---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code
---

# Writing Plans

## Overview

A plan is a **specification of intent, behavior, and contracts that a skilled implementor executes — not a transcript of code to paste.** It answers WHAT must be built and WHY this approach was chosen, and leaves HOW — the actual code — to the implementor, who has full repository context and will write better code than you can pre-write blind. **The implementor writes the code.**

Write for an implementor who has **zero context for our codebase** and needs the domain, constraints, interfaces, and acceptance bar made explicit. Delegate the implementation *approach* — but never delegate *completeness*: the errors to handle, the edge cases, and the test coverage are enumerated in the plan precisely because implementor judgment there is not trusted.

DRY. YAGNI. TDD. Frequent commits.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Context:** This should be run in a dedicated worktree (created by brainstorming skill).

**Save plans to:** `docs/quirk/plans/YYYY-MM-DD-<feature-name>.md`
- (User preferences for plan location override this default)

## The No-Code Rule

A plan **MUST NOT contain runnable implementation code or full test bodies.** Pasting code anchors the implementor to one approach, ages the moment the real code changes, duplicates work the implementor will redo anyway, and shifts reviewers from judging *decisions* to reviewing *syntax*.

Instead, every code-touching step carries:
- the exact **file path**,
- the **behavioral goal** (what it must do),
- the **contract** it must satisfy (preconditions, postconditions, invariants, error behavior),
- the **acceptance check** (an observable, testable success condition).

### When code IS allowed (the narrow exceptions)

Code is allowed ONLY when the literal text *is the contract another party must match exactly*. Tag every permitted block with one of these markers so the no-code audit is a grep, not a judgment call:

- `CONTRACT:` — an interface/signature sketch other tasks depend on (names, parameter/return types, error enums/status codes) — a shape, never a body
- `SCHEMA:` — exact data-schema field names/types, or an API request/response shape
- `COMMAND:` — exact shell/git commands the implementor runs verbatim
- `REGEX:` — a literal pattern that *is* the specification
- `CONFIG:` — exact config keys, env vars, or values where the literal string matters
- `PSEUDOCODE (justified):` — ≤3 lines, ONLY for a subtle algorithm where prose is genuinely ambiguous, with a one-line note on why prose failed

**Hard limits (mechanical, so review is a grep):**
- No runnable **function body**. No complete **test** (no `def test_…`, fixtures, setup, or mocks).
- Any code block without one of the tags above is a defect.
- **Expected-value data is contract, not code:** exact expected outputs, exception types, and error identifiers MUST be stated. An `input → expected output` table is a `CONTRACT:` and is allowed. What's forbidden is the surrounding test scaffolding.

**Migration:** Existing plans written in the old code-embedding style remain valid to execute — don't rewrite them just to strip code. New plans follow the no-code rule. Mark an obsolete plan `Status: Superseded` rather than editing it in place.

## Calibrate to the Executor

The plan header names the executor. Branch on it:

- **AI subagents** (`quirk:subagent-driven-development`): a fresh subagent receives only the pasted task text — no conversation history, limited repo-exploration budget. Bias toward MORE scaffolding: name the exact test file, the fixtures/builders to reuse, the assertion targets, and add reuse pointers (e.g. "reuse the builder at `tests/factories.py:40`"). The behavioral spec must be tight enough that two subagents would build the same thing.
- **Human implementor** (`quirk:executing-plans`): bias toward proportional brevity — enough contract and acceptance to remove ambiguity, no more.

**Tiebreaker** when proportionality and the "zero context" assumption pull in opposite directions: for subagent execution, add detail; for human execution, trim.

## Scope Check

If the spec covers multiple independent subsystems, it should have been broken into sub-project specs during brainstorming. If it wasn't, suggest breaking this into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified and what each one is responsible for. This is where decomposition decisions get locked in.

- Design units with clear boundaries and well-defined interfaces. Each file should have one clear responsibility.
- You reason best about code you can hold in context at once, and your edits are more reliable when files are focused. Prefer smaller, focused files over large ones that do too much.
- Files that change together should live together. Split by responsibility, not by technical layer.
- In existing codebases, follow established patterns. If the codebase uses large files, don't unilaterally restructure - but if a file you're modifying has grown unwieldy, including a split in the plan is reasonable.
- For each unit that other tasks or systems depend on, specify its interface as a behavioral **contract** — signature shape (names, parameter/return types), preconditions, postconditions, invariants — in prose or a `CONTRACT:` sketch, never a body. Accept broad input types; return specific types.

This structure informs the task decomposition. Each task should produce self-contained changes that make sense independently.

## Bite-Sized Task Granularity

