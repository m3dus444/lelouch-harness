# v2 inputs — the debrief's own output

Captured 2026-09-13/14, during the run-02 debrief, from C.C's session
impressions. **This is requirements, not design.** Nothing here has been
specced, and the open questions in §6 are genuinely open.

Written because it existed only in conversation context for several hours, and
this run has already lost context to a compact once. It is banked here so a
crash costs nothing.

Sources are separable and should stay that way:

- **C.C's impressions** — ergonomics no instrument records. Given raw, before
  the findings were discussed, deliberately, so the findings could not
  contaminate the recall.
- **Run-02 findings** — where they corroborate or contradict, the finding id is
  named inline.

---

## 1. Skills to build

Naming: the `britania-` prefix marks a Lelouch skill so it cannot be confused
with a generic one (`restore` alone is far too common a name). Spelling is
**`britania`**, one `n` — deliberate, C.C's choice, not the lore spelling
*Britannia*. Keep it consistent; it is in every filename.

| skill | invocation | what it does |
|---|---|---|
| `britania-afk` | **user only** | Two modes. `afk`: Lelouch goes silent, writes deltas to a file instead of the terminal, and — **pre-MVP only** — merges PRs himself following what he would otherwise have recommended. `back`: renders the accumulated digest. Goal is a readable terminal, not 200 lines to catch up on. |
| `britania-resume` | **user only** | After a quota cap. Resume in-flight work — Lelouch's and the workers' — without losing what is already done. |
| `britania-restore` | **user only** | Cold start: new session, fresh context, no continuity. After a power cut, a crash, or a deliberate `/clear` taken for token reasons. Rebuilds state from files. |
| `grill-with-lavish` | model-invokable | Grill rounds rendered as lavish artifacts instead of terminal Q&A. Name kept as-is, not prefixed. |
| `britania-board` | model-invokable | Project state on demand: every ongoing ticket, its worker/scout, its stage (building / review / waiting on the gate), and the queue behind it. **Ticket names alone are too ambiguous to be useful.** ASCII table. |
| `britania-vitals` | model-invokable | Machine and session state: battery %, session usage, RAM, disk. Skill + script, in the shape of the `*-axi` skills. |

The four user-only skills are all session-lifecycle. A model that decides on its
own to clear or restore is how work gets lost — hence user-only.

### `britania-afk`, the merge clause

The pre-MVP self-merge is **not** a skill change on its own. §6's approval gate
is what stops Lelouch merging; permissions are the second lock. Both have to
move. It removes C.C's only checkpoint on work they did not watch, so it must
**expire at MVP** — written into the skill, not remembered.

### `britania-board`, and a finding it closes

It has to read `~/.no-mistakes/state.sqlite` directly, because the supported
view truncates ([F-111](runs/run-02-findings.md)) — two workers in run-02
independently went to sqlite for exactly this reason, and one of them burned two
turns on `no such column: step` because the schema is undocumented tribal
knowledge. **Document the schema inside the skill** and the rediscovery tax dies
with it.

### `britania-vitals`, and what already exists

Mostly assembly, not invention:

- session usage, runway, reset times, pace → the **`quota-axi`** skill, already
  installed
- RAM and disk → **`fanwatch.py`** in `supervision/contract-monitor/`, written
  for run-02; already has a free-GB floor and alarms
- battery → one Win32 query
- the wake → **`orca terminal send`** on a cron
- when to schedule the wake → `quota-axi` reports the reset time

The shift for v2 is that these stop being *my* supervision instruments and
become *Lelouch's* own, shipped in the geass payload.

Intended behaviour: check the environment **before** dispatching a worker or a
scout and validate the go; warn when a user request is about to need RAM the
machine does not have; raise a threshold alarm that **wakes Lelouch** on low
battery, low RAM, or high session usage. The wake matters more than the check —
a woken Lelouch costs nothing while asleep, a polling one costs a context
re-read every cycle.

Worked example C.C gave: session usage hits 95% → script wakes Lelouch → he
stops the work → script wakes him two hours later → he resumes.

---

## 2. Behaviour changes — contract-level, not per-skill

### Verbosity: one rule, three symptoms

Lelouch talks far too much. Three observed shapes, **one root**:

1. **Restating a decision C.C just made.** Verbatim example, on Q10 of a grill —
   *"you're right, I overreached. Develop both, test both, pick one, delete the
   loser. What that still requires is…"* followed by a paragraph. The correct
   response was `Develop both, test both, pick one, delete the loser.` or, better,
   **nothing at all** — the call was made, the addition is noise. Same on Q6
   (the table decision).
2. **Narrating a lavish artifact** — the styling, what went in it. Useless:
   lavish has a sidebar for feedback and he edits live. He should go quiet and
   say the artifact is ready.
3. **Narrating a dispatch** — what the scout will bring back, what it is working
   on. That is `britania-board`'s job, on demand.

