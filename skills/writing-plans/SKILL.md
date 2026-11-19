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

**Re-resolve again, per dispatch.** Immediately before each task is dispatched, re-resolve every pointer in that task's excerpt against the live tree — a task that merged earlier may have already moved what `tech.md` pointed at. On a mismatch, update both `tech.md` and the excerpt before dispatching.

**Keep `tech.md` in sync.** When a task *intentionally* changes a symbol `tech.md` points to (e.g. renames a function), update `tech.md` in the same commit. Skip this and a later task's excerpt — and the reviewer that checks code against it — will certify the drift instead of catching it.

## Scope Check

If the upstream input — the tech spec (`tech.md`) when present, else the logic spec / requirements — covers multiple independent subsystems, it should have been broken into sub-project specs during brainstorming. If it wasn't, suggest breaking this into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified and what each one is responsible for. This is where decomposition decisions get locked in. Also build a **file-coupling map** from imports and shared files, then use it to minimize cross-task coupling before declaring `dependencies`.

When the work changes a protocol, vocabulary, or event set, perform a **coherence sweep** before locking that map: use repository-wide grep commands to enumerate every file that references the changed old or new terms. Every referencing file MUST either be scoped into a task or explicitly recorded as `unchanged, verified consistent`. Search for the **vocabulary terms themselves**, not just the names of the components being changed — a file can encode a protocol without ever naming the skill or module that owns it, and those are exactly the files a name-based search misses.

- Design units with clear boundaries and well-defined interfaces. Each file should have one clear responsibility.
- You reason best about code you can hold in context at once, and your edits are more reliable when files are focused. Prefer smaller, focused files over large ones that do too much.
- Files that change together should live together. Split by responsibility, not by technical layer.
- In existing codebases, follow established patterns. If the codebase uses large files, don't unilaterally restructure - but if a file you're modifying has grown unwieldy, including a split in the plan is reasonable.
- For each unit that other tasks or systems depend on, specify its interface as a behavioral **contract** — signature shape (names, parameter/return types), preconditions, postconditions, invariants — in prose or a `CONTRACT:` sketch, never a body. Accept broad input types; return specific types.

Require single-owner test topology: every created or modified test file belongs to one owning
task's `scope.files`. A test file in two tasks' scopes serializes them: the scheduler never runs
them at the same time. Assign tests with their owning behavior so parallel
tasks never collide on, or get blocked by, a shared test file.

This structure informs the task decomposition. Each task should produce self-contained changes that make sense independently. Partition by **vertical slices of user-visible behavior**, not horizontal technical layers such as "all API routes"; vertical slices create fewer inherent cross-task dependencies.

Treat hub-file isolation as a **scored heuristic, not a mandate**. Prefer assigning a hub change to the vertical slice that owns the behavior. Carve out a standalone hub task only when no single slice owns it, and record the explicit rationale plus the serialized integration dependency; making every hub a separate task recreates horizontal decomposition.

### Task-Boundary Granularity Economics

Every task pays a fixed pipeline tax: dispatch, scope audit, acceptance run, commit, and merge. Price a split rather than treating it as free:

- Split only when it buys real parallelism: the halves share no file and neither needs the other's output, so they **run at the same time**, or another task needs only one half and can **start as soon as that half merges**. A split whose halves share a file or depend on each other runs one after the other anyway, buys nothing, and pays the tax twice.
- Collapse a contiguous run of sequentially-dependent work into one task.
- Merge a task with a projected diff under roughly 50–100 lines into its neighbor.
- Preserve review isolation with **commit boundaries inside the task**: commit each sub-step separately instead of paying for separate task pipelines.
- Set the target task count from achievable parallel width, never from the number of requirement bullets.

### Shaping the DAG for wall-clock time

SDD runs independent tasks at the same time, so a run lasts about as long as its **critical path**:
the chain of dependent tasks with the most implementer time. Each dependency level costs at least
the longer of its build and its checkpoint review, and one long task holds up everything after it.
Apply the four rules below, in order, once the file-coupling map exists and before writing tasks.
They change the graph and the file layout, never the behavior that gets built. Every merge or split
still has to satisfy Task Independence: disjoint `scope.files` for tasks that can run at the same
time, and acceptance commands for every task.

**Size and time.** Size a task by its projected hand-written diff: source, tests, and fixtures, but
not lockfiles, build output, or other generated files. Estimate its wall time as three terms, to
compare paths rather than to promise a finish time:

- **Floor:** about 1–2 minutes for any task, however small.
- **Model time:** expected output tokens divided by about 170 tokens a second. Code and tests cost
  about 30 output tokens per hand-written line, thinking and narration included, so roughly 350
  lines a model-minute; fixtures and other data cost far less. Model time divides when a task
  splits.
- **Tool time:** installs, builds, headless browsers, and test runs. It does not divide: every piece
  of a split reruns it. It also grows when parallel tasks share one machine, since concurrent
  installs, browsers, and test runs compete with each other.

Two limits follow, because a minute only costs run time on the critical path:

- **On the critical path, aim for 3–6 minute tasks.** A task there whose expected model time is over
  about 5 minutes (about 1,700 hand-written lines) is a split candidate under rule 3.
- **Everywhere, the size ceiling** is about 2,000 hand-written lines or 20 hand-written files, about
  6 model-minutes and 10 wall-minutes with tools; crossing either limit crosses the ceiling. Off the
  critical path a bigger task costs no run time, and fewer tasks means fewer orchestrator accepts,
  tool reruns, and contract boundaries. So the ceiling bounds only what size does cost there: the
  cheaper implementer's reliability and the reviewer's diff. It bounds every merge in this section
  and the merges and collapses in Granularity Economics above.

1. **Pin shared shapes in the spec, not in edges.** A task that could build and pass its own
   acceptance against a pinned shape, such as sample data or fixtures, a type definition, an API
   request/response, or a schema, has a `contract` dependency, and that is not an edge. The spec
   pins the shape (`tech.md`'s Data models / schemas, per quirk:writing-specs; the plan's
   `CONTRACT:` or `SCHEMA:` when there is no `tech.md`). The dependent builds against it, keeping its
   own sample data in its own scope or mocking the API from the pinned shape. A check that needs
   another task's real output, such as rendering that task's real fixtures, moves to the harness task
   in rule 4. If no spec pins the shape yet, pin it before dropping the edge. A pinned signature does
   not turn an import into a `contract`: when acceptance runs the other task's real code, the edge is
   `code`. A spec's build-phase list orders delivery, not tasks; it becomes an edge only where a later
   phase needs an earlier phase's code.
2. **Merge same-file follow-ons.** When one task only extends a file another task owns, merge the two
   while the combined task stays under the size ceiling. Over it, restructure so the follow-on gets
   its own file behind a pinned contract; it then takes a `code` edge only if it still calls the
   first task's code. Fold a late addition to the spec into the tasks that own its files instead of
   appending tasks after them.
3. **Split long tasks along disjoint file scopes.** Split any task over the size ceiling. On the
   critical path, also split a task whose expected model time is over about 5 minutes, when its files
   divide cleanly (separate views, separate routes), the pieces can run at the same time, and the path
   still gets shorter once each piece's floor, its rerun of the tool time, and the seam are counted.
   Pieces that would run one after another never shorten the path. Never split along a contract
   boundary the spec doesn't pin: pin it first, or keep the work in one task. Every shared file, such as a `types.ts`, a theme stylesheet, or a `package.json`, gets
   exactly one owner among the tasks that can run at the same time; a task that depends on the owner
   may extend the file later, as the harness task extends `package.json` scripts. When the pieces
   must import a shared file to compile, that owner is a small **seam task**. It writes the shared
   files, from shapes the spec pins first, plus the composition point (entry, router, registry) the
   pieces register into, so that the seam never imports the pieces. The pieces take a `code` edge on
   the seam.
4. **Put cross-cutting test harnesses in one late task.** End-to-end and served-app tests, other
   checks that need more than one task's real output, and the harness config they need (an `e2e/`
   directory, its `package.json` scripts) go in one task that depends on everything it exercises.
   Feature tasks keep their unit and component checks in their own scope and never take an edge on
   the harness task. A new feature adds its scenarios to the harness task, which then depends on that
   feature's task, instead of hanging a new task off the harness.

**Task count.** Each task adds a serial orchestrator step (scope audit, an acceptance rerun, commit,
merge) of a few seconds to about 90, mostly the acceptance rerun, and each cross-task contract
boundary is where checkpoint findings collect, at about 5–10 minutes per fix round. Keep the task
count at or under the critical-path estimate in minutes divided by 1.5 (the worst-case accept, in
minutes), about 12 for an 18-minute path, so the orchestrator's serial work fits inside the run instead of lengthening it. The cap would
rise if acceptance moved into the implementer, leaving the orchestrator only the audit and merge.

**Effort.** Every task carries an `effort` hint (see Task Independence), because effort changes how much
the implementer thinks, and only about half of an implementer's output tokens are code or edits:

