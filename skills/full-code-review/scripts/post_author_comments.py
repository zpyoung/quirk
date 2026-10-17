#!/usr/bin/env python3
"""Post approved author-seat findings as inline comments on GitHub or GitLab.

Only findings named with --ids whose built body is marked `post: true` are posted, one
comment each, in the given order. Each confirmed create is written to --out immediately
as a receipt in the shape `review_memory.py save --receipts` reads, so a mid-batch
failure never loses what already posted. The overview receipt has no finding id, so it
goes to a sibling file (`overview_receipt_path`). Rerunning with the same --out resumes:
ids (and the overview) that already have a receipt are skipped. A create that came back
as a plain comment instead of an inline one is recorded in a third sibling file
(`stray_receipt_path`) and that id is not retried until the user deletes the comment and
the entry. The overview's posted and not-posted lists are rebuilt from the receipts, so
they match what actually posted. Never edits, replies to, or resolves notes.
Exit 0 when every requested finding posted or was skipped with a warning; exit 2 on bad
input or a failed create (receipts written so far are kept, and the error names the
failing id).
"""
import argparse
import json
import os
import re
import sys

import comment_body
import render_report
from jsonio import load_object, write_json
from forge import ForgeError, StrayComment, make_forge


class PostFailed(ForgeError):
    """A create failed; `finding_id` is the finding (or "overview") that was being posted.

    `receipt` is set when the comment was created on the forge but could not be recorded
    locally, so the operator can save it by hand instead of reposting.
    """

    def __init__(self, finding_id, cause, warnings=(), receipt=None):
        super().__init__("%s failed to post: %s" % (finding_id, cause), getattr(cause, "code", "unknown"))
        self.finding_id = finding_id
        self.warnings = list(warnings)
        self.receipt = receipt


_write = write_json


def _load(path):
    return load_object(path, os.path.basename(str(path)))


def overview_receipt_path(out):
    """Where the overview note's receipt is kept, beside the finding receipts in `out`."""
    return os.path.splitext(str(out))[0] + ".overview.json"


def stray_receipt_path(out):
    """Where plain comments created in place of inline ones are recorded, beside `out`."""
    return os.path.splitext(str(out))[0] + ".stray.json"


_LINE_RE = re.compile(r"(\d+)(?:-\d+)?")


def _line(value, finding_id="finding"):
    """Return the first line of a `N` or `N-M` anchor; ValueError names `finding_id` otherwise."""
    match = _LINE_RE.fullmatch(str(value).strip())
    if not match:
        raise ValueError("%s has a line that is not a number or a range: %r" % (finding_id, value))
    return int(match.group(1))


def _same(left, right):
    return left is not None and str(left) == str(right)


DELTA_REFUSAL = "delta review (--since) is report-only; it cannot be posted to the forge"


def _refuse_delta(report, context):
    """Raise ValueError when the context or the report's run belongs to a delta review."""
    run = report.get("run") if isinstance(report, dict) else None
    if "since" in context or (isinstance(run, dict) and "since" in run):
        raise ValueError(DELTA_REFUSAL)


def _check_binding(meta, change, refs, source_branch=None):
    """Require the report to describe the change the context will write to.

    Author reports carry no `head_sha`, so the head is checked only when present and the
    source branch only when both sides name one.
    """
    if meta.get("target") != "change":
        raise ValueError("author posting requires a change-request report")
    if not _same(meta.get("number"), change.get("number")):
        raise ValueError("report change request does not match the context")
    if meta.get("project") != change.get("project"):
        raise ValueError("report project does not match the context")
    if meta.get("head_sha") is not None and meta["head_sha"] != refs.get("head"):
        raise ValueError("report head does not match the context")
    if meta.get("source_branch") and source_branch and meta["source_branch"] != source_branch:
        raise ValueError("report source branch does not match the context")


def _save(path, value, finding_id, created, warnings):
    """Write a receipt; an OSError after a confirmed create becomes a PostFailed carrying it."""
    try:
        _write(path, value)
    except OSError as exc:
        raise PostFailed(
            finding_id, "created on the forge but its receipt was not saved (%s): %s" % (exc, created),
            warnings, receipt=created) from exc


def _posted_overview(prepared, bodies, receipts):
    """The overview with its posted and not-posted lists rebuilt from `receipts`."""
    plan = bodies.get("overview_plan")
    if not isinstance(plan, dict):
        return bodies["overview"]
    posted = [item for item in plan.get("posted") or [] if item.get("finding_id") in receipts]
    dropped = [{"id": item["finding_id"], "reason": "not posted", "disposition": "Not posted",
                "fingerprint": item.get("fingerprint")}
               for item in plan.get("posted") or [] if item.get("finding_id") not in receipts]
    body, _ = comment_body.overview_body(
        prepared, seat="author", posted=posted, omitted=list(plan.get("omitted") or []) + dropped,
        report_sha256=bodies.get("report_sha256"))
    return body


