#!/usr/bin/env bash
#
# git-split/analyze.sh
# Analyzes git diff and outputs structured JSON for branch splitting
#
# Usage: ./analyze.sh [target_branch]
# Output: JSON with file stats, directory groups, and suggested splits
#

set -euo pipefail

# Colors for stderr messages (not captured in JSON output)
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Target lines per split (configurable via env)
TARGET_LINES_PER_SPLIT="${TARGET_LINES_PER_SPLIT:-300}"

# Detect target branch
detect_target_branch() {
    local target="${1:-}"

    if [[ -n "$target" ]]; then
        echo "$target"
        return
    fi

    # Try to get default branch from remote
    if git symbolic-ref refs/remotes/origin/HEAD &>/dev/null; then
        git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'
        return
    fi

    # Fallback: check for main or master
    if git show-ref --verify --quiet refs/heads/main; then
        echo "main"
    elif git show-ref --verify --quiet refs/heads/master; then
        echo "master"
    else
        echo >&2 -e "${RED}Error: Could not detect target branch${NC}"
        exit 1
    fi
}

# Check for uncommitted changes
check_working_tree() {
    if ! git diff --quiet; then
        echo "unstaged changes detected"
    fi
    if ! git diff --cached --quiet; then
        echo "staged uncommitted changes detected"
    fi
}

# Get current branch name
get_current_branch() {
    git branch --show-current
}

# Analyze diff and output file statistics
analyze_diff() {
    local target_branch="$1"
    local current_branch
    current_branch=$(get_current_branch)

    # Get merge base for accurate diff
    local merge_base
    merge_base=$(git merge-base "$target_branch" HEAD 2>/dev/null || echo "$target_branch")

    # Get numstat for line counts
    git diff --numstat "$merge_base"...HEAD 2>/dev/null || git diff --numstat "$target_branch"...HEAD
}

# Detect binary files
detect_binary_files() {
    local target_branch="$1"
    local merge_base
    merge_base=$(git merge-base "$target_branch" HEAD 2>/dev/null || echo "$target_branch")

    git diff --numstat "$merge_base"...HEAD 2>/dev/null | grep -E "^-\s+-\s+" | awk '{print $3}' || true
}

# Group files by directory
# Files matching these patterns are excluded from the budget — generated/vendored content
# dominates diffs but isn't substantively reviewed. Override with EXCLUDE_PATTERNS env.
DEFAULT_EXCLUDE_PATTERNS='(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Cargo\.lock|Gemfile\.lock|go\.sum|composer\.lock)$|(^|/)(node_modules|vendor|dist|build|\.next|\.nuxt|target)/|\.min\.(js|css)$|\.generated\.|__generated__|_pb\.go$|_pb2\.py$'
EXCLUDE_PATTERNS="${EXCLUDE_PATTERNS:-$DEFAULT_EXCLUDE_PATTERNS}"

# Classify a file path: "source", "test", or "excluded"
classify_file() {
    local filepath="$1"

    if [[ "$filepath" =~ $EXCLUDE_PATTERNS ]]; then
        echo "excluded"
        return
    fi

    # Heuristic test detection
    if [[ "$filepath" =~ (^|/)(test|tests|spec|specs|__tests__)/|\.(test|spec)\.[a-zA-Z]+$|_test\.[a-zA-Z]+$|Test\.[a-zA-Z]+$ ]]; then
        echo "test"
        return
    fi

    echo "source"
}

