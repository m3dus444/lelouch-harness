# Run 2 findings -- index

One row per finding in `findings.md`. **The id is authoritative, the
line number is a fast path.** Corrections append, so line numbers are stable
in practice -- but if one is stale, `grep -n 'F-0NN' findings.md`
settles it in one command.

```
grep '| gate ' index.md          # every gate finding
grep 'confirmed' index.md        # skip the unproven and the corrected
sed -n '3624,3695p' findings.md  # read one entry at its offset
```

**Drift check** -- these two must agree:

```
grep -c '<!-- F-[0-9]' findings.md
grep -c '^| F-[0-9]'   index.md
```

**Do not narrow these to `F-0`.** That was the original pattern and it stopped
matching at `F-100`, under-counting *both* sides by the same amount -- so it
returned a matching 99/99 and read as healthy while a finding was invisible to
it. A check that fails into agreement is worse than no check.

## Categories

- **`contract`** (22) -- The agent contract -- CLAUDE.md, its sections, and the behaviour it produces
- **`gate`** (23) -- The ship gate -- `no-mistakes`: its steps, costs, custody and failures
- **`harness`** (29) -- The runtime -- Orca dispatch, Claude Code limits, shell and path traps
- **`resources`** (6) -- What the run runs out of -- RAM, tokens, context
- **`docs`** (4) -- Documentation and artifact links, where the writing itself is the defect
- **`working`** (13) -- Confirmed working -- kept because a run with none of these scores better and is worse
- **`supervisor`** (10) -- My own errors, kept in place because corrections must sit where they happened
- **`operator`** (11) -- C.C's own account of the run: what no instrument here can see
- **`meta`** (4) -- Reading guides, scope notes, and what is not yet proven

`status`: **confirmed** stands on evidence · **unproven** is one instance, do
not act on it · **corrected** is a claim I got wrong and fixed in place ·
**superseded** is wrong and replaced by another entry · **moved** lives in
`instrument-log.md` · **guide** is orientation, not a finding.

## Findings

