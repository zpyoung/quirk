from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "using-apps-like-a-user" / "scripts"
FIXTURES = REPO / "tests" / "fixtures" / "using-apps-like-a-user"
GOLDEN = FIXTURES / "golden" / "orca"
GOLDEN_CUA = FIXTURES / "golden" / "cua"
BUILD_SH = FIXTURES / "native" / "build.sh"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _desktop  # noqa: E402
import _effects  # noqa: E402
import _native  # noqa: E402
from _native import CuaDriver, OrcaDriver, get_native_driver, parse_orca_envelope  # noqa: E402
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


@pytest.fixture(autouse=True)
def no_cua_unless_asked(tmp_path, monkeypatch):
    """Keep every test off the real Cua Driver and the shared cache directory."""
    monkeypatch.setenv("LIKEUSER_NATIVE_BIN", str(tmp_path / "no-such-cua-driver"))
    cache_root = tmp_path / "tmp"
    cache_root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(cache_root))


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
    assert _native.NATIVE_DRIVER_PREFERENCE == ["cua", "orca"]
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


@pytest.mark.parametrize(
    "tree,sheet_open",
    [
        ("0 standard window Example\n\t1 sheet Save\n\t\t2 button Save\n", True),
        ("0 standard window Example\n\t1 dialog Open\n", True),
        ("0 standard window Example\n\t1 system dialog\n", True),
        ("0 standard window Example\n\t1 button Sheet music\n", False),
        ("0 standard window Example\n\t1 group\n\t\t2 button Dialog\n", False),
    ],
)
def test_orca_observe_reports_an_open_sheet_from_its_own_tree_format(fake_orca, tmp_path, monkeypatch, tree, sheet_open):
    _synthetic_dir(tmp_path, monkeypatch, "sheet", _snapshot("App=x (pid 1)\n\n" + tree))
    assert _bound().observe("com.example.app", 7, screenshot=False).sheet_open is sheet_open


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
    assert raised.value.missing == ["cua-driver", "orca"]


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


FAKE_CUA = r'''
import json
import os
import sys
from pathlib import Path

argv = sys.argv[1:]
golden_dir = Path(os.environ["FAKE_CUA_GOLDEN_DIR"])
log = Path(os.environ["FAKE_CUA_LOG"])
before = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
stdin_text = "" if sys.stdin.isatty() else sys.stdin.read()
with log.open("a") as handle:
    handle.write(json.dumps({"argv": argv, "stdin": stdin_text}) + "\n")


def golden(name):
    return json.loads((golden_dir / (name + ".json")).read_text())


def emit(stdout, returncode=0, stderr=""):
    sys.stdout.write(stdout if isinstance(stdout, str) else json.dumps(stdout))
    sys.stderr.write(stderr)
    sys.exit(returncode)


if argv[:1] == ["--version"]:
    emit(os.environ.get("FAKE_CUA_VERSION", "cua-driver 0.34.1") + "\n")
if argv[:1] == ["status"]:
    emit(os.environ.get("FAKE_CUA_STATUS", "Cua Driver daemon is running\n  socket: /tmp/x.sock\n"),
         int(os.environ.get("FAKE_CUA_STATUS_RC", "0")))
if argv[:2] == ["permissions", "status"]:
    emit(os.environ.get("FAKE_CUA_PERMISSIONS") or golden("permissions-status")["stdout"])
if argv[:1] != ["call"]:
    emit("unknown command\n", 2)

if len(argv) != 2:
    emit("the payload belongs on stdin\n", 2)
tool, payload = argv[1], json.loads(stdin_text)
prior = sum(1 for entry in before if entry["argv"][:2] == ["call", tool])
replies = json.loads(os.environ.get("FAKE_CUA_REPLIES", "{}")).get(tool)
if isinstance(replies, list):
    replies = replies[min(prior, len(replies) - 1)]
if replies is not None:
    emit(replies["stdout"], replies.get("returncode", 0), replies.get("stderr", ""))

case = {
    "get_window_state": "observe-screenshot", "type_text": "type-text", "press_key": "press-key",
    "hotkey": "hotkey", "list_windows": "list-windows",
    "get_accessibility_tree": "get-accessibility-tree-sheets",
}.get(tool, "click-coordinate" if "x" in payload else "click-element")
reply = golden(case)
out = reply["stdout"]
if tool == "get_window_state":
    data = json.loads(out)
    target = payload.get("screenshot_out_file")
    if target:
        Path(target).write_bytes(b"\x89PNG fake")
        data["screenshot_file_path"] = target
    else:
        for key in ("screenshot_file_path", "screenshot_width", "screenshot_height", "screenshot_scale", "capture_id"):
            data.pop(key, None)
    out = json.dumps(data)
emit(out, reply["returncode"], reply["stderr"])
'''

FAKE_LSAPPINFO = """#!/bin/sh
case "$*" in
  *"$FAKE_LSAPPINFO_BUNDLE"*) echo "\\"pid\\"=$FAKE_LSAPPINFO_PID" ;;
esac
"""

GOLDEN_PID = 82986
GOLDEN_WINDOW = 84869


@pytest.fixture
def fake_cua(tmp_path, monkeypatch):
    """A binary named by LIKEUSER_NATIVE_BIN that replays golden/cua outputs and logs each call."""
    script = tmp_path / "fake_cua.py"
    script.write_text(FAKE_CUA)
    wrapper = tmp_path / "cua-driver"
    wrapper.write_text(f"#!/bin/sh\nexec '{sys.executable}' '{script}' \"$@\"\n")
    wrapper.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    lsappinfo = bin_dir / "lsappinfo"
    lsappinfo.write_text(FAKE_LSAPPINFO)
    lsappinfo.chmod(0o755)
    log = tmp_path / "cua-calls.jsonl"
    monkeypatch.setenv("LIKEUSER_NATIVE_BIN", str(wrapper))
    monkeypatch.setenv("FAKE_CUA_GOLDEN_DIR", str(GOLDEN_CUA))
    monkeypatch.setenv("FAKE_CUA_LOG", str(log))
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_LSAPPINFO_BUNDLE", FIXTURE_BUNDLE)
    monkeypatch.setenv("FAKE_LSAPPINFO_PID", str(GOLDEN_PID))
    for name in ("FAKE_CUA_REPLIES", "FAKE_CUA_VERSION", "FAKE_CUA_STATUS", "FAKE_CUA_STATUS_RC", "FAKE_CUA_PERMISSIONS"):
        monkeypatch.delenv(name, raising=False)

    class FakeCua:
        path = wrapper

        @staticmethod
        def entries():
            if not log.exists():
                return []
            return [json.loads(line) for line in log.read_text().splitlines()]

        @staticmethod
        def calls():
            return [entry["argv"] for entry in FakeCua.entries()]

        @staticmethod
        def tool_calls(tool=None):
            found = [(e["argv"][1], json.loads(e["stdin"])) for e in FakeCua.entries() if e["argv"][:1] == ["call"]]
            return [item for item in found if tool is None or item[0] == tool]

        @staticmethod
        def reply(**tools):
            monkeypatch.setenv("FAKE_CUA_REPLIES", json.dumps(tools))

    return FakeCua


