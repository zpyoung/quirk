# Split: cut a branch into stacked PRs/MRs

This is the Split phase of the stacking-prs skill. The router (`../SKILL.md`) has already run `stack.sh`, so its JSON (`forge`, `mode`, `native_available`, `gh_stack_installed`, `warnings`) is the input to the preflight, native registration, and header steps below.

## Overview

Split a large branch into a stack of smaller PRs/MRs where each (except the bottom) targets the previous one — true stacked PRs, not "expanding-snapshot" PRs that all target `main`.

**Core principle:** smaller diffs are easier to review well, but the evidence that size speeds up merging is weak. Google's review guide calls about 100 lines a reasonable change. SmartBear/Cisco's review study recommends keeping a review under 400 lines. Kudrjavets et al. 2022 found PR size doesn't relate to time-to-merge across 845K PRs, so the targets below are a review-load heuristic, not a promise of speed. Split for reviewability, target ~300 weighted lines, and adjust per language.

## Targets and Weighting

| Change | Target |
|---|---|
| Bug fix / config | <100 / <50 |
| New feature | 200-400 |
| Refactor | 300-500 |
| **Default** | **~300 weighted lines** |
| Hard cap | 600 weighted lines |

300, 600, and the 200-line skip threshold are defaults. Step 2 confirms the split goals with the user on every run, and the confirmed values replace these figures wherever this skill cites them.

All targets are in **weighted review lines**: `analyze.sh` charges each changed line what it costs a reviewer to read. **A line costs its file's weight, capped by every discount that applies to the line**, so a comment is 0.25 in source and in tests, but 0.1 in a fixture.

| File kind (first match wins) | Weight | Override (env / config) |
|---|---|---|
| Excluded: lockfiles, generated (`__generated__`, `_pb.go`, `_pb2.py`, `.min.*`), vendored (`node_modules`, `vendor`, `dist`, `build`) | 0 | `EXCLUDE_PATTERNS` / `patterns.exclude` |
| Fixture: `__snapshots__/`, `fixtures/`, `testdata/`, `golden/`, `*.snap` | 0.1 | `FIXTURE_WEIGHT`, `FIXTURE_PATTERNS` / `weights.fixture`, `patterns.fixture` |
| Test | 0.5 | `TEST_WEIGHT` / `weights.test` |
| Risky: migrations, schema, auth/security/crypto paths, CI workflows, Terraform/Helm/k8s, Dockerfile | 1.5 | `RISKY_WEIGHT`, `RISKY_PATTERNS` / `weights.risky`, `patterns.risky` |
| Prose: `.md`, `.rst`, `.txt`, `.adoc` | 0.5 | `PROSE_WEIGHT`, `PROSE_PATTERNS` / `weights.prose`, `patterns.prose` |
| Source | 1.0 | — |

| Line discount | Cap | Override (env / config) |
|---|---|---|
| Blank, or a whitespace-only edit | 0 | — |
| Moved (same text removed elsewhere, ≥20 alphanumeric chars) | 0.1 | `MOVED_WEIGHT` / `weights.moved` |
| Comment or docstring | 0.25 | `COMMENT_WEIGHT` / `weights.comment` |
| Import / include | 0.25 | `IMPORT_WEIGHT` / `weights.import` |
| Deleted line | 0.5 | `DELETION_WEIGHT` / `weights.deletion` |

Re-indents are whitespace-only except in indentation-significant files (Python, YAML, Makefile), where they count in full. A changed line inside a block comment whose opener sits outside the hunk counts as code, which overstates the budget rather than understating it. In repos where Markdown is the product (a skills repo, a docs site), set `"weights": {"prose": 1}` in the project config.

These weights make the same branch read smaller than a raw line count, so the targets are looser on churny diffs (comments, moves, re-indents) and tighter on risky ones. Don't split tests away from their source to hit a number.

**Configuration.** `analyze.sh` reads `~/.quirk/stacking-prs.json` (user), then `<repo>/.quirk/stacking-prs.json` (project). Each setting resolves on its own, highest first: env var, project config, user config, built-in default. A file only needs the keys it changes:

```json
{
  "target_lines_per_split": 250,
  "weights": { "prose": 1 },
  "patterns": { "risky": ["(^|/)infra/", "(^|/)billing/"] }
}
```

Top-level keys are `target_lines_per_split`, `hard_cap`, `skip_threshold`, `weights`, and `patterns`. Config patterns (a regex, or an array of regexes) **extend** the built-in pattern, while a `*_PATTERNS` env var replaces it. Unknown keys, bad values, and goals out of order (`skip_threshold ≤ target_lines_per_split ≤ hard_cap`) stop `analyze.sh` with an error naming the file.

