#!/usr/bin/env python3
"""Render a structured combined-review report as HTML and/or Markdown."""

import argparse
import copy
import hashlib
import html
import json
import os
import pathlib
import re
import sys
import tempfile
import webbrowser

import highlight
from forge import change_label
from md_render import render_inline, render_markdown


SEVERITY_ORDER = {"Must fix": 0, "Should fix": 1, "Nit": 2}
SEVERITY_SLUG = {"Must fix": "must", "Should fix": "should", "Nit": "nit"}
UNSAFE_LINE = re.compile(r"[\r\n\u2028\u2029]")
_TOP_FIELDS = {"schema_version", "meta", "run", "mutation_probe", "risk", "findings", "recommended_order", "assumptions", "process_notes", "memory"}
_META_FIELDS = {"target", "forge", "number", "branch", "project", "ticket", "head_sha", "change_state", "title", "standfirst_md", "verdict", "storage_key", "seat", "repo_root", "source_branch", "web_url"}
_RUN_FIELDS = {"dimensions_run", "dimensions_skipped", "diff_size", "coverage", "guidance",
               "clean_notes", "notes_md", "source_access", "source_access_reason",
               "mutation_consent", "incomplete", "dimensions_failed", "models", "verification",
               "excluded_generated", "policy_sources", "severity_floor", "deep", "since"}
DEFAULT_SEVERITY_FLOOR = "Should fix"
_INCOMPLETE_OK_VERDICTS = {"fix, then merge", "request changes", "incomplete review"}
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
DISPOSITIONS = {
    "author": [("fix", "Will fix"), ("later", "Fix later"),
               ("detail", "Needs detail"), ("ignore", "Ignore"),
               ("none", "Undecided")],
    "reviewer": [("fix", "Blocking"), ("later", "Non-blocking"),
                 ("detail", "Question"), ("ignore", "Drop"),
                 ("none", "Undecided")],
}
_MEMORY_STATES = {"new", "carried", "answered", "restored-decision",
                  "re-found-after-resolution", "possible-regression"}
_MEMORY_MATCHES = {"exact", "candidate", None}
_MEMORY_FIELDS = {"fingerprint", "dimension", "anchor_hash", "state", "match",
                  "disposition", "note", "suppress_post", "thread", "candidates",
                  "human_context"}
_SNAPSHOT_FIELDS = {"schemaVersion", "target_key", "identity", "seat", "base_sha",
                    "head_sha", "dimensions", "guidance_hash", "started_at",
                    "findings", "discussions", "discussions_available", "warnings",
                    "invalidation_reason", "file_hashes", "unchanged_files"}
_FINDING_FIELDS = {"id", "dedup_key", "severity", "dimension", "dimensions", "file", "line", "issue", "recommendation", "verified", "assumptions", "title", "impact", "fix_md", "area", "evidence", "body_md", "aside_md", "recommendation_md", "anchor_side", "memory", "verification_status", "repro", "what_would_confirm"}


def severity_floor(prepared):
    """The lowest severity allowed to post for this report (run.severity_floor, default Should fix)."""
    run = prepared.get("run") if isinstance(prepared.get("run"), dict) else {}
    return run.get("severity_floor") or DEFAULT_SEVERITY_FLOOR


def below_floor(finding, floor):
    """Whether `finding` is less severe than `floor` and so must never be posted."""
    return SEVERITY_ORDER[finding["severity"]] > SEVERITY_ORDER[floor]


def slugify(name):
    """Return a lowercase, filesystem-safe slug capped at 48 characters."""
    value = re.sub(r"[^a-z0-9._-]+", "-", str(name).lower())
    return value.strip("-._")[:48]


def target_slug(meta):
    """Derive the stable output slug for a change request, branch, or local target."""
    target = meta.get("target")
    if target == "change":
        return str(meta.get("number", ""))
    if target == "branch":
        branch = meta.get("branch", "")
        digest = hashlib.sha256(branch.encode("utf-8", "backslashreplace")).hexdigest()[:6]
        return "%s-%s" % (slugify(branch) or "branch", digest)
    if target == "local":
        return "local"
    return ""


def derive_title(issue):
    """Derive a compact finding title from the first punctuated issue clause."""
    value = "" if issue is None else str(issue)
    value = re.split(r"(?<=[.;:])\s+", value.strip(), maxsplit=1)[0]
    value = re.sub(r"\s+", " ", value).rstrip(".;:")
    if not value:
        return "Untitled finding"
    if len(value) > 80:
        cut = value.rfind(" ", 0, 77)
        if cut < 1:
            cut = 77
        value = value[:cut].rstrip() + "…"
    return value


def normalize_finding(finding, warnings=None):
    """Map a core or enriched finding onto the renderer's complete shape."""
    warnings = warnings if warnings is not None else []
    value = copy.deepcopy(finding)
    issue = value.get("issue")
    body = value.get("body_md")
    if "title" not in value or value.get("title") is None:
        value["title"] = derive_title(issue if issue is not None else body)
    else:
        value["title"] = str(value["title"])

    if "dimensions" in value:
        dimensions = value["dimensions"]
    elif isinstance(value.get("dimension"), str):
        dimensions = [value["dimension"]]
    else:
        dimensions = ["unknown"]
        warnings.append("Finding at %s:%s has no dimension; using unknown." %
                        (value.get("file", "?"), value.get("line", "?")))
    value["dimensions"] = list(dimensions)
    value["file"] = str(value["file"]).strip()
    value["line"] = str(value["line"]).strip()
    if "impact" in value:
        if isinstance(value["impact"], str) and value["impact"].strip():
            value["impact"] = " ".join(value["impact"].split())
        else:
            value.pop("impact")
            warnings.append("Finding at %s:%s has a non-text impact; omitting it." %
                            (value.get("file", "?"), value.get("line", "?")))
    if "fix_md" in value:
        if isinstance(value["fix_md"], str) and value["fix_md"].strip():
            value["fix_md"] = " ".join(value["fix_md"].split())
        else:
            value.pop("fix_md")
            warnings.append("Finding at %s:%s has a non-text fix_md; omitting it." %
                            (value.get("file", "?"), value.get("line", "?")))
    if value.get("body_md") is None and issue is not None:
        value["body_md"] = str(issue)
    if value.get("recommendation_md") is None and value.get("recommendation") is not None:
        value["recommendation_md"] = str(value["recommendation"])
    return value


def rank_findings(findings):
    """Stable-sort by severity and assign deterministic F1..Fn identifiers."""
    ranked = sorted((copy.deepcopy(item) for item in findings),
                    key=lambda item: SEVERITY_ORDER[item["severity"]])
    for index, finding in enumerate(ranked, 1):
        finding["id"] = "F%d" % index
    return ranked


def finding_digest(findings):
    """Return a short digest over ranked finding identities and their substance.

    Substance is part of the identity on purpose: a re-review that surfaces a
    different problem at the same file, line, and severity must not inherit the
    previous finding's disposition and note under the same id.
    """
    source = "\n".join("%s\x1f%s\x1f%s\x1f%s\x1f%s\x1f%s\x1f%s\x1f%s" %
                       (item["severity"], item["file"], item["line"],
                        item.get("title") or "", item.get("body_md") or "",
                        item.get("recommendation_md") or "",
                        item.get("impact") or "", item.get("fix_md") or "")
                       for item in rank_findings(findings))
    return hashlib.sha256(source.encode("utf-8", "backslashreplace")).hexdigest()[:10]


def storage_key(meta, findings):
    """Return the authored storage key or a target-and-finding-set key."""
    if isinstance(meta.get("storage_key"), str) and meta["storage_key"]:
        return meta["storage_key"]
    if meta.get("seat", "author") == "reviewer":
        return "quirk-review-%s-reviewer-%s" % (target_slug(meta), finding_digest(findings))
    return "quirk-review-%s-%s" % (target_slug(meta), finding_digest(findings))


def replace_slot(template, name, replacement):
    """Replace exactly one complete HTML-comment slot, markers included."""
    opening = "<!-- slot:%s -->" % name
    closing = "<!-- /slot:%s -->" % name
    if template.count(opening) != 1 or template.count(closing) != 1:
        raise ValueError("template slot %s must appear exactly once" % name)
    start = template.index(opening)
    end = template.index(closing)
    if end < start:
        raise ValueError("template slot %s markers are out of order" % name)
    end += len(closing)
    return template[:start] + replacement + template[end:]


_HANDOFF_UNSAFE = re.compile(r"[\r\u2028\u2029]")
_LINE_RE = re.compile(r"[1-9][0-9]*(?:-[0-9]+)?")


def _handoff_safe(value, label):
    """Reject characters that a triage paste cannot carry, since the page copies this text into it."""
    if _HANDOFF_UNSAFE.search(value):
        raise ValueError("%s contains a carriage return or Unicode line separator" % label)


def _line_safe(value, label):
    if UNSAFE_LINE.search(value):
        raise ValueError("%s contains a line-breaking character" % label)


_POSTED_TEXT_CAPS = {"impact": 200, "fix_md": 160}


def _validate_posted_text(raw, label):
    """Reject multi-line or over-cap impact/fix_md, measured on the raw value before whitespace collapse."""
    for field, cap in _POSTED_TEXT_CAPS.items():
        value = raw.get(field)
        if not isinstance(value, str):
            continue
        if UNSAFE_LINE.search(value):
            raise ValueError("%s %s contains a line-breaking character" % (label, field))
        if len(value) > cap:
            raise ValueError("%s %s exceeds %d characters" % (label, field, cap))


def _positive_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and re.match(r"^[0-9]+$", value.strip()):
        number = int(value.strip())
        return number if number > 0 else None
    return None
def _validate_thread(value, label):
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError("%s must be an object or null" % label)
    for key in ("discussion_id", "note_id", "url"):
        if key in value and value[key] is not None and not isinstance(value[key], (str, int)):
            raise ValueError("%s.%s must be a string or integer" % (label, key))
    if "resolved" in value and not isinstance(value["resolved"], bool):
        raise ValueError("%s.resolved must be a boolean" % label)
    replies = value.get("replies", [])
    if not isinstance(replies, list):
        raise ValueError("%s.replies must be a list" % label)
    for index, reply in enumerate(replies):
        if not isinstance(reply, dict):
            raise ValueError("%s.replies[%d] must be an object" % (label, index))
        if not isinstance(reply.get("author", ""), str) or not isinstance(reply.get("body", ""), str):
            raise ValueError("%s.replies[%d] author/body must be strings" % (label, index))


