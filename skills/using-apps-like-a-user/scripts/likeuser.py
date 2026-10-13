#!/usr/bin/env python3
"""likeuser: the single entrypoint every UI action goes through for using-apps-like-a-user.

Each subcommand is its own process, prints exactly one JSON object on stdout, and keeps
diagnostics on stderr. Exit codes: 0 ran (an `act` outcome is in `status`), 1 internal error,
2 usage or contract violation, 3 run-state error, 4 driver failure outside `act`, 5 missing
tool, version, permission, extension, or credentials.

Run state lives in `<state root>/runs/<run-id>/`; the modules `_run`, `_effects`, `_desktop`,
`_web`, and `_native` hold the bookkeeping, the effect classifier, the macOS primitives, and the
two driver adapters this script composes.
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import fcntl
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

# loaded both as `python3 .../likeuser.py` (sys.path[0] is already this directory) and via
# importlib file-path loading in tests (which doesn't set sys.path at all) -- make the sibling
# imports work either way.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import _desktop  # noqa: E402
import _effects  # noqa: E402
import _run  # noqa: E402
from _native import NATIVE_DRIVER_PREFERENCE, NativeDriver, get_native_driver, stable_ref  # noqa: E402
from _types import (  # noqa: E402
    Action, DriverError, DriverResult, MissingError, Observation, RunStateError, UsageError,
)
from _web import PIN_TEXT, WebDriver  # noqa: E402

SURFACES = ("web", "electron", "native")
FAULTS = frozenset({
    "never_observed", "always_observed", "skip_visibility", "drop_network", "skip_gate",
    "skip_stale", "skip_drift", "allow_unverified_pass",
})
LOCK_WAIT_S = _run.LOCK_WAIT_S
LAUNCH_WAIT_S = 30.0
WINDOW_WAIT_S = 10.0
PID_BUNDLE_WAIT_S = 5.0
DRIFT_TOLERANCE_PT = 3.0
PASTE_MIN_CHARS = 200
PASTE_HOTKEY = "CmdOrCtrl+V"
SHEET_CLOSE_WAIT_S = 1.0
SHEET_LEFT_OPEN = "native sheet or dialog still open"
SCREENSHOT_WITHHELD = (
    "no screenshot was saved because a credential may be on screen; the tree and signals are recorded")
REFUSED_BEFORE_DELIVERY = ("needs_foreground", "window_gone")
MIN_REDACT_CHARS = 4
CDP_PORTS = range(9222, 9300)
CDP_LOCK_NAME = "cdp-ports.lock"
DEFAULT_CREDENTIALS_PREFIX = "LIKEUSER"
SENSITIVE_ENV_NAME = re.compile(
    r"(?:(?:^|_)(?:KEYS?|TOKEN|SECRETS?|PASSWORD|PASSWD|PASS|CREDENTIALS?|AUTH|SESSION|COOKIE)|_PWD)$"
    r"|^(?:AWS_|AZURE_|GCLOUD_|CLOUDSDK_|GH_|GITHUB_|GITLAB_|OP_|VAULT_|NPM_CONFIG__AUTH)"
    r"|^(?:GOOGLE_APPLICATION_CREDENTIALS|NPM_TOKEN|SSH_AUTH_SOCK|DOCKER_AUTH_CONFIG|KUBECONFIG)$",
    re.IGNORECASE)
GOAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SESSION_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
NATIVE_PREFIX = "n:"

ACTION_KINDS = (
    "click", "double-click", "right-click", "fill", "type", "press", "hotkey", "scroll",
    "drag", "select", "dismiss",
)
POINT_KINDS = ("click", "double-click", "right-click")
FOCUSED_VALUE_KINDS = ("type", "press", "hotkey")
EXPECTS = ("url", "title", "tree", "focus", "value", "screen", "any")
GATES = ("none", "requested", "approved", "created")
FINDING_KINDS = (
    "visibility", "accessibility", "console", "network", "injection", "undiscoverable", "other",
)
VERDICTS = ("pass", "fail", "blocked", "partial")
HANDOFF_REASONS = ("login", "2fa", "hint")
LOGIN_SUBMIT_RE = re.compile(r"\b(sign[\s-]?in|log[\s-]?in|submit|continue|next)\b", re.IGNORECASE)
ENTER_KEYS = ("enter", "return")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _digest(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def _write_text(path: Path, text: str, mode: int = _run.PRIVATE_FILE_MODE) -> None:
    """Replace `path` with `text` through a temp file that is never readable beyond `mode`."""
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        os.fchmod(handle.fileno(), mode)
        handle.write(text)
    os.replace(str(tmp), str(path))


def _scrub(value: Any, secrets) -> Any:
    secrets = [s for s in secrets if s]
    if not secrets:
        return value
    if isinstance(value, str):
        return _run.redact(value, secrets)
    if isinstance(value, dict):
        return {_scrub(k, secrets): _scrub(v, secrets) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v, secrets) for v in value]
    return value


class _Parser(argparse.ArgumentParser):
    """Argument parser whose errors surface as `UsageError` instead of exiting with text."""

    def error(self, message: str):
        raise UsageError("bad_arguments", message)


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI parser with one subparser per verb."""
    parser = _Parser(prog="likeuser.py", description=(
        "Guarded UI actions for web, Electron, and native macOS apps. Every subcommand prints "
        "one JSON object on stdout."))
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    p = sub.add_parser("doctor", help="check tools, versions, and macOS permissions")
    p.add_argument("--surface", choices=SURFACES)

    p = sub.add_parser("begin", help="open a run: folder, baseline, driver session")
    p.add_argument("--target", required=True)
    p.add_argument("--surface", required=True, choices=SURFACES)
    p.add_argument("--owner", required=True, choices=("yours", "third-party"))
    attend = p.add_mutually_exclusive_group(required=True)
    attend.add_argument("--attended", action="store_true")
    attend.add_argument("--unattended", action="store_true")
    p.add_argument("--launch")
    p.add_argument("--cdp-port", type=int)
    p.add_argument("--real-chrome", action="store_true")
    p.add_argument("--allow-foreground", action="store_true")
    p.add_argument("--launch-env", action="append", default=[], metavar="NAME")
    p.add_argument("--session-key")
    creds = p.add_mutually_exclusive_group()
    creds.add_argument("--credentials-env", metavar="PREFIX")
    creds.add_argument("--credentials-file", metavar="PATH")
    p.add_argument("--goals-file")
    p.add_argument("--budget-run", type=int)
    p.add_argument("--budget-goal", type=int)

    p = sub.add_parser("goal", help="register a goal")
    p.add_argument("--run", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--title-stdin", action="store_true", required=True)

    p = sub.add_parser("observe", help="capture the current screen and tree for a goal")
    p.add_argument("--run", required=True)
    p.add_argument("--goal", required=True)
    p.add_argument("--no-screenshot", action="store_true")

    p = sub.add_parser("act", help="perform one guarded action and report its effect")
    p.add_argument("--run", required=True)
    p.add_argument("--obs", required=True, type=int)
    p.add_argument("--action", required=True, choices=ACTION_KINDS)
    p.add_argument("--ref")
    p.add_argument("--x", type=float)
    p.add_argument("--y", type=float)
    p.add_argument("--to-ref")
    p.add_argument("--to-x", type=float)
    p.add_argument("--to-y", type=float)
    p.add_argument("--text-stdin", action="store_true")
    p.add_argument("--secret", choices=("username", "password"))
    p.add_argument("--key")
    p.add_argument("--value")
    p.add_argument("--direction", choices=("up", "down", "left", "right"))
    p.add_argument("--amount", type=float)
    p.add_argument("--expect", choices=EXPECTS, default="any")
    p.add_argument("--gate", choices=GATES, default="none")
    p.add_argument("--foreground", action="store_true")
    p.add_argument("--target-name")

    p = sub.add_parser("note", help="register a finding the model noticed")
    p.add_argument("--run", required=True)
    p.add_argument("--finding-kind", required=True, choices=FINDING_KINDS)
    p.add_argument("--summary-stdin", action="store_true", required=True)
    p.add_argument("--obs", type=int)

    p = sub.add_parser("verdict", help="set a goal's status")
    p.add_argument("--run", required=True)
    p.add_argument("--goal", required=True)
    p.add_argument("--status", required=True, choices=VERDICTS)
    p.add_argument("--summary-stdin", action="store_true", required=True)

    p = sub.add_parser("handoff", help="release the desktop and let the user act (attended)")
    p.add_argument("--run", required=True)
    p.add_argument("--reason", required=True, choices=HANDOFF_REASONS)

    p = sub.add_parser("resume", help="take the run back after a handoff")
    p.add_argument("--run", required=True)

    p = sub.add_parser("end", help="restore the desktop, close the run, write the reports")
    p.add_argument("--run", required=True)
    p.add_argument("--keep-open", action="store_true")
    return parser


class Snap(NamedTuple):
    """One observation of the bound surface: a renderer view, a native view, or both."""

    renderer: Optional[Observation]
    native: Optional[Observation]
    sheet: bool
    source: Optional[str]
    screenshot: Optional[Path]
    scale: Optional[float]
    native_error: Optional[str] = None
    screenshot_withheld: bool = False


class Ctx:
    """Per-process state shared by a verb handler and `main`."""

    def __init__(self) -> None:
        self.run: Optional[_run.Run] = None
        self.root: Optional[Path] = None
        self.inputs: Dict[str, Any] = {}
        self.status = "ok"
        self.goal_id: Optional[str] = None
        self.faults: frozenset = frozenset()
        self.credentials_lost = False
        self.cleanup_errors: List[str] = []

    def secrets(self):
        return self.run.secrets if self.run is not None else set()


def _faults() -> frozenset:
    names = [n.strip() for n in os.environ.get("LIKEUSER_FAULT", "").split(",") if n.strip()]
    unknown = [n for n in names if n not in FAULTS]
    if unknown:
        raise UsageError("unknown_fault", ", ".join(unknown))
    return frozenset(names)


def _project(cwd: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return str(cwd)


def _read_stdin() -> str:
    text = sys.stdin.read()
    return text[:-1] if text.endswith("\n") else text


def _add_secret(run: _run.Run, value: Optional[str], minimum: int = 1) -> None:
    if value and len(value) >= minimum:
        run.secrets.add(value)


def _add_credential(run: _run.Run, field: str, value: Optional[str]) -> None:
    if value:
        run.credentials.add(value)
        run.secrets.add(value)
        if field == "password":
            run.passwords.add(value)


def _prime_credentials(run: _run.Run) -> None:
    """Load the run's credentials into its redaction set.

    A run that began with credentials raises `MissingError` when they cannot be reloaded, because
    continuing would leave them unredacted. A run that began without any redacts the default
    `LIKEUSER_*` variables when they are set, and is otherwise unaffected.
    """
    source = run.data.get("credentials")
    try:
        creds = _run.load_credentials((source or {}).get("prefix"),
                                      Path(source["file"]) if source and source.get("file") else None)
    except MissingError:
        if source:
            raise
        return
    for field, value in creds.items():
        _add_credential(run, field, value)


def _load(ctx: Ctx, run_id: str, allow_ended: bool = False,
          tolerate_lost_credentials: bool = False) -> _run.Run:
    """Load a run and prime its redaction sets.

    With `tolerate_lost_credentials`, a credential source that cannot be reloaded sets
    `ctx.credentials_lost` instead of raising, for the verb that must still release the desktop.
    """
    ctx.root = _run.state_root(Path.cwd())
    run = _run.Run.load(ctx.root, run_id)
    ctx.run = run
    try:
        _prime_credentials(run)
    except MissingError:
        if not tolerate_lost_credentials:
            raise
        ctx.credentials_lost = True
    for value in _run.recall_typed(ctx.root, run_id):
        _add_secret(run, value)
    if run.data.get("ended") and not allow_ended:
        raise RunStateError("run_ended", run_id)
    return run


def _require_active(run: _run.Run) -> None:
    if run.data["paused"]:
        raise RunStateError("run_paused", "resume the run first")
    if run.data["stopped_reason"]:
        raise RunStateError("run_stopped", run.data["stopped_reason"],
                            {"stopped_reason": run.data["stopped_reason"]})


class Drivers:
    """The web and native drivers a run is bound to, constructed on first use."""

    def __init__(self, run: _run.Run) -> None:
        self.run = run
        self._web: Optional[WebDriver] = None
        self._native: Optional[NativeDriver] = None

    @property
    def web(self) -> WebDriver:
        if self._web is None:
            session = self.run.data["window"]["session"] or self.run.data["run_id"]
            self._web = WebDriver(session, self.run.dir)
        return self._web

    @property
    def native(self) -> NativeDriver:
        """The adapter the run began with, restored by name so a later verb never switches adapters.

        Raises `MissingError` when that adapter is no longer ready.
        """
        if self._native is None:
            driver = get_native_driver(name=_native_name(self.run), session=self.run.data["run_id"])
            window = self.run.data["window"]
            if window["bundle_id"]:
                driver.bind(window["bundle_id"], window["window_id"], window.get("pid"))
            self._native = driver
        return self._native

    def close_native(self, errors: List[str]) -> None:
        """Release the native driver's per-run state; failures are appended to `errors`.

        A run that never chose a native adapter has nothing to release.
        """
        if _native_name(self.run) is None:
            return
        try:
            self.native.close()
        except DriverError as exc:
            errors.append(f"close native driver: {exc.code}")
        except MissingError as exc:
            errors.append(f"close native driver: {', '.join(exc.missing)}")

    @property
    def uses_web(self) -> bool:
        return self.run.data["surface"] in ("web", "electron")


def _native_name(run: _run.Run) -> Optional[str]:
    """The native adapter recorded for `run`, or None before one was chosen.

    Runs written before the name had its own field carry it as the tail of the `driver` label.
    """
    name = run.data["window"].get("native_driver") or str(run.data.get("driver") or "").rsplit("+", 1)[-1]
    return name if name in NATIVE_DRIVER_PREFERENCE else None


def _copy_shot(source: Optional[Path], dest: Path) -> Optional[Path]:
    """Move a native driver's screenshot into the run folder; return `dest`, or None when it could not be saved.

    The driver's own copy is deleted whether or not the copy worked, so no UI image stays
    outside the run folder's private mode.
    """
    if source is None:
        return None
    try:
        shutil.copyfile(str(source), str(dest))
        os.chmod(str(dest), _run.PRIVATE_FILE_MODE)
    except OSError:
        return None
    finally:
        with contextlib.suppress(OSError):
            source.unlink()
    return dest


def _observe_native(drivers: Drivers, shot: Optional[Path]) -> Observation:
    window = drivers.run.data["window"]
    obs = drivers.native.observe(window["bundle_id"], window["window_id"], shot is not None)
    if window["window_id"] is None and obs.window_id is not None:
        window["window_id"] = obs.window_id
    return obs


def _shows_password(run: _run.Run, snap: Snap) -> bool:
    """True when the run's password is readable in the snapshot's tree text or values.

    The username is not checked: apps show the signed-in name after login. The check reads
    accessibility text, so a password drawn on screen without appearing in the tree is not caught.
    """
    texts = []
    for obs in (snap.renderer, snap.native):
        if obs is not None:
            texts.append(obs.tree_text)
            texts.extend(obs.values.values())
    return any(c in t for c in run.passwords for t in texts)


def _observe(run: _run.Run, drivers: Drivers, shot: Optional[Path]) -> Snap:
    """Observe the bound surface; with `shot`, also save a screenshot there.

    A screenshot cannot be redacted, so one taken while the password is readable in the tree is
    deleted and the snapshot is marked `screenshot_withheld`.
    """
    snap = _observe_surface(run, drivers, shot)
    if shot is None or not run.passwords or not _shows_password(run, snap):
        return snap
    with contextlib.suppress(OSError):
        shot.unlink()
    return snap._replace(screenshot=None, source=None, scale=None, screenshot_withheld=True)


def _observe_surface(run: _run.Run, drivers: Drivers, shot: Optional[Path]) -> Snap:
    """Observe the surface once.

    Electron runs read the renderer and the native tree; the native tree joins the result only
    while a sheet or dialog is open, and then the screenshot comes from the native side. A native
    observation that fails raises, because a failure does not show that no sheet is open.
    """
    surface = run.data["surface"]
    if surface == "web":
        obs = drivers.web.observe(shot)
        return Snap(obs, None, False, "renderer" if shot else None, shot,
                    obs.scale if shot else None)
    if surface == "native":
        obs = _observe_native(drivers, shot)
        saved = _copy_shot(obs.screenshot_path, shot) if shot else None
        return Snap(None, obs, False, "native" if saved else None, saved,
                    obs.scale if saved else None)
    native = _observe_native(drivers, None)
    if not native.sheet_open:
        renderer = drivers.web.observe(shot)
        return Snap(renderer, None, False, "renderer" if shot else None, shot,
                    renderer.scale if shot else None)
    renderer = drivers.web.observe(None)
    saved = None
    error: Optional[str] = None
    if shot is not None:
        try:
            native = _observe_native(drivers, shot)
            saved = _copy_shot(native.screenshot_path, shot)
        except DriverError as exc:
            error = exc.code
    return Snap(renderer, native, True, "native" if saved else None, saved,
                native.scale if saved else None, error)


def _merged(run: _run.Run, snap: Snap) -> Tuple[List[str], Dict[str, str], Dict[str, str]]:
    refs: List[str] = []
    names: Dict[str, str] = {}
    values: Dict[str, str] = {}
    if snap.renderer is not None:
        refs += snap.renderer.refs
        names.update(snap.renderer.names)
        values.update(snap.renderer.values)
    if snap.native is not None and (run.data["surface"] == "native" or snap.sheet):
        prefix = NATIVE_PREFIX if run.data["surface"] == "electron" else ""
        refs += [prefix + r for r in snap.native.refs]
        names.update({prefix + k: v for k, v in snap.native.names.items()})
        values.update({prefix + k: v for k, v in snap.native.values.items()})
    return refs, names, values


def _primary(snap: Snap) -> Observation:
    return snap.renderer if snap.renderer is not None else snap.native


def _stable(ref: str) -> str:
    """`ref` reduced to what survives re-observation, keeping the Electron native prefix."""
    if ref.startswith(NATIVE_PREFIX):
        return NATIVE_PREFIX + stable_ref(ref[len(NATIVE_PREFIX):])
    return stable_ref(ref)


def _signals(run: _run.Run, snap: Snap, value_ref: Optional[str] = None,
             screen_hash: Optional[int] = None) -> _effects.Signals:
    """Digest the observable signals of `snap`.

    `value_ref` is the ref, in `snap`, of the element whose value is compared; the focus
    signal follows the focused element's stable identity, so a renewed token is not a change.
    """
    primary = _primary(snap)
    parts = []
    if snap.renderer is not None:
        parts.append(_effects.normalize_tree(snap.renderer.tree_text))
    if snap.native is not None and (snap.renderer is None or snap.sheet):
        parts.append(_effects.normalize_tree(snap.native.tree_text))
    focus = _focus_ref(run, snap)
    _, _, values = _merged(run, snap)
    return _effects.Signals(
        url=_digest(primary.url), title=_digest(primary.title),
        tree=_digest("\n--native--\n".join(parts)),
        focus=_digest(_stable(focus) if focus else focus),
        value=_digest(values.get(value_ref)) if value_ref else None, screen_hash=screen_hash)


_ROLE_REF_RE = re.compile(r'^\s*-\s+([^\s":\[]+)[^\n]*?\[ref=([^\]]+)\]')


def _renderer_roles(snap: Snap) -> Dict[str, str]:
    """The role of each renderer ref in `snap`, read from the accessibility tree text."""
    if snap.renderer is None:
        return {}
    roles: Dict[str, str] = {}
    for line in snap.renderer.tree_text.splitlines():
        match = _ROLE_REF_RE.match(line)
        if match:
            roles[match.group(2)] = match.group(1)
    return roles


def _role_group(refs: List[str], names: Dict[str, str], roles: Dict[str, str], role: str,
                name: Optional[str]) -> List[str]:
    return [r for r in refs if roles.get(r) == role and _digest(names.get(r)) == name]


def _element_keys(refs: List[str], names: Dict[str, str],
                  roles: Optional[Dict[str, str]] = None) -> Dict[str, list]:
    """Per ref, what identifies its element again after a re-observation.

    Each entry is `[stable ref, name digest]`, plus `[role, ordinal, group size]` for a renderer
    element, where the group is every element with that role and name, in tree order.
    """
    roles = roles or {}
    keys: Dict[str, list] = {}
    for ref in refs:
        key: list = [_stable(ref), _digest(names.get(ref))]
        role = roles.get(ref)
        if role:
            group = _role_group(refs, names, roles, role, key[1])
            key += [role, group.index(ref), len(group)]
        keys[ref] = key
    return keys


def _correlate(run: _run.Run, snap: Snap, ref: str, element: Optional[list]) -> Optional[str]:
    """Return the ref in `snap` of the element `ref` named before the action, or None when it is gone.

    A ref still present is the same element. A renewed native token is found by its stable
    identity and name, then by a name only one element carries. A renewed renderer ref is found
    among the elements with the same role and name: the one that holds the same position when
    the group is the same size, never a guess when the group changed.
    """
    refs, names, _ = _merged(run, snap)
    if ref in refs:
        return ref
    if not element:
        return None
    key, name = element[0], element[1]
    if key != ref:
        same = [r for r in refs if _stable(r) == key and _digest(names.get(r)) == name]
        if same:
            return same[0]
        named = [r for r in refs if _stable(r) != r and _digest(names.get(r)) == name]
        if len(named) == 1:
            return named[0]
    if len(element) < 5:
        return None
    role, ordinal, size = element[2:5]
    group = _role_group(refs, names, _renderer_roles(snap), role, name)
    return group[ordinal] if len(group) == size else None


def _screen_hash(path: Optional[Path]) -> Optional[int]:
    if path is None:
        return None
    try:
        return _effects.average_hash(path)
    except (ValueError, OSError):
        return None


def _focus_ref(run: _run.Run, snap: Snap) -> Optional[str]:
    if snap.sheet and snap.native is not None and snap.native.focus is not None:
        return NATIVE_PREFIX + snap.native.focus
    primary = _primary(snap)
    return primary.focus


def _record_observation(run: _run.Run, oid: int, goal_id: Optional[str], snap: Snap,
                        screen_hash: Optional[int]) -> dict:
    """Persist an observation's trees, sidecar, and run.json entry; return its output block."""
    refs, names, values = _merged(run, snap)
    primary = _primary(snap)
    tree_text = _run.redact(primary.tree_text, run.secrets)
    tree_path = run.dir / f"obs-{oid}.tree.txt"
    _write_text(tree_path, tree_text)
    native_tree_path = None
    if snap.renderer is not None and snap.sheet and snap.native is not None:
        native_tree_path = run.dir / f"obs-{oid}.native.tree.txt"
        _write_text(native_tree_path, _run.redact(snap.native.tree_text, run.secrets))
    truncated = any(o.tree_truncated for o in (snap.renderer, snap.native) if o is not None)
    sparse = bool(_primary(snap).tree_sparse)
    signals = _signals(run, snap, None, screen_hash)
    sidecar = {
        "id": oid, "goal_id": goal_id, "sheet": snap.sheet, "surface": run.data["surface"],
        "focus_ref": _focus_ref(run, snap),
        "screenshot_source": snap.source, "scale": snap.scale,
        "refs": refs, "names": _scrub(names, run.secrets),
        "value_digests": {k: _digest(v) for k, v in values.items()},
        "elements": _element_keys(refs, names, _renderer_roles(snap)),
        "signals": {"url": signals.url, "title": signals.title, "tree": signals.tree,
                    "focus": signals.focus, "screen_hash": screen_hash},
    }
    _write_text(run.dir / f"obs-{oid}.json", json.dumps(sidecar, sort_keys=True))
    shot = str(snap.screenshot) if snap.screenshot else None
    run.data["observations"][str(oid)] = {
        "goal_id": goal_id, "screenshot_path": shot, "screenshot_source": snap.source,
        "scale": snap.scale, "tree_path": str(tree_path), "url": primary.url,
        "title": primary.title, "focus": primary.focus,
        "driver": run.data["driver"],
    }
    run.data["latest_observation_id"] = oid
    block = {
        "observation_id": oid, "goal_id": goal_id, "screenshot_path": shot,
        "screenshot_source": snap.source, "scale": snap.scale, "tree_path": str(tree_path),
        "tree_chars": len(primary.tree_text), "tree_truncated": truncated,
        "tree_sparse": sparse, "url": primary.url, "title": primary.title,
        "focus": primary.focus, "console_errors_new": [], "network_failures_new": [],
        "screenshot_withheld": snap.screenshot_withheld,
    }
    if native_tree_path is not None:
        block["native_tree_path"] = str(native_tree_path)
    if snap.native_error:
        block["native_error"] = snap.native_error
    return block


def _sidecar(run: _run.Run, oid: int) -> Optional[dict]:
    try:
        return json.loads((run.dir / f"obs-{oid}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _add_evidence(run: _run.Run, goal_id: Optional[str], path: Optional[str]) -> None:
    if not goal_id or not path:
        return
    evidence = run.data["goals"][goal_id]["evidence"]
    if path not in evidence:
        evidence.append(path)


def _auto_findings(run: _run.Run, drivers: Drivers, ctx: Ctx, goal_id: Optional[str],
                   shot: Optional[str]) -> Tuple[List[str], List[dict], List[str]]:
    """Register console errors and failed requests not yet seen; return (messages, requests, finding ids)."""
    if not drivers.uses_web:
        return [], [], []
    added: List[str] = []
    errors = drivers.web.console_errors()
    if len(errors) < run.data["console_seen"]:
        run.data["console_seen"] = 0
    fresh_console = errors[run.data["console_seen"]:]
    run.data["console_seen"] = len(errors)
    for message in fresh_console:
        added.append(run.add_finding("console", f"console error: {message}", goal_id, shot, "script"))
    fresh_requests: List[dict] = []
    if "drop_network" not in ctx.faults:
        failed = drivers.web.failed_requests()
        if len(failed) < run.data["requests_seen"]:
            run.data["requests_seen"] = 0
        fresh_requests = failed[run.data["requests_seen"]:]
        run.data["requests_seen"] = len(failed)
        for req in fresh_requests:
            outcome = "no response" if req["status"] is None else str(req["status"])
            added.append(run.add_finding(
                "network", f"failed request: {req['method']} {req['url']} -> {outcome}",
                goal_id, shot, "script"))
    if added:
        _add_evidence(run, goal_id, shot)
    return fresh_console, fresh_requests, added


def _drift_now() -> Optional[dict]:
    try:
        x, y = _desktop.cursor()
        return {"frontmost": _desktop.frontmost_bundle_id(), "cursor": [x, y]}
    except DriverError:
        return None


def _surface_report(surface: str) -> Tuple[dict, List[str]]:
    tools: List[dict] = []
    missing: List[str] = []
    if surface in ("web", "electron"):
        override = os.environ.get("LIKEUSER_PLAYWRIGHT_BIN")
        found = override or shutil.which("playwright-cli")
        driver = WebDriver("doctor", Path.cwd())
        gaps = driver.check()
        version = None
        if not gaps:
            version = driver.version()
        tools.append({"name": "playwright-cli", "path": found, "version": version,
                      "pin": PIN_TEXT})
        missing += gaps
    permissions: Dict[str, bool] = {}
    if surface in ("electron", "native"):
        try:
            tool = get_native_driver()
            tools.append({"name": tool.name, "path": tool.path, "version": tool.version or None,
                          "pin": tool.pin})
        except MissingError as exc:
            missing += exc.missing
        try:
            permissions = _desktop.permissions()
        except DriverError as exc:
            missing.append(f"macos ({exc.code})")
        else:
            if not permissions.get("accessibility"):
                missing.append("macOS permission: Accessibility")
            if not permissions.get("screen_recording"):
                missing.append("macOS permission: Screen Recording")
    return {"ready": not missing, "tools": tools, "permissions": permissions,
            "missing": missing}, missing


def cmd_doctor(args, ctx: Ctx):
    """Report tools, pins, and macOS permissions per surface; exit 5 naming what is missing."""
    surfaces = [args.surface] if args.surface else list(SURFACES)
    report: Dict[str, dict] = {}
    missing: List[str] = []
    for surface in surfaces:
        info, gaps = _surface_report(surface)
        report[surface] = info
        missing += [g for g in gaps if g not in missing]
    out = {"ok": not missing, "surfaces": report, "missing": missing}
    return out, (5 if missing else 0)


def _free_port() -> int:
    for port in CDP_PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise DriverError("no_free_port", "no free CDP port in 9222-9299")


@contextlib.contextmanager
def _cdp_port_lock():
    """Serialize CDP port choice and app launch across every likeuser process on this machine.

    The probe in `_free_port` releases its socket before the app binds, so two runs probing
    concurrently would pick the same port. Holding this lock from the probe until the app
    answers on its port makes each choice visible to the next run's probe.
    """
    path = _run.DesktopLock().path.with_name(CDP_LOCK_NAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _listener_pids(port: int) -> Optional[set]:
    """Return the pids listening on loopback `port`, or None when `lsof` cannot say."""
    lsof = shutil.which("lsof")
    if lsof is None:
        return None
    try:
        out = subprocess.run([lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return {int(token) for token in out.stdout.split() if token.isdigit()}


def _verify_cdp_owner(port: int, proc: subprocess.Popen) -> Optional[int]:
    """Refuse to attach when something other than the launched app (or its children) holds `port`.

    The app starts in its own session, so its process group id is its pid. Returns the pid of the
    listener that belongs to the launched app: `proc` itself, or the Electron child a wrapper
    command started. Returns None when the port's listeners cannot be identified, which is accepted.
    """
    listeners = _listener_pids(port)
    if not listeners:
        return None
    for pid in sorted(listeners):
        try:
            if pid == proc.pid or os.getpgid(pid) == proc.pid:
                return pid
        except ProcessLookupError:
            continue
    raise DriverError("cdp_port_conflict",
                      f"port {port} is answered by another process, not the launched app")


def _wait_for_cdp(port: int, proc: subprocess.Popen) -> None:
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.monotonic() + LAUNCH_WAIT_S
    while True:
        if proc.poll() is not None:
            raise DriverError("launch_failed", f"launched app exited with code {proc.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise DriverError("launch_timeout", f"{url} did not answer within {int(LAUNCH_WAIT_S)}s")
        time.sleep(0.2)


def _bundle_for_pid(pid: int) -> Optional[str]:
    """The bundle id LaunchServices registers for `pid`, waiting briefly for a new process; None when it has none."""
    deadline = time.monotonic() + PID_BUNDLE_WAIT_S
    while True:
        found = _desktop.bundle_id_for_pid(pid)
        if found:
            return found
        if os.environ.get("LIKEUSER_FAKE_DESKTOP") or time.monotonic() >= deadline:
            return None
        time.sleep(0.25)


def _find_window(driver: NativeDriver, bundle_id: str, wait_s: float) -> Optional[int]:
    finder = getattr(driver, "find_window", None)
    if finder is None:
        return None
    deadline = time.monotonic() + wait_s
    while True:
        try:
            found = finder(bundle_id)
        except DriverError as exc:
            if exc.code != "app_not_found" or time.monotonic() >= deadline:
                raise
            found = None
        if found is not None or time.monotonic() >= deadline:
            return found
        time.sleep(0.5)


def _looks_like_bundle_id(target: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", target))


def _native_running(driver: NativeDriver, target: str) -> bool:
    finder = getattr(driver, "find_window", None)
    if finder is None:
        return True
    try:
        finder(target)
    except DriverError as exc:
        if exc.code == "app_not_found":
            return False
        raise
    return True


def _launch_native_app(target: str) -> Dict[str, str]:
    flag = "-b" if _looks_like_bundle_id(target) else "-a"
    try:
        proc = subprocess.run(["open", flag, target], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise DriverError("launch_failed", f"open {flag} {target}: {exc}")
    if proc.returncode != 0:
        raise DriverError("launch_failed", f"open {flag} {target}: {proc.stderr.strip()}")
    return {"kind": "app", "id": ("bundle:" if flag == "-b" else "name:") + target}


def _read_goals_file(path: Optional[str]) -> List[Tuple[str, str]]:
    if not path:
        return []
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        goals = [(str(g["id"]), str(g["title"])) for g in doc]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise UsageError("bad_goals_file", f"{path}: {exc}")
    for goal_id, _ in goals:
        if not GOAL_ID_RE.match(goal_id):
            raise UsageError("bad_goal_id", goal_id)
    if len({g for g, _ in goals}) != len(goals):
        raise UsageError("duplicate_goal", "goals file repeats an id")
    return goals


def _native_is_background_capable() -> bool:
    """Whether the native driver `begin` would bind can act without taking the foreground.

    A missing driver reads as capable so `begin` reports the missing tool, not a flag error.
    """
    try:
        return bool(get_native_driver().background_capable)
    except MissingError:
        return True


def _needs_lock_at_begin(surface: str) -> bool:
    """Whether a run on `surface` holds the foreground for every native action from its first moment.

    Only a native driver that is not background-capable does; a background-capable run takes the
    lock on its first `--foreground` act instead.
    """
    return surface in ("native", "electron") and not _native_is_background_capable()


def _validate_begin(args) -> List[Tuple[str, str]]:
    if args.surface == "electron" and not args.launch:
        raise UsageError("launch_required",
                         "--surface electron needs --launch; running Electron apps use --surface native")
    if args.launch and args.surface != "electron":
        raise UsageError("launch_requires_electron", "--launch is for --surface electron")
    if args.launch_env and args.surface != "electron":
        raise UsageError("launch_requires_electron", "--launch-env is for --surface electron")
    if args.real_chrome and args.surface != "web":
        raise UsageError("real_chrome_requires_web", "--real-chrome is for --surface web")
    if args.cdp_port is not None and args.surface != "electron":
        raise UsageError("cdp_port_requires_electron", "--cdp-port is for --surface electron")
    if args.session_key is not None:
        if args.surface == "native":
            raise UsageError("session_key_unsupported", "native apps have no storage state")
        if not SESSION_KEY_RE.match(args.session_key):
            raise UsageError("bad_session_key", args.session_key)
    if args.surface in ("native", "electron") and not args.allow_foreground \
            and not _native_is_background_capable():
        raise UsageError("foreground_not_allowed",
                         "this run's native driver takes the foreground for every native action; "
                         "pass --allow-foreground")
    for name in ("budget_run", "budget_goal"):
        value = getattr(args, name)
        if value is not None and value < 1:
            raise UsageError("bad_budget", f"--{name.replace('_', '-')} must be at least 1")
    return _read_goals_file(args.goals_file)


def cmd_begin(args, ctx: Ctx):
    """Open a run: check the surface, take the lock if needed, record the baseline, bind a driver."""
    goals = _validate_begin(args)
    surface = args.surface
    gaps = _surface_report(surface)[1]
    if gaps:
        raise MissingError(gaps)
    credentials = None
    secret_values: List[str] = []
    if args.credentials_file or args.credentials_env:
        loaded = _run.load_credentials(
            args.credentials_env, Path(args.credentials_file) if args.credentials_file else None)
        secret_values = list(loaded.values())
        credentials = {"prefix": args.credentials_env,
                       "file": str(Path(args.credentials_file).resolve())
                       if args.credentials_file else None}
    _refuse_credential_launch_env(args.launch_env, args.credentials_env, secret_values)

    cwd = Path.cwd()
    root = _run.state_root(cwd)
    ctx.root = root
    project = _project(cwd)
    run_id = _run.new_run_id()
    lock = _run.DesktopLock()
    holds_lock = False
    if _needs_lock_at_begin(surface):
        lock.acquire(run_id, project, wait_s=LOCK_WAIT_S)
        holds_lock = True
    takeover = lock.replaced

    overrides = _run.test_overrides(os.environ)
    fields = {
        "run_id": run_id, "target": args.target, "surface": surface, "owner": args.owner,
        "attended": bool(args.attended), "allow_foreground": bool(args.allow_foreground),
        "holds_lock": holds_lock, "test_overrides": overrides, "credentials": credentials,
        "session_key": args.session_key, "real_chrome": bool(args.real_chrome),
        "launch_env": list(dict.fromkeys(args.launch_env)), "started": _now(),
        "budget": {"run_cap": args.budget_run or _run.DEFAULT_RUN_CAP,
                   "goal_cap": args.budget_goal or _run.DEFAULT_GOAL_CAP},
        "window": {"bundle_id": None, "window_id": None, "session": None, "cdp_port": None,
                   "native_driver": None, "pid": None},
    }
    try:
        run = _run.Run.create(root, fields)
    except BaseException:
        if holds_lock:
            lock.release(run_id)
        raise
    ctx.run = run
    for value in secret_values:
        _add_secret(run, value)
    if overrides:
        sys.stderr.write(_run.OVERRIDE_BANNER + "\n")
    if takeover:
        run.event("lock_takeover", {"replaced": takeover}, "ok", 0)

    try:
        _begin_bind(args, run, ctx)
        for goal_id, title in goals:
            run.add_goal(goal_id, title)
    except BaseException:
        _abort_begin(run, lock, ctx)
        raise
    run.save()
    return {
        "ok": True, "run_id": run_id, "run_dir": str(run.dir), "surface": surface,
        "owner": args.owner, "attended": bool(args.attended), "driver": run.data["driver"],
        "driver_version": run.data["driver_version"], "window": run.data["window"],
        "baseline": run.data["baseline"], "holds_lock": run.data["holds_lock"],
        "goals": [g for g, _ in goals], "budget": run.data["budget"],
        "test_overrides": overrides, "session_loaded": bool(run.data.get("session_loaded")),
    }


def _abort_begin(run: _run.Run, lock: _run.DesktopLock, ctx: Ctx) -> None:
    """Undo what a failed `begin` left behind, putting the desktop back as `end` would.

    Closes the browser session and any launched app, releases the native driver state, deletes the
    clipboard copy, and restores the frontmost app. A clean abort releases the lock and ends the
    run. When a step fails, the errors go to `ctx.cleanup_errors` and `begin_cleanup_errors`, the
    lock stays held, and the run stays open (stopped as `begin_failed`) so a cleanup-only `end`
    can retry the steps that failed.
    """
    errors: List[str] = []
    drivers = Drivers(run)
    if run.data["window"]["session"] is not None:
        _close_everything(run, drivers, errors)
    else:
        _terminate_launched(run, errors)
    drivers.close_native(errors)
    try:
        (run.dir / "clipboard.txt").unlink()
    except OSError:
        pass
    _restore_frontmost(run, errors)
    run.data["stopped_reason"] = "begin_failed"
    if errors:
        run.data["begin_cleanup_errors"] = errors
        ctx.cleanup_errors = errors
    else:
        if run.data["holds_lock"]:
            lock.release(run.data["run_id"])
            run.data["holds_lock"] = False
        run.data["ended"] = _now()
    run.save()


def _begin_bind(args, run: _run.Run, ctx: Ctx) -> None:
    surface = args.surface
    base = {
        "frontmost": _desktop.frontmost_bundle_id(),
        "cursor": list(_desktop.cursor()),
        "clipboard_change_count": _desktop.clipboard_change_count(),
        "clipboard_text_only": _desktop.clipboard_is_text_only(),
    }
    run.data["baseline"] = base
    if base["clipboard_text_only"]:
        clip = run.dir / "clipboard.txt"
        _write_text(clip, _desktop.clipboard_read_text(), 0o600)
    window = run.data["window"]
    drivers = Drivers(run)
    versions: List[str] = []
    if surface in ("web", "electron"):
        window["session"] = run.data["run_id"]
        run.data["driver"] = "playwright-cli"
        versions.append(drivers.web.version())
    if surface == "web":
        _begin_web(args, run, drivers)
    elif surface == "electron":
        _begin_electron(args, run, drivers)
    if surface in ("electron", "native"):
        native = _begin_native(args, run, drivers)
        run.data["driver"] = native.name if surface == "native" else f"playwright-cli+{native.name}"
        versions.append(native.version)
    run.data["driver_version"] = " + ".join(v for v in versions if v)
    current = _drift_now()
    run.data["drift_baseline"] = current or {"frontmost": base["frontmost"], "cursor": base["cursor"]}
    run.save()


def _session_file(run: _run.Run, key: str) -> Path:
    return run.dir.parents[1] / "sessions" / f"{key}.json"


def _begin_web(args, run: _run.Run, drivers: Drivers) -> None:
    web = drivers.web
    if args.real_chrome:
        try:
            web.attach_extension()
        except DriverError as exc:
            if exc.code == "extension_unavailable":
                raise MissingError(["chrome extension (playwright-cli attach --extension=chrome)"])
            raise
        return
    saved = _session_file(run, args.session_key) if args.session_key else None
    if saved is not None and saved.is_file():
        web.open("about:blank")
        web.state_load(saved)
        web.goto(args.target)
        run.data["session_loaded"] = True
    else:
        web.open(args.target)


def _sensitive_env_name(name: str) -> bool:
    """True when an environment variable's name looks like it holds a secret or host credential."""
    return SENSITIVE_ENV_NAME.search(name) is not None


def _credential_env_names(prefix: Optional[str]) -> set:
    return {f"{name}_{field}" for name in (prefix or DEFAULT_CREDENTIALS_PREFIX,
                                           DEFAULT_CREDENTIALS_PREFIX)
            for field in ("USERNAME", "PASSWORD")}


def _refuse_credential_launch_env(names: List[str], prefix: Optional[str],
                                  secret_values: List[str]) -> None:
    """Refuse a `--launch-env` name that is a credential variable or holds a known secret."""
    named = _credential_env_names(prefix)
    for name in names:
        if name in named or (os.environ.get(name) or None) in secret_values:
            raise UsageError("launch_env_credential",
                             f"--launch-env cannot pass the run's credentials to the app: {name}")


def _launch_env(run: _run.Run) -> Dict[str, str]:
    """The environment a launched app inherits: this process's, minus secrets.

    Drops the run's credential variables, any variable whose value is a known secret, and every
    variable whose name looks sensitive unless `begin --launch-env` named it. A named variable
    still never carries a credential.
    """
    named = _credential_env_names((run.data.get("credentials") or {}).get("prefix"))
    allowed = set(run.data.get("launch_env") or [])
    secrets = {value for value in run.secrets if value}
    return {k: v for k, v in os.environ.items()
            if k not in named and v not in secrets
            and (k in allowed or not _sensitive_env_name(k))}


def _open_private_log(path: Path):
    """Open `path` for writing as a fresh file readable only by the owner, whatever the umask."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        return os.fdopen(fd, "wb")
    except BaseException:
        os.close(fd)
        raise


def _begin_electron(args, run: _run.Run, drivers: Drivers) -> None:
    with _cdp_port_lock():
        port = args.cdp_port or _free_port()
        run.data["window"]["cdp_port"] = port
        proc = _spawn_app(args, run, port)
        _wait_for_cdp(port, proc)
        owner = _verify_cdp_owner(port, proc)
    drivers.web.attach_cdp(f"http://127.0.0.1:{port}")
    saved = _session_file(run, args.session_key) if args.session_key else None
    if saved is not None and saved.is_file():
        drivers.web.state_load(saved)
        run.data["session_loaded"] = True
    pid = owner or proc.pid
    run.data["window"]["pid"] = pid
    run.data["window"]["bundle_id"] = _bundle_for_pid(pid) or f"pid:{pid}"


def _spawn_app(args, run: _run.Run, port: int) -> subprocess.Popen:
    command = shlex.split(args.launch) + [f"--remote-debugging-port={port}"]
    out = err = None
    try:
        out = _open_private_log(run.dir / "launch.stdout.log")
        err = _open_private_log(run.dir / "launch.stderr.log")
        proc = subprocess.Popen(command, stdout=out, stderr=err, stdin=subprocess.DEVNULL,
                                start_new_session=True, env=_launch_env(run))
    except OSError as exc:
        raise DriverError("launch_failed", f"{command[0]}: {exc}")
    finally:
        for handle in (out, err):
            if handle is not None:
                handle.close()
    run.data["launched"].append({"kind": "app", "id": f"pid:{proc.pid}"})
    run.save()
    return proc


def _begin_native(args, run: _run.Run, drivers: Drivers) -> NativeDriver:
    window = run.data["window"]
    if args.surface == "native":
        window["bundle_id"] = args.target
    driver = drivers.native
    window["native_driver"] = driver.name
    if args.surface == "native" and not _native_running(driver, args.target):
        run.data["launched"].append(_launch_native_app(args.target))
        run.save()
    bundle = window["bundle_id"]
    driver.bind(bundle, None, window.get("pid"))
    window["window_id"] = _find_window(driver, bundle, WINDOW_WAIT_S)
    driver.bind(bundle, window["window_id"], window.get("pid"))
    return driver


def cmd_goal(args, ctx: Ctx):
    """Register a goal whose title is read from stdin."""
    run = _load(ctx, args.run)
    if not GOAL_ID_RE.match(args.id):
        raise UsageError("bad_goal_id", args.id)
    title = _read_stdin().strip()
    if not title:
        raise UsageError("empty_title", "the goal title on stdin is empty")
    ctx.inputs = {"id": args.id, "title_chars": len(title)}
    run.add_goal(args.id, title)
    return {"ok": True, "goal_id": args.id}


def _known_goal(run: _run.Run, goal_id: str) -> None:
    if goal_id not in run.data["goals"]:
        raise UsageError("unknown_goal", goal_id)


def cmd_observe(args, ctx: Ctx):
    """Capture the surface's tree and screenshot for a goal and record any new console or network findings."""
    run = _load(ctx, args.run)
    _require_active(run)
    _known_goal(run, args.goal)
    drivers = Drivers(run)
    oid = run.data["latest_observation_id"] + 1
    shot = None if args.no_screenshot else run.dir / f"obs-{oid}.png"
    snap = _observe(run, drivers, shot)
    block = _record_observation(run, oid, args.goal, snap, _screen_hash(snap.screenshot))
    console_new, requests_new, added = _auto_findings(run, drivers, ctx, args.goal,
                                                      block["screenshot_path"])
    block["console_errors_new"] = console_new
    block["network_failures_new"] = requests_new
    return {"ok": True, "observation": block, "findings_added": added}


class ActRequest(NamedTuple):
    """A validated `act` invocation: the action, its target, and the guard options."""

    kind: str
    ref: Optional[str]
    x: Optional[float]
    y: Optional[float]
    to_ref: Optional[str]
    to_x: Optional[float]
    to_y: Optional[float]
    text: Optional[str]
    secret: Optional[str]
    key: Optional[str]
    value: Optional[str]
    direction: Optional[str]
    amount: Optional[float]
    expect: str
    gate: str
    foreground: bool
    target_name: Optional[str]

    @property
    def has_point(self) -> bool:
        return self.x is not None and self.y is not None

    @property
    def uses_coordinates(self) -> bool:
        """True when the start or the drag destination is given as screenshot pixels."""
        return self.has_point or (self.to_x is not None and self.to_y is not None)


def _parse_act(args) -> ActRequest:
    """Validate the action's target and arguments and read typed text from stdin."""
    kind = args.action
    if args.secret and args.text_stdin:
        raise UsageError("text_and_secret", "use --text-stdin or --secret, not both")
    if (args.x is None) != (args.y is None):
        raise UsageError("bad_target", "--x and --y go together")
    if (args.to_x is None) != (args.to_y is None):
        raise UsageError("bad_target", "--to-x and --to-y go together")
    if args.ref and args.x is not None:
        raise UsageError("bad_target", "give --ref or --x/--y, not both")
    needs_text = kind in ("fill", "type")
    if needs_text and not (args.text_stdin or args.secret):
        raise UsageError("text_required", f"{kind} needs --text-stdin or --secret")
    if not needs_text and (args.text_stdin or args.secret):
        raise UsageError("text_unexpected", f"{kind} takes no text")
    has_target = args.ref is not None or args.x is not None
    if kind in POINT_KINDS and not has_target:
        raise UsageError("target_required", f"{kind} needs --ref or --x/--y")
    if kind in ("fill", "select", "dismiss") and not args.ref:
        raise UsageError("target_required", f"{kind} needs --ref")
    if kind == "select" and args.value is None:
        raise UsageError("value_required", "select needs --value")
    if kind in ("press", "hotkey") and not args.key:
        raise UsageError("key_required", f"{kind} needs --key")
    if kind == "scroll" and not args.direction:
        raise UsageError("direction_required", "scroll needs --direction")
    if kind == "drag":
        if not has_target:
            raise UsageError("target_required", "drag needs --ref or --x/--y")
        if not (args.to_ref or args.to_x is not None):
            raise UsageError("target_required", "drag needs --to-ref or --to-x/--to-y")
    text = _read_stdin() if args.text_stdin else None
    return ActRequest(
        kind=kind, ref=args.ref, x=args.x, y=args.y, to_ref=args.to_ref, to_x=args.to_x,
        to_y=args.to_y, text=text, secret=args.secret, key=args.key, value=args.value,
        direction=args.direction, amount=args.amount, expect=args.expect, gate=args.gate,
        foreground=args.foreground, target_name=args.target_name)


def _act_result(run: _run.Run, goal_id: Optional[str], status: str, **extra) -> dict:
    out = {
        "ok": True, "status": status, "signals": [], "other_changes": [],
        "driver_verified": None, "driver_error": None, "findings_added": [],
        "observation": None, "latest_observation_id": run.data["latest_observation_id"],
    }
    out.update(extra)
    if goal_id and goal_id in run.data["goals"]:
        run.data["goals"][goal_id]["last_act_status"] = status
    return out


def _budget_spent(run: _run.Run, goal_id: Optional[str]) -> bool:
    budget = run.data["budget"]
    if budget["run_used"] >= budget["run_cap"]:
        return True
    goal = run.data["goals"].get(goal_id) if goal_id else None
    return bool(goal) and goal["actions_used"] >= budget["goal_cap"]


def _route(run: _run.Run, sidecar: dict, req: ActRequest) -> str:
    surface = run.data["surface"]
    if req.uses_coordinates and sidecar.get("screenshot_source") is None:
        raise UsageError("coordinates_need_screenshot",
                         "--x/--y and --to-x/--to-y are screenshot pixels; observe with a screenshot first")
    routes = set()
    for ref in (req.ref, req.to_ref):
        if ref is not None:
            routes.add("native" if surface == "native" or ref.startswith(NATIVE_PREFIX)
                       else "renderer")
    if len(routes) > 1:
        raise UsageError("mixed_routes", "a drag cannot start in the renderer and end in a native dialog")
    if routes:
        return routes.pop()
    if surface == "web":
        return "renderer"
    if surface == "native":
        return "native"
    if req.uses_coordinates:
        return sidecar["screenshot_source"]
    return "native" if sidecar.get("sheet") else "renderer"


def _bare(ref: Optional[str], run: _run.Run) -> Optional[str]:
    if ref is not None and run.data["surface"] == "electron" and ref.startswith(NATIVE_PREFIX):
        return ref[len(NATIVE_PREFIX):]
    return ref


def _build_action(run: _run.Run, req: ActRequest, scale: Optional[float],
                  text: Optional[str]) -> Action:
    divisor = scale or 1.0

    def px(value: Optional[float]) -> Optional[float]:
        return None if value is None else value / divisor

    return Action(
        kind=req.kind, ref=_bare(req.ref, run), x=px(req.x), y=px(req.y),
        to_ref=_bare(req.to_ref, run), to_x=px(req.to_x), to_y=px(req.to_y), text=text,
        key=req.key, value=req.value, direction=req.direction, amount=req.amount)


def _perform(run: _run.Run, drivers: Drivers, route: str, req: ActRequest, action: Action,
             foreground: bool) -> DriverResult:
    if route == "renderer":
        return drivers.web.act(action)
    baseline = run.data["baseline"]
    long_text = (req.kind == "type" and action.text is not None
                 and len(action.text) > PASTE_MIN_CHARS and baseline["clipboard_text_only"])
    if not long_text:
        return drivers.native.act(action, foreground)
    if action.ref is not None:
        drivers.native.act(Action(kind="click", ref=action.ref), foreground)
    _desktop.clipboard_write_text(action.text)
    run.data["pasted"] = True
    run.data["paste_change_count"] = _desktop.clipboard_change_count()
    run.save()
    return drivers.native.act(Action(kind="hotkey", key=PASTE_HOTKEY), foreground)


def _gate_subjects(req: ActRequest, names: Dict[str, str]) -> List[str]:
    """The names that say what `req` acts on, each of which the gate is checked against.

    A `--ref` target is named by its accessible name, falling back to `--target-name`. A
    `press` or `hotkey` names its effect only through `--target-name`, so that is always a
    subject even when a `--ref` is also given.
    """
    ref_name = names.get(req.ref) if req.ref else None
    if req.kind in ("press", "hotkey"):
        return [s for s in (ref_name, req.target_name) if s]
    return [s for s in (ref_name or req.target_name,) if s]


def cmd_act(args, ctx: Ctx):
    """Run the seven guard checks, perform one action, settle, observe, and classify its effect.

    A driver failure anywhere in here is the `ERROR` status, never an exit code and never `OBSERVED`.
    """
    try:
        return _act(args, ctx)
    except DriverError as exc:
        return _act_result(ctx.run, ctx.goal_id, "ERROR", driver_error=exc.code,
                           driver_message=exc.message)


def _act(args, ctx: Ctx) -> dict:
    run = _load(ctx, args.run)
    if run.data["holds_lock"]:
        _run.DesktopLock().refresh(run.data["run_id"])
    req = _parse_act(args)
    if req.text is not None and len(req.text) >= MIN_REDACT_CHARS:
        _add_secret(run, req.text)
        _run.remember_typed(ctx.root, run.data["run_id"], req.text)
    secret_value: Optional[str] = None
    if req.secret:
        source = run.data.get("credentials") or {}
        creds = _run.load_credentials(source.get("prefix"),
                                      Path(source["file"]) if source.get("file") else None)
        for field, value in creds.items():
            _add_credential(run, field, value)
        secret_value = creds[req.secret]
    ctx.inputs = {
        "action": req.kind, "obs": args.obs, "ref": req.ref, "x": req.x, "y": req.y,
        "to_ref": req.to_ref, "to_x": req.to_x, "to_y": req.to_y, "key": req.key,
        "direction": req.direction, "amount": req.amount, "expect": req.expect,
        "gate": req.gate, "foreground": req.foreground, "target_name": req.target_name,
        "secret": req.secret, "text_chars": None if req.text is None else len(req.text),
    }
    data = run.data
    if data["paused"]:
        raise RunStateError("run_paused", "resume the run first")
    latest = data["latest_observation_id"]
    record = data["observations"].get(str(args.obs)) or data["observations"].get(str(latest))
    goal_id = record["goal_id"] if record else None
    ctx.goal_id = goal_id

    if data["stopped_reason"]:
        return _act_result(run, goal_id, "DRIFT", stopped_reason=data["stopped_reason"],
                           message="the run is stopped; end it and report how far it got")
    if _budget_spent(run, goal_id):
        return _act_result(run, goal_id, "BUDGET_EXHAUSTED")

    sidecar = _sidecar(run, latest) if latest else None
    stale = sidecar is None
    if not stale and "skip_stale" not in ctx.faults:
        stale = args.obs != latest or any(
            r is not None and r not in sidecar["refs"] for r in (req.ref, req.to_ref))
    if stale:
        return _act_result(run, goal_id, "STALE",
                           message="observe again and act on the new observation id")

    surface = data["surface"]
    route = _route(run, sidecar, req)
    drivers = Drivers(run)
    native_fg = route == "native" and not drivers.native.background_capable
    uses_foreground = route == "native" and (native_fg or req.foreground)

    if uses_foreground and "skip_drift" not in ctx.faults:
        drift = _check_drift(run)
        if drift is not None:
            data["stopped_reason"] = "drift"
            return _act_result(run, goal_id, "DRIFT", drift=drift, stopped_reason="drift",
                               message="the cursor or frontmost app changed; the user took over")

    if native_fg and not req.foreground:
        return _act_result(run, goal_id, "FOREGROUND_REQUIRED",
                           message="this action needs the foreground; tell the user, then re-issue with --foreground")
    if req.foreground:
        if not data["attended"] and not data["allow_foreground"]:
            raise UsageError("foreground_not_allowed",
                             "unattended runs need begin --allow-foreground before --foreground")
        lock = _run.DesktopLock()
        holder = lock.try_acquire(data["run_id"], _project(Path.cwd()))
        if holder is not None:
            return _act_result(run, goal_id, "DESKTOP_BUSY", holder=holder)
        if lock.replaced:
            run.event("lock_takeover", {"replaced": lock.replaced}, "ok", 0)
        data["holds_lock"] = True

    names = sidecar["names"]
    if route == "renderer" and drivers.uses_web and "skip_visibility" not in ctx.faults:
        for ref in (req.ref, req.to_ref):
            if ref is None:
                continue
            visible, reason = drivers.web.visibility(ref)
            if not visible:
                shot = record["screenshot_path"] if record else None
                label = names.get(ref) or ref
                finding = run.add_finding(
                    "visibility", f"{label} is in the accessibility tree but not visible ({reason})",
                    goal_id, shot, "script")
                _add_evidence(run, goal_id, shot)
                return _act_result(run, goal_id, "NOT_VISIBLE", findings_added=[finding],
                                   reason=reason)

    needs_name = (req.uses_coordinates or (req.kind in ("press", "hotkey") and data["owner"] == "third-party"))
    if needs_name and not req.target_name:
        raise UsageError("target_name_required",
                         "coordinate, press, and hotkey actions name what they hit with --target-name")
    subjects = _gate_subjects(req, names)
    gated = next((s for s in subjects if _run.gate_matches(s, data["owner"])), None)
    subject = gated or (subjects[0] if subjects else "")
    if gated and "skip_gate" not in ctx.faults:
        if req.gate == "none":
            run.record_gate(args.obs, subject, "stopped")
            _add_evidence(run, goal_id, record["screenshot_path"] if record else None)
            return _act_result(run, goal_id, "GATE_REQUIRED", subject=subject)
        if req.gate == "approved" and not data["attended"]:
            raise UsageError("unattended_approval",
                             "unattended runs cannot take user approval; report the goal blocked")
        if req.gate == "created" and data["owner"] != "yours":
            raise UsageError("created_third_party",
                             "--gate created is only for data this run created in the user's own app")
        run.record_gate(args.obs, subject, req.gate)

    if req.kind == "dismiss" and not _run.dismiss_allowed(subject):
        return _act_result(run, goal_id, "NOT_ALLOWLISTED", subject=subject)

    if req.secret and data["login_attempts"] >= 1:
        return _act_result(run, goal_id, "ERROR", driver_error="login_attempt_limit",
                           message="a login attempt already failed; hand off or report blocked")

    return _act_perform(args, ctx, run, drivers, req, sidecar, goal_id, route, uses_foreground,
                        secret_value)


def _check_drift(run: _run.Run) -> Optional[dict]:
    base = run.data["drift_baseline"]
    x, y = _desktop.cursor()
    now = {"frontmost": _desktop.frontmost_bundle_id(), "cursor": [x, y]}
    moved = math.hypot(now["cursor"][0] - base["cursor"][0], now["cursor"][1] - base["cursor"][1])
    changed = bool(base["frontmost"]) and now["frontmost"] != base["frontmost"]
    if moved > DRIFT_TOLERANCE_PT or changed:
        return {"cursor_moved_points": round(moved, 2), "frontmost": now["frontmost"],
                "expected_frontmost": base["frontmost"]}
    return None


def _act_perform(args, ctx: Ctx, run: _run.Run, drivers: Drivers, req: ActRequest,
                 sidecar: dict, goal_id: Optional[str], route: str, uses_foreground: bool,
                 secret_value: Optional[str]) -> dict:
    data = run.data
    elements = sidecar.get("elements", {})
    value_ref = req.ref
    if value_ref is None and req.kind in FOCUSED_VALUE_KINDS:
        value_ref = sidecar.get("focus_ref")
    before = _effects.Signals(
        url=sidecar["signals"]["url"], title=sidecar["signals"]["title"],
        tree=sidecar["signals"]["tree"], focus=sidecar["signals"]["focus"],
        value=sidecar["value_digests"].get(value_ref) if value_ref else None,
        screen_hash=sidecar["signals"]["screen_hash"])
    pending_password = None
    if req.secret == "password":
        password_ref = req.ref or sidecar.get("focus_ref")
        if password_ref:
            pending_password = {"ref": password_ref, "element": elements.get(password_ref)}
    action = _build_action(run, req, sidecar.get("scale"),
                           secret_value if req.secret else req.text)
    stage = "act"
    try:
        refused = False
        try:
            result = _perform(run, drivers, route, req, action, req.foreground)
        except DriverError as exc:
            refused = exc.code in REFUSED_BEFORE_DELIVERY
            raise
        finally:
            if uses_foreground and not refused:
                _refresh_drift(run)
        _charge(run, goal_id)
        stage = "observe"

        def read() -> _effects.Signals:
            return _signals(run, _observe(run, drivers, None))

        settled, _ = _effects.settle(read)
        oid = data["latest_observation_id"] + 1
        shot = None if req.secret else run.dir / f"obs-{oid}.png"
        snap = _observe(run, drivers, shot)
        if req.secret:
            snap = snap._replace(screenshot_withheld=True)
        after_ref = None
        if value_ref:
            after_ref = _correlate(run, snap, value_ref, elements.get(value_ref))
        after = _signals(run, snap, after_ref, _screen_hash(snap.screenshot))
        if value_ref and after_ref is None:
            after = dataclasses.replace(after, value=before.value)
        block = _record_observation(run, oid, goal_id, snap, after.screen_hash)
        console_new, requests_new, added = _auto_findings(run, drivers, ctx, goal_id,
                                                          block["screenshot_path"])
    except DriverError as exc:
        if stage == "act" and exc.code not in REFUSED_BEFORE_DELIVERY:
            _charge(run, goal_id)
        return _driver_failure(run, goal_id, exc, stage)
    block["console_errors_new"] = console_new
    block["network_failures_new"] = requests_new

    status, signals, other = _effects.classify(before, after, req.expect, settled)
    if "never_observed" in ctx.faults and status == "OBSERVED":
        status = "NO_EFFECT"
    if "always_observed" in ctx.faults and result.delivered:
        status = "OBSERVED"

    _login_bookkeeping(run, snap, pending_password, _submits_login(req, sidecar["names"]))
    if status in ("OBSERVED", "NO_EFFECT"):
        _add_evidence(run, goal_id, block["screenshot_path"])
    extra = {}
    if snap.screenshot_withheld:
        extra = {"screenshot_withheld": True, "message": SCREENSHOT_WITHHELD}
    return _act_result(
        run, goal_id, status, signals=signals, other_changes=other,
        driver_verified=result.driver_verified, findings_added=added, observation=block, **extra)


def _charge(run: _run.Run, goal_id: Optional[str]) -> None:
    if goal_id:
        run.charge_action(goal_id)


def _refresh_drift(run: _run.Run) -> None:
    now = _drift_now()
    if now is not None:
        run.data["drift_baseline"] = now


def _driver_failure(run: _run.Run, goal_id: Optional[str], exc: DriverError,
                    stage: str) -> dict:
    if stage == "act" and exc.code == "needs_foreground":
        return _act_result(run, goal_id, "FOREGROUND_REQUIRED", message=exc.message)
    if stage == "act" and exc.code == "window_gone":
        return _act_result(run, goal_id, "STALE", message="the target window is gone; observe again")
    return _act_result(run, goal_id, "ERROR", driver_error=exc.code, driver_message=exc.message)


def _names_login_submit(name: Optional[str]) -> bool:
    return bool(name and LOGIN_SUBMIT_RE.search(name))


def _submits_login(req: ActRequest, names: Dict[str, str]) -> bool:
    """True when `req` is the form's submission: an Enter press, or a click on a submit-named control."""
    if req.kind in ("press", "hotkey"):
        return bool(req.key) and req.key.split("+")[-1].strip().lower() in ENTER_KEYS
    if req.kind in ("click", "double-click"):
        return _names_login_submit(names.get(req.ref) if req.ref else req.target_name)
    return False


def _login_bookkeeping(run: _run.Run, snap: Snap, pending_password: Optional[dict],
                       submits: bool) -> None:
    """Count a login attempt when a submission leaves the password field on screen.

    A password fill stays pending through every act that is not a submission, so the run's one
    attempt is spent only by the form's own submit. The field is tracked by its element identity,
    so a password field with no accessible name counts the same as a named one.
    """
    data = run.data
    pending = data.get("login_pending")
    if pending and submits:
        if _correlate(run, snap, pending["ref"], pending.get("element")) is not None:
            data["login_attempts"] += 1
        data["login_pending"] = None
    if pending_password:
        data["login_pending"] = pending_password


def cmd_note(args, ctx: Ctx):
    """Register a finding the model noticed, linked to the goal of `--obs` or the latest observation."""
    run = _load(ctx, args.run)
    summary = _read_stdin().strip()
    if not summary:
        raise UsageError("empty_summary", "the finding summary on stdin is empty")
    ctx.inputs = {"finding_kind": args.finding_kind, "obs": args.obs,
                  "summary_chars": len(summary)}
    data = run.data
    key = str(args.obs) if args.obs is not None else str(data["latest_observation_id"])
    record = data["observations"].get(key)
    if args.obs is not None and record is None:
        raise UsageError("unknown_observation", str(args.obs))
    goal_id = record["goal_id"] if record else None
    shot = record["screenshot_path"] if record else None
    finding = run.add_finding(args.finding_kind, summary, goal_id, shot, "model")
    _add_evidence(run, goal_id, shot)
    return {"ok": True, "finding_id": finding, "goal_id": goal_id}


def cmd_verdict(args, ctx: Ctx):
    """Set a goal's status; `pass` is accepted only when its most recent act returned OBSERVED."""
    run = _load(ctx, args.run)
    _known_goal(run, args.goal)
    summary = _read_stdin().strip()
    ctx.inputs = {"goal": args.goal, "status": args.status, "summary_chars": len(summary)}
    goal = run.data["goals"][args.goal]
    if (args.status == "pass" and goal["last_act_status"] != "OBSERVED"
            and "allow_unverified_pass" not in ctx.faults):
        raise UsageError("pass_without_effect",
                         f"goal {args.goal} has no OBSERVED act as its most recent action")
    replaced = goal["verdict"]
    goal["verdict"] = args.status
    goal["summary"] = summary
    linked = [{"finding_id": f["finding_id"], "kind": f["kind"], "summary": f["summary"]}
              for f in run.data["findings"]
              if f["goal_id"] == args.goal and f["kind"] in ("console", "network")]
    if replaced is not None:
        ctx.status = f"replaced:{replaced}->{args.status}"
    return {"ok": True, "goal_id": args.goal, "status": args.status, "replaced": replaced,
            "linked_findings": linked}


def _save_state_privately(drivers: Drivers, path: Path) -> None:
    """Have the web driver write its storage state (cookies included) to `path`, readable only by the owner.

    The driver writes into a file created 0600 beforehand, so the cookies are never on disk
    under a looser mode. If the driver fails or leaves group or other access on the file, the
    file is removed and `path` is left as it was.
    """
    _run.ensure_private_dir(path.parent)
    staging = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(str(staging), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.close(fd)
        drivers.web.state_save(staging)
        info = os.lstat(str(staging))
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            raise DriverError("state_file_mode",
                              "the browser driver did not keep the storage state file private")
        os.replace(str(staging), str(path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(str(staging))
        raise


def _reopen_web(run: _run.Run, drivers: Drivers, url: str, headed: bool,
                state: Optional[Path]) -> None:
    web = drivers.web
    if state is not None and state.is_file():
        web.open("about:blank", headed=headed)
        web.state_load(state)
        web.goto(url)
    else:
        web.open(url, headed=headed)


def cmd_handoff(args, ctx: Ctx):
    """Release the desktop lock and, on web runs, reopen the page headed so the user can act."""
    run = _load(ctx, args.run)
    data = run.data
    if not data["attended"]:
        raise UsageError("unattended_handoff", "unattended runs cannot hand control to the user")
    if data["paused"]:
        raise RunStateError("run_paused", "the run is already handed off")
    ctx.inputs = {"reason": args.reason}
    drivers = Drivers(run)
    url = None
    headed = False
    try:
        if data["surface"] == "web" and not data["real_chrome"]:
            state = run.dir / "storage-state.json"
            snap = _observe(run, drivers, None)
            url = snap.renderer.url
            _save_state_privately(drivers, state)
            drivers.web.close()
            _reopen_web(run, drivers, url or data["target"], True, state)
            headed = True
            data["handoff_url"] = url
    finally:
        try:
            if data["holds_lock"]:
                _run.DesktopLock().release(data["run_id"])
                data["holds_lock"] = False
        finally:
            data["paused"] = True
    wants = {"login": "sign in", "2fa": "complete the second factor", "hint": "show what to try next"}
    return {
        "ok": True, "reason": args.reason, "headed": headed, "url": url,
        "instructions": f"Ask the user to {wants[args.reason]} in the open window, then run resume.",
    }


def cmd_resume(args, ctx: Ctx):
    """Take the run back after a handoff: restore the session, re-lock if needed, observe afresh."""
    run = _load(ctx, args.run)
    data = run.data
    if not data["paused"]:
        raise RunStateError("not_paused", "the run was not handed off")
    drivers = Drivers(run)
    took_lock = False
    if data["surface"] in ("native", "electron") and not drivers.native.background_capable:
        _run.DesktopLock().acquire(data["run_id"], _project(Path.cwd()), wait_s=LOCK_WAIT_S)
        data["holds_lock"] = True
        took_lock = True
    try:
        return _resume_observe(run, drivers, ctx)
    except BaseException:
        if took_lock:
            _run.DesktopLock().release(data["run_id"])
            data["holds_lock"] = False
        data["paused"] = True
        raise


def _resume_observe(run: _run.Run, drivers: Drivers, ctx: Ctx) -> dict:
    """Reopen the web session if handed off, clear the pause, and take the fresh observation."""
    data = run.data
    if data["surface"] == "web" and data.get("handoff_url") is not None:
        state = run.dir / "storage-state.json"
        snap = _observe(run, drivers, None)
        url = snap.renderer.url or data["handoff_url"]
        _save_state_privately(drivers, state)
        drivers.web.close()
        _reopen_web(run, drivers, url, False, state)
        data["handoff_url"] = None
    data["paused"] = False
    _refresh_drift(run)
    goal_id = None
    record = data["observations"].get(str(data["latest_observation_id"]))
    if record:
        goal_id = record["goal_id"]
    elif data["goals"]:
        goal_id = next(iter(data["goals"]))
    oid = data["latest_observation_id"] + 1
    shot = run.dir / f"obs-{oid}.png"
    snap = _observe(run, drivers, shot)
    block = _record_observation(run, oid, goal_id, snap, _screen_hash(snap.screenshot))
    console_new, requests_new, added = _auto_findings(run, drivers, ctx, goal_id,
                                                      block["screenshot_path"])
    block["console_errors_new"] = console_new
    block["network_failures_new"] = requests_new
    return {"ok": True, "observation": block, "findings_added": added}


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_pid(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            done, _ = os.waitpid(pid, os.WNOHANG)
            if done:
                return
        except ChildProcessError:
            if not _pid_alive(pid):
                return
        time.sleep(0.1)
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


QUIT_APP_SCRIPT = "function run(argv) { const app = Application(argv[0]); if (app.running()) { app.quit(); } }"


def _quit_app(name: str) -> None:
    """Ask the app named by bundle id or display name to quit, if it is running.

    The identifier travels as a script argument, never as script source, so a hostile name stays data.
    """
    proc = subprocess.run(["osascript", "-l", "JavaScript", "-e", QUIT_APP_SCRIPT, "--", name],
                          capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise DriverError("quit_failed", proc.stderr.strip())


def _terminate_launched(run: _run.Run, errors: List[str]) -> None:
    for entry in run.data["launched"]:
        if entry.get("terminated"):
            continue
        kind, _, ident = entry["id"].partition(":")
        try:
            if kind == "pid":
                _terminate_pid(int(ident))
            else:
                _quit_app(ident)
            entry["terminated"] = True
        except (DriverError, OSError, subprocess.SubprocessError, ValueError) as exc:
            errors.append(f"quit {entry['id']}: {exc}")


def _end_cleanup(args, ctx: Ctx, run: _run.Run) -> None:
    """Take the final screenshot, close what the run opened, restore the desktop, release the lock.

    Records the outcome in `state_left` and sets `cleanup_done`, so an `end` retried after a failed
    report write writes the reports without touching the desktop again.
    """
    data = run.data
    errors: List[str] = []
    drivers = Drivers(run)
    final = run.dir / "final.png"
    final_path = ""
    sheet_open = False
    cleanup_only = data["stopped_reason"] == "begin_failed"
    if not cleanup_only:
        try:
            snap = _observe(run, drivers, None if ctx.credentials_lost else final)
            final_path = str(snap.screenshot) if snap.screenshot else ""
            sheet_open = snap.native is not None and snap.native.sheet_open
        except (DriverError, MissingError) as exc:
            errors.append(f"final screenshot: {getattr(exc, 'code', exc)}")
        _save_session(run, drivers, errors)
    sheet_note = _cancel_open_sheet(run, drivers, errors) if sheet_open else None
    broken = [g for g, v in data["goals"].items() if v["verdict"] in ("fail", "blocked")]
    keep = bool(not cleanup_only and (args.keep_open or broken))
    kept: List[str] = []
    if keep:
        kept = _kept_windows(run)
    elif cleanup_only and data["window"]["session"] is None:
        _terminate_launched(run, errors)
    else:
        _close_everything(run, drivers, errors)
    if sheet_note and (keep or not data["launched"]):
        kept.append(sheet_note)
    drivers.close_native(errors)
    clipboard_restored = _restore_clipboard(run, errors)
    frontmost_restored = _restore_frontmost(run, errors)
    if data["holds_lock"]:
        _run.DesktopLock().release(data["run_id"])
    data["holds_lock"] = False
    data["state_left"] = {
        "final_screenshot": final_path, "clipboard_restored": clipboard_restored,
        "frontmost_restored": frontmost_restored, "kept_open": kept, "cleanup_errors": errors,
    }
    data["cleanup_done"] = True


def cmd_end(args, ctx: Ctx):
    """Restore the user's desktop, close what the run opened, release the lock, and write the reports.

    A run whose `begin` failed has nothing to observe, so `end` only retries the cleanup that
    `begin` could not finish, restores the frontmost app, and reports.
    """
    run = _load(ctx, args.run, allow_ended=True, tolerate_lost_credentials=True)
    data = run.data
    ctx.inputs = {"keep_open": args.keep_open}
    if data.get("ended"):
        if data.get("end_output") is None:
            raise RunStateError("run_ended", data["run_id"])
        return data["end_output"], data.get("end_exit", 0)
    if not data.get("cleanup_done"):
        _end_cleanup(args, ctx, run)
    errors = data["state_left"]["cleanup_errors"]
    data["ended"] = _now()
    try:
        report = run.write_report()
    except BaseException:
        data["ended"] = None
        raise
    _run.forget_typed(ctx.root, data["run_id"])
    out = {
        "ok": not errors, "run_id": data["run_id"], "summary": report,
        "report_json": str(run.dir / "report.json"), "report_md": str(run.dir / "report.md"),
        "test_overrides": data["test_overrides"],
    }
    code = 0
    if errors:
        out["error"] = "cleanup_failed"
        out["driver_error"] = "cleanup_failed"
        code = 4
    data["summary"] = report
    data["end_output"] = out
    data["end_exit"] = code
    return out, code


def _cancel_open_sheet(run: _run.Run, drivers: Drivers, errors: List[str]) -> Optional[str]:
    """Escape out of a sheet or dialog still open at `end`; return a note when it stays open.

    The key goes to the foreground only while the lock holder record still names this run, and
    never after the user took over, so `end` cannot steal the keyboard. A run whose lock was
    replaced sends nothing and reports the sheet as left open.
    """
    data = run.data
    if data["stopped_reason"]:
        return SHEET_LEFT_OPEN
    foreground = data["holds_lock"] and _run.DesktopLock().owns(data["run_id"])
    if data["holds_lock"] and not foreground:
        errors.append("cancel sheet: desktop lock no longer held by this run")
        return SHEET_LEFT_OPEN
    try:
        drivers.native.act(Action(kind="press", key="Escape"), foreground)
        deadline = time.monotonic() + SHEET_CLOSE_WAIT_S
        while _observe_native(drivers, None).sheet_open:
            if time.monotonic() >= deadline:
                return SHEET_LEFT_OPEN
            time.sleep(0.25)
    except DriverError as exc:
        if exc.code != "needs_foreground":
            errors.append(f"cancel sheet: {exc.code}")
        return SHEET_LEFT_OPEN
    return None


def _save_session(run: _run.Run, drivers: Drivers, errors: List[str]) -> None:
    key = run.data.get("session_key")
    if not key or not drivers.uses_web:
        return
    path = _session_file(run, key)
    try:
        _save_state_privately(drivers, path)
    except (DriverError, UsageError, OSError) as exc:
        errors.append(f"save session: {getattr(exc, 'code', exc)}")


def _kept_windows(run: _run.Run) -> List[str]:
    kept: List[str] = []
    if run.data["surface"] in ("web", "electron"):
        kept.append(f"browser session {run.data['window']['session']}")
    for entry in run.data["launched"]:
        kept.append(entry["id"])
    return kept


def _close_everything(run: _run.Run, drivers: Drivers, errors: List[str]) -> None:
    """Close or detach the browser session and quit what the run launched.

    Steps that already succeeded are remembered in the run state, so calling this again after a
    partial failure retries only what is left.
    """
    window = run.data["window"]
    if drivers.uses_web and not window.get("session_closed"):
        try:
            if run.data["surface"] == "electron" or run.data["real_chrome"]:
                drivers.web.detach()
            else:
                drivers.web.close()
            window["session_closed"] = True
        except DriverError as exc:
            errors.append(f"close session: {exc.code}")
    _terminate_launched(run, errors)


def _restore_clipboard(run: _run.Run, errors: List[str]) -> Optional[bool]:
    """Put back the clipboard the run pasted over.

    Returns None when the run never wrote the clipboard, True when it restored it, and False when
    it wrote the clipboard and left it as it is.
    """
    data = run.data
    clip = run.dir / "clipboard.txt"
    restored: Optional[bool] = False if data["pasted"] else None
    try:
        if data["pasted"] and clip.is_file():
            count = _desktop.clipboard_change_count()
            if count == data["baseline"]["clipboard_change_count"]:
                pass
            elif count != data.get("paste_change_count"):
                errors.append("clipboard changed after the run pasted; left as it is")
            else:
                _desktop.clipboard_write_text(clip.read_text(encoding="utf-8"))
                restored = True
    except (DriverError, OSError) as exc:
        errors.append(f"restore clipboard: {getattr(exc, 'code', exc)}")
    try:
        clip.unlink()
    except OSError:
        pass
    return restored


def _restore_frontmost(run: _run.Run, errors: List[str]) -> bool:
    wanted = run.data["baseline"]["frontmost"]
    if not wanted:
        return False
    try:
        if _desktop.frontmost_bundle_id() != wanted:
            _desktop.activate(wanted)
        return _desktop.frontmost_bundle_id() == wanted
    except DriverError as exc:
        errors.append(f"restore frontmost: {exc.code}")
        return False


HANDLERS = {
    "doctor": cmd_doctor, "begin": cmd_begin, "goal": cmd_goal, "observe": cmd_observe,
    "act": cmd_act, "note": cmd_note, "verdict": cmd_verdict, "handoff": cmd_handoff,
    "resume": cmd_resume, "end": cmd_end,
}


def _failure(exc: BaseException) -> Tuple[dict, int]:
    if isinstance(exc, UsageError):
        return {"ok": False, "error": exc.code, "message": exc.message}, 2
    if isinstance(exc, RunStateError):
        out = {"ok": False, "error": exc.code, "message": exc.message}
        if exc.code == "desktop_busy":
            out["holder"] = {k: exc.detail.get(k) for k in ("run_id", "project")}
        else:
            out.update(exc.detail)
        return out, 3
    if isinstance(exc, DriverError):
        return {"ok": False, "error": "driver_error", "driver_error": exc.code,
                "message": exc.message}, 4
    if isinstance(exc, MissingError):
        return {"ok": False, "error": "missing", "missing": exc.missing}, 5
    return {"ok": False, "error": "internal_error", "message": str(exc)}, 1


def main(argv: Optional[List[str]] = None) -> int:
    """Run one verb, print one JSON object, and return the exit code.

    The verb runs under umask 077, so the tools it spawns also create private files; the caller's
    umask is restored afterwards.
    """
    previous = os.umask(0o077)
    try:
        return _run_verb(argv)
    finally:
        os.umask(previous)


def _run_verb(argv: Optional[List[str]]) -> int:
    started = time.monotonic()
    ctx = Ctx()
    command = None
    try:
        args = build_parser().parse_args(argv)
        command = args.command
        ctx.faults = _faults()
        result = HANDLERS[command](args, ctx)
        out, code = result if isinstance(result, tuple) else (result, 0)
        if isinstance(out, dict) and "status" in out and command == "act":
            ctx.status = out["status"]
    except SystemExit:
        raise
    except BaseException as exc:
        out, code = _failure(exc)
        ctx.status = f"error:{out['error']}"
        if ctx.cleanup_errors and ctx.run is not None:
            out["run_id"] = ctx.run.data["run_id"]
            out["cleanup_errors"] = list(ctx.cleanup_errors)
        if code == 1:
            text = _run.redact(traceback.format_exc(), ctx.secrets())
            sys.stderr.write(text)
    run = ctx.run
    if run is not None and run.dir.exists():
        try:
            run.scrub_driver_files()
            run.save()
            run.event(command or "unknown", ctx.inputs, ctx.status,
                      int((time.monotonic() - started) * 1000))
            run.harden()
        except OSError as exc:
            sys.stderr.write(f"could not write run state: {exc}\n")
    sys.stdout.write(json.dumps(_scrub(out, ctx.secrets())) + "\n")
    sys.stdout.flush()
    return code


if __name__ == "__main__":
    sys.exit(main())
