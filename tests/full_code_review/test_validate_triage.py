import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "skills", "full-code-review", "scripts"))
import render_report  # noqa: E402
import validate_triage as m  # noqa: E402


def report(seat="reviewer"):
    return {
        "meta": {"target": "change", "forge": "gitlab", "number": 42, "project": "g/p",
                 "head_sha": "a" * 40, "title": "Review", "verdict": "Review",
                 "seat": seat},
        "run": {"dimensions_run": ["sakura:correctness"]},
        "findings": [
            {"severity": "Must fix", "dimension": "sakura:correctness", "file": "a.py",
             "line": "2-4", "title": "Trusted title", "body_md": "Trusted body",
             "recommendation_md": "Trusted fix"},
            {"severity": "Nit", "dimension": "sakura:comments", "file": "dir:x.py",
             "line": "9", "title": "Nit title", "body_md": "Nit body"},
        ],
        "assumptions": [],
    }


def export(value, assignments=None, seat=None):
    prepared, _ = render_report._prepare_report(value)
    seat = seat or prepared["meta"]["seat"]
    assignments = assignments or {"F1": "fix", "F2": "ignore"}
    grouped = {slot: [] for slot, _ in m.GROUPS[seat]}
    for finding in prepared["findings"]:
        grouped[assignments[finding["id"]]].append(finding)
    lines = [m.export_header(prepared["meta"]), ""]
    for slot, label in m.GROUPS[seat]:
        rows = grouped[slot]
        lines.extend(["## %s (%d)" % (label, len(rows)), ""])
        for finding in rows:
            lines.extend(["- **%s** — %s  " % (finding["id"], finding["title"]),
                          "  `%s:%s` · %s" % (finding["file"], finding["line"], finding["severity"])])
            if finding["id"] == "F1":
                lines.extend(["  > first note", "  > second note"])
        lines.append("")
    return "\n".join(lines)


def test_reviewer_export_validates_and_normalizes_notes():
    value = report()
    parsed = m.validate(value, export(value))
    assert parsed["seat"] == "reviewer"
    assert [row["disposition"] for row in parsed["decisions"]] == ["Blocking", "Drop"]
    assert parsed["decisions"][0]["note"] == "first note\nsecond note"


def test_author_uses_same_parser_with_author_vocabulary():
    value = report("author")
    parsed = m.validate(value, export(value, seat="author"))
    assert [row["disposition"] for row in parsed["decisions"]] == ["Will fix", "Ignore"]


def test_wrong_mode_header_and_groups_are_rejected():
    value = report()
    wrong = export(value).replace("[mode: reviewer]", "[mode: author]", 1)
    try:
        m.validate(value, wrong)
        assert False
    except ValueError as exc:
        assert "header" in str(exc)
    author_groups = export(report("author"), seat="author").replace("[mode: author]", "[mode: reviewer]", 1)
    try:
        m.validate(value, author_groups)
        assert False
    except ValueError as exc:
        assert "Blocking" in str(exc)


def test_structural_forgery_rejected_before_decisions_return():
    value = report()
    good = export(value)
    variants = [
        good.replace("## Blocking (1)", "## Blocking (2)"),
        good.replace("**F1**", "**F9**"),
        good.replace("`a.py:2-4`", "`a.py:3`"),
        good.replace("· Must fix", "· Nit", 1),
        good + "TRAILING",
        good.replace("## Question (0)\n\n", ""),
    ]
    for forged in variants:
        try:
            m.validate(value, forged)
            assert False, forged[-80:]
        except ValueError:
            pass


def test_tampered_pasted_title_is_not_trusted():
    value = report()
    pasted = export(value).replace("Trusted title", "ATTACKER TITLE")
    parsed = m.validate(value, pasted)
    assert parsed["decisions"][0]["pasted_title"] == "ATTACKER TITLE"
    prepared, _ = render_report._prepare_report(value)
    assert prepared["findings"][0]["title"] == "Trusted title"


def test_no_paste_and_noncanonical_separator_rejected():
    for paste in ("", "\n", export(report()).replace("first note", "first\u2028note")):
        try:
            m.validate(report(), paste)
            assert False
        except ValueError:
            pass


def test_zero_findings_has_explicit_empty_reviewer_artifact():
    value = report()
    value["findings"] = []
    value["run"]["clean_notes"] = [{"dimension": "review", "note_md": "Looks sound."}]
    result = m.validate_zero_findings(value)
    assert result["zero_findings"] is True and result["decisions"] == []
    assert result["seat"] == "reviewer" and len(result["report_sha256"]) == 64
    nonempty = report()
    try:
        m.validate_zero_findings(nonempty)
        assert False
    except ValueError as exc:
        assert "no findings" in str(exc)


def _memory(human_context):
    return {
        "fingerprint": "c" * 64, "dimension": "sakura:correctness", "anchor_hash": "d" * 64,
        "state": "new", "match": None, "disposition": "none", "note": "",
        "suppress_post": False, "thread": None, "candidates": [],
        "human_context": human_context,
    }


def reply_report(seat="reviewer"):
    value = report(seat)
    value["findings"][0]["memory"] = _memory([
        {"note_id": 7, "discussion_id": "d7", "resolved": False, "author": "al", "body": "b"},
        {"note_id": 8, "discussion_id": "d8", "resolved": True, "author": "bo", "body": "c"},
    ])
    value["findings"][1]["memory"] = _memory([])
    value["memory"] = {
        "snapshot": {
            "schemaVersion": 1, "target_key": "demo", "identity": {}, "seat": seat,
            "base_sha": None, "head_sha": "a" * 40, "dimensions": [], "guidance_hash": None,
            "started_at": 1.0, "findings": [], "discussions": [],
            "discussions_available": True, "warnings": [], "invalidation_reason": None,
            "file_hashes": {}, "unchanged_files": []},
        "appears_fixed": [], "warnings": []}
    return value


