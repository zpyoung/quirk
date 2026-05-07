---
name: split-branch
description: Use when a feature branch exceeds ~400 lines of diff, when a reviewer asks to "make this PR smaller", when planning a large feature so it ships in reviewable chunks, or when the user invokes /split-branch
---

# Splitting Branches Into Stacked PRs/MRs

## Overview

Split a large branch into a stack of smaller PRs/MRs where each (except the bottom) targets the previous one — true stacked PRs, not "expanding-snapshot" PRs that all target `main`.

**Core principle:** 200-400 line PRs correlate with the highest defect-detection rates and best architectural feedback; beyond ~400 lines feedback degrades to surface-level. Use as a heuristic, not a law — split aggressively, target ~300 lines, adjust per language.

**Announce:** "I'm using the split-branch skill to plan/execute the split."

## Targets and Weighting

| Change | Target |
|---|---|
| Bug fix / config | <100 / <50 |
| New feature | 200-400 |
| Refactor | 300-500 |
| **Default** | **~300 source lines** |
| Hard cap | 600 source lines |

**LOC** = `added + deleted` for files classified as source. `analyze.sh` excludes lockfiles, generated code (`__generated__`, `_pb.go`, `_pb2.py`, `.min.*`), and vendored dirs (`node_modules`, `vendor`, `dist`, `build`); override via `EXCLUDE_PATTERNS`.

**Test weighting:** reviewers skim tests, so they count at **~0.5×** weight. `analyze.sh` emits `weighted_review_lines = source + (tests / 2)`. Don't split tests away from their source to hit a raw line count.

Sources (correlational): SmartBear/Cisco (2,500 reviews), LinearB 2025 (6.1M PRs, elite teams <219 LOC/PR). Graphite reports 50-line PRs merge ~40% faster than 250-line ones.

**Skip the split** if `weighted_review_lines < 200` — confirm with the user before proceeding anyway.

## Strategies (in order)

### 0. Self-containment (overrides target, yields to hard cap)
A definition should ship with at least one usage so reviewers can evaluate the API in context.

**Usage hierarchy:**
1. Real production caller — ideal.
2. Contract / integration test — acceptable when (a) the real caller is in a later layer, (b) including it would exceed 600 lines, or (c) the layer *is* a public API where tests are the contract.
3. Unit test only — last resort; can pass on broken APIs.

Concretely: new function → real caller; new type → construction site; new module → import wiring; new endpoint → client (or contract test if client is downstream); rename → all call sites in same PR. **Monorepo rename exception:** when N call sites is unmanageable, ship a compatibility shim and phase the migration over follow-up PRs.

Prefer 450-line self-contained over 280 + 170 split. Past the 600 cap → split, but flag the dangling definition in "Intentionally Missing" and link forward.

**Layer-boundary exception:** when splitting by architectural layer (Strategy 2), it's legitimate for a PR's only "callers" to be tests — the real caller lives in the next layer up. Acknowledge in the PR description.

### 1. Extract pure refactors first
Renames, file moves, interface extractions go in PR #1. Often 20-30% of the diff with near-zero defect risk → fast approval, clarifies the actual feature change.

### 2. Split by architectural layer (most common)
Bottom-up: schema → repository → service → API → frontend. Bundle tests with their layer (tests count at 0.5×, so a layer + its tests usually fits comfortably).

### 3. Split by vertical slice (when possible)
Independently-shippable sub-units that touch all layers. Hardest to achieve, highest review quality — avoids invoking the layer-boundary exception.

### 4. Feature flags for mid-stack merges
Gate incomplete features so each PR is independently mergeable while staying dark.

## Why Stacked, Not "Progressive" PRs

Progressive PRs (each targeting `main`, growing to the full diff) seem flexible but break under merges:

| | Stacked | Progressive |
|---|---|---|
| Clean incremental diff | ✅ Always | ❌ Lost after any mid-chain merge |
| CI overhead per PR | Medium | High (each is full feature) |
| Merge race conditions | Low | High |
| Partial revert safety | ✅ | ❌ |
| Reviewer autonomy | Bottom-up order | Free pick |

If rebase-cascade pain is the concern, prefer **trunk + feature flags** — same autonomy, no snapshot bookkeeping.

## Terminology

