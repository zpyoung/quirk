#!/usr/bin/env python3
"""Build every comment body the review skill posts, in one three-part shape.

Each body is a hidden YAML metadata block, a short visible section, and a collapsed
`<details>` section. Bodies are built only from trusted report data, and the builder
keeps hostile text from closing the metadata block (`-->`) or the collapsed section
(`</details>`) early, and keeps a line-leading `/` from running as a GitLab quick action. The block round-trips through `render_block` / `parse_block`.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prepare_diff  # noqa: E402
import render_report  # noqa: E402
import review_memory  # noqa: E402
from jsonio import write_json  # noqa: E402

OPEN_LINE = "<!-- quirk-review:v1"
CLOSE_LINE = "-->"
NON_BLOCKING_SENTENCE = "*Optional feedback — this does not block the merge.*"
QUESTION_SENTENCE = "Could you clarify how this behavior is intended to work?"
MAX_BLOCKER_BULLETS = 3

_KEY_RE = re.compile(r"[a-z_][a-z0-9_]*")
_PLAIN_RE = re.compile(r"[A-Za-z0-9_./@+-][A-Za-z0-9 _./@+-]*")
_AMBIGUOUS_RE = re.compile(r"-?\d+|true|false|null")
_INT_RE = re.compile(r"-?\d+")
_HEX64_RE = re.compile(r"[0-9a-f]{64}")
_FENCE_OPEN_RE = re.compile(r" {0,3}(`{3,}|~{3,})")
_FENCE_CLOSE_RE = re.compile(r" {0,3}(`{3,}|~{3,})[ \t]*")
_DETAILS_TAG_RE = re.compile(r"<(/?)details", re.IGNORECASE)
_QUICK_ACTION_RE = re.compile(r"^((?:[ \t]*>)*[ \t]*)/")
_HTML_BLOCK_OPEN_RE = re.compile(
    r"^((?:[ \t]*>)*[ \t]*)<(?=!--|!\[CDATA\[|![A-Za-z]|\?|/?[A-Za-z])")
_CODE_SPAN_OR_MENTION_RE = re.compile(
    r"(?P<code>(?<![\\`])(?P<ticks>`+)(?!`).+?(?<!`)(?P=ticks)(?!`))|(?P<mention>(?<!\w)@(?=[A-Za-z0-9_]))")
_LINE_BREAK_RE = re.compile(r"\r\n|[\r\u2028\u2029]")
_POSTED_SLOTS = ("fix", "later", "detail")
_DIGITS_RE = re.compile(r"[0-9]+")
_SENTENCE_END_RE = re.compile(r"(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)(?<!\betc)[.?!](?=\s|$)", re.IGNORECASE)
_SEATS = ("author", "reviewer")
_RISK_METRICS = (("likelihood", "Likelihood"), ("impact", "Impact"),
                 ("blast_radius", "Blast radius"), ("detection", "Detection"),
                 ("rollback", "Rollback"))
_STILL_OPEN_STATES = ("carried", "answered")
_RESOLVED_STATE = "re-found-after-resolution"


def _encode_str(value):
    if (_PLAIN_RE.fullmatch(value) and not value.endswith(" ")
            and not _AMBIGUOUS_RE.fullmatch(value)):
        return value
    return json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e")


def _encode_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return _encode_str(value)
    if isinstance(value, (list, tuple)):
        if any(not isinstance(item, str) for item in value):
            raise ValueError("block list values must contain only strings")
        return "[" + ", ".join(_encode_str(item) for item in value) + "]"
    raise ValueError("unsupported block value type: %s" % type(value).__name__)


def _decode_list(text):
    if not text.endswith("]"):
        raise ValueError("unterminated list")
    inner = text[1:-1]
    decoder = json.JSONDecoder()
    items = []
    pos = 0
    while True:
        while pos < len(inner) and inner[pos] == " ":
            pos += 1
        if pos >= len(inner):
            return items
        if inner[pos] == '"':
            item, pos = decoder.raw_decode(inner, pos)
            if not isinstance(item, str):
                raise ValueError("list item is not a string")
        else:
            end = inner.find(",", pos)
            end = len(inner) if end < 0 else end
            item = inner[pos:end].strip()
            if not item:
                raise ValueError("empty list item")
            pos = end
        items.append(item)
        while pos < len(inner) and inner[pos] == " ":
            pos += 1
        if pos < len(inner):
            if inner[pos] != ",":
                raise ValueError("expected a comma between list items")
            pos += 1


def _decode_value(text):
    if text.startswith('"'):
        value = json.loads(text)
        if not isinstance(value, str):
            raise ValueError("quoted value is not a string")
        return value
    if text.startswith("["):
        return _decode_list(text)
    if text == "true":
        return True
    if text == "false":
        return False
    if text == "null":
        return None
    if _INT_RE.fullmatch(text):
        return int(text)
    return text


def render_block(meta):
    """Render the hidden metadata block for `meta`, dropping None values.

    Raises ValueError on a key outside `[a-z_][a-z0-9_]*` or an unsupported value type, so the
    block can always be parsed back to exactly what was written.
    """
    lines = [OPEN_LINE]
    for key, value in meta.items():
        if not isinstance(key, str) or not _KEY_RE.fullmatch(key):
            raise ValueError("invalid block key: %r" % (key,))
        if value is None:
            continue
        lines.append("%s: %s" % (key, _encode_value(value)))
    lines.append(CLOSE_LINE)
    return "\n".join(lines)


def parse_block(body):
    """Return the leading metadata block of `body` as a typed dict, else None.

    Only a block at the very start (after whitespace) counts, so a block quoted or
    pasted later in someone's comment is never read as ours. A malformed or
    unterminated block also returns None.
    """
    if not isinstance(body, str):
        return None
    lines = body.lstrip().split("\n")
    if lines[0].rstrip() != OPEN_LINE:
        return None
    result = {}
    for raw in lines[1:]:
        line = raw.rstrip("\r")
        if line == CLOSE_LINE:
            return result
        key, separator, value = line.partition(": ")
        if not separator or not _KEY_RE.fullmatch(key):
            return None
        try:
            result[key] = _decode_value(value.strip())
        except ValueError:
            return None
    return None


def first_sentence(md):
    """Return the first sentence of `md` on one line, or None when there isn't a usable one.

    Sentences may span hard-wrapped lines but never cross a blank line. A leading code fence
    yields None because a fence cannot be quoted as prose.
    """
    if not isinstance(md, str) or not md.strip():
        return None
    text = md.strip()
    if text.startswith("```") or text.startswith("~~~"):
        return None
    paragraph = []
    for line in text.split("\n"):
        if not line.strip() or _FENCE_OPEN_RE.match(line):
            break
        paragraph.append(line)
    flat = " ".join(" ".join(paragraph).split())
    match = _SENTENCE_END_RE.search(flat)
    if match:
        flat = flat[:match.end()]
    return flat or None


def _defuse_mentions(line):
    return _CODE_SPAN_OR_MENTION_RE.sub(
        lambda match: match.group("code") or "@\u200b", line)


def _neutralize(text, inline=False):
    """Make untrusted markdown inert inside the comment skeleton.

    With `inline`, the text's first line is embedded after a prefix, so it cannot open a fence.

    It cannot close our `<details>` or metadata block, run a GitLab quick action as the poster,
    open a raw HTML block that hides a fence or swallows the note, leave a fence open, or notify
    a user. The escapes apply fenced or not because GitLab's renderer and quick-action extractor
    can disagree with our fence parsing.
    """
    out = []
    fence = None
    for index, line in enumerate(_LINE_BREAK_RE.sub("\n", str(text)).split("\n")):
        line = _DETAILS_TAG_RE.sub(r"&lt;\1details", line)
        if fence is None:
            opened = None if inline and index == 0 else _FENCE_OPEN_RE.match(line)
            if opened and not (opened.group(1)[0] == "`" and "`" in line[opened.end():]):
                fence = opened.group(1)
                out.append(line)
            else:
                line = _QUICK_ACTION_RE.sub(r"\1\\/", line, count=1)
                line = _defuse_mentions(line)
                out.append(_HTML_BLOCK_OPEN_RE.sub(r"\1&lt;", line, count=1))
            continue
        out.append(_QUICK_ACTION_RE.sub(r"\1\\/", line, count=1))
        closed = _FENCE_CLOSE_RE.fullmatch(line)
        if closed and closed.group(1)[0] == fence[0] and len(closed.group(1)) >= len(fence):
            fence = None
    if fence is not None:
        out.append(fence)
    return "\n".join(out)


def _without_prefix(path, prefix):
    return path[len(prefix):] if path.startswith(prefix) else path


def path_pairs(diff_text):
    """Map each new path in a unified diff to its {"old", "new"} paths, following renames.

    Quoted paths are decoded the way git quotes them, and lines split on newlines only.
    """
    pairs = {}
    current = None
    for line in prepare_diff._diff_lines(str(diff_text or "")):
        fields = prepare_diff._diff_git_fields(line)
        if fields and all(fields):
            old_path, new_path = _without_prefix(fields[0], "a/"), _without_prefix(fields[1], "b/")
            current = {"old": old_path, "new": new_path}
            pairs[new_path] = current
        elif current and line.startswith("rename from "):
            current["old"] = prepare_diff._decode_git_path(line[len("rename from "):]) or current["old"]
        elif current and line.startswith("rename to "):
            renamed = prepare_diff._decode_git_path(line[len("rename to "):])
            if renamed:
                old_key = current["new"]
                current["new"] = renamed
                pairs.pop(old_key, None)
                pairs[renamed] = current
    return pairs


def _md(value, inline=False):
    return _neutralize(str(value).strip(), inline)


def _line(value):
    return _neutralize(" ".join(str(value).split()), inline=True)


def _paragraph(value):
    """A collapsed one-line `value` as its own paragraph, so a leading fence is balanced."""
    return _neutralize(" ".join(str(value).split()))


def _quote(text):
    return "\n".join("> " + line if line.strip() else ">" for line in text.split("\n"))


def _details(parts):
    return "<details><summary>Details</summary>\n\n%s\n\n</details>" % "\n\n".join(parts)


def _assemble(block, parts):
    return render_block(block) + "\n" + "\n\n".join(parts) + "\n"


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _fingerprint(finding):
    memory = finding.get("memory")
    value = memory.get("fingerprint") if isinstance(memory, dict) else None
    return value if isinstance(value, str) and _HEX64_RE.fullmatch(value) else None


def _line_value(finding):
    line = str(finding.get("line", "")).strip()
    return int(line) if _DIGITS_RE.fullmatch(line) else (line or None)


def _label(finding):
    return str(finding.get("id") or "finding")


def _over_cap(sentence, field):
    return bool(sentence) and len(sentence) > render_report._POSTED_TEXT_CAPS[field]


def _why_and_fix(finding, warnings):
    label = _label(finding)
    why = _text(finding.get("impact"))
    if why:
        why = " ".join(why.split())
    else:
        why = first_sentence(finding.get("body_md") or finding.get("issue"))
        if _over_cap(why, "impact"):
            warnings.append("%s: impact missing; first sentence of body exceeds %d characters, "
                            "why line omitted" % (label, render_report._POSTED_TEXT_CAPS["impact"]))
            why = None
        else:
            warnings.append("%s: impact missing; %s" % (
                label, "used first sentence of body" if why else "no why line"))
    fix = _text(finding.get("fix_md"))
    if fix:
        return why, " ".join(fix.split())
    recommendation = finding.get("recommendation_md") or finding.get("recommendation")
    fix = first_sentence(recommendation)
    if _over_cap(fix, "fix_md"):
        warnings.append("%s: fix_md missing; first sentence of recommendation exceeds %d "
                        "characters, fix line omitted" % (label, render_report._POSTED_TEXT_CAPS["fix_md"]))
        fix = None
    elif fix:
        warnings.append("%s: fix_md missing; used first sentence of recommendation" % label)
    elif _text(recommendation):
        warnings.append("%s: fix_md missing; recommendation starts with a code fence, "
                        "fix line omitted" % label)
    else:
        warnings.append("%s: fix_md missing; no recommendation, fix line omitted" % label)
    return why, fix


def _details_parts(finding, why, reviewer_note):
    body = _text(finding.get("body_md") or finding.get("issue"))
    if body and why and " ".join(body.split()) == why:
        body = None
    aside = _text(finding.get("aside_md"))
    evidence = finding.get("evidence")
    if isinstance(evidence, (list, tuple)):
        evidence = "; ".join(str(item) for item in evidence)
    evidence = " ".join(str(evidence).split()) if evidence else ""
    assumptions = finding.get("assumptions")
    if isinstance(assumptions, str):
        assumptions = [assumptions]
    if assumptions is not None and not isinstance(assumptions, (list, tuple)):
        raise ValueError("finding assumptions must be a list of strings")
    assumptions = [" ".join(str(item).split()) for item in (assumptions or []) if str(item).strip()]
    if not (body or aside or evidence or assumptions or reviewer_note):
        return []
    parts = []
    if reviewer_note:
        parts.append("**Reviewer note:**\n\n%s" % _md(reviewer_note))
    if body:
        parts.append(_md(body))
    if aside:
        parts.append(_quote(_md(aside)))
    facts = "**Evidence:** %s · %s" % (
        _line(evidence) if evidence else "none",
        "verified" if finding.get("verified") is True else "unverified")
    if assumptions:
        facts += "  \n**Assumptions:** %s" % _line("; ".join(assumptions))
    parts.append(facts)
    return [_details(parts)]


def _check_seat(seat):
    if seat not in _SEATS:
        raise ValueError("seat must be author or reviewer")


def _finding_block(kind, finding, seat, disposition, head_sha, leading):
    block = {"kind": kind, "fp": _fingerprint(finding)}
    block.update(leading)
    block.update({
        "seat": seat, "severity": finding.get("severity"), "disposition": disposition,
        "dimensions": [str(item) for item in finding.get("dimensions") or []] or None,
        "file": str(finding["file"]).strip() if finding.get("file") is not None else None,
        "line": _line_value(finding), "head_sha": head_sha,
        "verified": finding["verified"] if isinstance(finding.get("verified"), bool) else None,
    })
    return block


def finding_body(finding, *, seat, lead, note="", head_sha=None):
    """Build the comment body for one finding and return (body, warnings).

    `lead` is the disposition on the reviewer seat and the severity on the author seat.
    Warnings name each fallback taken when `impact` or `fix_md` is missing.
    """
    _check_seat(seat)
    warnings = []
    why, fix = _why_and_fix(finding, warnings)
    block = _finding_block("finding", finding, seat,
                           lead if seat == "reviewer" else None, head_sha, {})
    parts = ["**%s** · %s" % (lead, _line(finding.get("title", "")))]
    if lead == "Non-blocking":
        parts.append(NON_BLOCKING_SENTENCE)
    elif lead == "Question":
        parts.append(QUESTION_SENTENCE)
    if _text(note):
        parts.append("> **Reviewer note:** " + _quote(_md(note, inline=True))[2:])
    if why:
        parts.append(_paragraph(why))
    if fix:
        parts.append("**Fix:** %s" % _line(fix))
    parts.extend(_details_parts(finding, why, None))
    return _assemble(block, parts), warnings


def support_body(finding, *, disposition, discussion_id, note_id, note="", head_sha=None):
    """Build a reply that backs another person's discussion and return (body, warnings).

    The reviewer's note goes inside Details so the visible section stays at the lead,
    the reason, and the fix.
    """
    warnings = []
    why, fix = _why_and_fix(finding, warnings)
    block = _finding_block(
        "support", finding, "reviewer", disposition, head_sha,
        {"supports_discussion": str(discussion_id), "supports_note": note_id})
    parts = ["**Agree · %s** · quirk full-code-review found this independently" % disposition]
    if why:
        parts.append(_paragraph(why))
    if fix:
        parts.append("**Fix:** %s" % _line(fix))
    parts.extend(_details_parts(finding, why, _text(note)))
    return _assemble(block, parts), warnings


def _unique(values):
    seen = []
    for value in values:
        if isinstance(value, str) and value and value not in seen:
            seen.append(value)
    return seen


def _risk_section(risk):
    if not isinstance(risk, dict):
        return None
    parts = []
    if _text(risk.get("level")):
        parts.append("**Level:** %s" % _line(risk["level"]))
    metrics = risk.get("metrics") if isinstance(risk.get("metrics"), dict) else {}
    rows = []
    for key, label in _RISK_METRICS:
        entry = metrics.get(key)
        if isinstance(entry, dict) and _text(entry.get("level")):
            row = "- **%s:** %s" % (label, _line(entry["level"]))
            if _text(entry.get("note_md")):
                row += " — %s" % _line(entry["note_md"])
            rows.append(row)
    if rows:
        parts.append("\n".join(rows))
    if _text(risk.get("mitigations_md")):
        parts.append("**Lowering this risk:**\n\n%s" % _md(risk["mitigations_md"]))
    if _text(risk.get("verbatim_md")):
        parts.append(_md(risk["verbatim_md"]))
    for caveat in risk.get("caveats") if isinstance(risk.get("caveats"), list) else []:
        if isinstance(caveat, dict) and _text(caveat.get("body_md")):
            parts.append("**%s:**\n\n%s" % (_line(caveat.get("title") or "Caveat"),
                                            _md(caveat["body_md"])))
    return "**Risk**\n\n" + "\n\n".join(parts) if parts else None


def _clean_section(notes):
    parts = []
    for item in notes if isinstance(notes, list) else []:
        if isinstance(item, dict):
            if _text(item.get("note_md")):
                parts.append("**%s:** %s" % (_line(item.get("dimension") or "Review"),
                                             _md(item["note_md"], inline=True)))
        elif _text(item):
            parts.append(_md(item))
    return "**Clean dimensions**\n\n" + "\n\n".join(parts) if parts else None


def _probe_section(probe):
    if not isinstance(probe, dict):
        return None
    counts = ["%s: %s" % (label, _line(probe[key])) for key, label in
              (("mutants", "Mutants"), ("killed", "Killed"), ("survived", "Survived"))
              if probe.get(key) is not None]
    parts = [" · ".join(counts)] if counts else []
    if _text(probe.get("narrative_md")):
        parts.append(_md(probe["narrative_md"]))
    return "**Mutation probe**\n\n" + "\n\n".join(parts) if parts else None


def _skipped_label(item):
    if isinstance(item, dict):
        return "%s (%s)" % (item.get("name", "unknown"), item.get("why", "source unavailable"))
    return str(item)


def _title_of(item, by_id, id_key):
    title = _text(item.get("title"))
    if title:
        return title
    found = by_id.get(item.get(id_key))
    return _text(found.get("title")) if found else None


def _earlier_section(heading, omitted, by_id):
    rows = []
    for item in omitted:
        title = _title_of(item, by_id, "id") or str(item.get("id") or "finding")
        row = "- %s" % _line(title)
        if _text(item.get("thread_url")):
            row += " — %s" % _line(item["thread_url"])
        rows.append(row)
    return "**%s**\n\n%s" % (heading, "\n".join(rows)) if rows else None


def _unplaced_section(omitted, by_id):
    """List approved findings the forge could not anchor inline, so they still reach the author."""
    rows = []
    for item in omitted:
        if not item.get("unplaced"):
            continue
        found = by_id.get(item.get("id")) or {}
        title = _title_of(item, by_id, "id") or str(item.get("id") or "finding")
        row = "- **%s:** %s" % (_line(item.get("disposition") or "Finding"), _line(title))
        if found.get("file"):
            row += " (`%s`)" % _line(("%s:%s" % (found["file"], found.get("line", ""))).replace("`", ""))
        if _text(found.get("impact")):
            row += " — %s" % _line(found["impact"])
        rows.append(row)
    return "**Not anchored inline**\n\n%s" % "\n".join(rows) if rows else None


def _appears_fixed_section(report):
    memory = report.get("memory") if isinstance(report.get("memory"), dict) else {}
    rows = []
    for item in memory.get("appears_fixed") or []:
        if not isinstance(item, dict):
            continue
        row = "- %s" % _line(item.get("title") or "Earlier finding")
        if item.get("file"):
            row += " — %s%s" % (_line(item["file"]),
                                ":%s" % _line(item["line"]) if item.get("line") not in (None, "") else "")
        thread = item.get("thread") if isinstance(item.get("thread"), dict) else {}
        if _text(thread.get("url")):
            row += " — %s" % _line(thread["url"])
        rows.append(row)
    return "**Appears fixed**\n\n%s" % "\n".join(rows) if rows else None


def _run_limits_section(run, head_note, posted, omitted):
    rows = []
    if _text(run.get("source_access_reason")):
        rows.append("- **Source access:** %s" % _line(run["source_access_reason"]))
    skipped = run.get("dimensions_skipped") if isinstance(run.get("dimensions_skipped"), list) else []
    if skipped:
        rows.append("- **Skipped dimensions:** %s" %
                    _line(", ".join(_skipped_label(item) for item in skipped)))
    if head_note:
        rows.append("- **Head moved:** %s" % _line(head_note))
    rows.append("- Posted: %d · Not posted: %d" % (len(posted), len(omitted)))
    return "**Run limits**\n\n" + "\n".join(rows)


def _count_line(still_open, resolved):
    halves = []
    if still_open:
        halves.append("%d earlier finding%s still open" % (still_open, "" if still_open == 1 else "s"))
    if resolved:
        halves.append("%d previously resolved, still present" % resolved)
    return " · ".join(halves)


def overview_body(report, *, seat, posted, omitted, report_sha256, head_note=None):
    """Build the overview note for a review run and return (body, warnings).

    `posted` and `omitted` come from the staging plan; fingerprints and titles missing
    from them are looked up from the prepared report's findings by id.
    """
    _check_seat(seat)
    warnings = []
    meta = report["meta"]
    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    findings = [item for item in report.get("findings") or [] if isinstance(item, dict)]
    by_id = {item["id"]: item for item in findings if "id" in item}

    def fingerprint_of(item, id_key):
        value = item.get("fingerprint")
        if isinstance(value, str) and value:
            return value
        found = by_id.get(item.get(id_key))
        memory = found.get("memory") if found else None
        return memory.get("fingerprint") if isinstance(memory, dict) else None

    still_open = [item for item in omitted if item.get("memory_state") in _STILL_OPEN_STATES]
    resolved = [item for item in omitted if item.get("memory_state") == _RESOLVED_STATE]
    block = {
        "kind": "overview", "seat": seat, "head_sha": meta.get("head_sha"),
        "report_sha256": report_sha256,
        "posted": _unique(fingerprint_of(item, "finding_id") for item in posted) or None,
        "still_open": _unique(fingerprint_of(item, "id") for item in still_open) or None,
        "previously_resolved": _unique(fingerprint_of(item, "id") for item in resolved) or None,
        "supported": _unique(fingerprint_of(item, "finding_id") for item in posted
                             if item.get("kind") == "reply") or None,
    }

    tally = render_report._tally(findings)
    headline = "%d Must fix · %d Should fix · %d Nit" % (tally["must"], tally["should"], tally["nit"])
    verdict = _text(meta.get("verdict"))
    parts = ["**%s** · %s" % (_line(verdict), headline) if verdict else headline]
    if run.get("source_access") == "diff-only":
        parts.append("> Diff-only review: every finding is unverified.")
    if head_note:
        parts.append("> Head moved: %s" % _line(head_note))
    bullets = []
    for item in posted:
        if item.get("disposition") != "Blocking" or len(bullets) >= MAX_BLOCKER_BULLETS:
            continue
        title = _title_of(item, by_id, "finding_id")
        if not title:
            warnings.append("overview: blocking item %s has no title" % item.get("finding_id"))
            title = str(item.get("finding_id") or "finding")
        bullets.append("- **Blocking:** %s" % _line(title))
    if bullets:
        parts.append("\n".join(bullets))
    count_line = _count_line(len(still_open), len(resolved))
    if count_line:
        parts.append(count_line)
    unplaced = _unplaced_section(omitted, by_id)
    if unplaced:
        parts.append(unplaced)

    sections = [
        "**Summary**\n\n%s" % _md(meta["standfirst_md"]) if _text(meta.get("standfirst_md")) else None,
        _risk_section(report.get("risk")),
        ("**Assumptions**\n\n%s" % "\n".join("- %s" % _line(item) for item in report["assumptions"]
                                             if str(item).strip())
         if isinstance(report.get("assumptions"), list)
         and any(str(item).strip() for item in report["assumptions"]) else None),
        _clean_section(run.get("clean_notes")),
        _probe_section(report.get("mutation_probe")),
        _earlier_section("Still open from earlier reviews", still_open, by_id),
        _earlier_section("Previously resolved, still present", resolved, by_id),
        _appears_fixed_section(report),
        _run_limits_section(run, head_note, posted, omitted),
    ]
    parts.append(_details([section for section in sections if section]))
    return _assemble(block, parts), warnings


_report_digest = review_memory._report_digest


def _decision_rows(path, raw):
    """Load the author triage decisions bound to `raw` and return {finding id: row}, or None.

    Raises ValueError unless the file is an author-seat decisions export whose
    `report_sha256` matches the report being rendered.
    """
    if not path:
        return None
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("decisions must be a decisions export object")
    if value.get("seat") != "author":
        raise ValueError("decisions seat must be author")
    if value.get("report_sha256") != _report_digest(raw):
        raise ValueError("decisions were not made against this report")
    rows = value.get("decisions")
    if not isinstance(rows, list):
        raise ValueError("decisions must contain a decisions list")
    return {row["id"]: row for row in rows
            if isinstance(row, dict) and isinstance(row.get("id"), str)}


def _dropped_label(row):
    """Name why a decision kept a finding off the change: the row's own label, else Ignore or Undecided."""
    label = row.get("disposition")
    if isinstance(label, str) and label.strip():
        return label
    return "Ignore" if row.get("slot") == "ignore" else "Undecided"


