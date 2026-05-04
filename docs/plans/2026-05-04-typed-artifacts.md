# Typed Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a typed-artifacts feature module to the quirk plugin (v5.0.7 → v5.1.0) that gives Claude a structured destination for deferred bugs, skipped tests, out-of-scope tasks, and architectural proposals — replacing prose hedges ("pre-existing", "out of scope") with append-only markdown artifacts.

**Architecture:** Script-backed mutation. All artifact writes go through Python 3 scripts (stdlib-only, atomic via flock). Three lifecycle hooks (SessionStart, PostToolUse, Stop) are warn-only and gate on file presence so they're inert in non-typed-artifacts projects. Slash commands under `/quirk:artifacts:*` are short prompt files that delegate to the scripts.

**Tech Stack:** Python 3.9+ (stdlib only), POSIX shell (bash + standard utilities), Markdown (Claude Code prompts/skills/templates), pytest for tests.

**Spec:** `docs/specs/2026-05-04-typed-artifacts-design.md`

**Working directory for all paths below:** `/Users/zpyoung/ProjectWorkspaces/quirk-workspace/quirk/` (the plugin root, also a git repo as of `b3c9a12`).

---

## File Structure

### New files
```
quirk/
├── bin/                                 # NEW
│   ├── artifact_append.py
│   ├── adr_create.py
│   ├── artifact_init.py
│   └── artifact_review.py
├── commands/artifacts/                  # NEW
│   ├── init.md
│   ├── bug.md
│   ├── defer.md
│   ├── test-skip.md
│   ├── triage.md
│   ├── adr.md
│   └── review-artifacts.md
├── hooks/                               # NEW
│   ├── hooks.json
│   ├── load_artifact_tail.sh
│   ├── lint_tics.sh
│   └── wrap_session.sh
├── skills/typed-artifacts/              # NEW
│   └── SKILL.md
├── templates/                           # NEW
│   ├── BUGS.md
│   ├── DEFERRED.md
│   ├── TEST_BACKLOG.md
│   ├── proposals.md
│   ├── adr/0000-record-architecture-decisions.md
│   ├── claude_md_snippet.md
│   └── tic_phrases.json
└── tests/                               # NEW
    ├── conftest.py
    ├── test_artifact_append.py
    ├── test_adr_create.py
    ├── test_artifact_init.py
    ├── test_artifact_review.py
    ├── test_hooks.py
    ├── test_commands.py
    ├── test_skill.py
    ├── test_e2e.py
    └── fixtures/
        ├── empty-project/.gitkeep
        └── expected-final/(populated by E2E test setup)
```

### Modified files
- `.claude-plugin/plugin.json` (version bump 5.0.7 → 5.1.0; add keywords)
- `README.md` (will be created if missing; add typed-artifacts section)

### File responsibilities
- **`bin/artifact_append.py`** — single mutation entry-point for BUGS / DEFERRED / TEST_BACKLOG / proposals. Owns the schema dict, ID counters, flock, schema-version checks.
- **`bin/adr_create.py`** — ADR-specific: creates new `docs/adr/NNNN-kebab-title.md` files. Structurally distinct from the append flow.
- **`bin/artifact_init.py`** — idempotent scaffolder used by `/quirk:artifacts:init`.
- **`bin/artifact_review.py`** — read-only summary of all artifacts.
- **`templates/`** — inert source-of-truth files copied verbatim by `artifact_init.py`.
- **`commands/artifacts/*.md`** — short prompt wrappers that delegate to `bin/*.py`.
- **`hooks/*.sh`** — POSIX shell wrappers for SessionStart, PostToolUse, Stop. Always exit 0.
- **`skills/typed-artifacts/SKILL.md`** — surface-routing rules, trigger phrases, schema reference.
- **`tests/`** — pytest suite (Python tests for scripts, regex tests for prompts, shell tests for hooks).

---

## Task Breakdown

Tasks are grouped into 7 phases. Phase boundaries are good checkpoints for review and commits.

| Phase | Tasks | Output |
|---|---|---|
| 1. Test infra + templates | T1–T3 | Pytest skeleton + 7 template files |
| 2. `artifact_append.py` (foundation) | T4–T14 | Core mutation script + tests |
| 3. Init / ADR / Review scripts | T15–T26 | Three more scripts + tests |
| 4. Hooks | T27–T30 | Three shell hooks + tests |
| 5. Slash commands | T31–T35 | Seven command prompt files |
| 6. Skill + E2E | T36–T37 | Routing skill + integration test |
| 7. Ship | T38–T39 | Manifest bump + README |

---

## Phase 1: Test infra + templates

### Task 1: Set up pytest infrastructure

**Files:**
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`
- Create: `tests/fixtures/empty-project/.gitkeep` (empty)
- Create: `pyproject.toml`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "quirk-typed-artifacts"
version = "5.1.0"
requires-python = ">=3.9"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["bin"]
```

- [ ] **Step 2: Create `tests/__init__.py`** (empty file)

- [ ] **Step 3: Create `tests/conftest.py`**

```python
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = REPO_ROOT / "bin"
TEMPLATES_DIR = REPO_ROOT / "templates"
HOOKS_DIR = REPO_ROOT / "hooks"


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """A fresh empty 'project' directory the scripts can mutate."""
    return tmp_path


@pytest.fixture
def initialized_project(project_dir: Path) -> Path:
    """A project pre-populated with empty artifact files (no entries)."""
    for name in ["BUGS.md", "DEFERRED.md", "TEST_BACKLOG.md", "proposals.md"]:
        src = TEMPLATES_DIR / name
        if src.exists():
            shutil.copy(src, project_dir / name)
    adr_dir = project_dir / "docs" / "adr"
    adr_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def run_script(script_name: str, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke a bin/*.py script in a child process; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(BIN_DIR / script_name), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
```

- [ ] **Step 4: Create `tests/fixtures/empty-project/.gitkeep`** (empty file)

- [ ] **Step 5: Verify pytest discovers no tests yet**

