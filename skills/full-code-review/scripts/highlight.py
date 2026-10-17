"""Server-side syntax highlighter for the fenced code blocks in a review report.

Server-side on purpose: the report is a single self-contained file that has to
render identically with JavaScript disabled and on paper, so colouring a snippet in
the browser would lose it in exactly the two modes the template promises to support.

Pygments does the lexing when it is importable, which covers every language a
review is likely to quote and lets a file path pick its own lexer. Without it, a
small built-in set (Python, Bash, JSON, YAML, SQL) still colours, so the report
never depends on a third-party install. Either way tokens map onto the template's
own ``tok--*`` classes rather than Pygments' styles, so one palette themes both.
An unknown or absent info string is returned unhighlighted rather than guessed at -
mislabelled colour is worse than none.

The contract every caller depends on: stripping the emitted ``<span>`` tags
reproduces ``html.escape(source, quote=True)`` exactly, once CRLF and CR line endings
are read as LF. Tokens are matched against the raw source and escaped individually,
never the reverse.
"""
import html
import os
import re

try:
    from pygments import lexers as _pygments_lexers
    from pygments import token as _pygments_token
    from pygments.util import ClassNotFound as _ClassNotFound
except ImportError:
    _pygments_lexers = None

__all__ = ["backend", "highlight", "highlight_lines", "language_for_path", "supported"]

INSTALL_HINT = "python3 -m pip install --user pygments"

# Ordered alternation: whatever can swallow another construct comes first, so a
# keyword inside a comment or a string stays inside it.
_PYTHON = r"""
    (?P<comment>\#[^\n]*)
  | (?P<string>[rbfu]{0,2}(?:'''.*?'''|\"\"\".*?\"\"\"|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"))
  | (?P<keyword>\b(?:and|as|assert|async|await|break|class|continue|def|del|elif|else|except|
        finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|
        while|with|yield)\b)
  | (?P<constant>\b(?:True|False|None|self|cls)\b)
  | (?P<function>\b[A-Za-z_]\w*(?=\s*\())
  | (?P<number>\b(?:0[xXbBoO][0-9a-fA-F_]+|\d[\d_]*\.?[\d_]*(?:[eE][+-]?\d+)?)\b)
  | (?P<operator>[+\-*/%=<>!&|^~@]+)
  | (?P<punctuation>[()\[\]{},:;.])
"""

_BASH = r"""
    (?P<comment>\#[^\n]*)
  | (?P<string>'(?:[^'])*'|\"(?:\\.|[^\"\\])*\")
  | (?P<keyword>\b(?:if|then|else|elif|fi|for|while|do|done|case|esac|function|in|return|
        export|local|source|set|shift|trap|exit)\b)
  | (?P<function>\b(?:echo|cd|ls|grep|sed|awk|cat|cp|mv|rm|mkdir|git|python3?|pip|curl|
        printf|test|read|find|xargs)\b)
  | (?P<variable>\$\{?\w+\}?)
  | (?P<number>\b\d+\b)
  | (?P<operator>[|&;<>]+|--?[A-Za-z][\w-]*)
  | (?P<punctuation>[()\[\]{}])
"""

_JSON = r"""
    (?P<property>\"(?:\\.|[^\"\\])*\"(?=\s*:))
  | (?P<string>\"(?:\\.|[^\"\\])*\")
  | (?P<constant>\b(?:true|false|null)\b)
  | (?P<number>-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)
  | (?P<punctuation>[{}\[\],:])
"""

_YAML = r"""
    (?P<comment>\#[^\n]*)
  | (?P<property>^[ \t]*[\w.-]+(?=\s*:))
  | (?P<string>'(?:[^'])*'|\"(?:\\.|[^\"\\])*\")
  | (?P<constant>\b(?:true|false|null|yes|no)\b)
  | (?P<number>\b\d+(?:\.\d+)?\b)
  | (?P<punctuation>[:\-\[\]{},])
"""

