#!/usr/bin/env python3
"""Native-driver bake-off for the using-apps-like-a-user skill.

Delivers clicks and typed strings to the native fixture through each candidate driver's
background path while a sentinel app holds focus, polls the frontmost app and the cursor, and
scores each candidate. The winner is the candidate with zero focus steals and every input
landed; ties go to menu and dialog support; when nobody qualifies, `orca` wins and every
native action is foreground.

Re-runnable: `python3 bakeoff.py [--candidates peekaboo,cua,orca] [--clicks 10] [--strings 10]
[--out results.json] [--report bakeoff.md]`. macOS only; it launches two apps and sends real
input, so keep hands off the mouse and keyboard while it runs.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# loaded as a sibling of the other guard modules, which import each other as plain modules
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import _desktop  # noqa: E402

FIXTURE_BUNDLE_ID = "dev.quirk.uala.fixture"
SENTINEL_BUNDLE_ID = "dev.quirk.uala.sentinel"
CANDIDATES = ("peekaboo", "cua", "orca")
POLL_INTERVAL_S = 0.02
CURSOR_TOLERANCE_PT = 3.0
LAND_TIMEOUT_S = 2.0
COMMAND_TIMEOUT_S = 30.0
MIN_SAMPLE_INTERVAL_S = 0.1
BINARIES = {"peekaboo": "peekaboo", "cua": "cua-driver", "orca": "orca"}
WORKING_LABEL = "Working button"
NOTES_LABEL = "Notes"

# menu and dialog commands each driver ships, from its own tool list; used only to break ties
CAPABILITIES: Dict[str, Dict[str, bool]] = {
    "peekaboo": {"menu": True, "dialog": True},
    "cua": {"menu": True, "dialog": False},
    "orca": {"menu": False, "dialog": False},
}

SENTINEL_SWIFT = """\
import AppKit

