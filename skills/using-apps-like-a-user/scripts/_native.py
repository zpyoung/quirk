"""Native driver adapters for the using-apps-like-a-user guard script.

A native driver observes and acts on one bound macOS app window. The only adapter shipped is
`orca computer`; `NATIVE_DRIVER_PREFERENCE` names the adapters `get_native_driver` tries, best
first.
"""

from __future__ import annotations

import abc
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from _types import Action, DriverError, DriverResult, MissingError, Observation  # noqa: E402

NATIVE_DRIVER_PREFERENCE: List[str] = ["orca"]

_ORCA_TIMEOUT_S = 60.0
_GONE_CODES = ("window_not_found", "window_stale")

_ROLES = sorted(
    [
        "standard window", "window", "dialog", "sheet", "floating window", "system dialog",
        "close button", "minimize button", "full screen button", "zoom button", "pop up button",
        "radio button", "menu button", "button", "toggle", "check box", "disclosure triangle",
        "secure text field", "search text field", "text field", "text area", "text", "static text",
        "heading", "link", "image", "web area", "HTML content", "scroll area", "scroll bar",
        "split group", "group", "tab group", "tab", "toolbar", "table", "outline", "list", "row",
        "column", "cell", "menu bar item", "menu bar", "menu item", "menu", "combo box", "slider",
        "stepper", "progress indicator", "splitter", "container", "generic",
    ],
    key=len,
    reverse=True,
)
_ROLE_RE = re.compile(r"^(" + "|".join(re.escape(r) for r in _ROLES) + r")(?= |$|,)")
_FLAGS_RE = re.compile(r"^(?:\s*\([a-z][a-z ,]*\))+")
_LINE_RE = re.compile(r"^(\t*)(\d+) (.*)$")
_VALUE_SEP = ", Value: "
_ACTIONS_SEP = ", Secondary Actions:"

_CHROME_ROLES = frozenset(
    ["standard window", "window", "close button", "minimize button", "full screen button", "zoom button"]
)
_CONTAINER_ROLES = frozenset(
    ["web area", "HTML content", "group", "scroll area", "split group", "container", "generic"]
)

_REQUIRED_ACTIONS = ("click", "typeText", "pressKey", "hotkey")


class NativeDriver(abc.ABC):
    """A driver bound to one native app window.

    `observe` and `act` target only the bound bundle id and window id. `act(..., foreground=False)`
    must never activate another app; an adapter that cannot guarantee that for an action raises
    `DriverError("needs_foreground")`. A vanished window raises `DriverError("window_gone")`.
    """

    name: str = ""
    version: str = ""
    background_capable: bool = False

    def __init__(self) -> None:
        self._bundle_id: Optional[str] = None
        self._window_id: Optional[int] = None

    def bind(self, bundle_id: str, window_id: Optional[int] = None) -> None:
        """Set the app and window every later `act` targets; `observe` rebinds as it runs."""
        self._bundle_id = bundle_id
        self._window_id = window_id

    @abc.abstractmethod
    def check(self) -> List[str]:
        """Return the missing tools or permissions; empty when the driver is ready."""

    @abc.abstractmethod
    def observe(self, bundle_id: str, window_id: Optional[int], screenshot: bool) -> Observation:
        """Return the bound window's tree, element ids, focus, and optionally a screenshot."""

    @abc.abstractmethod
    def act(self, action: Action, foreground: bool) -> DriverResult:
        """Deliver one action and return the driver's own verdict and post-action view."""


def parse_orca_envelope(stdout: str, returncode: int) -> dict:
    """Return `result` from an `orca computer --json` envelope.

    Raises `DriverError` carrying orca's `error.code` when `ok` is false, `invalid_output` when
    stdout is not an envelope, and `driver_exit_<n>` when an ok envelope sits behind a failing exit.
    """
    text = (stdout or "").strip()
    try:
        envelope = json.loads(text)
    except ValueError:
        raise DriverError("invalid_output", f"exit {returncode}: {text[:200] or 'no output'}")
    if not isinstance(envelope, dict) or "ok" not in envelope:
        raise DriverError("invalid_output", f"exit {returncode}: not an orca envelope")
    if not envelope["ok"]:
        error = envelope.get("error") or {}
        raise DriverError(str(error.get("code") or "driver_error"), str(error.get("message") or ""))
    if returncode != 0:
        raise DriverError(f"driver_exit_{returncode}", "orca reported ok but exited non-zero")
    result = envelope.get("result")
    return result if isinstance(result, dict) else {}


