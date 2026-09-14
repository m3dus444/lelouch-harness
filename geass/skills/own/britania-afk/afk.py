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
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE_DIR = ".lelouch"
MARKER = "afk.json"
LOG = "afk.log"


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


def start(project: Path, autopilot: bool) -> int:
    d = state_dir(project)
    marker = {"since": now(), "autopilot": autopilot}
    (d / MARKER).write_text(json.dumps(marker, indent=2), encoding="utf-8")
    (d / LOG).write_text("", encoding="utf-8")  # a fresh absence, not a running tally

    print(f"away since {marker['since']}"
          + ("   AUTOPILOT: decisions taken on your recommendation" if autopilot else ""))
    if not autopilot:
        print("Questions and escalations will be recorded and re-asked, not decided.")
    print("The vitals watcher will now act on a breach rather than only warn.")
    return 0


def append(project: Path, kind: str, text: str) -> int:
    """One line per event. Append-only text, deliberately: a partially written
    line is still readable, where a partially written JSON document is not."""
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
    ap = argparse.ArgumentParser(description="Work unattended, report once.")
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
