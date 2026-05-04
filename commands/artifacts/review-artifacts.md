---
description: Read-only summary of all typed-artifact entries (bugs, deferred work, test backlog, proposals, ADRs).
---

Run a read-only review of all artifact files in this project. No mutation.

Run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/artifact_review.py --project-dir "$CLAUDE_PROJECT_DIR"
```

Then:
1. Render the script's stdout to the user verbatim (it's already grouped by file).
2. Identify the top 3 highest-severity / highest-priority items across all artifacts and surface them as a "Suggested triage order" list.
3. Flag any entries that look stale (e.g., DEFER-N items older than 30 days, BUG-N referencing files that no longer exist). Do NOT modify any artifact files.

User input: $ARGUMENTS (ignored — this command takes no args)
