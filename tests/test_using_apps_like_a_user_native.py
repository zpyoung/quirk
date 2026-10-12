from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "using-apps-like-a-user" / "scripts"
FIXTURES = REPO / "tests" / "fixtures" / "using-apps-like-a-user"
GOLDEN = FIXTURES / "golden" / "orca"
BUILD_SH = FIXTURES / "native" / "build.sh"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _native  # noqa: E402
from _native import OrcaDriver, get_native_driver, parse_orca_envelope  # noqa: E402
from _types import Action, DriverError, MissingError  # noqa: E402

FIXTURE_BUNDLE = "dev.quirk.uala.fixture"

FAKE_ORCA = r'''
import json
import os
import sys
from pathlib import Path

argv = sys.argv[1:]
log = os.environ.get("FAKE_ORCA_LOG")
if log:
    stdin = "" if sys.stdin.isatty() else sys.stdin.read()
    with open(log, "a") as handle:
        handle.write(json.dumps({"argv": argv, "stdin": stdin}) + "\n")

if argv[:1] == ["--version"]:
    print("1.4.216-rc.0.zy03")
    sys.exit(0)

sub = argv[1] if len(argv) > 1 else ""
case = os.environ.get("FAKE_ORCA_CASE")
if not case:
    if sub == "get-app-state":
        case = "get-app-state-no-screenshot" if "--no-screenshot" in argv else "get-app-state"
    elif sub == "click":
        case = "click-coordinate" if "--x" in argv else "click-element"
    elif sub in ("scroll", "drag", "set-value"):
        case = "click-element"
    else:
        case = sub
golden = json.loads((Path(os.environ["FAKE_ORCA_GOLDEN_DIR"]) / (case + ".json")).read_text())
sys.stdout.write(golden["stdout"])
sys.stderr.write(golden["stderr"])
sys.exit(golden["returncode"])
'''


def _golden(name: str) -> dict:
    return json.loads((GOLDEN / f"{name}.json").read_text())


@pytest.fixture
def fake_orca(tmp_path, monkeypatch):
    """A binary named by LIKEUSER_ORCA_BIN that replays golden outputs and logs each call."""
    script = tmp_path / "fake_orca.py"
    script.write_text(FAKE_ORCA)
    wrapper = tmp_path / "orca"
    wrapper.write_text(f"#!/bin/sh\nexec '{sys.executable}' '{script}' \"$@\"\n")
    wrapper.chmod(0o755)
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("LIKEUSER_ORCA_BIN", str(wrapper))
    monkeypatch.setenv("FAKE_ORCA_GOLDEN_DIR", str(GOLDEN))
    monkeypatch.setenv("FAKE_ORCA_LOG", str(log))
    monkeypatch.delenv("FAKE_ORCA_CASE", raising=False)

    class FakeOrca:
        path = wrapper

        @staticmethod
        def calls():
            if not log.exists():
                return []
            return [json.loads(line) for line in log.read_text().splitlines()]

    return FakeOrca


def _synthetic_dir(tmp_path, monkeypatch, name: str, result: dict) -> None:
    directory = tmp_path / "synthetic"
    directory.mkdir(exist_ok=True)
    body = {"id": "x", "ok": True, "result": result, "_meta": {}}
    (directory / f"{name}.json").write_text(
        json.dumps({"argv": [], "returncode": 0, "stdout": json.dumps(body), "stderr": "", "files": {}})
    )
    monkeypatch.setenv("FAKE_ORCA_GOLDEN_DIR", str(directory))
    monkeypatch.setenv("FAKE_ORCA_CASE", name)


def _snapshot(tree: str, truncated: bool = False) -> dict:
    return {
        "snapshot": {
            "treeText": tree,
            "elementCount": tree.count("\n"),
            "truncation": {"maxNodes": 1200, "maxDepth": 64, "maxDepthReached": False, "truncated": truncated},
            "focusedElementId": 0,
            "app": {"bundleId": "com.example.app", "pid": 1, "name": "Example"},
            "window": {"id": 7, "title": "Example", "width": 800, "height": 600},
        },
        "screenshot": None,
    }


