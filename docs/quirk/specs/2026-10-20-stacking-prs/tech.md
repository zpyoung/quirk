# Tech spec: `stacking-prs`

**Status**: Reviewed · tier gate fired: touches >3 source files across skill docs, scripts, and tests
**Logic spec**: [logic.md](logic.md)

Paths are relative to the repo root. "The skill dir" means `skills/stacking-prs/`.

## Architecture

Back-links: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

```
skills/stacking-prs/
  SKILL.md                 router: frontmatter, detection step, phase picker, always-on rules
  references/split.md      Split phase (today's Steps 1-8, plus off-ramps, depth, CI preflight, native)
  references/manage.md     Manage phase (fixup flow, trunk moved, broken chain, worktree guard)
  references/land.md       Land phase (pre-merge checks, post-merge sync, loop)
  evals/trigger-evals.json trigger eval set
  scripts/analyze.sh       moved from split-branch; config filename changes only
  scripts/weigh.awk        moved; header comment only
  scripts/extract.sh       moved unchanged
  scripts/stack.sh         NEW: read-only stack detection, emits JSON
  scripts/restack.sh       NEW: one-layer post-merge restack with backup, emits JSON
tests/
  test_stacking_prs_analyze.py   renamed from test_split_branch_analyze.py
  test_stacking_prs_stack.py     NEW
  test_stacking_prs_restack.py   NEW
  test_stacking_prs_skill.py     NEW: structure, links, evals, script paths, evidence strings
  stacking_prs_stubs.py          NEW: shared fake gh/glab writer (test helper module, not a test file)
```

Technologies: Bash 3.2-compatible scripts using `git`, `jq`, BSD-compatible `awk`, `sed`, and `grep -E`,
the same toolset `analyze.sh` uses. `gh` and `glab` are optional at runtime: they're needed only for
the forge reads and writes. pytest drives every script through `subprocess` against throwaway repos.

## Code references

