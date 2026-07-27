---
name: writing-plans
description: The planning rubric the execution skills run in-context at the start of a run — turns the tech spec (tech.md) when present, else the logic spec / requirements, into a task breakdown (contracts, acceptance, parallelism) before code
---

# Writing Plans

## Overview

> **How this skill is used:** Planning is **not a separate step** anymore. The execution
> skills (`quirk:subagent-driven-development` and `quirk:executing-plans`) invoke this skill
> as their first phase to build the plan **in the orchestrator's working context** — the
> conversation plus a TodoWrite task list — and then proceed straight into execution. A plan
> *file* is optional (see "Where the plan lives"). This rubric defines *what a good plan
> contains*; the calling skill owns *when* it runs and *where* the plan is held.

A plan is a **specification of intent, behavior, and contracts that a skilled implementor executes — not a transcript of code to paste.** It answers WHAT must be built and WHY this approach was chosen, and leaves HOW — the actual code — to the implementor, who has full repository context and will write better code than you can pre-write blind. **The implementor writes the code.**

Write for an implementor who has **zero context for our codebase** and needs the domain, constraints, interfaces, and acceptance bar made explicit. Delegate the implementation *approach* — but never delegate *completeness*: the errors to handle, the edge cases, and the test coverage are enumerated in the plan precisely because implementor judgment there is not trusted.

DRY. YAGNI. TDD. Frequent commits.

**Announce at start:** "I'm building the implementation plan in context (writing-plans rubric)."

**Context:** Runs inside the execution skill's worktree (the execution skill, or brainstorming before it, owns worktree setup).

## Where the plan lives

**Default: in context, not a file.** The plan is the task breakdown the orchestrator holds in
the conversation **and writes into a TodoWrite list** — one item per task, each carrying its
contract / acceptance / parallelism fields. TodoWrite is the durable home: it survives context
compaction, so the breakdown isn't lost if the conversation is summarized mid-run.

**Persist to a file only when you need to** — on explicit request, or to hand the plan to a
*separate session* (the `quirk:executing-plans` cross-session path), or for a durable record.
When you do, save to `docs/quirk/plans/YYYY-MM-DD-<feature-name>.md` (user preferences override
this location). Persisting is a copy of the in-context plan, not a precondition for execution.

## The No-Code Rule

A plan **MUST NOT contain runnable implementation code or full test bodies.** Pasting code anchors the implementor to one approach, ages the moment the real code changes, duplicates work the implementor will redo anyway, and shifts reviewers from judging *decisions* to reviewing *syntax*.

Instead, every code-touching step carries:
- the exact **file path**,
- the **behavioral goal** (what it must do),
- the **contract** it must satisfy (preconditions, postconditions, invariants, error behavior),
- the **acceptance check** — one or more literal, copy-runnable commands with exact flags and an expected result, never a prose description of a check.

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

## Consuming `tech.md`

When a reviewed `tech.md` exists for this work (the sibling of `logic.md`, in the same directory; by default `docs/quirk/specs/YYYY-MM-DD-<topic>/tech.md`), it is the source of truth for anything code-anchored — architecture, file-level contracts, DO-NOT-CHANGE fences. Absent a `tech.md`, plan from the logic spec / requirements directly; there is nothing to re-resolve or excerpt.

**Re-resolve once, at plan-build.** Before the File Structure pass, re-resolve every path/symbol `tech.md` cites against the live tree — `tech.md` is a map authored earlier, not the territory, and anchors drift. On a mismatch, correct `tech.md` itself (and log the correction) before decomposition locks in, so tasks are built against ground truth.

**Excerpt contracts verbatim, at dispatch.** A task that depends on a `tech.md` contract does not restate or summarize it in the task text — it excerpts the contract **verbatim**, because a dispatched subagent never reads `tech.md` (it receives only the pasted task text). Each excerpt must:
- include **every DO-NOT-CHANGE fence whose scope intersects the task's files** — dropping one is a defect: the subagent could then edit inside a fenced region unaware it's fenced.
- cite the `tech.md` section id it came from.
- come from `tech.md` directly, pasted at the last moment — never paraphrased, never reconstructed from memory.

**Re-resolve again, per dispatch.** Immediately before each task is dispatched, re-resolve every pointer in that task's excerpt against the live tree — an earlier wave may have already moved what `tech.md` pointed at. On a mismatch, update both `tech.md` and the excerpt before dispatching.

