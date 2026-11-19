"""Structure checks for the interface-design skill: spine, links, evals, checklist and detector parity."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "interface-design"
SKILL_PATH = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
CHECKLIST_PATH = REFERENCES_DIR / "checklist.md"
EVALS_PATH = SKILL_DIR / "evals" / "trigger-evals.json"
NOTICE_PATH = SKILL_DIR / "NOTICE.md"
LICENSES_DIR = SKILL_DIR / "licenses"

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
RULE_BULLET = re.compile(r"^- `([a-z0-9]+(?:-[a-z0-9]+)+)` (P[0-3]) — .+$")
CONTENTS_WINDOW = 25
FORBIDDEN = ("impeccable context", "impeccable detect", "PRODUCT.md", "DESIGN.md", ".interface-design/")

MOVES = (
    "adapt audit animate bolder clarify colorize critique delight distill "
    "extract harden layout onboard optimize overdrive polish quieter typeset"
).split()
SURFACES = ("read", "ios", "android")
LICENSE_FILES = (
    "interface-design-MIT.txt",
    "web-interface-guidelines-MIT.txt",
    "impeccable-Apache-2.0.txt",
)


def _frontmatter() -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", SKILL_PATH.read_text(), re.DOTALL)
    assert match is not None, "SKILL.md is missing YAML frontmatter"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        assert sep, f"unparseable frontmatter line: {line!r}"
        fields[key.strip()] = value.strip()
    return fields


def _body() -> str:
    return re.sub(r"^---\n.*?\n---\n", "", SKILL_PATH.read_text(), count=1, flags=re.DOTALL)


def _reference_files() -> list[Path]:
    return sorted(REFERENCES_DIR.rglob("*.md"))


def _markdown_files() -> list[Path]:
    return [SKILL_PATH, *_reference_files()]


def _load_detector() -> ModuleType:
    path = SKILL_DIR / "scripts" / "detect.py"
    spec = importlib.util.spec_from_file_location("_interface_design_detect_skill", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _checklist_rules() -> list[tuple[str, str, bool]]:
    rules: list[tuple[str, str, bool]] = []
    for line in CHECKLIST_PATH.read_text().splitlines():
        if not line.startswith("- `"):
            continue
        match = RULE_BULLET.match(line)
        assert match is not None, f"checklist bullet does not match the rule format: {line[:80]!r}"
        rules.append((match.group(1), match.group(2), line.endswith(" (detector)")))
    return rules


def test_frontmatter_has_only_name_and_description() -> None:
    assert set(_frontmatter()) == {"name", "description"}


def test_frontmatter_name_equals_directory() -> None:
    assert _frontmatter()["name"] == SKILL_DIR.name == "interface-design"


def test_description_length() -> None:
    description = _frontmatter()["description"]
    assert 50 <= len(description) <= 1024
    assert description.startswith("Use when")


def test_description_names_the_triggers_and_exclusions() -> None:
    description = _frontmatter()["description"].lower()
    terms = (
        "product ui",
        "dashboard",
        "admin",
        "tools",
        "settings",
        "data view",
        "docs",
        "ios",
        "android",
        "build",
        "review",
        "audit",
        "critique",
        "polish",
        "refine",
        "ui slop",
        "marketing",
        "landing",
        "html pages",
        "mini app",
    )
    for term in terms:
        assert term in description, term


def test_skill_body_is_at_most_300_lines() -> None:
    assert len(_body().splitlines()) <= 300


def test_skill_body_has_the_required_content() -> None:
    body = _body()
    lowered = body.lower()
    for needle in (
        ".quirk/design/system.md",
        "who is this person",
        "what must they do",
        "what should it feel like",
        "build",
        "review",
        "refine",
        "150",
        "250ms",
        "check-intent",
        "justify or change",
        "one accent",
        "SKILL_DIR",
        "scripts/detect.py",
        "invisible",
    ):
        assert needle.lower() in lowered, needle


def test_skill_names_the_upstream_memory_dir_once_as_never_read() -> None:
    lines = [line for line in _body().splitlines() if ".interface-design/" in line]
    assert len(lines) == 1
    assert "never" in lines[0].lower()


@pytest.mark.parametrize("doc", _markdown_files(), ids=lambda p: str(p.relative_to(SKILL_DIR)))
def test_every_relative_link_resolves(doc: Path) -> None:
    for target in LINK.findall(doc.read_text()):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        assert (doc.parent / path).exists(), f"{doc.name}: broken link {target}"


def test_reference_set_is_complete() -> None:
    found = {p.relative_to(REFERENCES_DIR).as_posix() for p in _reference_files()}
    expected = {"build.md", "system-md.md", "review.md", "checklist.md"}
    expected |= {f"moves/{m}.md" for m in MOVES}
    expected |= {f"surfaces/{s}.md" for s in SURFACES}
    assert found == expected


def test_skill_links_every_reference_in_the_table() -> None:
    lines = SKILL_PATH.read_text().splitlines()
    for ref in _reference_files():
        rel = f"references/{ref.relative_to(REFERENCES_DIR).as_posix()}"
        rows = [line for line in lines if line.startswith("|") and f"]({rel})" in line]
        assert rows, f"{rel} has no situation table row linking it"
        cells = [c.strip() for c in rows[0].strip().strip("|").split("|")]
        assert len(cells) >= 2 and all(cells), f"{rel} row needs a situation and a link"


@pytest.mark.parametrize("ref", _reference_files(), ids=lambda p: str(p.relative_to(REFERENCES_DIR)))
def test_long_references_open_with_a_contents_list(ref: Path) -> None:
    lines = ref.read_text().splitlines()
    if len(lines) <= 100:
        return
    assert "## Contents" in lines[:CONTENTS_WINDOW], f"{ref.name} needs a contents list in its first {CONTENTS_WINDOW} lines"


@pytest.mark.parametrize("doc", _markdown_files(), ids=lambda p: str(p.relative_to(SKILL_DIR)))
def test_no_removed_upstream_machinery_is_mentioned(doc: Path) -> None:
    text = doc.read_text()
    for needle in FORBIDDEN:
        if doc == SKILL_PATH and needle == ".interface-design/":
            continue
        assert needle not in text, f"{doc.name} mentions {needle!r}"


def test_trigger_evals_shape_and_counts() -> None:
    data = json.loads(EVALS_PATH.read_text())
    assert data["skill_name"] == "interface-design"
    queries = data["queries"]
    assert all(set(q) == {"query", "should_trigger"} for q in queries)
    assert all(isinstance(q["query"], str) and q["query"] for q in queries)
    assert all(isinstance(q["should_trigger"], bool) for q in queries)
    assert sum(q["should_trigger"] is True for q in queries) >= 10
    assert sum(q["should_trigger"] is False for q in queries) >= 10
    assert len({q["query"] for q in queries}) == len(queries)


def test_trigger_evals_cover_the_boundary_cases() -> None:
    queries = {q["query"]: q["should_trigger"] for q in json.loads(EVALS_PATH.read_text())["queries"]}
    assert queries["Build a settings page for our admin app"] is True
    assert queries["Improve our docs page layout"] is True
    assert queries["Make an HTML report of these results"] is False
    assert queries["Scaffold a mini app for tracking reading"] is False
    assert queries["Design our product's landing page"] is False


def test_checklist_bullets_match_the_rule_format_and_ids_are_unique() -> None:
    rules = _checklist_rules()
    assert rules
    ids = [rule_id for rule_id, _, _ in rules]
    assert len(ids) == len(set(ids)), sorted({i for i in ids if ids.count(i) > 1})


def test_checklist_pins_the_scenario_rules() -> None:
    severities = {rule_id: severity for rule_id, severity, _ in _checklist_rules()}
    assert severities["intent-eyebrow-label"] == "P3"
    assert severities["intent-hero-metric"] == "P3"
    assert severities["drift-system-value"] == "P1"
    assert all(sev == "P3" for rule_id, sev in severities.items() if rule_id.startswith("intent-"))


def test_detector_ids_match_checklist_detector_bullets() -> None:
    detector_ids = {rule.id for rule in _load_detector().RULES}
    checklist_ids = {rule_id for rule_id, _, is_detector in _checklist_rules() if is_detector}
    assert checklist_ids == detector_ids


def test_notice_lists_every_source() -> None:
    rows = [
        [c.strip() for c in line.strip().strip("|").split("|")]
        for line in NOTICE_PATH.read_text().splitlines()
        if line.startswith("|")
    ]
    assert rows[0] == ["source", "repo", "path", "license", "pinned"]
    sources = {row[0]: row for row in rows[2:]}
    assert set(sources) == {
        "interface-design",
        "web-interface-guidelines",
        "web-design-guidelines-skill",
        "impeccable",
    }
    for row in sources.values():
        assert re.fullmatch(r"[0-9a-f]{40}", row[4]), row


@pytest.mark.parametrize("name", LICENSE_FILES)
def test_license_files_exist(name: str) -> None:
    assert (LICENSES_DIR / name).is_file()
    assert (LICENSES_DIR / name).read_text().strip()
