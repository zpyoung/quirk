from __future__ import annotations

from pathlib import Path

from .conftest import run_script


def test_full_workflow(project_dir: Path) -> None:
    # Init
    r = run_script("artifact_init.py", "--no-claude-md", cwd=project_dir)
    assert r.returncode == 0, r.stderr
    for name in ["BUGS.md", "DEFERRED.md", "TEST_BACKLOG.md", "proposals.md"]:
        assert (project_dir / name).exists()
    assert (project_dir / "docs" / "adr" / "0000-record-architecture-decisions.md").exists()

    # Bug
    r = run_script(
        "artifact_append.py", "bug",
        "--field", "title=safari rejects cookie",
        "--field", "file=login.ts:42",
        "--field", "description=cookie has SameSite=None without Secure",
        "--field", "severity=high",
        cwd=project_dir,
    )
    assert r.returncode == 0
    assert "BUG-1: safari rejects cookie" in (project_dir / "BUGS.md").read_text()

    # Defer
    r = run_script(
        "artifact_append.py", "defer",
        "--field", "title=multi-tenant rate limits",
        "--field", "why_deferred=out of scope",
        "--field", "priority=P3",
        cwd=project_dir,
    )
    assert r.returncode == 0

    # Test skip
    r = run_script(
        "artifact_append.py", "test-skip",
        "--field", "title=oauth state CSRF",
        "--field", "file_under_test=auth/oauth.ts",
        "--field", "reason_skipped=mocking required",
        cwd=project_dir,
    )
    assert r.returncode == 0

    # ADR
    r = run_script(
        "adr_create.py", "--title", "Switch session storage from JWT to opaque tokens",
        cwd=project_dir,
    )
    assert r.returncode == 0
    assert (project_dir / "docs" / "adr" / "0001-switch-session-storage-from-jwt-to-opaque-tokens.md").exists()

    # Review
    r = run_script("artifact_review.py", cwd=project_dir)
    assert r.returncode == 0
    out = r.stdout
    assert "BUGS.md: 1 entries" in out
    assert "BUG-1 [high] safari rejects cookie" in out
    assert "DEFERRED.md: 1 entries" in out
    assert "DEFER-1 [P3] multi-tenant rate limits" in out
    assert "TEST_BACKLOG.md: 1 entries" in out
    assert "TEST-1 [-] oauth state CSRF" in out
    assert "docs/adr/: 2 ADRs" in out
