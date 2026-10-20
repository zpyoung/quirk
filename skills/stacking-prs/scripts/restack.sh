#!/usr/bin/env bash
#
# stacking-prs/restack.sh
# Replays one stack layer onto a new base after its parent changed or merged.
#
# Usage: ./restack.sh --branch <b> --onto <base-branch> --old-tip <sha>
#                     [--onto-ref <ref>] [--remote <name>] [--pr <number>]
#                     [--forge github|ghes|gitlab] [--no-push]
# Output: one JSON document on stdout; progress and git output go to stderr.
#
# Exit codes:
#   0 rebased (and pushed / retargeted when asked)
#   1 usage or precondition failure, or the post-rebase verification failed
#   2 rebase conflict: rebase aborted, branch restored to its pre-run head
#   3 <b> is checked out in another worktree: nothing changed
#   4 push rejected (lease or includes check): local rebase and backup kept
#   5 retarget failed after a successful push: JSON carries the PR URL
#
# --old-tip is the head SHA of the parent as the layer was built on it. Replaying
# `<old-tip>..<b>` onto the new base takes only the layer's own commits, whether the parent
# was squash-merged, rebase-merged, or merge-committed. For a layer above the first, pass the
# restacked parent's `old_head` as --old-tip and the parent branch as --onto.
#
# The backup branch (backup/<b>_<timestamp>) is local only and never deleted here.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for stderr messages (not captured in JSON output)
RED='\033[0;31m'
NC='\033[0m' # No Color

BRANCH=""
ONTO=""
OLD_TIP=""
ONTO_REF=""
REMOTE="origin"
PR=""
FORGE_ARG=""
NO_PUSH=0

FORGE="none"
ONTO_REF_RESOLVED=""
OLD_TIP_SHA=""
OLD_HEAD=""
NEW_HEAD=""
BACKUP_BRANCH=""
COMMITS_REPLAYED=0
PUSHED=false
RETARGETED=false
PR_URL=""
CONFLICTED_FILES=""

usage() {
    cat >&2 <<'USAGE'
Usage: restack.sh --branch <b> --onto <base-branch> --old-tip <sha>
                  [--onto-ref <ref>] [--remote <name>] [--pr <number>]
                  [--forge github|ghes|gitlab] [--no-push]
Environment: STACK_FORGE=github|ghes|gitlab|none sets the default --forge.
USAGE
}

# Emit the result document. $1 is the success flag; $2 is the message.
output_json() {
    local success="$1" message="$2"
    jq -n \
        --argjson success "$success" \
        --arg branch "$BRANCH" --arg onto "$ONTO" --arg onto_ref "$ONTO_REF_RESOLVED" \
        --arg old_tip "$OLD_TIP_SHA" --arg old_head "$OLD_HEAD" --arg new_head "$NEW_HEAD" \
        --arg backup "$BACKUP_BRANCH" --argjson replayed "$COMMITS_REPLAYED" \
        --argjson pushed "$PUSHED" --argjson retargeted "$RETARGETED" --arg pr_url "$PR_URL" \
        --arg conflicted "$CONFLICTED_FILES" --arg message "$message" '
        def nn: if . == "" then null else . end;
        {success: $success, branch: $branch, onto: $onto, onto_ref: ($onto_ref | nn),
         old_tip: ($old_tip | nn), old_head: ($old_head | nn), new_head: ($new_head | nn),
         backup_branch: ($backup | nn), commits_replayed: $replayed, pushed: $pushed,
         retargeted: $retargeted, pr_url: ($pr_url | nn),
         conflicted_files: ($conflicted | split("\n") | map(select(length > 0))),
         message: $message}'
}

# Report a failure: red message on stderr, success:false JSON on stdout, then exit with $1.
fail() {
    local code="$1"
    shift
    echo >&2 -e "${RED}Error: $*${NC}"
    output_json false "$*"
    exit "$code"
}

if ! command -v jq >/dev/null 2>&1; then
    echo >&2 -e "${RED}Error: jq is required but not installed${NC}"
    printf '{"success":false,"message":"jq is required but not installed"}\n'
    exit 1
