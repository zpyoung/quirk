# quirk:full-code-review

## Status & amendments

**Status:** Approved — Tech spec: authored (gate: user requested; >3 files; crosses subsystems; multi-session)

**Amendments:**
- 2026-10-17: Added `--since <ref>` delta reviews (scenario "Review only the fix commits", a Decisions Locked line under Verdict and output). Delta runs are report only.

## Purpose

`sakura:review-mr-combined` is the most thorough review we have: 14 parallel specialist passes, author and reviewer seats, decision memory, an HTML triage page, and gated posting. It only works for Recharge on GitLab. Its checklists are mostly generic already; what ties it down is hard-coded `glab` calls, a Recharge risk rubric, and sakura-specific plumbing.

`quirk:full-code-review` brings that review to any repo on GitHub, GitLab, or no forge at all, with no Recharge content. The first user is the author of this spec, running it on personal and open-source GitHub repos. `sakura:review-mr-combined` is left untouched.

## Conceptual model

A run is one advisory review of one change, with a human approving everything that leaves the machine. It moves through four stages, and each stage hands a file to the next:

1. **Resolve the change.** A PR/MR number, a branch, or `--local` becomes a forge-neutral change record: diff, refs, description, author, viewer, and seat.
2. **Resolve policy.** Built-in defaults, an optional org pack, a project pack, and `REVIEW.md` combine into one effective policy: which lenses run, on which models, at what severity floor, against which critical paths.
3. **Review.** Lenses run, findings are optionally checked by a second model family, and a coordinator merges everything into one versioned report.
4. **Deliver.** You triage on the HTML page, decisions are remembered, and approved findings are posted through the forge adapter or exported locally.

The forge adapter is the only part that knows GitHub or GitLab exists. Everything upstream of delivery works on the neutral change record.

## Data flow

The forge is detected from the git remote: `github.com` and `gitlab.com` are recognized directly, and a self-hosted host is classified by whichever of `gh` or `glab` is authenticated for it. `--forge` overrides detection. With no supported forge, the review still runs and delivery becomes a local export.

The seat comes from PR authorship. If you authored the PR you are in the author seat; otherwise the reviewer seat. When you authored it but someone else also pushed commits, or the reverse, the skill asks once, because the seat controls what gets posted.

Policy layers apply in this order, each overriding the last:

1. Built-in roster: 14 lenses, run conditions, default model tier per lens.
2. User pack at `${XDG_CONFIG_HOME:-~/.config}/quirk/review/`, or the directory given by `--pack <dir>` for this run.
3. Project pack at `<repo>/.quirk/review/`.
4. `REVIEW.md`: YAML front matter for toggles, Markdown prose for rules, nearest file to the changed code wins.

In the reviewer seat, the project pack and `REVIEW.md` are read from the target branch, so a PR cannot weaken its own review. `CLAUDE.md` and `AGENTS.md` feed the conventions lens. Files marked generated (`.gitattributes linguist-generated` or skip globs in policy) are dropped before any lens reads the diff and listed in the report summary.

The risk lens runs first and its rating sets verification depth for the rest. The other applicable lenses then run in parallel, each at its mapped model tier, escalating to a stronger tier on High risk or Critical findings unless policy turns escalation off. If cross-family verification is enabled, a second model family tries to refute each Must/Should finding before it reaches the report. The coordinator dedupes, calibrates severity, ranks, and writes `report.json`.

Delivery renders the report, opens the triage page, and turns the pasted decisions into a decisions file bound to the report and head SHA. Decisions are saved to the ledger at `$XDG_STATE_HOME/quirk/review-memory/` along with the lens that produced each finding. Only after a final explicit approval does the adapter post.

## Behavior & scenarios

### Self-review of your own GitHub PR, no config

The applicable lenses run with built-in defaults. The triage page offers Will fix, Fix later, Ignore, and Needs detail. After approval, Must and Should findings become inline comments on the PR. Nits stay in the local report.

### Reviewing someone else's GitHub PR

