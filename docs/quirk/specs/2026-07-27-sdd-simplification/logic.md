# Subagent-Driven Development — Simplification

Rewrite `skills/subagent-driven-development/` around a single idea: **cheap fast implementation,
with quality judgment moved from per-task review to branch-level adversarial review.**

## Problem

The current skill is 2,307 lines across `SKILL.md`, two captain templates, twelve worker prompts,
and four Python scripts. Two independent reviews (a Fable subagent and `gpt-5.6-sol` at high
effort, both run 2026-07-27) converged on the same diagnosis:

- It is a **cross-product of independent dimensions** — runtime (2) × execution mode (4) × risk
  tier (3) × phase (3) × dependency form (3) × fix path (2) × launcher (3). Every dimension
  multiplies the "which rules apply here?" reasoning an agent must do before acting.
- Roughly 90–130 lines describe **Phase 2/3 protocol that explicitly cannot execute**, including
  five events the captain template teaches and then forbids emitting.
- **Almost nothing is mechanically enforced.** `sdd-wave merge-lane` accepts no report path,
  reviewer evidence, or risk tier — a captain can skip its entire review chain, report PASS, and
  no downstream check detects it.
- Verified defects are shipping: `sdd-ledger query --type decision` (documented in both captain
  templates) omits the required `--run-dir` and errors out; `sdd-wave create --baseline-cmd` is
  required by argparse but never mentioned in prose; `pi-codex-adversarial-prompt.md:18` says
  capped-out CRITICAL findings carry forward while `SKILL.md:409` says they park the task.

The per-task review chain is the single largest source of that complexity, and it is what this
rewrite removes.

## Conceptual model

**Three tiers collapse to two.** The captain sub-orchestrator disappears. Captains existed
primarily to own a per-task review chain; with no per-task review there is no chain to own, so the
orchestrator dispatches workers directly. The captain's *other* responsibilities — worker status
handling, durable evidence, retries, recovery — move to the orchestrator's own state machine
rather than justifying the tier.

| Role | Model | Job |
| --- | --- | --- |
| Orchestrator | Opus (the session model) | Decompose, dispatch, audit, commit, adjudicate, route |
| Implementer | Sonnet subagent via `Task` | Build one small, well-defined task |
| Reviewer ×3 | `gpt-5.6-sol` at high effort via `pi-watch` | Adversarially review a diff through one lens |
| Fixer | Sonnet subagent via `Task` | Apply an adjudicated finding packet |

The orchestrator is the only agent that persists across the run. Every worker is fresh and
disposable, receives exactly what it needs, and returns once.

Quality judgment happens at the **branch level** rather than per task: one adversarial loop over
the whole branch at the end, a cheaper one-round checkpoint after any wave that has work stacked on
top of it, and mechanical build/test gates throughout.

## Data flow

### Preflight

The orchestrator records `RUN_BASE` (the feature branch tip at run start) into the run journal,
verifies the working tree is clean, and confirms it is not on `main`/`master` without explicit
consent. A dirty tree stops the run: pre-existing changes contaminate every subsequent scope audit.

It then pins the reviewer model once (see **Reviewer model pinning**).

### Planning

The orchestrator optionally authors a tech spec (unchanged complexity-tier gate: execution spans
more than one session, crosses a subsystem boundary, touches ≳3 source files, or the user asked).
It then decomposes the spec into tasks **inline**, in conversation and into TodoWrite.

Task fields reuse `quirk:writing-plans`' schema definitions by cross-reference rather than
restating them: contract, acceptance commands, dependencies, and `scope.files`. The
plan-document-reviewer dispatch is not used. `scope.files` is required for any task that will run
in parallel and optional for sequential ones; the scope audit applies to any task that declares it.

### Waves

Tasks are sorted into waves by declared dependencies. A **wave** is a set of tasks whose
dependencies are all satisfied. Within a wave, tasks run in parallel if and only if their declared
file scopes are disjoint; otherwise the wave runs sequentially. Wave membership is a scheduling
fact; it does not imply simultaneous dispatch.

### Execution — parallel wave

Each task gets its own worktree and branch, forked from the feature branch tip
(`WAVE_BASE = HEAD` before the wave). Implementers work only inside their worktree.

