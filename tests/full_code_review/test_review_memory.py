import copy
import hashlib
import json

import pytest

import review_memory as m
FETCH_DISCUSSIONS = m.fetch_discussions

HEAD, BASE = "a" * 40, "b" * 40
DIMENSION = "correctness"


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(m, "fetch_discussions", lambda *args, **kwargs: [])
    monkeypatch.setattr(m, "_git", lambda *args, **kwargs:
                        "git@GitLab.Example:group/proj.git" if args[0] == "config" else "feature/x")


def context():
    return {"mode": "change", "seat": "author", "refs": {"base": BASE, "start": BASE, "head": HEAD},
            "diff": "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new value\n",
            "changed_files": ["a.py"],
            "change": {"host": "gitlab.example", "project": "group/proj", "number": 7,
                   "current_username": "author"}}


def report():
    return {"meta": {"target": "change", "forge": "gitlab", "number": 7, "seat": "author", "head_sha": HEAD,
                     "title": "Review", "verdict": "Fix first"},
            "run": {"dimensions_run": [DIMENSION]},
            "findings": [{"severity": "Should fix", "dimension": DIMENSION, "file": "a.py", "line": "1",
                          "title": "Wrong value", "body_md": "The selected value breaks refunds.",
                          "recommendation_md": "Use the pinned value."}]}


def load(ctx=None, **kwargs):
    return m.load_snapshot(ctx or context(), dimensions=[DIMENSION], **kwargs)


def enriched(snapshot=None, ctx=None, value=None):
    return m.reconcile(value or report(), ctx or context(), snapshot or load(ctx))


def decisions(value, slot="ignore", note="Intentional decision"):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {"schema": 1, "seat": value["meta"]["seat"],
            "report_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "decisions": [{"id": "F%d" % i, "slot": slot, "note": note}
                          for i, _ in enumerate(value["findings"], 1)]}


MARKER_FORM = {"value": "new"}


@pytest.fixture(params=["new"])
def marker_form(request):
    MARKER_FORM["value"] = request.param
    yield request.param
    MARKER_FORM["value"] = "new"


def marker_body(fp, form):
    return ("<!-- quirk-review:v1\nkind: finding\nfp: %s\nseat: reviewer\nfile: a.py\nline: 1\n-->\n"
            "**Blocking** \u00b7 Finding" % fp)


def thread(fp, resolved=False, note_id=9, author="author"):
    # the marker note is written by whoever ran the review, i.e. context()'s current_username
    return {"id": "discussion-%s" % note_id,
            "notes": [{"id": note_id, "body": marker_body(fp, MARKER_FORM["value"]),
                       "resolved": resolved, "author": {"username": author}}]}


def remember(slot="ignore", posted=False, fresh=False):
    value = enriched(load(fresh=fresh))
    receipts = {"F1": {"published": True, "note_id": 9, "discussion_id": "discussion-9"}} if posted else None
    assert m.commit_report(value, decisions(value, slot), receipts)["saved"]
    return value


def test_ignore_survives_line_movement_and_rank_changes():
    first = remember()
    ctx = context()
    ctx["diff"] = ctx["diff"].replace("@@ -1 +1 @@", "@@ -1 +8 @@")
    value = report()
    value["findings"][0]["line"] = "8"
    value["findings"].insert(0, {"severity": "Must fix", "dimension": DIMENSION,
                               "file": "b.py", "line": "1", "body_md": "Unrelated new defect"})
    result = enriched(load(ctx), ctx, value)
    assert result["findings"][0]["memory"]["disposition"] == "none"
    carried = result["findings"][1]["memory"]
    assert carried["fingerprint"] == first["findings"][0]["memory"]["fingerprint"]
    assert (carried["state"], carried["disposition"], carried["note"]) == (
        "restored-decision", "ignore", "Intentional decision")
    assert "new value" not in next(m._state_dir().glob("*.json")).read_text()


