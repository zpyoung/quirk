"""Behavior of the explaining-features scripts: verify_outcome.py sorts a verify.json, fit_video.py fits a film."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "explaining-features" / "scripts"
VERIFY_OUTCOME = SCRIPTS_DIR / "verify_outcome.py"
FIT_VIDEO = SCRIPTS_DIR / "fit_video.py"

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg and ffprobe are not installed")

MP4 = "film-16x9.mp4"


def check(name: str, status: str = "pass") -> dict[str, Any]:
    return {"name": name, "status": status, "measured": None, "threshold": None, "detail": ""}


def run_doc(
    failed: tuple[str, ...] = (),
    *,
    stop: bool = False,
    passed: Optional[bool] = None,
    skipped: tuple[str, ...] = (),
    extra_checks: tuple[str, ...] = ("fonts", "contrast", "sync", "outside_calls"),
) -> dict[str, Any]:
    names = list(dict.fromkeys([*extra_checks, *failed]))
    checks = [check(n, "fail" if n in failed else "skip" if n in skipped else "pass") for n in names]
    return {
        "attempts": [{"n": 1, "ts": "2026-01-01T00:00:00+00:00", "passed": not failed}],
        "attempt": 1,
        "failed_attempts": 1 if failed else 0,
        "passed": (not failed) if passed is None else passed,
        "stop": stop,
        "checks": checks,
        "frames": {},
    }


def verify_doc(**runs: dict[str, Any]) -> dict[str, Any]:
    return {"version": "v1", "passed": all(r["passed"] for r in runs.values()), "runs": runs}


def write_verify(tmp_path: Path, doc: Any) -> Path:
    path = tmp_path / "verify.json"
    path.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    return path


def outcome(tmp_path: Path, doc: Any, *extra: str) -> tuple[int, dict[str, Any], str]:
    path = write_verify(tmp_path, doc)
    proc = subprocess.run(
        [sys.executable, str(VERIFY_OUTCOME), "--verify", str(path), *extra],
        capture_output=True,
        text=True,
        timeout=30,
    )
    stdout = proc.stdout.strip()
    return proc.returncode, (json.loads(stdout) if stdout else {}), proc.stderr


class TestVerifyOutcomeRules:
    def test_ship_when_the_run_passed(self, tmp_path: Path) -> None:
        code, out, _ = outcome(tmp_path, verify_doc(**{MP4: run_doc()}))
        assert code == 0
        assert out["outcome"] == "ship"
        assert out["failed"] == []
        assert isinstance(out["detail"], str)

    def test_stdout_is_exactly_one_json_object(self, tmp_path: Path) -> None:
        path = write_verify(tmp_path, verify_doc(**{MP4: run_doc()}))
        proc = subprocess.run(
            [sys.executable, str(VERIFY_OUTCOME), "--verify", str(path)], capture_output=True, text=True, timeout=30
        )
        assert set(json.loads(proc.stdout)) == {"outcome", "failed", "detail"}

    @pytest.mark.parametrize("failing", [("sync",), ("loudness",), ("sync", "loudness")])
    def test_ship_disclosed_when_only_polish_checks_failed(self, tmp_path: Path, failing: tuple[str, ...]) -> None:
        code, out, _ = outcome(tmp_path, verify_doc(**{MP4: run_doc(failing, stop=True)}))
        assert code == 0
        assert out["outcome"] == "ship_disclosed"
        assert out["failed"] == list(failing)

    @pytest.mark.parametrize(
        "failing", ["fonts", "render_log", "contrast", "title_safe", "captions", "blender"]
    )
    def test_omit_when_a_viewer_would_notice(self, tmp_path: Path, failing: str) -> None:
        code, out, _ = outcome(tmp_path, verify_doc(**{MP4: run_doc((failing,), stop=True)}))
        assert code == 0
        assert out["outcome"] == "omit"
        assert out["failed"] == [failing]

    def test_omit_when_a_polish_check_fails_beside_a_visible_one(self, tmp_path: Path) -> None:
        _, out, _ = outcome(tmp_path, verify_doc(**{MP4: run_doc(("sync", "contrast"), stop=True)}))
        assert out["outcome"] == "omit"
        assert sorted(out["failed"]) == ["contrast", "sync"]

    def test_omit_on_an_unknown_check_name(self, tmp_path: Path) -> None:
        _, out, _ = outcome(tmp_path, verify_doc(**{MP4: run_doc(("sparkle",), stop=True)}))
        assert out["outcome"] == "omit"
        assert out["failed"] == ["sparkle"]

    def test_omit_when_the_run_failed_and_names_no_failed_check(self, tmp_path: Path) -> None:
        doc = run_doc(passed=False, stop=True)
        _, out, _ = outcome(tmp_path, verify_doc(**{MP4: doc}))
        assert out["outcome"] == "omit"
        assert out["failed"] == []

    def test_halt_when_outside_calls_failed(self, tmp_path: Path) -> None:
        _, out, _ = outcome(tmp_path, verify_doc(**{MP4: run_doc(("outside_calls",), stop=True)}))
        assert out["outcome"] == "halt"
        assert out["failed"] == ["outside_calls"]

    def test_halt_beats_retry_while_attempts_remain(self, tmp_path: Path) -> None:
        _, out, _ = outcome(tmp_path, verify_doc(**{MP4: run_doc(("outside_calls",), stop=False)}))
        assert out["outcome"] == "halt"

    def test_halt_reads_the_current_checks_of_a_run_in_the_making_videos_shape(self, tmp_path: Path) -> None:
        run = run_doc(("outside_calls", "sync"), stop=False)
        run["attempts"] = [
            {"n": 1, "ts": "2026-01-01T00:00:00+00:00", "passed": False},
            {"n": 2, "ts": "2026-01-01T00:05:00+00:00", "passed": False},
        ]
        run["attempt"], run["failed_attempts"] = 2, 2
        _, out, _ = outcome(tmp_path, verify_doc(**{MP4: run}))
        assert out["outcome"] == "halt"
        assert sorted(out["failed"]) == ["outside_calls", "sync"]

    @pytest.mark.parametrize("failing", [("sync",), ("contrast",), ("fonts", "sync")])
    def test_retry_while_the_stop_flag_is_false(self, tmp_path: Path, failing: tuple[str, ...]) -> None:
        _, out, _ = outcome(tmp_path, verify_doc(**{MP4: run_doc(failing, stop=False)}))
        assert out["outcome"] == "retry"
        assert out["failed"] == list(failing)

    def test_a_skipped_check_is_not_a_failure(self, tmp_path: Path) -> None:
        run = run_doc(("sync",), stop=True, skipped=("loudness",), extra_checks=("loudness", "fonts"))
        _, out, _ = outcome(tmp_path, verify_doc(**{MP4: run}))
        assert out["outcome"] == "ship_disclosed"
        assert out["failed"] == ["sync"]

    def test_the_run_that_passed_wins_over_earlier_failures(self, tmp_path: Path) -> None:
        run = run_doc()
        run["attempts"] = [
            {"n": 1, "ts": "2026-01-01T00:00:00+00:00", "passed": False},
            {"n": 2, "ts": "2026-01-01T00:05:00+00:00", "passed": True},
        ]
        _, out, _ = outcome(tmp_path, verify_doc(**{MP4: run}))
        assert out["outcome"] == "ship"


class TestVerifyOutcomeInput:
    def test_the_only_run_is_used_without_mp4(self, tmp_path: Path) -> None:
        code, out, _ = outcome(tmp_path, verify_doc(**{MP4: run_doc()}))
        assert (code, out["outcome"]) == (0, "ship")

    def test_several_runs_without_mp4_exit_2(self, tmp_path: Path) -> None:
        doc = verify_doc(**{"a-16x9.mp4": run_doc(), "a-9x16.mp4": run_doc(("contrast",), stop=True)})
        code, out, err = outcome(tmp_path, doc)
        assert code == 2
        assert out == {}
        assert "--mp4" in err

    def test_mp4_picks_one_of_several_runs(self, tmp_path: Path) -> None:
        doc = verify_doc(**{"a-16x9.mp4": run_doc(), "a-9x16.mp4": run_doc(("contrast",), stop=True)})
        _, out, _ = outcome(tmp_path, doc, "--mp4", "a-9x16.mp4")
        assert out["outcome"] == "omit"
        _, out, _ = outcome(tmp_path, doc, "--mp4", "a-16x9.mp4")
        assert out["outcome"] == "ship"

    def test_mp4_accepts_a_path_and_matches_its_filename(self, tmp_path: Path) -> None:
        _, out, _ = outcome(tmp_path, verify_doc(**{MP4: run_doc()}), "--mp4", f"/studio/v1/{MP4}")
        assert out["outcome"] == "ship"

    def test_a_named_run_that_is_missing_exits_2(self, tmp_path: Path) -> None:
        code, out, err = outcome(tmp_path, verify_doc(**{MP4: run_doc()}), "--mp4", "other.mp4")
        assert code == 2
        assert out == {}
        assert "other.mp4" in err

    def test_no_runs_exits_2(self, tmp_path: Path) -> None:
        code, _, _ = outcome(tmp_path, {"version": "v1", "passed": False, "runs": {}})
        assert code == 2

    def test_flat_verify_json_is_the_single_run(self, tmp_path: Path) -> None:
        code, out, _ = outcome(tmp_path, run_doc(("contrast",), stop=True))
        assert (code, out["outcome"]) == (0, "omit")

    @pytest.mark.parametrize("text", ["", "not json", "[]", '"x"'])
    def test_unreadable_input_exits_2(self, tmp_path: Path, text: str) -> None:
        code, out, err = outcome(tmp_path, text)
        assert code == 2
        assert out == {}
        assert err.strip()

    def test_missing_file_exits_2(self, tmp_path: Path) -> None:
        proc = subprocess.run(
            [sys.executable, str(VERIFY_OUTCOME), "--verify", str(tmp_path / "nope.json")],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 2
        assert proc.stdout == ""

    def test_missing_verify_flag_exits_2(self) -> None:
        proc = subprocess.run([sys.executable, str(VERIFY_OUTCOME)], capture_output=True, text=True, timeout=30)
        assert proc.returncode == 2

    def test_a_failed_run_without_a_boolean_stop_flag_exits_2(self, tmp_path: Path) -> None:
        run = run_doc(("sync",))
        del run["stop"]
        code, _, err = outcome(tmp_path, verify_doc(**{MP4: run}))
        assert code == 2
        assert "stop" in err

    def test_a_run_without_a_boolean_passed_exits_2(self, tmp_path: Path) -> None:
        run = run_doc()
        run["passed"] = "yes"
        code, _, _ = outcome(tmp_path, verify_doc(**{MP4: run}))
        assert code == 2


def make_clip(path: Path, *, seconds: int = 6, audio: bool = True) -> Path:
    """A noisy clip that cannot be re-encoded smaller than its budget for free."""
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=24:duration={seconds}",
    ]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    cmd += ["-c:v", "libx264", "-b:v", "3000k", "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd += ["-f", "mp4", str(path)]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    return path


def fit(*args: str, env: Optional[dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(FIT_VIDEO), *args], capture_output=True, text=True, timeout=300, env=env
    )


def probe(path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "stream=codec_name,codec_type,pix_fmt,width,height:format=duration",
            "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


class TestFitVideoCopy:
    def test_copies_when_the_input_already_fits(self, tmp_path: Path) -> None:
        src = tmp_path / "in.mp4"
        src.write_bytes(b"\x00" * 5000)
        out = tmp_path / "nested" / "out.mp4"
        proc = fit("--in", str(src), "--budget-bytes", "5000", "--out", str(out))
        assert proc.returncode == 0
        result = json.loads(proc.stdout)
        assert result == {"out": str(out), "bytes": 5000, "reencoded": False, "video_kbps": None}
        assert out.read_bytes() == src.read_bytes()

    def test_copy_needs_no_ffmpeg(self, tmp_path: Path) -> None:
        src = tmp_path / "in.mp4"
        src.write_bytes(b"abc")
        empty = tmp_path / "empty-bin"
        empty.mkdir()
        proc = fit("--in", str(src), "--budget-bytes", "10", "--out", str(tmp_path / "o.mp4"), env={"PATH": str(empty)})
        assert proc.returncode == 0
        assert json.loads(proc.stdout)["reencoded"] is False


class TestFitVideoUsage:
    def test_missing_arguments_exit_2(self) -> None:
        assert fit().returncode == 2

    def test_missing_input_exits_2(self, tmp_path: Path) -> None:
        proc = fit("--in", str(tmp_path / "no.mp4"), "--budget-bytes", "100", "--out", str(tmp_path / "o.mp4"))
        assert proc.returncode == 2
        assert proc.stdout == ""

    @pytest.mark.parametrize("budget", ["0", "-5", "lots"])
    def test_a_bad_budget_exits_2(self, tmp_path: Path, budget: str) -> None:
        src = tmp_path / "in.mp4"
        src.write_bytes(b"abc")
        assert fit("--in", str(src), "--budget-bytes", budget, "--out", str(tmp_path / "o.mp4")).returncode == 2

    def test_output_may_not_be_the_input(self, tmp_path: Path) -> None:
        src = tmp_path / "in.mp4"
        src.write_bytes(b"abc")
        proc = fit("--in", str(src), "--budget-bytes", "100", "--out", str(src))
        assert proc.returncode == 2
        assert src.read_bytes() == b"abc"

    def test_ffmpeg_missing_exits_3_when_a_re_encode_is_needed(self, tmp_path: Path) -> None:
        src = tmp_path / "in.mp4"
        src.write_bytes(b"\x00" * 5000)
        empty = tmp_path / "empty-bin"
        empty.mkdir()
        out = tmp_path / "o.mp4"
        proc = fit("--in", str(src), "--budget-bytes", "100", "--out", str(out), env={"PATH": str(empty)})
        assert proc.returncode == 3
        assert proc.stdout == ""
        assert "ffmpeg" in proc.stderr
        assert not out.exists()


@needs_ffmpeg
class TestFitVideoReencode:
    def test_re_encodes_to_fit_the_budget(self, tmp_path: Path) -> None:
        src = make_clip(tmp_path / "in.mp4")
        budget = int(src.stat().st_size * 0.5)
        out = tmp_path / "out.mp4"
        proc = fit("--in", str(src), "--budget-bytes", str(budget), "--out", str(out))
        assert proc.returncode == 0, proc.stderr
        result = json.loads(proc.stdout)
        assert result["reencoded"] is True
        assert result["out"] == str(out)
        assert result["bytes"] == out.stat().st_size <= budget
        assert result["video_kbps"] >= 300
        info = probe(out)
        streams = {s["codec_type"]: s for s in info["streams"]}
        assert streams["video"]["codec_name"] == "h264"
        assert streams["video"]["pix_fmt"] == "yuv420p"
        assert streams["audio"]["codec_name"] == "aac"
        assert abs(float(info["format"]["duration"]) - 6.0) < 0.5

    def test_leaves_no_partial_file_beside_the_output(self, tmp_path: Path) -> None:
        src = make_clip(tmp_path / "in.mp4")
        out_dir = tmp_path / "media"
        proc = fit("--in", str(src), "--budget-bytes", str(int(src.stat().st_size * 0.5)), "--out", str(out_dir / "o.mp4"))
        assert proc.returncode == 0, proc.stderr
        assert [p.name for p in out_dir.iterdir()] == ["o.mp4"]

    def test_a_silent_clip_fits_without_an_audio_stream(self, tmp_path: Path) -> None:
        src = make_clip(tmp_path / "in.mp4", audio=False)
        out = tmp_path / "out.mp4"
        proc = fit("--in", str(src), "--budget-bytes", str(int(src.stat().st_size * 0.5)), "--out", str(out))
        assert proc.returncode == 0, proc.stderr
        assert {s["codec_type"] for s in probe(out)["streams"]} == {"video"}

    def test_below_the_floor_exits_1_and_names_budget_and_floor(self, tmp_path: Path) -> None:
        src = make_clip(tmp_path / "in.mp4")
        out_dir = tmp_path / "media"
        out = out_dir / "out.mp4"
        proc = fit("--in", str(src), "--budget-bytes", "20000", "--out", str(out))
        assert proc.returncode == 1
        assert proc.stdout == ""
        assert "20000" in proc.stderr
        assert "300" in proc.stderr
        assert list(out_dir.iterdir()) == []

    def test_a_budget_below_the_nominal_floor_size_succeeds_when_the_floor_encode_fits(self, tmp_path: Path) -> None:
        src = tmp_path / "in.mp4"
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=6,fps=1,fps=24",
                "-c:v", "libx264", "-b:v", "3000k", "-pix_fmt", "yuv420p", "-f", "mp4", str(src),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        floor_clip = tmp_path / "floor.mp4"
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y", "-i", str(src), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "medium", "-b:v", "300k", "-maxrate", "300k", "-bufsize", "600k",
                "-movflags", "+faststart", "-an", "-f", "mp4", str(floor_clip),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        budget = int(floor_clip.stat().st_size * 1.02)
        duration = float(probe(src)["format"]["duration"])
        assert budget * 8 / duration / 1000 < 300
        assert budget < src.stat().st_size
        out = tmp_path / "out.mp4"
        proc = fit("--in", str(src), "--budget-bytes", str(budget), "--out", str(out))
        assert proc.returncode == 0, proc.stderr
        result = json.loads(proc.stdout)
        assert result["video_kbps"] == 300
        assert result["bytes"] == out.stat().st_size <= budget

    def test_a_floor_encode_that_still_overshoots_exits_1_and_leaves_nothing(self, tmp_path: Path) -> None:
        src = make_clip(tmp_path / "in.mp4", seconds=30, audio=False)
        duration = float(probe(src)["format"]["duration"])
        budget = int(300 * 1000 / 8 * duration * 1.0005)
        out_dir = tmp_path / "media"
        proc = fit("--in", str(src), "--budget-bytes", str(budget), "--out", str(out_dir / "o.mp4"))
        assert proc.returncode == 1
        assert proc.stdout == ""
        assert str(budget) in proc.stderr
        assert "300" in proc.stderr
        assert list(out_dir.iterdir()) == []

    def test_an_input_named_like_the_old_partial_file_survives_a_floor_rejection(self, tmp_path: Path) -> None:
        out = tmp_path / "film.mp4"
        src = make_clip(tmp_path / "film.mp4.part")
        before = src.read_bytes()
        proc = fit("--in", str(src), "--budget-bytes", "20000", "--out", str(out))
        assert proc.returncode == 1
        assert src.read_bytes() == before
        assert not out.exists()

    def test_an_input_named_like_the_old_partial_file_survives_a_failed_encode(self, tmp_path: Path) -> None:
        shim = tmp_path / "bin"
        shim.mkdir()
        (shim / "ffmpeg").write_text("#!/bin/sh\necho boom >&2\nexit 1\n")
        (shim / "ffmpeg").chmod(0o755)
        (shim / "ffprobe").symlink_to(shutil.which("ffprobe"))
        out = tmp_path / "film.mp4"
        src = make_clip(tmp_path / "film.mp4.part")
        before = src.read_bytes()
        proc = fit(
            "--in", str(src), "--budget-bytes", str(int(src.stat().st_size * 0.5)), "--out", str(out),
            env={"PATH": str(shim)},
        )
        assert proc.returncode == 1
        assert "boom" in proc.stderr
        assert src.read_bytes() == before
        assert not out.exists()
        assert sorted(p.name for p in tmp_path.iterdir()) == ["bin", "film.mp4.part"]

    def test_an_input_named_like_the_old_partial_file_survives_a_successful_fit(self, tmp_path: Path) -> None:
        out = tmp_path / "film.mp4"
        src = make_clip(tmp_path / "film.mp4.part")
        before = src.read_bytes()
        proc = fit("--in", str(src), "--budget-bytes", str(int(src.stat().st_size * 0.5)), "--out", str(out))
        assert proc.returncode == 0, proc.stderr
        assert src.read_bytes() == before
        assert out.stat().st_size <= int(len(before) * 0.5)

    def test_not_a_video_exits_2(self, tmp_path: Path) -> None:
        src = tmp_path / "in.mp4"
        src.write_bytes(b"this is not a video" * 500)
        proc = fit("--in", str(src), "--budget-bytes", "100", "--out", str(tmp_path / "o.mp4"))
        assert proc.returncode == 2
