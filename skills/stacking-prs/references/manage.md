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

### 2. Show the plan, get approval, then commit the fix as a fixup

The fixup commit is a git write, so nothing below runs until the user approves. Set up the names the plan uses, then show the plan.

`LAYERS` is every layer's branch, bottom to top, from the stack JSON. `TOP` is the highest layer that is free in this worktree, which is the last entry unless step 1 left a layer behind:

```bash
LAYERS=()
while IFS= read -r b; do LAYERS+=("$b"); done < <("${CLAUDE_PLUGIN_ROOT}/skills/stacking-prs/scripts/stack.sh" | jq -r '.layers[].branch')
TOP=${LAYERS[${#LAYERS[@]}-1]}   # or the highest free layer
```

Pick the commit the fix belongs to. `git log --oneline <parent>..<layer>` lists the layer's own commits. The plan names that commit, the layers that will move, the backup branches step 3 creates, and the pushes step 4 makes. Get approval before the first git write.

After approval, switch to `TOP`, make the change, and commit it against that commit:

```bash
git switch "$TOP"
git add <files>
git commit --fixup=<sha of the commit being amended>
```

### 3. Back up every layer, then fold the fixup in

`TS` is the timestamp in the backup names. Capture it once here and reuse it in steps 3 and 5. A new shell loses it, so re-derive it from the newest backup name for the bottom layer: `TS=$(git for-each-ref --sort=-refname --count=1 --format='%(refname:strip=2)' "refs/heads/backup/${LAYERS[0]}_*")` then `TS=${TS#backup/${LAYERS[0]}_}`.

```bash
TS=$(date +%Y%m%d_%H%M%S)
for b in "${LAYERS[@]}"; do git branch "backup/${b}_${TS}" "$b"; done

BASE=$(git merge-base "<remote>/<trunk>" "$TOP")
GIT_SEQUENCE_EDITOR="sed -i.bak -E -e '/^(update-ref|u) refs\/heads\/backup\//d'" \
  git rebase -i --autosquash --update-refs "$BASE"
```

The sequence editor runs the rebase without opening an editor, and it deletes every `update-ref refs/heads/backup/` line from the todo list, including the `u refs/heads/backup/` form git writes when `rebase.abbreviateCommands` is set. Without that, `--update-refs` moves the backups along with their layers, which loses the recovery points and makes the step 4 and step 5 comparisons against the backups meaningless. The `sed -i.bak -E` form works on both GNU and BSD sed. The backup names match `extract.sh`. Backups stay local and are never pushed.

On a conflict, run `git rebase --abort`, report the files, point to the backups, and don't auto-resolve.

### 4. Push every branch that moved, with lease

`MOVED` is the layers whose head now differs from their backup, still bottom to top:

```bash
MOVED=()
for b in "${LAYERS[@]}"; do
  if [ "$(git rev-parse "$b")" != "$(git rev-parse "backup/${b}_${TS}")" ]; then MOVED+=("$b"); fi
done
for b in "${MOVED[@]}"; do
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
4. Rebase once from the top, with the same backup-skipping sequence editor as step 3, because a plain `--update-refs` rebase also moves the backups:

   ```bash
   GIT_SEQUENCE_EDITOR="sed -i.bak -E -e '/^(update-ref|u) refs\/heads\/backup\//d'" \
     git rebase -i --update-refs <remote>/<trunk> "$TOP"
   ```
5. Push every layer with lease, bottom to top, as in step 4.
6. Refresh every header, using [Split Step 7](split.md#step-7-refresh-every-stack-header-then-mark-the-bottom-ready), because the stack's commits changed.

Run the `git range-diff` verify from step 5 on each moved layer. On a conflict, abort, report the files, and point to the backups.

## Broken chain

`stack.sh` reports `broken_chain` when an open layer targets the head of a merged PR or MR, or a branch that no longer exists. That's the state after a bottom merge. Don't repair it here. Go to the [post-merge sync in Land](land.md#post-merge-sync), which restacks the layer onto trunk and retargets it.

## Per-forge notes for this phase

| Forge | What changes |
|---|---|
| GitHub, native | Make the fixup on the layer being amended, fold it in with a single-layer `git rebase -i --autosquash <parent>` using step 3's sequence editor, then run `gh stack rebase --upstack` instead of the `--update-refs` rebase to carry the layers above it, and `gh stack push` instead of per-branch pushes. For trunk moves, run `gh stack rebase`. `gh stack push` still checks each branch with a lease, but isn't atomic, so rerun it if one branch is rejected. Make the backups first and run the range-diff verify afterward, as above. On a conflict, resolve it, `git add`, and run `gh stack rebase --continue`, or `--abort` to restore every branch |
| GitHub, classic, and GHES | Everything above as written. GHES is always classic |
| GitLab | Classic, as written, with `glab mr update` for any retarget or description change. GitLab retargets only up to 4 open MRs when a target merges. If `gitlab_retarget_cap` is in the warnings, tell the user the rest will be checked and retargeted by hand at land time. If `gitlab_mixed_authors` is in the warnings, tell the user GitLab's stack view stops at the first MR with a different author |
