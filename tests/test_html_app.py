"""Tests for the tier-2 `app` template and `quirk_html.py build-app`.

Most builds run against a fake `pnpm` on PATH so no test needs Node packages or the network.
The one real build is skipped unless pnpm is on PATH and QUIRK_HTML_NETWORK_TESTS=1.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import header, layoutcheck, manifest, verify_runner  # noqa: E402
from htmlkit.layouts import LAYOUTS  # noqa: E402

CLI = SKILL / "scripts" / "quirk_html.py"
APP = SKILL / "templates" / "app"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not on PATH")

FAKE_PNPM = """#!{python}
import json, os, sys
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["FAKE_PNPM_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
fail = os.environ.get("FAKE_PNPM_FAIL")
if args and args[0] == "install":
    if fail == "install":
        for n in range(1, 51):
            print(f"install line {{n}}", flush=True)
        print("ERR_PNPM_FAKE install exploded", file=sys.stderr)
        sys.exit(1)
    deps = json.loads(Path("package.json").read_text()).get("dependencies", {{}})
    for name, version in deps.items():
        pkg = Path("node_modules") / name
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "package.json").write_text(json.dumps({{"name": name, "version": version, "license": "MIT"}}))
elif args[:2] == ["run", "build"]:
    if fail == "build":
        print("ERR_PNPM_FAKE build exploded", file=sys.stderr)
        sys.exit(1)
    Path("dist").mkdir(exist_ok=True)
    page = os.environ.get("FAKE_PNPM_HTML", {html!r})
    if os.environ.get("FAKE_PNPM_EMBED_TOKENS"):
        css = Path("src/quirk-tokens.css").read_text()
        page = page.replace("</head>", "<style>" + css + "</style></head>")
    Path("dist/index.html").write_text(page)
else:
    sys.exit(2)
"""
PAGE = (
    '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>Fake</title></head>'
    '<body><div id="root"></div><script type="module">console.log(1)</script></body></html>\n'
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    return proj


@pytest.fixture
def fake_env(tmp_path: Path) -> dict:
    """An env whose PATH holds only node and a fake pnpm that logs its argv."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    pnpm = bin_dir / "pnpm"
    pnpm.write_text(FAKE_PNPM.format(python=sys.executable, html=PAGE), encoding="utf-8")
    pnpm.chmod(pnpm.stat().st_mode | stat.S_IXUSR)
    if NODE:
        (bin_dir / "node").symlink_to(NODE)
    user = tmp_path / "user-templates"
    user.mkdir()
    return {
        "PATH": str(bin_dir),
        "HOME": str(tmp_path),
        "QUIRK_HTML_USER_DIR": str(user),
        "FAKE_PNPM_LOG": str(tmp_path / "pnpm.log"),
    }


def run_cli(*args: object, env: dict) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(CLI), *map(str, args)],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    out = proc.stdout.strip()
    assert out, f"no stdout (rc={proc.returncode}): {proc.stderr}"
    return proc.returncode, json.loads(out)


def build_app(project: Path, env: dict, slug: str = "demo", *extra: object) -> tuple[int, dict]:
    return run_cli("build-app", slug, "--project-dir", project, *extra, env=env)


def source_dir(project: Path, slug: str = "demo") -> Path:
    return project / ".quirk" / "html" / slug


def pnpm_calls(env: dict) -> list[list[str]]:
    log = Path(env["FAKE_PNPM_LOG"])
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def test_app_template_validates_and_lists_as_tier_2(project, fake_env):
    assert manifest.validate_template(APP, require_verified=False, skill_dir=SKILL) == []
    meta = json.loads((APP / "template.json").read_text())
    assert meta["tier"] == 2 and meta["project"] == "project/" and meta["example"] == "example/"
    assert meta["description"].startswith("Use when")
    env = {**os.environ, "QUIRK_HTML_USER_DIR": fake_env["QUIRK_HTML_USER_DIR"]}
    rc, result = run_cli("templates", "validate", APP, env=env)
    assert rc == 0 and result == {"valid": True, "errors": []}
    rc, listing = run_cli("templates", "list", "--project-dir", project, env=env)
    row = next(t for t in listing["templates"] if t["name"] == "app")
    assert (row["level"], row["tier"], row["path"]) == ("builtin", 2, str(APP))


def test_app_template_pins_the_contract_versions():
    pkg = json.loads((APP / "project" / "package.json").read_text())
    assert pkg["dependencies"] == {
        "@astryxdesign/core": "0.6.2",
        "@astryxdesign/theme-neutral": "0.6.2",
        "@tanstack/react-query": "5.104.2",
        "@tanstack/react-router": "1.170.44",
        "@tanstack/react-table": "9.3.1",
        "react": "19.2.8",
        "react-dom": "19.2.8",
    }
    dev = pkg["devDependencies"]
    assert {k: dev[k] for k in ("vite", "vite-plugin-singlefile", "@vitejs/plugin-react", "typescript")} == {
        "vite": "8.3.0",
        "vite-plugin-singlefile": "2.3.3",
        "@vitejs/plugin-react": "6.1.1",
        "typescript": "6.0.2",
    }
    every = {**pkg["dependencies"], **dev}
    assert all(v[0].isdigit() for v in every.values())
    assert (APP / "project" / "pnpm-lock.yaml").is_file()


def test_missing_node_is_exit_3_no_node(project, tmp_path):
    empty = tmp_path / "empty-path"
    empty.mkdir()
    rc, result = build_app(project, {"PATH": str(empty), "HOME": str(tmp_path)}, "demo", "--title", "Demo")
    assert rc == 3
    assert result["error"] == "tier2-unavailable" and result["reason"] == "no-node"
    assert result["detail"]


@needs_node
def test_missing_pnpm_is_exit_3_no_pnpm(project, fake_env):
    (Path(fake_env["PATH"]) / "pnpm").unlink()
    rc, result = build_app(project, fake_env, "demo", "--title", "Demo")
    assert rc == 3 and result["reason"] == "no-pnpm"


