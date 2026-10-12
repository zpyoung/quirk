"""Run folder, run state, desktop lock, credentials, and gate tables for likeuser.

The CLI is the only caller. Everything here is deterministic and stdlib-only so the guard's
bookkeeping can be tested without a browser or a display.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import secrets as _secrets
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from _types import MissingError, RunStateError, UsageError  # noqa: E402

STATE_DIR_PARTS = (".quirk", "using-apps-like-a-user")
DEFAULT_RUN_CAP = 200
DEFAULT_GOAL_CAP = 40
LOCK_WAIT_S = 30.0
LOCK_STALE_S = 15 * 60
LOCK_POLL_S = 0.5
REDACTED = "[REDACTED]"
OVERRIDE_BANNER = "TEST OVERRIDES ACTIVE — results are not valid evidence"

OVERRIDE_VARS = (
    "LIKEUSER_PLAYWRIGHT_BIN",
    "LIKEUSER_ORCA_BIN",
    "LIKEUSER_NATIVE_BIN",
    "LIKEUSER_FAKE_DESKTOP",
    "LIKEUSER_STATE_ROOT",
    "LIKEUSER_LOCK_PATH",
    "LIKEUSER_FAULT",
)

_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_CLEAR = object()

GATE_THIRD_PARTY_RE = re.compile(
    r"\b(submit|send|post|publish|share|pay|buy|purchase|order|checkout|subscribe|transfer"
    r"|delete|remove|deactivate|close account|confirm|authori[sz]e|grant|revoke|save changes"
    r"|update (?:password|email|payment))\b",
    re.IGNORECASE,
)
GATE_YOURS_RE = re.compile(r"\b(delete|remove|destroy|drop|purge|wipe|erase)\b", re.IGNORECASE)
DISMISS_RE = re.compile(
    r"^(reject all|reject|decline|necessary only|only necessary|essential only|not now|later"
    r"|no thanks|dismiss|close|maybe later|skip)$",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime(_TIME_FORMAT)


def state_root(cwd: Path) -> Path:
    """Return the self-ignoring folder that holds every run and saved session for a project.

    `LIKEUSER_STATE_ROOT` wins; otherwise the git toplevel of `cwd` (or `cwd` outside a repo)
    carries `.quirk/using-apps-like-a-user`. The folder gets its own `.gitignore` of `*` so the
    project's own ignore file is never edited.
    """
    override = os.environ.get("LIKEUSER_STATE_ROOT")
    if override:
        root = Path(override)
    else:
        base = Path(cwd)
        try:
            out = subprocess.run(
                ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=10,
            )
            if out.returncode == 0 and out.stdout.strip():
                base = Path(out.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass
        root = base.joinpath(*STATE_DIR_PARTS)
    root.mkdir(parents=True, exist_ok=True)
    ignore = root / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")
    return root


def new_run_id() -> str:
    """Return a run id of the form `<UTC yyyymmddThhmmss>-<4 hex>`."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{_secrets.token_hex(2)}"


def redact(text: str, secrets: Iterable[str]) -> str:
    """Replace every non-empty secret in `text` with `[REDACTED]`, longest secret first."""
    out = text
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        out = out.replace(secret, REDACTED)
    return out


def _redact_deep(value: Any, secrets: Iterable[str]) -> Any:
    secrets = [s for s in secrets if s]
    if not secrets:
        return value
    if isinstance(value, str):
        return redact(value, secrets)
    if isinstance(value, dict):
        return {_redact_deep(k, secrets): _redact_deep(v, secrets) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_deep(v, secrets) for v in value]
    return value


