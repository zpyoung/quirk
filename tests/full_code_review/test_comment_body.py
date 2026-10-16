import json
import os
import subprocess
import sys

import pytest

import comment_body as cb

FP = "ab" * 32
FP2 = "cd" * 32
FP3 = "ef" * 32
HEAD = "a" * 40
SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", "skills", "full-code-review", "scripts", "comment_body.py")

HOSTILE = [
    "a --> b", "-->", "line1\nline2", "# comment", "key: value", 'say "hi"', "</details>",
    " leading", "trailing ", "123", "-5", "true", "false", "null", "", "<script>x</script>",
    "back\\slash", "unicode é ☃", "a, b", "[x]", "a\r\nb", " sep", "--", "- dash",
    "<!-- quirk-review:v1", "tab\tchar",
]


def make_finding(**over):
    finding = {
        "id": "F1", "severity": "Must fix", "dimensions": ["correctness", "db"],
        "file": "app/refunds.py", "line": "88", "title": "By-type values drift",
        "impact": "Totals drift by a cent or more.",
        "fix_md": "Sum at full precision, round once.",
        "body_md": "Each part is rounded before summing.\n\nSecond paragraph.",
        "aside_md": "Holds only at 4 dp.", "recommendation_md": "Do the thing. Then more.",
        "evidence": "mutation probe", "verified": True,
        "assumptions": ["rates are stored at 4 dp"],
        "memory": {"fingerprint": FP, "state": "new", "suppress_post": False,
                   "thread": None, "human_context": []},
    }
    finding.update(over)
    return finding


def split_body(body):
    block = cb.parse_block(body)
    rest = body[body.index("\n-->") + 5:]
    return block, rest


@pytest.mark.parametrize("value", HOSTILE)
def test_block_round_trips_hostile_string(value):
    meta = {"kind": "finding", "evil": value, "other": [value, "ok"]}
    text = cb.render_block(meta) + "\nrest of the comment\n-->\n"
    assert cb.parse_block(text) == meta


def test_block_round_trips_types_and_drops_none():
    meta = {"kind": "finding", "n": 88, "neg": -3, "yes": True, "no": False, "gone": None,
            "tags": ["a b", "c"], "empty_list": [], "numstr": "88", "boolstr": "true"}
    parsed = cb.parse_block(cb.render_block(meta) + "\nrest")
    assert parsed == {k: v for k, v in meta.items() if v is not None}
    assert parsed["n"] == 88 and isinstance(parsed["n"], int)
    assert parsed["yes"] is True
    assert parsed["numstr"] == "88" and parsed["boolstr"] == "true"


def test_block_layout_and_escaping():
    block = cb.render_block({"kind": "finding", "file": "app/a.py", "t": "x --> </details> y"})
    lines = block.split("\n")
    assert lines[0] == "<!-- quirk-review:v1"
    assert lines[-1] == "-->"
    assert lines[1] == "kind: finding"
    assert lines[2] == "file: app/a.py"
    assert block.count("-->") == 1
    assert "<" not in "\n".join(lines[1:-1]) and ">" not in "\n".join(lines[1:-1])
    assert "\\u003c" in block and "\\u003e" in block


def test_block_preserves_insertion_order():
    parsed = cb.parse_block(cb.render_block({"z": "1x", "a": "2x", "m": "3x"}) + "\n")
    assert list(parsed) == ["z", "a", "m"]


@pytest.mark.parametrize("key", ["Bad", "has-dash", "", "a b", "1k"])
def test_render_block_rejects_bad_keys(key):
    with pytest.raises(ValueError):
        cb.render_block({key: "x"})


def test_render_block_rejects_unsupported_value():
    with pytest.raises(ValueError):
        cb.render_block({"k": {"a": 1}})


def test_parse_block_ignores_non_leading_block():
    block = cb.render_block({"kind": "finding"})
    assert cb.parse_block("some text\n" + block) is None
    assert cb.parse_block("  \n\n" + block + "\nrest") == {"kind": "finding"}
    assert cb.parse_block("") is None
    assert cb.parse_block(None) is None


def test_parse_block_unterminated_or_malformed_is_none():
    assert cb.parse_block("<!-- quirk-review:v1\nkind: finding\nno close") is None
    assert cb.parse_block("<!-- quirk-review:v1\nnot a pair\n-->") is None


def test_parse_block_stops_at_first_closing_line():
    text = cb.render_block({"kind": "x1"}) + "\nbody\n-->\nmore"
    assert cb.parse_block(text) == {"kind": "x1"}


def test_first_sentence_cases():
    assert cb.first_sentence(None) is None
    assert cb.first_sentence("") is None
    assert cb.first_sentence("   \n ") is None
    assert cb.first_sentence("```py\ncode\n```") is None
    assert cb.first_sentence("  ```\ncode") is None
    assert cb.first_sentence("One thing.  Then another.") == "One thing."
    assert cb.first_sentence("Really?  Yes.") == "Really?"
    assert cb.first_sentence("Stop! Now.") == "Stop!"
    assert cb.first_sentence("First line no stop\nSecond. Third") == "First line no stop Second."
    assert cb.first_sentence("v1.5 is  bad. ok") == "v1.5 is bad."
    assert cb.first_sentence("ends at eof.") == "ends at eof."
    assert cb.first_sentence("no punctuation   here") == "no punctuation here"


def test_first_sentence_spans_hard_wrapped_lines_but_not_paragraphs():
    assert cb.first_sentence("Totals drift when the\nrounding happens early. Next.") == (
        "Totals drift when the rounding happens early.")
    assert cb.first_sentence("No stop in this paragraph\n\nSecond paragraph. Done.") == (
        "No stop in this paragraph")
    assert cb.first_sentence("Lead in\n```py\ncode. more\n```") == "Lead in"


