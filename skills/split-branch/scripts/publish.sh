#!/usr/bin/env bash
# Publish a split branch in the ordering required by GitHub and GitLab.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=stackmeta.sh
source "$SCRIPT_DIR/stackmeta.sh"

usage() {
    echo "usage: publish.sh --plan <plan.json> [--remote <name>] [--forge github|gitlab] [--dry-run] [--fork] [--no-force-push]" >&2
}

bad_arguments() {
    usage
    exit 5
}

plan=""
remote=""
forge="github"
dry_run=false
fork=false
no_force_push=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --plan|--remote|--forge)
            [[ $# -ge 2 && -n "$2" ]] || bad_arguments
            case "$1" in
                --plan) plan="$2" ;;
                --remote) remote="$2" ;;
                --forge) forge="$2" ;;
            esac
            shift 2
            ;;
        --dry-run) dry_run=true; shift ;;
        --fork) fork=true; shift ;;
        --no-force-push) no_force_push=true; shift ;;
        *) bad_arguments ;;
    esac
done

[[ -n "$plan" && -f "$plan" ]] || bad_arguments
[[ "$forge" == "github" || "$forge" == "gitlab" ]] || bad_arguments

# Besides checking types, require slices to be in their declared position order.
if ! jq -e '
    type == "object" and
    (.base | type == "string" and length > 0) and
    (.original_branch | type == "string" and length > 0) and
    (.original_pr == null or (.original_pr | type == "number" and floor == . and . > 0)) and
    (.slices | type == "array" and length > 0) and
    (.slices | to_entries | all(
        .key as $i | .value as $s |
        ($s | type == "object") and
        ($s.branch | type == "string" and length > 0) and
        ($s.parent | type == "string" and length > 0) and
        ($s.title | type == "string") and
        ($s.body | type == "string") and
        ($s.position == ($i + 1))))
' "$plan" >/dev/null 2>&1; then
    echo "error: malformed plan" >&2
    exit 5
fi

if [[ -z "$remote" ]]; then
    remote=$(git config --get remote.pushDefault || true)
    remote=${remote:-origin}
fi

slice_count=$(jq '.slices | length' "$plan")
original_branch=$(jq -r '.original_branch' "$plan")
original_pr=$(jq -r '.original_pr // empty' "$plan")
bottom_branch=$(jq -r '.slices[0].branch' "$plan")
top_branch=$(jq -r '.slices[-1].branch' "$plan")

index=0
while [[ $index -lt $slice_count ]]; do
    branch=$(jq -r ".slices[$index].branch" "$plan")
    if ! git show-ref --verify --quiet "refs/heads/$branch"; then
        echo "error: slice branch does not exist locally: $branch" >&2
        exit 3
    fi
    index=$((index + 1))
done

if [[ "$dry_run" != true ]]; then
    cli="gh"
    [[ "$forge" == "gitlab" ]] && cli="glab"
    if ! command -v "$cli" >/dev/null 2>&1; then
        echo "error: required forge CLI not found: $cli" >&2
        exit 7
    fi
fi

print_command() {
    local separator=""
    local argument
    for argument in "$@"; do
        printf '%s' "$separator"
        printf '%q' "$argument"
        separator=" "
    done
    printf '\n'
}

run_command() {
    if [[ "$dry_run" == true ]]; then
        print_command "$@"
    else
        "$@"
    fi
}

# Resolve every parent and construct every body before making any remote change.
# This prevents a malformed later slice from leaving a partially published stack.
declare -a slice_branches slice_parents slice_titles slice_bodies
index=0
while [[ $index -lt $slice_count ]]; do
    branch=$(jq -r ".slices[$index].branch" "$plan")
    parent=$(jq -r ".slices[$index].parent" "$plan")
    title=$(jq -r ".slices[$index].title" "$plan")
    body=$(jq -r ".slices[$index].body" "$plan")
    position=$(jq -r ".slices[$index].position" "$plan")
    if ! base_sha=$(git rev-parse --verify "${parent}^{commit}" 2>/dev/null); then
        echo "error: slice parent does not resolve locally: $parent" >&2
        exit 5
    fi
    if ! body=$(printf '%s' "$body" | stackmeta_upsert "$parent" "$base_sha" "$position" "$slice_count"); then
        echo "error: malformed stack metadata in slice body" >&2
        exit 5
    fi
    slice_branches[$index]="$branch"
    slice_parents[$index]="$parent"
    slice_titles[$index]="$title"
    slice_bodies[$index]="$body"
    index=$((index + 1))
done

# Remote branches must all exist before any forge operation references them.
index=0
while [[ $index -lt $slice_count ]]; do
    branch=$(jq -r ".slices[$index].branch" "$plan")
    run_command git push -u "$remote" "$branch"
    index=$((index + 1))
done

if [[ "$no_force_push" == true ]]; then
    echo "NOTE: The original branch cannot be rewritten; create a new PR/MR instead of retargeting the original."
else
    run_command git push --force-with-lease "$remote" "$original_branch"

    # Warn reviewers while the original diff and inline-comment anchors remain intact.
    if [[ -n "$original_pr" ]]; then
        message="This change has been split into a stacked series; the original will be retargeted onto $top_branch."
        if [[ "$forge" == "github" ]]; then
            run_command gh pr comment "$original_pr" --body "$message"
        else
            run_command glab mr note "$original_pr" --message "$message"
        fi
    fi
fi

index=0
while [[ $index -lt $slice_count ]]; do
    branch=${slice_branches[$index]}
    parent=${slice_parents[$index]}
    title=${slice_titles[$index]}
    body=${slice_bodies[$index]}

    if [[ "$forge" == "github" ]]; then
        run_command gh pr create --draft --base "$parent" --head "$branch" --title "$title" --body "$body"
    else
        run_command glab mr create --draft --yes --target-branch "$parent" --source-branch "$branch" --title "$title" --description "$body"
    fi
    index=$((index + 1))
done

if [[ "$no_force_push" != true && -n "$original_pr" ]]; then
    if [[ "$forge" == "github" ]]; then
        run_command gh pr edit "$original_pr" --base "$top_branch"
    elif [[ "$fork" == true ]]; then
        echo "NOTE: GitLab fork MR retargeting is never automatic; run the following retarget command manually."
        # A dry run consists entirely of printable commands. During a real fork
        # publish, print this one command rather than changing the MR.
        print_command glab mr update "$original_pr" --yes --target-branch "$top_branch"
    else
        run_command glab mr update "$original_pr" --yes --target-branch "$top_branch"
    fi
fi

# Only the primary, bottom slice starts reviewable; all dependants remain draft.
if [[ "$forge" == "github" ]]; then
    run_command gh pr ready "$bottom_branch"
else
    run_command glab mr update "$bottom_branch" --yes --ready
fi
