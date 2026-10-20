---
name: stacking-prs
description: Use when splitting a large branch into a stack of smaller PRs/MRs, when managing or updating an existing stack (review feedback on a lower PR, trunk moved, a broken chain), or when landing or merging a stack and syncing the rest after the bottom merges. Also use when a reviewer asks to "make this PR smaller" or the user invokes /stacking-prs.
---

# Stacking PRs/MRs: split, manage, land

A stack is a chain of PRs/MRs where each one except the bottom targets the one below it. This skill covers the whole life of a stack, including stacks it didn't create. This file picks the phase and holds the rules every phase obeys. Each phase has its own reference file, so read only the one you're in.

**Announce:** "I'm using the stacking-prs skill to <split this branch | manage this stack | land this stack>."

## Step 0: detect

Run detection first and show the result. It only reads. It never fetches, checks out, pushes, or changes the forge.

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/stacking-prs/scripts/stack.sh"
```

It prints JSON: `forge` (`github`, `ghes`, `gitlab`, `none`), `mode` (`native`, `classic`, `local`), `in_stack`, `trunk`, `native_available`, `layers[]`, `merged_parents[]`, and `warnings[]`. If the forge CLI is missing or fails, it falls back to `local` mode with a `forge_unavailable` warning and still exits 0. It exits 1 only for a usage error, a non-repo, a detached HEAD, or no `jq`. Read the error and stop.

When `in_stack` is true, print the stack map before asking anything. List layers bottom first, mark the current one, and show each layer's PR, state, CI, review, and whether it's behind its parent. Mention every warning that applies:

| Warning | Say |
|---|---|
| `broken_chain` | A PR targets a merged branch or a missing one. Repair is in Land's post-merge sync |
| `branched_stack` | Two PRs share a base, so the map stops at the fork |
| `deep_stack` | More than 4 layers. Practitioners report 3-4 as the practical limit |
| `gitlab_retarget_cap`, `gitlab_mixed_authors` | GitLab retargets only up to 4 open MRs, and its stack view stops at the first MR by a different author |
| `cross_fork` | A cross-fork stack can't be native |
| `ci_filter` | A workflow filter will skip CI on layers above the bottom |
| `layer_in_other_worktree` | A layer is checked out elsewhere, which blocks a rebase |

## Pick the phase

| What Step 0 shows | Do |
|---|---|
| `in_stack` is false: one PR to trunk, or no PR, and no stacked branches | Say "not in a stack" and start [split](references/split.md) without asking |
| `in_stack` is true, `mode` is `native` or `classic` | Ask with AskUserQuestion: Manage, Land, or Split this layer further. Nothing changes until the user picks |
| `mode` is `local` | Offer Manage or Split. Don't offer Land, because nothing is pushed and nothing can merge |
| `broken_chain` is present | Flag the broken link and offer Land's post-merge sync to repair it |

If the user already named the job ("address this review comment", "PR 1 merged, what now", "split this up"), still show the stack map, then go straight to that phase.

- [Split](references/split.md): cut one large branch into a stack. Includes the off-ramps for deep stacks and small diffs, the CI-filter preflight, and native registration.
- [Manage](references/manage.md): apply feedback to a lower layer, restack onto moved trunk, and handle layers checked out in other worktrees.
- [Land](references/land.md): check the bottom PR before the user merges it, then rebuild the rest of the stack after.

## Rules every phase obeys

- **No git write before approval.** Show the plan for an operation and get the user's approval before running it.
- **Back up before rewriting history.** Every rewrite makes a `backup/<branch>_<timestamp>` branch first. Backups stay local and are never pushed.
- **Force-push safely.** Use `--force-with-lease --force-if-includes`, never a bare `--force`.
- **The user merges.** The skill never runs `gh pr merge`, `gh stack merge`, or `glab mr merge`. It checks before the merge and syncs after.
- **Draft until it's the bottom.** Non-bottom PRs stay in draft. Only the current bottom is marked ready.

## Modes

- **Native:** a GitHub stack registered with GitHub's stacked PRs. GitHub draws the map, rebases after a merge, and runs CI against the stack base. Use `gh stack` for the work.
- **Classic:** PRs/MRs whose bases chain, with no native registration. The skill does the rebase and retarget work itself. Every GitLab stack and every GHES stack is classic.
- **Local:** branches chained in git ancestry, nothing pushed yet.

## Scripts

All are under `${CLAUDE_PLUGIN_ROOT}/skills/stacking-prs/scripts/`.

- `stack.sh [--branch <b>] [--trunk <t>] [--remote <r>]` reads the stack. `stack.sh --check-ci <base>...` checks which workflows would skip the planned bases.
- `restack.sh --branch <b> --onto <base> --old-tip <sha> [--pr <n>] [--no-push]` replays one layer onto a new base, with a backup, a lease push, and a retarget. Land and Manage use it.
- `analyze.sh` and `extract.sh` weigh a branch and extract a slice of it. Split uses them. The config files are `~/.quirk/stacking-prs.json` and `<repo>/.quirk/stacking-prs.json`.

## Integration

- `using-git-worktrees` — stage splits in isolated worktrees
- `finishing-a-development-branch` — once the bottom merges and the stack collapses