def _cua_golden(name: str) -> dict:
    return json.loads((GOLDEN_CUA / f"{name}.json").read_text())


def _bound_cua(window_id: int = GOLDEN_WINDOW, observed: bool = False) -> CuaDriver:
    """A bound driver on the shared test session, so separate instances stand in for later processes."""
    driver = CuaDriver(session="test-run")
    driver.bind(FIXTURE_BUNDLE, window_id)
    if observed:
        driver.observe(FIXTURE_BUNDLE, window_id, screenshot=True)
    return driver


def _elements(rows) -> list:
    """Build `elements` from (role, label, value, parent_index) rows; the index is the row number."""
    elements = []
    for index, (role, label, value, parent) in enumerate(rows):
        element = {
            "element_index": index, "element_token": f"s0000000a:{index}", "role": role, "label": label,
            "screenshot_frame": {"x": 100 * index, "y": 50, "w": 40, "h": 20},
        }
        if value is not None:
            element["value"] = value
        if parent is not None:
            element["parent_index"] = parent
        elements.append(element)
    return elements


def _window_state(rows, markdown, shot=True, **extra) -> dict:
    data = {
        "elements": _elements(rows), "tree_markdown": markdown, "window_id": 7, "window_title": "Example",
        "window_bounds": {"x": 0, "y": 0, "width": 800.0, "height": 600.0}, "truncated": False,
        "snapshot_id": "s0000000a",
    }
    if shot:
        data.update(screenshot_file_path="/tmp/x/shot.png", screenshot_width=1600, screenshot_height=1200)
    data.update(extra)
    return data


def _ok(body) -> dict:
    return {"stdout": body, "returncode": 0}


MENU_ROWS = [
    ("AXWindow", "Example", None, None),
    ("AXButton", "Go", None, 0),
    ("AXMenuBar", None, None, None),
    ("AXMenuBarItem", "File", None, 2),
    ("AXMenuItem", "secret-recent-document.txt", None, 3),
]
MENU_MARKDOWN = "\n".join([
    '- [0] AXWindow "Example"',
    '  - [1] AXButton "Go" [actions=[press]]',
    "- [2] AXMenuBar [actions=[cancel]]",
    '  - [3] AXMenuBarItem "File"',
    '    - [4] AXMenuItem "secret-recent-document.txt"',
])
SHEET_ROWS = [
    ("AXWindow", "Example", None, None),
    ("AXButton", "Open", None, 0),
    ("AXSheet", None, None, 0),
    ("AXTextField", "Name", "", 2),
    ("AXButton", "Save", None, 2),
]
SHEET_MARKDOWN = "\n".join([
    '- [0] AXWindow "Example"',
    '  - [1] AXButton "Open" [actions=[press]]',
    "  - [2] AXSheet",
    '    - [3] AXTextField "Name"',
    '    - [4] AXButton "Save" [actions=[press]]',
])


def test_cua_golden_set_follows_the_schema():
    names = {path.stem for path in GOLDEN_CUA.glob("*.json")}
    assert {
        "observe-screenshot", "click-element", "click-coordinate", "type-text", "press-key", "hotkey",
        "click-missing-element", "permissions-status", "list-windows", "list-windows-sheets",
        "get-accessibility-tree-sheets",
    } <= names
    for path in GOLDEN_CUA.glob("*.json"):
        data = json.loads(path.read_text())
        assert set(data) == {"argv", "returncode", "stdout", "stderr", "files"}
        assert data["argv"][0] == "cua-driver"


def test_cua_driver_identity():
    assert CuaDriver.name == "cua"
    assert CuaDriver.background_capable is True
    assert issubclass(CuaDriver, _native.NativeDriver)


def test_cua_binary_comes_from_the_override_then_path(tmp_path, monkeypatch):
    monkeypatch.setenv("LIKEUSER_NATIVE_BIN", "/somewhere/cua")
    assert CuaDriver()._bin == "/somewhere/cua"
    stub = tmp_path / "cua-driver"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(0o755)
    monkeypatch.delenv("LIKEUSER_NATIVE_BIN")
    monkeypatch.setenv("PATH", str(tmp_path))
    assert CuaDriver()._bin == str(stub)


def test_cua_check_is_clean_and_never_grants_permissions(fake_cua):
    driver = CuaDriver()
    assert driver.check() == []
    assert driver.version == "0.34.1"
    assert ["permissions", "status", "--json"] in fake_cua.calls()
    assert not any("grant" in argv for argv in fake_cua.calls())


def test_cua_check_names_a_missing_binary(tmp_path):
    assert CuaDriver().check() == ["cua-driver"]


@pytest.mark.parametrize("version,clean", [("0.34.0", False), ("0.33.9", False), ("0.34.1", True), ("0.35.0", True), ("1.0.0", True)])
def test_cua_check_enforces_the_version_pin(fake_cua, monkeypatch, version, clean):
    monkeypatch.setenv("FAKE_CUA_VERSION", f"cua-driver {version}")
    missing = CuaDriver().check()
    assert (missing == []) is clean
    if not clean:
        assert "0.34.1" in missing[0]


def test_cua_check_reports_an_unreadable_version(fake_cua, monkeypatch):
    monkeypatch.setenv("FAKE_CUA_VERSION", "garbage")
    assert CuaDriver().check() == ["cua-driver version unreadable"]


@pytest.mark.parametrize("status,code", [("Cua Driver daemon is not running\n", 0), ("", 1), ("Cua Driver daemon is running\n", 1)])
def test_cua_check_requires_the_daemon(fake_cua, monkeypatch, status, code):
    monkeypatch.setenv("FAKE_CUA_STATUS", status)
    monkeypatch.setenv("FAKE_CUA_STATUS_RC", str(code))
    assert CuaDriver().check() == ["cua-driver daemon not running"]
    assert ["permissions", "status", "--json"] not in fake_cua.calls()


@pytest.mark.parametrize(
    "perms,expected",
    [
        ({"accessibility": False, "screen_recording": True}, ["Accessibility"]),
        ({"accessibility": True, "screen_recording": False}, ["Screen Recording"]),
        ({"accessibility": False, "screen_recording": False}, ["Accessibility", "Screen Recording"]),
        ({"accessibility": "unknown", "screen_recording": True}, ["Accessibility"]),
        ({"screen_recording": True}, ["Accessibility"]),
    ],
)
def test_cua_check_requires_both_permissions(fake_cua, monkeypatch, perms, expected):
    monkeypatch.setenv("FAKE_CUA_PERMISSIONS", json.dumps(perms))
    missing = CuaDriver().check()
    assert len(missing) == len(expected)
    for gap, name in zip(missing, expected):
        assert name in gap


def test_cua_check_reports_unreadable_permissions(fake_cua, monkeypatch):
    monkeypatch.setenv("FAKE_CUA_PERMISSIONS", "not json")
    assert CuaDriver().check() == ["cua-driver permissions unreadable"]


