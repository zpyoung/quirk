---
name: split-branch
description: Use when splitting a PR, MR, or branch into reviewable stacked slices, or when asked to make a PR smaller without losing the original review.
---

# Split a Branch into MVP-First Stacked Slices

## Overview

Split a large feature branch into a stack of smaller PRs/MRs. By default, the bottom feature slice is the smallest end-to-end outcome a user can observe: an **MVP-first vertical** slice. Each later PR/MR targets the preceding branch. Preserve and retarget the original PR/MR; never close and recreate it.

**MVP-first is a strong default, not a validity gate.** Whether a slice feels vertical is a soft planning prompt, never a STOP condition or an automatic re-split loop. The hard bottom-slice bar is **green + mergeable + main stays releasable**.

Announce: “I'm using the split-branch skill to plan and execute an MVP-first split.”

## Targets and Weighting

| Change | Target |
|---|---|
| Bug fix / config | <100 / <50 |
| New feature | 200-400 |
| Refactor | 300-500 |
| **Default** | **~300 source lines** |
| Hard cap | 600 source lines |

**LOC** means `added + deleted` for source files. Generated code, lockfiles, and vendored files are excluded by the analyzer; `EXCLUDE_PATTERNS` overrides its defaults.

**Test weighting:** reviewers skim tests, so tests count at **~0.5×**. The analyzer reports `weighted_review_lines = source + (tests / 2)`. Keep proving tests with their source rather than splitting them away to meet a raw count. This reviewer-effort weighting is a heuristic, not a claim that tests are less important.

Refuse to split under ~200 weighted lines unless the user explicitly asks to proceed. Prefer coherent 450-line slices to arbitrary 300 + 150 partitions: **coherence beats line targets up to the 600-line hard cap**.

Sources are correlational: SmartBear/Cisco (2,500 reviews), LinearB 2025 (6.1M PRs, elite teams under 219 LOC/PR), and Graphite (50-line PRs merge about 40% faster than 250-line PRs).

## Strategies

Invocation surface:

- `--vertical` — force **MVP-first vertical** planning, the default.
- `--layers` — force **layer-first** planning, the fallback.
- With neither option, auto-detect using the strategy probe below and present the mechanical recommendation in the plan.

### MVP-first vertical (default)

Choose the smallest user-observable path through the changed layers and put it first. It normally includes an entry point, the core state change, and one proving test. Add subsequent slices by distinct user outcome rather than by technical directory.

### Layer-first (fallback)

When no bounded vertical path is available, order architectural layers bottom-up, for example schema → repository → service → API → UI, and bundle tests with each layer. A layer may have only tests as callers; call that out in the PR/MR body. Feature flags may keep incomplete upper layers dark while main remains releasable.

### Strategy probe

Seed the probe on a changed entry point: a **route**, **handler**, **CLI command**, or **event registration**. Take its heuristic **compile closure** (changed definitions/imports/callers required to build), estimate its weighted size, and compare it against the 600-line cap. If no changed entry point exists, the closure is ambiguous, or the closure exceeds the cap, recommend layer-first **and name the blocker** (for example, “route closure is 742 weighted lines”). This is a recommendation, not semantic proof.

## Labelling and Grouping

Grouping is **file-first**. Assign each changed file an intent tag; descend to hunk-level grouping only where a file's hunks carry conflicting intent tags. Do not split an unsplittable binary or a change below Git's hunk floor.

The intent-tag vocabulary is exactly:

`FEATURE-CORE`, `FEATURE-VARIANT`, `VALIDATION`, `ERROR-HANDLING`, `PERF`, `REFACTOR/PREFACTOR`, `CONFIG-INFRA`, `TEST`, `DOCS`, `COSMETIC`, `UNRELATED`.

The dependency graph **orders and validates but never groups**. Use it after intent grouping to put prerequisites below dependants, detect cycles, and check that each proposed slice can build.

### Deferral ladder

To shrink the first feature slice, use this **deferral ladder** in order, stopping as soon as it fits:

1. Remove `UNRELATED` work from the stack.
2. Defer `COSMETIC` and nonessential `DOCS`.
3. Defer optional `FEATURE-VARIANT` behavior and `PERF` work.
4. Defer nonessential `REFACTOR/PREFACTOR` and `CONFIG-INFRA` work that is not a prerequisite.
5. Defer additional `VALIDATION` and `ERROR-HANDLING` cases while preserving a safe happy path.

**Never defer:** the entry point, the state change that makes the outcome observable, or the one proving test. Security or data-integrity validation is likewise required, not optional scope.

### Ordering and sizing

- Prerequisite leftovers go in a prep slice **below the MVP slice**; they do not displace MVP-first as the first feature slice.
- Slices **#2..N are ordered by descending user-facing value**, subject to dependency order.
- Definitions normally travel with a real caller. At a layer boundary, a contract/integration test may be the caller; unit-test-only is a last resort.
- Prefer a self-contained slice over a line target, but never exceed the 600-line hard cap.
- A monorepo-wide rename may use a compatibility shim and phased call-site migration.

## Pipeline and the One Gate

The pipeline is:

**pre-flight → analyze → label → probe → group → plan → GATE → materialize → verify → conserve → publish**

There is exactly one mandatory approval gate. Write the complete grouping and publication plan to `.git/split-branch/<branch>.plan.md`, show it to the user, and obtain approval at **GATE**. This plan file is the approval artifact. Before the gate, do not create branches, commits, worktrees, or remote changes. After approval, do not add another mandatory gate.

The Markdown plan records the base/head SHAs, strategy and blocker/recommendation, file/hunk IDs and tags per slice, dependency/order checks, weighted sizes, branch names, build/test commands, original PR/MR identity and base, remote/forge, and recovery notes. Generate the JSON publication plan required by the publisher from this approved artifact.

## Build and Test Command Discovery

The skill, not a script, discovers commands in this order:

1. Use an **explicit value already recorded for this repo**.
2. Use **convention detection**: inspect `Makefile` targets, then `package.json` scripts, then `pyproject.toml` / `pytest`, then `cargo`, then `go test`.
3. Read the **repo's CI config** and use its build and test commands.
4. **Ask the user once**, then **record the answer in the plan file** so later slices reuse it.

Script-side auto-detection is out of scope. The skill passes the discovered build command and optional test command to `verify.sh`; an explicitly empty build command is valid only when the plan explains why no build exists.

## Execution

### 1. Pre-flight and analyze

Require a repository, attached non-base branch, and clean index/worktree. Determine the base from an existing PR/MR before the remote default. Detect the remote from `--remote`, then `remote.pushDefault`, then the conventional fallback. Surface branch protection, permissions, and merge commits before planning.

Before touching anything, create a restorable backup of the branch tip and capture its name:

```bash
backup_ref=$(scripts/preflight.sh --base <base> [--branch <ref>])
```

`preflight.sh` enforces the state checks above and creates `backup/<branch>_<ts>` pointing at the current tip, so any later slice, rebase, or force-push can be undone with `git reset --hard <backup_ref>` (or `git branch --force <branch> <backup_ref>` from another branch). Exit codes are: 0 success, ref name on stdout; 2 dirty index/work tree; 3 detached HEAD or the target branch equals the base; 4 not a git work tree, base/branch unresolved, or the backup could not be created; 5 bad arguments. Keep `backup_ref` for the whole run — the verify-failure protocol below cites it in the restore command it reports.

Run the analyzer once for weights and once for hunk inventory:

```bash
scripts/analyze.sh [--remote <name>] <base>
scripts/analyze.sh --hunks [--remote <name>] <base>
```

Pin the emitted base and head SHAs. Grouping uses the hunk inventory, not a fresh later diff.

### 2. Label, probe, group, and plan

Apply the vocabulary and file-first rule, run the strategy probe, order groups with dependencies, and write the plan. Present bottom-to-top branches, targets, weighted sizes, hunk IDs, intentionally missing work, original PR/MR retarget, and the command-discovery result. Stop only at the single GATE.

