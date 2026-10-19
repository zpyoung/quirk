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

## BUG-15: pi-watch crashes at import: unpinned pi-coding-agent no longer exports AuthStorage
- **Observed**: 2026-10-13
- **File**: skills/pi-dev/scripts/pi-watch/pi-watch.mjs:23
- **Description**: skills/pi-dev/scripts/pi-watch/package.json declares @earendil-works/pi-coding-agent and pi-ai as "*". The installed version (pi 0.87.1) no longer exports AuthStorage, so pi-watch --check codex|gemini|opus exits 1 with: SyntaxError: The requested module '@earendil-works/pi-coding-agent' does not provide an export named 'AuthStorage'. Every pi-backed path (SDD pi implementers, adversarial-review reviewers) is dead; the SDD run on zpyoung/writing-artifacts fell back to Claude Agent reviewers with reduced independence.
- **Severity**: high
- **Proposed fix**: Pin both deps to a known-good version with a frozen lockfile install, and adapt to the new export if AuthStorage moved.

## BUG-16: Kit elements render unstyled in tier-2 apps
- **Observed**: 2026-10-14
- **File**: skills/writing-html-artifacts/vendor/kit/1.0.0/kit.css:715
- **Description**: kit.css relies on Simple.css for pre, button, select and summary styling. In a tier-2 build (Astryx reset.css, no Simple.css), q-code's <pre> body has no background, border or padding and sits outside the header bar's box; q-board's Reset / Copy as Markdown buttons and Move to… selects look like plain text; q-chart's Table view summary has no affordance. Tier-1 report pages look correct. Repro: build-app kit-showcase-app, then The change > Rollback tab, and the Follow-ups tab.
- **Severity**: medium
- **Proposed fix**: Style the kit's own inserted controls and the q-code pre in kit.css instead of inheriting from the host stylesheet; add a tier-2 verify screenshot of a non-first route so this is caught.

## BUG-17: q-flow browser tests time out when Chrome is launched from a Python parent
- **Observed**: 2026-10-17
- **File**: tests/fixtures/html-kit/harness.mjs:156
- **Description**: The harness waitForFunction (rAF polling) for data-q-flow-ready times out at 10s and also at 30s, though the page is ready ~120ms after load when the same harness.mjs runs directly from zsh or perl (<1s total). Any Python parent (rye 3.11, homebrew, /usr/bin) reproduces it, including os.system; close_fds, start_new_session, stdin DEVNULL and the shell's __CF_USER_TEXT_ENCODING made no difference. Interval polling and Chrome's --disable-renderer-backgrounding/--disable-background-timer-throttling/--disable-backgrounding-occluded-windows flags also made no difference: the page itself takes 10-25s to become ready. Verified: relaying the harness call through a node server started from zsh (so Chrome has no Python ancestor) makes the same pytest tests pass in about 3s, so the cause is the Python ancestry, not CPU load. Affects the q-flow tests in tests/test_html_kit_elements.py (runner _run_harness at :91), e.g. test_flow_renders_at_rest_with_controls_closed_list_and_sync_async_edges and test_flow_pulse_travels_at_one_speed_and_streams_before_the_last_one_lands, on zpyoung/q-flow-shapes at efa903b, unmodified. Blocks local browser verification; CI unknown.
- **Severity**: medium

## BUG-18: Verify's connected-navigation timeout test reports network passed under the local relay
- **Observed**: 2026-10-17
- **File**: tests/test_html_verify.py:300
- **Description**: test_connected_navigation_timeout_is_a_network_failure_with_a_report fails locally: verify reports network passed=True where the test expects a navigation-timeout network failure. Reproduces at a36dcfc (before the q-flow traces work) when run through the BUG-17 node relay shim, so the traces branch did not cause it. The relay or the local network may change how the connected-navigation timeout surfaces. Found 2026-10-17 during the q-flow traces wave-1 gate.
- **Severity**: low

