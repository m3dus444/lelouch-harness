# Run 03 — supervisor resume: **SHIPPING v3**

> **STATUS 18 Sep: the debrief is CLOSED and v3 is fully specified.**
> Scorecard refreshed → debrief written → C.C's own findings folded in → every decision ruled.
> **The next job is implementation**, in the shipping order below. One item remains open and it
> does **not** hold the release (F-077's larger half — it needs a mechanism, not a decision).
>
> **Nothing is implemented except `domain.md`'s deletion**, which C.C authorised directly.

**Ledger: 81 findings** (`grep -c '<!-- F-[0-9]' findings.md` = `grep -c '^| F-[0-9]' index.md` = 81).

## Read in this order

| file | what it is |
|---|---|
| **`.lavish/v3-change-list.html`** | **the work order** — 40 changes by artifact, with what each implies. Review session ended by C.C; do **not** reopen it uninvited. |
| `debrief.md` | themes A–I, the scorecard, and what each finding implies |
| `index.md` | one row per finding, with every ruling appended |
| `findings.md` | full detail; corrections append rather than overwrite |

---

## Ship in this order

**0 · BACK-PORT FIRST — this is the one that can be silently skipped.**

Everything Lelouch landed at C.C's direction went into **DCrafter's cast copy**. The cast is
one-way, so `geass/` never saw it. Measured by diffing `geass/harness/` against `DCrafter/`:

- **B1** — §6 design-gate narrowing, 29 lines → `geass/harness/CLAUDE.md`
- **B2** — the `Visual work:` block, 12 lines → `dispatch-templates.md`
- **B3** — Scout "scratch files count", 2 lines → `dispatch-templates.md`
- **B5** — **source-only bug**: `dispatch-templates.md:111` still tells Scouts to render through
  `lavish` while the same spec demands ZERO file changes. **Do not delete the `lavish` line**
  (that was the wrong fix, twice). Widen the permitted outputs instead:
  `docs/research/<slug>.md` **and** an optional `.lavish/<slug>.html`, zero changes elsewhere,
  scratch outside the repo.
- **B4 — DROPPED.** `design-gate-after-the-mvp.md` is *not* back-ported: it records a framing
  C.C withdrew and bakes it into its filename.

**1 · C7** — milestone definition moves to a numbered **MVP ADR**; `CONTEXT.md` stays a pure
glossary; `domain-modeling` untouched. **No `Status:` field on the ADR.**

**2 · C6 + S5** — Lelouch **derives** whether the milestone is met by reading the MVP ADR
against the done tickets (`backlog.md` *and* `done-archive.md` — prune moves them). Restore
reads the **whole project state**, not one fact.

**3 · Everything else** — independent of each other.

**4 · Cast + commit.**

---

## Every ruling, compact

**Design system.** Keep the per-ticket surface diff **and** add
`Status: specification | reference` + a surface-coverage check — but the check is **vacuous, not
failing, when there is no UI kit** (there may be none; naming one is C.C's own act).

**Design gate (restated by C.C, not indexed to the MVP).** Blocks when **both**: no design
system exists for workers to follow, **and** C.C has not said Lelouch should produce one. Plus:
the thing cannot be *composed* with the existing system. *The MVP is a milestone, not a mode.*

**AFK.** Three-way rule replaces *"any message ends it"*: status command = neutral · marked
quick instruction = window continues **and is recorded** · anything else ends it. **No new mode.**

**Tiering.** opus-5 / **medium** for core + architecture · sonnet-5 small dev · haiku scouts.
Decided at `to-tickets` time; **tiered tickets barred from the pre-warm path**.

**§W split.** Duties → `dispatch-templates.md` (already 18/18 in payloads). Environment
knowledge → **§11**, already "everyone's" (no-sub-workers is in **0/18** payloads — the contract
is its only carrier).

**`tdd`** stays advisory; stop scoring it; stop stating it unconditionally in specs.

**Instrument.** Fix `observe.py` forward only; **annotate run 02, do not recompute it.**

**Gate findings.** *"The Author should confirm"* ⇒ `ask`, never a worker-side `fix`. The wider
`docs/spec|adr` rule was **declined**.

**Retirement.** *"A builder you opened is yours to clean up"* — and Lelouch **says so** rather
than silently skipping it.

**Restore mode.** **Ask when omitted — never infer.**

**Quota.** A **dispatch precondition**; gates stay parallel.

**`harness-gotchas`.** Two shells, two filesystem views (Git-Bash vs native Windows). **WSL is a
per-project ADR decision, never a default** — 2 of the 3 failures involved no WSL at all.

**Dropped / downgraded:** F-071 (design-gate line — watch run 04) · F-065's `--yes` strand
(anecdote; no run-03 harm traces to it) · the stale `blocked-by` · `dc-9c`'s "lost closure"
(**withdrawn — no such defect**).

---

## Still open — one item

**F-077's larger half.** 86% of the contract is coordinator-only text in every worker's context.
Per-worktree split is blocked (workers are worktrees of the same repo); untracking is run 02's
failure; a skill makes the prime directive advisory (F-063: ~⅓ uptake). **Needs a mechanism
before it needs a decision.**

---

## Traps for the shipping session

1. **Fix the payload source, never the cast copy.** F-025 bit twice in this run, in both
   directions. `geass/` is the source; `DCrafter/` is a cast.
2. **A deletion is not one edit.** Removing `domain.md` took four: the file, the `CLAUDE.md:820`
   sentence *repaired* (not truncated), `manifest.py:164`, `README.md:261`. **The manifest entry
   is the one that matters** — without it a file keeps shipping regardless of the source.
3. **Never pipe `lavish-axi poll` through a filter.** Delivery *consumes* the response, so a
   `grep` destroys the feedback. This happened, and C.C's message was lost. Use
   `… | tee "$SP/poll-last.txt" | tail -N`, then read the tee'd file — background task output
   files keep only a tail and truncate the head.
4. **Never conclude absence from a truncated search.** `grep … | head -8` produced a false
   "dc-9c was never recorded", which became a headline in F-081 before C.C's question exposed it.
   The entry was at line 500.
5. **A remedy inherited from a finding is not verified by the finding existing.** B5 carried
   F-025's fix forward for a day before anyone asked whether deleting the capability was right.
6. **Do not coin a category and then score against it.** "Craft skills" and "shell boundary"
   were both the supervisor's inventions; both produced wrong conclusions until C.C asked what
   they meant.
7. **Timestamps in transcripts are UTC; Paris = +2.**
8. **Run 03's contract-v2 measurements close at `d9608a6`.** §6 and `dispatch-templates.md` were
   edited mid-stream at C.C's direction (F-039: a directed action is not a violation), so the
   next run measures a different document and must not be compared as continuous.

## Environment changes already made

- `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1` (User scope) — the reaper killed the review
  loop five times, once at 3.59 GB free of 15.6 GB.
- `LAVISH_AXI_NO_OPEN=1` (User scope) — stops Brave launching (23 processes, ~960 MB). Open
  artifacts in Orca's browser instead. `lavish-axi <file>` opens a browser; `lavish-axi poll`
  never does.

## Leftovers on disk

Empty `workspaces/DCrafter/dc-6-gap`; half-removed `workspaces/DCrafter/dc-9c-download` — close
its terminal first, which also tests F-062's retained-shell theory, still **unverified**.
