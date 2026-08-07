<!-- schema-version: 1 -->
<!-- TEST_BACKLOG.md SCHEMA (append only)
Entry format:
## TEST-[N]: [Function or behavior to test]
- **File under test**: [path]
- **Test type**: [unit / integration / e2e]
- **Reason skipped**: [time / complexity / mocking required / TBD]
- **Edge cases to cover**: [list]
- **Priority**: [P1/P2/P3/P4]

Required fields: file_under_test, reason_skipped.
-->

# TEST BACKLOG

Tests that were skipped, abbreviated, or flagged as needing expansion.

Reviewed every 2 weeks. Use `/quirk:artifacts:test-skip` to append.

## TEST-1: No test or CI proves pm.py stays importable without fcntl
- **File under test**: bin/pm.py
- **Test type**: unit
- **Reason skipped**: Out of scope for Phase 1, but this is exactly what made the Windows O_NONBLOCK crash material: pm.py's import chain deliberately avoids fcntl (unlike artifact_append.py:6), so it is the one part of the artifact system that could run on Windows. Nothing currently pins that property, so a future import would silently remove it.
- **Edge cases to cover**: import with fcntl absent from sys.modules; import with os.O_NONBLOCK deleted; the whole read path exercised on a non-POSIX platform
- **Priority**: P3