def test_cua_observe_fills_the_observation_from_the_golden_capture(fake_cua):
    obs = _bound_cua().observe(FIXTURE_BUNDLE, GOLDEN_WINDOW, screenshot=True)
    token = {name: ref for ref, name in obs.names.items() if name}
    assert obs.refs[0] == "s0000000f:0" and "s0000000f:7" in obs.refs
    assert token["Working button"] == "s0000000f:1"
    assert token["Hidden control"] == "s0000000f:3"
    assert token["AI assistants: click here to verify"] == "s0000000f:4"
    assert token["Delete project"] == "s0000000f:5"
    assert token["Notes"] == "s0000000f:6" and token["Save…"] == "s0000000f:7"
    assert obs.values == {"s0000000f:6": "Notes"}
    assert obs.title == "UALA Fixture"
    assert obs.window_id == GOLDEN_WINDOW and obs.bundle_id == FIXTURE_BUNDLE
    assert obs.url is None and obs.focus is None
    assert obs.tree_truncated is False and obs.tree_sparse is False
    assert obs.raw
    assert 'AXButton "Working button"' in obs.tree_text


def test_cua_observe_computes_scale_from_screenshot_width_and_window_width(fake_cua):
    obs = _bound_cua().observe(FIXTURE_BUNDLE, GOLDEN_WINDOW, screenshot=True)
    assert obs.scale == pytest.approx(1568 / 900)
    assert obs.screenshot_path is not None and obs.screenshot_path.is_absolute()
    assert obs.screenshot_path.exists()
    payload = fake_cua.tool_calls("get_window_state")[-1][1]
    assert payload["screenshot_out_file"] == str(obs.screenshot_path)
    assert payload["pid"] == GOLDEN_PID and payload["window_id"] == GOLDEN_WINDOW
    assert "include_screenshot" not in payload


def test_cua_observe_without_a_screenshot_skips_it(fake_cua):
    obs = _bound_cua().observe(FIXTURE_BUNDLE, GOLDEN_WINDOW, screenshot=False)
    assert obs.screenshot_path is None and obs.scale is None
    payload = fake_cua.tool_calls("get_window_state")[-1][1]
    assert payload["include_screenshot"] is False and "screenshot_out_file" not in payload


def test_cua_observe_adopts_the_first_on_screen_window_when_none_is_bound(fake_cua):
    driver = CuaDriver()
    obs = driver.observe(FIXTURE_BUNDLE, None, screenshot=False)
    assert obs.window_id == GOLDEN_WINDOW
    assert [tool for tool, _ in fake_cua.tool_calls()][:2] == ["list_windows", "get_window_state"]


def test_cua_every_call_carries_one_stable_session_and_the_bound_target(fake_cua):
    driver = _bound_cua()
    driver.observe(FIXTURE_BUNDLE, GOLDEN_WINDOW, screenshot=False)
    driver.act(Action(kind="click", ref="s0000000f:1"), foreground=False)
    driver.find_window(FIXTURE_BUNDLE)
    calls = fake_cua.tool_calls()
    assert len(calls) == 3
    assert {payload["session"] for _, payload in calls} == {driver.session}
    assert driver.session
    for tool, payload in calls:
        assert payload["pid"] == GOLDEN_PID
        if tool != "list_windows":
            assert payload["window_id"] == GOLDEN_WINDOW


def test_cua_instances_get_distinct_sessions_unless_one_is_given():
    assert CuaDriver().session != CuaDriver().session
    assert CuaDriver(session="run-a").session == "run-a"


def test_cua_sessions_keep_separate_memos_and_screenshots(fake_cua):
    first, second = CuaDriver(session="run-a"), CuaDriver(session="run-b")
    for driver in (first, second):
        driver.bind(FIXTURE_BUNDLE, GOLDEN_WINDOW)
        driver.observe(FIXTURE_BUNDLE, GOLDEN_WINDOW, screenshot=True)
    assert first._memo_path() != second._memo_path()
    assert first._memo_path().is_file() and second._memo_path().is_file()
    shots = {call[1]["screenshot_out_file"] for call in fake_cua.tool_calls("get_window_state")}
    assert len(shots) == 2


def test_cua_memo_survives_into_a_fresh_instance_with_the_same_session(fake_cua):
    first = CuaDriver(session="run-a")
    first.bind(FIXTURE_BUNDLE, GOLDEN_WINDOW)
    first.observe(FIXTURE_BUNDLE, GOLDEN_WINDOW, screenshot=True)
    later = CuaDriver(session="run-a")
    later.bind(FIXTURE_BUNDLE, GOLDEN_WINDOW)
    assert later._recall() is not None
    stranger = CuaDriver(session="run-b")
    stranger.bind(FIXTURE_BUNDLE, GOLDEN_WINDOW)
    assert stranger._recall() is None


def test_cua_payload_goes_on_stdin_and_never_in_argv(fake_cua):
    secret = "hunter2-do-not-leak"
    driver = _bound_cua()
    driver.act(Action(kind="fill", ref="s0000000f:1", text=secret), foreground=False)
    [entry] = [e for e in fake_cua.entries() if e["argv"][:2] == ["call", "set_value"]]
    assert entry["argv"] == ["call", "set_value"]
    assert json.loads(entry["stdin"])["value"] == secret
    assert not any(secret in part for argv in fake_cua.calls() for part in argv)


def test_cua_close_ends_the_session_and_deletes_its_cache_files(fake_cua):
    driver = _bound_cua(observed=True)
    driver.act(Action(kind="click", ref="s0000000f:1"), foreground=False)
    probe = driver._session_file("-probe.png")
    probe.write_bytes(b"x")
    assert driver._memo_path().is_file()
    driver.close()
    [(_, payload)] = fake_cua.tool_calls("end_session")
    assert payload == {"session": driver.session}
    assert not driver._memo_path().exists() and not probe.exists()
    assert not driver._session_file("-shot.png").exists()
    assert driver._recall() is None


def test_cua_close_still_deletes_files_when_ending_the_session_fails(fake_cua):
    driver = _bound_cua(observed=True)
    fake_cua.reply(end_session={"stdout": "boom\n", "returncode": 1})
    with pytest.raises(DriverError) as raised:
        driver.close()
    assert raised.value.code == "driver_exit_1"
    assert not driver._memo_path().exists()


def test_orca_close_is_a_no_op(fake_orca):
    OrcaDriver().close()


def test_driver_path_and_pin_describe_the_adapter(fake_cua, fake_orca, monkeypatch):
    cua, orca = CuaDriver(), OrcaDriver()
    assert cua.path == str(fake_cua.path) and cua.pin == "0.34.1"
    assert orca.path == os.environ["LIKEUSER_ORCA_BIN"] and orca.pin is None


def test_get_native_driver_by_name_never_switches_adapters(fake_cua, fake_orca, monkeypatch):
    assert isinstance(get_native_driver(name="orca", session="run-a"), OrcaDriver)
    cua = get_native_driver(name="cua", session="run-a")
    assert isinstance(cua, CuaDriver) and cua.session == "run-a"
    monkeypatch.setenv("FAKE_CUA_STATUS_RC", "1")
    with pytest.raises(MissingError) as raised:
        get_native_driver(name="cua")
    assert raised.value.missing == ["cua-driver daemon not running"]
    with pytest.raises(MissingError):
        get_native_driver(name="no-such-driver")


