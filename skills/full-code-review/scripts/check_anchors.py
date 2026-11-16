"""Check that finding line anchors are real line numbers in the reviewed source."""
import os


def line_count(path):
    """Number of lines in `path` as a forge numbers them: newline-terminated, plus an unterminated tail."""
    with open(path, "rb") as handle:
        data = handle.read()
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def _bounds(line):
    start, _, end = str(line).partition("-")
    return int(start), int(end or start)


def check_anchors(findings, source_root):
    """Split anchors into out-of-range problems and skip notes.

    Each new-side anchor must name lines inside its file at `source_root`, the head the
    specialists read. Old-side anchors point into the pre-change file, and a file absent
    from the source is taken as deleted; both are skipped, the latter with a note. A path
    that resolves outside the source is a problem. Expects findings that already passed
    the renderer's file and line validation.
    """
    root = os.path.realpath(source_root)
    if not os.path.isdir(root):
        raise ValueError("--source-root %s is not a directory" % source_root)
    problems = []
    notes = []
    for finding in findings:
        if finding.get("anchor_side") == "old":
            continue
        anchor = "%s:%s" % (finding["file"], finding["line"])
        path = os.path.realpath(os.path.join(root, finding["file"]))
        if os.path.commonpath([root, path]) != root:
            problems.append("%s (path is outside the review source)" % anchor)
            continue
        if not os.path.isfile(path):
            notes.append("%s is not in the review source; treating it as a deleted file and "
                         "skipping its line check." % finding["file"])
            continue
        start, end = _bounds(finding["line"])
        total = line_count(path)
        if end < start:
            problems.append("%s (range ends before it starts)" % anchor)
        elif end > total:
            problems.append("%s (file has %d lines)" % (anchor, total))
    return problems, notes
