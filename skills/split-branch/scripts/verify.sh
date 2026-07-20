#!/usr/bin/env bash
# Verify one branch in a dedicated, disposable worktree.

set -euo pipefail

usage() {
    echo "usage: verify.sh --branch <ref> --build-cmd <cmd> [--test-cmd <cmd>] [--worktree-root <dir>] [--keep-on-failure]" >&2
}

branch=""
build_cmd=""
build_cmd_given=0
test_cmd=""
test_cmd_given=0
worktree_root=""
worktree_root_given=0
root_is_temporary=0
keep_on_failure=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --branch)
            [[ $# -ge 2 ]] || { usage; exit 5; }
            branch="$2"
            shift 2
            ;;
        --build-cmd)
            [[ $# -ge 2 ]] || { usage; exit 5; }
            build_cmd="$2"
            build_cmd_given=1
            shift 2
            ;;
        --test-cmd)
            [[ $# -ge 2 ]] || { usage; exit 5; }
            test_cmd="$2"
            test_cmd_given=1
            shift 2
            ;;
        --worktree-root)
            [[ $# -ge 2 ]] || { usage; exit 5; }
            worktree_root="$2"
            worktree_root_given=1
            shift 2
            ;;
        --keep-on-failure)
            keep_on_failure=1
            shift
            ;;
        *)
            usage
            exit 5
            ;;
    esac
done

if [[ -z "$branch" || $build_cmd_given -ne 1 || ( $worktree_root_given -eq 1 && -z "$worktree_root" ) ]]; then
    usage
    exit 5
fi

if [[ -z "$worktree_root" ]]; then
    if ! worktree_root=$(mktemp -d "${TMPDIR:-/tmp}/split-branch-verify.XXXXXX"); then
        echo "error: could not create temporary worktree root" >&2
        exit 4
    fi
    root_is_temporary=1
else
    if ! mkdir -p "$worktree_root"; then
        echo "error: could not create worktree root: $worktree_root" >&2
        exit 4
    fi
    worktree_root=$(cd "$worktree_root" && pwd -P)
fi

sanitised_ref=$(printf '%s' "$branch" | LC_ALL=C sed 's/[^A-Za-z0-9._-]/-/g')
worktree_path="$worktree_root/$sanitised_ref"
worktree_created=0
final_status=4

cleanup() {
    local status=$?
    trap - EXIT

    if [[ $worktree_created -eq 1 ]]; then
        if [[ $keep_on_failure -eq 1 && $final_status -ne 0 ]]; then
            echo "worktree kept after failure: $worktree_path" >&2
        else
            git worktree remove --force "$worktree_path" >&2 || true
            if [[ $root_is_temporary -eq 1 ]]; then
                rm -rf "$worktree_root"
            fi
        fi
    elif [[ $root_is_temporary -eq 1 ]]; then
        rm -rf "$worktree_root"
    fi

    exit "$status"
}
trap cleanup EXIT

# --detach allows verification even when the named local branch is checked out
# in the caller's worktree.
if ! git worktree add --detach "$worktree_path" "$branch" >&2; then
    echo "error: could not create worktree for ref: $branch" >&2
    final_status=4
    exit "$final_status"
fi
worktree_created=1

build_status=0
(
    cd "$worktree_path"
    bash -c "$build_cmd"
) >&2 || build_status=$?

test_status=0
if [[ $test_cmd_given -eq 1 ]]; then
    (
        cd "$worktree_path"
        bash -c "$test_cmd"
    ) >&2 || test_status=$?
fi

if [[ $build_status -ne 0 ]]; then
    final_status=1
elif [[ $test_status -ne 0 ]]; then
    final_status=2
else
    final_status=0
fi

if [[ $final_status -eq 0 ]]; then
    ok=true
else
    ok=false
fi

jq -cn \
    --arg branch "$branch" \
    --argjson build "$build_status" \
    --argjson test "$test_status" \
    --argjson ok "$ok" \
    '{branch: $branch, build: $build, test: $test, ok: $ok}'

exit "$final_status"
