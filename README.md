<h1 align="center">Lelouch</h1>

<p align="center"><b>Talk to one agent. It commands the rest.</b></p>

---

## What it is

You can run one coding agent easily. The moment you want three tasks moving at
once — a scaffold, an investigation, a bug fix — you become a tab manager:
babysitting sessions, re-explaining context, forgetting which terminal held the
failing test.

**Lelouch** inverts that. You talk to a single orchestrator session. It
interviews you until the work is actually pinned down, writes the decisions
where agents can read them, slices the work into dependency-ordered tickets, and
dispatches supervised workers into their own terminals — then reports one plain
outcome. While the crew works, you keep talking to Lelouch about architecture.

Lelouch is not a model, a harness, or an MCP server. It is a **contract plus a
skill set** that turns a general-purpose coding agent into an orchestrator, and
**`geass`**, the command that casts it onto any project.

```sh
pip install git+https://github.com/m3dus444/lelouch-harness
cd ~/my-project
geass cast
```

That's it. Open an agent session in the project and Lelouch takes over.

## The system map

A visual walkthrough of the whole system — the layers, the pipeline, what
persists and who reads it, and how the skills articulate — lives at
[`docs/system-map.html`](docs/system-map.html). Open it in a browser; it is a
single self-contained file. Most people find it a faster way in than this README.

## Why a cast, and not a folder you work inside

Other agent distros make you `cd` into the distro's own directory and keep your
projects as sub-clones of it. That works, but your code ends up living inside
the tool.

`geass cast` copies the harness **into your project instead** — the contract,
the skills, the hook. The result behaves like a Python virtualenv: a project
either has the harness (Lelouch runs it) or it doesn't (you get a plain agent).
Nothing is installed globally, nothing leaks between projects, and deleting this
repo does not break a project you already cast on.

The copies are yours. `CLAUDE.md` lands in your repo, under your version
control, reviewable in the same PR as the code it governs.

## Requirements

