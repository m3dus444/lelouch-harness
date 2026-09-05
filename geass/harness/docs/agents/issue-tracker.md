# Issue tracker: tasks-axi (local) + GitHub (delivery)

This repo splits the tracker in two, on purpose:

- **`tasks-axi` owns the backlog.** Tickets, blocking edges, holds, and the ready
  queue live in `backlog.md` at the repo root. This is the **single source of
  truth** for what work exists and what is dispatchable.
- **GitHub owns delivery.** Branches, pull requests, and CI live at
  `{{REPO}}`. A ticket links to its PR; the PR never replaces the ticket.

Orca orchestration Tasks are a third thing and are **not** a tracker: they are
ephemeral per-dispatch execution state. When a worker reports `worker_done`, the
owning ticket in `backlog.md` must be closed. If Orca state and `backlog.md`
disagree, `backlog.md` is right.

Never hand-edit `backlog.md` for state, dependency, or hold changes — drive it
through the CLI so the ready queue stays correct.

## Conventions

- **Ticket id**: a short slug, e.g. `auth-session-q1`. Pass `--mint` to have one
  minted from the title instead of inventing it yourself.
- **Kind** maps onto the dispatch templates in `dispatch-templates.md`:
  - `--kind scout` → investigation only, no code changes, lands a report
  - `--kind ship` → a vertical slice that ends in a PR
  - `--kind docs` → documentation and decision records
- **Repo tag**: pass `--repo {{PROJECT}}` so multi-repo backlogs stay filterable.
- **Blocking** is a first-class edge, not prose. The blocker must already exist.
- **Triage state** is the task state itself (`queued` / `in_flight` / `done` /
  `held`), not a label. There is no separate label vocabulary in this repo.

## Command surface

Get current flags from `tasks-axi <command> --help` rather than trusting
this list; it is a map, not a contract.

| Operation | Command |
|---|---|
| Add a ticket | `tasks-axi add <id> "<title>" --kind ship --repo {{PROJECT}} --body-file <path>` |
| Add with a blocker | `tasks-axi add <id> "<title>" --blocked-by <other-id>` |
| Record a dependency later | `tasks-axi block <id> --by <other-id>` |
| What is dispatchable now | `tasks-axi ready` |
| Claim before working | `tasks-axi start <id>` |
| Close with a PR | `tasks-axi done <id> --pr <url>` |
| Close with a report | `tasks-axi done <id> --report <path>` |
| Pause without losing it | `tasks-axi hold <id> --reason "<why>" --kind captain` |
| Defer to a date | `tasks-axi hold <id> --reason "<why>" --until YYYY-MM-DD` |
| Release once answered | `tasks-axi unhold <id>` |
| What is waiting on the user | `tasks-axi list --state held --fields hold_kind,hold_reason` |
| Read one ticket in full | `tasks-axi show <id> --full` |

## Decisions waiting on the user

A pending decision is a **held ticket**, not a note in the conversation —
conversations do not survive a session ending, and the backlog does. See
`CLAUDE.md` §4 for the policy; the mechanics are:

- `--kind captain` marks it as waiting on the user, which is what distinguishes
  it from a hold for load, an external blocker, or parked work. **`captain` is
  `tasks-axi`'s own enum value, not vocabulary from this contract** — its hold
  kinds are `captain | external | load | parked | future`. Pass it literally
  because the CLI requires it; never use the word when speaking to the user (§0).
- The `--reason` carries **the question and its options**, because that string is
  what a future session sees when it lists held work.
- Hold **the ticket the decision gates**. Mint a new one only when no ticket
  exists to hold, so the decision and the work it blocks stay one row.
- `unhold` only after recording the user's actual words. Their answer belongs in
  the ticket body (`update --body-file`), not only in a chat log.
- `--until YYYY-MM-DD` is how "later" is recorded: it leaves the live list and
  returns on its date.

`ready` already excludes held work, so a held decision cannot be dispatched by
accident.

## When a skill says "publish to the issue tracker"

Create a tasks-axi task. Put the ticket body in a file and pass `--body-file`;
multi-line bodies do not survive shell quoting reliably on Windows.

Use the ticket body shape the skill asked for (what to build, acceptance
criteria, blocked-by). Do **not** write files under `.scratch/` — that path
belongs to the upstream local-files convention this repo replaced.

## When a skill says "fetch the relevant ticket"

`tasks-axi show <id> --full`. The user will normally pass the id.

## Pull requests

PRs are delivery, not intake. **PRs as a request surface: no.**

Workers open PRs through the `no-mistakes` ship gate, which owns the
push/PR/CI phases. Use `gh-axi` for any direct GitHub read or write
(`gh-axi pr --help`); prefer it over raw `gh`.

The default branch is `{{DEFAULT_BRANCH}}`. Work must land on a feature branch — the
`no-mistakes` gate refuses to validate the default branch.

## Wayfinding operations

Used by `/wayfinder`. The **map** is one task; each decision is a child task.

- **Map**: `tasks-axi add <effort>-map "<destination>" --kind docs
  --body-file map.md`. The body holds Notes / Decisions-so-far / Fog.
- **Child ticket**: `<effort>-NN-<slug>`, with the question in the body. Record
  the ticket type (`research` / `prototype` / `grilling` / `task`) on the first
  line of the body.
- **Blocking**: `tasks-axi block <effort>-NN-<slug> --by <effort>-MM-<slug>`.
- **Frontier**: `tasks-axi ready --repo {{PROJECT}}` — it already excludes
  blocked and held work, so do not re-derive the frontier by hand.
- **Claim**: `tasks-axi start <id>` before any work.
- **Resolve**: `tasks-axi done <id> --note "<the answer>"`, then append a
  context pointer to the map body with
  `tasks-axi update <effort>-map --body-file <updated> --archive-body`.
