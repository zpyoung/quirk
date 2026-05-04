---
description: Append a DEFER-N entry to DEFERRED.md for tasks that are out of scope for the current session.
---

The user has surfaced a task to defer. Required fields: `title`, `why_deferred`, `priority` (P1/P2/P3/P4).

Parse `$ARGUMENTS` for these fields. If a required field is missing, ask exactly one clarifying question.

When you have all three fields, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/artifact_append.py defer \
  --project-dir "$CLAUDE_PROJECT_DIR" \
  --field "title=$TITLE" \
  --field "why_deferred=$WHY" \
  --field "priority=$PRIORITY"
```

Optional fields: `session_context`, `estimated_effort` (S/M/L), `proposed_owner`.

After the script returns:
1. On exit 0: relay `DEFER-N: title` and confirm `Logged DEFER-N → DEFERRED.md`.
2. On exit 3: suggest `/quirk:artifacts:init`.
3. On any other non-zero exit: relay stderr verbatim with a remediation hint.

User input: $ARGUMENTS