@needs_node
def test_failed_install_is_exit_3_with_the_last_40_lines(project, fake_env):
    rc, result = build_app(project, {**fake_env, "FAKE_PNPM_FAIL": "install"}, "demo", "--title", "Demo")
    assert rc == 3 and result["reason"] == "install-failed"
    lines = result["detail"].splitlines()
    assert len(lines) <= 40
    assert "ERR_PNPM_FAKE install exploded" in lines[-1]
    assert "install line 50" in result["detail"] and "install line 1\n" not in result["detail"]
    assert not (project / ".quirk" / "html" / "demo.html").exists()


@needs_node
def test_failed_build_is_exit_3_build_failed(project, fake_env):
    rc, result = build_app(project, {**fake_env, "FAKE_PNPM_FAIL": "build"}, "demo", "--title", "Demo")
    assert rc == 3 and result["reason"] == "build-failed"
    assert "build exploded" in result["detail"]


@needs_node
def test_missing_dist_index_is_build_failed(project, fake_env):
    pnpm = Path(fake_env["PATH"]) / "pnpm"
    pnpm.write_text(pnpm.read_text().replace('Path("dist/index.html").write_text', "(lambda *_: None)"))
    rc, result = build_app(project, fake_env, "demo", "--title", "Demo")
    assert rc == 3 and result["reason"] == "build-failed" and "dist/index.html" in result["detail"]


@needs_node
def test_first_build_scaffolds_installs_frozen_and_writes_the_bundle(project, fake_env):
    rc, result = build_app(project, fake_env, "demo", "--title", "Demo <app>", "--signal", "editable grid")
    assert rc == 0, result
    out = project / ".quirk" / "html" / "demo.html"
    assert result["path"] == str(out) and result["size"] == out.stat().st_size
    assert result["source_dir"] == str(source_dir(project))
    assert (result["template"], result["template_level"], result["tier"]) == ("app", "builtin", 2)
    assert (result["tier_signal"], result["mode"], result["sidecar"], result["cut"]) == ("editable grid", "offline", None, [])
    assert result["checks"]["passed"] is True
    assert (project / ".quirk" / "html" / ".gitignore").read_text().strip() == "*"

    src = source_dir(project)
    assert (src / "vite.config.ts").is_file() and (src / "pnpm-lock.yaml").is_file()
    assert (src / "src" / "App.tsx").read_text() == (APP / "project" / "src" / "App.tsx").read_text()
    assert (src / "src" / "routes.tsx").read_text() == (APP / "example" / "src" / "routes.tsx").read_text()
    assert (src / "src" / "routes.tsx").read_text() != (APP / "project" / "src" / "routes.tsx").read_text()
    assert not (src / "example").exists()
    assert pnpm_calls(fake_env) == [
        ["install", "--frozen-lockfile", "--ignore-scripts", "--ignore-pnpmfile"],
        ["run", "build"],
    ]

    html = out.read_text()
    assert html.startswith("<!doctype html>\n")
    assert "<title>Demo &lt;app&gt;</title>" in html and "<title>Fake</title>" not in html
    meta = header.read_header(html)
    assert meta["tier"] == 2 and meta["template"] == "app" and meta["tier_signal"] == "editable grid"
    assert meta["mode"] == "offline" and meta["sidecar"] is None
    assert meta["libraries"]["react"] == "19.2.8"
    pkg = json.loads((APP / "project" / "package.json").read_text())
    for name, version in pkg["dependencies"].items():
        assert f"<!-- license: {name} {version} MIT" in html
    assert result["libraries"] == meta["libraries"]


@needs_node
def test_quirk_app_json_round_trips_and_flags_override(project, fake_env):
    rc, _ = build_app(project, fake_env, "demo", "--title", "First", "--mode", "connected", "--signal", "multi view")
    assert rc == 0
    saved = source_dir(project) / "quirk-app.json"
    assert json.loads(saved.read_text()) == {
        "template": "app",
        "title": "First",
        "mode": "connected",
        "tier_signal": "multi view",
        "layout": "report",
    }

    rc, result = build_app(project, fake_env)
    assert rc == 0
    meta = header.read_header((project / ".quirk" / "html" / "demo.html").read_text())
    assert (meta["mode"], meta["tier_signal"]) == ("connected", "multi view")
    assert (result["mode"], result["tier_signal"]) == ("connected", "multi view")

    rc, result = build_app(project, fake_env, "demo", "--title", "Second", "--mode", "offline")
    assert rc == 0 and result["mode"] == "offline"
    assert json.loads(saved.read_text()) == {
        "template": "app",
        "title": "Second",
        "mode": "offline",
        "tier_signal": "multi view",
        "layout": "report",
    }


@needs_node
def test_first_build_requires_a_title(project, fake_env):
    rc, result = build_app(project, fake_env)
    assert rc == 2 and "--title" in result["error"]
    assert not source_dir(project).exists()


@needs_node
def test_invalid_slug_and_mode_are_usage_errors(project, fake_env):
    rc, result = build_app(project, fake_env, "../escape", "--title", "x")
    assert rc == 2 and "slug" in result["error"]
    rc, result = build_app(project, fake_env, "demo", "--title", "x", "--mode", "companion")
    assert rc == 2 and "mode" in result["error"]


@needs_node
@pytest.mark.parametrize("slug", ["demo\n", "demo\n\n", "\ndemo"])
def test_a_slug_with_a_newline_is_a_usage_error(project, fake_env, slug):
    rc, result = build_app(project, fake_env, slug, "--title", "x")
    assert rc == 2 and "slug" in result["error"]
    assert not (project / ".quirk" / "html").exists() or not any(
        p.name.startswith("demo") for p in (project / ".quirk" / "html").iterdir()
    )


