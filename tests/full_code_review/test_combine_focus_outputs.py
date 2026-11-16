"""Combining a dimension's focus-agent files into the per-dimension layout the merge ledger reads."""

import json
import subprocess
import sys
from pathlib import Path

import check_merge_ledger
import combine_focus_outputs

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "full-code-review" / "scripts" / "combine_focus_outputs.py"
REAL_DIMENSIONS = Path(__file__).resolve().parents[2] / "skills" / "full-code-review" / "references" / "lenses"

CHECKLIST = """# Dimension: Fake (`correctness`)

You are the `correctness` specialist.

## Haiku focuses

One haiku agent per line.

- `edges`: wrong conditionals and empty inputs.
- `writes` [table: state-writes table]: the state-writes table.
- `times` [table: boundary table]: the boundary table.
"""

WRITES_HEADER = "| Record and transition | Existing writer | New code does it? |\n|---|---|---|\n"
BOUNDARY_HEADER = "| Boundary | What can arrive | What the layer above catches |\n|---|---|---|\n"


def finding(line="10", **overrides):
    item = {"severity": "Should fix", "dimension": "correctness", "file": "app.py", "line": line,
            "issue": "issue", "recommendation": "fix", "verified": True, "assumptions": []}
    item.update(overrides)
    return item


def setup(tmp_path, files, agents=None):
    """Write focus files under a run dir and a dispatch.json, returning the run dir."""
    (tmp_path / "raw").mkdir()
    (tmp_path / "tables").mkdir()
    dims = tmp_path / "dimensions"
    dims.mkdir()
    (dims / "correctness.md").write_text(CHECKLIST, encoding="utf-8")
    for relative, content in files.items():
        text = content if isinstance(content, str) else json.dumps(content)
        (tmp_path / relative).write_text(text, encoding="utf-8")
    manifest = {"agents": agents if agents is not None else [{"name": "correctness"}]}
    (tmp_path / "dispatch.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def full_files():
    return {
        "raw/correctness--edges.json": [finding("1"), finding("2")],
        "raw/correctness--writes.json": [finding("3")],
        "tables/correctness--writes.md": WRITES_HEADER + "| draft to void | sent.py:9 | no [#0] |\n"
                                         "| draft to paid | paid.py:2 | yes, same cleanup |\n",
        "raw/correctness--times.json": [finding("4"), finding("5")],
        "tables/correctness--times.md": BOUNDARY_HEADER + "| entry | null | nothing [#1] |\n| exit | value | none [#0, #1] |\n",
    }


def run(path, *extra):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--run-dir", str(path), "--dimensions-dir", str(path / "dimensions"), *extra],
        capture_output=True, text=True, check=False)
    return result.returncode, json.loads(result.stdout)


def read(path, relative):
    return json.loads((path / relative).read_text(encoding="utf-8"))


def test_findings_are_concatenated_in_focus_list_order(tmp_path):
    path = setup(tmp_path, full_files())

    code, out = run(path)

    assert code == 0 and out["ok"] is True
    combined = read(path, "raw/correctness.json")
    assert [item["line"] for item in combined] == ["1", "2", "3", "4", "5"]
    assert out["agents"]["correctness"]["focuses"] == {"edges": 2, "writes": 1, "times": 2}
    assert read(path, "focus-map.json") == {"correctness#0": "edges", "correctness#1": "edges",
                                            "correctness#2": "writes", "correctness#3": "times",
                                            "correctness#4": "times"}


def test_table_citations_are_shifted_to_the_combined_indices(tmp_path):
    path = setup(tmp_path, full_files())

    run(path)

    text = (path / "tables" / "correctness.md").read_text(encoding="utf-8")
    assert "| draft to void | sent.py:9 | no [#2] |" in text
    assert "| entry | null | nothing [#4] |" in text
    assert "| exit | value | none [#3, #4] |" in text
    assert "yes, same cleanup" in text


def test_citations_in_a_backticked_cell_shift_but_reasons_that_mention_a_number_do_not(tmp_path):
    files = full_files()
    files["tables/correctness--times.md"] = (BOUNDARY_HEADER + "| entry | null | `nothing [#1]` |\n"
                                             "| exit | value | handled: see ticket #7 |\n")
    path = setup(tmp_path, files)

    run(path)

    text = (path / "tables" / "correctness.md").read_text(encoding="utf-8")
    assert "| entry | null | `nothing [#4]` |" in text
    assert "handled: see ticket #7" in text


