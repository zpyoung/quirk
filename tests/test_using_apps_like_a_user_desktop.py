"""Tests for skills/using-apps-like-a-user/scripts/_desktop.py.

CI-safe tests run every primitive against the JSON fake desktop. Darwin tests are read-only:
they never write the real clipboard and never warp the real cursor.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "using-apps-like-a-user" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _desktop  # noqa: E402
from _types import DriverError  # noqa: E402

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

BASE_STATE = {
    "cursor": [120.5, 80.0],
    "frontmost": "com.example.one",
    "clipboard_change_count": 7,
    "clipboard_text_only": True,
    "clipboard_text": "hello",
    "scale": 2.0,
    "permissions": {"accessibility": True, "screen_recording": False},
}


@pytest.fixture
def fake(tmp_path, monkeypatch):
    path = tmp_path / "desktop.json"
    path.write_text(json.dumps(BASE_STATE))
    monkeypatch.setenv("LIKEUSER_FAKE_DESKTOP", str(path))
    return path


def _state(path):
    return json.loads(path.read_text())


def test_cursor_reads_fake(fake):
    assert _desktop.cursor() == (120.5, 80.0)


def test_warp_cursor_writes_fake(fake):
    _desktop.warp_cursor(10.0, 20.5)
    assert _state(fake)["cursor"] == [10.0, 20.5]
    assert _desktop.cursor() == (10.0, 20.5)


def test_frontmost_reads_fake(fake):
    assert _desktop.frontmost_bundle_id() == "com.example.one"


def test_activate_changes_frontmost(fake):
    _desktop.activate("com.example.two")
    assert _desktop.frontmost_bundle_id() == "com.example.two"
    assert _state(fake)["frontmost"] == "com.example.two"


def test_bundle_id_for_pid_reads_the_fake_table(fake):
    state = _state(fake)
    state["pid_bundles"] = {"4242": "com.example.dev"}
    fake.write_text(json.dumps(state))
    assert _desktop.bundle_id_for_pid(4242) == "com.example.dev"
    assert _desktop.bundle_id_for_pid(1) is None


def test_clipboard_reads_fake(fake):
    assert _desktop.clipboard_change_count() == 7
    assert _desktop.clipboard_is_text_only() is True
    assert _desktop.clipboard_read_text() == "hello"


def test_clipboard_text_only_false_is_reported(fake):
    state = _state(fake)
    state["clipboard_text_only"] = False
    fake.write_text(json.dumps(state))
    assert _desktop.clipboard_is_text_only() is False


def test_clipboard_write_increments_change_count(fake):
    _desktop.clipboard_write_text("new text")
    assert _desktop.clipboard_change_count() == 8
    assert _desktop.clipboard_read_text() == "new text"
    assert _desktop.clipboard_is_text_only() is True
    _desktop.clipboard_write_text("again")
    assert _desktop.clipboard_change_count() == 9


def test_clipboard_write_restores_text_only(fake):
    state = _state(fake)
    state["clipboard_text_only"] = False
    fake.write_text(json.dumps(state))
    _desktop.clipboard_write_text("plain")
    assert _desktop.clipboard_is_text_only() is True


def test_display_scale_reads_fake(fake):
    assert _desktop.display_scale() == 2.0


def test_permissions_reads_fake(fake):
    assert _desktop.permissions() == {"accessibility": True, "screen_recording": False}


def test_screenshot_window_writes_png(fake, tmp_path):
    out = tmp_path / "shots" / "w.png"
    assert _desktop.screenshot_window(42, out) == out
    assert out.read_bytes().startswith(PNG_MAGIC)


def test_screenshot_window_bogus_id_fails(fake, tmp_path):
    out = tmp_path / "w.png"
    with pytest.raises(DriverError) as exc:
        _desktop.screenshot_window(0, out)
    assert exc.value.code == "screenshot_failed"
    assert not out.exists()


def test_fake_write_leaves_other_fields(fake):
    _desktop.activate("com.example.two")
    state = _state(fake)
    assert state["clipboard_text"] == "hello"
    assert state["scale"] == 2.0


def test_fake_missing_file_is_a_driver_error(tmp_path, monkeypatch):
    monkeypatch.setenv("LIKEUSER_FAKE_DESKTOP", str(tmp_path / "absent.json"))
    with pytest.raises(DriverError) as exc:
        _desktop.cursor()
    assert exc.value.code == "fake_desktop_unreadable"


def test_fake_malformed_file_is_a_driver_error(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    monkeypatch.setenv("LIKEUSER_FAKE_DESKTOP", str(bad))
    with pytest.raises(DriverError) as exc:
        _desktop.frontmost_bundle_id()
    assert exc.value.code == "fake_desktop_unreadable"


CALLS = [
    ("cursor", ()),
    ("warp_cursor", (1.0, 2.0)),
    ("frontmost_bundle_id", ()),
    ("activate", ("com.example.one",)),
    ("clipboard_change_count", ()),
    ("clipboard_is_text_only", ()),
    ("clipboard_read_text", ()),
    ("clipboard_write_text", ("x",)),
    ("display_scale", ()),
    ("screenshot_window", (1, Path("unused.png"))),
    ("permissions", ()),
]


@pytest.mark.parametrize("name,args", CALLS)
def test_off_darwin_without_fake_is_unsupported(name, args, monkeypatch):
    monkeypatch.delenv("LIKEUSER_FAKE_DESKTOP", raising=False)
    monkeypatch.setattr(_desktop, "_is_darwin", lambda: False)
    with pytest.raises(DriverError) as exc:
        getattr(_desktop, name)(*args)
    assert exc.value.code == "unsupported_platform"


@pytest.mark.parametrize("name,args", CALLS[:1] + CALLS[2:3])
def test_fake_takes_precedence_off_darwin(name, args, fake, monkeypatch):
    monkeypatch.setattr(_desktop, "_is_darwin", lambda: False)
    getattr(_desktop, name)(*args)


darwin_only = pytest.mark.skipif(sys.platform != "darwin", reason="needs macOS")


@pytest.fixture
def live(monkeypatch):
    monkeypatch.delenv("LIKEUSER_FAKE_DESKTOP", raising=False)


@darwin_only
def test_live_cursor_is_two_floats(live):
    x, y = _desktop.cursor()
    assert isinstance(x, float) and isinstance(y, float)


@darwin_only
@pytest.mark.skipif(shutil.which("lsappinfo") is None, reason="lsappinfo not installed")
def test_live_frontmost_is_dotted_id(live):
    bundle = _desktop.frontmost_bundle_id()
    assert bundle and "." in bundle and " " not in bundle


@darwin_only
def test_live_display_scale(live):
    assert _desktop.display_scale() in (1.0, 2.0)


@darwin_only
def test_live_permissions_are_bools(live):
    perms = _desktop.permissions()
    assert set(perms) == {"accessibility", "screen_recording"}
    assert all(isinstance(v, bool) for v in perms.values())


@darwin_only
def test_live_clipboard_change_count_is_int(live):
    assert isinstance(_desktop.clipboard_change_count(), int)


@darwin_only
def test_live_clipboard_is_text_only_is_bool(live):
    assert isinstance(_desktop.clipboard_is_text_only(), bool)


@darwin_only
def test_live_screenshot_bogus_window_fails(live, tmp_path):
    out = tmp_path / "bogus.png"
    with pytest.raises(DriverError) as exc:
        _desktop.screenshot_window(2147483000, out)
    assert exc.value.code == "screenshot_failed"
    assert not out.exists() or out.stat().st_size == 0


@darwin_only
def test_live_bundle_id_for_a_plain_process_is_none_or_a_string(live):
    import os

    found = _desktop.bundle_id_for_pid(os.getpid())
    assert found is None or isinstance(found, str)
