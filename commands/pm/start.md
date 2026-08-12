---
description: Start work on a tracked entry — baseline a probe (it must currently fail) and mark the entry in_progress. Use when the user is ready to begin work on a specific BUG/DEFER/TEST entry.
---

The user wants to start work on an entry. Required: the entry `ID` (e.g. `BUG-7`) and a probe spec
`VERB:ARG`. Probe verbs: `test:<nodeid>` (pytest by default), `grep:<pattern> [-- <paths>]`, or
`none`.

Parse `$ARGUMENTS` for the ID and probe. **`--probe` is required and never defaults** — if the user
hasn't stated one, ask; do not silently pick `none` for them. Working unverified is a real choice
they have to make explicitly.

This build runs locally only — never pass `--repo`. Dispatch to another repo is a later phase and
the script refuses the flag if you pass it.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py start "$ID" --probe "$PROBE" --here --project-dir "$CLAUDE_PROJECT_DIR"
```

After the script returns:
1. On exit 0: relay `started (attempt N)`, then say what the baseline actually established. For a
   `test:` or `grep:` probe it failed as expected — that red baseline is the evidence `finish`
   later measures against. For `--probe none` **no probe ran at all**; say so plainly rather than
   claiming a failure that never happened, and note the entry will deliver unverified. Either way,
   `/quirk:pm:finish` closes the loop.
2. On exit 7 (project dir not found): tell the user to check `$CLAUDE_PROJECT_DIR`.
3. On exit 3 (ledger missing, or `ID` not found): if a ledger file is missing, direct to
   `/quirk:artifacts:init`; if the ID just isn't found, relay the message and check for a typo.
4. On exit 2 (bad argument): relay stderr — usually a missing `--probe`, a malformed probe spec, or
   (if you passed it) a rejected `--repo`. Fix and retry.
5. On exit 8 (schema v1): direct to `/quirk:pm:migrate`.
6. On exit 4 (corrupt/ambiguous entry): relay stderr verbatim — the ledger itself is malformed for
   this ID (a duplicate heading, or one with no title). Don't guess which block is right; tell the
   user.
7. On exit 6 (CAS failure): the entry isn't `open` — relay stderr (it names the state found); most
   often it's already `in_progress`, or it's a `PROPOSAL` entry, which the PM lifecycle rejects
   outright. Point the user at `/quirk:pm:status` to see the current state.
8. On exit 9 (probe refused at baseline): **relay the exact recorded outcome from stderr, not just
   "refused"** — it tells you what actually happened:
   - outcome `pass` — the probe already passes, so it can't discriminate this entry. Supply a
     different probe, or start with `--probe none` if the user wants to accept an unverified close.
   - outcome `missing` — the nodeid wasn't found/collected. Almost always a typo in the nodeid;
     check it before retrying.
   - outcome `error` — the probe errored, timed out, or hit a runner usage error. This is an
     environment/probe problem, not evidence the fix is unneeded — investigate the probe itself.
9. On any other non-zero exit: relay stderr verbatim plus a one-line plain-language summary and a
   remediation hint.

User input: $ARGUMENTS
