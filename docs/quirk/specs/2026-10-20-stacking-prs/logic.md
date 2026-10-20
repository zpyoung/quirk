# Logic spec: `stacking-prs`, a full-lifecycle stacked-PR skill

**Status**: Approved

`quirk:split-branch` is good at cutting one big branch into a stack of PRs. After it creates the PRs it
stops. The research in
[the splitting-and-stacking exploration](../../explorations/2026-10-19-splitting-and-stacking-prs.md)
found that most stack pain starts after creation. The bottom PR merges and the layers above need surgery,
reviewers ask for changes on PR 2 of 4, trunk moves, and CI path filters quietly skip every layer above
the bottom. GitHub's native stacked PRs went GA on 2026-10-06 and take over part of that work, but only
when the stack is registered with them.

This rework renames the skill to `stacking-prs` and covers the whole life of a stack: **Split**,
**Manage**, and **Land**. It works on any stack, including ones the skill didn't create. It also fixes the
size evidence the skill cites, offers a way out when stacking is the wrong tool, and warns before CI
filters skip layers.

## Conceptual model

The skill is a router plus three phases. The router decides which phase applies and holds the rules
every phase obeys. Each phase lives in its own reference file, so an agent loads only the phase it's in.

| Part | What it does | When it runs |
|---|---|---|
| Router (`SKILL.md`) | Detects whether the branch is in a stack, shows the stack, picks or asks for a phase, and holds the always-on rules | Every invocation |
| Split (`references/split.md`) | Today's split flow, plus off-ramps, a depth warning, the CI-filter preflight, and native registration | The branch isn't in a stack yet, or the user wants one layer split further |
| Manage (`references/manage.md`) | Feedback on a lower layer, trunk moved, broken-chain repair | The stack exists and nothing has merged out from under it |
| Land (`references/land.md`) | Pre-merge checks on the bottom PR, then post-merge sync of the rest | The user is ready to merge |

Forge differences (GitHub native, GitHub classic, GitLab) are written inline in each phase file as a short
per-forge block, not in a separate file. The reader of a phase needs them at the step they apply to.

A stack has one of three **modes**:

- **Native**: a GitHub stack registered with GitHub's stacked-PRs feature. GitHub draws the stack map,
  rebases after each merge, and runs CI against the stack base.
- **Classic**: PRs or MRs whose bases chain one to the next, with no native registration. The skill
  does the post-merge surgery itself. Every GitLab stack is classic.
- **Local**: the branches chain locally but nothing is pushed yet. The skill reads the stack from git
  ancestry.

The router enforces these rules in every phase:

- No git write happens before the user approves the plan for that operation.
- Every history rewrite makes a backup branch first.
- Every force-push uses `--force-with-lease` with `--force-if-includes`, never a bare `--force`.
- The skill never merges a PR or MR. The user presses merge, and the skill checks before and syncs after.
- Non-bottom PRs stay in draft. Only the current bottom is marked ready.

## Data flow

The skill gets a picture of the stack first and acts on it second.

**Detection.** A new script, `stack.sh`, reads the open PRs (through `gh`) or MRs (through `glab`) for
the repo and chains them from trunk upward by matching each one's base to another one's head. Before
anything is pushed it falls back to local git ancestry. It reports the forge, the mode, the trunk, and
one entry per layer. Each layer entry gives the branch, the PR or MR number, its base, whether it's open,
draft, or merged, its CI result, whether it's approved, whether it's behind its parent, and whether the
branch is checked out in another worktree. The script persists nothing. The forge is the source of
truth, so a stack built by hand or by another tool reads the same way.

The script also reports warnings the phases act on:

- a workflow filter that will skip CI on layers above the bottom (classic GitHub only)
- a stack deeper than 4 layers
- a GitLab stack deeper than 4 MRs, which is past GitLab's automatic retarget limit
- a broken chain, where a PR's base is neither trunk nor another open PR's head

**Splitting.** The existing `analyze.sh` and `extract.sh` keep doing the weighing and the extraction, and
move with the rename. After the PRs exist, a native-capable GitHub repo with `gh stack` installed gets
the stack registered with `gh stack link`.

