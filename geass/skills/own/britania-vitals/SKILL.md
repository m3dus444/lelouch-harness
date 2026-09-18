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
  memory   4.04 / 15.6 GB free (floor 1.0)
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

**The memory floor is 1.0 GB, and it used to be 2.0.** The evidence for moving it
is one run's worth of its own false positives: four breaches at the old floor,
every one of them recovered by the next reading, and not a single kill among
them. Defender alone holds around 1.5 GB here, so 2.0 GB free was never a
machine in distress — it was a line drawn across the middle of this machine's
ordinary range. A threshold with a 100% false-positive rate is not measuring
anything.

That is the **gate's** floor, though, and the gate answers a different question
from the watcher. Holding a dispatch on a low reading costs a pause; waking a
session costs a turn and the loss of whatever it was doing. So the watcher does
not alarm on this floor alone — see below.

## Auto mode — the watcher

This runs **outside** the session. It is not something you invoke
mid-conversation, and it is **not started by the session-start hook** — see
below for why.

```
python <skill>/vitals.py --watch --interval 300
python <skill>/vitals.py --watch --present      # user at the keyboard: warn only
python <skill>/vitals.py --watch --dry-run      # print what it would send
```

### Where it actually lives: the OS scheduler

```
geass watcher            # register it, once
geass watcher --force    # re-register after the skill changes
geass watcher --remove   # unregister
```

It runs **`vitals.py --once` on the scheduler's cadence**: check, wake if
something breached, say so if something recovered, exit. The cadence is
`WATCHER_EVERY_MIN` in `geass/cli.py`, and `geass watcher` prints the value it
registers — the number is deliberately not repeated here, because it is not
free to choose. See *"the cadence is downstream"* below.

**It costs no tokens of its own.** It is a plain script. The only tokens it ever
causes are one turn in the session that is already running — which is also the
only session that knows what to park.

#### Why not an Orca automation

The obvious choice, and wrong. `orca automations create` **requires `--prompt`
and `--provider`**: every firing that passes its precheck starts a *new agent
session*. That spends tokens, and worse, the agent arrives with no context — it
is not the orchestrator and cannot park work it knows nothing about. The only
plain-command slot there is `--precheck`, which is a gate, not an action.

#### Why `--once` on a schedule, not a resident `--watch`

A long-lived watcher is a process that can die without saying so, and **a
monitor that has gone quiet looks exactly like a healthy one.** This machine has
demonstrated that repeatedly. A scheduled one-shot has nothing to keep alive: if
a run is missed the scheduler records it, and the next one still fires.

**Records it — to `LastTaskResult`, and to nothing else.** That is not the same
as telling anyone, and the difference has already cost a run: a watcher
registered with an unresolvable interpreter fired every 15 minutes for hours,
failed instantly each time, and reported as "registered" throughout. Moving off
a resident process removed one silent death and introduced another. What closes
it is reading the result code, so `geass doctor` does — and counts a registered
but failing watcher as a blocking problem, because it occupies the place where
someone would otherwise notice nothing is watching.

`--watch` still exists for a foreground terminal you are actually looking at.

#### Why casting does not register it

Casting writes files — inert until someone uses them. Registering something that
runs on its own schedule changes the machine, so it is the user's call to make
explicitly. `cast` reports whether the watcher is registered and names the
command; it never does it silently.

> On the two exit codes: `--gate` answers *"may I dispatch"* (0 = clear) and
> `--breach` answers *"is there a problem"* (0 = yes). They are inverses on
> purpose, because one number cannot be right for both callers. `--breach`
> exists for any scheduler that treats exit 0 as "proceed".
>
> `--once` is a third caller and answers *"did I watch"*: **0 when it looked,
> 3 when it could not.** An idle machine with no orchestrator open exits 0 —
> that is the normal case and alarming on it would bury the scheduler's record
> in noise. Being unable to resolve `orca` exits 3, because then it cannot see
> the session at all, and a watcher that quietly exits 0 while watching nothing
> is the failure this whole section exists to prevent.

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

### The alarm is reversible now, and mostly silent

For most of its life this watcher was a **ratchet**. It held exactly one
`wake()` call with one fixed text — *"Stop dispatching and park the run"* — and
no branch anywhere that said the opposite. Set the two directions beside each
other and the defect is the whole design:

