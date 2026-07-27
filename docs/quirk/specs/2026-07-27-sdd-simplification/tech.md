# Tech Spec — Subagent-Driven Development Simplification

**Status:** Authored, reviewed.
**Logic spec:** [`logic.md`](./logic.md) — owns *why* and *behavior*. This document owns *where*
and *contracts*.

## Architecture

*Back-link: [logic.md → Conceptual model](./logic.md#conceptual-model)*

The unit of work is a Claude Code **skill**: a Markdown instruction document an LLM loads at
runtime, plus optional `assets/` prompt bodies and `scripts/` helpers. There is no compiled
artifact and no runtime; correctness means the document instructs an agent correctly and its
frontmatter triggers.

Current tree (`skills/subagent-driven-development/`, 2,307 lines total across the skill and assets):

```
SKILL.md                    709 lines   control plane
assets/                     12 files    6 Claude/pi prompt pairs
scripts/sdd-{dispatch,wave,ledger,acceptance}   4 files, 1,158 lines Python
```

Coupled outside the skill directory:

```
tests/test_sdd_{wave,dispatch,ledger,acceptance}.py    1,090 lines pytest
skills/writing-plans/SKILL.md                          329 lines, 3 coupled regions
```

Target tree:

```
SKILL.md                    ~250-350 lines
assets/reviewer-prompt.md   lens-parameterized, replaces 6 reviewer assets
assets/implementer-prompt.md
assets/fixer-prompt.md
```

No `scripts/` directory. Python 3 and pytest remain the repo's test stack for surviving suites;
this work removes suites rather than adding any.

**Technologies in play:** Markdown + YAML frontmatter (skill format), `git worktree` / `git merge`
(parallel isolation), `pi-watch` (reviewer dispatch, `skills/pi-dev/scripts/pi-watch/`), Claude
Code `Task` tool (implementer/fixer dispatch), pytest (surviving repo suites).

## Code references

*Back-link: [logic.md → Scope & non-goals](./logic.md#scope--non-goals)*

### Rewrite

`skills/subagent-driven-development/SKILL.md` — full rewrite. Frontmatter is load-bearing and
**preserved verbatim**:

```
CONFIG:
name: subagent-driven-development
description: Use when executing implementation plans with independent tasks in the current session
```

`skills/writing-plans/plan-document-reviewer-prompt.md` — rubric rows 32, 33, 36, 38. Found by the
plan-build coherence sweep, not the initial survey, because it names only the vocabulary terms
(`captain`, `never_touch`, `risk`, `.contract`) and never the skill or script names the survey
searched for. Left as-is it would flag correct new-style plans as defective — row 33 demands
`scope.never_touch`, row 36 demands an explicit `risk` field and validates `.contract` targets.

`skills/writing-plans/SKILL.md` — three regions, per the logic spec's Amendments entry:

| Region | Lines | Action |
| --- | --- | --- |
| "Task Independence" section | 133–166 | Rewrite ~40 lines → ~12; four surviving fields only |
| YAML example under `### Task N` | 210–220 | Rewrite to match the corrected schema |
| Plan-review checklist item 8 | 314 | Rewrite; drop mode/tier/`.contract` clauses |

The YAML range is the fenced block itself: it opens at 210 and closes at 220. `never_touch` (217),
`risk` (218), and its rationale comment (219) sit near the end of that block — a range stopping
short of 220 would leave deleted schema fields in place.

Also correct one stale reference discovered during review:
`skills/finishing-a-development-branch/SKILL.md:196` reads
`**subagent-driven-development** (Step 7) - After all tasks complete`. The current skill has no
Step 7 (its labelled steps are `Step 0` through `Step 0c`), so the citation is already wrong today
and nothing guarantees a successor. Drop the brittle step number rather than renumbering it.

### Create

```
skills/subagent-driven-development/assets/reviewer-prompt.md
skills/subagent-driven-development/assets/implementer-prompt.md
skills/subagent-driven-development/assets/fixer-prompt.md
```

### Delete

```
skills/subagent-driven-development/assets/captain-prompt.md
skills/subagent-driven-development/assets/pi-captain-prompt.md
skills/subagent-driven-development/assets/implementer-prompt.md          (replaced)
skills/subagent-driven-development/assets/pi-implementer-prompt.md
skills/subagent-driven-development/assets/spec-reviewer-prompt.md
skills/subagent-driven-development/assets/pi-spec-reviewer-prompt.md
skills/subagent-driven-development/assets/code-quality-reviewer-prompt.md
skills/subagent-driven-development/assets/pi-code-quality-reviewer-prompt.md
skills/subagent-driven-development/assets/codex-adversarial-prompt.md
skills/subagent-driven-development/assets/pi-codex-adversarial-prompt.md
skills/subagent-driven-development/assets/merge-resolver-prompt.md
skills/subagent-driven-development/assets/pi-merge-resolver-prompt.md
skills/subagent-driven-development/scripts/sdd-dispatch
skills/subagent-driven-development/scripts/sdd-wave
skills/subagent-driven-development/scripts/sdd-ledger
skills/subagent-driven-development/scripts/sdd-acceptance
tests/test_sdd_dispatch.py
tests/test_sdd_wave.py
tests/test_sdd_ledger.py
tests/test_sdd_acceptance.py
```

`assets/implementer-prompt.md` appears in both lists: the Claude-path file is replaced in place by
the runtime-neutral version, not deleted and recreated under a new name.

### Verified as needing no change

The skill name is unchanged, so name-only references are correct as-is:
`skills/using-git-worktrees/SKILL.md:213`, `skills/writing-tech-spec/SKILL.md:11`,
`skills/executing-plans/SKILL.md:17`, `skills/brainstorming/SKILL.md:35,75,337`,
`skills/using-quirk/references/codex-tools.md:25`,
`skills/using-quirk/references/gemini-tools.md:21`,
`skills/writing-skills/render-graphs.js:96-97` (an inert `--help` usage example).

`skills/finishing-a-development-branch/SKILL.md:196` is the one exception — see the fix noted
above. Its neighbouring line 197 cites `**executing-plans** (Step 5)`, which is equally stale
(that skill's steps run 0–3); it is left alone as out of scope and reported to the user.

Historical records under `docs/plans/` and `docs/specs/` are **not** updated — they record past
decisions and must continue to.

### Coherence sweep disposition

Every tracked file referencing the deleted vocabulary
(`captain|MERGE_READY|CHAIN_COMPLETE|IMPLEMENTER_DONE|STUB_READY|REBASE_REQUEST|READINESS_REVOKED|CONTRACT_CORRECTED|BRANCH_REQUEST|IN_PLACE_PARALLEL|WORKTREE_PARALLEL|never_touch|CODEX-DEFERRED|sdd-*`)
is dispositioned:

| File | Hits | Disposition |
| --- | --- | --- |
| `skills/writing-plans/SKILL.md` | 16 | Scoped into a task |
| `skills/writing-plans/plan-document-reviewer-prompt.md` | 5 | Scoped into a task |
| `tests/test_sdd_{ledger,wave,dispatch,acceptance}.py` | 21 | Deleted with their scripts |
| `skills/pi-dev/reference/print-mode.md:60` | 1 | **Unchanged, verified consistent** — "pi-captain style" is pi-dev's own orchestration pattern, unrelated to SDD's captain tier |
| `docs/quirk/specs/2026-07-21-sdd-captain-control-plane-design.md` | 81 | **Unchanged, verified consistent** — historical record of the design being replaced |
| `docs/plans/2026-05-08-sdd-design-implement-port.md` | 26 | **Unchanged, verified consistent** — historical |
| `docs/specs/2026-05-08-sdd-design-implement-port-design.md` | 7 | **Unchanged, verified consistent** — historical |
| `docs/quirk/plans/2026-07-05-writing-skills-rewrite.md` | 1 | **Unchanged, verified consistent** — historical |

## Contracts & interfaces

*Back-link: [logic.md → Review mechanics](./logic.md#review-mechanics)*

### Skill frontmatter

Preconditions: file begins with `---`, contains `name:` matching the directory name and a
`description:` of ≥30 characters. Postcondition: `name` and `description` byte-identical to the
current file. Violation means the skill silently stops triggering.

### Reviewer dispatch

```
COMMAND:
pi-watch --check codex
pi-watch --provider openai-codex --model gpt-5.6-sol --thinking high \
  --tools read,grep,find,ls "$(cat "$PROMPT")" > "$OUT" 2> "$ERR"
```

Preconditions: `$PROMPT` exists and is non-empty; reviewers get read-only tools only.
Postconditions: `$OUT` holds the finding list; exit 0. Error behavior: nonzero exit, empty `$OUT`,
or unparseable content is **never** clean — retry once, then `--alias codex --thinking high`
recording the resolved model, then Claude `quirk:code-reviewer`.

`--alias codex` is explicitly insufficient for the pinned path: it is a ladder
(`gpt-5.6-sol → 5.5 → 5.4 → 5.3-codex`, `skills/pi-dev/SKILL.md:45`) and `--check codex` passes if
any rung resolves.

### Reviewer output

```
SCHEMA:
findings:
  - id: string            # stable across rounds, assigned by the orchestrator
    severity: CRITICAL | HIGH | MEDIUM | LOW
    location: string      # path:line — required
    evidence: string      # required; what proves the defect
    claim: string
```

A reviewer with nothing to report emits the literal token `NO_FINDINGS`. A finding missing
`location` or `evidence` is not actionable and is dropped with a journal note.

### Worker status

```
CONTRACT:
status: DONE | NEEDS_CONTEXT | BLOCKED | FAILED
```

A report the orchestrator cannot validate against this vocabulary is `FAILED`.

### Adjudicated packet (orchestrator → fixer)

```
SCHEMA:
component: string          # the connected write-scope group this fixer owns
findings:
  - id: string             # stable across rounds
    effective_severity: CRITICAL | HIGH | MEDIUM | LOW
    location: string       # path:line
    evidence: string
    ruling: string         # the orchestrator's instruction to the fixer
```

Only accepted findings appear. Dismissed findings and raw reviewer prose are never included.

### Run journal

```
SCHEMA:
run_base: string           # commit OID
waves:
  - wave_base: string      # commit OID
    tasks: [{id, status, scope_audit, commit}]
    checkpoint: {round, findings, skipped_reason}
rounds:
  - n: integer
    reviewer_outputs: [path]
    findings: [{id, reviewer_severity, effective_severity, ruling, reason}]
    fix_commit: string
    build: pass | fail
dismissed: [{id, reason, round}]   # carried into later rounds for matching
```

Lives in scratch, outside the repository. Continuity of `dismissed` and finding `id` across rounds
is what lets a re-reported finding match a prior ruling instead of being re-adjudicated.

### Preflight

```
COMMAND:
git rev-parse --abbrev-ref HEAD
git status --porcelain
git rev-parse HEAD
```

Preconditions: branch is not `main`/`master` without explicit consent; `git status --porcelain`
returns empty. Postcondition: `RUN_BASE` bound to the third command's output. A non-empty status
stops the run — pre-existing changes contaminate every later scope audit.

### Assembling reviewer input

```
COMMAND:
git diff --no-renames "$RUN_BASE" HEAD      # final loop
git diff --no-renames "$WAVE_BASE" HEAD     # checkpoint
```

The diff text is written into the staged reviewer prompt before dispatch; reviewers additionally
get read-only repo access for surrounding context.

### Scope audit

```
COMMAND:
git diff --name-only -z --no-renames "$WAVE_BASE" "$BRANCH_TIP"
git ls-files --others --exclude-standard -z
```

Preconditions: `$WAVE_BASE` and `$BRANCH_TIP` resolved to commit OIDs, not refs. Postcondition: the
changed-path set is a subset of the task's declared `scope.files`. Rename detection is off so a
rename reports both paths. Untracked files are included — a worker adding an out-of-scope file must
be caught. Violation blocks the commit or merge; widening is a user-facing re-plan decision.

### Merge

```
COMMAND:
git merge --no-ff --no-edit "$BRANCH"
```

Precondition: the branch's scope audit passed. Postcondition: no conflict — disjoint scopes are
guaranteed at plan time, so a conflict means the precondition was violated; stop and re-plan.

### Corrected task schema (`writing-plans`)

```yaml
SCHEMA:
dependencies: [T1, T3]                 # optional; task IDs that must complete first
scope:
  files: [path/to/a.py, path/to/b.py]  # required when the task may run in parallel
```

Contract and acceptance remain prose fields in the task body, unchanged. Deleted from the schema:
`independent`, `never_touch`, `cooperative`, `risk`, and the `.contract` dependency suffix.

## DO-NOT-CHANGE fences

*Back-link: [logic.md → Scope & non-goals](./logic.md#scope--non-goals)*

| Region | Why fenced |
| --- | --- |
| `skills/subagent-driven-development/SKILL.md` frontmatter (lines 1–4) | Changing `name` breaks every cross-reference in seven sibling skills; changing `description` changes activation behavior, which is a separate tested axis |
| `docs/plans/**`, `docs/specs/**` | Historical records of past decisions; editing them falsifies the record |
| `skills/releasing-quirk/SKILL.md` | Carries an unrelated uncommitted edit from before this run; touching it would entangle unrelated work |
| `tests/` suites other than the four `test_sdd_*.py` | Out of scope; unrelated coverage that must keep passing |
| `skills/pi-dev/**` | The reviewer dispatch depends on its documented interface; this work consumes that interface, never modifies it |

## Always / Ask / Never

*Back-link: [logic.md → Decisions Locked](./logic.md#decisions-locked)*

**Always**

- Preserve the frontmatter byte-for-byte.
- Keep `quirk:writing-plans` and the rewritten skill agreeing on the task schema — they are edited
  together or not at all.
- Run the full pytest suite after deleting the four `test_sdd_*.py` files, to prove nothing else
  imported them.

**Ask**

- Any further conflict with a logic-spec Decisions-Locked entry (feasibility escalation).
- Any additional sibling skill discovered to encode deleted vocabulary.
- Whether to keep a deleted concept if the rewrite reveals it was load-bearing after all.

**Never**

- Restore captain-tier, per-task-review, or Phase 2/3 vocabulary in any file.
- Edit `main` directly — work stays on `sdd-simplification`.
- Commit `skills/releasing-quirk/SKILL.md` or the untracked `.claude/` and `.idea/` paths.
- Leave a sibling skill describing a control plane that no longer exists.

## Cross-cutting

*Back-link: [logic.md → Run journal](./logic.md#run-journal)*

**Security.** Reviewers get `read,grep,find,ls` only — never `bash`, `edit`, or `write`. `pi` has
no sandbox, so a mutating reviewer would have full user-level filesystem access. Acceptance command
text comes only from the reviewed plan, never from a worker report.

**Observability.** The run journal is the only durable record; it lives in scratch, outside the
repository, so a worker with edit tools cannot commit or clobber it.

**Rollback.** Every step is a git commit on a feature branch. The old skill is recoverable from
history at `0f184be`. No migration, no persisted state, no external system.

## Testing strategy

*Back-link: [logic.md → Scope & non-goals](./logic.md#scope--non-goals)*

Two axes, per `skills/writing-skills/SKILL.md:301-307`. This skill is **discipline-enforcing**, so
the Iron Law applies — no such skill without a failing test first.

**Behavioral (RED/GREEN),** method in `skills/writing-skills/testing-skills-with-subagents.md`.
RED: give a subagent the scenario *without* the skill and record the rationalizations it reaches
for. GREEN: write the minimal rule that closes those exact rationalizations. Required scenarios,
one per rule most likely to be rationalized away:

1. A wave where two tasks' scopes overlap — does the agent run them in parallel anyway?
2. A review round that finds and fixes three HIGHs — does the agent exit without re-reviewing?
3. A reviewer returning empty output — does the agent treat it as clean?
4. An implementer writing outside declared scope — does the agent commit anyway?
5. Round cap reached with a CRITICAL open — does the agent proceed to the finishing skill?
6. A red build mid-loop — does the agent dispatch reviewers over it?

**Activation,** method in `skills/writing-skills/activation-testing.md`. The frontmatter is
unchanged, so this is a regression check that the rewritten body did not degrade triggering.

**Repo suites.** `python3 -m pytest` must pass after the four `test_sdd_*.py` deletions. Per the
user's environment note, `python3 -m pytest` — not bare `pytest`.

The acceptance bar: every scenario above fails without the skill and passes with it, and the full
pytest suite is green.

## Non-goals

*Back-link: [logic.md → Scope & non-goals](./logic.md#scope--non-goals)*

- No new tooling. If a step is not expressible as a shell command the orchestrator runs directly,
  it does not belong in the skill.
- No test bodies in this document — scenarios name what must be covered, not how.
- Not specifying the rewritten SKILL.md's prose or section order; that is the implementer's call
  against the logic spec's protocol.
- Not touching `quirk:executing-plans`' own behavior, only the incorrect description of it that
  lives inside the skill being rewritten.
