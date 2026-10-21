#!/usr/bin/env bash
#
# git-split/analyze.sh
# Analyzes git diff and outputs structured JSON for branch splitting
#
# Usage: ./analyze.sh [target_branch]
# Output: JSON with per-line review-weighted totals, directory groups, and per-file rows
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for stderr messages (not captured in JSON output)
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Split goals, review weights and file patterns resolve per key, highest first: env var, project
# config (<repo>/.quirk/stacking-prs.json), user config (~/.quirk/stacking-prs.json), built-in
# default. A changed line costs its file's weight, capped by every line discount that applies to
# it; weigh.awk documents the rule.
GOAL_VARS="TARGET_LINES_PER_SPLIT HARD_CAP SKIP_THRESHOLD"
WEIGHT_VARS="TEST_WEIGHT FIXTURE_WEIGHT RISKY_WEIGHT PROSE_WEIGHT COMMENT_WEIGHT IMPORT_WEIGHT MOVED_WEIGHT DELETION_WEIGHT"

USER_CFG="$HOME/.quirk/stacking-prs.json"
PROJECT_CFG=""
CONFIG_KEYS='["target_lines_per_split","hard_cap","skip_threshold","weights","patterns"]'
WEIGHT_KEYS='["test","fixture","risky","prose","comment","import","moved","deletion"]'
PATTERN_KEYS='["exclude","fixture","risky","prose"]'
CONFIG_FILES=()

# Files matching these patterns are excluded from the budget — generated/vendored content
# dominates diffs but isn't substantively reviewed.
DEFAULT_EXCLUDE_PATTERNS='(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Cargo\.lock|Gemfile\.lock|go\.sum|composer\.lock)$|(^|/)(node_modules|vendor|dist|build|\.next|\.nuxt|target)/|\.min\.(js|css)$|\.generated\.|__generated__|_pb\.go$|_pb2\.py$'

# Bulk data nobody reads line by line.
DEFAULT_FIXTURE_PATTERNS='(^|/)(__snapshots__|fixtures?|testdata|goldens?|snapshots)/|\.snap$|\.golden$'

# Small diffs here deserve a smaller PR: schema, auth/security, CI and infrastructure.
DEFAULT_RISKY_PATTERNS='(^|/)(migrations?|alembic)/|(^|/)db/migrate/|(^|/)schema\.(rb|sql|prisma)$|\.prisma$|(^|/)(auth|authn|authz|security|crypto|permissions?)(/|[._-])|(^|/)\.github/workflows/|(^|/)\.gitlab-ci\.yml$|\.tf$|(^|/)(terraform|helm|k8s)/|(^|/)Dockerfile'

DEFAULT_PROSE_PATTERNS='\.(md|mdx|rst|txt|adoc)$'

die() {
    echo >&2 -e "${RED}Error: $*${NC}"
    exit 1
}