@needs_node
def test_a_project_tokens_file_reaches_the_tier_2_bundle(project, fake_env):
    tokens = project / ".quirk" / "html-templates" / "tokens.json"
    tokens.parent.mkdir(parents=True)
    tokens.write_text(json.dumps({"schema": 1, "color": {"accent": ["#123456", "#abcdef"]}}))
    env = {**fake_env, "FAKE_PNPM_EMBED_TOKENS": "1"}
    rc, result = build_app(project, env, "demo", "--title", "Branded")
    assert rc == 0, result
    css = (source_dir(project) / "src" / "quirk-tokens.css").read_text()
    assert "--q-color-accent: #123456" in css and "--q-color-accent: #abcdef" in css
    assert "--q-color-bg:" in css
    html = (project / ".quirk" / "html" / "demo.html").read_text()
    assert "--q-color-accent: #123456" in html


@needs_node
def test_the_user_tokens_layer_reaches_tier_2_and_a_rebuild_refreshes_the_file(project, fake_env):
    assert build_app(project, fake_env, "demo", "--title", "T")[0] == 0
    css_path = source_dir(project) / "src" / "quirk-tokens.css"
    assert "#123456" not in css_path.read_text()
    (Path(fake_env["QUIRK_HTML_USER_DIR"]) / "tokens.json").write_text(
        json.dumps({"schema": 1, "color": {"accent": ["#123456", "#abcdef"]}})
    )
    assert build_app(project, fake_env)[0] == 0
    assert "--q-color-accent: #123456" in css_path.read_text()


def test_the_scaffold_theme_imports_the_generated_tokens_instead_of_pasting_them():
    theme = (APP / "project" / "src" / "theme.css").read_text()
    assert "@import './quirk-tokens.css';" in theme
    assert "--q-color-bg:" not in theme and "--q-space-1:" not in theme
    assert "var(--q-color-bg)" in theme


@needs_node
def test_existing_source_folder_is_never_overwritten(project, fake_env):
    src = source_dir(project)
    (src / "src").mkdir(parents=True)
    (src / "package.json").write_text(json.dumps({"dependencies": {"left-pad": "1.3.0"}}))
    (src / "src" / "App.tsx").write_text("// mine\n")
    rc, result = build_app(project, fake_env, "demo", "--title", "Mine")
    assert rc == 0, result
    assert (src / "src" / "App.tsx").read_text() == "// mine\n"
    assert not (src / "vite.config.ts").exists()
    assert json.loads((src / "quirk-app.json").read_text())["title"] == "Mine"
    assert "<!-- license: left-pad 1.3.0 MIT" in (project / ".quirk" / "html" / "demo.html").read_text()


@needs_node
def test_a_rebuild_keeps_source_edits(project, fake_env):
    assert build_app(project, fake_env, "demo", "--title", "T")[0] == 0
    app = source_dir(project) / "src" / "App.tsx"
    app.write_text("// edited\n")
    assert build_app(project, fake_env)[0] == 0
    assert app.read_text() == "// edited\n"


@needs_node
def test_bundle_with_an_external_script_fails_static_checks(project, fake_env):
    page = PAGE.replace("<body>", '<body><script src="https://cdn.example.com/x.js"></script>')
    rc, result = build_app(project, {**fake_env, "FAKE_PNPM_HTML": page}, "demo", "--title", "Demo")
    assert rc == 1
    assert [f["check"] for f in result["checks"]["failures"]] == ["external-refs"]
    assert (project / ".quirk" / "html" / "demo.html").is_file()


@needs_node
def test_connected_bundle_may_call_the_network_but_not_load_scripts(project, fake_env):
    page = PAGE.replace("console.log(1)", "fetch('https://api.example.com/x')")
    rc, result = build_app(project, {**fake_env, "FAKE_PNPM_HTML": page}, "demo", "--title", "D", "--mode", "connected")
    assert rc == 0 and result["checks"]["passed"] is True


@needs_node
def test_upgrade_is_reported_as_a_no_op_for_a_kit_free_app(project, fake_env):
    rc, result = build_app(project, fake_env, "demo", "--title", "Demo", "--upgrade")
    assert rc == 0 and any("--upgrade has no effect on tier 2" in w for w in result["warnings"])
    page = (project / ".quirk" / "html" / "demo.html").read_text()
    assert "data-quirk-lib" not in page and "kit" not in header.read_header(page)["libraries"]


KIT_VIEW = (
    "export function Chart() {\n"
    '  return <q-chart summary="Signups rose">\n'
    "    <table><thead><tr><th>Month</th><th>n</th></tr></thead>\n"
    "    <tbody><tr><td>Jan</td><td>1</td></tr></tbody></table>\n"
    "  </q-chart>;\n"
    "}\n"
)


def add_source(project: Path, name: str, text: str, slug: str = "demo") -> Path:
    path = source_dir(project, slug) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def kit_catalog_tags() -> set[str]:
    catalog = json.loads((SKILL / "vendor" / "kit" / "1.0.0" / "catalog.json").read_text(encoding="utf-8"))
    return {element["tag"] for element in catalog["elements"]}


