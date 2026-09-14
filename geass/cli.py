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


def detect(project: Path, agent: str = "claude") -> dict[str, str]:
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

    # Deliberately no name for the user. git's user.name is right there, but
    # lifting an identity into the contract without being asked is a leak, not a
    # convenience -- and a wrong guess is worse than none. The contract addresses
    # them in plain second person; naming is one line they can edit themselves.
    # The agent workers run. Orca has no default of its own -- `worker-start`
    # requires --agent or --terminal -- so something must name one, and a
    # contract that says "claude" in prose quietly makes that everyone's choice.
    # Cast it once here instead; --agent overrides, and the rendered CLAUDE.md
    # stays editable afterwards like every other line in it.
    return {
        "PROJECT": project.resolve().name,
        "REPO": repo,
        "DEFAULT_BRANCH": branch or "main",
        "PLATFORM_NOTES": manifest.platform_notes(platform.system()),
        "AGENT": agent,
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

    # Skills this harness wrote. They have no vanilla counterpart to diff
    # against, so they are neither vendored nor forked -- hence their own home.
    own = SKILLS / "own"
    if own.is_dir():
        for src in sorted(own.iterdir()):
            if src.is_dir():
                out.append((src.name, src, "own"))

    return sorted(out)


# ------------------------------------------------------------------- settings


def merge_settings(project: Path) -> str:
    """Add our SessionStart hook and permission grants, keeping the project's own.

    Two things merge here, independently, because they fail independently: the
    hook that loads project state at session start, and the allow-list this
    contract's workflow needs to finish a ticket. Run 2 deadlocked when the ship
    gate rebased a branch and the only way to publish it - a force-push - was
    refused with nobody awake to approve it. A cast that installs the workflow
    without the permissions the workflow requires stalls on its first rebase.
    """
    fragment = json.loads((HARNESS / "settings.json").read_text(encoding="utf-8"))
    target = project / ".claude" / "settings.json"

    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(fragment, indent=2) + "\n", encoding="utf-8")
        return "created"

    existing = json.loads(target.read_text(encoding="utf-8"))
    notes = []

    ours = fragment["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    session_start = existing.setdefault("hooks", {}).setdefault("SessionStart", [])
    if any(hook.get("command") == ours
           for group in session_start for hook in group.get("hooks", [])):
        notes.append("hook already present")
    else:
        session_start.extend(fragment["hooks"]["SessionStart"])
        notes.append("hook merged")

    # Unioned, never replaced: a project's own grants outrank ours and survive.
    wanted = fragment.get("permissions", {}).get("allow", [])
    allow = existing.setdefault("permissions", {}).setdefault("allow", [])
    added = [rule for rule in wanted if rule not in allow]
    allow.extend(added)
    notes.append(f"{len(added)} permission(s) added" if added
                 else "permissions already present")

    target.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return ", ".join(notes)


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


def gate_initialised(project: Path) -> bool:
    """Has `no-mistakes init` been run on this repo?

    `init` adds a `no-mistakes` git remote pointing at the local bare gate repo,
    so the remote is the marker. This is per-project state: a machine-wide binary
    check says nothing about whether THIS repo can be pushed through the gate.
    """
    return _git(project, "remote", "get-url", "no-mistakes") is not None


def check_dependencies(project: Path) -> tuple[list[str], list[str]]:
    """Report what the contract needs and the machine does not have.

    Returns (blocking, advisory) as printable lines.
    """
    blocking: list[str] = []
    advisory: list[str] = []

    for tool, why in manifest.REQUIRED_TOOLS.items():
        if shutil.which(tool) is None:
            blocking.append(f"{tool:22} not on PATH - {why}")
            hint = manifest.tool_install_hint(tool, platform.system())
            if hint:
                blocking.append(f"{'':22}   {hint}")
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

    # The gate is the one dependency that is per-repo as well as per-machine.
    # An installed binary on an uninitialised repo fails at the first push, so
    # reporting only the binary would repeat the miss this check exists to close.
    if shutil.which("no-mistakes") is not None and not gate_initialised(project):
        blocking.append(f"{'no-mistakes gate':22} not initialised in this repo")
        blocking.append(f"{'':22}   run `no-mistakes init` here")

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


def init_gate(project: Path) -> str:
    """Run `no-mistakes init` on the target, so the ship gate exists at cast time.

    The contract ends every Build and Fix at this gate, so a cast that installs
    the contract and leaves the gate uninitialised has shipped a pipeline whose
    last step cannot run. That failure surfaces mid-dispatch, in a worker, hours
    later -- the worst place to find out, which is the same argument the
    dependency check above is built on.

    Deliberately not silent, and deliberately not fatal: `init` adds a git remote
    and starts a daemon, so what it did is printed, and a cast still completes
    without it. `init` is idempotent, so re-casting is safe.
    """
    if shutil.which("no-mistakes") is None:
        return "skipped - binary not installed"
    if gate_initialised(project):
        return "already initialised"
    try:
        proc = subprocess.run(
            ["no-mistakes", "init"],
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"FAILED - {type(exc).__name__}"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return f"FAILED - {detail[-1] if detail else f'exit {proc.returncode}'}"
    return "initialised"


def cast(project: Path, force: bool, agent: str = "claude") -> int:
    if not project.is_dir():
        print(f"! not a directory: {project}", file=sys.stderr)
        return 2

    values = detect(project, agent)
    print(f"Casting the Lelouch harness on {values['PROJECT']}\n")
    print(f"  repo            {values['REPO']}")
    print(f"  default branch  {values['DEFAULT_BRANCH']}")
    print(f"  platform        {platform.system()}")
    print(f"  worker agent    {values['AGENT']}\n")

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
    print(f"  ship gate   {init_gate(project)}")

    print("\nDependencies")
    unmet = report_dependencies(project)

    # Reported, never registered. See `watcher()` for why the line is drawn here.
    present = watcher_present(project)
    name = watcher_name(project)
    if present is False:
        print("\nWatcher")
        print(f"  {name}: not registered with the OS scheduler")
        print("  It runs on its own schedule, so casting does not register it for you.")
        print("  When you want it:  geass watcher")
    elif present:
        print("\nWatcher")
        print(f"  {name}: registered")

    print("\nDone. Next:")
    step = 1
    if unmet:
        print(f"  {step}. Install what is missing above — the contract references")
        print("     it, so Lelouch will reach for tools that are not there.")
        print("     Re-run `geass cast --force` after installing no-mistakes,")
        print("     so the ship gate gets initialised on this repo.")
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


WATCHER_EVERY_MIN = 15


def watcher_name(project: Path) -> str:
    """One watcher per project, never one per machine.

    The watcher wakes *a specific session*, so a second project needs a second
    registration. A constant name would have silently replaced the first
    project's watcher when the second was cast -- with no error, and no sign
    until something breached and nobody was told.
    """
    return f"britania-vitals-{project.resolve().name}"


def _run(args: list[str]) -> tuple[bool, str]:
    exe = shutil.which(args[0])
    if exe is None:
        return False, f"{args[0]} not on PATH"
    try:
        proc = subprocess.run([exe, *args[1:]], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    out = (proc.stdout or proc.stderr or "").strip()
    return proc.returncode == 0, out


def watcher_command(project: Path) -> str:
    """The thing a scheduler should run, every {WATCHER_EVERY_MIN} minutes."""
    script = project / SKILLS_DEST / "britania-vitals" / "vitals.py"
    return f'python "{script}" --once --path "{project}"'


def watcher_present(project: Path) -> bool | None:
    """True/False if the scheduler answered, None if it could not be asked."""
    if platform.system() != "Windows":
        return None
    ok, _ = _run(["schtasks", "/Query", "/TN", watcher_name(project)])
    return ok


def watcher(project: Path, force: bool, remove: bool) -> int:
    """Register the vitals watcher with the OS scheduler.

    **Not an Orca automation, and the reason is worth recording.** Orca
    automations are agent-backed: `--prompt` and `--provider` are required, and
    the only plain-command slot is `--precheck`. So every firing that passes its
    precheck starts a *new* agent session -- which costs tokens, and worse,
    arrives with no context. The job here is to tell the *running* orchestrator
    to park its work, and a fresh agent cannot do that.

    The OS scheduler runs a plain script instead. It costs nothing, and the only
    tokens involved are one turn in the session that already holds the state.

    **`--once` on a schedule, not a resident `--watch`.** A long-lived watcher is
    a process that can die without saying so, and a monitor that has gone quiet
    looks exactly like a healthy one -- which this machine has demonstrated
    repeatedly. A scheduled one-shot has nothing to keep alive.

    Deliberately not part of `cast`: casting writes files, which are inert until
    someone uses them. Registering something that runs on its own schedule is a
    change to the machine, and that is the user's call to make explicitly.
    """
    cmd = watcher_command(project)
    name = watcher_name(project)

    if platform.system() != "Windows":
        verb = "Remove" if remove else "Add"
        print(f"  {verb} this line with `crontab -e`:")
        print()
        print(f"    */{WATCHER_EVERY_MIN} * * * * {cmd}")
        return 0

    present = watcher_present(project)
    if remove:
        if not present:
            print(f"  {name}: not registered, nothing to remove")
            return 0
        ok, out = _run(["schtasks", "/Delete", "/TN", name, "/F"])
        print(f"  removed {name}" if ok else f"! remove failed: {out}")
        return 0 if ok else 1

    if present and not force:
        print(f"  {name} already registered. Re-run with --force to replace it.")
        return 0
    if present:
        _run(["schtasks", "/Delete", "/TN", name, "/F"])

    ok, out = _run([
        "schtasks", "/Create", "/TN", name, "/TR", cmd,
        "/SC", "MINUTE", "/MO", str(WATCHER_EVERY_MIN), "/F",
    ])
    if not ok:
        print(f"! could not register the watcher: {out}", file=sys.stderr)
        print()
        print("  Register it by hand:")
        print()
        print(f'    schtasks /Create /TN {name} /TR "{cmd}" '
              f"/SC MINUTE /MO {WATCHER_EVERY_MIN} /F")
        return 1

    print(f"  registered {name}, every {WATCHER_EVERY_MIN} minutes")
    print("  It runs a script, not an agent. Quiet checks cost nothing.")
    print(f"  Remove it with:  geass watcher --remove")
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
    p_cast.add_argument(
        "--agent",
        default="claude",
        help="TUI agent workers run (claude, codex, cursor, ...); default claude",
    )

    p_status = sub.add_parser("status", help="report what is installed")
    p_status.add_argument("path", nargs="?", default=".")

    p_doctor = sub.add_parser("doctor", help="check external skills and tools only")
    p_doctor.add_argument("path", nargs="?", default=".")

    p_diff = sub.add_parser("diff", help="show a fork against its vanilla copy")
    p_diff.add_argument("skill")

    p_watch = sub.add_parser("watcher", help="register the vitals watcher with the OS scheduler")
    p_watch.add_argument("path", nargs="?", default=".")
    p_watch.add_argument("--force", action="store_true", help="replace an existing registration")
    p_watch.add_argument("--remove", action="store_true", help="unregister it")

    args = parser.parse_args()
    if args.command == "cast":
        return cast(Path(args.path), args.force, args.agent)
    if args.command == "status":
        return status(Path(args.path))
    if args.command == "doctor":
        return doctor(Path(args.path))
    if args.command == "diff":
        return diff(args.skill)
    if args.command == "watcher":
        return watcher(Path(args.path).resolve(), args.force, args.remove)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
