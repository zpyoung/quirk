"""The probe execution contract: `test:`, `grep:`, and `none`.

docs/quirk/specs/2026-08-04-pm-agent/tech.md, §The probe execution contract.
Exercises `pm.parse_probe_spec` / `pm.run_probe` / `pm.probe_accepts_baseline` /
`pm.probe_accepts_final` / `pm.grep_baseline_files_missing` directly — the `start`/`finish`
commands that call this engine are a later task and remain unimplemented stubs.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

import pm

from .conftest import TEMPLATES_DIR, isolated_git_env, run_pm


@pytest.fixture(autouse=True)
def _clean_probe_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("QUIRK_PM_PROBE_TIMEOUT", "QUIRK_PM_TEST_RUNNER", "QUIRK_PM_TEST_EXIT_MAP"):
        monkeypatch.delenv(name, raising=False)


def write(root: Path, name: str, body: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


# --- parse_probe_spec --------------------------------------------------------


def test_parse_none() -> None:
    spec = pm.parse_probe_spec("none")
    assert spec == pm.ProbeSpec(verb="none", arg="")


def test_parse_test_verb() -> None:
    spec = pm.parse_probe_spec("test:tests/test_auth.py::test_safari")
    assert spec == pm.ProbeSpec(
        verb="test", arg="tests/test_auth.py::test_safari",
        nodeid="tests/test_auth.py::test_safari",
    )


def test_parse_grep_verb_with_no_separator_takes_whole_remainder_as_pattern() -> None:
    spec = pm.parse_probe_spec("grep:TODO_AUTH")
    assert spec == pm.ProbeSpec(verb="grep", arg="TODO_AUTH", pattern="TODO_AUTH", paths=())


def test_parse_grep_verb_splits_pattern_and_paths_on_first_separator_only() -> None:
    # a second " -- " inside the paths portion must NOT trigger a further split — it becomes
    # ordinary shlex tokens, proving the split is first-occurrence-only
    spec = pm.parse_probe_spec("grep:TODO -- src/ -- extra")
    assert spec.verb == "grep"
    assert spec.pattern == "TODO"
    assert spec.paths == ("src/", "--", "extra")
    assert spec.arg == "TODO -- src/ -- extra"


def test_parse_grep_paths_use_shlex_for_quoting() -> None:
    spec = pm.parse_probe_spec('grep:TODO -- "src/auth dir/" other/path')
    assert spec.pattern == "TODO"
    assert spec.paths == ("src/auth dir/", "other/path")


def test_parse_unknown_verb_is_an_error() -> None:
    result = pm.parse_probe_spec("lint:everything")
    assert isinstance(result, pm.ProbeArgError)


def test_parse_test_verb_requires_nonempty_nodeid() -> None:
    result = pm.parse_probe_spec("test:")
    assert isinstance(result, pm.ProbeArgError)


def test_parse_grep_verb_requires_nonempty_pattern() -> None:
    result = pm.parse_probe_spec("grep:")
    assert isinstance(result, pm.ProbeArgError)


def test_parse_grep_malformed_path_shell_syntax_is_an_error() -> None:
    result = pm.parse_probe_spec('grep:TODO -- "unterminated')
    assert isinstance(result, pm.ProbeArgError)


# --- test: the full pytest exit-code mapping ---------------------------------


def test_test_probe_exit_0_is_pass(tmp_path: Path) -> None:
    write(tmp_path, "test_x.py", "def test_ok():\n    assert True\n")
    spec = pm.parse_probe_spec("test:test_x.py::test_ok")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "pass"


def test_test_probe_exit_1_is_fail(tmp_path: Path) -> None:
    write(tmp_path, "test_x.py", "def test_bad():\n    assert False\n")
    spec = pm.parse_probe_spec("test:test_x.py::test_bad")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "fail"


def test_test_probe_exit_4_usage_error_is_missing(tmp_path: Path) -> None:
    write(tmp_path, "test_x.py", "def test_ok():\n    assert True\n")
    spec = pm.parse_probe_spec("test:test_x.py::test_does_not_exist")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "missing"


def test_test_probe_exit_5_no_tests_collected_is_missing(tmp_path: Path) -> None:
    write(tmp_path, "test_x.py", "def helper():\n    pass\n")
    spec = pm.parse_probe_spec("test:test_x.py")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "missing"


def test_test_probe_exit_2_interrupted_is_error(tmp_path: Path) -> None:
    # a whole-file collection error (no ::nodeid) is what actually reproduces pytest's exit 2
    # on 8.4.2 -- the same import failure targeted at a specific ::nodeid instead yields 4
    write(tmp_path, "test_x.py", "import this_module_does_not_exist_anywhere\n")
    spec = pm.parse_probe_spec("test:test_x.py")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "error"


def test_test_probe_exit_3_internal_error_is_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # pytest's own INTERNAL_ERROR (3) isn't reliably reproducible on demand; this pins the
    # "any code absent from the map defaults to error" fallback the real code path also uses
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args=["fake"], returncode=3)

    monkeypatch.setattr(pm.subprocess, "run", fake_run)
    spec = pm.parse_probe_spec("test:test_x.py::test_ok")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "error"


def test_test_probe_timeout_is_error(tmp_path: Path) -> None:
    write(tmp_path, "test_x.py", "import time\n\ndef test_slow():\n    time.sleep(5)\n")
    spec = pm.parse_probe_spec("test:test_x.py::test_slow")
    result = pm.run_probe(spec, tmp_path, timeout=1)
    assert result.outcome == "error"


# --- regression row 9: only a genuinely failing test is an acceptable baseline ----------------


def test_regression_9_nonexistent_nodeid_records_missing_and_refuses(tmp_path: Path) -> None:
    spec = pm.parse_probe_spec("test:tests/does_not_exist.py::test_nope")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "missing"
    assert pm.probe_accepts_baseline(spec, result) is False


def test_regression_9_import_error_records_error_and_refuses(tmp_path: Path) -> None:
    write(tmp_path, "test_x.py", "import this_module_does_not_exist_anywhere\n")
    spec = pm.parse_probe_spec("test:test_x.py")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "error"
    assert pm.probe_accepts_baseline(spec, result) is False


def test_regression_9_timeout_records_error_and_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(tmp_path, "test_x.py", "import time\n\ndef test_slow():\n    time.sleep(5)\n")
    monkeypatch.setenv("QUIRK_PM_PROBE_TIMEOUT", "1")
    spec = pm.parse_probe_spec("test:test_x.py::test_slow")
    result = pm.run_probe(spec, tmp_path)
    assert result.outcome == "error"
    assert pm.probe_accepts_baseline(spec, result) is False


def test_regression_9_only_a_genuinely_failing_test_is_accepted(tmp_path: Path) -> None:
    write(tmp_path, "test_x.py", "def test_bad():\n    assert False\n")
    spec = pm.parse_probe_spec("test:test_x.py::test_bad")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "fail"
    assert pm.probe_accepts_baseline(spec, result) is True


def test_regression_9_exact_outcome_tokens_are_not_collapsed_to_fail(tmp_path: Path) -> None:
    write(tmp_path, "test_x.py", "import this_module_does_not_exist_anywhere\n")
    missing_spec = pm.parse_probe_spec("test:tests/does_not_exist.py::test_nope")
    error_spec = pm.parse_probe_spec("test:test_x.py")

    missing_result = pm.run_probe(missing_spec, tmp_path, timeout=30)
    error_result = pm.run_probe(error_spec, tmp_path, timeout=30)

    assert (missing_result.outcome, error_result.outcome) == ("missing", "error")
    assert missing_result.outcome != "fail"
    assert error_result.outcome != "fail"


# --- test: finish-time acceptance --------------------------------------------


def test_finish_missing_refuses(tmp_path: Path) -> None:
    write(tmp_path, "test_x.py", "def test_ok():\n    assert True\n")
    spec = pm.parse_probe_spec("test:test_x.py::test_does_not_exist")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "missing"
    assert pm.probe_accepts_final(spec, result) is False


def test_finish_fail_refuses(tmp_path: Path) -> None:
    write(tmp_path, "test_x.py", "def test_bad():\n    assert False\n")
    spec = pm.parse_probe_spec("test:test_x.py::test_bad")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "fail"
    assert pm.probe_accepts_final(spec, result) is False


def test_finish_error_refuses(tmp_path: Path) -> None:
    write(tmp_path, "test_x.py", "import this_module_does_not_exist_anywhere\n")
    spec = pm.parse_probe_spec("test:test_x.py")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "error"
    assert pm.probe_accepts_final(spec, result) is False


def test_finish_pass_is_the_only_passing_outcome(tmp_path: Path) -> None:
    write(tmp_path, "test_x.py", "def test_ok():\n    assert True\n")
    spec = pm.parse_probe_spec("test:test_x.py::test_ok")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "pass"
    assert pm.probe_accepts_final(spec, result) is True


# --- QUIRK_PM_TEST_RUNNER / QUIRK_PM_TEST_EXIT_MAP ---------------------------


def _write_fake_runner(tmp_path: Path, exit_code: int) -> Path:
    script = tmp_path / "fake_runner.sh"
    script.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    script.chmod(0o755)
    return script


def test_non_default_runner_without_exit_map_is_a_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _write_fake_runner(tmp_path, 7)
    monkeypatch.setenv("QUIRK_PM_TEST_RUNNER", str(runner))
    spec = pm.parse_probe_spec("test:irrelevant")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "config_error"
    assert result.detail


def test_non_default_runner_with_exit_map_is_governed_by_the_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _write_fake_runner(tmp_path, 7)
    monkeypatch.setenv("QUIRK_PM_TEST_RUNNER", str(runner))
    monkeypatch.setenv("QUIRK_PM_TEST_EXIT_MAP", "7:pass")
    spec = pm.parse_probe_spec("test:irrelevant")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "pass"


def test_default_runner_explicitly_set_to_the_default_string_does_not_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QUIRK_PM_TEST_RUNNER", "python3 -m pytest")
    write(tmp_path, "test_x.py", "def test_ok():\n    assert True\n")
    spec = pm.parse_probe_spec("test:test_x.py::test_ok")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "pass"


# --- QUIRK_PM_PROBE_TIMEOUT ---------------------------------------------------


def test_probe_timeout_infinite_falls_back_to_the_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # a subprocess timeout of infinity raises rather than bounding anything, so the value that
    # parses to "unbounded" must be rejected, not honored
    monkeypatch.setenv("QUIRK_PM_PROBE_TIMEOUT", "inf")
    assert pm._probe_timeout() == pm.DEFAULT_PROBE_TIMEOUT
    assert "QUIRK_PM_PROBE_TIMEOUT" in capsys.readouterr().err


def test_probe_timeout_nan_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUIRK_PM_PROBE_TIMEOUT", "nan")
    assert pm._probe_timeout() == pm.DEFAULT_PROBE_TIMEOUT


def test_probe_timeout_negative_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUIRK_PM_PROBE_TIMEOUT", "-5")
    assert pm._probe_timeout() == pm.DEFAULT_PROBE_TIMEOUT


def test_probe_timeout_zero_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUIRK_PM_PROBE_TIMEOUT", "0")
    assert pm._probe_timeout() == pm.DEFAULT_PROBE_TIMEOUT


def test_probe_timeout_finite_positive_value_is_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUIRK_PM_PROBE_TIMEOUT", "45")
    assert pm._probe_timeout() == 45.0


# --- grep: pure-Python scan ---------------------------------------------------


def test_grep_counts_per_matching_line_not_per_occurrence(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "TODO TODO TODO\nnothing here\nTODO once\n")
    spec = pm.parse_probe_spec("grep:TODO")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "ok"
    assert result.count == 2
    assert result.files == ("f.txt",)


def test_grep_paths_restrict_the_scan(tmp_path: Path) -> None:
    write(tmp_path, "a/match.txt", "TODO here\n")
    write(tmp_path, "b/match.txt", "TODO here too\n")
    spec = pm.parse_probe_spec("grep:TODO -- a")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "ok"
    assert result.count == 1
    assert result.files == ("a/match.txt",)


def test_grep_no_paths_defaults_to_worktree_root(tmp_path: Path) -> None:
    write(tmp_path, "a/match.txt", "TODO here\n")
    write(tmp_path, "b/match.txt", "TODO here too\n")
    spec = pm.parse_probe_spec("grep:TODO")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.count == 2
    assert result.files == ("a/match.txt", "b/match.txt")


def test_grep_skips_the_dot_git_directory(tmp_path: Path) -> None:
    write(tmp_path, ".git/TODO_INSIDE_GIT.txt", "TODO\n")
    write(tmp_path, "src/f.txt", "TODO\n")
    spec = pm.parse_probe_spec("grep:TODO")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.files == ("src/f.txt",)


def test_grep_skips_binary_files_without_error(tmp_path: Path) -> None:
    (tmp_path / "binary.dat").write_bytes(b"\xff\xfe\x00TODO\x00\xff")
    write(tmp_path, "src/f.txt", "TODO\n")
    spec = pm.parse_probe_spec("grep:TODO")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "ok"
    assert result.files == ("src/f.txt",)
    assert result.skipped_files == 0


def test_grep_regexp_has_no_implicit_flags(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "todo lowercase\nTODO uppercase\n")
    spec = pm.parse_probe_spec("grep:TODO")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.count == 1


def test_grep_baseline_count_zero_refuses_at_start(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "nothing matches here\n")
    spec = pm.parse_probe_spec("grep:TODO_AUTH")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "ok"
    assert result.count == 0
    assert pm.probe_accepts_baseline(spec, result) is False


def test_grep_baseline_count_nonzero_is_an_acceptable_baseline(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "TODO_AUTH here\n")
    spec = pm.parse_probe_spec("grep:TODO_AUTH")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert pm.probe_accepts_baseline(spec, result) is True


def test_grep_final_count_zero_is_the_only_passing_final(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "clean now\n")
    spec = pm.parse_probe_spec("grep:TODO_AUTH")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.count == 0
    assert pm.probe_accepts_final(spec, result) is True


def test_grep_final_count_nonzero_refuses(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "TODO_AUTH still here\n")
    spec = pm.parse_probe_spec("grep:TODO_AUTH")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert pm.probe_accepts_final(spec, result) is False


# --- regression row 10: undefined grep inputs --------------------------------


def test_regression_10_invalid_regex_is_error_naming_the_re_error(tmp_path: Path) -> None:
    try:
        re.compile("(unclosed")
    except re.error as exc:
        expected = str(exc)
    spec = pm.parse_probe_spec("grep:(unclosed")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "error"
    assert result.detail == expected


def test_regression_10_compile_failure_other_than_re_error_is_a_result_not_an_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # some catastrophic patterns fail re.compile with RecursionError/OverflowError, not re.error
    # -- run_probe is contractually not supposed to raise on an ordinary probe failure
    def fake_compile(pattern: str, *args: object, **kwargs: object) -> None:
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setattr(pm.re, "compile", fake_compile)
    spec = pm.parse_probe_spec("grep:TODO")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "error"
    assert result.detail


def test_regression_10_nonexistent_listed_path_is_error_naming_the_path(tmp_path: Path) -> None:
    spec = pm.parse_probe_spec("grep:TODO -- does/not/exist")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "error"
    assert "does/not/exist" in result.detail


def test_regression_10_unreadable_listed_path_is_error_naming_the_path(tmp_path: Path) -> None:
    blocked = write(tmp_path, "blocked/f.txt", "TODO\n")
    (tmp_path / "blocked").chmod(0o000)
    try:
        spec = pm.parse_probe_spec("grep:TODO -- blocked")
        result = pm.run_probe(spec, tmp_path, timeout=30)
    finally:
        (tmp_path / "blocked").chmod(0o755)
    assert result.outcome == "error"
    assert "blocked" in result.detail


def test_regression_10_unreadable_file_mid_walk_is_skipped_and_counted(tmp_path: Path) -> None:
    write(tmp_path, "dir/readable.txt", "TODO here\n")
    blocked = write(tmp_path, "dir/blocked.txt", "TODO also here\n")
    blocked.chmod(0o000)
    try:
        spec = pm.parse_probe_spec("grep:TODO -- dir")
        result = pm.run_probe(spec, tmp_path, timeout=30)
    finally:
        blocked.chmod(0o644)
    assert result.outcome == "ok"
    assert result.skipped_files == 1
    assert result.files == ("dir/readable.txt",)
    assert result.count == 1


def test_regression_12_grep_skips_a_fifo_mid_walk_without_blocking(tmp_path: Path) -> None:
    write(tmp_path, "dir/readable.txt", "TODO here\n")
    if not hasattr(os, "mkfifo"):
        pytest.skip("no FIFOs on this platform")
    os.mkfifo(tmp_path / "dir" / "a.fifo")

    outcome: list[pm.ProbeResult] = []
    thread = threading.Thread(
        target=lambda: outcome.append(pm.run_probe(pm.parse_probe_spec("grep:TODO -- dir"), tmp_path, timeout=30)),
        daemon=True,
    )
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive(), "grep probe blocked opening a FIFO instead of skipping it"

    result = outcome[0]
    assert result.outcome == "ok"
    assert result.skipped_files == 1
    assert result.files == ("dir/readable.txt",)


def test_regression_10_symlink_loop_terminates(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    write(tmp_path, "a/real.txt", "TODO here\n")
    (tmp_path / "a" / "loop").symlink_to(tmp_path / "a", target_is_directory=True)
    spec = pm.parse_probe_spec("grep:TODO")
    result = pm.run_probe(spec, tmp_path, timeout=5)
    assert result.outcome == "ok"
    assert result.files == ("a/real.txt",)


def test_regression_10_symlinked_file_outside_listed_paths_is_excluded(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    write(outside, "secret.txt", "TODO outside\n")
    inside = tmp_path / "inside"
    inside.mkdir()
    (inside / "link.txt").symlink_to(outside / "secret.txt")
    spec = pm.parse_probe_spec("grep:TODO -- inside")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "ok"
    assert result.count == 0
    assert result.files == ()


def test_regression_10_large_tree_over_timeout_is_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for i in range(30):
        write(tmp_path, f"dir{i}/f.txt", "TODO\n")

    # deterministic instead of relying on wall-clock: the first per-file check must already
    # see elapsed time past the timeout, proving the check runs before any file is opened
    clock = iter([0.0, 5.0])
    monkeypatch.setattr(pm.time, "monotonic", lambda: next(clock))

    spec = pm.parse_probe_spec("grep:TODO")
    result = pm.run_probe(spec, tmp_path, timeout=1)
    assert result.outcome == "error"


# --- grep_baseline_files_missing / finish-time deleted-baseline-file refusal -------------------


def test_grep_baseline_files_missing_reports_deleted_files(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "TODO here\n")
    spec = pm.parse_probe_spec("grep:TODO")
    baseline_result = pm.run_probe(spec, tmp_path, timeout=30)
    assert baseline_result.files == ("f.txt",)

    (tmp_path / "f.txt").unlink()

    missing = pm.grep_baseline_files_missing(tmp_path, baseline_result.files)
    assert missing == ["f.txt"]


def test_grep_baseline_files_missing_is_empty_when_all_still_exist(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "TODO here\n")
    spec = pm.parse_probe_spec("grep:TODO")
    baseline_result = pm.run_probe(spec, tmp_path, timeout=30)

    missing = pm.grep_baseline_files_missing(tmp_path, baseline_result.files)
    assert missing == []


def test_grep_baseline_files_missing_reports_a_file_replaced_by_a_directory(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "TODO here\n")
    spec = pm.parse_probe_spec("grep:TODO")
    baseline_result = pm.run_probe(spec, tmp_path, timeout=30)
    assert baseline_result.files == ("f.txt",)

    (tmp_path / "f.txt").unlink()
    (tmp_path / "f.txt").mkdir()

    missing = pm.grep_baseline_files_missing(tmp_path, baseline_result.files)
    assert missing == ["f.txt"]


def test_finish_refuses_on_deleted_baseline_file_even_when_count_is_zero(tmp_path: Path) -> None:
    write(tmp_path, "f.txt", "TODO here\n")
    spec = pm.parse_probe_spec("grep:TODO")
    baseline_result = pm.run_probe(spec, tmp_path, timeout=30)
    baseline_files = baseline_result.files

    (tmp_path / "f.txt").unlink()

    final_result = pm.run_probe(spec, tmp_path, timeout=30)
    missing = pm.grep_baseline_files_missing(tmp_path, baseline_files)

    assert final_result.count == 0
    assert pm.probe_accepts_final(spec, final_result) is True
    assert missing == ["f.txt"]


# --- none: never executed, always passes --------------------------------------


def test_none_probe_never_spawns_a_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("none: probe must never be executed")

    monkeypatch.setattr(pm.subprocess, "run", fail_if_called)
    spec = pm.parse_probe_spec("none")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert result.outcome == "none"


def test_none_probe_always_accepted_as_baseline_and_final(tmp_path: Path) -> None:
    spec = pm.parse_probe_spec("none")
    result = pm.run_probe(spec, tmp_path, timeout=30)
    assert pm.probe_accepts_baseline(spec, result) is True
    assert pm.probe_accepts_final(spec, result) is True


# --- finish: a refusal names the outcome it observed -------------------------
#
# `commands/pm/finish.md` relays the recorded outcome on exit 9 so the worker can tell "still
# broken" (fail) apart from "the probe itself broke" (missing/error/deleted baseline files) — the
# command can only relay what `finish` prints.


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, env=isolated_git_env(), check=True,
    )


@pytest.fixture
def pm_git_project(fake_git_repo: Path) -> Path:
    """`fake_git_repo`, additionally scaffolded with v2 ledgers and committed — `finish`'s
    worktree-root precondition needs the project directory to itself be a git checkout."""
    for name in pm.LEDGER_FILES:
        shutil.copy(TEMPLATES_DIR / name, fake_git_repo / name)
    shutil.copy(TEMPLATES_DIR / "ROADMAP.md", fake_git_repo / "ROADMAP.md")
    (fake_git_repo / "docs" / "adr").mkdir(parents=True, exist_ok=True)
    _git(fake_git_repo, "add", "-A")
    _git(fake_git_repo, "commit", "-q", "-m", "seed ledger")
    return fake_git_repo


def commit_all(repo: Path, message: str = "commit") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def append_bug(project: Path, entry_id: int, title: str = "a bug", **fields: str) -> None:
    path = project / "BUGS.md"
    lines = [f"\n## BUG-{entry_id}: {title}"]
    for label, value in fields.items():
        lines.append(f"- **{label}**: {value}")
    path.write_text(path.read_text() + "\n".join(lines) + "\n")


def test_finish_refusal_names_the_observed_outcome_for_a_failing_test(pm_git_project: Path) -> None:
    (pm_git_project / "test_thing.py").write_text("def test_bad():\n    assert False\n")
    append_bug(pm_git_project, 1)
    commit_all(pm_git_project, "add BUG-1 and a failing test")
    run_pm("start", "BUG-1", "--probe", "test:test_thing.py::test_bad", "--here", cwd=pm_git_project)
    commit_all(pm_git_project, "start BUG-1")

    result = run_pm("finish", "BUG-1", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_PROBE_REFUSED, result.stdout
    assert "fail" in result.stderr


def test_finish_refusal_names_deleted_baseline_files(pm_git_project: Path) -> None:
    # two files in the scanned directory, only one carrying the marker: deleting it leaves the
    # directory itself intact, so the scan comes back a clean "ok" (no `result.detail`) — the
    # missing-baseline-files reason would otherwise be indistinguishable from a bare refusal
    (pm_git_project / "src").mkdir()
    (pm_git_project / "src" / "a.txt").write_text("MARKER here\n")
    (pm_git_project / "src" / "b.txt").write_text("other content\n")
    append_bug(pm_git_project, 1)
    commit_all(pm_git_project, "add BUG-1 and src files")
    run_pm("start", "BUG-1", "--probe", "grep:MARKER -- src", "--here", cwd=pm_git_project)
    commit_all(pm_git_project, "start BUG-1")

    (pm_git_project / "src" / "a.txt").unlink()
    commit_all(pm_git_project, "delete a.txt without touching the marker's cause")

    result = run_pm("finish", "BUG-1", cwd=pm_git_project)

    assert result.returncode == pm.EXIT_PROBE_REFUSED, result.stdout
    assert "missing baseline files" in result.stderr
    assert "a.txt" in result.stderr
