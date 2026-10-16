import html
import re

import pytest

import highlight as h

STRIP = re.compile(r"</?span[^>]*>")

SOURCES = [
    ("python", 'def f(x="a<b>"):\n    # note & comment\n    return None if x else 1.5\n'),
    ("bash", 'git log --oneline | grep "x&y"  # a <comment>\nexport N=3\n'),
    ("json", '{"a": "<b>", "n": -1.5e3, "ok": true, "z": null}'),
    ("diff", '@@ -1,2 +1,3 @@\n-old & gone\n+new <line>\n unchanged\n'),
    ("sql", "SELECT a FROM t WHERE b = 'x<y>' -- note\n"),
    ("yaml", 'key: "a<b>"\n# comment\nn: 3\n'),
]


def test_stripping_spans_restores_the_escaped_source():
    """The invariant everything else rests on: highlighting only ever wraps.

    If this holds, the highlighter can neither inject markup nor lose a character,
    which is the whole security and correctness surface of emitting raw HTML here.
    """
    for language, source in SOURCES:
        out = h.highlight(source, language)
        assert STRIP.sub("", out) == html.escape(source, quote=True), language


def test_unknown_and_missing_languages_are_left_alone():
    source = "whatever <b>&</b> this is"
    for language in (None, "", "no-such-language", "  ", "text"):
        assert h.highlight(source, language) == html.escape(source, quote=True)
        assert h.supported(language) is None


def test_aliases_resolve_to_one_canonical_name():
    assert h.supported("PY") == h.supported("python") == "python"
    assert h.supported("sh") == h.supported("Bash") == h.supported("shell") == "bash"
    assert h.supported("patch") == h.supported("diff") == "diff"


def _disable_pygments(monkeypatch):
    monkeypatch.setattr(h, "_pygments_lexers", None)
    monkeypatch.setattr(h, "_LEXERS", {})


@pytest.fixture(params=["installed", "builtin"])
def each_backend(request, monkeypatch):
    if request.param == "installed":
        pytest.importorskip("pygments")
    else:
        _disable_pygments(monkeypatch)


def test_comments_and_strings_swallow_keywords(each_backend):
    # ordering bug guard: a keyword inside a comment or string must not be coloured
    out = h.highlight("# def class return\n", "python")
    assert out.count("<span") == 1 and 'tok--comment' in out
    out = h.highlight('x = "def class"\n', "python")
    assert 'tok--keyword' not in out


def test_python_tokens_are_classified(each_backend):
    out = h.highlight('def go(n=1):\n    return None  # done\n', "python")
    for kind in ("keyword", "function", "number", "constant", "comment"):
        assert 'tok--%s' % kind in out, kind


def test_diff_is_line_oriented():
    out = h.highlight("-gone\n+added\n@@ hunk @@\n context\n", "diff")
    assert 'tok--del' in out and 'tok--ins' in out and 'tok--meta' in out
    # a bare context line stays unwrapped
    assert STRIP.sub("", out).endswith(" context\n")


def test_json_property_keys_differ_from_string_values(each_backend):
    out = h.highlight('{"k": "v"}', "json")
    assert 'tok--property' in out and 'tok--string' in out


PYGMENTS_SOURCES = [
    ("tsx", "const a = <Foo bar={1}>x &amp; y</Foo>; // c\n"),
    ("typescript", "const n: Array<string> = `t${x}`;\n"),
    ("vue", '<template><div :a="b">{{ x }}</div></template>\n'),
    ("html", '<a href="x?a=1&b=2">it\'s</a>\n'),
    ("css", ".a:hover { color: #fff; }\n"),
    ("scss", "$a: 1px;\n.b { margin: $a; }\n"),
    ("go", "func f() error { return nil }\n"),
    ("toml", '[tool]\nname = "x"\n'),
    ("graphql", "query Q($id: ID!) { a }\n"),
    ("docker", "FROM node:20 AS b\nRUN echo hi\n"),
    ("make", "all: x\n\t$(CC) -o $@\n"),
    ("liquid", "{% if x %}{{ y }}{% endif %}\n"),
]


