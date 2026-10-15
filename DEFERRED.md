<!-- schema-version: 1 -->
<!-- DEFERRED.md SCHEMA (append only)
Entry format:
## DEFER-[N]: [Task title]
- **Deferred**: [date]
- **Session context**: [what triggered this]
- **Why deferred**: [out of scope / blocked on / requires decision]
- **Estimated effort**: [S/M/L]
- **Priority**: [P1/P2/P3/P4]
- **Proposed owner**: [Claude / name / unassigned]

Required fields: title, why_deferred, priority.
-->

# DEFERRED

Tasks surfaced during sessions but explicitly out of scope for the current work.

Reviewed every sprint planning. Use `/quirk:artifacts:defer` to append.

## DEFER-1: pm-agent Phase 2 - the write layer
- **Deferred**: 2026-08-06
- **Session context**: Phase 1 (read layer) shipped on branch zpyoung/proj-manager; the phasing was ordered by falsifiability so the backlog could be seen before anything claimed to improve it.
- **Why deferred**: Deliberate phase boundary. Phase 2 is schema v2 plus migrate, Status/Probe/Blocked by, ROADMAP.md, the --next intake step, and the lifecycle commands start/finish/park/decide/reconcile. Spec: docs/quirk/specs/2026-08-04-pm-agent/logic.md.
- **Estimated effort**: L
- **Priority**: P2
- **Proposed owner**: unassigned

## DEFER-2: pm-agent Phase 3 - task handoff and dispatch
- **Deferred**: 2026-08-06
- **Session context**: Deferred behind Phase 2; carries all the cross-process and cross-repository risk in the design.
- **Why deferred**: Deliberate phase boundary, and its tech-spec sections are not a build target - see the tech.md DEFER entry. Covers the Handoff field, the handoff packet, the three-call adapter interface with its git-only fallback, and the orca adapter.
- **Estimated effort**: L
- **Priority**: P3
- **Proposed owner**: unassigned

## DEFER-3: Rework tech.md's Phase 2-3 sections before building from them
- **Deferred**: 2026-08-06
- **Session context**: An adversarial review of the tech spec returned 15 findings (3 critical, 10 high, 2 medium) with a verdict of not-buildable-as-written; every critical was in the write and dispatch layers.
- **Why deferred**: The Phase 1 sections were corrected and used; the rest are gated off in the document's own status banner and must not be built from. Confirmed defects include CAS silently dropping the locked attempt key, park recording neither reason nor count, the orca adapter omitting a required --subject and misreading dispatchId, and a v2 append writing into a v1 file. Review: docs/quirk/specs/2026-08-04-pm-agent/review-2026-08-05-codex-tech.md.
- **Estimated effort**: M
- **Priority**: P2
- **Proposed owner**: unassigned

## DEFER-4: Round-5 pm.py fixes shipped without an independent review round
- **Deferred**: 2026-08-06
- **Session context**: The subagent-driven-development final loop reached its five-round cap. Round 5's two fixes were applied at the cap and got no sixth round.
- **Why deferred**: Cap reached, not a scope decision. The fixes are the getattr(os, 'O_NONBLOCK', 0) Windows guard and the platform-codec-first decode order, both in bin/pm.py. They were verified by the orchestrator - scope audit, full suite, plus direct checks of the Windows path, the FIFO, both size bounds and all four decode combinations - but orchestrator verification is weaker than an independent lens and should not be read as equivalent.
- **Estimated effort**: S
- **Priority**: P3
- **Proposed owner**: unassigned

## DEFER-5: pm.py --next ignores the urgency gate until milestones exist
- **Deferred**: 2026-08-06
- **Session context**: logic.md defines eligible(e) := ready(e) AND (e is in a milestone OR urgency(e) <= 1).
- **Why deferred**: With no ROADMAP.md in Phase 1 that formula reduces to 'only critical/high are ever eligible', which was verified to leave a medium/low backlog with zero candidates permanently and no user action available. Phase 1 therefore uses eligible == open. Phase 2 must restore the gate once milestones make it meaningful, or --next will over-report on a large planned backlog.
- **Estimated effort**: S
- **Priority**: P2
- **Proposed owner**: unassigned

## DEFER-6: pm.py ships only top-level flags, not the subcommands tech.md specifies
- **Deferred**: 2026-08-07
- **Session context**: Surfaced by a code review of the Phase 1 branch; no caller depends on the subcommand form today.
- **Why deferred**: tech.md:617-625 specifies pm.py index / doctor / status / roadmap / migrate as subcommands, with --index and --doctor as equivalent top-level flags checked before subparser dispatch. Phase 1 implemented only the flags, so pm.py index exits 2. Deferred rather than fixed because the subcommand surface is mostly Phase 2 verbs (roadmap, migrate, status) and adding a parser for them now would front-run DEFER-3's rework of those spec sections.
- **Estimated effort**: S
- **Priority**: P3

