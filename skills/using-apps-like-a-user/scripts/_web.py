"""playwright-cli adapter for web pages and Electron renderers.

Every call runs with its cwd set to the run folder and `-s=<session>`, so playwright-cli's
`.playwright-cli/` snapshot files land inside the run. A `### Error` block in the output is a
failure whatever the exit code. `eval` is used only for observation (visibility and viewport
size); no action is ever performed through script evaluation.
"""
from __future__ import annotations

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

from _types import Action, DriverError, DriverResult, Observation  # noqa: E402

BIN_NAME = "playwright-cli"
BIN_ENV = "LIKEUSER_PLAYWRIGHT_BIN"
PIN_TEXT = "0.1.22"
PIN = (0, 1, 22)
CALL_TIMEOUT_S = 120
DEFAULT_VIEWPORT = (1280, 720)
VALUE_ROLES = frozenset({"textbox", "searchbox", "combobox", "spinbutton", "slider"})

# probes the unclipped box center: a center outside the viewport is offscreen even when part of
# the box is visible
VISIBILITY_JS = (
    "el => {"
    " const out = (visible, reason) => JSON.stringify({visible: visible, reason: reason});"
    " if (el.getClientRects().length === 0) return out(false, 'display');"
    " for (let n = el; n; n = n.parentElement) {"
    "  if (getComputedStyle(n).display === 'none') return out(false, 'display');"
    " }"
    " const vis = getComputedStyle(el).visibility;"
    " if (vis === 'hidden' || vis === 'collapse') return out(false, 'hidden');"
    " for (let n = el; n; n = n.parentElement) {"
    "  if (parseFloat(getComputedStyle(n).opacity) === 0) return out(false, 'opacity');"
    " }"
    " const r = el.getBoundingClientRect();"
    " if (r.right <= 0 || r.bottom <= 0 || r.left >= innerWidth || r.top >= innerHeight)"
    "  return out(false, 'offscreen');"
    " const cx = (r.left + r.right) / 2, cy = (r.top + r.bottom) / 2;"
    " if (cx < 0 || cy < 0 || cx >= innerWidth || cy >= innerHeight) return out(false, 'offscreen');"
    " const root = el.getRootNode();"
    " const probe = root.elementFromPoint ? root : document;"
    " const top = probe.elementFromPoint(cx, cy);"
    " if (!top || !(top === el || el.contains(top))) return out(false, 'occluded');"
    " return out(true, '');"
    "}"
)

VIEWPORT_JS = "() => JSON.stringify([innerWidth, innerHeight])"

_REF = re.compile(r"\[ref=([^\]]+)\]")
_LINE = re.compile(
    r'^\s*-\s+([^\s":\[]+)(?:\s+"((?:[^"\\]|\\.)*)")?((?:\s+\[[^\]]*\])*)\s*(?::\s*(.*))?$'
)
_YAML_BLOCK = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)
_SNAPSHOT_LINK = re.compile(r"^- \[Snapshot\]\(([^)]+)\)\s*$", re.MULTILINE)
_ERROR_HEADER = re.compile(r"^### Error[ \t]*$", re.MULTILINE)
_SECTION = re.compile(r"^### ", re.MULTILINE)
_REQUEST_LINE = re.compile(r"^\d+\.\s+\[(\w+)\]\s+(\S+)(?:\s+=>\s+\[([^\]]+)\].*)?$")
_CONSOLE_LINE = re.compile(r"^\[([A-Z]+)\] (.*)$")

_KEY_NAMES = {
    "cmd": "Meta", "command": "Meta", "meta": "Meta", "super": "Meta",
    "ctrl": "Control", "control": "Control",
    "opt": "Alt", "option": "Alt", "alt": "Alt",
    "shift": "Shift",
    "left": "ArrowLeft", "right": "ArrowRight", "up": "ArrowUp", "down": "ArrowDown",
    "enter": "Enter", "return": "Enter", "esc": "Escape", "escape": "Escape",
    "tab": "Tab", "space": "Space", "backspace": "Backspace", "delete": "Delete",
}


def _unquote(raw: str) -> str:
    try:
        return json.loads('"' + raw + '"')
    except ValueError:
        return raw.replace('\\"', '"')


def _num(value: float) -> str:
    return str(int(value)) if float(value) == int(value) else repr(float(value))