def _validate_context_list(value, label, discussion_entries=False):
    if not isinstance(value, list):
        raise ValueError("%s must be a list" % label)
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError("%s[%d] must be an object" % (label, index))
        for key in ("fingerprint", "dimension", "state", "match", "disposition",
                    "note", "title", "body", "body_md", "recommendation",
                    "recommendation_md", "file", "line", "author", "summary", "url"):
            if key in item and item[key] is not None and not isinstance(item[key], (str, int)):
                raise ValueError("%s[%d].%s must be text" % (label, index, key))
        if item.get("state") is not None and item["state"] not in _MEMORY_STATES:
            raise ValueError("%s[%d].state is unknown" % (label, index))
        if item.get("match") is not None and item["match"] not in _MEMORY_MATCHES:
            raise ValueError("%s[%d].match is unknown" % (label, index))
        _validate_thread(item.get("thread"), "%s[%d].thread" % (label, index))
        if discussion_entries:
            if not isinstance(item.get("note_id"), int) or isinstance(item.get("note_id"), bool):
                raise ValueError("%s[%d].note_id must be an integer" % (label, index))
            if not isinstance(item.get("discussion_id"), str) or not item["discussion_id"]:
                raise ValueError("%s[%d].discussion_id must be a non-empty string" % (label, index))
            if not isinstance(item.get("resolved"), bool):
                raise ValueError("%s[%d].resolved must be a boolean" % (label, index))
            if "own" in item and not isinstance(item["own"], bool):
                raise ValueError("%s[%d].own must be a boolean" % (label, index))


def _validate_memory_finding(memory, label):
    if not isinstance(memory, dict):
        raise ValueError("%s must be an object" % label)
    missing = _MEMORY_FIELDS - set(memory)
    if missing:
        raise ValueError("%s is missing %s" % (label, ", ".join(sorted(missing))))
    for key in ("fingerprint", "anchor_hash"):
        value = memory[key]
        if value is not None and (not isinstance(value, str) or not _HEX64_RE.match(value)):
            raise ValueError("%s.%s must be a lowercase 64-character hash or null" % (label, key))
    if not isinstance(memory["dimension"], str):
        raise ValueError("%s.dimension must be a string" % label)
    if memory["state"] not in _MEMORY_STATES:
        raise ValueError("%s.state is unknown" % label)
    if memory["match"] not in _MEMORY_MATCHES:
        raise ValueError("%s.match is unknown" % label)
    if memory["disposition"] not in ("fix", "later", "detail", "ignore", "none"):
        raise ValueError("%s.disposition is unknown" % label)
    if not isinstance(memory["note"], str):
        raise ValueError("%s.note must be a string" % label)
    if not isinstance(memory["suppress_post"], bool):
        raise ValueError("%s.suppress_post must be a boolean" % label)
    _validate_thread(memory["thread"], "%s.thread" % label)
    _validate_context_list(memory["candidates"], "%s.candidates" % label)
    _validate_context_list(memory["human_context"], "%s.human_context" % label,
                           discussion_entries=True)


def _validate_memory_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError("memory.snapshot must be an object")
    missing = _SNAPSHOT_FIELDS - set(snapshot)
    if missing:
        raise ValueError("memory.snapshot is missing %s" % ", ".join(sorted(missing)))
    if snapshot["schemaVersion"] != 1:
        raise ValueError("memory.snapshot.schemaVersion must be 1")
    if not isinstance(snapshot["target_key"], str) or not isinstance(snapshot["identity"], dict):
        raise ValueError("memory.snapshot target_key/identity are invalid")
    if snapshot["seat"] not in ("author", "reviewer"):
        raise ValueError("memory.snapshot.seat is invalid")
    for key in ("base_sha", "head_sha", "guidance_hash", "invalidation_reason"):
        if snapshot[key] is not None and not isinstance(snapshot[key], str):
            raise ValueError("memory.snapshot.%s must be a string or null" % key)
    if not isinstance(snapshot["started_at"], (int, float)) or isinstance(snapshot["started_at"], bool):
        raise ValueError("memory.snapshot.started_at must be a number")
    if not isinstance(snapshot["dimensions"], list) or any(not isinstance(item, str) for item in snapshot["dimensions"]):
        raise ValueError("memory.snapshot.dimensions must be a list of strings")
    if not isinstance(snapshot["findings"], list) or any(not isinstance(item, dict) for item in snapshot["findings"]):
        raise ValueError("memory.snapshot.findings must be a list of objects")
    if not isinstance(snapshot["discussions"], list) or any(not isinstance(item, dict) for item in snapshot["discussions"]):
        raise ValueError("memory.snapshot.discussions must be a list of objects")
    if not isinstance(snapshot["discussions_available"], bool):
        raise ValueError("memory.snapshot.discussions_available must be a boolean")
    if not isinstance(snapshot["warnings"], list) or any(not isinstance(item, str) for item in snapshot["warnings"]):
        raise ValueError("memory.snapshot.warnings must be a list of strings")
    if not isinstance(snapshot["file_hashes"], dict) or any(not isinstance(key, str) or not isinstance(value, str)
                                                            for key, value in snapshot["file_hashes"].items()):
        raise ValueError("memory.snapshot.file_hashes must map strings to strings")
    if not isinstance(snapshot["unchanged_files"], list) or any(not isinstance(item, str) for item in snapshot["unchanged_files"]):
        raise ValueError("memory.snapshot.unchanged_files must be a list of strings")


def _validate_memory(memory):
    if not isinstance(memory, dict):
        raise ValueError("memory must be an object")
    if set(("snapshot", "appears_fixed", "warnings")) - set(memory):
        raise ValueError("memory must contain snapshot, appears_fixed, and warnings")
    _validate_memory_snapshot(memory["snapshot"])
    if not isinstance(memory["warnings"], list) or any(not isinstance(item, str) for item in memory["warnings"]):
        raise ValueError("memory.warnings must be a list of strings")
    if not isinstance(memory["appears_fixed"], list):
        raise ValueError("memory.appears_fixed must be a list")
    for index, item in enumerate(memory["appears_fixed"]):
        if not isinstance(item, dict):
            raise ValueError("memory.appears_fixed[%d] must be an object" % index)
        for key in ("fingerprint", "dimension", "state", "match", "disposition",
                    "note", "title", "body", "recommendation", "file", "line",
                    "author", "summary", "url"):
            if key in item and item[key] is not None and not isinstance(item[key], (str, int)):
                raise ValueError("memory.appears_fixed[%d].%s must be text" % (index, key))
        _validate_thread(item.get("thread"), "memory.appears_fixed[%d].thread" % index)



def _list_of_strings(value, label):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("%s must be a list of strings" % label)


def _warn_unknown(mapping, allowed, label, warnings):
    if not isinstance(mapping, dict):
        return
    for key in sorted(set(mapping) - allowed):
        warnings.append("Unknown %s field ignored: %s" % (label, key))


def _validate_deep_hunk_fields(deep):
    """Reject malformed per-hunk coverage fields on deep areas and the deep summaries."""
    for area in deep.get("areas") or []:
        if "hunks" in area:
            hunks = area["hunks"]
            if not isinstance(hunks, list) or any(
                    not isinstance(hunk, dict)
                    or any(not isinstance(hunk.get(key), str) for key in ("id", "file", "header"))
                    for hunk in hunks):
                raise ValueError("run.deep.areas.hunks must be a list of objects with string id, file, and header")
        for key in ("examined", "hunkless_files"):
            if key in area:
                _list_of_strings(area[key], "run.deep.areas.%s" % key)
        if "priority" in area and (type(area["priority"]) is not int):
            raise ValueError("run.deep.areas.priority must be an integer")
    if "unexamined" in deep:
        unexamined = deep["unexamined"]
        if not isinstance(unexamined, dict):
            raise ValueError("run.deep.unexamined must map area ids to lists of hunk ids")
        for identifier, ids in unexamined.items():
            _list_of_strings(ids, "run.deep.unexamined")
    if "hunk_coverage" in deep and not isinstance(deep["hunk_coverage"], dict):
        raise ValueError("run.deep.hunk_coverage must be an object")


def _validate_contract_run(run, meta, warnings):
    """Validate the schema_version 1 run keys and enforce the incomplete-report rule."""
    if "incomplete" in run and not isinstance(run["incomplete"], bool):
        raise ValueError("run.incomplete must be true or false")
    for key in ("dimensions_failed", "excluded_generated"):
        if key in run:
            _list_of_strings(run[key], "run.%s" % key)
    if "severity_floor" in run and run["severity_floor"] not in SEVERITY_ORDER:
        raise ValueError("run.severity_floor must be Must fix, Should fix, or Nit")
    if "models" in run and (not isinstance(run["models"], dict) or
                            any(not isinstance(v, str) for v in run["models"].values())):
        raise ValueError("run.models must map lens ids to model names")
    if "verification" in run and not isinstance(run["verification"], dict):
        raise ValueError("run.verification must be an object")
    if "policy_sources" in run and (not isinstance(run["policy_sources"], list) or
                                    any(not isinstance(v, dict) for v in run["policy_sources"])):
        raise ValueError("run.policy_sources must be a list of objects")
    if "since" in run:
        since = run["since"]
        if (not isinstance(since, dict) or not isinstance(since.get("ref"), str) or not since["ref"].strip()
                or not isinstance(since.get("sha"), str) or not _SHA_RE.match(since["sha"])):
            raise ValueError("run.since must be an object with a non-empty ref and a 40-character lowercase hex sha")
    if "deep" in run:
        deep = run["deep"]
        if not isinstance(deep, dict):
            raise ValueError("run.deep must be an object")
        if "areas" in deep and (not isinstance(deep["areas"], list) or
                                any(not isinstance(area, dict) for area in deep["areas"])):
            raise ValueError("run.deep.areas must be a list of objects")
        if "unreached_areas" in deep:
            _list_of_strings(deep["unreached_areas"], "run.deep.unreached_areas")
        _validate_deep_hunk_fields(deep)
        unreached = list(deep.get("unreached_areas") or [])
        for area in deep.get("areas") or []:
            status = area.get("status")
            if status not in (None, "pending", "unreached", "completed", "read_only_degraded"):
                raise ValueError("run.deep area status has an unknown value")
            if status in ("pending", "unreached"):
                identifier = area.get("id")
                if not isinstance(identifier, str) or not identifier.strip():
                    raise ValueError("unfinished deep areas require an id")
                if identifier not in unreached:
                    unreached.append(identifier)
        if unreached:
            deep["unreached_areas"] = unreached
        failures = deep.get("checker_failures") or {}
        if not isinstance(failures, dict) or any(
                not isinstance(key, str) or not isinstance(reason, str) or not reason.strip()
                for key, reason in failures.items()):
            raise ValueError("run.deep.checker_failures must map ids to failure reasons")
        if failures:
            run["incomplete"] = True
            meta["verdict"] = "Incomplete review"
        if "checked_and_dropped" in deep:
            dropped = deep["checked_and_dropped"]
            if not isinstance(dropped, list) or any(
                    not isinstance(item, dict) or
                    any(not isinstance(item.get(key), str)
                        for key in ("file", "line", "title", "reason"))
                    for item in dropped):
                raise ValueError("run.deep.checked_and_dropped must contain objects with "
                                 "string file, line, title, and reason")
        if deep.get("unreached_areas"):
            run["incomplete"] = True
            meta["verdict"] = "Incomplete review"
    if run.get("dimensions_failed") and not run.get("incomplete"):
        warnings.append("run.dimensions_failed is non-empty; marking the report incomplete.")
        run["incomplete"] = True
    if run.get("incomplete") and meta["verdict"].strip().lower() not in _INCOMPLETE_OK_VERDICTS:
        warnings.append("Incomplete reports can only carry a blocking verdict; showing \"Incomplete review\".")
        meta["verdict"] = "Incomplete review"