Sources: Google's small-CLs guide (about 100 lines is reasonable), SmartBear/Cisco (under 400 lines per review), Kudrjavets et al. 2022 (845K PRs, size doesn't relate to time-to-merge), and LinearB 2026 (vendor data: elite teams are under 100 lines at p75). The 0.5× test weight is a configurable choice with no study behind it.

**Skip the split** if `weighted_review_lines` is below the confirmed skip threshold — confirm with the user before proceeding anyway.

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

### Step 2: Analyze and confirm split goals

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/stacking-prs/scripts/analyze.sh" "$ORIG_BASE"
```

Use the JSON's `weighted_review_lines`, `directory_groups[].weighted_lines`, `files[].weighted_lines`, and `excluded_files[]` to design splits. The `weights` object echoes the weights in effect, and `config_files` lists the config files that were loaded.

**Confirm the split goals every run (REQUIRED).** Before designing any split, ask the user with AskUserQuestion. Show the branch's weight and each goal from the JSON (`target_lines_per_split`, `hard_cap`, `skip_threshold`), labelled with its source from `goal_sources`:

```markdown
This branch weighs **1,240** review lines.
Split goals for this run:
- Target per PR: 300 (default)
- Hard cap: 600 (project config)
- Skip the split below: 200 (default)
```

Options: (A) use these, (B) change them, then ask for the new numbers. The answers apply to this run only. Never write them to a config file; if the user wants new defaults, point them to `.quirk/stacking-prs.json`. Ask only about the goals, not the weights.

**Detect non-linear history:**
```bash
git log --merges --oneline "$ORIG_BASE..HEAD"
```
If merge commits exist, `git rebase --onto` linearizes by default. Surface to user; default to **cherry-pick extraction** instead of `--rebase-merges`.

### Step 3: Present the plan (REQUIRED — never skip)

**Off-ramp check.** As soon as the plan's size is known, compare it to the thresholds, using the target the user confirmed in Step 2:

| Plan | What to show |
|---|---|
| More than 4 layers | Warn that practitioners report 3-4 layers as the practical limit, then offer the alternatives below |
| `weighted_review_lines` under 2× the target (for example 480 against a target of 300, since 480 < 600) | Say a single PR is likely easier, then offer the alternatives below |
| 2-4 layers and at least 2× the target | The stack plan only. No off-ramps |

The alternatives are (E) one PR with atomic commits, reviewed commit by commit, and (F) sequential PRs to trunk behind a feature flag (Strategy 4). The stack plan stays the default and the user picks. If the user picks an alternative, end the split flow here. Neither path is built by this skill.

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

Options: (A) execute, (B) modify groupings, (C) change names, (D) cancel, plus (E) and (F) when the off-ramp check applies. **Get explicit approval before any git operation.** Execute one split at a time.

### Step 4: Execute one split

Pin variables before extracting — this is what prevents the `--onto` ambiguity footgun:

```bash
ORIG_BASE_SHA=$(git merge-base "$ORIG_BASE" HEAD)
CURRENT="$(git branch --show-current)"
SPLIT_BASE="<new_branch_name>"

"${CLAUDE_PLUGIN_ROOT}/skills/stacking-prs/scripts/extract.sh" \
  "$SPLIT_BASE" "$ORIG_BASE" <file1> <file2> ...

git rebase --no-update-refs --onto "$SPLIT_BASE" "$ORIG_BASE_SHA" "$CURRENT"
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

Draft these with branch names in place of `#N`. PR numbers don't exist until Step 6, and Step 7 fills them in.

**Native header.** That is the classic four-section header. When `native_available` is true (the stack gets registered in Step 6f), GitHub draws the stack map and the review order itself, so the description carries two sections only:

```markdown
## Feature Goal
Add user payment method management.

## Intentionally Missing
HTTP endpoints in #4, UI in #5 (layer-boundary self-containment exception).
```

Any other stack gets the classic four-section header. When `forge` is `github` and `gh_stack_installed` is false, end your closing message to the user with one line, and keep it out of the PR descriptions: "Tip: `gh extension install github/gh-stack` lets GitHub manage this stack natively."

### Step 6: Push, create, retarget — in this order

Order matters: a new branch must exist on the remote before any PR can target it.

