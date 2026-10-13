"""Tests for the htmlkit core library and the house theme of writing-html-artifacts.

Every test builds its own vendor and template trees under tmp_path; nothing reads the
skill's real ``vendor/`` directory, and nothing touches the network.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import checks, fsutil, header, manifest, resolve, tokens, vendor  # noqa: E402

CHROME_JS = SKILL / "theme" / "chrome.js"
BASE_CSS = SKILL / "theme" / "base.css"
HOUSE_TOKENS = SKILL / "theme" / "house.tokens.json"

SKELETON = (
    "<!doctype html>\n{{header}}\n<html><head><title>{{title}}</title>{{head}}</head>\n"
    "<body>{{chrome}}<main>{{slot:main}}</main>{{data}}{{body_end}}</body></html>\n"
)
DESCRIPTION = "Use when you need a fixture template for the htmlkit tests."
FAKE_JS = 'var u="https://cdn.example.com/x.js"; fetch(u); var s="</SCRIPT>";\n'
FAKE_JS_V2 = 'var v=2; fetch("https://cdn.example.com/y.js");\n'
FAKE_CSS = "body{color:#111}\n"


def sha(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def lib_entry(root: Path, name: str, version: str, files: list[tuple[str, str, str, str, bool]]) -> dict:
    """Write library files under root/<name>/<version>/ and return the libraries.json version entry."""
    vdir = root / name / version
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "LICENSE").write_text(
        "MIT License\n\nCopyright (c) 2024 Fake Authors\n\nPermission is hereby granted.\n",
        encoding="utf-8",
    )
    entries = []
    for rel, kind, content, position, inline in files:
        (vdir / rel).write_text(content, encoding="utf-8")
        entries.append(
            {
                "path": rel,
                "kind": kind,
                "sha256": sha(content),
                "inline_sha256": sha(vendor.escape_inline(content, kind)),
                "position": position,
                "inline": inline,
            }
        )
    return {
        "package": name,
        "license": "MIT",
        "license_file": "LICENSE",
        "source": "https://example.invalid/" + name,
        "files": entries,
    }


def make_vendor(skill: Path) -> Path:
    vdir = skill / "vendor"
    libs = {
        "fakecss": {
            "current": "1.0.0",
            "versions": {"1.0.0": lib_entry(vdir, "fakecss", "1.0.0", [("fake.css", "css", FAKE_CSS, "head", True)])},
        },
        "fakejs": {
            "current": "1.1.0",
            "versions": {
                "1.0.0": lib_entry(vdir, "fakejs", "1.0.0", [("fake.js", "js", FAKE_JS, "body-end", True)]),
                "1.1.0": lib_entry(vdir, "fakejs", "1.1.0", [("fake.js", "js", FAKE_JS_V2, "body-end", True)]),
            },
        },
        "servedonly": {
            "current": "1.0.0",
            "versions": {
                "1.0.0": lib_entry(vdir, "servedonly", "1.0.0", [("big.js", "js", "var big=1;\n", "body-end", False)])
            },
        },
    }
    write_json(vdir / "libraries.json", {"schema": 1, "libraries": libs})
    return vdir / "libraries.json"


@pytest.fixture
def skill(tmp_path: Path) -> Path:
    root = tmp_path / "skill"
    make_vendor(root)
    (root / "theme").mkdir()
    shutil.copy(CHROME_JS, root / "theme" / "chrome.js")
    (root / "templates").mkdir()
    return root


@pytest.fixture
def store(skill: Path) -> vendor.VendorStore:
    return vendor.VendorStore([skill / "vendor" / "libraries.json"])


def make_template(
    parent: Path,
    name: str = "basic",
    *,
    tier: int = 1,
    verified: bool = False,
    **overrides: object,
) -> Path:
    tdir = parent / name
    tdir.mkdir(parents=True)
    meta: dict = {"schema": 1, "name": name, "description": DESCRIPTION, "tier": tier}
    if tier == 1:
        meta.update(
            {
                "libraries": ["fakecss"],
                "optional_libraries": ["fakejs"],
                "slots": {"main": {"required": True, "description": "Main content."}},
                "skeleton": "skeleton.html",
                "example": "example.src.html",
            }
        )
        (tdir / "skeleton.html").write_text(SKELETON, encoding="utf-8")
        (tdir / "example.src.html").write_text(
            '<!-- quirk-src {"template": "%s", "title": "T"} -->\n<!-- slot: main -->\n<p>hi</p>\n' % name,
            encoding="utf-8",
        )
    else:
        meta.update({"project": "project/", "example": "example/"})
        (tdir / "project").mkdir()
        (tdir / "project" / "package.json").write_text('{"name": "app"}\n', encoding="utf-8")
        (tdir / "project" / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
    meta.update(overrides)
    for key in [k for k, v in meta.items() if v is None]:
        del meta[key]
    write_json(tdir / "template.json", meta)
    if verified:
        write_verified(tdir)
    return tdir


def write_verified(tdir: Path) -> None:
    write_json(
        tdir / "verified.json",
        {"schema": 1, "verified_at": "2026-10-13T00:00:00Z", "browser": False, "hashes": manifest.compute_hashes(tdir)},
    )


def problems(tdir: Path, **kw: object) -> list[str]:
    kw.setdefault("require_verified", False)
    return manifest.validate_template(tdir, skill_dir=tdir.parent.parent / "skill", **kw)  # type: ignore[arg-type]


def load(tdir: Path) -> manifest.Template:
    return manifest.load_template(tdir, skill_dir=tdir.parent.parent / "skill")


def has(errors: list[str], needle: str) -> bool:
    return any(needle in e for e in errors)


@pytest.fixture
def troot(tmp_path: Path, skill: Path) -> Path:
    """Directory that holds candidate templates; sits beside the skill fixture."""
    d = tmp_path / "troot"
    d.mkdir()
    return d


# manifest


def test_valid_tier1_template_loads(troot: Path, skill: Path) -> None:
    tdir = make_template(troot, "basic")
    assert problems(tdir) == []
    tpl = load(tdir)
    assert tpl.name == "basic" and tpl.tier == 1
    assert tpl.dir == tdir
    assert tpl.libraries == ["fakecss"] and tpl.optional_libraries == ["fakejs"]
    assert list(tpl.slots) == ["main"]
    assert tpl.skeleton == "skeleton.html" and tpl.example == "example.src.html"


def test_valid_tier2_template(troot: Path, skill: Path) -> None:
    tdir = make_template(troot, "webapp", tier=2)
    assert problems(tdir) == []
    assert load(tdir).tier == 2


@pytest.mark.parametrize(
    "overrides, needle",
    [
        ({"schema": 2}, "schema"),
        ({"schema": None}, "schema"),
        ({"description": "Use when short"}, "description"),
        ({"description": "A fixture template for the htmlkit tests, long enough."}, "Use when"),
        ({"description": "Use when " + "x" * 400}, "description"),
        ({"tier": 3}, "tier"),
        ({"tier": None}, "tier"),
        ({"slots": {}}, "slots"),
        ({"slots": {f"s{i}": {"required": False} for i in range(4)}}, "slots"),
        ({"skeleton": "missing.html"}, "skeleton"),
        ({"skeleton": None}, "skeleton"),
        ({"example": "missing.src.html"}, "example"),
        ({"example": None}, "example"),
        ({"libraries": ["nonesuch"]}, "nonesuch"),
        ({"optional_libraries": ["nonesuch"]}, "nonesuch"),
        ({"tokens": "tokens.json"}, "tokens"),
        ({"rules": "rules.md"}, "rules"),
        ({"skeleton": "../outside.html"}, "skeleton"),
    ],
)
def test_tier1_manifest_rules(troot: Path, skill: Path, overrides: dict, needle: str) -> None:
    tdir = make_template(troot, "basic", **overrides)
    errors = problems(tdir)
    assert errors and has(errors, needle), errors


def test_name_must_equal_directory_name(troot: Path, skill: Path) -> None:
    tdir = make_template(troot, "basic")
    meta = json.loads((tdir / "template.json").read_text(encoding="utf-8"))
    meta["name"] = "other"
    write_json(tdir / "template.json", meta)
    assert has(problems(tdir), "name")


@pytest.mark.parametrize("bad", ["Bad_Name", "x" * 41, "has space"])
def test_name_pattern(troot: Path, skill: Path, bad: str) -> None:
    tdir = make_template(troot, bad)
    assert has(problems(tdir), "name")


@pytest.mark.parametrize(
    "placeholder", ["{{header}}", "{{title}}", "{{head}}", "{{chrome}}", "{{body_end}}", "{{slot:main}}"]
)
def test_skeleton_requires_each_placeholder(troot: Path, skill: Path, placeholder: str) -> None:
    tdir = make_template(troot, "basic")
    (tdir / "skeleton.html").write_text(SKELETON.replace(placeholder, ""), encoding="utf-8")
    assert has(problems(tdir), placeholder)


def test_skeleton_data_placeholder_is_optional(troot: Path, skill: Path) -> None:
    tdir = make_template(troot, "basic")
    (tdir / "skeleton.html").write_text(SKELETON.replace("{{data}}", ""), encoding="utf-8")
    assert problems(tdir) == []


def test_skeleton_undeclared_slot_is_an_error(troot: Path, skill: Path) -> None:
    tdir = make_template(troot, "basic")
    (tdir / "skeleton.html").write_text(SKELETON.replace("{{data}}", "{{slot:aside}}"), encoding="utf-8")
    assert has(problems(tdir), "{{slot:aside}}")


@pytest.mark.parametrize("missing", ["package.json", "pnpm-lock.yaml"])
def test_tier2_requires_package_and_lockfile(troot: Path, skill: Path, missing: str) -> None:
    tdir = make_template(troot, "webapp", tier=2)
    (tdir / "project" / missing).unlink()
    assert has(problems(tdir), missing)


def test_template_json_missing_or_invalid(troot: Path, skill: Path) -> None:
    empty = troot / "empty"
    empty.mkdir()
    assert has(problems(empty), "template.json")
    broken = troot / "broken"
    broken.mkdir()
    (broken / "template.json").write_text("{nope", encoding="utf-8")
    assert has(problems(broken), "template.json")


def test_template_local_library_resolves(troot: Path, skill: Path) -> None:
    tdir = make_template(troot, "basic", libraries=["localonly"])
    assert has(problems(tdir), "localonly")
    vdir = tdir / "vendor"
    write_json(
        vdir / "libraries.json",
        {
            "schema": 1,
            "libraries": {
                "localonly": {
                    "current": "0.1.0",
                    "versions": {"0.1.0": lib_entry(vdir, "localonly", "0.1.0", [("l.css", "css", "a{}\n", "head", True)])},
                }
            },
        },
    )
    assert problems(tdir) == []


def test_load_template_reports_every_problem(troot: Path, skill: Path) -> None:
    tdir = make_template(troot, "basic", schema=2, tier=7, description="nope")
    with pytest.raises(manifest.ManifestError) as exc:
        load(tdir)
    msg = str(exc.value)
    assert "schema" in msg and "tier" in msg and "description" in msg


def test_load_libraries_validation(tmp_path: Path) -> None:
    bad = tmp_path / "libraries.json"
    write_json(bad, {"schema": 9, "libraries": {"x": {"current": "2", "versions": {"1": {}}}}})
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.load_libraries(bad)
    assert "schema" in str(exc.value) and "current" in str(exc.value)
    with pytest.raises(manifest.ManifestError):
        manifest.load_libraries(tmp_path / "absent.json")


def test_load_libraries_returns_dict(skill: Path) -> None:
    data = manifest.load_libraries(skill / "vendor" / "libraries.json")
    assert data["libraries"]["fakejs"]["current"] == "1.1.0"


# verified.json


def test_verified_ok(troot: Path, skill: Path) -> None:
    tdir = make_template(troot, "basic", verified=True)
    assert problems(tdir, require_verified=True) == []


def test_verified_missing_file_is_unverified(troot: Path, skill: Path) -> None:
    tdir = make_template(troot, "basic")
    errors = problems(tdir, require_verified=True)
    assert has(errors, "unverified")


@pytest.mark.parametrize("target", ["template.json", "skeleton.html", "example.src.html"])
def test_verified_hash_mismatch_is_unverified(troot: Path, skill: Path, target: str) -> None:
    tdir = make_template(troot, "basic", verified=True)
    with (tdir / target).open("a", encoding="utf-8") as fh:
        fh.write("\n ")
    assert has(problems(tdir, require_verified=True), "unverified")


def test_verified_covers_vendor_files(troot: Path, skill: Path) -> None:
    tdir = make_template(troot, "basic", verified=True)
    (tdir / "vendor").mkdir()
    (tdir / "vendor" / "stray.js").write_text("x", encoding="utf-8")
    assert has(problems(tdir, require_verified=True), "unverified")


def test_verified_tier2_covers_package_and_lock(troot: Path, skill: Path) -> None:
    tdir = make_template(troot, "webapp", tier=2, verified=True)
    assert problems(tdir, require_verified=True) == []
    with (tdir / "project" / "pnpm-lock.yaml").open("a", encoding="utf-8") as fh:
        fh.write("# edit\n")
    assert has(problems(tdir, require_verified=True), "unverified")


def test_verified_json_unparseable(troot: Path, skill: Path) -> None:
    tdir = make_template(troot, "basic")
    (tdir / "verified.json").write_text("{", encoding="utf-8")
    assert has(problems(tdir, require_verified=True), "unverified")


# vendor


def test_escape_inline_rules() -> None:
    assert vendor.escape_inline('a</script>b</SCRIPT >', "js") == r"a<\/script>b<\/script >"
    assert vendor.escape_inline("a</style>b</STYLE>", "css") == r"a<\/style>b<\/style>"
    assert vendor.escape_inline("a</style>", "js") == "a</style>"
    assert vendor.escape_inline("a</script>", "css") == "a</script>"
    with pytest.raises(ValueError):
        vendor.escape_inline("x", "html")


def test_resolve_current_and_explicit(store: vendor.VendorStore) -> None:
    assert store.resolve("fakejs", None).version == "1.1.0"
    lv = store.resolve("fakejs", "1.0.0")
    assert lv.version == "1.0.0" and lv.license == "MIT"
    assert lv.files[0].path == "fake.js"


def test_resolve_absent_version_names_upgrade(store: vendor.VendorStore) -> None:
    with pytest.raises(vendor.VendorError) as exc:
        store.resolve("fakejs", "0.9.0")
    assert "--upgrade" in str(exc.value)


def test_resolve_unknown_library(store: vendor.VendorStore) -> None:
    with pytest.raises(vendor.VendorError):
        store.resolve("nonesuch", None)


def test_template_entry_shadows_builtin(tmp_path: Path, skill: Path) -> None:
    tvendor = tmp_path / "tvendor"
    write_json(
        tvendor / "libraries.json",
        {
            "schema": 1,
            "libraries": {
                "fakecss": {
                    "current": "9.0.0",
                    "versions": {"9.0.0": lib_entry(tvendor, "fakecss", "9.0.0", [("f.css", "css", "x{}\n", "head", True)])},
                }
            },
        },
    )
    st = vendor.VendorStore([tvendor / "libraries.json", skill / "vendor" / "libraries.json"])
    assert st.resolve("fakecss", None).version == "9.0.0"
    assert st.resolve("fakejs", None).version == "1.1.0"
    absent = vendor.VendorStore([tmp_path / "nope.json", skill / "vendor" / "libraries.json"])
    assert absent.resolve("fakecss", None).version == "1.0.0"


def test_inline_blocks_wrap_and_escape(store: vendor.VendorStore) -> None:
    (block,) = store.inline_blocks(store.resolve("fakejs", "1.0.0"))
    assert block.kind == "js" and block.position == "body-end"
    assert block.text.startswith('<script data-quirk-lib="fakejs@1.0.0">')
    assert block.text.endswith("</script>")
    inner = block.text[len('<script data-quirk-lib="fakejs@1.0.0">') : -len("</script>")]
    assert r"<\/script" in inner and "</SCRIPT" not in inner
    assert sha(inner) == store.resolve("fakejs", "1.0.0").files[0].inline_sha256
    (css,) = store.inline_blocks(store.resolve("fakecss", None))
    assert css.text == '<style data-quirk-lib="fakecss@1.0.0">' + FAKE_CSS + "</style>"
    assert css.kind == "css" and css.position == "head"


def test_inline_blocks_skip_non_inline_files(store: vendor.VendorStore) -> None:
    assert store.inline_blocks(store.resolve("servedonly", None)) == []


def test_inline_blocks_reject_checksum_mismatch(skill: Path, store: vendor.VendorStore) -> None:
    (skill / "vendor" / "fakecss" / "1.0.0" / "fake.css").write_text("body{color:red}\n", encoding="utf-8")
    with pytest.raises(vendor.VendorError) as exc:
        store.inline_blocks(store.resolve("fakecss", None))
    assert "sha256" in str(exc.value) or "checksum" in str(exc.value)


def test_inline_blocks_missing_file(skill: Path, store: vendor.VendorStore) -> None:
    (skill / "vendor" / "fakecss" / "1.0.0" / "fake.css").unlink()
    with pytest.raises(vendor.VendorError):
        store.inline_blocks(store.resolve("fakecss", None))


def test_license_comment_format(store: vendor.VendorStore) -> None:
    lv = store.resolve("fakecss", None)
    assert vendor.license_comment(lv) == "<!-- license: fakecss 1.0.0 MIT | Copyright (c) 2024 Fake Authors -->"


def test_license_comment_never_contains_double_dash(skill: Path) -> None:
    lic = skill / "vendor" / "fakecss" / "1.0.0" / "LICENSE"
    lic.write_text("Copyright (c) 2024 A -- B --> C\n", encoding="utf-8")
    st = vendor.VendorStore([skill / "vendor" / "libraries.json"])
    comment = vendor.license_comment(st.resolve("fakecss", None))
    body = comment[len("<!--") : -len("-->")]
    assert "--" not in body


# tokens


def test_merge_later_wins_per_key_per_group() -> None:
    a = {"schema": 1, "color": {"bg": ["#fff", "#000"], "text": ["#111", "#eee"]}, "radius": {"sm": "4px"}}
    b = {"schema": 1, "color": {"bg": ["#f0f0f0", "#101010"]}, "space": {"1": "2px"}}
    merged = tokens.merge_tokens([a, b])
    assert merged["color"] == {"bg": ["#f0f0f0", "#101010"], "text": ["#111", "#eee"]}
    assert merged["radius"] == {"sm": "4px"}
    assert merged["space"] == {"1": "2px"}


def test_merge_does_not_mutate_inputs() -> None:
    a = {"schema": 1, "color": {"bg": ["#fff", "#000"]}}
    tokens.merge_tokens([a, {"schema": 1, "color": {"bg": ["#eee", "#111"]}}])
    assert a["color"]["bg"] == ["#fff", "#000"]


@pytest.mark.parametrize("bad", ["#fff", ["#fff"], ["#fff", "#000", "#111"], [1, 2], None])
def test_color_must_be_a_light_dark_pair(bad: object) -> None:
    with pytest.raises(ValueError):
        tokens.merge_tokens([{"schema": 1, "color": {"bg": bad}}])
    with pytest.raises(ValueError):
        tokens.tokens_css({"color": {"bg": bad}})


def test_tokens_css_shape() -> None:
    css = tokens.tokens_css(
        {
            "color": {"bg": ["#fff", "#000"], "text-muted": ["#555", "#aaa"]},
            "font": {"sans": "system-ui, sans-serif"},
            "size": {"body": "17px", "h1": "2rem"},
            "space": {"1": "4px"},
            "radius": {"pill": "999px"},
        }
    )
    assert ":root {" in css or ":root{" in css
    assert "--q-color-bg: #fff;" in css and "--q-color-text-muted: #555;" in css
    assert "--q-font-sans: system-ui, sans-serif;" in css
    assert "--q-size-h1: 2rem;" in css and "--q-space-1: 4px;" in css and "--q-radius-pill: 999px;" in css
    media = css.index("@media (prefers-color-scheme: dark)")
    attr = css.index(':root[data-theme="dark"]')
    guard = css.index(':root:not([data-theme="light"])')
    assert media < guard < attr
    light, dark_media, dark_attr = css[:media], css[media:attr], css[attr:]
    assert "--q-color-bg: #fff;" in light and "#000" not in light
    assert "--q-color-bg: #000;" in dark_media and "--q-color-text-muted: #aaa;" in dark_media
    assert "--q-color-bg: #000;" in dark_attr
    assert "--q-font-sans" not in dark_media and "--q-font-sans" not in dark_attr


@pytest.mark.parametrize(
    "bad",
    [
        {"font": {"sans": "x; } body { display: none"}},
        {"font": {"sans": "url(https://x/f.woff2)"}},
        {"size": {"body": "@import 'x'"}},
        {"mystery": {"a": "b"}},
        {"space": {"Bad Key": "4px"}},
    ],
)
def test_tokens_reject_unsafe_values(bad: dict) -> None:
    with pytest.raises(ValueError):
        tokens.tokens_css(bad)


def test_token_layers_order_and_missing_files(tmp_path: Path, skill: Path) -> None:
    (skill / "theme").mkdir(exist_ok=True)
    write_json(skill / "theme" / "house.tokens.json", {"schema": 1, "radius": {"sm": "1px"}})
    user = tmp_path / "user"
    project = tmp_path / "project"
    assert [layer["radius"]["sm"] for layer in tokens.token_layers(skill, user, project, None)] == ["1px"]

    write_json(user / "tokens.json", {"schema": 1, "radius": {"sm": "2px"}})
    write_json(project / ".quirk" / "html-templates" / "tokens.json", {"schema": 1, "radius": {"sm": "3px"}})
    tdir = make_template(tmp_path / "troot", "basic", tokens="tokens.json")
    write_json(tdir / "tokens.json", {"schema": 1, "radius": {"sm": "4px"}})
    tpl = load(tdir)
    layers = tokens.token_layers(skill, user, project, tpl)
    assert [layer["radius"]["sm"] for layer in layers] == ["1px", "2px", "3px", "4px"]
    assert tokens.merge_tokens(layers)["radius"]["sm"] == "4px"


# header


def test_header_round_trip_with_double_dash() -> None:
    meta = {
        "schema": 1,
        "template": "report",
        "template_level": "builtin",
        "tier": 1,
        "tier_signal": "judgment: --- needs a chart --> and <!-- more",
        "mode": "offline",
        "libraries": {"simple-css": "2.3.7"},
        "sidecar": None,
        "built_at": "2026-10-13T00:00:00Z",
        "quirk_version": "unknown",
        "title": "a -- b",
    }
    line = header.render_header(meta)
    assert line.startswith("<!-- quirk-html-artifact {") and line.endswith("} -->")
    assert "\n" not in line
    assert "--" not in line[len("<!--") : -len("-->")]
    assert "\\u002d" in line
    assert header.read_header("<!doctype html>\n" + line + "\n<html></html>") == meta


def test_read_header_missing_or_garbage() -> None:
    assert header.read_header("<!doctype html>\n<html></html>") is None
    assert header.read_header("<!doctype html>\n<!-- quirk-html-artifact {oops -->\n") is None
    assert header.read_header("<!doctype html>\n<!-- quirk-html-artifact [1, 2] -->\n") is None
    assert header.read_header("") is None


# fsutil


def test_atomic_write_str_and_bytes(tmp_path: Path) -> None:
    target = tmp_path / "out.html"
    fsutil.atomic_write(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"
    fsutil.atomic_write(target, b"\x00\x01")
    assert target.read_bytes() == b"\x00\x01"
    assert [p.name for p in tmp_path.iterdir()] == ["out.html"]


def test_atomic_write_failure_leaves_original_and_no_temp(tmp_path: Path) -> None:
    target = tmp_path / "out.html"
    target.write_text("keep", encoding="utf-8")
    with pytest.raises(TypeError):
        fsutil.atomic_write(target, 123)  # type: ignore[arg-type]
    assert target.read_text(encoding="utf-8") == "keep"
    assert [p.name for p in tmp_path.iterdir()] == ["out.html"]


def test_ensure_self_ignoring(tmp_path: Path) -> None:
    d = tmp_path / ".quirk" / "html"
    fsutil.ensure_self_ignoring(d)
    assert (d / ".gitignore").read_text(encoding="utf-8") == "*\n"
    (d / ".gitignore").write_text("custom\n", encoding="utf-8")
    fsutil.ensure_self_ignoring(d)
    assert (d / ".gitignore").read_text(encoding="utf-8") == "custom\n"


# resolve


@pytest.fixture
def levels(tmp_path: Path, skill: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    user = tmp_path / "userroot"
    project = tmp_path / "proj"
    monkeypatch.setenv("QUIRK_HTML_USER_DIR", str(user))
    return {"skill": skill, "user": user, "project": project, "proj_root": project / ".quirk" / "html-templates"}


def test_template_roots_order_and_env_default(levels: dict) -> None:
    roots = resolve.template_roots(levels["skill"], levels["project"], None)
    assert [lvl for lvl, _ in roots] == ["project", "user", "builtin"]
    assert roots[0][1] == levels["proj_root"]
    assert roots[1][1] == levels["user"]
    assert roots[2][1] == levels["skill"] / "templates"


def test_user_dir_default_without_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("QUIRK_HTML_USER_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert resolve.default_user_dir() == Path.home() / ".quirk" / "html-templates"


def test_default_project_dir_uses_git_toplevel(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git not available")
    repo = tmp_path / "repo"
    (repo / "a" / "b").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    assert resolve.default_project_dir(repo / "a" / "b").resolve() == repo.resolve()
    plain = tmp_path / "plain"
    plain.mkdir()
    assert resolve.default_project_dir(plain).resolve() == plain.resolve()


def test_precedence_project_over_user_over_builtin(levels: dict) -> None:
    make_template(levels["skill"] / "templates", "basic")
    make_template(levels["user"], "basic", verified=True)
    make_template(levels["proj_root"], "basic", verified=True)
    roots = resolve.template_roots(levels["skill"], levels["project"], None)
    tpl, warnings = resolve.find_template("basic", roots)
    assert warnings == []
    assert tpl.dir == levels["proj_root"] / "basic" and tpl.level == "project"

    shutil.rmtree(levels["proj_root"] / "basic")
    tpl, _ = resolve.find_template("basic", roots)
    assert tpl.level == "user"
    shutil.rmtree(levels["user"] / "basic")
    tpl, _ = resolve.find_template("basic", roots)
    assert tpl.level == "builtin" and tpl.dir == levels["skill"] / "templates" / "basic"


def test_builtin_does_not_need_verified_but_custom_does(levels: dict) -> None:
    make_template(levels["skill"] / "templates", "basic")
    make_template(levels["proj_root"], "basic")
    roots = resolve.template_roots(levels["skill"], levels["project"], None)
    tpl, warnings = resolve.find_template("basic", roots)
    assert tpl.level == "builtin"
    assert len(warnings) == 1
    w = warnings[0]
    assert set(w) == {"name", "level", "path", "reason"}
    assert w["name"] == "basic" and w["level"] == "project"
    assert w["path"] == str(levels["proj_root"] / "basic")
    assert "unverified" in w["reason"]


def test_invalid_match_is_skipped_with_warning(levels: dict) -> None:
    make_template(levels["skill"] / "templates", "basic")
    bad = make_template(levels["user"], "basic", verified=True)
    meta = json.loads((bad / "template.json").read_text(encoding="utf-8"))
    meta["tier"] = 9
    write_json(bad / "template.json", meta)
    roots = resolve.template_roots(levels["skill"], levels["project"], None)
    tpl, warnings = resolve.find_template("basic", roots)
    assert tpl.level == "builtin"
    assert [w["level"] for w in warnings] == ["user"]


def test_hash_tampering_after_verification_is_skipped(levels: dict) -> None:
    make_template(levels["skill"] / "templates", "basic")
    tdir = make_template(levels["proj_root"], "basic", verified=True)
    (tdir / "skeleton.html").write_text(SKELETON + "<!-- edited -->", encoding="utf-8")
    roots = resolve.template_roots(levels["skill"], levels["project"], None)
    tpl, warnings = resolve.find_template("basic", roots)
    assert tpl.level == "builtin"
    assert "unverified" in warnings[0]["reason"]


def test_template_not_found(levels: dict) -> None:
    roots = resolve.template_roots(levels["skill"], levels["project"], None)
    with pytest.raises(resolve.TemplateNotFound):
        resolve.find_template("nope", roots)
    bad = make_template(levels["proj_root"], "basic")
    with pytest.raises(resolve.TemplateNotFound) as exc:
        resolve.find_template("basic", roots)
    assert "unverified" in str(exc.value)
    assert bad.exists()


@pytest.mark.parametrize("name", ["../escape", "a/b", "", "Upper"])
def test_find_template_rejects_path_like_names(levels: dict, name: str) -> None:
    roots = resolve.template_roots(levels["skill"], levels["project"], None)
    with pytest.raises(resolve.TemplateNotFound):
        resolve.find_template(name, roots)


def test_list_templates_lists_shadowed_names_once(levels: dict) -> None:
    make_template(levels["skill"] / "templates", "basic")
    make_template(levels["skill"] / "templates", "other")
    make_template(levels["proj_root"], "basic", verified=True)
    make_template(levels["user"], "mine", verified=True)
    make_template(levels["user"], "unverified-one")
    roots = resolve.template_roots(levels["skill"], levels["project"], None)
    templates, warnings = resolve.list_templates(roots)
    by_name = {t.name: t for t in templates}
    assert sorted(by_name) == ["basic", "mine", "other"]
    assert len(templates) == 3
    assert by_name["basic"].level == "project"
    assert by_name["other"].level == "builtin"
    assert [(w["name"], w["level"]) for w in warnings] == [("unverified-one", "user")]


def test_list_templates_missing_roots(tmp_path: Path) -> None:
    roots = [("project", tmp_path / "a"), ("user", tmp_path / "b"), ("builtin", tmp_path / "skill" / "templates")]
    assert resolve.list_templates(roots) == ([], [])


# checks


def make_page(
    skill: Path,
    store: vendor.VendorStore,
    *,
    mode: str = "offline",
    tier: int = 1,
    libs: tuple = (("fakecss", "1.0.0"), ("fakejs", "1.0.0")),
    body: str = "<p>hello</p>",
    head: str = "",
    shells: tuple = ("chrome",),
    license_comments: bool = True,
    meta: dict | None = None,
) -> str:
    base_meta = {
        "schema": 1,
        "template": "basic",
        "template_level": "builtin",
        "tier": tier,
        "tier_signal": None,
        "mode": mode if mode != "companion" else "offline",
        "libraries": dict(libs),
        "sidecar": None,
        "built_at": "2026-10-13T00:00:00Z",
        "quirk_version": "unknown",
    }
    parts = ["<!doctype html>", header.render_header(meta if meta is not None else base_meta)]
    head_blocks, end_blocks = [], []
    for name, ver in libs:
        lv = store.resolve(name, ver)
        if license_comments:
            parts.append(vendor.license_comment(lv))
        for blk in store.inline_blocks(lv):
            (head_blocks if blk.position == "head" else end_blocks).append(blk.text)
    parts.append("<html><head><title>t</title>" + "".join(head_blocks) + head + "</head><body>")
    parts.append(body)
    parts.extend(end_blocks)
    for name in shells:
        parts.append(vendor.shell_block(name, skill / "theme" / "chrome.js").text)
    parts.append("</body></html>\n")
    return "\n".join(parts)


def run(skill: Path, store: vendor.VendorStore, html: str, *, mode: str = "offline", tier: int = 1, shells: dict | None = None) -> dict:
    return checks.run_checks(
        html,
        mode=mode,
        tier=tier,
        vendor=store,
        shells=shells if shells is not None else {"chrome": skill / "theme" / "chrome.js"},
    )


def failed(result: dict) -> list[str]:
    return sorted({f["check"] for f in result["failures"]})


def test_clean_page_passes_and_result_shape(skill: Path, store: vendor.VendorStore) -> None:
    result = run(skill, store, make_page(skill, store))
    assert result == {"passed": True, "failures": [], "warnings": []}


def test_library_and_shell_blocks_ignored_by_reference_scan(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store)
    assert "https://cdn.example.com/x.js" in html and "fetch(" in html
    assert run(skill, store, html)["passed"]


def test_header_check(skill: Path, store: vendor.VendorStore) -> None:
    good = make_page(skill, store)
    no_header = "\n".join(line for line in good.split("\n") if "quirk-html-artifact" not in line)
    assert failed(run(skill, store, no_header)) == ["header"]
    schemaless = make_page(skill, store, meta={"template": "basic"})
    assert failed(run(skill, store, schemaless)) == ["header"]
    garbage = good.replace("<!-- quirk-html-artifact {", "<!-- quirk-html-artifact {{{", 1)
    assert failed(run(skill, store, garbage)) == ["header"]


def test_license_check(skill: Path, store: vendor.VendorStore) -> None:
    result = run(skill, store, make_page(skill, store, license_comments=False))
    assert failed(result) == ["license"]
    details = " ".join(f["detail"] for f in result["failures"])
    assert "fakecss@1.0.0" in details and "fakejs@1.0.0" in details


def test_checksum_tampered_library_block(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store).replace("var u=", "var evil=1; var u=", 1)
    result = run(skill, store, html)
    assert failed(result) == ["checksum"]
    assert "fakejs@1.0.0" in result["failures"][0]["detail"]


def test_checksum_tampered_css_block(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store).replace("body{color:#111}", "body{color:#222}")
    assert failed(run(skill, store, html)) == ["checksum"]


def test_checksum_unknown_library_version(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store).replace('data-quirk-lib="fakejs@1.0.0"', 'data-quirk-lib="fakejs@8.8.8"')
    assert "checksum" in failed(run(skill, store, html))


def test_checksum_tampered_shell_block(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store)
    tampered = html.replace('<script data-quirk-shell="chrome">', '<script data-quirk-shell="chrome">window.evil=1;', 1)
    result = run(skill, store, tampered)
    assert failed(result) == ["checksum"]
    assert "chrome" in result["failures"][0]["detail"]


def test_shell_checked_only_when_present(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store, shells=())
    assert run(skill, store, html, shells={"chrome": skill / "theme" / "chrome.js", "companion": skill / "nonexistent.js"})["passed"]


def test_unknown_shell_name_fails_checksum(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store).replace('data-quirk-shell="chrome"', 'data-quirk-shell="mystery"')
    assert "checksum" in failed(run(skill, store, html))


def test_default_shell_map_names() -> None:
    shells = checks.default_shells()
    assert set(shells) == {"chrome", "companion"}
    assert shells["chrome"] == SKILL / "theme" / "chrome.js"
    assert shells["companion"] == SKILL / "templates" / "companion" / "companion.js"


OFFLINE_FAILS = [
    '<script src="https://x.example/y.js"></script>',
    '<script src="//x.example/y.js"></script>',
    '<img src="http://x.example/a.png">',
    '<link rel="stylesheet" href="https://x.example/s.css">',
    '<img srcset="a.png 1x, https://x.example/b.png 2x">',
    '<video poster="https://x.example/p.png"></video>',
    '<form action="https://x.example/post"></form>',
    '<object data="https://x.example/o.swf"></object>',
    "<iframe src='https://x.example/'></iframe>",
    "<img src=https://x.example/a.png>",
    "<style>a{background:url(https://x.example/i.png)}</style>",
    '<style>a{background:URL( "//x.example/i.png" )}</style>',
    '<p style="background:url(\'https://x.example/i.png\')">x</p>',
    '<style>@import "https://x.example/a.css";</style>',
    "<style>@import url(//x.example/a.css);</style>",
    '<script>fetch("/api")</script>',
    "<script>var x = new XMLHttpRequest();</script>",
    '<script>new WebSocket("wss://x.example")</script>',
    '<script>new EventSource("/events")</script>',
]

OFFLINE_PASSES = [
    '<a href="https://example.com/docs">docs</a>',
    '<a class="x" href="http://example.com">docs</a>',
    '<img src="a.png"><link rel="stylesheet" href="local.css">',
    '<img src="data:image/png;base64,AAAA">',
    '<img src="/_quirk/lib/x.png">',
    '<script type="application/json" id="quirk-data">{"u": "https://x.example", "f": "fetch(1)"}</script>',
    "<!-- see https://x.example/a.js and fetch(1) -->",
    "<p>Visit https://x.example for docs.</p>",
    "<style>a{background:url(data:image/png;base64,AAAA)}</style>",
    "<style>a{background:url(local.png)}</style>",
    '<script>const s = "a < b"; document.title = s;</script>',
]


@pytest.mark.parametrize("snippet", OFFLINE_FAILS)
def test_offline_external_refs_fail(skill: Path, store: vendor.VendorStore, snippet: str) -> None:
    result = run(skill, store, make_page(skill, store, body=snippet))
    assert failed(result) == ["external-refs"], result
    assert result["passed"] is False


@pytest.mark.parametrize("snippet", OFFLINE_PASSES)
def test_offline_allowed_content_passes(skill: Path, store: vendor.VendorStore, snippet: str) -> None:
    result = run(skill, store, make_page(skill, store, body=snippet))
    assert result["passed"], result


EVIL_IMG = '<img src="https://evil.example/p.png">'

COMMENT_BYPASSES = [
    f"<!-->{EVIL_IMG}<!-- -->",
    f"<!--->{EVIL_IMG}<!-- -->",
    f"<!-- x --!>{EVIL_IMG}",
    f'<script>var a="<!--";</script>{EVIL_IMG}<script>var b="-->";</script>',
    f'<style>a::after{{content:"<!--"}}</style>{EVIL_IMG}<style>a::before{{content:"-->"}}</style>',
    f"<title><!--</title>{EVIL_IMG}<p>-->",
    f"<![CDATA[ x > {EVIL_IMG} ]]>",
    f"<script>1</script foo>{EVIL_IMG}",
    f'<script/>var a="<!--";</script>{EVIL_IMG}<script>"-->"</script>',
    f"<noscript><!--</noscript>{EVIL_IMG}<p>-->",
    f"<noscript>{EVIL_IMG}</noscript>",
]


@pytest.mark.parametrize("snippet", COMMENT_BYPASSES)
def test_comment_like_text_cannot_hide_markup(skill: Path, store: vendor.VendorStore, snippet: str) -> None:
    result = run(skill, store, make_page(skill, store, body=snippet))
    assert failed(result) == ["external-refs"], result
    assert "https://evil.example/p.png" in result["failures"][0]["detail"]


def test_real_comment_still_hides_markup(skill: Path, store: vendor.VendorStore) -> None:
    assert run(skill, store, make_page(skill, store, body=f"<!-- {EVIL_IMG} -->"))["passed"]


def test_double_escaped_script_keeps_scanning_past_end_tag(skill: Path, store: vendor.VendorStore) -> None:
    body = '<script><!--<script>1</script>fetch("/x")</script>'
    assert failed(run(skill, store, make_page(skill, store, body=body))) == ["external-refs"]


def test_unterminated_script_body_is_scanned(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store, body='<script>fetch("/x")')
    assert failed(run(skill, store, html.replace("</body></html>", ""))) == ["external-refs"]


@pytest.mark.parametrize(
    "snippet",
    [
        "<p>Call fetch(url) to load data.</p>",
        "<p>Use <code>fetch(url)</code>, <code>new WebSocket(u)</code> and XMLHttpRequest.</p>",
        "<pre>new EventSource('/events')</pre>",
    ],
)
def test_call_patterns_in_prose_do_not_fail(skill: Path, store: vendor.VendorStore, snippet: str) -> None:
    result = run(skill, store, make_page(skill, store, body=snippet))
    assert result["passed"], result


@pytest.mark.parametrize(
    "snippet",
    [
        '<button onclick="fetch(\'/api\')">go</button>',
        '<body onload="new XMLHttpRequest()"></body>',
        '<div onmouseover=\'new WebSocket("wss://x")\'></div>',
    ],
)
def test_call_patterns_in_event_handlers_fail(skill: Path, store: vendor.VendorStore, snippet: str) -> None:
    assert failed(run(skill, store, make_page(skill, store, body=snippet))) == ["external-refs"]


def test_connected_allows_calls_in_handlers(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store, mode="connected", body='<button onclick="fetch(\'/api\')">go</button>')
    assert run(skill, store, html, mode="connected")["passed"]


def test_library_block_with_src_fails_external_refs(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store).replace(
        '<script data-quirk-lib="fakejs@1.0.0">',
        '<script data-quirk-lib="fakejs@1.0.0" src="https://evil.example/x.js">',
        1,
    )
    result = run(skill, store, html)
    assert "external-refs" in failed(result)
    assert any("https://evil.example/x.js" in f["detail"] for f in result["failures"])


def test_library_style_block_with_href_or_extra_attribute_is_not_verified(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store).replace(
        '<style data-quirk-lib="fakecss@1.0.0">',
        '<style data-quirk-lib="fakecss@1.0.0" onload="fetch(1)" id="x">',
        1,
    )
    assert not run(skill, store, html)["passed"]


def test_shell_block_with_src_fails_external_refs(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store).replace(
        '<script data-quirk-shell="chrome">',
        '<script data-quirk-shell="chrome" src="https://evil.example/s.js">',
        1,
    )
    result = run(skill, store, html)
    assert "external-refs" in failed(result)
    assert any("https://evil.example/s.js" in f["detail"] for f in result["failures"])


CONNECTED_FAILS = [
    '<script src="https://x.example/y.js"></script>',
    '<script src="//x.example/y.js"></script>',
    '<link rel="stylesheet" href="https://x.example/s.css">',
    '<link rel="preconnect" href="https://fonts.example">',
    '<style>@import url("https://x.example/a.css");</style>',
    "<style>@font-face{font-family:F;src:url(https://x.example/f.woff2)}</style>",
]

CONNECTED_PASSES = [
    '<script>fetch("https://api.example/data").then(r => r.json())</script>',
    '<script>new WebSocket("wss://x.example"); new EventSource("/e"); new XMLHttpRequest();</script>',
    '<img src="https://x.example/a.png">',
    "<style>a{background:url(https://x.example/i.png)}</style>",
    '<a href="https://example.com">x</a>',
    "<style>@font-face{font-family:F;src:url(local.woff2)}</style>",
]


@pytest.mark.parametrize("snippet", CONNECTED_FAILS)
def test_connected_fails(skill: Path, store: vendor.VendorStore, snippet: str) -> None:
    result = run(skill, store, make_page(skill, store, mode="connected", body=snippet), mode="connected")
    assert failed(result) == ["external-refs"], result


@pytest.mark.parametrize("snippet", CONNECTED_PASSES)
def test_connected_allows_data_calls(skill: Path, store: vendor.VendorStore, snippet: str) -> None:
    result = run(skill, store, make_page(skill, store, mode="connected", body=snippet), mode="connected")
    assert result["passed"], result


def test_connected_same_snippets_fail_offline(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store, body='<script>fetch("https://api.example/data")</script>')
    assert failed(run(skill, store, html, mode="offline")) == ["external-refs"]


def test_companion_allows_lib_paths_and_shell_fetch(skill: Path, store: vendor.VendorStore, tmp_path: Path) -> None:
    companion_js = tmp_path / "companion.js"
    companion_js.write_text('fetch("/_quirk/event", {method: "POST"});\n', encoding="utf-8")
    shells = {"chrome": skill / "theme" / "chrome.js", "companion": companion_js}
    html = make_page(
        skill,
        store,
        body='<script src="/_quirk/lib/mermaid.min.js"></script><link rel="stylesheet" href="/_quirk/lib/wa.css">',
        libs=(),
        shells=(),
    )
    html = html.replace("</body>", vendor.shell_block("companion", companion_js).text + "</body>")
    result = run(skill, store, html, mode="companion", shells=shells)
    assert result["passed"], result


def test_companion_still_blocks_external_and_page_fetch(skill: Path, store: vendor.VendorStore) -> None:
    ext = make_page(skill, store, body='<script src="https://x.example/a.js"></script>')
    assert failed(run(skill, store, ext, mode="companion")) == ["external-refs"]
    page_fetch = make_page(skill, store, body='<script>fetch("/x")</script>')
    assert failed(run(skill, store, page_fetch, mode="companion")) == ["external-refs"]


def test_tier2_offline_scans_markup_only(skill: Path, store: vendor.VendorStore) -> None:
    def bundle(body: str) -> str:
        return make_page(skill, store, tier=2, libs=(), shells=(), body=body)

    for bad in (
        '<script src="https://x.example/a.js"></script>',
        '<link rel="stylesheet" href="//x.example/a.css">',
        "<style>@import url(https://x.example/a.css);</style>",
        "<style>a{background:url(https://x.example/i.png)}</style>",
    ):
        assert failed(run(skill, store, bundle(bad), tier=2)) == ["external-refs"], bad
    for ok in (
        '<script>fetch("https://api.example/x"); new WebSocket("wss://x")</script>',
        '<img src="https://x.example/a.png">',
        '<a href="https://example.com">x</a>',
        '<script type="module">import("./chunk.js")</script>',
    ):
        assert run(skill, store, bundle(ok), tier=2)["passed"], ok


def test_tier2_connected(skill: Path, store: vendor.VendorStore) -> None:
    def bundle(body: str) -> str:
        return make_page(skill, store, tier=2, mode="connected", libs=(), shells=(), body=body)

    bad = bundle('<script src="https://x.example/a.js"></script>')
    assert failed(run(skill, store, bad, mode="connected", tier=2)) == ["external-refs"]
    ok = bundle('<script>fetch("https://api.example/x")</script><style>a{background:url(https://x.example/i.png)}</style>')
    assert run(skill, store, ok, mode="connected", tier=2)["passed"]


def test_tier2_has_no_library_blocks_to_license_check(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store, tier=2, libs=(), shells=())
    assert run(skill, store, html, tier=2) == {"passed": True, "failures": [], "warnings": []}


def test_failure_detail_names_the_offending_reference(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store, body='<img src="https://tracker.example/pixel.gif">')
    detail = run(skill, store, html)["failures"][0]["detail"]
    assert "https://tracker.example/pixel.gif" in detail


def test_unknown_mode_is_rejected(skill: Path, store: vendor.VendorStore) -> None:
    with pytest.raises(ValueError):
        run(skill, store, make_page(skill, store), mode="online")


MB = 1024 * 1024


def test_size_warns_over_2mb(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store, body="<p>" + "x" * (2 * MB + 10) + "</p>")
    result = run(skill, store, html)
    assert result["passed"] is True
    assert [w["check"] for w in result["warnings"]] == ["size"]


def test_size_boundary_is_exclusive(skill: Path, store: vendor.VendorStore) -> None:
    base = make_page(skill, store, body="")
    pad = 2 * MB - len(base.encode("utf-8")) - len("<p></p>")
    html = make_page(skill, store, body="<p>" + "x" * pad + "</p>")
    assert len(html.encode("utf-8")) == 2 * MB
    assert run(skill, store, html)["warnings"] == []


def test_size_fails_over_10mb(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store, body="<p>" + "x" * (10 * MB + 10) + "</p>")
    result = run(skill, store, html)
    assert result["passed"] is False
    assert failed(result) == ["size"]


def test_size_counts_bytes_not_characters(skill: Path, store: vendor.VendorStore) -> None:
    html = make_page(skill, store, body="<p>" + "é" * (int(1.5 * MB)) + "</p>")
    assert [w["check"] for w in run(skill, store, html)["warnings"]] == ["size"]


# house theme


def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.fixture(scope="module")
def house() -> dict:
    return json.loads(HOUSE_TOKENS.read_text(encoding="utf-8"))


def test_house_tokens_are_valid_and_complete(house: dict) -> None:
    assert tokens.validate_tokens(house) == []
    assert tokens.merge_tokens([house]) == house
    assert {"bg", "surface", "text", "text-muted", "border", "accent", "accent-text", "good", "warn", "critical", "focus"} <= set(house["color"])
    assert {"sans", "mono", "display"} <= set(house["font"])
    assert {"body", "small", "h1", "h2", "h3", "h4"} <= set(house["size"])
    assert house["size"]["body"] == "17px"
    assert [house["space"][str(i)] for i in range(1, 9)] == ["4px", "8px", "12px", "16px", "24px", "32px", "48px", "64px"]
    assert house["radius"] == {"sm": "4px", "md": "6px", "pill": "999px"}
    for stack in house["font"].values():
        assert "url(" not in stack and "Inter" not in stack


@pytest.mark.parametrize("scheme", [0, 1], ids=["light", "dark"])
@pytest.mark.parametrize("role", ["text", "text-muted", "good", "warn", "critical"])
@pytest.mark.parametrize("ground", ["bg", "surface"])
def test_house_text_colors_reach_4_5(house: dict, scheme: int, role: str, ground: str) -> None:
    c = house["color"]
    assert contrast(c[role][scheme], c[ground][scheme]) >= 4.5


@pytest.mark.parametrize("scheme", [0, 1], ids=["light", "dark"])
def test_house_accent_pairs(house: dict, scheme: int) -> None:
    c = house["color"]
    assert contrast(c["accent"][scheme], c["bg"][scheme]) >= 3.0
    assert contrast(c["accent-text"][scheme], c["accent"][scheme]) >= 4.5
    assert contrast(c["focus"][scheme], c["bg"][scheme]) >= 3.0


def test_house_palette_avoids_purple(house: dict) -> None:
    for pair in house["color"].values():
        for value in pair:
            h = value.lstrip("#")
            r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
            purple = b > g + 40 and r > g + 40
            assert not purple, value


def test_base_css_maps_simple_and_web_awesome_variables() -> None:
    css = BASE_CSS.read_text(encoding="utf-8")
    for var in ("--bg", "--accent-bg", "--text", "--text-light", "--border", "--accent", "--accent-hover", "--accent-text", "--code", "--preformatted", "--marked", "--disabled"):
        assert f"{var}:" in css, var
    assert "--wa-color-brand-" in css and "--wa-color-surface-" in css
    assert "var(--q-color-bg)" in css and "var(--q-color-accent)" in css
    assert "color-scheme: light" in css and "color-scheme: dark" in css
    assert '@media (prefers-color-scheme: dark)' in css and ':root:not([data-theme="light"])' in css
    assert ':root[data-theme="dark"]' in css
    assert ":focus-visible" in css and "outline: 2px solid" in css and "outline-offset: 2px" in css
    assert "[x-cloak]" in css and "display: none !important" in css
    assert ".q-theme-toggle" in css and ".q-data-picker" in css
    assert "url(" not in css.lower() and "@import" not in css.lower() and "@font-face" not in css.lower()


def test_chrome_js_makes_no_network_calls() -> None:
    js = CHROME_JS.read_text(encoding="utf-8")
    for banned in ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "http://", "https://", "import(", "</script", "</SCRIPT"):
        assert banned not in js, banned
    assert "quirkData" in js and "quirk-data-picker" in js and "quirk-data" in js and "data-theme" in js
    assert "try" in js and "localStorage" in js


NODE = shutil.which("node")

CHROME_HARNESS = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
function el(tag) {
  return {
    tag, attrs: {}, children: [], listeners: {}, textContent: "", className: "", files: null, id: "",
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; },
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    appendChild(c) { this.children.push(c); return c; },
  };
}
function run(opts) {
  const root = el("html");
  const body = el("body");
  const byId = {};
  const store = Object.assign({}, opts.storage || {});
  const doc = {
    documentElement: root, body, readyState: "complete", listeners: {},
    getElementById(id) { return byId[id] || null; },
    querySelector(sel) { return opts.preToggle && sel.indexOf("data-quirk-theme-toggle") >= 0 ? opts.preToggle : null; },
    querySelectorAll() { return []; },
    createElement: el,
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
  };
  if (opts.data !== undefined) { const d = el("script"); d.textContent = opts.data; byId["quirk-data"] = d; }
  const win = { localStorage: opts.noStorage ? { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }, removeItem() { throw new Error("blocked"); } } : { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } } };
  new Function("window", "document", src)(win, doc);
  return { root, body, doc, win, store, byId };
}
module.exports = { run, el };
const scenario = process.argv[3];
const out = {};
(async () => {
  if (scenario === "toggle") {
    const t = run({});
    const btn = t.body.children[0];
    out.created = !!btn;
    out.initial = t.root.getAttribute("data-theme");
    const seen = [];
    for (let i = 0; i < 4; i++) { btn.listeners.click[0](); seen.push(t.root.getAttribute("data-theme")); }
    out.cycle = seen;
    out.stored = t.store["quirk-theme"] === undefined ? null : t.store["quirk-theme"];
    const t2 = run({ storage: { "quirk-theme": "dark" } });
    out.restored = t2.root.getAttribute("data-theme");
    const t3 = run({ noStorage: true });
    t3.body.children[0].listeners.click[0]();
    out.noStorage = t3.root.getAttribute("data-theme");
  } else if (scenario === "embedded") {
    const t = run({ data: '{"a": [1, 2], "u": "\\u003c/script>"}' });
    out.value = await t.win.quirkData();
    out.same = t.win.quirkData() === t.win.quirkData();
  } else if (scenario === "picker") {
    const t = run({});
    const p = t.win.quirkData();
    const picker = el("input"); picker.id = "quirk-data-picker";
    picker.files = [{ name: "rows.csv", text: async () => '\ufeffname,qty\r\n' + '"Smith, J",3\r\n' + '"say ' + '""' + 'hi' + '""' + '",4\r\n\r\n' }];
    t.doc.listeners.change[0]({ target: picker });
    out.csv = await p;
    const t2 = run({});
    const p2 = t2.win.quirkData();
    const jp = el("input"); jp.id = "quirk-data-picker";
    jp.files = [{ name: "d.json", text: async () => '{"k": 1}' }];
    t2.doc.listeners.change[0]({ target: jp });
    out.json = await p2;
    out.parse = t.win.quirkData.parseCSV("a,b\n1,2\n3\n");
  }
  console.log(JSON.stringify(out));
})();
"""