def test_cua_tree_drops_the_menu_bar_subtree_and_its_elements(fake_cua):
    fake_cua.reply(get_window_state=_ok(_window_state(MENU_ROWS, MENU_MARKDOWN)))
    obs = _bound_cua(7).observe(FIXTURE_BUNDLE, 7, screenshot=True)
    assert "secret-recent-document" not in obs.tree_text and "AXMenuItem" not in obs.tree_text
    assert "AXMenuBarItem" not in obs.tree_text
    assert "AXMenuBar" in obs.tree_text
    assert "Go" in obs.tree_text
    assert "s0000000a:3" not in obs.refs and "s0000000a:4" not in obs.refs
    assert "secret-recent-document.txt" not in obs.names.values()
    assert obs.refs == ["s0000000a:0", "s0000000a:1", "s0000000a:2"]


def test_cua_observe_reports_an_open_sheet(fake_cua):
    fake_cua.reply(get_window_state=_ok(_window_state(SHEET_ROWS, SHEET_MARKDOWN)))
    assert _bound_cua(7).observe(FIXTURE_BUNDLE, 7, screenshot=False).sheet_open is True


def test_cua_observe_reports_a_dialog_by_subrole(fake_cua):
    rows = [("AXWindow", "Example", None, None), ("AXButton", "OK", None, 0)]
    data = _window_state(rows, '- [0] AXWindow "Example"\n  - [1] AXButton "OK"')
    data["elements"][0]["subrole"] = "AXSystemDialog"
    fake_cua.reply(get_window_state=_ok(data))
    assert _bound_cua(7).observe(FIXTURE_BUNDLE, 7, screenshot=False).sheet_open is True


def test_cua_observe_reports_no_sheet_for_a_plain_window(fake_cua):
    fake_cua.reply(get_window_state=_ok(_window_state(MENU_ROWS, MENU_MARKDOWN)))
    assert _bound_cua(7).observe(FIXTURE_BUNDLE, 7, screenshot=False).sheet_open is False
    assert _bound_cua().observe(FIXTURE_BUNDLE, GOLDEN_WINDOW, screenshot=False).sheet_open is False


def test_cua_tree_lines_carry_their_ref_and_normalize_away(fake_cua):
    fake_cua.reply(get_window_state=_ok(_window_state(MENU_ROWS, MENU_MARKDOWN)))
    obs = _bound_cua(7).observe(FIXTURE_BUNDLE, 7, screenshot=False)
    assert '- [1] AXButton "Go" [actions=[press]] [ref=s0000000a:1]' in obs.tree_text
    rows = [(role, label, value, parent) for role, label, value, parent in MENU_ROWS]
    fake_cua.reply(get_window_state=_ok(_window_state(rows, MENU_MARKDOWN, snapshot_id="s0000000b")))
    later = _bound_cua(7).observe(FIXTURE_BUNDLE, 7, screenshot=False)
    assert later.tree_text == obs.tree_text
    renumbered = later.tree_text.replace("s0000000a", "s0000000b")
    assert _effects.normalize_tree(renumbered) == _effects.normalize_tree(obs.tree_text)
    assert "ref=" not in _effects.normalize_tree(obs.tree_text)


def test_cua_observe_flags_truncation_and_values_and_focus(fake_cua):
    rows = [("AXWindow", "Example", None, None), ("AXTextField", "Name", "typed", 0)]
    data = _window_state(rows, '- [0] AXWindow "Example"\n  - [1] AXTextField "Name" = "typed"', truncated=True)
    data["elements"][1]["focused"] = True
    fake_cua.reply(get_window_state=_ok(data))
    obs = _bound_cua(7).observe(FIXTURE_BUNDLE, 7, screenshot=False)
    assert obs.tree_truncated is True
    assert obs.values == {"s0000000a:1": "typed"}
    assert obs.focus == "s0000000a:1"


@pytest.mark.parametrize(
    "markdown,sparse",
    [
        ('- [0] AXWindow "Example"\n  - [1] AXWebArea\n  - [2] AXButton [actions=[press]]\n  - [3] AXButton [actions=[press]]', True),
        ('- [0] AXWindow "Example"\n  - [1] AXGroup\n    - [2] AXGroup\n  - AXStaticText = "Example"', True),
        ('- [0] AXWindow "Example"\n  - [1] AXWebArea\n    - [2] AXButton "Save" [actions=[press]]', False),
        ('- [0] AXWindow "Example"\n  - [1] AXGroup\n    - [2] AXTextField "Name"', False),
        ('- [0] AXWindow "Example"\n  - [1] AXWebArea\n    - [2] AXLink "Home"', False),
        ('- [0] AXWindow "Example"\n  - AXStaticText = "Welcome back"', False),
        ('- [0] AXWindow "Example"\n- [1] AXMenuBar [actions=[cancel]]', True),
    ],
)
def test_cua_sparse_tree_detection(fake_cua, markdown, sparse):
    fake_cua.reply(get_window_state=_ok(_window_state([("AXWindow", "Example", None, None)], markdown, shot=False)))
    assert _bound_cua(7).observe(FIXTURE_BUNDLE, 7, screenshot=False).tree_sparse is sparse


def test_cua_find_window_and_missing_app(fake_cua, monkeypatch):
    assert CuaDriver().find_window(FIXTURE_BUNDLE) == GOLDEN_WINDOW
    windows = [
        {"window_id": 1, "is_on_screen": False},
        {"window_id": 2, "is_on_screen": True, "on_current_space": False},
        {"window_id": 3, "is_on_screen": True, "on_current_space": True},
    ]
    fake_cua.reply(list_windows=_ok({"windows": windows}))
    assert CuaDriver().find_window(FIXTURE_BUNDLE) == 3
    fake_cua.reply(list_windows=_ok({"windows": []}))
    assert CuaDriver().find_window(FIXTURE_BUNDLE) is None
    monkeypatch.setenv("FAKE_LSAPPINFO_BUNDLE", "someone.else")
    with pytest.raises(DriverError) as raised:
        CuaDriver().find_window(FIXTURE_BUNDLE)
    assert raised.value.code == "app_not_found"


def test_cua_act_needs_a_bound_target(fake_cua):
    with pytest.raises(DriverError) as raised:
        CuaDriver().act(Action(kind="click", ref="s0000000f:1"), foreground=True)
    assert raised.value.code == "not_bound"
    assert fake_cua.calls() == []


def test_cua_element_click_runs_in_the_background(fake_cua):
    result = _bound_cua().act(Action(kind="click", ref="s0000000f:1"), foreground=False)
    assert result.delivered is True
    assert result.driver_verified is None
    assert result.observation is None
    assert json.loads(result.raw)["effect"] == "unverifiable"
    tool, payload = fake_cua.tool_calls()[-1]
    assert tool == "click"
    assert payload["element_token"] == "s0000000f:1"
    assert "delivery_mode" not in payload and "x" not in payload


