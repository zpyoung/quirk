"""Tests for the run folder, state, lock, credential, and gate helpers in `_run.py`."""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "using-apps-like-a-user" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _run as run  # noqa: E402
from _types import MissingError, RunStateError, UsageError  # noqa: E402

ISO = "%Y-%m-%dT%H:%M:%SZ"


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("LIKEUSER_STATE_ROOT", str(tmp_path / "state"))
    return run.state_root(tmp_path)


def make_run(root, **fields):
    base = {"target": "https://example.test", "surface": "web", "owner": "yours",
            "attended": True, "driver": "playwright-cli", "driver_version": "0.1.22"}
    base.update(fields)
    return run.Run.create(root, base)


def ago(minutes):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).strftime(ISO)


def test_state_root_honors_env_and_self_ignores(tmp_path, monkeypatch):
    target = tmp_path / "elsewhere" / "state"
    monkeypatch.setenv("LIKEUSER_STATE_ROOT", str(target))
    assert run.state_root(tmp_path) == target
    assert (target / ".gitignore").read_text() == "*\n"


def test_state_root_defaults_to_git_toplevel(tmp_path, monkeypatch):
    monkeypatch.delenv("LIKEUSER_STATE_ROOT", raising=False)
    repo = tmp_path / "repo"
    (repo / "pkg" / "deep").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    got = run.state_root(repo / "pkg" / "deep")
    assert got.resolve() == (repo / ".quirk" / "using-apps-like-a-user").resolve()
    assert (got / ".gitignore").read_text() == "*\n"


def test_state_root_falls_back_to_cwd_outside_a_repo(tmp_path, monkeypatch):
    monkeypatch.delenv("LIKEUSER_STATE_ROOT", raising=False)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    plain = tmp_path / "plain"
    plain.mkdir()
    got = run.state_root(plain)
    assert got == plain / ".quirk" / "using-apps-like-a-user"
    assert got.is_dir()


def test_state_root_keeps_the_lines_of_an_existing_gitignore_and_adds_the_catch_all(tmp_path, monkeypatch):
    target = tmp_path / "state"
    target.mkdir()
    (target / ".gitignore").write_text("custom\n")
    monkeypatch.setenv("LIKEUSER_STATE_ROOT", str(target))
    run.state_root(tmp_path)
    assert (target / ".gitignore").read_text() == "custom\n*\n"


@pytest.mark.parametrize("before, after", [
    ("custom", "custom\n*\n"),
    ("*\n", "*\n"),
    ("# keep\n*\n", "# keep\n*\n"),
    ("*\n!keep.json\n", "*\n!keep.json\n*\n"),
    ("\n", "\n*\n"),
    ("", "*\n"),
])
def test_state_root_guarantees_the_gitignore_ends_in_the_catch_all(tmp_path, monkeypatch, before, after):
    target = tmp_path / "state"
    target.mkdir()
    (target / ".gitignore").write_text(before)
    monkeypatch.setenv("LIKEUSER_STATE_ROOT", str(target))
    run.state_root(tmp_path)
    run.state_root(tmp_path)
    assert (target / ".gitignore").read_text() == after


def test_state_root_never_writes_through_a_symlinked_gitignore(tmp_path, monkeypatch):
    target = tmp_path / "state"
    target.mkdir()
    project_ignore = tmp_path / "project.gitignore"
    project_ignore.write_text("node_modules\n")
    (target / ".gitignore").symlink_to(project_ignore)
    monkeypatch.setenv("LIKEUSER_STATE_ROOT", str(target))
    run.state_root(tmp_path)
    assert project_ignore.read_text() == "node_modules\n"
    assert not (target / ".gitignore").is_symlink()
    assert (target / ".gitignore").read_text() == "*\n"


@pytest.fixture
def victim(tmp_path):
    target = tmp_path / "victim"
    target.mkdir()
    target.chmod(0o755)
    return target


def assert_untouched(victim):
    assert mode(victim) == 0o755
    assert list(victim.iterdir()) == []


def test_a_symlinked_dot_quirk_is_refused_and_its_target_left_alone(tmp_path, monkeypatch, victim):
    monkeypatch.delenv("LIKEUSER_STATE_ROOT", raising=False)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    project = tmp_path / "project"
    project.mkdir()
    (project / ".quirk").symlink_to(victim)
    with pytest.raises(UsageError) as exc:
        run.state_root(project)
    assert exc.value.code == "unsafe_state_path"
    assert_untouched(victim)


def test_a_symlinked_state_folder_is_refused_and_its_target_left_alone(tmp_path, monkeypatch, victim):
    monkeypatch.delenv("LIKEUSER_STATE_ROOT", raising=False)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    project = tmp_path / "project"
    (project / ".quirk").mkdir(parents=True)
    (project / ".quirk" / "using-apps-like-a-user").symlink_to(victim)
    with pytest.raises(UsageError) as exc:
        run.state_root(project)
    assert exc.value.code == "unsafe_state_path"
    assert_untouched(victim)