**CI preflight (GitHub and GHES, when `native_available` is false).** No PRs exist yet, so ask `stack.sh` which workflows would skip the planned bases. Pass every split branch, since each one becomes a non-trunk base:

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/stacking-prs/scripts/stack.sh" --check-ci "${SPLIT_BRANCHES[@]}"
# {"schema":1,"skipped":[{"base":"auth-schema","files":[".github/workflows/test.yml"]}]}
```

An empty `skipped` means go ahead. Otherwise stop before any push, name each workflow file and the bases it skips (for example: `test.yml` runs on `pull_request` with `branches: [main]`, so it won't run on layers 2 and up), and give two fixes. Either register the stack natively so CI runs against the stack base, or widen the `branches:` filter. Don't edit workflow files. The user decides whether to continue. The scan is a line-based heuristic, so a trigger written in a shape it can't read gives no warning.

```bash
# a. Push every new split branch
for b in "${SPLIT_BRANCHES[@]}"; do git push -u origin "$b"; done

# b. Force-push the rebased current branch
git push --force-with-lease --force-if-includes origin "$CURRENT"   # never plain --force

# c. Notify reviewers BEFORE retargeting (inline comments may be invalidated)
gh pr comment <existing_pr> --body "Splitting into a stack. Old diff: <commit-permalink>. New base: \`$NEW_TOP\`."

# d. Create draft PRs for the lower stack (#1..#N-1)
gh pr create --base "$ORIG_BASE" --head "$SPLIT_1" --draft ...
gh pr create --base "$SPLIT_1"   --head "$SPLIT_2" --draft ...

# e. Retarget the existing PR onto the new top
gh pr edit <existing_pr> --base "$NEW_TOP"
# GitLab: glab mr update <iid> --target-branch "$NEW_TOP" --repo "$NS/$PROJECT"
#   On failure: print the web URL and ask the user to retarget manually.
```

After the retarget, check whether the existing PR is now a non-bottom layer and still ready for review (not a draft). If so, convert it to draft so it follows the rule that non-bottom PRs stay in draft:

```bash
gh pr ready <existing_pr> --undo
# GitLab: glab mr update <iid> --draft --repo "$NS/$PROJECT"
```

Tell the user the PR went back to draft and that its existing approvals stay on it. Step 7 marks the bottom PR ready once every header is right.

**f. Register natively (only when `native_available` is true).** Once every PR exists and is retargeted, list the stack's branches bottom to top:

```bash
gh stack link "$SPLIT_1" "$SPLIT_2" ... "$CURRENT"   # <bottom> ... <top>
```

`gh stack link` accepts branch names, PR numbers, or PR URLs in stack order. `native_available` is true only on github.com, with `gh stack` installed and no cross-fork layer. If it's false, the stack stays classic, and Step 5 already chose the four-section header.

### Split this layer further: restack the layers above it

Use this section when Step 4's `CURRENT` is a layer with other layers above it (the router's "Split this layer further" on a non-top layer). The split rewrites only `CURRENT`, so every layer above it still sits on `CURRENT`'s old history and its PR diff would stop being incremental. Skip this section when `CURRENT` is the top layer.

`extract.sh` made `backup/<CURRENT>_<timestamp>`, which holds `CURRENT`'s pre-split head. After Step 6 pushes `CURRENT`, restack the layers above it bottom to top. Each layer's `--old-tip` is its parent's head before the parent moved:

```bash
RESTACK="${CLAUDE_PLUGIN_ROOT}/skills/stacking-prs/scripts/restack.sh"
"$RESTACK" --branch <layer above CURRENT> --onto "$CURRENT" \
  --old-tip "$(git rev-parse backup/<CURRENT>_<timestamp>)" --pr <its number>
# read old_head from its JSON, then the next layer up:
"$RESTACK" --branch <next layer> --onto <layer above CURRENT> --old-tip <old_head> --pr <its number>
```

Read the exit code after every layer, as [Land](land.md#post-merge-sync) does. Then refresh every header with Step 7, because the stack's shape changed.

### Step 7: Refresh every stack header, then mark the bottom ready

Now that every PR number exists, rewrite the stack header on **every** PR in the stack, bottom to top. That includes the existing PR, whose description predates the split and has no header yet. Replace only the header sections (Stack Position through Intentionally Missing, or Feature Goal and Intentionally Missing for a native stack) and leave the rest of each description as its author wrote it. For a PR with no header, prepend one.

```bash
gh pr view "$PR" --json body --jq .body > "$TMPDIR/pr-$PR.md"
# edit: regenerate the header for this PR's position, keep the rest of the body
gh pr edit "$PR" --body-file "$TMPDIR/pr-$PR.md"
# GitLab: glab mr update <iid> --description "$(cat "$TMPDIR/mr-$IID.md")" --repo "$NS/$PROJECT"

