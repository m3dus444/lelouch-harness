# Supervisor instrument log — run 2

Not run findings. This is the supervisor's own tooling (`watch.py`, the liveness
and memory monitors) breaking and being repaired while it watched run 2. It is
split out of `runs/run02/findings.md` so the debrief reads only evidence about
the Lelouch system.

Kept because it is the honest record of how reliable the instrument was while it
was producing that evidence — a finding is worth exactly what the tool that
caught it was worth at the time.

**The one thing here that generalises**, and which is recorded in the findings
rather than here: every defect below was *a value I did not inspect* — a
backspace where I expected a regex, mtime where I expected activity, a noun where
I expected a sentence, a comma where I expected a decimal point.

---

### Instrument defects — `watch.py`, fixed mid-run

Fixed live, deliberately, and the reasoning matters: the "do not change things
mid-run" rule protects the **contract under test**. `watch.py` is the observer.
Leaving it blind through the restart would corrupt the record more than the edit
does. No contract, skill or template was touched.

1. **`terminal send` was invisible.** The whole restart — three workers woken —
   streamed **nothing**. The single most consequential action of the run's last
   half hour produced silence indistinguishable from an idle orchestrator. Now
   `** WAKE` / `** SEND`.
2. **`DISPATCH` could not match the contract's own dispatch form.** The pattern
   demanded `worker-start` immediately followed by `--task`; the prescribed
   pre-warm form is `worker-start --terminal <h> --task <id>`. Relaxed to
   `worker-start\b`. **Open:** run 2's log credits pre-warm dispatch as observed
   — re-check how those were actually seen, because this pattern cannot have
   done it.
3. **`AskUserQuestion` was not watched at all.** The one tool that *implements*
   the §6 gate was invisible; every gate judgement so far has been inferred from
   what did or did not follow it. Now `** ASK-CC` with the question text.
4. **`no-mistakes axi status` labelled identically to a gate firing.** A read
   scored like a ship. Split off as `gate-read`.
5. **90-char truncation hid the matching token.** A line labelled `ship-gate`
   whose visible text was a `git log` — the match sat past the cut. Now 150.
6. **No session tag.** Heartbeats from three worktrees were identical lines.
   Now prefixed `[lelouch]`, `[wa-02-cache]`, `[wa-03-budget]`.

Four of these six are the same failure: **the stream was silent when it should
have spoken.** A monitor whose absence of output is ambiguous between "nothing
happened" and "I cannot see this" is worse than no monitor, because it is
trusted. Worth a rule at the debrief: every filter addition must answer "what
does this look like when it fails?"

**Correction to the above: the first attempt at that fix silently did nothing,
and briefly made things worse.** Two of the six patches did not apply, and one
regression was introduced — `\b` in the patch strings reached Python as a
literal **backspace character** (0x08) rather than backslash-b, so the patterns
ended in an invisible control byte and could never match. `DISPATCH` went from
"wrong pattern" to "matches nothing at all", and `gate-read` never fired. The
file parsed, the patch script printed success, and `grep` showed the lines as
present — the broken byte is invisible in every one of those checks.

Caught only because the live stream kept labelling `no-mistakes axi status` as
`ship-gate` after I had claimed it was fixed. Repaired, then verified by
**running the filter against a table of known inputs** and reading the labels,
including the negative cases (`--help`, heredoc) that must stay silent.

This is the same lesson as the six defects it was meant to fix, aimed at myself:
*I confirmed the patch by the patch reporting success, not by observing the
behaviour change.* A monitor is exactly the tool where that is fatal, and I had
just finished writing that silence must never be ambiguous. Rule for the
debrief, now earned twice in one hour: **`watch.py` changes ship with a
before/after label table, not a syntax check.**

### The monitor died of a print, 8 Sep ~20:39

`UnicodeEncodeError` inside `print()`. Windows stdout is cp1252 here; one line
carrying a character outside it raised, and the exception propagated out of
`emit` and killed the whole watch. The supervisor went blind roughly at the
moment the workers came back.

Hardened: ask for UTF-8 via `sys.stdout.reconfigure`, and wrap `emit` so an
encoding failure degrades the line instead of ending the stream. Verified by
forcing a cp1252 stdout and emitting CJK and box-drawing characters.

**The same defect then bit my own ad-hoc replay script** ten minutes later,
which is the point: this is not a `watch.py` bug, it is a property of every
tool that prints transcript content on this machine. Transcripts carry worker
output, CLI tables and file contents — arbitrary Unicode by definition.
Anything in `supervision/` that prints them needs the same two lines.

Nothing was lost: the window was recovered by replaying all six transcripts
through `interesting()` filtered on row timestamp. Worth keeping as a habit —
**a watcher restart should always be followed by a timestamp-filtered replay of
the gap**, because `--from-now` is a guarantee about the future only.



---

## Instrument changes made during the run — the whole record

The contract says **observe, do not fix**, and I did not touch the contract, the
skills or the templates. Every change below is to `supervision/contract-monitor/
watch.py`, the *observer*. The rule protects the thing under test; a blind
instrument corrupts the record more than an edit to the instrument does. That
distinction is the whole justification, and it is worth stating explicitly
because "I fixed it mid-run" otherwise reads as a violation.

