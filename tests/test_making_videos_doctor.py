"""Tests for the making-videos doctor, run through subprocess with fake tools on PATH."""
from __future__ import annotations

import functools
import http.server
import importlib.util
import json
import shutil
import ssl
import subprocess
import sys
import threading
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "making-videos" / "scripts"
DOCTOR_PY = SCRIPTS / "doctor.py"

_spec = importlib.util.spec_from_file_location("mv_common_for_doctor_tests", SCRIPTS / "_mv_common.py")
common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(common)

PROLOGUE = """#!{python}
import json, os, sys
args = sys.argv[1:]
if os.environ.get("FAKE_LOG"):
    with open(os.environ["FAKE_LOG"], "a") as fh:
        fh.write(json.dumps([os.path.basename(sys.argv[0])] + args) + "\\n")
"""

FILTERS_WITH = " ... subtitles        V->V       Render text subtitles onto input video.\n"
FILTERS_WITHOUT = " ... scale            V->V       Scale the input video.\n"


def write_stub(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PROLOGUE.format(python=sys.executable) + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def ffmpeg_body(filters: str, version: str = "8.1") -> str:
    return (
        f"if '-filters' in args:\n    sys.stdout.write({filters!r})\n"
        f"else:\n    print('ffmpeg version {version} Copyright')\n"
    )


def version_body(text: str) -> str:
    return f"print({text!r})\n"


def make_tools(bin_dir: Path, *, node: str = "v22.3.0", filters: str = FILTERS_WITH) -> None:
    write_stub(bin_dir / "node", version_body(node))
    write_stub(bin_dir / "pnpm", "print('10.1.0')\n")
    write_stub(bin_dir / "ffmpeg", ffmpeg_body(filters))
    write_stub(bin_dir / "ffprobe", version_body("ffprobe version 8.1 Copyright"))


def make_venv(cache: Path, version: str = "3.12.1", missing: str = "") -> Path:
    return write_stub(
        cache / "venv" / "bin" / "python", f"print({version!r})\nprint({missing!r})\n"
    )


def make_models(cache: Path) -> None:
    model_dir = cache / "models" / "kokoro"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "kokoro-v1.0.onnx").write_bytes(b"model")
    (model_dir / "voices-v1.0.bin").write_bytes(b"voices")


@pytest.fixture()
def env(tmp_path: Path) -> dict:
    bin_dir = tmp_path / "bin"
    make_tools(bin_dir)
    return {
        "PATH": str(bin_dir),
        "HOME": str(tmp_path / "home"),
        "QUIRK_STUDIO": str(tmp_path / "studio"),
        "QUIRK_VIDEO_CACHE": str(tmp_path / "cache"),
        "QUIRK_PLATFORM": "darwin",
        "QUIRK_FFMPEG": str(bin_dir / "ffmpeg"),
        "QUIRK_BLENDER": str(tmp_path / "no-blender"),
        "FAKE_LOG": str(tmp_path / "tools.log"),
    }


def bin_dir(env: dict) -> Path:
    return Path(env["PATH"])


def run_doctor(*args: object, env: dict) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(DOCTOR_PY), *map(str, args)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    out = proc.stdout.strip()
    assert out, f"no stdout (rc={proc.returncode}): {proc.stderr}"
    return proc.returncode, json.loads(out)


def tool(result: dict, name: str) -> dict:
    matches = [t for t in result["tools"] if t["name"] == name]
    assert matches, f"{name} not in {[t['name'] for t in result['tools']]}"
    return matches[0]


def tool_calls(env: dict) -> list:
    log = Path(env["FAKE_LOG"])
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines()]


@pytest.fixture()
def model_server(tmp_path: Path):
    root = tmp_path / "served"
    root.mkdir()
    (root / "kokoro-v1.0.onnx").write_bytes(b"onnx-bytes" * 100)
    (root / "voices-v1.0.bin").write_bytes(b"voice-bytes" * 10)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None  # type: ignore[attr-defined]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/", root
    server.shutdown()
    server.server_close()


def test_check_all_good_reports_ok(env):
    code, out = run_doctor("check", env=env)
    assert code == 0
    assert out["ok"] is True
    names = [t["name"] for t in out["tools"]]
    assert {"node", "pnpm", "ffmpeg", "ffprobe", "ffmpeg_subtitles"} <= set(names)
    assert "platform" not in names
    for t in out["tools"]:
        assert set(t) >= {"name", "ok", "version", "fix"}
        assert t["ok"] is True
    assert tool(out, "node")["version"] == "22.3.0"