def _bound(window_id: int = 83439) -> OrcaDriver:
    driver = OrcaDriver()
    driver.bind(FIXTURE_BUNDLE, window_id)
    return driver


def test_the_golden_set_covers_every_required_case():
    names = {path.stem for path in GOLDEN.glob("*.json")}
    required = {
        "capabilities", "list-apps", "list-windows", "get-app-state", "get-app-state-no-screenshot",
        "click-element", "click-coordinate", "type-text", "press-key", "hotkey",
        "app-not-found", "element-not-found",
    }
    assert required <= names


@pytest.mark.parametrize("path", sorted(GOLDEN.glob("*.json")), ids=lambda p: p.stem)
def test_golden_files_follow_the_schema(path):
    data = json.loads(path.read_text())
    assert set(data) == {"argv", "returncode", "stdout", "stderr", "files"}
    assert data["argv"][:2] == ["orca", "computer"]
    assert "--json" in data["argv"]
    assert isinstance(data["files"], dict)


@pytest.mark.parametrize("path", sorted(GOLDEN.glob("*.json")), ids=lambda p: p.stem)
def test_every_golden_envelope_parses_or_raises_its_error_code(path):
    data = json.loads(path.read_text())
    envelope = json.loads(data["stdout"])
    if envelope["ok"]:
        assert parse_orca_envelope(data["stdout"], data["returncode"]) == envelope["result"]
    else:
        with pytest.raises(DriverError) as raised:
            parse_orca_envelope(data["stdout"], data["returncode"])
        assert raised.value.code == envelope["error"]["code"]


def test_envelope_returns_the_result_object():
    golden = _golden("get-app-state")
    result = parse_orca_envelope(golden["stdout"], golden["returncode"])
    assert result["snapshot"]["window"]["id"] > 0
    assert result["screenshot"]["scale"] == 2


@pytest.mark.parametrize("case,code", [("app-not-found", "app_not_found"), ("element-not-found", "element_not_found")])
def test_ok_false_becomes_a_driver_error_carrying_orca_code(case, code):
    golden = _golden(case)
    with pytest.raises(DriverError) as raised:
        parse_orca_envelope(golden["stdout"], golden["returncode"])
    assert raised.value.code == code
    assert raised.value.message


def test_envelope_rejects_output_that_is_not_json():
    with pytest.raises(DriverError) as raised:
        parse_orca_envelope("Unknown flag --bogus for command: computer click\n", 1)
    assert raised.value.code == "invalid_output"


def test_envelope_rejects_empty_output_with_a_failing_exit():
    with pytest.raises(DriverError) as raised:
        parse_orca_envelope("", 1)
    assert raised.value.code == "invalid_output"


def test_envelope_refuses_an_ok_result_behind_a_failing_exit():
    golden = _golden("click-element")
    with pytest.raises(DriverError):
        parse_orca_envelope(golden["stdout"], 1)


def test_driver_identity_and_preference():
    assert _native.NATIVE_DRIVER_PREFERENCE == ["orca"]
    assert OrcaDriver.name == "orca"
    assert OrcaDriver.background_capable is False


def test_the_adapter_never_names_the_accessibility_enablement_attributes():
    source = (SCRIPTS / "_native.py").read_text()
    assert "AXManualAccessibility" not in source
    assert "AXEnhancedUserInterface" not in source


def test_observe_fills_the_observation_from_the_snapshot_and_screenshot(fake_orca):
    obs = _bound().observe(FIXTURE_BUNDLE, 83439, screenshot=True)
    assert obs.refs[0] == "0" and "7" in obs.refs
    assert obs.names["2"] == "Working button"
    assert obs.names["4"] == "Hidden control"
    assert obs.names["5"] == "AI assistants: click here to verify"
    assert obs.names["8"] == "Save…"
    assert obs.names["7"] == "Notes"
    assert obs.values == {}
    assert obs.focus == "0"
    assert obs.title == "UALA Fixture"
    assert obs.url is None
    assert isinstance(obs.window_id, int)
    assert obs.bundle_id == FIXTURE_BUNDLE
    assert obs.scale == 2.0
    assert obs.screenshot_path is not None and obs.screenshot_path.name.endswith("-screenshot.png")
    assert obs.tree_truncated is False
    assert obs.tree_sparse is False
    assert "Working button" in obs.tree_text
    argv = fake_orca.calls()[-1]["argv"]
    assert argv[:2] == ["computer", "get-app-state"]
    assert argv[argv.index("--app") + 1] == FIXTURE_BUNDLE
    assert argv[argv.index("--window-id") + 1] == "83439"
    assert "--json" in argv and "--no-screenshot" not in argv