def test_finding_body_order_reviewer_blocking():
    body, warnings = cb.finding_body(make_finding(), seat="reviewer", lead="Blocking",
                                     note="we hit this before", head_sha=HEAD)
    assert warnings == []
    block, rest = split_body(body)
    assert block == {
        "kind": "finding", "fp": FP, "seat": "reviewer", "severity": "Must fix",
        "disposition": "Blocking", "dimensions": ["correctness", "db"],
        "file": "app/refunds.py", "line": 88, "head_sha": HEAD, "verified": True,
    }
    assert list(block) == ["kind", "fp", "seat", "severity", "disposition", "dimensions",
                           "file", "line", "head_sha", "verified"]
    lead_i = rest.index("**Blocking** · By-type values drift")
    note_i = rest.index("> **Reviewer note:** we hit this before")
    why_i = rest.index("Totals drift by a cent or more.")
    fix_i = rest.index("**Fix:** Sum at full precision, round once.")
    det_i = rest.index("<details><summary>Details</summary>")
    assert 0 <= lead_i < note_i < why_i < fix_i < det_i
    assert rest.lstrip("\n").startswith("**Blocking**")
    assert "\n\nTotals drift" in rest and "\n\n**Fix:**" in rest and "\n\n<details>" in rest
    assert body.endswith("</details>\n")


def test_finding_body_author_seat_has_no_disposition_and_no_fp_when_missing():
    finding = make_finding(memory={"fingerprint": "short", "state": "new"})
    body, _ = cb.finding_body(finding, seat="author", lead="Must fix")
    block = cb.parse_block(body)
    assert block["seat"] == "author"
    assert "disposition" not in block and "fp" not in block and "head_sha" not in block
    assert "**Must fix** · By-type values drift" in body
    uppercase = make_finding(memory={"fingerprint": FP.upper()})
    assert "fp" not in cb.parse_block(cb.finding_body(uppercase, seat="author", lead="Nit")[0])


@pytest.mark.parametrize("line", ["\u00b2", "\u0663\u0664", "1\u00b2"])
def test_finding_body_non_ascii_digit_line_stays_text(line):
    body, _ = cb.finding_body(make_finding(line=line), seat="author", lead="Nit")
    assert cb.parse_block(body)["line"] == line


def test_finding_body_non_numeric_line_stays_text():
    body, _ = cb.finding_body(make_finding(line="2-4"), seat="author", lead="Nit")
    assert cb.parse_block(body)["line"] == "2-4"


def test_finding_body_fixed_sentences():
    nb, _ = cb.finding_body(make_finding(), seat="reviewer", lead="Non-blocking")
    q, _ = cb.finding_body(make_finding(), seat="reviewer", lead="Question")
    b, _ = cb.finding_body(make_finding(), seat="reviewer", lead="Blocking")
    assert "*Optional feedback — this does not block the merge.*" in nb
    assert nb.index("*Optional feedback") < nb.index("Totals drift")
    assert "Could you clarify how this behavior is intended to work?" in q
    assert "Optional feedback" not in b and "Could you clarify" not in b
    assert "Optional feedback" not in cb.finding_body(make_finding(), seat="author",
                                                      lead="Nit")[0]


def test_finding_body_multiline_note_is_quoted_line_by_line():
    body, _ = cb.finding_body(make_finding(), seat="reviewer", lead="Blocking",
                              note="first line\n\nthird line")
    assert "> **Reviewer note:** first line\n>\n> third line\n" in body
    blank, _ = cb.finding_body(make_finding(), seat="reviewer", lead="Blocking", note="  \n ")
    assert "Reviewer note" not in blank


def test_why_falls_back_to_first_body_sentence_with_warning():
    finding = make_finding(impact=None)
    del finding["impact"]
    body, warnings = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "Each part is rounded before summing." in body.split("<details>")[0]
    assert warnings == ["F1: impact missing; used first sentence of body"]


def test_fix_falls_back_to_recommendation_with_warning():
    finding = make_finding()
    del finding["fix_md"]
    body, warnings = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "**Fix:** Do the thing." in body
    assert len(warnings) == 1 and warnings[0].startswith("F1: ") and "fix" in warnings[0]


def test_fix_omitted_for_fenced_recommendation_with_warning():
    finding = make_finding(recommendation_md="```py\nfix()\n```")
    del finding["fix_md"]
    body, warnings = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "**Fix:**" not in body
    assert len(warnings) == 1 and "fix" in warnings[0]


def test_fix_omitted_when_nothing_available():
    finding = make_finding()
    del finding["fix_md"]
    del finding["recommendation_md"]
    body, warnings = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "**Fix:**" not in body
    assert len(warnings) == 1


def test_warning_without_id_still_names_something():
    finding = make_finding()
    del finding["id"]
    del finding["impact"]
    _, warnings = cb.finding_body(finding, seat="author", lead="Nit")
    assert warnings and "impact missing" in warnings[0]


def test_details_contents_and_order():
    body, _ = cb.finding_body(make_finding(), seat="author", lead="Must fix")
    details = body[body.index("<details>"):]
    assert details.startswith("<details><summary>Details</summary>\n\n")
    assert details.endswith("\n\n</details>\n")
    assert (details.index("Each part is rounded") < details.index("Holds only at 4 dp.")
            < details.index("**Evidence:** mutation probe · verified")
            < details.index("**Assumptions:** rates are stored at 4 dp"))
    assert "Second paragraph." in details


def test_details_unverified_and_no_evidence():
    finding = make_finding(verified=False, evidence=None, assumptions=[])
    body, _ = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "**Evidence:** none · unverified" in body
    assert "Assumptions" not in body


def test_details_omitted_for_thin_finding():
    finding = make_finding(body_md="Totals drift by a cent or more.", aside_md=None,
                           evidence=None, assumptions=[], verified=False)
    body, _ = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "<details" not in body and "</details" not in body
    empty = make_finding(body_md="", aside_md="", evidence="", assumptions=[])
    assert "<details" not in cb.finding_body(empty, seat="author", lead="Must fix")[0]


def test_details_kept_when_body_equals_why_but_aside_present():
    finding = make_finding(body_md="Totals drift by a cent or more.", evidence=None,
                           assumptions=[])
    body, _ = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "<details><summary>Details</summary>" in body
    assert "Holds only at 4 dp." in body
    assert body.count("Totals drift by a cent or more.") == 1


