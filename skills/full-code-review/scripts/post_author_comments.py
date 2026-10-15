#!/usr/bin/env python3
"""Post approved author-seat findings as inline comments on GitHub or GitLab.

Only findings named with --ids whose built body is marked `post: true` are posted, one
comment each, in the given order. Each confirmed create is written to --out immediately
as a receipt in the shape `review_memory.py save --receipts` reads, so a mid-batch
failure never loses what already posted. Never edits, replies to, or resolves notes.
Exit 0 when every requested finding posted or was skipped with a warning; exit 2 on bad
input or a failed create (receipts written so far are kept).
"""
import argparse
import json
import os
import sys

import render_report
from forge import ForgeError, make_forge


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _write(path, value):
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as fh:
        json.dump(value, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(temp, path)


def _line(value):
    return int(str(value).split("-", 1)[0])


def post(report, context, bodies, ids, out, overview=False, forge=None):
    """Post the approved findings; return (receipts, warnings). Raises ForgeError on a failed create."""
    prepared, _ = render_report._prepare_report(report)
    findings = {f["id"]: f for f in prepared["findings"]}
    change = context.get("change") or {}
    forge = forge or make_forge(context.get("forge", "gitlab"), change.get("host"), change.get("project"))
    refs = context.get("refs") or {}
    target_refs = {"base_sha": refs.get("base"), "start_sha": refs.get("start"), "head_sha": refs.get("head")}
    receipts, warnings = {}, []
    for finding_id in ids:
        entry = (bodies.get("findings") or {}).get(finding_id)
        finding = findings.get(finding_id)
        if entry is None or finding is None:
            raise ValueError("%s is not a finding in this report" % finding_id)
        if not entry.get("post"):
            warnings.append("%s is not eligible to post (decision, floor, or already posted); skipped" % finding_id)
            continue
        if finding["file"] in (context.get("unanchorable_files") or []):
            warnings.append("%s is on a file whose diff the forge collapsed; not posted" % finding_id)
            continue
        position = forge.inline_target(target_refs, finding["file"], finding["file"], _line(finding["line"]),
                                       context.get("diff"), finding.get("anchor_side") or "new")
        if position is None:
            warnings.append("%s anchors on a line outside the diff; not posted" % finding_id)
            continue
        receipts[finding_id] = forge.post_inline(change["number"], entry["body"], position, refs.get("head"))
        _write(out, receipts)
    if overview and bodies.get("overview"):
        receipts["overview"] = forge.post_overview(change["number"], bodies["overview"])
        _write(out, receipts)
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
        if os.path.exists(args.out):
            receipts = _load(args.out)
        print(json.dumps({"error": str(exc), "posted": sorted(k for k in receipts if k != "overview")}, indent=2))
        return 2
    print(json.dumps({"posted": sorted(k for k in receipts if k != "overview"), "warnings": warnings,
                      "out": os.path.abspath(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