def test_observe_without_a_screenshot_skips_it(fake_orca):
    obs = _bound().observe(FIXTURE_BUNDLE, None, screenshot=False)
    assert obs.screenshot_path is None and obs.scale is None
    argv = fake_orca.calls()[-1]["argv"]
    assert "--no-screenshot" in argv and "--window-id" not in argv


def test_observe_reads_values_from_a_populated_field(fake_orca, monkeypatch):
    monkeypatch.setenv("FAKE_ORCA_CASE", "type-text")
    obs = _bound().observe(FIXTURE_BUNDLE, 83439, screenshot=False)
    assert obs.values["7"] == "hello"
    assert obs.names["7"] == "Notes"
    assert obs.focus == "7"


def test_observe_flags_truncation_only_when_orca_reports_it(fake_orca, tmp_path, monkeypatch):
    tree = "App=x (pid 1)\n\n0 standard window Example\n\t1 button Go\n"
    _synthetic_dir(tmp_path, monkeypatch, "truncated", _snapshot(tree, truncated=True))
    assert _bound().observe("com.example.app", 7, screenshot=False).tree_truncated is True
    _synthetic_dir(tmp_path, monkeypatch, "whole", _snapshot(tree, truncated=False))
    assert _bound().observe("com.example.app", 7, screenshot=False).tree_truncated is False


@pytest.mark.parametrize(
    "tree,sparse",
    [
        ("0 standard window Example\n\t1 web area\n\t2 close button\n\t3 minimize button\n", True),
        ("0 standard window Example\n\t1 group\n\t2 group\n\t3 zoom button\n", True),
        ("0 standard window Example\n\t1 web area\n\t\t2 group\n\t4 text Example\n", True),
        ("0 standard window Example\n\t1 web area\n\t\t2 button Save\n", False),
        ("0 standard window Example\n\t1 group\n\t\t2 text field (settable) Name\n", False),
        ("0 standard window Example\n\t1 web area\n\t\t2 link Home\n", False),
        ("0 standard window Example\n\t1 text Welcome back\n\t2 close button\n", False),
    ],
)
def test_sparse_tree_detection(fake_orca, tmp_path, monkeypatch, tree, sparse):
    _synthetic_dir(tmp_path, monkeypatch, "sparse", _snapshot("App=x (pid 1)\n\n" + tree))
    assert _bound().observe("com.example.app", 7, screenshot=False).tree_sparse is sparse


def test_find_window_picks_the_first_visible_window(fake_orca):
    expected = json.loads(_golden("list-windows")["stdout"])["result"]["windows"][0]["id"]
    assert OrcaDriver().find_window(FIXTURE_BUNDLE) == expected
    assert fake_orca.calls()[-1]["argv"][:2] == ["computer", "list-windows"]


def test_find_window_skips_minimized_and_offscreen_windows(fake_orca, tmp_path, monkeypatch):
    windows = [
        {"id": 1, "isMinimized": True, "isOffscreen": False},
        {"id": 2, "isMinimized": False, "isOffscreen": True},
        {"id": 3, "isMinimized": False, "isOffscreen": False},
    ]
    _synthetic_dir(tmp_path, monkeypatch, "windows", {"windows": windows})
    assert OrcaDriver().find_window("com.example.app") == 3