load_config() {
    local root file unknown
    root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
    PROJECT_CFG="$root/.quirk/stacking-prs.json"
    for file in "$USER_CFG" "$PROJECT_CFG"; do
        [[ -f "$file" ]] || continue
        jq -e 'type == "object"' "$file" >/dev/null 2>&1 || die "$file is not a valid JSON object"
        unknown=$(jq -r --argjson top "$CONFIG_KEYS" --argjson w "$WEIGHT_KEYS" --argjson p "$PATTERN_KEYS" '
            (keys - $top | .[]),
            (if (.weights // {} | type) != "object" then "weights (must be an object)"
             else (.weights // {} | keys - $w | .[] | "weights." + .) end),
            (if (.patterns // {} | type) != "object" then "patterns (must be an object)"
             else (.patterns // {} | keys - $p | .[] | "patterns." + .),
                  (.patterns // {} | to_entries[]
                   | select(.value | if type == "string" then false
                                     elif type == "array" then any(.[]; type != "string" or . == "")
                                     else true end)
                   | "patterns." + .key + " (must be a regex or an array of non-empty regexes)") end)' "$file")
        [[ -z "$unknown" ]] || die "$file: unknown or malformed key(s): $(echo $unknown)"
        CONFIG_FILES+=("$file")
    done
}

# Prints the value at a jq path in one config file (an array joined with `|`); fails when the
# file or the key is absent, so a 0 weight still counts as set.
cfg_get() {
    local file="$1" path="$2"
    [[ -n "$file" && -f "$file" ]] || return 1
    jq -er "$path | if type == \"array\" then join(\"|\") else . end // empty" "$file" 2>/dev/null
}

# Sets NAME and NAME_SOURCE (env, project, user or default).
resolve() {
    local name="$1" path="$2" default="$3" value source
    if [[ -n "${!name:-}" ]]; then
        value="${!name}"; source="env"
    elif value=$(cfg_get "$PROJECT_CFG" "$path"); then
        source="project"
    elif value=$(cfg_get "$USER_CFG" "$path"); then
        source="user"
    else
        value="$default"; source="default"
    fi
    printf -v "$name" '%s' "$value"
    printf -v "${name}_SOURCE" '%s' "$source"
}

# An env pattern replaces the built-in; a config pattern extends it.
resolve_pattern() {
    local name="$1" key="$2" default="$3" extra
    [[ -n "${!name:-}" ]] && return
    if extra=$(cfg_get "$PROJECT_CFG" ".patterns.$key") || extra=$(cfg_get "$USER_CFG" ".patterns.$key"); then
        printf -v "$name" '%s' "$default${extra:+|$extra}"
    else
        printf -v "$name" '%s' "$default"
    fi
}

describe_source() {
    case "$1" in
        project) echo "project config: $PROJECT_CFG" ;;
        user) echo "user config: $USER_CFG" ;;
        *) echo "$1" ;;
    esac
}

validate_settings() {
    local number_re='^([0-9]+(\.[0-9]*)?|\.[0-9]+)$'
    local integer_re='^[1-9][0-9]*$'
    local var source
    for var in $WEIGHT_VARS; do
        [[ "${!var}" =~ $number_re ]] && continue
        source="${var}_SOURCE"
        die "$var must be a non-negative number, got '${!var}' ($(describe_source "${!source}"))"
    done
    for var in $GOAL_VARS; do
        [[ "${!var}" =~ $integer_re ]] && continue
        source="${var}_SOURCE"
        die "$var must be a positive integer, got '${!var}' ($(describe_source "${!source}"))"
    done
    if (( SKIP_THRESHOLD > TARGET_LINES_PER_SPLIT || TARGET_LINES_PER_SPLIT > HARD_CAP )); then
        die "split goals must satisfy skip_threshold ($SKIP_THRESHOLD) <= target_lines_per_split ($TARGET_LINES_PER_SPLIT) <= hard_cap ($HARD_CAP)"
    fi
}

load_settings() {
    load_config

    resolve TARGET_LINES_PER_SPLIT .target_lines_per_split 300
    resolve HARD_CAP .hard_cap 600
    resolve SKIP_THRESHOLD .skip_threshold 200

    resolve TEST_WEIGHT .weights.test 0.5
    resolve FIXTURE_WEIGHT .weights.fixture 0.1
    resolve RISKY_WEIGHT .weights.risky 1.5
    resolve PROSE_WEIGHT .weights.prose 0.5
    resolve COMMENT_WEIGHT .weights.comment 0.25
    resolve IMPORT_WEIGHT .weights.import 0.25
    resolve MOVED_WEIGHT .weights.moved 0.1
    resolve DELETION_WEIGHT .weights.deletion 0.5

    resolve_pattern EXCLUDE_PATTERNS exclude "$DEFAULT_EXCLUDE_PATTERNS"
    resolve_pattern FIXTURE_PATTERNS fixture "$DEFAULT_FIXTURE_PATTERNS"
    resolve_pattern RISKY_PATTERNS risky "$DEFAULT_RISKY_PATTERNS"
    resolve_pattern PROSE_PATTERNS prose "$DEFAULT_PROSE_PATTERNS"

    validate_settings

    export TEST_WEIGHT FIXTURE_WEIGHT RISKY_WEIGHT PROSE_WEIGHT COMMENT_WEIGHT IMPORT_WEIGHT MOVED_WEIGHT DELETION_WEIGHT
    export EXCLUDE_PATTERNS FIXTURE_PATTERNS RISKY_PATTERNS PROSE_PATTERNS
}

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

merge_base_of() {
    local target_branch="$1"
    git merge-base "$target_branch" HEAD 2>/dev/null || echo "$target_branch"
}

# Detect binary files
detect_binary_files() {
    local target_branch="$1"
    git -c core.quotePath=false diff --numstat "$(merge_base_of "$target_branch")"...HEAD 2>/dev/null |
        awk -F'\t' '$1 == "-" && $2 == "-" { print $3 }' || true
}

# Zero-context, unfused hunks with fixed a/ b/ prefixes, so user diff config can't change what weigh.awk parses.
# awk runs in the C locale because a non-UTF-8 source line makes a UTF-8 awk abort.
weigh_diff() {
    local target_branch="$1"
    git -c core.quotePath=false diff -U0 --inter-hunk-context=0 -M --no-color --no-ext-diff --no-textconv \
        --src-prefix=a/ --dst-prefix=b/ "$(merge_base_of "$target_branch")"...HEAD \
        | LC_ALL=C awk -f "$SCRIPT_DIR/weigh.awk"
}

# Main execution
main() {
    load_settings

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

    local weighed
    weighed=$(weigh_diff "$target_branch")

    local excluded_count excluded_lines
    excluded_count=$(echo "$weighed" | jq '.excluded_files | length')
    excluded_lines=$(echo "$weighed" | jq '.total_excluded_lines')
    if (( excluded_count > 0 )); then
        warnings+=("excluded ${excluded_count} generated/lockfile/vendored files from review-weighted budget (${excluded_lines} lines)")
    fi

    local header
    header=$(cat <<EOF
{
  "current_branch": $(echo -n "$current_branch" | jq -Rs .),
  "target_branch": $(echo -n "$target_branch" | jq -Rs .),
  "target_lines_per_split": $TARGET_LINES_PER_SPLIT,
  "hard_cap": $HARD_CAP,
  "skip_threshold": $SKIP_THRESHOLD,
  "goal_sources": {"target_lines_per_split": "$TARGET_LINES_PER_SPLIT_SOURCE", "hard_cap": "$HARD_CAP_SOURCE", "skip_threshold": "$SKIP_THRESHOLD_SOURCE"},
  "config_files": $(printf '%s\n' "${CONFIG_FILES[@]:-}" | jq -Rs 'split("\n") | map(select(length > 0))'),
  "warnings": $(printf '%s\n' "${warnings[@]:-}" | jq -Rs 'split("\n") | map(select(length > 0))'),
  "binary_files": $(printf '%s\n' "${binary_files[@]:-}" | jq -Rs 'split("\n") | map(select(length > 0))')
}
EOF
)

    printf '%s\n%s\n' "$header" "$weighed" | jq -s 'add'
}

# Run main with all arguments
main "$@"