When a task returns, the orchestrator audits that branch's `WAVE_BASE..branch-tip` diff against the
task's declared scope. Because the branch contains only that task's commits, attribution is exact.
The audit uses an immutable commit range, NUL-delimited paths, and rename detection off, and it
covers untracked files added by the worker.

Branches then merge into the feature branch with `git merge --no-ff`, one at a time. Disjoint
scopes are guaranteed at plan time, so these merges cannot conflict; a conflict means the
disjointness precondition was violated and the wave stops for re-planning. Worktrees are torn down
after a successful merge and preserved on failure.

### Execution — sequential task

A sequential task works in the main tree on the feature branch. Nothing else is in flight, so
`git diff` attribution is unambiguous. The orchestrator audits the declared scope (when present),
runs the task's acceptance commands, and commits.

### Gates

After each task returns, its own acceptance commands run before its work is committed or merged.
A failing acceptance blocks that task's commit.

After each wave completes, the project's build and test commands run against the feature branch. A
red gate is a hard, non-negotiable stop: it is fixed before anything else proceeds, and it
overrides every review exit condition.

After each wave that has a successor, a **checkpoint review** runs (see below).

### Review

**Checkpoint** (non-final waves): three reviewers over `WAVE_BASE..HEAD` with read-only repo access
and the spec, one round. The orchestrator adjudicates, dispatches fixers, commits the fix batch,
and re-runs build/test. There is no second review round; a checkpoint reduces the chance of
building on a defect, it does not certify the wave.

**Final loop**: three reviewers over `RUN_BASE..HEAD`, adjudicate, fix, commit the fix batch,
build/test, repeat. The loop exits only when a **completed review round reports no accepted finding
above LOW** and the build is green — or when five rounds have run.

### Completion

Open findings and the run journal are summarized, leading with anything unresolved. A capped exit
with an accepted CRITICAL or HIGH finding is a **blocked handoff**: the run does not report success
and requires explicit user override to continue to
`quirk:finishing-a-development-branch`.

## Run journal

The orchestrator owns one scratch file outside the repository for the run's duration. It records:
`RUN_BASE` and every `WAVE_BASE`/wave tip; each task's status, scope-audit result, and commit SHA;
each review round's reviewer outputs; every finding with a stable ID, effective severity, and
adjudication; every dismissal with its one-line reason; every fix batch's commit; and build/test
results.

This replaces `sdd-ledger`'s function without its script. It is a run artifact, not project state.

**Typed artifacts are not the run journal.** `quirk:typed-artifacts` explicitly says a bug
introduced this session should be fixed, not logged. Findings against this run's own code therefore
block or surface — they are never filed as `BUG-N`. Typed artifacts receive only genuine project
backlog: pre-existing issues the reviewers surfaced incidentally, and deliberate scope deferrals.

## Review mechanics

### Lenses

Three reviewers, distinct lenses: correctness/logic · spec-compliance · security and failure modes.
One prompt with a lens slot, not three prompts.

### Severity

All reviewers emit `CRITICAL | HIGH | MEDIUM | LOW` against a shared rubric carried in the reviewer
prompt, and every finding must carry evidence and a `path:line` location. A finding without them is
not actionable and is returned or dropped.

Uniform vocabulary removes normalization syntax but not calibration, so the orchestrator assigns an
**effective severity** during adjudication and may correct a reviewer's label with a recorded
reason. The exit threshold reads effective severity, never the raw reviewer label. Duplicate
findings across lenses are deduplicated to one ID at the highest effective severity.

### Adjudication

The orchestrator accepts or rejects each finding and may dismiss any severity with a one-line
recorded reason. Findings carry stable IDs across rounds; an accepted finding stays open until a
later review round no longer reports it. Dismissed findings carry forward into subsequent rounds so
a re-report is matched to the prior ruling rather than re-adjudicated from scratch.

### Fixing

Fixers receive the adjudicated packet only — never raw reviewer output. Findings are grouped into
**connected components of anticipated write scope**, not by cited file: one finding may require a
coordinated change across a schema, its callers, and its tests, and two findings in different files
may converge on one shared file. One fixer per component, running in parallel across components.
When write scope is uncertain or components interact, a single sequential fixer handles the batch.

