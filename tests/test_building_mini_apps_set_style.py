"""Scaffold-with-a-style and style-swap checks: usage errors, style_step and tokens_step. No network."""

from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "building-mini-apps"
SCRIPTS_DIR = SKILL_DIR / "scripts"

SLUGS = ("neutral-house", "calm-paper", "airy-white", "cool-tool",
         "dense-dark", "glass-launcher", "split-tone", "ink-panel")

HEADER_PREFIX = "/* mini-style: "

INDEX_CSS = """\
@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";

@custom-variant dark (&:is(.dark *));

@theme inline {
  --font-heading: var(--font-sans);
  --font-sans: 'Geist Variable', sans-serif;
  --color-background: var(--background);
}

:root {
  --background: oklch(1 0 0);
}
"""


def _scripts_on_path() -> None:
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))


def _load_script(name: str) -> ModuleType:
    _scripts_on_path()
    spec = importlib.util.spec_from_file_location(f"_bma_{name}", SCRIPTS_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mini() -> ModuleType:
    _scripts_on_path()
    return importlib.import_module("_mini")


@pytest.fixture
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> List[str]:
    """Make any subprocess launch fail the test; returns the list of attempted commands."""
    attempts: List[str] = []

    def _forbidden(*args: Any, **kwargs: Any) -> Any:
        attempts.append(str(args[0] if args else kwargs.get("args")))
        raise AssertionError(f"subprocess launched: {attempts[-1]}")

    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    return attempts


@pytest.fixture
def recorded_steps(monkeypatch: pytest.MonkeyPatch) -> List[Tuple[str, Any]]:
    """Replace every step function with a recorder, so a run touches no pnpm."""
    mini = _mini()
    calls: List[Tuple[str, Any]] = []
    monkeypatch.setattr(mini, "style_step", lambda app, slug: calls.append(("style", slug)) or 0)
    monkeypatch.setattr(mini, "tokens_step", lambda app: calls.append(("tokens", None)) or 0)
    monkeypatch.setattr(mini, "press_step", lambda app: calls.append(("press", None)) or 0)
    monkeypatch.setattr(mini, "build_step", lambda app: calls.append(("build", None)) or 0)
    monkeypatch.setattr(mini, "dev_step", lambda app: calls.append(("dev", None)) or 0)
    return calls


def _make_app(tmp_path: Path, tokens: str = "") -> Path:
    """An app directory with components.json and, when `tokens` is given, a tokens file."""
    app = tmp_path / "app"
    (app / "src" / "styles").mkdir(parents=True)
    (app / "components.json").write_text("{}")
    if tokens:
        (app / "src" / "styles" / "mini-tokens.css").write_text(tokens)
    return app


def _real_tokens() -> str:
    return (SKILL_DIR / "styles" / "dist" / "neutral-house.css").read_text(encoding="utf-8")


# --- new_app.py --style ---


def test_new_app_exits_2_on_unknown_style_listing_every_slug(
    tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    new_app = _load_script("new_app")
    target = tmp_path / "app"
    assert new_app.main([str(target), "--style", "no-such-style"]) == 2
    err = capsys.readouterr().err
    assert "no-such-style" in err
    assert all(slug in err for slug in SLUGS)
    assert not target.exists()
    assert no_subprocess == []


def test_new_app_runs_the_steps_in_order_and_reports_the_style(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    new_app = _load_script("new_app")
    mini = _mini()
    calls: List[Tuple[str, Any]] = []
    monkeypatch.setattr(new_app, "init_step", lambda app: calls.append(("init", None)) or 0)
    monkeypatch.setattr(mini, "add_step", lambda app, patterns: calls.append(("add", None)) or 0)
    monkeypatch.setattr(mini, "style_step", lambda app, slug: calls.append(("style", slug)) or 0)
    monkeypatch.setattr(mini, "tokens_step", lambda app: calls.append(("tokens", None)) or 0)
    monkeypatch.setattr(mini, "press_step", lambda app: calls.append(("press", None)) or 0)
    monkeypatch.setattr(mini, "build_step", lambda app: calls.append(("build", None)) or 0)
    monkeypatch.setattr(mini, "dev_step", lambda app: calls.append(("dev", None)) or 0)
    target = tmp_path / "app"
    assert new_app.main([str(target), "--style", "calm-paper"]) == 0
    assert [name for name, _ in calls] == ["init", "add", "style", "tokens", "press", "build", "dev"]
    assert ("style", "calm-paper") in calls
    assert "style: calm-paper" in capsys.readouterr().out


def test_new_app_style_defaults_to_neutral_house(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    new_app = _load_script("new_app")
    mini = _mini()
    seen: List[str] = []
    monkeypatch.setattr(new_app, "init_step", lambda app: 0)
    monkeypatch.setattr(mini, "add_step", lambda app, patterns: 0)
    monkeypatch.setattr(mini, "style_step", lambda app, slug: seen.append(slug) or 0)
    monkeypatch.setattr(mini, "tokens_step", lambda app: 0)
    monkeypatch.setattr(mini, "press_step", lambda app: 0)
    monkeypatch.setattr(mini, "build_step", lambda app: 0)
    monkeypatch.setattr(mini, "dev_step", lambda app: 0)
    assert new_app.main([str(tmp_path / "app")]) == 0
    assert seen == ["neutral-house"]
    assert "style: neutral-house" in capsys.readouterr().out


def test_new_app_keeps_tokens_step_importable() -> None:
    assert _load_script("new_app").tokens_step is _mini().tokens_step


# --- set_style.py usage errors ---


def test_set_style_exits_2_without_components_json(
    tmp_path: Path, no_subprocess: List[str]
) -> None:
    set_style = _load_script("set_style")
    assert set_style.main([str(tmp_path), "calm-paper"]) == 2
    assert no_subprocess == []


def test_set_style_exits_2_on_unknown_slug_listing_every_slug(
    tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    set_style = _load_script("set_style")
    app = _make_app(tmp_path, _real_tokens())
    assert set_style.main([str(app), "no-such-style"]) == 2
    err = capsys.readouterr().err
    assert "no-such-style" in err
    assert all(slug in err for slug in SLUGS)
    assert no_subprocess == []


def test_set_style_exits_2_when_the_tokens_file_is_missing(
    tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    set_style = _load_script("set_style")
    app = _make_app(tmp_path)
    assert set_style.main([str(app), "calm-paper"]) == 2
    assert "mini-tokens.css" in capsys.readouterr().err
    assert no_subprocess == []


def test_set_style_exits_2_on_a_tokens_file_without_a_header(
    tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    set_style = _load_script("set_style")
    app = _make_app(tmp_path, "html:root { --background: red; }\n")
    assert set_style.main([str(app), "calm-paper"]) == 2
    err = capsys.readouterr().err
    assert "mini-tokens.css" in err
    assert "--force" in err
    assert no_subprocess == []


def test_set_style_exits_2_on_a_header_whose_hash_no_longer_matches(
    tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    set_style = _load_script("set_style")
    edited = _real_tokens().replace("--radius: 0.5rem;", "--radius: 1rem;")
    assert edited.startswith(HEADER_PREFIX) and edited != _real_tokens()
    app = _make_app(tmp_path, edited)
    assert set_style.main([str(app), "calm-paper"]) == 2
    err = capsys.readouterr().err
    assert "mini-tokens.css" in err
    assert "--force" in err
    assert no_subprocess == []


def test_set_style_accepts_an_untouched_generated_file(
    tmp_path: Path, recorded_steps: List[Tuple[str, Any]], capsys: pytest.CaptureFixture
) -> None:
    set_style = _load_script("set_style")
    app = _make_app(tmp_path, _real_tokens())
    assert set_style.main([str(app), "calm-paper"]) == 0
    assert [name for name, _ in recorded_steps] == ["style", "tokens", "press", "build", "dev"]
    out = capsys.readouterr().out
    assert f"app: {app}" in out
    assert "style: calm-paper" in out


@pytest.mark.parametrize("tokens", ["html:root { --background: red; }\n", None])
def test_set_style_force_skips_the_hand_edit_check(
    tmp_path: Path, recorded_steps: List[Tuple[str, Any]], tokens: Any
) -> None:
    set_style = _load_script("set_style")
    if tokens is None:
        tokens = _real_tokens().replace("--radius: 0.5rem;", "--radius: 1rem;")
    app = _make_app(tmp_path, tokens)
    assert set_style.main([str(app), "calm-paper", "--force"]) == 0
    assert recorded_steps[0] == ("style", "calm-paper")
    assert [name for name, _ in recorded_steps] == ["style", "tokens", "press", "build", "dev"]


def test_set_style_still_requires_the_tokens_file_with_force(
    tmp_path: Path, recorded_steps: List[Tuple[str, Any]]
) -> None:
    set_style = _load_script("set_style")
    app = _make_app(tmp_path)
    assert set_style.main([str(app), "calm-paper", "--force"]) == 2
    assert recorded_steps == []


# --- style_step ---


@pytest.fixture
def style_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A styles dir holding one source and one dist file for `calm-paper`, with two font packages."""
    mini = _mini()
    styles = tmp_path / "styles"
    (styles / "dist").mkdir(parents=True)
    source: Dict[str, Any] = json.loads(
        (SKILL_DIR / "styles" / "neutral-house.json").read_text(encoding="utf-8")
    )
    source["slug"] = "calm-paper"
    source["font_packages"] = ["@fontsource-variable/inter", "@fontsource/lora"]
    (styles / "calm-paper.json").write_text(json.dumps(source), encoding="utf-8")
    (styles / "dist" / "calm-paper.css").write_bytes(b"/* dist bytes */\r\nhtml:root {}\n")
    monkeypatch.setattr(mini, "STYLES_DIR", styles)
    return styles


def _record_run_step(monkeypatch: pytest.MonkeyPatch) -> List[Tuple[str, List[str], Path]]:
    runs: List[Tuple[str, List[str], Path]] = []
    monkeypatch.setattr(
        _mini(), "run_step", lambda name, cmd, cwd: runs.append((name, cmd, cwd)) or 0
    )
    return runs


def test_style_step_writes_the_dist_bytes_and_adds_every_missing_package(
    tmp_path: Path, style_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = _record_run_step(monkeypatch)
    app = tmp_path / "app"
    app.mkdir()
    (app / "package.json").write_text(json.dumps({"dependencies": {"react": "^19"}}))
    assert _mini().style_step(app, "calm-paper") == 0
    written = (app / "src" / "styles" / "mini-tokens.css").read_bytes()
    assert written == (style_tree / "dist" / "calm-paper.css").read_bytes()
    assert runs == [(
        "style", ["pnpm", "add", "@fontsource-variable/inter", "@fontsource/lora"], app
    )]


def test_style_step_skips_packages_already_in_package_json(
    tmp_path: Path, style_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = _record_run_step(monkeypatch)
    app = tmp_path / "app"
    app.mkdir()
    (app / "package.json").write_text(
        json.dumps({"dependencies": {"@fontsource-variable/inter": "^5"}})
    )
    assert _mini().style_step(app, "calm-paper") == 0
    assert runs == [("style", ["pnpm", "add", "@fontsource/lora"], app)]


def test_style_step_runs_no_command_when_every_package_is_present(
    tmp_path: Path, style_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = _record_run_step(monkeypatch)
    app = tmp_path / "app"
    app.mkdir()
    deps = {"@fontsource-variable/inter": "^5", "@fontsource/lora": "^5", "left-over": "1"}
    (app / "package.json").write_text(json.dumps({"dependencies": deps}))
    assert _mini().style_step(app, "calm-paper") == 0
    assert runs == []
    assert (app / "src" / "styles" / "mini-tokens.css").is_file()


def test_style_step_returns_the_failure_code_of_pnpm_add(
    tmp_path: Path, style_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_mini(), "run_step", lambda name, cmd, cwd: 1)
    app = tmp_path / "app"
    app.mkdir()
    (app / "package.json").write_text("{}")
    assert _mini().style_step(app, "calm-paper") == 1


# --- tokens_step ---


def _index_css(app: Path) -> Path:
    return app / "src" / "index.css"


def _tokens_app(tmp_path: Path, css: str) -> Path:
    app = tmp_path / "app"
    (app / "src").mkdir(parents=True)
    _index_css(app).write_text(css, encoding="utf-8")
    return app


def test_tokens_step_wires_the_import_and_rewires_both_font_lines(tmp_path: Path) -> None:
    app = _tokens_app(tmp_path, INDEX_CSS)
    assert _mini().tokens_step(app) == 0
    text = _index_css(app).read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[lines.index('@import "shadcn/tailwind.css";') + 1] == '@import "./styles/mini-tokens.css";'
    assert "  --font-sans: var(--mini-font-sans);" in lines
    assert "  --font-heading: var(--mini-font-heading);" in lines
    assert "Geist Variable" not in text
    assert "  --color-background: var(--background);" in lines


def test_tokens_step_is_idempotent(tmp_path: Path) -> None:
    app = _tokens_app(tmp_path, INDEX_CSS)
    assert _mini().tokens_step(app) == 0
    once = _index_css(app).read_text(encoding="utf-8")
    assert _mini().tokens_step(app) == 0
    assert _index_css(app).read_text(encoding="utf-8") == once
    assert once.count("styles/mini-tokens.css") == 1
    assert once.count("--font-sans:") == 1
    assert once.count("--font-heading:") == 1


def test_tokens_step_adds_missing_font_lines_inside_the_block(tmp_path: Path) -> None:
    css = INDEX_CSS.replace("  --font-heading: var(--font-sans);\n", "").replace(
        "  --font-sans: 'Geist Variable', sans-serif;\n", ""
    )
    app = _tokens_app(tmp_path, css)
    assert _mini().tokens_step(app) == 0
    text = _index_css(app).read_text(encoding="utf-8")
    block = text[text.index("@theme inline"):text.index("}", text.index("@theme inline"))]
    assert "--font-sans: var(--mini-font-sans);" in block
    assert "--font-heading: var(--mini-font-heading);" in block
    assert text.count("--font-sans:") == 1
    assert _mini().tokens_step(app) == 0
    assert _index_css(app).read_text(encoding="utf-8") == text


def test_tokens_step_adds_the_one_missing_line(tmp_path: Path) -> None:
    css = INDEX_CSS.replace("  --font-heading: var(--font-sans);\n", "")
    app = _tokens_app(tmp_path, css)
    assert _mini().tokens_step(app) == 0
    text = _index_css(app).read_text(encoding="utf-8")
    assert text.count("--font-heading:") == 1
    assert "--font-heading: var(--mini-font-heading);" in text


def test_tokens_step_only_touches_the_first_theme_inline_block(tmp_path: Path) -> None:
    css = INDEX_CSS + "\n@theme inline {\n  --font-sans: 'Other', sans-serif;\n}\n"
    app = _tokens_app(tmp_path, css)
    assert _mini().tokens_step(app) == 0
    text = _index_css(app).read_text(encoding="utf-8")
    assert "  --font-sans: 'Other', sans-serif;" in text
    assert text.count("--font-sans: var(--mini-font-sans);") == 1


def _wired_block(block: str) -> str:
    return _mini()._wire_fonts(block)


@pytest.mark.parametrize(
    ("block", "expected"),
    [
        (
            "\n  --font-sans: sans-serif; --color-background: var(--background);\n",
            "\n  --font-sans: var(--mini-font-sans); --color-background: var(--background);\n"
            "  --font-heading: var(--mini-font-heading);\n",
        ),
        (
            "\n  --color-a: red; --font-sans: sans-serif; --color-b: blue;\n"
            "  --font-heading: serif; --radius: 4px;\n",
            "\n  --color-a: red; --font-sans: var(--mini-font-sans); --color-b: blue;\n"
            "  --font-heading: var(--mini-font-heading); --radius: 4px;\n",
        ),
        (
            "\n  --font-sans: 'Geist Variable',\n    system-ui, sans-serif;\n  --color-a: red;\n"
            "  --font-heading: var(--font-sans);\n",
            "\n  --font-sans: var(--mini-font-sans);\n  --color-a: red;\n"
            "  --font-heading: var(--mini-font-heading);\n",
        ),
        (
            "\n  --color-a: red;\n  --font-sans: serif;\n  --font-heading: serif",
            "\n  --color-a: red;\n  --font-sans: var(--mini-font-sans);\n"
            "  --font-heading: var(--mini-font-heading);",
        ),
        (
            "\n  --font-sans: serif;\n  --font-heading: serif\n",
            "\n  --font-sans: var(--mini-font-sans);\n  --font-heading: var(--mini-font-heading);\n",
        ),
        (
            "\n  --font-sans: \"a;b\", url(data:x;y); --color-a: red;\n  --font-heading: serif;\n",
            "\n  --font-sans: var(--mini-font-sans); --color-a: red;\n"
            "  --font-heading: var(--mini-font-heading);\n",
        ),
        (
            "\n  --font-sans-extra: x; --font-sans: serif; --color-a: red;\n"
            "  --font-heading: serif;\n",
            "\n  --font-sans-extra: x; --font-sans: var(--mini-font-sans); --color-a: red;\n"
            "  --font-heading: var(--mini-font-heading);\n",
        ),
        (
            "\n  --font-sans: Arial /* fallback; system font */; --color-a: red;\n"
            "  --font-heading: serif;\n",
            "\n  --font-sans: var(--mini-font-sans); --color-a: red;\n"
            "  --font-heading: var(--mini-font-heading);\n",
        ),
        (
            "\n  --note: \"example; --font-sans: serif; other\";\n  --font-heading: serif;\n",
            "\n  --note: \"example; --font-sans: serif; other\";\n"
            "  --font-heading: var(--mini-font-heading);\n  --font-sans: var(--mini-font-sans);\n",
        ),
        (
            "\n  --label: \"note; --font-sans: fake;\";\n  --font-sans: serif;\n  --font-heading: serif;\n",
            "\n  --label: \"note; --font-sans: fake;\";\n  --font-sans: var(--mini-font-sans);\n"
            "  --font-heading: var(--mini-font-heading);\n",
        ),
        (
            "\n  --font-sans /* why; here */ : serif; --color-a: red;\n  --font-heading: serif;\n",
            "\n  --font-sans /* why; here */ : var(--mini-font-sans); --color-a: red;\n"
            "  --font-heading: var(--mini-font-heading);\n",
        ),
        (
            "\n  /* --font-sans: decoy; */ --font-sans: serif;\n  --font-heading: serif;\n",
            "\n  /* --font-sans: decoy; */ --font-sans: var(--mini-font-sans);\n"
            "  --font-heading: var(--mini-font-heading);\n",
        ),
        (
            "\n  --note: \"a } b ; c\"; --font-sans: serif;\n  --font-heading: serif;\n",
            "\n  --note: \"a } b ; c\"; --font-sans: var(--mini-font-sans);\n"
            "  --font-heading: var(--mini-font-heading);\n",
        ),
        (
            "\n  --note: 'it\\'s; --font-sans: x'; --font-sans: \"a\\\"; b\", serif;\n"
            "  --font-heading: serif;\n",
            "\n  --note: 'it\\'s; --font-sans: x'; --font-sans: var(--mini-font-sans);\n"
            "  --font-heading: var(--mini-font-heading);\n",
        ),
    ],
    ids=[
        "neighbour-after",
        "neighbours-before-and-after",
        "value-spanning-two-lines",
        "no-semicolon-at-block-end",
        "no-semicolon-then-newline",
        "semicolon-inside-quotes-and-parens",
        "similarly-named-property",
        "semicolon-inside-comment-in-value",
        "font-name-inside-another-declarations-string",
        "decoy-string-before-real-declaration",
        "comment-between-property-and-colon",
        "font-name-inside-comment",
        "brace-and-semicolon-inside-string",
        "escaped-quotes-inside-strings",
    ],
)
def test_wire_fonts_replaces_only_the_font_declarations(block: str, expected: str) -> None:
    wired = _wired_block(block)
    assert wired == expected
    assert _wired_block(wired) == wired


def test_tokens_step_finds_the_block_end_past_a_brace_inside_a_string(tmp_path: Path) -> None:
    app = _tokens_app(
        tmp_path,
        '@import "tailwindcss";\n\n@theme inline {\n  --note: "}";\n  --font-sans: serif;\n'
        "  --font-heading: serif;\n}\n",
    )
    assert _mini().tokens_step(app) == 0
    text = _index_css(app).read_text(encoding="utf-8")
    assert '--note: "}";' in text
    assert text.count("--font-sans: var(--mini-font-sans);") == 1
    assert text.count("--font-heading: var(--mini-font-heading);") == 1
    assert _mini().tokens_step(app) == 0
    assert _index_css(app).read_text(encoding="utf-8") == text


def test_tokens_step_fails_without_a_theme_inline_block(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    app = _tokens_app(tmp_path, '@import "tailwindcss";\n\n:root { --background: white; }\n')
    assert _mini().tokens_step(app) == 1
    assert "step tokens failed" in capsys.readouterr().err


def test_tokens_step_fails_without_index_css(tmp_path: Path) -> None:
    app = tmp_path / "app"
    app.mkdir()
    assert _mini().tokens_step(app) == 1


def test_tokens_step_rewires_fonts_even_when_the_import_is_already_present(
    tmp_path: Path,
) -> None:
    css = INDEX_CSS.replace(
        '@import "shadcn/tailwind.css";\n',
        '@import "shadcn/tailwind.css";\n@import "./styles/mini-tokens.css";\n',
    )
    app = _tokens_app(tmp_path, css)
    assert _mini().tokens_step(app) == 0
    text = _index_css(app).read_text(encoding="utf-8")
    assert text.count("styles/mini-tokens.css") == 1
    assert "--font-sans: var(--mini-font-sans);" in text


# --- press_step ---

PRESS_REL = Path("src") / "lib" / "mini" / "press.ts"
PRESS_IMPORT = 'import "./lib/mini/press"'
PRESS_SOURCE = SKILL_DIR / "gallery" / "src" / "lib" / "mini" / "press.ts"

MAIN_TSX = """\
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "./index.css"
import App from "./App.tsx"
"""


def _press_app(tmp_path: Path, main: Any = MAIN_TSX) -> Path:
    app = tmp_path / "app"
    (app / "src").mkdir(parents=True)
    if main is not None:
        (app / "src" / "main.tsx").write_text(main, encoding="utf-8")
    return app


def _main_lines(app: Path) -> List[str]:
    return (app / "src" / "main.tsx").read_text(encoding="utf-8").splitlines()


def test_press_step_copies_the_module_when_absent(
    tmp_path: Path, no_subprocess: List[str], capsys: pytest.CaptureFixture
) -> None:
    app = _press_app(tmp_path)
    assert _mini().press_step(app) == 0
    assert (app / PRESS_REL).read_bytes() == PRESS_SOURCE.read_bytes()
    assert "+ [press]" in capsys.readouterr().out
    assert no_subprocess == []


def test_press_step_leaves_an_existing_module_alone(tmp_path: Path) -> None:
    app = _press_app(tmp_path)
    (app / PRESS_REL).parent.mkdir(parents=True)
    (app / PRESS_REL).write_bytes(b"// edited by hand\n")
    assert _mini().press_step(app) == 0
    assert (app / PRESS_REL).read_bytes() == b"// edited by hand\n"


def test_press_step_adds_the_import_once_after_index_css(tmp_path: Path) -> None:
    app = _press_app(tmp_path)
    assert _mini().press_step(app) == 0
    lines = _main_lines(app)
    assert lines.count(PRESS_IMPORT) == 1
    assert lines[lines.index('import "./index.css"') + 1] == PRESS_IMPORT
    assert [line for line in lines if line != PRESS_IMPORT] == MAIN_TSX.splitlines()


def test_press_step_adds_the_import_first_without_an_index_css_import(tmp_path: Path) -> None:
    body = 'import App from "./App.tsx"\n'
    app = _press_app(tmp_path, body)
    assert _mini().press_step(app) == 0
    assert _main_lines(app) == [PRESS_IMPORT, 'import App from "./App.tsx"']


def test_press_step_is_idempotent(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    app = _press_app(tmp_path)
    assert _mini().press_step(app) == 0
    main = app / "src" / "main.tsx"
    once = main.read_bytes()
    capsys.readouterr()
    before = main.stat().st_mtime_ns
    assert _mini().press_step(app) == 0
    assert main.read_bytes() == once
    assert main.stat().st_mtime_ns == before
    assert once.decode("utf-8").count(PRESS_IMPORT) == 1


def test_press_step_fails_without_main_tsx(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    app = _press_app(tmp_path, None)
    assert _mini().press_step(app) == 1
    assert "step press failed" in capsys.readouterr().err


def test_press_step_adds_a_real_import_when_only_a_comment_mentions_it(tmp_path: Path) -> None:
    body = 'import "./index.css"\n// import "./lib/mini/press"\n'
    app = _press_app(tmp_path, body)
    assert _mini().press_step(app) == 0
    assert _main_lines(app) == [
        'import "./index.css"',
        PRESS_IMPORT,
        '// import "./lib/mini/press"',
    ]


def test_press_step_does_not_count_an_import_inside_a_string(tmp_path: Path) -> None:
    body = 'import "./index.css"\nconst note = \'import "./lib/mini/press"\'\n'
    app = _press_app(tmp_path, body)
    assert _mini().press_step(app) == 0
    lines = _main_lines(app)
    assert lines.count(PRESS_IMPORT) == 1
    assert lines[1] == PRESS_IMPORT


def test_press_step_adds_a_real_import_when_a_block_comment_holds_it(tmp_path: Path) -> None:
    body = 'import "./index.css"\n/* Disabled while debugging:\nimport "./lib/mini/press"\n*/\n'
    app = _press_app(tmp_path, body)
    assert _mini().press_step(app) == 0
    assert (app / "src" / "main.tsx").read_text(encoding="utf-8") == (
        f'import "./index.css"\n{PRESS_IMPORT}\n/* Disabled while debugging:\n'
        'import "./lib/mini/press"\n*/\n'
    )


def test_press_step_adds_a_real_import_when_a_template_literal_holds_it(tmp_path: Path) -> None:
    body = 'import "./index.css"\nconst note = `\nimport "./lib/mini/press"\n`\n'
    app = _press_app(tmp_path, body)
    assert _mini().press_step(app) == 0
    assert (app / "src" / "main.tsx").read_text(encoding="utf-8") == (
        f'import "./index.css"\n{PRESS_IMPORT}\nconst note = `\nimport "./lib/mini/press"\n`\n'
    )


def test_press_step_counts_an_active_import_below_a_closed_block_comment(tmp_path: Path) -> None:
    body = 'import "./index.css"\n/* press marker */\nimport "./lib/mini/press"\n'
    app = _press_app(tmp_path, body)
    main = app / "src" / "main.tsx"
    before = main.stat().st_mtime_ns
    assert _mini().press_step(app) == 0
    assert main.read_text(encoding="utf-8") == body
    assert main.stat().st_mtime_ns == before


@pytest.mark.parametrize(
    "import_line",
    [
        "import './lib/mini/press'",
        'import "./lib/mini/press.ts"',
        'import "./lib/mini/press.js";',
        '  import "./lib/mini/press";',
    ],
)
def test_press_step_accepts_equivalent_active_import_forms(tmp_path: Path, import_line: str) -> None:
    body = f'import "./index.css"\n{import_line}\n'
    app = _press_app(tmp_path, body)
    main = app / "src" / "main.tsx"
    before = main.stat().st_mtime_ns
    assert _mini().press_step(app) == 0
    assert main.read_text(encoding="utf-8") == body
    assert main.stat().st_mtime_ns == before