- `lower`: mechanical work, such as fixtures, docs and skill text, and test wiring.
- `default`: ordinary feature work.
- `higher`: a task that owns a seam (shared state, a cross-task contract, a seam task under rule 3).

Fixers, which the execution skill dispatches, run at `default` or `higher`.

**Trade-offs.** Merging gives the cheaper implementer model a bigger task and the reviewer a bigger
diff, which is what the size ceiling bounds. Splitting needs the shared types pinned first, costs a
seam task, reruns the tool time in every piece, adds an orchestrator accept, and opens a contract
boundary where defects collect. Moving checks into the harness task means an
integration break surfaces late, in one place. Name the trade-off in the plan when a rule is applied
at the edge of its range.

**Report the shape.** Right after the plan header, before the first task, write a `DAG shape` block.
It holds the depth (the most tasks on any one dependency chain), the task count against its cap, the
estimated critical path in wall minutes with the chain that sets it, any critical-path task left
over the 3–6 minute target with the reason, every direct edge with its kind (see Task
Independence) and reason, and every edge the rules removed, with the rule that removed it. Depth and
the critical path can come from different chains; report both. SDD's shape preview counts its
critical path in tasks, which is this block's depth. A reader should be able to audit the
graph from this block alone:

```markdown
**DAG shape:** depth 3 · 8 tasks (cap 12) · critical path ≈ 18 min: T1 steps validator (5) → T3 server app mode + chat (9) → T8 e2e (4)
- T3 ← T1 · code: imports `validate_step` from `steps.py`
- T3 ← T2 · code: reads and writes session state through `appstate.py`
- T5, T6 ← T4 · code: shell views import `types.ts` and `theme.css` from the shell seam
- T8 ← T3, T5, T6 · code: e2e starts the real server and drives the built shell
- removed: shell ← steps validator · contract (rule 1): the shell renders its own sample steps; the real-fixture render moved to T8
- removed: chat ← server app mode · same-file (rule 2): merged into T3
- over target: T3 (9 min) stays one task; its pieces would share `companion.py` and run one after another (rule 3)
```

## Bite-Sized Task Granularity

Each step is one action in the red-green-commit rhythm. Reframe each as a behavioral instruction the implementor executes — not a container for code:
- "Write a failing test in `<file>` asserting `<behavior + exact expected values>`" - step
- "Run it; confirm it fails because `<reason>`" - step
- "Implement `<unit>` in `<file>` to satisfy `<contract>` and `<acceptance>`" - step
- "Run `<literal copy-runnable test command with exact flags>`; confirm the stated expected result" - step
- "Commit" - step

Keep one behavior per red-green cycle. A non-trivial behavior may take longer than five minutes to implement, but it is still one test → one implementation → one verification → one commit.

## Task Independence

When the plan will be executed by **quirk:subagent-driven-development**, declare dependencies and scope so the orchestrator can dispatch each task the moment its own dependencies merge. `dependencies` is optional — a task declaring none dispatches at the start of the run. `scope.files` and `effort` are **required on every task**.

Declare them in a fenced YAML-like block immediately under the `### Task N: ...` heading:

```yaml
dependencies: [T1, T3]                 # task IDs that must complete before this one starts
effort: default                        # lower | default | higher, relative to the executor's default
scope:
  files: [path/to/a.py, path/to/b.py]  # every file this task may create or modify
```

**Guidance:**

- Use `dependencies` for genuine semantic ordering — one task needing another's output — never merely for file overlap. File overlap is handled by scope, not by dependencies. Name every edge's kind in the `DAG shape` block, because the kind decides whether the edge survives **Shaping the DAG for wall-clock time**:
  - `code`: the task imports, calls, or runs the other task's code, or must import a file the other task owns to compile. This is the edge to keep.
  - `same-file`: the task only extends a file the other task owns. Merge or restructure (rule 2).
  - `contract`: the task could build and pass its acceptance against a pinned shape, such as fixtures, a type definition, an API, or a schema. Pin it in the spec and drop the edge (rule 1).
  - `harness`: the task needs only a test harness or config the other task owns. Move that work to the harness task and drop the edge (rule 4).

  A `same-file`, `contract`, or `harness` edge that survives must say why its rule could not remove it.
