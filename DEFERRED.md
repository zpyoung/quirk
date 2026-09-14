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