def test_a_symlinked_state_root_override_is_refused(tmp_path, monkeypatch, victim):
    link = tmp_path / "state"
    link.symlink_to(victim)
    monkeypatch.setenv("LIKEUSER_STATE_ROOT", str(link))
    with pytest.raises(UsageError) as exc:
        run.state_root(tmp_path)
    assert exc.value.code == "unsafe_state_path"
    assert_untouched(victim)


def test_a_state_folder_owned_by_someone_else_is_refused(tmp_path, monkeypatch):
    target = tmp_path / "state"
    target.mkdir()
    monkeypatch.setenv("LIKEUSER_STATE_ROOT", str(target))
    monkeypatch.setattr(run.os, "getuid", lambda: target.stat().st_uid + 1)
    with pytest.raises(UsageError) as exc:
        run.state_root(tmp_path)
    assert exc.value.code == "unsafe_state_path"


def test_a_symlinked_runs_folder_is_refused_and_its_target_left_alone(root, victim):
    (root / "runs").symlink_to(victim)
    with pytest.raises(UsageError) as exc:
        make_run(root)
    assert exc.value.code == "unsafe_state_path"
    assert_untouched(victim)


def test_a_symlinked_run_folder_is_refused_at_load(root, victim):
    (root / "runs").mkdir()
    (root / "runs" / "20260101T000000-abcd").symlink_to(victim)
    (victim / "run.json").write_text("{}")
    victim.chmod(0o755)
    with pytest.raises(UsageError) as exc:
        run.Run.load(root, "20260101T000000-abcd")
    assert exc.value.code == "unsafe_state_path"
    assert mode(victim) == 0o755


def test_a_symlinked_typed_folder_is_refused_and_its_target_left_alone(root, victim):
    (root / "typed").symlink_to(victim)
    with pytest.raises(UsageError) as exc:
        run.remember_typed(root, "r1", "typed-text")
    assert exc.value.code == "unsafe_state_path"
    assert_untouched(victim)


def mode(path):
    return stat.S_IMODE(Path(path).stat().st_mode)


@pytest.fixture
def loose_umask():
    previous = os.umask(0o022)
    yield
    os.umask(previous)


def test_the_state_root_and_runs_folder_are_private_whatever_the_umask(tmp_path, monkeypatch, loose_umask):
    monkeypatch.setenv("LIKEUSER_STATE_ROOT", str(tmp_path / "state"))
    state = run.state_root(tmp_path)
    created = make_run(state)
    assert mode(state) == 0o700
    assert mode(state / "runs") == 0o700
    assert mode(created.dir) == 0o700


def test_every_file_a_run_writes_is_private_whatever_the_umask(root, loose_umask):
    created = make_run(root)
    created.add_goal("g1", "goal")
    created.event("act", {"k": "v"}, "ok", 5)
    created.write_report()
    for name in ("run.json", "events.jsonl", "report.json", "report.md"):
        assert mode(created.dir / name) == 0o600, name
    assert mode(root / ".gitignore") == 0o600


def test_harden_makes_files_other_tools_left_in_the_run_folder_private(root, loose_umask, tmp_path):
    created = make_run(root)
    folder = created.dir / ".playwright-cli" / "nested"
    folder.mkdir(parents=True)
    leaked = folder / "page.yml"
    leaked.write_text("secret page text")
    leaked.chmod(0o644)
    shot = created.dir / "obs-1.png"
    shot.write_bytes(b"png")
    shot.chmod(0o666)
    outside = tmp_path / "outside.txt"
    outside.write_text("not ours")
    outside.chmod(0o644)
    (created.dir / "link").symlink_to(outside)
    created.harden()
    assert mode(leaked) == 0o600 and mode(shot) == 0o600
    assert mode(created.dir / ".playwright-cli") == 0o700 and mode(folder) == 0o700
    assert mode(outside) == 0o644


def test_new_run_id_format():
    import re
    ids = {run.new_run_id() for _ in range(20)}
    assert len(ids) > 1
    for rid in ids:
        assert re.fullmatch(r"\d{8}T\d{6}-[0-9a-f]{4}", rid)


def test_create_then_load_round_trips(root):
    created = make_run(root, owner="third-party")
    assert created.dir == root / "runs" / created.data["run_id"]
    assert (created.dir / "run.json").is_file()
    loaded = run.Run.load(root, created.data["run_id"])
    assert loaded.data == created.data
    assert loaded.data["owner"] == "third-party"
    assert loaded.data["budget"] == {"run_cap": 200, "goal_cap": 40, "run_used": 0}
    assert loaded.data["goals"] == {} and loaded.data["findings"] == []
    assert loaded.data["ended"] is None and loaded.data["test_overrides"] == []


def test_create_merges_partial_budget(root):
    r = make_run(root, budget={"run_cap": 5})
    assert r.data["budget"] == {"run_cap": 5, "goal_cap": 40, "run_used": 0}


