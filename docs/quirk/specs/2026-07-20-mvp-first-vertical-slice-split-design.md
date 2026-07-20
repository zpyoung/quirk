# MVP-First Vertical-Slice Branch Splitting

**Date:** 2026-07-20
**Status:** Approved, ready for implementation
**Affects:** `skills/split-branch/`

## Problem

The existing `split-branch` skill splits a large branch into stacked PRs, but its
strategy ordering optimizes for reviewability of *layers*, not delivery of *value*:

| Existing behavior | Desired behavior |
|---|---|
| PR #1 is "extract pure refactors first" | The first feature slice is the primary MVP deliverable |
| Layer split is "most common" (Strategy 2) | Vertical slices are the primary strategy |
| Vertical slice is "hardest to achieve" (Strategy 3) | Vertical slicing is the default attempt |
| `extract.sh` moves whole files | Slices need hunk-level granularity |

The last row is the blocking technical gap. A vertical slice through
schema → service → API typically needs *some hunks* from files that other slices
also touch. A file-level extractor cannot express that, which is why the existing
skill degrades to layer splits in practice.

This design rewrites `split-branch` to offer both strategies, recommend between
them from a mechanical probe, and materialize slices at hunk granularity.

## Scope

**In scope:** the initial split, and a restack mode for re-parenting the surviving
stack after a lower PR merges. GitHub and GitLab.

**Out of scope:** merge orchestration (collides with merge queues and branch
protections), native stacking extensions, and any attempt to raise the model's
grouping accuracy beyond what the approval gate exists to catch.

## The governing constraint

`AtomicCommitBench` (arXiv 2607.03332, Lin/Zhou/Li, 2026-07-03 — preprint,
800 real squashed-commit episodes across 10 Python projects) measured two things
separately:

- **Patch-replay applicability (PPAR): ≥0.988** for every non-random method.
- **Grouping quality (ARI): 0.030–0.46.**

Its stated conclusion: *"the main challenge is not making a patch sequence apply,
but recovering a maintainable grouping of change intents."*

Every structural decision below follows from this. The git mechanics are the
reliable half and get automated aggressively; the grouping is the unreliable half
and gets exactly one human gate.

**Citation verification.** Because two locked decisions were reversed on this
paper, the citation was independently verified against the arXiv API and by
reading the ARI figures off the paper's own chart image (`x2.png`, Figure 2)
rather than trusting a summarizer. DepSplit 0.063 / Random 0.030 / NoSplit 0.178 /
FileSplit 0.340 are exact matches; the closing quote is verbatim. One correction
to how the paper is often cited: the "0.43 / Claude Code" row is **GLM-5 run
through the Claude Code CLI**, not Anthropic's Claude — Claude Code there is the
harness, not the model.

## Architecture

Three stages, one gate, plus a second entry point.

```
/split-branch [--vertical|--layers]     →  Analyze → Plan → ⟨GATE⟩ → Execute
/split-branch --restack                 →  re-parent the stack after a merge
```

### Stage 1 — Analyze (no writes)

1. **Pre-flight.** Repo and clean-worktree checks; pin `ORIG_BASE` and
   `ORIG_BASE_SHA`; take a `backup/<branch>_<ts>` ref; detect forge, merge method,
   branch protections, fork status, and any existing PR/MR.
2. **Extract.** `git diff $ORIG_BASE HEAD -M`. Both details matter: `-M` for rename
   detection, and `BASE HEAD` rather than `BASE`, which otherwise silently sweeps
   in dirty worktree state.
3. **Purify.** Drop paths marked `linguist-generated` / `linguist-vendored` in
   `.gitattributes`, plus a conservative allowlist (lockfiles, `dist/`, `*.min.*`,
   `*.pb.go`). No content-guessing.
4. **Label.** Tag every hunk from a fixed vocabulary: `FEATURE-CORE`,
   `FEATURE-VARIANT`, `VALIDATION`, `ERROR-HANDLING`, `PERF`,
   `REFACTOR/PREFACTOR`, `CONFIG-INFRA`, `TEST`, `DOCS`, `COSMETIC`, `UNRELATED`.
   Ablation evidence: replacing this with zero-shot "just group these" costs
   ~7 points of accuracy.

### Stage 2 — Plan (writes one file)

