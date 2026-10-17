import contextlib
import io
import json

import pytest

import comment_body
from forge import gitlab as gitlab_forge
from forge.github import GitHubForge
import post_reviewer_review as m  # noqa: E402

HEAD = "a" * 40
BASE = "b" * 40
START = "c" * 40


def report():
    return {
        "meta": {"target": "change", "forge": "gitlab", "number": 42, "project": "group/project", "head_sha": HEAD,
                 "title": "Review", "standfirst_md": "Summary from report.",
                 "verdict": "Fix first", "seat": "reviewer"},
        # Nit posting mechanics are exercised here; the default floor has its own test
        "run": {"dimensions_run": ["correctness"],
                "source_access": "borrowed-worktree", "severity_floor": "Nit"},
        "risk": {"level": "Medium", "verbatim_md": "Some risk."},
        "findings": [
            {"severity": "Must fix", "dimension": "correctness", "file": "a.py", "line": "2-4",
             "title": "Trusted bug", "body_md": "Trusted body.", "recommendation_md": "Trusted fix."},
            {"severity": "Should fix", "dimension": "db", "file": "b.py", "line": "7",
             "title": "Drop me", "body_md": "Not posted."},
            {"severity": "Nit", "dimension": "comments", "file": "c.py", "line": "9",
             "title": "Small issue", "body_md": "Nit body.", "recommendation_md": "Tidy it."},
        ],
        "assumptions": ["Feature is enabled"],
    }


def context():
    return {"seat": "reviewer", "refs": {"base": BASE, "start": START, "head": HEAD},
            "change": {"number": 42, "host": "gitlab.example", "project": "group/project",
                   "sha": HEAD, "current_user_id": 2, "current_username": "reviewer"},
            "diff": "".join("diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -1,10 +1,10 @@\n%s" %
                            (name, name, name, name, " x\n" * 10) for name in ("a.py", "b.py", "c.py"))}


PLAN_FORGE = m._forge({"forge": "gitlab", "host": "gitlab.example", "project": "group/project"})


def decisions():
    return {"schema": 1, "seat": "reviewer", "head_sha": HEAD, "target": "MR !42",
            "report_sha256": m._report_digest(report()), "decisions": [
                {"id": "F1", "slot": "fix", "disposition": "Blocking", "note": "Human note"},
                {"id": "F2", "slot": "ignore", "disposition": "Drop", "note": ""},
                {"id": "F3", "slot": "detail", "disposition": "Question", "note": ""},
            ]}


class FakeGitLab:
    def __init__(self):
        self.user = {"id": 2, "username": "reviewer"}
        self.head = HEAD
        self.refs = {"base_sha": BASE, "start_sha": START, "head_sha": HEAD}
        self.drafts = []
        self.calls = []
        self.next_id = 100
        self.fail_create_number = None
        self.commit_before_failing = False
        self.foreign_draft_on_failure = None
        self.fail_draft_list_after_create = False
        self.create_count = 0
        self.compare_paths = []
        self.fail_publish = False
        self.publish_commits = False

    def __call__(self, host, method, endpoint, payload=None, timeout=120):
        self.calls.append((method, endpoint, payload))
        if method == "GET" and endpoint == "user":
            return dict(self.user)
        if method == "GET" and endpoint.endswith("merge_requests/42"):
            refs = dict(self.refs)
            refs["head_sha"] = self.head
            return {"iid": 42, "state": "opened", "sha": self.head, "diff_refs": refs,
                    "author": {"id": 1, "username": "author"}}
        if method == "GET" and "/draft_notes?" in endpoint:
            if self.fail_draft_list_after_create and self.create_count:
                raise m.ReviewError("injected draft list outage")
            page = int(endpoint.rsplit("page=", 1)[1])
            start = (page - 1) * 100
            return [dict(item) for item in self.drafts[start:start + 100]]
        if method == "GET" and "/repository/compare?" in endpoint:
            return {"diffs": [{"old_path": p, "new_path": p} for p in self.compare_paths]}
        if method == "POST" and endpoint.endswith("/draft_notes"):
            self.create_count += 1
            if self.fail_create_number == self.create_count:
                if self.commit_before_failing:
                    committed = {"id": self.next_id, "note": payload["note"]}
                    if "position" in payload:
                        committed["position"] = payload["position"]
                    if "in_reply_to_discussion_id" in payload:
                        committed["in_reply_to_discussion_id"] = payload["in_reply_to_discussion_id"]
                    self.next_id += 1
                    self.drafts.append(committed)
                if self.foreign_draft_on_failure:
                    self.drafts.append(dict(self.foreign_draft_on_failure))
                raise m.ReviewError("injected create failure")
            item = {"id": self.next_id, "note": payload["note"]}
            if "position" in payload:
                item["position"] = payload["position"]
            if "in_reply_to_discussion_id" in payload:
                item["in_reply_to_discussion_id"] = payload["in_reply_to_discussion_id"]
            self.next_id += 1
            self.drafts.append(item)
            return dict(item)
        if method == "POST" and endpoint.endswith("/draft_notes/bulk_publish"):
            if self.fail_publish:
                if self.publish_commits:
                    self.drafts = []
                raise m.ReviewError("injected publish timeout")
            self.drafts = []
            return {"published": True}
        if method == "POST" and endpoint.endswith("/approve"):
            return {"approved": True, "sha": payload["sha"]}
        raise AssertionError((host, method, endpoint, payload))


def files(tmp_path):
    paths = {}
    for name, value in (("report", report()), ("decisions", decisions()), ("context", context())):
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(value))
        paths[name] = path
    paths["staged"] = tmp_path / "staged.json"
    return paths


