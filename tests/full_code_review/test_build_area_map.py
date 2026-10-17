"""Contracts for coupled review areas and the command-line area-map writer."""

import importlib
import inspect
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "full-code-review" / "scripts"


def area_map_module():
    return importlib.import_module("build_area_map")


def put(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return name


def test_imports_resolve_package_initializers_and_modules(tmp_path):
    names = [
        put(tmp_path, "skills/review/scripts/prepare_diff.py", "import forge\nfrom forge import github\n"),
        put(tmp_path, "skills/review/scripts/forge/__init__.py", "from .github import Client\n"),
        put(tmp_path, "skills/review/scripts/forge/github.py", "class Client: pass\n"),
        put(tmp_path, "elsewhere/github.py", "class Other: pass\n"),
    ]
    graph = area_map_module().build_coupling_graph(names, str(tmp_path), "")
    assert graph[names[0]] == {names[1], names[2]}
    assert graph[names[1]] == {names[0], names[2]}
    assert graph[names[3]] == set()


def test_relative_package_imports_reach_changed_siblings(tmp_path):
    names = [
        put(tmp_path, "scripts/forge/__init__.py", "from . import github\n"),
        put(tmp_path, "scripts/forge/github.py", "from .. import prepare_diff\n"),
        put(tmp_path, "scripts/prepare_diff.py", "pass\n"),
    ]
    graph = area_map_module().build_coupling_graph(names, str(tmp_path), "")
    assert graph[names[0]] == {names[1]}
    assert graph[names[1]] == {names[0], names[2]}

def test_empty_module_relative_imports_at_the_repo_root_do_not_crash():
    files = ["a.py", "d/b.py", "x.py"]
    diff = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n"
            "@@ -0,0 +1 @@\n+from . import x\n"
            "diff --git a/d/b.py b/d/b.py\n--- a/d/b.py\n+++ b/d/b.py\n"
            "@@ -0,0 +1 @@\n+from .. import x\n")
    graph = area_map_module().build_coupling_graph(files, None, diff)
    assert graph["a.py"] == {"x.py"}
    assert graph["d/b.py"] == {"x.py"}


def test_backslash_in_a_changed_filename_is_accepted(tmp_path):
    names = [put(tmp_path, "we\\ird.py", "pass\n"), put(tmp_path, "other.py", "pass\n")]
    graph = area_map_module().build_coupling_graph(names, str(tmp_path), "")
    assert set(graph) == set(names)


def test_dunder_module_stems_do_not_couple_every_constructor(tmp_path):
    names = [
        put(tmp_path, "pkg/__init__.py", "pass\n"),
        put(tmp_path, "pkg/widget.py", "class Widget:\n    def __init__(self): pass\n"),
    ]
    graph = area_map_module().build_coupling_graph(names, str(tmp_path), "")
    assert graph[names[0]] == set()
    assert graph[names[1]] == set()


def test_imports_are_taken_from_added_and_context_diff_lines_without_source():
    files = ["scripts/runner.py", "scripts/forge/__init__.py", "scripts/forge/github.py"]
    diff = ("diff --git a/scripts/runner.py b/scripts/runner.py\n"
            "--- a/scripts/runner.py\n+++ b/scripts/runner.py\n"
            "@@ -1,2 +1,3 @@\n-from obsolete import thing\n"
            " import forge\n+from forge.github import Client\n+print('from ignored import thing')\n")
    graph = area_map_module().build_coupling_graph(files, None, diff)
    assert graph[files[0]] == {files[1], files[2]}


def test_diff_parser_accepts_c_quoted_paths_and_ignores_removed_imports():
    files = ["scripts/my runner.py", "scripts/helper.py", "scripts/obsolete.py"]
    diff = ('diff --git "a/scripts/my runner.py" "b/scripts/my runner.py"\n'
            '--- "a/scripts/my runner.py"\n+++ "b/scripts/my runner.py"\n'
            '@@ -1,2 +1,2 @@\n-import obsolete\n+import helper\n')
    graph = area_map_module().build_coupling_graph(files, None, diff)
    assert graph[files[0]] == {files[1]}
    assert graph[files[2]] == set()


