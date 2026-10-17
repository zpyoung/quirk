import re

import pytest

import md_render as m


def test_empty():
    assert m.render_markdown(None) == ""
    assert m.render_markdown("") == ""
    assert m.render_inline(None) == ""


def test_escaping_boundary():
    rendered = m.render_markdown("<script>alert(1)</script>")
    assert "&lt;script&gt;" in rendered and "<script" not in rendered
    rendered = m.render_markdown("- <img src=x onerror=boom>\n\n| H |\n| --- |\n| <img onerror=x> |")
    assert rendered.count("&lt;img") == 2
    assert "<img" not in rendered


def test_allowed_links():
    for dest in ("https://x", "HTTPS://x", "mailto:a@b", "./rel/path", "#anchor", ""):
        rendered = m.render_inline("[x](%s)" % dest)
        assert '<a href="' in rendered, (dest, rendered)
        assert 'rel="noopener noreferrer"' in rendered
    rendered = m.render_inline('[x](https://e/?a=1&b=")')
    assert 'href="https://e/?a=1&amp;b=&quot;"' in rendered


def test_rejected_links():
    destinations = ("javascript:alert(1)", "\x01javascript:void0", "//evil.com",
                    "data:text/html,x", "https://x/\npath", "https://x/\u2028path",
                    "https://x\n", "\u2028https://x", "https:\\evil.com", "\\\\evil.com")
    for dest in destinations:
        rendered = m.render_inline("[x](%s)" % dest)
        assert "<a " not in rendered, (repr(dest), rendered)
        assert "[x]" in rendered


def test_inline_nesting():
    assert m.render_inline("***x***") == "<strong><em>x</em></strong>"
    assert m.render_inline("**[see `x`](https://e)**") == (
        '<strong><a href="https://e" rel="noopener noreferrer">see <code>x</code></a></strong>')
    rendered = m.render_inline("[x](https://e/`p`)")
    assert rendered == '<a href="https://e/`p`" rel="noopener noreferrer">x</a>'
    assert "<code>" not in rendered
    assert m.render_inline("[**urgent**](https://e)") == (
        '<a href="https://e" rel="noopener noreferrer"><strong>urgent</strong></a>')


def test_code_protection():
    assert m.render_inline("`**x**`") == "<code>**x**</code>"
    assert m.render_inline('`"`') == "<code>&quot;</code>"
    assert m.render_inline("`[x](https://e)`") == "<code>[x](https://e)</code>"
    assert m.render_inline("``a ` b``") == "<code>a ` b</code>"
    block = m.render_markdown("```python\n<script>\n**bold**\n```")
    # highlighting only wraps: strip the spans and the fence is still inert markdown
    # and still escaped, which is what this test is actually protecting
    assert re.sub(r"</?span[^>]*>", "", block) == (
        '<pre class="snippet"><code class="lang-python">&lt;script&gt;\n**bold**</code></pre>')
    assert "<script>" not in block and "<strong>" not in block
    # an untagged fence is never guessed at
    plain = m.render_markdown("```\ndef f():\n```")
    assert plain == '<pre class="snippet"><code>def f():</code></pre>'
    unclosed = m.render_markdown("```\nfirst\nsecond")
    assert "first\nsecond" in unclosed and unclosed.endswith("</code></pre>")


def test_backslash_escapes():
    assert m.render_inline(r"\*not bold\*") == "*not bold*"
    assert m.render_inline(r"\`not code\`") == "`not code`"
    assert m.render_inline(r"\[not a link]") == "[not a link]"
    assert m.render_inline(r"\\") == "\\"


def test_unbalanced_markers():
    for value in ("**x", "*x", "[x](", "`unterminated"):
        assert m.render_inline(value) == value


@pytest.mark.parametrize("value", [
    "a * b * c", "n * 2 + m * 3", "src/*.py and tests/*.py", "a ** b ** c", "x *", "x **",
])
def test_spaced_asterisks_stay_literal(value):
    assert m.render_inline(value) == value