5. **Strategy probe.** Seed a candidate bottom slice on a *changed entry point* —
   route, handler, CLI command, event registration — and take its compile closure.
   Under the cap → recommend vertical. No changed entry point, or closure exceeds
   the cap → recommend layer-first **and name the blocker concretely**
   (e.g. "every path routes through a 900-line generated schema").

   **Compile closure**, used throughout this document, means: the minimal set of
   hunks that, added to the seed, makes the resulting tree build — hunks defining
   symbols the seed references, transitively — plus the one test that proves the
   behavior. It is a *validity* computation, not a grouping one.
6. **Group — file-first.** Start at file granularity; descend to hunk level only
   for files whose hunks carry conflicting intent tags. The dependency graph
   **orders** slices and **validates** compile closure; it never groups.
   Definitions precede uses. Symbol *removals invert* — a hunk deleting a
   definition lands at or after the hunks deleting its last uses. Import /
   `use` / `#include` / manifest hunks are sticky: they attach to the first slice
   that needs them.
7. **Emit the plan file, then stop.** This is the only mandatory gate.

### Stage 3 — Execute (writes branches, then remote)

8. **Materialize** each slice via temp index:
   `GIT_INDEX_FILE=$(mktemp -u)` → `git read-tree BASE` → `git apply --cached` →
   `git write-tree` → `git commit-tree` → `git branch`. Never touches the
   worktree; structurally cannot drift on untouched lines.
9. **Verify** each slice tip in its **own `git worktree`** — build plus the slice's
   own tests. On failure, consult the dependency graph for the missing symbol,
   pull that hunk up into this slice, retry **once**.
10. **Conserve.** `git diff --quiet <original> <top-of-stack>` (tree comparison),
    plus per-slice hunk accounting so any drift localizes to a specific hunk.
11. **Publish** in the load-bearing order: push new branches → `--force-with-lease`
    the rebased original → comment on the existing PR → create lower PRs as drafts
    → retarget the existing PR onto the new top → mark only the bottom ready.

### Two consequences, stated plainly

- **The original PR is preserved and becomes the top of the stack.** It keeps its
  number, timeline, and review threads; its diff shrinks to the remainder. No
  close-and-recreate. GitHub's only caveat is that some commits may leave the
  timeline and comments may become outdated — and the "Viewed" state argument is
  near-worthless, since GitHub auto-unmarks viewed on any change to a file, so
  every normal review round already clears it.
- **"First slice = MVP" means first _feature_ slice.** When prep work exists, the
  literal bottom PR is the prefactor and the MVP slice sits directly above it.

## Components

The organizing discipline: **scripts do everything deterministic; the model does
only judgment.** Each script is independently runnable and testable, and the model
never hand-rolls git.

| Component | Kind | Responsibility |
|---|---|---|
| `SKILL.md` | prose | Pipeline, decision rules, the gate, anti-patterns |
| `scripts/analyze.sh` | kept, extended | Weighted line counts, exclusions, directory groups, plus hunk inventory |
| `scripts/slice.sh` | new | Materialize one slice — temp index by default, `--at-commit <sha>` for the commit-boundary fallback |
| `scripts/verify.sh` | new | Build + test a slice tip in its own worktree |
| `scripts/publish.sh` | new | Push, create, retarget — in the load-bearing order |
| `scripts/restack.sh` | new | Re-parent surviving branches after a merge |
| `scripts/extract.sh` | **retired** | File-level by construction; cannot express hunk slices |

`extract.sh` is retired rather than kept: the commit-boundary fallback needs only
`git branch <sha>` + `git rebase --onto`, which does not justify preserving its
file-population machinery.

### Where judgment enters — exactly two places

1. **Intent labels.** `analyze.sh` emits the hunk inventory; the model assigns each
   hunk a tag. A read-and-classify step.
2. **Grouping.** The model assembles slices from labeled hunks under mechanical
   constraints it cannot violate — file-first descent, topological order, compile
   closure, hard cap.

Everything else — diffing, purifying, slicing, building, conservation-checking,
pushing — is script territory. Confining the ~46%-accuracy step to two well-marked
places is what makes a single gate sufficient.

## Data flow

