from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from .conftest import TEMPLATES_DIR, run_script

ROOT_TEMPLATES = ["BUGS.md", "DEFERRED.md", "TEST_BACKLOG.md", "proposals.md"]

ROADMAP_TEMPLATE = """<!-- schema-version: 2 -->
<!-- ROADMAP.md SCHEMA
Ordered milestones, each naming BUG/DEFER/TEST entry IDs. Milestones are ordered
top-to-bottom; earlier milestones rank higher for --next's sort key. An ID should
appear in at most one milestone (--doctor flags duplicates). PROPOSAL entries are
never valid roadmap members. This file is agent-proposed, human-ratified — see
/quirk:pm:roadmap. Manual edits are allowed; pm.py re-parses on every run.

Milestone format:
## Milestone: Auth hardening
- BUG-3
- DEFER-7
- TEST-12

## Milestone: Search v2
- BUG-9
-->

# ROADMAP

No milestones yet. Run `/quirk:pm:roadmap` to propose a grouping.
"""

# The spec's worked example (tech.md:363-383). It is a grammar-conformance fixture,
# not what init scaffolds: shipping live milestones would give every fresh project
# four DANGLING_ROADMAP_REF findings for IDs that do not exist.
SPEC_ROADMAP_EXAMPLE = """<!-- schema-version: 2 -->
<!-- ROADMAP.md SCHEMA
Ordered milestones, each naming BUG/DEFER/TEST entry IDs. Milestones are ordered
top-to-bottom; earlier milestones rank higher for --next's sort key. An ID should
appear in at most one milestone (--doctor flags duplicates). PROPOSAL entries are
never valid roadmap members. This file is agent-proposed, human-ratified — see
/quirk:pm:roadmap. Manual edits are allowed; pm.py re-parses on every run.
-->

# ROADMAP

## Milestone: Auth hardening
- BUG-3
- DEFER-7
- TEST-12

## Milestone: Search v2
- BUG-9
"""


def test_scaffolded_roadmap_names_no_entry_ids() -> None:
    """A fresh roadmap must be empty — a live member is a dangling reference on day one."""
    body = ROADMAP_TEMPLATE.rsplit("-->", 1)[1]
    assert "## Milestone:" not in body

PROPOSALS_REST = """<!-- proposals.md SCHEMA (append only)
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
"""


def test_all_ledger_templates_declare_schema_v2() -> None:
    for name in ROOT_TEMPLATES:
        text = (TEMPLATES_DIR / name).read_text()
        assert "<!-- schema-version: 2 -->" in text, name


@pytest.mark.parametrize("name", ["BUGS.md", "DEFERRED.md", "TEST_BACKLOG.md"])
def test_ledger_templates_document_v2_fields(name: str) -> None:
    text = (TEMPLATES_DIR / name).read_text()
    assert "- **Blocked by**: [comma-separated BUG-N/DEFER-N/TEST-N, or omit]" in text
    assert (
        "The fields below are written only by pm.py — never by hand, never via\n"
        "artifact_append.py. Absent Status means open."
    ) in text
    assert "- **Status**: [in_progress / delivered / closed / wontfix / superseded — see /quirk:pm:status]" in text
    assert "- **Probe**: [set at `pm start`, updated at `pm finish`]" in text
    assert "- **Handoff**: [set at `pm start` when dispatched]" in text


def test_test_backlog_documents_logged_field() -> None:
    text = (TEMPLATES_DIR / "TEST_BACKLOG.md").read_text()
    assert "- **Logged**: [date, auto-stamped like Observed/Deferred/Proposed on every other type]" in text


def test_proposals_only_version_marker_changed() -> None:
    text = (TEMPLATES_DIR / "proposals.md").read_text()
    assert text.startswith("<!-- schema-version: 2 -->\n")
    rest = text.split("\n", 1)[1]
    assert rest == PROPOSALS_REST


def test_roadmap_template_matches_spec_literal() -> None:
    assert (TEMPLATES_DIR / "ROADMAP.md").read_text() == ROADMAP_TEMPLATE


def test_init_scaffolds_roadmap(project_dir: Path) -> None:
    result = run_script("artifact_init.py", cwd=project_dir)
    assert result.returncode == 0, result.stderr
    assert (project_dir / "ROADMAP.md").exists()
    assert (project_dir / "ROADMAP.md").read_text() == ROADMAP_TEMPLATE


def test_init_skips_roadmap_when_present(project_dir: Path) -> None:
    run_script("artifact_init.py", cwd=project_dir)
    before = (project_dir / "ROADMAP.md").read_text()

    result = run_script("artifact_init.py", cwd=project_dir)
    assert result.returncode == 0, result.stderr
    assert "Skipped" in result.stdout
    assert "ROADMAP.md" in result.stdout
    assert (project_dir / "ROADMAP.md").read_text() == before


def test_v1_file_append_succeeds_without_v2_fields(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text().replace("schema-version: 2", "schema-version: 1"))

    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=v1 append",
        "--field", "file=x:1",
        "--field", "description=d",
        "--field", "severity=low",
        cwd=initialized_project,
    )
    assert result.returncode == 0, result.stderr
    body = bugs.read_text()
    entry = body.split("## BUG-1: v1 append", 1)[1]
    assert "**Blocked by**" not in entry


def test_v1_file_explicit_v2_field_refuses_and_writes_nothing(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text().replace("schema-version: 2", "schema-version: 1"))
    before = bugs.read_text()

    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=v1 append",
        "--field", "file=x:1",
        "--field", "description=d",
        "--field", "severity=low",
        "--field", "blocked_by=BUG-1",
        cwd=initialized_project,
    )
    assert result.returncode == 8
    assert "blocked_by" in result.stderr.lower()
    assert "migrate" in result.stderr.lower()
    assert bugs.read_text() == before


def test_test_skip_v2_file_autostamps_logged(initialized_project: Path) -> None:
    result = run_script(
        "artifact_append.py", "test-skip",
        "--field", "title=edge case",
        "--field", "file_under_test=auth.ts",
        "--field", "reason_skipped=complexity",
        cwd=initialized_project,
    )
    assert result.returncode == 0, result.stderr
    body = (initialized_project / "TEST_BACKLOG.md").read_text()
    assert f"**Logged**: {date.today().isoformat()}" in body


def test_test_skip_v1_file_appends_with_no_logged_line(initialized_project: Path) -> None:
    backlog = initialized_project / "TEST_BACKLOG.md"
    backlog.write_text(backlog.read_text().replace("schema-version: 2", "schema-version: 1"))

    result = run_script(
        "artifact_append.py", "test-skip",
        "--field", "title=edge case",
        "--field", "file_under_test=auth.ts",
        "--field", "reason_skipped=complexity",
        cwd=initialized_project,
    )
    assert result.returncode == 0, result.stderr
    body = backlog.read_text()
    entry = body.split("## TEST-1: edge case", 1)[1]
    assert "**Logged**" not in entry


def test_v3_file_still_refused_upper_bound(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text().replace("schema-version: 2", "schema-version: 3"))

    result = run_script(
        "artifact_append.py", "bug",
        "--field", "title=t", "--field", "file=x:1",
        "--field", "description=d", "--field", "severity=low",
        cwd=initialized_project,
    )
    assert result.returncode == 8