def _prepare_report(report):
    if not isinstance(report, dict):
        raise ValueError("report JSON must be an object")
    prepared = copy.deepcopy(report)
    warnings = []
    _warn_unknown(prepared, _TOP_FIELDS, "top-level", warnings)
    meta = prepared.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("meta must be an object")
    _warn_unknown(meta, _META_FIELDS, "meta", warnings)
    target = meta.get("target")
    if target not in ("change", "branch", "local"):
        raise ValueError("meta.target must be change, branch, or local")
    seat = meta.get("seat", "author")
    if seat not in ("author", "reviewer"):
        raise ValueError("meta.seat must be author or reviewer")
    meta["seat"] = seat
    if seat == "reviewer" and target != "change":
        raise ValueError("reviewer-seat reports must target a change request")
    if seat == "reviewer" and (not isinstance(meta.get("project"), str) or
                               not meta["project"].strip()):
        raise ValueError("reviewer-seat reports require meta.project")
    if seat == "reviewer" and (not isinstance(meta.get("head_sha"), str) or
                               not _SHA_RE.match(meta["head_sha"])):
        raise ValueError("reviewer-seat reports require a full lowercase meta.head_sha")
    if target == "change":
        number = _positive_number(meta.get("number"))
        if number is None:
            raise ValueError("meta.number must be a positive integer for a change request")
        meta["number"] = number
        if meta.get("forge") not in ("github", "gitlab"):
            raise ValueError("meta.forge must be github or gitlab for a change request")
    if target == "branch":
        if not isinstance(meta.get("branch"), str) or not meta["branch"].strip():
            raise ValueError("meta.branch must be a non-empty string for a branch")
        _line_safe(meta["branch"], "meta.branch")
        meta["branch"] = meta["branch"].strip()
    if not isinstance(meta.get("title"), str) or not meta["title"].strip():
        raise ValueError("meta.title must be a non-empty string")
    _line_safe(meta["title"], "meta.title")
    meta["title"] = meta["title"].strip()
    if not isinstance(meta.get("verdict"), str):
        raise ValueError("meta.verdict must be a string")
    for key in ("verdict", "ticket", "project", "change_state"):
        if isinstance(meta.get(key), str):
            _handoff_safe(meta[key], "meta.%s" % key)
    for key in ("repo_root", "source_branch"):
        if key in meta:
            if not isinstance(meta[key], str) or not meta[key].strip():
                warnings.append("meta.%s is not a non-empty string; omitting it." % key)
                meta.pop(key)
            else:
                _line_safe(meta[key], "meta.%s" % key)
                meta[key] = meta[key].strip()
    if "web_url" in meta:
        if _safe_http_url(meta["web_url"]):
            meta["web_url"] = _safe_http_url(meta["web_url"])
        else:
            warnings.append("meta.web_url is not a safe http(s) URL; omitting it.")
            meta.pop("web_url")
    if "storage_key" in meta and not isinstance(meta["storage_key"], str):
        warnings.append("meta.storage_key is not a string; using the derived key.")
        meta.pop("storage_key")

    findings = prepared.get("findings")
    if not isinstance(findings, list):
        raise ValueError("findings must be a list")
    normalized = []
    identities = set()
    run = prepared.get("run")
    if run is not None and not isinstance(run, dict):
        raise ValueError("run must be an object when present")
    memory_enabled = "memory" in prepared
    for index, raw in enumerate(findings):
        if not isinstance(raw, dict):
            raise ValueError("finding %d must be an object" % (index + 1))
        _warn_unknown(raw, _FINDING_FIELDS, "finding %d" % (index + 1), warnings)
        if raw.get("severity") not in SEVERITY_ORDER:
            raise ValueError("finding %d has an unknown severity" % (index + 1))
        if memory_enabled and "memory" not in raw:
            raise ValueError("finding %d is missing memory" % (index + 1))
        if "anchor_side" in raw and raw["anchor_side"] not in ("new", "old"):
            raise ValueError("finding %d anchor_side must be new or old" % (index + 1))
        if "memory" in raw:
            _validate_memory_finding(raw["memory"], "finding %d memory" % (index + 1))
        if "verified" in raw and not isinstance(raw.get("verified"), bool):
            raise ValueError("finding %d verified must be a boolean" % (index + 1))
        status = raw.get("verification_status")
        if "verification_status" in raw and status not in ("confirmed", "plausible"):
            raise ValueError("finding %d verification_status must be confirmed or plausible" %
                             (index + 1))
        if status == "plausible":
            if not isinstance(raw.get("what_would_confirm"), str) or not raw["what_would_confirm"].strip():
                raise ValueError("finding %d what_would_confirm must be a non-empty string" %
                                 (index + 1))
            raw["verified"] = False
        repro = raw.get("repro")
        if repro is not None and (not isinstance(repro, dict) or
                                  any(not isinstance(repro.get(key), str) or not repro[key].strip()
                                      for key in ("command", "output"))):
            raise ValueError("finding %d repro must have non-empty command and output" % (index + 1))
        deep = (prepared.get("run") or {}).get("deep")
        if isinstance(deep, dict) and deep.get("enabled") is True and raw.get("evidence") == "reproduced":
            if repro is None:
                raise ValueError("finding %d repro is required for reproduced evidence" % (index + 1))
        if seat == "reviewer" and "verified" not in raw:
            raw["verified"] = False
            warnings.append("Reviewer finding %d omitted verified; treating it as unverified." % (index + 1))
        for field in ("file", "line"):
            if field not in raw or raw[field] is None:
                raise ValueError("finding %d is missing %s" % (index + 1, field))
            try:
                raw_value = str(raw[field])
                coerced = raw_value.strip()
            except Exception:
                raise ValueError("finding %d %s is not string-coercible" % (index + 1, field))
            _line_safe(raw_value, "finding %d %s" % (index + 1, field))
            if not coerced:
                raise ValueError("finding %d %s must not be empty" % (index + 1, field))
        if raw.get("issue") is None and raw.get("body_md") is None:
            raise ValueError("finding %d needs issue or body_md" % (index + 1))
        if "dimensions" in raw:
            _list_of_strings(raw["dimensions"], "finding %d dimensions" % (index + 1))
        _validate_posted_text(raw, "finding %d (%s:%s)" % (index + 1, raw["file"], raw["line"]))
        value = normalize_finding(raw, warnings)
        for field in ("title", "file", "line"):
            _line_safe(value[field], "finding %d %s" % (index + 1, field))
        if not _LINE_RE.fullmatch(value["line"]):
            raise ValueError("finding %d line must be a number or a start-end range" % (index + 1))
        if isinstance(value.get("evidence"), str):
            _handoff_safe(value["evidence"], "finding %d evidence" % (index + 1))
        for dimension in value["dimensions"]:
            if isinstance(dimension, str):
                _handoff_safe(dimension, "finding %d dimensions" % (index + 1))
        identity = "%s:%s" % (value["file"], value["line"])
        if identity in identities:
            raise ValueError("duplicate finding identity %s" % identity)
        identities.add(identity)
        normalized.append(value)
    if "memory" in prepared:
        _validate_memory(prepared["memory"])
    prepared["findings"] = rank_findings(normalized)

    slug = target_slug(meta)
    if not slug:
        raise ValueError("target slug is empty after slugification")
    run = prepared.get("run")
    if run is not None and not isinstance(run, dict):
        raise ValueError("run must be an object when present")
    if isinstance(run, dict):
        _warn_unknown(run, _RUN_FIELDS, "run", warnings)
        source_access = run.get("source_access")
        if source_access not in (None, "author-worktree", "borrowed-worktree", "temp-clone", "diff-only"):
            raise ValueError("run.source_access has an unknown value")
        if source_access == "diff-only":
            if not isinstance(run.get("source_access_reason"), str) or not run["source_access_reason"].strip():
                raise ValueError("diff-only reports require run.source_access_reason")
            for finding in prepared["findings"]:
                finding["verified"] = False
        for key in ("dimensions_run", "guidance"):
            if key in run and (not isinstance(run[key], list) or
                               any(not isinstance(item, str) for item in run[key])):
                warnings.append("run.%s is not a list of strings; omitting it." % key)
                run[key] = []
        for key in ("dimensions_skipped", "clean_notes"):
            if key in run and not isinstance(run[key], list):
                warnings.append("run.%s is not a list; omitting it." % key)
                run[key] = []
        _validate_contract_run(run, meta, warnings)
    for key in ("recommended_order", "assumptions", "process_notes"):
        if key in prepared and not isinstance(prepared[key], list):
            warnings.append("%s is not a list; omitting it." % key)
            prepared[key] = []
    probe = prepared.get("mutation_probe")
    if probe is not None and not isinstance(probe, dict):
        warnings.append("mutation_probe is not an object; omitting it.")
        prepared["mutation_probe"] = None
    elif isinstance(probe, dict):
        _warn_unknown(probe, {"mutants", "killed", "survived", "narrative_md", "aside_md", "probes"},
                      "mutation_probe", warnings)
    risk = prepared.get("risk")
    if risk is not None and not isinstance(risk, dict):
        warnings.append("risk is not an object; omitting it.")
        prepared["risk"] = None
    elif isinstance(risk, dict):
        _warn_unknown(risk, {"level", "verbatim_md", "caveats", "metrics", "mitigations_md"},
                      "risk", warnings)
    if not normalized and not (isinstance(run, dict) and run.get("clean_notes")):
        warnings.append("No run.clean_notes were supplied for a zero-findings report.")
    return prepared, warnings


def _esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def _md(value):
    return render_markdown(value if isinstance(value, str) else "")


def export_label(meta):
    if meta["target"] == "change":
        return change_label(meta["forge"], meta["number"])
    if meta["target"] == "branch":
        return meta["branch"]
    return "local changes"


def _tally(findings):
    tally = {"must": 0, "should": 0, "nit": 0}
    for finding in findings:
        tally[SEVERITY_SLUG[finding["severity"]]] += 1
    return tally


def _token(text, tone=None, mono=False):
    """Render one astryx Token — the metadata chip. Not a Badge; Badge carries counts."""
    attrs = ""
    if tone:
        attrs += ' data-tone="%s"' % tone
    if mono:
        attrs += ' data-mono="true"'
    return '<span class="astryx-token"%s>%s</span>' % (attrs, _esc(text))