Five changes, in the order the run forced them.

**1. Six blind spots, after the restart streamed nothing.** Lelouch woke three
workers and the monitor emitted zero lines. Added/fixed: `terminal send` (the
wake path - the single most consequential action of the run was invisible);
`DISPATCH`, whose regex demanded `--task` immediately after `worker-start` and
so could never match the contract's own `worker-start --terminal … --task …`
form; `AskUserQuestion`, the tool that literally *is* the §6 approval gate;
`gate-read` split from `ship-gate` so a status poll stops reading as a ship;
truncation 90 -> 150 chars, because a line labelled `ship-gate` was showing a
`git log` with the matching token past the cut; and per-session tags, because
heartbeats from three worktrees were identical lines.

**2. That patch silently did nothing, and I had already reported it as done.**
`\b` in the patch strings reached Python as a literal backspace byte, so two
patterns ended in an invisible control character. `DISPATCH` went from wrong to
matching *nothing*. The file parsed, the script printed success, `grep` showed
the lines present. Caught only because the live stream kept mislabelling. Fixed,
then verified by running the filter over a table of known inputs including the
negative cases that must stay silent.

**3. Encoding hardening, after the monitor died of a `print()`.** Windows stdout
is cp1252; one line with a character outside it raised `UnicodeEncodeError` out
of `emit` and killed the whole watch - blind at the moment the workers came
back. Now: request UTF-8, and wrap `emit` so an encoding failure degrades the
line instead of ending the stream. The same bug then bit my own ad-hoc replay
script, which is the real lesson: it is a property of every tool here that
prints transcript content, not a `watch.py` bug.

**4. Noise rate-limiting, after measuring what the monitor cost.** See the token
section above. `hb` and `gate-read` now emit at most once per session per ten
minutes. They are throttled rather than removed so that silence still means
something.

**5. Nothing else.** No contract, skill, template or ticket was touched.

**What the sequence says about supervision.** Four of the five changes fixed the
same defect wearing different clothes: **the stream was silent when it should
have spoken.** A monitor whose absence of output is ambiguous between "nothing
happened" and "I cannot see this" is worse than no monitor, because it is
trusted. Every filter addition should have to answer: *what does this look like
when it fails?*

And the meta-lesson from change 2: I confirmed a patch by the patch reporting
success rather than by observing behaviour change - in the one tool where that
is fatal, minutes after writing that silence must never be ambiguous.
**`watch.py` changes ship with a before/after label table, not a syntax check.**



---

## Reported to C.C but not previously written down

**The memory monitor's locale bug (9 Sep ~19:50).** PowerShell returns free
memory as `1,76` under a French locale. The alarm compared it with
`awk 'BEGIN{print (f+0 < 1.2)}'`, and `f+0` on `"1,76"` evaluates to **1**. So
the effective threshold was "integer part below 2 GB", not 1.2 GB. It fired at
1.76 GB free — a false alarm — and the earlier 0.27 GB alarm and 2.18 GB recovery
were both correct only by luck. Fixed by normalising the comma before comparison,
skipping the check entirely on an empty reading rather than treating empty as
zero, and naming the top three consumers by process group instead of assuming
Brave.

**Caught only** by reading the alarm's own output against a number I already had.

---

## Tally

Eight instrument defects during run 2. Three of them were introduced by me while
fixing an earlier one:

    1  six filter blind spots (terminal send, DISPATCH, AskUserQuestion, …)
    2  that patch silently no-op'd — `` became a literal backspace     [self-inflicted]
    3  cp1252 crash killed the whole watch on a print
    4  noise throttle (hb/gate-read) — the token fix
    5  `sync --recover` classified as a throttled read
    6  board updates swallowed by the heartbeat label
    7  refusal signatures matched as bare keywords — flagged a workflow  [self-inflicted]
    8  memory alarm compared a locale decimal comma                      [self-inflicted]

Plus one non-code failure, recorded in the findings because its subject is a
Lelouch run: dismissing a correct silence alarm using mtime, which let a
two-hour-twenty stall run unreported.

---

## 9  `liveness.py` calls every non-workspace session "lelouch"

The tag expression falls through: a directory is `gate:` if its name contains
`worktrees-`, a worker if it contains `workspaces`, and **`lelouch` otherwise**.
So any session file under the project directory — including a stale one from an
earlier session that is still inside the four-hour window — prints as a second
`lelouch` row. Tonight that showed two orchestrator rows with different ages
(20:36 and 20:31) when there is exactly one live orchestrator.

Nothing was reported wrong because of it: I checked which file held the
`lavish-axi poll` call before drawing a conclusion, and it was the live one. But
the shape is the same as the mtime failure this afternoon — **a display that
looks like a measurement**. Two rows labelled `lelouch` invite the reading "the
orchestrator is fine, look, it wrote 20 seconds ago" when the row that wrote
20 seconds ago might be a dead session's tail.