```
git diff ORIG_BASE HEAD -M
    │
    ├─→ analyze.sh ──→ hunks.json   {file, hunk_id, old_range, +/- lines,
    │                                is_binary, splittable}
    │                                weighted_review_lines, excluded_files[]
    ├─→ [model] ─────→ labels       hunk_id → intent tag
    ├─→ [model] ─────→ groups       slice_id → [hunk_id], constrained by graph order
    │
    └─→ PLAN FILE  ══════ ⟨GATE⟩ ══════╗
                                       ▼
        for each slice:  slice.sh → verify.sh → (retry once on failure)
                                       │
                         conservation: tree(top) == tree(original)
                                       │
                                  publish.sh
```

### The plan file

Path: `.git/split-branch/<branch>.plan.md`, absolute path printed on emit.

Living under `.git/` means it can never appear in `git status`, be accidentally
committed, or pollute a slice's diff. It is ephemeral per-run; durable state lives
in the PR body (below).

Contents: strategy chosen and why; and per slice — name, parent, intent summary,
hunk assignments as `file:line`, weighted lines, what the bottom slice would demo,
the **stub inventory** (what each stub returns, why it is safe, which later slice
replaces it), and **Intentionally Missing** naming the later slice that supplies
each absent caller, endpoint, or UI.

Hand-editable. Execution consumes the edited file.

### The durable state

A fenced block appended to every PR/MR body:

```
<!-- split-branch:stack -->
parent: feature/payment-schema
base-sha: a1b2c3d4
position: 3/5
<!-- /split-branch:stack -->
```

`base-sha` is the load-bearing field. After a squash merge the original base SHA
is unrecoverable from the forge, and without it `git rebase main child` produces
duplicate-change conflicts, because squash destroys patch-id detection. With it,
restack is one command:

```bash
git rebase --onto <new-trunk> <recorded-base-sha> <child>
```

Chosen over a local ref namespace (git-spice keeps topology in `refs/spice/data`,
never pushed — simply gone in a fresh worktree), over deriving from the forge (the
base SHA is exactly what squash destroys), and over a committed manifest (appears
in every diff and conflicts on every restack). Parsed defensively: a mangled block
causes an ask, not a guess.

### Forge handling

A thin adapter over `gh` / `glab`, deliberately avoiding every stacking extension:

- `gh stack` — `github/gh-stack` v0.0.8, private preview behind a per-repo
  waitlist. Its `sync` exits 0 while pushing nothing on a diverged stack. Note the
  correct availability probe is `gh api repos/O/R/stacks` returning 404;
  `gh stack view --json` returns exit 2 (not-in-stack), not 9.
- `glab stack` — officially labelled experimental / "not ready for production use".
- git-spice — unpushed local-only topology ref; interactive-first auth.

The forge knowledge that *is* encoded is the gotcha set:

| | GitHub | GitLab |
|---|---|---|
| Retargeting | Auto-retargets open PRs when their base branch is deleted | Auto-retargets on merge; **never for forks**; **suppressed by "Delete source branch"** |
| PR identity | Head remote ref immutable; retarget base to preserve the PR | Source branch immutable; `target_branch` mutable |
| Merge method | Squash **and** rebase both rewrite SHAs; only merge-commit preserves | Merge trains documented only against the default branch |
| Blockers | Force-push blocked by rulesets; fork PRs unpushable; base change can dismiss approvals | Fork MRs excluded from retargeting entirely |

The GitLab `MAX_RETARGET_MERGE_REQUESTS = 4` limit is **not** a stack-depth cap —
it is a non-recursive query limit on MRs sharing the *same* target branch. A
linear stack has exactly one MR per branch, so a 10-deep stack retargets fine, one
hop per merge. The limit binds only on sibling fan-out (5+ MRs off one base).

## Error handling

### Hard guardrails

Each of these fails *silently* — exit 0, invisible damage. They belong in
`SKILL.md` as rules, not advice.