def _crumbs(meta):
    values = []
    if meta["target"] == "change" and meta.get("number") is not None:
        values.append(change_label(meta["forge"], meta["number"]))
    elif meta["target"] == "branch":
        values.append(meta["branch"])
    else:
        values.append("Local changes")
    for key in ("ticket", "project", "change_state"):
        if meta.get(key) not in (None, ""):
            values.append(str(meta[key]))
    parts = ['<span>%s</span>' % _esc(value) for value in values]
    if meta.get("head_sha"):
        parts.append('<span class="mono">%s</span>' % _esc(meta["head_sha"]))
    return '<div class="crumbs">%s</div>' % '<span class="sep">/</span>'.join(parts)


_VERDICT_TONE = {"block": "red", "blocked": "red", "request changes": "red",
                 "changes requested": "red", "approve with comments": "yellow",
                 "approve": "green", "approved": "green", "lgtm": "green"}


def _topnav(report, panes):
    """Render the pinned frame header: target identity, verdict, tally, and the tab strip.

    Identity has to stay visible while the reader scrolls a finding, which is what
    puts it in a TopNav rather than a masthead that scrolls away.
    """
    meta = report["meta"]
    findings = report["findings"]
    tally = _tally(findings)
    key = storage_key(meta, findings)
    verdict = str(meta["verdict"])
    tone = _VERDICT_TONE.get(verdict.strip().lower(), "gray")
    out = ['<header class="topnav" data-storage-key="%s" data-export-label="%s" data-review-seat="%s">' %
           (_esc(key), _esc(export_label(meta)), _esc(meta.get("seat", "author"))),
           '<div class="topnav-bar"><div class="identity">',
           _crumbs(meta),
           '<h1 class="astryx-heading" data-level="3" title="%s">%s</h1>' %
           (_esc(meta["title"]), _esc(meta["title"])),
           '</div>',
           '<div class="tally">']
    for slug, label in (("must", "Must fix"), ("should", "Should fix"), ("nit", "Nit")):
        out.append('<span class="tally-item"><span class="astryx-status-dot dot--%s" aria-hidden="true">'
                   '</span><b>%d</b> %s</span>' % (slug, tally[slug], _esc(label)))
    out.append('</div><div class="verdict">%s%s</div></div>' %
               (_token(meta.get("seat", "author") + " seat"), _token(verdict, tone=tone)))
    out.append(_tablist(panes))
    out.append("</header>")
    return "\n".join(out)


def _tablist(panes):
    out = ['<nav class="tablist" role="tablist" aria-label="Report sections">']
    for index, (pane_id, label, count, _) in enumerate(panes):
        badge = ('<span class="astryx-badge" data-variant="neutral">%d</span>' % count) if count is not None else ""
        out.append('<button class="tab" type="button" role="tab" id="tab-%s" aria-controls="pane-%s" '
                   'aria-selected="%s" tabindex="%d">%s%s</button>' %
                   (pane_id, pane_id, "true" if index == 0 else "false",
                    0 if index == 0 else -1, _esc(label), badge))
    out.append("</nav>")
    return "\n".join(out)


def _string_list(value):
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def _row(key, value, end=""):
    return ('<div class="row"><div class="row-k">%s</div><div class="row-v">%s</div>%s</div>' %
            (key, value, ('<div class="row-end">%s</div>' % end) if end else ""))


def _sec_head(title, lede=""):
    return ('<div class="sec-head"><h2 class="astryx-heading" data-level="2">%s</h2>%s</div>' %
            (title, ('<p class="lede">%s</p>' % lede) if lede else ""))


def _banner(status, title, body):
    return ('<div class="astryx-banner" data-status="%s"><div><strong>%s</strong> %s</div></div>'
            % (status, title, body))


def _checker_failure_text(deep):
    """One sentence naming each claim the deep checker failed on, or empty."""
    failures = deep.get("checker_failures") if isinstance(deep, dict) else None
    if not failures:
        return ""
    return "Unchecked claims withheld: %s" % ", ".join(
        "%s (%s)" % (key, reason.strip()) for key, reason in sorted(failures.items()))


def _budget_overrun_text(deep):
    """One sentence stating the deep time budget was exceeded, or empty."""
    if not isinstance(deep, dict):
        return ""
    budget, elapsed = deep.get("budget_minutes"), deep.get("elapsed_minutes")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in (budget, elapsed)):
        return ""
    if elapsed <= budget:
        return ""
    return "The deep review exceeded its time budget (%gm of %gm)" % (elapsed, budget)


def _since_text(run):
    """One line naming the delta-review base, or empty when the run is not a delta review."""
    since = run.get("since")
    if not isinstance(since, dict):
        return ""
    return "%s (%s); delta review, report only" % (since["ref"], since["sha"][:12])


def _hunk_coverage_text(deep):
    """One line summarizing self-reported hunk coverage, or empty when none was recorded."""
    coverage = deep.get("hunk_coverage")
    if not isinstance(coverage, dict):
        return ""
    text = "%s of %s hunks examined across %s areas (self-reported)" % (
        coverage.get("examined"), coverage.get("hunks"), coverage.get("areas"))
    mean = coverage.get("mean_area_lines")
    if isinstance(mean, (int, float)) and not isinstance(mean, bool):
        text += "; mean %g lines per area" % mean
    return text


def _area_hunk_text(area):
    """Lines and self-reported examined count for an area that carries hunks, or empty."""
    hunks = area.get("hunks")
    if not isinstance(hunks, list):
        return ""
    ids = {hunk.get("id") for hunk in hunks if isinstance(hunk, dict)}
    examined = len({item for item in _string_list(area.get("examined")) if item in ids})
    parts = []
    if isinstance(area.get("lines"), (int, float)) and not isinstance(area["lines"], bool):
        parts.append("%g lines" % area["lines"])
    parts.append("examined %d/%d hunks (self-reported)" % (examined, len(hunks)))
    return "; ".join(parts)


def _unexamined_hunks(area, deep):
    """The area's unexamined hunks as (id, file, header), looked up in its hunk list."""
    unexamined = deep.get("unexamined") if isinstance(deep.get("unexamined"), dict) else {}
    by_id = {hunk.get("id"): hunk for hunk in area.get("hunks") or [] if isinstance(hunk, dict)}
    missing = []
    for identifier in _string_list(unexamined.get(area.get("id"))):
        hunk = by_id.get(identifier) or {}
        missing.append((identifier, hunk.get("file") or "", hunk.get("header") or ""))
    return missing


def _what_was_run(report):
    """Render the run conditions as records in one Section: rows, not a grid of panels."""
    run = report.get("run") or {}
    dimensions = _string_list(run.get("dimensions_run"))
    skipped = run.get("dimensions_skipped") if isinstance(run.get("dimensions_skipped"), list) else []
    guidance = _string_list(run.get("guidance"))
    coverage = run.get("coverage")
    deep = run.get("deep") if isinstance(run.get("deep"), dict) else {}
    out = ['<section class="astryx-section" id="what-was-run">',
           _sec_head("What was run", "The conditions every finding was produced under.")]
    if isinstance(coverage, str) and "⚠" in coverage:
        out.append(_banner("warning", "Incomplete coverage.", _esc(coverage)))
    if run.get("source_access") == "diff-only":
        out.append(_banner("warning", "Verification limited to the diff.",
                           "Every finding is unverified. %s" % _esc(run.get("source_access_reason"))))
    if run.get("incomplete"):
        failed = ", ".join(_string_list(run.get("dimensions_failed")))
        if not failed and deep.get("unreached_areas"):
            failed = "Unreached areas: %s" % ", ".join(deep["unreached_areas"])
        checker = _checker_failure_text(deep)
        overrun = _budget_overrun_text(deep)
        if failed:
            body = "%s did not finish, so a short findings list here is not a clean bill." % _esc(failed)
            if checker:
                body += " %s." % _esc(checker)
            if overrun:
                body += " %s." % _esc(overrun)
        elif checker or overrun:
            body = "%s. A short findings list here is not a clean bill." % _esc(
                ". ".join(part for part in (checker, overrun) if part))
        elif deep:
            body = "Some deep checks did not finish, so a short findings list here is not a clean bill."
        else:
            body = "unknown lenses did not finish, so a short findings list here is not a clean bill."
        out.append(_banner("warning", "Incomplete review.", body))
    rows = []
    if run.get("diff_size"):
        rows.append(_row("Diff size", _esc(run["diff_size"])))
    if run.get("source_access"):
        rows.append(_row("Source access", _esc(run["source_access"])))
    if coverage:
        rows.append(_row("Coverage", _esc(coverage)))
    if _since_text(run):
        rows.append(_row("Reviewed since", _esc(_since_text(run))))
    if guidance:
        rows.append(_row("Guidance", '<div class="taglist">%s</div>' %
                         "".join(_token(item) for item in guidance)))
    if dimensions:
        rows.append(_row("Dimensions run",
                         '<div class="taglist">%s</div>' %
                         "".join(_token(item, mono=True) for item in dimensions)))
    models = run.get("models") if isinstance(run.get("models"), dict) else {}
    if models:
        rows.append(_row("Models", '<div class="taglist">%s</div>' %
                         "".join(_token("%s: %s" % (k, v), mono=True) for k, v in sorted(models.items()))))
    if run.get("severity_floor"):
        rows.append(_row("Posting floor", _esc(run["severity_floor"])))
    excluded = _string_list(run.get("excluded_generated"))
    if excluded:
        rows.append(_row("Excluded as generated", '<div class="taglist">%s</div>' %
                         "".join(_token(item, mono=True) for item in excluded)))
    for item in skipped:
        if isinstance(item, dict):
            rows.append(_row("Skipped: %s" % _esc(item.get("name", "unknown")),
                             _esc(item.get("why", "not applicable"))))
        else:
            rows.append(_row("Skipped", _esc(item)))
    if deep.get("enabled"):
        for key, label in (("budget_minutes", "Deep budget (minutes)"),
                           ("elapsed_minutes", "Deep elapsed (minutes)"),
                           ("sandbox_kind", "Deep sandbox")):
            if deep.get(key) is not None:
                rows.append(_row(label, _esc(deep[key])))
    if _hunk_coverage_text(deep):
        rows.append(_row("Hunk coverage", _esc(_hunk_coverage_text(deep))))
    if deep.get("checker_failures"):
        rows.append(_row("Checker failures", "".join(
            "<div><span class=\"mono\">%s</span> %s</div>" % (_esc(key), _esc(reason))
            for key, reason in sorted(deep["checker_failures"].items()))))
    if rows:
        out.append('<div class="rows">%s</div>' % "".join(rows))
    if not run.get("incomplete") and _budget_overrun_text(deep):
        out.append('<div class="section-note">%s</div>' % _esc(_budget_overrun_text(deep)))
    if "areas" in deep:
        out.append('<h3 class="astryx-heading" data-level="3">Area map</h3>')
        area_rows = []
        for area in deep["areas"]:
            title = _esc(area.get("title") or ", ".join(_string_list(area.get("files"))))
            files = ", ".join(_string_list(area.get("files")))
            questions = _string_list(area.get("questions"))
            detail = "<strong>%s</strong>" % title
            if files:
                detail += '<div class="mono">%s</div>' % _esc(files)
            hunk_text = _area_hunk_text(area)
            if hunk_text:
                detail += "<div>%s</div>" % _esc(hunk_text)
            missing = _unexamined_hunks(area, deep)
            if missing:
                detail += "<div>Unexamined hunks:</div><ul>%s</ul>" % "".join(
                    '<li><span class="mono">%s</span> %s <span class="mono">%s</span></li>' % (
                        _esc(identifier), _esc(file), _esc(header)) for identifier, file, header in missing)
            if questions:
                detail += "<ul>%s</ul>" % "".join("<li>%s</li>" % _esc(q) for q in questions)
            status = _esc(area.get("status", "pending"))
            if area.get("status") == "read_only_degraded" and area.get("degraded_reason"):
                status += " — %s" % _esc(area["degraded_reason"])
            area_rows.append(_row(_esc(area.get("id", "")), detail, status))
        out.append('<div class="rows">%s</div>' % "".join(area_rows))
    notes = _md(run.get("notes_md"))
    if notes:
        out.append('<div class="section-note">%s</div>' % notes)
    out.append("</section>")
    return "\n".join(out)


