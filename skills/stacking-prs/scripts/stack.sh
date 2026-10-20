#!/usr/bin/env bash
#
# stacking-prs/stack.sh
# Read-only stack detection: prints one JSON document describing the PR/MR stack around a branch.
#
# Usage: ./stack.sh [--branch <name>] [--trunk <name>] [--remote <name>]
#        ./stack.sh --check-ci <base-branch>...
# Output: detection JSON, or {"schema":1,"skipped":[...]} for --check-ci
#
# Never writes: no fetch, checkout, branch, push, or forge mutation. Only `gh`/`glab` read calls.
# A forge failure degrades to local (ancestry) mode with a forge_unavailable warning.
#
# `current_branch` is the branch the walk is anchored on: --branch, else the checked-out branch.
# GitLab calls use glab's `:id` placeholder (listed by `glab api --help`), which glab fills from
# the current repo.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for stderr messages (not captured in JSON output)
RED='\033[0;31m'
NC='\033[0m' # No Color

die() {
    echo >&2 -e "${RED}Error: $*${NC}"
    exit 1
}

usage() {
    cat >&2 <<'USAGE'
Usage: stack.sh [--branch <name>] [--trunk <name>] [--remote <name>]
       stack.sh --check-ci <base-branch>...
Environment: STACK_FORGE=github|ghes|gitlab|none overrides forge detection.
USAGE
}

