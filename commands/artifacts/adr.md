---
description: Create a new Architecture Decision Record (ADR) in docs/adr/. Use to record a significant architectural decision.
---

Create a new ADR. The argument is the title.

If `$ARGUMENTS` is empty or whitespace, ask the user for the title — do not guess.

Run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/adr_create.py \
  --project-dir "$CLAUDE_PROJECT_DIR" \
  --title "$ARGUMENTS"
```

After the script returns:
1. On exit 0: relay `ADR-NNNN: title` from stdout. Read the new file you just created and prompt the user to fill in Context, Decision, Consequences. Status defaults to `proposed`.
2. On exit 2 (empty kebab): tell the user the title needs letters or digits and ask for a revised one.
3. On any other non-zero exit: relay stderr verbatim with a remediation hint.

User input: $ARGUMENTS