## DEFER-7: Spec-validation layer for quirk:writing-specs (reverse-reasoning + quality gate)
- **Deferred**: 2026-09-14
- **Session context**: Scoped out of the brainstorming elicitation work (docs/quirk/specs/2026-09-14-brainstorming-elicitation/logic.md). Two of the six PAWNI-derived directions landed in writing-specs, not brainstorming, once PR #39 moved spec-writing out of the brainstorming skill.
- **Why deferred**: Different skill, different test file, doubles the review surface. Two mechanisms: (a) reverse-reasoning validation - a fresh-context agent builds a pseudo-plan from logic.md alone and a judge diffs it against conversation intent, catching ambiguity invisible to the spec's author; (b) a numeric spec-quality gate with a cross-family judge. Research caveat: self-preference bias in LLM judges is 4-8 points and model-agnostic (arxiv 2604.22891), so (b) needs genuine cross-family judging, not same-model scoring.
- **Estimated effort**: M
- **Priority**: P2
- **Proposed owner**: unassigned

## DEFER-8: Persistent cross-session pattern memory for brainstorming
- **Deferred**: 2026-09-14
- **Session context**: Direction 3 of six from the PAWNI exploration; scoped out of the elicitation spec as the only direction needing real code rather than prose.
- **Why deferred**: Needs a storage format and likely a bin/ script, unlike the prose-only elicitation work. Would seed gray-area questions from recurrence counts across sessions so the skill stops re-deriving everything each time. Open risk recorded in the exploration: at one user's session volume the weights may never beat the static catalog, while stale patterns actively mislead.
- **Estimated effort**: L
- **Priority**: P3
- **Proposed owner**: unassigned

## DEFER-9: Outcome telemetry for spec quality
- **Deferred**: 2026-09-14
- **Session context**: Raised repeatedly during the brainstorming elicitation design as the thing that would make every other mechanism falsifiable.
- **Why deferred**: A distinct mechanism from the elicitation work, and genuinely hard. No telemetry exists on skill behavior today, so nothing measures whether the coverage gate, altitude rule, or fast-track reduce execution-phase rework. Until it exists, every improvement to these skills is argued rather than demonstrated, and the prose pins prove only presence, not compliance.
- **Estimated effort**: M
- **Priority**: P3
- **Proposed owner**: unassigned

## DEFER-10: Downstream consumption of `[tech-spec]`-tagged Deferred Ideas
- **Deferred**: 2026-09-14
- **Session context**: PR #40 review. Brainstorming routes build-only questions into Deferred Ideas tagged `[tech-spec]` and says the tech spec inherits them, but `skills/writing-specs/tech-spec.md` never instructs its author to scan Deferred Ideas, so a tagged question can still be lost at handoff.
- **Why deferred**: Requires decision. The only real fix edits `skills/writing-specs/`, which the elicitation logic spec locks as untouched (the CONTRACT in its Scope & non-goals; tech.md fence 5). Either amend that contract and add a one-line consumption rule to the tech-spec rubric, or accept the tag as best-effort and soften the claim in `skills/brainstorming/SKILL.md`.
- **Estimated effort**: S
- **Priority**: P3
- **Proposed owner**: unassigned

## DEFER-11: Post-execution per-requirement disposition for interactive logic specs
- **Deferred**: 2026-09-24
- **Session context**: Review of archify, pr-lens, goal-workflow concepts against interactive-logic-spec v2
- **Why deferred**: Signed REQ-ids and derivedFrom chains end at the final fold; nothing after execution records how each in/conditional requirement was satisfied (test, commit) or deviated. Needs its own design (where it lives in logic.json, which skill writes it). Inspired by smallnest/goal-workflow skills/ship-it/SKILL.md closing comment.
- **Estimated effort**: M
- **Priority**: P2

## DEFER-12: Falsifiability self-review rule for derived requirements
- **Deferred**: 2026-09-24
- **Session context**: Review of archify, pr-lens, goal-workflow concepts against interactive-logic-spec v2
- **Why deferred**: Derived requirements are not checked for vagueness before stage-2 review; add a rubric rule to interactive-logic-spec.md Derivation that each requirement names the observation that would show it false and is checkable from its derivedFrom scenario's Then. Out of scope for the current branch. Source: smallnest/goal-workflow skills/prd/SKILL.md:102-106, skills/to-issues/SKILL.md:81.
- **Estimated effort**: S
- **Priority**: P3

## DEFER-13: Agent-authored guided walkthrough in the interactive review page
- **Deferred**: 2026-09-24
- **Session context**: Review of archify, pr-lens, goal-workflow concepts against interactive-logic-spec v2
- **Why deferred**: Page has ~9 views and no reading order; an optional walkthrough[] (ordered steps naming a view plus focused item ids, pruned when ids vanish) touches schema, validator, and page, so it needs its own spec round. Source: coldteadotai/pr-lens packages/schema/src/walkthrough.ts.
- **Estimated effort**: L
- **Priority**: P3

