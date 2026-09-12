#!/usr/bin/env bash
# Retire an Orca worktree without leaving an orphan directory behind.
#
# Why this exists: F-105/F-106. `orca worktree rm` de-registers from Orca and
# git, then deletes the directory -- and on Windows that delete walks entries in
# sort order, hits node_modules, and dies, leaving everything sorting after it
# on disk. Both registries are then CORRECT and the folder is invisible to
# both, which is why six of them accumulated for four days unnoticed.
#
# The repair is the last line. Everything above it is the reason the last line
# is allowed to run. A bare `rm -rf` appended to the removal would inherit
# exactly the silence it repairs: it would look right every time, including the
# run where the worker had uncommitted work. Once the directory is orphaned
# .git is severed and nothing inside can answer that question any more -- so it
# has to be asked BEFORE the removal, not after.
#
# Usage: worktree-retire.sh <worktree-path> [--base master] [--yes]

set -euo pipefail

WT=""; BASE="master"; CONFIRM=0
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="$2"; shift 2 ;;
    --yes)  CONFIRM=1; shift ;;
    -*)     echo "unknown option: $1" >&2; exit 2 ;;
    *)      WT="$1"; shift ;;
  esac
done
[ -n "$WT" ] || { echo "usage: $0 <worktree-path> [--base master] [--yes]" >&2; exit 2; }
[ -d "$WT" ] || { echo "no such directory: $WT" >&2; exit 2; }

# Resolve from the worktree itself while .git is still attached. After the
# removal this is unanswerable, which is the whole point of the ordering.
BR=$(git -C "$WT" rev-parse --abbrev-ref HEAD)
TIP=$(git -C "$WT" rev-parse HEAD)
echo "worktree : $WT"
echo "branch   : $BR @ ${TIP:0:12}"

DIRTY=$(git -C "$WT" status --porcelain --untracked-files=normal)
if [ -n "$DIRTY" ]; then
  echo "REFUSING: uncommitted or untracked content:" >&2
  printf '%s\n' "$DIRTY" | head -20 >&2
  exit 1
fi

# Merged into base? Ask about the commit, not the branch name -- a branch
# deleted and recreated, or renamed on the remote, still answers correctly here.
if ! git -C "$WT" merge-base --is-ancestor "$TIP" "$BASE"; then
  echo "REFUSING: $BR @ ${TIP:0:12} is not an ancestor of $BASE." >&2
  echo "          Merge it, or retire it deliberately by hand." >&2
  exit 1
fi
echo "verified : clean, and merged into $BASE"

if [ "$CONFIRM" -ne 1 ]; then
  echo "dry run. re-run with --yes to remove."
  exit 0
fi

# --force gets git past a locked tree, which is the likeliest cause of the
# partial delete in the first place. It governs worktree removal only; the
# help is explicit that it "does not force branch deletion".
orca worktree rm --worktree "path:$WT" --force

# The repair. A no-op on a healthy removal -- and a no-op is what it should be,
# so its firing is worth noticing rather than hiding.
if [ -d "$WT" ]; then
  echo "NOTE: orca left the directory behind; removing $(du -sh "$WT" | cut -f1)"
  rm -rf "$WT"
  [ -d "$WT" ] && { echo "FAILED to remove $WT -- something holds a handle" >&2; exit 1; }
fi
echo "retired  : $WT"
