---
name: britania-afk
description: "Work while nobody is at the keyboard, and report once in one digest instead of a scrollback. Use when the user says they are stepping away, going afk, back later, or leaving it running - and again when they return."
disable-model-invocation: true
metadata:
  author: the Lelouch harness
  hermes-tags: session, unattended, reporting
---

# britania-afk

**The user starts and ends this. You never decide to go quiet on your own.**

```
python <skill>/afk.py start               they are away; questions wait for them
python <skill>/afk.py start --autopilot   they are away; decide and merge for them
python <skill>/afk.py back                render the digest, clear the marker
```

## What actually changes

**Silence is already your default** — §7 has you say nothing between dispatch and
a real event, and surface exactly four things: a question, an escalation, a
`worker_done`, and a problem you cannot resolve.

So AFK does not make you quieter. **It changes what happens to those four.** They
stop interrupting an empty room and start accumulating into one digest.

| | without autopilot | with autopilot |
|---|---|---|
| a question you would ask | recorded, **re-asked** when they return | answered with your own recommendation |
| an `ask-user` finding from a worker | recorded, worker told to wait | answered with your recommendation |
| a PR ready to merge | recorded | merged, if it meets every criterion below |
| an escalation you can resolve | resolve it, record it | resolve it, record it |
| something you genuinely cannot resolve | recorded as a problem — **it is the first thing in the digest** | same |

## While they are away

Record as you go, one line at a time. **This is the only thing in the digest that
is not derived** — git, the gate and the backlog supply the state, but *why* you
did something exists nowhere else:

```
python <skill>/afk.py decision "merged PR #31 -- full traverse, CI green on head a1b2c3d"
python <skill>/afk.py event    "wa-cache hit a rate limit; retried once, it cleared"
python <skill>/afk.py ask      "Fast vs Exact default -- I recommend Fast, it changes the cost line"
```

`ask` is the important one, and it covers a case that is easy to miss: **they may
queue `afk` right behind a prompt they just sent you.** If your answer to that
prompt was a question, it was asked into an empty room. Record it with `ask` and
it comes back at the top of the digest, to be asked again properly.

## The merge criteria, in autopilot

Merge only when **all four** hold. Anything else is recorded and left:

1. The gate traverse completed — all nine steps, not eight and a skip.
2. CI is green **on the PR's current head**. Not "checks passed" — the head. A PR
   here once advertised green for a commit its branch had moved past, and the
   newer commit had never been pushed.
3. The diff does what its ticket says. A green pipeline is not a spec check.
4. No `ask-user` finding was parked and expired into a worker's own judgement.

Autopilot is a grant, not a habit. It lapses the moment they return, because the
marker is cleared by `back`.

## Coming back

**Any message from them ends it.** They do not have to remember a command — if
they type anything, run `back` before answering, and answer in the digest's
terms.

The digest is derived first and annotated second: merged PRs and landed commits
from git, live state from `britania-board`, then your log joined on top. If the
log is missing or a line is half-written — a session that died mid-sentence
leaves exactly that — **the digest still works.** That is the point of not
trusting a record as the source of truth.

Order matters. It leads with what they must act on:

```
WHILE YOU WERE AWAY -- 3h12m   (autopilot)

  Merged (2)
  Landed on this branch (5)
  Decisions taken for you (3)
  Also happened (4)
  [board]
  WAITING ON YOU (1)  -- asked while you were gone
```

Then **ask the waiting questions in your own words.** Do not paste the digest at
them and stop — the digest tells them what happened, but an unanswered question
is still your question to ask.

## It also tells the watcher

`britania-vitals` reads this marker. While it is set, a threshold breach makes
the watcher **act** — park the run, stop dispatching — instead of only printing a
warning. When they are present it warns and leaves the decision to them.

That used to be a `--present` flag someone had to remember to pass, and the one
time it would be wrong is the one time it matters.