@needs_node
def test_a_tsx_with_q_chart_inlines_the_kit_and_chartjs(project, fake_env):
    assert build_app(project, fake_env, "demo", "--title", "Demo")[0] == 0
    add_source(project, "src/Chart.tsx", KIT_VIEW)
    rc, result = build_app(project, fake_env)
    assert rc == 0 and result["checks"]["passed"] is True, result["checks"]
    page = (project / ".quirk" / "html" / "demo.html").read_text()
    libs = header.read_header(page)["libraries"]
    registry = json.loads((SKILL / "vendor" / "libraries.json").read_text())["libraries"]
    assert libs["kit"] == registry["kit"]["current"] and libs["chartjs"] == registry["chartjs"]["current"]
    assert result["libraries"] == libs
    assert f'<style data-quirk-lib="kit@{libs["kit"]}">' in page
    assert f'<script data-quirk-lib="chartjs@{libs["chartjs"]}">' in page
    assert f'<script data-quirk-lib="kit@{libs["kit"]}">' in page
    assert f"<!-- license: kit {libs['kit']} MIT" in page and f"<!-- license: chartjs {libs['chartjs']} MIT" in page
    head_end, body_end = page.index("</head>"), page.rindex("</body>")
    assert page.index('<style data-quirk-lib="kit@') < head_end
    chart_js, kit_js = page.index('<script data-quirk-lib="chartjs@'), page.index('<script data-quirk-lib="kit@')
    assert head_end < chart_js < kit_js < body_end
    assert page.index("<!-- license: kit") < head_end


@needs_node
def test_a_kit_check_failure_in_a_tsx_names_the_src_relative_file_and_line(project, fake_env):
    assert build_app(project, fake_env, "demo", "--title", "Demo")[0] == 0
    add_source(project, "src/views/Bad.tsx", "export const Bad = () => (\n  <div>\n    <q-stats>x</q-stats>\n  </div>\n);\n")
    rc, result = build_app(project, fake_env)
    assert rc == 1
    failures = [f for f in result["checks"]["failures"] if f["check"] == "kit"]
    assert [f["detail"] for f in failures] == ["src/views/Bad.tsx line 3: unknown element <q-stats>"]
    assert result["checks"]["passed"] is False
    assert (project / ".quirk" / "html" / "demo.html").is_file()


@needs_node
def test_kit_tags_in_test_files_and_declarations_are_neither_scanned_nor_pull_in_the_kit(project, fake_env):
    assert build_app(project, fake_env, "demo", "--title", "Demo")[0] == 0
    add_source(project, "src/Chart.test.tsx", "const x = <q-stats>x</q-stats>;\n")
    add_source(project, "src/Chart.spec.ts", "const y = '<q-chart summary=\"x\">';\n")
    add_source(project, "src/extra.d.ts", "// <q-stats>\n")
    rc, result = build_app(project, fake_env)
    assert rc == 0 and result["checks"]["passed"] is True
    assert "kit" not in result["libraries"]
    assert "data-quirk-lib" not in (project / ".quirk" / "html" / "demo.html").read_text()


@needs_node
def test_a_kit_tag_in_index_html_pulls_in_the_kit(project, fake_env):
    assert build_app(project, fake_env, "demo", "--title", "Demo")[0] == 0
    index = source_dir(project) / "index.html"
    index.write_text(index.read_text().replace("</body>", '<q-code filename="a.txt">hi</q-code></body>', 1))
    rc, result = build_app(project, fake_env)
    assert rc == 0 and result["checks"]["passed"] is True, result["checks"]
    assert "kit" in result["libraries"] and "chartjs" not in result["libraries"]


@needs_node
def test_dropping_every_kit_tag_drops_the_kit_from_the_header(project, fake_env):
    assert build_app(project, fake_env, "demo", "--title", "Demo")[0] == 0
    view = add_source(project, "src/Chart.tsx", KIT_VIEW)
    assert "kit" in build_app(project, fake_env)[1]["libraries"]
    view.write_text("export const Chart = () => null;\n")
    rc, result = build_app(project, fake_env)
    assert rc == 0 and "kit" not in result["libraries"] and "chartjs" not in result["libraries"]


