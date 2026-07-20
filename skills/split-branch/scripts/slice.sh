#!/usr/bin/env bash
# Materialize a hunk subset without changing the caller's index or worktree.
set -euo pipefail

usage() {
    echo "usage: slice.sh --base <ref> --head <ref> --branch <name> --hunks <file> [--message <msg>] [--parent <ref>]" >&2
    echo "       slice.sh --at-commit <sha> --parent <ref> --branch <name>" >&2
    exit 5
}

base="" head="" branch="" hunks="" message="split branch slice" parent="" at_commit=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --base|--head|--branch|--hunks|--message|--parent|--at-commit)
            [[ $# -ge 2 ]] || usage
            case "$1" in
                --base) base="$2" ;;
                --head) head="$2" ;;
                --branch) branch="$2" ;;
                --hunks) hunks="$2" ;;
                --message) message="$2" ;;
                --parent) parent="$2" ;;
                --at-commit) at_commit="$2" ;;
            esac
            shift 2
            ;;
        *) usage ;;
    esac
done

[[ -n "$branch" ]] || usage
git check-ref-format --branch "$branch" >/dev/null 2>&1 || usage
if git show-ref --verify --quiet "refs/heads/$branch"; then
    echo "branch already exists: $branch" >&2
    exit 4
fi
if [[ -n "$at_commit" ]]; then
    [[ -n "$parent" && -z "$base" && -z "$head" && -z "$hunks" ]] || usage
    git rev-parse --verify "${at_commit}^{commit}" >/dev/null 2>&1 || usage
    source_base=$(git rev-parse "${at_commit}^") || usage
    source_head=$(git rev-parse "$at_commit")
else
    [[ -n "$base" && -n "$head" && -n "$hunks" && -z "$at_commit" ]] || usage
    [[ -f "$hunks" ]] || usage
    parent=${parent:-$base}
    source_base=$(git rev-parse --verify "${base}^{commit}") || usage
    source_head=$(git rev-parse --verify "${head}^{commit}") || usage
fi
git rev-parse --verify "${parent}^{commit}" >/dev/null 2>&1 || usage

# A clean repository is a precondition. Capturing porcelain also makes explicit
# that none of the plumbing below may alter either caller-visible state.
status_before=$(git status --porcelain)
[[ -z "$status_before" ]] || { echo "working tree is not clean" >&2; exit 5; }
caller_index=$(git rev-parse --git-path index)

GIT_INDEX_FILE="$(mktemp -u)"
export GIT_INDEX_FILE
build_index="$(mktemp -u)"
raw_patch=$(mktemp)
zero_patch=$(mktemp)
subset_patch=$(mktemp)
inventory_ids=$(mktemp)
cleanup() {
    rm -f "$GIT_INDEX_FILE" "$build_index" "$raw_patch" "$zero_patch" "$subset_patch" "$inventory_ids"
}
trap cleanup EXIT HUP INT TERM

git diff --binary --full-index -U0 "$source_base" "$source_head" >"$raw_patch"

# When the additive analyzer mode is installed, accept its IDs directly. The
# ordered fallback aliases below keep this script usable before that task lands.
script_dir=$(cd "$(dirname "$0")" && pwd)
if analyzer_json=$("$script_dir/analyze.sh" --hunks --base "$source_base" --head "$source_head" 2>/dev/null); then
    printf '%s' "$analyzer_json" | jq -r '.. | objects | select(has("id")) | .id' >"$inventory_ids" 2>/dev/null || :
fi

if [[ -n "$at_commit" ]]; then
    cp "$raw_patch" "$zero_patch"
else
    # Split a -U0 patch into its identity units. Text hunks are independent;
    # binary and metadata-only file sections are one all-or-nothing unit. The
    # complete extended file header is copied verbatim for every selected unit.
    # The no-newline marker remains in its hunk because hunk bodies are retained
    # as complete line sequences.
    set +e
    awk -v requested_file="$hunks" -v analyzer_file="$inventory_ids" '
        BEGIN {
            while ((getline line < requested_file) > 0) {
                sub(/\r$/, "", line)
                if (line != "") requested[line] = 1
            }
            close(requested_file)
            while ((getline line < analyzer_file) > 0) {
                sub(/\r$/, "", line)
                if (line != "") analyzer[++analyzer_count] = line
            }
            close(analyzer_file)
        }
        function choose(n, canonical, short_id, upper_id, plain, analyzer_id, id) {
            canonical = sprintf("hunk-%04d", n)
            short_id = sprintf("hunk-%d", n)
            upper_id = sprintf("H%04d", n)
            plain = sprintf("%d", n)
            analyzer_id = analyzer[n]
            for (id in requested) {
                if (id == canonical || id == short_id || id == upper_id ||
                    id == plain || (analyzer_id != "" && id == analyzer_id)) {
                    matched[id] = 1
                    return 1
                }
            }
            return 0
        }
        function finish_file(should_emit) {
            if (!in_file) return
            if (saw_hunk) {
                if (selected_bodies != "") printf "%s%s", header, selected_bodies
            } else {
                unit++
                should_emit = choose(unit)
                if (should_emit) printf "%s", header
            }
        }
        /^diff --git / {
            finish_file()
            in_file = 1
            saw_hunk = 0
            emitting = 0
            selected_bodies = ""
            header = $0 ORS
            next
        }
        /^@@ / && in_file {
            saw_hunk = 1
            unit++
            emitting = choose(unit)
            if (emitting) selected_bodies = selected_bodies $0 ORS
            next
        }
        {
            if (!in_file) next
            if (!saw_hunk) header = header $0 ORS
            else if (emitting) selected_bodies = selected_bodies $0 ORS
        }
        END {
            finish_file()
            missing = 0
            for (id in requested) {
                if (!(id in matched)) {
                    print "unknown hunk id: " id > "/dev/stderr"
                    missing = 1
                }
            }
            if (missing) exit 2
        }
    ' "$raw_patch" >"$zero_patch"
    code=$?
    set -e
    [[ $code -eq 0 ]] || {
        [[ $code -eq 2 ]] && exit 2
        exit 5
    }
fi

# First build the exact selected tree on the inventory base. This zero-context
# application is deliberately against the undrifted base only. Diffing that
# tree back to the base then supplies ordinary context and correct hunk counts,
# including when -U3 would have merged selected and unselected regions.
GIT_INDEX_FILE="$build_index" git read-tree "$source_base"
if [[ -s "$zero_patch" ]]; then
    if ! GIT_INDEX_FILE="$build_index" git apply --cached --unidiff-zero "$zero_patch"; then
        echo "could not construct selected tree" >&2
        exit 3
    fi
fi
selected_tree=$(GIT_INDEX_FILE="$build_index" git write-tree)
git diff --binary --full-index -U3 "${source_base}^{tree}" "$selected_tree" >"$subset_patch"

# Materialize onto the requested parent with the mandated throwaway-index
# sequence. --3way is paired with --full-index and lets a parent drift from the
# inventory base without importing any unselected changes.
git read-tree "$parent"
if [[ -s "$subset_patch" ]]; then
    if ! git apply --cached --3way "$subset_patch"; then
        echo "selected patch did not apply to parent" >&2
        exit 3
    fi
fi
tree=$(git write-tree)
commit=$(printf '%s\n' "$message" | git commit-tree "$tree" -p "$parent")
[[ "$(GIT_INDEX_FILE="$caller_index" git status --porcelain)" == "$status_before" ]] || {
    echo "internal error: caller state changed" >&2
    exit 5
}
# Keep branch creation last so every preceding failure leaves no stray ref.
git branch "$branch" "$commit"
printf '%s\n' "$commit"