_PROBE_EXPLAINER = ("A mutation probe deliberately breaks the changed code one small edit at a "
                    "time, then reruns the tests. A mutant that is <em>killed</em> means a test "
                    "noticed the break, so that behavior is genuinely covered. A mutant that "
                    "<em>survives</em> means every test still passed while the code was wrong \u2014 "
                    "the behavior is not really tested, whatever the coverage number says.")


def _probe_rows(probes):
    """Render the per-mutant records; each row says what broke, what ran, and what it proves."""
    rows = []
    for item in probes:
        if not isinstance(item, dict):
            continue
        outcome = str(item.get("result", "")).strip().lower()
        outcome = outcome if outcome in ("killed", "survived") else "unknown"
        label = {"killed": "Killed", "survived": "Survived", "unknown": "Unrecorded"}[outcome]
        tone = {"killed": "green", "survived": "red", "unknown": "gray"}[outcome]
        rows.append(
            '<div class="row row--stack"><div class="row-k">%s%s</div><div class="row-v">'
            '<dl class="probe-detail"><dt>What was broken</dt><dd>%s</dd>'
            '<dt>What was run</dt><dd>%s</dd><dt>What it proves</dt><dd>%s</dd></dl>'
            '</div></div>' % (
                _token(label, tone=tone),
                ('<span class="mono">%s</span>' % _esc(item["where"])) if item.get("where") else "",
                _md(item.get("mutation_md")) or "<p>Not recorded.</p>",
                ('<p><code>%s</code></p>' % _esc(item["test"])) if item.get("test") else "<p>Not recorded.</p>",
                _md(item.get("means_md")) or "<p>Not recorded.</p>"))
    return rows


def _mutation_section(probe):
    if not isinstance(probe, dict):
        return ""
    mutants = probe.get("mutants", 0)
    killed = probe.get("killed", 0)
    survived = probe.get("survived", 0)
    out = ['<section class="astryx-section" id="mutation-probe">',
           _sec_head("Mutation probe", _PROBE_EXPLAINER),
           '<div class="stats">',
           '<div class="metric"><span class="metric-k">Mutants</span>'
           '<span class="metric-v">%s</span></div>' % _esc(mutants),
           '<div class="metric"><span class="metric-k">Killed</span><span class="metric-v">'
           '<span class="astryx-status-dot dot--good" aria-hidden="true"></span>%s</span></div>' % _esc(killed),
           '<div class="metric"><span class="metric-k">Survived</span><span class="metric-v">'
           '<span class="astryx-status-dot dot--%s" aria-hidden="true"></span>%s</span></div>' %
           ("bad" if survived else "good", _esc(survived)),
           '</div>']
    narrative = _md(probe.get("narrative_md"))
    if narrative:
        out.append(narrative)
    rows = _probe_rows(probe.get("probes") if isinstance(probe.get("probes"), list) else [])
    if rows:
        out.append('<div class="rows">')
        out.extend(rows)
        out.append("</div>")
    aside = _md(probe.get("aside_md"))
    if aside:
        out.append('<div class="aside-note">%s</div>' % aside)
    out.append("</section>")
    return "\n".join(out)


_RISK_METRICS = (("likelihood", "Likelihood"), ("impact", "Impact"),
                 ("blast_radius", "Blast radius"), ("detection", "Detection"),
                 ("rollback", "Rollback"))

# Same word can be good or bad depending on the metric: "weak" detection is bad,
# "minor" impact is good. Tone is therefore resolved per metric, never globally.
_RISK_TONES = {
    "likelihood": {"rare": "good", "unlikely": "good", "improbable": "good", "remote": "good",
                   "possible": "warn", "occasional": "warn", "likely": "bad", "probable": "bad",
                   "frequent": "bad", "certain": "bad"},
    "impact": {"none": "good", "no": "good", "minor": "good", "low": "good", "moderate": "warn",
               "significant": "bad", "major": "bad", "severe": "bad", "critical": "bad"},
    "blast_radius": {"none": "good", "single": "good", "narrow": "good", "limited": "good",
                     "partial": "warn", "broad": "bad", "wide": "bad", "all": "bad", "global": "bad"},
    "detection": {"strong": "good", "immediate": "good", "automatic": "good",
                  "moderate": "warn", "partial": "warn", "weak": "bad", "none": "bad", "manual": "bad"},
    "rollback": {"clean": "good", "easy": "good", "trivial": "good", "instant": "good",
                 "partial": "warn", "manual": "warn", "hard": "bad", "difficult": "bad",
                 "none": "bad", "irreversible": "bad"},
}
_RISK_LEVEL_TONE = {"very low": "good", "low": "good", "medium": "warn", "moderate": "warn",
                    "high": "bad", "critical": "bad", "do not ship": "bad"}

# StatusDot variants and Token colours are separate vocabularies; risk tone is
# resolved in the first and has to be translated before it reaches a Token.
_TONE_COLOR = {"good": "green", "warn": "yellow", "bad": "red", "none": "gray"}


def _risk_tone(key, entry):
    """Resolve a KPI tile's colour. An authored tone wins; otherwise infer from the level word."""
    tone = str(entry.get("tone", "")).strip().lower()
    if tone in ("good", "warn", "bad"):
        return tone
    level = str(entry.get("level", "")).strip().lower()
    return _RISK_TONES.get(key, {}).get(level.split()[0] if level else "", "none")


def _risk_metrics(risk):
    metrics = risk.get("metrics") if isinstance(risk.get("metrics"), dict) else {}
    out = []
    for key, label in _RISK_METRICS:
        entry = metrics.get(key)
        if not isinstance(entry, dict) or not str(entry.get("level", "")).strip():
            continue
        note = entry.get("note_md")
        out.append('<div class="metric"><span class="metric-k">%s</span>'
                   '<span class="metric-v"><span class="astryx-status-dot dot--%s" aria-hidden="true">'
                   '</span>%s</span>%s</div>' % (
                       _esc(label), _risk_tone(key, entry), _esc(entry["level"]),
                       ('<span class="astryx-text" data-type="supporting" data-color="secondary">%s</span>'
                        % render_inline(note)) if isinstance(note, str) and note.strip() else ""))
    return out


def _risk_section(risk):
    if not isinstance(risk, dict):
        return ""
    level = risk.get("level")
    out = ['<section class="astryx-section" id="risk">',
           '<div class="sec-head"><h2 class="astryx-heading" data-level="2">Risk%s</h2></div>' %
           (" " + _token(level, tone=_TONE_COLOR[_RISK_LEVEL_TONE.get(
               " ".join(str(level).lower().split()), "none")]) if level else "")]
    metrics = _risk_metrics(risk)
    if metrics:
        out.append('<div class="metrics">')
        out.extend(metrics)
        out.append("</div>")
    mitigations = _md(risk.get("mitigations_md"))
    if mitigations:
        out.append('<h3 class="astryx-heading" data-level="4">Lowering this risk</h3>%s' % mitigations)
    for caveat in (risk.get("caveats") if isinstance(risk.get("caveats"), list) else []):
        if isinstance(caveat, dict):
            out.append('<h3 class="astryx-heading" data-level="4">%s</h3>%s' %
                       (_esc(caveat.get("title", "Caveat")), _md(caveat.get("body_md"))))
    verbatim = _md(risk.get("verbatim_md"))
    if verbatim and metrics:
        out.append('<details class="verbatim"><summary>Full risk assessment</summary>%s</details>' % verbatim)
    elif verbatim:
        out.append(verbatim)
    out.append("</section>")
    return "\n".join(out)


def _progress(total, seat):
    """Render the decision tally: one bar plus a legend that doubles as the disposition filter."""
    labels = {slot: label for slot, label in DISPOSITIONS[seat]}
    out = ['<div class="progress" id="progress" role="group" aria-label="Filter by decision">',
           '<div class="astryx-progress-bar" aria-hidden="true">']
    for value in ("fix", "later", "detail", "ignore"):
        out.append('<span class="pseg pseg--%s"></span>' % value)
    out.append('</div><div class="pstats">')
    for value in ("fix", "later", "detail", "ignore", "none"):
        count = total if value == "none" else 0
        out.append('<button class="pstat" type="button" data-filter="disp" data-value="%s" '
                   'aria-pressed="false"><span class="n" data-count="%s">%d</span>'
                   '<span class="k">%s</span></button>' % (value, value, count, labels[value]))
    out.append("</div></div>")
    return "\n".join(out)


def _dimension_counts(findings):
    counts = {}
    order = []
    for finding in findings:
        for dimension in finding["dimensions"]:
            if dimension not in counts:
                counts[dimension] = 0
                order.append(dimension)
            counts[dimension] += 1
    return [(name, counts[name]) for name in order]


def _filters(findings, tally):
    out = ['<div class="filters" role="group" aria-label="Filter findings">',
           '<div class="frow"><span class="label">Severity</span>']
    for value, label in (("must", "Must"), ("should", "Should"), ("nit", "Nit")):
        if tally[value]:
            out.append('<button class="chip" type="button" data-filter="sev" data-value="%s" '
                       'aria-pressed="false"><span class="astryx-status-dot dot--%s" aria-hidden="true">'
                       '</span>%s<span class="c">%d</span></button>' % (value, value, label, tally[value]))
    dimensions = _dimension_counts(findings)
    out.append('</div><details class="dimfilter"><summary>Dimension'
               '<span class="astryx-badge" data-variant="neutral">%d</span></summary>'
               '<div class="frow">' % len(dimensions))
    for dimension, count in dimensions:
        out.append('<button class="chip" type="button" data-filter="dim" data-value="%s" '
                   'aria-pressed="false">%s<span class="c">%d</span></button>' %
                   (_esc(dimension), _esc(dimension), count))
    out.append("</div></details></div>")
    return "\n".join(out)


