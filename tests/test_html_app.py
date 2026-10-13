"""Tests for the tier-2 `app` template and `quirk_html.py build-app`.

Most builds run against a fake `pnpm` on PATH so no test needs Node packages or the network.
The one real build is skipped unless pnpm is on PATH and QUIRK_HTML_NETWORK_TESTS=1.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import header, manifest  # noqa: E402

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
    Path("dist/index.html").write_text(os.environ.get("FAKE_PNPM_HTML", {html!r}))
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
        ["install", "--frozen-lockfile", "--ignore-scripts"],
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
def test_upgrade_is_reported_as_a_no_op_for_tier_2(project, fake_env):
    rc, result = build_app(project, fake_env, "demo", "--title", "Demo", "--upgrade")
    assert rc == 0 and any("--upgrade" in w for w in result["warnings"])


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
    assert pnpm_calls(fake_env)[0] == ["install", "--frozen-lockfile", "--ignore-scripts"]
    assert json.loads((src / "quirk-app.json").read_text())["template"] == "mini"


@needs_node
def test_tier_1_template_is_refused_by_build_app(project, fake_env):
    rc, result = build_app(project, fake_env, "demo", "--title", "Demo", "--template", "report")
    assert rc == 2 and "tier 1" in result["error"]
    assert not source_dir(project).exists()


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