@pytest.fixture
def two_kit_versions_skill(tmp_path: Path) -> Path:
    """A copy of the skill whose registry holds kit 1.0.0 and 1.0.1, current still 1.0.0."""
    skill = tmp_path / "skill-copy"
    shutil.copytree(SKILL, skill, ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
    kit = skill / "vendor" / "kit"
    shutil.copytree(kit / "1.0.0", kit / "1.0.1")
    catalog = json.loads((kit / "1.0.1" / "catalog.json").read_text())
    catalog["kit_version"] = "1.0.1"
    (kit / "1.0.1" / "catalog.json").write_text(json.dumps(catalog))
    registry = json.loads((skill / "vendor" / "libraries.json").read_text())
    entry = registry["libraries"]["kit"]
    entry["versions"]["1.0.1"] = entry["versions"]["1.0.0"]
    (skill / "vendor" / "libraries.json").write_text(json.dumps(registry))
    return skill


def set_kit_current(skill: Path, version: str) -> None:
    path = skill / "vendor" / "libraries.json"
    registry = json.loads(path.read_text())
    registry["libraries"]["kit"]["current"] = version
    path.write_text(json.dumps(registry))


@needs_node
def test_upgrade_moves_a_frozen_kit_version_to_current(project, fake_env, two_kit_versions_skill, monkeypatch):
    from htmlkit import app as app_module

    for key, value in fake_env.items():
        monkeypatch.setenv(key, value)

    def build(upgrade: bool) -> dict:
        return app_module.build_app(
            "demo",
            title="Demo",
            mode=None,
            signal=None,
            template_name=None,
            upgrade=upgrade,
            project_dir=project,
            user_dir=Path(fake_env["QUIRK_HTML_USER_DIR"]),
            skill_dir=two_kit_versions_skill,
        )

    build(False)
    add_source(project, "src/Chart.tsx", KIT_VIEW)
    assert build(False)["libraries"]["kit"] == "1.0.0"
    set_kit_current(two_kit_versions_skill, "1.0.1")
    frozen = build(False)
    assert frozen["libraries"]["kit"] == "1.0.0"
    assert frozen["checks"]["passed"] is True
    assert not any("--upgrade" in w or "upgraded" in w for w in frozen["warnings"])
    upgraded = build(True)
    assert upgraded["libraries"]["kit"] == "1.0.1" and upgraded["checks"]["passed"] is True
    assert "library kit upgraded from 1.0.0 to 1.0.1" in upgraded["warnings"]
    assert not any("has no effect" in w for w in upgraded["warnings"])
    page = (project / ".quirk" / "html" / "demo.html").read_text()
    assert 'data-quirk-lib="kit@1.0.1"' in page and 'data-quirk-lib="kit@1.0.0"' not in page


@needs_node
def test_an_unloadable_kit_catalog_is_a_kit_check_failure_not_a_crash(project, fake_env, two_kit_versions_skill, monkeypatch):
    from htmlkit import app as app_module

    for key, value in fake_env.items():
        monkeypatch.setenv(key, value)
    (two_kit_versions_skill / "vendor" / "kit" / "1.0.0" / "catalog.json").write_text("{not json")
    kwargs = dict(
        title="Demo", mode=None, signal=None, template_name=None, upgrade=False,
        project_dir=project, user_dir=Path(fake_env["QUIRK_HTML_USER_DIR"]), skill_dir=two_kit_versions_skill,
    )
    app_module.build_app("demo", **kwargs)
    add_source(project, "src/Chart.tsx", KIT_VIEW)
    result = app_module.build_app("demo", **kwargs)
    assert result["checks"]["passed"] is False
    assert [f["check"] for f in result["checks"]["failures"]] == ["kit"]
    assert "cannot load the kit catalog" in result["checks"]["failures"][0]["detail"]
    assert (project / ".quirk" / "html" / "demo.html").is_file()


def test_quirk_kit_d_ts_declares_exactly_the_catalog_tags():
    dts = (APP / "project" / "src" / "quirk-kit.d.ts").read_text(encoding="utf-8")
    assert "<q-" not in dts
    assert re.findall(r"declare module 'react'", dts) and re.findall(r"^export \{\};?$", dts, re.MULTILINE)
    declared = set(re.findall(r"^\s*'(q-[a-z-]+)'\s*:", dts, re.MULTILINE))
    assert declared == kit_catalog_tags()


def test_app_rules_link_the_component_reference_and_it_resolves():
    rules = APP / "rules.md"
    text = rules.read_text(encoding="utf-8")
    assert "## Kit elements" in text and "../../references/components.md" in text
    assert (rules.parent / "../../references/components.md").resolve().is_file()


def seal(tdir: Path) -> None:
    (tdir / "verified.json").write_text(
        json.dumps({"schema": 1, "verified_at": "2026-10-13T00:00:00Z", "browser": False, "hashes": manifest.compute_hashes(tdir)})
    )


@needs_node
def test_custom_tier_2_template_is_copied_without_node_modules_and_installs_without_scripts(project, fake_env):
    tdir = project / ".quirk" / "html-templates" / "mini"
    (tdir / "project" / "node_modules" / "stale").mkdir(parents=True)
    (tdir / "project" / "node_modules" / "stale" / "x.js").write_text("x")
    (tdir / "project" / "dist").mkdir()
    (tdir / "project" / "dist" / "old.html").write_text("old")
    (tdir / "project" / "src").mkdir()
    (tdir / "project" / "src" / "App.tsx").write_text("// base\n")
    (tdir / "project" / "src" / "keep.ts").write_text("// keep\n")
    (tdir / "project" / "package.json").write_text(json.dumps({"dependencies": {"left-pad": "1.3.0"}}))
    (tdir / "project" / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    (tdir / "example" / "src").mkdir(parents=True)
    (tdir / "example" / "src" / "App.tsx").write_text("// overlay\n")
    (tdir / "template.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "name": "mini",
                "description": "Use when a test needs a minimal tier-2 template fixture.",
                "tier": 2,
                "project": "project/",
                "example": "example/",
            }
        )
    )
    seal(tdir)
    rc, result = build_app(project, fake_env, "demo", "--title", "Demo", "--template", "mini")
    assert rc == 0, result
    assert (result["template"], result["template_level"]) == ("mini", "project")
    src = source_dir(project)
    assert (src / "src" / "App.tsx").read_text() == "// overlay\n"
    assert (src / "src" / "keep.ts").read_text() == "// keep\n"
    assert not (src / "dist" / "old.html").exists()
    assert not (src / "node_modules" / "stale").exists()
    assert pnpm_calls(fake_env)[0] == ["install", "--frozen-lockfile", "--ignore-scripts", "--ignore-pnpmfile"]
    assert json.loads((src / "quirk-app.json").read_text())["template"] == "mini"


@needs_node
def test_custom_tier_2_template_without_src_still_builds(project, fake_env):
    tdir = project / ".quirk" / "html-templates" / "flat"
    (tdir / "project").mkdir(parents=True)
    (tdir / "project" / "package.json").write_text(json.dumps({"dependencies": {}}))
    (tdir / "project" / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    (tdir / "template.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "name": "flat",
                "description": "Use when a test needs a tier-2 template with no src folder.",
                "tier": 2,
                "project": "project/",
            }
        )
    )
    seal(tdir)
    rc, result = build_app(project, fake_env, "demo", "--title", "Demo", "--template", "flat")
    assert rc == 0, result
    assert (source_dir(project) / "src" / "quirk-tokens.css").is_file()
    assert pnpm_calls(fake_env)[0][0] == "install"


@needs_node
def test_tier_1_template_is_refused_by_build_app(project, fake_env):
    rc, result = build_app(project, fake_env, "demo", "--title", "Demo", "--template", "report")
    assert rc == 2 and "tier 1" in result["error"]
    assert not source_dir(project).exists()


def _built_header(project: Path, slug: str = "demo") -> dict:
    return header.read_header((project / ".quirk" / "html" / f"{slug}.html").read_text())