**Keep `tech.md` in sync.** When a task *intentionally* changes a symbol `tech.md` points to (e.g. renames a function), update `tech.md` in the same commit. Skip this and a later wave's excerpt — and the reviewer that checks code against it — will certify the drift instead of catching it.

## Scope Check

If the upstream input — the tech spec (`tech.md`) when present, else the logic spec / requirements — covers multiple independent subsystems, it should have been broken into sub-project specs during brainstorming. If it wasn't, suggest breaking this into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified and what each one is responsible for. This is where decomposition decisions get locked in. Also build a **file-coupling map** from imports and shared files, then use it to minimize cross-task coupling before declaring `dependencies` or computing waves.

When the work changes a protocol, vocabulary, or event set, perform a **coherence sweep** before locking that map: use repository-wide grep commands to enumerate every file that references the changed old or new terms. Every referencing file MUST either be scoped into a task or explicitly recorded as `unchanged, verified consistent`. Search for the **vocabulary terms themselves**, not just the names of the components being changed — a file can encode a protocol without ever naming the skill or module that owns it, and those are exactly the files a name-based search misses.

- Design units with clear boundaries and well-defined interfaces. Each file should have one clear responsibility.
- You reason best about code you can hold in context at once, and your edits are more reliable when files are focused. Prefer smaller, focused files over large ones that do too much.
- Files that change together should live together. Split by responsibility, not by technical layer.
- In existing codebases, follow established patterns. If the codebase uses large files, don't unilaterally restructure - but if a file you're modifying has grown unwieldy, including a split in the plan is reasonable.
- For each unit that other tasks or systems depend on, specify its interface as a behavioral **contract** — signature shape (names, parameter/return types), preconditions, postconditions, invariants — in prose or a `CONTRACT:` sketch, never a body. Accept broad input types; return specific types.

This structure informs the task decomposition. Each task should produce self-contained changes that make sense independently. Partition by **vertical slices of user-visible behavior**, not horizontal technical layers such as "all API routes"; vertical slices create fewer inherent cross-wave dependencies.

Treat hub-file isolation as a **scored heuristic, not a mandate**. Prefer assigning a hub change to the vertical slice that owns the behavior. Carve out a standalone hub task only when no single slice owns it, and record the explicit rationale plus the serialized integration dependency; making every hub a separate task recreates horizontal decomposition.

### Task-Boundary Granularity Economics

Every task pays a fixed pipeline tax: dispatch, scope audit, acceptance run, commit, and merge. Price a split rather than treating it as free:

- Split only when the result lands tasks in **different waves** and therefore buys real parallelism. A split whose halves stay in the same sequential run buys nothing and pays the tax twice.
- Collapse a contiguous run of sequentially-dependent work into one task.
- Merge a task with a projected diff under roughly 50–100 lines into its neighbor.
- Preserve review isolation with **commit boundaries inside the task**: commit each sub-step separately instead of paying for separate task pipelines.
- Set the target task count from achievable wave width, never from the number of requirement bullets.

## Bite-Sized Task Granularity

Each step is one action in the red-green-commit rhythm. Reframe each as a behavioral instruction the implementor executes — not a container for code:
- "Write a failing test in `<file>` asserting `<behavior + exact expected values>`" - step
- "Run it; confirm it fails because `<reason>`" - step
- "Implement `<unit>` in `<file>` to satisfy `<contract>` and `<acceptance>`" - step
- "Run `<literal copy-runnable test command with exact flags>`; confirm the stated expected result" - step
- "Commit" - step

Keep one behavior per red-green cycle. A non-trivial behavior may take longer than five minutes to implement, but it is still one test → one implementation → one verification → one commit.

## Task Independence

When the plan will be executed by **quirk:subagent-driven-development**, declare dependencies and scope so the orchestrator can compute waves. `dependencies` is optional — a task declaring none is eligible for the first wave. `scope.files` is **required on every task**.

Declare them in a fenced YAML-like block immediately under the `### Task N: ...` heading:

```yaml
dependencies: [T1, T3]                 # task IDs that must complete before this one starts
scope:
  files: [path/to/a.py, path/to/b.py]  # every file this task may create or modify
```

**Guidance:**

