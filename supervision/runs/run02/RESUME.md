# Where we stopped — 14 Sep, ~04:00

Run 02 is closed and torn down. What remains is the v2 decision pass, most of
the way through.

## State

- **Lelouch:** on hold, no builders out, no worker terminals.
- **Watchers:** all stopped. Logger stopped (`bayao61nx`).
- **no-mistakes:** updated to **v1.72.0**. It cannot go further —
  `channels.json` names v1.72.0 and the repair for that is in v1.73.0.
- **Lavish session:** **still open**, deliberately. Do not run `lavish-axi end`.
  Reopen with `npx -y lavish-axi .lavish/v2-change-list.html`, then
  `npx -y lavish-axi poll .lavish/v2-change-list.html`. Queued feedback survives;
  it is delivered whenever a poll next runs.
- The live artifact is `.lavish/v2-change-list.html` (gitignored); the committed
  copy here is an export and is **not** what to edit.

## Decided

| bucket | outcome |
|---|---|
| **Contract** | **all 26 kept, nothing cut** |
| **Skills** | **all 9 kept, nothing cut** — including Graphify, kept deliberately pending evidence |
| **Upstream** | **11 kept, 3 cut** — F-060 (the dopecert noise is local), F-053 (C.C had taken the terminal over by hand), F-052 (the permissions fix covers it) |

Also settled in the exchange: v2 ships contract **and** skills together; the
memories split **5 rules / 6 reference** rather than going into one doc;
`britania-vitals` is **one script with two modes**, and Lelouch never writes
shell for it; the npx precedence rule goes in the **contract**, not the lavish
skill; `worktree-retire` stays as a **script plus a one-line rule**.

## Open

1. **Which app does v2 run on** — weave-atlas continued, or a fresh app. The
   radio at the bottom of the artifact. Nothing else blocks on it, but it
   changes what run 03 can measure.
2. **Graphify**, after the scout. Storage lands well — `graphify-out/` sits in
   the working tree and is meant to be committed, so each worktree gets its own
   graph. Three things land badly: rebase is undocumented entirely, deletions
   leave stale nodes without `--force`, and the docs contradict the repo on
   license, stars and language count — so the 71.5× token claim is unverified.
   Two local measurements settle it; both are in the artifact row.
3. **`no-mistakes axi run` re-attach** — can a blocking wait observe a gate you
   do not own? Test on a throwaway branch; the risk is starting a duplicate run.

## Closed since — two of the five open questions

**Model invocation is enforced, and I had named the wrong field.** There are two
independent flags, not one with two directions:

```
disable-model-invocation: true   -> user only   (grill-with-docs, grill-me)
user-invocable: false            -> model only  (quota-axi)
```

C.C pointed out the proof was already in our own scorecard: `grill-with-docs`
was **called and never ran** — the flag refusing the model, observed live. So it
is enforced, not advisory, and `britania-afk` / `-resume` / `-restore` get
`disable-model-invocation: true` on demonstrated rather than assumed safety.

**`observe.py` was right; its label was wrong.** Both halves are true at once:

```
CONTEXT.md        exists, 10,652 bytes, "## Vocabulary" at line 27
Skill tool calls  12 across the run -- research, lavish, to-tickets, prototype,
                  grill-with-docs, grilling, chrome-devtools-axi
domain-modeling   never invoked. Not once, in six days.
```

**The glossary was written by hand and the skill that exists to write it never
ran.** The check is called *"wrote the glossary (domain-modeling)"* but it
measures **skill invocation**, not the artifact — and this run is exactly where
those diverge. Same family as [F-040](findings.md), *a step that runs and a step
that does its job are different things*, inverted. **Fix: measure the artifact
and the invocation separately, and name each for what it measures.**

This also resizes [F-116](findings.md): the cost of `grill-with-docs` being
refused was not one extra step — `domain-modeling`'s method was skipped
entirely.

And it answers C.C's contract question: coverage **already exists**
(`CLAUDE.md:251` routes *"Terminology or ADR work"* to `domain-modeling`;
`docs/agents/domain.md` says to note missing concepts for it) and **was never
followed in six days.** So it is a rule that needs a *trigger*, not a rule that
needs writing.

**Run-03 scorecard row, agreed with C.C:** count `domain-modeling` invocations.
It should fire several times — once in the grill, and again whenever terminology
changes.

## The dopecert warning — diagnosed and fixed, 14 Sep

`NODE_EXTRA_CA_CERTS` was set in **User** scope to
`C:\Users\JulienHélie\Documents\Coding\HUM\dopecert.cer`, **a file that did not
exist.** That was the origin of the `dopecert.cer … load failed` warning on every
Node invocation here — the same string [F-060](findings.md) found masking the
real cause of every gate failure.

**The cert is real.** `CN=dope.security_root_ca 1` — a TLS-inspecting proxy root,
present in **both** `CurrentUser\Root` and `LocalMachine\Root`, valid to 2039.
It vanished from disk because it had been stored inside
`Documents\Coding\HUM`, which is a **git repo**.

**It was noise, not breakage — but only for now.** Measured at the time of the
fix, every chain terminated at a *public* root:

```
registry.npmjs.org  authorized: true  root: GTS Root R4
graphify.net        authorized: true  root: SSL.com TLS ECC Root CA 2022
api.github.com      authorized: true  root: USERTrust ECC Certification Authority
```

So dope.security was not intercepting on this network. The moment it does — a
different network, a VPN, the agent re-enabled — Node fails on an unverifiable
chain, and a variable pointing at a missing file protects nothing.

**Applied**, at C.C's choice of the three options offered:

```
NODE_EXTRA_CA_CERTS   removed        (User scope)
NODE_OPTIONS          --use-system-ca (User scope)
```

Node 24.19.0 reads the Windows store directly, where the cert already lives and
is already trusted. Nothing new is trusted; there is no longer a file to lose;
a future corporate cert is picked up automatically. Verified: `npx -y lavish-axi
--version` now prints only `0.1.63`, with no warning lines.

**Two residuals, stated rather than assumed.** The flag is documented to read the
OS store and the cert is in it, but that cannot be *proven* until something
actually gets intercepted — no current connection is. And this is a User-scope
change: **every already-running process keeps the old environment**, so Orca
terminals, the Lavish server and any live session will keep printing the warning
until restarted. Do not read that as the fix having failed.

## Next actions, in order

1. Reopen the Lavish session and poll; answer the subject radio.
2. Apply the two Graphify measurements, or defer it out of v2.
3. Write the v2 contract from the 26 kept edits.
4. `geass cast --force` into the chosen project, `git diff` to confirm the
   version landed (issue #20), commit, then start the session.
5. Open `supervision/runs/run03/` — numbering restarts at **F-001**.
