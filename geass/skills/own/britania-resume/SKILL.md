---
name: britania-resume
description: "Pick work back up after a stop - a quota cap, a pause, a machine that slept - without redoing what is already done. Reports each worker's real position against the ship gate before anything is restarted."
disable-model-invocation: true
metadata:
  author: the Lelouch harness
  hermes-tags: orchestration, recovery, session
---

# britania-resume

**The user runs this.** You never invoke it yourself.

```
python <skill>/resume.py
python <skill>/resume.py --all    # include settled workers too
```

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
