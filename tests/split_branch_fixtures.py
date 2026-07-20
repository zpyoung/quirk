from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Union


@dataclass(frozen=True)
class FixtureRepo:
    path: Path
    base: str
    head: str
    branch: str


_FIXED_ENV = {
    "GIT_AUTHOR_NAME": "Fixture Author",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+0000",
    "GIT_COMMITTER_NAME": "Fixture Author",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+0000",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
}


def _git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env.update(_FIXED_ENV)
    return subprocess.run(
        ["git", *args], cwd=repo, env=env, check=True, text=True, capture_output=True
    ).stdout.strip()


def make_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir(parents=True)
    _git(repo, "init", "--quiet")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "config", "user.name", "Fixture Author")
    _git(repo, "config", "commit.gpgSign", "false")
    commit(repo, {"README.md": "fixture repository\n"}, "initial commit")
    return repo


def _commit_files(
    repo: Path, files: Dict[str, Union[str, bytes]], message: str
) -> str:
    for relative_name, contents in files.items():
        destination = repo / relative_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contents, bytes):
            destination.write_bytes(contents)
        else:
            destination.write_text(contents)
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def commit(repo: Path, files: dict[str, str], message: str) -> str:
    return _commit_files(repo, files, message)


def _start_feature(repo: Path) -> tuple[str, str]:
    base = _git(repo, "rev-parse", "HEAD")
    branch = "feature"
    _git(repo, "checkout", "--quiet", "-b", branch)
    return base, branch


def _finish(repo: Path, base: str, branch: str) -> FixtureRepo:
    return FixtureRepo(repo, base, _git(repo, "rev-parse", "HEAD"), branch)


def _simple(tmp_path: Path) -> FixtureRepo:
    repo = make_repo(tmp_path)
    initial = "".join(f"line {number}\n" for number in range(1, 13))
    commit(repo, {f"file-{number}.txt": initial for number in range(1, 4)}, "add files")
    base, branch = _start_feature(repo)
    changed = "".join(
        f"changed {number}\n" if number in (2, 11) else f"line {number}\n"
        for number in range(1, 13)
    )
    commit(repo, {f"file-{number}.txt": changed for number in range(1, 4)}, "change six regions")
    return _finish(repo, base, branch)


def _closely_spaced(tmp_path: Path) -> FixtureRepo:
    repo = make_repo(tmp_path)
    original = "".join(f"line {number}\n" for number in range(1, 9))
    commit(repo, {"close.txt": original}, "add close regions")
    base, branch = _start_feature(repo)
    changed = "".join(
        f"changed {number}\n" if number in (3, 6) else f"line {number}\n"
        for number in range(1, 9)
    )
    commit(repo, {"close.txt": changed}, "change close regions")
    return _finish(repo, base, branch)


def _binary(tmp_path: Path) -> FixtureRepo:
    repo = make_repo(tmp_path)
    _commit_files(repo, {"notes.txt": "before\n", "data.bin": bytes(range(256))}, "add binary")
    base, branch = _start_feature(repo)
    _commit_files(
        repo,
        {"notes.txt": "after\n", "data.bin": bytes(reversed(range(256)))},
        "change binary and text",
    )
    return _finish(repo, base, branch)


def _split_floor(tmp_path: Path) -> FixtureRepo:
    repo = make_repo(tmp_path)
    commit(repo, {"floor.txt": "top\none\ntwo\nthree\nbottom\n"}, "add floor")
    base, branch = _start_feature(repo)
    commit(repo, {"floor.txt": "top\nONE\nTWO\nTHREE\nbottom\n"}, "change consecutive lines")
    return _finish(repo, base, branch)


def _rename_mode(tmp_path: Path) -> FixtureRepo:
    repo = make_repo(tmp_path)
    commit(repo, {"old-script.sh": "#!/bin/sh\necho fixture\n"}, "add script")
    base, branch = _start_feature(repo)
    source = repo / "old-script.sh"
    destination = repo / "new-script.sh"
    source.rename(destination)
    destination.chmod(0o755)
    _commit_files(repo, {}, "rename and make executable")
    return _finish(repo, base, branch)


def _no_newline_eof(tmp_path: Path) -> FixtureRepo:
    repo = make_repo(tmp_path)
    commit(repo, {"unterminated.txt": "first\nlast"}, "add unterminated file")
    base, branch = _start_feature(repo)
    commit(repo, {"unterminated.txt": "first\nchanged last"}, "change unterminated line")
    return _finish(repo, base, branch)


def _deletion_only(tmp_path: Path) -> FixtureRepo:
    repo = make_repo(tmp_path)
    commit(
        repo,
        {"trim.txt": "keep\nremove one\nremove two\nend\n", "deleted.txt": "gone\n"},
        "add deletable content",
    )
    base, branch = _start_feature(repo)
    (repo / "deleted.txt").unlink()
    commit(repo, {"trim.txt": "keep\nend\n"}, "delete lines and file")
    return _finish(repo, base, branch)


def _merge_commits(tmp_path: Path) -> FixtureRepo:
    repo = make_repo(tmp_path)
    base, branch = _start_feature(repo)
    commit(repo, {"feature.txt": "feature\n"}, "feature change")
    _git(repo, "checkout", "--quiet", "-b", "side", base)
    commit(repo, {"side.txt": "side\n"}, "side change")
    _git(repo, "checkout", "--quiet", branch)
    _git(repo, "merge", "--quiet", "--no-ff", "-m", "merge side", "side")
    return _finish(repo, base, branch)


def _squash_merged_base(tmp_path: Path) -> FixtureRepo:
    repo = make_repo(tmp_path)
    root = _git(repo, "rev-parse", "HEAD")
    _, branch = _start_feature(repo)
    commit(repo, {"early.txt": "first part\n"}, "early feature part one")
    commit(repo, {"early.txt": "first part\nsecond part\n"}, "early feature part two")
    commit(repo, {"late.txt": "late feature content\n"}, "late feature")
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "--quiet", "main")
    commit(
        repo,
        {"early.txt": "first part\nsecond part\n"},
        "squash merge early feature",
    )
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "--quiet", branch)
    assert _git(repo, "merge-base", root, head) == root
    return FixtureRepo(repo, base, head, branch)


_BUILDERS = {
    "simple": _simple,
    "closely_spaced": _closely_spaced,
    "binary": _binary,
    "split_floor": _split_floor,
    "rename_mode": _rename_mode,
    "no_newline_eof": _no_newline_eof,
    "deletion_only": _deletion_only,
    "merge_commits": _merge_commits,
    "squash_merged_base": _squash_merged_base,
}


def build_fixture(tmp_path: Path, kind: str) -> FixtureRepo:
    try:
        builder = _BUILDERS[kind]
    except KeyError:
        raise ValueError(f"unknown fixture kind: {kind}")
    return builder(tmp_path)
