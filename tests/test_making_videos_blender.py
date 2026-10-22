"""Tests for the making-videos headless Blender runner and its in-Blender guard."""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import stat
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "making-videos" / "scripts"
RENDER_PY = SCRIPTS / "blender_render.py"
GUARD_PY = SCRIPTS / "bl_guard.py"


def _tiny_png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    raw = zlib.compress(b"\x00\x00\x00\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


TINY_PNG_B64 = base64.b64encode(_tiny_png()).decode()

FAKE_BLENDER = f'''#!{sys.executable}
import base64, json, os, sys
from pathlib import Path

argv = sys.argv[1:]
with open(os.environ["FAKE_BLENDER_LOG"], "a") as fh:
    fh.write(json.dumps(argv) + "\\n")
with open(os.environ["FAKE_BLENDER_LOG"] + ".env", "a") as fh:
    fh.write(json.dumps(sorted(os.environ)) + "\\n")
if os.environ.get("FAKE_BLENDER_EXIT"):
    sys.stderr.write("Traceback: boom from fake blender\\n")
    raise SystemExit(int(os.environ["FAKE_BLENDER_EXIT"]))
tail = argv[argv.index("--") + 1:]
out = Path(tail[tail.index("--out") + 1])
a, b = (int(x) for x in tail[tail.index("--frames") + 1].split("-"))
guard = {{"default_scene": False, "view_transform": "Standard", "text_objects": [],
         "mirrored_frames": [], "edge_on_frames": [], "frames_rendered": b - a + 1}}
override = json.loads(os.environ.get("FAKE_BLENDER_GUARD", "{{}}"))
for key, value in override.items():
    if key in ("mirrored_frames", "edge_on_frames"):
        value = [f for f in value if a <= f <= b]
    guard[key] = value
if guard["default_scene"] or guard["mirrored_frames"]:
    guard["frames_rendered"] = 0
elif not os.environ.get("FAKE_BLENDER_NO_PNGS"):
    out.mkdir(parents=True, exist_ok=True)
    png = base64.b64decode("{TINY_PNG_B64}")
    for f in range(a, b + 1):
        (out / ("f_%04d.png" % f)).write_bytes(png)
if not os.environ.get("FAKE_BLENDER_NO_GUARD"):
    out.mkdir(parents=True, exist_ok=True)
    (out / "guard.json").write_text(json.dumps(guard))
'''

FAKE_FFMPEG = f'''#!{sys.executable}
import json, os, sys
with open(os.environ["FAKE_FFMPEG_LOG"], "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
with open(os.environ["FAKE_FFMPEG_LOG"] + ".env", "a") as fh:
    fh.write(json.dumps(sorted(os.environ)) + "\\n")
if os.environ.get("FAKE_FFMPEG_EXIT"):
    sys.stderr.write("ffmpeg: encode exploded\\n")
    raise SystemExit(int(os.environ["FAKE_FFMPEG_EXIT"]))
open(sys.argv[-1], "wb").write(b"fake-clip")
'''


def _write_exe(path: Path, source: str) -> Path:
    path.write_text(source)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture()
def rig(tmp_path: Path) -> dict:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    blender = _write_exe(bin_dir / "blender", FAKE_BLENDER)
    _write_exe(bin_dir / "ffmpeg", FAKE_FFMPEG)
    blend = tmp_path / "scene.blend"
    blend.write_bytes(b"BLENDER")
    script = tmp_path / "build_scene.py"
    script.write_text("# author script\n")
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "QUIRK_STUDIO": str(tmp_path / "studio"),
        "QUIRK_VIDEO_CACHE": str(tmp_path / "cache"),
        "QUIRK_BLENDER": str(blender),
        "FAKE_BLENDER_LOG": str(tmp_path / "blender.log"),
        "FAKE_FFMPEG_LOG": str(tmp_path / "ffmpeg.log"),
    }
    return {
        "env": env,
        "blend": blend,
        "script": script,
        "out": tmp_path / "cache" / "out",
        "blender": blender,
        "bin": bin_dir,
        "blender_log": tmp_path / "blender.log",
        "ffmpeg_log": tmp_path / "ffmpeg.log",
    }


