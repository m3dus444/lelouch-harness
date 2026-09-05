# Dispatch templates

How Lelouch turns a ticket into a supervised worker. Fill a template in — do not
improvise a spec. The spec is the only reliable mechanism for making a worker
reach for the right skill (`CLAUDE.md` §6).

**Clear both gates in `CLAUDE.md` §6 before anything here runs:** the user has
approved the ticket breakdown, and — if this project has a user interface — a
design pass exists for any styled-UI ticket. Silence is not approval.

Load the orchestration guide once per session before dispatching:

```
orca skills get orchestration
```

## Naming, so the Orca board stays readable

Every dispatch sets three labels. They are what the user sees in the workspace
list without opening a terminal, so they are not optional.

| Field | Value | Set by |
|---|---|---|
| Worktree `--name` | the ticket id, e.g. `auth-session-q1` | `worker-start --name` |
| `--display-name` | `[Build] short ticket title` | `worker-start --display-name` |
| `--comment` | current state, one short line | `worker-start --comment`, then updated by the worker |
| Terminal title | `Build 1 - Scaffold` | `orca terminal rename` after dispatch |
| `--workspace-status` | board column | `orca worktree set` |

Prefix display names with the shape — `[Scout]`, `[Build]`, `[Fix]` — so a glance
at the board shows what kind of work is in flight.

Orca's default terminal title is `worker-<task_id>`, which tells the user
nothing. That id is **cosmetic** — Orca routes by `dispatchId` and terminal
handle, so renaming the tab breaks nothing. Number each shape within the session:

```
orca terminal rename --terminal <handle> --title "Scout 1 - Prior art" --json
```

Board status transitions Lelouch owns:

| When | Status |
|---|---|
| Ticket queued, not dispatched | `todo` |
| Worker dispatched | `in-progress` |
| `worker_done` succeeded, PR open | `in-review` |
| PR merged, worktree releasable | `completed` |

```
orca worktree set --worktree name:<ticket-id> --workspace-status in-review --json
```

Workers update `--comment` themselves at checkpoints (`CLAUDE.md` §W.3); Lelouch
owns the status column.

## Spec skeleton

Every spec, whatever the shape, states these five things. Write them in the
vocabulary of `CONTEXT.md` — the worker never saw the conversation that produced
the ticket.

```
Ticket: <id> - <title>

Context:
  <2-4 lines: what exists now, why this is wanted. No implementation detail.>

Do this:
  <the end-to-end behaviour to deliver, from the user's perspective>

Skills to use:
  <named, in order>

Done means:
  <observable acceptance criteria, not "the code is written">

Ship gate:
  <no-mistakes | a report file | nothing>
```

## Scout

Investigation only. Shares the current checkout because it does not write code.

```
orca orchestration task-create \
  --task-title "<short title>" \
  --display-name "[Scout] <short title>" \
  --spec "<filled skeleton>" --json

orca orchestration worker-start --task <task_id> \
  --worktree current --agent claude \
  --display-name "[Scout] <short title>" \
  --comment "dispatched" --json
```

Spec body:

```
Skills to use:
  Use the `research` skill. Investigate against primary sources, not memory.
  Render any comparison or report for the user through `lavish`.

Done means:
  A cited Markdown report at docs/research/<slug>.md.
  ZERO changes to any other file. You are read-only outside that report.

Ship gate:
  None. Report the file path in your worker_done body.
```

## Build

One vertical slice. Own worktree because it needs its own branch.

```
orca orchestration task-create \
  --task-title "<short title>" \
  --display-name "[Build] <short title>" \
  --spec "<filled skeleton>" --json

orca orchestration worker-start --task <task_id> \
  --worktree new-top-level --name <ticket-id> --setup run --agent claude \
  --display-name "[Build] <short title>" \
  --comment "dispatched" --json
```

Spec body:

```
Skills to use:
  Use the `implement` skill to drive the work.
  Use `tdd` at the seams named below - failing test first, then the code.
  Use `codebase-design` if you need to place a new seam.
  Close with `prod-review` against this ticket. Do NOT also run a standards
  or lint review; the no-mistakes gate owns that axis.

Seams to test at:
  <the highest existing seam, named. Prefer one.>

Done means:
  <acceptance criteria as observable behaviour>
  Tests pass. Typecheck clean.

Ship gate:
  Run `no-mistakes` with this ticket's text as --intent, on a feature branch.
  Report the PR url in your worker_done body.
```

