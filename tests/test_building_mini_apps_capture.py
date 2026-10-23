"""capture.py contracts: preflight, search and video, driven by fake yt-dlp and ffmpeg executables.

No network. The only test that needs a real ffmpeg is guarded by a skipif.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "building-mini-apps"
CAPTURE = SKILL_DIR / "scripts" / "capture.py"

FAKE_YTDLP = """#!{python}
import json, os, sys
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps(["yt-dlp"] + args) + "\\n")
if os.environ.get("FAKE_YTDLP_FAIL"):
    print("ERROR: fake download failure", file=sys.stderr)
    sys.exit(1)
if "--print" in args:
    print("abc123|Sentry in 10 minutes|Some Channel|20260101|600")
    print("def456|Sentry review|Other Channel|20251201|900")
    sys.exit(0)
template = args[args.index("-o") + 1]
out = Path(template.replace("%(ext)s", "mp4"))
out.parent.mkdir(parents=True, exist_ok=True)
source = os.environ.get("FAKE_VIDEO_SOURCE")
if source:
    out.write_bytes(Path(source).read_bytes())
else:
    out.write_bytes(b"fake video")
"""

FAKE_FFMPEG = """#!{python}
import json, os, sys
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps(["ffmpeg"] + args) + "\\n")
if os.environ.get("FAKE_FFMPEG_FAIL"):
    print("fake ffmpeg exploded", file=sys.stderr)
    sys.exit(1)
vf = args[args.index("-vf") + 1]
times = os.environ["FAKE_FPS_TIMES" if "fps=1" in vf else "FAKE_SCENE_TIMES"]
times = [t for t in times.split(",") if t]
pattern = args[-1]
print("ffmpeg version fake", file=sys.stderr)
for n, t in enumerate(times):
    print(f"[Parsed_showinfo_1 @ 0x1] n:   {{n}} pts:  {{n}} pts_time:{{t}}       fmt:yuv420p", file=sys.stderr)
    Path(pattern % (n + 1)).write_bytes(b"png " + t.encode())
