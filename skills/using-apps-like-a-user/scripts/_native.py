"""Native driver adapters for the using-apps-like-a-user guard script.

A native driver observes and acts on one bound macOS app window. Two adapters ship: Cua Driver,
the bake-off winner, which can deliver element actions without taking the foreground, and
`orca computer`. `NATIVE_DRIVER_PREFERENCE` names the adapters `get_native_driver` tries, best
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
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from _types import Action, DriverError, DriverResult, MissingError, Observation  # noqa: E402

NATIVE_DRIVER_PREFERENCE: List[str] = ["cua", "orca"]

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

_SHEET_ROW_RE = re.compile(r"^\t*\d+ (?:sheet|dialog|system dialog)\b", re.MULTILINE)

_REQUIRED_ACTIONS = ("click", "typeText", "pressKey", "hotkey")


class NativeDriver(abc.ABC):
    """A driver bound to one native app window.

    `observe` and `act` target only the bound bundle id and window id. `act(..., foreground=False)`
    must never activate another app; an adapter that cannot guarantee that for an action raises
    `DriverError("needs_foreground")`. A vanished window raises `DriverError("window_gone")`.
    """

    name: str = ""
    version: str = ""
    pin: Optional[str] = None
    background_capable: bool = False

    def __init__(self, session: Optional[str] = None) -> None:
        self._bundle_id: Optional[str] = None
        self._window_id: Optional[int] = None
        self._bin: Optional[str] = None

    @property
    def path(self) -> Optional[str]:
        """The driver binary this adapter runs, or None when none was found."""
        return self._bin

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

    def close(self) -> None:
        """Release whatever driver-side state this run's observations left behind.

        Raises `DriverError` when cleanup fails. Adapters with no such state keep this no-op.
        """


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
        sheet_open=bool(_SHEET_ROW_RE.search(tree_text)),
    )


def _number(value: float) -> str:
    return str(int(value)) if float(value) == int(value) else repr(float(value))


class OrcaDriver(NativeDriver):
    """Adapter for `orca computer`.

    Not background-capable: element clicks activate and raise the target app, so every `act`
    needs `foreground=True`. The binary comes from `LIKEUSER_ORCA_BIN`, else PATH. Accessibility
    permission is not probed by `check` because `orca computer permissions` opens System Settings.
    `fill` double-clicks the element to focus it (a plain element click on a text field does not),
    selects all, and types, so the app's own model hears the text; `select` writes the value.
    """

    name = "orca"
    background_capable = False

    def __init__(self, session: Optional[str] = None) -> None:
        super().__init__(session)
        self._bin = os.environ.get("LIKEUSER_ORCA_BIN") or shutil.which("orca")

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
        """Deliver `action` to the bound window; refused unless `foreground` is True.

        An unbound driver reports `not_bound` before any foreground check.
        """
        if self._bundle_id is None:
            raise DriverError("not_bound", "observe or bind a target before acting")
        if not foreground:
            raise DriverError("needs_foreground", "orca element clicks raise the target app")
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
                steps.append((["click", "--element-index", str(action.ref), "--click-count", "2"], None))
                steps.append((["press-key", "--key", "Right"], None))
            steps.append((["type-text", "--text-stdin"], _required(action.text, "text")))
            return steps
        if kind == "fill":
            if action.ref is None:
                raise DriverError("invalid_action", "fill needs a ref")
            text = _required(action.text, "value")
            steps = [
                (["click", "--element-index", str(action.ref), "--click-count", "2"], None),
                (["hotkey", "--key", "CmdOrCtrl+A"], None),
            ]
            if text:
                steps.append((["type-text", "--text-stdin"], text))
            else:
                steps.append((["press-key", "--key", "Delete"], None))
            return steps
        if kind == "select":
            if action.ref is None:
                raise DriverError("invalid_action", "select needs a ref")
            return [(["set-value", "--element-index", str(action.ref), "--value-stdin"],
                     _required(action.value, "value"))]
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


CUA_MIN_VERSION = (0, 34, 1)
_CUA_TIMEOUT_S = 60.0
_CUA_GONE_CODES = frozenset(
    ["stale_element_token", "window_not_found", "window_stale", "window_gone", "no_such_window"]
)
_CUA_CODE_ALIASES = {"background_unavailable": "needs_foreground"}
_CUA_SHEET_ROLES = frozenset(["AXSheet", "AXDialog"])
_CUA_DIALOG_SUBROLES = frozenset(["AXDialog", "AXSystemDialog"])
_CUA_CONTAINER_ROLES = frozenset(
    ["AXGroup", "AXScrollArea", "AXSplitGroup", "AXWebArea", "AXUnknown", "AXLayoutArea",
     "AXTabGroup", "AXSplitter"]
)
_CUA_KEY_ALIASES = {"enter": "return", "esc": "escape"}
_CUA_MODIFIER_ALIASES = {"cmdorctrl": "cmd", "command": "cmd", "control": "ctrl"}
_CUA_MODIFIERS = frozenset(["cmd", "shift", "option", "alt", "ctrl", "fn"])

_MENU_BAR_RE = re.compile(r"^(\s*)- (?:\[\d+\] )?AXMenuBar\b")
_INDEXED_ROW_RE = re.compile(r"^(\s*- )\[(\d+)\](.*)$")
_ROW_RE = re.compile(r"^\s*- (?:\[\d+\] )?(AX\w+)(.*)$")
_STATIC_VALUE_RE = re.compile(r'^\s*= "(.*)"')
_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_PID_RE = re.compile(r'"?pid"?\s*=\s*(\d+)')


def _drop_menu_bar(markdown: str) -> str:
    """Remove the menu-bar subtree from a tree rendering, keeping the `AXMenuBar` row itself."""
    kept: List[str] = []
    skip_below: Optional[int] = None
    for line in markdown.splitlines():
        indent = len(line) - len(line.lstrip())
        if skip_below is not None and indent > skip_below:
            continue
        skip_below = None
        kept.append(line)
        match = _MENU_BAR_RE.match(line)
        if match:
            skip_below = len(match.group(1))
    return "\n".join(kept)


def _menu_bar_members(elements: List[dict]) -> frozenset:
    """Return the `element_index` of every element under an `AXMenuBar`, excluding the bar itself."""
    parents = {e.get("element_index"): e.get("parent_index") for e in elements}
    bars = {e.get("element_index") for e in elements if e.get("role") == "AXMenuBar"}
    members = set()
    for index in parents:
        node, hops = parents[index], 0
        while node is not None and hops < 64:
            if node in bars:
                members.add(index)
                break
            node, hops = parents.get(node), hops + 1
    return frozenset(members)


def _cua_is_sparse(markdown: str, title: Optional[str]) -> bool:
    """True when nothing in the tree beyond window chrome is more than a bare container."""
    for line in markdown.splitlines():
        match = _ROW_RE.match(line)
        if not match:
            continue
        role, rest = match.group(1), match.group(2)
        if role in ("AXWindow", "AXMenuBar") or role in _CUA_CONTAINER_ROLES:
            continue
        if role == "AXButton" and not rest.lstrip().startswith('"'):
            continue
        if role == "AXStaticText":
            value = _STATIC_VALUE_RE.match(rest)
            if value and value.group(1) == (title or None):
                continue
        return False
    return True


def _is_sheet_element(element: dict) -> bool:
    return element.get("role") in _CUA_SHEET_ROLES or element.get("subrole") in _CUA_DIALOG_SUBROLES


def _in_sheet(index: int, by_index: Dict[int, dict]) -> bool:
    node, hops = index, 0
    while node is not None and hops < 64:
        element = by_index.get(node) or {}
        if _is_sheet_element(element):
            return True
        node, hops = element.get("parent_index"), hops + 1
    return False


def _cua_snapshot(data: dict, raw: str, bundle_id: str) -> Tuple[Observation, dict]:
    """Build the `Observation` and the memo `act` needs from one `get_window_state` reply.

    Refs are element tokens, shown in the tree as `[ref=<token>]` so an agent can copy them and
    `normalize_tree` strips them. The memo holds the screenshot scale, which tokens sit in a sheet
    or dialog, and element centers, because each `likeuser.py` call is a fresh process.
    """
    elements = [e for e in (data.get("elements") or []) if isinstance(e, dict)]
    hidden = _menu_bar_members(elements)
    shown = [e for e in elements if e.get("element_index") not in hidden and e.get("element_token")]
    by_index = {e.get("element_index"): e for e in elements}
    tokens = {e["element_index"]: str(e["element_token"]) for e in shown}

    lines = []
    for line in _drop_menu_bar(str(data.get("tree_markdown") or "")).splitlines():
        match = _INDEXED_ROW_RE.match(line)
        if match and int(match.group(2)) in tokens:
            line = f"{line} [ref={tokens[int(match.group(2))]}]"
        lines.append(line)
    tree_text = "\n".join(lines)

    bounds = data.get("window_bounds") or {}
    shot = data.get("screenshot_file_path")
    width, bounds_width = data.get("screenshot_width"), bounds.get("width")
    scale = float(width) / float(bounds_width) if shot and width and bounds_width else None
    title = data.get("window_title")
    window_id = data.get("window_id")
    focus = next((str(e["element_token"]) for e in shown if e.get("focused")), None)

    observation = Observation(
        tree_text=tree_text,
        refs=[str(e["element_token"]) for e in shown],
        names={str(e["element_token"]): str(e.get("label") or "") for e in shown},
        values={str(e["element_token"]): str(e["value"]) for e in shown if e.get("value") is not None},
        title=title,
        focus=focus,
        screenshot_path=Path(shot) if shot else None,
        scale=scale,
        tree_truncated=bool(data.get("truncated")),
        tree_sparse=_cua_is_sparse(tree_text, title),
        window_id=int(window_id) if window_id is not None else None,
        bundle_id=bundle_id,
        raw=raw,
        sheet_open=any(_is_sheet_element(e) for e in shown),
    )
    sheet = [tokens[e["element_index"]] for e in shown if _in_sheet(e["element_index"], by_index)]
    centers = {}
    for element in shown:
        frame = element.get("screenshot_frame") or {}
        if all(key in frame for key in ("x", "y", "w", "h")):
            centers[tokens[element["element_index"]]] = [
                frame["x"] + frame["w"] / 2.0, frame["y"] + frame["h"] / 2.0,
            ]
    memo = {
        "bundle_id": bundle_id,
        "window_id": observation.window_id,
        "scale": scale,
        "sheet": sheet,
        "labels": {t: [by_index[i].get("role"), by_index[i].get("label")] for i, t in tokens.items() if t in sheet},
        "centers": centers,
    }
    return observation, memo


class _Plan:
    """One Cua tool call: the tool, its payload, and what delivering it demands.

    `points` names payload keys holding driver points that must become window-local pixels.
    `keyboard` marks key and text delivery, which goes to a window rather than an element.
    `before` lists (tool, payload) calls to run first against the same window and element;
    `before_foreground` replaces it when the app is being driven in the foreground.
    """

    def __init__(self, tool: str, payload: dict, tokens: Tuple[str, ...] = (), points: Tuple[str, ...] = (),
                 always_foreground: bool = False, delivery_mode: bool = True, keyboard: bool = False,
                 before: Tuple[Tuple[str, dict], ...] = (),
                 before_foreground: Optional[Tuple[Tuple[str, dict], ...]] = None) -> None:
        self.tool = tool
        self.payload = payload
        self.before = before
        self.before_foreground = before if before_foreground is None else before_foreground
        self.tokens = tokens
        self.points = points
        self.always_foreground = always_foreground
        self.delivery_mode = delivery_mode
        self.keyboard = keyboard

    @property
    def window_keys(self) -> bool:
        """True for keyboard input aimed at no element and no point, so at whichever window has focus."""
        return self.keyboard and not self.tokens and not self.points


class CuaDriver(NativeDriver):
    """Adapter for Cua Driver (`cua-driver call <tool>`, payload on stdin).

    Background-capable: element actions run through accessibility without activating the app.
    Coordinate actions, targeted `scroll`, `drag`, and anything inside an `AXSheet` or dialog need
    `foreground=True`; with `foreground=False` they raise `DriverError("needs_foreground")` before
    any call. Keys and text with no element target go to the frontmost sheet or dialog window when
    the last observation showed one open, because those are windows of their own that the main
    window's id never reaches. Every call carries one `session` label because tokens only stay
    valid within a session. Callers that span processes pass the same `session` (the run id) to every instance so
    a token from `observe` still works in the next `likeuser.py` call; without one, each instance
    gets a label of its own so unrelated runs never share tokens, memos, or screenshots. The
    payload goes in on stdin so text typed from `--secret` never appears in argv. The binary comes
    from `LIKEUSER_NATIVE_BIN`, else PATH. Never grants permissions.

    `fill` selects the element's whole text, then types the new text as keystrokes, so the app's
    own model hears it; a value write changes only what the field shows. In the background the
    selection is made with cursor keys, because cmd+a only reaches an app that is in front; in the
    foreground it is cmd+a, because a save panel claims cmd+up and cmd+down for folder navigation.
    `select` still writes the value.
    """

    name = "cua"
    pin = ".".join(str(part) for part in CUA_MIN_VERSION)
    background_capable = True

    def __init__(self, session: Optional[str] = None) -> None:
        super().__init__(session)
        self.session = session or f"likeuser-{uuid.uuid4().hex[:12]}"
        self._bin = os.environ.get("LIKEUSER_NATIVE_BIN") or shutil.which("cua-driver")
        self._pids: Dict[str, int] = {}
        self._memo: Optional[dict] = None

    def bind(self, bundle_id: str, window_id: Optional[int] = None) -> None:
        """Set the app and window every later `act` targets; a new bundle forgets the last observation."""
        if bundle_id != self._bundle_id:
            self._memo = None
        super().bind(bundle_id, window_id)

    def _exec(self, args: List[str], stdin: Optional[str] = None) -> Tuple[str, str, int]:
        if not self._bin:
            raise DriverError("driver_unavailable", "cua-driver binary not found")
        try:
            proc = subprocess.run(
                [self._bin] + args, capture_output=True, text=True, timeout=_CUA_TIMEOUT_S,
                input=stdin if stdin is not None else "",
            )
        except FileNotFoundError:
            raise DriverError("driver_unavailable", f"cua-driver binary not found: {self._bin}")
        except subprocess.TimeoutExpired:
            raise DriverError("timeout", f"cua-driver did not answer within {int(_CUA_TIMEOUT_S)}s")
        return proc.stdout, proc.stderr, proc.returncode

    def _call(self, tool: str, payload: dict, tolerate_partial: bool = False,
              revived: bool = False) -> Tuple[dict, str]:
        """Run one tool and return its JSON reply plus the raw stdout, or raise `DriverError`.

        A refusal (`effect: refused`) or non-zero exit raises with Cua's `code`; stale tokens and
        missing windows become `window_gone`. `tolerate_partial` accepts a `status: partial` reply.
        A session the daemon has ended is started again once, because ordinary calls never revive it.
        """
        body = json.dumps(dict(payload, session=self.session), separators=(",", ":"))
        stdout, stderr, returncode = self._exec(["call", tool], stdin=body)
        if returncode != 0 and not revived and "session has ended" in (stdout + stderr).lower():
            self._call("start_session", {}, revived=True)
            return self._call(tool, payload, tolerate_partial, revived=True)
        text = stdout.strip()
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if not isinstance(data, dict):
            if returncode == 0:
                raise DriverError("invalid_output", f"{tool}: {text[:200] or 'no output'}")
            detail = (text or stderr.strip())[:200]
            code = "ax_action_failed" if detail.startswith("AX action failed") else f"driver_exit_{returncode}"
            raise DriverError(code, detail)
        partial = tolerate_partial and data.get("status") == "partial"
        if data.get("effect") == "refused" or (returncode != 0 and not partial):
            code = str(data.get("code") or f"driver_exit_{returncode}")
            if code in _CUA_GONE_CODES:
                code = "window_gone"
            code = _CUA_CODE_ALIASES.get(code, code)
            raise DriverError(code, str(data.get("reason") or data.get("summary") or ""))
        return data, stdout

    def check(self) -> List[str]:
        """Return what is missing: the binary, the 0.34.1 pin, the daemon, or a macOS permission.

        Reads permissions with the read-only `permissions status`; it never asks for a grant.
        """
        if not self._bin or not (os.path.isfile(self._bin) and os.access(self._bin, os.X_OK)):
            return ["cua-driver"]
        try:
            out, _, code = self._exec(["--version"])
            found = _VERSION_RE.search(out) if code == 0 else None
            if found is None:
                return ["cua-driver version unreadable"]
            self.version = ".".join(found.groups())
            if tuple(int(part) for part in found.groups()) < CUA_MIN_VERSION:
                return [f"cua-driver {self.version} is below the 0.34.1 pin"]
            out, err, code = self._exec(["status"])
            text = (out + err).lower()
            if code != 0 or "running" not in text or "not running" in text:
                return ["cua-driver daemon not running"]
            out, _, code = self._exec(["permissions", "status", "--json"])
        except DriverError as error:
            return [f"cua-driver: {error.code}"]
        try:
            status = json.loads(out)
        except ValueError:
            status = None
        if code != 0 or not isinstance(status, dict):
            return ["cua-driver permissions unreadable"]
        missing = []
        if status.get("accessibility") is not True:
            missing.append("cua-driver permission: Accessibility")
        if status.get("screen_recording") is not True:
            missing.append("cua-driver permission: Screen Recording")
        return missing

    def close(self) -> None:
        """End this run's Cua session and delete its memo and screenshots from the cache.

        Both always run; the first failure is raised afterwards so a daemon that is gone does not
        leave UI captures behind.
        """
        failure: Optional[DriverError] = None
        try:
            self._call("end_session", {}, revived=True)
        except DriverError as error:
            failure = error
        self._memo = None
        try:
            for suffix in (".json", "-shot.png", "-probe.png"):
                try:
                    self._session_file(suffix).unlink()
                except FileNotFoundError:
                    pass
        except (OSError, DriverError) as error:
            failure = failure or DriverError("cleanup_failed", str(error))
        if failure is not None:
            raise failure

    def _pid(self, bundle_id: Optional[str] = None) -> int:
        bundle_id = bundle_id or self._bundle_id or ""
        if bundle_id in self._pids:
            return self._pids[bundle_id]
        try:
            proc = subprocess.run(
                ["lsappinfo", "info", "-only", "pid", "-app", bundle_id],
                capture_output=True, text=True, timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            raise DriverError("unsupported_platform", "lsappinfo is unavailable")
        found = _PID_RE.search(proc.stdout)
        if not found:
            raise DriverError("app_not_found", f"{bundle_id} is not running")
        self._pids[bundle_id] = int(found.group(1))
        return self._pids[bundle_id]

    def find_window(self, bundle_id: str) -> Optional[int]:
        """Return the id of the app's first on-screen window, None when it has none.

        Raises `DriverError("app_not_found")` when the app is not running.
        """
        data, _ = self._call("list_windows", {"pid": self._pid(bundle_id)})
        for window in data.get("windows") or []:
            if window.get("is_on_screen", True) and window.get("on_current_space", True):
                return int(window["window_id"])
        return None

    def observe(self, bundle_id: str, window_id: Optional[int], screenshot: bool) -> Observation:
        """Bind the target and return its tree plus, when asked, a screenshot path and scale.

        `scale` is screenshot pixels per point of the window. The tree omits the menu-bar subtree
        because it lists the user's recent documents. With no `window_id`, the app's first
        on-screen window is adopted.
        """
        self.bind(bundle_id, window_id)
        payload = {"pid": self._pid(), "window_id": self._require_window()}
        if screenshot:
            payload["screenshot_out_file"] = str(self._session_file("-shot.png"))
        else:
            payload["include_screenshot"] = False
        data, raw = self._call("get_window_state", payload)
        observation, memo = _cua_snapshot(data, raw, bundle_id)
        self._remember(memo)
        return observation

    def _cache_dir(self) -> Path:
        path = Path(tempfile.gettempdir()) / f"likeuser-cua-{os.getuid()}"
        try:
            path.mkdir(mode=0o700, exist_ok=True)
        except OSError as error:
            raise DriverError("cache_unavailable", str(error))
        return path

    def _session_file(self, suffix: str) -> Path:
        stem = re.sub(r"[^A-Za-z0-9_.-]", "_", self.session)
        return self._cache_dir() / f"{stem}{suffix}"

    def _memo_path(self) -> Path:
        return self._session_file(".json")

    def _remember(self, memo: dict) -> None:
        self._memo = memo
        try:
            target = self._memo_path()
            handle, temp = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
            try:
                with os.fdopen(handle, "w") as stream:
                    stream.write(json.dumps(memo))
                os.replace(temp, str(target))
            except BaseException:
                try:
                    os.unlink(temp)
                except OSError:
                    pass
                raise
        except (OSError, DriverError):
            pass

    def _recall(self) -> Optional[dict]:
        """Return what the last observation of the bound window recorded, here or in an earlier process."""
        if self._memo is None:
            try:
                self._memo = json.loads(self._memo_path().read_text())
            except (OSError, ValueError, DriverError):
                return None
        memo = self._memo
        if memo.get("bundle_id") != self._bundle_id:
            return None
        if self._window_id is not None and memo.get("window_id") not in (None, self._window_id):
            return None
        return memo

    def _pixel_scale(self) -> float:
        memo = self._recall()
        if memo is not None:
            return float(memo.get("scale") or 1.0)
        path = self._session_file("-probe.png")
        data, raw = self._call(
            "get_window_state",
            {"pid": self._pid(), "window_id": self._require_window(), "include_accessibility_tree": False,
             "screenshot_out_file": str(path)},
        )
        observation, _ = _cua_snapshot(data, raw, self._bundle_id or "")
        return observation.scale or 1.0

    def _require_window(self) -> int:
        if self._window_id is None:
            self._window_id = self.find_window(self._bundle_id or "")
        if self._window_id is None:
            raise DriverError("window_gone", f"{self._bundle_id} has no on-screen window")
        return self._window_id

    def _sheet_window(self) -> Optional[int]:
        """Return the frontmost window of the app other than the bound one, None when there is none.

        Reads `get_accessibility_tree`, which lists on-screen windows front to back. `list_windows`
        cannot say: its `z_index` can rank a parent sheet above the nested one that is on top.
        """
        data, _ = self._call("get_accessibility_tree", {})
        pid, bound = self._pid(), self._require_window()
        for window in data.get("windows") or []:
            if window.get("pid") == pid and window.get("window_id") != bound:
                return int(window["window_id"])
        return None

    def act(self, action: Action, foreground: bool) -> DriverResult:
        """Deliver `action` to the bound window.

        Element actions run in the background. Coordinate actions (converted from driver points
        to window-local screenshot pixels with the last observation's scale), targeted `scroll`,
        `drag`, and elements inside a sheet or dialog raise `needs_foreground` unless `foreground`
        is True. `press`, `hotkey`, and `type` with no element target go to the frontmost sheet or
        dialog window of the app when the last observation showed one open, and need `foreground`
        for it too. `driver_verified` is True for `effect: confirmed`, None otherwise. The reply
        carries no post-action tree, so `observation` is None.
        """
        if self._bundle_id is None:
            raise DriverError("not_bound", "observe or bind a target before acting")
        plan = self._plan(action)
        memo = self._recall() or {}
        in_sheet = any(token in (memo.get("sheet") or ()) for token in plan.tokens)
        keys_to_sheet = plan.window_keys and bool(memo.get("sheet"))
        if (plan.points or plan.always_foreground or in_sheet or keys_to_sheet) and not foreground:
            raise DriverError("needs_foreground", f"{action.kind} needs the target app in front")
        payload = dict(plan.payload, pid=self._pid(), window_id=self._require_window())
        if keys_to_sheet:
            payload["window_id"] = self._sheet_window() or payload["window_id"]
        if plan.points:
            scale = self._pixel_scale()
            for key in plan.points:
                payload[key] = round(float(payload[key]) * scale, 2)
        if in_sheet:
            self._call("bring_to_front", {"pid": payload["pid"], "window_id": payload["window_id"]},
                       tolerate_partial=True)
            if "element_token" in payload:
                payload["element_token"] = self._renewed(payload["element_token"], memo)
        elif foreground and plan.delivery_mode:
            payload["delivery_mode"] = "foreground"
        shared = {k: payload[k] for k in ("pid", "window_id", "element_token", "delivery_mode") if k in payload}
        for tool, extra in (plan.before_foreground if foreground else plan.before):
            self._call(tool, dict(extra, **shared))
        data, raw = self._call(plan.tool, payload)
        return DriverResult(
            delivered=True,
            driver_verified=True if data.get("effect") == "confirmed" else None,
            observation=None,
            raw=raw,
        )

    def _renewed(self, token: str, memo: dict) -> str:
        """Return `token`'s successor in a fresh snapshot, which bringing the app forward made necessary."""
        data, raw = self._call(
            "get_window_state",
            {"pid": self._pid(), "window_id": self._require_window(), "include_screenshot": False},
        )
        _, fresh = _cua_snapshot(data, raw, self._bundle_id or "")
        self._remember(fresh)
        role, label = (memo.get("labels") or {}).get(token) or (None, None)
        index = token.rsplit(":", 1)[-1]
        matches = [
            e for e in data.get("elements") or []
            if e.get("role") == role and e.get("label") == label and e.get("element_token")
        ]
        same_index = [e for e in matches if str(e.get("element_index")) == index]
        chosen = same_index or (matches if len(matches) == 1 else [])
        if not chosen:
            raise DriverError("element_not_found", f"{label or token} is gone after bringing the app forward")
        return str(chosen[0]["element_token"])

    def _target(self, action: Action, required: bool = True) -> Tuple[dict, Tuple[str, ...], Tuple[str, ...]]:
        if action.ref is not None:
            return {"element_token": action.ref}, (action.ref,), ()
        if action.x is not None and action.y is not None:
            return {"x": action.x, "y": action.y}, (), ("x", "y")
        if required:
            raise DriverError("invalid_action", f"{action.kind} needs a ref or x and y")
        return {}, (), ()

    def _plan(self, action: Action) -> _Plan:
        """Translate one CLI action into the Cua tool call that delivers it.

        `hotkey` is delivered as `press_key` with modifiers: Cua's own `hotkey` tool posts chords
        that a save sheet's remote view service ignores, while `press_key` reaches it.
        """
        kind = action.kind
        if kind in ("click", "dismiss", "double-click", "right-click"):
            tool = {"double-click": "double_click", "right-click": "right_click"}.get(kind, "click")
            target, tokens, points = self._target(action)
            return _Plan(tool, target, tokens, points)
        if kind == "type":
            target, tokens, points = self._target(action, required=False)
            return _Plan("type_text", dict(target, text=_required(action.text, "text")), tokens, points,
                         keyboard=True)
        if kind == "fill":
            if action.ref is None:
                raise DriverError("invalid_action", "fill needs a ref")
            text = _required(action.text, "value")
            target = {"element_token": action.ref}
            select_all = (("press_key", {"key": "a", "modifiers": ["cmd"]}),)
            to_ends = (("press_key", {"key": "down", "modifiers": ["cmd"]}),
                       ("press_key", {"key": "up", "modifiers": ["cmd", "shift"]}))
            if text:
                tool, payload = "type_text", dict(target, text=text)
            else:
                tool, payload = "press_key", dict(target, key="delete")
            return _Plan(tool, payload, (action.ref,), keyboard=True, before=to_ends,
                         before_foreground=select_all)
        if kind == "select":
            if action.ref is None:
                raise DriverError("invalid_action", "select needs a ref")
            value = _required(action.value, "value")
            return _Plan("set_value", {"element_token": action.ref, "value": value}, (action.ref,),
                         delivery_mode=False)
        if kind in ("press", "hotkey"):
            parts = [p for p in _required(action.key, "key").split("+") if p]
            parts = [_CUA_MODIFIER_ALIASES.get(p.lower(), p.lower()) for p in parts]
            if not parts:
                raise DriverError("invalid_action", "missing key")
            target, tokens, points = self._target(action, required=False)
            modifiers = [p for p in parts[:-1] if p in _CUA_MODIFIERS]
            payload = dict(target, key=_CUA_KEY_ALIASES.get(parts[-1], parts[-1]))
            if modifiers:
                payload["modifiers"] = modifiers
            return _Plan("press_key", payload, tokens, points, keyboard=True)
        if kind == "scroll":
            payload = {"direction": _required(action.direction, "direction")}
            if action.amount is not None:
                payload["amount"] = max(1, min(50, int(round(action.amount))))
            target, tokens, points = self._target(action, required=False)
            return _Plan("scroll", dict(payload, **target), tokens, points, always_foreground=bool(target))
        if kind == "drag":
            return self._drag(action)
        raise DriverError("unsupported_action", kind)

    def _drag(self, action: Action) -> _Plan:
        keys = ("from_x", "from_y", "to_x", "to_y")
        if action.ref is not None and action.to_ref is not None:
            start, end = self._center(action.ref), self._center(action.to_ref)
            tokens: Tuple[str, ...] = (action.ref, action.to_ref)
            points: Tuple[str, ...] = ()
        elif None not in (action.x, action.y, action.to_x, action.to_y):
            start, end, tokens, points = [action.x, action.y], [action.to_x, action.to_y], (), keys
        else:
            raise DriverError("invalid_action", "drag needs refs or both coordinate pairs")
        payload = {"from_x": start[0], "from_y": start[1], "to_x": end[0], "to_y": end[1]}
        return _Plan("drag", payload, tokens, points, always_foreground=True)

    def _center(self, token: str) -> List[float]:
        center = ((self._recall() or {}).get("centers") or {}).get(token)
        if center is None:
            raise DriverError("invalid_action", f"no screenshot frame recorded for {token}; observe with a screenshot")
        return center


_DRIVERS: Dict[str, type] = {"cua": CuaDriver, "orca": OrcaDriver}


def get_native_driver(*, name: Optional[str] = None, session: Optional[str] = None) -> NativeDriver:
    """Return a ready native driver.

    With no `name`, the first preferred driver whose `check()` is clean; raises `MissingError`
    listing what every tried driver lacked, or `native_driver` when no preferred driver is known.
    With a `name`, exactly that adapter: a later CLI process restoring the driver a run began with
    must not switch to another one, so a gap raises `MissingError` instead of falling through.
    `session` is the label session-based adapters keep their state under.
    """
    if name is not None:
        factory = _DRIVERS.get(name)
        if factory is None:
            raise MissingError([f"native driver: {name}"])
        driver = factory(session=session)
        gaps = driver.check()
        if gaps:
            raise MissingError(gaps)
        return driver
    missing: List[str] = []
    for preferred in NATIVE_DRIVER_PREFERENCE:
        factory = _DRIVERS.get(preferred)
        if factory is None:
            continue
        driver = factory(session=session)
        gaps = driver.check()
        if not gaps:
            return driver
        missing.extend(gaps)
    raise MissingError(missing or ["native_driver"])
