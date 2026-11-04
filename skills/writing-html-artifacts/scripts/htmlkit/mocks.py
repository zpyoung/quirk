"""Pure helpers for the UX-review mock registry: input validation, pin ids, the harness page and exports.

Nothing here touches session state; ``companion.py`` and ``appstate.py`` call these so the server,
``mock``/``mock-export`` and the tests share one definition of a valid screens file and pin id.
"""
from __future__ import annotations

import datetime
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from . import SKILL_DIR

MAX_MOCK_BYTES = 5 * 1024 * 1024
MAX_VERSION = 9999
MAX_SCREENS = 50
MAX_STATES = 8
MAX_CHANGED = 500
HARNESS_ENV = "QUIRK_MOCK_HARNESS"
BOOT_PLACEHOLDER = '<script id="quirk-mock-boot" type="application/json">null</script>'
CORE_PLACEHOLDER = "<!--quirk-harness-core-->"
NO_UI_LAYER = "none (no UI layer)"

SCREEN_ID_RE = re.compile(r"[a-z0-9-]{1,40}")
PIN_KEY_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,79}")
PIN_BLOCK_RE = re.compile(
    r"mock:v([1-9][0-9]{0,3})/([a-z0-9-]{1,40})/([a-z0-9-]{1,40})/([a-z0-9][a-z0-9._-]{0,79})/x([0-9]{1,3})-y([0-9]{1,3})"
)


class MockError(ValueError):
    """Invalid mock input; ``field`` is the path of the offending key ("" for the root)."""

    def __init__(self, message: str, field: str = ""):
        super().__init__(message)
        self.field = field


def _bad(path: str, message: str) -> MockError:
    return MockError(f"{path or 'file'}: {message}", field=path)


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _object(value: Any, path: str, allowed: set[str]) -> dict:
    if not isinstance(value, dict):
        raise _bad(path, "must be an object")
    for key in value:
        if key not in allowed:
            raise _bad(_join(path, str(key)), "unknown field")
    return value


def _text(value: Any, path: str, limit: int) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= limit:
        raise _bad(path, f"must be a string of 1 to {limit} characters")
    return value


def _ident(value: Any, path: str, pattern: re.Pattern) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise _bad(path, f"must match {pattern.pattern}")
    return value


def _reject_unencodable(value: Any, path: str) -> None:
    """Raises ``MockError`` for a string (value or key) that UTF-8 cannot encode, such as a lone surrogate.

    JSON text can carry ``"\\ud800"``; stored as-is it would fail the registry write after validation passed.
    """
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise _bad(path, "must not contain an unpaired surrogate") from None
    elif isinstance(value, dict):
        for key, item in value.items():
            sub = _join(path, str(key)) if isinstance(key, str) and key.isascii() else _join(path, "<key>")
            _reject_unencodable(key, sub)
            _reject_unencodable(item, sub)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _reject_unencodable(item, f"{path}[{i}]")


def _present(obj: dict, key: str, path: str) -> Any:
    if key not in obj:
        raise _bad(_join(path, key), "is required")
    return obj[key]


def validate_screens(raw: Any) -> dict:
    """The screens inventory as a deep copy; raises ``MockError`` naming the first offending field."""
    _reject_unencodable(raw, "")
    root = _object(raw, "", {"ui_layer", "screens"})
    if not isinstance(_present(root, "ui_layer", ""), bool):
        raise _bad("ui_layer", "must be true or false")
    screens = _present(root, "screens", "")
    if not isinstance(screens, list) or not 1 <= len(screens) <= MAX_SCREENS:
        raise _bad("screens", f"must be a list of 1 to {MAX_SCREENS} screens")
    seen: set[str] = set()
    for i, screen in enumerate(screens):
        path = f"screens[{i}]"
        item = _object(screen, path, {"id", "title", "purpose", "states", "skipped_states", "elements"})
        sid = _ident(_present(item, "id", path), f"{path}.id", SCREEN_ID_RE)
        if sid in seen:
            raise _bad(f"{path}.id", "duplicate screen id")
        seen.add(sid)
        _text(_present(item, "title", path), f"{path}.title", 80)
        _text(_present(item, "purpose", path), f"{path}.purpose", 200)
        _validate_states(_present(item, "states", path), f"{path}.states")
        if "skipped_states" in item:
            _validate_skipped(item["skipped_states"], f"{path}.skipped_states")
        if "elements" in item:
            _validate_elements(item["elements"], f"{path}.elements")
    return json.loads(json.dumps(root))


def _validate_states(states: Any, path: str) -> None:
    if not isinstance(states, list) or not 1 <= len(states) <= MAX_STATES:
        raise _bad(path, f"must be a list of 1 to {MAX_STATES} state ids")
    seen: set[str] = set()
    for j, state in enumerate(states):
        _ident(state, f"{path}[{j}]", SCREEN_ID_RE)
        if state in seen:
            raise _bad(f"{path}[{j}]", "duplicate state id")
        seen.add(state)


def _validate_skipped(skipped: Any, path: str) -> None:
    if not isinstance(skipped, list):
        raise _bad(path, "must be a list")
    for j, entry in enumerate(skipped):
        sub = f"{path}[{j}]"
        item = _object(entry, sub, {"state", "reason"})
        _ident(_present(item, "state", sub), f"{sub}.state", SCREEN_ID_RE)
        _text(_present(item, "reason", sub), f"{sub}.reason", 200)


