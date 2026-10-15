"""Contract for the vendored library store and its offline checksum verifier (pins.py)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
SCRIPT = SKILL / "scripts" / "pins.py"
VENDOR = SKILL / "vendor"

sys.path.insert(0, str(SCRIPT.parent))
import pins  # noqa: E402


def run_verify(*args: str) -> "tuple[int, Dict[str, Any]]":
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "verify", *args],
        capture_output=True,
        text=True,
    )
    return proc.returncode, json.loads(proc.stdout)


@pytest.fixture()
def vendor_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "vendor"
    shutil.copytree(VENDOR, dest)
    return dest


def test_verify_passes_on_real_vendor_dir() -> None:
    code, out = run_verify()
    assert code == 0
    assert out == {"ok": True, "errors": []}


def test_manifest_lists_v1_libraries_at_pinned_versions() -> None:
    manifest = json.loads((VENDOR / "libraries.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == 1
    current = {n: lib["current"] for n, lib in manifest["libraries"].items()}
    assert current == {
        "simple-css": "2.3.7",
        "alpine": "3.17.4",
        "chartjs": "4.5.1",
        "mermaid": "12.2.0",
        "webawesome": "3.14.0",
        "highlightjs": "11.12.0",
        "kit": "1.0.0",
    }
    alpine_file = manifest["libraries"]["alpine"]["versions"]["3.17.4"]["files"][0]
    assert alpine_file["position"] == "body-end"
    mermaid_file = manifest["libraries"]["mermaid"]["versions"]["12.2.0"]["files"][0]
    assert mermaid_file["inline"] is True


def test_tampered_file_is_named_and_fails(vendor_copy: Path) -> None:
    target = vendor_copy / "simple-css" / "2.3.7" / "simple.min.css"
    data = bytearray(target.read_bytes())
    data[10] = ord("X") if data[10] != ord("X") else ord("Y")
    target.write_bytes(bytes(data))
    code, out = run_verify("--vendor-dir", str(vendor_copy))
    assert code == 1
    assert out["ok"] is False
    assert any("simple-css/2.3.7/simple.min.css" in e for e in out["errors"])


def test_missing_license_is_reported(vendor_copy: Path) -> None:
    (vendor_copy / "alpine" / "3.17.4" / "LICENSE").unlink()
    code, out = run_verify("--vendor-dir", str(vendor_copy))
    assert code == 1
    assert any("alpine/3.17.4/LICENSE" in e for e in out["errors"])


def test_missing_file_is_reported(vendor_copy: Path) -> None:
    (vendor_copy / "chartjs" / "4.5.1" / "chart.umd.js").unlink()
    code, out = run_verify("--vendor-dir", str(vendor_copy))
    assert code == 1
    assert any("chartjs/4.5.1/chart.umd.js" in e for e in out["errors"])


def test_current_must_name_an_existing_version(vendor_copy: Path) -> None:
    manifest_path = vendor_copy / "libraries.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["libraries"]["mermaid"]["current"] = "0.0.0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    code, out = run_verify("--vendor-dir", str(vendor_copy))
    assert code == 1
    assert any("mermaid" in e and "0.0.0" in e for e in out["errors"])


def test_escape_inline_script_is_case_insensitive() -> None:
    assert pins.escape_inline("a</script>b</SCRIPT >c", "js") == "a<\\/script>b<\\/script >c"


def test_escape_inline_style_is_case_insensitive() -> None:
    assert pins.escape_inline("a</STYLE>b</style>", "css") == "a<\\/style>b<\\/style>"


def test_escape_inline_leaves_other_text_untouched() -> None:
    text = "x</style> y <script>z</div> é\n"
    assert pins.escape_inline(text, "js") == text
    assert pins.escape_inline("</script> q", "css") == "</script> q"


def test_escape_inline_ignores_non_ascii_case_folds() -> None:
    text = "a</\u017fcript>b</\u212astyle>"
    assert pins.escape_inline(text, "js") == text
    assert pins.escape_inline(text, "css") == text


def test_non_inline_file_needs_no_inline_sha256(vendor_copy: Path) -> None:
    manifest_path = vendor_copy / "libraries.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec = manifest["libraries"]["chartjs"]["versions"]["4.5.1"]["files"][0]
    spec["inline"] = False
    del spec["inline_sha256"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    code, out = run_verify("--vendor-dir", str(vendor_copy))
    assert (code, out["errors"]) == (0, [])


def test_inline_file_still_needs_a_matching_inline_sha256(vendor_copy: Path) -> None:
    manifest_path = vendor_copy / "libraries.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec = manifest["libraries"]["chartjs"]["versions"]["4.5.1"]["files"][0]
    spec["inline"] = True
    spec["inline_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    code, out = run_verify("--vendor-dir", str(vendor_copy))
    assert code == 1
    assert any("inline_sha256" in e for e in out["errors"])


def test_escape_inline_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        pins.escape_inline("x", "html")


WEBAWESOME_DIR = VENDOR / "webawesome" / "3.14.0"


def test_webawesome_manifest_entry_positions_and_hashes() -> None:
    manifest = json.loads((VENDOR / "libraries.json").read_text(encoding="utf-8"))
    entry = manifest["libraries"]["webawesome"]["versions"]["3.14.0"]
    assert entry["package"] == "@awesome.me/webawesome"
    assert entry["license"] == "MIT"
    files = {f["path"]: f for f in entry["files"]}
    assert set(files) == {"webawesome.bundle.js", "webawesome.css"}
    assert files["webawesome.css"]["kind"] == "css"
    assert files["webawesome.css"]["position"] == "head"
    assert files["webawesome.bundle.js"]["kind"] == "js"
    assert files["webawesome.bundle.js"]["position"] == "body-end"
    assert all(f["inline"] is True for f in files.values())


def test_every_file_position_matches_its_kind() -> None:
    manifest = json.loads((VENDOR / "libraries.json").read_text(encoding="utf-8"))
    expected = {"js": "body-end", "css": "head"}
    for name, lib in manifest["libraries"].items():
        for version, entry in lib["versions"].items():
            for f in entry["files"]:
                assert f["position"] == expected[f["kind"]], f"{name} {version} {f['path']}"


def test_webawesome_bundle_is_a_single_file_iife() -> None:
    text = (WEBAWESOME_DIR / "webawesome.bundle.js").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|export)\s", text, re.MULTILINE)
    assert not re.search(r"\bimport\s*\(", text)


def test_webawesome_bundle_never_reaches_the_font_awesome_cdn() -> None:
    text = (WEBAWESOME_DIR / "webawesome.bundle.js").read_text(encoding="utf-8")
    assert "ka-f.fontawesome.com" not in text
    assert "data:image/svg+xml" in text
    assert re.search(r"registerIconLibrary\(\s*[\"']default[\"']", text)


def test_webawesome_css_is_self_contained() -> None:
    text = (WEBAWESOME_DIR / "webawesome.css").read_text(encoding="utf-8")
    assert "@import" not in text
    assert "url(http" not in text
    assert 'url("http' not in text
    assert "url('http" not in text


def test_webawesome_notes_record_the_dark_class() -> None:
    lines = (WEBAWESOME_DIR / "NOTES.md").read_text(encoding="utf-8").splitlines()
    assert any(re.fullmatch(r"dark-class: \S+", line) for line in lines)
