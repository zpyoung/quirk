"""Tests for the making-videos narration launcher, caption builder and Kokoro/whisper worker."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "making-videos" / "scripts"
VOICE_PY = SCRIPTS / "voice.py"
WORKER_PY = SCRIPTS / "voice_worker.py"

SRT_TIME = re.compile(r"^(\d\d):(\d\d):(\d\d),(\d\d\d)$")


@pytest.fixture()
def env(tmp_path: Path) -> dict:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "QUIRK_STUDIO": str(tmp_path / "studio"),
        "QUIRK_VIDEO_CACHE": str(tmp_path / "cache"),
        "QUIRK_FFMPEG_FULL_PATHS": "",
    }


def run_voice(*args: object, env: dict) -> tuple[int, dict, str]:
    proc = subprocess.run(
        [sys.executable, str(VOICE_PY), *map(str, args)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    out = proc.stdout.strip()
    assert out, f"no stdout (rc={proc.returncode}): {proc.stderr}"
    assert len(out.splitlines()) == 1, out
    return proc.returncode, json.loads(out), proc.stderr


def write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return path


def make_project(tmp_path: Path, product: str = "acme", brand: object = "default") -> Path:
    studio = tmp_path / "studio"
    project = studio / "videos" / "2026-10-22-demo"
    write_json(project / "brief.json", {"slug": "demo", "product": product})
    if brand == "default":
        brand = {
            "product": product,
            "voice": {"engine": "kokoro", "id": "af_heart"},
            "pronunciations": {"quirk": {"from": "kwˈɜːk", "to": "kwˈɜɹk"}},
        }
    if brand is not None:
        write_json(studio / "brands" / product / "brand.json", brand)
    return project


def write_words(project: Path, clip: str, words: "list[tuple[str, float, float]]") -> None:
    write_json(
        project / "assets" / "voice" / f"{clip}.words.json",
        [{"text": t, "start": s, "end": e} for t, s, e in words],
    )


def make_stub(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def fake_venv_python(tmp_path: Path, reply: str, code: int = 0) -> Path:
    log = tmp_path / "worker.log"
    body = (
        f'echo "$@" > "{log}.argv"\n'
        f'env > "{log}.env"\n'
        f"echo '{reply}'\n"
        f"exit {code}\n"
    )
    return make_stub(tmp_path / "cache" / "venv" / "bin" / "python", body)


def fake_ffmpeg(tmp_path: Path, with_subtitles: bool = True, fail: bool = False) -> Path:
    log = tmp_path / "ffmpeg.argv"
    filters = (
        " T.. subtitles        V->V       Render text subtitles onto input video using libass.\\n"
        if with_subtitles
        else ""
    )
    body = (
        'case "$*" in\n'
        "  *-filters*)\n"
        f'    printf " ... scale   V->V   Scale.\\n{filters}"\n'
        "    exit 0;;\n"
        "esac\n"
        f'echo "$@" > "{log}"\n'
        + ("echo 'boom: encoder exploded' >&2\nexit 1\n" if fail else 'for last; do :; done\ntouch "$last"\n')
    )
    return make_stub(tmp_path / "bin" / "ffmpeg", body)


def with_ffmpeg(env: dict, tmp_path: Path) -> dict:
    return dict(env, QUIRK_FFMPEG=str(make_stub(tmp_path / "ffbin" / "ffmpeg", "exit 0\n")))


def fake_ffprobe(tmp_path: Path, width: int = 1080, height: int = 1920, extra: str = "") -> Path:
    stream = f'{{"width": {width}, "height": {height}{extra}}}'
    body = f"""echo '{{"streams": [{stream}]}}'\n"""
    return make_stub(tmp_path / "bin" / "ffprobe", body)


def burn_vf(tmp_path: Path) -> str:
    match = re.search(r"-vf (.*?) -c:v ", (tmp_path / "ffmpeg.argv").read_text())
    assert match
    return match.group(1)


def style_of(vf: str) -> dict:
    match = re.search(r"force_style='([^']*)'", vf)
    assert match, vf
    return dict(pair.split("=", 1) for pair in match.group(1).split(","))


def burn_args(tmp_path: Path, *extra: object) -> "tuple[list, Path]":
    video = tmp_path / "in.mp4"
    video.write_bytes(b"")
    burned = tmp_path / "out" / "burned.mp4"
    return ["--burn", video, "--burned", burned, *extra], burned


def parse_srt(text: str) -> "list[dict]":
    cues = []
    for block in text.strip().split("\n\n"):
        lines = block.split("\n")
        start, end = lines[1].split(" --> ")
        cues.append(
            {"n": int(lines[0]), "start": _secs(start), "end": _secs(end), "lines": lines[2:]}
        )
    return cues


def _secs(stamp: str) -> float:
    m = SRT_TIME.match(stamp)
    assert m, stamp
    h, mi, s, ms = map(int, m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000


# ---------------------------------------------------------------- launcher


def test_say_without_venv_exits_3_with_doctor_fix(env, tmp_path):
    project = make_project(tmp_path)
    lines = write_json(tmp_path / "lines.json", [{"id": "a", "text": "Hi.", "start_s": 0}])
    code, out, _ = run_voice("say", "--project", project, "--lines", lines, env=env)
    assert code == 3
    assert "doctor.py install --what tts --yes" in out["fix"]


def test_align_without_venv_exits_3(env, tmp_path):
    project = make_project(tmp_path)
    code, out, _ = run_voice("align", "--project", project, env=env)
    assert code == 3
    assert "doctor.py install --what tts --yes" in out["fix"]


def test_say_runs_worker_with_brand_voice_and_env(env, tmp_path):
    project = make_project(tmp_path)
    lines = write_json(tmp_path / "lines.json", [{"id": "a", "text": "Hi.", "start_s": 0}])
    reply = json.dumps({"clips": [{"id": "a", "wav": "x.wav", "duration_s": 1.2}]})
    fake_venv_python(tmp_path, reply)
    env = dict(env, GEMINI_API_KEY="leak", GOOGLE_API_KEY="leak", ELEVENLABS_API_KEY="leak", QUIRK_FFMPEG=str(make_stub(tmp_path / "x" / "ffmpeg", "exit 0\n")))
    code, out, _ = run_voice("say", "--project", project, "--lines", lines, env=env)
    assert code == 0
    assert out == json.loads(reply)
    argv = (tmp_path / "worker.log.argv").read_text().split()
    assert argv[0] == str(WORKER_PY)
    assert argv[1] == "say"
    assert argv[argv.index("--ffmpeg") + 1] == str(tmp_path / "x" / "ffmpeg")
    assert argv[argv.index("--voice") + 1] == "af_heart"
    assert argv[argv.index("--out-dir") + 1] == str(project / "assets" / "voice")
    assert argv[argv.index("--model-dir") + 1] == str(tmp_path / "cache" / "models" / "kokoro")
    assert (project / "assets" / "voice").is_dir()
    child_env = dict(
        line.split("=", 1) for line in (tmp_path / "worker.log.env").read_text().splitlines() if "=" in line
    )
    assert child_env["ORT_DISABLE_TELEMETRY"] == "1"
    assert child_env["HF_HOME"] == str(tmp_path / "cache" / "hf")
    for leaked in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ELEVENLABS_API_KEY"):
        assert leaked not in child_env


def test_say_passes_brand_pronunciations_to_worker(env, tmp_path):
    project = make_project(tmp_path)
    lines = write_json(tmp_path / "lines.json", [{"id": "a", "text": "Hi.", "start_s": 0}])
    fake_venv_python(tmp_path, json.dumps({"clips": []}))
    code, _, _ = run_voice("say", "--project", project, "--lines", lines, env=with_ffmpeg(env, tmp_path))
    assert code == 0
    raw = (tmp_path / "worker.log.argv").read_text()
    argv = raw.split(" --pronunciations ", 1)[1].strip()
    assert json.loads(argv) == {"quirk": {"from": "kwˈɜːk", "to": "kwˈɜɹk"}}


def test_say_explicit_voice_wins(env, tmp_path):
    project = make_project(tmp_path)
    lines = write_json(tmp_path / "lines.json", [{"id": "a", "text": "Hi.", "start_s": 0}])
    fake_venv_python(tmp_path, json.dumps({"clips": []}))
    code, _, _ = run_voice("say", "--project", project, "--lines", lines, "--voice", "bf_emma", env=with_ffmpeg(env, tmp_path))
    assert code == 0
    argv = (tmp_path / "worker.log.argv").read_text().split()
    assert argv[argv.index("--voice") + 1] == "bf_emma"


def test_say_cloud_engine_brand_exits_1_pointing_at_cloud(env, tmp_path):
    brand = {"product": "acme", "voice": {"engine": "elevenlabs", "id": "rachel"}}
    project = make_project(tmp_path, brand=brand)
    lines = write_json(tmp_path / "lines.json", [{"id": "a", "text": "Hi.", "start_s": 0}])
    fake_venv_python(tmp_path, json.dumps({"clips": []}))
    code, out, _ = run_voice("say", "--project", project, "--lines", lines, env=env)
    assert code == 1
    assert "cloud.py" in out["error"]
    assert not (tmp_path / "worker.log.argv").exists()


def test_say_without_voice_or_brand_exits_1(env, tmp_path):
    project = make_project(tmp_path, brand=None)
    lines = write_json(tmp_path / "lines.json", [{"id": "a", "text": "Hi.", "start_s": 0}])
    fake_venv_python(tmp_path, json.dumps({"clips": []}))
    code, out, _ = run_voice("say", "--project", project, "--lines", lines, env=env)
    assert code == 1
    assert "--voice" in out["error"]


def test_say_rejects_unsafe_clip_ids(env, tmp_path):
    project = make_project(tmp_path)
    fake_venv_python(tmp_path, json.dumps({"clips": []}))
    for bad in ("../evil", ".hidden", "a/b", "a\\b"):
        lines = write_json(tmp_path / "lines.json", [{"id": bad, "text": "Hi.", "start_s": 0}])
        code, out, _ = run_voice("say", "--project", project, "--lines", lines, env=env)
        assert code == 1, bad
        assert "id" in out["error"]


def test_say_worker_failure_exits_1_with_stderr_tail(env, tmp_path):
    project = make_project(tmp_path)
    lines = write_json(tmp_path / "lines.json", [{"id": "a", "text": "Hi.", "start_s": 0}])
    make_stub(
        tmp_path / "cache" / "venv" / "bin" / "python",
        "echo 'kokoro model missing' >&2\nexit 7\n",
    )
    code, out, _ = run_voice("say", "--project", project, "--lines", lines, env=with_ffmpeg(env, tmp_path))
    assert code == 1
    assert "kokoro model missing" in out["error"]


def test_say_without_ffmpeg_exits_3_with_install_fix(env, tmp_path):
    project = make_project(tmp_path)
    lines = write_json(tmp_path / "lines.json", [{"id": "a", "text": "Hi.", "start_s": 0}])
    fake_venv_python(tmp_path, json.dumps({"clips": []}))
    code, out, _ = run_voice("say", "--project", project, "--lines", lines, env=env)
    assert code == 3
    assert out["missing"] == "ffmpeg" and out["fix"] == "brew install ffmpeg-full"
    assert not (tmp_path / "worker.log.argv").exists()


def test_say_maps_a_worker_missing_ffmpeg_reply_to_exit_3(env, tmp_path):
    project = make_project(tmp_path)
    lines = write_json(tmp_path / "lines.json", [{"id": "a", "text": "Hi.", "start_s": 0}])
    reply = json.dumps({"error": "ffmpeg not found: ffmpeg", "missing": "ffmpeg"})
    fake_venv_python(tmp_path, reply, code=3)
    code, out, _ = run_voice("say", "--project", project, "--lines", lines, env=with_ffmpeg(env, tmp_path))
    assert code == 3
    assert out["missing"] == "ffmpeg" and out["fix"] == "brew install ffmpeg-full"


def test_say_rejects_ids_that_collide_with_raw_clips(env, tmp_path):
    project = make_project(tmp_path)
    lines = write_json(tmp_path / "lines.json", [{"id": "a.raw", "text": "Hi.", "start_s": 0}])
    fake_venv_python(tmp_path, json.dumps({"clips": []}))
    code, out, _ = run_voice("say", "--project", project, "--lines", lines, env=env)
    assert code == 1
    assert ".raw" in out["error"]


def test_say_missing_project_exits_1(env, tmp_path):
    lines = write_json(tmp_path / "lines.json", [{"id": "a", "text": "Hi.", "start_s": 0}])
    fake_venv_python(tmp_path, json.dumps({"clips": []}))
    code, out, _ = run_voice("say", "--project", tmp_path / "nope", "--lines", lines, env=env)
    assert code == 1
    assert "project" in out["error"]


def test_align_runs_worker_over_project_wavs(env, tmp_path):
    project = make_project(tmp_path)
    voice_dir = project / "assets" / "voice"
    voice_dir.mkdir(parents=True)
    (voice_dir / "b.wav").write_bytes(b"")
    (voice_dir / "a.wav").write_bytes(b"")
    reply = json.dumps({"words": [{"clip": "a", "path": "p"}]})
    fake_venv_python(tmp_path, reply)
    code, out, _ = run_voice("align", "--project", project, "--model", "small.en", env=env)
    assert code == 0
    assert out == json.loads(reply)
    argv = (tmp_path / "worker.log.argv").read_text().split()
    assert argv[1] == "align"
    assert argv[argv.index("--model") + 1] == "small.en"
    wavs = argv[argv.index("--wavs") + 1 :]
    assert wavs == [str(voice_dir / "a.wav"), str(voice_dir / "b.wav")]


def test_align_skips_the_untouched_raw_clips(env, tmp_path):
    project = make_project(tmp_path)
    voice_dir = project / "assets" / "voice"
    voice_dir.mkdir(parents=True)
    for name in ("a.wav", "a.raw.wav"):
        (voice_dir / name).write_bytes(b"")
    fake_venv_python(tmp_path, json.dumps({"words": []}))
    code, _, _ = run_voice("align", "--project", project, env=env)
    assert code == 0
    argv = (tmp_path / "worker.log.argv").read_text().split()
    assert argv[argv.index("--wavs") + 1 :] == [str(voice_dir / "a.wav")]


def test_align_with_no_clips_exits_1(env, tmp_path):
    project = make_project(tmp_path)
    fake_venv_python(tmp_path, json.dumps({"words": []}))
    code, out, _ = run_voice("align", "--project", project, env=env)
    assert code == 1
    assert "say" in out["error"]


# ---------------------------------------------------------------- captions


def captions(env, project: Path, tmp_path: Path, lines: list, *extra: object):
    lines_file = write_json(tmp_path / "caption-lines.json", lines)
    out = tmp_path / "out" / "demo.srt"
    code, payload, _ = run_voice(
        "captions", "--project", project, "--lines", lines_file, "--out", out, *extra, env=env
    )
    return code, payload, out


def test_captions_exact_small_case(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Hello", 0.0, 0.4), ("there,", 0.5, 0.9), ("friend.", 1.0, 1.6)])
    write_words(project, "b", [("Second", 0.0, 0.5), ("clip.", 0.6, 1.0)])
    write_words(project, "c", [("Hi.", 0.0, 0.3)])
    code, payload, out = captions(
        env,
        project,
        tmp_path,
        [
            {"id": "a", "start_s": 0},
            {"id": "b", "start_s": 3.0},
            {"id": "c", "start_s": 6.0},
        ],
    )
    assert code == 0
    assert payload == {"srt": str(out), "burned": None, "text_mismatches": []}
    assert out.read_text() == (
        "1\n00:00:00,000 --> 00:00:01,600\nHello there, friend.\n\n"
        "2\n00:00:03,000 --> 00:00:04,000\nSecond clip.\n\n"
        "3\n00:00:06,000 --> 00:00:07,000\nHi.\n"
    )


def test_captions_extends_short_cue_only_up_to_next_cue(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Wow.", 0.0, 0.3), ("Next", 0.8, 1.4), ("one.", 1.5, 2.2)])
    code, _, out = captions(env, project, tmp_path, [{"id": "a", "start_s": 10.0}])
    assert code == 0
    cues = parse_srt(out.read_text())
    assert [(c["start"], c["end"]) for c in cues] == [(10.0, 10.8), (10.8, 12.2)]


def test_captions_timestamps_use_hours_and_milliseconds(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Late.", 0.25, 1.5)])
    code, _, out = captions(env, project, tmp_path, [{"id": "a", "start_s": 3723.0}])
    assert code == 0
    assert "01:02:03,250 --> 01:02:04,500" in out.read_text()


def long_clip() -> "list[tuple[str, float, float]]":
    words = []
    t = 0.0
    lengths = [3, 7, 5, 9, 4, 6, 8, 2, 5, 10, 3, 6]
    for i in range(160):
        text = "x" * lengths[i % len(lengths)]
        if i % 11 == 10:
            text += "."
        dur = (len(text) + 1) / 14.0
        words.append((text, round(t, 3), round(t + dur, 3)))
        t += dur + (0.45 if i % 11 == 10 else 0.04)
    return words


def test_captions_long_case_respects_limits(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", long_clip())
    write_words(project, "b", long_clip()[:30])
    lines = [{"id": "a", "start_s": 0.0}, {"id": "b", "start_s": 200.0}]
    code, _, out = captions(env, project, tmp_path, lines)
    assert code == 0
    cues = parse_srt(out.read_text())
    assert len(cues) > 10
    for prev, cue in zip(cues, cues[1:]):
        assert prev["end"] <= cue["start"] + 1e-9
    for cue in cues:
        assert 1 <= len(cue["lines"]) <= 2
        assert all(len(line) <= 42 for line in cue["lines"])
        duration = cue["end"] - cue["start"]
        assert duration >= 1.0 - 1e-9
        chars = len(" ".join(cue["lines"]))
        assert chars / duration <= 20.0 + 1e-9
    assert any(len(cue["lines"]) == 2 for cue in cues)


def test_captions_merges_fast_neighbours_to_meet_speed_limit(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Extraordinary.", 0.0, 0.3), ("Next.", 0.4, 0.7)])
    code, _, out = captions(env, project, tmp_path, [{"id": "a", "start_s": 0}])
    assert code == 0
    cues = parse_srt(out.read_text())
    assert [c["lines"] for c in cues] == [["Extraordinary. Next."]]
    assert len(cues[0]["lines"][0]) / (cues[0]["end"] - cues[0]["start"]) <= 20.0 + 1e-9


def test_captions_resplits_words_when_merged_cue_would_not_fit(env, tmp_path):
    project = make_project(tmp_path)
    tail = (
        "one two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen fifteen sixteen seventeen."
    ).split()
    words = [("Extraordinary.", 0.0, 0.2)]
    t = 0.3
    for word in tail:
        words.append((word, t, t + 0.3))
        t += 0.35
    write_words(project, "a", words)
    code, _, out = captions(env, project, tmp_path, [{"id": "a", "start_s": 0}])
    assert code == 0
    cues = parse_srt(out.read_text())
    assert " ".join(" ".join(c["lines"]) for c in cues) == " ".join(w[0] for w in words)
    assert cues[0]["lines"][0].startswith("Extraordinary. one")
    for cue in cues:
        assert len(" ".join(cue["lines"])) / (cue["end"] - cue["start"]) <= 20.0 + 1e-9
        assert len(cue["lines"]) <= 2 and all(len(line) <= 42 for line in cue["lines"])


def test_captions_fast_speech_fails_loud_but_writes_srt(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Extraordinary", 0.0, 0.2), ("acceleration", 0.2, 0.4)])
    write_words(project, "b", [("Next.", 0.0, 0.5)])
    code, payload, out = captions(
        env,
        project,
        tmp_path,
        [{"id": "a", "start_s": 0}, {"id": "b", "start_s": 0.5}],
    )
    assert code == 1
    assert payload["ok"] is False
    assert payload["srt"] == str(out)
    assert out.exists()
    (violation,) = payload["cps_violations"]
    assert violation["cue"] == 1
    assert violation["start"] == 0.0 and violation["end"] == 0.5
    assert violation["cps"] > 20
    assert "error" in payload


def test_captions_fast_speech_does_not_burn(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Extraordinary", 0.0, 0.2), ("acceleration", 0.2, 0.4)])
    write_words(project, "b", [("Next.", 0.0, 0.5)])
    stub = fake_ffmpeg(tmp_path)
    video = tmp_path / "in.mp4"
    video.write_bytes(b"")
    burned = tmp_path / "burned.mp4"
    env = dict(env, QUIRK_FFMPEG=str(stub))
    code, payload, _ = captions(
        env,
        project,
        tmp_path,
        [{"id": "a", "start_s": 0}, {"id": "b", "start_s": 0.5}],
        "--burn",
        video,
        "--burned",
        burned,
    )
    assert code == 1
    assert payload["ok"] is False
    assert not burned.exists()


def test_captions_breaks_word_longer_than_line_limit(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("x" * 50, 0.0, 3.0)])
    code, _, out = captions(env, project, tmp_path, [{"id": "a", "start_s": 0}])
    assert code == 0
    (cue,) = parse_srt(out.read_text())
    assert cue["lines"] == ["x" * 41 + "-", "x" * 9]


def test_captions_breaks_very_long_word_across_cues(env, tmp_path):
    project = make_project(tmp_path)
    token = "y" * 130
    write_words(project, "a", [(token, 0.0, 12.0)])
    code, _, out = captions(env, project, tmp_path, [{"id": "a", "start_s": 0}])
    assert code == 0
    cues = parse_srt(out.read_text())
    lines = [line for cue in cues for line in cue["lines"]]
    assert all(len(line) <= 42 for line in lines)
    assert all(len(cue["lines"]) <= 2 for cue in cues)
    assert "".join(line.rstrip("-") for line in lines) == token


def test_captions_missing_words_json_exits_1(env, tmp_path):
    project = make_project(tmp_path)
    code, out, _ = captions(env, project, tmp_path, [{"id": "a", "start_s": 0}])
    assert code == 1
    assert "align" in out["error"]


def test_captions_burn_requires_burned(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Hi.", 0.0, 0.3)])
    code, out, _ = captions(
        env, project, tmp_path, [{"id": "a", "start_s": 0}], "--burn", tmp_path / "in.mp4"
    )
    assert code == 2
    assert "--burned" in out["error"]


def test_captions_burn_argv(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Hi.", 0.0, 0.3)])
    stub = fake_ffmpeg(tmp_path)
    video = tmp_path / "in.mp4"
    video.write_bytes(b"")
    burned = tmp_path / "out" / "burned.mp4"
    env = dict(env, QUIRK_FFMPEG=str(stub))
    code, payload, srt = captions(
        env,
        project,
        tmp_path,
        [{"id": "a", "start_s": 0}],
        "--burn",
        video,
        "--burned",
        burned,
        "--aspect",
        "16:9",
    )
    assert code == 0
    assert payload == {"srt": str(srt), "burned": str(burned), "text_mismatches": []}
    assert burned.exists()
    argv = (tmp_path / "ffmpeg.argv").read_text().split()
    assert argv[argv.index("-i") + 1] == str(video)
    vf = argv[argv.index("-vf") + 1]
    assert vf.startswith("subtitles=") and str(srt) in vf.replace("\\", "")
    for flag, value in [
        ("-c:v", "libx264"),
        ("-pix_fmt", "yuv420p"),
        ("-crf", "18"),
        ("-c:a", "copy"),
        ("-movflags", "+faststart"),
    ]:
        assert argv[argv.index(flag) + 1] == value
    assert argv[-1] == str(burned)


def _burn_style(env, tmp_path, aspect=None, probed=None):
    project = make_project(tmp_path)
    write_words(project, "a", [("Hi.", 0.0, 0.3)])
    stub = fake_ffmpeg(tmp_path)
    if probed:
        fake_ffprobe(tmp_path, *probed)
    args, _ = burn_args(tmp_path, *(["--aspect", aspect] if aspect else []))
    code, payload, _ = captions(
        dict(env, QUIRK_FFMPEG=str(stub)), project, tmp_path, [{"id": "a", "start_s": 0}], *args
    )
    return code, payload


def test_captions_burn_9x16_lifts_captions_clear_of_platform_ui(env, tmp_path):
    code, _ = _burn_style(env, tmp_path, aspect="9:16", probed=(1080, 1920))
    assert code == 0
    style = style_of(burn_vf(tmp_path))
    # libass units at PlayRes 384x288: 672 px * 288/1920, 120 and 192 px * 384/1080, 48 px font * 288/1920
    assert style["MarginV"] == "101"
    assert style["MarginL"] == "43"
    assert style["MarginR"] == "68"
    assert float(style["FontSize"]) == pytest.approx(7.2)
    assert float(style["Outline"]) == pytest.approx(0.6)
    assert style["Alignment"] == "2" and style["BorderStyle"] == "1"
    assert style["PrimaryColour"] == "&H00FFFFFF" and style["OutlineColour"] == "&H00000000"


def test_captions_burn_style_scales_with_the_probed_size(env, tmp_path):
    code, _ = _burn_style(env, tmp_path, aspect="9:16", probed=(540, 960))
    assert code == 0
    style = style_of(burn_vf(tmp_path))
    # same pixel fractions on half the frame: 336 px bottom -> 336 * 288/960
    assert style["MarginV"] == "101"
    assert float(style["FontSize"]) == pytest.approx(7.2)


def test_captions_burn_1x1_margins(env, tmp_path):
    code, _ = _burn_style(env, tmp_path, aspect="1:1", probed=(1080, 1080))
    assert code == 0
    style = style_of(burn_vf(tmp_path))
    assert style["MarginV"] == "29"
    assert style["MarginL"] == style["MarginR"] == "19"
    assert float(style["FontSize"]) == pytest.approx(11.73)


def test_captions_burn_16x9_keeps_a_five_percent_bottom_margin(env, tmp_path):
    code, _ = _burn_style(env, tmp_path, aspect="16:9", probed=(1920, 1080))
    assert code == 0
    style = style_of(burn_vf(tmp_path))
    assert style["MarginV"] == "14"
    assert style["MarginL"] == style["MarginR"] == "19"


def test_captions_burn_infers_9x16_from_probed_size(env, tmp_path):
    code, _ = _burn_style(env, tmp_path, probed=(1080, 1920))
    assert code == 0
    assert style_of(burn_vf(tmp_path))["MarginV"] == "101"


def test_captions_burn_infers_16x9_and_1x1_from_probed_size(env, tmp_path):
    assert _burn_style(env, tmp_path, probed=(1920, 1080))[0] == 0
    assert style_of(burn_vf(tmp_path))["MarginV"] == "14"
    assert _burn_style(env, tmp_path, probed=(1080, 1080))[0] == 0
    assert style_of(burn_vf(tmp_path))["MarginV"] == "29"


def test_captions_burn_swaps_size_for_rotated_video(env, tmp_path):
    probed = (1920, 1080, ', "side_data_list": [{"rotation": -90}]')
    code, _ = _burn_style(env, tmp_path, probed=probed)
    assert code == 0
    assert style_of(burn_vf(tmp_path))["MarginV"] == "101"


def test_captions_burn_without_aspect_or_ffprobe_exits_2(env, tmp_path):
    code, payload = _burn_style(env, tmp_path)
    assert code == 2
    assert "--aspect" in payload["error"]
    assert not (tmp_path / "ffmpeg.argv").exists()
    assert payload["srt"].endswith("demo.srt")


def test_captions_burn_with_aspect_but_no_ffprobe_assumes_reference_size(env, tmp_path):
    code, _ = _burn_style(env, tmp_path, aspect="9:16")
    assert code == 0
    assert style_of(burn_vf(tmp_path))["MarginV"] == "101"


def test_captions_burn_aspect_that_contradicts_the_video_exits_2(env, tmp_path):
    code, payload = _burn_style(env, tmp_path, aspect="9:16", probed=(1920, 1080))
    assert code == 2
    assert "disagrees" in payload["error"]
    assert not (tmp_path / "ffmpeg.argv").exists()


def test_captions_rejects_unknown_aspect(env, tmp_path):
    code, payload = _burn_style(env, tmp_path, aspect="4:3")
    assert code == 2


def test_captions_burn_children_do_not_inherit_secrets(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Hi.", 0.0, 0.3)])
    envlog = tmp_path / "ffmpeg.env"
    body = (
        f'env >> "{envlog}"\n'
        'case "$*" in\n'
        "  *-filters*)\n"
        '    printf " T.. subtitles        V->V       Render.\\n"\n'
        "    exit 0;;\n"
        "esac\n"
        'for last; do :; done\n'
        'touch "$last"\n'
    )
    stub = make_stub(tmp_path / "bin" / "ffmpeg", body)
    video = tmp_path / "in.mp4"
    video.write_bytes(b"")
    env = dict(
        env,
        QUIRK_FFMPEG=str(stub),
        GEMINI_API_KEY="leak",
        GOOGLE_API_KEY="leak",
        ELEVENLABS_API_KEY="leak",
    )
    code, _, _ = captions(
        env,
        project,
        tmp_path,
        [{"id": "a", "start_s": 0}],
        "--burn",
        video,
        "--burned",
        tmp_path / "burned.mp4",
        "--aspect",
        "16:9",
    )
    assert code == 0
    logged = envlog.read_text()
    assert logged.count("PATH=") == 2
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ELEVENLABS_API_KEY"):
        assert name not in logged


def test_captions_burn_without_subtitles_filter_exits_3(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Hi.", 0.0, 0.3)])
    stub = fake_ffmpeg(tmp_path, with_subtitles=False)
    video = tmp_path / "in.mp4"
    video.write_bytes(b"")
    env = dict(env, QUIRK_FFMPEG=str(stub))
    code, payload, srt = captions(
        env,
        project,
        tmp_path,
        [{"id": "a", "start_s": 0}],
        "--burn",
        video,
        "--burned",
        tmp_path / "burned.mp4",
    )
    assert code == 3
    assert payload["fix"] == "brew install ffmpeg-full"
    assert not (tmp_path / "ffmpeg.argv").exists()


def test_captions_burn_finds_ffmpeg_full_through_brew_prefix(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Hi.", 0.0, 0.3)])
    prefix = tmp_path / "cellar" / "ffmpeg-full"
    stub = fake_ffmpeg(tmp_path)
    (prefix / "bin").mkdir(parents=True)
    stub.rename(prefix / "bin" / "ffmpeg")
    make_stub(tmp_path / "shim" / "brew", f'echo "{prefix}"\n')
    env = dict(env, PATH=f"{tmp_path / 'shim'}:/usr/bin:/bin")
    video = tmp_path / "in.mp4"
    video.write_bytes(b"")
    code, payload, _ = captions(
        env,
        project,
        tmp_path,
        [{"id": "a", "start_s": 0}],
        "--burn",
        video,
        "--burned",
        tmp_path / "burned.mp4",
        "--aspect",
        "16:9",
    )
    assert code == 0, payload
    assert (tmp_path / "ffmpeg.argv").exists()


def test_captions_burn_encoder_failure_exits_1(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Hi.", 0.0, 0.3)])
    stub = fake_ffmpeg(tmp_path, fail=True)
    video = tmp_path / "in.mp4"
    video.write_bytes(b"")
    env = dict(env, QUIRK_FFMPEG=str(stub))
    code, payload, _ = captions(
        env,
        project,
        tmp_path,
        [{"id": "a", "start_s": 0}],
        "--burn",
        video,
        "--burned",
        tmp_path / "burned.mp4",
        "--aspect",
        "16:9",
    )
    assert code == 1
    assert "encoder exploded" in payload["error"]


# ---------------------------------------------------------------- caption words from the script


def script_captions(env, tmp_path: Path, text: str, heard: "list[tuple[str, float, float]]", start: float = 0.0):
    project = make_project(tmp_path)
    write_words(project, "a", heard)
    code, payload, out = captions(env, project, tmp_path, [{"id": "a", "text": text, "start_s": start}])
    assert code == 0, payload
    return payload, out.read_text()


def test_captions_use_script_words_when_counts_match(env, tmp_path):
    payload, srt = script_captions(
        env,
        tmp_path,
        "Three: HyperFrames checks the file.",
        [("3.", 0.0, 0.4), ("Hyperframes", 0.5, 1.2), ("checks", 1.3, 1.6), ("the", 1.6, 1.7), ("file.", 1.7, 2.2)],
    )
    assert "Three: HyperFrames checks the file." in srt
    assert "3." not in srt and "Hyperframes" not in srt
    assert payload["text_mismatches"] == []


def test_captions_keep_whisper_timing_for_script_words(env, tmp_path):
    _, srt = script_captions(
        env, tmp_path, "Hello again.", [("Hello", 1.0, 1.4), ("again.", 1.5, 2.5)], start=2.0
    )
    (cue,) = parse_srt(srt)
    assert cue["start"] == pytest.approx(3.0) and cue["end"] == pytest.approx(4.5)
    assert cue["lines"] == ["Hello again."]


def test_captions_align_unequal_counts_and_report_unmatched_spans(env, tmp_path):
    payload, srt = script_captions(
        env,
        tmp_path,
        "Quirk makes plans. Then tests run quickly.",
        [
            ("Quirk", 0.0, 0.4),
            ("makes", 0.5, 0.8),
            ("plans.", 0.9, 1.4),
            ("Then", 2.0, 2.3),
            ("the", 2.3, 2.4),
            ("tests", 2.4, 2.8),
            ("run", 2.9, 3.1),
            ("quickly.", 3.2, 3.8),
        ],
    )
    assert "Then tests run quickly." not in srt
    assert [c["lines"] for c in parse_srt(srt)] == [["Quirk makes plans."], ["Then the tests run quickly."]]
    (miss,) = payload["text_mismatches"]
    assert miss == {"clip": "a", "script": "", "heard": "the", "at_s": 2.3}


def test_captions_fall_back_to_whisper_text_for_a_differing_span(env, tmp_path):
    payload, srt = script_captions(
        env,
        tmp_path,
        "Ship it tonight please",
        [("Ship", 0.0, 0.3), ("it", 0.3, 0.5), ("to", 0.5, 0.6), ("day", 0.6, 0.9), ("please", 1.0, 1.4)],
    )
    assert parse_srt(srt)[0]["lines"] == ["Ship it to day please"]
    (miss,) = payload["text_mismatches"]
    assert miss["script"] == "tonight" and miss["heard"] == "to day"


def test_captions_time_script_words_whisper_never_heard(env, tmp_path):
    payload, srt = script_captions(
        env,
        tmp_path,
        "One small step forward",
        [("One", 0.0, 0.4), ("step", 1.0, 1.4), ("forward", 1.5, 2.0)],
    )
    assert parse_srt(srt)[0]["lines"] == ["One small step forward"]
    (miss,) = payload["text_mismatches"]
    assert miss["script"] == "small" and miss["heard"] == ""
    assert 0.4 <= miss["at_s"] <= 1.0


def test_captions_merge_words_whisper_split_but_script_joined(env, tmp_path):
    payload, srt = script_captions(
        env,
        tmp_path,
        "Use the making-videos skill now",
        [("Use", 0.0, 0.2), ("the", 0.2, 0.3), ("making", 0.3, 0.6), ("videos", 0.6, 0.9), ("skill", 1.0, 1.3), ("now", 1.3, 1.6)],
    )
    assert parse_srt(srt)[0]["lines"] == ["Use the making-videos skill now"]
    assert payload["text_mismatches"] == []


def test_captions_without_script_text_use_the_heard_words(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Hello", 0.0, 0.4), ("3.", 0.5, 0.9)])
    code, payload, out = captions(env, project, tmp_path, [{"id": "a", "start_s": 0}])
    assert code == 0
    assert parse_srt(out.read_text())[0]["lines"] == ["Hello 3."]
    assert payload["text_mismatches"] == []


# ---------------------------------------------------------------- burned caption font


def make_ttf(path: Path, full_name: str) -> Path:
    """A minimal sfnt file whose only table is a name table holding ``full_name`` as name ID 4."""
    raw = full_name.encode("utf-16-be")
    table = struct.pack(">HHH", 0, 1, 18) + struct.pack(">HHHHHH", 3, 1, 0x409, 4, len(raw), 0) + raw
    header = struct.pack(">IHHHH", 0x00010000, 1, 16, 0, 0) + struct.pack(">4sIII", b"name", 0, 28, len(table))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + table)
    return path


def burn_with_brand(env, tmp_path, fonts: object, make_files=()):
    brand = {"product": "acme", "voice": {"engine": "kokoro", "id": "af_heart"}, "fonts": fonts}
    project = make_project(tmp_path, brand=brand)
    brand_dir = tmp_path / "studio" / "brands" / "acme"
    for name, full_name in make_files:
        make_ttf(brand_dir / name, full_name)
    write_words(project, "a", [("Hi.", 0.0, 0.3)])
    stub = fake_ffmpeg(tmp_path)
    args, _ = burn_args(tmp_path, "--aspect", "9:16")
    code, payload, err = run_voice_captions(dict(env, QUIRK_FFMPEG=str(stub)), project, tmp_path, args)
    assert code == 0, payload
    return burn_vf(tmp_path), err, brand_dir


def run_voice_captions(env, project, tmp_path, extra):
    lines = write_json(tmp_path / "caption-lines.json", [{"id": "a", "start_s": 0}])
    return run_voice(
        "captions", "--project", project, "--lines", lines, "--out", tmp_path / "out" / "demo.srt", *extra, env=env
    )


def test_burn_uses_the_brand_font_file_and_its_full_name(env, tmp_path):
    fonts = {"display": {"family": "Outfit", "files": ["fonts/Outfit-SemiBold.ttf"]}}
    vf, _, brand_dir = burn_with_brand(env, tmp_path, fonts, [("fonts/Outfit-SemiBold.ttf", "Outfit SemiBold")])
    assert f":fontsdir={brand_dir / 'fonts'}:" in vf.replace("\\", "")
    assert style_of(vf)["FontName"] == "Outfit SemiBold"


def test_burn_prefers_a_text_font_over_mono_and_mono_last(env, tmp_path):
    fonts = {
        "mono": {"family": "Plex Mono", "files": ["fonts/Mono.ttf"]},
        "display": {"family": "Outfit", "files": ["fonts/Display.ttf"]},
        "text": {"family": "Inter", "files": ["fonts/Text.ttf"]},
    }
    files = [("fonts/Mono.ttf", "Plex Mono"), ("fonts/Display.ttf", "Outfit"), ("fonts/Text.ttf", "Inter")]
    vf, _, _ = burn_with_brand(env, tmp_path, fonts, files)
    assert style_of(vf)["FontName"] == "Inter"


def test_burn_falls_to_mono_when_it_is_the_only_font(env, tmp_path):
    fonts = {"mono": {"family": "Plex Mono", "files": ["fonts/Mono.ttf"]}}
    vf, _, _ = burn_with_brand(env, tmp_path, fonts, [("fonts/Mono.ttf", "Plex Mono")])
    assert style_of(vf)["FontName"] == "Plex Mono"


def test_burn_uses_the_brand_family_when_the_file_has_no_readable_name(env, tmp_path):
    fonts = {"display": {"family": "Outfit", "files": ["fonts/Broken.ttf"]}}
    brand_dir = tmp_path / "studio" / "brands" / "acme" / "fonts"
    brand_dir.mkdir(parents=True)
    (brand_dir / "Broken.ttf").write_bytes(b"not a font")
    vf, _, _ = burn_with_brand(env, tmp_path, fonts)
    assert style_of(vf)["FontName"] == "Outfit"


def test_burn_without_a_font_file_keeps_the_default_and_says_so(env, tmp_path):
    fonts = {"display": {"family": "Outfit", "files": ["fonts/Missing.ttf"]}}
    vf, err, _ = burn_with_brand(env, tmp_path, fonts)
    assert "fontsdir" not in vf and "FontName" not in vf
    assert "default font" in err


def test_burn_with_an_empty_files_list_keeps_the_default_and_says_so(env, tmp_path):
    vf, err, _ = burn_with_brand(env, tmp_path, {"display": {"family": "Outfit", "files": []}})
    assert "fontsdir" not in vf
    assert "default font" in err


# ---------------------------------------------------------------- worker logic


@pytest.fixture()
def worker():
    pytest.importorskip("numpy")
    spec = importlib.util.spec_from_file_location("mv_voice_worker_under_test", WORKER_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worker_apply_patches_rewrites_every_occurrence(worker):
    patches = {
        "quirk": {"from": "kwˈɜːk", "to": "kwˈɜɹk"},
        "other": {"from": "ab", "to": "cd"},
    }
    assert worker.apply_patches("kwˈɜːk ab kwˈɜːk", patches) == "kwˈɜɹk cd kwˈɜɹk"


def test_worker_apply_patches_without_patches_is_identity(worker):
    assert worker.apply_patches("həlˈO", {}) == "həlˈO"


def test_worker_words_from_segments_rounds_and_strips(worker):
    seg = SimpleNamespace(
        words=[
            SimpleNamespace(word=" Hello", start=0.12345, end=0.5),
            SimpleNamespace(word=" there.", start=0.5004, end=1.0),
        ]
    )
    other = SimpleNamespace(words=[SimpleNamespace(word=" more", start=1.2, end=1.4)])
    assert worker.words_from_segments([seg, other]) == [
        {"text": "Hello", "start": 0.123, "end": 0.5},
        {"text": "there.", "start": 0.5, "end": 1.0},
        {"text": "more", "start": 1.2, "end": 1.4},
    ]


def test_worker_words_json_path_replaces_wav_suffix(worker):
    assert worker.words_path("/a/b/intro.wav") == Path("/a/b/intro.words.json")


# ---------------------------------------------------------------- clip loudness


@pytest.fixture()
def stdlib_worker():
    spec = importlib.util.spec_from_file_location("mv_voice_worker_stdlib_under_test", WORKER_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_clip_measures_then_applies_a_linear_gain(stdlib_worker, tmp_path):
    log = tmp_path / "ffmpeg.log"
    body = (
        f'echo "$@" >> "{log}"\n'
        "cat >&2 <<'EOF'\n"
        '{"input_i": "-27.50", "input_tp": "-9.00", "input_lra": "1.00", "input_thresh": "-38.00",'
        ' "target_offset": "0.20", "normalization_type": "linear"}\n'
        "EOF\n"
        'for last; do :; done\n'
        '[ "$last" = "-" ] || touch "$last"\n'
    )
    stub = make_stub(tmp_path / "bin" / "ffmpeg", body)
    raw = tmp_path / "a.raw.wav"
    raw.write_bytes(b"")
    out = tmp_path / "a.wav"
    levels = stdlib_worker.normalize_clip(str(stub), raw, out, 24000)
    assert out.exists() and sorted(p.name for p in tmp_path.iterdir()) == ["a.raw.wav", "a.wav", "bin", "ffmpeg.log"]
    measure, apply, check = [line.split() for line in log.read_text().splitlines()]
    assert "measured_I" not in " ".join(measure)
    filt = apply[apply.index("-af") + 1]
    assert filt.startswith("acompressor=") and "alimiter=" in filt
    assert "I=-16.0" in filt and "linear=true" in filt
    assert "measured_I=-27.50" in filt and "measured_TP=-9.00" in filt and "offset=0.20" in filt
    assert "acompressor" not in check[check.index("-af") + 1]


def test_normalize_clip_reports_an_ffmpeg_failure(stdlib_worker, tmp_path):
    stub = make_stub(tmp_path / "bin" / "ffmpeg", "echo 'no such filter' >&2\nexit 1\n")
    raw = tmp_path / "a.raw.wav"
    raw.write_bytes(b"")
    with pytest.raises(RuntimeError, match="no such filter"):
        stdlib_worker.normalize_clip(str(stub), raw, tmp_path / "a.wav", 24000)
    assert not (tmp_path / "a.wav").exists()


def _measuring_stub(tmp_path: Path, input_i: str, input_tp: str, offset: str) -> Path:
    body = (
        f'echo "$@" >> "{tmp_path}/ffmpeg.log"\n'
        "cat >&2 <<'EOF'\n"
        f'{{"input_i": "{input_i}", "input_tp": "{input_tp}", "input_lra": "0.00", "input_thresh": "-70.00",'
        f' "target_offset": "{offset}", "normalization_type": "linear"}}\n'
        "EOF\n"
        'for last; do :; done\n'
        '[ "$last" = "-" ] || touch "$last"\n'
    )
    return make_stub(tmp_path / "bin" / "ffmpeg", body)


def test_normalize_clip_skips_loudnorm_when_the_measurement_is_not_finite(stdlib_worker, tmp_path):
    stub = _measuring_stub(tmp_path, "-inf", "-14.00", "inf")
    raw = tmp_path / "a.raw.wav"
    raw.write_bytes(b"")
    out = tmp_path / "a.wav"
    levels = stdlib_worker.normalize_clip(str(stub), raw, out, 24000)
    assert levels["normalization"] == "skipped_short"
    assert levels["reason"]
    assert levels["lufs"] is None and levels["true_peak_dbtp"] == -14.0
    assert out.exists()
    json.dumps(levels, allow_nan=False)
    passes = (tmp_path / "ffmpeg.log").read_text().splitlines()
    assert "measured_I" not in " ".join(passes)
    leveled = passes[1].split()
    assert leveled[leveled.index("-af") + 1] == stdlib_worker.LEVELING_CHAIN


def test_normalize_clip_survives_a_silent_clip(stdlib_worker, tmp_path):
    stub = _measuring_stub(tmp_path, "-inf", "-inf", "inf")
    raw = tmp_path / "s.raw.wav"
    raw.write_bytes(b"")
    levels = stdlib_worker.normalize_clip(str(stub), raw, tmp_path / "s.wav", 24000)
    assert levels["normalization"] == "skipped_short"
    assert levels["lufs"] is None and levels["true_peak_dbtp"] is None
    assert (tmp_path / "s.wav").exists()


def test_normalize_clip_keeps_clips_whose_ids_look_like_temporary_names(stdlib_worker, tmp_path):
    stub = _measuring_stub(tmp_path, "-16.00", "-3.00", "0.10")
    for order in (("a.norm-tmp", "a"), ("a", "a.norm-tmp")):
        voice = tmp_path / "-".join(order)
        voice.mkdir()
        for clip in order:
            raw = voice / f"{clip}.raw.wav"
            raw.write_bytes(b"")
            stdlib_worker.normalize_clip(str(stub), raw, voice / f"{clip}.wav", 24000)
        assert (voice / "a.wav").exists() and (voice / "a.norm-tmp.wav").exists()
        assert sorted(p.name for p in voice.iterdir()) == sorted(
            ["a.raw.wav", "a.wav", "a.norm-tmp.raw.wav", "a.norm-tmp.wav"]
        )


def test_normalize_clip_reports_a_missing_ffmpeg(stdlib_worker, tmp_path):
    raw = tmp_path / "a.raw.wav"
    raw.write_bytes(b"")
    with pytest.raises(stdlib_worker.MissingTool):
        stdlib_worker.normalize_clip(str(tmp_path / "nope" / "ffmpeg"), raw, tmp_path / "a.wav", 24000)


def _real_ffmpeg() -> "str | None":
    path = shutil.which("ffmpeg")
    if not path:
        return None
    filters = subprocess.run([path, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return path if all(name in filters for name in ("loudnorm", "alimiter", "acompressor")) else None


def _speechlike(ffmpeg: str, out: Path, seconds: float, seed: int) -> None:
    """Pink noise gated into syllable bursts with a few loud transients, as peaky as Kokoro output."""
    chain = (
        f"anoisesrc=d={seconds}:c=pink:r=24000:seed={seed},volume=0.05,"
        "tremolo=f=4:d=0.95,volume='1+8*lt(mod(t,1.7),0.01)':eval=frame"
    )
    subprocess.run([ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", chain, "-c:a", "pcm_s16le", str(out)], check=True)


def _ebur128(ffmpeg: str, path: Path) -> "tuple[float, float]":
    err = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True,
        text=True,
    ).stderr
    summary = err[err.rindex("Summary") :]
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1)), float(
        re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary).group(1)
    )


@pytest.mark.skipif(_real_ffmpeg() is None, reason="needs an ffmpeg with loudnorm, alimiter and acompressor")
def test_normalized_clips_mix_to_minus_16_lufs_at_unity_gain(stdlib_worker, tmp_path):
    ffmpeg = _real_ffmpeg()
    starts = [0.3, 4.2, 8.9]
    clips = []
    for i, _ in enumerate(starts):
        raw = tmp_path / f"c{i}.raw.wav"
        _speechlike(ffmpeg, raw, 3.2 + i * 0.4, seed=i + 1)
        wav = tmp_path / f"c{i}.wav"
        levels = stdlib_worker.normalize_clip(ffmpeg, raw, wav, 24000)
        assert levels["lufs"] == pytest.approx(-16, abs=0.5), levels
        assert levels["true_peak_dbtp"] <= -1.5, levels
        measured, _ = _ebur128(ffmpeg, wav)
        assert measured == pytest.approx(levels["lufs"], abs=0.3)
        clips.append(wav)
    argv = [ffmpeg, "-y", "-v", "error"]
    for wav in clips:
        argv += ["-i", str(wav)]
    graph = ";".join(f"[{i}:a]aresample=48000,adelay={int(s * 1000)}[a{i}]" for i, s in enumerate(starts))
    graph += ";" + "".join(f"[a{i}]" for i in range(len(clips))) + f"amix=inputs={len(clips)}:normalize=0[m]"
    mix = tmp_path / "mix.wav"
    subprocess.run(argv + ["-filter_complex", graph, "-map", "[m]", str(mix)], check=True)
    loudness, _ = _ebur128(ffmpeg, mix)
    assert loudness == pytest.approx(-16, abs=1.0)


@pytest.mark.skipif(_real_ffmpeg() is None, reason="needs an ffmpeg with loudnorm, alimiter and acompressor")
def test_real_ffmpeg_normalizes_a_clip_shorter_than_the_gating_window(stdlib_worker, tmp_path):
    ffmpeg = _real_ffmpeg()
    raw = tmp_path / "short.raw.wav"
    subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.2:sample_rate=24000",
         "-c:a", "pcm_s16le", str(raw)],
        check=True,
    )
    levels = stdlib_worker.normalize_clip(ffmpeg, raw, tmp_path / "short.wav", 24000)
    assert levels["normalization"] == "skipped_short"
    assert (tmp_path / "short.wav").stat().st_size > 44


@pytest.mark.skipif(_real_ffmpeg() is None, reason="needs an ffmpeg with loudnorm, alimiter and acompressor")
def test_real_ffmpeg_normalizes_a_silent_clip(stdlib_worker, tmp_path):
    ffmpeg = _real_ffmpeg()
    raw = tmp_path / "quiet.raw.wav"
    subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "2",
         "-c:a", "pcm_s16le", str(raw)],
        check=True,
    )
    levels = stdlib_worker.normalize_clip(ffmpeg, raw, tmp_path / "quiet.wav", 24000)
    assert levels["normalization"] == "skipped_short"
    assert levels["lufs"] is None
