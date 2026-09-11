# Run 2 findings -- index

One row per finding in `run-02-findings.md`. **The id is authoritative, the
line number is a fast path.** Corrections append, so line numbers are stable
in practice -- but if one is stale, `grep -n 'F-0NN' run-02-findings.md`
settles it in one command.

```
grep '| gate ' run-02-index.md          # every gate finding
grep 'confirmed' run-02-index.md        # skip the unproven and the corrected
sed -n '3624,3695p' run-02-findings.md  # read one entry at its offset
```

**Drift check** -- these two must agree:

```
grep -c '<!-- F-[0-9]' run-02-findings.md
grep -c '^| F-[0-9]'   run-02-index.md
```

**Do not narrow these to `F-0`.** That was the original pattern and it stopped
matching at `F-100`, under-counting *both* sides by the same amount -- so it
returned a matching 99/99 and read as healthy while a finding was invisible to
it. A check that fails into agreement is worse than no check.

## Categories

- **`contract`** (18) -- The agent contract -- CLAUDE.md, its sections, and the behaviour it produces
- **`gate`** (22) -- The ship gate -- `no-mistakes`: its steps, costs, custody and failures
- **`harness`** (23) -- The runtime -- Orca dispatch, Claude Code limits, shell and path traps
- **`resources`** (6) -- What the run runs out of -- RAM, tokens, context
- **`docs`** (4) -- Documentation and artifact links, where the writing itself is the defect
- **`working`** (13) -- Confirmed working -- kept because a run with none of these scores better and is worse
- **`supervisor`** (10) -- My own errors, kept in place because corrections must sit where they happened
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

## What the shape says

Counting **confirmed** rows only -- the reproducible rule, since the earlier
numbers here matched neither the totals nor the confirmed counts -- the defects
are concentrated in **`gate` (15)**, **`harness` (14)** and **`contract` (12)**.
`gate` has overtaken `harness` since that sentence was first written. There is no
`worker` or `scout` category, and that is a finding in itself: across a
four-day run, almost nothing here is a worker doing bad work. The scout
terminal leak is a harness fault; the builders' own mistakes were caught by
their gates before they reached a PR. What failed was the machinery around
them, and the sequencing decisions nobody was asked to make.

