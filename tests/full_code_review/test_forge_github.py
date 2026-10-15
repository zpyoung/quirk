import contextlib
import io
import json

import pytest

import post_reviewer_review as reviewer
import prepare_diff
from forge import ForgeError
from forge.github import GitHubForge, hunk_lines

from .fakes import (BASE_TIP, DIFF, HEAD, HOST, MERGE_BASE, NUMBER, PROJECT, FakeGitHub,
                    forge)


# ---- read path --------------------------------------------------------------

def test_change_records_map_pull_files_onto_change_records_with_merge_base_refs():
    data = forge(FakeGitHub()).change_records(NUMBER)
    assert data["refs"] == {"base": MERGE_BASE, "start": MERGE_BASE, "head": HEAD}
    assert data["number"] == NUMBER and data["author"] == "author" and data["source_branch"] == "feature"
    assert data["reported_count"] == 3 and data["overflow"] is None
    a, img, renamed = data["records"]
    assert a["new_path"] == "a.py" and a["diff"].startswith("@@") and not a["too_large"]
    # a missing patch asks prepare_diff to recover the file from local git
    assert img["diff"] == "" and img["new_file"] is True and img["too_large"] is False
    assert renamed["old_path"] == "old.py" and renamed["renamed_file"] is True


def test_missing_patch_on_a_changed_file_is_flagged_for_git_recovery():
    fake = FakeGitHub()
    fake.files = [{"filename": "big.json", "status": "modified", "changes": 5000}]
    record = forge(fake).change_records(NUMBER)["records"][0]
    assert record["diff"] == "" and record["too_large"] is True


def test_file_list_paginates_past_one_hundred():
    fake = FakeGitHub()
    fake.files = [{"filename": "f%d.py" % i, "status": "added", "patch": "@@ -0,0 +1 @@\n+x", "changes": 1}
                  for i in range(150)]
    assert len(forge(fake).change_records(NUMBER)["records"]) == 150


@pytest.mark.parametrize("change, expected", [
    ({}, (False, True)),
    ({"head": {"sha": HEAD, "ref": "feature", "repo": {"full_name": "fork/r"}}}, (True, True)),
    ({"head": {"sha": HEAD, "ref": "feature", "repo": None}}, (True, True)),
    ({"author_association": "CONTRIBUTOR"}, (False, False)),
])
def test_change_details_map_fork_and_trust(change, expected):
    fake = FakeGitHub()
    fake.pr.update(change)
    details = forge(fake).change_details(NUMBER)
    assert (details["is_fork"], details["author_trusted"]) == expected
    assert details["open"] is True and details["base_sha"] == details["start_sha"] == MERGE_BASE


def test_merged_pull_request_is_not_open():
    fake = FakeGitHub()
    fake.pr.update({"state": "closed", "merged": True})
    assert forge(fake).change_details(NUMBER)["open"] is False


def test_identity_commit_authors_and_branch_lookup():
    fake = FakeGitHub()
    gh = forge(fake)
    assert gh.current_user() == {"id": 2, "username": "reviewer", "emails": []}
    assert gh.commit_authors(NUMBER) == [{"username": "author", "email": "a@x.io"}]
    assert gh.find_change_for_branch("feature") == NUMBER
    assert gh.find_change_for_branch("other") is None
    assert gh.change_label(NUMBER) == "PR #7"
    assert gh.head_refspec(NUMBER) == "refs/pull/7/head"


def test_clone_command_targets_the_host():
    cmd, env = GitHubForge("ghe.example.com", PROJECT).clone_command("/tmp/x")
    assert cmd[:4] == ["gh", "repo", "clone", "ghe.example.com/o/r"]
    assert "--depth=1" in cmd and env["GH_HOST"] == "ghe.example.com"
    assert GitHubForge(HOST, PROJECT).clone_command("/tmp/x")[0][3] == "o/r"


def test_list_threads_normalizes_to_discussion_dicts():
    fake = FakeGitHub()
    fake.threads = [{"id": "PRRT_1", "isResolved": False, "path": "a.py", "line": 2, "comments": {"nodes": [
        {"databaseId": 41, "body": "hm", "url": "https://u", "author": {"login": "bob", "databaseId": 9}}]}}]
    thread = forge(fake).list_threads(NUMBER)[0]
    assert thread["id"] == "PRRT_1" and thread["resolved"] is False
    note = thread["notes"][0]
    assert note == {"id": 41, "body": "hm", "author": {"id": 9, "username": "bob"}, "web_url": "https://u",
                    "position": {"new_path": "a.py", "new_line": 2}, "resolved": False}