## DEFER-14: Deduplicate v1 and v2 logic-spec validators in render_spec.py
- **Deferred**: 2026-09-25
- **Session context**: code-review high --fix on zpyoung/interactive-logic-spec
- **Why deferred**: validate_logic_v2 (render_spec.py ~644) copies ~150 lines of validate_logic (amendments, sections, conflicts, state-machine and story-map views), so shared-section schema fixes must be made twice or v1/v2 drift. Found by /code-review high; too large and risky to refactor as a review fix.
- **Estimated effort**: M
- **Priority**: P3

## DEFER-15: Compute custom-view quote drift once, in render, instead of in both Python and the page
- **Deferred**: 2026-09-26
- **Session context**: code review of typed custom views (db10b48) on zpyoung/interactive-logic-spec-extra-views
- **Why deferred**: Quote drift is matched twice: TS quotableText/quotePattern (skills/writing-specs/interactive/app/src/views/custom-view.tsx) and Python _quotable_text/quote_pattern (skills/writing-specs/interactive/render_spec.py), kept in sync only by a docstring. Regex semantics already differ (JS `.` excludes \r,  ,  ; Python does not) and no test checks agreement. Fix: render computes drift into the page payload and the page only displays it. Left out of the /code-review high --fix pass on db10b48 because it changes the payload format and the page data flow.
- **Estimated effort**: M
- **Priority**: P3


## DEFER-16: Port pi-watch to the pi-coding-agent 1.x ModelRuntime API
- **Deferred**: 2026-10-12
- **Session context**: pi-watch failed preflight for subagent-driven-development with "does not provide an export named 'AuthStorage'". skills/pi-dev/scripts/pi-watch/package.json depends on "*", so installs resolve pi-coding-agent 1.x, which stopped exporting AuthStorage in 0.80.8 (replaced by ModelRuntime). The local plugin cache was pinned to 0.80.7 with a fresh lockfile as a workaround.
- **Why deferred**: Out of scope for the stage-3 branch. Needs a port of pi-watch.mjs (AuthStorage.create, ModelRegistry, createAgentSession options) to ModelRuntime, plus an exact pin or tested range in package.json.
- **Estimated effort**: M
- **Priority**: P2
- **Proposed owner**: unassigned
- **Resolved**: 2026-10-15. pi-watch.mjs now builds a ModelRuntime and passes it to createAgentSession. package.json pins ^1.2.0, not ^1.0.0, because pi-coding-agent 1.0.0 and 1.1.0 fail on a fresh install: their caret range on pi-codemode resolves to 1.2.0, which dropped an export they import. The launcher reinstalls deps older than that floor, and a committed pnpm-workspace.yaml declines the two dependency build scripts so pnpm 12's install doesn't exit 1.

## DEFER-17: Refresh pi-watch alias ladders for the pi 1.x model catalog
- **Deferred**: 2026-10-15
- **Session context**: pi-watch 1.x SDK port on zpyoung/fix-pi-watch
- **Why deferred**: pi 1.1.0 --list-models lists anthropic/claude-sonnet-5-5, anthropic/claude-haiku-5-5 and openai/gpt-6.1-sol, which no ladder in skills/pi-dev/scripts/pi-watch/pi-watch.mjs ALIASES includes, so sonnet/haiku/codex resolve to older models. The launcher's --where staleness probe greps for gpt-5.6 and needs the same update. Left out of the 1.x SDK port because a ladder refresh is a separate model-choice decision.
- **Estimated effort**: S
- **Priority**: P2
- **Resolved**: 2026-10-15. The ladders now lead with GPT-6.1/6 Sol, GPT-6 Luna, and Claude 5.5. A new opt-in `fable` alias covers Claude Fable, and grok routes to grok-4.7/4.6 via xai, then Copilot. GPT-6 Astra is excluded as pro-priced, and terra stays on GPT-5.6 Terra because GPT-6 has no Terra tier. Entries the pinned pi-ai 1.2.0 catalog doesn't ship were removed. The --where probe now looks for gpt-6.1-sol, and adversarial-review's ALIAS_LADDER heads match.

## DEFER-18: Replace the per-provider model dumps in pi-dev's models.md
- **Deferred**: 2026-10-15
- **Session context**: DEFER-17 alias ladder refresh on zpyoung/fix-pi-watch
- **Why deferred**: skills/pi-dev/reference/models.md has a hand-copied pi --list-models table for each provider (openai-codex, openai, anthropic, google, github-copilot). It's a pre-1.x snapshot that lacks GPT-6, Claude 5.x and Grok 4.x and still lists grok-code-fast-1. Either regenerate it from the pi-ai catalog or replace it with a pointer to pi --list-models <pattern>. Left out of the DEFER-17 ladder refresh because it's a doc restructure, not a ladder change.
- **Estimated effort**: S
- **Priority**: P3