The orchestrator commits each fix batch. Without that commit the next `RUN_BASE..HEAD` review would
not see the fixes.

### Reviewer model pinning

Reviewers are pinned once at preflight to `--provider openai-codex --model gpt-5.6-sol --thinking
high`. `--alias codex` is explicitly **not** sufficient: it is a fallback ladder
(`gpt-5.6-sol → 5.5 → 5.4 → 5.3-codex`) and `--check codex` passes if any rung resolves, so the
alias cannot deliver the locked model.

If Sol is unavailable, the orchestrator falls back to `--alias codex --thinking high` and records
which model actually resolved. If the alias fails entirely, reviewers become Claude
`quirk:code-reviewer` subagents with the same three lenses. Each degradation warns the user once.

### Reviewer output handling

A reviewer must return a parseable finding list or an explicit `NO_FINDINGS`. Empty, truncated,
unparseable, or errored output is **never** treated as clean — it is retried once, then falls back
per the ladder above, then blocks the review round if both fail.

## Failure routing

Every worker returns one of a closed status vocabulary: `DONE`, `NEEDS_CONTEXT`, `BLOCKED`, or
`FAILED`. A report the orchestrator cannot validate against that vocabulary is `FAILED`.
`NEEDS_CONTEXT` is answered from the spec and codebase when derivable, and becomes a question to
the user when not.

Routing is a compact table, not an event system. Every row's default is stop and ask rather than
improvise.

| Situation | Response |
| --- | --- |
| Implementer returns `BLOCKED` or `FAILED` | Retry once with a fresh worker and the failure in its prompt; then stop and ask |
| Implementer returns garbage or an unvalidatable report | Treat as `FAILED` |
| Task acceptance fails | Do not commit; retry once; then stop and ask |
| Scope audit fails | Do not commit or merge. Stop the wave. Widening scope is a re-plan decision surfaced to the user, never a silent orchestrator override — in a parallel wave it destroys the disjointness precondition |
| Merge conflict in a parallel wave | The disjointness precondition was violated; stop and re-plan |
| Build/test red | Hard gate. Dispatch a fixer or revert the batch; never dispatch a reviewer or finish over a red build |
| Reviewer output missing or unparseable | Retry once, then model fallback, then block the round |
| Dependency discovered to be misdeclared | Stop dispatch, amend the wave graph, re-run affected downstream tasks' acceptance and review against the corrected upstream |
| Round cap reached with accepted CRITICAL/HIGH open | Blocked handoff; explicit user override required |

## Key decisions & rationale

**Two tiers, not three.** The captain tier's primary purpose was owning a per-task
implementer→reviewers→adjudicate→fix→re-review chain without returning to the orchestrator between
stages. Removing per-task review removes the chain. This also removes the duplicated-authority
problem: the old `SKILL.md` declared the captain template authoritative and then restated its
protocol anyway, which is where most of the documented drift originated.

**Quality judgment at the branch level.** One strong adversarial pass over a complete, coherent
branch can see cross-task integration defects, a class the old per-task reviewers structurally
could not reach. The trade is explicit and accepted: a defect can live in the tree until the
checkpoint or final loop.

**Worktrees for parallel tasks; disjoint scopes make them cheap.** An earlier draft of this spec
proposed parallel implementers sharing one working tree. That is unsound: `git diff --name-only`
returns the union of all in-flight changes, so a task cannot be attributed. Checking the union
against one task's scope yields false positives from its siblings; checking only its declared files
cannot detect it writing into a sibling's scope — the exact failure the audit exists to catch. Two
workers writing one file also lose data silently.

Disjoint scopes do not remove the need for isolation; they remove the need for a complicated
*merge*. Because disjointness is guaranteed at plan time, worktree branches cannot conflict, so the
old skill's scope-auditing merge lane reduces to a per-branch audit plus `git merge --no-ff`.

