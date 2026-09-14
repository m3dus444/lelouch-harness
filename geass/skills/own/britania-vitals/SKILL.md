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

This runs **outside** the session. It is not something you invoke
mid-conversation, and it is **not started by the session-start hook** — see
below for why.

```
python <skill>/vitals.py --watch --interval 300
python <skill>/vitals.py --watch --present      # user at the keyboard: warn only
python <skill>/vitals.py --watch --dry-run      # print what it would send
```

### Where it should actually live: an Orca automation

You do not create this by hand, and casting does not create it for you:

```
geass automation            # create it, once
geass automation --force    # replace it after the skill changes
```

It is opt-in because **an automation spends tokens on a schedule.** Casting
writes files and initialises a gate — inert things that cost nothing until
someone uses them. A recurring bill is not in that category, so `cast` only
reports that the watcher is absent and names the command.

It is also **global to the Orca runtime**, not per-project, so casting into a
second project must not produce a second watcher. `geass automation` checks
before it creates.

What it builds:

```
orca automations create --name britania-vitals --trigger hourly \
  --precheck "python <skill>/vitals.py --breach" \
  --provider claude --workspace <selector> --prompt "..."
```

`--precheck` is what makes this cheap: the check runs on its own schedule and
costs nothing, and **only a breach involves an agent at all.** Quiet hours are
free.

> **`--breach`, not `--gate`.** Orca documents the precheck as *"exit code 0
> continues, anything else records a skipped run"* — so the precheck must answer
> **"is there a breach"**, which is the inverse of **"is it safe to dispatch"**.
> Wiring `--gate` here would wake an agent every quiet hour and stay silent
> through an actual breach. Two flags, named for the question each answers,
> because one number cannot be right for both callers.

### Why NOT the session-start hook

It is the obvious place and it is wrong, for a reason worth stating so nobody
re-proposes it:

- **The hook is deliberately role-neutral and fires for every agent that opens
  this repo — including each dispatched worker in its own worktree.** Four
  builders would start five watchers, all waking the same coordinator terminal.
  There is no role check available to prevent it, because the hook refusing to
  assert a role is the whole point of its design.
- **A process spawned from a hook outlives the shell that started it and
  inherits its working directory.** That is exactly how the ship gate's daemon
  came to pin a worktree open and make it undeletable.
- **Background processes here are killed unpredictably**, so a watcher started
  this way would stop without saying so — and a monitor that has gone quiet is
  indistinguishable from a healthy one.

A scheduled automation has none of those properties: one instance, owned by the
runtime, restartable, and visible in `orca automations list`.

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
