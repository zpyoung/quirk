"""Tests for the making-videos web-app recorder, run against fake node, ffmpeg and ffprobe."""
from __future__ import annotations

import json
import re
import stat
import subprocess
import sys
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
    fh.write(json.dumps({{"tool": "ffmpeg", "argv": sys.argv[1:]}}) + "\\n")
if os.environ.get("FAKE_FFMPEG_FAIL"):
    sys.stderr.write("Conversion failed!\\n")
    sys.exit(1)
open(sys.argv[-1], "wb").write(b"mp4")
"""

FAKE_FFPROBE = """#!{python}
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps({{"tool": "ffprobe", "argv": sys.argv[1:]}}) + "\\n")
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


def test_missing_project_directory_exits_1(tmp_path, env):
    install_playwright(env)
    proc, out = record(tmp_path / "nope", write_steps(tmp_path), env)
    assert proc.returncode == 1
    assert fake_calls(env, "node") == []