**Checkpoint every wave that has a successor.** Written this way the rule needs no size threshold:
a single-wave run has no non-final wave, so it gets zero checkpoints and goes straight to the final
loop *by construction*. The trigger is also the right signal — a wave has a successor because
something depends on it, and dependency is what makes a defect in it expensive. A wave-size
threshold was rejected as the same pattern as the old skill's `>150 changed lines` Codex gate: a
proxy for a judgment the planner already made, re-evaluated at the wrong time by the wrong decider.

**Checkpoint and final review are different shapes.** A checkpoint asks "is this foundation sound
enough to build on?" and gets one round. The final loop asks "is the whole thing correct?" and
iterates. Converging mid-run is wasted effort because the final loop re-examines everything with
the complete picture. Cost stays near `(waves − 1) × 1 round + 1 final loop` rather than
`waves × 5`.

**Exit requires a clean review round, not a clean fix report.** A round that finds and fixes three
HIGHs must run another review round. A fixer's self-report plus a green build is not independent
verification of a semantic fix.

**Cross-family review by construction.** Claude Sonnet implements; `gpt-5.6-sol` reviews. A model
reviewing another family's output catches more than one reviewing its own idioms. This falls out of
the runtime split rather than requiring a rule.

**Orchestrator may dismiss any finding with a recorded reason.** This is what makes a five-round cap
affordable. An LLM reviewer will always find something; without discretion the loop converts
confabulation into real work. Opus is the most capable agent in the loop, so it adjudicates — but
every dismissal costs one written line in the journal.

**Zero scripts.** `sdd-wave`'s merge lane is replaced by an explicit command sequence that keeps its
real properties (immutable ranges, NUL-delimited paths, rename detection off, negative scope) rather
than a bare `git diff`. `sdd-ledger` becomes the run journal. `sdd-acceptance` becomes direct
execution of plan-sourced commands with recorded exit codes. `sdd-dispatch` becomes `pi-watch` with
a redirect and a Bash timeout — its remaining value was timeout handling and partial-output
preservation, both of which the harness supplies.

**Replace in place, keep the name.** Existing routing keeps working — `brainstorming`'s terminal
state, `executing-plans`' cross-reference, `writing-plans`' integration note. A second skill
alongside would reintroduce dimension-multiplication at the routing layer.

## Behavior & scenarios

**Single-wave run (the common case).** Three independent tasks, one wave, disjoint scopes. Three
worktrees, three Sonnet implementers in parallel. Each returns; the orchestrator runs its acceptance
commands, audits its branch diff against its scope, and merges `--no-ff`. Build/test runs. This is
the final wave, so there is no checkpoint. The final loop runs over `RUN_BASE..HEAD` until a review
round reports nothing above LOW, or five rounds.

**Multi-wave run.** Wave 1 lays a data model; wave 2 builds two features on it. Wave 1 has a
successor, so after its build/test gate it gets a one-round checkpoint over `WAVE_BASE..HEAD`. The
orchestrator adjudicates, fixers fix, the fix batch is committed, build/test re-runs. Wave 2
dispatches from the corrected tip. Wave 2 is final and gets no checkpoint.

**Trivial non-final wave.** Wave 1 changes one config value wave 2 reads. The orchestrator skips its
checkpoint and records a reason naming why it is trivial. The final loop still sees the change.

**Reviewer raises a CRITICAL the orchestrator disagrees with.** Opus rejects it with a recorded
reason and the fixer never sees it. When a later round's reviewer re-reports it, the carried
dismissed-findings list matches it to the prior ruling instead of re-adjudicating.

**Implementer writes outside its declared scope.** The branch-diff audit catches it before merge.
Nothing merges. The orchestrator surfaces it; widening the scope is a re-plan decision for the user,
because in a parallel wave it retroactively breaks disjointness.

**Sol unavailable at preflight.** Reviewers fall back to the `codex` alias ladder, recording the
resolved model, with one warning. If the alias fails too, Claude `quirk:code-reviewer` subagents run
the same three lenses.

**Loop hits five rounds with a HIGH still open.** The run stops looping and reports a blocked
handoff. It does not proceed to the finishing skill without explicit user override, and the summary
leads with the open finding.

## Scope & non-goals