def test_details_closer_escaped_everywhere_including_fences():
    hostile = ("before </details> and <details open> text\n\n"
               "```html\n</details>\n<details>\n```\n\nafter </DETAILS>")
    finding = make_finding(body_md=hostile, aside_md="aside </details> too")
    body, _ = cb.finding_body(finding, seat="author", lead="Must fix")
    real_closers = [line for line in body.split("\n") if line == "</details>"]
    assert len(real_closers) == 1
    assert "before &lt;/details> and &lt;details open> text" in body
    assert "after &lt;/details>" in body
    assert "aside &lt;/details> too" in body
    assert "```html\n&lt;/details>\n&lt;details>\n```" in body


def test_details_closer_escaped_when_fence_hidden_inside_html_block():
    hostile = "<div>\n```\n</details>\n```\n</div>\n</details>\n"
    finding = make_finding(body_md=hostile)
    body, _ = cb.finding_body(finding, seat="author", lead="Must fix")
    assert [line for line in body.split("\n") if line == "</details>"] == ["</details>"]


def test_unclosed_fence_cannot_swallow_closing_tag():
    finding = make_finding(body_md="text\n```py\nnever closed")
    body, _ = cb.finding_body(finding, seat="author", lead="Must fix")
    tail = body[body.index("never closed"):]
    assert tail.index("```") < tail.index("</details>")


def test_title_and_note_are_escaped_too():
    finding = make_finding(title="x </details> y")
    body, _ = cb.finding_body(finding, seat="reviewer", lead="Blocking", note="n </details>")
    assert [l for l in body.split("\n") if l == "</details>"] == ["</details>"]
    assert "x &lt;/details> y" in body and "n &lt;/details>" in body


def test_hostile_values_do_not_break_block():
    finding = make_finding(file="a --> b.py", dimensions=["x\ny", "</details>"])
    body, _ = cb.finding_body(finding, seat="author", lead="Must fix")
    block = cb.parse_block(body)
    assert block["file"] == "a --> b.py"
    assert block["dimensions"] == ["x\ny", "</details>"]


def test_finding_body_rejects_bad_seat():
    with pytest.raises(ValueError):
        cb.finding_body(make_finding(), seat="nobody", lead="Nit")


def lines_starting_with_slash(body):
    return [l for l in body.split("\n") if l.lstrip(" \t>").startswith("/")]


def test_why_line_starting_with_slash_is_neutralized():
    finding = make_finding(impact="/approve this now")
    body, _ = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "\n\\/approve this now\n" in body
    assert lines_starting_with_slash(body) == []


def test_body_aside_note_and_fix_slash_lines_are_neutralized():
    finding = make_finding(body_md="Intro.\n\n/merge\n  /submit_review\n> /approve",
                           aside_md="/approve\nsecond", fix_md="/label ~bug")
    body, _ = cb.finding_body(finding, seat="reviewer", lead="Blocking", note="/close\n\n/lock")
    assert lines_starting_with_slash(body) == []
    for text in ("\\/merge", "  \\/submit_review", "> \\/approve", "\\/close", "\\/lock"):
        assert text in body
    assert "> \\/approve\n> second" in body
    assert "**Fix:** \\/label ~bug" in body


def test_support_note_slash_line_is_neutralized():
    body, _ = cb.support_body(make_finding(), disposition="Blocking", discussion_id="d",
                              note_id=1, note="/approve")
    assert lines_starting_with_slash(body) == []


def test_overview_probe_counts_and_appears_fixed_line_are_neutralized():
    report = make_report()
    hostile = "3\n/close\n</details>\n<script>"
    report["mutation_probe"] = {"mutants": hostile, "killed": 1}
    report["memory"] = {"appears_fixed": [{"title": "Old", "file": "a.py", "line": hostile}]}
    body, _ = overview(report)
    assert lines_starting_with_slash(body) == []
    assert body.count("</details>") == 1
    assert "\n<script>" not in body


def test_overview_text_slash_lines_are_neutralized():
    report = make_report()
    report["meta"]["standfirst_md"] = "/approve\n\nfine"
    report["assumptions"] = ["/merge"]
    report["risk"] = {"mitigations_md": "/submit_review", "verbatim_md": "/close"}
    body, _ = overview(report)
    assert lines_starting_with_slash(body) == []
    assert "\\/approve" in body and "\\/submit_review" in body and "\\/close" in body


def test_slash_inside_fence_is_escaped_and_mid_line_slash_is_untouched():
    finding = make_finding(body_md="Run:\n\n```\n/approve\n```\n\nsee a/b and x /merge "
                                   "and https://x.test/y\n\n~~~\n/merge\n~~~")
    body, _ = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "```\n\\/approve\n```" in body and "~~~\n\\/merge\n~~~" in body
    assert "see a/b and x /merge and https://x.test/y" in body
    assert lines_starting_with_slash(body) == []


def test_unclosed_fence_escapes_slash_inside_and_is_closed():
    out = cb._neutralize("```\n/approve")
    assert out == "```\n\\/approve\n```"


def test_support_body_lead_block_and_no_visible_note():
    body, warnings = cb.support_body(make_finding(), disposition="Blocking",
                                     discussion_id="9f2c", note_id=481223, head_sha=HEAD)
    assert warnings == []
    block = cb.parse_block(body)
    assert block["kind"] == "support"
    assert block["fp"] == FP
    assert block["supports_discussion"] == "9f2c"
    assert block["supports_note"] == 481223
    assert block["disposition"] == "Blocking" and block["seat"] == "reviewer"
    assert block["head_sha"] == HEAD
    visible = body[body.index("\n-->") + 4:].split("<details>")[0]
    assert "**Agree · Blocking** · quirk full-code-review found this independently" in visible
    assert "Reviewer note" not in visible and "> " not in visible
    assert "Totals drift by a cent or more." in visible and "**Fix:**" in visible


def test_support_body_note_goes_inside_details():
    body, _ = cb.support_body(make_finding(), disposition="Question", discussion_id="d",
                              note_id=5, note="seen before\nsecond line")
    visible, details = body.split("<details>", 1)
    assert "Reviewer note" not in visible
    assert "**Reviewer note:**" in details and "seen before\nsecond line" in details
    assert details.index("Reviewer note") < details.index("**Evidence:**")


