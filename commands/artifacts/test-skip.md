---
description: Append a TEST-N entry to TEST_BACKLOG.md for skipped or abbreviated tests.
---

The user has surfaced a skipped test to log. Required fields: `title`, `file_under_test`, `reason_skipped`.

Parse `$ARGUMENTS`. If a required field is missing, ask exactly one clarifying question.

When you have the required fields, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/artifact_append.py test-skip \
  --project-dir "$CLAUDE_PROJECT_DIR" \
  --field "title=$TITLE" \
  --field "file_under_test=$FILE_UNDER_TEST" \
  --field "reason_skipped=$REASON"
```

Optional fields: `test_type` (unit/integration/e2e), `edge_cases`, `priority` (P1–P4).

After the script returns:
1. On exit 0: relay `TEST-N: title` and confirm `Logged TEST-N → TEST_BACKLOG.md`.
2. On exit 3: suggest `/quirk:artifacts:init`.
3. On any other non-zero exit: relay stderr verbatim with a remediation hint.

User input: $ARGUMENTS