@needs_node
def test_layout_round_trips_through_quirk_app_json_and_the_header(project, fake_env):
    rc, result = build_app(project, fake_env, "demo", "--title", "Ops", "--layout", "dashboard")
    assert rc == 0, result
    saved = source_dir(project) / "quirk-app.json"
    assert json.loads(saved.read_text())["layout"] == "dashboard"
    assert result["layout"] == "dashboard" and _built_header(project)["layout"] == "dashboard"

    rc, result = build_app(project, fake_env)
    assert rc == 0 and result["layout"] == "dashboard"
    assert _built_header(project)["layout"] == "dashboard"
    assert "dashboard" in (source_dir(project) / "src" / "quirk-page.ts").read_text()


@needs_node
def test_a_build_with_no_layout_is_a_report(project, fake_env):
    rc, result = build_app(project, fake_env, "demo", "--title", "Plain")
    assert rc == 0 and result["layout"] == "report"
    assert json.loads((source_dir(project) / "quirk-app.json").read_text())["layout"] == "report"
    assert _built_header(project)["layout"] == "report"


@needs_node
def test_the_layout_flag_overrides_the_saved_value_and_is_saved(project, fake_env):
    assert build_app(project, fake_env, "demo", "--title", "T", "--layout", "tool")[0] == 0
    rc, result = build_app(project, fake_env, "demo", "--layout", "reference")
    assert rc == 0 and result["layout"] == "reference"
    saved = source_dir(project) / "quirk-app.json"
    assert json.loads(saved.read_text())["layout"] == "reference"
    assert _built_header(project)["layout"] == "reference"
    assert "reference" in (source_dir(project) / "src" / "quirk-page.ts").read_text()


@needs_node
def test_a_saved_layout_is_used_when_the_source_folder_already_holds_one(project, fake_env):
    src = source_dir(project)
    shutil.copytree(APP / "project", src)
    (src / "quirk-app.json").write_text(json.dumps({"layout": "comparison"}))
    rc, result = build_app(project, fake_env, "demo", "--title", "Pick one")
    assert rc == 0 and result["layout"] == "comparison"
    assert json.loads((src / "quirk-app.json").read_text())["layout"] == "comparison"


@needs_node
def test_a_bad_layout_flag_is_a_usage_error_that_lists_the_shapes(project, fake_env):
    rc, result = build_app(project, fake_env, "demo", "--title", "x", "--layout", "poster")
    assert rc == 2
    assert all(name in result["error"] for name in LAYOUTS)
    assert not source_dir(project).exists() and pnpm_calls(fake_env) == []


@needs_node
def test_a_bad_saved_layout_is_a_usage_error(project, fake_env):
    assert build_app(project, fake_env, "demo", "--title", "T")[0] == 0
    saved = source_dir(project) / "quirk-app.json"
    saved.write_text(json.dumps({**json.loads(saved.read_text()), "layout": "poster"}))
    rc, result = build_app(project, fake_env)
    assert rc == 2 and "layout" in result["error"] and "poster" in result["error"]
    saved.write_text(json.dumps({**json.loads(saved.read_text()), "layout": 3}))
    assert build_app(project, fake_env)[0] == 2


@needs_node
def test_the_layout_stylesheet_and_page_module_are_written_every_build(project, fake_env):
    assert build_app(project, fake_env, "demo", "--title", "T", "--layout", "longform")[0] == 0
    src = source_dir(project) / "src"
    css, module = src / "quirk-layout.css", src / "quirk-page.ts"
    assert css.read_text() == (SKILL / "theme" / "layout.css").read_text()
    assert "export const layout" in module.read_text() and '"longform"' in module.read_text()

    css.write_text("/* edited by hand */")
    module.write_text("export const layout: string = 'tool'\n")
    assert build_app(project, fake_env)[0] == 0
    assert css.read_text() == (SKILL / "theme" / "layout.css").read_text()
    assert '"longform"' in module.read_text() and "tool" not in module.read_text()

    css.unlink()
    module.unlink()
    assert build_app(project, fake_env, "demo", "--layout", "explainer")[0] == 0
    assert css.is_file() and '"explainer"' in module.read_text()


@needs_node
def test_a_template_without_a_src_folder_still_gets_the_layout_files(project, fake_env):
    tdir = project / ".quirk" / "html-templates" / "flat"
    (tdir / "project").mkdir(parents=True)
    (tdir / "project" / "package.json").write_text(json.dumps({"dependencies": {}}))
    (tdir / "project" / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    (tdir / "template.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "name": "flat",
                "description": "Use when a test needs a tier-2 template with no src folder.",
                "tier": 2,
                "project": "project/",
            }
        )
    )
    seal(tdir)
    rc, result = build_app(project, fake_env, "demo", "--title", "Demo", "--template", "flat", "--layout", "tool")
    assert rc == 0, result
    assert (source_dir(project) / "src" / "quirk-layout.css").is_file()
    assert '"tool"' in (source_dir(project) / "src" / "quirk-page.ts").read_text()


@needs_node
def test_hand_written_page_geometry_in_the_app_sources_fails_the_build(project, fake_env):
    assert build_app(project, fake_env, "demo", "--title", "T")[0] == 0
    src = source_dir(project) / "src"
    (src / "views").mkdir(exist_ok=True)
    (src / "views" / "cards.css").write_text(".cards {\n  color: red;\n  display: grid;\n}\n")
    (src / "views" / "Wide.tsx").write_text("export const Wide = () => <div style={{ maxWidth: '900px' }} />\n")
    rc, result = build_app(project, fake_env)
    assert rc == 1 and result["checks"]["passed"] is False
    layout = [f for f in result["checks"]["failures"] if f["check"] == "layout"]
    details = " | ".join(f["detail"] for f in layout)
    assert "src/views/cards.css line 3" in details and "q-grid" in details
    assert "src/views/Wide.tsx line 1" in details and "max-width" in details
    assert Path(result["path"]).is_file()

    (src / "views" / "cards.css").unlink()
    (src / "views" / "Wide.tsx").unlink()
    rc, result = build_app(project, fake_env)
    assert rc == 0 and result["checks"]["passed"] is True


