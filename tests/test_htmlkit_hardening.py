"""Regression tests for manifest and vendor hardening: unreadable template files, license
comment containment and neutralisation, and one escape rule across the Python implementations."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parent.parent / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

import pins  # noqa: E402
from htmlkit import manifest, vendor  # noqa: E402

DESCRIPTION = "Use when you need a fixture template for the hardening tests."
SKELETON = (
    "<!doctype html>\n{{header}}\n<html><head><title>{{title}}</title>{{head}}</head>\n"
    "<body>{{chrome}}<main>{{slot:main}}</main>{{body_end}}</body></html>\n"
)


def _template(tmp_path: Path) -> Path:
    tdir = tmp_path / "basic"
    tdir.mkdir()
    (tdir / "skeleton.html").write_text(SKELETON, encoding="utf-8")
    (tdir / "example.src.html").write_text("<p>hi</p>\n", encoding="utf-8")
    meta = {
        "schema": 1,
        "name": "basic",
        "description": DESCRIPTION,
        "tier": 1,
        "slots": {"main": {"required": True}},
        "skeleton": "skeleton.html",
        "example": "example.src.html",
    }
    (tdir / "template.json").write_text(json.dumps(meta), encoding="utf-8")
    return tdir


def _problems(tdir: Path, **kw: object) -> list[str]:
    kw.setdefault("require_verified", False)
    return manifest.validate_template(tdir, skill_dir=tdir.parent / "skill", **kw)  # type: ignore[arg-type]


def test_non_utf8_skeleton_is_a_validation_error(tmp_path: Path) -> None:
    tdir = _template(tmp_path)
    assert _problems(tdir) == []
    (tdir / "skeleton.html").write_bytes(b"\xca\xfe\xba\xbe")
    errors = _problems(tdir)
    assert any("skeleton" in e and "cannot be read" in e for e in errors)


def test_non_utf8_tokens_is_a_validation_error(tmp_path: Path) -> None:
    tdir = _template(tmp_path)
    meta = json.loads((tdir / "template.json").read_text(encoding="utf-8"))
    meta["tokens"] = "tokens.json"
    (tdir / "template.json").write_text(json.dumps(meta), encoding="utf-8")
    (tdir / "tokens.json").write_bytes(b"\xff\xfe\x00")
    assert any(e.startswith("tokens") for e in _problems(tdir))


def test_non_utf8_manifest_is_a_validation_error(tmp_path: Path) -> None:
    tdir = _template(tmp_path)
    (tdir / "template.json").write_bytes(b"\xff\xfe{")
    assert _problems(tdir) != []


def test_unreadable_verified_file_is_reported_unverified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tdir = _template(tmp_path)
    (tdir / "verified.json").write_text(
        json.dumps({"schema": 1, "hashes": manifest.compute_hashes(tdir)}), encoding="utf-8"
    )
    real = manifest._sha256_file

    def flaky(path: Path) -> str:
        if path.name == "skeleton.html":
            raise PermissionError("denied")
        return real(path)

    monkeypatch.setattr(manifest, "_sha256_file", flaky)
    errors = _problems(tdir, require_verified=True)
    assert any("unverified" in e and "skeleton.html" in e for e in errors)


def _lib(tmp_path: Path, *, license_file: str = "LICENSE", license: str = "MIT", name: str = "lib") -> vendor.LibraryVersion:
    root = tmp_path / "vendor" / name / "1.0.0"
    root.mkdir(parents=True)
    (root / "LICENSE").write_text("Copyright (c) 2024 Fake Authors\n", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("Copyright (c) Somebody Private\n", encoding="utf-8")
    return vendor.LibraryVersion(
        name=name,
        version="1.0.0",
        package=name,
        license=license,
        license_file=license_file,
        source="",
        files=(),
        root=root,
    )


def test_license_comment_happy_path_is_unchanged(tmp_path: Path) -> None:
    assert vendor.license_comment(_lib(tmp_path)) == "<!-- license: lib 1.0.0 MIT | Copyright (c) 2024 Fake Authors -->"


@pytest.mark.parametrize("escape", ["../../../secret.txt", "../../../../secret.txt"])
def test_license_file_cannot_climb_out_of_the_version_root(tmp_path: Path, escape: str) -> None:
    with pytest.raises(vendor.VendorError, match="escapes"):
        vendor.license_comment(_lib(tmp_path, license_file=escape))


def test_license_file_cannot_be_absolute(tmp_path: Path) -> None:
    with pytest.raises(vendor.VendorError, match="escapes"):
        vendor.license_comment(_lib(tmp_path, license_file=str(tmp_path / "secret.txt")))


def test_license_file_that_is_not_utf8_raises_vendor_error(tmp_path: Path) -> None:
    lv = _lib(tmp_path)
    (lv.root / "LICENSE").write_bytes(b"\xca\xfe")
    with pytest.raises(vendor.VendorError, match="cannot read license file"):
        vendor.license_comment(lv)


@pytest.mark.parametrize("field", ["license", "name"])
def test_license_comment_neutralises_every_interpolated_field(tmp_path: Path, field: str) -> None:
    hostile = "MIT --> <img src=https://evil/x> <!--"
    lv = _lib(tmp_path, **{field: hostile}) if field == "license" else _lib(tmp_path, name="a-->b<c")
    comment = vendor.license_comment(lv)
    body = comment[len("<!--") : -len("-->")]
    assert "--" not in body and "<" not in body and ">" not in body
    assert comment.startswith("<!-- license: ") and comment.endswith(" -->")


def test_license_comment_neutralises_angle_brackets_in_the_copyright_line(tmp_path: Path) -> None:
    lv = _lib(tmp_path)
    (lv.root / "LICENSE").write_text("Copyright (c) A <a@example.com>\n", encoding="utf-8")
    comment = vendor.license_comment(lv)
    assert "<a@" not in comment and "&lt;a@example.com&gt;" in comment


ESCAPE_CASES = [
    "a</script>b</SCRIPT >c</sCrIpT",
    "a</style>b</STYLE>c</StYlE",
    "a</ſcript>b</Kstyle>",
    "no closers é\n",
]


@pytest.mark.parametrize("kind", ["js", "css"])
@pytest.mark.parametrize("text", ESCAPE_CASES)
def test_python_escape_implementations_agree(text: str, kind: str) -> None:
    assert pins.escape_inline(text, kind) == vendor.escape_inline(text, kind)


def test_escape_rule_is_ascii_only() -> None:
    text = "a</ſcript>b"
    assert pins.escape_inline(text, "js") == text
    assert vendor.escape_inline(text, "js") == text


def test_vendored_hashes_still_match_the_ascii_rule() -> None:
    assert pins.verify(SKILL / "vendor") == []


def _tier2(tmp_path: Path, files: dict[str, str]) -> Path:
    tdir = tmp_path / "kit"
    (tdir / "project").mkdir(parents=True)
    meta = {"schema": 1, "name": "kit", "description": DESCRIPTION, "tier": 2, "project": "project/"}
    (tdir / "template.json").write_text(json.dumps(meta), encoding="utf-8")
    for rel, text in {"project/package.json": "{}", "project/pnpm-lock.yaml": "", **files}.items():
        path = tdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tdir


def test_tier_2_verification_covers_the_whole_project_tree_except_build_output(tmp_path: Path) -> None:
    tdir = _tier2(
        tmp_path,
        {
            "project/.pnpmfile.cjs": "module.exports = {}",
            "project/vite.config.ts": "export default {}",
            "project/src/App.tsx": "x",
            "project/node_modules/dep/index.js": "x",
            "project/dist/index.html": "x",
            "project/.DS_Store": "x",
        },
    )
    assert manifest.verification_paths(tdir) == [
        "project/.pnpmfile.cjs",
        "project/package.json",
        "project/pnpm-lock.yaml",
        "project/src/App.tsx",
        "project/vite.config.ts",
        "template.json",
    ]


def test_editing_a_tier_2_build_script_after_verifying_makes_it_unverified(tmp_path: Path) -> None:
    tdir = _tier2(tmp_path, {"project/vite.config.ts": "export default {}"})
    stamp = {"schema": 1, "verified_at": "", "browser": False, "hashes": manifest.compute_hashes(tdir)}
    (tdir / "verified.json").write_text(json.dumps(stamp), encoding="utf-8")
    assert _problems(tdir, require_verified=True) == []
    (tdir / "project" / "vite.config.ts").write_text("export default { evil: 1 }", encoding="utf-8")
    assert any("vite.config.ts changed" in e for e in _problems(tdir, require_verified=True))
    (tdir / "project" / "vite.config.ts").write_text("export default {}", encoding="utf-8")
    (tdir / "project" / ".pnpmfile.cjs").write_text("module.exports = {}", encoding="utf-8")
    assert any(".pnpmfile.cjs is not covered" in e for e in _problems(tdir, require_verified=True))


def _tier2_with_example(tmp_path: Path, files: dict[str, str]) -> Path:
    tdir = _tier2(tmp_path, files)
    meta = json.loads((tdir / "template.json").read_text(encoding="utf-8"))
    meta["example"] = "example/"
    (tdir / "template.json").write_text(json.dumps(meta), encoding="utf-8")
    return tdir


def test_tier_2_verification_covers_every_example_file_except_build_output(tmp_path: Path) -> None:
    tdir = _tier2_with_example(
        tmp_path,
        {
            "example/vite.config.ts": "export default {}",
            "example/src/routes.tsx": "x",
            "example/node_modules/dep/index.js": "x",
            "example/dist/index.html": "x",
            "example/.DS_Store": "x",
        },
    )
    assert manifest.verification_paths(tdir) == [
        "example/src/routes.tsx",
        "example/vite.config.ts",
        "project/package.json",
        "project/pnpm-lock.yaml",
        "template.json",
    ]


def test_editing_a_tier_2_example_after_verifying_makes_it_unverified(tmp_path: Path) -> None:
    tdir = _tier2_with_example(tmp_path, {"example/vite.config.ts": "export default {}"})
    stamp = {"schema": 1, "verified_at": "", "browser": False, "hashes": manifest.compute_hashes(tdir)}
    (tdir / "verified.json").write_text(json.dumps(stamp), encoding="utf-8")
    assert _problems(tdir, require_verified=True) == []
    (tdir / "example" / "vite.config.ts").write_text("export default { evil: 1 }", encoding="utf-8")
    assert any("example/vite.config.ts changed" in e for e in _problems(tdir, require_verified=True))


def _tier1_with_data(tmp_path: Path, header: dict) -> Path:
    tdir = _template(tmp_path)
    (tdir / "example.src.html").write_text(
        "<!-- quirk-src " + json.dumps(header) + " -->\n<!-- slot: main -->\n<p>hi</p>\n", encoding="utf-8"
    )
    return tdir


def test_tier_1_verification_covers_the_example_data_file(tmp_path: Path) -> None:
    tdir = _tier1_with_data(tmp_path, {"template": "basic", "title": "T", "data": "example.data.json"})
    (tdir / "example.data.json").write_text('{"a": 1}', encoding="utf-8")
    assert "example.data.json" in manifest.verification_paths(tdir)
    stamp = {"schema": 1, "verified_at": "", "browser": False, "hashes": manifest.compute_hashes(tdir)}
    (tdir / "verified.json").write_text(json.dumps(stamp), encoding="utf-8")
    assert _problems(tdir, require_verified=True) == []
    (tdir / "example.data.json").write_text('{"a": 2}', encoding="utf-8")
    assert any("example.data.json changed" in e for e in _problems(tdir, require_verified=True))


def test_tier_1_example_data_outside_the_template_is_not_hashed(tmp_path: Path) -> None:
    tdir = _tier1_with_data(tmp_path, {"template": "basic", "title": "T", "data": "../outside.json"})
    (tmp_path / "outside.json").write_text("{}", encoding="utf-8")
    assert not any("outside" in p for p in manifest.verification_paths(tdir))


def test_tier_1_example_without_data_adds_no_data_path(tmp_path: Path) -> None:
    tdir = _tier1_with_data(tmp_path, {"template": "basic", "title": "T"})
    assert manifest.verification_paths(tdir) == ["example.src.html", "skeleton.html", "template.json"]


@pytest.mark.parametrize("name", ["report\n", "report\n\n", "\nreport"])
def test_a_template_name_with_a_trailing_newline_is_rejected(name: str) -> None:
    assert manifest.NAME_RE.match(name) is None
    assert manifest.NAME_RE.match("report") is not None


def test_a_manifest_name_with_a_trailing_newline_is_invalid(tmp_path: Path) -> None:
    tdir = _template(tmp_path)
    meta = json.loads((tdir / "template.json").read_text(encoding="utf-8"))
    meta["name"] = "basic\n"
    (tdir / "template.json").write_text(json.dumps(meta), encoding="utf-8")
    assert any("must match" in e for e in _problems(tdir))


def test_a_symlink_under_a_tier_2_project_is_a_validation_error(tmp_path: Path) -> None:
    tdir = _tier2(tmp_path, {"project/src/App.tsx": "x"})
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.ts").write_text("x", encoding="utf-8")
    (tdir / "project" / "linked").symlink_to(outside, target_is_directory=True)
    (tdir / "project" / "App.link.tsx").symlink_to(tdir / "project" / "src" / "App.tsx")
    problems = _problems(tdir)
    assert any("project/linked is a symlink" in p for p in problems)
    assert any("project/App.link.tsx is a symlink" in p for p in problems)


def test_a_symlink_under_a_tier_2_example_is_a_validation_error(tmp_path: Path) -> None:
    tdir = _tier2_with_example(tmp_path, {"example/src/App.tsx": "x"})
    outside = tmp_path / "outside"
    outside.mkdir()
    (tdir / "example" / "linked").symlink_to(outside, target_is_directory=True)
    assert any("example/linked is a symlink" in p for p in _problems(tdir))


def test_a_symlink_under_tier_1_vendor_is_a_validation_error(tmp_path: Path) -> None:
    tdir = _template(tmp_path)
    (tdir / "vendor").mkdir()
    real = tmp_path / "real.js"
    real.write_text("x", encoding="utf-8")
    (tdir / "vendor" / "lib.js").symlink_to(real)
    assert any("vendor/lib.js is a symlink" in p for p in _problems(tdir))


def test_a_template_without_symlinks_has_no_symlink_problems(tmp_path: Path) -> None:
    tdir = _tier2(tmp_path, {"project/src/App.tsx": "x", "project/node_modules/dep/index.js": "x"})
    assert not any("symlink" in p for p in _problems(tdir))