Fix: label by file, not by directory — carry the session id into the tag so two
rows can never be confused for one subject, and drop files whose last row
predates the current run.

Not a Lelouch finding. Logged here because the debrief's one carried lesson —
*every instrument bug was a value I did not inspect* — now has a ninth instance,
and this one I caught before it cost anything, which is the first time.

---

## 10  `!! nonzero` is a label on the exit code, not on the outcome

Four occurrences in run 2 where a non-zero exit meant nothing had failed:

| exit | command | what actually happened |
|---|---|---|
| 127 | DuckDB trial | every result printed; `bc: command not found` ran after |
| 128 | `wa-hydrate` PR read | `mergeable=MERGEABLE state=CLEAN head=09a4a84` printed in full |
| 1 | `wa-app-shell` first look | directory listing complete; a later link in the chain failed |
| 1 | `lelouch` JSON parse | reading a task `.output` file that was not JSON |

Agents chain work as `cmd && cmd && cmd` and pipe through `head`/`tail`, so the
process exit status reports the *last* link, not the work. The monitor labels on
exit status because that is what a shell gives it.

I raised the error body from 110 to 300 characters after the DuckDB miss, and
that is the fix — **the label is a pointer, the body is the evidence**. The one
time I trusted the label alone I reported a successful trial as a failure to C.C.

Worth stating plainly because it is the mirror of finding 9: there a display
looked like a measurement, here a measurement looks like a verdict. Both are
cured the same way, by reading the thing the label is standing in for.

---

## 11  The monitor cannot see a gate failure, and I had the signal anyway

C.C found the `wa-app-shell` review timeout by reading the worker's narration.
The monitor said nothing. Three reasons, in increasing order of how much they are
my fault:

**It watches actions, not narration.** `watch.py` streams commands. The worker
*said* "the review step hit its 30-minute agent timeout" in assistant prose,
which the action stream does not carry by design.

**It never reads gate state.** The failure lived in the `no-mistakes` state
machine — `status: failed`, `phase: pre_push`, `pushed_head: ""` — reachable only
by running `axi status` against each active worktree. Nothing does.

**`axi status` exits 0 while reporting a failed run.** This is entry 10 inverted.
I logged that a non-zero exit is a label on the exit code rather than the
outcome, and never asked the converse: **a zero exit is not a claim of success
either.** Both halves are the same bug, and I only wrote down the half that had
already bitten me.

**And I had the signal.** At 23:0x the worker re-ran `axi run --intent` with an
identical intent, and I reported it as "a retry of the gate run — nothing to
surface unless it repeats a third time." A gate re-submitting the same intent
means the previous traverse died. That is not an ambiguous reading; it is one I
did not make.

Fix: a gate-state check per active worktree, alarming on `status: failed` and on
`active_for` past a threshold — a **positive check on a schedule**, which is
exactly what I demanded of the Lelouch resume-after-token-cap skill. I asked the
system under test for a discipline the instrument watching it did not have.

---

## 12  `gatewatch.py`, and the bug I caught in it before trusting it

Written to close entry 11: a positive check on gate state, every three minutes
per worktree, alarming on `status: failed`, on a step past 45 minutes, and on a
run id that changes while the previous run was still `running` — which is how a
discarded traverse looks from outside.

**The first version returned almost nothing.** `run` parsed; `status`, `head`,
`findings`, `step` and `active_for` all came back empty. The cause was one
missing flag: `grab()` used `re.search(pattern, out)` with patterns anchored on
`^`, and **without `re.M` that anchor matches only the start of the whole
document**. Every field in `axi status` lives on its own indented line, so
exactly one of them could ever match — the first.

That is the twelfth instance of the same thing, and the tally is now boring in a
useful way: a backspace where I expected a regex, mtime where I expected
activity, a noun where I expected a sentence, a comma where I expected a decimal
point, a zero exit where I expected success, a `merge-tree` output format I never
looked at, and now a regex flag. **Every one is a value I did not inspect.**

The difference this time is only that I ran the parser against a live gate and
printed every field before believing any of it. That is the whole discipline, and
it cost one command:

```
run=01M246PRRAEKG…  status=running  head=4fbdfb3d
findings='2 awaiting, 2 auto-fix'   step=review  fixing  48m55s  round='fix 2'
```

Had I skipped it, the watch would have run all night reporting nothing, and the
absence of alarms would have read as the absence of failures — which is the
precise error this instrument exists to prevent.

---

## 13  The memory ceiling kills the instruments too

`gatewatch.py` ran for forty minutes and was then **killed by the harness**:
*"Background command was stopped because the system is running low on memory."*
Built to watch a failure mode, killed by the one standing next to it.

Worth separating two mechanisms that this run has now shown both of:

- **The OS reclaiming memory** — what took six gate agents at 16:12 and left
  transcripts ending mid-sentence.
- **The harness pre-emptively stopping background tasks** — what took this one.
  Politer, announced, and equally blinding.

The second is the more dangerous of the two for a supervisor, because it targets
exactly the processes that have no user watching them. A foreground turn is
protected by someone waiting on it; a background monitor is the cheapest thing in
the room to stop.

