<!-- schema-version: 1 -->
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

Required fields: title, file, description, severity.
-->

# BUGS

Bugs noticed during sessions but not fixed in the current scope.

Reviewed every PR. Use `/quirk:artifacts:bug` to append. Do not edit older
entries' IDs; manual edits to fix typos are fine.

## BUG-1: Artifact lock files are not gitignored
- **Observed**: 2026-08-06
- **File**: .gitignore:6
- **Description**: artifact_append.py creates .<ARTIFACT>.lock beside each artifact file (bin/artifact_append.py:165), but .gitignore's '.lock' entry matches only a file literally named .lock, not .BUGS.md.lock. Verified: git check-ignore -v .BUGS.md.lock exits 1. artifact_init.py adds no ignore entry either, so every project adopting typed-artifacts accumulates untracked lock files in its root.
- **Introduced by**: pre-dates this session
- **Severity**: low
- **Proposed fix**: Add a '.*.lock' pattern to the templates and have artifact_init.py append it to the target project's .gitignore.
- **Resolved**: 2026-08-07. Fixed differently than proposed: locks moved to .quirk/locks/ which carries its own .gitignore of '*', so no project's root .gitignore is edited and projects that adopted artifacts earlier self-heal on their next append. artifact_init.py also removes legacy root locks. Phase 1 has no Status field, so --index still counts this entry open; see DEFER-1.

## BUG-2: artifact_append.py writes non-atomically while pm.py writes atomically
- **Observed**: 2026-08-06
- **File**: bin/artifact_append.py:175
- **Description**: The append path uses a plain target.write_text(new_text), so a crash mid-write truncates the ledger. bin/pm.py's writers use an atomic temp-file-plus-os.replace helper. Both mutate the same files, so one ledger now has two different crash-safety properties depending on which script touched it last.
- **Introduced by**: pre-dates this session; the asymmetry is new as of the pm.py work
- **Severity**: medium
- **Proposed fix**: Backport the atomic write helper to artifact_append.py.
- **Blocker for**: any claim that the ledger survives a crash mid-append

## BUG-3: Skill(quirk:adversarial-review) returns the command wrapper instead of loading its protocol
- **Observed**: 2026-08-06
- **File**: skills/adversarial-review/SKILL.md
- **Description**: Invoking the skill from a fresh session returns the routing text of commands/adversarial-review.md ('This command only routes to it - do not restate its rules here') rather than SKILL.md's protocol. A second invocation reports the instructions as 'previously loaded' while they are absent from context. subagent-driven-development Step 8 delegates its entire review gate to this skill, so the documented delegation seam does not work as written; the mechanical layer at scripts/adversarial-review had to be driven directly for all five review rounds of this branch.
- **Introduced by**: pre-dates this session
- **Severity**: high
- **Proposed fix**: Reproduce a Skill invocation from a clean session and fix whichever of the command file or the skill resolution is shadowing SKILL.md.
- **Blocker for**: subagent-driven-development's review gate being usable as documented

## BUG-4: artifact_append.py reads and writes with the platform-default encoding
- **Observed**: 2026-08-06
- **File**: bin/artifact_append.py:169
- **Description**: read_text()/write_text() are called with no encoding, so the ledger's on-disk encoding follows each host's locale. A file written on a latin-1 host is not readable as the same text on a utf-8 host. bin/pm.py had to couple its own decode order to this behaviour (platform codec first when that codec is not utf-8) to avoid silently misreading files quirk itself wrote. That coupling is a workaround; this is the root cause.
- **Introduced by**: pre-dates this session
- **Severity**: medium
- **Proposed fix**: Pin encoding='utf-8' on both calls, with a one-time migration for any ledger written under a non-utf-8 locale.

## BUG-5: MemoryError escapes _read_and_parse's OSError guard
- **Observed**: 2026-08-07
- **File**: bin/pm.py:115
- **Description**: data = f.read(max_bytes + 1) is wrapped in except OSError, but CPython pre-allocates the read buffer, so a large QUIRK_PM_MAX_FILE_BYTES (up to the permitted MAX_USABLE_FILE_BYTES of 1 GiB) can raise MemoryError, which is not an OSError. It escapes _read_and_parse and crashes pm.py, contradicting the module docstring's promise that one bad file never takes down the whole read layer. The SessionStart hook masks it as 'index unavailable'; --index/--next/--doctor run directly will traceback.
- **Introduced by**: the Phase 1 pm.py work on this branch
- **Severity**: low
- **Proposed fix**: Widen the guard to except (OSError, MemoryError).

