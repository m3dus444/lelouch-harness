#!/usr/bin/env python
"""britania-resume -- pick the work back up after a stop, without redoing it.

For a session that is **still itself**: the context survived, the work did not
finish. A quota cap, a deliberate pause, a machine that went to sleep.

    resume.py            what to do, per worker
    resume.py --json     same, machine-readable

Not the same job as `britania-restore`. Restore rebuilds a session that lost its
memory. Resume assumes the memory is intact and asks a narrower, sharper
question: **what is each worker's position, and what would restarting it
destroy?**

The answer is usually not "nothing". The ship gate commits its fix rounds to a
shadow remote rather than to the worker's checkout, so a stalled worker can sit
**behind its own finished work**. Restart it cold and it rebuilds commits that
already exist -- which is the expensive failure this skill exists to prevent.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE_DB = Path(os.path.expanduser("~/.no-mistakes/state.sqlite"))
DEAD_WORKER = {"succeeded", "failed", "abandoned", "cancelled"}
DEAD_RUN = {"completed", "cancelled"}


def sh(cmd: list[str], timeout: int = 60) -> str | None:
    exe = shutil.which(cmd[0])
    if exe is None:
        return None
    try:
        p = subprocess.run(
            [exe, *cmd[1:]], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout if p.returncode == 0 else None


def orca(args: list[str]) -> dict:
    raw = sh(["orca", *args])
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict) or data.get("ok") is False:
        return {}
    return data.get("result", data) or {}


def same_project(a: str | None, b: str) -> bool:
    if not a:
        return False
    norm = lambda p: os.path.normcase(os.path.abspath(str(p))).replace("\\", "/").rstrip("/")
    return norm(a) == norm(b)


# ------------------------------------------------------------------ the gate


def gate_by_branch() -> dict[str, dict]:
    """Newest run per branch, with the heads the gate believes in.

    `head_sha` and `last_pushed_sha` are the interesting pair: they are the
    gate's position, which is not necessarily the worker's. `worktree_dir` is
    NOT useful here -- it points at the gate's own internal checkout, not at
    the worker's.
    """
    if not GATE_DB.exists():
        return {}
    try:
        con = sqlite3.connect(f"file:{GATE_DB.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}
    out: dict[str, dict] = {}
    try:
        for rid, branch, status, head, pushed, err in con.execute(
            "select id, branch, status, head_sha, last_pushed_sha, error"
            "  from runs order by created_at desc"
        ):
            if not branch or branch in out:
                continue
            steps = con.execute(
                "select step_name, status, last_activity_at from step_results"
                " where run_id = ? order by step_order", (rid,)
            ).fetchall()
            live = next((s for s, st, _ in steps if st not in ("completed", "skipped")), None)
            out[branch] = {
                "status": status,
                "stage": live or "done",
                "head": head,
                "pushed": pushed,
                "last_act": max((a for _, _, a in steps if a), default=None),
                "error": (err or "").strip().splitlines()[0] if err else None,
            }
    except sqlite3.Error:
        return {}
    finally:
        con.close()
    return out


# --------------------------------------------------------------- the workers


def checkouts(project: str) -> list[dict]:
    """Every worktree of this repo, with whatever Orca still knows about it.

    **Driven by git, not by Orca**, and that inversion is the whole point. Of 77
    workers on this machine, *none* still had a live terminal -- so a
    terminal-first join returns nothing and silently skips the case that matters
    most: **the client died, the gate run did not.** The pipeline lives in the
    daemon, so a worker with no terminal can still have work in flight.

    Terminals are used only to enrich. Their `worktreePath` is clean, unlike the
    worker's own `resource.worktreeId`, which arrives double-encoded
    (`JulienH\\u00c3\\u00a9lie`) and will not open a directory.
    """
    terms = [
        t for t in (orca(["terminal", "list", "--json"]).get("terminals") or [])
        if isinstance(t, dict) and t.get("worktreePath")
    ]
    workers = {
        w.get("agentTerminalHandle"): w
        for w in (orca(["orchestration", "worker-list", "--json"]).get("workers") or [])
        if isinstance(w, dict)
    }

    card_by_path = cards(project)
    out: list[dict] = []
    listing = sh(["git", "-C", project, "worktree", "list", "--porcelain"]) or ""
    path = branch = None
    for line in listing.splitlines() + [""]:
        if line.startswith("worktree "):
            path = line.split(" ", 1)[1].strip()
        elif line.startswith("branch "):
            branch = line.split(" ", 1)[1].strip().replace("refs/heads/", "")
        elif not line.strip() and path:
            if not same_project(path, project) and Path(path).exists():
                t = next((x for x in terms if same_project(x["worktreePath"], path)), {})
                w = workers.get(t.get("handle")) if t else None
                card = card_by_path.get(os.path.normcase(path.replace("\\", "/").rstrip("/")), {})
                out.append({
                    "path": path,
                    "branch": branch or "",
                    "state": (w or {}).get("workerState") or "no worker",
                    "handle": t.get("handle"),
                    "terminal": "live" if t else "gone",
                    "comment": (card.get("comment") or "").strip(),
                    "ticket": (branch or "").rsplit("/", 1)[-1],
                    "card_status": card.get("workspaceStatus"),
                })
            path = branch = None
    return out


def position(path: str, branch: str, gate: dict) -> dict:
    """Everything needed to tell a worker where it left off.

    A builder interrupted by a usage cap is the ordinary case, not an edge one,
    and it stops **mid-edit**: uncommitted files, possibly some banked commits
    the gate has not taken yet. So a dirty tree is not a fault to refuse over --
    it is the work, and it is what has to be described back to the worker.

    Four distinct things, and they are easy to conflate:

      dirty      edits in progress, never committed anywhere
      mine       commits it made that the gate does not have yet
      behind     commits the GATE made that this checkout does not have
      comment    the worker's own last progress note, from its Orca card
    """
    head = (sh(["git", "-C", path, "rev-parse", "HEAD"]) or "").strip()
    sh(["git", "-C", path, "fetch", "--quiet", "no-mistakes"], timeout=90)

    behind = [ln for ln in (sh(["git", "-C", path, "log", "--oneline",
                                f"HEAD..no-mistakes/{branch}"]) or "").splitlines() if ln.strip()]
    mine = [ln for ln in (sh(["git", "-C", path, "log", "--oneline",
                              f"no-mistakes/{branch}..HEAD"]) or "").splitlines() if ln.strip()]
    dirty = [ln.strip() for ln in (sh(["git", "-C", path, "status", "--porcelain"]) or "").splitlines() if ln.strip()]
    return {
        "head": head[:12],
        "gate_head": (gate.get("head") or "")[:12],
        "behind": behind,
        "mine": mine,
        "dirty": dirty,
        "files": [ln.split(None, 1)[-1] for ln in dirty][:8],
    }


def cards(project: str) -> dict[str, dict]:
    """Per-worktree Orca card, keyed by path. Carries `comment` -- the progress
    note §W asks every worker to keep, which is the one record of what it
    thought it was doing when it stopped."""
    out: dict[str, dict] = {}
    for w in orca(["worktree", "list", "--json"]).get("worktrees") or []:
        if isinstance(w, dict) and w.get("path"):
            out[os.path.normcase(str(w["path"]).replace("\\", "/").rstrip("/"))] = w
    return out


def act(w: dict, g: dict, pos: dict, dry: bool) -> list[str]:
    """Do the safe half of resuming, and report what it did.

    **`merge --ff-only` is the guard, not a risk.** It advances a branch only
    when the move is a pure fast-forward and refuses otherwise -- it cannot
    overwrite a commit, cannot drop uncommitted work, and cannot rewrite
    history. That refusal is exactly the check a human would perform by hand,
    which is why this is safe to run unattended and pointless to only describe.

    What is NOT done here, and why:

      a fresh dispatch    costs tokens and needs a spec; that is a decision
      a force-push        one-way, and the classifier refuses it anyway
      closing a ticket    the work is not verified from here
    """
    done: list[str] = []

    if pos["behind"]:
        if pos["dirty"]:
            # Not a refusal to help -- ff-only would decline anyway with edits in
            # the tree, and moving the branch under work in progress is exactly
            # what must not happen. The worker is told instead, and does it.
            done.append(f"did NOT fast-forward: {len(pos['dirty'])} file(s) still being edited. "
                        f"The worker commits or stashes first, then merges.")
        elif dry:
            done.append(f"would fast-forward {len(pos['behind'])} commit(s) from the gate's remote")
        else:
            out = sh(["git", "-C", w["path"], "merge", "--ff-only", f"no-mistakes/{w['branch']}"])
            done.append(
                f"fast-forwarded {len(pos['behind'])} commit(s); the checkout now has its own finished work"
                if out is not None else
                "fast-forward REFUSED -- the branch has diverged, so this needs a human"
            )

    alive = w.get("terminal") == "live" and (w.get("state") or "") not in DEAD_WORKER
    if alive and w.get("handle"):
        body = build_brief(w, pos)
        if dry:
            done.append(f"would send its position to dispatch:{w['handle'][:18]}")
        else:
            sent = sh(["orca", "orchestration", "send", "--to", f"dispatch:{w['handle']}",
                       "--type", "status", "--subject", "resume where you left off",
                       "--body", body, "--json"])
            done.append("told the worker what changed while it was parked (--type status)"
                        if sent else "could not reach the worker; treat it as gone")
    elif pos["dirty"] or pos["mine"] or pos["behind"]:
        done.append(
            "TERMINAL GONE -- this is not a resume. Open a fresh session in that "
            "worktree and let it run britania-restore; recovering a dead session is "
            "that skill's job, from inside, and its unfinished work is listed below."
        )

    return done


def build_brief(w: dict, pos: dict) -> str:
    """What to send a worker that is **parked, not dead**.

    A usage cap does not clear a session -- the process sits there with its
    context intact. So it already knows its ticket, its own note, and the files
    it was editing, and repeating those is the noise §0 exists to forbid.

    Send only what it **cannot** know:

      the gate's commits   made by a different agent, in the shadow repo
      a moved tree         if we fast-forwarded, its memory of those files is behind

    The ticket is named anyway, in one clause -- F-011 recorded a woken worker
    that simply did nothing, and a nudge that lands without a subject is cheap
    to make pointless.
    """
    parts = [f"Resuming {w.get('ticket') or 'your ticket'}. You were parked, not cancelled."]

    if pos["behind"]:
        if pos["dirty"]:
            parts.append(
                "The ship gate committed while you were parked, and your tree still has "
                f"edits, so nothing was moved under you. Commit or stash, then "
                f"`git merge --ff-only no-mistakes/{w.get('branch', '')}`: "
                + "; ".join(pos["behind"][:6]) + "."
            )
        else:
            parts.append(
                "The ship gate committed while you were parked and your checkout has been "
                "fast-forwarded onto it -- so the files on disk are AHEAD of what you "
                "remember. Re-read anything you touch before editing it. Do not rebuild: "
                + "; ".join(pos["behind"][:6]) + "."
            )
    else:
        parts.append("Nothing changed underneath you; the tree is as you left it.")

    parts.append("Continue from there and report worker_done when finished.")
    return " ".join(parts)


def verdict(w: dict, g: dict, pos: dict) -> list[str]:
    """What to do with this worker, most destructive mistake first."""
    lines: list[str] = []

    # The fast-forward itself is `act`'s job; this only names the commits, which
    # is what has to be handed to the worker so it does not rebuild them.
    if pos["behind"]:
        lines.append("Work it already has -- name these when you resume it:")
        for c in pos["behind"][:6]:
            lines.append(f"    {c}")

    if w.get("comment"):
        lines.append(f"Its own last note: \"{w['comment'][:100]}\"")
    if pos["dirty"]:
        lines.append(f"Work in progress, {len(pos['dirty'])} file(s): {', '.join(pos['files'])}")
    if pos["mine"]:
        lines.append(f"{len(pos['mine'])} commit(s) of its own the gate has not taken yet")

    if g:
        if g["status"] in DEAD_RUN:
            lines.append(f"Gate run is {g['status']}; nothing of the gate's is waiting.")
        elif g["stage"] == "review":
            lines.append(
                "Gate is at review. A timeout here RECYCLES the agent inside the step -- "
                "a new process with an advancing head is still working. Check before restarting."
            )
        else:
            lines.append(f"Gate is at {g['stage']}, run {g['status']}.")
        if g.get("error"):
            lines.append(f"Last gate error: {g['error'][:90]}")

    if w.get("terminal") == "gone" and g and g["status"] not in DEAD_RUN:
        lines.append(
            "Its terminal is gone but the gate run is NOT -- the pipeline lives in the "
            "daemon, so the client died, not the run. Check `no-mistakes axi status` "
            "here; re-running `axi run --intent ...` with HEAD unchanged reattaches."
        )
    elif (w.get("state") or "") in DEAD_WORKER or w.get("terminal") == "gone":
        lines.append(f"Worker is {w['state']}, terminal {w['terminal']} -- resuming means a fresh dispatch, not a nudge.")
    else:
        lines.append(f"Worker is {w['state']}; send it a `--type status` message rather than restarting.")

    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="Resume in-flight work without redoing it.")
    ap.add_argument("--path", default=os.getcwd())
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true", help="include settled workers")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what it would do without touching anything")
    args = ap.parse_args()
    project = str(Path(args.path).resolve())

    gate = gate_by_branch()
    workers = checkouts(project)
    def unfinished(w: dict) -> bool:
        """Worth resuming if either half is still alive: the worker, or the run.
        A settled worker over a live run is the client-died case, which is the
        one a terminal-first view would have missed entirely."""
        g = next((v for k, v in gate.items() if w["branch"] and k.endswith(w["branch"])), {})
        return (w.get("state") or "") not in DEAD_WORKER or (g and g["status"] not in DEAD_RUN)

    if not args.all:
        workers = [w for w in workers if unfinished(w)]

    report = []
    for w in workers:
        g = next((v for k, v in gate.items() if w["branch"] and k.endswith(w["branch"])), {})
        pos = position(w["path"], w["branch"], g) if w["branch"] else {"head": "?", "gate_head": "", "behind": [], "dirty": 0}
        report.append({
            "worker": w, "gate": g, "position": pos,
            "did": act(w, g, pos, args.dry_run),
            "verdict": verdict(w, g, pos),
        })

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    print(f"RESUME -- {Path(project).name}" + ("   (dry run, nothing touched)" if args.dry_run else ""))
    print()
    if not report:
        print("  No worker needs resuming.")
        print("  Re-arm the wait before you say anything, or the session is deaf:")
        print("    orca orchestration check --wait --types worker_done,escalation,question")
        return 0

    for r in report:
        w, pos = r["worker"], r["position"]
        print(f"  {w['branch'] or '(no branch)'}   worker {w['state']}"
              f" (terminal {w['terminal']})   local {pos['head']}"
              + (f"   gate {pos['gate_head']}" if pos["gate_head"] else ""))
        for line in r["did"]:
            print(f"    -> {line}")
        for line in r["verdict"]:
            print(f"       {line}")
        print()

    print("  Re-arm the wait yourself -- it must be backgrounded, which a script cannot do")
    print("  on your behalf without detaching it from the session that needs to hear it:")
    print("    orca orchestration check --wait --types worker_done,escalation,question")
    return 0


if __name__ == "__main__":
    sys.exit(main())
