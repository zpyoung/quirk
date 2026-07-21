from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "subagent-driven-development" / "scripts"
SCRIPT = SCRIPTS_DIR / "sdd-acceptance"


def run_acceptance(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_manifest_runs_every_command_verbatim_and_reports_failure(tmp_path: Path) -> None:
    commands = [
        "printf 'first output'",
        "printf 'second error' >&2; exit 6",
        "printf 'still ran'",
    ]
    manifest = tmp_path / "acceptance.json"
    manifest.write_text(json.dumps({"cwd": str(tmp_path), "commands": commands}))

    result = run_acceptance("--manifest", str(manifest), cwd=tmp_path)

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "fail"
    assert [item["command"] for item in payload["results"]] == commands
    assert payload["results"] == [
        {
            "command": commands[0],
            "exit_code": 0,
            "stdout": "first output",
            "stderr": "",
            "status": "pass",
        },
        {
            "command": commands[1],
            "exit_code": 6,
            "stdout": "",
            "stderr": "second error",
            "status": "fail",
        },
        {
            "command": commands[2],
            "exit_code": 0,
            "stdout": "still ran",
            "stderr": "",
            "status": "pass",
        },
    ]


def test_repeatable_cmd_preserves_shell_flags_and_uses_cwd(tmp_path: Path) -> None:
    cwd = tmp_path / "command-cwd"
    cwd.mkdir()
    (cwd / "needle.txt").write_text("--fixed-string -e value\n")
    command = "grep -F -- '--fixed-string -e value' needle.txt"

    result = run_acceptance(
        "--cwd", str(cwd),
        "--cmd", command,
        "--cmd", "test \"$(pwd)\" = \"$PWD\"",
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
    assert payload["results"][0]["command"] == command
    assert payload["results"][0]["stdout"] == "--fixed-string -e value\n"
    assert all(item["status"] == "pass" for item in payload["results"])


def test_non_utf8_output_is_replaced_without_changing_command_status(
    tmp_path: Path,
) -> None:
    command = (
        f"{shlex.quote(sys.executable)} "
        "-c \"import os; os.write(1, b'\\\\xff')\""
    )

    result = run_acceptance("--cmd", command, cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
    assert payload["results"][0]["status"] == "pass"
    assert payload["results"][0]["exit_code"] == 0
    assert payload["results"][0]["stdout"] == "\ufffd"


def test_requires_a_manifest_or_at_least_one_command(tmp_path: Path) -> None:
    result = run_acceptance("--cwd", str(tmp_path), cwd=tmp_path)

    assert result.returncode != 0
    assert "manifest" in result.stderr.lower()
    assert "--cmd" in result.stderr