**Post-merge surgery.** A new script, `restack.sh`, handles classic stacks after the bottom merges. For
each remaining layer it makes a backup, replays only that layer's own commits onto the new base with
`git rebase --onto <new base> <old parent tip>`, force-pushes with lease, retargets the PR if the forge
didn't, and checks the result. That works the same whether the parent was squashed, rebased, or merged
with a merge commit. Native stacks don't use it. They go through `gh stack sync --prune` and
`gh stack rebase`, because GitHub already rebases server-side.

**Mid-stack feedback** is a documented sequence rather than a script, because the agent has to decide
which commit each fix belongs to. The sequence is `git commit --fixup`, then
`git rebase -i --autosquash --update-refs`, then a lease-protected push of every branch that moved, then
a verify step.

## Key decisions and rationale

- **Forge-first detection.** The forge already knows how the PRs chain, and reading it means the skill
  works on stacks it didn't create. Storing stack metadata in git config was the alternative. It would
  go stale the moment someone retargets a PR in the UI.
- **The user merges.** Merging is outward-facing and hard to undo, and on a classic stack a mid-stack
  merge lands a PR into its parent branch instead of trunk. The skill makes merging safe and leaves the
  button to the user.
- **Native when available, classic otherwise.** Native stacks fix the CI-filter problem, keep approvals
  through "Rebase stack", and do the post-merge rebase for us. The skill uses them whenever it can. It
  doesn't make installing `gh stack` a requirement, so a repo without it still gets a working classic
  stack plus a one-line tip.
- **Off-ramps are conditional.** Stacking is the default because that's why the user invoked the skill.
  The alternatives come up only where the research says they're likely better: deep stacks and small
  diffs.
- **Weak evidence is labelled weak.** Kudrjavets et al. found PR size doesn't relate to time-to-merge
  across 845K PRs. The skill keeps its size targets as a review-load heuristic and stops implying they
  have firmer backing than they do.
- **Clean rename.** There's no `/split-branch` stub, and the release changelog calls the rename out as
  breaking. The config file has no fallback to the old path because the config arrived in 66eccfc and
  hasn't shipped in a release yet.

## Behavior and scenarios

### Entry and detection

1. **SC-1: an unstacked branch goes to Split**
   - **Given** a branch with one open PR targeting trunk, or no PR at all, and no stacked branches
     around it
   - **When** the skill is invoked
   - **Then** it reports "not in a stack" and starts the Split phase without asking which phase
2. **SC-2: a branch already in a stack shows the stack and asks**
   - **Given** a branch whose PR is one layer of an open stack, created by this skill or not
   - **When** the skill is invoked
   - **Then** it prints the stack map, bottom first, with each layer's PR, state, CI, and approval.
     It then asks which phase to run: Manage, Land, or Split this layer further
   - **Data before:** **PR 41** `auth-schema` → main, open, ready, CI ✓, approved; **PR 42**
     `auth-api` → `auth-schema`, draft, CI ✓, not approved; **PR 43** `auth-ui` → `auth-api`, draft,
     CI ✗, not approved; current branch `auth-api`
   - **Walkthrough:**
     1. The skill runs stack detection and gets mode classic, trunk main, 3 layers
     2. The skill prints the map and marks `auth-api` as the current layer
     3. The skill asks: Manage, Land, or Split this layer
   - **Data after:** ✓ no git or forge state changed; the user's phase choice is pending
3. **SC-3: an unpushed chain reads from local ancestry**
   - **Given** three local branches that each start at the previous one's tip, none pushed
   - **When** the skill is invoked on the top branch
   - **Then** it reports mode local with three layers and offers Manage or Split. Land isn't offered,
     because nothing can be merged yet
4. **SC-4: a broken chain is reported and repair is offered**
   - **Given** a classic stack where the bottom PR merged but the next PR still targets the merged
     branch
   - **When** the skill is invoked
   - **Then** it flags the broken link and offers the Land phase's post-merge sync to repair it

### Split

5. **SC-5: a deep plan warns and offers off-ramps**
   - **Given** a split plan with more than 4 layers
   - **When** the skill presents the plan
   - **Then** it warns that practitioners report 3-4 layers as the practical limit. Alongside the stack
     plan it offers two alternatives: one PR with atomic commits reviewed commit by commit, or
     sequential PRs to trunk behind a feature flag. The stack plan stays the default, and the user picks