## BUG-19: A q-flow label, kind or detail with an escaped lone surrogate breaks the page build
- **Observed**: 2026-10-17
- **File**: skills/writing-html-artifacts/scripts/htmlkit/kitcheck.py:1284
- **Description**: The no-JS fallback that inject_flow_fallbacks writes for a <q-flow> copies node labels (and other graph strings) from the JSON. A JSON escape such as "\ud800" decodes to a lone surrogate that passes the kit check, and the assembled page then raises UnicodeEncodeError when written as UTF-8. Reproduced with a node label "A \ud800". Trace values get the same treatment in the q-flow traces branch, where they fail the check as not JSON; labels, kinds, group labels, edge labels and details predate that and still crash. Found 2026-10-17 in the q-flow traces final review.
- **Severity**: low
- **Status**: fixed on branch zpyoung/q-flow-traces (graph-level UTF-8 check)

## BUG-20: q-flow keeps pulsing when reduced motion is switched on mid-pulse
- **Observed**: 2026-10-17
- **File**: skills/writing-html-artifacts/vendor/kit/1.0.0/kit.js:5840
- **Description**: Reduced motion is read only when a trace step is shown (and when a node is focused). If the reader turns on prefers-reduced-motion while a trace edge or a focused path is pulsing, the pulse keeps running until the next step, a new focus, or trace mode closes; there is no change listener on the media query. Focus mode had the same gap before traces. Found 2026-10-17 by the q-flow traces final review (HX1), logged instead of a fourth review round.
- **Severity**: low
- **Proposed fix**: Listen for changes to the reduced-motion query while pulsing; stop the pulse and apply the static 3.5px lit style.

## BUG-21: q-flow's no-JS fallback crashes the build on very deep group nesting
- **Observed**: 2026-10-17 (q-schema SDD checkpoint review)
- **File**: skills/writing-html-artifacts/scripts/htmlkit/kitcheck.py:2086
- **Description**: `_render_flow_fallback_html` renders groups with a recursive `render_group`, so a q-flow graph whose groups nest about 1,000 deep raises an uncaught RecursionError during fallback injection and aborts the build instead of reporting a check failure. q-schema had the same pattern and now uses an explicit stack (commit 6f59893).
- **Introduced by**: unknown (q-flow fallback, before d6895d2)
- **Severity**: low
- **Proposed fix**: render the group tree with an explicit stack, as `_render_schema_fallback_html` does.
- **Blocker for**: nothing in practice; only pathological input

## BUG-22: Text "data-q-flow-list" inside q-flow data suppresses the no-JS fallback
- **Observed**: 2026-10-17 (q-schema SDD checkpoint review)
- **File**: skills/writing-html-artifacts/scripts/htmlkit/kitcheck.py:2120
- **Description**: `inject_flow_fallbacks` skips any block whose raw text contains "data-q-flow-list", including that text inside a node label or detail in the JSON, so such a graph ships with no no-JS list. q-schema had the same guard and now checks for a real element attribute outside the JSON script (commit 6f59893).
- **Introduced by**: unknown (q-flow fallback, before d6895d2)
- **Severity**: low
- **Proposed fix**: skip only when a tag outside the JSON script carries a data-q-flow-list attribute, as `inject_schema_fallbacks` does.
- **Blocker for**: no-JS readers of a graph whose data mentions the attribute name

## BUG-23: q-flow keys its id maps on plain objects, so ids like "constructor" misbehave
- **Observed**: 2026-10-17 (q-schema SDD checkpoint review)
- **File**: skills/writing-html-artifacts/vendor/kit/1.0.0/kit.js:3849
- **Description**: QFlow's parse, layout and focus code index author-supplied node and group ids into plain `{}` objects (`seenIds`, `groupMap`, `nodeMap`, `outByNode`, `nodeSizes`, ...). An id such as `constructor`, `toString` or `__proto__` resolves to an inherited property. The same pattern in q-schema crashed layout before readiness was set; q-flow was not reproduced here and is fenced from this branch. q-schema now uses prototype-free maps (commit 76cd7b9).
- **Introduced by**: unknown (q-flow runtime, before d6895d2)
- **Severity**: medium
- **Proposed fix**: use `Object.create(null)` or `Map` for every QFlow dictionary keyed by an author id, and add a browser test with those ids.
- **Blocker for**: graphs whose node or group ids collide with Object.prototype names

