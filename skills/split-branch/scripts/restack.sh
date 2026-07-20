#!/usr/bin/env bash
# Restack a child branch after its recorded parent has been squash-merged.
# Exit codes: 2 base unavailable, 3 conflict (cleanly aborted), 4 unresolved
# branch/trunk, 5 bad arguments, 6 forge/rebase/cleanup operational failure.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
STACKMETA="$SCRIPT_DIR/stackmeta.sh"

usage() {
    echo "usage: restack.sh --branch <child> --onto <new-trunk> [--base-sha <sha>] [--remote <name>] [--dry-run]" >&2
}

branch=""
onto=""
base_sha=""
remote=""
dry_run=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --branch|--onto|--base-sha|--remote)
            [[ $# -ge 2 && -n "$2" ]] || { usage; exit 5; }
            case "$1" in
                --branch) branch="$2" ;;
                --onto) onto="$2" ;;
                --base-sha) base_sha="$2" ;;
                --remote) remote="$2" ;;
            esac
            shift 2
            ;;
        --dry-run) dry_run=1; shift ;;
        *) usage; exit 5 ;;
    esac
done
[[ -n "$branch" && -n "$onto" ]] || { usage; exit 5; }

if ! git rev-parse --verify --quiet "refs/heads/$branch^{commit}" >/dev/null ||
   ! git rev-parse --verify --quiet "$onto^{commit}" >/dev/null; then
    echo "error: child branch '$branch' and new trunk '$onto' must resolve locally" >&2
    exit 4
fi

if [[ -z "$remote" ]]; then
    remote=$(git config --get remote.pushDefault 2>/dev/null || true)
    remote=${remote:-origin}
fi
remote_url=$(git remote get-url "$remote" 2>/dev/null || true)
repo_slug=""
case "$remote_url" in
    *://*) repo_slug=${remote_url#*://}; repo_slug=${repo_slug#*/} ;;
    *@*:*|*:*/*) repo_slug=${remote_url#*:} ;;
esac
repo_slug=${repo_slug%.git}

# Self-hosted providers cannot be inferred from a hostname.  The per-remote
# setting is authoritative; hostname discovery is only a convenience.
forge=$(git config --get "remote.$remote.splitBranchForge" 2>/dev/null || true)
if [[ -z "$forge" ]]; then
    lower_url=$(printf '%s' "$remote_url" | tr '[:upper:]' '[:lower:]')
    if [[ "$lower_url" == *gitlab* ]]; then forge="gitlab"; else forge="github"; fi
fi
case "$forge" in
    glab|gitlab) forge="gitlab" ;;
    gh|github) forge="github" ;;
    *) echo "error: remote.$remote.splitBranchForge must be github or gitlab" >&2; exit 6 ;;
esac

body_file=$(mktemp "${TMPDIR:-/tmp}/restack-body.XXXXXX")
updated_body=$(mktemp "${TMPDIR:-/tmp}/restack-updated.XXXXXX")
rebase_output=$(mktemp "${TMPDIR:-/tmp}/restack-rebase.XXXXXX")
cleanup() { rm -f "$body_file" "$updated_body" "$rebase_output"; }
trap cleanup EXIT

fetch_body() {
    if [[ "$forge" == "gitlab" ]]; then
        if [[ -n "$repo_slug" ]]; then
            glab mr view "$branch" --repo "$repo_slug" --output json | jq -r '.description // ""'
        else
            glab mr view "$branch" --output json | jq -r '.description // ""'
        fi
    else
        if [[ -n "$repo_slug" ]]; then
            gh pr view "$branch" --repo "$repo_slug" --json body --jq '.body // ""'
        else
            gh pr view "$branch" --json body --jq '.body // ""'
        fi
    fi
}

update_body() {
    if [[ "$forge" == "gitlab" ]]; then
        if [[ -n "$repo_slug" ]]; then
            glab mr update "$branch" --repo "$repo_slug" --description "$(cat "$updated_body")"
        else
            glab mr update "$branch" --description "$(cat "$updated_body")"
        fi
    else
        if [[ -n "$repo_slug" ]]; then
            gh pr edit "$branch" --repo "$repo_slug" --body-file "$updated_body"
        else
            gh pr edit "$branch" --body-file "$updated_body"
        fi
    fi
}

# Fetch and validate everything needed for publication before touching a ref.
if ! fetch_body >"$body_file"; then
    if [[ -z "$base_sha" ]]; then
        echo "error: recorded base sha is unavailable; pass --base-sha explicitly" >&2
        exit 2
    fi
    echo "error: PR/MR body could not be read; child branch was not changed" >&2
    exit 6
fi

parsed_base=""
parse_status=0
if parsed_base=$("$STACKMETA" parse base-sha <"$body_file"); then
    parse_status=0
else
    parse_status=$?
fi
if [[ -z "$base_sha" ]]; then
    if [[ $parse_status -ne 0 ]]; then
        echo "error: PR/MR stack metadata is absent or malformed; pass --base-sha explicitly" >&2
        exit 2
    fi
    base_sha="$parsed_base"
fi

# Even with an explicit base, parent and position must be preserved rather than
# invented.  Invalid/missing metadata is an operational publication failure.
parent=""
position=""
if ! parent=$("$STACKMETA" parse parent <"$body_file") ||
   ! position=$("$STACKMETA" parse position <"$body_file"); then
    echo "error: PR/MR stack metadata is absent or malformed; cannot preserve parent/position" >&2
    exit 6
fi
if ! git rev-parse --verify --quiet "$base_sha^{commit}" >/dev/null; then
    echo "error: recorded base sha '$base_sha' does not resolve; pass --base-sha explicitly" >&2
    exit 2
fi

new_base_sha=$(git rev-parse "$onto^{commit}")
position_number=${position%/*}
total=${position#*/}
if ! "$STACKMETA" upsert "$parent" "$new_base_sha" "$position_number" "$total" \
    <"$body_file" >"$updated_body"; then
    echo "error: PR/MR stack metadata could not be prepared" >&2
    exit 6