fi

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --branch | --onto | --old-tip | --onto-ref | --remote | --pr | --forge)
                if [[ $# -lt 2 || -z "$2" ]]; then
                    usage
                    fail 1 "$1 needs a value"
                fi
                case "$1" in
                    --branch) BRANCH="$2" ;;
                    --onto) ONTO="$2" ;;
                    --old-tip) OLD_TIP="$2" ;;
                    --onto-ref) ONTO_REF="$2" ;;
                    --remote) REMOTE="$2" ;;
                    --pr) PR="$2" ;;
                    --forge) FORGE_ARG="$2" ;;
                esac
                shift 2
                ;;
            --no-push)
                NO_PUSH=1
                shift
                ;;
            -h | --help)
                usage
                exit 0
                ;;
            *)
                usage
                fail 1 "unknown argument: $1"
                ;;
        esac
    done
    [[ -n "$BRANCH" ]] || { usage; fail 1 "--branch is required"; }
    [[ -n "$ONTO" ]] || { usage; fail 1 "--onto is required"; }
    [[ -n "$OLD_TIP" ]] || { usage; fail 1 "--old-tip is required"; }
    if [[ -n "$PR" && ! "$PR" =~ ^[0-9]+$ ]]; then
        fail 1 "--pr must be a number (got '$PR')"
    fi
    return 0
}

# Same resolution as stack.sh: --forge, else STACK_FORGE, else the remote host.
resolve_forge() {
    local url auth host
    if [[ -n "$FORGE_ARG" ]]; then
        FORGE="$FORGE_ARG"
    elif [[ -n "${STACK_FORGE:-}" ]]; then
        FORGE="$STACK_FORGE"
    else
        url=$(git remote get-url "$REMOTE" 2>/dev/null || true)
        auth="${url#*://}"
        auth="${auth%%/*}"
        auth="${auth#*@}"
        host=$(printf '%s' "${auth%%:*}" | tr '[:upper:]' '[:lower:]')
        case "$host" in
            github.com) FORGE="github" ;;
            *gitlab*) FORGE="gitlab" ;;
            *) FORGE="none" ;;
        esac
    fi
    case "$FORGE" in
        github | ghes | gitlab | none) ;;
        *) fail 1 "forge must be one of github|ghes|gitlab|none (got '$FORGE')" ;;
    esac
}

# Print the path of another worktree that has $1 checked out; nothing when there is none.
other_worktree_of() {
    local branch="$1" here path="" line
    here=$(git rev-parse --show-toplevel)
    while IFS= read -r line; do
        case "$line" in
            "worktree "*) path="${line#worktree }" ;;
            "branch refs/heads/$branch")
                if [[ "$path" != "$here" ]]; then
                    printf '%s' "$path"
                    return 0
                fi
                ;;
        esac
    done < <(git worktree list --porcelain)
    return 0
}

check_preconditions() {
    local other cli

    git rev-parse --git-dir >/dev/null 2>&1 || fail 1 "not inside a git repository"

    if ! git diff --quiet || ! git diff --cached --quiet; then
        fail 1 "uncommitted changes detected; commit or stash first"
    fi

    git rev-parse --verify --quiet "refs/heads/$BRANCH" >/dev/null ||
        fail 1 "branch '$BRANCH' does not exist locally"
    OLD_HEAD=$(git rev-parse "refs/heads/$BRANCH")

    OLD_TIP_SHA=$(git rev-parse --verify --quiet "${OLD_TIP}^{commit}" 2>/dev/null) ||
        fail 1 "--old-tip '$OLD_TIP' does not resolve to a commit"
    git merge-base --is-ancestor "$OLD_TIP_SHA" "$OLD_HEAD" ||
        fail 1 "--old-tip $OLD_TIP_SHA is not an ancestor of '$BRANCH'"

    if [[ -z "$ONTO_REF" ]]; then
        if git rev-parse --verify --quiet "refs/remotes/$REMOTE/$ONTO" >/dev/null; then
            ONTO_REF="$REMOTE/$ONTO"
        else
            ONTO_REF="$ONTO"
        fi
    fi
    git rev-parse --verify --quiet "${ONTO_REF}^{commit}" >/dev/null ||
        fail 1 "--onto-ref '$ONTO_REF' does not resolve to a commit"
    ONTO_REF_RESOLVED="$ONTO_REF"

    if [[ -n "$PR" ]]; then
        resolve_forge
        case "$FORGE" in
            none) fail 1 "--pr needs a forge, but none was resolved; pass --forge or set STACK_FORGE" ;;
            gitlab) cli="glab" ;;
            *) cli="gh" ;;
        esac
        command -v "$cli" >/dev/null 2>&1 || fail 1 "--pr needs '$cli', which is not installed"
    fi

    other=$(other_worktree_of "$BRANCH")
    if [[ -n "$other" ]]; then
        fail 3 "branch '$BRANCH' is checked out in another worktree: $other"
    fi
}