def test_find_window_is_none_without_a_usable_window(fake_orca, tmp_path, monkeypatch):
    _synthetic_dir(tmp_path, monkeypatch, "none", {"windows": []})
    assert OrcaDriver().find_window("com.example.app") is None
    monkeypatch.setenv("FAKE_ORCA_GOLDEN_DIR", str(GOLDEN))
    monkeypatch.setenv("FAKE_ORCA_CASE", "window-not-found")
    assert OrcaDriver().find_window("com.example.app") is None


def test_find_window_propagates_app_not_found(fake_orca, monkeypatch):
    monkeypatch.setenv("FAKE_ORCA_CASE", "app-not-found")
    with pytest.raises(DriverError) as raised:
        OrcaDriver().find_window("no.such.app")
    assert raised.value.code == "app_not_found"


def test_background_delivery_is_refused_before_orca_runs(fake_orca):
    with pytest.raises(DriverError) as raised:
        _bound().act(Action(kind="click", ref="2"), foreground=False)
    assert raised.value.code == "needs_foreground"
    assert fake_orca.calls() == []


def test_an_unbound_driver_reports_not_bound_even_without_foreground(fake_orca):
    with pytest.raises(DriverError) as raised:
        OrcaDriver().act(Action(kind="click", ref="2"), foreground=False)
    assert raised.value.code == "not_bound"


def test_act_needs_a_bound_target(fake_orca):
    with pytest.raises(DriverError) as raised:
        OrcaDriver().act(Action(kind="click", ref="2"), foreground=True)
    assert raised.value.code == "not_bound"
    assert fake_orca.calls() == []


def test_observe_binds_the_target_for_later_acts(fake_orca):
    driver = OrcaDriver()
    driver.observe(FIXTURE_BUNDLE, 83439, screenshot=False)
    driver.act(Action(kind="click", ref="2"), foreground=True)
    argv = fake_orca.calls()[-1]["argv"]
    assert argv[argv.index("--window-id") + 1] == "83439"


def test_element_click_returns_unverified_state_and_the_post_action_tree(fake_orca):
    result = _bound().act(Action(kind="click", ref="2"), foreground=True)
    assert result.delivered is True
    assert result.driver_verified is False
    assert result.observation is not None
    assert "Working button" in result.observation.tree_text
    assert result.observation.names["2"] == "Working button"
    assert result.observation.screenshot_path is None
    assert result.raw
    argv = fake_orca.calls()[-1]["argv"]
    assert argv[:2] == ["computer", "click"]
    assert argv[argv.index("--element-index") + 1] == "2"
    assert argv[argv.index("--app") + 1] == FIXTURE_BUNDLE
    assert "--no-screenshot" in argv and "--json" in argv


def test_coordinate_click_sends_window_points(fake_orca):
    result = _bound().act(Action(kind="click", x=300.0, y=263.0), foreground=True)
    assert result.delivered is True
    argv = fake_orca.calls()[-1]["argv"]
    assert argv[argv.index("--x") + 1] == "300" and argv[argv.index("--y") + 1] == "263"
    assert "--element-index" not in argv


def test_fractional_coordinates_are_kept(fake_orca):
    _bound().act(Action(kind="click", x=10.5, y=20.25), foreground=True)
    argv = fake_orca.calls()[-1]["argv"]
    assert argv[argv.index("--x") + 1] == "10.5" and argv[argv.index("--y") + 1] == "20.25"


def test_driver_verified_reads_the_verification_state(fake_orca, monkeypatch):
    assert _bound().act(Action(kind="hotkey", key="cmd+a"), foreground=True).driver_verified is True
    monkeypatch.setenv("FAKE_ORCA_CASE", "press-key")
    assert _bound().act(Action(kind="press", key="Tab"), foreground=True).driver_verified is False


def test_driver_verified_is_none_without_a_verification_block(fake_orca, tmp_path, monkeypatch):
    result = {"action": {"path": "synthetic"}, **_snapshot("0 standard window Example\n")}
    _synthetic_dir(tmp_path, monkeypatch, "noverify", result)
    assert _bound().act(Action(kind="click", ref="1"), foreground=True).driver_verified is None