_SQL = r"""
    (?P<comment>--[^\n]*)
  | (?P<string>'(?:[^'])*')
  | (?P<keyword>(?i:\b(?:select|from|where|join|left|right|inner|outer|on|group|order|by|having|
        limit|offset|insert|into|values|update|set|delete|create|alter|drop|table|index|and|or|
        not|null|as|distinct|union|case|when|then|else|end)\b))
  | (?P<number>\b\d+(?:\.\d+)?\b)
  | (?P<operator>[=<>!+\-*/]+)
  | (?P<punctuation>[(),.;])
"""

_LANGUAGES = {
    "python": _PYTHON,
    "bash": _BASH,
    "json": _JSON,
    "yaml": _YAML,
    "sql": _SQL,
}

# Every spelling an author might use collapses to one canonical name, so the
# emitted lang- class does not depend on whether they wrote py or python.
_ALIASES = {
    "py": "python",
    "sh": "bash", "shell": "bash", "console": "bash",
    "yml": "yaml",
    "diff": "diff", "patch": "diff",
}

_EXTENSIONS = {".py": "python", ".sh": "bash", ".bash": "bash", ".json": "json",
               ".yml": "yaml", ".yaml": "yaml", ".sql": "sql"}
# spellings Pygments' filename patterns miss
_PYGMENTS_EXTENSIONS = {".gql": "graphql"}

_COMPILED = {}
_LEXERS = {}

# Diff is line-oriented, not token-oriented; a '-' in a removed line is not an operator.
_DIFF_PREFIXES = (
    ("@@", "meta"), ("+++", "meta"), ("---", "meta"),
    ("diff ", "meta"), ("index ", "meta"),
    ("+", "ins"), ("-", "del"),
)

# Most specific first: Keyword.Constant must win over Keyword, String over Literal.
_PYGMENTS_KINDS = () if _pygments_lexers is None else (
    (_pygments_token.Comment, "comment"),
    (_pygments_token.String, "string"),
    (_pygments_token.Number, "number"),
    (_pygments_token.Keyword.Constant, "constant"),
    (_pygments_token.Keyword.Type, "type"),
    (_pygments_token.Operator.Word, "keyword"),
    (_pygments_token.Keyword, "keyword"),
    (_pygments_token.Name.Tag, "tag"),
    (_pygments_token.Name.Attribute, "attribute"),
    (_pygments_token.Name.Function, "function"),
    (_pygments_token.Name.Decorator, "function"),
    (_pygments_token.Name.Builtin.Pseudo, "constant"),
    (_pygments_token.Name.Builtin, "function"),
    (_pygments_token.Name.Class, "type"),
    (_pygments_token.Name.Constant, "constant"),
    (_pygments_token.Name.Entity, "constant"),
    (_pygments_token.Name.Variable, "variable"),
    (_pygments_token.Name.Property, "property"),
    (_pygments_token.Name.Label, "property"),
    (_pygments_token.Operator, "operator"),
    (_pygments_token.Punctuation, "punctuation"),
    (_pygments_token.Generic.Inserted, "ins"),
    (_pygments_token.Generic.Deleted, "del"),
    (_pygments_token.Generic.Heading, "meta"),
    (_pygments_token.Generic.Subheading, "meta"),
)


# Pygments marks a key in data formats as a tag or attribute; here it reads as a property.
_DATA_LANGUAGES = {"json", "json5", "jsonld", "yaml", "toml", "ini"}


def _pygments_lexer(name):
    if name not in _LEXERS:
        try:
            lexer = _pygments_lexers.get_lexer_by_name(name, stripnl=False, ensurenl=False)
        except _ClassNotFound:
            lexer = None
        # the plain-text lexer colours nothing, so it is an unknown language, not a known one
        _LEXERS[name] = None if lexer is None or lexer.aliases[:1] == ["text"] else lexer
    return _LEXERS[name]