| Hazard | Guardrail |
|---|---|
| `--recount` on generated patches | **Never pass it.** Turns a trailing blank line into a hard failure, and a truncated-hunk `corrupt patch` (exit 128) into a silent exit 0 with partial application |
| `git apply --check` pre-flight | Redundant — `git apply` is already all-or-nothing. `--check --3way` is actively harmful: exits 0 on a patch that will conflict |
| `-U0` / `--unidiff-zero` | Generate at `-U0` for *grouping* (context width is what merges nearby hunks and destroys separability); **apply with context**. Against a drifted tree, `-U0` misapplies pure-insertion hunks silently — verified landing a change 5 lines off, exit 0 |
| Verification via `git checkout` loop | Use a dedicated worktree per slice. The common loop always exits 0, misreports dirty-checkout aborts as build failures, and leaks stale artifacts. `git rebase <base> --exec '<build>'` is the cheap alternative |
| Conservation via diff-of-diffs | **Compare trees.** The diff-of-diffs recipe fails open — a failed `git diff` with `>` redirection leaves two empty files and reports PASS |
| Computing a slice's complement | `git diff-tree -p T1 <final-tree>` — never "all hunks except A" sliced out of the original patch |
| Extended headers | Re-emit verbatim per file: `old mode`/`new mode`/`similarity index`/`rename from\|to`/`new file mode`/`deleted file mode`/`index`. `\ No newline at end of file` belongs to the *preceding* line |
| `git push --force` | `--force-with-lease`, always |
| Hardcoded `origin` | Read `remote.pushDefault` or take an explicit remote — forks and `upstream` workflows break the hardcode |
| Interactive commands | None anywhere in the execution path |

`--3way` requires `--full-index` and is mutually exclusive with `--reject`.

### Structural failures

- **Split floor.** Consecutive changed lines with no intervening context cannot be
  separated at any `-U` width (`git add -p`: "Sorry, cannot split this hunk").
  Mark unsplittable, assign whole; if that breaks the plan, fall back to commit
  boundaries.
- **Binary in range.** Unsliceable — `--binary` payloads carry no `@@` blocks, and
  one binary aborts the entire subset patch. Assign atomically to one slice.
- **Dependency cycle.** **Merge the cycling slices.** Never ship a non-building
  intermediate to satisfy a slice count.
- **Verification fails after the retry.** Halt. Verified slices remain as local
  branches, nothing is pushed. Report the failing slice, why, and the restore
  command for the backup ref.
- **Hunk surgery blocked outright** (binary in range, split floor, protected
  branch, fork PR): fall back to commit-boundary splitting —
  `git branch <name> <sha>` + `git rebase --onto`. When the existing commit
  boundaries make that degenerate, say so plainly rather than shipping a pointless
  stack.
- **Refuse to split** when weighted lines are under ~200, or the diff is a
  single-concern bug fix. Confirm before proceeding anyway.
- **Sizing is a signal, never a veto.** Dependency bumps, generated code, and
  mechanical migrations are legitimately atomic and large.

### Approval model

Exactly **one** mandatory gate, at the grouping plan. More gates train
blanket-approve. Paired with hard blocks that never auto-pass: `push --force`
without `--force-with-lease`, `reset --hard`, `rm -rf`. Read-only tools
auto-approve.

## Testing

pytest against synthetic git repos in tmpdirs, matching the existing `tests/`
convention (`pythonpath = ["bin"]`, `testpaths = ["tests"]`).

1. **Conservation as a property test — the load-bearing one.** For every fixture
   repo and every generated plan: `tree(top-of-stack) == tree(original)`. If this
   holds, no slicing bug can silently lose or duplicate work.
2. **Fixture repos, one per hazard:** binary file in range · split floor · rename
   with mode change · no-newline-at-EOF · deletion-only hunk · merge commits in
   history · squash-merged base · fork / protected-branch simulation.
3. **Guardrail regression tests** that grep the scripts: no `--recount`, no
   `git checkout` loop in verification, no bare `--force`, no hardcoded `origin`,
   no interactive invocations.
4. **Restack tests:** metadata block round-trips; `rebase --onto <recorded-base-sha>`
   produces no duplicate-change conflicts after a simulated squash merge; a mangled
   metadata block causes an ask, not a guess.
5. **Skill-content test** in the style of `tests/test_adhd_skill.py`, asserting the
   anti-patterns and strategy rules are present in `SKILL.md`.

## Decisions Locked

### Skill scope
- Update `split-branch` in place; do not create a sibling skill.
- Offer both strategies with an agent recommendation, rather than replacing
  layer-first outright.
- `/split-branch` auto-detects; `--vertical` / `--layers` force a strategy.
- Keep `analyze.sh`; retire `extract.sh` in favor of a hunk slicer.