**The failure mode this creates is silence that reads as calm.** Between the kill
and the restart there was no gate watch at all, and nothing anywhere said so
except a task notification I happened to be awake for. Had it arrived while I was
mid-report on something else, the log would show a monitor that simply stopped
having opinions — which is indistinguishable, at a distance, from a gate that
stopped having problems. That is [F-051](runs/run02/findings.md) in miniature:
death and quiet produce identical evidence.

What would fix it properly is a monitor that records its own liveness where
something else can read it — a heartbeat file with a timestamp, checked by
whatever reads the alarms. Restarting by hand works only while someone is awake
to notice, which is the opposite of the shift a night watch is for.

Restarted at 02:38 with 4.2 GB free. Brave had left the top-five consumers
entirely by then, which is also the answer to why the pressure existed.

---

## 14  CORRECTION to 12 and 13 -- the subprocess was not why the watch kept dying

Entry 12 said the gate watch was killed because it spawned a Node process per
poll, and that rewriting it against `state.sqlite` removed the cause. **The
sqlite version was killed too**, at 05:04, after 86 minutes -- with no subprocess
of any kind, and with **3.5 GB of physical memory free**:

```
free_MB=3,524
node 21 procs 1675 MB · claude 4 procs 1457 MB · chrome 16 procs 1297 MB
```

Three kills, three versions, one message each time: *"stopped because the system
is running low on memory."* The system was not low on memory on the third. So
whatever the harness measures to decide this, **it is not free physical RAM**,
and my explanation in entry 12 was a story that fit two data points and died on
the third.

What is actually observable is a lifetime, not a cause:

```
version 1 (subprocess)   ~40 min    killed
version 2 (subprocess)   ~50 min    killed
version 3 (sqlite only)  ~86 min    killed
```

Each watch does useful work and then stops. The third had just reported PR #11,
an `AWAITING AGENT` alarm on `wa-landing-route`, and two step transitions before
it went.

**The part that transfers, and is worth someone testing properly.** Lelouch
backgrounds its filtered `orchestration check --wait` as a harness task
([F-017](runs/run02/findings.md)). If long-running background tasks are reaped
on roughly this horizon regardless of footprint, **Lelouch's wait is being reaped
the same way** -- which would explain the re-arming, the shortened wait cycles it
described, and why the orchestrator keeps discovering it has no listener. I am
flagging that as a hypothesis with one supporting observation, not a finding. The
test is cheap: watch whether a Lelouch wait ever survives past ninety minutes.

**And the operational conclusion, which does not depend on the cause.** A watch
that has to be restarted by hand three times in one night is not a night watch.
Entry 13's fix -- a heartbeat file the monitor writes and something else reads --
is now the minimum, because the failure is recurrent rather than incidental, and
its signature is silence.

---

## 15  Five kills, three explanations, none of them right

Entry 12 blamed the subprocess. Entry 14 corrected that and offered a lifetime
pattern. Then I proposed a background-task cap, tested it by stopping the memory
watch to free a slot, and the gate watch was killed in that slot too.

Every hypothesis and what killed it:

| hypothesis | test | result |
|---|---|---|
| it spawns Node per poll | rewrote against `state.sqlite`, no subprocess | killed anyway |
| it uses too much memory | 3.5 GB free, commit 54%, at a kill | killed anyway |
| footprint decides | memory watch spawned 2 PowerShell procs/min, all night | never touched |
| the third task gets reaped | stopped the memory watch, ran it in the freed slot | killed after 85m |

Observed lifetimes: **40, 50, 86, 2, 85 minutes**. The two-minute one has no
explanation at all under any of the above.

**What I actually know**, stated without a theory attached: background tasks in
this harness are stopped with the message *"the system is running low on
memory"*, at times that do not correspond to free memory, footprint, subprocess
use, or task count. One task -- `watch.py`, the oldest -- has run for **eight
hours untouched** while five successive gate watches died around it.

That last fact is the only real regularity, and I am not going to build a fourth
theory on one observation. Writing down "the oldest task survives" would be
exactly the mistake of entries 12 and 14, and of [F-062](runs/run02/findings.md),
where I generalised a rule from a single refusal and closed off a design C.C had
argued for.

**What I am doing instead of theorising.** The run currently has zero `in_flight`
tickets and no active gate runs, so there is nothing for a gate watch to watch.
Rather than restart it a sixth time into an empty room, the gate check goes back
to being an inline sqlite read -- one command, on demand, when work resumes. It
costs a few seconds when I need it and cannot be reaped.

**The standing cost, unchanged and worth the debrief's attention.** A supervisor
in this harness cannot rely on a background monitor staying up. Every alarm I
built tonight has a failure mode where it simply stops, and the signature of that
is silence -- which is the one signal this whole log says cannot be trusted. The
heartbeat file from entry 13 is not an improvement any more, it is the only thing
that would make a night watch honest.

## 16  The silence alarm contradicted the evidence it carries

Found on restarting supervision after the supervisor session died of token
exhaustion, 10 Sep ~20:55. The last two alarms on the stream read:

```
!! SILENT   no activity in any weave-atlas session for 15m.
            Last ROW per session (not mtime): lelouch -1m; wa-05-resolve 15m; gate 16m; ...
```

Two defects in one line, and the second is the one that matters.

**The `-1m`.** `last_rows()` takes `now` once, then walks every `.jsonl` in
every session directory — 8.7 MB for lelouch alone. A session that writes a row
*during* that walk reads as newer than `now`, and `{age:.0f}` rounds -0.6 to
`-1`. Cosmetic in isolation. Not cosmetic in an alarm whose entire purpose,
since entry 13 and [F-044](runs/run02/findings.md), is to arrive with ages you
can trust without taking a second measurement. Clamped at zero.

**The wording, which is the real fault.** `quiet` is time since the last
**watched action** — `last_data`, updated only when the watcher emits a line.
`last_rows()` reports the age of the last **transcript row of any kind**. These
are different clocks, and the alarm printed one under a label describing the
other. So it announced *"no activity in any weave-atlas session for 15m"* about
a session whose last row was seconds old, and then attached the standing rule
*"anything over 15m is stalled"* — pointing that rule directly at lelouch, which
was alive and mid-turn.

A supervisor obeying its own instrument here concludes the orchestrator has
stalled and intervenes in a run that is fine. That is the mirror image of
[F-044](runs/run02/findings.md): there I talked a correct alarm down, here the
alarm invites a wrong intervention. Both come from an age whose meaning was
never stated.

**What I did not do: suppress it.** The obvious fix — hold the alarm when some
row is fresh — is the F-044 mistake with the reasoning automated. An
orchestrator can write prose for fifteen minutes while every worker under it is
dead, and that is precisely when the alarm must still fire. The alarm now names
the two measurements apart and says what each means:

```
!! SILENT   no watched ACTION in any weave-atlas session for 15m.
            Last ROW per session (not mtime): ...
            A row age over 15m is stalled; a fresh row with no action is
            thinking or prose, not health. Do not re-check with mtime.
```

**Same root cause as every other entry here.** A value I did not inspect —
this time a variable whose name (`quiet`) was accurate and whose printed label
was not. The instrument was correct; the sentence wrapped around it was the bug,
and a sentence is what the supervisor actually reads at 3 AM.

**Not live yet.** The running watch has had `watch.py` loaded in memory since
8 Sep 09:27Z and is now the longest-lived background task of the run. The patch
applies on its next start. I am not restarting a two-day-old healthy watch to
land a wording fix — the reaping behaviour in entry 15 says I might not get it
back.

## 17  The stream is annotated, not tabular -- do not count rows from it

Chased this after `npx -y lavish-axi design` appeared twice in the stream, once
as `!! npx` and once as `lavish`, and I suspected double emission.

It is not a bug. `watch.py` appends the npx flag **independently** of the
category loop, because the `!!` is an annotation on a call, not a classification
of it. One command that trips the npx rule therefore produces **two lines**. By
design, and the right design — the flag would be useless if it replaced the
label telling you what the call was.

**The hazard is mine, not the tool's.** I counted `!! npx` occurrences straight
out of the stream to answer "is Lelouch doing this systematically". That count
happened to be right, but *any* count of category rows is inflated by the npx'd
ones. **The stream is an annotated log, not a table. Counts come from the
transcripts.** Which is the monitor's own first rule — read files, not command
streams — and I broke it while auditing the monitor.

**Second false alarm in the same check.** I then looked for adjacent lines with
identical commands under different labels and found seven `hb`/`board` pairs.
Those are not duplicates either: the stream truncates commands, and a worker
sends `--type heartbeat` and a board update through the same
`orca orchestration send --from term_… --dispatch-capability …` prefix. The
first ninety characters are identical; the flag that distinguishes them is past
the cut. **Two genuinely different calls that render the same.** My comparison
was on the rendering.