def backend():
    """Return ``"pygments"`` when Pygments does the lexing, else ``"builtin"``."""
    return "pygments" if _pygments_lexers is not None else "builtin"


def supported(language):
    """Return the canonical language name this module can colour, or None."""
    if not language or not language.strip():
        return None
    name = _ALIASES.get(language.strip().lower(), language.strip().lower())
    if name == "diff":
        return name
    if _pygments_lexers is not None:
        lexer = _pygments_lexer(name)
        return lexer.aliases[0] if lexer is not None else None
    return name if name in _LANGUAGES else None


def language_for_path(path):
    """Return the language to colour ``path`` with, judged by its file name, or None."""
    if not path:
        return None
    if _pygments_lexers is not None:
        try:
            lexer = _pygments_lexers.get_lexer_for_filename(os.path.basename(path))
        except _ClassNotFound:
            return supported(_PYGMENTS_EXTENSIONS.get(os.path.splitext(path)[1].lower()))
        return supported(lexer.aliases[0]) if lexer.aliases else None
    return _EXTENSIONS.get(os.path.splitext(path)[1].lower())


def _regex(name):
    if name not in _COMPILED:
        _COMPILED[name] = re.compile(_LANGUAGES[name], re.VERBOSE | re.DOTALL | re.MULTILINE)
    return _COMPILED[name]


def _span(kind, text):
    return '<span class="tok tok--%s">%s</span>' % (kind, html.escape(text, quote=True))


def _pygments_kind(ttype):
    return next((kind for parent, kind in _PYGMENTS_KINDS if ttype in parent), None)


def _tokens(source, name):
    """Yield ``(kind, text)`` pairs whose texts concatenate back to ``source``."""
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    if name == "diff":
        for index, line in enumerate(source.split("\n")):
            if index:
                yield None, "\n"
            yield next((k for prefix, k in _DIFF_PREFIXES if line.startswith(prefix)), None), line
        return
    if _pygments_lexers is not None:
        bom = len(source) - len(source.lstrip("\ufeff"))
        if bom:
            yield None, source[:bom]
        body = source[bom:]
        emitted = 0
        lexed = []
        for ttype, text in _pygments_lexer(name).get_tokens(body):
            text = text[:max(0, len(body) - emitted)]
            emitted += len(text)
            kind = _pygments_kind(ttype)
            if name in _DATA_LANGUAGES and kind in ("tag", "attribute"):
                kind = "property"
            lexed.append((kind, text))
        if emitted < len(body):
            lexed.append((None, body[emitted:]))
        if "".join(text for _, text in lexed) != body:
            lexed = [(None, body)]
        yield from lexed
        return
    cursor = 0
    for match in _regex(name).finditer(source):
        if match.start() > cursor:
            yield None, source[cursor:match.start()]
        yield match.lastgroup, match.group()
        cursor = match.end()
    yield None, source[cursor:]


def _emit(kind, text):
    return _span(kind, text) if kind and text else html.escape(text, quote=True)


def highlight(source, language):
    """Return ``source`` as HTML with token spans, or escaped plain text.

    Falls back to plain escaped output for an unknown or missing language, so the
    caller never has to decide whether colouring applied. CRLF and CR line endings in
    highlighted output are normalised to LF.
    """
    name = supported(language)
    if name is None:
        return html.escape(source, quote=True)
    return "".join(_emit(kind, text) for kind, text in _tokens(source, name))


def highlight_lines(lines, language):
    """Highlight ``lines`` as one source and return one HTML string per line.

    Lexing the lines together keeps a comment or string that spans several of them
    coloured throughout; a token crossing a line break is split so every returned
    line closes its own spans.
    """
    name = supported(language)
    if name is None or not lines:
        return [html.escape(line, quote=True) for line in lines]
    out = [[]]
    for kind, text in _tokens("\n".join(lines), name):
        for index, part in enumerate(text.split("\n")):
            if index:
                out.append([])
            out[-1].append(_emit(kind, part))
    return ["".join(parts) for parts in out]