| id | line | category | status | cost | finding |
|---|---|---|---|---|---|
| F-001 | 6 | working | confirmed | -- | What the contract got right; first observations, not re-runs |
| F-002 | 85 | harness | superseded | -- | `worker-release` has never run -- SUPERSEDED by F-069, release does run |
| F-003 | 239 | resources | confirmed | near-loss | Worker hit a usage limit mid-ticket; third instance, C.C wants a skill |
| F-004 | 688 | meta | unproven | -- | Do not act on these: single instances, no counter-example yet |
| F-005 | 830 | supervisor | moved | -- | Monitor bugs found while watching (moved to instrument-log.md) |
| F-006 | 872 | meta | guide | -- | C.C stopped me shipping contract edits off single observations |
| F-007 | 880 | docs | confirmed | -- | Documentation debt this run exposed, not behaviour findings |
| F-008 | 1442 | contract | confirmed | -- | What a cleared Lelouch reloads on re-cast, and what it loses |
| F-009 | 1504 | supervisor | corrected | -- | CORRECTION: I quoted a stale `pipeline_owned` from an old snapshot |
| F-010 | 1521 | working | confirmed | -- | The restart was clean, and did the thing I said to watch for |
| F-011 | 1546 | harness | confirmed | -- | A woken worker that does not resume its work |
| F-012 | 1574 | supervisor | corrected | -- | CORRECTION: the DuckDB trial did not fail; I misread exit 127 |
| F-013 | 1613 | supervisor | corrected | -- | CORRECTION: "idle" was too strong for `wa-03-budget` |
| F-014 | 1658 | docs | confirmed | artifact | Report-link loss reproduced live; the losing path reports success |
| F-015 | 1731 | harness | confirmed | -- | Quiet worker: third variant of the presence-vs-absence ambiguity |
| F-016 | 1760 | gate | confirmed | 31 min | Gate-poll cost measured, and a hypothesis about the token deaths |
| F-017 | 1792 | contract | confirmed | -- | The §7 wait outlived the session that armed it: undesigned recovery |
| F-018 | 1831 | working | confirmed | -- | The captain hold that got it right: `wa-required-checks` |
| F-019 | 1870 | supervisor | unproven | -- | Transcript growth as early warning; a proxy, not a measurement |
| F-020 | 1910 | working | corrected | -- | The non-convergence risk resolved in the good direction |
| F-021 | 1943 | contract | confirmed | -- | The re-cast Lelouch re-armed its own wait |
| F-022 | 1978 | meta | guide | -- | Reading guide for the 8 Sep session: what still stands |
| F-023 | 2018 | resources | confirmed | 23% spend | Token accounting measured; the supervisor was part of the problem |
| F-024 | 2065 | working | confirmed | -- | First complete gate traverse of the run: `wa-02-cache`, PR #4 |
| F-025 | 2104 | gate | guide | -- | Judge gate convergence by finding ids, not by counts |
| F-026 | 2147 | supervisor | confirmed | 3 h | The run stopped three hours ago and the monitor never said so |
| F-027 | 2206 | gate | confirmed | -- | A blocking `axi run` was backgrounded, then polled anyway |
| F-028 | 2265 | harness | corrected | -- | The watchdog: the backstop a notification-only design needs |
| F-029 | 2309 | harness | confirmed | universal | Heredoc quoting failure is environmental, not agent error |
| F-030 | 2332 | contract | confirmed | -- | §6 needs a notion of standing authorisation |
| F-031 | 2369 | harness | confirmed | 4 tries | Dispatch stalls on `--worktree new-top-level`: every fresh ticket |
| F-032 | 2396 | resources | confirmed | -- | Fan-out is bounded by RAM, not only by tokens |
| F-033 | 2431 | working | confirmed | -- | Recovery pattern confirmed twice: banked commits survive death |
| F-034 | 2461 | harness | confirmed | universal | The /tmp and /c/ path trap: bash writes it, Python cannot read it |
| F-035 | 2493 | gate | confirmed | -- | A worker reported `worker_done` with its gate parked on the agent |
| F-036 | 2558 | harness | superseded | -- | CORRECTION: harness blocks sleep-polling -- SUPERSEDED by F-072 |
| F-037 | 2594 | contract | confirmed | 1 h+ | ARCHITECTURE: one README conflict became an hour; the gate is not why |
| F-038 | 2701 | docs | confirmed | whole run | No worker has ever read the glossary: CONTEXT.md is gitignored |
| F-039 | 2763 | harness | confirmed | -- | The scout terminal leak has two causes; my fix addressed one |
| F-040 | 2815 | gate | corrected | 8 of 9 | `lint` is a no-op -- CORRECTED by F-074: it runs inside the document agent |
| F-041 | 2856 | harness | confirmed | universal | Both environment traps are universal, not occasional; final counts |
| F-042 | 2889 | gate | confirmed | -- | The remediation advice the gate gives is itself a trap |
| F-043 | 2926 | gate | confirmed | twice | The gate reports commits the worker cannot resolve |
| F-044 | 2951 | supervisor | corrected | 2 h 20 | The supervisor's worst failure: the alarm was right, I talked it down |
| F-045 | 3004 | resources | confirmed | -- | Memory pressure, waits, and who watches for silence: the whole thread |
| F-046 | 3082 | contract | corrected | turn/hb | CORRECTION: nudges are not free; not holding a wait costs a turn each |
| F-047 | 3120 | harness | confirmed | twice/day | `awaiting_agent` is invisible to the agent it is waiting for |
| F-048 | 3158 | contract | confirmed | 2-3 cmds | FIX NEEDED IN LELOUCH TOO: the anonymous heartbeat |
| F-049 | 3205 | working | confirmed | 4 caught | The correction loop runs upward, and it is load-bearing |
| F-050 | 3263 | resources | superseded | -- | Second memory kill -- SUPERSEDED by F-051, the cause was wrong |
| F-051 | 3328 | resources | corrected | 78 min | The 20:48 stop was token exhaustion, not a kill |
| F-052 | 3376 | gate | confirmed | blocking | Recovery from a gate rebase needs a force-push, which is auto-blocked |
| F-053 | 3410 | harness | confirmed | 2 h | Context exhaustion deadlocks dispatch until a human types `/clear` |
| F-054 | 3470 | contract | confirmed | 2-3x | The false-healthy report, and the missing resume-after-token-cap skill |
| F-055 | 3545 | contract | confirmed | 4 days | Ship the MVP as early as it is honest to; make ordering a decision |
| F-056 | 3624 | gate | confirmed | 73 min | The review step's 30-minute timeout discards a completed traverse |
| F-057 | 3695 | meta | guide | -- | SCOPE NOTE: what in this log is a Lelouch finding, and what is not |

