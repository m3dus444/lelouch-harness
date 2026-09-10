# -*- coding: utf-8 -*-
"""Watch the ship gate's own state machine, which nothing else does.

`watch.py` streams the *actions* agents take. A gate failure is not an action --
it is a state inside `no-mistakes`, reported by a command that exits 0 while
saying `status: failed`. C.C found one that way, by reading a worker's prose,
and the monitor said nothing. This is the positive check that closes that.

**Reads `state.sqlite` directly, read-only.** The first version shelled out to
`no-mistakes axi status`, which spawns a Node process per poll per worktree.
That version was killed twice by the harness for low memory, with `node` sitting
at 14 processes and 1 GB -- the instrument was feeding the pressure that killed
it, and a monitor that dies quietly is worse than no monitor, because its
silence reads as calm. A sqlite read costs nothing and cannot be throttled.

Alarms on four things, and stays silent otherwise:

  * a run whose status becomes `failed`, with the error text the gate recorded
  * a step active longer than STALL_AFTER
  * a new run beginning on a branch whose previous run was still `running`,
    which is how a discarded traverse looks from outside
  * a run parked on `awaiting_agent`, which is invisible to the agent it waits
    for (F-047) and so has never once been noticed by the party responsible
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = Path.home() / ".no-mistakes" / "state.sqlite"
EVERY = 120.0
STALL_AFTER = 45 * 60
ACTIVE = ("running", "fixing", "pending_fix", "reviewing")


def emit(line: str) -> None:
    try:
        print(f"{time.strftime('%H:%M:%S')}  {line}", flush=True)
    except Exception:
        print(time.strftime("%H:%M:%S") + "  (unprintable)", flush=True)


def snapshot() -> dict[str, dict]:
    """Latest run per branch, with its active step. Read-only; never blocks the gate."""
    out: dict[str, dict] = {}
    try:
        cx = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True, timeout=10)
    except Exception as exc:
        emit(f"!! GATE DB unreadable: {str(exc)[:120]}")
        return out

    try:
        runs = cx.execute(
            "select id, branch, status, head_sha, error, awaiting_agent_since,"
            "       created_at, pr_url"
            "  from runs order by created_at desc limit 40").fetchall()

        for rid, branch, status, head, error, awaiting, created, pr in runs:
            if branch in out:          # newest run per branch wins
                continue
            step = cx.execute(
                "select step_name, status, findings_json, started_at,"
                "       last_activity, agent_pid"
                "  from step_results where run_id = ?"
                "   and status in ('running','fixing','pending_fix','reviewing')"
                " order by step_order desc limit 1", (rid,)).fetchone()
            out[branch] = {
                "run": rid, "status": status, "head": (head or "")[:8],
                "error": (error or "")[:200], "awaiting": awaiting,
                "created": created, "pr": pr or "",
                "step": step[0] if step else "",
                "step_status": step[1] if step else "",
                "findings": step[2] if step else "",
                "started": step[3] if step else 0,
                "activity": (step[4] or "")[:90] if step else "",
                "pid": step[5] if step else 0,
            }
    except Exception as exc:
        emit(f"!! GATE DB query failed: {str(exc)[:120]}")
    finally:
        cx.close()
    return out


def count(findings_json: str) -> str:
    try:
        data = json.loads(findings_json or "[]")
        return str(len(data)) if isinstance(data, list) else "?"
    except Exception:
        return "?"


def main() -> int:
    emit(f"gate watch (sqlite): every {EVERY/60:.0f}m, stall at {STALL_AFTER/60:.0f}m")
    seen: dict[str, dict] = {}
    said: set[str] = set()
    now = time.time

    while True:
        for branch, st in snapshot().items():
            prev = seen.get(branch)
            short = branch.split("/")[-1]

            if prev and prev["run"] != st["run"] and prev["status"] == "running":
                emit(f"!! RESTART  {short}: run {prev['run'][:8]} was still running "
                     f"when {st['run'][:8]} began -- a traverse was discarded at "
                     f"step {prev['step'] or '?'}.")
                said = {k for k in said if not k.startswith(short)}

            if st["status"] == "failed" and (not prev or prev["status"] != "failed"):
                emit(f"!! GATE FAILED  {short}: run {st['run'][:8]} at step "
                     f"{st['step'] or '?'}, head {st['head']}. "
                     f"{st['error'] or 'no error text recorded'}")

            if st["awaiting"] and f"{short}:await:{st['run']}" not in said:
                said.add(f"{short}:await:{st['run']}")
                mins = (now() - st["awaiting"]) / 60 if st["awaiting"] else 0
                emit(f"!! AWAITING AGENT  {short}: parked {mins:.0f}m. The agent it "
                     f"waits for cannot see this state (F-047).")

            key = f"{short}:slow:{st['run']}:{st['step']}"
            if st["started"] and st["step_status"] in ACTIVE:
                age = now() - st["started"]
                if age > STALL_AFTER and key not in said:
                    said.add(key)
                    emit(f"!! GATE SLOW  {short}: {st['step']} ({st['step_status']}) "
                         f"active {age/60:.0f}m, {count(st['findings'])} findings. "
                         f"Last: {st['activity']}")

            if prev and prev["step"] != st["step"] and st["step"]:
                emit(f"[{short}] step -> {st['step']} ({st['step_status']}), "
                     f"{count(st['findings'])} findings")

            if st["pr"] and (not prev or prev["pr"] != st["pr"]):
                emit(f"** PR  {short}: {st['pr']}")

            seen[branch] = st

        time.sleep(EVERY)


if __name__ == "__main__":
    raise SystemExit(main())
