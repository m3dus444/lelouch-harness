# Harness gotchas

Things about this machine and its tooling that are **not discoverable from the
documentation**, each one learned by paying for it. None of this is project
knowledge — it is true of the harness itself, which is why it ships with the
harness instead of being rediscovered per project.

> **Every entry is version-stamped.** Tooling moves; a gotcha that describes a
> bug someone has since fixed is worse than no gotcha, because it teaches a
> workaround for a problem that no longer exists. Observations below were made
> against **`no-mistakes` v1.64–v1.72**. If you are on something newer and an
> entry does not match what you see, **believe what you see** and say so.

---

## Two shells, two filesystem views — a path made in one may not resolve in the other

There are two ways to run a command here and they do not see the same
filesystem. Git-Bash sees `/tmp` and `/c/Users/…`. Native Windows Python and
PowerShell see `%TEMP%` and `C:\Users\…`. Each is internally consistent, which
is why this is invisible until **a path produced in one is consumed by the
other** — then it simply does not resolve, and the error names the path rather
than the boundary it crossed.

So it does not bite at all until a command hands a path across. A run that never
does will never see it; one that does can hit it three times in a night.

- **Write intermediates to the session scratchpad**, not to a shared temp
  directory. Besides the two views, a shared temp dir is a shared namespace: a
  stray `types.py` sitting in `%TEMP%` **shadows the standard library** for
  anything run from there, and the resulting failure looks like a broken
  interpreter rather than a stray file.
- **Decide which view owns a path before you build it**, not after a command
  fails on it.

**A project may opt into WSL, which adds a third view — and that is a per-project
decision recorded in an ADR, never a default.** One project needed it because a
tenant Defender rule blocked freshly compiled executables on the Windows host,
so native `cargo` could not work there at all. Under WSL, `/mnt/c/…` paths exit
`127` when handed to Git-Bash, and WSL `git` cannot read an Orca worktree's
`.git` pointer because that pointer holds a Windows path. None of that applies
to a project that has not opted in.

## The background-shell reaper kills long-running jobs on memory pressure

A backgrounded shell can be killed by the host's memory-pressure reaper while it
is working, with no failure of its own. It killed one long review loop **five
times**, once with **3.59 GB free of 15.6 GB** — comfortable, by any reading
except the reaper's.

Set `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1` at launch. It is set here at
User scope. Filed upstream; until it moves, treat a backgrounded job that
vanished without an error as this until proven otherwise.

## The ship gate commits to a shadow remote, so a worker can be behind its own work

The gate is a git proxy. Its fix rounds are committed to
`~/.no-mistakes/repos/<hash>.git`, wired into each worktree as the `no-mistakes`
remote — **not** into the worktree's checkout. So a worker's `HEAD` can sit
behind work it already finished, and a cold restart rebuilds commits that
already exist.

Before resuming any stalled worker, find out what it already has:

```
git -C <worktree> fetch no-mistakes
git -C <worktree> log --oneline HEAD..no-mistakes/<branch>
```

Then tell it to `git merge --ff-only` that branch **before it touches code**, and
name the commits so it does not re-derive them.

Observed four times in one day across four different workers.

## A gate timeout has two outcomes, and only one of them is a dead run

| Where it hits | What happens |
|---|---|
| inside **review** | the agent is recycled *within the step* — a new process picks up, `HEAD` advances, the fix commit survives, the run continues |
| at **pre_push** | the whole run **fails** and restarts from intent |

The timeout fences the **agent**, not the run; only the steps that own the run's
exit gate turn an agent death into a run death.

**So a timeout message in a transcript is not evidence that anything died.**
Check two things before acting: did the **agent PID change**, and did **`HEAD`
advance**. A new PID with a new commit means it recycled and is still working —
do not restart it, and do not hand it recovery instructions it does not need.

**A killed client is not a killed run.** The pipeline lives in the daemon. When
the harness kills a backgrounded `no-mistakes axi run` client, `axi status` will
still show the run progressing, and re-running `axi run --intent …` with `HEAD`
unchanged **reattaches to the same run**. Always check `axi status` before
starting anything.

> *v1.68.0 changed part of this:* each review agent now gets a fresh timeout
> budget rather than sharing one across a fixer and its re-reviewer. The
> two-outcomes distinction above still holds; the aggregate-boundary
> cancellations that used to kill long fix rounds should not recur.

## A re-gate on an already-green PR strands its fix, invisibly

The gate pushes only **after** review, test, document and lint have all passed.
So while a re-gate is parked — on an ask-user finding, say — **the open PR still
shows the previous head and gives no sign a newer commit is waiting.**

Observed cost: a run parked at review for ~7.5 hours; the PR was merged at the
old head in good faith and the fix never reached master.

**If you re-gate a PR that is already green and the gate parks, say so in the
escalation:** the PR still shows the old head, and merging it now drops the
pending commit. If it gets merged anyway, list the stranded commit in
`worker_done` as follow-up rather than assuming someone noticed.

## Finding text arrives truncated, and the full text is not in the supported view

`no-mistakes axi` truncates finding descriptions. A worker that must quote a
finding **accurately** to its coordinator cannot get it from the sanctioned
interface, which is why workers keep ending up in `state.sqlite` — a schema
nobody has documented, rediscovered at a cost of two or three failed queries
each time.

