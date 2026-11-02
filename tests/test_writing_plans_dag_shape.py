"""Pins the writing-plans rules that keep SDD task graphs shallow.

SDD runs a plan's tasks in parallel, so these rules decide a run's wall-clock time. The plan reviewer
and the self-review audit plans against the same edge kinds and size ceiling, so the literals must
agree across the files that state them.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLANS = REPO_ROOT / "skills" / "writing-plans"
SKILL = PLANS / "SKILL.md"
REVIEWER = PLANS / "plan-document-reviewer-prompt.md"

SHAPING = "### Shaping the DAG for wall-clock time"
EDGE_KINDS = ("`code`", "`same-file`", "`contract`", "`harness`")


def _section(text: str, heading: str, next_heading: str) -> str:
    start = text.index(heading)
    return text[start:text.index(next_heading, start + len(heading))]


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_shaping_section_sits_inside_file_structure() -> None:
    body = SKILL.read_text()
    structure = _section(body, "## File Structure", "## Bite-Sized Task Granularity")
    assert SHAPING in structure


def test_shaping_section_states_the_four_rules_and_the_size_ceiling() -> None:
    shaping = _flat(_section(SKILL.read_text(), SHAPING, "## Bite-Sized Task Granularity"))
    for rule in ("1. **Pin shared shapes in the spec, not in edges.**",
                 "2. **Merge same-file follow-ons.**",
                 "3. **Split long tasks along disjoint file scopes.**",
                 "4. **Put cross-cutting test harnesses in one late task.**"):
        assert rule in shaping
    assert "**size ceiling** is about 2,000 hand-written lines or 20 hand-written" in shaping
    assert "200 hand-written lines a minute" in shaping
    assert "not lockfiles, build output, or other generated files" in shaping


def test_splits_and_merges_keep_sdd_rules() -> None:
    shaping = _flat(_section(SKILL.read_text(), SHAPING, "## Bite-Sized Task Granularity"))
    assert "disjoint `scope.files` for tasks that can run at the same time" in shaping
    assert "acceptance commands for every task" in shaping
    assert "exactly one owner" in shaping and "**seam task**" in shaping
    assert "pinned first" in shaping


def test_trade_offs_stay_explicit() -> None:
    shaping = _flat(_section(SKILL.read_text(), SHAPING, "## Bite-Sized Task Granularity"))
    trade_offs = shaping[shaping.index("**Trade-offs.**"):shaping.index("**Report the shape.**")]
    assert "cheaper implementer model a bigger task" in trade_offs
    assert "bigger diff" in trade_offs
    assert "shared types pinned first" in trade_offs


def test_shape_report_names_depth_critical_path_and_edge_kinds() -> None:
    shaping = _section(SKILL.read_text(), SHAPING, "## Bite-Sized Task Granularity")
    report = _flat(shaping[shaping.index("**Report the shape.**"):])
    assert "`DAG shape` block" in report
    assert "depth" in report and "estimated critical path" in report
    example = re.search(r"```markdown\n(.*?)```", shaping, re.DOTALL)
    assert example, "the shape report needs one worked example"
    lines = example.group(1).splitlines()
    assert lines[0].startswith("**DAG shape:** depth ")
    assert "critical path ≈" in lines[0]
    kinds = "(code|same-file|contract|harness)"
    kept = [line for line in lines[1:] if not line.startswith("- removed:")]
    removed = [line for line in lines[1:] if line.startswith("- removed:")]
    assert kept and removed, "the example shows kept and removed edges"
    for edge in kept:
        assert re.match(rf"- T[\d, T]+ ← T[\d, T]+ · {kinds}: \S", edge), edge
    for edge in removed:
        assert re.match(rf"- removed: .+ ← .+ · {kinds} \(rule [1-4]\): \S", edge), edge
    assert "every edge the rules removed" in report


def test_edge_kinds_extend_the_existing_dependency_rule() -> None:
    """One home for the dependency rule: the kinds extend the Task Independence bullet."""
    independence = _section(SKILL.read_text(), "## Task Independence", "## Plan Document Header")
    bullet = independence[independence.index("- Use `dependencies` for genuine semantic ordering"):]
    bullet = bullet[:bullet.index("\n- `scope.files`")]
    for kind in EDGE_KINDS:
        assert f"  - {kind}:" in bullet
    assert "must say why its rule could not remove it" in _flat(bullet)


def test_self_review_audits_the_shape_inside_item_eight() -> None:
    review = _section(SKILL.read_text(), "## Self-Review", "## After the plan")
    item = _flat(_section(review, "**8.", "If you find issues"))
    assert "Shaping the DAG for wall-clock time" in item
    assert "size ceiling" in item and "`DAG shape` block" in item
    assert "**9." not in review


def test_plan_reviewer_checks_the_shape() -> None:
    row = next(line for line in REVIEWER.read_text().splitlines() if "| DAG Shape |" in line)
    for token in (*EDGE_KINDS, "depth", "critical path", "2,000 hand-written lines or 20 hand-written files",
                  "single owner"):
        assert token in row