**In scope:** rewriting `skills/subagent-driven-development/SKILL.md`; replacing twelve prompt
assets with three (lens-parameterized reviewer, implementer, fixer); deleting all four Python
scripts **and their four pytest suites** (`tests/test_sdd_{wave,dispatch,ledger,acceptance}.py`,
1,090 lines); rewriting `skills/writing-plans/SKILL.md`'s task-schema sections to the new
vocabulary; RED/GREEN pressure tests and activation tests for the rewritten skill; updating
cross-references in sibling skills that describe this one.

`skills/writing-plans/SKILL.md` requires real editing rather than a passive cross-reference. Its
"Task Independence" section (`:133-166`), YAML example (`:205-215`), and plan-review checklist item
8 (`:314`) are built from vocabulary this rewrite deletes — captain mode, `scope.never_touch`,
`cooperative`/TEAM, the three `risk` tiers, `.contract` dependencies, `IN_PLACE_PARALLEL`,
`CODEX-DEFERRED`, and Phase 2 references. The corrected schema keeps four fields: contract,
acceptance, `dependencies`, and `scope.files`.

**Testing is mandatory, not optional.** `quirk:writing-skills` classifies discipline-enforcing
skills under the Iron Law — no such skill without a failing test first — and this rewrite changes
rules and workflow steps throughout. The work includes watching an agent violate the new rules
without the skill (RED), writing the skill to close those exact rationalizations (GREEN), then
plugging loopholes. Activation is tested separately.

**Non-goals:**

- Not a replacement for `quirk:executing-plans`, which remains the sequential no-subagents path.
  The existing cross-reference describing it as a "parallel session" alternative is wrong and gets
  corrected as part of this work.
- Not attempting per-task quality guarantees. A defect can live in the tree until checkpoint or
  final review. This is the deliberate trade for implementation speed, and it is the one property
  the old skill bought with all its machinery.
- Not restoring risk tiers. The old enum mixed planning judgment with reviewer omission and
  thresholds. Universal mechanical gates replace it.
- Not building new tooling. If a step cannot be expressed as a shell command the orchestrator runs
  directly, it does not belong in this skill.

**Retained from the old skill, deliberately:** never start implementation on main/master without
explicit consent; a real scope audit on an immutable commit range; foreground dispatch (the one rule
backed by a real incident — background dispatch stranded 3/3 captains in the first dogfood run); and
leading the final summary with unresolved findings rather than hiding them behind a positive
verdict.

**Length target:** roughly 250–350 lines of `SKILL.md` plus ~250 lines of assets, against 2,307
today. This is a target reached by specifying the protocol and then compressing it into tables and
prompts — not a cap that licenses omitting required behavior.

## Decisions Locked

**Review-loop termination**

- Exit requires a **completed review round reporting no accepted finding above LOW**, plus a green
  build — or the round cap.
- Round cap: **5**.
- The orchestrator may dismiss a finding of any severity with a one-line recorded reason, and may
  assign an effective severity that overrides the reviewer's label.
- A capped exit with an accepted CRITICAL or HIGH is a blocked handoff requiring explicit user
  override.
- Findings against this run's own code are never filed as typed artifacts; only genuine project
  backlog is.

**Review composition**

- **3** reviewers per round, distinct lenses: correctness/logic · spec-compliance · security and
  failure modes.
- Final-loop reviewers see `RUN_BASE..HEAD`; checkpoint reviewers see `WAVE_BASE..HEAD`. Both get
  read-only repo access and the spec.
- Pinned to `--provider openai-codex --model gpt-5.6-sol --thinking high`. Fallback: `codex` alias
  ladder (recording the resolved model), then Claude `quirk:code-reviewer`.
- Findings require evidence and `path:line`. Unparseable or empty output is never clean.

**Isolation**

- Parallel tasks each get a worktree and branch forked from `WAVE_BASE`; sequential tasks work in
  the main tree.
- `scope.files` required for parallel tasks, optional for sequential; the audit applies wherever
  declared.
- The orchestrator audits each parallel branch's `WAVE_BASE..tip` range before merging `--no-ff`,
  and audits the working tree for sequential tasks.
