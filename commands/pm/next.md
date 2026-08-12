---
description: Report what's ready to work on next and recommend one candidate. Use when the user asks what to work on, what's next, or wants a shortlist of ready backlog entries.
---

Run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py next --project-dir "$CLAUDE_PROJECT_DIR"
```

This is read-only and always exits 0. If stdout says "No artifact files found", suggest
`/quirk:artifacts:init` and stop.

Then:
1. If stdout shows "no ready candidates", relay the explanation it prints (which blockers are open,
   what would unblock the most work) — do not just say "nothing to do."
2. Otherwise, relay the shortlist (up to 5 entries, already sorted by milestone → severity/priority
   → age). **This is your judgment call, not the script's:** recommend exactly one candidate from
   the shortlist, with a stated reason grounded in its content (why it matters now, what it
   unblocks, how it fits the current milestone) — don't just repeat the script's ordering as the
   recommendation. You may argue against the sort if you have a real reason, but never silently
   reorder or drop entries from what the script printed.
3. **Always** report the unplaced count from stdout, even if it's 0 — it's unconditional by design.
   If it's greater than 0, offer to place the unplaced entries on the roadmap (declining is fine).
4. If the user accepts placement, follow the exact same propose → show diff → ratify → write flow
   as `/quirk:pm:roadmap`'s propose mode — placement is a roadmap write and goes through the same
   gate as any other roadmap change. Use `python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py roadmap --write
   <draft> --project-dir "$CLAUDE_PROJECT_DIR"` once approved; see `/quirk:pm:roadmap` for the exit
   codes that write path can return.

User input: $ARGUMENTS (ignored — this command takes no args)
