---
description: Record a human decision that an entry is wontfix or superseded, with a reason. Use when the user decides not to do something, or that another entry replaces it — never for work that's actually done.
---

`decide` is the one PM lifecycle transition that removes work from the board without anything
being built, and it is **human-gated — never run it unattended.** Confirming `$ARGUMENTS` back to
the user is not optional ceremony here; it's the whole point of the gate.

<HARD-GATE>
Before running the script, state back to the user in plain language: the exact entry ID, whether
it's becoming `wontfix` or `superseded`, and the exact reason text you're about to record (and, for
`superseded`, the exact `--by` ID). Get explicit confirmation of that specific combination before
invoking `pm.py decide`. Do this every time — even if the user's original message seemed to already
authorize it, even mid-session, even if you're working through a list of several. A restated
"proceed" from the user in direct response to your confirmation counts; an earlier general request
to "clean up the backlog" does not.
</HARD-GATE>

Required: `ID`, `--as` (`wontfix` or `superseded`), and `--reason`. `superseded` additionally
requires `--by <ID>` naming the entry that replaces it. Parse these from `$ARGUMENTS`; ask for
whichever is missing rather than guessing.

After confirmation, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/bin/pm.py decide "$ID" --as "$AS" --reason "$REASON" --project-dir "$CLAUDE_PROJECT_DIR"
```

(add `--by "$BY"` when `--as superseded`)

After the script returns:
1. On exit 0: relay the outcome (`wontfix` or `superseded`). This satisfies any blocker naming this
   entry.
2. On exit 7 (project dir not found): tell the user to check the path they passed.
3. On exit 3 (ledger missing, or `ID` not found): if a ledger file is missing, direct to
   `/quirk:artifacts:init`; otherwise relay the message and check for a typo.
4. On exit 2 (bad argument): relay stderr — missing `--as`, a missing/invalid `--reason`, or
   `superseded` without a valid `--by`. Fix and re-confirm before retrying — don't silently retry
   with a guessed value.
5. On exit 8 (schema v1): direct to `/quirk:pm:migrate`.
6. On exit 4 (corrupt entry): relay stderr verbatim; the ledger itself is malformed for this ID —
   don't guess a fix, show the user.
7. On exit 6 (CAS failure): either the entry is already terminal (`closed`/`wontfix`/`superseded`
   already) or it's a `PROPOSAL` entry, which every PM lifecycle command rejects — `proposals.md`
   keeps its own human vocabulary. Relay stderr and point to `/quirk:pm:status`.
8. On any other non-zero exit: relay stderr verbatim plus a one-line plain-language summary and a
   remediation hint.

User input: $ARGUMENTS