def test_check_node_below_22_is_not_ok_but_exits_zero(env):
    write_stub(bin_dir(env) / "node", version_body("v20.11.0"))
    code, out = run_doctor("check", env=env)
    assert code == 0
    assert out["ok"] is False
    assert tool(out, "node")["ok"] is False
    assert tool(out, "node")["fix"]
    assert tool(out, "pnpm")["ok"] is True


def test_check_missing_pnpm_has_a_fix(env):
    (bin_dir(env) / "pnpm").unlink()
    code, out = run_doctor("check", env=env)
    assert code == 0 and out["ok"] is False
    assert "brew install" in tool(out, "pnpm")["fix"]


def test_check_ffmpeg_without_subtitles_filter_points_at_ffmpeg_full(env):
    write_stub(bin_dir(env) / "ffmpeg", ffmpeg_body(FILTERS_WITHOUT))
    code, out = run_doctor("check", env=env)
    assert code == 0 and out["ok"] is False
    sub = tool(out, "ffmpeg_subtitles")
    assert sub["ok"] is False
    assert sub["fix"] == "brew install ffmpeg-full"
    assert tool(out, "ffmpeg")["ok"] is True


def test_check_non_darwin_adds_unsupported_platform_entry(env):
    env["QUIRK_PLATFORM"] = "linux"
    code, out = run_doctor("check", env=env)
    assert code == 0
    assert out["ok"] is False
    plat = tool(out, "platform")
    assert plat["ok"] is False
    assert "unsupported platform; making-videos runs on macOS only" in plat["fix"] + plat["version"]


def test_check_unknown_need_is_a_usage_error(env):
    code, out = run_doctor("check", "--need", "narration,bogus", env=env)
    assert code == 2
    assert "bogus" in out["error"]


def test_narration_need_with_healthy_venv_and_models(env, tmp_path):
    cache = tmp_path / "cache"
    make_venv(cache)
    make_models(cache)
    code, out = run_doctor("check", "--need", "narration", env=env)
    assert code == 0
    assert out["ok"] is True
    assert tool(out, "narration_venv")["version"].startswith("3.12")
    assert tool(out, "kokoro_models")["ok"] is True


def test_narration_need_without_venv_points_at_install(env):
    code, out = run_doctor("check", "--need", "narration", env=env)
    assert code == 0 and out["ok"] is False
    venv = tool(out, "narration_venv")
    assert venv["ok"] is False
    assert venv["fix"] == "doctor.py install --what tts --yes"
    assert tool(out, "kokoro_models")["fix"] == "doctor.py install --what tts --yes"


def test_narration_need_rejects_wrong_python_and_missing_modules(env, tmp_path):
    cache = tmp_path / "cache"
    make_models(cache)
    make_venv(cache, version="3.13.0")
    _, out = run_doctor("check", "--need", "narration", env=env)
    assert tool(out, "narration_venv")["ok"] is False
    make_venv(cache, version="3.12.4", missing="faster_whisper")
    _, out = run_doctor("check", "--need", "narration", env=env)
    venv = tool(out, "narration_venv")
    assert venv["ok"] is False
    assert "faster_whisper" in venv["fix"] or "faster_whisper" in venv["version"]


def test_narration_probe_is_one_subprocess_with_ort_telemetry_off(env, tmp_path):
    cache = tmp_path / "cache"
    make_models(cache)
    write_stub(
        cache / "venv" / "bin" / "python",
        "print('3.11.9')\nprint('')\n"
        "open(os.environ['FAKE_LOG'] + '.ort', 'a').write(os.environ.get('ORT_DISABLE_TELEMETRY', ''))\n",
    )
    run_doctor("check", "--need", "narration", env=env)
    assert len([c for c in tool_calls(env) if c[0] == "python"]) == 1
    assert Path(env["FAKE_LOG"] + ".ort").read_text() == "1"


@pytest.mark.parametrize(
    "banner,ok,version",
    [("Blender 4.2.3 LTS", True, "4.2.3"), ("Blender 5.0.1", True, "5.0.1"), ("Blender 4.1.1", False, "4.1.1")],
)
def test_3d_need_parses_blender_version(env, tmp_path, banner, ok, version):
    stub = write_stub(tmp_path / "apps" / "Blender", version_body(banner))
    env["QUIRK_BLENDER"] = str(stub)
    code, out = run_doctor("check", "--need", "3d", env=env)
    assert code == 0
    blender = tool(out, "blender")
    assert blender["ok"] is ok
    assert blender["version"] == version
    assert out["ok"] is ok
    if not ok:
        assert "blender.org" in blender["fix"]


