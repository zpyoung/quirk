---
description: Finish work on an in_progress entry — re-run its probe against HEAD and mark it delivered. Use when the user believes a fix is done and ready to close out.
---

Required: the entry `ID` (e.g. `BUG-7`). Parse it from `$ARGUMENTS`.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py finish "$ID" --project-dir "$CLAUDE_PROJECT_DIR"
```

`--project-dir` must name the checkout the work was committed in — `finish` probes and records
*that* directory's `HEAD`. In Phase 2 `start` is `--here`-only, so the ledger and the code are the
same checkout and the default is almost always right. Do not point it at some other project on
behalf of work done elsewhere: the probe would run against the wrong tree and record the wrong
commit. Cross-checkout finishing arrives with the handoff packet in a later phase.

After the script returns:
1. On exit 0: relay `delivered (<commit>)`. This is `delivered`, not `closed` — say so if the user
   assumes the entry is fully closed. `/quirk:pm:reconcile`, run later from the origin, is what
   promotes it to `closed` once the commit is reachable from the integration branch.
2. On exit 7 (project dir not found): tell the user to check the path they passed.
3. On exit 3 (ledger missing, or `ID` not found): if a ledger file is missing, direct to
   `/quirk:artifacts:init`; otherwise relay the message and check for a typo.
4. On exit 8 (schema v1): direct to `/quirk:pm:migrate`.
5. On exit 4 (corrupt entry): relay stderr verbatim — most likely a missing or malformed `Probe`
   field, which shouldn't happen on an entry that went through `start`. Don't guess a fix; show the
   user.
6. On exit 6 (CAS failure): the entry isn't `in_progress` — relay stderr (it names the state found)
   and point to `/quirk:pm:status` to see what it actually is.
7. On exit 10 (precondition failed): relay stderr verbatim — it names which precondition failed:
   worktree root doesn't match the project directory (`finish` from the wrong checkout), working
   tree is dirty (commit first), or a git failure reading tree status or `HEAD`.
8. On exit 9 (probe refused): **relay the exact recorded outcome from stderr, not just
   "refused"** — this is the difference between "still broken" and "the probe itself is broken":
   - the message names a failing result — the fix genuinely isn't done yet; the entry stays
     `in_progress` and the refusal count went up. Keep working.
   - the message names `missing` or `error` — the probe itself broke (nodeid renamed/removed,
     import error, timeout). This isn't evidence about the fix; it means the probe needs
     investigating before `finish` can say anything meaningful.
9. On any other non-zero exit: relay stderr verbatim plus a one-line plain-language summary and a
   remediation hint.

User input: $ARGUMENTS