final class SentinelDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!

    func applicationDidFinishLaunching(_ notification: Notification) {
        window = NSWindow(
            contentRect: NSRect(x: 20, y: 60, width: 260, height: 120),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        window.title = "UALA Sentinel"
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = SentinelDelegate()
app.delegate = delegate
app.run()
"""

_SENTINEL_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>UALASentinel</string>
  <key>CFBundleIdentifier</key><string>%s</string>
  <key>CFBundleName</key><string>UALASentinel</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSPrincipalClass</key><string>NSApplication</string>
</dict>
</plist>
""" % SENTINEL_BUNDLE_ID


def repo_root() -> Path:
    """The repository root, resolved from this script's location."""
    return Path(__file__).resolve().parents[3]


def analyze_samples(
    samples: Sequence[Tuple[float, str, Tuple[float, float]]],
    sentinel: str,
    cursor_tolerance: float = CURSOR_TOLERANCE_PT,
) -> Dict[str, Any]:
    """Score polled `(seconds, frontmost bundle id, (x, y))` samples against the sentinel.

    A focus steal starts when the frontmost app changes from the sentinel to anything else and
    lasts until the sentinel is frontmost again (or the last sample). A cursor move is a change
    of more than `cursor_tolerance` points between consecutive polls. Empty frontmost readings
    are ignored.
    """
    steals = 0
    steal_s = 0.0
    steal_start: Optional[float] = None
    seen_sentinel = False
    last_t = 0.0
    moves = 0
    prev_xy: Optional[Tuple[float, float]] = None
    for t, front, xy in samples:
        last_t = t
        if prev_xy is not None and math.hypot(xy[0] - prev_xy[0], xy[1] - prev_xy[1]) > cursor_tolerance:
            moves += 1
        prev_xy = xy
        if not front:
            continue
        if front == sentinel:
            seen_sentinel = True
            if steal_start is not None:
                steal_s += t - steal_start
                steal_start = None
        elif seen_sentinel and steal_start is None:
            steals += 1
            steal_start = t
    if steal_start is not None:
        steal_s += last_t - steal_start
    return {
        "focus_steals": steals,
        "focus_steal_ms": steal_s * 1000.0,
        "cursor_moves": moves,
        "samples": len(samples),
    }


def required_samples(action_s: float) -> int:
    """Fewest polls that cover an action interval at one per `MIN_SAMPLE_INTERVAL_S`, at least one."""
    return max(1, int(action_s / MIN_SAMPLE_INTERVAL_S))


def qualifies(result: Dict[str, Any]) -> bool:
    """True when a candidate measured zero focus steals, every input landed, and polling held up.

    A candidate with poller errors or too few samples for its action interval has no trustworthy
    focus measurement, so zero steals proves nothing and it does not qualify.
    """
    if result.get("error") or result.get("poller_errors"):
        return False
    if int(result.get("samples", 0)) < required_samples(float(result.get("action_s", 0.0))):
        return False
    clicks = int(result.get("clicks", 0))
    strings = int(result.get("strings", 0))
    if clicks + strings == 0:
        return False
    return (
        int(result.get("focus_steals", 1)) == 0
        and int(result.get("clicks_landed", 0)) == clicks
        and int(result.get("strings_landed", 0)) == strings
    )


def choose_winner(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply the winner rule to per-candidate results.

    Qualifiers (zero steals, everything landed, polling healthy) are ranked by menu plus dialog support, ties
    keeping the listed order. No qualifier means `orca` with `background_capable` false, and so
    does an `orca` win: it has no background path.
    """
    qualified = [r for r in results if qualifies(r)]
    names = [str(r["name"]) for r in qualified]
    if not qualified:
        return {
            "winner": "orca",
            "background_capable": False,
            "qualified": [],
            "reason": "no candidate had zero focus steals and every input landed; "
                      "every native action is foreground",
        }
    best = max(qualified, key=lambda r: int(bool(r.get("menu"))) + int(bool(r.get("dialog"))))
    name = str(best["name"])
    if name == "orca":
        return {
            "winner": "orca",
            "background_capable": False,
            "qualified": names,
            "reason": "orca qualified but has no background path; every native action is foreground",
        }
    support = int(bool(best.get("menu"))) + int(bool(best.get("dialog")))
    return {
        "winner": name,
        "background_capable": True,
        "qualified": names,
        "reason": "zero focus steals and every input landed"
                  + ("; tie broken by menu and dialog support" if len(qualified) > 1 and support else ""),
    }


def make_strings(count: int) -> List[str]:
    """Short distinct strings, none a substring of another."""
    return [f"uala{i:02d}z" for i in range(1, count + 1)]


def count_landed_strings(text: Optional[str], strings: Sequence[str]) -> int:
    """How many of `strings` appear in the fixture's text field content."""
    haystack = text or ""
    return sum(1 for s in strings if s in haystack)


def read_state(path: Path) -> Dict[str, Any]:
    """The fixture's state file as a dict, or `{}` when missing or mid-write."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def parse_orca_index(tree_text: str, label: str) -> Optional[int]:
    """The element index of the first `orca computer get-app-state` tree row ending in `label`."""
    for line in tree_text.splitlines():
        m = re.match(r"^\t*(\d+) (.*)$", line)
        if not m:
            continue
        row = re.split(r", (?:Value:|Secondary Actions:)", m.group(2), maxsplit=1)[0]
        if row == label or row.endswith(" " + label):
            return int(m.group(1))
    return None


def parse_frame(text: str) -> Optional[Tuple[float, float, float, float]]:
    """Parse System Events `x, y, w, h` output into a tuple, or None when it is not four numbers."""
    parts = [p.strip() for p in text.strip().split(",")]
    if len(parts) != 4:
        return None
    try:
        x, y, w, h = (float(p) for p in parts)
    except ValueError:
        return None
    return x, y, w, h


def window_local_center(field: Tuple[float, float, float, float],
                        window: Tuple[float, float, float, float]) -> Tuple[int, int]:
    """Center of `field` in coordinates relative to `window`'s top-left, both given as x, y, w, h."""
    return (int(round(field[0] + field[2] / 2 - window[0])), int(round(field[1] + field[3] / 2 - window[1])))


def find_in_json(doc: Any, predicate: Callable[[Dict[str, Any]], bool]) -> Optional[Dict[str, Any]]:
    """Depth-first search for the first dict in `doc` satisfying `predicate`."""
    if isinstance(doc, dict):
        if predicate(doc):
            return doc
        children: List[Any] = list(doc.values())
    elif isinstance(doc, list):
        children = doc
    else:
        return None
    for child in children:
        hit = find_in_json(child, predicate)
        if hit is not None:
            return hit
    return None


def find_key(doc: Any, keys: Sequence[str]) -> Any:
    """Depth-first search for the first value stored under any of `keys`."""
    if isinstance(doc, dict):
        for key in keys:
            if key in doc and doc[key] not in (None, ""):
                return doc[key]
        children: List[Any] = list(doc.values())
    elif isinstance(doc, list):
        children = doc
    else:
        return None
    for child in children:
        hit = find_key(child, keys)
        if hit is not None:
            return hit
    return None


def parse_json_output(stdout: str) -> Any:
    """Parse a driver's stdout as JSON, tolerating log lines around the object."""
    try:
        return json.loads(stdout)
    except ValueError:
        pass
    start, end = stdout.find("{"), stdout.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(stdout[start:end + 1])
        except ValueError:
            return None
    return None


_LABEL_KEYS = ("label", "title", "description", "name")
_ID_KEYS = ("element_token", "id", "element_id", "identifier")


def find_element(doc: Any, label: str, role_hint: str) -> Optional[Dict[str, Any]]:
    """Find an element dict in a driver's JSON by accessible label, preferring `role_hint`."""
    matches: List[Dict[str, Any]] = []

    def collect(node: Any) -> None:
        if isinstance(node, dict):
            has_label = any(str(node.get(k, "")).strip() == label for k in _LABEL_KEYS)
            has_id = any(node.get(k) not in (None, "") for k in _ID_KEYS)
            if has_label and has_id:
                matches.append(node)
            for child in node.values():
                collect(child)
        elif isinstance(node, list):
            for child in node:
                collect(child)

    collect(doc)
    for node in matches:
        if role_hint in str(node.get("role", "")).lower():
            return node
    return matches[0] if matches else None


def element_id(node: Dict[str, Any]) -> str:
    """The id a driver's action command takes for an element dict."""
    for key in _ID_KEYS:
        if node.get(key) not in (None, ""):
            return str(node[key])
    return ""


class Recorder:
    """Collects the command lines, exit codes, and failures of one candidate's run."""

    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir
        self.commands: Dict[str, List[str]] = {}
        self.exit_codes: List[Dict[str, Any]] = []
        self.failures: List[Dict[str, Any]] = []

    def run(self, role: str, argv: List[str], stdin: Optional[str] = None) -> Tuple[int, str, str]:
        """Run one driver command, record it, and return `(returncode, stdout, stderr)`."""
        self.commands.setdefault(role, list(argv))
        try:
            proc = subprocess.run(
                argv, input=stdin, capture_output=True, text=True,
                timeout=COMMAND_TIMEOUT_S, cwd=str(self.workdir),
            )
            rc, out, err = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            rc, out, err = 124, "", "timed out"
        except OSError as exc:
            rc, out, err = 127, "", str(exc)
        self.exit_codes.append({"role": role, "returncode": rc})
        doc = parse_json_output(out)
        reported_error = isinstance(doc, dict) and (
            doc.get("ok") is False or doc.get("isError") is True or doc.get("success") is False
            or doc.get("status") == "refused" or "refusal" in doc)
        if rc != 0 or reported_error:
            self.failures.append({
                "role": role, "returncode": rc,
                "stdout": out[-400:], "stderr": err[-400:],
            })
        return rc, out, err


class Adapter:
    """A candidate driver's discovery and input commands against the fixture app."""

    name = ""

    def __init__(self, rec: Recorder, bundle_id: str, pid: int) -> None:
        self.rec = rec
        self.bundle_id = bundle_id
        self.pid = pid

    def version(self) -> str:
        raise NotImplementedError

    def prepare(self) -> None:
        """Observe the fixture window and resolve the elements later commands act on."""
        raise NotImplementedError

    def focus_text(self) -> None:
        """Give the notes field keyboard focus through the driver."""
        raise NotImplementedError

    def click_working(self) -> None:
        raise NotImplementedError

    def type_string(self, text: str) -> None:
        raise NotImplementedError


class OrcaAdapter(Adapter):
    name = "orca"

    def version(self) -> str:
        return _first_line(_capture(["orca", "--version"]))

    def _base(self) -> List[str]:
        return ["--app", self.bundle_id, "--json", "--no-screenshot"]

    def prepare(self) -> None:
        rc, out, _ = self.rec.run("observe", ["orca", "computer", "get-app-state"] + self._base())
        doc = parse_json_output(out) or {}
        tree = str(find_key(doc, ("treeText",)) or "")
        self.working = parse_orca_index(tree, WORKING_LABEL)
        self.notes = parse_orca_index(tree, NOTES_LABEL)

    def _notes_point(self) -> Optional[Tuple[int, int]]:
        """Window-local center of the notes field; orca's tree carries no frames."""
        script = (
            'tell application "System Events" to tell (first process whose bundle identifier is "%s") to '
            "get {%s} of %s"
        )
        frames = []
        for prop, target in (("position, size", "text field 1 of group 1 of window 1"),
                             ("position, size", "window 1")):
            out = _capture(["osascript", "-e", script % (self.bundle_id, prop, target)])
            frames.append(parse_frame(out))
        if frames[0] is None or frames[1] is None:
            return None
        return window_local_center(frames[0], frames[1])

    def _click(self, role: str, index: Optional[int]) -> None:
        if index is None:
            self.rec.failures.append({"role": role, "returncode": -1, "stderr": "element not found in tree"})
            return
        self.rec.run(role, ["orca", "computer", "click", "--element-index", str(index)] + self._base())

    def focus_text(self) -> None:
        point = self._notes_point()
        if point is None:
            self.rec.failures.append({"role": "focus_text", "returncode": -1, "stderr": "notes field frame unknown"})
            return
        # an element click on a text field only AXConfirms it; a pointer click is what gives it focus
        self.rec.run("focus_text", ["orca", "computer", "click", "--x", str(point[0]), "--y", str(point[1])]
                     + self._base())

    def click_working(self) -> None:
        self._click("click", self.working)

    def type_string(self, text: str) -> None:
        self.rec.run("type", ["orca", "computer", "type-text", "--text", text] + self._base())


class PeekabooAdapter(Adapter):
    name = "peekaboo"

    def version(self) -> str:
        return _first_line(_capture(["peekaboo", "--version"]))

    def prepare(self) -> None:
        """Take a fresh snapshot; peekaboo marks a snapshot stale once it has driven a mutation."""
        shot = self.rec.workdir / "peekaboo-see.png"
        rc, out, _ = self.rec.run(
            "observe", ["peekaboo", "see", "--app", self.bundle_id, "--json", "--path", str(shot)])
        doc = parse_json_output(out) or {}
        self.snapshot = str(find_key(doc, ("snapshot_id", "snapshotId")) or "")
        working = find_element(doc, WORKING_LABEL, "button")
        notes = find_element(doc, NOTES_LABEL, "field")
        self.working = element_id(working) if working else ""
        self.notes = element_id(notes) if notes else ""

    def _click(self, role: str, element: str) -> None:
        if not element:
            self.rec.failures.append({"role": role, "returncode": -1, "stderr": "element not found"})
            return
        self.rec.run(role, ["peekaboo", "click", "--on", element, "--snapshot", self.snapshot,
                            "--app", self.bundle_id, "--json"])

    def focus_text(self) -> None:
        self.prepare()
        self._click("focus_text", self.notes)

    def click_working(self) -> None:
        self.prepare()
        self._click("click", self.working)

    def type_string(self, text: str) -> None:
        self.prepare()
        self.rec.run("type", ["peekaboo", "type", text, "--snapshot", self.snapshot,
                              "--app", self.bundle_id, "--clear", "--json"])


class CuaAdapter(Adapter):
    name = "cua"
    session = "bakeoff"

    def version(self) -> str:
        return _first_line(_capture(["cua-driver", "--version"]))

    def _call(self, role: str, tool: str, args: Dict[str, Any]) -> Any:
        payload = dict(args, session=self.session)
        rc, out, _ = self.rec.run(role, ["cua-driver", "call", tool, json.dumps(payload, separators=(",", ":"))])
        return parse_json_output(out)

    def prepare(self) -> None:
        windows = self._call("list_windows", "list_windows", {"pid": self.pid})
        win = find_in_json(windows, lambda d: "window_id" in d)
        self.window_id = int(win["window_id"]) if win else 0
        self._snapshot()

    def _snapshot(self) -> None:
        doc = self._call("observe", "get_window_state",
                         {"pid": self.pid, "window_id": self.window_id, "include_screenshot": False})
        working = find_element(doc, WORKING_LABEL, "button")
        notes = find_element(doc, NOTES_LABEL, "field")
        self.working = element_id(working) if working else ""
        self.notes = element_id(notes) if notes else ""

    def _target(self, token: str) -> Dict[str, Any]:
        return {"pid": self.pid, "window_id": self.window_id, "element_token": token}

    def focus_text(self) -> None:
        self._snapshot()

    def click_working(self) -> None:
        self._call("click", "click", self._target(self.working))

    def type_string(self, text: str) -> None:
        args = self._target(self.notes)
        args["text"] = text
        self._call("type", "type_text", args)


ADAPTERS = {"peekaboo": PeekabooAdapter, "cua": CuaAdapter, "orca": OrcaAdapter}


def _capture(argv: List[str]) -> str:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (proc.stdout or proc.stderr).strip()


def _first_line(text: str) -> str:
    return text.splitlines()[0] if text else ""


def wait_for(predicate: Callable[[], bool], timeout_s: float, poll_s: float = 0.02) -> bool:
    """Poll `predicate` until it holds or `timeout_s` passes."""
    deadline = time.monotonic() + timeout_s
    while True:
        if predicate():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_s)


class Poller:
    """Samples the frontmost bundle id and cursor position on a background thread."""

    def __init__(self, interval_s: float = POLL_INTERVAL_S) -> None:
        self.interval_s = interval_s
        self.samples: List[Tuple[float, str, Tuple[float, float]]] = []
        self.errors: List[str] = []
        self.duration_s = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._t0 = 0.0
        self._started = False

    def start(self) -> None:
        self._t0 = time.monotonic()
        self._started = True
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            began = time.monotonic()
            try:
                front = _desktop.frontmost_bundle_id()
                xy = _desktop.cursor()
                self.samples.append((began - self._t0, front, xy))
            except Exception as exc:
                self.errors.append(f"{type(exc).__name__}: {exc}")
            rest = self.interval_s - (time.monotonic() - began)
            if rest > 0:
                self._stop.wait(rest)

    def stop(self) -> None:
        """Stop sampling; the first call fixes `duration_s` as the time since `start`."""
        self._stop.set()
        if not self._started:
            return
        if not self.duration_s:
            self.duration_s = time.monotonic() - self._t0
        self._thread.join(timeout=5)


def build_sentinel(out_dir: Path) -> Path:
    """Compile the sentinel app into `out_dir` and return its `.app` path."""
    app = out_dir / "UALASentinel.app"
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    (app / "Contents" / "Info.plist").write_text(_SENTINEL_PLIST)
    src = out_dir / "sentinel.swift"
    src.write_text(SENTINEL_SWIFT)
    subprocess.run(["swiftc", "-O", "-o", str(macos / "UALASentinel"), str(src)],
                   check=True, capture_output=True, text=True)
    subprocess.run(["codesign", "--force", "--sign", "-", str(app)], capture_output=True)
    return app


def build_fixture(out_dir: Path) -> Path:
    """Build the native fixture with its build script and return the `.app` path."""
    script = repo_root() / "tests" / "fixtures" / "using-apps-like-a-user" / "native" / "build.sh"
    proc = subprocess.run(["bash", str(script), str(out_dir)], check=True, capture_output=True, text=True)
    return Path(proc.stdout.strip().splitlines()[-1])


def _executable(app: Path) -> Path:
    return next((app / "Contents" / "MacOS").iterdir())


def _stop_process(proc: Optional["subprocess.Popen[bytes]"]) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def run_candidate(
    name: str,
    clicks: int,
    strings: int,
    fixture_app: Path,
    sentinel_app: Path,
    workdir: Path,
) -> Dict[str, Any]:
    """Measure one candidate; the fixture and sentinel are quit before returning."""
    rec = Recorder(workdir)
    state_path = workdir / f"state-{name}.json"
    if state_path.exists():
        state_path.unlink()
    env = dict(os.environ, LIKEUSER_FIXTURE_STATE=str(state_path))
    fixture: Optional["subprocess.Popen[bytes]"] = None
    sentinel: Optional["subprocess.Popen[bytes]"] = None
    poller = Poller()
    result: Dict[str, Any] = {
        "name": name, "clicks": clicks, "strings": strings,
        "menu": CAPABILITIES[name]["menu"], "dialog": CAPABILITIES[name]["dialog"],
    }
    inputs = make_strings(strings)
    try:
        fixture = subprocess.Popen([str(_executable(fixture_app))], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not wait_for(state_path.exists, 15):
            raise RuntimeError("fixture never wrote its state file")
        wait_for(lambda: _desktop.frontmost_bundle_id() == FIXTURE_BUNDLE_ID, 10)
        time.sleep(1.0)
        sentinel = subprocess.Popen([str(_executable(sentinel_app))],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not wait_for(lambda: _desktop.frontmost_bundle_id() == SENTINEL_BUNDLE_ID, 10):
            _desktop.activate(SENTINEL_BUNDLE_ID)
            if not wait_for(lambda: _desktop.frontmost_bundle_id() == SENTINEL_BUNDLE_ID, 10):
                raise RuntimeError("sentinel never became frontmost")
        time.sleep(0.5)

        adapter = ADAPTERS[name](rec, FIXTURE_BUNDLE_ID, fixture.pid)
        result["version"] = adapter.version()
        base_clicks = int(read_state(state_path).get("hits", {}).get("working", 0))
        poller.start()
        adapter.prepare()
        clicks_landed = 0
        for i in range(clicks):
            adapter.click_working()
            if wait_for(lambda: int(read_state(state_path).get("hits", {}).get("working", 0))
                        >= base_clicks + i + 1, LAND_TIMEOUT_S):
                clicks_landed += 1
        adapter.focus_text()
        strings_landed = 0
        for text in inputs:
            adapter.type_string(text)
            if wait_for(lambda: text in str(read_state(state_path).get("text", "")), LAND_TIMEOUT_S):
                strings_landed += 1
        poller.stop()
        result["clicks_landed"] = clicks_landed
        result["strings_landed"] = strings_landed
        result["final_hits_working"] = int(read_state(state_path).get("hits", {}).get("working", 0))
        result["final_text"] = str(read_state(state_path).get("text", ""))
    # a broken candidate must not abort the others
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result.setdefault("clicks_landed", 0)
        result.setdefault("strings_landed", 0)
    finally:
        poller.stop()
        _stop_process(sentinel)
        _stop_process(fixture)
    result.update(analyze_samples(poller.samples, SENTINEL_BUNDLE_ID))
    result["action_s"] = poller.duration_s
    result["poller_errors"] = len(poller.errors)
    if poller.errors:
        result["poller_error"] = poller.errors[0]
    result["commands"] = rec.commands
    result["exit_codes"] = rec.exit_codes
    result["failures"] = rec.failures
    return result


def run_once(args: argparse.Namespace, fixture_app: Path, sentinel_app: Path, workdir: Path) -> Dict[str, Any]:
    """One full pass over the selected candidates, returning results plus the winner verdict."""
    results = []
    for name in args.candidates:
        results.append(run_candidate(name, args.clicks, args.strings, fixture_app, sentinel_app, workdir))
        time.sleep(1.0)
    return {"results": results, "verdict": choose_winner(results)}


def render_report(meta: Dict[str, Any], runs: Sequence[Dict[str, Any]]) -> str:
    """Render bakeoff.md text from run metadata and one or more `run_once` outputs."""
    lines = ["# Native-driver bake-off", ""]
    lines.append(f"Date: {meta.get('date', '')}  ")
    lines.append(f"Machine: {meta.get('machine', '')}  ")
    versions = meta.get("versions", {})
    lines.append("Versions: " + ", ".join(f"{k} {v}" for k, v in versions.items()))
    lines.append("")
    final = runs[-1]["verdict"] if runs else choose_winner([])
    winners = [r["verdict"]["winner"] for r in runs]
    lines.append(f"**Winner:** {final['winner']}")
    lines.append("")
    lines.append(f"background_capable: {str(final['background_capable']).lower()}  ")
    lines.append(f"Runs: {len(runs)} (winners: {', '.join(winners)})  ")
    lines.append(f"Reason: {final['reason']}")
    for n, run in enumerate(runs, 1):
        lines += ["", f"## Run {n}", "",
                  "| candidate | steals | steal ms | cursor moves | clicks landed | strings landed | menu | dialog |",
                  "|---|---|---|---|---|---|---|---|"]
        for r in run["results"]:
            lines.append(
                f"| {r['name']} | {r.get('focus_steals', '')} | {round(r.get('focus_steal_ms', 0))} "
                f"| {r.get('cursor_moves', '')} | {r.get('clicks_landed', 0)}/{r.get('clicks', '')} "
                f"| {r.get('strings_landed', 0)}/{r.get('strings', '')} "
                f"| {'yes' if r.get('menu') else 'no'} | {'yes' if r.get('dialog') else 'no'} |")
            if r.get("error"):
                lines.append(f"|  | error: {r['error']} | | | | | | |")
        lines.append("")
        for r in run["results"]:
            lines.append(f"- {r['name']} verdict: {'qualified' if qualifies(r) else 'disqualified'}"
                         f"; failures: {len(r.get('failures', []))}")
    last = runs[-1] if runs else {"results": []}
    lines += ["", "## Commands used", ""]
    for r in last["results"]:
        lines.append(f"### {r['name']} {r.get('version', '')}".rstrip())
        lines.append("")
        lines.append("```")
        for role, argv in r.get("commands", {}).items():
            lines.append(f"{role}: {' '.join(_shell_quote(a) for a in argv)}")
        lines.append("```")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _shell_quote(arg: str) -> str:
    return arg if re.fullmatch(r"[\w@%+=:,./-]+", arg) else "'" + arg.replace("'", "'\\''") + "'"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse the CLI; `--candidates` is validated against the known drivers."""
    parser = argparse.ArgumentParser(description="Native-driver bake-off")
    parser.add_argument("--candidates", default=",".join(CANDIDATES),
                        help="comma-separated subset of peekaboo,cua,orca")
    parser.add_argument("--clicks", type=int, default=10)
    parser.add_argument("--strings", type=int, default=10)
    parser.add_argument("--runs", type=int, default=1,
                        help="full passes; a third runs automatically when two disagree on the winner")
    parser.add_argument("--out", help="write the JSON results here")
    parser.add_argument("--report", help="write the markdown report here")
    parser.add_argument("--fixture-app", help="use this built fixture .app instead of building one")
    ns = parser.parse_args(argv)
    names = [n.strip() for n in ns.candidates.split(",") if n.strip()]
    unknown = [n for n in names if n not in CANDIDATES]
    if unknown or not names:
        parser.error(f"unknown candidates: {', '.join(unknown) or '(none)'}")
    ns.candidates = names
    return ns


def machine_description() -> str:
    """`sw_vers` and hardware model on one line."""
    parts = [_capture(["sw_vers", "-productName"]), _capture(["sw_vers", "-productVersion"]),
             f"(build {_capture(['sw_vers', '-buildVersion'])})", "on",
             _capture(["sysctl", "-n", "hw.model"])]
    return " ".join(p for p in parts if p)


def check_readiness(
    candidates: Sequence[str],
    which: Callable[[str], Optional[str]] = shutil.which,
    capture: Callable[[List[str]], str] = _capture,
) -> List[str]:
    """Name what each selected candidate still lacks before any app launches; empty when ready.

    Every driver needs its binary on PATH. Cua also needs Accessibility and Screen Recording
    granted (`cua-driver permissions status --json`), and Peekaboo its required permissions
    (`peekaboo permissions --json`); without them a run reports driver failures instead of a
    failed precondition. Orca's permission is not probed because that command opens System Settings.
    """
    missing: List[str] = []
    for name in candidates:
        binary = BINARIES[name]
        if which(binary) is None:
            missing.append(f"{binary} is not on PATH")
            continue
        if name == "cua":
            doc = parse_json_output(capture(["cua-driver", "permissions", "status", "--json"]))
            if not isinstance(doc, dict):
                missing.append("cua-driver permissions status --json returned no JSON")
                continue
            for key, label in (("accessibility", "Accessibility"), ("screen_recording", "Screen Recording")):
                if doc.get(key) is not True:
                    missing.append(f"cua-driver lacks {label} permission")
        elif name == "peekaboo":
            doc = parse_json_output(capture(["peekaboo", "permissions", "--json"]))
            perms = doc.get("data", {}).get("permissions") if isinstance(doc, dict) else None
            if not isinstance(perms, list):
                missing.append("peekaboo permissions --json returned no permission list")
                continue
            for perm in perms:
                if isinstance(perm, dict) and perm.get("isRequired") and not perm.get("isGranted"):
                    missing.append(f"peekaboo lacks {perm.get('name', 'a required')} permission")
    return missing


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if sys.platform != "darwin":
        print("bakeoff.py needs macOS", file=sys.stderr)
        return 2
    missing = check_readiness(args.candidates)
    if missing:
        for line in missing:
            print(line, file=sys.stderr)
        return 2

    original = _desktop.frontmost_bundle_id()
    runs: List[Dict[str, Any]] = []
    tmp = Path(tempfile.mkdtemp(prefix="uala-bakeoff."))
    try:
        fixture_app = Path(args.fixture_app) if args.fixture_app else build_fixture(tmp / "fixture")
        sentinel_app = build_sentinel(tmp)
        passes = max(1, args.runs)
        for _ in range(passes):
            runs.append(run_once(args, fixture_app, sentinel_app, tmp))
        if passes >= 2 and runs[0]["verdict"]["winner"] != runs[1]["verdict"]["winner"]:
            runs.append(run_once(args, fixture_app, sentinel_app, tmp))
    finally:
        if original and _desktop.frontmost_bundle_id() != original:
            try:
                _desktop.activate(original)
            except Exception:
                pass
        shutil.rmtree(tmp, ignore_errors=True)

    versions = {r["name"]: r.get("version", "") for r in runs[-1]["results"]} if runs else {}
    meta = {"date": datetime.date.today().isoformat(), "machine": machine_description(), "versions": versions}
    payload = {"meta": meta, "runs": runs}
    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2) + "\n")
    if args.report:
        Path(args.report).write_text(render_report(meta, runs))
    print(json.dumps({"winners": [r["verdict"]["winner"] for r in runs],
                      "verdict": runs[-1]["verdict"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