def test_3d_need_finds_blender_on_path(env):
    write_stub(bin_dir(env) / "blender", version_body("Blender 4.4.0"))
    del env["QUIRK_BLENDER"]
    _, out = run_doctor("check", "--need", "3d", env=env)
    assert tool(out, "blender")["ok"] is True


def test_3d_need_missing_blender_names_the_download(env):
    _, out = run_doctor("check", "--need", "3d", env=env)
    blender = tool(out, "blender")
    assert blender["ok"] is False
    assert "blender.org" in blender["fix"]


def test_record_need_checks_the_pinned_playwright_version(env, tmp_path):
    _, out = run_doctor("check", "--need", "record", env=env)
    pw = tool(out, "playwright")
    assert pw["ok"] is False
    assert pw["fix"] == "doctor.py install --what playwright --yes"

    pkg = tmp_path / "cache" / "node" / "node_modules" / "playwright" / "package.json"
    pkg.parent.mkdir(parents=True)
    pkg.write_text(json.dumps({"version": "1.0.0"}))
    _, out = run_doctor("check", "--need", "record", env=env)
    assert tool(out, "playwright")["ok"] is False

    pkg.write_text(json.dumps({"version": common.PLAYWRIGHT_VERSION}))
    _, out = run_doctor("check", "--need", "record", env=env)
    assert tool(out, "playwright")["ok"] is True
    assert out["ok"] is True


def test_needs_not_requested_are_not_checked(env):
    _, out = run_doctor("check", env=env)
    names = {t["name"] for t in out["tools"]}
    assert not names & {"narration_venv", "kokoro_models", "blender", "playwright"}


def test_install_refuses_without_yes(env, model_server, tmp_path):
    env["QUIRK_KOKORO_BASE_URL"] = model_server[0]
    write_stub(bin_dir(env) / "uv", "")
    for what in ("tts", "playwright"):
        code, out = run_doctor("install", "--what", what, env=env)
        assert code == 2
        assert "--yes" in out["error"]
    assert tool_calls(env) == []
    assert not (tmp_path / "cache").exists()


def test_install_tts_without_uv_exits_3_with_fix(env):
    code, out = run_doctor("install", "--what", "tts", "--yes", env=env)
    assert code == 3
    assert "brew install uv" in json.dumps(out)


def test_install_tts_runs_uv_then_downloads_models(env, model_server, tmp_path):
    base_url, _ = model_server
    env["QUIRK_KOKORO_BASE_URL"] = base_url
    write_stub(bin_dir(env) / "uv", "")
    code, out = run_doctor("install", "--what", "tts", "--yes", env=env)
    assert code == 0, out
    cache = tmp_path / "cache"
    venv = cache / "venv"
    assert tool_calls(env) == [
        ["uv", "venv", "--python", "3.12", str(venv)],
        [
            "uv", "pip", "install", "--python", str(venv / "bin" / "python"),
            "kokoro-onnx==0.6.1", "soundfile", "faster-whisper", "numpy",
        ],
    ]
    models = cache / "models" / "kokoro"
    assert (models / "kokoro-v1.0.onnx").read_bytes() == b"onnx-bytes" * 100
    assert (models / "voices-v1.0.bin").read_bytes() == b"voice-bytes" * 10
    assert not list(models.glob("*.part")) and not list(models.glob("*.tmp"))
    assert out["installed"]
    assert out["path"] == str(venv)


def test_install_tts_download_failure_leaves_no_partial_file(env, model_server, tmp_path):
    base_url, root = model_server
    (root / "voices-v1.0.bin").unlink()
    env["QUIRK_KOKORO_BASE_URL"] = base_url
    write_stub(bin_dir(env) / "uv", "")
    code, out = run_doctor("install", "--what", "tts", "--yes", env=env)
    assert code == 1
    assert "voices-v1.0.bin" in out["error"]
    models = tmp_path / "cache" / "models" / "kokoro"
    assert not (models / "voices-v1.0.bin").exists()
    assert not [p for p in models.iterdir() if p.name.startswith("voices")]