## BUG-24: Text "</q-flow>" inside q-flow data stops the no-JS fallback injection early
- **Observed**: 2026-10-17 (q-schema SDD final review)
- **File**: skills/writing-html-artifacts/scripts/htmlkit/kitcheck.py:2109
- **Description**: `inject_flow_fallbacks` finds each element with the non-greedy regex `_FLOW_BLOCK`, which stops at the text `</q-flow>` when it appears inside the JSON script (valid JSON; browsers end a script only at `</script`). A graph whose data contains that text builds with no no-JS list. q-schema had the same pattern and now scans for the real closing tag while skipping script content.
- **Introduced by**: unknown (q-flow fallback, before d6895d2)
- **Severity**: low
- **Proposed fix**: locate the closing tag with the script-aware scan `inject_schema_fallbacks` uses.
- **Blocker for**: no-JS readers of a graph whose data mentions the closing tag

## BUG-25: On a phone the graph toolbar covers the top of a fitted q-flow or q-schema
- **Observed**: 2026-10-17 (q-schema visual check at 375px)
- **File**: skills/writing-html-artifacts/vendor/kit/1.0.0/kit.js:3599
- **Description**: `canvasFitBounds` fits the drawing to the whole stage with a 28px pad, but the zoom/fit/expand toolbar overlays the stage's top-left corner. At 375px a tall drawing is scaled so its top row sits under the toolbar (the parser class diagram's Parser card was hidden behind it). The shared fit predates q-schema, so q-flow behaves the same.
- **Introduced by**: unknown (q-flow canvas, before d6895d2)
- **Severity**: low
- **Proposed fix**: reserve the toolbar's height at the top when fitting, at least on narrow stages.
- **Blocker for**: reading the top node of a tall graph on a phone without panning

## BUG-26: q-flow's detail sanitizer crashes the build on deeply nested detail HTML
- **Observed**: 2026-10-17
- **File**: skills/writing-html-artifacts/scripts/htmlkit/kitcheck.py:906
- **Description**: _check_and_sanitize_flow_detail recurses per nested element, so a q-flow node detail with about 1,100 nested lists raises an uncaught RecursionError and aborts the build. q-schema now catches it and reports a validation failure (commit 797d789); q-flow does not. Observed 2026-10-17 in the q-schema SDD final review.
- **Introduced by**: unknown (q-flow kit check, before d6895d2)
- **Severity**: low
- **Proposed fix**: Sanitize iteratively, or cap nesting depth with a validation failure.
- **Blocker for**: builds of q-flow pages whose node detail is pathologically nested

## BUG-27: QSchema change detection joins its parts with NUL, so some changes could skip a re-render
- **Observed**: 2026-10-17
- **File**: skills/writing-html-artifacts/vendor/kit/1.0.0/kit.js:6577
- **Description**: QSchema._signature joins the JSON text, summary and notation with a NUL separator to decide whether to re-render, so two different attribute and data combinations containing NUL could compare equal and leave a stale drawing. Observed 2026-10-17 in the q-schema SDD final review.
- **Introduced by**: this session (q-schema runtime)
- **Severity**: low
- **Proposed fix**: Compare the parts separately, or encode them unambiguously.
- **Blocker for**: live edits of a q-schema whose summary or data contains NUL

## BUG-28: q-flow and q-schema pass the kit check with JSON their browser elements reject
- **Observed**: 2026-10-17
- **File**: skills/writing-html-artifacts/scripts/htmlkit/kitcheck.py:1197
- **Description**: The Python kit check accepts two payloads the browser elements reject. One is NaN or Infinity anywhere in the data, which json.loads accepts and JSON.parse does not. The other is a JSON script child whose type has surrounding whitespace or other case: Python strips and lowercases it, while QFlow and QSchema select script[type="application/json"] exactly (kit.js:3790, :3821 and the QSchema equivalents). The build passes and injects a no-JS list, while the element shows the fail-hard notice. Reproduced for q-flow with "extra": NaN and with type=" Application/JSON ". q-sequence fixed both on its own path: strict_constants in _json_child, and QSequence._jsonScript. Found 2026-10-17 in the q-sequence final review.
- **Severity**: low
- **Proposed fix**: Pass strict_constants=True from the q-flow and q-schema callers of _json_child, and select the JSON child by trimmed, lowercased type in QFlow and QSchema, as q-sequence does.