Specialists read a detached worktree at the exact PR head, never your own branch. If no matching local clone exists, the skill asks before making a temporary clone; declining gives a diff-only review where every finding is marked unverified. The mutation probe asks for consent every run and is never offered on a fork PR. Triage offers Blocking, Non-blocking, Question, and Drop. Approved findings become one pending review. Submitting it as comment, approve, or request-changes is a separate offer, never inferred.

### GitLab MR, either seat

Same behavior as GitHub. Reviewer findings become one batch of draft notes published together.

### Local changes, or a repo on an unsupported forge

Same lenses and report. Posting is replaced by an exported findings file in Markdown and JSON. The summary says why nothing was posted.

### Re-review after new pushes

Findings that match exactly keep your earlier decision. Findings on changed or moved code come back for a fresh decision, so a dismissal lapses when the code it covered changes. Findings already posted are recognized from markers in your own comments and are not posted again.

### Review only the fix commits

You pass `--since <ref>` after pushing fixes for an earlier review, and the review covers only what changed after that commit. The ref must be an ancestor of the head, and in a change or branch run it must also sit after the change's merge base, so target-branch history never enters the review. A ref equal to the head is refused as empty, except in `--local` when uncommitted changes remain. A merge commit in the range draws a warning, because it can carry target-branch changes into the delta. The report says which ref it was reviewed since, and the run is report only: nothing posts, and the ledger is neither read nor written. The exported triage handoff asks the fixer to prove each fix with a test that fails without it, to run the tests on every runtime version CI covers, and then to re-review with `--since <head SHA>`.

### A lens fails or a mapped model is unavailable

A failed or timed-out lens marks the whole report incomplete and names the missing lens. The report is never presented as clean. An unavailable model (no pi install, quota, error) falls back to the lens's default Claude tier, and the Assumptions section names the model that actually ran.

### Large change

No change is refused or flagged for its size. The diff is split into batches by file and never silently truncated, and the report states the size after generated files are excluded.

### A pack overrides risk and adds a lens

The pack's risk rubric replaces the generic one, the added lens appears in the report's list of lenses run, and the critical paths declared in `REVIEW.md` feed the risk lens.

### Capturing a lesson

`--add-guidance "<lesson>"` asks whether the lesson belongs in `REVIEW.md`, the project pack, or the user pack, writes it there, and leaves committing to you.

### Seeing which lens is noisy

`--stats` reads the ledger and shows, per lens, how often its findings were kept versus dismissed.

## Decisions Locked

### Home and relationships
- New skill in quirk, named `quirk:full-code-review`. A bare `code-review` would collide with Claude Code's built-in command.
- `sakura:review-mr-combined` stays untouched. The new skill has its own lens IDs, markers, and ledger, and shares no state with sakura.
- Coexists with `quirk:requesting-code-review`: that skill stays the cheap per-task check, this one is the full pre-merge review.
- Independent of `quirk:adversarial-review`. This skill keeps its own verification.

### Forge support
- GitLab and GitHub behind a small forge interface.
- GitHub gets full parity with GitLab in both seats.
- Forge auto-detected from the git remote, with a `--forge` override. No default host is baked in.
- With no supported forge, the review runs fully and delivers locally.

### Customization
- Repo policy lives in `REVIEW.md`: prose rules plus YAML front matter for toggles.
- Org standards arrive as packs: user-level, project-level, or `--pack`, in the precedence order given under Data flow.
- A pack or `REVIEW.md` can add lenses, replace checklist content, skip lenses, set the severity floor, and set the model map.
- In the reviewer seat, policy comes from the target branch.
- `--add-guidance` asks each time where the lesson goes.

### Machinery
- Both seats ship, auto-detected; the mixed-authorship case asks.
- Local decision ledger kept. A dismissal lapses when the code it covered changes.
- The HTML triage page with paste-back is kept.
- Mutation probe kept, with per-run consent, never on fork PRs or code from authors outside the repo.
- Reviewer seat reads a detached worktree at the PR head and asks before a temporary clone.

### Lens roster
- All 14 lenses ship, under sakura's existing run conditions.
- Risk uses a generic rubric (blast radius, reversibility, rollout safety) plus critical paths each repo declares.
- Cross-repo uses local heuristics, including searching sibling clones on disk, plus an optional search hook a pack can supply.
- Must and Should findings are postable by default. Nits stay in the local report unless policy lowers the floor.
- Marked generated files are excluded from review and disclosed.
- A partial run is marked incomplete and never shown as clean.