6. **SC-6: a small diff offers the single-PR off-ramp**
   - **Given** a diff whose weighted size is under 2× the target
   - **When** the skill presents the plan
   - **Then** it says a single PR is likely easier and offers the same two alternatives as SC-5
   - **Data before:** **Branch** `billing-retry`: 480* weighted lines; target 300 weighted lines
   - **Walkthrough:**
     1. The skill computes 2 × 300 = 600
     2. 480 < 600, so the off-ramp applies
   - **Data after:** ✓ the plan shows a 2-layer stack plus "one PR with atomic commits" and "trunk
     plus flag" as alternatives; no branches created yet
7. **SC-7: a plan between the thresholds shows no off-ramps**
   - **Given** a plan of 2-4 layers for a diff of at least 2× target
   - **When** the skill presents the plan
   - **Then** it shows the stack plan only
8. **SC-8: a native-capable repo registers the stack**
   - **Given** a github.com repo, a same-repo stack (no forks), and the `gh stack` extension installed
   - **When** the Split phase has pushed the branches and created the PRs
   - **Then** it registers them bottom to top with `gh stack link`, and each PR description carries
     only the Feature Goal and Intentionally Missing sections
   - **PR description:**

     ```markdown
     ## Feature Goal
     Users can sign in with a passkey.

     ## Intentionally Missing
     The sign-in screen lands in the next PR in the stack.
     ```
9. **SC-9: a repo without native support gets a classic stack and a tip**
   - **Given** a github.com repo without `gh stack` installed, or a GHES repo, or a cross-fork stack
   - **When** the Split phase creates the PRs
   - **Then** it builds a classic stack with the full four-section header (Stack Position, Feature
     Goal, Review Order, Intentionally Missing). On github.com without the extension it adds one line:
     "Tip: `gh extension install github/gh-stack` lets GitHub manage this stack natively."
10. **SC-10: a CI filter that would skip layers is flagged before push**
    - **Given** a classic GitHub stack about to be pushed, and a workflow triggered on `pull_request`
      with a `branches: [main]` filter
    - **When** the Split phase runs its preflight
    - **Then** it warns that this workflow won't run on any layer above the bottom, names the workflow
      file, and gives two fixes: register the stack natively, or widen the filter. It doesn't edit
      workflow files, and the user decides whether to continue
    - **Data before:** **Workflow** `.github/workflows/test.yml`: on `pull_request`, branches main;
      **Plan**: 3 layers, classic
    - **Walkthrough:**
      1. The skill reads the workflow triggers
      2. Layers 2 and 3 will target `auth-schema` and `auth-api`, which the filter doesn't match
    - **Data after:** ✗ CI won't run on layers 2-3 under `test.yml`; the push waits for the user's
      choice

### Manage

11. **SC-11: feedback on a lower layer goes in as a fixup**
    - **Given** a 3-layer classic stack and a review comment on PR 2
    - **When** the user asks the skill to address it
    - **Then** the skill makes the fix as a fixup commit targeting the PR 2 commit it amends, folds it
      in with `git rebase -i --autosquash --update-refs` from the top branch, and backs up the branches
      first. It pushes every moved branch with lease. It then verifies that each layer's diff against
      its parent changed only where the fix landed, and gives the user a `git range-diff` for the
      reviewer
    - **Data before:** **PR 42** `auth-api`: commits a1, a2; **PR 43** `auth-ui`: commits u1 on top
      of a2
    - **Walkthrough:**
      1. The agent commits the fix as "fixup! a2"
      2. The rebase folds the fixup into a2 to make a2′, then replays u1 to make u1′. `--update-refs`
         moves both branch pointers
      3. The skill pushes `auth-api` and `auth-ui` with lease
      4. The verify step shows a range-diff: PR 42 changed in a2 only, and PR 43's own diff is unchanged
    - **Data after:** **PR 42** `auth-api`: ✓ a1, a2′; **PR 43** `auth-ui`: ✓ u1′ on a2′; backups
      kept for both branches
12. **SC-12: a layer checked out in another worktree stops the rebase**
    - **Given** the same stack, with `auth-ui` checked out in another worktree
    - **When** the skill is about to run the `--update-refs` rebase
    - **Then** it stops before rewriting anything and names the worktree, because `--update-refs` skips
      branches checked out elsewhere and would leave that layer behind. It asks the user to free that
      worktree or to have the skill rebase that layer separately afterward