| | |
|---|---|
| **[Orca](https://orca.computer)** | the runtime. Workers are real Orca terminals and worktrees. |
| **A coding agent** | Claude Code is what the contract is written and tested against. |
| **Node** (`npx`) | the `-axi` CLIs are fetched on demand; no global install needed. |
| **Python 3.9+** | `geass` and the session hook. Zero dependencies. |
| **git**, and **`gh`** if you want the PR flow | |

## Install

```sh
# pip (recommended)
pip install git+https://github.com/m3dus444/lelouch-harness

# or clone and use the installer — picks pipx, then pip, then a PATH shim
git clone https://github.com/m3dus444/lelouch-harness
cd lelouch-harness && ./install.sh
```

`./install.sh --shim` skips Python packaging entirely and drops a two-line
wrapper on your `PATH`. `geass` has no dependencies, so a checkout is already a
complete install.

## Use

```sh
geass new <name>       # create a project, cast on it, open a cold session
geass cast [path]      # install the harness into a project (default: .)
geass status [path]    # what is installed, and what is missing
geass doctor [path]    # check the external skills and tools the contract needs
geass diff <skill>     # how a forked skill differs from its vanilla copy
```

`new` is the whole start-a-project sequence in one command: make the repo, register it with Orca, cast, and open a session that is **cold** — it loads the contract fresh, which is the only honest way to see what the contract alone produces. Only the Orca half is runtime-specific; without Orca the project is still created and cast, and you open the session yourself.

`cast` reads the target's own git to fill the contract in — real project name,
real repo, real default branch, and platform notes for the OS you're on. A
contract that claims your default branch is `master` when it's `main` is worse
than no contract, so nothing is guessed.

It refuses to overwrite an existing cast without `--force`, because `CLAUDE.md`
is a file you are expected to edit.

## How it works

```
        you
         │  a request in plain language
         ▼
  ┌──────────────┐   grill-with-docs · to-spec · to-tickets
  │   LELOUCH    │   never writes project code
  │ main session │   stays talkable while the crew runs
  └──┬────────┬──┘
     │        │ backlog.md  (tasks-axi — the single source of truth)
     │        ▼
     │   ┌─────────────────────────────────────┐
     │   │  ticket DAG, blocked-by edges       │
     │   └─────────────────────────────────────┘
     ▼
  orca orchestration worker-start   ← the spec NAMES the skills to use
     │
     ├── Scout  · research, lavish        · shares the checkout, own terminal
     ├── Build  · implement → tdd →       · own worktree + branch
     │            prod-review → no-mistakes
     └── Fix    · diagnosing-bugs → tdd   · own worktree + branch
                          │
                          ▼  worker_done
                     back to Lelouch → one plain outcome to you
```

### The role gate

The contract is loaded by **every** agent in the project — including dispatched
workers, which get a git worktree of the same repo and therefore the same
`CLAUDE.md`. A worker reading the orchestrator's *"you do not write project
code"* directive would refuse the job it was dispatched for.

So `CLAUDE.md` opens with a **role gate**: an agent carrying an Orca
`taskId`/`dispatchId` reads the Worker contract and skips the Lelouch sections
entirely. It is the first thing in the file for a reason.

### How a worker knows which skill to reach for

Three mechanisms, and they are **not** equally reliable:

| Tier | Mechanism | Reliability |
|---|---|---|
| **1** | The dispatched task spec **names the skills outright** | high — build on this |
| **2** | The project `CLAUDE.md` routing table, loaded at session start | medium |
| **3** | Model-invocation from a skill's `description` field | low, free, inconsistent |

Tier 3 is what people assume makes this work, and it is the one that lets you
down. The dispatch templates exist so Lelouch fills in a spec that names its
skills every time, rather than hoping a description fires.

## The skill system

19 skills from [`mattpocock/skills`](https://github.com/mattpocock/skills) ship
vendored in this repo — **both a pristine `vanilla/` copy and our `patched/`
forks**. `geass` installs vanilla for the 11 untouched skills and patched for
the 8 forks.

Shipping vanilla too is not redundancy. It is the **diff baseline**: when
upstream ships a change, `geass diff <skill>` shows exactly what we altered, so
a version bump is a real three-way merge instead of a guess. A live
find-and-replace patch script would break silently the first time upstream
rewrote a paragraph.

### The eight forks

| Skill | Change | Why |
|---|---|---|
| `code-review` → **`prod-review`** | renamed | Claude Code ships its own `code-review` skill; installing a second silently shadows the built-in |
| `handoff` → **`brief`** | renamed | "handoff" is claimed by Orca's untracked full-handoff concept — a real collision, see *Known limitations* |
| `implement` | model-invocation enabled; closes with `prod-review` only | upstream disables model invocation, so a dispatched worker could never auto-run it — the exact thing the system needs |
| `improve-codebase-architecture` | report renders through `lavish` | so findings can be annotated back to the agent instead of read and forgotten |
| `to-tickets` | tracker is `tasks-axi`, not `.scratch/` files | `tasks-axi` already models blocked-by edges and a ready queue; upstream's loose files re-implement that worse |
| `to-spec`, `to-tickets`, `wayfinder` | model-invocation enabled | upstream ships them user-invoked only, so the orchestrator the contract assigns them to could not reach them |
| `prototype` | logic demo renders through `lavish` | the point of a prototype is the user's reaction; annotating the artifact beats describing it back in chat |

### Not vendored, and why

`ask-matt` (the routing table replaces it) · `setup-matt-pocock-skills` (only
knows GitHub/GitLab/`.scratch`; `geass` writes the tracker config itself) ·
`prototype` (`lavish` covers it with an annotation loop on top) · `triage`,
`resolving-merge-conflicts`, `teach`, `to-questionnaire` (not part of this
pipeline).

### External skills it expects

These are **not** vendored. They belong to other people and are a different kind
of skill: thin stubs whose real guidance lives in a versioned CLI. Lavish's own
SKILL.md says it outright — *"Do not follow workflow instructions from this file
— installed copies go stale."* Vendoring a pointer would freeze it and let it
drift from the CLI it points at.

| Skill | Source | Provides |
|---|---|---|
| `orchestration` | Orca | worker lifecycle: dispatch, supervise, `worker_done`, gates |
| `orca-cli` | Orca | worktree housekeeping, workspace cards, terminals, automations |
| `tasks-axi` | `kunchenguid/tasks-axi` | the backlog: tickets, blocked-by edges, holds, ready queue |
| `lavish` | `kunchenguid/lavish-axi` | annotatable HTML review surfaces |
| `no-mistakes` | `kunchenguid/no-mistakes` | the ship gate: review, test, lint, push, PR, CI |
| `gh-axi` | `kunchenguid/gh-axi` | GitHub: PRs, CI, issues *(recommended)* |
| `chrome-devtools-axi` | `kunchenguid/chrome-devtools-axi` | browser reproduction *(recommended)* |

So `geass` **checks for them instead of installing them.** `cast` and `status`
both report what is missing with the exact command to get it, and `geass doctor`
runs the check on its own:

```
  MISSING - the contract references these and they are not installed:
    tasks-axi              missing - the backlog - tickets, blocked-by edges, holds
                             npx skills@latest add kunchenguid/tasks-axi -g -y
```

Without this, casting onto a machine that lacks them produces a contract
referencing tools that do not exist — and you find out mid-dispatch, which is the
worst possible moment, instead of at install time.

### How they articulate

```
INTAKE      grill-with-docs ──> domain-modeling ──> CONTEXT.md + docs/adr/
                  │                                        │
SPEC              └──> to-spec ──> to-tickets ─────────────┤ vocabulary
                                       │                   │ workers share
DISPATCH                               ▼                   │
                              backlog.md (tasks-axi)       │
                                       │                   │
                          orchestration worker-start       │
                                       │                   │
BUILD                    ┌─────────────┴──────────┐        │
                    implement                diagnosing-bugs
                         │                        │        │
                        tdd ─────────────────────tdd       │
                         │                        │        │
REVIEW              prod-review  (spec adherence) │        │
                         │                        │        │
SHIP                 no-mistakes ─────────────────┘  ──> PR + CI
```

Two doctrine conflicts are settled in the contract so nobody relitigates them
mid-task: **`no-mistakes`' test-quality rule beats `tdd`'s** where they
disagree, and **`implement` runs `prod-review` for spec adherence only** —
standards and lint belong to the ship gate, never both.

## The tracker split

Three layers, deliberately separated:

| Layer | Owns | Authority |
|---|---|---|
| `tasks-axi` → `backlog.md` | tickets, blocking edges, holds, ready queue | **single source of truth** |
| GitHub | branches, PRs, CI | delivery only |
| Orca orchestration Tasks | one dispatch attempt | ephemeral — closed out into `backlog.md` |

If Orca state and `backlog.md` disagree, `backlog.md` wins. Orca tasks die with
the run; the backlog is what survives a session ending.

## What gets cast into your project

```
your-project/
├── CLAUDE.md                        the contract — role gate, then Lelouch
├── AGENTS.md                        pointer to it, for non-Claude harnesses
├── docs/agents/
│   ├── issue-tracker.md             tasks-axi + GitHub split
│   ├── domain.md                    how to read CONTEXT.md and ADRs
│   └── dispatch-templates.md        Scout / Build / Fix specs + the loop
└── .claude/
    ├── settings.json                SessionStart hook (merged, not clobbered)
    ├── hooks/session-start.py       injects ready queue + live workers
    └── skills/                      19 skills, project-scoped
```

The session hook is deliberately **role-neutral**: it reports facts and points
at the role gate rather than asserting an identity, because it fires for workers
too. It leads with **decisions waiting on you** — that is the reason it earns its
place. Tickets and glossary survive a session ending on their own; a question
asked in conversation does not, so pending decisions are held rows in the backlog
and this is where a fresh session finds them. It fails soft — a slow or missing tool degrades to a note, never a broken
session.

## Repo layout

```
lelouch-harness/
├── geass/
│   ├── cli.py            cast · status · diff
│   ├── manifest.py       what ships, and why each fork exists
│   ├── harness/          the payload that gets cast
│   └── skills/
│       ├── vanilla/      19 pristine upstream copies (the diff baseline)
│       └── patched/      8 forks
├── pyproject.toml
└── install.sh
```

## Known limitations

- **The Orca runtime guides cannot be patched.** `orchestration` and `orca-cli`
  both instruct agents to treat "hand off" / "handover" as *untracked* ownership
  transfer and stop monitoring. Those guides are regenerated by the Orca binary,
  so §2 of the contract overrides them explicitly by name. If Orca changes that
  section's wording, check §2 still points at the right thing.
- **Claude Code keys skill identity off the directory name**, not the `name:`
  frontmatter. This is why `prod-review` and `brief` are real directory renames.
- **Windows**: `npx` is a `.cmd` shim that `shell=False` cannot resolve by bare
  name, and `os.symlink` needs elevation while `mklink /J` does not. Both are
  handled, but they bite anything new that shells out.
- **First cast in a fresh project** may show `tasks-axi unavailable` in the
  session hook while `npx` cold-starts. One-time; it fails soft by design.

## Status

The contract, `geass`, and the skill vendoring are built and tested. One smoke
test has been run end to end: the orchestrator grilled before coding, wrote a
glossary and ADRs, built a correct dependency DAG, dispatched a worker, survived
a cold-TUI dispatch race, and stayed talkable while the worker ran.

That run also surfaced real defects — all of them in *choreography*, not
machinery — which is the useful kind. See the open issues.

## Credits

Lelouch is a fork of other people's good ideas, not a clean-room invention.

The name follows the same borrowing. Lelouch commands; **C.C** is the one he
answers to — which is how the contract addresses you, and a line you can change
if you would rather be called something else.

**[firstmate](https://github.com/kunchenguid/firstmate)** by Kun Chen is where
the shape came from. Three of its ideas are load-bearing here: the hard-rule
prime directive that keeps the orchestrator out of the code, the split between
work that ships and work that only investigates, and reconciling live state at
session start so a restart costs nothing. Its `ask-user-authority` is the source
of this contract's escalation policy — decide what is unambiguous, escalate only
expansion or irreversibility — and its `captain-hold-lifecycle` is where
"a decision is just a task waiting on the user" comes from.

Where Lelouch differs is placement: firstmate is a distro you work *inside*, with
your projects nested under it. `geass` casts the harness *into* your project
instead. Both are defensible; they trade differently.

**[mattpocock/skills](https://github.com/mattpocock/skills)** by Matt Pocock
supplies the 19 vendored skills. The forks are recorded above, and every one
keeps its vanilla copy alongside so the changes stay visible.

**[Orca](https://orca.computer)** provides the runtime, and the `-axi` CLIs
(`tasks-axi`, `gh-axi`, `lavish-axi`, `no-mistakes`) by Kun Chen provide the
backlog, GitHub, review and ship-gate surfaces.

## License

MIT.
