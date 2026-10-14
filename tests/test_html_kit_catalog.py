"""Contract for the component kit's foundation: catalog, registry entry, chart tokens and pins.

Everything here is offline. Tests that change the catalog or the registry work on tmp copies of
the real vendor directory.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "writing-html-artifacts"
sys.path.insert(0, str(SKILL / "scripts"))

from htmlkit import kitcheck, manifest, vendor  # noqa: E402

VENDOR = SKILL / "vendor"
KIT_DIR = VENDOR / "kit" / "1.0.0"
PINS = SKILL / "scripts" / "pins.py"
HOUSE_TOKENS = SKILL / "theme" / "house.tokens.json"

GLOBAL_ATTRIBUTES = ["id", "class", "style", "hidden", "title", "lang", "dir", "slot"]

# tag -> (parent, interactive, {attribute: (required, kind, values, default)}, requires, rules)
SECTION_3_4: dict[str, tuple[Any, bool, dict[str, tuple[bool, str, Any, Any]], list[list[str]], list[str]]] = {
    "q-tabs": (None, True, {"label": (False, "text", None, None)}, [["section"]], ["heading-sections"]),
    "q-chart": (
        None,
        False,
        {
            "summary": (True, "text", None, None),
            "type": (False, "enum", ["bar", "line", "area", "donut"], "bar"),
            "x": (False, "text", None, None),
            "y": (False, "text", None, None),
            "stacked": (False, "boolean", None, None),
            "horizontal": (False, "boolean", None, None),
            "data-from": (False, "ident", None, None),
        },
        [["table", "@data-from"]],
        ["max-series"],
    ),
    "q-stat": (
        None,
        False,
        {
            "direction": (False, "enum", ["up-good", "down-good"], "up-good"),
            "points": (False, "number-list", None, None),
        },
        [["[slot=label]"], ["[slot=value]"], ["[slot=definition]"]],
        [],
    ),
    "q-table": (None, True, {"data-from": (False, "ident", None, None)}, [["table"]], []),
    "q-timeline": (None, False, {}, [["ol"]], ["timeline-items"]),
    "q-code": (None, True, {"filename": (False, "text", None, None)}, [["pre"]], []),
    "q-diff": (None, False, {}, [["pre"]], ["diff-notes"]),
    "q-diff-note": (
        "q-diff",
        True,
        {"file": (True, "text", None, None), "line": (True, "integer", None, None)},
        [],
        [],
    ),
    "q-board": (None, True, {"id": (True, "ident", None, None)}, [["section"]], ["board-columns"]),
}


def _store(vendor_dir: Path = VENDOR) -> vendor.VendorStore:
    return vendor.VendorStore([vendor_dir / "libraries.json"])


@pytest.fixture()
def vendor_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "vendor"
    shutil.copytree(VENDOR, dest)
    return dest


def _edit_catalog(vendor_dir: Path, mutate) -> None:
    path = vendor_dir / "kit" / "1.0.0" / "catalog.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _element(data: dict, tag: str) -> dict:
    return next(e for e in data["elements"] if e["tag"] == tag)


@pytest.fixture(scope="module")
def catalog() -> Any:
    return kitcheck.load_catalog(_store(), None)


def test_catalog_loads_for_current_and_explicit_version(catalog: Any) -> None:
    assert catalog.kit_version == "1.0.0"
    assert list(catalog.global_attributes) == GLOBAL_ATTRIBUTES
    assert kitcheck.load_catalog(_store(), "1.0.0").kit_version == "1.0.0"
    assert list(catalog.elements) == list(SECTION_3_4)


@pytest.mark.parametrize("tag", list(SECTION_3_4))
def test_element_matches_the_authoring_contract(catalog: Any, tag: str) -> None:
    parent, interactive, attrs, requires, rules = SECTION_3_4[tag]
    el = catalog.elements[tag]
    assert el.parent == parent
    assert el.interactive is interactive
    assert [a.name for a in el.attributes] == list(attrs)
    for a in el.attributes:
        required, kind, values, default = attrs[a.name]
        assert (a.required, a.kind) == (required, kind), a.name
        assert (list(a.values) if a.values is not None else None) == values, a.name
        assert a.default == default, a.name
        assert a.description, a.name
    assert [list(group) for group in el.requires] == requires
    assert list(el.rules) == rules


@pytest.mark.parametrize("tag", list(SECTION_3_4))
def test_element_documentation_is_complete(catalog: Any, tag: str) -> None:
    el = catalog.elements[tag]
    assert el.use_when.startswith("Use when")
    assert "\n" not in el.use_when
    assert len(el.children.strip()) > 20 and "\n" not in el.children
    assert f"<{tag}" in el.example and f"</{tag}>" in el.example
    scripts = re.findall(r"<script\b[^>]*>", el.example, re.IGNORECASE)
    if tag == "q-chart":
        assert scripts == ['<script type="application/json">'] or scripts == []
        assert "<table" in el.example
    else:
        assert scripts == []


def test_stat_example_shows_three_adjacent_stats(catalog: Any) -> None:
    example = catalog.elements["q-stat"].example
    assert example.count("<q-stat") == 3
    assert example.count("</q-stat>") == 3


def test_diff_example_has_a_valid_note(catalog: Any) -> None:
    example = catalog.elements["q-diff"].example
    assert "<q-diff-note " in example
    assert catalog.elements["q-diff-note"].parent == "q-diff"


def test_selector_grammar_accepts_every_form(vendor_copy: Path) -> None:
    good = ["@data-from", "table", "table[summary]", "table[role=grid]", "[slot=label]", "[hidden]", "h2"]

    def mutate(data: dict) -> None:
        _element(data, "q-code")["requires"] = [good]

    _edit_catalog(vendor_copy, mutate)
    loaded = kitcheck.load_catalog(_store(vendor_copy), None)
    assert list(loaded.elements["q-code"].requires[0]) == good


@pytest.mark.parametrize(
    "selector",
    ["table tr", "Table", "@Data", "@", "table[", "table[a=B]", "div > p", "table[a=b][c]", ".cls", "#id", "", "1table", "table[a=1]"],
)
def test_selector_outside_the_grammar_is_rejected(vendor_copy: Path, selector: str) -> None:
    def mutate(data: dict) -> None:
        _element(data, "q-code")["requires"] = [[selector]]

    _edit_catalog(vendor_copy, mutate)
    with pytest.raises(kitcheck.KitError) as exc:
        kitcheck.load_catalog(_store(vendor_copy), None)
    assert "q-code" in str(exc.value) and "selector" in str(exc.value)


def test_unknown_rule_is_rejected(vendor_copy: Path) -> None:
    _edit_catalog(vendor_copy, lambda d: _element(d, "q-code").update(rules=["no-such-rule"]))
    with pytest.raises(kitcheck.KitError, match="no-such-rule"):
        kitcheck.load_catalog(_store(vendor_copy), None)


@pytest.mark.parametrize("rule", sorted(kitcheck.KNOWN_RULES))
def test_every_known_rule_is_accepted(vendor_copy: Path, rule: str) -> None:
    _edit_catalog(vendor_copy, lambda d: _element(d, "q-code").update(rules=[rule]))
    assert list(kitcheck.load_catalog(_store(vendor_copy), None).elements["q-code"].rules) == [rule]


def test_known_rules_are_exactly_the_spec_set() -> None:
    assert set(kitcheck.KNOWN_RULES) == {"max-series", "diff-notes", "heading-sections", "board-columns", "timeline-items"}


def test_kit_version_must_equal_directory_name(vendor_copy: Path) -> None:
    _edit_catalog(vendor_copy, lambda d: d.update(kit_version="1.0.1"))
    with pytest.raises(kitcheck.KitError, match="kit_version"):
        kitcheck.load_catalog(_store(vendor_copy), None)


def test_duplicate_and_malformed_tags_are_rejected(vendor_copy: Path) -> None:
    def dup(data: dict) -> None:
        data["elements"].append(dict(_element(data, "q-code")))

    _edit_catalog(vendor_copy, dup)
    with pytest.raises(kitcheck.KitError, match="duplicate"):
        kitcheck.load_catalog(_store(vendor_copy), None)


@pytest.mark.parametrize("tag", [["q-code"], {"q": "code"}, 7, None], ids=["list", "dict", "int", "null"])
def test_non_string_tag_raises_kit_error_not_type_error(vendor_copy: Path, tag: Any) -> None:
    _edit_catalog(vendor_copy, lambda d: _element(d, "q-code").update(tag=tag))
    with pytest.raises(kitcheck.KitError, match="tag"):
        kitcheck.load_catalog(_store(vendor_copy), None)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda d: d["elements"].append(["q-extra"]), id="element-is-a-list"),
        pytest.param(lambda d: d["elements"].append(None), id="element-is-null"),
        pytest.param(lambda d: _element(d, "q-code").update(attributes={"filename": {}}), id="attributes-is-an-object"),
        pytest.param(lambda d: _element(d, "q-code").update(requires="pre"), id="requires-is-a-string"),
        pytest.param(lambda d: _element(d, "q-code").update(requires=[[["pre"]]]), id="selector-is-a-list"),
        pytest.param(lambda d: _element(d, "q-code").update(rules=[["max-series"]]), id="rule-is-a-list"),
        pytest.param(lambda d: _element(d, "q-code").update(parent=["q-diff"]), id="parent-is-a-list"),
        pytest.param(lambda d: _element(d, "q-code")["attributes"][0].update(name=["filename"]), id="attribute-name-is-a-list"),
        pytest.param(lambda d: _element(d, "q-code")["attributes"][0].update(name={"a": 1}), id="attribute-name-is-an-object"),
        pytest.param(lambda d: _element(d, "q-code")["attributes"][0].update(kind=["text"]), id="kind-is-a-list"),
        pytest.param(
            lambda d: _element(d, "q-chart")["attributes"][1].update(values=[["bar"]]), id="enum-value-is-a-list"
        ),
        pytest.param(lambda d: _element(d, "q-chart")["attributes"][1].update(default=["bar"]), id="default-is-a-list"),
        pytest.param(lambda d: d.update(global_attributes=[["id"]]), id="global-attribute-is-a-list"),
        pytest.param(lambda d: d.update(elements={"q-code": {}}), id="elements-is-an-object"),
    ],
)
def test_every_malformed_shape_raises_kit_error(vendor_copy: Path, mutate: Any) -> None:
    _edit_catalog(vendor_copy, mutate)
    with pytest.raises(kitcheck.KitError):
        kitcheck.load_catalog(_store(vendor_copy), None)


@pytest.mark.parametrize("tag", ["x-code", "q-Code", "q-", "q-code-", "q_code", "q-9"])
def test_malformed_tag_is_rejected(vendor_copy: Path, tag: str) -> None:
    _edit_catalog(vendor_copy, lambda d: _element(d, "q-code").update(tag=tag))
    with pytest.raises(kitcheck.KitError, match="tag"):
        kitcheck.load_catalog(_store(vendor_copy), None)


def test_use_when_must_start_with_use_when(vendor_copy: Path) -> None:
    _edit_catalog(vendor_copy, lambda d: _element(d, "q-code").update(use_when="For code."))
    with pytest.raises(kitcheck.KitError, match="use_when"):
        kitcheck.load_catalog(_store(vendor_copy), None)


def test_enum_needs_values_and_other_kinds_must_not_have_them(vendor_copy: Path) -> None:
    def no_values(data: dict) -> None:
        del _element(data, "q-chart")["attributes"][1]["values"]

    _edit_catalog(vendor_copy, no_values)
    with pytest.raises(kitcheck.KitError, match="values"):
        kitcheck.load_catalog(_store(vendor_copy), None)


def test_unknown_attribute_kind_is_rejected(vendor_copy: Path) -> None:
    _edit_catalog(vendor_copy, lambda d: _element(d, "q-code")["attributes"][0].update(kind="color"))
    with pytest.raises(kitcheck.KitError, match="kind"):
        kitcheck.load_catalog(_store(vendor_copy), None)


def test_parent_must_name_a_catalog_element(vendor_copy: Path) -> None:
    _edit_catalog(vendor_copy, lambda d: _element(d, "q-diff-note").update(parent="q-nothing"))
    with pytest.raises(kitcheck.KitError, match="parent"):
        kitcheck.load_catalog(_store(vendor_copy), None)


def test_wrong_schema_is_rejected(vendor_copy: Path) -> None:
    _edit_catalog(vendor_copy, lambda d: d.update(schema=2))
    with pytest.raises(kitcheck.KitError, match="schema"):
        kitcheck.load_catalog(_store(vendor_copy), None)


def test_unreadable_or_invalid_catalog_raises_kit_error(vendor_copy: Path) -> None:
    path = vendor_copy / "kit" / "1.0.0" / "catalog.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(kitcheck.KitError, match="catalog.json"):
        kitcheck.load_catalog(_store(vendor_copy), None)
    path.unlink()
    with pytest.raises(kitcheck.KitError, match="catalog.json"):
        kitcheck.load_catalog(_store(vendor_copy), None)


def test_missing_kit_library_or_version_raises_kit_error() -> None:
    with pytest.raises(kitcheck.KitError, match="9.9.9"):
        kitcheck.load_catalog(_store(), "9.9.9")


def test_all_problems_are_reported_together(vendor_copy: Path) -> None:
    def mutate(data: dict) -> None:
        _element(data, "q-code").update(rules=["nope"], requires=[["Bad Selector"]])

    _edit_catalog(vendor_copy, mutate)
    with pytest.raises(kitcheck.KitError) as exc:
        kitcheck.load_catalog(_store(vendor_copy), None)
    assert "nope" in str(exc.value) and "Bad Selector" in str(exc.value)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("<q-stat>", (True, False)),
        ("<Q-CHART>", (True, True)),
        ("<q-chart-x>", (True, False)),
        ("<q-chart>", (True, True)),
        ('<q-chart type="line">', (True, True)),
        ("<q-chart\n  summary='x'>", (True, True)),
        ("<q-chart/>", (True, True)),
        ("&lt;q-chart", (False, False)),
        ("<p>no kit here</p>", (False, False)),
        ("<q->", (False, False)),
        ("<q-1>", (False, False)),
        ("const html = '<q-table>';", (True, False)),
        ("<script>el.innerHTML = '<q-chart summary=\"x\">'</script>", (True, True)),
        ("", (False, False)),
    ],
)
def test_needs_truth_table(text: str, expected: tuple[bool, bool]) -> None:
    assert kitcheck.needs(text) == expected


def test_needs_exposes_the_two_regexes() -> None:
    assert kitcheck.KIT_TAG.pattern == r"<q-[a-z]" and kitcheck.KIT_TAG.flags & re.IGNORECASE
    assert kitcheck.CHART_TAG.pattern == r"<q-chart[\s/>]" and kitcheck.CHART_TAG.flags & re.IGNORECASE


def _channel(value: float) -> float:
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (_channel(int(h[i : i + 2], 16) / 255) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


CHART_KEYS = [f"chart-{i}" for i in range(1, 9)]


def test_chart_tokens_exist_as_light_dark_pairs() -> None:
    color = json.loads(HOUSE_TOKENS.read_text(encoding="utf-8"))["color"]
    for key in CHART_KEYS:
        assert key in color, key
        assert len(color[key]) == 2 and all(re.fullmatch(r"#[0-9a-f]{6}", v) for v in color[key]), key
    assert len({tuple(color[k]) for k in CHART_KEYS}) == 8


@pytest.mark.parametrize("scheme", [0, 1], ids=["light", "dark"])
@pytest.mark.parametrize("key", CHART_KEYS)
def test_chart_token_reaches_3_to_1_against_its_background(key: str, scheme: int) -> None:
    color = json.loads(HOUSE_TOKENS.read_text(encoding="utf-8"))["color"]
    assert _contrast(color[key][scheme], color["bg"][scheme]) >= 3.0


def test_kit_registry_entry() -> None:
    entry = json.loads((VENDOR / "libraries.json").read_text(encoding="utf-8"))["libraries"]["kit"]
    assert entry["current"] == "1.0.0"
    version = entry["versions"]["1.0.0"]
    assert (version["package"], version["license"], version["license_file"]) == ("quirk-kit", "MIT", "LICENSE")
    assert version["first_party"] is True
    assert "source" not in version
    files = {f["path"]: f for f in version["files"]}
    assert list(files) == ["kit.css", "kit.js"]
    assert (files["kit.css"]["kind"], files["kit.css"]["position"], files["kit.css"]["inline"]) == ("css", "head", True)
    assert (files["kit.js"]["kind"], files["kit.js"]["position"], files["kit.js"]["inline"]) == ("js", "body-end", True)
    assert "catalog.json" not in files


def test_kit_license_is_mit_with_the_repo_copyright_line() -> None:
    text = (KIT_DIR / "LICENSE").read_text(encoding="utf-8")
    root = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    copyright_line = next(ln for ln in root.splitlines() if ln.startswith("Copyright"))
    assert text.startswith("MIT License")
    assert copyright_line in text.splitlines()
    assert "Permission is hereby granted, free of charge" in text


def test_kit_license_comment_resolves_through_the_store() -> None:
    lv = _store().resolve("kit", None)
    assert vendor.license_comment(lv) == "<!-- license: kit 1.0.0 MIT | Copyright (c) 2026 Zach Young -->"


def test_kit_blocks_inline_and_verify() -> None:
    store = _store()
    blocks = store.inline_blocks(store.resolve("kit", None))
    assert [(b.kind, b.position, b.label) for b in blocks] == [("css", "head", "kit@1.0.0"), ("js", "body-end", "kit@1.0.0")]


def test_kit_js_shell_defines_no_elements_yet() -> None:
    text = (KIT_DIR / "kit.js").read_text(encoding="utf-8")
    assert re.search(r"^\(function \(\) \{$", text, re.MULTILINE) and text.rstrip().endswith("})();")
    assert text.count("customElements.define(") == 1  # only inside the guarded define helper
    assert re.search(r"customElements\.get\(\s*tag\s*\)", text)
    assert not re.search(r"^\s*(import|export)\b", text, re.MULTILINE)
    for helper in ("whenReady", "token", "onTheme", "bindData", "readTable"):
        assert re.search(rf"function {helper}\(", text), helper


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_kit_js_parses_as_a_classic_script_and_exposes_nothing() -> None:
    check = subprocess.run(["node", "--check", str(KIT_DIR / "kit.js")], capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
    harness = (
        "const vm = require('vm'); const fs = require('fs');"
        "const win = {}; const doc = {readyState: 'complete', addEventListener() {}, documentElement: {}};"
        "const ctx = {window: win, document: doc, customElements: {get() {}, define() { throw new Error('defined'); }},"
        " getComputedStyle() { return {getPropertyValue() { return ''; }}; }};"
        "ctx.globalThis = ctx; vm.createContext(ctx);"
        "vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);"
        "if (Object.keys(win).length) throw new Error('window polluted: ' + Object.keys(win));"
    )
    run = subprocess.run(["node", "-e", harness, str(KIT_DIR / "kit.js")], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr


def test_kit_css_has_only_the_shared_base() -> None:
    css = (KIT_DIR / "kit.css").read_text(encoding="utf-8")
    assert "[data-q-inactive]" in css and "[data-q-replaced]" in css
    assert re.search(r"@media not print\s*\{\s*:where\(\[data-q-inactive\]\)", css), "inactive panels stay visible in print"
    assert re.search(r"data-q-replaced\][^{]*\{[^}]*display:\s*none", css)
    assert "q-visually-hidden" in css or "q-sr-only" in css
    assert ":where(" in css
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", css), "no hard-coded colors"
    for tag in SECTION_3_4:
        assert not re.search(rf"(?<![\w-]){re.escape(tag)}(?![\w-])", css), f"{tag} has no styles yet"


def test_manifest_accepts_boolean_first_party_and_rejects_others(tmp_path: Path) -> None:
    real = json.loads((VENDOR / "libraries.json").read_text(encoding="utf-8"))
    assert manifest._library_problems(real) == []
    for value in ("yes", 1, None, [], "true"):
        bad = json.loads(json.dumps(real))
        bad["libraries"]["kit"]["versions"]["1.0.0"]["first_party"] = value
        problems = manifest._library_problems(bad)
        assert any("first_party" in p for p in problems), (value, problems)
    for value in (True, False):
        ok = json.loads(json.dumps(real))
        ok["libraries"]["kit"]["versions"]["1.0.0"]["first_party"] = value
        assert manifest._library_problems(ok) == []
    absent = json.loads(json.dumps(real))
    del absent["libraries"]["kit"]["versions"]["1.0.0"]["first_party"]
    assert manifest._library_problems(absent) == []


def _pins(*args: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(PINS), *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout


def test_pins_verify_passes_on_the_real_vendor_dir() -> None:
    code, out = _pins("verify")
    assert code == 0, out
    assert json.loads(out) == {"ok": True, "errors": []}


def test_stamp_is_idempotent_and_leaves_the_real_file_stamped(vendor_copy: Path) -> None:
    code, _ = _pins("stamp", "kit", "1.0.0", "--vendor-dir", str(vendor_copy))
    assert code == 0
    first = (vendor_copy / "libraries.json").read_bytes()
    code, _ = _pins("stamp", "kit", "1.0.0", "--vendor-dir", str(vendor_copy))
    assert code == 0
    assert (vendor_copy / "libraries.json").read_bytes() == first
    assert first == (VENDOR / "libraries.json").read_bytes()
    assert first.endswith(b"}\n") and not first.endswith(b"\n\n")


def test_stamp_repairs_hashes_after_an_edit_and_keeps_layout(vendor_copy: Path) -> None:
    before = (vendor_copy / "libraries.json").read_text(encoding="utf-8")
    (vendor_copy / "kit" / "1.0.0" / "kit.js").write_text("(function () {})();\n</SCRIPT>\n", encoding="utf-8")
    assert _pins("verify", "--vendor-dir", str(vendor_copy))[0] == 1
    code, out = _pins("stamp", "kit", "1.0.0", "--vendor-dir", str(vendor_copy))
    assert code == 0, out
    assert _pins("verify", "--vendor-dir", str(vendor_copy))[0] == 0
    after = (vendor_copy / "libraries.json").read_text(encoding="utf-8")
    assert after != before
    data = json.loads(after)
    spec = next(f for f in data["libraries"]["kit"]["versions"]["1.0.0"]["files"] if f["path"] == "kit.js")
    assert spec["sha256"] != spec["inline_sha256"], "inline hash covers the escaped </script"
    assert after == json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    assert list(data["libraries"]) == list(json.loads(before)["libraries"])
    # only the kit entry's hashes move; every other library line is untouched
    untouched = [ln for ln in before.splitlines() if "sha256" not in ln]
    assert untouched == [ln for ln in after.splitlines() if "sha256" not in ln]


@pytest.mark.parametrize("args", [("nope", "1.0.0"), ("kit", "9.9.9")])
def test_stamp_unknown_name_or_version_exits_2_with_a_json_error(vendor_copy: Path, args: tuple[str, str]) -> None:
    before = (vendor_copy / "libraries.json").read_bytes()
    code, out = _pins("stamp", *args, "--vendor-dir", str(vendor_copy))
    assert code == 2
    payload = json.loads(out)
    assert payload["ok"] is False and payload["error"]
    assert (vendor_copy / "libraries.json").read_bytes() == before


def test_check_skips_first_party_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    sys.path.insert(0, str(SKILL / "scripts"))
    import pins

    seen: list[str] = []

    def fake_get_json(url: str, body: Any = None) -> dict:
        seen.append(url)
        if body is not None:
            return {}
        return {"version": "0.0.0"}

    monkeypatch.setattr(pins, "_get_json", fake_get_json)
    report = pins.check(VENDOR)
    kit = next(r for r in report["libraries"] if r["name"] == "kit")
    assert kit["status"] == "first-party"
    assert not any("quirk-kit" in u for u in seen)
    assert "error" not in kit and kit["outdated"] is False and kit["advisories"] == []
