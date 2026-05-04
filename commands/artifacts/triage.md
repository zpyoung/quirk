---
description: Classify an observation into bug / defer / test-skip / proposal and append a structured entry. Use when the routing destination isn't obvious.
---

You have an observation that needs routing but the user did not specify a category. Your job is to:

1. Classify the observation into ONE of: `bug`, `defer`, `test-skip`, `proposal`.
   - **bug** — concrete defect that exists in the code right now (wrong behavior, error, regression).
   - **defer** — work that is out of scope for the current session (not a defect; just not now).
   - **test-skip** — a test that should exist but was skipped or abbreviated.
   - **proposal** — architectural concern, design suggestion, or unsettled tradeoff that requires human judgment.
2. If two categories are equally plausible, ask the user one clarifying question with the two options. Do NOT pick.
3. Extract the required fields for the chosen category:
   - bug: title, file (path:line), description, severity
   - defer: title, why_deferred, priority
   - test-skip: title, file_under_test, reason_skipped
   - proposal: title, context, recommendation
4. Run the script:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/artifact_append.py <CATEGORY> \
  --project-dir "$CLAUDE_PROJECT_DIR" \
  --field "title=..." \
  ... (one --field per required arg) ...
```

5. Relay the entry ID and destination file to the user. If the script exited non-zero, relay stderr and a remediation hint.

The script re-validates required fields per the chosen schema. If your classification was wrong, the entry still lands in plain markdown — the user can move it manually.

User input: $ARGUMENTS
