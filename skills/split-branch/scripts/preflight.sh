#!/usr/bin/env bash
set -euo pipefail
#
# preflight.sh — safety gate run once before a split.
#
# Verifies the working state is safe to split, then creates a restorable backup
# ref pointing at the branch tip so a later failed slice, rebase, or force-push
# can be undone. Prints ONLY the created backup ref's short name on stdout, so a
# caller can capture it: backup_ref=$(preflight.sh --base main)
#
# Usage: preflight.sh --base <ref> [--branch <ref>]
#   --base    the branch the split targets (e.g. main); required
#   --branch  the feature branch to back up; defaults to the current branch
#
# Exit codes:
#   0  success — backup ref created; its short name is on stdout
#   2  dirty index or work tree — commit or stash before splitting
#   3  cannot split — detached HEAD, or the target branch equals the base
#   4  not inside a git work tree, or base/branch does not resolve, or the
#      backup ref could not be created
#   5  bad arguments

base=""
branch=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --base)
            [[ $# -ge 2 && -n "$2" ]] || { echo >&2 "error: --base requires a value"; exit 5; }
            base="$2"; shift 2 ;;
        --branch)
            [[ $# -ge 2 && -n "$2" ]] || { echo >&2 "error: --branch requires a value"; exit 5; }
            branch="$2"; shift 2 ;;
        *)
            echo >&2 "error: unknown argument: $1"; exit 5 ;;
    esac
done

[[ -n "$base" ]] || { echo >&2 "error: --base is required"; exit 5; }

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo >&2 "error: not inside a git work tree"; exit 4
fi

# Splitting starts from a branch. Refuse a detached HEAD unconditionally — there
# is no branch to protect now or to rewrite later — even when --branch is given.
if ! git symbolic-ref --quiet HEAD >/dev/null 2>&1; then
    echo >&2 "error: detached HEAD — check out the feature branch first"; exit 3
fi
if [[ -z "$branch" ]]; then
    branch=$(git symbolic-ref --quiet --short HEAD)
fi

if ! git rev-parse --verify --quiet "${branch}^{commit}" >/dev/null; then
    echo >&2 "error: branch does not resolve: ${branch}"; exit 4
fi
if ! git rev-parse --verify --quiet "${base}^{commit}" >/dev/null; then
    echo >&2 "error: base does not resolve: ${base}"; exit 4
fi

# Reduce a ref to the short name Git would show, collapsing equivalent spellings
# so the base-equality guard below cannot be bypassed by an alternate spelling.
#   main, refs/heads/main, and a remote-tracking main all reduce to "main".
canonical_ref() {
    local ref="$1" full
    if full=$(git rev-parse --symbolic-full-name "$ref" 2>/dev/null) && [[ -n "$full" ]]; then
        case "$full" in
            refs/heads/*)   printf '%s' "${full#refs/heads/}" ;;
            refs/remotes/*) printf '%s' "${full#refs/remotes/*/}" ;;
            *)              printf '%s' "$full" ;;
        esac
    else
        printf '%s' "$ref"
    fi
}

branch_name=$(canonical_ref "$branch")

# Splitting while sitting on the base would back up and later rewrite the base
# itself. Compare canonical names so no alternate spelling slips through.
if [[ "$branch_name" == "$(canonical_ref "$base")" ]]; then
    echo >&2 "error: the target branch equals the base (${base}); check out the feature branch"; exit 3
fi

# Require a clean index and work tree so the backup ref captures exactly the
# committed history the split will rewrite. Untracked files are ignored: they
# are not part of the committed tree and do not affect the backup.
if ! git diff --quiet; then
    echo >&2 "error: unstaged changes present — commit or stash before splitting"; exit 2
fi
if ! git diff --cached --quiet; then
    echo >&2 "error: staged changes present — commit or stash before splitting"; exit 2
fi

tip=$(git rev-parse --verify "${branch}^{commit}")
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_ref="backup/${branch_name}_${timestamp}"

# Choose a name Git's DWIM resolution does not already map to any ref — branch,
# tag, or remote — so `git reset --hard <backup_ref>` is unambiguous. Both a
# same-second rerun and a name-shadowing tag are disambiguated here.
attempt=0
while git rev-parse --verify --quiet "$backup_ref" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    backup_ref="backup/${branch_name}_${timestamp}_$$_${attempt}"
done

if ! git branch "$backup_ref" "$tip" >/dev/null 2>&1; then
    echo >&2 "error: could not create backup ref ${backup_ref}"; exit 4
fi

# The printed name must resolve, under DWIM, to exactly the tip we backed up.
if [[ "$(git rev-parse --verify --quiet "$backup_ref" || true)" != "$tip" ]]; then
    echo >&2 "error: backup ref ${backup_ref} is ambiguous"; exit 4
fi

printf '%s\n' "$backup_ref"
