# Handoff — read this first on a fresh session

Current as of 15 Sep. Supersedes the forward-looking parts of
`runs/run02/RESUME.md`, which is now a historical run-02 record only.

## What is done

**Run 02 is closed** — findings, scorecard, instrument-log all in
`runs/run02/`, on master.

**v2 is built and merged to master** (PR #29, merge commit `00ec649`). It is
the run-02 debrief turned into changes:

- **The contract** (`geass/harness/CLAUDE.md`): the milestone gate (§3), bounded
  reporting + attribution (§0), model tiering (§6), the wait floor (§7),
  `succeeded`-means-pushed (§W), the role gate now sending workers to §11.
- **Six skills** in `geass/skills/own/`: `britania-board`, `britania-vitals`,
  `britania-restore`, `britania-resume`, `britania-afk`, `grill-with-lavish`.
- **`docs/agents/harness-gotchas.md`** in the payload — the eleven facts that
  used to live in one agent's private memory.
- **`observe.py`** split transcript checks from repository checks; stale docs
  removed; `worktree-retire.sh` promoted into `contract-monitor/`.

**The supervisor side (`contract-monitor/`) is current to v2** — `SKILL.md`
knows the new rules, which instruments to arm, and the britania skills.

## The geass command — pip-free, and why

Microsoft Defender blocks the pip-installed `geass.exe` ("Access denied"), and
blocks pip's network reinstall. **Do not fight pip.** There is a wrapper at

    C:\Users\...\Python312\Scripts\geass.cmd

that runs `python -X utf8 -m geass.cli` against the murphy-c2 checkout — a
different exe (`python.exe`) that Defender is fine with. It loads the checkout
(= current master = v2), proven by `geass watcher` existing. No pip, no
download, nothing Defender objects to. If the checkout ever moves, edit that one
line in the .cmd.

## Run 03

**Subject: DCrafter** — a template/mask-based wordlist generator (CLI + WebUI)
with keyspace stats. A legitimate security-education tool. Its design is
deliberately NOT decided — the first thing the run does is get grilled, which is
the stage v2 changes most and the whole reason a fresh app was chosen over
continuing weave-atlas.

`~/orca/projects/DCrafter`: git-initialized, README, initial commit. The user is
casting it by hand (`geass cast`), then starting a Lelouch session from the Orca
GUI (`+` → Claude agent). **Cast happens before the session opens** — the hook
and CLAUDE.md are read at session start.

## Immediate next actions (supervisor)

1. **When the DCrafter session has started**, create `runs/run03/` with
   `findings.md` and `index.md`. Numbering restarts at **F-001**. The filing
   convention is in `contract-monitor/SKILL.md` under "Where findings go".
2. **Arm the watchers**: `watch.py DCrafter --from-now` under the Monitor tool,
   `persistent: true`. Add `fanwatch.py` once more than two builders run at once.
3. **Watch for the v2 rules specifically** — the table in
   `contract-monitor/SKILL.md` under "What v2 added" lists each new rule and what
   a violation looks like. The milestone gate and `domain-modeling`-every-round
   are the two most worth confirming, since run 02 failed both.

## Open questions carried into run 03

- `no-mistakes axi run` re-attach: can a blocking wait observe a gate you do not
  own? Test on a throwaway branch; the risk is a duplicate run.
- Graphify: worth trying, decided by one measurement — regeneration cost per
  rebase. Measure on weave-atlas (parked, a real repo with history), not DCrafter.
- `domain-modeling` invocation count: run 03's scorecard now counts it. Run 02
  was zero in six days; a healthy number is what we are trying to learn.