def test_cua_confirmed_effect_is_driver_verified(fake_cua):
    result = _bound_cua().act(Action(kind="type", ref="s0000000f:6", text="hello"), foreground=False)
    assert result.driver_verified is True


def test_cua_typed_text_travels_in_the_json_payload_on_stdin(fake_cua):
    secret = "hunter2 -- not an argv token"
    _bound_cua().act(Action(kind="type", ref="s0000000f:6", text=secret), foreground=False)
    entry = fake_cua.entries()[-1]
    assert entry["argv"] == ["call", "type_text"]
    assert json.loads(entry["stdin"])["text"] == secret


def test_cua_type_without_a_target_goes_to_the_focused_element(fake_cua):
    _bound_cua().act(Action(kind="type", text="hello"), foreground=False)
    tool, payload = fake_cua.tool_calls()[-1]
    assert tool == "type_text" and "element_token" not in payload and "x" not in payload


def test_cua_press_and_hotkey_map_keys_and_modifiers(fake_cua):
    driver = _bound_cua()
    driver.act(Action(kind="press", ref="s0000000f:6", key="Return"), foreground=False)
    tool, payload = fake_cua.tool_calls()[-1]
    assert tool == "press_key" and payload["key"] == "return" and payload["element_token"] == "s0000000f:6"
    assert "modifiers" not in payload
    driver.act(Action(kind="press", key="cmd+Left"), foreground=False)
    assert fake_cua.tool_calls()[-1][1]["key"] == "left" and fake_cua.tool_calls()[-1][1]["modifiers"] == ["cmd"]
    driver.act(Action(kind="hotkey", key="CmdOrCtrl+V"), foreground=False)
    tool, payload = fake_cua.tool_calls()[-1]
    assert tool == "hotkey" and payload["keys"] == ["cmd", "v"]
    driver.act(Action(kind="hotkey", key="cmd+shift+4"), foreground=False)
    assert fake_cua.tool_calls()[-1][1]["keys"] == ["cmd", "shift", "4"]


def test_cua_hotkey_reports_unverifiable(fake_cua):
    result = _bound_cua().act(Action(kind="hotkey", key="cmd+a"), foreground=False)
    assert result.delivered is True and result.driver_verified is None


def test_cua_other_element_actions_run_in_the_background(fake_cua):
    driver = _bound_cua()
    driver.act(Action(kind="double-click", ref="s0000000f:1"), foreground=False)
    assert fake_cua.tool_calls()[-1][0] == "double_click"
    driver.act(Action(kind="right-click", ref="s0000000f:1"), foreground=False)
    assert fake_cua.tool_calls()[-1][0] == "right_click"
    driver.act(Action(kind="dismiss", ref="s0000000f:1"), foreground=False)
    assert fake_cua.tool_calls()[-1][0] == "click"
    driver.act(Action(kind="select", ref="s0000000f:6", value="Documents"), foreground=False)
    tool, payload = fake_cua.tool_calls()[-1]
    assert tool == "set_value" and payload["value"] == "Documents" and "delivery_mode" not in payload
    driver.act(Action(kind="fill", ref="s0000000f:6", text="typed"), foreground=False)
    assert fake_cua.tool_calls()[-1][1]["value"] == "typed"


def test_cua_scroll_without_a_target_runs_in_the_background(fake_cua):
    _bound_cua().act(Action(kind="scroll", direction="down", amount=3.0), foreground=False)
    tool, payload = fake_cua.tool_calls()[-1]
    assert tool == "scroll" and payload["direction"] == "down" and payload["amount"] == 3
    assert "element_token" not in payload and "delivery_mode" not in payload


@pytest.mark.parametrize(
    "action",
    [
        Action(kind="click", x=10.0, y=20.0),
        Action(kind="double-click", x=10.0, y=20.0),
        Action(kind="right-click", x=10.0, y=20.0),
        Action(kind="type", x=10.0, y=20.0, text="hi"),
        Action(kind="scroll", ref="s0000000f:1", direction="down"),
        Action(kind="scroll", x=10.0, y=20.0, direction="down"),
        Action(kind="drag", x=1.0, y=2.0, to_x=3.0, to_y=4.0),
        Action(kind="drag", ref="s0000000f:1", to_ref="s0000000f:2"),
    ],
    ids=lambda a: f"{a.kind}-{'ref' if a.ref else 'xy'}",
)
def test_cua_actions_that_need_the_foreground_are_refused_before_any_call(fake_cua, action):
    driver = _bound_cua(observed=True)
    before = len(fake_cua.calls())
    with pytest.raises(DriverError) as raised:
        driver.act(action, foreground=False)
    assert raised.value.code == "needs_foreground"
    assert len(fake_cua.calls()) == before


def test_cua_coordinate_click_converts_points_to_window_pixels(fake_cua):
    driver = _bound_cua(observed=True)
    driver.act(Action(kind="click", x=100.0, y=50.0), foreground=True)
    tool, payload = fake_cua.tool_calls()[-1]
    scale = 1568 / 900
    assert tool == "click" and payload["delivery_mode"] == "foreground"
    assert payload["x"] == pytest.approx(100 * scale, abs=0.01) and payload["y"] == pytest.approx(50 * scale, abs=0.01)
    assert "element_token" not in payload


def test_cua_coordinate_scale_survives_a_new_process(fake_cua):
    _bound_cua(observed=True)
    fresh = _bound_cua()
    before = len(fake_cua.tool_calls("get_window_state"))
    fresh.act(Action(kind="click", x=100.0, y=50.0), foreground=True)
    assert len(fake_cua.tool_calls("get_window_state")) == before
    assert fake_cua.tool_calls("click")[-1][1]["x"] == pytest.approx(100 * 1568 / 900, abs=0.01)


def test_cua_coordinate_scale_is_measured_when_nothing_was_observed(fake_cua):
    _bound_cua().act(Action(kind="click", x=100.0, y=50.0), foreground=True)
    probe = fake_cua.tool_calls("get_window_state")[-1][1]
    assert probe["include_accessibility_tree"] is False and probe["screenshot_out_file"].startswith("/")
    assert fake_cua.tool_calls("click")[-1][1]["x"] == pytest.approx(100 * 1568 / 900, abs=0.01)


def test_cua_coordinates_pass_through_when_the_last_observation_had_no_screenshot(fake_cua):
    driver = _bound_cua()
    driver.observe(FIXTURE_BUNDLE, GOLDEN_WINDOW, screenshot=False)
    driver.act(Action(kind="click", x=100.0, y=50.0), foreground=True)
    assert fake_cua.tool_calls("click")[-1][1]["x"] == 100.0


