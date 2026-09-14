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
4. **What enforces `user-invocable`** as a one-way door, for the three user-only
   skills.
5. **Does `observe.py` miss `domain-modeling`** — detector question, decides
   whether that scorecard row can be trusted.

## Free win found while answering a question, not yet applied

`NODE_EXTRA_CA_CERTS` is set in **User** scope to
`C:\Users\JulienHélie\Documents\Coding\HUM\dopecert.cer`, **and that file does
not exist.** That is the origin of the `dopecert.cer … load failed` warning on
every single Node invocation in this environment — and it is the same string
[F-060](findings.md) found masking the real cause of every gate failure.

Unset the variable (or repoint it at a real certificate) and the noise stops
everywhere at once. Not done: it is a machine-level change and C.C called the
cert a hold fix, so it is theirs to make.

## Next actions, in order

1. Reopen the Lavish session and poll; answer the subject radio.
2. Apply the two Graphify measurements, or defer it out of v2.
3. Write the v2 contract from the 26 kept edits.
4. `geass cast --force` into the chosen project, `git diff` to confirm the
   version landed (issue #20), commit, then start the session.
5. Open `supervision/runs/run03/` — numbering restarts at **F-001**.
