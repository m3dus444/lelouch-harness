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


# Windows stdout defaults to cp1252 here. On 8 Sep a worker command carrying
# one character outside it raised UnicodeEncodeError inside print() and killed
# the entire watch mid-run - the supervisor went blind at the exact moment the
# workers came back. Ask for UTF-8, and never trust that the ask succeeded.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def emit(line: str) -> None:
    """Print, or degrade the line - but never raise. A monitor that dies on a
    print is indistinguishable from a quiet run, which is the one thing this
    tool must never be."""
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(line.encode(enc, "replace").decode(enc, "replace"), flush=True)


def interesting(row: dict) -> list[str]:
    """Actions worth a notification. Deliberately narrow."""
    content = (row.get("message") or {}).get("content")

    # A refusal arrives one row after the call, on a user-role row. Without this
    # a blocked skill streams as if it ran -- and in run 2 that sent the
    # supervisor to report that intake had started when it had just died.
    #
    # The skill that caused it (`grill-with-docs`) is gone from the v2 payload,
    # but the mechanism is not: every user-only skill still refuses this way,
    # and v2 ships four of them (britania-afk, -resume, -restore, and brief).
    if row.get("type") == "user" and isinstance(content, list):
        out = []
        for x in content:
            if not isinstance(x, dict) or x.get("type") != "tool_result":
                continue
            body = str(x.get("content", ""))
            if x.get("is_error") or "<tool_use_error>" in body:
                # A non-zero exit is not a refusal. Tonight alone this label was
                # worn by `bc: command not found`, a bash quoting error, a curl
                # TLS failure, and `diff` exiting 1 because files differ - which
                # is diff working. The 127 case made me report a successful
                # DuckDB trial to C.C as a failure. Keep both loud, stop lying
                # about which is which.
                low = body.lower()
                # Match SIGNATURES, not words. The first version keyed on bare
                # "permission" and duly flagged a GitHub Actions workflow as a
                # refusal, because its YAML contains `permissions: contents:
                # read`. A refusal has a specific sentence; a workflow merely has
                # a noun.
                deny = any(k in low for k in (
                    "permission for this action was denied",
                    "requested permissions to use",
                    "blocked by classifier",
                    "requires approval",
                    "user rejected",
                    "disable-model-invocation",
                    "you have not granted it yet",
                ))
                mark = "!! REFUSED " if deny else "!! nonzero "
                out.append(f"{mark} {' '.join(body.split())[:300]}")
        return out

    if row.get("type") != "assistant" or not isinstance(content, list):
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
        # The approval gate, caught in the act. Everything else here infers
        # the gate from what did or did not follow it.
        if name == "AskUserQuestion":
            qs = inp.get("questions") or []
            q = qs[0].get("question", "") if qs and isinstance(qs[0], dict) else ""
            out.append(f"** ASK-CC  {' '.join(str(q).split())[:120]}")
            continue
        if name != "Bash":
            continue

        cmd = " ".join(str(inp.get("command", "")).split())
        low = cmd.lower()

        # Reading the manual is not doing the thing. `tasks-axi add --help`
        # streamed as `ticket+`, which would have put a ticket on the board
        # before the approval gate that must precede it.
        if re.search(r"(--help|-h)\b", low) or low.endswith("--help"):
            continue

        # Skip commands that WRITE a file. Lelouch writes task specs that name
        # `worker-start` and `no-mistakes`, so matching tool names inside a
        # heredoc reports a dispatch that never happened - and a phantom
        # dispatch would have me wrongly accusing the approval gate.
        if re.search(r"(^|&&|\|\|,?|;)\s*(cat|tee)\s*>>?|<<\s*['\"]?\w*EOF", cmd):
            continue

        # The contract says call installed tools directly. Measured on this
        # machine: direct ~1.2s, `npx --no-install` ~4s, `npx -y` worse and
        # unbounded when the registry is cold. Only the fetching form earns a
        # `!!` -- `--no-install` cannot fetch, so it is a slow habit, not a
        # defect, and flagging both alike just teaches me to ignore the marker.
        if re.search(r"\bnpx\b.*\b(tasks-axi|gh-axi|lavish-axi)\b", low):
            mark = "slow-npx  " if "--no-install" in low else "!! npx    "
            out.append(f"{mark} {cmd[:150]}")

        # Match the tool as an executed COMMAND - name followed by a real
        # subcommand - never as a substring of a path or a sentence.
        for pattern, label in (
            (r"orchestration\s+worker-start\b", "DISPATCH  "),
            (r"orchestration\s+task-create\s+", "task-new  "),
            # `orchestration check` is deliberately absent: a compliant run
            # re-arms it constantly and silently (contract section 7), so
            # streaming it would drown everything in the noise the contract
            # exists to suppress. Verified from the transcript afterwards.
            # Typed sends first, and by type: a worker chains
            # `worktree set && orchestration send --type worker_done` in one
            # command, and a generic "mail" label truncated at 90 chars buried
            # the single event the whole run exists to produce.
            (r"orchestration\s+send\s+.*--type\s+worker_done", "** DONE   "),
            (r"orchestration\s+send\s+.*--type\s+(escalation|question)", "** ASKS   "),
            # Board updates carry real progress ("master merged, 192 tests
            # green") and workers chain them with a heartbeat in one command.
            # First match wins, so with `hb` listed first the whole line was
            # labelled a heartbeat - and heartbeats are rate-limited. A chained
            # board update was therefore suppressible. Match the action first;
            # a bare heartbeat still falls through to `hb` below.
            (r"worktree\s+set\s+--worktree", "board     "),
            (r"terminal\s+rename\s+--terminal", "board     "),
            (r"orchestration\s+send\s+.*--type\s+heartbeat", "hb        "),
            (r"orchestration\s+send\s+", "mail      "),
            (r"(?<![\w/-])tasks-axi\s+hold\s+", "HOLD      "),
            (r"(?<![\w/-])tasks-axi\s+add\s+", "ticket+   "),
            (r"(?<![\w/-])tasks-axi\s+done\s+", "ticket-ok "),
            (r"(?<![\w/-])tasks-axi\s+unhold\s+", "released  "),
            (r"(?<![\w/-])lavish-axi\s+\S", "lavish    "),
            # `axi status` and `axi sync` are reads; only `run` ships.
            # Labelling both `ship-gate` made a status poll read as a gate
            # firing on a branch nobody had authorised shipping.
            # `sync --recover` RESTORES a dead run's banked commits onto the
            # branch - it is the move that turned wa-02-cache from "never cleared
            # review" into a merged PR. It is a mutation wearing a read's name, and
            # the noise throttle would happily suppress it. Match it first.
            (r"(?<![\w/-])no-mistakes\s+axi\s+sync\s+.*--(recover|apply)", "** SYNC   "),
            (r"(?<![\w/-])no-mistakes\s+axi\s+(status|sync|doctor)\b", "gate-read "),
            (r"(?<![\w/-])no-mistakes\s+(axi|init|doctor|run)\b", "ship-gate "),
            # Waking a dead worker in place is a dispatch in everything but
            # name - same task, same dispatch capability, same session file.
            # The 8 Sep restart woke three workers through this path and the
            # stream showed nothing at all. Silence here is the worst failure
            # this tool can have: it is the moment work resumes.
            (r"terminal\s+send\s+.*--interrupt", "** WAKE   "),
            (r"terminal\s+send\s+.*--text", "** SEND   "),
        ):
            if re.search(pattern, low):
                out.append(f"{label} {cmd[:150]}")
                break
    return out


