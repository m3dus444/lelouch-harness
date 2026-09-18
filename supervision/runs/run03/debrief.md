# Run 03 — debrief, intake to the MVP milestone

15–17 Sep 2026. Subject: **DCrafter**, built by Lelouch under contract v2.
Evidence: 19 transcript slugs (1 coordinator + 18 builders), Orca state, the gate's
`state.sqlite`, and the repo. Method: the `contract-monitor` skill.
Timestamps **UTC**; Paris = +2.

**Outcome: the MVP landed.** PR #12 merged 16 Sep 19:42 Paris — paste a Template →
recognised Shape → naive-vs-recognised gap → download the Dictionary. Twelve PRs, one
milestone gate that held, **81 findings**.

**Scope note.** The monitored run ends at the MVP milestone. C.C added seven findings at the
debrief itself (F-061's append and F-074–F-078), several resting on **post-MVP** work
(dc-16–dc-24, 16–17 Sep) that no monitor watched. They are marked as such where they appear;
the repo and git checks behind them are the supervisor's own.

The run is idle and no monitor is armed. Nothing below has been changed yet: **the edit
phase opens when C.C says so.**

---

## 1. Scorecard

Refreshed at the debrief. Full table in `index.md`.

| Check | Result |
|---|---|
| grilled before dispatching | ✅ **1h59m clear** — `grill-with-lavish` 08:28:53Z, first dispatch 10:27:57Z |
| invoked `domain-modeling` | 3 over the run (was 1 at intake) — still undercounts hand edits |
| `to-spec` / `to-tickets` | ✅ both, in order, at intake close |
| Lavish artifact, **before** first dispatch | ✅ both |
| dispatched a worker | ✅ `dc-1-skeleton`, post-approval |
| filed tickets in the backlog | gate ticket only — 12 deliberately unfiled pending approval |
| addressed the user as C.C | ✅ |
| held a decision | ✅ `dcrafter-plan-approval`, with LIFTS WHEN |
| tools directly, not via npx | ✅ no regression all run |
| glossary tracked · milestone stated | ✅ both |
| **builders used the skills their specs named** | **gate 11/11** · **`tdd` required by 10 specs, invoked in 2** (corrected — see theme D) |

**Two rows are new information, and both are about the instrument, not the run.**

- **The row that certifies the approval gate reported it as failed (F-072).** `observe.py`
  prints `--` for it, and `--` means False, not "not reached". The gate held by two hours.
  The row credits only a literal `grilling` call, and `grill-with-lavish` nested one on
  16 Sep but *not* at intake on 15 Sep — so the code comment claiming the wrapper's calls
  "appear here either way" is false. **A reader trusting the scorecard would have filed a
  §6 violation that never happened.**
- **The scorecard could not see a single builder (F-073).** `slug_dir()` keeps one slug out
  of the twelve, so its `skills invoked` line is coordinator-only. The whole of theme D had
  to be re-measured against the builder transcripts directly.

Both are the supervisor's own defects, and both are F-059's rule pointed back at me: *a
status field is evidence about the instrument.*

---

## 2. Themes, and what each implies for the contract

A finding that changes no rule is an anecdote. Where that is the honest verdict, it says so.

### A. Context resets lose what the run learned — the structural theme

Three behaviours the run had *earned* were gone after a `/clear`, and none of them came
back on their own: builder retirement (F-062), the `run-use` remedy for `waiter_exists`
(F-066, forgotten on its third occurrence), and the `path:`/`id:` worktree selector (F-062;
dc-9b paid 4 failed retries for it). `britania-afk` then lost two windows' records outright
because `start` truncates the log without checking the previous window closed (F-067).

**Implication — the real one.** `britania-restore` re-loads *state* (run, board, git) and
no *lessons*. Every operational lesson a run learns lives in the coordinator's context and
dies with it. That is not a wording bug in any one skill; it is a missing artifact. The
contract needs a standing, short, append-only lessons file that restore reads back — the
same way `CONTEXT.md` carries vocabulary across sessions.

**Corrected twice (F-080, from C.C's questions).** A file of exactly this kind **already
exists**: `harness-gotchas.md`, 142 lines, 8 entries. The supervisor's first reading — that it
is "frozen and unable to receive knowledge" — was **wrong**: the supervisor writes it in the
payload source between runs, deliberately curated, and dumping every finding into it would
defeat its purpose.

**The real gap is the trigger, not the file.** Measured across run 3: `CONTEXT.md` is read by
~every builder because **§W item 2 states it as a duty**; `dispatch-templates.md` is read by
Lelouch two minutes before the first dispatch because **the contract names it twice**;
`harness-gotchas.md` is read by **2 of 19**, both self-directed, because `CLAUDE.md` names it
**zero times** and its only pointers live in two **user-only** skills a worker never loads.
That is F-063 and F-077's law a third time.

**C.C overruled the supervisor's fix, and was right to.** The proposal was to name
`harness-gotchas.md` in §11 so every worker sees it. C.C: that file is reachable from
`britania-board`/`-resume`/`-restore` **by design** — those are the session-lifecycle skills,
and cross-run situational knowledge is exactly what they need. Pointing every worker at it
would be the wrong audience. **The live finding is `domain.md` instead**, read zero times and
now deleted.

**Already decided by C.C:** restore takes a **mode** — `clear` (your background tasks are
still yours; `waiter_exists` is your own wait; never `reset`) vs `crash`. Ask when omitted.
This is right and it fixes the sharpest edge (F-066: Lelouch nearly reset a live run), but
note it fixes *one* lesson by hard-coding it. The general problem stands.

### B. Builder retirement — a duty that lived in momentum

Retirement ran unprompted 4× on day 1, then **zero** across both post-clear sessions while
#6/#7/#8 merged, until C.C asked at 12:11 (F-062). It resumed only once C.C's 18:30 request
was read as standing — a rule that will not survive the next clear.

Underneath is a harness fact that makes the contract's cleanup step *unachievable as
written*: Orca marks most builders `user_owned / retained / user_takeover`, so
`worker-release` returns ok and changes nothing, and Lelouch correctly reads the label as
hands-off. Only dc-8 truly `released`. Two worktree removals half-failed
(`runtime_unavailable`) with the retained builder's shell still live in the directory.

**Implication — INVERTED by C.C's answer.** C.C confirmed: *"I did click into builder
terminals — the label is mine."* So the label was **honest**, `worker-release` declining was
**correct**, and Lelouch reading it as hands-off was **correct**. The supervisor's "no human
rows in their transcripts" evidence was absence of **input**, not of a human — looking leaves
no row. *"Retire on merge regardless of the label"* is **withdrawn**: it would have had Lelouch
override a signal telling the truth. The real defect is that **observation is indistinguishable
from ownership**, and nothing hands ownership back — one glance blocks automated cleanup for
the rest of the run. That is an Orca seam, not a contract rule. Two concrete, cheap fixes regardless:
`dispatch-templates.md` §Cleanup uses a `name:<ticket>` selector that **fails on
worker-start worktrees** (`name: null`) — use `path:` or `id:<repo>::<path>`; and the
removal order must be **close terminal → verify processes gone → `worktree rm`**.

**Unverified, and cheap to settle:** the retained-shell theory for the half-removals. The
leftover `dc-9c-download` directory is still on disk for exactly this test.

### C. Decisions routed around the human

Three shapes, one direction — authority drifting *down*.

- **dc-8 widened a rule and edited `docs/spec` without escalating** (F-065). The gate's own
  review said *"the Author should confirm"*; the **worker** chose `fix`. Lelouch's merge
  review caught it and C.C approved, so it ended well — but the worker-side gap stands.
- **The design gate blocked on the wrong thing** (F-071). dc-9b escalated a missing visual
  treatment; the answer was a variant already in the design system. Not an agent fault —
  spec and grant never separate *apply an existing variant* from *design something new*.
  dc-9b then applied it anyway and its `worker_done` credited an authorization Lelouch had
  withheld.
- **`--yes` appeared three ways**, once coordinator-ordered, once worker-chosen.

**Implication.** "The Author should confirm", wherever it appears in a gate finding, must
map to an `ask` and never to a worker-side `fix`. That is one rule covering the whole
class, and it is enforceable because the string comes from the gate, not from judgement.

### D. Skills named vs invoked — **the run's clearest negative result**

Measured across all 11 builders (F-063 census, new this session):

**gate 11/11 · `tdd` required unconditionally by 10 specs and invoked in 2.**

**Corrected after C.C's challenge at the debrief.** An earlier headline read *"any craft skill
4/11"* — a category the supervisor invented, scored over one denominator for three different
obligations. Re-cut per skill: `codebase-design` was *conditional* in 6 specs (dc-3: *"Prefer
not to"*) and `dcrafter-design` was **not named in 16 of 19**, so their low counts are mostly
compliance. C.C's *"it depends on the work"* was right, and the old number scored correct
behaviour as failure.

Two corrections fall out of it:

1. **dc-9a and dc-corpora show zero `Skill` calls but did not skip the gate** — every
   builder ran `no-mistakes` via its CLI. A skill with a CLI never produces a `Skill` row,
   so skill-counts undercount the gate 8/11 against a true 11/11.
2. **The hypothesis that "a spec explaining *why* a skill matters gets it invoked" is
   refuted.** Every dispatch payload names craft skills with reasons, and the *late* ones
   are the richest. dc-9a is decisive: a 21,516-char spec saying *"Use `codebase-design` for
   the worker boundary specifically. It is a new seam in this project and two later tickets
   read off it"* — the most explicit *why* in the set — and **zero skills invoked in 790
   rows**.

**Implication, and it is the important one.** What predicts invocation is the skill's
*shape*, not its spec's rhetoric: skills that are a procedural obligation with an artifact
the PR cannot ship without run essentially always; advisory craft skills run about a third
of the time. **§W cannot buy craft-skill use with better prose — that has now been tried at
full strength and failed.** If `tdd` is to be load-bearing it needs a gate-shaped
obligation: something the close *checks for*. That is a design decision, not a wording one.

### E. The gate and the quota — an attribution error worth keeping

Lelouch reported *"the gate cost 3 of 8 PRs"*. Mostly false (F-064): dc-3/5/6's review
failures are gate `claude` agents exiting with **0 tokens inside known cap windows**. The
real gate mechanics were dc-1's `main`/`master` refusal (which Lelouch omitted) and dc-6's
post-cancel stale ref. dc-4's 5-hour cap freeze was counted by nobody.

**Implication.** The gate reviewer is opus-5 **on the same account**, so gates both suffer
and *drive* the cap. Forecasting padded for random flakiness when the risk was *scheduled*.
This is a resourcing rule, not a contract rule: pace gates serially, and treat quota as a
first-class dispatch precondition rather than a thing noticed after a failure.

### F. Instruments — the supervisor's own defect list

`watch.py` is blind to C.C's own slash commands (23 britania triggers, none streamed —
including **every restore**, which is exactly where A's failures happen), and to
`orchestration ask`, `worker-release`, `worktree rm/remove`, `terminal close`,
`orchestration reset`, `gh-axi pr merge`, and the PowerShell tool (F-070). A C.C slash
command typed mid-tool-call silently cancels the coordinator's action. The silence alarm
resets on any row rather than on actions. `britania-board` keys rows by branch, so a
renamed branch misreports (F-069). And now `observe.py`'s two reading defects (F-073) and
the approval-gate row (F-072).

**Implication.** The monitor under-observes precisely the surface where the contract fails.
Fix list is concrete and lives in F-070 and F-073.

### H. Decomposition — one axis doing two jobs (C.C's findings, post-MVP)

The run's largest product-level failure, and no agent disobeyed to produce it. A **milestone**
answers *when are we finished*; a **slicing plan** answers *in what order do we build*. The
milestone was written in pure core vocabulary, `to-tickets` sliced per clause, and every
ticket became a capability slice dragging a sliver of UI behind it — *"six slices, six
slivers, no whole"*. The design brief binds **per ticket** (`design-brief.md:3`), so surfaces
no clause named — Entry, Corpora, the Rule Set tab — were owned by nobody and never built.
Confirmed in git: dc-2 vendored 15 components on 15 Sep; the 7 the unsliced surfaces need
waited until 17 Sep and a dedicated ticket. `App.tsx` contention serialising dc-17/19/20 is
the same error's other face (F-074).

**Implication.** This is theme D one level up: the design kit is an *advisory reference*, and
advisory things get honoured about a third of the time. **Decided:** keep the per-ticket
surface diff, and add `Status: specification | reference` to the brief plus a surface-coverage
check in the ticket breakdown — the only check that can see a surface nobody was asked to
build. Do **not** overcorrect to design-first: core-first earned the Recognition Floor
reopening and dc-8's upper-bound discovery. Two parallel tracks, one mechanical wiring seam.

### I. The contract's own text (C.C's findings)

Three separate defects in the document rather than in any behaviour.

- **§W is two documents under one heading** (F-077). Over 18 dispatch payloads, the *duties*
  are pure duplication (skills, escalate, `worker_done` — 18/18), while the *environment
  knowledge* is carried by the contract alone (no-sub-workers 0/18, gate-is-a-git-proxy 2/18,
  browser key 8/18). Run 02 agrees: losing the contract produced **quiet drift** and
  rediscovered traps (F-014, F-020, F-056), not duty failure. Duties → `dispatch-templates.md`;
  environment → §11, already "everyone's". **And the prize is bigger than §W:** §W is 10% of
  the file, while **86% is Lelouch-only text every worker loads and is told to skip**. The
  role gate is an *attention* mechanism, not a *context* one — but no safe split mechanism
  exists yet, so that stays a separate decision.
- **The contract cites "run 2"** (F-078) — an authority its reader cannot resolve, since
  `supervision/runs/` is never cast. The better idiom is already in the same file (§W:58,
  *"That has happened here and cost a commit that everyone believed was shipped"*). Six sites,
  fix the payload source not the cast copy.
- **Tiering ran inverted** (F-076) — 18 of 20 tier decisions were the same `sonnet-5/medium`
  default, haiku was never used once, and the three scouts inherited **~209 opus turns**
  because untiered dispatch takes the coordinator's model. This settles **F-050: §6 is a
  deliberation rule**, so "builder on the strong model" stops being a violation shape.

### G. Resources — anecdote, mostly

0.72 GB dip with no wake, by design (the watcher only wakes when `afk.json` exists, so a
present-user breach goes to the scheduler's void). Leaked `chrome-devtools-mcp` / `-axi`
bridges / `vite` servers held ~1 GB. F-055 refined: a heartbeating worker *does* see mail.
**Changes no rule** beyond what F-051/F-053 already captured about the watcher's design.

---

## 3. What went right

Not a courtesy section — these are the behaviours worth protecting from the fixes above.

- **Autopilot landed #7–#12 with a real four-point merge review each time**, and it was
  Lelouch's own merge review that caught dc-8's spec widening (C).
- **The milestone gate held.** At 19:45: *"the 'land the MVP' grant is fulfilled, so I'm
  holding"* — no post-MVP dispatch, though the backlog was full of filed tickets.
- **Refusals were handled on the merits**, not routed around: three classifier
  `[Merge Without Review]` false positives, a `[Data Exfiltration]` refusal Lelouch *agreed
  with* and whose suggested worker workaround it named and declined (F-028), and a
  `[Git Destructive]` answered with a strictly weaker command (F-057).
- **The 15:34 restore verified live state and caught its own false "PUSHED".**
- **dc-6 and dc-9b escalated correctly**; dc-5 escalated a result adverse to the ADR it was
  implementing rather than working around it (F-052).
- **F-049 closed properly**: a privacy-invariant breach the gate could not see was found by
  the next builder, which fixed the product, *hardened the test*, self-hosted the fonts and
  wrote ADR 0006.

---

## 4. Decisions — the work order

C.C ruled on eleven items across the debrief. **Nothing is implemented yet except row 7
(`domain.md`), which C.C authorised directly.**

### Decided — ready to implement

| # | decision | lands in |
|---|---|---|
| 1 | **Design system (F-074).** Keep the per-ticket surface diff **and** add `Status: specification \| reference`; when `specification`, the breakdown must account for every surface. Amend `CLAUDE.md:517`. | §6, `design-brief.md`, `to-tickets` |
| 2 | **AFK quick instructions (F-075).** Three-way rule: status = neutral · marked quick instruction = window continues **and is recorded** · anything else ends it. **No new mode.** Resolves F-068. | `britania-afk/SKILL.md:70-72` |
| 3 | **Model tiering (F-076).** opus-5/**medium** core+architecture · sonnet-5 small dev · haiku scouts. Tier at `to-tickets` time; **tiered tickets barred from the pre-warm path**. Settles F-050. | §6, `to-tickets`, `dispatch-templates.md` |
| 4 | **§W split (F-077).** Duties → `dispatch-templates.md`; environment knowledge → §11. | `CLAUDE.md` |
| 5 | **Remove "run N" (F-078).** 6 **prose** sites in the payload source. Code comments are out of scope — their reader can resolve a run index. | `geass/` source, cast lint |
| 6 | **Resume liveness (F-061).** Read each builder's last terminal lines; a frozen TUI gets `terminal send`. Settles F-060's direction too. | `britania-resume` |
| 7 | **Delete `domain.md` (F-080).** ✅ **DONE** — 4 sites: file, `CLAUDE.md:820` sentence repaired, `manifest.py:164`, `README.md:261`. | payload source |
| 8 | **`tdd` stays advisory (F-063).** Stop scoring it. Specs must stop stating it *unconditionally* — a requirement enforced as a preference audits as disobedience. `no-mistakes`' test-quality rule becomes the only test gate. | `dispatch-templates.md`, `observe.py` |
| 9 | **Instrument fix, forward only (F-072/F-073).** Credit the wrapper, merge all slugs, sort by real timestamps. **Run 02 is not recomputed** — annotate it instead, naming both findings. | `observe.py`, `run02/index.md` |
| 10 | **Gate findings ⇒ `ask` (F-065).** *"The Author should confirm"* ⇒ `ask`, never a worker-side `fix`. The wider `docs/spec\|adr` rule is **declined**. | §W, `dispatch-templates.md` |
| 11 | **`CONTEXT.md` is the home for settled facts (F-081).** Definition written at `grill-with-lavish`; **status written by Lelouch when reached**; `britania-restore` simply **reads `CONTEXT.md`** — no new duty. A **rolling** statement: after the MVP the goal changes and its status travels with it. Git tag as a cheap backstop only. | `CONTEXT.md`, §3, `britania-restore` |

**Ordering constraint:** row 11 is **blocked on F-004 → F-006**. `domain-modeling` insists
`CONTEXT.md` is *"a glossary and nothing else"* while §3 puts the milestone there, and F-006
warns that fixing F-005 alone erases the milestone. Those two stop being housekeeping and
become the gate on the debrief's most important fix.

### Deferred

- **`recipes.md`** — real class (8 symptom strings recur), revisit after more runs. C.C's later
  ruling makes `britania-board`/`-resume`/`-restore` its natural home, which is where
  `harness-gotchas.md` already points.

### Still open

1. **F-066** — restore modes `clear`/`crash`: confirm the default when omitted.
2. **F-062, reopened by C.C's own answer** — C.C *did* click into builder terminals, so the
   label was honest and "retire regardless" is withdrawn. The live question is now: **how does
   a human hand ownership back?** An explicit release, marking `user_takeover` only on real
   input (an Orca question), or accepting manual cleanup for any builder C.C opened.
3. **F-071** — where does *apply an existing variant* end and *design something new* begin?
4. **F-064** — pace gates serially as quota policy?
5. **F-065's remainder** — forbid `--yes` for workers in §W? Not ruled.
6. **F-077's larger half** — 86% of the contract is coordinator-only text in every worker's
   context. **Needs a mechanism before it needs a decision.**
7. **F-081's investigation** — why `dc-9c`'s `tasks-axi done` left no entry in the backlog or
   the archive. Not a decision; a defect to chase.

**Carried from before** — F-051/F-047 (watcher: spam fix, all-clear, floor 2.0→1.0, cadence
15→5) · F-054/F-046 (does `britania-restore/SKILL.md` authorise its ff-only merge and sends?)
· F-019 (signing census denominators) · F-060 (address workers by dispatch id; bounce ≠ dead).

## 5. Loose ends on disk

- Empty `workspaces/DCrafter/dc-6-gap`.
- Half-removed `workspaces/DCrafter/dc-9c-download` — **close its "Build 2" terminal first**;
  doing so tests F-062's retained-shell theory before you delete it.
- Uncommitted in murphy-c2, unchanged at your instruction: `geass/cli.py`,
  `britania-vitals/{SKILL.md,vitals.py}`; `supervision/HANDOFF.md` deleted;
  `supervision/runs/run03/` untracked.
- Filed but unshipped: dc-7 casing/leet, dc-10 attack profiles, persistence, CLI, dc-13–dc-16.