- Use `dependencies` for genuine semantic ordering — one task needing another's output — never merely for file overlap. File overlap is handled by scope, not by dependencies.
- `scope.files` is **required on every task**, whether or not it will run in parallel. It is the boundary the orchestrator audits each task's diff against before committing, and the same list it hands the implementer as a hard fence — a task without it has neither. An incomplete list reads as a scope violation and stops the wave.
- Tasks in the same wave run in parallel **only if their `scope.files` are disjoint**. Any shared path forces the wave to run sequentially — there is no small-overlap exemption: the two branches either conflict at merge, costing the parallelism the overlap was meant to buy, or auto-merge into a file version neither agent tested.
- List every file the task will touch, including tests and any index/barrel file it must re-export from. Under-declaring is the common failure: the task gets blocked mid-wave for touching a file it always needed.

## Plan Document Header

**Every plan MUST start with this header:**

When a `tech.md` exists, the **Architecture**, **Tech Stack**, **Constraints**, and **Cross-cutting** fields below become **one-line pointers** into the corresponding `tech.md` section (e.g. `Architecture: see tech.md#architecture`), instead of restated prose — `tech.md` is the single source of truth for that material, and restating it here duplicates and drifts. When there is no `tech.md`, author these fields inline as before. Separately, **Alternatives considered** always points to the logic spec (which owns rationale, and — unlike `tech.md` — always exists): `Alternatives considered: see logic.md#key-decisions--rationale`. If the plan is **persisted to a file** (see "Where the plan lives"), any pointer must carry the **full path** — `docs/quirk/specs/YYYY-MM-DD-<topic>/tech.md#architecture` or `docs/quirk/specs/YYYY-MM-DD-<topic>/logic.md#key-decisions--rationale` — because a bare `tech.md#…` or `logic.md#…` resolves relative to `docs/quirk/plans/` and dangles identically. `Goal`, `Goals / Non-Goals`, and `Status` are always authored inline.

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use quirk:subagent-driven-development (recommended) or quirk:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. "Follow the step exactly" means **satisfy the stated acceptance criteria** — if a contract is ambiguous, ask before guessing.

**Status:** Draft | Superseded   (the plan is reviewed by an agent automatically before execution — there is no human approval gate)

**Goal:** [One sentence describing what this builds]

**Goals / Non-Goals:** [bullet lists; non-goals name things a reader might reasonably assume are in scope but that are deliberately excluded]

**Architecture:** [tech spec exists → one-line pointer, e.g. "see `tech.md#architecture`" (full path `docs/quirk/specs/YYYY-MM-DD-<topic>/tech.md#architecture` if persisted to a file); no tech spec → 2-3 sentences about approach, authored inline]

**Alternatives considered:** [logic spec owns rationale → pointer, e.g. "see `logic.md#key-decisions--rationale`" (full path `docs/quirk/specs/YYYY-MM-DD-<topic>/logic.md#key-decisions--rationale` if persisted to a file); no logic-spec rationale → the chosen approach + at least one honest rejected alternative + why]

**Tech Stack:** [tech spec exists → covered under Architecture, e.g. "see `tech.md#architecture`"; no tech spec → key technologies/libraries]

**Constraints:** [tech spec exists → pointer, e.g. "see `tech.md#always--ask--never`"; no tech spec → hard constraints to preserve (regulatory, security, existing APIs) vs. choices delegated to the implementor]

**Cross-cutting:** [tech spec exists → pointer, e.g. "see `tech.md#cross-cutting`"; no tech spec → security / observability / data migration / rollback — where relevant]

---
```

Match plan size to task size: a ~2-day change is ~1-2 pages. If writing the plan takes longer than implementing it, the altitude is wrong.

## Task Structure

Every task follows this template. Use the scope and dependency declarations described in **Task Independence** above; `dependencies` is optional, but every task MUST declare `scope.files`.

Notice what the template does NOT contain: no test body, no implementation body. Each step states behavior, contract, and acceptance — the implementor writes the code. The only code blocks are tagged exceptions (`CONTRACT:`, `COMMAND:`).

The task's **Acceptance:** field MUST contain one or more literal, copy-runnable commands with every flag fixed, plus the expected result. Never substitute prose such as "run the relevant tests" or a description of what someone should check; the orchestrator and the worker must be able to execute exactly the same command without choosing different flags. This prevents a real dogfood-run failure where the two ran the same check with different flags and got different pass/fail results.

````markdown
### Task N: Daily metrics summary

```yaml
# Drives wave computation under quirk:subagent-driven-development.
dependencies: []
scope:
  files: [src/metrics/summary.py, src/metrics/__init__.py, tests/metrics/test_summary.py]
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