| F-058 | 3732 | gate | confirmed | 9 rounds | The review does not converge: five rounds, no repeated finding id |
| F-059 | 3774 | gate | confirmed | history | The gate writes a PR number into history before the PR exists |

| F-060 | 3809 | gate | confirmed | 6 runs | Every gate failure reports the same error, and it is the wrong one |

| F-061 | 2763 | docs | corrected | 46s/worker | CORRECTION to F-038: a worker did read the glossary, by hunting for it |

| F-062 | 2594 | harness | superseded | turn/min | CORRECTION to F-036: real but not uniform -- SUPERSEDED by F-072, it is uniform on duration |

| F-063 | 4023 | gate | confirmed | 4 decisions | An ask-user finding expires into the worker own judgement |

| F-064 | 4238 | gate | corrected | 6 min | Gate solved it at 17:24, worker again at 19:02 -- cause CORRECTED by F-073 |

| F-065 | 4350 | harness | confirmed | 1 trip | ADDENDUM to F-034: Node resolves modules against /tmp too |

| F-066 | 4399 | gate | confirmed | 3 of 13 PRs | Three PRs shipped without a completed traverse; the bypass ledger has zero rows |

| F-067 | 4502 | contract | confirmed | run stalled | `head -40` ate a worker_done, and the ack made it unrecoverable |

| F-068 | 4598 | contract | corrected | 1 h measured | CORRECTION to F-067: the timeout was the backstop, and it worked |

| F-069 | 4668 | harness | corrected | 17 of 33 | CORRECTION to F-002: release works; watching a worker is what keeps it alive |

| F-070 | 4768 | harness | confirmed | 59 s / retry | F-031's mechanism: the first dispatch races worktree creation |

| F-071 | 4832 | harness | confirmed | 38 s here | `python3` is a Store-alias decoy on this machine, and it fails in French |

| F-072 | 4921 | harness | confirmed | reopens §W | The sleep block is uniform on duration, and the cheap wait is unenforced |

| F-073 | 4998 | gate | corrected | -- | CORRECTION to F-064: the gate's analysis was one documented command away |

| F-074 | 5072 | gate | confirmed | 47.5 min | First complete traverse measured; `test` and `lint` are agents, not commands |

| F-075 | 5179 | gate | confirmed | wrong tree | `no-mistakes rerun` validates the previous head, not the current one |

| F-076 | 5251 | gate | confirmed | 50x spread | ADDENDUM to F-074: gate cost is not predictable from the diff |

| F-077 | 5305 | contract | confirmed | latent | ADDENDUM to F-067: the truncation fires only after a backlog, i.e. on recovery |

| F-078 | 5367 | contract | confirmed | ~9 min | Contract says call tools directly; the `lavish` skill says use `npx -y` |

| F-079 | 5446 | contract | confirmed | attribution | "Did you decide that on yourself?" -- skill decisions read as agent decisions |

| F-080 | 5501 | harness | confirmed | 5/5 stall | F-070 at n=5: stall is total, retry reliable, nothing dropped |

| F-081 | 5550 | supervisor | confirmed | 10 cmds + F-064 | A resume artifact must derive state, not record it -- FIX NEEDED IN LELOUCH TOO |

| F-082 | 5634 | harness | confirmed | 2m12s | The §7 wait is a singleton; `/clear` orphans its holder and only a force-kill frees it |

| F-083 | 5705 | contract | corrected | -- | CORRECTION to F-017: the task dir is the lineage's, not a dead session's |

