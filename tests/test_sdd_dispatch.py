from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "subagent-driven-development" / "scripts"
SCRIPT = SCRIPTS_DIR / "sdd-dispatch"


def run_dispatch(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def make_dispatcher(tmp_path: Path, body: str) -> Path:
    dispatcher = tmp_path / "fake-dispatcher"
    dispatcher.write_text("#!/usr/bin/env python3\n" + body)
    dispatcher.chmod(dispatcher.stat().st_mode | 0o111)
    return dispatcher


def test_missing_prompt_hard_fails_without_invoking_dispatcher(tmp_path: Path) -> None:
    marker = tmp_path / "invoked"
    dispatcher = make_dispatcher(
        tmp_path,
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('yes')\n",
    )

    result = run_dispatch(
        "--prompt", str(tmp_path / "missing.md"),
        "--provider", "p", "--model", "m", "--thinking", "high",
        "--dispatcher", str(dispatcher),
        cwd=tmp_path,
    )

    assert result.returncode != 0
    assert "missing prompt" in result.stderr.lower()
    assert not marker.exists()


def test_configured_dispatch_streams_and_writes_meta(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("do the staged work")
    config = tmp_path / "models.json"
    config.write_text(json.dumps({
        "implementer": {
            "provider": "configured-provider",
            "model": "configured-model",
            "thinking": "medium",
        }
    }))
    dispatcher = make_dispatcher(
        tmp_path,
        "import json, sys\n"
        "print(json.dumps(sys.argv[1:]), flush=True)\n"
        "print('known stderr', file=sys.stderr, flush=True)\n"
        "raise SystemExit(7)\n",
    )
    out_dir = tmp_path / "artifacts"

    result = run_dispatch(
        "--prompt", str(prompt),
        "--config", str(config),
        "--role", "implementer",
        "--tools", "read,bash,edit,write",
        "--dispatcher", str(dispatcher),
        "--out-dir", str(out_dir),
        cwd=tmp_path,
    )

    assert result.returncode == 7
    attempt = out_dir / "attempt-1"
    worker_args = json.loads((attempt / "worker.out").read_text())
    assert worker_args == [
        "--provider", "configured-provider",
        "--model", "configured-model",
        "--thinking", "medium",
        "--tools", "read,bash,edit,write",
        "do the staged work",
    ]
    assert "known stderr" in (attempt / "worker.err").read_text()
    assert json.loads(result.stdout) == worker_args
    assert "known stderr" in result.stderr

    meta = json.loads((attempt / "meta.json").read_text())
    assert meta["exit_code"] == 7
    assert meta["provider"] == "configured-provider"
    assert meta["model"] == "configured-model"
    assert meta["thinking"] == "medium"
    assert meta["start"].endswith("Z")
    assert meta["end"].endswith("Z")


def test_configured_triple_rejects_direct_overrides(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("do not dispatch")
    config = tmp_path / "models.json"
    config.write_text(json.dumps({
        "implementer": {
            "provider": "configured-provider",
            "model": "configured-model",
            "thinking": "medium",
        }
    }))
    marker = tmp_path / "invoked"
    dispatcher = make_dispatcher(
        tmp_path,
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('yes')\n",
    )

    result = run_dispatch(
        "--prompt", str(prompt),
        "--config", str(config),
        "--role", "implementer",
        "--model", "override-model",
        "--dispatcher", str(dispatcher),
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert "cannot be combined" in result.stderr
    assert "--config/--role" in result.stderr
    assert not marker.exists()


def test_timeout_preserves_partial_output_and_meta(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("slow work")
    dispatcher = make_dispatcher(
        tmp_path,
        "import sys, time\n"
        "print('partial stdout', flush=True)\n"
        "print('partial stderr', file=sys.stderr, flush=True)\n"
        "time.sleep(10)\n"
        "print('too late', flush=True)\n",
    )
    out_dir = tmp_path / "timeout-artifacts"

    result = run_dispatch(
        "--prompt", str(prompt),
        "--provider", "p", "--model", "m", "--thinking", "low",
        "--dispatcher", str(dispatcher),
        "--out-dir", str(out_dir),
        "--timeout", "0.2",
        cwd=tmp_path,
    )

    assert result.returncode == 124
    attempt = out_dir / "attempt-1"
    assert (attempt / "worker.out").read_text() == "partial stdout\n"
    assert (attempt / "worker.err").read_text() == "partial stderr\n"
    assert json.loads((attempt / "meta.json").read_text())["exit_code"] == 124


def test_timeout_kills_start_new_session_descendants(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("fork escaped work")
    child_pid_file = tmp_path / "child.pid"
    dispatcher = make_dispatcher(
        tmp_path,
        "import signal, subprocess, sys, time\n"
        "from pathlib import Path\n"
        "child = subprocess.Popen(\n"
        "    [sys.executable, '-c', "
        "'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)'],\n"
        "    start_new_session=True,\n"
        ")\n"
        f"Path({str(child_pid_file)!r}).write_text(str(child.pid))\n"
        "time.sleep(30)\n",
    )

    child_pid = None
    try:
        result = run_dispatch(
            "--prompt", str(prompt),
            "--provider", "p", "--model", "m", "--thinking", "low",
            "--dispatcher", str(dispatcher),
            "--out-dir", str(tmp_path / "escaped-child-artifacts"),
            "--timeout", "0.2",
            cwd=tmp_path,
        )
        child_pid = int(child_pid_file.read_text())

        assert result.returncode == 124
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
    finally:
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_repeated_out_dir_dispatches_preserve_monotonic_attempts(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    dispatcher = make_dispatcher(
        tmp_path,
        "import sys\nprint(sys.argv[-1], flush=True)\n",
    )
    out_dir = tmp_path / "dispatch" / "implementer"

    prompt.write_text("first attempt")
    first = run_dispatch(
        "--prompt", str(prompt),
        "--provider", "p", "--model", "m", "--thinking", "low",
        "--dispatcher", str(dispatcher),
        "--out-dir", str(out_dir),
        cwd=tmp_path,
    )
    prompt.write_text("second attempt")
    second = run_dispatch(
        "--prompt", str(prompt),
        "--provider", "p", "--model", "m", "--thinking", "low",
        "--dispatcher", str(dispatcher),
        "--out-dir", str(out_dir),
        cwd=tmp_path,
    )

    assert first.returncode == second.returncode == 0
    assert (out_dir / "attempt-1" / "worker.out").read_text() == "first attempt\n"
    assert (out_dir / "attempt-2" / "worker.out").read_text() == "second attempt\n"
    assert json.loads((out_dir / "attempt-1" / "meta.json").read_text())["exit_code"] == 0
    assert json.loads((out_dir / "attempt-2" / "meta.json").read_text())["exit_code"] == 0


def test_populated_out_dir_requires_explicit_opt_out(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("preserve evidence")
    dispatcher = make_dispatcher(tmp_path, "print('new evidence', flush=True)\n")
    out_dir = tmp_path / "dispatch" / "reviewer"
    out_dir.mkdir(parents=True)
    legacy = out_dir / "worker.out"
    legacy.write_text("old evidence\n")

    refused = run_dispatch(
        "--prompt", str(prompt),
        "--provider", "p", "--model", "m", "--thinking", "low",
        "--dispatcher", str(dispatcher),
        "--out-dir", str(out_dir),
        cwd=tmp_path,
    )
    allowed = run_dispatch(
        "--prompt", str(prompt),
        "--provider", "p", "--model", "m", "--thinking", "low",
        "--dispatcher", str(dispatcher),
        "--out-dir", str(out_dir),
        "--allow-populated-out-dir",
        cwd=tmp_path,
    )

    assert refused.returncode == 2
    assert "unmanaged artifacts" in refused.stderr
    assert allowed.returncode == 0
    assert legacy.read_text() == "old evidence\n"
    assert (out_dir / "attempt-1" / "worker.out").read_text() == "new evidence\n"


def test_timeout_bounds_inherited_pipes_after_dispatcher_exits(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("fork work")
    dispatcher = make_dispatcher(
        tmp_path,
        "import subprocess, sys\n"
        "subprocess.Popen(\n"
        "    [sys.executable, '-c', 'import time; time.sleep(3)'],\n"
        "    stdout=sys.stdout, stderr=sys.stderr, start_new_session=True,\n"
        ")\n",
    )
    out_dir = tmp_path / "inherited-pipe-artifacts"

    start = time.monotonic()
    result = run_dispatch(
        "--prompt", str(prompt),
        "--provider", "p", "--model", "m", "--thinking", "low",
        "--dispatcher", str(dispatcher),
        "--out-dir", str(out_dir),
        "--timeout", "0.15",
        cwd=tmp_path,
    )
    elapsed = time.monotonic() - start

    assert result.returncode == 124
    assert elapsed < 1.5
    assert json.loads((out_dir / "attempt-1" / "meta.json").read_text())["exit_code"] == 124
