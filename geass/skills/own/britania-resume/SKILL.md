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

## The usual case: a builder cut off mid-edit

A usage cap does not wait for a clean stopping point. It interrupts a builder
**between keystrokes** — half-written files, maybe a commit or two of its own
that the gate has not taken yet. That is the ordinary shape of this, not an edge
case, and **a dirty tree is the work, not damage.**

Four states get told apart, and conflating them is how work gets redone:

| | |
|---|---|
| **work in progress** | edits never committed anywhere — the most fragile, and invisible to every registry but git |
| **commits of its own** | banked, but the gate has not taken them |
| **commits from the gate** | fix rounds made while it was stopped |
| **its own last note** | the progress comment it wrote on its Orca card |

The worker gets all four back, because **it has no memory of the session
either**:

> You were interrupted, not cancelled. Resume from where you were. Ticket:
> wa-feature. Your own last note: *"Wired the parser; tests for the error path
> still to write."* You have 2 uncommitted file(s) — this is your work in
> progress, not damage: `feature.py`, `NOTES.md`. **Read them before editing;
> they are further along than your memory of them.** Commits you already made,
> do NOT rebuild them: `3ae88eb wip(feature): first half`. The ship gate added
> these while you were stopped; commit or stash first, then
> `git merge --ff-only …`: `ed2c1a9 …`. Then continue, and report `worker_done`
> when finished.

That line about reading the files first is the one that matters. A resumed agent
trusts its own memory over the disk, and after an interruption the disk is
ahead — so it will happily rewrite work it already did.

**This is why §W asks workers to keep their card comment current.** It is the
only record of intent that survives the agent, and it is what makes the
difference between "resume this ticket" and "resume what you were actually
doing".

## Not the same job as `britania-restore`

| | |
|---|---|
| **restore** | the session lost its memory — rebuild what it knew |
| **resume** | the session is intact — the *work* stopped, and restarting it can destroy things |

If you can still remember the conversation, this is the one you want.

## The question it answers

**What would restarting each worker destroy?**

Usually something. The ship gate commits its fix rounds to a **shadow remote**,
not to the worker's checkout — so a stalled worker routinely sits *behind its own
finished work*. Restart it cold and it rebuilds commits that already exist,
which is the expensive failure this exists to prevent.

```
_wa-paging   worker abandoned (terminal gone)   local c0fa1bd   gate 7bfd6af
    FAST-FORWARD FIRST -- 1 commit(s) exist on the gate's remote that this
    checkout does not have.
        7bfd6af fix(paging): keep the cursor stable across a refill
        git -C "..." merge --ff-only no-mistakes/_wa-paging
        Name these commits when you resume it, or it will rebuild them.
    1 uncommitted file(s) -- bank them before anything else.
```

The order is deliberate: **fast-forward first**, because getting that wrong
costs the most; then uncommitted work; then how to re-engage the worker.

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
