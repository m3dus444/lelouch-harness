---
name: britania-vitals
description: "Read what the machine and the session can afford right now - free memory, disk, battery, and remaining quota with its real reset time. Use before dispatching a worker or fanning out, when the user asks for something expensive, and whenever deciding whether there is runway left to continue. Also provides the unattended watcher that wakes the session on a threshold breach."
metadata:
  author: the Lelouch harness
  hermes-tags: environment, quota, resources, orchestration
---

# britania-vitals

**Run the script. Never write shell for this yourself.**

```
python <skill>/vitals.py            # read it
python <skill>/vitals.py --gate     # read it, and exit non-zero if you should not dispatch
python <skill>/vitals.py --json     # same numbers, machine-readable
```

```
vitals:
  memory   4.04 / 15.6 GB free (floor 2.0)
  disk     620.47 / 951.7 GB free (floor 5.0)
  battery  57% ON BATTERY
  session  86% left on the binding window (week), resets in 120h17m
           all: five_hour=99%, seven_day=86%, model:fable=100%
  verdict  clear to dispatch
```

## When to run it

- **Before dispatching a worker, and before any fan-out.** `--gate` gives you a
  non-zero exit so the check is a condition, not a paragraph you might skip.
- **Before agreeing to something expensive** the user asks for.
- **When deciding whether to keep going.** "Do we have runway" has a number.

## Why it is a script and not you running commands

Every reading here has a platform trap in it, and they do not announce
themselves:

- Free memory on Windows comes back through CIM, and a French-locale machine
  writes `4,22` where a parser wants `4.22`. A monitor here lost its memory
  readings to exactly that.
- Battery does not exist on a desktop. Absent is not an error, and code that
  treats it as one reports a healthy machine as broken.
- **Quota has several concurrent windows.** A five-hour session at 99% means
  nothing when the seven-day cap is at 4%. The script reports the window with
  **least remaining**, because that is the one that will stop you.

Each of those is fixed once, in one file. An agent improvising a one-liner
rediscovers them, and usually discovers only the first one.

## Reading the verdict

`clear to dispatch` means every floor is satisfied. `HOLD` names which one is
not, and by how much. The floors are printed beside the values on purpose — a
threshold you cannot see is one you cannot argue with.

**Free RAM is a useful number and a poor predictor.** On this machine background
tasks are sometimes killed with a low-memory message at moments that correlate
with nothing measurable. Report the number; never present it as the cause of a
kill you did not measure.

## Auto mode — the watcher

This runs **outside** the session, from a terminal or a scheduled task. It is
not something you invoke mid-conversation.

```
python <skill>/vitals.py --watch --interval 300
python <skill>/vitals.py --watch --present      # user at the keyboard: warn only
python <skill>/vitals.py --watch --dry-run      # print what it would send
```

On a breach it finds the coordinator's terminal (from the Run's
`coordinator_handle`), **waits for `tui-idle`**, and then sends one line into
the session.

Two rules it enforces, both agreed deliberately:

- **Wait for the turn boundary.** Injecting mid-turn corrupts whatever the agent
  was in the middle of. The wait is not politeness.
- **If the user is present, warn and do nothing.** `--present` is that switch.
  Automatic action is for when nobody is there to take it.

It does **not** clear or compact anything yet. That waits on `britania-restore`
being built and proven — auto-clear without a working restore destroys whatever
was not written down, at the moment the session is most loaded.