13. **SC-13: trunk moved, so the stack restacks onto it**
    - **Given** a classic stack whose bottom is behind trunk
    - **When** the user asks to update the stack
    - **Then** the skill backs up every layer, rebases the whole stack onto trunk in one
      `--update-refs` rebase from the top, pushes every layer with lease, and refreshes the headers
14. **SC-14: a native stack uses `gh stack` for the same jobs**
    - **Given** a native stack and either a review fix or a moved trunk
    - **When** the Manage phase runs
    - **Then** it does the fixup the same way, then uses `gh stack rebase` and `gh stack push` instead
      of the raw rebase and per-branch pushes. It still makes backups first and still runs the verify
      step
15. **SC-15: GitLab warns past the retarget limit**
    - **Given** a GitLab stack of 6 MRs
    - **When** detection runs
    - **Then** the skill warns that GitLab retargets only up to 4 open MRs when their target merges, so
      it will check and retarget the rest by hand at land time. If the MRs have different authors, it
      also warns that GitLab's stack view stops at the first MR with a different author

### Land

16. **SC-16: the bottom isn't ready, so the skill reports why**
    - **Given** a stack whose bottom PR has failing CI or lacks the required approval
    - **When** the user starts the Land phase
    - **Then** the skill lists each blocker against the bottom PR and stops. It doesn't merge, and it
      doesn't touch layers above
17. **SC-17: the bottom is ready, so the user merges**
    - **Given** a bottom PR that targets trunk, has CI passing, has the required approval, and isn't
      behind trunk
    - **When** the Land phase runs its checks
    - **Then** it tells the user the bottom PR is ready to merge and waits for them to say it's merged.
      It never runs `gh pr merge`, `gh stack merge`, or `glab mr merge`
18. **SC-18: after a classic merge, the rest of the stack is rebuilt**
    - **Given** a 3-layer classic GitHub stack whose bottom PR the user just squash-merged
    - **When** the user says it's merged
    - **Then** the skill re-reads the stack, confirms the merge, and shows the restack plan. Once the
      user approves it, `restack.sh` takes each remaining layer in order, bottom first: backup, replay
      that layer's own commits onto its new base (trunk for the next layer, the rebuilt parent for the
      rest), push with lease, and retarget the next layer's PR to trunk. It refreshes every header,
      marks the new bottom ready while the rest stay draft, and deletes the merged local branch. Then
      it offers to run Land again
    - **Data before:** **PR 41** `auth-schema` → main: merged as squash commit S; **PR 42** `auth-api`
      → `auth-schema`, draft: own commits a1, a2 on old tip s3; **PR 43** `auth-ui` → `auth-api`,
      draft: own commit u1
    - **Walkthrough:**
      1. The skill backs up `auth-api` and `auth-ui`
      2. `git rebase --onto main s3 auth-api` replays a1, a2 onto S to make a1′, a2′
      3. `auth-ui` is replayed onto a2′ to make u1′
      4. Both branches are pushed with lease, and PR 42 is retargeted to main
      5. Headers are refreshed, and PR 42 is marked ready
    - **Data after:** **PR 42** `auth-api` → ✓ main, ready, own commits a1′, a2′; **PR 43** `auth-ui`
      → `auth-api`, ✓ draft, u1′; ✓ local `auth-schema` deleted; backups kept
19. **SC-19: after a native merge, GitHub's sync does the rebuild**
    - **Given** a native stack whose bottom PR the user just merged
    - **When** the user says it's merged
    - **Then** the skill runs `gh stack sync --prune`, confirms the next PR now targets trunk, refreshes
      the two header sections, and offers to run Land again
20. **SC-20: GitLab retargets are verified**
    - **Given** a GitLab stack of 6 MRs whose bottom the user just merged
    - **When** the post-merge sync runs
    - **Then** the skill restacks the next MR like SC-18. It checks which open MRs GitLab retargeted
      and retargets any it didn't with `glab mr update --target-branch`
