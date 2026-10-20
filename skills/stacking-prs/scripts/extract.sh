#!/usr/bin/env bash
#
# git-split/extract.sh
# Safely extracts specified files/changes into a new base branch
#
# Usage: ./extract.sh <new_branch_name> <target_branch> <file1> [file2] ...
# Output: JSON with operation results
#
# Operations:
#   1. Creates backup of current branch
#   2. Creates new branch from target
#   3. Extracts specified files from current branch
#   4. Returns to original branch (ready for rebase)
#

set -euo pipefail

# Colors for stderr messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Globals for cleanup
ORIGINAL_BRANCH=""
BACKUP_BRANCH=""
NEW_BRANCH=""
CREATED_BRANCHES=()

# Cleanup on error
cleanup_on_error() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        echo >&2 -e "${RED}Error occurred, attempting cleanup...${NC}"

        # Return to original branch if possible
        if [[ -n "$ORIGINAL_BRANCH" ]]; then
            git checkout "$ORIGINAL_BRANCH" 2>/dev/null || true
        fi

        # Delete created branches (except backup)
        for branch in "${CREATED_BRANCHES[@]:-}"; do
            [[ -z "$branch" ]] && continue
            if [[ "$branch" != "$BACKUP_BRANCH" ]]; then
                git branch -D "$branch" 2>/dev/null || true
                echo >&2 -e "${YELLOW}Cleaned up branch: $branch${NC}"
            fi
        done

        if [[ -n "$BACKUP_BRANCH" ]]; then
            echo >&2 -e "${YELLOW}Backup branch preserved: $BACKUP_BRANCH${NC}"
        fi
    fi
    exit $exit_code
}

trap cleanup_on_error EXIT

