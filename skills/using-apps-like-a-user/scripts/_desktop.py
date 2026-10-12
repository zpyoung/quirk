"""macOS desktop primitives for the using-apps-like-a-user guard: cursor, frontmost app,
clipboard, display scale, window screenshots, and privacy permissions.

Real paths never prompt for a permission and never open System Settings. When
`LIKEUSER_FAKE_DESKTOP` names a JSON file, every function reads that file (and, for
`warp_cursor`, `activate`, and `clipboard_write_text`, writes it back) and never touches the
real desktop. Off darwin without the fake, every function raises
`DriverError("unsupported_platform")`.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Dict, Optional, Tuple

# loaded as a sibling of the other guard modules, which import each other as plain modules
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from _types import DriverError  # noqa: E402

FAKE_ENV = "LIKEUSER_FAKE_DESKTOP"
SUBPROCESS_TIMEOUT_S = 10.0

_FAKE_DEFAULTS = {
    "cursor": [0.0, 0.0],
    "frontmost": "",
    "clipboard_change_count": 0,
    "clipboard_text_only": True,
    "clipboard_text": "",
    "scale": 1.0,
    "permissions": {"accessibility": False, "screen_recording": False},
}

_PASTEBOARD_JXA = """
ObjC.import('AppKit');
var pb = $.NSPasteboard.generalPasteboard;
var items = pb.pasteboardItems;
var textOnly = true;
for (var i = 0; i < items.count; i++) {
  var types = items.objectAtIndex(i).types;
  for (var j = 0; j < types.count; j++) {
    var t = ObjC.unwrap(types.objectAtIndex(j));
    if (!/^public\\..*text$/.test(t)) { textOnly = false; }
  }
}
JSON.stringify({changeCount: Number(pb.changeCount), textOnly: textOnly});
"""

_SCALE_JXA = """
ObjC.import('AppKit');
String($.NSScreen.screens.objectAtIndex(0).backingScaleFactor);
"""


def _is_darwin() -> bool:
    return sys.platform == "darwin"


def _fake_path() -> Optional[Path]:
    raw = os.environ.get(FAKE_ENV)
    return Path(raw) if raw else None


def _require_real() -> None:
    if not _is_darwin():
        raise DriverError("unsupported_platform", f"{sys.platform} has no desktop primitives")


def _load_fake(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise DriverError("fake_desktop_unreadable", f"{path}: {exc}")
    if not isinstance(data, dict):
        raise DriverError("fake_desktop_unreadable", f"{path}: not a JSON object")
    merged = dict(_FAKE_DEFAULTS)
    merged.update(data)
    return merged


def _save_fake(path: Path, state: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state))
    os.replace(str(tmp), str(path))


def _run(argv, input_text: Optional[str] = None) -> str:
    try:
        proc = subprocess.run(
            argv, input=input_text, capture_output=True, text=True,
            timeout=SUBPROCESS_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DriverError("desktop_command_failed", f"{argv[0]}: {exc}")
    if proc.returncode != 0:
        raise DriverError("desktop_command_failed", f"{argv[0]}: {proc.stderr.strip()}")
    return proc.stdout


def _jxa(script: str) -> str:
    return _run(["osascript", "-l", "JavaScript", "-e", script]).strip()


def _framework(name: str):
    lib = ctypes.util.find_library(name)
    if not lib:
        raise DriverError("desktop_command_failed", f"framework {name} not found")
    return ctypes.cdll.LoadLibrary(lib)


class _CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


def cursor() -> Tuple[float, float]:
    """Return the pointer position in global points, origin top-left of the primary display."""
    fake = _fake_path()
    if fake:
        x, y = _load_fake(fake)["cursor"]
        return float(x), float(y)
    _require_real()
    quartz = _framework("CoreGraphics")
    foundation = _framework("CoreFoundation")
    quartz.CGEventCreate.restype = ctypes.c_void_p
    quartz.CGEventCreate.argtypes = [ctypes.c_void_p]
    quartz.CGEventGetLocation.restype = _CGPoint
    quartz.CGEventGetLocation.argtypes = [ctypes.c_void_p]
    foundation.CFRelease.argtypes = [ctypes.c_void_p]
    event = quartz.CGEventCreate(None)
    if not event:
        raise DriverError("desktop_command_failed", "CGEventCreate returned NULL")
    try:
        point = quartz.CGEventGetLocation(event)
    finally:
        foundation.CFRelease(event)
    return float(point.x), float(point.y)


def warp_cursor(x: float, y: float) -> None:
    """Move the pointer to global points (x, y). Test fixtures only: the guard never moves it."""
    fake = _fake_path()
    if fake:
        state = _load_fake(fake)
        state["cursor"] = [float(x), float(y)]
        _save_fake(fake, state)
        return
    _require_real()
    quartz = _framework("CoreGraphics")
    quartz.CGWarpMouseCursorPosition.argtypes = [_CGPoint]
    quartz.CGWarpMouseCursorPosition.restype = ctypes.c_int32
    if quartz.CGWarpMouseCursorPosition(_CGPoint(float(x), float(y))) != 0:
        raise DriverError("desktop_command_failed", "CGWarpMouseCursorPosition failed")


def frontmost_bundle_id() -> str:
    """Return the bundle id of the frontmost application, or "" when none reports one."""
    fake = _fake_path()
    if fake:
        return str(_load_fake(fake)["frontmost"])
    _require_real()
    front = _run(["lsappinfo", "front"]).strip()
    if not front:
        return ""
    out = _run(["lsappinfo", "info", "-only", "bundleid", front])
    if "=" not in out:
        return ""
    value = out.split("=", 1)[1].strip().strip('"')
    return "" if value.lower() == "[ null ]" else value


def activate(bundle_id: str) -> None:
    """Bring the application with `bundle_id` to the front."""
    fake = _fake_path()
    if fake:
        state = _load_fake(fake)
        state["frontmost"] = bundle_id
        _save_fake(fake, state)
        return
    _require_real()
    _jxa(f"Application({json.dumps(bundle_id)}).activate()")


def clipboard_change_count() -> int:
    """Return the general pasteboard's change count; it moves whenever anything writes it."""
    fake = _fake_path()
    if fake:
        return int(_load_fake(fake)["clipboard_change_count"])
    _require_real()
    return int(json.loads(_jxa(_PASTEBOARD_JXA))["changeCount"])