def test_support_body_details_present_when_note_even_if_thin():
    finding = make_finding(body_md="Totals drift by a cent or more.", aside_md=None,
                           evidence=None, assumptions=[])
    plain, _ = cb.support_body(finding, disposition="Blocking", discussion_id="d", note_id=1)
    assert "<details" not in plain
    noted, _ = cb.support_body(finding, disposition="Blocking", discussion_id="d", note_id=1,
                               note="hi")
    assert "<details><summary>Details</summary>" in noted and "hi" in noted


def make_report(**over):
    report = {
        "meta": {"target": "change", "forge": "gitlab", "number": 7, "project": "g/p", "head_sha": HEAD,
                 "title": "T", "standfirst_md": "The summary.", "verdict": "Request changes",
                 "seat": "reviewer"},
        "run": {"source_access": "borrowed-worktree"},
        "risk": {}, "assumptions": [],
        "findings": [
            make_finding(id="F1", title="Blocker one", severity="Must fix",
                         memory={"fingerprint": FP}),
            make_finding(id="F2", title="Blocker two", severity="Must fix",
                         memory={"fingerprint": FP2}),
            make_finding(id="F3", title="Should one", severity="Should fix",
                         memory={"fingerprint": FP3}),
            make_finding(id="F4", title="Old open", severity="Should fix",
                         memory={"fingerprint": "11" * 32}),
            make_finding(id="F5", title="Back again", severity="Nit",
                         memory={"fingerprint": "22" * 32}),
        ],
    }
    report.update(over)
    return report


def make_posted():
    return [
        {"kind": "inline", "finding_id": "F1", "disposition": "Blocking", "fingerprint": FP,
         "title": "Blocker one"},
        {"kind": "inline", "finding_id": "F2", "disposition": "Blocking", "fingerprint": FP2},
        {"kind": "reply", "finding_id": "F3", "disposition": "Non-blocking",
         "fingerprint": FP3},
    ]


def make_omitted():
    return [
        {"id": "F4", "reason": "already posted (carried)", "memory_state": "carried",
         "thread_url": "https://gl/x/1"},
        {"id": "F5", "reason": "already posted", "memory_state": "re-found-after-resolution",
         "thread_url": "https://gl/x/2", "fingerprint": "22" * 32},
    ]


def overview(report=None, posted=None, omitted=None, **kw):
    return cb.overview_body(report or make_report(), seat="reviewer",
                            posted=make_posted() if posted is None else posted,
                            omitted=make_omitted() if omitted is None else omitted,
                            report_sha256="9e" * 32, **kw)


def test_overview_block_lists():
    body, warnings = overview()
    block = cb.parse_block(body)
    assert block == {
        "kind": "overview", "seat": "reviewer", "head_sha": HEAD, "report_sha256": "9e" * 32,
        "posted": [FP, FP2, FP3], "still_open": ["11" * 32],
        "previously_resolved": ["22" * 32], "supported": [FP3],
    }
    assert warnings == []


def test_overview_block_omits_empty_lists_and_missing_head():
    report = make_report()
    del report["meta"]["head_sha"]
    body, _ = overview(report, posted=[], omitted=[])
    assert cb.parse_block(body) == {"kind": "overview", "seat": "reviewer",
                                    "report_sha256": "9e" * 32}


def test_overview_omitted_fingerprint_looked_up_by_id():
    omitted = [{"id": "F4", "memory_state": "answered", "reason": "x"}]
    body, _ = overview(omitted=omitted)
    assert cb.parse_block(body)["still_open"] == ["11" * 32]


def test_overview_visible_section():
    body, _ = overview()
    visible = body[body.index("\n-->") + 4:].split("<details>")[0]
    lines = [l for l in visible.split("\n") if l.strip()]
    assert lines[0] == "**Request changes** · 2 Must fix · 2 Should fix · 1 Nit"
    assert "- **Blocking:** Blocker one" in visible
    assert "- **Blocking:** Blocker two" in visible
    assert "Should one" not in visible
    assert lines[-1] == "1 earlier finding still open · 1 previously resolved, still present"
    assert "Diff-only" not in visible and "Head moved" not in visible


def test_overview_blocker_bullets_capped_at_three_and_title_lookup():
    posted = [{"kind": "inline", "finding_id": "F%d" % i, "disposition": "Blocking",
               "fingerprint": None} for i in (1, 2, 3, 4)]
    body, _ = overview(posted=posted)
    visible = body.split("<details>")[0]
    assert visible.count("- **Blocking:**") == 3
    assert "Blocker one" in visible and "Blocker two" in visible


def test_overview_lists_unplaced_findings_visibly():
    omitted = [{"id": "F3", "reason": "line is outside the diff", "disposition": "Blocking",
                "fingerprint": FP3, "unplaced": True},
               {"id": "F4", "reason": "Ignore", "disposition": "Ignore"}]
    body, _ = overview(omitted=omitted)
    visible = body.split("<details>")[0]
    assert "**Not anchored inline**" in visible
    assert "- **Blocking:** Should one (`app/refunds.py:88`) — Totals drift by a cent or more." in visible
    assert "Old open" not in visible


def test_overview_has_no_unplaced_section_when_everything_anchored():
    body, _ = overview(omitted=make_omitted())
    assert "Not anchored inline" not in body


def test_overview_count_line_plural_and_halves():
    omitted = [{"id": "F4", "memory_state": "carried"}, {"id": "F5", "memory_state": "answered"}]
    body, _ = overview(omitted=omitted)
    visible = body.split("<details>")[0]
    assert "2 earlier findings still open" in visible
    assert "previously resolved" not in visible
    only_resolved = [{"id": "F5", "memory_state": "re-found-after-resolution"}]
    body, _ = overview(omitted=only_resolved)
    assert body.split("<details>")[0].rstrip().endswith("1 previously resolved, still present")
    assert "earlier finding" not in body.split("<details>")[0]
    body, _ = overview(omitted=[])
    assert "earlier finding" not in body.split("<details>")[0]
    assert "previously resolved" not in body.split("<details>")[0].split("-->")[1]


def test_overview_diff_only_and_head_moved_lines():
    report = make_report()
    report["run"] = {"source_access": "diff-only", "source_access_reason": "no clone"}
    body, _ = overview(report, head_note="2 new commits")
    visible = body.split("<details>")[0]
    assert "> Diff-only review: every finding is unverified." in visible
    assert "> Head moved: 2 new commits" in visible
    assert visible.index("Diff-only") < visible.index("Head moved") < visible.index("- **Blocking:**")


