"""split-branch analyze.sh: per-line review weighting of a branch diff."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional, Union

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYZE = REPO_ROOT / "skills" / "split-branch" / "scripts" / "analyze.sh"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _write(repo: Path, files: Dict[str, Optional[str]]) -> None:
    for rel, content in files.items():
        path = repo / rel
        if content is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)


def _run(
    tmp_path: Path,
    base: Dict[str, Optional[str]],
    feature: Dict[str, Optional[str]],
    env: Optional[Dict[str, str]] = None,
    project_config: Union[dict, str, None] = None,
    user_config: Union[dict, str, None] = None,
) -> subprocess.CompletedProcess:
    repo = tmp_path / "repo"
    repo.mkdir()
    # a private HOME keeps the developer's real ~/.quirk config out of every case
    home = tmp_path / "home"
    home.mkdir()
    if user_config is not None:
        _write_config(home / ".quirk" / "split-branch.json", user_config)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    # an untouched file keeps main non-empty when a case has no base files
    _write(repo, {"README": "base\n", **base})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo, feature)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "feature")
    # written untracked after the commits so the config itself isn't part of the diff
    if project_config is not None:
        _write_config(repo / ".quirk" / "split-branch.json", project_config)
    return subprocess.run(
        [str(ANALYZE), "main"],
        cwd=repo,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home), **(env or {})},
    )


def _write_config(path: Path, config: Union[dict, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config if isinstance(config, str) else json.dumps(config))


def analyze(tmp_path: Path, base, feature, env=None, **configs) -> dict:
    result = _run(tmp_path, base, feature, env, **configs)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def weight_of(report: dict, path: str) -> float:
    for row in report["files"]:
        if row["file"] == path:
            return row["weighted_lines"]
    raise AssertionError(f"{path} not in files: {[r['file'] for r in report['files']]}")


def test_blank_lines_cost_nothing(tmp_path):
    report = analyze(tmp_path, {}, {"app/x.js": "a = 1;\n\n\nb = 2;\n"})
    assert weight_of(report, "app/x.js") == pytest.approx(2.0)
    assert report["total_blank_lines"] == 2


def test_hash_comments_cost_a_quarter(tmp_path):
    src = "# one\n# two\n# three\n# four\nx = 1\n"
    report = analyze(tmp_path, {}, {"app/c.py": src})
    assert weight_of(report, "app/c.py") == pytest.approx(2.0)
    assert report["total_comment_lines"] == 4


def test_slash_comments_cost_a_quarter(tmp_path):
    report = analyze(tmp_path, {}, {"app/c.js": "// one\n  // two\nrun();\n"})
    assert weight_of(report, "app/c.js") == pytest.approx(1.5)


def test_c_block_comment_costs_a_quarter_per_line(tmp_path):
    src = "/*\n * a\n * b\n */\nint x = 1;\n"
    report = analyze(tmp_path, {}, {"app/c.c": src})
    assert weight_of(report, "app/c.c") == pytest.approx(2.0)


def test_python_docstring_counts_as_comment(tmp_path):
    src = 'def f():\n    """Doc.\n\n    More.\n    """\n    return 1\n'
    report = analyze(tmp_path, {}, {"app/d.py": src})
    # def 1 + three docstring lines 0.75 + blank 0 + return 1
    assert weight_of(report, "app/d.py") == pytest.approx(2.75)


def test_shebang_is_code_not_comment(tmp_path):
    report = analyze(tmp_path, {}, {"bin/run.sh": "#!/bin/sh\necho hi\n"})
    assert weight_of(report, "bin/run.sh") == pytest.approx(2.0)


def test_comment_in_test_file_is_flat_quarter(tmp_path):
    report = analyze(tmp_path, {}, {"tests/test_x.py": "# why\nassert f()\n"})
    assert weight_of(report, "tests/test_x.py") == pytest.approx(0.75)


def test_js_reindent_is_free(tmp_path):
    base = {"src/r.js": "function f() {\nreturn computeTheTotal(x);\n}\n"}
    feature = {"src/r.js": "function f() {\n    return computeTheTotal(x);\n}\n"}
    report = analyze(tmp_path, base, feature)
    assert weight_of(report, "src/r.js") == pytest.approx(0.0)
    assert report["total_whitespace_only_lines"] == 2


def test_python_reindent_still_counts(tmp_path):
    base = {"src/r.py": "if x:\n    y = compute_value(a)\nz = 1\n"}
    feature = {"src/r.py": "if x:\n    pass\ny = compute_value(a)\nz = 1\n"}
    report = analyze(tmp_path, base, feature)
    # -indented y (0.5) + pass (1) + dedented y (1)
    assert weight_of(report, "src/r.py") == pytest.approx(2.5)


def test_block_moved_between_files_costs_a_tenth(tmp_path):
    moved = "const total = computeInvoiceTotal(lines);\nconst taxed = applyRegionalTax(total);\n"
    base = {"src/a.js": "start();\n" + moved + "finish();\n", "src/b.js": "other();\n"}
    feature = {"src/a.js": "start();\nfinish();\n", "src/b.js": "other();\n" + moved}
    report = analyze(tmp_path, base, feature)
    assert weight_of(report, "src/a.js") == pytest.approx(0.2)
    assert weight_of(report, "src/b.js") == pytest.approx(0.2)
    assert report["total_moved_lines"] == 4


def test_short_line_is_not_treated_as_moved(tmp_path):
    base = {"src/p.js": "x();\n}\n", "src/q.js": "y();\n"}
    feature = {"src/p.js": "x();\n", "src/q.js": "y();\n}\n"}
    report = analyze(tmp_path, base, feature)
    assert weight_of(report, "src/p.js") == pytest.approx(0.5)
    assert weight_of(report, "src/q.js") == pytest.approx(1.0)


def test_pure_rename_is_free(tmp_path):
    body = "".join(f"value_{i} = compute_something({i})\n" for i in range(10))
    report = analyze(tmp_path, {"old/name.py": body}, {"old/name.py": None, "new/name.py": body})
    assert report["weighted_review_lines"] == 0


def test_deleted_code_costs_half(tmp_path):
    report = analyze(tmp_path, {"src/d.py": "a = 1\nb = 2\n"}, {"src/d.py": "a = 1\n"})
    assert weight_of(report, "src/d.py") == pytest.approx(0.5)


def test_python_imports_cost_a_quarter(tmp_path):
    src = "import os\nfrom x import y\nprint(1)\n"
    report = analyze(tmp_path, {}, {"src/i.py": src})
    assert weight_of(report, "src/i.py") == pytest.approx(1.5)
    assert report["total_import_lines"] == 2


def test_js_imports_cost_a_quarter(tmp_path):
    src = "import a from 'a';\nconst b = require('b');\nrun();\n"
    report = analyze(tmp_path, {}, {"src/i.js": src})
    assert weight_of(report, "src/i.js") == pytest.approx(1.5)


def test_go_import_block_costs_a_quarter(tmp_path):
    src = 'package m\n\nimport (\n\t"fmt"\n\t"os"\n)\n\nfunc f() {}\n'
    report = analyze(tmp_path, {}, {"src/i.go": src})
    # package 1 + four import-block lines 1.0 + func 1
    assert weight_of(report, "src/i.go") == pytest.approx(3.0)


def test_migration_code_is_up_weighted_but_comments_are_not(tmp_path):
    src = "-- add col\nALTER TABLE t ADD c int;\n"
    report = analyze(tmp_path, {}, {"db/migrations/001.sql": src})
    assert weight_of(report, "db/migrations/001.sql") == pytest.approx(1.75)
    assert report["total_risky_lines"] == 2


def test_snapshot_file_costs_a_tenth(tmp_path):
    src = "".join(f"line {i}\n" for i in range(10))
    report = analyze(tmp_path, {}, {"src/__snapshots__/a.snap": src})
    assert weight_of(report, "src/__snapshots__/a.snap") == pytest.approx(1.0)
    assert report["total_fixture_lines"] == 10


def test_prose_doc_costs_half_and_heading_is_not_a_comment(tmp_path):
    report = analyze(tmp_path, {}, {"docs/a.md": "# Title\n\nSome text.\n"})
    assert weight_of(report, "docs/a.md") == pytest.approx(1.0)
    assert report["total_prose_lines"] == 3


def test_lockfile_costs_nothing(tmp_path):
    src = "".join(f"pkg{i}: 1.0.{i}\n" for i in range(5))
    report = analyze(tmp_path, {}, {"pnpm-lock.yaml": src})
    assert report["weighted_review_lines"] == 0
    assert report["total_excluded_lines"] == 5


def test_raw_kind_totals_keep_their_meaning(tmp_path):
    feature = {"src/s.py": "a = 1\n\n# c\n", "tests/test_s.py": "assert 1\n"}
    report = analyze(tmp_path, {}, feature)
    assert report["total_source_lines"] == 3
    assert report["total_test_lines"] == 1
    assert report["total_lines_added"] == 4


def test_comment_weight_override(tmp_path):
    src = "# one\n# two\n# three\n# four\nx = 1\n"
    report = analyze(tmp_path, {}, {"app/c.py": src}, env={"COMMENT_WEIGHT": "1"})
    assert weight_of(report, "app/c.py") == pytest.approx(5.0)
    assert report["weights"]["comment"] == pytest.approx(1.0)


def test_prose_weight_override(tmp_path):
    report = analyze(tmp_path, {}, {"docs/a.md": "# Title\n\nSome text.\n"}, env={"PROSE_WEIGHT": "1"})
    assert weight_of(report, "docs/a.md") == pytest.approx(2.0)


def test_non_numeric_weight_is_rejected(tmp_path):
    result = _run(tmp_path, {}, {"src/a.py": "a = 1\n"}, env={"TEST_WEIGHT": "abc"})
    assert result.returncode != 0
    assert "TEST_WEIGHT" in result.stderr


def test_directory_groups_sum_to_total(tmp_path):
    feature = {
        "src/a.py": "import os\nx = compute(1)\n# note\n",
        "tests/test_a.py": "assert x\n",
        "docs/a.md": "Words here.\n",
        "db/migrations/1.sql": "ALTER TABLE t ADD c int;\n",
    }
    report = analyze(tmp_path, {}, feature)
    file_sum = sum(row["weighted_lines"] for row in report["files"])
    dir_sum = sum(group["weighted_lines"] for group in report["directory_groups"])
    assert dir_sum == pytest.approx(file_sum)
    # 0.25 + 1 + 0.25 + 0.5 + 0.5 + 1.5
    assert file_sum == pytest.approx(4.0)
    assert report["weighted_review_lines"] == 4


COMMENTED_PY = {"app/c.py": "# one\n# two\n# three\n# four\nx = 1\n"}
IMPORTS_PY = {"app/i.py": "import os\nimport sys\n# note\nx = 1\n"}


def test_project_config_weight_applies(tmp_path):
    report = analyze(tmp_path, {}, COMMENTED_PY, project_config={"weights": {"comment": 1}})
    assert weight_of(report, "app/c.py") == pytest.approx(5.0)


def test_user_config_weight_applies(tmp_path):
    report = analyze(tmp_path, {}, COMMENTED_PY, user_config={"weights": {"comment": 1}})
    assert weight_of(report, "app/c.py") == pytest.approx(5.0)


def test_project_config_beats_user_config_key_by_key(tmp_path):
    report = analyze(
        tmp_path,
        {},
        IMPORTS_PY,
        user_config={"weights": {"comment": 1, "import": 1}},
        project_config={"weights": {"comment": 0.5}},
    )
    # imports 2 x 1 (user) + comment 0.5 (project) + code 1
    assert weight_of(report, "app/i.py") == pytest.approx(3.5)
    assert report["weights"]["comment"] == pytest.approx(0.5)
    assert report["weights"]["import"] == pytest.approx(1.0)


def test_env_beats_project_config(tmp_path):
    report = analyze(
        tmp_path,
        {},
        COMMENTED_PY,
        env={"COMMENT_WEIGHT": "0"},
        project_config={"weights": {"comment": 1}},
    )
    assert weight_of(report, "app/c.py") == pytest.approx(1.0)


RISKY_FEATURE = {"infra/x.py": "x = 1\n", "db/migrations/1.sql": "ALTER TABLE t ADD c int;\n"}


@pytest.mark.parametrize("pattern", ["(^|/)infra/", ["(^|/)nothing/", "(^|/)infra/"]])
def test_config_pattern_extends_the_default(tmp_path, pattern):
    report = analyze(tmp_path, {}, RISKY_FEATURE, project_config={"patterns": {"risky": pattern}})
    assert weight_of(report, "infra/x.py") == pytest.approx(1.5)
    assert weight_of(report, "db/migrations/1.sql") == pytest.approx(1.5)


def test_env_pattern_still_replaces_the_default(tmp_path):
    report = analyze(
        tmp_path,
        {},
        RISKY_FEATURE,
        env={"RISKY_PATTERNS": "(^|/)infra/"},
        project_config={"patterns": {"risky": "(^|/)db/"}},
    )
    assert weight_of(report, "infra/x.py") == pytest.approx(1.5)
    assert weight_of(report, "db/migrations/1.sql") == pytest.approx(1.0)


def test_split_goals_default_with_sources(tmp_path):
    report = analyze(tmp_path, {}, {"src/a.py": "a = 1\n"})
    assert (report["target_lines_per_split"], report["hard_cap"], report["skip_threshold"]) == (300, 600, 200)
    assert report["goal_sources"] == {
        "target_lines_per_split": "default",
        "hard_cap": "default",
        "skip_threshold": "default",
    }
    assert report["config_files"] == []


def test_split_goals_come_from_config_layers(tmp_path):
    report = analyze(
        tmp_path,
        {},
        {"src/a.py": "a = 1\n"},
        env={"HARD_CAP": "800"},
        user_config={"skip_threshold": 150},
        project_config={"target_lines_per_split": 250},
    )
    assert (report["target_lines_per_split"], report["hard_cap"], report["skip_threshold"]) == (250, 800, 150)
    assert report["goal_sources"] == {
        "target_lines_per_split": "project",
        "hard_cap": "env",
        "skip_threshold": "user",
    }
    assert [Path(p).parent.parent.name for p in report["config_files"]] == ["home", "repo"]


@pytest.mark.parametrize(
    "config, needle",
    [
        ({"weigths": {"comment": 1}}, "weigths"),
        ({"weights": {"comments": 1}}, "weights.comments"),
        ({"patterns": {"riskyy": "x"}}, "patterns.riskyy"),
        ("{not json", "split-branch.json"),
        ({"weights": {"comment": "abc"}}, "project config"),
        ({"hard_cap": "big"}, "HARD_CAP"),
        ({"skip_threshold": 500}, "skip_threshold"),
    ],
)
def test_bad_config_is_rejected(tmp_path, config, needle):
    result = _run(tmp_path, {}, {"src/a.py": "a = 1\n"}, project_config=config)
    assert result.returncode != 0
    assert needle in result.stderr