def test_references_assets_and_shared_triage_headers_form_edges(tmp_path):
    names = [
        put(tmp_path, "skills/review/SKILL.md", "Run scripts/prepare_diff.py; see references/posting.md\n"),
        put(tmp_path, "skills/review/references/posting.md", "Use the posting guide\n"),
        put(tmp_path, "skills/review/scripts/prepare_diff.py", "print('ready')\n"),
        put(tmp_path, "skills/review/scripts/render_report.py", "TEMPLATE = 'assets/report.html'\n"),
        put(tmp_path, "skills/review/assets/report.html", "<h1>quirk-review handoff</h1>\n"),
        put(tmp_path, "skills/review/scripts/validate_triage.py", "HEADER = 'quirk-review handoff'\n"),
    ]
    graph = area_map_module().build_coupling_graph(names, str(tmp_path), "")
    assert {names[1], names[2]} <= graph[names[0]]
    assert names[4] in graph[names[3]]
    assert names[5] in graph[names[4]]
    assert names[2] not in graph[names[3]]


def test_tests_pair_with_subject_not_other_same_name(tmp_path):
    files = ["scripts/reader.py", "tests/test_reader.py", "tests/other/test_reader.py",
             "other/reader.py"]
    graph = area_map_module().build_coupling_graph(files, str(tmp_path), "")
    assert graph[files[0]] == {files[1]}
    assert graph[files[3]] == {files[2]}


@pytest.mark.parametrize("subject, test", [
    ("web/foo.ts", "web/foo.test.ts"),
    ("web/foo.ts", "web/foo.spec.ts"),
    ("pkg/baz.py", "pkg/baz_test.py"),
    ("cmd/a.go", "cmd/a_test.go"),
    ("src/Foo.java", "src/FooTest.java"),
])
def test_non_python_and_suffix_style_tests_pair_with_their_subject(tmp_path, subject, test):
    module = area_map_module()
    graph = module.build_coupling_graph([subject, test], str(tmp_path), "")
    assert graph[subject] == {test}
    area = module.build_area_map({"changed_files": [subject, test], "diff": ""}, str(tmp_path))["areas"][0]
    assert area["test_files"] == [test]


def test_partition_prioritizes_non_test_boundaries_before_tests():
    files = ["tests/test_a.py", "scripts/a.py", "scripts/b.py", "tests/test_b.py"]
    edges = {p: set() for p in files}
    for a, b in ((files[0], files[1]), (files[1], files[2]), (files[2], files[3])):
        edges[a].add(b)
        edges[b].add(a)
    areas = area_map_module().partition_areas(files, edges, {p: 10 for p in files}, max_files=2)
    assert [set(a["files"]) for a in areas] == [{files[1], files[2]}, {files[0], files[3]}]
    assert areas[0]["coupled_edges"] == [[files[1], files[2]]]


def test_partition_bounds_oversized_file_and_attaches_directory_siblings():
    files = ["scripts/a.py", "scripts/b.py", "other/c.py"]
    graph = {p: set() for p in files}
    areas = area_map_module().partition_areas(files, graph, {files[0]: 11, files[1]: 2,
                                                               files[2]: 1}, max_lines=10, max_files=2)
    assert [a["files"] for a in areas] == [[files[0]], [files[1]], [files[2]]]
    assert areas[0]["lines"] == 11
    areas = area_map_module().partition_areas(files, graph, {p: 1 for p in files}, max_files=2)
    assert [a["files"] for a in areas] == [[files[0], files[1]], [files[2]]]


def test_area_map_uses_source_line_weights_and_boundaries_in_questions(tmp_path):
    files = [
        put(tmp_path, "scripts/prepare_diff.py", "from forge import load\nline = 1\nline = 2\n"),
        put(tmp_path, "scripts/forge/__init__.py", "def load(): pass\n"),
        put(tmp_path, "tests/test_prepare_diff.py", "assert True\n"),
    ]
    result = area_map_module().build_area_map({"changed_files": files, "diff": ""}, str(tmp_path))
    assert result["schema_version"] == 1
    assert len(result["areas"]) == 1
    area = result["areas"][0]
    assert area["files"] == files
    assert area["test_files"] == [files[2]]
    assert area["lines"] == 5
    assert area["id"] == "A1"
    assert area["status"] == "pending" and area["degraded_reason"] is None
    assert 2 <= len(area["questions"]) <= 5
    assert any("prepare_diff.py" in q and "__init__.py" in q for q in area["questions"])
    assert any("test_prepare_diff.py" in q for q in area["questions"])


