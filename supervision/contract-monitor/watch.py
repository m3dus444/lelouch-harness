#!/usr/bin/env python3
"""Stream the meaningful actions of a Lelouch run as they happen.

Claude Code appends every session to ~/.claude/projects/<slug>/<id>.jsonl, and
a dispatched worker gets its own slug under .../workspaces/<project>-<branch>.
So watching every slug whose name contains the project catches the orchestrator
AND its crew, without either of them reporting anything.

Emits one line per ACTION only - skills, dispatches, holds, tickets, gates. Not
prose: the conversation is the user's to have, and a per-message stream would
drown the signal. Failure signatures are in the filter too, because a run that
dies silently must not look identical to one still thinking.

    python watch.py weave-atlas
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"
POLL = 3.0


def emit(line: str) -> None:
    print(line, flush=True)


def interesting(row: dict) -> list[str]:
    """Actions worth a notification. Deliberately narrow."""
    if row.get("type") != "assistant":
        return []
    content = row.get("message", {}).get("content")
    if not isinstance(content, list):
        return []

    out = []
    for x in content:
        if not isinstance(x, dict) or x.get("type") != "tool_use":
            continue
        name = x.get("name", "?")
        inp = x.get("input", {}) or {}

        if name == "Skill":
            out.append(f"SKILL      {inp.get('skill', '?')}")
            continue
        if name != "Bash":
            continue

        cmd = " ".join(str(inp.get("command", "")).split())
        low = cmd.lower()

        # Skip commands that WRITE a file. Lelouch writes task specs that name
        # `worker-start` and `no-mistakes`, so matching tool names inside a
        # heredoc reports a dispatch that never happened - and a phantom
        # dispatch would have me wrongly accusing the approval gate.
        if re.search(r"(^|&&|\|\|,?|;)\s*(cat|tee)\s*>>?|<<\s*['\"]?\w*EOF", cmd):
            continue

        # A defect, not progress: the contract says call installed tools direct.
        if re.search(r"\bnpx\b.*\b(tasks-axi|gh-axi|lavish-axi)\b", low):
            out.append(f"!! npx     {cmd[:90]}")

        # Match the tool as an executed COMMAND - name followed by a real
        # subcommand - never as a substring of a path or a sentence.
        for pattern, label in (
            (r"orchestration\s+worker-start\s+--task", "DISPATCH  "),
            (r"orchestration\s+task-create\s+", "task-new  "),
            # `orchestration check` is deliberately absent: a compliant run
            # re-arms it constantly and silently (contract section 7), so
            # streaming it would drown everything in the noise the contract
            # exists to suppress. Verified from the transcript afterwards.
            (r"orchestration\s+send\s+", "mail      "),
            (r"(?<![\w/-])tasks-axi\s+hold\s+", "HOLD      "),
            (r"(?<![\w/-])tasks-axi\s+add\s+", "ticket+   "),
            (r"(?<![\w/-])tasks-axi\s+done\s+", "ticket-ok "),
            (r"(?<![\w/-])tasks-axi\s+unhold\s+", "released  "),
            (r"(?<![\w/-])lavish-axi\s+\S", "lavish    "),
            (r"(?<![\w/-])no-mistakes\s+(axi|init|doctor|run)\b", "ship-gate "),
            (r"worktree\s+set\s+--worktree", "board     "),
            (r"terminal\s+rename\s+--terminal", "board     "),
        ):
            if re.search(pattern, low):
                out.append(f"{label} {cmd[:90]}")
                break
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: watch.py <project-name>", file=sys.stderr)
        return 2
    needle = sys.argv[1].lower()

    offsets: dict[Path, int] = {}
    seen_dirs: set[str] = set()
    announced = False

    # Seed offsets at EOF: a restart mid-run must not replay history as if it
    # were live, which would bury the present under events already reported.
    if "--from-now" in sys.argv:
        for d in PROJECTS.iterdir():
            if d.is_dir() and needle in d.name.lower():
                for f in d.glob("*.jsonl"):
                    try: offsets[f] = f.stat().st_size
                    except OSError: pass
                seen_dirs.add(d.name)
        announced = True

    while True:
        try:
            dirs = [
                d for d in PROJECTS.iterdir()
                if d.is_dir() and needle in d.name.lower()
            ]
        except OSError:
            dirs = []

        if dirs and not announced:
            emit(f"-- {needle}: session started --")
            announced = True

        for d in dirs:
            if d.name not in seen_dirs:
                seen_dirs.add(d.name)
                # A new slug mid-run means a worker just got its own session.
                if announced and len(seen_dirs) > 1:
                    emit(f"-- new session: {d.name[-40:]} --")

            for f in d.glob("*.jsonl"):
                try:
                    size = f.stat().st_size
                except OSError:
                    continue
                start = offsets.get(f, 0)
                if size <= start:
                    offsets[f] = min(start, size)  # truncated/rotated
                    continue
                try:
                    with f.open("r", encoding="utf-8", errors="replace") as fh:
                        fh.seek(start)
                        chunk = fh.read()
                        offsets[f] = fh.tell()
                except OSError:
                    continue

                for line in chunk.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # a partial trailing write; next poll gets it
                    for ev in interesting(row):
                        emit(ev)

        time.sleep(POLL)


if __name__ == "__main__":
    raise SystemExit(main())