def test_load_unknown_run(root):
    with pytest.raises(RunStateError) as exc:
        run.Run.load(root, "20000101T000000-ffff")
    assert exc.value.code == "unknown_run"


def test_load_rejects_path_traversal(root):
    make_run(root)
    with pytest.raises(RunStateError) as exc:
        run.Run.load(root, "../runs")
    assert exc.value.code == "unknown_run"


def test_save_is_atomic(root, monkeypatch):
    r = make_run(root)
    before = (r.dir / "run.json").read_text()
    r.data["paused"] = True

    def boom(src, dst):
        raise OSError("disk gone")

    monkeypatch.setattr(run.os, "replace", boom)
    with pytest.raises(OSError):
        r.save()
    monkeypatch.undo()
    assert (r.dir / "run.json").read_text() == before
    assert sorted(p.name for p in r.dir.iterdir()) == ["run.json"]


def test_save_replaces_through_a_temp_file(root, monkeypatch):
    r = make_run(root)
    calls = []
    real = os.replace

    def spy(src, dst):
        calls.append((Path(src).name, Path(dst).name))
        real(src, dst)

    monkeypatch.setattr(run.os, "replace", spy)
    r.data["paused"] = True
    r.save()
    assert calls and calls[0][1] == "run.json" and calls[0][0] != "run.json"
    assert json.loads((r.dir / "run.json").read_text())["paused"] is True


def test_event_appends_one_line_per_call(root):
    r = make_run(root)
    r.event("observe", {"goal": "g1"}, "OK", 12)
    r.event("act", {"action": "click"}, "OBSERVED", 340)
    lines = (r.dir / "events.jsonl").read_text().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert set(first) == {"ts", "verb", "inputs", "status", "elapsed_ms"}
    assert first["verb"] == "observe" and first["inputs"] == {"goal": "g1"}
    assert first["elapsed_ms"] == 12
    assert json.loads(lines[1])["status"] == "OBSERVED"


def test_a_secret_never_reaches_events_or_run_json(root):
    r = make_run(root)
    r.secrets.add("hunter2")
    r.secrets.add('pa"ss\\word')
    r.event("act", {"text": "hunter2", "nested": ["x hunter2 y", {"k": 'pa"ss\\word'}]}, "OBSERVED", 1)
    r.add_goal("g1", "log in with hunter2")
    r.data["goals"]["g1"]["summary"] = 'typed hunter2 and pa"ss\\word'
    r.add_finding("other", "saw hunter2 on screen", "g1", None, "model")
    r.save()
    for name in ("events.jsonl", "run.json"):
        text = (r.dir / name).read_text()
        assert "hunter2" not in text
        assert "pa\\\"ss" not in text and 'pa"ss' not in text
    assert "[REDACTED]" in (r.dir / "events.jsonl").read_text()
    assert "hunter2" in r.data["findings"][0]["summary"]


def test_secrets_are_not_persisted_or_reloaded(root):
    r = make_run(root)
    r.secrets.add("hunter2")
    r.save()
    assert run.Run.load(root, r.data["run_id"]).secrets == set()


def test_typed_text_is_remembered_for_later_verbs_outside_the_run_folder(root):
    r = make_run(root)
    run_id = r.data["run_id"]
    run.remember_typed(root, run_id, "jane@example.com")
    run.remember_typed(root, run_id, "second value")
    run.remember_typed(root, run_id, "jane@example.com")
    assert sorted(run.recall_typed(root, run_id)) == ["jane@example.com", "second value"]
    path = run.typed_path(root, run_id)
    assert r.dir not in path.parents
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert oct(path.parent.stat().st_mode & 0o777) == "0o700"


def test_typed_text_is_per_run(root):
    run.remember_typed(root, "run-a", "alpha value")
    assert run.recall_typed(root, "run-b") == []


def test_forgetting_typed_text_removes_the_file_and_tolerates_absence(root):
    run.remember_typed(root, "run-a", "alpha value")
    run.forget_typed(root, "run-a")
    assert not run.typed_path(root, "run-a").exists()
    assert run.recall_typed(root, "run-a") == []
    run.forget_typed(root, "run-a")


def test_a_corrupt_typed_file_recalls_nothing(root):
    run.remember_typed(root, "run-a", "alpha value")
    run.typed_path(root, "run-a").write_text("{not json")
    assert run.recall_typed(root, "run-a") == []
    run.remember_typed(root, "run-a", "beta value")
    assert run.recall_typed(root, "run-a") == ["beta value"]


def test_the_typed_file_is_never_wider_than_0600_even_for_a_loose_umask(root):
    old = os.umask(0)
    try:
        run.remember_typed(root, "run-a", "alpha value")
    finally:
        os.umask(old)
    assert oct(run.typed_path(root, "run-a").stat().st_mode & 0o777) == "0o600"


