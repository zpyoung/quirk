from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = REPO_ROOT / "commands" / "artifacts"


def test_init_command_invokes_artifact_init() -> None:
    body = (COMMANDS_DIR / "init.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/bin/artifact_init.py" in body
    assert "$ARGUMENTS" in body


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


def test_triage_command_classifies_then_appends() -> None:
    body = (COMMANDS_DIR / "triage.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/bin/artifact_append.py" in body
    # must mention all four destinations
    for kind in ("bug", "defer", "test-skip", "proposal"):
        assert kind in body


def test_adr_command_invokes_adr_create() -> None:
    body = (COMMANDS_DIR / "adr.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/bin/adr_create.py" in body
    assert "$ARGUMENTS" in body


def test_review_artifacts_command_invokes_review_script() -> None:
    body = (COMMANDS_DIR / "review-artifacts.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/bin/artifact_review.py" in body
