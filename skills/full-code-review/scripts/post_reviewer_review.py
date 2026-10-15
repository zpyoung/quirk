#!/usr/bin/env python3
"""Stage, atomically publish, and conclude reviewer-seat GitLab reviews.

The irreversible bulk publish is a separate, explicitly confirmed command. All note
bodies are rebuilt from trusted report JSON by comment_body; normalized triage contributes
only the chosen slot, the reviewer's optional note, and an optional support-reply target
that is re-resolved against the trusted report before use.
"""
import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys

import review_memory  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comment_body  # noqa: E402
import render_report  # noqa: E402
from forge import ForgeError, positive_int as _positive_int, valid_sha as _valid_sha  # noqa: E402
from forge import change_label  # noqa: E402
from forge import gitlab as _gitlab  # noqa: E402

SCHEMA = 1
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
POST_SLOTS = {"fix": "Blocking", "later": "Non-blocking", "detail": "Question"}
ALL_SLOTS = {"fix": "Blocking", "later": "Non-blocking", "detail": "Question",
             "ignore": "Drop", "none": "Undecided"}


ReviewError = ForgeError


def _run(cmd, input_text=None, timeout=120):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, input=input_text,
                              timeout=timeout, shell=False)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


# Late-bound so a test's replacement of the module-level _run/_api is honored.
def _late_run(cmd, input_text=None, timeout=120):
    return _run(cmd, input_text=input_text, timeout=timeout)


def _late_api(host, method, endpoint, payload=None, timeout=120):
    return _api(host, method, endpoint, payload, timeout)


def _emit(value):
    print(json.dumps(value, indent=2, sort_keys=True))


