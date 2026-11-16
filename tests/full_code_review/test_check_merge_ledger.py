"""Contract tests for the merge-ledger check that runs before report.json is written."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import check_merge_ledger

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "full-code-review" / "scripts" / "check_merge_ledger.py"


def finding(file="app.py", line="10", **overrides):
    item = {"severity": "Should fix", "dimension": "correctness", "file": file, "line": line,
            "issue": "issue", "recommendation": "fix", "verified": True, "assumptions": []}
    item.update(overrides)
    return item


def run_dir(tmp_path, raw, kept, entries):
    (tmp_path / "raw").mkdir()
    for name, findings in raw.items():
        (tmp_path / "raw" / ("%s.json" % name)).write_text(json.dumps(findings), encoding="utf-8")
    (tmp_path / "merged-findings.json").write_text(json.dumps(kept), encoding="utf-8")
    (tmp_path / "merge-ledger.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return tmp_path


def run(path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--raw-dir", str(path / "raw"),
         "--kept", str(path / "merged-findings.json"), "--ledger", str(path / "merge-ledger.json")],
        capture_output=True, text=True, check=False)
    return result.returncode, json.loads(result.stdout)


def test_a_complete_ledger_passes_and_prints_counts(tmp_path):
    raw = {"correctness": [finding(), finding("b.py", "5")],
           "safety": [finding(line="9-12"), finding("c.py", "1")],
           "conventions-batch1": [finding("d.py", "3"), finding("e.py", "4")]}
    kept = [finding(), finding("b.py", "5")]
    entries = [{"raw": "correctness#0", "kept": 0}, {"raw": "correctness#1", "kept": 1},
               {"raw": "safety#0", "reason": "duplicate", "kept": 0,
                "single_fix": "guard the None before the lookup"},
               {"raw": "safety#1", "reason": "refuted", "evidence": "c.py:1 already guards the None"},
               {"raw": "conventions-batch1#0", "reason": "linter-enforced"},
               {"raw": "conventions-batch1#1", "reason": "out-of-scope"}]

    code, out = run(run_dir(tmp_path, raw, {"findings": kept}, entries))

    assert code == 0
    assert out == {"ok": True, "raw": 6, "merged": 2, "covered": 2,
                   "dropped": {"duplicate": 1, "refuted": 1, "out-of-scope": 1, "linter-enforced": 1}}


def test_an_empty_specialist_result_needs_no_entries(tmp_path):
    code, out = run(run_dir(tmp_path, {"db": []}, [], []))

    assert code == 0 and out["raw"] == 0


def test_a_raw_finding_missing_from_the_ledger_fails(tmp_path):
    raw = {"correctness": [finding()], "resilience": [finding("job.py", "40")]}

    code, out = run(run_dir(tmp_path, raw, [finding()], [{"raw": "correctness#0", "kept": 0}]))

    assert code == 1
    assert out["problems"] == ["raw finding resilience#0 is missing from the ledger"]


@pytest.mark.parametrize("reason", ["low confidence", "speculative", "Duplicate", ""])
def test_a_reason_outside_the_list_fails(tmp_path, reason):
    code, out = run(run_dir(tmp_path, {"correctness": [finding()]}, [],
                            [{"raw": "correctness#0", "reason": reason}]))

    assert code == 1
    assert "drop reasons are duplicate, refuted, out-of-scope, linter-enforced" in out["problems"][0]


def test_a_duplicate_in_another_file_fails(tmp_path):
    raw = {"correctness": [finding()], "safety": [finding("other.py", "10")]}
    entries = [{"raw": "correctness#0", "kept": 0}, {"raw": "safety#0", "reason": "duplicate", "kept": 0}]

    code, out = run(run_dir(tmp_path, raw, [finding()], entries))

    assert code == 1
    assert "in another file" in out["problems"][0]


@pytest.mark.parametrize("raw_line,kept_line,ok", [
    ("10", "10", True), ("8-10", "10-12", True), ("11", "10-12", True),
    ("13", "10-12", False), ("1-9", "10", False), ("ten", "10", False)])
def test_a_duplicate_must_overlap_the_kept_line_range(tmp_path, raw_line, kept_line, ok):
    raw = {"correctness": [finding(line=kept_line)], "safety": [finding(line=raw_line)]}
    entries = [{"raw": "correctness#0", "kept": 0},
               {"raw": "safety#0", "reason": "duplicate", "kept": 0, "single_fix": "one guard covers both"}]

    code, out = run(run_dir(tmp_path, raw, [finding(line=kept_line)], entries))

    assert code == (0 if ok else 1), out


# a per-row query in a loop and an uncapped page size share a file but need two fixes
@pytest.mark.parametrize("reason", [None, "duplicate"])
@pytest.mark.parametrize("single_fix", [None, "", "  "])
def test_folding_a_different_line_into_a_kept_finding_needs_a_single_fix(tmp_path, reason, single_fix):
    raw = {"db": [finding("api/orders.py", "42-48"), finding("api/orders.py", "45")]}
    entry = {"raw": "db#1", "kept": 0}
    if reason:
        entry["reason"] = reason
    if single_fix is not None:
        entry["single_fix"] = single_fix

    code, out = run(run_dir(tmp_path, raw, [finding("api/orders.py", "42-48")], [{"raw": "db#0", "kept": 0}, entry]))

    assert code == 1
    assert out["problems"] == [
        "entry 1 (db#1) folds line 45 into kept finding 0 at line 42-48 without a single_fix naming the one "
        "change that resolves both; keep it as its own finding if it needs a fix of its own"]


def test_a_single_fix_lets_a_different_line_fold_in(tmp_path):
    raw = {"db": [finding("api/orders.py", "42-48")], "resilience": [finding("api/orders.py", "45")]}
    entries = [{"raw": "db#0", "kept": 0},
               {"raw": "resilience#0", "kept": 0, "single_fix": "batch the lookup into one query before the loop"}]

    code, out = run(run_dir(tmp_path, raw, [finding("api/orders.py", "42-48")], entries))

    assert code == 0 and out["covered"] == 2


@pytest.mark.parametrize("raw_line,kept_line", [("10", "10"), ("10", "10-10"), (" 8-9", "8-9")])
def test_the_same_line_folds_in_without_a_single_fix(tmp_path, raw_line, kept_line):
    raw = {"correctness": [finding(line=kept_line)], "safety": [finding(line=raw_line)]}
    entries = [{"raw": "correctness#0", "kept": 0}, {"raw": "safety#0", "reason": "duplicate", "kept": 0}]

    assert run(run_dir(tmp_path, raw, [finding(line=kept_line)], entries))[0] == 0


@pytest.mark.parametrize("target", [1, -1, "0", None, True])
def test_a_pointer_at_a_kept_finding_that_does_not_exist_fails(tmp_path, target):
    code, out = run(run_dir(tmp_path, {"correctness": [finding()]}, [finding()],
                            [{"raw": "correctness#0", "reason": "duplicate", "kept": target}]))

    assert code == 1
    assert "does not exist" in out["problems"][0]


@pytest.mark.parametrize("evidence", [None, "", "   "])
def test_a_refuted_finding_needs_evidence(tmp_path, evidence):
    entry = {"raw": "correctness#0", "reason": "refuted"}
    if evidence is not None:
        entry["evidence"] = evidence

    code, out = run(run_dir(tmp_path, {"correctness": [finding()]}, [], [entry]))

    assert code == 1
    assert out["problems"] == ["entry 0 (correctness#0) is refuted without evidence"]


def test_a_dropped_finding_cannot_also_point_at_a_kept_finding(tmp_path):
    code, out = run(run_dir(tmp_path, {"correctness": [finding()]}, [finding()],
                            [{"raw": "correctness#0", "reason": "out-of-scope", "kept": 0}]))

    assert code == 1
    assert "also points at a kept finding" in out["problems"][0]


def test_unknown_and_repeated_raw_ids_fail(tmp_path):
    entries = [{"raw": "correctness#0", "kept": 0}, {"raw": "correctness#0", "kept": 0},
               {"raw": "correctness#7", "kept": 0}]

    code, out = run(run_dir(tmp_path, {"correctness": [finding()]}, [finding()], entries))

    assert code == 1
    assert out["problems"] == ["entry 1 (correctness#0) accounts for a raw finding a second time",
                               "entry 2 (correctness#7) names no raw finding"]


def test_non_json_files_in_the_raw_directory_are_ignored(tmp_path):
    path = run_dir(tmp_path, {"correctness": [finding()]}, [finding()], [{"raw": "correctness#0", "kept": 0}])
    (path / "raw" / "notes.md").write_text("scratch", encoding="utf-8")

    assert run(path)[0] == 0


@pytest.mark.parametrize("break_input", ["no-raw-dir", "raw-not-a-list", "ledger-not-object", "entries-missing"])
def test_malformed_input_exits_2_with_an_error(tmp_path, break_input):
    path = run_dir(tmp_path, {"correctness": [finding()]}, [finding()], [{"raw": "correctness#0", "kept": 0}])
    if break_input == "no-raw-dir":
        (path / "raw" / "correctness.json").unlink()
        (path / "raw").rmdir()
    elif break_input == "raw-not-a-list":
        (path / "raw" / "correctness.json").write_text('"oops"', encoding="utf-8")
    elif break_input == "ledger-not-object":
        (path / "merge-ledger.json").write_text("[]", encoding="utf-8")
    else:
        (path / "merge-ledger.json").write_text("{}", encoding="utf-8")

    code, out = run(path)

    assert code == 2
    assert set(out) == {"error"}


def test_drop_reasons_are_the_fixed_list():
    assert check_merge_ledger.DROP_REASONS == ("duplicate", "refuted", "out-of-scope", "linter-enforced")


def files_dir(tmp_path, agents, raw, tables):
    (tmp_path / "raw").mkdir()
    (tmp_path / "tables").mkdir()
    for name, findings in raw.items():
        (tmp_path / "raw" / ("%s.json" % name)).write_text(json.dumps(findings), encoding="utf-8")
    for name, text in tables.items():
        (tmp_path / "tables" / ("%s.md" % name)).write_text(text, encoding="utf-8")
    (tmp_path / "dispatch.json").write_text(json.dumps({"agents": agents}), encoding="utf-8")
    return tmp_path


def run_files(path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--raw-dir", str(path / "raw"),
         "--dispatch", str(path / "dispatch.json"), "--tables-dir", str(path / "tables")],
        capture_output=True, text=True, check=False)
    return result.returncode, json.loads(result.stdout)


TABLE = "| Changed symbol or new value | Caller or reader (file:line) | What it assumes | Still holds? |\n" \
        "|---|---|---|---|\n" \
        "| `charge()` | `jobs.py:12` | returns a list | yes, jobs.py:14 iterates the list |\n" \
        "| `charge()` | `api.py:40` | never None | no [#0] |\n"


def complete_files(tmp_path):
    agents = [{"name": "cross-repo"}, {"name": "db"}, {"name": "correctness-batch1"}, {"name": "correctness-batch2"}]
    raw = {"cross-repo": [finding()], "db": [], "correctness-batch1": [finding()], "correctness-batch2": [finding()]}
    tables = {"cross-repo": TABLE, "correctness-batch1": TABLE, "correctness-batch2": "No boundaries: the diff only renames a test.\n"}
    return files_dir(tmp_path, agents, raw, tables)


def test_every_dispatched_agent_with_its_files_passes_and_counts_table_rows(tmp_path):
    code, out = run_files(complete_files(tmp_path))

    assert code == 0, out
    assert out == {"ok": True, "agents": 4, "exempt": [],
                   "table_rows": {"cross-repo": 2, "correctness-batch1": 2, "correctness-batch2": 0}}


def test_a_missing_table_names_the_agent_to_redispatch(tmp_path):
    path = complete_files(tmp_path)
    (path / "tables" / "correctness-batch2.md").unlink()

    code, out = run_files(path)

    assert code == 1
    assert out["problems"] == ["correctness-batch2 wrote no tables/correctness-batch2.md; "
                               "re-dispatch correctness for batch 2"]


@pytest.mark.parametrize("text", ["", "  \n\n"])
def test_an_empty_table_fails(tmp_path, text):
    path = complete_files(tmp_path)
    (path / "tables" / "cross-repo.md").write_text(text, encoding="utf-8")

    code, out = run_files(path)

    assert code == 1
    assert out["problems"] == ["tables/cross-repo.md is empty; re-dispatch cross-repo"]


STATE_WRITES = "| Record and transition | Existing writer (file:line), same source or same target | Side effect on that path " \
               "| New code does it? |\n|---|---|---|---|\n"
JOBS = "| Job or entry point | Checked at enqueue or request time | Re-checked when the run starts? " \
       "| Two at once? Guard (file:line) | Caller-supplied size and its upper bound |\n|---|---|---|---|---|\n"
ROW = "| invoice: `draft` to `void` | `billing.py:30` | emits `invoice.voided` | %s |\n"
WHERE = "tables/correctness.md, Record and transition table, row 1 (invoice: `draft` to `void`)"


def rows_problems(tmp_path, rows, raw=None, header=STATE_WRITES):
    path = files_dir(tmp_path, [{"name": "correctness"}],
                     {"correctness": raw if raw is not None else [finding(), finding("b.py", "5")]},
                     {"correctness": "Intro line.\n\n" + header + "".join(rows)})
    code, out = run_files(path)
    return code, out.get("problems", [])


@pytest.mark.parametrize("answer", [
    "no [#1]", "no, the event is never emitted [#0, #1]", "`no` `[#0]`", "yes", "yes, at `billing.py:44`",
    "no, because the MR says the event moves to the nightly sync", "n/a: no webhook on this path",
    "ok: the stored key is checked first"])
def test_a_problem_cell_with_its_citation_or_a_cell_with_no_problem_passes(tmp_path, answer):
    assert rows_problems(tmp_path, [ROW % answer]) == (0, [])


@pytest.mark.parametrize("answer", [
    "no", "No - the side table row stays", "not cleared", "never", "none", "missing", "unknown", "could not check"])
def test_a_negative_verdict_cell_without_a_citation_fails_naming_table_row_and_column(tmp_path, answer):
    code, problems = rows_problems(tmp_path, [ROW % answer])

    assert code == 1
    assert problems == ["%s, New code does it? reads %r but cites no finding; add [#<n>] after it; "
                        "re-dispatch correctness" % (WHERE, answer)]


# the row-level citation let one finding stand in for two problems in different cells
def test_two_problem_cells_citing_one_finding_fail(tmp_path):
    row = "| `nightly_sync` | flag on | no [#0] | no guard [#0] | `limit`: unbounded [#1] |\n"

    code, problems = rows_problems(tmp_path, [row], header=JOBS)

    assert code == 1
    assert problems == ["tables/correctness.md, Job or entry point table, row 1 (`nightly_sync`) cites #0 in "
                        "Re-checked when the run starts? and Two at once? Guard (file:line); file each problem as "
                        "its own finding, or give #0 a single_fix naming the one change that fixes every cell "
                        "citing it; re-dispatch correctness"]


def test_a_finding_with_a_single_fix_may_cover_two_problem_cells(tmp_path):
    row = "| `nightly_sync` | flag on | no [#0] | no guard [#0] | `limit` capped at 500 at `api.py:9` |\n"
    raw = [finding(single_fix="moving the flag check into the locked run fixes both")]

    assert rows_problems(tmp_path, [row], raw=raw, header=JOBS) == (0, [])


def test_one_finding_may_be_cited_in_different_rows(tmp_path):
    rows = [ROW % "no [#0]", ROW.replace("emits", "clears") % "no [#0]"]

    assert rows_problems(tmp_path, rows) == (0, [])


@pytest.mark.parametrize("row, column", [
    ("| invoice: `draft` to `void` | `billing.py:30` |  | yes |\n", "Side effect on that path"),
    ("| invoice: `draft` to `void` | `billing.py:30` | emits `invoice.voided` |\n", "New code does it?")])
def test_an_empty_cell_fails(tmp_path, row, column):
    code, problems = rows_problems(tmp_path, [row])

    assert code == 1
    assert problems == ["%s, %s is empty; write the answer, and [#<n>] after it if it is a problem; "
                        "re-dispatch correctness" % (WHERE, column)]


@pytest.mark.parametrize("answer", [
    "ok: outside this dimension", "n/a: belongs to another dimension", "n/a: covered by `safety`",
    "yes, covered by resilience", "n/a: not this pass", "no, because it is handled by the safety dimension",
    "OK - left to the other specialist", "n/a: out of my scope"])
def test_a_cell_that_defers_to_another_dimension_fails(tmp_path, answer):
    code, problems = rows_problems(tmp_path, [ROW % answer])

    assert code == 1
    assert problems == ["%s, New code does it? defers to another dimension (%r); file the finding here and cite it, "
                        "the merge drops duplicates; re-dispatch correctness" % (WHERE, answer)]


@pytest.mark.parametrize("answer", [
    "yes, covered by `test_void_emits_event`", "ok: covered by tests in `test_billing.py`",
    "yes, checked by the caller at `api.py:9`", "n/a: nothing left to do on this path",
    "yes, the invoice belongs to the same account", "ok: defers to the repo's own writer at `billing.py:30`"])
def test_a_genuine_reason_that_names_coverage_or_ownership_passes(tmp_path, answer):
    assert rows_problems(tmp_path, [ROW % answer]) == (0, [])


def test_a_descriptive_cell_is_not_read_as_a_verdict(tmp_path):
    row = "| invoice: `draft` to `void` | none found (searched `status = 'void'`) | missing totals row " \
          "is rebuilt; covered by the other writer | yes |\n"

    assert rows_problems(tmp_path, [row]) == (0, [])


def test_a_dangling_finding_index_fails(tmp_path):
    rows = [ROW % "no [#0]", ROW.replace("emits", "clears") % "no [#1, #4]"]

    code, problems = rows_problems(tmp_path, rows)

    assert code == 1
    assert problems == ["tables/correctness.md, Record and transition table, row 2 (invoice: `draft` to `void`) "
                        "cites #4, but raw/correctness.json has 2 findings; re-dispatch correctness"]


def test_any_index_dangles_when_the_raw_file_is_empty(tmp_path):
    code, problems = rows_problems(tmp_path, [ROW % "no [#0]"], raw=[])

    assert code == 1 and "cites #0, but raw/correctness.json has 0 findings" in problems[0]


@pytest.mark.parametrize("column, answer", [
    ("Verdict", "misleading"), ("Killing test", "none"), ("Test that pins it", "none"), ("Still holds?", "No"),
    ("Still holds?", "not checked"), ("Pass, violation or n/a (file:line)", "violation at `api.py:9`"),
    ("What the layer above catches", "nothing"), ("What collides", "two stores share a number, unhandled"),
    ("Two at once? Guard (file:line)", "no guard"), ("Every waiter finishes?", "no: the poller spins"),
    ("Caller-supplied size and its upper bound", "`page_size`: unbounded"),
    ("Caller-supplied size and its upper bound", "`limit`, no upper bound")])
def test_each_verdict_column_marks_a_problem_answer(tmp_path, column, answer):
    header = "| Item | %s |\n|---|---|\n" % column

    code, problems = rows_problems(tmp_path, ["| `refund()` | %s |\n" % answer], header=header)

    assert code == 1 and "%s reads %r but cites no finding" % (column, answer) in problems[0]


@pytest.mark.parametrize("column, answer", [
    ("What collides", "none"), ("What splits", "nothing"), ("Caller-supplied size and its upper bound", "none"),
    ("Two at once? Guard (file:line)", "lock at `jobs.py:20`"), ("Test that pins it", "n/a: wording only")])
def test_a_negative_word_that_means_no_problem_passes_in_its_column(tmp_path, column, answer):
    header = "| Item | %s |\n|---|---|\n" % column

    assert rows_problems(tmp_path, ["| `refund()` | %s |\n" % answer], header=header) == (0, [])


def test_an_escaped_pipe_stays_inside_its_cell():
    text = "| Rule | Applies to | Pass, violation or n/a (file:line) |\n|---|---|---|\n" \
           "| use `a \\| b` unions | `types.py` | pass `types.py:3` |\n"

    assert check_merge_ledger.check_table_rows("conventions", text, []) == []


def test_a_missing_raw_file_fails_even_for_a_dimension_without_a_table(tmp_path):
    path = complete_files(tmp_path)
    (path / "raw" / "db.json").unlink()

    code, out = run_files(path)

    assert code == 1
    assert out["problems"] == ["db wrote no raw/db.json; re-dispatch db"]


def test_a_raw_file_that_is_not_a_findings_array_fails(tmp_path):
    path = complete_files(tmp_path)
    (path / "raw" / "db.json").write_text("Found 2 issues, see above.", encoding="utf-8")

    code, out = run_files(path)

    assert code == 1
    assert out["problems"][0].startswith("could not read raw/db.json")
    assert out["problems"][0].endswith("re-dispatch db")


def test_an_agent_recorded_as_exempt_owes_no_files(tmp_path):
    path = complete_files(tmp_path)
    (path / "raw" / "cross-repo.json").unlink()
    (path / "tables" / "cross-repo.md").unlink()
    agents = json.loads((path / "dispatch.json").read_text(encoding="utf-8"))["agents"]
    agents[0]["exempt"] = "failed after its retry; in run.dimensions_failed"
    (path / "dispatch.json").write_text(json.dumps({"agents": agents}), encoding="utf-8")

    code, out = run_files(path)

    assert code == 0, out
    assert out["exempt"] == ["cross-repo"]


def test_a_dimension_that_was_not_dispatched_owes_nothing(tmp_path):
    path = files_dir(tmp_path, [{"name": "db"}], {"db": []}, {})

    assert run_files(path)[0] == 0


@pytest.mark.parametrize("agents", [
    [{"name": "prefix:db"}], [{"name": "risk"}], [{"name": "db", "exempt": ""}], [{"name": 3}], ["db"]])
def test_a_malformed_dispatch_manifest_exits_2(tmp_path, agents):
    code, out = run_files(files_dir(tmp_path, agents, {"db": []}, {}))

    assert code == 2
    assert set(out) == {"error"}


def test_both_checks_run_together_and_report_every_problem(tmp_path):
    path = files_dir(tmp_path, [{"name": "correctness"}], {"correctness": [finding()]}, {})
    (path / "merged-findings.json").write_text("[]", encoding="utf-8")
    (path / "merge-ledger.json").write_text('{"entries": []}', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--raw-dir", str(path / "raw"),
         "--dispatch", str(path / "dispatch.json"), "--tables-dir", str(path / "tables"),
         "--kept", str(path / "merged-findings.json"), "--ledger", str(path / "merge-ledger.json")],
        capture_output=True, text=True, check=False)

    assert result.returncode == 1
    assert json.loads(result.stdout)["problems"] == [
        "correctness wrote no tables/correctness.md; re-dispatch correctness",
        "raw finding correctness#0 is missing from the ledger"]


@pytest.mark.parametrize("flags", [[], ["--kept", "k.json"], ["--dispatch", "d.json"]])
def test_each_check_needs_both_of_its_flags(tmp_path, flags):
    result = subprocess.run([sys.executable, str(SCRIPT), "--raw-dir", str(tmp_path)] + flags,
                            capture_output=True, text=True, check=False)

    assert result.returncode == 2
    assert set(json.loads(result.stdout)) == {"error"}


def diff(path, old="    return run()", new="    return run(lock)"):
    return "```diff\n--- a/%s\n+++ b/%s\n@@ -10,3 +10,3 @@\n def go():\n-%s\n+%s\n```" % (path, path, old, new)


# a scheduler fix that also patches the worker leaves the worker's defect with no anchor of its own
def test_a_recommendation_that_also_edits_another_file_fails(tmp_path):
    path = complete_files(tmp_path)
    folded = finding("app/scheduler.py", "40", recommendation="Lock per store.\n\n%s\n\nand in the worker:\n\n%s" % (
        diff("app/scheduler.py"), diff("app/worker.py")))
    (path / "raw" / "db.json").write_text(json.dumps([finding(), folded]), encoding="utf-8")

    code, out = run_files(path)

    assert code == 1
    assert out["problems"] == [
        "raw/db.json finding #1 (app/scheduler.py) has a recommendation that also edits app/worker.py; file each "
        "other defect as its own finding anchored where its change goes, or add a single_fix naming why the "
        "edits are one change; re-dispatch db"]


@pytest.mark.parametrize("recommendation", [
    diff("app/scheduler.py"),
    diff("./app/scheduler.py"),
    "Lock per store:\n\n" + diff("app/scheduler.py") + "\n\nsee app/worker.py:12 for the caller",
    # a plain fence and a removed SQL comment are not diff headers
    "```python\n--- a/app/worker.py\n+++ b/app/worker.py\n```",
    "```diff\n--- a/app/scheduler.py\n+++ b/app/scheduler.py\n@@ -1,2 +1,2 @@\n--- a/app/worker.py\n+++++ b/x\n```",
    "```diff\n--- /dev/null\n+++ b/app/scheduler.py\n```",
    "no code change",
    None,
])
def test_a_recommendation_that_edits_only_its_own_file_passes(recommendation):
    assert check_merge_ledger.check_raw_findings(
        "db", [finding("app/scheduler.py", "40", recommendation=recommendation)]) == []


def test_a_single_fix_lets_a_recommendation_edit_another_file():
    rename = finding("app/scheduler.py", "40", recommendation=diff("app/scheduler.py") + "\n" + diff("app/cli.py"),
                     single_fix="the renamed argument must change at its one caller")

    assert check_merge_ledger.check_raw_findings("db", [rename]) == []
    assert check_merge_ledger.check_raw_findings("db", [dict(rename, single_fix=" ")]) != []


def test_diff_files_lists_each_edited_file_once_in_order():
    text = "\n".join([diff("b.py"), diff("a.py"), "~~~~diff\n--- a/b.py\n+++ b/b.py\n~~~~", "```diff\n+++ b/c.py\n```"])

    assert check_merge_ledger.diff_files(text) == ["b.py", "a.py"]
