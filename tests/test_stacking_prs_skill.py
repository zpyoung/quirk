"""Structural checks for the stacking-prs skill router, its phase references and its trigger evals."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "stacking-prs"
SKILL_PATH = SKILL_DIR / "SKILL.md"
EVALS_PATH = SKILL_DIR / "evals" / "trigger-evals.json"
ANALYZE_TEST = REPO_ROOT / "tests" / "test_stacking_prs_analyze.py"
LAND_PATH = SKILL_DIR / "references" / "land.md"
MANAGE_PATH = SKILL_DIR / "references" / "manage.md"
SPLIT_PATH = SKILL_DIR / "references" / "split.md"

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
PLUGIN_PATH = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/(skills/[A-Za-z0-9_./-]+)")
MERGE_COMMANDS = ("gh pr merge", "gh stack merge", "glab mr merge")
OLD_NAME = "split" + "-branch"


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
    return [SKILL_PATH, *sorted((SKILL_DIR / "references").glob("*.md"))]


def _skill_files() -> list[Path]:
    return sorted(p for p in SKILL_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def test_frontmatter_has_only_name_and_description() -> None:
    assert set(_frontmatter()) == {"name", "description"}


def test_frontmatter_name_equals_directory() -> None:
    assert _frontmatter()["name"] == SKILL_DIR.name == "stacking-prs"


def test_description_length_and_opening() -> None:
    description = _frontmatter()["description"]
    assert 50 <= len(description) <= 1024
    assert description.startswith("Use when")


def test_description_covers_split_manage_and_land() -> None:
    description = _frontmatter()["description"].lower()
    for phrase in ("split", "stack", "land"):
        assert phrase in description, phrase


@pytest.mark.parametrize("doc", _markdown_files(), ids=lambda p: p.name)
def test_every_relative_link_resolves(doc: Path) -> None:
    for target in LINK.findall(doc.read_text()):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        assert (doc.parent / path).exists(), f"{doc.name}: broken link {target}"


def test_skill_links_the_three_references() -> None:
    body = SKILL_PATH.read_text()
    for name in ("split.md", "manage.md", "land.md"):
        assert f"](references/{name})" in body, name


def test_skill_body_stays_under_150_lines() -> None:
    text = SKILL_PATH.read_text()
    body = text.split("\n---\n", 1)[1]
    assert len(body.splitlines()) < 150


def test_script_paths_exist() -> None:
    found = 0
    for doc in _markdown_files():
        for rel in PLUGIN_PATH.findall(doc.read_text()):
            found += 1
            assert (REPO_ROOT / rel.rstrip(".,;:)")).exists(), f"{doc.name}: missing {rel}"
    assert found, "no ${CLAUDE_PLUGIN_ROOT} script paths found in the skill docs"


def test_docs_name_the_stack_and_restack_scripts() -> None:
    text = "\n".join(doc.read_text() for doc in _markdown_files())
    for name in ("stack.sh", "restack.sh", "analyze.sh", "extract.sh"):
        assert f"${{CLAUDE_PLUGIN_ROOT}}/skills/stacking-prs/scripts/{name}" in text, name


def test_no_skill_file_or_analyze_test_uses_the_old_name() -> None:
    for path in [*_skill_files(), ANALYZE_TEST]:
        assert OLD_NAME not in path.read_text(), path.relative_to(REPO_ROOT)


def test_evidence_strings_are_corrected() -> None:
    text = "\n".join(doc.read_text() for doc in _markdown_files())
    for stale in ("LinearB 2025", "<219", "70-90%"):
        assert stale not in text, stale
    for current in ("Kudrjavets", "LinearB 2026"):
        assert current in text, current


def test_merge_commands_appear_only_on_never_lines() -> None:
    for doc in _markdown_files():
        for number, line in enumerate(doc.read_text().splitlines(), start=1):
            if any(cmd in line for cmd in MERGE_COMMANDS):
                assert "never" in line.lower(), f"{doc.name}:{number} runs a merge command: {line}"


def test_land_states_the_never_merge_rule() -> None:
    lines = [
        line
        for line in LAND_PATH.read_text().splitlines()
        if "never" in line.lower() and any(cmd in line for cmd in MERGE_COMMANDS)
    ]
    assert lines


def test_manage_rebases_never_move_a_backup_branch() -> None:
    text = MANAGE_PATH.read_text()
    assert "GIT_SEQUENCE_EDITOR=:" not in text
    assert "(update-ref|u) refs\\/heads\\/backup\\/" in text
    rebases = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("git rebase") and "--update-refs" in line
    ]
    assert len(rebases) >= 2
    assert all(line.startswith("git rebase -i ") for line in rebases), rebases


def test_manage_backup_filter_deletes_long_and_abbreviated_update_refs() -> None:
    text = MANAGE_PATH.read_text()
    exprs = set(re.findall(r"sed -i\.bak (-E -e '[^']+')", text))
    assert len(exprs) == 1, exprs
    expr = re.fullmatch(r"-E -e '([^']+)'", exprs.pop()).group(1)
    todo = (
        "pick abc123 first\n"
        "update-ref refs/heads/backup/auth-api_20261020_141500\n"
        "u refs/heads/backup/auth-api_20261020_141500\n"
        "update-ref refs/heads/auth-api\n"
        "u refs/heads/auth-ui\n"
    )
    out = subprocess.run(
        ["sed", "-E", "-e", expr], input=todo, text=True, capture_output=True, check=True
    ).stdout
    assert out == (
        "pick abc123 first\nupdate-ref refs/heads/auth-api\nu refs/heads/auth-ui\n"
    )


def test_split_step_4_rebase_ignores_rebase_update_refs() -> None:
    rebases = [
        line
        for line in SPLIT_PATH.read_text().splitlines()
        if line.startswith("git rebase --onto") or line.startswith("git rebase --no-update-refs --onto")
    ]
    assert len(rebases) == 1, rebases
    assert "--no-update-refs" in rebases[0]


def test_every_force_push_in_split_uses_force_if_includes() -> None:
    pushes = [
        line
        for line in SPLIT_PATH.read_text().splitlines()
        if "git push" in line and "--force-with-lease" in line
    ]
    assert pushes
    assert all("--force-if-includes" in line for line in pushes), pushes


def test_split_this_layer_section_restacks_the_layers_above() -> None:
    text = SPLIT_PATH.read_text()
    start = text.index("### Split this layer further")
    section = text[start : text.index("\n### ", start + 1)]
    assert "scripts/restack.sh" in section
    assert "--old-tip" in section


def test_trigger_evals_are_balanced() -> None:
    data = json.loads(EVALS_PATH.read_text())
    assert data["skill_name"] == "stacking-prs"
    queries = data["queries"]
    assert all(set(q) == {"query", "should_trigger"} for q in queries)
    assert all(isinstance(q["query"], str) and q["query"] for q in queries)
    assert sum(q["should_trigger"] is True for q in queries) >= 12
    assert sum(q["should_trigger"] is False for q in queries) >= 12
    assert len({q["query"] for q in queries}) == len(queries)
