"""Tests for the making-videos skill's strict verify script and its media worker."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "making-videos" / "scripts"
VERIFY_PY = SCRIPTS / "verify.py"
WORKER_PY = SCRIPTS / "media_worker.py"
FIX = Path(__file__).resolve().parent / "fixtures" / "making_videos"

REAL_FFMPEG = shutil.which("ffmpeg")
REAL_FFPROBE = shutil.which("ffprobe")
needs_ffmpeg = pytest.mark.skipif(not (REAL_FFMPEG and REAL_FFPROBE), reason="ffmpeg/ffprobe not installed")

FAKE_FFMPEG = """#!/bin/sh
case "$*" in
*ebur128*)
  echo "[Parsed_ebur128_0 @ 0x1] t: 1.0 TARGET:-23 LUFS M: -30 S: -30 I: -30.0 LUFS" >&2
  printf '[Parsed_ebur128_0 @ 0x1] Summary:\\n\\n  Integrated loudness:\\n    I:         %s LUFS\\n' "${FAKE_LUFS:--16.0}" >&2
  printf '    LRA:         0.0 LU\\n\\n  True peak:\\n    Peak:      %s dBFS\\n' "${FAKE_TP:--1.5}" >&2
  ;;
*)
  for last; do :; done
  printf 'fake image' > "$last"
  ;;
