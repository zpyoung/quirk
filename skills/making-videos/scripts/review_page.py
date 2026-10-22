#!/usr/bin/env python3
"""Build the self-contained review page for a making-videos project.

``review_page.py --project DIR`` writes ``<project>/review.html`` and prints ``{"page": path}``.
Each MP4's verify run and frames (``frames/<mp4 stem>/``) get their own block; an older flat
``verify.json`` and ``frames/`` still render. The page is one file: inline CSS, a few lines of inline JS for the compare players, no network
resources, so it opens from ``file://``. Every value taken from project files is HTML-escaped.
Exit codes: 0 ok; 1 the page could not be written; 2 usage error or missing project.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, NoReturn, Optional
from urllib.parse import quote

# siblings are imported by bare name, so the script directory must be on sys.path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _mv_common import EXIT_FAILED, EXIT_USAGE, emit  # noqa: E402

LOCAL_PROVIDERS = frozenset({"hyperframes", "playwright"})


class _Parser(argparse.ArgumentParser):
    """Argument parser whose usage errors are one JSON object on stdout, exit 2."""

    def error(self, message: str) -> NoReturn:
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        emit({"error": message}, EXIT_USAGE)


def esc(value: Any) -> str:
    """HTML-escape any value; non-strings are JSON-encoded first."""
    if isinstance(value, str):
        text = value
    elif value is None:
        text = ""
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        text = str(value)
    else:
        text = json.dumps(value)
    return html.escape(text, quote=True)


def rel_url(path: Path, base: Path) -> str:
    """Percent-encoded relative URL of ``path`` under ``base``, escaped for an attribute."""
    return esc(quote(path.relative_to(base).as_posix(), safe="/"))


_CODE_SPAN = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_FENCE = re.compile(r"^\s*```")


def _inline(text: str) -> str:
    parts = _CODE_SPAN.split(text)
    out = []
    for i, part in enumerate(parts):
        if i % 2:
            out.append("<code>%s</code>" % esc(part))
        else:
            out.append(_BOLD.sub(lambda m: "<strong>%s</strong>" % m.group(1), esc(part)))
    return "".join(out)


def render_markdown(text: str) -> str:
    """Render a small Markdown subset to HTML; unknown syntax falls back to escaped text."""
    lines = text.splitlines()
    out: "list[str]" = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _FENCE.match(line):
            i += 1
            code = []
            while i < len(lines) and not _FENCE.match(lines[i]):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>%s</code></pre>" % esc("\n".join(code)))
            continue
        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            out.append("<h%d>%s</h%d>" % (level, _inline(heading.group(2)), level))
            i += 1
            continue
        for pattern, tag in ((_BULLET, "ul"), (_NUMBERED, "ol")):
            if pattern.match(line):
                items = []
                while i < len(lines) and pattern.match(lines[i]):
                    items.append("<li>%s</li>" % _inline(pattern.match(lines[i]).group(1)))
                    i += 1
                out.append("<%s>\n%s\n</%s>" % (tag, "\n".join(items), tag))
                break
        else:
            if not line.strip():
                i += 1
                continue
            para = []
            while (
                i < len(lines)
                and lines[i].strip()
                and not _FENCE.match(lines[i])
                and not _HEADING.match(lines[i])
                and not _BULLET.match(lines[i])
                and not _NUMBERED.match(lines[i])
            ):
                para.append(lines[i].strip())
                i += 1
            out.append("<p>%s</p>" % _inline(" ".join(para)))
    return "\n".join(out)


def _read_json(path: Path) -> "tuple[Optional[Any], Optional[str]]":
    """Parsed JSON and None, or None and a short reason the file could not be used."""
    if not path.is_file():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeError, ValueError) as exc:
        return None, "unreadable (%s)" % type(exc).__name__


def _version_dirs(project: Path) -> "list[Path]":
    found = [p for p in project.iterdir() if p.is_dir() and re.fullmatch(r"v\d+", p.name)]
    return sorted(found, key=lambda p: int(p.name[1:]), reverse=True)


def _list_cell(value: Any) -> str:
    return esc(", ".join(str(v) for v in value)) if isinstance(value, list) else esc(value)


def render_header(brief: Any, reason: Optional[str]) -> str:
    if not isinstance(brief, dict):
        return (
            "<h1>Video review</h1>\n<p class=\"missing\">brief.json %s, so the header is empty.</p>"
            % esc(reason or "is not an object")
        )
    narration = "on" if brief.get("narration") else "off"
    length = brief.get("length_s")
    facts = [
        ("Product", esc(brief.get("product"))),
        ("Length", esc("%s s" % length) if length is not None else ""),
        ("Aspects", _list_cell(brief.get("aspects"))),
        ("Narration", narration),
        ("Date", esc(brief.get("created"))),
    ]
    dl = "".join("<div><dt>%s</dt><dd>%s</dd></div>" % (k, v) for k, v in facts)
    return "<h1>%s</h1>\n<dl class=\"facts\">%s</dl>" % (esc(brief.get("title") or "Video review"), dl)


def _checks_table(checks: Any) -> str:
    if not isinstance(checks, list) or not checks:
        return "<p class=\"missing\">verify.json lists no checks.</p>"
    rows = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        status = str(check.get("status", ""))
        rows.append(
            "<tr class=\"check-%s\"><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (
                esc(re.sub(r"[^a-z]", "", status.lower())),
                esc(check.get("name")),
                esc(status),
                esc(check.get("measured")),
                esc(check.get("threshold")),
                esc(check.get("detail")),
            )
        )
    return (
        "<div class=\"scroll\"><table><thead><tr><th>Check</th><th>Status</th><th>Measured</th>"
        "<th>Threshold</th><th>Detail</th></tr></thead><tbody>%s</tbody></table></div>"
        % "".join(rows)
    )


def _verdict(data: dict) -> str:
    passed = bool(data.get("passed"))
    attempts = data.get("attempt")
    return "<p class=\"verdict %s\"><strong>%s</strong>%s</p>" % (
        "pass" if passed else "fail",
        "Verify passed" if passed else "Verify failed",
        esc(" (attempt %s)" % attempts) if attempts is not None else "",
    )


def _verify_block(vdir: Path, mp4s: "list[Path]", missing: "list[str]") -> str:
    """Verdict and check table per MP4 run; a flat ``verify.json`` without ``runs`` renders as one run."""
    data, reason = _read_json(vdir / "verify.json")
    if reason == "missing":
        missing.append("no verify.json")
        return ""
    if reason or not isinstance(data, dict):
        missing.append("verify.json %s" % (reason or "is not an object"))
        return ""
    runs = data.get("runs")
    if not isinstance(runs, dict):
        return _verdict(data) + _checks_table(data.get("checks"))
    parts = [_verdict(data)]
    for name in sorted(runs):
        run = runs[name]
        if not isinstance(run, dict):
            continue
        parts.append(
            "<div class=\"run\" id=\"run-%s\"><h4>%s</h4>%s%s</div>"
            % (esc(name), esc(name), _verdict(run), _checks_table(run.get("checks")))
        )
    missing.extend("no verify run for %s" % mp4.name for mp4 in mp4s if mp4.name not in runs)
    return "".join(parts)


def _frames_html(project: Path, vdir: Path, mp4s: "list[Path]", missing: "list[str]") -> "list[str]":
    """Contact sheet and stills per MP4 (``frames/<stem>/``), or the flat ``frames/`` of an older verify run."""
    frames = vdir / "frames"
    groups = [(mp4.name, "frames/%s/" % mp4.stem, frames / mp4.stem) for mp4 in mp4s if (frames / mp4.stem).is_dir()]
    if not groups or (frames.is_dir() and any(frames.glob("*.png"))):
        groups.append(("", "frames/", frames))
    out = []
    for label, where, folder in groups:
        sheet = folder / "sheet.png"
        stills = sorted(p for p in folder.glob("*.png") if p.name != "sheet.png") if folder.is_dir() else []
        if label:
            out.append("<h4>%s</h4>" % esc(label))
        if sheet.is_file():
            out.append(
                "<figure><img loading=\"lazy\" alt=\"Contact sheet for %s\" src=\"%s\">"
                "<figcaption>Contact sheet</figcaption></figure>" % (esc(label or vdir.name), rel_url(sheet, project))
            )
        else:
            missing.append("no %ssheet.png" % where)
        if stills:
            imgs = "".join(
                "<figure><img loading=\"lazy\" alt=\"%s\" src=\"%s\"><figcaption>%s</figcaption></figure>"
                % (esc(s.name), rel_url(s, project), esc(s.name))
                for s in stills
            )
            out.append("<div class=\"stills\">%s</div>" % imgs)
        else:
            missing.append("no stills in %s" % where)
    return out


def render_version(project: Path, vdir: Path) -> "tuple[str, list[Path]]":
    """HTML section for one version and its MP4 paths (for the compare selects)."""
    missing: "list[str]" = []
    mp4s = sorted(vdir.glob("*.mp4"))
    parts = ["<h3>Video</h3>"]
    if mp4s:
        for mp4 in mp4s:
            parts.append(
                "<figure><video controls preload=\"metadata\" playsinline src=\"%s\"></video>"
                "<figcaption>%s</figcaption></figure>" % (rel_url(mp4, project), esc(mp4.name))
            )
    else:
        missing.append("no MP4")
    srts = sorted(vdir.glob("*.srt"))
    if srts:
        parts.append(
            "<p>Captions: %s</p>"
            % ", ".join("<a href=\"%s\">%s</a>" % (rel_url(s, project), esc(s.name)) for s in srts)
        )

    parts.append("<h3>Verify</h3>")
    parts.append(_verify_block(vdir, mp4s, missing))
    parts.append("<h3>Frames</h3>")
    parts.extend(_frames_html(project, vdir, mp4s, missing))

    note = ""
    if missing:
        note = "<p class=\"missing\">Missing: %s.</p>" % esc("; ".join(missing))
    section = (
        "<section class=\"version\" id=\"%s\">\n<h2>%s</h2>\n%s\n%s\n</section>"
        % (esc(vdir.name), esc(vdir.name), note, "\n".join(parts))
    )
    return section, mp4s


def render_compare(project: Path, versions: "list[tuple[Path, list[Path]]]") -> str:
    options = []
    for vdir, mp4s in versions:
        if not mp4s:
            options.append(
                "<option value=\"\" disabled>%s (no video)</option>" % esc(vdir.name)
            )
        for mp4 in mp4s:
            label = vdir.name if len(mp4s) == 1 else "%s / %s" % (vdir.name, mp4.name)
            options.append("<option value=\"%s\">%s</option>" % (rel_url(mp4, project), esc(label)))
    playable = [i for i, o in enumerate(options) if "disabled" not in o]
    if not playable:
        return "<p class=\"missing\">No version has an MP4 to compare yet.</p>"
    initial = [playable[0], playable[1] if len(playable) > 1 else playable[0]]

    def pane(idx: int, which: str) -> str:
        opts = [
            o.replace("<option ", "<option selected ", 1) if j == initial[idx] else o
            for j, o in enumerate(options)
        ]
        src = re.search(r'value="([^"]*)"', options[initial[idx]]).group(1)
        return (
            "<div class=\"pane\"><label>%s <select data-target=\"cmp-%s\">%s</select></label>"
            "<video class=\"compare-player\" id=\"cmp-%s\" controls preload=\"metadata\" "
            "playsinline src=\"%s\"></video></div>" % (which.upper(), which, "".join(opts), which, src)
        )

    return "<div class=\"compare\">%s%s</div>" % (pane(0, "a"), pane(1, "b"))


def _read_calls(project: Path) -> "tuple[list[dict], int]":
    path = project / "calls.jsonl"
    if not path.is_file():
        return [], 0
    records, bad = [], 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(rec, dict):
            records.append(rec)
        else:
            bad += 1
    return records, bad


def render_calls(project: Path, brief: Any) -> str:
    records, bad = _read_calls(project)
    allowed = set(brief.get("cloud_allow") or []) if isinstance(brief, dict) else set()
    if not records and not bad:
        return "<p>No outside calls were logged.</p>"
    cols = ("ts", "provider", "method", "host", "path", "status", "bytes")
    rows = []
    for rec in records:
        provider = rec.get("provider")
        flagged = provider not in allowed and provider not in LOCAL_PROVIDERS
        cells = "".join("<td>%s</td>" % esc(rec.get(c)) for c in cols)
        if flagged:
            cells += "<td class=\"flag\">not in cloud_allow</td>"
        else:
            cells += "<td></td>"
        rows.append("<tr class=\"%s\">%s</tr>" % ("not-allowed" if flagged else "allowed", cells))
    head = "".join("<th>%s</th>" % c for c in cols) + "<th>Note</th>"
    note = "<p class=\"missing\">%d unreadable line(s) in calls.jsonl.</p>" % bad if bad else ""
    return (
        "%s<div class=\"scroll\"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>"
        % (note, head, "".join(rows))
    )


CSS = """
:root{--bg:#f7f7f5;--fg:#1c1c1a;--muted:#5d5d58;--card:#fff;--line:#d9d9d3;--pass:#176b3a;
--fail:#a42424;--warn-bg:#fdebd0;--warn-fg:#7a3b00;--code-bg:#efefea;--accent:#2455c3}
@media (prefers-color-scheme: dark){:root{--bg:#161614;--fg:#ececE6;--muted:#a3a39b;--card:#201f1d;
--line:#3a3a36;--pass:#6fd39a;--fail:#ff8d8d;--warn-bg:#4a2f10;--warn-fg:#ffd199;--code-bg:#2b2a27;
--accent:#8cb0ff}}
*{box-sizing:border-box}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);
font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;overflow-wrap:anywhere}
main{max-width:1100px;margin:0 auto}
h1{font-size:1.6rem;margin:0 0 .5rem}h2{font-size:1.25rem;margin:1.5rem 0 .5rem}
h3{font-size:1rem;margin:1rem 0 .4rem;color:var(--muted)}
h4{font-size:.95rem;margin:.75rem 0 .3rem}
a{color:var(--accent)}
.facts{display:flex;flex-wrap:wrap;gap:.5rem 1.5rem;margin:0 0 1rem}
.facts div{min-width:6rem}.facts dt{font-size:.8rem;color:var(--muted)}.facts dd{margin:0}
section,.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 16px;
margin:0 0 16px}
video,img{max-width:100%;height:auto;display:block}
video{width:100%;background:#000;border-radius:4px}
figure{margin:0 0 .75rem}figcaption{font-size:.85rem;color:var(--muted)}
.stills{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}
tr.check-fail td:nth-child(2),.verdict.fail{color:var(--fail);font-weight:600}
tr.check-pass td:nth-child(2),.verdict.pass{color:var(--pass)}
tr.not-allowed{background:var(--warn-bg);color:var(--warn-fg)}
.missing{color:var(--warn-fg);background:var(--warn-bg);padding:4px 8px;border-radius:4px}
pre{background:var(--code-bg);padding:8px;overflow-x:auto;border-radius:4px}
code{background:var(--code-bg);padding:0 .25em;border-radius:3px}pre code{padding:0}
.compare{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:640px){.compare{grid-template-columns:1fr}}
select{max-width:100%;font:inherit}
"""

JS = """
document.querySelectorAll('select[data-target]').forEach(function(sel){
  sel.addEventListener('change',function(){
    var v=document.getElementById(sel.getAttribute('data-target'));
    v.src=sel.value;v.load();
  });
});
"""


def build_page(project: Path) -> str:
    brief, brief_reason = _read_json(project / "brief.json")
    story_path = project / "storyboard.md"
    if story_path.is_file():
        storyboard = render_markdown(story_path.read_text(encoding="utf-8", errors="replace"))
    else:
        storyboard = "<p class=\"missing\">storyboard.md is missing.</p>"

    sections, versions = [], []
    for vdir in _version_dirs(project):
        section, mp4s = render_version(project, vdir)
        sections.append(section)
        versions.append((vdir, mp4s))
    versions_html = "\n".join(sections) or "<p class=\"missing\">No version folders yet.</p>"

    title = brief.get("title") if isinstance(brief, dict) else None
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n<main>\n"
        "<header>%s</header>\n"
        "<h2>Compare versions</h2>\n<div class=\"card\">%s</div>\n"
        "<h2>Versions, newest first</h2>\n%s\n"
        "<h2>Storyboard</h2>\n<div class=\"card storyboard\">%s</div>\n"
        "<h2>Outside calls</h2>\n<div class=\"card\">%s</div>\n"
        "</main>\n<script>%s</script>\n</body>\n</html>\n"
        % (
            esc("Review: %s" % title if title else "Video review"),
            CSS,
            render_header(brief, brief_reason),
            render_compare(project, versions),
            versions_html,
            storyboard,
            render_calls(project, brief),
            JS,
        )
    )


def main(argv: "Optional[list[str]]" = None) -> int:
    parser = _Parser(description="Build review.html for a making-videos project.")
    parser.add_argument("--project", required=True, help="project folder")
    args = parser.parse_args(argv)
    project = Path(args.project).expanduser()
    if not project.is_dir():
        emit({"error": "project directory not found: %s" % project}, EXIT_USAGE)
    page = project / "review.html"
    try:
        page.write_text(build_page(project), encoding="utf-8")
    except OSError as exc:
        emit({"error": "%s: %s" % (type(exc).__name__, exc)}, EXIT_FAILED)
    emit({"page": str(page)})


if __name__ == "__main__":
    sys.exit(main())