## BUG-6: Every TEST_BACKLOG entry sorts as maximally old in --next
- **Observed**: 2026-08-07
- **File**: bin/pm.py:160
- **Description**: _age_sort_key returns the empty string whenever spec.date_field is None, and TEST_BACKLOG.md has no date field at all. The empty string precedes every ISO date lexically, so TEST entries outrank every same-priority BUG or DEFER entry permanently, regardless of real age. The 'missing date sorts oldest' rule is right for an absent value but wrong for a file that structurally has none. Visible in this repo: TEST-1 [P3] holds a top-5 slot.
- **Introduced by**: the Phase 1 pm.py work on this branch
- **Severity**: low
- **Proposed fix**: Sort date-less specs neutrally rather than oldest, or give TEST_BACKLOG a date field in schema v2.

## BUG-7: The index's doctor hint names a command no surface exposes
- **Observed**: 2026-08-07
- **File**: bin/pm.py:242
- **Description**: The index emits 'run pm.py --doctor for details', but no command, skill, hook, or README entry exposes pm.py, and no path is given - it lives at ${CLAUDE_PLUGIN_ROOT}/bin/pm.py. tech.md:1093 specifies this hint as /quirk:pm:status, which also does not exist. The one actionable line the index produces is not actionable.
- **Introduced by**: the Phase 1 pm.py work on this branch
- **Severity**: low
- **Proposed fix**: Either ship the slash command the hint names or make the hint carry a runnable absolute path.

## BUG-8: README still describes the removed SessionStart tail loading
- **Observed**: 2026-08-07
- **File**: README.md:46
- **Description**: README reads 'SessionStart loads tail of artifact files (or suggests /init if none exist)'. As of this branch the hook calls pm.py and emits an index counts line plus the --next shortlist; it has not loaded file tails since. The parenthetical also names /init rather than the actual /quirk:artifacts:init.
- **Introduced by**: the Phase 1 pm.py work on this branch
- **Severity**: low
- **Proposed fix**: Rewrite the bullet to describe the index-plus-shortlist output and correct the command name.

## BUG-9: pi-watch --check reports a ready alias when the provider auth token is expired
- **Observed**: 2026-08-23
- **File**: skills/adversarial-review/scripts/adversarial-review (select-model preflight)
- **Description**: pi-watch --check codex printed "✓ codex openai-codex/gpt-5.6-sol:medium — 1/1 alias ready" and select-model stamped triple_verified: true, resolved: true. Every actual dispatch to that alias then returned a single newline. A raw `pi -p --provider openai-codex --model gpt-5.6-sol "Say OK"` printed "Provided authentication token is expired." --check validates the alias against the authed model list but never proves a dispatch can produce output, so an expired token reads as a ready reviewer. In adversarial-review this is the dangerous direction: the skill says an empty dispatch is a crash, but a caller who trusts triple_verified and sees repeated empty replies is one step from recording a clean review over a reviewer that never ran. Hit live during the HEAD~1..HEAD review on zpyoung/agent-tool-naming; worked around by walking the ladder to gemini.
- **Severity**: medium
- **Proposed fix**: Make the preflight prove liveness, not just alias resolution — have --check issue a trivial dispatch and require non-empty output before reporting the alias ready, or have select-model degrade triple_verified to false when the check cannot demonstrate one.

## BUG-10: Sign-off tab's visible JSON is the decision record, not the export — copying it fails check-export
- **Observed**: 2026-09-24
- **File**: skills/writing-specs/interactive/app/src/views/sign-off-view.tsx:35
- **Description**: The Sign-off tab renders decisionRecord(...) in a CodeBlock directly above the Download/Copy buttons, while copy() (lines 50-60) writes createExport(). A reviewer who copies the visible JSON pastes only the record, and check-export fails with 9 'required key is missing' errors (kind, schemaVersion, slug, renderId, exportedAt, signed, seen, state, record). Seen 2026-09-24 reviewing the orca spec 2026-09-24-claude-ultracode-effort-level.
- **Severity**: medium
- **Proposed fix**: Show the export in the block, or label it 'Decision record — use Copy or Download to export'; and/or have check-export recognise a bare record and say 'this is the record, not the export — use the Copy button'.