### Model mapping
- The roster sets a default model tier per lens; packs and `REVIEW.md` can override it.
- Risk- and severity-triggered escalation to a stronger tier is on by default and can be turned off in policy.
- Cross-family verification of Must/Should findings is opt-in.
- An unavailable model falls back to the lens's default Claude tier, disclosed in Assumptions.

### Verdict and output
- Advisory only. The skill never gates a merge and never emits a pass/fail exit code.
- Headless runs never post. They write the report and stop.
- Delta (`--since`) runs are report only: they never post and never read or write review memory.
- `report.json` carries a schema version, changes only additively, and is documented.

### Quality measurement
- A smoke corpus of about five seeded-bug diffs, run on demand.
- The ledger records which lens produced each decided finding, and `--stats` reports keep and dismiss rates per lens.

### Approach
- Port sakura's skill into quirk, extract every `glab` call into a GitLab adapter behind the forge interface while the existing tests keep passing, strip Recharge content and rename the namespace, then add the GitHub adapter. The GitHub adapter takes priority over GitLab polish because the first user is on GitHub.

### Done when
- The smoke corpus passes: each seeded bug is caught by its lens on the default model map.
- A run on a repo with no `REVIEW.md` and no pack produces a sensible report.
- An example org pack overrides the risk rubric and adds a lens without any core change.
- No Recharge or sakura names remain anywhere in the skill: no hosts, rubric terms, kai provenance, or `sakura:*` IDs.

## Scope & non-goals

In scope for v1: the skill with all 14 lenses; both seats on GitHub and GitLab; local-only delivery; user packs, project packs, `--pack`, and `REVIEW.md`; the ledger and `--stats`; the triage page; the guarded mutation probe; opt-in cross-family verification; the smoke corpus and an example org pack; the versioned report schema.

Not in scope:
- Any change to sakura.
- CI gating, pass/fail exit codes, auto-posting, or posting from headless runs.
- Approving or submitting a review without an explicit choice.
- Forges other than GitHub and GitLab.
- Resolving threads or responding to review comments. That is `quirk:receiving-code-review`.
- Replacing `quirk:requesting-code-review` or calling `quirk:adversarial-review`.
- A large evaluation corpus or any telemetry leaving the machine.

## Industry Insights

