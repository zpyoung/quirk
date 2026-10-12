"""Tests for skills/using-apps-like-a-user/scripts/likeuser.py.

Every test runs likeuser.py as a subprocess under the LIKEUSER_* overrides, against fake
playwright-cli and orca binaries built from the golden files and a fake desktop JSON. Nothing
here launches a real app or browser, or touches the real desktop, clipboard, or lock.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
import shlex
import stat
import sys
import threading
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "skills" / "using-apps-like-a-user" / "scripts"
FAKES = REPO / "tests" / "fixtures" / "using-apps-like-a-user" / "fakes"
for entry in (str(SCRIPTS), str(FAKES)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import harness  # noqa: E402
from harness import (  # noqa: E402
    FIXTURE_BUNDLE, NATIVE_SHEET_TREE, NATIVE_TREE, NATIVE_WORKING_TREE, USER_APP,
    golden_yaml, home_pages, web_page,
)

import _run  # noqa: E402
from _types import Observation  # noqa: E402

SECRET_PASSWORD = "s3cret-Pa55w0rd"
SECRET_USER = "alice-the-tester"
TYPED_TEXT = "typed-sentinel-text-42"
ALL_FILE_NAMES = ("events.jsonl", "run.json", "report.json", "report.md")


@pytest.fixture
def sb(tmp_path):
    sandbox = harness.Sandbox(tmp_path)
    yield sandbox
    sandbox.kill_launched()


def click_rule(ref, page="counted", **extra):
    rule = {"on": ["click", ref], "page": page}
    rule.update(extra)
    return rule


def write_goals(sb, *goal_ids):
    path = sb.tmp / "goals.json"
    path.write_text(json.dumps([{"id": g, "title": f"goal {g}"} for g in goal_ids]))
    return str(path)


def start(sb, surface="web", owner="yours", attended=True, goals=("g1",), observe=True,
          begin_args=(), **env):
    """Begin a run with goals and (by default) take the first observation; return (run id, obs)."""
    result = sb.begin(surface, None, owner, attended, "--goals-file", write_goals(sb, *goals),
                      *begin_args, **env)
    assert result.code == 0, result.stdout + result.stderr
    run_id = result["run_id"]
    if not observe:
        return run_id, None
    seen = sb.run("observe", "--run", run_id, "--goal", goals[0], **env)
    assert seen.code == 0, seen.stdout + seen.stderr
    return run_id, seen["observation"]


def act(sb, run_id, obs_id, *args, stdin=None, **env):
    return sb.run("act", "--run", run_id, "--obs", str(obs_id), *args, stdin=stdin, **env)


def click(sb, run_id, obs_id, ref, *args, **env):
    return act(sb, run_id, obs_id, "--action", "click", "--ref", ref, *args, **env)


def web_run(sb, rules=None, pages=None, owner="yours", attended=True, goals=("g1",),
            begin_args=(), observe=True, **scenario):
    sb.web_scenario(pages, rules=rules or [], **scenario)
    return start(sb, "web", owner, attended, goals, observe=observe, begin_args=begin_args)


def native_run(sb, rules=None, pages=None, owner="yours", attended=True, goals=("g1",),
               begin_args=(), **scenario):
    sb.native_scenario(pages, rules=rules or [], **scenario)
    return start(sb, "native", owner, attended, goals, begin_args=begin_args)


def electron_command(port=None):
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(FAKES / 'fake_electron.py'))}"


def electron_run(sb, orca_pages=None, orca_start="idle", rules=None, pw_rules=None,
                 goals=("g1",), owner="yours", attended=True, **scenario):
    sb.web_scenario(rules=pw_rules or [])
    sb.native_scenario(orca_pages, start=orca_start, rules=rules or [],
                       bundle="com.github.Electron", **scenario)
    port = harness.free_port()
    return start(sb, "electron", owner, attended, goals,
                 begin_args=("--launch", electron_command(), "--cdp-port", str(port),
                             "--allow-foreground"))


def load_cli_module():
    spec = importlib.util.spec_from_file_location("likeuser_under_test", SCRIPTS / "likeuser.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_in_order(names, wanted):
    """Assert `wanted` appears in `names` as an ordered subsequence."""
    remaining = iter(names)
    assert all(any(name == item for item in remaining) for name in wanted), (names, wanted)


def private_port_block(size):
    """Return a `range` of `size` consecutive free loopback ports, chosen at random.

    The port lock is per sandbox, so concurrent test processes would otherwise race for the
    default CDP range and fail each other's fake app launches.
    """
    import random
    import socket

    while True:
        first = random.randrange(20000, 45000)
        probes = []
        try:
            for port in range(first, first + size):
                probe = socket.socket()
                probes.append(probe)
                probe.bind(("127.0.0.1", port))
        except OSError:
            continue
        finally:
            for probe in probes:
                probe.close()
        return range(first, first + size)


def pids_alive(sb):
    alive = []
    for path in sb.state_root.glob("runs/*/run.json"):
        for entry in json.loads(path.read_text()).get("launched", []):
            kind, _, ident = entry["id"].partition(":")
            if kind == "pid":
                try:
                    os.kill(int(ident), 0)
                    alive.append(int(ident))
                except ProcessLookupError:
                    pass
    return alive


class TestCliSurface:
    def test_help_lists_every_subcommand(self, sb):
        proc = sb.raw("--help")
        assert proc.returncode == 0
        for name in ("doctor", "begin", "goal", "observe", "act", "note", "verdict",
                     "handoff", "resume", "end"):
            assert name in proc.stdout

    def test_argparse_errors_exit_2_with_one_json_object(self, sb):
        result = sb.run("observe", "--run", "x")
        assert result.code == 2
        assert result["ok"] is False and result["error"] == "bad_arguments"

    def test_unknown_subcommand_exits_2(self, sb):
        assert sb.run("frobnicate").code == 2

    def test_unknown_run_exits_3(self, sb):
        result = sb.run("observe", "--run", "nope", "--goal", "g1")
        assert result.code == 3
        assert result["error"] == "unknown_run"

    def test_unknown_fault_name_exits_2(self, sb):
        result = sb.run("doctor", "--surface", "web", LIKEUSER_FAULT="skip_everything")
        assert result.code == 2 and result["error"] == "unknown_fault"

    def test_internal_error_exits_1_with_traceback_on_stderr(self, sb):
        sb.web_scenario()
        run_id, _ = start(sb, observe=False)
        state = sb.run_json(run_id)
        del state["observations"]
        sb.write_run_json(run_id, state)
        result = sb.run("observe", "--run", run_id, "--goal", "g1")
        assert result.code == 1
        assert result["error"] == "internal_error"
        assert "Traceback" in result.stderr

    def test_driver_failure_outside_act_exits_4_with_driver_error(self, sb):
        run_id, _ = web_run(sb, observe=False, errors=[{"on": ["snapshot"],
                                                         "stdout": "### Error\nboom\n",
                                                         "returncode": 0}])
        result = sb.run("observe", "--run", run_id, "--goal", "g1")
        assert result.code == 4
        assert result["error"] == "driver_error" and result["driver_error"] == "playwright_error"

    def test_missing_tool_exits_5_naming_it(self, sb):
        sb.web_scenario()
        result = sb.begin("web", LIKEUSER_PLAYWRIGHT_BIN=str(sb.tmp / "nope"))
        assert result.code == 5
        assert "playwright-cli" in result["missing"]
        assert not list(sb.state_root.glob("runs/*"))


class TestDoctor:
    def test_web_reports_the_tool_version_and_pin(self, sb):
        sb.web_scenario()
        result = sb.run("doctor", "--surface", "web")
        assert result.code == 0 and result["ok"] is True
        tool = result["surfaces"]["web"]["tools"][0]
        assert tool["name"] == "playwright-cli" and tool["version"] == "0.1.22"
        assert tool["pin"] == "0.1.22"

    def test_old_playwright_version_exits_5(self, sb):
        sb.web_scenario(version="0.1.1")
        result = sb.run("doctor", "--surface", "web")
        assert result.code == 5
        assert any("0.1.22" in item for item in result["missing"])

    def test_native_needs_both_macos_permissions(self, sb):
        sb.native_scenario()
        sb.set_desktop(permissions={"accessibility": False, "screen_recording": False})
        result = sb.run("doctor", "--surface", "native")
        assert result.code == 5
        assert "macOS permission: Accessibility" in result["missing"]
        assert "macOS permission: Screen Recording" in result["missing"]

    def test_without_a_surface_it_covers_all_three(self, sb):
        sb.web_scenario()
        sb.native_scenario()
        result = sb.run("doctor")
        assert result.code == 0
        assert set(result["surfaces"]) == {"web", "electron", "native"}
        assert result["surfaces"]["native"]["permissions"] == {
            "accessibility": True, "screen_recording": True}

    def test_the_sandbox_pins_the_native_driver_binary_to_a_missing_path(self, sb):
        pinned = Path(sb.env()["LIKEUSER_NATIVE_BIN"])
        assert not pinned.exists()
        assert str(sb.tmp) in str(pinned)

    def test_native_reports_the_orca_binary_with_no_pin(self, sb):
        sb.native_scenario()
        result = sb.run("doctor", "--surface", "native")
        tool = result["surfaces"]["native"]["tools"][0]
        assert tool["name"] == "orca" and tool["path"] == sb.env()["LIKEUSER_ORCA_BIN"]
        assert tool["pin"] is None

    def test_a_selected_cua_driver_reports_its_own_binary_and_pin(self, sb, monkeypatch):
        import _native

        class StandInCua(_native.CuaDriver):
            version = "0.34.1"

            def check(self):
                return []

        for key, value in sb.env().items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("LIKEUSER_NATIVE_BIN", "/fake/cua-driver")
        monkeypatch.setenv("LIKEUSER_ORCA_BIN", "/fake/orca")
        module = load_cli_module()
        monkeypatch.setattr(module, "get_native_driver", lambda name=None, session=None: StandInCua())
        for surface in ("native", "electron"):
            [tool] = module._surface_report(surface)[0]["tools"][-1:]
            assert tool == {"name": "cua", "path": "/fake/cua-driver", "version": "0.34.1", "pin": "0.34.1"}

    def test_missing_orca_is_reported(self, sb):
        sb.native_scenario()
        result = sb.run("doctor", "--surface", "native", LIKEUSER_ORCA_BIN=str(sb.tmp / "no-orca"))
        assert result.code == 5 and "orca" in result["missing"]


class TestBegin:
    def test_creates_the_run_folder_baseline_and_goals(self, sb):
        sb.web_scenario()
        result = sb.begin("web", None, "yours", True, "--goals-file", write_goals(sb, "g1", "g2"))
        assert result.code == 0
        run_id = result["run_id"]
        assert (sb.state_root / ".gitignore").read_text() == "*\n"
        state = sb.run_json(run_id)
        assert state["baseline"] == {"frontmost": USER_APP, "cursor": [100.0, 200.0],
                                     "clipboard_change_count": 3, "clipboard_text_only": True}
        assert state["drift_baseline"]["frontmost"] == USER_APP
        assert set(state["goals"]) == {"g1", "g2"}
        assert state["window"]["session"] == run_id
        clip = sb.run_dir(run_id) / "clipboard.txt"
        assert clip.read_text() == "users clipboard"
        assert stat.S_IMODE(clip.stat().st_mode) == 0o600

    def test_opens_a_session_named_after_the_run_from_the_run_folder(self, sb):
        sb.web_scenario()
        run_id = sb.begin("web", "http://127.0.0.1:64361/")["run_id"]
        opens = [c for c in sb.pw_calls() if c["argv"][:1] == ["open"]]
        assert opens[0]["argv"] == ["open", "http://127.0.0.1:64361/"]
        assert opens[0]["session"] == run_id
        assert os.path.realpath(opens[0]["cwd"]) == os.path.realpath(str(sb.run_dir(run_id)))

    def test_a_clipboard_that_is_not_text_only_saves_nothing(self, sb):
        sb.web_scenario()
        sb.set_desktop(clipboard_text_only=False)
        run_id = sb.begin("web")["run_id"]
        assert not (sb.run_dir(run_id) / "clipboard.txt").exists()
        assert sb.run_json(run_id)["baseline"]["clipboard_text_only"] is False

    def test_budgets_come_from_the_flags(self, sb):
        sb.web_scenario()
        run_id = sb.begin("web", None, "yours", True, "--budget-run", "7", "--budget-goal", "3")["run_id"]
        assert sb.run_json(run_id)["budget"] == {"run_cap": 7, "goal_cap": 3, "run_used": 0}

    def test_bad_goals_file_exits_2_before_any_run_exists(self, sb):
        sb.web_scenario()
        bad = sb.tmp / "goals.json"
        bad.write_text("{not json")
        result = sb.begin("web", None, "yours", True, "--goals-file", str(bad))
        assert result.code == 2 and result["error"] == "bad_goals_file"
        assert not list(sb.state_root.glob("runs/*"))

    def test_electron_without_launch_exits_2(self, sb):
        sb.web_scenario()
        sb.native_scenario()
        result = sb.begin("electron")
        assert result.code == 2 and result["error"] == "launch_required"

    def test_native_without_allow_foreground_exits_2(self, sb):
        sb.native_scenario()
        result = sb.run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native",
                        "--owner", "yours", "--attended")
        assert result.code == 2 and result["error"] == "foreground_not_allowed"

    def test_electron_without_allow_foreground_exits_2_while_the_native_driver_needs_the_foreground(self, sb):
        sb.web_scenario()
        sb.native_scenario(bundle="com.github.Electron")
        result = sb.begin("electron", None, "yours", True, "--launch", electron_command())
        assert result.code == 2 and result["error"] == "foreground_not_allowed"
        assert not list(sb.state_root.glob("runs/*"))
        assert pids_alive(sb) == []

    @pytest.mark.parametrize("surface", ["native", "electron"])
    @pytest.mark.parametrize("background_capable", [False, True])
    def test_allow_foreground_is_required_only_for_a_driver_that_is_not_background_capable(
            self, sb, monkeypatch, capsys, surface, background_capable):
        import _native

        class FakeDriver(_native.OrcaDriver):
            pass

        FakeDriver.background_capable = background_capable
        sb.web_scenario()
        sb.native_scenario(bundle=FIXTURE_BUNDLE if surface == "native" else "com.github.Electron")
        for key, value in sb.env().items():
            monkeypatch.setenv(key, value)
        module = load_cli_module()
        monkeypatch.setattr(module, "get_native_driver", lambda name=None, session=None: FakeDriver())
        target = FIXTURE_BUNDLE if surface == "native" else "app"
        argv = ["begin", "--target", target, "--surface", surface, "--owner", "yours", "--attended"]
        if surface == "electron":
            argv += ["--launch", electron_command(), "--cdp-port", str(harness.free_port())]
        code = module.main(argv)
        out = json.loads(capsys.readouterr().out)
        if background_capable:
            assert code == 0, out
            assert out["holds_lock"] is False
        else:
            assert code == 2 and out["error"] == "foreground_not_allowed"
        sb.kill_launched()

    def test_launch_flag_is_for_electron_only(self, sb):
        sb.web_scenario()
        result = sb.begin("web", None, "yours", True, "--launch", "echo")
        assert result.code == 2

    def test_failure_to_open_the_session_exits_4_and_ends_the_run(self, sb):
        sb.web_scenario(errors=[{"on": ["open"], "stdout": "### Error\nbrowser failed\n"}])
        result = sb.begin("web")
        assert result.code == 4 and result["driver_error"] == "playwright_error"
        [run_json] = list(sb.state_root.glob("runs/*/run.json"))
        state = json.loads(run_json.read_text())
        assert state["ended"] and state["stopped_reason"] == "begin_failed"

    def test_a_begin_that_fails_after_the_session_opened_closes_it_and_removes_the_clipboard_copy(self, sb):
        sb.web_scenario(errors=[{"on": ["goto"], "stdout": "### Error\nnavigation failed\n"}])
        saved = sb.state_root / "sessions" / "demo.json"
        saved.parent.mkdir(parents=True)
        saved.write_text("{}")
        result = sb.begin("web", "http://127.0.0.1:64361/", "yours", True, "--session-key", "demo")
        assert result.code == 4
        [run_dir] = list(sb.state_root.glob("runs/*"))
        assert sb.pw_argvs("close") != []
        assert not (run_dir / "clipboard.txt").exists()
        state = json.loads((run_dir / "run.json").read_text())
        assert state["ended"] and state["holds_lock"] is False

    def test_a_native_begin_that_fails_removes_the_clipboard_copy(self, sb, monkeypatch, capsys):
        sb.native_scenario()
        for key, value in sb.env().items():
            monkeypatch.setenv(key, value)
        module = load_cli_module()

        def fail(*args):
            raise module.DriverError("window_not_found", "no window")

        monkeypatch.setattr(module, "_begin_native", fail)
        code = module.main(["begin", "--target", FIXTURE_BUNDLE, "--surface", "native",
                            "--owner", "yours", "--attended", "--allow-foreground"])
        capsys.readouterr()
        assert code == 4
        [run_dir] = list(sb.state_root.glob("runs/*"))
        assert not (run_dir / "clipboard.txt").exists()

    def test_real_chrome_without_the_extension_exits_5(self, sb):
        sb.web_scenario(errors=[{"on": ["attach"], "stdout": "### Error\nno extension\n"}])
        result = sb.begin("web", None, "yours", True, "--real-chrome")
        assert result.code == 5
        assert any("extension" in item for item in result["missing"])

    def test_real_chrome_attaches_instead_of_opening(self, sb):
        sb.web_scenario()
        assert sb.begin("web", None, "yours", True, "--real-chrome").code == 0
        assert sb.pw_argvs("attach") == [["attach", "--extension=chrome"]]
        assert sb.pw_argvs("open") == []

    def test_saved_session_is_loaded_with_state_load_before_navigating(self, sb):
        sb.web_scenario()
        saved = sb.state_root / "sessions" / "demo.json"
        saved.parent.mkdir(parents=True)
        saved.write_text("{}")
        result = sb.begin("web", "http://127.0.0.1:64361/", "yours", True, "--session-key", "demo")
        assert result.code == 0 and result["session_loaded"] is True
        order = [a[0] for a in sb.pw_argvs() if a[0] in ("open", "state-load", "goto")]
        assert order == ["open", "state-load", "goto"]
        assert sb.pw_argvs("state-load") == [["state-load", str(saved)]]

    def test_missing_saved_session_just_opens(self, sb):
        sb.web_scenario()
        result = sb.begin("web", None, "yours", True, "--session-key", "demo")
        assert result["session_loaded"] is False
        assert sb.pw_argvs("state-load") == []

    def test_a_0644_credentials_file_exits_5_and_creates_no_run(self, sb):
        sb.web_scenario()
        creds = sb.tmp / "creds.json"
        creds.write_text(json.dumps({"username": SECRET_USER, "password": SECRET_PASSWORD}))
        creds.chmod(0o644)
        result = sb.begin("web", None, "yours", True, "--credentials-file", str(creds))
        assert result.code == 5 and result["missing"] == ["credentials_file_mode"]
        assert not list(sb.state_root.glob("runs/*"))

    def test_missing_credentials_env_exits_5(self, sb):
        sb.web_scenario()
        result = sb.begin("web", None, "yours", True, "--credentials-env", "NOPE")
        assert result.code == 5 and result["missing"] == ["credentials"]

    def test_test_overrides_are_recorded_and_bannered_on_stderr(self, sb):
        sb.web_scenario()
        result = sb.begin("web", LIKEUSER_FAULT="skip_gate")
        assert "TEST OVERRIDES ACTIVE" in result.stderr
        assert "LIKEUSER_FAULT" in result["test_overrides"]
        assert "LIKEUSER_FAULT" in sb.run_json(result["run_id"])["test_overrides"]


class TestDesktopLock:
    def test_native_begin_takes_the_lock_and_end_releases_it(self, sb):
        run_id, _ = native_run(sb)
        lock = _run.DesktopLock(sb.lock_path)
        assert lock.holder()["run_id"] == run_id
        assert sb.run_json(run_id)["holds_lock"] is True
        assert sb.run("end", "--run", run_id).code == 0
        assert lock.holder() is None

    def test_a_busy_desktop_at_begin_exits_3_with_the_holder(self, sb, monkeypatch, capsys):
        sb.native_scenario()
        _run.DesktopLock(sb.lock_path).try_acquire("other-run", "/other/project")
        for key, value in sb.env().items():
            monkeypatch.setenv(key, value)
        module = load_cli_module()
        monkeypatch.setattr(module, "LOCK_WAIT_S", 0.3)
        code = module.main(["begin", "--target", FIXTURE_BUNDLE, "--surface", "native",
                            "--owner", "yours", "--attended", "--allow-foreground"])
        out = json.loads(capsys.readouterr().out)
        assert code == 3
        assert out["error"] == "desktop_busy"
        assert out["holder"] == {"run_id": "other-run", "project": "/other/project"}

    def test_a_stale_holder_is_replaced_and_the_takeover_logged(self, sb):
        sb.native_scenario()
        lock = _run.DesktopLock(sb.lock_path)
        lock.try_acquire("old-run", "/old")
        old = json.loads(sb.lock_path.read_text())
        old["last_act_at"] = "2020-01-01T00:00:00Z"
        sb.lock_path.write_text(json.dumps(old))
        run_id = sb.begin("native", FIXTURE_BUNDLE, "yours", True, "--allow-foreground")["run_id"]
        assert lock.holder()["run_id"] == run_id
        assert any(e["verb"] == "lock_takeover" for e in sb.events(run_id))

    @pytest.mark.parametrize("refusal", ["stale", "budget", "stopped"])
    def test_a_refused_act_still_refreshes_the_held_lock(self, sb, refusal):
        begin_args = ("--budget-run", "1") if refusal == "budget" else ()
        run_id, obs = native_run(sb, begin_args=begin_args)
        if refusal == "budget":
            click(sb, run_id, obs["observation_id"], "2", "--foreground")
            obs = {"observation_id": sb.run_json(run_id)["latest_observation_id"]}
        if refusal == "stopped":
            state = sb.run_json(run_id)
            state["stopped_reason"] = "drift"
            (sb.run_dir(run_id) / "run.json").write_text(json.dumps(state))
        record = json.loads(sb.lock_path.read_text())
        record["last_act_at"] = "2020-01-01T00:00:00Z"
        sb.lock_path.write_text(json.dumps(record))
        wrong_obs = obs["observation_id"] + (5 if refusal == "stale" else 0)
        result = click(sb, run_id, wrong_obs, "2", "--foreground")
        assert result.status == {"stale": "STALE", "budget": "BUDGET_EXHAUSTED", "stopped": "DRIFT"}[refusal]
        refreshed = json.loads(sb.lock_path.read_text())
        assert refreshed["run_id"] == run_id and refreshed["last_act_at"] != "2020-01-01T00:00:00Z"

    def test_foreground_act_in_a_web_run_is_desktop_busy_while_another_run_holds_it(self, sb):
        run_id, obs = web_run(sb, rules=[click_rule("e4")])
        _run.DesktopLock(sb.lock_path).try_acquire("other-run", "/other")
        result = click(sb, run_id, obs["observation_id"], "e4", "--foreground")
        assert result.code == 0 and result.status == "DESKTOP_BUSY"
        assert result["holder"]["run_id"] == "other-run"
        assert sb.pw_argvs("click") == []

    def test_foreground_act_takes_the_lock_and_end_releases_it(self, sb):
        run_id, obs = web_run(sb, rules=[click_rule("e4")])
        assert click(sb, run_id, obs["observation_id"], "e4", "--foreground").status == "OBSERVED"
        assert _run.DesktopLock(sb.lock_path).holder()["run_id"] == run_id
        sb.run("end", "--run", run_id)
        assert _run.DesktopLock(sb.lock_path).holder() is None

    def test_unattended_foreground_without_allow_foreground_exits_2(self, sb):
        run_id, obs = web_run(sb, attended=False)
        result = click(sb, run_id, obs["observation_id"], "e4", "--foreground")
        assert result.code == 2 and result["error"] == "foreground_not_allowed"

    def test_unattended_foreground_is_fine_after_allow_foreground(self, sb):
        run_id, obs = web_run(sb, attended=False, rules=[click_rule("e4")],
                              begin_args=("--allow-foreground",))
        result = click(sb, run_id, obs["observation_id"], "e4", "--foreground")
        assert result.status == "OBSERVED"


class TestObserve:
    def test_writes_the_tree_screenshot_and_ids_into_the_run_folder(self, sb):
        run_id, obs = web_run(sb)
        assert obs["observation_id"] == 1 and obs["goal_id"] == "g1"
        assert Path(obs["screenshot_path"]).is_file()
        assert Path(obs["tree_path"]).read_text() == golden_yaml()
        assert obs["tree_chars"] == len(golden_yaml())
        assert obs["tree_truncated"] is False and obs["tree_sparse"] is False
        assert obs["screenshot_source"] == "renderer" and obs["scale"] == 1.0
        assert obs["url"] == "http://127.0.0.1:64361/" and obs["focus"] == "e1"
        second = sb.run("observe", "--run", run_id, "--goal", "g1")
        assert second["observation"]["observation_id"] == 2

    def test_no_screenshot_skips_it(self, sb):
        run_id, _ = web_run(sb)
        seen = sb.run("observe", "--run", run_id, "--goal", "g1", "--no-screenshot")
        assert seen["observation"]["screenshot_path"] is None
        assert seen["observation"]["screenshot_source"] is None
        assert sb.pw_argvs("screenshot")[-1][1].endswith("obs-1.png")
        assert len(sb.pw_argvs("screenshot")) == 1

    def test_requires_a_registered_goal(self, sb):
        run_id, _ = web_run(sb)
        result = sb.run("observe", "--run", run_id, "--goal", "ghost")
        assert result.code == 2 and result["error"] == "unknown_goal"

    def test_goal_registration_rejects_duplicates(self, sb):
        run_id, _ = web_run(sb)
        assert sb.run("goal", "--run", run_id, "--id", "g2", "--title-stdin", stdin="Second").code == 0
        again = sb.run("goal", "--run", run_id, "--id", "g2", "--title-stdin", stdin="Second")
        assert again.code == 2 and again["error"] == "duplicate_goal"

    def test_native_surface_copies_the_screenshot_into_the_run_and_keeps_its_scale(self, sb):
        run_id, obs = native_run(sb)
        assert obs["screenshot_source"] == "native" and obs["scale"] == 2.0
        assert Path(obs["screenshot_path"]).parent == sb.run_dir(run_id)
        assert "standard window UALA Fixture" in Path(obs["tree_path"]).read_text()
        begin_calls = sb.orca_commands("get-app-state")
        assert "--window-id" in begin_calls[-1]["argv"]

    def test_a_tree_the_driver_truncated_says_so(self, sb):
        pages = {"idle": {"tree": NATIVE_TREE, "title": "UALA Fixture", "truncated": True}}
        _, obs = native_run(sb, pages=pages)
        assert obs["tree_truncated"] is True

    def test_a_sparse_native_tree_is_flagged(self, sb):
        sparse = {"idle": {"tree": 'App=x (pid 1)\n\n0 standard window X\n\t1 web area\n\t2 close button',
                           "title": "X"}}
        run_id, obs = native_run(sb, pages=sparse)
        assert obs["tree_sparse"] is True


class TestEffectStatuses:
    def test_observed_lists_every_changed_signal(self, sb):
        run_id, obs = web_run(sb, rules=[click_rule("e4")])
        result = click(sb, run_id, obs["observation_id"], "e4")
        assert result.code == 0 and result.status == "OBSERVED"
        assert result["signals"] == ["tree", "focus"]
        assert result["observation"]["observation_id"] == 2
        assert result["driver_error"] is None and result["driver_verified"] is None

    def test_a_dead_button_is_no_effect(self, sb):
        run_id, obs = web_run(sb)
        assert click(sb, run_id, obs["observation_id"], "e7").status == "NO_EFFECT"

    def test_expect_narrows_and_other_changes_report_the_rest(self, sb):
        run_id, obs = web_run(sb, rules=[click_rule("e4")])
        narrow = click(sb, run_id, obs["observation_id"], "e4", "--expect", "url")
        assert narrow.status == "NO_EFFECT"
        assert narrow["signals"] == ["tree", "focus"] and narrow["other_changes"] == ["tree", "focus"]

    def test_expect_tree_is_observed_with_focus_as_the_other_change(self, sb):
        run_id, obs = web_run(sb, rules=[click_rule("e4")])
        result = click(sb, run_id, obs["observation_id"], "e4", "--expect", "tree")
        assert result.status == "OBSERVED" and result["other_changes"] == ["focus"]

    def test_unsettled_when_the_page_keeps_changing(self, sb):
        flip_a = golden_yaml().replace("Count: 0", "Count: 7")
        pages = {"a": web_page(flip_a, next_on_snapshot="b"),
                 "b": web_page(golden_yaml(), next_on_snapshot="a")}
        run_id, obs = web_run(sb, pages=pages, start="a")
        result = click(sb, run_id, obs["observation_id"], "e7")
        assert result.status == "UNSETTLED"

    def test_stale_observation_id_does_not_act(self, sb):
        run_id, obs = web_run(sb, rules=[click_rule("e4")])
        assert click(sb, run_id, obs["observation_id"], "e4").status == "OBSERVED"
        clicks = len(sb.pw_argvs("click"))
        again = click(sb, run_id, obs["observation_id"], "e4")
        assert again.status == "STALE"
        assert len(sb.pw_argvs("click")) == clicks

    def test_a_ref_absent_from_the_latest_observation_is_stale(self, sb):
        run_id, obs = web_run(sb)
        assert click(sb, run_id, obs["observation_id"], "e999").status == "STALE"
        assert sb.pw_argvs("click") == []

    def test_a_stale_ref_on_a_gated_target_is_stale_not_gate_required(self, sb):
        run_id, obs = web_run(sb, owner="third-party", rules=[click_rule("e4")])
        click(sb, run_id, obs["observation_id"], "e4")
        result = click(sb, run_id, obs["observation_id"], "e17")
        assert result.status == "STALE"
        assert sb.run_json(run_id)["gates"] == []

    def test_a_driver_error_is_error_and_never_observed(self, sb):
        run_id, obs = web_run(sb, rules=[{"on": ["click", "e4"], "error": "boom"}])
        result = click(sb, run_id, obs["observation_id"], "e4")
        assert result.code == 0 and result.status == "ERROR"
        assert result["driver_error"] == "playwright_error" and result["signals"] == []

    def test_an_error_block_with_exit_zero_is_still_error(self, sb):
        run_id, obs = web_run(sb, rules=[{"on": ["click", "e4"], "error": "boom", "returncode": 0}])
        assert click(sb, run_id, obs["observation_id"], "e4").status == "ERROR"

    def test_a_native_driver_error_is_error(self, sb):
        run_id, obs = native_run(sb, rules=[{"cmd": "click", "error": "element_not_found"}])
        result = click(sb, run_id, obs["observation_id"], "2", "--foreground")
        assert result.status == "ERROR" and result["driver_error"] == "element_not_found"

    def test_a_vanished_native_window_is_stale(self, sb):
        run_id, obs = native_run(sb, rules=[{"cmd": "click", "error": "window_not_found"}])
        assert click(sb, run_id, obs["observation_id"], "2", "--foreground").status == "STALE"

    def test_the_screen_signal_counts_when_the_screenshot_changes(self, sb):
        png_dir = harness.PNG_DIR
        pages = {"home": web_page(png=str(png_dir / "gradient.png")),
                 "counted": web_page(png=str(png_dir / "gradient_inverted.png"))}
        run_id, obs = web_run(sb, pages=pages, rules=[click_rule("e7")])
        result = click(sb, run_id, obs["observation_id"], "e7", "--expect", "screen")
        assert result.status == "OBSERVED" and "screen" in result["signals"]

    def test_driver_verified_never_yields_observed_by_itself(self, sb):
        run_id, obs = native_run(sb, rules=[{"cmd": "click", "verification": "verified"}])
        result = click(sb, run_id, obs["observation_id"], "3", "--foreground")
        assert result.status == "NO_EFFECT" and result["driver_verified"] is True

    def test_native_click_with_a_changed_tree_is_observed(self, sb):
        run_id, obs = native_run(sb, rules=[
            {"cmd": "click", "opts": {"--element-index": "2"}, "page": "working"}])
        result = click(sb, run_id, obs["observation_id"], "2", "--foreground")
        assert result.status == "OBSERVED" and result["signals"][0] == "tree"
        assert result["driver_verified"] is False
        click_call = sb.orca_commands("click")[0]["argv"]
        assert click_call[click_call.index("--element-index") + 1] == "2"

    def test_the_value_signal_tracks_the_targets_value(self, sb):
        typed = golden_yaml().replace('textbox "Notes" [ref=e10]', 'textbox "Notes" [ref=e10]: hello')
        pages = {"home": web_page(), "counted": web_page(typed)}
        run_id, obs = web_run(sb, pages=pages, rules=[
            {"on": ["fill", "e10"], "page": "counted"}])
        result = act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", "e10",
                     "--text-stdin", "--expect", "value", stdin="hello")
        assert result.status == "OBSERVED" and "value" in result["signals"]


class TestForegroundAndDrift:
    def test_native_actions_need_the_foreground_flag(self, sb):
        run_id, obs = native_run(sb)
        result = click(sb, run_id, obs["observation_id"], "2")
        assert result.status == "FOREGROUND_REQUIRED"
        assert sb.orca_commands("click") == []

    def test_the_cursor_moving_stops_the_run_and_the_stop_persists(self, sb):
        run_id, obs = native_run(sb)
        sb.set_desktop(cursor=[400.0, 200.0])
        result = click(sb, run_id, obs["observation_id"], "2", "--foreground")
        assert result.status == "DRIFT" and result["stopped_reason"] == "drift"
        assert sb.orca_commands("click") == []
        sb.set_desktop(cursor=[100.0, 200.0])
        again = click(sb, run_id, obs["observation_id"], "2", "--foreground")
        assert again.status == "DRIFT"
        assert sb.run_json(run_id)["stopped_reason"] == "drift"

    def test_a_stopped_run_refuses_observe_with_exit_3(self, sb):
        run_id, obs = native_run(sb)
        sb.set_desktop(frontmost="com.example.intruder")
        assert click(sb, run_id, obs["observation_id"], "2", "--foreground").status == "DRIFT"
        result = sb.run("observe", "--run", run_id, "--goal", "g1")
        assert result.code == 3 and result["stopped_reason"] == "drift"

    def test_a_stopped_run_still_takes_verdicts_and_ends_with_the_reason(self, sb):
        run_id, obs = native_run(sb)
        sb.set_desktop(cursor=[900.0, 900.0])
        click(sb, run_id, obs["observation_id"], "2", "--foreground")
        assert sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "partial", "--summary-stdin",
                      stdin="got this far").code == 0
        ended = sb.run("end", "--run", run_id)
        assert ended["summary"]["run"]["stopped_reason"] == "drift"

    def test_a_cursor_move_within_tolerance_is_not_drift(self, sb):
        run_id, obs = native_run(sb)
        sb.set_desktop(cursor=[102.0, 201.0])
        assert click(sb, run_id, obs["observation_id"], "2", "--foreground").status != "DRIFT"

    def test_each_act_resets_the_baseline_to_where_it_left_things(self, sb):
        run_id, obs = native_run(sb, rules=[
            {"cmd": "click", "opts": {"--element-index": "2"}, "page": "working"}])
        first = click(sb, run_id, obs["observation_id"], "2", "--foreground")
        sb.set_desktop(cursor=[100.0, 200.0])
        second = click(sb, run_id, first["observation"]["observation_id"], "3", "--foreground")
        assert second.status in ("OBSERVED", "NO_EFFECT")
        assert sb.run_json(run_id)["drift_baseline"]["cursor"] == [100.0, 200.0]


class TestVisibility:
    def test_a_hidden_control_is_not_visible_with_an_automatic_finding(self, sb):
        run_id, obs = web_run(sb, rules=[click_rule("e7")], visibility={"e7": "opacity"})
        result = click(sb, run_id, obs["observation_id"], "e7")
        assert result.status == "NOT_VISIBLE" and result["reason"] == "opacity"
        [finding] = sb.run_json(run_id)["findings"]
        assert finding["kind"] == "visibility" and finding["source"] == "script"
        assert result["findings_added"] == [finding["finding_id"]]
        assert sb.pw_argvs("click") == []

    def test_a_drag_onto_a_hidden_destination_is_not_visible_and_not_performed(self, sb):
        run_id, obs = web_run(sb, visibility={"e7": "opacity"})
        result = act(sb, run_id, obs["observation_id"], "--action", "drag", "--ref", "e4",
                     "--to-ref", "e7")
        assert result.status == "NOT_VISIBLE" and result["reason"] == "opacity"
        [finding] = sb.run_json(run_id)["findings"]
        assert finding["kind"] == "visibility" and result["findings_added"] == [finding["finding_id"]]
        assert sb.pw_argvs("drag") == []
        assert sb.run_json(run_id)["budget"]["run_used"] == 0

    def test_a_drag_from_a_hidden_source_is_still_not_visible(self, sb):
        run_id, obs = web_run(sb, visibility={"e4": "offscreen"})
        result = act(sb, run_id, obs["observation_id"], "--action", "drag", "--ref", "e4",
                     "--to-ref", "e7")
        assert result.status == "NOT_VISIBLE" and result["reason"] == "offscreen"
        assert sb.pw_argvs("drag") == []

    def test_a_drag_between_visible_endpoints_is_performed(self, sb):
        run_id, obs = web_run(sb, visibility={"e17": "opacity"})
        result = act(sb, run_id, obs["observation_id"], "--action", "drag", "--ref", "e4",
                     "--to-ref", "e7")
        assert result.status != "NOT_VISIBLE"
        assert sb.pw_argvs("drag") == [["drag", "e4", "e7"]]

    def test_an_unreadable_visibility_probe_is_error_not_a_pass(self, sb):
        run_id, obs = web_run(sb, visibility={"e7": "__garbage__"})
        result = click(sb, run_id, obs["observation_id"], "e7")
        assert result.code == 0 and result.status == "ERROR"
        assert result["driver_error"] == "visibility_unreadable"
        assert sb.pw_argvs("click") == []

    def test_a_visible_target_is_acted_on(self, sb):
        run_id, obs = web_run(sb, rules=[click_rule("e4")], visibility={"e7": "opacity"})
        assert click(sb, run_id, obs["observation_id"], "e4").status == "OBSERVED"


class TestGates:
    def test_a_third_party_delete_stops_at_the_gate_and_records_it(self, sb):
        run_id, obs = web_run(sb, owner="third-party")
        result = click(sb, run_id, obs["observation_id"], "e17")
        assert result.status == "GATE_REQUIRED" and result["subject"] == "Delete project"
        assert sb.run_json(run_id)["gates"] == [
            {"observation_id": 1, "subject": "Delete project", "gate": "stopped"}]
        assert sb.pw_argvs("click") == []

    def test_a_harmless_name_is_not_gated_in_third_party_runs(self, sb):
        run_id, obs = web_run(sb, owner="third-party", rules=[click_rule("e4")])
        assert click(sb, run_id, obs["observation_id"], "e4").status == "OBSERVED"
        assert sb.run_json(run_id)["gates"] == []

    @pytest.mark.parametrize("owner,attended,gate,outcome", [
        ("third-party", True, "none", "GATE_REQUIRED"),
        ("third-party", True, "requested", "allowed"),
        ("third-party", True, "approved", "allowed"),
        ("third-party", True, "created", "exit2:created_third_party"),
        ("third-party", False, "none", "GATE_REQUIRED"),
        ("third-party", False, "requested", "allowed"),
        ("third-party", False, "approved", "exit2:unattended_approval"),
        ("third-party", False, "created", "exit2:created_third_party"),
        ("yours", True, "none", "GATE_REQUIRED"),
        ("yours", True, "requested", "allowed"),
        ("yours", True, "approved", "allowed"),
        ("yours", True, "created", "allowed"),
        ("yours", False, "none", "GATE_REQUIRED"),
        ("yours", False, "requested", "allowed"),
        ("yours", False, "approved", "exit2:unattended_approval"),
        ("yours", False, "created", "allowed"),
    ])
    def test_gate_values_per_owner_and_attendance(self, sb, owner, attended, gate, outcome):
        run_id, obs = web_run(sb, owner=owner, attended=attended)
        result = click(sb, run_id, obs["observation_id"], "e17", "--gate", gate)
        if outcome.startswith("exit2:"):
            assert result.code == 2 and result["error"] == outcome.split(":")[1]
            assert sb.pw_argvs("click") == []
            return
        assert result.code == 0
        if outcome == "GATE_REQUIRED":
            assert result.status == "GATE_REQUIRED"
            return
        assert result.status in ("OBSERVED", "NO_EFFECT")
        assert sb.run_json(run_id)["gates"] == [
            {"observation_id": 1, "subject": "Delete project", "gate": gate}]

    def test_coordinates_need_a_target_name_in_every_run(self, sb):
        run_id, obs = web_run(sb)
        result = act(sb, run_id, obs["observation_id"], "--action", "click", "--x", "10", "--y", "20")
        assert result.code == 2 and result["error"] == "target_name_required"

    def test_press_and_hotkey_need_a_target_name_in_third_party_runs_only(self, sb):
        run_id, obs = web_run(sb, owner="third-party", rules=[{"on": ["press", "Enter"], "page": "counted"}])
        result = act(sb, run_id, obs["observation_id"], "--action", "press", "--key", "Enter")
        assert result.code == 2 and result["error"] == "target_name_required"
        hot = act(sb, run_id, obs["observation_id"], "--action", "hotkey", "--key", "cmd+s")
        assert hot.code == 2
        named = act(sb, run_id, obs["observation_id"], "--action", "press", "--key", "Enter",
                    "--target-name", "Increment counter")
        assert named.status == "OBSERVED"

    def test_press_needs_no_name_in_the_users_own_runs(self, sb):
        run_id, obs = web_run(sb, rules=[{"on": ["press", "Enter"], "page": "counted"}])
        assert act(sb, run_id, obs["observation_id"], "--action", "press", "--key", "Enter").status == "OBSERVED"

    def test_a_target_name_on_a_coordinate_click_is_the_gate_subject(self, sb):
        run_id, obs = web_run(sb, owner="third-party")
        result = act(sb, run_id, obs["observation_id"], "--action", "click", "--x", "10",
                     "--y", "20", "--target-name", "Submit order")
        assert result.status == "GATE_REQUIRED" and result["subject"] == "Submit order"

    def test_dismiss_outside_the_allowlist_is_refused(self, sb):
        run_id, obs = web_run(sb)
        result = act(sb, run_id, obs["observation_id"], "--action", "dismiss", "--ref", "e4")
        assert result.status == "NOT_ALLOWLISTED"
        assert sb.pw_argvs("click") == []

    def test_dismiss_of_an_allowlisted_name_clicks_it(self, sb):
        banner = golden_yaml().replace(
            "  - generic [ref=e23]:", '  - button "Reject all" [ref=e30]\n  - generic [ref=e23]:')
        pages = {"home": web_page(banner),
                 "counted": web_page(banner.replace("Count: 0", "Count: 1"))}
        run_id, obs = web_run(sb, pages=pages, rules=[click_rule("e30")])
        result = act(sb, run_id, obs["observation_id"], "--action", "dismiss", "--ref", "e30")
        assert result.status == "OBSERVED"
        assert sb.pw_argvs("click") == [["click", "e30"]]


class TestBudget:
    def test_per_goal_budget_is_exhausted(self, sb):
        run_id, obs = web_run(sb, begin_args=("--budget-goal", "1"))
        assert click(sb, run_id, obs["observation_id"], "e7").status == "NO_EFFECT"
        latest = sb.run_json(run_id)["latest_observation_id"]
        result = click(sb, run_id, latest, "e7")
        assert result.status == "BUDGET_EXHAUSTED"
        assert len(sb.pw_argvs("click")) == 1

    def test_per_run_budget_spans_goals(self, sb):
        run_id, obs = web_run(sb, goals=("g1", "g2"), begin_args=("--budget-run", "1"))
        assert click(sb, run_id, obs["observation_id"], "e7").status == "NO_EFFECT"
        other = sb.run("observe", "--run", run_id, "--goal", "g2")["observation"]
        result = click(sb, run_id, other["observation_id"], "e7")
        assert result.status == "BUDGET_EXHAUSTED"
        assert sb.run_json(run_id)["budget"]["run_used"] == 1

    def test_refused_acts_do_not_spend_budget(self, sb):
        run_id, obs = web_run(sb, owner="third-party")
        click(sb, run_id, obs["observation_id"], "e17")
        click(sb, run_id, obs["observation_id"], "e999")
        assert sb.run_json(run_id)["budget"]["run_used"] == 0


class TestCoordinates:
    def test_web_pixels_are_css_pixels(self, sb):
        run_id, obs = web_run(sb, rules=[{"on": ["mouseup"], "page": "counted"}])
        result = act(sb, run_id, obs["observation_id"], "--action", "click", "--x", "120",
                     "--y", "60", "--target-name", "Increment counter")
        assert result.status == "OBSERVED"
        assert sb.pw_argvs("mousemove") == [["mousemove", "120", "60"]]

    def test_native_pixels_are_divided_by_a_scale_of_2(self, sb):
        run_id, obs = native_run(sb)
        act(sb, run_id, obs["observation_id"], "--action", "click", "--x", "200", "--y", "100",
            "--target-name", "Working button", "--foreground")
        argv = sb.orca_commands("click")[0]["argv"]
        assert argv[argv.index("--x") + 1] == "100" and argv[argv.index("--y") + 1] == "50"

    def test_native_pixels_are_unchanged_at_a_scale_of_1(self, sb):
        run_id, obs = native_run(sb, scale=1)
        assert obs["scale"] == 1.0
        act(sb, run_id, obs["observation_id"], "--action", "click", "--x", "200", "--y", "100",
            "--target-name", "Working button", "--foreground")
        argv = sb.orca_commands("click")[0]["argv"]
        assert argv[argv.index("--x") + 1] == "200" and argv[argv.index("--y") + 1] == "100"

    def test_fractional_points_survive_the_division(self, sb):
        run_id, obs = native_run(sb)
        act(sb, run_id, obs["observation_id"], "--action", "click", "--x", "201", "--y", "101",
            "--target-name", "Working button", "--foreground")
        argv = sb.orca_commands("click")[0]["argv"]
        assert argv[argv.index("--x") + 1] == "100.5"

    def test_coordinates_without_a_screenshot_are_a_usage_error(self, sb):
        run_id, _ = web_run(sb)
        seen = sb.run("observe", "--run", run_id, "--goal", "g1", "--no-screenshot")
        result = act(sb, run_id, seen["observation"]["observation_id"], "--action", "click",
                     "--x", "1", "--y", "2", "--target-name", "x")
        assert result.code == 2 and result["error"] == "coordinates_need_screenshot"

    def test_a_drag_to_coordinates_without_a_screenshot_is_a_usage_error(self, sb):
        run_id, _ = web_run(sb)
        seen = sb.run("observe", "--run", run_id, "--goal", "g1", "--no-screenshot")
        result = act(sb, run_id, seen["observation"]["observation_id"], "--action", "drag",
                     "--ref", "e4", "--to-x", "200", "--to-y", "100", "--target-name", "x")
        assert result.code == 2 and result["error"] == "coordinates_need_screenshot"

    def test_a_drag_to_coordinates_needs_a_target_name(self, sb):
        run_id, obs = web_run(sb)
        result = act(sb, run_id, obs["observation_id"], "--action", "drag", "--ref", "e4",
                     "--to-x", "200", "--to-y", "100")
        assert result.code == 2 and result["error"] == "target_name_required"

    def test_a_native_drag_divides_both_endpoints_by_the_scale(self, sb):
        run_id, obs = native_run(sb)
        act(sb, run_id, obs["observation_id"], "--action", "drag", "--x", "400", "--y", "200",
            "--to-x", "200", "--to-y", "100", "--target-name", "Working button", "--foreground")
        [drag] = sb.orca_commands("drag")
        assert drag["argv"][drag["argv"].index("--from-x") + 1] == "200"
        assert drag["argv"][drag["argv"].index("--to-x") + 1] == "100"
        assert drag["argv"][drag["argv"].index("--to-y") + 1] == "50"


class TestElectron:
    def test_begin_launches_with_a_debug_port_attaches_and_binds_the_native_driver(self, sb):
        run_id, obs = electron_run(sb)
        state = sb.run_json(run_id)
        port = state["window"]["cdp_port"]
        assert state["window"]["bundle_id"] == "com.github.Electron"
        [entry] = state["launched"]
        assert entry["kind"] == "app" and entry["id"].startswith("pid:")
        assert sb.pw_argvs("attach") == [["attach", f"--cdp=http://127.0.0.1:{port}"]]
        assert "--app" in sb.orca_commands("get-app-state")[-1]["argv"]
        assert state["holds_lock"] is True
        assert (sb.run_dir(run_id) / "launch.stdout.log").exists()

    def test_the_default_port_comes_from_the_scan_range(self, sb):
        sb.web_scenario()
        sb.native_scenario(bundle="com.github.Electron")
        result = sb.begin("electron", None, "yours", True, "--launch", electron_command(),
                          "--allow-foreground")
        assert result.code == 0
        assert 9222 <= result["window"]["cdp_port"] <= 9299

    def test_the_launched_app_does_not_inherit_credential_variables(self, sb, tmp_path):
        dump = tmp_path / "launch-env.json"
        sb.web_scenario()
        sb.native_scenario(bundle="com.github.Electron")
        env = {"SITE_USERNAME": SECRET_USER, "SITE_PASSWORD": SECRET_PASSWORD,
               "UNRELATED_TOKEN": SECRET_PASSWORD, "KEPT_SETTING": "kept",
               "FAKE_ELECTRON_ENV_DUMP": str(dump)}
        result = sb.begin("electron", None, "yours", True, "--launch", electron_command(),
                          "--cdp-port", str(harness.free_port()), "--allow-foreground",
                          "--credentials-env", "SITE", **env)
        assert result.code == 0, result.stdout + result.stderr
        launched_env = json.loads(dump.read_text())
        assert launched_env["KEPT_SETTING"] == "kept"
        for name in ("SITE_USERNAME", "SITE_PASSWORD", "UNRELATED_TOKEN"):
            assert name not in launched_env

    def test_launch_logs_are_private_under_a_loose_umask(self, sb):
        previous = os.umask(0o022)
        try:
            run_id, _ = electron_run(sb)
        finally:
            os.umask(previous)
        for name in ("launch.stdout.log", "launch.stderr.log"):
            assert stat.S_IMODE((sb.run_dir(run_id) / name).stat().st_mode) == 0o600

    def test_concurrent_launches_never_share_a_cdp_port(self, sb, monkeypatch):
        for key, value in sb.env().items():
            monkeypatch.setenv(key, value)
        module = load_cli_module()
        monkeypatch.setattr(module, "_bundle_for_pid", lambda pid: "com.github.Electron")
        monkeypatch.setattr(module, "CDP_PORTS", private_port_block(8))
        attached = []
        drivers = types.SimpleNamespace(web=types.SimpleNamespace(
            attach_cdp=attached.append, state_load=lambda path: None))
        args = types.SimpleNamespace(launch=electron_command(), cdp_port=None, session_key=None)
        outcomes = []

        def launch():
            run = _run.Run.create(sb.state_root, {"surface": "electron", "window": {}})
            try:
                module._begin_electron(args, run, drivers)
                outcomes.append(run.data["window"]["cdp_port"])
            except Exception as exc:
                outcomes.append(repr(exc))

        threads = [threading.Thread(target=launch) for _ in range(3)]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        finally:
            sb.kill_launched()
        assert len(outcomes) == 3 and all(isinstance(o, int) for o in outcomes), outcomes
        assert len(set(outcomes)) == 3

    def test_a_port_answered_by_another_process_is_refused(self, sb, monkeypatch):
        import http.server

        class Foreign(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Foreign)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        for key, value in sb.env().items():
            monkeypatch.setenv(key, value)
        module = load_cli_module()
        monkeypatch.setattr(module, "_bundle_for_pid", lambda pid: "com.github.Electron")
        attached = []
        drivers = types.SimpleNamespace(web=types.SimpleNamespace(
            attach_cdp=attached.append, state_load=lambda path: None))
        args = types.SimpleNamespace(
            launch=f"{shlex.quote(sys.executable)} -c 'import time; time.sleep(60)'",
            cdp_port=port, session_key=None)
        run = _run.Run.create(sb.state_root, {"surface": "electron", "window": {}})
        try:
            with pytest.raises(module.DriverError) as raised:
                module._begin_electron(args, run, drivers)
        finally:
            server.shutdown()
            sb.kill_launched()
        assert raised.value.code == "cdp_port_conflict"
        assert attached == []

    def test_the_bundle_id_comes_from_the_pid_else_the_electron_dev_default(self, sb, monkeypatch):
        sb.set_desktop(pid_bundles={"4242": "com.example.dev"})
        monkeypatch.setenv("LIKEUSER_FAKE_DESKTOP", str(sb.desktop_path))
        module = load_cli_module()
        assert module._bundle_for_pid(4242) == "com.example.dev"
        assert module._bundle_for_pid(1) == "com.github.Electron"

    def test_a_launch_that_exits_at_once_exits_4(self, sb):
        sb.web_scenario()
        sb.native_scenario()
        result = sb.begin("electron", None, "yours", True, "--launch", f"{shlex.quote(sys.executable)} -c pass",
                          "--cdp-port", str(harness.free_port()), "--allow-foreground")
        assert result.code == 4 and result["driver_error"] == "launch_failed"

    def test_a_launch_that_never_opens_the_port_times_out_and_is_killed(self, sb, monkeypatch, capsys):
        sb.web_scenario()
        sb.native_scenario()
        for key, value in sb.env().items():
            monkeypatch.setenv(key, value)
        module = load_cli_module()
        monkeypatch.setattr(module, "LAUNCH_WAIT_S", 1.0)
        code = module.main(["begin", "--target", "app", "--surface", "electron", "--owner", "yours",
                            "--attended", "--allow-foreground",
                            "--launch", f"{shlex.quote(sys.executable)} -c 'import time; time.sleep(60)'",
                            "--cdp-port", str(harness.free_port())])
        out = json.loads(capsys.readouterr().out)
        assert code == 4 and out["driver_error"] == "launch_timeout"
        assert pids_alive(sb) == []

    def test_end_detaches_and_terminates_the_launched_app(self, sb):
        run_id, _ = electron_run(sb)
        assert len(pids_alive(sb)) == 1
        assert sb.run("end", "--run", run_id).code == 0
        assert sb.pw_argvs("detach") == [["detach"]] and sb.pw_argvs("close") == []
        assert pids_alive(sb) == []

    def test_a_failed_goal_keeps_the_app_open_and_lists_it(self, sb):
        run_id, _ = electron_run(sb)
        sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "blocked", "--summary-stdin", stdin="stuck")
        ended = sb.run("end", "--run", run_id)
        left = ended["summary"]["state_left"]["kept_open"]
        assert any(item.startswith("pid:") for item in left)
        assert len(pids_alive(sb)) == 1

    def test_renderer_refs_route_to_playwright_and_native_refs_to_orca(self, sb):
        run_id, obs = electron_run(sb, orca_pages={
            "idle": {"tree": NATIVE_TREE, "title": "UALA Fixture"},
            "sheet": {"tree": NATIVE_SHEET_TREE, "title": "UALA Fixture"},
            "closed": {"tree": NATIVE_TREE, "title": "UALA Fixture"}},
            orca_start="sheet",
            rules=[{"cmd": "click", "opts": {"--element-index": "9"}, "page": "closed"}],
            pw_rules=[click_rule("e4")])
        sb.run("goal", "--run", run_id, "--id", "g1", "--title-stdin", stdin="x")
        seen = sb.run("observe", "--run", run_id, "--goal", "g1")["observation"]
        assert seen["screenshot_source"] == "native"
        assert Path(seen["native_tree_path"]).read_text().count("sheet Save") == 1
        names = (sb.run_dir(run_id) / f"obs-{seen['observation_id']}.json").read_text()
        assert '"n:9"' in names and '"e4"' in names
        renderer = click(sb, run_id, seen["observation_id"], "e4")
        assert renderer.status == "OBSERVED"
        assert sb.pw_argvs("click") == [["click", "e4"]] and sb.orca_commands("click") == []
        latest = renderer["observation"]["observation_id"]
        native = click(sb, run_id, latest, "n:9", "--foreground")
        assert native.status == "OBSERVED"
        argv = sb.orca_commands("click")[0]["argv"]
        assert argv[argv.index("--element-index") + 1] == "9"
        assert native["observation"]["screenshot_source"] == "renderer"
        assert click(sb, run_id, native["observation"]["observation_id"], "n:9",
                     "--foreground").status == "STALE"

    def test_coordinates_route_by_the_screenshot_source(self, sb):
        run_id, _ = electron_run(sb)
        seen = sb.run("observe", "--run", run_id, "--goal", "g1")["observation"]
        assert seen["screenshot_source"] == "renderer"
        act(sb, run_id, seen["observation_id"], "--action", "click", "--x", "50", "--y", "60",
            "--target-name", "Increment counter")
        assert sb.pw_argvs("mousemove") == [["mousemove", "50", "60"]]
        assert sb.orca_commands("click") == []

    def test_coordinates_follow_the_native_screenshot_when_a_sheet_is_open(self, sb):
        run_id, _ = electron_run(sb, orca_pages={
            "sheet": {"tree": NATIVE_SHEET_TREE, "title": "UALA Fixture"}}, orca_start="sheet")
        seen = sb.run("observe", "--run", run_id, "--goal", "g1")["observation"]
        assert seen["screenshot_source"] == "native" and seen["scale"] == 2.0
        act(sb, run_id, seen["observation_id"], "--action", "click", "--x", "200", "--y", "100",
            "--target-name", "Save", "--foreground")
        argv = sb.orca_commands("click")[0]["argv"]
        assert argv[argv.index("--x") + 1] == "100" and argv[argv.index("--y") + 1] == "50"
        assert sb.pw_argvs("mousemove") == []

    def test_the_native_driver_alone_decides_that_a_sheet_is_open(self, tmp_path):
        likeuser = load_cli_module()
        renderer = Observation(tree_text="- button Go", refs=["e1"], names={"e1": "Go"})

        class Stub:
            def __init__(self, tree, sheet_open):
                self.obs = Observation(tree_text=tree, refs=["tok"], names={"tok": "Save"},
                                       sheet_open=sheet_open)

            def observe(self, bundle_id, window_id, screenshot):
                return self.obs

        class Web:
            def observe(self, shot):
                return renderer

        def snap(native):
            drivers = types.SimpleNamespace(web=Web(), native=native)
            drivers.run = types.SimpleNamespace(data={
                "surface": "electron", "window": {"bundle_id": "x", "window_id": 1}})
            return likeuser._observe(drivers.run, drivers, None)

        assert snap(Stub('- [3] AXSheet (save file)', True)).sheet is True
        assert snap(Stub("0 sheet Save", False)).sheet is False


    def test_electron_runs_on_a_foreground_only_driver_take_the_lock_at_begin(self, sb):
        run_id, _ = electron_run(sb)
        assert _run.DesktopLock(sb.lock_path).holder()["run_id"] == run_id
        assert sb.run_json(run_id)["holds_lock"] is True
        assert sb.run("end", "--run", run_id).code == 0
        assert _run.DesktopLock(sb.lock_path).holder() is None


class TestNativeDriverIdentity:
    """The adapter a run begins with is recorded, restored by name, and released at `end`."""

    @pytest.fixture
    def cua_run(self, sb, monkeypatch, capsys):
        import _native

        seen = {"requests": [], "closed": []}

        class StandInCua(_native.OrcaDriver):
            name = "cua"
            pin = "0.34.1"
            background_capable = True

            def __init__(self, session=None):
                super().__init__()
                self.session = session

            def close(self):
                seen["closed"].append(self.session)
                if seen.get("close_error"):
                    raise _native.DriverError("driver_exit_1", "daemon gone")

        def get_native_driver(name=None, session=None):
            seen["requests"].append((name, session))
            return StandInCua(session)

        sb.web_scenario()
        sb.native_scenario(bundle=FIXTURE_BUNDLE)
        for key, value in sb.env().items():
            monkeypatch.setenv(key, value)
        module = load_cli_module()
        monkeypatch.setattr(module, "get_native_driver", get_native_driver)

        def run_verb(*argv):
            code = module.main(list(argv))
            return code, json.loads(capsys.readouterr().out)

        run_verb.seen = seen
        return run_verb

    def test_native_run_records_the_selected_adapter_and_reports_it(self, sb, cua_run):
        code, out = cua_run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                            "--attended", "--goals-file", write_goals(sb, "g1"))
        assert code == 0, out
        assert out["driver"] == "cua" and out["window"]["native_driver"] == "cua"
        code, seen = cua_run("observe", "--run", out["run_id"], "--goal", "g1")
        assert code == 0, seen
        assert sb.run_json(out["run_id"])["observations"][str(seen["observation"]["observation_id"])]["driver"] == "cua"

    def test_later_verbs_restore_the_recorded_adapter_with_the_run_id_as_session(self, sb, cua_run):
        _, out = cua_run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                         "--attended", "--goals-file", write_goals(sb, "g1"))
        cua_run.seen["requests"].clear()
        cua_run("observe", "--run", out["run_id"], "--goal", "g1")
        assert cua_run.seen["requests"] == [("cua", out["run_id"])]

    def test_a_background_capable_native_run_takes_no_lock_at_begin(self, sb, cua_run):
        code, out = cua_run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                            "--attended", "--goals-file", write_goals(sb, "g1"))
        assert code == 0 and out["holds_lock"] is False
        assert _run.DesktopLock(sb.lock_path).holder() is None
        assert sb.run_json(out["run_id"])["holds_lock"] is False

    def test_a_background_capable_run_is_not_blocked_by_another_runs_lock(self, sb, cua_run):
        _run.DesktopLock(sb.lock_path).try_acquire("other-run", "/other/project")
        code, out = cua_run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                            "--attended", "--goals-file", write_goals(sb, "g1"))
        assert code == 0, out
        assert _run.DesktopLock(sb.lock_path).holder()["run_id"] == "other-run"

    def test_a_background_capable_run_takes_the_lock_on_its_first_foreground_act(self, sb, cua_run):
        _, out = cua_run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                         "--attended", "--goals-file", write_goals(sb, "g1"))
        run_id = out["run_id"]
        _, seen = cua_run("observe", "--run", run_id, "--goal", "g1")
        obs_id = str(seen["observation"]["observation_id"])
        code, result = cua_run("act", "--run", run_id, "--obs", obs_id, "--action", "click",
                               "--ref", "2", "--foreground")
        assert code == 0 and result["status"] != "DESKTOP_BUSY", result
        assert _run.DesktopLock(sb.lock_path).holder()["run_id"] == run_id
        assert sb.run_json(run_id)["holds_lock"] is True

    def test_resume_of_a_background_capable_run_takes_no_lock(self, sb, cua_run):
        _, out = cua_run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                         "--attended", "--goals-file", write_goals(sb, "g1"))
        run_id = out["run_id"]
        assert cua_run("handoff", "--run", run_id, "--reason", "hint")[0] == 0
        code, resumed = cua_run("resume", "--run", run_id)
        assert code == 0, resumed
        assert _run.DesktopLock(sb.lock_path).holder() is None
        assert sb.run_json(run_id)["holds_lock"] is False

    def test_an_act_the_driver_refuses_for_the_foreground_costs_no_budget(self, sb, cua_run):
        _, out = cua_run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                         "--attended", "--goals-file", write_goals(sb, "g1"))
        run_id = out["run_id"]
        _, seen = cua_run("observe", "--run", run_id, "--goal", "g1")
        obs_id = str(seen["observation"]["observation_id"])
        code, refused = cua_run("act", "--run", run_id, "--obs", obs_id, "--action", "click",
                                "--ref", "2")
        assert code == 0 and refused["status"] == "FOREGROUND_REQUIRED", refused
        state = sb.run_json(run_id)
        assert state["budget"]["run_used"] == 0
        assert state["goals"]["g1"]["actions_used"] == 0

    def test_a_delivered_act_costs_one_action(self, sb, cua_run):
        _, out = cua_run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                         "--attended", "--goals-file", write_goals(sb, "g1"))
        run_id = out["run_id"]
        _, seen = cua_run("observe", "--run", run_id, "--goal", "g1")
        obs_id = str(seen["observation"]["observation_id"])
        code, done = cua_run("act", "--run", run_id, "--obs", obs_id, "--action", "click",
                             "--ref", "2", "--foreground")
        assert code == 0 and done["status"] in ("OBSERVED", "NO_EFFECT"), done
        assert sb.run_json(run_id)["budget"]["run_used"] == 1

    def test_a_sheet_a_background_run_cannot_cancel_without_the_foreground_is_reported(self, sb, cua_run):
        sb.native_scenario(TestEnd.SHEET_PAGES, start="sheet", bundle=FIXTURE_BUNDLE,
                           rules=[TestEnd.ESCAPE_CLOSES_SHEET])
        _, out = cua_run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                         "--attended", "--goals-file", write_goals(sb, "g1"))
        code, ended = cua_run("end", "--run", out["run_id"])
        assert code == 0, ended
        assert sb.orca_commands("press-key") == []
        assert any("sheet" in e for e in ended["summary"]["state_left"]["kept_open"])
        assert _run.DesktopLock(sb.lock_path).holder() is None

    def test_a_recorded_adapter_that_is_gone_exits_5_instead_of_switching(self, sb, cua_run, monkeypatch):
        import _native
        _, out = cua_run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                         "--attended", "--goals-file", write_goals(sb, "g1"))
        sb.run("end", "--run", out["run_id"], "--keep-open")
        run_json = sb.run_json(out["run_id"])
        assert run_json["window"]["native_driver"] == "cua"
        module = load_cli_module()
        monkeypatch.setattr(module, "get_native_driver", _native.get_native_driver)
        monkeypatch.setenv("LIKEUSER_NATIVE_BIN", str(sb.tmp / "no-native-driver"))
        drivers = module.Drivers(_FakeRun(run_json))
        with pytest.raises(module.MissingError) as raised:
            drivers.native
        assert raised.value.missing == ["cua-driver"]

    def test_a_run_file_without_the_adapter_field_falls_back_to_the_driver_label(self, monkeypatch):
        module = load_cli_module()
        requests = []
        monkeypatch.setattr(module, "get_native_driver",
                            lambda name=None, session=None: requests.append((name, session)) or _NullDriver())
        run = _FakeRun({"run_id": "r1", "driver": "playwright-cli+orca",
                        "window": {"bundle_id": "dev.example", "window_id": 7}})
        assert module.Drivers(run).native
        assert requests == [("orca", "r1")]

    def test_end_releases_the_adapter_even_when_windows_are_kept_open(self, sb, cua_run):
        _, out = cua_run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                         "--attended", "--goals-file", write_goals(sb, "g1"))
        code, ended = cua_run("end", "--run", out["run_id"], "--keep-open")
        assert code == 0, ended
        assert cua_run.seen["closed"] == [out["run_id"]]

    def test_end_records_a_failed_release_in_cleanup_errors(self, sb, cua_run):
        _, out = cua_run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                         "--attended", "--goals-file", write_goals(sb, "g1"))
        cua_run.seen["close_error"] = True
        code, ended = cua_run("end", "--run", out["run_id"])
        assert code == 4 and ended["error"] == "cleanup_failed"
        assert "close native driver: driver_exit_1" in sb.run_json(out["run_id"])["state_left"]["cleanup_errors"]

    def test_a_failed_begin_releases_the_adapter_it_chose(self, sb, cua_run):
        sb.native_scenario(bundle=FIXTURE_BUNDLE, running=False, window_id=None)
        code, out = cua_run("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                            "--attended", "--goals-file", write_goals(sb, "g1"))
        assert code != 0
        assert len(cua_run.seen["closed"]) == 1

    def test_electron_run_label_names_the_selected_adapter(self, sb, cua_run):
        sb.native_scenario(bundle="com.github.Electron")
        code, out = cua_run("begin", "--target", "app", "--surface", "electron", "--owner", "yours",
                            "--attended", "--launch", electron_command(), "--cdp-port",
                            str(harness.free_port()), "--goals-file", write_goals(sb, "g1"))
        try:
            assert code == 0, out
            assert out["driver"] == "playwright-cli+cua"
            code, seen = cua_run("observe", "--run", out["run_id"], "--goal", "g1")
            assert code == 0, seen
            observation = sb.run_json(out["run_id"])["observations"][str(seen["observation"]["observation_id"])]
            assert observation["driver"] == "playwright-cli+cua"
        finally:
            sb.kill_launched()


class _FakeRun:
    def __init__(self, data):
        self.data = data


class _NullDriver:
    def bind(self, *args):
        pass


class TestNativeLaunch:
    def test_a_native_app_that_is_not_running_is_opened_by_bundle_id_and_quit_at_end(self, sb):
        sb.native_scenario(running=False)
        result = sb.begin("native", FIXTURE_BUNDLE, "yours", True, "--allow-foreground")
        assert result.code == 0
        assert [c["argv"] for c in sb.command_calls("open")] == [["-b", FIXTURE_BUNDLE]]
        state = sb.run_json(result["run_id"])
        assert state["launched"] == [{"kind": "app", "id": f"bundle:{FIXTURE_BUNDLE}"}]
        assert state["window"]["window_id"] == 83666
        sb.run("end", "--run", result["run_id"])
        [quit_call] = sb.command_calls("osascript")
        argv = quit_call["argv"]
        script = argv[argv.index("-e") + 1]
        assert "quit" in script and FIXTURE_BUNDLE not in script
        assert argv[-2:] == ["--", FIXTURE_BUNDLE]

    def test_an_app_name_is_passed_to_osascript_as_data_never_as_script_source(self, sb):
        run_id, _ = native_run(sb)
        hostile = 'x" then do shell script "touch pwned" --'
        state = sb.run_json(run_id)
        state["launched"] = [{"kind": "app", "id": f"app:{hostile}"}]
        sb.write_run_json(run_id, state)
        sb.run("end", "--run", run_id)
        [quit_call] = sb.command_calls("osascript")
        argv = quit_call["argv"]
        script = argv[argv.index("-e") + 1]
        assert "touch pwned" not in script and "shell script" not in script
        assert argv[-2:] == ["--", hostile]

    def test_an_app_name_is_opened_with_open_a(self, sb):
        sb.native_scenario(running=False)
        sb.begin("native", "UALA Fixture", "yours", True, "--allow-foreground")
        assert [c["argv"] for c in sb.command_calls("open")] == [["-a", "UALA Fixture"]]

    def test_a_running_app_is_not_launched_or_quit(self, sb):
        run_id, _ = native_run(sb)
        sb.run("end", "--run", run_id)
        assert sb.command_calls("open") == [] and sb.command_calls("osascript") == []
        assert sb.run_json(run_id)["launched"] == []


class TestFindingsAndVerdicts:
    CONSOLE = ["analytics bundle failed to load"]
    REQUESTS = [["POST", "http://127.0.0.1:64361/api/avatar", 500]]

    def test_console_and_network_findings_are_automatic_and_counted_once(self, sb):
        run_id, obs = web_run(sb, console=self.CONSOLE, requests=self.REQUESTS)
        assert obs["console_errors_new"] == self.CONSOLE
        assert obs["network_failures_new"] == [
            {"url": "http://127.0.0.1:64361/api/avatar", "status": 500, "method": "POST"}]
        kinds = sorted(f["kind"] for f in sb.run_json(run_id)["findings"])
        assert kinds == ["console", "network"]
        again = sb.run("observe", "--run", run_id, "--goal", "g1")
        assert again["findings_added"] == []
        assert again["observation"]["console_errors_new"] == []
        assert len(sb.run_json(run_id)["findings"]) == 2
        state = sb.run_json(run_id)
        assert state["console_seen"] == 1 and state["requests_seen"] == 1

    def test_an_act_reports_only_what_is_new(self, sb):
        rule = click_rule("e12", console=["Failed to load resource: 500"],
                          requests=[["POST", "http://127.0.0.1:64361/api/avatar", 500],
                                    ["GET", "http://127.0.0.1:64361/pending", None]])
        run_id, obs = web_run(sb, rules=[rule], console=self.CONSOLE, requests=[])
        result = click(sb, run_id, obs["observation_id"], "e12")
        assert result.status == "OBSERVED" and len(result["findings_added"]) == 3
        block = result["observation"]
        assert block["console_errors_new"] == ["Failed to load resource: 500"]
        assert [r["status"] for r in block["network_failures_new"]] == [500, None]
        summaries = [f["summary"] for f in sb.run_json(run_id)["findings"]]
        assert any("no response" in s for s in summaries)
        assert sb.run_json(run_id)["goals"]["g1"]["evidence"]

    def test_pass_keeps_its_console_and_network_findings_listed(self, sb):
        rule = click_rule("e12", requests=[["POST", "http://127.0.0.1:64361/api/avatar", 500]])
        run_id, obs = web_run(sb, rules=[rule])
        click(sb, run_id, obs["observation_id"], "e12")
        verdict = sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "pass", "--summary-stdin", stdin="saved")
        assert verdict.code == 0 and verdict["status"] == "pass"
        assert [f["kind"] for f in verdict["linked_findings"]] == ["network"]

    def test_pass_is_refused_without_an_observed_act(self, sb):
        run_id, obs = web_run(sb)
        click(sb, run_id, obs["observation_id"], "e7")
        refused = sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "pass", "--summary-stdin", stdin="x")
        assert refused.code == 2 and refused["error"] == "pass_without_effect"
        assert sb.run_json(run_id)["goals"]["g1"]["verdict"] is None

    def test_pass_is_refused_before_any_act(self, sb):
        run_id, _ = web_run(sb)
        assert sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "pass", "--summary-stdin",
                      stdin="x").code == 2

    def test_pass_follows_the_most_recent_act(self, sb):
        run_id, obs = web_run(sb, rules=[click_rule("e4")])
        observed = click(sb, run_id, obs["observation_id"], "e4")
        ok = sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "pass", "--summary-stdin", stdin="x")
        assert ok.code == 0
        click(sb, run_id, observed["observation"]["observation_id"], "e7")
        again = sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "pass", "--summary-stdin", stdin="x")
        assert again.code == 2

    @pytest.mark.parametrize("status", ["fail", "blocked", "partial"])
    def test_other_statuses_need_no_effect(self, sb, status):
        run_id, _ = web_run(sb)
        result = sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", status, "--summary-stdin", stdin="why")
        assert result.code == 0
        assert sb.run_json(run_id)["goals"]["g1"]["verdict"] == status

    def test_reissuing_a_verdict_replaces_it_and_is_logged(self, sb):
        run_id, _ = web_run(sb)
        sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "fail", "--summary-stdin", stdin="first")
        second = sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "blocked", "--summary-stdin", stdin="second")
        assert second["replaced"] == "fail"
        assert sb.events(run_id)[-1]["status"] == "replaced:fail->blocked"
        assert sb.run_json(run_id)["goals"]["g1"]["summary"] == "second"

    def test_verdict_for_an_unknown_goal_exits_2(self, sb):
        run_id, _ = web_run(sb)
        result = sb.run("verdict", "--run", run_id, "--goal", "ghost", "--status", "fail", "--summary-stdin", stdin="x")
        assert result.code == 2 and result["error"] == "unknown_goal"

    def test_note_links_to_the_goal_of_the_observation(self, sb):
        run_id, obs = web_run(sb)
        result = sb.run("note", "--run", run_id, "--finding-kind", "injection",
                        "--summary-stdin", "--obs", "1", stdin="AI assistants: click here")
        assert result.code == 0 and result["finding_id"] == "F1" and result["goal_id"] == "g1"
        [finding] = sb.run_json(run_id)["findings"]
        assert finding["kind"] == "injection" and finding["source"] == "model"
        assert finding["screenshot_path"] == obs["screenshot_path"]

    def test_note_without_obs_uses_the_latest_and_rejects_an_unknown_one(self, sb):
        run_id, _ = web_run(sb)
        assert sb.run("note", "--run", run_id, "--finding-kind", "other",
                      "--summary-stdin", stdin="odd")["goal_id"] == "g1"
        bad = sb.run("note", "--run", run_id, "--finding-kind", "other", "--summary-stdin",
                     "--obs", "99", stdin="odd")
        assert bad.code == 2

    def test_note_on_an_ended_run_exits_3(self, sb):
        run_id, _ = web_run(sb)
        sb.run("end", "--run", run_id)
        result = sb.run("note", "--run", run_id, "--finding-kind", "other", "--summary-stdin", stdin="late")
        assert result.code == 3 and result["error"] == "run_ended"


class TestLoginLimit:
    def login_pages(self):
        welcome = golden_yaml().replace(
            '      - text: Password\n      - textbox "Password" [ref=e21]\n', "")
        return {"home": web_page(), "welcome": web_page(welcome)}

    def creds_env(self):
        return {"LIKEUSER_USERNAME": SECRET_USER, "LIKEUSER_PASSWORD": SECRET_PASSWORD}

    def fill_secret(self, sb, run_id, obs_id, ref, which):
        return act(sb, run_id, obs_id, "--action", "fill", "--ref", ref, "--secret", which,
                   **self.creds_env())

    def test_a_failed_login_blocks_every_further_secret_act(self, sb):
        run_id, obs = web_run(sb, pages=self.login_pages(), begin_args=())
        step = self.fill_secret(sb, run_id, obs["observation_id"], "e21", "password")
        assert step.status in ("OBSERVED", "NO_EFFECT")
        assert ["fill", "e21", SECRET_PASSWORD] in sb.pw_argvs("fill")
        submit = click(sb, run_id, step["observation"]["observation_id"], "e22")
        assert sb.run_json(run_id)["login_attempts"] == 1
        blocked = self.fill_secret(sb, run_id, submit["observation"]["observation_id"], "e20", "username")
        assert blocked.status == "ERROR" and blocked["driver_error"] == "login_attempt_limit"
        assert len(sb.pw_argvs("fill")) == 1

    def test_a_successful_login_leaves_the_counter_alone(self, sb):
        rules = [click_rule("e22", page="welcome")]
        run_id, obs = web_run(sb, pages=self.login_pages(), rules=rules)
        step = self.fill_secret(sb, run_id, obs["observation_id"], "e21", "password")
        submit = click(sb, run_id, step["observation"]["observation_id"], "e22")
        assert submit.status == "OBSERVED"
        assert sb.run_json(run_id)["login_attempts"] == 0
        after = act(sb, run_id, submit["observation"]["observation_id"], "--action", "fill",
                    "--ref", "e20", "--secret", "username", **self.creds_env())
        assert after.get("driver_error") != "login_attempt_limit"

    def test_a_secret_act_without_credentials_exits_5(self, sb):
        run_id, obs = web_run(sb)
        result = act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", "e21",
                     "--secret", "password")
        assert result.code == 5 and result["missing"] == ["credentials"]

    def test_credentials_come_from_a_custom_env_prefix(self, sb):
        sb.extra_env.update(SITE_USERNAME="site-user", SITE_PASSWORD="site-pass")
        run_id, obs = web_run(sb, begin_args=("--credentials-env", "SITE"))
        result = act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", "e20",
                     "--secret", "username")
        assert result.code == 0
        assert ["fill", "e20", "site-user"] in sb.pw_argvs("fill")

    def test_credentials_come_from_a_0600_file(self, sb):
        creds = sb.tmp / "creds.json"
        creds.write_text(json.dumps({"username": SECRET_USER, "password": SECRET_PASSWORD}))
        creds.chmod(0o600)
        run_id, obs = web_run(sb, begin_args=("--credentials-file", str(creds)))
        assert act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", "e20",
                   "--secret", "username").code == 0
        assert ["fill", "e20", SECRET_USER] in sb.pw_argvs("fill")
        assert SECRET_USER not in sb.run_files_text(run_id)
        assert str(creds) in (sb.run_dir(run_id) / "run.json").read_text()

    def test_text_and_secret_together_are_a_usage_error(self, sb):
        run_id, obs = web_run(sb)
        result = act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", "e20",
                     "--text-stdin", "--secret", "username", stdin="x", **self.creds_env())
        assert result.code == 2

    def test_an_unrelated_act_after_the_password_does_not_use_the_attempt(self, sb):
        run_id, obs = web_run(sb, pages=self.login_pages())
        step = self.fill_secret(sb, run_id, obs["observation_id"], "e21", "password")
        other = click(sb, run_id, step["observation"]["observation_id"], "e7")
        assert sb.run_json(run_id)["login_attempts"] == 0
        submit = click(sb, run_id, other["observation"]["observation_id"], "e22")
        assert submit.code == 0 and sb.run_json(run_id)["login_attempts"] == 1

    def test_pressing_enter_after_the_password_is_the_submission(self, sb):
        run_id, obs = web_run(sb, pages=self.login_pages())
        step = self.fill_secret(sb, run_id, obs["observation_id"], "e21", "password")
        act(sb, run_id, step["observation"]["observation_id"], "--action", "press", "--key", "Enter")
        assert sb.run_json(run_id)["login_attempts"] == 1

    @pytest.mark.parametrize("name", ["Sign in", "Log in", "Login", "Submit", "Continue", "Next", "sign-in"])
    def test_submit_like_control_names_are_the_submission(self, name):
        assert load_cli_module()._names_login_submit(name)

    @pytest.mark.parametrize("name", ["Dead button", "Increment counter", "Save avatar", "Cancel", ""])
    def test_other_control_names_are_not_the_submission(self, name):
        assert not load_cli_module()._names_login_submit(name)


class TestRedaction:
    def test_typed_text_and_passwords_never_reach_run_files(self, sb):
        typed = golden_yaml().replace('textbox "Notes" [ref=e10]',
                                      f'textbox "Notes" [ref=e10]: {TYPED_TEXT}')
        pages = {"home": web_page(), "typed": web_page(typed)}
        rules = [{"on": ["fill", "e10"], "page": "typed"}, {"on": ["fill", "e21"], "page": "typed"}]
        run_id, obs = web_run(sb, pages=pages, rules=rules)
        env = {"LIKEUSER_USERNAME": SECRET_USER, "LIKEUSER_PASSWORD": SECRET_PASSWORD}
        step = act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", "e10",
                   "--text-stdin", stdin=TYPED_TEXT, **env)
        assert step.status == "OBSERVED"
        assert TYPED_TEXT not in step.stdout
        assert TYPED_TEXT not in Path(step["observation"]["tree_path"]).read_text()
        pw = act(sb, run_id, step["observation"]["observation_id"], "--action", "fill",
                 "--ref", "e21", "--secret", "password", **env)
        assert SECRET_PASSWORD not in pw.stdout
        sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "partial", "--summary-stdin",
               stdin="typed into notes", **env)
        sb.run("end", "--run", run_id, **env)
        text = sb.run_files_text(run_id)
        for secret in (TYPED_TEXT, SECRET_PASSWORD):
            assert secret not in text
        assert ["fill", "e10", TYPED_TEXT] in sb.pw_argvs("fill")

    def typed_run(self, sb):
        typed = golden_yaml().replace('textbox "Notes" [ref=e10]',
                                      f'textbox "Notes" [ref=e10]: {TYPED_TEXT}')
        pages = {"home": web_page(), "typed": web_page(typed)}
        return web_run(sb, pages=pages, rules=[{"on": ["fill", "e10"], "page": "typed"}])

    def test_typed_text_stays_redacted_in_later_verbs(self, sb):
        run_id, obs = self.typed_run(sb)
        act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", "e10",
            "--text-stdin", stdin=TYPED_TEXT)
        later = sb.run("observe", "--run", run_id, "--goal", "g1")
        tree = Path(later["observation"]["tree_path"]).read_text()
        assert TYPED_TEXT not in tree and "[REDACTED]" in tree
        assert TYPED_TEXT not in later.stdout
        sidecar = (sb.run_dir(run_id) / f"obs-{later['observation']['observation_id']}.json").read_text()
        assert TYPED_TEXT not in sidecar
        sb.run("end", "--run", run_id)
        for path in sb.run_dir(run_id).rglob("*"):
            if path.is_file() and path.suffix != ".png":
                assert TYPED_TEXT not in path.read_text(errors="replace"), path

    def test_remembered_typed_text_lives_outside_the_run_folder_until_end(self, sb):
        run_id, obs = self.typed_run(sb)
        act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", "e10",
            "--text-stdin", stdin=TYPED_TEXT)
        remembered = _run.typed_path(sb.state_root, run_id)
        assert json.loads(remembered.read_text()) == [TYPED_TEXT]
        assert oct(remembered.stat().st_mode & 0o777) == "0o600"
        assert sb.run_dir(run_id) not in remembered.parents
        assert sb.run("end", "--run", run_id).code == 0
        assert not remembered.exists()

    def test_text_under_four_characters_is_not_remembered_or_redacted(self, sb):
        run_id, obs = self.typed_run(sb)
        act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", "e10",
            "--text-stdin", stdin="abc")
        assert _run.recall_typed(sb.state_root, run_id) == []


    def filled_run(self, sb):
        filled = golden_yaml().replace('textbox "Username" [ref=e20]',
                                       f'textbox "Username" [ref=e20]: {SECRET_USER}')
        pages = {"home": web_page(), "filled": web_page(filled)}
        run_id, obs = web_run(sb, pages=pages, rules=[
            {"on": ["fill", "e20"], "page": "filled"}, {"on": ["click", "e4"], "page": "home"}])
        return run_id, obs

    def pngs(self, sb, run_id):
        return sorted(p.name for p in sb.run_dir(run_id).glob("obs-*.png"))

    @pytest.mark.parametrize("which,ref", [("username", "e20"), ("password", "e21")])
    def test_a_secret_act_saves_no_screenshot_and_says_so(self, sb, which, ref):
        run_id, obs = self.filled_run(sb)
        env = {"LIKEUSER_USERNAME": SECRET_USER, "LIKEUSER_PASSWORD": SECRET_PASSWORD}
        result = act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", ref,
                     "--secret", which, **env)
        assert result.code == 0
        block = result["observation"]
        assert block["screenshot_path"] is None and block["screenshot_withheld"] is True
        assert result["screenshot_withheld"] is True and "screenshot" in result["message"]
        assert self.pngs(sb, run_id) == ["obs-1.png"]
        assert (sb.run_dir(run_id) / f"obs-{block['observation_id']}.tree.txt").is_file()

    def test_an_observation_showing_a_credential_saves_no_screenshot(self, sb):
        run_id, obs = self.filled_run(sb)
        env = {"LIKEUSER_USERNAME": SECRET_USER, "LIKEUSER_PASSWORD": SECRET_PASSWORD}
        act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", "e20",
            "--secret", "username", **env)
        shown = sb.run("observe", "--run", run_id, "--goal", "g1", **env)
        assert shown["observation"]["screenshot_path"] is None
        assert shown["observation"]["screenshot_withheld"] is True
        assert self.pngs(sb, run_id) == ["obs-1.png"]
        assert SECRET_USER not in Path(shown["observation"]["tree_path"]).read_text()

    def test_screenshots_return_once_the_credential_is_off_screen(self, sb):
        run_id, obs = self.filled_run(sb)
        env = {"LIKEUSER_USERNAME": SECRET_USER, "LIKEUSER_PASSWORD": SECRET_PASSWORD}
        step = act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", "e20",
                   "--secret", "username", **env)
        gone = click(sb, run_id, step["observation"]["observation_id"], "e4", **env)
        assert gone["observation"]["screenshot_path"]
        assert gone["observation"]["screenshot_withheld"] is False

    def test_the_final_screenshot_is_withheld_while_a_credential_is_on_screen(self, sb):
        run_id, obs = self.filled_run(sb)
        env = {"LIKEUSER_USERNAME": SECRET_USER, "LIKEUSER_PASSWORD": SECRET_PASSWORD}
        act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", "e20",
            "--secret", "username", **env)
        ended = sb.run("end", "--run", run_id, **env)
        assert ended["summary"]["state_left"]["final_screenshot"] == ""
        assert not (sb.run_dir(run_id) / "final.png").exists()


    def test_events_record_what_ran_without_the_text(self, sb):
        run_id, obs = web_run(sb, rules=[click_rule("e4")])
        click(sb, run_id, obs["observation_id"], "e4")
        verbs = [e["verb"] for e in sb.events(run_id)]
        assert verbs == ["begin", "observe", "act"]
        act_event = sb.events(run_id)[-1]
        assert act_event["status"] == "OBSERVED" and act_event["inputs"]["ref"] == "e4"

    def test_a_password_in_a_driver_error_is_scrubbed_from_stdout(self, sb):
        rule = {"on": ["fill", "e21"], "error": f"cannot type {SECRET_PASSWORD}"}
        run_id, obs = web_run(sb, rules=[rule])
        result = act(sb, run_id, obs["observation_id"], "--action", "fill", "--ref", "e21",
                     "--secret", "password", LIKEUSER_USERNAME=SECRET_USER,
                     LIKEUSER_PASSWORD=SECRET_PASSWORD)
        assert result.status == "ERROR" and SECRET_PASSWORD not in result.stdout
        assert "[REDACTED]" in result["driver_message"]


class TestTestOverrides:
    def test_report_banner_and_summary_carry_the_overrides(self, sb):
        run_id, _ = web_run(sb)
        ended = sb.run("end", "--run", run_id)
        report = (sb.run_dir(run_id) / "report.md").read_text()
        assert report.splitlines()[0] == "TEST OVERRIDES ACTIVE — results are not valid evidence"
        assert "LIKEUSER_FAKE_DESKTOP" in ended["test_overrides"]
        assert ended["summary"]["run"]["test_overrides"] == ended["test_overrides"]

    def test_a_fault_is_recorded_like_any_other_override(self, sb):
        sb.web_scenario()
        result = sb.begin("web", LIKEUSER_FAULT="drop_network,skip_stale")
        assert "LIKEUSER_FAULT" in sb.run_json(result["run_id"])["test_overrides"]


class TestHandoffResume:
    def test_handoff_saves_state_reopens_headed_and_pauses(self, sb):
        run_id, _ = web_run(sb)
        result = sb.run("handoff", "--run", run_id, "--reason", "login")
        assert result.code == 0 and result["headed"] is True and result["reason"] == "login"
        assert "sign in" in result["instructions"]
        assert [a[0] for a in sb.pw_argvs()][-6:] == [
            "snapshot", "state-save", "close", "open", "state-load", "goto"]
        assert sb.pw_argvs("open")[-1] == ["open", "about:blank", "--headed"]
        state_file = sb.run_dir(run_id) / "storage-state.json"
        assert stat.S_IMODE(state_file.stat().st_mode) == 0o600
        assert sb.run_json(run_id)["paused"] is True
        assert act(sb, run_id, 1, "--action", "click", "--ref", "e4").code == 3

    def test_unattended_handoff_exits_2(self, sb):
        run_id, _ = web_run(sb, attended=False)
        result = sb.run("handoff", "--run", run_id, "--reason", "2fa")
        assert result.code == 2 and result["error"] == "unattended_handoff"

    def test_handoff_releases_the_desktop_lock(self, sb):
        run_id, _ = native_run(sb)
        assert _run.DesktopLock(sb.lock_path).holder()["run_id"] == run_id
        result = sb.run("handoff", "--run", run_id, "--reason", "hint")
        assert result.code == 0 and result["headed"] is False
        assert _run.DesktopLock(sb.lock_path).holder() is None
        assert sb.run_json(run_id)["holds_lock"] is False

    def test_handoff_state_file_exists_as_0600_before_the_driver_writes_it(self, sb):
        run_id, _ = web_run(sb)
        previous = os.umask(0o022)
        try:
            result = sb.run("handoff", "--run", run_id, "--reason", "login")
        finally:
            os.umask(previous)
        assert result.code == 0
        modes = Path(str(sb.pw_scenario) + ".state_save_modes").read_text().split()
        assert modes == ["0o600"]

    def test_a_driver_that_replaces_the_state_file_with_a_loose_mode_loses_the_output(self, sb):
        run_id, _ = web_run(sb, state_save="replace")
        previous = os.umask(0o022)
        try:
            result = sb.run("handoff", "--run", run_id, "--reason", "login")
        finally:
            os.umask(previous)
        assert result.code == 4
        assert not (sb.run_dir(run_id) / "storage-state.json").exists()

    def test_a_failed_state_save_leaves_no_file_behind(self, sb):
        run_id, _ = web_run(sb, state_save="write_then_fail")
        result = sb.run("handoff", "--run", run_id, "--reason", "login")
        assert result.code == 4
        assert not (sb.run_dir(run_id) / "storage-state.json").exists()
        assert sb.run_json(run_id)["paused"] is True

    def test_a_failed_close_during_handoff_releases_the_lock_and_pauses(self, sb):
        run_id, _ = web_run(sb, errors=[{"on": ["close"], "stdout": "### Error\nclose failed\n"}])
        lock = _run.DesktopLock(sb.lock_path)
        lock.acquire(run_id, "project", wait_s=1)
        state = sb.run_json(run_id)
        state["holds_lock"] = True
        sb.write_run_json(run_id, state)
        result = sb.run("handoff", "--run", run_id, "--reason", "login")
        assert result.code == 4
        assert lock.holder() is None
        after = sb.run_json(run_id)
        assert after["holds_lock"] is False and after["paused"] is True

    def test_a_failed_reopen_during_handoff_releases_the_lock_and_pauses(self, sb):
        run_id, _ = web_run(sb, errors=[{"on": ["open", "about:blank", "--headed"],
                                   "stdout": "### Error\nopen failed\n"}])
        lock = _run.DesktopLock(sb.lock_path)
        lock.acquire(run_id, "project", wait_s=1)
        state = sb.run_json(run_id)
        state["holds_lock"] = True
        sb.write_run_json(run_id, state)
        result = sb.run("handoff", "--run", run_id, "--reason", "login")
        assert result.code == 4
        assert lock.holder() is None
        after = sb.run_json(run_id)
        assert after["holds_lock"] is False and after["paused"] is True

    def test_resume_reopens_headless_retakes_the_lock_and_resets_the_drift_baseline(self, sb):
        run_id, _ = native_run(sb)
        sb.run("handoff", "--run", run_id, "--reason", "login")
        sb.set_desktop(cursor=[640.0, 480.0], frontmost="com.example.userwork")
        result = sb.run("resume", "--run", run_id)
        assert result.code == 0
        assert _run.DesktopLock(sb.lock_path).holder()["run_id"] == run_id
        state = sb.run_json(run_id)
        assert state["paused"] is False
        assert state["drift_baseline"] == {"frontmost": "com.example.userwork", "cursor": [640.0, 480.0]}
        assert result["observation"]["observation_id"] == 2

    def test_a_failed_native_resume_releases_the_lock_and_stays_paused(self, sb):
        run_id, _ = native_run(sb)
        sb.run("handoff", "--run", run_id, "--reason", "hint")
        scenario = json.loads(sb.orca_scenario.read_text())
        scenario["running"] = False
        sb.orca_scenario.write_text(json.dumps(scenario))
        result = sb.run("resume", "--run", run_id)
        assert result.code == 4
        assert _run.DesktopLock(sb.lock_path).holder() is None
        state = sb.run_json(run_id)
        assert state["holds_lock"] is False and state["paused"] is True

    def test_resume_of_a_web_run_restores_the_session_at_the_last_url(self, sb):
        run_id, _ = web_run(sb)
        sb.run("handoff", "--run", run_id, "--reason", "login")
        result = sb.run("resume", "--run", run_id)
        assert result.code == 0
        assert_in_order([a[0] for a in sb.pw_argvs()][-12:], [
            "snapshot", "state-save", "close", "open", "state-load", "goto", "snapshot"])
        assert sb.pw_argvs("open")[-1] == ["open", "about:blank"]
        assert sb.pw_argvs("goto")[-1] == ["goto", "http://127.0.0.1:64361/"]
        assert result["observation"]["url"] == "http://127.0.0.1:64361/"

    def test_resume_without_a_handoff_exits_3(self, sb):
        run_id, _ = web_run(sb)
        result = sb.run("resume", "--run", run_id)
        assert result.code == 3 and result["error"] == "not_paused"


class TestEnd:
    def test_writes_the_reports_and_a_second_end_returns_the_same_summary(self, sb):
        run_id, obs = web_run(sb, rules=[click_rule("e4")])
        click(sb, run_id, obs["observation_id"], "e4")
        sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "pass", "--summary-stdin", stdin="counter works")
        first = sb.run("end", "--run", run_id)
        assert first.code == 0
        assert (sb.run_dir(run_id) / "report.json").is_file() and (sb.run_dir(run_id) / "report.md").is_file()
        assert Path(first["summary"]["state_left"]["final_screenshot"]).name == "final.png"
        assert (sb.run_dir(run_id) / "final.png").is_file()
        assert first["summary"]["goals"][0]["status"] == "pass"
        second = sb.run("end", "--run", run_id)
        assert second.out == first.out and second.code == 0
        assert sb.pw_argvs("close") == [["close"]]

    def test_end_takes_the_final_screenshot_before_closing_anything(self, sb):
        run_id, _ = web_run(sb)
        sb.run("end", "--run", run_id)
        names = [a[0] for a in sb.pw_argvs()]
        assert names.index("close") > len(names) - 2
        assert sb.pw_argvs("screenshot")[-1][1].endswith("final.png")

    def test_a_failed_goal_or_keep_open_leaves_the_session_and_lists_it(self, sb):
        run_id, _ = web_run(sb)
        sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "fail", "--summary-stdin", stdin="broke")
        ended = sb.run("end", "--run", run_id)
        assert sb.pw_argvs("close") == []
        assert ended["summary"]["state_left"]["kept_open"] == [f"browser session {run_id}"]

    def test_keep_open_flag(self, sb):
        run_id, _ = web_run(sb)
        ended = sb.run("end", "--run", run_id, "--keep-open")
        assert sb.pw_argvs("close") == [] and ended["summary"]["state_left"]["kept_open"]

    def test_session_key_saves_the_storage_state_with_mode_0600(self, sb):
        run_id, _ = web_run(sb, begin_args=("--session-key", "demo"))
        sb.run("end", "--run", run_id)
        saved = sb.state_root / "sessions" / "demo.json"
        assert saved.is_file() and stat.S_IMODE(saved.stat().st_mode) == 0o600
        [call] = sb.pw_argvs("state-save")
        assert Path(call[1]).parent == saved.parent
        assert list(saved.parent.iterdir()) == [saved]

    def test_the_session_file_exists_as_0600_before_the_driver_writes_it(self, sb):
        run_id, _ = web_run(sb, begin_args=("--session-key", "demo"))
        previous = os.umask(0o022)
        try:
            sb.run("end", "--run", run_id)
        finally:
            os.umask(previous)
        assert Path(str(sb.pw_scenario) + ".state_save_modes").read_text().split() == ["0o600"]

    def test_a_failed_session_save_leaves_no_session_file(self, sb):
        run_id, _ = web_run(sb, begin_args=("--session-key", "demo"), state_save="write_then_fail")
        ended = sb.run("end", "--run", run_id)
        assert ended.code == 4
        assert not (sb.state_root / "sessions" / "demo.json").exists()
        assert list((sb.state_root / "sessions").glob("*")) == []

    def test_a_failed_session_save_keeps_the_previous_session(self, sb):
        sessions = sb.state_root / "sessions"
        sessions.mkdir(parents=True)
        (sessions / "demo.json").write_text('{"cookies": ["old"]}')
        run_id, _ = web_run(sb, begin_args=("--session-key", "demo"), state_save="write_then_fail")
        sb.run("end", "--run", run_id)
        assert (sessions / "demo.json").read_text() == '{"cookies": ["old"]}'

    def test_cleanup_failure_writes_the_report_then_exits_4_and_replays(self, sb):
        run_id, _ = web_run(sb, errors=[{"on": ["close"], "stdout": "### Error\nclose failed\n"}])
        first = sb.run("end", "--run", run_id)
        assert first.code == 4 and first["driver_error"] == "cleanup_failed"
        assert (sb.run_dir(run_id) / "report.json").is_file()
        assert first["summary"]["state_left"]["cleanup_errors"]
        assert sb.run("end", "--run", run_id).code == 4

    SHEET_PAGES = {
        "idle": {"tree": NATIVE_TREE, "title": "UALA Fixture"},
        "sheet": {"tree": NATIVE_SHEET_TREE, "title": "UALA Fixture"},
    }
    ESCAPE_CLOSES_SHEET = {"cmd": "press-key", "opts": {"--key": "Escape"}, "page": "idle"}

    def sheet_run(self, sb, rules=(), **kwargs):
        return native_run(sb, pages=self.SHEET_PAGES, rules=list(rules), start="sheet", **kwargs)

    def test_end_cancels_a_sheet_the_run_left_open(self, sb):
        run_id, _ = self.sheet_run(sb, rules=[self.ESCAPE_CLOSES_SHEET])
        ended = sb.run("end", "--run", run_id)
        assert ended.code == 0
        [press] = sb.orca_commands("press-key")
        assert press["argv"][press["argv"].index("--key") + 1] == "Escape"
        assert ended["summary"]["state_left"]["kept_open"] == []

    def test_end_cancels_the_sheet_even_when_a_failed_goal_keeps_the_app_open(self, sb):
        run_id, _ = self.sheet_run(sb, rules=[self.ESCAPE_CLOSES_SHEET])
        sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "blocked",
               "--summary-stdin", stdin="stuck")
        ended = sb.run("end", "--run", run_id)
        assert len(sb.orca_commands("press-key")) == 1
        assert ended["summary"]["state_left"]["kept_open"] == []

    def test_end_without_a_sheet_sends_no_key(self, sb):
        run_id, _ = native_run(sb)
        assert sb.run("end", "--run", run_id).code == 0
        assert sb.orca_commands("press-key") == []

    def test_a_sheet_that_survives_the_cancel_is_reported_in_state_left(self, sb):
        run_id, _ = self.sheet_run(sb)
        ended = sb.run("end", "--run", run_id)
        assert len(sb.orca_commands("press-key")) == 1
        left = ended["summary"]["state_left"]["kept_open"]
        assert any("sheet" in entry for entry in left)

    def test_end_after_drift_reports_the_sheet_instead_of_taking_the_keyboard(self, sb):
        run_id, _ = self.sheet_run(sb, rules=[self.ESCAPE_CLOSES_SHEET])
        state = sb.run_json(run_id)
        state["stopped_reason"] = "drift"
        sb.write_run_json(run_id, state)
        ended = sb.run("end", "--run", run_id)
        assert sb.orca_commands("press-key") == []
        assert any("sheet" in entry for entry in ended["summary"]["state_left"]["kept_open"])

    def test_end_sends_no_key_when_another_run_took_over_the_desktop_lock(self, sb):
        run_id, _ = self.sheet_run(sb, rules=[self.ESCAPE_CLOSES_SHEET])
        assert sb.run_json(run_id)["holds_lock"] is True
        lock = _run.DesktopLock(sb.lock_path)
        lock.release(run_id)
        lock.acquire("other-run", "project", wait_s=1)
        ended = sb.run("end", "--run", run_id)
        assert sb.orca_commands("press-key") == []
        assert any("sheet" in entry for entry in ended["summary"]["state_left"]["kept_open"])
        assert lock.holder()["run_id"] == "other-run"

    def test_end_sends_no_key_when_the_lock_file_is_empty(self, sb):
        run_id, _ = self.sheet_run(sb, rules=[self.ESCAPE_CLOSES_SHEET])
        _run.DesktopLock(sb.lock_path).release(run_id)
        ended = sb.run("end", "--run", run_id)
        assert sb.orca_commands("press-key") == []
        assert any("sheet" in entry for entry in ended["summary"]["state_left"]["kept_open"])

    def test_frontmost_app_is_restored(self, sb):
        run_id, _ = native_run(sb)
        sb.set_desktop(frontmost=FIXTURE_BUNDLE)
        ended = sb.run("end", "--run", run_id)
        assert sb.desktop()["frontmost"] == USER_APP
        assert ended["summary"]["state_left"]["frontmost_restored"] is True

    def test_a_run_that_never_pasted_leaves_the_clipboard_alone_and_deletes_the_copy(self, sb):
        run_id, _ = native_run(sb)
        before = sb.desktop()
        assert (sb.run_dir(run_id) / "clipboard.txt").exists()
        ended = sb.run("end", "--run", run_id)
        assert not (sb.run_dir(run_id) / "clipboard.txt").exists()
        assert ended["summary"]["state_left"]["clipboard_restored"] is None
        assert sb.desktop()["clipboard_change_count"] == before["clipboard_change_count"]
        assert "Clipboard: not touched" in (sb.run_dir(run_id) / "report.md").read_text()


class TestPasteAndClipboard:
    def long_type(self, sb, run_id, obs_id, text):
        return act(sb, run_id, obs_id, "--action", "type", "--text-stdin", "--foreground", stdin=text)

    def test_long_text_is_pasted_and_the_clipboard_restored_at_end(self, sb):
        run_id, obs = native_run(sb)
        text = "x" * 201
        result = self.long_type(sb, run_id, obs["observation_id"], text)
        assert result.code == 0
        assert sb.orca_commands("type-text") == []
        [hotkey] = sb.orca_commands("hotkey")
        assert "CmdOrCtrl+V" in hotkey["argv"]
        desktop = sb.desktop()
        assert desktop["clipboard_text"] == text and desktop["clipboard_change_count"] == 4
        assert sb.run_json(run_id)["pasted"] is True
        ended = sb.run("end", "--run", run_id)
        assert sb.desktop()["clipboard_text"] == "users clipboard"
        assert ended["summary"]["state_left"]["clipboard_restored"] is True
        assert not (sb.run_dir(run_id) / "clipboard.txt").exists()

    def test_text_of_exactly_200_characters_is_typed(self, sb):
        run_id, obs = native_run(sb)
        text = "y" * 200
        self.long_type(sb, run_id, obs["observation_id"], text)
        [typed] = sb.orca_commands("type-text")
        assert typed["stdin"] == text
        assert sb.run_json(run_id)["pasted"] is False
        assert sb.desktop()["clipboard_change_count"] == 3

    def test_a_clipboard_that_is_not_text_only_is_never_overwritten(self, sb):
        sb.set_desktop(clipboard_text_only=False)
        run_id, obs = native_run(sb)
        self.long_type(sb, run_id, obs["observation_id"], "z" * 500)
        assert len(sb.orca_commands("type-text")) == 1
        assert sb.desktop()["clipboard_change_count"] == 3
        assert sb.run_json(run_id)["pasted"] is False

    def test_the_clipboard_is_not_restored_when_the_change_count_did_not_move(self, sb):
        run_id, _ = native_run(sb)
        state = sb.run_json(run_id)
        state["pasted"] = True
        sb.write_run_json(run_id, state)
        ended = sb.run("end", "--run", run_id)
        assert ended["summary"]["state_left"]["clipboard_restored"] is False
        assert sb.desktop()["clipboard_text"] == "users clipboard"

    def test_a_copy_made_after_the_paste_is_left_alone(self, sb):
        run_id, obs = native_run(sb)
        self.long_type(sb, run_id, obs["observation_id"], "p" * 300)
        sb.set_desktop(clipboard_change_count=9, clipboard_text="copied by the user")
        ended = sb.run("end", "--run", run_id)
        assert sb.desktop()["clipboard_text"] == "copied by the user"
        assert ended["summary"]["state_left"]["clipboard_restored"] is False

    def test_a_long_type_into_a_ref_clicks_it_first(self, sb):
        run_id, obs = native_run(sb)
        act(sb, run_id, obs["observation_id"], "--action", "type", "--ref", "5", "--text-stdin",
            "--foreground", stdin="q" * 250)
        clicks = sb.orca_commands("click")
        assert clicks[0]["argv"][clicks[0]["argv"].index("--element-index") + 1] == "5"


class TestFaults:
    def test_never_observed_turns_a_working_click_into_no_effect(self, sb):
        run_id, obs = web_run(sb, rules=[click_rule("e4")])
        assert click(sb, run_id, obs["observation_id"], "e4", LIKEUSER_FAULT="never_observed").status == "NO_EFFECT"

    def test_always_observed_calls_a_dead_button_observed(self, sb):
        run_id, obs = web_run(sb)
        assert click(sb, run_id, obs["observation_id"], "e7", LIKEUSER_FAULT="always_observed").status == "OBSERVED"

    def test_always_observed_does_not_cover_a_failed_delivery(self, sb):
        run_id, obs = web_run(sb, rules=[{"on": ["click", "e4"], "error": "boom"}])
        result = click(sb, run_id, obs["observation_id"], "e4", LIKEUSER_FAULT="always_observed")
        assert result.status == "ERROR"

    def test_skip_visibility_clicks_the_hidden_control(self, sb):
        run_id, obs = web_run(sb, visibility={"e7": "opacity"})
        result = click(sb, run_id, obs["observation_id"], "e7", LIKEUSER_FAULT="skip_visibility")
        assert result.status == "NO_EFFECT" and sb.pw_argvs("click") == [["click", "e7"]]

    def test_drop_network_registers_no_network_findings(self, sb):
        sb.web_scenario(console=["boom"], requests=[["POST", "http://127.0.0.1:1/api", 500]])
        run_id, obs = start(sb, LIKEUSER_FAULT="drop_network")
        assert obs["network_failures_new"] == [] and obs["console_errors_new"] == ["boom"]
        assert [f["kind"] for f in sb.run_json(run_id)["findings"]] == ["console"]

    def test_skip_gate_lets_a_gated_click_through(self, sb):
        run_id, obs = web_run(sb, owner="third-party")
        result = click(sb, run_id, obs["observation_id"], "e17", LIKEUSER_FAULT="skip_gate")
        assert result.status == "NO_EFFECT" and sb.pw_argvs("click") == [["click", "e17"]]

    def test_skip_stale_lets_an_old_observation_id_through(self, sb):
        run_id, obs = web_run(sb, rules=[click_rule("e4")])
        click(sb, run_id, obs["observation_id"], "e4")
        result = click(sb, run_id, obs["observation_id"], "e7", LIKEUSER_FAULT="skip_stale")
        assert result.status != "STALE"

    def test_skip_drift_lets_a_moved_cursor_through(self, sb):
        run_id, obs = native_run(sb)
        sb.set_desktop(cursor=[900.0, 900.0])
        result = click(sb, run_id, obs["observation_id"], "2", "--foreground", LIKEUSER_FAULT="skip_drift")
        assert result.status != "DRIFT" and len(sb.orca_commands("click")) == 1

    def test_allow_unverified_pass_accepts_a_pass_with_no_observed_act(self, sb):
        run_id, obs = web_run(sb)
        click(sb, run_id, obs["observation_id"], "e7")
        result = sb.run("verdict", "--run", run_id, "--goal", "g1", "--status", "pass", "--summary-stdin", stdin="x",
                        LIKEUSER_FAULT="allow_unverified_pass")
        assert result.code == 0

    def test_a_fault_disables_only_its_own_guard(self, sb):
        run_id, obs = web_run(sb, owner="third-party")
        stale = click(sb, run_id, 99, "e17", LIKEUSER_FAULT="skip_gate")
        assert stale.status == "STALE"


class TestRenewedNativeRefs:
    """Cua tokens are renewed by every snapshot, so signals must follow the element, not the token."""

    FIELD_TREE = (
        "App=dev.quirk.uala.fixture (pid 30794)\n"
        "Window: \"UALA Fixture\", App: UALA Fixture.\n\n"
        "0 standard window UALA Fixture\n"
        "\t1 text Status: idle\n"
        "\t2 button Working button\n"
        "\t3 text field (settable) Notes, Value: hello\n\n"
        "The focused UI element is 3 text field Notes."
    )
    TYPED_TREE = FIELD_TREE.replace("Value: hello", "Value: hello world")
    GONE_TREE = FIELD_TREE.replace("\t3 text field (settable) Notes, Value: hello\n", "")

    @pytest.fixture
    def renewing(self, sb, monkeypatch, capsys):
        import _native

        counter = {"n": 0}

        class RenewingDriver(_native.OrcaDriver):
            name = "cua"
            pin = "0.34.1"
            background_capable = True

            def __init__(self, session=None):
                super().__init__()
                self.session = session

            def observe(self, bundle_id, window_id, screenshot):
                obs = super().observe(bundle_id, window_id, screenshot)
                counter["n"] += 1
                rename = {ref: f"s{counter['n']:08x}:{ref}" for ref in obs.refs}
                return Observation(
                    tree_text=obs.tree_text, refs=list(rename.values()),
                    names={rename[k]: v for k, v in obs.names.items()},
                    values={rename[k]: v for k, v in obs.values.items()},
                    title=obs.title, focus=rename.get(obs.focus), screenshot_path=obs.screenshot_path,
                    scale=obs.scale, window_id=obs.window_id, bundle_id=obs.bundle_id, raw=obs.raw)

            def act(self, action, foreground):
                bare = action.ref.rsplit(":", 1)[-1] if action.ref else None
                return super().act(dataclasses.replace(action, ref=bare), True)

        pages = {"idle": {"tree": self.FIELD_TREE, "title": "UALA Fixture", "focused": 3},
                 "typed": {"tree": self.TYPED_TREE, "title": "UALA Fixture", "focused": 3},
                 "gone": {"tree": self.GONE_TREE, "title": "UALA Fixture", "focused": 0}}

        def prepare(rules):
            sb.web_scenario()
            sb.native_scenario(pages, rules=rules, bundle=FIXTURE_BUNDLE)
            for key, value in sb.env().items():
                monkeypatch.setenv(key, value)
            module = load_cli_module()
            monkeypatch.setattr(module, "get_native_driver", lambda name=None, session=None: RenewingDriver(session))

            def verb(*argv):
                code = module.main(list(argv))
                return code, json.loads(capsys.readouterr().out)

            _, out = verb("begin", "--target", FIXTURE_BUNDLE, "--surface", "native", "--owner", "yours",
                          "--attended", "--goals-file", write_goals(sb, "g1"))
            _, seen = verb("observe", "--run", out["run_id"], "--goal", "g1")
            return verb, out["run_id"], seen["observation"]["observation_id"]

        return prepare

    def field_ref(self, sb, run_id, obs_id):
        sidecar = json.loads((sb.run_dir(run_id) / f"obs-{obs_id}.json").read_text())
        return next(ref for ref, name in sidecar["names"].items() if name == "Notes")

    def click_field(self, sb, verb, run_id, obs_id, *extra):
        ref = self.field_ref(sb, run_id, obs_id)
        return verb("act", "--run", run_id, "--obs", str(obs_id), "--action", "click", "--ref", ref, *extra)

    def test_an_unchanged_value_under_a_renewed_ref_is_no_effect(self, sb, renewing):
        verb, run_id, obs_id = renewing(rules=[])
        code, result = self.click_field(sb, verb, run_id, obs_id, "--expect", "value")
        assert code == 0 and result["status"] == "NO_EFFECT", result
        assert result["signals"] == []

    def test_a_renewed_focused_ref_is_not_a_focus_change(self, sb, renewing):
        verb, run_id, obs_id = renewing(rules=[])
        _, result = self.click_field(sb, verb, run_id, obs_id)
        assert result["status"] == "NO_EFFECT" and "focus" not in result["signals"], result

    def test_a_changed_value_under_a_renewed_ref_is_observed(self, sb, renewing):
        verb, run_id, obs_id = renewing(rules=[{"cmd": "click", "page": "typed"}])
        _, result = self.click_field(sb, verb, run_id, obs_id, "--expect", "value")
        assert result["status"] == "OBSERVED" and "value" in result["signals"], result

    def test_an_element_gone_after_the_act_is_not_a_value_change(self, sb, renewing):
        verb, run_id, obs_id = renewing(rules=[{"cmd": "click", "page": "gone"}])
        _, result = self.click_field(sb, verb, run_id, obs_id, "--expect", "value")
        assert result["status"] == "NO_EFFECT" and "value" not in result["signals"], result
        assert "tree" in result["other_changes"]
