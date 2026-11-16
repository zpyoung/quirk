"""Structure checks for the explaining-code skill: frontmatter, links, evals and sub-skill wiring."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
SKILL_DIR = SKILLS_DIR / "explaining-code"
SKILL_PATH = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
EVALS_PATH = SKILL_DIR / "evals" / "trigger-evals.json"

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6} (.+)$", re.MULTILINE)
SUB_SKILL = re.compile(r"\*\*REQUIRED SUB-SKILL:\*\* Use quirk:([a-z0-9-]+)")
# the skill was ported from a company-internal one; none of its vocabulary may leak into a public repo
FORBIDDEN = ("recharge", "rechargeapps", "merchant", "kokoro", "PRO-", "!17170", "~/Studio/explainers")


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
    return [SKILL_PATH, *sorted(REFERENCES_DIR.glob("*.md"))]


def _anchor(heading: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", heading.strip().lower())
    return re.sub(r"\s", "-", slug)


def test_frontmatter_has_only_name_and_description() -> None:
    assert set(_frontmatter()) == {"name", "description"}


def test_frontmatter_name_equals_directory() -> None:
    assert _frontmatter()["name"] == SKILL_DIR.name == "explaining-code"


def test_description_length_and_shape() -> None:
    description = _frontmatter()["description"]
    assert 50 <= len(description) <= 1024
    assert description.startswith("Use when")


def test_description_names_targets_and_neighbours() -> None:
    description = _frontmatter()["description"].lower()
    for term in ("pr", "mr", "branch", "commit range", "local", "design", "video", "page"):
        assert term in description, term
    for neighbour in ("full-code-review", "making-videos", "writing-html-artifacts"):
        assert neighbour in description, neighbour


@pytest.mark.parametrize("doc", _markdown_files(), ids=lambda p: p.name)
def test_relative_links_and_anchors_resolve(doc: Path) -> None:
    for target in LINK.findall(doc.read_text()):
        if target.startswith(("http://", "https://")):
            continue
        path_part, _, anchor = target.partition("#")
        dest = (doc.parent / path_part).resolve() if path_part else doc
        assert dest.is_file(), f"{doc.name} links to missing {target}"
        if anchor:
            anchors = {_anchor(h) for h in HEADING.findall(dest.read_text())}
            assert anchor in anchors, f"{doc.name} links to missing anchor {target}"


@pytest.mark.parametrize("doc", _markdown_files(), ids=lambda p: p.name)
def test_no_internal_vocabulary(doc: Path) -> None:
    text = doc.read_text().lower()
    for needle in FORBIDDEN:
        assert needle.lower() not in text, f"{doc.name} mentions {needle!r}"


def test_sub_skills_exist() -> None:
    names = set(SUB_SKILL.findall(SKILL_PATH.read_text()))
    assert names == {"writing-html-artifacts", "making-videos"}
    for name in names:
        assert (SKILLS_DIR / name / "SKILL.md").is_file(), name


def test_no_links_into_other_skills_internals() -> None:
    for doc in _markdown_files():
        for target in LINK.findall(doc.read_text()):
            assert not target.startswith("../../"), f"{doc.name} links into another skill: {target}"


def test_references_have_contents_lists() -> None:
    for ref in sorted(REFERENCES_DIR.glob("*.md")):
        assert "## Contents" in ref.read_text().splitlines()[:15], ref.name


def test_trigger_evals_shape_and_counts() -> None:
    data = json.loads(EVALS_PATH.read_text())
    assert data["skill_name"] == "explaining-code"
    queries = data["queries"]
    assert all(set(q) == {"query", "should_trigger"} for q in queries)
    assert all(isinstance(q["should_trigger"], bool) for q in queries)
    assert sum(q["should_trigger"] for q in queries) >= 10
    assert sum(not q["should_trigger"] for q in queries) >= 10
    assert len({q["query"] for q in queries}) == len(queries)


def test_trigger_evals_cover_the_neighbour_boundaries() -> None:
    queries = {q["query"]: q["should_trigger"] for q in json.loads(EVALS_PATH.read_text())["queries"]}
    assert queries["Review this PR for bugs"] is False
    assert queries["Make a 30 second video announcing our new CLI release"] is False
    assert queries["Make an HTML report of these test results"] is False
    assert queries["Explain how the auth module in this repo works"] is False
    assert queries["Make a walkthrough video of this pull request for reviewers"] is True
    assert queries["Explain this design doc to the team: docs/specs/2026-11-01-billing-retries/tech.md"] is True