Run: `cd /Users/zpyoung/ProjectWorkspaces/quirk-workspace/quirk && python3 -m pytest -q`
Expected: `no tests ran` (exit 5 from pytest = no tests collected, that's fine)

- [ ] **Step 6: Commit**

```bash
git add tests/__init__.py tests/conftest.py tests/fixtures/empty-project/.gitkeep pyproject.toml
git commit -m "chore(typed-artifacts): scaffold pytest infrastructure"
```

---

### Task 2: Create the four append-target templates

**Files:**
- Create: `templates/BUGS.md`
- Create: `templates/DEFERRED.md`
- Create: `templates/TEST_BACKLOG.md`
- Create: `templates/proposals.md`

These are inert source-of-truth files copied verbatim by `artifact_init.py`. Each carries a schema-comment header and a schema-version marker.

- [ ] **Step 1: Create `templates/BUGS.md`**

```markdown
<!-- schema-version: 1 -->
<!-- BUGS.md SCHEMA (append only — do not rewrite existing entries)
Entry format:
## BUG-[N]: [Short title]
- **Observed**: [date or session ID]
- **File**: [path/to/file.ts:line]
- **Description**: [what the bug is]
- **Introduced by**: [this session / unknown / commit SHA]
- **Severity**: [critical / high / medium / low]
- **Proposed fix**: [one sentence]
- **Blocker for**: [what this would break]

Required fields: title, file, description, severity.
-->

# BUGS

Bugs noticed during sessions but not fixed in the current scope.

Reviewed every PR. Use `/quirk:artifacts:bug` to append. Do not edit older
entries' IDs; manual edits to fix typos are fine.
```

- [ ] **Step 2: Create `templates/DEFERRED.md`**

```markdown
<!-- schema-version: 1 -->
<!-- DEFERRED.md SCHEMA (append only)
Entry format:
## DEFER-[N]: [Task title]
- **Deferred**: [date]
- **Session context**: [what triggered this]
- **Why deferred**: [out of scope / blocked on / requires decision]
- **Estimated effort**: [S/M/L]
- **Priority**: [P1/P2/P3/P4]
- **Proposed owner**: [Claude / name / unassigned]

Required fields: title, why_deferred, priority.
-->

# DEFERRED

Tasks surfaced during sessions but explicitly out of scope for the current work.

Reviewed every sprint planning. Use `/quirk:artifacts:defer` to append.
```

- [ ] **Step 3: Create `templates/TEST_BACKLOG.md`**

```markdown
<!-- schema-version: 1 -->
<!-- TEST_BACKLOG.md SCHEMA (append only)
Entry format:
## TEST-[N]: [Function or behavior to test]
- **File under test**: [path]
- **Test type**: [unit / integration / e2e]
- **Reason skipped**: [time / complexity / mocking required / TBD]
- **Edge cases to cover**: [list]
- **Priority**: [P1/P2/P3/P4]

Required fields: file_under_test, reason_skipped.
-->

# TEST BACKLOG

Tests that were skipped, abbreviated, or flagged as needing expansion.

Reviewed every 2 weeks. Use `/quirk:artifacts:test-skip` to append.
```

- [ ] **Step 4: Create `templates/proposals.md`**

```markdown
<!-- schema-version: 1 -->
<!-- proposals.md SCHEMA (append only)
Entry format:
## PROPOSAL-[N]: [Title]
- **Proposed**: [date]
- **Context**: [neutral description of why this came up]
- **Options considered**: [Option A / Option B / ...]
- **Recommendation**: [with rationale]
- **Decision required from**: [human / team / architect]
- **Status**: [proposed / accepted / rejected / superseded]

Required fields: title, context, recommendation.
-->

# PROPOSALS

Architectural observations Claude surfaces but cannot act on unilaterally.
Holding pen for unsettled decisions; promote to `docs/adr/` once accepted.

Reviewed with architect monthly. Use `/quirk:artifacts:triage` (proposal
category) to append, or edit manually.
```

- [ ] **Step 5: Commit**

```bash
git add templates/BUGS.md templates/DEFERRED.md templates/TEST_BACKLOG.md templates/proposals.md
git commit -m "feat(typed-artifacts): add four append-target templates"
```

---

### Task 3: Create ADR template, CLAUDE.md snippet, tic_phrases.json

**Files:**
- Create: `templates/adr/0000-record-architecture-decisions.md`
- Create: `templates/claude_md_snippet.md`
- Create: `templates/tic_phrases.json`

- [ ] **Step 1: Create `templates/adr/0000-record-architecture-decisions.md`**

```markdown
# 0000. Record architecture decisions

- **Status:** accepted
- **Date:** 2026-05-04

## Context

This project benefits from recording the architectural decisions made
during its lifecycle, in a way that preserves the *why* alongside the
*what*. Memory and chat logs are unreliable; documents are durable.

## Decision

Use Architecture Decision Records (ADRs) as described by Michael Nygard
to capture significant decisions. Each ADR lives in `docs/adr/` as a
file named `NNNN-kebab-title.md`. Numbers are sequential. Once an ADR
is accepted it is immutable except for status transitions
(accepted → superseded by NNNN, etc.).

Use `/quirk:artifacts:adr "title"` to create a new ADR. Status starts
at `proposed` and is promoted by editing the file.

## Consequences

Positive — durable rationale; new contributors can read history; reviews
have a structured place to land.

Negative — small overhead per decision; risk of ADRs going stale if not
linked to status reviews.

Neutral — number space is sequential and gap-free; renumbering is a
breaking change to references.
```

- [ ] **Step 2: Create `templates/claude_md_snippet.md`**

```markdown
<!-- quirk-typed-artifacts:trigger -->
## Surface Routing (typed-artifacts)

When you notice something you cannot act on in this session, do NOT bury
it in prose with phrases like "pre-existing", "out of scope", or "skipped
for brevity". Route it via the `typed-artifacts` skill (auto-loads on
those phrases) or use one of:
- `/quirk:artifacts:bug`        — log a bug to BUGS.md
- `/quirk:artifacts:defer`      — log out-of-scope work to DEFERRED.md
- `/quirk:artifacts:test-skip`  — log a skipped test to TEST_BACKLOG.md
- `/quirk:artifacts:triage`     — let Claude classify the observation
- `/quirk:artifacts:adr`        — record an architectural decision

Review cadence: BUGS.md every PR · DEFERRED.md every sprint planning ·
TEST_BACKLOG.md every 2 weeks · proposals.md / docs/adr/ monthly with
architect. Run `/quirk:artifacts:review-artifacts` to scan all four.
<!-- /quirk-typed-artifacts:trigger -->
```

- [ ] **Step 3: Create `templates/tic_phrases.json`**

```json
{
  "schema_version": 1,
  "patterns": [
    {"phrase": "pre-existing", "suggested_artifact": "BUGS.md"},
    {"phrase": "already existed", "suggested_artifact": "BUGS.md"},
    {"phrase": "introduced before", "suggested_artifact": "BUGS.md"},
    {"phrase": "out of scope", "suggested_artifact": "DEFERRED.md"},
    {"phrase": "larger refactor needed", "suggested_artifact": "DEFERRED.md"},
    {"phrase": "future work", "suggested_artifact": "DEFERRED.md"},
    {"phrase": "skipped for brevity", "suggested_artifact": "TEST_BACKLOG.md"},
    {"phrase": "tests can be added later", "suggested_artifact": "TEST_BACKLOG.md"},
    {"phrase": "worth reconsidering", "suggested_artifact": "proposals.md"},
    {"phrase": "architectural concern", "suggested_artifact": "proposals.md"},
    {"phrase": "worth revisiting", "suggested_artifact": "proposals.md"}
  ]
}
```

- [ ] **Step 4: Commit**

```bash
git add templates/adr/0000-record-architecture-decisions.md templates/claude_md_snippet.md templates/tic_phrases.json
git commit -m "feat(typed-artifacts): add ADR-0000, CLAUDE.md snippet, tic_phrases.json"
```

---

## Phase 2: `artifact_append.py` (the foundation)

This is the most-tested, highest-stakes script in the plan. Everything else delegates to it. We TDD it carefully.

### Task 4: argparse skeleton + schema dict + unknown-type test

**Files:**
- Create: `bin/artifact_append.py`
- Create: `tests/test_artifact_append.py`

- [ ] **Step 1: Write the failing test for unknown type**

In `tests/test_artifact_append.py`:
```python
from __future__ import annotations

from pathlib import Path

from .conftest import run_script


def test_unknown_artifact_type_exits_2(initialized_project: Path) -> None:
    result = run_script("artifact_append.py", "bgu", cwd=initialized_project)
    assert result.returncode == 2
    assert "unknown type" in result.stderr.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_artifact_append.py::test_unknown_artifact_type_exits_2 -v`
Expected: FAIL — `bin/artifact_append.py` does not exist yet.

- [ ] **Step 3: Create `bin/artifact_append.py` with skeleton**

```python
#!/usr/bin/env python3
"""Append an entry to a typed-artifact markdown file."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCHEMAS: dict[str, dict] = {
    "bug": {
        "header": "BUG",
        "file": "BUGS.md",
        "required": ["title", "file", "description", "severity"],
        "fields": [
            "title", "observed", "file", "description",
            "introduced_by", "severity", "proposed_fix", "blocker_for",
        ],
        "labels": {
            "observed": "Observed",
            "file": "File",
            "description": "Description",
            "introduced_by": "Introduced by",
            "severity": "Severity",
            "proposed_fix": "Proposed fix",
            "blocker_for": "Blocker for",
        },
    },
    "defer": {
        "header": "DEFER",
        "file": "DEFERRED.md",
        "required": ["title", "why_deferred", "priority"],
        "fields": [
            "title", "deferred", "session_context", "why_deferred",
            "estimated_effort", "priority", "proposed_owner",
        ],
        "labels": {
            "deferred": "Deferred",
            "session_context": "Session context",
            "why_deferred": "Why deferred",
            "estimated_effort": "Estimated effort",
            "priority": "Priority",
            "proposed_owner": "Proposed owner",
        },
    },
    "test-skip": {
        "header": "TEST",
        "file": "TEST_BACKLOG.md",
        "required": ["title", "file_under_test", "reason_skipped"],
        "fields": [
            "title", "file_under_test", "test_type", "reason_skipped",
            "edge_cases", "priority",
        ],
        "labels": {
            "file_under_test": "File under test",
            "test_type": "Test type",
            "reason_skipped": "Reason skipped",
            "edge_cases": "Edge cases to cover",
            "priority": "Priority",
        },
    },
    "proposal": {
        "header": "PROPOSAL",
        "file": "proposals.md",
        "required": ["title", "context", "recommendation"],
        "fields": [
            "title", "proposed", "context", "options_considered",
            "recommendation", "decision_required_from", "status",
        ],
        "labels": {
            "proposed": "Proposed",
            "context": "Context",
            "options_considered": "Options considered",
            "recommendation": "Recommendation",
            "decision_required_from": "Decision required from",
            "status": "Status",
        },
    },
}

EXPECTED_SCHEMA_VERSION = 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append to a typed-artifact file.")
    parser.add_argument("type", help="Artifact type")
    parser.add_argument("--field", action="append", default=[],
                        help="Field as key=value (repeatable)")
    parser.add_argument("--project-dir", default=".",
                        help="Project root containing artifact files")
    args = parser.parse_args(argv)

    if args.type not in SCHEMAS:
        valid = ", ".join(sorted(SCHEMAS.keys()))
        print(f"Unknown type {args.type!r}. Valid: {valid}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_append.py::test_unknown_artifact_type_exits_2 -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/artifact_append.py tests/test_artifact_append.py
git commit -m "feat(typed-artifacts): scaffold artifact_append.py with schema dict"
```

---

### Task 5: Parse `--field key=value` and reject missing required fields

**Files:**
- Modify: `bin/artifact_append.py`
- Modify: `tests/test_artifact_append.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_artifact_append.py`:
```python
def test_missing_required_field_exits_2(initialized_project: Path) -> None:
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=auth fails",
        "--field", "file=login.ts:42",
        # missing: description, severity
        cwd=initialized_project,
    )
    assert result.returncode == 2
    assert "missing required field" in result.stderr.lower()


def test_unknown_field_exits_2(initialized_project: Path) -> None:
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "nonsense=oops",
        cwd=initialized_project,
    )
    assert result.returncode == 2
    assert "unknown field" in result.stderr.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_artifact_append.py -v -k "missing_required or unknown_field"`
Expected: both FAIL — script doesn't validate fields yet.

- [ ] **Step 3: Add field parsing + validation**

Edit `bin/artifact_append.py`. Replace the `main()` body after the `if args.type not in SCHEMAS` block with:

```python
    schema = SCHEMAS[args.type]

    fields: dict[str, str] = {}
    for raw in args.field:
        if "=" not in raw:
            print(f"Bad --field {raw!r}: expected key=value", file=sys.stderr)
            return 2
        key, value = raw.split("=", 1)
        if key not in schema["fields"]:
            valid = ", ".join(schema["fields"])
            print(f"Unknown field {key!r} for {args.type}. Valid: {valid}", file=sys.stderr)
            return 2
        fields[key] = value

    missing = [k for k in schema["required"] if k not in fields]
    if missing:
        print(
            f"Missing required field: {', '.join(missing)}. "
            f"See schema in templates/{schema['file']}.",
            file=sys.stderr,
        )
        return 2

    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_artifact_append.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add bin/artifact_append.py tests/test_artifact_append.py
git commit -m "feat(typed-artifacts): validate fields and required-field presence"
```

---

### Task 6: Append BUG-1 to empty BUGS.md (happy path)

**Files:**
- Modify: `bin/artifact_append.py`
- Modify: `tests/test_artifact_append.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_artifact_append.py`:
```python
def test_append_bug_1_to_empty_file(initialized_project: Path) -> None:
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=auth fails on safari",
        "--field", "file=login.ts:42",
        "--field", "description=safari rejects the cookie",
        "--field", "severity=high",
        cwd=initialized_project,
    )
    assert result.returncode == 0, result.stderr
    bugs = (initialized_project / "BUGS.md").read_text()
    assert "## BUG-1: auth fails on safari" in bugs
    assert "**File**: login.ts:42" in bugs
    assert "**Severity**: high" in bugs
    assert "BUG-1: auth fails on safari" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_artifact_append.py::test_append_bug_1_to_empty_file -v`
Expected: FAIL — script returns 0 but doesn't write to BUGS.md yet.

- [ ] **Step 3: Implement read + append**

Edit `bin/artifact_append.py`. Add helper functions before `main()`:

```python
import re
from datetime import date


def find_max_id(text: str, header: str) -> int:
    """Return max N from '## HEADER-N:' lines, or 0 if none found."""
    pattern = re.compile(rf"^##\s+{re.escape(header)}-(\d+):", re.MULTILINE)
    ids = [int(m.group(1)) for m in pattern.finditer(text)]
    return max(ids) if ids else 0


def render_entry(schema: dict, entry_id: int, fields: dict[str, str]) -> str:
    """Render a markdown entry block for the given schema and fields."""
    title = fields.get("title", "")
    lines = [f"## {schema['header']}-{entry_id}: {title}"]
    for key in schema["fields"]:
        if key == "title":
            continue
        if key in fields:
            label = schema["labels"].get(key, key)
            lines.append(f"- **{label}**: {fields[key]}")
    lines.append("")
    return "\n".join(lines)
```

Replace the final `return 0` in `main()` with:

```python
    project = Path(args.project_dir).resolve()
    target = project / schema["file"]

    if not target.exists():
        print(
            f"{schema['file']} not found in {project}. "
            f"Run /quirk:artifacts:init first.",
            file=sys.stderr,
        )
        return 3

    text = target.read_text()
    next_id = find_max_id(text, schema["header"]) + 1

    if "observed" in schema["fields"] and "observed" not in fields:
        fields["observed"] = date.today().isoformat()
    if "deferred" in schema["fields"] and "deferred" not in fields:
        fields["deferred"] = date.today().isoformat()
    if "proposed" in schema["fields"] and "proposed" not in fields:
        fields["proposed"] = date.today().isoformat()

    entry = render_entry(schema, next_id, fields)
    new_text = text.rstrip() + "\n\n" + entry + "\n"
    target.write_text(new_text)

    print(f"{schema['header']}-{next_id}: {fields.get('title', '')}")
    return 0
```

Also add the `import re` and `from datetime import date` at the top of the file alongside the existing imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_append.py::test_append_bug_1_to_empty_file -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bin/artifact_append.py tests/test_artifact_append.py
git commit -m "feat(typed-artifacts): append BUG-1 entry to BUGS.md (happy path)"
```

---

### Task 7: Sequential ID increment (BUG-7 from BUG-6)

**Files:**
- Modify: `tests/test_artifact_append.py`

The `find_max_id` helper from Task 6 already handles this; we add a test to lock the behavior in.

- [ ] **Step 1: Write the test**

Append to `tests/test_artifact_append.py`:
```python
def test_sequential_id_increment(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-6: prior\n- **File**: x.py:1\n- **Description**: y\n- **Severity**: low\n")
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=new bug",
        "--field", "file=a.py:1",
        "--field", "description=z",
        "--field", "severity=low",
        cwd=initialized_project,
    )
    assert result.returncode == 0, result.stderr
    assert "## BUG-7: new bug" in bugs.read_text()
    assert "BUG-7: new bug" in result.stdout
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_append.py::test_sequential_id_increment -v`
Expected: PASS (the implementation from Task 6 already supports this; the test locks it in).

- [ ] **Step 3: Commit**

```bash
git add tests/test_artifact_append.py
git commit -m "test(typed-artifacts): lock in sequential ID increment behavior"
```

---

### Task 8: Gap handling (BUG-3, BUG-7, BUG-12 → BUG-13)

**Files:**
- Modify: `tests/test_artifact_append.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_artifact_append.py`:
```python
def test_gaps_use_max_plus_one(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    body = bugs.read_text()
    for n in (3, 7, 12):
        body += f"\n## BUG-{n}: x\n- **File**: x.py:1\n- **Description**: y\n- **Severity**: low\n"
    bugs.write_text(body)
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=after gaps",
        "--field", "file=a.py:1",
        "--field", "description=z",
        "--field", "severity=low",
        cwd=initialized_project,
    )
    assert result.returncode == 0, result.stderr
    assert "## BUG-13: after gaps" in bugs.read_text()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_append.py::test_gaps_use_max_plus_one -v`
Expected: PASS (max-plus-one already implemented).

- [ ] **Step 3: Commit**

```bash
git add tests/test_artifact_append.py
git commit -m "test(typed-artifacts): max-plus-one ID over gaps"
```

---

### Task 9: Schema-version mismatch exits 8

**Files:**
- Modify: `bin/artifact_append.py`
- Modify: `tests/test_artifact_append.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_artifact_append.py`:
```python
def test_schema_version_mismatch_exits_8(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    text = bugs.read_text().replace("schema-version: 1", "schema-version: 99")
    bugs.write_text(text)
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=t", "--field", "file=x:1",
        "--field", "description=d", "--field", "severity=low",
        cwd=initialized_project,
    )
    assert result.returncode == 8
    assert "schema" in result.stderr.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_artifact_append.py::test_schema_version_mismatch_exits_8 -v`
Expected: FAIL — script doesn't check schema version yet.

- [ ] **Step 3: Add schema-version check**

In `bin/artifact_append.py`, add this helper above `main()`:

```python
SCHEMA_VERSION_RE = re.compile(r"<!--\s*schema-version:\s*(\d+)\s*-->")


def detect_schema_version(text: str) -> int | None:
    m = SCHEMA_VERSION_RE.search(text)
    return int(m.group(1)) if m else None
```

In `main()`, after `text = target.read_text()`, insert:

```python
    version = detect_schema_version(text)
    if version is not None and version > EXPECTED_SCHEMA_VERSION:
        print(
            f"Schema v{version} file, plugin understands v{EXPECTED_SCHEMA_VERSION}. "
            "Upgrade quirk.",
            file=sys.stderr,
        )
        return 8
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_append.py::test_schema_version_mismatch_exits_8 -v`
Expected: PASS.

- [ ] **Step 5: Run full test file to check no regressions**

Run: `python3 -m pytest tests/test_artifact_append.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add bin/artifact_append.py tests/test_artifact_append.py
git commit -m "feat(typed-artifacts): reject newer schema versions with exit 8"
```

---

### Task 10: Missing target file exits 3

**Files:**
- Modify: `tests/test_artifact_append.py`

The implementation from Task 6 already handles this; lock it in with a test.

- [ ] **Step 1: Write the test**

Append to `tests/test_artifact_append.py`:
```python
def test_missing_target_file_exits_3(project_dir: Path) -> None:
    # project_dir has no BUGS.md
    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=t", "--field", "file=x:1",
        "--field", "description=d", "--field", "severity=low",
        cwd=project_dir,
    )
    assert result.returncode == 3
    assert "BUGS.md not found" in result.stderr
    assert "init" in result.stderr.lower()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_append.py::test_missing_target_file_exits_3 -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_artifact_append.py
