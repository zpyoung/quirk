"""Tests for the making-videos web-app recorder, run against fake node, ffmpeg and ffprobe."""
from __future__ import annotations

import functools
import http.server
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import threading
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "making-videos" / "scripts"
RECORD_PY = SCRIPTS / "record.py"
PLAYWRIGHT_VERSION = "1.64.1"

FAKE_NODE = """#!{python}
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps({{"tool": "node", "argv": sys.argv[1:], "cwd": os.getcwd(),
        "node_path": os.environ.get("NODE_PATH"),
        "browsers_path": os.environ.get("PLAYWRIGHT_BROWSERS_PATH"),
        "leaked": [k for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY") if k in os.environ]}}) + "\\n")
if os.environ.get("FAKE_NODE_FAIL"):
    sys.stderr.write("browserType.launch: Executable doesn't exist\\n")
    sys.exit(1)
webm = os.environ["FAKE_WEBM"]
open(webm, "wb").write(b"webm")
print("noise from the page")
print(webm)
"""

FAKE_FFMPEG = """#!{python}
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps({{"tool": "ffmpeg", "argv": sys.argv[1:],
        "leaked": [k for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY") if k in os.environ]}}) + "\\n")
if os.environ.get("FAKE_FFMPEG_FAIL"):
    sys.stderr.write("Conversion failed!\\n")
    sys.exit(1)
open(sys.argv[-1], "wb").write(b"mp4")
"""

FAKE_FFPROBE = """#!{python}
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps({{"tool": "ffprobe", "argv": sys.argv[1:],
        "leaked": [k for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY") if k in os.environ]}}) + "\\n")
print("12.3456")
"""

STEPS = [
    {"action": "goto", "url": "/pricing"},
    {"action": "click", "selector": "#signup"},
    {"action": "fill", "selector": "input[name=email]", "value": "a@b.co"},
    {"action": "wait", "ms": 750},
    {"action": "scroll", "selector": "footer"},
    {"action": "click", "text": "Continue"},
]