def test_file_list_past_the_page_cap_is_flagged_for_git_recovery_instead_of_failing():
    fake = FakeGitHub()
    fake.files = [{"filename": "f%d.py" % i, "status": "added", "patch": "@@ -0,0 +1 @@\n+x", "changes": 1}
                  for i in range(3050)]
    fake.pr["changed_files"] = 3050
    data = forge(fake).change_records(NUMBER)
    assert len(data["records"]) == 3000 and data["overflow"] is True and data["reported_count"] == 3050


def test_commit_authors_at_the_listing_cap_are_unknown():
    fake = FakeGitHub()
    commit = {"author": {"login": "author"}, "commit": {"author": {"email": "a@x.io"}}}
    fake.commits = [commit] * 249
    assert len(forge(fake).commit_authors(NUMBER)) == 249
    fake.commits = [commit] * 250
    assert forge(fake).commit_authors(NUMBER) is None


def test_changed_paths_returns_old_and_new_names_and_rejects_a_capped_listing():
    fake = FakeGitHub()
    fake.compare_files = [{"filename": "new.py", "previous_filename": "old.py"}]
    assert forge(fake).changed_paths(BASE_TIP, HEAD) == {"new.py", "old.py"}
    fake.compare_files = [{"filename": "f%d.py" % i} for i in range(300)]
    with pytest.raises(ForgeError, match="at most 300 files"):
        forge(fake).changed_paths(BASE_TIP, HEAD)


def test_list_threads_rejects_a_thread_with_unread_comments():
    fake = FakeGitHub()
    fake.threads = [{"id": "PRRT_1", "isResolved": False, "path": "a.py", "line": 2,
                     "comments": {"pageInfo": {"hasNextPage": True}, "nodes": []}}]
    with pytest.raises(ForgeError, match="more than 100 comments"):
        forge(fake).list_threads(NUMBER)


def test_branch_lookup_url_encodes_the_branch_name():
    fake = FakeGitHub()
    forge(fake).find_change_for_branch("fix&x#y/z")
    endpoint = fake.calls[-1][1]
    assert endpoint == "repos/o/r/pulls?head=o:fix%26x%23y%2Fz&state=open"


def test_failed_identity_and_detail_reads_record_the_cause_and_clear_it_on_success():
    class Failing(FakeGitHub):
        def __call__(self, host, method, endpoint, payload=None, timeout=120):
            if self.broken:
                raise ForgeError("GitHub GET %s failed: HTTP 401" % endpoint, "auth")
            return super().__call__(host, method, endpoint, payload, timeout)

    fake = Failing()
    fake.broken = True
    gh = forge(fake)
    assert gh.current_user() is None and "HTTP 401" in gh.last_error
    assert gh.change_details(NUMBER) is None and "HTTP 401" in gh.last_error
    fake.broken = False
    assert gh.change_details(NUMBER) is not None and gh.last_error is None


def test_hunk_lines_read_header_like_content_inside_a_hunk_as_content():
    diff = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,3 @@\n one\n"
            "-- removed dashes\n+++ added pluses\n three\n"
            "diff --git a/b.py b/b.py\n--- a/b.py\n+++ b/b.py\n@@ -1 +1,2 @@\n six\n+seven\n")
    new, old = hunk_lines(diff, "a.py")
    assert new == {1, 2, 3} and old == {1, 2, 3}
    assert hunk_lines(diff, "b.py") == ({1, 2}, {1})


def test_hunk_lines_anchor_old_side_lines_of_a_deleted_file():
    diff = "diff --git a/gone.py b/gone.py\ndeleted file mode 100644\n--- a/gone.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-x\n-y\n"
    assert hunk_lines(diff, "gone.py") == (set(), {1, 2})
    assert forge(FakeGitHub()).inline_target({}, "gone.py", "gone.py", 2, diff, side="old") == {
        "path": "gone.py", "line": 2, "side": "LEFT"}


def test_hunk_lines_and_inline_target():
    new, old = hunk_lines(DIFF, "a.py")
    assert new == {1, 2, 3, 4} and old == {1, 2, 3}
    gh = forge(FakeGitHub())
    assert gh.inline_target({}, "a.py", "a.py", 2, DIFF) == {"path": "a.py", "line": 2, "side": "RIGHT"}
    assert gh.inline_target({}, "a.py", "a.py", 40, DIFF) is None
    assert gh.inline_target({}, "b.py", "b.py", 6, DIFF, side="old") == {"path": "b.py", "line": 6, "side": "LEFT"}


def test_author_inline_and_overview_posts():
    fake = FakeGitHub()
    gh = forge(fake)
    receipt = gh.post_inline(NUMBER, "body", {"path": "a.py", "line": 2, "side": "RIGHT"}, HEAD)
    method, endpoint, payload = fake.calls[-1]
    assert (method, endpoint) == ("POST", "repos/o/r/pulls/7/comments")
    assert payload == {"path": "a.py", "line": 2, "side": "RIGHT", "body": "body", "commit_id": HEAD}
    assert receipt["published"] is True and receipt["url"].endswith("#discussion_r%d" % receipt["note_id"])
    assert gh.post_overview(NUMBER, "summary")["url"].startswith("https://github.com/o/r/pull/7#issuecomment")