esac
"""

FAKE_FFPROBE = """#!/bin/sh
echo '{"streams": [{"avg_frame_rate": "30/1", "r_frame_rate": "30/1", "width": 1920, "height": 1080, "duration": "6.0"}], "format": {"duration": "6.0"}}'
"""

BANDS = ("top", "bottom", "left", "right")
SEEK = "seek=.05,.15,.25,.35,.45,.55,.65,.75,.85,.95,1"


def _load_worker():
    pytest.importorskip("numpy")
    spec = importlib.util.spec_from_file_location("mv_media_worker_under_test", WORKER_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload))
    return path


class Studio:
    """A hermetic studio with one project, one version and a dummy MP4."""

    def __init__(self, tmp_path: Path, *, fake_tools: bool = True, narration: bool = False,
                 cloud_allow=(), scenes: str = "scenes_inline", render_log: str = "render_ok.log",
                 clean_checks: bool = True):
        self.tmp = tmp_path
        self.studio = tmp_path / "studio"
        self.cache = tmp_path / "cache"
        self.project = self.studio / "videos" / "2026-10-22-demo"
        self.vdir = self.project / "v1"
        self.vdir.mkdir(parents=True)
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        write_json(self.project / "brief.json", {
            "slug": "demo", "product": "acme", "title": "Demo", "length_s": 6,
            "aspects": ["16:9"], "narration": narration, "cloud_allow": list(cloud_allow),
            "music": {"source": "none", "path": None}, "created": "2026-10-22",
        })
        write_json(self.studio / "brands" / "acme" / "brand.json", {
            "product": "acme", "confirmed": True, "colors": {"ground": "#f2efe8"},
            "fonts": {"display": {"family": "Outfit", "files": []}, "mono": {"family": "IBM Plex Mono", "files": []}},
            "logo": None, "voice": {"engine": "kokoro", "id": "af_heart"}, "pronunciations": {},
        })
        shutil.copytree(FIX / scenes, self.project / "scenes")
        if render_log:
            shutil.copy(FIX / render_log, self.vdir / "render.log")
        (self.vdir / "demo-16x9.mp4").write_bytes(b"not a real mp4")
        self.checks = []
        if clean_checks:
            for band in BANDS:
                self.checks.append("%s=%s" % (band, FIX / "check_clean.json"))
        if fake_tools:
            self.install_fake_tools()

    def install_fake_tools(self) -> None:
        for name, body in (("ffmpeg", FAKE_FFMPEG), ("ffprobe", FAKE_FFPROBE)):
            path = self.bin / name
            path.write_text(body)
            path.chmod(0o755)

    def env(self, **extra: str) -> dict:
        env = {
            "PATH": "%s:/usr/bin:/bin" % self.bin,
            "HOME": str(self.tmp / "home"),
            "QUIRK_STUDIO": str(self.studio),
            "QUIRK_VIDEO_CACHE": str(self.cache),
        }
        env.update(extra)
        return env

    def run(self, *args: object, check_args=None, env=None, version: str = "v1", project=None) -> "tuple[int, dict]":
        argv = [sys.executable, str(VERIFY_PY), "--project", str(project or self.project)]
        if version:
            argv += ["--version", version]
        for item in self.checks if check_args is None else check_args:
            argv += ["--check-json", str(item)]
        argv += [str(a) for a in args]
        proc = subprocess.run(argv, capture_output=True, text=True, env=env or self.env(), timeout=120)
        out = proc.stdout.strip()
        assert out, "no stdout (rc=%s): %s" % (proc.returncode, proc.stderr)
        assert len(out.splitlines()) == 1, out
        return proc.returncode, json.loads(out)


@pytest.fixture()
def studio(tmp_path: Path) -> Studio:
    return Studio(tmp_path)


@pytest.fixture()
def narrated(tmp_path: Path) -> Studio:
    return Studio(tmp_path, narration=True)


def add_aspect(s: Studio, aspect: str, scenes: str = "scenes_inline", render: bool = True) -> Path:
    """A second MP4 in the version plus its own layout-pass folder."""
    mp4 = s.vdir / ("demo-%s.mp4" % aspect)
    mp4.write_bytes(b"not a real mp4")
    shutil.copytree(FIX / scenes, s.project / ("scenes-%s" % aspect))
    return mp4


def fake_venv(s: Studio, rows) -> None:
    shim = s.cache / "venv" / "bin" / "python"
    shim.parent.mkdir(parents=True)
    shim.write_text("#!/bin/sh\ncat >/dev/null\necho '%s'\n" % json.dumps({"beats": rows}))
    shim.chmod(0o755)


def check_of(result: dict, name: str) -> dict:
    found = [c for c in result["checks"] if c["name"] == name]
    assert len(found) == 1, "check %s in %s" % (name, [c["name"] for c in result["checks"]])
    return found[0]


def test_everything_passes_and_verify_json_is_written(studio):
    code, out = studio.run()
    assert code == 0, out
    assert out["passed"] is True
    assert out["version"] == "v1"
    assert out["mp4"] == "demo-16x9.mp4"
    assert out["attempt"] == 1
    assert out["stop"] is False
    statuses = {c["name"]: c["status"] for c in out["checks"]}
    assert statuses == {
        "fonts": "pass", "render_log": "pass", "contrast": "pass", "title_safe": "pass", "loudness": "skip",
        "sync": "skip", "blender": "skip", "outside_calls": "pass",
    }
    for check in out["checks"]:
        assert set(check) == {"name", "status", "measured", "threshold", "detail"}
    saved = json.loads((studio.vdir / "verify.json").read_text())
    assert saved["version"] == "v1" and saved["passed"] is True
    assert set(saved["runs"]) == {"demo-16x9.mp4"}
    run = saved["runs"]["demo-16x9.mp4"]
    assert set(run) == {"attempts", "attempt", "passed", "stop", "checks", "frames"}
    assert run["passed"] is True and run["attempt"] == 1 and run["stop"] is False
    assert len(run["attempts"]) == 1
    assert set(run["attempts"][0]) == {"n", "ts", "passed"}


def test_a_narrated_video_passes_with_beats_and_sync_run(narrated):
    beats_file(narrated.project / "beats.json")
    fake_venv(narrated, [{"id": "label", "via": "silence", "offset_s": 0.0, "offset_frames": 0.0}])
    write_json(narrated.project / "assets" / "vo.audio.json", audio_doc())
    code, out = narrated.run("--audio-json", "assets/vo.wav=%s" % (narrated.project / "assets" / "vo.audio.json"))
    assert code == 0, out
    statuses = {c["name"]: c["status"] for c in out["checks"]}
    assert statuses["loudness"] == "pass" and statuses["sync"] == "pass"


def test_frames_contact_sheet_and_default_stills(studio):
    code, out = studio.run()
    assert code == 0
    frames = studio.vdir / "frames" / "demo-16x9"
    sheet = Path(out["frames"]["sheet"])
    assert sheet == frames / "sheet.png"
    assert sheet.is_file()
    assert len(out["frames"]["stills"]) == 6
    for still in out["frames"]["stills"]:
        assert Path(still).parent == frames
        assert Path(still).suffix == ".png" and Path(still).is_file()
    assert sorted(p.name for p in frames.iterdir() if p.is_file()).count("sheet.png") == 1
    assert not [p for p in frames.iterdir() if p.name.startswith(".")]


def test_stills_at_given_times(studio):
    code, out = studio.run("--at", "0.5,2,5.5")
    assert code == 0
    assert len(out["frames"]["stills"]) == 3


def test_bad_at_value_is_a_usage_error(studio):
    code, out = studio.run("--at", "abc")
    assert code == 2 and "error" in out


# fonts ------------------------------------------------------------------------------------------

def test_fonts_fail_when_a_stylesheet_link_defines_font_tokens(tmp_path):
    s = Studio(tmp_path, scenes="scenes_linked")
    code, out = s.run()
    fonts = check_of(out, "fonts")
    assert code == 1 and fonts["status"] == "fail"
    assert "tokens.css" in fonts["detail"]
    assert "index.html" in fonts["detail"]


def test_fonts_fail_on_a_font_token_nobody_defines(tmp_path):
    s = Studio(tmp_path, scenes="scenes_undefined")
    code, out = s.run()
    fonts = check_of(out, "fonts")
    assert fonts["status"] == "fail"
    assert "--font-mono" in fonts["detail"]


def test_fonts_pass_when_tokens_are_inlined_in_the_root_page(studio):
    code, out = studio.run()
    fonts = check_of(out, "fonts")
    assert fonts["status"] == "pass"
    assert fonts["measured"]["injected"] == 2 and fonts["measured"]["required"] == 2


def test_fonts_fail_without_a_render_log_and_say_how_to_make_one(tmp_path):
    s = Studio(tmp_path, render_log="")
    code, out = s.run()
    fonts = check_of(out, "fonts")
    assert fonts["status"] == "fail"
    assert "render.log" in fonts["detail"] and "hf.py" in fonts["detail"] and "render" in fonts["detail"]


def test_fonts_fail_when_the_log_lacks_the_injection_line(tmp_path):
    s = Studio(tmp_path, render_log="render_no_injection.log")
    code, out = s.run()
    fonts = check_of(out, "fonts")
    assert fonts["status"] == "fail" and "Injected deterministic" in fonts["detail"]


def test_fonts_fail_when_fewer_families_injected_than_the_brand_has(tmp_path):
    s = Studio(tmp_path, render_log="render_one_family.log")
    code, out = s.run()
    fonts = check_of(out, "fonts")
    assert fonts["status"] == "fail"
    assert fonts["measured"] == {"injected": 1, "required": 2, "unresolved": 0}


def test_fonts_fail_on_a_font_shorthand_that_uses_a_font_token(tmp_path):
    s = Studio(tmp_path, scenes="scenes_shorthand")
    code, out = s.run()
    fonts = check_of(out, "fonts")
    assert code == 1 and fonts["status"] == "fail"
    assert "compositions/a.html:7" in fonts["detail"]
    assert "font-family: longhand" in fonts["detail"]
    assert fonts["detail"].count("font: shorthand") == 1


def test_fonts_ignore_a_font_shorthand_inside_a_comment_or_without_a_token(tmp_path):
    s = Studio(tmp_path)
    page = s.project / "scenes" / "compositions" / "a.html"
    page.write_text(page.read_text() + "<!-- font: 500 72px var(--font-display) -->\n"
                    "<style>.x { font: 500 12px sans-serif; font-family: var(--font-mono); }</style>\n")
    code, out = s.run()
    assert check_of(out, "fonts")["status"] == "pass"


def test_render_log_flag_overrides_the_default_location(tmp_path):
    s = Studio(tmp_path, render_log="")
    code, out = s.run("--render-log", FIX / "render_ok.log")
    assert check_of(out, "fonts")["status"] == "pass"


def test_fonts_scan_every_scenes_folder(tmp_path):
    s = Studio(tmp_path)
    shutil.copytree(FIX / "scenes_undefined", s.project / "scenes-9x16")
    code, out = s.run()
    fonts = check_of(out, "fonts")
    assert fonts["status"] == "fail"
    assert "scenes-9x16" in fonts["detail"] and "--font-mono" in fonts["detail"]


@pytest.mark.parametrize("aspect", ["9x16", "1x1"])
def test_an_aspect_mp4_requires_its_scenes_folder(tmp_path, aspect):
    s = Studio(tmp_path)
    mp4 = s.vdir / ("demo-%s.mp4" % aspect)
    mp4.write_bytes(b"x")
    code, out = s.run("--mp4", mp4)
    fonts = check_of(out, "fonts")
    assert code == 1 and fonts["status"] == "fail"
    assert "scenes-%s" % aspect in fonts["detail"]


@pytest.mark.parametrize("aspect", ["9x16", "1x1"])
def test_an_aspect_mp4_passes_with_clean_matching_fonts(tmp_path, aspect):
    s = Studio(tmp_path)
    mp4 = add_aspect(s, aspect)
    code, out = s.run("--mp4", mp4)
    assert code == 0, out
    assert check_of(out, "fonts")["status"] == "pass"


def test_an_aspect_mp4_fails_on_its_own_folders_fonts(tmp_path):
    s = Studio(tmp_path)
    mp4 = s.vdir / "demo-9x16.mp4"
    mp4.write_bytes(b"x")
    shutil.copytree(FIX / "scenes_linked", s.project / "scenes-9x16")
    code, out = s.run("--mp4", mp4)
    assert code == 1 and "scenes-9x16" in check_of(out, "fonts")["detail"]


# contrast and title_safe ------------------------------------------------------------------------

def test_contrast_and_title_safe_fail_with_commands_when_no_check_json(studio):
    code, out = studio.run(check_args=[])
    assert code == 1
    contrast, safe = check_of(out, "contrast"), check_of(out, "title_safe")
    assert contrast["status"] == "fail" and safe["status"] == "fail"
    assert "hf.py" in contrast["detail"] and "check --json" in contrast["detail"]
    for needle in ("x0=0;y0=0;x1=1;y1=.05", "x0=0;y0=.95;x1=1;y1=1", "x0=0;y0=0;x1=.05;y1=1",
                   "x0=.95;y0=0;x1=1;y1=1", "severity=error", "--caption-zone"):
        assert needle in safe["detail"], needle
    assert safe["detail"].count(";" + SEEK) == 4


def test_contrast_fails_with_count_and_worst_ratio(studio):
    code, out = studio.run(check_args=["top=%s" % (FIX / "check_contrast_fail.json")] + studio.checks[1:])
    contrast = check_of(out, "contrast")
    assert code == 1 and contrast["status"] == "fail"
    assert contrast["measured"] == {"failing": 2, "worst_ratio": 1.51}


def test_contrast_ratio_falls_back_to_the_message(tmp_path):
    doc = {"contrast": {"enabled": True, "findings": [
        {"code": "contrast_aa_failure", "message": "Contrast is 2.10:1; WCAG AA requires 4.5:1.", "text": "x"},
    ]}}
    s = Studio(tmp_path)
    path = write_json(tmp_path / "c.json", doc)
    code, out = s.run(check_args=[path])
    assert check_of(out, "contrast")["measured"] == {"failing": 1, "worst_ratio": 2.1}


def test_contrast_passes_on_clean_and_other_findings_do_not_count(studio):
    code, out = studio.run()
    contrast = check_of(out, "contrast")
    assert contrast["status"] == "pass" and contrast["measured"]["failing"] == 0


def test_title_safe_fails_on_a_band_finding_and_names_the_text(studio):
    checks = ["top=%s" % (FIX / "check_band_top.json")] + studio.checks[1:]
    code, out = studio.run(check_args=checks)
    safe = check_of(out, "title_safe")
    assert code == 1 and safe["status"] == "fail"
    assert safe["measured"]["collisions"] == 1
    assert "Top edge text" in safe["detail"]


def test_title_safe_fails_when_a_band_run_is_missing(studio):
    code, out = studio.run(check_args=studio.checks[:2])
    safe = check_of(out, "title_safe")
    assert safe["status"] == "fail"
    assert "left" in safe["detail"] and "right" in safe["detail"]


def test_an_unlabelled_check_json_still_reports_band_findings(studio):
    code, out = studio.run(check_args=[FIX / "check_band_top.json"])
    assert check_of(out, "title_safe")["status"] == "fail"
    assert check_of(out, "title_safe")["measured"]["collisions"] == 1


def test_check_json_with_leading_log_lines_is_parsed(studio):
    code, out = studio.run(check_args=["top=%s" % (FIX / "check_contrast_fail.json")] + studio.checks[1:])
    assert check_of(out, "contrast")["measured"]["failing"] == 2


def test_unreadable_check_json_is_a_usage_error(studio, tmp_path):
    bad = write_json(tmp_path / "bad.json", "no json here")
    code, out = studio.run(check_args=[bad])
    assert code == 2 and "bad.json" in out["error"]


def _every_band(tmp_path: Path, doc: object) -> list:
    path = write_json(tmp_path / "doc.json", doc)
    return ["%s=%s" % (band, path) for band in BANDS]


@pytest.mark.parametrize("doc", [
    {"error": "browser launch failed"},
    {"ok": False, "error": "browser failed to launch"},
    {},
    {"ok": True},
    [],
])
def test_check_json_without_results_fails_contrast_and_title_safe(studio, tmp_path, doc):
    code, out = studio.run(check_args=_every_band(tmp_path, doc))
    assert code == 1
    for name in ("contrast", "title_safe"):
        check = check_of(out, name)
        assert check["status"] == "fail", check
        assert "doc.json" in check["detail"]


def test_a_tool_error_next_to_complete_sections_still_fails(studio, tmp_path):
    doc = json.loads((FIX / "check_clean.json").read_text())
    doc["error"] = "partial run"
    code, out = studio.run(check_args=_every_band(tmp_path, doc))
    assert check_of(out, "contrast")["status"] == "fail"
    assert check_of(out, "title_safe")["status"] == "fail"


def test_contrast_needs_the_enabled_flag(studio, tmp_path):
    doc = json.loads((FIX / "check_clean.json").read_text())
    doc["contrast"]["enabled"] = False
    code, out = studio.run(check_args=_every_band(tmp_path, doc))
    contrast = check_of(out, "contrast")
    assert contrast["status"] == "fail" and "enabled" in contrast["detail"]
    assert check_of(out, "title_safe")["status"] == "pass"


def test_title_safe_needs_a_layout_findings_list_in_every_band(studio, tmp_path):
    doc = json.loads((FIX / "check_clean.json").read_text())
    del doc["layout"]["findings"]
    bad = write_json(tmp_path / "left.json", doc)
    code, out = studio.run(check_args=studio.checks[:1] + studio.checks[2:] + ["left=%s" % bad])
    safe = check_of(out, "title_safe")
    assert safe["status"] == "fail" and "left.json" in safe["detail"] and "layout" in safe["detail"]
    assert check_of(out, "contrast")["status"] == "pass"


def test_an_invalid_band_document_does_not_count_as_covered(studio, tmp_path):
    bad = write_json(tmp_path / "left.json", {"error": "crashed"})
    code, out = studio.run(check_args=studio.checks[:2] + studio.checks[3:] + ["left=%s" % bad])
    safe = check_of(out, "title_safe")
    assert safe["status"] == "fail"
    assert "left.json" in safe["detail"]


# loudness ---------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "lufs,peak,status",
    [("-16.0", "-1.5", "pass"), ("-15.0", "-1.0", "pass"), ("-17.0", "-3.0", "pass"),
     ("-20.0", "-1.5", "fail"), ("-14.0", "-1.5", "fail"), ("-16.0", "-0.5", "fail")],
)
def test_loudness_thresholds(narrated, lufs, peak, status):
    studio = narrated
    code, out = studio.run(env=studio.env(FAKE_LUFS=lufs, FAKE_TP=peak))
    loud = check_of(out, "loudness")
    assert loud["status"] == status
    assert loud["measured"] == {"lufs": float(lufs), "true_peak_dbtp": float(peak)}
    assert loud["threshold"] == {"lufs": [-17.0, -15.0], "true_peak_dbtp_max": -1.0}


def test_loudness_is_skipped_for_silent_videos(tmp_path):
    s = Studio(tmp_path, narration=False)
    code, out = s.run(env=s.env(FAKE_LUFS="-70.0"))
    assert check_of(out, "loudness")["status"] == "skip"
    assert code == 0


# blender and outside calls ---------------------------------------------------------------------

def test_blender_fails_on_default_scene_and_mirrored_frames(studio):
    write_json(studio.project / "assets" / "3d" / "guard.json", json.loads((FIX / "guard_default_scene.json").read_text()))
    write_json(studio.project / "assets" / "3d2" / "guard.json", json.loads((FIX / "guard_mirrored.json").read_text()))
    code, out = studio.run()
    blender = check_of(out, "blender")
    assert code == 1 and blender["status"] == "fail"
    assert "default scene" in blender["detail"] and "3d/guard.json" in blender["detail"]
    assert "mirrored" in blender["detail"] and "3d2/guard.json" in blender["detail"]
    assert blender["measured"] == {
        "guards": 2, "default_scene": 1, "mirrored_frames": 3,
        "files": ["assets/3d/guard.json", "assets/3d2/guard.json"],
    }


def test_blender_ignores_guards_under_sketches_and_names_the_ones_it_counted(studio):
    ok = json.loads((FIX / "guard_ok.json").read_text())
    bad = json.loads((FIX / "guard_mirrored.json").read_text())
    write_json(studio.project / "assets" / "3d" / "guard.json", ok)
    write_json(studio.project / "assets" / "3d" / "sketches" / "s1" / "guard.json", bad)
    write_json(studio.project / "sketches" / "guard.json", bad)
    code, out = studio.run()
    blender = check_of(out, "blender")
    assert blender["status"] == "pass", blender
    assert blender["measured"]["guards"] == 1
    assert blender["measured"]["files"] == ["assets/3d/guard.json"]
    assert "assets/3d/guard.json" in blender["detail"] and "sketches" not in blender["detail"].replace("(sketches/ ignored)", "")


def test_blender_skips_when_only_sketch_guards_exist(studio):
    write_json(studio.project / "sketches" / "guard.json", json.loads((FIX / "guard_ok.json").read_text()))
    code, out = studio.run()
    assert check_of(out, "blender")["status"] == "skip"


def test_blender_passes_on_a_clean_guard(studio):
    write_json(studio.project / "assets" / "3d" / "guard.json", json.loads((FIX / "guard_ok.json").read_text()))
    code, out = studio.run()
    assert check_of(out, "blender")["status"] == "pass"


def test_outside_calls_pass_for_allowed_providers(tmp_path):
    s = Studio(tmp_path, cloud_allow=["pexels"])
    shutil.copy(FIX / "calls_ok.jsonl", s.project / "calls.jsonl")
    code, out = s.run()
    calls = check_of(out, "outside_calls")
    assert calls["status"] == "pass" and code == 0


def test_outside_calls_fail_lists_offenders(tmp_path):
    s = Studio(tmp_path, cloud_allow=["pexels"])
    shutil.copy(FIX / "calls_bad.jsonl", s.project / "calls.jsonl")
    code, out = s.run()
    calls = check_of(out, "outside_calls")
    assert code == 1 and calls["status"] == "fail"
    assert "elevenlabs" in calls["detail"] and "pexels" not in calls["detail"]
    assert calls["measured"] == {"elevenlabs": 2}


def test_outside_calls_fail_when_nothing_is_allowed(tmp_path):
    s = Studio(tmp_path)
    shutil.copy(FIX / "calls_ok.jsonl", s.project / "calls.jsonl")
    code, out = s.run()
    assert check_of(out, "outside_calls")["status"] == "fail"
    assert check_of(out, "outside_calls")["measured"] == {"pexels": 1}


# attempts and exit codes -----------------------------------------------------------------------

def test_attempts_accumulate_and_stop_at_three_failures(tmp_path):
    s = Studio(tmp_path)
    shutil.copy(FIX / "calls_bad.jsonl", s.project / "calls.jsonl")
    seen = []
    for expected in (1, 2, 3):
        code, out = s.run()
        assert code == 1 and out["passed"] is False
        assert out["attempt"] == expected
        seen.append(out["stop"])
    assert seen == [False, False, True]
    saved = json.loads((s.vdir / "verify.json").read_text())
    assert [a["n"] for a in saved["runs"]["demo-16x9.mp4"]["attempts"]] == [1, 2, 3]


def test_a_passing_attempt_never_stops(tmp_path):
    s = Studio(tmp_path)
    failed = [{"n": n, "ts": "t", "passed": False} for n in (1, 2, 3)]
    write_json(s.vdir / "verify.json", {"version": "v1", "passed": False, "runs": {
        "demo-16x9.mp4": {"attempts": failed, "attempt": 3, "passed": False, "stop": True, "checks": [], "frames": {}}}})
    code, out = s.run()
    assert code == 0 and out["attempt"] == 4 and out["stop"] is False


def test_a_flat_verify_json_becomes_the_run_for_the_single_mp4(tmp_path):
    s = Studio(tmp_path)
    write_json(s.vdir / "verify.json", {
        "version": "v1", "attempt": 2, "passed": False, "stop": False, "checks": [], "frames": {},
        "attempts": [{"n": 1, "ts": "t", "passed": False}, {"n": 2, "ts": "t", "passed": False}]})
    code, out = s.run()
    assert out["attempt"] == 3
    saved = json.loads((s.vdir / "verify.json").read_text())
    assert set(saved) == {"version", "passed", "runs"}
    assert list(saved["runs"]) == ["demo-16x9.mp4"]
    assert [a["n"] for a in saved["runs"]["demo-16x9.mp4"]["attempts"]] == [1, 2, 3]


def test_two_mp4s_keep_separate_runs_in_one_verify_json(tmp_path):
    s = Studio(tmp_path)
    nine = add_aspect(s, "9x16")
    code, first = s.run("--mp4", s.vdir / "demo-16x9.mp4")
    assert code == 0 and first["attempt"] == 1
    code, second = s.run("--mp4", nine)
    assert code == 0 and second["attempt"] == 1 and second["mp4"] == "demo-9x16.mp4"
    saved = json.loads((s.vdir / "verify.json").read_text())
    assert saved["passed"] is True
    assert sorted(saved["runs"]) == ["demo-16x9.mp4", "demo-9x16.mp4"]
    for name, stem in (("demo-16x9.mp4", "demo-16x9"), ("demo-9x16.mp4", "demo-9x16")):
        run = saved["runs"][name]
        assert run["attempt"] == 1 and len(run["attempts"]) == 1 and run["passed"] is True
        assert Path(run["frames"]["sheet"]) == s.vdir / "frames" / stem / "sheet.png"
        assert (s.vdir / "frames" / stem / "sheet.png").is_file()


def test_top_level_passed_needs_every_run_to_pass(tmp_path):
    s = Studio(tmp_path)
    nine = add_aspect(s, "9x16")
    s.run("--mp4", s.vdir / "demo-16x9.mp4")
    code, out = s.run("--mp4", nine, check_args=[])
    assert code == 1 and out["passed"] is False
    saved = json.loads((s.vdir / "verify.json").read_text())
    assert saved["passed"] is False
    assert saved["runs"]["demo-16x9.mp4"]["passed"] is True
    assert saved["runs"]["demo-9x16.mp4"]["passed"] is False


def test_the_three_attempt_stop_counts_per_mp4(tmp_path):
    s = Studio(tmp_path)
    nine = add_aspect(s, "9x16")
    stops = []
    for _ in range(3):
        code, out = s.run("--mp4", nine, check_args=[])
        assert code == 1
        stops.append(out["stop"])
        code, wide = s.run("--mp4", s.vdir / "demo-16x9.mp4")
        assert code == 0 and wide["stop"] is False
    assert stops == [False, False, True]
    saved = json.loads((s.vdir / "verify.json").read_text())
    assert saved["runs"]["demo-16x9.mp4"]["attempt"] == 3
    assert saved["runs"]["demo-9x16.mp4"]["attempt"] == 3
    assert saved["runs"]["demo-9x16.mp4"]["stop"] is True
    assert saved["runs"]["demo-16x9.mp4"]["stop"] is False


def test_corrupt_verify_json_restarts_the_attempt_count(studio):
    (studio.vdir / "verify.json").write_text("{broken")
    code, out = studio.run()
    assert out["attempt"] == 1


def test_missing_project_is_exit_2(studio):
    code, out = studio.run(project=studio.tmp / "nope")
    assert code == 2 and "error" in out


def test_missing_version_is_exit_2(studio):
    code, out = studio.run(version="v9")
    assert code == 2 and "v9" in out["error"]


def test_missing_required_flag_is_exit_2(studio):
    proc = subprocess.run([sys.executable, str(VERIFY_PY)], capture_output=True, text=True, env=studio.env())
    assert proc.returncode == 2
    assert "error" in json.loads(proc.stdout)


def test_missing_mp4_is_exit_1_missing_render(studio):
    (studio.vdir / "demo-16x9.mp4").unlink()
    code, out = studio.run()
    assert code == 1 and out["error"] == "missing_render"


def test_several_mp4s_need_an_explicit_flag(studio):
    add_aspect(studio, "9x16")
    code, out = studio.run()
    assert code == 2 and "--mp4" in out["error"]
    code, out = studio.run("--mp4", studio.vdir / "demo-9x16.mp4")
    assert code == 0


def test_missing_ffmpeg_is_exit_3(tmp_path):
    s = Studio(tmp_path, fake_tools=False)
    empty = tmp_path / "empty"
    empty.mkdir()
    code, out = s.run(env=s.env(PATH=str(empty)))
    assert code == 3
    assert "ffmpeg" in out["error"]


# sync (skip paths need no numpy) ---------------------------------------------------------------

def beats_file(path: Path, **overrides) -> Path:
    beat = {"id": "label", "word": "Hello", "clip": "assets/vo.wav", "expected_s": 1.0,
            "region": [100, 100, 300, 200], "baseline_s": 0.9, "detector": "changed", "color": None}
    beat.update(overrides)
    return write_json(path, [beat])


def test_sync_skips_without_beats(studio):
    code, out = studio.run()
    sync = check_of(out, "sync")
    assert sync["status"] == "skip" and "beats" in sync["detail"]


def test_sync_fails_a_narrated_video_without_beats(narrated):
    code, out = narrated.run()
    sync = check_of(out, "sync")
    assert code == 1 and sync["status"] == "fail"
    assert sync["detail"] == "narrated videos need beats.json (see audio.md)"


def test_sync_fails_a_narrated_video_when_the_venv_is_missing(narrated):
    beats = beats_file(narrated.tmp / "beats.json")
    code, out = narrated.run("--beats", beats, "--audio-json", "assets/vo.wav=%s" % (FIX / "audio_vo.json"))
    sync = check_of(out, "sync")
    assert code == 1 and sync["status"] == "fail"
    assert "venv" in sync["detail"] and "doctor.py check --need narration" in sync["detail"]


def test_sync_skips_with_a_reason_when_the_venv_is_missing(studio):
    beats = beats_file(studio.tmp / "beats.json")
    code, out = studio.run("--beats", beats, "--audio-json", "assets/vo.wav=%s" % (FIX / "audio_vo.json"))
    sync = check_of(out, "sync")
    assert sync["status"] == "skip" and "venv" in sync["detail"]
    assert code == 0


def test_default_beats_file_is_read_from_the_project(studio):
    beats_file(studio.project / "beats.json")
    code, out = studio.run()
    assert "venv" in check_of(out, "sync")["detail"]


def test_malformed_beats_is_a_usage_error(studio):
    path = write_json(studio.tmp / "beats.json", {"not": "a list"})
    code, out = studio.run("--beats", path)
    assert code == 2 and "beats" in out["error"]


def test_color_beat_without_color_is_a_usage_error(studio):
    beats = beats_file(studio.tmp / "beats.json", detector="color", color=None)
    code, out = studio.run("--beats", beats)
    assert code == 2 and "color" in out["error"]


# real ffmpeg -----------------------------------------------------------------------------------

def _ffmpeg(*args: object) -> None:
    subprocess.run([REAL_FFMPEG, "-nostdin", "-v", "error", "-y", *map(str, args)], check=True, timeout=120)


@pytest.fixture(scope="module")
def tone_videos(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("tones")
    out = {}
    for name, volume in (("on_target", "5.1dB"), ("too_loud", "18dB"), ("too_quiet", "-6dB")):
        path = root / ("%s.mp4" % name)
        _ffmpeg("-f", "lavfi", "-i", "sine=frequency=1000:duration=6:sample_rate=48000",
                "-f", "lavfi", "-i", "color=c=gray:s=320x180:r=30:d=6",
                "-af", "volume=%s" % volume, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-shortest", path)
        out[name] = path
    return out


def real_env(s: Studio, **extra: str) -> dict:
    env = s.env(**extra)
    env["PATH"] = "%s:/usr/bin:/bin" % Path(REAL_FFMPEG).parent
    return env


@needs_ffmpeg
@pytest.mark.parametrize("name,status", [("on_target", "pass"), ("too_loud", "fail"), ("too_quiet", "fail")])
def test_loudness_on_a_generated_tone(tmp_path, tone_videos, name, status):
    s = Studio(tmp_path, fake_tools=False, narration=True)
    (s.vdir / "demo-16x9.mp4").unlink()
    code, out = s.run("--mp4", tone_videos[name], env=real_env(s))
    loud = check_of(out, "loudness")
    assert loud["status"] == status, loud
    if name == "on_target":
        assert -17 <= loud["measured"]["lufs"] <= -15
        assert loud["measured"]["true_peak_dbtp"] <= -1.0


@needs_ffmpeg
def test_contact_sheet_and_stills_decode_from_the_real_mp4(tmp_path, tone_videos):
    s = Studio(tmp_path, fake_tools=False)
    (s.vdir / "demo-16x9.mp4").unlink()
    code, out = s.run("--mp4", tone_videos["on_target"], "--at", "1,3,5", env=real_env(s))
    assert out["frames"]["sheet"].endswith("frames/on_target/sheet.png")
    sheet = Path(out["frames"]["sheet"])
    probe = subprocess.run(
        [REAL_FFPROBE, "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(sheet)],
        capture_output=True, text=True,
    )
    assert probe.stdout.strip() == "1920,810"
    assert len(out["frames"]["stills"]) == 3
    assert all(Path(p).stat().st_size > 0 for p in out["frames"]["stills"])


@pytest.fixture(scope="module")
def box_videos(tmp_path_factory) -> dict:
    """1080p 30 fps clips with a box appearing at a known time, in white and in the accent colour."""
    root = tmp_path_factory.mktemp("boxes")
    out = {}
    for name, color, at in (("white_at_1", "white", "1.0"), ("white_at_1_5", "white", "1.5"),
                            ("accent_at_1", "0x1e7a52", "1.0")):
        path = root / ("%s.mp4" % name)
        _ffmpeg("-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=30:d=3", "-vf",
                "drawbox=x=100:y=100:w=300:h=200:color=%s:t=fill:enable='gte(t,%s)'" % (color, at),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", path)
        out[name] = path
    return out


def venv_shim(s: Studio) -> None:
    shim = s.cache / "venv" / "bin" / "python"
    shim.parent.mkdir(parents=True)
    import numpy

    site = Path(numpy.__file__).resolve().parent.parent
    shim.write_text("#!/bin/sh\nPYTHONPATH=%s exec %s \"$@\"\n" % (site, sys.executable))
    shim.chmod(0o755)


def audio_doc(silence_end=1.0, onsets=()):
    return {"items": [{"duration": 3.0, "onsets": {"events": [{"t": t, "strength": st} for t, st in onsets]},
                       "silence": [{"start": 0, "end": silence_end}] if silence_end is not None else []}]}


def run_sync(tmp_path, video, audio, **beat):
    pytest.importorskip("numpy")
    s = Studio(tmp_path, fake_tools=False)
    venv_shim(s)
    (s.vdir / "demo-16x9.mp4").unlink()
    beats = beats_file(tmp_path / "beats.json", **beat)
    audio_path = write_json(tmp_path / "vo.audio.json", audio)
    return s.run("--mp4", video, "--beats", beats, "--audio-json", "assets/vo.wav=%s" % audio_path, env=real_env(s))


@needs_ffmpeg
def test_sync_passes_when_the_picture_lands_on_the_word(tmp_path, box_videos):
    code, out = run_sync(tmp_path, box_videos["white_at_1"], audio_doc())
    sync = check_of(out, "sync")
    assert sync["status"] == "pass", sync
    assert sync["measured"]["worst_frames"] == 0
    assert sync["measured"]["beats"][0]["via"] == "silence"


@needs_ffmpeg
def test_sync_fails_when_the_picture_is_late(tmp_path, box_videos):
    code, out = run_sync(tmp_path, box_videos["white_at_1_5"], audio_doc())
    sync = check_of(out, "sync")
    assert sync["status"] == "fail"
    assert sync["measured"]["worst_frames"] == pytest.approx(15, abs=0.1)
    assert "label" in sync["detail"]


@needs_ffmpeg
def test_sync_color_detector_finds_the_accent_box(tmp_path, box_videos):
    code, out = run_sync(tmp_path, box_videos["accent_at_1"], audio_doc(), detector="color", color="#1e7a52")
    assert check_of(out, "sync")["status"] == "pass"


@needs_ffmpeg
def test_sync_color_detector_ignores_a_different_colour(tmp_path, box_videos):
    code, out = run_sync(tmp_path, box_videos["white_at_1"], audio_doc(), detector="color", color="#1e7a52")
    sync = check_of(out, "sync")
    assert sync["status"] == "fail" and "no change" in sync["detail"]


@needs_ffmpeg
def test_sync_flags_a_beat_with_no_audio_onset_and_uses_the_expected_time(tmp_path, box_videos):
    code, out = run_sync(tmp_path, box_videos["white_at_1"], audio_doc(silence_end=None))
    sync = check_of(out, "sync")
    assert sync["status"] == "pass"
    assert sync["measured"]["beats"][0]["via"] == "expected"
    assert "flagged" in sync["detail"]


@needs_ffmpeg
def test_sync_clip_start_shifts_audio_into_film_time(tmp_path, box_videos):
    code, out = run_sync(tmp_path, box_videos["white_at_1"], audio_doc(silence_end=0.5), clip_start_s=0.5)
    assert check_of(out, "sync")["status"] == "pass"


# media_worker logic ----------------------------------------------------------------------------

def blank(n=4, h=20, w=40):
    import numpy as np
    return [np.zeros((h, w, 3), np.uint8) for _ in range(n)]


def test_worker_changed_share_counts_pixels_over_the_threshold():
    worker = _load_worker()
    import numpy as np
    base = np.zeros((10, 10, 3), np.uint8)
    cur = base.copy()
    cur[:2, :5] = 25
    assert worker.changed_share(base, cur) == pytest.approx(0.1)
    cur[:2, :5] = 24
    assert worker.changed_share(base, cur) == 0.0


def test_worker_color_share_uses_a_tolerance_around_the_colour():
    worker = _load_worker()
    import numpy as np
    cur = np.zeros((10, 10, 3), np.uint8)
    cur[:5] = (30, 122, 82)
    assert worker.color_share(cur, (30, 122, 82)) == pytest.approx(0.5)
    cur[:5] = (30 + 20, 122 - 20, 82 + 20)
    assert worker.color_share(cur, (30, 122, 82)) == pytest.approx(0.5)
    cur[:5] = (255, 255, 255)
    assert worker.color_share(cur, (30, 122, 82)) == 0.0


def test_worker_parse_color():
    worker = _load_worker()
    assert worker.parse_color("#1e7a52") == (30, 122, 82)


def test_worker_region_scales_to_the_half_size_decode():
    worker = _load_worker()
    assert worker.scale_region([100, 40, 300, 200], 0.5, 960, 540) == (50, 20, 200, 120)
    assert worker.scale_region([1900, 1070, 500, 500], 0.5, 960, 540) == (950, 535, 960, 540)


def test_worker_visual_onset_finds_first_changed_frame_after_baseline():
    worker = _load_worker()
    frames = blank(6)
    for i in (3, 4, 5):
        frames[i][:, :] = 200
    assert worker.visual_onset(frames, (0, 0, 40, 20), 0, "changed", None) == 3
    assert worker.visual_onset(frames, (0, 0, 40, 20), 3, "changed", None) is None


def test_worker_visual_onset_color_counts_only_new_colour():
    worker = _load_worker()
    frames = blank(5)
    for i in (0, 1, 2, 3, 4):
        frames[i][:, :] = (30, 122, 82)
    assert worker.visual_onset(frames, (0, 0, 40, 20), 0, "color", (30, 122, 82)) is None
    frames = blank(5)
    for i in (2, 3, 4):
        frames[i][:, :] = (30, 122, 82)
    assert worker.visual_onset(frames, (0, 0, 40, 20), 0, "color", (30, 122, 82)) == 2


def test_worker_select_onset_prefers_silence_end_then_onset_then_expected():
    worker = _load_worker()
    item = {"duration": 10.0,
            "silence": [{"start": 0, "end": 0.36}, {"start": 1, "end": 10.0}],
            "onsets": {"events": [{"t": 0.575, "strength": 0.58}, {"t": 0.9, "strength": 0.05},
                                  {"t": 1.3, "strength": 0.4}]}}
    assert worker.select_onset(0.37, item, 0.0) == (0.36, "silence", False)
    assert worker.select_onset(0.57, item, 0.0) == (0.575, "onset", False)
    # a weak onset is ignored; a silence that runs to the end of the clip is not a word start
    assert worker.select_onset(0.9, item, 0.0) == (0.9, "expected", True)
    assert worker.select_onset(10.0, item, 0.0) == (10.0, "expected", True)
    assert worker.select_onset(1.8, item, 0.5) == (1.8, "onset", False)


def test_worker_main_reports_a_request_error(tmp_path):
    pytest.importorskip("numpy")
    proc = subprocess.run([sys.executable, str(WORKER_PY)], input="not json", capture_output=True, text=True)
    assert proc.returncode == 1
    assert "error" in json.loads(proc.stdout)


def test_worker_keeps_full_precision_offsets():
    worker = _load_worker()
    frames = blank(6)
    for i in (3, 4, 5):
        frames[i][:, :] = 200
    worker.decode_window = lambda *a, **k: frames
    worker.select_onset = lambda *a, **k: (2 / 24, "silence", False)
    report = worker.analyse({
        "mp4": "x.mp4", "fps": 24, "width": 80, "height": 40, "audio": {"a": {}},
        "beats": [{"id": "b", "clip_key": "a", "expected_s": 0.5, "baseline_s": 0.0, "region": [0, 0, 80, 40]}],
    })
    row = report["beats"][0]
    assert row["offset_s"] == pytest.approx(1 / 24, abs=1e-12)
    assert row["offset_frames"] == pytest.approx(1.0, abs=1e-9)


def test_worker_ffmpeg_child_is_scrubbed_of_keys(monkeypatch):
    worker = _load_worker()
    seen = {}

    def fake_run(argv, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.setattr(worker.subprocess, "run", fake_run)
    worker.decode_window("x.mp4", 0, 1, 24.0, 4, 4)
    assert "GEMINI_API_KEY" not in seen["env"]


def test_sync_passes_a_beat_exactly_one_frame_off_at_full_precision(tmp_path):
    s = Studio(tmp_path)
    shim = s.cache / "venv" / "bin" / "python"
    shim.parent.mkdir(parents=True)
    row = {"id": "label", "via": "silence", "offset_s": 1 / 30, "offset_frames": 1.0}
    shim.write_text("#!/bin/sh\ncat >/dev/null\necho '%s'\n" % json.dumps({"beats": [row]}))
    shim.chmod(0o755)
    beats = beats_file(tmp_path / "beats.json")
    audio = write_json(tmp_path / "vo.audio.json", audio_doc())
    code, out = s.run("--beats", beats, "--audio-json", "assets/vo.wav=%s" % audio)
    sync = check_of(out, "sync")
    assert sync["status"] == "pass", sync
    assert sync["measured"]["worst_frames"] == 1.0


def test_media_children_never_see_provider_or_gemini_keys(tmp_path):
    s = Studio(tmp_path)
    log = tmp_path / "env.log"
    for name in ("ffmpeg", "ffprobe"):
        path = s.bin / name
        body = path.read_text().split("\n", 1)[1]
        path.write_text('#!/bin/sh\nenv >> "$ENV_LOG"\n' + body)
    keys = {k: "secret" for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ELEVENLABS_API_KEY", "OPENAI_API_KEY")}
    code, out = s.run(env=s.env(ENV_LOG=str(log), **keys))
    assert code == 0, out
    text = log.read_text()
    assert "HOME=" in text
    for key in keys:
        assert key not in text


@pytest.mark.parametrize("script", sorted(p.name for p in SCRIPTS.glob("*.py")))
def test_running_a_script_leaves_no_pycache_in_the_skill_directory(tmp_path, script):
    copy = tmp_path / "scripts"
    shutil.copytree(SCRIPTS, copy, ignore=shutil.ignore_patterns("__pycache__"))
    env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
    env.update({"HOME": str(tmp_path / "home"), "QUIRK_STUDIO": str(tmp_path / "studio"),
                "QUIRK_VIDEO_CACHE": str(tmp_path / "cache")})
    subprocess.run([sys.executable, str(copy / script), "--help"], stdin=subprocess.DEVNULL,
                   capture_output=True, text=True, env=env, timeout=60)
    assert not list(copy.rglob("__pycache__"))