def invoke(func, args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = func(args)
    return rc, json.loads(buf.getvalue())


def stage_args(paths, allow=False):
    return type("Args", (), {"report": str(paths["report"]), "decisions": str(paths["decisions"]),
                              "context": str(paths["context"]), "out": str(paths["staged"]),
                              "allow_unaffected": allow})()


def _publish_args(paths, confirm=True):
    return type("Args", (), {"staged": str(paths["staged"]), "confirm": confirm})()


def _complete_args(paths, action):
    return type("Args", (), {"staged": str(paths["staged"]), "action": action})()


def test_stage_builds_trusted_overview_and_inline_drafts_then_publish_is_separate(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 0 and state["staged"] is True and state["published"] is False
    assert [item["kind"] for item in state["created"]] == ["overview", "inline", "inline"]
    create_calls = [call for call in fake.calls if call[0] == "POST" and call[1].endswith("/draft_notes")]
    overview_block = comment_body.parse_block(create_calls[0][2]["note"])
    assert overview_block["kind"] == "overview" and overview_block["seat"] == "reviewer"
    assert overview_block["report_sha256"] == m._report_digest(report())
    assert "Posted: 2 · Not posted: 1" in create_calls[0][2]["note"]
    first = create_calls[1][2]
    assert comment_body.parse_block(first["note"])["kind"] == "finding"
    lead = first["note"].split("-->\n", 1)[1]
    assert lead.startswith("**Blocking** · Trusted bug")
    assert "Trusted body." in first["note"] and "**Fix:** Trusted fix." in first["note"]
    assert "Human note" in lead and "F1" not in lead and "correctness" not in lead
    assert first["position"]["head_sha"] == HEAD and first["position"]["new_line"] == 2
    nit = create_calls[2][2]["note"].split("-->\n", 1)[1]
    assert nit.startswith("**Non-blocking** · Small issue")
    assert any("normalized to Non-blocking" in warning for warning in state["warnings"])
    assert not any(call[1].endswith("bulk_publish") for call in fake.calls)

    args = _publish_args(paths)
    rc, published = invoke(m.publish, args)
    assert rc == 0 and published["published"] is True
    assert sum(call[1].endswith("bulk_publish") for call in fake.calls) == 1
    assert json.loads(paths["staged"].read_text())["published"] is True


def _stage_with_unanchorable_blocker(tmp_path, monkeypatch, line="50", **context_updates):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    changed = report()
    changed["findings"][0]["line"] = line
    choice = decisions()
    choice["report_sha256"] = m._report_digest(changed)
    paths["report"].write_text(json.dumps(changed))
    paths["decisions"].write_text(json.dumps(choice))
    paths["context"].write_text(json.dumps(dict(context(), **context_updates)))
    rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 0
    return state, fake


def test_blocking_finding_outside_the_diff_is_listed_in_the_staged_overview(tmp_path, monkeypatch):
    state, fake = _stage_with_unanchorable_blocker(tmp_path, monkeypatch)
    assert [item["kind"] for item in state["created"]] == ["overview", "inline"]
    overview = state["preview"][0]["body"]
    visible = overview.split("<details>")[0]
    assert "**Not anchored inline**" in visible
    assert "- **Blocking:** Trusted bug (`a.py:50`)" in visible
    assert any("F1 anchors on a line outside the diff" in warning for warning in state["warnings"])
    assert state["completion"]["suggested"] == "request-changes"


def test_blocking_finding_on_a_collapsed_file_is_listed_in_the_staged_overview(tmp_path, monkeypatch):
    state, _ = _stage_with_unanchorable_blocker(tmp_path, monkeypatch, line="2", unanchorable_files=["a.py"])
    visible = state["preview"][0]["body"].split("<details>")[0]
    assert "- **Blocking:** Trusted bug (`a.py:2`)" in visible
    assert [item["kind"] for item in state["created"]] == ["overview", "inline"]
    assert not any(item.get("finding_id") == "F1" for item in state["created"])
    assert any("diff the forge collapsed" in warning for warning in state["warnings"])
    assert state["completion"]["suggested"] == "request-changes"


def test_preexisting_draft_blocks_all_creation(tmp_path, monkeypatch):
    fake = FakeGitLab()
    fake.drafts = [{"id": 55, "note": "my existing draft"}]
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    rc, result = invoke(m.stage, stage_args(paths))
    assert rc == 4 and result["drafts"][0]["id"] == 55
    assert not any(call[0] == "POST" for call in fake.calls)


def test_partial_stage_failure_records_only_created_ids_and_never_deletes_or_publishes(tmp_path, monkeypatch):
    fake = FakeGitLab()
    fake.fail_create_number = 3
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 2 and state["staged"] is False
    assert [item["draft_id"] for item in state["created"]] == [100, 101]
    assert state["failed_note"] == {"kind": "inline", "finding_id": "F3"}
    assert len(state["cleanup_commands"]) == 2
    assert all("--method DELETE" in command for command in state["cleanup_commands"])
    assert not any(call[0] == "DELETE" or call[1].endswith("bulk_publish") for call in fake.calls)
    assert json.loads(paths["staged"].read_text())["created"] == state["created"]


def test_publish_refuses_a_staging_that_did_not_complete(tmp_path, monkeypatch):
    fake = FakeGitLab()
    fake.fail_create_number = 3
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    assert invoke(m.stage, stage_args(paths))[0] == 2
    rc, result = invoke(m.publish, _publish_args(paths))
    assert rc == 2 and result["published"] is False and "staging did not complete" in result["error"]
    assert not any(call[1].endswith("bulk_publish") for call in fake.calls)


def test_publish_requires_confirmation_and_exact_live_draft_set(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    assert invoke(m.stage, stage_args(paths))[0] == 0
    no = _publish_args(paths, confirm=False)
    assert invoke(m.publish, no)[0] == 2
    fake.drafts.append({"id": 999, "note": "created in UI"})
    yes = _publish_args(paths)
    rc, result = invoke(m.publish, yes)
    assert rc == 2 and "unexpected: [999]" in result["error"]
    assert not any(call[1].endswith("bulk_publish") for call in fake.calls)


def test_head_movement_blocks_before_staging_and_explicit_unaffected_uses_current_refs(tmp_path, monkeypatch):
    fake = FakeGitLab()
    fake.head = "d" * 40
    fake.refs["head_sha"] = fake.head
    fake.compare_paths = ["a.py"]
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    rc, result = invoke(m.stage, stage_args(paths))
    assert rc == 3 and result["affected_findings"] == ["F1"]
    assert not any(call[0] == "POST" for call in fake.calls)
    rc, state = invoke(m.stage, stage_args(paths, allow=True))
    assert rc == 0
    assert any(item["id"] == "F1" and "head moved" in item["reason"] for item in state["omitted"])
    inline = [item for item in state["preview"] if item["kind"] == "inline"]
    assert all(item["position"]["head_sha"] == "d" * 40 for item in inline)


def test_head_movement_after_staging_blocks_bulk(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    assert invoke(m.stage, stage_args(paths))[0] == 0
    fake.head = "e" * 40
    yes = _publish_args(paths)
    rc, result = invoke(m.publish, yes)
    assert rc == 2 and "head moved" in result["error"]
    assert not any(call[1].endswith("bulk_publish") for call in fake.calls)


def test_completion_is_explicit_and_requires_published_state(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    requested = []
    monkeypatch.setattr(gitlab_forge, "request_changes",
                        lambda run, host, project, iid: requested.append((host, project, iid)) or {"iid": str(iid)})
    paths = files(tmp_path)
    assert invoke(m.stage, stage_args(paths))[0] == 0
    before = _complete_args(paths, "approve")
    assert invoke(m.complete, before)[0] == 2
    assert invoke(m.publish, _publish_args(paths))[0] == 0
    published_state = paths["staged"].read_text()
    approve = _complete_args(paths, "approve")
    rc, result = invoke(m.complete, approve)
    assert rc == 0 and result["completion"] == "approve"
    assert any(call[1].endswith("/approve") and call[2]["sha"] == HEAD for call in fake.calls)
    assert invoke(m.complete, approve)[0] == 2

    paths["staged"].write_text(published_state)
    request = _complete_args(paths, "request-changes")
    assert invoke(m.complete, request)[0] == 0 and requested

    paths["staged"].write_text(published_state)
    comment = _complete_args(paths, "comment-only")
    before_posts = len([call for call in fake.calls if call[0] == "POST"])
    assert invoke(m.complete, comment)[0] == 0
    assert len([call for call in fake.calls if call[0] == "POST"]) == before_posts


def test_head_movement_after_publication_blocks_completion(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    assert invoke(m.stage, stage_args(paths))[0] == 0
    assert invoke(m.publish, _publish_args(paths))[0] == 0
    fake.head = "e" * 40
    rc, result = invoke(m.complete, _complete_args(paths, "approve"))
    assert rc == 2 and "head moved" in result["error"]
    assert not any(call[1].endswith("/approve") for call in fake.calls)
    assert "completion_result" not in json.loads(paths["staged"].read_text())


def test_sweep_paginates_beyond_one_hundred_drafts(tmp_path, monkeypatch):
    fake = FakeGitLab()
    fake.drafts = [{"id": i, "note": "draft %d" % i} for i in range(1, 102)]
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    rc, result = invoke(m.stage, stage_args(paths))
    assert rc == 4 and len(result["drafts"]) == 101
    pages = [call for call in fake.calls if "/draft_notes?" in call[1]]
    assert len(pages) == 2
    assert not any(call[0] == "POST" for call in fake.calls)


def test_zero_findings_still_stages_one_overview(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    value = report()
    value["findings"] = []
    value["run"]["clean_notes"] = [{"dimension": "review", "note_md": "Looks sound."}]
    paths["report"].write_text(json.dumps(value))
    choice = decisions()
    choice["decisions"] = []
    choice["zero_findings"] = True
    choice["report_sha256"] = m._report_digest(value)
    paths["decisions"].write_text(json.dumps(choice))
    rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 0 and [item["kind"] for item in state["created"]] == ["overview"]
    assert state["completion"]["suggested"] == "approve"


def test_empty_report_without_the_validator_flag_is_rejected_before_any_forge_call(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    value = report()
    value["findings"] = []
    paths["report"].write_text(json.dumps(value))
    choice = decisions()
    choice["decisions"] = []
    choice["report_sha256"] = m._report_digest(value)
    paths["decisions"].write_text(json.dumps(choice))
    rc, result = invoke(m.stage, stage_args(paths))
    assert rc == 2 and "explicit validator artifact" in result["error"]
    assert fake.calls == []


def test_missing_staged_draft_blocks_bulk_and_reports_cleanup(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    assert invoke(m.stage, stage_args(paths))[0] == 0
    fake.drafts.pop()
    yes = _publish_args(paths)
    rc, result = invoke(m.publish, yes)
    assert rc == 2 and "missing:" in result["error"]
    assert result["cleanup_commands"]
    assert not any(call[1].endswith("bulk_publish") for call in fake.calls)


def test_identity_change_blocks_stage_before_draft_creation(tmp_path, monkeypatch):
    fake = FakeGitLab()
    fake.user = {"id": 3, "username": "someone-else"}
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    rc, result = invoke(m.stage, stage_args(paths))
    assert rc == 2 and "identity changed" in result["error"]
    assert not any(call[0] == "POST" for call in fake.calls)


def test_stale_decision_file_is_rejected_before_gitlab_calls(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    choice = json.loads(paths["decisions"].read_text())
    choice["report_sha256"] = "0" * 64
    paths["decisions"].write_text(json.dumps(choice))
    rc, result = invoke(m.stage, stage_args(paths))
    assert rc == 2 and "exact report" in result["error"]
    assert fake.calls == []


@pytest.mark.parametrize("tamper, message", [
    (lambda c: c.update(head_sha="d" * 40), "decision head"),
    (lambda c: c.update(target="MR !43"), "decision target"),
    (lambda c: c["decisions"].append(dict(c["decisions"][0])), "duplicate id"),
    (lambda c: c["decisions"][0].update(disposition="Drop"), "invalid slot/disposition"),
    (lambda c: c["decisions"][0].update(reply_note_id=True), "reply_note_id must be an integer"),
    (lambda c: c["decisions"].pop(), "finding IDs do not match"),
    (lambda c: c.update(zero_findings=True), "zero_findings cannot be set"),
])
def test_forged_decisions_are_rejected_before_any_forge_call(tmp_path, monkeypatch, tamper, message):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    choice = json.loads(paths["decisions"].read_text())
    tamper(choice)
    paths["decisions"].write_text(json.dumps(choice))
    rc, result = invoke(m.stage, stage_args(paths))
    assert rc == 2 and message in result["error"]
    assert fake.calls == []


@pytest.mark.parametrize("field, value, message", [
    ("number", 43, "report change request"),
    ("project", "group/other", "report project"),
    ("head_sha", "d" * 40, "report head"),
])
def test_report_bound_to_another_change_is_rejected_before_any_forge_call(
        tmp_path, monkeypatch, field, value, message):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    changed = report()
    changed["meta"][field] = value
    choice = decisions()
    choice["report_sha256"] = m._report_digest(changed)
    paths["report"].write_text(json.dumps(changed))
    paths["decisions"].write_text(json.dumps(choice))
    rc, result = invoke(m.stage, stage_args(paths))
    assert rc == 2 and message in result["error"]
    assert fake.calls == []


def test_target_movement_with_unchanged_head_blocks_staging_even_with_allow(tmp_path, monkeypatch):
    fake = FakeGitLab()
    fake.refs["start_sha"] = "f" * 40
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    rc, result = invoke(m.stage, stage_args(paths))
    assert rc == 2 and "diff refs changed" in result["error"]
    assert not any(call[0] == "POST" for call in fake.calls)
    rc, result = invoke(m.stage, stage_args(paths, allow=True))
    assert rc == 2 and "diff refs changed" in result["error"]
    assert not any(call[0] == "POST" for call in fake.calls)


@pytest.mark.parametrize("field", ["base_sha", "start_sha"])
def test_target_movement_after_staging_blocks_bulk(tmp_path, monkeypatch, field):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    assert invoke(m.stage, stage_args(paths))[0] == 0
    fake.refs[field] = "f" * 40
    yes = _publish_args(paths)
    rc, result = invoke(m.publish, yes)
    assert rc == 2 and "diff refs changed" in result["error"]
    assert result["cleanup_commands"]
    assert not any(call[1].endswith("bulk_publish") for call in fake.calls)


def test_ambiguous_create_failure_reconciles_orphan_into_cleanup(tmp_path, monkeypatch):
    fake = FakeGitLab()
    fake.fail_create_number = 3
    fake.commit_before_failing = True
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 2 and state["staged"] is False
    assert [item["draft_id"] for item in state["created"]] == [100, 101]
    assert [item["draft_id"] for item in state["reconciled"]] == [102]
    assert state["reconciled"][0]["matches_failed_note"] is True
    assert len(state["cleanup_commands"]) == 3
    assert sum("draft_notes/102" in command for command in state["cleanup_commands"]) == 1
    assert not any(call[0] == "DELETE" or call[1].endswith("bulk_publish") for call in fake.calls)
    assert json.loads(paths["staged"].read_text())["reconciled"] == state["reconciled"]


def test_concurrent_foreign_draft_is_surfaced_but_never_offered_for_deletion(tmp_path, monkeypatch):
    fake = FakeGitLab()
    fake.fail_create_number = 3
    fake.commit_before_failing = True
    fake.foreign_draft_on_failure = {"id": 900, "note": "unrelated draft typed in the UI"}
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 2 and state["staged"] is False
    assert [item["draft_id"] for item in state["reconciled"]] == [102]
    assert [item["id"] for item in state["unrecognized_drafts"]] == [900]
    assert not any("draft_notes/900" in command for command in state["cleanup_commands"])
    assert len(state["cleanup_commands"]) == 3


def test_reconciled_orphans_keep_their_kind_so_comment_ids_are_not_cleaned_as_reviews(monkeypatch):
    body = "overview body"
    live = [{"id": 900, "kind": "review", "note": body, "position": None},
            {"id": 1000, "kind": "comment", "note": body, "position": {"new_path": "a.py", "new_line": 2}}]
    monkeypatch.setattr(m, "_list_drafts", lambda ctx: live)
    state = {"expected_username": "reviewer", "created": []}
    m._reconcile_orphans(state, body)
    assert [(item["draft_id"], item["kind"]) for item in state["reconciled"]] == [(900, "review"), (1000, "comment")]
    commands = GitHubForge("github.com", "o/r").cleanup_commands(
        dict(state, review_id=None, host="github.com", project="o/r", number=7))
    assert [command.rsplit("/", 1)[1] for command in commands] == ["900"]


def test_reconcile_list_outage_reports_incomplete_cleanup(tmp_path, monkeypatch):
    fake = FakeGitLab()
    fake.fail_create_number = 3
    fake.commit_before_failing = True
    fake.fail_draft_list_after_create = True
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 2 and state["staged"] is False
    assert "cleanup_warning" in state and "incomplete" in state["cleanup_warning"]
    assert len(state["cleanup_commands"]) == 2


def _plan_one(finding, slot="later", **row):
    prepared = {"meta": {"head_sha": HEAD}, "findings": [dict(
        {"id": "F1", "severity": "Should fix", "file": "a.py", "line": "2"}, **finding)]}
    disposition = m.ALL_SLOTS[slot]
    by_id = {"F1": dict({"id": "F1", "slot": slot, "disposition": disposition, "note": ""}, **row)}
    posted, _, warnings = m._plan(prepared, by_id, context(), {
        "base_sha": BASE, "start_sha": START, "head_sha": HEAD}, PLAN_FORGE)
    return posted[0], warnings


def test_inline_body_marks_optional_feedback_and_phrases_questions_as_asks():
    finding = {"title": "Behavior", "body_md": "Observed behavior.", "recommendation_md": "Explain it."}
    optional, _ = _plan_one(finding, slot="later")
    question, _ = _plan_one(finding, slot="detail")
    assert optional["body"].split("-->\n", 1)[1].startswith("**Non-blocking** · Behavior")
    assert "Optional feedback — this does not block" in optional["body"]
    assert question["body"].split("-->\n", 1)[1].startswith("**Question** · Behavior")
    assert "Could you clarify" in question["body"]


def test_inline_body_leads_with_impact_and_puts_fix_line_before_details():
    finding = {"title": "Behavior", "impact": "Totals drift.", "body_md": "Observed behavior.",
               "fix_md": "Round once.", "recommendation_md": "```diff\n-a\n+b\n```"}
    entry, warnings = _plan_one(finding, slot="fix")
    body = entry["body"]
    assert body.index("Totals drift.") < body.index("**Fix:** Round once.") < body.index("<summary>Details")
    assert body.index("<summary>Details") < body.index("Observed behavior.")
    assert warnings == []


def test_inline_body_warnings_from_comment_body_reach_staging_warnings():
    entry, warnings = _plan_one({"title": "Behavior", "body_md": "Observed behavior."}, slot="fix")
    assert any("impact missing" in warning for warning in warnings)
    assert any("fix_md missing" in warning for warning in warnings)


def test_inline_body_carries_fingerprint_only_in_leading_block():
    fingerprint = "a1" * 32
    entry, _ = _plan_one({"title": "Behavior", "body_md": "Body.", "impact": "Why.", "fix_md": "Do.",
                          "memory": {"fingerprint": fingerprint}}, slot="fix")
    assert comment_body.parse_block(entry["body"])["fp"] == fingerprint
    assert entry["body"].count(fingerprint) == 1
    assert m.review_memory.marker_fingerprints(entry["body"]) == [fingerprint]


def test_request_changes_uses_string_graphql_variables(monkeypatch):
    calls = []

    def fake_run(cmd, input_text=None, timeout=120):
        calls.append(cmd)
        body = {"data": {"mergeRequestRequestChanges": {"errors": [], "mergeRequest": {"iid": "42"}}}}
        return type("Result", (), {"returncode": 0, "stdout": json.dumps(body), "stderr": ""})()

    monkeypatch.setattr(m, "_run", fake_run)
    result = PLAN_FORGE.complete(42, "request-changes", HEAD, "")
    assert result["mergeRequest"]["iid"] == "42"
    cmd = calls[0]
    assert ["-f", "iid=42"] == cmd[-2:]
    assert "mergeRequestRequestChanges" in cmd[cmd.index("-f") + 1]


def _memory_stage_files(tmp_path, monkeypatch):
    """Write stage inputs for a memory-enabled report; return (paths, fingerprint of F1)."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    ctx = context()
    ctx["diff"] = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n"
        "@@ -1,3 +1,3 @@\n old\n-old\n+new\n")
    snapshot = m.review_memory.load_snapshot(
        ctx, repo=str(tmp_path), dimensions=("correctness",), fresh=True)
    enriched = m.review_memory.reconcile(report(), ctx, snapshot)
    choice = decisions()
    choice["report_sha256"] = m._report_digest(enriched)
    paths = files(tmp_path)
    paths["report"].write_text(json.dumps(enriched))
    paths["decisions"].write_text(json.dumps(choice))
    paths["context"].write_text(json.dumps(ctx))
    return paths, enriched["findings"][0]["memory"]["fingerprint"]


def test_memory_enabled_stage_reconciles_live_discussions_before_drafts(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths, fingerprint = _memory_stage_files(tmp_path, monkeypatch)
    live = [{"id": "discussion-1", "notes": [{
        "id": 7, "web_url": "https://gitlab.example/group/project/-/merge_requests/42#note_7",
        "author": {"id": 2, "username": "reviewer"},
        "body": "<!-- quirk-review:v1\nkind: finding\nfp: %s\n-->\nposted" % fingerprint}]}]
    monkeypatch.setattr(m.review_memory, "fetch_discussions", lambda *args, **kwargs: list(live))
    rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 0 and state["memory_enabled"] is True
    omitted = next(item for item in state["omitted"] if item["id"] == "F1")
    assert omitted["thread_url"].endswith("#note_7")
    assert all(item.get("finding_id") != "F1" for item in state["created"])
    assert state["completion"]["suggested"] == "request-changes"
    assert not any("bulk_publish" in call[1] for call in fake.calls)


@pytest.mark.parametrize("severity, slot, suggested", [
    ("Must fix", "fix", "request-changes"),
    ("Nit", "fix", "approve"),
    ("Must fix", "later", "approve"),
], ids=["blocking-thread", "nit-thread", "later-slot-thread"])
def test_an_already_posted_thread_suggests_request_changes_only_when_blocking(severity, slot, suggested):
    prepared = {"findings": [{"id": "F1", "severity": severity}]}
    omitted = [{"id": "F1", "reason": "already posted in an open thread", "disposition": "Blocking",
                "decision": {"slot": slot}}]
    assert m._suggested_completion(prepared, [], omitted) == suggested


def test_failed_memory_cross_check_blocks_stage_before_any_draft(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths, _ = _memory_stage_files(tmp_path, monkeypatch)

    def unavailable(*args, **kwargs):
        raise m.ReviewError("discussions unavailable")

    monkeypatch.setattr(m.review_memory, "fetch_discussions", unavailable)
    rc, result = invoke(m.stage, stage_args(paths))
    assert rc == 2 and "memory discussion cross-check failed" in result["error"]
    assert not any(call[0] == "POST" for call in fake.calls)


def test_failed_memory_snapshot_binding_blocks_stage_before_any_draft(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths, _ = _memory_stage_files(tmp_path, monkeypatch)

    def mismatched(*args, **kwargs):
        raise ValueError("snapshot belongs to another change")

    monkeypatch.setattr(m.review_memory, "validate_snapshot", mismatched)
    rc, result = invoke(m.stage, stage_args(paths))
    assert rc == 2 and "memory snapshot binding failed" in result["error"]
    assert not any(call[0] == "POST" for call in fake.calls)


def test_memory_exact_open_thread_suppresses_duplicate_post_and_keeps_decision():
    fingerprint = "f" * 64
    prepared = {"findings": [{
        "id": "F1", "severity": "Must fix", "file": "a.py", "line": "2",
        "title": "Already raised", "body_md": "Body.",
        "memory": {"fingerprint": fingerprint, "state": "carried",
                   "suppress_post": True,
                   "thread": {"url": "https://gitlab.example/thread/1"}},
    }]}
    decisions_by_id = {"F1": {"id": "F1", "slot": "fix", "disposition": "Blocking", "note": ""}}
    posted, omitted, _ = m._plan(prepared, decisions_by_id, context(), {
        "base_sha": BASE, "start_sha": START, "head_sha": HEAD}, PLAN_FORGE)
    assert posted == []
    assert omitted[0]["id"] == "F1"
    assert omitted[0]["thread_url"].endswith("/1")
    assert omitted[0]["decision"]["disposition"] == "Blocking"


def _stage_with_fingerprint(paths, fingerprint, **state_updates):
    """Stage the default review, then tag its first inline draft as a memory finding."""
    assert invoke(m.stage, stage_args(paths))[0] == 0
    state = json.loads(paths["staged"].read_text())
    inline = next(item for item in state["created"] if item["kind"] == "inline")
    inline["fingerprint"] = fingerprint
    state["memory_enabled"] = True
    state.update(state_updates)
    paths["staged"].write_text(json.dumps(state))


@pytest.mark.parametrize("marker_author, blocks", [
    ({"id": 2, "username": "reviewer"}, True),
    # a marker copied by someone else must not stall our publication
    ({"id": 99, "username": "unrelated-human"}, False),
])
def test_memory_marker_blocks_publish_only_when_it_is_ours(tmp_path, monkeypatch, marker_author, blocks):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    fingerprint = "e" * 64
    monkeypatch.setattr(m.review_memory, "fetch_discussions", lambda *args, **kwargs: [{
        "id": "discussion-1",
        "notes": [{"id": 7, "author": marker_author,
                   "body": "<!-- quirk-review:v1\nkind: finding\nfp: %s\n-->\nposted" % fingerprint}],
    }])
    paths = files(tmp_path)
    _stage_with_fingerprint(paths, fingerprint)
    rc, result = invoke(m.publish, _publish_args(paths))
    published = any(call[1].endswith("bulk_publish") for call in fake.calls)
    if blocks:
        assert rc == 2 and result["published"] is False and "restage" in result["error"]
        assert not published
    else:
        assert rc == 0 and result["published"] is True and published


def test_memory_receipt_failure_after_bulk_reports_published(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    monkeypatch.setattr(m.review_memory, "fetch_discussions", lambda *args, **kwargs: [])

    def fail_commit(*args, **kwargs):
        raise m.ReviewError("ledger unavailable")

    monkeypatch.setattr(m.review_memory, "commit_report", fail_commit)
    paths = files(tmp_path)
    _stage_with_fingerprint(paths, "d" * 64, memory_report=report(), memory_decisions=decisions())
    rc, result = invoke(m.publish, _publish_args(paths))
    assert rc == 0 and result["published"] is True
    assert any("ledger" in warning for warning in result["warnings"])
    assert json.loads(paths["staged"].read_text())["published"] is True
    assert any(call[1].endswith("bulk_publish") for call in fake.calls)


REPLY_FP = "b2" * 32
CARRIED_FP = "c3" * 32


def _memory(fingerprint, human_context=(), suppress=False, state="new"):
    return {"fingerprint": fingerprint, "dimension": "correctness", "anchor_hash": None,
            "state": state, "match": None, "disposition": "none", "note": "",
            "suppress_post": suppress, "thread": None, "candidates": [],
            "human_context": list(human_context)}


def _human(note_id=7, discussion_id="disc-9", resolved=False):
    return {"discussion_id": discussion_id, "note_id": note_id, "author": "alice",
            "url": "https://gitlab.example/group/project/-/merge_requests/42#note_%s" % note_id,
            "body": "this looks wrong", "resolved": resolved}


def reply_report(human_context=None):
    value = report()
    value["findings"][0]["impact"] = "Totals drift."
    value["findings"][0]["fix_md"] = "Round once."
    value["findings"][0]["memory"] = _memory(
        REPLY_FP, [_human()] if human_context is None else human_context)
    value["findings"][1]["memory"] = _memory(
        CARRIED_FP, suppress=True, state="carried")
    return value


def reply_files(tmp_path, value=None, reply_note_id=7):
    value = value or reply_report()
    paths = files(tmp_path)
    choice = decisions()
    choice["report_sha256"] = m._report_digest(value)
    if reply_note_id is not None:
        choice["decisions"][0]["reply_note_id"] = reply_note_id
    paths["report"].write_text(json.dumps(value))
    paths["decisions"].write_text(json.dumps(choice))
    return paths


@contextlib.contextmanager
def with_fake(monkeypatch, fake):
    with monkeypatch.context() as patch:
        patch.setattr(m, "_api", fake)
        yield


def draft_posts(fake):
    return [call[2] for call in fake.calls if call[0] == "POST" and call[1].endswith("/draft_notes")]


def test_reply_is_staged_as_a_positionless_reply_draft_after_inline_drafts(tmp_path, monkeypatch):
    fake = FakeGitLab()
    with with_fake(monkeypatch, fake):
        paths = reply_files(tmp_path)
        rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 0 and state["staged"] is True
    assert [item["kind"] for item in state["created"]] == ["overview", "inline", "reply"]
    inline_payload, reply_payload = draft_posts(fake)[1:]
    assert "position" in inline_payload and "in_reply_to_discussion_id" not in inline_payload
    assert reply_payload["in_reply_to_discussion_id"] == "disc-9"
    assert set(reply_payload) == {"note", "in_reply_to_discussion_id"}
    block = comment_body.parse_block(reply_payload["note"])
    assert block["kind"] == "support" and block["supports_discussion"] == "disc-9"
    assert block["supports_note"] == 7 and block["fp"] == REPLY_FP
    assert "**Agree · Blocking**" in reply_payload["note"] and "Human note" in reply_payload["note"]
    reply = state["preview"][-1]
    assert reply["kind"] == "reply" and reply["label"] == "reply → @alice"
    assert (reply["discussion_id"], reply["note_id"], reply["author"]) == ("disc-9", 7, "alice")
    assert state["created"][-1]["fingerprint"] == REPLY_FP


def test_overview_block_lists_posted_and_still_open_fingerprints(tmp_path, monkeypatch):
    fake = FakeGitLab()
    with with_fake(monkeypatch, fake):
        paths = reply_files(tmp_path)
        assert invoke(m.stage, stage_args(paths))[0] == 0
    block = comment_body.parse_block(draft_posts(fake)[0]["note"])
    assert block["kind"] == "overview" and block["seat"] == "reviewer"
    assert block["posted"] == [REPLY_FP] and block["supported"] == [REPLY_FP]
    assert block["still_open"] == [CARRIED_FP]
    assert block["report_sha256"] == m._report_digest(reply_report())
    assert block["head_sha"] == HEAD


def test_stale_reply_target_falls_back_to_inline_with_a_warning(tmp_path, monkeypatch):
    for stale in ([], [_human(resolved=True)], [_human(note_id=8)]):
        fake = FakeGitLab()
        with with_fake(monkeypatch, fake):
            paths = reply_files(tmp_path, reply_report(stale))
            rc, state = invoke(m.stage, stage_args(paths))
        assert rc == 0
        assert [item["kind"] for item in state["created"]] == ["overview", "inline", "inline"]
        assert all("in_reply_to_discussion_id" not in payload for payload in draft_posts(fake))
        assert any("F1" in warning and "reply target" in warning for warning in state["warnings"])


def test_reply_to_an_own_comment_falls_back_to_inline_with_a_warning(tmp_path, monkeypatch):
    fake = FakeGitLab()
    with with_fake(monkeypatch, fake):
        paths = reply_files(tmp_path, reply_report([dict(_human(), own=True)]))
        rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 0
    assert [item["kind"] for item in state["created"]] == ["overview", "inline", "inline"]
    assert all("in_reply_to_discussion_id" not in payload for payload in draft_posts(fake))
    assert any("F1" in warning and "reply target" in warning for warning in state["warnings"])


def test_reply_target_comes_from_trusted_report_not_decision_paste(tmp_path, monkeypatch):
    fake = FakeGitLab()
    with with_fake(monkeypatch, fake):
        paths = reply_files(tmp_path)
        choice = json.loads(paths["decisions"].read_text())
        choice["decisions"][0]["discussion_id"] = "attacker-discussion"
        paths["decisions"].write_text(json.dumps(choice))
        rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 0
    assert draft_posts(fake)[-1]["in_reply_to_discussion_id"] == "disc-9"


def test_reply_note_id_of_the_wrong_type_is_rejected_before_gitlab_calls(tmp_path, monkeypatch):
    for bad in ("7", True, 7.0, [7]):
        fake = FakeGitLab()
        with with_fake(monkeypatch, fake):
            paths = reply_files(tmp_path, reply_note_id=bad)
            rc, result = invoke(m.stage, stage_args(paths))
        assert rc == 2 and "reply_note_id must be an integer" in result["error"]
        assert fake.calls == []


def test_reply_is_not_staged_for_a_slot_that_does_not_post(tmp_path, monkeypatch):
    fake = FakeGitLab()
    with with_fake(monkeypatch, fake):
        paths = reply_files(tmp_path)
        choice = json.loads(paths["decisions"].read_text())
        choice["decisions"][0].update({"slot": "ignore", "disposition": "Drop"})
        paths["decisions"].write_text(json.dumps(choice))
        rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 0
    assert [item["kind"] for item in state["created"]] == ["overview", "inline"]
    assert any(item["id"] == "F1" and item["reason"] == "Drop" for item in state["omitted"])


def test_reply_nit_is_normalized_to_non_blocking():
    prepared = {"meta": {"head_sha": HEAD}, "run": {"severity_floor": "Nit"}, "findings": [{
        "id": "F1", "severity": "Nit", "file": "a.py", "line": "2", "title": "Tidy",
        "impact": "Reads badly.", "fix_md": "Rename it.",
        "memory": _memory(REPLY_FP, [_human()])}]}
    by_id = {"F1": {"id": "F1", "slot": "fix", "disposition": "Blocking", "note": "",
                    "reply_note_id": 7}}
    posted, _, warnings = m._plan(prepared, by_id, context(), {
        "base_sha": BASE, "start_sha": START, "head_sha": HEAD}, PLAN_FORGE)
    assert posted[0]["kind"] == "reply" and posted[0]["disposition"] == "Non-blocking"
    assert "**Agree · Non-blocking**" in posted[0]["body"]
    assert any("normalized to Non-blocking" in warning for warning in warnings)


def test_reply_for_a_suppressed_finding_is_not_posted():
    prepared = {"meta": {"head_sha": HEAD}, "findings": [{
        "id": "F1", "severity": "Must fix", "file": "a.py", "line": "2", "title": "Seen",
        "memory": _memory(REPLY_FP, [_human()], suppress=True, state="carried")}]}
    by_id = {"F1": {"id": "F1", "slot": "fix", "disposition": "Blocking", "note": "",
                    "reply_note_id": 7}}
    posted, omitted, _ = m._plan(prepared, by_id, context(), {
        "base_sha": BASE, "start_sha": START, "head_sha": HEAD}, PLAN_FORGE)
    assert posted == [] and omitted[0]["fingerprint"] == REPLY_FP


def test_reply_is_omitted_when_its_file_changed_with_the_head(tmp_path, monkeypatch):
    fake = FakeGitLab()
    fake.head = "d" * 40
    fake.refs["head_sha"] = fake.head
    fake.compare_paths = ["a.py"]
    with with_fake(monkeypatch, fake):
        paths = reply_files(tmp_path)
        rc, state = invoke(m.stage, stage_args(paths, allow=True))
    assert rc == 0
    assert any(item["id"] == "F1" and "head moved" in item["reason"] for item in state["omitted"])
    assert not any(item["kind"] == "reply" for item in state["created"])
    assert all("in_reply_to_discussion_id" not in payload for payload in draft_posts(fake))


def _memory_enabled_state(paths):
    state = json.loads(paths["staged"].read_text())
    state["memory_enabled"] = True
    state["memory_report"] = reply_report()
    state["memory_decisions"] = json.loads(paths["decisions"].read_text())
    paths["staged"].write_text(json.dumps(state))


def _our_note(body, note_id=7):
    return {"id": note_id, "author": {"id": 2, "username": "reviewer"}, "body": body}


def _reply_thread(resolved=False):
    """The live human thread the staged support reply answers."""
    return {"id": "disc-9", "notes": [{"id": 7, "author": {"id": 50, "username": "alice"},
                                       "body": "Totals look off.", "resolved": resolved}]}


def _publish_reply(tmp_path, monkeypatch, fake, discussions):
    monkeypatch.setattr(m.review_memory, "fetch_discussions", discussions)
    with with_fake(monkeypatch, fake):
        paths = reply_files(tmp_path)
        assert invoke(m.stage, stage_args(paths))[0] == 0
        _memory_enabled_state(paths)
        return invoke(m.publish, _publish_args(paths))


def test_publish_aborts_when_a_reply_fingerprint_already_appears_in_a_live_discussion(
        tmp_path, monkeypatch):
    fake = FakeGitLab()
    body = comment_body.finding_body(
        reply_report()["findings"][0], seat="reviewer", lead="Blocking")[0]
    rc, result = _publish_reply(tmp_path, monkeypatch, fake, lambda *a, **k: [
        _reply_thread(), {"id": "late", "notes": [_our_note(body)]}])
    assert rc == 2 and result["published"] is False and "restage" in result["error"]
    assert REPLY_FP in result["error"]
    assert not any(call[1].endswith("bulk_publish") for call in fake.calls)


@pytest.mark.parametrize("live", [[], [_reply_thread(resolved=True)]], ids=["deleted", "resolved"])
def test_publish_aborts_when_the_reply_thread_is_no_longer_open(tmp_path, monkeypatch, live):
    fake = FakeGitLab()
    rc, result = _publish_reply(tmp_path, monkeypatch, fake, lambda *a, **k: live)
    assert rc == 2 and result["published"] is False and "disc-9" in result["error"]
    assert not any(call[1].endswith("bulk_publish") for call in fake.calls)


def test_new_form_marker_from_another_author_does_not_block_publish(tmp_path, monkeypatch):
    copied = comment_body.finding_body(
        reply_report()["findings"][0], seat="reviewer", lead="Blocking")[0]
    note = _our_note(copied)
    note["author"] = {"id": 99, "username": "unrelated-human"}
    rc, result = _publish_reply(tmp_path, monkeypatch, FakeGitLab(), lambda *a, **k: [
        _reply_thread(), {"id": "late", "notes": [note]}])
    assert rc == 0 and result["published"] is True


def test_receipts_are_recorded_for_published_replies(tmp_path, monkeypatch):
    reply_note = comment_body.support_body(
        reply_report()["findings"][0], disposition="Blocking", discussion_id="disc-9",
        note_id=7)[0]
    fetches = []

    def fetch(*args, **kwargs):
        fetches.append(1)
        if len(fetches) == 1:
            return [_reply_thread()]
        return [{"id": "disc-9", "notes": [_our_note(reply_note, 55)]}]

    saved = {}
    monkeypatch.setattr(m.review_memory, "commit_report",
                        lambda report_, decisions_, receipts=None: saved.update(receipts=receipts) or {})
    rc, result = _publish_reply(tmp_path, monkeypatch, FakeGitLab(), fetch)
    assert rc == 0 and result["published"] is True
    receipt = saved["receipts"]["F1"]
    assert receipt["published"] is True and receipt["head_sha"] == HEAD
    assert receipt["discussion_id"] == "disc-9" and receipt["note_id"] == 55


def test_receipts_helper_warns_when_a_reply_has_no_recoverable_marker():
    state = {"memory_enabled": True, "expected_user_id": 2, "expected_username": "reviewer",
             "created": [{"kind": "reply", "finding_id": "F1", "fingerprint": REPLY_FP}]}
    receipts, warnings = m._memory_receipts(state, {"head_sha": HEAD}, [])
    assert receipts["F1"] == {"published": True, "head_sha": HEAD}
    assert any("F1" in warning for warning in warnings)


def test_plan_omits_findings_below_the_default_floor():
    prepared = {"meta": {"head_sha": HEAD}, "findings": [
        {"id": "F1", "severity": "Should fix", "file": "a.py", "line": "2", "title": "Real",
         "impact": "Breaks.", "fix_md": "Fix."},
        {"id": "F2", "severity": "Nit", "file": "a.py", "line": "3", "title": "Tidy",
         "impact": "Reads badly.", "fix_md": "Rename it."}]}
    by_id = {fid: {"id": fid, "slot": "later", "disposition": "Non-blocking", "note": ""}
             for fid in ("F1", "F2")}
    posted, omitted, _ = m._plan(prepared, by_id, context(), {
        "base_sha": BASE, "start_sha": START, "head_sha": HEAD}, PLAN_FORGE)
    assert [item["finding_id"] for item in posted] == ["F1"]
    assert omitted == [{"id": "F2", "reason": "below the posting floor (Should fix)",
                        "disposition": "Non-blocking", "fingerprint": None}]


@pytest.mark.parametrize("seat_source, staged", [("chosen", True), ("detected", False)])
def test_reviewer_seat_on_own_change_is_allowed_only_when_chosen(tmp_path, seat_source, staged, monkeypatch):
    fake = FakeGitLab()
    fake.user = {"id": 1, "username": "author"}
    paths = files(tmp_path)
    ctx = context()
    ctx["change"].update({"current_user_id": 1, "current_username": "author", "seat_source": seat_source})
    paths["context"].write_text(json.dumps(ctx))
    with with_fake(monkeypatch, fake):
        rc, state = invoke(m.stage, stage_args(paths))
    if staged:
        assert rc == 0 and state["staged"] is True and state["seat_source"] == "chosen"
    else:
        assert rc == 2 and "author now matches" in state["error"]


def test_old_side_finding_is_staged_on_the_removed_line():
    old_side, _ = _plan_one({"title": "Removed", "body_md": "Body.", "anchor_side": "old"}, slot="fix")
    new_side, _ = _plan_one({"title": "Added", "body_md": "Body."}, slot="fix")
    assert old_side["position"]["old_line"] == 2 and "new_line" not in old_side["position"]
    assert new_side["position"]["new_line"] == 2 and new_side["position"]["old_line"] == 2


def _stage_with_run(tmp_path, monkeypatch, **run):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    value = report()
    value["run"].update(run)
    paths = files(tmp_path)
    choice = decisions()
    choice["report_sha256"] = m._report_digest(value)
    paths["report"].write_text(json.dumps(value))
    paths["decisions"].write_text(json.dumps(choice))
    rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 0
    return state


@pytest.mark.parametrize("run", [{"incomplete": True}, {"dimensions_failed": ["db"]}],
                         ids=["incomplete", "failed-lens"])
def test_incomplete_review_is_never_suggested_as_approvable(tmp_path, monkeypatch, run):
    state = _stage_with_run(tmp_path, monkeypatch, **run)
    assert state["completion"]["suggested"] == "comment-only"


def test_complete_review_with_a_blocking_finding_still_suggests_request_changes(tmp_path, monkeypatch):
    state = _stage_with_run(tmp_path, monkeypatch, incomplete=False)
    assert state["completion"]["suggested"] == "request-changes"


def test_plausible_finding_triaged_blocking_does_not_suggest_request_changes(tmp_path, monkeypatch):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    value = report()
    value["findings"][0].update(verification_status="plausible", what_would_confirm="Run the path.")
    paths = files(tmp_path)
    choice = decisions()
    choice["report_sha256"] = m._report_digest(value)
    paths["report"].write_text(json.dumps(value))
    paths["decisions"].write_text(json.dumps(choice))
    rc, state = invoke(m.stage, stage_args(paths))
    assert rc == 0
    assert "F1" not in [item.get("finding_id") for item in state["preview"]]
    assert state["completion"]["suggested"] == "approve"


def _publish_after_staging(tmp_path, monkeypatch, fake):
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    assert invoke(m.stage, stage_args(paths))[0] == 0
    fake.fail_publish = True
    rc, result = invoke(m.publish, _publish_args(paths))
    return paths, rc, result


def test_publish_whose_response_was_lost_but_committed_counts_as_published(tmp_path, monkeypatch):
    fake = FakeGitLab()
    fake.publish_commits = True
    paths, rc, result = _publish_after_staging(tmp_path, monkeypatch, fake)
    assert rc == 0 and result["published"] is True
    assert "cleanup_commands" not in result
    assert any("response was lost" in warning for warning in result["warnings"])
    assert json.loads(paths["staged"].read_text())["published"] is True
    assert invoke(m.complete, _complete_args(paths, "comment-only"))[0] == 0


def test_publish_that_really_failed_keeps_the_cleanup_commands(tmp_path, monkeypatch):
    fake = FakeGitLab()
    paths, rc, result = _publish_after_staging(tmp_path, monkeypatch, fake)
    assert rc == 2 and result["published"] is False and "injected publish timeout" in result["error"]
    assert result["cleanup_commands"] and len(result["staged_draft_ids"]) == 3
    assert json.loads(paths["staged"].read_text())["published"] is False


def test_publish_failure_with_an_unreadable_draft_list_is_reported_as_unpublished(tmp_path, monkeypatch):
    fake = FakeGitLab()
    fake.publish_commits = True
    original = fake.__call__

    def flaky(host, method, endpoint, payload=None, timeout=120):
        if method == "GET" and "/draft_notes?" in endpoint and fake.fail_publish and fake.drafts == []:
            raise m.ReviewError("injected draft list outage")
        return original(host, method, endpoint, payload, timeout)

    monkeypatch.setattr(m, "_api", flaky)
    paths = files(tmp_path)
    assert invoke(m.stage, stage_args(paths))[0] == 0
    fake.fail_publish = True
    rc, result = invoke(m.publish, _publish_args(paths))
    assert rc == 2 and result["published"] is False


@pytest.mark.parametrize("slot", ["fix", "later", "detail"])
def test_plausible_reviewer_finding_is_never_staged_or_counted_as_blocking(slot):
    prepared = {"meta": {"head_sha": HEAD}, "findings": [
        {"id": "F1", "severity": "Must fix", "file": "a.py", "line": "2",
         "title": "Maybe", "body_md": "Needs more evidence.", "verification_status": "plausible",
         "what_would_confirm": "Run the failing input."},
        {"id": "F2", "severity": "Should fix", "file": "b.py", "line": "7",
         "title": "Confirmed", "body_md": "Fails.", "impact": "Breaks.", "fix_md": "Fix it.",
         "verification_status": "confirmed"}]}
    decisions_by_id = {
        "F1": {"id": "F1", "slot": slot, "disposition": "Blocking", "note": ""},
        "F2": {"id": "F2", "slot": "fix", "disposition": "Blocking", "note": ""}}
    staged, omitted, warnings = m._plan(prepared, decisions_by_id, context(), {
        "base_sha": BASE, "start_sha": START, "head_sha": HEAD}, PLAN_FORGE)
    assert [item["finding_id"] for item in staged] == ["F2"]
    assert omitted == [{"id": "F1", "file": "a.py", "line": "2", "severity": "Must fix",
                        "reason": "plausible finding (never posted)"}]
    assert warnings == []


DELTA_SINCE = {"ref": "abc", "sha": "d" * 40, "merge_commits": 0}


def test_context_helper_refuses_a_delta_context():
    with pytest.raises(m.ReviewError, match=r"delta review \(--since\) is report-only"):
        m._context(dict(context(), since=DELTA_SINCE))
    assert m._context(context())["number"] == 42


@pytest.mark.parametrize("where", ["context", "report"])
def test_stage_refuses_a_delta_review_before_any_forge_call(tmp_path, monkeypatch, where):
    fake = FakeGitLab()
    monkeypatch.setattr(m, "_api", fake)
    paths = files(tmp_path)
    if where == "context":
        paths["context"].write_text(json.dumps(dict(context(), since=DELTA_SINCE)))
    else:
        value = report()
        value["run"]["since"] = DELTA_SINCE
        paths["report"].write_text(json.dumps(value))
    rc, result = invoke(m.stage, stage_args(paths))
    assert rc == 2 and "delta review (--since) is report-only" in result["error"]
    assert fake.calls == []
