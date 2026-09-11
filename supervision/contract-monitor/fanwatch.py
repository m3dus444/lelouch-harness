"""Memory and liveness watch for a fan-out.

Why: F-032 says fan-out is bounded by RAM, not tokens. Instrument-log entry 15
says background tasks here are killed with a low-memory message at times that
correlate with nothing measurable — so free RAM is NOT a predictor, and this
watcher does not pretend otherwise. It reports the number alongside the thing
that actually matters (did a worker stop writing), and lets the reader join them.

watch.py's silence alarm is global: it fires only when EVERY weave-atlas session
goes quiet, so one busy worker masks two dead ones. That is precisely the wrong
shape for a fan-out, which is why this exists.

Prints measurements, never verdicts (instrument-log entry 19). The hourly ALIVE
line makes this process's own death visible as a missing line rather than as
silence (entry 15, F-084).
"""

import datetime
import glob
import os
import subprocess
import sys
import time

TAGS = sys.argv[1].split(",") if len(sys.argv) > 1 else [
    "wa-04a-compile-papers",
    "wa-04b-compile-authors",
    "wa-04c-compile-inst-topics",
]
QUIET_LIMIT_MIN = 20
FREE_GB_FLOOR = 2.0
POLL_SEC = 60
ALIVE_EVERY_SEC = 3600

PROJECTS = os.path.expanduser("~/.claude/projects")

PS_MEM = (
    "$o=Get-CimInstance Win32_OperatingSystem;"
    "'{0:N2}|{1:N0}' -f ($o.FreePhysicalMemory/1MB),"
    "(100*($o.TotalVirtualMemorySize-$o.FreeVirtualMemory)/$o.TotalVirtualMemorySize)"
)


def stamp():
    return datetime.datetime.now(datetime.UTC).strftime("%H:%M:%SZ")


def memory():
    """(free_gb, commit_pct) or (None, None). Locale writes a decimal comma."""
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", PS_MEM],
            capture_output=True, text=True, timeout=25,
        ).stdout.strip()
        free, commit = out.split("|")
        # A French locale renders 3.09 as "3,09"; comparing that as a float
        # silently fails. Instrument-log entry 8 was exactly this bug.
        return float(free.replace(",", ".").replace("\xa0", "")), int(commit)
    except Exception:
        return None, None


def quiet_min(tag):
    files = glob.glob(os.path.join(PROJECTS, "*%s*" % tag, "*.jsonl"))
    if not files:
        return None
    return int((time.time() - max(os.path.getmtime(f) for f in files)) // 60)


def main():
    print("%s fanwatch armed  tags=%s  quiet>%dm  free<%.1fGB"
          % (stamp(), ",".join(t[-12:] for t in TAGS), QUIET_LIMIT_MIN,
             FREE_GB_FLOOR), flush=True)
    was_quiet = {}
    # The level last reported, not a boolean. A latching flag is right for a
    # silence episode (it either is silent or it is not) and wrong for a
    # continuous quantity that can keep getting worse: on 11 Sep this alarm
    # fired once at 0.87 GB and then sat mute through 1.58 GB, because the
    # latch only cleared upward. Re-alarm on material further degradation.
    low_at = None
    REALARM_DROP_GB = 0.4
    last_alive = time.time()

    while True:
        try:
            free, commit = memory()
            ages = {t: quiet_min(t) for t in TAGS}
            live = {t: a for t, a in ages.items() if a is not None}

            if free is not None:
                first = low_at is None and free < FREE_GB_FLOOR
                worse = low_at is not None and free <= low_at - REALARM_DROP_GB
                if first or worse:
                    print("%s !! LOW MEMORY   free %.2f GB%s, commit %s%%. "
                          "Sessions: %s. Free RAM has never predicted a kill in "
                          "this harness (entry 15) -- this is context for a "
                          "worker that stops, not a forecast."
                          % (stamp(), free,
                             "" if first else " (was %.2f when last reported)" % low_at,
                             commit,
                             ", ".join("%s %dm" % (t[-10:], a)
                                       for t, a in live.items()) or "none"),
                          flush=True)
                    low_at = free
                elif low_at is not None and free >= FREE_GB_FLOOR + 0.5:
                    print("%s ** MEMORY BACK  free %.2f GB, above %.1f GB"
                          % (stamp(), free, FREE_GB_FLOOR + 0.5), flush=True)
                    low_at = None

            for t, age in live.items():
                if age >= QUIET_LIMIT_MIN and not was_quiet.get(t):
                    print("%s !! WORKER QUIET %s wrote no row for %dm. "
                          "free %s GB, commit %s%%. Other workers: %s"
                          % (stamp(), t, age,
                             "%.2f" % free if free is not None else "?", commit,
                             ", ".join("%s %dm" % (o[-10:], a)
                                       for o, a in live.items() if o != t) or "none"),
                          flush=True)
                    was_quiet[t] = True
                elif age < QUIET_LIMIT_MIN and was_quiet.get(t):
                    print("%s ** WORKER BACK  %s wrote a row" % (stamp(), t), flush=True)
                    was_quiet[t] = False

            if time.time() - last_alive >= ALIVE_EVERY_SEC:
                print("%s .. ALIVE         free %s GB commit %s%%  %s"
                      % (stamp(),
                         "%.2f" % free if free is not None else "?", commit,
                         "  ".join("%s=%sm" % (t[-10:], a) for t, a in ages.items())),
                      flush=True)
                last_alive = time.time()

        except Exception as exc:
            print("%s !! FANWATCH ERROR %s: %s"
                  % (stamp(), type(exc).__name__, exc), flush=True)

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