def test_deleted_files_use_hunk_weight_and_no_source_has_minimum_one(tmp_path):
    files = ["deleted.py", "empty.py"]
    diff = ("diff --git a/deleted.py b/deleted.py\n"
            "--- a/deleted.py\n+++ /dev/null\n@@ -1,3 +0,0 @@\n-one\n-two\n-three\n")
    result = area_map_module().build_area_map({"changed_files": files, "diff": diff}, str(tmp_path),
                                               max_files=1)
    assert [a["lines"] for a in result["areas"]] == [3, 1]


def test_risk_level_and_caveats_produce_targeted_questions(tmp_path):
    file = put(tmp_path, "scripts/parse.py", "def parse(data): return data\n")
    result = area_map_module().build_area_map(
        {"changed_files": [file], "diff": ""}, str(tmp_path),
        risk={"level": "High", "verbatim_md": "Path traversal in uploaded names",
              "caveats": ["The path may be C-quoted"]})
    questions = result["areas"][0]["questions"]
    assert 2 <= len(questions) <= 5
    assert any("High" in q and "Path traversal" in q and "parse.py" in q for q in questions)
    assert any("C-quoted" in q and "parse.py" in q for q in questions)


def test_report_shaped_caveats_seed_a_question(tmp_path):
    file = put(tmp_path, "scripts/parse.py", "def parse(data): return data\n")
    result = area_map_module().build_area_map(
        {"changed_files": [file], "diff": ""}, str(tmp_path),
        risk={"caveats": [{"title": "Quoting", "body_md": "The path may be C-quoted"}]})
    assert any("C-quoted" in q and "parse.py" in q for q in result["areas"][0]["questions"])


def test_whole_file_weight_is_the_fallback_when_no_diff_section_exists(tmp_path):
    html = "<style>\n" + "p { color: red; }\n" * 100 + "</style>\n"
    files = [put(tmp_path, "page.html", html),
             put(tmp_path, "reader.py", "TEMPLATE = 'page.html'\n")]
    result = area_map_module().build_area_map(
        {"changed_files": files, "diff": ""}, str(tmp_path), max_lines=50)
    page = next(area for area in result["areas"] if "page.html" in area["files"])
    assert page["files"] == ["page.html"]
    assert page["lines"] == 102


def test_area_map_is_deterministic_and_covers_every_file_once():
    files = ["scripts/b.py", "scripts/a.py", "tests/test_a.py", "docs/unrelated.md"]
    context = {"changed_files": files, "diff": ""}
    module = area_map_module()
    first = module.build_area_map(context, max_files=2)
    assert first == module.build_area_map(context, max_files=2)
    assert sorted(f for area in first["areas"] for f in area["files"]) == sorted(files)
    assert [area["id"] for area in first["areas"]] == ["A1", "A2", "A3"]