git commit -m "test(typed-artifacts): missing artifact file exits 3"
```

---

### Task 11: All four artifact types end-to-end

**Files:**
- Modify: `tests/test_artifact_append.py`

Make sure defer / test-skip / proposal also work, not just bug. Bugs in render_entry or schema dict will surface here.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_artifact_append.py`:
```python
import pytest


@pytest.mark.parametrize(
    "kind, header, target_file, fields",
    [
        ("defer", "DEFER", "DEFERRED.md", [
            ("title", "ship later"),
            ("why_deferred", "out of scope"),
            ("priority", "P3"),
        ]),
        ("test-skip", "TEST", "TEST_BACKLOG.md", [
            ("title", "edge case"),
            ("file_under_test", "auth.ts"),
            ("reason_skipped", "complexity"),
        ]),
        ("proposal", "PROPOSAL", "proposals.md", [
            ("title", "rethink session storage"),
            ("context", "JWT has problems"),
            ("recommendation", "switch to opaque tokens"),
        ]),
    ],
)
def test_all_artifact_types_append(
    initialized_project: Path,
    kind: str, header: str, target_file: str,
    fields: list[tuple[str, str]],
) -> None:
    args = []
    for k, v in fields:
        args += ["--field", f"{k}={v}"]
    result = run_script("artifact_append.py", kind, *args, cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    target = (initialized_project / target_file).read_text()
    assert f"## {header}-1:" in target
    assert f"{header}-1:" in result.stdout
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_append.py::test_all_artifact_types_append -v`
Expected: 3 PASS (one per parametrize entry).

- [ ] **Step 3: Commit**

```bash
git add tests/test_artifact_append.py
git commit -m "test(typed-artifacts): cover defer/test-skip/proposal append flows"
```

---

### Task 12: Atomic append via flock

**Files:**
- Modify: `bin/artifact_append.py`
- Modify: `tests/test_artifact_append.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_artifact_append.py`:
```python
import fcntl
import threading
import time


def test_concurrent_appends_do_not_collide_on_id(initialized_project: Path) -> None:
    """Two concurrent runs must produce BUG-1 and BUG-2, not two BUG-1s."""
    results = []

    def runner() -> None:
        r = run_script(
            "artifact_append.py", "bug",
            "--field", "title=concurrent",
            "--field", "file=x:1",
            "--field", "description=d",
            "--field", "severity=low",
            cwd=initialized_project,
        )
        results.append(r)

    threads = [threading.Thread(target=runner) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    bugs = (initialized_project / "BUGS.md").read_text()
    assert "## BUG-1: concurrent" in bugs
    assert "## BUG-2: concurrent" in bugs
    assert all(r.returncode == 0 for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_artifact_append.py::test_concurrent_appends_do_not_collide_on_id -v`
Expected: may FAIL or be flaky — without flock, the read-modify-write window can produce two BUG-1s.

- [ ] **Step 3: Add flock-based mutual exclusion**

In `bin/artifact_append.py`, add at the top with the imports:

```python
import fcntl
import time
```

In `main()`, replace the block from `text = target.read_text()` through `target.write_text(new_text)` with:

```python
    lock_path = target.with_name(f".{schema['file']}.lock")
    deadline = time.monotonic() + 5.0
    with open(lock_path, "w") as lock_file:
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    print(
                        f"Could not acquire lock on {lock_path.name}. Retry.",
                        file=sys.stderr,
                    )
                    return 5
                time.sleep(0.05)

        text = target.read_text()
        version = detect_schema_version(text)
        if version is not None and version > EXPECTED_SCHEMA_VERSION:
            print(
                f"Schema v{version} file, plugin understands v{EXPECTED_SCHEMA_VERSION}. "
                "Upgrade quirk.",
                file=sys.stderr,
            )
            return 8

        next_id = find_max_id(text, schema["header"]) + 1

        if "observed" in schema["fields"] and "observed" not in fields:
            fields["observed"] = date.today().isoformat()
        if "deferred" in schema["fields"] and "deferred" not in fields:
            fields["deferred"] = date.today().isoformat()
        if "proposed" in schema["fields"] and "proposed" not in fields:
            fields["proposed"] = date.today().isoformat()

        entry = render_entry(schema, next_id, fields)
        new_text = text.rstrip() + "\n\n" + entry + "\n"
        target.write_text(new_text)

        print(f"{schema['header']}-{next_id}: {fields.get('title', '')}")
    return 0
```

(Remove the now-duplicate schema-version check that was previously above this block — it now lives inside the `with` block.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_append.py::test_concurrent_appends_do_not_collide_on_id -v`
Expected: PASS.

- [ ] **Step 5: Re-run all artifact_append tests**

Run: `python3 -m pytest tests/test_artifact_append.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add bin/artifact_append.py tests/test_artifact_append.py
git commit -m "feat(typed-artifacts): atomic appends via flock with 5s timeout"
```

---

### Task 13: Lock contention exits 5 deterministically

**Files:**
- Modify: `tests/test_artifact_append.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_artifact_append.py`:
```python
def test_lock_contention_exits_5(initialized_project: Path) -> None:
    """If the lock file is already held, the script gives up after 5s and exits 5."""
    lock_path = initialized_project / ".BUGS.md.lock"
    with open(lock_path, "w") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        # Run with a short fake timeout via env var
        import os
        env = {**os.environ, "ARTIFACT_LOCK_TIMEOUT": "0.5"}
        import subprocess, sys
        r = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "bin" / "artifact_append.py"),
             "bug",
             "--field", "title=t", "--field", "file=x:1",
             "--field", "description=d", "--field", "severity=low"],
            cwd=initialized_project,
            capture_output=True,
            text=True,
            env=env,
        )
        assert r.returncode == 5
        assert "lock" in r.stderr.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_artifact_append.py::test_lock_contention_exits_5 -v`
Expected: FAIL — there's no `ARTIFACT_LOCK_TIMEOUT` honored yet, the test takes 5s and may hang.

- [ ] **Step 3: Honor `ARTIFACT_LOCK_TIMEOUT` env var**

In `bin/artifact_append.py`, replace `deadline = time.monotonic() + 5.0` with:

```python
        timeout = float(os.environ.get("ARTIFACT_LOCK_TIMEOUT", "5.0"))
        deadline = time.monotonic() + timeout