fi

if [[ $dry_run -eq 1 ]]; then
    printf 'git rebase --onto %q %q %q\n' "$onto" "$base_sha" "$branch"
    exit 0
fi

old_child=$(git rev-parse "refs/heads/$branch")
if ! git rebase --onto "$onto" "$base_sha" "$branch" >"$rebase_output" 2>&1; then
    conflicts=$(git diff --name-only --diff-filter=U 2>/dev/null || true)
    git_dir=$(git rev-parse --git-dir)
    if [[ "$git_dir" != /* ]]; then git_dir="$(pwd)/$git_dir"; fi
    rebase_state=0
    [[ -d "$git_dir/rebase-merge" || -d "$git_dir/rebase-apply" ]] && rebase_state=1

    if [[ $rebase_state -eq 1 ]]; then
        if ! git rebase --abort >/dev/null 2>&1; then
            echo "error: rebase cleanup failed; manual recovery is required" >&2
            exit 6
        fi
    fi
    if [[ -d "$git_dir/rebase-merge" || -d "$git_dir/rebase-apply" ]] ||
       [[ $(git rev-parse "refs/heads/$branch") != "$old_child" ]]; then
        echo "error: rebase cleanup was incomplete; manual recovery is required" >&2
        exit 6
    fi
    if [[ -n "$conflicts" ]]; then
        echo "error: rebase conflict in:" >&2
        printf '%s\n' "$conflicts" >&2
        exit 3
    fi
    echo "error: rebase failed without a content conflict; child branch was not changed" >&2
    cat "$rebase_output" >&2
    exit 6
fi

rebased_child=$(git rev-parse "refs/heads/$branch")
if ! update_body >/dev/null; then
    # Roll back both the branch and its checked-out worktree.  update-ref uses
    # the rebased value as a lease so an unexpected concurrent move is never
    # overwritten.
    if git update-ref "refs/heads/$branch" "$old_child" "$rebased_child" &&
       git reset --hard "$old_child" >/dev/null 2>&1; then
        echo "error: PR/MR metadata update failed; child branch was restored" >&2
        exit 6
    fi
    echo "error: metadata update failed and branch rollback was incomplete; manual recovery is required" >&2
    exit 6
fi
