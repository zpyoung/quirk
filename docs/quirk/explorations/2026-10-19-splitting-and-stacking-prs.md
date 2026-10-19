> 🧭 EXPLORATION — not a spec. No locked decisions; nothing here is build-ready.

# Exploring: splitting PRs and creating, managing, and merging stacked PRs

**Date**: 2026-10-19 · **Emphasis**: research-heavy · **Intensity**: 0.5 (Exploratory)

## Framing

What do current best practices say about splitting large PRs, building stacks, keeping them healthy through review, and landing them? The answer feeds `quirk:split-branch`, which today covers splitting and creation well but stops once the PRs are open. Scope was GitHub and GitLab, web and Reddit/HN sources, standard depth: one parallel breadth round of six agents, then one gap round of two.

The timing matters. GitHub's native stacked PRs went GA on 2026-10-06, thirteen days before this research, so a lot of 2024-2025 advice about GitHub stacks is now stale, and the native feature's own docs still contradict its changelog in places.

## What was explored

- Splitting: size evidence, split strategies, size measurement, over-splitting costs, after-the-fact techniques
- Creating stacks: when to stack, slicing, commit-per-PR vs branch-per-PR, descriptions and navigation, native platform support
- Managing: review feedback on lower PRs, restacking, force-push etiquette, CI on stacked PRs, reordering
- Merging: the squash-merge cascade, merge strategy, auto-retargeting on both forges, merge order, merge queues, protection rules, cleanup
- Tooling: 17 tools surveyed, plus a gap round on git-spice and Graphite after the Cursor acquisition
- Community sentiment: r/ExperiencedDevs, r/programming, r/github, r/git, r/devops, and Hacker News
- Gap round: GitHub native stack behavior at GA (adoption of existing PRs, squash handling, partial merges) and GitLab retargeting and MR dependencies
- Left out: Bitbucket and other forges, GHES (native stacks not shipped there yet), Gerrit-style review systems except as migration context
- _Steered:_ at scoping the user chose split-branch as the target, both forges, standard depth, all six facets
- _Ran headless:_ the idea-landscape review card went unanswered and the user said "continue", so all nine directions are kept as drafted with none dropped or deepened

## Findings

### Theme: GitHub native stacks change the defaults

