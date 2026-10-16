#!/usr/bin/env python3
"""Post approved author-seat findings as inline comments on GitHub or GitLab.

Only findings named with --ids whose built body is marked `post: true` are posted, one
comment each, in the given order. Each confirmed create is written to --out immediately
as a receipt in the shape `review_memory.py save --receipts` reads, so a mid-batch
failure never loses what already posted. The overview receipt has no finding id, so it
goes to a sibling file (`overview_receipt_path`). Rerunning with the same --out resumes:
ids (and the overview) that already have a receipt are skipped. Never edits, replies to,
or resolves notes.
Exit 0 when every requested finding posted or was skipped with a warning; exit 2 on bad
input or a failed create (receipts written so far are kept, and the error names the
failing id).
"""
import argparse
import json
import os
import sys

import comment_body
import render_report
from jsonio import load_object, write_json
from forge import ForgeError, make_forge


class PostFailed(ForgeError):
    """A create failed; `finding_id` is the finding (or "overview") that was being posted."""

    def __init__(self, finding_id, cause, warnings=()):
        super().__init__("%s failed to post: %s" % (finding_id, cause), getattr(cause, "code", "unknown"))
        self.finding_id = finding_id
        self.warnings = list(warnings)


_write = write_json


def _load(path):
    return load_object(path, os.path.basename(str(path)))


def overview_receipt_path(out):
    """Where the overview note's receipt is kept, beside the finding receipts in `out`."""
    return os.path.splitext(str(out))[0] + ".overview.json"


def _line(value):
    return int(str(value).split("-", 1)[0])


def post(report, context, bodies, ids, out, overview=False, forge=None):
    """Post the approved findings; return (receipts, warnings).

    Receipts already in `out` are kept and their ids are not posted again. Every id is
    validated before the first create, and `bodies` must have been built from this exact
    report. Raises ValueError for a stale bodies file or an id that is not a postable
    finding of the report, and PostFailed (a ForgeError) on a failed create.
    """
    prepared, _ = render_report._prepare_report(report)
    findings = {f["id"]: f for f in prepared["findings"]}
    change = context.get("change") or {}
    forge = forge or make_forge(context.get("forge", "gitlab"), change.get("host"), change.get("project"))
    refs = context.get("refs") or {}
    target_refs = {"base_sha": refs.get("base"), "start_sha": refs.get("start"), "head_sha": refs.get("head")}
    entries = bodies.get("findings") or {}
    if bodies.get("report_sha256") != comment_body._report_digest(report):
        raise ValueError("bodies were not built from this report; rebuild them with comment_body.py author")
    unknown = [i for i in ids if i not in findings or entries.get(i) is None]
    if unknown:
        raise ValueError("%s is not a finding in this report" % ", ".join(unknown))
    receipts = _load(out) if os.path.exists(out) else {}
    warnings = []
    pairs = comment_body.path_pairs(context.get("diff"))
    for finding_id in ids:
        entry = entries[finding_id]
        finding = findings[finding_id]
        if finding_id in receipts:
            warnings.append("%s already has a receipt; skipped" % finding_id)
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
        position = forge.inline_target(target_refs, pair["old"], pair["new"], _line(finding["line"]),
                                       context.get("diff"), finding.get("anchor_side") or "new")
        if position is None:
            warnings.append("%s anchors on a line outside the diff; not posted" % finding_id)
            continue
        try:
            receipts[finding_id] = forge.post_inline(change["number"], entry["body"], position, refs.get("head"))
        except ForgeError as exc:
            raise PostFailed(finding_id, exc, warnings) from exc
        _write(out, receipts)
    overview_out = overview_receipt_path(out)
    if overview and bodies.get("overview") and not os.path.exists(overview_out):
        try:
            overview_receipt = forge.post_overview(change["number"], bodies["overview"])
        except ForgeError as exc:
            raise PostFailed("overview", exc, warnings) from exc
        _write(overview_out, overview_receipt)
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
        print(json.dumps(failure, indent=2))
        return 2
    print(json.dumps({"posted": sorted(receipts), "warnings": warnings,
                      "out": os.path.abspath(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