create_backup() {
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    BACKUP_BRANCH="backup/${BRANCH}_${timestamp}"
    git rev-parse --verify --quiet "refs/heads/$BACKUP_BRANCH" >/dev/null &&
        fail 1 "backup branch '$BACKUP_BRANCH' already exists; retry in a second"
    git branch "$BACKUP_BRANCH" "$OLD_HEAD" >&2
}

# Restore HEAD to what was checked out before the run (a branch, or a detached commit).
restore_start_point() {
    if [[ -n "$START_BRANCH" ]]; then
        git checkout -q "$START_BRANCH" >&2 || true
    else
        git checkout -q --detach "$START_SHA" >&2 || true
    fi
}

replay() {
    local expected
    if ! GIT_EDITOR=true git rebase --onto "$ONTO_REF_RESOLVED" "$OLD_TIP_SHA" "$BRANCH" >&2 2>&1; then
        CONFLICTED_FILES=$(git diff --name-only --diff-filter=U || true)
        git rebase --abort >&2 2>&1 || true
        restore_start_point
        if [[ -n "$CONFLICTED_FILES" ]]; then
            fail 2 "rebase conflict replaying '$BRANCH' onto $ONTO_REF_RESOLVED; branch restored (backup: $BACKUP_BRANCH)"
        fi
        fail 1 "rebase of '$BRANCH' failed without conflicts; branch restored (backup: $BACKUP_BRANCH)"
    fi

    NEW_HEAD=$(git rev-parse HEAD)
    COMMITS_REPLAYED=$(git rev-list --count "${ONTO_REF_RESOLVED}..${NEW_HEAD}")
    expected=$(git rev-list --count "${OLD_TIP_SHA}..${OLD_HEAD}")

    git merge-base --is-ancestor "$ONTO_REF_RESOLVED" "$NEW_HEAD" ||
        fail 1 "verification failed: $ONTO_REF_RESOLVED is not an ancestor of the rebased '$BRANCH'; branch left rebased, backup: $BACKUP_BRANCH"
    [[ "$COMMITS_REPLAYED" -eq "$expected" ]] ||
        fail 1 "verification failed: replayed $COMMITS_REPLAYED commits, expected $expected; branch left rebased, backup: $BACKUP_BRANCH"
}

push_branch() {
    if ! git push --force-with-lease --force-if-includes "$REMOTE" "$BRANCH" >&2 2>&1; then
        fail 4 "push of '$BRANCH' to '$REMOTE' was rejected; local rebase kept, backup: $BACKUP_BRANCH"
    fi
    PUSHED=true
}

PR_BASE=""

# Fill PR_URL and PR_BASE (the PR's current base branch) from the forge; either stays empty when
# the forge can't be read, which makes the retarget run anyway.
read_pr() {
    local json
    case "$FORGE" in
        gitlab)
            json=$(glab mr view "$PR" -F json 2>/dev/null) || json=""
            PR_URL=$(printf '%s' "$json" | jq -r '.web_url // empty' 2>/dev/null || true)
            PR_BASE=$(printf '%s' "$json" | jq -r '.target_branch // empty' 2>/dev/null || true)
            ;;
        *)
            PR_URL=$(gh pr view "$PR" --json url --jq .url 2>/dev/null || true)
            PR_BASE=$(gh pr view "$PR" --json baseRefName --jq .baseRefName 2>/dev/null || true)
            ;;
    esac
    PR_URL=$(printf '%s' "$PR_URL" | tr -d '[:space:]')
    PR_BASE=$(printf '%s' "$PR_BASE" | tr -d '[:space:]')
}

retarget() {
    read_pr
    if [[ "$PR_BASE" == "$ONTO" ]]; then
        return 0
    fi
    case "$FORGE" in
        gitlab) glab mr update "$PR" --target-branch "$ONTO" >&2 || return 1 ;;
        *) gh pr edit "$PR" --base "$ONTO" >&2 || return 1 ;;
    esac
    RETARGETED=true
}

main() {
    parse_args "$@"
    check_preconditions

    START_BRANCH=$(git symbolic-ref --quiet --short HEAD || true)
    START_SHA=$(git rev-parse HEAD)

    create_backup
    replay

    if [[ $NO_PUSH -eq 0 ]]; then
        push_branch
    fi

    if [[ -n "$PR" ]]; then
        if ! retarget; then
            fail 5 "retarget of PR $PR to '$ONTO' failed after the push; retarget it manually${PR_URL:+: $PR_URL}"
        fi
    fi

    output_json true "Restacked '$BRANCH' onto $ONTO_REF_RESOLVED"
}

START_BRANCH=""
START_SHA=""
main "$@"