def test_overview_details_sections_in_order_and_content():
    report = make_report()
    report["run"] = {
        "source_access": "diff-only", "source_access_reason": "no clone available",
        "dimensions_skipped": [{"name": "perf", "why": "no source"}, "x-repo"],
        "clean_notes": [{"dimension": "security", "note_md": "Nothing found."}],
    }
    report["risk"] = {
        "level": "Medium", "verbatim_md": "Verbatim risk text.",
        "metrics": {"likelihood": {"level": "possible"}, "rollback": {"level": "hard",
                                                                       "note_md": "no flag"}},
        "mitigations_md": "Add a flag.", "caveats": [{"title": "Cav", "body_md": "caveat body"}],
    }
    report["assumptions"] = ["Rates are 4 dp"]
    report["mutation_probe"] = {"mutants": 5, "killed": 4, "survived": 1,
                                "narrative_md": "One mutant survived."}
    report["memory"] = {"appears_fixed": [
        {"title": "Fixed thing", "file": "a.py", "line": "3",
         "thread": {"url": "https://gl/fixed"}}]}
    body, _ = overview(report, head_note="moved")
    details = body[body.index("<details><summary>Details</summary>"):]
    order = ["The summary.", "**Risk**", "**Assumptions**", "**Clean dimensions**",
             "**Mutation probe**", "**Still open from earlier reviews**",
             "**Previously resolved, still present**", "**Appears fixed**", "**Run limits**"]
    positions = [details.index(token) for token in order]
    assert positions == sorted(positions)
    assert "Level:** Medium" in details and "Likelihood" in details and "possible" in details
    assert "Add a flag." in details and "Verbatim risk text." in details and "caveat body" in details
    assert "- Rates are 4 dp" in details
    assert "Nothing found." in details and "security" in details
    assert "Killed: 4" in details and "Survived: 1" in details and "One mutant survived." in details
    assert "Old open" in details and "https://gl/x/1" in details
    assert "Back again" in details and "https://gl/x/2" in details
    assert "Fixed thing" in details and "https://gl/fixed" in details
    assert "no clone available" in details and "perf" in details and "x-repo" in details
    assert "moved" in details.split("**Run limits**")[1]
    assert "Posted: 3 · Not posted: 2" in details
    assert details.endswith("\n\n</details>\n")


def test_overview_omits_empty_sections():
    body, _ = overview(omitted=[])
    details = body[body.index("<details>"):]
    for heading in ("**Risk**", "**Assumptions**", "**Clean dimensions**", "**Mutation probe**",
                    "**Still open", "**Previously resolved", "**Appears fixed**"):
        assert heading not in details
    assert "**Run limits**" in details and "Posted: 3 · Not posted: 0" in details


def test_overview_escapes_details_closer_in_user_text():
    report = make_report()
    report["meta"]["standfirst_md"] = "x </details> y\n\n```\n</details>\n```"
    body, _ = overview(report)
    assert [l for l in body.split("\n") if l == "</details>"] == ["</details>"]
    assert "x &lt;/details> y" in body


def test_overview_rejects_bad_seat():
    with pytest.raises(ValueError):
        cb.overview_body(make_report(), seat="x", posted=[], omitted=[], report_sha256="a1")


def raw_report():
    return {
        "meta": {"target": "change", "forge": "gitlab", "number": 7, "project": "g/p", "head_sha": HEAD, "title": "T",
                 "standfirst_md": "Summary.", "verdict": "Fix first"},
        # these tests cover Nit body mechanics; the default floor is tested in test_render_contract
        "run": {"severity_floor": "Nit"},
        "findings": [
            {"severity": "Must fix", "dimension": "correctness", "file": "a.py", "line": "2",
             "title": "Bug", "impact": "It breaks.", "fix_md": "Fix it.",
             "body_md": "Longer explanation here.\n\nMore.", "verified": True},
            {"severity": "Nit", "dimension": "comments", "file": "b.py", "line": "9",
             "title": "Tiny", "body_md": "Small thing. Really.",
             "recommendation_md": "Tidy up."},
        ],
        "assumptions": ["An assumption"],
    }


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return str(path)


def test_cli_output_shape(tmp_path, capsys):
    report = write_json(tmp_path / "r.json", raw_report())
    out = tmp_path / "out" / "bodies.json"
    code = cb.main(["author", "--report", report, "--out", str(out)])
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data) == {"findings", "overview", "overview_plan", "warnings", "report_sha256"}
    assert data["report_sha256"] == cb._report_digest(raw_report())
    assert set(data["findings"]) == {"F1", "F2"}
    first = data["findings"]["F1"]
    assert first["fingerprint"] is None
    block = cb.parse_block(first["body"])
    assert block["seat"] == "author" and block["severity"] == "Must fix"
    assert block["head_sha"] == HEAD and "disposition" not in block
    assert "**Must fix** · Bug" in first["body"]
    assert "**Nit** · Tiny" in data["findings"]["F2"]["body"]
    assert any("F2" in w for w in data["warnings"])
    over = cb.parse_block(data["overview"])
    assert over["kind"] == "overview" and over["head_sha"] == HEAD
    import hashlib
    digest = hashlib.sha256(json.dumps(raw_report(), sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=False).encode("utf-8")).hexdigest()
    assert over["report_sha256"] == digest
    assert "**Fix first** · 1 Must fix · 0 Should fix · 1 Nit" in data["overview"]
    printed = json.loads(capsys.readouterr().out)
    assert printed["findings"] == 2 and printed["warnings"] == data["warnings"]


def decisions_doc(raw, rows, **over):
    doc = {"schema": 1, "seat": "author", "decisions": rows,
           "report_sha256": cb._report_digest(raw)}
    doc.update(over)
    return doc


