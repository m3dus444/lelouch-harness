---
name: britania-restore
description: "Rebuild the orchestrator's working state in a session that has no continuity - after a crash, a power cut, or a deliberate /clear. Derives everything from the backlog, Orca and the ship gate rather than from a handoff file."
disable-model-invocation: true
metadata:
  author: the Lelouch harness
  hermes-tags: orchestration, recovery, session
---

# britania-restore

**The user runs this. You never invoke it yourself** — a session that decides on
its own to rebuild its context is one step away from a session that decides to
clear it.

```
python <skill>/restore.py
```

## What to do with the output, in order

1. **Re-read `CLAUDE.md`, starting at the role gate.** A cleared session has
   lost the contract, not just the conversation, and the role gate is what
   decides whether you are the orchestrator or a worker. Everything else is
   wrong if that is wrong.
2. **Load the command schema in one call:** `orca agent-context`. It prints the
   whole machine-readable surface. Probing `--help` per command is the slower
   way to learn less.
3. **Bind the Run, if the briefing says you are not bound.** Until you do,
   `check` answers `consumer_fenced` — *"this coordinator terminal is no longer
   bound"* — which reads like a dead Run and is not one.
4. **Read the held decisions first.** They are questions the user is still
   owed. Everything in flight can wait behind them.
5. **Re-arm the wait** — `check --wait --types worker_done,escalation,question`,
   backgrounded — before saying anything. A restored session with no armed wait
   is deaf.
6. **Report to C.C in a few lines:** where the work stands, what is waiting on
   them, and **what was lost.** Not a transcript of this briefing.

## What it derives, and from where

Nothing here comes from a file the previous session was supposed to write,
because the case this exists for is exactly the case where it never got to.

| source | gives |
|---|---|
| `tasks-axi` | the backlog, and the decisions held against it |
| `orca` | Runs, terminals, live workers |
| `~/.no-mistakes/state.sqlite` | where each branch stands in the gate |
| `git` | branch, uncommitted work, unpushed commits |
| `CONTEXT.md` | the vocabulary the tickets are written in |

It reuses `britania-board` for the work itself rather than re-deriving it.

## The Run is the part to read carefully

**A Run carries no project identity** — only an id, a free-text objective and a
coordinator handle. On a machine with several projects there are several Runs,
so the briefing prints **how** it picked one:

- *"its coordinator terminal is in this project"* — exact. Trust it.
- *"its objective names <project> — CONFIRM before binding"* — a convention, not
  a guarantee. This is the usual case after a crash, because the terminal the
  Run names died with the session.
- *"GUESS: newest Run on the machine, project unverified"* — do not bind on
  this. Ask.

Binding the wrong Run points your waits and dispatches at someone else's work.

## Where the sources disagree

A crash lands *between* systems. Each one is updated by a different actor at a
different moment, so the boundaries between them are where state goes wrong —
and the briefing reconciles them explicitly:

```
backlog says done, gate never finished     the fix may not have shipped
backlog says done, PR still open           nobody merged it
backlog in flight, no live worker          a crash left the ticket started
live worker, backlog not in flight         the start was never recorded
a registered worktree is gone from disk    removal died halfway
```

**`backlog.md` and `tasks-axi` are not on that list, and cannot be.** The file
*is* the store rather than a rendering of one, so there is nothing to reconcile
between them.

### Reported, never repaired — and the flagged side is not the wrong side

A restored session does not know which source is right, and guessing turns a
visible inconsistency into an invisible one. That is not caution for its own
sake; here is a real instance from run 2:

```
wa-06a-paging: closed in the backlog, gate run is ci_monitor_interrupted
```

The backlog said done. The gate said its run never completed and its PR was
still open. **The backlog was right** — PR #24 had merged, and the gate's CI
monitor had been killed and never saw it. An automatic "fix" that trusted the
gate would have reopened finished work.

So: bring each disagreement to the user with what both sides claim, and check
the thing neither of them owns — the remote — before acting.

## What it cannot recover

**The conversation.** Anything decided and never written to the backlog, the
glossary or an ADR is gone.

Say that plainly. Do not reconstruct a plausible version of what was probably
agreed — a confident wrong summary is worse than an admitted gap, and the user
is the only one who can fill it. This is also the whole reason the contract puts
decisions in held rows rather than leaving them in chat: the backlog is the only
layer that survives a session ending.

## Two things the briefing will tell you that are worth acting on

- **`CONTEXT.md NOT TRACKED BY GIT`** — the glossary exists but no worker can
  read it, because a dispatched worker gets a worktree and an ignored file is
  not in it. Commit it before dispatching anything.
- **`NEEDS ATTENTION`** rows — runs that finished, but not cleanly. A failed
  step nobody looked at, a PR left open, a run that cannot close. These are what
  a crash leaves behind and what nobody notices on their own.