- `effort` is required on every task. Pick it by the rules under **Effort** in Shaping the DAG for wall-clock time; it is relative to the effort the execution skill would otherwise give an implementer.
- A dependency costs more than ordering. The dependent's merge waits for the checkpoint review of what it depends on, and a checkpoint fix to that contract can send the dependent back to be rebuilt. A spurious dependency delays a merge for nothing; a missing one lets a task build on a contract no checkpoint is watching.
- `scope.files` is **required on every task**, whether or not it will run in parallel. It is the boundary the orchestrator audits each task's diff against before committing, and the same list it hands the implementer as a hard fence — a task without it has neither. An incomplete list reads as a scope violation and stops the task.
- Tasks whose `scope.files` intersect never run at the same time: the scheduler serializes them, in dependency order and then plan order, and runs everything else beside them. A shared path serializes only the tasks that share it, not the whole plan. There is no small-overlap exemption: concurrent branches would either conflict at merge, costing the parallelism the overlap was meant to buy, or auto-merge into a file version neither agent tested.
- List every file the task will touch, including tests and any index/barrel file it must re-export from. Under-declaring is the common failure: the task gets blocked mid-run for touching a file it always needed.
- Enforce single-owner test files: every created or modified test file must be assigned to a
  single task's `scope.files`, or the tasks sharing it are serialized, one after the other. Do
  not let tasks meant to run in parallel share a test file even when they expect to edit different
  test functions.

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

Make each `Acceptance` command task-scoped: run only the task's owned test files and fast targeted
checks. Reserve full-suite execution for the execution skill's final gate (Step 7 in SDD) or branch
completion, not each parallel worker. SDD's mid-run gates select tests from these owned test files
and the tests that reference the files a merge changes, so an accurate `scope.files` keeps them fast.

````markdown
### Task N: Daily metrics summary

```yaml
# Drives per-task scheduling under quirk:subagent-driven-development.
dependencies: []
effort: default
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

**6. Acceptance-command audit:** Inspect every acceptance criterion. Is each one a literal,
copy-runnable command with exact flags and an expected result? Does it run only the task's owned
test files and fast targeted checks, rather than the full suite? Reserve the full suite for the final
gate or branch completion. Fix every mismatch.

**7. Coherence sweep:** If the plan changes a protocol, vocabulary, or event set, did you grep-enumerate every file referencing the changed old or new terms? Verify that each result is either scoped into a task or explicitly recorded as `unchanged, verified consistent`. Check that you searched for the vocabulary terms themselves, not only the names of the components being changed — a file can encode a protocol without naming the skill or module that owns it.

**8. Scope and dependency declarations:** For each task, did you declare `scope.files` accurately and `dependencies` only for genuine semantic ordering? Every task needs a complete `scope.files` — including its tests and any index/barrel file it re-exports from — because the orchestrator audits each task's diff against that list and an under-declared file stops the task. Tasks that genuinely don't depend on each other should say so, otherwise execution falls back to sequential and leaves throughput on the table. Tasks sharing any file path cannot run in parallel at all: reserve `dependencies` for one task needing another's output, never for file overlap.
Then check the shape against **Shaping the DAG for wall-clock time**: every edge names its kind and
reason, every `same-file`, `contract`, and `harness` edge is gone or justified, no task is over the
size ceiling, critical-path tasks sit at 3–6 minutes or carry a reason, the task count is under its
cap, every task has an `effort` hint, and the `DAG shape` block reports all of it.
Verify every created or modified test file has a single owner (or its sharers are
serialized), and that no task must modify or run acceptance against another task's
in-flight test file. Task-scoped acceptance must match the owned test files in `scope.files`.

If you find issues, fix them inline. No need to re-review — just fix and move on. If you find a requirement in the tech spec (`tech.md`) when present, else the logic spec, with no task, add the task.

## After the plan: agent review, then execute

There is **no separate handoff step and no human approval gate** — you are already inside the
execution skill that invoked this rubric. Two things happen next, both owned by the calling skill:

1. **Agent review (default).** Standalone `writing-plans` and `quirk:executing-plans` dispatch
   `plan-document-reviewer-prompt.md` on the in-context plan and apply its fixes inline.
   `quirk:subagent-driven-development`'s inline decomposition skips plan-document review: it spends
   its review budget on the branch via `quirk:adversarial-review`. This carve-out replaces neither
   the standalone plan review nor the execution skill's branch gates.
2. **Execute.** Continue in the same skill — `quirk:subagent-driven-development` dispatches each
   task from the fields above as soon as its dependencies merge and runs the per-task pipeline; `quirk:executing-plans`
   executes sequentially. No "which approach?" prompt here: the choice of execution skill was
   already made when one of them invoked this rubric.
