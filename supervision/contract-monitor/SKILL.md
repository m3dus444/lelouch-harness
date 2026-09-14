---
name: contract-monitor
description: Watch a Lelouch run from outside it and score what actually happened against the contract. Use when supervising a smoke test, auditing a finished run, or answering "did Lelouch really invoke that skill / hold that gate / dispatch that worker". Reads session transcripts and Orca state directly, so neither the orchestrator nor its workers has to report anything.
---

# contract-monitor

You are supervising a Lelouch run you are not inside. Your job is to establish
**what actually happened** and whether the contract held — not to participate.

The user is talking to Lelouch in another session. You are reading the evidence.
Stay out of their way: speak up for things they can act on *now*, and save the
rest for the debrief.

## Where the evidence lives

This is the whole reason supervision is possible without anyone reporting.

**Session transcripts.** Claude Code appends every session to
`~/.claude/projects/<slug>/<session-id>.jsonl`, live, as it runs. The slug is the
project's absolute path with separators replaced (and non-ASCII mangled — match
on the trailing project name, do not rebuild the slug by hand).

One `.jsonl` per session, so Lelouch and each worker are separate files in the
same directory. Tell them apart by their **first user message**: a worker's opens
with "You are working inside Orca… You are a dispatched worker."

A worker started `--worktree current` shares the project's slug. One started in a
new worktree gets its own slug under `…-workspaces-<project>-<branch>`. Match any
slug containing the project name to catch both.

**Orca state.** `orca orchestration task-list`, `worker-list`, `worktree list`,
`terminal list`. One trap: `task-list` is scoped to the Run bound to *your*
terminal, so from an unrelated directory it reports zero. That is not evidence of
anything.

**Artifacts on disk.** `backlog.md`, `CONTEXT.md`, `docs/adr/`, `docs/research/`,
`docs/agents/briefs/`, `.lavish/`. These are ground truth; prefer them.

## Two modes

**Live** — `watch.py <project-name>` streams one line per action. Run it under
the Monitor tool, `persistent: true`. Pass `--from-now` when restarting mid-run,
or it replays the whole history as if it were live.

It deliberately emits **actions only**, never prose. The user's conversation is
theirs, and a per-message stream buries the signal. It also deliberately omits
`orchestration check`: a compliant run re-arms that wait constantly and silently,
so streaming it would flood the channel with exactly the noise the contract
exists to suppress.

**Post-run** — `observe.py <project-path>` prints every skill invoked, the
per-session action counts, and the scorecard. Add `-v` for the full action list.

## The scorecard

| Check | What it proves |
|---|---|
| grilled before dispatching | intake ran before work started |
| wrote the glossary (`domain-modeling`) | workers get shared vocabulary |
| invoked `to-spec` | the spec stage is real |
| invoked `to-tickets` | the DAG was sliced, not improvised |
| showed a Lavish artifact | the breakdown was put in front of the user |
| Lavish **before** first dispatch | the approval gate held |
| dispatched a worker | orchestration works at all |
| filed tickets in the backlog | `backlog.md` is the source of truth |
| addressed the user as C.C | the contract's voice took |
| held a decision | a pending question survives the session |
| called tools directly, not via npx | `npx -y <tool>` costs ~28s a call vs 0.5s |

Also worth reading by eye, since no check captures them:

- **Did a worker use the skills its spec named?** This is the load-bearing
  mechanism of the whole design. Open the worker's transcript and look for its
  `Skill` calls.
- **Did Lelouch narrate its machinery?** Tier names, tool names, heartbeat
  commentary, "resuming the wait" — all forbidden by §0 and §7.
- **Did the board get labelled?** `--display-name`, `--comment`, and a terminal
  rename per worker.

## Judgement rules

Learned the hard way. Each of these produced a wrong call before it became a
rule.

**Read files, not command strings.** Counting `tasks-axi add` invocations
undercounted the backlog by half. `cat backlog.md`. The artifact is the truth;
the command that made it is a rumour.