def test_cli_decisions_contribute_notes(tmp_path):
    raw = raw_report()
    report = write_json(tmp_path / "r.json", raw)
    decisions = write_json(tmp_path / "d.json", decisions_doc(raw, [
        {"id": "F1", "slot": "fix", "disposition": "Will fix", "note": "Human note"},
        {"id": "F2", "slot": "ignore", "disposition": "Ignore", "note": ""}]))
    out = tmp_path / "b.json"
    assert cb.main(["author", "--report", report, "--decisions", decisions,
                    "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "> **Reviewer note:** Human note" in data["findings"]["F1"]["body"]
    assert "Reviewer note" not in data["findings"]["F2"]["body"]


ROWS = [{"id": "F1", "slot": "fix", "disposition": "Will fix", "note": "Human note"}]


@pytest.mark.parametrize("make_doc", [
    lambda raw: decisions_doc(raw, ROWS, report_sha256="0" * 64),
    lambda raw: decisions_doc(raw, ROWS, seat="reviewer"),
    lambda raw: ROWS,
    lambda raw: {"schema": 1, "seat": "author", "decisions": ROWS},
], ids=["digest-mismatch", "reviewer-seat", "bare-list", "missing-digest"])
def test_cli_rejects_unbound_decisions(tmp_path, capsys, make_doc):
    raw = raw_report()
    report = write_json(tmp_path / "r.json", raw)
    decisions = write_json(tmp_path / "d.json", make_doc(raw))
    out = tmp_path / "b.json"
    assert cb.main(["author", "--report", report, "--decisions", decisions,
                    "--out", str(out)]) == 2
    assert "error" in json.loads(capsys.readouterr().out)
    assert not out.exists()


def three_finding_report():
    raw = raw_report()
    raw["findings"].append({"severity": "Should fix", "dimension": "correctness",
                            "file": "c.py", "line": "4", "title": "Third",
                            "impact": "Drifts.", "fix_md": "Fix.", "body_md": "Third body."})
    return raw


def overview_of(tmp_path, raw, rows):
    args = ["author", "--report", write_json(tmp_path / "r.json", raw),
            "--out", str(tmp_path / "b.json")]
    if rows is not None:
        args += ["--decisions", write_json(tmp_path / "d.json", decisions_doc(raw, rows))]
    assert cb.main(args) == 0
    return json.loads((tmp_path / "b.json").read_text(encoding="utf-8"))


def test_cli_overview_counts_only_posted_slots(tmp_path):
    raw = three_finding_report()
    rows = [{"id": "F1", "slot": "fix", "disposition": "Will fix", "note": ""},
            {"id": "F2", "slot": "ignore", "disposition": "Ignore", "note": ""},
            {"id": "F3", "slot": "none", "disposition": "No decision", "note": ""}]
    data = overview_of(tmp_path, raw, rows)
    assert "Posted: 1 · Not posted: 2" in data["overview"]
    assert set(data["findings"]) == {"F1", "F2", "F3"}


def test_cli_marks_post_eligibility_and_warns_only_for_posted_findings(tmp_path):
    rows = [{"id": "F1", "slot": "fix", "disposition": "Will fix", "note": ""},
            {"id": "F2", "slot": "ignore", "disposition": "Ignore", "note": ""}]
    data = overview_of(tmp_path, raw_report(), rows)
    assert {fid: entry["post"] for fid, entry in data["findings"].items()} == {"F1": True, "F2": False}
    assert not any("F2" in warning for warning in data["warnings"])


def test_cli_memory_suppressed_finding_is_not_eligible_to_post(tmp_path):
    raw = with_memory(raw_report(), first={"state": "carried", "suppress_post": True,
                                           "thread": {"url": "https://gl/t"}})
    data = overview_of(tmp_path, raw, None)
    assert data["findings"]["F1"]["post"] is False and data["findings"]["F2"]["post"] is True
    assert "Posted: 1 · Not posted: 1" in data["overview"]


def test_cli_decision_dropped_findings_stay_out_of_memory_lists(tmp_path):
    raw = three_finding_report()
    rows = [{"id": "F1", "slot": "fix", "disposition": "Will fix", "note": ""},
            {"id": "F2", "slot": "ignore", "disposition": "Ignore", "note": ""}]
    overview = overview_of(tmp_path, raw, rows)["overview"]
    assert "Posted: 1 · Not posted: 2" in overview
    assert "Still open from earlier reviews" not in overview
    assert "Previously resolved, still present" not in overview
    assert "still open" not in overview and "previously resolved" not in overview
    assert "Tiny" not in overview and "Third" not in overview


def test_author_bodies_label_decision_dropped_findings(monkeypatch):
    raw = three_finding_report()
    rows = {"F2": {"id": "F2", "slot": "ignore", "disposition": "Ignore"},
            "F3": {"id": "F3", "slot": "none", "disposition": ""}}
    captured = []
    original = cb.overview_body

    def capture(report, **kwargs):
        captured.extend(kwargs["omitted"])
        return original(report, **kwargs)

    monkeypatch.setattr(cb, "overview_body", capture)
    cb._author_bodies(raw, rows)
    assert [(item["id"], item["reason"], item["disposition"]) for item in captured] == [
        ("F1", "Undecided", "Undecided"), ("F2", "Ignore", "Ignore"),
        ("F3", "Undecided", "Undecided")]


@pytest.mark.parametrize("slot", ["fix", "later", "detail"])
def test_cli_overview_counts_each_posted_slot(tmp_path, slot):
    raw = three_finding_report()
    rows = [{"id": "F1", "slot": slot, "disposition": "x", "note": ""}]
    assert "Posted: 1 · " in overview_of(tmp_path, raw, rows)["overview"]


def test_cli_overview_counts_every_finding_without_decisions(tmp_path):
    data = overview_of(tmp_path, three_finding_report(), None)
    assert "Posted: 3 · Not posted: 0" in data["overview"]


def with_memory(raw, first=None, second=None):
    """Attach a reconciled memory snapshot to `raw`; `first`/`second` override each finding's entry."""
    memory_entry = {"fingerprint": FP, "dimension": "correctness", "anchor_hash": None,
                    "state": "new", "match": None, "disposition": "none", "note": "",
                    "suppress_post": False, "thread": None, "candidates": [],
                    "human_context": []}
    raw["memory"] = {"appears_fixed": [], "warnings": [], "snapshot": {
        "schemaVersion": 1, "target_key": "k", "identity": {}, "seat": "author",
        "base_sha": None, "head_sha": None, "guidance_hash": None, "invalidation_reason": None,
        "started_at": 0, "dimensions": [], "findings": [], "discussions": [],
        "discussions_available": True, "warnings": [], "file_hashes": {},
        "unchanged_files": []}}
    raw["findings"][0]["memory"] = dict(memory_entry, **(first or {}))
    raw["findings"][1]["memory"] = dict(memory_entry, **(second or {"fingerprint": None}))
    return raw


def test_cli_fingerprint_from_memory(tmp_path):
    raw = with_memory(raw_report())
    report = write_json(tmp_path / "r.json", raw)
    out = tmp_path / "b.json"
    assert cb.main(["author", "--report", report, "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["findings"]["F1"]["fingerprint"] == FP
    assert cb.parse_block(data["findings"]["F1"]["body"])["fp"] == FP
    assert data["findings"]["F2"]["fingerprint"] is None


def run_cli(*args):
    return subprocess.run([sys.executable, SCRIPT] + list(args), capture_output=True, text=True)


def test_cli_rejects_reviewer_seat_report(tmp_path, capsys):
    raw = raw_report()
    raw["meta"].update({"seat": "reviewer", "project": "g/p"})
    report = write_json(tmp_path / "r.json", raw)
    out = tmp_path / "o.json"
    assert cb.main(["author", "--report", report, "--out", str(out)]) == 2
    assert "seat" in json.loads(capsys.readouterr().out)["error"]
    assert not out.exists()


def test_cli_overview_uses_author_seat(tmp_path):
    raw = raw_report()
    raw["meta"]["seat"] = "author"
    report = write_json(tmp_path / "r.json", raw)
    out = tmp_path / "o.json"
    assert cb.main(["author", "--report", report, "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert cb.parse_block(data["overview"])["seat"] == "author"


def test_cli_exit_2_on_missing_report(tmp_path, capsys):
    code = cb.main(["author", "--report", str(tmp_path / "nope.json"),
                    "--out", str(tmp_path / "o.json")])
    assert code == 2
    assert "error" in json.loads(capsys.readouterr().out)
    assert not (tmp_path / "o.json").exists()


def test_cli_exit_2_on_invalid_report_and_decisions(tmp_path, capsys):
    bad = write_json(tmp_path / "bad.json", {"meta": "nope", "findings": []})
    assert cb.main(["author", "--report", bad, "--out", str(tmp_path / "o.json")]) == 2
    assert "error" in json.loads(capsys.readouterr().out)
    good = write_json(tmp_path / "g.json", raw_report())
    broken = tmp_path / "d.json"
    broken.write_text("{not json", encoding="utf-8")
    assert cb.main(["author", "--report", good, "--decisions", str(broken),
                    "--out", str(tmp_path / "o.json")]) == 2
    assert "error" in json.loads(capsys.readouterr().out)


def test_cli_as_subprocess(tmp_path):
    report = write_json(tmp_path / "r.json", raw_report())
    out = tmp_path / "b.json"
    done = run_cli("author", "--report", report, "--out", str(out))
    assert done.returncode == 0, done.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["findings"]["F1"]["body"]
    failed = run_cli("author", "--report", str(tmp_path / "missing.json"), "--out", str(out))
    assert failed.returncode == 2
    assert "error" in json.loads(failed.stdout)


@pytest.mark.parametrize("sep", ["\r", "\r\n", "\u2028", "\u2029"])
def test_alternate_line_endings_cannot_hide_quick_action(sep):
    out = cb._neutralize("x%s/close" % sep)
    assert out == "x\n\\/close"
    assert "\r" not in out and "\u2028" not in out and "\u2029" not in out


def test_crlf_input_yields_no_carriage_return_anywhere():
    finding = make_finding(body_md="a\r\n/merge\r\nb", aside_md="c\r/lock", note="x")
    body, _ = cb.finding_body(finding, seat="reviewer", lead="Blocking", note="n\r\n/close")
    assert "\r" not in body
    assert lines_starting_with_slash(body) == []


def test_fence_closed_by_crlf_line_restores_escaping_after_it():
    out = cb._neutralize("```\r\n<!-- inside\r\n```\r\n<!-- after")
    assert out == "```\n<!-- inside\n```\n&lt;!-- after"


def test_quote_and_line_helpers_split_on_normalized_endings():
    assert "\r" not in cb._quote(cb._md("a\r\n/b\u2028/c"))
    assert cb._line("a\u2028/b") == "a /b"


def test_line_leading_html_comment_opener_is_escaped():
    assert cb._neutralize("<!-- hide") == "&lt;!-- hide"
    assert cb._neutralize("> <!-- hide") == "> &lt;!-- hide"
    assert cb._neutralize("  >  <!--") == "  >  &lt;!--"
    assert cb._neutralize("text <!-- mid") == "text <!-- mid"


def test_html_comment_opener_inside_fence_stays_literal():
    assert cb._neutralize("```\n<!-- x\n```") == "```\n<!-- x\n```"


@pytest.mark.parametrize("opener", [
    "<pre>", "<pre class=x>", "<PRE>", "<script>", "<script src=x>", "<style>", "<textarea>",
    "<pre", "<?php", "<!DOCTYPE html>", "<![CDATA[", "<!-- c",
])
def test_line_leading_terminated_html_openers_are_escaped(opener):
    assert cb._neutralize(opener + " rest") == "&lt;" + opener[1:] + " rest"
    assert cb._neutralize("> " + opener) == "> &lt;" + opener[1:]


def test_blockquoted_script_opener_is_escaped():
    assert cb._neutralize("> <script>") == "> &lt;script>"


def test_html_opener_inside_fence_stays_literal():
    assert cb._neutralize("```\n<pre>\n<script>\n```") == "```\n<pre>\n<script>\n```"


@pytest.mark.parametrize("line", ["<br>", "<div>", "<kbd>x</kbd>", "<prefix>", "<scripts>", "</div>"])
def test_any_line_leading_tag_is_escaped_so_no_html_block_can_hide_a_fence(line):
    assert cb._neutralize(line) == "&lt;" + line[1:]


@pytest.mark.parametrize("line", ["<! not letter", "text <pre>", "a < b", "<3"])
def test_non_tag_text_is_unchanged(line):
    assert cb._neutralize(line) == line


def test_html_block_opener_cannot_turn_a_fence_into_literal_text():
    # with <div> escaped the renderer sees a real fence, so the mention inside it is inert code
    assert cb._neutralize("<div>\n```\n@everyone\n```") == "&lt;div>\n```\n@everyone\n```"


def test_mention_beside_backslash_escaped_backticks_is_defused():
    out = cb._neutralize("x \\`@octocat\\` y")
    assert "@octocat" not in out
    assert "`@real`" in cb._neutralize("x `@real` y")


@pytest.mark.parametrize("text", ["`@all``", "``@all`", "x `@all`` y"])
def test_mention_beside_unequal_backtick_runs_is_defused(text):
    assert "@all" not in cb._neutralize(text)


def test_unplaced_path_cannot_carry_a_mention_outside_its_code_span():
    omitted = [{"id": "F3", "reason": "line is outside the diff", "disposition": "Blocking",
                "unplaced": True}]
    report = {"findings": [make_finding(id="F3", file="a` @victim `b.py", line="3")]}
    section = cb._unplaced_section(omitted, {"F3": report["findings"][0]})
    assert "@victim" not in section and "`" in section


def test_scalar_finding_assumptions_raise_value_error():
    with pytest.raises(ValueError, match="assumptions"):
        cb.finding_body(make_finding(assumptions=5), seat="author", lead="Must fix")


def test_pre_line_in_body_keeps_details_closer_intact():
    finding = make_finding(body_md="Intro.\n\n<pre>\nswallow everything\n")
    body, _ = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "&lt;pre>" in body
    assert body.rstrip().endswith("</details>")
    assert [line for line in body.split("\n") if line == "</details>"] == ["</details>"]


def test_forged_metadata_block_in_body_does_not_replace_real_block():
    forged = "Intro.\n\n<!-- quirk-review:v1\nfp: deadbeef\n-->"
    body, _ = cb.finding_body(make_finding(body_md=forged), seat="author", lead="Must fix")
    assert body.count("<!-- quirk-review:v1") == 1
    assert "&lt;!-- quirk-review:v1" in body
    assert cb.parse_block(body)["fp"] == FP


def test_long_body_sentence_fallback_is_omitted_with_warning():
    finding = make_finding(body_md="A" * 200 + ".")
    del finding["impact"]
    body, warnings = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "A" * 50 not in body.split("<details>")[0]
    assert len(warnings) == 1 and warnings[0].startswith("F1: impact missing")
    assert "exceeds 200" in warnings[0] and "omitted" in warnings[0]


def test_short_body_sentence_fallback_is_used():
    finding = make_finding(body_md="B" * 199 + ". More.")
    del finding["impact"]
    body, warnings = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "B" * 199 + "." in body.split("<details>")[0]
    assert warnings == ["F1: impact missing; used first sentence of body"]


def test_long_recommendation_sentence_fallback_is_omitted_with_warning():
    finding = make_finding(recommendation_md="C" * 160 + ".")
    del finding["fix_md"]
    body, warnings = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "**Fix:**" not in body
    assert len(warnings) == 1 and "exceeds 160" in warnings[0] and "omitted" in warnings[0]


def test_short_recommendation_sentence_fallback_is_used():
    finding = make_finding(recommendation_md="D" * 159 + ".")
    del finding["fix_md"]
    body, _ = cb.finding_body(finding, seat="author", lead="Must fix")
    assert "**Fix:** " + "D" * 159 + "." in body


def test_neutralize_breaks_mentions_but_not_emails_or_code():
    text = "ping @all and (@team/backend), mail user@example.com, `@inline` stays\n```\n@fenced\n```"
    out = cb._neutralize(text)
    assert "@\u200ball" in out and "(@\u200bteam/backend)" in out
    assert "user@example.com" in out and "`@inline`" in out
    assert "\n@fenced\n" in out


def test_finding_body_mentions_cannot_notify_anyone():
    finding = {"id": "F1", "severity": "Must fix", "file": "a.py", "line": "2", "title": "Tell @bob",
               "impact": "@all will see this.", "fix_md": "Ask @team.", "body_md": "Details.",
               "dimension": "correctness"}
    body, _ = cb.finding_body(finding, seat="author", lead="Must fix", head_sha="a" * 40)
    visible = body.split("-->\n", 1)[1]
    assert "@bob" not in visible and "@all" not in visible and "@team" not in visible


def test_path_pairs_decodes_git_quoted_rename_paths():
    diff = ('diff --git "a/old name\\303\\251.py" "b/new\\tname.py"\nsimilarity index 80%\n'
            'rename from "old name\\303\\251.py"\nrename to "new\\tname.py"\n'
            '--- "a/old name\\303\\251.py"\n+++ "b/new\\tname.py"\n@@ -1 +1 @@\n-a\n+b\n')
    assert cb.path_pairs(diff) == {"new\tname.py": {"old": "old nameé.py", "new": "new\tname.py"}}


def test_path_pairs_splits_diff_text_on_newlines_only():
    # a form feed or U+2028 inside a hunk line must not start a phantom "rename" line
    diff = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n"
            "-x\n+y\x0crename to evil.py rename to other.py\n"
            "diff --git a/b.py b/b.py\n")
    assert cb.path_pairs(diff) == {"a.py": {"old": "a.py", "new": "a.py"},
                                   "b.py": {"old": "b.py", "new": "b.py"}}


@pytest.mark.parametrize("slot", [None, "fix", "later"])
def test_plausible_author_finding_never_becomes_post_eligible(slot):
    raw = raw_report()
    raw["findings"][0].update(verification_status="plausible",
                              what_would_confirm="Run the input.", verified=True)
    decisions = None if slot is None else {
        "F1": {"id": "F1", "slot": slot, "disposition": "Will fix", "note": ""}}
    data = cb._author_bodies(raw, decisions)
    assert data["findings"]["F1"]["post"] is False
    assert data["findings"]["F2"]["post"] is (decisions is None)
    assert "Posted: %d · Not posted: %d" % (
        1 if decisions is None else 0, 1 if decisions is None else 2) in data["overview"]
