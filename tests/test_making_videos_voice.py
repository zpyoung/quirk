"""Tests for the making-videos narration launcher, caption builder and Kokoro/whisper worker."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
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
    env = dict(env, GEMINI_API_KEY="leak", GOOGLE_API_KEY="leak", ELEVENLABS_API_KEY="leak")
    code, out, _ = run_voice("say", "--project", project, "--lines", lines, env=env)
    assert code == 0
    assert out == json.loads(reply)
    argv = (tmp_path / "worker.log.argv").read_text().split()
    assert argv[0] == str(WORKER_PY)
    assert argv[1] == "say"
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
    code, _, _ = run_voice("say", "--project", project, "--lines", lines, env=env)
    assert code == 0
    raw = (tmp_path / "worker.log.argv").read_text()
    argv = raw.split(" --pronunciations ", 1)[1].strip()
    assert json.loads(argv) == {"quirk": {"from": "kwˈɜːk", "to": "kwˈɜɹk"}}


def test_say_explicit_voice_wins(env, tmp_path):
    project = make_project(tmp_path)
    lines = write_json(tmp_path / "lines.json", [{"id": "a", "text": "Hi.", "start_s": 0}])
    fake_venv_python(tmp_path, json.dumps({"clips": []}))
    code, _, _ = run_voice("say", "--project", project, "--lines", lines, "--voice", "bf_emma", env=env)
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
    lines = write_json(tmp_path / "lines.json", [{"id": "../evil", "text": "Hi.", "start_s": 0}])
    fake_venv_python(tmp_path, json.dumps({"clips": []}))
    code, out, _ = run_voice("say", "--project", project, "--lines", lines, env=env)
    assert code == 1
    assert "id" in out["error"]


def test_say_worker_failure_exits_1_with_stderr_tail(env, tmp_path):
    project = make_project(tmp_path)
    lines = write_json(tmp_path / "lines.json", [{"id": "a", "text": "Hi.", "start_s": 0}])
    make_stub(
        tmp_path / "cache" / "venv" / "bin" / "python",
        "echo 'kokoro model missing' >&2\nexit 7\n",
    )
    code, out, _ = run_voice("say", "--project", project, "--lines", lines, env=env)
    assert code == 1
    assert "kokoro model missing" in out["error"]


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
            {"id": "a", "text": "x", "start_s": 0},
            {"id": "b", "text": "x", "start_s": 3.0},
            {"id": "c", "text": "x", "start_s": 6.0},
        ],
    )
    assert code == 0
    assert payload == {"srt": str(out), "burned": None}
    assert out.read_text() == (
        "1\n00:00:00,000 --> 00:00:01,600\nHello there, friend.\n\n"
        "2\n00:00:03,000 --> 00:00:04,000\nSecond clip.\n\n"
        "3\n00:00:06,000 --> 00:00:07,000\nHi.\n"
    )


def test_captions_extends_short_cue_only_up_to_next_cue(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Wow.", 0.0, 0.3), ("Next", 0.8, 1.4), ("one.", 1.5, 2.2)])
    code, _, out = captions(env, project, tmp_path, [{"id": "a", "text": "x", "start_s": 10.0}])
    assert code == 0
    cues = parse_srt(out.read_text())
    assert [(c["start"], c["end"]) for c in cues] == [(10.0, 10.8), (10.8, 12.2)]


def test_captions_timestamps_use_hours_and_milliseconds(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Late.", 0.25, 1.5)])
    code, _, out = captions(env, project, tmp_path, [{"id": "a", "text": "x", "start_s": 3723.0}])
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
    lines = [{"id": "a", "text": "x", "start_s": 0.0}, {"id": "b", "text": "x", "start_s": 200.0}]
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
    code, _, out = captions(env, project, tmp_path, [{"id": "a", "text": "x", "start_s": 0}])
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
    code, _, out = captions(env, project, tmp_path, [{"id": "a", "text": "x", "start_s": 0}])
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
        [{"id": "a", "text": "x", "start_s": 0}, {"id": "b", "text": "x", "start_s": 0.5}],
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
        [{"id": "a", "text": "x", "start_s": 0}, {"id": "b", "text": "x", "start_s": 0.5}],
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
    code, _, out = captions(env, project, tmp_path, [{"id": "a", "text": "x", "start_s": 0}])
    assert code == 0
    (cue,) = parse_srt(out.read_text())
    assert cue["lines"] == ["x" * 41 + "-", "x" * 9]


def test_captions_breaks_very_long_word_across_cues(env, tmp_path):
    project = make_project(tmp_path)
    token = "y" * 130
    write_words(project, "a", [(token, 0.0, 12.0)])
    code, _, out = captions(env, project, tmp_path, [{"id": "a", "text": "x", "start_s": 0}])
    assert code == 0
    cues = parse_srt(out.read_text())
    lines = [line for cue in cues for line in cue["lines"]]
    assert all(len(line) <= 42 for line in lines)
    assert all(len(cue["lines"]) <= 2 for cue in cues)
    assert "".join(line.rstrip("-") for line in lines) == token


def test_captions_missing_words_json_exits_1(env, tmp_path):
    project = make_project(tmp_path)
    code, out, _ = captions(env, project, tmp_path, [{"id": "a", "text": "x", "start_s": 0}])
    assert code == 1
    assert "align" in out["error"]


def test_captions_burn_requires_burned(env, tmp_path):
    project = make_project(tmp_path)
    write_words(project, "a", [("Hi.", 0.0, 0.3)])
    code, out, _ = captions(
        env, project, tmp_path, [{"id": "a", "text": "x", "start_s": 0}], "--burn", tmp_path / "in.mp4"
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
        [{"id": "a", "text": "x", "start_s": 0}],
        "--burn",
        video,
        "--burned",
        burned,
    )
    assert code == 0
    assert payload == {"srt": str(srt), "burned": str(burned)}
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
        [{"id": "a", "text": "x", "start_s": 0}],
        "--burn",
        video,
        "--burned",
        tmp_path / "burned.mp4",
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
        [{"id": "a", "text": "x", "start_s": 0}],
        "--burn",
        video,
        "--burned",
        tmp_path / "burned.mp4",
    )
    assert code == 3
    assert payload["fix"] == "brew install ffmpeg-full"
    assert not (tmp_path / "ffmpeg.argv").exists()


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
        [{"id": "a", "text": "x", "start_s": 0}],
        "--burn",
        video,
        "--burned",
        tmp_path / "burned.mp4",
    )
    assert code == 1
    assert "encoder exploded" in payload["error"]


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
