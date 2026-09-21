#!/usr/bin/env python
"""britania-afk -- work while nobody is watching, and report once they are.

    afk.py start [--autopilot]   nobody is at the keyboard from now
    afk.py decision "<line>"     something you decided on their behalf
    afk.py event "<line>"        something that happened
    afk.py ask "<question>"      a question asked into an empty room
    afk.py back                  render the digest, clear the marker
    afk.py status [--json]       is anyone away? (britania-vitals reads this)

**Silence is already the default.** The contract has the orchestrator say
nothing between dispatch and a real event, and surface exactly four things: a
question, an escalation, a worker_done, and a problem it cannot resolve. So AFK
does not make it quieter -- it changes what happens to those four. They are
recorded instead of interrupting, and in autopilot the ones that can be decided
are decided.

**`afk.log` is a buffer, not a record.** It holds exactly one window. `back`
renders it, and the next `start` retires it -- so a line written here has a
lifetime of one absence and no more. Anything that must OUTLIVE the window -- a
milestone, a decision that changes the plan, a question nobody has answered --
has to be written to its own durable home (the backlog, an ADR, a commit,
a tag) *at the same moment* it is recorded here. Run 3 lost a `MILESTONE
REACHED` and an unanswered `ask` this way; `start` now retires an old buffer
instead of deleting it, but a net is not a home.

**The digest is derived, then annotated.** State comes from the registries that
survive independently, the way `britania-restore` does it; the log only adds the
one thing no registry holds -- *why* something was done. If the log is missing or
half-written, the digest still works, which is the whole point of not trusting a
record written by a session that may have died mid-sentence.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE_DIR = ".lelouch"
MARKER = "afk.json"
LOG = "afk.log"

# Said by the tool, not only by the SKILL.md next to it: the one fact that has
# to be true in the operator's head at the moment they start recording.
BUFFER_NOTE = (
    "afk.log is a BUFFER, not a record: it lives one window, and `start` retires\n"
    "it. Anything that must outlive this absence -- a milestone, a decision that\n"
    "changes the plan -- write it to its durable home (backlog, an ADR, a\n"
    "commit, a tag) in the same breath as recording it here."
)


def state_dir(project: Path) -> Path:
    d = project / STATE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def sh(cmd: list[str], cwd: str | None = None, timeout: int = 120) -> str | None:
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


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_marker(project: Path) -> dict | None:
    f = project / STATE_DIR / MARKER
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# --------------------------------------------------------------------- modes


def retire_log(project: Path, previous: dict | None) -> tuple[Path | None, int, int]:
    """Move an old buffer aside instead of truncating it. (path, lines, asks)

    `start` used to open the log with "w" unconditionally, so every absence began
    by destroying the one before it. Run 3 did that three times in two days: a
    `/clear` or a restore ended a window with no `back`, and the next `start`
    took with it the digest nobody had read, once including an `ask` that was
    still open (F-067). A buffer is still the only copy until somebody reads it,
    and renaming a file costs nothing next to losing that.

    Any non-empty buffer is retired, not only one whose window never closed: the
    `MILESTONE REACHED` that went missing (F-081) was in a window that closed
    *cleanly*, and was erased by the next `start` regardless. `back` renders the
    digest to a terminal; it does not make the lines durable, and the scrollback
    it printed into may be gone.

    Named for the absence it holds -- the old marker's `since`, or failing that
    the first line's own timestamp -- so the file says which window it is.
    """
    entries = read_log(project)
    if not entries:
        return None, 0, 0
    asks = len([e for e in entries if e.get("kind") == "ask"])
    since = (previous or {}).get("since") or entries[0].get("at") or now()
    stamp = re.sub(r"[^0-9A-Za-z]", "", str(since)[:19]) or "unknown"
    d = state_dir(project)
    dest = d / f"afk-{stamp}.log"
    bump = 2
    while dest.exists():  # two starts inside one second, or a re-run
        dest = d / f"afk-{stamp}-{bump}.log"
        bump += 1
    try:
        (d / LOG).replace(dest)
    except OSError:
        # Could not move it: leave it exactly where it is. Refusing to start is
        # worse than a stale buffer, but destroying the buffer is worse than both.
        return None, len(entries), asks
    return dest, len(entries), asks


def start(project: Path, autopilot: bool) -> int:
    d = state_dir(project)
    # Read the OLD marker before writing the new one: its presence is the proof
    # that the previous window never closed, and it is about to be overwritten.
    previous = read_marker(project)
    kept, n, asks = retire_log(project, previous)

    marker = {"since": now(), "autopilot": autopilot}
    (d / MARKER).write_text(json.dumps(marker, indent=2), encoding="utf-8")
    if kept or not n:
        # A fresh absence, not a running tally -- but only once the old one is
        # safely aside. If the rename failed the old lines are still in there,
        # and truncating now would be the very deletion this guard exists to
        # prevent; a doubled buffer is the lesser fault, and it is announced.
        (d / LOG).write_text("", encoding="utf-8")

    if previous:
        print(f"!! the window opened {previous.get('since', '?')} NEVER CLOSED -- no digest")
        print("   was ever rendered for it, so nobody has read what it holds.")
    if kept:
        print(f"   {n} line(s) retired to {kept} rather than deleted.")
        if asks:
            print(f"   {asks} unanswered ask(s) in there -- asked into an empty room,")
            print("   never answered, and still open. Re-ask them.")
    elif n:
        print(f"   {n} line(s) could not be moved aside and are still in {LOG}"
              " -- read them before they are overwritten.")
    elif previous:
        print("   its buffer was empty; nothing was lost.")

    print(f"away since {marker['since']}"
          + ("   AUTOPILOT: decisions taken on your recommendation" if autopilot else ""))
    if not autopilot:
        print("Questions and escalations will be recorded and re-asked, not decided.")
    print("The vitals watcher will now act on a breach rather than only warn.")
    print(BUFFER_NOTE)
    return 0


def append(project: Path, kind: str, text: str) -> int:
    """One line per event. Append-only text, deliberately: a partially written
    line is still readable, where a partially written JSON document is not.

    Written to the BUFFER. It survives until the next `start`, and no longer --
    if this line must outlive the absence, write it somewhere durable too, now.
    """
    if not read_marker(project):
        print("not away -- nothing recorded", file=sys.stderr)
        return 1
    line = json.dumps({"at": now(), "kind": kind, "text": text}, ensure_ascii=False)
    with (state_dir(project) / LOG).open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return 0


def read_log(project: Path) -> list[dict]:
    f = project / STATE_DIR / LOG
    if not f.exists():
        return []
    out = []
    for raw in f.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            # A torn final line is expected if the session died mid-write.
            out.append({"at": "?", "kind": "note", "text": raw[:200]})
    return out


# ------------------------------------------------------------------- derived


def merged_since(project: Path, since: str) -> list[str]:
    out = sh(["git", "-C", str(project), "log", "--first-parent", "--merges",
              f"--since={since}", "--pretty=%h %s"]) or ""
    return [ln for ln in out.splitlines() if ln.strip()]


def landed_since(project: Path, since: str) -> list[str]:
    out = sh(["git", "-C", str(project), "log", f"--since={since}",
              "--no-merges", "--pretty=%h %s"]) or ""
    return [ln for ln in out.splitlines() if ln.strip()][:12]


def board(project: Path) -> str:
    script = HERE.parent / "britania-board" / "board.py"
    if not script.exists():
        return ""
    return (sh([sys.executable, str(script)], cwd=str(project), timeout=240) or "").rstrip()


def back(project: Path) -> int:
    marker = read_marker(project)
    if not marker:
        print("Nobody was away.")
        return 0

    since = marker.get("since", "")
    entries = read_log(project)
    pending = [e for e in entries if e["kind"] == "ask"]
    decided = [e for e in entries if e["kind"] == "decision"]
    events = [e for e in entries if e["kind"] not in ("ask", "decision")]

    gone = ""
    try:
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(since)
        secs = int(delta.total_seconds())
        gone = f"{secs // 3600}h{(secs % 3600) // 60:02d}m"
    except ValueError:
        gone = "?"

    print(f"WHILE YOU WERE AWAY -- {gone}"
          + ("   (autopilot)" if marker.get("autopilot") else ""))
    print()

    merged = merged_since(project, since)
    landed = landed_since(project, since)
    if merged:
        print(f"  Merged ({len(merged)})")
        for m in merged[:10]:
            print(f"    {m}")
        print()
    if landed:
        print(f"  Landed on this branch ({len(landed)})")
        for c in landed[:8]:
            print(f"    {c}")
        print()

    if decided:
        print(f"  Decisions taken for you ({len(decided)})")
        for e in decided:
            print(f"    {e['text']}")
        print()

    if events:
        print(f"  Also happened ({len(events)})")
        for e in events[:12]:
            print(f"    [{e['kind']}] {e['text']}")
        print()

    b = board(project)
    if b:
        print(b)
        print()

    if pending:
        print(f"  WAITING ON YOU ({len(pending)})  -- asked while you were gone")
        for e in pending:
            print(f"    {e['text']}")
        print()
        print("  Ask these again now, in your own words. They were asked into an")
        print("  empty room and never answered.")
    else:
        print("  Nothing is waiting on you.")

    print()
    print(BUFFER_NOTE)

    (project / STATE_DIR / MARKER).unlink(missing_ok=True)
    return 0


def status(project: Path, as_json: bool) -> int:
    marker = read_marker(project)
    if as_json:
        print(json.dumps(marker or {"since": None, "autopilot": False}))
        return 0 if marker else 1
    if not marker:
        print("present")
        return 1
    print(f"away since {marker['since']}"
          + ("  (autopilot)" if marker.get("autopilot") else ""))
    return 0


def main() -> int:
    # The kind IS the mode. It was a `--kind` flag, which meant an optional sat
    # between two positionals -- argparse then drops the trailing text and the
    # entry records nothing, silently. `afk.py decision "..."` also just reads
    # better than `afk.py log --kind decision "..."`.
    ap = argparse.ArgumentParser(
        description="Work unattended, report once.",
        epilog=BUFFER_NOTE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("mode", choices=["start", "decision", "event", "ask", "back", "status"])
    ap.add_argument("text", nargs="*", default=[])
    ap.add_argument("--autopilot", action="store_true",
                    help="decide on your own recommendation, and merge what qualifies")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--path", default=os.getcwd())
    args = ap.parse_args()
    project = Path(args.path).resolve()
    text = " ".join(args.text).strip()

    if args.mode == "start":
        return start(project, args.autopilot)
    if args.mode in ("decision", "event", "ask"):
        if not text:
            print(f"{args.mode} needs something to record", file=sys.stderr)
            return 2
        return append(project, args.mode, text)
    if args.mode == "back":
        return back(project)
    return status(project, args.json)


if __name__ == "__main__":
    sys.exit(main())
