"""Contracts for coupled review areas and the command-line area-map writer."""

import importlib
import json
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


def test_html_styles_count_toward_review_size_limit(tmp_path):
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