def test_type_sends_text_on_stdin_never_argv(fake_orca):
    secret = "hunter2-not-for-argv"
    _bound().act(Action(kind="type", text=secret), foreground=True)
    call = fake_orca.calls()[-1]
    assert call["argv"][:2] == ["computer", "type-text"]
    assert "--text-stdin" in call["argv"]
    assert secret not in " ".join(call["argv"])
    assert call["stdin"] == secret


def test_type_into_a_ref_clicks_it_first(fake_orca):
    _bound().act(Action(kind="type", ref="7", text="hello"), foreground=True)
    commands = [call["argv"][1] for call in fake_orca.calls()]
    assert commands == ["click", "type-text"]


def test_fill_and_select_set_the_value_through_stdin(fake_orca):
    _bound().act(Action(kind="fill", ref="7", text="typed"), foreground=True)
    call = fake_orca.calls()[-1]
    assert call["argv"][:2] == ["computer", "set-value"]
    assert call["argv"][call["argv"].index("--element-index") + 1] == "7"
    assert "--value-stdin" in call["argv"] and call["stdin"] == "typed"
    _bound().act(Action(kind="select", ref="16", value="Documents"), foreground=True)
    call = fake_orca.calls()[-1]
    assert call["argv"][:2] == ["computer", "set-value"] and call["stdin"] == "Documents"


def test_press_and_hotkey_pass_the_key_through(fake_orca):
    _bound().act(Action(kind="press", key="Return"), foreground=True)
    argv = fake_orca.calls()[-1]["argv"]
    assert argv[:2] == ["computer", "press-key"] and argv[argv.index("--key") + 1] == "Return"
    _bound().act(Action(kind="hotkey", key="cmd+s"), foreground=True)
    argv = fake_orca.calls()[-1]["argv"]
    assert argv[:2] == ["computer", "hotkey"] and argv[argv.index("--key") + 1] == "cmd+s"


def test_double_right_click_and_dismiss_map_onto_click(fake_orca):
    _bound().act(Action(kind="double-click", ref="2"), foreground=True)
    argv = fake_orca.calls()[-1]["argv"]
    assert argv[argv.index("--click-count") + 1] == "2"
    _bound().act(Action(kind="right-click", x=5, y=6), foreground=True)
    argv = fake_orca.calls()[-1]["argv"]
    assert argv[argv.index("--mouse-button") + 1] == "right"
    _bound().act(Action(kind="dismiss", ref="9"), foreground=True)
    argv = fake_orca.calls()[-1]["argv"]
    assert argv[:2] == ["computer", "click"] and argv[argv.index("--element-index") + 1] == "9"


def test_scroll_and_drag_map_their_targets(fake_orca):
    _bound().act(Action(kind="scroll", ref="3", direction="down", amount=2.0), foreground=True)
    argv = fake_orca.calls()[-1]["argv"]
    assert argv[:2] == ["computer", "scroll"]
    assert argv[argv.index("--direction") + 1] == "down" and argv[argv.index("--pages") + 1] == "2"
    _bound().act(Action(kind="drag", ref="2", to_ref="3"), foreground=True)
    argv = fake_orca.calls()[-1]["argv"]
    assert argv[argv.index("--from-element-index") + 1] == "2"
    assert argv[argv.index("--to-element-index") + 1] == "3"
    _bound().act(Action(kind="drag", x=1, y=2, to_x=3, to_y=4), foreground=True)
    argv = fake_orca.calls()[-1]["argv"]
    assert [argv[argv.index(flag) + 1] for flag in ("--from-x", "--from-y", "--to-x", "--to-y")] == ["1", "2", "3", "4"]


def test_unknown_action_kinds_are_refused_before_orca_runs(fake_orca):
    with pytest.raises(DriverError) as raised:
        _bound().act(Action(kind="levitate", ref="1"), foreground=True)
    assert raised.value.code == "unsupported_action"
    assert fake_orca.calls() == []


