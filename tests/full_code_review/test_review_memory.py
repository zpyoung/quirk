import copy
import hashlib
import json
import os
import time

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


def marker_body(fp):
    return ("<!-- quirk-review:v1\nkind: finding\nfp: %s\nseat: reviewer\nfile: a.py\nline: 1\n-->\n"
            "**Blocking** \u00b7 Finding" % fp)


def thread(fp, resolved=False, note_id=9, author="author"):
    # the marker note is written by whoever ran the review, i.e. context()'s current_username
    return {"id": "discussion-%s" % note_id,
            "notes": [{"id": note_id, "body": marker_body(fp),
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


def test_committing_an_invalidated_run_drops_entries_it_did_not_re_find():
    old_fp = remember("ignore")["findings"][0]["memory"]["fingerprint"]
    ctx = context()
    ctx["diff"] = ctx["diff"].replace("+new value", "+another value")
    snapshot = m.load_snapshot(ctx, dimensions=[DIMENSION], fresh=True)
    value = m.reconcile(report(), ctx, snapshot)
    new_fp = value["findings"][0]["memory"]["fingerprint"]
    assert new_fp != old_fp
    assert m.commit_report(value, decisions(value, "fix"))["saved"]
    assert [row["fingerprint"] for row in load()["findings"]] == [new_fp]


def test_commit_prunes_ledgers_untouched_past_retention():
    remember()
    live = next(m._state_dir().glob("*.json"))
    record = json.loads(live.read_text())
    record["updated_at"] = time.time() - m._RETENTION_SECONDS - 60
    stale = m._state_dir() / ("e" * 64 + ".json")
    stale.write_text(json.dumps(record))
    unreadable = m._state_dir() / "broken.json"
    unreadable.write_text("not json")
    remember()
    assert not stale.exists()
    assert live.exists() and unreadable.exists()


def test_commit_prunes_an_unreadable_ledger_by_file_age():
    remember()
    broken = m._state_dir() / "broken.json"
    broken.write_text("not json")
    old = time.time() - m._RETENTION_SECONDS - 60
    os.utime(broken, (old, old))
    remember()
    assert not broken.exists()


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
    assert old["fingerprint"] == m._fingerprint("a.py", "old")[0]
    assert new["fingerprint"] == m._fingerprint("a.py", "new value")[0]
    assert old["fingerprint"] != new["fingerprint"]
    default = enriched()["findings"][0]["memory"]
    assert default["fingerprint"] == new["fingerprint"]


def test_old_side_anchor_on_an_added_line_has_no_fingerprint():
    value = anchored_report("old")
    value["findings"][0]["line"] = "2"
    result = enriched(value=value)
    assert result["findings"][0]["memory"]["fingerprint"] is None
    assert any("No unique nonblank diff anchor" in w for w in result["memory"]["warnings"])


NEW_FILE_DIFF = ("diff --git a/doc.py b/doc.py\nnew file mode 100644\n--- /dev/null\n+++ b/doc.py\n"
                 "@@ -0,0 +1,6 @@\n+\"\"\"Title.\n+\n+first body line\n+second body line\n+\n+\"\"\"\n")


@pytest.mark.parametrize("line, expected", [
    ("2-4", "first body line"),
    ("5-6", '"""'),
    ("2", None),
    ("5", None),
])
def test_range_starting_on_blank_lines_anchors_on_its_first_nonblank_line(line, expected):
    assert m._anchor(NEW_FILE_DIFF, "doc.py", line) == expected


def test_range_whose_first_nonblank_line_repeats_has_no_anchor():
    diff = NEW_FILE_DIFF.replace("second body line", "first body line")
    assert m._anchor(diff, "doc.py", "2-4") == "first body line"
    duplicated = diff + ("diff --git a/doc.py b/doc.py\n--- a/doc.py\n+++ b/doc.py\n"
                         "@@ -1,0 +3,1 @@\n+other\n")
    assert m._anchor(duplicated, "doc.py", "2-4") is None


def test_finding_on_a_blank_leading_range_gets_a_fingerprint():
    ctx = context()
    ctx["diff"] = NEW_FILE_DIFF
    ctx["changed_files"] = ["doc.py"]
    value = report()
    value["findings"][0].update({"file": "doc.py", "line": "2-4"})
    result = enriched(load(ctx), ctx, value)
    assert result["findings"][0]["memory"]["fingerprint"] == m._fingerprint(
        "doc.py", "first body line")[0]
    assert not any("No unique nonblank diff anchor" in w for w in result["memory"]["warnings"])


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
    body = marker_body(FP)
    assert m.marker_fingerprints(body) == [FP]
    assert m.marker_fingerprints("\n  \n" + body) == [FP]
    support = "<!-- quirk-review:v1\nkind: support\nfp: %s\nseat: reviewer\n-->\ntext" % FP
    assert m.marker_fingerprints(support) == [FP]


def test_marker_fingerprints_leading_block_ignores_planted_later_blocks():
    body = marker_body(FP) + "\n<!-- quirk-review:v1\nfp: %s\n-->\n<!-- quirk-review:v1\nfp: %s\n-->" % (OTHER, FP)
    assert m.marker_fingerprints(body) == [FP]


def test_marker_fingerprints_leading_block_without_fp_ignores_planted_later_blocks():
    body = "<!-- quirk-review:v1\nkind: overview\nseat: reviewer\n-->\n<!-- quirk-review:v1\nfp: %s\n-->" % OTHER
    assert m.marker_fingerprints(body) == []


def test_marker_fingerprints_crlf_leading_block():
    body = marker_body(FP).replace("\n", "\r\n")
    assert "\r\n" in body
    assert m.marker_fingerprints(body) == [FP]


def test_marker_fingerprints_crlf_leading_block_ignores_planted_later_blocks():
    body = (marker_body(FP) + "\n<!-- quirk-review:v1\nfp: %s\n-->" % OTHER).replace("\n", "\r\n")
    assert m.marker_fingerprints(body) == [FP]


def test_marker_fingerprints_ignores_block_that_is_not_leading():
    quoted = "Reviewer said:\n" + marker_body(FP)
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


def test_cli_input_errors_name_the_offending_flag(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    rc, _, err = cli(tmp_path, capsys, "reconcile", "--report", write_json(tmp_path, "report.json", report()),
                     "--context", write_json(tmp_path, "context.json", context()), "--snapshot", str(bad),
                     "--out", str(tmp_path / "out.json"))
    assert rc == 2 and "--snapshot" in json.loads(err)["error"]


def header_diff(header, plus="+++ b/{p}", minus="--- a/{p}", path="x.py", extra=""):
    return ("%s\n%s%s\n%s\n@@ -1 +1 @@\n-old\n+new value\n" % (
        header, extra, minus.format(p=path), plus.format(p=path)))


@pytest.mark.parametrize("path, header", [
    ("my file.py", "diff --git a/my file.py b/my file.py"),
    ("my file.py", 'diff --git "a/my file.py" "b/my file.py"'),
    ("caf\u00e9.py", 'diff --git "a/caf\\303\\251.py" "b/caf\\303\\251.py"'),
    ("caf\u00e9.py", "diff --git a/caf\u00e9.py b/caf\u00e9.py"),
    ("tab\there.py", 'diff --git "a/tab\\there.py" "b/tab\\there.py"'),
])
def test_diff_headers_with_spaced_quoted_or_non_ascii_paths_are_anchored_and_hashed(path, header):
    quoted = header.startswith('diff --git "')
    plain = path.replace("\t", "\\t")
    diff = header + "\n" + ('--- "a/%s"\n+++ "b/%s"' % (plain, plain) if quoted
                            else "--- a/%s\n+++ b/%s" % (path, path)) + "\n@@ -1 +1 @@\n-old\n+new value\n"
    assert m._anchor(diff, path, "1") == "new value"
    assert m._anchor(diff, path, "1", "old") == "old"
    assert list(m._file_hashes({"diff": diff})) == [path]


def test_quoted_rename_header_matches_old_and_new_paths():
    diff = ('diff --git "a/old name.py" "b/new name.py"\nsimilarity index 80%\n'
            'rename from old name.py\nrename to new name.py\n'
            '--- "a/old name.py"\n+++ "b/new name.py"\n@@ -1 +1 @@\n-old\n+new value\n')
    assert m._anchor(diff, "new name.py", "1") == "new value"
    assert m._anchor(diff, "old name.py", "1", "old") == "old"
    assert list(m._file_hashes({"diff": diff})) == ["new name.py"]


@pytest.mark.parametrize("separator", ["\x0c", "\u2028", "\x85", "\x1c"])
def test_line_separators_inside_a_line_do_not_shift_anchors_or_sections(separator):
    diff = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,3 @@\n a = 1\n"
            " x%s y\n b = 2\n"
            "+z%sdiff --git a/zz b/zz\n" % (separator, separator))
    assert m._anchor(diff, "a.py", "2") == "x%s y" % separator
    assert m._anchor(diff, "a.py", "3") == "b = 2"
    assert list(m._file_hashes({"diff": diff})) == ["a.py"]


def test_fingerprint_survives_a_change_in_which_lenses_flagged_the_line():
    remember("fix")
    value = report()
    value["findings"][0]["dimension"] = "aaa-earlier-lens"
    memory = enriched(load(), value=value)["findings"][0]["memory"]
    assert memory["dimension"] == "aaa-earlier-lens"
    assert memory["match"] == "exact" and memory["disposition"] == "fix"


def repeated_line_ctx():
    ctx = context()
    ctx["diff"] = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,4 @@\n"
                   " keep\n+    return None\n+other\n+    return None\n")
    return ctx


def repeated_line_report(line, title, body):
    value = report()
    value["findings"][0].update({"line": line, "title": title, "body_md": body})
    return value


def test_unrelated_finding_on_an_identical_anchor_line_does_not_inherit_a_decision():
    ctx = repeated_line_ctx()
    first = enriched(load(ctx), ctx, repeated_line_report(
        "2", "Silent None hides refund failure", "Returning None here makes the caller skip the refund."))
    fp = first["findings"][0]["memory"]["fingerprint"]
    assert m.commit_report(first, decisions(first, "ignore", "Intentional"))["saved"]
    ctx = context()
    ctx["diff"] = repeated_line_ctx()["diff"].replace("+other\n+    return None\n", "+other\n")
    ctx["diff"] = ctx["diff"].replace("@@ -1,2 +1,4 @@", "@@ -1,2 +1,3 @@")
    snapshot = load(ctx)
    snapshot["discussions"] = [thread(fp)]
    value = repeated_line_report("2", "Race in cache eviction", "Two workers evict the same key concurrently.")
    result = enriched(snapshot, ctx, value)
    memory = result["findings"][0]["memory"]
    assert memory["fingerprint"] == fp
    assert (memory["state"], memory["match"], memory["disposition"], memory["suppress_post"]) == (
        "new", None, "none", False)
    assert memory["thread"] is None
    assert any("different text" in w for w in result["memory"]["warnings"])


def test_same_finding_on_a_repeated_anchor_line_still_matches_after_rewording():
    remember("fix")
    value = report()
    value["findings"][0]["body_md"] = "The selected value breaks refunds badly."
    memory = enriched(load(), value=value)["findings"][0]["memory"]
    assert memory["match"] == "exact" and memory["disposition"] == "fix"


def test_ledger_without_a_fingerprint_scheme_is_migrated_with_fingerprints_recomputed_from_anchor_hashes():
    value = remember("fix")
    new_fp = value["findings"][0]["memory"]["fingerprint"]
    path = m._state_dir() / (value["memory"]["snapshot"]["target_key"] + ".json")
    record = json.loads(path.read_text())
    entry = record["snapshot"]["findings"][0]
    old_fp = hashlib.sha256((DIMENSION + "\0a.py\0" + entry["anchor_hash"]).encode()).hexdigest()
    entry["fingerprint"] = old_fp
    del record["fingerprintScheme"]
    path.write_text(json.dumps(record))
    snapshot = load()
    assert snapshot["findings"][0]["fingerprint"] == new_fp != old_fp
    assert any("migrated memory ledger to fingerprint scheme 2" in w for w in snapshot["warnings"])
    assert enriched(snapshot)["findings"][0]["memory"]["disposition"] == "fix"
    assert m.commit_report(enriched(snapshot), decisions(enriched(snapshot), "later"))["saved"]
    assert json.loads(path.read_text())["fingerprintScheme"] == m.FINGERPRINT_SCHEME


def test_migration_drops_entries_whose_fingerprints_collapse_together():
    value = remember("fix")
    path = m._state_dir() / (value["memory"]["snapshot"]["target_key"] + ".json")
    record = json.loads(path.read_text())
    first = record["snapshot"]["findings"][0]
    second = copy.deepcopy(first)
    second["dimension"] = "db"
    first["fingerprint"], second["fingerprint"] = "1" * 64, "2" * 64
    record["snapshot"]["findings"] = [first, second]
    del record["fingerprintScheme"]
    path.write_text(json.dumps(record))
    snapshot = load()
    assert snapshot["findings"] == []
    assert any("became ambiguous" in w for w in snapshot["warnings"])