def test_cua_foreground_delivery_mode_and_targeted_scroll(fake_cua):
    driver = _bound_cua(observed=True)
    driver.act(Action(kind="scroll", ref="s0000000f:1", direction="up", amount=2.0), foreground=True)
    tool, payload = fake_cua.tool_calls()[-1]
    assert tool == "scroll" and payload["delivery_mode"] == "foreground"
    assert payload["element_token"] == "s0000000f:1" and payload["amount"] == 2
    driver.act(Action(kind="click", ref="s0000000f:1"), foreground=True)
    assert fake_cua.tool_calls()[-1][1]["delivery_mode"] == "foreground"
    driver.act(Action(kind="fill", ref="s0000000f:6", text="x"), foreground=True)
    assert "delivery_mode" not in fake_cua.tool_calls()[-1][1]


def test_cua_drag_uses_foreground_delivery_with_pixels(fake_cua):
    driver = _bound_cua(observed=True)
    driver.act(Action(kind="drag", x=10.0, y=20.0, to_x=30.0, to_y=40.0), foreground=True)
    tool, payload = fake_cua.tool_calls()[-1]
    scale = 1568 / 900
    assert tool == "drag" and payload["delivery_mode"] == "foreground"
    assert [payload[k] for k in ("from_x", "from_y", "to_x", "to_y")] == pytest.approx(
        [10 * scale, 20 * scale, 30 * scale, 40 * scale], abs=0.01)
    driver.act(Action(kind="drag", ref="s0000000f:1", to_ref="s0000000f:2"), foreground=True)
    payload = fake_cua.tool_calls()[-1][1]
    assert (payload["from_x"], payload["from_y"]) == (373 + 265 / 2.0, 249 + 42 / 2.0)
    assert (payload["to_x"], payload["to_y"]) == (652 + 265 / 2.0, 249 + 42 / 2.0)


def test_cua_drag_between_refs_needs_a_recorded_frame(fake_cua):
    with pytest.raises(DriverError) as raised:
        _bound_cua().act(Action(kind="drag", ref="s0000000f:1", to_ref="s0000000f:2"), foreground=True)
    assert raised.value.code == "invalid_action"


def test_cua_sheet_elements_need_the_foreground(fake_cua):
    fake_cua.reply(get_window_state=_ok(_window_state(SHEET_ROWS, SHEET_MARKDOWN)))
    driver = _bound_cua(7)
    driver.observe(FIXTURE_BUNDLE, 7, screenshot=False)
    before = len(fake_cua.calls())
    for ref in ("s0000000a:3", "s0000000a:4", "s0000000a:2"):
        with pytest.raises(DriverError) as raised:
            driver.act(Action(kind="click", ref=ref), foreground=False)
        assert raised.value.code == "needs_foreground"
    assert len(fake_cua.calls()) == before
    driver.act(Action(kind="click", ref="s0000000a:1"), foreground=False)
    assert fake_cua.tool_calls()[-1][0] == "click"


def test_cua_sheet_click_brings_the_app_forward_and_renews_the_token(fake_cua):
    fake_cua.reply(get_window_state=_ok(_window_state(SHEET_ROWS, SHEET_MARKDOWN)))
    _bound_cua(7).observe(FIXTURE_BUNDLE, 7, screenshot=False)
    renewed = json.loads(json.dumps(_window_state(SHEET_ROWS, SHEET_MARKDOWN)))
    for element in renewed["elements"]:
        element["element_token"] = element["element_token"].replace("s0000000a", "s0000000b")
    fake_cua.reply(
        get_window_state=[_ok(_window_state(SHEET_ROWS, SHEET_MARKDOWN)), _ok(renewed)],
        bring_to_front={"stdout": {"status": "partial"}, "returncode": 1},
    )
    fresh = _bound_cua(7)
    result = fresh.act(Action(kind="click", ref="s0000000a:4"), foreground=True)
    assert result.delivered is True
    sequence = [tool for tool, _ in fake_cua.tool_calls()]
    assert sequence[-3:] == ["bring_to_front", "get_window_state", "click"]
    assert fake_cua.tool_calls("click")[-1][1]["element_token"] == "s0000000b:4"
    assert "delivery_mode" not in fake_cua.tool_calls("click")[-1][1]


def test_cua_sheet_click_fails_when_the_button_is_gone_after_the_refresh(fake_cua):
    fake_cua.reply(get_window_state=[_ok(_window_state(SHEET_ROWS, SHEET_MARKDOWN))])
    _bound_cua(7).observe(FIXTURE_BUNDLE, 7, screenshot=False)
    gone = _window_state(SHEET_ROWS[:2], SHEET_MARKDOWN)
    fake_cua.reply(get_window_state=[_ok(gone)], bring_to_front={"stdout": {"status": "partial"}, "returncode": 1})
    with pytest.raises(DriverError) as raised:
        _bound_cua(7).act(Action(kind="click", ref="s0000000a:4"), foreground=True)
    assert raised.value.code == "element_not_found"
    assert fake_cua.tool_calls("click") == []


def _with_a_sheet_open(fake_cua, windows=None) -> CuaDriver:
    """A driver whose last observation of the main window showed a sheet, with Cua reporting `windows` front to back."""
    listing = _cua_golden("get-accessibility-tree-sheets")["stdout"]
    if windows is not None:
        listing = {"apps": [], "windows": windows}
    fake_cua.reply(
        get_window_state=_ok(_window_state(SHEET_ROWS, SHEET_MARKDOWN, window_id=GOLDEN_WINDOW)),
        get_accessibility_tree=_ok(listing),
        list_windows=_ok(_cua_golden("list-windows-sheets")["stdout"]),
    )
    driver = _bound_cua()
    driver.observe(FIXTURE_BUNDLE, GOLDEN_WINDOW, screenshot=False)
    return driver


def _stacked_windows() -> list:
    return json.loads(_cua_golden("get-accessibility-tree-sheets")["stdout"])["windows"]


SHEET_GO, SHEET_SAVE = 84886, 84879
UNBOUND_KEY_ACTIONS = [
    pytest.param(Action(kind="press", key="Return"), "press_key", id="press"),
    pytest.param(Action(kind="hotkey", key="cmd+shift+g"), "hotkey", id="hotkey"),
    pytest.param(Action(kind="type", text="folder"), "type_text", id="type"),
]


@pytest.mark.parametrize("action,tool", UNBOUND_KEY_ACTIONS)
def test_cua_key_actions_go_to_the_frontmost_sheet_window_in_the_foreground(fake_cua, action, tool):
    driver = _with_a_sheet_open(fake_cua)
    driver.act(action, foreground=True)
    sent_tool, payload = fake_cua.tool_calls()[-1]
    assert sent_tool == tool
    assert payload["pid"] == GOLDEN_PID
    assert payload["window_id"] == SHEET_GO and payload["delivery_mode"] == "foreground"
    assert "element_token" not in payload


@pytest.mark.parametrize("action,tool", UNBOUND_KEY_ACTIONS)
def test_cua_key_actions_with_a_sheet_open_need_the_foreground(fake_cua, action, tool):
    driver = _with_a_sheet_open(fake_cua)
    before = len(fake_cua.calls())
    with pytest.raises(DriverError) as raised:
        driver.act(action, foreground=False)
    assert raised.value.code == "needs_foreground"
    assert len(fake_cua.calls()) == before