| F-084 | 5760 | harness | confirmed | 65 of 70 min | A worker's backgrounded heartbeat loop died after one beat; nothing told it |

| F-085 | 5829 | working | confirmed | -- | Blanket overnight authority used narrowly: the unwritten rule two agents both found |

| F-086 | 5892 | contract | confirmed | ~31 h | A captain hold has no falsifier and no expiry; its own refutation sat in the same file |

| F-087 | 5953 | gate | confirmed | none realised | PR #15 shows green CI for a head the branch moved past; the new commit was never pushed |

| F-088 | 6015 | gate | confirmed | 1 commit lost | F-087 realised: ec5900f never reached master, and worker_done reported succeeded |

| F-089 | 6077 | working | confirmed | fix redone | The dropped commit was caught by its symptom, unprompted -- but filed as new work, not as a loss |

| F-090 | 6128 | supervisor | corrected | wrong deadline | CORRECTION to F-088/F-089: the commit was reachable via a live branch, and Lelouch had read the cause |

| F-091 | 6195 | gate | confirmed | 1 of 15 PRs | The head divergence needs a prior run's PR plus an unpushed live run; one query flags it |

| F-092 | 6248 | contract | confirmed | 6 days | `docs/adr/**` has a read instruction and no writer; decisions went to three worse places |

| F-093 | 6309 | contract | confirmed | live | A spec called ADR 0001 binding; it was never committed, so the worker's tree has no copy |

| F-094 | 6364 | working | confirmed | 34 s | F-093's outcome: the worker globbed the ADR out of the main tree and committed it |

| F-095 | 6415 | working | confirmed | n=3 | F-085 at n=3: three agents independently escalate behaviour changes and fix false claims |

| F-096 | 6457 | working | confirmed | loss pre-empted | Asking "is your work pushed?" surfaced F-088's stranding before it cost anything |

| F-097 | 6507 | harness | confirmed | n=2 | F-084 bounded: a 60s-sleep loop survived two intervals; sleep length and lifetime are confounded |

| F-098 | 6558 | working | confirmed | 3 h | The committed ADR caught an implementation drifting from decision 3 -- F-092's payoff |

| F-099 | 6609 | supervisor | corrected | 3 findings | CONFOUND: Claude Code memory was enabled; it wrote F-095/F-096's behaviour and F-085's best quote |

| F-100 | 6689 | harness | corrected | -- | CORRECTION to F-052: force-push is blocked by auto mode, not by the system; bypass-mode workers publish fine |

| F-101 | 6741 | harness | confirmed | 3 threads / 2d | An expired ask leaves a pending thread forever; only a schema migration collects it |

| F-102 | 6797 | contract | confirmed | 45 shots / 0 shown | Browser verification is real but headless and unauditable; no report carries a screenshot |

| F-103 | 6853 | contract | corrected | -- | CORRECTION to F-102: C.C rejected the screenshot fix; the defect is the spec's "say that you did" |

| F-104 | 6914 | contract | confirmed | latent | One shared browser bridge for all workers; SESSION isolation exists and is never set -- FIX AGREED |

| F-105 | 6973 | harness | confirmed | 592 MB / 4 days | Worktree removal de-registers before deleting; orphans are invisible to both registries |

| F-106 | 7048 | harness | confirmed | 0 of 300 files lost — FIX AGREED | Orphan sweep is provably safe today, but the proof dies with `.git` — verify before removal, not after |

| F-107 | 7132 | contract | confirmed | spend avoided | Dispatch preceded disclosure by 64s — but the warmed terminal is the only place the 95% limit banner exists; the unapproved action was the sensor; C.C ruled hold, but `--until` is day-granular so nothing fires at the reset |

| F-108 | 7259 | harness | confirmed | 1 run unclosable | The no-mistakes daemon is global: one worker's recovery restart killed another's CI monitor — and the notice said "PR remains open" 17m after the merge, from a 4h49m-stale read |

| F-109 | 7308 | harness | corrected | 1 review re-spent | CORRECTION to F-060: the cause IS recoverable, from `agent_invocations` — 10m21s, no model, no session, 0 tokens; a memory kill, and the cost is the retry, not the crash |

