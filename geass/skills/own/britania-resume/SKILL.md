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
  wa-paging   worker running   local c0fa1bd   gate 7bfd6af
    -> fast-forwarded 1 commit(s); the checkout now has its own finished work
    -> sent the worker its position by --type status
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

## A dead terminal is not a resume

If the terminal is gone, this skill **does not message anything**. It says so and
stops:

```
TERMINAL GONE -- this is not a resume. Open a fresh session in that worktree and
let it run britania-restore; recovering a dead session is that skill's job, from
inside, and its unfinished work is listed below.
```

The boundary is worth holding. You cannot restore a session from outside it —
restore runs **in** the session being rebuilt. So resume reports the state and
hands over, rather than pretending a dead worker can be nudged.

`britania-restore` detects that it is in a linked worktree (its `.git` is a file,
not a directory) and gives the **worker's** briefing instead of the
orchestrator's: read §W and stop there, here are your uncommitted files, your own
banked commits, and what the gate added.

## Three verdicts, and how to tell them apart

- **"Its terminal is gone but the gate run is NOT."** The client died, the run
  did not — the pipeline lives in the daemon. Do not start anything. Check
  `no-mistakes axi status` in that worktree; re-running `axi run --intent …`
  with `HEAD` unchanged **reattaches to the same run**.
- **"Gate is at review."** A timeout there **recycles the agent inside the
  step**. A new process with an advancing head is still working, and restarting
  it throws away a round. Check before acting.
- **"Worker is <settled>, terminal gone."** Resuming means a fresh dispatch, not
  a nudge. A live worker takes `--type status` mail instead.

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