def test_driver_snapshot_files_in_the_run_folder_are_redacted(root):
    r = make_run(root)
    folder = r.dir / ".playwright-cli"
    folder.mkdir()
    (folder / "page-1.yml").write_text("- textbox [ref=e1]: hunter2 and hunter2\n")
    (folder / "console-1.log").write_text("typed hunter2\n")
    (folder / "clean.yml").write_text("- button\n")
    (folder / "shot.png").write_bytes(b"\x89PNG\xff\xfehunter2")
    r.secrets.add("hunter2")
    r.scrub_driver_files()
    assert (folder / "page-1.yml").read_text() == "- textbox [ref=e1]: [REDACTED] and [REDACTED]\n"
    assert (folder / "console-1.log").read_text() == "typed [REDACTED]\n"
    assert (folder / "clean.yml").read_text() == "- button\n"
    assert b"hunter2" in (folder / "shot.png").read_bytes()


def test_scrubbing_driver_files_without_secrets_or_a_folder_is_a_noop(root):
    r = make_run(root)
    r.scrub_driver_files()
    r.secrets.add("hunter2")
    r.scrub_driver_files()


def test_add_goal_registers_and_rejects_duplicates(root):
    r = make_run(root)
    r.add_goal("g1", "Sign in")
    assert r.data["goals"]["g1"] == {"title": "Sign in", "last_act_status": None,
                                     "actions_used": 0, "verdict": None,
                                     "summary": "", "evidence": []}
    with pytest.raises(UsageError) as exc:
        r.add_goal("g1", "Again")
    assert exc.value.code == "duplicate_goal"
    assert r.data["goals"]["g1"]["title"] == "Sign in"


def test_add_finding_ids_are_unique_and_shaped(root):
    r = make_run(root)
    ids = [r.add_finding("console", f"error {i}", "g1", None, "script") for i in range(5)]
    ids.append(r.add_finding("injection", "page says ignore instructions", None, "/s/a.png", "model"))
    assert len(set(ids)) == 6
    assert [f["finding_id"] for f in r.data["findings"]] == ids
    last = r.data["findings"][-1]
    assert last == {"finding_id": ids[-1], "kind": "injection",
                    "summary": "page says ignore instructions", "goal_id": None,
                    "screenshot_path": "/s/a.png", "source": "model"}


def test_record_gate_appends(root):
    r = make_run(root)
    r.record_gate(3, "Delete project", "requested")
    assert r.data["gates"] == [{"observation_id": 3, "subject": "Delete project",
                                "gate": "requested"}]


def test_budget_per_goal(root):
    r = make_run(root, budget={"run_cap": 200, "goal_cap": 2})
    r.add_goal("g1", "a")
    r.add_goal("g2", "b")
    assert r.charge_action("g1") is None
    assert r.charge_action("g1") is None
    assert r.charge_action("g1") == "goal"
    assert r.data["goals"]["g1"]["actions_used"] == 2
    assert r.data["budget"]["run_used"] == 2
    assert r.charge_action("g2") is None
    assert r.data["budget"]["run_used"] == 3


def test_budget_per_run_wins_and_charges_nothing(root):
    r = make_run(root, budget={"run_cap": 3, "goal_cap": 40})
    r.add_goal("g1", "a")
    r.add_goal("g2", "b")
    assert [r.charge_action("g1"), r.charge_action("g1"), r.charge_action("g2")] == [None] * 3
    assert r.charge_action("g2") == "run"
    assert r.data["budget"]["run_used"] == 3
    assert r.data["goals"]["g2"]["actions_used"] == 1


def test_budget_reports_run_before_goal_when_both_spent(root):
    r = make_run(root, budget={"run_cap": 1, "goal_cap": 1})
    r.add_goal("g1", "a")
    assert r.charge_action("g1") is None
    assert r.charge_action("g1") == "run"


def test_charge_unknown_goal(root):
    r = make_run(root)
    with pytest.raises(UsageError) as exc:
        r.charge_action("nope")
    assert exc.value.code == "unknown_goal"
    assert r.data["budget"]["run_used"] == 0


@pytest.fixture
def lock(tmp_path, monkeypatch):
    path = tmp_path / "locks" / "desktop.lock"
    monkeypatch.setenv("LIKEUSER_LOCK_PATH", str(path))
    return run.DesktopLock()


def test_lock_path_from_env_and_default(tmp_path, monkeypatch):
    monkeypatch.setenv("LIKEUSER_LOCK_PATH", str(tmp_path / "x.lock"))
    assert run.DesktopLock().path == tmp_path / "x.lock"
    monkeypatch.delenv("LIKEUSER_LOCK_PATH")
    assert run.DesktopLock().path == (Path.home() / ".local" / "state" / "quirk"
                                      / "using-apps-like-a-user" / "desktop.lock")