- GA on 2026-10-06 for all github.com plans. GHES is promised for "an upcoming release" with no date. No setup or enablement is required. — [GA changelog](https://github.blog/changelog/2026-10-06-stacked-pull-requests-generally-available/), [rollout tutorial](https://docs.github.com/en/pull-requests/tutorials/roll-out-stacked-prs)
- Existing ordinary PRs whose bases already chain can be adopted, either through a UI banner or with `gh stack link <bottom> ... <top>`, which takes branch names or PR numbers and is additive only. The CLI is optional. — [creating stacked PRs](https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/creating-stacked-pull-requests), [CLI reference](https://docs.github.com/en/pull-requests/reference/stacked-prs-cli-commands)
- jj, Sapling, and git-town branches can be registered the same way. — [other tools](https://docs.github.com/en/pull-requests/reference/use-other-tools-with-stacked-pull-requests)
- The stack shows as a layer indicator in the PR header and a stack map in the merge box, with Shift+J/K navigation and a `stacked` webhook action. That covers what the skill's hand-written "Stack Position" header does today, but only inside GitHub's UI. — [about stacked PRs](https://docs.github.com/en/pull-requests/get-started/about-stacked-prs)
- Merges go bottom-up only. Merging a mid-stack PR lands everything below it. After a merge, the next PR is rebased server-side to target the stack base. Linear history between layers is a merge requirement, and a "Rebase stack" button repairs it. — [merging stacked PRs](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/merging-stacked-pull-requests)
- Actions "trigger as if each pull request in the stack targets the base of the stack", so a `pull_request: branches: [main]` workflow runs on every layer. Branch protection and required checks are evaluated against the stack base for every PR. — [stacked PRs reference](https://docs.github.com/en/pull-requests/reference/stacked-pull-requests)
- Limits: same repository only (no cross-fork stacks), no GitHub Desktop support, no documented maximum depth. A stack enters the merge queue as one group, and ejecting one PR ejects everything above it. — [reference](https://docs.github.com/en/pull-requests/reference/stacked-pull-requests), [GA changelog](https://github.blog/changelog/2026-10-06-stacked-pull-requests-generally-available/)
- "Rebase stack" keeps approvals on unchanged diffs even where stale approvals are dismissed. A maintainer acknowledged an approval-evaluation bug during preview (2026-07-22), and HN commenters at launch reported squash stacks needing per-PR re-approval. — [GA changelog](https://github.blog/changelog/2026-10-06-stacked-pull-requests-generally-available/), [gh-stack discussion #212](https://github.com/github/gh-stack/discussions/212), [HN 49112232](https://news.ycombinator.com/item?id=49112232)

### Theme: merging is where classic stacks break

- Squash-merging the bottom gives main one new commit, while the next branch still carries the original commits. The fix is `git rebase --onto origin/main <old-parent-tip> <child>`, then `--force-with-lease` and a retarget. Git won't see the squashed parent as merged, so it needs `git branch -D`. — [sleepingpotato](https://sleepingpotato.com/stacking-prs-squashing-merges/), [Andrew Lock part 2](https://andrewlock.net/working-with-stacked-branches-in-git-part-2/), [git-rebase](https://git-scm.com/docs/git-rebase)
- `gh stack rebase` switches to `--onto` automatically when a branch's PR has merged. git-spice needs `gs repo sync --restack`, because plain `repo sync` retargets children without restacking since v0.29. — [gh-stack README](https://github.com/github/gh-stack), [git-spice limits](https://abhinav.github.io/git-spice/guide/limits/)
- On classic GitHub stacks, retargeting happens when the merged PR's head branch is deleted. If protection or rulesets block deletion, or the head is in a fork the merger can't write to, nothing retargets. — [managing branches](https://docs.github.com/en/pull-requests/how-tos/commit-changes/managing-branches-within-your-repository)
- On GitLab, retargeting happens when the target branch merges, for up to four open MRs. "Remove source branch" after a merge does not retarget. — [GitLab MR docs](https://docs.gitlab.com/user/project/merge_requests/)
- GitLab auto-detects stacks (an MR targeting another open MR's source branch) up to 20 MRs. Since 19.2 the MRs must share an author, or the stack stops at the first one that doesn't. — [GitLab stacked MRs](https://docs.gitlab.com/user/project/merge_requests/reviews/stacked_merge_requests/)
- GitLab MR dependencies (Premium/Ultimate) block an MR until its blockers merge, and closed blockers still block. Nothing in the docs ties them to stacks. Using them to enforce stack order is an inference. — [MR dependencies](https://docs.gitlab.com/user/project/merge_requests/dependencies/)
- `glab stack` is still labeled "an experiment and is not ready for production use." — [glab stack](https://docs.gitlab.com/cli/stack/)
- On a classic stack, merging an upper PR merges it into its parent branch, so the code never reaches main. This follows from the base-branch model. No official doc states it. (inference)

### Theme: managing a stack is mostly a rebase problem

- `git rebase --update-refs` (or `rebase.updateRefs=true`) moves every branch in the stack in one rebase. It does not update branches checked out in another worktree, which matters for quirk's worktree-heavy flow. — [git-rebase](https://git-scm.com/docs/git-rebase), [Andrew Lock](https://andrewlock.net/working-with-stacked-branches-in-git-is-easier-with-update-refs/)
- Feedback on a lower PR: `git commit --fixup <sha>`, then `git rebase -i --autosquash --update-refs`, then force-push each moved branch. — [Adam Johnson](https://adamj.eu/tech/2022/10/15/how-to-rebase-stacked-git-branches/), [Rietta](https://rietta.com/blog/git-rebase-autosquash-code-reviews/)
- In `git rebase -i --update-refs`, moving a commit across an `update-ref` line changes which branch owns it. That is how you reorder or rehome a change mid-stack. — [Adam Johnson](https://adamj.eu/tech/2022/10/15/how-to-rebase-stacked-git-branches/)
- `--force-with-lease` is defeated by background fetches. `--force-with-lease=<ref>:<sha>` or adding `--force-if-includes` is stricter. — [git-push](https://git-scm.com/docs/git-push), [Adam Johnson](https://adamj.eu/tech/2023/10/31/git-force-push-safely/)
- GitHub's "changes since last review" breaks after a rebase. `git range-diff` gives reviewers the real interdiff. — [pyor](https://dev.to/pyor/re-reviewing-a-pr-after-changes-the-interdiff-problem-26i6) (current GitHub behavior unverified)
- On classic stacks, `pull_request: branches: [main]` filters match the PR's base, so stacked PRs silently get no CI. Native GitHub stacks fix this. — [GitHub community](https://github.community/t/actions-on-pull-request-against-another-pull-request/18046), [stacked PRs reference](https://docs.github.com/en/pull-requests/reference/stacked-pull-requests)

### Theme: the size evidence is weaker than the skill implies

- SmartBear/Cisco (2006, ~2,500 reviews): under 200 LOC recommended, never over 400, inspection under 300 LOC/hour. The "70-90% defect discovery" figure on SmartBear's web page does not appear in the primary PDF. — [Cisco case study PDF](https://static1.smartbear.co/support/media/resources/cc/book/code-review-cisco-case-study.pdf), [SmartBear page](https://smartbear.com/learn/code-review/best-practices-for-peer-code-review/)
- Kudrjavets, Nagappan, Rastogi (MSR 2022, 845,316 PRs, replicated on 401,790 Gerrit/Phabricator reviews): "pull request size and composition do not relate to time-to-merge." — [arXiv 2203.05045](https://arxiv.org/pdf/2203.05045)
- Google (2018): median change is 24 lines. First-feedback latency is under an hour for small changes and about 5 hours for very large ones. Defects were not measured against size. Google's guide calls ~100 lines reasonable and 1,000 too large. — [Sadowski et al.](https://sback.it/publications/icse2018seip.pdf), [eng-practices Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
- LinearB 2026 (8.1M PRs, p75): elite is under 100 lines. The skill cites "LinearB 2025, elite <219". AI-assisted PRs have a median of 96 lines vs 26 unassisted. — [LinearB benchmarks](https://linearb.io/library/engineering-benchmarks-and-research) (vendor)
- Graphite: 50-line PRs merge ~40% faster than 250-line ones. The sample is Graphite users, and reverts are detected by title. — [Graphite](https://graphite.com/blog/the-ideal-pr-is-50-lines-long) (vendor)
- Tests already get less review. In PRs touching both, 26.71% of test files drew comments vs 35.90% of production files, and test files are no less defect-prone. No source supports or tests a 0.5× size weight for tests. — [arXiv 2603.15935](https://arxiv.org/html/2603.15935)
- Preparatory refactoring ("make the change easy, then make the easy change") and refactor-only changes first are backed by Beck, Fowler, and Google. — [Fowler](https://martinfowler.com/articles/preparatory-refactoring-example.html), [Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
- Stacking does not cut CI work, and "for a small change, a single PR is usually easier." — [CircleCI](https://circleci.com/blog/stacked-prs-and-ci/) (vendor)

### Theme: practitioners are split, and "atomic" beats "small"

- The most-repeated pains: rebase churn after the bottom merges (r/programming 1sl4erj, 529 pts), conflicts that only appear after PR1 merges (r/github 1wmd7qy), and the same conflict resolved in every layer above (HN 32216027). — [1sl4erj](https://www.reddit.com/r/programming/comments/1sl4erj/github_stacked_prs/), [1wmd7qy](https://www.reddit.com/r/github/comments/1wmd7qy/why_are_stacked_prs_so_annoying_to_work_with/), [HN 32216027](https://news.ycombinator.com/item?id=32216027)
- The highest-voted pushback on small PRs says to make them atomic, not small. Another top reply says to split tasks before starting rather than splitting finished diffs. — [1in4vf8](https://www.reddit.com/r/ExperiencedDevs/comments/1in4vf8/please_dont_make_prs_too_small/), [1tpbhra](https://www.reddit.com/r/ExperiencedDevs/comments/1tpbhra/)
- Reviewer rigor runs backwards: a joke that a 50-line PR gets five change requests while a 1,500-line PR gets LGTM drew 362 points. — [1p8v861](https://www.reddit.com/r/ExperiencedDevs/comments/1p8v861/)
- Practical stack depth is 3-4 per practitioners and 5-10 per Graphite. No measured data supports either. — [dandoescode](https://www.dandoescode.com/blog/github-stacked-pull-requests), [stacking.dev](https://www.stacking.dev/)
- Tips that recur: `rebase.updateRefs`, atomic commits curated locally, refactor-first (add a parameter with a default, then migrate callers), and jj for automatic rebasing. — [1qjh66z](https://www.reddit.com/r/ExperiencedDevs/comments/1qjh66z/), [r/git 1uopaf2](https://www.reddit.com/r/git/comments/1uopaf2/)

### Theme: tooling is consolidating around the forge

- Cursor signed to acquire Graphite on 2025-12-19, and Graphite says it continues standalone. Its free Hobby tier covers personal repos only, and org repos start at $20/user/month. — [Cursor](https://cursor.com/blog/graphite), [Graphite pricing](https://graphite.com/pricing)
- git-spice (GPL-3.0, v0.32.0 on 2026-10-13) is branch-per-PR and supports GitHub, GitLab, Bitbucket, Gitea, Forgejo, and Azure DevOps. It posts a navigation comment and has experimental `gs stack merge`. — [git-spice](https://abhinav.github.io/git-spice/), [releases](https://github.com/abhinav/git-spice/releases)
- Other cross-forge options: git-town (GitHub, GitLab, Bitbucket, Gitea, Forgejo), jj-ryu (alpha, linear stacks), and git-gud (wraps `gh` and `glab`). — [git-town](https://www.git-town.com/), [jj-ryu](https://github.com/dmmulroy/jj-ryu), [git-gud](https://nlopez.io/introducing-git-gud-a-stacked-diffs-cli-for-github-and-gitlab/)
- Commit-per-PR tools (ghstack, spr, Sapling) all have a landing caveat. ghstack PRs can't merge from the UI, spr closes intermediate PRs on merge, and Sapling's overlapping PRs read badly without ReviewStack. — [ghstack](https://github.com/ezyang/ghstack), [spr](https://github.com/ejoffe/spr), [Sapling](https://sapling-scm.com/docs/git/sapling-stack/)

## Idea landscape

Possible directions for `split-branch`. None is ranked.

### Direction: register GitHub native stacks after pushing
After the PRs are created, run `gh stack link <bottom> ... <top>` so GitHub owns navigation, CI evaluation, and merge order. Keep the hand-written header for GitLab and GHES.
*why this might actually work:* adoption is additive and needs no enablement, and it removes the skill's most fragile step (refreshing every header) while also fixing the CI-filter gap.
*surfaced by:* research grounding · *sits at intensity:* Grounded

### Direction: add a "land the stack" phase
Give the skill a forge-aware merge section with three paths. Native GitHub: merge the bottom, then `gh stack sync`. Classic GitHub: delete the head branch to trigger retargeting, and use `rebase --onto` after a squash. GitLab: merge (not "remove source branch"), watch the four-MR retarget cap, and optionally add MR dependencies to enforce order.
*why this might actually work:* the skill ends at "mark the bottom ready", while the research and community pain cluster at merge time.
*surfaced by:* first-principles (follow the PR's whole life) · *sits at intensity:* Grounded

### Direction: add an "address feedback mid-stack" phase
Cover fixup plus `--autosquash --update-refs`, per-branch `--force-with-lease`, and a `range-diff` comment for reviewers. Warn that update-refs skips branches checked out in other worktrees.
*why this might actually work:* cascade conflicts are the most-cited pain, and quirk's worktree habit makes the update-refs gap a likely silent failure.
*surfaced by:* research grounding · *sits at intensity:* Grounded

### Direction: recalibrate the size evidence
Replace the "core principle" citations with what the primary sources say: Cisco's numbers, Google's ~100-line guidance, LinearB 2026, and Kudrjavets's null result on merge time. Reframe size as being about reviewer comprehension and defect discovery, not speed.
*why this might actually work:* the skill currently cites a figure missing from its primary source and an outdated benchmark, and a skill that tells agents to cite evidence should cite it accurately.
*surfaced by:* assumption-reversal · *sits at intensity:* Grounded

### Direction: plan-time stacking
When a plan exists (writing-plans), map its tasks to stack layers before any code is written, so each layer is built on its own branch instead of being carved out of a finished diff.
*why this might actually work:* "split tasks, not finished diffs" is the top-voted practitioner advice, and extraction is where the skill's riskiest git surgery lives.
*surfaced by:* contrarian-inversion (do the split before the work) · *sits at intensity:* Exploratory

### Direction: detect a stack tool and delegate to it
If `gh stack`, git-spice, `gt`, git-town, or jj is installed, run the split through its commands instead of `extract.sh` and raw rebases.
*why this might actually work:* these tools already encode the squash and restack edge cases the skill would otherwise have to teach, and git-spice spans both forges.
*surfaced by:* analogical-transfer (borrow from tools that solved it) · *sits at intensity:* Exploratory

### Direction: a depth ceiling and don't-stack off-ramps
Cap stacks at about four layers, and offer alternatives before splitting: trunk plus flags, or one PR with curated atomic commits reviewed commit by commit.
*why this might actually work:* depth multiplies rebase churn, and the strongest community pushback is about atomicity, not size.
*surfaced by:* radical-simplification · *sits at intensity:* Exploratory

### Direction: land bottoms as soon as they're approved
Reverse the current "keep non-bottom PRs in draft until the full stack is reviewed" rule. Merge each bottom as it's approved, so the stack stays short-lived.
*why this might actually work:* native GitHub enforces bottom-up order anyway, and every hour a stack stays open is another chance for the rebase cascade the community complains about.
*surfaced by:* deliberately-wrong (break a rule the skill states) · *sits at intensity:* Bold

### Direction: preflight check for CI filters
Before creating a classic stack, grep `.github/workflows` for `pull_request` `branches:` filters that would skip non-main bases, and warn.
*why this might actually work:* this failure is silent. A stacked PR shows no failing checks, just no checks, so reviewers read it as green.
*surfaced by:* overlooked-value · *sits at intensity:* Grounded

## Tensions & trade-offs

- Native GitHub stacks pull toward dropping the hand-written header and Step 7's refresh loop. GitLab, GHES, cross-fork work, and email notifications pull toward keeping it, so the skill may end up with two paths where it now has one.
- Delegating to a tool pulls toward a thin skill. Keeping `extract.sh` pulls toward zero dependencies and identical behavior everywhere. Graphite's acquisition and git-spice's GPL license are both reasons someone might not want a tool.
- The 0.5× test weight (and the comment/blank-line weighting under discussion in this branch) treats tests as cheaper to review. The only test-review data says tests already get too little review. A lower weight measures what reviewers do. A higher weight measures what they should do.
- Size targets pull toward more, smaller PRs. Kudrjavets's null result, CircleCI's CI-cost point, and the "atomic, not small" consensus pull toward fewer, coherent PRs.
- Landing bottoms early shortens stack lifetime. Holding upper PRs in draft protects reviewers from diffs that shift under them. Both aim to reduce rework, from opposite ends.
- Squash merges keep main clean but force `--onto` surgery on classic stacks. Rebase or merge-commit methods keep commit identity, so children need no surgery, but they change what main's history looks like.

## Challenge notes

- **Register GitHub native stacks**:
  - Steelman: one command replaces the header refresh, the CI gotcha, and merge-order discipline.
  - Strongest counter: the feature is 13 days past GA. The docs contradict the changelog on auto-merge, and preview users reported squash stacks hanging and approvals dropping.
  - Would be disproven if: gh-stack issues show approval or squash-merge failures continuing after GA.
- **Land the stack phase**:
  - Steelman: it closes the biggest gap between the skill and the research.
  - Strongest counter: merge behavior differs across native GitHub, classic GitHub, and GitLab, and the native path may change monthly, so this section would rot fastest.
  - Would be disproven if: in practice, stacks the skill creates mostly get merged by the native UI with no local steps.
- **Recalibrate the size evidence**:
  - Steelman: accuracy is cheap, and wrong citations erode trust in the rest of the skill.
  - Strongest counter: the thresholds still point the same way. Every source favors smaller over larger, so the practical guidance barely moves.
  - Would be disproven if: the skill's targets turn out to rest on the disputed figures in a way that changes the numbers.
- **Plan-time stacking**:
  - Steelman: it avoids extraction entirely, and plans already decompose work.
  - Strongest counter: plan tasks are sized for implementation, not review. A task often isn't a coherent PR, and plans change mid-build.
  - Would be disproven if: plan-to-layer mapping needs a manual re-split most of the time.
- **Land bottoms early**:
  - Steelman: short-lived stacks avoid the cascade.
  - Strongest counter: a bottom PR's design can be invalidated by feedback on a later layer, and once merged it costs a follow-up PR.
  - Would be disproven if: feedback on upper layers frequently forces changes to already-approved lower layers.
- **Detect and delegate**:
  - Steelman: tools have solved the edge cases.
  - Strongest counter: every supported tool is a branch in the skill to maintain and test, and agents run tools they don't know less reliably than raw git.
  - Would be disproven if: the tool paths need as much skill text as the raw-git path they replace.

## Open questions & gaps

- Does GitHub's server-side rebase after a squash merge avoid the duplicate-commit conflicts, or do authors still need `--onto` locally? The docs don't say, and one anecdote says `gh stack sync` skipped the upstack rebase.
- Is auto-merge for native stacks live? The changelog says it is rolling out, and the docs say it isn't supported.
- What does GitHub do when a plain-git force-push hits a mid-stack branch outside `gh stack`? It's undocumented beyond "Rebase stack" restoring linear history.
- Exact GitHub CODEOWNERS behavior across stack layers: the fetched sentence was garbled.
- GitLab's four-MR retarget cap vs its 20-MR stack limit: does a deep stack leave MRs pointing at merged branches?
- Does git-spice register native GitHub stacks, or only chain bases?
- No sourced guidance was found on feature-flag sequencing, interface-first PRs, or tests-first PRs as split strategies.
- Brave's llm-context endpoint returned `OPTION_NOT_IN_PLAN` for every agent, so web coverage rests on WebSearch, Brave web-search, and direct fetches.
- Two agents saw instructions embedded in fetched pages and ignored them. Nothing from those pages is used here without a primary-source match.

## Sources

Inline links above are the source for each claim. Primary GitHub and GitLab docs:
- GitHub GA changelog — https://github.blog/changelog/2026-10-06-stacked-pull-requests-generally-available/
- GitHub public preview changelog — https://github.blog/changelog/2026-07-30-stacked-pull-requests-are-now-in-public-preview/
- About stacked PRs — https://docs.github.com/en/pull-requests/get-started/about-stacked-prs
- Stacked PRs reference — https://docs.github.com/en/pull-requests/reference/stacked-pull-requests
- Merging stacked PRs — https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/merging-stacked-pull-requests
- Creating stacked PRs — https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/creating-stacked-pull-requests
- gh stack CLI — https://docs.github.com/en/pull-requests/reference/stacked-prs-cli-commands
- Other tools with stacked PRs — https://docs.github.com/en/pull-requests/reference/use-other-tools-with-stacked-pull-requests
- gh-stack README — https://github.com/github/gh-stack
- GitLab stacked MRs — https://docs.gitlab.com/user/project/merge_requests/reviews/stacked_merge_requests/
- GitLab MRs (retargeting) — https://docs.gitlab.com/user/project/merge_requests/
- GitLab MR dependencies — https://docs.gitlab.com/user/project/merge_requests/dependencies/
- glab stack — https://docs.gitlab.com/cli/stack/
- git-rebase — https://git-scm.com/docs/git-rebase
- git-push — https://git-scm.com/docs/git-push

---
*Exploration only. To build a direction: invoke `quirk:brainstorming` → an execution skill (which authors a tech spec when warranted, then plans in context).*