# Bash 3.2-compatible: emit per-file `dir<TAB>kind<TAB>lines<TAB>filepath` rows
# from stdin, then aggregate via awk. Avoids associative arrays.
group_by_directory() {
    awk -F'\t' -v exclude_re="$EXCLUDE_PATTERNS" '
        function classify(fp) {
            if (fp ~ exclude_re) return "excluded"
            # Heuristic: files under test/, tests/, spec/, specs/, __tests__/, or
            # ending in .test.X, .spec.X, _test.X, Test.X
            if (fp ~ /(^|\/)(tests?|specs?|__tests__)\//) return "test"
            if (fp ~ /\.(test|spec)\.[a-zA-Z]+$/) return "test"
            if (fp ~ /(_test|Test)\.[a-zA-Z]+$/) return "test"
            return "source"
        }
        function dirof(fp,    i) {
            i = index(fp, "/")
            if (i == 0) return "(root)"
            return substr(fp, 1, i - 1)
        }
        NF >= 3 && $1 != "-" {
            dir = dirof($3)
            kind = classify($3)
            lines = $1 + $2
            src[dir] += (kind == "source") ? lines : 0
            tst[dir] += (kind == "test")   ? lines : 0
            exc[dir] += (kind == "excluded") ? lines : 0
            count[dir] += 1
            seen[dir] = 1
        }
        END {
            n = 0
            for (d in seen) dirs[++n] = d
            # Stable sort dirs alphabetically for deterministic output
            for (i = 1; i <= n; i++) {
                for (j = i + 1; j <= n; j++) {
                    if (dirs[j] < dirs[i]) { tmp = dirs[i]; dirs[i] = dirs[j]; dirs[j] = tmp }
                }
            }
            print "["
            for (i = 1; i <= n; i++) {
                d = dirs[i]
                # Manually JSON-escape directory name
                gsub(/\\/, "\\\\", d); gsub(/"/, "\\\"", d)
                printf "    {\n"
                printf "      \"directory\": \"%s\",\n", d
                printf "      \"source_lines\": %d,\n", src[dirs[i]]
                printf "      \"test_lines\": %d,\n", tst[dirs[i]]
                printf "      \"excluded_lines\": %d,\n", exc[dirs[i]]
                printf "      \"file_count\": %d\n", count[dirs[i]]
                printf "    }%s\n", (i < n ? "," : "")
            }
            print "]"
        }
    '
}

# Main execution
main() {
    local target_branch
    target_branch=$(detect_target_branch "${1:-}")

    local current_branch
    current_branch=$(get_current_branch)

    if [[ -z "$current_branch" ]]; then
        echo >&2 -e "${RED}Error: Not on a branch (detached HEAD?)${NC}"
        exit 1
    fi

    if [[ "$current_branch" == "$target_branch" ]]; then
        echo >&2 -e "${RED}Error: Current branch is the target branch${NC}"
        exit 1
    fi

    # Collect warnings
    local -a warnings=()
    while IFS= read -r warning; do
        [[ -n "$warning" ]] && warnings+=("$warning")
    done < <(check_working_tree)

    # Collect binary files
    local -a binary_files=()
    while IFS= read -r binary; do
        [[ -n "$binary" ]] && binary_files+=("$binary")
    done < <(detect_binary_files "$target_branch")

    if (( ${#binary_files[@]} > 0 )); then
        warnings+=("binary files detected: ${binary_files[*]}")
    fi

    # Get diff stats
    local diff_output
    diff_output=$(analyze_diff "$target_branch")

    # Calculate totals, classifying each file as source / test / excluded
    local total_files=0
    local total_source_lines=0
    local total_test_lines=0
    local total_excluded_lines=0
    local total_added=0
    local total_deleted=0
    local -a file_stats=()
    local -a excluded_files=()

    while IFS=$'\t' read -r added deleted filepath; do
        [[ -z "$filepath" ]] && continue
        ((total_files++))

        local kind="binary"
        if [[ "$added" != "-" ]]; then
            ((total_added += added))
            ((total_deleted += deleted))
            local lines=$((added + deleted))
            kind=$(classify_file "$filepath")
            case "$kind" in
                source)   ((total_source_lines += lines)) ;;
                test)     ((total_test_lines += lines)) ;;
                excluded) ((total_excluded_lines += lines)); excluded_files+=("$filepath") ;;
            esac
        fi

        file_stats+=("{\"file\": $(echo -n "$filepath" | jq -Rs .), \"added\": \"$added\", \"deleted\": \"$deleted\", \"kind\": \"$kind\"}")
    done <<< "$diff_output"

    local total_lines=$((total_added + total_deleted))
    # Reviewer-weighted budget: source counts 1x, tests 0.5x, excluded 0x.
    # Use integer math: weighted = source + (test / 2). Skill-side documents 0.5x.
    local weighted_review_lines=$(( total_source_lines + (total_test_lines / 2) ))

    if (( ${#excluded_files[@]} > 0 )); then
        warnings+=("excluded ${#excluded_files[@]} generated/lockfile/vendored files from review-weighted budget (${total_excluded_lines} lines)")
    fi

    # Group by directory
    local dir_groups
    dir_groups=$(echo "$diff_output" | group_by_directory)

    # Build JSON output
    cat <<EOF
{
  "current_branch": $(echo -n "$current_branch" | jq -Rs .),
  "target_branch": $(echo -n "$target_branch" | jq -Rs .),
  "total_files": $total_files,
  "total_lines_added": $total_added,
  "total_lines_deleted": $total_deleted,
  "total_lines": $total_lines,
  "total_source_lines": $total_source_lines,
  "total_test_lines": $total_test_lines,
  "total_excluded_lines": $total_excluded_lines,
  "weighted_review_lines": $weighted_review_lines,
  "target_lines_per_split": $TARGET_LINES_PER_SPLIT,
  "directory_groups": $dir_groups,
  "files": [
$(IFS=,; echo "    ${file_stats[*]:-}" | sed 's/},{/},\n    {/g')
  ],
  "warnings": $(printf '%s\n' "${warnings[@]:-}" | jq -Rs 'split("\n") | map(select(length > 0))'),
  "binary_files": $(printf '%s\n' "${binary_files[@]:-}" | jq -Rs 'split("\n") | map(select(length > 0))'),
  "excluded_files": $(printf '%s\n' "${excluded_files[@]:-}" | jq -Rs 'split("\n") | map(select(length > 0))')
}
EOF
}

# Run main with all arguments
main "$@"
