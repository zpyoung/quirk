from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

from .conftest import BIN_DIR, REPO_ROOT, run_script

sys.path.insert(0, str(BIN_DIR))
import agent_isles


def _exe(path: Path) -> None:
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_doctor_reports_without_mutation(tmp_path: Path) -> None:
    result = run_script("agent_isles.py", "doctor", "--repo-root", str(tmp_path), cwd=tmp_path)
    assert result.returncode == 0
    assert "Agent Isles bridge doctor" in result.stdout
    assert "repo-local isles:" in result.stdout
    assert not (tmp_path / ".quirk").exists()


def test_render_command_prefers_repo_local_isles(tmp_path: Path) -> None:
    local = tmp_path / "node_modules" / ".bin" / "isles"
    local.parent.mkdir(parents=True)
    _exe(local)
    pack = tmp_path / "packs" / "quirk"
    pack.mkdir(parents=True)
    artifact = tmp_path / "examples" / "report.md"
    artifact.parent.mkdir()
    artifact.write_text("# Report\n")

    cmd = agent_isles.build_command("render", artifact, repo_root=tmp_path, execute=False)

    assert cmd.argv[0] == str(local)
    assert cmd.argv[:3] == [str(local), "render", str(artifact)]
    assert "--pack" in cmd.argv
    assert str(pack) in cmd.argv
    assert "--no-user-packs" in cmd.argv
    assert str(tmp_path / ".quirk" / "isles" / "report.html") in cmd.argv


def test_render_command_uses_path_isles(tmp_path: Path, monkeypatch) -> None:
    path_dir = tmp_path / "pathbin"
    path_dir.mkdir()
    _exe(path_dir / "isles")
    artifact = tmp_path / "artifact.md"
    artifact.write_text("# Artifact\n")
    monkeypatch.setenv("PATH", str(path_dir))

    cmd = agent_isles.build_command("render", artifact, repo_root=tmp_path, execute=False)

    assert cmd.argv[0] == str(path_dir / "isles")
    assert "--pack" not in cmd.argv
    assert "--no-user-packs" in cmd.argv


def test_render_command_uses_explicit_npx_fallback(tmp_path: Path, monkeypatch) -> None:
    path_dir = tmp_path / "pathbin"
    path_dir.mkdir()
    _exe(path_dir / "npx")
    artifact = tmp_path / "artifact.md"
    artifact.write_text("# Artifact\n")
    monkeypatch.setenv("PATH", str(path_dir))

    cmd = agent_isles.build_command("render", artifact, repo_root=tmp_path, execute=False)

    assert cmd.argv[:3] == [str(path_dir / "npx"), "agent-isles@next", "render"]
    assert cmd.note == "npx fallback is explicit; it may download agent-isles@next when executed"


def test_no_agent_isles_path_fails_without_npx(tmp_path: Path, monkeypatch) -> None:
    artifact = tmp_path / "artifact.md"
    artifact.write_text("# Artifact\n")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    try:
        agent_isles.build_command("render", artifact, repo_root=tmp_path, no_npx=True)
    except agent_isles.AgentIslesUnavailable as exc:
        assert "No Agent Isles executable found" in str(exc)
    else:
        raise AssertionError("expected AgentIslesUnavailable")


def test_print_command_does_not_create_output_dir(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.md"
    artifact.write_text("# Artifact\n")
    result = run_script(
        "agent_isles.py",
        "command",
        str(artifact),
        "--repo-root",
        str(tmp_path),
        "--no-npx",
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert not (tmp_path / ".quirk").exists()