```

Add `import os` at the top with the other imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_append.py::test_lock_contention_exits_5 -v`
Expected: PASS within ~1s.

- [ ] **Step 5: Commit**

```bash
git add bin/artifact_append.py tests/test_artifact_append.py
git commit -m "feat(typed-artifacts): lock-contention timeout configurable; exits 5"
```

---

### Task 14: Unicode and special chars round-trip safely

**Files:**
- Modify: `tests/test_artifact_append.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_artifact_append.py`:
```python
def test_unicode_and_special_chars_preserved(initialized_project: Path) -> None:
    weird = "café — emoji 🐛 quotes \"don't\" newlines\\nliteral"
    result = run_script(
        "artifact_append.py", "bug",
        "--field", f"title={weird}",
        "--field", "file=x:1",
        "--field", f"description={weird}",
        "--field", "severity=low",
        cwd=initialized_project,
    )
    assert result.returncode == 0, result.stderr
    body = (initialized_project / "BUGS.md").read_text()
    assert weird in body
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_append.py::test_unicode_and_special_chars_preserved -v`
Expected: PASS (Python 3 strings handle this transparently).

- [ ] **Step 3: Commit**

```bash
git add tests/test_artifact_append.py
git commit -m "test(typed-artifacts): unicode and special chars preserved in entries"
```

---

## Phase 3: Init / ADR / Review scripts

### Task 15: `artifact_init.py` — empty project scaffolding

**Files:**
- Create: `bin/artifact_init.py`
- Create: `tests/test_artifact_init.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_artifact_init.py`:
```python
from __future__ import annotations

from pathlib import Path

from .conftest import run_script


def test_init_empty_project_creates_all_artifacts(project_dir: Path) -> None:
    result = run_script("artifact_init.py", cwd=project_dir)
    assert result.returncode == 0, result.stderr
    for name in ["BUGS.md", "DEFERRED.md", "TEST_BACKLOG.md", "proposals.md"]:
        assert (project_dir / name).exists(), f"missing {name}"
    assert (project_dir / "docs" / "adr" / "0000-record-architecture-decisions.md").exists()
    assert "Created" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_artifact_init.py::test_init_empty_project_creates_all_artifacts -v`
Expected: FAIL — `bin/artifact_init.py` does not exist.

- [ ] **Step 3: Create `bin/artifact_init.py`**

```python
#!/usr/bin/env python3
"""Scaffold typed-artifact files into the current project."""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"

ROOT_TEMPLATES = ["BUGS.md", "DEFERRED.md", "TEST_BACKLOG.md", "proposals.md"]
ADR_TEMPLATE = TEMPLATES_DIR / "adr" / "0000-record-architecture-decisions.md"
SNIPPET_TEMPLATE = TEMPLATES_DIR / "claude_md_snippet.md"
SNIPPET_MARKER = "<!-- quirk-typed-artifacts:trigger -->"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold typed-artifact files.")
    parser.add_argument("--force", action="store_true",
                        help="Backup and overwrite existing artifacts")
    parser.add_argument("--no-claude-md", action="store_true",
                        help="Do not write/append to CLAUDE.md")
    parser.add_argument("--project-dir", default=".",
                        help="Project root to scaffold into")
    args = parser.parse_args(argv)

    project = Path(args.project_dir).resolve()
    if not project.exists() or not project.is_dir():
        print(f"Project dir not found: {project}", file=sys.stderr)
        return 7

    created: list[str] = []
    skipped: list[str] = []

    for name in ROOT_TEMPLATES:
        src = TEMPLATES_DIR / name
        dst = project / name
        if dst.exists() and not args.force:
            skipped.append(name)
            continue
        if dst.exists() and args.force:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy(dst, dst.with_suffix(dst.suffix + f".bak.{stamp}"))
        shutil.copy(src, dst)
        created.append(name)

    adr_dir = project / "docs" / "adr"
    adr_dir.mkdir(parents=True, exist_ok=True)
    adr_dst = adr_dir / "0000-record-architecture-decisions.md"
    if not adr_dst.exists() or args.force:
        if adr_dst.exists() and args.force:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy(adr_dst, adr_dst.with_suffix(adr_dst.suffix + f".bak.{stamp}"))
        shutil.copy(ADR_TEMPLATE, adr_dst)
        created.append("docs/adr/0000-record-architecture-decisions.md")
    else:
        skipped.append("docs/adr/0000-record-architecture-decisions.md")

    if not args.no_claude_md:
        claude_md = project / "CLAUDE.md"
        snippet = SNIPPET_TEMPLATE.read_text()
        existing = claude_md.read_text() if claude_md.exists() else ""
        if SNIPPET_MARKER in existing:
            skipped.append("CLAUDE.md (snippet already present)")
        else:
            joiner = "\n\n" if existing and not existing.endswith("\n") else ""
            new_text = existing + joiner + snippet if existing else snippet
            claude_md.write_text(new_text)
            created.append("CLAUDE.md (snippet appended)" if existing else "CLAUDE.md")

    print(f"Created: {', '.join(created) if created else '(none)'}")
    if skipped:
        print(f"Skipped: {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_init.py::test_init_empty_project_creates_all_artifacts -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bin/artifact_init.py tests/test_artifact_init.py
git commit -m "feat(typed-artifacts): artifact_init.py scaffolds empty project"
```

---

### Task 16: `artifact_init.py` — idempotent re-run

**Files:**
- Modify: `tests/test_artifact_init.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_artifact_init.py`:
```python
def test_init_is_idempotent(project_dir: Path) -> None:
    run1 = run_script("artifact_init.py", cwd=project_dir)
    assert run1.returncode == 0
    bugs_before = (project_dir / "BUGS.md").read_text()

    run2 = run_script("artifact_init.py", cwd=project_dir)
    assert run2.returncode == 0
    assert "Skipped" in run2.stdout
    assert (project_dir / "BUGS.md").read_text() == bugs_before
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_init.py::test_init_is_idempotent -v`
Expected: PASS (Task 15 implementation already supports this; locks behavior in).

- [ ] **Step 3: Commit**

```bash
git add tests/test_artifact_init.py
git commit -m "test(typed-artifacts): init re-run is idempotent"
```

---

### Task 17: `artifact_init.py` — `--force` makes timestamped backup

**Files:**
- Modify: `tests/test_artifact_init.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_artifact_init.py`:
```python
def test_init_force_creates_backup(project_dir: Path) -> None:
    run_script("artifact_init.py", cwd=project_dir)  # initialize first
    bugs = project_dir / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: hand-written\n")
    pre_backups = list(project_dir.glob("BUGS.md.bak.*"))

    result = run_script("artifact_init.py", "--force", cwd=project_dir)
    assert result.returncode == 0, result.stderr

    post_backups = list(project_dir.glob("BUGS.md.bak.*"))
    assert len(post_backups) == len(pre_backups) + 1
    backup = post_backups[-1]
    assert "BUG-1: hand-written" in backup.read_text()
    assert "BUG-1: hand-written" not in bugs.read_text()  # overwritten
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_init.py::test_init_force_creates_backup -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_artifact_init.py
git commit -m "test(typed-artifacts): --force creates timestamped backups"
```

---

### Task 18: `artifact_init.py` — CLAUDE.md snippet logic

**Files:**
- Modify: `tests/test_artifact_init.py`

- [ ] **Step 1: Write the tests**

Append to `tests/test_artifact_init.py`:
```python
def test_init_creates_claude_md_when_missing(project_dir: Path) -> None:
    result = run_script("artifact_init.py", cwd=project_dir)
    assert result.returncode == 0
    assert (project_dir / "CLAUDE.md").exists()
    assert "<!-- quirk-typed-artifacts:trigger -->" in (project_dir / "CLAUDE.md").read_text()


def test_init_appends_snippet_to_existing_claude_md(project_dir: Path) -> None:
    (project_dir / "CLAUDE.md").write_text("# project rules\n- use python3\n")
    result = run_script("artifact_init.py", cwd=project_dir)
    assert result.returncode == 0
    body = (project_dir / "CLAUDE.md").read_text()
    assert "use python3" in body
    assert "<!-- quirk-typed-artifacts:trigger -->" in body


def test_init_skips_snippet_when_marker_present(project_dir: Path) -> None:
    (project_dir / "CLAUDE.md").write_text("# rules\n<!-- quirk-typed-artifacts:trigger -->\nold body\n<!-- /quirk-typed-artifacts:trigger -->\n")
    before = (project_dir / "CLAUDE.md").read_text()
    result = run_script("artifact_init.py", cwd=project_dir)
    assert result.returncode == 0
    assert (project_dir / "CLAUDE.md").read_text() == before
    assert "Skipped" in result.stdout


def test_init_no_claude_md_flag(project_dir: Path) -> None:
    result = run_script("artifact_init.py", "--no-claude-md", cwd=project_dir)
    assert result.returncode == 0
    assert not (project_dir / "CLAUDE.md").exists()
```

- [ ] **Step 2: Run tests**

Run: `python3 -m pytest tests/test_artifact_init.py -v`
Expected: all PASS (Task 15 implementation supports all four cases).

- [ ] **Step 3: Commit**

```bash
git add tests/test_artifact_init.py
git commit -m "test(typed-artifacts): CLAUDE.md snippet append/skip/no-flag matrix"
```

---

### Task 19: `adr_create.py` — empty `docs/adr/` produces 0001

**Files:**
- Create: `bin/adr_create.py`
- Create: `tests/test_adr_create.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_adr_create.py`:
```python
from __future__ import annotations

from pathlib import Path

from .conftest import run_script


def test_first_adr_is_0001(project_dir: Path) -> None:
    result = run_script(
        "adr_create.py", "--title", "Switch to opaque tokens",
        cwd=project_dir,
    )
    assert result.returncode == 0, result.stderr
    files = list((project_dir / "docs" / "adr").glob("*.md"))
    assert len(files) == 1
    assert files[0].name == "0001-switch-to-opaque-tokens.md"
    assert "ADR-0001:" in result.stdout
    body = files[0].read_text()
    assert "# 0001. Switch to opaque tokens" in body
    assert "**Status:** proposed" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_adr_create.py::test_first_adr_is_0001 -v`
Expected: FAIL — `bin/adr_create.py` doesn't exist.

- [ ] **Step 3: Create `bin/adr_create.py`**