def test_lock_acquire_records_holder(lock):
    assert lock.try_acquire("r1", "/proj") is None
    assert lock.replaced is None
    holder = lock.holder()
    assert holder["run_id"] == "r1" and holder["project"] == "/proj"
    datetime.strptime(holder["acquired_at"], ISO)
    datetime.strptime(holder["last_act_at"], ISO)


def test_lock_same_run_reacquires(lock):
    assert lock.try_acquire("r1", "/proj") is None
    first = lock.holder()["acquired_at"]
    assert lock.try_acquire("r1", "/proj") is None
    assert lock.replaced is None
    assert lock.holder()["acquired_at"] == first


def test_lock_second_run_gets_the_holder(lock):
    assert lock.try_acquire("r1", "/proj") is None
    got = lock.try_acquire("r2", "/other")
    assert got["run_id"] == "r1" and got["project"] == "/proj"
    assert lock.holder()["run_id"] == "r1"


def test_lock_acquire_busy_after_wait_carries_holder(lock):
    lock.try_acquire("r1", "/proj")
    now = [0.0]
    slept = []

    def clock():
        return now[0]

    def sleep(s):
        slept.append(s)
        now[0] += s

    with pytest.raises(RunStateError) as exc:
        lock.acquire("r2", "/other", wait_s=3.0, sleep=sleep, clock=clock)
    assert exc.value.code == "desktop_busy"
    assert exc.value.detail["run_id"] == "r1" and exc.value.detail["project"] == "/proj"
    assert slept and sum(slept) >= 3.0


def test_lock_acquire_succeeds_when_holder_releases_mid_wait(lock):
    lock.try_acquire("r1", "/proj")
    now = [0.0]

    def clock():
        return now[0]

    def sleep(s):
        now[0] += s
        lock.release("r1")

    assert lock.acquire("r2", "/other", wait_s=30.0, sleep=sleep, clock=clock) is None
    assert lock.holder()["run_id"] == "r2"


def test_lock_stale_holder_is_replaced_and_recorded(lock):
    lock.path.parent.mkdir(parents=True)
    old = {"run_id": "old", "project": "/p", "acquired_at": ago(60), "last_act_at": ago(16)}
    lock.path.write_text(json.dumps(old))
    assert lock.try_acquire("r2", "/other") is None
    assert lock.replaced == old
    assert lock.holder()["run_id"] == "r2"


def test_lock_fresh_holder_is_not_replaced(lock):
    lock.path.parent.mkdir(parents=True)
    live = {"run_id": "live", "project": "/p", "acquired_at": ago(60), "last_act_at": ago(14)}
    lock.path.write_text(json.dumps(live))
    assert lock.try_acquire("r2", "/other") == live


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '{"project": "/p"}',
                                     '{"run_id": "r0"}', '{"run_id": "r0", "last_act_at": "x"}'])
def test_lock_corrupt_record_fails_closed(lock, content):
    lock.path.parent.mkdir(parents=True)
    lock.path.write_text(content)
    held = lock.try_acquire("r1", "/p")
    assert held is not None and held["unreadable"] is True
    assert lock.holder()["unreadable"] is True
    assert lock.path.read_text() == content


def test_lock_corrupt_record_goes_stale_by_mtime(lock):
    lock.path.parent.mkdir(parents=True)
    lock.path.write_text("{not json")
    old = time.time() - 16 * 60
    os.utime(lock.path, (old, old))
    assert lock.try_acquire("r1", "/p") is None
    assert lock.replaced["unreadable"] is True
    assert lock.holder()["run_id"] == "r1"


def test_lock_corrupt_record_ignores_refresh_and_release(lock):
    lock.path.parent.mkdir(parents=True)
    lock.path.write_text("{not json")
    lock.refresh("unknown")
    lock.release("unknown")
    assert lock.path.read_text() == "{not json"


def test_lock_owns_is_true_only_while_the_holder_names_the_run(lock):
    assert lock.owns("r1") is False
    lock.acquire("r1", "/p", wait_s=1)
    assert lock.owns("r1") is True and lock.owns("r2") is False
    lock.release("r1")
    assert lock.owns("r1") is False


def test_lock_owns_is_false_for_an_unreadable_record(lock):
    lock.path.parent.mkdir(parents=True)
    lock.path.write_text("{not json")
    assert lock.owns("unknown") is False


def test_lock_refresh_moves_last_act(lock):
    lock.path.parent.mkdir(parents=True)
    mine = {"run_id": "r1", "project": "/p", "acquired_at": ago(30), "last_act_at": ago(10)}
    lock.path.write_text(json.dumps(mine))
    lock.refresh("r1")
    after = lock.holder()
    assert after["acquired_at"] == mine["acquired_at"]
    assert after["last_act_at"] > mine["last_act_at"]
    lock.refresh("someone-else")
    assert lock.holder() == after


def test_lock_release_by_holder_frees_it(lock):
    lock.try_acquire("r1", "/p")
    lock.release("r1")
    assert lock.holder() is None
    assert lock.try_acquire("r2", "/q") is None