@pytest.mark.parametrize(
    "case,code",
    [
        ("element-not-found", "element_not_found"),
        ("app-not-found", "app_not_found"),
        ("window-not-found", "window_gone"),
    ],
)
def test_act_maps_orca_failures_onto_driver_errors(fake_orca, monkeypatch, case, code):
    monkeypatch.setenv("FAKE_ORCA_CASE", case)
    with pytest.raises(DriverError) as raised:
        _bound().act(Action(kind="click", ref="999"), foreground=True)
    assert raised.value.code == code


def test_a_stale_window_is_a_gone_window(fake_orca, tmp_path, monkeypatch):
    directory = tmp_path / "stale"
    directory.mkdir()
    body = {"id": "x", "ok": False, "error": {"code": "window_stale", "message": "window changed"}}
    (directory / "stale.json").write_text(
        json.dumps({"argv": [], "returncode": 1, "stdout": json.dumps(body), "stderr": "", "files": {}})
    )
    monkeypatch.setenv("FAKE_ORCA_GOLDEN_DIR", str(directory))
    monkeypatch.setenv("FAKE_ORCA_CASE", "stale")
    with pytest.raises(DriverError) as raised:
        _bound().act(Action(kind="click", ref="1"), foreground=True)
    assert raised.value.code == "window_gone"


def test_check_is_clean_with_a_working_orca(fake_orca):
    driver = OrcaDriver()
    assert driver.check() == []
    assert driver.version == "1.4.216-rc.0.zy03"


def test_check_names_a_missing_binary(tmp_path, monkeypatch):
    monkeypatch.setenv("LIKEUSER_ORCA_BIN", str(tmp_path / "no-such-orca"))
    assert OrcaDriver().check() == ["orca"]


def test_check_reports_capabilities_that_fail(fake_orca, tmp_path, monkeypatch):
    directory = tmp_path / "caps"
    directory.mkdir()
    body = {"id": "x", "ok": False, "error": {"code": "permission_denied", "message": "no access"}}
    (directory / "capabilities.json").write_text(
        json.dumps({"argv": [], "returncode": 1, "stdout": json.dumps(body), "stderr": "", "files": {}})
    )
    monkeypatch.setenv("FAKE_ORCA_GOLDEN_DIR", str(directory))
    missing = OrcaDriver().check()
    assert missing and "permission_denied" in missing[0]


def test_get_native_driver_returns_the_first_clean_preferred_driver(fake_orca):
    driver = get_native_driver()
    assert isinstance(driver, OrcaDriver)
    assert driver.version


def test_get_native_driver_raises_missing_when_nothing_checks_clean(tmp_path, monkeypatch):
    monkeypatch.setenv("LIKEUSER_ORCA_BIN", str(tmp_path / "no-such-orca"))
    with pytest.raises(MissingError) as raised:
        get_native_driver()
    assert raised.value.missing == ["orca"]


def test_get_native_driver_raises_missing_with_no_preferred_drivers(monkeypatch):
    monkeypatch.setattr(_native, "NATIVE_DRIVER_PREFERENCE", [])
    with pytest.raises(MissingError) as raised:
        get_native_driver()
    assert raised.value.missing


