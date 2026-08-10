<!-- schema-version: 2 -->
<!-- DEFERRED.md SCHEMA (append only)
Entry format:
## DEFER-[N]: [Task title]
- **Deferred**: [date]
- **Session context**: [what triggered this]
- **Why deferred**: [out of scope / blocked on / requires decision]
- **Estimated effort**: [S/M/L]
- **Priority**: [P1/P2/P3/P4]
- **Proposed owner**: [Claude / name / unassigned]
- **Blocked by**: [comma-separated BUG-N/DEFER-N/TEST-N, or omit]

Required fields: title, why_deferred, priority.

The fields below are written only by pm.py — never by hand, never via
artifact_append.py. Absent Status means open.
- **Status**: [in_progress / delivered / closed / wontfix / superseded — see /quirk:pm:status]
- **Probe**: [set at `pm start`, updated at `pm finish`]
- **Handoff**: [set at `pm start` when dispatched]
-->

# DEFERRED

Tasks surfaced during sessions but explicitly out of scope for the current work.

Reviewed every sprint planning. Use `/quirk:artifacts:defer` to append.
