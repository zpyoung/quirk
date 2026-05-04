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