@pytest.fixture
def builtin(monkeypatch):
    """Run against the stdlib grammars, as on a machine without Pygments."""
    _disable_pygments(monkeypatch)


def test_builtin_backend_keeps_the_invariant_and_its_language_set(builtin):
    for language, source in SOURCES:
        out = h.highlight(source, language)
        assert STRIP.sub("", out) == html.escape(source, quote=True), language
    assert h.supported("tsx") is None and h.highlight("<a>", "tsx") == "&lt;a&gt;"
    assert h.language_for_path("a/b.py") == "python" and h.language_for_path("a/b.tsx") is None


def test_builtin_yaml_colours_every_key_not_only_the_first(builtin):
    out = h.highlight("a: 1\nb: 2\n  c: 3\n", "yaml")
    assert out.count("tok--property") == 3


@pytest.mark.parametrize("language", ["python", "yaml", "diff"])
def test_crlf_input_is_read_as_lf_on_both_backends(language, monkeypatch):
    source = "x = 1\r\ny = 2\r\n"
    expected = html.escape(source.replace("\r\n", "\n"), quote=True)
    assert STRIP.sub("", h.highlight(source, language)) == expected
    assert [STRIP.sub("", line) for line in h.highlight_lines(source.split("\n"), language)] == expected.split("\n")
    _disable_pygments(monkeypatch)
    assert STRIP.sub("", h.highlight(source, language)) == expected


def test_pygments_languages_keep_the_invariant():
    pytest.importorskip("pygments")
    for language, source in PYGMENTS_SOURCES:
        assert h.supported(language), language
        out = h.highlight(source, language)
        assert STRIP.sub("", out) == html.escape(source, quote=True), language
        assert "tok--" in out, language


@pytest.mark.parametrize("language,source", [("json", '\ufeff{"a": 1}'), ("python", "\ufeffx = 1\n")])
def test_leading_bom_survives_pygments_highlighting(language, source):
    pytest.importorskip("pygments")
    out = h.highlight(source, language)
    assert STRIP.sub("", out) == html.escape(source, quote=True)


@pytest.mark.parametrize("language", ["c", "python", "json"])
def test_every_leading_bom_survives_pygments_highlighting(language):
    pytest.importorskip("pygments")
    source = "\ufeff\ufeffx = 1;\n"
    assert STRIP.sub("", h.highlight(source, language)) == html.escape(source, quote=True)


def test_pygments_maps_markup_and_data_keys_onto_template_kinds():
    pytest.importorskip("pygments")
    tsx = h.highlight('<Foo bar="1" />', "tsx")
    assert "tok--tag" in tsx and "tok--attribute" in tsx
    # a data-format key is a property, not a markup tag
    assert "tok--tag" not in h.highlight("key: v\n", "yaml")
    assert "tok--property" in h.highlight("key: v\n", "yaml")


def test_language_for_path_uses_file_names():
    pytest.importorskip("pygments")
    cases = {"a/LineItemPrice.tsx": "tsx", "Dockerfile": "docker", "Makefile": "make",
             "schema.gql": "graphql", "pyproject.toml": "toml", "x.vue": "vue"}
    for path, language in cases.items():
        assert h.language_for_path(path) == language, path
    assert h.language_for_path("README") is None and h.language_for_path(None) is None


MULTILINE_LINES = {
    "python": ['"""open', 'still inside"""', "x = 1"],
    "typescript": ["/* open", "still inside */", "x = 1"],
}


@pytest.mark.parametrize("language", sorted(MULTILINE_LINES))
def test_highlight_lines_carries_a_token_across_line_breaks(language):
    if language == "typescript":
        pytest.importorskip("pygments")
    lines = MULTILINE_LINES[language]
    out = h.highlight_lines(lines, language)
    assert len(out) == 3
    assert all("tok--" in line for line in out)
    assert out[1].startswith('<span class="tok tok--') and "inside" in out[1]
    assert [STRIP.sub("", line) for line in out] == [html.escape(line, quote=True) for line in lines]


def test_highlight_lines_passes_through_empty_and_unknown_input():
    assert h.highlight_lines([], "python") == []
    assert h.highlight_lines(["<a>"], None) == ["&lt;a&gt;"]