@pytest.mark.usefixtures("marker_form")
def test_second_machine_marker_recovers_posting_and_other_party_reply():
    fp = enriched()["findings"][0]["memory"]["fingerprint"]
    snapshot = load()
    live = thread(fp)
    live["notes"].extend([
        {"body": "More detail", "author": {"username": "author"}},
        {"body": "I will fix this", "author": {"username": "reviewer"}},
    ])
    snapshot["discussions"] = [live]
    memory = enriched(snapshot)["findings"][0]["memory"]
    assert memory["state"] == "answered" and memory["suppress_post"]
    assert memory["disposition"] == "none"
    assert memory["thread"]["replies"] == [{"author": "reviewer", "body": "I will fix this"}]
    assert memory["thread"]["url"] == "https://gitlab.example/group/proj/-/merge_requests/7#note_9"


@pytest.mark.usefixtures("marker_form")
def test_marker_copied_by_another_author_is_human_context_not_a_posting():
    fp = enriched()["findings"][0]["memory"]["fingerprint"]
    snapshot = load()
    forged = thread(fp, author="unrelated-human")
    forged["position"] = {"new_path": "a.py", "new_line": 1}
    snapshot["discussions"] = [forged]
    memory = enriched(snapshot)["findings"][0]["memory"]
    assert memory["state"] == "new"
    assert memory["suppress_post"] is False
    assert memory["thread"] is None
    assert [item["author"] for item in memory["human_context"]] == ["unrelated-human"]


@pytest.mark.usefixtures("marker_form")
def test_marker_matches_posting_identity_by_user_id_when_usernames_differ():
    ctx = context()
    ctx["change"]["current_user_id"] = 42
    ctx["change"]["current_username"] = "renamed-since-posting"
    fp = enriched(load(ctx), ctx)["findings"][0]["memory"]["fingerprint"]
    snapshot = load(ctx)
    live = thread(fp)
    live["notes"][0]["author"] = {"username": "old-handle", "id": 42}
    snapshot["discussions"] = [live]
    memory = enriched(snapshot, ctx)["findings"][0]["memory"]
    assert memory["state"] == "carried" and memory["suppress_post"]


@pytest.mark.usefixtures("marker_form")
def test_missing_posting_identity_warns_and_refuses_to_trust_markers():
    ctx = context()
    ctx["change"].pop("current_username")
    fp = enriched(load(ctx), ctx)["findings"][0]["memory"]["fingerprint"]
    snapshot = load(ctx)
    snapshot["discussions"] = [thread(fp)]
    result = enriched(snapshot, ctx)
    memory = result["findings"][0]["memory"]
    assert memory["state"] == "new" and memory["suppress_post"] is False
    assert any("Posting identity unknown" in w for w in result["memory"]["warnings"])


@pytest.mark.usefixtures("marker_form")
def test_resolved_exact_is_visible_but_not_reposted_and_fuzzy_is_regression():
    previous = remember("fix", posted=True)
    fp = previous["findings"][0]["memory"]["fingerprint"]
    snapshot = load()
    snapshot["discussions"] = [thread(fp, resolved=True)]
    exact = enriched(snapshot)["findings"][0]["memory"]
    assert (exact["state"], exact["disposition"], exact["suppress_post"]) == (
        "re-found-after-resolution", "none", True)
    ctx = context()
    ctx["diff"] = ctx["diff"].replace("+new value", "+regressed value")
    result = enriched(snapshot, ctx)
    fuzzy = result["findings"][0]["memory"]
    assert (fuzzy["state"], fuzzy["match"], fuzzy["disposition"], fuzzy["suppress_post"]) == (
        "possible-regression", "candidate", "none", False)
    assert fuzzy["thread"]["note_id"] == 9
    assert result["memory"]["appears_fixed"] == []


def test_deleted_thread_does_not_suppress_and_seats_do_not_share_decisions():
    remember("fix", posted=True)
    result = enriched(load())
    assert result["findings"][0]["memory"]["disposition"] == "fix"
    assert not result["findings"][0]["memory"]["suppress_post"]
    ctx, value = context(), report()
    ctx["seat"] = value["meta"]["seat"] = "reviewer"
    result = enriched(load(ctx), ctx, value)
    assert result["findings"][0]["memory"]["disposition"] == "none"
    assert result["findings"][0]["memory"]["note"] == ""


