<!-- schema-version: 2 -->
<!-- BUGS.md SCHEMA (append only — do not rewrite existing entries)
Entry format:
## BUG-[N]: [Short title]
- **Observed**: [date or session ID]
- **File**: [path/to/file.ts:line]
- **Description**: [what the bug is]
- **Introduced by**: [this session / unknown / commit SHA]
- **Severity**: [critical / high / medium / low]
- **Proposed fix**: [one sentence]
- **Blocker for**: [what this would break]
- **Blocked by**: [comma-separated BUG-N/DEFER-N/TEST-N, or omit]

Required fields: title, file, description, severity.

The fields below are written only by pm.py — never by hand, never via
artifact_append.py. Absent Status means open.
- **Status**: [in_progress / delivered / closed / wontfix / superseded — see /quirk:pm:status]
- **Probe**: [set at `pm start`, updated at `pm finish`]
- **Handoff**: [set at `pm start` when dispatched]
-->

# BUGS

Bugs noticed during sessions but not fixed in the current scope.

Reviewed every PR. Use `/quirk:artifacts:bug` to append. Do not edit older
entries' IDs; manual edits to fix typos are fine.