Each step is one action in the red-green-commit rhythm. Reframe each as a behavioral instruction the implementor executes — not a container for code:
- "Write a failing test in `<file>` asserting `<behavior + exact expected values>`" - step
- "Run it; confirm it fails because `<reason>`" - step
- "Implement `<unit>` in `<file>` to satisfy `<contract>` and `<acceptance>`" - step
- "Run the tests; confirm they pass" - step
- "Commit" - step

Keep one behavior per red-green cycle. A non-trivial behavior may take longer than five minutes to implement, but it is still one test → one implementation → one verification → one commit.

## Task Independence (optional)

When the plan will be executed by **quirk:subagent-driven-development**, you can opt into the orchestrator's parallel modes by declaring task independence and scope. All four fields are optional — plans without them produce singleton waves (one task per wave, executed sequentially), which is the legacy behaviour.

Declare any of these fields directly in the task heading area, in a fenced YAML-like block immediately under the `### Task N: ...` heading:

```yaml
independent: true                     # this task can run alongside any other independent task in its eligible wave
dependencies: [T1, T3]                # task ids that must complete before this one starts
scope:
  files: [path/to/a.py, path/to/b.py] # files this task is expected to touch (used for IN_PLACE_PARALLEL gate)
cooperative: true                     # task needs live cross-task negotiation (TEAM mode only — rare)
```

**Guidance:**

- Most tasks should use `independent: true` (with optional `scope.files`) when they truly stand alone. The orchestrator will then group them into parallel waves.
- Use `dependencies` whenever a task needs another task's output — e.g., a test task that requires a feature task to ship first.
- Use `scope.files` when you want the orchestrator to consider `IN_PLACE_PARALLEL` mode (lower overhead than worktrees). The gate fires only when every task in the wave declares `scope.files` and no two scopes overlap.
- Use `cooperative: true` very rarely — only when two or more tasks in the same wave need to negotiate interfaces during work (the orchestrator uses TEAM mode in that case, which relaxes the "fresh subagent per task" guarantee within the wave).
- Tasks that declare none of these fields fall back to a singleton wave (`SEQUENTIAL` mode). This is safe and matches legacy behaviour.

See **quirk:subagent-driven-development → The Process → Step 0b** for the full wave-compute and mode-decision logic.

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use quirk:subagent-driven-development (recommended) or quirk:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. "Follow the step exactly" means **satisfy the stated acceptance criteria** — if a contract is ambiguous, ask before guessing.

**Status:** Draft | Under Review | Approved | Superseded

**Goal:** [One sentence describing what this builds]

**Goals / Non-Goals:** [bullet lists; non-goals name things a reader might reasonably assume are in scope but that are deliberately excluded]

**Architecture:** [2-3 sentences about approach]

**Alternatives considered:** [the chosen approach + at least one honest rejected alternative + why]

**Tech Stack:** [Key technologies/libraries]

**Constraints:** [hard constraints to preserve (regulatory, security, existing APIs) vs. choices delegated to the implementor]

**Cross-cutting:** [security / observability / data migration / rollback — where relevant]

---
```

Match plan size to task size: a ~2-day change is ~1-2 pages. If writing the plan takes longer than implementing it, the altitude is wrong.

## Task Structure

Every task follows this template. The `independent` / `dependencies` / `scope.files` / `cooperative` block is optional but **strongly recommended** — it lets `quirk:subagent-driven-development` execute the plan in parallel waves instead of strictly sequentially. Most well-decomposed tasks should declare `independent: true` plus `scope.files`.

Notice what the template does NOT contain: no test body, no implementation body. Each step states behavior, contract, and acceptance — the implementor writes the code. The only code blocks are tagged exceptions (`CONTRACT:`, `COMMAND:`).

````markdown
### Task N: Daily metrics summary

```yaml
# Optional — drives parallel execution under quirk:subagent-driven-development.
# Omit any line that doesn't apply. Omit the whole block to fall back to sequential.
independent: true
dependencies: []
scope:
  files: [src/metrics/summary.py, tests/metrics/test_summary.py]
