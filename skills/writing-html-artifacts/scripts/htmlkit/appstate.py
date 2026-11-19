"""On-disk session state for the visual companion's app mode.

The companion server and short-lived CLI processes (``step``, ``status``, ``decide``, ``say``,
``reply``) all read and write the same files under ``<session>/state/``. Every mutating method
takes an exclusive ``fcntl.flock`` on ``state/app.lock``, so concurrent writers never lose updates.
Reads that feed a snapshot take the same lock, so a snapshot is internally consistent.

``rev`` (bumped once per mutating call) and ``seq`` (shared by user events and chat entries) live in
``state/counters.json`` and so stay monotonic across restarts. A new seq is allocated above the
highest seq already in ``app-events`` or ``chat.json``, so a lost counters write never reuses one.
"""
from __future__ import annotations

import contextlib
import datetime
import fcntl
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, ContextManager, Iterable, Iterator

from .fsutil import atomic_write

STAGES = ("context", "gray-areas", "questions", "approaches", "ux-review", "design", "spec", "hand-off")
EVENT_TYPES = ("submit", "continue", "chat", "comment", "edit-request", "edit-decision", "review-export",
               "run-answer", "run-stop", "run-retry")

_SENDERS = ("agent", "user", "system")
_DECISION_STATUSES = ("confirmed", "assumed", "open")
_RESOLUTIONS = ("addressed", "not-addressed")
_PROGRESS_RE = re.compile(r"\d+/\d+")
_DECISION_ID_RE = re.compile(r"[a-z0-9-]{1,40}")
_KIND_RE = re.compile(r"[a-z0-9-]{1,40}")
_STEP_NUM_RE = re.compile(r"^(\d{4})-")
_STEP_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_POINTER_CHARS = 80


class AppStateError(ValueError):
    """Invalid input to an AppState call; ``field`` names the offending argument or key."""

    def __init__(self, field: str, message: str | None = None):
        self.field = field
        super().__init__(message or f"invalid {field}")


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


