# Subagent-Driven Development — Simplification

Rewrite `skills/subagent-driven-development/` around a single idea: **cheap fast
implementation, with all quality judgment concentrated in one adversarial review loop at the
end.**

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

**Three tiers collapse to two.** The captain sub-orchestrator disappears. Captains existed to own
a per-task review chain; with no per-task review there is no chain to own, so the orchestrator
dispatches workers directly.

| Role | Model | Job |
| --- | --- | --- |
| Orchestrator | Opus (the session model) | Decompose, dispatch, commit, adjudicate, route |
| Implementer | Sonnet subagent via `Task` | Build one small, well-defined task |
| Reviewer ×3 | `gpt-5.6-sol` at high effort via `pi-watch` | Adversarially review a diff through one lens |
| Fixer | Sonnet subagent via `Task` | Apply an adjudicated finding packet |

The orchestrator is the only agent that persists across the run. Every worker is fresh and
disposable, receives exactly what it needs, and returns once.

Quality is not distributed across the run. It is concentrated in one adversarial loop at the end,
with cheap mechanical gates (build/test) in between and a one-round checkpoint after any wave that
has work stacked on top of it.

## Data flow

The orchestrator optionally authors a tech spec (unchanged complexity-tier gate: execution spans
more than one session, crosses a subsystem boundary, touches ≳3 source files, or the user asked).
It then decomposes the spec into tasks **inline**, in conversation and into TodoWrite. Each task
carries a contract, acceptance criteria, and — when it will run in parallel — a `scope.files` list.

Tasks are sorted into waves by declared dependencies. Within a wave, tasks run in parallel if and
only if their declared file scopes are disjoint; otherwise they run sequentially. All work happens
in the one working tree on a single feature branch. There are no worktrees, no per-task branches,
and no merge step.

For each task the orchestrator compares `git diff --name-only` against the declared scope before
committing that task's work. A task that wrote outside its scope is a defect: the orchestrator
surfaces it rather than committing silently.

After each wave the orchestrator runs the project's build and test commands. A red gate is fixed
before the next wave dispatches. After each wave that has a successor, the orchestrator also runs
a **checkpoint review**: three reviewers, one round, adjudicate, fix, re-run build/test.

After the final wave the orchestrator runs the **final review loop** over `base..HEAD`: three
reviewers, adjudicate, fix, build/test, repeat. The loop exits when no finding above LOW survives
adjudication, or after five rounds — whichever comes first.

Findings still open at exit are filed to the typed-artifact files (`BUGS.md`, `DEFERRED.md`,
`TEST_BACKLOG.md`) via the existing `quirk:typed-artifacts` machinery, and they lead the run
summary. The run then hands off to `quirk:finishing-a-development-branch`.

## Key decisions & rationale

**Two tiers, not three.** The captain tier's entire purpose was owning a per-task
implementer→reviewers→adjudicate→fix→re-review chain without returning to the orchestrator between
stages. Removing per-task review removes the chain, which removes the reason for the tier. This
also removes the duplicated-authority problem: the old `SKILL.md` declared the captain template
authoritative and then restated its protocol anyway, which is where most of the documented drift
originated.

**Quality concentrated at the end.** One strong adversarial pass over a complete, coherent branch
finds more than several weaker passes over fragments — and it can see cross-task integration
defects, a class the old per-task reviewers structurally could not reach. The trade is explicit: a
defect can live in the tree until the final loop.

**In-place with disjoint scopes.** This is the single largest simplification available. Requiring
parallel tasks to declare non-overlapping files makes one shared working tree safe, which deletes
worktree creation, branch naming, the serialized merge lane, merge conflict handling, and the
merge resolver in one move. The residual risk — an implementer straying outside its declared
scope — is covered by the pre-commit scope diff, which is one command.

**Checkpoint every wave that has a successor.** Written this way, the rule needs no size threshold
and no wave-count parameter: a single-wave run has no non-final wave, so it gets zero checkpoints
and goes straight to the final loop *by construction*. The trigger is also the right signal — a
wave has a successor because something depends on it, and dependency is exactly what makes a
defect in it expensive. A wave-size threshold was explicitly rejected as the same pattern as the
old skill's `>150 changed lines` Codex gate: a proxy for a judgment the planner already made,
re-evaluated at the wrong time by the wrong decider.

**Checkpoint and final review are different shapes.** A checkpoint asks "is this foundation sound
enough to build on?" and gets one round. The final loop asks "is the whole thing correct?" and
iterates. Converging to clean mid-run is wasted effort, because the final loop re-examines
everything anyway with the complete picture. Cost stays at `(waves − 1) × 1 round + 1 final loop`
rather than `waves × 5`.

**Cross-family review by construction.** Claude Sonnet implements; `gpt-5.6-sol` reviews. A model
reviewing another family's output catches more than one reviewing its own idioms. This falls out
of the runtime split rather than requiring a rule.

