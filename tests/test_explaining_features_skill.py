"""Structural checks for the explaining-features skill: entry point, references, links, evals, honesty strings."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "explaining-features"
SKILL_PATH = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
EVALS_PATH = SKILL_DIR / "evals" / "trigger-evals.json"
MAKING_VIDEOS_EVALS = REPO_ROOT / "skills" / "making-videos" / "evals" / "trigger-evals.json"
README_PATH = REPO_ROOT / "README.md"

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SCRIPT_REF = re.compile(r"scripts/([A-Za-z0-9_./-]+\.py)")
SIBLING_PATH = re.compile(r"skills/(making-videos|writing-html-artifacts|using-apps-like-a-user)\b")

PRESSURE_HEADINGS = ("## Scenario", "## Your Options", "## Choose A, B, or C", "## Correct choice")

# Phrases from the logic spec's Then clauses and Decisions Locked, so a rewrite can't quietly drop one.
REQUIRED_STRINGS: dict[str, tuple[str, ...]] = {
    "SKILL.md": (
        "SKILL_DIR",
        "quirk:making-videos",
        "quirk:writing-html-artifacts",
        "quirk:using-apps-like-a-user",
        "--unattended",
        "stops: none",
        "--scale 2",
        "macOS only",
        "only when asked",
        "doesn't wait",
        "no film, because nothing moves",
        "before the user walks away",
        "clip per behavior",
        "main behavior",
        "mock up",
        "no footage was captured",
        "seeded data",
        "frame check",
        "verify_outcome.py",
        "fit_video.py",
        "ship_disclosed",
        "outside_calls",
        "not proven",
        "disappears with the worktree",
        "versions are never overwritten",
        "run the skill again",
        "storyboard",
        "~/Studio/explainers/",
        ".quirk/html",
        "Never",
        "self-ignoring",
        "reencoded: true",
        "This skill's own scripts",
    ),
    "references/evidence.md": (
        "Behavior | Claim | Result | How checked | Proof",
        "Pass",
        "Partly",
        "Unit test only",
        "Not proven",
        "Failed",
        "pass_without_effect",
        "one file at a time",
        "sources.md",
        "diagram",
        "using-apps-like-a-user",
    ),
    "references/capture.md": (
        "private instance",
        "seeded",
        "persisted",
        "parent commit",
        "git archive",
        "fps=1/3",
        "home directory",
        "username",
        "alt text",
        "captions",
        "beats.json",
        "copy",
        "fitted",
        "reencoded: true",
        "fresh home",
        "fixture's repo path",
    ),
    "references/page.md": (
        "Staged for the camera",
        "seeded data",
        "drawn pointer",
        "added labels",
        "sped up",
        "parent commit",
        "at this commit",
        "customer",
        "How it's built",
        "What's still open",
        "10 MiB",
        "base64",
        "data-inline",
        "names the code or spec",
        "ledger",
    ),
}


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


def _markdown_files() -> list[Path]:
    return [SKILL_PATH, *sorted(REFERENCES_DIR.glob("*.md"))]


def _skill_files() -> list[Path]:
    return sorted(p for p in SKILL_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def test_frontmatter_has_only_name_and_description() -> None:
    assert set(_frontmatter()) == {"name", "description"}


def test_frontmatter_name_equals_directory() -> None:
    assert _frontmatter()["name"] == SKILL_DIR.name == "explaining-features"


def test_description_length_and_opening() -> None:
    description = _frontmatter()["description"]
    assert 50 <= len(description) <= 1024
    assert description.startswith("Use when")


def test_description_covers_the_trigger_phrases_and_routes_video_only_requests() -> None:
    description = _frontmatter()["description"].lower()
    for phrase in ("walkthrough", "explain this feature", "feature explainer", "show what this pr does"):
        assert phrase in description, phrase
    assert "making-videos" in description


def test_skill_body_is_under_300_lines() -> None:
    assert len(_body().splitlines()) < 300


@pytest.mark.parametrize("doc", _markdown_files(), ids=lambda p: p.name)
def test_every_relative_link_resolves(doc: Path) -> None:
    for target in LINK.findall(doc.read_text()):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        assert (doc.parent / path).exists(), f"{doc.name}: broken link {target}"


def test_every_script_named_in_the_skill_exists() -> None:
    named: set[str] = set()
    for doc in _markdown_files():
        named.update(SCRIPT_REF.findall(doc.read_text()))
    assert {"verify_outcome.py", "fit_video.py", "leftovers.py"} <= named
    for name in named:
        assert (SKILL_DIR / "scripts" / name).is_file(), name


def test_skill_does_not_use_plugin_root_variable() -> None:
    for path in _skill_files():
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        assert "CLAUDE_PLUGIN_ROOT" not in text, path.relative_to(SKILL_DIR)


@pytest.mark.parametrize("doc", _markdown_files(), ids=lambda p: p.name)
def test_sibling_skills_are_named_not_pathed(doc: Path) -> None:
    assert not SIBLING_PATH.search(doc.read_text()), f"{doc.name} builds a sibling skill's path"


@pytest.mark.parametrize("doc", _markdown_files(), ids=lambda p: p.name)
def test_docs_have_no_em_dashes(doc: Path) -> None:
    assert "—" not in doc.read_text()


def test_stopping_processes_is_a_hard_rule_in_skill_and_capture() -> None:
    skill = SKILL_PATH.read_text()
    assert "Stop only what you started" in skill
    for text in (skill, (REFERENCES_DIR / "capture.md").read_text()):
        for needle in ("PID", "pkill", "killall", "by name or pattern"):
            assert needle in text, needle
    capture = (REFERENCES_DIR / "capture.md").read_text()
    section = capture.split("## Stopping what you started", 1)[1].split("\n## ", 1)[0]
    for needle in ("working directory", "HOME", "$E", "outlive"):
        assert needle in section, needle


def test_capture_requires_checking_that_a_yours_entry_is_a_command_you_started() -> None:
    capture = (REFERENCES_DIR / "capture.md").read_text()
    section = capture.split("## Stopping what you started", 1)[1].split("\n## ", 1)[0]
    assert "only if its command is one you started" in section
    assert "out of text" in section


def test_capture_finds_survivors_with_leftovers_not_a_lsof_sweep() -> None:
    capture = (REFERENCES_DIR / "capture.md").read_text()
    section = capture.split("## Stopping what you started", 1)[1].split("\n## ", 1)[0]
    assert "leftovers.py" in section
    assert "lsof -w +D" not in capture
    assert "+D" not in capture
    assert "Anything listed is yours" not in capture
    assert re.search(r"[Nn]ever stop anything in `check_by_hand`", section)
    assert "$E/harness/" in capture and "HOME" in capture
    assert "temp folder or `$E`" not in capture
    assert "leftovers.py" in SKILL_PATH.read_text()


def test_skill_points_at_every_reference() -> None:
    body = SKILL_PATH.read_text()
    for ref in sorted(REFERENCES_DIR.glob("*.md")):
        assert f"references/{ref.name}" in body, ref.name
    assert {p.name for p in REFERENCES_DIR.glob("*.md")} == {"evidence.md", "capture.md", "page.md"}


def test_skill_points_at_every_pressure_scenario() -> None:
    body = SKILL_PATH.read_text()
    for n in (1, 2, 3, 4):
        assert f"test-pressure-{n}.md" in body


@pytest.mark.parametrize("rel", sorted(REQUIRED_STRINGS))
def test_required_strings_are_present(rel: str) -> None:
    text = (SKILL_DIR / rel).read_text().lower()
    for needle in REQUIRED_STRINGS[rel]:
        assert needle.lower() in text, f"{rel} is missing {needle!r}"


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_pressure_scenario_follows_the_house_layout(n: int) -> None:
    text = (SKILL_DIR / f"test-pressure-{n}.md").read_text()
    assert text.startswith(f"# Pressure Test {n}:")
    assert "**IMPORTANT: This is a real scenario." in text
    assert f"skills/explaining-features" in text
    positions = [text.find(h) for h in PRESSURE_HEADINGS]
    assert all(p >= 0 for p in positions), PRESSURE_HEADINGS
    assert positions == sorted(positions)
    for option in ("**A)", "**B)", "**C)"):
        assert option in text
    assert re.search(r"## Correct choice\n\n\*\*[ABC]\.\*\*", text)


def test_pressure_scenario_4_covers_the_sourced_reasoning_rule_and_the_blocked_stop() -> None:
    text = (SKILL_DIR / "test-pressure-4.md").read_text().lower()
    for needle in ("blocked", "login", "stop 2", "from reading the code", "design reason", "names the code or spec"):
        assert needle in text, needle
    assert re.search(r"## correct choice\n\n\*\*c\.\*\*", text)


def test_trigger_evals_are_balanced() -> None:
    data = json.loads(EVALS_PATH.read_text())
    assert data["skill_name"] == "explaining-features"
    queries = data["queries"]
    assert all(set(q) == {"query", "should_trigger"} for q in queries)
    assert all(isinstance(q["query"], str) and q["query"] for q in queries)
    assert sum(q["should_trigger"] is True for q in queries) >= 12
    assert sum(q["should_trigger"] is False for q in queries) >= 12
    assert len({q["query"] for q in queries}) == len(queries)


def test_trigger_evals_cover_the_routing_table() -> None:
    queries = {q["query"]: q["should_trigger"] for q in json.loads(EVALS_PATH.read_text())["queries"]}
    assert queries["Make a walkthrough of this feature"] is True
    assert queries["Explain what this PR does, with screenshots"] is True
    assert queries["Make a 30 second video announcing our release"] is False
    assert queries["Build a dashboard page for these numbers"] is False
    assert queries["Try this flow in the app"] is False


def test_making_videos_evals_carry_near_misses_for_this_skill() -> None:
    queries = {q["query"]: q["should_trigger"] for q in json.loads(MAKING_VIDEOS_EVALS.read_text())["queries"]}
    for query in ("Make a walkthrough of this feature", "Explain what this PR does, with screenshots"):
        assert queries[query] is False
    own = {q["query"] for q in json.loads(EVALS_PATH.read_text())["queries"] if q["should_trigger"]}
    assert len(own & {q for q, t in queries.items() if t is False}) >= 3


def test_readme_counts_and_names_the_skill() -> None:
    readme = README_PATH.read_text()
    assert "**31 skills**" in readme
    assert "explaining-features" in readme