## Fix

A specific defect. Own worktree, own branch.

```
orca orchestration task-create \
  --task-title "<short title>" \
  --display-name "[Fix] <short title>" \
  --spec "<filled skeleton>" --json

orca orchestration worker-start --task <task_id> \
  --worktree new-top-level --name <ticket-id> --setup run --agent claude \
  --display-name "[Fix] <short title>" \
  --comment "dispatched" --json
```

Spec body:

```
Skills to use:
  Use the `diagnosing-bugs` skill. Follow its loop in order: build a feedback
  loop that goes red on THIS bug, minimise, hypothesise, instrument, fix.
  Do not jump to a fix before you have a reproduction.
  Use `chrome-devtools-axi` if reproducing needs a real browser.
  Use `tdd` to lock the fix with a regression test.

Reported symptom:
  <verbatim, including any error text>

Done means:
  A test that failed before your fix and passes after it.
  The reproduction is described in your worker_done body.

Ship gate:
  Run `no-mistakes` on a feature branch. Report the PR url.
```

## The supervised loop

Create the Run and every independent Task first. Start **all** independent
workers before the first wait — starting one, waiting, then starting the next
serialises work that should be parallel.

```
orca orchestration run-create --objective "<the user's goal>" --json
orca orchestration task-create --spec "<A>" --json
orca orchestration task-create --spec "<B>" --json          # --deps for edges
orca orchestration worker-start --task <A> ... --json
orca orchestration worker-start --task <B> ... --json
```

Then wait — **backgrounded**, never in the foreground (`CLAUDE.md` §7):

```
orca orchestration check --wait \
  --types worker_done,escalation,question --timeout-ms 900000 --json
```

Pipe stdout only. `--wait` writes keepalive lines to stderr, and merging the
streams breaks any JSON parser with "Extra data: line 2".

On each Delivery, process **every** message before acknowledging:

| Message | Do |
|---|---|
| `question` | `orca orchestration reply --id <msg_id> --body "<answer>"` |
| `escalation` | Raise to the user (`CLAUDE.md` §4). Do not decide alone. |
| `worker_done` | Close the ticket, set the board status, then release |

```
tasks-axi done <ticket-id> --pr <url>          # or --report <path>
orca worktree set --worktree name:<ticket-id> --workspace-status in-review --json
orca orchestration worker-release --dispatch <dispatch_id> --json
orca orchestration check --ack <delivery_id> --wait --types worker_done,escalation,question --timeout-ms 900000 --json
```

Release after **both** succeeded and failed reports. Release is cleanup, not
cancellation — it closes only that dispatch's agent terminal.

## Mid-flight

| Need | Command |
|---|---|
| Amend a live worker | `orca orchestration send --to dispatch:<id> --subject "Course correction" --body "<guidance>" --json` |
| See what a worker is thinking | `orca orchestration worker-read --dispatch <id> --limit 50 --json` |
| What is still running | `orca orchestration worker-list --terminal-state active --json` |
| Stop one worker | `orca orchestration worker-stop --dispatch <id> --json` |

Amend by mail, not by typing into the worker's terminal. Mail arrives on the
worker's next `orchestration check` and lands cleanly mid-task.

## Recovery

Never release a worker because of a timeout, an idle TUI, or a missing heartbeat.
A `check --wait` timeout or `{count:0}` is a checkpoint; tasks routinely run
15–60 minutes.

| Symptom | Action |
|---|---|
| `worker-show` says `ready` | Keep waiting, or read bounded output |
| Proven `failed` / `stopped` | `worker-start --task <t> --retry-of <id>` with an explicit `--worktree` and `--agent` — retry does not inherit placement |
| `outcome_unknown` | `worker-stop` and inspect, or `worker-abandon` accepting that resources may still be live |
| Two failures on one ticket | Escalate to the user before the third (Orca circuit-breaks at 3) |

## Cleanup

Once a PR is merged, set the board and remove the worktree — they accumulate
otherwise:

```
orca worktree set --worktree name:<ticket-id> --workspace-status completed --json
orca worktree rm --worktree name:<ticket-id> --force --json
```
