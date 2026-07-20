# Pi Merge Resolver Dispatch Template

Use this when the runtime is **pi** (see SKILL.md → Runtime Selection) AND
`git merge --no-ff <task-branch>` reports overlapping-hunk conflicts during
the rolling auto-merge phase of `WORKTREE_PARALLEL` mode.

The merge resolver model is the **pi-dev `codex` alias at `xhigh` thinking** (see
**quirk:pi-dev**) — not a frozen model id; hard-pinning an exact id via `--provider`/`--model` is
the documented exception, not the default. Invoked with full edit/commit tools.

**Triggered when:** `git merge` exits non-zero AND `git status` reports
`Unmerged paths`.

**Not triggered when:** Two tasks merely touched the same file with
non-overlapping hunks (git auto-resolves those).

## Prompt body

The Claude path uses the `Task` tool with a general-purpose subagent (see
`merge-resolver-prompt.md`). The pi path inlines the same instructions.

Build the prompt body with the following placeholders:

- `PARENT_BRANCH`: name of the branch the merge target lives on
- `TASK_BRANCH`: name of the task branch being merged in
- `TASK_TITLE`: incoming task's title
- `TASK_BODY`: incoming task's full body, pasted verbatim
- `ALREADY_MERGED`: list of (task-id, title) tuples already merged in this wave
- `WORKDIR`: absolute path to the worktree where the merge was attempted
- `CONFLICTED_FILES`: output of `git diff --name-only --diff-filter=U`

The prompt MUST instruct the resolver to:

- Inspect conflicts via `git status` and `git diff`.
- Read both sides of each conflict marker, plus surrounding context.
- Decide the correct resolution that satisfies BOTH task bodies' intent.
- Edit files to remove conflict markers; stage with `git add`; complete via
  `git commit --no-edit`.
- Refuse to "accept theirs" / "accept ours" wholesale unless one side is a
  clear strict superset.
- Report `UNRESOLVABLE` (no commit, markers left in place) if the two task
  bodies are semantically incompatible.

End the prompt with: "Output `Status: SUCCESS | UNRESOLVABLE`, `Files resolved`,
`Resolution summary`, `Concerns`."

## Invocation

Write the assembled prompt body to a task/role-keyed file **outside the repository**
(see SKILL.md → Dispatch hygiene — never a generic name inside the worktree, where a
worker could commit or clobber it), e.g. `<scratch>/t<N>-merge-resolver.md`, then:

```bash
cd <worktree>
PROMPT=<scratch>/t<N>-merge-resolver.md
[ -f "$PROMPT" ] || { echo "prompt missing" >&2; exit 1; }
pi-watch --alias codex --thinking xhigh \
  --tools read,bash,edit,write \
  "$(cat "$PROMPT")"
```

`pi-watch` has no `@file` include — the prompt is passed as a positional string, so the file's
contents are inlined via `$(cat ...)`. It resolves the newest authed model in the `codex` alias's
fallback ladder automatically; hard-pinning an exact model id via `--provider`/`--model` is the
documented exception (**quirk:pi-dev**), not the default.

Verify the prompt file exists before dispatching — never fall back to
something like `cat merge-resolver-prompt.md || echo MISSING` that pipes
garbage into a live worker; a bad prompt burns the entire dispatch.

`--tools read,bash,edit,write` is required: the resolver must edit files and
run git commands. (Contrast with the reviewer templates, which use `read,bash` or the
actually-read-only `read,grep,find,ls` — this role needs to mutate files, so it gets `edit,write`
on top.)

For the hardened multi-arg recipe, see **quirk:pi-dev →
reference/print-mode.md#canonical-headless-recipe**.

## Output parsing

The resolver's final message contains a `Status:` line followed by `Files
resolved:`, `Resolution summary:`, and `Concerns:`. Parse pi's stdout for
that structure.

If pi's response is unparseable, apply **quirk:pi-dev → Reviewer JSON parse
fallback** to extract a structured verdict. Treat anything other than a clear
SUCCESS as UNRESOLVABLE — do not silently proceed.

## Handling the result

Same as the Claude path:

- **SUCCESS:** orchestrator continues with the next branch in the rolling
  merge sequence; teardown the merged worktree via `quirk:using-git-worktrees`.
- **UNRESOLVABLE:** orchestrator escalates to the user with the resolver's
  report. Worktree and conflicts are preserved.

## Failure detection

Apply **quirk:pi-dev → Failure detection** rules. On auth/billing failure,
fall back to the Claude merge resolver (`Task` general-purpose) for the rest
of the plan (SKILL.md → Fallback).
