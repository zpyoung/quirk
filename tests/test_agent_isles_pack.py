from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACK_DIR = REPO_ROOT / "packs" / "quirk"
EXAMPLES_DIR = REPO_ROOT / "examples" / "agent-isles"
DOC_PATH = REPO_ROOT / "docs" / "agent-isles-artifacts.md"

EXPECTED_COMPONENTS = {
    "quirk-artifact-summary",
    "quirk-tdd-cycle",
    "quirk-plan-review",
    "quirk-review-finding",
}
UNSAFE_ATTRS = {"style", "srcdoc"}


def test_pack_manifest_shape_and_safe_attributes() -> None:
    manifest = json.loads((PACK_DIR / "agent-isles.pack.json").read_text())
    assert manifest["name"] == "quirk"
    assert manifest["version"].startswith("0.")
    assert manifest["module"] == "./quirk-components.js"
    assert manifest["styles"] == ["./quirk-components.css"]

    components = {component["tag"]: component for component in manifest["components"]}
    assert set(components) == EXPECTED_COMPONENTS
    for tag, component in components.items():
        assert "-" in tag
        assert not tag.startswith("agent-")
        attrs = set(component["sanitizedModeAttributes"])
        assert attrs
        assert not (attrs & UNSAFE_ATTRS)
        assert not any(attr.lower().startswith("on") for attr in attrs)


def test_pack_assets_exist_and_are_local_boring_code() -> None:
    module = (PACK_DIR / "quirk-components.js").read_text()
    styles = (PACK_DIR / "quirk-components.css").read_text()
    assert "customElements.define" in module
    for tag in EXPECTED_COMPONENTS:
        class_name = "".join(part.title() for part in tag.split("-"))
        assert f'customElements.define("{tag}"' in module
        assert class_name in module
    for forbidden in ("fetch(", "XMLHttpRequest", "localStorage", "document.body", "document.write"):
        assert forbidden not in module
    assert "quirk-card" in styles


def test_agent_isles_examples_are_plain_markdown_and_reference_pack_tags() -> None:
    expected_files = {
        "typed-artifacts-summary.md": ["quirk-artifact-summary", "BUGS", "DEFERRED", "TEST_BACKLOG", "proposals", "ADR"],
        "tdd-cycle.md": ["quirk-tdd-cycle", "RED", "GREEN", "REFACTOR", "Verification"],
        "plan-review.md": ["quirk-plan-review", "quirk-review-finding", "Plan readiness", "Review findings"],
        "integrated-workflow.md": ["bin/agent_isles.py", "packs/quirk", ".quirk/isles"],
    }
    for name, needles in expected_files.items():
        body = (EXAMPLES_DIR / name).read_text()
        assert body.startswith("# ")
        assert "Plain Markdown fallback" in body
        assert "<agent-" in body
        assert "</" in body
        assert not re.search(r"<quirk-[^>]+/>|<agent-[^>]+/>", body)
        for needle in needles:
            assert needle in body


def test_docs_define_canonical_markdown_and_disposable_html_contract() -> None:
    body = DOC_PATH.read_text()
    for needle in [
        "Markdown source is canonical",
        "generated HTML is disposable",
        "Any built-in Agent Isles island may be used",
        "Quirk-specific component-pack tags",
        "trusted local code",
        "sanitized mode",
        "no self-closing custom elements",
        "bin/agent_isles.py",
        "agent-isles@next",
    ]:
        assert needle in body


def test_generated_isles_output_is_ignored() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text()
    assert ".quirk/isles/" in gitignore