## BUG-29: q-sequence phone pinned-header test can race the page's smooth scroll
- **Observed**: 2026-10-17
- **File**: tests/test_html_kit_elements.py:9413
- **Description**: test_seq_phone_scrolls_sideways_at_full_size_with_headers_pinned_and_in_step failed once during the q-sequence build and passed on every run after it, including four full-file runs. The report template sets scroll-behavior: smooth on html, so a page scroll the test starts can still be animating when the test reads the pinned strip's position. Found 2026-10-17 by the q-sequence trace-mode implementer.
- **Severity**: low
- **Proposed fix**: Scroll with behavior 'instant' in the test (or set scroll-behavior: auto on the test page), and wait for the stuck attribute before measuring.

## BUG-30: A q-sequence payload with NaN and markup text in a string reports the detail rule
- **Observed**: 2026-10-17
- **File**: skills/writing-html-artifacts/scripts/htmlkit/kitcheck.py:1223
- **Description**: _json_child's parse-failure branch searches the whole raw payload for forbidden markup before choosing its message. A q-sequence payload that holds NaN (rejected by strict_constants) and also a string such as "<img" elsewhere therefore fails with '<q-sequence> detail may hold only paragraphs, lists, code and links' instead of the JSON-child message. The page still fails the check, so only the diagnostic is wrong. Found 2026-10-17 by the q-sequence closure review (CL1).
- **Severity**: low
- **Proposed fix**: Raise a distinct error from the constant hook and report the JSON-child message for it before the forbidden-markup search.

## BUG-31: The diagram list disclosure renders as plain text in tier-2 app builds
- **Observed**: 2026-10-18
- **File**: skills/writing-html-artifacts/vendor/kit/1.0.0/kit.css:1282
- **Description**: In tier-2 app builds the "Graph as a list" and "Diagram as a list" disclosures under q-flow and q-sequence render as plain unstyled text, with no bordered box or chevron. Tier-1 report and components pages show a bordered disclosure with a chevron. The kit's own rules (kit.css:1282 for q-flow and q-schema, :1668 for q-sequence) only set height, layout and cursor; the box and chevron on tier-1 pages come from the base stylesheet (Simple.css or Web Awesome), which the app's Astryx theme doesn't supply. Seen 2026-10-18 building templates/app/examples/explainer and reference at 4fe1e65 and screenshotting at 1280px light.
- **Severity**: low
- **Proposed fix**: Give the kit's diagram disclosures their own border, padding and marker so they look the same without a base stylesheet, or add matching details styles to the app theme.

## BUG-32: SKILL.md and orchestration.md disagree on which dispatches carry the mutation-probe line
- **Observed**: 2026-10-18
- **File**: skills/full-code-review/SKILL.md:318
- **Description**: SKILL.md Step 4 says to state the mutation-probe line in every dispatch, but orchestration.md's 'Every specialist prompt also says' paragraph says the coordinator adds 'mutation probe: enabled' only to the three test lenses, and only with consent. A coordinator can't tell whether every dispatch needs a mutation-probe line (disabled for the non-test lenses) or only the test lenses do. Doc-only. Found while fixing the gaps the MR !722 re-review exposed.
- **Severity**: low
- **Proposed fix**: Pick one rule: either every dispatch states the probe status (enabled or disabled), or only the test lenses get the line. Then make both files say the same thing.