## BUG-11: Stage-2 fold silently discards reviewer notes on requirements
- **Observed**: 2026-09-24
- **File**: skills/writing-specs/interactive/render_spec.py:1
- **Description**: A signed stage-2 export carried state.notes {REQ-09: 'This is verified', REQ-11: 'Verified'}, meaning the reviewer wanted those requirements' certainty raised. fold applied placements/conditions/reviewReason and signoff but dropped notes entirely; nothing in logic.json or logic.md records them, and nothing warned. Worked around with a manual dated amendment. Seen 2026-09-24 on the orca spec 2026-09-24-claude-ultracode-effort-level. Related: the stage-2 record also lists every stage-1 scenario as approved:false / dropped:null (SC-04 included), which misreads as unapproved.
- **Severity**: medium
- **Proposed fix**: Have fold carry notes into the requirement (e.g. reviewNote) or print them on stderr so Claude must act on them; and either let the page set certainty directly or document that notes are advisory. Omit stage-1 items from the stage-2 record, or mark them as pinned.

## BUG-12: pi-watch dispatch prints nothing when the provider request fails
- **Observed**: 2026-10-15
- **File**: skills/pi-dev/scripts/pi-watch/pi-watch.mjs:442
- **Description**: With an expired anthropic OAuth token, pi-watch --alias sonnet --tools read --require-trailer STATUS wrote empty stdout and exited 6 (missing trailer). Without --require-trailer it exits 0 with empty output. Raw pi -p --provider anthropic --model claude-sonnet-4-6 prints 'OAuth refresh failed for anthropic: ... invalid_grant'. session.prompt() does not throw on a provider error, so pi-watch's catch never runs; the failure sits on the final assistant message (stopReason/errorMessage), which pi-watch never inspects. Callers such as adversarial-review read the empty reply as a reviewer result. This is the dispatch side of the expired-token case in BUG-9. Seen while verifying the 1.x SDK port on zpyoung/fix-pi-watch; BUG-9 shows the same empty-reply symptom on the pre-port SDK.
- **Severity**: high
- **Proposed fix**: After session.prompt(), check the last assistant message's stopReason; on error, write errorMessage to stderr and exit non-zero.
- **Resolved**: 2026-10-15. After session.prompt(), pi-watch reads the last assistant message the way pi's print mode does: stopReason error or aborted exits 1 with errorMessage on stderr, and length exits 1 as truncated. The check runs before --require-trailer, so a provider failure no longer surfaces as exit 6. BUG-9 (--check passing an expired token) stays open.

## BUG-13: Review page markdown renders in quadratic time on long runs of unmatched '['
- **Observed**: 2026-10-15
- **File**: skills/writing-specs/interactive/app/src/views/scenario-example.tsx:51
- **Description**: The Astryx 0.6.2 Markdown parser is quadratic on long runs of unmatched '['. It affects every markdown field on the writing-specs review page, examples included, through SpecMarkdown in src/views/shared.tsx too. Timings: 100k '[' 92ms, 200k 334ms, 400k 1301ms, 800k 5172ms. Found by the round-5 security review of scenario-data-states. Triggering it takes a hostile 400k+ character spec field, and spec JSON is Claude-written.
- **Introduced by**: upstream @astryxdesign/core 0.6.2 Markdown parser (pre-dates scenario-data-states)
- **Severity**: low
- **Proposed fix**: Bound example and markdown field length in spec validation, or escape pathological unmatched delimiters before parsing.
- **Resolved**: 2026-10-15. render_spec.py validation now rejects any logic.json string over MAX_TEXT_CHARS (10,000), reported at its JSON pointer. The parser cost is per paragraph, so the cap bounds every render site (SpecMarkdown, the example panes, and the generated logic.md in SpecView) to about 24ms per field in the worst case. The parser itself is unchanged.