- **Stack** — chain of PRs where each (except bottom) targets the previous
- **Bottom** — PR targeting `main`/`master`. Reviewers read **bottom-up**
- **Top** — PR farthest from `main`; where the original feature branch points after splitting
- **`ORIG_BASE`** — branch the feature was originally based on (e.g. `main`)
- **`ORIG_BASE_SHA`** — `git merge-base "$ORIG_BASE" HEAD` *pinned before any split* — used as the rebase boundary
- **`SPLIT_BASE`** — new branch created by `extract.sh` to hold the extracted slice

## The Process

### Step 1: Pre-flight

```bash
git rev-parse --is-inside-work-tree
git status --porcelain   # must be clean

DEFAULT_BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null \
  | sed 's@^refs/remotes/origin/@@' || echo main)

# Existing PR/MR? Its base overrides DEFAULT_BASE.
gh pr view --json number,title,baseRefName,url 2>/dev/null \
  || gh pr list --head "$(git branch --show-current)" \
       --json number,title,baseRefName,url --jq '.[0]' 2>/dev/null
# GitLab equivalent: glab mr view --output json (with --repo for nested namespaces)
```

Set `ORIG_BASE` to the existing PR's base (or `DEFAULT_BASE`). **Stop** if: not in a repo, detached HEAD, on `ORIG_BASE`, or working tree dirty.

**Surface up front** if branch protection on `ORIG_BASE` blocks force-push, requires linear history, or your token can't retarget. The fallback in those cases is to create new branches and new PRs rather than rewriting the existing PR.

### Step 2: Analyze

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/split-branch/scripts/analyze.sh" "$ORIG_BASE"
```

Use the JSON's `weighted_review_lines`, `directory_groups[]`, and `excluded_files[]` to design splits. Override budget with `TARGET_LINES_PER_SPLIT`, exclusions with `EXCLUDE_PATTERNS`.

**Detect non-linear history:**
```bash
git log --merges --oneline "$ORIG_BASE..HEAD"
```
If merge commits exist, `git rebase --onto` linearizes by default. Surface to user; default to **cherry-pick extraction** instead of `--rebase-merges`.

### Step 3: Present the plan (REQUIRED — never skip)

Use AskUserQuestion. Format:

```markdown
**Stack** — bottom (targets `main`) to top (current work)

1. `feature/json-utils-refactor` (~310 weighted) — bottom, extract first
2. `feature/payment-schema` (~340)
3. `feature/payment-service` (~380)
4. `feature/payment-api` (~300)
5. `feature/payment-ui` (~420) ← current branch retargets here (top)

Existing PR #456 → main; will retarget to PR #5.
Branch protections: none / [list]
```

Options: (A) execute, (B) modify groupings, (C) change names, (D) cancel. **Get explicit approval before any git operation.** Execute one split at a time.

### Step 4: Execute one split

Pin variables before extracting — this is what prevents the `--onto` ambiguity footgun:

```bash
ORIG_BASE_SHA=$(git merge-base "$ORIG_BASE" HEAD)
CURRENT="$(git branch --show-current)"
SPLIT_BASE="<new_branch_name>"

"${CLAUDE_PLUGIN_ROOT}/skills/split-branch/scripts/extract.sh" \
  "$SPLIT_BASE" "$ORIG_BASE" <file1> <file2> ...

git rebase --onto "$SPLIT_BASE" "$ORIG_BASE_SHA" "$CURRENT"
git log --oneline "$SPLIT_BASE..$CURRENT"   # verify only non-extracted commits remain
```

`extract.sh` creates `backup/<branch>_<timestamp>` automatically. On conflicts: report files, point to backup, **don't auto-resolve**.

For subsequent splits in the same stack, the previous `SPLIT_BASE` becomes the next `ORIG_BASE`.

### Step 5: PR descriptions (mandatory stack header)

Without this, reviewers flag intentional placeholders as bugs:

```markdown
## Stack Position
[1 (bottom): refactor] → [2: schema] → **[3: service] (this PR)** → [4: API] → [5 (top): UI]

## Feature Goal
Add user payment method management.

## Review Order
Bottom-up. Depends on #1, #2.

## Intentionally Missing
HTTP endpoints in #4, UI in #5 (layer-boundary self-containment exception).
```

### Step 6: Push, create, retarget — in this order

Order matters: a new branch must exist on the remote before any PR can target it.

```bash
# a. Push every new split branch
for b in "${SPLIT_BRANCHES[@]}"; do git push -u origin "$b"; done