def test_flanking_asterisks_still_emphasise():
    assert m.render_inline("*a b* and **c d**") == "<em>a b</em> and <strong>c d</strong>"


def test_closing_fence_cannot_carry_an_info_string():
    rendered = m.render_markdown("```sql\nselect 1\n```js\nstill code\n```\n\nafter")
    assert rendered.count("<pre") == 1
    assert "still code" in rendered and "<p>after</p>" in rendered


def test_paragraphs_and_lists():
    rendered = m.render_markdown("first\nsecond\n\n- one\n  continued\n- two\n\n1. alpha\n2. beta")
    assert "<p>first second</p>" in rendered
    assert "<ul><li>one continued</li><li>two</li></ul>" in rendered
    assert "<ol><li>alpha</li><li>beta</li></ol>" in rendered
    nested = m.render_markdown("- parent\n  - child")
    assert nested == "<ul><li>parent - child</li></ul>"


def test_blockquotes():
    rendered = m.render_markdown("> quoted\n> ```\n> <x>\n> ```")
    assert rendered.startswith("<blockquote>")
    assert '<pre class="snippet"><code>&lt;x&gt;</code></pre>' in rendered


def test_block_boundary_flushing():
    cases = (
        ("text\n```\ncode\n```", "<p>text</p>\n<pre"),
        ("text\n- item", "<p>text</p>\n<ul>"),
        ("text\n> quote", "<p>text</p>\n<blockquote>"),
        ("text\n| H |\n| --- |", "<p>text</p>\n<div class=\"table-wrap\">"),
    )
    for source, boundary in cases:
        assert boundary in m.render_markdown(source)


def test_tables():
    source = "| Left | Center | Right |\n| --- | :---: | ---: |\n| a\\|b | c | d |\n| short |\n| 1 | 2 | 3 | extra |"
    rendered = m.render_markdown(source)
    assert rendered.startswith('<div class="table-wrap"><table>')
    assert 'style="text-align:center"' in rendered
    assert 'style="text-align:right"' in rendered
    assert ">a|b</td>" in rendered
    assert rendered.count("<td") == 9
    assert "extra" not in rendered


def test_one_column_table():
    rendered = m.render_markdown("| H |\n| --- |")
    assert "<table>" in rendered and "<th>H</th>" in rendered


def test_non_table_pipe_and_list_precedence():
    rendered = m.render_markdown("a | b\nplain")
    assert "<table>" not in rendered and "a | b plain" in rendered
    rendered = m.render_markdown("- a | b\n  | --- |")
    assert rendered.startswith("<ul>") and "<table>" not in rendered


def test_unsupported_constructs_literal():
    rendered = m.render_markdown("# h\n![i](u)\n---")
    assert "<h1" not in rendered and "<a " not in rendered and "<hr" not in rendered
    assert "# h ![i](u) ---" in rendered


def test_nul_is_not_a_sentinel():
    rendered = m.render_inline("*\x00*x*\x00*")
    assert "\x00" in rendered
    assert "<strong>" not in rendered


def test_pathological_depth_fails_safe():
    source = ">" * 2000 + " <script>"
    rendered = m.render_markdown(source)
    assert "<script>" not in rendered and "&lt;script&gt;" in rendered


def test_diff_fence_renders_side_by_side_with_line_numbers():
    rendered = m.render_markdown(
        "```diff\n--- a/app/rates.py\n+++ b/app/rates.py\n@@ -10,3 +10,4 @@\n"
        "     total = 0\n-    total += round(p)\n+    total += p\n+    log(total)\n"
        "     return total\n```")
    assert '<table class="sbs" aria-label="Current and suggested code for app/rates.py">' in rendered
    assert '<div class="sbs-path">app/rates.py</div>' in rendered
    assert "Current</th>" in rendered and "Suggested</th>" in rendered
    rows = re.findall(r"<tr>(.*?)</tr>", rendered.split("<tbody>")[1])
    numbers = [re.findall(r'<td class="sbs-ln">(\d*)</td>', row) for row in rows]
    assert numbers == [["10", "10"], ["11", "11"], ["", "12"], ["12", "13"]]
    assert 'class="sbs-code sbs-del"><del>' in rows[1] and 'class="sbs-code sbs-ins"><ins>' in rows[1]
    assert "sbs-empty" in rows[2]
    assert 'class="tok tok--' in rendered, "python path should select syntax colouring"
    assert "@@ -10,3 +10,4 @@" in rendered