**Do not go to the database.** Relay the finding's **id and its summary**, and
let whoever needs the full text read it from the gate themselves. If the exact
wording genuinely matters, write it to a file and pass the path — never paste
finding text through a shell argument, because findings are full of backticks and
the shell will eat them. That has already cost a correction round-trip.

*Not fixed upstream as of v1.72.0.*

## The `no-mistakes` daemon is global, and it pins the worktree that started it

One daemon, one `state.sqlite`, for every worktree on the machine.

- **Restarting it affects everyone.** One worker recovering its own gate killed
  another worker's CI monitor mid-run.
- **It outlives the shell that launched it**, carrying that shell's working
  directory — so a worktree where someone once ran `no-mistakes daemon start`
  **cannot be deleted** for the daemon's lifetime, even when it is completely
  empty. An empty directory that refuses to delete with *"device or resource
  busy"* and no process naming its path is almost always this.

## `no-mistakes update` cannot always reach the newest version

The updater reads a published channel manifest, and that manifest has been stale
before — naming an older release than the repository actually had, with the fix
for exactly that staleness shipping in a version the stale channel could not
offer. **A bootstrap trap: the repair is only distributed through the thing it
repairs.**

If `update` claims you are current, check the project's releases before believing
it. *Observed v1.64.0 → v1.72.0, with v1.75.1 published and unreachable.*

## Lavish: one shared design-system copy, and pages live at the root

When Lavish pages use the project's own design system — which its design router
ranks above its default theme — **copy the assets once**, not per page:

```
.lavish/ds/tokens/*.css          from the project's design tokens
.lavish/ds/styles.css
.lavish/ds/assets/fonts/*
.lavish/<page>.html              references href="ds/tokens/colors.css"
```

**A page in a subfolder cannot reach a shared folder above it.** Lavish serves
each artifact from its own directory, so `../ds/…` returns 404 — measured.
Keeping the HTML at `.lavish/` root makes the reference a plain `ds/…` and the
problem disappears.

## Detect a stalled worker by heartbeat age, never by whether mail exists

Heartbeats **are** mail. So `you have 1 orchestration message` keeps arriving
from the healthy workers while the dead one says nothing — which is exactly what
hid a 2.5-hour stall.

Compare `created_at` per `from_handle` (`orca orchestration check --peek`)
against your worker map. And never drop the armed `check --wait` to save
memory: without it nothing acknowledges heartbeats, they pile up, every new one
re-triggers the notice, and you pay a turn per heartbeat *while* losing the
signal that would have shown the stall.

## The nudge cannot be silenced, and a filtered wait is why it keeps firing

Measured 2026-09-21, after C.C asked whether the injected `You have N
orchestration messages` prompts could be turned off. They interrupt whatever the
user is typing — the line is injected as if they had typed it, so an unfinished
sentence gets submitted along with it. That is the real cost, and it is theirs,
not yours.

**There is no switch.** `orca` exposes no settings command, and the only
`inject` in the machine-readable schema is `dispatch --inject`, which pushes a
spec at a worker. The nudge is emitted by the runtime whenever the bound Run
holds mail the coordinator has not consumed.

**So it can only be starved, and a filtered wait is what prevents that.** The
only consumer of the queue is your `check --wait`. It returns *only* when a
matching type arrives, and it **holds the delivery** while parked — so
everything non-matching stacks up unread behind it, which is exactly the
condition that fires the nudge. Draining and waiting are mutually exclusive on
one Run: you cannot empty the queue without letting the wait return or killing
it.

The consequence worth internalising: **filtering `--types` buys quiet in your
context and buys the user nothing.** The messages still arrive; they simply
accumulate instead of being read.

What is actually available, in the order worth trying:

- **Drop the type filter and drain.** Every message returns, you ack and re-arm,
  the queue stays near zero, and the nudge starves. The cost is a full context
  re-entry per message — §7's 12x figure — and it is yours rather than the
  user's.
- **Reduce what workers emit.** Heartbeat cadence comes from the dispatch
  preamble; fewer messages is fewer nudges at no context cost. Not yet checked
  whether it is tunable.
- **Ask Orca for a coordinator-quiet mode.** The real fix, and not ours to make.

**One thing remains unestablished, so do not assert it:** whether heartbeats
*alone* trigger the nudge, or only actionable mail does. On the night this was
written the queue held four `worker_done` and one `question` and no heartbeats
at all, so the clean case has never been observed. Settle it the next time a
worker runs with a wait armed — if a nudge fires while only heartbeats are
queued, the filter is the cause; if nothing fires, the cause was always unread
reports, which means a dead listener rather than a noisy runtime.

## A green test summary can hide files that never ran

Observed under vitest on a WSL worktree, and the shape generalises: a runner
that drops test files on a worker-start timeout can still print a green summary
for the files it *did* run. Three files vanished that way while the run reported
success, and the full suite only appeared once the tree was on a native path.

The cause was the crossing rather than the tests — loading a heavy test
environment across the Windows/WSL boundary took roughly **two minutes** against
a hardcoded **60s** worker-start timeout. A native `node_modules` symlink helped
and **was not sufficient**.

So: **a test claim is worth what its file count is worth.** A worker reporting
green reports how many files ran, and says so plainly when that number is below
the suite. Colour is not evidence; the count is. If a project's runner can be
made to fail loudly on a dropped file, that is worth doing once — and note that
a `--reporter` override on the command line puts you back to trusting the
summary.
