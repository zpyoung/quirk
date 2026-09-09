---
description: Promote delivered entries to closed by checking whether their commit is reachable from the integration branch. Use when the user wants to sweep for finished work that has since merged.
---

Run in the origin repository, not a worktree — this checks ancestry against the project's own
integration ref. The sweep takes no ID; it walks every `delivered` entry in one pass.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py reconcile --project-dir "$CLAUDE_PROJECT_DIR"
```

There is a second mode, `--close`, described at the bottom of this file. It is **human-gated and
never run unattended** — do not reach for it while handling an ordinary sweep.

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

## `--close` — the human-ratified close

Rebase, cherry-pick and squash break commit identity, so work that genuinely landed can never be
proved reachable by ancestry. Those entries surface as `AWAITING_INTEGRATION`, then `UNDETERMINED`
once they age past the threshold. `--close` is how a human resolves one, and it is the only way an
entry reaches `closed` without ancestry proving it.

<HARD-GATE>
Never run this unattended, and never as part of handling a sweep. State back to the user the exact
entry ID, the exact full 40-character SHA you are about to record as `integrated:`, and the exact
reason text — then get explicit confirmation of that specific combination. `decide` is not the
alternative here: `wontfix` and `superseded` both mean the work was not done, which is the opposite
of what this records.
</HARD-GATE>

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py reconcile --close "$ID" \
  --integrated "$FULL_SHA" --reason "$REASON" --project-dir "$CLAUDE_PROJECT_DIR"
```

The SHA is the **rewritten** commit — the one that actually landed on the integration branch, not
the one the worker originally reported. The entry must currently be `delivered`.

Unlike the sweep, this targets one entry, so its exit code describes that entry. Checks run in this
order, so the first matching condition is what you get:
1. On exit 0: relay the entry ID and the recorded SHA.
2. On exit 7 (project dir not found): tell the user to check the path they passed.
3. On exit 3 (ledger missing, or `ID` not found): if a ledger file is missing, direct to
   `/quirk:artifacts:init`; otherwise relay the message and check for a typo in the ID.
4. On exit 2: `--integrated` is not a full 40-character SHA, is not a commit this repo knows, or is
   not an ancestor of the integration ref; or `--reason` contains a newline, the ` — ` delimiter, or
   an HTML comment. A human asserting closure still cannot record a SHA the repository cannot
   resolve — relay which of those it was and re-confirm before retrying.
5. On exit 8 (schema mismatch): direct to `/quirk:pm:migrate`. Nothing was written.
6. On exit 4 (corrupt entry): a heading or a lifecycle field on this entry is malformed or
   duplicated. Relay stderr; do not guess a fix.
7. On exit 6 (CAS failure): the entry is not `delivered`, or it changed since you read it. Re-read
   with `/quirk:pm:status` and re-confirm with the user rather than retrying blind.
8. On exit 5 (lock timeout): another process holds the ledger lock; nothing was written. Offer to
   retry.
9. On any other non-zero exit: relay stderr verbatim plus a one-line plain-language summary and a
   remediation hint.

User input: $ARGUMENTS