def test_a_focus_with_no_findings_adds_no_offset_and_a_table_of_ok_rows_passes(tmp_path):
    files = full_files()
    files["raw/correctness--edges.json"] = []
    files["tables/correctness--writes.md"] = WRITES_HEADER + "| draft to paid | none: grep `status =` | yes |\n"
    files["raw/correctness--writes.json"] = [finding("3")]
    path = setup(tmp_path, files)

    code, out = run(path)

    assert code == 0
    assert [item["line"] for item in read(path, "raw/correctness.json")] == ["3", "4", "5"]
    assert "| entry | null | nothing [#2] |" in (path / "tables" / "correctness.md").read_text(encoding="utf-8")


def test_a_focus_that_finds_nothing_and_owns_no_rows_still_combines(tmp_path):
    files = {name: [] for name in ("raw/correctness--edges.json", "raw/correctness--writes.json",
                                   "raw/correctness--times.json")}
    files["tables/correctness--writes.md"] = WRITES_HEADER + "\nno rows: the diff writes no state\n"
    files["tables/correctness--times.md"] = BOUNDARY_HEADER + "| entry | null | guarded at app.py:3 |\n"
    path = setup(tmp_path, files)

    code, out = run(path)

    assert code == 0
    assert read(path, "raw/correctness.json") == []
    assert "writes: no rows: the diff writes no state" in (path / "tables" / "correctness.md").read_text("utf-8")


def test_tables_with_the_same_header_merge_into_one_table(tmp_path):
    files = full_files()
    files["tables/correctness--edges.md"] = BOUNDARY_HEADER + "| helper | None | nothing [#0] |\n"
    path = setup(tmp_path, files)
    dims = path / "dimensions" / "correctness.md"
    dims.write_text(dims.read_text(encoding="utf-8").replace("- `edges`:", "- `edges` [table: boundary table]:"),
                    encoding="utf-8")

    code, _ = run(path)

    text = (path / "tables" / "correctness.md").read_text(encoding="utf-8")
    assert code == 0
    assert text.count("| Boundary | What can arrive | What the layer above catches |") == 1
    tables = check_merge_ledger.parse_tables(text)
    boundary = [rows for header, rows in tables if header[0] == "Boundary"][0]
    assert [row[0] for row in boundary] == ["helper", "entry", "exit"]


def test_a_missing_focus_file_is_an_error_naming_the_focus_and_writes_nothing(tmp_path):
    files = full_files()
    del files["raw/correctness--times.json"]
    path = setup(tmp_path, files)

    code, out = run(path)

    assert code == 1 and out["ok"] is False
    assert out["problems"] == ["correctness focus times wrote no raw/correctness--times.json; "
                               "re-dispatch correctness focus times"]
    assert not (path / "raw" / "correctness.json").exists()
    assert (path / "raw" / "correctness--edges.json").exists()


def test_a_batch_dispatch_names_the_batch_in_the_error(tmp_path):
    files = {"raw/correctness-batch2--edges.json": []}
    path = setup(tmp_path, files, agents=[{"name": "correctness-batch2"}])

    code, out = run(path)

    assert code == 1
    assert "correctness-batch2 focus writes wrote no raw/correctness-batch2--writes.json; " \
           "re-dispatch correctness focus writes for batch 2" in out["problems"]


def test_a_table_owning_focus_without_its_table_is_an_error(tmp_path):
    files = full_files()
    del files["tables/correctness--writes.md"]
    path = setup(tmp_path, files)

    code, out = run(path)

    assert code == 1
    assert out["problems"] == ["correctness focus writes wrote no tables/correctness--writes.md; "
                               "re-dispatch correctness focus writes"]


def test_a_citation_past_the_focus_own_findings_names_the_focus_file(tmp_path):
    files = full_files()
    files["tables/correctness--writes.md"] = WRITES_HEADER + "| draft to void | sent.py:9 | no [#1] |\n"
    path = setup(tmp_path, files)

    code, out = run(path)

    assert code == 1
    assert len(out["problems"]) == 1
    assert "tables/correctness--writes.md" in out["problems"][0]
    assert "raw/correctness--writes.json has 1 findings" in out["problems"][0]
    assert out["problems"][0].endswith("re-dispatch correctness focus writes")


def test_a_malformed_raw_file_is_an_error_naming_the_focus(tmp_path):
    files = full_files()
    files["raw/correctness--edges.json"] = "{not json"
    path = setup(tmp_path, files)

    code, out = run(path)

    assert code == 1
    assert "raw/correctness--edges.json" in out["problems"][0]
    assert out["problems"][0].endswith("re-dispatch correctness focus edges")