gh pr ready "$BOTTOM_PR_NUM"   # only after every header is correct
```

Re-run this step whenever the stack's shape changes. That means after each further split, after any PR in the stack merges (the next one up becomes the bottom and retargets to `ORIG_BASE`), and after reordering. One stale header misleads reviewers on every PR above it.

**Keep all non-bottom PRs in draft** until the full stack is reviewed — prevents premature merges that silently change downstream diffs.

### Step 8: Cleanup & caveats

`extract.sh` accumulates `backup/*` branches (local-only, not pushed). After the stack merges cleanly:
```bash
git branch -D $(git branch --list 'backup/*' --format='%(refname:short)')
```
Don't auto-delete — user may need to recover from a bad rebase.

**Commit history:** rebasing rewrites SHAs. `Co-authored-by:` trailers survive but references break. Re-sign signed commits (`git rebase --signoff`). Review Conventional Commits history before pushing if you use `release-please`/`semantic-release`.

### Per-forge notes for this phase

| Forge | What changes |
|---|---|
| GitHub, native-capable (`native_available`) | Run Step 6f after the PRs exist. Use the two-section header. Skip the CI preflight, because native stacks run CI against the stack base |
| GitHub without `gh stack` | Classic stack, four-section header, the CI preflight, and the one-line tip |
| GHES, or a cross-fork stack (`cross_fork` warning) | Classic stack, four-section header, the CI preflight. No tip, because native isn't available here |
| GitLab | Classic stack. Create each MR with `glab mr create --draft --source-branch <head> --target-branch <base>`, and use `glab mr update` as shown in Steps 6 and 7. Only 4 open MRs retarget automatically when a target merges, so if the plan is deeper than 4, say that Land will retarget the rest by hand |

## Quick Reference

| Symptom | Action |
|---|---|
| `weighted_review_lines` >400 / >600 | Split / hard split |
| Mostly tests (200 src + 500 tests = 450 weighted) | Keep together (0.5× weight) |
| Touches migrations, auth, or CI | Smaller PR; risky files count 1.5× |
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
| Stack changed (new split, merge, reorder) | Re-run Step 7 on every PR in the stack |

## Common Mistakes

- **Setting target >400 lines** — past the cognitive-load cliff. Default 300, hard cap 600.
- **Each PR targeting `main` (progressive PRs)** — incremental diff lost after any merge. Use stacked or trunk + flags.
- **No stack header in PRs, or a stale one** — reviewers flag placeholders as bugs. Refresh every header after the stack changes, not just the PR you touched.
- **Definitions without usage** — bundle a real caller, or a contract test at a layer boundary, or link forward in "Intentionally Missing".
- **Splitting tests off** — tests are 0.5× weight; almost never needs splitting.
- **Confusing `ORIG_BASE` and `SPLIT_BASE` in rebase** — pin `ORIG_BASE_SHA` *before* extract; verify with `git log --oneline "$SPLIT_BASE..$CURRENT"`.
- **Retargeting without warning reviewers** — comment first, link the old commit SHA.
- **Pushing in the wrong order** — branches must be on the remote *before* PRs can target them.
- **`--force` instead of `--force-with-lease --force-if-includes`** — silently overwrites collaborators.
- **Splitting after the fact** — for new features, plan layers up front.

## Red Flags — STOP

- Designing splits without running `analyze.sh`
- Designing splits before the user confirmed this run's split goals
- Git operations before user approves the plan
- Suggesting a single 2,000-line split as "good enough"
- Defining something without including any caller (when one exists in the diff)

## Bundled Scripts

`${CLAUDE_PLUGIN_ROOT}/skills/stacking-prs/scripts/`:
- `analyze.sh <target>` — JSON budget breakdown: raw lines per file kind and line kind, weighted totals per file and directory. Bash 3.2+, BSD awk.
- `weigh.awk` — the per-line weighing `analyze.sh` runs over the diff.
- `stack.sh --check-ci <base>...` — read-only CI-filter scan for the planned bases, used by the Step 6 preflight. The router runs `stack.sh` itself for detection.
- `extract.sh <new> <target> <files>...` — creates timestamped backup, then a new branch from target, populates from feature branch. Handles **modifies, adds, AND deletes**. For renames pass both old and new paths.