def clipboard_is_text_only() -> bool:
    """True when every pasteboard item carries only text types, so a text restore loses nothing."""
    fake = _fake_path()
    if fake:
        return bool(_load_fake(fake)["clipboard_text_only"])
    _require_real()
    return bool(json.loads(_jxa(_PASTEBOARD_JXA))["textOnly"])


def clipboard_read_text() -> str:
    """Return the pasteboard's plain text, or "" when it holds none."""
    fake = _fake_path()
    if fake:
        return str(_load_fake(fake)["clipboard_text"])
    _require_real()
    return _run(["pbpaste"])


def clipboard_write_text(text: str) -> None:
    """Replace the pasteboard with plain `text`, which bumps the change count."""
    fake = _fake_path()
    if fake:
        state = _load_fake(fake)
        state["clipboard_text"] = text
        state["clipboard_text_only"] = True
        state["clipboard_change_count"] = int(state["clipboard_change_count"]) + 1
        _save_fake(fake, state)
        return
    _require_real()
    _run(["pbcopy"], input_text=text)


def display_scale() -> float:
    """Return the primary display's backing scale factor (2.0 on Retina, 1.0 otherwise)."""
    fake = _fake_path()
    if fake:
        return float(_load_fake(fake)["scale"])
    _require_real()
    try:
        return float(_jxa(_SCALE_JXA))
    except ValueError as exc:
        raise DriverError("desktop_command_failed", f"unreadable backing scale: {exc}")


def _blank_png(size: int = 8) -> bytes:
    def chunk(tag: bytes, body: bytes) -> bytes:
        crc = zlib.crc32(tag + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", crc)

    rows = b"".join(b"\x00" + b"\xff" * (size * 3) for _ in range(size))
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def screenshot_window(window_id: int, out: Path) -> Path:
    """Capture window `window_id` to the PNG `out` and return `out`.

    Raises DriverError("screenshot_failed") when no file was written; `screencapture` exits 0
    on failure, so the file itself is the only reliable signal.
    """
    out = Path(out)
    fake = _fake_path()
    if fake:
        _load_fake(fake)
        if window_id <= 0:
            raise DriverError("screenshot_failed", f"no window {window_id}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(_blank_png())
        return out
    _require_real()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    detail = ""
    try:
        proc = subprocess.run(
            ["screencapture", "-x", "-o", "-l", str(int(window_id)), str(out)],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_S,
        )
        detail = proc.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        detail = str(exc)
    if not out.exists() or out.stat().st_size == 0:
        out.unlink(missing_ok=True)
        raise DriverError("screenshot_failed", detail or f"no window {window_id}")
    return out


def permissions() -> Dict[str, bool]:
    """Report Accessibility and Screen Recording grants without prompting for either."""
    fake = _fake_path()
    if fake:
        granted = _load_fake(fake)["permissions"]
        return {
            "accessibility": bool(granted.get("accessibility", False)),
            "screen_recording": bool(granted.get("screen_recording", False)),
        }
    _require_real()
    services = _framework("ApplicationServices")
    quartz = _framework("CoreGraphics")
    services.AXIsProcessTrusted.restype = ctypes.c_bool
    services.AXIsProcessTrusted.argtypes = []
    quartz.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
    quartz.CGPreflightScreenCaptureAccess.argtypes = []
    return {
        "accessibility": bool(services.AXIsProcessTrusted()),
        "screen_recording": bool(quartz.CGPreflightScreenCaptureAccess()),
    }