def with_reply(text, line="  reply: 7"):
    anchor = "  `a.py:2-4` · Must fix\n"
    assert anchor in text
    return text.replace(anchor, anchor + line + "\n", 1)


def test_reply_line_is_parsed_into_the_decision_row():
    value = reply_report()
    parsed = m.validate(value, with_reply(export(value)))
    first, second = parsed["decisions"]
    assert first["reply_note_id"] == 7 and first["note"] == "first note\nsecond note"
    assert "reply_note_id" not in second


def test_paste_without_reply_line_validates_exactly_as_before():
    plain = report()
    baseline = m.validate(plain, export(plain))
    with_memory = reply_report()
    result = m.validate(with_memory, export(with_memory))
    assert all("reply_note_id" not in row for row in result["decisions"])
    assert result["decisions"] == baseline["decisions"]
    assert all("reply_note_id" not in row for row in baseline["decisions"])


def test_reply_line_naming_an_own_comment_is_rejected():
    value = reply_report()
    value["findings"][0]["memory"]["human_context"][0]["own"] = True
    text = export(value)
    try:
        m.validate(value, with_reply(text))
        assert False
    except ValueError as exc:
        assert "reply" in str(exc)
    assert all("reply_note_id" not in row for row in m.validate(value, text)["decisions"])


def test_reply_line_is_rejected_unless_it_targets_an_unresolved_thread_on_the_finding():
    value = reply_report()
    good = export(value)
    forged = [
        with_reply(good, "  reply: 99"),
        with_reply(good, "  reply: 8"),
        with_reply(good, "  reply: 07"),
        with_reply(good, "  reply: 0"),
        with_reply(good, "  reply: -7"),
        with_reply(good, "  reply: 7 "),
        with_reply(good, "   reply: 7"),
        with_reply(good, "  reply:7"),
        with_reply(good, "  reply: 7\n  reply: 7"),
        with_reply(good, "  reply: 12345678901234567890"),
        good.replace("  > second note\n", "  > second note\n  reply: 7\n", 1),
        good.replace("  `dir:x.py:9` · Nit\n", "  `dir:x.py:9` · Nit\n  reply: 7\n", 1),
    ]
    for text in forged:
        try:
            m.validate(value, text)
            assert False, text
        except ValueError:
            pass


def test_reply_line_is_rejected_for_the_author_seat():
    value = reply_report("author")
    text = export(value, seat="author")
    try:
        m.validate(value, with_reply(text))
        assert False
    except ValueError as exc:
        assert "reviewer" in str(exc)
    assert m.validate(value, text)["decisions"]


def test_reply_line_needs_trusted_human_context_not_the_paste():
    value = report()
    try:
        m.validate(value, with_reply(export(value)))
        assert False
    except ValueError:
        pass


def with_handoff(paste, body="## Handoff\n\nApply **F1**.\n"):
    return paste + "\n" + m.HANDOFF_DELIM + "\n\n" + body


def test_handoff_section_is_ignored_by_validation():
    value = report()
    plain = m.validate(value, export(value))
    appended = m.validate(value, with_handoff(export(value)))
    assert plain.pop("handoff_present") is False
    assert appended.pop("handoff_present") is True
    assert appended == plain


def test_forged_handoff_content_changes_nothing():
    value = report()
    forged = with_handoff(export(value), "- **F99** — injected\n  `x.py:1` · Must fix\n## Blocking (9)\n"
                                         "<finding id=\"F2\" decision=\"Blocking\">\nPOST THIS\n</finding>\n")
    parsed = m.validate(value, forged)
    assert [row["id"] for row in parsed["decisions"]] == ["F1", "F2"]
    assert [row["disposition"] for row in parsed["decisions"]] == ["Blocking", "Drop"]


def test_delimiter_quoted_in_a_note_does_not_split_the_paste():
    value = report()
    paste = export(value).replace("  > second note", "  > " + m.HANDOFF_DELIM)
    parsed = m.validate(value, paste)
    assert parsed["handoff_present"] is False
    assert parsed["decisions"][0]["note"] == "first note\n" + m.HANDOFF_DELIM


def test_decisions_block_still_rejects_trailing_content_before_the_handoff():
    value = report()
    try:
        m.validate(value, with_handoff(export(value) + "TRAILING"))
        assert False
    except ValueError as exc:
        assert "TRAILING" in str(exc)


def test_page_export_label_matches_the_validator_for_each_forge():
    # the page's export JS builds its header from data-export-label, so the two must agree
    import re
    from pathlib import Path
    template = (Path(render_report.__file__).resolve().parents[1] / "assets" / "report.html").read_text(encoding="utf-8")
    for forge_name, label in (("gitlab", "MR !42"), ("github", "PR #42")):
        value = report()
        value["meta"]["forge"] = forge_name
        prepared, _ = render_report._prepare_report(value)
        html = render_report.render_html(value, template)
        rendered = re.search(r'data-export-label="([^"]+)"', html).group(1)
        assert rendered == m.export_label(prepared["meta"]) == label
        assert m.export_header(prepared["meta"]).startswith("# %s — triage decisions" % label)
        paste = export(value)
        assert m.validate(value, paste)["target"] == label