def _chord(combo: str) -> str:
    parts = []
    for token in combo.split("+"):
        low = token.lower()
        if low in _KEY_NAMES:
            parts.append(_KEY_NAMES[low])
        elif re.fullmatch(r"f\d{1,2}", low):
            parts.append(low.upper())
        else:
            parts.append(token)
    return "+".join(parts)


def parse_error(stdout: str) -> Optional[str]:
    """Return the body of a `### Error` block in playwright-cli output, else None.

    The block is a failure whatever the process exit code was; callers must test the result
    with `is not None` because an empty body is still an error.
    """
    match = _ERROR_HEADER.search(stdout)
    if not match:
        return None
    rest = stdout[match.end():].lstrip("\n")
    stop = _SECTION.search(rest)
    body = (rest[:stop.start()] if stop else rest).strip()
    return body or "unknown error"


def _header(stdout: str, label: str) -> Optional[str]:
    match = re.search(r"^- %s: (.*)$" % re.escape(label), stdout, re.MULTILINE)
    return match.group(1).strip() if match else None


def _snapshot_text(stdout: str, cwd: Path) -> Optional[str]:
    block = _YAML_BLOCK.search(stdout)
    if block:
        return block.group(1)
    link = _SNAPSHOT_LINK.search(stdout)
    if not link:
        return None
    try:
        return (Path(cwd) / link.group(1)).read_text()
    except OSError as exc:
        raise DriverError("snapshot_unreadable", "%s: %s" % (link.group(1), exc))


def parse_snapshot(stdout: str, cwd: Path) -> Observation:
    """Build an Observation from playwright-cli output carrying a snapshot.

    The snapshot is either inline (a fenced yaml block) or linked (`- [Snapshot](path)`, read
    relative to `cwd`). Raises DriverError("snapshot_missing") when the output has neither and
    DriverError("snapshot_unreadable") when the linked file cannot be read.
    """
    tree = _snapshot_text(stdout, Path(cwd))
    if tree is None:
        raise DriverError("snapshot_missing", "output carries no snapshot")
    refs: List[str] = []
    names: Dict[str, str] = {}
    values: Dict[str, str] = {}
    focus: Optional[str] = None
    for line in tree.splitlines():
        match = _LINE.match(line)
        if not match:
            continue
        role, name, attrs, value = match.groups()
        ref_match = _REF.search(attrs)
        if not ref_match:
            continue
        ref = ref_match.group(1)
        refs.append(ref)
        if name:
            names[ref] = _unquote(name)
        if "[active]" in attrs:
            focus = ref
        if value and role in VALUE_ROLES:
            values[ref] = _unquote(value[1:-1]) if value[:1] == '"' and value[-1:] == '"' and len(value) > 1 else value
    return Observation(
        tree_text=tree,
        refs=refs,
        names=names,
        values=values,
        url=_header(stdout, "Page URL"),
        title=_header(stdout, "Page Title"),
        focus=focus,
        tree_sparse=not refs,
        raw=stdout,
    )


def _result_section(stdout: str) -> str:
    start = re.search(r"^### Result[ \t]*$", stdout, re.MULTILINE)
    if not start:
        raise ValueError("no result section")
    rest = stdout[start.end():].lstrip("\n")
    stop = _SECTION.search(rest)
    return (rest[:stop.start()] if stop else rest).strip()


def _eval_json(stdout: str):
    """Decode the JSON a page function returned; function results are JSON-string encoded."""
    value = json.loads(_result_section(stdout))
    return json.loads(value) if isinstance(value, str) else value


def _version_tuple(text: str) -> Optional[Tuple[int, ...]]:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", text.strip())
    return tuple(int(g) for g in match.groups()) if match else None


