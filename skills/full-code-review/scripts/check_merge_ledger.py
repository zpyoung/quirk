#!/usr/bin/env python3
"""Check that every specialist wrote its files and the merge accounted for every raw finding.

Inputs, all under `$REVIEW_RUN_DIR`:

  dispatch.json           {"agents": [...]}, one entry per findings specialist dispatched:
                            {"name": "<file stem>"}
                            {"name": ..., "exempt": "<why it has no files>"}
                          The name is the dimension id without `quirk:`, plus `-batch<k>` per
                          batch. `exempt` marks an agent that failed after its retry or was
                          degraded, and is recorded the same way in the report.
  tables/<name>.md        the enumeration tables a table-owning dimension wrote. Every cell
                          that records a problem carries `[#<n>]` (or `[#<n>, #<m>]`) right
                          after the problem text, citing raw finding n of raw/<name>.json; a
                          cell with no problem carries none.

  raw/<name>.json         one specialist's findings exactly as returned, a JSON array.
                          Raw finding `<name>#<n>` is item n (from 0) of that file.
  merged-findings.json    the merged findings, a JSON array or {"findings": [...]}.
                          Kept finding k is item k (from 0).
  merge-ledger.json       {"entries": [...]}, one entry per raw finding:
                            {"raw": "<name>#<n>", "kept": k}
                            {"raw": ..., "reason": "duplicate", "kept": k}
                            {"raw": ..., "kept": k, "single_fix": "<the one change that fixes both>"}
                            {"raw": ..., "reason": "refuted", "evidence": "<what the source shows>"}
                            {"raw": ..., "reason": "out-of-scope" | "linter-enforced"}

The file check fails when a dispatched, non-exempt agent has no raw file, a raw file that
is not an array of finding objects, or (for a dimension in TABLE_OWNERS) no tables file or
an empty one. It also fails a table cell that is empty, a cell in one of PROBLEM_ANSWERS'
columns that reads as a problem without a `[#<n>]`, an index past the end of the raw file,
two cells in one row citing the same index when that raw finding has no `single_fix` naming
the one change that fixes both, and a cell without a citation whose verdict or `ok`/`n/a`
reason defers it to another dimension or pass (DEFERRALS), since the specialist that wrote
a problem cell files it and the merge drops duplicates. It fails a raw finding whose
recommendation holds a ```diff fence that edits a file other than the finding's `file`,
unless the finding carries a `single_fix` naming why those edits are one change, because a
second defect folded into another finding's fix gets no anchor and no triage decision of its
own. Each problem names the agent to re-dispatch, and a cell or finding problem also names
where it is.

The ledger fails when a raw finding has no entry or more than one, an entry names a raw
finding that does not exist, a reason is outside the list above, a `kept` index is not a
kept finding, a refuted entry has no evidence, or a duplicate points at a kept finding in
another file or a line range that does not overlap its own. It also fails an entry that folds
a raw finding into a kept finding at a different line without a `single_fix` naming the one
change that resolves both, because two defects that need two fixes must stay two findings.

Pass `--dispatch` and `--tables-dir` for the file check, `--kept` and `--ledger` for the
ledger check, or all four. Exit 0 prints the counts (agents, exempt agents, table rows per
tables file; raw, merged, covered, dropped by reason) as JSON; exit 1 prints the problems;
exit 2 prints `{"error": ...}` when an input is unreadable or malformed.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import jsonio  # noqa: E402

DROP_REASONS = ("duplicate", "refuted", "out-of-scope", "linter-enforced")
TABLE_OWNERS = ("correctness", "resilience", "cross-repo", "conventions", "adversarial", "test-adequacy")
_AGENT_NAME = re.compile(r"^([a-z]+(?:-[a-z]+)*?)(?:-batch(\d+))?$")
_NO = r"no\b(?!,?\s+because\b)"
# a negative answer to a yes/no or "what catches it" question; "no, because ..." states the reason
_NEGATIVE = r"^(" + _NO + r"|(none|nothing|missing|never|unknown|unguarded|unbounded)\b|not\s+\w|could\s+not\b|cannot\b)"
_UNHANDLED = r"\b(unhandled|not\s+handled)\b"
PROBLEM_ANSWERS = {
    "What the layer above catches": _NEGATIVE,
    "What collides": _UNHANDLED,
    "What splits": _UNHANDLED,
    "New code does it?": _NEGATIVE,
    "Every waiter finishes?": _NEGATIVE,
    "Re-checked when the run starts?": _NEGATIVE,
    "Two at once? Guard (file:line)": r"^(no\s+guard|unguarded|none|nothing|missing)\b",
    "Caller-supplied size and its upper bound": r"\b(unbounded|no\s+(upper\s+)?(bound|limit|cap|max(imum)?))\b",
    "Still holds?": _NEGATIVE,
    "Pass, violation or n/a (file:line)": r"^(violation|fail(s|ed)?|missing)\b",
    "Verdict": r"^(wrong|misleading|partial)\b",
    "Test that pins it": _NEGATIVE,
    "Killing test": _NEGATIVE,
}
_DIMENSIONS = r"(correctness|safety|adversarial|cross-repo|conventions|observability|resilience|test-adequacy|test-coverage)"
_UNIT = r"(dimension|pass|specialist|lens|checklist)s?"
# "covered by tests" is a real reason, so a dimension named by a common word needs its unit
_ANOTHER = r"(the\s+)?(other\b|another\b|" + _DIMENSIONS + r"\b|(risk|scope|db|comments|tests)\s+" + _UNIT + r"\b)"
DEFERRALS = tuple(re.compile(pattern, re.I) for pattern in (
    r"\bquirk:[a-z]",
    r"\b(other|another|different|separate)\s+" + _UNIT + r"\b",
    r"\b(outside|out of|beyond)\s+((this|my|the)\s+" + _UNIT + r"|(this|my)\s+scope)\b",
    r"\bnot\s+(this|my|our)\s+" + _UNIT + r"\b",
    r"\b(defer(red|s)?|leave\s+it|left|belongs)\s+to\s+" + _ANOTHER,
    r"\b(covered|handled|owned|caught|checked|flagged|reported)\s+(by|in|under)\s+" + _ANOTHER,
))
_CITATION = re.compile(r"\[#\d+(?:\s*,\s*#\d+)*\]")
_CLEARED = re.compile(r"^(ok|n/a)\b")
_SEPARATOR = re.compile(r"^\|[\s|:-]*-[\s|:-]*$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*(\S*)")
_DIFF_PATH = re.compile(r"^\+\+\+ (?:b/)?(\S+)")


def _range(line):
    match = re.match(r"^\s*(\d+)(?:\s*-\s*(\d+))?\s*$", str(line))
    if not match:
        return None
    start = int(match.group(1))
    return start, int(match.group(2) or start)


def _load_json(path, label):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise ValueError("could not read %s: %s" % (label, exc))


def _findings(value, label):
    if isinstance(value, dict):
        value = value.get("findings")
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError("%s must be an array of finding objects" % label)
    return value


def load_raw(raw_dir):
    """Map each raw finding id (`<file stem>#<position>`) to the finding."""
    if not os.path.isdir(raw_dir):
        raise ValueError("raw findings directory %s does not exist" % raw_dir)
    raw = {}
    for name in sorted(os.listdir(raw_dir)):
        stem, extension = os.path.splitext(name)
        if extension != ".json":
            continue
        items = _findings(_load_json(os.path.join(raw_dir, name), "raw/" + name), "raw/" + name)
        for position, finding in enumerate(items):
            raw["%s#%d" % (stem, position)] = finding
    return raw


def load_dispatch(path):
    """Return the dispatch entries as (name, dimension, batch, exempt reason or None)."""
    manifest = jsonio.load_object(path, "dispatch.json")
    agents = manifest.get("agents")
    if not isinstance(agents, list) or any(not isinstance(agent, dict) for agent in agents):
        raise ValueError("dispatch.json must be {\"agents\": [objects]}")
    entries = []
    for index, agent in enumerate(agents):
        name = agent.get("name")
        match = _AGENT_NAME.match(name) if isinstance(name, str) else None
        if not match:
            raise ValueError("dispatch.json agent %d has name %r; use the dimension id without "
                             "`quirk:`, plus -batch<k> per batch" % (index, name))
        if match.group(1) == "risk":
            raise ValueError("dispatch.json lists risk, which returns a risk block and writes no files")
        exempt = agent.get("exempt")
        if exempt is not None and (not isinstance(exempt, str) or not exempt.strip()):
            raise ValueError("dispatch.json agent %s has an exempt value that is not a reason" % name)
        entries.append((name, match.group(1), match.group(2), exempt))
    return entries


def table_rows(text):
    """Count the body rows of every Markdown table in `text`."""
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    separators = sum(1 for line in lines if _SEPARATOR.match(line))
    return len(lines) - 2 * separators


def _cells(line):
    body = line.strip()[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", body)]


def parse_tables(text):
    """Return each Markdown table in `text` as (header cells, list of row cells)."""
    tables, block = [], []
    for line in text.splitlines() + [""]:
        if line.strip().startswith("|"):
            block.append(line)
            continue
        if len(block) >= 2 and _SEPARATOR.match(block[1].strip()):
            tables.append((_cells(block[0]), [_cells(row) for row in block[2:]]))
        block = []
    return tables


def _answer(cell):
    return _CITATION.sub("", cell).replace("`", "").replace("*", "").strip().lower()


def _cited(cell):
    return [int(index) for citation in _CITATION.findall(cell.replace("`", "")) for index in re.findall(r"\d+", citation)]


def _has_single_fix(finding):
    single_fix = finding.get("single_fix")
    return isinstance(single_fix, str) and bool(single_fix.strip())


def check_table_rows(name, text, findings):
    """Return the problems with each problem cell's `[#<n>]` citation in one tables file.

    `findings` is the agent's raw findings list, or None when it could not be read, which
    skips the checks that need it.
    """
    problems = []
    for header, rows in parse_tables(text):
        table = "tables/%s.md, %s table" % (name, header[0])
        for number, row in enumerate(rows, 1):
            label = "%s, row %d (%s)" % (table, number, row[0][:60] if row else "")
            row = row + [""] * (len(header) - len(row))
            citing = {}
            for column, cell in zip(header, row):
                where = "%s, %s" % (label, column)
                cited = _cited(cell)
                answer = _answer(cell)
                pattern = PROBLEM_ANSWERS.get(column)
                if not cell.replace("`", "").strip():
                    problems.append("%s is empty; write the answer, and [#<n>] after it if it is a problem" % where)
                elif cited:
                    for index in sorted(set(cited)):
                        citing.setdefault(index, []).append(column)
                elif pattern and re.search(pattern, answer):
                    problems.append("%s reads %r but cites no finding; add [#<n>] after it" % (where, cell))
                elif (pattern or _CLEARED.match(answer)) and any(p.search(answer) for p in DEFERRALS):
                    problems.append("%s defers to another dimension (%r); file the finding here and cite it, "
                                    "the merge drops duplicates" % (where, cell))
            for index, columns in sorted(citing.items()):
                if findings is not None and index >= len(findings):
                    problems.append("%s cites #%d, but raw/%s.json has %d findings" % (
                        label, index, name, len(findings)))
                elif len(columns) > 1 and findings is not None and not _has_single_fix(findings[index]):
                    problems.append("%s cites #%d in %s; file each problem as its own finding, or give #%d "
                                    "a single_fix naming the one change that fixes every cell citing it" % (
                                        label, index, " and ".join(columns), index))
    return problems


def _normal_path(path):
    path = path.strip()
    while path.startswith("./"):
        path = path[2:]
    return path


def diff_files(recommendation):
    """Return the files the ```diff fences in a recommendation edit, in order, without /dev/null."""
    files, fence, in_diff, previous = [], None, False, ""
    for line in str(recommendation or "").splitlines():
        stripped = line.strip()
        if fence is None:
            match = _FENCE.match(line)
            if match:
                fence, in_diff = match.group(1), match.group(2).lower() == "diff"
        elif stripped.startswith(fence) and not stripped.strip(fence[0]):
            fence, in_diff = None, False
        elif in_diff and previous.startswith("--- "):
            match = _DIFF_PATH.match(line)
            path = _normal_path(match.group(1)) if match else None
            if path and path != "/dev/null" and path not in files:
                files.append(path)
        previous = line
    return files


def check_raw_findings(name, findings):
    """Return the problems with each raw finding's recommendation in one raw file."""
    problems = []
    for index, finding in enumerate(findings):
        if _has_single_fix(finding):
            continue
        own = _normal_path(str(finding.get("file", "")))
        others = [path for path in diff_files(finding.get("recommendation")) if path != own]
        if others:
            problems.append("raw/%s.json finding #%d (%s) has a recommendation that also edits %s; file each "
                            "other defect as its own finding anchored where its change goes, or add a "
                            "single_fix naming why the edits are one change" % (
                                name, index, own, ", ".join(others)))
    return problems


def check_files(agents, raw_dir, tables_dir):
    """Return (problems, counts) for the files each dispatched agent owes."""
    problems = []
    counts = {"agents": len(agents), "exempt": [], "table_rows": {}}
    for name, dimension, batch, exempt in agents:
        if exempt is not None:
            counts["exempt"].append(name)
            continue
        redispatch = "re-dispatch %s%s" % (dimension, " for batch %s" % batch if batch else "")
        raw_path = os.path.join(raw_dir, name + ".json")
        findings = None
        if not os.path.isfile(raw_path):
            problems.append("%s wrote no raw/%s.json; %s" % (name, name, redispatch))
        else:
            try:
                findings = _findings(_load_json(raw_path, "raw/%s.json" % name), "raw/%s.json" % name)
            except ValueError as exc:
                problems.append("%s; %s" % (exc, redispatch))
            else:
                problems += ["%s; %s" % (problem, redispatch) for problem in check_raw_findings(name, findings)]
        if dimension not in TABLE_OWNERS:
            continue
        table_path = os.path.join(tables_dir, name + ".md")
        try:
            with open(table_path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            problems.append("%s wrote no tables/%s.md; %s" % (name, name, redispatch))
            continue
        if not text.strip():
            problems.append("tables/%s.md is empty; %s" % (name, redispatch))
            continue
        counts["table_rows"][name] = table_rows(text)
        problems += ["%s; %s" % (problem, redispatch) for problem in check_table_rows(name, text, findings)]
    return problems, counts


def check(raw, kept, ledger):
    """Return (problems, counts) for one ledger over the raw and kept findings."""
    entries = ledger.get("entries") if isinstance(ledger, dict) else None
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("merge-ledger.json must be {\"entries\": [objects]}")
    problems = []
    seen = set()
    counts = {"raw": len(raw), "merged": len(kept), "covered": 0,
              "dropped": {reason: 0 for reason in DROP_REASONS}}
    for index, entry in enumerate(entries):
        raw_id = entry.get("raw")
        label = "entry %d (%s)" % (index, raw_id)
        if raw_id not in raw:
            problems.append("%s names no raw finding" % label)
            continue
        if raw_id in seen:
            problems.append("%s accounts for a raw finding a second time" % label)
            continue
        seen.add(raw_id)
        reason = entry.get("reason")
        if reason is not None and reason not in DROP_REASONS:
            problems.append("%s has reason %r; drop reasons are %s" % (label, reason, ", ".join(DROP_REASONS)))
            continue
        if reason is None or reason == "duplicate":
            target = entry.get("kept")
            if isinstance(target, bool) or not isinstance(target, int) or not 0 <= target < len(kept):
                problems.append("%s points at kept finding %r, which does not exist" % (label, target))
                continue
            problem = _duplicate_problem(raw[raw_id], kept[target], target) if reason else None
            problem = problem or _single_fix_problem(raw[raw_id], kept[target], target, entry)
            if problem:
                problems.append("%s %s" % (label, problem))
                continue
        elif "kept" in entry:
            problems.append("%s is dropped as %s but also points at a kept finding" % (label, reason))
            continue
        if reason == "refuted" and (not isinstance(entry.get("evidence"), str) or not entry["evidence"].strip()):
            problems.append("%s is refuted without evidence" % label)
            continue
        if reason is None:
            counts["covered"] += 1
        else:
            counts["dropped"][reason] += 1
    for raw_id in sorted(set(raw) - seen):
        problems.append("raw finding %s is missing from the ledger" % raw_id)
    return problems, counts


def _duplicate_problem(finding, target, index):
    if finding.get("file") != target.get("file"):
        return "is a duplicate of kept finding %d in another file (%s, not %s)" % (
            index, target.get("file"), finding.get("file"))
    own, other = _range(finding.get("line")), _range(target.get("line"))
    if own is None or other is None:
        return "is a duplicate of kept finding %d, but a line is not a number or start-end range" % index
    if own[0] > other[1] or other[0] > own[1]:
        return "is a duplicate of kept finding %d at lines %s, which do not overlap %s" % (
            index, target.get("line"), finding.get("line"))
    return None


def _single_fix_problem(finding, target, index, entry):
    own, other = _range(finding.get("line")), _range(target.get("line"))
    if own is not None and own == other:
        return None
    if own is None and str(finding.get("line")).strip() == str(target.get("line")).strip():
        return None
    single_fix = entry.get("single_fix")
    if isinstance(single_fix, str) and single_fix.strip():
        return None
    return ("folds line %s into kept finding %d at line %s without a single_fix naming the one change "
            "that resolves both; keep it as its own finding if it needs a fix of its own" % (
                finding.get("line"), index, target.get("line")))



_SEV_ORDER = {"Nit": 0, "Should fix": 1, "Must fix": 2}


def _one_line_cap(text, cap):
    line = " ".join(str(text or "").split())
    return line if len(line) <= cap else line[:cap - 1].rstrip() + "…"


def _norm_line_str(val):
    match = re.search(r"[1-9]\d*(?:\s*-\s*[1-9]\d*)?", str(val or ""))
    if not match:
        return "1"
    span_str = re.sub(r"\s*-\s*", "-", match.group(0))
    parts = span_str.split("-")
    if len(parts) == 2 and int(parts[1]) < int(parts[0]):
        return parts[0]
    return span_str


def _norm_sev_str(val):
    if val in _SEV_ORDER:
        return val
    text = str(val or "").strip().lower()
    if "must" in text or "high" in text or "crit" in text or "block" in text:
        return "Must fix"
    if "nit" in text or "low" in text or "minor" in text:
        return "Nit"
    return "Should fix"


def materialize_kept(raw, ledger_doc):
    """Build the `merged-findings.json` list mechanically from `raw` and `merge-ledger.json`."""
    if not isinstance(ledger_doc, dict):
        raise ValueError("merge-ledger.json must be {\"entries\": [objects]}")
    overrides = ledger_doc.get("overrides") if isinstance(ledger_doc.get("overrides"), dict) else {}
    if isinstance(ledger_doc.get("groups"), list) and "entries" not in ledger_doc:
        conv_entries = []
        seen_r = set()
        for d_item in ledger_doc.get("drops") or []:
            if isinstance(d_item, dict) and d_item.get("raw") in raw and d_item["raw"] not in seen_r:
                r_id = d_item["raw"]
                seen_r.add(r_id)
                reason = d_item.get("reason") if d_item.get("reason") in DROP_REASONS else "refuted"
                ent = {"raw": r_id, "reason": reason}
                if reason == "refuted":
                    ent["evidence"] = str(d_item.get("evidence") or "Refuted against source at refs.head.")
                conv_entries.append(ent)
        k_idx = 0
        for g_item in ledger_doc.get("groups") or []:
            if not isinstance(g_item, dict):
                continue
            prim = str(g_item.get("primary") or g_item.get("keep") or "").strip()
            dups = [str(x).strip() for x in (g_item.get("duplicates") or g_item.get("with") or []) if str(x).strip()]
            valid_ids = [r for r in ([prim] + dups) if r in raw and r not in seen_r]
            if not valid_ids:
                continue
            seen_r.add(valid_ids[0])
            conv_entries.append({"raw": valid_ids[0], "kept": k_idx})
            for dup_id in valid_ids[1:]:
                if dup_id not in seen_r:
                    seen_r.add(dup_id)
                    conv_entries.append({"raw": dup_id, "reason": "duplicate", "kept": k_idx})
            ov = {f: g_item[f] for f in ("severity", "file", "line", "title", "impact", "fix_md", "issue", "recommendation")
                  if g_item.get(f) is not None and str(g_item.get(f)).strip()}
            if ov:
                overrides[str(k_idx)] = ov
            k_idx += 1
        ledger_doc["entries"] = conv_entries
        ledger_doc["overrides"] = overrides

    entries = ledger_doc.get("entries")
    if not isinstance(entries, list):
        raise ValueError("merge-ledger.json must be {\"entries\": [objects]}")
    # Ensure any omitted raw finding becomes its own singleton kept finding during --materialize
    covered_raws = {e.get("raw") for e in entries if isinstance(e, dict) and e.get("raw") in raw}
    next_k = max([e.get("kept", -1) for e in entries if isinstance(e, dict) and isinstance(e.get("kept"), int)] + [-1]) + 1
    for r_id in sorted(raw):
        if r_id not in covered_raws:
            entries.append({"raw": r_id, "kept": next_k})
            next_k += 1

    by_kept = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        target = entry.get("kept")
        reason = entry.get("reason")
        if isinstance(target, int) and not isinstance(target, bool) and (reason is None or reason == "duplicate"):
            by_kept.setdefault(target, []).append(entry)
    if not by_kept:
        return []
    split_groups = []
    for k in sorted(by_kept):
        group = by_kept[k]
        primaries = [e for e in group if e.get("reason") is None and e.get("raw") in raw]
        all_valid = [e for e in group if e.get("raw") in raw]
        if not all_valid:
            continue
        anchor_entry = primaries[0] if primaries else all_valid[0]
        anchor_rf = dict(raw[anchor_entry["raw"]])
        ov = overrides.get(str(k)) if isinstance(overrides.get(str(k)), dict) else {}
        if "file" in ov and ov["file"]:
            anchor_rf["file"] = ov["file"]
        if "line" in ov and ov["line"]:
            anchor_rf["line"] = ov["line"]
        anchor_rf["line"] = _norm_line_str(anchor_rf.get("line"))
        main_group = []
        overflow_clusters = []
        for e in all_valid:
            rf = dict(raw[e["raw"]], line=_norm_line_str(raw[e["raw"]].get("line")))
            if e is anchor_entry:
                main_group.append(e)
            elif rf.get("file") != anchor_rf.get("file") or _duplicate_problem(rf, anchor_rf, 0) is not None:
                placed = False
                for cl_anchor, cl_entries in overflow_clusters:
                    if rf.get("file") == cl_anchor.get("file") and _duplicate_problem(rf, cl_anchor, 0) is None:
                        cl_entries.append(e)
                        s1, s2 = _range(cl_anchor["line"]), _range(rf["line"])
                        if s1 and s2:
                            mn, mx = min(s1[0], s2[0]), max(s1[1], s2[1])
                            cl_anchor["line"] = str(mn) if mn == mx else "%d-%d" % (mn, mx)
                        placed = True
                        break
                if not placed:
                    overflow_clusters.append((dict(rf), [e]))
            else:
                main_group.append(e)
        split_groups.append((k, main_group, ov))
        for _, o_group in overflow_clusters:
            o_group[0].pop("reason", None)
            o_group[0].pop("single_fix", None)
            for oe in o_group[1:]:
                oe["reason"] = "duplicate"
                oe.pop("single_fix", None)
            split_groups.append((None, o_group, None))

    kept = []
    for _orig_k, group, ov in split_groups:
        primaries = [e for e in group if e.get("reason") is None and e.get("raw") in raw]
        anchor_entry = primaries[0] if primaries else group[0]
        base = dict(raw[anchor_entry["raw"]])
        base["line"] = _norm_line_str(base.get("line"))
        dims = set()
        assumptions = []
        best_sev = _norm_sev_str(base.get("severity"))
        sub_notes = []
        seen_titles = {str(base.get("title") or "").strip().lower()}
        span = _range(base.get("line"))
        min_l, max_l = (span[0], span[1]) if span else (None, None)
        for e in group:
            rf = raw[e["raw"]]
            if isinstance(rf.get("dimension"), str) and rf["dimension"].strip():
                dims.add(rf["dimension"].strip())
            for d in rf.get("dimensions") or []:
                if isinstance(d, str) and d.strip():
                    dims.add(d.strip())
            for a in rf.get("assumptions") or []:
                if isinstance(a, str) and a.strip() and a not in assumptions:
                    assumptions.append(a)
            r_sev = _norm_sev_str(e.get("severity") or rf.get("severity"))
            if _SEV_ORDER.get(r_sev, 0) > _SEV_ORDER.get(best_sev, 0):
                best_sev = r_sev
            r_span = _range(_norm_line_str(rf.get("line")))
            if r_span and min_l is not None:
                min_l = min(min_l, r_span[0])
                max_l = max(max_l, r_span[1])
            t = str(rf.get("title") or "").strip()
            if t and t.lower() not in seen_titles:
                seen_titles.add(t.lower())
                imp = str(rf.get("impact") or rf.get("issue") or "").split("\n")[0].strip()
                sub_notes.append("- **%s:** %s" % (t, imp[:220]))
        sorted_dims = sorted(dims) if dims else [base.get("dimension", "correctness")]
        base["dimension"] = sorted_dims[0]
        base["dimensions"] = sorted_dims
        base["severity"] = best_sev
        base["assumptions"] = assumptions
        ov = ov if isinstance(ov, dict) else {}
        for field in ("severity", "file", "line", "title", "impact", "fix_md", "issue", "recommendation",
                      "body_md", "recommendation_md", "verification_status", "what_would_confirm", "verified"):
            if field in anchor_entry and anchor_entry[field] is not None:
                base[field] = anchor_entry[field]
            if field in ov and ov[field] is not None:
                base[field] = ov[field]
        base["severity"] = _norm_sev_str(base.get("severity"))
        if min_l is not None and max_l is not None:
            base["line"] = str(min_l) if min_l == max_l else "%d-%d" % (min_l, max_l)
        else:
            base["line"] = _norm_line_str(base.get("line"))
        for key, cap, fb in (("title", 80, "issue"), ("impact", 200, "issue"), ("fix_md", 160, "recommendation")):
            val = base.get(key)
            if not isinstance(val, str) or not val.strip():
                raw_fb = str(base.get(fb) or "").split("\n```")[0]
                first_sent = re.split(r"(?<=[.!?])\s+", " ".join(raw_fb.split()))[0]
                base[key] = _one_line_cap(first_sent or base.get("file") or "Finding", cap)
            else:
                base[key] = _one_line_cap(val, cap)
        if not isinstance(base.get("body_md"), str) or not base["body_md"].strip():
            base["body_md"] = base.get("issue", "")
        if sub_notes:
            extra = "\n\n" + "\n".join(sub_notes[:5])
            base["body_md"] = base["body_md"].rstrip() + extra
            base["issue"] = (base.get("issue") or "").rstrip() + extra
        if not isinstance(base.get("recommendation_md"), str) or not base["recommendation_md"].strip():
            base["recommendation_md"] = base.get("recommendation", "")
        new_idx = len(kept)
        kept.append(base)
        for e in group:
            e["kept"] = new_idx
            rf = raw.get(e.get("raw"))
            if not rf:
                continue
            if e.get("reason") == "duplicate" and _duplicate_problem(rf, base, new_idx) is not None:
                e.pop("reason", None)
                e["single_fix"] = e.get("single_fix") or base.get("fix_md") or "resolved by the same change"
            elif e.get("reason") is None and _single_fix_problem(rf, base, new_idx, e) is not None:
                e["single_fix"] = base.get("fix_md") or "resolved by the same change"
    return kept

