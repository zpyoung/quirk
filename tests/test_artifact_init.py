from __future__ import annotations

from pathlib import Path

from .conftest import run_script


def test_init_empty_project_creates_all_artifacts(project_dir: Path) -> None:
    result = run_script("artifact_init.py", cwd=project_dir)
    assert result.returncode == 0, result.stderr
    for name in ["BUGS.md", "DEFERRED.md", "TEST_BACKLOG.md", "proposals.md"]:
        assert (project_dir / name).exists(), f"missing {name}"
    assert (project_dir / "docs" / "adr" / "0000-record-architecture-decisions.md").exists()
    assert "Created" in result.stdout


def test_init_is_idempotent(project_dir: Path) -> None:
    run1 = run_script("artifact_init.py", cwd=project_dir)
    assert run1.returncode == 0
    bugs_before = (project_dir / "BUGS.md").read_text()

    run2 = run_script("artifact_init.py", cwd=project_dir)
    assert run2.returncode == 0
    assert "Skipped" in run2.stdout
    assert (project_dir / "BUGS.md").read_text() == bugs_before


def test_init_force_creates_backup(project_dir: Path) -> None:
    run_script("artifact_init.py", cwd=project_dir)  # initialize first
    bugs = project_dir / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: hand-written\n")
    pre_backups = list(project_dir.glob("BUGS.md.bak.*"))

    result = run_script("artifact_init.py", "--force", cwd=project_dir)
    assert result.returncode == 0, result.stderr

    post_backups = list(project_dir.glob("BUGS.md.bak.*"))
    assert len(post_backups) == len(pre_backups) + 1
    backup = post_backups[-1]
    assert "BUG-1: hand-written" in backup.read_text()
    assert "BUG-1: hand-written" not in bugs.read_text()  # overwritten


def test_init_creates_claude_md_when_missing(project_dir: Path) -> None:
    result = run_script("artifact_init.py", cwd=project_dir)
    assert result.returncode == 0
    assert (project_dir / "CLAUDE.md").exists()
    assert "<!-- quirk-typed-artifacts:trigger -->" in (project_dir / "CLAUDE.md").read_text()


def test_init_appends_snippet_to_existing_claude_md(project_dir: Path) -> None:
    (project_dir / "CLAUDE.md").write_text("# project rules\n- use python3\n")
    result = run_script("artifact_init.py", cwd=project_dir)
    assert result.returncode == 0
    body = (project_dir / "CLAUDE.md").read_text()
    assert "use python3" in body
    assert "<!-- quirk-typed-artifacts:trigger -->" in body


def test_init_skips_snippet_when_marker_present(project_dir: Path) -> None:
    (project_dir / "CLAUDE.md").write_text("# rules\n<!-- quirk-typed-artifacts:trigger -->\nold body\n<!-- /quirk-typed-artifacts:trigger -->\n")
    before = (project_dir / "CLAUDE.md").read_text()
    result = run_script("artifact_init.py", cwd=project_dir)
    assert result.returncode == 0
    assert (project_dir / "CLAUDE.md").read_text() == before
    assert "Skipped" in result.stdout


def test_init_no_claude_md_flag(project_dir: Path) -> None:
    result = run_script("artifact_init.py", "--no-claude-md", cwd=project_dir)
    assert result.returncode == 0
    assert not (project_dir / "CLAUDE.md").exists()