def test_prepare_diff_reviews_a_github_pull_request(tmp_path, monkeypatch):
    fake = FakeGitHub()
    out = tmp_path / "ctx.json"
    monkeypatch.setattr(prepare_diff, "get_origin_url", lambda cwd=".": "git@github.com:o/r.git")
    monkeypatch.setattr(prepare_diff, "detect_target_branch", lambda cwd=".": "main")
    monkeypatch.setattr(prepare_diff, "make_forge",
                        lambda name, host, project, run=None: GitHubForge(host, project, api_call=fake))
    monkeypatch.setattr(prepare_diff, "_git_diff_path",
                        lambda *a, **k: ("diff --git a/img.png b/img.png\nnew file mode 100644\n"
                                         "Binary files /dev/null and b/img.png differ\n"))
    with contextlib.redirect_stdout(io.StringIO()):
        assert prepare_diff.main(["--change", "7", "--out", str(out)]) == 0
    ctx = json.loads(out.read_text())
    assert ctx["forge"] == "github" and ctx["seat"] == "reviewer" and ctx["source"] == "github"
    assert ctx["refs"] == {"base": MERGE_BASE, "start": MERGE_BASE, "head": HEAD}
    assert ctx["change"]["label"] == "PR #7" and ctx["change"]["author_trusted"] is True
    assert ctx["change"]["mixed_authorship"] is False
    assert "img.png" in ctx["not_text_reviewable"]


# ---- reviewer seat ------------------------------------------------------------

def report():
    return {
        "schema_version": 1,
        "meta": {"target": "change", "forge": "github", "number": NUMBER, "project": PROJECT,
                 "head_sha": HEAD, "title": "Review", "verdict": "Fix first", "seat": "reviewer"},
        "run": {"dimensions_run": ["correctness"], "source_access": "borrowed-worktree"},
        "findings": [
            {"severity": "Must fix", "dimension": "correctness", "file": "a.py", "line": "2",
             "title": "Bug", "body_md": "Body.", "impact": "Breaks.", "fix_md": "Fix."},
            {"severity": "Should fix", "dimension": "db", "file": "b.py", "line": "40",
             "title": "Off-diff", "body_md": "Body.", "impact": "Slow.", "fix_md": "Index."},
        ],
    }


def context():
    return {"forge": "github", "seat": "reviewer", "refs": {"base": MERGE_BASE, "start": MERGE_BASE, "head": HEAD},
            "change": {"number": NUMBER, "host": HOST, "project": PROJECT, "sha": HEAD,
                       "current_user_id": 2, "current_username": "reviewer"},
            "diff": DIFF}


def decisions(value):
    return {"schema": 1, "seat": "reviewer", "head_sha": HEAD, "target": "PR #7",
            "report_sha256": reviewer._report_digest(value), "decisions": [
                {"id": "F1", "slot": "fix", "disposition": "Blocking", "note": ""},
                {"id": "F2", "slot": "later", "disposition": "Non-blocking", "note": ""}]}


def _paths(tmp_path, value=None, ctx=None):
    value = value or report()
    paths = {}
    for name, data in (("report", value), ("decisions", decisions(value)), ("context", ctx or context())):
        paths[name] = tmp_path / ("%s.json" % name)
        paths[name].write_text(json.dumps(data))
    paths["staged"] = tmp_path / "staged.json"
    return paths


