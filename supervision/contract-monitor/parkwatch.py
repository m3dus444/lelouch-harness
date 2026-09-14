"""Per-session night watch for a parked ship gate.

Why this exists, and why watch.py does not cover it:

watch.py's silence alarm fires on "no watched ACTION in ANY weave-atlas session
for 15m". That is a global clock. On the night of 11 Sep two workers were live,
one parked at an ask-user gate finding and quiet, the other mid-gate and noisy.
The busy one holds the global alarm open indefinitely, so the parked one could
die and the alarm would never fire. See F-084 and instrument-log entry 16.

This watches ONE run and ONE session and reports state changes only.

It prints measurements, never verdicts (instrument-log entry 19). Every line is
data the reader judges.

An hourly ALIVE line is deliberate: this process can be reaped like any other
background task in this harness (instrument-log entry 15, F-084), and the
signature of that is silence. An hourly beat makes its own death detectable by
the absence of a line rather than leaving silence to mean two things.
"""

import datetime
import glob
import os
import sqlite3
import sys
import time

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else "01M26XMW2S14EB43JX8R39S6RV"
SESSION_TAG = sys.argv[2] if len(sys.argv) > 2 else "wa-entity-projection"
# The worker's Orca terminal handle. Heartbeat rows carry no session name --
# their payload is {taskId, dispatchId, phase} -- so from_handle is the only
# join back to a worker. Matching the session tag against payload returns zero
# rows and reads as "no heartbeat", which is a different claim entirely.
TERM_PREFIX = sys.argv[3] if len(sys.argv) > 3 else "term_aa99a3f0"
QUIET_LIMIT_MIN = 25
POLL_SEC = 60
ALIVE_EVERY_SEC = 3600

NM_DB = os.path.expanduser("~/.no-mistakes/state.sqlite")
ORCA_DB = os.path.expanduser("~/AppData/Roaming/Orca/orchestration.db")
PROJECTS = os.path.expanduser("~/.claude/projects")


def utcnow():
    return datetime.datetime.now(datetime.UTC)


def stamp():
    return utcnow().strftime("%H:%M:%SZ")


