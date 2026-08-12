---
description: Return an in_progress entry to open, recording why, without losing its attempt history. Use when the user is giving up on the current attempt but not the entry itself.
---

Required: the entry `ID` and a `--reason` — the entire value of `park` over silently abandoning
work is the recorded why, so ask if the user hasn't given one.

Parse `$ARGUMENTS` for the ID and reason.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py park "$ID" --reason "$REASON" --project-dir "$CLAUDE_PROJECT_DIR"
```

Pass `--project-dir` pointed at the origin project if you're parking on behalf of work done
elsewhere; otherwise it defaults to the current project.

After the script returns:
1. On exit 0: relay `parked`. The entry is back to `open` with its attempt and refusal counts
   preserved — it isn't gone, and a later `/quirk:pm:start` picks up the next attempt number.
2. On exit 7 (project dir not found): tell the user to check the path they passed.
3. On exit 3 (ledger missing, or `ID` not found): if a ledger file is missing, direct to
   `/quirk:artifacts:init`; otherwise relay the message and check for a typo.
4. On exit 2 (bad argument): relay stderr — almost always a missing, empty, or invalid `--reason`
   (it can't contain a newline or an em dash). Ask for a plain-text reason and retry.
5. On exit 8 (schema v1): direct to `/quirk:pm:migrate`.
6. On exit 4 (corrupt entry): relay stderr verbatim; the ledger itself is malformed for this ID —
   don't guess a fix, show the user.
7. On exit 6 (CAS failure): the entry isn't `in_progress` — relay stderr (it names the state found)
   and point to `/quirk:pm:status` to see what it actually is.
8. On any other non-zero exit: relay stderr verbatim plus a one-line plain-language summary and a
   remediation hint.

User input: $ARGUMENTS