def _export_panel(total):
    """Render the export control plus the hand-off instruction and remaining-decision counter."""
    return (
        '<div class="texport">'
        '<p class="texport-why">Decide every finding, then copy this block and paste it back '
        'into the session you launched the review from, or into a new session. It carries '
        'your decisions plus each finding\'s full text and the target to check out. Nothing is '
        'posted or acted on until the paste arrives.</p>'
        '<p class="texport-left" id="export-left">%d of %d still undecided</p>'
        '<div class="texport-actions">'
        '<button class="btn" type="button" id="btn-export">Copy decisions</button>'
        '<button class="btn" type="button" data-variant="ghost" id="btn-reset">Reset</button>'
        '</div>'
        '<span class="saved" id="saved" aria-live="polite"></span></div>' % (total, total))


def open_human_threads(finding):
    """Unresolved human threads on `finding` that the posting identity did not write.

    The one eligibility rule for a support reply: triage validation, the report's reply control,
    and the reviewer stager all accept exactly these entries.
    """
    memory = finding.get("memory") if isinstance(finding.get("memory"), dict) else {}
    return [entry for entry in memory.get("human_context") or []
            if isinstance(entry, dict) and entry.get("resolved") is False and entry.get("own") is not True]


def _reply_targets(finding):
    """Unresolved human threads on this finding, oldest note first, as triage-control data."""
    candidates = []
    for entry in open_human_threads(finding):
        url = _safe_http_url(entry.get("url"))
        candidates.append({
            "note_id": entry["note_id"],
            "author": "" if entry.get("author") is None else str(entry["author"]),
            "excerpt": " ".join(str(entry.get("body") or "").split())[:200],
            "url": url,
        })
    return sorted(candidates, key=lambda item: item["note_id"])


def _finding_card(finding, seat="author"):
    severity = SEVERITY_SLUG[finding["severity"]]
    location = "%s:%s" % (finding["file"], finding["line"])
    dims_json = json.dumps(finding["dimensions"], ensure_ascii=False, separators=(",", ":"))
    memory = finding.get("memory") if isinstance(finding.get("memory"), dict) else {}
    seeded_disp = memory.get("disposition", "none")
    if seeded_disp not in ("fix", "later", "detail", "ignore", "none"):
        seeded_disp = "none"
    attrs = ['class="finding"', 'id="%s"' % finding["id"],
             'data-title="%s"' % _esc(finding["title"]), 'data-file="%s"' % _esc(location),
             'data-sev="%s"' % severity, 'data-dims="%s"' % _esc(dims_json),
             'data-memory-disposition="%s"' % _esc(seeded_disp),
             'data-memory-note="%s"' % _esc(memory.get("note", ""))]
    if finding.get("area") is not None:
        attrs.append('data-area="%s"' % _esc(finding["area"]))
    if seat == "reviewer":
        candidates = _reply_targets(finding)
        if candidates:
            attrs.append('data-reply-targets="%s"' % _esc(
                json.dumps(candidates, ensure_ascii=False, separators=(",", ":"))))
    out = ["<article %s>" % " ".join(attrs),
           '<div class="f-head"><span class="f-id">%s</span>' % finding["id"],
           '<span class="sev sev--%s"><span class="astryx-status-dot dot--%s" aria-hidden="true">'
           '</span>%s</span>' % (severity, severity, finding["severity"])]
    for dimension in finding["dimensions"]:
        out.append(_token(dimension, mono=True))
    if finding.get("evidence") not in (None, ""):
        out.append(_token(finding["evidence"], tone="blue"))
    if finding.get("verification_status") == "plausible":
        out.append(_token("plausible", tone="yellow"))
    out.append('</div><h2 class="f-title">%s</h2>' % _esc(finding["title"]))
    out.append('<span class="anchor">%s<span class="ln">:%s</span></span>' %
               (_esc(finding["file"]), _esc(finding["line"])))
    if finding.get("impact"):
        out.append('<p class="f-impact">%s</p>' % render_inline(finding["impact"]))
    body = _md(finding.get("body_md"))
    if body:
        out.append(body)
    aside = _md(finding.get("aside_md"))
    if aside:
        out.append('<div class="aside-note">%s</div>' % aside)
    if finding.get("verification_status") == "plausible":
        out.append('<div class="aside-note"><strong>What would confirm this:</strong> %s</div>' %
                   _esc(finding["what_would_confirm"]))
    repro = finding.get("repro")
    if isinstance(repro, dict) and repro.get("command") and repro.get("output"):
        out.append('<div class="repro"><span class="rec-k">Reproduction</span>'
                   '<pre><code>$ %s\n%s</code></pre></div>' %
                   (_esc(repro["command"]), _esc(repro["output"])))
    recommendation = _md(finding.get("recommendation_md"))
    if recommendation:
        out.append('<div class="rec"><span class="rec-k">Recommendation</span>%s</div>' % recommendation)
    out.append("</article>")
    return "\n".join(out)


def _safe_http_url(value):
    if not isinstance(value, str) or UNSAFE_LINE.search(value) or "\\" in value:
        return None
    value = value.strip()
    if re.match(r"^https?://[^\s<>\"']+$", value, re.IGNORECASE):
        return value
    return None


def _memory_link_html(label, url):
    safe = _safe_http_url(url)
    if not safe:
        return _esc(label)
    return '<a href="%s" rel="noopener noreferrer">%s</a>' % (_esc(safe), _esc(label))


def _memory_md_text(value):
    """Render untrusted memory prose as one inert Markdown line."""
    text = "" if value is None else str(value)
    text = re.sub(r"[\r\n\u2028\u2029]+", " ", text)
    return re.sub(r"([\\`*_{}\[\]()#+.!|<>])", r"\\\1", text)


def _memory_link_md(label, url):
    safe = _safe_http_url(url)
    if not safe:
        return _memory_md_text(label)
    return "[%s](%s)" % (_memory_md_text(label), safe.replace(")", "%29").replace("(", "%28"))


def _memory_record_html(item):
    title = item.get("title") or item.get("summary") or item.get("body") or item.get("body_md") or "Prior finding"
    detail = item.get("body") or item.get("body_md") or item.get("recommendation") or item.get("recommendation_md")
    location = ""
    if item.get("file") is not None:
        location = '<span class="mono">%s%s</span>' % (
            _esc(item.get("file")), (":" + _esc(item.get("line")) if item.get("line") is not None else ""))
    link = (" " + _memory_link_html("Open discussion", item["thread"].get("url"))
            if isinstance(item.get("thread"), dict) and item["thread"].get("url") else "")
    return ('<div class="row row--stack"><div class="row-k">%s</div><div class="row-v">%s%s%s</div></div>'
            % (_esc(title), location, link, _md(detail) if detail else ""))


def _memory_sections_html(report):
    memory = report.get("memory")
    if not isinstance(memory, dict):
        return []
    snapshot = memory.get("snapshot") if isinstance(memory.get("snapshot"), dict) else {}
    warnings = list(memory.get("warnings") or []) + list(snapshot.get("warnings") or [])
    reason = snapshot.get("invalidation_reason")
    out = []
    if warnings or reason:
        out.append('<section class="astryx-section" id="memory-warnings">%s' %
                   _sec_head("Memory warnings"))
        if reason:
            out.append(_banner("warning", "Memory reset:", _esc(reason)))
        for warning in warnings:
            out.append(_banner("warning", "", _esc(warning)))
        out.append("</section>")
    appears = memory.get("appears_fixed") or []
    if appears:
        out.append('<section class="astryx-section" id="appears-fixed">%s<div class="rows">' %
                   _sec_head("Appears fixed",
                             "Prior findings not raised in this run. Follow up with "
                             "quirk:receiving-code-review; this report does not resolve threads."))
        out.extend(_memory_record_html(item) for item in appears if isinstance(item, dict))
        out.append("</div></section>")
    for state, section_id, title in (
            ("re-found-after-resolution", "re-found-after-resolution", "Re-found after resolution"),
            ("possible-regression", "possible-regression", "Possible regression")):
        rows = [finding for finding in report.get("findings", [])
                if (finding.get("memory") or {}).get("state") == state]
        if not rows:
            continue
        out.append('<section class="astryx-section" id="%s">%s<div class="rows">' %
                   (section_id, _sec_head(title, "These findings need explicit triage; "
                                                 "this report does not resolve threads.")))
        for finding in rows:
            memory_finding = finding.get("memory") or {}
            thread = memory_finding.get("thread") if isinstance(memory_finding, dict) else None
            links = _esc(finding["id"])
            if isinstance(thread, dict) and thread.get("url"):
                links += " " + _memory_link_html("Open discussion", thread.get("url"))
            out.append(_row(links, _esc(finding["title"])))
        out.append("</div></section>")
    return out


def _memory_sections_md(report):
    memory = report.get("memory")
    if not isinstance(memory, dict):
        return []
    snapshot = memory.get("snapshot") if isinstance(memory.get("snapshot"), dict) else {}
    warnings = list(memory.get("warnings") or []) + list(snapshot.get("warnings") or [])
    reason = snapshot.get("invalidation_reason")
    lines = []
    if warnings or reason:
        lines.extend(["## Memory warnings", ""])
        if reason:
            lines.extend(["**Memory reset:** %s" % _memory_md_text(reason), ""])
        lines.extend("- %s" % _memory_md_text(warning) for warning in warnings)
        lines.append("")
    appears = memory.get("appears_fixed") or []
    if appears:
        lines.extend(["## Appears fixed", "",
                      "Prior findings not raised in this run. Follow up with quirk:receiving-code-review; this report does not resolve threads.", ""])
        for item in appears:
            if isinstance(item, dict):
                title = item.get("title") or item.get("summary") or "Prior finding"
                detail = item.get("body") or item.get("body_md")
                line = "- %s" % _memory_md_text(title)
                if item.get("file") is not None:
                    location = "%s%s" % (item["file"], ":%s" % item["line"] if item.get("line") is not None else "")
                    line += " (`%s`)" % re.sub(r"[`\r\n\u2028\u2029]", "'", location)
                thread = item.get("thread")
                if isinstance(thread, dict) and thread.get("url"):
                    line += " — %s" % _memory_link_md("Open discussion", thread.get("url"))
                if detail:
                    line += ": %s" % _memory_md_text(detail)
                lines.append(line)
        lines.append("")
    for state, title in (("re-found-after-resolution", "Re-found after resolution"),
                         ("possible-regression", "Possible regression")):
        rows = [finding for finding in report.get("findings", [])
                if (finding.get("memory") or {}).get("state") == state]
        if not rows:
            continue
        lines.extend(["## %s" % title, "",
                      "These findings need explicit triage; this report does not resolve threads.", ""])
        for finding in rows:
            line = "- [%s](#%s) — %s" % (finding["id"], finding["id"], _memory_md_text(finding["title"]))
            thread = (finding.get("memory") or {}).get("thread")
            if isinstance(thread, dict) and thread.get("url"):
                line += " — " + _memory_link_md("Open discussion", thread.get("url"))
            lines.append(line)
        lines.append("")
    return lines



