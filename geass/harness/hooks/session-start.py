#!/usr/bin/env python3
"""SessionStart hook: inject current project state into a fresh session.

Deliberately ROLE-NEUTRAL. This hook fires for every agent that opens this
repo, and dispatched workers get a worktree of this same repo - so it reports
facts and points at the CLAUDE.md role gate rather than asserting an identity.
Telling a Build worker "you are Lelouch" would stop it doing its job.

Fails soft: a slow or broken tool degrades to a note, never a broken session.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

TIMEOUT = 20


def run(cmd: list[str]) -> tuple[bool, str]:
    # Resolve through PATH/PATHEXT ourselves: on Windows these are .cmd
    # shims, which shell=False cannot find by bare name (WinError 2). Keeping
    # shell=False avoids quoting surprises in the arguments.
    exe = shutil.which(cmd[0])
    if exe is None:
        return False, f"{cmd[0]} not found on PATH"
    try:
        proc = subprocess.run(
            [exe, *cmd[1:]], capture_output=True, text=True, timeout=TIMEOUT, shell=False
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {TIMEOUT}s"
    except (OSError, ValueError) as exc:
        return False, str(exc)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "no output").strip()[:200]
    return True, proc.stdout


def ready_queue() -> str:
    ok, out = run(["npx", "-y", "tasks-axi", "ready"])
    if not ok:
        return f"  (tasks-axi unavailable: {out})"
    keep = []
    for line in out.splitlines():
        stripped = line.strip()
        # Drop the CLI's own next-step hints and npm's cert warnings; keep state.
        if not stripped or stripped.startswith(("help[", "- Run", "Warning:")):
            continue
        keep.append("  " + stripped)
    return "\n".join(keep) if keep else "  (empty)"


def active_workers() -> str:
    ok, out = run(
        ["orca", "orchestration", "worker-list", "--terminal-state", "active", "--json"]
    )
    if not ok:
        return f"  (Orca unavailable: {out})"
    try:
        workers = json.loads(out).get("result", {}).get("workers", [])
    except (json.JSONDecodeError, AttributeError):
        return "  (could not parse Orca response)"
    if not workers:
        return "  none"
    lines = []
    for w in workers:
        dispatch = w.get("dispatch_id") or w.get("dispatchId") or "?"
        task = w.get("task_id") or w.get("taskId") or "?"
        state = w.get("state") or w.get("terminal_state") or "?"
        lines.append(f"  dispatch {dispatch} | task {task} | {state}")
    return "\n".join(lines)


def main() -> int:
    # Consume stdin so the hook never blocks on an unread pipe.
    try:
        sys.stdin.read()
    except Exception:
        pass

    context = "\n".join(
        [
            "## {{PROJECT}} — state at session start",
            "",
            "Read the **Role gate** at the top of CLAUDE.md before acting: it decides",
            "whether you are Lelouch (the orchestrator) or a dispatched Worker, and the",
            "two roles have opposite rules about writing project code.",
            "",
            "Ready to dispatch (tasks-axi, unblocked and unheld):",
            ready_queue(),
            "",
            "Active Orca workers:",
            active_workers(),
        ]
    )

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