| F-110 | 7362 | gate | confirmed | 1 permanent wrong ref | F-059 realised: two parallel builders raced for PR #25; the loser's commit message points at the winner's PR forever. Collision rate is gate timing, not worker behaviour |

| F-111 | 7395 | harness | confirmed | 1 round-trip per quote | The supported finding view truncates, so workers read state.sqlite and then fight shell quoting to relay it — lossy view, no structured relay, mangled backticks |
| F-112 | 7445 | operator | confirmed | terminal unreadable | Lelouch talks far too much: restating settled decisions, narrating Lavish pages, narrating dispatches — one unbounded reporting rule wearing three coats |
| F-113 | 7495 | operator | confirmed | manual recovery | The session-lifecycle skills: afk/back, resume, restore — all user-only, and restore is load-bearing for auto-clear so it gets proven first |
| F-114 | 7532 | operator | confirmed | state on request only | Ticket names are too ambiguous to say what is being worked on; britania-board must read state.sqlite directly and document the schema |
| F-115 | 7555 | operator | confirmed | silent resource failures | britania-vitals gates a dispatch on the environment and wakes Lelouch on a threshold; quota-axi and fanwatch already do most of it, pointed the wrong way |
| F-116 | 7586 | operator | confirmed | none | grill-with-docs was never model-invokable, so it and grill-me leave the payload; grill-with-lavish absorbs the job and calls domain-modeling itself |
| F-117 | 7611 | operator | confirmed | one model, one effort | worker-start already takes --model and --effort; model moves the rate on 2.1M cache-read, effort moves 137 output tokens. Tier by role: scouts keep thinking |
| F-118 | 7648 | operator | confirmed | 12x on short cycles | Heartbeats re-enter context; the long-wait floor was already measured and written down. Auto-compact is possible, but only from outside via orca terminal send |
| F-119 | 7679 | operator | confirmed | relearned per cast | Eleven harness facts are living in Claude's per-project memory instead of the harness; deleting them for consistency would make v2 worse |
| F-120 | 7717 | operator | unproven | -- | Graphify: my cache-that-asserts objection did not survive C.C's per-worktree design; the open question is regeneration cost per gate rebase |
| F-121 | 7742 | operator | confirmed | none | Ponytail rejected on the ratio: generation is ~0.01% of spend, so no output-side optimisation can move a bill made of cache reads |
| F-122 | 7760 | operator | confirmed | 1 branch stranded | Permissions: F-052's refused force-push is a classifier problem no gate release will fix. Also records two non-defects so nobody fixes them |

## What the shape says

Counting **confirmed** rows only -- the reproducible rule, since the earlier
numbers here matched neither the totals nor the confirmed counts -- the defects
are concentrated in **`harness` (22)**, **`gate` (19)** and **`contract` (18)**.
These are recomputed from the rows above, not carried forward: the figures
standing here until 12 Sep read 15/15/12, then 20/18/17 — and that last set was
already one short on `contract` before F-108 was written, drifting again in
exactly the way this paragraph warns about. A count kept by hand beside the data it counts is not a summary, it is
a second source that silently disagrees. Recompute:
`awk -F'|' '$4==" harness " && $5==" confirmed "' index.md | wc -l`. There is no
`worker` or `scout` category, and that is a finding in itself: across a
four-day run, almost nothing here is a worker doing bad work. The scout
terminal leak is a harness fault; the builders' own mistakes were caught by
their gates before they reached a PR. What failed was the machinery around
them, and the sequencing decisions nobody was asked to make.


---

# Final scorecard -- run 02

Produced 2026-09-14 with `observe.py weave-atlas`, post-run: Lelouch on hold, no
builders out, nothing in flight. Run it again the same way and it should
reproduce; the volume figures will not, because transcripts keep growing.

## What the instrument reads

13 weave-atlas sessions on disk, **2,879 events / 638 actions**. The run is
carried by three sessions -- `75166262` (922/190), `c2d90830` (810/170) and
`0615d09e` (331/64) -- which is the re-cast boundary showing up in the data:
each long session is one Lelouch lifetime between clears.