def post(report, context, bodies, ids, out, overview=False, forge=None):
    """Post the approved findings; return (receipts, warnings).

    Receipts already in `out` are kept and their ids are not posted again. Every id is
    validated before the first create (it must name a finding of the report, with a numeric
    line), `bodies` must have been built from this exact report, and the report must be for
    the context's change (and head, when the report names one). A delta-review (`since`)
    context or report is refused. The change must still be open
    at the context's head; a closed change raises the forge's ForgeError. Raises ValueError for
    any of those or a context with no forge, and PostFailed (a ForgeError) on a failed create or
    when a created comment's receipt cannot be written.
    """
    _refuse_delta(report, context)
    prepared, _ = render_report._prepare_report(report)
    findings = {f["id"]: f for f in prepared["findings"]}
    change = context.get("change") or {}
    refs = context.get("refs") or {}
    _check_binding(prepared["meta"], change, refs, context.get("source_branch"))
    forge = forge or make_forge(context.get("forge", "gitlab"), change.get("host"), change.get("project"))
    if forge is None:
        raise ValueError("author posting requires a forge")
    target_refs = {"base_sha": refs.get("base"), "start_sha": refs.get("start"), "head_sha": refs.get("head")}
    entries = bodies.get("findings") or {}
    if bodies.get("report_sha256") != comment_body._report_digest(report):
        raise ValueError("bodies were not built from this report; rebuild them with comment_body.py author")
    unknown = [i for i in ids if i not in findings or entries.get(i) is None]
    if unknown:
        raise ValueError("%s is not a finding in this report" % ", ".join(unknown))
    lines = {i: _line(findings[i]["line"], i) for i in ids}
    _, live_refs, _ = forge.live_change(change["number"])
    if live_refs["head_sha"] != refs.get("head"):
        raise ValueError("the change head moved since the review was prepared; re-run the review")
    receipts = _load(out) if os.path.exists(out) else {}
    strays_out = stray_receipt_path(out)
    strays = _load(strays_out) if os.path.exists(strays_out) else {}
    warnings = []
    pairs = comment_body.path_pairs(context.get("diff"))
    for finding_id in ids:
        entry = entries[finding_id]
        finding = findings[finding_id]
        if finding_id in receipts:
            warnings.append("%s already has a receipt; skipped" % finding_id)
            continue
        if finding_id in strays:
            warnings.append("%s left a plain comment (%s); delete it and its entry in %s to retry; skipped"
                            % (finding_id, strays[finding_id].get("url"), os.path.basename(strays_out)))
            continue
        if finding.get("verification_status") == "plausible":
            warnings.append("%s is a plausible finding and cannot be posted; skipped" % finding_id)
            continue
        if not entry.get("post"):
            warnings.append("%s is not eligible to post (decision, floor, or already posted); skipped" % finding_id)
            continue
        if finding["file"] in (context.get("unanchorable_files") or []):
            warnings.append("%s is on a file whose diff the forge collapsed; not posted" % finding_id)
            continue
        pair = pairs.get(finding["file"], {"old": finding["file"], "new": finding["file"]})
        position = forge.inline_target(target_refs, pair["old"], pair["new"], lines[finding_id],
                                       context.get("diff"), finding.get("anchor_side") or "new")
        if position is None:
            warnings.append("%s anchors on a line outside the diff; not posted" % finding_id)
            continue
        try:
            receipts[finding_id] = forge.post_inline(change["number"], entry["body"], position, refs.get("head"))
        except StrayComment as exc:
            strays[finding_id] = {"discussion_id": exc.discussion_id, "note_id": exc.note_id, "url": exc.url}
            _save(strays_out, strays, finding_id, {finding_id: strays[finding_id]}, warnings)
            raise PostFailed(finding_id, exc, warnings) from exc
        except ForgeError as exc:
            raise PostFailed(finding_id, exc, warnings) from exc
        _save(out, receipts, finding_id, {finding_id: receipts[finding_id]}, warnings)
    overview_out = overview_receipt_path(out)
    if overview and bodies.get("overview") and not os.path.exists(overview_out):
        try:
            overview_receipt = forge.post_overview(change["number"], _posted_overview(prepared, bodies, receipts))
        except ForgeError as exc:
            raise PostFailed("overview", exc, warnings) from exc
        _save(overview_out, overview_receipt, "overview", {"overview": overview_receipt}, warnings)
    return receipts, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description="Post approved author-seat findings as inline comments.")
    ap.add_argument("--report", required=True)
    ap.add_argument("--context", required=True)
    ap.add_argument("--bodies", required=True)
    ap.add_argument("--ids", required=True, help="comma-separated finding IDs the user approved")
    ap.add_argument("--out", required=True)
    ap.add_argument("--overview", action="store_true")
    args = ap.parse_args(argv)
    ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    receipts = {}
    try:
        context = _load(args.context)
        if context.get("seat") != "author":
            raise ValueError("author posting requires an author-seat context")
        receipts, warnings = post(_load(args.report), context, _load(args.bodies), ids,
                                  args.out, overview=args.overview)
    except (ForgeError, ValueError, OSError, KeyError) as exc:
        try:
            receipts = _load(args.out)
        except (OSError, ValueError):
            receipts = {}
        failure = {"error": str(exc), "posted": sorted(receipts)}
        if isinstance(exc, PostFailed):
            failure["failed_id"] = exc.finding_id
            failure["warnings"] = exc.warnings
            if exc.receipt:
                failure["unsaved_receipt"] = exc.receipt
        print(json.dumps(failure, indent=2))
        return 2
    print(json.dumps({"posted": sorted(receipts), "warnings": warnings,
                      "out": os.path.abspath(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
