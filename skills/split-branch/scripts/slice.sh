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
    source_head=$(git rev-parse "$at_commit")
    commit_line=$(git rev-list --parents -n 1 "$source_head")
    if [[ "$commit_line" == *" "* ]]; then
        source_base=${commit_line#* }
        source_base=${source_base%% *}
    else
        # A root commit replays the difference from Git's canonical empty tree.
        source_base=$(git hash-object -t tree /dev/null)
    fi
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
included_files=$(mktemp)
names_file=$(mktemp)
cleanup() {
    rm -f "$GIT_INDEX_FILE" "$build_index" "$raw_patch" "$zero_patch" "$subset_patch" \
        "$inventory_ids" "$included_files" "$names_file"
}
trap cleanup EXIT HUP INT TERM

git diff --binary --full-index -M -U0 "$source_base" "$source_head" >"$raw_patch"

# The analyzer inventory is the sole authority for selectable IDs. File
# ordinals join that filtered inventory back to raw patch sections without
# parsing Git's potentially C-quoted patch headers. Whole-commit replay does
# not select hunks and therefore needs no inventory.
if [[ -z "$at_commit" ]]; then
    script_dir=$(cd "$(dirname "$0")" && pwd)
    if ! analyzer_json=$("$script_dir/analyze.sh" --hunks --base "$source_base" --head "$source_head"); then
        echo "could not obtain hunk inventory" >&2
        exit 5
    fi
    if ! printf '%s' "$analyzer_json" | jq -e \
        '.hunks | type == "array" and all(.[]; (.id | type == "string") and (.file | type == "string"))' \
        >/dev/null; then
        echo "invalid hunk inventory" >&2
        exit 5
    fi
    printf '%s' "$analyzer_json" | jq -r '.hunks[].id' >"$inventory_ids"
    git diff "$source_base" "$source_head" -M --name-only -z >"$names_file"
    file_number=0
    while IFS= read -r -d '' file; do
        file_number=$((file_number + 1))
        if printf '%s' "$analyzer_json" | jq -e --arg file "$file" \
            'any(.hunks[]; .file == $file)' >/dev/null; then
            printf '%s\n' "$file_number" >>"$included_files"
        fi
    done <"$names_file"
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
    awk -v requested_file="$hunks" -v analyzer_file="$inventory_ids" -v included_file="$included_files" '
        BEGIN {
            while ((getline line < requested_file) > 0) {
                sub(/\r$/, "", line)
                if (line != "") {
                    requested[line] = 1
                    requested_count[line]++
                }
            }
            close(requested_file)
            while ((getline line < analyzer_file) > 0) {
                sub(/\r$/, "", line)
                if (line != "") analyzer[++analyzer_count] = line
            }
            close(analyzer_file)
            while ((getline line < included_file) > 0) included[line] = 1
            close(included_file)
        }
        function choose(analyzer_id, id) {
            chosen_count = 0
            if (!(file_number in included)) return 0
            analyzer_index++
            analyzer_id = analyzer[analyzer_index]
            if (analyzer_id == "") inventory_mismatch = 1
            for (id in requested) {
                if (id == analyzer_id) {
                    matched[id] = 1
                    chosen_count += requested_count[id]
                }
            }
            return chosen_count > 0
        }
        function finish_file(should_emit) {
            if (!in_file) return
            if (saw_hunk) {
                if (selected_bodies != "") printf "%s%s", header, selected_bodies
            } else {
                should_emit = choose()
                # A binary section contributes one atomic inventory unit. Track
                # inventory and selection cardinalities per file and reject any
                # inconsistent partial selection (normally impossible via analyze).
                binary_inventory_units = is_binary ? 1 : 0
                binary_selected_units = is_binary ? chosen_count : 0
                if (binary_selected_units > 0 &&
                    binary_selected_units != binary_inventory_units) partial_binary = 1
                if (should_emit) printf "%s", header
            }
        }
        /^diff --git / {
            finish_file()
            in_file = 1
            file_number++
            saw_hunk = 0
            emitting = 0
            selected_bodies = ""
            is_binary = 0
            header = $0 ORS
            next
        }
        /^@@ / && in_file {
            saw_hunk = 1
            emitting = choose()
            if (emitting) selected_bodies = selected_bodies $0 ORS
            next
        }
        {
            if (!in_file) next
            if ($0 == "GIT binary patch" || $0 ~ /^Binary files .* differ$/) is_binary = 1
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
            if (inventory_mismatch || analyzer_index != analyzer_count) {
                print "analyzer inventory does not match source diff" > "/dev/stderr"
                exit 7
            }
            if (partial_binary) {
                print "partial selection of binary file" > "/dev/stderr"
                exit 6
            }
        }
    ' "$raw_patch" >"$zero_patch"
    code=$?
    set -e
    [[ $code -eq 0 ]] || {
        [[ $code -eq 2 ]] && exit 2
        [[ $code -eq 6 ]] && exit 6
        exit 5
    }
fi

# First build the exact selected tree on the inventory base. This zero-context
# application is deliberately against the undrifted base only. Diffing that
# tree back to the base then supplies ordinary context and correct hunk counts,
# including when -U3 would have merged selected and unselected regions.
GIT_INDEX_FILE="$build_index" git read-tree "$source_base"
if [[ -s "$zero_patch" ]]; then
    apply_failed=0
    # GUARDRAIL-OK: undrifted-base -- zero context only constructs the exact base-relative tree.
    GIT_INDEX_FILE="$build_index" git apply --cached --unidiff-zero "$zero_patch" || apply_failed=$?
    if [[ $apply_failed -ne 0 ]]; then
        echo "could not construct selected tree" >&2
        exit 3
    fi
fi
selected_tree=$(GIT_INDEX_FILE="$build_index" git write-tree)
git diff --binary --full-index -M -U3 "${source_base}^{tree}" "$selected_tree" >"$subset_patch"

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