```
skills invoked   grilling, prototype, to-tickets, research, lavish,
                 chrome-devtools-axi
skills REFUSED   grill-with-docs  (called, but never ran)
```

## Contract compliance

```
PASS   grilled before dispatching
PASS   invoked to-tickets (not improvised)
PASS   showed a Lavish artifact
PASS   Lavish shown BEFORE first dispatch
PASS   dispatched a worker
PASS   filed tickets in the backlog
PASS   addressed the user as C.C
PASS   held a decision rather than losing it
 --    wrote the glossary (domain-modeling)      not reachable
 --    invoked to-spec                           not reachable
 --    called tools directly, not via npx        not reachable
```

**8 PASS, 0 FAIL, 3 unreachable.** No check regressed across the run.

> **Instrument caveat, added 2026-09-18 -- these numbers are NOT recomputed.**
> Two defects in `observe.py` were found after this run and fixed forward only:
> run 03's **F-072** (the `grilled before dispatching` row credited a literal
> `grilling` call and nothing else, so a run that grills through the
> `grill-with-lavish` wrapper scores a silent FAIL on the row that certifies
> the approval gate) and run 03's **F-073** (`slug_dir()` kept one matching
> transcript directory out of the many a run writes, and sessions were ordered
> by file mtime with the real clock discarded). Both live in
> `runs/run03/findings.md`; run 02's own F-072 and F-073, in the table above,
> are unrelated findings that happen to share the ids.
>
> What that makes unreliable here:
>
> - **Every row above, and the volume figures.** The 13 sessions read are one
>   directory's. 29 transcript directories match `weave-atlas`, 28 of them
>   builder worktrees, and none of those was read -- so `skills invoked` is the
>   coordinator's list alone, and any `--` may be a builder invocation the
>   instrument never saw rather than something that did not happen.
> - **The two ordering rows**, `grilled before dispatching` and `Lavish shown
>   BEFORE first dispatch`. Session order came from mtime, which tracks the last
>   append, so a long session sorts behind short ones that started after it:
>   either verdict can be an artifact of how long a session ran.
> - **`grilled before dispatching`** again, on F-072's side: run 02 did make a
>   literal `grilling` call, so the bug did not manufacture this PASS -- but it
>   is not the same row that run 03 onward reports.
>
> The numbers stay exactly as produced on 2026-09-14. Re-deriving them under
> the repaired instrument would leave two runs measured differently while
> looking comparable, which is worse than a caveat beside them.

## Two things the script cannot see, and I watched happen

- **Workers ran the skills their specs named: 4 of 4**, in the order named. The
  spec-to-behaviour link held for every builder dispatched on the final day.
- **Escalations answered: 3 of 3, all under two minutes.** Measured against
  [F-101](findings.md), where `ask` findings expired into the worker's own
  judgement because nothing answered them in time. This is the one place the run
  visibly improved on its own earlier behaviour.

## Run totals

```
findings            111        index rows 111   (drift check clean)
confirmed            80        corrected   20   superseded 4
                              unproven      2   guide      4   moved 1
concentration        harness 22 | gate 19 | contract 18   (confirmed only)
PRs                  29, all merged, none closed unmerged
backlog              31 queued, 23 ready, 0 in flight, 10 done retained
```

