from __future__ import annotations

from pathlib import Path

from .conftest import run_script


def test_first_adr_is_0001(project_dir: Path) -> None:
    result = run_script(
        "adr_create.py", "--title", "Switch to opaque tokens",
        cwd=project_dir,
    )
    assert result.returncode == 0, result.stderr
    files = list((project_dir / "docs" / "adr").glob("*.md"))
    assert len(files) == 1
    assert files[0].name == "0001-switch-to-opaque-tokens.md"
    assert "ADR-0001:" in result.stdout
    body = files[0].read_text()
    assert "# 0001. Switch to opaque tokens" in body
    assert "**Status:** proposed" in body


def test_adr_increments_from_existing(project_dir: Path) -> None:
    adr_dir = project_dir / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    for n in (1, 2, 7):
        (adr_dir / f"{n:04d}-old.md").write_text(f"# {n:04d}. old\n")
    result = run_script("adr_create.py", "--title", "Newest one", cwd=project_dir)
    assert result.returncode == 0
    assert (adr_dir / "0008-newest-one.md").exists()
    assert "ADR-0008:" in result.stdout
