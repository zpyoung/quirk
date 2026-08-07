from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "hooks"


def run_hook(name: str, project_dir: Path, **extra_env: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir), **extra_env}
    return subprocess.run(
        ["bash", str(HOOKS_DIR / name)],
        env=env,
        capture_output=True,
        text=True,
    )


def test_load_tail_suggests_init_when_no_artifacts(project_dir: Path) -> None:
    r = run_hook("load_artifact_tail.sh", project_dir)
    assert r.returncode == 0
    assert "/quirk:artifacts:init" in r.stdout


def test_load_tail_calls_pm_index_when_artifacts_exist(initialized_project: Path) -> None:
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: alpha\n- **Severity**: high\n")
    r = run_hook("load_artifact_tail.sh", initialized_project)
    assert r.returncode == 0
    assert "[quirk:pm]" in r.stdout
    assert "BUGS 1/1 open" in r.stdout


def test_load_tail_silent_when_project_dir_unset(project_dir: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    r = subprocess.run(
        ["bash", str(HOOKS_DIR / "load_artifact_tail.sh")],
        env=env, capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert r.stdout == ""


def test_load_tail_falls_back_when_pm_missing(initialized_project: Path, tmp_path: Path) -> None:
    fake_plugin_root = tmp_path / "fake_plugin_no_pm"
    fake_plugin_root.mkdir()
    r = run_hook("load_artifact_tail.sh", initialized_project, CLAUDE_PLUGIN_ROOT=str(fake_plugin_root))
    assert r.returncode == 0
    assert r.stdout.strip() == "[quirk:pm] index unavailable"


def test_load_tail_falls_back_when_pm_exits_nonzero(initialized_project: Path, tmp_path: Path) -> None:
    fake_plugin_root = tmp_path / "fake_plugin_bad_exit"
    (fake_plugin_root / "bin").mkdir(parents=True)
    (fake_plugin_root / "bin" / "pm.py").write_text("import sys\nsys.exit(1)\n")
    r = run_hook("load_artifact_tail.sh", initialized_project, CLAUDE_PLUGIN_ROOT=str(fake_plugin_root))
    assert r.returncode == 0
    assert r.stdout.strip() == "[quirk:pm] index unavailable"


def test_load_tail_suppresses_pm_traceback(initialized_project: Path, tmp_path: Path) -> None:
    fake_plugin_root = tmp_path / "fake_plugin_traceback"
    (fake_plugin_root / "bin").mkdir(parents=True)
    (fake_plugin_root / "bin" / "pm.py").write_text("raise RuntimeError('boom')\n")
    r = run_hook("load_artifact_tail.sh", initialized_project, CLAUDE_PLUGIN_ROOT=str(fake_plugin_root))
    assert r.returncode == 0
    assert r.stdout.strip() == "[quirk:pm] index unavailable"
    assert "Traceback" not in r.stdout
    assert "RuntimeError" not in r.stdout


def stdin_for_edit(file_path: Path) -> str:
    return json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(file_path)}})


def run_hook_with_stdin(name: str, stdin: str, project_dir: Path, **extra_env: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir), **extra_env}
    return subprocess.run(
        ["bash", str(HOOKS_DIR / name)],
        env=env, input=stdin, capture_output=True, text=True,
    )


def test_lint_tics_warns_on_match(initialized_project: Path) -> None:
    bad = initialized_project / "thing.py"
    bad.write_text("# this is a pre-existing thing — should be flagged\n")
    r = run_hook_with_stdin("lint_tics.sh", stdin_for_edit(bad), initialized_project)
    assert r.returncode == 0
    assert "pre-existing" in r.stdout.lower()
    assert "BUGS.md" in r.stdout


def test_lint_tics_silent_on_no_match(initialized_project: Path) -> None:
    ok = initialized_project / "thing.py"
    ok.write_text("# clean code\n")
    r = run_hook_with_stdin("lint_tics.sh", stdin_for_edit(ok), initialized_project)
    assert r.returncode == 0
    assert r.stdout == ""


def test_lint_tics_silent_on_binary(initialized_project: Path) -> None:
    bin_file = initialized_project / "thing.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03")
    r = run_hook_with_stdin("lint_tics.sh", stdin_for_edit(bin_file), initialized_project)
    assert r.returncode == 0
    assert r.stdout == ""


def test_lint_tics_silent_when_no_artifacts(project_dir: Path) -> None:
    f = project_dir / "x.py"
    f.write_text("pre-existing code here\n")
    r = run_hook_with_stdin("lint_tics.sh", stdin_for_edit(f), project_dir)
    assert r.returncode == 0
    assert r.stdout == ""  # no artifacts → don't warn


def test_wrap_session_emits_reminder_when_artifacts_exist(initialized_project: Path) -> None:
    r = run_hook("wrap_session.sh", initialized_project)
    assert r.returncode == 0
    assert "Route any unrouted observations" in r.stdout


def test_wrap_session_silent_when_no_artifacts(project_dir: Path) -> None:
    r = run_hook("wrap_session.sh", project_dir)
    assert r.returncode == 0
    assert r.stdout == ""


def test_hooks_json_structure() -> None:
    config = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text())
    hooks = config["hooks"]
    assert "SessionStart" in hooks
    assert "PostToolUse" in hooks
    assert "Stop" in hooks

    post = hooks["PostToolUse"][0]
    assert post["matcher"] == "Edit|Write"
    assert "lint_tics.sh" in post["hooks"][0]["command"]
    assert "${CLAUDE_PLUGIN_ROOT}" in post["hooks"][0]["command"]


def test_load_tail_names_the_work_not_just_the_count(initialized_project: Path) -> None:
    """A counts line alone tells a session nothing actionable; titles are the point."""
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: safari drops the session cookie\n- **Severity**: high\n")
    r = run_hook("load_artifact_tail.sh", initialized_project)
    assert r.returncode == 0
    assert "BUGS 1/1 open" in r.stdout
    assert "safari drops the session cookie" in r.stdout


def test_load_tail_does_not_repeat_the_unplaced_summary(initialized_project: Path) -> None:
    """--index and --next each end with it; emitting both would print it twice."""
    bugs = initialized_project / "BUGS.md"
    bugs.write_text(bugs.read_text() + "\n## BUG-1: alpha\n- **Severity**: high\n")
    r = run_hook("load_artifact_tail.sh", initialized_project)
    assert r.stdout.count("unplaced (") == 1


def test_load_tail_still_falls_back_when_next_fails(initialized_project: Path, tmp_path: Path) -> None:
    """The shortlist must not become a new way for session start to break."""
    fake_plugin_root = tmp_path / "plugin"
    (fake_plugin_root / "bin").mkdir(parents=True)
    (fake_plugin_root / "bin" / "pm.py").write_text(
        "import sys\n"
        "if '--next' in sys.argv:\n"
        "    sys.stderr.write('boom\\n'); sys.exit(1)\n"
        "print('[quirk:pm] BUGS 1/1 open')\n"
    )
    r = run_hook("load_artifact_tail.sh", initialized_project, CLAUDE_PLUGIN_ROOT=str(fake_plugin_root))
    assert r.returncode == 0
    assert "BUGS 1/1 open" in r.stdout
    assert "boom" not in r.stdout
