---
name: britania-board
description: "Show the current state of the project as one table - every live ticket, which worker holds it, what stage of the ship gate it is in, and what is queued behind it. Use when the user asks what is happening, what is in flight, what is left, or where a ticket has got to; and before answering any question about progress from memory."
metadata:
  author: the Lelouch harness
  hermes-tags: orchestration, state, backlog
---

# britania-board

**Run the script. Show its table. Add nothing.**

```
python <skill>/board.py            # live work
python <skill>/board.py --all      # plus the full queue
python <skill>/board.py --run <id> # when you know the Orca run id
```

That is the whole skill. What follows is why it exists and how to read what it
prints — not extra steps.

## Why a script rather than you looking things up

The answer to "what is happening" is split across three registries, and **none
of them knows about the other two**:

| source | holds |
|---|---|
| `tasks-axi` | what work exists, what is blocked on what |
| `orca` | which worker holds which ticket, and whether it is alive |
| `~/.no-mistakes/state.sqlite` | where that ticket's branch is in the ship gate |

A ticket id on its own does not tell you whether its worker is building, parked
on a review finding, or dead. Joining that by hand costs several commands and a
paragraph of reasoning **every time it is asked**, and the reasoning is where the
mistakes come from.

The script also carries the gate's schema in a comment, so nobody has to
rediscover it. That matters: the supported `no-mistakes axi` view **truncates**,
which is why agents keep opening the database directly and paying for the same
two failed queries each time.

## Reading the table

```
IN FLIGHT
ticket          backlog      worker    gate     steps  pr   pr state (age)  last act
wa-06a-paging   in_progress  running   review   3/9    24   open (4h49m)    6m
```

- **gate** is the step it is *sitting on*, not the last one it finished.
- **steps** is completed over total, so `3/9` and `review` together say where.
- **pr state (age)** is the one to read carefully. It is a **cached
  observation**, not a live read — the age is how long ago the gate last
  actually looked. Minutes means a monitor is watching. Hours means it stopped,
  and the state shown may be long out of date. A run once reported `PR remains
  open` seventeen minutes after that PR had merged, from a read four hours and
  forty-nine minutes old.

The script prints a note when any row is in that condition. **Do not paraphrase
the note away** — it is the difference between a live fact and a stale one.

## What not to do with it

- **Do not narrate the board into the conversation.** The user asks for state
  when they want state. Between events you say nothing (contract §7).
- **Do not answer progress questions from memory** because you dispatched the
  work and think you remember. You remember the dispatch, not the gate.
- **Do not write to `state.sqlite`.** The script opens it `mode=ro` and so
  should anything else. It belongs to the gate daemon, which is shared by every
  worktree on this machine.

## When a row looks wrong

The three sources disagreeing **is information**, not an error to reconcile
silently:

- backlog says done, gate says `review` → a re-gate is running on a merged
  ticket, and its fix is not on the remote yet.
- worker alive, gate stage unchanged for hours → check `last act` before
  restarting anything. A gate timeout recycles the agent inside the step; a new
  process with an advancing head is still working.
- worker gone, gate mid-run → the client died, not the run. The pipeline lives
  in the daemon; `no-mistakes axi status` is the authority.

Each of those has a fuller entry in `docs/agents/harness-gotchas.md`.