def _parse_tree(tree_text: str) -> List[Tuple[str, str, str, Optional[str]]]:
    """Split orca's tree text into (ref, role, name, value) rows, one per element line."""
    rows = []
    for line in tree_text.splitlines():
        match = _LINE_RE.match(line)
        if not match:
            continue
        ref, rest = match.group(2), match.group(3)
        cut = rest.find(_ACTIONS_SEP)
        if cut >= 0:
            rest = rest[:cut]
        value: Optional[str] = None
        cut = rest.find(_VALUE_SEP)
        if cut >= 0:
            value = rest[cut + len(_VALUE_SEP):]
            rest = rest[:cut]
        role_match = _ROLE_RE.match(rest)
        if role_match:
            role = role_match.group(1)
            remainder = rest[role_match.end():]
        else:
            role, _, remainder = rest.partition(" ")
        flags = _FLAGS_RE.match(remainder)
        if flags:
            remainder = remainder[flags.end():]
        rows.append((ref, role, remainder.strip(), value))
    return rows


def _is_sparse(rows: List[Tuple[str, str, str, Optional[str]]], window_title: Optional[str]) -> bool:
    """True when nothing in the tree beyond window chrome is more than a bare container."""
    content = [
        (role, name)
        for _, role, name, _ in rows
        if role not in _CHROME_ROLES and not (role == "text" and name == (window_title or None))
    ]
    return all(role in _CONTAINER_ROLES for role, _ in content)


def _observation_from(result: dict, raw: str, bundle_id: str) -> Optional[Observation]:
    snapshot = result.get("snapshot")
    if not isinstance(snapshot, dict):
        return None
    tree_text = str(snapshot.get("treeText") or "")
    rows = _parse_tree(tree_text)
    window = snapshot.get("window") or {}
    app = snapshot.get("app") or {}
    shot = result.get("screenshot") or {}
    focused = snapshot.get("focusedElementId")
    window_id = window.get("id")
    scale = shot.get("scale")
    title = window.get("title")
    return Observation(
        tree_text=tree_text,
        refs=[ref for ref, _, _, _ in rows],
        names={ref: name for ref, _, name, _ in rows},
        values={ref: value for ref, _, _, value in rows if value is not None},
        title=title,
        focus=None if focused is None else str(focused),
        screenshot_path=Path(shot["path"]) if shot.get("path") else None,
        scale=float(scale) if scale is not None else None,
        tree_truncated=bool((snapshot.get("truncation") or {}).get("truncated")),
        tree_sparse=_is_sparse(rows, title),
        window_id=int(window_id) if window_id is not None else None,
        bundle_id=app.get("bundleId") or bundle_id,
        raw=raw,
    )


def _number(value: float) -> str:
    return str(int(value)) if float(value) == int(value) else repr(float(value))


