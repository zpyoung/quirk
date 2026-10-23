"""Structural checks for the making-videos skill entry point, its references, links and trigger evals."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "making-videos"
SKILL_PATH = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
EVALS_PATH = SKILL_DIR / "evals" / "trigger-evals.json"

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SCRIPT_REF = re.compile(r"scripts/([A-Za-z0-9_./-]+\.py)")

REQUIRED_STRINGS: dict[str, tuple[str, ...]] = {
    "SKILL.md": ("hf.py", "cloud.py", "3 minutes", "avatar", "macOS", "3 failed", "stop", "SKILL_DIR"),
    "references/storyboard.md": ("about 20 s", "9:16", "Blender", "silent", "scene kit"),
    "references/motion.md": ("immediateRender: false", "fromTo", "repeat: -1", "gsap.set", "4.5:1"),
    "references/long-form.md": ("scene kit", "assembled MP4"),
    "references/hyperframes.md": (
        "hf.py",
        "--describe false",
        "HYPERFRAMES_NO_TELEMETRY",
        ":root",
        "Injected deterministic",
    ),
    "references/3d.md": ("blender_render.py", "--python-exit-code", "parse_known_args", "Standard", "2D"),
    "references/review.md": ("verify.py", "review_page.py", "3 failed", "v2", "contact sheet", "review-notes.md"),
    "references/audio.md": ("voice.py", "LUFS", "dBTP", "20 dB", ".srt", "--burn", "cps_violations"),
    "references/cloud.md": ("cloud.py", "cloud_allow", "never permission", "calls.jsonl"),
    "references/gather.md": ("capture", "record.py", "native macOS"),
    "references/brand.md": ("brand save", "--confirm", "pronunciations", ":root"),
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
    assert _frontmatter()["name"] == SKILL_DIR.name == "making-videos"


def test_description_length_and_opening() -> None:
    description = _frontmatter()["description"]
    assert 50 <= len(description) <= 1024
    assert description.startswith("Use when")


def test_description_names_the_triggers_and_exclusions() -> None:
    description = _frontmatter()["description"].lower()
    for phrase in ("video", "explainer", "motion graphics", "narration", "voiceover", "render", "avatar", "upload"):
        assert phrase in description, phrase


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
    assert {"hf.py", "cloud.py", "doctor.py", "verify.py", "review_page.py"} <= named
    for name in named:
        assert (SKILL_DIR / "scripts" / name).is_file(), name


def test_skill_does_not_use_plugin_root_variable() -> None:
    for path in _skill_files():
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        assert "CLAUDE_PLUGIN_ROOT" not in text, path.relative_to(SKILL_DIR)


def test_skill_points_at_every_reference() -> None:
    body = SKILL_PATH.read_text()
    for ref in sorted(REFERENCES_DIR.glob("*.md")):
        assert f"references/{ref.name}" in body, ref.name


@pytest.mark.parametrize("rel", sorted(REQUIRED_STRINGS))
def test_required_strings_are_present(rel: str) -> None:
    text = (SKILL_DIR / rel).read_text().lower()
    for needle in REQUIRED_STRINGS[rel]:
        assert needle.lower() in text, f"{rel} is missing {needle!r}"


def test_trigger_evals_are_balanced() -> None:
    data = json.loads(EVALS_PATH.read_text())
    assert data["skill_name"] == "making-videos"
    queries = data["queries"]
    assert all(set(q) == {"query", "should_trigger"} for q in queries)
    assert all(isinstance(q["query"], str) and q["query"] for q in queries)
    assert sum(q["should_trigger"] is True for q in queries) >= 12
    assert sum(q["should_trigger"] is False for q in queries) >= 12
    assert len({q["query"] for q in queries}) == len(queries)
