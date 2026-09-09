# Supervisor instrument log — run 2

Not run findings. This is the supervisor's own tooling (`watch.py`, the liveness
and memory monitors) breaking and being repaired while it watched run 2. It is
split out of `runs/run-02-findings.md` so the debrief reads only evidence about
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
