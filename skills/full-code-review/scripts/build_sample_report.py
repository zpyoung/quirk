#!/usr/bin/env python3
"""Refill assets/report.html's slot with freshly rendered sample content.

The template ships a worked example inside its own slot so the manual QA gate can
open assets/report.html straight from file://. Hand-maintaining that example lets
it drift from what render_report.py actually emits, so it is generated instead:

    python3 scripts/build_sample_report.py

Run it after any change to the markup builders, then re-check the QA gate.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import render_report as renderer  # noqa: E402

SKILL_ROOT = os.path.dirname(HERE)
TEMPLATE = os.path.join(SKILL_ROOT, "assets", "report.html")
SAMPLE = os.path.join(SKILL_ROOT, "assets", "sample-report.json")


def main():
    import json

    report = json.load(io.open(SAMPLE, encoding="utf-8"))
    prepared, warnings = renderer._prepare_report(report)
    for warning in warnings:
        sys.stderr.write("warning: %s\n" % warning)

    template = io.open(TEMPLATE, encoding="utf-8").read()
    body = renderer._content(prepared)
    filled = renderer.replace_slot(
        template, "main", "<!-- slot:main -->\n%s\n<!-- /slot:main -->" % body)
    filled = renderer.replace_slot(
        filled, "title",
        "<!-- slot:title --><title>%s</title><!-- /slot:title -->"
        % renderer._esc(prepared["meta"]["title"]))
    io.open(TEMPLATE, "w", encoding="utf-8").write(filled)
    print("refilled %s (%d bytes)" % (os.path.relpath(TEMPLATE, SKILL_ROOT), len(filled)))


if __name__ == "__main__":
    main()