**Acceptance (`COMMAND:`):** `pytest tests/metrics/test_summary.py -v`

Expected: exits 0; the passing tests demonstrate that `summarize` returns correct `count`/`total` for empty, single, and mixed inputs, and raises on a non-numeric amount.

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
- An acceptance criterion stated as prose rather than a literal, copy-runnable command with exact flags
- An interface or contract referenced but never specified
- A requirement open to two or more reasonable interpretations
- References to types, functions, or methods not defined in any task
- **Pasting a full implementation body or full test body** — that is the implementor's job; it anchors them and ages immediately. Specify behavior, contract, and acceptance instead.

## Remember
- Exact file paths always
- Complete **behavior** in every step — if a step changes code, state the behavioral goal, the contract it must satisfy, and the acceptance check. The implementor writes the code.
- Every acceptance criterion is an exact, copy-runnable command with all flags and expected output — never a prose description of a check
- State the **why** for every non-obvious decision (rationale + rejected alternative) so the implementor can adapt when context shifts
- DRY, YAGNI, TDD, frequent commits

## Self-Review

After writing the complete plan, look at the tech spec (`tech.md`) when present, else the logic spec / requirements, with fresh eyes and check the plan against it. This is a checklist you run yourself — not a subagent dispatch.

**1. Spec coverage:** Skim each section/requirement in the tech spec (`tech.md`) when present, else the logic spec / requirements. Can you point to a task that implements it? List any gaps.

**2. Vagueness scan:** Search your plan for the red flags in the "No Vagueness" section above. Fix them.

**3. Altitude / no-code audit:** Find every code block. Each must carry a tag (`CONTRACT:` / `SCHEMA:` / `COMMAND:` / `REGEX:` / `CONFIG:` / `PSEUDOCODE (justified):`). Any untagged block, any runnable function body, or any full test body → remove it and replace with behavior + contract + acceptance.

**4. Ambiguity probe:** For each requirement, ask whether a skilled implementor could reasonably build two or more different things. If yes, tighten the behavioral spec — not by adding code.

**5. Contract consistency:** Do the signatures, method names, and property names in your `CONTRACT:` sketches match across tasks? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 is a bug.

**6. Acceptance-command audit:** Inspect every acceptance criterion. Is each one a literal, copy-runnable command with exact flags and an expected result, rather than prose that leaves the orchestrator and the worker to choose how to run the check? Fix every mismatch.

**7. Coherence sweep:** If the plan changes a protocol, vocabulary, or event set, did you grep-enumerate every file referencing the changed old or new terms? Verify that each result is either scoped into a task or explicitly recorded as `unchanged, verified consistent`. Check that you searched for the vocabulary terms themselves, not only the names of the components being changed — a file can encode a protocol without naming the skill or module that owns it.

**8. Scope and dependency declarations:** For each task, did you declare `scope.files` accurately and `dependencies` only for genuine semantic ordering? Every task needs a complete `scope.files` — including its tests and any index/barrel file it re-exports from — because the orchestrator audits each task's diff against that list and an under-declared file stops the wave. Tasks that genuinely don't depend on each other should say so, otherwise execution falls back to sequential and leaves throughput on the table. Tasks sharing any file path cannot run in parallel at all: reserve `dependencies` for one task needing another's output, never for file overlap.

If you find issues, fix them inline. No need to re-review — just fix and move on. If you find a requirement in the tech spec (`tech.md`) when present, else the logic spec, with no task, add the task.

## After the plan: agent review, then execute

There is **no separate handoff step and no human approval gate** — you are already inside the
execution skill that invoked this rubric. Two things happen next, both owned by the calling skill:

1. **Agent review (default).** Dispatch the plan-document reviewer
   (`plan-document-reviewer-prompt.md`) on the in-context plan. Apply its fixes inline. This
   replaces the old human "Under Review → Approved" gate.
2. **Execute.** Continue in the same skill — `quirk:subagent-driven-development` computes parallel
   waves from the task fields above and runs the per-task pipeline; `quirk:executing-plans`
   executes sequentially. No "which approach?" prompt here: the choice of execution skill was
   already made when one of them invoked this rubric.