He also writes about the decision C.C took rather than **what is left to do**.
Summaries after several decisions are fine, but short and structured — an ASCII
table, not fifty lines. This matters most when something goes wrong: **a problem
must surface immediately, not after a chapter of prose.**

The fix is one §-level contract rule, not three skill patches:

> Report state changes and blockers. Never restate a decision the user has just
> made. Never describe a produced artifact — name it. State lives in
> `britania-board`; the terminal carries exceptions and asks.

Per-skill patching would miss the next symptom.

### MVP-first ordering

Already a standing rule (see the `mvp-first-ordering` memory). It goes into the
v2 contract as an **ordering gate**, not as advice. Spotting future gaps is
fine; *dispatched workers* must be pointed at the MVP until there is one.

### Model and effort tiering

`orca orchestration worker-start` **already takes `--model <id>` and
`--effort <level>`.** Verified. So this is a pure contract change — no upstream
work.

Which lever matters, measured on one real gate review pass:

    input 84   ·   output 137   ·   cache-read 2,109,276

**Effort moves output tokens.** That is the 137. **Model moves the rate on all
2.1M.** So tier by model first, effort second.

Tier by **role**, not uniformly:

- **Scouts** keep high effort. Exploration is where thinking pays, and a scout
  exists to bring back judgement.
- **Builders** drop. They receive a spec with the information already in it; a
  builder re-deriving its own brief is the spec's failure, not the model's.

