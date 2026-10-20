# Land: check the bottom, then rebuild the stack after it merges

This is the Land phase of the stacking-prs skill. The user presses merge. This phase checks the bottom PR before that and rebuilds the rest of the stack after it. The router (`../SKILL.md`) has already run `stack.sh`, so its JSON is the input here. Land isn't offered in local mode, because nothing is pushed and nothing can merge.

## The no-merge rule

The skill never runs `gh pr merge`, `gh stack merge`, or `glab mr merge`, and never enables auto-merge or a merge queue entry. If the user asks the skill to merge, say it doesn't merge and hand the button back. If they ask to merge a PR that isn't the bottom, decline and explain why. On a native stack that merge lands every layer below it. On a classic stack it lands the PR into its parent's branch instead of trunk. Offer to run the checks on the bottom PR instead.

## Pre-merge checks on the bottom PR

Read `layers[0]` from the `stack.sh` JSON. The bottom is ready only when all of these hold:

| Check | Passes when | If it fails |
|---|---|---|
| Base | `base` equals `trunk` | The chain is broken. Go to [Post-merge sync](#post-merge-sync) |
| CI | `ci == "pass"` | Say `fail` means fix it (see [Manage](manage.md)), and `pending` or `none` means wait or ask whether CI is configured |
| Review | `review == "approved"` | Say who or what is missing: `changes_requested` or `review_required` |
| Up to date | `behind_parent == 0` | Offer the trunk-moved flow in [Manage](manage.md#trunk-moved) |
| Not a draft | `state != "draft"` | Offer `gh pr ready <number>` (GitLab: `glab mr update <iid> --ready`) after the user approves |

When any check fails, list every blocker against the bottom PR in one message and stop. Don't touch the layers above it. When all pass, tell the user the bottom PR is ready to merge and wait for them to say it's merged.

## Post-merge sync

Run this when the user says the bottom merged, or when `stack.sh` reports `broken_chain` with a non-empty `merged_parents`. It also repairs a broken chain from [Manage](manage.md#broken-chain).

### Classic stack (GitHub, GHES, GitLab)

1. **Fetch and re-read.** Run `git fetch <remote>`, then `stack.sh` again. Confirm `merged_parents[]` lists the bottom you expected, with its `head_sha` and `merge_sha`. If it's missing, the PR isn't merged yet, so stop. If the forge already retargeted the next PR to trunk, that list is empty. In that case take the old tip from the merged layer's local branch (`git rev-parse <merged branch>`), whose name is in the stack map you printed before the merge.
2. **Show the restack plan and get approval.** One row per remaining layer, bottom first: the branch, what it goes onto, and the old tip. Include the last steps (headers, `gh pr ready`, deleting the merged local branch).

   | Layer | `--onto` | `--old-tip` |
   |---|---|---|
   | first remaining layer | trunk | `merged_parents[].head_sha` |
   | each layer above | the layer below it | that lower layer's `old_head` from its `restack.sh` run |

3. **Restack each layer, bottom to top.** `--old-tip` is the parent's head before it moved, so the layer replays only its own commits, whether the parent was squashed, rebased, or merged with a merge commit.

   ```bash
   RESTACK="${CLAUDE_PLUGIN_ROOT}/skills/stacking-prs/scripts/restack.sh"
   "$RESTACK" --branch <layer 2> --onto <trunk> --old-tip <head_sha> --pr <number of layer 2>
   # read old_head from its JSON, then:
   "$RESTACK" --branch <layer 3> --onto <layer 2> --old-tip <layer 2 old_head> --pr <number of layer 3>
   ```

   `restack.sh` makes `backup/<branch>_<timestamp>`, rebases with `--onto`, pushes with `--force-with-lease --force-if-includes`, and retargets the PR when its base differs. Add `--forge gitlab` on GitLab when the remote host doesn't say so. Read the exit code after every layer:

   | Exit | Meaning | What to do |
   |---|---|---|
   | 0 | Rebased, pushed, retargeted | Continue with the next layer |
   | 1 | A precondition failed or the replay count was off | Stop, show the message and backup |
   | 2 | Conflict. The rebase was aborted and the branch is back at its old head | Stop, list `conflicted_files`, point to the backup, and don't auto-resolve |
   | 3 | The branch is checked out in another worktree. Nothing changed | Ask the user to free it, or run `restack.sh` from inside that worktree |
   | 4 | The push was rejected. The local rebase and backup are kept | Stop. The remote moved, so fetch and compare before any retry, and never fall back to `--force` |
   | 5 | The retarget failed after the push | Finish the remaining layers, then give the user `pr_url` to retarget by hand |

4. **Refresh every header.** Run [Split Step 7](split.md#step-7-refresh-every-stack-header-then-mark-the-bottom-ready) on every remaining PR, because positions and bases changed.
5. **Mark the new bottom ready.** Run `gh pr ready <number>` (GitLab: `glab mr update <iid> --ready`) on the new bottom only, after the headers are right. Every other layer stays in draft.
6. **Delete the merged local branch** with `git branch -D <merged branch>`. Keep the `backup/*` branches. `git branch -d` would refuse after a squash merge, so `-D` is expected here.
7. Offer to run Land again on the new bottom.

### Native stack (GitHub)

GitHub rebases the rest of the stack itself, so don't use `restack.sh`.

1. Run `gh stack sync --prune`. It fetches, fast-forwards trunk, rebases the stack onto it, pushes with lease, and deletes local branches for merged PRs. If it stops on a conflict or reports a diverged stack, don't force anything. Run `gh stack rebase` and resolve as [Manage](manage.md) describes.
2. Re-run `stack.sh` and confirm the next PR now targets trunk (`layers[0].base == trunk`).
3. Refresh the two header sections, Feature Goal and Intentionally Missing, on each PR, using [Split Step 7](split.md#step-7-refresh-every-stack-header-then-mark-the-bottom-ready). If the new bottom is still a draft, mark it ready.
4. Offer to run Land again.

## Per-forge notes for this phase

| Forge | What changes |
|---|---|
| GitHub, native | `gh stack sync --prune` replaces the restack loop |
| GitHub, classic, and GHES | The classic loop above. GitHub retargets a dependent PR on its own only when the merged head branch is deleted, so `restack.sh --pr` retargets explicitly |
| GitLab | The classic loop with `--forge gitlab`. Then verify the retargets (below) |

### GitLab: verify the retargets

GitLab retargets only up to 4 open MRs when their target merges, and `restack.sh` has already retargeted the next MR. After the loop, check every open MR in the stack against the plan:

```bash
glab mr view <iid> -F json   # compare .target_branch with the expected base
```

For any MR whose target is wrong, run `glab mr update <iid> --target-branch <expected base>` and tell the user which ones you fixed. The stack is only done when every open MR targets the layer below it, and the new bottom targets trunk.
