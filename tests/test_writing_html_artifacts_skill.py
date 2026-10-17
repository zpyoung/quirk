"""Structural checks for the writing-html-artifacts skill entry point, its links and its trigger evals."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "writing-html-artifacts"
SKILL_PATH = SKILL_DIR / "SKILL.md"
EVALS_PATH = SKILL_DIR / "evals" / "trigger-evals.json"
LAYOUT_EVALS_PATH = SKILL_DIR / "evals" / "layout-evals.json"
FLOW_EVALS_PATH = SKILL_DIR / "evals" / "flow-evals.json"
TRACE_EVALS_PATH = SKILL_DIR / "evals" / "trace-evals.json"

sys.path.insert(0, str(SKILL_DIR / "scripts"))

from htmlkit.layouts import LAYOUTS  # noqa: E402

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SCRIPT_REF = re.compile(r"scripts/([A-Za-z0-9_./-]+\.(?:py|js|mjs))")


def _frontmatter() -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", SKILL_PATH.read_text(), re.DOTALL)
    assert match is not None, "SKILL.md is missing YAML frontmatter"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        assert sep, f"unparseable frontmatter line: {line!r}"
        fields[key.strip()] = value.strip()
    return fields


def _markdown_files() -> list[Path]:
    return [
        SKILL_PATH,
        *sorted((SKILL_DIR / "references").glob("*.md")),
        *sorted((SKILL_DIR / "templates").glob("*/rules.md")),
    ]


def test_frontmatter_has_only_name_and_description() -> None:
    assert set(_frontmatter()) == {"name", "description"}


def test_frontmatter_name_equals_directory() -> None:
    assert _frontmatter()["name"] == SKILL_DIR.name == "writing-html-artifacts"


def test_description_length_and_opening() -> None:
    description = _frontmatter()["description"]
    assert 50 <= len(description) <= 1024
    assert description.startswith("Use when")


def test_description_names_the_triggers_and_the_companion() -> None:
    description = _frontmatter()["description"].lower()
    for phrase in ("html", "web page", "interactive tool", "dashboard", "offline", "companion"):
        assert phrase in description, phrase


@pytest.mark.parametrize("doc", _markdown_files(), ids=lambda p: p.name)
def test_every_relative_link_resolves(doc: Path) -> None:
    for target in LINK.findall(doc.read_text()):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        assert (doc.parent / path).exists(), f"{doc.name}: broken link {target}"


def test_every_script_named_in_skill_exists() -> None:
    named = set(SCRIPT_REF.findall(SKILL_PATH.read_text()))
    assert {"quirk_html.py", "companion.py"} <= named
    for name in named:
        assert (SKILL_DIR / "scripts" / name).is_file(), name


def test_skill_does_not_use_plugin_root_variable() -> None:
    assert "CLAUDE_PLUGIN_ROOT" not in SKILL_PATH.read_text()


def test_skill_links_the_three_references() -> None:
    body = SKILL_PATH.read_text()
    for name in ("design-reference.md", "templates.md", "companion.md"):
        assert f"references/{name}" in body, name


def test_trigger_evals_are_balanced() -> None:
    data = json.loads(EVALS_PATH.read_text())
    assert data["skill_name"] == "writing-html-artifacts"
    queries = data["queries"]
    assert all(set(q) == {"query", "should_trigger"} for q in queries)
    assert all(isinstance(q["query"], str) and q["query"] for q in queries)
    assert sum(q["should_trigger"] is True for q in queries) >= 10
    assert sum(q["should_trigger"] is False for q in queries) >= 10
    assert len({q["query"] for q in queries}) == len(queries)


def _layout_evals() -> list[dict]:
    data = json.loads(LAYOUT_EVALS_PATH.read_text())
    assert data["skill_name"] == "writing-html-artifacts"
    return data["evals"]


def test_layout_evals_have_the_documented_fields() -> None:
    evals = _layout_evals()
    assert all(set(e) == {"id", "prompt", "expected_layout"} for e in evals)
    assert all(isinstance(e["id"], int) and not isinstance(e["id"], bool) for e in evals)
    assert all(isinstance(e["prompt"], str) and e["prompt"].strip() for e in evals)
    assert all(e["expected_layout"] in LAYOUTS for e in evals)


def test_layout_evals_cover_every_shape_at_least_twice() -> None:
    evals = _layout_evals()
    for layout in LAYOUTS:
        assert sum(e["expected_layout"] == layout for e in evals) >= 2, layout
    assert len(evals) >= 2 * len(LAYOUTS)


def test_layout_evals_prompts_and_ids_are_unique() -> None:
    evals = _layout_evals()
    assert len({e["prompt"] for e in evals}) == len(evals)
    assert len({e["id"] for e in evals}) == len(evals)


def test_skill_names_every_shape_in_documented_order() -> None:
    body = SKILL_PATH.read_text()
    positions = [body.find(f"`{layout}`") for layout in LAYOUTS]
    assert all(p >= 0 for p in positions), positions
    assert positions == sorted(positions)


def test_flow_evals_are_balanced_and_unique() -> None:
    data = json.loads(FLOW_EVALS_PATH.read_text())
    assert data["skill_name"] == "writing-html-artifacts"
    evals = data["evals"]
    assert all(set(e) == {"id", "prompt", "expected"} for e in evals)
    assert all(isinstance(e["id"], int) and not isinstance(e["id"], bool) for e in evals)
    assert all(isinstance(e["prompt"], str) and e["prompt"].strip() for e in evals)
    assert all(e["expected"] in ("q-flow", "mermaid", "q-schema", "q-sequence") for e in evals)
    assert sum(e["expected"] == "q-flow" for e in evals) >= 6
    assert sum(e["expected"] == "mermaid" for e in evals) >= 6
    assert sum(e["expected"] == "q-schema" for e in evals) >= 2
    assert sum(e["expected"] == "q-sequence" for e in evals) >= 6
    assert len({e["prompt"] for e in evals}) == len(evals)
    assert len({e["id"] for e in evals}) == len(evals)


def test_trace_evals_are_balanced_and_unique() -> None:
    data = json.loads(TRACE_EVALS_PATH.read_text())
    assert data["skill_name"] == "writing-html-artifacts"
    evals = data["evals"]
    assert all(set(e) == {"id", "prompt", "expected"} for e in evals)
    assert all(isinstance(e["id"], int) and not isinstance(e["id"], bool) for e in evals)
    assert all(isinstance(e["prompt"], str) and e["prompt"].strip() for e in evals)
    assert all(e["expected"] in ("trace", "no-trace") for e in evals)
    assert sum(e["expected"] == "trace" for e in evals) >= 4
    assert sum(e["expected"] == "no-trace" for e in evals) >= 4
    assert len({e["prompt"] for e in evals}) == len(evals)
    assert len({e["id"] for e in evals}) == len(evals)
