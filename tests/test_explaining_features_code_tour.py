"""Behavior of explaining-features/scripts/code_tour.py: it turns tour.json and measured voice clips into a code-tour film's scenes, and refuses a tour whose code differs from its commit."""

from __future__ import annotations

import ast
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import unicodedata
import wave
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_TOUR = REPO_ROOT / "skills" / "explaining-features" / "scripts" / "code_tour.py"

FRAME = 1 / 30
FIRST_ROW_Y = 200
ROW_H = 52

APP = [
    'import { useState } from "react";',
    "",
    "/* a block",
    " * comment */",
    "export function App() {",
    "\tconst a = x < 3 && y > 2;",
    '\tconst s = "say \\"hi\\" & bye";',
    "\t// a /* nested */ comment",
    "\tif (a <= 1 && b >= 2) {",
    "\t\treturn <p>{s}</p>;",
    "\t}",
    '\tconst long = "' + "word " * 17 + '";',
    '\tconst glob = "src/**/*.ts";',
    "\treturn null;",
    "}",
]
BIG = [f"const v{n} = {n};" for n in range(1, 41)]
BIG[19] = 'const wide = "' + "w" * 100 + '";'


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    return done.stdout.strip()


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """One read-only repository for the whole module, because every git process is slow to start."""
    root = tmp_path_factory.mktemp("tour-repo") / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.tsx").write_bytes(("\n".join(APP) + "\n").encode())
    (root / "src" / "big.ts").write_bytes(("\n".join(BIG) + "\n").encode())
    git(root.parent, "init", "-q", str(root))
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "first")
    return root, git(root, "rev-parse", "HEAD")


def write_wav(path: Path, seconds: float, rate: int = 1000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(round(seconds * rate)))


def line(text: str, source: str = "src/app.tsx:1", **extra: Any) -> dict[str, Any]:
    return {"text": text, "source": source, **extra}


def default_scenes() -> list[dict[str, Any]]:
    return [
        {
            "map": [{"name": "Plugin", "file": "app.tsx"}, {"name": "Big file", "file": "big.ts"}, {"name": "Styles", "file": "x.css"}],
            "lines": [line("Add project crosses three files.", "git diff", lit=[0]), line("The rest lives lower down.", "spec", lit=[1, 2])],
            "label": "Three files",
        },
        {
            "stop": "PLUGIN", "path": "src/app.tsx",
            "rows": [3, 4, 5, 6, 7, 8, {"skip": "branch", "from": 9, "to": 12}, 13],
            "lines": [line("It compares two numbers.", "src/app.tsx:6", highlight=[6]), line("Then it globs the sources.", "src/app.tsx:13", highlight=[13])],
            "label": "Two things happen",
        },
        {
            "stop": "INNER", "path": "src/app.tsx", "rows": [6, 7, 8, 9, 10, 11],
            "lines": [line("It returns a paragraph.", "src/app.tsx:10", highlight=[10])],
        },
    ]


def count_lines(scenes: list[dict[str, Any]]) -> int:
    return sum(len(s["lines"]) for s in scenes)