BRANCH=""
TRUNK=""
REMOTE="origin"
CHECK_CI=0
CI_BASES=()

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --branch | --trunk | --remote)
                [[ $# -ge 2 && -n "$2" ]] || { usage; die "$1 needs a value"; }
                case "$1" in
                    --branch) BRANCH="$2" ;;
                    --trunk) TRUNK="$2" ;;
                    --remote) REMOTE="$2" ;;
                esac
                shift 2
                ;;
            --check-ci)
                CHECK_CI=1
                shift
                ;;
            -h | --help)
                usage
                exit 0
                ;;
            -*)
                usage
                die "unknown option: $1"
                ;;
            *)
                [[ $CHECK_CI -eq 1 ]] || { usage; die "unexpected argument: $1"; }
                CI_BASES+=("$1")
                shift
                ;;
        esac
    done
    if [[ $CHECK_CI -eq 1 && ${#CI_BASES[@]} -eq 0 ]]; then
        usage
        die "--check-ci needs at least one base branch"
    fi
}

# ---- preconditions ---------------------------------------------------------

command -v jq >/dev/null 2>&1 || die "jq is required but not installed"

TMP=$(mktemp -d "${TMPDIR:-/tmp}/stack.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

: >"$TMP/notes"
note() { printf '%s\n' "$*" >>"$TMP/notes"; }

ref_exists() { git show-ref --verify --quiet "$1"; }

# Same fallback order as split-branch's analyze.sh detect_target_branch, with a configurable remote.
detect_trunk() {
    local target="$1"
    if [[ -n "$target" ]]; then
        echo "$target"
        return
    fi
    if git symbolic-ref "refs/remotes/$REMOTE/HEAD" &>/dev/null; then
        git symbolic-ref "refs/remotes/$REMOTE/HEAD" | sed "s@^refs/remotes/$REMOTE/@@"
        return
    fi
    if ref_exists refs/heads/main; then
        echo "main"
    elif ref_exists refs/heads/master; then
        echo "master"
    else
        die "Could not detect target branch"
    fi
}

# tip_ref <branch>: the ref to read a branch's commits from, local first
tip_ref() {
    if ref_exists "refs/heads/$1"; then
        echo "refs/heads/$1"
    elif ref_exists "refs/remotes/$REMOTE/$1"; then
        echo "refs/remotes/$REMOTE/$1"
    fi
}

branch_exists() { [[ -n "$(tip_ref "$1")" ]]; }

# ---- CI filter scan --------------------------------------------------------

# Line-oriented heuristic, not a YAML parser. For each pull_request / pull_request_target trigger it
# prints "G" then one "B<TAB>pattern" (branches) or "I<TAB>pattern" (branches-ignore) per entry, or
# "U" when the trigger is written in a shape it cannot read, which means no verdict.
CI_AWK=$(
    cat <<'AWK'
function ind(s) { match(s, /^ */); return RLENGTH }
function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
function unq(s,   q) {
    q = substr(s, 1, 1)
    if ((q == "\"" || q == "\047") && length(s) >= 2 && substr(s, length(s), 1) == q) s = substr(s, 2, length(s) - 2)
    return s
}
function add(kind, p) {
    p = unq(trim(p))
    if (p == "" || p ~ /^!/ || p ~ /[][{}]/ || p ~ /:[ \t]/) { bad = 1; return }
    n++; k[n] = kind; v[n] = p; cnt++
}
function endlist() { if (inlist && cnt == 0) bad = 1; inlist = 0 }
function flush(   i) {
    endlist()
    if (ingrp) {
        if (bad) print "U"
        else { print "G"; for (i = 1; i <= n; i++) print k[i] "\t" v[i] }
    }
    ingrp = 0; n = 0; bad = 0
}
{
    line = $0; sub(/\r$/, "", line)
    t = trim(line)
    if (t == "" || t ~ /^#/) next
    body = trim(t); sub(/[ \t]#.*$/, "", body); body = trim(body)
    d = ind(line)
    if (inlist) {
        if (body ~ /^-([ \t]|$)/ && d >= kind_ind) { add(kk, substr(body, 2)); next }
        endlist()
    }
    if (ingrp && d <= tind) flush()
    if (ingrp) {
        if (cind == 0) cind = d
        if (d == cind && body ~ /^branches(-ignore)?[ \t]*:/) {
            key = body; sub(/[ \t]*:.*$/, "", key)
            rest = trim(substr(body, index(body, ":") + 1))
            kk = (key == "branches") ? "B" : "I"
            if (rest == "") { inlist = 1; kind_ind = d; cnt = 0 }
            else if (substr(rest, 1, 1) == "[") {
                if (substr(rest, length(rest), 1) != "]") bad = 1
                else {
                    inner = substr(rest, 2, length(rest) - 2)
                    if (trim(inner) == "") bad = 1
                    m = split(inner, parts, ",")
                    for (j = 1; j <= m; j++) add(kk, parts[j])
                }
            } else bad = 1
        }
        next
    }
    if (body ~ /^(pull_request|pull_request_target)[ \t]*:/) {
        ingrp = 1; tind = d; cind = 0; n = 0; bad = 0
        if (trim(substr(body, index(body, ":") + 1)) != "") bad = 1
    }
}
END { flush() }
AWK
)

# scan_skips <scan-output> <base>: succeeds when every pull_request trigger in the file skips <base>
scan_skips() {
    local scan="$1" base="$2" line pat ing=0 groups=0 has_b=0 has_i=0 m_b=0 m_i=0 unread=0 all_skip=1

    close_group() {
        local skipped=0
        groups=$((groups + 1))
        if [[ $has_b -eq 1 && $has_i -eq 1 ]]; then
            unread=1
        elif [[ $has_b -eq 1 && $m_b -eq 0 ]]; then
            skipped=1
        elif [[ $has_i -eq 1 && $m_i -eq 1 ]]; then
            skipped=1
        fi
        [[ $skipped -eq 1 ]] || all_skip=0
        has_b=0 has_i=0 m_b=0 m_i=0
    }

    while IFS= read -r line; do
        case "$line" in
            U) return 1 ;;
            G)
                [[ $ing -eq 0 ]] || close_group
                ing=1
                ;;
            B$'\t'*)
                pat="${line#*$'\t'}"
                has_b=1
                # shellcheck disable=SC2254
                case "$base" in $pat) m_b=1 ;; esac
                ;;
            I$'\t'*)
                pat="${line#*$'\t'}"
                has_i=1
                # shellcheck disable=SC2254
                case "$base" in $pat) m_i=1 ;; esac
                ;;
        esac
    done <<<"$scan"
    [[ $ing -eq 0 ]] || close_group
    [[ $unread -eq 0 && $groups -gt 0 && $all_skip -eq 1 ]]
}