def test_cli_writes_with_jsonio_and_prints_matching_summary(tmp_path, capsys):
    module = area_map_module()
    path = tmp_path / "context.json"
    path.write_text(json.dumps({"changed_files": ["scripts/tool.py"], "diff": ""}))
    out = tmp_path / "nested" / "area-map.json"
    assert module.main(["--context", str(path), "--out", str(out)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert json.loads(out.read_text()) == result
    assert result["areas"][0]["lines"] == 1


@pytest.mark.parametrize("arguments", [
    ["--context", "missing.json", "--out", "map.json"],
    ["--context", "context.json", "--risk", "missing.json", "--out", "map.json"],
    ["--context", "context.json", "--max-files", "0", "--out", "map.json"],
    ["--context", "context.json", "--max-lines", "-1", "--out", "map.json"],
    ["--context", "context.json", "--max-files", "wat", "--out", "map.json"],
])
def test_cli_invalid_input_exits_two_with_json_error(tmp_path, arguments):
    (tmp_path / "context.json").write_text('{"changed_files": [], "diff": ""}')
    result = subprocess.run([sys.executable, str(SCRIPTS / "build_area_map.py"), *arguments],
                            cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert isinstance(json.loads(result.stdout)["error"], str)


@pytest.mark.parametrize("context", ["not json", "{}", '{"changed_files": "wrong", "diff": ""}',
                                      '{"changed_files": ["../escape.py"], "diff": ""}'])
def test_cli_rejects_invalid_context(tmp_path, context):
    file = tmp_path / "context.json"
    file.write_text(context)
    result = subprocess.run([sys.executable, str(SCRIPTS / "build_area_map.py"),
                             "--context", str(file), "--out", str(tmp_path / "output.json")],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "error" in json.loads(result.stdout)


def test_changed_symlinked_directory_falls_back_to_the_diff_section(tmp_path):
    (tmp_path / "real_dir").mkdir()
    (tmp_path / "linkdir").symlink_to("real_dir", target_is_directory=True)
    files = [put(tmp_path, "ok.py", "x = 1\n"), "linkdir"]
    diff = "diff --git a/linkdir b/linkdir\n--- a/linkdir\n+++ b/linkdir\n@@ -1 +1 @@\n-a\n+b\n"
    result = area_map_module().build_area_map({"changed_files": files, "diff": diff}, str(tmp_path))
    assert sorted(f for area in result["areas"] for f in area["files"]) == sorted(files)


def test_changed_symlink_to_a_file_outside_the_root_is_not_read(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "secret.py"
    outside.write_text("import os\n" * 50)
    (root / "link.py").symlink_to(outside)
    module = area_map_module()
    texts, weights = module._contents(["link.py"], str(root), "")
    assert texts["link.py"] == "" and weights["link.py"] == 1


def test_questions_do_not_seed_filename_specific_prompts(tmp_path):
    files = [put(tmp_path, "assets/report.html", "<h1>quirk-review handoff</h1>\n"),
             put(tmp_path, "scripts/validate_triage.py", "HEADER = 'quirk-review handoff'\n")]
    result = area_map_module().build_area_map({"changed_files": files, "diff": ""}, str(tmp_path))
    questions = " ".join(q for area in result["areas"] for q in area["questions"])
    assert "delimiters" not in questions and "export headers" not in questions


def test_risk_question_states_the_level_once(tmp_path):
    file = put(tmp_path, "scripts/parse.py", "def parse(data): return data\n")
    result = area_map_module().build_area_map(
        {"changed_files": [file], "diff": ""}, str(tmp_path),
        risk={"level": "Medium", "verbatim_md": "Thin coverage"})
    question = next(q for q in result["areas"][0]["questions"] if "Thin coverage" in q)
    assert question.count("Medium") == 1


def modify_diff(path, old_lines, new_lines, header="@@ -1,3 +1,3 @@"):
    body = "".join("-%s\n" % line for line in old_lines) + "".join("+%s\n" % line for line in new_lines)
    return "diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n%s\n %s\n%s" % (
        path, path, path, path, header, "ctx", body)


def build(files, diff, root=None, **kwargs):
    return area_map_module().build_area_map(
        {"changed_files": files, "diff": diff}, str(root) if root else None, **kwargs)


def test_modified_file_weighs_changed_lines_not_file_length(tmp_path):
    name = put(tmp_path, "scripts/big.py", "x = 1\n" * 500)
    diff = modify_diff(name, ["x = 1"], ["x = 2"])
    area = build([name], diff, tmp_path)["areas"][0]
    assert area["lines"] == 2


def test_new_file_counts_in_full(tmp_path):
    name = put(tmp_path, "scripts/new.py", "x = 1\n" * 40)
    diff = ("diff --git a/%s b/%s\nnew file mode 100644\n--- /dev/null\n+++ b/%s\n"
            "@@ -0,0 +1,40 @@\n" % (name, name, name)) + "+x = 1\n" * 40
    assert build([name], diff, tmp_path)["areas"][0]["lines"] == 40


def test_file_header_lines_are_not_counted_as_changes():
    diff = modify_diff("a.py", [], ["new"])
    assert build(["a.py"], diff)["areas"][0]["lines"] == 1


def test_hunkless_section_weighs_one_even_when_source_file_is_long(tmp_path):
    name = put(tmp_path, "scripts/moved.py", "x = 1\n" * 90)
    diff = ("diff --git a/old.py b/%s\nsimilarity index 100%%\nrename from old.py\nrename to %s\n"
            % (name, name))
    assert build([name], diff, tmp_path)["areas"][0]["lines"] == 1


def test_area_lines_sum_file_weights(tmp_path):
    files = [put(tmp_path, "scripts/a.py", "x\n" * 100), put(tmp_path, "scripts/b.py", "x\n" * 100)]
    diff = modify_diff(files[0], ["a"], ["b"]) + modify_diff(files[1], [], ["c", "d", "e"])
    area = build(files, diff, tmp_path)["areas"][0]
    assert area["lines"] == 2 + 3


def test_default_size_cap_is_600_in_function_and_cli(tmp_path):
    module = area_map_module()
    for function in (module.partition_areas, module.build_area_map):
        assert inspect.signature(function).parameters["max_lines"].default == 600
    files = ["a/x.py", "a/y.py"]
    assert len(module.partition_areas(files, {f: set() for f in files}, {files[0]: 300, files[1]: 300})) == 1
    assert len(module.partition_areas(files, {f: set() for f in files}, {files[0]: 300, files[1]: 301})) == 2
    context = tmp_path / "context.json"
    changes = "".join("+l%d\n" % i for i in range(301))
    diff = "".join("diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -0,0 +1,301 @@\n%s" % (f, f, f, f, changes)
                   for f in files)
    context.write_text(json.dumps({"changed_files": files, "diff": diff}))
    result = subprocess.run([sys.executable, str(SCRIPTS / "build_area_map.py"), "--context", str(context),
                             "--out", str(tmp_path / "map.json")], capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert len(json.loads(result.stdout)["areas"]) == 2


def test_hunks_get_area_scoped_ids_and_exact_headers_across_files():
    first = ("diff --git a/scripts/a.py b/scripts/a.py\n--- a/scripts/a.py\n+++ b/scripts/a.py\n"
             "@@ -1,2 +1,2 @@ def f():\n-x\n+y\n z\n@@ -40,2 +40,3 @@\n k\n+m\n n\n")
    second = modify_diff("scripts/b.py", ["p"], ["q"], header="@@ -5 +5 @@")
    area = build(["scripts/a.py", "scripts/b.py"], first + second)["areas"][0]
    assert area["hunks"] == [
        {"id": "A1.h1", "file": "scripts/a.py", "header": "@@ -1,2 +1,2 @@ def f():"},
        {"id": "A1.h2", "file": "scripts/a.py", "header": "@@ -40,2 +40,3 @@"},
        {"id": "A1.h3", "file": "scripts/b.py", "header": "@@ -5 +5 @@"},
    ]
    assert area["hunkless_files"] == []


def test_hunk_numbering_restarts_per_area_and_follows_area_file_order():
    files = ["a/one.py", "b/two.py"]
    diff = modify_diff(files[1], ["a"], ["b"], "@@ -2 +2 @@") + modify_diff(files[0], ["a"], ["b"], "@@ -1 +1 @@")
    areas = build(files, diff, max_files=1)["areas"]
    assert [a["hunks"] for a in areas] == [
        [{"id": "A1.h1", "file": "a/one.py", "header": "@@ -1 +1 @@"}],
        [{"id": "A2.h1", "file": "b/two.py", "header": "@@ -2 +2 @@"}],
    ]


def test_repeated_sections_for_one_path_contribute_in_order():
    diff = (modify_diff("a.py", ["a"], ["b"], "@@ -1 +1 @@") + modify_diff("a.py", ["c"], ["d"], "@@ -9 +9 @@"))
    area = build(["a.py"], diff)["areas"][0]
    assert [h["header"] for h in area["hunks"]] == ["@@ -1 +1 @@", "@@ -9 +9 @@"]
    assert [h["id"] for h in area["hunks"]] == ["A1.h1", "A1.h2"]
    assert area["lines"] == 4


def test_test_files_hunks_are_listed_once_after_their_position_in_the_area():
    files = ["scripts/a.py", "tests/test_a.py"]
    diff = (modify_diff(files[1], ["a"], ["b"], "@@ -3 +3 @@") + modify_diff(files[0], ["a"], ["b"], "@@ -1 +1 @@"))
    area = build(files, diff)["areas"][0]
    assert area["test_files"] == [files[1]]
    assert [h["file"] for h in area["hunks"]] == files


def test_renamed_and_quoted_paths_map_to_their_new_name():
    files = ["scripts/new name.py", "scripts/renamed.py"]
    diff = ('diff --git "a/scripts/new name.py" "b/scripts/new name.py"\n'
            '--- "a/scripts/new name.py"\n+++ "b/scripts/new name.py"\n@@ -1 +1 @@\n-a\n+b\n'
            "diff --git a/scripts/old.py b/scripts/renamed.py\nsimilarity index 80%\n"
            "rename from scripts/old.py\nrename to scripts/renamed.py\n"
            "--- a/scripts/old.py\n+++ b/scripts/renamed.py\n@@ -2 +2 @@\n-a\n+b\n")
    hunks = build(files, diff)["areas"][0]["hunks"]
    assert [(h["file"], h["header"]) for h in hunks] == [
        ("scripts/new name.py", "@@ -1 +1 @@"), ("scripts/renamed.py", "@@ -2 +2 @@")]


def test_pure_rename_and_binary_files_are_hunkless():
    files = ["scripts/moved.py", "assets/logo.png", "scripts/edit.py"]
    diff = ("diff --git a/scripts/old.py b/scripts/moved.py\nsimilarity index 100%\n"
            "rename from scripts/old.py\nrename to scripts/moved.py\n"
            "diff --git a/assets/logo.png b/assets/logo.png\nBinary files a/assets/logo.png and b/assets/logo.png differ\n"
            + modify_diff("scripts/edit.py", ["a"], ["b"]))
    areas = build(files, diff, max_files=8)["areas"]
    assert sorted(f for a in areas for f in a["hunkless_files"]) == sorted(files[:2])
    assert [h["file"] for a in areas for h in a["hunks"]] == ["scripts/edit.py"]


def test_empty_diff_gives_no_hunks_and_every_file_hunkless():
    files = ["scripts/a.py", "tests/test_a.py"]
    area = build(files, "")["areas"][0]
    assert area["hunks"] == []
    assert area["hunkless_files"] == files


def test_priority_ranks_by_non_test_changed_lines_then_edges_then_id():
    files = ["a/p.py", "b/q.py", "c/r.py", "d/s.py", "e/t.py"]
    sizes = {"a/p.py": 3, "b/q.py": 9, "c/r.py": 3, "d/s.py": 3, "e/t.py": 1}
    diff = "".join("diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -0,0 +1,%d @@\n%s" % (
        f, f, f, f, n, "+x\n" * n) for f, n in sizes.items())
    areas = build(files, diff, max_files=1)["areas"]
    assert [(a["id"], a["priority"]) for a in areas] == [
        ("A1", 2), ("A2", 1), ("A3", 3), ("A4", 4), ("A5", 5)]


def test_priority_breaks_ties_by_coupled_edge_count(tmp_path):
    files = [put(tmp_path, "one/a.py", "pass\n"), put(tmp_path, "two/b.py", "import c\n"),
             put(tmp_path, "two/c.py", "pass\n")]
    diff = "".join("diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -0,0 +1,2 @@\n+x\n+y\n" % (f, f, f, f)
                   for f in files)
    areas = build(files, diff, tmp_path, max_files=2)["areas"]
    by_files = {tuple(a["files"]): a for a in areas}
    coupled = next(a for a in areas if len(a["files"]) == 2)
    alone = next(a for a in areas if len(a["files"]) == 1)
    assert coupled["coupled_edges"] and not alone["coupled_edges"]
    assert coupled["priority"] == 1 and alone["priority"] == 2
    assert len(by_files) == 2


def test_priority_ignores_test_file_lines():
    files = ["a/p.py", "tests/test_x.py"]
    diff = (modify_diff("a/p.py", ["a"], ["b"]) + "".join(
        "diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -0,0 +1,50 @@\n%s" % (f, f, f, f, "+x\n" * 50)
        for f in files[1:]))
    areas = build(files, diff, max_files=1)["areas"]
    prod = next(a for a in areas if a["files"] == ["a/p.py"])
    only_tests = next(a for a in areas if a["files"] == ["tests/test_x.py"])
    assert prod["priority"] == 1 and only_tests["priority"] == 2


def test_existing_area_keys_are_unchanged():
    area = build(["a.py"], "")["areas"][0]
    assert {"id", "title", "files", "test_files", "coupled_edges", "lines", "questions", "status",
            "degraded_reason", "hunks", "hunkless_files", "priority"} == set(area)


def test_estimate_capacity_fitting_budget():
    result = area_map_module().estimate_capacity(6, 60, 3)
    assert result == {"areas": 6, "waves": 2, "estimated_minutes": 16.0, "available_minutes": 48.0,
                      "fits": True, "fit_count": 6, "finder_minutes": 8.0, "concurrency": 3}


def test_estimate_capacity_not_fitting_budget_counts_areas_that_fit():
    result = area_map_module().estimate_capacity(10, 30, 2, finder_minutes=8.0, elapsed_minutes=4.0)
    assert result["waves"] == 5 and result["estimated_minutes"] == 40.0
    assert math.isclose(result["available_minutes"], 20.0)
    assert result["fits"] is False
    assert result["fit_count"] == 2 * 2


def test_estimate_capacity_fit_count_is_capped_at_area_count_and_floored_at_zero():
    module = area_map_module()
    assert module.estimate_capacity(3, 600, 5)["fit_count"] == 3
    exhausted = module.estimate_capacity(3, 10, 2, elapsed_minutes=9.0)
    assert exhausted["fit_count"] == 0 and exhausted["fits"] is False


def test_estimate_capacity_survives_a_quotient_that_overflows_to_infinity():
    module = area_map_module()
    result = module.estimate_capacity(1, 1e308, 1, finder_minutes=5e-324)
    assert result["fit_count"] == 1 and result["fits"] is True
    exhausted = module.estimate_capacity(3, 10, 2, finder_minutes=5e-324, elapsed_minutes=1e308)
    assert exhausted["fit_count"] == 0 and exhausted["fits"] is False


def test_estimate_capacity_with_no_areas_fits():
    result = area_map_module().estimate_capacity(0, 10, 2)
    assert result["waves"] == 0 and result["estimated_minutes"] == 0 and result["fits"] is True


@pytest.mark.parametrize("kwargs", [
    {"budget_minutes": 0}, {"budget_minutes": -5}, {"budget_minutes": math.nan},
    {"budget_minutes": math.inf}, {"budget_minutes": True}, {"budget_minutes": "60"},
    {"concurrency": 0}, {"concurrency": -1}, {"concurrency": 2.5}, {"concurrency": True},
    {"finder_minutes": 0}, {"finder_minutes": -1.0}, {"finder_minutes": math.nan},
    {"finder_minutes": False}, {"elapsed_minutes": -1}, {"elapsed_minutes": math.nan},
    {"elapsed_minutes": math.inf}, {"elapsed_minutes": True},
])
def test_estimate_capacity_rejects_invalid_values(kwargs):
    arguments = {"area_count": 4, "budget_minutes": 60, "concurrency": 2, **kwargs}
    with pytest.raises(ValueError):
        area_map_module().estimate_capacity(**arguments)


def run_cli(tmp_path, *extra):
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"changed_files": ["a.py", "b/c.py"], "diff": ""}))
    return subprocess.run([sys.executable, str(SCRIPTS / "build_area_map.py"), "--context", str(context),
                           "--out", str(tmp_path / "map.json"), "--max-files", "1", *extra],
                          capture_output=True, text=True, check=False)


def test_cli_emits_capacity_when_budget_is_given(tmp_path):
    result = run_cli(tmp_path, "--budget-minutes", "20", "--concurrency", "1", "--elapsed-minutes", "2",
                     "--finder-minutes", "5")
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert json.loads((tmp_path / "map.json").read_text()) == output
    assert output["capacity"] == {"areas": 2, "waves": 2, "estimated_minutes": 10.0,
                                  "available_minutes": 14.0, "fits": True, "fit_count": 2,
                                  "finder_minutes": 5.0, "concurrency": 1}


def test_cli_capacity_defaults_elapsed_zero_and_finder_eight(tmp_path):
    output = json.loads(run_cli(tmp_path, "--budget-minutes", "100", "--concurrency", "2").stdout)
    assert output["capacity"]["finder_minutes"] == 8.0
    assert output["capacity"]["available_minutes"] == 80.0


def test_cli_omits_capacity_without_budget(tmp_path):
    result = run_cli(tmp_path)
    assert result.returncode == 0
    assert "capacity" not in json.loads(result.stdout)


@pytest.mark.parametrize("extra", [
    ["--budget-minutes", "0", "--concurrency", "1"],
    ["--budget-minutes", "-5", "--concurrency", "1"],
    ["--budget-minutes", "nan", "--concurrency", "1"],
    ["--budget-minutes", "60"],
    ["--budget-minutes", "60", "--concurrency", "0"],
    ["--budget-minutes", "60", "--concurrency", "1.5"],
    ["--budget-minutes", "60", "--concurrency", "1", "--elapsed-minutes", "-1"],
    ["--budget-minutes", "60", "--concurrency", "1", "--finder-minutes", "0"],
    ["--budget-minutes", "wat", "--concurrency", "1"],
])
def test_cli_rejects_invalid_capacity_inputs(tmp_path, extra):
    result = run_cli(tmp_path, *extra)
    assert result.returncode == 2
    assert isinstance(json.loads(result.stdout)["error"], str)
