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


@pytest.mark.parametrize(
    "text, expected",
    [
        ("a: |\n  x\n  y\nb: z\n", "x\ny\n"),
        ("a: |-\n  x\n  y\nb: z\n", "x\ny"),
        ("a: |+\n  x\n\n\nb: z\n", "x\n\n\n"),
        ("a: >\n  x\n  y\nb: z\n", "x y\n"),
        ("a: >-\n  x\n  y\nb: z\n", "x y"),
        ("a: >+\n  x\n  y\n\nb: z\n", "x y\n\n"),
        ("a: |-\n\nb: z\n", ""),
        ("a: |+\n\nb: z\n", "\n"),
    ],
)
def test_block_scalar_chomping(yaml_mini, text, expected) -> None:
    assert yaml_mini.parse(text, "chomp.yml")["a"] == expected


def test_block_sequence_at_the_key_indent(yaml_mini) -> None:
    text = "skip_globs:\n- \"*.lock\"\n- dist/**\nseverity_floor: Must fix\n"
    assert yaml_mini.parse(text, "flush.yml") == {
        "skip_globs": ["*.lock", "dist/**"],
        "severity_floor": "Must fix",
    }


def test_block_sequence_at_the_key_indent_inside_a_list_item(yaml_mini) -> None:
    text = "items:\n- a:\n  - x\n  - y\n  b: two\n- c\n"
    assert yaml_mini.parse(text, "flush.yml") == {"items": [{"a": ["x", "y"], "b": "two"}, "c"]}


def test_apostrophe_inside_a_plain_scalar_does_not_open_a_quote(yaml_mini) -> None:
    text = "a: don't touch # note\nb: 1\n"
    assert yaml_mini.parse(text, "plain.yml") == {"a": "don't touch", "b": "1"}


@pytest.mark.parametrize(
    "text, expected",
    [
        ("desc: yes, 'cause # c\n", {"desc": "yes, 'cause"}),
        ("labels: ['a # b', c] # c\n", {"labels": ["a # b", "c"]}),
    ],
)
def test_comma_before_an_apostrophe_in_a_block_scalar_does_not_open_a_quote(
    yaml_mini, text, expected
) -> None:
    assert yaml_mini.parse(text, "plain.yml") == expected


@pytest.mark.parametrize("escape", [r"\U00110000", r"\UFFFFFFFF", r"\U7FFFFFFF"])
def test_out_of_range_unicode_escape_is_a_parse_error(yaml_mini, escape) -> None:
    with pytest.raises(yaml_mini.TemplateParseError) as exc_info:
        yaml_mini.parse('key: "a%s"\n' % escape, "escape.yml")
    assert exc_info.value.line == 1


def test_highest_valid_unicode_escape_still_parses(yaml_mini) -> None:
    assert yaml_mini.parse('key: "\\U0010FFFF"\n', "escape.yml") == {"key": "\U0010FFFF"}


@pytest.mark.parametrize(
    "text",
    [
        "a:\n\tb: 1\n",
        "body:\n  - type: textarea\n\tattributes:\n    label: x\n",
        "a:\n \tb: 1\n",
    ],
)
def test_tab_indentation_is_a_parse_error(yaml_mini, text) -> None:
    with pytest.raises(yaml_mini.TemplateParseError) as exc_info:
        yaml_mini.parse(text, "tabs.yml")
    assert "tab" in exc_info.value.message
    assert exc_info.value.path == "tabs.yml"


def test_tab_inside_a_block_scalar_body_is_content(yaml_mini) -> None:
    assert yaml_mini.parse("a: |\n  x\n  \ty\n", "tabs.yml") == {"a": "x\n\ty\n"}


@pytest.mark.parametrize(
    "text",
    [
        "a: >\n  x\n    y\n  z\n",
        "a: >\n  x\n\n    y\n  z\n",
        "a: >\n  x\n    y\n\n  z\n",
        "a: >\n  x\n  y\n\n  z\n",
    ],
)
@pytest.mark.skipif(not _pyyaml_available(), reason="PyYAML not installed")
def test_folded_scalar_matches_pyyaml_around_more_indented_lines(yaml_mini, text) -> None:
    import yaml

    assert yaml_mini.parse(text, "fold.yml") == yaml.safe_load(text)


