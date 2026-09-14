#!/usr/bin/env python
"""britania-board -- one table answering "what is actually happening right now".

Joins the three registries that each hold a third of the answer:

    tasks-axi      what work exists, and what is blocked on what
    orca           which worker holds which ticket, and is it alive
    state.sqlite   where that worker's branch is in the ship gate

None of them knows the other two. A ticket id alone does not say whether its
worker is building, waiting on review, or dead -- which is the whole reason this
exists.

Read-only throughout. It opens the gate's database with `mode=ro` and shells out
to the two CLIs for the rest; it never writes anything anywhere.

**Why Python and not shell.** Measured on this machine: the interpreter costs
~270ms against bash's ~180ms, while the script's own run is 3.7-5.0s -- so the
choice is roughly 3% of runtime, and shell would call the identical Node
binaries for the rest of it. What actually decides it is that **the `sqlite3`
CLI is not installed here**, so shell cannot read the gate database at all,
while Python's `sqlite3` is stdlib. Quoted-CSV parsing in awk is the second
reason. A future script that is pure CLI calls with no parsing and no database
would be fine in shell.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import shutil
import subprocess
import sys
import time
from pathlib import Path

GATE_DB = Path(os.path.expanduser("~/.no-mistakes/state.sqlite"))

# The gate's nine steps, in the order it runs them. Anything not in this list is
# printed as-is rather than dropped -- a new step should be visible immediately,
# not silently missing.
STEPS = ["intent", "rebase", "review", "test", "document", "lint", "push", "pr", "ci"]


def sh(cmd: list[str], timeout: int = 30) -> str | None:
    """Run a command, return stdout, or None if it failed in any way.

    **Resolve the executable first.** On Windows these CLIs are installed as
    `.CMD` shims, and `subprocess` will not execute one by bare name -- it
    raises `FileNotFoundError` even though the command works perfectly in a
    shell. `shutil.which` finds the shim; without this every source silently
    returns nothing and the board reports an empty project.
    """
    exe = shutil.which(cmd[0])
    if exe is None:
        return None
    try:
        p = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout if p.returncode == 0 else None


def orca_json(cmd: list[str]):
    """Orca wraps every payload as {id, ok, result: {...}} -- unwrap to result."""
    out = sh(cmd)
    if not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        if data.get("ok") is False:
            return None
        return data.get("result", data)
    return data


def toon(text: str) -> list[dict]:
    """Parse the -axi CLIs' TOON output.

        tasks[41]{id,state,kind,repo,title}:
          wa-ship-both,queued,captain,"-","Decide after the bake-off: ..."

    Header names the columns; rows are indented and CSV-quoted. Anything that is
    not a header-plus-rows block is ignored rather than guessed at.

    `tasks-axi` does have a `--json` flag, but it is scoped to **mutations** --
    it returns a machine-readable result for `add`, `done`, `hold` and friends.
    Reads like `list` and `show` emit TOON, so a reader parses TOON.
    """
    rows: list[dict] = []
    cols: list[str] | None = None
    for raw in (text or "").splitlines():
        head = re.match(r"^\w+\[\d+\]\{([^}]*)\}:\s*$", raw.strip())
        if head:
            cols = [c.strip() for c in head.group(1).split(",")]
            continue
        if cols is None or not raw.startswith(("  ", "\t")):
            continue
        try:
            values = next(csv.reader([raw.strip()]))
        except (csv.Error, StopIteration):
            continue
        # A short row is not a row. These CLIs append indented help lines after
        # the block ("- Run `tasks-axi show <id>` for full details"), and padding
        # them out turns advice into a ticket.
        if len(values) < len(cols):
            continue
        rows.append(dict(zip(cols, values)))
    return rows


def tasks_axi(state: str, fields: str = "") -> list[dict]:
    cmd = ["tasks-axi", "list", "--state", state]
    if fields:
        cmd += ["--fields", fields]
    return toon(sh(cmd) or "")


def age(ts) -> str:
    """Human age of a unix timestamp. Staleness is the point, so never hide it."""
    if not ts:
        return "-"
    try:
        secs = int(time.time() - float(ts))
    except (TypeError, ValueError):
        return "-"
    if secs < 0:
        return "0m"
    if secs < 3600:
        return f"{secs // 60}m"
    if secs < 86400:
        return f"{secs // 3600}h{(secs % 3600) // 60:02d}"
    return f"{secs // 86400}d"


# ------------------------------------------------------------------ the gate


def gate_rows() -> dict[str, dict]:
    """Latest gate run per branch, with the step it is actually sitting on.

    Schema, documented here so nobody has to rediscover it (the supported
    `axi` view truncates, which is why agents keep ending up in this file):

        runs          id, branch, status, pr_url, pr_state, pr_state_observed_at,
                      awaiting_agent_since, error, created_at, worktree_dir
        step_results  run_id, step_name, step_order, status, last_activity_at
        step_rounds   step_result_id, round

        run status    completed | failed | cancelled | ci_monitor_interrupted
        step status   completed | failed | pending    | skipped

    `pr_state_observed_at` is a CACHED observation, not a live read. Its age is
    the only thing separating a monitor that is watching from one that stopped
    hours ago, so it is always displayed.
    """
    if not GATE_DB.exists():
        return {}
    try:
        con = sqlite3.connect(f"file:{GATE_DB.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}

    out: dict[str, dict] = {}
    try:
        runs = con.execute(
            "select id, branch, status, pr_url, pr_state, pr_state_observed_at,"
            "       awaiting_agent_since, error"
            "  from runs order by created_at desc"
        ).fetchall()
        for rid, branch, status, pr_url, pr_state, observed, awaiting, error in runs:
            key = (branch or "").rsplit("/", 1)[-1]
            if key in out:
                continue  # newest run per branch wins
            steps = con.execute(
                "select step_name, status, last_activity_at"
                "  from step_results where run_id = ? order by step_order",
                (rid,),
            ).fetchall()
            done = [s for s, st, _ in steps if st == "completed"]
            live = next((s for s, st, _ in steps if st not in ("completed", "skipped")), None)
            failed = next((s for s, st, _ in steps if st == "failed"), None)
            last_act = max((a for _, _, a in steps if a), default=None)
            out[key] = {
                "run_status": status,
                "stage": failed or live or "done",
                "progress": f"{len(done)}/{len(steps) or len(STEPS)}",
                "pr": (pr_url or "").rsplit("/", 1)[-1],
                "pr_state": pr_state,
                "pr_age": age(observed),
                "awaiting": awaiting,
                "error": (error or "").strip().splitlines()[0] if error else None,
                "last_act": age(last_act),
            }
    except sqlite3.Error:
        return {}
    finally:
        con.close()
    return out


# --------------------------------------------------------------- the backlog


def backlog() -> tuple[list[dict], list[dict], list[dict]]:
    """(in flight, queued, held). `held` rows still report state `queued`, so
    holds must be fetched separately or they look like ordinary queued work."""
    flight = tasks_axi("in_flight")
    queued = tasks_axi("queued", "blocked_by")
    held = tasks_axi("held", "hold_reason,hold_until")
    held_ids = {h.get("id") for h in held}
    queued = [q for q in queued if q.get("id") not in held_ids]
    return flight, queued, held


# --------------------------------------------------------------- the workers


def workers(run_id: str | None) -> dict[str, dict]:
    """Real worker state, keyed by the ticket id its task names.

    Two calls, because neither alone answers it:

        worker-list   workerState / terminalState, keyed by taskId
        task-list     the ticket id, which only ever appears in the task text

    `worker-list` carries the state that matters and no ticket id at all --
    its keys are `dispatchId, taskId, runId, workerState, dispatchStatus,
    agentTerminalHandle, terminalState`. So the join is on `taskId`, and the
    ticket id is still recovered from the task's own text.
    """
    if not run_id:
        runs = (orca_json(["orca", "orchestration", "run-list", "--json"]) or {}).get("runs") or []
        run_id = runs[0].get("id") if runs else None
    if not run_id:
        return {}

    by_task: dict[str, dict] = {}
    wl = orca_json(["orca", "orchestration", "worker-list", "--run", run_id, "--json"]) or {}
    for w in wl.get("workers") or []:
        if isinstance(w, dict) and w.get("taskId"):
            by_task[w["taskId"]] = w

    data = orca_json(["orca", "orchestration", "task-list", "--run", run_id, "--json"]) or {}
    out: dict[str, dict] = {}
    for t in data.get("tasks") or data.get("items") or []:
        if not isinstance(t, dict):
            continue
        blob = " ".join(
            str(t.get(k) or "") for k in ("title", "displayName", "spec", "objective", "name")
        )
        key = next((m for m in re.findall(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+)+\b", blob)), None)
        if not key:
            continue
        w = by_task.get(t.get("id"), {})
        out.setdefault(key, {
            # Prefer the worker's own state over the task's: a task reads
            # completed while its terminal is still retained and holding a slot.
            "state": w.get("workerState") or t.get("status") or t.get("state"),
            "terminal": w.get("terminalState"),
            "task": t.get("id"),
        })
    return out


# ------------------------------------------------------------------- render


def table(rows: list[list[str]], head: list[str]) -> str:
    cols = len(head)
    width = [max(len(str(r[i])) for r in [head] + rows) for i in range(cols)]
    line = "  ".join("-" * w for w in width)
    body = ["  ".join(str(r[i]).ljust(width[i]) for i in range(cols)) for r in rows]
    return "\n".join(["  ".join(head[i].ljust(width[i]) for i in range(cols)), line, *body])


def main() -> int:
    ap = argparse.ArgumentParser(description="Project state: tickets, workers, gate stages.")
    ap.add_argument("--run", help="Orca run id, if you have it")
    ap.add_argument("--all", action="store_true", help="include done and queued, not just live")
    args = ap.parse_args()

    gate = gate_rows()
    crew = workers(args.run)
    flight, queued, held = backlog()

    # A task or run in a terminal state is history, not work in flight. Orca's
    # task-list returns every task the Run ever had, so without this the board
    # reports a finished project as fully busy.
    # Orca's own vocabulary, read from the runtime rather than guessed:
    #   workerState     succeeded | failed | abandoned   (and running, while live)
    #   terminalState   retained  | released | reclaimable
    # A settled worker can still hold a `retained` terminal, which is a slot the
    # machine cannot reuse -- that is worth seeing, but it is not work in flight.
    DEAD_WORKER = {"succeeded", "failed", "abandoned", "cancelled"}
    DEAD_RUN = {"completed", "cancelled", "failed", "ci_monitor_interrupted"}

    def row(tid: str) -> list[str]:
        g, w = gate.get(tid, {}), crew.get(tid, {})
        return [
            tid[:30],
            (w.get("state") or "-")[:9],
            (g.get("stage") or "-")[:9],
            g.get("progress", "-"),
            g.get("pr") or "-",
            f"{g['pr_state']} ({g['pr_age']})" if g.get("pr_state") else "-",
            g.get("last_act", "-"),
        ]

    live_ids = {t["id"] for t in flight if t.get("id")}
    live_ids |= {k for k, w in crew.items() if (w.get("state") or "") not in DEAD_WORKER}
    live_ids |= {k for k, g in gate.items() if (g.get("run_status") or "") not in DEAD_RUN}

    # Finished, but not cleanly. These are the ones that quietly cost something:
    # a run that cannot close, a failed step nobody looked at, a PR left open.
    attention = {
        k for k, g in gate.items()
        if k not in live_ids and (
            g.get("run_status") in {"failed", "cancelled", "ci_monitor_interrupted"}
            or (g.get("pr_state") == "open" and g.get("stage") == "done")
        )
    }

    head = ["ticket", "worker", "gate", "steps", "pr", "pr state (age)", "last act"]
    chunks: list[str] = []
    chunks.append(
        "IN FLIGHT\n" + table([row(t) for t in sorted(live_ids)], head)
        if live_ids else "IN FLIGHT\n  nothing running"
    )

    if attention:
        chunks.append(
            "NEEDS ATTENTION -- finished, but not cleanly\n"
            + table([row(t) + [gate[t].get("run_status") or "-"] for t in sorted(attention)], head + ["run"])
        )

    if held:
        chunks.append("HELD -- waiting on a decision\n" + table(
            [[h.get("id", "")[:30], (h.get("hold_until") or "-")[:10],
              " ".join((h.get("hold_reason") or "").split())[:88]] for h in held],
            ["ticket", "until", "what would lift it"],
        ))

    if queued:
        shown = queued if args.all else queued[:10]
        chunks.append("NEXT UP\n" + table(
            [[q.get("id", "")[:30], (q.get("blocked_by") or "-")[:24],
              " ".join((q.get("title") or "").split())[:70]] for q in shown],
            ["ticket", "blocked by", "title"],
        ) + ("" if args.all or len(queued) <= 10 else f"\n  ... and {len(queued) - 10} more (--all)"))

    shown_rows = [row(t) for t in sorted(live_ids | attention)]
    if any(r[5] != "-" and ("h" in r[5] or "d" in r[5]) for r in shown_rows):
        chunks.append(
            "NOTE\n  A PR state older than an hour is a cached read, not a live one.\n"
            "  The monitor that wrote it may have stopped; check GitHub before acting on it."
        )

    if not gate and not crew and not (flight or queued or held):
        print("No board: tasks-axi, orca and the gate database all returned nothing.", file=sys.stderr)
        return 1

    print("\n\n".join(chunks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