```python
#!/usr/bin/env python3
"""Create a new ADR file in docs/adr/."""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ADR_TEMPLATE = """# {nnnn}. {title}

- **Status:** {status}
- **Date:** {today}

## Context

[neutral, pre-decision facts]

## Decision

[the decision]

## Consequences

[positive / negative / neutral]
"""


def kebab(title: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    return s


def find_max_nnnn(adr_dir: Path) -> int:
    pattern = re.compile(r"^(\d{4})-")
    nums = []
    for f in adr_dir.glob("*.md"):
        m = pattern.match(f.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) if nums else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a new ADR file.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--status", default="proposed")
    parser.add_argument("--project-dir", default=".")
    args = parser.parse_args(argv)

    slug = kebab(args.title)
    if not slug:
        print("Title produced empty kebab; provide letters/digits.", file=sys.stderr)
        return 2

    adr_dir = Path(args.project_dir).resolve() / "docs" / "adr"
    adr_dir.mkdir(parents=True, exist_ok=True)

    for attempt in range(3):
        nnnn = f"{find_max_nnnn(adr_dir) + 1 + attempt:04d}"
        target = adr_dir / f"{nnnn}-{slug}.md"
        if not target.exists():
            target.write_text(ADR_TEMPLATE.format(
                nnnn=nnnn, title=args.title, status=args.status,
                today=date.today().isoformat(),
            ))
            print(f"ADR-{nnnn}: {args.title}")
            return 0
    print("Could not allocate ADR number after 3 retries.", file=sys.stderr)
    return 5


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_adr_create.py::test_first_adr_is_0001 -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bin/adr_create.py tests/test_adr_create.py
git commit -m "feat(typed-artifacts): adr_create.py creates 0001 in empty dir"
```

---

### Task 20: `adr_create.py` — increment from existing files

**Files:**
- Modify: `tests/test_adr_create.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_adr_create.py`:
```python
def test_adr_increments_from_existing(project_dir: Path) -> None:
    adr_dir = project_dir / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    for n in (1, 2, 7):
        (adr_dir / f"{n:04d}-old.md").write_text(f"# {n:04d}. old\n")
    result = run_script("adr_create.py", "--title", "Newest one", cwd=project_dir)
    assert result.returncode == 0
    assert (adr_dir / "0008-newest-one.md").exists()
    assert "ADR-0008:" in result.stdout
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_adr_create.py::test_adr_increments_from_existing -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_adr_create.py
git commit -m "test(typed-artifacts): ADR number increments past existing"
```

---

### Task 21: `adr_create.py` — kebab handles punctuation; empty kebab exits 2

**Files:**
- Modify: `tests/test_adr_create.py`

- [ ] **Step 1: Write the tests**

Append to `tests/test_adr_create.py`:
```python
def test_kebab_strips_punctuation(project_dir: Path) -> None:
    result = run_script(
        "adr_create.py", "--title", "Switch JWT → opaque tokens (V2)!",
        cwd=project_dir,
    )
    assert result.returncode == 0
    files = list((project_dir / "docs" / "adr").glob("*.md"))
    assert files[0].name == "0001-switch-jwt-opaque-tokens-v2.md"


def test_empty_kebab_exits_2(project_dir: Path) -> None:
    result = run_script("adr_create.py", "--title", "!!!---!!!", cwd=project_dir)
    assert result.returncode == 2
    assert "kebab" in result.stderr.lower()
```

- [ ] **Step 2: Run tests**

Run: `python3 -m pytest tests/test_adr_create.py -v`
Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_adr_create.py
git commit -m "test(typed-artifacts): kebab punctuation handling and empty-kebab guard"
```

---

### Task 22: `artifact_review.py` — empty/initialized project produces clean report

**Files:**
- Create: `bin/artifact_review.py`
- Create: `tests/test_artifact_review.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_artifact_review.py`:
```python
from __future__ import annotations

from pathlib import Path

from .conftest import run_script


