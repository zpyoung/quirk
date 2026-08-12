---
description: Show ROADMAP.md, or propose a new milestone grouping for the user to ratify. Use when the user asks to see the roadmap, plan milestones, or organize the backlog into a plan.
---

Two modes, chosen by `$ARGUMENTS`: **show** the current roadmap, or **propose/revise** a grouping.
If `$ARGUMENTS` is empty or asks to see/view the roadmap, use show mode. Otherwise, propose mode.

## Show mode

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py roadmap --show --project-dir "$CLAUDE_PROJECT_DIR"
```

This always exits 0. Relay the milestones verbatim. If stdout says "No artifact files found",
suggest `/quirk:artifacts:init`. If it says "no milestones", say so plainly — that's the normal
starting state, not an error.

## Propose/revise mode

1. Gather context — none of this writes anything:
   - Run `roadmap --show` (above) for the current milestones.
   - Run `python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py status --project-dir "$CLAUDE_PROJECT_DIR"` for
     open/unplaced counts.
   - Read `BUGS.md`, `DEFERRED.md`, and `TEST_BACKLOG.md` directly for the full set of open entries
     (ID, title, severity/priority, `Blocked by`) — no single `pm.py` command dumps that detail, and
     reading these files for context is not the write path the "never Edit/Write an artifact"
     rule guards. Never include `PROPOSAL-*` IDs; the roadmap grammar rejects them outright.
2. **This is your judgment call, not the script's.** Group the open entries into ordered
   milestones with a stated rationale (theme, dependency order, what unblocks the most work).
   `pm.py` only validates the grammar of what you propose — it never proposes a grouping.
3. Show the proposed `ROADMAP.md` content to the user as a diff against the current file (or the
   full content if there are no milestones yet). Get explicit approval before writing anything.
4. Once approved, write the proposed content to a scratch file, then validate-and-commit it:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py roadmap --write "$DRAFT_PATH" --project-dir "$CLAUDE_PROJECT_DIR"
```

`$DRAFT_PATH` is a scratch file you write the proposed content to (e.g. via `mktemp`) — never
`ROADMAP.md` itself. `pm.py` reads it, validates it, and atomically writes `ROADMAP.md` only if it
passes.

After the script returns:
1. On exit 0: confirm `ROADMAP.md written` and relay the new milestone list.
2. On exit 2 (malformed draft): relay every finding line verbatim (e.g. `PROPOSAL_IN_ROADMAP`,
   `ROADMAP_LINE_MALFORMED`, an unknown ID). Fix the draft and retry once; if it fails again, stop
   and show the user what's wrong rather than guessing.
3. On exit 3 (can't read the draft file): the scratch file went missing or is unreadable — recreate
   it at `$DRAFT_PATH` and retry.
4. On exit 5 (lock timeout): tell the user nothing was written and offer to retry.
5. On exit 7 (project dir not found): tell the user to check `$CLAUDE_PROJECT_DIR`.
6. On any other non-zero exit: relay stderr verbatim plus a one-line plain-language summary and a
   remediation hint.

User input: $ARGUMENTS
