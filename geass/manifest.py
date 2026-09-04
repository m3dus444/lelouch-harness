"""What geass installs, and why each piece is shaped the way it is.

The skill story in one paragraph: upstream `mattpocock/skills` ships 18 skills we
want. Five of them we fork. Rather than installing upstream and mutating it in
place — which breaks the moment upstream rewrites a passage — this repo vendors
BOTH a pristine `skills/vanilla/` copy and our `skills/patched/` forks. geass
installs vanilla for the 13 untouched skills and patched for the 5 forks. The
vanilla copy is not dead weight: it is the diff baseline that makes a future
upstream bump a real three-way merge instead of a guess.
"""

from __future__ import annotations

# Forks that keep their upstream name. geass installs the patched copy instead
# of the vanilla one.
OVERLAID = {
    "implement": (
        "de-disabled model invocation so a dispatched worker can auto-run it; "
        "closes with prod-review only, leaving standards review to no-mistakes"
    ),
    "improve-codebase-architecture": (
        "renders its report through lavish so findings can be annotated back"
    ),
    "to-tickets": (
        "local tracker is tasks-axi/backlog.md, not loose .scratch/ files"
    ),
}

# Forks that are RENAMED. The vanilla name is never installed; the patched name
# is installed in its place. Both renames exist to resolve a real collision.
RENAMED = {
    "code-review": (
        "prod-review",
        "upstream 'code-review' collides with Claude Code's own built-in skill "
        "of that name, which silently shadows it",
    ),
    "handoff": (
        "brief",
        "'handoff' is claimed by Orca's full-handoff concept and by the user's "
        "own global override that maps the word to supervised orchestration",
    ),
}

# Skills deliberately NOT vendored, and why.
EXCLUDED = {
    "ask-matt": "a router over the other skills; the contract's routing table replaces it",
    "setup-matt-pocock-skills": "only knows GitHub/GitLab/.scratch; geass writes the tracker config itself",
    "prototype": "lavish covers the same ground with an annotation loop on top",
    "triage": "no triage-label workflow in this harness",
    "resolving-merge-conflicts": "not part of the orchestrator pipeline",
    "teach": "not part of the orchestrator pipeline",
    "to-questionnaire": "not part of the orchestrator pipeline",
}

# Skills the contract depends on but does NOT vendor. They are owned by other
# people and are CLI-backed stubs: the real guidance lives in a versioned binary,
# so a vendored copy would freeze a pointer and drift from what it points at.
#
# geass therefore checks for them rather than installing them. Casting a contract
# that references tools which are not present produces a harness that fails
# mid-dispatch instead of at install time, which is the worst place to find out.
#
#   name: (source, why the contract needs it)
REQUIRED_SKILLS = {
    "orchestration": ("stablyai/orca", "worker lifecycle: dispatch, supervise, worker_done"),
    "orca-cli": ("stablyai/orca", "worktree housekeeping, workspace cards, terminals"),
    "tasks-axi": ("kunchenguid/tasks-axi", "the backlog - tickets, blocked-by edges, holds"),
    "lavish": ("kunchenguid/lavish-axi", "annotatable review surfaces for plans and reports"),
    "no-mistakes": ("kunchenguid/no-mistakes", "the ship gate every Build and Fix ends with"),
}

RECOMMENDED_SKILLS = {
    "gh-axi": ("kunchenguid/gh-axi", "GitHub PRs and CI; without it the ship gate stops at a branch"),
    "chrome-devtools-axi": ("kunchenguid/chrome-devtools-axi", "browser reproduction for diagnosing-bugs"),
}

# Executables the harness shells out to. The -axi CLIs are NOT here: they are
# fetched on demand by npx, so npx itself is the only requirement for them.
REQUIRED_TOOLS = {
    "git": "geass reads the target repo to fill the contract in; workers branch",
    "npx": "the -axi skills fetch their CLIs on demand",
    "orca": "the runtime workers actually run in",
}

RECOMMENDED_TOOLS = {
    "gh": "the pull-request flow at the end of the ship gate",
}


def install_hint(source: str) -> str:
    """How to obtain a missing skill."""
    if source == "stablyai/orca":
        return "ships with Orca - enable it in Orca's Agent skills panel"
    return f"npx skills@latest add {source} -g -y"


# Files copied into the target project, as (source in harness/, destination).
PAYLOAD = [
    ("CLAUDE.md", "CLAUDE.md"),
    ("AGENTS.md", "AGENTS.md"),
    ("docs/agents/issue-tracker.md", "docs/agents/issue-tracker.md"),
    ("docs/agents/domain.md", "docs/agents/domain.md"),
    ("docs/agents/dispatch-templates.md", "docs/agents/dispatch-templates.md"),
    ("hooks/session-start.py", ".claude/hooks/session-start.py"),
]

# Paths geass adds to the target's .gitignore, with the reason as a comment.
GITIGNORE_ENTRIES = [
    (".lavish/", "Lavish review artifacts: transient per-session review surfaces"),
]

# Text file suffixes that get placeholder substitution.
SUBSTITUTED_SUFFIXES = {".md", ".py", ".json", ".toml", ".txt"}


def platform_notes(system: str) -> str:
    """The §11 Environment paragraph, written for the OS geass is installing on.

    The orchestrator needs to know this because several vendored skills assume a
    POSIX shell — `wizard` emits bash outright.
    """
    if system == "Windows":
        return (
            "Windows. Default shell is PowerShell; Git Bash is available. Several\n"
            "installed skills assume POSIX — notably `wizard`, which emits bash. Adapt\n"
            "or skip rather than emitting scripts that cannot run here."
        )
    if system == "Darwin":
        return (
            "macOS. POSIX shell throughout, so the vendored skills' shell assumptions\n"
            "hold as written."
        )
    return (
        "Linux. POSIX shell throughout, so the vendored skills' shell assumptions\n"
        "hold as written."
    )
