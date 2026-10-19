"""No-regression goldens: logic.md output for specs without data-state examples."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "writing-specs" / "interactive" / "render_spec.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "interactive"
GOLDENS = FIXTURES / "goldens"
V1_SPEC = REPO_ROOT / "docs" / "quirk" / "specs" / "2026-09-24-interactive-logic-spec-v2"


def render_copy(logic_json: Path, tmp_path: Path, slug: str) -> bytes:
    """Render a copy of logic_json in a dir named slug (the basename is the spec slug)."""
    spec_dir = tmp_path / slug
    spec_dir.mkdir(parents=True)
    shutil.copy(logic_json, spec_dir / "logic.json")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "render", str(spec_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return (spec_dir / "logic.md").read_bytes()


@pytest.mark.parametrize("stage", ["stage1", "stage2"])
def test_v2_fixture_logic_md_matches_golden(tmp_path: Path, stage: str) -> None:
    rendered = render_copy(FIXTURES / "v2" / stage / "logic.json", tmp_path, stage)
    assert rendered == (GOLDENS / f"v2-{stage}.logic.md").read_bytes()


def test_v1_spec_renders_committed_logic_md(tmp_path: Path) -> None:
    rendered = render_copy(V1_SPEC / "logic.json", tmp_path, V1_SPEC.name)
    assert rendered == (V1_SPEC / "logic.md").read_bytes()
