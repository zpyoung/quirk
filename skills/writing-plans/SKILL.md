---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code
---

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they don't know good test design very well.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Context:** This should be run in a dedicated worktree (created by brainstorming skill).

**Save plans to:** `docs/quirk/plans/YYYY-MM-DD-<feature-name>.md`
- (User preferences for plan location override this default)

## Scope Check

If the spec covers multiple independent subsystems, it should have been broken into sub-project specs during brainstorming. If it wasn't, suggest breaking this into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified and what each one is responsible for. This is where decomposition decisions get locked in.

- Design units with clear boundaries and well-defined interfaces. Each file should have one clear responsibility.
- You reason best about code you can hold in context at once, and your edits are more reliable when files are focused. Prefer smaller, focused files over large ones that do too much.
- Files that change together should live together. Split by responsibility, not by technical layer.
- In existing codebases, follow established patterns. If the codebase uses large files, don't unilaterally restructure - but if a file you're modifying has grown unwieldy, including a split in the plan is reasonable.

This structure informs the task decomposition. Each task should produce self-contained changes that make sense independently.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

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

> **For agentic workers:** REQUIRED SUB-SKILL: Use quirk:subagent-driven-development (recommended) or quirk:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

## Task Structure

Every task follows this template. The `independent` / `dependencies` / `scope.files` / `cooperative` block is optional but **strongly recommended** — it lets `quirk:subagent-driven-development` execute the plan in parallel waves instead of strictly sequentially. Most well-decomposed tasks should declare `independent: true` plus `scope.files`.

````markdown
### Task N: [Component Name]

```yaml
# Optional — drives parallel execution under quirk:subagent-driven-development.
# Omit any line that doesn't apply. Omit the whole block to fall back to sequential.
independent: true
dependencies: []
scope:
  files: [exact/path/to/file.py, tests/exact/path/to/test.py]
```

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## No Placeholders

Every step must contain the actual content an engineer needs. These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — the engineer may be reading tasks out of order)
- Steps that describe what to do without showing how (code blocks required for code steps)
- References to types, functions, or methods not defined in any task

## Remember
- Exact file paths always
- Complete code in every step — if a step changes code, show the code
- Exact commands with expected output
- DRY, YAGNI, TDD, frequent commits

## Self-Review

After writing the complete plan, look at the spec with fresh eyes and check the plan against it. This is a checklist you run yourself — not a subagent dispatch.

**1. Spec coverage:** Skim each section/requirement in the spec. Can you point to a task that implements it? List any gaps.

**2. Placeholder scan:** Search your plan for red flags — any of the patterns from the "No Placeholders" section above. Fix them.

**3. Type consistency:** Do the types, method signatures, and property names you used in later tasks match what you defined in earlier tasks? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 is a bug.

**4. Parallelism declarations:** For each task, did you accurately declare `independent: true` / `dependencies: [...]` / `scope.files: [...]`? Tasks that genuinely don't depend on each other should say so — otherwise the orchestrator falls back to sequential execution and leaves throughput on the table. Tasks that share a target file (e.g., multiple edits to the same `SKILL.md`) MUST run sequentially — express that with `dependencies`, never with overlapping `scope.files` and `independent: true` together.

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