def test_lock_release_by_non_holder_is_a_noop(lock):
    lock.try_acquire("r1", "/p")
    lock.release("r2")
    assert lock.holder()["run_id"] == "r1"
    DesktopLockFresh = run.DesktopLock(lock.path)
    DesktopLockFresh.release("r2")
    assert lock.holder()["run_id"] == "r1"


def test_lock_release_with_no_file_is_a_noop(lock):
    lock.release("r1")
    assert lock.holder() is None


RACER = """
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import _run
start = float(sys.argv[4])
while time.time() < start:
    pass
lock = _run.DesktopLock(Path(sys.argv[2]))
print("WIN" if lock.try_acquire(sys.argv[3], "proj") is None else "LOSE")
"""


def test_lock_is_atomic_across_processes(tmp_path):
    path = tmp_path / "race" / "desktop.lock"
    start = time.time() + 2.0
    procs = [subprocess.Popen([sys.executable, "-c", RACER, str(SCRIPTS), str(path), f"run-{i}",
                               str(start)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True) for i in range(4)]
    outs = []
    for p in procs:
        out, err = p.communicate(timeout=30)
        assert p.returncode == 0, err
        outs.append(out.strip())
    assert sorted(outs) == ["LOSE", "LOSE", "LOSE", "WIN"]


def test_credentials_from_env(monkeypatch):
    monkeypatch.setenv("LIKEUSER_USERNAME", "ann")
    monkeypatch.setenv("LIKEUSER_PASSWORD", "s3cret")
    assert run.load_credentials(None, None) == {"username": "ann", "password": "s3cret"}


def test_credentials_from_env_with_prefix(monkeypatch):
    monkeypatch.setenv("ACME_USERNAME", "bob")
    monkeypatch.setenv("ACME_PASSWORD", "pw")
    monkeypatch.delenv("LIKEUSER_USERNAME", raising=False)
    assert run.load_credentials("ACME", None) == {"username": "bob", "password": "pw"}


def test_credentials_missing_from_env(monkeypatch):
    monkeypatch.setenv("LIKEUSER_USERNAME", "ann")
    monkeypatch.delenv("LIKEUSER_PASSWORD", raising=False)
    with pytest.raises(MissingError) as exc:
        run.load_credentials(None, None)
    assert exc.value.missing == ["credentials"]


def test_credentials_from_a_0600_file(tmp_path, monkeypatch):
    monkeypatch.setenv("LIKEUSER_USERNAME", "env-user")
    monkeypatch.setenv("LIKEUSER_PASSWORD", "env-pw")
    f = tmp_path / "creds.json"
    f.write_text(json.dumps({"username": "file-user", "password": "file-pw"}))
    f.chmod(0o600)
    assert run.load_credentials(None, f) == {"username": "file-user", "password": "file-pw"}


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o604, 0o660])
def test_credentials_file_rejected_unless_0600(tmp_path, mode):
    f = tmp_path / "creds.json"
    f.write_text(json.dumps({"username": "u", "password": "p"}))
    f.chmod(mode)
    with pytest.raises(MissingError) as exc:
        run.load_credentials(None, f)
    assert exc.value.missing == ["credentials_file_mode"]


def test_credentials_file_with_missing_keys(tmp_path):
    f = tmp_path / "creds.json"
    f.write_text(json.dumps({"username": "u"}))
    f.chmod(0o600)
    with pytest.raises(MissingError) as exc:
        run.load_credentials(None, f)
    assert exc.value.missing == ["credentials"]


def test_credentials_file_symlink_refused(tmp_path):
    real = tmp_path / "real.json"
    real.write_text(json.dumps({"username": "u", "password": "p"}))
    real.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(MissingError) as exc:
        run.load_credentials(None, link)
    assert exc.value.missing == ["credentials_file"]


def test_credentials_file_missing_or_not_regular(tmp_path):
    for target in (tmp_path / "absent.json", tmp_path):
        with pytest.raises(MissingError) as exc:
            run.load_credentials(None, target)
        assert exc.value.missing == ["credentials_file"]


def test_credentials_mode_and_content_come_from_the_same_open_file(tmp_path, monkeypatch):
    """A pathname swap after the open must not change what is validated or read."""
    f = tmp_path / "creds.json"
    f.write_text(json.dumps({"username": "good", "password": "good-pw"}))
    f.chmod(0o600)
    swap = tmp_path / "swap.json"
    swap.write_text(json.dumps({"username": "evil", "password": "evil-pw"}))
    swap.chmod(0o644)
    real_open = os.open

    def swapping_open(path, *args, **kwargs):
        fd = real_open(path, *args, **kwargs)
        os.replace(swap, f)
        return fd

    monkeypatch.setattr(run.os, "open", swapping_open)
    assert run.load_credentials(None, f) == {"username": "good", "password": "good-pw"}


