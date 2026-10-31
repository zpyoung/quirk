"""Behavior of the explaining-features scripts: verify_outcome.py sorts a verify.json and leftovers.py finds survivors."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterator, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "explaining-features" / "scripts"
VERIFY_OUTCOME = SCRIPTS_DIR / "verify_outcome.py"

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


LEFTOVERS = SCRIPTS_DIR / "leftovers.py"
SLEEPER = "import sys, time\nheld = open(sys.argv[1]) if len(sys.argv) > 1 else None\nprint('ready', flush=True)\ntime.sleep(120)\n"


@contextlib.contextmanager
def sleeper(
    *, home: Path, cwd: Path, holding: Optional[Path] = None, extra: Optional[dict[str, str]] = None, extra_first: bool = False
) -> Iterator[int]:
    """A real process with the given HOME and working directory, optionally holding a file open; stopped on exit.

    ``extra`` adds variables, placed before HOME when ``extra_first`` so a test controls the order ``ps`` prints.
    """
    argv = [sys.executable, "-c", SLEEPER] + ([str(holding)] if holding else [])
    base = {"HOME": str(home), "PATH": os.environ.get("PATH", "")}
    env = {**(extra or {}), **base} if extra_first else {**base, **(extra or {})}
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout is not None and proc.stdout.readline().strip() == "ready"
        yield proc.pid
    finally:
        proc.kill()
        proc.wait()


def leftovers(folder: Path, *, env: Optional[dict[str, str]] = None, cwd: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LEFTOVERS), "--explainer", str(folder)],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )


def groups(folder: Path) -> tuple[set[int], set[int]]:
    done = leftovers(folder)
    assert done.returncode == 0, done.stderr
    doc = json.loads(done.stdout)
    assert set(doc) == {"yours", "check_by_hand"}
    for row in doc["yours"] + doc["check_by_hand"]:
        assert isinstance(row["pid"], int) and row["command"]
    return {r["pid"] for r in doc["yours"]}, {r["pid"] for r in doc["check_by_hand"]}


@pytest.fixture
def folders(tmp_path: Path) -> tuple[Path, Path, Path]:
    """The explainer folder with a harness home inside it, plus an unrelated folder."""
    explainer = tmp_path / "explainer"
    home = explainer / "harness" / "home"
    elsewhere = tmp_path / "elsewhere"
    for folder in (home, elsewhere):
        folder.mkdir(parents=True)
    return explainer, home, elsewhere


class TestLeftovers:
    def test_home_under_the_folder_is_yours(self, folders: tuple[Path, Path, Path]) -> None:
        explainer, home, elsewhere = folders
        with sleeper(home=home, cwd=elsewhere) as pid:
            assert groups(explainer) == ({pid}, set())

    def test_an_open_file_alone_lists_nothing(self, folders: tuple[Path, Path, Path]) -> None:
        explainer, _, elsewhere = folders
        held = explainer / "notes.txt"
        held.write_text("an editor has this open\n")
        with sleeper(home=elsewhere, cwd=elsewhere, holding=held) as pid:
            opened = subprocess.run(["lsof", "-w", "-p", str(pid)], capture_output=True, text=True).stdout
            assert str(held.resolve()) in opened, "the process must really hold the file"
            assert groups(explainer) == (set(), set())

    def test_working_directory_alone_is_check_by_hand(self, folders: tuple[Path, Path, Path]) -> None:
        explainer, _, elsewhere = folders
        with sleeper(home=elsewhere, cwd=explainer) as pid:
            assert groups(explainer) == (set(), {pid})

    def test_home_and_working_directory_list_it_once_as_yours(self, folders: tuple[Path, Path, Path]) -> None:
        explainer, home, _ = folders
        with sleeper(home=home, cwd=explainer) as pid:
            assert groups(explainer) == ({pid}, set())

    def test_a_sibling_folder_sharing_the_prefix_is_not_matched(self, folders: tuple[Path, Path, Path]) -> None:
        explainer, _, _ = folders
        sibling = explainer.parent / "explainer-2"
        sibling.mkdir()
        with sleeper(home=sibling, cwd=sibling):
            assert groups(explainer) == (set(), set())

    def test_a_symlinked_path_to_the_folder_matches_the_real_one(self, folders: tuple[Path, Path, Path]) -> None:
        explainer, home, elsewhere = folders
        link = explainer.parent / "link"
        link.symlink_to(explainer)
        with sleeper(home=home, cwd=elsewhere) as pid:
            assert groups(link) == ({pid}, set())

    def test_a_folder_with_spaces_in_its_name(self, tmp_path: Path) -> None:
        explainer = tmp_path / "my explainer 1"
        home = explainer / "harness" / "home dir"
        sibling = tmp_path / "my explainer 1 extra"
        for folder in (home, sibling):
            folder.mkdir(parents=True)
        with sleeper(home=home, cwd=tmp_path) as under, sleeper(home=explainer, cwd=tmp_path) as exact, sleeper(
            home=sibling, cwd=tmp_path
        ):
            assert groups(explainer) == ({under, exact}, set())

    @pytest.mark.parametrize("extra_first", [False, True])
    def test_a_home_quoted_inside_another_variable_does_not_make_it_yours(
        self, folders: tuple[Path, Path, Path], extra_first: bool
    ) -> None:
        explainer, _, elsewhere = folders
        note = {"NOTE": f"ticket HOME={explainer}/harness"}
        with sleeper(home=elsewhere, cwd=elsewhere, extra=note, extra_first=extra_first) as pid:
            assert pid not in groups(explainer)[0]

    def test_a_home_that_climbs_out_of_the_folder_is_not_yours(self, folders: tuple[Path, Path, Path]) -> None:
        explainer, _, elsewhere = folders
        climbing = Path(f"{explainer}/harness/../../elsewhere")
        with sleeper(home=climbing, cwd=elsewhere) as pid:
            assert pid not in groups(explainer)[0]

    def test_it_never_lists_itself_or_its_parent(self, folders: tuple[Path, Path, Path]) -> None:
        explainer, home, _ = folders
        env = {"HOME": str(home), "PATH": os.environ.get("PATH", "")}
        alone = leftovers(explainer, env=env, cwd=explainer)
        assert alone.returncode == 0 and json.loads(alone.stdout) == {"yours": [], "check_by_hand": []}
        parent_code = (
            "import subprocess, sys\n"
            f"done = subprocess.run([sys.executable, {str(LEFTOVERS)!r}, '--explainer', {str(explainer)!r}], capture_output=True, text=True)\n"
            "print(done.stdout)\n"
        )
        via_parent = subprocess.run([sys.executable, "-c", parent_code], capture_output=True, text=True, env=env, cwd=explainer)
        assert json.loads(via_parent.stdout) == {"yours": [], "check_by_hand": []}

    def test_a_missing_folder_exits_2(self, tmp_path: Path) -> None:
        done = leftovers(tmp_path / "nope")
        assert done.returncode == 2 and done.stdout == "" and done.stderr

    def test_lsof_exiting_1_with_text_on_stderr_exits_3(self, tmp_path: Path) -> None:
        folder = tmp_path / "explainer"
        folder.mkdir()
        fakes = tmp_path / "fakes"
        fakes.mkdir()
        fake = fakes / "lsof"
        fake.write_text("#!/bin/sh\necho 'boom' >&2\nexit 1\n")
        fake.chmod(0o755)
        path = os.pathsep.join([str(fakes), str(Path(shutil.which("ps") or "").parent)])
        done = leftovers(folder, env={"PATH": path})
        assert done.returncode == 3 and done.stdout == "" and done.stderr

    @pytest.mark.parametrize("broken", ["none", "lsof", "ps"])
    def test_a_missing_or_failing_tool_exits_3_without_json(self, tmp_path: Path, broken: str) -> None:
        folder = tmp_path / "explainer"
        folder.mkdir()
        fakes = tmp_path / "fakes"
        fakes.mkdir()
        if broken == "none":
            path = str(fakes)
        else:
            fake = fakes / broken
            fake.write_text("#!/bin/sh\necho 'boom' >&2\nexit 2\n")
            fake.chmod(0o755)
            real = {t: Path(shutil.which(t) or "").parent for t in ("ps", "lsof")}
            path = os.pathsep.join([str(fakes), *{str(d) for d in real.values()}])
        done = leftovers(folder, env={"PATH": path})
        assert done.returncode == 3 and done.stdout == "" and done.stderr