def _pair(first, second, first_flag, second_flag):
    if (first is None) != (second is None):
        raise ValueError("%s and %s go together" % (first_flag, second_flag))
    return first is not None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check each specialist's files and the merge ledger against the raw findings.")
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--dispatch")
    parser.add_argument("--tables-dir")
    parser.add_argument("--kept")
    parser.add_argument("--ledger")
    parser.add_argument("--materialize", action="store_true",
                        help="build --kept (merged-findings.json) mechanically from --raw-dir and --ledger before checking")
    args = parser.parse_args(argv)
    problems, counts = [], {}
    try:
        files_check = _pair(args.dispatch, args.tables_dir, "--dispatch", "--tables-dir")
        ledger_check = _pair(args.kept, args.ledger, "--kept", "--ledger")
        if not files_check and not ledger_check:
            raise ValueError("pass --dispatch and --tables-dir, --kept and --ledger, or all four")
        if files_check:
            problems, counts = check_files(load_dispatch(args.dispatch), args.raw_dir, args.tables_dir)
        if ledger_check:
            raw = load_raw(args.raw_dir)
            ledger = jsonio.load_object(args.ledger, "merge-ledger.json")
            if args.materialize:
                kept = materialize_kept(raw, ledger)
                jsonio.write_json(args.kept, kept)
                jsonio.write_json(args.ledger, ledger)
            else:
                kept = _findings(_load_json(args.kept, "merged findings"), "merged findings")
            ledger_problems, ledger_counts = check(raw, kept, ledger)
            problems += ledger_problems
            counts.update(ledger_counts)
    except (TypeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    if problems:
        print(json.dumps({"ok": False, "problems": problems}, indent=2))
        return 1
    print(json.dumps(dict(counts, ok=True), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
