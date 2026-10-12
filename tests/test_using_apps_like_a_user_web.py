"""Tests for the playwright-cli adapter and the web fixture of using-apps-like-a-user.

CI-safe tests replay golden playwright-cli output through a fake binary named by
LIKEUSER_PLAYWRIGHT_BIN. Live tests drive the real playwright-cli against the fixture server
and run only on macOS with the tool installed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "skills" / "using-apps-like-a-user" / "scripts"
FIXTURES = REPO / "tests" / "fixtures" / "using-apps-like-a-user"
GOLDEN = FIXTURES / "golden" / "playwright"
SERVER = FIXTURES / "web" / "server.py"

FAKES = FIXTURES / "fakes"
for _entry in (str(SCRIPTS), str(FAKES)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import _web  # noqa: E402
import harness  # noqa: E402
from _types import Action, DriverError  # noqa: E402

LIVE = sys.platform == "darwin" and shutil.which("playwright-cli") is not None
needs_live = pytest.mark.skipif(
    not LIVE, reason="needs macOS and playwright-cli on PATH"
)

FAKE_BIN_SOURCE = '''#!{python}
import json, os, sys
from pathlib import Path

here = Path(__file__).resolve()
queue_path = here.with_suffix(".queue.json")
calls_path = here.with_suffix(".calls.json")
queue = json.loads(queue_path.read_text())
calls = json.loads(calls_path.read_text()) if calls_path.exists() else []
calls.append({{"argv": sys.argv[1:], "cwd": os.getcwd()}})
calls_path.write_text(json.dumps(calls))
if not queue:
    sys.stderr.write("fake playwright-cli: unexpected call " + repr(sys.argv[1:]) + "\\n")
    sys.exit(99)
entry = queue.pop(0)
queue_path.write_text(json.dumps(queue))
golden = json.loads((Path({golden!r}) / (entry["case"] + ".json")).read_text())
for rel, text in golden["files"].items():
    target = Path(os.getcwd()) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text if text is not None else "")
sys.stdout.write(entry.get("stdout", golden["stdout"]))
sys.stderr.write(golden["stderr"])
sys.exit(entry.get("returncode", golden["returncode"]))
'''


def load_golden(case: str) -> dict:
    return json.loads((GOLDEN / f"{case}.json").read_text())


class Fake:
    """A fake playwright-cli replaying golden cases in order and logging each call."""

    def __init__(self, tmp_path: Path, monkeypatch, cases: list) -> None:
        self.run_dir = tmp_path / "run"
        self.run_dir.mkdir()
        self.bin = tmp_path / "fake-playwright-cli"
        self.bin.write_text(FAKE_BIN_SOURCE.format(python=sys.executable, golden=str(GOLDEN)))
        self.bin.chmod(0o755)
        queue = [{"case": c} if isinstance(c, str) else c for c in cases]
        self.bin.with_suffix(".queue.json").write_text(json.dumps(queue))
        monkeypatch.setenv("LIKEUSER_PLAYWRIGHT_BIN", str(self.bin))
        self.driver = _web.WebDriver("sess", self.run_dir)

    @property
    def calls(self) -> list:
        path = self.bin.with_suffix(".calls.json")
        return json.loads(path.read_text()) if path.exists() else []

    @property
    def argvs(self) -> list:
        return [c["argv"] for c in self.calls]


@pytest.fixture
def fake(tmp_path, monkeypatch):
    def make(cases: list) -> Fake:
        return Fake(tmp_path, monkeypatch, cases)

    return make


def materialize(case: str, cwd: Path) -> str:
    golden = load_golden(case)
    for rel, text in golden["files"].items():
        target = cwd / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text or "")
    return golden["stdout"]


class TestGoldenCoverage:
    REQUIRED = [
        "version", "open", "snapshot", "click", "click_stale_ref", "fill", "type", "press",
        "console", "requests", "eval_visibility_hidden", "screenshot", "state_save", "close",
    ]

    @pytest.mark.parametrize("case", REQUIRED)
    def test_golden_case_exists_in_schema(self, case):
        golden = load_golden(case)
        assert set(golden) == {"argv", "returncode", "stdout", "stderr", "files"}
        assert golden["argv"][0] == "playwright-cli"

    def test_stale_ref_golden_is_a_real_error_block_with_nonzero_exit(self):
        golden = load_golden("click_stale_ref")
        assert golden["returncode"] != 0
        assert golden["stdout"].startswith("### Error")

    def test_goldens_carry_no_local_paths(self):
        for path in GOLDEN.glob("*.json"):
            text = path.read_text()
            assert "/Users/" not in text and "/private/" not in text, path.name


class TestParseSnapshot:
    def test_inline_snapshot_refs_names_focus_and_header(self, tmp_path):
        stdout = load_golden("snapshot")["stdout"]
        obs = _web.parse_snapshot(stdout, tmp_path)
        assert obs.refs[:4] == ["e1", "e2", "e3", "e4"]
        assert obs.refs[-1] == "e24"
        assert obs.names["e4"] == "Increment counter"
        assert obs.names["e8"] == "Promo code"
        assert obs.names["e15"] == "click here to verify"
        assert "e1" not in obs.names
        assert obs.focus == "e1"
        assert obs.url.startswith("http://127.0.0.1:")
        assert obs.title == "Like-a-User Fixture"
        assert "- button \"Increment counter\" [ref=e4]" in obs.tree_text
        assert "### Page" not in obs.tree_text
        assert obs.raw == stdout
        assert not obs.tree_sparse

    def test_linked_snapshot_is_read_from_the_file_under_cwd(self, tmp_path):
        stdout = materialize("click", tmp_path)
        assert "```yaml" not in stdout
        obs = _web.parse_snapshot(stdout, tmp_path)
        assert obs.focus == "e4"
        assert obs.names["e4"] == "Increment counter"
        assert obs.values.get("e5") is None
        assert obs.url.startswith("http://127.0.0.1:")
        assert obs.title == "Like-a-User Fixture"

    def test_linked_snapshot_with_missing_file_raises(self, tmp_path):
        stdout = load_golden("click")["stdout"]
        with pytest.raises(DriverError) as err:
            _web.parse_snapshot(stdout, tmp_path)
        assert err.value.code == "snapshot_unreadable"

    def test_output_without_any_snapshot_raises(self, tmp_path):
        with pytest.raises(DriverError) as err:
            _web.parse_snapshot(load_golden("fill")["stdout"], tmp_path)
        assert err.value.code == "snapshot_missing"

    def test_input_values_are_captured_and_status_text_is_not(self, tmp_path):
        obs = _web.parse_snapshot(load_golden("snapshot_after_type")["stdout"], tmp_path)
        assert obs.values == {"e10": "hello world", "e24": "Light"}
        assert obs.focus == "e10"
        assert obs.names["e10"] == "Notes"

    def test_names_unescape_quotes_and_quoted_values_unquote(self, tmp_path):
        stdout = (
            "### Page\n- Page URL: http://x/\n- Page Title: T\n### Snapshot\n```yaml\n"
            '- textbox "Say \\"hi\\"" [ref=e1]: "a: b"\n'
            "- button [ref=e2]\n"
            "```\n"
        )
        obs = _web.parse_snapshot(stdout, tmp_path)
        assert obs.names == {"e1": 'Say "hi"'}
        assert obs.values == {"e1": "a: b"}
        assert obs.refs == ["e1", "e2"]
        assert obs.focus is None

    @staticmethod
    def _tree_stdout(*rows):
        return ("### Page\n- Page URL: http://x/\n- Page Title: T\n### Snapshot\n```yaml\n"
                + "\n".join(rows) + "\n```\n")

    def test_a_combobox_value_is_its_selected_option(self, tmp_path):
        before = _web.parse_snapshot(self._tree_stdout(
            '- combobox "Theme" [ref=e24]:',
            '  - option "Light" [selected]',
            '  - option "Dark"',
            '- status [ref=e25]: "Theme: Light"'), tmp_path)
        after = _web.parse_snapshot(self._tree_stdout(
            '- combobox "Theme" [ref=e24]:',
            '  - option "Light"',
            '  - option "Dark" [selected]',
            '- status [ref=e25]: "Theme: Dark"'), tmp_path)
        assert before.values == {"e24": "Light"}
        assert after.values == {"e24": "Dark"}

    def test_a_multi_select_listbox_value_joins_every_selected_option(self, tmp_path):
        obs = _web.parse_snapshot(self._tree_stdout(
            '- listbox "Tags" [ref=e3]:',
            '  - option "A" [selected]',
            '  - option "B"',
            '  - option "C" [selected]',
            '- button "Go" [ref=e4]'), tmp_path)
        assert obs.values == {"e3": "A, C"}

    def test_selected_options_do_not_leak_into_the_next_element(self, tmp_path):
        obs = _web.parse_snapshot(self._tree_stdout(
            '- combobox "Theme" [ref=e1]:',
            '  - option "Light"',
            '  - option "Dark"',
            '- generic [ref=e2]:',
            '  - option "Stray" [selected]'), tmp_path)
        assert obs.values == {}

    def test_the_golden_post_select_tree_reports_the_selected_theme(self, tmp_path):
        obs = _web.parse_snapshot(materialize("select", tmp_path), tmp_path)
        assert obs.values["e24"] == "Dark"

    def test_a_tree_with_no_refs_is_marked_sparse(self, tmp_path):
        stdout = "### Page\n- Page URL: http://x/\n### Snapshot\n```yaml\n- generic\n```\n"
        assert _web.parse_snapshot(stdout, tmp_path).tree_sparse is True


class TestParseError:
    def test_error_block_body(self):
        body = _web.parse_error(load_golden("click_stale_ref")["stdout"])
        assert body.startswith("Error: Ref e999 not found")

    def test_multiline_error_body_stops_at_next_section(self):
        body = _web.parse_error("### Error\nboom\nsecond line\n### Page\n- Page URL: x\n")
        assert body == "boom\nsecond line"

    def test_none_when_there_is_no_error_block(self):
        assert _web.parse_error(load_golden("click")["stdout"]) is None
        assert _web.parse_error("") is None


class TestVersion:
    def test_version_and_check_pass_at_the_pin(self, fake):
        f = fake(["version", "version"])
        assert f.driver.version() == "0.1.22"
        assert f.driver.check() == []

    def test_check_flags_a_version_below_the_pin(self, fake):
        f = fake([{"case": "version", "stdout": "0.1.1\n"}])
        problems = f.driver.check()
        assert len(problems) == 1 and "0.1.22" in problems[0] and "0.1.1" in problems[0]

    def test_check_accepts_a_newer_version(self, fake):
        f = fake([{"case": "version", "stdout": "0.2.0\n"}])
        assert f.driver.check() == []

    def test_check_reports_a_missing_binary(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LIKEUSER_PLAYWRIGHT_BIN", str(tmp_path / "nope"))
        driver = _web.WebDriver("sess", tmp_path)
        assert driver.check() == ["playwright-cli"]
        with pytest.raises(DriverError) as err:
            driver.version()
        assert err.value.code == "playwright_missing"

    def test_check_reports_a_binary_that_cannot_print_its_version(self, fake):
        f = fake([{"case": "version", "stdout": "garbage\n"}])
        assert f.driver.check() == ["playwright-cli (unreadable version)"]


class TestSessionAndCwd:
    def test_every_call_runs_in_the_run_folder_with_the_session(self, fake):
        f = fake(["version", "open", "snapshot", "click", "console", "requests",
                  "eval_visibility_hidden", "state_save", "close"])
        d = f.driver
        d.version()
        d.open("http://127.0.0.1:1/")
        obs = d.observe(None)
        d.act(Action(kind="click", ref="e4"))
        d.console_errors()
        d.failed_requests()
        d.visibility("e8")
        d.state_save(f.run_dir / "state.json")
        d.close()
        assert obs.refs
        calls = f.calls
        assert len(calls) == 9
        for call in calls:
            assert os.path.realpath(call["cwd"]) == os.path.realpath(str(f.run_dir))
        for argv in f.argvs[1:]:
            assert argv[0] == "-s=sess"

    def test_open_passes_the_url_and_headed_flag(self, fake):
        f = fake(["open", "open"])
        f.driver.open("http://127.0.0.1:1/")
        f.driver.open("http://127.0.0.1:1/", headed=True)
        assert f.argvs[0] == ["-s=sess", "open", "http://127.0.0.1:1/"]
        assert f.argvs[1] == ["-s=sess", "open", "http://127.0.0.1:1/", "--headed"]

    def test_goto_navigates_the_open_session(self, fake):
        f = fake(["open"])
        f.driver.goto("http://127.0.0.1:1/next")
        assert f.argvs == [["-s=sess", "goto", "http://127.0.0.1:1/next"]]

    def test_attach_cdp_close_detach_and_state_load_commands(self, fake):
        f = fake(["open", "close", "close", "state_save"])
        f.driver.attach_cdp("http://127.0.0.1:9222")
        f.driver.detach()
        f.driver.close()
        f.driver.state_load(Path("/tmp/s.json"))
        assert f.argvs == [
            ["-s=sess", "attach", "--cdp=http://127.0.0.1:9222"],
            ["-s=sess", "detach"],
            ["-s=sess", "close"],
            ["-s=sess", "state-load", "/tmp/s.json"],
        ]

    def test_attach_extension_failure_is_extension_unavailable(self, fake):
        f = fake([{"case": "snapshot_session_closed"}])
        with pytest.raises(DriverError) as err:
            f.driver.attach_extension()
        assert err.value.code == "extension_unavailable"
        assert f.argvs[0] == ["-s=sess", "attach", "--extension=chrome"]


class TestObserve:
    def test_observe_runs_snapshot_and_returns_the_parsed_tree(self, fake):
        f = fake(["snapshot"])
        obs = f.driver.observe(None)
        assert f.argvs == [["-s=sess", "snapshot"]]
        assert obs.names["e12"] == "Save avatar"
        assert obs.screenshot_path is None

    def test_observe_with_screenshot_records_path_and_css_scale(self, fake, tmp_path):
        f = fake(["snapshot", "screenshot"])
        shot = tmp_path / "shot.png"
        obs = f.driver.observe(shot)
        assert f.argvs[1] == ["-s=sess", "screenshot", f"--filename={shot}"]
        assert obs.screenshot_path == shot
        assert obs.scale == 1.0

    def test_observe_raises_when_the_browser_is_closed(self, fake):
        f = fake(["snapshot_session_closed"])
        with pytest.raises(DriverError) as err:
            f.driver.observe(None)
        assert err.value.code == "playwright_failed"


class TestActFailures:
    def test_error_block_with_nonzero_exit_raises(self, fake):
        f = fake(["click_stale_ref"])
        with pytest.raises(DriverError) as err:
            f.driver.act(Action(kind="click", ref="e999"))
        assert err.value.code == "playwright_error"
        assert "Ref e999 not found" in err.value.message

    def test_error_block_with_exit_zero_still_raises(self, fake):
        f = fake([{"case": "click_stale_ref", "returncode": 0}])
        with pytest.raises(DriverError) as err:
            f.driver.act(Action(kind="click", ref="e999"))
        assert err.value.code == "playwright_error"

    def test_nonzero_exit_without_error_block_raises(self, fake):
        f = fake(["snapshot_session_closed"])
        with pytest.raises(DriverError) as err:
            f.driver.act(Action(kind="click", ref="e4"))
        assert err.value.code == "playwright_failed"

    def test_a_failure_midway_through_a_sequence_stops_it(self, fake):
        f = fake(["mousemove", {"case": "mousedown", "returncode": 1}])
        with pytest.raises(DriverError):
            f.driver.act(Action(kind="click", x=5, y=6))
        assert len(f.argvs) == 2

    def test_unknown_action_kind_is_rejected_before_any_call(self, fake):
        f = fake([])
        with pytest.raises(DriverError) as err:
            f.driver.act(Action(kind="levitate", ref="e4"))
        assert err.value.code == "unsupported_action"
        assert f.argvs == []

    def test_click_without_any_target_is_rejected(self, fake):
        f = fake([])
        with pytest.raises(DriverError) as err:
            f.driver.act(Action(kind="click"))
        assert err.value.code == "target_required"


class TestActMapping:
    def test_successful_click_returns_the_linked_observation(self, fake):
        f = fake(["click"])
        result = f.driver.act(Action(kind="click", ref="e4"))
        assert f.argvs == [["-s=sess", "click", "e4"]]
        assert result.delivered is True
        assert result.driver_verified is None
        assert result.observation.focus == "e4"
        assert result.observation.names["e4"] == "Increment counter"
        assert "Ran Playwright code" in result.raw

    def test_actions_without_a_snapshot_return_no_observation(self, fake):
        f = fake(["fill"])
        result = f.driver.act(Action(kind="fill", ref="e10", text="hello"))
        assert result.delivered is True
        assert result.observation is None

    @pytest.mark.parametrize(
        "action, cases, expected",
        [
            (Action(kind="double-click", ref="e4"), ["dblclick"], [["dblclick", "e4"]]),
            (Action(kind="right-click", ref="e4"), ["click_right"], [["click", "e4", "right"]]),
            (Action(kind="fill", ref="e10", text="hello"), ["fill"], [["fill", "e10", "hello"]]),
            (Action(kind="type", text=" world"), ["type"], [["type", " world"]]),
            (Action(kind="type", ref="e10", text="x"), ["click", "type"],
             [["click", "e10"], ["type", "x"]]),
            (Action(kind="press", key="Tab"), ["press"], [["press", "Tab"]]),
            (Action(kind="hotkey", key="cmd+s"), ["hotkey"], [["press", "Meta+s"]]),
            (Action(kind="hotkey", key="ctrl+shift+Z"), ["hotkey"],
             [["press", "Control+Shift+Z"]]),
            (Action(kind="hotkey", key="opt+Left"), ["hotkey"], [["press", "Alt+ArrowLeft"]]),
            (Action(kind="select", ref="e24", value="Dark"), ["select"],
             [["select", "e24", "Dark"]]),
            (Action(kind="fill", ref="e10", text="-x"), ["fill"], [["fill", "e10", "--", "-x"]]),
            (Action(kind="type", text="--submit"), ["type"], [["type", "--", "--submit"]]),
            (Action(kind="dismiss", ref="e4"), ["click"], [["click", "e4"]]),
            (Action(kind="click", x=10, y=20), ["mousemove", "mousedown", "mouseup"],
             [["mousemove", "10", "20"], ["mousedown"], ["mouseup"]]),
            (Action(kind="right-click", x=10.5, y=20), ["mousemove", "mousedown", "mouseup"],
             [["mousemove", "10.5", "20"], ["mousedown", "right"], ["mouseup", "right"]]),
            (Action(kind="double-click", x=1, y=2),
             ["mousemove", "mousedown", "mouseup", "mousedown", "mouseup"],
             [["mousemove", "1", "2"], ["mousedown"], ["mouseup"], ["mousedown"], ["mouseup"]]),
            (Action(kind="drag", x=1, y=2, to_x=30, to_y=40),
             ["mousemove", "mousedown", "mousemove", "mouseup"],
             [["mousemove", "1", "2"], ["mousedown"], ["mousemove", "30", "40"], ["mouseup"]]),
            (Action(kind="drag", ref="e4", to_ref="e7"), ["click"], [["drag", "e4", "e7"]]),
            (Action(kind="drag", ref="e4", to_x=30, to_y=40),
             ["hover", "mousedown", "mousemove", "mouseup"],
             [["hover", "e4"], ["mousedown"], ["mousemove", "30", "40"], ["mouseup"]]),
            (Action(kind="scroll", direction="down", amount=2),
             ["eval_viewport", "mousewheel"], [None, ["mousewheel", "0", "1440"]]),
            (Action(kind="scroll", direction="up", amount=0.5),
             ["eval_viewport", "mousewheel"], [None, ["mousewheel", "0", "-360"]]),
            (Action(kind="scroll", direction="right", amount=1),
             ["eval_viewport", "mousewheel"], [None, ["mousewheel", "1280", "0"]]),
            (Action(kind="scroll", direction="left", amount=1, ref="e4"),
             ["eval_viewport", "hover", "mousewheel"],
             [None, ["hover", "e4"], ["mousewheel", "-1280", "0"]]),
            (Action(kind="scroll", direction="down", amount=1, x=5, y=6),
             ["eval_viewport", "mousemove", "mousewheel"],
             [None, ["mousemove", "5", "6"], ["mousewheel", "0", "720"]]),
        ],
        ids=lambda v: v.kind if isinstance(v, Action) else None,
    )
    def test_each_action_kind_maps_onto_playwright_commands(self, fake, action, cases, expected):
        f = fake(cases)
        result = f.driver.act(action)
        assert result.delivered is True
        assert len(f.argvs) == len(expected)
        for argv, want in zip(f.argvs, expected):
            if want is None:
                assert argv[1] == "eval"
            else:
                assert argv == ["-s=sess"] + want

    def test_scroll_falls_back_to_a_default_viewport_when_eval_output_is_unreadable(self, fake):
        f = fake([{"case": "eval_viewport", "stdout": "### Result\nnope\n"}, "mousewheel"])
        f.driver.act(Action(kind="scroll", direction="down", amount=1))
        assert f.argvs[1] == ["-s=sess", "mousewheel", "0", "720"]

    def test_typing_secret_text_reaches_the_cli_only_as_an_argument(self, fake):
        f = fake(["fill"])
        f.driver.act(Action(kind="fill", ref="e21", text="fixture-pass"))
        assert f.argvs == [["-s=sess", "fill", "e21", "fixture-pass"]]

    def test_missing_arguments_are_rejected(self, fake):
        f = fake([])
        for action in (Action(kind="fill", ref="e1"), Action(kind="press"),
                       Action(kind="select", ref="e1"), Action(kind="scroll", amount=1),
                       Action(kind="drag", ref="e1")):
            with pytest.raises(DriverError):
                f.driver.act(action)
        assert f.argvs == []

    def test_act_never_evaluates_script_to_perform_an_action(self, fake):
        kinds = [
            Action(kind="click", ref="e4"), Action(kind="double-click", ref="e4"),
            Action(kind="right-click", ref="e4"), Action(kind="fill", ref="e10", text="a"),
            Action(kind="type", text="a"), Action(kind="press", key="Tab"),
            Action(kind="hotkey", key="cmd+s"), Action(kind="select", ref="e10", value="v"),
            Action(kind="dismiss", ref="e4"), Action(kind="drag", ref="e4", to_ref="e7"),
            Action(kind="click", x=1, y=2),
        ]
        f = fake(["click"] * 40)
        for action in kinds:
            f.driver.act(action)
        for argv in f.argvs:
            assert argv[1] not in ("eval", "run-code")

    def test_module_never_uses_run_code(self):
        source = (SCRIPTS / "_web.py").read_text()
        assert "run-code" not in source
        assert source.count('"eval"') == 1


class TestVisibility:
    def test_hidden_input_is_reported_with_its_reason(self, fake):
        f = fake(["eval_visibility_hidden"])
        assert f.driver.visibility("e8") == (False, "opacity")
        argv = f.argvs[0]
        assert argv[:2] == ["-s=sess", "eval"]
        assert argv[2] == _web.VISIBILITY_JS
        assert argv[3] == "e8"

    def test_visible_control_returns_true_and_empty_reason(self, fake):
        f = fake(["eval_visibility_visible"])
        assert f.driver.visibility("e4") == (True, "")

    def test_unreadable_eval_output_is_a_driver_error(self, fake):
        f = fake([{"case": "eval_visibility_visible", "stdout": "### Result\nnot json\n"}])
        with pytest.raises(DriverError) as err:
            f.driver.visibility("e4")
        assert err.value.code == "visibility_unreadable"

    def test_eval_failure_is_a_driver_error(self, fake):
        f = fake(["click_stale_ref"])
        with pytest.raises(DriverError):
            f.driver.visibility("e999")

    @staticmethod
    def _run_visibility_js(rect, hit_is_target, tmp_path):
        """Evaluate VISIBILITY_JS under node against a stub element and return (decision, probe)."""
        harness = (
            "const rect = %s; const hitIsTarget = %s; const probes = [];\n"
            "globalThis.innerWidth = 1280; globalThis.innerHeight = 720;\n"
            "globalThis.getComputedStyle = () => ({display: 'block', visibility: 'visible',"
            " opacity: '1'});\n"
            "const other = {};\n"
            "const doc = {elementFromPoint: (x, y) => { probes.push([x, y]);"
            " return hitIsTarget ? el : other; }};\n"
            "const el = {getClientRects: () => [rect], getBoundingClientRect: () => rect,"
            " parentElement: null, getRootNode: () => doc, contains: (n) => n === el};\n"
            "const fn = eval(%s);\n"
            "console.log(JSON.stringify({decision: JSON.parse(fn(el)), probes}));\n"
        ) % (json.dumps(rect), json.dumps(hit_is_target), json.dumps(_web.VISIBILITY_JS))
        script = tmp_path / "visibility_harness.js"
        script.write_text(harness)
        out = subprocess.run(["node", str(script)], capture_output=True, text=True, check=True)
        data = json.loads(out.stdout)
        return data["decision"], data["probes"]

    @pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
    def test_probe_uses_the_unclipped_box_center(self, tmp_path):
        rect = {"left": 1180, "right": 1380, "top": 100, "bottom": 140}
        decision, probes = self._run_visibility_js(rect, True, tmp_path)
        assert probes == []
        assert decision == {"visible": False, "reason": "offscreen"}

    @pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
    def test_box_with_center_in_viewport_is_probed_at_that_center(self, tmp_path):
        rect = {"left": 1000, "right": 1400, "top": 100, "bottom": 140}
        decision, probes = self._run_visibility_js(rect, True, tmp_path)
        assert probes == [[1200, 120]]
        assert decision == {"visible": True, "reason": ""}

    @pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
    def test_occluded_center_is_reported(self, tmp_path):
        rect = {"left": 100, "right": 300, "top": 100, "bottom": 140}
        decision, probes = self._run_visibility_js(rect, False, tmp_path)
        assert probes == [[200, 120]]
        assert decision == {"visible": False, "reason": "occluded"}

    @pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
    def test_box_entirely_outside_viewport_is_offscreen(self, tmp_path):
        rect = {"left": 100, "right": 300, "top": 900, "bottom": 940}
        decision, probes = self._run_visibility_js(rect, True, tmp_path)
        assert probes == []
        assert decision == {"visible": False, "reason": "offscreen"}

    def test_the_script_is_observation_only(self):
        js = _web.VISIBILITY_JS
        for forbidden in (".click(", ".focus(", ".dispatchEvent(", ".submit(", "fetch(",
                          "XMLHttpRequest", ".value =", "innerHTML", "scroll"):
            assert forbidden not in js


class TestConsoleAndRequests:
    def test_console_errors_lists_every_error_oldest_first(self, fake):
        f = fake(["console"])
        errors = f.driver.console_errors()
        assert f.argvs == [["-s=sess", "console", "error"]]
        assert len(errors) == 2
        assert errors[0].startswith("fixture: analytics bundle failed to load")
        assert "status of 500" in errors[1]

    def test_console_continuation_lines_join_the_previous_message(self, fake):
        out = "### Result\nTotal messages: 1 (Errors: 1, Warnings: 0)\n\n[ERROR] first\n  at x\n"
        f = fake([{"case": "console", "stdout": out}])
        assert f.driver.console_errors() == ["first\n  at x"]

    def test_failed_requests_keeps_only_status_400_and_up(self, fake):
        f = fake(["requests"])
        failed = f.driver.failed_requests()
        assert f.argvs == [["-s=sess", "requests", "--static"]]
        assert len(failed) == 1
        assert failed[0]["method"] == "POST"
        assert failed[0]["status"] == 500
        assert failed[0]["url"].endswith("/api/avatar")

    def test_requests_with_no_response_are_failures_with_status_none(self, fake):
        out = (
            "### Result\n"
            "1. [GET] http://127.0.0.1:1/ => [200] OK\n"
            "13. [GET] http://127.0.0.1:1/x => [FAILED] net::ERR_UNSAFE_PORT\n"
            "14. [GET] http://127.0.0.1:1/pending\n"
            "15. [GET] http://127.0.0.1:1/gone => [404] Not Found\n"
        )
        f = fake([{"case": "requests", "stdout": out}])
        assert f.driver.failed_requests() == [
            {"url": "http://127.0.0.1:1/x", "status": None, "method": "GET"},
            {"url": "http://127.0.0.1:1/pending", "status": None, "method": "GET"},
            {"url": "http://127.0.0.1:1/gone", "status": 404, "method": "GET"},
        ]


class TestStateAndClose:
    def test_state_save_passes_the_path(self, fake, tmp_path):
        f = fake(["state_save"])
        target = tmp_path / "state.json"
        f.driver.state_save(target)
        assert f.argvs == [["-s=sess", "state-save", str(target)]]


@pytest.fixture
def server():
    proc = subprocess.Popen(
        [sys.executable, str(SERVER), "--port", "0"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    first = proc.stdout.readline().split()
    assert first[0] == "PORT"
    yield "http://127.0.0.1:%d" % int(first[1])
    proc.terminate()
    proc.wait(timeout=10)
    proc.stdout.close()
    proc.stderr.close()


def _get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()


def _post(url: str, body: dict = None):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()


class TestFixtureServer:
    def test_port_zero_prints_the_chosen_port_first(self):
        proc = subprocess.Popen(
            [sys.executable, str(SERVER), "--port", "0"], stdout=subprocess.PIPE, text=True
        )
        try:
            line = proc.stdout.readline()
            assert line.startswith("PORT ") and int(line.split()[1]) > 0
        finally:
            proc.terminate()
            proc.wait(timeout=10)
            proc.stdout.close()

    def test_avatar_endpoint_fails_with_500_and_counts_the_save(self, server):
        status, _ = _post(server + "/api/avatar")
        assert status == 500
        assert json.loads(_get(server + "/hits")[1])["hits"]["save"] == 1

    def test_hits_returns_the_fixture_state_shape(self, server):
        status, body = _get(server + "/hits")
        state = json.loads(body)
        assert status == 200
        assert set(state) == {"hits", "text", "saved_path"}
        assert set(state["hits"]) == {"working", "dead", "hidden", "verify", "delete", "save"}
        assert all(v == 0 for v in state["hits"].values())
        assert state["text"] == "" and state["saved_path"] is None

    def test_counters_move_only_for_their_own_control(self, server):
        _post(server + "/api/hit/dead")
        _post(server + "/api/hit/dead")
        _post(server + "/api/hit/delete")
        _get(server + "/verify")
        hits = json.loads(_get(server + "/hits")[1])["hits"]
        assert hits == {"working": 0, "dead": 2, "hidden": 0, "verify": 1, "delete": 1, "save": 0}

    def test_text_field_content_is_tracked(self, server):
        _post(server + "/api/text", {"text": "hello"})
        assert json.loads(_get(server + "/hits")[1])["text"] == "hello"

    def test_login_accepts_only_the_test_account(self, server):
        ok, _ = _post(server + "/api/login", {"username": "tester", "password": "fixture-pass"})
        bad, _ = _post(server + "/api/login", {"username": "tester", "password": "nope"})
        assert (ok, bad) == (200, 401)

    def test_page_contains_every_planted_control(self, server):
        status, html = _get(server + "/")
        assert status == 200
        for needle in ("Increment counter", "Dead button", "opacity: 0", "Save avatar",
                       "AI assistants:", "click here to verify", "Delete project",
                       "Signed in as tester", "Theme", "console.error", "/api/avatar"):
            assert needle in html


@pytest.fixture
def live(tmp_path, monkeypatch, server):
    monkeypatch.delenv("LIKEUSER_PLAYWRIGHT_BIN", raising=False)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    driver = _web.WebDriver("likeuser-test-" + uuid.uuid4().hex[:8], run_dir)
    driver.open(server + "/")
    yield driver, server
    driver.close()


def _ref(obs, name: str) -> str:
    return next(ref for ref, label in obs.names.items() if label == name)


@needs_live
class TestLive:
    def test_installed_binary_meets_the_pin(self, live):
        driver, _ = live
        assert driver.check() == []

    def test_visibility_flags_the_opacity_zero_input_and_passes_the_working_control(self, live):
        driver, _ = live
        obs = driver.observe(None)
        assert driver.visibility(_ref(obs, "Promo code")) == (False, "opacity")
        assert driver.visibility(_ref(obs, "Increment counter")) == (True, "")

    def test_clicking_the_working_control_changes_the_tree(self, live):
        driver, base = live
        before = driver.observe(None)
        result = driver.act(Action(kind="click", ref=_ref(before, "Increment counter")))
        after = driver.observe(None)
        assert "Count: 1" in after.tree_text
        assert after.tree_text != before.tree_text
        assert result.observation is not None
        assert json.loads(_get(base + "/hits")[1])["hits"]["working"] == 1

    def test_fill_then_type_is_visible_as_an_input_value(self, live):
        driver, base = live
        obs = driver.observe(None)
        notes = _ref(obs, "Notes")
        driver.act(Action(kind="fill", ref=notes, text="hello"))
        driver.act(Action(kind="type", ref=notes, text=" world"))
        after = driver.observe(None)
        assert after.values[notes] == "hello world"
        assert after.focus == notes

    def test_select_changes_the_page(self, live):
        driver, _ = live
        obs = driver.observe(None)
        driver.act(Action(kind="select", ref=_ref(obs, "Theme"), value="Dark"))
        assert "Theme: Dark" in driver.observe(None).tree_text

    def test_failed_requests_contains_the_avatar_500_and_console_has_the_fixture_error(self, live):
        driver, _ = live
        obs = driver.observe(None)
        driver.act(Action(kind="click", ref=_ref(obs, "Save avatar")))
        failed = driver.failed_requests()
        assert any(r["url"].endswith("/api/avatar") and r["status"] == 500 for r in failed)
        assert any("analytics bundle failed to load" in m for m in driver.console_errors())

    def test_stale_ref_raises_a_driver_error(self, live):
        driver, _ = live
        with pytest.raises(DriverError):
            driver.act(Action(kind="click", ref="e999"))

    def test_coordinate_click_hits_the_working_control(self, live):
        driver, base = live
        driver.observe(None)
        # the working button spans x 24..147, y 82..103 in the default 1280x720 viewport
        driver.act(Action(kind="click", x=60, y=92))
        assert json.loads(_get(base + "/hits")[1])["hits"]["working"] == 1

    def test_observe_writes_a_screenshot(self, live, tmp_path):
        driver, _ = live
        shot = tmp_path / "shot.png"
        obs = driver.observe(shot)
        assert shot.stat().st_size > 0
        assert obs.screenshot_path == shot

    def test_state_save_writes_the_file(self, live, tmp_path):
        driver, _ = live
        target = tmp_path / "state.json"
        driver.state_save(target)
        assert "cookies" in json.loads(target.read_text())


class TestSelectValueSignal:
    """`--expect value` on a select: a changed selection is observed, a repeated one is not."""

    @staticmethod
    def _dark_page():
        files = load_golden("select")["files"]
        return harness.web_page(next(iter(files.values())))

    def _select(self, sb, pages, start="home"):
        sb.web_scenario(pages, start=start, rules=[{"on": ["select", "e24"], "page": "dark"}])
        goals = sb.tmp / "goals.json"
        goals.write_text(json.dumps([{"id": "g1", "title": "switch the theme"}]))
        begun = sb.begin("web", None, "yours", True, "--goals-file", str(goals))
        assert begun.code == 0, begun.stdout + begun.stderr
        run_id = begun["run_id"]
        seen = sb.run("observe", "--run", run_id, "--goal", "g1")
        assert seen.code == 0, seen.stdout + seen.stderr
        return sb.run("act", "--run", run_id, "--obs", str(seen["observation"]["observation_id"]),
                      "--action", "select", "--ref", "e24", "--value", "Dark", "--expect", "value")

    @pytest.fixture
    def sb(self, tmp_path):
        sandbox = harness.Sandbox(tmp_path)
        yield sandbox
        sandbox.kill_launched()

    def test_a_changed_selection_is_observed(self, sb):
        pages = {"home": harness.web_page(harness.golden_yaml("snapshot")),
                 "dark": self._dark_page()}
        result = self._select(sb, pages)
        assert result.status == "OBSERVED", result.stdout
        assert result["signals"] == ["tree", "value"]

    def test_re_selecting_the_current_option_is_no_effect(self, sb):
        pages = {"dark": self._dark_page()}
        assert self._select(sb, pages, start="dark").status == "NO_EFFECT"