# b. Force-push the rebased current branch
git push --force-with-lease origin "$CURRENT"   # never plain --force

# c. Notify reviewers BEFORE retargeting (inline comments may be invalidated)
gh pr comment <existing_pr> --body "Splitting into a stack. Old diff: <commit-permalink>. New base: \`$NEW_TOP\`."

# d. Create draft PRs for the lower stack (#1..#N-1)
gh pr create --base "$ORIG_BASE" --head "$SPLIT_1" --draft ...
gh pr create --base "$SPLIT_1"   --head "$SPLIT_2" --draft ...

# e. Retarget the existing PR onto the new top
gh pr edit <existing_pr> --base "$NEW_TOP"
# GitLab: glab mr update <iid> --target-branch "$NEW_TOP" --repo "$NS/$PROJECT"
#   On failure: print the web URL and ask the user to retarget manually.

# f. Mark only the bottom PR ready
gh pr ready "$BOTTOM_PR_NUM"
```

**Keep all non-bottom PRs in draft** until the full stack is reviewed — prevents premature merges that silently change downstream diffs.

### Step 7: Cleanup & caveats

`extract.sh` accumulates `backup/*` branches (local-only, not pushed). After the stack merges cleanly:
```bash
git branch -D $(git branch --list 'backup/*' --format='%(refname:short)')
```
Don't auto-delete — user may need to recover from a bad rebase.

**Commit history:** rebasing rewrites SHAs. `Co-authored-by:` trailers survive but references break. Re-sign signed commits (`git rebase --signoff`). Review Conventional Commits history before pushing if you use `release-please`/`semantic-release`.

## Quick Reference

| Symptom | Action |
|---|---|
| `weighted_review_lines` >400 / >600 | Split / hard split |
| Mostly tests (200 src + 500 tests = 450 weighted) | Keep together (0.5× weight) |
| Mixed refactor + feature | Refactor as PR #1 |
| Full-stack feature | Layer split; tests satisfy boundary self-containment |
| Vertical slice possible | Prefer it |
| Branch has merge commits | Cherry-pick extraction, not `--rebase-merges` |
| Monorepo rename, N call sites unmanageable | Compatibility shim + phased migration |
| New definition with caller in diff | Pull caller in |
| New definition, caller is later layer | Contract test in same PR; flag in "Intentionally Missing" |
| Branch protections block force-push | New branches/new PRs, don't rewrite existing |
| Reviewer needs full picture | Compare top-of-stack against `main` |
| Existing PR | `gh pr view` first; its base = `ORIG_BASE` |

## Common Mistakes

- **Setting target >400 lines** — past the cognitive-load cliff. Default 300, hard cap 600.
- **Each PR targeting `main` (progressive PRs)** — incremental diff lost after any merge. Use stacked or trunk + flags.
- **No stack header in PRs** — reviewers flag placeholders as bugs.
- **Definitions without usage** — bundle a real caller, or a contract test at a layer boundary, or link forward in "Intentionally Missing".
- **Splitting tests off** — tests are 0.5× weight; almost never needs splitting.
- **Confusing `ORIG_BASE` and `SPLIT_BASE` in rebase** — pin `ORIG_BASE_SHA` *before* extract; verify with `git log --oneline "$SPLIT_BASE..$CURRENT"`.
- **Retargeting without warning reviewers** — comment first, link the old commit SHA.
- **Pushing in the wrong order** — branches must be on the remote *before* PRs can target them.
- **`--force` instead of `--force-with-lease`** — silently overwrites collaborators.
- **Splitting after the fact** — for new features, plan layers up front.

## Red Flags — STOP

- Designing splits without running `analyze.sh`
- Git operations before user approves the plan
- Suggesting a single 2,000-line split as "good enough"
- Defining something without including any caller (when one exists in the diff)

## Bundled Scripts

`${CLAUDE_PLUGIN_ROOT}/skills/split-branch/scripts/`:
- `analyze.sh <target>` — JSON budget breakdown (source/test/excluded, weighted), directory groupings. Bash 3.2+.
- `extract.sh <new> <target> <files>...` — creates timestamped backup, then a new branch from target, populates from feature branch. Handles **modifies, adds, AND deletes**. For renames pass both old and new paths.

## Integration

- `updating-pr` — refresh PR descriptions with stack metadata after each split
- `using-git-worktrees` — stage splits in isolated worktrees
- `finishing-a-development-branch` — once the bottom merges and the stack collapses