**Orchestrator may dismiss any finding with a recorded reason.** This is what makes a five-round
cap affordable. An LLM reviewer will always find something; without discretion the loop converts
reviewer confabulation into real work. Opus is the most capable agent in the loop, so it
adjudicates — but every dismissal costs one written line, which keeps it auditable.

**Severity is set at the producer.** All three reviewers emit `CRITICAL | HIGH | MEDIUM | LOW`
directly. The old skill reconciled three reviewer dialects centrally with a normalization table
and a default-to-HIGH rule for a reviewer that had no severity vocabulary at all. Constraining the
producer empties the table.

**Zero scripts.** `sdd-wave` has no worktrees or merge lane left to manage. `sdd-ledger` is
replaced by typed artifacts. `sdd-acceptance` is the orchestrator running build/test directly.
`sdd-dispatch` is `pi-watch` plus a shell redirect. All four are deleted.

**Replace in place, keep the name.** Existing routing keeps working — `brainstorming`'s terminal
state, `executing-plans`' cross-reference, `writing-plans`' integration note. Shipping a second
skill alongside would reintroduce the dimension-multiplication problem at the routing layer: every
run would start with "which of these two do I use?" The old version remains in git history.

## Behavior & scenarios

**Single-wave run (the common case).** Spec decomposes into 3 independent tasks. One wave. Three
Sonnet implementers dispatch in parallel with disjoint scopes. The orchestrator scope-diffs and
commits each. Build/test runs. Because this is the final (only) wave there is no checkpoint — the
run goes straight to the final loop. Three reviewers examine `base..HEAD`, the orchestrator
adjudicates, fixers apply accepted findings, build/test runs, and the loop repeats until clean.

**Multi-wave run.** Wave 1 lays a data model; wave 2 builds two features on it. Wave 1 has a
successor, so after its build/test gate it gets a one-round checkpoint: three reviewers see wave
1's diff plus read-only repo access, the orchestrator adjudicates, fixers fix, build/test re-runs.
Wave 2 dispatches against corrected foundations. Wave 2 is final, so it gets no checkpoint — the
final loop covers it.

**Trivial non-final wave.** Wave 1 changes one config value that wave 2 reads. The orchestrator
skips its checkpoint and records one line of why. The final loop still sees the change.

**Reviewer raises a CRITICAL the orchestrator disagrees with.** Opus rejects it, writes a one-line
reason, and the fixer never sees it. The finding does not reappear in later rounds because fixers
receive only the adjudicated packet, never raw reviewer output.

**Implementer writes outside its declared scope.** The pre-commit `git diff --name-only` check
catches it. The orchestrator does not commit; it inspects, and either widens the scope
deliberately or re-dispatches the task.

**`pi-watch --check codex` fails at run start.** Reviewers fall back to Claude
`quirk:code-reviewer` subagents using the same three lenses, with a single warning to the user.
Cross-family diversity is lost; the loop is not.

**Loop hits five rounds with findings still open.** The run stops looping. Open findings are filed
to `BUGS.md` / `DEFERRED.md` / `TEST_BACKLOG.md` and lead the final summary. The run does not claim
success without naming them.

## Scope & non-goals

**In scope:** rewriting `skills/subagent-driven-development/SKILL.md`; replacing twelve prompt
assets with three (lens-parameterized reviewer, implementer, fixer); deleting all four Python
scripts; updating cross-references in sibling skills that describe this one.

**Non-goals:**

- Not a replacement for `quirk:executing-plans`, which remains the sequential no-subagents path.
  The existing cross-reference describing it as a "parallel session" alternative is wrong and gets
  corrected as part of this work.
- Not attempting per-task quality guarantees. A defect can live in the tree until the final loop.
  This is the deliberate trade for implementation speed.
- Not preserving the mechanical merge audit. With no branches there is nothing to merge, so the
  guarantee it provided is obtained instead by never letting unreviewed work leave the one working
  tree before the loop runs.
- Not building new tooling. If a step cannot be expressed as a shell command the orchestrator runs
  directly, it does not belong in this skill.

**Retained from the old skill, deliberately:** never start implementation on main/master without
explicit consent; the scope diff before commit; foreground dispatch (the one rule backed by a real
incident — background dispatch stranded 3/3 captains in the first dogfood run); and leading the
final summary with unresolved findings rather than hiding them behind a positive verdict.

**Rough budget:** ~150 lines of `SKILL.md` plus ~200 lines of assets, against 2,307 today.

## Decisions Locked

**Review-loop termination**

- Exit when no finding above LOW survives adjudication, **or** at the round cap — whichever first.
- Round cap: **5**.
- The orchestrator may dismiss a finding of **any** severity, with a one-line recorded reason.
- Findings open at exit are filed to typed artifacts (`BUGS.md` / `DEFERRED.md` /
  `TEST_BACKLOG.md`) and lead the final summary.

**Review composition**

- **3** reviewers per round, with **distinct lenses**: correctness/logic · spec-compliance ·
  security and failure modes.
