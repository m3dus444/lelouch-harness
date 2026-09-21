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

**`afk.log` is a buffer, not a record.** Every `start` clears it, so anything
written here has a lifetime of exactly one window. That is fine for what the
digest needs — the digest is derived, and the log only annotates it. It is not
fine for anything else.

**The lifetime is one window whether or not the last one closed cleanly.** This
is the part that surprises people, because it is not a crash bug: a milestone
was once written to a window that then closed perfectly normally, and the next
`start` four and a half hours later erased it anyway. A clean shutdown does not
promote a buffer into a record.

`start` retires a non-empty buffer to `.lelouch/afk-<since>.log` rather than
destroying it, and says so — loudly when the window it is retiring never closed.
Treat that as a way to read back what just happened, **not** as storage:
`.lelouch/` is gitignored, so nothing in it has history, a remote copy, or any
way back once the directory does.

**So anything that must outlive the window gets written somewhere else at the
same moment.** Not afterwards, when you remember: at the same moment, in the
same breath as the `decision` line. A milestone being reached, a decision that
changes the backlog, a fact the next session needs — those go to their real
homes, and the log line is a copy for the digest rather than the only copy. A
"MILESTONE REACHED" recorded here and nowhere else has already been lost to the
next `start`.

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

**What ends the window depends on what they sent.** They do not have to remember
a command, so read the message and decide between three cases:

- **A read-only status question** — "how's it going", "anything waiting on me" —
  is **neutral.** Answer it and leave the window open. They are checking on the
  work, not returning to it, and ending the window here throws away the digest
  they will actually want later.
- **A quick instruction they have marked as such** — they say to keep going, to
  stay on it, that this is just one thing — **continues the window, and its
  outcome is recorded** like anything else that happened while they were away.
  It becomes a line in the digest, not an exception to it.
- **Anything else ends it.** Run `back` before answering, and answer in the
  digest's terms.

When the message genuinely does not fall cleanly into one of those, end the
window. A digest delivered slightly early costs a paragraph; a window that
silently outlives their return means everything after it was recorded for a
reader who was already in the room.

This is a reading of the message, not a new mode, and it must stay that way: a
slash command would re-inject the skill mid-flight, and an injected skill has
been observed cancelling a coordinator tool call in progress.

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
