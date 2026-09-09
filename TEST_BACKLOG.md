<!-- schema-version: 1 -->
<!-- TEST_BACKLOG.md SCHEMA (append only)
Entry format:
## TEST-[N]: [Function or behavior to test]
- **File under test**: [path]
- **Test type**: [unit / integration / e2e]
- **Reason skipped**: [time / complexity / mocking required / TBD]
- **Edge cases to cover**: [list]
- **Priority**: [P1/P2/P3/P4]

Required fields: file_under_test, reason_skipped.
-->

# TEST BACKLOG

Tests that were skipped, abbreviated, or flagged as needing expansion.

Reviewed every 2 weeks. Use `/quirk:artifacts:test-skip` to append.

## TEST-1: No test or CI proves pm.py stays importable without fcntl
- **File under test**: bin/pm.py
- **Test type**: unit
- **Reason skipped**: Out of scope for Phase 1, but this is exactly what made the Windows O_NONBLOCK crash material: pm.py's import chain deliberately avoids fcntl (unlike artifact_append.py:6), so it is the one part of the artifact system that could run on Windows. Nothing currently pins that property, so a future import would silently remove it.
- **Edge cases to cover**: import with fcntl absent from sys.modules; import with os.O_NONBLOCK deleted; the whole read path exercised on a non-POSIX platform
- **Priority**: P3

## TEST-2: No runtime proof that brainstorming and SDD resolve quirk:writing-specs
- **File under test**: skills/writing-specs/SKILL.md
- **Test type**: e2e
- **Reason skipped**: Cannot run in-session: the loaded plugin resolves from the installed path (~/ProjectWorkspaces/quirk-workspace/quirk/skills/), not this worktree, so the edited skills are not live. Requires a plugin reinstall from this branch. Structural coverage exists (tests/test_writing_specs_skill.py pins the contract literals; relative links, the 24-skill count, and zero stale writing-tech-spec references are all verified); what is unproven is runtime routing.
- **Edge cases to cover**: brainstorming step 9 reads logic-spec.md and writes logic.md with all six required sections; brainstorming halts at the user review gate; subagent-driven-development Step 2 resolves quirk:writing-specs and reads tech-spec.md when the complexity gate fires; executing-plans Step 0 does the same on the no-subagent path
- **Priority**: P2

