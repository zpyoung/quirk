---
description: Scaffold typed-artifact files (BUGS, DEFERRED, TEST_BACKLOG, proposals, docs/adr/) into this project.
---

Scaffold typed-artifact files into the current project.

Run this command:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/artifact_init.py --project-dir "$CLAUDE_PROJECT_DIR" $ARGUMENTS
```

Then:
1. Relay the script's stdout (`Created: ...` / `Skipped: ...`) to the user.
2. If the script created artifact files, do NOT continue and read them yourself — they are templates and the schema headers are intentionally inert. Just confirm setup is complete.
3. If the user passed `--force`, mention that timestamped backups were created next to any overwritten files.
4. Suggest one of: `/quirk:artifacts:bug`, `/quirk:artifacts:defer`, `/quirk:artifacts:adr`, or `/quirk:artifacts:review-artifacts` as the next step.

If the script exited non-zero, relay the stderr verbatim and propose how to fix it (e.g., make the project dir writable).