@pytest.mark.usefixtures("marker_form")
def test_duplicate_anchor_identity_fails_toward_new_and_does_not_persist():
    previous = remember()
    fp = previous["findings"][0]["memory"]["fingerprint"]
    ctx, value, snapshot = context(), report(), load()
    ctx["diff"] += "@@ -3 +3 @@\n-old\n+new value\n"
    value["findings"].append({**value["findings"][0], "line": "3"})
    snapshot["discussions"] = [thread(fp)]
    result = enriched(snapshot, ctx, value)
    assert all(f["memory"]["fingerprint"] is None and not f["memory"]["suppress_post"]
               and f["memory"]["disposition"] == "none" for f in result["findings"])
    assert m.commit_report(result, decisions(result, "fix"))["saved"]
    assert load()["findings"][0]["disposition"] == "ignore"


def test_appears_fixed_requires_posted_finding_and_completed_coverage():
    remember()
    empty = report()
    empty["findings"] = []
    assert enriched(load(), value=empty)["memory"]["appears_fixed"] == []
    remember(posted=True)
    assert len(enriched(load(), value=empty)["memory"]["appears_fixed"]) == 1
    empty["run"]["dimensions_run"] = []
    assert enriched(load(), value=empty)["memory"]["appears_fixed"] == []
    empty["run"]["dimensions_run"] = [DIMENSION]
    ctx = context()
    ctx["not_text_reviewable"] = ["a.py"]
    assert enriched(load(ctx), ctx, empty)["memory"]["appears_fixed"] == []


@pytest.mark.parametrize("trigger", ["fresh", "base", "dimensions", "guidance"])
@pytest.mark.usefixtures("marker_form")
def test_invalidation_discards_decisions_not_live_posting_identity(trigger, tmp_path):
    first = remember()
    fp = first["findings"][0]["memory"]["fingerprint"]
    ctx, kwargs = context(), {}
    if trigger == "fresh":
        kwargs["fresh"] = True
    elif trigger == "base":
        ctx["refs"]["base"] = "c" * 40
    elif trigger == "guidance":
        guide = tmp_path / "guide.txt"
        guide.write_text("New guidance")
        kwargs["guidance"] = [guide]
    snapshot = (m.load_snapshot(ctx, dimensions=[DIMENSION, "db"]) if trigger == "dimensions"
                else load(ctx, **kwargs))
    assert snapshot["invalidation_reason"] and snapshot["findings"] == []
    snapshot["discussions"] = [thread(fp)]
    memory = enriched(snapshot, ctx)["findings"][0]["memory"]
    assert memory["disposition"] == "none" and memory["suppress_post"]


def test_head_and_start_change_preserve_decisions_and_guidance_paths_do_not_invalidate(tmp_path):
    a, b = tmp_path / "first.txt", tmp_path / "second.txt"
    a.write_text("Same guidance")
    b.write_text("Same guidance")
    value = enriched(load(guidance=[a]))
    assert m.commit_report(value, decisions(value))["saved"]
    ctx = context()
    ctx["refs"]["head"] = "c" * 40
    ctx["refs"]["start"] = "d" * 40
    snapshot = load(ctx, guidance=[b])
    assert snapshot["invalidation_reason"] is None and snapshot["unchanged_files"] == ["a.py"]
    new_report = report()
    new_report["meta"]["head_sha"] = ctx["refs"]["head"]
    assert enriched(snapshot, ctx, new_report)["findings"][0]["memory"]["disposition"] == "ignore"


def test_same_run_receipt_only_and_decision_saves_preserve_each_other():
    value = remember(fresh=True)
    receipt = {"F1": {"published": True, "note_id": 19}}
    assert m.commit_report(value, receipts=receipt)["saved"]
    assert m.commit_report(value, decisions(value, "later"))["saved"]
    stored = load()["findings"][0]
    assert stored["receipt"]["note_id"] == 19 and stored["disposition"] == "later"


