<!-- quirk-typed-artifacts:trigger -->
## Surface Routing (typed-artifacts)

When you notice something you cannot act on in this session, do NOT bury
it in prose with phrases like "pre-existing", "out of scope", or "skipped
for brevity". Route it via the `typed-artifacts` skill (auto-loads on
those phrases) or use one of:
- `/quirk:artifacts:bug`        — log a bug to BUGS.md
- `/quirk:artifacts:defer`      — log out-of-scope work to DEFERRED.md
- `/quirk:artifacts:test-skip`  — log a skipped test to TEST_BACKLOG.md
- `/quirk:artifacts:triage`     — let Claude classify the observation
- `/quirk:artifacts:adr`        — record an architectural decision

Review cadence: BUGS.md every PR · DEFERRED.md every sprint planning ·
TEST_BACKLOG.md every 2 weeks · proposals.md / docs/adr/ monthly with
architect. Run `/quirk:artifacts:review-artifacts` to scan all four.
<!-- /quirk-typed-artifacts:trigger -->
