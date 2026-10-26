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

## TEST-3: Two complete Sonnet deep-mode recall acceptance runs
- **File under test**: skills/full-code-review/references/deep.md
- **Test type**: e2e
- **Reason skipped**: Sonnet runtime dispatch failed Anthropic OAuth refresh with invalid_grant. Historical eval-run1/eval-run2 were invalidated because they reused old lenses, supplied literal timings, seeded prompts, and claimed unvisited areas complete. No qualifying recall run has been established.
- **Edge cases to cover**: After reauthenticating Anthropic, run every applicable lens and every area twice at 3605fd8777b60646bcad11aba08f83c2c858e6b9 with unseeded prompts, measured whole-run budgets, fresh per-claim checkers, and independent spot checks; score against the corrected answer key.
- **Priority**: P1

## TEST-4: Live-model adjudicator smoke runs not yet run
- **File under test**: skills/full-code-review/references/orchestration.md
- **Test type**: e2e
- **Reason skipped**: The smoke corpus needs live Opus and Sonnet dispatch through the installed plugin, and this build ran in a worktree; CI only checks that the new cases' patches apply. Structural coverage exists: apply_adjudication unit tests, renderer, posting and policy tests, and smoke_check absent/marker tests. The adjudicator and prover prompts (references/lenses/_adjudicator.md, _prover.md) have never run against a live model.
- **Edge cases to cover**: All five existing smoke cases still exit 0 with production statements under complete adjudication; correctness-guarded passes with absent: true; correctness-wrong-fix passes recommendation_contains ceil_div (a correct fix written as (total + size - 1) // size would miss the marker); a run with adjudicator.enabled false still passes all five baseline cases
- **Priority**: P1