def test_stale_writer_cannot_replace_newer_decision():
    old = enriched()
    newer = enriched()
    newer["memory"]["snapshot"]["started_at"] = old["memory"]["snapshot"]["started_at"] + 1
    assert m.commit_report(newer, decisions(newer, "later"))["saved"]
    assert not m.commit_report(old, decisions(old, "ignore"))["saved"]
    assert load()["findings"][0]["disposition"] == "later"


def test_decisions_bind_entire_report_and_complete_id_set():
    value = enriched()
    choice = decisions(value)
    changed = copy.deepcopy(value)
    changed["memory"]["warnings"].append("Different report")
    with pytest.raises(ValueError):
        m.commit_report(changed, choice)
    choice["decisions"] = []
    with pytest.raises(ValueError):
        m.commit_report(value, choice)


@pytest.mark.parametrize("content", ['{"schemaVersion":99}', '[]', '{"schemaVersion":"1"}', 'not json'])
def test_corrupt_or_future_ledger_is_never_overwritten(content):
    snapshot = load()
    ledger = m._state_dir() / (snapshot["target_key"] + ".json")
    ledger.write_text(content)
    value = enriched(load())
    assert value["memory"]["warnings"]
    assert not m.commit_report(value, decisions(value))["saved"]
    assert ledger.read_text() == content


def anchored_report(side):
    value = report()
    value["findings"][0]["anchor_side"] = side
    return value


def test_old_side_finding_is_fingerprinted_from_the_removed_line():
    old = enriched(value=anchored_report("old"))["findings"][0]["memory"]
    new = enriched(value=anchored_report("new"))["findings"][0]["memory"]
    assert old["fingerprint"] == m._fingerprint(DIMENSION, "a.py", "old")[0]
    assert new["fingerprint"] == m._fingerprint(DIMENSION, "a.py", "new value")[0]
    assert old["fingerprint"] != new["fingerprint"]
    default = enriched()["findings"][0]["memory"]
    assert default["fingerprint"] == new["fingerprint"]


def test_old_side_anchor_on_an_added_line_has_no_fingerprint():
    value = anchored_report("old")
    value["findings"][0]["line"] = "2"
    result = enriched(value=value)
    assert result["findings"][0]["memory"]["fingerprint"] is None
    assert any("No unique nonblank diff anchor" in w for w in result["memory"]["warnings"])


@pytest.mark.parametrize("side", ["both", "", None, 1])
def test_invalid_anchor_side_is_rejected(side):
    with pytest.raises(ValueError, match="anchor_side"):
        enriched(value=anchored_report(side))


def test_human_thread_context_does_not_suppress_without_anchor():
    snapshot, value = load(), report()
    value["findings"][0]["line"] = "99"
    snapshot["discussions"] = [{"id": "human", "notes": [{"id": 7, "body": "Check this edge",
        "author": {"username": "human"}, "position": {"new_path": "a.py", "new_line": 99}}]}]
    memory = enriched(snapshot, value=value)["findings"][0]["memory"]
    assert memory["fingerprint"] is None and memory["disposition"] == "none" and not memory["suppress_post"]
    assert memory["human_context"][0]["author"] == "human"


def test_human_context_marks_the_posting_identitys_own_comments():
    ctx = context()
    ctx["change"]["current_user_id"] = 42
    snapshot = load(ctx)

    def positioned(note_id, author):
        return {"id": "d%s" % note_id, "notes": [{"id": note_id, "body": "Check this edge",
                "author": author, "position": {"new_path": "a.py", "new_line": 1}}]}
    snapshot["discussions"] = [
        positioned(1, {"username": "author"}),
        positioned(2, {"username": "old-handle", "id": 42}),
        positioned(3, {"username": "human", "id": 7}),
    ]
    context_rows = enriched(snapshot, ctx)["findings"][0]["memory"]["human_context"]
    assert [(row["note_id"], row["own"]) for row in context_rows] == [(1, True), (2, True), (3, False)]