def run_render(rig: dict, *extra: object, env: dict = None, blend: object = None, script: object = None):
    argv = [
        sys.executable,
        str(RENDER_PY),
        "--blend",
        str(rig["blend"] if blend is None else blend),
        "--script",
        str(rig["script"] if script is None else script),
        "--out",
        str(rig["out"]),
        *map(str, extra),
    ]
    proc = subprocess.run(
        argv, capture_output=True, text=True, env=env if env is not None else rig["env"], timeout=60
    )
    out = proc.stdout.strip()
    assert out, f"no stdout (rc={proc.returncode}): {proc.stderr}"
    assert len(out.splitlines()) == 1, out
    return proc.returncode, json.loads(out)


def log_lines(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def with_env(rig: dict, **extra: str) -> dict:
    return {**rig["env"], **extra}


def test_argv_order_and_trailing_args(rig):
    rc, data = run_render(rig, "--frames", "1-10")
    assert rc == 0, data
    (argv,) = log_lines(rig["blender_log"])
    out = str(rig["out"].resolve())
    assert argv == [
        "-b",
        str(rig["blend"].resolve()),
        "--python-exit-code",
        "1",
        "--python",
        str(rig["script"].resolve()),
        "--python",
        str(GUARD_PY),
        "--",
        "--out",
        out,
        "--frames",
        "1-10",
    ]
    assert argv.index(str(rig["blend"].resolve())) < argv.index("--python")
    for banned in ("-o", "-a", "-s", "-e", "-f"):
        assert banned not in argv


def test_mp4_encode_and_json(rig):
    rc, data = run_render(rig, "--frames", "1-10")
    assert rc == 0, data
    assert data["frames"] == 10
    assert data["clip"].endswith(".mp4")
    assert Path(data["clip"]).is_file()
    assert data["guard"]["default_scene"] is False
    assert data["guard"]["mirrored_frames"] == []
    assert data["warnings"] == []
    (ffmpeg,) = log_lines(rig["ffmpeg_log"])
    joined = " ".join(ffmpeg)
    for token in ("-c:v libx264", "-pix_fmt yuv420p", "-crf 14", "-movflags +faststart", "-framerate 30"):
        assert token in joined
    assert "-g 30 -keyint_min 30" in joined
    assert "f_%04d.png" in joined
    assert ffmpeg[-1] == data["clip"]
    assert (rig["out"] / "guard.json").is_file()
    assert (rig["out"] / "f_0001.png").is_file()


def test_fps_flag_and_env(rig):
    rc, _ = run_render(rig, "--frames", "1-3", "--fps", "24")
    assert rc == 0
    joined = " ".join(log_lines(rig["ffmpeg_log"])[0])
    assert "-framerate 24" in joined and "-g 24 -keyint_min 24" in joined
    rig["ffmpeg_log"].unlink()
    rc, _ = run_render(rig, "--frames", "1-3", env=with_env(rig, QUIRK_VIDEO_FPS="60"))
    assert rc == 0
    assert "-framerate 60" in " ".join(log_lines(rig["ffmpeg_log"])[0])


def test_arguments_after_a_double_dash_reach_the_scene_script(rig):
    rc, data = run_render(rig, "--frames", "1-4", "--alpha", "--", "--font", "/x/Outfit-SemiBold.ttf", "--accent", "#1e7a52")
    assert rc == 0, data
    (argv,) = log_lines(rig["blender_log"])
    out = str(rig["out"].resolve())
    assert argv[argv.index("--") :] == [
        "--", "--out", out, "--frames", "1-4", "--alpha", "--font", "/x/Outfit-SemiBold.ttf", "--accent", "#1e7a52",
    ]


def test_no_double_dash_adds_nothing_to_the_scene_script_argv(rig):
    rc, _ = run_render(rig, "--frames", "1-4")
    assert rc == 0
    (argv,) = log_lines(rig["blender_log"])
    assert argv[-2:] == ["--frames", "1-4"]


def test_alpha_keeps_pngs_and_writes_prores(rig):
    rc, data = run_render(rig, "--frames", "1-4", "--alpha")
    assert rc == 0, data
    assert data["clip"].endswith(".mov")
    (argv,) = log_lines(rig["blender_log"])
    assert argv[-1] == "--alpha"
    (ffmpeg,) = log_lines(rig["ffmpeg_log"])
    joined = " ".join(ffmpeg)
    for token in ("-c:v prores_ks", "-profile:v 4444", "-pix_fmt yuva444p10le"):
        assert token in joined
    assert "libx264" not in joined and "-keyint_min" not in joined
    assert len(list(rig["out"].glob("f_*.png"))) == 4


def test_missing_blend_exits_1_without_running_blender(rig):
    rc, data = run_render(rig, "--frames", "1-3", blend=rig["blend"].parent / "nope.blend")
    assert rc == 1
    assert "nope.blend" in data["error"]
    assert log_lines(rig["blender_log"]) == []


def test_missing_script_exits_1(rig):
    rc, data = run_render(rig, "--frames", "1-3", script=rig["script"].parent / "nope.py")
    assert rc == 1
    assert "nope.py" in data["error"]
    assert log_lines(rig["blender_log"]) == []


def test_missing_blender_exits_3(rig):
    env = with_env(rig, QUIRK_BLENDER=str(rig["bin"] / "does-not-exist"))
    rc, data = run_render(rig, "--frames", "1-3", env=env)
    assert rc == 3
    assert "blender.org" in json.dumps(data)


def test_blender_found_on_path(rig):
    env = dict(rig["env"])
    del env["QUIRK_BLENDER"]
    rc, data = run_render(rig, "--frames", "1-2", env=env)
    assert rc == 0, data
    assert len(log_lines(rig["blender_log"])) == 1


def test_blender_nonzero_exit_reports_stderr_tail(rig):
    rc, data = run_render(rig, "--frames", "1-3", env=with_env(rig, FAKE_BLENDER_EXIT="1"))
    assert rc == 1
    assert "boom from fake blender" in data["error"]
    assert log_lines(rig["ffmpeg_log"]) == []


def test_guard_json_missing_exits_1(rig):
    rc, data = run_render(rig, "--frames", "1-3", env=with_env(rig, FAKE_BLENDER_NO_GUARD="1"))
    assert rc == 1
    assert "guard.json" in data["error"]


def test_missing_frames_on_disk_exits_1(rig):
    rc, data = run_render(rig, "--frames", "1-3", env=with_env(rig, FAKE_BLENDER_NO_PNGS="1"))
    assert rc == 1
    assert "f_0001.png" in data["error"]
    assert log_lines(rig["ffmpeg_log"]) == []


def test_default_scene_fails(rig):
    env = with_env(rig, FAKE_BLENDER_GUARD=json.dumps({"default_scene": True}))
    rc, data = run_render(rig, "--frames", "1-3", env=env)
    assert rc == 1
    assert data["guard"]["default_scene"] is True
    assert "default scene" in data["error"].lower()
    assert log_lines(rig["ffmpeg_log"]) == []


def test_mirrored_text_fails(rig):
    env = with_env(rig, FAKE_BLENDER_GUARD=json.dumps({"mirrored_frames": [2, 3], "text_objects": ["Title"]}))
    rc, data = run_render(rig, "--frames", "1-5", env=env)
    assert rc == 1
    assert data["guard"]["mirrored_frames"] == [2, 3]
    assert "mirrored" in data["error"].lower()
    assert log_lines(rig["ffmpeg_log"]) == []


def test_edge_on_and_view_transform_are_warnings_only(rig):
    env = with_env(
        rig, FAKE_BLENDER_GUARD=json.dumps({"edge_on_frames": [4], "view_transform": "AgX"})
    )
    rc, data = run_render(rig, "--frames", "1-5", env=env)
    assert rc == 0, data
    text = " ".join(data["warnings"])
    assert "edge-on" in text and "4" in text
    assert "AgX" in text and "Standard" in text
    assert data["guard"]["edge_on_frames"] == [4]


def test_chunking_runs_one_process_per_range_and_merges(rig):
    env = with_env(
        rig,
        FAKE_BLENDER_GUARD=json.dumps({"edge_on_frames": [2, 9], "text_objects": ["T"]}),
    )
    rc, data = run_render(rig, "--frames", "1-10", "--chunk", "4", env=env)
    assert rc == 0, data
    calls = log_lines(rig["blender_log"])
    ranges = [c[c.index("--frames") + 1] for c in calls]
    assert ranges == ["1-4", "5-8", "9-10"]
    assert data["frames"] == 10
    assert data["guard"]["frames_rendered"] == 10
    assert data["guard"]["edge_on_frames"] == [2, 9]
    assert data["guard"]["text_objects"] == ["T"]
    merged = json.loads((rig["out"] / "guard.json").read_text())
    assert merged["frames_rendered"] == 10
    (ffmpeg,) = log_lines(rig["ffmpeg_log"])
    assert "-start_number 1" in " ".join(ffmpeg)


def test_chunking_merges_mirrored_and_fails(rig):
    env = with_env(rig, FAKE_BLENDER_GUARD=json.dumps({"mirrored_frames": [6]}))
    rc, data = run_render(rig, "--frames", "1-8", "--chunk", "4", env=env)
    assert rc == 1
    assert data["guard"]["mirrored_frames"] == [6]


def test_usage_errors_exit_2(rig):
    for bad in (["--frames", "5-1"], ["--frames", "abc"], ["--frames", "1-3", "--chunk", "0"], []):
        rc, data = run_render(rig, *bad)
        assert rc == 2, (bad, data)
        assert "error" in data


@pytest.fixture(scope="module")
def guard():
    spec = importlib.util.spec_from_file_location("mv_bl_guard_under_test", GUARD_PY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def test_guard_loads_without_bpy(guard):
    assert guard.bpy is None


def test_world_normal_identity_and_rotated(guard):
    assert guard.world_normal(IDENTITY) == (0.0, 0.0, 1.0)
    flip_x = ((1, 0, 0), (0, -1, 0), (0, 0, -1))
    assert guard.world_normal(flip_x) == (0.0, 0.0, -1.0)
    scaled = ((3, 0, 0), (0, 3, 0), (0, 0, 3))
    assert guard.world_normal(scaled) == (0.0, 0.0, 1.0)


def test_classify_facing_toward_camera(guard):
    assert guard.classify_facing((0, 0, 1), (0, 0, 0), (0, 0, 5)) == (False, False)


def test_classify_facing_mirrored_when_facing_away(guard):
    assert guard.classify_facing((0, 0, 1), (0, 0, 0), (0, 0, -5)) == (True, False)


def test_classify_facing_edge_on(guard):
    assert guard.classify_facing((0, 0, 1), (0, 0, 0), (5, 0, 0.1)) == (False, True)
    mirrored, edge = guard.classify_facing((0, 0, 1), (0, 0, 0), (5, 0, -0.1))
    assert mirrored and edge


def test_classify_facing_float_noise_at_exact_edge_is_not_mirrored(guard):
    assert guard.classify_facing((0, 0, 1), (0, 0, 0), (5, 0, -1e-9)) == (False, True)


def test_classify_facing_oblique_is_fine(guard):
    assert guard.classify_facing((0, 0, 1), (0, 0, 0), (3, 0, 3)) == (False, False)


def test_classify_facing_camera_at_object_is_edge_on(guard):
    assert guard.classify_facing((0, 0, 1), (1, 1, 1), (1, 1, 1)) == (False, True)


def _objs(*pairs):
    return [{"name": n, "type": t} for n, t in pairs]


def test_default_scene_startup_scene(guard):
    assert guard.is_default_scene(_objs(("Cube", "MESH"), ("Camera", "CAMERA"), ("Light", "LIGHT")))


def test_default_scene_only_camera_and_light_or_empty(guard):
    assert guard.is_default_scene(_objs(("Camera", "CAMERA"), ("Light", "LIGHT")))
    assert guard.is_default_scene([])


def test_default_scene_false_for_real_content(guard):
    base = [("Camera", "CAMERA"), ("Light", "LIGHT")]
    assert not guard.is_default_scene(_objs(("Title", "FONT"), *base))
    assert not guard.is_default_scene(_objs(("Cube", "MESH"), ("Sphere", "MESH"), *base))
    assert not guard.is_default_scene(_objs(("Cube.001", "MESH"), *base))
    assert not guard.is_default_scene(_objs(("Cube", "MESH"), ("Rig", "EMPTY"), *base))


class _Matrix:
    def __init__(self, rows, translation):
        self._rows, self.translation = rows, translation

    def to_3x3(self):
        return self._rows


class _Coll:
    def __init__(self, name, hide_render=False):
        self.name, self.hide_render = name, hide_render


class _LayerColl:
    def __init__(self, collection, children=(), exclude=False):
        self.collection, self.children, self.exclude = collection, list(children), exclude


class _Text:
    def __init__(self, name, rows, collections=(), hidden_on=()):
        self.type, self.name = "FONT", name
        self.matrix_world = _Matrix(rows, (0, 0, 0))
        self.users_collection = list(collections)
        self.hidden_on = set(hidden_on)
        self.hide_render = False


class _Scene:
    def __init__(self, texts, layer_collection=None):
        self.objects = texts
        self.camera = type("Cam", (), {"matrix_world": _Matrix(IDENTITY, (0, 0, 5))})()
        self.view_layers = [type("VL", (), {"layer_collection": layer_collection})()] if layer_collection else []
        self.collections = []

    def frame_set(self, frame):
        for t in self.objects:
            t.hide_render = frame in t.hidden_on
        for c in self.collections:
            c.hide_render = frame in getattr(c, "hidden_on", ())


FLIPPED = ((1, 0, 0), (0, 1, 0), (0, 0, -1))


def test_render_visible(guard):
    assert guard.render_visible(False, [])
    assert not guard.render_visible(True, [True])
    assert not guard.render_visible(False, [False, False])
    assert guard.render_visible(False, [False, True])


def test_text_hidden_then_visible_and_mirrored_is_caught(guard):
    title = _Text("BackwardsTitle", FLIPPED, hidden_on={1, 2})
    result = guard._inspect_text(_Scene([title]), 1, 3)
    assert result == (["BackwardsTitle"], [3], [])


def test_text_hidden_for_whole_range_is_ignored(guard):
    title = _Text("Hidden", FLIPPED, hidden_on={1, 2, 3})
    assert guard._inspect_text(_Scene([title]), 1, 3) == ([], [], [])


def test_text_visible_only_before_it_is_mirrored_is_not_flagged_later(guard):
    title = _Text("Gone", FLIPPED, hidden_on={2, 3})
    assert guard._inspect_text(_Scene([title]), 1, 3) == (["Gone"], [1], [])


def test_text_in_hidden_collection_is_ignored(guard):
    sub = _Coll("Sub", hide_render=True)
    root = _Coll("Scene Collection")
    layer = _LayerColl(root, [_LayerColl(sub)])
    title = _Text("Title", FLIPPED, collections=[sub])
    assert guard._inspect_text(_Scene([title], layer), 1, 2) == ([], [], [])


def test_text_in_excluded_collection_is_ignored(guard):
    sub = _Coll("Sub")
    layer = _LayerColl(_Coll("Scene Collection"), [_LayerColl(sub, exclude=True)])
    title = _Text("Title", FLIPPED, collections=[sub])
    assert guard._inspect_text(_Scene([title], layer), 1, 2) == ([], [], [])


def test_text_inherits_hidden_ancestor_collection(guard):
    parent, child = _Coll("Parent", hide_render=True), _Coll("Child")
    layer = _LayerColl(_Coll("Scene Collection"), [_LayerColl(parent, [_LayerColl(child)])])
    title = _Text("Title", FLIPPED, collections=[child])
    assert guard._inspect_text(_Scene([title], layer), 1, 2) == ([], [], [])


def test_text_in_collection_that_becomes_visible_mid_range_is_caught(guard):
    sub = _Coll("Sub", hide_render=True)
    sub.hidden_on = {1, 2}
    layer = _LayerColl(_Coll("Scene Collection"), [_LayerColl(sub)])
    title = _Text("Title", FLIPPED, collections=[sub])
    scene = _Scene([title], layer)
    scene.collections = [sub]
    assert guard._inspect_text(scene, 1, 3) == (["Title"], [3], [])


def test_text_visible_via_any_of_its_collections(guard):
    hidden, shown = _Coll("Hidden", hide_render=True), _Coll("Shown")
    layer = _LayerColl(_Coll("Scene Collection"), [_LayerColl(hidden), _LayerColl(shown)])
    title = _Text("Title", FLIPPED, collections=[hidden, shown])
    assert guard._inspect_text(_Scene([title], layer), 1, 1) == (["Title"], [1], [])


def test_visible_text_without_camera_raises(guard):
    scene = _Scene([_Text("Title", IDENTITY)])
    scene.camera = None
    with pytest.raises(RuntimeError):
        guard._inspect_text(scene, 1, 1)


def test_parse_frames(guard):
    assert guard.parse_frames("3-12") == (3, 12)
    with pytest.raises(ValueError):
        guard.parse_frames("12-3")
    with pytest.raises(ValueError):
        guard.parse_frames("x")


def test_guard_args_ignore_unknown_flags(guard):
    args = guard.parse_args(["--out", "/o", "--frames", "1-5", "--alpha", "--mine", "1"])
    assert args.out == "/o" and args.frames == "1-5" and args.alpha is True


def test_runner_finds_mac_app_fallback(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("mv_blender_render_under_test", RENDER_PY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    app = tmp_path / "Blender"
    _write_exe(app, "#!/bin/sh\n")
    monkeypatch.setattr(mod, "MAC_APP_BLENDER", str(app))
    assert mod.find_blender({"PATH": str(tmp_path / "empty")}) == str(app)
    monkeypatch.setattr(mod, "MAC_APP_BLENDER", str(tmp_path / "absent"))
    assert mod.find_blender({"PATH": str(tmp_path / "empty")}) is None
    assert mod.find_blender({"QUIRK_BLENDER": str(app), "PATH": ""}) == str(app)
    assert mod.find_blender({"QUIRK_BLENDER": str(tmp_path / "absent"), "PATH": ""}) is None


def test_children_get_no_scrubbed_env(rig):
    secrets = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ELEVENLABS_API_KEY", "OPENAI_API_KEY",
               "PEXELS_API_KEY", "PIXABAY_API_KEY", "FREESOUND_API_KEY")
    env = with_env(rig, **{k: "dummy" for k in secrets})
    rc, data = run_render(rig, "--frames", "1-2", env=env)
    assert rc == 0, data
    for log in (rig["blender_log"], rig["ffmpeg_log"]):
        (keys,) = log_lines(Path(str(log) + ".env"))
        assert "PATH" in keys
        assert not set(secrets) & set(keys)


def test_out_outside_roots_is_refused_without_touching_disk(rig, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    victim = outside / "f_0001.png"
    victim.write_bytes(b"keep")
    rig["out"] = outside
    rc, data = run_render(rig, "--frames", "1-2")
    assert rc == 1
    assert "--out" in data["error"]
    assert victim.read_bytes() == b"keep"
    assert log_lines(rig["blender_log"]) == []


def test_out_symlink_escaping_roots_is_refused(rig, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "f_0001.png").write_bytes(b"keep")
    (tmp_path / "cache").mkdir()
    link = tmp_path / "cache" / "link"
    link.symlink_to(outside)
    rig["out"] = link
    rc, data = run_render(rig, "--frames", "1-2")
    assert rc == 1
    assert (outside / "f_0001.png").read_bytes() == b"keep"
    assert log_lines(rig["blender_log"]) == []


def test_out_inside_studio_is_allowed_but_not_in_a_version_folder(rig, tmp_path):
    project = tmp_path / "studio" / "videos" / "2026-10-22-demo"
    rig["out"] = project / "renders" / "f1"
    rc, data = run_render(rig, "--frames", "1-2")
    assert rc == 0, data
    for refused in (project / "v1", project / "v3" / "frames"):
        refused.mkdir(parents=True, exist_ok=True)
        (refused / "f_0001.png").write_bytes(b"keep")
        rig["out"] = refused
        rc, data = run_render(rig, "--frames", "1-2")
        assert rc == 1, refused
        assert "version folder" in data["error"]
        assert (refused / "f_0001.png").read_bytes() == b"keep"


def test_shorter_rerun_encodes_only_requested_frames(rig):
    rc, _ = run_render(rig, "--frames", "1-6")
    assert rc == 0
    rig["ffmpeg_log"].unlink()
    rc, data = run_render(rig, "--frames", "1-3")
    assert rc == 0, data
    (ffmpeg,) = log_lines(rig["ffmpeg_log"])
    assert ffmpeg[ffmpeg.index("-frames:v") + 1] == "3"
    assert (rig["out"] / "f_0006.png").is_file()
    assert data["frames"] == 3


def test_alpha_encodes_only_requested_frames(rig):
    rc, _ = run_render(rig, "--frames", "1-6", "--alpha")
    assert rc == 0
    rig["ffmpeg_log"].unlink()
    rc, data = run_render(rig, "--frames", "2-4", "--alpha")
    assert rc == 0, data
    (ffmpeg,) = log_lines(rig["ffmpeg_log"])
    assert ffmpeg[ffmpeg.index("-frames:v") + 1] == "3"
    assert ffmpeg[ffmpeg.index("-start_number") + 1] == "2"
    assert data["frames"] == 3