def _checked_dropped_section(report):
    run = report.get("run") or {}
    deep = run.get("deep") if isinstance(run.get("deep"), dict) else {}
    dropped = deep.get("checked_and_dropped") or []
    if not dropped:
        return ""
    rows = [_row('<span class="mono">%s:%s</span>' % (_esc(item["file"]), _esc(item["line"])),
                 '<strong>%s</strong> — %s' % (_esc(item["title"]), _esc(item["reason"])))
            for item in dropped]
    return ('<details class="checked-dropped"><summary>Checked and dropped (%d)</summary>'
            '<div class="rows">%s</div></details>' % (len(dropped), "".join(rows)))


def _findings_section(report):
    """Render the findings pane: a master-detail Layout with the rail in the start slot."""
    findings = report["findings"]
    if not findings:
        out = ['<div class="doc">', _sec_head("Findings", "No findings — see per-dimension notes.")]
        notes = (report.get("run") or {}).get("clean_notes") or []
        rows = [_row(_esc(item.get("dimension", "Review")), _md(item.get("note_md")))
                for item in notes if isinstance(item, dict)]
        out.append('<div class="rows">%s</div>' % "".join(rows) if rows else
                   '<p>No findings were reported. Per-dimension clean notes were not supplied.</p>')
        dropped = _checked_dropped_section(report)
        if dropped:
            out.append(dropped)
        out.append("</div>")
        return "\n".join(out)

    tally = _tally(findings)
    seat = report["meta"].get("seat", "author")
    return "\n".join([
        '<div class="layout">',
        '<aside class="rail" aria-label="Findings">',
        '<div class="rail-head">%s</div>' % _progress(len(findings), seat),
        _filters(findings, tally),
        '<div class="rail-body" id="rail-body">',
        '<ol class="tnav" id="tnav"></ol>',
        '<p class="no-match" id="no-match" hidden>No findings match those filters.</p>',
        '</div>',
        '<div class="rail-foot">%s</div>' % _export_panel(len(findings)),
        '<div class="rail-resizer" role="separator" aria-orientation="vertical"'
        ' aria-label="Resize findings list" tabindex="0"></div>',
        '</aside>',
        '<div class="detail">',
        '<div class="detail-body" id="tdetail">',
        "\n".join(_finding_card(finding, seat) for finding in findings),
        _checked_dropped_section(report),
        '</div>',
        '<div class="detail-foot" id="decide-bar">',
        '<span class="decide-k">Decision</span><div class="dopts"></div>',
        '<div class="dnav">',
        '<button class="btn" type="button" data-variant="ghost" data-step="prev">← Previous</button>',
        '<button class="btn" type="button" data-variant="ghost" data-step="next">Next →</button>',
        '<span class="hint">1 / 2 / 3 / 4 to decide · J / K to move</span>',
        '</div></div></div></div>'])


def _simple_list_section(section_id, title, values, ordered):
    if not isinstance(values, list) or not values:
        return ""
    tag = "ol" if ordered else "ul"
    items = "".join('<li class="row"><div class="row-v">%s</div></li>' %
                    render_inline(value if isinstance(value, str) else str(value))
                    for value in values)
    return ('<section class="astryx-section" id="%s">%s<%s class="rows">%s</%s></section>' %
            (section_id, _sec_head(title), tag, items, tag))


def _process_section(notes):
    if not isinstance(notes, list) or not notes:
        return ""
    out = ['<section class="astryx-section" id="process-notes">', _sec_head("Process notes")]
    for note in notes:
        if isinstance(note, dict):
            out.append('<h3 class="astryx-heading" data-level="4">%s</h3>%s' %
                       (_esc(note.get("title", "Note")), _md(note.get("body_md"))))
    out.append("</section>")
    return "\n".join(out)


def _footer(report):
    findings = report["findings"]
    tally = _tally(findings)
    count = len(findings)
    parts = ["%d finding%s · %d Must fix · %d Should fix · %d Nit" %
             (count, "" if count == 1 else "s", tally["must"], tally["should"], tally["nit"])]
    probe = report.get("mutation_probe")
    if isinstance(probe, dict):
        parts.append("%s mutants run, %s survived" % (probe.get("mutants", 0), probe.get("survived", 0)))
    meta = report["meta"]
    target = export_label(meta)
    if meta.get("head_sha"):
        target += " · %s" % meta["head_sha"]
    parts.append(target)
    return '<footer class="footer">%s</footer>' % " — ".join(_esc(item) for item in parts)


def _panes(report):
    """Return one (id, tab label, count, html) per pane that has content.

    Built in a single pass so the tab strip and the panes cannot disagree about
    which sections exist.
    """
    panes = [("findings", "Findings", len(report["findings"]), _findings_section(report))]
    standfirst = _md(report["meta"].get("standfirst_md"))
    summary = "\n".join(filter(None, [
        ('<section class="astryx-section" id="summary">%s%s</section>' %
         (_sec_head("Summary"), standfirst)) if standfirst else "",
        _risk_section(report.get("risk"))]))
    if summary:
        panes.append(("summary", "Summary & risk", None, '<div class="doc">%s</div>' % summary))
    run = "\n".join(filter(None, [_what_was_run(report),
                                  _mutation_section(report.get("mutation_probe"))]))
    if run:
        panes.append(("run", "What was run", None, '<div class="doc">%s</div>' % run))
    memory = _memory_sections_html(report)
    if memory:
        panes.append(("memory", "Review memory", None,
                      '<div class="doc">%s</div>' % "\n".join(memory)))
    notes = "\n".join(filter(None, [
        _simple_list_section("assumptions", "Assumptions", report.get("assumptions"), False),
        _process_section(report.get("process_notes"))]))
    if notes:
        panes.append(("notes", "Assumptions & notes", None, '<div class="doc">%s</div>' % notes))
    return panes


_HANDOFF_META = ("forge", "project", "number", "branch", "source_branch", "web_url", "change_state",
                 "head_sha", "repo_root", "title", "verdict", "ticket")
_HANDOFF_FINDING = ("id", "severity", "dimensions", "file", "line", "anchor_side", "title",
                    "impact", "fix_md", "evidence", "body_md", "recommendation_md", "aside_md",
                    "verification_status", "repro", "what_would_confirm")
_SCRIPT_JSON_ESCAPES = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026",
                        "\u2028": "\\u2028", "\u2029": "\\u2029"}


def handoff_payload(report, report_path=None):
    """Everything a fresh session needs to act on the triage export without the report JSON.

    The page appends this, rendered as text, after the validated decisions block. It is
    convenience context for a human-directed session and never a source for posted text.
    """
    meta = report["meta"]
    payload = {"label": export_label(meta), "seat": meta.get("seat", "author"),
               "target": meta["target"]}
    payload.update({key: meta[key] for key in _HANDOFF_META if meta.get(key) not in (None, "")})
    if report_path:
        payload["report_path"] = os.path.abspath(report_path)
    payload["findings"] = [{key: finding[key] for key in _HANDOFF_FINDING
                            if finding.get(key) not in (None, "", [])}
                           for finding in report["findings"]]
    return payload


def _handoff_script(report, report_path=None):
    if not report["findings"]:
        return ""
    encoded = json.dumps(handoff_payload(report, report_path), ensure_ascii=False,
                         separators=(",", ":"))
    for raw, escaped in _SCRIPT_JSON_ESCAPES.items():
        encoded = encoded.replace(raw, escaped)
    return '<script type="application/json" id="handoff-data">%s</script>' % encoded


def _content(report, report_path=None):
    panes = _panes(report)
    out = ['<div class="app">', _topnav(report, panes)]
    run = report.get("run") or {}
    deep = run.get("deep") or {}
    if deep and run.get("incomplete"):
        unreached = ", ".join(deep.get("unreached_areas") or [])
        checker = _checker_failure_text(deep)
        overrun = _budget_overrun_text(deep)
        body = " ".join(part for part in (
            ("Unreached areas: %s." % unreached) if unreached else "",
            ("%s." % checker) if checker else "",
            ("%s." % overrun) if overrun else "") if part)
        body = body or "Some deep checks did not finish."
        out.append(_banner("warning", "Incomplete review.", _esc(body)))
    out.append('<div class="panes">')
    for index, (pane_id, label, _, html) in enumerate(panes):
        out.append('<section class="pane%s" id="pane-%s" role="tabpanel" aria-labelledby="tab-%s">' %
                   (" is-active" if index == 0 else "", pane_id, pane_id))
        out.append(html)
        out.append("</section>")
    out.extend(["</div>", _footer(report), "</div>"])
    handoff = _handoff_script(report, report_path)
    if handoff:
        out.append(handoff)
    return "\n".join(out)


def _render_html_prepared(report, template_text, report_path=None):
    output = replace_slot(template_text, "title", "<title>%s</title>" % _esc(report["meta"]["title"]))
    output = replace_slot(output, "main", _content(report, report_path))
    if "<!-- slot:" in output:
        raise ValueError("unreplaced template slot remains")
    return output


def render_html(report, template_text, report_path=None):
    """Validate a report and splice fully rendered content into the HTML shell."""
    prepared, _ = _prepare_report(report)
    return _render_html_prepared(prepared, template_text, report_path)


def _raw_md(value):
    return value.strip() if isinstance(value, str) else ""