@pytest.mark.parametrize("discussion_id, note_id", [("d1", None), ("d1", True), ("", 1), (5, 1)])
def test_human_context_drops_a_record_without_usable_ids(discussion_id, note_id):
    snapshot = load()
    snapshot["discussions"] = [
        {"id": discussion_id, "notes": [{"id": note_id, "body": "Odd", "author": {"username": "x"},
                                         "position": {"new_path": "a.py", "new_line": 1}}]},
        {"id": "d2", "notes": [{"id": 2, "body": "Fine", "author": {"username": "human"},
                                "position": {"new_path": "a.py", "new_line": 1}}]},
    ]
    rows = enriched(snapshot)["findings"][0]["memory"]["human_context"]
    assert [(row["discussion_id"], row["note_id"]) for row in rows] == [("d2", 2)]


def test_discussions_pagination_reaches_second_page_and_rejects_duplicates():
    pages = [[{"id": str(i), "notes": []} for i in range(100)], [{"id": "last", "notes": []}]]
    calls = []
    def api(host, method, endpoint, payload=None):
        calls.append((method, endpoint))
        return pages[int(endpoint.rsplit("=", 1)[1]) - 1]
    assert FETCH_DISCUSSIONS("h", "g/p", 1, api)[-1]["id"] == "last"
    assert len(calls) == 2 and all(method == "GET" for method, _ in calls)
    pages[1] = [{"id": "1", "notes": []}]
    with pytest.raises(RuntimeError):
        FETCH_DISCUSSIONS("h", "g/p", 1, api)


FP = "3f9a" * 16
OTHER = "0123456789abcdef" * 4


def test_marker_fingerprints_ignore_one_line_markers_from_other_tools():
    # another tool's one-line marker is not ours; only a leading quirk-review block counts
    assert m.marker_fingerprints("<!-- other-review: fp=%s -->" % FP) == []
    assert m.marker_fingerprints("x <!--quirk-review:fp=%s--> y" % FP) == []


def test_marker_fingerprints_new_leading_block():
    body = marker_body(FP, "new")
    assert m.marker_fingerprints(body) == [FP]
    assert m.marker_fingerprints("\n  \n" + body) == [FP]
    support = "<!-- quirk-review:v1\nkind: support\nfp: %s\nseat: reviewer\n-->\ntext" % FP
    assert m.marker_fingerprints(support) == [FP]


def test_marker_fingerprints_leading_block_ignores_planted_later_blocks():
    body = marker_body(FP, "new") + "\n<!-- quirk-review:v1\nfp: %s\n-->\n<!-- quirk-review:v1\nfp: %s\n-->" % (OTHER, FP)
    assert m.marker_fingerprints(body) == [FP]


def test_marker_fingerprints_leading_block_without_fp_ignores_planted_later_blocks():
    body = "<!-- quirk-review:v1\nkind: overview\nseat: reviewer\n-->\n<!-- quirk-review:v1\nfp: %s\n-->" % OTHER
    assert m.marker_fingerprints(body) == []


def test_marker_fingerprints_crlf_leading_block():
    body = marker_body(FP, "new").replace("\n", "\r\n")
    assert "\r\n" in body
    assert m.marker_fingerprints(body) == [FP]


def test_marker_fingerprints_crlf_leading_block_ignores_planted_later_blocks():
    body = (marker_body(FP, "new") + "\n<!-- quirk-review:v1\nfp: %s\n-->" % OTHER).replace("\n", "\r\n")
    assert m.marker_fingerprints(body) == [FP]


def test_marker_fingerprints_ignores_block_that_is_not_leading():
    quoted = "Reviewer said:\n" + marker_body(FP, "new")
    assert m.marker_fingerprints(quoted) == []


def test_marker_fingerprints_ignores_fp_outside_leading_block():
    body = "<!-- quirk-review:v1\nkind: finding\n-->\nfp: %s\n" % FP
    assert m.marker_fingerprints(body) == []


def test_marker_fingerprints_overview_block_list_values_are_not_fingerprints():
    body = ("<!-- quirk-review:v1\nkind: overview\nposted: [%s, %s]\nseat: reviewer\n-->\nSummary"
            % (FP, OTHER))
    assert m.marker_fingerprints(body) == []