def _default_run_data() -> dict:
    return {
        "run_id": "", "target": "", "surface": "", "owner": "", "attended": False,
        "allow_foreground": False, "driver": "", "driver_version": "",
        "window": {"bundle_id": None, "window_id": None, "session": None, "cdp_port": None},
        "baseline": {"frontmost": "", "cursor": [0.0, 0.0], "clipboard_change_count": 0,
                     "clipboard_text_only": True},
        "drift_baseline": {"frontmost": "", "cursor": [0.0, 0.0]},
        "holds_lock": False, "paused": False, "stopped_reason": None, "pasted": False,
        "goals": {},
        "budget": {"run_cap": DEFAULT_RUN_CAP, "goal_cap": DEFAULT_GOAL_CAP, "run_used": 0},
        "latest_observation_id": 0, "launched": [], "observations": {},
        "findings": [], "gates": [], "console_seen": 0, "requests_seen": 0,
        "login_attempts": 0, "test_overrides": [], "started": "", "ended": None,
        "summary": None,
    }


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class Run:
    """One guarded session: its folder, its `run.json` state, and its event log.

    `data` follows the run.json schema. `secrets` is an in-memory set the CLI fills with
    credential values; every write redacts against it and it is never persisted.
    """

    def __init__(self, directory: Path, data: dict) -> None:
        self.dir = Path(directory)
        self.data = data
        self.secrets: Set[str] = set()

    @classmethod
    def create(cls, root: Path, fields: dict) -> "Run":
        """Create `<root>/runs/<run-id>/` and write its first `run.json` from schema defaults and `fields`."""
        data = _default_run_data()
        for key, value in fields.items():
            if key == "budget":
                data["budget"].update(value)
            else:
                data[key] = value
        runs = Path(root) / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        while True:
            run_id = data["run_id"] or new_run_id()
            directory = runs / run_id
            try:
                directory.mkdir()
                break
            except FileExistsError:
                if fields.get("run_id"):
                    raise RunStateError("run_exists", run_id)
                data["run_id"] = ""
        data["run_id"] = run_id
        if not data["started"]:
            data["started"] = _utc_now()
        run = cls(directory, data)
        run.save()
        return run

    @classmethod
    def load(cls, root: Path, run_id: str) -> "Run":
        """Load a run by id; `RunStateError("unknown_run")` when it does not exist."""
        directory = Path(root) / "runs" / run_id
        state = directory / "run.json"
        if not run_id or "/" in run_id or run_id in (".", "..") or not state.is_file():
            raise RunStateError("unknown_run", run_id)
        try:
            data = json.loads(state.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RunStateError("unknown_run", f"{run_id}: {exc}")
        return cls(directory, data)

    def save(self) -> None:
        """Write `run.json` atomically, redacting known secrets from every string."""
        payload = _redact_deep(self.data, self.secrets)
        _atomic_write(self.dir / "run.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def event(self, verb: str, inputs: dict, status: str, elapsed_ms: int) -> None:
        """Append one redacted `{ts, verb, inputs, status, elapsed_ms}` line to `events.jsonl`."""
        record = {"ts": _utc_now(), "verb": verb, "inputs": inputs, "status": status,
                  "elapsed_ms": elapsed_ms}
        line = json.dumps(_redact_deep(record, self.secrets), sort_keys=True)
        with open(self.dir / "events.jsonl", "a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def add_goal(self, goal_id: str, title: str) -> None:
        """Register a goal; `UsageError("duplicate_goal")` when the id is already taken."""
        if goal_id in self.data["goals"]:
            raise UsageError("duplicate_goal", goal_id)
        self.data["goals"][goal_id] = {
            "title": title, "last_act_status": None, "actions_used": 0, "verdict": None,
            "summary": "", "evidence": [],
        }

    def add_finding(self, kind: str, summary: str, goal_id: Optional[str],
                    screenshot_path: Optional[str], source: str) -> str:
        """Append a finding and return its run-unique id."""
        finding_id = f"F{len(self.data['findings']) + 1}"
        self.data["findings"].append({
            "finding_id": finding_id, "kind": kind, "summary": summary, "goal_id": goal_id,
            "screenshot_path": screenshot_path, "source": source,
        })
        return finding_id

    def record_gate(self, observation_id: int, subject: str, gate: str) -> None:
        """Record that an action on `subject` was gated at `observation_id`."""
        self.data["gates"].append(
            {"observation_id": observation_id, "subject": subject, "gate": gate})

    def charge_action(self, goal_id: str) -> Optional[str]:
        """Spend one action on `goal_id`, or name the spent budget (`"run"` before `"goal"`) and charge nothing."""
        goal = self.data["goals"].get(goal_id)
        if goal is None:
            raise UsageError("unknown_goal", goal_id)
        budget = self.data["budget"]
        if budget["run_used"] >= budget["run_cap"]:
            return "run"
        if goal["actions_used"] >= budget["goal_cap"]:
            return "goal"
        budget["run_used"] += 1
        goal["actions_used"] += 1
        return None

    def write_report(self) -> dict:
        """Write `report.json` and `report.md` from run state and return the report summary."""
        report = self._build_report()
        report = _redact_deep(report, self.secrets)
        _atomic_write(self.dir / "report.json", json.dumps(report, indent=2) + "\n")
        _atomic_write(self.dir / "report.md", _render_markdown(report))
        return report

    def _build_report(self) -> dict:
        d = self.data
        findings = d["findings"]
        goals = []
        for goal_id, goal in d["goals"].items():
            goals.append({
                "goal_id": goal_id,
                "title": goal["title"],
                "status": goal["verdict"] or "unset",
                "evidence": list(goal["evidence"]),
                "findings": [f["finding_id"] for f in findings if f["goal_id"] == goal_id],
                "summary": goal["summary"],
            })
        state_left = {"final_screenshot": "", "clipboard_restored": None,
                      "frontmost_restored": False, "kept_open": [], "cleanup_errors": []}
        state_left.update(d.get("state_left") or {})
        return {
            "run": {key: d.get(key) for key in (
                "run_id", "target", "surface", "owner", "attended", "driver", "driver_version",
                "started", "ended", "stopped_reason", "test_overrides")},
            "goals": goals,
            "findings": [dict(f) for f in findings],
            "gates": [dict(g) for g in d["gates"]],
            "state_left": state_left,
            "budget": {"run_used": d["budget"]["run_used"], "run_cap": d["budget"]["run_cap"]},
        }


_CLIPBOARD_LABELS = {None: "not touched", True: "restored", False: "changed and not restored"}


def _render_markdown(report: dict) -> str:
    run = report["run"]
    lines: List[str] = []
    if run["test_overrides"]:
        lines += [OVERRIDE_BANNER, "", "Overrides set: " + ", ".join(run["test_overrides"]), ""]
    lines += [f"# Run {run['run_id']}", ""]
    lines += [
        f"- Target: {run['target']} ({run['surface']}, owner {run['owner']})",
        f"- Driver: {run['driver']} {run['driver_version']}",
        f"- Started: {run['started']}  ",
        f"- Ended: {run['ended'] or 'not ended'}  ",
        f"- Stopped reason: {run['stopped_reason'] or 'none'}",
        f"- Budget: {report['budget']['run_used']} of {report['budget']['run_cap']} actions",
        "", "## Goals", "",
    ]
    if not report["goals"]:
        lines += ["No goals registered.", ""]
    for goal in report["goals"]:
        lines += [f"### {goal['goal_id']}: {goal['title']} ({goal['status']})", ""]
        if goal["summary"]:
            lines += [goal["summary"], ""]
        if goal["findings"]:
            lines += ["Findings: " + ", ".join(goal["findings"]), ""]
        for path in goal["evidence"]:
            lines += [f"- [{Path(path).name}]({path})"]
        if goal["evidence"]:
            lines.append("")
    lines += ["## Findings", ""]
    if not report["findings"]:
        lines += ["None.", ""]
    for f in report["findings"]:
        entry = f"- {f['finding_id']} [{f['kind']}, {f['source']}] {f['summary']}"
        if f["goal_id"]:
            entry += f" (goal {f['goal_id']})"
        if f["screenshot_path"]:
            entry += f" [{Path(f['screenshot_path']).name}]({f['screenshot_path']})"
        lines.append(entry)
    if report["findings"]:
        lines.append("")
    lines += ["## Gates", ""]
    if not report["gates"]:
        lines += ["None.", ""]
    for g in report["gates"]:
        lines.append(f"- observation {g['observation_id']}: {g['gate']} on \"{g['subject']}\"")
    if report["gates"]:
        lines.append("")
    left = report["state_left"]
    lines += ["## State left", ""]
    if left["final_screenshot"]:
        lines.append(f"- Final screenshot: [{Path(left['final_screenshot']).name}]"
                     f"({left['final_screenshot']})")
    lines += [
        f"- Clipboard: {_CLIPBOARD_LABELS[left['clipboard_restored']]}",
        f"- Frontmost app restored: {'yes' if left['frontmost_restored'] else 'no'}",
        f"- Kept open: {', '.join(left['kept_open']) or 'nothing'}",
        f"- Cleanup errors: {'; '.join(left['cleanup_errors']) or 'none'}",
        "",
    ]
    return "\n".join(lines)


def _parse_time(value: Any) -> Optional[datetime]:
    try:
        return datetime.strptime(value, _TIME_FORMAT).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


class DesktopLock:
    """Machine-wide lock that serializes runs needing the foreground desktop.

    The holder record lives in the lock file and every read or write happens under `flock`, so
    acquisition is atomic across processes. A holder idle for more than 15 minutes is stale and
    may be replaced; `replaced` then names it so the caller can log the takeover.

    A non-empty record that is malformed or lacks `run_id`/`last_act_at` (a short write after
    truncation) fails closed: it reads as a holder with `run_id` "unknown" and `unreadable` set,
    and ages by the lock file's mtime so it cannot wedge the desktop for good.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        if path is not None:
            self.path = Path(path)
        elif os.environ.get("LIKEUSER_LOCK_PATH"):
            self.path = Path(os.environ["LIKEUSER_LOCK_PATH"])
        else:
            self.path = (Path.home() / ".local" / "state" / "quirk" / "using-apps-like-a-user"
                         / "desktop.lock")
        self.replaced: Optional[dict] = None

    def _locked(self, fn: Callable[[Optional[dict]], Any], write: bool = True) -> Any:
        """Run `fn(holder)` under an exclusive flock and return its result.

        With `write`, `fn` returns `(result, change)`: a dict `change` becomes the new holder,
        `_CLEAR` empties the file, and None leaves it untouched.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            raw = b""
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                raw += chunk
            holder: Optional[dict] = None
            if raw.strip():
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except ValueError:
                    parsed = None
                if isinstance(parsed, dict) and isinstance(parsed.get("run_id"), str) \
                        and parsed["run_id"] and _parse_time(parsed.get("last_act_at")):
                    holder = parsed
                else:
                    holder = self._unknown_holder(os.fstat(fd).st_mtime)
            outcome = fn(holder)
            if not write:
                return outcome
            result, change = outcome
            if change is _CLEAR:
                os.ftruncate(fd, 0)
                os.fsync(fd)
            elif change is not None:
                os.ftruncate(fd, 0)
                os.lseek(fd, 0, os.SEEK_SET)
                os.write(fd, json.dumps(change, sort_keys=True).encode("utf-8"))
                os.fsync(fd)
            return result
        finally:
            os.close(fd)

    @staticmethod
    def _unknown_holder(mtime: float) -> dict:
        seen = datetime.fromtimestamp(mtime, timezone.utc).strftime(_TIME_FORMAT)
        return {"run_id": "unknown", "project": "unknown", "acquired_at": seen,
                "last_act_at": seen, "unreadable": True}

    @staticmethod
    def _is_stale(holder: dict) -> bool:
        seen = _parse_time(holder.get("last_act_at"))
        if seen is None:
            return True
        return (datetime.now(timezone.utc) - seen).total_seconds() > LOCK_STALE_S

    def try_acquire(self, run_id: str, project: str) -> Optional[dict]:
        """Take the lock for `run_id`; return None on success, else the live holder's record."""
        self.replaced = None
        replaced: List[Optional[dict]] = [None]

        def attempt(holder: Optional[dict]):
            now = _utc_now()
            if holder and not holder.get("unreadable") and holder.get("run_id") == run_id:
                updated = dict(holder)
                updated["last_act_at"] = now
                return None, updated
            if holder and not self._is_stale(holder):
                return holder, None
            replaced[0] = holder
            return None, {"run_id": run_id, "project": project, "acquired_at": now,
                          "last_act_at": now}

        busy = self._locked(attempt)
        if busy is None:
            self.replaced = replaced[0]
        return busy

    def acquire(self, run_id: str, project: str, wait_s: float = LOCK_WAIT_S,
                sleep: Callable[[float], None] = time.sleep,
                clock: Callable[[], float] = time.monotonic) -> None:
        """Poll `try_acquire` for up to `wait_s` seconds; raise `RunStateError("desktop_busy")` with the holder."""
        deadline = clock() + wait_s
        while True:
            holder = self.try_acquire(run_id, project)
            if holder is None:
                return
            remaining = deadline - clock()
            if remaining <= 0:
                raise RunStateError(
                    "desktop_busy",
                    f"held by run {holder.get('run_id')} ({holder.get('project')})",
                    detail=holder)
            sleep(min(LOCK_POLL_S, remaining))

    def refresh(self, run_id: str) -> None:
        """Mark the holder as just active; a no-op unless `run_id` holds the lock."""
        def touch(holder: Optional[dict]):
            if holder and not holder.get("unreadable") and holder.get("run_id") == run_id:
                updated = dict(holder)
                updated["last_act_at"] = _utc_now()
                return None, updated
            return None, None

        self._locked(touch)

    def release(self, run_id: str) -> None:
        """Free the lock if `run_id` holds it; a no-op for anyone else."""
        def drop(holder: Optional[dict]):
            if holder and not holder.get("unreadable") and holder.get("run_id") == run_id:
                return None, _CLEAR
            return None, None

        self._locked(drop)

    def holder(self) -> Optional[dict]:
        """Return the current holder record, or None when the lock is free."""
        if not self.path.exists():
            return None
        return self._locked(lambda holder: holder, write=False)


def load_credentials(prefix: Optional[str], file: Optional[Path]) -> Dict[str, str]:
    """Return `{username, password}` from a 0600 JSON file when given, else from `<PREFIX>_USERNAME`/`_PASSWORD`.

    The mode check and the read use one opened descriptor, and symlinks and non-regular files are
    refused. Raises `MissingError(["credentials_file_mode"])` for a file readable by group or others and
    `MissingError(["credentials"])` when either value is absent.
    """
    if file is not None:
        path = Path(file)
        try:
            fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            raise MissingError(["credentials_file"])
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise MissingError(["credentials_file"])
            if stat.S_IMODE(info.st_mode) & 0o077:
                raise MissingError(["credentials_file_mode"])
            try:
                with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as handle:
                    doc = json.load(handle)
                username, password = doc["username"], doc["password"]
            except (OSError, ValueError, KeyError, TypeError):
                raise MissingError(["credentials"])
        finally:
            os.close(fd)
        if not isinstance(username, str) or not isinstance(password, str) \
                or not username or not password:
            raise MissingError(["credentials"])
        return {"username": username, "password": password}
    name = prefix or "LIKEUSER"
    username = os.environ.get(f"{name}_USERNAME")
    password = os.environ.get(f"{name}_PASSWORD")
    if not username or not password:
        raise MissingError(["credentials"])
    return {"username": username, "password": password}


def test_overrides(env: Mapping[str, str]) -> List[str]:
    """Return the sorted names of the test-only `LIKEUSER_*` override variables set in `env`."""
    return sorted(name for name in OVERRIDE_VARS if env.get(name))


def gate_matches(subject: str, owner: str) -> bool:
    """True when `subject` (an accessible name) names an action that needs a gate for this `owner`."""
    if owner == "third-party":
        return bool(GATE_THIRD_PARTY_RE.search(subject))
    if owner == "yours":
        return bool(GATE_YOURS_RE.search(subject))
    raise UsageError("bad_owner", owner)


def dismiss_allowed(name: str) -> bool:
    """True when the whole accessible name is on the harmless-dismiss allowlist."""
    return bool(DISMISS_RE.fullmatch(name.strip()))
