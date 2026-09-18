#!/usr/bin/env python3
"""Watch a Lelouch run from outside it.

Claude Code appends every session to ~/.claude/projects/<slug>/<id>.jsonl as it
runs, so a run can be observed without the user relaying anything: which skills
actually fired, in what order, and whether the gates held.

    python observe.py <project-path> [--follow]

The point is to answer questions the last smoke test could not. "Did it really
invoke to-tickets, or improvise a DAG?" is a fact in the transcript, not a
judgement call.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"


def slug_dirs(project: Path) -> list[Path]:
    """Every transcript directory Claude Code writes for this project.

    The slug is the absolute path with separators replaced, and non-ASCII
    mangled, so match on the project name rather than rebuilding it. A worker
    started `--worktree current` shares the project's own slug; one started in a
    new worktree gets its own, `...-workspaces-<project>-<branch>`, where the
    name sits in the middle -- so the test is containment, not a suffix.

    F-073: this used to end `max(hits, key=st_mtime)` and hand back one
    directory. Run 3 matched twelve, eleven of them builder worktrees, and the
    scorecard read the coordinator's alone -- so no dispatched builder has ever
    been scored, and the `skills invoked` line was coordinator-only while
    reading as the run's. Merge them all instead.
    """
    name = project.resolve().name
    return sorted(d for d in PROJECTS.iterdir() if d.is_dir() and name in d.name)


def started_at(path: Path) -> str:
    """When a session really began, taken from the transcript's own clock.

    F-073: ordering came from `st_mtime`, which records the *last* append, so a
    session that ran nine hours sorted behind short ones that started long after
    it -- and every "X before Y" row could be inverted by how long a session
    ran, not by when anything happened. Transcript timestamps are ISO-8601 in a
    fixed shape, so string order is time order. Summary records carry no clock
    and can sit at the head of a resumed file, hence the scan.

    The mtime fallback is for a file with no clock anywhere: it keeps such a
    session roughly in place rather than sorting it to the front of the run.
    """
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            stamp = r.get("timestamp")
            if isinstance(stamp, str) and stamp:
                return stamp
    when = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return when.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def sessions(dirs: list[Path]) -> list[Path]:
    """Every session across every matching slug, in real chronological order."""
    return sorted((p for d in dirs for p in d.glob("*.jsonl")), key=started_at)


def rows(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def failed_calls(rs: list[dict]) -> set[str]:
    """tool_use ids whose result came back an error.

    A call is not an invocation. A `disable-model-invocation` skill produces a
    tool_use block and then a refusal, so scoring the block alone credits a skill
    that never ran -- which is how run 2's scorecard reported intake as having
    started at the moment it had died.

    Still live in v2, and more so: the payload now ships four user-only skills
    (`britania-afk`, `-resume`, `-restore`, `brief`), so there are four ways for
    a refused call to look like a successful one.
    """
    bad = set()
    for r in rs:
        content = (r.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for x in content:
            if not isinstance(x, dict) or x.get("type") != "tool_result":
                continue
            if x.get("is_error") or "<tool_use_error>" in str(x.get("content", "")):
                if x.get("tool_use_id"):
                    bad.add(x["tool_use_id"])
    return bad


def events(rs: list[dict]) -> list[tuple[str, str]]:
    """(kind, detail) for the things worth watching."""
    out = []
    bad = failed_calls(rs)
    for r in rs:
        if r.get("type") not in ("user", "assistant"):
            continue
        content = r.get("message", {}).get("content")
        if isinstance(content, str):
            if r["type"] == "user" and content.strip():
                out.append(("user", content.strip()[:160]))
            continue
        if not isinstance(content, list):
            continue
        for x in content:
            if not isinstance(x, dict):
                continue
            kind = x.get("type")
            if kind == "text" and r["type"] == "assistant" and x.get("text", "").strip():
                out.append(("say", x["text"].strip()[:160]))
            elif kind == "text" and r["type"] == "user" and x.get("text", "").strip():
                out.append(("user", x["text"].strip()[:160]))
            elif kind == "tool_use":
                name = x.get("name", "?")
                inp = x.get("input", {}) or {}
                if name == "Skill":
                    ok = x.get("id") not in bad
                    out.append(("SKILL" if ok else "skill-refused",
                                inp.get("skill", "?")))
                elif name == "Bash":
                    cmd = " ".join(str(inp.get("command", "")).split())
                    # The contract says call installed tools directly; npx
                    # re-checks the registry at ~28s a call.
                    if "npx" in cmd and any(
                        t in cmd for t in ("tasks-axi", "gh-axi", "lavish-axi")
                    ):
                        out.append(("npx-regression", cmd[:120]))
                    for marker, label in (
                        ("orchestration worker-start", "DISPATCH"),
                        ("orchestration task-create", "task-create"),
                        ("orchestration check", "wait"),
                        ("tasks-axi hold", "HOLD"),
                        ("tasks-axi add", "ticket+"),
                        ("tasks-axi done", "ticket-done"),
                        ("lavish-axi", "lavish"),
                        ("no-mistakes", "ship-gate"),
                    ):
                        if marker in cmd:
                            out.append((label, cmd[:120]))
                            break
    return out


def _skill(ev, *names) -> bool:
    return any(k == "SKILL" and d in names for k, d in ev)


def _before(ev, marker, skills=None, kind=None):
    """Did `skills` (or an event of `kind`) happen before the first `marker`?

    None when the marker has not occurred: an ordering question is unanswerable
    until the thing it orders against exists. Reporting that as a failure is the
    "too early is not failed" mistake, printed straight onto the scorecard.
    """
    first = next((i for i, (k, _) in enumerate(ev) if k == marker), None)
    if first is None:
        return None
    head = ev[:first]
    if kind:
        return any(k == kind for k, _ in head)
    return any(k == "SKILL" and d in skills for k, d in head)


# One row per thing we shipped, so a run scores the fixes rather than vibes.
SCORECARD = [
    # intake
    # `grill-with-lavish` credits this row exactly as a direct `grilling` call
    # does. The comment that stood here assumed the wrapper always nests a
    # literal `grilling` call, so crediting the underlying skill alone was
    # enough. F-072 measured that false: of run 3's two wrapper calls only the
    # second nested one, and the one that did not was the intake -- two hours
    # before the first dispatch. So the row that certifies the approval gate,
    # the single thing this monitor most exists to prove, scored a correct run
    # a silent FAIL.
    # This is not the bug that got `grill-me` and `grill-with-docs` dropped: a
    # refused call cannot reach this row, because `events()` files it as
    # `skill-refused` rather than `SKILL`.
    ("grilled before dispatching",
     lambda e: _before(e, "DISPATCH", {"grilling", "grill-with-lavish"})),
    # Was one row called "wrote the glossary (domain-modeling)" while measuring
    # only the skill call. Run 2 is exactly where those diverge: CONTEXT.md was
    # written -- by hand -- and `domain-modeling` was never invoked once in six
    # days. The row read `--`, which was correct about the skill and silently
    # wrong about the artifact it was named for. Two rows now, each named for
    # what it actually measures. The artifact half lives in PROJECT_CHECKS,
    # because it is a fact about the repo rather than about the transcript.
    ("invoked domain-modeling", lambda e: _skill(e, "domain-modeling")),
    # #13 - the pipeline skills are reachable now
    ("invoked to-spec",   lambda e: _skill(e, "to-spec")),
    ("invoked to-tickets (not improvised)", lambda e: _skill(e, "to-tickets")),
    # #6 - the approval gate
    ("showed a Lavish artifact", lambda e: any(k == "lavish" for k, _ in e)),
    ("Lavish shown BEFORE first dispatch",
     lambda e: _before(e, "DISPATCH", kind="lavish")),
    # dispatch
    ("dispatched a worker", lambda e: any(k == "DISPATCH" for k, _ in e)),
    ("filed tickets in the backlog", lambda e: any(k == "ticket+" for k, _ in e)),
    # #14 - the user relationship
    ("addressed the user as C.C", lambda e: any(k == "say" and "C.C" in d for k, d in e)),
    ("held a decision rather than losing it", lambda e: any(k == "HOLD" for k, _ in e)),
    # perf regression: the contract says call an installed tool directly.
    # Measured delta on this machine is ~1.5s per call (0.9s direct against
    # 2.4s through npx), not the 28s this comment claimed for years -- real,
    # paid on every call, and nowhere near the figure that justified the rule.
    ("called tools directly, not via npx",
     lambda e: not any(k == "npx-regression" for k, _ in e)),
]


# Facts about the repository rather than about the transcript. Kept apart on
# purpose: a transcript says what an agent *did*, a working tree says what
# actually *exists*, and run 2 proved those are different questions.
PROJECT_CHECKS = [
    ("glossary exists and is tracked", lambda p: _glossary(p)),
    ("a milestone is stated in CONTEXT.md", lambda p: _milestone(p)),
]


def worktree(project: Path) -> Path | None:
    """The project's actual directory, or None if it cannot be found.

    The transcript side of this tool only ever needed `project.name` -- the
    slug match works from a bare name -- so `observe.py weave-atlas` has always
    been a legitimate invocation. The repository checks need a real directory,
    and resolving a bare name against the current one silently answers about the
    wrong repo: the first version of these rows reported a tracked glossary as
    missing, which is the exact false-failure this whole change exists to stop.

    So: use it if it is a directory, look for it beside the known projects, and
    otherwise say nothing rather than something wrong.
    """
    if project.is_dir():
        return project.resolve()
    guess = Path.home() / "orca" / "projects" / project.name
    return guess.resolve() if guess.is_dir() else None


def _tracked(project: Path, rel: str) -> bool:
    try:
        r = subprocess.run(["git", "-C", str(project), "ls-files", "--error-unmatch", rel],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def _glossary(project: Path) -> bool | None:
    """Present AND tracked -- because existing is not the bug that happened.

    F-038: `CONTEXT.md` was written, and gitignored. Every worker was told to
    read a glossary that was not in its worktree, nobody errored, and they each
    named things their own way. A check for mere existence passes straight
    through that.
    """
    root = worktree(project)
    if root is None:
        return None
    f = root / "CONTEXT.md"
    if not f.exists():
        return False
    return _tracked(root, "CONTEXT.md")


def _milestone(project: Path) -> bool | None:
    """Is a product milestone written down at all?

    Weak on purpose. Whether a run *advanced* the milestone is not derivable
    from here, and inventing a proxy for it would be worse than admitting the
    gap. What IS checkable is whether one was ever stated -- and run 2 shipped
    an MVP with no milestone recorded anywhere, which is why its scorecard could
    pass every row while saying nothing about the thing that mattered.
    """
    root = worktree(project)
    if root is None:
        return None
    f = root / "CONTEXT.md"
    if not f.exists():
        return False
    text = f.read_text(encoding="utf-8", errors="replace").lower()
    return any(w in text for w in ("## milestone", "milestone:", "## mvp", "mvp:"))


def report(project: Path, verbose: bool) -> int:
    dirs = slug_dirs(project)
    if not dirs:
        print(f"! no transcripts yet for {project.name}", file=sys.stderr)
        return 1

    all_events: list[tuple[str, str]] = []
    found = sessions(dirs)
    print(f"{project.name}  ({len(found)} session(s) across {len(dirs)} slug(s))\n")
    for s in found:
        ev = events(rows(s))
        if not ev:
            continue
        all_events += ev
        acts = [(k, v) for k, v in ev if k not in ("say", "user")]
        print(f"  {s.stem[:8]}  {len(ev):>4} events, {len(acts):>3} actions")
        if verbose:
            for k, v in acts:
                print(f"      {k:<12} {v}")

    print("\n  skills invoked:", ", ".join(dict.fromkeys(d for k, d in all_events if k == "SKILL")) or "none")
    refused = dict.fromkeys(d for k, d in all_events if k == "skill-refused")
    if refused:
        print("  skills REFUSED:", ", ".join(refused), "(called, but never ran)")
    # How often, not merely whether. A boolean cannot express "this should fire
    # several times in a run" -- and picking a threshold before ever seeing a
    # healthy run would be inventing one, not earning it. Count first; a rule
    # can come later, from data.
    counted = Counter(d for k, d in all_events if k == "SKILL")
    if counted:
        print("\n  skill calls:",
              "   ".join(f"{name} x{n}" for name, n in counted.most_common()))

    print("\n  scorecard")
    for label, check in SCORECARD:
        v = check(all_events)
        mark = " n/a" if v is None else ("PASS" if v else "  --")
        print(f"    {mark}  {label}")
    if worktree(project) is None:
        print(f"     ?    repository checks skipped -- cannot find {project.name} on disk")
        print(f"          pass its path, not just its name, to run them")
    else:
        for label, check in PROJECT_CHECKS:
            v = check(project)
            mark = " n/a" if v is None else ("PASS" if v else "  --")
            print(f"    {mark}  {label}")
    print("\n  n/a = not reachable yet, not a failure")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--follow", action="store_true", help="re-report every 30s")
    a = ap.parse_args()

    p = Path(a.project)
    if not a.follow:
        return report(p, a.verbose)
    while True:
        print("\033[2J\033[H", end="")
        report(p, a.verbose)
        time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())