"""


def _copy_skill(dest: Path) -> Path:
    """Copy the skill tree; scripts anchor on their own location, so the copy is self-contained."""
    target = dest / "building-mini-apps"
    shutil.copytree(SKILL_DIR, target, ignore=shutil.ignore_patterns("node_modules", "media"))
    return target


def _write_exe(path: Path, template: str) -> Path:
    path.write_text(template.format(python=sys.executable))
    path.chmod(0o755)
    return path


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)


class Rig:
    """A copied skill inside a git repo, with fake tools wired through the env overrides."""

    def __init__(self, tmp_path: Path) -> None:
        _git_init(tmp_path)
        self.skill = _copy_skill(tmp_path)
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.log = tmp_path / "calls.log"
        self.ytdlp = _write_exe(self.bin / "yt-dlp", FAKE_YTDLP)
        self.ffmpeg = _write_exe(self.bin / "ffmpeg", FAKE_FFMPEG)
        self.playwright = _write_exe(self.bin / "playwright-cli", "#!{python}\n")
        self.env: Dict[str, str] = {
            "CAPTURE_YTDLP": str(self.ytdlp),
            "CAPTURE_FFMPEG": str(self.ffmpeg),
            "CAPTURE_PLAYWRIGHT": str(self.playwright),
            "FAKE_LOG": str(self.log),
            "FAKE_SCENE_TIMES": "0.0,3.2,3.9,42.7,90.1,200.5",
            "FAKE_FPS_TIMES": "0,1,2,3,4,5,6",
        }

    def run(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        full = {**os.environ, **self.env, **env}
        return subprocess.run(
            [sys.executable, str(self.skill / "scripts" / "capture.py"), *args],
            env=full, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
        )

    def calls(self) -> List[List[str]]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def media(self, app: str = "sentry") -> Path:
        return self.skill / "references" / "media" / app


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


def _frames(media: Path) -> List[str]:
    return sorted(p.name for p in media.glob("*.png"))


# --- usage errors ---


@pytest.mark.parametrize("source_id", ["X1", "s1", "S", "S1a", "1", ""])
def test_video_rejects_a_bad_source_id_before_any_tool_runs(rig: Rig, source_id: str) -> None:
    result = rig.run("video", "sentry", source_id, "https://example.invalid")
    assert result.returncode == 2
    assert rig.calls() == []
    assert not rig.media().exists()


@pytest.mark.parametrize("app", ["Sentry", "-sentry", "../etc", "a b", "a/b"])
def test_app_names_must_match_the_name_regex(rig: Rig, app: str) -> None:
    assert rig.run("video", app, "S1", "https://example.invalid").returncode == 2
    assert rig.run("search", app).returncode == 2
    assert rig.calls() == []


def test_missing_subcommand_and_bad_numbers_exit_2(rig: Rig) -> None:
    assert rig.run().returncode == 2
    assert rig.run("search", "sentry", "--limit", "0").returncode == 2
    assert rig.run("video", "sentry", "S1", "u", "--threshold", "1.5").returncode == 2
    assert rig.run("video", "sentry", "S1", "u", "--threshold", "abc").returncode == 2


# --- preflight ---


def test_preflight_passes_with_every_check_listed(rig: Rig) -> None:
    result = rig.run("preflight")
    assert result.returncode == 0, result.stdout + result.stderr
    out = result.stdout
    for needle in ("git", "references", "yt-dlp", "ffmpeg", "playwright-cli"):
        assert needle in out
    assert "FAIL" not in out


def test_preflight_names_a_missing_tool(rig: Rig) -> None:
    result = rig.run("preflight", CAPTURE_FFMPEG=str(rig.bin / "no-such-ffmpeg"))
    assert result.returncode == 1
    fail_lines = [line for line in result.stdout.splitlines() if "FAIL" in line]
    assert len(fail_lines) == 1
    assert "ffmpeg" in fail_lines[0]


def test_preflight_names_a_non_git_skill_root(tmp_path: Path) -> None:
    skill = _copy_skill(tmp_path)
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(tmp_path.parent)}
    for name in ("CAPTURE_YTDLP", "CAPTURE_FFMPEG", "CAPTURE_PLAYWRIGHT"):
        tool = tmp_path / name
        _write_exe(tool, "#!{python}\n")
        env[name] = str(tool)
    result = subprocess.run(
        [sys.executable, str(skill / "scripts" / "capture.py"), "preflight"],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
    )
    assert result.returncode == 1
    fail_lines = [line for line in result.stdout.splitlines() if "FAIL" in line]
    assert len(fail_lines) == 1
    assert "git" in fail_lines[0]
    assert "quirk checkout" in fail_lines[0]
    assert "installed plugin" in fail_lines[0]


def test_preflight_fails_when_references_is_not_writable(rig: Rig) -> None:
    references = rig.skill / "references"
    references.chmod(0o555)
    try:
        if os.access(references, os.W_OK):
            pytest.skip("running as a user that ignores directory modes")
        result = rig.run("preflight")
    finally:
        references.chmod(0o755)
    assert result.returncode == 1
    assert any("FAIL" in line and "references" in line for line in result.stdout.splitlines())


# --- search ---


def test_search_prints_ytdlp_lines_unchanged_with_defaults(rig: Rig) -> None:
    result = rig.run("search", "sentry")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "abc123|Sentry in 10 minutes|Some Channel|20260101|600",
        "def456|Sentry review|Other Channel|20251201|900",
    ]
    (call,) = rig.calls()
    year = str(__import__("datetime").date.today().year)
    assert f"ytsearch8:sentry app walkthrough {year}" in call
    assert "--flat-playlist" in call
    assert "%(id)s|%(title)s|%(channel)s|%(upload_date)s|%(duration)s" in call


def test_search_honours_query_and_limit(rig: Rig) -> None:
    result = rig.run("search", "sentry", "--query", "sentry issues tour", "--limit", "3")
    assert result.returncode == 0
    (call,) = rig.calls()
    assert "ytsearch3:sentry issues tour" in call


def test_search_failure_exits_1(rig: Rig) -> None:
    result = rig.run("search", "sentry", FAKE_YTDLP_FAIL="1")
    assert result.returncode == 1
    assert "yt-dlp" in result.stderr


# --- video ---


def test_video_names_frames_by_whole_second_and_keeps_the_first_per_second(rig: Rig) -> None:
    result = rig.run("video", "sentry", "S1", "https://example.invalid/v")
    assert result.returncode == 0, result.stdout + result.stderr
    # 3.2 and 3.9 share second 3; the first (3.2) wins
    expected = ["S1-t0000.png", "S1-t0003.png", "S1-t0042.png", "S1-t0090.png", "S1-t0200.png"]
    assert _frames(rig.media()) == expected
    assert result.stdout.splitlines() == [f"references/media/sentry/{n}" for n in expected]
    assert (rig.media() / "S1-t0003.png").read_bytes() == b"png 3.2"


def test_video_downloads_at_720p_or_lower_and_scene_detects_at_the_threshold(rig: Rig) -> None:
    rig.run("video", "sentry", "S1", "https://example.invalid/v", "--threshold", "0.45")
    ytdlp, ffmpeg = rig.calls()
    assert ytdlp[ytdlp.index("-f") + 1] == "bv*[height<=720][ext=mp4]/b[height<=720]"
    assert "https://example.invalid/v" in ytdlp
    vf = ffmpeg[ffmpeg.index("-vf") + 1]
    assert "select='gt(scene,0.45)'" in vf
    assert "showinfo" in vf
    assert "scale=1280:-1" in vf


def test_video_deletes_the_video_folder_after_success(rig: Rig) -> None:
    assert rig.run("video", "sentry", "S1", "https://example.invalid/v").returncode == 0
    assert not (rig.media() / "_video").exists()


def test_video_deletes_the_video_folder_after_a_failing_download(rig: Rig) -> None:
    result = rig.run("video", "sentry", "S1", "https://example.invalid/v", FAKE_YTDLP_FAIL="1")
    assert result.returncode == 1
    assert "download" in result.stderr
    assert not (rig.media() / "_video").exists()
    assert _frames(rig.media()) == []


def test_video_deletes_the_video_folder_after_a_failing_extraction(rig: Rig) -> None:
    result = rig.run("video", "sentry", "S1", "https://example.invalid/v", FAKE_FFMPEG_FAIL="1")
    assert result.returncode == 1
    assert "ffmpeg" in result.stderr
    assert not (rig.media() / "_video").exists()
    assert _frames(rig.media()) == []


def test_video_reruns_at_one_fps_when_scene_detection_finds_under_five(rig: Rig) -> None:
    result = rig.run("video", "sentry", "S2", "https://example.invalid/v", FAKE_SCENE_TIMES="0,7.5")
    assert result.returncode == 0, result.stderr
    assert _frames(rig.media()) == [f"S2-t000{n}.png" for n in range(7)]
    filters = [c[c.index("-vf") + 1] for c in rig.calls() if c[0] == "ffmpeg"]
    assert len(filters) == 2
    assert "gt(scene" in filters[0]
    assert filters[1].startswith("fps=1") and "showinfo" in filters[1]
    # the scene frame at second 7 was replaced, not kept beside the fps frames
    assert not (rig.media() / "S2-t0007.png").exists()


def test_video_keeps_scene_frames_at_exactly_five(rig: Rig) -> None:
    result = rig.run("video", "sentry", "S1", "u", FAKE_SCENE_TIMES="1,2,3,4,5")
    assert result.returncode == 0
    assert len([c for c in rig.calls() if c[0] == "ffmpeg"]) == 1
    assert len(_frames(rig.media())) == 5


def test_video_fails_when_no_frames_come_out(rig: Rig) -> None:
    result = rig.run("video", "sentry", "S1", "u", FAKE_SCENE_TIMES="", FAKE_FPS_TIMES="")
    assert result.returncode == 1
    assert "no frames" in result.stderr
    assert not (rig.media() / "_video").exists()


def test_video_never_overwrites_or_touches_other_sources_frames(rig: Rig) -> None:
    media = rig.media()
    media.mkdir(parents=True)
    other = media / "S3-t0042.png"
    other.write_bytes(b"other source")
    note = media / "notes.txt"
    note.write_text("keep me")
    stale = media / "S1-t9999.png"
    stale.write_bytes(b"stale same-source frame")
    outside = rig.skill / "references" / "apps" / "linear.md"
    before = outside.read_bytes()

    assert rig.run("video", "sentry", "S1", "u").returncode == 0

    assert other.read_bytes() == b"other source"
    assert note.read_text() == "keep me"
    assert not stale.exists()
    assert outside.read_bytes() == before
    assert (media / "S1-t0042.png").exists()


def test_video_reports_a_missing_tool_before_creating_anything(rig: Rig) -> None:
    result = rig.run("video", "sentry", "S1", "u", CAPTURE_FFMPEG=str(rig.bin / "missing"))
    assert result.returncode == 1
    assert "ffmpeg" in result.stderr
    assert not rig.media().exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs a real ffmpeg")
def test_video_names_frames_from_real_ffmpeg_showinfo_output(rig: Rig, tmp_path: Path) -> None:
    sample = tmp_path / "sample.mp4"
    made = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
         "color=red:s=320x240:d=2:r=10[a];color=blue:s=320x240:d=2:r=10[b];"
         "color=green:s=320x240:d=2:r=10[c];[a][b][c]concat=n=3:v=1:a=0", str(sample)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
    )
    assert made.returncode == 0, made.stderr
    real_ffmpeg = shutil.which("ffmpeg")
    assert real_ffmpeg is not None

    result = rig.run(
        "video", "sentry", "S1", "u",
        CAPTURE_FFMPEG=real_ffmpeg, FAKE_VIDEO_SOURCE=str(sample),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # three solid colours give 2 scene cuts, so the fps=1 rerun supplies the frames
    assert _frames(rig.media()) == [f"S1-t000{n}.png" for n in range(6)]
    assert not (rig.media() / "_video").exists()


# --- concurrent runs and frame ordering ---


def _load_capture(skill: Path, name: str) -> ModuleType:
    """Import the copied capture.py so SKILL_ROOT and MEDIA_DIR anchor inside the rig."""
    spec = importlib.util.spec_from_file_location(name, skill / "scripts" / "capture.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_video_runs_for_different_sources_do_not_delete_each_others_scratch(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    for key, value in rig.env.items():
        monkeypatch.setenv(key, value)
    capture = _load_capture(rig.skill, "capture_interleave")
    real_run = capture.run
    scratch = rig.media() / "_video"
    state = {"nested": False, "s1_video_survived": False}

    def interleaving_run(cmd):
        is_first_ffmpeg = Path(cmd[0]).name == "ffmpeg" and not state["nested"]
        if is_first_ffmpeg:
            # S1 has downloaded and is about to extract; S2 now runs start to finish
            state["nested"] = True
            other = capture.main(["video", "sentry", "S2", "https://example.invalid/two"])
            assert other == 0
            state["s1_video_survived"] = (scratch / "S1" / "S1.mp4").is_file()
        return real_run(cmd)

    monkeypatch.setattr(capture, "run", interleaving_run)
    assert capture.main(["video", "sentry", "S1", "https://example.invalid/one"]) == 0

    assert state["s1_video_survived"], "S2's run removed S1's downloaded video"
    names = _frames(rig.media())
    for source in ("S1", "S2"):
        assert [n for n in names if n.startswith(source)] == [
            f"{source}-t0000.png", f"{source}-t0003.png", f"{source}-t0042.png",
            f"{source}-t0090.png", f"{source}-t0200.png",
        ]
    assert not scratch.exists()
    assert capsys.readouterr().out.count("references/media/sentry/") == 10


def test_video_leaves_another_sources_scratch_alone_and_keeps_the_shared_parent(rig: Rig) -> None:
    other = rig.media() / "_video" / "S9"
    other.mkdir(parents=True)
    (other / "S9.mp4").write_bytes(b"in flight")

    assert rig.run("video", "sentry", "S1", "u").returncode == 0
    assert (other / "S9.mp4").read_bytes() == b"in flight"
    assert not (rig.media() / "_video" / "S1").exists()

    assert rig.run("video", "sentry", "S1", "u", FAKE_YTDLP_FAIL="1").returncode == 1
    assert (other / "S9.mp4").read_bytes() == b"in flight"
    assert not (rig.media() / "_video" / "S1").exists()


def test_extract_pairs_timestamps_with_frames_past_9999(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    capture = _load_capture(rig.skill, "capture_sort")
    total = 10001

    def fake_run(cmd):
        out_pattern = cmd[-1]
        lines = []
        for n in range(total):
            Path(out_pattern % (n + 1)).write_bytes(b"")
            lines.append(f"[Parsed_showinfo_1 @ 0x1] n: {n} pts: {n} pts_time:{n}.0 fmt:yuv420p")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="\n".join(lines))

    monkeypatch.setattr(capture, "run", fake_run)
    pairs = capture.extract("ffmpeg", tmp_path / "v.mp4", "showinfo", tmp_path / "frames")

    assert len(pairs) == total
    assert all(int(path.stem) == int(pts) + 1 for pts, path in pairs)