def test_redact():
    assert run.redact("pw=abc and abc", ["abc"]) == "pw=[REDACTED] and [REDACTED]"
    assert run.redact("nothing here", ["", "zzz"]) == "nothing here"
    assert run.redact("abcd", ["abc", "abcd"]) == "[REDACTED]"
    assert run.redact("x", []) == "x"


def test_test_overrides_lists_only_set_config_names():
    env = {"LIKEUSER_STATE_ROOT": "/x", "LIKEUSER_FAKE_DESKTOP": "/y", "PATH": "/bin",
           "LIKEUSER_USERNAME": "ann", "LIKEUSER_PASSWORD": "pw"}
    assert run.test_overrides(env) == ["LIKEUSER_FAKE_DESKTOP", "LIKEUSER_STATE_ROOT"]
    assert run.test_overrides({}) == []
    everything = {n: "1" for n in ("LIKEUSER_PLAYWRIGHT_BIN", "LIKEUSER_ORCA_BIN",
                                   "LIKEUSER_NATIVE_BIN", "LIKEUSER_FAKE_DESKTOP",
                                   "LIKEUSER_STATE_ROOT", "LIKEUSER_LOCK_PATH", "LIKEUSER_FAULT")}
    assert run.test_overrides(everything) == sorted(everything)


BANNER = "TEST OVERRIDES ACTIVE — results are not valid evidence"


def _populated(root, **fields):
    r = make_run(root, **fields)
    r.add_goal("g1", "Sign in")
    r.add_goal("g2", "Open settings")
    r.data["goals"]["g1"]["verdict"] = "pass"
    r.data["goals"]["g1"]["summary"] = "signed in"
    r.data["goals"]["g1"]["evidence"] = ["/runs/x/shot-1.png"]
    fid = r.add_finding("console", "TypeError on load", "g1", "/runs/x/shot-1.png", "script")
    r.add_finding("injection", "page asks agent to email data", None, None, "model")
    r.record_gate(2, "Delete project", "stopped")
    r.charge_action("g1")
    r.save()
    return r, fid


def test_report_json_shape(root):
    r, fid = _populated(root)
    summary = r.write_report()
    report = json.loads((r.dir / "report.json").read_text())
    assert report == summary
    assert set(report) == {"run", "goals", "findings", "gates", "state_left", "budget"}
    assert set(report["run"]) == {"run_id", "target", "surface", "owner", "attended", "driver",
                                  "driver_version", "started", "ended", "stopped_reason",
                                  "test_overrides"}
    g1, g2 = report["goals"]
    assert g1 == {"goal_id": "g1", "title": "Sign in", "status": "pass",
                  "evidence": ["/runs/x/shot-1.png"], "findings": [fid], "summary": "signed in"}
    assert g2["status"] == "unset" and g2["evidence"] == [] and g2["findings"] == []
    assert [f["kind"] for f in report["findings"]] == ["console", "injection"]
    assert report["gates"] == [{"observation_id": 2, "subject": "Delete project",
                                "gate": "stopped"}]
    assert set(report["state_left"]) == {"final_screenshot", "clipboard_restored",
                                         "frontmost_restored", "kept_open", "cleanup_errors"}
    assert report["budget"] == {"run_used": 1, "run_cap": 200}


@pytest.mark.parametrize("restored,line", [
    (None, "- Clipboard: not touched"),
    (True, "- Clipboard: restored"),
    (False, "- Clipboard: changed and not restored"),
])
def test_report_md_tells_untouched_from_restored_from_unrestored_clipboards(root, restored, line):
    r, _ = _populated(root)
    r.data["state_left"] = {"clipboard_restored": restored}
    summary = r.write_report()
    assert summary["state_left"]["clipboard_restored"] is restored
    assert line in (r.dir / "report.md").read_text(encoding="utf-8").splitlines()


def test_a_report_with_no_end_state_reads_the_clipboard_as_not_touched(root):
    r, _ = _populated(root)
    assert r.write_report()["state_left"]["clipboard_restored"] is None


def test_report_md_links_screenshots_and_has_no_banner_without_overrides(root):
    r, _ = _populated(root)
    r.write_report()
    md = (r.dir / "report.md").read_text(encoding="utf-8")
    assert BANNER not in md
    assert not md.startswith("TEST OVERRIDES")
    assert "(/runs/x/shot-1.png)" in md
    assert "Sign in" in md and "TypeError on load" in md and "Delete project" in md


def test_report_md_first_line_is_the_banner_with_overrides(root):
    r, _ = _populated(root, test_overrides=["LIKEUSER_FAKE_DESKTOP", "LIKEUSER_STATE_ROOT"])
    summary = r.write_report()
    md = (r.dir / "report.md").read_text(encoding="utf-8")
    assert md.splitlines()[0] == BANNER
    assert summary["run"]["test_overrides"] == ["LIKEUSER_FAKE_DESKTOP", "LIKEUSER_STATE_ROOT"]
    assert "LIKEUSER_FAKE_DESKTOP" in md