def _write(path, value):
    target = os.path.abspath(path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temp = target + ".tmp"
    with open(temp, "w", encoding="utf-8") as fh:
        json.dump(value, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(temp, target)


def _load(path, label):
    try:
        with open(path, encoding="utf-8") as fh:
            value = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError("could not read %s: %s" % (label, exc))
    if not isinstance(value, dict):
        raise ReviewError("%s must be a JSON object" % label)
    return value


def _api(host, method, endpoint, payload=None, timeout=120):
    return _gitlab.api(_late_run, host, method, endpoint, payload, timeout)


def _base(project, number):
    return _gitlab.mr_path(project, number)


def _identity(host):
    return _gitlab.identity(_late_api, host)


def _mr(host, project, number):
    return _gitlab.merge_request(_late_api, host, project, number)


def _context(value):
    if value.get("seat") != "reviewer":
        raise ReviewError("reviewer delivery requires a detected reviewer seat")
    change = value.get("change")
    refs = value.get("refs")
    if not isinstance(change, dict) or not isinstance(refs, dict):
        raise ReviewError("review context is missing change or refs")
    host = change.get("host")
    project = change.get("project")
    if not isinstance(host, str) or not host:
        raise ReviewError("review context is missing change.host")
    if not isinstance(project, str) or not project:
        raise ReviewError("review context is missing change.project")
    number = _positive_int(change.get("number"), "change.number")
    expected_user_id = _positive_int(change.get("current_user_id"), "change.current_user_id")
    expected_username = change.get("current_username")
    if not isinstance(expected_username, str) or not expected_username:
        raise ReviewError("review context is missing change.current_username")
    expected_head = _valid_sha(refs.get("head"), "refs.head")
    expected_base = _valid_sha(refs.get("base"), "refs.base")
    expected_start = _valid_sha(refs.get("start"), "refs.start")
    if change.get("sha") and change.get("sha") != expected_head:
        raise ReviewError("review context change sha does not match refs.head")
    return {
        "host": host, "project": project, "number": number,
        "expected_user_id": expected_user_id, "expected_username": expected_username,
        "expected_head": expected_head, "expected_base": expected_base,
        "expected_start": expected_start,
        "seat_source": change.get("seat_source", "detected"),
    }


def _revalidate(ctx):
    user = _identity(ctx["host"])
    if str(user["id"]) != str(ctx["expected_user_id"]) or user["username"] != ctx["expected_username"]:
        raise ReviewError("authenticated GitLab identity changed since the review was prepared")
    data, refs, author = _mr(ctx["host"], ctx["project"], ctx["number"])
    author_id = _positive_int(author.get("id"), "change author id")
    # a reviewer seat the user chose on a co-authored change is allowed on their own change
    if str(author_id) == str(user["id"]) and ctx.get("seat_source") != "chosen":
        raise ReviewError("change author now matches the authenticated user; reviewer delivery is blocked")
    return data, refs


def _list_drafts(host, project, number):
    return _gitlab.list_drafts(_late_api, host, project, number)


def _draft_summary(item):
    return _gitlab.draft_summary(item)


_report_digest = review_memory._report_digest


def _body_digest(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()

def _memory_snapshot(report):
    memory = report.get("memory") if isinstance(report, dict) else None
    snapshot = memory.get("snapshot") if isinstance(memory, dict) else None
    return snapshot if isinstance(snapshot, dict) else None




def _prepare_memory_report(raw_report, context, ctx):
    """Refresh and reconcile a memory report against live discussions.

    This is deliberately before any draft is created: an unavailable or
    mismatched cross-check must never result in a partially posted review.
    """
    snapshot = _memory_snapshot(raw_report)
    if snapshot is None:
        return raw_report, None, []
    try:
        review_memory.validate_snapshot(snapshot, context)
    except Exception as exc:
        raise ReviewError("memory snapshot binding failed: %s" % exc)
    try:
        discussions = review_memory.fetch_discussions(
            ctx["host"], ctx["project"], ctx["number"], api=_api)
    except Exception as exc:
        raise ReviewError("memory discussion cross-check failed: %s" % exc)
    live_snapshot = copy.deepcopy(snapshot)
    live_snapshot["discussions"] = discussions
    live_snapshot["discussions_available"] = True
    reconciled = review_memory.reconcile(raw_report, context, live_snapshot)
    prepared, warnings = render_report._prepare_report(reconciled)
    return reconciled, prepared, warnings


def _trusted_inputs(report, decisions, context):
    prepared, warnings = render_report._prepare_report(report)
    meta = prepared["meta"]
    if meta.get("seat") != "reviewer" or meta.get("target") != "change":
        raise ReviewError("report must be a reviewer-seat change-request report")
    ctx = _context(context)
    if meta.get("number") != ctx["number"]:
        raise ReviewError("report change request does not match review context")
    if meta.get("project") != ctx["project"]:
        raise ReviewError("report project does not match review context")
    if meta.get("head_sha") != ctx["expected_head"]:
        raise ReviewError("report head does not match review context")
    if decisions.get("schema") != 1 or decisions.get("seat") != "reviewer":
        raise ReviewError("decisions must be normalized reviewer-seat triage output")
    if decisions.get("target") != change_label(meta.get("forge"), ctx["number"]):
        raise ReviewError("decision target does not match review context")
    if decisions.get("head_sha") != ctx["expected_head"]:
        raise ReviewError("decision head does not match review context")
    if decisions.get("report_sha256") != _report_digest(report):
        raise ReviewError("decisions were not validated against this exact report JSON")
    rows = decisions.get("decisions")
    if not isinstance(rows, list):
        raise ReviewError("decisions.decisions must be a list")
    by_id = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ReviewError("decisions contain a malformed row")
        finding_id = row["id"]
        if finding_id in by_id:
            raise ReviewError("decisions contain duplicate id %s" % finding_id)
        slot = row.get("slot")
        if slot not in ALL_SLOTS or row.get("disposition") != ALL_SLOTS[slot]:
            raise ReviewError("decision %s has an invalid slot/disposition" % finding_id)
        if not isinstance(row.get("note", ""), str):
            raise ReviewError("decision %s note must be a string" % finding_id)
        reply_note_id = row.get("reply_note_id")
        if reply_note_id is not None and (isinstance(reply_note_id, bool)
                                          or not isinstance(reply_note_id, int)):
            raise ReviewError("decision %s reply_note_id must be an integer" % finding_id)
        by_id[finding_id] = row
    expected = [finding["id"] for finding in prepared["findings"]]
    if set(by_id) != set(expected):
        raise ReviewError("decision finding IDs do not match the report")
    if not expected and decisions.get("zero_findings") is not True:
        raise ReviewError("zero-findings delivery requires the explicit validator artifact")
    if expected and decisions.get("zero_findings"):
        raise ReviewError("zero_findings cannot be set when findings exist")
    return prepared, by_id, ctx, warnings


def _line_number(value):
    match = re.match(r"^(\d+)(?:-\d+)?$", str(value).strip())
    if not match or int(match.group(1)) <= 0:
        raise ReviewError("inline finding line must be a positive line or range")
    return int(match.group(1))


def _path_pairs(diff_text):
    pairs = {}
    current = None
    for line in str(diff_text or "").splitlines():
        match = re.match(r"^diff --git a/(.*?) b/(.*)$", line)
        if match:
            old_path, new_path = match.groups()
            current = {"old": old_path, "new": new_path}
            pairs[new_path] = current
        elif current and line.startswith("rename from "):
            current["old"] = line[len("rename from "):]
        elif current and line.startswith("rename to "):
            old_key = current["new"]
            current["new"] = line[len("rename to "):]
            pairs.pop(old_key, None)
            pairs[current["new"]] = current
    return pairs


def _changed_paths(host, project, old_head, new_head):
    return _gitlab.changed_paths(_late_api, host, project, old_head, new_head)


def _reply_target(finding, reply_note_id):
    """Return the unresolved, not-own human_context entry for `reply_note_id` on a trusted finding, else None."""
    for entry in render_report.open_human_threads(finding):
        if (not isinstance(entry.get("note_id"), bool)
                and entry.get("note_id") == reply_note_id
                and entry.get("discussion_id") not in (None, "")):
            return entry
    return None


def _plan(prepared, by_id, context, refs, changed_paths=None):
    """Plan the notes to stage: inline findings first, then support replies, plus what is omitted.

    A reply target comes from the trusted report's unresolved `human_context`, never from the
    triage paste; a target that no longer resolves falls back to an inline finding with a warning.
    """
    pairs = _path_pairs(context.get("diff"))
    inline = []
    replies = []
    omitted = []
    warnings = []
    changed_paths = changed_paths or set()
    head_sha = (prepared.get("meta") or {}).get("head_sha")
    floor = render_report.severity_floor(prepared)
    for finding in prepared["findings"]:
        decision = by_id[finding["id"]]
        memory = finding.get("memory") if isinstance(finding.get("memory"), dict) else {}
        fingerprint = memory.get("fingerprint")
        if finding["file"] in changed_paths:
            omitted.append({"id": finding["id"], "reason": "head moved in this file",
                            "disposition": decision["disposition"], "fingerprint": fingerprint})
            continue
        if memory.get("suppress_post") is True:
            thread = memory.get("thread") if isinstance(memory.get("thread"), dict) else {}
            omitted.append({
                "id": finding["id"],
                "reason": "already posted (%s)" % (memory.get("state") or "carried"),
                "disposition": decision["disposition"],
                "decision": decision,
                "memory_state": memory.get("state"),
                "thread_url": thread.get("url"),
                "fingerprint": fingerprint,
            })
            continue
        slot = decision["slot"]
        if slot in POST_SLOTS and render_report.below_floor(finding, floor):
            omitted.append({"id": finding["id"], "reason": "below the posting floor (%s)" % floor,
                            "disposition": decision["disposition"], "fingerprint": fingerprint})
            continue
        if slot not in POST_SLOTS:
            omitted.append({"id": finding["id"], "reason": decision["disposition"],
                            "disposition": decision["disposition"], "fingerprint": fingerprint})
            continue
        disposition = POST_SLOTS[slot]
        if finding["severity"] == "Nit" and disposition != "Non-blocking":
            warnings.append("%s is a Nit; %s was normalized to Non-blocking." %
                            (finding["id"], disposition))
            disposition = "Non-blocking"
        note = decision.get("note", "")
        line = _line_number(finding["line"])
        entry = {"finding_id": finding["id"], "disposition": disposition,
                 "severity": finding["severity"], "file": finding["file"], "line": line,
                 "fingerprint": fingerprint}
        reply_note_id = decision.get("reply_note_id")
        target = _reply_target(finding, reply_note_id) if reply_note_id is not None else None
        if reply_note_id is not None and target is None:
            warnings.append("%s: reply target note %s is no longer an unresolved discussion; "
                            "posting as a normal inline finding." % (finding["id"], reply_note_id))
        if target is not None:
            body, body_warnings = comment_body.support_body(
                finding, disposition=disposition, discussion_id=str(target["discussion_id"]),
                note_id=reply_note_id, note=note, head_sha=head_sha)
            warnings.extend(body_warnings)
            entry.update({"kind": "reply", "body": body,
                          "discussion_id": str(target["discussion_id"]), "note_id": reply_note_id,
                          "author": str(target.get("author") or "")})
            replies.append(entry)
            continue
        body, body_warnings = comment_body.finding_body(
            finding, seat="reviewer", lead=disposition, note=note, head_sha=head_sha)
        warnings.extend(body_warnings)
        pair = pairs.get(finding["file"], {"old": finding["file"], "new": finding["file"]})
        entry.update({
            "kind": "inline", "body": body,
            "position": _gitlab.inline_position(refs, pair["old"], pair["new"], line),
        })
        inline.append(entry)
    return inline + replies, omitted, warnings


def _cleanup_commands(state):
    return _gitlab.cleanup_commands(state)


def _reconcile_orphans(state, failed_body):
    """Fold drafts GitLab committed without a usable response into the cleanup set.

    A create POST can commit server-side even when its response is lost or
    malformed; such a draft never reaches state["created"], so cleanup built
    from recorded IDs alone would strand it to block the next run. Staging only
    starts from an empty draft set, so any unrecorded live draft is an orphan.
    """
    try:
        live = _list_drafts(state["host"], state["project"], state["number"])
    except Exception as exc:
        state["cleanup_warning"] = ("could not re-list drafts after the staging failure; "
                                    "cleanup commands may be incomplete: %s" % exc)
        return
    known = {item["draft_id"] for item in state.get("created", [])}
    failed_digest = _body_digest(failed_body) if isinstance(failed_body, str) else None
    orphans = []
    unrecognized = []
    for item in live:
        draft_id = _positive_int(item.get("id"), "draft id")
        if draft_id in known:
            continue
        note = item.get("note") if isinstance(item.get("note"), str) else ""
        digest = _body_digest(note)
        # only the failed POST can have committed without an ack, so only a
        # body match proves ownership; anything else may be the user's own draft
        if digest == failed_digest:
            orphans.append({"draft_id": draft_id, "body_sha256": digest,
                            "matches_failed_note": True})
        else:
            unrecognized.append(_draft_summary(item))
    if orphans:
        state["reconciled"] = orphans
    if unrecognized:
        state["unrecognized_drafts"] = unrecognized


def stage(args):
    try:
        raw_report = _load(args.report, "report")
        decisions = _load(args.decisions, "decisions")
        context = _load(args.context, "review context")
        prepared, by_id, ctx, prep_warnings = _trusted_inputs(raw_report, decisions, context)
        memory_enabled = _memory_snapshot(raw_report) is not None
        if memory_enabled:
            _, live_prepared, memory_warnings = _prepare_memory_report(raw_report, context, ctx)
            prepared = live_prepared
            prep_warnings = list(prep_warnings) + list(memory_warnings)
            # Reconciliation can add/remove only classification metadata; IDs and
            # prose remain bound to the exact raw report and decision artifact.
            by_id = {row["id"]: row for row in decisions["decisions"]}
        _, live_refs = _revalidate(ctx)
        # head partitioning can't salvage a moved diff basis: the findings were
        # judged against a diff GitLab no longer serves, so only a rerun is safe
        if (live_refs["base_sha"] != ctx["expected_base"]
                or live_refs["start_sha"] != ctx["expected_start"]):
            raise ReviewError("MR base/start diff refs changed since the review was prepared "
                              "(target branch moved or the diff was refreshed); re-run the review")
        moved = live_refs["head_sha"] != ctx["expected_head"]
        changed = set()
        affected = []
        if moved:
            changed = _changed_paths(ctx["host"], ctx["project"], ctx["expected_head"], live_refs["head_sha"])
            affected = [finding["id"] for finding in prepared["findings"] if finding["file"] in changed]
            if not args.allow_unaffected:
                raise HeadMoved(ctx["expected_head"], live_refs["head_sha"], sorted(changed), affected,
                                [f["id"] for f in prepared["findings"] if f["id"] not in affected])
        drafts = _list_drafts(ctx["host"], ctx["project"], ctx["number"])
        if drafts:
            raise ExistingDrafts([_draft_summary(item) for item in drafts])
        memory_save = None
        if memory_enabled:
            try:
                memory_save = review_memory.commit_report(raw_report, decisions)
            except Exception as exc:
                raise ReviewError("memory decision save failed: %s" % exc)
            if not isinstance(memory_save, dict):
                raise ReviewError("memory decision save returned an invalid response")
            prep_warnings += list(memory_save.get("warnings") or [])
        posted, omitted, plan_warnings = _plan(prepared, by_id, context, live_refs,
                                               changed_paths=changed if moved else None)
        head_note = None
        if moved:
            head_note = ("review built at `%s`; only findings in files unchanged at `%s` are included. "
                         "Omitted affected findings: %s." %
                         (ctx["expected_head"], live_refs["head_sha"], ", ".join(affected) or "none"))
        titles = {finding["id"]: finding["title"] for finding in prepared["findings"]}
        overview, overview_warnings = comment_body.overview_body(
            prepared, seat="reviewer",
            posted=[{"kind": item["kind"], "finding_id": item["finding_id"],
                     "disposition": item["disposition"], "fingerprint": item["fingerprint"],
                     "title": titles.get(item["finding_id"])} for item in posted],
            omitted=omitted, report_sha256=_report_digest(raw_report), head_note=head_note)
        plan_warnings = plan_warnings + overview_warnings
        notes = [{"kind": "overview", "finding_id": None, "body": overview}] + [
            dict(item, label="reply \u2192 @%s" % item["author"]) if item["kind"] == "reply" else item
            for item in posted]
        state = {
            "schema": SCHEMA, "host": ctx["host"], "project": ctx["project"], "number": ctx["number"],
            "expected_user_id": ctx["expected_user_id"], "expected_username": ctx["expected_username"],
            "seat_source": ctx["seat_source"],
            "report_head_sha": ctx["expected_head"], "publish_head_sha": live_refs["head_sha"],
            "diff_refs": live_refs, "report_sha256": _report_digest(raw_report),
            "created": [], "preview": notes, "omitted": omitted,
            "warnings": prep_warnings + plan_warnings, "published": False,
            "memory_enabled": memory_enabled,
            "memory_report": raw_report if memory_enabled else None,
            "memory_decisions": decisions if memory_enabled else None,
            "completion": {"offered": ["approve", "request-changes", "comment-only"],
                           "suggested": "request-changes" if any(
                               by_id[finding["id"]]["slot"] == "fix" and finding["severity"] != "Nit"
                               for finding in prepared["findings"])
                                        else "approve"},
        }
        _write(args.out, state)
        current_note = None
        for note in notes:
            current_note = note
            data = _gitlab.create_draft(_late_api, ctx["host"], ctx["project"], ctx["number"],
                                        _gitlab.draft_payload(note))
            draft_id = _positive_int(data.get("id") if isinstance(data, dict) else None, "created draft id")
            if any(item["draft_id"] == draft_id for item in state["created"]):
                raise ReviewError("GitLab returned duplicate created draft id %s" % draft_id)
            state["created"].append({"draft_id": draft_id, "kind": note["kind"],
                                     "finding_id": note.get("finding_id"),
                                     "fingerprint": note.get("fingerprint"),
                                     "body_sha256": _body_digest(note["body"])})
            _write(args.out, state)
        state["staged"] = True
        state["cleanup_commands"] = _cleanup_commands(state)
        _write(args.out, state)
        _emit(state)
        return 0
    except HeadMoved as exc:
        _emit(exc.payload)
        return 3
    except ExistingDrafts as exc:
        _emit({"error": "pre-existing draft notes block staging", "drafts": exc.drafts})
        return 4
    except Exception as exc:
        state = locals().get("state")
        if isinstance(state, dict):
            state["staged"] = False
            state["error"] = str(exc)
            failed = locals().get("current_note")
            if isinstance(failed, dict):
                state["failed_note"] = {"kind": failed.get("kind"),
                                        "finding_id": failed.get("finding_id")}
                _reconcile_orphans(state, failed.get("body"))
            state["cleanup_commands"] = _cleanup_commands(state)
            _write(args.out, state)
            _emit(state)
        else:
            _emit({"error": str(exc)})
        return 2


class HeadMoved(Exception):
    def __init__(self, old, new, paths, affected, unaffected):
        self.payload = {"error": "MR head moved; publishing is blocked", "head_moved": True,
                        "old_head": old, "new_head": new, "changed_files": paths,
                        "affected_findings": affected, "unaffected_findings": unaffected,
                        "options": ["re-run the review", "after explicit approval, stage only unaffected findings"]}


class ExistingDrafts(Exception):
    def __init__(self, drafts):
        self.drafts = drafts


def _state_context(state):
    if state.get("schema") != SCHEMA:
        raise ReviewError("unsupported staged-review schema")
    host = state.get("host")
    project = state.get("project")
    username = state.get("expected_username")
    if not isinstance(host, str) or not host or not isinstance(project, str) or not project:
        raise ReviewError("staged review is missing host or project")
    if not isinstance(username, str) or not username:
        raise ReviewError("staged review is missing expected_username")
    refs = state.get("diff_refs")
    if not isinstance(refs, dict):
        raise ReviewError("staged review is missing diff_refs")
    return {"host": host, "project": project,
            "number": _positive_int(state.get("number"), "number"),
            "expected_user_id": _positive_int(state.get("expected_user_id"), "expected_user_id"),
            "expected_username": username,
            "expected_head": _valid_sha(state.get("publish_head_sha"), "publish_head_sha"),
            "expected_base": _valid_sha(refs.get("base_sha"), "diff_refs.base_sha"),
            "expected_start": _valid_sha(refs.get("start_sha"), "diff_refs.start_sha"),
            "seat_source": state.get("seat_source", "detected")}


_FINDING_KINDS = ("inline", "reply")


def _discussion_markers(discussions, identity, state=None):
    found = {}
    for discussion in discussions if isinstance(discussions, list) else []:
        if not isinstance(discussion, dict):
            continue
        discussion_id = discussion.get("id")
        notes = discussion.get("notes")
        if not isinstance(notes, list):
            notes = [discussion]
        for note in notes:
            if not isinstance(note, dict):
                continue
            if not review_memory.note_is_from(note, identity.get("username"), identity.get("id")):
                continue
            body = note.get("body")
            if not isinstance(body, str):
                body = note.get("note") if isinstance(note.get("note"), str) else ""
            for fingerprint in review_memory.marker_fingerprints(body):
                note_id = note.get("id")
                url = note.get("url") or note.get("web_url") or discussion.get("web_url")
                if not url and note_id and isinstance(state, dict):
                    url = _gitlab.note_url(state["host"], state["project"], state["number"], note_id)
                found.setdefault(fingerprint, {
                    "discussion_id": discussion_id, "note_id": note_id, "url": url})
    return found


def _memory_publish_crosscheck(state, ctx):
    if not state.get("memory_enabled"):
        return None
    try:
        discussions = review_memory.fetch_discussions(
            ctx["host"], ctx["project"], ctx["number"], api=_api)
    except Exception as exc:
        raise ReviewError("memory discussion cross-check failed before publication: %s" % exc)
    markers = _discussion_markers(
        discussions, {"id": ctx["expected_user_id"], "username": ctx["expected_username"]})
    staged = {item.get("fingerprint") for item in state.get("created", [])
              if item.get("kind") in _FINDING_KINDS and item.get("fingerprint")}
    duplicate = sorted(staged.intersection(markers))
    if duplicate:
        raise ReviewError("memory findings appeared in live discussions; restage before publication: %s" %
                          ", ".join(duplicate))
    open_threads = {str(item.get("id")) for item in discussions
                    if isinstance(item, dict) and not _discussion_resolved(item)}
    stale = sorted({item["discussion_id"] for item in state.get("preview", [])
                    if item.get("kind") == "reply" and item.get("discussion_id") not in open_threads})
    if stale:
        raise ReviewError("support-reply threads were resolved or deleted; restage before publication: %s" %
                          ", ".join(stale))
    return discussions


def _discussion_resolved(discussion):
    return _gitlab.discussion_resolved(discussion)


def _memory_receipts(state, refs, discussions=None):
    if not state.get("memory_enabled"):
        return {}, []
    inline = [item for item in state.get("created", [])
              if item.get("kind") in _FINDING_KINDS and item.get("fingerprint")]
    if not inline:
        return {}, []
    warnings = []
    identity = {"id": state.get("expected_user_id"), "username": state.get("expected_username")}
    markers = _discussion_markers(discussions, identity, state) if discussions is not None else {}
    receipts = {}
    for item in inline:
        fingerprint = item["fingerprint"]
        receipt = {"published": True, "head_sha": refs["head_sha"]}
        receipt.update(markers.get(fingerprint) or {})
        if fingerprint not in markers:
            warnings.append("published finding %s has no recoverable discussion marker" %
                            (item.get("finding_id") or fingerprint))
        receipts[item.get("finding_id")] = receipt
    return receipts, warnings

def publish(args):
    published = False
    already_published = False
    try:
        if not args.confirm:
            raise ReviewError("bulk publication requires --confirm after showing the staged preview")
        state = _load(args.staged, "staged review")
        ctx = _state_context(state)
        if state.get("published"):
            already_published = True
            published = True
            raise ReviewError("this staged review is already marked published")
        if not state.get("staged"):
            raise ReviewError("review staging did not complete")
        _, refs = _revalidate(ctx)
        if refs["head_sha"] != ctx["expected_head"]:
            raise ReviewError("MR head moved after staging; bulk publication is blocked. Run the printed cleanup commands, then re-run or restage unaffected findings.")
        if refs["base_sha"] != ctx["expected_base"] or refs["start_sha"] != ctx["expected_start"]:
            raise ReviewError("MR base/start diff refs changed after staging; bulk publication is blocked. Run the printed cleanup commands, then re-run the review.")
        # Read discussions immediately before the draft listing/equality and
        # bulk call to reduce (but never claim to close) the race.
        _memory_publish_crosscheck(state, ctx)
        drafts = _list_drafts(ctx["host"], ctx["project"], ctx["number"])
        current = {_positive_int(item.get("id"), "draft id") for item in drafts}
        expected = {_positive_int(item.get("draft_id"), "staged draft id") for item in state.get("created", [])}
        if current != expected:
            raise ReviewError("live drafts do not exactly match this staged review (unexpected: %s; missing: %s)" %
                              (sorted(current - expected), sorted(expected - current)))
        _gitlab.bulk_publish(_late_api, ctx["host"], ctx["project"], ctx["number"])
        # Publication is durable before any best-effort ledger work. Never
        # turn a successful irreversible POST into an "unpublished" result.
        published = True
        state["published"] = True
        state["published_head_sha"] = refs["head_sha"]
        post_warnings = []
        try:
            _write(args.staged, state)
        except Exception as exc:
            post_warnings.append("could not persist published marker: %s" % exc)
        if state.get("memory_enabled"):
            try:
                discussions = review_memory.fetch_discussions(
                    ctx["host"], ctx["project"], ctx["number"], api=_api)
                receipts, receipt_warnings = _memory_receipts(state, refs, discussions)
                post_warnings.extend(receipt_warnings)
            except Exception as exc:
                receipts, receipt_warnings = _memory_receipts(state, refs, None)
                post_warnings.append("could not fetch published discussion receipts: %s" % exc)
            try:
                result = review_memory.commit_report(
                    state.get("memory_report"), state.get("memory_decisions"), receipts=receipts)
                if isinstance(result, dict):
                    post_warnings.extend(result.get("warnings") or [])
            except Exception as exc:
                post_warnings.append("could not save published memory receipts: %s" % exc)
            if post_warnings:
                state.setdefault("warnings", []).extend(post_warnings)
            state["memory_receipts"] = receipts
            state["memory_receipt_recovery"] = bool(post_warnings)
            try:
                _write(args.staged, state)
            except Exception as exc:
                post_warnings.append("could not persist published receipt state: %s" % exc)
        result = {"published": True, "draft_ids": sorted(expected),
                  "completion": state.get("completion")}
        if post_warnings:
            result["warnings"] = post_warnings
        _emit(result)
        return 0
    except Exception as exc:
        if already_published:
            _emit({"error": str(exc), "published": True})
            return 2
        if published:
            warnings = list(locals().get("post_warnings") or [])
            warnings.append("publication completed but receipt bookkeeping failed: %s" % exc)
            _emit({"published": True, "warnings": warnings})
            return 0
        value = {"error": str(exc), "published": False}
        if isinstance(locals().get("state"), dict):
            value["staged_draft_ids"] = [item.get("draft_id") for item in state.get("created", [])]
            value["cleanup_commands"] = state.get("cleanup_commands") or _cleanup_commands(state)
        _emit(value)
        return 2


def _request_changes(host, project, number):
    return _gitlab.request_changes(_late_run, host, project, number)


def complete(args):
    try:
        state = _load(args.staged, "staged review")
        ctx = _state_context(state)
        if not state.get("published"):
            raise ReviewError("completion is unavailable until the review is published")
        if state.get("completion_result"):
            raise ReviewError("a completion action has already been recorded for this review")
        _, refs = _revalidate(ctx)
        if refs["head_sha"] != ctx["expected_head"]:
            raise ReviewError("MR head moved after publication; completion action is blocked")
        if args.action == "approve":
            result = _gitlab.approve(_late_api, ctx["host"], ctx["project"], ctx["number"],
                                     ctx["expected_head"])
        elif args.action == "request-changes":
            result = _request_changes(ctx["host"], ctx["project"], ctx["number"])
        else:
            result = {"comment_only": True}
        state["completion_result"] = {"action": args.action, "ok": True}
        _write(args.staged, state)
        _emit({"review_published": True, "completion": args.action, "result": result})
        return 0
    except Exception as exc:
        _emit({"error": str(exc), "review_published": bool(locals().get("state", {}).get("published")),
               "completion": args.action})
        return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stage and publish an isolated reviewer-seat GitLab review.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_stage = sub.add_parser("stage")
    p_stage.add_argument("--report", required=True)
    p_stage.add_argument("--decisions", required=True)
    p_stage.add_argument("--context", required=True)
    p_stage.add_argument("--out", required=True)
    p_stage.add_argument("--allow-unaffected", action="store_true")
    p_publish = sub.add_parser("publish")
    p_publish.add_argument("--staged", required=True)
    p_publish.add_argument("--confirm", action="store_true")
    p_complete = sub.add_parser("complete")
    p_complete.add_argument("--staged", required=True)
    p_complete.add_argument("--action", required=True,
                            choices=("approve", "request-changes", "comment-only"))
    args = parser.parse_args(argv)
    if args.command == "stage":
        return stage(args)
    if args.command == "publish":
        return publish(args)
    return complete(args)


if __name__ == "__main__":
    sys.exit(main())