@needs_node
def test_the_shipped_layout_and_token_stylesheets_are_not_flagged(project, fake_env):
    rc, result = build_app(project, fake_env, "demo", "--title", "T", "--layout", "dashboard")
    assert rc == 0, result
    assert [f for f in result["checks"]["failures"] if f["check"] == "layout"] == []


def _scaffold_sources() -> list[Path]:
    roots = [APP / "project" / "src", APP / "example" / "src", *sorted((APP / "examples").glob("*/src"))]
    return sorted(p for root in roots for p in root.rglob("*") if p.suffix in (".css", ".tsx"))


def test_every_scaffold_and_example_source_is_clean_under_the_layout_check():
    paths = _scaffold_sources()
    assert any(p.name == "PageLayout.tsx" for p in paths) and len(paths) > 7
    findings = []
    for path in paths:
        root = next(r for r in [APP / "project" / "src", APP / "example" / "src", *(APP / "examples").glob("*/src")] if r in path.parents)
        findings += layoutcheck.check_app_sources([path], root=root)
    assert findings == []


def test_the_scaffold_table_class_is_q_data_grid_everywhere():
    theme = (APP / "project" / "src" / "theme.css").read_text()
    assert ".q-data-grid {" in theme and ".q-data-grid th" in theme
    assert not re.search(r"\.q-grid\b", theme)
    assert "@import './quirk-layout.css';" in theme
    editor = (APP / "example" / "src" / "views" / "EditorView.tsx").read_text()
    assert 'className="q-data-grid"' in editor and 'className="q-grid"' not in editor
    rules = (APP / "rules.md").read_text()
    assert "`q-data-grid`" in rules and not re.search(r"`q-grid`[^.\n]*class", rules)


def test_page_layout_renders_the_region_dom_of_render_regions():
    source = (APP / "project" / "src" / "PageLayout.tsx").read_text()
    for needle in (
        "q-wrap",
        "q-page",
        "data-layout",
        "q-summary",
        'aria-label="Summary"',
        'id="main"',
        "q-nav",
        "q-nav-menu",
        "q-nav-rail",
        "On this page",
        "Sections",
        "q-panel, q-compare, q-tabs, q-board",
    ):
        assert needle in source, needle
    app = (APP / "project" / "src" / "App.tsx").read_text()
    assert "<PageLayout" in app and "quirk-page" in source + app


def test_every_shape_has_an_app_example_overlay():
    names = sorted(p.name for p in (APP / "examples").iterdir() if p.is_dir())
    assert names == sorted(LAYOUTS)
    for name in LAYOUTS:
        overlay = APP / "examples" / name
        assert json.loads((overlay / "quirk-app.json").read_text()) == {"layout": name}
        assert (overlay / "src" / "routes.tsx").is_file()


@pytest.mark.skipif(
    shutil.which("pnpm") is None or os.environ.get("QUIRK_HTML_NETWORK_TESTS") != "1",
    reason="needs pnpm on PATH and QUIRK_HTML_NETWORK_TESTS=1",
)
def test_real_build_of_the_app_template(project, tmp_path):
    env = {**os.environ, "QUIRK_HTML_USER_DIR": str(tmp_path / "user")}
    rc, result = build_app(project, env, "flag-editor", "--title", "Feature flags", "--signal", "editable grid; multiple views")
    assert rc == 0, result
    assert result["checks"]["passed"] is True
    html = Path(result["path"]).read_text()
    assert "flag" in html.lower() and header.read_header(html)["tier"] == 2


@pytest.mark.skipif(
    shutil.which("pnpm") is None or os.environ.get("QUIRK_HTML_NETWORK_TESTS") != "1",
    reason="needs pnpm on PATH and QUIRK_HTML_NETWORK_TESTS=1",
)
@pytest.mark.parametrize("shape", LAYOUTS)
def test_real_build_and_verify_of_each_app_example(project, tmp_path, shape):
    env = {**os.environ, "QUIRK_HTML_USER_DIR": str(tmp_path / "user")}
    src = source_dir(project, shape)
    ignore = shutil.ignore_patterns("node_modules", "dist", ".DS_Store")
    shutil.copytree(APP / "project", src, ignore=ignore)
    shutil.copytree(APP / "examples" / shape, src, ignore=ignore, dirs_exist_ok=True)
    rc, result = build_app(project, env, shape, "--title", f"{shape} example")
    assert rc == 0, result
    assert result["layout"] == shape and result["checks"]["passed"] is True
    html = Path(result["path"]).read_text()
    assert header.read_header(html)["layout"] == shape
    assert "data-layout" in html and "q-page" in html
    proc = subprocess.run(
        [sys.executable, str(CLI), "verify", result["path"]], capture_output=True, text=True, env=env, timeout=600
    )
    report = json.loads(proc.stdout)
    if report["status"] == "not-browser-verified":
        pytest.skip(f"no browser to verify with: {report.get('reason')}")
    assert report["status"] == "passed", report
    assert all(check["passed"] for check in report["checks"].values()), report["checks"]