```

**Files:**
- Create: `src/metrics/summary.py`
- Modify: `src/metrics/__init__.py:1-12` (export `summarize`)
- Test: `tests/metrics/test_summary.py`

**Contract** — what `summarize` must guarantee:
- Preconditions: accepts any iterable of `Record` (possibly empty); records may arrive unsorted.
- Postconditions: returns a `Summary` with `count` (int) and `total` (Decimal); never mutates the input.
- Invariants: `total` equals the sum of `record.amount` over all records.
- Errors: a record with a non-numeric `amount` raises `ValueError("amount must be numeric")`.

**Acceptance:** `summarize` returns correct `count`/`total` for empty, single, and mixed inputs, and raises on a non-numeric amount.

- [ ] **Step 1: Write the failing test**

  In `tests/metrics/test_summary.py`, assert:
  - Given an empty iterable, When summarized, Then `count == 0` and `total == Decimal("0")`.
  - Given records `[10.00, 5.50]`, When summarized, Then `count == 2` and `total == Decimal("15.50")`.
  - Given a record whose `amount` is `"x"`, When summarized, Then it raises `ValueError` with message `"amount must be numeric"`.

  Reuse the `make_record(...)` builder at `tests/factories.py:40`.

- [ ] **Step 2: Run test to verify it fails**

  Run: `pytest tests/metrics/test_summary.py -v`
  Expected: FAIL — `summarize` not defined

- [ ] **Step 3: Implement to satisfy the contract**

  Implement `summarize` in `src/metrics/summary.py` to meet the Contract and Acceptance above, then export it from `src/metrics/__init__.py`. The interface other tasks depend on:

  `CONTRACT:`
  ```
  def summarize(records: Iterable[Record]) -> Summary: ...
  ```

- [ ] **Step 4: Run test to verify it passes**

  Run: `pytest tests/metrics/test_summary.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**

  `COMMAND:`
  ```bash
  git add src/metrics/summary.py src/metrics/__init__.py tests/metrics/test_summary.py
  git commit -m "feat(metrics): add daily summary aggregation"
  ```
````

## No Vagueness

A plan fails on **ambiguity**, not on the absence of code. These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" — name WHICH errors and the exact behavior
- "Handle edge cases" — name the cases and their expected outcomes
- "Write tests for the above" — give the assertion list (behavior + exact expected values)
- "Similar to Task N" — restate the contract; the implementor may read tasks out of order
- A step that states neither a behavioral goal nor an acceptance check
- An interface or contract referenced but never specified
- A requirement open to two or more reasonable interpretations
- References to types, functions, or methods not defined in any task
- **Pasting a full implementation body or full test body** — that is the implementor's job; it anchors them and ages immediately. Specify behavior, contract, and acceptance instead.

## Remember
- Exact file paths always
- Complete **behavior** in every step — if a step changes code, state the behavioral goal, the contract it must satisfy, and the acceptance check. The implementor writes the code.
- Exact commands with expected output
- State the **why** for every non-obvious decision (rationale + rejected alternative) so the implementor can adapt when context shifts
- DRY, YAGNI, TDD, frequent commits

## Self-Review

After writing the complete plan, look at the spec with fresh eyes and check the plan against it. This is a checklist you run yourself — not a subagent dispatch.

**1. Spec coverage:** Skim each section/requirement in the spec. Can you point to a task that implements it? List any gaps.

**2. Vagueness scan:** Search your plan for the red flags in the "No Vagueness" section above. Fix them.

**3. Altitude / no-code audit:** Find every code block. Each must carry a tag (`CONTRACT:` / `SCHEMA:` / `COMMAND:` / `REGEX:` / `CONFIG:` / `PSEUDOCODE (justified):`). Any untagged block, any runnable function body, or any full test body → remove it and replace with behavior + contract + acceptance.

**4. Ambiguity probe:** For each requirement, ask whether a skilled implementor could reasonably build two or more different things. If yes, tighten the behavioral spec — not by adding code.

**5. Contract consistency:** Do the signatures, method names, and property names in your `CONTRACT:` sketches match across tasks? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 is a bug.

**6. Parallelism declarations:** For each task, did you accurately declare `independent: true` / `dependencies: [...]` / `scope.files: [...]`? Tasks that genuinely don't depend on each other should say so — otherwise the orchestrator falls back to sequential execution and leaves throughput on the table. Tasks that share a target file MUST run sequentially — express that with `dependencies`, never with overlapping `scope.files` and `independent: true` together.

If you find issues, fix them inline. No need to re-review — just fix and move on. If you find a spec requirement with no task, add the task.

## Execution Handoff

After saving the plan, offer execution choice:

**"Plan complete and saved to `docs/quirk/plans/<filename>.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?"**

**If Subagent-Driven chosen:**
- **REQUIRED SUB-SKILL:** Use quirk:subagent-driven-development
- Fresh subagent per task + three-pass review (spec, quality, Codex adversarial); orchestrator computes parallel waves from the task fields above

**If Inline Execution chosen:**
- **REQUIRED SUB-SKILL:** Use quirk:executing-plans
- Batch execution with checkpoints for review