def test_report_redacts_secrets(root):
    r, _ = _populated(root)
    r.secrets.add("signed in")
    r.write_report()
    assert "signed in" not in (r.dir / "report.json").read_text()
    assert "signed in" not in (r.dir / "report.md").read_text()


HOSTILE = "boom\n# Heading\n[x](http://e) ![i](http://e) <img src=x>\r\nnext line"


def _finding_lines(md):
    return [line for line in md.splitlines() if re.match(r"- F\d+ ", line)]


def test_script_findings_cannot_make_structure_in_report_md(root):
    r = make_run(root)
    r.add_finding("console", f"console error: {HOSTILE}", None, None, "script")
    r.add_finding("network", "failed request: GET http://e/`x` -> 500", None, None, "script")
    r.write_report()
    md = (r.dir / "report.md").read_text(encoding="utf-8")
    assert "\n# Heading" not in md
    assert not any(line.startswith(("#", "![", "[", "<")) for line in md.splitlines()
                   if line and not line.startswith("# Run ") and not line.startswith("## ")
                   and not line.startswith("### "))
    [first, second] = _finding_lines(md)
    assert first == ("- F1 [console, script] ` console error: boom # Heading [x](http://e) "
                     "![i](http://e) <img src=x> next line `")
    assert second == "- F2 [network, script] `` failed request: GET http://e/`x` -> 500 ``"


def test_a_backtick_run_in_app_text_cannot_close_the_code_span(root):
    r = make_run(root)
    r.add_finding("console", "a ``` b `` c ` d\n# Heading", None, None, "script")
    r.write_report()
    [line] = _finding_lines((r.dir / "report.md").read_text(encoding="utf-8"))
    assert line == "- F1 [console, script] ```` a ``` b `` c ` d # Heading ````"


def test_agent_written_summaries_keep_their_markdown(root):
    r = make_run(root)
    r.add_finding("other", "the **save** button is `dead`", None, None, "model")
    r.write_report()
    [line] = _finding_lines((r.dir / "report.md").read_text(encoding="utf-8"))
    assert line == "- F1 [other, model] the **save** button is `dead`"


def test_gate_subjects_and_cleanup_errors_are_literal_in_report_md(root):
    r = make_run(root)
    r.record_gate(2, "Delete [x](http://e)\n# Heading", "stopped")
    r.data["state_left"] = {"cleanup_errors": ["quit pid:1: boom\n# Heading"],
                            "kept_open": ["pid:1"]}
    r.write_report()
    md = (r.dir / "report.md").read_text(encoding="utf-8")
    assert '- observation 2: stopped on ` Delete [x](http://e) # Heading `' in md
    assert "- Cleanup errors: ` quit pid:1: boom # Heading `" in md
    assert "\n# Heading" not in md


@pytest.mark.parametrize("subject", [
    "Submit", "Send", "Post", "Publish", "Share", "Pay now", "Buy", "Purchase", "Place order",
    "Checkout", "Subscribe", "Transfer funds", "Delete project", "Remove", "Deactivate",
    "Close account", "Confirm", "Authorize", "Authorise app", "Grant access", "Revoke",
    "Save changes", "Update password", "Update email", "Update payment method", "SEND",
])
def test_third_party_gate_positives(subject):
    assert run.gate_matches(subject, "third-party")


@pytest.mark.parametrize("subject", [
    "Settings", "Search", "Next", "Open menu", "Rejected items", "Sender name", "Reposted",
    "Close", "Cancel", "Profile", "Save", "Update",
])
def test_third_party_gate_negatives(subject):
    assert not run.gate_matches(subject, "third-party")


@pytest.mark.parametrize("subject", [
    "Delete project", "Remove", "Destroy", "Drop table", "Purge cache", "Wipe data",
    "Erase all", "DELETE",
])
def test_yours_gate_positives(subject):
    assert run.gate_matches(subject, "yours")


@pytest.mark.parametrize("subject", [
    "Save changes", "Send", "Post", "Close account", "Settings", "Submit", "Deleted items",
    "Reject all", "Rejected items", "Pay",
])
def test_yours_gate_negatives(subject):
    assert not run.gate_matches(subject, "yours")


def test_gate_matches_rejects_unknown_owner():
    with pytest.raises(UsageError):
        run.gate_matches("Delete", "nobody")


@pytest.mark.parametrize("name", [
    "Reject all", "reject", "Decline", "Necessary only", "Only necessary", "Essential only",
    "Not now", "Later", "No thanks", "Dismiss", "Close", "Maybe later", "Skip",
    "  Reject All  ", "SKIP",
])
def test_dismiss_allowed_positives(name):
    assert run.dismiss_allowed(name)


@pytest.mark.parametrize("name", [
    "Rejected items", "Accept all", "Close account", "Skip to content", "Delete", "",
    "Reject all cookies", "Not now, thanks", "Decline invitation",
])
def test_dismiss_allowed_negatives(name):
    assert not run.dismiss_allowed(name)