def _validate_elements(elements: Any, path: str) -> None:
    if not isinstance(elements, list):
        raise _bad(path, "must be a list")
    seen: set[str] = set()
    for j, entry in enumerate(elements):
        sub = f"{path}[{j}]"
        item = _object(entry, sub, {"pin", "label", "component"})
        pin = _ident(_present(item, "pin", sub), f"{sub}.pin", PIN_KEY_RE)
        if pin in seen:
            raise _bad(f"{sub}.pin", "duplicate pin key on this screen")
        seen.add(pin)
        _text(_present(item, "label", sub), f"{sub}.label", 200)
        component = _present(item, "component", sub)
        if component is not None:
            _text(component, f"{sub}.component", 120)


def validate_changed(raw: Any) -> list[str]:
    """The pin keys of a ``--changed`` file; raises ``MockError`` for a malformed file."""
    _reject_unencodable(raw, "")
    root = _object(raw, "", {"changed"})
    keys = _present(root, "changed", "")
    if not isinstance(keys, list) or len(keys) > MAX_CHANGED:
        raise _bad("changed", f"must be a list of at most {MAX_CHANGED} pin keys")
    for i, key in enumerate(keys):
        _ident(key, f"changed[{i}]", PIN_KEY_RE)
    return list(keys)


def parse_pin(block_id: Any) -> Optional[dict]:
    """The parts of a pin block id, or None when ``block_id`` is not a pin (including x or y over 100)."""
    if not isinstance(block_id, str):
        return None
    m = PIN_BLOCK_RE.fullmatch(block_id)
    if m is None:
        return None
    x, y = int(m.group(5)), int(m.group(6))
    if x > 100 or y > 100:
        return None
    return {"version": int(m.group(1)), "screen": m.group(2), "state": m.group(3), "pin": m.group(4), "x": x, "y": y}


# ---- harness page ------------------------------------------------------------------------------


def make_boot(*, mode: str, version: int, latest: int, versions: list[int], screens: dict, changed: list[str],
              mock_html: str, token: Optional[str] = None) -> dict:
    """The boot JSON the harness reads; ``token`` is only ever present in app mode."""
    boot: dict[str, Any] = {"mode": mode, "version": version, "latest": latest, "versions": versions}
    if token is not None:
        boot["token"] = token
    boot.update({"screens": screens, "changed": changed, "mock_html": mock_html})
    return boot


def load_template() -> tuple[str, str]:
    """The harness template and its core script; ``MockError`` when either cannot be read."""
    override = os.environ.get(HARNESS_ENV)
    template = Path(override) if override else SKILL_DIR / "companion-app" / "harness" / "mock-harness.html"
    try:
        return (
            template.read_text(encoding="utf-8"),
            template.with_name("harness-core.js").read_text(encoding="utf-8"),
        )
    except (OSError, UnicodeError) as exc:
        raise MockError("mock harness missing") from exc


def fill_template(template: str, core_js: str, boot: dict) -> str:
    """The harness page with the boot JSON and core script inlined; ``MockError`` unless each placeholder occurs once."""
    if template.count(BOOT_PLACEHOLDER) != 1 or template.count(CORE_PLACEHOLDER) != 1:
        raise MockError("mock harness missing")
    boot_json = json.dumps(boot, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")
    core = re.sub(r"</(script)", r"<\\/\1", core_js, flags=re.IGNORECASE)
    page = template.replace(BOOT_PLACEHOLDER, BOOT_PLACEHOLDER.replace("null", boot_json))
    return page.replace(CORE_PLACEHOLDER, f"<script>{core}</script>")


# ---- exports -----------------------------------------------------------------------------------


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def screens_markdown(screens: dict, version: int) -> str:
    """The inventory as markdown: one table per screen, then the list of gaps."""
    ui_layer = screens["ui_layer"]
    lines = [f"# Screens (mock v{version})", ""]
    gaps: list[str] = []
    for screen in screens["screens"]:
        lines += [f"## {_cell(screen['title'])} (`{screen['id']}`)", "", _cell(screen["purpose"]), ""]
        lines += ["| Kind | Name | Notes |", "|---|---|---|"]
        for n, state in enumerate(screen["states"]):
            lines.append(f"| state | {state} | {'default' if n == 0 else ''} |")
        for entry in screen.get("skipped_states", []):
            lines.append(f"| skipped state | {entry['state']} | {_cell(entry['reason'])} |")
        for element in screen.get("elements", []):
            component = element["component"]
            if not ui_layer:
                note = NO_UI_LAYER
            elif component is None:
                note = "gap"
                gaps.append(f"- {_cell(screen['title'])} / {_cell(element['label'])} (`{element['pin']}`)")
            else:
                note = _cell(component)
            lines.append(f"| element | {_cell(element['label'])} (`{element['pin']}`) | {note} |")
        lines.append("")
    lines += ["## Gaps", ""]
    lines += gaps or ["None."]
    return "\n".join(lines) + "\n"


def _iso(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.datetime.fromtimestamp(value, datetime.timezone.utc).isoformat(timespec="seconds")
    return str(value)


def build_review(version: int, threads: list[dict], exported_at: str) -> dict:
    """``review.json``: every thread whose block id is a pin, with its messages and resolution."""
    pins = []
    for thread in threads:
        pin = parse_pin(thread.get("block_id"))
        if pin is None:
            continue
        pins.append({
            "thread_id": thread["id"],
            "version": pin["version"],
            "screen": pin["screen"],
            "state": pin["state"],
            "pin": pin["pin"],
            "messages": [
                {"from": m.get("from"), "text": m.get("text"), "timestamp": _iso(m.get("timestamp"))}
                for m in thread.get("messages", [])
            ],
            "resolution": thread.get("resolution"),
        })
    return {"version": version, "exported_at": exported_at, "pins": pins}


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
