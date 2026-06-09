"""Tests for the Quirk bridge `wait` command — the blocking-wait transport.

`wait` blocks until a `{"type":"proceed",...}` record lands in the live server's
events file (`<screen_dir>/state/events`), then returns the selection. The poll is
wrapped in a swappable transport so a Claude Code channel can replace the file poll
in Phase 2 without changing the wait loop.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .conftest import BIN_DIR, run_script

sys.path.insert(0, str(BIN_DIR))
import agent_isles


# ---- latest_proceed_event: parse the JSONL events file ----------------------

def _write_events(path: Path, *records: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def test_latest_proceed_event_none_when_missing(tmp_path: Path) -> None:
    assert agent_isles.latest_proceed_event(tmp_path / "events") is None


def test_latest_proceed_event_ignores_plain_clicks(tmp_path: Path) -> None:
    events = tmp_path / "events"
    _write_events(
        events,
        {"type": "click", "choice": "a", "selected": ["a"]},
        {"type": "click", "choice": "b", "selected": ["b"]},
    )
    assert agent_isles.latest_proceed_event(events) is None


def test_latest_proceed_event_returns_newest_proceed(tmp_path: Path) -> None:
    events = tmp_path / "events"
    _write_events(
        events,
        {"type": "click", "choice": "a", "selected": ["a"]},
        {"type": "proceed", "selected": ["a"], "ts": 1},
        {"type": "click", "choice": "b", "selected": ["b"]},
        {"type": "proceed", "selected": ["b"], "ts": 2},
    )
    event = agent_isles.latest_proceed_event(events)
    assert event is not None
    assert event["type"] == "proceed"
    assert event["selected"] == ["b"]
    assert event["ts"] == 2


def test_latest_proceed_event_skips_malformed_lines(tmp_path: Path) -> None:
    events = tmp_path / "events"
    events.parent.mkdir(parents=True, exist_ok=True)
    events.write_text(
        '{"type":"click","choice":"a"}\n'
        "not json at all\n"
        "\n"
        '{"type":"proceed","selected":["a"],"ts":5}\n'
    )
    event = agent_isles.latest_proceed_event(events)
    assert event is not None and event["selected"] == ["a"]


# ---- wait_for_proceed: the transport-agnostic blocking loop ------------------

def test_wait_returns_immediately_when_transport_has_event() -> None:
    sleeps: list[float] = []
    event = {"type": "proceed", "selected": ["x"], "ts": 1}

    result = agent_isles.wait_for_proceed(
        lambda: event,
        timeout=10,
        poll_interval=0.5,
        _clock=lambda: 0.0,
        _sleep=sleeps.append,
    )

    assert result == event
    assert sleeps == []  # never slept; the event was already present


def test_wait_polls_until_event_appears() -> None:
    calls = {"n": 0}
    event = {"type": "proceed", "selected": ["y"], "ts": 2}

    def transport():
        calls["n"] += 1
        return event if calls["n"] >= 3 else None

    ticks = iter([0.0, 0.5, 1.0, 1.5, 2.0])
    result = agent_isles.wait_for_proceed(
        transport,
        timeout=10,
        poll_interval=0.5,
        _clock=lambda: next(ticks),
        _sleep=lambda _s: None,
    )

    assert result == event
    assert calls["n"] == 3


def test_wait_times_out_returns_none() -> None:
    ticks = iter([0.0, 0.4, 0.8, 1.2])  # exceeds timeout=1.0
    result = agent_isles.wait_for_proceed(
        lambda: None,
        timeout=1.0,
        poll_interval=0.3,
        _clock=lambda: next(ticks),
        _sleep=lambda _s: None,
    )
    assert result is None


def test_file_transport_reads_proceed(tmp_path: Path) -> None:
    events = tmp_path / "state" / "events"
    _write_events(events, {"type": "proceed", "selected": ["z"], "ts": 9})
    transport = agent_isles.make_file_transport(events)
    assert transport() == {"type": "proceed", "selected": ["z"], "ts": 9}


# ---- CLI: `agent_isles.py wait <dir>` ---------------------------------------

def test_wait_cli_prints_selection_on_proceed(tmp_path: Path) -> None:
    screen_dir = tmp_path / "session-1"
    events = screen_dir / "state" / "events"
    _write_events(
        events,
        {"type": "click", "choice": "two-column", "selected": ["two-column"]},
        {"type": "proceed", "selected": ["two-column"], "ts": 1781003090},
    )

    result = run_script(
        "agent_isles.py", "wait", str(screen_dir), "--timeout", "0",
        "--repo-root", str(tmp_path), cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["type"] == "proceed"
    assert payload["selected"] == ["two-column"]


def test_wait_cli_times_out_nonzero_when_no_proceed(tmp_path: Path) -> None:
    screen_dir = tmp_path / "session-1"
    events = screen_dir / "state" / "events"
    _write_events(events, {"type": "click", "choice": "a", "selected": ["a"]})

    result = run_script(
        "agent_isles.py", "wait", str(screen_dir), "--timeout", "0",
        "--repo-root", str(tmp_path), cwd=tmp_path,
    )

    assert result.returncode == 1
    assert "no proceed" in result.stderr.lower() or "timed out" in result.stderr.lower()


def test_wait_cli_missing_events_times_out(tmp_path: Path) -> None:
    screen_dir = tmp_path / "session-1"
    screen_dir.mkdir()
    result = run_script(
        "agent_isles.py", "wait", str(screen_dir), "--timeout", "0",
        "--repo-root", str(tmp_path), cwd=tmp_path,
    )
    assert result.returncode == 1