def _node(tmp_path: Path, scenario: str) -> dict:
    harness = tmp_path / "harness.js"
    harness.write_text(CHROME_HARNESS, encoding="utf-8")
    proc = subprocess.run(
        ["node", str(harness), str(CHROME_JS), scenario], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_chrome_js_theme_toggle_cycles_and_persists(tmp_path: Path) -> None:
    out = _node(tmp_path, "toggle")
    assert out["created"] is True
    assert out["initial"] is None
    assert out["cycle"] == ["light", "dark", None, "light"]
    assert out["restored"] == "dark"
    assert out["noStorage"] == "light"


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_chrome_js_quirk_data_embedded(tmp_path: Path) -> None:
    out = _node(tmp_path, "embedded")
    assert out["value"] == {"a": [1, 2], "u": "</script>"}
    assert out["same"] is True


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_chrome_js_quirk_data_from_picker(tmp_path: Path) -> None:
    out = _node(tmp_path, "picker")
    assert out["csv"] == [{"name": "Smith, J", "qty": "3"}, {"name": 'say "hi"', "qty": "4"}]
    assert out["json"] == {"k": 1}
    assert out["parse"] == [{"a": "1", "b": "2"}, {"a": "3", "b": ""}]


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_chrome_js_is_valid_script(tmp_path: Path) -> None:
    proc = subprocess.run(["node", "--check", str(CHROME_JS)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert os.path.getsize(CHROME_JS) < 20_000
