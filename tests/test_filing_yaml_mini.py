from __future__ import annotations

import importlib.util
import sys

import pytest

from .conftest import load_filing_module


@pytest.fixture(scope="module")
def yaml_mini():
    return load_filing_module("_yaml_mini")


def _pyyaml_available() -> bool:
    return importlib.util.find_spec("yaml") is not None


# ---- _yaml_mini.parse() -- the bounded subset, called directly ---------
#
# These call `.parse()`, never `parse_yaml()`: going through the tier-resolving entry
# point would silently exercise PyYAML on this machine (it has PyYAML 6.0 installed),
# leaving the fallback tier untested exactly where it is the only tier.


def test_nested_mapping(yaml_mini) -> None:
    text = "name: Bug Report\ntarget:\n  kind: github\n  repo: acme/reports\n"
    assert yaml_mini.parse(text, "nested.yml") == {
        "name": "Bug Report",
        "target": {"kind": "github", "repo": "acme/reports"},
    }


def test_block_sequence_of_scalars(yaml_mini) -> None:
    text = "labels:\n  - bug\n  - needs-triage\n"
    assert yaml_mini.parse(text, "seq.yml") == {"labels": ["bug", "needs-triage"]}


def test_block_sequence_of_mapping_items(yaml_mini) -> None:
    text = (
        "body:\n"
        "  - type: input\n"
        "    id: title\n"
        "    validations:\n"
        "      required: true\n"
        "  - type: textarea\n"
        "    id: description\n"
    )
    assert yaml_mini.parse(text, "seq2.yml") == {
        "body": [
            {"type": "input", "id": "title", "validations": {"required": True}},
            {"type": "textarea", "id": "description"},
        ]
    }


def test_block_scalar_literal(yaml_mini) -> None:
    text = "steps:\n  value: |\n    1. Do the thing\n    2. See the crash\n"
    assert yaml_mini.parse(text, "block.yml") == {
        "steps": {"value": "1. Do the thing\n2. See the crash\n"}
    }


def test_block_scalar_folded(yaml_mini) -> None:
    text = "description: >\n  line one\n  line two\n\n  line three\n"
    assert yaml_mini.parse(text, "folded.yml") == {
        "description": "line one line two\nline three\n"
    }


def test_single_quoted_scalar_with_escaped_quote(yaml_mini) -> None:
    text = "title: 'It''s broken'\n"
    assert yaml_mini.parse(text, "single.yml") == {"title": "It's broken"}


def test_double_quoted_scalar_with_escapes(yaml_mini) -> None:
    text = 'detail: "needs \\"quotes\\" and a\\ttab"\n'
    assert yaml_mini.parse(text, "double.yml") == {"detail": 'needs "quotes" and a\ttab'}


def test_booleans_and_null(yaml_mini) -> None:
    text = "a: true\nb: false\nc: null\nd:\n"
    assert yaml_mini.parse(text, "bools.yml") == {
        "a": True,
        "b": False,
        "c": None,
        "d": None,
    }


def test_comments_are_stripped(yaml_mini) -> None:
    text = "key: value # trailing comment\n# full line comment\nother: 1\n"
    assert yaml_mini.parse(text, "comments.yml") == {"key": "value", "other": "1"}


def test_hash_inside_quotes_is_not_a_comment(yaml_mini) -> None:
    text = 'key: "value # not a comment"\n'
    assert yaml_mini.parse(text, "hash.yml") == {"key": "value # not a comment"}


def test_empty_document_is_none(yaml_mini) -> None:
    assert yaml_mini.parse("", "empty.yml") is None
    assert yaml_mini.parse("\n\n# just a comment\n", "empty2.yml") is None


# ---- unsupported constructs -- one fixture per construct ----------------


def test_flow_mapping_rejected(yaml_mini) -> None:
    text = "key: {a: 1}\n"
    with pytest.raises(yaml_mini.TemplateParseError) as exc_info:
        yaml_mini.parse(text, "flow-map.yml")
    assert exc_info.value.path == "flow-map.yml"
    assert exc_info.value.line == 1


def test_flow_sequence_rejected(yaml_mini) -> None:
    text = "labels: [bug, urgent]\n"
    with pytest.raises(yaml_mini.TemplateParseError) as exc_info:
        yaml_mini.parse(text, "flow-seq.yml")
    assert exc_info.value.path == "flow-seq.yml"
    assert exc_info.value.line == 1


def test_anchor_rejected(yaml_mini) -> None:
    text = "key: &anchor value\n"
    with pytest.raises(yaml_mini.TemplateParseError) as exc_info:
        yaml_mini.parse(text, "anchor.yml")
    assert exc_info.value.line == 1


def test_alias_rejected(yaml_mini) -> None:
    text = "base: &b value\nkey: *b\n"
    with pytest.raises(yaml_mini.TemplateParseError) as exc_info:
        yaml_mini.parse(text, "alias.yml")
    assert exc_info.value.line == 1


def test_tag_rejected(yaml_mini) -> None:
    text = "key: !!str value\n"
    with pytest.raises(yaml_mini.TemplateParseError) as exc_info:
        yaml_mini.parse(text, "tag.yml")
    assert exc_info.value.line == 1


def test_multi_document_separator_rejected(yaml_mini) -> None:
    text = "---\nkey: value\n"
    with pytest.raises(yaml_mini.TemplateParseError) as exc_info:
        yaml_mini.parse(text, "multidoc.yml")
    assert exc_info.value.line == 1


def test_merge_key_rejected(yaml_mini) -> None:
    text = "base:\n  a: 1\nkey:\n  <<: base\n  b: 2\n"
    with pytest.raises(yaml_mini.TemplateParseError) as exc_info:
        yaml_mini.parse(text, "merge.yml")
    assert exc_info.value.line == 4


# ---- tier selection -------------------------------------------------------


def test_yaml_tier_matches_pyyaml_availability(yaml_mini) -> None:
    if _pyyaml_available():
        assert yaml_mini.YAML_TIER == "pyyaml"
    else:
        assert yaml_mini.YAML_TIER == "mini"


def test_yaml_tier_falls_back_to_mini_when_pyyaml_unimportable(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "yaml", None)
    forced = load_filing_module("_yaml_mini")
    assert forced.YAML_TIER == "mini"
    assert forced.parse_yaml("key: value\n", "forced.yml") == {"key": "value"}


def test_parse_yaml_raises_template_parse_error_on_forced_mini_tier(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "yaml", None)
    forced = load_filing_module("_yaml_mini")
    with pytest.raises(forced.TemplateParseError):
        forced.parse_yaml("key: [1, 2]\n", "forced-bad.yml")


# ---- parity between tiers on the shared subset ---------------------------

PARITY_FIXTURES = [
    "name: Bug Report\nlabels:\n  - bug\n  - needs-triage\n",
    (
        "body:\n"
        "  - type: input\n"
        "    id: title\n"
        "    attributes:\n"
        "      label: Title\n"
        "    validations:\n"
        "      required: true\n"
    ),
    "description: |\n  line one\n  line two\n",
    "description: >\n  line one\n  line two\n\n  line three\n",
    "title: 'It''s broken'\n",
    'detail: "needs \\"quotes\\""\n',
]


@pytest.mark.skipif(not _pyyaml_available(), reason="PyYAML not installed; nothing to compare against")
@pytest.mark.parametrize("text", PARITY_FIXTURES)
def test_mini_matches_pyyaml_on_shared_subset(yaml_mini, text) -> None:
    import yaml

    assert yaml_mini.parse(text, "parity.yml") == yaml.safe_load(text)
