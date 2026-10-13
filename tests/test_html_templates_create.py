"""Tests for `quirk_html.py templates new` and `templates verify` (custom template authoring).

Browser verification is stubbed in-process or made unavailable by running the CLI with an empty
PATH, so no test needs Node, a browser or the network.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import assemble, create, manifest, resolve  # noqa: E402

CLI = SKILL / "scripts" / "quirk_html.py"

SRC = """<!-- quirk-src {"template": "report", "title": "Weekly notes", "mode": "offline", "libraries": []} -->
<!-- slot: main -->
<p class="q-lede">Nothing broke this week.</p>
"""

PLAIN = """<!doctype html>
<html><head><title>Status board</title><style>body { color: red; }</style></head>
<body>
<h2>Services</h2>
<p>All green.</p>
</body></html>
"""

NOT_VERIFIED = {
    "status": "not-browser-verified",
    "file_sha256": None,
    "browser": None,
    "checks": {},
    "screenshots": ["/gone/shot.png"],
    "requests": [],
    "reason": "no-browser",
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    user = tmp_path / "user-templates"
    empty_bin = tmp_path / "emptybin"
    empty_bin.mkdir()
    monkeypatch.setenv("QUIRK_HTML_USER_DIR", str(user))
    project = tmp_path / "project"
    project.mkdir()
    return {"project": project, "user": user, "bin": empty_bin, "tmp": tmp_path}


def run_cli(env, *args, path_override=True):
    environ = {**os.environ, "QUIRK_HTML_USER_DIR": str(env["user"])}
    if path_override:
        environ["PATH"] = str(env["bin"])
    proc = subprocess.run(
        [sys.executable, str(CLI), *args], capture_output=True, text=True, env=environ, timeout=120
    )
    assert proc.stdout.strip().count("\n") == 0, proc.stdout
    return proc.returncode, json.loads(proc.stdout)


def new(env, name, *extra, level="project"):
    return run_cli(env, "templates", "new", name, "--level", level, "--project-dir", str(env["project"]), *extra)


def verify(env, name):
    return run_cli(env, "templates", "verify", name, "--project-dir", str(env["project"]))


def listing(env):
    code, out = run_cli(env, "templates", "list", "--project-dir", str(env["project"]))
    assert code == 0
    return out


def stub_browser(monkeypatch, result=None):
    monkeypatch.setattr(create.verify_runner, "run_verify", lambda *a, **k: dict(result or NOT_VERIFIED))


def verify_in_process(env, name):
    return create.verify_template(name, project_dir=env["project"], user_dir=env["user"])


def test_new_copies_the_default_base_and_renames_it(env):
    code, out = new(env, "mine")
    dest = env["project"] / ".quirk" / "html-templates" / "mine"
    assert code == 0
    assert out["path"] == str(dest)
    assert isinstance(out["next"], list) and out["next"]
    meta = json.loads((dest / "template.json").read_text())
    assert meta["name"] == "mine" and meta["tier"] == 1
    assert not (dest / "verified.json").exists()
    example = (dest / "example.src.html").read_text()
    assert example.splitlines()[0].startswith('<!-- quirk-src {"template": "mine"')
    assert "<!-- slot: main -->" in example
    code, checked = run_cli(env, "templates", "validate", str(dest))
    assert (code, checked) == (0, {"valid": True, "errors": []})


def test_new_at_user_level_uses_the_user_dir(env):
    code, out = new(env, "shared", level="user")
    assert code == 0
    assert out["path"] == str(env["user"] / "shared")
    assert not (env["project"] / ".quirk").exists()


def test_new_from_a_named_base(env):
    code, _ = new(env, "tabs", "--base", "components")
    meta = json.loads((env["project"] / ".quirk/html-templates/tabs/template.json").read_text())
    assert code == 0 and meta["libraries"] == ["webawesome", "alpine"]


def test_new_refuses_an_existing_name(env):
    assert new(env, "mine")[0] == 0
    marker = env["project"] / ".quirk/html-templates/mine/marker.txt"
    marker.write_text("keep")
    code, out = new(env, "mine")
    assert code == 2 and "already exists" in out["error"]
    assert marker.read_text() == "keep"


def test_new_rejects_a_bad_name_and_an_unknown_base(env):
    assert new(env, "Bad Name")[0] == 2
    code, out = new(env, "x", "--base", "no-such-template")
    assert code == 2 and "no-such-template" in out["error"]
    assert not (env["project"] / ".quirk/html-templates/x").exists()


def test_new_rejects_base_together_with_from(env):
    page = env["tmp"] / "page.html"
    page.write_text(PLAIN)
    code, out = new(env, "x", "--base", "report", "--from", str(page))
    assert code == 2 and "--base" in out["error"]


def build_artifact(env, slug="notes", write_src=True):
    html_dir = env["project"] / ".quirk" / "html"
    html_dir.mkdir(parents=True)
    src = html_dir / f"{slug}.src.html"
    src.write_text(SRC)
    code, built = run_cli(env, "build", str(src), "--project-dir", str(env["project"]))
    assert code == 0, built
    if not write_src:
        src.unlink()
    return Path(built["path"])


def test_from_a_quirk_built_artifact_copies_its_template_and_source(env):
    artifact = build_artifact(env)
    code, out = new(env, "notes-kit", "--from", str(artifact))
    dest = env["project"] / ".quirk/html-templates/notes-kit"
    assert code == 0, out
    meta = json.loads((dest / "template.json").read_text())
    assert meta["name"] == "notes-kit" and list(meta["slots"]) == ["main", "aside"]
    example = (dest / "example.src.html").read_text()
    assert example.startswith('<!-- quirk-src {"template": "notes-kit", "title": "Weekly notes"')
    assert '<p class="q-lede">Nothing broke this week.</p>' in example
    assert (dest / "skeleton.html").read_text() == (SKILL / "templates/report/skeleton.html").read_text()
    assert not any("by hand" in step for step in out["next"])


def test_from_a_quirk_built_artifact_without_its_source_says_so(env):
    artifact = build_artifact(env, write_src=False)
    code, out = new(env, "notes-kit", "--from", str(artifact))
    dest = env["project"] / ".quirk/html-templates/notes-kit"
    assert code == 0, out
    assert any("by hand" in step and "notes.src.html" in step for step in out["next"])
    assert (dest / "example.src.html").read_text().startswith('<!-- quirk-src {"template": "notes-kit"')


def test_from_a_source_with_data_keeps_the_data_beside_the_example(env):
    html_dir = env["project"] / ".quirk" / "html"
    html_dir.mkdir(parents=True)
    (html_dir / "t.data.json").write_text('[{"a": 1}]')
    (html_dir / "t.src.html").write_text(SRC.replace('"libraries": []', '"libraries": [], "data": "t.data.json"'))
    code, built = run_cli(env, "build", str(html_dir / "t.src.html"), "--project-dir", str(env["project"]))
    assert code == 0, built
    code, out = new(env, "with-data", "--from", built["path"])
    dest = env["project"] / ".quirk/html-templates/with-data"
    assert code == 0, out
    assert json.loads((dest / "example.data.json").read_text()) == [{"a": 1}]
    assert '"data": "example.data.json"' in (dest / "example.src.html").read_text()
    assert manifest.validate_template(dest, require_verified=False) == []


def test_from_plain_html_makes_a_one_slot_skeleton_that_validates(env):
    page = env["tmp"] / "board.html"
    page.write_text(PLAIN)
    code, out = new(env, "board", "--from", str(page))
    dest = env["project"] / ".quirk/html-templates/board"
    assert code == 0, out
    meta = json.loads((dest / "template.json").read_text())
    assert meta["tier"] == 1 and list(meta["slots"]) == ["main"] and meta["tokens"] == "tokens.json"
    assert (dest / "tokens.json").read_text() == (SKILL / "theme/house.tokens.json").read_text()
    example = (dest / "example.src.html").read_text()
    assert example.startswith('<!-- quirk-src {"template": "board", "title": "Status board"')
    assert "<h2>Services</h2>" in example and "color: red" not in example
    assert not (dest / "verified.json").exists()
    code, checked = run_cli(env, "templates", "validate", str(dest))
    assert (code, checked) == (0, {"valid": True, "errors": []})


def test_from_plain_html_without_a_body_tag_uses_the_markup(env):
    page = env["tmp"] / "frag.html"
    page.write_text("<h2>Only a fragment</h2><p>text</p>")
    code, _ = new(env, "frag", "--from", str(page))
    example = (env["project"] / ".quirk/html-templates/frag/example.src.html").read_text()
    assert code == 0 and "<h2>Only a fragment</h2>" in example and '"title": "frag"' in example


def test_from_a_missing_file_is_a_usage_error(env):
    code, out = new(env, "x", "--from", str(env["tmp"] / "nope.html"))
    assert code == 2 and "error" in out


def test_unverified_template_is_skipped_by_list(env):
    new(env, "mine")
    out = listing(env)
    assert "mine" not in [t["name"] for t in out["templates"]]
    skipped = [w for w in out["warnings"] if w["name"] == "mine"]
    assert len(skipped) == 1 and skipped[0]["level"] == "project" and "unverified" in skipped[0]["reason"]


def test_verify_without_a_browser_passes_and_lists_the_template(env):
    new(env, "mine")
    code, out = verify(env, "mine")
    assert code == 0, out
    assert out["passed"] is True and out["browser"] is False
    assert out["report"]["checks"]["passed"] is True
    assert out["report"]["verify"]["status"] == "not-browser-verified"
    stamp = json.loads((env["project"] / ".quirk/html-templates/mine/verified.json").read_text())
    assert stamp["schema"] == 1 and stamp["browser"] is False and stamp["verified_at"].endswith("Z")
    listed = {t["name"]: t for t in listing(env)["templates"]}
    assert listed["mine"]["level"] == "project"


def test_verified_json_hashes_cover_the_files_the_manifest_names(env, monkeypatch):
    new(env, "mine")
    stub_browser(monkeypatch)
    result = verify_in_process(env, "mine")
    dest = env["project"] / ".quirk/html-templates/mine"
    stamp = json.loads((dest / "verified.json").read_text())
    assert result["passed"] is True
    assert set(stamp["hashes"]) == set(manifest.verification_paths(dest))
    assert {"template.json", "skeleton.html", "rules.md", "example.src.html"} <= set(stamp["hashes"])
    assert stamp["hashes"] == manifest.compute_hashes(dest)
    assert manifest.validate_template(dest, require_verified=True) == []


def test_verified_json_covers_the_tokens_of_a_skeleton_template(env):
    page = env["tmp"] / "board.html"
    page.write_text(PLAIN)
    new(env, "board", "--from", str(page))
    code, out = verify(env, "board")
    assert code == 0, out
    stamp = json.loads((env["project"] / ".quirk/html-templates/board/verified.json").read_text())
    assert set(stamp["hashes"]) == {"template.json", "skeleton.html", "tokens.json", "example.src.html"}


def test_a_real_browser_pass_records_browser_true(env, monkeypatch):
    new(env, "mine")
    stub_browser(monkeypatch, {**NOT_VERIFIED, "status": "passed", "browser": "chromium"})
    result = verify_in_process(env, "mine")
    stamp = json.loads((env["project"] / ".quirk/html-templates/mine/verified.json").read_text())
    assert result["passed"] is True and result["browser"] is True and stamp["browser"] is True
    assert "screenshots" not in result["report"]["verify"]


def test_a_failed_browser_check_writes_no_verified_json(env, monkeypatch):
    new(env, "mine")
    stub_browser(monkeypatch, {**NOT_VERIFIED, "status": "failed"})
    result = verify_in_process(env, "mine")
    assert result["passed"] is False and result["browser"] is False
    assert not (env["project"] / ".quirk/html-templates/mine/verified.json").exists()


def test_a_failed_static_check_fails_the_verify(env):
    page = env["tmp"] / "ext.html"
    page.write_text('<body><p>hi</p><script src="https://cdn.example.com/x.js"></script></body>')
    new(env, "ext", "--from", str(page))
    code, out = verify(env, "ext")
    assert code == 1 and out["passed"] is False
    assert out["report"]["checks"]["passed"] is False
    assert not (env["project"] / ".quirk/html-templates/ext/verified.json").exists()


def test_an_example_naming_another_template_fails(env):
    new(env, "mine")
    example = env["project"] / ".quirk/html-templates/mine/example.src.html"
    example.write_text(example.read_text().replace('"template": "mine"', '"template": "report"', 1))
    code, out = verify(env, "mine")
    assert code == 1 and out["passed"] is False
    assert "report" in out["report"]["error"] and out["report"]["stage"] == "build"


def test_an_example_that_does_not_build_fails(env):
    new(env, "mine")
    example = env["project"] / ".quirk/html-templates/mine/example.src.html"
    example.write_text(example.read_text().replace("<!-- slot: main -->", "<!-- slot: nope -->"))
    code, out = verify(env, "mine")
    assert code == 1 and out["report"]["stage"] == "build"


def test_editing_a_verified_template_makes_it_unverified_again(env):
    page = env["tmp"] / "board.html"
    page.write_text(PLAIN)
    new(env, "board", "--from", str(page))
    assert verify(env, "board")[0] == 0
    assert "board" in [t["name"] for t in listing(env)["templates"]]
    skeleton = env["project"] / ".quirk/html-templates/board/skeleton.html"
    skeleton.write_text(skeleton.read_text() + "<!-- edited -->\n")
    out = listing(env)
    assert "board" not in [t["name"] for t in out["templates"]]
    assert "unverified" in next(w for w in out["warnings"] if w["name"] == "board")["reason"]
    assert verify(env, "board")[0] == 0
    assert "board" in [t["name"] for t in listing(env)["templates"]]


def test_verify_resolves_project_before_user_and_skips_built_ins(env):
    new(env, "same", level="user")
    new(env, "same")
    assert verify(env, "same")[0] == 0
    assert (env["project"] / ".quirk/html-templates/same/verified.json").is_file()
    assert not (env["user"] / "same" / "verified.json").exists()
    assert verify(env, "report")[0] == 2


def test_verify_finds_a_user_level_template(env):
    new(env, "shared", level="user")
    code, out = verify(env, "shared")
    assert code == 0, out
    assert (env["user"] / "shared" / "verified.json").is_file()


def test_verify_an_unknown_or_invalid_template_is_a_usage_error(env):
    code, out = verify(env, "ghost")
    assert code == 2 and "ghost" in out["error"]
    new(env, "broken")
    (env["project"] / ".quirk/html-templates/broken/skeleton.html").write_text("<p>no placeholders</p>")
    code, out = verify(env, "broken")
    assert code == 2 and "skeleton is missing" in out["error"]


def test_a_new_tier_2_template_verifies_as_failed_when_tier_2_is_unavailable(env):
    code, out = new(env, "my-app", "--base", "app")
    dest = env["project"] / ".quirk/html-templates/my-app"
    assert code == 0, out
    assert (dest / "project" / "package.json").is_file() and (dest / "example" / "src").is_dir()
    assert not (dest / "project" / "node_modules").exists()
    assert manifest.validate_template(dest, require_verified=False) == []
    code, out = verify(env, "my-app")
    assert code == 1 and out["passed"] is False
    assert out["report"]["stage"] == "build" and out["report"]["reason"] == "no-node"


def test_the_scratch_build_leaves_no_output_in_the_project(env, monkeypatch):
    new(env, "mine")
    stub_browser(monkeypatch)
    verify_in_process(env, "mine")
    assert not (env["project"] / ".quirk" / "html").exists()


def test_the_module_matches_what_the_cli_resolves(env):
    new(env, "mine")
    roots = resolve.template_roots(SKILL, env["project"], env["user"])
    _, warnings = resolve.list_templates(roots, skill_dir=SKILL)
    assert [w["name"] for w in warnings] == ["mine"]
    assert assemble.BuildError is create.BuildError


def _tier2_skeleton(root: Path, extra: dict[str, str]) -> Path:
    tdir = root / "kit"
    (tdir / "project").mkdir(parents=True)
    (tdir / "template.json").write_text(json.dumps({"tier": 2, "name": "kit", "project": "project/"}))
    for rel, text in {"project/package.json": "{}", "project/pnpm-lock.yaml": "", **extra}.items():
        path = tdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return tdir


def test_copy_keeps_a_vendored_dist_path_in_a_tier_1_template(tmp_path):
    tdir = tmp_path / "t1"
    (tdir / "vendor" / "chart" / "1.0" / "dist").mkdir(parents=True)
    (tdir / "vendor" / "chart" / "1.0" / "dist" / "chart.js").write_text("lib")
    (tdir / "vendor" / "chart" / "node_modules").mkdir()
    (tdir / "vendor" / "chart" / "node_modules" / "x.js").write_text("x")
    (tdir / "vendor" / "chart" / "verified.json").write_text("{}")
    (tdir / "template.json").write_text(json.dumps({"tier": 1, "name": "t1"}))
    (tdir / "verified.json").write_text("{}")
    dest = tmp_path / "copy"
    create._copy_tree(tdir, dest)
    assert (dest / "vendor/chart/1.0/dist/chart.js").read_text() == "lib"
    assert (dest / "vendor/chart/node_modules/x.js").is_file()
    assert (dest / "vendor/chart/verified.json").is_file()
    assert not (dest / "verified.json").exists()


def test_copy_skips_build_output_only_under_a_tier_2_project(tmp_path):
    tdir = _tier2_skeleton(
        tmp_path,
        {
            "project/node_modules/dep/index.js": "x",
            "project/dist/index.html": "old",
            "project/src/dist/keep.ts": "x",
            "example/dist/kept.txt": "kept",
            "verified.json": "{}",
        },
    )
    dest = tmp_path / "copy"
    create._copy_tree(tdir, dest)
    assert (dest / "project/package.json").is_file()
    assert not (dest / "project/node_modules").exists() and not (dest / "project/dist").exists()
    assert not (dest / "project/src/dist").exists()
    assert (dest / "example/dist/kept.txt").is_file()
    assert not (dest / "verified.json").exists()


def test_a_custom_template_with_a_vendored_dist_path_verifies(env, monkeypatch):
    assert new(env, "mine")[0] == 0
    dest = env["project"] / ".quirk/html-templates/mine"
    (dest / "vendor/chart/1.0/dist").mkdir(parents=True)
    (dest / "vendor/chart/1.0/dist/chart.js").write_text("lib")
    stub_browser(monkeypatch)
    assert verify_in_process(env, "mine")["passed"] is True
    stamp = json.loads((dest / "verified.json").read_text())
    assert "vendor/chart/1.0/dist/chart.js" in stamp["hashes"]
    assert manifest.validate_template(dest, require_verified=True) == []


@pytest.mark.parametrize("reason", ["no-node", "no-browser", "install-failed"])
def test_environment_limits_still_pass_without_a_browser(env, monkeypatch, reason):
    new(env, "mine")
    stub_browser(monkeypatch, {**NOT_VERIFIED, "reason": reason})
    result = verify_in_process(env, "mine")
    assert result["passed"] is True and result["browser"] is False
    assert (env["project"] / ".quirk/html-templates/mine/verified.json").is_file()


@pytest.mark.parametrize("reason", ["verify-crashed", "verify-timeout", "missing-file"])
def test_a_verifier_crash_or_timeout_does_not_pass(env, monkeypatch, reason):
    new(env, "mine")
    stub_browser(monkeypatch, {**NOT_VERIFIED, "reason": reason})
    result = verify_in_process(env, "mine")
    assert result["passed"] is False and result["browser"] is False
    assert result["report"]["verify"]["reason"] == reason
    assert not (env["project"] / ".quirk/html-templates/mine/verified.json").exists()


def test_companion_is_refused_as_a_base(env):
    code, out = new(env, "screens", "--base", "companion")
    assert code == 2 and "companion" in out["error"] and "not a base" in out["error"]
    assert not (env["project"] / ".quirk/html-templates/screens").exists()


def test_a_companion_screen_is_refused_as_a_from_source(env):
    screen = env["tmp"] / "screen.html"
    screen.write_text('<!doctype html>\n<!-- quirk-html-artifact {"template": "companion", "tier": 1} -->\n<html><body>q</body></html>\n')
    code, out = new(env, "screens", "--from", str(screen))
    assert code == 2 and "companion" in out["error"]
    assert not (env["project"] / ".quirk/html-templates/screens").exists()


def test_from_a_source_whose_data_is_outside_the_allowed_directories_copies_nothing(env):
    secret = env["tmp"] / "secret.json"
    secret.write_text('{"token": "hunter2"}')
    elsewhere = env["tmp"] / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "t.src.html").write_text(SRC.replace('"libraries": []', f'"libraries": [], "data": "{secret}"'))
    artifact = elsewhere / "t.html"
    artifact.write_text('<!doctype html>\n<!-- quirk-html-artifact {"template": "report", "tier": 1} -->\n<html><body>x</body></html>\n')
    code, out = new(env, "leak", "--from", str(artifact))
    dest = env["project"] / ".quirk/html-templates/leak"
    assert code == 0, out
    assert not list(dest.glob("example.data.*"))
    example = (dest / "example.src.html").read_text()
    assert "hunter2" not in example and '"data"' not in example
    assert any("outside" in step and "not copied" in step for step in out["next"])
