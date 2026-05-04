---
description: Append a BUG-N entry to BUGS.md. Use when you've noticed a bug you cannot fix in the current scope.
---

The user has surfaced a bug to log. Required fields: `title`, `file` (path:line), `description`, `severity` (critical/high/medium/low).

Parse `$ARGUMENTS` for these fields. If any required field is missing or ambiguous, ask exactly one clarifying question — do NOT guess defaults.

When you have all four fields, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/artifact_append.py bug \
  --project-dir "$CLAUDE_PROJECT_DIR" \
  --field "title=$TITLE" \
  --field "file=$FILE_LINE" \
  --field "description=$DESCRIPTION" \
  --field "severity=$SEVERITY"
```

Optional fields you may also pass if the user provided them: `introduced_by`, `proposed_fix`, `blocker_for`.

After the script returns:
1. On exit 0: relay the `BUG-N: title` line from stdout, then confirm `Logged BUG-N → BUGS.md`. Do not narrate further unless severity is `critical`.
2. On exit 3 (`BUGS.md not found`): tell the user to run `/quirk:artifacts:init` first.
3. On any other non-zero exit: relay stderr verbatim plus a one-line plain-language summary and a remediation hint.

User input: $ARGUMENTS
