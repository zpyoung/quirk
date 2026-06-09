"""Tests for the Quirk bridge `wait` command — the blocking-wait transport.

`wait` blocks until a `{"type":"proceed",...}` record lands in the live server's
events file (`<screen_dir>/state/events`), then returns the selection. Proceeds are
filtered by `timestamp >= since` (the current screen's start), so a stale proceed
from a previous screen is ignored and re-running `wait` is a true continuation. The
poll is wrapped in a swappable transport so a Phase-2 channel can replace it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from .conftest import BIN_DIR, run_script

sys.path.insert(0, str(BIN_DIR))
import agent_isles


def _write_events(path: Path, *records: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def _setup_session(screen_dir: Path) -> Path:
    """A screen dir with a screen.md and a 'running' server-info; returns events path."""
    screen_dir.mkdir(parents=True, exist_ok=True)
    (screen_dir / "screen.md").write_text("# screen\n")
    state = screen_dir / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "server-info").write_text(json.dumps({"pid": os.getpid(), "url": "http://localhost:0"}))
    return state / "events"


# ---- latest_proceed_event: parse + timestamp filter -------------------------

def test_latest_proceed_event_none_when_missing(tmp_path: Path) -> None:
    assert agent_isles.latest_proceed_event(tmp_path / "events") is None


def test_latest_proceed_event_ignores_plain_clicks(tmp_path: Path) -> None:
    events = tmp_path / "events"
    _write_events(
        events,
        {"type": "click", "choice": "a", "selected": ["a"], "timestamp": 1},
        {"type": "click", "choice": "b", "selected": ["b"], "timestamp": 2},
    )
    assert agent_isles.latest_proceed_event(events) is None


def test_latest_proceed_event_returns_newest_proceed(tmp_path: Path) -> None:
    events = tmp_path / "events"
    _write_events(
        events,
        {"type": "click", "choice": "a", "selected": ["a"], "timestamp": 1},
        {"type": "proceed", "selected": ["a"], "timestamp": 1},
        {"type": "click", "choice": "b", "selected": ["b"], "timestamp": 2},
        {"type": "proceed", "selected": ["b"], "timestamp": 2},
    )
    event = agent_isles.latest_proceed_event(events)
    assert event is not None
    assert event["type"] == "proceed"
    assert event["selected"] == ["b"]
    assert event["timestamp"] == 2


def test_latest_proceed_event_skips_malformed_lines(tmp_path: Path) -> None:
    events = tmp_path / "events"
    events.parent.mkdir(parents=True, exist_ok=True)
    events.write_text(
        '{"type":"click","choice":"a"}\n'
        "not json at all\n"
        "\n"
        '{"type":"proceed","selected":["a"],"timestamp":5}\n'
    )
    event = agent_isles.latest_proceed_event(events)
    assert event is not None and event["selected"] == ["a"]


def test_latest_proceed_event_filters_by_since(tmp_path: Path) -> None:
    events = tmp_path / "events"
    _write_events(
        events,
        {"type": "proceed", "selected": ["old"], "timestamp": 100},
        {"type": "proceed", "selected": ["new"], "timestamp": 300},
    )
    assert agent_isles.latest_proceed_event(events, since=200)["selected"] == ["new"]
    assert agent_isles.latest_proceed_event(events, since=400) is None


# ---- wait_for_proceed: the transport-agnostic blocking loop ------------------

def test_wait_returns_immediately_when_transport_has_event() -> None:
    sleeps: list[float] = []
    event = {"type": "proceed", "selected": ["x"], "timestamp": 1}

    result = agent_isles.wait_for_proceed(
        lambda: event, timeout=10, poll_interval=0.5,
        _clock=lambda: 0.0, _sleep=sleeps.append,
    )

    assert result == event
    assert sleeps == []  # never slept; the event was already present


def test_wait_polls_until_event_appears() -> None:
    calls = {"n": 0}
    event = {"type": "proceed", "selected": ["y"], "timestamp": 2}

    def transport():
        calls["n"] += 1
        return event if calls["n"] >= 3 else None

    ticks = iter([0.0, 0.5, 1.0, 1.5, 2.0])
    result = agent_isles.wait_for_proceed(
        transport, timeout=10, poll_interval=0.5,
        _clock=lambda: next(ticks), _sleep=lambda _s: None,
    )

    assert result == event
    assert calls["n"] == 3


def test_wait_times_out_returns_none() -> None:
    ticks = iter([0.0, 0.4, 0.8, 1.2])  # exceeds timeout=1.0
    result = agent_isles.wait_for_proceed(
        lambda: None, timeout=1.0, poll_interval=0.3,
        _clock=lambda: next(ticks), _sleep=lambda _s: None,
    )
    assert result is None


# ---- make_file_transport: screen-scoped (timestamp) filtering ----------------

def test_file_transport_ignores_proceed_before_since(tmp_path: Path) -> None:
    # A stale proceed from a previous screen (older timestamp) must be ignored,
    # even if the live server failed to clear the events file.
    events = tmp_path / "state" / "events"
    _write_events(events, {"type": "proceed", "selected": ["stale"], "timestamp": 100})
    transport = agent_isles.make_file_transport(events, since=200)
    assert transport() is None


def test_file_transport_returns_proceed_at_or_after_since(tmp_path: Path) -> None:
    events = tmp_path / "state" / "events"
    _write_events(events, {"type": "click", "choice": "z", "timestamp": 210})
    transport = agent_isles.make_file_transport(events, since=200)
    assert transport() is None  # only a click so far
    with events.open("a") as fh:
        fh.write(json.dumps({"type": "proceed", "selected": ["z"], "timestamp": 250}) + "\n")
    assert transport()["selected"] == ["z"]


def test_file_transport_rerun_is_a_continuation(tmp_path: Path) -> None:
    # HIGH-1 regression: a proceed that arrives between turns must be seen by a
    # FRESH transport using the same `since` — re-running wait must not lose it.
    events = tmp_path / "state" / "events"
    _write_events(events, {"type": "click", "choice": "a", "timestamp": 210})
    first = agent_isles.make_file_transport(events, since=200)
    assert first() is None  # wait #1 sees nothing, times out

    with events.open("a") as fh:  # user clicks Proceed in the gap between turns
        fh.write(json.dumps({"type": "proceed", "selected": ["x"], "timestamp": 230}) + "\n")

    second = agent_isles.make_file_transport(events, since=200)  # wait #2, same since
    assert second()["selected"] == ["x"]  # continuation, NOT dropped


# ---- CLI: `agent_isles.py wait <dir>` ---------------------------------------

def test_wait_cli_blocks_then_returns_on_proceed(tmp_path: Path) -> None:
    # Mirrors the real flow: wait starts, THEN the user clicks Proceed.
    screen_dir = tmp_path / "session-1"
    events = _setup_session(screen_dir)

    proc = subprocess.Popen(
        [sys.executable, str(BIN_DIR / "agent_isles.py"), "wait", str(screen_dir),
         "--timeout", "5", "--poll-interval", "0.1", "--repo-root", str(tmp_path)],
        cwd=str(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )

    def _append_proceed() -> None:
        time.sleep(0.4)
        with events.open("a") as fh:
            fh.write(json.dumps(
                {"type": "proceed", "selected": ["two-column"], "timestamp": int(time.time())}
            ) + "\n")

    appender = threading.Thread(target=_append_proceed)
    appender.start()
    try:
        out, err = proc.communicate(timeout=15)
    finally:
        if proc.poll() is None:
            proc.kill()
        appender.join()

    assert proc.returncode == 0, err
    payload = json.loads(out)
    assert payload["type"] == "proceed"
    assert payload["selected"] == ["two-column"]


def test_wait_cli_ignores_stale_proceed(tmp_path: Path) -> None:
    # A stale proceed (timestamp older than the current screen) must not advance.
    screen_dir = tmp_path / "session-1"
    events = _setup_session(screen_dir)  # screen.md mtime ~now
    _write_events(events, {"type": "proceed", "selected": ["stale"], "timestamp": 1})

    result = run_script(
        "agent_isles.py", "wait", str(screen_dir), "--timeout", "0",
        "--repo-root", str(tmp_path), cwd=tmp_path,
    )
    assert result.returncode == 1
    assert "no proceed" in result.stderr.lower() or "timed out" in result.stderr.lower()


def test_wait_cli_times_out_nonzero_when_no_proceed(tmp_path: Path) -> None:
    screen_dir = tmp_path / "session-1"
    events = _setup_session(screen_dir)
    _write_events(events, {"type": "click", "choice": "a", "selected": ["a"], "timestamp": int(time.time())})

    result = run_script(
        "agent_isles.py", "wait", str(screen_dir), "--timeout", "0",
        "--repo-root", str(tmp_path), cwd=tmp_path,
    )

    assert result.returncode == 1
    assert "no proceed" in result.stderr.lower() or "timed out" in result.stderr.lower()


def test_wait_cli_missing_events_times_out(tmp_path: Path) -> None:
    screen_dir = tmp_path / "session-1"
    _setup_session(screen_dir)  # server up, screen present, but no events file
    result = run_script(
        "agent_isles.py", "wait", str(screen_dir), "--timeout", "0",
        "--repo-root", str(tmp_path), cwd=tmp_path,
    )
    assert result.returncode == 1


def test_wait_cli_no_server_exits_2(tmp_path: Path) -> None:
    # No live server (no server-info) → fast-fail, don't block uselessly.
    screen_dir = tmp_path / "session-1"
    screen_dir.mkdir(parents=True)
    (screen_dir / "screen.md").write_text("# screen\n")

    result = run_script(
        "agent_isles.py", "wait", str(screen_dir), "--timeout", "0",
        "--repo-root", str(tmp_path), cwd=tmp_path,
    )
    assert result.returncode == 2
    assert "server" in result.stderr.lower()


def test_wait_cli_stopped_server_exits_2(tmp_path: Path) -> None:
    screen_dir = tmp_path / "session-1"
    _setup_session(screen_dir)
    (screen_dir / "state" / "server-stopped").write_text("")

    result = run_script(
        "agent_isles.py", "wait", str(screen_dir), "--timeout", "0",
        "--repo-root", str(tmp_path), cwd=tmp_path,
    )
    assert result.returncode == 2