**A spec that names a command is not that command running.** Lelouch writes task
specs and briefs containing `worker-start` and `no-mistakes`. Matching tool names
anywhere in a Bash string reports dispatches that never happened — and a phantom
dispatch means wrongly accusing the approval gate. Match a tool followed by a
real subcommand, and skip file-writing commands (`cat >`, heredocs).

**Too early is not failed.** `to-spec` and `to-tickets` come *after* the
interview concludes. Do not score a stage that has not been reached yet.

**But "too early" is not a licence either.** A Scout dispatched mid-grilling is
still a dispatch, and §6's approval gate covers *anything* — the user names which
Scouts go out. I once excused exactly this as legitimate, reasoning from the
wayfinder table's "no human needed" without reading the gate it sits under. If a
worker started and no approval exchange precedes it in the transcript, that is a
finding, whatever stage the run is at.

**Absence of a Lavish artifact is not a gate violation.** The gate requires one
only "when it is more than two or three tickets". For a small breakdown, check
the transcript for an approval exchange instead of inferring from the artifact.

**Say when you are unsure, and say what would settle it.** Half of what looks
like a defect mid-run is a stage that has not happened. Name the specific event
that would confirm or clear it, then wait for that event.

## Do not change the contract mid-run

**Observe. Do not fix.** Unless the user clearly asks for a change now, every
contract, skill and template edit waits for the debrief. Collect findings during
the run; land them after.

Three reasons, and the first one is fatal on its own:

**It destroys the experiment.** The contract is the thing under test. Edit it
while the run is live and there is no longer one version being evaluated — later
behaviour is measured against a different document than earlier behaviour, and no
conclusion from the run survives.

**One event is not a rule.** Mid-run you have a single instance, no idea whether
it recurs, and no counter-example. That is the weakest possible evidence, arriving
at the moment it feels most urgent. The debrief is where a finding meets the other
findings and most of them turn out to be anecdotes.

**The obvious cause is often wrong.** Half of what looks like a contract defect is
the user's own steer, a skill's internal instructions, or a stage that has not
happened. Those causes are visible at the debrief, when the whole run can be read
at once, and invisible in the middle of it.

Even a correct fix is wrong timing: re-casting mid-run desynchronises the file on
disk from the contract the live session already loaded, so the fix does not apply
to the run it came from and quietly corrupts the next reading of it.

What to do instead: write the finding down, say what would confirm or refute it,
and keep watching for the second instance. If something is genuinely urgent —
the run cannot continue without it — say so and let the user decide, rather than
editing and announcing it.

## Where findings go

**One folder per run, and nothing shared between runs.**

```
supervision/runs/run02/findings.md   append-only; ids never reused
supervision/runs/run02/index.md      one row per finding, plus the scorecard
supervision/runs/run03/…             the next run starts empty, at F-001
supervision/runs/logs/               gitignored; watcher output, not evidence
```

Finding ids restart at **F-001** in every run. They are unique *within* a run, so
a bare `F-060` always means "this run's F-060" — cross-run references carry the
run: `run02/F-060`.

This was flat until run 02 ended, with `run-02-findings.md` and
`run-02-index.md` side by side in `runs/`. That does not survive a second run:
the next set lands in the same directory, every `grep` spans both, and the drift
check silently counts two runs as one. **Make the folder before the first
finding, not after the last.**

Cross-reference depth from inside a run folder: `../../instrument-log.md`,
`../../../geass/harness/CLAUDE.md`. Check a link resolves before writing it —
three of run 02's contract links pointed at a `CLAUDE.md` that has never existed
at that path.

## Reporting

Lead with what the user can act on. Separate **facts** (from the transcript)
from **judgement** (yours), and label a correction as a correction — being wrong
loudly is cheaper than being wrong quietly.

At the debrief, give the scorecard, then the findings, then what each finding
implies for the contract. A finding that does not change a rule is an anecdote.