def _author_bodies(raw, decisions=None):
    prepared, warnings = render_report._prepare_report(raw)
    meta = prepared["meta"]
    if meta["seat"] != "author":
        raise ValueError("author subcommand requires meta.seat to be author, got %r" % meta["seat"])
    head_sha = meta.get("head_sha")
    floor = render_report.severity_floor(prepared)
    bodies = {}
    posted = []
    omitted = []
    for finding in prepared["findings"]:
        row = (decisions or {}).get(finding["id"], {})
        body, finding_warnings = finding_body(
            finding, seat="author", lead=finding["severity"],
            note=row.get("note") if isinstance(row.get("note"), str) else "",
            head_sha=head_sha)
        bodies[finding["id"]] = {"body": body, "fingerprint": _fingerprint(finding), "post": False}
        memory = finding.get("memory") if isinstance(finding.get("memory"), dict) else {}
        if memory.get("suppress_post") is True:
            thread = memory.get("thread") if isinstance(memory.get("thread"), dict) else {}
            omitted.append({"id": finding["id"], "reason": "already posted",
                            "memory_state": memory.get("state"),
                            "thread_url": thread.get("url"),
                            "fingerprint": memory.get("fingerprint")})
        elif render_report.below_floor(finding, floor):
            omitted.append({"id": finding["id"], "reason": "below the posting floor (%s)" % floor,
                            "disposition": "Below floor", "fingerprint": memory.get("fingerprint")})
        elif finding.get("verification_status") == "plausible":
            omitted.append({"id": finding["id"], "reason": "plausible finding (never posted)",
                            "file": finding["file"], "line": finding["line"],
                            "severity": finding["severity"]})
        elif decisions is None or row.get("slot") in _POSTED_SLOTS:
            warnings.extend(finding_warnings)
            bodies[finding["id"]]["post"] = True
            posted.append({"kind": "inline", "finding_id": finding["id"], "disposition": None,
                           "fingerprint": memory.get("fingerprint"), "title": finding["title"]})
        else:
            label = _dropped_label(row)
            omitted.append({"id": finding["id"], "reason": label, "disposition": label,
                            "fingerprint": memory.get("fingerprint")})
    overview, overview_warnings = overview_body(
        prepared, seat="author", posted=posted, omitted=omitted,
        report_sha256=_report_digest(raw))
    warnings.extend(overview_warnings)
    return {"findings": bodies, "overview": overview, "warnings": warnings,
            "overview_plan": {"posted": posted, "omitted": omitted},
            "report_sha256": _report_digest(raw)}


def main(argv=None):
    """Run the author-seat CLI; exit 0 on success, 2 with a JSON error otherwise."""
    parser = argparse.ArgumentParser(description="Build comment bodies from a review report.")
    commands = parser.add_subparsers(dest="command", required=True)
    author = commands.add_parser("author", help="build finding and overview bodies")
    author.add_argument("--report", required=True)
    author.add_argument("--decisions")
    author.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        with open(args.report, encoding="utf-8") as handle:
            raw = json.load(handle)
        result = _author_bodies(raw, _decision_rows(args.decisions, raw))
        target = os.path.abspath(args.out)
        write_json(target, result)
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps({"out": target, "findings": len(result["findings"]),
                      "warnings": result["warnings"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