def test_folded_scalar_keeps_the_break_around_a_more_indented_line(yaml_mini) -> None:
    assert yaml_mini.parse("a: >\n  x\n    y\n  z\n", "fold.yml") == {"a": "x\n  y\nz\n"}


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


# ---- scalar flow sequences (T11: the one flow form the mini tier admits) -----------


def test_flow_sequence_of_plain_scalars(yaml_mini) -> None:
    text = "labels: [bug, needs-triage]\n"
    assert yaml_mini.parse(text, "flow-plain.yml") == {"labels": ["bug", "needs-triage"]}


def test_flow_sequence_of_quoted_scalars(yaml_mini) -> None:
    text = 'labels: ["bug", "needs-triage"]\n'
    assert yaml_mini.parse(text, "flow-quoted.yml") == {"labels": ["bug", "needs-triage"]}


def test_flow_sequence_of_mixed_scalars(yaml_mini) -> None:
    text = "labels: [bug, \"needs-triage\", 'urgent']\n"
    assert yaml_mini.parse(text, "flow-mixed.yml") == {
        "labels": ["bug", "needs-triage", "urgent"]
    }


def test_flow_sequence_empty(yaml_mini) -> None:
    text = "labels: []\n"
    assert yaml_mini.parse(text, "flow-empty.yml") == {"labels": []}


def test_flow_sequence_trailing_comma(yaml_mini) -> None:
    text = "labels: [bug, needs-triage,]\n"
    assert yaml_mini.parse(text, "flow-trailing.yml") == {"labels": ["bug", "needs-triage"]}


def test_flow_sequence_extra_whitespace(yaml_mini) -> None:
    text = "labels: [  bug ,   needs-triage  ]\n"
    assert yaml_mini.parse(text, "flow-whitespace.yml") == {
        "labels": ["bug", "needs-triage"]
    }


def test_flow_sequence_as_root_document(yaml_mini) -> None:
    text = "[a, b, c]\n"
    assert yaml_mini.parse(text, "flow-root.yml") == ["a", "b", "c"]


def test_flow_sequence_as_sequence_item(yaml_mini) -> None:
    text = "- [a, b]\n- c\n"
    assert yaml_mini.parse(text, "flow-item.yml") == [["a", "b"], "c"]


def test_github_issue_form_with_flow_labels(yaml_mini) -> None:
    text = (
        "name: Bug Report\n"
        "description: File a bug\n"
        'labels: ["bug", "needs-triage"]\n'
        "body:\n"
        "  - type: input\n"
        "    id: current_behavior\n"
        "    attributes:\n"
        "      label: Current behavior\n"
        "    validations:\n"
        "      required: true\n"
        "  - type: textarea\n"
        "    id: steps_to_reproduce\n"
        "    attributes:\n"
        "      label: Steps to reproduce\n"
    )
    assert yaml_mini.parse(text, "issue-form.yml") == {
        "name": "Bug Report",
        "description": "File a bug",
        "labels": ["bug", "needs-triage"],
        "body": [
            {
                "type": "input",
                "id": "current_behavior",
                "attributes": {"label": "Current behavior"},
                "validations": {"required": True},
            },
            {
                "type": "textarea",
                "id": "steps_to_reproduce",
                "attributes": {"label": "Steps to reproduce"},
            },
        ],
    }


# ---- unsupported constructs -- one fixture per construct ----------------


def test_flow_mapping_rejected(yaml_mini) -> None:
    text = "key: {a: 1}\n"
    with pytest.raises(yaml_mini.TemplateParseError) as exc_info:
        yaml_mini.parse(text, "flow-map.yml")
    assert exc_info.value.path == "flow-map.yml"
    assert exc_info.value.line == 1


