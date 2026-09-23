#!/usr/bin/env python
"""Refuse a process kill by name, before it runs. Every agent, every role.

`taskkill //F //IM node.exe //T` kills every node.exe on the machine -- other
worktrees, other workers' dev servers, any node service beside them. It fires
silently in both directions: the session that runs it sees a clean exit, the one
that loses its server sees an unexplained failure elsewhere, and nothing ties the
two together. No script contains the command. Agents improvise it, fresh, as the
obvious way to stop a server they started -- so the fix cannot be made where the
command is written, because it is not written anywhere.

A rule in the contract only reaches an agent that read that paragraph. This
reaches every agent, including the ones that did not.

What counts as a kill by name, on either shell:

    taskkill ... /IM <image>          (or //IM, -IM)
    Stop-Process -Name / spps -Name / kill -Name
    Get-Process <name> | Stop-Process
    pkill / killall                   (both select by name or pattern)
    wmic process where name=... delete|terminate

Only at a command position -- start of a line, or after `;` `&` `|` `(` or `$(`
-- so a commit message or a grep that merely *mentions* the command passes.

**It fails open.** A hook that crashes, or cannot parse its input, lets the
command run. It exists to catch an improvisation, not to be a single point of
failure for every shell call on the machine.
"""

from __future__ import annotations

import json
import re
import sys

AT_COMMAND = r"(?:^|[;&|(\n]|\$\()\s*(?:sudo\s+)?"

PATTERNS = [
    rf"{AT_COMMAND}taskkill(?:\.exe)?\b[^\n;&|]*?\s[/-]{{1,2}}im\b",
    rf"{AT_COMMAND}(?:stop-process|spps|kill)\b[^\n;&|]*?\s-name\b",
    rf"{AT_COMMAND}(?:get-process|gps)\b[^\n;&|]*\|\s*(?:stop-process|spps|kill)\b",
    rf"{AT_COMMAND}(?:pkill|killall)\b",
    rf"{AT_COMMAND}wmic\b[^\n;&|]*\bname\s*=[^\n;&|]*\b(?:delete|terminate)\b",
]
KILL_BY_NAME = re.compile("|".join(PATTERNS), re.IGNORECASE)

REASON = """\
Refused: this kills processes by NAME, which takes every matching process on the
machine -- other worktrees, other workers' dev servers, any service beside them.

Kill by the pid you started, and only that:
    taskkill //F //T //PID <pid>        (Windows; //T takes its children)
    kill <pid>                          (POSIX)
If the project ships a scoped start/stop for its dev server, use that instead.
Don't know the pid? Find the one process that is yours -- by its port or its
command line -- and kill that pid. Contract section 11: stop a process by pid.
"""


def main() -> int:
    try:
        event = json.load(sys.stdin)
        command = (event.get("tool_input") or {}).get("command") or ""
    except (ValueError, AttributeError):
        return 0
    if not isinstance(command, str) or not KILL_BY_NAME.search(command):
        return 0
    # Exit 2 blocks the call; stderr is handed back to the agent as the reason.
    sys.stderr.write(REASON)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
