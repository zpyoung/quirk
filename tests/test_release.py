from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

import release

REPO = Path(__file__).resolve().parent.parent
VERSION_FILES = ("pyproject.toml", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json")


@pytest.mark.parametrize(
    ("current", "today", "expected"),
    [
        ("2026.9.25", date(2026, 10, 8), "2026.10.8"),
        ("2026.10.8", date(2026, 10, 8), "2026.10.8.1"),
        ("2026.10.8.3", date(2026, 10, 8), "2026.10.8.4"),
        ("2026.1.5.2", date(2026, 1, 6), "2026.1.6"),
        ("2026.12.31", date(2027, 1, 1), "2027.1.1"),
        ("5.1.0", date(2026, 7, 9), "2026.7.9"),
    ],
)
def test_next_version(current: str, today: date, expected: str) -> None:
    assert release.next_version(current, today) == expected


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    for rel in (*VERSION_FILES, "CHANGELOG.md"):
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, dest)
    return tmp_path


def test_stamp_changes_only_version_strings(repo_copy: Path) -> None:
    current = release.read_version(repo_copy)
    before = {rel: (repo_copy / rel).read_text() for rel in VERSION_FILES}
    release.stamp(repo_copy, "2099.1.2.3")
    for rel in VERSION_FILES:
        after = (repo_copy / rel).read_text()
        assert after == before[rel].replace(current, "2099.1.2.3"), rel
    assert release.read_version(repo_copy) == "2099.1.2.3"
    assert json.loads((repo_copy / ".claude-plugin/plugin.json").read_text())["version"] == "2099.1.2.3"
    market = json.loads((repo_copy / ".claude-plugin/marketplace.json").read_text())
    assert market["plugins"][0]["version"] == "2099.1.2.3"


def test_stamp_raises_when_field_missing(repo_copy: Path) -> None:
    plugin = repo_copy / ".claude-plugin/plugin.json"
    plugin.write_text(plugin.read_text().replace('"version"', '"ver"'))
    with pytest.raises(release.ReleaseError, match="plugin.json"):
        release.stamp(repo_copy, "2099.1.2")


def _pr(**overrides: object) -> dict:
    pr = {"number": 44, "title": "Add release workflow", "body": "", "labels": []}
    pr.update(overrides)
    return pr


def test_entry_falls_back_to_title() -> None:
    entry = release.changelog_entry("2026.10.8", _pr(body=None))
    assert entry == "## 2026.10.8\n\n### Changes\n- Add release workflow (#44)\n"


def test_entry_uses_changelog_section_until_next_heading() -> None:
    body = (
        "Intro text.\n\n## Changelog\n- **New:** auto releases.\n  Wrapped line.\n"
        "- Second item.\n\n## Testing\n- not in changelog\n"
    )
    entry = release.changelog_entry("2026.10.8", _pr(body=body))
    assert entry == (
        "## 2026.10.8\n\n### Changes\n"
        "- **New:** auto releases.\n  Wrapped line.\n- Second item.\n"
    )


def test_entry_handles_crlf_body() -> None:
    body = "## Changelog\r\n- One.\r\n- Two.\r\n"
    entry = release.changelog_entry("2026.10.8", _pr(body=body))
    assert entry == "## 2026.10.8\n\n### Changes\n- One.\n- Two.\n"


def test_entry_with_empty_changelog_section_falls_back_to_title() -> None:
    entry = release.changelog_entry("2026.10.8", _pr(body="## Changelog\n\n## Notes\nx\n"))
    assert "- Add release workflow (#44)" in entry


def test_breaking_label_moves_entry_under_breaking() -> None:
    entry = release.changelog_entry("2026.10.8", _pr(labels=[{"name": "breaking"}]))
    assert entry == "## 2026.10.8\n\n### ⚠️ BREAKING\n- Add release workflow (#44)\n"


def test_prepend_keeps_header_and_puts_entry_on_top(repo_copy: Path) -> None:
    path = repo_copy / "CHANGELOG.md"
    original = path.read_text()
    first_heading = original.index("\n## ") + 1
    release.prepend_changelog(path, "## 2099.1.1\n\n### Changes\n- x (#1)\n")
    updated = path.read_text()
    assert updated.startswith(original[:first_heading])
    assert updated[first_heading:].startswith("## 2099.1.1\n\n### Changes\n- x (#1)\n\n## ")
    assert updated.endswith(original[first_heading:])


def test_main_end_to_end(repo_copy: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    event = repo_copy / "event.json"
    event.write_text(json.dumps({"pull_request": _pr()}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setattr(release, "today", lambda: date(2099, 3, 4))
    assert release.main(["--root", str(repo_copy)]) == 0
    assert capsys.readouterr().out.strip() == "2099.3.4"
    assert release.read_version(repo_copy) == "2099.3.4"
    assert "## 2099.3.4\n\n### Changes\n- Add release workflow (#44)\n" in (repo_copy / "CHANGELOG.md").read_text()
