"""Tests for the companion's chat and comment-thread server side: say, reply and the chat/comment events."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_companion_app_server import QUESTIONS, App, run, start_app, stop_app

EVENTS = "/_quirk/app/event"


@pytest.fixture
def session(tmp_path: Path) -> Path:
    return tmp_path / ".quirk" / "brainstorm" / "chat"


@pytest.fixture
def app(tmp_path: Path, session: Path):
    srv = start_app(tmp_path / "root", session)
    try:
        yield srv
    finally:
        stop_app(srv)


@pytest.fixture
def offline(tmp_path: Path) -> Path:
    """An app-mode session with no server running."""
    session = tmp_path / "offline"
    (session / "state").mkdir(parents=True)
    (session / "state" / "mode.json").write_text(json.dumps({"mode": "app"}))
    return session


def chat_of(snap: dict) -> list[dict]:
    return snap["chat"]


def event_log(app: App) -> list[dict]:
    path = app.state / "app-events"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---- say --------------------------------------------------------------------------------------


def test_say_defaults_to_the_agent_and_works_without_a_server(offline: Path) -> None:
    rc, out, _ = run("say", offline, "--text", "hello")
    assert rc == 0 and set(out) == {"chat"} and isinstance(out["chat"], int)
    rc, snap, _ = run("snapshot", offline)
    (entry,) = snap["chat"]
    assert entry["seq"] == out["chat"] and entry["from"] == "agent" and entry["text"] == "hello"
    assert entry["delivered"] is True


def test_say_from_user_records_a_user_message(offline: Path) -> None:
    rc, out, _ = run("say", offline, "--text", "typed in terminal", "--from", "user")
    assert rc == 0
    _, snap, _ = run("snapshot", offline)
    (entry,) = snap["chat"]
    assert entry["from"] == "user" and entry["seq"] == out["chat"]


def test_say_reads_text_from_a_file(offline: Path, tmp_path: Path) -> None:
    f = tmp_path / "msg.txt"
    f.write_text("line one\nline two", encoding="utf-8")
    rc, out, _ = run("say", offline, "--file", f)
    assert rc == 0
    _, snap, _ = run("snapshot", offline)
    assert snap["chat"][0]["text"] == "line one\nline two"


def test_say_while_the_server_runs_shows_in_the_http_snapshot(app: App) -> None:
    out = app.cli("say", app.session, "--text", "hi there")
    (entry,) = chat_of(app.snapshot())
    assert entry["seq"] == out["chat"] and entry["from"] == "agent"


@pytest.mark.parametrize("text", ["", "   \n\t"])
def test_say_rejects_empty_or_blank_text(offline: Path, text: str) -> None:
    rc, out, _ = run("say", offline, "--text", text)
    assert rc == 2 and "error" in out
    assert run("snapshot", offline)[1]["chat"] == []


def test_say_rejects_an_unreadable_file(offline: Path, tmp_path: Path) -> None:
    rc, out, _ = run("say", offline, "--file", tmp_path / "missing.txt")
    assert rc == 2 and "error" in out
    binary = tmp_path / "bin.dat"
    binary.write_bytes(b"\xff\xfe\x00bad")
    rc, out, _ = run("say", offline, "--file", binary)
    assert rc == 2 and "error" in out


def test_say_rejects_an_empty_file(offline: Path, tmp_path: Path) -> None:
    f = tmp_path / "empty.txt"
    f.write_text("  \n")
    rc, out, _ = run("say", offline, "--file", f)
    assert rc == 2 and "error" in out


def test_say_needs_exactly_one_of_text_and_file(offline: Path, tmp_path: Path) -> None:
    f = tmp_path / "m.txt"
    f.write_text("x")
    rc, out, _ = run("say", offline)
    assert rc == 2 and "error" in out
    rc, out, _ = run("say", offline, "--text", "a", "--file", f)
    assert rc == 2 and "error" in out
    assert run("snapshot", offline)[1]["chat"] == []


def test_say_rejects_an_unknown_sender(offline: Path) -> None:
    rc, out, _ = run("say", offline, "--text", "a", "--from", "system")
    assert rc == 2 and "error" in out


def test_say_and_reply_refuse_a_screen_session(tmp_path: Path) -> None:
    session = tmp_path / "screen"
    (session / "state").mkdir(parents=True)
    for args in (("say", session, "--text", "x"), ("reply", session, "t-0001", "--text", "x")):
        rc, out, _ = run(*args)
        assert rc == 2 and out == {"error": "session is not in app mode"}


# ---- reply ------------------------------------------------------------------------------------


def open_thread(app: App, text: str = "why this?", block_id: str = "b1", **kw) -> str:
    status, _ = app.event("comment", {"block_id": block_id, "text": text}, **kw)
    assert status == 204
    return app.snapshot()["threads"][-1]["id"]


def test_reply_adds_an_agent_message_to_the_thread_not_to_chat(app: App) -> None:
    tid = open_thread(app)
    chat_before = chat_of(app.snapshot())
    out = app.cli("reply", app.session, tid, "--text", "because")
    assert out == {"thread": tid}
    snap = app.snapshot()
    (thread,) = snap["threads"]
    assert [(m["from"], m["text"]) for m in thread["messages"]] == [("user", "why this?"), ("agent", "because")]
    assert "resolution" not in thread
    assert chat_of(snap) == chat_before
    assert not any(e["from"] == "agent" for e in chat_of(snap))


@pytest.mark.parametrize("resolution", ["addressed", "not-addressed"])
def test_reply_resolve_records_the_resolution(app: App, resolution: str) -> None:
    tid = open_thread(app)
    app.cli("reply", app.session, tid, "--text", "done", "--resolve", resolution)
    assert app.snapshot()["threads"][0]["resolution"] == resolution


def test_reply_to_an_unknown_thread_exits_2_naming_the_field(offline: Path) -> None:
    rc, out, _ = run("reply", offline, "t-9999", "--text", "x")
    assert rc == 2 and out["field"] == "thread_id" and "error" in out


def test_reply_rejects_empty_text_and_a_bad_resolve(app: App) -> None:
    tid = open_thread(app)
    rc, out, _ = run("reply", app.session, tid, "--text", "  ")
    assert rc == 2 and "error" in out
    rc, out, _ = run("reply", app.session, tid, "--text", "x", "--resolve", "maybe")
    assert rc == 2 and "error" in out
    assert len(app.snapshot()["threads"][0]["messages"]) == 1


# ---- chat event -------------------------------------------------------------------------------


def test_chat_event_requires_the_token(app: App) -> None:
    assert app.event("chat", {"text": "hi"}, token=None)[0] == 403
    assert app.event("chat", {"text": "hi"}, token="wrong")[0] == 403
    assert chat_of(app.snapshot()) == []


def test_chat_event_needs_no_nonce_and_works_before_any_step(app: App) -> None:
    status, data = app.event("chat", {"text": "hello"})
    assert (status, data) == (204, b"")
    (entry,) = chat_of(app.snapshot())
    assert entry["from"] == "user" and entry["text"] == "hello" and entry["delivered"] is False
    (ev,) = event_log(app)
    assert ev["type"] == "chat" and ev["step"] is None and ev["payload"] == {"text": "hello"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"text": ""},
        {"text": "   "},
        {"text": 5},
        {"text": None},
        {"text": ["a"]},
        {"text": "x" * 4001},
        {"text": "ok", "extra": 1},
    ],
)
def test_chat_event_rejects_bad_payloads_and_writes_nothing(app: App, payload: dict) -> None:
    status, data = app.event("chat", payload)
    assert status == 400 and "error" in json.loads(data)
    assert chat_of(app.snapshot()) == [] and event_log(app) == []


def test_chat_event_accepts_the_length_limit(app: App) -> None:
    assert app.event("chat", {"text": "x" * 4000})[0] == 204


def test_chat_event_records_the_current_step_and_next_marks_it_delivered(app: App) -> None:
    step = app.step(QUESTIONS)
    assert app.event("chat", {"text": "question for you"}, client_id="c-chat")[0] == 204
    snap = app.snapshot()
    (entry,) = chat_of(snap)
    assert entry["delivered"] is False
    out = app.next()
    (ev,) = out["events"]
    assert ev["type"] == "chat" and ev["step"] == step["step"] and ev["payload"] == {"text": "question for you"}
    (entry,) = chat_of(app.snapshot())
    assert entry["delivered"] is True and entry["seq"] != ev["seq"]


def test_next_only_delivers_chat_it_returned(app: App) -> None:
    app.event("chat", {"text": "one"})
    first = app.next()
    app.event("chat", {"text": "two"})
    flags = {e["text"]: e["delivered"] for e in chat_of(app.snapshot())}
    assert flags == {"one": True, "two": False}
    app.next("--after", first["cursor"])
    assert all(e["delivered"] for e in chat_of(app.snapshot()))


def test_chat_event_with_a_duplicate_client_id_writes_nothing(app: App) -> None:
    assert app.event("chat", {"text": "once"}, client_id="dup")[0] == 204
    status, data = app.event("chat", {"text": "once"}, client_id="dup")
    assert status == 200 and json.loads(data) == {"duplicate": True}
    assert len(chat_of(app.snapshot())) == 1 and len(event_log(app)) == 1


def test_chat_event_does_not_touch_a_draft_or_step_state(app: App) -> None:
    app.step(QUESTIONS)
    app.event("chat", {"text": "hi"})
    assert app.snapshot()["step_state"] == "open"


# ---- comment event ----------------------------------------------------------------------------


def test_comment_event_requires_the_token(app: App) -> None:
    assert app.event("comment", {"block_id": "b1", "text": "x"}, token=None)[0] == 403
    assert app.snapshot()["threads"] == []


def test_a_new_comment_opens_a_thread_with_a_system_pointer_and_a_resolved_event(app: App) -> None:
    step = app.step(QUESTIONS)
    long_text = "c" * 200
    status, data = app.event("comment", {"block_id": "design:s1", "text": long_text}, client_id="c-1")
    assert (status, data) == (204, b"")
    snap = app.snapshot()
    (thread,) = snap["threads"]
    assert thread["block_id"] == "design:s1" and thread["step"] == step["step"]
    assert [(m["from"], m["text"]) for m in thread["messages"]] == [("user", long_text)]
    (pointer,) = chat_of(snap)
    assert pointer["from"] == "system" and pointer["kind"] == "thread" and pointer["thread_id"] == thread["id"]
    assert pointer["text"] == "c" * 80
    (ev,) = event_log(app)
    assert ev["type"] == "comment" and ev["step"] == step["step"] and ev["client_id"] == "c-1"
    assert ev["payload"] == {"block_id": "design:s1", "text": long_text, "thread_id": thread["id"]}
    (returned,) = app.next()["events"]
    assert returned["payload"]["thread_id"] == thread["id"]


def test_a_comment_before_any_step_has_a_null_step(app: App) -> None:
    assert app.event("comment", {"block_id": "b", "text": "hi"})[0] == 204
    assert app.snapshot()["threads"][0]["step"] is None
    assert event_log(app)[0]["step"] is None


def test_a_follow_up_comment_joins_the_thread_without_a_new_pointer(app: App) -> None:
    tid = open_thread(app, "first")
    status, _ = app.event("comment", {"block_id": "b1", "text": "second", "thread_id": tid})
    assert status == 204
    snap = app.snapshot()
    (thread,) = snap["threads"]
    assert [m["text"] for m in thread["messages"]] == ["first", "second"]
    assert len(chat_of(snap)) == 1
    follow = event_log(app)[-1]
    assert follow["payload"] == {"block_id": "b1", "text": "second", "thread_id": tid}


def test_a_comment_naming_an_unknown_thread_is_400_and_writes_nothing(app: App) -> None:
    status, data = app.event("comment", {"block_id": "b1", "text": "x", "thread_id": "t-0042"})
    assert status == 400 and "error" in json.loads(data)
    snap = app.snapshot()
    assert snap["threads"] == [] and chat_of(snap) == [] and event_log(app) == []


@pytest.mark.parametrize("block_id", ["", "has space", "semi;colon", "x" * 201, "ünï", "a\nb"])
def test_a_comment_with_a_bad_block_id_is_400(app: App, block_id: str) -> None:
    status, _ = app.event("comment", {"block_id": block_id, "text": "x"})
    assert status == 400
    assert app.snapshot()["threads"] == [] and event_log(app) == []


@pytest.mark.parametrize("block_id", ["a", "design:s1", "a/b_c.d-e", "x" * 200])
def test_a_comment_accepts_valid_block_ids(app: App, block_id: str) -> None:
    assert app.event("comment", {"block_id": block_id, "text": "x"})[0] == 204


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"text": "x"},
        {"block_id": "b"},
        {"block_id": 1, "text": "x"},
        {"block_id": ["b"], "text": "x"},
        {"block_id": None, "text": "x"},
        {"block_id": {"a": 1}, "text": "x"},
        {"block_id": "b", "text": 1},
        {"block_id": "b", "text": ""},
        {"block_id": "b", "text": " "},
        {"block_id": "b", "text": "x" * 4001},
        {"block_id": "b", "text": "x", "thread_id": 1},
        {"block_id": "b", "text": "x", "thread_id": ["t-0001"]},
        {"block_id": "b", "text": "x", "thread_id": {"a": 1}},
        {"block_id": "b", "text": "x", "thread_id": None},
        {"block_id": "b", "text": "x", "extra": 1},
    ],
)
def test_a_comment_with_wrong_types_or_keys_is_400_never_a_crash(app: App, payload: dict) -> None:
    status, data = app.event("comment", payload)
    assert status == 400 and "error" in json.loads(data)
    assert app.snapshot()["threads"] == [] and event_log(app) == []
    assert app.event("chat", {"text": "still alive"})[0] == 204


def test_a_comment_with_a_duplicate_client_id_writes_nothing(app: App) -> None:
    assert app.event("comment", {"block_id": "b", "text": "once"}, client_id="dup")[0] == 204
    status, data = app.event("comment", {"block_id": "b", "text": "once"}, client_id="dup")
    assert status == 200 and json.loads(data) == {"duplicate": True}
    snap = app.snapshot()
    assert len(snap["threads"]) == 1 and len(snap["threads"][0]["messages"]) == 1
    assert len(chat_of(snap)) == 1 and len(event_log(app)) == 1


def test_a_duplicate_follow_up_comment_adds_no_message(app: App) -> None:
    tid = open_thread(app)
    body = {"block_id": "b1", "text": "more", "thread_id": tid}
    assert app.event("comment", body, client_id="f-1")[0] == 204
    assert app.event("comment", body, client_id="f-1")[0] == 200
    assert len(app.snapshot()["threads"][0]["messages"]) == 2


def test_comments_survive_a_server_restart(tmp_path: Path, session: Path) -> None:
    first = start_app(tmp_path / "root", session)
    try:
        first.event("comment", {"block_id": "b", "text": "kept"})
        first.event("chat", {"text": "kept too"})
    finally:
        stop_app(first)
    second = start_app(tmp_path / "root", session)
    try:
        snap = second.snapshot()
        assert snap["threads"][0]["messages"][0]["text"] == "kept"
        assert [e["text"] for e in snap["chat"] if e["from"] == "user"] == ["kept too"]
    finally:
        stop_app(second)
