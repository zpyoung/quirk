<!-- schema-version: 2 -->
<!-- TEST_BACKLOG.md SCHEMA (append only)
Entry format:
## TEST-[N]: [Function or behavior to test]
- **Logged**: [date, auto-stamped like Observed/Deferred/Proposed on every other type]
- **File under test**: [path]
- **Test type**: [unit / integration / e2e]
- **Reason skipped**: [time / complexity / mocking required / TBD]
- **Edge cases to cover**: [list]
- **Priority**: [P1/P2/P3/P4]
- **Blocked by**: [comma-separated BUG-N/DEFER-N/TEST-N, or omit]

Required fields: file_under_test, reason_skipped.

The fields below are written only by pm.py — never by hand, never via
artifact_append.py. Absent Status means open.
- **Status**: [in_progress / delivered / closed / wontfix / superseded — see /quirk:pm:status]
- **Probe**: [set at `pm start`, updated at `pm finish`]
- **Handoff**: [set at `pm start` when dispatched]
-->

# TEST BACKLOG

Tests that were skipped, abbreviated, or flagged as needing expansion.

Reviewed every 2 weeks. Use `/quirk:artifacts:test-skip` to append.
