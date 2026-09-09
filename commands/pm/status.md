---
description: Read-only index and doctor findings for the PM backlog — open/in_progress/stalled counts and structural issues. Use when the user asks for backlog health, task status, or "what's stuck."
---

Run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py status --project-dir "$CLAUDE_PROJECT_DIR"
```

This is read-only and always exits 0 — it's index output followed by doctor output, concatenated.
If stdout says "No artifact files found", suggest `/quirk:artifacts:init` and stop.

Then:
1. Relay the index line(s) (open/in_progress/stalled counts, with denominators) and the doctor
   findings verbatim.
2. If doctor reports `STALLED` entries, name them and point to the attempt and refusal counts on
   their `Status` line as the starting point for follow-up.
3. If it reports `AWAITING_INTEGRATION` entries, mention that `/quirk:pm:reconcile` is what
   re-checks them. `cannot evaluate` is not a doctor finding — it appears only in
   `/quirk:pm:reconcile`'s own output, because doctor never touches git.
4. If it reports no findings and nothing is stalled, say so plainly — don't pad a clean report.
5. Do NOT modify any artifact file from this command; it's diagnostic only.

User input: $ARGUMENTS (ignored — this command takes no args)