Fourth time tonight I reached for a derived value instead of the source
([F-071](runs/run02/findings.md)'s exit code, [F-073](runs/run02/findings.md)'s
missing CLI command, [F-074](runs/run02/findings.md)'s lint duration, now this).
Every one was cheap to catch and every one was one command away from being
published wrong.

**The finding that came out of it, and it is a good one for the debrief.** One
`!! npx` in the entire watched stream — roughly two and a half days of Lelouch's
actions — against `lavish-axi` being installed directly at
`~/AppData/Roaming/npm/lavish-axi`. The scorecard's *"called tools directly, not
via npx"* check **passes**, and passes by a wide margin. A single ~28s lapse in
two and a half days is not a defect; it is a habit that took.

## 17b  CORRECTION to entry 17 -- the npx check was never sound

Entry 17 closed with *"the scorecard's 'called tools directly' check passes, and
passes by a wide margin -- one ~28s lapse in two and a half days."* Both halves
are wrong, and [F-078](runs/run02/findings.md) has the detail.

The count is **20 npx calls against 17 direct**, from the transcripts. I got "one"
by grepping `!! npx` out of the watch stream, which starts on 8 Sep and misses
most of the run -- breaking *"counts come from the transcripts"* in the same
entry that states the rule.

And the check was unsound regardless: `~/.claude/skills/lavish/SKILL.md` tells
the agent to invoke `npx -y lavish-axi`, and line 26 tells it to rewrite direct
invocations into npx ones. The scorecard was grading Lelouch for a decision its
skill made. **Drop the check or restate it as a question about documents.**

## 18  CORRECTION to entry 16 -- the watch's age was asserted, not read

Entry 16 closed by declining to land its own wording fix:

> The running watch has had `watch.py` loaded in memory since 8 Sep 09:27Z and
> is now the longest-lived background task of the run. The patch applies on its
> next start. I am not restarting a two-day-old healthy watch to land a wording
> fix -- the reaping behaviour in entry 15 says I might not get it back.

Both halves of that reason are wrong, and I never checked either. The task
`.output` files carry birth and last-write times and a `[killed]` sentinel on
the last line, so the whole lineage was one `Get-ChildItem` away.

**The ledger.** Every watch-format stream in this session's task directory:

| task | born (UTC) | last write | ran | ended |
|---|---|---|---|---|
| `bxbhojfqv` | 09-08 09:33:03 | 09-08 14:44:37 | 312m | `[killed]` |
| `bymx5ryaa` | 09-08 18:38:52 | 09-08 19:39:02 | 60m | `[killed]` |
| `by4189vs2` | 09-08 19:39:29 | 09-09 01:20:28 | 341m | `[killed]` |
| `bzdcv7sup` | 09-09 06:18:22 | 09-09 13:17:28 | 419m | `[killed]` |
| `bftyb60a9` | 09-09 13:17:53 | 09-09 16:47:21 | 209m | `[killed]` |
| `bysf7hkyf` | 09-09 16:49:39 | *alive* | 1897m+ | -- |

**The 8 Sep process died on 8 Sep, after five hours.** The process running now
was born **9 Sep 16:49:39Z**. Entry 16 was written on 10 Sep and described a
process that had been dead for a day and a half, through four intervening
restarts.

**"I might not get it back" is the wrong reading of entry 15.** Every restart
that was attempted came back, and fast: the kill-to-next-birth gaps are **27s,
25s and 2m18s**. The one long gap -- 01:20Z to 06:18Z -- is five hours of no
supervisor, not a failed restart. What entry 15 actually observed is that a
restarted watch does not *survive*; entry 16 promoted that to "may not *start*"
and then used the stronger claim to decline a fix.

**The method error is the one that generalises.** This is the house rule --
*read the artifact, never a derived value* -- failing on a value I derived from
my own memory. A remembered process age feels like an observation and is not
one, and it is worse than a stale file, because nothing about it looks stale.
Entries 12, 14 and 15 each died of a number I had not inspected. This one died
of a number I had not *taken*.

**What is now true, stated from the artifact.** The current watch has run
**31.6 hours**, against a previous best of 7.0 (`bzdcv7sup`). So entry 16's
instinct -- do not disturb it -- is better founded today than it was when
written, on evidence that did not exist then. That is a decision for C.C, and
the price is small and worth stating: a restart needs `--from-now`, so it costs
only the seconds it takes, and the entry-16 wording patch is still not live.

## 19  A verdict I hardcoded, on a query that could not answer the question

Checking whether `wa-graph-surface`'s backgrounded heartbeat loop was really
sleeping 300s between beats, I wrote this:

```python
gap = int((b - a).total_seconds())
print("VERDICT:", "spaced - background sleep held" if gap >= 240
                  else "BURST - sleep collapsed, liveness fabricated")
```

It printed **`BURST - sleep collapsed, liveness fabricated`** on a gap of
**161 seconds**, and I was one sentence away from reporting that to C.C.

**Two independent faults, either one fatal.**

**The threshold sentence.** A collapsed `sleep` produces a gap near *zero*. 161s
is not a burst by any reading — it is a *short* interval, which means something
entirely different and possibly nothing at all. I wrote a binary where the data
is continuous, then let the `else` branch name a conclusion the number does not
support. The instrument did not measure "burst"; it measured "not ≥240", and I
labelled that "burst" because those were the only two words I had written.

**The query, which is the worse one.** I asked for *heartbeats from
`term_42264eb3`*. The question was *heartbeats from the detached loop*. That
handle is shared: the worker sends inline heartbeats through it all run long. So
the two rows I differenced came from **different sources** — the loop's first
beat at 00:41:57 and an inline beat the worker sent by hand at 00:44:25. The gap
between them is a meaningless number, and no threshold applied to it could have
been right. The query was incapable of answering the question, and nothing in
its output said so.

**What fixed it.** Not a better threshold — a different output. The second
version prints no verdict. It correlates each heartbeat against the worker's own
tool calls and labels the row `INLINE (worker tool call at …)` or
`DETACHED LOOP (no worker tool call within 25s)`, and lets me do the judging.
That answered it immediately: every beat after the first was inline, and the
loop was dead ([F-084](runs/run02/findings.md)).

**Third instance of entry 16's fault, and I wrote entry 16.** There, `quiet` was
correct and its printed label described a different clock. Here the gap was
correctly computed and its printed label described a different phenomenon,
twice. The rule that keeps surviving: **an instrument may report measurements;
the moment it reports a conclusion, the conclusion is the thing that breaks**,
and it breaks silently, because a sentence looks like a finding.

Also worth its own line: **a shared identifier is not a source.** Terminal
handle, session id, branch name — each is used by more than one actor here, and
grouping by one of them and calling the result "the loop" is the same class of
error as counting `tasks-axi add` invocations instead of reading `backlog.md`.

## 20  CORRECTION to entry 16 -- the alarm's clock counts bytes, and entry 16 only fixed the sentence

Entry 16 found the silence alarm printing a label that described a different
measurement from the one it took, rewrote the sentence, and closed. Tonight the
alarm sat silent for **1h42m** while I watched, and checking why turned up the
half entry 16 never looked at.

**The observation.** The watch emitted nothing between 01:24:15Z and 03:06Z. No
`!! SILENT` fired, though `SILENCE_AFTER` is 900s. In that window the weave-atlas
sessions wrote **258 transcript rows** — 108 from lelouch, 150 from
`wa-entity-projection`.

**The cause, at `watch.py:346`:**

```python
with f.open("r", encoding="utf-8", errors="replace") as fh:
    fh.seek(start)
    chunk = fh.read()
    offsets[f] = fh.tell()
last_data = time.time()          # <- before parsing, before interesting(),
                                 #    before the hb/gate-read throttle
```

`last_data` is the alarm's clock. It is re-armed by **any byte appended to any
watched transcript** — prose, thinking, tool results, a worker's blocking wait —
and the alarm it drives says *"no watched ACTION in any session for Nm"*. Those
are different quantities, and N is the byte one.

**Entry 16 wrote the better sentence over the unchanged clock.** Its patch is
still not live (see entry 18), so when it does start it will print *"no watched
**ACTION**"* next to a number that has never measured actions. Entry 16 made the
label more specific and therefore **more wrong**: the old wording was vague
enough to be merely unhelpful; the new one names a measurement the code does not
take.

**And it declined a suppression the code already had.** Entry 16's proudest
paragraph:

> **What I did not do: suppress it.** The obvious fix — hold the alarm when some
> row is fresh — is the F-044 mistake with the reasoning automated. An
> orchestrator can write prose for fifteen minutes while every worker under it
> is dead, and that is precisely when the alarm must still fire.

That suppression is already there, structurally, in `last_data`. The exact
scenario named as must-fire — an orchestrator writing prose over dead workers —
**cannot** fire this alarm, because the prose keeps re-arming its clock. I
argued against adding a hold that the instrument had been applying all along,
and the argument read as rigour because it was about a line of code I never
opened.

**What the alarm does still catch, stated fairly.** If everything stops writing,
`last_data` freezes and it fires. That is [F-026](runs/run02/findings.md)'s
three-hour dead run, and the alarm would catch it. It is a **run-stopped**
detector, and a sound one. It is not an **action-stopped** detector, and both its
old and new sentences claim to be.

**Not fixing it mid-run.** The same reason as always — the running watch is now
34 hours old and re-casting the instrument that is producing the record is worse
than a known, documented gap. Written down instead, which is the standing trade
this log keeps making. Tonight the gap costs nothing: `parkwatch.py` measures
the parked session's transcript age directly and per-session, which is the
measurement the global alarm was being asked for and never took.

**Third time the same shape.** Entry 16: a name that was accurate and a printed
label that was not. Entry 19: a threshold sentence and a query that could not
answer the question. This: a corrected sentence over an uncorrected clock. The
sentence is always the part I fix, because the sentence is the part I read.

## 21  Seed every scan with a known positive

Chasing whether every fresh worktree pays a missing-`node_modules` tax, I
scanned nineteen worker transcripts for the shell's missing-binary message:

```python
pat = re.compile(r"n'est pas reconnu|is not recognized", re.I)
```

It reported `wa-docblock-stranded` as clean. I had watched that session throw
three of those errors ninety seconds earlier.

**The bug:** the shell writes `n’est pas reconnu` with U+2019, and I typed
U+0027. A whole-corpus scan, silently near-empty, with no error and no warning —
the exact failure shape of entries 16, 19 and 20, and this time in a throwaway
query rather than a committed instrument.

**What caught it was not care. It was an accident of ordering**: the known
positive happened to be in the sample, and its row said `-`. Had I run the same
scan an hour earlier, before that session existed, every row would have read
clean and I would have concluded the tax is rare. The regex would never have
been questioned, because a scan that finds nothing looks exactly like a
phenomenon that is not there.

**The practice, which costs one line:** before believing a corpus scan, point it
at a case you have already seen with your own eyes and confirm it fires. If the
known positive does not light up, the pattern is wrong, not the corpus. This is
the same discipline as *read the artifact* applied to the reading instrument
itself — and it is the only one of these four entries that yields a check I can
actually run every time rather than a resolution to be more careful.

**Footnote: the hypothesis died anyway, and correctly.** With the apostrophe
fixed, 4 of 19 sessions hit a missing-binary error, and in all four `npm install`
had already been issued **before** the first error (-239s, -520s, -752s, -51s).
So it is not an empty worktree; it is a worker starting checks before its
install finishes. Four instances, all self-corrected, no cost to the run — an
anecdote, and deliberately not written into the findings file.

## 22  A latch is right for an episode and wrong for a quantity

`fanwatch.py` fired once, at 14:00:50, on `free 0.87 GB`. Then it went quiet and
stayed quiet while memory sat at 1.58, 1.65, 1.34 GB — all below its own 2.0 GB
floor. The alarm was mute for the entire window it existed to cover.

**The code:**

```python
if free < FREE_GB_FLOOR and not low_reported:
    emit(...); low_reported = True
elif free >= FREE_GB_FLOOR + 0.5:
    low_reported = False
```

`low_reported` only clears **upward**, past 2.5 GB. Memory never recovered that
far, so after the first alarm nothing below the floor could ever fire again —
including a drop to 0.1 GB.

**Where the pattern came from, and why it was wrong here.** I copied it from
`watch.py`'s silence alarm, where entry 15's *"fire once per silent episode,
then re-arm when the run comes back"* is correct: silence is binary, a session
either is writing or is not, and repeating the same alarm every poll is the
noise that alarm was built to replace. Free memory is not binary. It is a
continuous quantity that can keep degrading, and *"already told you"* is not a
reason to stay silent about a value that has since halved.

**The fix keeps the level, not a flag:**

```python
first = low_at is None and free < FREE_GB_FLOOR
worse = low_at is not None and free <= low_at - REALARM_DROP_GB   # 0.4 GB
```

Re-alarm on material further degradation, naming the previous reading so the
trend is legible in the line itself; clear only on real recovery. Validated
against six seeded cases before arming, including the exact 0.87 → 1.58 pair
that produced the bug — which must *not* fire, because that direction is
improvement.

**What found it was not the alarm.** It was reading the alarm's own output file
and noticing two lines where there should have been six. An alarm that has gone
mute produces exactly what a healthy system produces, which is the thesis of
this entire log and which I keep rediscovering from the other side: entry 16's
alarm said the wrong thing, entry 20's clock measured the wrong thing, and this
one said nothing at all. **Silence from an instrument is the one output that
never proves anything**, and the only defence is to go and look at it.

**Generalises to every threshold alarm here.** `parkwatch`'s quiet alarm has the
same latch and it is correct there for the same reason `watch.py`'s is — quiet
is an episode. Anything measuring a level rather than a state needs this shape
instead.

## 23  Three kills, one stated reason, and the reason is measurably wrong

Entry 15 counted five kills and three explanations, none of which held. Here is
a fourth, and this one is separable from the others because the harness *told me
why* and the claim is checkable.

The silent run logger was killed three times in one evening. Every notice read:

```
Background command "Restart the silent run logger" was stopped
because the system is running low on memory
```

**Free physical memory, measured at the third restart, seconds after the notice:**

```
4.22 GB free of 15.62 GB
```

C.C had already said it independently, before I measured: *"memory wasn't low at
all when your logger got closed, nothing is running on the PC, brave was running
but with very low memory usage. restart the logger, if it closes, it's not
memory."* They were right and I had been taking the notice at face value.

**The contrast that makes this a finding rather than a grievance.** Memory
pressure on this machine is real and documented — [F-050](runs/run02/findings.md)
records 0.42–1.19 GB free across a window where six Claude processes fell to
four, with Brave holding 5494 MB. That was a genuine ceiling. Tonight's 4.22 GB
is not, and the reaper said the same sentence both times.

So the string is **not a measurement**. It is a fixed label attached to a kill
event, and it reads exactly like a diagnosis. That is the same defect as
[F-108](runs/run02/findings.md)'s *"PR remains open"* — a status line asserting
a remote condition it had not checked, at the moment it stopped looking — and
[entry 18](#)'s asserted-not-read age. Third instance of one shape, now found in
three separate systems: the ship gate, my own watch, and the agent harness.

**What it costs here.** An unattended observation window cannot be trusted to
exist. The logger is the instrument that covers exactly the periods I am not
watching, so a logger that dies silently converts "nothing happened" into
"nothing was recorded" without changing the output. Entry 22's thesis again from
a third side: **silence from an instrument never proves anything.**

**What I could not establish.** I have no trigger. Three kills, no established
correlation with context compaction, with the running builder, or with anything
else measured. I looked, I do not have it, and the honest state is that the
cause is unknown rather than that the cause is not memory. Only the *stated*
reason is disproved.

**Operating rule, effective now:** never quote the harness's kill reason in a
finding. `fanwatch.py` is the only source here that actually measures free
memory; if a kill is to be attributed to RAM, the attribution comes from
fanwatch's reading at that timestamp, or it is not made. Where no reading
exists, the entry says the cause is unknown — which is what entry 15's three
wrong explanations cost and what this one is meant to stop repeating.