21. **SC-21: a request to merge mid-stack is declined**
    - **Given** any stack
    - **When** the user asks the skill to merge PR 2 before PR 1
    - **Then** the skill doesn't merge and explains why. On a native stack that merge lands every layer
      below it. On a classic stack it lands PR 2 into PR 1's branch instead of trunk. It offers to run
      Land on the bottom instead

## Scope and non-goals

In scope:

- Rename `skills/split-branch` to `skills/stacking-prs`, along with its scripts, its tests, and the
  config path, which becomes `.quirk/stacking-prs.json` at user and repo level. The rename is called
  out as breaking in the release changelog entry that `releasing-quirk` stamps.
- The router, the three phase files, and the two new scripts, `stack.sh` and `restack.sh`.
- Native registration with `gh stack link`, and the trimmed native header.
- The depth warning and the conditional off-ramps.
- The CI-filter preflight for classic GitHub stacks.
- GitLab stacked-MR detection, bottom-up guidance, and the warning past 4 MRs.
- The corrected evidence (see Industry Insights): LinearB 2026 p75 replaces "LinearB 2025, elite <219".
  SmartBear's 70-90% figure goes, and Kudrjavets and Google's ~100 lines come in. The 0.5× test weight
  stays, labelled as a configurable choice with no study behind it.

Non-goals:

- Merging anything, including through `gh stack merge` or the merge queue.
- Editing CI workflow files.
- Delegating to Graphite, git-spice, git-town, or other stack tools.
- Planning a stack before code is written.
- Landing bottoms as soon as they're approved. Non-bottom PRs stay in draft.
- GitLab MR dependencies, which are Premium-only, and `glab stack`, which is experimental.
- Cross-fork stacks beyond reporting that they can't be native.

## Success criteria

- pytest covers `stack.sh` and `restack.sh` against throwaway repos, with `gh` and `glab` stubbed, in
  the style of `tests/test_split_branch_analyze.py`. The existing analyze tests move with the rename and
  still pass.
- A `trigger-evals.json` for the skill covers split, manage, and land phrasings, plus near-misses that
  shouldn't trigger it.
- One fresh-agent scenario run per phase (Split, Manage, Land) against a local fixture repo follows the
  phase file to the expected result without help.
- No live GitHub or GitLab repo is used.

## Decisions Locked

Scope

- Ship directions 1 (native registration), 2 (land phase), 3 (mid-stack feedback), 4 (evidence fix),
  7 (depth ceiling and off-ramps), and 9 (CI-filter preflight).
- Defer directions 5, 6, and 8 (see Deferred Ideas).
- Keep the rule that non-bottom PRs stay in draft.
- Use the standard gray-area set without adhd.

Trigger scope

- The skill covers the full lifecycle on any stack, including stacks it didn't create.
- Rename to `stacking-prs`.
- On a branch already in a stack, detect it, show it, and ask which phase.
- Offer off-ramps only when the plan is over 4 layers or the diff is under 2× target.

Forge paths

- Register native stacks automatically when `gh stack` is installed. Otherwise build a classic stack
  and print a one-line tip.
- The native header drops Stack Position and Review Order and keeps Feature Goal and Intentionally
  Missing.
- The user merges. The skill does pre-merge checks and post-merge sync.
- GitLab relies on stacked-MR detection plus bottom-up guidance, with a warning past 4 MRs.

Skill shape

- A clean rename, noted in the release changelog, with no `/split-branch` stub.
- The config moves to `.quirk/stacking-prs.json` with no fallback.
- A lean `SKILL.md` router plus one `references/` file per phase.
- Forge differences sit inline in each phase file as a short per-forge block.

Scripts vs instructions

- Stack detection is a new script that emits JSON, like `analyze.sh`.
- Post-merge restack is a script with automatic backups, like `extract.sh`.
- Native stacks go through `gh stack` commands (rebase, sync, push).
- Mid-stack feedback is a documented fixup, autosquash, and update-refs flow plus a verify step.

Approach and verification

- Approach A: forge-first detection with a local-ancestry fallback, persisting nothing.
- Success is measured by script tests, trigger evals, and one scenario run per phase, with no live
  repo.

## Industry Insights