SCAFFOLD = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      /* Placeholders: replace all three with the film's own palette and display face. */
      :root { --ground: #6b6b6b; }
    </style>
  </head>
  <body>
    <div id="root"><div id="title">Hello</div></div>
  </body>
</html>
"""


def make_project(
    tmp_path: Path,
    sha: str,
    repo_dir: Path,
    scenes: Optional[list[dict[str, Any]]] = None,
    *,
    seconds: Any = 1.5,
    commit: Optional[str] = None,
    scaffold: bool = True,
    wavs: bool = True,
    title: str = "Add project: how it's built",
) -> Path:
    scenes = default_scenes() if scenes is None else scenes
    project = tmp_path / "proj"
    project.mkdir(exist_ok=True)
    tour = {"repo": str(repo_dir), "commit": sha if commit is None else commit, "title": title, "scenes": scenes}
    (project / "tour.json").write_text(json.dumps(tour), encoding="utf-8")
    if scaffold:
        (project / "scenes").mkdir(exist_ok=True)
        (project / "scenes" / "index.html").write_text(SCAFFOLD, encoding="utf-8")
    if wavs:
        for n in range(1, count_lines(scenes) + 1):
            length = seconds[n - 1] if isinstance(seconds, (list, tuple)) else seconds
            write_wav(project / "assets" / "voice" / f"l{n:02d}.wav", length)
    return project


LENGTHS = [1.234, 2.001, 0.777, 3.3333, 1.0]


@pytest.fixture(scope="module")
def shared(repo: tuple[Path, str], tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The default tour built once. Tests that only read it share it; tests that edit it work on a clone."""
    return built(tmp_path_factory.mktemp("tour-shared"), repo, seconds=LENGTHS)


def clone(project: Path, tmp_path: Path) -> Path:
    target = tmp_path / "clone"
    shutil.copytree(project, target)
    return target


def copy_repo(repo: tuple[Path, str], tmp_path: Path) -> tuple[Path, str]:
    target = tmp_path / "repo-copy"
    shutil.copytree(repo[0], target)
    return target, repo[1]


def run(command: str, project: Path, *, env: Optional[dict[str, str]] = None) -> tuple[int, dict[str, Any], str]:
    proc = subprocess.run(
        [sys.executable, str(CODE_TOUR), command, "--project", str(project)],
        capture_output=True, text=True, timeout=120, env=env,
    )
    out = proc.stdout.strip()
    return proc.returncode, (json.loads(out) if out else {}), proc.stderr


def built(tmp_path: Path, repo: tuple[Path, str], scenes: Optional[list[dict[str, Any]]] = None, **kw: Any) -> Path:
    project = make_project(tmp_path, repo[1], repo[0], scenes, **kw)
    code, _, err = run("build", project)
    assert code == 0, err
    return project


def composition(project: Path, name: str) -> str:
    return (project / "scenes" / "compositions" / f"{name}.html").read_text(encoding="utf-8")


def no_git_env(tmp_path: Path) -> dict[str, str]:
    empty = tmp_path / "empty-bin"
    empty.mkdir(exist_ok=True)
    return {"PATH": str(empty)}


def cells(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


@pytest.fixture(scope="module")
def tour_module() -> Any:
    spec = importlib.util.spec_from_file_location("code_tour_under_test", CODE_TOUR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def on_frame(seconds: float) -> bool:
    return abs(seconds / FRAME - round(seconds / FRAME)) < 1e-3


def code_rows(markup: str) -> dict[int, tuple[int, str]]:
    """data-line -> (data-dedent, text) for each code row, read back the way a browser would."""
    rows: dict[int, tuple[int, str]] = {}
    for match in re.finditer(r'<div class="txt" id="[^"]*" data-line="(\d+)" data-dedent="(\d+)">(.*?)</div>', markup, re.S):
        text = html.unescape(re.sub(r"<[^>]+>", "", match.group(3)))
        rows[int(match.group(1))] = (int(match.group(2)), text)
    return rows


class WrapBlocks(HTMLParser):
    """The text of each explicit wrap block (span.w) of each numbered code row, in order."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: dict[int, list[str]] = {}
        self.line = 0
        self.depth = 0
        self.inside = False

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        a = dict(attrs)
        if "data-line" in a:
            self.line = int(a["data-line"])
            self.rows[self.line] = []
        elif tag == "span" and self.inside:
            self.depth += 1
        elif tag == "span" and a.get("class") == "w" and self.line:
            self.inside, self.depth = True, 0
            self.rows[self.line].append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self.inside:
            if self.depth:
                self.depth -= 1
            else:
                self.inside = False

    def handle_data(self, data: str) -> None:
        if self.inside:
            self.rows[self.line][-1] += data


def wrap_blocks(markup: str) -> dict[int, list[str]]:
    parser = WrapBlocks()
    parser.feed(markup)
    return parser.rows


class TestLines:
    def test_writes_one_clip_per_narration_line_in_order(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, repo[1], repo[0], wavs=False, scaffold=False)
        code, out, _ = run("lines", project)
        assert code == 0
        assert out == {"lines": 5}
        clips = json.loads((project / "assets" / "lines.json").read_text())
        assert [c["id"] for c in clips] == ["l01", "l02", "l03", "l04", "l05"]
        assert [c["text"] for c in clips] == [
            "Add project crosses three files.", "The rest lives lower down.", "It compares two numbers.",
            "Then it globs the sources.", "It returns a paragraph.",
        ]
        assert all(c["start_s"] == 0 for c in clips)

    def test_never_touches_git(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, "no-such-ref", tmp_path / "gone", wavs=False, scaffold=False)
        code, out, _ = run("lines", project, env=no_git_env(tmp_path))
        assert code == 0
        assert out == {"lines": 5}

    def test_a_line_with_no_source_cannot_ship(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = default_scenes()
        del scenes[1]["lines"][1]["source"]
        project = make_project(tmp_path, repo[1], repo[0], scenes, wavs=False)
        code, _, err = run("lines", project)
        assert code == 1
        assert "Then it globs the sources." in err
        assert "source" in err
        assert not (project / "assets" / "lines.json").exists()

    @pytest.mark.parametrize("source", ["", "   ", None, 7])
    def test_a_blank_or_non_text_source_cannot_ship(self, tmp_path: Path, repo: tuple[Path, str], source: Any) -> None:
        scenes = default_scenes()
        scenes[2]["lines"][0]["source"] = source
        project = make_project(tmp_path, repo[1], repo[0], scenes, wavs=False)
        assert run("lines", project)[0] == 1

    def test_a_highlight_naming_a_line_the_stop_does_not_show_cannot_ship(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = default_scenes()
        scenes[1]["lines"][0]["highlight"] = [10]
        project = make_project(tmp_path, repo[1], repo[0], scenes, wavs=False)
        code, _, err = run("lines", project)
        assert code == 1
        assert "10" in err and "PLUGIN" in err

    def test_a_highlight_on_a_skipped_line_cannot_ship(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = default_scenes()
        scenes[1]["lines"][0]["highlight"] = [9]
        project = make_project(tmp_path, repo[1], repo[0], scenes, wavs=False)
        assert run("lines", project)[0] == 1

    def test_a_lit_node_the_map_does_not_have_cannot_ship(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = default_scenes()
        scenes[0]["lines"][0]["lit"] = [3]
        project = make_project(tmp_path, repo[1], repo[0], scenes, wavs=False)
        assert run("lines", project)[0] == 1

    def test_missing_tour_is_a_usage_error_naming_the_file(self, tmp_path: Path) -> None:
        code, _, err = run("lines", tmp_path)
        assert code == 2
        assert "tour.json" in err

    @pytest.mark.parametrize("breakage", [
        lambda t: t.pop("commit"),
        lambda t: t.pop("title"),
        lambda t: t.update(repo="relative/path"),
        lambda t: t.update(scenes=[]),
        lambda t: t["scenes"][0].update(map=t["scenes"][0]["map"][:1]),
        lambda t: t["scenes"][0].update(map=t["scenes"][0]["map"] + [{"name": "a", "file": "b"}, {"name": "c", "file": "d"}]),
        lambda t: t["scenes"][1].update(rows=[]),
        lambda t: t["scenes"][1].update(rows=[3, 4, 6]),
        lambda t: t["scenes"][1].update(rows=[3, 4, 5, 6, 7, 8, {"skip": "x", "from": 10, "to": 12}, 13]),
        lambda t: t["scenes"][1].update(rows=[0, 1]),
        lambda t: t["scenes"][1].update(path=""),
        lambda t: t["scenes"][1].update(lines=[]),
        lambda t: t["scenes"][1]["lines"][0].update(text=""),
        lambda t: t["scenes"][1]["lines"][0].update(highlight=[]),
        lambda t: t["scenes"][1]["lines"][0].update(highlight="6"),
        lambda t: t["scenes"][2].update(label="x" * 200),
        lambda t: t["scenes"].append({"neither": "map nor stop", "lines": []}),
    ])
    def test_a_malformed_tour_is_a_usage_error(self, tmp_path: Path, repo: tuple[Path, str], breakage: Any) -> None:
        project = make_project(tmp_path, repo[1], repo[0], wavs=False)
        tour = json.loads((project / "tour.json").read_text())
        breakage(tour)
        (project / "tour.json").write_text(json.dumps(tour))
        assert run("lines", project)[0] == 2

    def test_tour_that_is_not_json_is_a_usage_error(self, tmp_path: Path) -> None:
        (tmp_path / "tour.json").write_text("{not json")
        assert run("lines", tmp_path)[0] == 2

    def test_a_missing_project_flag_is_a_usage_error(self) -> None:
        proc = subprocess.run([sys.executable, str(CODE_TOUR), "lines"], capture_output=True, text=True)
        assert proc.returncode == 2
        assert proc.stdout == ""


class TestTextLimits:
    def lines(self, tmp_path: Path, repo: tuple[Path, str], *, label: Optional[str] = None, title: Optional[str] = None) -> tuple[int, str]:
        scenes = default_scenes()
        if label is not None:
            scenes[2]["label"] = label
        project = make_project(tmp_path, repo[1], repo[0], scenes, wavs=False, **({} if title is None else {"title": title}))
        code, _, err = run("lines", project)
        return code, err

    WORST_LABEL = " ".join(["aaaaa"] * 12)
    WORST_TITLE = "Add project: one button, three places"

    def refused(self, code: int, err: str) -> None:
        assert code == 2
        assert "more rows than the screen has" in err and "shorten" in err

    def test_the_worst_label_in_two_rows_of_35_is_accepted(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        assert len(self.WORST_LABEL) == 71
        assert self.lines(tmp_path, repo, label=self.WORST_LABEL)[0] == 0

    def test_three_long_words_that_wrap_to_a_third_label_row_are_refused(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        label = " ".join(["a" * 23] * 3)
        assert len(label) == 71
        self.refused(*self.lines(tmp_path, repo, label=label))

    def test_a_label_word_longer_than_a_row_cannot_wrap_and_is_refused(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        assert self.lines(tmp_path, repo, label="x" * 35)[0] == 0
        self.refused(*self.lines(tmp_path, repo, label="x" * 36))
        self.refused(*self.lines(tmp_path, repo, label="x" * 200))

    def test_a_cjk_label_breaks_between_characters_so_two_rows_of_35_fit(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        assert self.lines(tmp_path, repo, label="漢" * 70)[0] == 0
        self.refused(*self.lines(tmp_path, repo, label="漢" * 71))

    def test_a_cjk_run_can_only_break_between_wide_characters(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        assert self.lines(tmp_path, repo, label="a" * 30 + "漢" * 10)[0] == 0
        self.refused(*self.lines(tmp_path, repo, label="a" * 36 + "漢" * 3))

    def test_a_title_in_three_rows_of_17_is_accepted(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        assert self.lines(tmp_path, repo, title=self.WORST_TITLE)[0] == 0

    def test_a_title_that_needs_four_rows_is_refused(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        self.refused(*self.lines(tmp_path, repo, title=" ".join(["a" * 10] * 4)))

    def test_a_title_word_longer_than_a_row_is_refused(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        assert self.lines(tmp_path, repo, title="x" * 17)[0] == 0
        self.refused(*self.lines(tmp_path, repo, title="x" * 18))

    def test_a_blank_label_or_title_is_still_a_usage_error(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        assert self.lines(tmp_path, repo, label="  ")[0] == 2
        assert self.lines(tmp_path, repo, title="")[0] == 2


class TestMissingInputs:
    def test_build_without_the_scaffold_names_the_command_that_makes_it(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, repo[1], repo[0], scaffold=False)
        code, _, err = run("build", project)
        assert code == 2
        assert "hf.py" in err and "init" in err

    def test_build_without_a_voice_clip_names_the_clip_and_the_command(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, repo[1], repo[0])
        (project / "assets" / "voice" / "l03.wav").unlink()
        code, _, err = run("build", project)
        assert code == 2
        assert "l03" in err and "voice.py" in err and "say" in err

    def test_build_without_a_tour_is_a_usage_error(self, tmp_path: Path) -> None:
        code, _, err = run("build", tmp_path)
        assert code == 2
        assert "tour.json" in err

    def test_build_with_a_voice_clip_that_is_not_a_wav_is_a_usage_error(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, repo[1], repo[0])
        (project / "assets" / "voice" / "l01.wav").write_bytes(b"not a wav")
        code, _, err = run("build", project)
        assert code == 2
        assert "l01" in err

    def test_build_with_a_lines_file_that_no_longer_matches_the_tour_asks_for_new_voice(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, repo[1], repo[0])
        assert run("lines", project)[0] == 0
        tour = json.loads((project / "tour.json").read_text())
        tour["scenes"][2]["lines"][0]["text"] = "A different sentence."
        (project / "tour.json").write_text(json.dumps(tour))
        code, _, err = run("build", project)
        assert code == 2
        assert "l05" in err and "lines" in err

    def test_check_without_a_tour_is_a_usage_error(self, tmp_path: Path) -> None:
        code, _, err = run("check", tmp_path)
        assert code == 2
        assert "tour.json" in err

    def test_check_before_any_build_names_the_build_command(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, repo[1], repo[0])
        code, _, err = run("check", project)
        assert code == 2
        assert "code_tour.py build" in err


class TestGit:
    def test_build_and_check_exit_3_when_git_is_missing(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = make_project(tmp_path, repo[1], repo[0])
        assert run("build", project, env=no_git_env(tmp_path))[0] == 3
        assert run("check", shared, env=no_git_env(tmp_path))[0] == 3

    def test_a_commit_that_does_not_resolve_cannot_ship(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, repo[1], repo[0], commit="deadbeefdeadbeef")
        code, out, err = run("build", project)
        assert code == 1
        assert "deadbeefdeadbeef" in err
        assert "error" in out
        assert not (project / "beats.json").exists()

    def test_a_commit_shaped_like_an_option_is_a_ref_not_a_flag(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, repo[1], repo[0], commit="--all")
        code, _, err = run("build", project)
        assert code == 1
        assert "--all" in err

    def test_a_directory_that_is_not_a_repository_cannot_ship(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        bare = tmp_path / "plain"
        bare.mkdir()
        project = make_project(tmp_path, repo[1], bare)
        assert run("build", project)[0] == 1

    def test_a_path_that_does_not_exist_at_the_commit_cannot_ship(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = default_scenes()
        scenes[2]["path"] = "src/missing.tsx"
        project = make_project(tmp_path, repo[1], repo[0], scenes)
        code, _, err = run("build", project)
        assert code == 1
        assert "src/missing.tsx" in err

    def test_a_path_that_is_a_folder_cannot_ship(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = default_scenes()
        scenes[2]["path"] = "src"
        project = make_project(tmp_path, repo[1], repo[0], scenes)
        assert run("build", project)[0] == 1

    def test_a_line_past_the_end_of_the_file_cannot_ship_and_is_named(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = default_scenes()
        scenes[2]["rows"] = [14, 15, 16]
        scenes[2]["lines"][0]["highlight"] = [15]
        project = make_project(tmp_path, repo[1], repo[0], scenes)
        code, _, err = run("build", project)
        assert code == 1
        assert "src/app.tsx:16" in err

    def test_a_skipped_range_past_the_end_of_the_file_cannot_ship(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = default_scenes()
        scenes[2]["rows"] = [13, {"skip": "tail", "from": 14, "to": 99}]
        scenes[2]["lines"][0]["highlight"] = [13]
        project = make_project(tmp_path, repo[1], repo[0], scenes)
        code, _, err = run("build", project)
        assert code == 1
        assert "99" in err

    def test_code_is_read_at_the_commit_not_the_working_tree(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        root, sha = copy_repo(repo, tmp_path)
        (root / "src" / "app.tsx").write_text("changed\n" * 20)
        git(root, "commit", "-q", "-am", "second")
        project = built(tmp_path, (root, sha))
        assert code_rows(composition(project, "s2"))[6][1].strip().startswith("const a = x < 3")


class TestWrapping:
    COMMENT = "/* the highlight bar sits on the row and moves when the line changes, to the button's right */"
    LONG = "x" * 200
    INDENTED = "        " + "word " * 20 + "end"

    def source(self, tmp_path: Path, lines: list[str]) -> tuple[Path, str]:
        root = tmp_path / "wrap-repo"
        (root / "src").mkdir(parents=True)
        (root / "src" / "w.ts").write_text("\n".join(lines) + "\n")
        git(root.parent, "init", "-q", str(root))
        git(root, "add", ".")
        git(root, "commit", "-q", "-m", "first")
        return root, git(root, "rev-parse", "HEAD")

    def stop(self, rows: list[int]) -> list[dict[str, Any]]:
        return [{"stop": "WRAP", "path": "src/w.ts", "rows": rows, "lines": [line("Look.", "src/w.ts:1", highlight=[rows[-1]])]}]

    def build(self, tmp_path: Path, lines: list[str], rows: list[int]) -> tuple[Path, dict[str, Any]]:
        root, sha = self.source(tmp_path, lines)
        project = make_project(tmp_path, sha, root, self.stop(rows))
        code, out, err = run("build", project)
        assert code == 0, err
        return project, out

    def test_a_long_comment_breaks_at_a_space_and_keeps_its_words(self, tmp_path: Path) -> None:
        assert len(self.COMMENT) > 72
        project, _ = self.build(tmp_path, ["a", self.COMMENT], [1, 2])
        blocks = wrap_blocks(composition(project, "s1"))[2]
        assert len(blocks) == 2
        assert "".join(blocks) == self.COMMENT
        assert all(len(b) <= 72 for b in blocks)
        assert blocks[0].endswith(" ")
        assert not blocks[1].startswith(" ")
        assert blocks[0] + blocks[1] == self.COMMENT
        assert {w for b in blocks for w in b.split()} == set(self.COMMENT.split())

    def test_an_unbroken_run_longer_than_a_row_still_hard_breaks(self, tmp_path: Path) -> None:
        project, _ = self.build(tmp_path, ["a", self.LONG], [1, 2])
        blocks = wrap_blocks(composition(project, "s1"))[2]
        assert [len(b) for b in blocks] == [72, 72, 56]
        assert "".join(blocks) == self.LONG

    def test_a_row_whose_only_spaces_are_its_indentation_hard_breaks(self, tmp_path: Path) -> None:
        text = "    " + "z" * 100
        project, _ = self.build(tmp_path, ["a", text], [1, 2])
        blocks = wrap_blocks(composition(project, "s1"))[2]
        assert [len(b) for b in blocks] == [72, 32]
        assert "".join(blocks) == text

    def test_a_continuation_does_not_gain_indentation(self, tmp_path: Path) -> None:
        project, _ = self.build(tmp_path, ["a", self.INDENTED], [1, 2])
        blocks = wrap_blocks(composition(project, "s1"))[2]
        assert len(blocks) == 2
        assert blocks[0].startswith("        ")
        assert not blocks[1].startswith(" ")
        assert "".join(blocks) == self.INDENTED

    def test_wide_characters_wrap_by_cells_and_join_back_exactly(self, tmp_path: Path) -> None:
        text = "// " + "漢" * 69
        project, _ = self.build(tmp_path, ["a", text], [1, 2])
        blocks = wrap_blocks(composition(project, "s1"))[2]
        assert blocks == ["// ", "漢" * 36, "漢" * 33]
        assert "".join(blocks) == text
        assert all(cells(b) <= 72 for b in blocks)

    def test_a_wide_character_that_does_not_fit_the_last_cell_moves_to_the_next_block(self, tmp_path: Path) -> None:
        text = "a" * 71 + "漢" * 3
        project, _ = self.build(tmp_path, ["a", text], [1, 2])
        blocks = wrap_blocks(composition(project, "s1"))[2]
        assert blocks == ["a" * 71, "漢漢漢"]

    def test_a_stop_of_wide_lines_overflows_by_cells_and_is_refused(self, tmp_path: Path) -> None:
        root, sha = self.source(tmp_path, ["漢" * 50] * 8)
        project = make_project(tmp_path, sha, root, self.stop(list(range(1, 9))))
        code, _, err = run("build", project)
        assert code == 1
        assert "16" in err

    def test_check_passes_a_clean_build_of_wide_lines(self, tmp_path: Path) -> None:
        project, _ = self.build(tmp_path, ["a", "// " + "漢" * 69, "漢" * 50], [1, 2, 3])
        code, out, err = run("check", project)
        assert code == 0, err
        assert out["checked"] == 3

    def test_cells_count_wide_and_fullwidth_as_two(self, tour_module: Any) -> None:
        assert tour_module._cells("a漢Ａ") == 5
        assert tour_module._cells("") == 0

    def test_a_wide_character_always_makes_progress_on_a_budget_smaller_than_it(self, tour_module: Any) -> None:
        assert tour_module._break_at("漢漢", 1) == 1
        chunks = tour_module._chunks([(None, "漢漢漢")], 1)
        assert ["".join(p for _, p in c) for c in chunks] == ["漢", "漢", "漢"]

    def test_check_still_compares_whole_lines(self, tmp_path: Path) -> None:
        project, _ = self.build(tmp_path, ["a", self.COMMENT, self.LONG], [1, 2, 3])
        code, out, err = run("check", project)
        assert code == 0, err
        assert out["checked"] == 3
        assert out["mismatches"] == []

    def test_the_row_count_and_beat_height_match_the_rendered_blocks(self, tmp_path: Path) -> None:
        lines = ["a", self.COMMENT, self.LONG, "    " + "z" * 100, "b"]
        project, out = self.build(tmp_path, lines, [1, 2, 3, 4, 5])
        rendered = wrap_blocks(composition(project, "s1"))
        assert out["stops"][0]["rows"] == sum(len(b) for b in rendered.values())
        beats = {b["id"]: b for b in json.loads((project / "beats.json").read_text())}
        assert beats["s1-l01"]["region"][3] == ROW_H * len(rendered[5])
        assert beats["s1-l01"]["region"][1] == FIRST_ROW_Y + ROW_H * sum(len(rendered[n]) for n in (1, 2, 3, 4))


class TestRowLimit:
    def stop(self, rows: list[Any], label: Optional[str] = None) -> list[dict[str, Any]]:
        first = next(r for r in rows if isinstance(r, int))
        scene: dict[str, Any] = {
            "stop": "BIG", "path": "src/big.ts", "rows": rows,
            "lines": [line("Look here.", "src/big.ts:1", highlight=[first])],
        }
        if label:
            scene["label"] = label
        return [scene]

    def test_a_stop_at_exactly_fourteen_rows_builds(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = self.stop(list(range(1, 15)))
        project = make_project(tmp_path, repo[1], repo[0], scenes)
        code, out, err = run("build", project)
        assert code == 0, err
        assert out["stops"] == [{"stop": "BIG", "rows": 14}]

    def test_a_stop_at_fifteen_rows_is_refused_and_named(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, repo[1], repo[0], self.stop(list(range(1, 16))))
        code, _, err = run("build", project)
        assert code == 1
        assert "BIG" in err and "15" in err and "14" in err
        assert not (project / "scenes" / "compositions").exists()

    def test_a_label_takes_a_row_so_thirteen_is_the_limit(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        ok = make_project(tmp_path, repo[1], repo[0], self.stop(list(range(1, 14)), "Why it matters"))
        assert run("build", ok)[0] == 0
        over = tmp_path / "over"
        over.mkdir()
        project = make_project(over, repo[1], repo[0], self.stop(list(range(1, 15)), "Why it matters"))
        code, _, err = run("build", project)
        assert code == 1
        assert "13" in err

    def test_a_long_line_wraps_into_extra_rows_that_count(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        # line 20 breaks after 'const wide = ' and its 103-character string hard-breaks, so it takes three rows
        fits = make_project(tmp_path, repo[1], repo[0], self.stop(list(range(9, 21))))
        code, out, _ = run("build", fits)
        assert code == 0
        assert out["stops"][0]["rows"] == 14
        over = tmp_path / "over"
        over.mkdir()
        project = make_project(over, repo[1], repo[0], self.stop(list(range(8, 21))))
        code, _, err = run("build", project)
        assert code == 1
        assert "15" in err

    def test_a_skip_row_counts_as_one_row(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        rows = [1, 2, {"skip": "many", "from": 3, "to": 30}, 31]
        project = make_project(tmp_path, repo[1], repo[0], self.stop(rows))
        code, out, _ = run("build", project)
        assert code == 0
        assert out["stops"][0]["rows"] == 4

    def test_a_film_of_ninety_seconds_or_more_cannot_ship(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = default_scenes()
        project = make_project(tmp_path, repo[1], repo[0], scenes, seconds=18.0)
        code, _, err = run("build", project)
        assert code == 1
        assert "90" in err
        assert not (project / "beats.json").exists()

    def test_a_film_just_under_ninety_seconds_builds(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = default_scenes()
        project = make_project(tmp_path, repo[1], repo[0], scenes, seconds=16.0)
        code, out, err = run("build", project)
        assert code == 0, err
        assert 85 < out["film_s"] < 90


class TestBuild:
    def test_reports_scenes_beats_film_and_stops(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, repo[1], repo[0])
        code, out, err = run("build", project)
        assert code == 0, err
        assert out["scenes"] == 3
        assert out["stops"] == [{"stop": "PLUGIN", "rows": 8}, {"stop": "INNER", "rows": 6}]
        beats = json.loads((project / "beats.json").read_text())
        assert out["beats"] == len(beats)
        assert on_frame(out["film_s"])

    def test_writes_every_file_the_film_needs(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        for name in ("s1", "s2", "s3"):
            assert (project / "scenes" / "compositions" / f"{name}.html").is_file()
        for n in range(1, 6):
            assert (project / "scenes" / "assets" / "voice" / f"l{n:02d}.wav").read_bytes() == (project / "assets" / "voice" / f"l{n:02d}.wav").read_bytes()
        for name in ("beats.json", "sources.md", "storyboard.md"):
            assert (project / name).is_file()
        assert (project / "kit" / "kit.md").is_file()

    def test_index_keeps_the_scaffold_head_and_hosts_every_scene(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        page = (project / "scenes" / "index.html").read_text()
        assert "gsap.min.js" in page.split("<body", 1)[0]
        assert "Placeholders: replace all three" in page
        for name in ("s1", "s2", "s3"):
            assert f'<div id="{name}" class="clip" data-composition-id="{name}" data-composition-src="compositions/{name}.html"' in page
        assert 'data-composition-id="main"' in page
        assert 'window.__timelines["main"]' in page
        assert page.count("<audio") == 5
        assert "Hello" not in page

    def test_scenes_are_seek_safe_and_named_by_scene_id(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        for name in ("s1", "s2", "s3"):
            markup = composition(project, name)
            assert f'data-composition-id="{name}"' in markup
            assert f'window.__timelines["{name}"] = tl;' in markup
            assert "gsap.timeline({ paused: true })" in markup
            tweens = re.findall(r"tl\.fromTo\([^;]*\);", markup)
            assert tweens
            assert all("immediateRender: false" in t for t in tweens)
            assert "tl.set(" not in markup
            assert not re.search(r"font:\s", markup)
            assert "font-family" in markup
        assert 'gsap.set("#s2-label", { opacity: 0 });' in composition(project, "s2")

    def test_tokens_and_fonts_are_inlined_in_every_scene(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        for name in ("s1", "s2", "s3"):
            markup = composition(project, name)
            for token in ("#101114", "#16171b", "#2c3050", "#24262c", "#eceef2", "#9aa0ab", "#9aa6ff", "#c6cbe8", "Inter", "JetBrains Mono"):
                assert token in markup
            assert "<link" not in markup

    def test_code_text_is_the_source_after_unescaping(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        rows = code_rows(composition(project, "s2"))
        assert sorted(rows) == [3, 4, 5, 6, 7, 8, 13]
        for number, (dedent, text) in rows.items():
            expected = APP[number - 1].replace("\t", "    ")
            assert dedent == 0
            assert text == expected, number
        inner = code_rows(composition(project, "s3"))
        assert sorted(inner) == [6, 7, 8, 9, 10, 11]
        for number, (dedent, text) in inner.items():
            assert dedent == 4
            assert text == APP[number - 1].replace("\t", "    ")[4:]
        assert inner[9][1] == "if (a <= 1 && b >= 2) {"
        assert "&lt;=" in composition(project, "s3") and "&gt;=" in composition(project, "s3")

    def test_the_markup_holds_no_literal_comment_opener(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        for name in ("s1", "s2", "s3"):
            assert "/*" not in composition(project, name)
        assert "&#47;" in composition(project, "s2")

    def test_tokens_colour_comments_strings_and_keywords_without_changing_text(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        markup = composition(project, "s2")
        assert re.search(r'<span class="c">[^<]*a block', markup)
        assert re.search(r'<span class="s">&quot;|<span class="s">"', markup)
        assert '<span class="k">export</span>' in markup
        assert '<span class="k">function</span>' in markup

    def test_a_skipped_range_is_marked_on_screen(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        markup = composition(shared, "s2")
        assert 'data-skip="9-12"' in markup
        assert "branch (lines 9–12 skipped)" in markup

    def test_the_stop_commit_and_path_are_on_screen(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        markup = composition(shared, "s2")
        assert "STOP 1 OF 2 · PLUGIN" in markup
        assert f"commit {repo[1][:8]}" in markup
        assert re.search(r'class="mono path">src/app.tsx</div>', markup)

    def test_the_map_names_its_files_and_the_title_is_on_the_first_frame(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        markup = composition(shared, "s1")
        assert "Add project: how it&#x27;s built" in markup or "Add project: how it's built" in markup
        for text in ("Plugin", "app.tsx", "Big file", "big.ts", "Styles", "x.css"):
            assert text in markup

    def test_markup_in_a_title_or_a_map_node_is_escaped(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        raw = "<img src=x onerror=alert(1)>"
        scenes = default_scenes()
        scenes[0]["map"][0] = {"name": "<img onerror=alert(1)>", "file": raw}
        project = built(tmp_path, repo, scenes, title=raw)
        markup = composition(project, "s1")
        assert raw not in markup
        assert "<img" not in markup
        assert html.escape(raw, quote=False) in markup
        assert "&lt;img onerror=alert(1)&gt;" in markup

    def test_the_title_balances_its_lines_so_no_word_is_left_alone(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        css = re.search(r"\.title \{([^}]*)\}", composition(shared, "s1"))
        assert css and "text-wrap: balance" in css.group(1)

    def test_a_rebuild_is_identical_and_drops_scenes_the_tour_no_longer_has(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        first = {p.name: p.read_bytes() for p in (project / "scenes" / "compositions").glob("*.html")}
        stale = project / "scenes" / "compositions" / "s9.html"
        stale.write_text("stale")
        keep = project / "scenes" / "compositions" / "notes.html"
        keep.write_text("mine")
        assert run("build", project)[0] == 0
        again = {p.name: p.read_bytes() for p in (project / "scenes" / "compositions").glob("s[123].html")}
        assert again == {k: v for k, v in first.items() if k.startswith("s")}
        assert not stale.exists()
        assert keep.exists()


class TestBrandFonts:
    def studio(self, tmp_path: Path, fonts: dict[str, Any], files: Optional[dict[str, bytes]] = None, product: str = "acme") -> dict[str, str]:
        brand = tmp_path / "studio" / "brands" / product
        brand.mkdir(parents=True, exist_ok=True)
        (brand / "brand.json").write_text(json.dumps({"product": product, "fonts": fonts}))
        for name, data in (files or {}).items():
            (brand / name).parent.mkdir(parents=True, exist_ok=True)
            (brand / name).write_bytes(data)
        return {**os.environ, "QUIRK_STUDIO": str(tmp_path / "studio")}

    def project(self, tmp_path: Path, repo: tuple[Path, str], product: str = "acme") -> Path:
        project = make_project(tmp_path, repo[1], repo[0])
        (project / "brief.json").write_text(json.dumps({"product": product}))
        return project

    def families(self, markup: str) -> tuple[str, str]:
        return (
            re.search(r'--font-display: "([^"]*)"', markup).group(1),
            re.search(r'--font-mono: "([^"]*)"', markup).group(1),
        )

    def nothing_written(self, project: Path) -> None:
        assert not (project / "scenes" / "compositions").exists()
        assert not (project / "beats.json").exists()
        assert not (project / "scenes" / "assets" / "fonts").exists()

    def test_bundled_brand_families_replace_the_defaults_everywhere_and_need_no_font_face(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        env = self.studio(tmp_path, {"display": {"family": "Outfit", "files": []}, "mono": {"family": "IBM Plex Mono", "files": []}})
        project = self.project(tmp_path, repo)
        code, _, err = run("build", project, env=env)
        assert code == 0, err
        for markup in [composition(project, n) for n in ("s1", "s2", "s3")] + [(project / "scenes" / "index.html").read_text()]:
            assert self.families(markup) == ("Outfit", "IBM Plex Mono")
            assert "Inter" not in markup and "JetBrains" not in markup
            assert "@font-face" not in markup
        assert not (project / "scenes" / "assets" / "fonts").exists()
        kit = (project / "kit" / "kit.md").read_text()
        assert "display Outfit" in kit and "mono IBM Plex Mono" in kit
        assert "Inter" not in kit

    def test_a_family_that_is_not_bundled_ships_its_file_and_an_inline_font_face(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        env = self.studio(
            tmp_path,
            {"display": {"family": "Fraunces", "files": ["fonts/Fraunces.ttf"]}, "mono": {"family": "JetBrains Mono", "files": []}},
            {"fonts/Fraunces.ttf": b"font-bytes"},
        )
        project = self.project(tmp_path, repo)
        code, _, err = run("build", project, env=env)
        assert code == 0, err
        assert (project / "scenes" / "assets" / "fonts" / "display-0-Fraunces.ttf").read_bytes() == b"font-bytes"
        face = "@font-face { font-family: \"Fraunces\"; src: url('assets/fonts/display-0-Fraunces.ttf'); }"
        for markup in [composition(project, n) for n in ("s1", "s2", "s3")] + [(project / "scenes" / "index.html").read_text()]:
            assert markup.count(face) == 1
            assert markup.index(face) < markup.rindex(":root")
            assert self.families(markup) == ("Fraunces", "JetBrains Mono")
        assert "display Fraunces" in (project / "kit" / "kit.md").read_text()

    def test_two_font_files_with_the_same_name_keep_their_own_bytes_and_rules(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        env = self.studio(
            tmp_path,
            {"display": {"family": "Fraunces", "files": ["display/font.ttf"]}, "mono": {"family": "Space Mono Custom", "files": ["mono/font.ttf"]}},
            {"display/font.ttf": b"display-bytes", "mono/font.ttf": b"mono-bytes"},
        )
        project = self.project(tmp_path, repo)
        code, _, err = run("build", project, env=env)
        assert code == 0, err
        fonts = project / "scenes" / "assets" / "fonts"
        assert sorted(p.name for p in fonts.iterdir()) == ["display-0-font.ttf", "mono-0-font.ttf"]
        assert (fonts / "display-0-font.ttf").read_bytes() == b"display-bytes"
        assert (fonts / "mono-0-font.ttf").read_bytes() == b"mono-bytes"
        markup = composition(project, "s1")
        assert "font-family: \"Fraunces\"; src: url('assets/fonts/display-0-font.ttf')" in markup
        assert "font-family: \"Space Mono Custom\"; src: url('assets/fonts/mono-0-font.ttf')" in markup

    def test_two_files_of_one_role_with_the_same_name_do_not_collide(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        env = self.studio(
            tmp_path,
            {"display": {"family": "Fraunces", "files": ["regular/font.ttf", "bold/font.ttf"]}, "mono": {"family": "JetBrains Mono"}},
            {"regular/font.ttf": b"regular", "bold/font.ttf": b"bold"},
        )
        project = self.project(tmp_path, repo)
        assert run("build", project, env=env)[0] == 0
        fonts = project / "scenes" / "assets" / "fonts"
        assert (fonts / "display-0-font.ttf").read_bytes() == b"regular"
        assert (fonts / "display-1-font.ttf").read_bytes() == b"bold"

    def test_a_missing_brief_brand_or_role_falls_back_to_the_defaults_for_that_role(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        env = self.studio(tmp_path, {"mono": {"family": "Space Mono"}})
        for name, brief, expected in (
            ("nobrief", None, ("Inter", "JetBrains Mono")),
            ("nobrand", {"product": "ghost"}, ("Inter", "JetBrains Mono")),
            ("norole", {"product": "acme"}, ("Inter", "Space Mono")),
        ):
            where = tmp_path / name
            where.mkdir()
            project = make_project(where, repo[1], repo[0])
            if brief is not None:
                (project / "brief.json").write_text(json.dumps(brief))
            code, _, err = run("build", project, env=env)
            assert code == 0, err
            assert self.families(composition(project, "s2")) == expected, name

    def test_a_family_that_is_not_bundled_and_has_no_file_exits_1_before_writing(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        env = self.studio(tmp_path, {"display": {"family": "Fraunces", "files": []}, "mono": {"family": "JetBrains Mono"}})
        project = self.project(tmp_path, repo)
        code, _, err = run("build", project, env=env)
        assert code == 1
        assert "Fraunces" in err and "files" in err
        self.nothing_written(project)

    def test_a_font_file_that_does_not_exist_exits_1_before_writing(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        env = self.studio(tmp_path, {"display": {"family": "Fraunces", "files": ["fonts/Fraunces.ttf"]}, "mono": {"family": "JetBrains Mono"}})
        project = self.project(tmp_path, repo)
        code, _, err = run("build", project, env=env)
        assert code == 1
        assert "Fraunces" in err and "Fraunces.ttf" in err
        self.nothing_written(project)

    def test_a_font_file_outside_the_brand_folder_is_a_bad_input(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        env = self.studio(
            tmp_path,
            {"display": {"family": "Fraunces", "files": ["../../outside.ttf"]}, "mono": {"family": "JetBrains Mono"}},
            {"../../outside.ttf": b"x"},
        )
        project = self.project(tmp_path, repo)
        code, _, err = run("build", project, env=env)
        assert code == 2
        assert "outside.ttf" in err
        self.nothing_written(project)

    @pytest.mark.parametrize("family", ['Evil"; } body { color: red', "Name;", "A/B", "Bad'quote", "Tab\there", "Ünïcode"])
    def test_a_family_name_that_could_break_out_of_the_css_is_a_bad_input(self, tmp_path: Path, repo: tuple[Path, str], family: str) -> None:
        env = self.studio(tmp_path, {"display": {"family": family, "files": []}, "mono": {"family": "JetBrains Mono"}})
        project = self.project(tmp_path, repo)
        code, _, err = run("build", project, env=env)
        assert code == 2
        assert "font" in err
        self.nothing_written(project)

    def test_a_brand_family_outside_the_display_and_mono_roles_exits_1_naming_it(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        env = self.studio(tmp_path, {
            "display": {"family": "Outfit"}, "mono": {"family": "IBM Plex Mono"}, "accent": {"family": "Playfair Display"},
        })
        project = self.project(tmp_path, repo)
        code, _, err = run("build", project, env=env)
        assert code == 1
        assert "Playfair Display" in err
        self.nothing_written(project)

    def test_another_role_that_repeats_a_used_family_is_fine(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        env = self.studio(tmp_path, {"display": {"family": "Outfit"}, "mono": {"family": "IBM Plex Mono"}, "heading": {"family": "Outfit"}})
        project = self.project(tmp_path, repo)
        code, _, err = run("build", project, env=env)
        assert code == 0, err


class TestTiming:
    def starts(self, project: Path) -> dict[str, tuple[float, float]]:
        page = (project / "scenes" / "index.html").read_text()
        out = {}
        for match in re.finditer(r'<audio id="vo-(l\d+)"[^>]*data-start="([\d.]+)" data-duration="([\d.]+)"', page):
            out[match.group(1)] = (float(match.group(2)), float(match.group(3)))
        return out

    def hosts(self, project: Path) -> list[tuple[str, float, float]]:
        page = (project / "scenes" / "index.html").read_text()
        return [(m.group(1), float(m.group(2)), float(m.group(3))) for m in re.finditer(
            r'<div id="(s\d+)" class="clip"[^>]*data-start="([\d.]+)" data-duration="([\d.]+)"', page)]

    def test_every_clip_start_and_scene_boundary_is_on_a_frame(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        clips = json.loads((project / "assets" / "lines.json").read_text())
        assert all(on_frame(c["start_s"]) for c in clips)
        assert all(on_frame(s) for s, _ in self.starts(project).values())
        hosts = self.hosts(project)
        assert all(on_frame(start) and on_frame(duration) for _, start, duration in hosts)
        page = (project / "scenes" / "index.html").read_text()
        assert on_frame(float(re.search(r'data-composition-id="main" data-start="0" data-duration="([\d.]+)"', page).group(1)))

    def test_lead_gaps_and_hold_follow_the_measured_clip_lengths(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        lengths = [1.234, 2.001, 0.777, 3.3333, 1.0]
        project = built(tmp_path, repo, seconds=lengths)
        clips = json.loads((project / "assets" / "lines.json").read_text())
        starts = [c["start_s"] for c in clips]
        assert starts[0] == pytest.approx(0.3, abs=1e-6)
        ends = [s + n for s, n in zip(starts, lengths)]
        # l01-l02 share scene 1, l03-l04 share scene 2, l05 is scene 3
        for left, right in ((0, 1), (2, 3)):
            gap = starts[right] - ends[left]
            assert 0.35 - 1e-6 <= gap < 0.35 + FRAME
        for left, right in ((1, 2), (3, 4)):
            gap = starts[right] - ends[left]
            assert 0.8 - 1e-6 <= gap < 0.8 + FRAME
        page = (project / "scenes" / "index.html").read_text()
        film = float(re.search(r'data-composition-id="main" data-start="0" data-duration="([\d.]+)"', page).group(1))
        assert 2.5 - 1e-6 <= film - ends[-1] < 2.5 + FRAME

    def test_scenes_tile_the_film_with_no_gap_or_overlap(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        hosts = self.hosts(project)
        assert hosts[0][1] == 0
        for (_, start, duration), (_, nxt, _) in zip(hosts, hosts[1:]):
            assert start + duration == pytest.approx(nxt, abs=1e-5)
        page = (project / "scenes" / "index.html").read_text()
        film = float(re.search(r'data-composition-id="main" data-start="0" data-duration="([\d.]+)"', page).group(1))
        assert hosts[-1][1] + hosts[-1][2] == pytest.approx(film, abs=1e-5)

    def test_lines_json_is_rewritten_with_the_real_starts(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, repo[1], repo[0])
        assert run("lines", project)[0] == 0
        assert run("build", project)[0] == 0
        clips = json.loads((project / "assets" / "lines.json").read_text())
        assert [c["id"] for c in clips] == ["l01", "l02", "l03", "l04", "l05"]
        assert clips[0]["start_s"] > 0
        assert [c["start_s"] for c in clips] == sorted(c["start_s"] for c in clips)
        assert {s: v[0] for s, v in self.starts(project).items()} == {c["id"]: c["start_s"] for c in clips}

    def test_each_highlight_tween_starts_on_its_clips_start_frame(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        clips = {c["id"]: c["start_s"] for c in json.loads((project / "assets" / "lines.json").read_text())}
        scene_start = {name: start for name, start, _ in self.hosts(project)}
        cases = {"s2": [("l03", "#s2-b6"), ("l04", "#s2-b13")], "s3": [("l05", "#s3-b10")]}
        for scene, expected in cases.items():
            markup = composition(project, scene)
            for clip, selector in expected:
                match = re.search(r'tl\.fromTo\("%s",.*?\}, ([\d.]+)\);' % re.escape(selector), markup)
                assert match, selector
                assert float(match.group(1)) == pytest.approx(clips[clip] - scene_start[scene], abs=1e-5)
                assert on_frame(float(match.group(1)))

    def test_highlight_is_a_band_on_the_row_and_the_rest_dim(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        markup = composition(shared, "s2")
        assert re.search(r'tl\.fromTo\("#s2-b6", \{ opacity: 0 \}, \{ opacity: 1, duration: 0\.2, ease: "power2\.out", immediateRender: false \}', markup)
        assert re.search(r'tl\.fromTo\("#s2-t5", \{ opacity: 1 \}, \{ opacity: 0\.72, duration: 0\.2, ease: "power2\.out", immediateRender: false \}', markup)
        assert len(re.findall(r'"#s2-t6"', markup)) == 1
        # the second highlight takes the band off line 6 and puts it on 13
        assert re.search(r'tl\.fromTo\("#s2-b6", \{ opacity: 1 \}, \{ opacity: 0,', markup)
        assert re.search(r'tl\.fromTo\("#s2-b13", \{ opacity: 0 \}, \{ opacity: 1,', markup)

    def test_the_label_enters_with_the_last_line_of_its_scene(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        clips = {c["id"]: c["start_s"] for c in json.loads((project / "assets" / "lines.json").read_text())}
        scene_start = {name: start for name, start, _ in self.hosts(project)}
        match = re.search(r'tl\.fromTo\("#s2-label",.*?power3\.out.*?\}, ([\d.]+)\);', composition(project, "s2"))
        assert match
        assert float(match.group(1)) == pytest.approx(clips["l04"] - scene_start["s2"], abs=1e-5)


class TestBeats:
    def beats(self, project: Path) -> dict[str, dict[str, Any]]:
        return {b["id"]: b for b in json.loads((project / "beats.json").read_text())}

    def test_a_beat_region_is_the_accent_bar_of_the_highlighted_row(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        beats = self.beats(shared)
        # rows 3, 4 and 5 come before line 6; the skip row and rows 6 to 8 come before line 13
        assert beats["s2-l03"]["region"] == [98, FIRST_ROW_Y + 3 * ROW_H, 8, ROW_H]
        assert beats["s2-l04"]["region"] == [98, FIRST_ROW_Y + 7 * ROW_H, 8, ROW_H]
        assert beats["s3-l05"]["region"] == [98, FIRST_ROW_Y + 4 * ROW_H, 8, ROW_H]

    def test_a_wrapped_row_pushes_the_rows_after_it_down(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = [{
            "stop": "WRAP", "path": "src/app.tsx", "rows": [12, 13, 14],
            "lines": [line("Look at the glob.", "src/app.tsx:13", highlight=[13]), line("Then the wrapped line.", "src/app.tsx:12", highlight=[12])],
        }]
        project = built(tmp_path, repo, scenes)
        beats = self.beats(project)
        # line 12 is 101 characters once dedented, so it takes two rows
        assert beats["s1-l01"]["region"] == [98, FIRST_ROW_Y + 2 * ROW_H, 8, ROW_H]
        assert beats["s1-l02"]["region"] == [98, FIRST_ROW_Y, 8, 2 * ROW_H]

    def test_a_beat_carries_what_verify_needs(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        clips = {c["id"]: c["start_s"] for c in json.loads((project / "assets" / "lines.json").read_text())}
        starts = {name: start for name, start, _ in TestTiming().hosts(project)}
        beat = self.beats(project)["s2-l03"]
        assert beat["word"] == "it"
        assert beat["clip"] == "assets/voice/l03.wav"
        assert beat["clip_start_s"] == pytest.approx(clips["l03"], abs=1e-6)
        assert beat["expected_s"] == pytest.approx(clips["l03"], abs=1e-6)
        assert beat["baseline_s"] == pytest.approx(max(clips["l03"] - 0.5, starts["s2"] + 0.05), abs=1e-3)
        assert beat["detector"] == "changed"

    def test_a_label_has_a_beat_over_its_box(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        beats = self.beats(shared)
        assert beats["s2-label"]["region"] == [96, 900, 1728, 120]
        assert beats["s2-label"]["clip"] == "assets/voice/l04.wav"
        assert "s3-label" not in beats

    def test_a_line_that_moves_nothing_has_no_beat(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = default_scenes()
        scenes[1]["lines"].append(line("And once more.", "src/app.tsx:13", highlight=[13]))
        scenes[1]["lines"].append(line("A line with no highlight.", "src/app.tsx:1"))
        project = make_project(tmp_path, repo[1], repo[0], scenes)
        assert run("build", project)[0] == 0
        beats = self.beats(project)
        assert "s2-l05" not in beats and "s2-l06" not in beats

    def test_a_map_node_lights_with_a_bar_the_beat_watches(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        beats = self.beats(project)
        assert "s1-l01" in beats and "s1-l02" in beats
        region = beats["s1-l01"]["region"]
        assert region[2] == 8
        assert 96 <= region[0] and region[0] + region[2] <= 1824
        assert beats["s1-l02"]["region"][0] > region[0]
        assert 'id="s1-p0"' in composition(project, "s1")


class TestCheck:
    def test_passes_a_fresh_build_and_counts_every_code_line(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        code, out, err = run("check", project)
        assert code == 0, err
        assert out == {"commit": repo[1], "checked": 13, "mismatches": []}

    def test_fails_after_a_code_line_in_a_built_scene_is_changed(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        path = project / "scenes" / "compositions" / "s2.html"
        path.write_text(path.read_text().replace("x &lt; 3", "x &lt; 4"))
        code, out, err = run("check", project)
        assert code == 1
        assert out["checked"] == 13
        assert len(out["mismatches"]) == 1
        mismatch = out["mismatches"][0]
        assert mismatch["scene"] == "s2.html"
        assert mismatch["line"] == 6
        assert "x < 4" in mismatch["screen"]
        assert "x < 3" in mismatch["source"]
        assert "s2.html" in err and "6" in err

    def test_fails_after_a_dedent_that_cuts_non_whitespace(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        scenes = [{
            "stop": "TAIL", "path": "src/app.tsx", "rows": [13, 14],
            "lines": [line("The end.", "src/app.tsx:14", highlight=[14])],
        }]
        project = built(tmp_path, repo, scenes)
        path = project / "scenes" / "compositions" / "s1.html"
        markup = path.read_text()
        assert 'data-line="14" data-dedent="4"' in markup
        # the screen text still equals what is left of the source after the cut, so only the cut can give it away
        edited = re.sub(r'(data-line="14" data-dedent=")4(">).*?(</div>)', r"\g<1>8\g<2>rn null;\g<3>", markup, flags=re.S)
        assert edited != markup
        path.write_text(edited)
        code, out, err = run("check", project)
        assert code == 1
        assert [m["line"] for m in out["mismatches"]] == [14]
        assert "retu" in err or "whitespace" in err

    def row_markup(self, markup: str, scene: str, number: int) -> str:
        match = re.search(r'<div class="row" id="%s-r%d">.*?</div></div>' % (scene, number), markup, re.S)
        assert match
        return match.group(0)

    def edit(self, project: Path, name: str, change: Any) -> None:
        path = project / "scenes" / "compositions" / f"{name}.html"
        markup = path.read_text()
        edited = change(markup)
        assert edited != markup
        path.write_text(edited)

    def test_fails_when_a_row_loses_its_marker_and_others_remain(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        self.edit(project, "s2", lambda m: m.replace(' data-line="6" data-dedent="0"', ""))
        code, out, _ = run("check", project)
        assert code == 1
        reasons = " | ".join(m["reason"] for m in out["mismatches"])
        assert any(m["line"] == 6 for m in out["mismatches"])
        assert "data-line" in reasons

    def test_fails_when_a_text_element_has_no_marker_even_if_its_code_matches(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)

        def twin(markup: str) -> str:
            row = self.row_markup(markup, "s2", 6)
            return markup.replace(row, row + row.replace(' data-line="6" data-dedent="0"', "").replace('id="s2-r6"', 'id="s2-r6x"'))

        self.edit(project, "s2", twin)
        code, out, _ = run("check", project)
        assert code == 1
        assert out["checked"] == 13
        assert [m["reason"] for m in out["mismatches"]] == [out["mismatches"][0]["reason"]]
        assert "data-line" in out["mismatches"][0]["reason"]

    def test_fails_when_a_row_is_deleted_outright(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        self.edit(project, "s2", lambda m: m.replace(self.row_markup(m, "s2", 7), ""))
        code, out, _ = run("check", project)
        assert code == 1
        assert [m["line"] for m in out["mismatches"]] == [7]
        assert "tour.json" in out["mismatches"][0]["reason"]

    def test_fails_when_a_line_is_on_screen_that_the_tour_does_not_show(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        self.edit(project, "s2", lambda m: m.replace('data-line="13"', 'data-line="14"'))
        code, out, _ = run("check", project)
        assert code == 1
        for number in (13, 14):
            assert any("tour.json" in m["reason"] for m in out["mismatches"] if m["line"] == number)

    def test_fails_when_rows_are_swapped_in_the_markup(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)

        def swap(markup: str) -> str:
            first, second = self.row_markup(markup, "s2", 7), self.row_markup(markup, "s2", 8)
            assert markup.index(first) < markup.index(second)
            return markup.replace(first + "\n" + second, second + "\n" + first)

        self.edit(project, "s2", swap)
        code, out, _ = run("check", project)
        assert code == 1
        assert out["checked"] == 13
        assert len(out["mismatches"]) == 1
        reason = out["mismatches"][0]["reason"]
        assert "out of order" in reason
        assert "[3, 4, 5, 6, 8, 7, 13]" in reason and "[3, 4, 5, 6, 7, 8, 13]" in reason

    def test_a_missing_row_is_reported_as_missing_and_not_as_out_of_order(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        self.edit(project, "s2", lambda m: m.replace(self.row_markup(m, "s2", 7), ""))
        _, out, _ = run("check", project)
        assert not any("out of order" in m["reason"] for m in out["mismatches"])

    def stray(self, kind: str, markup: str) -> str:
        return {
            "rows": self.row_markup(markup, "s2", 6),
            "loose": '<div class="txt" id="stray">const a = 1;</div>',
            "skip": '<div class="row"><div class="num">x</div><div class="txt skip" data-skip="1-2"><span class="w">lines 1-2</span></div></div>',
        }[kind]

    @pytest.mark.parametrize("kind", ["rows", "loose", "skip"])
    def test_fails_when_a_map_scene_carries_code(self, tmp_path: Path, repo: tuple[Path, str], shared: Path, kind: str) -> None:
        project = clone(shared, tmp_path)
        extra = self.stray(kind, composition(shared, "s2"))
        self.edit(project, "s1", lambda m: m.replace('<div class="nodes">', extra + '<div class="nodes">'))
        code, out, err = run("check", project)
        assert code == 1
        assert out["checked"] == 13
        assert [m["scene"] for m in out["mismatches"]] == ["s1.html"]
        assert "shows none" in out["mismatches"][0]["reason"]
        assert "s1.html" in err

    @pytest.mark.parametrize("kind", ["rows", "loose", "skip"])
    def test_fails_when_a_composition_the_tour_does_not_name_carries_code(self, tmp_path: Path, repo: tuple[Path, str], shared: Path, kind: str) -> None:
        project = clone(shared, tmp_path)
        (project / "scenes" / "compositions" / "s9.html").write_text("<template><div>" + self.stray(kind, composition(shared, "s2")) + "</div></template>")
        code, out, _ = run("check", project)
        assert code == 1
        assert out["checked"] == 13
        assert [m["scene"] for m in out["mismatches"]] == ["s9.html"]
        assert "shows none" in out["mismatches"][0]["reason"]

    def test_a_composition_without_code_that_the_tour_does_not_name_is_fine(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        (project / "scenes" / "compositions" / "outro.html").write_text("<template><div class=\"title\">The end</div></template>")
        code, out, err = run("check", project)
        assert code == 0, err
        assert out["checked"] == 13

    def test_fails_when_a_skip_row_is_gone(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        self.edit(project, "s2", lambda m: m.replace('data-skip="9-12"', 'data-skp="9-12"'))
        assert run("check", project)[0] == 1

    def test_fails_when_a_stop_has_no_composition(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        (project / "scenes" / "compositions" / "s3.html").unlink()
        code, out, err = run("check", project)
        assert code == 1
        assert any(m["scene"] == "s3.html" for m in out["mismatches"])
        assert "s3.html" in err

    def test_fails_when_one_stop_has_no_code_rows_and_the_others_do(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        self.edit(project, "s3", lambda m: m.replace("data-line=", "data-ln="))
        code, out, _ = run("check", project)
        assert code == 1
        assert out["checked"] == 7
        assert any(m["scene"] == "s3.html" for m in out["mismatches"])

    def test_fails_when_the_path_on_screen_is_not_the_tours(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        self.edit(project, "s3", lambda m: m.replace(">src/app.tsx<", ">src/big.ts<"))
        code, out, _ = run("check", project)
        assert code == 1
        assert any("src/big.ts" in m["reason"] for m in out["mismatches"])

    def test_fails_when_no_code_line_is_found_on_screen(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        for path in (project / "scenes" / "compositions").glob("*.html"):
            path.write_text(path.read_text().replace("data-line=", "data-ln="))
        code, out, err = run("check", project)
        assert code == 1
        assert out["checked"] == 0
        assert "0" in err

    def test_a_tour_with_no_code_stop_cannot_be_built(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, repo[1], repo[0], default_scenes()[:1])
        code, _, err = run("build", project)
        assert code == 1
        assert "checked" in err or "0" in err

    def test_fails_when_the_commit_in_the_tour_changes_under_a_built_film(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        root, sha = copy_repo(repo, tmp_path)
        (root / "src" / "app.tsx").write_bytes(("\n".join(APP).replace("x < 3", "x < 9") + "\n").encode())
        git(root, "commit", "-q", "-am", "second")
        project = built(tmp_path, (root, sha))
        tour = json.loads((project / "tour.json").read_text())
        tour["commit"] = git(root, "rev-parse", "HEAD")
        (project / "tour.json").write_text(json.dumps(tour))
        code, out, _ = run("check", project)
        assert code == 1
        assert out["mismatches"][0]["line"] == 6

    def test_fails_when_a_scene_names_a_path_the_commit_does_not_have(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        path = project / "scenes" / "compositions" / "s3.html"
        path.write_text(path.read_text().replace(">src/app.tsx<", ">src/gone.tsx<"))
        code, _, err = run("check", project)
        assert code == 1
        assert "src/gone.tsx" in err

    def test_fails_when_the_commit_no_longer_resolves(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = clone(shared, tmp_path)
        tour = json.loads((project / "tour.json").read_text())
        tour["commit"] = "0" * 40
        (project / "tour.json").write_text(json.dumps(tour))
        assert run("check", project)[0] == 1


class TestScript:
    def test_imports_only_the_standard_library(self) -> None:
        tree = ast.parse(CODE_TOUR.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
        assert names
        stdlib = Path(sysconfig.get_paths()["stdlib"]).resolve()
        for name in names:
            spec = importlib.util.find_spec(name)
            assert spec is not None, name
            origin = spec.origin or ""
            assert origin in ("built-in", "frozen") or Path(origin).resolve().is_relative_to(stdlib), name
            assert "site-packages" not in origin, name

    def test_runs_with_site_packages_switched_off(self) -> None:
        proc = subprocess.run([sys.executable, "-I", "-S", str(CODE_TOUR), "--help"], capture_output=True, text=True)
        assert proc.returncode == 0
        assert "lines" in proc.stdout and "build" in proc.stdout and "check" in proc.stdout

    def test_parses_as_python_3_9(self) -> None:
        ast.parse(CODE_TOUR.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_prints_one_json_object_on_stdout_and_never_prompts(self, tmp_path: Path, repo: tuple[Path, str]) -> None:
        project = make_project(tmp_path, repo[1], repo[0])
        proc = subprocess.run(
            [sys.executable, str(CODE_TOUR), "build", "--project", str(project)],
            capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120,
        )
        assert proc.returncode == 0
        assert len(proc.stdout.strip().splitlines()) == 1
        assert isinstance(json.loads(proc.stdout), dict)


class TestWrittenNotes:
    def test_sources_lists_every_narration_line_with_its_source_and_the_commit(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        text = (project / "sources.md").read_text()
        assert repo[1] in text
        assert str(repo[0]) in text
        for source in ("git diff", "spec", "src/app.tsx:6", "src/app.tsx:13", "src/app.tsx:10"):
            assert source in text
        assert "It compares two numbers." in text

    def test_storyboard_has_a_script_item_and_a_timed_row_per_scene(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        project = shared
        text = (project / "storyboard.md").read_text()
        assert text.startswith("# Add project: how it's built")
        script = re.search(r"## Script\n\n(.*?)\n\n## ", text, re.S).group(1)
        assert len(re.findall(r"^\d+\. ", script, re.M)) == 3
        table = [row for row in text.splitlines() if row.startswith("| s")]
        assert len(table) == 3
        header = next(row for row in text.splitlines() if row.startswith("| Scene"))
        assert "Time" in header
        starts = [float(re.search(r"\d+(?:\.\d+)?", row.split("|")[2]).group(0)) for row in table]
        assert starts[0] == 0
        assert starts == sorted(starts)

    def test_storyboard_scenes_are_found_by_the_making_videos_parser(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        scripts = REPO_ROOT / "skills" / "making-videos" / "scripts"
        spec = importlib.util.spec_from_file_location("review_page_under_test", scripts / "review_page.py")
        assert spec and spec.loader
        sys.path.insert(0, str(scripts))
        try:
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        finally:
            sys.path.remove(str(scripts))
        project = shared
        scenes = module.parse_scenes((project / "storyboard.md").read_text())
        assert scenes is not None
        assert [s.scene_id for s in scenes] == ["s1", "s2", "s3"]
        assert scenes[0].start == "0.0" or float(scenes[0].start) == 0
        assert "Add project crosses three files." in scenes[0].words

    def test_the_kit_names_the_tokens_and_motion(self, tmp_path: Path, repo: tuple[Path, str], shared: Path) -> None:
        text = (shared / "kit" / "kit.md").read_text()
        for token in ("#101114", "#9aa6ff", "Inter", "JetBrains Mono", "0.2 s", "power2.out"):
            assert token in text
        assert "frame before" not in text
        assert "starting on the frame of its narration line" in text
