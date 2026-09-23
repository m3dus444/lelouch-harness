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

Two rules this file has had to learn the hard way, both of them about the
*report* rather than the behaviour:

**A worker is addressed by its dispatch id, and a bounce is not a death.** Mail
routes by `dispatchId`; a terminal handle is a different address for a different
courier. Sending to a handle bounces, and reading that bounce as "the worker is
gone" once recommended replacement dispatches into fresh worktrees for two
workers that were both alive and both holding committed work -- the exact trap
this skill warns about in its own output. Liveness has an independent source,
`orca terminal list`, and a failed delivery is not evidence against it.

**The dry run checks what the real run will check.** It used to predict from
`behind` alone and promised a fast-forward of 14 commits on a branch that was
also 3 ahead; the real run refused it minutes later. A dry run exists to be read
before committing to the real thing, so its checks are the real one's checks.
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

    **Each row carries two addresses, and they are not interchangeable.**
    `dispatch` is where mail goes (`--to dispatch:<dispatchId>`); `handle` is
    where a keystroke goes (`orca terminal send --terminal <handle>`). Using the
    handle as a mail address is what F-060 did, and the bounce it produced was
    then read as a dead worker. The field is `dispatchId`, camelCase -- a read
    written for `dispatch_id` returns `None` silently and loses the address
    altogether, so both spellings are tried and neither is guessed at.
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
                    "dispatch": (w or {}).get("dispatchId") or (w or {}).get("dispatch_id"),
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


def ff_possible(path: str, branch: str) -> tuple[bool, str]:
    """Will `git merge --ff-only no-mistakes/<branch>` actually move this branch?

    **The forward check.** It exists because the dry run used to predict a
    fast-forward from `behind` alone and never looked at the state it was about
    to move into: 14 commits behind was reported as *"would fast-forward 14
    commit(s)"* on a branch that was also 3 commits ahead. The two are not
    exclusive -- a diverged branch is behind *and* ahead -- and `--ff-only`
    refuses that by definition, which the real run then did, minutes later.

    The damage there was to the decision, not to the repository. The safety held
    the whole time; the plan built on the promise did not. So the two paths now
    ask the same two questions, in the same order, and can no longer disagree:

      does the ref exist        a gate-owned worktree may never have pushed, and
                                a fast-forward onto a ref with no commits in it
                                is not a thing that can happen
      is HEAD an ancestor       the only condition under which git will move a
                                branch without a merge commit

    Both are asked against the same refs the merge itself would use, and both
    are cheap. Nothing here writes.
    """
    ref = f"no-mistakes/{branch}"
    if sh(["git", "-C", path, "rev-parse", "--verify", "--quiet", ref]) is None:
        return False, f"{ref} does not exist in this checkout -- nothing to fast-forward onto"
    # `--is-ancestor` answers in its exit code: 0 yes, 1 no. `sh` returns None
    # for any non-zero, and an empty string -- falsy, but not None -- for yes.
    if sh(["git", "-C", path, "merge-base", "--is-ancestor", "HEAD", ref]) is None:
        return False, f"HEAD is not an ancestor of {ref} -- the branch has diverged"
    return True, f"HEAD is an ancestor of {ref}"


WAKE_LINE = ("You were parked, not cancelled. Your position is in your mail: run "
             "`orca orchestration check` and carry on from it.")