Full findings with every citation are in
[the exploration](../../explorations/2026-10-19-splitting-and-stacking-prs.md#findings). The ones that
shaped this design:

- GitHub native stacks are GA on all github.com plans as of 2026-10-06. GHES support has no date.
  Existing chained PRs can be adopted with `gh stack link`.
  [GA changelog](https://github.blog/changelog/2026-10-06-stacked-pull-requests-generally-available/),
  [CLI reference](https://docs.github.com/en/pull-requests/reference/stacked-prs-cli-commands)
- Native stacks merge bottom-up only, rebase server-side after a merge, run Actions as if every PR
  targets the stack base, and can't span forks.
  [Merging stacked PRs](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/merging-stacked-pull-requests),
  [reference](https://docs.github.com/en/pull-requests/reference/stacked-pull-requests)
- Squash-merging the bottom of a classic stack needs `git rebase --onto <trunk> <old-parent-tip>
  <child>` on the next layer. [sleepingpotato](https://sleepingpotato.com/stacking-prs-squashing-merges/),
  [Andrew Lock](https://andrewlock.net/working-with-stacked-branches-in-git-part-2/)
- Classic GitHub retargets dependent PRs only when the merged head branch is deleted, so the skill
  retargets explicitly.
  [Managing branches](https://docs.github.com/en/pull-requests/how-tos/commit-changes/managing-branches-within-your-repository)
- GitLab retargets up to 4 open MRs when their target merges, and detects stacks of up to 20 MRs from
  a single author. [MR docs](https://docs.gitlab.com/user/project/merge_requests/),
  [stacked MRs](https://docs.gitlab.com/user/project/merge_requests/reviews/stacked_merge_requests/)
- `--update-refs` skips branches checked out in another worktree.
  [git-rebase](https://git-scm.com/docs/git-rebase)
- `--force-with-lease` alone is defeated by background fetches, and adding `--force-if-includes`
  closes that gap. [git-push](https://git-scm.com/docs/git-push)
- `pull_request: branches: [main]` filters skip classic stacked PRs.
  [GitHub community](https://github.community/t/actions-on-pull-request-against-another-pull-request/18046)
- PR size doesn't relate to time-to-merge across 845,316 PRs.
  [Kudrjavets et al. 2022](https://arxiv.org/pdf/2203.05045). Google calls about 100 lines reasonable.
  [Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html). LinearB 2026
  puts elite at under 100 lines at p75 (vendor).
  [LinearB](https://linearb.io/library/engineering-benchmarks-and-research)
- Practitioners put practical depth at 3-4 layers, and the top pushback says PRs should be atomic, not
  merely small.
  [dandoescode](https://www.dandoescode.com/blog/github-stacked-pull-requests),
  [r/ExperiencedDevs](https://www.reddit.com/r/ExperiencedDevs/comments/1in4vf8/please_dont_make_prs_too_small/)

## Deferred Ideas

- Direction 5, plan-time stacking: split the task before writing code.
- Direction 6, detecting a stack tool (git-spice, git-town, Graphite) and delegating to it.
- Direction 8, landing each bottom as soon as it's approved instead of keeping non-bottom PRs in draft.
- `[tech-spec]` How to detect native-stack membership: `gh stack` JSON output or the REST stacks
  endpoint.
- `[tech-spec]` How to find the old parent tip after a merge, and whether squash merges need detecting
  at all (from the PR's merge method or by patch-id), given that `--onto` with the old tip handles
  every merge method.
- `[tech-spec]` How to stub `gh` and `glab` in pytest.

## Glossary

- **Layer**: one branch and its PR or MR in a stack.
- **Bottom / top**: the layer that targets trunk, and the layer nothing else targets.
- **Trunk**: the branch the stack eventually lands in, usually main.
- **Parent**: the layer a given layer's PR targets.
- **Native stack**: a GitHub stack registered with GitHub's stacked-PRs feature.
- **Classic stack**: chained PRs or MRs with no native registration.
- **Local mode**: a chain of local branches with nothing pushed.
- **Restack**: replay a layer's own commits onto a new base after its parent changed or merged.
- **Retarget**: change the branch a PR or MR merges into.
- **Off-ramp**: an alternative to stacking. Here that means one PR with atomic commits, or sequential
  PRs to trunk behind a feature flag.
- **Weighted lines**: the size measure `analyze.sh` computes, with file-kind and line-kind weights.

## Status & amendments

**Status**: Approved

**Amendments:** none yet.
