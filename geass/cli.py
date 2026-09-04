"""geass — install the Lelouch orchestrator harness into a project.

    geass cast [path]     install the harness (default: current directory)
    geass status [path]   report what is installed and whether it has drifted
    geass doctor [path]   check the external skills and tools the contract needs
    geass diff <skill>    show how a forked skill differs from its vanilla copy

Design notes worth knowing before changing this file:

- Installing is a COPY, never a symlink. The target project must keep working if
  this repo is deleted, and its contract must be reviewable in its own git
  history alongside the code it governs.
- Placeholders are substituted at install time from the target's own git, so the
  contract names the real project, repo and default branch rather than a
  generic. A contract that says "the default branch is master" in a repo whose
  default branch is `main` is worse than no contract at all.
- `cast` refuses to clobber by default. Re-casting over an existing install
  needs --force, because the contract is a file the user edits.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from . import manifest

# The payload ships inside the package so `pip install` carries it. Browse it at
# geass/harness (the contract) and geass/skills (vanilla + patched forks).
PACKAGE = Path(__file__).resolve().parent
HARNESS = PACKAGE / "harness"
SKILLS = PACKAGE / "skills"

# Where project-scoped skills live for Claude Code.
SKILLS_DEST = Path(".claude") / "skills"


# ---------------------------------------------------------------- git probing


def _git(project: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(project), *args],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def detect(project: Path) -> dict[str, str]:
    """Everything the contract needs to know about the project it governs."""
    remote = _git(project, "remote", "get-url", "origin")
    repo = "no remote configured"
    if remote:
        slug = remote.removesuffix(".git").replace(":", "/")
        parts = [p for p in slug.split("/") if p]
        if len(parts) >= 2:
            repo = "/".join(parts[-2:])

    # The default branch: prefer what the remote says, fall back to the branch
    # we are on. Guessing "main" would be a lie half the time.
    branch = None
    head = _git(project, "symbolic-ref", "refs/remotes/origin/HEAD")
    if head:
        branch = head.rsplit("/", 1)[-1]
    if not branch:
        branch = _git(project, "rev-parse", "--abbrev-ref", "HEAD")

    # How the orchestrator addresses its principal. Taken from the environment
    # so a cast can be personalised without editing the contract afterwards;
    # git's user.name is the best guess available, and the contract is a plain
    # file the user can edit if the guess is wrong.
    user = (
        os.environ.get("LELOUCH_USER")
        or _git(project, "config", "user.name")
        or "the user"
    )

    return {
        "PROJECT": project.resolve().name,
        "REPO": repo,
        "DEFAULT_BRANCH": branch or "main",
        "USER": user,
        "PLATFORM_NOTES": manifest.platform_notes(platform.system()),
    }


def substitute(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def _copy(src: Path, dest: Path, values: dict[str, str]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix in manifest.SUBSTITUTED_SUFFIXES:
        dest.write_text(
            substitute(src.read_text(encoding="utf-8"), values), encoding="utf-8"
        )
    else:
        shutil.copy2(src, dest)


def _copy_tree(src: Path, dest: Path, values: dict[str, str]) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    for item in src.rglob("*"):
        if item.is_file():
            _copy(item, dest / item.relative_to(src), values)


# --------------------------------------------------------------------- skills


def resolve_skills() -> list[tuple[str, Path, str]]:
    """Every skill to install, as (installed_name, source_dir, origin)."""
    out: list[tuple[str, Path, str]] = []
    renamed_from = set(manifest.RENAMED)

    for src in sorted((SKILLS / "vanilla").iterdir()):
        if not src.is_dir() or src.name in renamed_from:
            continue  # a renamed skill is installed under its new name only
        if src.name in manifest.OVERLAID:
            out.append((src.name, SKILLS / "patched" / src.name, "patched"))
        else:
            out.append((src.name, src, "vanilla"))

    for old, (new, _why) in manifest.RENAMED.items():
        out.append((new, SKILLS / "patched" / new, f"patched, renamed from {old}"))

    return sorted(out)


# ------------------------------------------------------------------- settings


def merge_settings(project: Path) -> str:
    """Add our SessionStart hook without discarding the project's own settings."""
    fragment = json.loads((HARNESS / "settings.json").read_text(encoding="utf-8"))
    target = project / ".claude" / "settings.json"

    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(fragment, indent=2) + "\n", encoding="utf-8")
        return "created"

    existing = json.loads(target.read_text(encoding="utf-8"))
    hooks = existing.setdefault("hooks", {})
    ours = fragment["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    session_start = hooks.setdefault("SessionStart", [])

    for group in session_start:
        for hook in group.get("hooks", []):
            if hook.get("command") == ours:
                return "already present"

    session_start.extend(fragment["hooks"]["SessionStart"])
    target.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return "merged"


# -------------------------------------------------------------- dependencies


def _skill_installed(name: str, project: Path) -> bool:
    """A skill counts as present if any agent scope can see it.

    Checked narrowest first: project-scoped, then Claude Code's user scope, then
    the shared ~/.agents store that every agent symlinks into.
    """
    candidates = [
        project / ".claude" / "skills" / name,
        Path.home() / ".claude" / "skills" / name,
        Path.home() / ".agents" / "skills" / name,
    ]
    return any(c.is_dir() for c in candidates)


def check_dependencies(project: Path) -> tuple[list[str], list[str]]:
    """Report what the contract needs and the machine does not have.

    Returns (blocking, advisory) as printable lines.
    """
    blocking: list[str] = []
    advisory: list[str] = []

    for tool, why in manifest.REQUIRED_TOOLS.items():
        if shutil.which(tool) is None:
            blocking.append(f"{tool:22} not on PATH - {why}")
    for tool, why in manifest.RECOMMENDED_TOOLS.items():
        if shutil.which(tool) is None:
            advisory.append(f"{tool:22} not on PATH - {why}")

    for name, (source, why) in manifest.REQUIRED_SKILLS.items():
        if not _skill_installed(name, project):
            blocking.append(f"{name:22} missing - {why}")
            blocking.append(f"{'':22}   {manifest.install_hint(source)}")
    for name, (source, why) in manifest.RECOMMENDED_SKILLS.items():
        if not _skill_installed(name, project):
            advisory.append(f"{name:22} missing - {why}")
            advisory.append(f"{'':22}   {manifest.install_hint(source)}")

    return blocking, advisory


def report_dependencies(project: Path) -> int:
    """Print the dependency state. Returns the count of blocking problems."""
    blocking, advisory = check_dependencies(project)

    if not blocking and not advisory:
        n = len(manifest.REQUIRED_SKILLS) + len(manifest.RECOMMENDED_SKILLS)
        print(f"  ok    all {n} external skills and every tool are present")
        return 0

    if blocking:
        print("  MISSING - the contract references these and they are not installed:")
        for line in blocking:
            print(f"    {line}")
    if advisory:
        if blocking:
            print()
        print("  optional - the harness works without these, with less reach:")
        for line in advisory:
            print(f"    {line}")
    return len([b for b in blocking if not b.startswith(" " * 22)])


def update_gitignore(project: Path) -> str:
    path = project / ".gitignore"
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    additions = [
        (entry, why)
        for entry, why in manifest.GITIGNORE_ENTRIES
        if entry not in current
    ]
    if not additions:
        return "already covered"
    block = "" if not current or current.endswith("\n") else "\n"
    for entry, why in additions:
        block += f"\n# {why}\n{entry}\n"
    path.write_text(current + block, encoding="utf-8")
    return f"added {len(additions)}"


# -------------------------------------------------------------------- actions


def cast(project: Path, force: bool) -> int:
    if not project.is_dir():
        print(f"! not a directory: {project}", file=sys.stderr)
        return 2

    values = detect(project)
    print(f"Casting the Lelouch harness on {values['PROJECT']}\n")
    print(f"  repo            {values['REPO']}")
    print(f"  default branch  {values['DEFAULT_BRANCH']}")
    print(f"  platform        {platform.system()}\n")

    existing = [dest for _src, dest in manifest.PAYLOAD if (project / dest).exists()]
    if existing and not force:
        print("! already cast — these would be overwritten:", file=sys.stderr)
        for dest in existing:
            print(f"    {dest}", file=sys.stderr)
        print("\n  Re-cast with --force to overwrite.", file=sys.stderr)
        return 1

    for src, dest in manifest.PAYLOAD:
        _copy(HARNESS / src, project / dest, values)
        print(f"  contract    {dest}")

    skills = resolve_skills()
    dest_root = project / SKILLS_DEST
    for name, src, origin in skills:
        _copy_tree(src, dest_root / name, values)
    print(f"  skills      {len(skills)} into {SKILLS_DEST}")
    for name, _src, origin in skills:
        if origin != "vanilla":
            print(f"                {name}  ({origin})")

    print(f"  settings    .claude/settings.json ({merge_settings(project)})")
    print(f"  gitignore   {update_gitignore(project)}")

    print("\nDependencies")
    unmet = report_dependencies(project)

    print("\nDone. Next:")
    step = 1
    if unmet:
        print(f"  {step}. Install the missing skills above — the contract references")
        print("     them, so Lelouch will reach for tools that are not there.")
        step += 1
    print(f"  {step}. Review CLAUDE.md — it is yours to edit, not a black box.")
    print(f"  {step + 1}. Commit it, so the contract is versioned with the code it governs.")
    print(f"  {step + 2}. Start a fresh agent session here. Lelouch takes over.")
    return 0


def status(project: Path) -> int:
    values = detect(project)
    print(f"{values['PROJECT']}  ({values['REPO']}, default {values['DEFAULT_BRANCH']})\n")

    missing = 0
    for _src, dest in manifest.PAYLOAD:
        ok = (project / dest).exists()
        missing += not ok
        print(f"  {'ok  ' if ok else 'MISS'}  {dest}")

    dest_root = project / SKILLS_DEST
    expected = resolve_skills()
    if not dest_root.is_dir():
        print(f"  MISS  {SKILLS_DEST} (no skills installed)")
        missing += 1
    else:
        installed = {p.name for p in dest_root.iterdir() if p.is_dir()}
        absent = [n for n, _s, _o in expected if n not in installed]
        print(f"  {'ok  ' if not absent else 'PART'}  {SKILLS_DEST}: "
              f"{len(installed & {n for n, _s, _o in expected})}/{len(expected)} skills")
        for name in absent:
            print(f"          missing: {name}")
        missing += bool(absent)

    print("\nDependencies")
    unmet = report_dependencies(project)

    print()
    if missing:
        print("Not fully cast. Run: geass cast")
        return 1
    if unmet:
        print("Cast, but dependencies are missing. See above.")
        return 1
    print("Fully cast.")
    return 0


def doctor(project: Path) -> int:
    """Dependencies only — the check on its own, for an already-cast project."""
    values = detect(project)
    print(f"{values['PROJECT']}  (platform {platform.system()})\n")
    unmet = report_dependencies(project)
    print()
    if unmet:
        print(f"{unmet} blocking problem(s).")
        return 1
    print("Ready.")
    return 0


def diff(skill: str) -> int:
    vanilla = SKILLS / "vanilla" / skill
    patched = SKILLS / "patched" / skill

    if not patched.is_dir():
        for old, (new, _why) in manifest.RENAMED.items():
            if new == skill:
                vanilla, patched = SKILLS / "vanilla" / old, SKILLS / "patched" / new
                break

    if not patched.is_dir():
        forks = sorted(list(manifest.OVERLAID) + [n for n, _w in manifest.RENAMED.values()])
        print(f"! {skill} is not a fork. Forked skills: {', '.join(forks)}", file=sys.stderr)
        return 2

    why = manifest.OVERLAID.get(skill)
    if why is None:
        for old, (new, reason) in manifest.RENAMED.items():
            if new == skill:
                why = f"renamed from {old}: {reason}"
    print(f"# {skill}\n# {why}\n")
    # git writes unbuffered; without this our header lands after its output.
    sys.stdout.flush()

    subprocess.run(["git", "diff", "--no-index", str(vanilla), str(patched)])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="geass",
        description="Install the Lelouch orchestrator harness into a project.",
    )
    sub = parser.add_subparsers(dest="command")

    p_cast = sub.add_parser("cast", help="install the harness into a project")
    p_cast.add_argument("path", nargs="?", default=".")
    p_cast.add_argument("--force", action="store_true", help="overwrite an existing cast")

    p_status = sub.add_parser("status", help="report what is installed")
    p_status.add_argument("path", nargs="?", default=".")

    p_doctor = sub.add_parser("doctor", help="check external skills and tools only")
    p_doctor.add_argument("path", nargs="?", default=".")

    p_diff = sub.add_parser("diff", help="show a fork against its vanilla copy")
    p_diff.add_argument("skill")

    args = parser.parse_args()
    if args.command == "cast":
        return cast(Path(args.path), args.force)
    if args.command == "status":
        return status(Path(args.path))
    if args.command == "doctor":
        return doctor(Path(args.path))
    if args.command == "diff":
        return diff(args.skill)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