def _render_md_prepared(report):
    meta = report["meta"]
    findings = report["findings"]
    tally = _tally(findings)
    run = report.get("run") or {}
    deep = run.get("deep") if isinstance(run.get("deep"), dict) else {}
    lines = ["# %s" % meta["title"], "", "## 1. Summary", ""]
    if _raw_md(meta.get("standfirst_md")):
        lines.extend([_raw_md(meta["standfirst_md"]), ""])
    lines.extend(["**Tally:** %d Must fix · %d Should fix · %d Nit" %
                  (tally["must"], tally["should"], tally["nit"]), "",
                  "**Verdict:** %s" % meta["verdict"], "",
                  "**Seat:** %s" % meta.get("seat", "author"), ""])
    if run.get("source_access"):
        source_line = "**Source access:** %s" % run["source_access"]
        if run.get("source_access") == "diff-only":
            source_line += " — every finding is unverified. %s" % run.get("source_access_reason", "")
        lines.extend([source_line.rstrip(), ""])
    if run.get("incomplete"):
        failed = ", ".join(_string_list(run.get("dimensions_failed")))
        if not failed and deep.get("unreached_areas"):
            failed = "unreached areas (%s)" % ", ".join(deep["unreached_areas"])
        checker = _checker_failure_text(deep)
        overrun = _budget_overrun_text(deep)
        if failed:
            text = "%s did not finish; this report is not a clean bill." % failed
            if checker:
                text += " %s." % checker
            if overrun:
                text += " %s." % overrun
        elif checker or overrun:
            text = "%s; this report is not a clean bill." % ". ".join(
                part for part in (checker, overrun) if part)
        elif deep:
            text = "some deep checks did not finish; this report is not a clean bill."
        else:
            text = "some lenses did not finish; this report is not a clean bill."
        lines.extend(["**Incomplete:** %s" % text, ""])
    dimensions = _string_list(run.get("dimensions_run"))
    if dimensions:
        lines.extend(["**Dimensions run:** %s" % ", ".join(dimensions), ""])
    models = run.get("models") if isinstance(run.get("models"), dict) else {}
    if models:
        lines.extend(["**Models:** %s" % ", ".join("%s: %s" % kv for kv in sorted(models.items())), ""])
    skipped = run.get("dimensions_skipped") if isinstance(run.get("dimensions_skipped"), list) else []
    if skipped:
        labels = []
        for item in skipped:
            if isinstance(item, dict):
                labels.append("%s (%s)" % (item.get("name", "unknown"), item.get("why", "not applicable")))
            else:
                labels.append(str(item))
        lines.extend(["**Dimensions skipped:** %s" % ", ".join(labels), ""])
    if run.get("diff_size"):
        lines.extend(["**Diff size:** %s" % run["diff_size"], ""])
    if run.get("coverage"):
        lines.extend(["**Coverage:** %s" % run["coverage"], ""])
    if _since_text(run):
        lines.extend(["**Reviewed since:** %s" % _since_text(run), ""])
    if _hunk_coverage_text(deep):
        lines.extend(["**Hunk coverage:** %s" % _hunk_coverage_text(deep), ""])
    if not run.get("incomplete") and _budget_overrun_text(deep):
        lines.extend(["**Time budget:** %s" % _budget_overrun_text(deep), ""])
    probe = report.get("mutation_probe")
    if isinstance(probe, dict):
        lines.extend(["**Mutation probe:** run — %s mutants, %s killed, %s survived" %
                      (probe.get("mutants", 0), probe.get("killed", 0), probe.get("survived", 0)), ""])
    guidance = _string_list(run.get("guidance"))
    if guidance:
        lines.extend(["**Guidance loaded:** %s" % ", ".join(guidance), ""])
    if _raw_md(run.get("notes_md")):
        lines.extend([_raw_md(run["notes_md"]), ""])
    if deep.get("areas"):
        lines.extend(["**Area map:**", ""])
        for area in deep["areas"]:
            title = area.get("title") or ", ".join(_string_list(area.get("files")))
            files = ", ".join(_string_list(area.get("files")))
            questions = "; ".join(_string_list(area.get("questions")))
            status = str(area.get("status", "pending"))
            if area.get("status") == "read_only_degraded" and area.get("degraded_reason"):
                status += " (%s)" % area["degraded_reason"]
            hunk_text = _area_hunk_text(area)
            lines.append("- **%s** — %s%s; %s%s%s" %
                         (area.get("id", ""), title, " (`%s`)" % files if files else "",
                          status, "; %s" % hunk_text if hunk_text else "",
                          "; %s" % questions if questions else ""))
            for identifier, file, header in _unexamined_hunks(area, deep):
                lines.append("  - Unexamined: `%s` %s %s" % (identifier, file, header))
        lines.append("")

    risk = report.get("risk")
    if isinstance(risk, dict):
        lines.extend(["## 2. Risk Assessment", ""])
        if risk.get("level"):
            lines.extend(["**Risk level:** %s" % risk["level"], ""])
        if _raw_md(risk.get("verbatim_md")):
            lines.extend([_raw_md(risk["verbatim_md"]), ""])
        for caveat in risk.get("caveats") or []:
            if isinstance(caveat, dict):
                lines.extend(["**Caveat — %s:**" % caveat.get("title", "Caveat"), "",
                              _raw_md(caveat.get("body_md")), ""])

    lines.extend(["## 3. Findings", "",
                  "**Derived tally:** %d Must fix · %d Should fix · %d Nit" %
                  (tally["must"], tally["should"], tally["nit"]), ""])
    if findings:
        for index, finding in enumerate(findings):
            lines.extend(["### %s — %s" % (finding["id"], finding["title"]), "",
                          "**Severity:** %s" % finding["severity"], "",
                          "**Dimensions:** %s" % ", ".join(finding["dimensions"]), "",
                          "**Location:** `%s:%s`" % (finding["file"], finding["line"]), ""])
            if finding.get("evidence"):
                lines.extend(["**Evidence:** %s" % finding["evidence"], ""])
            if finding.get("verification_status") == "plausible":
                lines.extend(["**Status:** Plausible — what would confirm: %s" %
                              finding["what_would_confirm"], ""])
            repro = finding.get("repro")
            if isinstance(repro, dict) and repro.get("command") and repro.get("output"):
                command = "$ %s" % repro["command"]
                longest = max((len(run) for run in re.findall(r"`+", command + repro["output"])), default=0)
                fence = "`" * max(3, longest + 1)
                lines.extend(["**Reproduction:**", "", fence, command, repro["output"], fence, ""])
            if finding.get("impact"):
                lines.extend(["**Impact:** %s" % finding["impact"], ""])
            if _raw_md(finding.get("body_md")):
                lines.extend([_raw_md(finding["body_md"]), ""])
            if _raw_md(finding.get("recommendation_md")):
                lines.extend(["**Recommendation:**", "", _raw_md(finding["recommendation_md"]), ""])
            if index != len(findings) - 1:
                lines.extend(["---", ""])
    else:
        lines.extend(["No findings — see per-dimension notes below.", ""])
        notes = run.get("clean_notes") or []
        if notes:
            for note in notes:
                if isinstance(note, dict):
                    lines.extend(["**%s:**" % note.get("dimension", "Review"), "",
                                  _raw_md(note.get("note_md")), ""])
        else:
            lines.extend(["No per-dimension clean notes were supplied.", ""])

    dropped = deep.get("checked_and_dropped") or []
    if dropped:
        lines.extend(["<details><summary>Checked and dropped (%d)</summary>" % len(dropped), ""])
        for item in dropped:
            lines.append("- `%s:%s` — **%s**: %s" %
                         (item["file"], item["line"], item["title"], item["reason"]))
        lines.extend(["", "</details>", ""])
    memory_lines = _memory_sections_md(report)
    if memory_lines:
        lines.extend(memory_lines)
    lines.extend(["## 4. Assumptions", ""])
    assumptions = report.get("assumptions") or []
    if assumptions:
        lines.extend("- %s" % (value if isinstance(value, str) else str(value)) for value in assumptions)
    else:
        lines.append("- None recorded.")
    lines.extend(["", "## 5. Recommendations", ""])
    recommendations = report.get("recommended_order") or []
    if recommendations:
        lines.extend("%d. %s" % (index, value if isinstance(value, str) else str(value))
                     for index, value in enumerate(recommendations, 1))
    else:
        lines.append("1. No follow-up actions recorded.")
    return "\n".join(lines).rstrip() + "\n"


def render_md(report):
    """Validate a report and render the five-section Markdown backend."""
    prepared, _ = _prepare_report(report)
    return _render_md_prepared(prepared)


def _template_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "assets", "report.html"))


def _write_text(path, text):
    """Replace `path` with `text` atomically, so a failed write never truncates the previous file."""
    directory = os.path.dirname(path) or "."
    fd, temp = tempfile.mkstemp(prefix=".%s." % os.path.basename(path), suffix=".tmp", dir=directory,
                                text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="backslashreplace") as handle:
            handle.write(text)
        os.replace(temp, path)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def _error(message):
    print(json.dumps({"error": str(message)}, indent=2))
    return 2


def main(argv=None):
    """Run the report renderer CLI and print exactly one JSON metadata object."""
    parser = argparse.ArgumentParser(description="Render a combined code-review report.")
    parser.add_argument("--in", dest="in_path", required=True)
    parser.add_argument("--format", choices=("html", "md", "both"), default="html")
    parser.add_argument("--out-dir")
    parser.add_argument("--out")
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.out and args.format == "both":
            raise ValueError("--out is valid only with --format html or md")
        with open(args.in_path, "r", encoding="utf-8") as handle:
            report = json.load(handle)
        prepared, warnings = _prepare_report(report)
        slug = target_slug(prepared["meta"])
        out_dir = args.out_dir or os.environ.get("REVIEW_OUT_DIR") or "/tmp"
        out_dir = os.path.abspath(out_dir)
        html_path = None
        md_path = None
        html_text = None
        md_text = None
        if args.format in ("html", "both"):
            with open(_template_path(), "r", encoding="utf-8") as handle:
                template = handle.read()
            html_text = _render_html_prepared(prepared, template, args.in_path)
            html_path = os.path.abspath(args.out) if args.out else os.path.join(out_dir, "review-%s-findings.html" % slug)
        if args.format in ("md", "both"):
            md_text = _render_md_prepared(prepared)
            md_path = os.path.abspath(args.out) if args.out else os.path.join(out_dir, "review-%s-findings.md" % slug)
        if html_path:
            os.makedirs(os.path.dirname(html_path) or ".", exist_ok=True)
            _write_text(html_path, html_text)
        if md_path:
            os.makedirs(os.path.dirname(md_path) or ".", exist_ok=True)
            _write_text(md_path, md_text)

        opened = False
        if html_path and not args.no_open:
            try:
                opened = bool(webbrowser.open(pathlib.Path(html_path).resolve().as_uri()))
            except Exception:
                opened = False
        tally = _tally(prepared["findings"])
        meta = {
            "slug": slug,
            "format": args.format,
            "html": html_path,
            "md": md_path,
            "report": os.path.abspath(args.in_path),
            "opened": opened,
            "tally": tally,
            "verdict": prepared["meta"]["verdict"],
            "seat": prepared["meta"].get("seat", "author"),
            "head_sha": prepared["meta"].get("head_sha"),
            "source_access": (prepared.get("run") or {}).get("source_access"),
            "highlighter": highlight.backend(),
            "order": [{"id": item["id"], "severity": item["severity"], "file": item["file"],
                       "line": item["line"], "title": item["title"]}
                      for item in prepared["findings"]],
        }
        if html_path and highlight.backend() == "builtin":
            warnings.append("Pygments is not installed, so code outside Python, Bash, JSON, YAML, "
                            "SQL and diff renders uncoloured. Install it with: %s" % highlight.INSTALL_HINT)
        if warnings:
            meta["warnings"] = warnings
        print(json.dumps(meta, indent=2))
        return 0
    except Exception as exc:
        return _error(exc)


if __name__ == "__main__":
    sys.exit(main())
