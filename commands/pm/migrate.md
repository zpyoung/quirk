---
description: Idempotent v1 → v2 schema upgrade for the ledger files. Use when a pm.py command exits 8 saying a file isn't on schema v2, or the user wants to upgrade an existing typed-artifacts project for PM.
---

Run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py migrate --project-dir "$CLAUDE_PROJECT_DIR"
```

This rewrites only the schema-version marker and schema-comment block in each ledger file — no
entry body is touched. It's safe to re-run: an already-v2 file reports "already v2" and changes
nothing, and a partial run is safe to repeat.

After the script returns:
1. On exit 0: relay the per-file report from stdout (`migrated` / `already v2` / `ROADMAP.md
   created`). Nothing further needed.
2. On exit 7 (project dir not found): tell the user to check `$CLAUDE_PROJECT_DIR`.
3. On exit 3 (ledger file(s) missing): direct to `/quirk:artifacts:init` first — there's nothing to
   migrate until the ledger exists.
4. On exit 8 (a file is newer than this tool understands): this isn't the v1→v2 case migrate fixes
   — relay stderr and tell the user the file needs a newer version of this plugin, not a re-run of
   `migrate`.
5. On exit 5 (lock timeout): nothing was written; offer to retry.
6. On any other non-zero exit: relay stderr verbatim plus a one-line plain-language summary and a
   remediation hint.

User input: $ARGUMENTS (ignored — this command takes no args)
