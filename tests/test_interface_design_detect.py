"""Detector behavior over fixtures, CLI exit codes and formats, and --changed-since. No network."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import List, Sequence, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "interface-design" / "scripts" / "detect.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "interface-design"
DIRTY = FIXTURES / "dirty"
CLEAN = FIXTURES / "clean"

EXPECT_MARKER = "/* expect */"
SEVERITIES = ("P0", "P1", "P2", "P3")
TEXT_LINE = re.compile(r"^(?P<path>.+):(?P<line>\d+)  (?P<rule>[a-z0-9-]+)  (?P<sev>P[0-3])  (?P<msg>.+)$")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_interface_design_detect", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


detect = _load()


def _rule_ids() -> List[str]:
    return [rule.id for rule in detect.RULES]


def _run(args: Sequence[str], cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def _expected_lines(path: Path) -> List[int]:
    return [
        number
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if EXPECT_MARKER in line
    ]


def _lines_for(rule_id: str, path: Path) -> List[int]:
    return sorted({line for rid, line, _ in detect.scan_file(path) if rid == rule_id})


def _lines_in_text(rule_id: str, text: str, suffix: str, tmp_path: Path) -> List[int]:
    target = tmp_path / f"sample{suffix}"
    target.write_text(text, encoding="utf-8")
    return _lines_for(rule_id, target)


DIRTY_FILES = sorted(DIRTY.iterdir())


class TestRegistry:
    def test_exactly_the_twenty_pinned_ids(self) -> None:
        assert sorted(_rule_ids()) == sorted(
            [
                "focus-outline-removed", "a11y-click-on-div", "a11y-zoom-disabled",
                "a11y-img-no-alt", "a11y-positive-tabindex", "forms-placeholder-as-label",
                "forms-paste-blocked", "a11y-autofocus", "motion-transition-all",
                "motion-layout-property", "motion-no-reduced-motion", "type-tiny-text",
                "type-justified", "content-three-dots", "layout-z-index-escalation",
                "slop-gradient-text", "slop-hard-offset-shadow", "slop-glow-shadow",
                "intent-side-stripe", "intent-overused-font",
            ]
        )

    def test_rule_shape(self) -> None:
        assert len(set(_rule_ids())) == len(detect.RULES)
        for rule in detect.RULES:
            assert isinstance(rule.id, str) and rule.id
            assert rule.severity in SEVERITIES
            assert isinstance(rule.title, str) and rule.title
            assert callable(rule.check)
            assert rule.check("") == []

    def test_severities_match_the_table(self) -> None:
        by_id = {rule.id: rule.severity for rule in detect.RULES}
        assert by_id["focus-outline-removed"] == "P0"
        assert by_id["a11y-click-on-div"] == "P0"
        assert by_id["a11y-zoom-disabled"] == "P0"
        assert by_id["forms-paste-blocked"] == "P1"
        assert by_id["a11y-autofocus"] == "P2"
        assert by_id["type-justified"] == "P3"
        assert by_id["intent-side-stripe"] == "P3"

    def test_every_rule_has_one_dirty_fixture(self) -> None:
        stems = sorted(path.name.rsplit(".", 1)[0] for path in DIRTY_FILES)
        assert stems == sorted(_rule_ids())
        assert all(path.suffix in (".css", ".tsx") for path in DIRTY_FILES)

    def test_intent_messages_ask_for_a_reason(self) -> None:
        for rule in (r for r in detect.RULES if r.id.startswith("intent-")):
            fixture = next(p for p in DIRTY_FILES if p.name.startswith(rule.id))
            messages = [msg for rid, _, msg in detect.scan_file(fixture) if rid == rule.id]
            assert messages and all("justify or change" in msg for msg in messages)


@pytest.mark.parametrize("fixture", DIRTY_FILES, ids=lambda p: p.name)
def test_dirty_fixture_flags_exactly_the_marked_lines(fixture: Path) -> None:
    rule_id = fixture.name.rsplit(".", 1)[0]
    expected = _expected_lines(fixture)
    assert expected, f"{fixture.name} has no expect marker"
    assert _lines_for(rule_id, fixture) == expected


@pytest.mark.parametrize("fixture", DIRTY_FILES, ids=lambda p: p.name)
def test_dirty_fixture_exits_one_through_the_cli(fixture: Path) -> None:
    result = _run([str(fixture)])
    rule_id = fixture.name.rsplit(".", 1)[0]
    assert result.returncode == 1
    assert any(f"  {rule_id}  " in line for line in result.stdout.splitlines())


class TestCleanSet:
    def test_clean_set_is_a_css_file_and_two_tsx_files(self) -> None:
        suffixes = sorted(path.suffix for path in CLEAN.iterdir())
        assert suffixes == [".css", ".tsx", ".tsx"]

    def test_clean_set_has_no_findings(self) -> None:
        for path in sorted(CLEAN.iterdir()):
            assert detect.scan_file(path) == [], path.name

    def test_clean_directory_exits_zero_and_prints_nothing(self) -> None:
        result = _run([str(CLEAN.relative_to(REPO_ROOT))])
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""


class TestCli:
    def test_findings_exit_one_with_text_lines(self) -> None:
        result = _run(["tests/fixtures/interface-design/dirty/type-justified.css"])
        assert result.returncode == 1
        lines = result.stdout.splitlines()
        assert lines
        match = TEXT_LINE.match(lines[0])
        assert match, lines[0]
        assert match["path"] == "tests/fixtures/interface-design/dirty/type-justified.css"
        assert match["rule"] == "type-justified" and match["sev"] == "P3"

    def test_text_output_is_sorted_by_path_line_rule(self) -> None:
        result = _run([str(DIRTY.relative_to(REPO_ROOT))])
        keys: List[Tuple[str, int, str]] = []
        for line in result.stdout.splitlines():
            match = TEXT_LINE.match(line)
            assert match, line
            keys.append((match["path"], int(match["line"]), match["rule"]))
        assert keys == sorted(keys)
        assert {rule for _, _, rule in keys} >= set(_rule_ids())

    def test_json_format_shape(self) -> None:
        result = _run(["--format", "json", "tests/fixtures/interface-design/dirty/a11y-img-no-alt.tsx"])
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert set(payload) == {"findings", "scanned"}
        assert payload["scanned"] == 1
        assert payload["findings"]
        for finding in payload["findings"]:
            assert set(finding) == {"path", "line", "rule", "severity", "message"}
            assert isinstance(finding["path"], str)
            assert isinstance(finding["line"], int)
            assert finding["severity"] in SEVERITIES
            assert isinstance(finding["message"], str) and finding["message"]
        assert {f["rule"] for f in payload["findings"]} == {"a11y-img-no-alt"}

    def test_json_with_no_findings_exits_zero(self) -> None:
        result = _run(["--format", "json", str(CLEAN)])
        assert result.returncode == 0
        assert json.loads(result.stdout) == {"findings": [], "scanned": 3}

    def test_list_rules_lists_exactly_rules(self) -> None:
        result = _run(["--list-rules"])
        assert result.returncode == 0
        lines = result.stdout.splitlines()
        assert len(lines) == len(detect.RULES) == 20
        for line, rule in zip(lines, detect.RULES):
            assert line.split()[:2] == [rule.id, rule.severity]
            assert rule.title in line

    def test_missing_path_exits_two(self) -> None:
        result = _run(["no/such/path.css"])
        assert result.returncode == 2
        assert result.stderr.strip()
        assert result.stdout == ""

    def test_no_paths_exits_two(self) -> None:
        result = _run([])
        assert result.returncode == 2
        assert result.stderr.strip()

    def test_unknown_format_exits_two(self) -> None:
        assert _run(["--format", "xml", str(CLEAN)]).returncode == 2

    def test_unscanned_suffixes_are_ignored_silently(self, tmp_path: Path) -> None:
        (tmp_path / "notes.md").write_text("outline: none\n", encoding="utf-8")
        (tmp_path / "page.html").write_text("<img src='x'>\n", encoding="utf-8")
        result = _run(["--format", "json", str(tmp_path)])
        assert result.returncode == 0
        assert json.loads(result.stdout) == {"findings": [], "scanned": 0}

    def test_directory_walk_skips_vendored_and_build_dirs(self, tmp_path: Path) -> None:
        dirty = "a { outline: none; }\n"
        for skipped in ("node_modules", ".git", "dist", "build", ".next"):
            (tmp_path / skipped).mkdir()
            (tmp_path / skipped / "x.css").write_text(dirty, encoding="utf-8")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "kept.scss").write_text(dirty, encoding="utf-8")
        (tmp_path / "src" / "kept.jsx").write_text("<img src='a' />\n", encoding="utf-8")
        result = _run(["--format", "json", str(tmp_path)])
        payload = json.loads(result.stdout)
        assert payload["scanned"] == 2
        assert sorted(Path(f["path"]).name for f in payload["findings"]) == ["kept.jsx", "kept.scss"]

    def test_paths_print_relative_under_cwd_and_absolute_elsewhere(self, tmp_path: Path) -> None:
        inside = tmp_path / "a.css"
        inside.write_text("a { text-align: justify; }\n", encoding="utf-8")
        relative = _run(["a.css"], cwd=tmp_path)
        assert relative.stdout.startswith("a.css:1  type-justified")
        elsewhere = _run([str(inside)], cwd=REPO_ROOT)
        assert elsewhere.stdout.startswith(f"{inside.resolve()}:1  ") or elsewhere.stdout.startswith(f"{inside}:1  ")

    def test_a_file_named_twice_is_scanned_once(self) -> None:
        fixture = str(DIRTY / "type-justified.css")
        once = _run(["--format", "json", fixture])
        twice = _run(["--format", "json", fixture, fixture])
        assert json.loads(once.stdout) == json.loads(twice.stdout)


INLINE_CASES: List[Tuple[str, str, str, List[int]]] = [
    # (rule, suffix, text, expected lines)
    ("focus-outline-removed", ".scss", "a { color: red; // leave neutral\n  outline: none;\n}\n", [2]),
    ("focus-outline-removed", ".scss", "a { // note\n  outline: none;\n}\n", [2]),
    ("focus-outline-removed", ".scss", 'a { content: "x; // y";\n  outline: none;\n}\n', [2]),
    ("focus-outline-removed", ".scss", "a { color: red; // outline: none;\n}\n", []),
    ("focus-outline-removed", ".scss", 'a { content: "it\'s"; // label\n  outline: none;\n}\n', [2]),
    ("focus-outline-removed", ".scss", 'a { content: "x; // y"; // note\n  outline: none;\n}\n', [2]),
    ("a11y-img-no-alt", ".tsx", 'const x = <p>{name} // <img src="avatar.png" /></p>;\n', [1]),
    ("a11y-img-no-alt", ".tsx", 'const x = <nav>Home // Settings <img src="a.png" /></nav>;\n', [1]),
    ("a11y-img-no-alt", ".jsx", 'const x = <nav>Home // Settings <img src="a.png" /></nav>;\n', [1]),
    ("a11y-img-no-alt", ".tsx", 'const x = <p>Press ` to continue <img src="a.png" /></p>;\nconst s = `ok`;\n', [1]),
    ("a11y-img-no-alt", ".tsx", 'const x = <p>Press ` to continue <img src="a.png" /></p>;\nconst s = `<img src="b.png" />`;\n', [1]),
    ("motion-transition-all", ".scss", "a { color: red; // fade\n  transition: all 200ms;\n}\n", [2]),
    ("focus-outline-removed", ".tsx", '<button className="outline-none px-2">A</button>\n', [1]),
    ("focus-outline-removed", ".tsx", '<button className="outline-none focus-visible:ring-2">A</button>\n', []),
    ("focus-outline-removed", ".tsx", '<button className="focus:outline-none focus-visible:ring-2">A</button>\n', []),
    ("focus-outline-removed", ".tsx", '<button className="md:outline-none px-2">A</button>\n', [1]),
    ("focus-outline-removed", ".tsx", 'const a = cn("outline-none px-2");\n', [1]),
    ("focus-outline-removed", ".css", "a:focus { outline: none; }\na:focus-visible { outline: 2px solid red; }\n", []),
    ("focus-outline-removed", ".css", "a { outline: 0 }\n", [1]),
    ("focus-outline-removed", ".css", "a { outline: 2px solid red; }\n", []),
    ("focus-outline-removed", ".css", 'a { outline: none; content: ":focus-visible"; }\n', [1]),
    ("focus-outline-removed", ".css", "a { outline: none; &:focus-visible { outline: 2px solid red; } }\n", []),
    ("focus-outline-removed", ".css", "/* outline: none is banned */\na { color: red; }\n", []),
    ("focus-outline-removed", ".css", ".x { @apply outline-none; }\n", [1]),
    ("a11y-click-on-div", ".tsx", "<div\n  className='x'\n  onClick={() => go()}\n>t</div>\n", [3]),
    ("a11y-click-on-div", ".tsx", "<div onClick={() => go()} role='button'>t</div>\n", []),
    ("a11y-click-on-div", ".tsx", "<divider onClick={go} />\n", []),
    ("a11y-click-on-div", ".tsx", "<a onClick={go}>t</a>\n", []),
    ("a11y-zoom-disabled", ".tsx", '<meta content="user-scalable=no" />\n', [1]),
    ("a11y-zoom-disabled", ".tsx", '<meta content="maximum-scale=1" />\n', [1]),
    ("a11y-zoom-disabled", ".tsx", '<meta content="maximum-scale=1.0" />\n', [1]),
    ("a11y-zoom-disabled", ".tsx", '<meta content="maximum-scale=1.5" />\n', []),
    ("a11y-zoom-disabled", ".tsx", '<meta content="maximum-scale=10" />\n', []),
    ("a11y-zoom-disabled", ".tsx", '<meta content="user-scalable=yes" />\n', []),
    ("a11y-img-no-alt", ".tsx", '<img\n  src="a.png"\n/>\n', [1]),
    ("a11y-img-no-alt", ".tsx", '<img src="a.png" alt="" />\n', []),
    ("a11y-img-no-alt", ".tsx", '<img src="alt.png" className="alt" />\n', [1]),
    ("a11y-img-no-alt", ".tsx", '<imgx src="a.png" />\n', []),
    ("a11y-img-no-alt", ".tsx", 'const documentation = "<img src=x>";\n', []),
    ("a11y-img-no-alt", ".tsx", "const documentation = '<img src=x>';\n", []),
    ("a11y-img-no-alt", ".tsx", "<p>Don't <img src=\"a.png\" /> it's</p>\n", [1]),
    ("a11y-img-no-alt", ".tsx", 'const documentation = `<img src="avatar.png">`;\n', []),
    ("a11y-img-no-alt", ".tsx", 'const documentation = `\n  <img src="a.png">\n`;\n<img src="b.png" />\n', [4]),
    ("a11y-img-no-alt", ".tsx", 'const x = `before ${<img src="a.png" />} after`;\n', [1]),
    ("a11y-img-no-alt", ".tsx", 'const x = `a ${cond ? `<img src="a.png">` : ""} b`;\n', []),
    ("a11y-img-no-alt", ".tsx", 'const x = `unterminated\n<img src="a.png" />\n', [2]),
    ("a11y-click-on-div", ".tsx", 'const html = "<div onClick={go}>";\n', []),
    ("a11y-positive-tabindex", ".tsx", "<div tabindex='1'></div>\n", [1]),
    ("a11y-positive-tabindex", ".tsx", "<div tabIndex={10}></div>\n", [1]),
    ("a11y-positive-tabindex", ".tsx", "<div tabIndex={0}></div>\n", []),
    ("a11y-positive-tabindex", ".tsx", "<div tabIndex={-1}></div>\n", []),
    ("forms-placeholder-as-label", ".tsx", '<input placeholder="Name" />\n', [1]),
    ("forms-placeholder-as-label", ".tsx", '<input placeholder="Name" aria-labelledby="n" />\n', []),
    ("forms-placeholder-as-label", ".tsx", '<input\n  type="text"\n  placeholder="Name"\n/>\n', [3]),
    ("forms-placeholder-as-label", ".tsx", '<input placeholder="Name" id="n" />\n', []),
    ("forms-placeholder-as-label", ".tsx", '<select placeholder="Name"></select>\n', []),
    ("forms-paste-blocked", ".tsx", "<input onPaste={(e) => { e.preventDefault(); }} />\n", [1]),
    ("forms-paste-blocked", ".tsx", "<input onPaste={logPaste} />\n", []),
    ("forms-paste-blocked", ".tsx", "<input onPaste={handlePaste} onClick={(e) => e.preventDefault()} />\n", []),
    ("forms-paste-blocked", ".tsx", "<input onClick={(e) => e.preventDefault()} onPaste={logPaste} />\n", []),
    ("forms-paste-blocked", ".tsx", "<input onPaste={(e) => {\n  e.preventDefault();\n}} />\n", [1]),
    ("a11y-autofocus", ".tsx", "<input autoFocus />\n", [1]),
    ("a11y-autofocus", ".tsx", "<input autoFocus={true} />\n", [1]),
    ("a11y-autofocus", ".tsx", "<input id='a' />\n", []),
    ("motion-transition-all", ".tsx", '<div className="transition-all duration-200">x</div>\n', [1]),
    ("motion-transition-all", ".tsx", '<div className="transition-colors duration-200">x</div>\n', []),
    ("motion-transition-all", ".css", "a { transition: opacity 1s, all 2s; }\n", [1]),
    ("motion-transition-all", ".css", "a { transition: none; }\n", []),
    ("motion-layout-property", ".tsx", '<div className="transition-[height] duration-200">x</div>\n', [1]),
    ("motion-layout-property", ".tsx", '<div className="transition-[opacity,margin-top]">x</div>\n', [1]),
    ("motion-layout-property", ".tsx", '<div className="transition-[opacity]">x</div>\n', []),
    ("motion-layout-property", ".css", "a { animation: slide 1s; }\n", []),
    ("motion-layout-property", ".css", "a { animation: width 1s; }\n", [1]),
    ("motion-layout-property", ".css", "a { transition: padding 1s; }\n", [1]),
    ("motion-layout-property", ".css", "a { transition: top .2s, bottom .2s; }\n", [1]),
    ("motion-no-reduced-motion", ".css", "a { color: red; }\n", []),
    ("motion-no-reduced-motion", ".css", "a { color: red; }\n\n@keyframes x { to { opacity: 1; } }\n", [3]),
    ("motion-no-reduced-motion", ".css", "a { color: red; animation: x 1s; }\n@keyframes x { to { opacity: 1; } }\n", [1]),
    ("motion-no-reduced-motion", ".css", "@keyframes x { to { opacity: 1; } }\n@media (prefers-reduced-motion: reduce) { a { animation: none; } }\n", []),
    ("type-tiny-text", ".css", "a { font-size: 11px; }\n", [1]),
    ("type-tiny-text", ".css", "a { font-size: 11.5px; }\n", [1]),
    ("type-tiny-text", ".css", "a { font-size: 12px; }\n", []),
    ("type-tiny-text", ".css", "a { font-size: 0.7rem; }\n", [1]),
    ("type-tiny-text", ".css", "a { font-size: 0.75rem; }\n", []),
    ("type-tiny-text", ".css", "a { font-size: 0.7em; }\n", [1]),
    ("type-tiny-text", ".css", "a { font-size: var(--small); }\n", []),
    ("type-tiny-text", ".css", "a { font-size: 0; }\n", []),
    ("type-tiny-text", ".tsx", '<p className="text-[10px] uppercase">x</p>\n', [1]),
    ("type-tiny-text", ".tsx", '<p className="md:text-[11px]">x</p>\n', [1]),
    ("type-tiny-text", ".tsx", '<p className="text-[12px]">x</p>\n', []),
    ("type-tiny-text", ".tsx", '<p className="text-xs">x</p>\n', []),
    ("type-justified", ".tsx", '<p className="text-justify">x</p>\n', [1]),
    ("type-justified", ".tsx", '<p className="text-left">x</p>\n', []),
    ("type-justified", ".css", "p { text-align: justify; }\n", [1]),
    ("content-three-dots", ".tsx", "const a = 'Saving...';\n", [1]),
    ("content-three-dots", ".tsx", "const a = `Saving${n}...`;\n", [1]),
    ("content-three-dots", ".tsx", "const a = [...items, ...more];\nf(...args);\n", []),
    ("content-three-dots", ".tsx", "const a = <p>\n  Saving...\n</p>;\n", [2]),
    ("content-three-dots", ".tsx", "const a = <p {...rest}>Saved</p>;\n", []),
    ("content-three-dots", ".tsx", "const a = \"Don't wait... it's fine\";\n", []),
    ("content-three-dots", ".tsx", "const [s, setS] = useState<string>(...initial);\n", []),
    ("content-three-dots", ".tsx", 'const x = <p>{busy ? "Saving" : "Done"} Loading...</p>;\n', [1]),
    ("content-three-dots", ".tsx", "const x = <p>{a}{b}\n  Loading...</p>;\n", [2]),
    ("content-three-dots", ".tsx", "const x = <div><section><p>\n  Loading...</p></section></div>;\n", [2]),
    ("content-three-dots", ".tsx", "const x = <div>{ok && <p>\n  Loading...</p>}\n</div>;\n", [2]),
    ("content-three-dots", ".tsx", "const x = <>\n  <p>a</p>\n  <p>\n    Loading...</p>\n</>;\n", [4]),
    ("content-three-dots", ".tsx", "const x = <p><b>{n}</b> Loading...</p>;\n", [1]),
    ("content-three-dots", ".tsx", "const x = <><b>a</b> Wait...</>;\n", [1]),
    ("content-three-dots", ".tsx", "const out = <p>Hi</p>;\nconst next = [...items];\n", []),
    ("content-three-dots", ".tsx", "const out = <p>{a}</p>;\nconst opts = [...rest];\nf(...args);\n", []),
    ("content-three-dots", ".tsx", "const out = <p><b>Hi</b></p>;\nconst opts = [...rest];\n", []),
    ("content-three-dots", ".css", 'a::after { content: "More..."; }\n', [1]),
    ("layout-z-index-escalation", ".css", "a { z-index: 999; }\n", [1]),
    ("layout-z-index-escalation", ".css", "a { z-index: 998; }\n", []),
    ("layout-z-index-escalation", ".css", "a { z-index: 2147483647; }\n", [1]),
    ("layout-z-index-escalation", ".css", "a { z-index: var(--z-modal); }\n", []),
    ("layout-z-index-escalation", ".tsx", '<div className="z-[9999]">x</div>\n', [1]),
    ("layout-z-index-escalation", ".tsx", '<div className="z-[50]">x</div>\n', []),
    ("slop-gradient-text", ".css", "h1 { background: linear-gradient(red, blue); -webkit-background-clip: text; }\n", [1]),
    ("slop-gradient-text", ".css", "h1 { background-image: linear-gradient(red, blue);\n  background-clip: text;\n}\n", [2]),
    ("slop-gradient-text", ".css", "h1 { background: #fff; background-clip: text; }\n", []),
    ("slop-gradient-text", ".css", "h1 { background: linear-gradient(red, blue); }\n", []),
    ("slop-gradient-text", ".tsx", '<h1 className="bg-clip-text bg-linear-to-r from-a to-b">x</h1>\n', [1]),
    ("slop-gradient-text", ".tsx", '<h1 className="bg-clip-text text-black">x</h1>\n', []),
    ("slop-hard-offset-shadow", ".css", "a { box-shadow: 4px 4px 0 #000; }\n", [1]),
    ("slop-hard-offset-shadow", ".css", "a { box-shadow: 0 0 0 1px #000; }\n", []),
    ("slop-hard-offset-shadow", ".css", "a { box-shadow: 0 1px 0 #000; }\n", []),
    ("slop-hard-offset-shadow", ".css", "a { box-shadow: 0 1px 2px #000, 3px 3px 0 #111; }\n", [1]),
    ("slop-hard-offset-shadow", ".tsx", '<div className="shadow-[4px_4px_0_#000]">x</div>\n', [1]),
    ("slop-hard-offset-shadow", ".tsx", '<div className="shadow-[4px_4px_8px_#000]">x</div>\n', []),
    ("slop-glow-shadow", ".css", "a { box-shadow: 0 0 16px #6366f1; }\n", [1]),
    ("slop-glow-shadow", ".css", "a { box-shadow: 0 0 15px #6366f1; }\n", []),
    ("slop-glow-shadow", ".css", "a { box-shadow: 0 0 30px rgb(255, 255, 255); }\n", []),
    ("slop-glow-shadow", ".css", "a { box-shadow: 0 0 30px #888; }\n", []),
    ("slop-glow-shadow", ".css", "a { box-shadow: 0 0 30px hsl(220 80% 60%); }\n", [1]),
    ("slop-glow-shadow", ".css", "a { box-shadow: 0 0 30px hsl(0 0% 50%); }\n", []),
    ("slop-glow-shadow", ".css", "a { box-shadow: 0 0 1rem rgba(10, 200, 30, .4); }\n", [1]),
    ("slop-glow-shadow", ".css", "a { box-shadow: 0 4px 24px rgba(10, 200, 30, .4); }\n", []),
    ("slop-glow-shadow", ".tsx", '<div className="shadow-[0_0_20px_rgba(59,130,246,0.5)]">x</div>\n', [1]),
    ("slop-glow-shadow", ".tsx", '<div className="shadow-[0_0_20px_rgba(0,0,0,0.5)]">x</div>\n', []),
    ("intent-side-stripe", ".css", "a { border-left: 2px solid red; border-radius: 4px; }\n", [1]),
    ("intent-side-stripe", ".css", "a { border-left: 8px solid red; border-radius: 4px; }\n", [1]),
    ("intent-side-stripe", ".css", "a { border-left: 9px solid red; border-radius: 4px; }\n", []),
    ("intent-side-stripe", ".css", "a { border-left: 4px solid red; }\n", []),
    ("intent-side-stripe", ".css", "a { border-left: 1px solid red; border-radius: 4px; }\n", []),
    ("intent-side-stripe", ".css", "a { border-left: 4px dashed red; border-radius: 4px; }\n", []),
    ("intent-side-stripe", ".tsx", '<div className="border-l-4 border-red-500 rounded-md p-3">x</div>\n', [1]),
    ("intent-side-stripe", ".tsx", '<div className="md:border-l-[3px] rounded p-3">x</div>\n', [1]),
    ("intent-side-stripe", ".tsx", '<div className="border-l-4 border-red-500 p-3">x</div>\n', []),
    ("intent-side-stripe", ".tsx", '<div className="border-l rounded p-3">x</div>\n', []),
    ("intent-overused-font", ".css", "a { font-family: 'Inter', sans-serif; }\n", [1]),
    ("intent-overused-font", ".css", 'a { font-family: "Geist", sans-serif; }\n', [1]),
    ("intent-overused-font", ".css", "a { font-family: roboto, sans-serif; }\n", [1]),
    ("intent-overused-font", ".css", "a { font-family: system-ui, Inter, sans-serif; }\n", []),
    ("intent-overused-font", ".css", 'a { font-family: "IBM Plex Sans", Inter; }\n', []),
    ("intent-overused-font", ".tsx", "<p className=\"font-['Inter',sans-serif]\">x</p>\n", [1]),
    ("intent-overused-font", ".tsx", '<p className="font-[Arial]">x</p>\n', [1]),
    ("intent-overused-font", ".tsx", '<p className="font-[600]">x</p>\n', []),
    ("intent-overused-font", ".tsx", '<p className="font-semibold">x</p>\n', []),
]


@pytest.mark.parametrize(
    "rule_id,suffix,text,expected",
    INLINE_CASES,
    ids=[f"{case[0]}-{index}" for index, case in enumerate(INLINE_CASES)],
)
def test_inline_forms_and_near_misses(
    rule_id: str, suffix: str, text: str, expected: List[int], tmp_path: Path
) -> None:
    assert _lines_in_text(rule_id, text, suffix, tmp_path) == expected


def test_every_rule_has_an_inline_case_that_fires() -> None:
    fired = {case[0] for case in INLINE_CASES if case[3]}
    assert fired == set(_rule_ids())


class TestRobustness:
    @pytest.mark.parametrize("depth", [100, 600, 5000])
    def test_deeply_nested_templates_do_not_crash(self, depth: int, tmp_path: Path) -> None:
        text = "const c = cn(" + "`x${" * depth + '"outline-none"' + "}`" * depth + ");\n"
        assert detect.scan_text(text) is not None
        target = tmp_path / "deep.tsx"
        target.write_text(text, encoding="utf-8")
        result = _run([str(target)])
        assert result.returncode in (0, 1)
        assert "Traceback" not in result.stderr

    @pytest.mark.parametrize("depth", [4000, 20000])
    def test_deeply_nested_jsx_scans_in_linear_time(self, depth: int) -> None:
        text = "const x = " + "<div>" * depth + "wait..." + "</div>" * depth + ";\n"
        start = time.perf_counter()
        results = detect.scan_text(text)
        assert time.perf_counter() - start < 5
        assert [(r.id, line) for r, line, _ in results] == [("content-three-dots", 1)]

    def test_shallow_nested_template_still_finds_class_strings(self) -> None:
        text = 'const c = cn(`a ${cond ? `b ${"outline-none"}` : ""}`);\n'
        assert [r.id for r, _, _ in detect.scan_text(text)] == ["focus-outline-removed"]

    def test_unreadable_directory_exits_two_with_a_stderr_message(self, tmp_path: Path) -> None:
        locked = tmp_path / "locked"
        locked.mkdir()
        (locked / "a.css").write_text("a { text-align: justify; }\n", encoding="utf-8")
        (tmp_path / "ok.css").write_text("a { color: red; }\n", encoding="utf-8")
        locked.chmod(0)
        try:
            if os.access(locked, os.R_OK):
                pytest.skip("directory permissions are not enforced for this user")
            result = _run([str(tmp_path)])
        finally:
            locked.chmod(0o755)
        assert result.returncode == 2
        assert "locked" in result.stderr
        assert "Traceback" not in result.stderr

    def test_walk_error_is_raised_not_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def denied(*args: object, **kwargs: object) -> None:
            raise PermissionError("denied")

        monkeypatch.setattr(detect.os, "scandir", denied)
        with pytest.raises(OSError):
            detect.collect_files([str(tmp_path)])


class TestChangedSince:
    DIRTY_A = "a { text-align: justify; }\n"
    DIRTY_B = "b { text-align: justify; }\n"
    CLEAN_LINE = "c { color: red; }\n"

    @staticmethod
    def _git(repo: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
            cwd=str(repo),
            check=True,
            capture_output=True,
        )

    @pytest.fixture()
    def repo(self, tmp_path: Path) -> Path:
        self._git(tmp_path, "init", "-q", "-b", "main")
        (tmp_path / "ui.css").write_text(self.DIRTY_A + self.CLEAN_LINE + self.DIRTY_B, encoding="utf-8")
        (tmp_path / "anim.css").write_text(
            "a { color: red; }\n@keyframes x { to { opacity: 1; } }\n", encoding="utf-8"
        )
        self._git(tmp_path, "add", "-A")
        self._git(tmp_path, "commit", "-q", "-m", "base")
        return tmp_path

    def _findings(self, repo: Path, *args: str) -> List[Tuple[str, int, str]]:
        result = _run(["--format", "json", *args], cwd=repo)
        assert result.returncode in (0, 1), result.stderr
        payload = json.loads(result.stdout)
        return sorted((f["path"], f["line"], f["rule"]) for f in payload["findings"])

    def test_no_changes_reports_nothing(self, repo: Path) -> None:
        assert self._findings(repo, "--changed-since", "HEAD", ".") == []
        assert _run(["--changed-since", "HEAD", "."], cwd=repo).returncode == 0

    def test_only_added_or_modified_lines_are_reported(self, repo: Path) -> None:
        (repo / "ui.css").write_text(
            self.DIRTY_A + self.CLEAN_LINE + self.DIRTY_B + "d { text-align: justify; }\n", encoding="utf-8"
        )
        assert self._findings(repo, "--changed-since", "HEAD", ".") == [("ui.css", 4, "type-justified")]
        assert len(self._findings(repo, ".")) == 4

    def test_modified_line_counts(self, repo: Path) -> None:
        (repo / "ui.css").write_text(
            self.DIRTY_A + "c { text-align: justify; }\n" + self.DIRTY_B, encoding="utf-8"
        )
        assert self._findings(repo, "--changed-since", "HEAD", "ui.css") == [("ui.css", 2, "type-justified")]

    def test_pure_deletion_changes_no_line(self, repo: Path) -> None:
        (repo / "ui.css").write_text(self.DIRTY_A + self.DIRTY_B, encoding="utf-8")
        assert self._findings(repo, "--changed-since", "HEAD", "ui.css") == []

    def test_untracked_files_count_as_wholly_changed(self, repo: Path) -> None:
        (repo / "new.css").write_text(self.DIRTY_A + self.DIRTY_B, encoding="utf-8")
        assert self._findings(repo, "--changed-since", "HEAD", "new.css") == [
            ("new.css", 1, "type-justified"),
            ("new.css", 2, "type-justified"),
        ]

    def test_committed_changes_since_an_older_ref(self, repo: Path) -> None:
        (repo / "ui.css").write_text(
            self.DIRTY_A + self.CLEAN_LINE + self.DIRTY_B + "d { text-align: justify; }\n", encoding="utf-8"
        )
        self._git(repo, "commit", "-q", "-am", "more")
        assert self._findings(repo, "--changed-since", "HEAD", ".") == []
        assert self._findings(repo, "--changed-since", "HEAD~1", ".") == [("ui.css", 4, "type-justified")]

    def test_file_level_rule_needs_a_changed_line_in_the_file(self, repo: Path) -> None:
        assert self._findings(repo, "--changed-since", "HEAD", "anim.css") == []
        assert [f[2] for f in self._findings(repo, "anim.css")] == ["motion-no-reduced-motion"]
        (repo / "anim.css").write_text(
            "a { color: blue; }\n@keyframes x { to { opacity: 1; } }\n", encoding="utf-8"
        )
        assert self._findings(repo, "--changed-since", "HEAD", "anim.css") == [
            ("anim.css", 2, "motion-no-reduced-motion")
        ]

    def test_file_level_rule_ignores_a_pure_deletion(self, repo: Path) -> None:
        (repo / "anim.css").write_text("@keyframes x { to { opacity: 1; } }\n", encoding="utf-8")
        assert self._findings(repo, "--changed-since", "HEAD", "anim.css") == []

    def test_absolute_paths_work(self, repo: Path) -> None:
        (repo / "ui.css").write_text(
            self.DIRTY_A + self.CLEAN_LINE + self.DIRTY_B + "d { text-align: justify; }\n", encoding="utf-8"
        )
        result = _run(["--format", "json", "--changed-since", "HEAD", str(repo / "ui.css")], cwd=repo)
        payload = json.loads(result.stdout)
        assert [f["line"] for f in payload["findings"]] == [4]

    def test_unknown_ref_exits_two(self, repo: Path) -> None:
        result = _run(["--changed-since", "no-such-ref", "."], cwd=repo)
        assert result.returncode == 2
        assert result.stderr.strip()

    def test_option_shaped_ref_exits_two(self, repo: Path) -> None:
        assert _run(["--changed-since=--output=x", "."], cwd=repo).returncode == 2

    def test_outside_a_repo_exits_two(self, tmp_path: Path) -> None:
        (tmp_path / "a.css").write_text(self.DIRTY_A, encoding="utf-8")
        result = _run(["--changed-since", "HEAD", "a.css"], cwd=tmp_path)
        assert result.returncode == 2
        assert result.stderr.strip()