class WebDriver:
    """Drives one playwright-cli session for a web page or an Electron renderer.

    Every call runs in `run_dir` with `-s=<session>`. Actions return a DriverResult and raise
    DriverError on a `### Error` block or a non-zero exit, so a failed action can never be
    mistaken for a delivered one.
    """

    name = "playwright-cli"

    def __init__(self, session: str, run_dir: Path) -> None:
        self.session = session
        self.run_dir = Path(run_dir)

    def _bin(self) -> Optional[str]:
        override = os.environ.get(BIN_ENV)
        if override:
            return override if os.path.isfile(override) and os.access(override, os.X_OK) else None
        return shutil.which(BIN_NAME)

    def _run(self, args: List[str], session: bool = True) -> str:
        binary = self._bin()
        if binary is None:
            raise DriverError("playwright_missing", "%s not found" % BIN_NAME)
        argv = [binary] + (["-s=%s" % self.session] if session else []) + args
        try:
            proc = subprocess.run(
                argv, cwd=str(self.run_dir), capture_output=True, text=True,
                timeout=CALL_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            raise DriverError("playwright_timeout", " ".join(args[:2]))
        except OSError as exc:
            raise DriverError("playwright_missing", str(exc))
        failure = parse_error(proc.stdout)
        if failure is not None:
            raise DriverError("playwright_error", failure)
        if proc.returncode != 0:
            detail = (proc.stderr.strip() or proc.stdout.strip())[:500]
            raise DriverError("playwright_failed", "exit %d: %s" % (proc.returncode, detail))
        return proc.stdout

    def _eval(self, function: str, ref: Optional[str] = None) -> str:
        return self._run(["eval", function] + ([ref] if ref else []))

    def version(self) -> str:
        """Return the installed playwright-cli version string."""
        return self._run(["--version"], session=False).strip()

    def check(self) -> List[str]:
        """List what is missing or below the 0.1.22 pin; empty when the driver is usable."""
        if self._bin() is None:
            return [BIN_NAME]
        try:
            found = self.version()
        except DriverError:
            return ["%s (unreadable version)" % BIN_NAME]
        parsed = _version_tuple(found)
        if parsed is None:
            return ["%s (unreadable version)" % BIN_NAME]
        if parsed < PIN:
            return ["%s>=%s (found %s)" % (BIN_NAME, PIN_TEXT, found)]
        return []

    def open(self, url: str, headed: bool = False) -> None:
        """Open a browser session on `url`; headless unless `headed`."""
        self._run(["open", url] + (["--headed"] if headed else []))

    def attach_cdp(self, endpoint: str) -> None:
        """Attach the session to an already-running browser at a CDP endpoint."""
        self._run(["attach", "--cdp=%s" % endpoint])

    def attach_extension(self) -> None:
        """Attach through the Chrome extension; DriverError("extension_unavailable") if it fails."""
        try:
            self._run(["attach", "--extension=chrome"])
        except DriverError as exc:
            raise DriverError("extension_unavailable", exc.message or exc.code)

    def observe(self, screenshot_path: Optional[Path]) -> Observation:
        """Snapshot the page, and screenshot it too when a path is given.

        Screenshots are CSS-pixel sized, so the observation scale is 1.0.
        """
        obs = parse_snapshot(self._run(["snapshot"]), self.run_dir)
        if screenshot_path is not None:
            self._run(["screenshot", "--filename=%s" % screenshot_path])
            obs.screenshot_path = Path(screenshot_path)
            obs.scale = 1.0
        return obs

    def _viewport(self) -> Tuple[float, float]:
        try:
            width, height = _eval_json(self._eval(VIEWPORT_JS))
            return float(width), float(height)
        except (ValueError, TypeError):
            return DEFAULT_VIEWPORT

    def _click_steps(self, action: Action, count: int, right: bool) -> List[List[str]]:
        if action.ref:
            if count == 2:
                return [["dblclick", action.ref]]
            return [["click", action.ref] + (["right"] if right else [])]
        if action.x is None or action.y is None:
            raise DriverError("target_required", "%s needs --ref or --x/--y" % action.kind)
        button = ["right"] if right else []
        steps = [["mousemove", _num(action.x), _num(action.y)]]
        steps += [["mousedown"] + button, ["mouseup"] + button] * count
        return steps

    def _text_args(self, command: str, ref: Optional[str], text: str) -> List[str]:
        head = [command] + ([ref] if ref else [])
        return head + (["--", text] if text.startswith("-") else [text])

    def _plan(self, action: Action) -> List[List[str]]:
        kind = action.kind
        if kind in ("click", "dismiss"):
            return self._click_steps(action, 1, False)
        if kind == "double-click":
            return self._click_steps(action, 2, False)
        if kind == "right-click":
            return self._click_steps(action, 1, True)
        if kind == "fill":
            if not action.ref or action.text is None:
                raise DriverError("target_required", "fill needs --ref and text")
            return [self._text_args("fill", action.ref, action.text)]
        if kind == "type":
            if action.text is None:
                raise DriverError("target_required", "type needs text")
            steps = [["click", action.ref]] if action.ref else []
            return steps + [self._text_args("type", None, action.text)]
        if kind in ("press", "hotkey"):
            if not action.key:
                raise DriverError("target_required", "%s needs --key" % kind)
            return [["press", _chord(action.key) if kind == "hotkey" else action.key]]
        if kind == "select":
            if not action.ref or action.value is None:
                raise DriverError("target_required", "select needs --ref and --value")
            return [["select", action.ref, action.value]]
        if kind == "drag":
            return self._drag_steps(action)
        if kind == "scroll":
            return []
        raise DriverError("unsupported_action", kind)

    def _point_step(self, ref: Optional[str], x: Optional[float], y: Optional[float],
                    what: str) -> List[str]:
        if ref:
            return ["hover", ref]
        if x is None or y is None:
            raise DriverError("target_required", "drag needs %s" % what)
        return ["mousemove", _num(x), _num(y)]

    def _drag_steps(self, action: Action) -> List[List[str]]:
        if action.ref and action.to_ref:
            return [["drag", action.ref, action.to_ref]]
        start = self._point_step(action.ref, action.x, action.y, "a start (--ref or --x/--y)")
        end = self._point_step(action.to_ref, action.to_x, action.to_y,
                               "a destination (--to-ref or --to-x/--to-y)")
        return [start, ["mousedown"], end, ["mouseup"]]

    def _scroll_steps(self, action: Action) -> List[List[str]]:
        signs = {"down": (0, 1), "up": (0, -1), "right": (1, 0), "left": (-1, 0)}
        if action.direction not in signs:
            raise DriverError("target_required", "scroll needs --direction up|down|left|right")
        amount = 1.0 if action.amount is None else float(action.amount)
        width, height = self._viewport()
        sx, sy = signs[action.direction]
        steps: List[List[str]] = []
        if action.ref:
            steps.append(["hover", action.ref])
        elif action.x is not None and action.y is not None:
            steps.append(["mousemove", _num(action.x), _num(action.y)])
        steps.append(["mousewheel", _num(sx * amount * width), _num(sy * amount * height)])
        return steps

    def act(self, action: Action) -> DriverResult:
        """Perform one action; DriverError on a `### Error` block or non-zero exit.

        The result's observation is the page snapshot the final command printed, when it
        printed one; the caller observes again otherwise. playwright-cli does not verify
        delivery, so `driver_verified` is always None.
        """
        steps = self._scroll_steps(action) if action.kind == "scroll" else self._plan(action)
        out = ""
        for step in steps:
            out = self._run(step)
        try:
            observation = parse_snapshot(out, self.run_dir)
        except DriverError:
            observation = None
        return DriverResult(delivered=True, driver_verified=None, observation=observation, raw=out)

    def visibility(self, ref: str) -> Tuple[bool, str]:
        """Report whether a user could see and hit `ref`; reason is "" when they could.

        Reasons: display, hidden, opacity, offscreen, occluded. Observation-only: the page
        function reads layout and style and changes nothing.
        """
        try:
            data = _eval_json(self._eval(VISIBILITY_JS, ref))
            return bool(data["visible"]), str(data["reason"])
        except (ValueError, TypeError, KeyError):
            raise DriverError("visibility_unreadable", ref)

    def console_errors(self) -> List[str]:
        """Every error-level console message so far, oldest first."""
        messages: List[str] = []
        for line in self._run(["console", "error"]).splitlines():
            match = _CONSOLE_LINE.match(line)
            if match:
                messages.append(match.group(2) if match.group(1) == "ERROR" else None)
            elif messages and messages[-1] is not None and line.strip():
                messages[-1] += "\n" + line
        return [m for m in messages if m is not None]

    def failed_requests(self) -> List[dict]:
        """Every {url, status, method} with status >= 400 or no response, oldest first.

        A request with no response (blocked, refused, or still pending) has status 0.
        """
        failed = []
        for line in self._run(["requests", "--static"]).splitlines():
            match = _REQUEST_LINE.match(line.strip())
            if not match:
                continue
            method, url, status_text = match.groups()
            status = int(status_text) if status_text and status_text.isdigit() else 0
            if status == 0 or status >= 400:
                failed.append({"url": url, "status": status, "method": method})
        return failed

    def state_save(self, path: Path) -> None:
        """Write the browser's storage state (cookies, local storage) to `path`."""
        self._run(["state-save", str(path)])

    def state_load(self, path: Path) -> None:
        """Load a storage state previously written by `state_save`."""
        self._run(["state-load", str(path)])

    def close(self) -> None:
        """Close the session's browser."""
        self._run(["close"])

    def detach(self) -> None:
        """Detach from an attached browser without closing it."""
        self._run(["detach"])