The upstream corollary: **v1.72.0 added independent reviewer and fixer harness
profiles** (#1016), so the same tiering is available *inside the gate*.

The deeper point C.C made, which outranks the tuning: **tasks stay static, so
specification quality is the real lever.** Higher-quality input → less
exploration → fewer tokens, at any model tier.

### Heartbeats

Heartbeats cost real tokens because each one re-enters the full context. Already
measured and already solved, in a memory that was nearly deleted:
`long-orchestration-waits-beat-polling` — *"measured 12x token cost for short
cycles; keep the wait at a full hour."*

Orca's long wait blocks without re-entering context. That is the script-shaped
mechanism C.C remembered from Firstmate. **Put a floor on the wait interval in
the contract.**

Corollary, from run-02: `sleep 570; no-mistakes axi status` is the polling
anti-pattern in the wild ([F-027](runs/run-02-findings.md)). `no-mistakes axi
run` blocks until a decision point or outcome — see §6, it needs a test.

### New gate behaviour v2 will meet and run-02 never saw

- **v1.69.0** added *live validation to the test gate*.
- **v1.75.0** added *prevent fake TUI live-validation passes*.
- **v1.70.0** added *ask before proceeding without a live-testable surface*.

Workers will hit these. A line in the v2 contract before the first dispatch.

---

## 3. Environment, permissions, and the external script

### Permissions

Either set the permissions properly, or run Lelouch and his agents with
`--dangerously-skip-permissions`. Note **PR #28 on `lelouch-harness`** — *"Cast
the permissions the workflow needs, not just the hook"* — is the surgical
version and is already in flight. Check which is further along before defaulting
to the blunt one.

Related: [F-052](runs/run-02-findings.md) — the force-push a gate-rebase
recovery requires is refused by Claude Code's auto-mode classifier. That is a
permissions problem wearing a gate costume, and it is *not* upstream's to fix.

### Auto-compact and auto-clear — an external script can do it

Lelouch cannot invoke `/compact` on himself; there is no tool for it. **But
`orca terminal send` exists** ("Send input to a live terminal"), so an external
script can push `/compact`, `/clear`, or a wake prompt into his terminal from
outside. That is the mechanism for the whole of §1's `britania-vitals` wake
story.

Two hard constraints, both agreed:

1. **Wait for the turn boundary.** `orca terminal wait` supports `tui-idle`.
   Injecting mid-turn is how state gets corrupted.
2. **`britania-restore` must be proven first.** Auto-clear with an unproven
   restore destroys whatever Lelouch had not written down, at the moment he is
   most loaded. Restore, then PoC, then let the script trigger it.

And the presence rule: **if C.C is at the keyboard, the script only warns** and
lets them do it manually. Automatic handling is for AFK.

---

## 4. Knowledge to promote out of Claude's memory

C.C's instinct was to delete `~/.claude/projects/…-weave-atlas/memory/` for v2
consistency. **Do not blanket-delete.** Of its 13 entries, only two are
weave-atlas-specific (`design-comes-from-external-team`,
`capability-needs-its-surface-flipped`). The other **eleven are harness facts**,
several independently confirmed as run-02 findings:

| memory | finding |
|---|---|
| `gate-finding-text-is-truncated` | F-111, arrived at twice, independently |
| `ship-gate-strands-commits` | the F-059 family |
| `gate-run-owns-the-branch` | rebase collisions |
| `regate-after-checks-passed-strands-fix` | F-087's neighbourhood |
| `gate-intent-size-limit` | >6KB `--intent` kills the run, exit 141 |
| `orchestration-send-type-status` | `note` invalid; `decision_gate` needs a worker-only token |
| `gate-timeout-two-outcomes` | check PID and HEAD before restarting |
| `long-orchestration-waits-beat-polling` | the 12x figure §2 relies on |
| `escalation-beats-ask-for-blockers` | F-101's neighbourhood |
| `lavish-shares-one-design-system-copy` | — |
| `cc-delegates-backend-judgement` | §4 decisions stay C.C's |

**That is the actual defect: eleven pieces of harness knowledge live in Claude's
private per-project memory instead of in the harness.** Every fresh `geass cast`
starts blind and relearns them at full cost. Deleting them makes v2 worse.

**Plan, agreed:** cross-check all eleven against run-02's findings; drop any
already marked fixed or superseded by a correction — *and* against no-mistakes
v1.75.1, since a memory recording a bug that upstream fixed is worse than no
memory; promote the survivors into a shipped harness-gotchas doc in the geass
payload (`docs/agents/`); **then** delete the memory directory. Consistency by
moving the knowledge, not by dropping it.

---

## 5. Considered and settled

### Graphify — conditionally in

Maps a project into a queryable knowledge graph instead of grepping files.

My first objection was wrong for the design C.C actually proposed. I argued a
shared graph over a codebase four builders rewrite in parallel is *a cache that
asserts* — the F-087 / F-108 failure family, a stale read stated as fact. But
C.C's model is per-worktree graphs, updated on merge, master holding the live
one. **That is git's own model and it defeats the objection.**

The residual is real but narrow: the ship gate **rebases** every branch onto
master before review, so each merge invalidates every other worker's graph. The
graph must regenerate **on rebase**, not only on merge — otherwise a worker
queries a graph describing a master that no longer exists.

So the open question is not correctness, it is **cost per regeneration**
(see §6).

### Ponytail — dropped

Claimed benefit is faster generation with fewer lines. Measured spend on a real
pass: 84 input / 137 output / 2,109,276 cache-read. **Generation is ~0.01% of
the bill.** Nothing that optimises emitted code touches it. C.C agreed to drop.

---

## 6. Open questions — none of these are answered

1. **Can a blocking wait re-attach to an already-running gate?**
   `no-mistakes axi run` is documented as *"blocking until the first approval
   gate, CI-ready point, or final outcome"* — but it **triggers** a run; it is
   not an observer API. `no-mistakes attach` exists but **opens a TUI**, which
   would hang an agent. So today there may be *no non-polling observer API*, and
   the `sleep 570` loop may be the only option for watching a gate you do not
   own.
   **How to test it safely:** throwaway branch, trivial diff, start a gate with
   `axi run`, then from a second terminal in the same worktree try to observe it
   without polling. The risk to avoid is a *duplicate run* — hence the throwaway
   branch. C.C flagged not knowing how to test this; that is the shape.
   Secondary conclusion, worth stating regardless: **Lelouch was polling a gate
   he did not own.** The worker owns its gate and reports. That is a contract
   fix independent of the API answer.

2. **What enforces "user-invocable, never model-invocable"?** `user-invocable`
   is a real frontmatter field (`quota-axi` sets it `false`). Whether the
   converse is *enforced* or merely discouraged by description wording is
   unverified. It matters: the four §1 skills are user-only for safety reasons.

3. **Graphify's regeneration cost per rebase.** Seconds → adopt as designed. A
   full project scan → the gate's rebase cadence makes it expensive. Measure
   before adopting.

4. **When to run `no-mistakes update`** (v1.64.0 → v1.75.1, eleven releases).
   Not during a live run: the update resets the daemon, which is **global**
   ([F-108](runs/run-02-findings.md)) and would hit every worktree at once.
   After run-02 closes, before v2 starts.

5. **Why Lelouch reached for `orca terminal send`.** C.C's global CLAUDE.md
   names it as the untracked handoff path they do not want used. He may have
   wanted it for something else entirely. Low confidence, worth asking if it
   recurs.

---

## 7. What is *not* a problem — do not fix these

**Lelouch probing `orca terminal send --help` after a `/clear`.** One
`--help | head -50` is roughly 200 tokens; loading the `orca-cli` skill guide is
thousands. He picked the cheap option correctly. The real signal is *why* he had
to: the `/clear` took the skill context with it. That is an argument for
`britania-restore`, not for a new orca-cli skill.

Useful primitive for restore: **`orca agent-context`** prints the entire
machine-readable command schema in one call — one call instead of N probes.

**Gate duration.** ~1h for a three-round review plus test/lint/push/pr/ci is
mostly real work. The *waiting pattern* is reducible (§2); the duration largely
is not. v1.70.0's *prepare dependencies once per run* helps a little.