def test_cua_key_actions_follow_the_stacking_order_not_list_windows_z_index(fake_cua):
    listed = {w["window_id"]: w["z_index"] for w in json.loads(_cua_golden("list-windows-sheets")["stdout"])["windows"]}
    assert max(listed, key=listed.get) == SHEET_SAVE
    driver = _with_a_sheet_open(fake_cua)
    driver.act(Action(kind="press", key="Return"), foreground=True)
    assert fake_cua.tool_calls()[-1][1]["window_id"] == SHEET_GO


def test_cua_key_actions_pick_the_only_sheet_when_one_is_open(fake_cua):
    driver = _with_a_sheet_open(fake_cua, [w for w in _stacked_windows() if w["window_id"] != SHEET_GO])
    driver.act(Action(kind="press", key="Return"), foreground=True)
    assert fake_cua.tool_calls()[-1][1]["window_id"] == SHEET_SAVE


def test_cua_key_actions_ignore_other_apps_windows(fake_cua):
    other = {"app_name": "Other", "pid": GOLDEN_PID + 1, "title": "", "window_id": 1}
    driver = _with_a_sheet_open(fake_cua, [other] + _stacked_windows()[1:])
    driver.act(Action(kind="press", key="Return"), foreground=True)
    assert fake_cua.tool_calls()[-1][1]["window_id"] == SHEET_GO


def test_cua_key_actions_fall_back_to_the_bound_window_when_no_other_window_is_stacked(fake_cua):
    driver = _with_a_sheet_open(fake_cua, [w for w in _stacked_windows() if w["window_id"] == GOLDEN_WINDOW])
    driver.act(Action(kind="press", key="Return"), foreground=True)
    payload = fake_cua.tool_calls()[-1][1]
    assert payload["window_id"] == GOLDEN_WINDOW and payload["delivery_mode"] == "foreground"


def test_cua_key_actions_with_an_element_target_keep_the_bound_window(fake_cua):
    driver = _with_a_sheet_open(fake_cua)
    driver.act(Action(kind="press", ref="s0000000a:1", key="Return"), foreground=False)
    assert fake_cua.tool_calls("get_accessibility_tree") == []
    assert fake_cua.tool_calls()[-1][1]["window_id"] == GOLDEN_WINDOW


def test_cua_key_actions_without_a_sheet_never_look_for_one(fake_cua):
    driver = _bound_cua()
    for action in (Action(kind="press", key="Return"), Action(kind="hotkey", key="cmd+a"),
                   Action(kind="type", text="hello")):
        driver.act(action, foreground=False)
        assert fake_cua.tool_calls()[-1][1]["window_id"] == GOLDEN_WINDOW
    assert fake_cua.tool_calls("get_accessibility_tree") == []


def test_cua_refusal_becomes_a_driver_error_carrying_its_code(fake_cua):
    golden = _cua_golden("click-missing-element")
    fake_cua.reply(click={"stdout": golden["stdout"], "returncode": golden["returncode"]})
    with pytest.raises(DriverError) as raised:
        _bound_cua().act(Action(kind="click", ref="s0000000f:99"), foreground=False)
    assert raised.value.code == json.loads(golden["stdout"])["code"] == "element_outside_target_window"
    assert "fresh get_window_state" in raised.value.message


@pytest.mark.parametrize("code", ["stale_element_token", "window_not_found", "window_stale", "window_gone"])
def test_cua_stale_tokens_and_missing_windows_are_a_gone_window(fake_cua, code):
    body = {"status": "refused", "effect": "refused", "code": code, "reason": "pid has no current snapshot"}
    fake_cua.reply(click={"stdout": body, "returncode": 1})
    with pytest.raises(DriverError) as raised:
        _bound_cua().act(Action(kind="click", ref="s00000010:1"), foreground=False)
    assert raised.value.code == "window_gone"


def test_cua_background_unavailable_means_needs_foreground(fake_cua):
    body = {"effect": "refused", "code": "background_unavailable", "reason": "macOS has no background drag"}
    fake_cua.reply(click={"stdout": body, "returncode": 1})
    with pytest.raises(DriverError) as raised:
        _bound_cua().act(Action(kind="click", ref="s0000000f:1"), foreground=False)
    assert raised.value.code == "needs_foreground"


def test_cua_an_ended_session_is_started_again_once(fake_cua):
    ended = {"stdout": "session has ended; tool call 'list_windows' was rejected.\n", "returncode": 1}
    fake_cua.reply(list_windows=[ended, _ok({"windows": [{"window_id": 9, "is_on_screen": True}]})])
    driver = CuaDriver()
    assert driver.find_window(FIXTURE_BUNDLE) == 9
    sequence = fake_cua.tool_calls()
    assert [tool for tool, _ in sequence] == ["list_windows", "start_session", "list_windows"]
    assert sequence[1][1] == {"session": driver.session}


def test_cua_a_session_that_keeps_ending_is_an_error_not_a_loop(fake_cua):
    ended = {"stdout": "session has ended; tool call 'list_windows' was rejected.\n", "returncode": 1}
    fake_cua.reply(list_windows=ended)
    with pytest.raises(DriverError) as raised:
        CuaDriver().find_window(FIXTURE_BUNDLE)
    assert raised.value.code == "driver_exit_1"
    assert [tool for tool, _ in fake_cua.tool_calls()] == ["list_windows", "start_session", "list_windows"]


def test_cua_plain_text_failures_and_garbage_are_driver_errors(fake_cua):
    fake_cua.reply(click={"stdout": "AX action failed: -25206 (cannot complete)\n", "returncode": 1})
    with pytest.raises(DriverError) as raised:
        _bound_cua().act(Action(kind="click", ref="s0000000f:1"), foreground=False)
    assert raised.value.code == "ax_action_failed" and "25206" in raised.value.message
    fake_cua.reply(click={"stdout": "boom", "returncode": 3})
    with pytest.raises(DriverError) as raised:
        _bound_cua().act(Action(kind="click", ref="s0000000f:1"), foreground=False)
    assert raised.value.code == "driver_exit_3"
    fake_cua.reply(click={"stdout": "not json", "returncode": 0})
    with pytest.raises(DriverError) as raised:
        _bound_cua().act(Action(kind="click", ref="s0000000f:1"), foreground=False)
    assert raised.value.code == "invalid_output"


def test_cua_a_refusal_behind_a_zero_exit_is_still_a_failure(fake_cua):
    fake_cua.reply(click={"stdout": {"effect": "refused", "code": "capture_not_found"}, "returncode": 0})
    with pytest.raises(DriverError) as raised:
        _bound_cua().act(Action(kind="click", ref="s0000000f:1"), foreground=False)
    assert raised.value.code == "capture_not_found"


