# Run 2 — weave-atlas — findings log

Live notes for the debrief. Nothing here has been applied to the contract; the
run is testing master at `f16f2f6` (#23) unmodified.

## Confirmed working — first observations, not re-runs

| What | Evidence |
|---|---|
| **Pre-warm dispatch (#19)** | `terminal create` → `wait --for tui-idle` → `worker-start --terminal`, twice, 19s and 24s, zero retries. Run 1: 5 `task-create`s, 4 failed dispatches, 3 orphans. |
| **Spec injection** | 3 confirmations — both scouts reached for `research` unprompted; scout 1 also reached for `lavish`. Both named in their specs. |
| **§7 wait discipline** | One backgrounded `--wait --types worker_done,escalation,question --timeout-ms 3000000`. On `worker_done`, went straight to `--ack`. No bare `check --run`; run 1 burned 331s on exactly that. |
| **Captain-hold lifecycle** | `wa-design-opens` and `wa-engine-strategy` both went hold → user decided → unhold → Done. First time the release half has ever been seen. |
| **Holds sharpen with evidence** | `wa-engine-strategy` was rewritten in place as the scout reported: "metered API" became "705 requests, 4–19 min, 7% of daily budget for the flagship search". Lelouch then recommended reversing its own live-first position. |
| **`hold-kind: future`** | A deferral (`wa-ship-both`, "revisit once both exist") kept distinct from a decision needing the user. Not something the contract prescribes — Lelouch's own distinction. |
| **Routing fix (#23)** | `grilling` called directly. Run 2's first session died on the refused `grill-with-docs` wrapper; after re-cast, clean. |
| **Worker §W compliance** | Heartbeats typed `heartbeat` (so the filtered wait sleeps through them), board `--comment` updated at checkpoints, report written to the single file its spec allowed. |
| **Voice** | "C.C" throughout, fresh project, no contamination. |

## Defects

**`worker-release` has never run — finished workers stay open forever.**
Zero occurrences across both runs. Scout 1 sat live for 5+ hours after
`worker_done`. Cause: `dispatch-templates.md:231` puts release in a block whose
middle line is `orca worktree set --worktree name:<ticket-id>` — a Build-shaped
command addressing a worktree by ticket name, which a Scout on `--worktree
current` does not have. The block reads as inapplicable and the release goes with
it. Not a regression: it has never once executed.

**`tasks-axi done --report` path mismatch loses the artifact link.** *(PR #25)*
Contract says `--report <path>`; the tool validates `data/<id>/report.md`. The
obvious recovery — drop the flag, close the ticket — leaves a 46 KB report linked
from nowhere, contradicting "backlog.md is the source of truth".

**The npx habit is taught by the skills.** *(PR #25)*
`prototype`, `improve-codebase-architecture` and `to-tickets` each instruct
`npx -y` in their own bodies. That is why scouts called `lavish-axi` directly
while the coordinator did not — the scouts' skills never told them otherwise.
Measured: direct ~1.2s, `npx --no-install` ~4s.

**`worker-start` is still piped through `grep`.**
The contract says not to, precisely because the pipe eats the exit code. Harmless
while dispatches succeed — and it is the exact habit that made run 1's failures
invisible. Untested here because nothing failed.

**The harness was committed into the product repo.** *(fixed)*
Lelouch pushed 61 files to `github.com/m3dus444/weave-atlas`, of which **50 were
`.claude/skills/`** -- 19 vendored third-party skill packages, 82% of a new
product repo.

Not Lelouch's doing, and `.gitignore` was never edited: `GITIGNORE_ENTRIES` had
exactly one line, `.lavish/`, and `geass cast` ended by printing "Commit it, so
the contract is versioned with the code it governs." The harness instructed the
commit. Versioning your own contract is at least a defensible choice; dragging 19
skill packages along with it is a consequence nobody chose.

Fixed at C.C's request: geass now ignores `.claude/`, `/CLAUDE.md`, `/AGENTS.md`,
`/docs/agents/` and `/backlog.md`; the cast report no longer tells you to commit
the contract; and §1 says the harness is tooling, respect `.gitignore`, never
`git add -f` or a blind `git add -A`. `CONTEXT.md` and `docs/research/**` stay
tracked -- they are project knowledge, not tooling. A fresh cast now leaves only
`.gitignore` trackable. **Not re-cast into weave-atlas: that waits for the run to
end.**

The already-pushed files stay tracked until untracked explicitly -- `.gitignore`
does not apply retroactively.

## Unproven — do not act on these

**Prototype: build vs dispatch — still one instance.** I promoted this to a
pattern on the strength of the missing README, then C.C said the README was down
to a misspelled prompt of their own. So the second instance evaporated and this
goes back to where it was: one ambiguous event. Recording the retraction because
promoting it was the more interesting mistake -- I found a second instance
quickly *because I was looking for one*.

C.C asked for prototyping "in the meantime",
signalling parallelism; Lelouch built it itself and blocked. But C.C used the
word "prototype", and the `prototype` skill's own body tells the builder to open
the artifact and poll for the reaction. Plausible causes: the contract, the
skill's body, or a reasonable reading of the request. One instance. C.C's test is
the right one — if the user's steer produced the behaviour, it is not a contract
defect.

**The approval gate's proactive half.** Both scouts were requested by C.C
("you can send the scout", "I would like to do some research on..."), so the gate
has never been tested in the direction that matters. 2/2 user-initiated is a
pattern, but the innocent reading — C.C is decisive and gets there first — fits
equally. What would settle it: a decision point where the user stays quiet.

**Not a defect: the Orca GUI nesting.** Scout 2 briefly rendered indented and
smaller beneath Scout 1, then promoted itself to a sibling. `terminal list` shows
no parent field at any point — identical `worktreeId`, distinct `tabId`s. A
startup render state, not hierarchy. Worth recording because if it had *not*
resolved, it would have been real.

**Two pipeline stages were skipped, and it may not matter.**
Full skill timeline: `grilling` → `prototype` → `to-tickets`. §3's Full tier
prescribes `grilling` + `domain-modeling` → `to-spec` → `to-tickets`. So
`to-spec` never ran, and `domain-modeling` never ran either -- yet `CONTEXT.md`
exists with a glossary and settled decisions, written by hand.

The innocent reading is strong: the interview ran ~20 hours across two Lavish
artifacts, four resolved captain-holds, a decisions document and two research
reports. The spec plausibly already existed in `CONTEXT.md` and
`decisions.html`, and `to-spec` would have re-derived what was written down.

What settles it is the output, not the process: if `to-tickets` produces
well-formed, dependency-ordered tickets, the stages were redundant here and the
pipeline is over-specified for a long interview. If the tickets are vague or
mis-ordered, the skip cost something. Read the backlog before judging.

## Monitor bugs found while watching *(PR #24, #25)*

Each caused a misreport to C.C before it was caught.

- **Refused skills counted as invocations.** Scored `PASS wrote the glossary`
  when `domain-modeling` was never invoked — the refused `grill-with-docs` was
  accepted as a stand-in for the skill it failed to reach. A run whose whole
  problem was that it could not invoke the skill scored as though it had.
- **`worker_done` streamed as generic "mail".** The worker chains
  `worktree set && orchestration send --type worker_done`; the pattern loop broke
  on the first match, with `send` ordered before `worktree set`, and truncation at
  90 chars hid the type. The most important event of the run nearly went unseen.
- **`--help` counted as the command it documents.** `tasks-axi add --help`
  streamed as a filed ticket — a phantom ticket on the board *before* the
  approval gate that must precede it.
- **`npx --no-install` flagged as a defect.** It cannot fetch, so it is not the
  unbounded cold-registry case. Crying wolf on the benign form teaches the
  supervisor to ignore the marker on the real one.
- **`--` meant both "failed" and "not yet".** The scorecard was making the
  premature judgement the skill's own rules forbid. Now `n/a`.

## Process note

C.C stopped me mid-run for shipping contract edits off single observations. The
contract is the experiment; editing it live means later behaviour is measured
against a different document than earlier behaviour. Now written into the
`contract-monitor` skill: observe, do not fix — collect findings, land them at the
debrief.
