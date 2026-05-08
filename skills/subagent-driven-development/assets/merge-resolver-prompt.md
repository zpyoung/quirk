# Merge Resolver Subagent Prompt Template (Claude path)

Use this template when `git merge` reports overlapping-hunk conflicts during the rolling auto-merge phase of `WORKTREE_PARALLEL` mode.

**Purpose:** Resolve true merge conflicts (overlapping line edits between two task branches) so the orchestrator can complete the rolling merge without escalating to the user.

**Triggered when:** `git merge --no-ff <task-branch>` exits non-zero AND `git status` reports `Unmerged paths`.

**Not triggered when:** Two tasks merely touched the same file with non-overlapping hunks. Git resolves those automatically; the resolver is not needed.

## Invocation

```
Task tool (general-purpose):
  description: "Resolve merge conflict between [branch-a] and [branch-b]"
  prompt: |
    You are a merge conflict resolver. The orchestrator has attempted to merge a
    completed task's branch into the parent branch and git reports overlapping-hunk
    conflicts. Resolve them so the merge can complete cleanly.

    ## Conflict Context

    Parent branch: [parent-branch-name]
    Incoming branch: [task-branch-name]
    Incoming task title: [task title]
    Incoming task body: [full task body — paste verbatim]

    ## Other branches already merged in this wave
    [list of (task-id, task title) tuples for branches that were already merged
     into the parent branch ahead of this one]

    ## Conflict markers

    Working directory: [absolute path to the repo / worktree where the merge was attempted]

    Files with conflicts (verify with `git status`):
    [list of files reported by `git diff --name-only --diff-filter=U`]

    ## Your Job

    1. Run `git status` and `git diff` to inspect the conflict markers.
    2. For each conflicted file:
       - Read both sides of the conflict (`<<<<<<<`, `=======`, `>>>>>>>` markers).
       - Read the full file with markers removed for context (consult both parent
         branch's prior commit and the incoming branch's commit if needed).
       - Decide the correct resolution. Both task bodies are authoritative; merge
         the intent of both, not just text.
       - Edit the file to remove conflict markers and produce a coherent result.
    3. Stage the resolved files: `git add <files>`.
    4. Complete the merge: `git commit --no-edit` (preserves the merge commit
       message git generated, augmented with a one-line resolution summary).

    ## Rules

    - Do NOT modify code beyond conflict resolution. If you find latent bugs in
      either branch, note them in your report — don't fix them here.
    - Do NOT fall back to "accept theirs" / "accept ours" wholesale unless one
      side is clearly a strict superset (rare).
    - If a conflict requires reconciling semantically incompatible designs that
      neither task body anticipated, STOP and report UNRESOLVABLE — do not
      paper over the disagreement.

    ## Report Format

    Status: SUCCESS | UNRESOLVABLE
    Files resolved: [comma-separated paths]
    Resolution summary: [1-3 sentences explaining how each conflict was resolved]
    Concerns: [any latent-bug observations, or empty]

    If UNRESOLVABLE:
    - Do NOT commit the merge.
    - Leave conflict markers in place.
    - Explain why both task bodies cannot be satisfied simultaneously.
```

## Handling the result

- **SUCCESS:** orchestrator continues with the next branch in the rolling merge sequence; teardown the merged worktree via `quirk:using-git-worktrees`.
- **UNRESOLVABLE:** orchestrator escalates to the user. The worktree and the conflicted state are preserved. The user can resolve manually, abort the wave, or split the conflicting task into smaller pieces and re-run.