# Validate inputs
validate_inputs() {
    local new_branch="$1"
    local target_branch="$2"
    shift 2
    local files=("$@")

    if [[ -z "$new_branch" ]]; then
        echo >&2 -e "${RED}Error: New branch name required${NC}"
        return 1
    fi

    if [[ -z "$target_branch" ]]; then
        echo >&2 -e "${RED}Error: Target branch required${NC}"
        return 1
    fi

    if [[ ${#files[@]} -eq 0 ]]; then
        echo >&2 -e "${RED}Error: At least one file required${NC}"
        return 1
    fi

    # Check if new branch already exists
    if git show-ref --verify --quiet "refs/heads/$new_branch"; then
        echo >&2 -e "${RED}Error: Branch '$new_branch' already exists${NC}"
        return 1
    fi

    # Check if target branch exists
    if ! git show-ref --verify --quiet "refs/heads/$target_branch"; then
        # Try remote
        if ! git show-ref --verify --quiet "refs/remotes/origin/$target_branch"; then
            echo >&2 -e "${RED}Error: Target branch '$target_branch' not found${NC}"
            return 1
        fi
    fi

    # Check for uncommitted changes
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo >&2 -e "${RED}Error: Uncommitted changes detected. Please commit or stash first.${NC}"
        return 1
    fi

    return 0
}

# Create backup branch
create_backup() {
    local current_branch="$1"
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)

    BACKUP_BRANCH="backup/${current_branch}_${timestamp}"

    git branch "$BACKUP_BRANCH"
    CREATED_BRANCHES+=("$BACKUP_BRANCH")

    echo "$BACKUP_BRANCH"
}

# Extract files to new branch.
#
# Per requested file:
#   1. Modified or added in current_branch -> checkout from current_branch
#   2. Deleted in current_branch (existed at merge-base, gone in current) -> git rm
#   3. Never existed in either -> failed_files
#
# Renames: pass BOTH the old and new path to replicate the rename in this PR.
extract_files() {
    local new_branch="$1"
    local target_branch="$2"
    local current_branch="$3"
    shift 3
    local files=("$@")

    NEW_BRANCH="$new_branch"

    # Compute merge-base BEFORE switching branches so we can detect deletions
    local merge_base
    merge_base=$(git merge-base "$target_branch" "$current_branch" 2>/dev/null || echo "$target_branch")

    git checkout -b "$new_branch" "$target_branch"
    CREATED_BRANCHES+=("$new_branch")

    local -a extracted_files=()
    local -a deleted_files=()
    local -a failed_files=()

    for file in "${files[@]}"; do
        local in_current=0 in_base=0
        git show "$current_branch:$file" &>/dev/null && in_current=1
        git show "$merge_base:$file"   &>/dev/null && in_base=1

        if (( in_current )); then
            if git checkout "$current_branch" -- "$file" 2>/dev/null; then
                extracted_files+=("$file")
            else
                failed_files+=("$file (checkout failed)")
            fi
        elif (( in_base )); then
            # Deleted in current_branch -> replicate the deletion
            if git rm -- "$file" &>/dev/null; then
                deleted_files+=("$file")
            else
                failed_files+=("$file (rm failed)")
            fi
        else
            failed_files+=("$file (not found in current or merge-base)")
        fi
    done

    local changes=$(( ${#extracted_files[@]} + ${#deleted_files[@]} ))
    if (( changes > 0 )); then
        # Stage only the files we touched, not the whole tree
        if (( ${#extracted_files[@]} > 0 )); then
            git add -- "${extracted_files[@]}"
        fi
        # `git rm` already staged the deletes

        local commit_msg
        commit_msg="Extract changes for stacked PR

Files extracted from $current_branch:
$(printf '+ %s\n' "${extracted_files[@]}")"
        if (( ${#deleted_files[@]} > 0 )); then
            commit_msg+=$'\n'"$(printf -- '- %s\n' "${deleted_files[@]}")"
        fi
        commit_msg+=$'\n\n'"This branch is the base for stacked PRs."

        # Redirect to stderr — function's stdout carries our return value
        git commit -m "$commit_msg" >&2
    fi

    git checkout "$current_branch" >&2

    printf '%s\n' "${extracted_files[@]:-}" > /tmp/git_split_extracted.txt
    printf '%s\n' "${deleted_files[@]:-}"   > /tmp/git_split_deleted.txt
    printf '%s\n' "${failed_files[@]:-}"    > /tmp/git_split_failed.txt

    local failed_count="${#failed_files[@]}"
    echo "${changes}:${failed_count}"
}

# Generate JSON output
output_json() {
    local success="$1"
    local new_branch="$2"
    local backup_branch="$3"
    local current_branch="$4"
    local extracted_count="$5"
    local failed_count="$6"
    local message="$7"

    local extracted_files=()
    local deleted_files=()
    local failed_files=()

    # bash 3.2 compat: read line-by-line instead of `mapfile`
    if [[ -f /tmp/git_split_extracted.txt ]]; then
        while IFS= read -r line; do
            [[ -n "$line" ]] && extracted_files+=("$line")
        done < /tmp/git_split_extracted.txt
        rm -f /tmp/git_split_extracted.txt
    fi

    if [[ -f /tmp/git_split_deleted.txt ]]; then
        while IFS= read -r line; do
            [[ -n "$line" ]] && deleted_files+=("$line")
        done < /tmp/git_split_deleted.txt
        rm -f /tmp/git_split_deleted.txt
    fi

    if [[ -f /tmp/git_split_failed.txt ]]; then
        while IFS= read -r line; do
            [[ -n "$line" ]] && failed_files+=("$line")
        done < /tmp/git_split_failed.txt
        rm -f /tmp/git_split_failed.txt
    fi

    cat <<EOF
{
  "success": $success,
  "new_branch": $(echo -n "$new_branch" | jq -Rs .),
  "backup_branch": $(echo -n "$backup_branch" | jq -Rs .),
  "original_branch": $(echo -n "$current_branch" | jq -Rs .),
  "extracted_files_count": $extracted_count,
  "failed_files_count": $failed_count,
  "extracted_files": $(printf '%s\n' "${extracted_files[@]:-}" | jq -Rs 'split("\n") | map(select(length > 0))'),
  "deleted_files": $(printf '%s\n' "${deleted_files[@]:-}" | jq -Rs 'split("\n") | map(select(length > 0))'),
  "failed_files": $(printf '%s\n' "${failed_files[@]:-}" | jq -Rs 'split("\n") | map(select(length > 0))'),
  "message": $(echo -n "$message" | jq -Rs .),
  "next_step": "git rebase --onto $new_branch \$ORIG_BASE $current_branch  # ORIG_BASE = merge-base(target_branch, current_branch) BEFORE the split"
}
EOF
}

# Main execution
main() {
    if [[ $# -lt 3 ]]; then
        cat >&2 <<EOF
Usage: $0 <new_branch_name> <target_branch> <file1> [file2] ...

Arguments:
  new_branch_name  Name for the new base branch
  target_branch    Branch to base the new branch on (e.g., main)
  file1, file2...  Files to extract into the new branch

Example:
  $0 feature/json-utils main src/utils/json.ts src/utils/json.test.ts
EOF
        exit 1
    fi

    local new_branch="$1"
    local target_branch="$2"
    shift 2
    local files=("$@")

    # Get current branch
    ORIGINAL_BRANCH=$(git branch --show-current)

    if [[ -z "$ORIGINAL_BRANCH" ]]; then
        echo >&2 -e "${RED}Error: Not on a branch (detached HEAD?)${NC}"
        output_json "false" "" "" "" "0" "0" "Not on a branch"
        exit 1
    fi

    # Validate
    if ! validate_inputs "$new_branch" "$target_branch" "${files[@]}"; then
        output_json "false" "" "" "$ORIGINAL_BRANCH" "0" "0" "Validation failed"
        exit 1
    fi

    # Create backup
    echo >&2 -e "${GREEN}Creating backup branch...${NC}"
    local backup
    backup=$(create_backup "$ORIGINAL_BRANCH")
    echo >&2 -e "${GREEN}Backup created: $backup${NC}"

    # Extract files
    echo >&2 -e "${GREEN}Extracting files to new branch...${NC}"
    local result
    result=$(extract_files "$new_branch" "$target_branch" "$ORIGINAL_BRANCH" "${files[@]}")

    local extracted_count="${result%%:*}"
    local failed_count="${result##*:}"

    if [[ $extracted_count -eq 0 ]]; then
        output_json "false" "$new_branch" "$backup" "$ORIGINAL_BRANCH" "$extracted_count" "$failed_count" "No files were extracted"
        exit 1
    fi

    echo >&2 -e "${GREEN}Successfully extracted $extracted_count files to $new_branch${NC}"

    if [[ $failed_count -gt 0 ]]; then
        echo >&2 -e "${YELLOW}Warning: $failed_count files could not be extracted${NC}"
    fi

    output_json "true" "$new_branch" "$backup" "$ORIGINAL_BRANCH" "$extracted_count" "$failed_count" "Extraction successful"
}

main "$@"