If dependencies form a cycle, **merge cycling slices on a dependency cycle** until the condensation graph is acyclic; if that exceeds the cap, use layer-first or report the blocker. If hunk surgery is blocked by an unsplittable change or repeated application failure, use **commit-boundary splitting when hunk surgery is blocked**, via `slice.sh --at-commit`.

### 3. Materialize

For each approved slice, feed selected analyzer IDs to the materializer. Its throwaway index creates trees and commits without touching the caller's worktree or index:

```bash
scripts/slice.sh --base <sha> --head <sha> --parent <ref> \
  --branch <name> --hunks <id-file> --message <message>
scripts/slice.sh --at-commit <sha> --parent <ref> --branch <name>
```

Exit codes are: 0 success; 2 unknown hunk ID; 3 patch/application conflict; 4 branch exists; 5 bad arguments, dirty caller state, or internal state error; 6 invalid partial binary selection.

### 4. Verify and conserve

Verify every slice in its own disposable worktree:

```bash
scripts/verify.sh --branch <ref> --build-cmd <cmd> [--test-cmd <cmd>] \
  [--worktree-root <dir>] [--keep-on-failure]
```

Exit codes are: 0 green; 1 build failed; 2 tests failed; 4 worktree infrastructure/cleanup failed; 5 bad arguments.

**On verify failure, retry once, then stop.** When a slice fails to build or test, it usually references a symbol defined by a hunk that landed in a later slice. Consult the dependency graph for that symbol, pull the defining hunk up into the failing slice, and retry once. If it still fails after that single retry, stop: keep the slices that already verified as local branches, push nothing, and report the failing slice together with the restore command `git reset --hard <backup_ref>` from pre-flight. Never force a non-building slice forward, never silently merge it into its successor, and never exceed the one retry.

For each slice, check mergeability and that main would stay releasable. Treat “is this really vertical?” only as a soft review prompt. Finally conserve the original result by comparing trees: the top materialized tree must equal the original head tree.

### 5. Publish and preserve the original review

The publication JSON contains `base`, `original_branch`, optional numeric `original_pr`, and ordered `slices` with `branch`, `parent`, `title`, `body`, and one-based `position`.

```bash
scripts/publish.sh --plan <plan.json> [--remote <name>] \
  [--forge github|gitlab] [--dry-run] [--fork] [--no-force-push]
```

It pushes all branches before forge operations, warns reviewers, creates draft lower PRs/MRs with stack metadata, retargets the original PR/MR to the top split branch, and marks only the bottom ready. Exit codes defined by the script are: 0 success; 3 a local slice branch is missing; 5 bad arguments/malformed plan; 7 required forge CLI missing. Plain `gh` and `glab` are the only forge integrations.

If branch protection prevents rewriting the original, use `--no-force-push`, create new review branches, and explain why the original cannot be retargeted. Otherwise the original PR/MR is preserved and retargeted, never closed and recreated.

## Restacking after Merge

PR/MR bodies carry machine-readable parent, base SHA, and stack position metadata. After a parent is squash-merged or rebased, restack its child onto the new trunk:

```bash
scripts/restack.sh --branch <child> --onto <new-trunk> \
  [--base-sha <sha>] [--remote <name>] [--dry-run]
```

It reads the recorded base from the body unless explicitly supplied, rebases transactionally, updates metadata, and restores the branch if publication fails. Exit codes are: 0 success; 2 recorded base unavailable; 3 content conflict, cleanly aborted; 4 child/new trunk unresolved; 5 bad arguments; 6 forge, rebase, cleanup, or transactional metadata failure.

Forge gotchas:

- **GitLab never auto-retargets fork MRs**; print the manual command.
- GitLab's **“Delete source branch” suppresses retargeting** of dependent MRs; turn it off until dependants are retargeted.
- **Squash and rebase both rewrite SHAs**; restack from body metadata rather than assuming ancestry remains.

## Guardrails

Every item below is a rule, not advice:

- **Never pass `--recount` to `git apply`** — recounting can silently reinterpret selected patch boundaries.
- **Never use `git apply --check` as a pre-flight** — application is already atomic, so a pre-flight adds a drift race.
- **Never use `--check --3way`** — it is not a safe preview of the real indexed application.
- **Generate grouping diffs at `-U0` only** — zero context gives stable hunk identity for grouping, not application.
- **Apply with ordinary context** — context protects against importing adjacent changes.
- **Never use `--unidiff-zero` against a drifted tree** — zero-context application can land on the wrong content; it is allowed only while constructing the exact undrifted base-relative tree.
- **Verification uses a dedicated `git worktree` per slice** — isolation prevents caller-worktree contamination.
- **Never use a `git checkout` loop** — checkout mutates shared caller state and makes cleanup fragile.
- **Conservation compares trees with `git diff --quiet A B` or `rev-parse <ref>^{tree}`** — tree identity proves the final content is conserved.
- **Never compare diff-of-diffs** — textual diff formatting is not content identity.
- **Use `git push --force-with-lease`** — the lease protects collaborators; **never use bare `--force`** because it can overwrite remote work.
- **Never hardcode `origin`** — accept `--remote`, default to `remote.pushDefault`, then fall back to `origin`; runtime selection keeps nonstandard repositories working.
- **No interactive commands** — automation must not hang; pass noninteractive flags to Git and forge CLIs.
- **`--3way` requires `--full-index`** — full blob IDs are required for safe three-way fallback.
- **`--3way` is mutually exclusive with `--reject`** — the modes have incompatible failure semantics.

## Why Stacked, Not Progressive PRs

Progressive PRs all target main and grow toward the full diff. They lose clean incremental review after a mid-chain merge.

| | Stacked | Progressive |
|---|---|---|
| Clean incremental diff | ✅ Always | ❌ Lost after a mid-chain merge |
| CI overhead per PR | Medium | High (each is a full feature) |
| Merge race conditions | Low | High |
| Partial revert safety | ✅ | ❌ |
| Reviewer autonomy | Bottom-up order | Free pick |

If rebase-cascade pain dominates, prefer trunk plus feature flags rather than progressive snapshots.

## Terminology

- **Stack** — chain of PRs/MRs where each slice except the bottom targets the preceding slice branch
- **Slice** — one coherent review unit represented by a branch and PR/MR
- **Bottom** — PR/MR targeting the original base; reviewed and merged first
- **Top** — slice farthest from the original base; the original feature PR/MR is retargeted here
- **MVP slice** — first feature slice containing the minimum observable user outcome
- **Prep slice** — prerequisite-only leftovers below the MVP slice
- **Original base** — the PR/MR's pre-split target branch
- **Inventory base/head** — immutable SHAs captured before grouping and materialization

## Script Reference

`${CLAUDE_PLUGIN_ROOT}/skills/split-branch/scripts/`:

- `preflight.sh` `--base <ref> [--branch <ref>]` — verifies a clean non-base branch and creates a restorable `backup/<branch>_<ts>` ref, printing its name.
- `analyze.sh` `[--hunks] [--remote <name>] [base]` — reports weighted file statistics or immutable hunk inventory.
- `slice.sh` `--base/--head/--branch/--hunks` or `--at-commit` — materializes a selected slice with a throwaway index.
- `verify.sh` `--branch --build-cmd [--test-cmd ...]` — builds and tests one ref in a dedicated disposable worktree.
- `publish.sh` `--plan <json> [forge/remote options]` — pushes the stack, creates reviews, and retargets the original review.
- `restack.sh` `--branch --onto [metadata options]` — transactionally rebases a child after its parent SHA is rewritten.
- `stackmeta.sh` `emit|parse|upsert` — manages machine-readable stack metadata in PR/MR bodies and can also be sourced as a library.

`stackmeta.sh` returns 0 on success, 2 for absent metadata, 3 for malformed metadata, 4 for multiple metadata blocks, and 5 for bad arguments.
