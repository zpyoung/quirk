import contextlib
import io
import json
from pathlib import Path

import pytest

import prepare_diff as m

ME = {"id": 1, "username": "me", "emails": ["me@example.com"]}
OTHER = {"username": "other", "email": "other@example.com"}
MINE_BY_EMAIL = {"username": None, "email": "ME@example.com"}
MINE_BY_LOGIN = {"username": "Me", "email": None}


@pytest.mark.parametrize("seat, commits, expected", [
    ("author", [MINE_BY_LOGIN], False),
    ("author", [MINE_BY_LOGIN, OTHER], True),
    ("author", [MINE_BY_EMAIL, OTHER], True),
    ("reviewer", [OTHER], False),
    ("reviewer", [OTHER, MINE_BY_EMAIL], True),
    ("reviewer", [OTHER, MINE_BY_LOGIN], True),
    ("author", [], False),
    ("author", None, None),
])
def test_mixed_authorship_truth_table(seat, commits, expected):
    assert m.mixed_authorship(seat, ME, commits) is expected


def _run_main(tmp_path, monkeypatch, commits, extra=(), author="other"):
    out = Path(tmp_path) / "ctx.json"
    monkeypatch.setattr(m, "get_origin_url", lambda cwd=".": "git@x:grp/proj.git")
    monkeypatch.setattr(m, "detect_target_branch", lambda cwd=".": "main")
    monkeypatch.setattr(m, "change_diff", lambda forge, number, cwd=".", metadata=None: (
        "diff --git a/z b/z\n--- a/z\n+++ b/z\n@@ -1 +1 @@\n-x\n+y\n",
        {"base": "b" * 40, "start": "c" * 40, "head": "a" * 40},
        {"number": 42, "title": "t", "description": "d", "source_branch": "feature"}))
    monkeypatch.setattr(m, "change_details", lambda forge, number: {
        "number": 42, "open": True, "state": "opened", "author_id": 1 if author == "me" else 9,
        "author_username": author, "source_branch": "feature", "target_branch": "main",
        "sha": "a" * 40, "base_sha": "b" * 40, "start_sha": "c" * 40,
        "is_fork": False, "author_trusted": None})
    monkeypatch.setattr(m, "current_user", lambda forge: dict(ME))
    monkeypatch.setattr(m, "commit_authors", lambda forge, number: (
        commits(forge, number) if callable(commits) else commits))
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        rc = m.main(["--forge", "gitlab", "--change", "42", "--out", str(out)] + list(extra))
    ctx = json.loads(out.read_text()) if out.exists() else None
    err = json.loads(stderr.getvalue()) if stderr.getvalue().strip() else None
    return rc, ctx, err


def test_unmixed_change_records_detected_seat_and_trust_fields(tmp_path, monkeypatch):
    rc, ctx, _ = _run_main(tmp_path, monkeypatch, [OTHER])
    assert rc == 0
    change = ctx["change"]
    assert ctx["seat"] == "reviewer"
    assert change["mixed_authorship"] is False and change["seat_source"] == "detected"
    assert change["is_fork"] is False and change["author_trusted"] is None


def test_author_seat_is_trusted(tmp_path, monkeypatch):
    rc, ctx, _ = _run_main(tmp_path, monkeypatch, [MINE_BY_LOGIN], author="me")
    assert rc == 0 and ctx["seat"] == "author" and ctx["change"]["author_trusted"] is True


def test_mixed_authorship_without_seat_stops_and_names_the_flag(tmp_path, monkeypatch):
    rc, ctx, err = _run_main(tmp_path, monkeypatch, [OTHER, MINE_BY_EMAIL])
    assert rc != 0 and ctx is None
    assert err["seat"] == "ambiguous" and "--seat" in err["error"]["message"]


@pytest.mark.parametrize("choice", ["author", "reviewer"])
def test_mixed_authorship_with_seat_uses_the_choice(tmp_path, monkeypatch, choice):
    rc, ctx, _ = _run_main(tmp_path, monkeypatch, [OTHER, MINE_BY_EMAIL], extra=["--seat", choice])
    assert rc == 0 and ctx["seat"] == choice
    assert ctx["change"]["seat"] == choice and ctx["change"]["seat_source"] == "chosen"


def test_seat_flag_is_rejected_when_authorship_is_not_mixed(tmp_path, monkeypatch):
    rc, ctx, err = _run_main(tmp_path, monkeypatch, [OTHER], extra=["--seat", "author"])
    assert rc != 0 and ctx is None and "--seat" in err["error"]["message"]


def test_unresolvable_commit_authors_skip_the_check(tmp_path, monkeypatch):
    def failing_authors(forge, number):
        forge.last_error = "HTTP 403"

    rc, ctx, _ = _run_main(tmp_path, monkeypatch, failing_authors)
    assert rc == 0 and ctx["change"]["mixed_authorship"] is None
    note = ctx["change"]["mixed_authorship_note"]
    assert "commit authors unavailable" in note and "HTTP 403" in note


def test_resolved_commit_authors_leave_no_note(tmp_path, monkeypatch):
    rc, ctx, _ = _run_main(tmp_path, monkeypatch, [OTHER])
    assert rc == 0 and "mixed_authorship_note" not in ctx["change"]