- **Noise is what makes teams stop using AI review.** Complaints center on comment volume and nits rather than outright wrong findings, and tools that hold users either post only P0/P1 findings or drop anything below a confidence threshold. This drove the Must/Should posting floor. ([cubic](https://www.cubic.dev/blog/how-ai-code-review-works), [CodeRabbit noise guide](https://aicodereview.cc/blog/coderabbit-reduce-noise), [Codex on GitHub](https://developers.openai.com/codex/integrations/github))
- **Review-only policy belongs in its own file.** Claude Code's managed review reads `REVIEW.md` for severity calibration, nit caps, and skip rules, separate from `CLAUDE.md`. CodeRabbit, Greptile, and Copilot all scope rules by path and severity. ([Claude Code review docs](https://code.claude.com/docs/en/code-review), [CodeRabbit config](https://docs.coderabbit.ai/reference/configuration), [Greptile standards](https://www.greptile.com/docs/code-review/custom-standards))
- **Config read from the PR head lets a PR weaken its own review.** PR-Agent requires config on the default branch for this reason. This drove the target-branch rule. ([PR-Agent usage](https://docs.pr-agent.ai/usage-guide/automations_and_usage/), [Copilot instructions](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions))
- **Generate, then verify, then rank.** Claude's managed review, Qodo, and Anthropic's open-source plugin all separate finding generation from a verification pass. Cursor's Bugbot reportedly keeps only bugs found by more than one pass. ([Anthropic blog](https://claude.com/blog/code-review), [Qodo docs](https://docs.qodo.ai/code-review), [anthropics/claude-code plugin](https://github.com/anthropics/claude-code/blob/main/plugins/code-review/README.md))
- **Keep the human gate.** Claude's managed review never approves PRs, and there is early research on reviewers habituating to agent-authored PRs. ([Anthropic blog](https://claude.com/blog/code-review), [arXiv 2606.22721](https://arxiv.org/pdf/2606.22721), title only)
- **Model-driven posting fails silently.** One team found five of six review runs reported success while posting nothing because of permission denials; posting moved into a dedicated job. Direct `gh api --paginate` also breaks behind proxies. This supports keeping posting in deterministic scripts. ([m3l-groundwork #117](https://github.com/monte3l/m3l-groundwork/pull/117), [gh-aw-mcpg #14061](https://github.com/github/gh-aw-mcpg/issues/14061), [Anthropic skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices))
- **Forge parity has real gaps.** GitHub allows one pending review per user, a single unplaceable comment can fail a whole review batch, and a 422 can be returned for a review that was actually created. GitLab has a reported bug where drafts on oversized-diff files vanish on publish. Multi-forge tools like PR-Agent use a provider interface with capability flags. ([GitHub reviews API](https://docs.github.com/en/rest/pulls/reviews), [community #168380](https://github.com/orgs/community/discussions/168380), [t3code #12549](https://github.com/pingdotgg/t3code/issues/12549), [GitLab #579609](https://gitlab.com/gitlab-org/gitlab/-/issues/579609), [PR-Agent providers](https://github.com/qodo-ai/pr-agent/tree/main/pr_agent/git_providers))
- **Extract the adapter with behavior-preserving steps.** Moving a hard-coded forge client behind a provider works best as refactor-only steps that keep existing tests passing, with the seam drawn at domain operations rather than CLI commands. ([Kilo #14278](https://github.com/Kilo-Org/kilocode/issues/14278), [characterization tests](https://www.freecodecamp.org/news/characterization-tests-before-refactoring-legacy-code/))

Coverage gap: Brave Search and Reddit research were unavailable in this session, so these findings rest on vendor docs, GitHub issues, and blogs. Several figures are single-source.

## Deferred Ideas

- sakura as a thin Recharge layer over this skill: a runtime dependency, a Recharge pack, golden-MR parity checks, and a cutover plan.
- A CI mode: `--fail-on <severity>` and opt-in headless posting.
- More cross-family options: assigning model families per lens, or consensus runs on correctness and safety.
- A larger evaluation corpus, results compared across models, and opt-in telemetry export.
- `[tech-spec]` The forge interface's operations and capability flags.
- `[tech-spec]` GitHub specifics: the one-pending-review limit, all-or-nothing comment batches, false 422s, and the fallback for very large diffs.
- `[tech-spec]` GitLab drafts silently lost on oversized-diff files.
- `[tech-spec]` Keeping `SKILL.md` under about 500 lines through progressive disclosure; sakura's is 710.
- `[tech-spec]` Splitting the port into a stack of reviewable PRs.
- `[tech-spec]` Lens ID and marker namespace (for example `quirk-review:v1`).
- `[tech-spec]` Replacing the internal design tokens vendored into the HTML report.
- `[tech-spec]` The search-hook contract a pack uses for cross-repo search, and how sibling clones are found.
- `[tech-spec]` How cross-family verification calls `quirk:pi-dev`.

## Glossary

- **Lens:** one specialist review pass with its own checklist. sakura calls these dimensions.
- **Seat:** author or reviewer. It sets the triage vocabulary and how findings are posted.
- **Pack:** a directory of checklist overrides, extra lenses, and toggles, at user level, project level, or passed with `--pack`.
- **REVIEW.md:** a repo's review policy, prose rules plus YAML front matter.
- **Severity floor:** the lowest severity allowed to post.
- **Critical paths:** money, auth, or data paths a repo declares so the risk lens weighs them.
- **Ledger:** local memory of your triage decisions, recorded per lens.
- **Marker:** a hidden tag in a posted comment that identifies the finding, so it is never posted twice.
- **Incomplete report:** a run where at least one lens did not finish. It is never shown as clean.
- **Cross-family verification:** a second model family trying to refute a finding before it reaches the report.