NAV_PROBE = """
import { chromium } from %(playwright)s;

const [, , file] = process.argv;
const candidates = [{ channel: "chrome" }, { channel: "msedge" }];
if (process.env.CHROME_PATH) candidates.push({ executablePath: process.env.CHROME_PATH });
try {
  candidates.push({ executablePath: chromium.executablePath() });
} catch {}
let browser = null;
for (const options of candidates) {
  try {
    browser = await chromium.launch({ headless: true, ...options });
    break;
  } catch {}
}
if (!browser) process.exit(77);
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
await page.goto("file://" + file);
await page.waitForSelector(".q-nav-rail a");
const current = () =>
  page.$$eval(".q-nav-rail a", (links) => ({
    total: links.length,
    current: links.filter((a) => a.hasAttribute("aria-current")).map((a) => [a.getAttribute("href"), a.getAttribute("aria-current")]),
  }));
const out = { initial: await current() };
await page.evaluate(() => document.getElementById("the-retry-schedule").scrollIntoView());
await page.waitForFunction(() => document.querySelector('.q-nav-rail a[href="#the-retry-schedule"]')?.hasAttribute("aria-current"));
out.middle = await current();
await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
await page.waitForFunction(() => document.querySelector('.q-nav-rail a[href="#what-the-customer-sees"]')?.hasAttribute("aria-current"));
out.bottom = await current();
await browser.close();
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(
    shutil.which("pnpm") is None or NODE is None or os.environ.get("QUIRK_HTML_NETWORK_TESTS") != "1",
    reason="needs node, pnpm on PATH and QUIRK_HTML_NETWORK_TESTS=1",
)
def test_real_build_marks_the_rail_link_of_the_section_being_read(project, tmp_path):
    env = {**os.environ, "QUIRK_HTML_USER_DIR": str(tmp_path / "user")}
    src = source_dir(project, "explainer")
    ignore = shutil.ignore_patterns("node_modules", "dist", ".DS_Store")
    shutil.copytree(APP / "project", src, ignore=ignore)
    shutil.copytree(APP / "examples" / "explainer", src, ignore=ignore, dirs_exist_ok=True)
    rc, result = build_app(project, env, "explainer", "--title", "explainer example")
    assert rc == 0, result
    failure = verify_runner._ensure_installed()
    if failure:
        pytest.skip(f"no playwright to drive a browser with: {failure}")
    playwright = (verify_runner.VERIFY_DIR / "node_modules" / "playwright-core" / "index.mjs").as_uri()
    probe = tmp_path / "probe" / "nav_probe.mjs"
    probe.parent.mkdir()
    probe.write_text(NAV_PROBE % {"playwright": json.dumps(playwright)})
    proc = subprocess.run(
        [NODE, str(probe), str(Path(result["path"]).resolve())], capture_output=True, text=True, env=env, timeout=120
    )
    if proc.returncode == 77:
        pytest.skip("no browser to read the page with")
    assert proc.returncode == 0, proc.stderr
    seen = json.loads(proc.stdout)
    assert seen["initial"]["total"] == 5, seen
    for stage, href in (("middle", "#the-retry-schedule"), ("bottom", "#what-the-customer-sees")):
        assert seen[stage]["current"] == [[href, "location"]], (stage, seen[stage])


WIDTH_PROBE = """
import { chromium } from %(playwright)s;

const [, , file] = process.argv;
const candidates = [{ channel: "chrome" }, { channel: "msedge" }];
if (process.env.CHROME_PATH) candidates.push({ executablePath: process.env.CHROME_PATH });
try {
  candidates.push({ executablePath: chromium.executablePath() });
} catch {}
let browser = null;
for (const options of candidates) {
  try {
    browser = await chromium.launch({ headless: true, ...options });
    break;
  } catch {}
}
if (!browser) process.exit(77);
const out = {};
for (const width of [1800, 2400]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  await page.goto("file://" + file);
  await page.waitForSelector(".q-page");
  out[width] = await page.$eval(".q-page", (el) => {
    const r = el.getBoundingClientRect();
    return { left: r.left, right: r.right, width: r.width };
  });
  await page.close();
}
await browser.close();
console.log(JSON.stringify(out));
"""


def _page_boxes(project: Path, env: dict, tmp_path: Path, shape: str) -> dict:
    src = source_dir(project, shape)
    ignore = shutil.ignore_patterns("node_modules", "dist", ".DS_Store")
    shutil.copytree(APP / "project", src, ignore=ignore)
    shutil.copytree(APP / "examples" / shape, src, ignore=ignore, dirs_exist_ok=True)
    rc, result = build_app(project, env, shape, "--title", f"{shape} example")
    assert rc == 0, result
    failure = verify_runner._ensure_installed()
    if failure:
        pytest.skip(f"no playwright to drive a browser with: {failure}")
    playwright = (verify_runner.VERIFY_DIR / "node_modules" / "playwright-core" / "index.mjs").as_uri()
    probe = tmp_path / f"probe-{shape}" / "width_probe.mjs"
    probe.parent.mkdir()
    probe.write_text(WIDTH_PROBE % {"playwright": json.dumps(playwright)})
    proc = subprocess.run(
        [NODE, str(probe), str(Path(result["path"]).resolve())], capture_output=True, text=True, env=env, timeout=120
    )
    if proc.returncode == 77:
        pytest.skip("no browser to measure the page with")
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.skipif(
    shutil.which("pnpm") is None or NODE is None or os.environ.get("QUIRK_HTML_NETWORK_TESTS") != "1",
    reason="needs node, pnpm on PATH and QUIRK_HTML_NETWORK_TESTS=1",
)
def test_a_report_app_page_is_capped_at_1440_and_centred_on_wide_screens(project, tmp_path):
    env = {**os.environ, "QUIRK_HTML_USER_DIR": str(tmp_path / "user")}
    boxes = _page_boxes(project, env, tmp_path, "report")
    for viewport, box in boxes.items():
        assert box["width"] <= 1440, (viewport, box)
        assert abs(box["left"] - (int(viewport) - box["right"])) <= 1, (viewport, box)


@pytest.mark.skipif(
    shutil.which("pnpm") is None or NODE is None or os.environ.get("QUIRK_HTML_NETWORK_TESTS") != "1",
    reason="needs node, pnpm on PATH and QUIRK_HTML_NETWORK_TESTS=1",
)
def test_a_dashboard_app_page_stays_fluid_past_1440(project, tmp_path):
    env = {**os.environ, "QUIRK_HTML_USER_DIR": str(tmp_path / "user")}
    boxes = _page_boxes(project, env, tmp_path, "dashboard")
    assert boxes["2400"]["width"] > 1440, boxes
