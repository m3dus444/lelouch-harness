---
name: britania-resume
description: "Pick work back up after a stop - a quota cap, a pause, a machine that slept - without redoing what is already done. Reports each worker's real position against the ship gate before anything is restarted."
disable-model-invocation: true
metadata:
  author: the Lelouch harness
  hermes-tags: orchestration, recovery, session
---

# britania-resume

**The user runs this. It acts — it does not just describe.**

```
python <skill>/resume.py              # resume the work
python <skill>/resume.py --dry-run    # show what it would do, touch nothing
python <skill>/resume.py --all        # include settled workers too
```

## What it actually does

Running it **fast-forwards each stalled checkout onto the work the gate already
finished**, and **tells each live worker where it now stands** so it carries on
instead of rebuilding. You do not run the commands afterwards; it ran them.

```
  wa-paging   worker running (terminal live, dispatch ctx_7b41c9d0e255)   local c0fa1bd   gate 7bfd6af
    -> fast-forwarded 1 commit(s); the checkout now has its own finished work
    -> queued its position for the worker (--type status). Queued, not read:
       mail is pull, so it lands when the worker next runs `orchestration check`
       Work it already has -- name these when you resume it:
           7bfd6af fix(paging): keep the cursor stable across a refill
```

**`merge --ff-only` is the safety, not a risk.** It advances a branch only when
the move is a pure fast-forward and refuses otherwise — it cannot overwrite a
commit, drop uncommitted work, or rewrite history. That refusal is the same
check a human would make by hand, which is why this runs unattended.

Three things it deliberately will not do, because none of them is safe to decide
from here:

| | |
|---|---|
| a fresh dispatch | costs tokens and needs a spec — that is a decision |
| a force-push | one-way, and the classifier refuses it anyway |
| closing a ticket | the work is not verified from here |

It also skips the fast-forward on any tree with uncommitted files and says so,
rather than moving a branch under work in progress.

## The dry run reads ahead, not only behind

`--dry-run` runs **the same two checks the acting path runs**, against the same
refs, before it promises anything:

| | |
|---|---|
| does `no-mistakes/<branch>` exist here | a gate-owned worktree may never have pushed, and there is no fast-forwarding onto commits that were never sent |
| is `HEAD` an ancestor of it | the only condition under which git moves a branch without a merge commit |

So a dry run either says *"would fast-forward N commit(s) — checked against the
real condition, not assumed"*, or it says **"will NOT fast-forward, in either
mode"** and names why. The two paths can no longer disagree about what is going
to happen.

They once did, and it is the reason this section exists. The dry run predicted
from `behind` alone — *"would fast-forward 14 commit(s)"* — on a branch that was
also **3 commits ahead**. Behind and ahead are not exclusive; together they mean
*diverged*, which `--ff-only` refuses by definition, and the real run refused it
minutes later.

**The safety held; the report did not.** Nothing was overwritten and no history
was rewritten — the damage was to the plan built on the promise. That is the
shape of every reporting defect this skill has had, and a dry run that predicts
from what already happened, without checking the state it is about to move into,
is how each of them got written.

## A parked worker still has its context

A usage cap does not clear a session. The process sits there with its memory
intact, so it already knows its ticket, its own note, and the files it was
editing — **repeating those back is the noise §0 exists to forbid.**

It is sent only what it cannot know:

| | |
|---|---|
| **the gate's commits** | made by a *different* agent, in the shadow repo |
| **a moved tree** | if we fast-forwarded, the disk is now ahead of its memory |

> Resuming wa-feature. You were parked, not cancelled. The ship gate committed
> while you were parked and your checkout has been fast-forwarded onto it — so
> **the files on disk are AHEAD of what you remember. Re-read anything you touch
> before editing it.** Do not rebuild: `19dfc6b …`. Continue from there and
> report `worker_done` when finished.

If nothing changed underneath it, it is told that too — that is also something
it cannot verify without looking.

The ticket is named in one clause anyway. [F-011](../../harness/docs/agents/harness-gotchas.md)
recorded a woken worker that simply did nothing, and a nudge with no subject is
cheap to make pointless.

## Addressed by dispatch id — and a bounce is not a death

A worker has **two addresses, and they take different couriers**:

| | |
|---|---|
| `orca orchestration send --to dispatch:<dispatchId>` | mail, which the worker pulls |
| `orca terminal send --terminal <handle>` | a keystroke into its TUI |

The skill addresses mail by **`dispatchId`**, in full, and it never falls back to
the terminal handle when the dispatch id is missing. A handle used as a mail
address does not reach anybody — and the report says so instead, naming the
terminal route as the alternative.

**A failed delivery is not a dead worker.** Liveness is read from
`orca terminal list` and from nothing else; a bounce means *undeliverable*.

> Two workers were once reported *"gone, treat as dead"* because the message
> sent to them had bounced off a truncated terminal handle. **Both terminals
> were alive and connected.** Acting on it meant replacement dispatches into
> fresh worktrees and walking away from the gate-side fix commits already
> sitting in the existing ones — *the exact trap this skill warns about two
> sections down.*

The inverse holds just as firmly, and costs just as much: **a live terminal is
not a working agent.** A session that hit a usage cap still answers
`orca terminal list` as live and connected while its agent cannot act — two
builders sat frozen for four hours that way and were reported as *"both builds
are running again."* When the answer depends on whether an agent is doing
anything, read its screen: `britania-restore` classifies every builder as
**building / idle / capped** from exactly that.

## A dead terminal is not a resume

Everything here runs in **your** session. C.C talks to you, not to builders, and
these skills are `disable-model-invocation: true` — so no worker can invoke one
even in principle. There is no worker-side half of this.

So when a terminal is gone, there is nothing to nudge. The skill says so and
hands you the material for the **replacement dispatch you will write**:

```
TERMINAL GONE -- nothing to nudge. This needs a replacement dispatch from you;
its unfinished state is below, to go into the spec.
```

### The stranding trap, which is the part to read

```
DECIDE FIRST: 2 uncommitted file(s) live only in that worktree. §6 dispatches
Build and Fix with `--worktree new-top-level`, so a replacement gets a FRESH
checkout and this work is stranded. Either dispatch into the existing worktree,
or bank it first -- it is not on any branch and nothing else knows it exists.
```

Uncommitted work is the only state in this entire system that **no registry
holds**. The backlog does not know it, Orca does not know it, the gate does not
know it. It exists on one disk, in one directory, and the standard recovery —
a fresh dispatch into a new worktree — walks away from it without a word.

That is a decision, so it is yours: reuse the worktree, bank the work first, or
knowingly drop it.

## Four verdicts, and how to tell them apart

- **"Its terminal is LIVE."** Read first, and it outranks the worker record
  beside it — a record is a memory, `orca terminal list` is a reading. Resuming
  this one is **mail to its dispatch id**, never a replacement dispatch, and
  never a decision made from whether the last message landed.
- **"Its terminal is gone but the gate run is NOT."** The client died, the run
  did not — the pipeline lives in the daemon. Do not start anything. Check
  `no-mistakes axi status` in that worktree; re-running `axi run --intent …`
  with `HEAD` unchanged **reattaches to the same run**.
- **"Gate is at review."** A timeout there **recycles the agent inside the
  step**. A new process with an advancing head is still working, and restarting
  it throws away a round. Check before acting.
- **"Worker is <settled>, terminal gone."** Both halves are settled, so resuming
  means a fresh dispatch rather than a nudge. Note the **and**: a settled record
  over a live terminal is not this verdict, and the skill says so separately.

## Why it is driven by git rather than by Orca

Because Orca's view goes stale in exactly this situation. On the machine this
was built against, **77 workers existed and not one still had a live terminal** —
so a terminal-first listing returns nothing and silently skips the case that
matters most, where the client died and the run did not.

So the enumeration starts from `git worktree list`, and Orca and the gate are
used to enrich it. A worktree that exists is a fact; a worker record is a memory
of one.

## Afterwards

**Re-arm the wait before saying anything.** A resumed session with no armed wait
is deaf — it will sit through every `worker_done` that arrives.

```
orca orchestration check --wait --types worker_done,escalation,question
```

And if the stop was a quota cap, check the cap actually lifted before dispatching
into it: `britania-vitals` reports the **binding** window and its real reset
time, which is not always the one you were watching.
