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
import sys
import time
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"


def slug_dir(project: Path) -> Path | None:
    """Claude Code's per-project transcript directory.

    The slug is the absolute path with separators replaced, and non-ASCII
    mangled, so match on the trailing project name rather than rebuilding it.
    """
    name = project.resolve().name
    hits = [d for d in PROJECTS.iterdir() if d.is_dir() and d.name.endswith(name)]
    return max(hits, key=lambda d: d.stat().st_mtime) if hits else None


def sessions(d: Path) -> list[Path]:
    return sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)


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


def events(rs: list[dict]) -> list[tuple[str, str]]:
    """(kind, detail) for the things worth watching."""
    out = []
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
                    out.append(("SKILL", inp.get("skill", "?")))
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


def _before(ev, marker, skills=None, kind=None) -> bool:
    """Did `skills` (or an event of `kind`) happen before the first `marker`?"""
    first = next((i for i, (k, _) in enumerate(ev) if k == marker), None)
    if first is None:
        return False  # never reached the marker: nothing to have preceded it
    head = ev[:first]
    if kind:
        return any(k == kind for k, _ in head)
    return any(k == "SKILL" and d in skills for k, d in head)


# One row per thing we shipped, so a run scores the fixes rather than vibes.
SCORECARD = [
    # intake
    ("grilled before dispatching",
     lambda e: _before(e, "DISPATCH", {"grilling", "grill-with-docs", "grill-me"})),
    ("wrote the glossary (domain-modeling)",
     lambda e: _skill(e, "domain-modeling", "grill-with-docs")),
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
    # perf regression: npx costs 28s a call, the contract says call directly
    ("called tools directly, not via npx",
     lambda e: not any(k == "npx-regression" for k, _ in e)),
]


def report(project: Path, verbose: bool) -> int:
    d = slug_dir(project)
    if d is None:
        print(f"! no transcripts yet for {project.name}", file=sys.stderr)
        return 1

    all_events: list[tuple[str, str]] = []
    print(f"{project.name}  ({len(sessions(d))} session(s))\n")
    for s in sessions(d):
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
    print("\n  scorecard")
    for label, check in SCORECARD:
        print(f"    {'PASS' if check(all_events) else '  --'}  {label}")
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
