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
