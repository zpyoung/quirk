from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "subagent-driven-development" / "scripts"
SCRIPT = SCRIPTS_DIR / "sdd-ledger"


def run_ledger(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_append_is_append_only_and_accepts_payload_file(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    first_payload = json.dumps({"finding_id": "F1", "severity": "HIGH"})

    first = run_ledger(
        "append",
        "--run-dir", str(run_dir),
        "--agent", "captain-T1",
        "--namespace", "T1",
        "--type", "finding",
        "--payload", first_payload,
        cwd=tmp_path,
    )
    assert first.returncode == 0, first.stderr
    original = (run_dir / "run.jsonl").read_text()

    payload_file = tmp_path / "decision.json"
    payload_file.write_text(json.dumps({"choice": "keep API", "reason": "contract"}))
    second = run_ledger(
        "append",
        "--run-dir", str(run_dir),
        "--agent", "captain-T2",
        "--namespace", "T2",
        "--type", "decision",
        "--payload-file", str(payload_file),
        cwd=tmp_path,
    )

    assert second.returncode == 0, second.stderr
    ledger_text = (run_dir / "run.jsonl").read_text()
    assert ledger_text.startswith(original)
    records = [json.loads(line) for line in ledger_text.splitlines()]
    assert len(records) == 2
    assert records[0]["payload"] == {"finding_id": "F1", "severity": "HIGH"}
    assert records[1]["payload"] == {"choice": "keep API", "reason": "contract"}
    assert records[1]["type"] == "decision"
    assert records[1]["agent"] == "captain-T2"
    assert records[1]["namespace"] == "T2"
    assert all(record["ts"].endswith("Z") for record in records)


def test_append_rejects_types_outside_closed_set(tmp_path: Path) -> None:
    result = run_ledger(
        "append",
        "--run-dir", str(tmp_path / "run"),
        "--agent", "captain",
        "--namespace", "T1",
        "--type", "message",
        "--payload", "{}",
        cwd=tmp_path,
    )

    assert result.returncode != 0
    assert "invalid choice" in result.stderr.lower()
    assert not (tmp_path / "run" / "run.jsonl").exists()


def test_query_filters_and_missing_ledger_is_empty(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    records = [
        {
            "ts": "2026-07-21T10:00:00Z",
            "agent": "captain-T1",
            "namespace": "T1",
            "type": "decision",
            "payload": {"choice": "A"},
        },
        {
            "ts": "2026-07-21T10:00:01Z",
            "agent": "captain-T2",
            "namespace": "T2",
            "type": "decision",
            "payload": {"choice": "B"},
        },
        {
            "ts": "2026-07-21T10:00:02Z",
            "agent": "captain-T1",
            "namespace": "T1",
            "type": "finding",
            "payload": {"finding_id": "F1"},
        },
    ]
    (run_dir / "run.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records)
    )

    result = run_ledger(
        "query",
        "--run-dir", str(run_dir),
        "--type", "decision",
        "--agent", "captain-T1",
        "--namespace", "T1",
        cwd=tmp_path,
    )
    missing = run_ledger(
        "query", "--run-dir", str(tmp_path / "missing"), cwd=tmp_path
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [records[0]]
    assert missing.returncode == 0
    assert json.loads(missing.stdout) == []


def test_report_pairs_timestamp_events_into_deterministic_latency_table(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    records = [
        {
            "ts": "2026-07-21T12:00:00.000Z",
            "agent": "captain-T1",
            "namespace": "T1",
            "type": "timestamp",
            "payload": {"stage": "implement", "status": "start"},
        },
        {
            "ts": "2026-07-21T12:00:01.250Z",
            "agent": "captain-T1",
            "namespace": "T1",
            "type": "timestamp",
            "payload": {"stage": "implement", "status": "end"},
        },
        {
            "ts": "2026-07-21T12:00:02.000Z",
            "agent": "captain-T1",
            "namespace": "T1",
            "type": "timestamp",
            "payload": {"stage": "unpaired", "status": "start"},
        },
    ]
    (run_dir / "run.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records)
    )

    result = run_ledger("report", "--run-dir", str(run_dir), cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "AGENT\tNAMESPACE\tSTAGE\tSTART\tEND\tELAPSED_SECONDS",
        "captain-T1\tT1\timplement\t2026-07-21T12:00:00.000Z\t"
        "2026-07-21T12:00:01.250Z\t1.250",
    ]
