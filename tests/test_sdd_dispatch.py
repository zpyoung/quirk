from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

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
        "--model", "override-model",
        "--tools", "read,bash,edit,write",
        "--dispatcher", str(dispatcher),
        "--out-dir", str(out_dir),
        cwd=tmp_path,
    )

    assert result.returncode == 7
    worker_args = json.loads((out_dir / "worker.out").read_text())
    assert worker_args == [
        "--provider", "configured-provider",
        "--model", "override-model",
        "--thinking", "medium",
        "--tools", "read,bash,edit,write",
        "do the staged work",
    ]
    assert "known stderr" in (out_dir / "worker.err").read_text()
    assert json.loads(result.stdout) == worker_args
    assert "known stderr" in result.stderr

    meta = json.loads((out_dir / "meta.json").read_text())
    assert meta["exit_code"] == 7
    assert meta["provider"] == "configured-provider"
    assert meta["model"] == "override-model"
    assert meta["thinking"] == "medium"
    assert meta["start"].endswith("Z")
    assert meta["end"].endswith("Z")


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
    assert (out_dir / "worker.out").read_text() == "partial stdout\n"
    assert (out_dir / "worker.err").read_text() == "partial stderr\n"
    assert json.loads((out_dir / "meta.json").read_text())["exit_code"] == 124