def test_flow_mapping_nested_in_sequence_rejected(yaml_mini) -> None:
    text = "labels: [{k: v}]\n"
    with pytest.raises(yaml_mini.TemplateParseError) as exc_info:
        yaml_mini.parse(text, "flow-seq-nested-map.yml")
    assert exc_info.value.path == "flow-seq-nested-map.yml"
    assert exc_info.value.line == 1


def test_flow_sequence_nested_in_sequence_rejected(yaml_mini) -> None:
    text = "labels: [[a], b]\n"
    with pytest.raises(yaml_mini.TemplateParseError) as exc_info:
        yaml_mini.parse(text, "flow-seq-nested-seq.yml")
    assert exc_info.value.path == "flow-seq-nested-seq.yml"
    assert exc_info.value.line == 1


def test_anchor_rejected(yaml_mini) -> None:
    text = "key: &anchor value\n"
    with pytest.raises(yaml_mini.TemplateParseError) as exc_info:
        yaml_mini.parse(text, "anchor.yml")
    assert exc_info.value.line == 1


def test_alias_rejected(yaml_mini) -> None:
    text = "key: *b\n"
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
        forced.parse_yaml("key: {a: 1}\n", "forced-bad.yml")


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
    "labels: [bug, needs-triage]\n",
    'labels: ["bug", "needs-triage"]\n',
    "labels: []\n",
    "labels: [bug, needs-triage,]\n",
    "a: |-\n  x\n  y\nb: z\n",
    "a: >+\n  x\n  y\n\nb: z\n",
    "skip_globs:\n- \"*.lock\"\n- dist/**\nseverity_floor: Must fix\n",
    "a: don't touch # note\nb: it's 'q' # c\n",
    "a: [don't, 'x, y', \"q\"]\n",
    "k: don't ' #c\n",
    'k: a "b #c\n',
    "k: a ' b #c\n",
    "k: 'q #c' # real\n",
    "- 'x # y' # real\n",
    "desc: yes, 'cause # c\n",
    "labels: ['a, b', c] # c\n",
]


@pytest.mark.skipif(not _pyyaml_available(), reason="PyYAML not installed; nothing to compare against")
@pytest.mark.parametrize("text", PARITY_FIXTURES)
def test_mini_matches_pyyaml_on_shared_subset(yaml_mini, text) -> None:
    import yaml

    assert yaml_mini.parse(text, "parity.yml") == yaml.safe_load(text)


# ---- wave-3 checkpoint regressions ---------------------------------------


def test_deeply_nested_mapping_raises_template_parse_error_not_recursion_error(yaml_mini) -> None:
    # discovery parses every candidate in a repo; one pathological file must fail as this
    # module's own per-file error, not as a RecursionError crashing the whole sweep.
    text = "".join(f"{' ' * (2 * i)}k{i}:\n" for i in range(400)) + " " * 800 + "leaf: 1\n"
    with pytest.raises(yaml_mini.TemplateParseError) as excinfo:
        yaml_mini.parse(text, "deep.yml")
    assert "nesting" in str(excinfo.value)
    assert excinfo.value.path == "deep.yml"


def test_deeply_nested_sequence_raises_template_parse_error(yaml_mini) -> None:
    text = "".join(f"{' ' * (2 * i)}- a{i}:\n" for i in range(400)) + " " * 800 + "leaf: 1\n"
    with pytest.raises(yaml_mini.TemplateParseError):
        yaml_mini.parse(text, "deep.yml")


def test_nesting_within_the_bound_still_parses(yaml_mini) -> None:
    depth = 10
    text = "".join(f"{' ' * (2 * i)}k{i}:\n" for i in range(depth)) + f"{' ' * (2 * depth)}leaf: 1\n"
    node = yaml_mini.parse(text, "shallow.yml")
    for i in range(depth):
        node = node[f"k{i}"]
    assert node == {"leaf": "1"}  # plain scalars stay strings in this tier