class AppState:
    """Reads and writes one session's app-mode state; safe across threads and processes."""

    def __init__(self, session: os.PathLike):
        self._dir = Path(session) / "state"
        self._rlock = threading.RLock()
        self._depth = 0
        self._fd: int | None = None

    # ---- locking and layout -------------------------------------------------

    def _ensure_dirs(self) -> None:
        for d in (self._dir, self._dir / "steps", self._dir / "drafts"):
            d.mkdir(parents=True, exist_ok=True)

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        with self._rlock:
            if self._depth == 0:
                self._ensure_dirs()
                fd = os.open(self._dir / "app.lock", os.O_RDWR | os.O_CREAT, 0o600)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX)
                except BaseException:
                    os.close(fd)
                    raise
                self._fd = fd
            self._depth += 1
            try:
                yield
            finally:
                self._depth -= 1
                if self._depth == 0:
                    fd, self._fd = self._fd, None
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    finally:
                        os.close(fd)

    def lock(self) -> ContextManager[None]:
        """Exclusive inter-process lock on ``state/app.lock``; re-entrant within this instance."""
        return self._locked()

    def bump_rev(self) -> int:
        """Advance ``rev`` for a change made outside AppState's own files; returns the new rev."""
        with self._locked():
            return self._tick()

    # ---- raw file helpers (callers hold the lock) ----------------------------

    def _read_json(self, name: str, default: Any) -> Any:
        try:
            return json.loads((self._dir / name).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return default

    def _write_json(self, name: str, value: Any) -> None:
        atomic_write(self._dir / name, json.dumps(value, ensure_ascii=False))

    def _tick(self, *, seq: int | None = None) -> int:
        """Bump ``rev`` in one counters write, recording ``seq`` as the high-water mark when given.

        Returns ``seq`` when given, else the new rev.
        """
        c = self._read_json("counters.json", {"rev": 0, "seq": 0})
        c["rev"] = int(c.get("rev", 0)) + 1
        if seq is not None:
            c["seq"] = max(int(c.get("seq", 0)), seq)
        self._write_json("counters.json", c)
        return seq if seq is not None else c["rev"]

    def _next_seq_value(self, chat: list[dict] | None = None) -> int:
        """Next unused seq, above anything already durable.

        The counters file can lag the event and chat files after a crash between the two writes, so
        the high-water mark is taken over all three. Callers holding the lock may pass the chat
        list they already loaded.
        """
        if chat is None:
            chat = self._read_json("chat.json", [])
        high = int(self._read_json("counters.json", {"seq": 0}).get("seq", 0))
        for item in (*self._events(), *chat):
            s = item.get("seq") if isinstance(item, dict) else None
            if isinstance(s, int) and s > high:
                high = s
        return high + 1

    def _events(self) -> list[dict]:
        out: list[dict] = []
        try:
            text = (self._dir / "app-events").read_text(encoding="utf-8")
        except FileNotFoundError:
            return out
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    # ---- init and token ------------------------------------------------------

    def init(self) -> None:
        """Create the state layout, counters and token if absent; never rotates an existing token."""
        with self._locked():
            if not (self._dir / "counters.json").exists():
                self._write_json("counters.json", {"rev": 0, "seq": 0})
            tok = self._dir / "token"
            if not tok.exists():
                # pre-create at 0600 so atomic_write (which keeps an existing file's mode) never widens it
                os.close(os.open(tok, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
                atomic_write(tok, secrets.token_urlsafe(24))
                os.chmod(tok, 0o600)

    def token(self) -> str:
        with self._locked():
            return (self._dir / "token").read_text(encoding="utf-8").strip()

    # ---- steps ---------------------------------------------------------------

    def write_step(self, step: dict) -> dict:
        """Persist ``step`` as the next numbered step and make it current; returns ``{step, nonce}``."""
        if not isinstance(step, dict):
            raise AppStateError("step")
        kind = step.get("kind")
        if not isinstance(kind, str) or not _KIND_RE.fullmatch(kind):
            raise AppStateError("kind")
        if "stage" in step and step["stage"] not in STAGES:
            raise AppStateError("stage")
        with self._locked():
            nums = [
                int(m.group(1))
                for p in (self._dir / "steps").glob("*.json")
                if (m := _STEP_NUM_RE.match(p.name))
            ]
            step_id = f"{max(nums, default=0) + 1:04d}-{kind}"
            nonce = secrets.token_urlsafe(16)
            self._write_json(f"steps/{step_id}.json", step)
            self._write_json(
                "current.json",
                {"screen": step_id, "nonce": nonce, "shown_at": time.time(), "mode": "app"},
            )
            self._tick()
            return {"step": step_id, "nonce": nonce}

    def current(self) -> dict | None:
        with self._locked():
            return self._read_json("current.json", None)

    # ---- status --------------------------------------------------------------

    def set_status(
        self,
        text: str,
        stage: str | None = None,
        progress: str | None = None,
        interruptible: bool = False,
    ) -> dict:
        if not _nonempty_str(text):
            raise AppStateError("text")
        if stage is not None and stage not in STAGES:
            raise AppStateError("stage")
        if progress is not None and not (isinstance(progress, str) and _PROGRESS_RE.fullmatch(progress)):
            raise AppStateError("progress")
        with self._locked():
            prior = self._read_json("status.json", None)
            started = prior["started_at"] if isinstance(prior, dict) and "started_at" in prior else time.time()
            status: dict[str, Any] = {"text": text}
            if stage is not None:
                status["stage"] = stage
            if progress is not None:
                status["progress"] = progress
            status["interruptible"] = bool(interruptible)
            status["started_at"] = started
            self._write_json("status.json", status)
            self._tick()
            return status

    def clear_status(self) -> None:
        with self._locked():
            (self._dir / "status.json").unlink(missing_ok=True)
            self._tick()

    # ---- decisions -----------------------------------------------------------

    @staticmethod
    def _validate_decisions(decisions: Any) -> list[dict]:
        if not isinstance(decisions, list):
            raise AppStateError("decisions")
        seen: set[str] = set()
        clean: list[dict] = []
        for i, d in enumerate(decisions):
            if not isinstance(d, dict):
                raise AppStateError(f"[{i}]")
            did = d.get("id")
            if not (isinstance(did, str) and _DECISION_ID_RE.fullmatch(did)) or did in seen:
                raise AppStateError(f"[{i}].id")
            seen.add(did)
            if d.get("stage") not in STAGES:
                raise AppStateError(f"[{i}].stage")
            for key in ("area", "label", "value"):
                if not _nonempty_str(d.get(key)):
                    raise AppStateError(f"[{i}].{key}")
            if d.get("status") not in _DECISION_STATUSES:
                raise AppStateError(f"[{i}].status")
            item = {k: d[k] for k in ("id", "stage", "area", "label", "value", "status")}
            if "note" in d:
                if not isinstance(d["note"], str):
                    raise AppStateError(f"[{i}].note")
                item["note"] = d["note"]
            clean.append(item)
        return clean

    def set_decisions(self, decisions: list) -> int:
        """Replace the whole decisions list; an invalid list changes nothing. Returns the new rev."""
        clean = self._validate_decisions(decisions)
        with self._locked():
            self._write_json("decisions.json", clean)
            return self._tick()

    # ---- events and drafts ---------------------------------------------------

    def append_event(self, type: str, payload: dict, client_id: str, step: str | None = None) -> int | None:
        """Append a user event; returns its seq, or None when ``client_id`` was already recorded."""
        if type not in EVENT_TYPES:
            raise AppStateError("type")
        if not isinstance(payload, dict):
            raise AppStateError("payload")
        if not _nonempty_str(client_id):
            raise AppStateError("client_id")
        with self._locked():
            if any(e.get("client_id") == client_id for e in self._events()):
                return None
            seq = self._next_seq_value()
            event = {
                "seq": seq, "type": type, "step": step, "client_id": client_id,
                "timestamp": time.time(), "payload": payload,
            }
            with open(self._dir / "app-events", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            self._tick(seq=seq)
            return seq

    def events_after(self, seq: int) -> list[dict]:
        with self._locked():
            return sorted((e for e in self._events() if e.get("seq", 0) > seq), key=lambda e: e["seq"])

    def save_draft(self, step_id: str, payload: dict) -> None:
        if not (isinstance(step_id, str) and _STEP_ID_RE.fullmatch(step_id)):
            raise AppStateError("step_id")
        if not isinstance(payload, dict):
            raise AppStateError("payload")
        with self._locked():
            self._write_json(f"drafts/{step_id}.json", payload)
            self._tick()

    def draft(self, step_id: str) -> dict | None:
        if not (isinstance(step_id, str) and _STEP_ID_RE.fullmatch(step_id)):
            return None
        with self._locked():
            return self._read_json(f"drafts/{step_id}.json", None)

    # ---- chat ----------------------------------------------------------------

    @staticmethod
    def _chat_entry(seq: int, sender: str, text: str, kind: str | None, thread_id: str | None,
                    event_seq: int | None) -> dict:
        entry: dict[str, Any] = {
            "seq": seq, "from": sender, "text": text, "timestamp": time.time(),
            "delivered": sender != "user",
        }
        if kind is not None:
            entry["kind"] = kind
        if thread_id is not None:
            entry["thread_id"] = thread_id
        if event_seq is not None:
            entry["event_seq"] = event_seq
        return entry

    def append_chat(
        self,
        sender: str,
        text: str,
        *,
        kind: str | None = None,
        thread_id: str | None = None,
        event_seq: int | None = None,
    ) -> int:
        if sender not in _SENDERS:
            raise AppStateError("sender")
        if not _nonempty_str(text):
            raise AppStateError("text")
        with self._locked():
            chat = self._read_json("chat.json", [])
            seq = self._next_seq_value(chat)
            chat.append(self._chat_entry(seq, sender, text, kind, thread_id, event_seq))
            self._write_json("chat.json", chat)
            self._tick(seq=seq)
            return seq

    def mark_delivered(self, event_seqs: Iterable[int]) -> None:
        wanted = set(event_seqs)
        with self._locked():
            chat = self._read_json("chat.json", [])
            changed = False
            for entry in chat:
                if (
                    entry.get("from") == "user"
                    and entry.get("event_seq") in wanted
                    and not entry.get("delivered")
                ):
                    entry["delivered"] = True
                    changed = True
            if changed:
                self._write_json("chat.json", chat)
                self._tick()

    # ---- comment threads -----------------------------------------------------

    def add_comment(self, block_id: str, step: str | None, text: str, thread_id: str | None = None) -> str:
        """Add a user comment; a new thread also gets a system pointer entry in chat. Returns the thread id."""
        if not _nonempty_str(block_id):
            raise AppStateError("block_id")
        if not _nonempty_str(text):
            raise AppStateError("text")
        message = {"from": "user", "text": text, "timestamp": time.time()}
        with self._locked():
            threads = self._read_json("threads.json", [])
            if thread_id is not None:
                thread = next((t for t in threads if t["id"] == thread_id), None)
                if thread is None:
                    raise AppStateError("thread_id")
                thread["messages"].append(message)
                self._write_json("threads.json", threads)
                self._tick()
                return thread_id
            nums = [int(t["id"][2:]) for t in threads if re.fullmatch(r"t-\d+", t["id"])]
            new_id = f"t-{max(nums, default=0) + 1:04d}"
            threads.append({"id": new_id, "block_id": block_id, "step": step, "messages": [message]})
            chat = self._read_json("chat.json", [])
            seq = self._next_seq_value(chat)
            chat.append(self._chat_entry(seq, "system", text[:_POINTER_CHARS], "thread", new_id, None))
            self._write_json("threads.json", threads)
            self._write_json("chat.json", chat)
            self._tick(seq=seq)
            return new_id

    def reply(self, thread_id: str, text: str, resolve: str | None = None) -> None:
        """Agent reply inside a thread (never in chat); ``resolve`` records how the comment was handled."""
        if not _nonempty_str(text):
            raise AppStateError("text")
        if resolve is not None and resolve not in _RESOLUTIONS:
            raise AppStateError("resolve")
        with self._locked():
            threads = self._read_json("threads.json", [])
            thread = next((t for t in threads if t["id"] == thread_id), None)
            if thread is None:
                raise AppStateError("thread_id")
            thread["messages"].append({"from": "agent", "text": text, "timestamp": time.time()})
            if resolve is not None:
                thread["resolution"] = resolve
            self._write_json("threads.json", threads)
            self._tick()

    # ---- review --------------------------------------------------------------

    def set_review(self, path: os.PathLike) -> None:
        with self._locked():
            self._write_json("review.json", {"path": os.path.abspath(path)})
            self._tick()

    def review_path(self) -> Path | None:
        with self._locked():
            data = self._read_json("review.json", None)
            return Path(data["path"]) if data and data.get("path") else None

    # ---- mocks ---------------------------------------------------------------

    _MAX_MOCK_VERSION = 9999

    def _mock_versions(self) -> dict:
        data = self._read_json("mocks.json", {})
        versions = data.get("versions") if isinstance(data, dict) else None
        return versions if isinstance(versions, dict) else {}

    def _mocks_index(self) -> dict:
        nums = sorted(int(n) for n in self._mock_versions())
        return {"latest": nums[-1] if nums else None, "versions": nums}

    def _mocks_view(self) -> dict:
        versions = self._mock_versions()
        view = self._mocks_index()
        view["revisions"] = {
            str(n): entry["revision"]
            for n in view["versions"]
            if isinstance(entry := versions.get(str(n)), dict) and isinstance(entry.get("revision"), str)
        }
        return view

    def mocks_index(self) -> dict:
        """``{"latest": int | None, "versions": [int, ...]}`` for the registered mock versions."""
        with self._locked():
            return self._mocks_index()

    def _is_ui_session(self) -> bool:
        """True once the agent signalled UI work: a ux-review step or decision, or any registered mock."""
        if self._mock_versions():
            return True
        if any(d.get("stage") == "ux-review" for d in self._read_json("decisions.json", []) if isinstance(d, dict)):
            return True
        for path in (self._dir / "steps").glob("*.json"):
            try:
                step = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(step, dict) and step.get("stage") == "ux-review":
                return True
        return False

    def register_mock(self, version: int, html: str, screens: dict, changed: list) -> None:
        """Copy ``html`` to a new file under ``mocks/`` and record it; a re-registered latest is replaced.

        The first version must be 1 and each later one the latest or latest + 1; a refusal changes
        nothing. The caller validates ``screens`` and ``changed``. Each registration writes its HTML to a
        fresh file and then switches ``mocks.json`` to it in one atomic write, so a reader sees either the
        old HTML with the old metadata or the new HTML with the new metadata.
        """
        if not (isinstance(version, int) and not isinstance(version, bool)) or not 1 <= version <= self._MAX_MOCK_VERSION:
            raise AppStateError("version", "version must be a positive integer")
        with self._locked():
            latest = self._mocks_index()["latest"]
            allowed = (1,) if latest is None else (latest, latest + 1)
            if version not in allowed:
                want = " or ".join(str(n) for n in allowed)
                raise AppStateError("version", f"version must be {want}, not {version}")
            (self._dir / "mocks").mkdir(parents=True, exist_ok=True)
            versions = self._mock_versions()
            previous = versions.get(str(version))
            rel = f"mocks/v{version}-{secrets.token_hex(4)}.html"
            atomic_write(self._dir / rel, html)
            versions[str(version)] = {
                "file": rel,
                "screens": screens,
                "changed": list(changed),
                "registered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "revision": secrets.token_hex(8),
            }
            try:
                self._write_json("mocks.json", {"versions": versions})
            except BaseException:
                self._unlink_mock_file(rel)
                raise
            if isinstance(previous, dict) and isinstance(previous.get("file"), str):
                self._unlink_mock_file(previous["file"])
            self._tick()

    def _unlink_mock_file(self, rel: str) -> None:
        """Best-effort removal of a registry HTML file; a leftover is harmless because ``mocks.json`` decides what is served."""
        target = (self._dir / rel).resolve()
        if target.parent != (self._dir / "mocks").resolve():
            return
        with contextlib.suppress(OSError):
            target.unlink()

    def get_mock(self, version: int) -> dict | None:
        """``{version, html, screens, changed, registered_at, revision}`` for a registered version, else None.

        ``revision`` is opaque and changes on every registration of the version.
        """
        with self._locked():
            entry = self._mock_versions().get(str(version))
            if not isinstance(entry, dict):
                return None
            try:
                html = (self._dir / entry["file"]).read_text(encoding="utf-8")
            except (OSError, KeyError, UnicodeError):
                return None
            return {
                "version": version,
                "html": html,
                "screens": entry.get("screens"),
                "changed": entry.get("changed", []),
                "registered_at": entry.get("registered_at"),
                "revision": entry.get("revision"),
            }

    # ---- snapshot ------------------------------------------------------------

    def snapshot(self) -> dict:
        """The full app-mode view the shell renders, read under the lock so it is consistent."""
        with self._locked():
            counters = self._read_json("counters.json", {"rev": 0})
            current = self._read_json("current.json", None)
            step = None
            step_id = None
            if current:
                step_id = current["screen"]
                step = dict(self._read_json(f"steps/{step_id}.json", {}))
                step["id"] = step_id
                step["nonce"] = current["nonce"]
            step_state = "open"
            if step_id is not None and any(
                e.get("type") == "submit" and e.get("step") == step_id for e in self._events()
            ):
                step_state = "submitted"
            cur_stage = step.get("stage") if step else None
            if cur_stage not in STAGES:
                cur_stage = STAGES[0]
            idx = STAGES.index(cur_stage)
            ui_session = self._is_ui_session()
            stages = [
                {"id": s, "state": "done" if i < idx else "current" if i == idx else "todo"}
                for i, s in enumerate(STAGES)
                if ui_session or s != "ux-review"
            ]
            chat = []
            for entry in self._read_json("chat.json", []):
                out = {k: entry[k] for k in ("seq", "from", "text", "timestamp", "delivered")}
                for k in ("kind", "thread_id"):
                    if k in entry:
                        out[k] = entry[k]
                chat.append(out)
            snap: dict[str, Any] = {
                "rev": int(counters.get("rev", 0)),
                "mode": "app",
                "step": step,
                "step_state": step_state,
                "status": self._read_json("status.json", None),
                "stages": stages,
                "decisions": self._read_json("decisions.json", []),
                "chat": chat,
                "threads": self._read_json("threads.json", []),
                "review_registered": (self._dir / "review.json").exists(),
                "mocks": self._mocks_view(),
            }
            if step_id is not None:
                draft = self._read_json(f"drafts/{step_id}.json", None)
                if draft is not None:
                    snap["draft"] = draft
            return snap