### Slice identification
- MVP slice = the **thinnest end-to-end path** — narrowest chain letting a real
  caller exercise the feature once, happy path only.
- Carving is **file-first**, descending to hunk level only where a file's hunks
  carry conflicting intent tags.
- The dependency graph **orders and validates**; it never groups.
- Leftovers (pure refactors, formatting, config) go in a **prep slice below** the
  MVP slice.
- Slice #2..N ordered by **descending user-facing value**.
- **Coherence beats line targets** up to the 600-line hard cap.
- No end-to-end path under the cap → **fall back to layer split and say why**.

### Slice integrity
- Bar per slice: **builds + the slice's own tests pass.**
- Reconstruction: **tree-hash equality plus per-slice hunk accounting.**
- On verification failure: **pull the missing dependency up, retry once.**
- Materialization: **temp-index git plumbing** (`read-tree` → `apply --cached` →
  `write-tree` → `commit-tree`).
- Verification runs in a **dedicated worktree per slice**.

### Strategy selection
- Recommendation driven by **reachability of an end-to-end seam** — probe for a
  changed entry point, take its compile closure, check it against the cap.
- Recommendation is **stated with concrete evidence**, both strategies stay live.
- A single split **may mix strategies**: prefactor bottom, vertical above.

### Execution safety
- **One gate**, at the grouping plan.
- Approval artifact is a **written plan file**, hand-editable, consumed by
  execution.
- On failure: **stop, keep verified slices locally, push nothing, report where.**
- Blocked hunk surgery → **commit-boundary fallback.**

### Lifecycle and state
- Scope is **split plus a restack/sync mode** — not merge orchestration.
- Stack topology lives in a **machine-readable block in the PR/MR body**.
- **GitHub and GitLab**, stateless CLI, **no stacking extensions.**
- Bottom-slice bar: **green + mergeable + main stays releasable.** MVP-first is a
  strong default, not a validity gate.

## Industry Insights

Research swarm: 31 agents, 6 research angles, 24 load-bearing heuristics put
through adversarial refutation. **Only 1 of 24 survived** — the verifiers ran real
commands against git 2.53 and checked primary sources rather than blog summaries.
The synthesis below salvages the true parts of the refuted claims.

**What overturned a decision:**

- **Dependency-graph partitioning is empirically weak.** DepSplit (group hunks by
  def-use / compile components) scores ARI 0.063 vs FileSplit 0.340 and NoSplit
  0.178 — worse than one-commit-per-file, and worse than not splitting at all.
  *Scope this correctly:* DepSplit is a naive syntactic-only baseline. The same
  paper's DACE result shows dependency information fed to an agent as *evidence*
  improves ARI by 0.05–0.08, and Atomizer (ICSE 2026) and ColaUntangle both treat
  dependency-based methods as respectable prior art. The supported claim is
  "unlearned dependency clustering is a bad partitioner," not "dependency
  information is useless."
- **Hunk-level splitting is feasible and worktree-safe.** The temp-index recipe was
  verified end-to-end on git 2.53 with a clean `git status` afterward. Patch replay
  is the solved half of this problem, which removes the main argument for
  full-file authoring.
- **"Bottom slice must be independently shippable" has no source support.** GitHub
  native stacks merge bottom-up *atomically*. Google eng-practices explicitly
  endorses merging a proto CL or API stub with no caller. Fowler's Keystone
  Interface lands dormant code with no flag. The universally defensible bar is
  weaker: green, mergeable, main stays releasable.
- **Every semantic "is this a vertical slice" gate failed refutation** — the
  walking-skeleton/steel-thread/tracer taxonomy (the literature treats these as
  synonyms), the `<Actor> does <Trigger> observes <Outcome>` template (Gherkin
  relabeled; drives fabricated user stories when an agent must satisfy it), the
  five-stage production-path check (one person's dotfiles, contradicted by
  Google), the caller test, and the flag test. These are **soft prompts in the
  proposal text, never STOP conditions or re-split loops.**

**What was folklore:**

- **Stack-depth caps of 3–5** trace to a single content-marketing page.
  stacking.dev says 5–10 is normal. Depth measures dependency-chain length;
  "un-stack them" produces branches that don't build.
