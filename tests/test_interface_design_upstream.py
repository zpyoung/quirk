"""NOTICE parsing and upstream drift for quirk:interface-design. Offline: local file:// repos only."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "interface-design" / "scripts" / "upstream_diff.py"
REAL_NOTICE = REPO_ROOT / "skills" / "interface-design" / "NOTICE.md"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("interface_design_upstream_diff", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


upstream = _load()


def _git(cwd: Path, *args: str) -> str:
    import os

    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env={**os.environ, **GIT_ENV},
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _make_repo(root: Path, name: str, files: List[str]) -> Path:
    """Create a one-commit repo containing the given relative files; return its path."""
    repo = root / name
    repo.mkdir()
    _git(repo, "init", "-q")
    for rel in files:
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{name} {rel} v1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"{name} initial")
    return repo


def _commit_change(repo: Path, rel: str, message: str) -> None:
    (repo / rel).write_text(f"{repo.name} {rel} changed: {message}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _notice(rows: List[str]) -> str:
    header = "| source | repo | path | license | pinned |\n|---|---|---|---|---|\n"
    return "# Sources\n\nintro text\n\n" + header + "\n".join(rows) + "\n\nBelow the table.\n"


def _row(name: str, repo: Path, path: str, sha: str, license_: str = "MIT") -> str:
    return f"| {name} | file://{repo} | {path} | {license_} | {sha} |"


class TestParseNotice:
    def test_parses_rows_in_order(self) -> None:
        text = _notice([
            "| alpha | https://example.com/a | .claude | MIT | " + "a" * 40 + " |",
            "| beta | https://example.com/b | command.md | Apache-2.0 | " + "B" * 40 + " |",
        ])
        sources = upstream.parse_notice(text)
        assert [s.name for s in sources] == ["alpha", "beta"]
        assert sources[0].repo == "https://example.com/a"
        assert sources[0].path == ".claude"
        assert sources[1].license == "Apache-2.0"
        assert sources[1].pinned == "b" * 40

    def test_ignores_prose_around_the_table(self) -> None:
        text = "before | not | a | table |\n" + _notice(
            ["| alpha | https://example.com/a | p | MIT | " + "a" * 40 + " |"]
        ) + "| stray | row | after | the | table |\n"
        assert [s.name for s in upstream.parse_notice(text)] == ["alpha"]

    @pytest.mark.parametrize(
        "text",
        [
            "no table here\n",
            "| source | repo | path | license | pinned |\n|---|---|---|---|---|\n",
            "| source | repo | path | license | pinned |\n|---|---|---|---|---|\n"
            "| a | https://x | p | MIT | abc123 |\n",
            "| source | repo | path | license | pinned |\n|---|---|---|---|---|\n"
            "| a | https://x | p | MIT |\n",
            "| name | repo | path | license | pinned |\n|---|---|---|---|---|\n"
            "| a | https://x | p | MIT | " + "a" * 40 + " |\n",
        ],
        ids=["no-table", "no-rows", "short-sha", "missing-column", "wrong-header"],
    )
    def test_malformed_table_raises(self, text: str) -> None:
        with pytest.raises(upstream.NoticeError):
            upstream.parse_notice(text)

    @pytest.mark.parametrize("separator", ["|---|", "|---|---|", "|---|---|---|---|---|---|"])
    def test_separator_column_count_must_match_header(self, separator: str) -> None:
        text = (
            "| source | repo | path | license | pinned |\n" + separator + "\n"
            "| a | https://x | p | MIT | " + "a" * 40 + " |\n"
        )
        with pytest.raises(upstream.NoticeError):
            upstream.parse_notice(text)

    def test_shipped_notice_parses_with_full_shas(self) -> None:
        sources = upstream.parse_notice(REAL_NOTICE.read_text())
        assert [s.name for s in sources] == [
            "interface-design",
            "web-interface-guidelines",
            "web-design-guidelines-skill",
            "impeccable",
        ]
        assert all(len(s.pinned) == 40 for s in sources)
        wig = next(s for s in sources if s.name == "web-interface-guidelines")
        assert wig.pinned == "434b7f91364665f2f733b310ec54809bf8f37937"


class TestShippedFiles:
    def test_notice_carries_attribution_and_licenses_pointer(self) -> None:
        text = REAL_NOTICE.read_text()
        assert "https://github.com/ehmo/platform-design-skills" in text
        assert "licenses/" in text
        assert "rewritten" in text and "modified" in text

    @pytest.mark.parametrize(
        "name",
        ["interface-design-MIT.txt", "web-interface-guidelines-MIT.txt", "impeccable-Apache-2.0.txt"],
    )
    def test_license_files_exist(self, name: str) -> None:
        assert (REAL_NOTICE.parent / "licenses" / name).read_text().strip()


class TestDrift:
    def _run(self, tmp_path: Path, rows: List[str], capsys: pytest.CaptureFixture[str]):
        notice = tmp_path / "NOTICE.md"
        notice.write_text(_notice(rows))
        code = upstream.main(["--notice", str(notice)])
        return code, capsys.readouterr()

    def test_all_at_pin_exits_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        repo = _make_repo(tmp_path, "stable", ["skill/a.md"])
        pin = _git(repo, "rev-parse", "HEAD")
        code, out = self._run(tmp_path, [_row("stable", repo, "skill", pin)], capsys)
        assert code == 0
        assert "stable: no change" in out.out

    def test_moved_source_exits_one_and_names_only_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stable = _make_repo(tmp_path, "stable", ["skill/a.md"])
        stable_pin = _git(stable, "rev-parse", "HEAD")
        moved = _make_repo(tmp_path, "moved", ["skill/a.md", "other/b.md"])
        moved_pin = _git(moved, "rev-parse", "HEAD")
        _commit_change(moved, "skill/a.md", "touch skill")
        _commit_change(moved, "other/b.md", "touch other")

        code, out = self._run(
            tmp_path,
            [_row("stable", stable, "skill", stable_pin), _row("moved", moved, "skill", moved_pin)],
            capsys,
        )
        assert code == 1
        text = out.out
        assert "stable: no change" in text
        assert "moved:" in text and "no change" not in text.split("moved:", 1)[1].splitlines()[0]
        assert "2 commits" in text
        assert "touch skill" in text
        assert "touch other" not in text
        assert "skill/a.md" in text
        assert "other/b.md" not in text

    def test_does_not_write_inside_repo(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        moved = _make_repo(tmp_path, "moved", ["skill/a.md"])
        pin = _git(moved, "rev-parse", "HEAD")
        _commit_change(moved, "skill/a.md", "touch skill")
        before = sorted(p.name for p in REPO_ROOT.iterdir())
        self._run(tmp_path, [_row("moved", moved, "skill", pin)], capsys)
        assert sorted(p.name for p in REPO_ROOT.iterdir()) == before

    def test_unreachable_pin_exits_two(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        repo = _make_repo(tmp_path, "r", ["skill/a.md"])
        code, out = self._run(tmp_path, [_row("r", repo, "skill", "0" * 40)], capsys)
        assert code == 2
        assert out.err.strip()

    def test_unreachable_repo_exits_two(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        missing = tmp_path / "does-not-exist"
        code, out = self._run(tmp_path, [_row("gone", missing, "skill", "a" * 40)], capsys)
        assert code == 2
        assert out.err.strip()


class TestCli:
    def test_malformed_table_exits_two(self, tmp_path: Path) -> None:
        notice = tmp_path / "NOTICE.md"
        notice.write_text("# Sources\n\n| source | repo | path | license | pinned |\n|---|---|---|---|---|\n"
                          "| a | https://x | p | MIT | not-a-sha |\n")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--notice", str(notice)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert result.stderr.strip()

    @pytest.mark.parametrize("separator", ["|---|", "|---|---|---|---|---|---|"])
    def test_wrong_separator_column_count_exits_two_before_git(
        self, tmp_path: Path, separator: str
    ) -> None:
        notice = tmp_path / "NOTICE.md"
        notice.write_text(
            "| source | repo | path | license | pinned |\n" + separator + "\n"
            "| a | file:///nonexistent | p | MIT | " + "a" * 40 + " |\n"
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--notice", str(notice)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "separator" in result.stderr
        assert result.stdout == ""

    def test_missing_notice_exits_two(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--notice", str(tmp_path / "nope.md")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2

    def test_cli_reports_moved_source(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, "moved", ["skill/a.md"])
        pin = _git(repo, "rev-parse", "HEAD")
        _commit_change(repo, "skill/a.md", "touch skill")
        notice = tmp_path / "NOTICE.md"
        notice.write_text(_notice([_row("moved", repo, "skill", pin)]))
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--notice", str(notice)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "touch skill" in result.stdout