def test_an_exempt_focus_keeps_its_findings_and_loses_its_table(tmp_path):
    files = full_files()
    del files["tables/correctness--writes.md"]
    path = setup(tmp_path, files, agents=[
        {"name": "correctness", "exempt_focuses": {"writes": "harness refused the table write twice"}}])

    code, out = run(path)

    assert code == 0
    assert [item["line"] for item in read(path, "raw/correctness.json")] == ["1", "2", "3", "4", "5"]
    assert out["agents"]["correctness"]["exempt_focuses"] == {"writes": "harness refused the table write twice"}
    text = (path / "tables" / "correctness.md").read_text(encoding="utf-8")
    assert "draft to void" not in text and "| entry | null | nothing [#4] |" in text


def test_an_exempt_focus_with_no_raw_file_contributes_nothing(tmp_path):
    files = full_files()
    del files["raw/correctness--edges.json"]
    path = setup(tmp_path, files, agents=[{"name": "correctness", "exempt_focuses": {"edges": "never returned"}}])

    code, _ = run(path)

    assert code == 0
    assert [item["line"] for item in read(path, "raw/correctness.json")] == ["3", "4", "5"]


def test_an_exempt_focus_the_dimension_does_not_list_is_an_input_error(tmp_path):
    path = setup(tmp_path, full_files(), agents=[{"name": "correctness", "exempt_focuses": {"nope": "x"}}])

    code, out = run(path)

    assert code == 2 and "nope" in out["error"]


def test_a_dimension_with_no_focus_list_is_an_input_error(tmp_path):
    path = setup(tmp_path, {}, agents=[{"name": "safety"}])

    code, out = run(path)

    assert code == 2 and "safety" in out["error"]


def test_a_whole_agent_exemption_is_skipped(tmp_path):
    path = setup(tmp_path, {}, agents=[{"name": "correctness", "exempt": "dispatch failed twice"}])

    code, out = run(path)

    assert code == 0 and out["agents"] == {}


def test_focus_files_leave_raw_so_the_ledger_check_sees_the_same_layout_as_before(tmp_path):
    path = setup(tmp_path, full_files())

    code, _ = run(path)

    assert code == 0
    assert sorted(p.name for p in (path / "raw").iterdir()) == ["correctness.json"]
    assert sorted(p.name for p in (path / "tables").iterdir()) == ["correctness.md"]
    assert (path / "focus" / "raw" / "correctness--edges.json").exists()
    agents = check_merge_ledger.load_dispatch(str(path / "dispatch.json"))
    problems, counts = check_merge_ledger.check_files(agents, str(path / "raw"), str(path / "tables"))
    # correctness is a table owner, so the ledger check reads the merged tables and every citation resolves
    assert problems == []
    assert counts["table_rows"]["correctness"] == 4


def test_a_rerun_after_archiving_gives_the_same_result_and_a_fresh_file_wins(tmp_path):
    path = setup(tmp_path, full_files())
    run(path)
    first = (path / "tables" / "correctness.md").read_text(encoding="utf-8")

    code, _ = run(path)
    assert code == 0 and (path / "tables" / "correctness.md").read_text(encoding="utf-8") == first

    (path / "raw" / "correctness--edges.json").write_text(json.dumps([finding("9")]), encoding="utf-8")
    code, _ = run(path)

    assert code == 0
    assert [item["line"] for item in read(path, "raw/correctness.json")] == ["9", "3", "4", "5"]
    assert "| entry | null | nothing [#3] |" in (path / "tables" / "correctness.md").read_text(encoding="utf-8")


def test_a_retry_after_an_error_combines_once_the_focus_is_back(tmp_path):
    files = full_files()
    del files["raw/correctness--times.json"]
    path = setup(tmp_path, files)
    assert run(path)[0] == 1

    (path / "raw" / "correctness--times.json").write_text(json.dumps([finding("4"), finding("5")]), encoding="utf-8")

    assert run(path)[0] == 0
    assert len(read(path, "raw/correctness.json")) == 5


def test_every_real_checklist_focus_list_parses_with_unique_slugs():
    focuses = combine_focus_outputs.load_focuses(str(REAL_DIMENSIONS))

    assert len(focuses) == 13
    for dimension, entries in focuses.items():
        slugs = [slug for slug, _, _ in entries]
        assert len(slugs) == len(set(slugs)), dimension


def test_prepare_extracts_diff_and_meta_and_writes_focus_prompt_files(tmp_path):
    path = setup(tmp_path, {"review-context.json": {"diff": "--- a/x.py\n+++ b/x.py\n", "seat": "reviewer", "batches": []}})

    code, out = run(path, "--prepare", "--source-root", "/tmp/src", "--risk-level", "High")

    assert code == 0 and out["ok"] is True and out["count"] == 3
    assert (path / "diff.patch").read_text(encoding="utf-8") == "--- a/x.py\n+++ b/x.py\n"
    assert read(path, "context-meta.json") == {"seat": "reviewer"}
    prompt = (path / "focus" / "prompts" / "correctness--writes.md").read_text(encoding="utf-8")
    assert "Your focus is only: `writes` [table: state-writes table]: the state-writes table." in prompt
    assert "Tables file:" in prompt and "Keep your total context under 90k tokens" in prompt