- Merge conflict in a parallel wave means disjointness was violated: stop and re-plan.
- Scope widening is a user-facing re-plan decision, never a silent orchestrator override.
- Clean-tree preflight required; `RUN_BASE` recorded at run start.

**Fix ownership**

- Fresh Sonnet implementers apply fixes — never the original implementer, never Opus directly.
- Findings are grouped by connected components of write scope; one fixer per component, parallel
  across components; a single sequential fixer when scopes are uncertain or interacting.
- Fixers receive the adjudicated packet only.
- The orchestrator commits each fix batch; build and tests run after it.

**Wave gating**

- Checkpoint-review every wave that has a successor; the final wave gets none.
- A checkpoint is one round, not a loop.
- The orchestrator may skip a trivial non-final wave's checkpoint with a reason naming why.
- Build/test runs after every wave regardless, and a red build is a hard gate that overrides review
  exit conditions.
- Per-task acceptance commands run before that task's commit or merge.

**Structure**

- Replace `skills/subagent-driven-development/` in place; keep the name and description.
- Implementers and fixers are Claude Sonnet subagents via `Task`.
- Optional tech-spec gate retained; task breakdown inline, cross-referencing
  `quirk:writing-plans`' field schema without dispatching its plan reviewer. That schema is
  rewritten as part of this work to the four surviving fields — contract, acceptance,
  `dependencies`, `scope.files` — because its current form encodes deleted vocabulary.
- Run state lives in an orchestrator-owned scratch journal.
- Workers return a closed status vocabulary: `DONE | NEEDS_CONTEXT | BLOCKED | FAILED`; an
  unvalidatable report is `FAILED`.
- RED/GREEN pressure tests and activation tests are in scope.

## Industry Insights

**(No external web research — reused in-session findings, per the brainstorming skill's
already-researched-domain rule.)**

Three adversarial reviews grounded this spec, all run 2026-07-27:

- A **Fable subagent** reading `SKILL.md`, both captain templates, all worker assets, and the four
  scripts, calibrated against `writing-skills` and `executing-plans`.
- **`gpt-5.6-sol` at high effort** over the same corpus, independent context.
- **`gpt-5.6-sol` at xhigh effort** against the first draft of this spec, which found the
  shared-tree attribution flaw, the `--alias codex` ladder defect, the typed-artifacts policy
  conflict, and the omitted pressure-test requirement. All four were independently verified against
  source before being accepted.

The first two independently identified: the inert Phase 2/3 protocol, `IN_PLACE_PARALLEL` as
narrow-firing with an audit no script implements, `TEAM` mode as creating a team then forbidding its
communication channel, the guarded-patch path as unverifiable, and platform-qualified timeout
containment as adversarial-grade hardening for a declared non-adversarial threat model. Both landed
on ~40% of current length with substantially the same cut list.

Applicable multi-agent patterns already established in this session's tooling context, and applied
here: **perspective-diverse verification** (distinct lenses beat redundant reviewers, because
diversity catches failure classes redundancy structurally cannot), **adversarial verify** (reviewers
prompted to refute rather than confirm), and bounded iteration with an explicit cap rather than
loop-until-subjectively-clean.