def _invoke(func, args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = func(args)
    return rc, json.loads(buf.getvalue())


def _stage(paths, allow=False):
    args = type("Args", (), {"report": str(paths["report"]), "decisions": str(paths["decisions"]),
                             "context": str(paths["context"]), "out": str(paths["staged"]),
                             "allow_unaffected": allow})()
    return _invoke(reviewer.stage, args)


def _publish(paths):
    return _invoke(reviewer.publish, type("Args", (), {"staged": str(paths["staged"]), "confirm": True})())


@pytest.fixture
def fake(monkeypatch):
    value = FakeGitHub()
    monkeypatch.setattr(reviewer, "_github_api", value)
    return value


def test_stage_is_one_pending_review_and_off_diff_findings_are_omitted(tmp_path, fake):
    paths = _paths(tmp_path)
    rc, state = _stage(paths)
    assert rc == 0 and state["staged"] is True and state["forge"] == "github"
    creates = [c for c in fake.calls if c[:2] == ("POST", "repos/o/r/pulls/7/reviews")]
    assert len(creates) == 1
    payload = creates[0][2]
    assert "event" not in payload and payload["commit_id"] == HEAD
    assert [(c["path"], c["line"], c["side"]) for c in payload["comments"]] == [("a.py", 2, "RIGHT")]
    assert [o["id"] for o in state["omitted"]] == ["F2"]
    assert "outside the diff" in state["omitted"][0]["reason"]
    review_id = state["review_id"]
    assert [item["draft_id"] for item in state["created"]] == [review_id, fake.review_comments[review_id][0]["id"]]
    assert state["cleanup_commands"] == ["gh api --hostname github.com -X DELETE repos/o/r/pulls/7/reviews/%d" % review_id]


def test_stage_refuses_when_the_viewer_already_has_a_pending_review(tmp_path, fake):
    fake.reviews.append({"id": 1, "body": "mine", "state": "PENDING", "user": {"login": "reviewer"}})
    fake.review_comments[1] = []
    rc, result = _stage(_paths(tmp_path))
    assert rc == 4 and result["drafts"][0]["id"] == 1


def test_false_422_on_create_adopts_the_committed_review(tmp_path, fake):
    fake.fail_create_after_commit = True
    rc, state = _stage(_paths(tmp_path))
    assert rc == 0 and state["staged"] is True
    assert len([r for r in fake.reviews if r["state"] == "PENDING"]) == 1
    assert state["review_id"] == fake.reviews[0]["id"]


def test_support_reply_is_added_inside_the_pending_review(tmp_path, fake):
    value = report()
    value["findings"][0]["memory"] = {
        "fingerprint": "f" * 64, "dimension": "correctness", "anchor_hash": "e" * 64, "state": "new",
        "match": None, "disposition": "none", "note": "", "suppress_post": False, "thread": None,
        "candidates": [], "human_context": [{"title": "earlier", "author": "bob", "url": "https://u",
                                             "note_id": 41, "discussion_id": "PRRT_1", "resolved": False}]}
    paths = _paths(tmp_path, value)
    choice = decisions(value)
    choice["decisions"][0]["reply_note_id"] = 41
    paths["decisions"].write_text(json.dumps(choice))
    rc, state = _stage(paths)
    assert rc == 0, state
    reply_calls = [c for c in fake.calls if c[1] == "graphql" and "addPullRequestReviewThreadReply" in c[2]["query"]]
    assert reply_calls[0][2]["variables"]["t"] == "PRRT_1"
    assert [item["kind"] for item in state["created"]] == ["overview", "reply"]


def test_publish_requires_exact_pending_contents_then_submits_comment(tmp_path, fake):
    paths = _paths(tmp_path)
    rc, state = _stage(paths)
    assert rc == 0
    review_id = state["review_id"]
    fake.review_comments[review_id].append({"id": 999, "path": "a.py", "line": 3, "body": "sneaky"})
    rc, result = _publish(paths)
    assert rc == 2 and "unexpected: [999]" in result["error"]
    fake.review_comments[review_id].pop()
    rc, result = _publish(paths)
    assert rc == 0 and result["published"] is True
    assert ("POST", "repos/o/r/pulls/7/reviews/%d/events" % review_id, {"event": "COMMENT"}) in fake.calls


def test_publish_aborts_when_the_head_moved_after_staging(tmp_path, fake):
    paths = _paths(tmp_path)
    assert _stage(paths)[0] == 0
    fake.pr["head"]["sha"] = "d" * 40
    rc, result = _publish(paths)
    assert rc == 2 and "head moved" in result["error"]


@pytest.mark.parametrize("action, event", [("approve", "APPROVE"), ("request-changes", "REQUEST_CHANGES")])
def test_complete_creates_a_separate_review_with_the_chosen_event(tmp_path, fake, action, event):
    paths = _paths(tmp_path)
    assert _stage(paths)[0] == 0 and _publish(paths)[0] == 0
    args = type("Args", (), {"staged": str(paths["staged"]), "action": action})()
    rc, result = _invoke(reviewer.complete, args)
    assert rc == 0 and result["completion"] == action
    payload = [c for c in fake.calls if c[:2] == ("POST", "repos/o/r/pulls/7/reviews")][-1][2]
    assert payload["event"] == event and payload["commit_id"] == HEAD
    assert ("body" in payload) is (event == "REQUEST_CHANGES")


def test_memory_threads_come_from_graphql_for_github(fake):
    fake.threads = [{"id": "PRRT_1", "isResolved": True, "path": "a.py", "line": 2, "comments": {"nodes": []}}]
    threads = reviewer.review_memory.fetch_discussions(HOST, PROJECT, NUMBER, api=fake, forge="github")
    assert threads[0]["id"] == "PRRT_1" and threads[0]["resolved"] is True