def wake(handle: str | None, dry: bool) -> str:
    """Type one line into a worker's terminal, so it reads the mail just queued.

    Mail is pull. A worker frozen at a usage cap is sitting at its prompt and
    will not run `orchestration check` until something types into it -- so
    without this, a resume done while nobody is at the keyboard queues positions
    that nobody reads until morning.

    **Only at a turn boundary, and only if one comes.** Injecting mid-turn
    corrupts whatever the agent was doing. A terminal that does not reach
    tui-idle within the wait is working, which is the state a wake exists to
    produce, so it is left alone rather than typed into late.
    """
    if not handle:
        return "no terminal handle, so no wake -- it reads the mail on its next check"
    if dry:
        return f"would wake terminal {handle} with one line, once it is idle"
    idle = sh(["orca", "terminal", "wait", "--terminal", handle, "--for", "tui-idle",
               "--timeout-ms", "60000"], timeout=90)
    if idle is None:
        return f"did NOT wake {handle}: not idle within 60s, so it is working -- left alone"
    sent = sh(["orca", "terminal", "send", "--terminal", handle,
               "--text", WAKE_LINE, "--enter"], timeout=30)
    # `ok` acknowledges the courier, not the recipient: a wake spent while the
    # window was still capped once returned ok and two builders sat frozen four
    # more hours. So this reports a delivery, and recovery is read off the screen.
    return (f"wake line delivered to {handle} -- delivered, not acted on: read its screen "
            f"on the next sweep before calling it recovered" if sent is not None else
            f"the wake to {handle} did NOT land; the mail is still queued for it")