**Re-verified against the upstream changelog** (we ran v1.64.0 throughout;
eleven releases landed during the run). Of eleven candidates: **F-056** and
**F-075** are superseded -- `fix(pipeline): give each review agent a fresh
timeout` (#962, v1.68.0) and `fix(daemon): refuse reruns that differ from the
clean caller HEAD` (#972, v1.66.0) name the same mechanisms, and **both are in
the version we now run.** The other nine stand, including F-087 and F-110, which
I initially and wrongly matched to upstream fixes.

**F-109 is the one that needs the distinction "fixed upstream" cannot carry.**
`fix(agent): record honest token usage on failed and cancelled invocations`
(#1059) makes a killed invocation record *unknown* rather than a fabricated 0 --
but it shipped in **v1.75.1, and `no-mistakes update` cannot reach past
v1.72.0** (see below). So F-109 stands *for this deployment*: a killed
invocation here still writes 0/0/0, and the forensic method it documents is
still the one that works. **F-060**'s wrong error attribution is untouched in
every version.

Detail in the `operator` findings, [F-112 onward](findings.md).

## What this scorecard does not measure, and the omission is the finding

**The MVP arrived during this run** -- four anchors, each with its filters,
verified by C.C in a live smoke test. **There is no row above for it**, because
the instrument scores contract compliance and nothing else. A run could pass all
eight checks and ship nothing.

That gap is not cosmetic. It is the same gap named in the `mvp-first-ordering`
memory and in [F-111](findings.md)'s neighbourhood: the contract has an
approval gate, a design gate and a Scout gate, and **no notion of a product
milestone that orders the backlog.** The scorecard inherited that blindness
honestly, by measuring exactly what the contract asks for.

For run 03: a scorecard row that asks *did the run advance the milestone*, and
a contract that has a milestone to advance.

## Resolved after the scorecard ran

`grill-with-docs` was **called and never ran**, and the reason is mundane:
**the skill is not model-invokable.** Lelouch could not run it, so he read the
skill and ran `grilling` and `domain-modeling` separately instead -- the
behaviour the skill packages, obtained the long way. Not a defect, and not
F-112.

The v2 consequence is a deletion, not a fix: C.C does not intend to invoke a
grill skill by hand, so **`grill-with-docs` and `grill-me` both come out of the
payload**, and `grill-with-lavish` absorbs the job -- it must invoke
`domain-modeling` itself rather than leaving it to be remembered. Recorded in
[F-116](findings.md).

**One discrepancy left open.** `observe.py` does not list `domain-modeling`
among the skills invoked, and the `wrote the glossary (domain-modeling)` check
reads unreachable. Either the detector misses the invocation or the glossary was
never written -- and [F-038](findings.md) says no worker ever read one,
which is weak support for the second. Not resolved here; it is a detector
question and it belongs to the instrument, not to the run.

## Teardown, and two things it proved

Run 02 was torn down 2026-09-14 with Lelouch on hold and nothing in flight.
Watchers down, logger stopped, no worker terminals left, `git worktree list`
showing only master.

**The global daemon pins the worktree that started it. Confirmed, not inferred.**
`wa-cache-projection-doorway` survived as an empty directory that would not
delete -- *"Device or resource busy"* from both `rmdir` and PowerShell, with **no
process naming the path**. The candidate was the no-mistakes daemon, pid 23728,
started `2026-09-12T15:45:17Z` -- the exact second of
[F-108](findings.md)'s restart, when the doorway worker ran
`no-mistakes daemon start` from inside that worktree. Its parent process was
already gone, so it was orphaned and carrying that shell's working directory.

Tested rather than asserted: delete before (busy) -> `no-mistakes update`
replaces the daemon (23728 -> 19488) -> delete after (**removed**), nothing else
changed in between. So this is **[F-108](findings.md) extended**: the
global daemon does not only kill another worker's CI monitor, it **holds that
worktree undeletable for its own lifetime**, which is [F-105](findings.md)'s
orphan problem with a named mechanism and a one-line cause.

**The update channel is four releases stale, and the fix for that is only
distributed through the channel it fixes.** `no-mistakes update` took us
v1.64.0 -> **v1.72.0** and then reported "already up to date". GitHub has
v1.75.1, published 12 Sep. The channel manifest explains it:

```
channels.json   stable: v1.72.0      asset updated 2026-09-12T13:21:57Z
```

Updated *after* v1.75.0 shipped, still naming v1.72.0. And v1.73.0 contains
`fix: publish update channels after automated releases` (#1024) -- **the repair
for the stale channel is itself only reachable through the stale channel.** A
bootstrap trap: no client on <= v1.72.0 can update past it by updating.

Consequence for these findings: "fixed upstream" and "fixed in what we run" are
different claims, and only the second one matters to a run. Everything through
v1.72.0 is live for us; v1.73.0-v1.75.1 is not, including #1059.
