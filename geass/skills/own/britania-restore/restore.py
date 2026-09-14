#!/usr/bin/env python
"""britania-restore -- rebuild a session's working state from durable sources.

For a session that has no continuity: a fresh terminal after a crash, a power
cut, or a deliberate `/clear`. It answers "where was I" **without asking the
previous session anything**, because the previous session may not have got the
chance to say.

    restore.py                 the briefing
    restore.py --json          same, machine-readable

**It derives; it never replays a record.** Nothing here reads a handoff file
that a dying session was supposed to write, because the case this exists for is
exactly the case where it did not. Every line comes from something that survives
independently:

    tasks-axi          the backlog, and the decisions held against it
    orca               Runs, terminals, workers
    ~/.no-mistakes     where each branch stands in the ship gate
    git                the branch and whether the tree is dirty
    CONTEXT.md         the vocabulary the tickets are written in

**What it cannot recover is the conversation.** That is not a gap to engineer
around -- it is the reason the contract puts decisions in the backlog instead of
leaving them in chat. If something mattered and was never written down, it is
gone, and the honest response is to say so rather than to reconstruct a
plausible version of it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE_DB = Path(os.path.expanduser("~/.no-mistakes/state.sqlite"))


def sh(cmd: list[str], cwd: str | None = None, timeout: int = 60) -> str | None:
    """Resolve the executable (Windows .CMD shims) and force UTF-8 (a locale
    codec raises on an accented path, inside a thread, and returns empty)."""
    exe = shutil.which(cmd[0])
    if exe is None:
        return None
    try:
        p = subprocess.run(
            [exe, *cmd[1:]], cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout if p.returncode == 0 else None


def orca(args: list[str], cwd: str | None = None) -> dict:
    raw = sh(["orca", *args], cwd=cwd)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict) or data.get("ok") is False:
        return {}
    return data.get("result", data) or {}


def same_project(a: str | None, b: str) -> bool:
    if not a:
        return False
    norm = lambda p: os.path.normcase(os.path.abspath(str(p))).replace("\\", "/").rstrip("/")
    return norm(a) == norm(b)


# ------------------------------------------------------------------- the Run


def find_run(project: Path) -> tuple[str | None, str, str]:
    """(run_id, how_it_was_found, objective) for this project's Run.

    This is the awkward one. **A Run carries no project identity** -- only an
    id, a free-text objective and a `coordinator_handle` -- and a machine with
    several projects has several Runs. Two signals, strongest first:

    1. Its coordinator handle is a terminal living in this project. Exact, but
       it fails in precisely the situation restore exists for: after a crash the
       old terminal is gone, so the handle points at nothing.
    2. Its objective names the project. A convention rather than a guarantee,
       which is why the briefing prints *how* the Run was identified and asks
       for confirmation instead of binding silently.
    """
    runs = orca(["orchestration", "run-list", "--json"]).get("runs") or []
    runs.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    if not runs:
        return None, "no Runs exist", ""

    here = {
        t.get("handle")
        for t in (orca(["terminal", "list", "--json"]).get("terminals") or [])
        if isinstance(t, dict) and same_project(t.get("worktreePath"), str(project))
    }
    for r in runs:
        if r.get("coordinator_handle") in here:
            return r.get("id"), "its coordinator terminal is in this project", str(r.get("objective") or "")

    name = project.resolve().name.lower()
    for r in runs:
        if name in str(r.get("objective") or "").lower():
            return r.get("id"), f"its objective names {project.resolve().name} -- CONFIRM before binding", str(r.get("objective") or "")

    newest = runs[0]
    return newest.get("id"), "GUESS: newest Run on the machine, project unverified", str(newest.get("objective") or "")


def bound_run(project: Path) -> str | None:
    run = orca(["orchestration", "run-current", "--json"], cwd=str(project)).get("run")
    return (run or {}).get("id") if isinstance(run, dict) else None


# ------------------------------------------------------------------ the rest


def git_state(project: Path) -> dict:
    branch = sh(["git", "-C", str(project), "rev-parse", "--abbrev-ref", "HEAD"])
    dirty = sh(["git", "-C", str(project), "status", "--porcelain"])
    ahead = sh(["git", "-C", str(project), "rev-list", "--count", "@{u}..HEAD"])
    return {
        "branch": (branch or "?").strip(),
        "dirty": len([ln for ln in (dirty or "").splitlines() if ln.strip()]),
        "unpushed": (ahead or "").strip() or "?",
    }


def glossary(project: Path) -> dict:
    path = project / "CONTEXT.md"
    if not path.exists():
        return {"present": False, "tracked": False, "terms": 0}
    tracked = sh(["git", "-C", str(project), "ls-files", "--error-unmatch", "CONTEXT.md"]) is not None
    text = path.read_text(encoding="utf-8", errors="replace")
    in_vocab, terms = False, 0
    for line in text.splitlines():
        if line.startswith("## "):
            in_vocab = "vocab" in line.lower() or "glossar" in line.lower()
        elif in_vocab and line.strip().startswith(("- ", "**", "### ")):
            terms += 1
    return {"present": True, "tracked": tracked, "terms": terms}


def board(project: Path) -> str:
    """Reuse britania-board rather than re-deriving the same three registries."""
    script = HERE.parent / "britania-board" / "board.py"
    if not script.exists():
        return "  (britania-board not installed; state unavailable)"
    out = sh([sys.executable, str(script)], cwd=str(project), timeout=180)
    return out.rstrip() if out else "  (board returned nothing)"


# ------------------------------------------------------------------ briefing


def main() -> int:
    ap = argparse.ArgumentParser(description="Rebuild session state from durable sources.")
    ap.add_argument("--path", default=os.getcwd())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    project = Path(args.path).resolve()

    run_id, how, objective = find_run(project)
    bound = bound_run(project)
    state = {
        "project": project.name,
        "git": git_state(project),
        "glossary": glossary(project),
        "run": {"id": run_id, "identified_by": how, "objective": objective, "bound": bound},
        "gate_db": GATE_DB.exists(),
    }

    if args.json:
        print(json.dumps(state, indent=2))
        return 0

    g, gl = state["git"], state["glossary"]
    print(f"RESTORE -- {project.name}")
    print()
    print(f"  branch     {g['branch']}"
          + (f", {g['dirty']} uncommitted file(s)" if g["dirty"] else ", clean")
          + (f", {g['unpushed']} unpushed" if g["unpushed"] not in ("0", "?") else ""))
    if gl["present"]:
        print(f"  glossary   CONTEXT.md, ~{gl['terms']} terms"
              + ("" if gl["tracked"] else "  -- NOT TRACKED BY GIT, so no worker can read it"))
    else:
        print("  glossary   CONTEXT.md missing -- workers have no shared vocabulary")

    print()
    print("  Run")
    if bound:
        print(f"    bound to {bound}. Your mail is readable.")
    elif run_id:
        print(f"    NOT BOUND. This terminal cannot read deliveries until it is --")
        print(f"    `check` will answer `consumer_fenced`, which is not a dead Run.")
        print()
        print(f"      orca orchestration run-use --id {run_id}")
        print()
        print(f"    candidate  {run_id}")
        print(f"    chosen by  {how}")
        if objective:
            print(f"    objective  {objective[:78]}")
    else:
        print(f"    none found ({how}). A new Run is created by the orchestration skill.")

    print()
    print(board(project))

    print()
    print("  Not recoverable")
    print("    The conversation. Anything decided but never written to the backlog,")
    print("    the glossary or an ADR is gone -- say so plainly rather than")
    print("    reconstructing a plausible version of it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
