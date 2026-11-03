"""Tests for the companion's read-only git watcher (htmlkit.gitwatch).

Every test builds a real temp repo with subprocess git. Worktrees hold code written by unsandboxed
workers, so the hardening tests plant fsmonitor, hook and external-diff payloads and assert none run.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import gitwatch  # noqa: E402
from htmlkit.gitwatch import GitError, Watcher, observe, task_diff  # noqa: E402

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
}


def g(cwd, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], env=ENV, check=True, capture_output=True, text=True
    ).stdout.strip()


def commit_file(cwd, name: str, text: str, msg: str = "c") -> str:
    p = Path(cwd) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    g(cwd, "add", "-A")
    g(cwd, "commit", "-q", "-m", msg)
    return g(cwd, "rev-parse", "HEAD")


class Fx:
    """A repo with a feature branch, a RUN.json dict and helpers to build task branches."""

    def __init__(self, root: Path):
        self.root = root
        self.repo = root / "repo"
        self.repo.mkdir()
        g(self.repo, "init", "-q", "-b", "main")
        self.base = commit_file(self.repo, "README.md", "hello\n", "init")
        g(self.repo, "branch", "feat")
        self.run = {
            "v": 1,
            "run_id": "r1",
            "repo": str(self.repo),
            "branch": "feat",
            "branch_pattern": "sdd/{run}/{task}",
            "base": self.base,
            "tasks": [],
        }

    def add_task(self, tid: str) -> str:
        self.run["tasks"].append({"id": tid, "title": tid, "deps": [], "order_after": []})
        return f"sdd/r1/{tid}"

    def fork(self, tid: str, *, commit: tuple[str, str] | None = None) -> str:
        branch = self.add_task(tid)
        g(self.repo, "branch", branch, "feat")
        if commit:
            wt = self.root / f"wt-{tid}"
            g(self.repo, "worktree", "add", "-q", str(wt), branch)
            commit_file(wt, *commit)
            g(self.repo, "worktree", "remove", "--force", str(wt))
        return branch

    def worktree(self, tid: str) -> Path:
        wt = self.root / f"wt-{tid}"
        g(self.repo, "worktree", "add", "-q", str(wt), f"sdd/r1/{tid}")
        return wt


def dispatch(tid: str, branch: str, worktree: Path | str, base: str, n: int = 1) -> dict:
    return {"n": n, "kind": "dispatch", "task": tid, "attempt": 1, "branch": branch,
            "worktree": str(worktree), "base": base}


@pytest.fixture
def fx(tmp_path):
    return Fx(tmp_path.resolve())


def script(path: Path, marker: Path) -> Path:
    path.write_text(f"#!/bin/sh\necho ran >> '{marker}'\nexit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


# ---- hardening ----


def test_git_runs_hardened_and_raises_giterror(fx):
    assert gitwatch.git(fx.repo, "rev-parse", "--is-inside-work-tree").strip() == "true"
    with pytest.raises(GitError):
        gitwatch.git(fx.repo, "rev-parse", "--verify", "--quiet", "refs/heads/nope")
    with pytest.raises(GitError):
        gitwatch.git(fx.root / "missing", "status")


def test_poisoned_worktree_config_never_executes(fx, tmp_path):
    marker = tmp_path / "marker"
    hook = script(tmp_path / "evil.sh", marker)
    branch = fx.fork("T1", commit=("a.txt", "one\n"))
    wt = fx.worktree("T1")
    (wt / "untracked.txt").write_text("u\n")
    (wt / "a.txt").write_text("changed\n")

    g(fx.repo, "config", "extensions.worktreeConfig", "true")
    for cwd in (fx.repo, wt):
        flag = ["--worktree"] if cwd == wt else []
        g(cwd, "config", *flag, "core.fsmonitor", str(hook))
        g(cwd, "config", *flag, "diff.external", str(hook))
        g(cwd, "config", *flag, "core.hooksPath", str(tmp_path / "hooks"))
    for name in ("post-checkout", "pre-commit", "post-merge", "reference-transaction"):
        script(fx.repo / ".git" / "hooks" / name, marker)
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    script(hooks / "post-checkout", marker)

    reports = [dispatch("T1", branch, wt, fx.base)]
    prev = None
    for i in range(3):
        prev = observe(fx.run, reports, prev, float(i))
        assert prev["tasks"]["T1"]["worktree_present"] is True
        diff = task_diff(fx.run, reports, "T1")
        assert diff is not None and diff["source"] == "worktree"
    committed = task_diff(fx.run, reports + [{"n": 2, "kind": "commit", "task": "T1", "commit": "x"}], "T1")
    assert committed["source"] == "commit"
    assert not marker.exists()


def test_poisoned_config_would_run_without_hardening(fx, tmp_path):
    marker = tmp_path / "marker"
    hook = script(tmp_path / "evil.sh", marker)
    g(fx.repo, "config", "core.fsmonitor", str(hook))
    (fx.repo / "x.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(fx.repo), "status"], env=ENV, capture_output=True)
    assert marker.exists()  # proves the payload is live, so the test above is meaningful
    marker.unlink()
    gitwatch.git(fx.repo, "status", "--porcelain=v1")
    assert not marker.exists()


def test_unlisted_worktree_is_never_read(fx, tmp_path, monkeypatch):
    branch = fx.fork("T1", commit=("a.txt", "one\n"))
    rogue = tmp_path / "rogue"
    rogue.mkdir()
    g(rogue, "init", "-q")
    (rogue / "secret.txt").write_text("s\n")
    cwds: list[str] = []
    real = gitwatch.git

    def spy(cwd, *args, **kw):
        cwds.append(os.path.realpath(cwd))
        return real(cwd, *args, **kw)

    monkeypatch.setattr(gitwatch, "git", spy)
    reports = [dispatch("T1", branch, rogue, fx.base)]
    facts = observe(fx.run, reports, None, 1.0)
    assert facts["tasks"]["T1"]["worktree_present"] is False
    assert facts["tasks"]["T1"]["files"] == ["a.txt"]
    diff = task_diff(fx.run, reports, "T1")
    assert diff["source"] == "commit"
    assert [f["path"] for f in diff["files"]] == ["a.txt"]
    assert os.path.realpath(rogue) not in cwds
    assert cwds and all(c == os.path.realpath(fx.repo) for c in cwds)


def test_listed_worktrees_returns_realpaths(fx):
    fx.fork("T1")
    wt = fx.worktree("T1")
    listed = gitwatch.listed_worktrees(fx.repo)
    assert os.path.realpath(wt) in listed
    assert os.path.realpath(fx.repo) in listed


# ---- facts ----


def test_unreported_branch_one_commit_then_merged(fx):
    branch = fx.fork("T1", commit=("a.txt", "one\n"))
    facts = observe(fx.run, [], None, 1.0)["tasks"]["T1"]
    assert facts["commits"] == 1 and facts["merged"] is False
    assert facts["worktree_present"] is False
    assert facts["branch_head"] == g(fx.repo, "rev-parse", branch)
    assert facts["files"] == ["a.txt"]

    wt = fx.root / "integ"
    g(fx.repo, "worktree", "add", "-q", str(wt), "feat")
    g(wt, "merge", "--no-ff", "-q", "-m", "merge T1", branch)
    after = observe(fx.run, [], None, 2.0)["tasks"]["T1"]
    assert after["merged"] is True


def test_fresh_fork_has_zero_commits_and_is_not_merged(fx):
    fx.fork("T1")
    facts = observe(fx.run, [], None, 1.0)["tasks"]["T1"]
    assert facts["commits"] == 0 and facts["merged"] is False and facts["files"] == []


def test_dispatch_base_counts_from_task_base(fx):
    # the task forked after feat advanced, so counting from the run base would over-count
    commit_file(fx.repo, "feat.txt", "f\n", "advance")  # on main; move feat to it
    g(fx.repo, "branch", "-f", "feat", "main")
    branch = fx.fork("T1", commit=("a.txt", "one\n"))
    green = g(fx.repo, "rev-parse", "feat")
    reports = [dispatch("T1", branch, fx.root / "none", green)]
    facts = observe(fx.run, reports, None, 1.0)["tasks"]["T1"]
    assert facts["commits"] == 1 and facts["files"] == ["a.txt"]


def test_running_task_files_include_untracked(fx):
    branch = fx.fork("T1")
    wt = fx.worktree("T1")
    (wt / "new dir").mkdir()
    (wt / "new dir" / "n.txt").write_text("n\n")
    reports = [dispatch("T1", branch, wt, fx.base)]
    facts = observe(fx.run, reports, None, 1.0)["tasks"]["T1"]
    assert facts["worktree_present"] is True
    assert "new dir/n.txt" in facts["files"]


def test_task_without_branch_has_no_entry(fx):
    fx.add_task("T9")
    assert observe(fx.run, [], None, 1.0)["tasks"] == {}


def test_dispatch_branch_overrides_pattern_and_task_add_is_observed(fx):
    g(fx.repo, "branch", "custom/x", "feat")
    fx.add_task("T1")
    fix = {"id": "F1", "title": "fix", "deps": [], "order_after": []}
    g(fx.repo, "branch", "sdd/r1/F1", "feat")
    reports = [
        dispatch("T1", "custom/x", fx.root / "none", fx.base),
        {"n": 2, "kind": "task-add", "task": fix, "round": "c1"},
    ]
    tasks = observe(fx.run, reports, None, 1.0)["tasks"]
    assert set(tasks) == {"T1", "F1"}
    assert tasks["T1"]["branch_head"] == g(fx.repo, "rev-parse", "custom/x")


def test_per_task_error_keeps_previous_facts(fx):
    branch = fx.fork("T1", commit=("a.txt", "one\n"))
    first = observe(fx.run, [], None, 1.0)
    bad = [dispatch("T1", branch, fx.root / "none", "deadbeef" * 5)]
    second = observe(fx.run, bad, first, 2.0)["tasks"]["T1"]
    assert "error" in second
    assert second["commits"] == first["tasks"]["T1"]["commits"]
    assert second["branch_head"] == first["tasks"]["T1"]["branch_head"]


def test_changed_at_stable_then_moves(fx):
    branch = fx.fork("T1", commit=("a.txt", "one\n"))
    one = observe(fx.run, [], None, 10.0)
    assert one["changed_at"] == 10.0 and one["observed_at"] == 10.0
    two = observe(fx.run, [], one, 20.0)
    assert two["changed_at"] == 10.0 and two["observed_at"] == 20.0
    wt = fx.worktree("T1")
    commit_file(wt, "b.txt", "two\n")
    three = observe(fx.run, [], two, 30.0)
    assert three["changed_at"] == 30.0
    assert three["tasks"]["T1"]["commits"] == 2
    assert branch in g(fx.repo, "branch", "--list", branch)


# ---- task_diff ----


def test_task_diff_unknown_task_or_no_branch(fx):
    fx.add_task("T1")
    assert task_diff(fx.run, [], "T1") is None
    assert task_diff(fx.run, [], "nope") is None


def test_task_diff_committed_lists_files_with_patches(fx):
    branch = fx.fork("T1")
    wt = fx.worktree("T1")
    (wt / "README.md").write_text("hello\nworld\n")
    (wt / "added.txt").write_text("new\n")
    g(wt, "add", "-A")
    g(wt, "commit", "-q", "-m", "work")
    g(wt, "mv", "added.txt", "renamed.txt")
    g(wt, "commit", "-q", "-m", "rename")
    (wt / "blob.bin").write_bytes(b"\x00\x01\x02")
    g(wt, "add", "-A")
    g(wt, "commit", "-q", "-m", "bin")
    head = g(wt, "rev-parse", "HEAD")
    reports = [dispatch("T1", branch, wt, fx.base), {"n": 2, "kind": "commit", "task": "T1", "commit": head}]
    diff = task_diff(fx.run, reports, "T1")
    assert diff["task"] == "T1" and diff["source"] == "commit" and diff["head"] == head
    assert diff["base"] == fx.base and diff["truncated"] is False
    by = {f["path"]: f for f in diff["files"]}
    assert by["README.md"]["status"] == "modified" and "+world" in by["README.md"]["patch"]
    assert by["renamed.txt"]["status"] == "added" and "+new" in by["renamed.txt"]["patch"]
    assert by["blob.bin"]["binary"] is True and by["blob.bin"]["patch"] == ""


def test_task_diff_base_falls_back_to_merge_base(fx):
    branch = fx.fork("T1", commit=("a.txt", "one\n"))
    diff = task_diff(fx.run, [], "T1")
    assert diff["base"] == fx.base and diff["head"] == g(fx.repo, "rev-parse", branch)
    assert [f["path"] for f in diff["files"]] == ["a.txt"]


def test_task_diff_deleted_file(fx):
    branch = fx.fork("T1")
    wt = fx.worktree("T1")
    g(wt, "rm", "-q", "README.md")
    g(wt, "commit", "-q", "-m", "rm")
    diff = task_diff(fx.run, [], "T1")
    assert [(f["path"], f["status"]) for f in diff["files"]] == [("README.md", "deleted")]
    assert branch


def test_task_diff_running_includes_untracked_as_added(fx):
    branch = fx.fork("T1")
    wt = fx.worktree("T1")
    (wt / "README.md").write_text("hello\nedited\n")
    (wt / "fresh.txt").write_text("line1\nline2\n")
    (wt / "blob.dat").write_bytes(b"ab\x00cd")
    (wt / "big.txt").write_text("x" * (300 * 1024))
    reports = [dispatch("T1", branch, wt, fx.base)]
    diff = task_diff(fx.run, reports, "T1")
    assert diff["source"] == "worktree" and diff["head"] is None and diff["base"] == fx.base
    by = {f["path"]: f for f in diff["files"]}
    assert by["README.md"]["status"] == "modified" and "+edited" in by["README.md"]["patch"]
    assert by["fresh.txt"]["status"] == "added" and "+line2" in by["fresh.txt"]["patch"]
    assert by["blob.dat"]["binary"] is True and by["blob.dat"]["patch"] == ""
    assert by["big.txt"]["status"] == "added"
    assert len(by["big.txt"]["patch"]) < 300 * 1024


def test_task_diff_untracked_symlink_and_fifo_are_skipped(fx, tmp_path):
    branch = fx.fork("T1")
    wt = fx.worktree("T1")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n")
    (wt / "link.txt").symlink_to(outside)
    os.mkfifo(wt / "pipe")
    (wt / "ok.txt").write_text("ok\n")
    diff = task_diff(fx.run, [dispatch("T1", branch, wt, fx.base)], "T1")
    paths = [f["path"] for f in diff["files"]]
    assert "ok.txt" in paths and "link.txt" not in paths and "pipe" not in paths
    assert not any("secret" in f["patch"] for f in diff["files"])


def test_task_diff_truncates_at_max_bytes(fx):
    branch = fx.fork("T1")
    wt = fx.worktree("T1")
    for i in range(4):
        (wt / f"f{i}.txt").write_text("line\n" * 50)
    g(wt, "add", "-A")
    g(wt, "commit", "-q", "-m", "many")
    diff = task_diff(fx.run, [], "T1", max_bytes=100)
    assert diff["truncated"] is True and 1 <= len(diff["files"]) < 4
    full = task_diff(fx.run, [], "T1")
    assert full["truncated"] is False and len(full["files"]) == 4
    assert branch


# ---- watcher ----


def wait_for(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_watcher_saves_on_first_poll_and_after_change_then_stops(fx):
    branch = fx.fork("T1", commit=("a.txt", "one\n"))
    saved: list[dict] = []
    reports: list[dict] = []
    lock = threading.Lock()

    def load():
        with lock:
            return fx.run, list(reports), (saved[-1] if saved else None)

    def save(facts):
        with lock:
            saved.append(facts)

    w = Watcher(load, save, interval=0.05)
    w.start()
    try:
        assert wait_for(lambda: len(saved) == 1)
        time.sleep(0.3)
        assert len(saved) == 1
        wt = fx.worktree("T1")
        commit_file(wt, "b.txt", "two\n")
        assert wait_for(lambda: len(saved) == 2)
        assert saved[1]["tasks"]["T1"]["commits"] == 2
        assert saved[1]["changed_at"] > saved[0]["changed_at"]
    finally:
        t0 = time.time()
        w.stop()
        w.join(1.0)
    assert not w.is_alive() and time.time() - t0 < 1.0
    assert w.daemon and branch


def test_watcher_final_poll_after_run_end_then_idles_and_restarts(fx):
    fx.fork("T1", commit=("a.txt", "one\n"))
    state = {"reports": [{"n": 1, "kind": "run-end", "outcome": "clean"}], "prev": None, "loads": 0}
    saved: list[dict] = []

    def load():
        state["loads"] += 1
        return fx.run, list(state["reports"]), state["prev"]

    def save(facts):
        saved.append(facts)
        state["prev"] = facts

    w = Watcher(load, save, interval=0.05)
    w.start()
    try:
        assert wait_for(lambda: len(saved) == 1)
        wt = fx.worktree("T1")
        commit_file(wt, "b.txt", "two\n")
        time.sleep(0.3)
        assert len(saved) == 1  # ended run: no polling after the final one
        assert state["loads"] > 2  # but still idling and checking
        state["reports"] = []  # a new run starts
        assert wait_for(lambda: len(saved) == 2)
    finally:
        w.stop()
        w.join(1.0)
    assert not w.is_alive()


def test_watcher_survives_exception_in_poll(fx):
    fx.fork("T1", commit=("a.txt", "one\n"))
    calls = {"n": 0}
    saved: list[dict] = []

    def load():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return fx.run, [], None

    w = Watcher(load, saved.append, interval=0.05)
    w.start()
    try:
        assert wait_for(lambda: len(saved) >= 1)
    finally:
        w.stop()
        w.join(1.0)


def test_watcher_retries_final_poll_when_it_raises(fx):
    fx.fork("T1", commit=("a.txt", "one\n"))
    calls = {"n": 0}
    saved: list[dict] = []

    def load():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient git error")
        return fx.run, [{"n": 1, "kind": "run-end", "outcome": "clean"}], None

    w = Watcher(load, saved.append, interval=0.05)
    w.start()
    try:
        assert wait_for(lambda: len(saved) == 1)
    finally:
        w.stop()
        w.join(1.0)
    assert not w.is_alive()


def test_watcher_retries_final_poll_when_observe_raises(fx, monkeypatch):
    fx.fork("T1", commit=("a.txt", "one\n"))
    real = gitwatch.observe
    calls = {"n": 0}
    saved: list[dict] = []

    def flaky(*args, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient git error")
        return real(*args, **kw)

    monkeypatch.setattr(gitwatch, "observe", flaky)
    reports = [{"n": 1, "kind": "run-end", "outcome": "clean"}]
    w = Watcher(lambda: (fx.run, reports, None), saved.append, interval=0.05)
    w.start()
    try:
        assert wait_for(lambda: len(saved) == 1)
    finally:
        w.stop()
        w.join(1.0)
    assert not w.is_alive()


def test_watcher_retries_failed_save_until_it_succeeds(fx):
    fx.fork("T1", commit=("a.txt", "one\n"))
    state = {"prev": None, "attempts": 0}
    saved: list[dict] = []

    def load():
        return fx.run, [], state["prev"]

    def save(facts):
        state["attempts"] += 1
        if state["attempts"] == 1:
            raise OSError("disk full")
        saved.append(facts)
        state["prev"] = facts

    w = Watcher(load, save, interval=0.05)
    w.start()
    try:
        assert wait_for(lambda: len(saved) == 1)
        assert state["attempts"] == 2
    finally:
        w.stop()
        w.join(1.0)
    assert not w.is_alive()


def test_watcher_failed_final_save_is_retried_not_finalized(fx):
    fx.fork("T1", commit=("a.txt", "one\n"))
    state = {"prev": None, "attempts": 0}
    saved: list[dict] = []
    reports = [{"n": 1, "kind": "run-end", "outcome": "clean"}]

    def save(facts):
        state["attempts"] += 1
        if state["attempts"] == 1:
            raise OSError("disk full")
        saved.append(facts)
        state["prev"] = facts

    w = Watcher(lambda: (fx.run, reports, state["prev"]), save, interval=0.05)
    w.start()
    try:
        assert wait_for(lambda: len(saved) == 1)
        time.sleep(0.3)
        assert len(saved) == 1 and state["attempts"] == 2
    finally:
        w.stop()
        w.join(1.0)
