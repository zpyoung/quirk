# Pi Worker Delta

Appended to the staged prompt when this run's implementer backend is pi-codex. Implementers get the
whole file, including the marked section below; fixers get everything outside the markers.

---

## Status trailer

End your output with exactly one line, written exactly as: `STATUS: <word>`, where `<word>` is one
of `DONE`, `NEEDS_CONTEXT`, `BLOCKED`, or `FAILED`. One line, one key, nothing after it — a
machine-readable summary, not a substitute for the report the core prompt's Return section asks
for. Put the real detail — what changed, what's ambiguous, what's blocking, what broke — in prose
above the trailer. A trailer with nothing above it is as unusable as no trailer at all.

## Do not commit

**Do not commit**, restated: the orchestrator recorded this worktree's HEAD before dispatching you
and compares it against HEAD once you return. A commit moves HEAD — that alone is the check,
regardless of what the commit contains. A mismatch stops the task right there and is surfaced.
Leave your changes uncommitted in the working tree.

## No `Skill` tool

This environment has no `Skill` tool. Any skill referenced above by name — `quirk:test-driven-development`
and other `quirk:*` references — cannot be resolved; do not attempt to invoke one. Its operative
content, where it matters for your task, is included directly in this file.

<!-- IMPLEMENTER-ONLY -->
## Test-driven development

`quirk:test-driven-development`, referenced above, does not resolve here (see "No `Skill` tool").
Follow the same discipline directly: write the failing test first, watch it fail for the reason you
expect — not an import error or a typo — implement, then watch it pass. Do not skip the
failing-test step because the change looks too small to need one; that is exactly the case where it
catches a test that was never wired up.
<!-- /IMPLEMENTER-ONLY -->
