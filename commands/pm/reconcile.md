---
description: Promote delivered entries to closed by checking whether their commit is reachable from the integration branch. Use when the user wants to sweep for finished work that has since merged.
---

Run in the origin repository, not a worktree — this checks ancestry against the project's own
integration ref. Takes no ID; it sweeps every `delivered` entry in one pass.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py reconcile --project-dir "$CLAUDE_PROJECT_DIR"
```

If `$ARGUMENTS` asks for the stronger check (e.g. "verify", "also check for regressions"), add
`--verify` — it additionally re-runs each entry's probe against the integration ref in a temporary
checkout, catching a post-merge regression the default reachability-only check can't see. This is
heavier; only do it when asked.

This processes many entries per run, so a single exit code describes the run, not any one entry —
read the per-entry outcomes from stdout, not just the exit code.

After the script returns:
1. On exit 0: relay the per-entry outcomes from stdout. Each `delivered` entry lands in one of
   three states, and they mean different things — don't collapse them into "not merged yet":
   - promoted to `closed` — the commit is reachable from the integration branch.
   - still `delivered`, "awaiting integration" — known commit, not yet reachable. Normal; the work
     is done and just hasn't merged.
   - still `delivered`, "cannot evaluate" — reconcile could not determine reachability. Read the
     parenthesised reason, because they need opposite responses: "fetch failed" is transient, so
     offer to re-run. "commit not in destination repo" and "integration ref unresolvable" are not
     transient — re-running gets the same answer, and these need a human to look at the repository
     or the ref.
   Zero promotions in a run is a normal outcome, not a failure.
2. On exit 7 (project dir not found): tell the user to check the path they passed.
3. On exit 3 (ledger missing): direct to `/quirk:artifacts:init`.
4. On exit 8 (schema mismatch): direct to `/quirk:pm:migrate`. Nothing was evaluated — do not
   report this as "nothing to reconcile."
5. On exit 5 (lock timeout): nothing was written; offer to retry.
6. On exit 1 (unexpected error mid-run): relay stderr. Any per-entry write that already completed
   stands — each is its own atomic write — so relay which entries, if any, the stdout shows as
   already promoted before the error.
7. On any other non-zero exit: relay stderr verbatim plus a one-line plain-language summary and a
   remediation hint.

User input: $ARGUMENTS