## BUG-33: full-code-review lets the coordinator skip the lens fan-out on small diffs
- **Observed**: 2026-10-19
- **File**: skills/full-code-review/SKILL.md:292
- **Description**: In a headless smoke-corpus run (claude -p "/quirk:full-code-review --local --no-open", Sonnet 5.5 default, 2026-10-19), all 5 smoke cases reviewed the 2-9 line diff inline instead of dispatching lenses and wrote no report.json (one used the ReportFindings tool, one wrote a Markdown report). One also overrode a pre-exported REVIEW_OUT_DIR with its own mktemp despite the ${REVIEW_OUT_DIR:-...} default in Setup. SKILL.md never says the fan-out runs regardless of diff size, so the smoke corpus can't run without a prompt override and real tiny-diff reviews silently drop to one inline pass.
- **Severity**: medium
- **Proposed fix**: State in SKILL.md (Setup + Step 4) that the lens fan-out and report.json are mandatory at any diff size with no inline shortcut, and that a pre-set REVIEW_OUT_DIR is kept; add a test pinning that wording.
- **Resolved**: 2026-10-19. Wording alone (fan-out at any size, keep REVIEW_OUT_DIR) fixed the out-dir override but still left 3 of 5 plain-prompt runs skipping, now citing "headless run on a one-line diff". Closing those excuses by name (one Agent per lens; skip only on run_when, policy, or failed dispatch; diff size, headless, no forge, or cost is never a skip reason) brought all 5 to a full fan-out, report.json in the caller's dir, and a passing smoke_check. Residual lens-packing is BUG-34.

## BUG-34: full-code-review coordinator occasionally packs several lenses into one agent
- **Observed**: 2026-10-19
- **File**: skills/full-code-review/SKILL.md:298
- **Description**: In the 2026-10-19 plain-prompt smoke run after the BUG-33 fix, 1 of 54 lens dispatches (correctness case) combined comments, db and observability into one agent despite SKILL.md Step 4 saying one Agent per lens. A packed agent shares one context across checklists, so a lens can get a shallower pass than its own dispatch would give, and run.models then reports per-lens models for a single dispatch. Earlier rounds also packed lenses (test-adequacy case, 2 multi-lens agents).
- **Severity**: low
- **Proposed fix**: Re-run the smoke corpus a few times to measure the rate; if it persists, have the coordinator check its dispatch count against policy.json's runnable lenses before Step 5, or record per-lens agent ids in run so a packed dispatch is visible in the report.

## BUG-35: --launch-env check ignores the default LIKEUSER credentials
- **Observed**: 2026-10-13
- **File**: skills/using-apps-like-a-user/scripts/likeuser.py:981
- **Description**: cmd_begin loads secret_values only when --credentials-env or --credentials-file is given. A begin with neither still redacts the default LIKEUSER_* values, but _refuse_credential_launch_env and _launch_env never see them, so begin --launch-env PUBLIC_COPY passes a variable whose value equals the default password through to the launched Electron app. Reproduced by the targeted review of f41f461..c337402.
- **Introduced by**: 52dc460
- **Severity**: high
- **Proposed fix**: Load the default credential source before the --launch-env check and add both values to secret_values and run.secrets when no explicit source is given.
- **Blocker for**: Electron runs that pass --launch-env while LIKEUSER_* is exported

## BUG-36: Electron observe swallows a failed native screenshot observation while a sheet is open
- **Observed**: 2026-10-13
- **File**: skills/using-apps-like-a-user/scripts/likeuser.py:478
- **Description**: _observe_surface now raises when the first native observation of an Electron run fails, but the second native observation that captures the sheet screenshot still catches DriverError and returns a successful snapshot with native_error set and no screenshot. The 'a native failure never reads as no sheet' fix is incomplete on this path.
- **Introduced by**: 52dc460 (partial fix)
- **Severity**: high
- **Proposed fix**: Let DriverError from the screenshot-bearing native observation propagate so observe exits 4.
- **Blocker for**: Electron runs with native sheets open

## BUG-37: A failed delete of a password-bearing screenshot is reported as withheld
- **Observed**: 2026-10-13
- **File**: skills/using-apps-like-a-user/scripts/likeuser.py:451
- **Description**: _observe deletes a screenshot that shows the password under contextlib.suppress(OSError) and then marks the snapshot screenshot_withheld unconditionally, so a failed unlink leaves the file in the run folder while the output says it was withheld.
- **Introduced by**: pre-dates 52dc460 (text-match withholding)
- **Severity**: medium
- **Proposed fix**: Raise when unlink fails and mark screenshot_withheld only after confirming the path is gone.
- **Blocker for**: credential handling guarantee in references/safety.md
