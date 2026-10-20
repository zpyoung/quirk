# Manage: change a stack that already exists

This is the Manage phase of the stacking-prs skill. Use it when the stack is live and nothing has merged out from under it: a reviewer wants a change on a lower layer, trunk moved, or the chain is broken. The router (`../SKILL.md`) has already run `stack.sh`, so its JSON (`mode`, `layers[]`, `warnings`) is the input here. If a bottom PR has merged, go to [Land](land.md) instead.

Every sequence below follows the router's rules. Ask the user to approve the plan before the first git write. Back up every layer before a rewrite. Push with `--force-with-lease --force-if-includes`, one branch at a time, never `--force`.

## Fix a lower layer from review feedback

Make the fix as a fixup commit, fold it into the commit it amends, and let `--update-refs` move every branch above it. The order is fixup, then backups, then rebase, then push, then verify.

### 1. Check the worktrees first (stop here if one is in the way)

`git rebase --update-refs` silently skips a branch that is checked out in another worktree, which would leave that layer behind. Read `layers[].worktree` from the Step 0 JSON, or look for the `layer_in_other_worktree` warning. If any layer has a path there, stop before writing anything and name the worktree and the layer. Ask the user to pick one:

- **Free the worktree.** The user switches that worktree off the branch or removes it. Re-run `stack.sh` and continue.
- **Rebase that layer separately afterward.** Run the steps below from the highest layer that is free in this worktree. After the push in step 4, restack the layer that was checked out elsewhere by running this from inside that worktree, where the branch is current, so `restack.sh` doesn't exit 3:

  ```bash
  cd <that worktree>
  "${CLAUDE_PLUGIN_ROOT}/skills/stacking-prs/scripts/restack.sh" \
    --branch <layer> --onto <rebased parent branch> \
    --old-tip "$(git rev-parse backup/<parent>_<timestamp>)" --no-push
  ```

  `--onto` is the parent as it is now, and `--old-tip` is the parent's head before the rebase, read from the parent's backup. Then push that layer with lease from any worktree, as in step 4. The layer being amended can't be the one checked out elsewhere. It has to be free.

### 2. Commit the fix as a fixup

Pick the commit the fix belongs to. `git log --oneline <parent>..<layer>` lists the layer's own commits. Switch to the top layer (the highest free one), make the change, and commit it against that commit:

```bash
git switch "$TOP"
git add <files>
git commit --fixup=<sha of the commit being amended>
```

Show the user which commit the fix lands in and which branches will move, and get approval before step 3.

### 3. Back up every layer, then fold the fixup in

```bash
TS=$(date +%Y%m%d_%H%M%S)
for b in "${LAYERS[@]}"; do git branch "backup/${b}_${TS}" "$b"; done

BASE=$(git merge-base "<remote>/<trunk>" "$TOP")
GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash --update-refs "$BASE"
```

`GIT_SEQUENCE_EDITOR=:` accepts the autosquashed todo list as written, so the rebase runs without opening an editor. The backup names match `extract.sh`. Backups stay local and are never pushed.

On a conflict, run `git rebase --abort`, report the files, point to the backups, and don't auto-resolve.

### 4. Push every branch that moved, with lease

```bash
for b in "${MOVED[@]}"; do   # bottom to top; a layer moved if its head differs from its backup
  git push --force-with-lease --force-if-includes <remote> "$b"
done
```

### 5. Verify and show the user

Each layer's own diff should have changed only where the fix landed. Show `git range-diff` for every moved branch, using the parent's backup as the old parent and the parent as it is now:

```bash
git range-diff <backup-parent>..<backup> <parent>..<branch>
# bottom layer: git range-diff <remote>/<trunk>..backup/<bottom>_$TS <remote>/<trunk>..<bottom>
```

Expected output: `!` on the amended commit in its own layer, `=` on every other commit, and the fixup commit shown as removed from the top layer because it folded down. Anything else means the fix touched more than intended, so stop and compare against the backup. Give the user the range-diff to post for the reviewer. Header refreshes aren't needed unless the stack's shape changed.

## Trunk moved

When the bottom's `behind_parent` is above 0, or the user asks to update the stack, restack the whole stack onto trunk in one rebase.

1. Show the plan (which layers move, onto which ref) and get approval.
2. `git fetch <remote>`.
3. Back up every layer, as in step 3 above. If a layer has a `worktree`, stop as in step 1.
4. Rebase once from the top: `git rebase --update-refs <remote>/<trunk> "$TOP"`.
5. Push every layer with lease, bottom to top, as in step 4.
6. Refresh every header, using [Split Step 7](split.md#step-7-refresh-every-stack-header-then-mark-the-bottom-ready), because the stack's commits changed.

Run the `git range-diff` verify from step 5 on each moved layer. On a conflict, abort, report the files, and point to the backups.

## Broken chain

`stack.sh` reports `broken_chain` when an open layer targets the head of a merged PR or MR, or a branch that no longer exists. That's the state after a bottom merge. Don't repair it here. Go to the [post-merge sync in Land](land.md#post-merge-sync), which restacks the layer onto trunk and retargets it.

## Per-forge notes for this phase

| Forge | What changes |
|---|---|
| GitHub, native | Make the fixup on the layer being amended, fold it in with a single-layer `GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash <parent>`, then run `gh stack rebase --upstack` instead of the `--update-refs` rebase to carry the layers above it, and `gh stack push` instead of per-branch pushes. For trunk moves, run `gh stack rebase`. `gh stack push` still checks each branch with a lease, but isn't atomic, so rerun it if one branch is rejected. Make the backups first and run the range-diff verify afterward, as above. On a conflict, resolve it, `git add`, and run `gh stack rebase --continue`, or `--abort` to restore every branch |
| GitHub, classic, and GHES | Everything above as written. GHES is always classic |
| GitLab | Classic, as written, with `glab mr update` for any retarget or description change. GitLab retargets only up to 4 open MRs when a target merges. If `gitlab_retarget_cap` is in the warnings, tell the user the rest will be checked and retargeted by hand at land time. If `gitlab_mixed_authors` is in the warnings, tell the user GitLab's stack view stops at the first MR with a different author |
