#!/usr/bin/env bash
# Restack a child branch after its recorded parent has been squash-merged.

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
        --dry-run)
            dry_run=1
            shift
            ;;
        *)
            usage
            exit 5
            ;;
    esac
done

[[ -n "$branch" && -n "$onto" ]] || { usage; exit 5; }

if ! git rev-parse --verify --quiet "$branch^{commit}" >/dev/null ||
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
if [[ "$remote_url" == *://* ]]; then
    repo_slug=${remote_url#*://}
    repo_slug=${repo_slug#*/}
elif [[ "$remote_url" == *@*:* ]]; then
    repo_slug=${remote_url#*:}
fi
repo_slug=${repo_slug%.git}

forge="gh"
if [[ "$remote_url" == *gitlab* ]]; then
    forge="glab"
fi

body_file=$(mktemp "${TMPDIR:-/tmp}/restack-body.XXXXXX")
updated_body=$(mktemp "${TMPDIR:-/tmp}/restack-updated.XXXXXX")
rebase_output=$(mktemp "${TMPDIR:-/tmp}/restack-rebase.XXXXXX")
cleanup() {
    rm -f "$body_file" "$updated_body" "$rebase_output"
}
trap cleanup EXIT

fetch_body() {
    if [[ "$forge" == "glab" ]]; then
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
    if [[ "$forge" == "glab" ]]; then
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

body_fetched=0
if [[ -z "$base_sha" ]]; then
    if ! fetch_body >"$body_file"; then
        echo "error: recorded base sha is unavailable; pass --base-sha explicitly" >&2
        exit 2
    fi
    body_fetched=1

    parse_status=0
    if base_sha=$("$STACKMETA" parse base-sha <"$body_file"); then
        parse_status=0
    else
        parse_status=$?
    fi
    if [[ $parse_status -eq 2 || $parse_status -eq 3 || $parse_status -eq 4 ]]; then
        echo "error: PR/MR stack metadata is absent or malformed; pass --base-sha explicitly" >&2
        exit 2
    elif [[ $parse_status -ne 0 ]]; then
        echo "error: could not parse PR/MR stack metadata; pass --base-sha explicitly" >&2
        exit 2
    fi
fi

if ! git rev-parse --verify --quiet "$base_sha^{commit}" >/dev/null; then
    echo "error: recorded base sha '$base_sha' does not resolve; pass --base-sha explicitly" >&2
    exit 2
fi

if [[ $dry_run -eq 1 ]]; then
    printf 'git rebase --onto %q %q %q\n' "$onto" "$base_sha" "$branch"
    exit 0
fi

if ! git rebase --onto "$onto" "$base_sha" "$branch" >"$rebase_output" 2>&1; then
    conflicts=$(git diff --name-only --diff-filter=U 2>/dev/null || true)
    git rebase --abort >/dev/null 2>&1 || true
    if [[ -n "$conflicts" ]]; then
        echo "error: rebase conflict in:" >&2
        printf '%s\n' "$conflicts" >&2
    else
        echo "error: rebase failed; rebase was aborted" >&2
        cat "$rebase_output" >&2
    fi
    exit 3
fi

new_base_sha=$(git rev-parse "$onto^{commit}")
if [[ $body_fetched -eq 0 ]]; then
    if ! fetch_body >"$body_file"; then
        echo "error: rebase succeeded, but the PR/MR body could not be read" >&2
        exit 1
    fi
fi

parent=""
position=""
metadata_status=0
if parent=$("$STACKMETA" parse parent <"$body_file") &&
   position=$("$STACKMETA" parse position <"$body_file"); then
    metadata_status=0
else
    metadata_status=$?
fi

if [[ $metadata_status -eq 2 && -n "$base_sha" ]]; then
    parent="$onto"
    position="1/1"
elif [[ $metadata_status -ne 0 ]]; then
    echo "error: rebase succeeded, but PR/MR stack metadata is malformed" >&2
    exit 1
fi

position_number=${position%/*}
total=${position#*/}
"$STACKMETA" upsert "$parent" "$new_base_sha" "$position_number" "$total" \
    <"$body_file" >"$updated_body"
update_body >/dev/null