def act(w: dict, g: dict, pos: dict, dry: bool, wake_terminal: bool = False) -> list[str]:
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
        else:
            # Asked once, before either path speaks, so that the dry run's
            # sentence and the real run's sentence are answers to the same
            # question rather than two guesses that happen to differ.
            can, why = ff_possible(w["path"], w["branch"])
            if not can:
                done.append(
                    f"will NOT fast-forward, in either mode: {why}"
                    + (f"; {len(pos['mine'])} commit(s) of its own are what put it there" if pos["mine"] else "")
                    + ". The merge is not attempted, and the gate's commits stay where they are."
                )
            elif dry:
                done.append(f"would fast-forward {len(pos['behind'])} commit(s) from the gate's "
                            f"remote -- checked against the real condition, not assumed: {why}")
            else:
                out = sh(["git", "-C", w["path"], "merge", "--ff-only", f"no-mistakes/{w['branch']}"])
                done.append(
                    f"fast-forwarded {len(pos['behind'])} commit(s); the checkout now has its own finished work"
                    if out is not None else
                    "fast-forward REFUSED although the ancestry check passed -- the remote moved "
                    "under this run, or a hook declined it. This one needs a human."
                )

    # Two addresses, two couriers, and F-060 is what happens when they are
    # confused: mail routes by `dispatchId`, a keystroke routes by terminal
    # handle. `--to dispatch:<terminal handle>` bounces. That bounce was read as
    # "both workers are gone, treat them as dead" while both terminals were
    # alive and connected, and acting on it meant replacement dispatches into
    # fresh worktrees, abandoning the gate-side fix commits already sitting in
    # the existing ones. So: address by dispatch id, never fall back to the
    # handle, and never let a delivery result decide whether a worker is alive.
    live_terminal = w.get("terminal") == "live"
    settled = (w.get("state") or "") in DEAD_WORKER
    dispatch = w.get("dispatch")

    if live_terminal and dispatch and not settled:
        body = build_brief(w, pos)
        if dry:
            done.append(f"would send its position to dispatch:{dispatch} (--type status)")
        else:
            sent = sh(["orca", "orchestration", "send", "--to", f"dispatch:{dispatch}",
                       "--type", "status", "--subject", "resume where you left off",
                       "--body", body, "--json"])
            done.append(
                "queued its position for the worker (--type status). Queued, not read: mail is "
                "pull, so it lands when the worker next runs `orchestration check`"
                if sent else
                "the send did NOT land -- UNDELIVERED, which is not dead. Liveness is read from "
                "`orca terminal list`, and that still shows this terminal live. Do not replace a "
                "worker on a failed delivery."
            )
        if wake_terminal and (dry or sent):
            done.append(wake(w.get("handle"), dry))
    elif live_terminal and not dispatch:
        done.append(
            f"its terminal is LIVE but `worker-list` carries no dispatch id for it, so it has no "
            f"mail address. Do NOT substitute the terminal handle -- that address bounces, and a "
            f"bounce has already been misread once as a dead worker. Either find its dispatch id "
            f"in `orca orchestration worker-list --json`, or reach it as a terminal instead: "
            f"orca terminal send --terminal {w.get('handle')} --text \"<one line>\" --enter"
        )
    elif live_terminal and settled:
        done.append(f"worker record says {w['state']} while its terminal is LIVE. The terminal is "
                    f"the independent reading and the record is a memory of one; look at the "
                    f"terminal before treating this ticket as finished.")
    elif pos["dirty"] or pos["mine"] or pos["behind"]:
        # Nothing to message: the agent is gone, and only C.C invokes these
        # skills, only in your session. So this is material for the replacement
        # dispatch YOU write, not a briefing anyone else will read.
        done.append("TERMINAL GONE -- nothing to nudge. This needs a replacement dispatch "
                    "from you; its unfinished state is below, to go into the spec.")
        if pos["dirty"]:
            done.append(
                f"DECIDE FIRST: {len(pos['dirty'])} uncommitted file(s) live only in that "
                f"worktree. §6 dispatches Build and Fix with `--worktree new-top-level`, so "
                f"a replacement gets a FRESH checkout and this work is stranded. Either "
                f"dispatch into the existing worktree, or bank it first -- it is not on any "
                f"branch and nothing else knows it exists."
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

    # Liveness first, and it is read from `orca terminal list` alone. Not from a
    # delivery result: a bounced message means undeliverable, and the one time
    # it was read as death the recommendation was to replace two working
    # builders and walk away from their committed work.
    if w.get("terminal") == "live":
        lines.append(
            f"Its terminal is LIVE (worker record says {w['state']}). Resuming it is mail, not a "
            f"dispatch, and the address is "
            + (f"dispatch:{w['dispatch']}" if w.get("dispatch")
               else "its dispatch id -- which `worker-list` did not carry, so look it up")
            + " -- never its terminal handle."
        )
        lines.append(
            "A live terminal is still not a working agent: it stays live and connected around a "
            "session that hit a usage cap and cannot act. Read what the screen shows before "
            "concluding it is busy -- `britania-restore` classifies each builder's screen."
        )
    elif g and g["status"] not in DEAD_RUN:
        lines.append(
            "Its terminal is gone but the gate run is NOT -- the pipeline lives in the "
            "daemon, so the client died, not the run. Check `no-mistakes axi status` "
            "here; re-running `axi run --intent ...` with HEAD unchanged reattaches."
        )
    else:
        lines.append(f"Worker is {w['state']}, terminal gone -- resuming means a fresh dispatch, not a nudge.")

    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="Resume in-flight work without redoing it.")
    ap.add_argument("--path", default=os.getcwd())
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true", help="include settled workers")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what it would do without touching anything")
    ap.add_argument("--wake", action="store_true",
                    help="after queuing a worker's position, type one line into its terminal "
                         "so a worker frozen at a cap reads it (autopilot uses this)")
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
        # The branchless fallback carries every key `act` and `verdict` read, in
        # the type they read it as. It used to omit `mine`, which turns a
        # detached-HEAD worktree into a KeyError that takes the whole report
        # down -- a checkout nobody can describe is exactly one worth reporting.
        pos = position(w["path"], w["branch"], g) if w["branch"] else {
            "head": "?", "gate_head": "", "behind": [], "mine": [], "dirty": [], "files": []}
        report.append({
            "worker": w, "gate": g, "position": pos,
            "did": act(w, g, pos, args.dry_run, args.wake),
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
        # The dispatch id is on the row because it is the address the operator
        # will type next, and the one thing that must not be improvised from the
        # handle sitting next to it.
        print(f"  {w['branch'] or '(no branch)'}   worker {w['state']}"
              f" (terminal {w['terminal']}, dispatch {w.get('dispatch') or 'unknown'})"
              f"   local {pos['head']}"
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