| | |
|---|---|
| says **park** | every tick, indefinitely, for as long as the condition holds |
| says **resume** | never, under any condition |

So a *momentary* dip produced a *permanent* park. In one run free memory
breached at 1.92 GB and stood at 3.6 GB a minute later; nothing said so, and the
work restarted only because the coordinator reasoned its way there from a stale
number. Recovery depended on precisely the unreliable attention the watcher
exists to compensate for — and *being woken once and then being careful* looks
identical in a transcript to *staying watchful*, which is how this went unnoticed.

Four changes close it. They are described separately and they landed together,
because each one is unsafe on its own.

**1. A session at 0% quota is not woken at all.** The general rule here is that a
level which is still bad is still worth saying, and that **de-duplication belongs
to whoever reads it** — a good rule, and it held the one time the recipient had
quota left to answer with: it replied that the run was already parked and moved
on. It fails for exactly one condition. A binding window at 0% does not mean
*nearly out*, it means the session can only answer *"you've hit your session
limit"*, so the breach has disabled the reader the breach is addressed to. Eight
injections went into a capped session that way. Anything above zero keeps the
delegation; an unavailable reading is not zero and is still woken, because not
knowing the quota is no reason to stay quiet about the disk.

**2. There is an all-clear, and a deliberate gap between the two lines.** When a
condition recovers, the same instrument that parked the run says so and lifts
the hold. The recovery line is **not** the floor: a value must come back to
`RECOVERY_MARGIN` above it — 25% above the floor — before anything is
announced. Declaring an all-clear at exactly the floor is declaring it one
reading before the next alarm, and a run told to park, resume and park again has
been told nothing it can act on. The band between the two lines is silent on
purpose — inside it, whatever was last said still stands.

That needs the watcher to remember what it last said, which a scheduled one-shot
cannot do in memory. It is written to `.lelouch/vitals-state.json`, beside
britania-afk's marker. **File-held state usually deserves suspicion, so be exact
about what it can cost here:** the file never decides *what* to send, only
whether to repeat it, because every message is driven by the reading taken from
the machine on that tick. A lost or corrupt write therefore produces a duplicate
park or a duplicate resume — one wasted turn — and cannot produce an inverted
one. Delete the file and the watcher re-derives everything from the next reading.

**3. Memory alarms on a sustained step change *and* a dangerous level — both.**
Not either. Each half alone is a false-alarm generator, and this machine has
supplied the data for both:

- *A threshold alone fires on churn.* Free RAM wanders across any line you draw.
  Three dips under 2 GB in forty-five minutes, all self-recovered, no kills.
- *A step alone fires on a harmless drop.* 8 GB falling to 6 GB and staying there
  is a large, sustained, entirely fine step — something launched, and there is
  still ample headroom.

The intersection is what is worth a turn: a fall big enough that a program took
the memory and is keeping it, landing somewhere the machine cannot afford.
2.2 GB dropping to 0.4 GB and holding is that. 1.92 GB for one minute is not, and
neither is a machine that has simply been low all along — no step, no news, and
the latch has already said whatever there was to say. This is a **different
instrument from `FREE_GB_FLOOR`, not a tuning of it**; the floor became the
backstop when it stopped being the trigger.

**Quota is explicitly excluded from this treatment** and stays a plain threshold.
It is monotonic and it does not wander, so waiting for a second reading to
confirm only spends more of the thing being protected.

**4. And only then, the cadence is downstream.** How often the scheduled task
fires is `WATCHER_EVERY_MIN` in `geass/cli.py`, and the agreed move is **15 -> 5
minutes, conditional on 1-3 above being in place**. That condition is not a
formality: at fifteen minutes an instrument that could only say "park" produced
nine injections in a single run, and at five it would have produced
twenty-seven. Five minutes is affordable only because most ticks now say nothing
at all. **If any of the quiet above is ever taken back out, the cadence goes back
up with it** — and a faster cadence proposed on its own, as a way to notice
things sooner, is the same mistake wearing a better motive.

It does **not** clear or compact anything yet. That waits on `britania-restore`
being built and proven — auto-clear without a working restore destroys whatever
was not written down, at the moment the session is most loaded.