# scan_ci <base>...: writes "base<TAB>workflow-path" to $TMP/ci_hits for each workflow that skips it
scan_ci() {
    local root file scan base
    : >"$TMP/ci_hits"
    [[ $# -gt 0 ]] || return 0
    root=$(git rev-parse --show-toplevel)
    for file in "$root"/.github/workflows/*.yml "$root"/.github/workflows/*.yaml; do
        [[ -f "$file" ]] || continue
        scan=$(awk "$CI_AWK" "$file")
        for base in "$@"; do
            if scan_skips "$scan" "$base"; then
                printf '%s\t.github/workflows/%s\n' "$base" "$(basename "$file")" >>"$TMP/ci_hits"
            fi
        done
    done
}

run_check_ci() {
    local bases_json
    scan_ci "${CI_BASES[@]}"
    bases_json=$(printf '%s\n' "${CI_BASES[@]}" | jq -R . | jq -s .)
    jq -n --argjson bases "$bases_json" --rawfile hits "$TMP/ci_hits" '
        ($hits | split("\n") | map(select(length > 0) | split("\t") | {base: .[0], file: .[1]})) as $h
        | {schema: 1,
           skipped: ($bases
                     | reduce .[] as $b ([]; if index($b) == null then . + [$b] else . end)
                     | map(. as $b | {base: $b, files: ([$h[] | select(.base == $b) | .file] | unique)})
                     | map(select(.files | length > 0)))}'
}

# ---- forge resolution ------------------------------------------------------

FORGE="none"

resolve_forge() {
    local url auth host
    if [[ -n "${STACK_FORGE:-}" ]]; then
        case "$STACK_FORGE" in
            github | ghes | gitlab | none) FORGE="$STACK_FORGE" ;;
            *) die "STACK_FORGE must be one of github|ghes|gitlab|none (got '$STACK_FORGE')" ;;
        esac
        return
    fi
    url=$(git remote get-url "$REMOTE" 2>/dev/null || true)
    auth="${url#*://}"
    auth="${auth%%/*}"
    auth="${auth#*@}"
    host=$(printf '%s' "${auth%%:*}" | tr '[:upper:]' '[:lower:]')
    case "$host" in
        github.com) FORGE="github" ;;
        *gitlab*) FORGE="gitlab" ;;
        *) FORGE="none" ;;
    esac
}

# GitHub rollup entries are CheckRuns (status/conclusion) or StatusContexts (state).
GH_NORMALIZE='
def isin($l): . as $x | ($l | index($x)) != null;
def up: (. // "") | ascii_upcase;
def ci_of:
    (.statusCheckRollup // []) as $r
    | if ($r | length) == 0 then "none"
      elif any($r[]; (.conclusion | up | isin(["FAILURE","ERROR","CANCELLED","TIMED_OUT","ACTION_REQUIRED"]))
                     or (.state | up | isin(["FAILURE","ERROR","CANCELLED","TIMED_OUT","ACTION_REQUIRED"]))) then "fail"
      elif any($r[]; (.conclusion | up | isin(["PENDING","QUEUED","IN_PROGRESS","EXPECTED"]))
                     or (.state | up | isin(["PENDING","QUEUED","IN_PROGRESS","EXPECTED"]))
                     or (.status | up | isin(["PENDING","QUEUED","IN_PROGRESS","WAITING"]))
                     or ((.conclusion | up) == "" and (.state | up) == "")) then "pending"
      else "pass" end;
def review_of:
    (.reviewDecision | up) as $d
    | if $d == "APPROVED" then "approved"
      elif $d == "CHANGES_REQUESTED" then "changes_requested"
      elif $d == "REVIEW_REQUIRED" then "review_required"
      else "none" end;
'

# Each fetcher writes normalized $TMP/open.json and $TMP/merged.json, or notes why it cannot.
fetch_github() {
    command -v gh >/dev/null 2>&1 || { note "gh is not installed"; return 1; }
    gh pr list --state open --limit 200 --json \
        number,url,headRefName,baseRefName,isDraft,state,reviewDecision,statusCheckRollup,headRefOid,isCrossRepository,author \
        >"$TMP/raw_open.json" 2>/dev/null || { note "gh pr list (open) failed"; return 1; }
    gh pr list --state merged --limit 100 --json \
        number,headRefName,baseRefName,headRefOid,mergeCommit,mergedAt \
        >"$TMP/raw_merged.json" 2>/dev/null || { note "gh pr list (merged) failed"; return 1; }
    jq "$GH_NORMALIZE"'
        map({number, url, head: .headRefName, base: .baseRefName, draft: (.isDraft // false),
             sha: .headRefOid, author: (.author.login // null), cross: (.isCrossRepository // false),
             ci: ci_of, review: review_of, merge_sha: null})' "$TMP/raw_open.json" >"$TMP/open.json" 2>/dev/null ||
        { note "gh pr list (open) returned unreadable output"; return 1; }
    jq 'map({number, head: .headRefName, base: .baseRefName, sha: .headRefOid,
             merge_sha: (.mergeCommit.oid // null)})' "$TMP/raw_merged.json" >"$TMP/merged.json" 2>/dev/null ||
        { note "gh pr list (merged) returned unreadable output"; return 1; }
}

fetch_gitlab() {
    command -v glab >/dev/null 2>&1 || { note "glab is not installed"; return 1; }
    glab mr list -F json --per-page 100 >"$TMP/raw_open.json" 2>/dev/null ||
        { note "glab mr list failed"; return 1; }
    glab mr list -M -F json --per-page 100 >"$TMP/raw_merged.json" 2>/dev/null ||
        { note "glab mr list -M failed"; return 1; }
    jq 'map({number: .iid, url: .web_url, head: .source_branch, base: .target_branch,
             draft: (.draft // .work_in_progress // false), sha: .sha,
             author: (.author.username // null), cross: false, ci: "unknown", review: "unknown",
             merge_sha: null})' "$TMP/raw_open.json" >"$TMP/open.json" 2>/dev/null ||
        { note "glab mr list returned unreadable output"; return 1; }
    jq 'map({number: .iid, head: .source_branch, base: .target_branch, sha: .sha,
             merge_sha: (.merge_commit_sha // .squash_commit_sha // null)})' \
        "$TMP/raw_merged.json" >"$TMP/merged.json" 2>/dev/null ||
        { note "glab mr list -M returned unreadable output"; return 1; }
}

# ---- chain building --------------------------------------------------------

# Walk down from the branch's PR to the bottom, then up while exactly one open PR targets the top.
CHAIN_JQ='
def o: $open | sort_by(.number);
def by_head($h): [o[] | select(.head == $h)] | first;
def by_base($b): [o[] | select(.base == $b)];
def kids($c): by_base($c[-1].head) | map(select(.head as $h | ($c | map(.head) | index($h)) == null));
def down:
    until(. as $c | ($c[0].base == $trunk) or (by_head($c[0].base) == null)
                    or (($c | map(.head) | index($c[0].base)) != null);
          . as $c | [by_head($c[0].base)] + $c);
def up:
    until(. as $c | (kids($c) | length) != 1;
          . as $c | $c + [kids($c)[0]]);
(by_head($branch)) as $start
| if $start == null then {found: false}
  else ([$start] | down | up) as $chain
       | {found: true, chain: $chain,
          fork_heads: (if (kids($chain) | length) > 1 then (kids($chain) | map(.head)) else [] end)}
  end'

PR_CHAIN_FOUND=0

build_pr_chain() {
    jq -n --argjson open "$(cat "$TMP/open.json")" --arg branch "$BRANCH" --arg trunk "$TRUNK" \
        "$CHAIN_JQ" >"$TMP/chain.json"
    [[ "$(jq -r '.found' "$TMP/chain.json")" == "true" ]] && PR_CHAIN_FOUND=1
    return 0
}

# ---- local (ancestry) mode -------------------------------------------------

# parent_of <branch>: the closest strict-ancestor local branch not yet in trunk, else trunk
parent_of() {
    local b="$1" btip mb cand ctip n best="" best_n=-1 ref skip
    btip=$(git rev-parse "$(tip_ref "$b")")
    mb=$(git merge-base "$TRUNK_REF" "$btip" 2>/dev/null || true)
    while IFS= read -r cand; do
        [[ "$cand" != "$b" ]] || continue
        ctip=$(git rev-parse "refs/heads/$cand")
        [[ "$ctip" != "$btip" ]] || continue
        git merge-base --is-ancestor "$ctip" "$btip" 2>/dev/null || continue
        skip=0
        for ref in $TRUNK_ALL_REFS; do
            if git merge-base --is-ancestor "$ctip" "$ref" 2>/dev/null; then skip=1; fi
        done
        [[ $skip -eq 0 ]] || continue
        if [[ -n "$mb" ]]; then
            n=$(git rev-list --count "$mb..$ctip")
        else
            n=$(git rev-list --count "$ctip")
        fi
        if [[ $n -gt $best_n ]]; then
            best="$cand"
            best_n=$n
        fi
    done <"$TMP/eligible"
    echo "${best:-$TRUNK}"
}

build_local_chain() {
    local cur parent guard=0 kids count rows="" head
    git for-each-ref --format='%(refname:short)' refs/heads |
        { grep -v '^backup/' || true; } | { grep -vxF -- "$TRUNK" || true; } >"$TMP/eligible"
    : >"$TMP/parents"
    {
        cat "$TMP/eligible"
        echo "$BRANCH"
    } | sort -u | while IFS= read -r head; do
        [[ "$head" != "$TRUNK" ]] || continue
        [[ -n "$(tip_ref "$head")" ]] || continue
        printf '%s\t%s\n' "$head" "$(parent_of "$head")" >>"$TMP/parents"
    done

    : >"$TMP/local_rows"
    FORK_HEADS="[]"
    if [[ "$BRANCH" != "$TRUNK" ]]; then
        cur="$BRANCH"
        printf '%s\n' "$cur" >"$TMP/local_names"
        while [[ $guard -lt 200 ]]; do
            guard=$((guard + 1))
            parent=$(awk -F'\t' -v b="$cur" '$1 == b { print $2; exit }' "$TMP/parents")
            [[ -n "$parent" && "$parent" != "$TRUNK" ]] || break
            grep -qxF -- "$parent" "$TMP/local_names" && break
            printf '%s\n' "$parent" | cat - "$TMP/local_names" >"$TMP/local_names.new"
            mv "$TMP/local_names.new" "$TMP/local_names"
            cur="$parent"
        done
        cur="$BRANCH"
        guard=0
        while [[ $guard -lt 200 ]]; do
            guard=$((guard + 1))
            kids=$(awk -F'\t' -v p="$cur" '$2 == p { print $1 }' "$TMP/parents" | { grep -vxF -f "$TMP/local_names" || true; })
            count=$(printf '%s' "$kids" | grep -c . || true)
            if [[ "$count" -eq 1 ]]; then
                printf '%s\n' "$kids" >>"$TMP/local_names"
                cur="$kids"
            else
                if [[ "$count" -gt 1 ]]; then
                    FORK_HEADS=$(printf '%s\n' "$kids" | jq -R . | jq -s .)
                fi
                break
            fi
        done
        while IFS= read -r head; do
            printf '%s\t%s\t%s\n' "$head" "$(awk -F'\t' -v b="$head" '$1 == b { print $2; exit }' "$TMP/parents")" \
                "$(git rev-parse "$(tip_ref "$head")")" >>"$TMP/local_rows"
        done <"$TMP/local_names"
    fi
    jq -R -s --argjson fork "$FORK_HEADS" '
        {found: true,
         chain: (split("\n") | map(select(length > 0) | split("\t")
                 | {number: null, url: null, head: .[0], base: .[1], draft: false, sha: .[2],
                    author: null, cross: false, ci: "unknown", review: "unknown", local: true})),
         fork_heads: $fork}' "$TMP/local_rows" >"$TMP/chain.json"
}

# ---- per-layer enrichment --------------------------------------------------

gitlab_enrich_layers() {
    local iid status approved ci review pipeline
    while IFS= read -r iid; do
        ci="unknown"
        review="unknown"
        if pipeline=$(glab mr view "$iid" -F json 2>/dev/null) && printf '%s' "$pipeline" | jq -e . >/dev/null 2>&1; then
            status=$(printf '%s' "$pipeline" | jq -r '.head_pipeline.status // empty')
            case "$status" in
                "") ci="none" ;;
                success) ci="pass" ;;
                failed | canceled) ci="fail" ;;
                running | pending | created | preparing | waiting_for_resource | scheduled) ci="pending" ;;
                *) ci="unknown" ;;
            esac
        else
            note "glab mr view $iid failed"
        fi
        if approved=$(glab api "projects/:id/merge_requests/$iid/approvals" 2>/dev/null) &&
            printf '%s' "$approved" | jq -e . >/dev/null 2>&1; then
            if [[ "$(printf '%s' "$approved" | jq -r '.approved // false')" == "true" ]]; then
                review="approved"
            else
                review="review_required"
            fi
        else
            note "glab api approvals for $iid failed"
        fi
        jq --argjson iid "$iid" --arg ci "$ci" --arg review "$review" \
            '.chain |= map(if .number == $iid then .ci = $ci | .review = $review else . end)' \
            "$TMP/chain.json" >"$TMP/chain.new" && mv "$TMP/chain.new" "$TMP/chain.json"
    done < <(jq -r '.chain[].number' "$TMP/chain.json")
}

# native_stack_number: prints the stack number (or "null") when the bottom PR belongs to a native stack
detect_native() {
    local bottom response
    bottom=$(jq -r '.chain[0].number // empty' "$TMP/chain.json")
    [[ -n "$bottom" ]] || return 0
    if ! response=$(gh api "repos/{owner}/{repo}/pulls/$bottom" --jq '.stack // empty' 2>/dev/null); then
        note "gh api pulls/$bottom failed"
        return 0
    fi
    if printf '%s' "$response" | jq -e 'type == "object" and length > 0' >/dev/null 2>&1; then
        MODE="native"
        STACK_NUMBER=$(printf '%s' "$response" | jq -c '.number // .id // null')
    fi
}

# worktrees_other: "branch<TAB>path" for branches checked out in a worktree other than this one
worktrees_other() {
    local here
    here=$(git rev-parse --show-toplevel)
    git worktree list --porcelain 2>/dev/null | awk -v here="$here" '
        /^worktree / { path = substr($0, 10) }
        /^branch refs\/heads\// { if (path != here) print substr($0, 19) "\t" path }'
}

# layer_enrichment: "branch<TAB>behind<TAB>worktree" per layer
layer_enrichment() {
    local head base sha ref parent_ref behind wt
    worktrees_other >"$TMP/worktrees"
    : >"$TMP/enrich"
    while IFS=$'\t' read -r head base sha; do
        ref=$(tip_ref "$head")
        if [[ -z "$ref" && -n "$sha" ]] && git cat-file -e "$sha^{commit}" 2>/dev/null; then
            ref="$sha"
        fi
        parent_ref=""
        if ref_exists "refs/remotes/$REMOTE/$base"; then
            parent_ref="refs/remotes/$REMOTE/$base"
        elif ref_exists "refs/heads/$base"; then
            parent_ref="refs/heads/$base"
        fi
        behind=""
        if [[ -n "$ref" && -n "$parent_ref" ]]; then
            behind=$(git rev-list --count "$ref..$parent_ref" 2>/dev/null || true)
        fi
        wt=$(awk -F'\t' -v b="$head" '$1 == b { print $2; exit }' "$TMP/worktrees")
        printf '%s\t%s\t%s\n' "$head" "$behind" "$wt" >>"$TMP/enrich"
    done < <(jq -r '.chain[] | [.head, .base, .sha] | @tsv' "$TMP/chain.json")
}

# ---- main ------------------------------------------------------------------

parse_args "$@"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git work tree"

if [[ $CHECK_CI -eq 1 ]]; then
    run_check_ci
    exit 0
fi

if [[ -z "$BRANCH" ]]; then
    BRANCH=$(git symbolic-ref -q --short HEAD 2>/dev/null) || die "HEAD is detached; check out a branch or pass --branch"
fi

TRUNK=$(detect_trunk "$TRUNK")
if ref_exists "refs/remotes/$REMOTE/$TRUNK"; then
    TRUNK_REF="refs/remotes/$REMOTE/$TRUNK"
elif ref_exists "refs/heads/$TRUNK"; then
    TRUNK_REF="refs/heads/$TRUNK"
else
    die "trunk branch '$TRUNK' not found"
fi
TRUNK_ALL_REFS=""
for _ref in "refs/heads/$TRUNK" "refs/remotes/$REMOTE/$TRUNK"; do
    if ref_exists "$_ref"; then TRUNK_ALL_REFS="$TRUNK_ALL_REFS $_ref"; fi
done
branch_exists "$BRANCH" || die "branch '$BRANCH' not found"

resolve_forge

MODE="local"
STACK_NUMBER="null"
FORK_HEADS="[]"
echo '[]' >"$TMP/merged.json"
echo '[]' >"$TMP/open.json"

FORGE_OK=0
case "$FORGE" in
    github | ghes) fetch_github && FORGE_OK=1 ;;
    gitlab) fetch_gitlab && FORGE_OK=1 ;;
esac

if [[ $FORGE_OK -eq 1 ]]; then
    build_pr_chain
fi

if [[ $PR_CHAIN_FOUND -eq 1 ]]; then
    MODE="classic"
    [[ "$FORGE" != "gitlab" ]] || gitlab_enrich_layers
    [[ "$FORGE" != "github" ]] || detect_native
else
    build_local_chain
fi

GH_STACK_INSTALLED=false
if command -v gh >/dev/null 2>&1 && gh stack --help >/dev/null 2>&1; then
    GH_STACK_INSTALLED=true
fi

BOTTOM_BASE_EXISTS=true
if [[ $PR_CHAIN_FOUND -eq 1 ]]; then
    _bottom_base=$(jq -r '.chain[0].base' "$TMP/chain.json")
    if [[ "$_bottom_base" != "$TRUNK" ]] && ! branch_exists "$_bottom_base"; then
        BOTTOM_BASE_EXISTS=false
    fi
fi

layer_enrichment

# ci_filter applies to classic/local stacks on GitHub, where non-trunk bases may be filtered out
CIF='{"branches":[],"files":[]}'
if [[ "$MODE" != "native" && ( "$FORGE" == "github" || "$FORGE" == "ghes" ) ]]; then
    # shellcheck disable=SC2046
    set -- $(jq -r --arg trunk "$TRUNK" '[.chain[].base | select(. != $trunk)] | unique | .[]' "$TMP/chain.json")
    scan_ci "$@"
    CIF=$(jq -n --slurpfile chain "$TMP/chain.json" --rawfile hits "$TMP/ci_hits" '
        ($hits | split("\n") | map(select(length > 0) | split("\t") | {base: .[0], file: .[1]})) as $h
        | ($h | map(.base)) as $skipped
        | {branches: [$chain[0].chain[] | select(.base as $b | $skipped | index($b) != null) | .head],
           files: ($h | map(.file) | unique)}')
fi

jq -n \
    --slurpfile chainfile "$TMP/chain.json" \
    --slurpfile merged "$TMP/merged.json" \
    --rawfile enrich "$TMP/enrich" \
    --rawfile notes "$TMP/notes" \
    --argjson cif "$CIF" \
    --argjson stack_number "$STACK_NUMBER" \
    --argjson gh_stack_installed "$GH_STACK_INSTALLED" \
    --argjson base_exists "$BOTTOM_BASE_EXISTS" \
    --arg forge "$FORGE" --arg mode "$MODE" --arg trunk "$TRUNK" --arg remote "$REMOTE" \
    --arg current "$BRANCH" '
    $chainfile[0] as $cf
    | $cf.chain as $chain
    | $merged[0] as $merged
    | ($enrich | split("\n") | map(select(length > 0) | split("\t")
        | {b: .[0], behind: (if .[1] == "" then null else (.[1] | tonumber) end),
           wt: (if .[2] == "" then null else .[2] end)})) as $e
    | ($chain | to_entries | map(.value as $p
        | ($e | map(select(.b == $p.head)) | first) as $x
        | {position: (.key + 1), branch: $p.head, base: $p.base, number: $p.number, url: $p.url,
           state: (if $p.local then "local" elif $p.draft then "draft" else "open" end),
           head_sha: $p.sha, ci: $p.ci, review: $p.review, behind_parent: $x.behind,
           worktree: $x.wt, is_current: ($p.head == $current), author: $p.author})) as $layers
    | ($layers | length) as $n
    | ($layers | map(select(.state != "local")) | length) as $open_n
    | ($chain | map(select(.cross) | .head)) as $cross
    | (if $n > 0 and $mode != "local" then
         ($merged | map(select(.head == $layers[0].base)) | sort_by(.number) | last)
       else null end) as $mp
    | ($notes | split("\n") | map(select(length > 0)) | unique | join("; ")) as $unavailable
    | {
        schema: 1,
        forge: $forge,
        mode: $mode,
        in_stack: ($n >= 2),
        trunk: $trunk,
        remote: $remote,
        current_branch: $current,
        gh_stack_installed: $gh_stack_installed,
        native_available: ($forge == "github" and ($cross | length) == 0 and $gh_stack_installed),
        stack_number: $stack_number,
        layers: $layers,
        merged_parents: (if $mp == null then []
                         else [{branch: $mp.head, number: $mp.number, head_sha: $mp.sha,
                                merge_sha: $mp.merge_sha, child: $layers[0].branch}] end),
        warnings: ([
            (if ($unavailable | length) > 0
             then {code: "forge_unavailable", message: ("forge data unavailable: " + $unavailable)}
             else empty end),
            (if $n > 0 and $mode != "local" and ($mp != null or ($base_exists | not))
             then {code: "broken_chain",
                   message: ("the base of " + $layers[0].branch + " (" + $layers[0].base
                             + ") is "
                             + (if $mp != null then "the head of a merged PR/MR" else "not trunk or an existing branch" end)),
                   branches: [$layers[0].branch]}
             else empty end),
            (if ($cf.fork_heads | length) > 1
             then {code: "branched_stack",
                   message: "more than one open PR/MR targets the same base; the walk stopped at the fork",
                   branches: $cf.fork_heads}
             else empty end),
            (if $n > 4
             then {code: "deep_stack", message: ("the stack has " + ($n | tostring) + " layers; 3-4 is the practical limit")}
             else empty end),
            (if $forge == "gitlab" and $open_n > 4
             then {code: "gitlab_retarget_cap", message: "GitLab retargets at most 4 open MRs when their target merges"}
             else empty end),
            (if $forge == "gitlab" and ([$layers[].author | select(. != null)] | unique | length) > 1
             then {code: "gitlab_mixed_authors", message: "GitLab stack view stops at the first MR with a different author"}
             else empty end),
            (if ($cross | length) > 0
             then {code: "cross_fork", message: "a layer comes from a fork; native stacks need same-repo branches", branches: $cross}
             else empty end),
            (if ($cif.branches | length) > 0
             then {code: "ci_filter", message: "a workflow filters pull_request by base branch and will skip these layers",
                   branches: $cif.branches, files: $cif.files}
             else empty end),
            (if ($layers | map(select(.worktree != null)) | length) > 0
             then {code: "layer_in_other_worktree", message: "a layer is checked out in another worktree",
                   branches: [$layers[] | select(.worktree != null) | .branch]}
             else empty end)
        ])
      }'