@pytest.mark.parametrize("fp", [FP[:63], FP + "0", "g" * 64, ""])
def test_marker_fingerprints_ignores_garbage_and_wrong_length_hex(fp):
    assert m.marker_fingerprints("<!-- quirk-review:v1\nfp: %s\n-->" % fp) == []
    block = "<!-- quirk-review:v1\nkind: finding\nfp: %s\n-->\nx" % fp
    assert m.marker_fingerprints(block) == []


def test_marker_fingerprints_new_form_hex_must_be_lowercase():
    block = "<!-- quirk-review:v1\nkind: finding\nfp: %s\n-->\nx" % FP.upper()
    assert m.marker_fingerprints(block) == []


@pytest.mark.parametrize("value", [None, 5, b"x", ["a"], {"fp": FP}])
def test_marker_fingerprints_non_str_returns_empty(value):
    assert m.marker_fingerprints(value) == []


def live_discussions(monkeypatch, discussions):
    monkeypatch.setattr(m, "fetch_discussions", lambda *args, **kwargs: discussions)


def plan_for(snapshot, value=None, ctx=None):
    return m.check_plan(value or report(), ctx or context(), snapshot)["findings"]


def test_check_plan_suppresses_a_finding_already_posted_by_this_identity(monkeypatch):
    fp = enriched()["findings"][0]["memory"]["fingerprint"]
    live_discussions(monkeypatch, [thread(fp)])
    [row] = plan_for(load())
    assert (row["id"], row["fingerprint"], row["suppress_post"], row["state"]) == ("F1", fp, True, "carried")
    assert row["thread"]["note_id"] == 9


def test_check_plan_suppresses_a_resolved_thread_and_labels_it(monkeypatch):
    fp = enriched()["findings"][0]["memory"]["fingerprint"]
    live_discussions(monkeypatch, [thread(fp, resolved=True)])
    [row] = plan_for(load())
    assert (row["suppress_post"], row["state"]) == (True, "re-found-after-resolution")


def test_check_plan_does_not_suppress_on_a_human_comment_or_a_forged_marker(monkeypatch):
    fp = enriched()["findings"][0]["memory"]["fingerprint"]
    human = {"id": "h1", "notes": [{"id": 3, "body": "Check this", "author": {"username": "human"},
                                    "position": {"new_path": "a.py", "new_line": 1}}]}
    live_discussions(monkeypatch, [human, thread(fp, author="someone-else", note_id=4)])
    [row] = plan_for(load())
    assert (row["suppress_post"], row["state"], row["thread"]) == (False, "new", None)


def test_check_plan_treats_a_finding_with_no_thread_as_fresh(monkeypatch):
    live_discussions(monkeypatch, [])
    [row] = plan_for(load())
    assert (row["suppress_post"], row["state"], row["thread"]) == (False, "new", None)
    assert row["fingerprint"]


def test_check_plan_ids_follow_severity_rank_not_report_order(monkeypatch):
    live_discussions(monkeypatch, [])
    value = report()
    value["findings"].append({"severity": "Must fix", "dimension": DIMENSION, "file": "b.py", "line": "1",
                              "title": "Worse", "body_md": "Worse defect"})
    rows = plan_for(load(), value)
    assert [row["id"] for row in rows] == ["F2", "F1"]