Back-link: [Decisions Locked](logic.md#decisions-locked).

| Path | Action | Anchor |
|---|---|---|
| `skills/split-branch/` | `git mv` to `skills/stacking-prs/` | whole dir |
| `skills/split-branch/SKILL.md` | becomes router + three references; frontmatter `name: stacking-prs` | lines 1-4 frontmatter; Steps 1-8 at 118-274 move to `references/split.md` |
| `skills/split-branch/scripts/analyze.sh:20,26,53` | `split-branch.json` → `stacking-prs.json` | `USER_CFG`, `PROJECT_CFG`, comment |
| `skills/split-branch/scripts/weigh.awk:1-2` | header comment names `stacking-prs` | comment only |
| `tests/test_split_branch_analyze.py` | `git mv` to `tests/test_stacking_prs_analyze.py`; lines 1, 14, 45, 60, 359 | `ANALYZE`, config paths, stderr needle |
| `tests/test_html_app.py:70-95` | pattern to copy for PATH stubs (`fake_env`) | read only |
| `tests/test_filing_github_file.py:23-53` | pattern for Python-shebang argv-logging stubs | read only |
| `tests/test_writing_html_artifacts_skill.py:44-99` | pattern to copy for frontmatter, link, and trigger-eval assertions | read only |
| `skills/writing-html-artifacts/evals/trigger-evals.json` | schema to copy | read only |

## Contracts & interfaces

### `stack.sh`: read-only detection

Back-links: [Data flow](logic.md#data-flow), [Entry and detection](logic.md#entry-and-detection),
SC-1 to SC-4, SC-10, SC-15.

`CONTRACT:`
```
stack.sh [--branch <name>] [--trunk <name>] [--remote <name>]
stack.sh --check-ci <base-branch>...
exit 0: JSON on stdout (detection, or the --check-ci report)
exit 1: usage error, not a git repo, detached HEAD, jq missing; red "Error: ..." on stderr, no stdout
```

Preconditions: run inside a git work tree. `--branch` defaults to the current branch, `--remote` to
`origin`, and `--trunk` to `refs/remotes/<remote>/HEAD`, then local `main`, then `master`. The
fallback order is `analyze.sh`'s `detect_target_branch`, so reuse that logic.

Invariants:
- **It never writes.** No fetch, checkout, branch, push, or forge mutation. Only `gh`/`glab` read
  calls, `gh api` GETs among them.
- **A forge failure degrades, never aborts.** A missing or unauthenticated `gh`/`glab`, or a failing
  chain-listing call, falls back to local mode and adds a `forge_unavailable` warning. A failing
  per-layer enrichment call (GitLab pipeline or approvals) keeps the chain, sets that layer's `ci` or
  `review` to `unknown`, and adds `forge_unavailable`. The script still exits 0.
- Output is deterministic for the same refs and forge responses: layers in bottom-to-top order, and
  warnings in a fixed code order.

Forge resolution, first match wins:
1. The `STACK_FORGE` env var, one of `github|ghes|gitlab|none`. Tests and unusual hosts use it.
2. The `<remote>` URL host. `github.com` → `github`, a host containing `gitlab` → `gitlab`, and anything
   else → `none`.

Chain building (forge modes):
- GitHub/GHES lists open PRs with `gh pr list --state open --limit 200 --json
  number,url,headRefName,baseRefName,isDraft,state,reviewDecision,statusCheckRollup,headRefOid,isCrossRepository,author`.
  It lists merged PRs with `--state merged --limit 100 --json
  number,headRefName,baseRefName,headRefOid,mergeCommit,mergedAt`.
- GitLab lists open MRs with `glab mr list -F json --per-page 100` and merged MRs with `glab mr list -M
  -F json --per-page 100`. The fields are `iid`, `source_branch`, `target_branch`, `draft`, `sha`,
  `author.username`, `web_url`, and `merge_commit_sha`/`squash_commit_sha`. Per open layer, CI comes
  from `glab mr view <iid> -F json` (`head_pipeline.status`), and approval comes from
  `glab api projects/:id/merge_requests/<iid>/approvals` (`approved`). Verify the `:id` placeholder
  against `glab api --help` and document what's used.
- Walk down from `--branch`: follow each open PR's base to the open PR whose head equals it, until
  the base is trunk. Walk up the same way: an open PR whose base equals the current top's head. If two
  open PRs share a base anywhere along the chain, in either direction, add `branched_stack`; on the
  walk up, stop at the fork.
- When `--branch` has no open PR, two cases still read the forge chain before local fallback applies:
  - **Merged anchor.** `--branch` is the head of a merged PR and open PRs target it. The chain is
    the open PRs walked up from that base. `merged_parents[]` names `--branch`, and no layer is
    `is_current`. This is the Land phase's normal post-merge position.
  - **Unpublished bottom.** `--branch` has no PR, but open PRs target it. Layer 1 is `--branch`
    itself, with `state: "local"`, `number: null`, and `base` from local ancestry (the local-mode
    parent rule), followed by the open PRs walked up from it.
- `in_stack` is true when the chain has 2 or more layers. A lone PR targeting trunk, or no PR at all
  with no local chain, is `in_stack: false` (SC-1).

Native detection (GitHub only, never GHES): when the bottom layer has a PR, check
`gh api 'repos/{owner}/{repo}/pulls/<n>' --jq '.stack // empty'`. A non-empty object means
`mode: native` and fills `stack_number`. An absent key or `null` means classic. A failed call
means classic plus a `forge_unavailable` warning. `gh pr list --json` has no stack field, which is
why this needs `gh api`.

`gh_stack_installed`: `gh stack --help` exits 0. `native_available` is true only when
`forge == "github"`, no layer has `isCrossRepository: true`, and `gh_stack_installed` is true. SC-8
and SC-9 branch on it.

Local mode, used when the forge is `none` or unavailable, or when `--branch` has no PR and no PR
chains to it (SC-3):

`PSEUDOCODE (justified, ≤3 lines):` prose is ambiguous about which ancestor is "the parent" when several local branches point into one history.
```
parent(b) = among local branches ≠ b, ≠ trunk, not matching ^backup/, whose tip is a strict ancestor of b's tip and not an ancestor of trunk: the one with the most commits since merge-base(trunk, b); none → trunk
children(b) = branches c with parent(c) == b; walk down via parent, up via children (stop with branched_stack on >1 child)
```

Per-layer derived fields:
- `behind_parent` is `git rev-list --count <head>..<parent-ref>`. `<parent-ref>` is
  `<remote>/<base>` when that ref exists, else local `<base>`, else `null`.
- `worktree` is the path from `git worktree list --porcelain` when the branch is checked out in a
  worktree other than the current one, else `null`.
- `ci` comes from GitHub's `statusCheckRollup`. It is `fail` if any conclusion or state is
  FAILURE/ERROR/CANCELLED/TIMED_OUT/ACTION_REQUIRED, `pending` if any is PENDING/QUEUED/IN_PROGRESS/
  EXPECTED or has an empty conclusion, `none` for an empty rollup, and `pass` otherwise. On GitLab,
  pipeline `success` → `pass`; `failed`/`canceled` → `fail`; `running`/`pending`/`created` → `pending`;
  no pipeline → `none`. It's `unknown` in local mode.
- `review` maps reviewDecision `APPROVED` → `approved`, `CHANGES_REQUESTED` → `changes_requested`,
  `REVIEW_REQUIRED` → `review_required`, and null or empty → `none`. GitLab's `approved: true` →
  `approved`, otherwise `review_required`. It's `unknown` in local mode.

Warnings, emitted in this code order:

| Code | Condition |
|---|---|
| `forge_unavailable` | the forge CLI is missing or unauthenticated, or a call failed |
| `broken_chain` | an open layer's base is the head of a merged PR or MR (SC-4), or is neither trunk nor an existing branch |
| `branched_stack` | two open PRs share a base along the walk |
| `deep_stack` | more than 4 layers (SC-5 at detection time) |
| `gitlab_retarget_cap` | forge `gitlab` and more than 4 open layers (SC-15) |
| `gitlab_mixed_authors` | forge `gitlab` and the layers have more than one author (SC-15) |
| `cross_fork` | any layer has `isCrossRepository: true` (SC-9) |
| `ci_filter` | mode is not `native`, forge is `github`/`ghes`, and a workflow would skip a non-trunk base (SC-10) |
| `layer_in_other_worktree` | any layer has a non-null `worktree` (SC-12) |

CI-filter scan (`ci_filter`, and the `--check-ci` mode): for each `.github/workflows/*.yml|*.yaml`,
find a `pull_request` or `pull_request_target` trigger with a `branches:` or `branches-ignore:` list,
in either flow (`[a, b]`) or block (`- a`) style. A base is skipped when a `branches` list matches
none of its entries, or when a `branches-ignore` entry matches it. Patterns match as bash globs,
with `**` treated as `*`. This is a line-oriented awk heuristic, not a YAML parser. It reads only
keys nested under a top-level `on:` key. A trigger written in a shape it can't read, including quoted
entries it can't split safely, produces no warning. Never guess a positive. `--check-ci <base>...` runs only
this scan for the given planned bases. The Split phase calls it before push, because no PRs exist yet
then.

### `restack.sh`: replay one layer onto a new base

Back-links: [Data flow](logic.md#data-flow), SC-13, SC-18, SC-20.

`CONTRACT:`
```
restack.sh --branch <b> --onto <base-branch> --old-tip <sha>
           [--onto-ref <ref>] [--remote <name>] [--pr <number>] [--forge github|gitlab] [--no-push]
exit 0: rebased (and pushed / retargeted when asked); JSON on stdout
exit 1: usage or precondition failure; JSON success:false on stdout, red "Error:" on stderr
exit 2: rebase conflict; rebase aborted, branch restored to its pre-run head; JSON lists conflicted files
exit 3: <b> is checked out in another worktree; nothing changed
exit 4: push rejected (lease or includes check); local rebase kept, backup kept
exit 5: retarget failed after a successful push; JSON carries the PR URL for a manual retarget
```

Behavior, in order:
1. Preconditions: the tree is clean (staged and unstaged), `<b>` exists locally, `<old-tip>` resolves
   to a commit that is an ancestor of `<b>`, and `--onto-ref` resolves. `--onto-ref` defaults to
   `<remote>/<onto>` when that ref exists, else `<onto>`. A failed check exits 1. If `<b>` is
   checked out in a different worktree, it exits 3.
2. Backup: `git branch backup/<b>_<YYYYMMDD_HHMMSS>` at `<b>`'s current head. This is the exact
   format of `extract.sh:106-117`, and the branch is never pushed.
3. `git rebase --onto <onto-ref> <old-tip> <b>`. On conflict, capture
   `git diff --name-only --diff-filter=U`, run `git rebase --abort`, return to the branch that was
   checked out before the run, and exit 2.
4. Verify: `<onto-ref>` is an ancestor of the new head, and the number of commits replayed equals
   `git rev-list --count <old-tip>..<old-head>`. A mismatch exits 1 with the backup named, and the
   branch is left rebased for the human to inspect.
5. Push, unless `--no-push`: `git push --force-with-lease --force-if-includes <remote> <b>`. A
   rejection exits 4.
6. Retarget when `--pr` is given. `--forge` defaults to the same resolution `stack.sh` uses
   (`STACK_FORGE`, then the remote host). With `--pr` and a resolved forge of `none`, it exits 1 before
   step 2. Retarget only when the PR's current base isn't `<onto>`. GitHub uses
   `gh pr edit <n> --base <onto>`, and GitLab uses `glab mr update <n> --target-branch <onto>`. A
   failure exits 5.

This contract settles the deferred tech-spec item on old-parent-tip and squash detection: `--old-tip`
is the merged parent's head SHA. The forge keeps it, as GitHub's `headRefOid` and GitLab's `sha`, and
`stack.sh` reports it in `merged_parents[]`. Squash detection isn't needed, because `--onto` with the
old tip replays only the child's own commits under squash, rebase, and merge-commit merges alike. For
layers above the first, the Land phase passes the restacked parent's `old_head` from the previous
`restack.sh` run as `--old-tip`, and the parent branch as `--onto`.

### `analyze.sh` and `extract.sh`

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals). `analyze.sh`'s contract is unchanged
except the config filename, which becomes `~/.quirk/stacking-prs.json` and
`<repo>/.quirk/stacking-prs.json`, and every error message that names it. There's no fallback to
`split-branch.json`. `extract.sh` is unchanged.

### Skill documents

Back-links: [Conceptual model](logic.md#conceptual-model), [Decisions Locked](logic.md#decisions-locked).

- `SKILL.md` frontmatter has exactly `name: stacking-prs` and a `description` that starts with
  "Use when" and is 50-1024 characters. The description must cover splitting a large branch,
  managing or updating a stack (review feedback on a lower PR, trunk moved), and landing or merging a
  stack.
- `SKILL.md` body: an announce line, then "Step 0: detect" running `stack.sh` and printing the stack
  map, then the phase picker (SC-1, SC-2, SC-3), the always-on rules from the logic spec's Conceptual
  model verbatim in substance, and links `[split](references/split.md)`,
  `[manage](references/manage.md)`, and `[land](references/land.md)`. Keep the body under 150 lines.
- Script paths in every skill doc use `${CLAUDE_PLUGIN_ROOT}/skills/stacking-prs/scripts/<name>`.
- `references/split.md` carries today's Targets and Weighting, Strategies, Process Steps 1-8, Quick
  Reference, Common Mistakes, and Red Flags. It adds:
  - the off-ramp check right after the plan's size is known (SC-5, SC-6, SC-7)
  - a `stack.sh --check-ci` preflight before push on GitHub (SC-10)
  - native registration after PR creation, with `gh stack link <bottom> ... <top>`, when
    `native_available` is true (SC-8)
  - the one-line tip for when it's false on github.com (SC-9)
  - the native two-section header vs the classic four-section header (SC-8, SC-9)
  - its own per-forge block
  - for "Split this layer further" on a non-top layer: after the split, restack every layer above it
    bottom-up with `restack.sh --onto <its parent> --old-tip <parent's pre-split head>`, then refresh
    every header
- `references/manage.md`:
  - the fixup → backups → `git rebase -i --autosquash --update-refs` → per-branch lease push → verify
    sequence (SC-11). The sequence editor runs non-interactively and deletes every
    `update-ref refs/heads/backup/` line from the todo list, so `--update-refs` never moves a backup.
    Verify means each layer's own diff changed only where the fix landed, shown to the user with
    `git range-diff <backup-parent>..<backup> <parent>..<branch>` per moved branch
  - the worktree stop (SC-12). The "rebase that layer separately afterward" option runs
    `restack.sh --no-push` from inside that worktree, where the branch is current so exit 3 doesn't
    apply, with `--onto` the rebased parent and `--old-tip` the parent's pre-rebase head from its
    backup. Then the skill pushes with lease
  - trunk moved: `git fetch`, backups of every layer, one `--update-refs` rebase from the top onto
    `<remote>/<trunk>`, a lease push per layer, then the header refresh (SC-13)
  - the native path through `gh stack rebase` and `gh stack push` (SC-14)
  - broken-chain repair routed to `land.md`'s post-merge sync (SC-4)
  - a per-forge block covering the GitLab warnings (SC-15)
- `references/land.md`:
  - pre-merge checks on the bottom layer from `stack.sh` JSON: base is trunk, `ci == pass`,
    `review == approved`, `behind_parent == 0`, and not draft (SC-16, SC-17)
  - the no-merge rule with the exact commands it never runs (SC-17, SC-21)
  - the classic post-merge loop: `git fetch`, then re-run `stack.sh`, then show the restack plan,
    then `restack.sh` per layer bottom-up, then refresh headers, then `gh pr ready` on the new bottom,
    then `git branch -D` on the merged local branch (SC-18)
  - native `gh stack sync --prune` (SC-19)
  - GitLab retarget verification (SC-20)
- Evidence edits: the old "Core principle" sentence and the Sources line are replaced. The new text
  cites LinearB 2026 (elite <100 lines at p75), Google's ~100-line guidance, Kudrjavets et al. 2022
  (size doesn't relate to time-to-merge), and SmartBear/Cisco's under-400 guidance without the
  "70-90%" figure. It labels the 0.5× test weight as a configurable choice with no study behind it.
  These exact strings must disappear: `LinearB 2025`, `<219`, `70-90%`.

## Data models / schemas

Back-links: [Data flow](logic.md#data-flow), [Success criteria](logic.md#success-criteria).

`SCHEMA:` `stack.sh` detection output
```json
{
  "schema": 1,
  "forge": "github | ghes | gitlab | none",
  "mode": "native | classic | local",
  "in_stack": true,
  "trunk": "main",
  "remote": "origin",
  "current_branch": "auth-api",
  "gh_stack_installed": false,
  "native_available": false,
  "stack_number": null,
  "layers": [
    {
      "position": 1,
      "branch": "auth-schema",
      "base": "main",
      "number": 41,
      "url": "https://…/pull/41",
      "state": "open | draft | local",
      "head_sha": "…",
      "ci": "pass | fail | pending | none | unknown",
      "review": "approved | changes_requested | review_required | none | unknown",
      "behind_parent": 0,
      "worktree": null,
      "is_current": false,
      "author": "octocat"
    }
  ],
  "merged_parents": [
    { "branch": "auth-old", "number": 40, "head_sha": "…", "merge_sha": "…", "child": "auth-schema" }
  ],
  "warnings": [ { "code": "ci_filter", "message": "…", "branches": ["auth-api"], "files": [".github/workflows/test.yml"] } ]
}
```
`position` is 1-based with 1 at the bottom. `number`, `url`, and `author` are `null` in local
mode. `merged_parents[]` lists merged PRs or MRs whose head is the base of an open layer. `files` is
present only on `ci_filter`.

`SCHEMA:` `stack.sh --check-ci` output
```json
{ "schema": 1, "skipped": [ { "base": "auth-schema", "files": [".github/workflows/test.yml"] } ] }
```

`SCHEMA:` `restack.sh` output
```json
{ "success": true, "branch": "auth-api", "onto": "main", "onto_ref": "origin/main",
  "old_tip": "…", "old_head": "…", "new_head": "…", "backup_branch": "backup/auth-api_20261020_141500",
  "commits_replayed": 2, "pushed": true, "retargeted": true, "pr_url": "…",
  "conflicted_files": [], "message": "…" }
```

`SCHEMA:` `evals/trigger-evals.json`, the same schema as writing-html-artifacts
```json
{ "skill_name": "stacking-prs", "queries": [ { "query": "…", "should_trigger": true } ] }
```

## DO-NOT-CHANGE fences

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

- **`analyze.sh` weighting and config logic, and all of `weigh.awk` except its header comment.** They
  landed in 66eccfc with 41 passing tests. This work is a rename, and any behavior change would need
  its own review.
- **`extract.sh`.** The Split flow depends on its backup name and JSON fields exactly as they are,
  and `restack.sh` copies its backup format.
- **The split-flow guidance in `references/split.md`: weights tables, Strategies 0-4, Steps 1-8,
  Quick Reference, and Common Mistakes.** Move it verbatim except for the evidence edits, the path
  edits, the additions listed under Skill documents, and adding `--force-if-includes` to every
  `--force-with-lease` push (the router's force-push rule overrides the fence there). It's approved, tested behavior, and the logic
  spec changes only what it lists.
- **`README.md:9` skill count.** A rename keeps it at 27. Bumping it breaks
  `tests/test_adhd_skill.py:157-164` and `tests/test_simplifying_safely_skill.py:86-95`.
- **Version files and `CHANGELOG.md`.** CI stamps them from the PR (`bin/release.py:67-86`). The
  BREAKING note comes from the PR's `breaking` label and its `## Changelog` section, not from a hand
  edit. The implementing PR must carry both, and the section must name the rename and point users at
  `quirk:stacking-prs` and `.quirk/stacking-prs.json`.

## Always / Ask / Never

Back-links: [Conceptual model](logic.md#conceptual-model), [Key decisions and rationale](logic.md#key-decisions-and-rationale).

Always:
- Keep scripts Bash 3.2-compatible: no `mapfile`, no associative arrays, and `"${arr[@]:-}"` under
  `set -u`.
- Use `set -euo pipefail`, and resolve `SCRIPT_DIR` the way `analyze.sh:12` does.
- Build JSON with `jq`, never by string concatenation of unescaped values. Check `command -v jq` up
  front and exit 1 with a clear error.
- Pass data between functions through variables or `mktemp` files cleaned by a trap, never fixed
  `/tmp/` paths (the `extract.sh:194-236` weakness).
- Send progress and git noise to stderr and keep stdout to the single JSON document.

Ask:
- If `stack.sh` or `restack.sh` needs a tool beyond git, jq, awk, sed, grep, gh, and glab, stop and
  surface it before using it.
- If a glab placeholder or JSON field doesn't behave as described above, surface it rather than
  inventing a substitute.

Never:
- Call `gh pr merge`, `gh stack merge`, or `glab mr merge` anywhere in scripts or skill docs, except
  in sentences forbidding them.
- Use `git push --force` without `--force-with-lease --force-if-includes`.
- Fetch, push, or write any ref from `stack.sh`.
- Make a test reach the network or a real forge. Every `gh`/`glab` call in tests goes to a stub.

## Cross-cutting

Back-link: [Conceptual model](logic.md#conceptual-model).

- Safety: every history rewrite (`restack.sh`, and the Manage phase's documented rebases) makes a
  `backup/<branch>_<timestamp>` branch first. Backups stay local and are never auto-deleted.
- Failure modes: a forge outage degrades `stack.sh` to local mode with a warning. `restack.sh`
  leaves the branch either at its old head (exit 2/3) or rebased with a backup (exit 4/5), never
  half-written.
- Migration: none. The config path change has no fallback, because the config is unreleased.

## Testing strategy

Back-link: [Success criteria](logic.md#success-criteria).

- **Stubs** (settles the deferred `gh`/`glab` stubbing item). `tests/stacking_prs_stubs.py` writes
  `gh` and `glab` executables into `tmp_path/bin` as Python-shebang scripts, following
  `tests/test_filing_github_file.py:23-53`. Each one reads a JSON fixture named by `FAKE_FORGE_FIXTURE`.
  The fixture maps an argv prefix to `{stdout, exit}`, and the longest matching prefix wins. Each
  appends its argv as one JSON line to `FAKE_FORGE_LOG`, and an unmatched argv exits 99 so a missed
  stub fails loudly. Tests prepend `tmp_path/bin` to `PATH`, following
  `tests/full_code_review/test_deep_sandbox.py:273-278`, so git and jq stay reachable, and they set a
  private `HOME`. A test for "gh not installed" uses a stub dir without `gh` and a `PATH` holding only
  symlinked `git` and `jq`.
- **Remotes.** Restack tests use a local bare repo (`git init --bare`) as `origin`, so pushes really
  run and `--force-with-lease` really checks.
- `tests/test_stacking_prs_analyze.py`: all 41 existing cases pass after the rename, with the
  `stacking-prs.json` paths and stderr needle.
- `tests/test_stacking_prs_stack.py` must cover:
  - SC-1: an unstacked branch, and a lone PR, report `in_stack: false`
  - SC-2: a 3-layer classic GitHub chain in bottom-to-top order, with each mapped ci/review/state
    value
  - SC-3: local-mode ancestry, `backup/*` branches ignored
  - native detection from the `pulls/<n>` stack key, both present and absent, and a failing call
  - `gh_stack_installed` / `native_available`, including `cross_fork`
  - SC-4: `broken_chain` and `merged_parents[].head_sha`
  - `branched_stack`
  - SC-5: `deep_stack` at 5 layers and not at 4
  - SC-15: GitLab chain, `gitlab_retarget_cap` at 5 open MRs, and `gitlab_mixed_authors`
  - SC-10: `ci_filter` for flow and block styles, `branches-ignore`, a glob, an unreadable shape
    giving no warning, and `--check-ci`
  - SC-12: `layer_in_other_worktree`
  - forge unavailable → local plus a warning, still exit 0
  - stack.sh never writes: refs and remote-tracking refs are unchanged before and after, and the
    stub log has no mutating subcommand
- `tests/test_stacking_prs_restack.py` must cover:
  - SC-18: squash-merged parent → child replays only its own commits, pushed, retargeted (stub log
    shows `pr edit <n> --base main`)
  - a merge-commit parent
  - the middle-layer chaining case (`--onto` a parent branch with `--old-tip` = that parent's
    `old_head`)
  - the backup name format
  - conflict → exit 2 with the branch at its old head and the files listed
  - a branch checked out in another worktree → exit 3
  - lease rejection after the remote moved → exit 4
  - retarget failure → exit 5
  - a dirty tree → exit 1
  - `--no-push`
  - the GitLab retarget command shape
- `tests/test_stacking_prs_skill.py` must check:
  - frontmatter has exactly `name` and `description`, name equals the dir name, and the description
    starts with "Use when" at 50-1024 characters
  - every relative link in `SKILL.md` and `references/*.md` resolves
  - `SKILL.md` links all three references
  - every `${CLAUDE_PLUGIN_ROOT}/skills/...` path in the skill's docs exists
  - no file under the skill dir, or the analyze test, contains `split-branch`
  - `LinearB 2025`, `<219`, and `70-90%` are absent, and `Kudrjavets` and `LinearB 2026` are present
  - a never-merge sentence is present in `references/land.md`, and no doc runs a merge command
    outside it
  - trigger evals are balanced: at least 12 true and 12 false, unique, exactly the keys
    `query`/`should_trigger`, and `skill_name == "stacking-prs"`
- Scenario runs: one fresh agent per phase follows only the skill docs against a local fixture repo
  with a bare `origin` and stubbed forge, and reaches the scenario's Data after. Split runs SC-6 then
  SC-9, Manage runs SC-11, and Land runs SC-18. Record each run's transcript summary in the run
  journal. These aren't pytest.
- Acceptance bar: `python3 -m pytest -q tests/test_stacking_prs_*.py` passes, and the full suite stays
  green.

## Non-goals

Everything in the logic spec's [Scope and non-goals](logic.md#scope-and-non-goals) non-goal list.
Beyond that:
- No YAML library for the CI scan.
- No `gh stack view --json` parsing. It needs local gh-stack tracking state, so `stack.sh` reads the
  REST stack key instead.
- No GitLab CI-rules scan.
- No automated runner for the trigger evals. Their shape is checked by pytest and they're run by hand.