def newest_gate_write() -> float:
    """Latest write by any no-mistakes pipeline agent, as an epoch time.

    A worker blocked inside a long `axi run` writes nothing at all - no tool
    call, no heartbeat - so its own transcript is indistinguishable from a dead
    one. The gate agent doing the work writes its own transcript under a
    `…worktrees-<hash>-<RUNID>` slug, and that keeps growing throughout. Checking
    it is the difference between "silent" and "dead", and it costs one stat pass
    only when we are already about to cry wolf.
    """
    newest = 0.0
    try:
        for d in PROJECTS.iterdir():
            if not (d.is_dir() and "worktrees-" in d.name.lower()):
                continue
            for f in d.glob("*.jsonl"):
                try:
                    newest = max(newest, f.stat().st_mtime)
                except OSError:
                    pass
    except OSError:
        pass
    return newest


def last_rows(needle: str) -> str:
    """Per-session age of the LAST TRANSCRIPT ROW, for the silence alarm to carry.

    On 9 Sep the alarm fired correctly and the supervisor then checked liveness
    with file mtime, read a reassuring 8.6 minutes, and stood down. The stall ran
    2h20m. mtime is touched by flushes and rotation; it is not activity. The fix
    is not a better alarm - it is that the alarm should arrive with the evidence
    already attached, so there is no second, sloppier measurement to make.
    """
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)
    out = []
    try:
        dirs = [d for d in PROJECTS.iterdir()
                if d.is_dir() and (needle in d.name.lower() or "worktrees-" in d.name.lower())]
    except OSError:
        return ""
    for d in dirs:
        low = d.name.lower()
        tag = (low.split(needle + "-")[-1] if "workspaces" in low
               else "gate" if "worktrees-" in low else "lelouch")
        for f in d.glob("*.jsonl"):
            last = None
            try:
                for line in f.open(encoding="utf-8", errors="replace"):
                    if '"timestamp"' not in line:
                        continue
                    try:
                        t = json.loads(line).get("timestamp")
                    except json.JSONDecodeError:
                        continue
                    if t:
                        last = t
            except OSError:
                continue
            if not last:
                continue
            try:
                ts = _dt.datetime.fromisoformat(str(last).replace("Z", "+00:00"))
            except ValueError:
                continue
            # Clamp: the scan of every jsonl takes seconds, and a session
            # that writes a row mid-scan reads as negative. A negative age
            # in an alarm whose whole job is trustworthy ages is worse than
            # the rounding it comes from.
            age = max((now - ts).total_seconds() / 60, 0.0)
            if age < 240:
                out.append((age, tag))
    if not out:
        return ""
    out.sort()
    return "; ".join(f"{tag} {age:.0f}m" for age, tag in out[:8])


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

    # Heartbeats and gate-status polls are liveness, not events. Measured
    # 8 Sep: a worker polling every 29s drove 241 supervisor turns at ~171k
    # cache-read each - 23% of the whole run's token spend, for lines that
    # produced no finding all session. The same poll loop was billed twice,
    # once in the worker and once in the supervisor it woke. Keep them, so
    # silence still means something, but at a tenth of the rate.
    noise_last: dict[tuple[str, str], float] = {}
    NOISE_EVERY = 600.0

    # Presence signals cannot detect their own cessation. On 8 Sep the whole
    # run stopped at 00:04 and this tool said nothing for three hours, because
    # "no events" is exactly what a healthy quiet run looks like. Heartbeats
    # were never the liveness signal - their ABSENCE is. Fire once per silent
    # episode, then re-arm when the run comes back.
    SILENCE_AFTER = 900.0
    last_data = time.time()
    silence_reported = False

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
            low = d.name.lower()
            tag = low.split(needle + "-")[-1] if "workspaces" in low else "lelouch"
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
                    last_data = time.time()
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
                        kind = ev.split()[0] if ev.split() else ""
                        if kind in ("hb", "gate-read"):
                            seen = noise_last.get((tag, kind), 0.0)
                            if time.time() - seen < NOISE_EVERY:
                                continue
                            noise_last[(tag, kind)] = time.time()
                        # Re-arm the silence alarm only on a REAL event. Re-arming
                        # on any byte written meant a finished-but-idle run alarmed
                        # every 15 minutes forever - the alarm became the noise it
                        # was built to replace. Told you once; tell you again only
                        # after something actually happened.
                        silence_reported = False
                        emit(f"[{tag}] {ev}")

        quiet = time.time() - last_data
        if quiet > SILENCE_AFTER and not silence_reported:
            # Before crying wolf: a worker can be blocked in a 38-minute gate
            # call, writing nothing while the gate agent works. That is silent,
            # not dead. Verified 8 Sep on wa-03-budget's nine-minute gap.
            gate = newest_gate_write()
            if gate and time.time() - gate < SILENCE_AFTER:
                last_data = gate
                quiet = 0.0
        if quiet > SILENCE_AFTER and not silence_reported:
            detail = last_rows(needle)
            # `quiet` is time since the last WATCHED ACTION, not since the
            # last row. A session can write prose and thinking for 15m
            # without emitting one action this watcher reports. Saying "no
            # activity" over a row age of 0m makes the alarm contradict the
            # evidence it carries, and the standing rule ("over 15m is
            # stalled") then points at a session that is plainly alive.
            # Do NOT suppress on a fresh row: on 9 Sep an alarm was talked
            # down and the stall ran 2h20m. Name the two measurements apart
            # and let the reader apply the rule to the right one.
            emit(f"!! SILENT   no watched ACTION in any {needle} session for "
                 f"{quiet/60:.0f}m. Last ROW per session (not mtime): "
                 f"{detail or 'none in 4h'}. A row age over 15m is stalled; a "
                 f"fresh row with no action is thinking or prose, not health. "
                 f"Do not re-check with mtime.")
            silence_reported = True
        time.sleep(POLL)


if __name__ == "__main__":
    raise SystemExit(main())