- Final-loop reviewers see the whole-branch `base..HEAD` diff, read-only repo access, and the
  spec. Checkpoint reviewers see that wave's diff, read-only repo access, and the spec — prior
  waves are already committed, so repo access covers whether this wave broke an earlier
  assumption.
- All three run `gpt-5.6-sol` at **high** effort (`pi-watch --alias codex --thinking high`).
- Fallback when `codex` does not resolve: Claude `quirk:code-reviewer` subagents, same three
  lenses, one warning.

**Isolation and merge safety**

- In-place in one working tree; parallel tasks **must** declare disjoint `scope.files`.
- `scope.files` required for parallel tasks, optional for sequential ones.
- The orchestrator commits per task; implementers never commit.
- Before committing, the orchestrator diffs `git diff --name-only` against the declared scope.

**Fix ownership**

- Fresh Sonnet implementers apply fixes — never the original implementer, never Opus directly.
- Findings are grouped by file; fixers run in parallel across disjoint groups.
- Fixers receive the **adjudicated packet only**, never raw reviewer output.
- Build and tests run after each fix batch, before the next review round.

**Wave gating**

- Checkpoint-review every wave that has a successor; the final wave gets none.
- A checkpoint is **one round**, not a loop.
- The orchestrator may skip a trivial non-final wave's checkpoint with a recorded reason.
- Build/test runs after every wave regardless.

**Structure**

- Replace `skills/subagent-driven-development/` in place; keep the name and description.
- Implementers and fixers are Claude Sonnet subagents via `Task`.
- Optional tech-spec gate retained; task breakdown moves inline (no `writing-plans` rubric
  invocation, no plan-document-reviewer dispatch).

## Industry Insights

**(No external web research — reused in-session findings, per the brainstorming skill's
already-researched-domain rule.)**

Two independent adversarial reviews of the current skill, run 2026-07-27, grounded every decision
above:

- A **Fable subagent** reading `SKILL.md`, both captain templates, all worker assets, and the four
  scripts, calibrated against `writing-skills` and `executing-plans`.
- **`gpt-5.6-sol` at high effort** via `pi-watch`, same corpus, independent context.

Both independently identified: the inert Phase 2/3 protocol, `IN_PLACE_PARALLEL` as
narrow-firing with an audit that no script implements, `TEAM` mode as creating a team and then
forbidding its communication channel, the guarded-patch path as unverifiable, and the
platform-qualified timeout containment as adversarial-grade hardening for a declared
non-adversarial threat model. Both independently landed on ~40% of current length as the target,
with substantially the same cut list.

Applicable multi-agent patterns already established in this session's tooling context, and applied
here: **perspective-diverse verification** (distinct lenses beat redundant reviewers, because
diversity catches failure classes redundancy structurally cannot), **adversarial verify**
(reviewers prompted to refute rather than confirm), and bounded iteration with an explicit cap
rather than loop-until-subjectively-clean.

One empirical constraint from this repo's own history: `pi-watch` stdout truncation was a real
observed bug (fixed in commit `5bdba89`, "flush stdout before exit so long pi-watch responses
aren't truncated"). Reviewer output is therefore redirected to a scratch file and read back, rather
than consumed from remembered stdout.

## Deferred Ideas

- **Scale reviewer count with diff size** (1 reviewer per N changed files). Rejected for the first
  version as another runtime threshold; revisit if 3 reviewers prove thin on large branches.
- **Mixed reviewer families** (gpt-5.6-sol + Claude + gemini). Was the recommendation; the user
  chose all-`gpt-5.6-sol` at high. Worth revisiting if the loop shows correlated blind spots.
- **PreToolUse hook enforcing scope at write time.** Stronger than the pre-commit diff, but needs
  per-run hook config and fails awkwardly mid-implementation.
- **Orchestrator fixing small findings inline** to save a dispatch round-trip. Rejected as the
  guarded-patch complexity the old skill got wrong.
- **`.contract` partial dependencies.** If the parallelism gain ever proves material, express it by
  splitting a task into a contract task and an implementation task — using plain dependencies
  rather than a second definition of "done."

## Glossary

- **Wave** — a set of tasks whose declared dependencies are all satisfied, dispatched together.
- **Checkpoint review** — a single round of three reviewers after a non-final wave.
- **Final loop** — up to five rounds of three reviewers over the whole branch at run end.
- **Lens** — the perspective assigned to one reviewer (correctness, spec-compliance, or security
  and failure modes); one prompt with a lens slot, not three prompts.
- **Adjudicated packet** — the accepted findings plus the orchestrator's rulings, and the only
  thing a fixer receives.
- **Scope diff** — `git diff --name-only` compared against a task's declared `scope.files`, run by
  the orchestrator before committing that task.
- **Disjoint scopes** — no two parallel tasks in a wave name the same file path; the precondition
  that makes one shared working tree safe.

## Status & amendments

**Status:** Approved — ready for execution.

**Amendments:** none.
