import contextlib
import copy
import io
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "skills", "full-code-review", "scripts"))
import render_report as m  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "full-code-review"
TEMPLATE = (SKILL_ROOT / "assets" / "report.html").read_text(encoding="utf-8")


class DOM(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        values["_tag"] = tag
        values["_classes"] = set(values.get("class", "").split())
        self.nodes.append(values)

    def find_id(self, value):
        return next((node for node in self.nodes if node.get("id") == value), None)

    def find(self, tag=None, class_name=None, **attrs):
        found = []
        for node in self.nodes:
            if tag and node["_tag"] != tag:
                continue
            if class_name and class_name not in node["_classes"]:
                continue
            if any(node.get(key) != value for key, value in attrs.items()):
                continue
            found.append(node)
        return found


def report():
    return {
        "meta": {
            "target": "mr", "iid": 42, "project": "demo/project", "ticket": "DEMO-1",
            "head_sha": "abcdef1", "mr_state": "Draft", "title": "Review demo",
            "standfirst_md": "A **structured** review.", "verdict": "Fix, then merge",
        },
        "run": {
            "dimensions_run": ["sakura:correctness", "coordinator verification", "sakura:db"],
            "dimensions_skipped": [{"name": "sakura:tests", "why": "no tests changed"}],
            "diff_size": "12 files, 340 lines", "coverage": "all 12 changed files reviewed",
            "guidance": ["CLAUDE.md"], "notes_md": "Run complete.",
            "clean_notes": [{"dimension": "sakura:db", "note_md": "Queries look bounded."}],
        },
        "mutation_probe": {"mutants": 2, "killed": 1, "survived": 1,
                           "narrative_md": "One **survived**.", "aside_md": "Local only.",
                           "probes": [{"where": "a.py:2", "result": "survived",
                                       "mutation_md": "Broke the branch.",
                                       "test": "pytest -k a", "means_md": "Nothing covers it."},
                                      {"where": "z.py:9", "result": "killed",
                                       "mutation_md": "Broke the name.", "test": "pytest -k z",
                                       "means_md": "A test caught it."}]},
        "risk": {"level": "Medium", "verbatim_md": "**Likelihood:** Possible.",
                 "metrics": {"likelihood": {"level": "Possible", "note_md": "Only on one path."},
                             "impact": {"level": "Minor"},
                             "detection": {"level": "Weak"},
                             "rollback": {"level": "Clean"},
                             "blast_radius": {"level": "Narrow"}},
                 "mitigations_md": "Alerting on the metric would strengthen detection.",
                 "caveats": [{"title": "Scope", "body_md": "One path was not run."}]},
        "findings": [
            {"severity": "Nit", "dimension": "coordinator verification", "file": "z.py", "line": 9,
             "issue": "Name is vague: More detail follows.", "recommendation": "Rename `x`."},
            {"severity": "Must fix", "dimensions": ["sakura:correctness"], "file": "a.py", "line": "2-4",
             "title": "Incorrect result", "area": "prod", "evidence": "source verified",
             "body_md": "Returns **the wrong value**.", "aside_md": "Only when enabled.",
             "recommendation_md": "Return `expected`."},
            {"severity": "Should fix", "dimensions": ["sakura:db", "coordinator verification"],
             "file": "b.py", "line": "7", "title": "Query can grow",
             "body_md": "The query is not bounded.", "recommendation_md": "Add a bound."},
        ],
        "recommended_order": ["Fix the result", "Bound the query"],
        "assumptions": ["The feature is enabled"],
        "process_notes": [{"title": "Environment", "body_md": "Ran locally."}],
    }


def memory_payload():
    snapshot = {
        "schemaVersion": 1, "target_key": "demo", "identity": {"repo": "demo", "target": "mr:42"},
        "seat": "author", "base_sha": None, "head_sha": "a" * 40, "dimensions": ["sakura:db"],
        "guidance_hash": "b" * 64, "started_at": 1.0, "findings": [], "discussions": [],
        "discussions_available": True, "warnings": [], "invalidation_reason": None,
        "file_hashes": {}, "unchanged_files": [],
    }
    return {
        "snapshot": snapshot,
        "appears_fixed": [{"title": "Old issue", "file": "old.py", "line": 3,
                           "thread": {"url": "https://gitlab.example/discussion/1"}}],
        "warnings": [],
    }


def finding_memory(state="carried", disposition="fix"):
    return {
        "fingerprint": "c" * 64, "dimension": "sakura:db", "anchor_hash": "d" * 64,
        "state": state, "match": "exact", "disposition": disposition, "note": "Remember <this>",
        "suppress_post": True, "thread": {"discussion_id": 1, "note_id": 2,
                                          "url": "javascript:alert(1)", "resolved": False,
                                          "replies": [{"author": "<bot>", "body": "<script>bad</script>"}]},
        "candidates": [{"title": "Candidate <one>", "url": "https://gitlab.example/candidate"}],
        "human_context": [{"summary": "Human context", "url": "javascript:bad",
                           "note_id": 11, "discussion_id": "disc-1", "resolved": False,
                           "author": "alice", "body": "Human context body"}],
    }


def invoke(tmp_path, value, extra=None, filename="report.json"):
    path = Path(tmp_path) / filename
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    stdout = io.StringIO()
    stderr = io.StringIO()
    argv = ["--in", str(path), "--out-dir", str(tmp_path), "--no-open"] + (extra or [])
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        rc = m.main(argv)
    payload = json.loads(stdout.getvalue())
    return rc, payload, stderr.getvalue(), path


def parse(value):
    dom = DOM()
    dom.feed(value)
    return dom


def assert_dom_contract(value):
    dom = parse(value)
    topnavs = dom.find("header", "topnav")
    assert len(topnavs) == 1
    assert "data-storage-key" in topnavs[0] and "data-export-label" in topnavs[0]
    assert topnavs[0].get("data-review-seat") in ("author", "reviewer")
    cards = dom.find("article", "finding")
    assert cards
    for card in cards:
        assert card.get("id", "").startswith("F")
        assert card.get("data-title") and card.get("data-file")
        assert card.get("data-sev") in ("must", "should", "nit")
        assert isinstance(json.loads(card["data-dims"]), list)
    assert dom.find_id("tdetail") and dom.find_id("tnav")
    assert dom.find_id("no-match") and dom.find_id("saved") and dom.find_id("progress")
    assert dom.find_id("btn-export") and dom.find_id("btn-reset")
    progress = dom.find_id("progress")
    assert progress["_tag"] == "div" and "progress" in progress["_classes"]
    pstats = dom.find("button", "pstat", **{"data-filter": "disp"})
    assert {node["data-value"] for node in pstats} == {"fix", "later", "ignore", "detail", "none"}
    counts = dom.find("span", **{"data-count": "fix"})
    assert counts
    for severity in ("must", "should", "nit"):
        assert dom.find("button", "chip", **{"data-filter": "sev", "data-value": severity})
    assert dom.find("button", "chip", **{"data-filter": "dim"})
    assert dom.find_id("decide-bar")
    # every tab names a panel that exists, so the strip cannot outrun the panes
    tabs = dom.find("button", "tab")
    assert tabs and tabs[0].get("aria-selected") == "true"
    for tab in tabs:
        assert dom.find_id(tab["aria-controls"])


def test_id_determinism_and_stability(tmp_path):
    original = report()["findings"]
    shuffled_tiers = [original[1], original[0], original[2]]
    first = m.rank_findings(original)
    second = m.rank_findings(shuffled_tiers)
    assert [(x["id"], x["file"]) for x in first] == [(x["id"], x["file"]) for x in second]
    same_tier = [copy.deepcopy(original[2]), copy.deepcopy(original[2])]
    same_tier[0]["file"], same_tier[1]["file"] = "first.py", "second.py"
    ranked = m.rank_findings(same_tier)
    assert [x["file"] for x in ranked] == ["first.py", "second.py"]


def test_derived_numbers_and_order(tmp_path):
    value = m.render_html(report(), TEMPLATE)
    for slug, label in (("must", "Must fix"), ("should", "Should fix"), ("nit", "Nit")):
        assert ('<span class="astryx-status-dot dot--%s" aria-hidden="true"></span><b>1</b> %s'
                % (slug, label)) in value
    assert "3 findings · 1 Must fix · 1 Should fix · 1 Nit" in value
    assert value.index('id="F1"') < value.index('id="F2"') < value.index('id="F3"')
    rc, meta, _, _ = invoke(tmp_path, report())
    assert rc == 0
    assert [x["file"] for x in meta["order"]] == ["a.py", "b.py", "z.py"]
    assert meta["tally"] == {"must": 1, "should": 1, "nit": 1}


def test_old_schema_degradation(tmp_path):
    old = report()
    old["findings"] = [{"severity": "Should fix", "dimension": "sakura:db", "file": "old.py",
                        "line": 12, "issue": "First clause. More detail.",
                        "recommendation": "Use a cap.", "verified": True, "assumptions": []}]
    value = m.render_html(old, TEMPLATE)
    assert 'data-title="First clause"' in value
    assert 'data-dims="[&quot;sakura:db&quot;]"' in value
    assert "source verified" not in value
    assert "First clause. More detail." in value and "Use a cap." in value
    assert m.derive_title("First; second") == "First"
    assert m.derive_title("First: second") == "First"
    long = "word " * 30
    title = m.derive_title(long)
    assert len(title) <= 80 and title.endswith("…") and not title.endswith(" …")


def test_zero_findings(tmp_path):
    value = report()
    value["findings"] = []
    rendered = m.render_html(value, TEMPLATE)
    dom = parse(rendered)
    assert not dom.find("article", "finding")
    assert not dom.find_id("progress") and not dom.find_id("btn-export")
    assert "Queries look bounded." in rendered
    assert "Fix, then merge" in rendered
    rc, meta, _, _ = invoke(tmp_path, value)
    assert rc == 0 and "warnings" not in meta

    value["run"].pop("clean_notes")
    rc, meta, _, _ = invoke(tmp_path, value, filename="empty.json")
    assert rc == 0 and meta["warnings"]
    output = Path(meta["html"]).read_text(encoding="utf-8")
    assert "Per-dimension clean notes were not supplied" in output


def test_omission_rules(tmp_path):


    value = report()
    value["mutation_probe"] = None
    value["run"].pop("diff_size")
    value["run"].pop("coverage")
    value.pop("risk")
    value.pop("process_notes")
    rendered = m.render_html(value, TEMPLATE)
    assert 'id="mutation-probe"' not in rendered and 'id="risk"' not in rendered
    assert 'id="process-notes"' not in rendered
    assert "12 files, 340 lines" not in rendered and "changed files reviewed" not in rendered
def test_memory_sections_and_seeds_without_per_finding_context(tmp_path):
    value = report()
    value["findings"] = value["findings"][:1]
    value["memory"] = memory_payload()
    value["memory"]["warnings"] = ["discussion fetch <failed>"]
    value["memory"]["snapshot"]["invalidation_reason"] = "guidance changed"
    value["findings"][0]["memory"] = finding_memory()
    html = m.render_html(value, TEMPLATE)
    markdown = m.render_md(value)
    assert "Appears fixed" in html and "Re-found after resolution" not in html
    assert 'data-memory-disposition="fix"' in html
    assert 'data-memory-note="Remember &lt;this&gt;"' in html
    assert "Memory warnings" in html and "guidance changed" in html
    assert "Appears fixed" in markdown
    assert "Memory warnings" in markdown and "javascript:" not in markdown
    # per-finding memory is coordinator context and never reaches the reader
    for rendered in (html, markdown):
        assert "Candidate" not in rendered and "Human context" not in rendered
        assert "&lt;bot&gt;" not in rendered and "<bot>" not in rendered
    assert 'class="memory-context"' not in html and "**Memory:**" not in markdown


def test_impact_line_renders_above_body_and_is_escaped(tmp_path):
    value = report()
    value["findings"] = value["findings"][:1]
    value["findings"][0]["impact"] = "Merchants  see <b>wrong</b>   `totals`."
    html = m.render_html(value, TEMPLATE)
    markdown = m.render_md(value)
    impact = '<p class="f-impact">Merchants see &lt;b&gt;wrong&lt;/b&gt; <code>totals</code>.</p>'
    assert impact in html
    card = html[html.index('<article class="finding"'):]
    assert card.index('class="anchor"') < card.index("f-impact") < card.index("</article>")
    assert "**Impact:** Merchants see <b>wrong</b> `totals`." in markdown


def test_non_text_impact_is_dropped_with_warning(tmp_path):
    value = report()
    value["findings"][0]["impact"] = ["not", "text"]
    prepared, warnings = m._prepare_report(value)
    assert all("impact" not in finding for finding in prepared["findings"])
    assert any("impact" in warning for warning in warnings)


def test_fix_md_non_text_is_dropped_and_text_is_collapsed(tmp_path):
    value = report()
    value["findings"][0]["fix_md"] = ["not", "text"]
    value["findings"][1]["fix_md"] = "Use  `expected`   here"
    prepared, warnings = m._prepare_report(value)
    by_file = {finding["file"]: finding for finding in prepared["findings"]}
    assert "fix_md" not in by_file["z.py"]
    assert by_file["a.py"]["fix_md"] == "Use `expected` here"
    assert any("fix_md" in warning for warning in warnings)
    assert not any("unknown" in warning and "fix_md" in warning for warning in warnings)


def test_impact_and_fix_md_reject_multiline_and_over_cap(tmp_path):
    cases = [("impact", "one\ntwo"), ("impact", "one\rtwo"), ("impact", "a\u2028b"),
             ("impact", "a\u2029b"), ("impact", "x" * 201),
             ("fix_md", "one\ntwo"), ("fix_md", "a\u2028b"), ("fix_md", "y" * 161),
             ("fix_md", "trailing\n")]
    for index, (field, bad) in enumerate(cases):
        value = report()
        value["findings"][1][field] = bad
        rc, payload, _, _ = invoke(tmp_path, value, filename="posted-%d.json" % index)
        assert rc == 2 and set(payload) == {"error"}, (field, bad)
        assert field in payload["error"] and "a.py:2-4" in payload["error"]
    for field, cap in (("impact", 200), ("fix_md", 160)):
        value = report()
        value["findings"][1][field] = "x" * cap
        rc, _, _, _ = invoke(tmp_path, value, filename="cap-%s.json" % field)
        assert rc == 0
    value = report()
    value["findings"][1]["impact"] = "a" + " " * 300 + "b"
    rc, payload, _, _ = invoke(tmp_path, value, filename="padded.json")
    assert rc == 2 and "impact" in payload["error"] and "exceeds 200" in payload["error"]
    value = report()
    value["findings"][1]["impact"] = "a" + " " * 198 + "b"
    assert len(value["findings"][1]["impact"]) == 200
    assert m._prepare_report(value)[0]["findings"][0]["impact"] == "a b"


def test_finding_digest_covers_impact_and_fix_md(tmp_path):
    base = m._prepare_report(report())[0]["findings"]
    digest = m.finding_digest(base)
    for field in ("impact", "fix_md"):
        changed = copy.deepcopy(base)
        changed[0][field] = "different"
        assert m.finding_digest(changed) != digest
    first = copy.deepcopy(base)
    first[0]["fix_md"] = "one"
    second = copy.deepcopy(base)
    second[0]["fix_md"] = "two"
    assert m.finding_digest(first) != m.finding_digest(second)


def test_human_context_entries_are_type_checked(tmp_path):
    good = {"note_id": 5, "discussion_id": "d", "resolved": False, "author": "a", "body": "b"}
    bad_fields = [("note_id", True), ("note_id", "5"), ("note_id", None), ("note_id", 5.0),
                  ("discussion_id", ""), ("discussion_id", 7), ("discussion_id", None),
                  ("resolved", "no"), ("resolved", None), ("resolved", 0)]
    for field, bad in bad_fields:
        value = report()
        value["findings"] = value["findings"][:1]
        value["findings"][0]["memory"] = finding_memory()
        value["findings"][0]["memory"]["human_context"] = [dict(good, **{field: bad})]
        try:
            m._prepare_report(value)
            assert False, (field, bad)
        except ValueError as exc:
            assert field in str(exc) and "human_context" in str(exc)
    for field in ("note_id", "discussion_id", "resolved"):
        value = report()
        value["findings"] = value["findings"][:1]
        value["findings"][0]["memory"] = finding_memory()
        entry = {key: val for key, val in good.items() if key != field}
        value["findings"][0]["memory"]["human_context"] = [entry]
        try:
            m._prepare_report(value)
            assert False, field
        except ValueError as exc:
            assert field in str(exc)
    value = report()
    value["findings"] = value["findings"][:1]
    value["findings"][0]["memory"] = finding_memory()
    value["findings"][0]["memory"]["candidates"] = [{"title": "no ids needed"}]
    m._prepare_report(value)


def reply_report(seat, human_context):
    value = report()
    value["findings"] = value["findings"][:1]
    value["findings"][0]["memory"] = finding_memory()
    value["findings"][0]["memory"]["human_context"] = human_context
    if seat == "reviewer":
        value["meta"]["seat"] = "reviewer"
        value["meta"]["head_sha"] = "a" * 40
    return value


def reply_attr(html):
    match = re.search(r'data-reply-targets="([^"]*)"', html)
    return json.loads(__import__("html").unescape(match.group(1))) if match else None


def test_reply_candidates_reviewer_only_sorted_and_capped(tmp_path):
    entries = [
        {"note_id": 30, "discussion_id": "d3", "resolved": False, "author": "carol",
         "body": "late", "url": "https://gitlab.example/n30"},
        {"note_id": 10, "discussion_id": "d1", "resolved": False, "author": "alice",
         "body": "  first \n\n  thread " + "x" * 400, "url": "javascript:alert(1)"},
        {"note_id": 20, "discussion_id": "d2", "resolved": True, "author": "bob", "body": "done"},
    ]
    html = m.render_html(reply_report("reviewer", entries), TEMPLATE)
    candidates = reply_attr(html)
    assert [item["note_id"] for item in candidates] == [10, 30]
    assert candidates[0]["author"] == "alice" and candidates[0]["url"] is None
    assert candidates[0]["excerpt"].startswith("first thread xxx")
    assert len(candidates[0]["excerpt"]) == 200
    assert candidates[1] == {"note_id": 30, "author": "carol", "excerpt": "late",
                             "url": "https://gitlab.example/n30"}
    assert set(candidates[0]) == {"note_id", "author", "excerpt", "url"}
    assert reply_attr(m.render_html(reply_report("author", entries), TEMPLATE)) is None
    resolved_only = [dict(entries[2])]
    assert reply_attr(m.render_html(reply_report("reviewer", resolved_only), TEMPLATE)) is None
    assert reply_attr(m.render_html(reply_report("reviewer", []), TEMPLATE)) is None


def test_own_comments_are_never_reply_candidates(tmp_path):
    entries = [
        {"note_id": 10, "discussion_id": "d1", "resolved": False, "author": "me",
         "body": "mine", "own": True},
        {"note_id": 20, "discussion_id": "d2", "resolved": False, "author": "bob",
         "body": "theirs", "own": False},
        {"note_id": 30, "discussion_id": "d3", "resolved": False, "author": "carol",
         "body": "older snapshot without the key"},
    ]
    candidates = reply_attr(m.render_html(reply_report("reviewer", entries), TEMPLATE))
    assert [item["note_id"] for item in candidates] == [20, 30]
    own_only = [dict(entries[0])]
    assert reply_attr(m.render_html(reply_report("reviewer", own_only), TEMPLATE)) is None


def test_human_context_own_must_be_a_boolean():
    good = {"note_id": 5, "discussion_id": "d", "resolved": False, "author": "a", "body": "b"}
    for bad in ("yes", 1, None):
        value = reply_report("reviewer", [dict(good, own=bad)])
        try:
            m._prepare_report(value)
            assert False, bad
        except ValueError as exc:
            assert "own" in str(exc) and "human_context" in str(exc)
    m._prepare_report(reply_report("reviewer", [dict(good, own=True)]))


def test_reply_candidates_stay_attribute_only(tmp_path):
    entries = [{"note_id": 4, "discussion_id": "d", "resolved": False, "author": "<bot>",
                "body": "<script>bad</script>"}]
    html = m.render_html(reply_report("reviewer", entries), TEMPLATE)
    card = html[html.index('<article class="finding"'):html.index("</article>")]
    assert "<script>" not in card and "<bot>" not in card
    assert card.count("&lt;bot&gt;") == 1
    assert reply_attr(html)[0]["author"] == "<bot>"
    assert "<bot>" not in m.render_md(reply_report("reviewer", entries))


def test_template_has_reply_toggle_and_export_line(tmp_path):
    assert "Reply in support" in TEMPLATE and "data-reply-targets" not in TEMPLATE
    assert "replyTargets" in TEMPLATE
    assert "Candidate" not in TEMPLATE
    assert 'lines.push("  reply: " + replyTarget[card.id].note_id)' in TEMPLATE
    assert TEMPLATE.index('"  reply: "') < TEMPLATE.index('lines.push("  > " + line)')
    assert 'reply: true' in TEMPLATE and 'typeof record.reply === "boolean"' in TEMPLATE
    assert "cards.forEach(function (card) { entry(card.id); });" in TEMPLATE
    start = TEMPLATE.index("var replyTarget")
    block = TEMPLATE[start:TEMPLATE.index("var saveTimer")]
    assert "innerHTML" not in block and "textContent" in block


def test_reply_toggle_is_seeded_on_and_gates_the_export_line():
    seed = 'seeded[card.id] = { disp: disp, note: card.dataset.memoryNote || "", reply: true };'
    guard = 'if (replyTarget[card.id] && record.reply) lines.push("  reply: "'
    toggle = "entry(card.id).reply = checkbox.checked;"
    for line in (seed, guard, toggle):
        assert TEMPLATE.count(line) == 1, line


def test_memory_sections_keep_history_for_zero_findings(tmp_path):
    value = report()
    value["findings"] = []
    value["memory"] = memory_payload()
    html = m.render_html(value, TEMPLATE)
    markdown = m.render_md(value)
    assert "Appears fixed" in html and "Appears fixed" in markdown
    assert "Re-found after resolution" not in html and "Possible regression" not in markdown


def test_memory_schema_rejects_malformed_hash_and_thread(tmp_path):
    value = report()
    value["findings"] = value["findings"][:1]
    value["memory"] = memory_payload()
    value["findings"][0]["memory"] = finding_memory()
    value["findings"][0]["memory"]["fingerprint"] = "not-a-hash"
    try:
        m.render_html(value, TEMPLATE)
        assert False, "malformed memory fingerprint should fail"
    except ValueError as exc:
        assert "fingerprint" in str(exc)
    value = report()
    value["findings"] = value["findings"][:1]
    value["memory"] = memory_payload()
    value["findings"][0]["memory"] = finding_memory()
    value["findings"][0]["memory"]["thread"]["replies"] = "bad"
    try:
        m.render_md(value)
        assert False, "malformed memory replies should fail"
    except ValueError as exc:
        assert "replies" in str(exc)


def test_slug_and_naming(tmp_path):
    assert m.slugify(" Feature / Foo ") == "feature-foo"
    assert m.target_slug({"target": "mr", "iid": 88}) == "88"
    assert m.target_slug({"target": "local"}) == "local"
    one = m.target_slug({"target": "branch", "branch": "feat/foo"})
    two = m.target_slug({"target": "branch", "branch": "feat-foo"})
    assert one != two and one.startswith("feat-foo-") and two.startswith("feat-foo-")

    value = report()
    value["meta"] = {"target": "local", "title": "Local", "verdict": "Approve"}
    rc, meta, _, _ = invoke(tmp_path, value)
    assert rc == 0 and Path(meta["html"]).name == "review-local-findings.html"


def test_review_out_dir_and_out_override(tmp_path):
    value = report()
    source = Path(tmp_path) / "source.json"
    source.write_text(json.dumps(value), encoding="utf-8")
    env_dir = Path(tmp_path) / "from-env"
    old = os.environ.get("REVIEW_OUT_DIR")
    os.environ["REVIEW_OUT_DIR"] = str(env_dir)
    try:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = m.main(["--in", str(source), "--no-open"])
        payload = json.loads(stdout.getvalue())
    finally:
        if old is None:
            os.environ.pop("REVIEW_OUT_DIR", None)
        else:
            os.environ["REVIEW_OUT_DIR"] = old
    assert rc == 0 and Path(payload["html"]).parent == env_dir

    custom = Path(tmp_path) / "custom-name.md"
    rc, payload, _, _ = invoke(tmp_path, value, ["--format", "md", "--out", str(custom)], "custom.json")
    assert rc == 0 and payload["html"] is None and Path(payload["md"]) == custom
    rc, payload, _, _ = invoke(tmp_path, value, ["--format", "both", "--out", str(custom)], "bad-out.json")
    assert rc == 2 and "error" in payload


def test_storage_key(tmp_path):
    value = report()
    first = m.storage_key(value["meta"], m.rank_findings(value["findings"]))
    second = m.storage_key(value["meta"], m.rank_findings(value["findings"]))
    assert first == second
    for field, replacement in (("file", "changed.py"), ("line", "999"), ("severity", "Should fix")):
        changed = copy.deepcopy(value["findings"])
        changed[1][field] = replacement
        assert m.storage_key(value["meta"], m.rank_findings(changed)) != first
    changed = copy.deepcopy(value["findings"])
    changed[1], changed[2] = changed[2], changed[1]
    changed[2]["severity"] = changed[1]["severity"]
    assert m.storage_key(value["meta"], m.rank_findings(changed)) != first
    # a different problem reported at the same location and severity must not reuse the key
    for field in ("title", "body_md", "recommendation_md"):
        changed = copy.deepcopy(value["findings"])
        changed[1][field] = "a substantively different finding"
        assert m.storage_key(value["meta"], m.rank_findings(changed)) != first
    value["meta"]["storage_key"] = "authored-key"
    assert m.storage_key(value["meta"], value["findings"]) == "authored-key"


def test_format_and_browser_matrix(tmp_path):
    value = report()
    opened = []
    saved = m.webbrowser.open
    try:
        m.webbrowser.open = lambda url: opened.append(url) or True
        rc, payload, _, _ = invoke(tmp_path, value, ["--format", "md"], "md.json")
        assert rc == 0 and payload["html"] is None and not opened
        rc, payload, _, _ = invoke(tmp_path, value, ["--format", "both"], "both.json")
        assert rc == 0 and Path(payload["html"]).exists() and Path(payload["md"]).exists() and not opened
        source = Path(tmp_path) / "open.json"
        source.write_text(json.dumps(value), encoding="utf-8")
        target = Path(tmp_path) / "review #1.html"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = m.main(["--in", str(source), "--out", str(target)])
        payload = json.loads(stdout.getvalue())
        assert rc == 0 and payload["opened"] is True and len(opened) == 1
        assert "%20%231.html" in opened[0]
        m.webbrowser.open = lambda url: (_ for _ in ()).throw(RuntimeError("no browser"))
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = m.main(["--in", str(source), "--out", str(target)])
        assert rc == 0 and json.loads(stdout.getvalue())["opened"] is False
    finally:
        m.webbrowser.open = saved


def test_utf8_round_trip(tmp_path):
    value = report()
    value["meta"]["title"] = "Ellipsis … and café"
    value["findings"][1]["body_md"] = "Unicode → survives."
    rc, payload, _, _ = invoke(tmp_path, value, ["--format", "both"], "utf8.json")
    assert rc == 0
    assert "café" in Path(payload["html"]).read_text(encoding="utf-8")
    assert "Unicode → survives" in Path(payload["md"]).read_text(encoding="utf-8")


def test_slot_mechanics_and_script_identity(tmp_path):
    synthetic = "<html><!-- slot:title --><title>x</title><!-- /slot:title --><body><!-- slot:main -->x<!-- /slot:main --><script>{x}</script></body></html>"
    rendered = m.render_html(report(), synthetic)
    assert "<!-- slot:" not in rendered and rendered.count("<script>") == 1
    assert re.findall(r"<script>(.*?)</script>", rendered, re.S) == re.findall(r"<script>(.*?)</script>", synthetic, re.S)
    for broken in (synthetic.replace("<!-- slot:title -->", ""), synthetic + "<!-- slot:main --><!-- /slot:main -->"):
        try:
            m.render_html(report(), broken)
            assert False, "missing/duplicate slot should fail"
        except ValueError:
            pass
    full = m.render_html(report(), TEMPLATE)
    assert re.findall(r"<script>(.*?)</script>", full, re.S) == re.findall(r"<script>(.*?)</script>", TEMPLATE, re.S)


def test_template_error_reaches_json_contract(tmp_path):
    value = report()
    broken = Path(tmp_path) / "broken.html"
    broken.write_text("<html><!-- slot:title -->x<!-- /slot:title --></html>", encoding="utf-8")
    saved = m._template_path
    try:
        m._template_path = lambda: str(broken)
        rc, payload, stderr, _ = invoke(tmp_path, value, filename="template-error.json")
    finally:
        m._template_path = saved
    assert rc == 2 and "error" in payload and stderr == ""


def test_escaping_end_to_end(tmp_path):
    value = report()
    value["findings"][1]["title"] = 'Bad <"> title'
    value["findings"][1]["body_md"] = "<img src=x onerror=boom>"
    rendered = m.render_html(value, TEMPLATE)
    assert 'data-title="Bad &lt;&quot;&gt; title"' in rendered
    assert "Bad &lt;&quot;&gt; title" in rendered
    assert "<img src=x" not in rendered and "&lt;img" in rendered


def test_dom_contract_and_dimension_round_trip(tmp_path):
    rendered = m.render_html(report(), TEMPLATE)
    assert_dom_contract(rendered)
    assert_dom_contract(TEMPLATE)
    cards = parse(rendered).find("article", "finding")
    target = next(card for card in cards if card["id"] == "F2")
    assert json.loads(target["data-dims"]) == ["sakura:db", "coordinator verification"]
    broken = re.sub(r'<button class="btn" type="button" id="btn-export">.*?</button>', "", rendered, count=1)
    assert parse(broken).find_id("btn-export") is None
    try:
        assert_dom_contract(broken)
        assert False, "parsed DOM pin must detect the missing element"
    except AssertionError:
        pass


def test_validation_errors(tmp_path):
    cases = [[], {"meta": [], "findings": []}]
    bad = report(); bad["meta"]["target"] = "tag"; cases.append(bad)
    bad = report(); bad["findings"] = "oops"; cases.append(bad)
    bad = report(); bad["findings"] = ["oops"]; cases.append(bad)
    bad = report(); bad["meta"]["title"] = []; cases.append(bad)
    bad = report(); bad["meta"]["title"] = "   "; cases.append(bad)
    bad = report(); bad["findings"][0]["dimensions"] = ["ok", 3]; cases.append(bad)
    bad = report(); bad["meta"]["iid"] = "7/x"; cases.append(bad)
    bad = report(); bad["meta"]["iid"] = 0; cases.append(bad)
    bad = report(); bad["meta"] = {"target": "branch", "title": "x", "verdict": "Approve"}; cases.append(bad)
    bad = report(); bad["meta"] = {"target": "branch", "branch": "***", "title": "x", "verdict": "Approve"}; cases.append(bad)
    bad = report(); bad["findings"][0]["severity"] = "Blocker"; cases.append(bad)
    bad = report(); bad["meta"].pop("verdict"); cases.append(bad)
    bad = report(); bad["findings"][0].pop("file"); cases.append(bad)
    bad = report(); bad["findings"][0]["line"] = ""; cases.append(bad)
    bad = report(); bad["findings"][1]["file"] = bad["findings"][0]["file"]; bad["findings"][1]["line"] = bad["findings"][0]["line"]; cases.append(bad)
    bad = report(); bad["findings"][0]["title"] = "bad\nline"; cases.append(bad)
    bad = report(); bad["meta"]["title"] = "bad\rline"; cases.append(bad)
    bad = report(); bad["meta"]["title"] = "bad trailing\n"; cases.append(bad)
    bad = report(); bad["findings"][0]["file"] = "bad\u2028file"; cases.append(bad)
    bad = report(); bad["findings"][0]["line"] = "9\r"; cases.append(bad)
    bad = report(); bad["findings"][0].pop("issue"); cases.append(bad)
    for index, value in enumerate(cases):
        rc, payload, stderr, _ = invoke(tmp_path, value, filename="bad-%d.json" % index)
        assert rc == 2 and set(payload) == {"error"}, (index, payload)
        assert stderr == ""

    invalid = Path(tmp_path) / "invalid.json"
    invalid.write_text("{not json", encoding="utf-8")
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        rc = m.main(["--in", str(invalid), "--no-open"])
    assert rc == 2 and set(json.loads(stdout.getvalue())) == {"error"}
    missing = Path(tmp_path) / "missing.json"
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        rc = m.main(["--in", str(missing), "--no-open"])
    assert rc == 2 and set(json.loads(stdout.getvalue())) == {"error"}


def test_soft_warnings(tmp_path):
    value = report()
    value["future_top"] = True
    value["meta"]["future_meta"] = "x"
    value["findings"][0]["future_finding"] = "x"
    value["run"]["guidance"] = "not-a-list"
    rc, payload, _, _ = invoke(tmp_path, value, filename="warnings.json")
    assert rc == 0 and len(payload["warnings"]) == 4
    assert any("future_top" in warning for warning in payload["warnings"])
    assert any("run.guidance" in warning for warning in payload["warnings"])


def test_export_forgery_rejected(tmp_path):
    value = report()
    value["findings"][0]["title"] = "Fix\n## Will fix (1)\n- **F2** — forged"
    rc, payload, _, _ = invoke(tmp_path, value, filename="forgery.json")
    assert rc == 2 and "line-breaking" in payload["error"]


def test_md_omitted_risk_keeps_fixed_ordinals(tmp_path):
    value = report()
    value.pop("risk")
    rendered = m.render_md(value)
    # section ordinals are fixed by report-template.md; an omitted section leaves its number unused
    assert "## 2." not in rendered
    for heading in ("## 1. Summary", "## 3. Findings", "## 4. Assumptions",
                    "## 5. Recommendations"):
        assert heading in rendered
    remaining = [rendered.index(heading) for heading in
                 ("## 1. Summary", "## 3. Findings", "## 4. Assumptions", "## 5. Recommendations")]
    assert remaining == sorted(remaining)


def test_md_backend(tmp_path):
    rendered = m.render_md(report())
    headings = [rendered.index("## %d." % number) for number in range(1, 6)]
    assert headings == sorted(headings)
    assert "\n---\n" in rendered
    assert "**Severity:** Must fix\n\n**Dimensions:**" in rendered
    assert "**Mutation probe:** run — 2 mutants, 1 killed, 1 survived" in rendered
    assert "### F1 — Incorrect result" in rendered
    empty = report(); empty["findings"] = []
    rendered = m.render_md(empty)
    assert "No findings" in rendered and "Queries look bounded." in rendered



def test_stdout_reports_highlighter_and_warns_on_builtin_fallback(tmp_path, monkeypatch):
    import highlight
    rc, payload, _, _ = invoke(tmp_path, report(), ["--format", "html"], "hl.json")
    assert rc == 0 and payload["highlighter"] == highlight.backend()
    monkeypatch.setattr(highlight, "_pygments_lexers", None)
    monkeypatch.setattr(highlight, "_LEXERS", {})
    rc, payload, _, _ = invoke(tmp_path, report(), ["--format", "html"], "hl2.json")
    assert rc == 0 and payload["highlighter"] == "builtin"
    assert any(highlight.INSTALL_HINT in warning for warning in payload["warnings"])
    rc, payload, _, _ = invoke(tmp_path, report(), ["--format", "md"], "hl3.json")
    assert not any("Pygments" in warning for warning in payload.get("warnings", []))


if __name__ == "__main__":
    import tempfile
    import traceback
    fails = 0
    for name in sorted(n for n in dict(globals()) if n.startswith("test_")):
        fn = globals()[name]
        if not callable(fn):
            continue
        with tempfile.TemporaryDirectory() as td:
            try:
                fn(Path(td))
                print("PASS", name)
            except Exception:
                fails += 1
                print("FAIL", name)
                traceback.print_exc()
    print("DONE fails=%d" % fails)
    sys.exit(1 if fails else 0)


def test_risk_kpis_tone_per_metric(tmp_path):
    value = report()
    rendered = m.render_html(value, TEMPLATE)
    # the same word means opposite things across metrics, so tone is resolved per metric
    assert 'dot--warn' in rendered   # likelihood Possible
    assert 'dot--good' in rendered   # impact Minor, rollback Clean
    assert 'dot--bad' in rendered    # detection Weak
    # the metric dot speaks good/warn/bad; the level Token speaks palette colours
    assert '<span class="astryx-token" data-tone="yellow">Medium</span>' in rendered
    assert "Lowering this risk" in rendered
    # verbatim is preserved, folded behind a disclosure once metrics lead
    assert '<details class="verbatim">' in rendered and "Likelihood:" in rendered
    authored = report()
    authored["risk"]["metrics"]["detection"]["tone"] = "good"
    assert 'dot--good' in m.render_html(authored, TEMPLATE)


def test_risk_without_metrics_keeps_plain_verbatim(tmp_path):
    value = report()
    value["risk"].pop("metrics")
    value["risk"].pop("mitigations_md")
    rendered = m.render_html(value, TEMPLATE)
    assert '<div class="metrics">' not in rendered
    assert '<details class="verbatim">' not in rendered
    assert "Likelihood:" in rendered


def test_probe_rows_and_unrecorded_fields(tmp_path):
    value = report()
    rendered = m.render_html(value, TEMPLATE)
    assert '<span class="astryx-token" data-tone="red">Survived</span>' in rendered
    assert '<span class="astryx-token" data-tone="green">Killed</span>' in rendered
    assert "What it proves" in rendered and "pytest -k a" in rendered
    sparse = report()
    sparse["mutation_probe"]["probes"] = [{"result": "nonsense"}]
    rendered = m.render_html(sparse, TEMPLATE)
    assert '<span class="astryx-token" data-tone="gray">Unrecorded</span>' in rendered
    assert "Not recorded." in rendered


def test_pane_order_leads_with_findings(tmp_path):
    rendered = m.render_html(report(), TEMPLATE)
    # findings are the work surface, so they lead; context panes follow in the tab strip
    order = [rendered.index('id="pane-%s"' % name)
             for name in ("findings", "summary", "run", "notes")]
    assert order == sorted(order)
    # the mutation probe reads with the rest of the run conditions, not on its own
    assert (rendered.index('id="pane-run"') < rendered.index('id="mutation-probe"')
            < rendered.index('id="pane-notes"'))


def test_controls_strip_and_export_panel(tmp_path):
    rendered = m.render_html(report(), TEMPLATE)
    # progress and filters pin above the rail list; export pins below it
    assert rendered.index('id="progress"') < rendered.index('class="filters"')
    assert rendered.index('class="filters"') < rendered.index('id="tnav"')
    assert rendered.index('id="tnav"') < rendered.index('class="texport"')
    assert '3 of 3 still undecided' in rendered
    assert "paste it back" in rendered


def test_rail_is_drag_resizable(tmp_path):
    rendered = m.render_html(report(), TEMPLATE)
    # the handle ships inside the rail, after the export panel, so it spans the
    # whole column rather than any one of the three stacked regions
    assert rendered.index('class="texport"') < rendered.index('class="rail-resizer"')
    assert rendered.index('class="rail-resizer"') < rendered.index("</aside>")
    assert 'role="separator"' in rendered and 'aria-orientation="vertical"' in rendered
    assert 'tabindex="0"' in rendered
    # the grid column it drives has to stay a variable with a fallback, or a
    # report opened before anything is dragged renders a zero-width rail
    assert "grid-template-columns: var(--rail-w, 340px) minmax(0, 1fr)" in rendered
    # width is a global preference; the triage blob is per-report and exported
    assert '"sakura-review:rail-width"' in rendered
    key = re.search(r'data-storage-key="([^"]+)"', rendered).group(1)
    assert key != "sakura-review:rail-width"


def test_findings_fill_the_detail_pane(tmp_path):
    rendered = m.render_html(report(), TEMPLATE)
    assert ".finding { min-width: 0; }" in rendered
    assert "max-width: 96ch" not in rendered
    assert "max-width: 74ch" not in rendered


def test_type_ramp_override_outranks_the_vendored_theme(tmp_path):
    rendered = m.render_html(report(), TEMPLATE)
    # the theme declares the ramp inside @layer astryx-theme; an unlayered
    # :root block is what beats it, so the override must stay after the tokens
    assert rendered.index("/* END astryx-tokens */") < rendered.index("--font-size-base: 1rem;")
    assert rendered.index("--font-size-base: 1rem;") < rendered.index("@media (max-width: 64rem)")


def test_recommended_order_is_markdown_only(tmp_path):
    value = report()
    rendered = m.render_html(value, TEMPLATE)
    assert 'id="recommended-order"' not in rendered
    assert "Bound the query" not in rendered
    assert "Bound the query" in m.render_md(value)


def test_reviewer_mode_switches_labels_and_isolates_storage(tmp_path):
    author = report()
    reviewer = copy.deepcopy(author)
    reviewer["meta"]["seat"] = "reviewer"
    reviewer["meta"]["head_sha"] = "a" * 40
    author_html = m.render_html(author, TEMPLATE)
    reviewer_html = m.render_html(reviewer, TEMPLATE)
    assert 'data-review-seat="reviewer"' in reviewer_html
    assert ">Blocking</span>" in reviewer_html
    assert ">Non-blocking</span>" in reviewer_html
    assert ">Question</span>" in reviewer_html
    assert ">Drop</span>" in reviewer_html
    assert "var VOCAB" in reviewer_html and "var SEAT" in reviewer_html
    author_key = re.search(r'data-storage-key="([^"]+)"', author_html).group(1)
    reviewer_key = re.search(r'data-storage-key="([^"]+)"', reviewer_html).group(1)
    assert author_key != reviewer_key
    assert reviewer_key == re.search(r'data-storage-key="([^"]+)"', m.render_html(reviewer, TEMPLATE)).group(1)


def test_reviewer_report_requires_mr_and_full_head(tmp_path):
    value = report()
    value["meta"]["seat"] = "reviewer"
    for bad in (None, "abcdef1", "A" * 40):
        candidate = copy.deepcopy(value)
        candidate["meta"]["head_sha"] = bad
        try:
            m.render_html(candidate, TEMPLATE)
            assert False
        except ValueError as exc:
            assert "head_sha" in str(exc)
    candidate = copy.deepcopy(value)
    candidate["meta"]["head_sha"] = "a" * 40
    candidate["meta"]["target"] = "local"
    try:
        m.render_html(candidate, TEMPLATE)
        assert False
    except ValueError as exc:
        assert "target an MR" in str(exc)


def test_diff_only_forces_unverified_and_renders_limitation(tmp_path):
    value = report()
    value["meta"]["seat"] = "reviewer"
    value["meta"]["head_sha"] = "a" * 40
    value["run"]["source_access"] = "diff-only"
    value["run"]["source_access_reason"] = "Temporary clone was declined."
    value["findings"][0]["verified"] = True
    prepared, _ = m._prepare_report(value)
    assert all(finding["verified"] is False for finding in prepared["findings"])
    html = m.render_html(value, TEMPLATE)
    assert "Every finding is unverified" in html
    assert "Temporary clone was declined" in html


def test_reset_counts_a_toggled_off_reply_as_a_change():
    start = TEMPLATE.index('getElementById("btn-reset")')
    block = TEMPLATE[start:TEMPLATE.index('flash("Reset")', start)]
    assert "replyTarget[card.id] && record.reply === false" in block
    assert "state = { __seat: SEAT };" in block and "entry(card.id)" in block


def handoff_blob(rendered):
    match = re.search(r'<script type="application/json" id="handoff-data">(.*?)</script>', rendered, re.S)
    return json.loads(match.group(1)) if match else None


def test_handoff_blob_carries_raw_finding_text_and_target(tmp_path):
    value = report()
    value["meta"].update({"repo_root": "/work/repo", "source_branch": "feat/x",
                          "web_url": "https://gitlab.example/demo/project/-/merge_requests/42"})
    rc, meta, _, path = invoke(tmp_path, value)
    assert rc == 0 and "warnings" not in meta
    blob = handoff_blob(Path(meta["html"]).read_text(encoding="utf-8"))
    assert blob["label"] == "MR !42" and blob["seat"] == "author"
    assert blob["repo_root"] == "/work/repo" and blob["source_branch"] == "feat/x"
    assert blob["web_url"].endswith("/merge_requests/42")
    assert blob["report_path"] == str(path.resolve())
    prepared, _ = m._prepare_report(value)
    assert [item["id"] for item in blob["findings"]] == [item["id"] for item in prepared["findings"]]
    for item, trusted in zip(blob["findings"], prepared["findings"]):
        assert item["body_md"] == trusted["body_md"]
        assert item["file"] == trusted["file"] and item["line"] == trusted["line"]


def test_handoff_blob_cannot_close_its_script_tag():
    value = report()
    value["findings"][1]["body_md"] = "</script><img src=x onerror=boom> &   done"
    rendered = m.render_html(value, TEMPLATE)
    raw = re.search(r'id="handoff-data">(.*?)</script>', rendered, re.S).group(1)
    assert "<" not in raw and ">" not in raw and " " not in raw
    assert any(item.get("body_md") == value["findings"][1]["body_md"]
               for item in handoff_blob(rendered)["findings"])


def test_handoff_blob_absent_without_findings():
    value = report()
    value["findings"] = []
    assert handoff_blob(m.render_html(value, TEMPLATE)) is None


def test_handoff_meta_fields_are_validated():
    value = report()
    value["meta"]["source_branch"] = "feat/x\nInjected: yes"
    try:
        m.render_html(value, TEMPLATE)
        assert False
    except ValueError as exc:
        assert "meta.source_branch" in str(exc)
    value = report()
    value["meta"]["web_url"] = "javascript:alert(1)"
    value["meta"]["repo_root"] = 7
    prepared, warnings = m._prepare_report(value)
    assert "web_url" not in prepared["meta"] and "repo_root" not in prepared["meta"]
    assert len([w for w in warnings if "web_url" in w or "repo_root" in w]) == 2


def test_template_script_has_no_raw_line_separators():
    # js treats raw U+2028/U+2029 as line terminators, so one inside a regex literal is a syntax error
    for script in re.findall(r"<script>(.*?)</script>", TEMPLATE, re.S):
        assert " " not in script and " " not in script