One empirical constraint from this repo's own history: `pi-watch` stdout truncation was a real
observed bug (fixed in `5bdba89`, "flush stdout before exit so long pi-watch responses aren't
truncated"). Reviewer output is therefore redirected to a scratch file and read back, rather than
consumed from remembered stdout.

## Deferred Ideas

- **Scale reviewer count with diff size.** Rejected for v1 as another runtime threshold; revisit if
  3 reviewers prove thin on large branches.
- **Mixed reviewer families** (gpt-5.6-sol + Claude + gemini). Was the original recommendation; the
  user chose all-Sol. Revisit if the loop shows correlated blind spots.
- **PreToolUse hook enforcing scope at write time.** Stronger than a post-hoc audit, but needs
  per-run hook config and fails awkwardly mid-implementation.
- **Orchestrator fixing small findings inline.** Rejected as the guarded-patch complexity the old
  skill got wrong.
- **`.contract` partial dependencies.** If the parallelism gain proves material, express it by
  splitting a task into a contract task and an implementation task, using plain dependencies rather
  than a second definition of "done."
- **A focused per-task contract gate** for tasks that export interfaces consumed by later waves.
  The xhigh review pushed for this; deferred because it partially reintroduces per-task review,
  which is the deliberate trade of this design. Revisit if checkpoints prove insufficient.

## Glossary

- **Wave** — a set of tasks whose declared dependencies are all satisfied. A scheduling fact, not a
  dispatch mode: tasks within a wave run in parallel only when their scopes are disjoint.
- **`RUN_BASE`** — the feature branch tip at run start; the base of the final review diff.
- **`WAVE_BASE`** — the feature branch tip before a wave; the fork point for its worktree branches
  and the base of its checkpoint diff.
- **Checkpoint review** — one round of three reviewers after a non-final wave.
- **Final loop** — up to five rounds of three reviewers over `RUN_BASE..HEAD` at run end.
- **Lens** — the perspective assigned to one reviewer (correctness, spec-compliance, or security and
  failure modes); one prompt with a lens slot.
- **Effective severity** — the severity the orchestrator assigns during adjudication, which may
  override the reviewer's label. The exit threshold reads this, never the raw label.
- **Adjudicated packet** — the accepted findings plus the orchestrator's rulings; the only thing a
  fixer receives.
- **Scope audit** — a task's changed-path set over an immutable commit range, compared against its
  declared `scope.files`.
- **Disjoint scopes** — no two parallel tasks in a wave name the same file path; the precondition
  that makes conflict-free merges possible.
- **Run journal** — the orchestrator-owned scratch file holding SHAs, task status, findings,
  adjudications, dismissals, and fix commits for the run.
- **Blocked handoff** — a run that reached the round cap with an accepted CRITICAL or HIGH open; it
  does not report success and cannot proceed without explicit user override.

## Status & amendments

**Status:** In execution — tech spec authored (complexity gate met: ≳3 source files, crosses a
subsystem boundary).

**Amendments:**

- **2026-07-27** — Reworked after a `gpt-5.6-sol` xhigh review of the first draft. Four verified
  defects fixed: (1) parallel implementers sharing one working tree cannot be scope-attributed —
  replaced with a worktree and branch per parallel task; (2) `--alias codex` is a fallback ladder
  and cannot pin `gpt-5.6-sol` — replaced with an explicit provider/model pin plus a defined
  degradation path; (3) routing this run's own findings to typed artifacts contradicts
  `quirk:typed-artifacts`' "fix it, don't log it" rule — replaced with an orchestrator-owned run
  journal; (4) RED/GREEN pressure tests and activation tests are mandatory house rules for
  discipline-enforcing skills and were missing from scope. Also added: exit requires a clean review
  round rather than a clean fix report; effective severity and a shared rubric; carried
  dismissed-findings list; explicit git ranges and fix-batch commits; a failure-routing table;
  per-task acceptance gating; connected-component fixer grouping; reviewer output validation; and a
  blocked-handoff state for capped exits. Length target raised from ~350 to ~600 lines total after
  the review showed the original budget was forcing required state transitions out of the design.
- **2026-07-27** — Defined the closed worker status vocabulary
  (`DONE | NEEDS_CONTEXT | BLOCKED | FAILED`), which the failure-routing table referenced without
  establishing.
- **2026-07-27** — Feasibility escalation raised while authoring `tech.md` and resolved with the
  user. The locked decision to reuse `quirk:writing-plans`' field schema "by cross-reference"
  assumed that schema was reusable; the in-session codebase survey found it encodes the exact
  vocabulary this rewrite deletes (captain mode, `scope.never_touch`, `cooperative`/TEAM, the three
  `risk` tiers, `.contract`, `IN_PLACE_PARALLEL`, `CODEX-DEFERRED`, Phase 2). **Resolution:**
  rewrite that skill's task-schema sections to the four surviving fields rather than leaving a
  sibling documenting a deleted control plane. `skills/writing-plans/SKILL.md` is added to scope.
- **2026-07-27** — Survey also found four pytest suites covering the deleted scripts
  (`tests/test_sdd_{wave,dispatch,ledger,acceptance}.py`, 1,090 lines). They are deleted with the
  scripts they cover; added to scope.