## BUG-14: Review page links lose their underscores' meaning: SpecMarkdown inserts zero-width spaces into link URLs
- **Observed**: 2026-10-15
- **File**: skills/writing-specs/interactive/app/src/views/shared.tsx:37
- **Description**: SpecMarkdown's page-wide underscore guard (children.replace(/_/g, '_\u200b')) also rewrites Markdown link destinations, so [r](https://x.test/a_b) renders href="https://x.test/a_\u200bb" and the link opens the wrong URL. Affects every SpecMarkdown field on the review page: explanations, details, custom views. Found by the round-1 correctness review of the details sections, which fixed the same defect in scenario-example.tsx; shared.tsx is fenced in that work.
- **Introduced by**: pre-dates the details-section work (SpecMarkdown underscore guard)
- **Severity**: medium
- **Proposed fix**: Skip link destinations and autolinks when applying the underscore guard, as scenario-example.tsx now does.

## BUG-15: SKILL.md and orchestration.md disagree on which dispatches carry the mutation-probe line
- **Observed**: 2026-10-18
- **File**: skills/full-code-review/SKILL.md:318
- **Description**: SKILL.md Step 4 says to state the mutation-probe line in every dispatch, but orchestration.md's 'Every specialist prompt also says' paragraph says the coordinator adds 'mutation probe: enabled' only to the three test lenses, and only with consent. A coordinator can't tell whether every dispatch needs a mutation-probe line (disabled for the non-test lenses) or only the test lenses do. Doc-only. Found while fixing the gaps the MR !722 re-review exposed.
- **Severity**: low
- **Proposed fix**: Pick one rule: either every dispatch states the probe status (enabled or disabled), or only the test lenses get the line. Then make both files say the same thing.

## BUG-16: full-code-review lets the coordinator skip the lens fan-out on small diffs
- **Observed**: 2026-10-19
- **File**: skills/full-code-review/SKILL.md:292
- **Description**: In a headless smoke-corpus run (claude -p "/quirk:full-code-review --local --no-open", Sonnet 5.5 default, 2026-10-19), all 5 smoke cases reviewed the 2-9 line diff inline instead of dispatching lenses and wrote no report.json (one used the ReportFindings tool, one wrote a Markdown report). One also overrode a pre-exported REVIEW_OUT_DIR with its own mktemp despite the ${REVIEW_OUT_DIR:-...} default in Setup. SKILL.md never says the fan-out runs regardless of diff size, so the smoke corpus can't run without a prompt override and real tiny-diff reviews silently drop to one inline pass.
- **Severity**: medium
- **Proposed fix**: State in SKILL.md (Setup + Step 4) that the lens fan-out and report.json are mandatory at any diff size with no inline shortcut, and that a pre-set REVIEW_OUT_DIR is kept; add a test pinning that wording.
- **Resolved**: 2026-10-19. Wording alone (fan-out at any size, keep REVIEW_OUT_DIR) fixed the out-dir override but still left 3 of 5 plain-prompt runs skipping, now citing "headless run on a one-line diff". Closing those excuses by name (one Agent per lens; skip only on run_when, policy, or failed dispatch; diff size, headless, no forge, or cost is never a skip reason) brought all 5 to a full fan-out, report.json in the caller's dir, and a passing smoke_check. Residual lens-packing is BUG-17.

## BUG-17: full-code-review coordinator occasionally packs several lenses into one agent
- **Observed**: 2026-10-19
- **File**: skills/full-code-review/SKILL.md:298
- **Description**: In the 2026-10-19 plain-prompt smoke run after the BUG-16 fix, 1 of 54 lens dispatches (correctness case) combined comments, db and observability into one agent despite SKILL.md Step 4 saying one Agent per lens. A packed agent shares one context across checklists, so a lens can get a shallower pass than its own dispatch would give, and run.models then reports per-lens models for a single dispatch. Earlier rounds also packed lenses (test-adequacy case, 2 multi-lens agents).
- **Severity**: low
- **Proposed fix**: Re-run the smoke corpus a few times to measure the rate; if it persists, have the coordinator check its dispatch count against policy.json's runnable lenses before Step 5, or record per-lens agent ids in run so a packed dispatch is visible in the report.