def test_diff_fence_pairs_removed_runs_and_keeps_dash_content():
    rendered = m.render_markdown("```diff\n--- old sql comment\n-x\n+y\n```")
    rows = re.findall(r"<tr>(.*?)</tr>", rendered.split("<tbody>")[1])
    # a lone "---" line with no "+++" partner is a removed line, not a file header
    assert "sbs-path" not in rendered
    assert "<del>-- old sql comment</del>" in rows[0] and "<ins>y</ins>" in rows[0]
    assert "<del>x</del>" in rows[1] and "sbs-empty" in rows[1]
    assert re.findall(r'<td class="sbs-ln">(\d*)</td>', "".join(rows)) == ["", "", "", ""]


def test_diff_fence_hunk_lines_that_look_like_a_file_header_stay_rows():
    rendered = m.render_markdown(
        "```diff\n--- a/app/x.py\n+++ b/app/x.py\n@@ -1,3 +1,3 @@\n keep\n--- gone\n+++ added\n keep\n```")
    rows = re.findall(r"<tr>(.*?)</tr>", rendered.split("<tbody>")[1])
    assert '<div class="sbs-path">app/x.py</div>' in rendered
    assert len(rows) == 3
    assert "sbs-del" in rows[1] and "gone" in rows[1] and "sbs-ins" in rows[1] and "added" in rows[1]


def test_diff_fence_escapes_content_and_falls_back_without_changes():
    rendered = m.render_markdown("```diff\n-<script>x</script>\n+ok\n```")
    assert "<script>" not in rendered and "&lt;script&gt;" in rendered
    plain = m.render_markdown("```diff\n context only\n```")
    assert "sbs" not in plain and '<pre class="snippet"><code class="lang-diff">' in plain


def test_diff_fence_colours_each_side_as_one_source():
    pytest.importorskip("pygments")
    rendered = m.render_markdown(
        "```diff\n--- a/web/Price.tsx\n+++ b/web/Price.tsx\n@@ -1,3 +1,3 @@\n"
        " /* keeps the\n-   old note */\n+   new note */\n const a = <Text size=\"body2\" />;\n```")
    rows = re.findall(r"<tr>(.*?)</tr>", rendered.split("<tbody>")[1])
    # the comment opened on the context line still colours both sides of the next row
    assert rows[1].count("tok--comment") == 2
    assert "tok--tag" in rows[2] and "tok--attribute" in rows[2]



@pytest.mark.parametrize("separator", ["\x0c", "\x0b", "\x1c", "\x85", "\u2028", "\u2029"])
def test_fenced_code_keeps_unicode_line_separators_inside_one_line(separator):
    rendered = m.render_markdown("```\na%sb\nnext\n```" % separator)
    assert rendered == '<pre class="snippet"><code>a%sb\nnext</code></pre>' % separator


def test_unclosed_emphasis_openers_tokenize_in_polynomial_time():
    import time

    text = "*a " * 40 + "**b " * 40
    started = time.monotonic()
    rendered = m.render_inline(text)
    assert time.monotonic() - started < 2
    assert rendered.count("*") == 120 and "<em>" not in rendered


def test_memoized_tokenizer_still_pairs_nested_emphasis():
    assert m.render_inline("*a **b** c* and **d *e* f**") == (
        "<em>a <strong>b</strong> c</em> and <strong>d <em>e</em> f</strong>")