class OrcaDriver(NativeDriver):
    """Adapter for `orca computer`.

    Not background-capable: element clicks activate and raise the target app, so every `act`
    needs `foreground=True`. The binary comes from `LIKEUSER_ORCA_BIN`, else PATH. Accessibility
    permission is not probed by `check` because `orca computer permissions` opens System Settings.
    """

    name = "orca"
    background_capable = False

    def __init__(self) -> None:
        super().__init__()
        self._bin: Optional[str] = os.environ.get("LIKEUSER_ORCA_BIN") or shutil.which("orca")

    def _exec(self, args: List[str], stdin: Optional[str] = None) -> Tuple[str, int]:
        if not self._bin:
            raise DriverError("driver_unavailable", "orca binary not found")
        try:
            proc = subprocess.run(
                [self._bin] + args,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=_ORCA_TIMEOUT_S,
            )
        except FileNotFoundError:
            raise DriverError("driver_unavailable", f"orca binary not found: {self._bin}")
        except subprocess.TimeoutExpired:
            raise DriverError("timeout", f"orca did not answer within {int(_ORCA_TIMEOUT_S)}s")
        return proc.stdout, proc.returncode

    def _call(self, args: List[str], stdin: Optional[str] = None) -> Tuple[dict, str]:
        stdout, returncode = self._exec(["computer"] + args + ["--json"], stdin)
        try:
            return parse_orca_envelope(stdout, returncode), stdout
        except DriverError as error:
            if error.code in _GONE_CODES:
                raise DriverError("window_gone", error.message)
            raise

    def check(self) -> List[str]:
        """Return `["orca"]` when the binary is absent, else any reason `computer` is unusable."""
        if not self._bin or not (os.path.isfile(self._bin) and os.access(self._bin, os.X_OK)):
            return ["orca"]
        try:
            out, code = self._exec(["--version"])
            self.version = out.strip() if code == 0 else ""
            result, _ = self._call(["capabilities"])
        except DriverError as error:
            return [f"orca computer: {error.code}"]
        actions = ((result.get("supports") or {}).get("actions")) or {}
        return [f"orca computer action: {name}" for name in _REQUIRED_ACTIONS if not actions.get(name)]

    def find_window(self, bundle_id: str) -> Optional[int]:
        """Return the id of the app's first on-screen window, or None when it has none."""
        try:
            result, _ = self._call(["list-windows", "--app", bundle_id])
        except DriverError as error:
            if error.code == "window_gone":
                return None
            raise
        for window in result.get("windows") or []:
            if not window.get("isMinimized") and not window.get("isOffscreen"):
                return int(window["id"])
        return None

    def observe(self, bundle_id: str, window_id: Optional[int], screenshot: bool) -> Observation:
        """Bind the target and return its tree plus, when asked, a screenshot path and scale.

        With no `window_id`, the window orca picked is adopted so later acts hit the same one.
        """
        self.bind(bundle_id, window_id)
        args = ["get-app-state"] + self._target()
        if not screenshot:
            args.append("--no-screenshot")
        result, raw = self._call(args)
        observation = _observation_from(result, raw, bundle_id)
        if observation is None:
            raise DriverError("invalid_output", "get-app-state returned no snapshot")
        if self._window_id is None:
            self._window_id = observation.window_id
        return observation

    def act(self, action: Action, foreground: bool) -> DriverResult:
        """Deliver `action` to the bound window; refused unless `foreground` is True."""
        if not foreground:
            raise DriverError("needs_foreground", "orca element clicks raise the target app")
        if self._bundle_id is None:
            raise DriverError("not_bound", "observe or bind a target before acting")
        steps = self._steps(action)
        result: dict = {}
        raw = ""
        for args, stdin in steps:
            result, raw = self._call(args + self._target() + ["--no-screenshot"], stdin)
        verification = ((result.get("action") or {}).get("verification") or {}).get("state")
        return DriverResult(
            delivered=True,
            driver_verified=None if verification is None else verification == "verified",
            observation=_observation_from(result, raw, self._bundle_id),
            raw=raw,
        )

    def _target(self) -> List[str]:
        args = ["--app", self._bundle_id or ""]
        if self._window_id is not None:
            args += ["--window-id", str(self._window_id)]
        return args

    def _steps(self, action: Action) -> List[Tuple[List[str], Optional[str]]]:
        """Translate one CLI action into the orca commands that deliver it, with any stdin text."""
        kind = action.kind
        if kind in ("click", "double-click", "right-click", "dismiss"):
            args = ["click"] + self._point(action)
            if kind == "double-click":
                args += ["--click-count", "2"]
            elif kind == "right-click":
                args += ["--mouse-button", "right"]
            return [(args, None)]
        if kind == "type":
            steps: List[Tuple[List[str], Optional[str]]] = []
            if action.ref is not None:
                steps.append((["click", "--element-index", str(action.ref)], None))
            steps.append((["type-text", "--text-stdin"], _required(action.text, "text")))
            return steps
        if kind in ("fill", "select"):
            if action.ref is None:
                raise DriverError("invalid_action", f"{kind} needs a ref")
            text = action.text if kind == "fill" else action.value
            return [(["set-value", "--element-index", str(action.ref), "--value-stdin"], _required(text, "value"))]
        if kind == "press":
            return [(["press-key", "--key", _required(action.key, "key")], None)]
        if kind == "hotkey":
            return [(["hotkey", "--key", _required(action.key, "key")], None)]
        if kind == "scroll":
            args = ["scroll"] + self._point(action) + ["--direction", _required(action.direction, "direction")]
            if action.amount is not None:
                args += ["--pages", _number(action.amount)]
            return [(args, None)]
        if kind == "drag":
            if action.ref is not None and action.to_ref is not None:
                return [(["drag", "--from-element-index", str(action.ref), "--to-element-index", str(action.to_ref)], None)]
            if None in (action.x, action.y, action.to_x, action.to_y):
                raise DriverError("invalid_action", "drag needs refs or both coordinate pairs")
            return [(
                ["drag", "--from-x", _number(action.x), "--from-y", _number(action.y),
                 "--to-x", _number(action.to_x), "--to-y", _number(action.to_y)],
                None,
            )]
        raise DriverError("unsupported_action", kind)

    def _point(self, action: Action) -> List[str]:
        if action.ref is not None:
            return ["--element-index", str(action.ref)]
        if action.x is not None and action.y is not None:
            return ["--x", _number(action.x), "--y", _number(action.y)]
        raise DriverError("invalid_action", f"{action.kind} needs a ref or x and y")


def _required(value: Optional[str], what: str) -> str:
    if value is None:
        raise DriverError("invalid_action", f"missing {what}")
    return value


_DRIVERS: Dict[str, type] = {"orca": OrcaDriver}


def get_native_driver() -> NativeDriver:
    """Return the first preferred driver whose `check()` is clean.

    Raises `MissingError` listing what every tried driver lacked, or `native_driver` when no
    preferred driver is known.
    """
    missing: List[str] = []
    for name in NATIVE_DRIVER_PREFERENCE:
        factory = _DRIVERS.get(name)
        if factory is None:
            continue
        driver = factory()
        gaps = driver.check()
        if not gaps:
            return driver
        missing.extend(gaps)
    raise MissingError(missing or ["native_driver"])