def test_review_empty_project_reports_no_entries(initialized_project: Path) -> None:
    result = run_script("artifact_review.py", cwd=initialized_project)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "BUGS.md" in out
    assert "no entries" in out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_artifact_review.py::test_review_empty_project_reports_no_entries -v`
Expected: FAIL — script doesn't exist.

- [ ] **Step 3: Create `bin/artifact_review.py`**

```python
#!/usr/bin/env python3
"""Read-only summary of typed-artifact entries grouped by file."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ARTIFACT_FILES = [
    ("BUGS.md", "BUG"),
    ("DEFERRED.md", "DEFER"),
    ("TEST_BACKLOG.md", "TEST"),
    ("proposals.md", "PROPOSAL"),
]


def parse_entries(text: str, header: str) -> list[dict]:
    """Return list of {id, title, fields} dicts parsed from artifact text."""
    entry_re = re.compile(rf"^##\s+{re.escape(header)}-(\d+):\s*(.+)$", re.MULTILINE)
    field_re = re.compile(r"^-\s+\*\*(.+?)\*\*:\s*(.+)$", re.MULTILINE)

    matches = list(entry_re.finditer(text))
    entries = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        fields = {fm.group(1): fm.group(2).strip() for fm in field_re.finditer(block)}
        entries.append({"id": int(m.group(1)), "title": m.group(2).strip(), "fields": fields})
    return entries


def render_report(project: Path) -> str:
    lines: list[str] = []
    for filename, header in ARTIFACT_FILES:
        path = project / filename
        if not path.exists():
            lines.append(f"## {filename}: file not found")
            continue
        entries = parse_entries(path.read_text(), header)
        if not entries:
            lines.append(f"## {filename}: no entries")
            continue
        lines.append(f"## {filename}: {len(entries)} entries")
        for e in entries:
            sev = e["fields"].get("Severity") or e["fields"].get("Priority") or "-"
            lines.append(f"  - {header}-{e['id']} [{sev}] {e['title']}")
    adr_dir = project / "docs" / "adr"
    if adr_dir.exists():
        adrs = sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md"))
        lines.append(f"## docs/adr/: {len(adrs)} ADRs")
        for f in adrs:
            lines.append(f"  - {f.name}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize typed-artifact entries.")
    parser.add_argument("--project-dir", default=".")
    args = parser.parse_args(argv)

    project = Path(args.project_dir).resolve()
    print(render_report(project))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_review.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bin/artifact_review.py tests/test_artifact_review.py
git commit -m "feat(typed-artifacts): artifact_review.py read-only summary"
```

---

### Task 23: `artifact_review.py` — populated entries grouped correctly

**Files:**
- Modify: `tests/test_artifact_review.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_artifact_review.py`:
```python
def test_review_lists_populated_entries(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + (
        "\n## BUG-1: alpha\n- **File**: a:1\n- **Description**: x\n- **Severity**: high\n"
        "\n## BUG-2: beta\n- **File**: b:1\n- **Description**: y\n- **Severity**: low\n"
    ))
    defers = initialized_project / "DEFERRED.md"
    defers.write_text(defers.read_text() + (
        "\n## DEFER-1: refactor\n- **Why deferred**: out of scope\n- **Priority**: P2\n"
    ))
    result = run_script("artifact_review.py", cwd=initialized_project)
    assert result.returncode == 0
    out = result.stdout
    assert "BUGS.md: 2 entries" in out
    assert "BUG-1 [high] alpha" in out
    assert "BUG-2 [low] beta" in out
    assert "DEFERRED.md: 1 entries" in out
    assert "DEFER-1 [P2] refactor" in out
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_artifact_review.py::test_review_lists_populated_entries -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_artifact_review.py
git commit -m "test(typed-artifacts): review reports entries with severity/priority"
```

---

## Phase 4: Hooks

### Task 24: `hooks/load_artifact_tail.sh` + tests

**Files:**
- Create: `hooks/load_artifact_tail.sh`
- Create: `tests/test_hooks.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_hooks.py`:
```python
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "hooks"


def run_hook(name: str, project_dir: Path, **extra_env: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir), **extra_env}
    return subprocess.run(
        ["bash", str(HOOKS_DIR / name)],
        env=env,
        capture_output=True,
        text=True,
    )


def test_load_tail_suggests_init_when_no_artifacts(project_dir: Path) -> None:
    r = run_hook("load_artifact_tail.sh", project_dir)
    assert r.returncode == 0
    assert "/quirk:artifacts:init" in r.stdout


def test_load_tail_emits_tail_when_artifacts_exist(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: alpha\n- **Severity**: high\n")
    r = run_hook("load_artifact_tail.sh", initialized_project)
    assert r.returncode == 0
    assert "BUG-1: alpha" in r.stdout


def test_load_tail_silent_when_project_dir_unset(project_dir: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    r = subprocess.run(
        ["bash", str(HOOKS_DIR / "load_artifact_tail.sh")],
        env=env, capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert r.stdout == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_hooks.py -v -k load_tail`
Expected: 3 FAIL — script doesn't exist.

- [ ] **Step 3: Create `hooks/load_artifact_tail.sh`**

```bash
#!/usr/bin/env bash
set -u
# SessionStart hook for typed-artifacts.
# - If artifact files exist: print last lines so Claude has context.
# - If artifact files are missing: suggest /quirk:artifacts:init.
# - If $CLAUDE_PROJECT_DIR is unset: silent no-op.
# Always exits 0.

[[ -z "${CLAUDE_PROJECT_DIR:-}" ]] && exit 0
[[ ! -d "$CLAUDE_PROJECT_DIR" ]] && exit 0

ARTIFACTS=(BUGS.md DEFERRED.md TEST_BACKLOG.md proposals.md)
present=0
for f in "${ARTIFACTS[@]}"; do
  [[ -f "$CLAUDE_PROJECT_DIR/$f" ]] && present=$((present+1))
done

if [[ $present -eq 0 ]]; then
  echo "[quirk:typed-artifacts] No artifact files in this project. Run /quirk:artifacts:init to scaffold."
  exit 0
fi

for f in "${ARTIFACTS[@]}"; do
  path="$CLAUDE_PROJECT_DIR/$f"
  [[ -f "$path" ]] || continue
  size=$(wc -c <"$path" 2>/dev/null || echo 0)
  if [[ "$size" -gt 1048576 ]]; then
    echo "[quirk:typed-artifacts] $f >1MB; skipping tail load."
    continue
  fi
  echo "----- $f (last 50 lines) -----"
  tail -n 50 "$path"
  echo ""
done

exit 0
```

Mark executable:
```bash
chmod +x hooks/load_artifact_tail.sh
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_hooks.py -v -k load_tail`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add hooks/load_artifact_tail.sh tests/test_hooks.py
git commit -m "feat(typed-artifacts): SessionStart hook loads artifact tails"
```

---

### Task 25: `hooks/lint_tics.sh` + tests

**Files:**
- Create: `hooks/lint_tics.sh`
- Modify: `tests/test_hooks.py`

PostToolUse hook receives JSON on stdin including `tool_input.file_path`. Hook reads the JSON, extracts the file path, greps for tic phrases, emits a warning if matched. Always exit 0.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_hooks.py`:
```python
import json


def stdin_for_edit(file_path: Path) -> str:
    return json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(file_path)}})


def run_hook_with_stdin(name: str, stdin: str, project_dir: Path, **extra_env: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir), **extra_env}
    return subprocess.run(
        ["bash", str(HOOKS_DIR / name)],
        env=env, input=stdin, capture_output=True, text=True,
    )


def test_lint_tics_warns_on_match(initialized_project: Path) -> None:
    bad = initialized_project / "thing.py"
    bad.write_text("# this is a pre-existing thing — should be flagged\n")
    r = run_hook_with_stdin("lint_tics.sh", stdin_for_edit(bad), initialized_project)
    assert r.returncode == 0
    assert "pre-existing" in r.stdout.lower()
    assert "BUGS.md" in r.stdout


def test_lint_tics_silent_on_no_match(initialized_project: Path) -> None:
    ok = initialized_project / "thing.py"
    ok.write_text("# clean code\n")
    r = run_hook_with_stdin("lint_tics.sh", stdin_for_edit(ok), initialized_project)
    assert r.returncode == 0
    assert r.stdout == ""


def test_lint_tics_silent_on_binary(initialized_project: Path) -> None:
    bin_file = initialized_project / "thing.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03")
    r = run_hook_with_stdin("lint_tics.sh", stdin_for_edit(bin_file), initialized_project)
    assert r.returncode == 0
    assert r.stdout == ""


def test_lint_tics_silent_when_no_artifacts(project_dir: Path) -> None:
    f = project_dir / "x.py"
    f.write_text("pre-existing code here\n")
    r = run_hook_with_stdin("lint_tics.sh", stdin_for_edit(f), project_dir)
    assert r.returncode == 0
    assert r.stdout == ""  # no artifacts → don't warn
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_hooks.py -v -k lint_tics`
Expected: 4 FAIL — script doesn't exist.

- [ ] **Step 3: Create `hooks/lint_tics.sh`**

```bash
#!/usr/bin/env bash
set -u
# PostToolUse hook for typed-artifacts.
# - Reads JSON from stdin; extracts tool_input.file_path.
# - Greps the file for tic phrases from templates/tic_phrases.json.
# - On match: emits a warning suggesting the routing destination.
# - On no match, no artifacts, missing file, missing patterns, or binary file: silent.
# Always exits 0.

[[ -z "${CLAUDE_PROJECT_DIR:-}" ]] && exit 0
[[ ! -f "$CLAUDE_PROJECT_DIR/BUGS.md" ]] && exit 0  # gate on artifacts

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")")}"
PHRASES="$PLUGIN_ROOT/templates/tic_phrases.json"
[[ -f "$PHRASES" ]] || exit 0

# Read stdin; extract file_path with python (json on path everywhere).
stdin_json="$(cat 2>/dev/null || true)"
[[ -z "$stdin_json" ]] && exit 0

file_path="$(printf '%s' "$stdin_json" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get("tool_input",{}).get("file_path",""))
except Exception:
    pass' 2>/dev/null)"

[[ -z "$file_path" ]] && exit 0
[[ ! -f "$file_path" ]] && exit 0

# Skip binaries.
if file -b --mime "$file_path" 2>/dev/null | grep -qv 'charset=utf-8\|charset=us-ascii\|charset=binary'; then
  :
fi
if grep -qIc . "$file_path" >/dev/null 2>&1; then
  :  # text file
else
  # grep -I returns no output for binary; skip
  if ! grep -Iq '' "$file_path" 2>/dev/null; then
    exit 0
  fi
fi

# Extract phrase list with python.
phrases="$(python3 -c 'import json,sys
with open("'"$PHRASES"'") as f: d=json.load(f)
for p in d.get("patterns",[]):
    print(p["phrase"]+"\t"+p["suggested_artifact"])' 2>/dev/null)"

[[ -z "$phrases" ]] && exit 0

while IFS=$'\t' read -r phrase artifact; do
  [[ -z "$phrase" ]] && continue
  if grep -nFi -- "$phrase" "$file_path" >/dev/null 2>&1; then
    line=$(grep -nFi -- "$phrase" "$file_path" | head -n 1 | cut -d: -f1)
    echo "[quirk:typed-artifacts] Tic phrase '$phrase' detected at $file_path:$line — consider routing to $artifact"
  fi
done <<< "$phrases"

exit 0
```

```bash
chmod +x hooks/lint_tics.sh
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_hooks.py -v -k lint_tics`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add hooks/lint_tics.sh tests/test_hooks.py
git commit -m "feat(typed-artifacts): PostToolUse hook lints for tic phrases"
```

---

### Task 26: `hooks/wrap_session.sh` + tests

**Files:**
- Create: `hooks/wrap_session.sh`
- Modify: `tests/test_hooks.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_hooks.py`:
```python
def test_wrap_session_emits_reminder_when_artifacts_exist(initialized_project: Path) -> None:
    r = run_hook("wrap_session.sh", initialized_project)
    assert r.returncode == 0
    assert "Route any unrouted observations" in r.stdout


def test_wrap_session_silent_when_no_artifacts(project_dir: Path) -> None:
    r = run_hook("wrap_session.sh", project_dir)
    assert r.returncode == 0
    assert r.stdout == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_hooks.py -v -k wrap_session`
Expected: 2 FAIL.

- [ ] **Step 3: Create `hooks/wrap_session.sh`**

```bash
#!/usr/bin/env bash
set -u
# Stop hook for typed-artifacts.
# - Emits a one-line wrap-up reminder if artifact files exist.
# - Silent otherwise.
# Always exits 0.

[[ -z "${CLAUDE_PROJECT_DIR:-}" ]] && exit 0
[[ ! -f "$CLAUDE_PROJECT_DIR/BUGS.md" ]] && exit 0

echo "[quirk:typed-artifacts] Before closing: Route any unrouted observations to BUGS.md / DEFERRED.md / TEST_BACKLOG.md / proposals.md."
exit 0
```

```bash
chmod +x hooks/wrap_session.sh
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_hooks.py -v -k wrap_session`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add hooks/wrap_session.sh tests/test_hooks.py
git commit -m "feat(typed-artifacts): Stop hook emits wrap-up reminder"
```

---

### Task 27: `hooks/hooks.json` wiring + structural test

**Files:**
- Create: `hooks/hooks.json`
- Modify: `tests/test_hooks.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_hooks.py`:
```python
def test_hooks_json_structure() -> None:
    config = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text())
    hooks = config["hooks"]
    assert "SessionStart" in hooks
    assert "PostToolUse" in hooks
    assert "Stop" in hooks

    post = hooks["PostToolUse"][0]
    assert post["matcher"] == "Edit|Write"
    assert "lint_tics.sh" in post["hooks"][0]["command"]
    assert "${CLAUDE_PLUGIN_ROOT}" in post["hooks"][0]["command"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_hooks.py::test_hooks_json_structure -v`
Expected: FAIL — file doesn't exist.

- [ ] **Step 3: Create `hooks/hooks.json`**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/load_artifact_tail.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/lint_tics.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/wrap_session.sh"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_hooks.py::test_hooks_json_structure -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hooks/hooks.json tests/test_hooks.py
git commit -m "feat(typed-artifacts): hooks.json wires SessionStart/PostToolUse/Stop"
```

---

## Phase 5: Slash commands

These are markdown prompt files. Each is short and follows the same pattern: parse `$ARGUMENTS`, invoke `bin/*.py` via Bash, relay stdout. Tests are static regex checks.

### Task 28: `commands/artifacts/init.md`

**Files:**
- Create: `commands/artifacts/init.md`
- Create: `tests/test_commands.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_commands.py`:
```python
from __future__ import annotations

from pathlib import Path

import re

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = REPO_ROOT / "commands" / "artifacts"


def test_init_command_invokes_artifact_init(project_dir: Path) -> None:
    body = (COMMANDS_DIR / "init.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/bin/artifact_init.py" in body
    assert "$ARGUMENTS" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_commands.py::test_init_command_invokes_artifact_init -v`
Expected: FAIL — file doesn't exist.

- [ ] **Step 3: Create `commands/artifacts/init.md`**

```markdown
---
description: Scaffold typed-artifact files (BUGS, DEFERRED, TEST_BACKLOG, proposals, docs/adr/) into this project.
---

Scaffold typed-artifact files into the current project.

Run this command:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/artifact_init.py --project-dir "$CLAUDE_PROJECT_DIR" $ARGUMENTS
```

Then:
1. Relay the script's stdout (`Created: ...` / `Skipped: ...`) to the user.
2. If the script created artifact files, do NOT continue and read them yourself — they are templates and the schema headers are intentionally inert. Just confirm setup is complete.
3. If the user passed `--force`, mention that timestamped backups were created next to any overwritten files.
4. Suggest one of: `/quirk:artifacts:bug`, `/quirk:artifacts:defer`, `/quirk:artifacts:adr`, or `/quirk:artifacts:review-artifacts` as the next step.

If the script exited non-zero, relay the stderr verbatim and propose how to fix it (e.g., make the project dir writable).
```

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_commands.py::test_init_command_invokes_artifact_init -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commands/artifacts/init.md tests/test_commands.py
git commit -m "feat(typed-artifacts): /quirk:artifacts:init slash command"
```

---

### Task 29: `commands/artifacts/bug.md`, `defer.md`, `test-skip.md` (three append shortcuts)

**Files:**
- Create: `commands/artifacts/bug.md`
- Create: `commands/artifacts/defer.md`
- Create: `commands/artifacts/test-skip.md`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_commands.py`:
```python
import pytest


@pytest.mark.parametrize("cmd, kind", [
    ("bug.md", "bug"),
    ("defer.md", "defer"),
    ("test-skip.md", "test-skip"),
])
def test_shortcut_command_invokes_artifact_append(cmd: str, kind: str) -> None:
    body = (COMMANDS_DIR / cmd).read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/bin/artifact_append.py" in body
    assert kind in body
    assert "$ARGUMENTS" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_commands.py -v -k shortcut`
Expected: 3 FAIL.

- [ ] **Step 3: Create `commands/artifacts/bug.md`**

```markdown
---
description: Append a BUG-N entry to BUGS.md. Use when you've noticed a bug you cannot fix in the current scope.
---

The user has surfaced a bug to log. Required fields: `title`, `file` (path:line), `description`, `severity` (critical/high/medium/low).

Parse `$ARGUMENTS` for these fields. If any required field is missing or ambiguous, ask exactly one clarifying question — do NOT guess defaults.

When you have all four fields, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/artifact_append.py bug \
  --project-dir "$CLAUDE_PROJECT_DIR" \
  --field "title=$TITLE" \
  --field "file=$FILE_LINE" \
  --field "description=$DESCRIPTION" \
  --field "severity=$SEVERITY"
```

Optional fields you may also pass if the user provided them: `introduced_by`, `proposed_fix`, `blocker_for`.

After the script returns:
1. On exit 0: relay the `BUG-N: title` line from stdout, then confirm `Logged BUG-N → BUGS.md`. Do not narrate further unless severity is `critical`.
2. On exit 3 (`BUGS.md not found`): tell the user to run `/quirk:artifacts:init` first.
3. On any other non-zero exit: relay stderr verbatim plus a one-line plain-language summary and a remediation hint.

User input: $ARGUMENTS
```

- [ ] **Step 4: Create `commands/artifacts/defer.md`**

```markdown
---
description: Append a DEFER-N entry to DEFERRED.md for tasks that are out of scope for the current session.
---

The user has surfaced a task to defer. Required fields: `title`, `why_deferred`, `priority` (P1/P2/P3/P4).

Parse `$ARGUMENTS` for these fields. If a required field is missing, ask exactly one clarifying question.

When you have all three fields, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/artifact_append.py defer \
  --project-dir "$CLAUDE_PROJECT_DIR" \
  --field "title=$TITLE" \
  --field "why_deferred=$WHY" \
  --field "priority=$PRIORITY"
```

Optional fields: `session_context`, `estimated_effort` (S/M/L), `proposed_owner`.

After the script returns:
1. On exit 0: relay `DEFER-N: title` and confirm `Logged DEFER-N → DEFERRED.md`.
2. On exit 3: suggest `/quirk:artifacts:init`.
3. On any other non-zero exit: relay stderr verbatim with a remediation hint.

User input: $ARGUMENTS
```

- [ ] **Step 5: Create `commands/artifacts/test-skip.md`**

```markdown
---
description: Append a TEST-N entry to TEST_BACKLOG.md for skipped or abbreviated tests.
---

The user has surfaced a skipped test to log. Required fields: `title`, `file_under_test`, `reason_skipped`.

Parse `$ARGUMENTS`. If a required field is missing, ask exactly one clarifying question.

When you have the required fields, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/artifact_append.py test-skip \
  --project-dir "$CLAUDE_PROJECT_DIR" \
  --field "title=$TITLE" \
  --field "file_under_test=$FILE_UNDER_TEST" \
  --field "reason_skipped=$REASON"
```

Optional fields: `test_type` (unit/integration/e2e), `edge_cases`, `priority` (P1–P4).

After the script returns:
1. On exit 0: relay `TEST-N: title` and confirm `Logged TEST-N → TEST_BACKLOG.md`.
2. On exit 3: suggest `/quirk:artifacts:init`.
3. On any other non-zero exit: relay stderr verbatim with a remediation hint.

User input: $ARGUMENTS
```

- [ ] **Step 6: Run tests**

Run: `python3 -m pytest tests/test_commands.py -v -k shortcut`
Expected: 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add commands/artifacts/bug.md commands/artifacts/defer.md commands/artifacts/test-skip.md tests/test_commands.py
git commit -m "feat(typed-artifacts): /quirk:artifacts:{bug,defer,test-skip} shortcuts"
```

---

### Task 30: `commands/artifacts/triage.md`

**Files:**
- Create: `commands/artifacts/triage.md`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands.py`:
```python
def test_triage_command_classifies_then_appends() -> None:
    body = (COMMANDS_DIR / "triage.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/bin/artifact_append.py" in body
    # must mention all four destinations
    for kind in ("bug", "defer", "test-skip", "proposal"):
        assert kind in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_commands.py::test_triage_command_classifies_then_appends -v`
Expected: FAIL.

- [ ] **Step 3: Create `commands/artifacts/triage.md`**

```markdown
---
description: Classify an observation into bug / defer / test-skip / proposal and append a structured entry. Use when the routing destination isn't obvious.
---

You have an observation that needs routing but the user did not specify a category. Your job is to:

1. Classify the observation into ONE of: `bug`, `defer`, `test-skip`, `proposal`.
   - **bug** — concrete defect that exists in the code right now (wrong behavior, error, regression).
   - **defer** — work that is out of scope for the current session (not a defect; just not now).
   - **test-skip** — a test that should exist but was skipped or abbreviated.
   - **proposal** — architectural concern, design suggestion, or unsettled tradeoff that requires human judgment.
2. If two categories are equally plausible, ask the user one clarifying question with the two options. Do NOT pick.
3. Extract the required fields for the chosen category:
   - bug: title, file (path:line), description, severity
   - defer: title, why_deferred, priority
   - test-skip: title, file_under_test, reason_skipped
   - proposal: title, context, recommendation
4. Run the script:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/artifact_append.py <CATEGORY> \
  --project-dir "$CLAUDE_PROJECT_DIR" \
  --field "title=..." \
  ... (one --field per required arg) ...
```

5. Relay the entry ID and destination file to the user. If the script exited non-zero, relay stderr and a remediation hint.

The script re-validates required fields per the chosen schema. If your classification was wrong, the entry still lands in plain markdown — the user can move it manually.

User input: $ARGUMENTS
```

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_commands.py::test_triage_command_classifies_then_appends -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commands/artifacts/triage.md tests/test_commands.py
git commit -m "feat(typed-artifacts): /quirk:artifacts:triage classifier command"
```

---

### Task 31: `commands/artifacts/adr.md`

**Files:**
- Create: `commands/artifacts/adr.md`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands.py`:
```python
def test_adr_command_invokes_adr_create() -> None:
    body = (COMMANDS_DIR / "adr.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/bin/adr_create.py" in body
    assert "$ARGUMENTS" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_commands.py::test_adr_command_invokes_adr_create -v`
Expected: FAIL.

- [ ] **Step 3: Create `commands/artifacts/adr.md`**

```markdown
---
description: Create a new Architecture Decision Record (ADR) in docs/adr/. Use to record a significant architectural decision.
---

Create a new ADR. The argument is the title.

If `$ARGUMENTS` is empty or whitespace, ask the user for the title — do not guess.

Run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/adr_create.py \
  --project-dir "$CLAUDE_PROJECT_DIR" \
  --title "$ARGUMENTS"
```

After the script returns:
1. On exit 0: relay `ADR-NNNN: title` from stdout. Read the new file you just created and prompt the user to fill in Context, Decision, Consequences. Status defaults to `proposed`.
2. On exit 2 (empty kebab): tell the user the title needs letters or digits and ask for a revised one.
3. On any other non-zero exit: relay stderr verbatim with a remediation hint.

User input: $ARGUMENTS
```

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_commands.py::test_adr_command_invokes_adr_create -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commands/artifacts/adr.md tests/test_commands.py
git commit -m "feat(typed-artifacts): /quirk:artifacts:adr creates Nygard ADR"
```

---

### Task 32: `commands/artifacts/review-artifacts.md`

**Files:**
- Create: `commands/artifacts/review-artifacts.md`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands.py`:
```python
def test_review_artifacts_command_invokes_review_script() -> None:
    body = (COMMANDS_DIR / "review-artifacts.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/bin/artifact_review.py" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_commands.py::test_review_artifacts_command_invokes_review_script -v`
Expected: FAIL.

- [ ] **Step 3: Create `commands/artifacts/review-artifacts.md`**

```markdown
---
description: Read-only summary of all typed-artifact entries (bugs, deferred work, test backlog, proposals, ADRs).
---

Run a read-only review of all artifact files in this project. No mutation.

Run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/artifact_review.py --project-dir "$CLAUDE_PROJECT_DIR"
```

Then:
1. Render the script's stdout to the user verbatim (it's already grouped by file).
2. Identify the top 3 highest-severity / highest-priority items across all artifacts and surface them as a "Suggested triage order" list.
3. Flag any entries that look stale (e.g., DEFER-N items older than 30 days, BUG-N referencing files that no longer exist). Do NOT modify any artifact files.

User input: $ARGUMENTS (ignored — this command takes no args)
```

- [ ] **Step 4: Run test**

Run: `python3 -m pytest tests/test_commands.py::test_review_artifacts_command_invokes_review_script -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add commands/artifacts/review-artifacts.md tests/test_commands.py
git commit -m "feat(typed-artifacts): /quirk:artifacts:review-artifacts read-only summary"
```

---

## Phase 6: Skill + E2E

### Task 33: `skills/typed-artifacts/SKILL.md`

**Files:**
- Create: `skills/typed-artifacts/SKILL.md`
- Create: `tests/test_skill.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_skill.py`:
```python
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "typed-artifacts" / "SKILL.md"


def test_skill_has_frontmatter() -> None:
    body = SKILL_PATH.read_text()
    fm = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)
    assert fm is not None, "skill missing YAML frontmatter"
    fm_body = fm.group(1)
    assert re.search(r"^name:\s*typed-artifacts\s*$", fm_body, re.MULTILINE)
    assert re.search(r"^description:\s*.{30,}$", fm_body, re.MULTILINE)


def test_skill_description_lists_trigger_phrases() -> None:
    body = SKILL_PATH.read_text()
    fm = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL).group(1)
    description = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE).group(1)
    for trigger in ("BUGS.md", "out of scope", "pre-existing", "skipped"):
        assert trigger in description, f"description missing trigger phrase: {trigger}"


def test_skill_references_all_four_artifacts() -> None:
    body = SKILL_PATH.read_text()
    for name in ("BUGS.md", "DEFERRED.md", "TEST_BACKLOG.md", "proposals.md"):
        assert name in body
    assert "docs/adr/" in body


def test_skill_references_all_seven_commands() -> None:
    body = SKILL_PATH.read_text()
    for cmd in ("init", "bug", "defer", "test-skip", "triage", "adr", "review-artifacts"):
        assert f"/quirk:artifacts:{cmd}" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_skill.py -v`
Expected: 4 FAIL — file doesn't exist.

- [ ] **Step 3: Create `skills/typed-artifacts/SKILL.md`**

```markdown
---
name: typed-artifacts
description: Use when about to write hedging language like "pre-existing", "out of scope", "future work", "skipped for brevity", or "architectural concern" — instead, route the observation to a typed artifact (BUGS.md, DEFERRED.md, TEST_BACKLOG.md, proposals.md) or an ADR. Also use when the user invokes /quirk:artifacts:* commands or asks how to log a bug, defer a task, or record a decision.
---

# Typed Artifacts: Surface Routing

When you notice something you cannot act on in this session, do NOT bury it in prose. Route it to a typed artifact via one of the slash commands.

## The routing table

| If you're about to write… | Use this command | Lands in |
|---|---|---|
| "pre-existing", "already existed", "introduced before" | `/quirk:artifacts:bug` | `BUGS.md` |
| "out of scope", "future work", "larger refactor needed" | `/quirk:artifacts:defer` | `DEFERRED.md` |
| "skipped for brevity", "tests can be added later" | `/quirk:artifacts:test-skip` | `TEST_BACKLOG.md` |
| "worth reconsidering", "architectural concern", "worth revisiting" | `/quirk:artifacts:triage` (proposal) | `proposals.md` |
| "we made an architectural decision" | `/quirk:artifacts:adr` | `docs/adr/NNNN-*.md` |
| Don't know which fits | `/quirk:artifacts:triage` | one of the above |

After appending, **continue the current task**. Do NOT stop to discuss the routing entry unless severity is `critical`. The artifact is the discussion.

## Schemas (summary)

Full schemas live in the `templates/` directory of the quirk plugin. Required fields per artifact:

- **BUGS.md** (BUG-N): title, file (path:line), description, severity (critical/high/medium/low)
- **DEFERRED.md** (DEFER-N): title, why_deferred, priority (P1/P2/P3/P4)
- **TEST_BACKLOG.md** (TEST-N): title, file_under_test, reason_skipped
- **proposals.md** (PROPOSAL-N): title, context, recommendation
- **docs/adr/NNNN-*.md** (Nygard): title, status (proposed → accepted → superseded)

The mutation scripts re-validate required fields. Missing fields surface as a clarifying question — never invent values.

## When NOT to route

- The observation is the work you're doing right now → fix it, don't log it.
- The observation is a bug **you just introduced this session** → fix it, don't log it. The "Introduced by" field on BUGS.md is for things that pre-date your session.
- The observation is information about the user's intent → ask, don't log.

## First-time setup

If the user hasn't run `/quirk:artifacts:init` in this project yet, suggest it. Without artifact files in the project root, the append commands will exit 3.

## Review cadences

(Declared in the user's CLAUDE.md when `/init` runs.)

- BUGS.md — every PR
- DEFERRED.md — every sprint planning
- TEST_BACKLOG.md — every 2 weeks
- proposals.md / docs/adr/ — monthly with architect

Use `/quirk:artifacts:review-artifacts` to scan all four files in one read-only pass.
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_skill.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/typed-artifacts/SKILL.md tests/test_skill.py
git commit -m "feat(typed-artifacts): typed-artifacts routing skill"
```

---

### Task 34: End-to-end fixture test

**Files:**
- Create: `tests/test_e2e.py`

This is a single integration test that walks the full happy path: init → bug → defer → test-skip → adr → review. It catches regressions in any layer composing with another.

- [ ] **Step 1: Write the failing test**

Create `tests/test_e2e.py`:
```python
from __future__ import annotations

from pathlib import Path

from .conftest import run_script


def test_full_workflow(project_dir: Path) -> None:
    # Init
    r = run_script("artifact_init.py", "--no-claude-md", cwd=project_dir)
    assert r.returncode == 0, r.stderr
    for name in ["BUGS.md", "DEFERRED.md", "TEST_BACKLOG.md", "proposals.md"]:
        assert (project_dir / name).exists()
    assert (project_dir / "docs" / "adr" / "0000-record-architecture-decisions.md").exists()

    # Bug
    r = run_script(
        "artifact_append.py", "bug",
        "--field", "title=safari rejects cookie",
        "--field", "file=login.ts:42",
        "--field", "description=cookie has SameSite=None without Secure",
        "--field", "severity=high",
        cwd=project_dir,
    )
    assert r.returncode == 0
    assert "BUG-1: safari rejects cookie" in (project_dir / "BUGS.md").read_text()

    # Defer
    r = run_script(
        "artifact_append.py", "defer",
        "--field", "title=multi-tenant rate limits",
        "--field", "why_deferred=out of scope",
        "--field", "priority=P3",
        cwd=project_dir,
    )
    assert r.returncode == 0

    # Test skip
    r = run_script(
        "artifact_append.py", "test-skip",
        "--field", "title=oauth state CSRF",
        "--field", "file_under_test=auth/oauth.ts",
        "--field", "reason_skipped=mocking required",
        cwd=project_dir,
    )
    assert r.returncode == 0

    # ADR
    r = run_script(
        "adr_create.py", "--title", "Switch session storage from JWT to opaque tokens",
        cwd=project_dir,
    )
    assert r.returncode == 0
    assert (project_dir / "docs" / "adr" / "0001-switch-session-storage-from-jwt-to-opaque-tokens.md").exists()

    # Review
    r = run_script("artifact_review.py", cwd=project_dir)
    assert r.returncode == 0
    out = r.stdout
    assert "BUGS.md: 1 entries" in out
    assert "BUG-1 [high] safari rejects cookie" in out
    assert "DEFERRED.md: 1 entries" in out
    assert "DEFER-1 [P3] multi-tenant rate limits" in out
    assert "TEST_BACKLOG.md: 1 entries" in out
    assert "TEST-1 [-] oauth state CSRF" in out
    assert "docs/adr/: 2 ADRs" in out
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python3 -m pytest tests/test_e2e.py -v`
Expected: PASS (all units already implemented; this just composes them).

- [ ] **Step 3: Run the full suite**

Run: `python3 -m pytest -q`
Expected: all PASS, no skipped tests.

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test(typed-artifacts): end-to-end workflow integration"
```

---

## Phase 7: Ship

### Task 35: Bump plugin version + add keywords

**Files:**
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Update `.claude-plugin/plugin.json`**

Change:
```json
{
  "name": "quirk",
  "description": "Core skills library for Claude Code: TDD, debugging, collaboration patterns, and proven techniques",
  "version": "5.0.7",
  "author": {
    "name": "Zachary Young",
    "email": "zach@fabledfreedom.com"
  },
  "homepage": "https://github.com/zyoung/quirk",
  "repository": "https://github.com/zyoung/quirk",
  "license": "MIT",
  "keywords": [
    "skills",
    "tdd",
    "debugging",
    "collaboration",
    "best-practices",
    "workflows"
  ]
}
```

To:
```json
{
  "name": "quirk",
  "description": "Core skills library for Claude Code: TDD, debugging, collaboration patterns, typed artifacts, and proven techniques",
  "version": "5.1.0",
  "author": {
    "name": "Zachary Young",
    "email": "zach@fabledfreedom.com"
  },
  "homepage": "https://github.com/zyoung/quirk",
  "repository": "https://github.com/zyoung/quirk",
  "license": "MIT",
  "keywords": [
    "skills",
    "tdd",
    "debugging",
    "collaboration",
    "best-practices",
    "workflows",
    "typed-artifacts",
    "surface-routing"
  ]
}
```

Also update the version in `.claude-plugin/marketplace.json`:
```json
"version": "5.1.0",
```

- [ ] **Step 2: Verify plugin manifest is valid JSON**

Run: `python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])"`
Expected: `5.1.0`

Run: `python3 -c "import json; print(json.load(open('.claude-plugin/marketplace.json'))['plugins'][0]['version'])"`
Expected: `5.1.0`

- [ ] **Step 3: Commit**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore(typed-artifacts): bump quirk plugin version to 5.1.0"
```

---

### Task 36: Add README section + final integration

**Files:**
- Create or modify: `README.md`

- [ ] **Step 1: Check whether `README.md` exists**

Run: `ls README.md 2>/dev/null && echo PRESENT || echo MISSING`

- [ ] **Step 2: If missing, create `README.md`. If present, append a `## Typed artifacts` section.**

If creating fresh, write:

```markdown
# quirk

Core skills library for Claude Code: TDD, debugging, collaboration patterns, typed artifacts, and proven techniques.

Version: **5.1.0**

## What ships

- **15 skills** under `skills/` covering TDD, systematic debugging, brainstorming, plan writing, code review, parallel agent dispatch, and more.
- **Typed artifacts** (added in 5.1.0) — surface-routing for observations Claude cannot act on. See below.

## Installation

Install via the quirk-dev marketplace (`.claude-plugin/marketplace.json`).

## Typed artifacts

A discipline for routing deferred observations into structured markdown files instead of burying them in prose ("pre-existing", "out of scope", "skipped for brevity").

### Quick start

In your project, run:

```
/quirk:artifacts:init
```

That scaffolds `BUGS.md`, `DEFERRED.md`, `TEST_BACKLOG.md`, `proposals.md`, and `docs/adr/`. It also appends a 5-line trigger snippet to your project's `CLAUDE.md` (use `--no-claude-md` to skip that).

### Slash commands

| Command | Purpose |
|---|---|
| `/quirk:artifacts:init` | Scaffold artifact files into the current project |
| `/quirk:artifacts:bug` | Append a BUG-N entry to BUGS.md |
| `/quirk:artifacts:defer` | Append a DEFER-N entry to DEFERRED.md |
| `/quirk:artifacts:test-skip` | Append a TEST-N entry to TEST_BACKLOG.md |
| `/quirk:artifacts:triage` | Classify an observation and append to the right file |
| `/quirk:artifacts:adr` | Create a new Architecture Decision Record |
| `/quirk:artifacts:review-artifacts` | Read-only summary of all entries |

### Hooks

Three lifecycle hooks (warn-only, never block):

- **SessionStart** loads tail of artifact files (or suggests `/init` if none exist).
- **PostToolUse** lints written files for tic phrases ("pre-existing", etc.).
- **Stop** posts a wrap-up reminder.

All three gate on artifact-file presence — they are inert no-ops in projects that haven't run `/quirk:artifacts:init`.

### Design + spec

See `docs/specs/2026-05-04-typed-artifacts-design.md`.

## Development

```bash
python3 -m pytest -q
```

Stdlib-only Python 3.9+. No third-party dependencies.
```

If `README.md` already exists, append the `## Typed artifacts` section after the existing content.

- [ ] **Step 3: Final smoke test of the full repo**

Run: `python3 -m pytest -q`
Expected: all PASS.

Run: `git status`
Expected: clean working tree (or just the README staged).

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "docs(typed-artifacts): document typed-artifacts in README"
```

- [ ] **Step 5: Tag the release**

```bash
git tag -a v5.1.0 -m "release 5.1.0: typed-artifacts module"
git log --oneline | head -10
```

---

## Self-review checklist (run after writing the plan)

- [x] Spec section 5.1 (manifest) → Task 35
- [x] Spec section 5.2 (skill) → Task 33
- [x] Spec section 5.3 (commands × 7) → Tasks 28–32
- [x] Spec section 5.4 (hooks × 3 + hooks.json) → Tasks 24–27
- [x] Spec section 5.5 (`bin/*.py` × 4) → Tasks 4–14, 15–18, 19–21, 22–23
- [x] Spec section 5.6 (templates × 7) → Tasks 2–3
- [x] Spec section 6 (schemas) → Tasks 2–3 (templates) + Task 4 (schema dict)
- [x] Spec section 7 (data flows) → Tasks 6 (append), 15 (init), 19 (ADR), 22 (review), 24/25/26 (hooks), 34 (E2E composes all)
- [x] Spec section 8 (error handling) → Tasks 4 (unknown type), 5 (missing required), 9 (schema mismatch), 10 (missing file), 12 (flock), 13 (lock contention)
- [x] Spec section 9 (testing layers) → all tasks include tests; Task 34 covers E2E

---

## Execution

Plan complete and saved to `docs/plans/2026-05-04-typed-artifacts.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
