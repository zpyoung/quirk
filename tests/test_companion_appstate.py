"""Tests for the companion's on-disk app-mode session state (htmlkit.appstate).

Everything runs against a tmp_path session directory. The multi-process test spawns real
interpreters so the inter-process flock is exercised, not just the in-process path.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit.appstate import EVENT_TYPES, STAGES, AppState, AppStateError  # noqa: E402


@pytest.fixture
def st(tmp_path):
    s = AppState(tmp_path)
    s.init()
    return s


def rev(s: AppState) -> int:
    return s.snapshot()["rev"]


def decision(i: int = 1, **over) -> dict:
    d = {"id": f"d-{i}", "stage": "design", "area": "UI", "label": "Layout", "value": "grid", "status": "open"}
    d.update(over)
    return d


def test_constants():
    assert STAGES == ("context", "gray-areas", "questions", "approaches", "design", "spec", "hand-off")
    assert EVENT_TYPES == (
        "submit", "continue", "chat", "comment", "edit-request", "edit-decision", "review-export",
    )
    assert issubclass(AppStateError, ValueError)


def test_init_creates_layout_and_is_idempotent(tmp_path):
    s = AppState(tmp_path)
    s.init()
    state = tmp_path / "state"
    assert (state / "steps").is_dir() and (state / "drafts").is_dir()
    assert json.loads((state / "counters.json").read_text()) == {"rev": 0, "seq": 0}
    tok = s.token()
    s.append_event("chat", {"text": "hi"}, "c1")
    before = json.loads((state / "counters.json").read_text())
    s.init()
    AppState(tmp_path).init()
    assert s.token() == tok
    assert json.loads((state / "counters.json").read_text()) == before


def test_token_persists_across_instances_and_is_0600(tmp_path):
    s = AppState(tmp_path)
    s.init()
    tok = s.token()
    assert len(tok) >= 24
    mode = stat.S_IMODE(os.stat(tmp_path / "state" / "token").st_mode)
    assert mode == 0o600
    other = AppState(tmp_path)
    other.init()
    assert other.token() == tok
    assert stat.S_IMODE(os.stat(tmp_path / "state" / "token").st_mode) == 0o600


def test_lock_is_reentrant_and_excludes_other_instances(tmp_path):
    import fcntl

    a = AppState(tmp_path)
    a.init()
    with a.lock():
        with a.lock():
            a.append_event("chat", {}, "x")
        fd = os.open(tmp_path / "state" / "app.lock", os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
    fd = os.open(tmp_path / "state" / "app.lock", os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(fd)


def test_write_step_numbering_across_instances(tmp_path):
    a = AppState(tmp_path)
    a.init()
    r1 = a.write_step({"kind": "question", "stage": "questions"})
    assert r1["step"] == "0001-question"
    r2 = AppState(tmp_path).write_step({"kind": "choice", "stage": "design"})
    assert r2["step"] == "0002-choice"
    assert r1["nonce"] != r2["nonce"]
    assert (tmp_path / "state" / "steps" / "0002-choice.json").is_file()
    cur = a.current()
    assert cur["screen"] == "0002-choice"
    assert cur["nonce"] == r2["nonce"]
    assert cur["mode"] == "app"
    assert isinstance(cur["shown_at"], float)


def test_write_step_numbers_after_max_not_count(tmp_path):
    s = AppState(tmp_path)
    s.init()
    (tmp_path / "state" / "steps" / "0007-x.json").write_text("{}")
    assert s.write_step({"kind": "y", "stage": "design"})["step"] == "0008-y"


def test_current_none_before_any_step(st):
    assert st.current() is None


def test_rev_strictly_increases_on_every_write(st):
    seen = [rev(st)]

    def check():
        r = rev(st)
        assert r > seen[-1]
        seen.append(r)

    st.write_step({"kind": "q", "stage": "questions"}); check()
    st.set_status("thinking"); check()
    st.clear_status(); check()
    st.set_decisions([decision()]); check()
    ev = st.append_event("chat", {"text": "a"}, "c1"); check()
    st.append_chat("user", "a", event_seq=ev); check()
    st.mark_delivered([ev]); check()
    tid = st.add_comment("b1", None, "note"); check()
    st.add_comment("b1", None, "again", thread_id=tid); check()
    st.reply(tid, "ok"); check()
    st.save_draft("0001-q", {"answers": {}}); check()
    st.set_review("/tmp/x.md"); check()


def test_mark_delivered_without_change_does_not_bump_rev(st):
    before = rev(st)
    st.mark_delivered([99])
    assert rev(st) == before


def test_set_status_keeps_started_at_and_validates(st):
    s1 = st.set_status("a", stage="design", progress="1/3", interruptible=True)
    assert s1["text"] == "a" and s1["stage"] == "design" and s1["progress"] == "1/3"
    assert s1["interruptible"] is True
    s2 = st.set_status("b")
    assert s2["started_at"] == s1["started_at"]
    assert s2["interruptible"] is False
    for bad in ("1-3", "x/3", "1/", "1/3 "):
        with pytest.raises(AppStateError) as e:
            st.set_status("c", progress=bad)
        assert e.value.field == "progress"
    with pytest.raises(AppStateError) as e:
        st.set_status("c", stage="nope")
    assert e.value.field == "stage"
    assert st.snapshot()["status"]["text"] == "b"
    st.clear_status()
    assert st.snapshot()["status"] is None
    s3 = st.set_status("fresh")
    assert s3["started_at"] >= s1["started_at"]


def test_set_decisions_replaces_and_returns_rev(st):
    r = st.set_decisions([decision(1), decision(2, status="confirmed", note="n")])
    assert r == rev(st)
    assert [d["id"] for d in st.snapshot()["decisions"]] == ["d-1", "d-2"]
    st.set_decisions([decision(3)])
    assert [d["id"] for d in st.snapshot()["decisions"]] == ["d-3"]


@pytest.mark.parametrize(
    "items, field",
    [
        ([decision(1), decision(2, id="Bad_ID")], "[1].id"),
        ([decision(1), decision(1)], "[1].id"),
        ([decision(1, id="a" * 41)], "[0].id"),
        ([decision(1, stage="nope")], "[0].stage"),
        ([decision(1, area="")], "[0].area"),
        ([decision(1, label=5)], "[0].label"),
        ([decision(1, value="")], "[0].value"),
        ([decision(1, status="maybe")], "[0].status"),
        ([decision(1, note=3)], "[0].note"),
    ],
)
def test_set_decisions_invalid_keeps_previous(st, items, field):
    st.set_decisions([decision(9)])
    before = rev(st)
    with pytest.raises(AppStateError) as e:
        st.set_decisions(items)
    assert e.value.field == field
    snap = st.snapshot()
    assert [d["id"] for d in snap["decisions"]] == ["d-9"]
    assert snap["rev"] == before


def test_set_decisions_missing_key(st):
    d = decision(1)
    del d["label"]
    with pytest.raises(AppStateError) as e:
        st.set_decisions([d])
    assert e.value.field == "[0].label"


def test_append_event_dedupes_on_client_id(st):
    s1 = st.append_event("submit", {"answers": {}}, "cid-1", step="0001-q")
    before = rev(st)
    assert st.append_event("submit", {"answers": {}}, "cid-1", step="0001-q") is None
    assert rev(st) == before
    assert len(st.events_after(0)) == 1
    s2 = st.append_event("chat", {"text": "x"}, "cid-2")
    assert s2 == s1 + 1


def test_append_event_shape_and_unknown_type(st):
    seq = st.append_event("comment", {"block_id": "b"}, "cid", step="0001-q")
    (ev,) = st.events_after(0)
    assert ev["seq"] == seq and ev["type"] == "comment" and ev["step"] == "0001-q"
    assert ev["client_id"] == "cid" and ev["payload"] == {"block_id": "b"}
    assert isinstance(ev["timestamp"], float)
    with pytest.raises(AppStateError) as e:
        st.append_event("draft", {}, "cid-d")
    assert e.value.field == "type"
    with pytest.raises(AppStateError):
        st.append_event("bogus", {}, "cid-b")


def test_events_after_ordering_and_filter(st):
    seqs = [st.append_event("chat", {"n": i}, f"c{i}") for i in range(5)]
    assert seqs == sorted(seqs)
    assert [e["seq"] for e in st.events_after(0)] == seqs
    assert [e["seq"] for e in st.events_after(seqs[2])] == seqs[3:]
    assert st.events_after(seqs[-1]) == []


def test_events_file_is_app_events_not_events(st, tmp_path):
    st.append_event("chat", {}, "c")
    assert (tmp_path / "state" / "app-events").is_file()
    assert not (tmp_path / "state" / "events").exists()


def test_drafts_never_appear_in_events(st, tmp_path):
    st.save_draft("0001-q", {"answers": {"a": 1}, "comment": "wip"})
    assert st.draft("0001-q") == {"answers": {"a": 1}, "comment": "wip"}
    assert st.draft("0002-none") is None
    assert st.events_after(0) == []
    assert not (tmp_path / "state" / "app-events").exists() or (tmp_path / "state" / "app-events").read_text() == ""
    assert (tmp_path / "state" / "drafts" / "0001-q.json").is_file()


def test_chat_and_events_share_seq(st):
    e1 = st.append_event("chat", {}, "c1")
    c1 = st.append_chat("agent", "hello")
    e2 = st.append_event("chat", {}, "c2")
    c2 = st.append_chat("user", "hey", event_seq=e2)
    assert (e1, c1, e2, c2) == (1, 2, 3, 4)
    assert [e["seq"] for e in st.events_after(0)] == [1, 3]


def test_seq_survives_restart(tmp_path):
    a = AppState(tmp_path)
    a.init()
    a.append_event("chat", {}, "c1")
    b = AppState(tmp_path)
    b.init()
    assert b.append_event("chat", {}, "c2") == 2


def test_append_chat_delivered_and_validation(st):
    st.append_chat("agent", "a")
    st.append_chat("system", "s", kind="note")
    st.append_chat("user", "u")
    chat = st.snapshot()["chat"]
    assert [c["delivered"] for c in chat] == [True, True, False]
    assert chat[1]["kind"] == "note"
    assert "kind" not in chat[0]
    assert set(chat[0]) == {"seq", "from", "text", "timestamp", "delivered"}
    with pytest.raises(AppStateError) as e:
        st.append_chat("bot", "x")
    assert e.value.field == "sender"


def test_mark_delivered(st):
    e1 = st.append_event("chat", {}, "c1")
    st.append_chat("user", "one", event_seq=e1)
    e2 = st.append_event("chat", {}, "c2")
    st.append_chat("user", "two", event_seq=e2)
    st.mark_delivered([e1])
    chat = st.snapshot()["chat"]
    assert [c["delivered"] for c in chat] == [True, False]
    assert all("event_seq" not in c for c in chat)
    st.mark_delivered([e2, 12345])
    assert all(c["delivered"] for c in st.snapshot()["chat"])


def test_add_comment_new_thread_and_pointer(st):
    long_text = "x" * 200
    tid = st.add_comment("block-1", "0001-q", long_text)
    assert tid == "t-0001"
    snap = st.snapshot()
    (th,) = snap["threads"]
    assert th["id"] == tid and th["block_id"] == "block-1" and th["step"] == "0001-q"
    assert th["messages"][0]["from"] == "user" and th["messages"][0]["text"] == long_text
    assert "resolution" not in th
    (ptr,) = snap["chat"]
    assert ptr["from"] == "system" and ptr["kind"] == "thread" and ptr["thread_id"] == tid
    assert ptr["text"] == "x" * 80
    assert ptr["delivered"] is True
    assert st.add_comment("block-2", None, "short") == "t-0002"
    assert st.snapshot()["chat"][1]["text"] == "short"


def test_add_comment_to_existing_thread_makes_no_pointer(st):
    tid = st.add_comment("b", None, "first")
    assert st.add_comment("b", None, "more", thread_id=tid) == tid
    snap = st.snapshot()
    assert [m["text"] for m in snap["threads"][0]["messages"]] == ["first", "more"]
    assert len(snap["chat"]) == 1


def test_reply_and_resolution_stay_out_of_chat(st):
    tid = st.add_comment("b", None, "q?")
    st.reply(tid, "done", resolve="addressed")
    snap = st.snapshot()
    th = snap["threads"][0]
    assert th["messages"][-1]["from"] == "agent" and th["messages"][-1]["text"] == "done"
    assert th["resolution"] == "addressed"
    assert len(snap["chat"]) == 1
    st.reply(tid, "actually no", resolve="not-addressed")
    assert st.snapshot()["threads"][0]["resolution"] == "not-addressed"
    st.reply(tid, "just talking")
    assert st.snapshot()["threads"][0]["resolution"] == "not-addressed"
    with pytest.raises(AppStateError) as e:
        st.reply(tid, "x", resolve="maybe")
    assert e.value.field == "resolve"


def test_unknown_thread_errors(st):
    with pytest.raises(AppStateError) as e:
        st.reply("t-0042", "x")
    assert e.value.field == "thread_id"
    with pytest.raises(AppStateError) as e:
        st.add_comment("b", None, "x", thread_id="t-0042")
    assert e.value.field == "thread_id"


def test_review_path(st, tmp_path):
    assert st.review_path() is None
    assert st.snapshot()["review_registered"] is False
    st.set_review(tmp_path / "r.md")
    assert st.review_path() == Path(os.path.abspath(tmp_path / "r.md"))
    assert st.review_path().is_absolute()
    assert st.snapshot()["review_registered"] is True


def test_snapshot_empty(st):
    snap = st.snapshot()
    assert snap == {
        "rev": 0, "mode": "app", "step": None, "step_state": "open", "status": None,
        "stages": [{"id": s, "state": "current" if s == "context" else "todo"} for s in STAGES],
        "decisions": [], "chat": [], "threads": [], "review_registered": False,
    }


def test_snapshot_step_stages_and_state(st):
    r = st.write_step({"kind": "choice", "stage": "approaches", "title": "Pick"})
    snap = st.snapshot()
    assert snap["step"]["id"] == r["step"] and snap["step"]["nonce"] == r["nonce"]
    assert snap["step"]["title"] == "Pick" and snap["step"]["kind"] == "choice"
    assert snap["mode"] == "app"
    states = {s["id"]: s["state"] for s in snap["stages"]}
    assert [s["id"] for s in snap["stages"]] == list(STAGES)
    assert states["context"] == states["gray-areas"] == states["questions"] == "done"
    assert states["approaches"] == "current"
    assert states["design"] == states["spec"] == states["hand-off"] == "todo"
    assert snap["step_state"] == "open"
    assert "draft" not in snap

    st.append_event("submit", {"answers": {}}, "s-other", step="0099-other")
    assert st.snapshot()["step_state"] == "open"
    st.append_event("submit", {"answers": {}}, "s-1", step=r["step"])
    assert st.snapshot()["step_state"] == "submitted"

    r2 = st.write_step({"kind": "next", "stage": "design"})
    assert st.snapshot()["step_state"] == "open"
    assert st.snapshot()["step"]["id"] == r2["step"]


def test_snapshot_draft_for_current_step_only(st):
    st.save_draft("0001-q", {"answers": {"a": 1}})
    r = st.write_step({"kind": "q", "stage": "questions"})
    assert r["step"] == "0001-q"
    assert st.snapshot()["draft"] == {"answers": {"a": 1}}
    st.write_step({"kind": "q", "stage": "questions"})
    assert "draft" not in st.snapshot()


def test_write_step_validates(st):
    with pytest.raises(AppStateError) as e:
        st.write_step({"stage": "design"})
    assert e.value.field == "kind"
    with pytest.raises(AppStateError) as e:
        st.write_step({"kind": "q", "stage": "nope"})
    assert e.value.field == "stage"
    assert st.current() is None


WORKER = """
import sys
sys.path.insert(0, sys.argv[1])
from htmlkit.appstate import AppState
s = AppState(sys.argv[2])
for i in range(25):
    s.append_event("chat", {"n": i}, f"p{sys.argv[3]}-{i}")
"""


def test_multiprocess_appends_are_serialised(tmp_path):
    AppState(tmp_path).init()
    procs = [
        subprocess.Popen([sys.executable, "-c", WORKER, str(SKILL / "scripts"), str(tmp_path), str(n)])
        for n in range(4)
    ]
    for p in procs:
        assert p.wait(timeout=120) == 0
    s = AppState(tmp_path)
    seqs = [e["seq"] for e in s.events_after(0)]
    assert seqs == list(range(1, 101))
    assert s.snapshot()["rev"] >= 100
    lines = (tmp_path / "state" / "app-events").read_text().splitlines()
    assert len(lines) == 100 and all(json.loads(ln) for ln in lines)