def gate_state():
    """(run_status, review_status, parked_minutes) or None if the run is gone."""
    con = sqlite3.connect("file:" + NM_DB + "?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT status, awaiting_agent_since FROM runs WHERE id=?", (RUN_ID,)
        ).fetchone()
        if row is None:
            return None
        step = con.execute(
            "SELECT status FROM step_results WHERE run_id=? AND step_name='review'",
            (RUN_ID,),
        ).fetchone()
        parked = None
        if row[1]:
            parked = int((time.time() - row[1]) // 60)
        return (row[0], step[0] if step else "?", parked)
    finally:
        con.close()


def transcript_quiet_min(tag=None):
    """Minutes since the named session last wrote a transcript row."""
    files = glob.glob(os.path.join(PROJECTS, "*%s*" % (tag or SESSION_TAG), "*.jsonl"))
    if not files:
        return None
    newest = max(os.path.getmtime(f) for f in files)
    return int((time.time() - newest) // 60)


def coordinator_quiet_min():
    """Minutes since the orchestrator's own project session wrote a row.

    Nothing else watches Lelouch. watch.py's alarm only fires when EVERY
    weave-atlas session goes quiet, so an orchestrator that dies while a worker
    keeps cycling is invisible -- and that is the failure that strands the run,
    because the worker is parked waiting for a ruling only the orchestrator can
    relay.

    Reported in the hourly beat rather than alarmed on: the coordinator legitimately
    holds hour-long waits, so an age here is context for the reader, not a
    threshold. The project directory carries retired sessions too, so this is
    the freshest row in it -- a floor on the coordinator's silence, not proof
    of which session wrote it.
    """
    return transcript_quiet_min("orca-projects-weave-atlas")


def last_heartbeat_min():
    con = sqlite3.connect("file:" + ORCA_DB + "?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT created_at FROM messages WHERE type='heartbeat' "
            "AND from_handle LIKE ? ORDER BY created_at DESC LIMIT 1",
            (TERM_PREFIX + "%",),
        ).fetchone()
        if row is None:
            return None
        when = datetime.datetime.fromisoformat(row[0]).replace(tzinfo=datetime.UTC)
        return int((utcnow() - when).total_seconds() // 60)
    finally:
        con.close()


def blocking_wait_pid():
    """PID of a live `orca … check … <terminal>` wait, or None.

    A parked worker holds its turn open inside a blocking mail wait. While it
    does, it writes no transcript rows and sends no heartbeats, so both clocks
    this watcher reads go stale on a worker that is perfectly healthy. The wait
    is a real OS process, so ask about it directly instead of inferring from two
    silences.

    Deliberately NOT used to suppress the alarm (F-044: a correct alarm talked
    down cost 2h20m). It is reported alongside, so the reader can tell "blocked
    in a live wait" from "gone" without taking a second measurement -- which is
    the standing complaint against every silence alarm in this log.

    Queried only when the alarm fires, not every poll: spawning a process per
    poll is exactly the footprint instrument-log entries 12-15 spent a night
    failing to pin a reaping on.
    """
    import subprocess

    ps = (
        "Get-CimInstance Win32_Process | ForEach-Object { $c=$_.CommandLine; "
        "if ($c -and $c -match '%s' -and $c -match 'check') "
        "{ '{0}|{1}' -f $_.ProcessId, $_.CreationDate.ToUniversalTime()"
        ".ToString('HH:mm:ss') } }" % TERM_PREFIX
    )
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except Exception as exc:
        return "query failed: %s" % type(exc).__name__
    hits = [ln.strip() for ln in out.splitlines()
            if ln.strip() and "orca" not in ln.lower()[:0]]
    hits = [h for h in hits if "|" in h]
    if not hits:
        return None
    pid, started = hits[0].split("|", 1)
    return "pid %s since %sZ" % (pid, started)


def main():
    print(
        "%s parkwatch armed  run=%s session=%s quiet_limit=%dm"
        % (stamp(), RUN_ID[:12], SESSION_TAG, QUIET_LIMIT_MIN),
        flush=True,
    )
    prev_gate = None
    was_quiet = False
    last_alive = time.time()

    while True:
        try:
            gate = gate_state()
            quiet = transcript_quiet_min()

            if gate is None:
                print(
                    "%s !! RUN GONE      run %s is no longer in state.sqlite"
                    % (stamp(), RUN_ID[:12]),
                    flush=True,
                )
                return

            if prev_gate is not None and gate[:2] != prev_gate[:2]:
                print(
                    "%s ** GATE MOVED    run=%s review=%s (was run=%s review=%s) "
                    "parked=%sm"
                    % (
                        stamp(),
                        gate[0],
                        gate[1],
                        prev_gate[0],
                        prev_gate[1],
                        gate[2],
                    ),
                    flush=True,
                )
            prev_gate = gate

            if quiet is not None:
                if quiet >= QUIET_LIMIT_MIN and not was_quiet:
                    print(
                        "%s !! SESSION QUIET %s wrote no transcript row for %dm. "
                        "Gate: run=%s review=%s parked=%sm. Last heartbeat %sm. "
                        "Blocking wait: %s. A parked worker heartbeats only when "
                        "it acts, so a stale heartbeat alone is not death -- the "
                        "transcript age is the measurement that moved. A live "
                        "blocking wait explains BOTH silences; no wait process "
                        "and two stale clocks is the combination to act on."
                        % (
                            stamp(),
                            SESSION_TAG,
                            quiet,
                            gate[0],
                            gate[1],
                            gate[2],
                            last_heartbeat_min(),
                            blocking_wait_pid() or "NONE FOUND",
                        ),
                        flush=True,
                    )
                    was_quiet = True
                elif quiet < QUIET_LIMIT_MIN and was_quiet:
                    print(
                        "%s ** SESSION BACK  %s wrote a row; quiet was cleared at %dm"
                        % (stamp(), SESSION_TAG, quiet),
                        flush=True,
                    )
                    was_quiet = False

            if time.time() - last_alive >= ALIVE_EVERY_SEC:
                print(
                    "%s .. ALIVE         run=%s review=%s parked=%sm "
                    "worker_quiet=%sm coordinator_quiet=%sm"
                    % (
                        stamp(),
                        gate[0],
                        gate[1],
                        gate[2],
                        quiet,
                        coordinator_quiet_min(),
                    ),
                    flush=True,
                )
                last_alive = time.time()

        except Exception as exc:  # never die silently
            print(
                "%s !! PARKWATCH ERROR %s: %s" % (stamp(), type(exc).__name__, exc),
                flush=True,
            )

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
