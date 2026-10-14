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
    if ! canonical_root=$(cd "$worktree_root" && pwd -P); then
        echo "error: could not canonicalize worktree root: $worktree_root" >&2
        exit 4
    fi
    worktree_root="$canonical_root"
fi

sanitised_ref=$(printf '%s' "$branch" | LC_ALL=C sed 's/[^A-Za-z0-9._-]/-/g')
worktree_path="$worktree_root/$sanitised_ref"
worktree_created=0
final_status=4
emit_verdict=0
build_status=0
test_status=0

cleanup() {
    local status=$?
    local cleanup_failed=0
    trap - EXIT
    set +e

    if [[ $worktree_created -eq 1 ]]; then
        if [[ $keep_on_failure -eq 1 && $final_status -ne 0 ]]; then
            echo "worktree kept after failure: $worktree_path" >&2
        else
            # A command run in the worktree may lock it. Unlock first so that
            # mandatory removal cannot silently leak a successful worktree.
            git worktree unlock "$worktree_path" >/dev/null 2>&1 || true
            if ! git worktree remove --force "$worktree_path" >&2; then
                rm -rf "$worktree_path"
                git worktree prune --expire now >&2
            fi
            if [[ -e "$worktree_path" ]] || \
                git worktree list --porcelain | grep -Fqx "worktree $worktree_path"; then
                echo "error: could not remove worktree: $worktree_path" >&2
                cleanup_failed=1
            fi
        fi
    fi

    if [[ $root_is_temporary -eq 1 && ! ( $keep_on_failure -eq 1 && $final_status -ne 0 && $worktree_created -eq 1 ) ]]; then
        rm -rf "$worktree_root"
        if [[ -e "$worktree_root" ]]; then
            echo "error: could not remove temporary worktree root: $worktree_root" >&2
            cleanup_failed=1
        fi
    fi

    if [[ $cleanup_failed -ne 0 ]]; then
        # Exit 4 is the worktree infrastructure error code; never report a
        # successful verification when its mandatory worktree cleanup failed.
        final_status=4
    elif [[ $emit_verdict -eq 0 ]]; then
        final_status=$status
    fi

    if [[ $emit_verdict -eq 1 ]]; then
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
    fi

    exit "$final_status"
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

(
    cd "$worktree_path"
    bash -c "$build_cmd"
) >&2 || build_status=$?

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

emit_verdict=1
exit "$final_status"