def test_check_plan_refuses_when_the_live_cross_check_fails_and_leaves_inputs_alone(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("offline")
    monkeypatch.setattr(m, "fetch_discussions", broken)
    value, ctx, snapshot = report(), context(), load()
    before = copy.deepcopy((value, ctx, snapshot))
    with pytest.raises(RuntimeError, match="cross-check unavailable"):
        m.check_plan(value, ctx, snapshot)
    assert (value, ctx, snapshot) == before


def test_check_plan_resolves_branch_identity_against_the_given_repo(monkeypatch):
    def origin(*args, repo=".", **kwargs):
        if args[0] == "config":
            return "git@gitlab.example:group/%s.git" % ("reviewed" if repo == "/reviewed" else "cwd")
        return "feature/x"
    monkeypatch.setattr(m, "_git", origin)
    ctx = {"mode": "branch", "seat": "author", "source_branch": "feature/x",
           "refs": {"base": BASE, "start": BASE, "head": HEAD}, "diff": context()["diff"]}
    value = report()
    value["meta"] = {"target": "branch", "branch": "feature/x", "seat": "author", "head_sha": HEAD,
                     "title": "Review", "verdict": "Fix first"}
    snapshot = m.load_snapshot(ctx, repo="/reviewed", dimensions=[DIMENSION])
    [row] = m.check_plan(value, ctx, snapshot, repo="/reviewed")["findings"]
    assert row["fingerprint"]
    with pytest.raises(ValueError, match="identity"):
        m.check_plan(value, ctx, snapshot, repo="/elsewhere")


def cli(tmp_path, capsys, *argv):
    rc = m.main(list(argv))
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def write_json(tmp_path, name, value):
    path = tmp_path / name
    path.write_text(json.dumps(value))
    return str(path)


def test_cli_load_reconcile_check_save_round_trip(tmp_path, capsys):
    ctx = write_json(tmp_path, "context.json", context())
    snap_path = str(tmp_path / "snapshot.json")
    assert cli(tmp_path, capsys, "load", "--context", ctx, "--dimension", DIMENSION,
               "--out", snap_path)[0] == 0
    assert json.loads(open(snap_path).read())["identity"]["number"] == "7"

    enriched_path = str(tmp_path / "enriched.json")
    rc, _, _ = cli(tmp_path, capsys, "reconcile", "--report", write_json(tmp_path, "report.json", report()),
                   "--context", ctx, "--snapshot", snap_path, "--out", enriched_path)
    assert rc == 0
    value = json.loads(open(enriched_path).read())
    assert value["findings"][0]["memory"]["state"] == "new"

    plan_path = str(tmp_path / "plan.json")
    rc, _, _ = cli(tmp_path, capsys, "check", "--report", enriched_path, "--context", ctx, "--out", plan_path)
    assert rc == 0 and json.loads(open(plan_path).read())["findings"][0]["id"] == "F1"

    rc, out, _ = cli(tmp_path, capsys, "save", "--report", enriched_path,
                     "--decisions", write_json(tmp_path, "decisions.json", decisions(value, "later")))
    assert rc == 0 and json.loads(out)["saved"] is True
    assert load()["findings"][0]["disposition"] == "later"


def test_cli_check_without_any_snapshot_is_an_input_error(tmp_path, capsys):
    rc, _, err = cli(tmp_path, capsys, "check", "--report", write_json(tmp_path, "report.json", report()),
                     "--context", write_json(tmp_path, "context.json", context()),
                     "--out", str(tmp_path / "plan.json"))
    assert rc == 2 and "--snapshot" in json.loads(err)["error"]


def test_cli_save_requires_decisions_or_receipts(tmp_path, capsys):
    rc, _, err = cli(tmp_path, capsys, "save", "--report", write_json(tmp_path, "report.json", enriched()))
    assert rc == 2 and "--decisions or --receipts" in json.loads(err)["error"]


def test_cli_save_exits_1_with_json_on_stdout_when_nothing_was_persisted(tmp_path, capsys):
    old, newer = enriched(), enriched()
    newer["memory"]["snapshot"]["started_at"] = old["memory"]["snapshot"]["started_at"] + 1
    assert m.commit_report(newer, decisions(newer, "later"))["saved"]
    rc, out, _ = cli(tmp_path, capsys, "save", "--report", write_json(tmp_path, "old.json", old),
                     "--decisions", write_json(tmp_path, "decisions.json", decisions(old, "ignore")))
    result = json.loads(out)
    assert rc == 1 and result["saved"] is False and "stale review run" in result["warnings"][0]


def test_unreadable_ledger_warnings_name_the_file_to_fix():
    snapshot = load()
    ledger = m._state_dir() / (snapshot["target_key"] + ".json")
    ledger.write_text("not json")
    value = enriched(load())
    assert any(str(ledger) in warning for warning in value["memory"]["warnings"])
    refused = m.commit_report(value, decisions(value))
    assert not refused["saved"]
    assert any(str(ledger) in warning for warning in refused["warnings"])