- **"Cap GitLab stacks at 4"** misreads `MAX_RETARGET_MERGE_REQUESTS` — a fan-out
  limit, not a depth limit.
- **"Splitting after review means closing the PR"** is false; base retargeting
  preserves number, timeline, and threads.
- **"Refuse to stack on squash-merge repos"** is wrong, and offering `--rebase` as
  the safe alternative is self-contradicting — GitHub groups rebase-and-merge with
  squash as SHA-rewriting.

**Sources**

Benchmarks and untangling research:
- https://arxiv.org/abs/2607.03332 — AtomicCommitBench (PPAR/ARI; DepSplit 0.063 vs FileSplit 0.340)
- https://arxiv.org/html/2601.01233 — Atomizer (ICSE 2026; intent-driven untangling)
- https://arxiv.org/html/2507.16395v3 — ColaUntangle (explicit vs implicit dependency reasoning)
- https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/barnett2015hdh.pdf — ClusterChanges
- https://dl.acm.org/doi/pdf/10.1145/3540250.3549171 — UTango

Git mechanics:
- https://git-scm.com/docs/git-apply · https://git-scm.com/docs/git-commit-tree · https://git-scm.com/docs/git-rebase
- https://kamalmarhubi.com/blog/2016/03/08/git-rebase-exec-make-sure-your-tests-pass-at-each-commit-and-other-rebase-goodies/

Forge and stacking:
- https://github.github.com/gh-stack/ · https://docs.github.com/articles/changing-the-base-branch-of-a-pull-request
- https://docs.gitlab.com/user/project/merge_requests/reviews/stacked_merge_requests/
- https://gitlab.com/gitlab-org/gitlab/-/raw/master/app/services/merge_requests/retarget_chain_service.rb
- https://abhinav.github.io/git-spice/ · https://www.git-town.com/stacked-changes.html

Slicing doctrine:
- https://google.github.io/eng-practices/review/developer/small-cls.html
- https://www.martinfowler.com/bliki/KeystoneInterface.html · https://martinfowler.com/bliki/ParallelChange.html
- https://gojko.net/2012/01/23/splitting-user-stories-the-hamburger-method/
- https://blog.crisp.se/2013/07/25/henrikkniberg/elephant-carpaccio-facilitation-guide

Failure modes:
- https://www.davepacheco.net/blog/2025/stacked-prs-on-github/
- https://discourse.llvm.org/t/rfc-enabling-graphite-merge-queue-to-resolve-infinite-loops-while-merging-stacked-prs/88769

**Treated as unreliable, deliberately not encoded as rationale:** pullnotifier.com
stack-depth "3–5"; LinearB/exceeds.ai p75 <100 lines; cubic.dev "one defect per 27
lines"; Graphite throughput and time-saved claims; any "9% accuracy from diff
purification" figure (no source exists).

## Deferred Ideas

- **Native stacking extensions.** Revisit when `gh stack` leaves private preview
  and `glab stack` drops the experimental label. The `gh-stack` agent contract is
  worth copying when it lands: exit codes as control flow (0 ok, 3 rebase
  conflict, 5 bad args, 6 branch in multiple stacks, 9 stacks not enabled),
  `view --json`, `submit --auto`.
- **Merge orchestration.** Driving the bottom-up merge sequence. Excluded for now
  because it interacts badly with merge queues and branch protections, and it
  means the skill executes merges.
- **Branchless / no-forge mode.** Produce the local branch stack with no PR
  creation, for dry runs or repos on neither forge.
- **Language-aware compile closure.** The strategy probe's closure computation is
  initially heuristic. Per-language LSP or ctags integration would sharpen it.

## Open Risks

- **Grouping accuracy is the ceiling.** Published untangling SOTA runs 46–72%, and
  a measured +0.333 ARI gap between synthetic tangles and real same-session
  squashed diffs means those numbers overstate real-repo performance. The skill
  will propose a wrong grouping on a meaningful fraction of nontrivial diffs. The
  gate is the mitigation; it is not a fix.
- **`AtomicCommitBench` is a preprint** on 10 Python projects. Its baseline
  ordering is the strongest evidence available for the file-first decision, but it
  is one study on one language.
- **Build/test command detection** is unspecified per-repo. Verification needs a
  build and test command; discovery is a known gap that implementation must
  resolve (config, convention detection, or asking once and remembering).
