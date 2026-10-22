"""Tests for the making-videos HyperFrames wrapper (hf.py), run through subprocess with a fake pnpm."""
from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "making-videos" / "scripts"
HF_PY = SCRIPTS / "hf.py"

_spec = importlib.util.spec_from_file_location("mv_common_for_hf_tests", SCRIPTS / "_mv_common.py")
common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(common)

FAKE_PNPM = """#!{python}
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
with open(os.environ["FAKE_ENV_DUMP"], "w") as fh:
    json.dump(dict(os.environ), fh)
sys.stdout.write("child-out\\n")
sys.stderr.write("child-err\\n")
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
"""


@pytest.fixture()
def env(tmp_path: Path) -> dict:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    pnpm = bin_dir / "pnpm"
    pnpm.write_text(FAKE_PNPM.format(python=sys.executable), encoding="utf-8")
    pnpm.chmod(pnpm.stat().st_mode | stat.S_IXUSR)
    env = {
        "PATH": str(bin_dir),
        "HOME": str(tmp_path / "home"),
        "QUIRK_STUDIO": str(tmp_path / "studio"),
        "QUIRK_VIDEO_CACHE": str(tmp_path / "cache"),
        "FAKE_LOG": str(tmp_path / "pnpm.log"),
        "FAKE_ENV_DUMP": str(tmp_path / "pnpm-env.json"),
    }
    for name in common.SCRUB_ENV:
        env[name] = "secret-" + name
    return env


def run_hf(*args: object, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HF_PY), *map(str, args)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def child_argv(env: dict) -> list:
    lines = Path(env["FAKE_LOG"]).read_text().splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


def test_runs_pinned_hyperframes_and_passes_output_through(env):
    env["FAKE_EXIT"] = "0"
    proc = run_hf("--", "check", "--json", env=env)
    assert proc.returncode == 0
    assert proc.stdout == "child-out\n"
    assert "child-err" in proc.stderr
    assert child_argv(env) == ["dlx", f"hyperframes@{common.HYPERFRAMES_VERSION}", "check", "--json"]


def test_exit_code_is_the_childs(env):
    env["FAKE_EXIT"] = "7"
    proc = run_hf("--", "render", env=env)
    assert proc.returncode == 7
    assert proc.stdout == "child-out\n"


def test_telemetry_and_skills_env_set_and_secrets_scrubbed(env):
    proc = run_hf("--", "check", env=env)
    assert proc.returncode == 0
    child_env = json.loads(Path(env["FAKE_ENV_DUMP"]).read_text())
    assert child_env["HYPERFRAMES_NO_TELEMETRY"] == "1"
    assert child_env["DO_NOT_TRACK"] == "1"
    assert child_env["HYPERFRAMES_SKIP_SKILLS"] == "1"
    for name in common.SCRUB_ENV:
        assert name in env
        assert name not in child_env
    assert "GEMINI_API_KEY" in common.SCRUB_ENV


def test_snapshot_gets_describe_false_injected(env):
    proc = run_hf("--", "snapshot", "--at", "1.5", env=env)
    assert proc.returncode == 0
    argv = child_argv(env)
    assert argv[2:] == ["snapshot", "--at", "1.5", "--describe", "false"]


@pytest.mark.parametrize(
    "given",
    [
        ["--describe", "false"],
        ["--describe=false"],
        ["--describe", "false", "--describe=false"],
    ],
)
def test_snapshot_describe_false_is_kept_as_given(env, given):
    proc = run_hf("--", "snapshot", *given, env=env)
    assert proc.returncode == 0
    argv = child_argv(env)
    assert argv[2:] == ["snapshot", *given]


@pytest.mark.parametrize(
    "given",
    [
        ["--describe", "true"],
        ["--describe=true"],
        ["--describe", "TRUE"],
        ["--describe"],
        ["--describe", "false", "--describe", "true"],
        ["--describe", "true", "--describe", "false"],
        ["--describe=false", "--describe=true"],
        ["--describe=true", "--describe=false"],
        ["--describe", "false", "--describe=true"],
        ["--describe=false", "--describe", "true"],
        ["--describe", "false", "--describe"],
    ],
)
def test_snapshot_describe_true_is_refused_without_running_child(env, tmp_path, given):
    proc = run_hf("--", "snapshot", *given, env=env)
    assert proc.returncode == 2
    out = json.loads(proc.stdout)
    assert "describe" in out["error"]
    assert not Path(env["FAKE_LOG"]).exists()


def test_describe_is_untouched_for_other_subcommands(env):
    proc = run_hf("--", "render", "--out", "x.mp4", env=env)
    assert proc.returncode == 0
    assert child_argv(env)[2:] == ["render", "--out", "x.mp4"]


def test_missing_pnpm_names_doctor_and_exits_3(env, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    env["PATH"] = str(empty)
    proc = run_hf("--", "check", env=env)
    assert proc.returncode == 3
    out = json.loads(proc.stdout)
    assert "doctor.py check" in out["error"]
    assert not Path(env["FAKE_LOG"]).exists()


def test_project_logs_a_hyperframes_call(env, tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    proc = run_hf("--project", project, "--", "render", "--out", "x.mp4", env=env)
    assert proc.returncode == 0
    records = [json.loads(line) for line in (project / "calls.jsonl").read_text().splitlines()]
    assert len(records) == 1
    assert records[0]["provider"] == "hyperframes"
    assert records[0]["subcommand"] == "render"


def test_project_log_survives_child_failure(env, tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    env["FAKE_EXIT"] = "4"
    proc = run_hf("--project", project, "--", "render", env=env)
    assert proc.returncode == 4
    record = json.loads((project / "calls.jsonl").read_text().splitlines()[0])
    assert record["status"] == 4


def test_missing_project_directory_fails_without_running_child(env, tmp_path):
    proc = run_hf("--project", tmp_path / "nope", "--", "render", env=env)
    assert proc.returncode == 1
    assert "project" in json.loads(proc.stdout)["error"]
    assert not Path(env["FAKE_LOG"]).exists()


def test_without_arguments_is_a_usage_error(env):
    proc = run_hf(env=env)
    assert proc.returncode == 2
    assert "error" in json.loads(proc.stdout)
    proc = run_hf("--", env=env)
    assert proc.returncode == 2


def test_never_touches_hyperframes_global_config(env, tmp_path):
    run_hf("--", "check", env=env)
    assert not (tmp_path / "home").exists()