def test_install_tts_child_failure_reports_command_and_stderr_tail(env):
    write_stub(
        bin_dir(env) / "uv",
        "sys.stderr.write('line1\\nboom: no network\\n')\nsys.exit(2)\n",
    )
    code, out = run_doctor("install", "--what", "tts", "--yes", env=env)
    assert code == 1
    blob = json.dumps(out)
    assert "uv venv" in blob
    assert "boom: no network" in blob


def test_install_playwright_runs_pnpm_add_then_install_chromium(env, tmp_path):
    write_stub(bin_dir(env) / "pnpm", "")
    code, out = run_doctor("install", "--what", "playwright", "--yes", env=env)
    assert code == 0, out
    node_dir = tmp_path / "cache" / "node"
    assert tool_calls(env) == [
        ["pnpm", "add", "--dir", str(node_dir), f"playwright@{common.PLAYWRIGHT_VERSION}"],
        ["pnpm", "--dir", str(node_dir), "exec", "playwright", "install", "chromium"],
    ]
    assert out["path"] == str(node_dir)


def test_install_playwright_without_pnpm_exits_3(env):
    (bin_dir(env) / "pnpm").unlink()
    code, out = run_doctor("install", "--what", "playwright", "--yes", env=env)
    assert code == 3
    assert "pnpm" in json.dumps(out)


def test_install_children_do_not_receive_cloud_keys(env, tmp_path):
    write_stub(
        bin_dir(env) / "pnpm",
        "open(os.environ['FAKE_LOG'] + '.env', 'w').write(json.dumps(dict(os.environ)))\n",
    )
    env["GEMINI_API_KEY"] = "secret"
    env["OPENAI_API_KEY"] = "secret"
    code, _ = run_doctor("install", "--what", "playwright", "--yes", env=env)
    assert code == 0
    child_env = json.loads(Path(env["FAKE_LOG"] + ".env").read_text())
    assert "GEMINI_API_KEY" not in child_env and "OPENAI_API_KEY" not in child_env


def test_unknown_install_target_is_a_usage_error(env):
    code, out = run_doctor("install", "--what", "blender", "--yes", env=env)
    assert code == 2
    assert "error" in out


@pytest.fixture()
def tls_model_server(tmp_path: Path):
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("openssl CLI not available")
    cert, key = tmp_path / "server.pem", tmp_path / "server.key"
    subprocess.run(
        [
            openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
            "-subj", "/CN=127.0.0.1", "-keyout", str(key), "-out", str(cert),
            "-addext", "subjectAltName=IP:127.0.0.1",
            "-addext", "basicConstraints=critical,CA:TRUE",
        ],
        check=True,
        capture_output=True,
    )
    root = tmp_path / "served"
    root.mkdir()
    (root / "kokoro-v1.0.onnx").write_bytes(b"onnx-bytes" * 100)
    (root / "voices-v1.0.bin").write_bytes(b"voice-bytes" * 10)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None  # type: ignore[attr-defined]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(str(cert), str(key))
    server.socket = server_ctx.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"https://127.0.0.1:{server.server_address[1]}/", cert
    server.shutdown()
    server.server_close()


def test_install_tts_downloads_over_https_trusting_ssl_cert_file(env, tls_model_server, tmp_path):
    base_url, cert = tls_model_server
    env["QUIRK_KOKORO_BASE_URL"] = base_url
    env["SSL_CERT_FILE"] = str(cert)
    write_stub(bin_dir(env) / "uv", "")
    code, out = run_doctor("install", "--what", "tts", "--yes", env=env)
    assert code == 0, out
    models = tmp_path / "cache" / "models" / "kokoro"
    assert (models / "kokoro-v1.0.onnx").read_bytes() == b"onnx-bytes" * 100


def test_install_tts_refuses_an_untrusted_https_certificate(env, tls_model_server, tmp_path):
    base_url, _ = tls_model_server
    env["QUIRK_KOKORO_BASE_URL"] = base_url
    env["QUIRK_CA_FALLBACKS"] = str(tmp_path / "missing.pem")
    write_stub(bin_dir(env) / "uv", "")
    code, out = run_doctor("install", "--what", "tts", "--yes", env=env)
    assert code == 1
    assert "CERTIFICATE_VERIFY_FAILED" in out["error"]
    assert not list((tmp_path / "cache" / "models" / "kokoro").glob("kokoro*"))