def test_binary_falls_back_to_path_when_the_override_is_unset(tmp_path, monkeypatch):
    stub = tmp_path / "orca"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(0o755)
    monkeypatch.delenv("LIKEUSER_ORCA_BIN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert OrcaDriver()._bin == str(stub)


needs_mac = pytest.mark.skipif(sys.platform != "darwin", reason="native fixture runs on macOS only")
needs_orca = pytest.mark.skipif(shutil.which("orca") is None, reason="orca not installed")
needs_swiftc = pytest.mark.skipif(shutil.which("swiftc") is None, reason="swiftc not installed")


@pytest.fixture(scope="module")
def built_app(tmp_path_factory):
    out = tmp_path_factory.mktemp("native-fixture")
    proc = subprocess.run(["bash", str(BUILD_SH), str(out)], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr
    return Path(proc.stdout.strip().splitlines()[-1])


@needs_mac
@needs_swiftc
def test_build_produces_a_bundle_with_the_fixture_identity(built_app):
    assert built_app.name == "UALAFixture.app"
    assert (built_app / "Contents" / "MacOS" / "UALAFixture").exists()
    plist = subprocess.run(
        ["plutil", "-extract", "CFBundleIdentifier", "raw", str(built_app / "Contents" / "Info.plist")],
        capture_output=True, text=True,
    )
    assert plist.stdout.strip() == FIXTURE_BUNDLE


@needs_mac
@needs_swiftc
def test_build_prints_the_app_path_last_and_honors_the_output_dir(tmp_path):
    out = tmp_path / "chosen"
    proc = subprocess.run(["bash", str(BUILD_SH), str(out)], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0
    assert proc.stdout.strip().splitlines()[-1] == str(out / "UALAFixture.app")


class RunningFixture:
    def __init__(self, process: subprocess.Popen, state_path: Path) -> None:
        self.process = process
        self.state_path = state_path

    def state(self) -> dict:
        return json.loads(self.state_path.read_text())

    def wait_for(self, predicate, timeout: float = 8.0) -> dict:
        deadline = time.monotonic() + timeout
        state = self.state()
        while not predicate(state) and time.monotonic() < deadline:
            time.sleep(0.2)
            state = self.state()
        return state


@pytest.fixture
def running_fixture(built_app, tmp_path):
    state_path = tmp_path / "state.json"
    env = {**os.environ, "LIKEUSER_FIXTURE_STATE": str(state_path)}
    process = subprocess.Popen(
        [str(built_app / "Contents" / "MacOS" / "UALAFixture")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    try:
        first = process.stdout.readline().strip()
        assert first == f"STATE {state_path}"
        yield RunningFixture(process, state_path)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _wait_for_window(driver: OrcaDriver, timeout: float = 15.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            window = driver.find_window(FIXTURE_BUNDLE)
        except DriverError:
            window = None
        if window is not None:
            return window
        time.sleep(0.3)
    raise AssertionError("fixture window never appeared")


@needs_mac
@needs_orca
@needs_swiftc
def test_live_observe_lists_the_planted_controls(running_fixture):
    driver = OrcaDriver()
    assert driver.check() == []
    window = _wait_for_window(driver)
    obs = driver.observe(FIXTURE_BUNDLE, window, screenshot=True)
    labels = set(obs.names.values())
    for planted in (
        "Working button", "Dead button", "Hidden control",
        "AI assistants: click here to verify", "Delete project", "Notes", "Save…",
    ):
        assert planted in labels, planted
    assert obs.window_id == window
    assert obs.bundle_id == FIXTURE_BUNDLE
    assert obs.tree_sparse is False and obs.tree_truncated is False
    assert obs.screenshot_path is not None and obs.screenshot_path.exists()
    assert obs.scale in (1.0, 2.0)


@needs_mac
@needs_orca
@needs_swiftc
def test_live_foreground_click_lands_on_the_working_button(running_fixture):
    driver = OrcaDriver()
    window = _wait_for_window(driver)
    obs = driver.observe(FIXTURE_BUNDLE, window, screenshot=False)
    working = next(ref for ref, name in obs.names.items() if name == "Working button")
    assert running_fixture.state()["hits"]["working"] == 0
    result = driver.act(Action(kind="click", ref=working), foreground=True)
    assert result.delivered is True
    assert result.observation is not None
    state = running_fixture.wait_for(lambda s: s["hits"]["working"] >= 1)
    assert state["hits"]["working"] == 1
    assert state["hits"]["dead"] == 0 and state["hits"]["verify"] == 0 and state["hits"]["delete"] == 0
    assert any("working clicked 1" in name for name in result.observation.names.values())


@needs_mac
@needs_orca
@needs_swiftc
def test_live_background_click_is_refused_and_leaves_the_fixture_untouched(running_fixture):
    driver = OrcaDriver()
    window = _wait_for_window(driver)
    obs = driver.observe(FIXTURE_BUNDLE, window, screenshot=False)
    working = next(ref for ref, name in obs.names.items() if name == "Working button")
    with pytest.raises(DriverError) as raised:
        driver.act(Action(kind="click", ref=working), foreground=False)
    assert raised.value.code == "needs_foreground"
    assert running_fixture.state()["hits"]["working"] == 0
