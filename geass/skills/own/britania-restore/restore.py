#!/usr/bin/env python
"""britania-restore -- rebuild a session's working state from durable sources.

For a session that has no continuity: a fresh terminal after a crash, a power
cut, or a deliberate `/clear`. It answers "where was I" **without asking the
previous session anything**, because the previous session may not have got the
chance to say.

    restore.py --mode clear    the briefing, for a conversation wiped in place
    restore.py --mode crash    the briefing, for a process that died
    restore.py --json          same, machine-readable

**The mode is stated, never inferred.** A `/clear` and a crash leave different
machines behind -- the first keeps its process, its background tasks and its
waiters, the second keeps none of them -- and the cause is a fact the user has
and this script does not. When it is omitted the briefing asks for it and stops,
because the one time it was inferred, a restored session read its *own* live
wait as an orphan from a dead one and reached for `orca orchestration reset` on
a Run with a worker still building in it. A human stopped the call.

**It derives; it never replays a record.** Nothing here reads a handoff file
that a dying session was supposed to write, because the case this exists for is
exactly the case where it did not. Every line comes from something that survives
independently:

    tasks-axi          the backlog, and the decisions held against it
    orca               Runs, terminals, workers
    orca terminal      what each builder's screen is actually showing
    ~/.no-mistakes     where each branch stands in the ship gate
    git                the branch and whether the tree is dirty
    CONTEXT.md         the vocabulary the tickets are written in

**What it cannot recover is the conversation.** That is not a gap to engineer
around -- it is the reason the contract puts decisions in the backlog instead of
leaving them in chat. If something mattered and was never written down, it is
gone, and the honest response is to say so rather than to reconstruct a
plausible version of it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE_DB = Path(os.path.expanduser("~/.no-mistakes/state.sqlite"))
MODES = ("clear", "crash")


def sh(cmd: list[str], cwd: str | None = None, timeout: int = 60) -> str | None:
    """Resolve the executable (Windows .CMD shims) and force UTF-8 (a locale
    codec raises on an accented path, inside a thread, and returns empty)."""
    exe = shutil.which(cmd[0])
    if exe is None:
        return None
    try:
        p = subprocess.run(
            [exe, *cmd[1:]], cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout if p.returncode == 0 else None


def orca(args: list[str], cwd: str | None = None) -> dict:
    raw = sh(["orca", *args], cwd=cwd)
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


# ------------------------------------------------------------------- the Run


def find_run(project: Path) -> tuple[str | None, str, str]:
    """(run_id, how_it_was_found, objective) for this project's Run.

    This is the awkward one. **A Run carries no project identity** -- only an
    id, a free-text objective and a `coordinator_handle` -- and a machine with
    several projects has several Runs. Two signals, strongest first:

    1. Its coordinator handle is a terminal living in this project. Exact, but
       it fails in precisely the situation restore exists for: after a crash the
       old terminal is gone, so the handle points at nothing.
    2. Its objective names the project. A convention rather than a guarantee,
       which is why the briefing prints *how* the Run was identified and asks
       for confirmation instead of binding silently.
    """
    runs = orca(["orchestration", "run-list", "--json"]).get("runs") or []
    runs.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    if not runs:
        return None, "no Runs exist", ""

    here = {
        t.get("handle")
        for t in (orca(["terminal", "list", "--json"]).get("terminals") or [])
        if isinstance(t, dict) and same_project(t.get("worktreePath"), str(project))
    }
    for r in runs:
        if r.get("coordinator_handle") in here:
            return r.get("id"), "its coordinator terminal is in this project", str(r.get("objective") or "")

    name = project.resolve().name.lower()
    for r in runs:
        if name in str(r.get("objective") or "").lower():
            return r.get("id"), f"its objective names {project.resolve().name} -- CONFIRM before binding", str(r.get("objective") or "")

    newest = runs[0]
    return newest.get("id"), "GUESS: newest Run on the machine, project unverified", str(newest.get("objective") or "")


def bound_run(project: Path) -> str | None:
    run = orca(["orchestration", "run-current", "--json"], cwd=str(project)).get("run")
    return (run or {}).get("id") if isinstance(run, dict) else None


# ------------------------------------------------------------------ the rest


def git_state(project: Path) -> dict:
    branch = sh(["git", "-C", str(project), "rev-parse", "--abbrev-ref", "HEAD"])
    dirty = sh(["git", "-C", str(project), "status", "--porcelain"])
    ahead = sh(["git", "-C", str(project), "rev-list", "--count", "@{u}..HEAD"])
    return {
        "branch": (branch or "?").strip(),
        "dirty": len([ln for ln in (dirty or "").splitlines() if ln.strip()]),
        "unpushed": (ahead or "").strip() or "?",
    }


def glossary(project: Path) -> dict:
    path = project / "CONTEXT.md"
    if not path.exists():
        return {"present": False, "tracked": False, "terms": 0}
    tracked = sh(["git", "-C", str(project), "ls-files", "--error-unmatch", "CONTEXT.md"]) is not None
    text = path.read_text(encoding="utf-8", errors="replace")
    in_vocab, terms = False, 0
    for line in text.splitlines():
        if line.startswith("## "):
            in_vocab = "vocab" in line.lower() or "glossar" in line.lower()
        elif in_vocab and line.strip().startswith(("- ", "**", "### ")):
            terms += 1
    return {"present": True, "tracked": tracked, "terms": terms}


def board(project: Path) -> str:
    """Reuse britania-board rather than re-deriving the same three registries."""
    script = HERE.parent / "britania-board" / "board.py"
    if not script.exists():
        return "  (britania-board not installed; state unavailable)"
    out = sh([sys.executable, str(script)], cwd=str(project), timeout=180)
    return out.rstrip() if out else "  (board returned nothing)"


def contradictions(project: Path) -> list[str]:
    """Where the registries disagree with each other.

    **`backlog.md` and `tasks-axi` cannot disagree** -- the file *is* the store,
    not a rendering of one, so there is nothing to reconcile there.

    What genuinely diverges is the boundary *between* systems, because each one
    is updated by a different actor at a different moment and a crash lands
    between them. Every check below is a shape run 2 actually produced:

      backlog says done, gate never finished   the fix may not have shipped
      backlog says done, PR still open         nobody merged it
      backlog in flight, no live worker        a crash left the ticket started
      live worker, backlog not in flight       the start was never recorded
      a registered worktree is gone from disk  removal died halfway

    These are reported, never repaired. A restored session does not know which
    side is right, and guessing would turn a visible inconsistency into an
    invisible one -- which is how the worst of these got expensive in the first
    place.
    """
    sys.path.insert(0, str(HERE.parent / "britania-board"))
    try:
        import board as B  # type: ignore
    except Exception:
        return []

    cwd = os.getcwd()
    try:
        os.chdir(project)
        gate = B.gate_rows()
        crew = B.workers(None)
        flight, _queued, _held = B.backlog()
        done = {t.get("id") for t in B.tasks_axi("done") if t.get("id")}
    except Exception:
        return []
    finally:
        os.chdir(cwd)
        sys.path.pop(0)

    DEAD = {"succeeded", "failed", "abandoned", "cancelled"}
    out: list[str] = []

    for t in flight:
        tid = t.get("id")
        if not tid:
            continue
        state = (crew.get(tid) or {}).get("state")
        if state is None:
            out.append(f"{tid}: backlog says in flight, Orca has no worker for it "
                       f"-- a crash between start and dispatch, or the ticket was never released")
        elif state in DEAD:
            out.append(f"{tid}: backlog says in flight, its worker is {state} "
                       f"-- the completion was never written back")

    for tid, w in crew.items():
        if (w.get("state") or "") in DEAD:
            continue
        if tid not in {t.get("id") for t in flight} and tid not in done:
            out.append(f"{tid}: a worker is {w.get('state')}, the backlog does not have it in flight")

    for tid in sorted(done):
        g = gate.get(tid)
        if not g:
            continue
        if g.get("run_status") not in (None, "completed"):
            out.append(f"{tid}: closed in the backlog, gate run is {g['run_status']} "
                       f"at {g['stage']} -- check the work actually shipped")
        elif g.get("pr_state") == "open":
            out.append(f"{tid}: closed in the backlog, PR #{g['pr']} is still open "
                       f"(last looked {g['pr_age']} ago)")

    listed = sh(["git", "-C", str(project), "worktree", "list", "--porcelain"]) or ""
    for line in listed.splitlines():
        if line.startswith("worktree "):
            path = line.split(" ", 1)[1].strip()
            if path and not Path(path).exists():
                out.append(f"git registers a worktree at {path}, which is not on disk")

    return out


# ------------------------------------------------------------- the builders


# What a Claude Code TUI draws only while a turn is genuinely running.
#
# The composer prompt is deliberately NOT on this list and must never be added
# to it: the TUI keeps drawing `>` underneath the spinner the entire time the
# agent works, so "a prompt is showing" would read as idle on a worker that is
# mid-edit. The markers below only exist while something is in flight.
WORKING = (
    "esc to interrupt",
    "ctrl+b to run in background",
    "tokens)",
    "tokens ·",
)

# The animated spinner glyphs, without the completed-step bullet. A finished
# tool call keeps its bullet on screen for as long as the screen is not
# repainted, so including it would call a long-dead session busy.
SPINNER = re.compile(r"^\s*[*✦✳✴✶✸✹✻✽·]\s+\S.*…")

# A capped session's own notice, which is the only evidence that separates
# "quiet because it is thinking" from "quiet because it cannot act". It usually
# names its own reset time, so the deciding line is printed verbatim rather
# than summarised. "approaching" is excluded on purpose: that one is a warning
# drawn by a session that is still working.
CAPPED = ("session limit", "usage limit", "limit reached", "quota exceeded")

# Chrome the TUI draws whatever is happening. Never evidence of anything.
CHROME = ("bypass permissions", "shift+tab to cycle", "for shortcuts", "? for help")


def substantive(tail: list[str]) -> str:
    """The last line on the screen that says something -- skipping the rules,
    the empty composer and the permissions footer, which are always there."""
    for line in reversed(tail):
        s = line.strip()
        if not s or set(s) <= set("─━│—-=_ ") or s in ("❯", ">", "|"):
            continue
        if any(c in s.lower() for c in CHROME):
            continue
        return s
    return ""


def classify(tail: list[str]) -> tuple[str, str]:
    """building | idle | capped -- and the line that decided it.

    Read from the BOTTOM upwards, stopping at the first decisive line, because
    the most recent line is the one describing the present. A capped session
    keeps its dead spinner on screen *above* the cap notice, so a top-down scan
    finds the spinner first and calls a frozen agent busy. That is not a
    hypothetical ordering: two builders sat four hours on a cap notice with a
    stale spinner over it, and were reported as "both builds are running
    again".

    There is a fourth answer, `unreadable`, and it is not folded into `idle`.
    An instrument that could not take its measurement has to say so rather than
    return the reassuring value -- reporting a terminal nobody could read as
    idle is how this briefing was wrong in the other direction, calling live
    workers dead.
    """
    for line in reversed(tail):
        low = line.lower()
        if "approaching" not in low and any(m in low for m in CAPPED):
            return "capped", line.strip()
        if any(m in low for m in WORKING) or SPINNER.match(line):
            return "building", line.strip()
    if not tail:
        return "unreadable", "the terminal returned no screen"
    return "idle", substantive(tail)


def terminal_tail(handle: str | None, rows: int = 40) -> list[str]:
    """The last rendered rows of one terminal, or nothing.

    `--screen` rather than the default accumulated stream. The stream returns
    every repaint stacked on top of the last, so a TUI comes back as fragments
    -- one `clear` typed keystroke by keystroke reads as `cclclecleaclear`.
    The question here is what the terminal is *showing*, which is the question
    `--screen` answers and the other one does not.
    """
    if not handle:
        return []
    term = orca(["terminal", "read", "--terminal", handle, "--screen",
                 "--limit", str(rows), "--json"]).get("terminal") or {}
    return [str(x) for x in (term.get("tail") or [])]


def builders(project: Path) -> list[dict]:
    """Every builder terminal of this project, classified by what it SHOWS.

    The briefing used to report on builders without once looking at one, and it
    was wrong in **both** directions on the same night: two live workers
    reported dead, because a message to them had bounced; and two workers
    frozen on a cap notice reported as running again, because their terminals
    still answered. Both readings came from metadata -- a handle, a delivery
    receipt, a `connected` flag -- and metadata describes the terminal, not the
    agent inside it.

    `orca terminal list` says `connected: true` for a session whose agent hit a
    usage cap four hours ago and cannot act. The screen says so plainly. So
    read the screen: one instrument settles both directions, and it costs one
    call per builder.

    Enumerated from `git worktree list` rather than from the worker registry,
    for the same reason `britania-resume` does it: a worktree that exists is a
    fact, a worker record is a memory of one.
    """
    listed = sh(["git", "-C", str(project), "worktree", "list", "--porcelain"]) or ""
    trees: dict[str, str] = {}
    path = branch = None
    for line in listed.splitlines() + [""]:
        if line.startswith("worktree "):
            path = line.split(" ", 1)[1].strip()
        elif line.startswith("branch "):
            branch = line.split(" ", 1)[1].strip().replace("refs/heads/", "")
        elif not line.strip() and path:
            if not same_project(path, str(project)) and Path(path).exists():
                trees[path] = branch or ""
            path = branch = None

    out: list[dict] = []
    for t in orca(["terminal", "list", "--json"]).get("terminals") or []:
        if not isinstance(t, dict) or not t.get("worktreePath"):
            continue
        tree = next((p for p in trees if same_project(t["worktreePath"], p)), None)
        if tree is None:
            continue
        tail = terminal_tail(t.get("handle"))
        state, evidence = classify(tail)
        out.append({
            "branch": trees[tree],
            "path": tree,
            "handle": t.get("handle"),
            "connected": bool(t.get("connected")),
            "state": state,
            "evidence": evidence,
        })
    return sorted(out, key=lambda b: (b["branch"], b["path"]))


# ------------------------------------------------------------------ briefing


def ask_for_mode() -> int:
    """Refuse to brief rather than guess which kind of restart this was.

    Asking costs one line and one re-run. The alternative was measured: after a
    `/clear`, `waiter_exists` looked exactly like an orphaned waiter from a dead
    session -- it was the restored session's own armed wait, still running,
    still delivering into the new conversation -- and the remedy reached for was
    `orca orchestration reset --messages` on a live Run.

    The two errors do not cost the same, which is why there is no default.
    Treating a crash as a clear costs a wait that never returns, caught by the
    next heartbeat. Treating a clear as a crash destroys live state.
    """
    print("RESTORE -- the mode was not stated, and it is not inferred here")
    print()
    print("  Ask, in one line, before anything else:")
    print()
    print("      \"Was that a /clear, or did the session crash?\"")
    print()
    print("  Then re-run with the answer:")
    print()
    print("      restore.py --mode clear     same process, conversation wiped")
    print("      restore.py --mode crash     process gone, machine restarted")
    print()
    print("  Nothing on disk settles this reliably, and the evidence that looks")
    print("  like it does is the evidence that misled once already: a live wait")
    print("  looks like an orphaned one. The cause of the restart belongs to the")
    print("  person who caused it.")
    return 2


def sweep_note(project: Path, mode: str) -> list[str]:
    """An autopilot window still open means a sweep that may not be.

    The sweep is a session-scoped cron job: a /clear keeps it, because the
    process survived, and a crash takes it. Either way the marker still names
    an id, and after a crash that id points at nothing.
    """
    try:
        marker = json.loads((project / ".lelouch" / "afk.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(marker, dict) or not marker.get("autopilot"):
        return []
    job = marker.get("sweep") or "none recorded"
    if mode == "clear":
        return [f"An autopilot window is open (sweep {job}). A /clear keeps the sweep:",
                "CronList to confirm it is still scheduled, and re-arm only if not."]
    return [f"An autopilot window is open, and its sweep ({job}) died with the",
            "process. Re-arm it -- `afk.py start --autopilot` printed the exact",
            "CronCreate call, and afk.py's SWEEP_PROMPT holds it -- then record the",
            "new id with `afk.py sweep <job-id>`."]


def session_note(mode: str, run_id: str | None) -> list[str]:
    """What this restart did, and did not, take away -- and the remedy for it.

    This is the half of the briefing that the mode exists for. Everything else
    here reads the same in either mode; background tasks, waiters and the
    remedy for a fenced consumer do not.
    """
    if mode == "clear":
        return [
            "A /clear resets the conversation, not the process. Every background",
            "task armed before it is STILL RUNNING and STILL YOURS, and its",
            "notification lands in this conversation when it fires.",
            "",
            "So `waiter_exists` here is your own armed wait working as designed,",
            "not an orphan and not evidence of a dead session. Let it deliver, or",
            "TaskStop it and arm one -- and check the task list before deciding,",
            "since the answer is in the process you are still running in.",
            "",
            "`orca orchestration reset` is NEVER the remedy in this mode. It",
            "throws away live delivery state to fix a problem you do not have.",
            "Re-binding is the remedy, and it is one command:",
            "",
            f"    orca orchestration run-use --id {run_id or '<run id>'}",
            "",
            "run-use worked at two clears and was forgotten at the third, where",
            "reset --messages was reached for instead, on a Run with a worker",
            "still building in it. Orca terminals, workers and dispatches are",
            "untouched by a clear: the builders below are the ones the previous",
            "conversation dispatched, and they never noticed.",
        ]
    return [
        "The process died, so every pre-crash `check --wait` died with it. A",
        "registered waiter may genuinely be an orphan here, and displacing it is",
        "legitimate -- but read what the scope actually removes rather than",
        "asserting it, and name the in-flight dispatches first. A peek showing",
        "zero unread proves nothing about thread history, acknowledged",
        "deliveries, or a worker_done still in routing.",
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="Rebuild session state from durable sources.")
    ap.add_argument("--path", default=os.getcwd())
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--mode", choices=MODES,
                    help="what ended the last session: `clear` (same process, "
                         "conversation wiped) or `crash` (process gone). Omitted, "
                         "it asks -- it is never inferred from the evidence.")
    args = ap.parse_args()
    project = Path(args.path).resolve()

    # A builder's screen is full of what a Windows console's cp1252 stdout
    # cannot encode -- spinner glyphs, box drawing, the tool-result elbow -- and
    # encoding it is fatal by default. The encoding is left alone so a terminal
    # that can render them still does; only the failure mode changes. A briefing
    # that raises while printing the line it exists to print would be a worse
    # instrument than one that prints a question mark.
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, OSError, ValueError):
        pass

    # Asking is impossible down the --json path, so that one reports the mode as
    # unknown and says nothing that depends on it. Reporting `unknown` is the
    # point: a machine-readable briefing that picked a mode would be the same
    # inference this option exists to remove, only harder to notice.
    if args.mode is None and not args.json:
        return ask_for_mode()

    run_id, how, objective = find_run(project)
    bound = bound_run(project)
    state = {
        "project": project.name,
        "mode": args.mode or "unknown",
        "mode_stated": args.mode is not None,
        "git": git_state(project),
        "glossary": glossary(project),
        "run": {"id": run_id, "identified_by": how, "objective": objective, "bound": bound},
        "builders": builders(project),
        "gate_db": GATE_DB.exists(),
    }

    if args.json:
        if args.mode is None:
            state["mode_note"] = (
                "unknown: no --mode was given and the cause of a restart is not "
                "inferred here. Ask whether it was a /clear or a crash before "
                "acting on anything that depends on it -- a waiter, a re-arm, or "
                "any command that resets run state."
            )
        print(json.dumps(state, indent=2))
        return 0

    g, gl = state["git"], state["glossary"]
    print(f"RESTORE -- {project.name}   (mode: {args.mode}, as stated by the user)")
    print()
    print(f"  branch     {g['branch']}"
          + (f", {g['dirty']} uncommitted file(s)" if g["dirty"] else ", clean")
          + (f", {g['unpushed']} unpushed" if g["unpushed"] not in ("0", "?") else ""))
    if gl["present"]:
        print(f"  glossary   CONTEXT.md, ~{gl['terms']} terms"
              + ("" if gl["tracked"] else "  -- NOT TRACKED BY GIT, so no worker can read it"))
    else:
        print("  glossary   CONTEXT.md missing -- workers have no shared vocabulary")

    print()
    print("  Run")
    if bound:
        print(f"    bound to {bound}. Your mail is readable.")
    elif run_id:
        print(f"    NOT BOUND. This terminal cannot read deliveries until it is --")
        print(f"    `check` will answer `consumer_fenced`, which is not a dead Run.")
        print()
        print(f"      orca orchestration run-use --id {run_id}")
        print()
        print(f"    candidate  {run_id}")
        print(f"    chosen by  {how}")
        if objective:
            print(f"    objective  {objective[:78]}")
    else:
        print(f"    none found ({how}). A new Run is created by the orchestration skill.")

    print()
    print(f"  After a {args.mode}")
    for line in session_note(args.mode, run_id):
        print(f"    {line}" if line else "")
    for line in sweep_note(project, args.mode):
        print(f"    {line}")

    print()
    print(board(project))

    crew = state["builders"]
    print()
    print("  Builders, read from their own screens")
    if not crew:
        print("    none -- no terminal is open on a worktree of this project")
    for b in crew:
        print(f"    {b['state']:<10} {b['branch'] or b['path']}")
        if b["evidence"]:
            print(f"               {b['evidence'][:92]}")

    frozen = [b for b in crew if b["state"] == "capped"]
    if frozen:
        print()
        print("    A capped session has no self-wake. It does not poll for its own reset;")
        print("    it stops, and something outside has to reach it. Mail will not: mail is")
        print("    pull, and a session that cannot act cannot run `check` to collect it.")
        print("    The only push that lands on a parked TUI is a keystroke:")
        for b in frozen:
            print(f"      orca terminal send --terminal {b['handle']} --text \"<one line>\" --enter")
        print()
        print("    `ok:true` on that call acknowledges THE COURIER, NOT THE RECIPIENT.")
        print("    It means the keystroke was delivered, not that the agent acted on it.")
        print("    Confirm recovery by reading the terminal again, never by the send's own")
        print("    return value -- a wake spent while the window was still capped returned")
        print("    ok, and both builders then sat frozen for four more hours with quota in")
        print("    hand, because nothing re-fired and nothing checked.")

    unread = [b for b in crew if b["state"] == "unreadable"]
    if unread:
        print()
        print("    An `unreadable` row is not an idle one. The screen could not be read,")
        print("    so this briefing knows nothing about that agent; look at the terminal")
        print("    yourself before concluding anything about it.")

    clashes = contradictions(project)
    print()
    if clashes:
        print("  Sources disagree -- resolve these before dispatching anything")
        for line in clashes:
            print(f"    {line}")
        print()
        print("    Reported, not repaired. Which side is right is not derivable,")
        print("    and guessing turns a visible inconsistency into an invisible one.")
    else:
        print("  Sources agree: backlog, Orca and the gate tell the same story.")

    print()
    print("  Not recoverable")
    print("    The conversation. Anything decided but never written to the backlog,")
    print("    the glossary or an ADR is gone -- say so plainly rather than")
    print("    reconstructing a plausible version of it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