def test_combine_writes_raw_clusters_and_index(tmp_path):
    path = setup(tmp_path, full_files())

    code, _ = run(path)

    assert code == 0
    clusters = read(path, "raw-clusters.json")["clusters"]
    assert len(clusters) == 1 and clusters[0]["file"] == "app.py"
    assert len(clusters[0]["items"]) == 5
    index_text = (path / "raw-index.txt").read_text(encoding="utf-8")
    assert "correctness#0\tedges\tapp.py:1" in index_text


def test_test_dimension_must_fix_findings_are_capped_at_should_fix(tmp_path):
    (tmp_path / "raw").mkdir()
    test_raw = tmp_path / "raw" / "test-adequacy--paths.json"
    test_raw.write_text(json.dumps([finding("1", severity="Must fix", dimension="test-adequacy"),
                                    finding("2", severity="Nit", dimension="test-adequacy")]),
                        encoding="utf-8")
    prod_raw = tmp_path / "raw" / "correctness-batch2--edges.json"
    prod_raw.write_text(json.dumps([finding("3", severity="Must fix")]), encoding="utf-8")

    combine_focus_outputs._normalize_focus_files(str(tmp_path), "test-adequacy--paths", False)
    combine_focus_outputs._normalize_focus_files(str(tmp_path), "correctness-batch2--edges", False)

    assert [f["severity"] for f in json.loads(test_raw.read_text(encoding="utf-8"))] == ["Should fix", "Nit"]
    assert json.loads(prod_raw.read_text(encoding="utf-8"))[0]["severity"] == "Must fix"


def test_a_passing_check_focus_leaves_the_marker_wait_blocks_on(tmp_path):
    path = setup(tmp_path, full_files())

    code, _ = run(path, "--check-focus", "correctness--edges")

    assert code == 0
    assert (path / "focus" / "checked" / "correctness--edges").is_file()


def test_a_failing_check_focus_leaves_no_marker(tmp_path):
    path = setup(tmp_path, {"raw/correctness--edges.json": "not json"})

    code, _ = run(path, "--check-focus", "correctness--edges")

    assert code == 1
    assert not (path / "focus" / "checked" / "correctness--edges").exists()


def test_wait_returns_once_every_dispatched_focus_is_checked(tmp_path):
    path = setup(tmp_path, full_files())
    for stem in ("correctness--edges", "correctness--writes", "correctness--times"):
        assert run(path, "--check-focus", stem)[0] == 0

    code, out = run(path, "--wait", "5")

    assert code == 0 and out == {"ok": True, "done": 3, "pending": [], "waited_s": 0}


def test_wait_times_out_naming_the_focuses_still_running(tmp_path):
    path = setup(tmp_path, full_files())
    assert run(path, "--check-focus", "correctness--edges")[0] == 0

    code, out = run(path, "--wait", "0")

    assert code == 3 and out["ok"] is False
    assert out["pending"] == ["correctness--writes", "correctness--times"]


def test_wait_skips_exempt_focuses_and_counts_a_long_unchanged_raw_file_as_done(tmp_path):
    path = setup(tmp_path, {"raw/correctness--writes.json": []},
                 agents=[{"name": "correctness", "exempt_focuses": {"times": "agent failed twice"}}])
    assert run(path, "--check-focus", "correctness--edges")[0] == 1
    stems = combine_focus_outputs.expected_focus_stems(
        check_merge_ledger.load_dispatch(str(path / "dispatch.json")),
        combine_focus_outputs.load_focuses(str(path / "dimensions")),
        combine_focus_outputs.load_exempt_focuses(str(path / "dispatch.json")))

    pending = combine_focus_outputs.wait_for_focuses(str(path), stems, timeout=0, stale_after=0)

    assert stems == ["correctness--edges", "correctness--writes"]
    assert pending == ["correctness--edges"]


def test_prepare_clears_markers_from_an_earlier_fan_out(tmp_path):
    path = setup(tmp_path, {"review-context.json": {"diff": "", "batches": []}})
    combine_focus_outputs.mark_checked(str(path), "correctness--edges")

    code, _ = run(path, "--prepare")

    assert code == 0
    assert list((path / "focus" / "checked").iterdir()) == []