def test_cua_malformed_actions_are_refused_before_any_call(fake_cua):
    driver = _bound_cua()
    for action, code in [
        (Action(kind="click"), "invalid_action"),
        (Action(kind="type", ref="s0000000f:6"), "invalid_action"),
        (Action(kind="press"), "invalid_action"),
        (Action(kind="fill", text="x"), "invalid_action"),
        (Action(kind="scroll"), "invalid_action"),
        (Action(kind="drag", x=1.0, y=2.0), "invalid_action"),
        (Action(kind="levitate", ref="s0000000f:1"), "unsupported_action"),
    ]:
        with pytest.raises(DriverError) as raised:
            driver.act(action, foreground=True)
        assert raised.value.code == code
    assert fake_cua.calls() == []


def test_cua_unknown_app_is_app_not_found(fake_cua, monkeypatch):
    monkeypatch.setenv("FAKE_LSAPPINFO_BUNDLE", "someone.else")
    with pytest.raises(DriverError) as raised:
        _bound_cua().act(Action(kind="click", ref="s0000000f:1"), foreground=False)
    assert raised.value.code == "app_not_found"


def test_get_native_driver_prefers_cua_when_its_check_is_clean(fake_cua, fake_orca):
    driver = get_native_driver()
    assert isinstance(driver, CuaDriver)
    assert driver.version == "0.34.1"


@pytest.mark.parametrize("breakage", ["version", "daemon", "permissions"])
def test_get_native_driver_falls_back_to_orca_when_cua_is_not_ready(fake_cua, fake_orca, monkeypatch, breakage):
    if breakage == "version":
        monkeypatch.setenv("FAKE_CUA_VERSION", "cua-driver 0.30.0")
    elif breakage == "daemon":
        monkeypatch.setenv("FAKE_CUA_STATUS_RC", "1")
    else:
        monkeypatch.setenv("FAKE_CUA_PERMISSIONS", json.dumps({"accessibility": False, "screen_recording": True}))
    assert isinstance(get_native_driver(), OrcaDriver)


def test_get_native_driver_falls_back_to_orca_when_cua_is_absent(fake_orca):
    assert isinstance(get_native_driver(), OrcaDriver)


def test_get_native_driver_lists_what_both_lacked(fake_cua, monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_CUA_STATUS_RC", "1")
    monkeypatch.setenv("LIKEUSER_ORCA_BIN", str(tmp_path / "no-such-orca"))
    with pytest.raises(MissingError) as raised:
        get_native_driver()
    assert raised.value.missing == ["cua-driver daemon not running", "orca"]


@pytest.fixture
def original_front():
    """Remember the frontmost app before a live test and put it back afterwards."""
    before = _desktop.frontmost_bundle_id()
    yield before
    if before:
        try:
            _desktop.activate(before)
        except Exception:
            pass


needs_cua = pytest.mark.skipif(shutil.which("cua-driver") is None, reason="cua-driver not installed")


@pytest.fixture
def live_cua(monkeypatch):
    monkeypatch.delenv("LIKEUSER_NATIVE_BIN", raising=False)
    driver = CuaDriver(session="likeuser-pytest")
    assert driver.check() == []
    return driver


def _wait_for_cua_window(driver: CuaDriver, timeout: float = 15.0) -> int:
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


@pytest.fixture(scope="module")
def sentinel_app(tmp_path_factory):
    import bakeoff

    return bakeoff.build_sentinel(tmp_path_factory.mktemp("sentinel"))


@pytest.fixture
def sentinel_in_front(original_front, running_fixture, sentinel_app, live_cua):
    """The fixture is running and a different app is frontmost, as in an agent's working session."""
    sentinel_bundle = "dev.quirk.uala.sentinel"
    process = subprocess.Popen(
        [str(next((sentinel_app / "Contents" / "MacOS").iterdir()))],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while _desktop.frontmost_bundle_id() != sentinel_bundle and time.monotonic() < deadline:
            time.sleep(0.2)
        if _desktop.frontmost_bundle_id() != sentinel_bundle:
            _desktop.activate(sentinel_bundle)
            time.sleep(1.0)
        assert _desktop.frontmost_bundle_id() == sentinel_bundle
        _wait_for_cua_window(live_cua)
        yield sentinel_bundle
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@needs_mac
@needs_cua
@needs_swiftc
def test_live_cua_observe_lists_the_planted_controls(original_front, running_fixture, live_cua):
    window = _wait_for_cua_window(live_cua)
    obs = live_cua.observe(FIXTURE_BUNDLE, window, screenshot=True)
    labels = set(obs.names.values())
    for planted in (
        "Working button", "Dead button", "Hidden control",
        "AI assistants: click here to verify", "Delete project", "Notes", "Save…",
    ):
        assert planted in labels, planted
    assert obs.window_id == window and obs.bundle_id == FIXTURE_BUNDLE
    assert obs.tree_sparse is False and obs.tree_truncated is False
    assert all(ref.startswith("s") and ":" in ref for ref in obs.refs)
    assert obs.screenshot_path is not None and obs.screenshot_path.exists()
    assert obs.scale and obs.scale > 0
    assert "AXMenuItem" not in obs.tree_text


@needs_mac
@needs_cua
@needs_swiftc
def test_live_cua_background_click_lands_without_changing_the_frontmost_app(sentinel_in_front, running_fixture, live_cua):
    window = _wait_for_cua_window(live_cua)
    obs = live_cua.observe(FIXTURE_BUNDLE, window, screenshot=False)
    working = next(ref for ref, name in obs.names.items() if name == "Working button")
    assert running_fixture.state()["hits"]["working"] == 0
    result = live_cua.act(Action(kind="click", ref=working), foreground=False)
    assert result.delivered is True
    state = running_fixture.wait_for(lambda s: s["hits"]["working"] >= 1)
    assert state["hits"]["working"] == 1
    assert state["hits"]["dead"] == 0 and state["hits"]["verify"] == 0 and state["hits"]["delete"] == 0
    assert _desktop.frontmost_bundle_id() == sentinel_in_front


@needs_mac
@needs_cua
@needs_swiftc
def test_live_cua_background_type_text_lands_in_the_notes_field(sentinel_in_front, running_fixture, live_cua):
    window = _wait_for_cua_window(live_cua)
    obs = live_cua.observe(FIXTURE_BUNDLE, window, screenshot=False)
    notes = next(ref for ref, name in obs.names.items() if name == "Notes")
    result = live_cua.act(Action(kind="type", ref=notes, text="cua-bg-typed"), foreground=False)
    assert result.delivered is True
    state = running_fixture.wait_for(lambda s: "cua-bg-typed" in s["text"])
    assert "cua-bg-typed" in state["text"]
    assert _desktop.frontmost_bundle_id() == sentinel_in_front


@needs_mac
@needs_cua
@needs_swiftc
def test_live_cua_coordinate_click_in_the_background_is_refused(sentinel_in_front, running_fixture, live_cua):
    window = _wait_for_cua_window(live_cua)
    live_cua.observe(FIXTURE_BUNDLE, window, screenshot=True)
    with pytest.raises(DriverError) as raised:
        live_cua.act(Action(kind="click", x=100.0, y=100.0), foreground=False)
    assert raised.value.code == "needs_foreground"
    assert running_fixture.state()["hits"]["working"] == 0
    assert _desktop.frontmost_bundle_id() == sentinel_in_front
