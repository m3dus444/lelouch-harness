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

Workers update `--comment` themselves at checkpoints — it is one of the standing
duties below; Lelouch owns the status column.

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

Model:
  <the tier from `CLAUDE.md` §6, named per ticket at `to-tickets` time>

Your duties:
  <the standing block below, verbatim>
```

A ticket that names a `Model:` **cannot be pre-warmed.** `terminal create` takes
no `--model`, and Orca refuses `--model` together with `--terminal`, so the
worker silently inherits whatever the tab was already running. Dispatch it with
`--agent` and `--model` on `worker-start` and pay the boot race instead.

## Standing duties

Every spec carries this block verbatim. It is the contract for a dispatched
worker — the payload is the only thing a worker reliably reads, so this is where
the duties live rather than in a section of `CLAUDE.md` addressed to no one who
opens it.

```
Your duties:
  Use the skills named above. They were chosen deliberately; if you substitute
  your own approach, say so.
  Read CONTEXT.md and any relevant docs/adr/** before naming things. You did
  not see the conversation that produced this ticket, and the glossary is the
  vocabulary you share with it.
  Report progress on your card at meaningful checkpoints, so your state is
  visible without opening your terminal:
    orca worktree set --worktree active --workspace-status in-progress --json
    orca worktree set --worktree active --comment "<short state>" --json
  Escalate a blocker; `ask` only what can wait. `orca orchestration ask` times
  out in minutes while the coordinator waits on the hour, so an ask that gates
  your work expires into your own judgement and you proceed on a decision
  nobody made. Anything that stops you uses --type escalation.
  Do not dispatch sub-workers. Nested depth is 1. Do the work yourself; do not
  route around nested_worker_depth_exceeded.
  Report exactly once when done, with an honest outcome:
    orca orchestration send --type worker_done --outcome succeeded|failed \
      --task-id <id> --dispatch-id <id> --subject "<status>" \
      --body "<what changed, what remains>" --files-modified "a,b" --json
  Never encode failure only in prose. --outcome failed is not a disappointment;
  a false succeeded is a real problem. And `succeeded` means the work is on the
  remote, not that a step went green: check `git log origin/<branch> -1`
  against your own HEAD before you claim it. A gate can pass and a PR can show
  green while the commit sits only in your worktree.
  On wake, say which ticket you are on and resume it. A worker that wakes and
  does nothing is indistinguishable from a dead one.
  A report you link must exist where you say it does. Verify the path after
  writing it — this failure mode reports success, so the link is worth only
  what the check behind it is worth.
```

## Scout

Investigation only. Shares the current checkout because it does not write code.

```
orca orchestration task-create \
  --task-title "<short title>" \
  --display-name "[Scout] <short title>" \
  --spec "<filled skeleton>" --json

orca terminal create --worktree current \
  --title "Scout <n> - <short title>" --command {{AGENT}} --json

orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 90000

orca orchestration worker-start --task <task_id> \
  --terminal <handle> --worktree current --json
```

Warm the terminal first so the spec cannot lose the boot race, and name the tab
at `terminal create` — Orca rejects `--display-name` and `--comment` on
`--worktree current`. Read the reply: `"state": "ready"`, `"stage":
"input_accepted"`. Never pipe it.

Spec body:

```
Skills to use:
  Use the `research` skill. Investigate against primary sources, not memory.
  Render any comparison or report for the user through `lavish`.

Done means:
  A cited Markdown report at docs/research/<slug>.md.
  Optionally a Lavish artifact at .lavish/<slug>.html presenting it.
  ZERO changes to any other file — those two paths are the only writes you
  may make.
  Scratch files count. Write intermediates to a temp directory outside the
  repo, never beside the report.

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
  --worktree new-top-level --name <ticket-id> --setup run --agent {{AGENT}} \
  --display-name "[Build] <short title>" \
  --comment "dispatched" --json
```

Spec body:

```
Skills to use:
  Use the `implement` skill to drive the work.
  Use `tdd` where the seam earns it - failing test first, then the code at
  the seams named below. It is advisory: `no-mistakes`' test-quality rule is
  the one that binds.
  Use `codebase-design` if you need to place a new seam.
  Close with `prod-review` against this ticket. Do NOT also run a standards
  or lint review; the no-mistakes gate owns that axis.

Visual work:            <only when the ticket changes what a person sees>
  Build from the project design system - its tokens, its components, its
  guidelines. Use a component that already exists rather than restyling one
  locally, and take every colour, space and type size from the tokens rather
  than picking a number. You are not waiting for a mock and you do not need
  one: following the system IS the design, per CLAUDE.md §6.
  If the ticket has a signed-off design for its surface, name it here and it
  wins over your own judgement where the two differ.
  If you find yourself inventing a look the system does not cover, that is a
  design question rather than a styling choice - send an escalation instead of
  deciding it.

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
  --worktree new-top-level --name <ticket-id> --setup run --agent {{AGENT}} \
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
  Lock the fix with a regression test - that part is required. Reach for
  `tdd` to write it where the seam earns it.

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
otherwise. **Order matters, and so does the selector.**

**Close the terminal first, then check nothing is still running in the
directory, and only then remove the worktree.** Removal de-registers from Orca
and git *before* it deletes, so a delete that fails partway leaves both
registries correct and the directory invisible to both. Two half-removals in one
run left exactly that behind. A worktree can also be held open by a process
started inside it — the ship gate's daemon is global and outlives the shell that
launched it.

**`name:` does not select a worktree that `worker-start` created.** It is null on
those, so the obvious cleanup command cannot work and fails in a way that looks
like a transient error; one ticket spent four retries rediscovering that. Select
by path instead, or by the fully qualified form:

```
orca terminal close --terminal <handle> --json
orca worktree set --worktree path:<path> --workspace-status completed --json
orca worktree rm --worktree path:<path> --force --json
```

`id:<repo>::<path>` works wherever `path:` does, and is the unambiguous form when
two repos have a worktree at the same relative path.