@pytest.mark.parametrize(
    "text,expected",
    [
        ('id: "\\u005f"', "_"),
        ('id: "\\x41"', "A"),
        ('id: "\\U0001F600"', "\U0001f600"),
        ('id: "a\\/b"', "a/b"),
        ('id: "a\\ab"', "a\ab"),
        ('id: "a\\eb"', "a\x1bb"),
    ],
)
def test_double_quoted_escapes_decode_rather_than_dropping_the_backslash(
    yaml_mini, text, expected,
) -> None:
    # silently stripping the backslash makes this tier disagree with PyYAML about the
    # *content* of a template id or field name -- the one thing the tiers must never do.
    assert yaml_mini.parse(text, "escapes.yml") == {"id": expected}


@pytest.mark.parametrize("text", ['id: "\\q"', 'id: "\\u00"', 'id: "\\xZZ"'])
def test_unknown_or_truncated_double_quoted_escape_is_rejected(yaml_mini, text) -> None:
    with pytest.raises(yaml_mini.TemplateParseError):
        yaml_mini.parse(text, "escapes.yml")


@pytest.mark.skipif(not _pyyaml_available(), reason="PyYAML not installed; nothing to compare against")
@pytest.mark.parametrize(
    "text",
    ['id: "\\u005f"', 'id: "\\x41"', 'id: "\\U0001F600"', 'id: "a\\/b"', 'id: "a\\eb"'],
)
def test_escape_decoding_matches_pyyaml(yaml_mini, text) -> None:
    import yaml

    assert yaml_mini.parse(text, "escapes.yml") == yaml.safe_load(text)


# ---- production-review round 3 -------------------------------------------


QUOTED_KEY_FIXTURES = [
    '"name": Bug report\n',
    "'name': Bug report\n",
    '"name": Bug report\nlabels: [bug]\nbody:\n  - type: textarea\n    "id": what\n',
    'body:\n  - "type": textarea\n    id: what\n',
]


@pytest.mark.parametrize("text", QUOTED_KEY_FIXTURES)
def test_quoted_mapping_keys_parse_to_the_same_key_as_unquoted(yaml_mini, text) -> None:
    # `"name": x` and `name: x` are one mapping. A tier that keeps the quotes produces a
    # document whose keys nothing matches, so a valid template resolves to no fields at all --
    # on exactly the machines this tier exists to serve.
    parsed = yaml_mini.parse(text, "quoted.yml")

    def keys(node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from keys(value)
        elif isinstance(node, list):
            for item in node:
                yield from keys(item)

    assert all("'" not in key and '"' not in key for key in keys(parsed))


def test_quoted_key_template_survives_discovery_on_the_mini_tier(yaml_mini) -> None:
    text = (
        '"name": Bug report\n'
        '"labels": [bug]\n'
        "body:\n"
        "  - type: textarea\n"
        '    "id": what_happened\n'
        "    attributes:\n"
        "      label: What happened?\n"
    )
    parsed = yaml_mini.parse(text, "quoted.yml")
    assert parsed["name"] == "Bug report"
    assert parsed["labels"] == ["bug"]
    assert parsed["body"][0]["id"] == "what_happened"


@pytest.mark.skipif(not _pyyaml_available(), reason="PyYAML not installed; nothing to compare against")
@pytest.mark.parametrize("text", QUOTED_KEY_FIXTURES)
def test_quoted_key_parsing_matches_pyyaml(yaml_mini, text) -> None:
    import yaml

    assert yaml_mini.parse(text, "quoted.yml") == yaml.safe_load(text)


@pytest.mark.parametrize("text", ["- - x\n", "- - - z\n", "k:\n  - - x\n", "- - k: v\n"])
def test_nested_block_sequence_is_rejected_not_kept_as_text(yaml_mini, text) -> None:
    with pytest.raises(yaml_mini.TemplateParseError, match="nested sequences"):
        yaml_mini.parse(text, "nested.yml")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("k: don't ' #c\n", {"k": "don't '"}),
        ('k: a "b #c\n', {"k": 'a "b'}),
        ("k: a ' b #c\n", {"k": "a ' b"}),
        ("k: 'q #c' # real\n", {"k": "q #c"}),
    ],
)
def test_quote_inside_a_plain_scalar_does_not_hide_a_trailing_comment(yaml_mini, text, expected) -> None:
    assert yaml_mini.parse(text, "plain.yml") == expected