def _install_fake(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(body.format(python=sys.executable), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "studio" / "videos" / "2026-10-22-demo"
    proj.mkdir(parents=True)
    (proj / "brief.json").write_text(json.dumps({"slug": "demo", "cloud_allow": []}))
    return proj


@pytest.fixture()
def env(tmp_path: Path) -> dict:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _install_fake(bin_dir, "node", FAKE_NODE)
    _install_fake(bin_dir, "ffmpeg", FAKE_FFMPEG)
    _install_fake(bin_dir, "ffprobe", FAKE_FFPROBE)
    cache = tmp_path / "cache"
    return {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "QUIRK_STUDIO": str(tmp_path / "studio"),
        "QUIRK_VIDEO_CACHE": str(cache),
        "FAKE_LOG": str(tmp_path / "fake.log"),
        "FAKE_WEBM": str(tmp_path / "raw" / "video.webm"),
        "GEMINI_API_KEY": "gem-secret",
        "OPENAI_API_KEY": "oai-secret",
    }


def install_playwright(env: dict, version: str = PLAYWRIGHT_VERSION) -> Path:
    pkg = Path(env["QUIRK_VIDEO_CACHE"]) / "node" / "node_modules" / "playwright"
    pkg.mkdir(parents=True)
    (pkg / "package.json").write_text(json.dumps({"name": "playwright", "version": version}))
    Path(env["FAKE_WEBM"]).parent.mkdir(parents=True, exist_ok=True)
    return pkg


def write_steps(tmp_path: Path, steps: object = STEPS) -> Path:
    path = tmp_path / "steps.json"
    path.write_text(json.dumps(steps))
    return path


def record(project: Path, steps: Path, env: dict, *extra: object, url: str = "http://localhost:3000/app"):
    proc = subprocess.run(
        [sys.executable, str(RECORD_PY), "--project", str(project), "--url", url,
         "--steps", str(steps), *map(str, extra)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    out = proc.stdout.strip()
    assert out, f"no stdout (rc={proc.returncode}): {proc.stderr}"
    assert len(out.splitlines()) == 1
    return proc, json.loads(out)


def fake_calls(env: dict, tool: str) -> list:
    path = Path(env["FAKE_LOG"])
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [r for r in rows if r["tool"] == tool]


def generated_script(project: Path) -> str:
    scripts = list((project / "assets" / "recordings").glob("*.cjs"))
    assert len(scripts) == 1
    return scripts[0].read_text()


def test_records_converts_and_reports_json(project, env, tmp_path):
    install_playwright(env)
    proc, out = record(project, write_steps(tmp_path), env)
    assert proc.returncode == 0, proc.stderr
    assert set(out) == {"webm", "mp4", "duration_s"}
    assert out["webm"] == env["FAKE_WEBM"]
    assert out["mp4"] == str(Path(env["FAKE_WEBM"]).with_suffix(".mp4"))
    assert Path(out["mp4"]).read_bytes() == b"mp4"
    assert out["duration_s"] == pytest.approx(12.346, abs=1e-3)


def test_generated_script_records_at_size_and_runs_steps_in_order(project, env, tmp_path):
    pkg = install_playwright(env)
    proc, out = record(project, write_steps(tmp_path), env, "--size", "1280x720", "--fps", "60")
    assert proc.returncode == 0, proc.stderr
    script = generated_script(project)
    assert "recordVideo" in script
    assert re.search(r'const SIZE = \{"width": 1280, "height": 720\}', script)
    assert "const FPS = 60;" in script
    assert re.search(r"recordVideo:\s*\{[^}]*size: SIZE[^}]*fps: FPS", script, re.S)
    assert "chromium" in script and "headless" in script
    assert "context.close()" in script
    assert str(pkg) in script
    positions = [script.index(token) for token in
                 ('"/pricing"', '"#signup"', '"input[name=email]"', '"a@b.co"', "750", '"footer"', '"Continue"')]
    assert positions == sorted(positions)
    (node_call,) = fake_calls(env, "node")
    assert node_call["argv"][0].endswith(".cjs")
    assert Path(node_call["argv"][0]).parent == project / "assets" / "recordings"
    assert node_call["node_path"].split(":")[0] == str(pkg.parent)


def test_default_size_and_fps(project, env, tmp_path):
    install_playwright(env)
    record(project, write_steps(tmp_path), env)
    script = generated_script(project)
    assert 'const SIZE = {"width": 1920, "height": 1080}' in script
    assert "const FPS = 30;" in script


def test_step_text_is_data_not_code(project, env, tmp_path):
    install_playwright(env)
    nasty = '"); process.exit(7); //'
    record(project, write_steps(tmp_path, [{"action": "fill", "selector": "#a", "value": nasty}]), env)
    script = generated_script(project)
    assert json.dumps(nasty) in script
    assert nasty not in script.replace(json.dumps(nasty), "")


def test_ffmpeg_argv(project, env, tmp_path):
    install_playwright(env)
    record(project, write_steps(tmp_path), env)
    (ff,) = fake_calls(env, "ffmpeg")
    argv = ff["argv"]
    assert argv[argv.index("-i") + 1] == env["FAKE_WEBM"]
    assert argv[argv.index("-c:v") + 1] == "libx264"
    assert argv[argv.index("-pix_fmt") + 1] == "yuv420p"
    assert argv[argv.index("-crf") + 1] == "18"
    assert argv[argv.index("-movflags") + 1] == "+faststart"
    assert argv[-1] == str(Path(env["FAKE_WEBM"]).with_suffix(".mp4"))
    (probe,) = fake_calls(env, "ffprobe")
    assert probe["argv"][-1] == argv[-1]


def test_unknown_action_exits_2_before_launching(project, env, tmp_path):
    install_playwright(env)
    steps = write_steps(tmp_path, [{"action": "goto", "url": "/"}, {"action": "teleport"}])
    proc, out = record(project, steps, env)
    assert proc.returncode == 2
    assert "teleport" in out["error"] and "step 2" in out["error"]
    assert fake_calls(env, "node") == []
    assert not (project / "assets" / "recordings").exists()


@pytest.mark.parametrize(
    "step",
    [
        {"action": "click"},
        {"action": "fill", "selector": "#a"},
        {"action": "wait"},
        {"action": "wait", "ms": -5},
        {"action": "goto", "url": 5},
        "click",
    ],
)
def test_malformed_steps_exit_2(project, env, tmp_path, step):
    install_playwright(env)
    proc, out = record(project, write_steps(tmp_path, [step]), env)
    assert proc.returncode == 2
    assert fake_calls(env, "node") == []


def test_steps_file_must_be_a_json_list(project, env, tmp_path):
    install_playwright(env)
    proc, out = record(project, write_steps(tmp_path, {"action": "goto"}), env)
    assert proc.returncode == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    proc, out = record(project, bad, env)
    assert proc.returncode == 2


@pytest.mark.parametrize("extra", [("--size", "big"), ("--size", "0x720"), ("--fps", "0"), ("--fps", "abc")])
def test_bad_size_or_fps_exit_2(project, env, tmp_path, extra):
    install_playwright(env)
    proc, out = record(project, write_steps(tmp_path), env, *extra)
    assert proc.returncode == 2


def test_non_http_url_exits_2(project, env, tmp_path):
    install_playwright(env)
    proc, out = record(project, write_steps(tmp_path), env, url="file:///etc/passwd")
    assert proc.returncode == 2


def test_missing_playwright_exits_3_with_the_install_command(project, env, tmp_path):
    proc, out = record(project, write_steps(tmp_path), env)
    assert proc.returncode == 3
    assert "doctor.py install --what playwright --yes" in json.dumps(out)
    assert fake_calls(env, "node") == []


def test_wrong_playwright_version_exits_3(project, env, tmp_path):
    install_playwright(env, version="1.50.0")
    proc, out = record(project, write_steps(tmp_path), env)
    assert proc.returncode == 3
    assert PLAYWRIGHT_VERSION in json.dumps(out)


def test_missing_node_exits_3(project, env, tmp_path):
    install_playwright(env)
    env["PATH"] = "/usr/bin:/bin"
    proc, out = record(project, write_steps(tmp_path), env)
    assert proc.returncode == 3
    assert "node" in json.dumps(out)


def test_missing_ffmpeg_exits_3(project, env, tmp_path):
    install_playwright(env)
    (tmp_path / "bin" / "ffmpeg").unlink()
    proc, out = record(project, write_steps(tmp_path), env)
    assert proc.returncode == 3
    assert "ffmpeg" in json.dumps(out)


def test_node_failure_exits_1_and_still_logs(project, env, tmp_path):
    install_playwright(env)
    env["FAKE_NODE_FAIL"] = "1"
    proc, out = record(project, write_steps(tmp_path), env)
    assert proc.returncode == 1
    assert "Executable doesn't exist" in out["error"]
    assert fake_calls(env, "ffmpeg") == []
    assert json.loads((project / "calls.jsonl").read_text().splitlines()[0])["status"] == 0


def test_ffmpeg_failure_exits_1(project, env, tmp_path):
    install_playwright(env)
    env["FAKE_FFMPEG_FAIL"] = "1"
    proc, out = record(project, write_steps(tmp_path), env)
    assert proc.returncode == 1
    assert "Conversion failed" in out["error"]


def test_logs_a_playwright_record_with_host_and_no_query(project, env, tmp_path):
    install_playwright(env)
    record(project, write_steps(tmp_path), env, url="http://localhost:3000/app?token=secret#frag")
    (entry,) = [json.loads(l) for l in (project / "calls.jsonl").read_text().splitlines()]
    assert entry["provider"] == "playwright"
    assert entry["host"] == "localhost"
    assert entry["path"] == "/app"
    assert entry["status"] == 200
    assert "token" not in json.dumps(entry)
    assert {"ts", "method", "bytes"} <= set(entry)


def test_child_environment_is_scrubbed_of_keys(project, env, tmp_path):
    install_playwright(env)
    record(project, write_steps(tmp_path), env)
    (node_call,) = fake_calls(env, "node")
    assert node_call["leaked"] == []


def test_node_child_keeps_playwright_browsers_in_the_cache(project, env, tmp_path):
    install_playwright(env)
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(tmp_path / "elsewhere")
    record(project, write_steps(tmp_path), env)
    (node_call,) = fake_calls(env, "node")
    assert node_call["browsers_path"] == str(Path(env["QUIRK_VIDEO_CACHE"]) / "ms-playwright")


def test_conversion_children_are_scrubbed_of_keys(project, env, tmp_path):
    install_playwright(env)
    record(project, write_steps(tmp_path), env)
    (ffmpeg_call,) = fake_calls(env, "ffmpeg")
    (ffprobe_call,) = fake_calls(env, "ffprobe")
    assert ffmpeg_call["leaked"] == []
    assert ffprobe_call["leaked"] == []


def test_missing_project_directory_exits_1(tmp_path, env):
    install_playwright(env)
    proc, out = record(tmp_path / "nope", write_steps(tmp_path), env)
    assert proc.returncode == 1
    assert fake_calls(env, "node") == []


FAKE_NODE_FRAMES = """#!{python}
import json, os, re, sys
script = open(sys.argv[1]).read()
frames_dir = json.loads(re.search(r"const FRAMES_DIR = (.*);", script).group(1))
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps({{"tool": "node", "argv": sys.argv[1:]}}) + "\\n")
os.makedirs(frames_dir, exist_ok=True)
listing = os.path.join(frames_dir, "list.txt")
open(listing, "w").write("file '00000.jpg'\\n")
print("noise from the page")
print(listing)
"""

FAKE_FFPROBE_SIZE = """#!{python}
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps({{"tool": "ffprobe", "argv": sys.argv[1:]}}) + "\\n")
if any("stream=width,height" in a for a in sys.argv):
    print(os.environ.get("FAKE_SIZE", "2560x1440"))
else:
    print("12.3456")
"""

POINTER_ID = "mv-pointer"


@pytest.fixture()
def frames_env(env: dict, tmp_path: Path) -> dict:
    bin_dir = tmp_path / "bin"
    _install_fake(bin_dir, "node", FAKE_NODE_FRAMES)
    _install_fake(bin_dir, "ffprobe", FAKE_FFPROBE_SIZE)
    install_playwright(env)
    return env


def frames_dirs(project: Path) -> list:
    return list((project / "assets" / "recordings").glob(".frames-*"))


@pytest.mark.parametrize(
    "step, needle",
    [
        ({"action": "hover"}, "hover"),
        ({"action": "move", "x": 10}, "move"),
        ({"action": "move", "y": 10}, "move"),
        ({"action": "move", "x": "10", "y": 5}, "move"),
        ({"action": "press"}, "press"),
        ({"action": "press", "key": ""}, "press"),
        ({"action": "drag", "from": {"selector": "#a"}}, "drag"),
        ({"action": "drag", "to": {"selector": "#a"}}, "drag"),
        ({"action": "drag", "from": {"selector": "#a"}, "to": {"x": 3}}, "drag"),
        ({"action": "drag", "from": {"selector": "#a"}, "to": "#b"}, "drag"),
        ({"action": "drag", "from": {}, "to": {"selector": "#b"}}, "drag"),
    ],
)
def test_malformed_pointer_steps_exit_2_naming_the_step(project, env, tmp_path, step, needle):
    install_playwright(env)
    steps = write_steps(tmp_path, [{"action": "goto", "url": "/"}, step])
    proc, out = record(project, steps, env)
    assert proc.returncode == 2
    assert "step 2" in out["error"] and needle in out["error"]
    assert fake_calls(env, "node") == []


@pytest.mark.parametrize("scale", ["0", "4", "-1", "2.5", "two"])
def test_bad_scale_exits_2_before_launching(project, env, tmp_path, scale):
    install_playwright(env)
    proc, out = record(project, write_steps(tmp_path), env, "--scale", scale)
    assert proc.returncode == 2
    assert fake_calls(env, "node") == []


def test_default_capture_keeps_recordvideo_and_the_playwright_cursor(project, env, tmp_path):
    install_playwright(env)
    record(project, write_steps(tmp_path), env)
    script = generated_script(project)
    assert "showActions" in script
    assert "recordVideo" in script
    assert "const POINTER = false;" in script and POINTER_ID not in script
    assert "startScreencast" not in script


def test_press_alone_keeps_the_default_capture(project, env, tmp_path):
    install_playwright(env)
    steps = write_steps(tmp_path, [{"action": "press", "key": "Tab"}, {"action": "press", "key": "Shift+Tab", "ms": 900}])
    proc, out = record(project, steps, env)
    assert proc.returncode == 0, proc.stderr
    script = generated_script(project)
    assert "showActions" in script and "const POINTER = false;" in script and POINTER_ID not in script
    assert '"Shift+Tab"' in script and "keyboard.press" in script


@pytest.mark.parametrize(
    "step",
    [
        {"action": "hover", "selector": "#add"},
        {"action": "hover", "text": "Add project"},
        {"action": "move", "x": 100, "y": 200},
        {"action": "drag", "from": {"selector": "#a"}, "to": {"x": 10, "y": 20}},
    ],
)
def test_pointer_steps_at_scale_1_draw_a_pointer_and_drop_showactions(project, env, tmp_path, step):
    install_playwright(env)
    proc, out = record(project, write_steps(tmp_path, [step]), env)
    assert proc.returncode == 0, proc.stderr
    assert set(out) == {"webm", "mp4", "duration_s"} and out["webm"] == env["FAKE_WEBM"]
    script = generated_script(project)
    assert "recordVideo" in script and "showActions" not in script
    assert POINTER_ID in script and "addInitScript" in script and "pointer-events:none" in script
    assert "startScreencast" not in script
    assert "const POINTER = true;" in script
    assert len(fake_calls(env, "ffprobe")) == 1


def test_pointer_step_values_are_data_not_code(project, env, tmp_path):
    install_playwright(env)
    nasty = '"); process.exit(7); //'
    steps = [
        {"action": "hover", "selector": nasty},
        {"action": "drag", "from": {"text": nasty}, "to": {"selector": nasty}},
        {"action": "press", "key": nasty},
    ]
    record(project, write_steps(tmp_path, steps), env)
    script = generated_script(project)
    assert json.dumps(nasty) in script
    assert nasty not in script.replace(json.dumps(nasty), "")


def test_scale_2_script_uses_the_screencast_path(project, frames_env, tmp_path):
    proc, out = record(project, write_steps(tmp_path), frames_env, "--size", "1280x720", "--scale", "2")
    assert proc.returncode == 0, proc.stderr
    script = generated_script(project)
    assert "recordVideo" not in script and "showActions" not in script
    assert "const SCALE = 2;" in script
    assert "--force-device-scale-factor=" in script and "--window-size=" in script
    assert "viewport: null" in script
    assert "Page.startScreencast" in script and "Page.screencastFrameAck" in script
    assert re.search(r"maxWidth: SIZE\.width \* SCALE", script) and re.search(r"maxHeight: SIZE\.height \* SCALE", script)
    assert "const POINTER = true;" in script and POINTER_ID in script
    assert re.search(r'const FRAMES_DIR = ".*/assets/recordings/\.frames-\d{8}-\d{6}";', script)


def test_scale_2_reports_null_webm_converts_the_list_and_removes_the_frames(project, frames_env, tmp_path):
    proc, out = record(project, write_steps(tmp_path), frames_env, "--size", "1280x720", "--scale", "2")
    assert proc.returncode == 0, proc.stderr
    assert set(out) == {"webm", "mp4", "duration_s"}
    assert out["webm"] is None
    mp4 = Path(out["mp4"])
    assert mp4.parent == project / "assets" / "recordings" and mp4.suffix == ".mp4"
    assert mp4.read_bytes() == b"mp4"
    assert out["duration_s"] == pytest.approx(12.346, abs=1e-3)
    (ff,) = fake_calls(frames_env, "ffmpeg")
    argv = ff["argv"]
    assert argv[argv.index("-f") + 1] == "concat"
    assert argv[argv.index("-i") + 1].endswith("/list.txt")
    assert argv[argv.index("-crf") + 1] == "18" and argv[-1] == str(mp4)
    assert frames_dirs(project) == []


def test_scale_2_list_building_has_no_upper_bound_on_a_frames_hold(project, frames_env, tmp_path):
    proc, out = record(project, write_steps(tmp_path), frames_env, "--size", "1280x720", "--scale", "2")
    assert proc.returncode == 0, proc.stderr
    script = generated_script(project)
    assert "(hold > 0 ? hold : 0.2).toFixed(4)" in script
    assert not re.search(r"hold\s*<\s*\d", script), "a long static interval would be shortened"


def test_scale_2_asserts_the_frame_size_and_keeps_the_frames_on_a_mismatch(project, frames_env, tmp_path):
    frames_env["FAKE_SIZE"] = "1280x720"
    proc, out = record(project, write_steps(tmp_path), frames_env, "--size", "1280x720", "--scale", "2")
    assert proc.returncode == 1
    assert "1280x720" in out["error"] and "2560x1440" in out["error"]
    assert len(frames_dirs(project)) == 1


def test_scale_2_even_rounds_the_expected_size(project, frames_env, tmp_path):
    frames_env["FAKE_SIZE"] = "1202x1202"
    proc, out = record(project, write_steps(tmp_path), frames_env, "--size", "601x601", "--scale", "2")
    assert proc.returncode == 0, proc.stderr


def test_scale_2_keeps_the_frames_when_ffmpeg_fails(project, frames_env, tmp_path):
    frames_env["FAKE_FFMPEG_FAIL"] = "1"
    proc, out = record(project, write_steps(tmp_path), frames_env, "--scale", "2")
    assert proc.returncode == 1
    assert len(frames_dirs(project)) == 1


def test_scale_1_flag_matches_the_default(project, env, tmp_path):
    install_playwright(env)
    proc, out = record(project, write_steps(tmp_path), env, "--scale", "1")
    assert proc.returncode == 0, proc.stderr
    assert out["webm"] == env["FAKE_WEBM"]
    assert "showActions" in generated_script(project)


def _working_node_dir():
    candidates = [Path(p) for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    candidates += sorted((Path.home() / ".nvm" / "versions" / "node").glob("*/bin"), reverse=True)
    for directory in candidates:
        node = directory / "node"
        if node.is_file():
            probe = subprocess.run([str(node), "-v"], capture_output=True, text=True)
            if probe.returncode == 0:
                return directory
    return None


LIVE_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
html, body { margin: 0; height: 100%; background: #20a050; }
#add { position: absolute; left: 200px; top: 300px; width: 400px; height: 120px; border: 0;
       background: #d02020; color: #fff; font: 28px sans-serif; }
#add:hover { background: #2030d0; }
</style></head><body><button id="add">Add project</button></body></html>
"""


DRAG_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
html, body { margin: 0; height: 100%; background: #202020; }
body.pressed { background: #20a050; }
#box { position: absolute; left: 100px; top: 100px; width: 120px; height: 120px; background: #d02020; }
#go { position: absolute; left: 900px; top: 600px; width: 200px; height: 60px; border: 0; background: #888; }
body.clicked #go { background: #f0f000; }
</style></head><body>
<div id="box"></div><button id="go">Go</button>
<script>
let held = false;
box.addEventListener("mousedown", () => { held = true; });
addEventListener("mouseup", () => { held = false; });
addEventListener("mousemove", (e) => {
  if (held) { box.style.left = (e.clientX - 60) + "px"; box.style.top = (e.clientY - 60) + "px"; }
});
addEventListener("keydown", (e) => { if (e.key === "a") document.body.classList.add("pressed"); });
go.addEventListener("click", () => document.body.classList.add("clicked"));
</script></body></html>
"""


@pytest.fixture()
def live_page(tmp_path: Path, request):
    root = tmp_path / "site"
    root.mkdir()
    (root / "index.html").write_text(getattr(request, "param", LIVE_PAGE))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    server.shutdown()
    server.server_close()


def _ffprobe_size(path: Path) -> str:
    proc = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                           "stream=width,height", "-of", "csv=s=x:p=0", str(path)],
                          capture_output=True, text=True)
    return proc.stdout.strip()


def _frame_rgb(path: Path, seek: "list[str]", width: int, height: int) -> bytes:
    proc = subprocess.run(["ffmpeg", "-v", "error", *seek, "-i", str(path), "-frames:v", "1",
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    assert proc.returncode == 0, proc.stderr
    assert len(proc.stdout) == width * height * 3
    return proc.stdout


def _pixel(frame: bytes, width: int, x: int, y: int) -> "tuple[int, int, int]":
    offset = (y * width + x) * 3
    return frame[offset], frame[offset + 1], frame[offset + 2]


def _pixel_series(path: Path, x: int, y: int, fps: int) -> "list[tuple[int, int, int]]":
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={fps},format=rgb24,crop=1:1:{x}:{y}",
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    assert proc.returncode == 0, proc.stderr
    return [tuple(proc.stdout[i:i + 3]) for i in range(0, len(proc.stdout), 3)]


def _near(actual, expected, tolerance=24) -> bool:
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))


def test_live_scale2_produces_true_2x_frames(project, live_page, tmp_path):
    node_dir = _working_node_dir()
    ffmpeg_ok = shutil.which("ffmpeg") and shutil.which("ffprobe")
    cache = Path(os.environ.get("QUIRK_VIDEO_CACHE") or "~/.cache/quirk-video").expanduser()
    assert node_dir is not None, "no working node found on PATH or under ~/.nvm"
    assert ffmpeg_ok, "ffmpeg and ffprobe are required"
    assert (cache / "node" / "node_modules" / "playwright" / "package.json").is_file(), "pinned Playwright is not installed"

    env = dict(os.environ)
    env["PATH"] = f"{node_dir}{os.pathsep}{env.get('PATH', '')}"
    env["QUIRK_STUDIO"] = str(tmp_path / "studio")
    steps = write_steps(tmp_path, [
        {"action": "wait", "ms": 600},
        {"action": "hover", "selector": "#add", "ms": 900},
        {"action": "wait", "ms": 400},
    ])
    proc = subprocess.run(
        [sys.executable, str(RECORD_PY), "--project", str(project), "--url", live_page,
         "--steps", str(steps), "--size", "1280x720", "--scale", "2"],
        capture_output=True, text=True, env=env, timeout=240,
    )
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    out = json.loads(proc.stdout.strip())
    assert out["webm"] is None
    mp4 = Path(out["mp4"])
    assert mp4.is_file()
    assert frames_dirs(project) == []
    assert _ffprobe_size(mp4) == "2560x1440"

    w, h = 2560, 1440
    first = _frame_rgb(mp4, [], w, h)
    last = _frame_rgb(mp4, ["-sseof", "-0.3"], w, h)
    assert _near(_pixel(first, w, 2400, 1350), (0x20, 0xA0, 0x50)), "bottom-right is not the page background"
    assert _near(_pixel(last, w, 2400, 1350), (0x20, 0xA0, 0x50))
    # the button spans x 400..1200 and y 600..840 at 2x; sample left of the pointer, which rests at its center
    before, after = _pixel(first, w, 480, 720), _pixel(last, w, 480, 720)
    assert _near(before, (0xD0, 0x20, 0x20)), before
    assert _near(after, (0x20, 0x30, 0xD0)), after


@pytest.mark.parametrize("live_page", [DRAG_PAGE], indirect=True)
def test_live_scale1_pointer_steps_move_press_click_and_drag_for_real(project, live_page, tmp_path):
    node_dir = _working_node_dir()
    assert node_dir is not None, "no working node found on PATH or under ~/.nvm"
    env = dict(os.environ)
    env["PATH"] = f"{node_dir}{os.pathsep}{env.get('PATH', '')}"
    env["QUIRK_STUDIO"] = str(tmp_path / "studio")
    steps = write_steps(tmp_path, [
        {"action": "move", "x": 300, "y": 200},
        {"action": "press", "key": "a"},
        {"action": "drag", "from": {"selector": "#box"}, "to": {"x": 600, "y": 400}},
        {"action": "click", "selector": "#go"},
        {"action": "hover", "text": "Go", "ms": 300},
    ])
    proc = subprocess.run(
        [sys.executable, str(RECORD_PY), "--project", str(project), "--url", live_page,
         "--steps", str(steps), "--size", "1280x720"],
        capture_output=True, text=True, env=env, timeout=240,
    )
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    out = json.loads(proc.stdout.strip())
    assert out["webm"] and Path(out["webm"]).is_file()
    assert _ffprobe_size(Path(out["mp4"])) == "1280x720"
    w, h = 1280, 720
    last = _frame_rgb(Path(out["mp4"]), ["-sseof", "-0.2"], w, h)
    assert _near(_pixel(last, w, 600, 440), (0xD0, 0x20, 0x20)), "the box did not follow the drag"
    assert _near(_pixel(last, w, 100, 650), (0x20, 0xA0, 0x50)), "the key press did not land"
    assert _near(_pixel(last, w, 910, 640), (0xF0, 0xF0, 0x00), 40), "the click did not land"


POINTER_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
html, body { margin: 0; height: 100%; background: #203080; }
</style></head><body></body></html>
"""

POINTER_BACKGROUND = (0x20, 0x30, 0x80)


@pytest.mark.parametrize("live_page", [POINTER_PAGE], indirect=True)
def test_live_scale2_drawn_pointer_follows_real_mouse_moves(project, live_page, tmp_path):
    node_dir = _working_node_dir()
    assert node_dir is not None, "no working node found on PATH or under ~/.nvm"
    env = dict(os.environ)
    env["PATH"] = f"{node_dir}{os.pathsep}{env.get('PATH', '')}"
    env["QUIRK_STUDIO"] = str(tmp_path / "studio")
    hold_ms = 2500
    first_point, second_point = (300, 200), (900, 500)
    steps = write_steps(tmp_path, [
        {"action": "move", "x": first_point[0], "y": first_point[1]},
        {"action": "wait", "ms": hold_ms},
        {"action": "move", "x": second_point[0], "y": second_point[1]},
        {"action": "wait", "ms": hold_ms},
    ])
    proc = subprocess.run(
        [sys.executable, str(RECORD_PY), "--project", str(project), "--url", live_page,
         "--steps", str(steps), "--size", "1280x720", "--scale", "2"],
        capture_output=True, text=True, env=env, timeout=240,
    )
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    out = json.loads(proc.stdout.strip())
    mp4 = Path(out["mp4"])
    assert _ffprobe_size(mp4) == "2560x1440"

    def arrow_body_series(point):
        # the arrow's filled body sits 4 css px right of and 10 below its tip, which is the mouse position
        return _pixel_series(mp4, 2 * (point[0] + 4), 2 * (point[1] + 10), fps=4)

    at_first, at_second = arrow_body_series(first_point), arrow_body_series(second_point)
    white = [_near(p, (0xFF, 0xFF, 0xFF)) for p in at_first]
    other = [_near(p, (0xFF, 0xFF, 0xFF)) for p in at_second]
    assert len(white) == len(other) > 8

    # glides take a variable time at 2x, so find the moments instead of seeking to fixed timestamps
    on_first = [i for i in range(len(white)) if white[i] and not other[i]]
    on_second = [i for i in range(len(white)) if other[i] and not white[i]]
    assert on_first, "the pointer never appeared at the first point"
    assert on_second, "the pointer never appeared at the second point"
    assert max(on_first) < min(on_second), "the pointer did not move from the first point to the second"
    assert _near(at_first[-1], POINTER_BACKGROUND), "the pointer was left at the first point"
    assert _near(at_second[0], POINTER_BACKGROUND), "the pointer was at the second point from the start"
