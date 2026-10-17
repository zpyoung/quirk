"""Tests for the tier-1 builder, the quirk_html CLI and the report and components templates.

Builds run against the skill's real vendor store and built-in templates; custom templates,
fake vendor registries, data files and projects live under tmp_path. No test needs a browser
or the network.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import assemble, header, manifest, vendor, verify_runner  # noqa: E402

CLI = SKILL / "scripts" / "quirk_html.py"
DATA_BLOCK = re.compile(r'<script type="application/json" id="quirk-data">([\[{].*?)</script>', re.S)
BUILTINS = ("report", "components")
REAL_STORE = vendor.VendorStore([SKILL / "vendor" / "libraries.json"])

SKELETON = (
    "<!doctype html>\n{{header}}\n<html lang=\"en\"><head><title>{{title}}</title>{{head}}</head>\n"
    "<body>{{chrome}}<main>{{slot:main}}</main>{{data}}{{body_end}}</body></html>\n"
)
DESCRIPTION = "Use when you need a fixture template for the builder tests."


@pytest.fixture
def env(tmp_path: Path) -> dict:
    user = tmp_path / "user-templates"
    user.mkdir()
    return {**os.environ, "QUIRK_HTML_USER_DIR": str(user)}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    return proj


def run_cli(*args: object, env: dict | None = None, cwd: Path | None = None) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(CLI), *map(str, args)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd) if cwd else None,
        timeout=120,
    )
    out = proc.stdout.strip()
    assert out, f"no stdout (rc={proc.returncode}): {proc.stderr}"
    return proc.returncode, json.loads(out)


def build(src: Path, out: Path, env: dict, project: Path, *extra: str) -> tuple[int, dict]:
    return run_cli("build", src, "--out", out, "--project-dir", project, *extra, env=env)


def write_src(path: Path, meta: dict, slots: dict[str, str]) -> Path:
    if "main" in slots and "summary" not in slots:
        slots = {**slots, "summary": "<p>Summary.</p>"}
    parts = [f"<!-- quirk-src {json.dumps(meta)} -->"]
    for name, body in slots.items():
        parts.append(f"<!-- slot: {name} -->")
        parts.append(body)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fake_registry(root: Path, versions: dict[str, str], current: str) -> None:
    """Write root/vendor/libraries.json with a one-file JS library called fakelib."""
    entries = {}
    for version, body in versions.items():
        vdir = root / "vendor" / "fakelib" / version
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "LICENSE").write_text("MIT License\n\nCopyright (c) 2024 Fake Authors\n", encoding="utf-8")
        (vdir / "fake.js").write_text(body, encoding="utf-8")
        entries[version] = {
            "package": "fakelib",
            "license": "MIT",
            "license_file": "LICENSE",
            "files": [
                {
                    "path": "fake.js",
                    "kind": "js",
                    "sha256": sha(body),
                    "inline_sha256": sha(vendor.escape_inline(body, "js")),
                    "position": "body-end",
                    "inline": True,
                }
            ],
        }
    registry = {"schema": 1, "libraries": {"fakelib": {"current": current, "versions": entries}}}
    (root / "vendor" / "libraries.json").write_text(json.dumps(registry), encoding="utf-8")


def seal(tdir: Path) -> None:
    hashes = manifest.compute_hashes(tdir)
    (tdir / "verified.json").write_text(
        json.dumps({"schema": 1, "verified_at": "2026-10-13T00:00:00Z", "browser": False, "hashes": hashes}),
        encoding="utf-8",
    )


def custom_template(project: Path, name: str = "fx", skeleton: str = SKELETON, libraries: list[str] | None = None) -> Path:
    tdir = project / ".quirk" / "html-templates" / name
    tdir.mkdir(parents=True)
    meta = {
        "schema": 1,
        "name": name,
        "description": DESCRIPTION,
        "tier": 1,
        "libraries": libraries if libraries is not None else [],
        "slots": {"main": {"required": True, "description": "Main content."}},
        "skeleton": "skeleton.html",
        "example": "example.src.html",
    }
    (tdir / "template.json").write_text(json.dumps(meta), encoding="utf-8")
    (tdir / "skeleton.html").write_text(skeleton, encoding="utf-8")
    write_src(tdir / "example.src.html", {"template": name, "title": "Fixture"}, {"main": "<p>Hello.</p>"})
    return tdir


def example_src(name: str) -> Path:
    return SKILL / "templates" / name / "example.src.html"


@pytest.mark.parametrize("name", BUILTINS)
def test_builtin_example_builds_and_passes_check(name, tmp_path, env, project):
    out = tmp_path / f"{name}.html"
    rc, result = build(example_src(name), out, env, project)
    assert rc == 0, result
    assert result["checks"]["passed"] is True, result["checks"]
    assert result["template"] == name
    assert result["template_level"] == "builtin"
    assert result["tier"] == 1
    assert result["tier_signal"] is None
    assert result["mode"] == "offline"
    assert result["source_dir"] is None and result["cut"] == []
    assert result["path"] == str(out) and result["size"] == out.stat().st_size

    rc, check = run_cli("check", out, env=env)
    assert rc == 0 and check["passed"] is True, check

    meta = header.read_header(out.read_text(encoding="utf-8"))
    assert meta["template"] == name and meta["sidecar"] is None
    for lib, version in meta["libraries"].items():
        assert version == REAL_STORE.resolve(lib, None).version


@pytest.mark.parametrize("name", BUILTINS)
def test_builtin_templates_validate_and_resolve_libraries(name, env, project):
    tdir = SKILL / "templates" / name
    assert manifest.validate_template(tdir, require_verified=False) == []
    tpl = manifest.load_template(tdir)
    assert tpl.description.startswith("Use when")
    for lib in tpl.libraries + tpl.optional_libraries:
        REAL_STORE.inline_blocks(REAL_STORE.resolve(lib, None))
    assert (tdir / "rules.md").is_file() and (tdir / "example.src.html").is_file()

    rc, result = run_cli("templates", "validate", tdir, env=env)
    assert rc == 0 and result == {"valid": True, "errors": []}

    rc, listing = run_cli("templates", "list", "--project-dir", project, env=env)
    assert rc == 0 and listing["warnings"] == []
    row = next(t for t in listing["templates"] if t["name"] == name)
    assert row["level"] == "builtin" and row["tier"] == 1 and row["path"] == str(tdir)


def test_report_template_declares_its_contract():
    tpl = manifest.load_template(SKILL / "templates" / "report")
    assert tpl.libraries == ["simple-css", "alpine"]
    assert tpl.optional_libraries == ["chartjs", "mermaid"]
    assert tpl.slots["main"]["required"] is True and "aside" not in tpl.slots
    rules = (SKILL / "templates" / "report" / "rules.md").read_text(encoding="utf-8")
    assert "q-chart" in rules and "references/components.md" in rules


def test_components_rules_point_at_the_kit_reference():
    rules = (SKILL / "templates" / "components" / "rules.md").read_text(encoding="utf-8")
    assert "q-chart" in rules and "references/components.md" in rules


def test_components_template_declares_its_contract():
    tpl = manifest.load_template(SKILL / "templates" / "components")
    assert tpl.libraries == ["webawesome", "alpine"]
    assert tpl.optional_libraries == ["chartjs", "mermaid"]
    assert list(tpl.slots) == ["main"] and tpl.slots["main"]["required"] is True


def test_library_order_puts_alpine_last_then_chrome(tmp_path, env, project):
    out = tmp_path / "report.html"
    rc, result = build(example_src("report"), out, env, project)
    assert rc == 0
    html = out.read_text(encoding="utf-8")
    assert list(result["libraries"]) == ["simple-css", "chartjs", "kit", "alpine"]
    chart = html.index('<script data-quirk-lib="chartjs@')
    kit = html.index('<script data-quirk-lib="kit@')
    alpine = html.index('<script data-quirk-lib="alpine@')
    chrome = html.index('<script data-quirk-shell="chrome">')
    assert chart < kit < alpine < chrome
    assert html.index('<style data-quirk-lib="simple-css@') < html.index("--q-color-bg")
    assert html.index("<!-- license: simple-css") < html.index("<html")
    assert html.startswith("<!doctype html>\n<!-- quirk-html-artifact ")


def test_default_output_goes_to_self_ignoring_quirk_html(tmp_path, env, project):
    src = write_src(tmp_path / "plain.src.html", {"template": "report", "title": "Plain page"}, {"main": "<p>Body.</p>"})
    rc, result = run_cli("build", src, "--project-dir", project, env=env)
    assert rc == 0, result
    out_dir = project / ".quirk" / "html"
    assert result["path"] == str(out_dir / "plain.html")
    assert (out_dir / ".gitignore").read_text(encoding="utf-8").strip() == "*"


def test_explicit_out_does_not_drop_a_gitignore_there(tmp_path, env, project):
    src = write_src(tmp_path / "plain.src.html", {"template": "report", "title": "Plain page"}, {"main": "<p>Body.</p>"})
    out_dir = tmp_path / "elsewhere"
    rc, _ = build(src, out_dir / "x.html", env, project)
    assert rc == 0 and not (out_dir / ".gitignore").exists()


def test_tier_reason_becomes_a_judgment_signal(tmp_path, env, project):
    meta = {"template": "report", "title": "Plain page", "tier_reason": "single form, no app state"}
    src = write_src(tmp_path / "p.src.html", meta, {"main": "<p>Body.</p>"})
    rc, result = build(src, tmp_path / "p.html", env, project)
    assert rc == 0
    assert result["tier_signal"] == "judgment: single form, no app state"
    assert header.read_header((tmp_path / "p.html").read_text(encoding="utf-8"))["tier_signal"] == result["tier_signal"]


def test_title_is_escaped_in_head_and_slot_content_is_not_resubstituted(tmp_path, env, project):
    src = write_src(
        tmp_path / "p.src.html",
        {"template": "report", "title": "A <b> & B"},
        {"main": "<p>Literal {{title}} stays.</p>"},
    )
    rc, _ = build(src, tmp_path / "p.html", env, project)
    assert rc == 0
    html = (tmp_path / "p.html").read_text(encoding="utf-8")
    assert "<title>A &lt;b&gt; &amp; B</title>" in html
    assert "Literal {{title}} stays." in html


def test_small_data_is_embedded_with_lt_escaped(tmp_path, env, project):
    data = {"rows": [{"name": "</script><b>x", "ms": 5}]}
    (tmp_path / "d.json").write_text(json.dumps(data), encoding="utf-8")
    src = write_src(tmp_path / "d.src.html", {"template": "report", "title": "Data", "data": "d.json"}, {"main": "<p>x</p>"})
    rc, result = build(src, tmp_path / "d.html", env, project)
    assert rc == 0 and result["sidecar"] is None
    html = (tmp_path / "d.html").read_text(encoding="utf-8")
    block = DATA_BLOCK.search(html)
    assert block and "<" not in block.group(1)
    assert json.loads(block.group(1)) == data
    assert '<div class="q-data-picker">' not in html


def test_csv_data_is_embedded_as_row_objects(tmp_path, env, project):
    (tmp_path / "d.csv").write_text("name,ms\nalpha,5\n\"be,ta\",7\n", encoding="utf-8")
    src = write_src(tmp_path / "c.src.html", {"template": "report", "title": "Data", "data": "d.csv"}, {"main": "<p>x</p>"})
    rc, _ = build(src, tmp_path / "c.html", env, project)
    assert rc == 0
    html = (tmp_path / "c.html").read_text(encoding="utf-8")
    block = DATA_BLOCK.search(html)
    assert json.loads(block.group(1)) == [{"name": "alpha", "ms": "5"}, {"name": "be,ta", "ms": "7"}]


def test_oversized_data_moves_to_a_sidecar_with_a_picker(tmp_path, env, project):
    big = tmp_path / "big.json"
    big.write_text(json.dumps({"blob": ["x" * 1000] * 11_000}), encoding="utf-8")
    assert big.stat().st_size > checks_size_fail()
    src = write_src(tmp_path / "b.src.html", {"template": "report", "title": "Big", "data": "big.json"}, {"main": "<p>x</p>"})
    out = tmp_path / "out" / "b.html"
    rc, result = build(src, out, env, project)
    assert rc == 0, result
    sidecar = out.parent / "b.data.json"
    assert result["sidecar"] == str(sidecar) and sidecar.read_bytes() == big.read_bytes()
    html = out.read_text(encoding="utf-8")
    assert '<div class="q-data-picker">' in html
    assert DATA_BLOCK.search(html) is None
    assert header.read_header(html)["sidecar"] == "b.data.json"
    assert result["size"] < checks_size_fail() and result["checks"]["passed"] is True


def checks_size_fail() -> int:
    from htmlkit import checks

    return checks.SIZE_FAIL


def test_unknown_placeholder_in_skeleton_is_exit_2(tmp_path, env, project):
    custom_template(project, skeleton=SKELETON.replace("<main>", "<main>{{bogus}}"))
    seal(project / ".quirk" / "html-templates" / "fx")
    src = write_src(tmp_path / "u.src.html", {"template": "fx", "title": "T"}, {"main": "<p>x</p>"})
    rc, result = build(src, tmp_path / "u.html", env, project)
    assert rc == 2 and "{{bogus}}" in result["error"]
    assert not (tmp_path / "u.html").exists()


def test_missing_required_slot_is_exit_2(tmp_path, env, project):
    src = write_src(tmp_path / "m.src.html", {"template": "report", "title": "T"}, {"summary": "<p>x</p>"})
    rc, result = build(src, tmp_path / "m.html", env, project)
    assert rc == 2 and "main" in result["error"]


def test_undeclared_slot_and_unlisted_library_are_exit_2(tmp_path, env, project):
    src = write_src(tmp_path / "s.src.html", {"template": "report", "title": "T"}, {"main": "x", "extra": "y"})
    rc, result = build(src, tmp_path / "s.html", env, project)
    assert rc == 2 and "extra" in result["error"]
    src = write_src(tmp_path / "l.src.html", {"template": "report", "title": "T", "libraries": ["webawesome"]}, {"main": "x"})
    rc, result = build(src, tmp_path / "l.html", env, project)
    assert rc == 2 and "webawesome" in result["error"]


def test_invalid_project_template_shadowing_report_falls_back_with_warning(tmp_path, env, project):
    bad = project / ".quirk" / "html-templates" / "report"
    bad.mkdir(parents=True)
    (bad / "template.json").write_text("{}", encoding="utf-8")

    rc, listing = run_cli("templates", "list", "--project-dir", project, env=env)
    assert rc == 0
    assert [w["level"] for w in listing["warnings"]] == ["project"]
    assert listing["warnings"][0]["name"] == "report" and listing["warnings"][0]["path"] == str(bad)
    assert next(t for t in listing["templates"] if t["name"] == "report")["level"] == "builtin"

    rc, result = build(example_src("report"), tmp_path / "r.html", env, project)
    assert rc == 0 and result["template_level"] == "builtin"
    assert any("project" in w and "report" in w for w in result["warnings"]), result["warnings"]


def test_user_level_template_is_used_and_recorded(tmp_path, env, project):
    user_root = Path(env["QUIRK_HTML_USER_DIR"])
    tdir = custom_template(user_root.parent / "scratch", name="fx")
    target = user_root / "fx"
    tdir.rename(target)
    seal(target)
    src = write_src(tmp_path / "f.src.html", {"template": "fx", "title": "T"}, {"main": "<p>x</p>"})
    rc, result = build(src, tmp_path / "f.html", env, project)
    assert rc == 0 and result["template_level"] == "user", result


def test_frozen_versions_hold_until_upgrade(tmp_path, env, project):
    tdir = custom_template(project, libraries=["fakelib"])
    fake_registry(tdir, {"1.0.0": "window.fakeVersion = 1;\n"}, current="1.0.0")
    seal(tdir)
    src = write_src(tmp_path / "v.src.html", {"template": "fx", "title": "T"}, {"main": "<p>x</p>"})
    out = tmp_path / "v.html"
    rc, first = build(src, out, env, project)
    assert rc == 0 and first["libraries"] == {"fakelib": "1.0.0"}, first

    fake_registry(tdir, {"1.0.0": "window.fakeVersion = 1;\n", "2.0.0": "window.fakeVersion = 2;\n"}, current="2.0.0")
    seal(tdir)
    rc, second = build(src, out, env, project)
    assert rc == 0 and second["libraries"] == {"fakelib": "1.0.0"} and second["warnings"] == []

    rc, third = build(src, out, env, project, "--upgrade")
    assert rc == 0 and third["libraries"] == {"fakelib": "2.0.0"}
    assert any("fakelib" in w and "1.0.0" in w and "2.0.0" in w for w in third["warnings"]), third["warnings"]
    assert header.read_header(out.read_text(encoding="utf-8"))["libraries"] == {"fakelib": "2.0.0"}


def test_recorded_version_missing_from_registry_is_exit_2_naming_upgrade(tmp_path, env, project):
    tdir = custom_template(project, libraries=["fakelib"])
    fake_registry(tdir, {"1.0.0": "window.v = 1;\n"}, current="1.0.0")
    seal(tdir)
    src = write_src(tmp_path / "v.src.html", {"template": "fx", "title": "T"}, {"main": "<p>x</p>"})
    out = tmp_path / "v.html"
    assert build(src, out, env, project)[0] == 0

    fake_registry(tdir, {"2.0.0": "window.v = 2;\n"}, current="2.0.0")
    seal(tdir)
    rc, result = build(src, out, env, project)
    assert rc == 2 and "--upgrade" in result["error"]
    rc, result = build(src, out, env, project, "--upgrade")
    assert rc == 0 and result["libraries"] == {"fakelib": "2.0.0"}


def test_tampered_library_file_fails_the_build(tmp_path, env, project):
    tdir = custom_template(project, libraries=["fakelib"])
    fake_registry(tdir, {"1.0.0": "window.v = 1;\n"}, current="1.0.0")
    (tdir / "vendor" / "fakelib" / "1.0.0" / "fake.js").write_text("window.v = 666;\n", encoding="utf-8")
    seal(tdir)
    src = write_src(tmp_path / "t.src.html", {"template": "fx", "title": "T"}, {"main": "<p>x</p>"})
    rc, result = build(src, tmp_path / "t.html", env, project)
    assert rc == 2 and "sha256" in result["error"]


def test_failed_static_check_is_exit_1_but_file_is_written(tmp_path, env, project):
    src = write_src(
        tmp_path / "x.src.html",
        {"template": "report", "title": "T"},
        {"main": '<img src="https://cdn.example.com/a.png" alt="">'},
    )
    out = tmp_path / "x.html"
    rc, result = build(src, out, env, project)
    assert rc == 1 and result["checks"]["passed"] is False
    assert out.is_file()
    rc, check = run_cli("check", out, env=env)
    assert rc == 1 and any(f["check"] == "external-refs" for f in check["failures"])


def test_connected_mode_allows_data_calls(tmp_path, env, project):
    body = "<script>fetch('https://api.example.com/x')</script>"
    src = write_src(tmp_path / "c.src.html", {"template": "report", "title": "T", "mode": "connected"}, {"main": body})
    rc, result = build(src, tmp_path / "c.html", env, project)
    assert rc == 0 and result["mode"] == "connected"


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("<p>no header</p>\n", "header"),
        ('<!-- quirk-src {"template": "report"} -->\n<!-- slot: main -->\nx\n', "title"),
        ('<!-- quirk-src {"template": "report", "title": "T", "mode": "cdn"} -->\n<!-- slot: main -->\nx\n', "mode"),
        ('<!-- quirk-src {"template": "report", "title": "T"} -->\nstray\n<!-- slot: main -->\nx\n', "before the first slot"),
        ('<!-- quirk-src {"template": "report", "title": "T"} -->\n<!-- slot: main -->\nx\n<!-- slot: main -->\ny\n', "twice"),
        ('<!-- quirk-src {"template": "report", "title": "T"} -->\n', "slot"),
        ('<!-- quirk-src {not json} -->\n<!-- slot: main -->\nx\n', "JSON"),
    ],
)
def test_parse_source_rejects_malformed_files(tmp_path, text, fragment):
    path = tmp_path / "bad.src.html"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(assemble.SourceError) as info:
        assemble.parse_source(path)
    assert fragment in str(info.value)


def test_parse_source_reads_slots_and_fields(tmp_path):
    path = write_src(
        tmp_path / "ok.src.html",
        {"template": "report", "title": "T", "libraries": ["chartjs"], "interactions": ["sort"], "data": "d.json"},
        {"main": "<p>one</p>\n<p>two</p>", "aside": "<aside>side</aside>", "summary": "<p>sum</p>"},
    )
    src = assemble.parse_source(path)
    assert (src.template, src.title, src.mode) == ("report", "T", "offline")
    assert src.libraries == ["chartjs"] and src.interactions == ["sort"] and src.data == "d.json"
    assert src.slots == {"main": "<p>one</p>\n<p>two</p>", "aside": "<aside>side</aside>", "summary": "<p>sum</p>"}


def built_example(tmp_path: Path, env: dict, project: Path, name: str = "report") -> Path:
    out = tmp_path / f"{name}.html"
    rc, result = build(example_src(name), out, env, project)
    assert rc == 0, result
    return out


def test_note_lists_every_delivery_fact_and_is_stale_before_verify(tmp_path, env, project):
    out = built_example(tmp_path, env, project)
    rc, result = run_cli("note", out, env=env)
    assert rc == 0 and result["verify_stale"] is True
    note = result["markdown"]
    assert out.name in note and f"{out.stat().st_size:,}" in note
    assert "report" in note and "builtin" in note
    assert re.search(r"tier\s*1", note, re.I)
    assert "offline" in note
    for lib in ("simple-css", "alpine", "chartjs"):
        assert f"{lib} {REAL_STORE.resolve(lib, None).version}" in note
    assert "not browser-verified" in note
    last = [line for line in note.strip().splitlines() if line.strip()][-1].lower()
    assert "open" in last and "publish" in last


def test_note_reports_a_fresh_verify_with_screenshots_and_flags_a_stale_one(tmp_path, env, project):
    out = built_example(tmp_path, env, project)
    out_dir = verify_runner.default_out_dir(out)
    out_dir.mkdir()
    shots = [str(out_dir / "375-light.png"), str(out_dir / "1280-dark.png")]
    report = {"status": "passed", "file_sha256": sha(out.read_text(encoding="utf-8")), "browser": "chrome",
              "checks": {}, "screenshots": shots, "requests": []}
    (out_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")

    rc, result = run_cli("note", out, env=env)
    assert rc == 0 and result["verify_stale"] is False
    assert "passed" in result["markdown"] and all(s in result["markdown"] for s in shots)
    assert "not browser-verified" not in result["markdown"]

    out.write_text(out.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    rc, result = run_cli("note", out, env=env)
    assert result["verify_stale"] is True


@pytest.mark.parametrize("reason", ["verify-crashed", "verify-timeout"])
def test_note_reports_a_verifier_crash_with_its_reason_and_no_browser(tmp_path, env, project, reason):
    out = built_example(tmp_path, env, project)
    out_dir = verify_runner.default_out_dir(out)
    out_dir.mkdir()
    report = {"status": "failed", "file_sha256": sha(out.read_text(encoding="utf-8")), "browser": None,
              "checks": {}, "screenshots": [], "requests": [], "reason": reason, "detail": "chrome exited 9"}
    (out_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
    rc, result = run_cli("note", out, env=env)
    assert rc == 0 and result["verify_stale"] is False
    note = result["markdown"]
    assert f"Verify: failed ({reason}): chrome exited 9" in note
    assert "in a browser" not in note


def test_note_mentions_sidecar_and_the_mermaid_size_warning(tmp_path, env, project):
    big = tmp_path / "big.json"
    big.write_text(json.dumps({"blob": ["x" * 1000] * 11_000}), encoding="utf-8")
    src = write_src(
        tmp_path / "b.src.html",
        {"template": "report", "title": "Big", "data": "big.json", "libraries": ["mermaid"]},
        {"main": "<p>x</p>"},
    )
    out = tmp_path / "b.html"
    rc, result = build(src, out, env, project)
    assert rc == 0 and result["sidecar"]
    rc, note = run_cli("note", out, env=env)
    assert "b.data.json" in note["markdown"] and "mermaid" in note["markdown"].lower()
    assert "2 MB" in note["markdown"]


def test_verify_without_node_reports_not_browser_verified(tmp_path, env, project):
    out = built_example(tmp_path, env, project)
    bare = {**env, "PATH": str(tmp_path / "empty-bin")}
    rc, result = run_cli("verify", out, "--out-dir", tmp_path / "v", env=bare)
    assert rc == 0 and result["status"] == "not-browser-verified"
    assert (tmp_path / "v" / "report.json").is_file()


def test_cli_exit_codes_for_usage_errors(tmp_path, env, project):
    assert run_cli(env=env)[0] == 2
    assert run_cli("frobnicate", env=env)[0] == 2
    assert run_cli("build", tmp_path / "missing.src.html", "--project-dir", project, env=env)[0] == 2
    assert run_cli("check", tmp_path / "missing.html", env=env)[0] == 2
    assert run_cli("verify", tmp_path / "missing.html", env=env)[0] == 2
    assert run_cli("note", tmp_path / "missing.html", env=env)[0] == 2

    unknown = write_src(tmp_path / "n.src.html", {"template": "nope", "title": "T"}, {"main": "x"})
    rc, result = build(unknown, tmp_path / "n.html", env, project)
    assert rc == 2 and "nope" in result["error"]

    malformed = tmp_path / "bad.src.html"
    malformed.write_text("stray\n", encoding="utf-8")
    assert build(malformed, tmp_path / "bad.html", env, project)[0] == 2

    rc, result = run_cli("templates", "validate", tmp_path, env=env)
    assert rc == 2 and result["valid"] is False and result["errors"]


def test_build_refuses_a_tier_2_template(tmp_path, env, project):
    tdir = project / ".quirk" / "html-templates" / "app2"
    (tdir / "project").mkdir(parents=True)
    (tdir / "project" / "package.json").write_text("{}", encoding="utf-8")
    (tdir / "project" / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
    (tdir / "template.json").write_text(
        json.dumps({"schema": 1, "name": "app2", "description": DESCRIPTION, "tier": 2, "project": "project/"}),
        encoding="utf-8",
    )
    seal(tdir)
    src = write_src(tmp_path / "a.src.html", {"template": "app2", "title": "T"}, {"main": "x"})
    rc, result = build(src, tmp_path / "a.html", env, project)
    assert rc == 2 and "tier 2" in result["error"]


def data_src(tmp_path: Path, data_name: str, **meta: object) -> Path:
    return write_src(
        tmp_path / "d.src.html",
        {"template": "report", "title": "Data", "data": data_name, **meta},
        {"main": "<p>x</p>"},
    )


def test_oversized_csv_field_is_exit_2_with_json(tmp_path, env, project):
    (tmp_path / "big.csv").write_text("a\n" + "x" * 200_000 + "\n", encoding="utf-8")
    rc, result = build(data_src(tmp_path, "big.csv"), tmp_path / "o.html", env, project)
    assert rc == 2 and "big.csv" in result["error"]


@pytest.mark.parametrize(
    "text",
    ['{"v": NaN}', '{"v": -Infinity}', '[Infinity]', '{"v": 1e999}', '{"v": "\\ud800"}', "[" * 100_000 + "]" * 100_000],
    ids=["nan", "neg-inf", "inf", "overflow", "lone-surrogate", "deep"],
)
def test_unembeddable_json_data_is_exit_2_naming_the_file(tmp_path, env, project, text):
    (tmp_path / "bad.json").write_text(text, encoding="utf-8")
    rc, result = build(data_src(tmp_path, "bad.json"), tmp_path / "o.html", env, project)
    assert rc == 2 and "bad.json" in result["error"]
    assert not (tmp_path / "o.html").exists()


def test_unwritable_output_is_exit_2_not_a_traceback(tmp_path, env, project):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory", encoding="utf-8")
    src = write_src(tmp_path / "p.src.html", {"template": "report", "title": "T"}, {"main": "<p>x</p>"})
    rc, result = build(src, blocker / "sub" / "p.html", env, project)
    assert rc == 2 and "error" in result


def test_out_equal_to_source_or_data_is_refused_and_leaves_them_intact(tmp_path, env, project):
    (tmp_path / "d.json").write_text('{"a": 1}', encoding="utf-8")
    src = data_src(tmp_path, "d.json")
    before = src.read_text(encoding="utf-8")
    rc, result = build(src, src, env, project)
    assert rc == 2 and "error" in result and src.read_text(encoding="utf-8") == before
    rc, result = build(src, tmp_path / "sub" / ".." / "d.json", env, project)
    assert rc == 2 and (tmp_path / "d.json").read_text(encoding="utf-8") == '{"a": 1}'


def test_data_path_must_stay_inside_the_project_or_source_directory(tmp_path, env, project):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "d.json").write_text('{"a": 1}', encoding="utf-8")
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    for ref in (str(outside / "d.json"), "../outside/d.json"):
        src = write_src(srcdir / "d.src.html", {"template": "report", "title": "T", "data": ref}, {"main": "<p>x</p>"})
        rc, result = build(src, tmp_path / "o.html", env, project)
        assert rc == 2 and "outside" in result["error"], ref


def test_data_inside_the_project_directory_is_allowed_from_another_source_directory(tmp_path, env, project):
    (project / "d.json").write_text('{"a": 1}', encoding="utf-8")
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    src = write_src(srcdir / "d.src.html", {"template": "report", "title": "T", "data": str(project / "d.json")}, {"main": "<p>x</p>"})
    rc, result = build(src, tmp_path / "o.html", env, project)
    assert rc == 0, result


def test_data_with_a_skeleton_lacking_the_data_placeholder_is_exit_2_naming_the_template(tmp_path, env, project):
    custom_template(project, skeleton=SKELETON.replace("{{data}}", ""))
    seal(project / ".quirk" / "html-templates" / "fx")
    (tmp_path / "d.json").write_text('{"a": 1}', encoding="utf-8")
    src = write_src(tmp_path / "d.src.html", {"template": "fx", "title": "T", "data": "d.json"}, {"main": "<p>x</p>"})
    rc, result = build(src, tmp_path / "o.html", env, project)
    assert rc == 2 and "'fx'" in result["error"] and "{{data}}" in result["error"]


@pytest.mark.parametrize("sub", [".quirk/brainstorm", ".quirk/html/nested/deeper"])
def test_explicit_out_under_a_quirk_output_directory_gets_a_gitignore(tmp_path, env, project, sub):
    src = write_src(tmp_path / "plain.src.html", {"template": "report", "title": "Plain page"}, {"main": "<p>Body.</p>"})
    out_dir = tmp_path / "other-project" / sub
    rc, result = build(src, out_dir / "x.html", env, project)
    assert rc == 0, result
    assert (out_dir / ".gitignore").read_text(encoding="utf-8").strip() == "*"


def test_sidecar_is_named_from_the_source_slug_and_removed_when_data_is_embedded_later(tmp_path, env, project):
    data = tmp_path / "d.json"
    data.write_text(json.dumps({"blob": ["x" * 1000] * 11_000}), encoding="utf-8")
    src = data_src(tmp_path, "d.json")
    out = tmp_path / "out" / "other.html"
    rc, result = build(src, out, env, project)
    sidecar = out.parent / "d.data.json"
    assert rc == 0 and result["sidecar"] == str(sidecar) and sidecar.is_file()
    assert header.read_header(out.read_text(encoding="utf-8"))["sidecar"] == "d.data.json"

    data.write_text('{"a": 1}', encoding="utf-8")
    rc, result = build(src, out, env, project)
    assert rc == 0 and result["sidecar"] is None and not sidecar.exists()


def test_a_data_file_named_like_the_sidecar_survives_an_embedding_build(tmp_path, env, project):
    data = tmp_path / "d.data.json"
    data.write_text('{"a": 1}', encoding="utf-8")
    src = data_src(tmp_path, "d.data.json")
    rc, _ = build(src, tmp_path / "o.html", env, project)
    assert rc == 0 and data.is_file()


def test_every_subcommand_failure_keeps_to_one_json_object(tmp_path, env, project):
    directory = tmp_path / "adir"
    directory.mkdir()
    for command in ("check", "note", "verify"):
        rc, result = run_cli(command, directory, env=env)
        assert rc == 2 and "error" in result


def test_note_reads_a_report_from_verify_dir(tmp_path, env, project):
    out = built_example(tmp_path, env, project)
    report_dir = tmp_path / "custom-verify"
    report_dir.mkdir()
    report = {"status": "passed", "file_sha256": sha(out.read_text(encoding="utf-8")), "browser": "chrome",
              "checks": {}, "screenshots": [], "requests": []}
    (report_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")

    rc, result = run_cli("note", out, env=env)
    assert result["verify_stale"] is True
    rc, result = run_cli("note", out, "--verify-dir", report_dir, env=env)
    assert rc == 0 and result["verify_stale"] is False
    assert "passed in chrome" in result["markdown"]


# -- the component kit: auto-inclusion ---------------------------------------------------------------

KIT_DIR = SKILL / "vendor" / "kit" / "1.0.0"
STAT = (
    '<q-stat direction="up-good" points="1,2,3">'
    '<span slot="label">Users</span><span slot="value">3</span>'
    '<span slot="definition">Distinct users.</span></q-stat>'
)
CHART = (
    '<q-chart summary="Builds per month." type="line">'
    "<table><thead><tr><th>Month</th><th>Builds</th></tr></thead>"
    "<tbody><tr><td>June</td><td>4</td></tr></tbody></table></q-chart>"
)


def fake_kit_registry(root: Path, versions: list[str], current: str) -> None:
    """Write root/vendor with a first-party kit at each of ``versions``, each a copy of the real one."""
    entries = {}
    for version in versions:
        vdir = root / "vendor" / "kit" / version
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "LICENSE").write_text((KIT_DIR / "LICENSE").read_text(encoding="utf-8"), encoding="utf-8")
        css = (KIT_DIR / "kit.css").read_text(encoding="utf-8")
        js = (KIT_DIR / "kit.js").read_text(encoding="utf-8") + f"\n/* fake kit {version} */\n"
        (vdir / "kit.css").write_text(css, encoding="utf-8")
        (vdir / "kit.js").write_text(js, encoding="utf-8")
        catalog = json.loads((KIT_DIR / "catalog.json").read_text(encoding="utf-8"))
        catalog["kit_version"] = version
        (vdir / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
        files = []
        for name, kind, position, body in (("kit.css", "css", "head", css), ("kit.js", "js", "body-end", js)):
            files.append(
                {
                    "path": name,
                    "kind": kind,
                    "sha256": sha(body),
                    "inline_sha256": sha(vendor.escape_inline(body, kind)),
                    "position": position,
                    "inline": True,
                }
            )
        entries[version] = {
            "package": "quirk-kit",
            "license": "MIT",
            "license_file": "LICENSE",
            "first_party": True,
            "files": files,
        }
    registry = {"schema": 1, "libraries": {"kit": {"current": current, "versions": entries}}}
    (root / "vendor" / "libraries.json").write_text(json.dumps(registry), encoding="utf-8")


def report_build(tmp_path: Path, env: dict, project: Path, main: str, name: str = "k", **meta: object):
    src = write_src(tmp_path / f"{name}.src.html", {"template": "report", "title": "T", **meta}, {"main": main})
    out = tmp_path / f"{name}.html"
    rc, result = build(src, out, env, project)
    return rc, result, out


def test_a_source_without_q_tags_gets_no_kit(tmp_path, env, project):
    rc, result, out = report_build(tmp_path, env, project, "<p>plain</p>")
    assert rc == 0 and list(result["libraries"]) == ["simple-css", "alpine"], result
    html = out.read_text(encoding="utf-8")
    assert "kit@" not in html and "quirk-kit" not in html and "kit" not in header.read_header(html)["libraries"]
    assert result["checks"]["passed"] is True


def test_a_source_without_q_tags_builds_byte_identical_to_a_build_without_the_kit_scan(
    tmp_path, env, project, monkeypatch
):
    src = write_src(tmp_path / "plain.src.html", {"template": "report", "title": "T"}, {"main": "<p>plain</p>"})

    def built(name: str) -> str:
        out = tmp_path / f"{name}.html"
        assemble.build_tier1(src, out=out, upgrade=False, project_dir=project, user_dir=Path(env["QUIRK_HTML_USER_DIR"]))
        return re.sub(r'"built_at": "[^"]*"', '"built_at": "-"', out.read_text(encoding="utf-8"))

    with_scan = built("with")
    monkeypatch.setattr(assemble.kitcheck, "needs", lambda text: (False, False))
    assert with_scan == built("without")


def test_q_tags_pull_in_the_kit_before_alpine(tmp_path, env, project):
    rc, result, out = report_build(tmp_path, env, project, STAT)
    assert rc == 0 and result["checks"]["passed"] is True, result["checks"]
    assert list(result["libraries"]) == ["simple-css", "kit", "alpine"]
    assert result["libraries"]["kit"] == REAL_STORE.resolve("kit", None).version
    html = out.read_text(encoding="utf-8")
    assert "chartjs" not in result["libraries"] and 'data-quirk-lib="chartjs@' not in html
    kit_js = html.index('<script data-quirk-lib="kit@')
    alpine = html.index('<script data-quirk-lib="alpine@')
    chrome = html.index('<script data-quirk-shell="chrome">')
    assert kit_js < alpine < chrome
    assert header.read_header(html)["libraries"] == result["libraries"]
    assert "<!-- license: kit " in html


def test_q_chart_pulls_in_chartjs_and_then_the_kit(tmp_path, env, project):
    rc, result, out = report_build(tmp_path, env, project, CHART)
    assert rc == 0 and result["checks"]["passed"] is True, result["checks"]
    assert list(result["libraries"]) == ["simple-css", "chartjs", "kit", "alpine"]
    html = out.read_text(encoding="utf-8")
    positions = [html.index(f'<script data-quirk-lib="{lib}@') for lib in ("chartjs", "kit", "alpine")]
    assert positions == sorted(positions)


def test_a_chart_in_a_script_string_or_template_still_pulls_the_libraries_in(tmp_path, env, project):
    main = "<script>const html = '<q-chart summary=\"x\">';</script>"
    rc, result, _ = report_build(tmp_path, env, project, main)
    assert rc == 0 and list(result["libraries"]) == ["simple-css", "chartjs", "kit", "alpine"], result
    assert result["checks"]["passed"] is True, result["checks"]


def test_a_chart_already_requested_in_the_header_is_not_duplicated(tmp_path, env, project):
    rc, result, out = report_build(tmp_path, env, project, CHART, libraries=["chartjs"])
    assert rc == 0 and list(result["libraries"]) == ["simple-css", "chartjs", "kit", "alpine"], result
    assert out.read_text(encoding="utf-8").count('data-quirk-lib="chartjs@') == 1


def test_auto_included_libraries_need_not_be_optional_libraries_of_the_template(tmp_path, env, project):
    seal(custom_template(project, libraries=[]))
    src = write_src(tmp_path / "f.src.html", {"template": "fx", "title": "T"}, {"main": CHART})
    rc, result = build(src, tmp_path / "f.html", env, project)
    assert rc == 0 and list(result["libraries"]) == ["chartjs", "kit"], result


def test_a_header_declared_kit_is_rejected(tmp_path, env, project):
    for main in ("<p>plain</p>", STAT):
        src = write_src(
            tmp_path / "h.src.html", {"template": "report", "title": "T", "libraries": ["kit"]}, {"main": main}
        )
        rc, result = build(src, tmp_path / "h.html", env, project)
        assert rc == 2 and "kit" in result["error"] and "optional" in result["error"], result


def test_kit_css_follows_base_css_in_the_head(tmp_path, env, project):
    rc, result, out = report_build(tmp_path, env, project, STAT)
    assert rc == 0, result
    html = out.read_text(encoding="utf-8")
    base_css = (SKILL / "theme" / "base.css").read_text(encoding="utf-8")
    base = html.index(f"<style>\n{base_css}</style>")
    kit_css = html.index('<style data-quirk-lib="kit@')
    assert base < kit_css < html.index("</head>")
    assert html.index('<style data-quirk-lib="simple-css@') < html.index("--q-color-bg") < base


def test_a_kit_page_rebuilds_with_the_same_markup_and_stays_checked(tmp_path, env, project):
    rc, first, out = report_build(tmp_path, env, project, STAT + CHART)
    assert rc == 0
    rc, second = build(tmp_path / "k.src.html", out, env, project)
    assert rc == 0 and second["libraries"] == first["libraries"] and second["checks"]["passed"] is True
    rc, check = run_cli("check", out, env=env)
    assert rc == 0 and check["passed"] is True, check


def test_frozen_kit_version_holds_until_upgrade(tmp_path, env, project):
    tdir = custom_template(project, libraries=[])
    fake_kit_registry(tdir, ["1.0.0"], current="1.0.0")
    seal(tdir)
    src = write_src(tmp_path / "v.src.html", {"template": "fx", "title": "T"}, {"main": STAT})
    out = tmp_path / "v.html"
    rc, first = build(src, out, env, project)
    assert rc == 0 and first["libraries"] == {"kit": "1.0.0"}, first

    fake_kit_registry(tdir, ["1.0.0", "2.0.0"], current="2.0.0")
    seal(tdir)
    rc, second = build(src, out, env, project)
    assert rc == 0 and second["libraries"] == {"kit": "1.0.0"} and second["warnings"] == [], second
    assert second["checks"]["passed"] is True

    rc, third = build(src, out, env, project, "--upgrade")
    assert rc == 0 and third["libraries"] == {"kit": "2.0.0"}, third
    assert any("kit" in w and "1.0.0" in w and "2.0.0" in w for w in third["warnings"]), third["warnings"]
    assert header.read_header(out.read_text(encoding="utf-8"))["libraries"] == {"kit": "2.0.0"}


def test_a_page_that_starts_using_the_kit_gets_the_current_version(tmp_path, env, project):
    tdir = custom_template(project, libraries=[])
    fake_kit_registry(tdir, ["1.0.0", "2.0.0"], current="2.0.0")
    seal(tdir)
    src = write_src(tmp_path / "s.src.html", {"template": "fx", "title": "T"}, {"main": "<p>plain</p>"})
    out = tmp_path / "s.html"
    rc, plain = build(src, out, env, project)
    assert rc == 0 and plain["libraries"] == {}
    write_src(src, {"template": "fx", "title": "T"}, {"main": STAT})
    rc, used = build(src, out, env, project)
    assert rc == 0 and used["libraries"] == {"kit": "2.0.0"}, used
    write_src(src, {"template": "fx", "title": "T"}, {"main": "<p>plain again</p>"})
    rc, dropped = build(src, out, env, project)
    assert rc == 0 and dropped["libraries"] == {}
    assert "kit" not in header.read_header(out.read_text(encoding="utf-8"))["libraries"]


def test_a_bad_q_tag_fails_the_build_with_the_source_line(tmp_path, env, project):
    main = "<p>fine</p>\n<q-stats>\n  nope\n</q-stats>"
    rc, result, out = report_build(tmp_path, env, project, main, name="bad")
    assert rc == 1 and result["checks"]["passed"] is False, result
    assert out.is_file()
    kit = [f["detail"] for f in result["checks"]["failures"] if f["check"] == "kit"]
    # line 1 is the quirk-src header, line 2 the slot marker, so the slot's second line is 4
    assert kit == ["bad.src.html line 4: unknown element <q-stats>"]


def test_a_bad_attribute_in_a_slot_names_its_source_line(tmp_path, env, project):
    main = "<p>intro</p>\n\n" + CHART.replace('type="line"', 'type="pie"')
    rc, result, _ = report_build(tmp_path, env, project, main, name="bad")
    assert rc == 1
    kit = [f["detail"] for f in result["checks"]["failures"] if f["check"] == "kit"]
    assert kit == ['bad.src.html line 5: <q-chart> type="pie" is not one of bar, line, area, donut']


def test_the_rebuilt_check_of_a_bad_page_cites_the_built_file(tmp_path, env, project):
    rc, result, out = report_build(tmp_path, env, project, "<q-stats></q-stats>", name="bad")
    assert rc == 1
    rc, check = run_cli("check", out, env=env)
    assert rc == 1
    details = [f["detail"] for f in check["failures"] if f["check"] == "kit"]
    assert len(details) == 1 and details[0].startswith("bad.html line ") and details[0].endswith("unknown element <q-stats>")


FLOW = (
    '<q-flow summary="Orders flow from checkout to ledger.">'
    '<script type="application/json">'
    '{"kinds":{"ui":1,"db":3},"groups":[{"id":"billing","label":"Billing"}],'
    '"nodes":[{"id":"checkout","label":"Checkout","kind":"ui"},'
    '{"id":"ledger","label":"Ledger","kind":"db","group":"billing","detail":"<p>Stores entries.</p>"}],'
    '"edges":[{"from":"checkout","to":"ledger","label":"order.created","async":true}]}'
    "</script></q-flow>"
)


def test_q_flow_pulls_in_flow_and_kit_and_injects_the_text_list_fallback(tmp_path, env, project):
    rc, result, out = report_build(tmp_path, env, project, FLOW, name="flow")
    assert rc == 0 and result["checks"]["passed"] is True, result["checks"]
    assert list(result["libraries"]) == ["simple-css", "flow", "kit", "alpine"]
    html = out.read_text(encoding="utf-8")
    positions = [html.index(f'<script data-quirk-lib="{lib}@') for lib in ("flow", "kit", "alpine")]
    assert positions == sorted(positions)
    assert "<!-- license: flow 0.12.0 EPL-2.0 AND ISC" in html
    assert "<!-- license: kit 1.0.0 MIT" in html
    assert "<details class=\"q-flow-list\" data-q-kit data-q-flow-list open>" in html
    assert "<summary>Graph as a list</summary>" in html
    assert "Stores entries." in html
    assert "\u2192 Ledger (order.created, async)" in html


CHECKOUT_FLOW = (
    '<q-flow id="checkout-flow" summary="Checkout charges, ships or retries, and refunds on return.">'
    '<script type="application/json">'
    '{"kinds":{"ui":1,"worker":2,"queue":3},'
    '"nodes":[{"id":"checkout","label":"Checkout","kind":"ui"},'
    '{"id":"charge","label":"Charge worker","kind":"worker"},'
    '{"id":"paid","label":"Paid?","kind":"worker","shape":"decision"},'
    '{"id":"ship","label":"Ship","kind":"worker"},'
    '{"id":"retry","label":"Retry queue","kind":"queue"},'
    '{"id":"refund","label":"Issue refund","shape":"subprocess","flow":"refund-flow"}],'
    '"edges":[{"from":"checkout","to":"charge","label":"order.created","async":true},'
    '{"from":"charge","to":"paid"},'
    '{"from":"paid","to":"ship","label":"Yes"},'
    '{"from":"paid","to":"retry","label":"No"},'
    '{"from":"retry","to":"charge","label":"retry up to 3x","loop":true},'
    '{"from":"ship","to":"refund","label":"on return"}]}'
    "</script></q-flow>"
)
REFUND_FLOW = (
    '<q-flow id="refund-flow" summary="Refunds are issued and confirmed.">'
    '<script type="application/json">'
    '{"nodes":[{"id":"issue","label":"Issue"},{"id":"confirm","label":"Confirm"}],'
    '"edges":[{"from":"issue","to":"confirm"}]}'
    "</script></q-flow>"
)
POLLER_FLOW = (
    '<q-flow summary="A poller checks status on a timer.">'
    '<script type="application/json">'
    '{"nodes":[{"id":"poll","label":"Status poller"}],'
    '"edges":[{"from":"poll","to":"poll","label":"every 30s"}]}'
    "</script></q-flow>"
)


def test_q_flow_text_list_covers_decisions_loops_and_subprocess_links(tmp_path, env, project):
    page = CHECKOUT_FLOW + REFUND_FLOW + POLLER_FLOW
    rc, result, out = report_build(tmp_path, env, project, page, name="flowshapes")
    assert rc == 0 and result["checks"]["passed"] is True, result["checks"]
    html = out.read_text(encoding="utf-8")
    assert "Paid?</strong> (decision, worker): Yes \u2192 Ship, No \u2192 Retry queue" in html
    assert "Issue refund</strong> (subprocess): <a href=\"#refund-flow\">opens the &quot;refund-flow&quot; graph</a>" in html
    assert "<li>\u21a9 returns to Charge worker: retry up to 3x</li>" in html
    assert "<li>\u21a9 returns to itself: every 30s</li>" in html
    assert "\u2192 Charge worker (order.created, async)" in html
    assert "Ship</strong> (worker)<ul><li>\u2192 Issue refund (on return)</li></ul>" in html
    assert "Status poller</strong><ul>" in html
    paid_entry = html.split('data-q-flow-list-node="paid"', 1)[1].split("</li>", 1)[0]
    assert "<ul>" not in paid_entry


def test_q_flow_warnings_are_reported_in_build_checks(tmp_path, env, project):
    long_edge = FLOW.replace('"order.created"', '"' + ("e" * 45) + '"')
    rc, result, _ = report_build(tmp_path, env, project, long_edge, name="flowwarn")
    assert rc == 0 and result["checks"]["passed"] is True
    kit_warns = [w["detail"] for w in result["checks"]["warnings"] if w["check"] == "kit"]
    assert any("edge labels over 30 characters crowd the layout" in w for w in kit_warns), kit_warns


RENEWAL_V1 = {"order": "R-1042", "status": "queued", "lines": [{"item": "Coffee beans", "qty": 2, "price": 18}]}
RENEWAL_V2 = {**RENEWAL_V1, "subtotal": 36, "discount": {"code": "LOYALTY10", "amount": 3.6}, "total": 32.4}
RENEWAL_V3 = {**RENEWAL_V2, "tax": 2.67, "total": 35.07}
RENEWAL_V4 = {**RENEWAL_V3, "status": "declined", "attempt": 1, "decline": "insufficient_funds"}
RENEWAL_V6 = {**RENEWAL_V4, "status": "retry_scheduled", "retry_at": "2026-10-18T09:00Z"}
RENEWAL_V7 = {
    **{k: v for k, v in RENEWAL_V6.items() if k not in ("decline", "retry_at")},
    "status": "paid",
    "attempt": 2,
    "charge": "ch_88",
}
RENEWAL_V9 = {**RENEWAL_V7, "status": "settled", "settled_at": "2026-10-18T09:02Z"}
RENEWAL_GRAPH = {
    "nodes": [
        {"id": "scheduler", "label": "Renewal scheduler"},
        {"id": "pricing", "label": "Pricing"},
        {"id": "tax", "label": "Tax"},
        {"id": "charge", "label": "Charge worker"},
        {"id": "paid", "label": "Paid?", "shape": "decision"},
        {"id": "retry", "label": "Retry queue"},
        {"id": "settle", "label": "Settlement"},
    ],
    "edges": [
        {"from": "scheduler", "to": "pricing"},
        {"from": "pricing", "to": "tax", "label": "domestic quote", "id": "tax-domestic"},
        {"from": "pricing", "to": "tax", "label": "cross-border quote", "id": "tax-intl"},
        {"from": "tax", "to": "charge"},
        {"from": "charge", "to": "paid"},
        {"from": "paid", "to": "settle", "label": "Yes"},
        {"from": "paid", "to": "retry", "label": "No"},
        {"from": "retry", "to": "charge", "label": "retry up to 3x", "id": "retry", "loop": True},
    ],
    "traces": [
        {
            "id": "succeeds",
            "label": "Card succeeds",
            "steps": [
                {"node": "scheduler", "value": RENEWAL_V1},
                {"node": "pricing", "value": RENEWAL_V2},
                {"node": "tax", "value": RENEWAL_V3, "via": "tax-domestic"},
                {"node": "charge", "value": RENEWAL_V3},
                {"node": "paid", "value": RENEWAL_V3},
                {"node": "settle", "value": RENEWAL_V9},
            ],
        },
        {
            "id": "declined",
            "label": "Card declined, retried",
            "steps": [
                {"node": "scheduler", "value": RENEWAL_V1},
                {"node": "pricing", "value": RENEWAL_V2, "note": "Pricing applies the loyalty discount"},
                {"node": "tax", "value": RENEWAL_V3, "via": "tax-domestic", "note": "Tax adds 8.25% sales tax"},
                {"node": "charge", "value": RENEWAL_V4, "note": "The card is declined"},
                {"node": "paid", "value": RENEWAL_V4, "note": "Paid? answers No"},
                {"node": "retry", "value": RENEWAL_V6, "note": "The retry is booked for tomorrow"},
                {"node": "charge", "value": RENEWAL_V7, "note": "The second attempt succeeds"},
                {"node": "paid", "value": RENEWAL_V7, "note": "Paid? answers Yes"},
                {"node": "settle", "value": RENEWAL_V9, "note": "The order settles"},
            ],
        },
    ],
}


def trace_flow_markup(graph: dict, flow_id: str) -> str:
    return (
        f'<q-flow id="{flow_id}" summary="Traced graph."><script type="application/json">'
        f"{json.dumps(graph)}</script></q-flow>"
    )


def test_q_flow_text_list_appends_one_block_per_trace(tmp_path, env, project):
    page = trace_flow_markup(RENEWAL_GRAPH, "renewal")
    rc, result, out = report_build(tmp_path, env, project, page, name="flowtraces")
    assert rc == 0 and result["checks"]["passed"] is True, result["checks"]
    html = out.read_text(encoding="utf-8")
    body = html.split("<div data-q-flow-list-body>", 1)[1].split("</details>", 1)[0]
    assert body.index("</ul><div data-q-flow-list-trace=\"succeeds\">") < body.index('data-q-flow-list-trace="declined"')
    assert '<div data-q-flow-list-trace="declined"><p><strong>Trace: Card declined, retried</strong></p><ol>' in html
    assert (
        '<li data-q-flow-list-step="3">Tax, via &quot;domestic quote&quot;: Tax adds 8.25% sales tax<pre><code>' in html
    )
    assert (
        '<li data-q-flow-list-step="7">Charge worker, via &quot;retry up to 3x&quot;: The second attempt succeeds<pre><code>'
        in html
    )
    assert '<li data-q-flow-list-step="2">Pricing: Pricing applies the loyalty discount<pre><code>' in html
    declined = html.split('data-q-flow-list-trace="declined"', 1)[1].split("</div>", 1)[0]
    assert declined.endswith("</code></pre></li></ol>")
    assert "{\n  &quot;order&quot;: &quot;R-1042&quot;,\n  &quot;status&quot;: &quot;queued&quot;," in declined
    assert "&quot;price&quot;: 18\n    }\n  ]\n}</code></pre></li>" in declined


def test_q_flow_trace_list_names_loop_and_edge_id_when_unlabelled(tmp_path, env, project):
    graph = {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [
            {"from": "a", "to": "b", "id": "go"},
            {"from": "b", "to": "a", "loop": True},
        ],
        "traces": [
            {
                "id": "t",
                "label": "T",
                "steps": [
                    {"node": "a", "value": 1},
                    {"node": "b", "value": 2, "via": "go", "note": "<b>x</b>"},
                    {"node": "a", "value": None},
                ],
            }
        ],
    }
    page = trace_flow_markup(graph, "loops")
    rc, result, out = report_build(tmp_path, env, project, page, name="flowtraceloop")
    assert rc == 0 and result["checks"]["passed"] is True, result["checks"]
    html = out.read_text(encoding="utf-8")
    assert '<li data-q-flow-list-step="2">B, via &quot;go&quot;: &lt;b&gt;x&lt;/b&gt;<pre><code>2</code></pre></li>' in html
    assert '<li data-q-flow-list-step="3">A, around the loop<pre><code>null</code></pre></li>' in html


def test_q_flow_trace_with_a_lone_surrogate_value_fails_the_build_instead_of_crashing(tmp_path, env, project):
    graph = json.loads(json.dumps(RENEWAL_GRAPH))
    graph["traces"][0]["steps"][1]["value"] = {"k": "\ud800"}
    page = trace_flow_markup(graph, "surrogate")
    rc, result, out = report_build(tmp_path, env, project, page, name="flowsurrogate")
    assert rc == 1 and result["checks"]["passed"] is False, result
    kit = [f["detail"] for f in result["checks"]["failures"] if f["check"] == "kit"]
    assert len(kit) == 1 and kit[0].endswith('<q-flow> trace "succeeds" step 2 has a value that isn\'t JSON'), kit
    out.read_bytes().decode("utf-8")


def test_q_flow_trace_list_omits_the_note_part_for_an_empty_note(tmp_path, env, project):
    graph = {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b"}],
        "traces": [
            {
                "id": "t",
                "label": "T",
                "steps": [{"node": "a", "value": 1, "note": ""}, {"node": "b", "value": 2, "note": "kept"}],
            }
        ],
    }
    page = trace_flow_markup(graph, "emptynote")
    rc, result, out = report_build(tmp_path, env, project, page, name="flowtraceemptynote")
    assert rc == 0 and result["checks"]["passed"] is True, result["checks"]
    html = out.read_text(encoding="utf-8")
    assert '<li data-q-flow-list-step="1">A<pre><code>1</code></pre></li>' in html
    assert '<li data-q-flow-list-step="2">B: kept<pre><code>2</code></pre></li>' in html


def test_q_flow_trace_with_a_question_mark_id_stays_in_the_list(tmp_path, env, project):
    graph = {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b"}],
        "traces": [{"id": "?", "label": "Odd id", "steps": [{"node": "a", "value": 1}, {"node": "b", "value": 2}]}],
    }
    page = trace_flow_markup(graph, "qmarkid")
    rc, result, out = report_build(tmp_path, env, project, page, name="flowtracequestion")
    assert rc == 0 and result["checks"]["passed"] is True, result["checks"]
    assert '<div data-q-flow-list-trace="?">' in out.read_text(encoding="utf-8")


def test_q_flow_without_traces_has_no_trace_block(tmp_path, env, project):
    rc, result, out = report_build(tmp_path, env, project, FLOW, name="flownotraces")
    assert rc == 0, result
    # the inlined kit.js names the attribute too, so look for the rendered block only
    assert '<div data-q-flow-list-trace="' not in out.read_text(encoding="utf-8")
