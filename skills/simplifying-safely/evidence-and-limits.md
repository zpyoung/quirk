# Evidence and limits

This file records what each of the 32 rules in [SKILL.md](SKILL.md) rests on: its status, the
caveat that keeps it from being stronger, and — for the 15 rules that carry one — the full
falsification note (`SKILL.md` carries a one-line pointer). It also reports the one validation
run performed on the skill's core gate before this file was written. Nothing here changes what
an agent does; an agent that never opens this file must still act correctly on `SKILL.md` alone.

The source is `docs/quirk/specs/2026-09-11-simplifying-safely/audited-ruleset.json` — 32 rules
that survived a research pass (471 findings, 28 facets, 99 quantitative claims adversarially
verified) and a subsequent audit pass that re-tagged, corrected, or reinstated several of them.
Citations below trace to that audit's `evidence` fields and to logic.md's own Industry Insights
section; where the audit's own `audit_note` narrowed a claim, that narrowing is what's reported
here, not the original drafted evidence.

## Audit → shipped ID mapping

The audit record and `SKILL.md` use different IDs. The audit reused `S1`/`S2` for two unrelated
rules (one in the code tier, one in specs) and reused `D1`/`D2`/`D4` across the core-detection
tier and the agent-docs tier — harmless in a JSON asset keyed by section, unworkable in one flat
document. `SKILL.md`'s IDs are the renumber that removes the collision. This table is the only
place the provenance chain from a shipped ID back to its audit entry is recorded.

**Always-on core (7)**

| Audit ID | Shipped | Status |
|---|---|---|
| G1 | G1 | precautionary |
| G2 | G2 | judgment |
| G3 | G3 | precautionary |
| G4 | G4 | grounded |
| D1-coevolution | D1 | precautionary |
| D2-pruning-executed | D2 | judgment |
| D3-retrospective-only | D3 | grounded |

**Code (6)**

| Audit ID | Shipped | Status |
|---|---|---|
| S1(code) | C1 | precautionary |
| S5(code) | C2 | precautionary |
| S2(code) | C3 | precautionary |
| S6(code) | C4 | precautionary |
| S7(code) | C5 | precautionary |
| D4-blocklist-metrics | C6 | grounded |

**Agent-facing docs (4)**

| Audit ID | Shipped | Status |
|---|---|---|
| D1(agentdocs) | A1 | precautionary |
| D2(agentdocs) | A2 | precautionary |
| D4(agentdocs) | A3 | judgment |
| D5(agentdocs) | A4 | precautionary |

**Specs (3)**

| Audit ID | Shipped | Status |
|---|---|---|
| S1(specs) | S1 | precautionary |
| S2(specs) | S2 | judgment |
| S3(specs) | S3 | precautionary |

**Human-facing docs (4)**

| Audit ID | Shipped | Status |
|---|---|---|
| HD1 | H1 | judgment |
| HD2 | H2 | judgment |
| HD3 | H3 | judgment |
| HD4 | H4 | judgment |

**Conversational output (2)**

| Audit ID | Shipped | Status |
|---|---|---|
| P1B-1(chat) | V1 | judgment |
| P1B-2(chat) | V2 | judgment |

**Meta (6)**

| Audit ID | Shipped | Status |
|---|---|---|
| M1 | M1 | grounded |
| M2 | M2 | judgment |
| M3 | M3 | judgment |
| M4 | M4 | precautionary |
| M5 | M5 | judgment |
| M6 | M6 | judgment |

32 rules, status tally 4 `grounded` / 14 `precautionary` / 14 `judgment`. Seven rules carry no
reviewer test and are marked diagnosis-only in `SKILL.md`: **D3, C1, A4, S2, S3, M4, V1**.

## Per-rule evidence status

`grounded` means the audit found no application-changing caveat. `precautionary` means the check
rests on convergence across related findings, or on a narrow-domain result extended by inference,
rather than a single settled result in the check's own scope. `judgment` means the rule encodes a
design choice or an invented mechanism the corpus does not itself adjudicate — real reasoning, not
evidentiary convergence. Several rows below record a status the audit *changed* from the original
draft; that correction is what's reported, not the superseded tag.

| Shipped | Status | Rests on |
|---|---|---|
| G1 | precautionary | RECAP's Oracle-Guided Refinement mode — subordinating conciseness to a test-pass gate — beat baseline on SWE-bench-Verified while ungated minimal-patch prompting and trained minimizers cost resolved instances across all four tested host agents. Called the corpus's best-evidenced finding, but it is one winning configuration among four, on bug-fix patch-refinement only; the source exploration's own challenge note flags refactoring and long-horizon transfer as unconfirmed. Downgraded `grounded`→`precautionary` for exactly that reason — the rule's text covers "any" shrinking change, wider than the finding under it. |
| G2 | judgment | The symmetric gate (additions and deletions face the identical re-check, neither carries a special burden) is the locked design's chosen framing of the same RECAP/linter-reward evidence G1 and G3 cite. The exploration doc's own irreducible-tension note says both that framing and the rejected asymmetric one ("deletion needs justification") read the *same* evidence — the corpus doesn't adjudicate which default posture is right. Downgraded `precautionary`→`judgment`: a design decision, not a convergent empirical result. |
| G3 | precautionary | A Ruff-linter-reward RL loop degraded pass@1 when it dominated a training signal, but beat test-only when subordinated to a unit-test gate; RECAP's ungated minimal-patch modes cost resolved instances. A Reddit report corroborates: appending "minimum viable functionality" to a prompt made a model strip working features. All three are patch-refinement/small-model-training-scoped. Downgraded `grounded`→`precautionary` — same narrow-domain caveat as G1. |
| G4 | grounded | "The correctness gate has no evidenced analogue for documents, specs, or human-facing docs" is the exploration document's own stated absence, not an inference from a transferred result. One of the four rules that is a statement about what the skill cannot do, not what it can. |
| D1 | precautionary | Kapser & Godfrey's §4.2 co-evolution question is the literal deciding criterion for harmful clones, not a paraphrase — but their own "good clone" fraction is unstable across four case-study samples (71% / 42% / 33% / 57%), and the citation carries no adversarial-verification mark. The reviewer test checks that a co-evolution claim was *stated*, not that it's true. |
| D2 | judgment | "Cut a rule if the task still goes fine without it" is itself grounded — Claude Code's own docs state it as a real, cited pruning practice. What's invented, and what earns the `judgment` tag, is converting that from a *predicted* judgment ("would removing this cause a mistake?") into an *executed* one (remove it, run the task, observe). The method is judgment; the underlying keep/cut criterion is not. |
| D3 | grounded, diagnosis-only | "Over-engineering has no review-time definition — every review-time test in this document is a proxy for a fact that has not happened yet" is the exploration document's own headline synthesis, drawn from an independently cross-thread-confirmed practitioner consensus. No reviewer test is claimed; this rule names a limit, not a checkable property. |
| C1 | precautionary, diagnosis-only | A 500k-function study finds AI-generated functions shorter and structurally simpler than human ones; project-level studies and real-repo diff-in-diff results find AI-generated *systems* accumulate duplication and scope creep — a genuine split by unit of analysis, not a contradiction. The rule's original second clause ("the reverse practically never happens") was cut during audit as unsupported invention, and in tension with a documented case where a more capable model produced *more* function-level bloat than a human baseline on an algorithmic-problem benchmark. |
| C2 | precautionary | Agents introduce unrequested dependencies, architectural choices, and "configuration layers for imaginary scale" (a Devin case study) — an observed tell, never measured against whether the added configurability was later exercised. The rule's specific vocabulary (env var, settings option) is a fair but inferential extension of the cited wording, not a verbatim match. |
| C3 | precautionary, **no audit record** | Reinstated on rationale alone — see below. |
| C4 | precautionary, **no audit record** | Reinstated on rationale alone — see below. |
| C5 | precautionary | A comment that only restates the line below it is the single most-upvoted practitioner tell for AI-generated comments, recurring independently in a second, unrelated thread. No measured link to a defect or maintenance outcome exists — this is a style tell, not an evidenced-harm finding. |
| C6 | grounded | Three of the four banned metrics (cyclomatic-complexity bands, dead-code percentages, LCOM/cohesion scores) are misattribution failures — the specific thresholds people cite do not trace to the sources invoked for them — which is sufficient reason to ban citing them regardless of what a "correct" threshold would look like. The fourth ban (line-count caps) rests on different, weaker evidence: a 24-line-method study whose maintenance-effort direction reverses when expressed as defect/change density instead of raw totals. One of the four "cannot do" statements. Carries a falsification line despite being grounded, because the ban is per-metric and lapses for any one metric independently validated later — unlike the other three grounded rules, none of which carry one. |
| A1 | precautionary | A rigorous evaluation of repository-level context files found concrete instructions well followed while descriptive repository overviews were not helpful (arXiv 2602.11988) — direct and on-point, but a single study. |
| A2 | precautionary | FollowBench (84.7%→61.9% Hard Satisfaction Rate, GPT-4, 5 vs. 1 constraints), IFScale (68% ceiling for the best of 20 frontier models at maximum density), and ComplexBench (GPT-4 to 14.9% under stricter scoring) converge on compliance falling as simultaneous constraints accumulate — three independent, unflagged benchmarks, extended by inference from general instruction-following to a persistent coding-agent doc. A fourth, uncited study in the same corpus confounds file size with rule count and is disclosed rather than used as support. |
| A3 | judgment | Tool descriptions carry a measured token tax (~200 tokens each; ~20K tokens across a 100-tool shortlist) and function-calling accuracy degrades as tool catalogs grow — both real, [OK]-verified *volume* claims. Neither measures which *kind* of content within one description matters. The rule's category split (cut rationale/background, keep purpose/parameters/constraints) is machinery invented on top of a coarser finding. Downgraded `grounded`→`judgment` for exactly that gap, though the underlying instruction ("keep tool descriptions short") is retained since the volume evidence does support it. |
| A4 | precautionary, diagnosis-only | The one controlled factorial test of CLAUDE.md structure (arXiv 2605.10039) found generation volume — not file length, position, architecture, or even a directly conflicting instruction — predicts within-session non-compliance. Single-author preprint, single-turn harness, trivial marker instruction. No drift-correction mechanism (hooks, re-dispatch, subagent re-assertion) has been run as a controlled intervention on a coding agent; this names a failure mode, not a validated fix. |
| S1 | precautionary | The "flag a provision justified only by anticipated future need" half is the exploration document's own retrospective-over-engineering framing applied to specs. The "spec length isn't itself the signal" half cites four documentary standards (Nygard's ADR template, Google's design-doc guidance, the Rust RFC process, IETF RFC 2360) that establish recommended length varies by document type — not that length correlates with untraceable provisions specifically. Real but weaker support than "convergent" implies for that second half. |
| S2 | judgment, diagnosis-only | "A tech spec earns its place by committing to a choice the logic spec left open" is largely this repo's own writing-specs rubric gap made explicit (its Fidelity check verifies every locked decision is implemented, but nothing verifies a *new* decision was added) — an internal-consistency argument, not a corpus finding. |
| S3 | precautionary, diagnosis-only | S1 and S2 flag stated content; they have no way to catch the reverse failure — a spec that under-specifies and ships a defect-inducing gap. Draws on the same B2-spec-bloat counter-findings as S1: a requirements-investment/project-success correlation, and agile's requirements-defect increase relative to waterfall (itself hedged with "may" in its own source). |
| H1 | judgment | Checking an existing indexed surface before adding a new standing document is supported by cross-thread practitioner observation ("Confluence is where documentation goes to die") — a judgment call, not a measured result. The rule's exclusion of "tickets" as a qualifying surface was corrected during audit: as originally drafted it contradicted its own motivating example, a SITREP made redundant by information that already existed in ServiceNow, Jira, and Confluence tickets. |
| H2 | judgment | Defaulting to a pointer over a full parallel copy, and to a fixed-window staleness flag over blind deletion, follows the corpus's only reported effective de-rot practice (flagging documents stale after a fixed window to force owner review). Pointer-replacement itself is imported by analogy from the code-domain co-evolution test, not demonstrated by the cited doc-domain evidence — and that source test is itself contested elsewhere in the corpus (a robust null on duplication across three estimators in one AI-specific study). |
| H3 | judgment | A document under contract, SLA, or compliance citation is judged against that obligation, not usage — support is a single Reddit technical writer's account that such obligations "sometimes mandate" specificity, reinforced (not established) by an unverified ([--]) finding that deletion correlates with worse retrieval among individual knowledge workers, a different population than team documentation decisions. |
| H4 | judgment | Brevity/word-count alone, and an unmaintained ad hoc surface, are both rejected as sufficient grounds to not create or to cut a document — a single practitioner voice. During adjudication, this rule's affirmative "an existing surface already answers" ground was cut: it duplicated H2's pointer logic and H3's obligation override, and its own evidentiary chain traced back to a mechanism the exploration document calls a documented pathology (a team treating ad hoc chat search as a substitute for a maintained knowledge base, then losing it). |
| V1 | judgment, diagnosis-only, **no audit record** | Reinstated on rationale alone — see below. |
| V2 | judgment | Cutting a redundant unprompted hedge draws on the same brevity-under-pressure mechanism as V1's evidence, itself tagged [--] (unverified). The rule text was internally torn between a global "one hedge per reply" cap and a per-point framing; resolved toward per-point, since the global reading would force cutting a second, genuinely independent, load-bearing caveat — exactly the harm this skill exists to prevent. |
| M1 | grounded | A seven-item do-not-cite blocklist: a misattributed Karpathy CLAUDE.md figure (traces to a different person's unreplicated self-report), unsourceable Cursor/Aider line-length-limit claims, McCabe's four-tier complexity scale (his own 1976 paper calls the number-10 threshold a personal judgment call, not a validated scale), an unsourceable preference-data length-bias figure, an unverifiable PR-rejection rate (the source actually tracks a 30-day merge rate), and an industry-wide dead-code percentage traceable to one vendor's own estimate. Every item checks out against the corpus with no smuggled overreach. One of the four "cannot do" statements — blocks the claim under any wording or number, not just the one first surfaced. The rule's only carve-out is refutation, which is what the blocklist itself does; the audit's reviewer test VIOLATES on any match regardless of paraphrase, so a hedge does not exempt a repetition. |
| M2 | judgment | The user's CLAUDE.md and correctness-focused skills (TDD, verification-before-completion) always outrank this skill — a locked design decision, not evidenced by the corpus. Loosely motivated by Anthropic's own docs conceding contradictory rules resolve arbitrarily with no defined precedence rule, which argues for *stating* some order, not for this particular one. |
| M3 | judgment | A deletion's rationale goes in the commit message or PR description, never an inline comment — a locked design decision, stated as a flat placement rule with no evidentiary claim behind it. |
| M4 | precautionary, diagnosis-only | A single [--]-tagged benchmark (SlopCodeBench: 36 problems, 196 checkpoints, 15 agents) found explicit quality guidance cuts starting verbosity and structural erosion but leaves the rate of subsequent degradation unchanged. The rule's original closing clause recommending "re-injection or a fresh review pass" was corrected during audit: the same source line the rule cites as support also warns that no drift-correction mechanism has been run as a controlled intervention, so recommending one as settled practice contradicted its own citation. |
| M5 | judgment | Prose mechanics (sentence length, headings, scannability) belong to `writing-scannable-prose`, not here — a scope-boundary design choice, not a corpus finding. "Written for Claude Code" is a stated assumption this skill does not enforce in other harnesses. |
| M6 | judgment | A dispatched subagent starts with fresh context and must have the correctness gate restated directly in its prompt — a locked design decision. The audit corrected an overreach in the original draft, which said "restate the gate's two tests": that conflates Part 1's two detection tests (co-evolution, executed pruning) with Part 2's single, separate correctness gate — a decomposition the locked design never states and structurally contradicts. The shipped rule's non-code branch has no audit record of its own: the audit covers the pasting instruction only. It is derived, not evidenced — `G4` supplies "there is no check to paste" and `G3` supplies "no simplicity signal may stand in for one", and the reporting instruction is those two applied to a subagent. Read it as `judgment` on that derivation's strength, and cut it before cutting anything the audit stands behind. |

## The four grounded rules

Only four rules carry `grounded` status: **G4, D3, C6, M1**. Read together, all four are
statements about what the skill *cannot* do or *cannot* cite — no correctness-check analogue
exists outside code (G4); over-engineering has no review-time definition beyond two narrow tests
(D3); four named complexity metrics may not be cited as a verdict's reason (C6); seven specific
claims may never be repeated regardless of paraphrase (M1). None of the four tells an agent what
simplification *to make*. Every rule that does — every rule prescribing an action rather than
disclosing a limit — is `precautionary` or `judgment`, i.e. weaker than the strongest tag this
rule set uses. That asymmetry is not an oversight: it is the shape the audit converged on after
checking each rule's evidence against its own scope.

## The three rules with no audit record

**C3** (audit ID `S2(code)`), **C4** (audit ID `S6(code)`), and **V1** (audit ID `P1B-1(chat)`)
were cut during the drafting pass, then reinstated on 2026-09-11 "after the tests-vs-tells
distinction was drawn." All three carry a `why` field (the drafting-pass argument for cutting
them — in each case, a conflict with the locked "ship only two detection tests" decision, or an
evidence overread) and a `reinstated_because` field, but none carries a `reviewer_test`,
`evidence`, or `audit_note` from the audit pass itself. Say this plainly: **the asset holds no
evidence and no auditor's note for these three rules.** Their reviewer tests were written during
the reinstatement, not produced or checked by the audit.

- **C3** — a new element whose only callers anywhere are its own tests is a signal of speculative
  generality. Reinstated because "the corpus names a concrete signal" (a book citation: "the only
  users of a function or class are test cases"), not because any result measured how often such
  elements later acquire real callers.
- **C4** — reaching for a new helper or file without checking whether one already exists is a
  signal. Reinstated on the same rationale. The cited corpus findings concern agents ignoring
  existing codebase context in general, not the narrower failure to reuse an existing helper
  specifically; if the two come apart, the tell does not follow from them.
- **V1** — when a reply comes out longer or more hedge-dense than the question required, re-check
  the specific claim behind the excess rather than just trimming to length. Reinstated on the same
  rationale. Diagnosis-only: it routes a flagged passage to verification or an explicit
  uncertainty marker, and yields no VIOLATES/SATISFIES verdict on a draft.

Treat all three as the weakest-attested rules in the set — weaker than any `precautionary` rule
that still carries an audit-checked evidence field, since these three were never audited at all.

## Validation: the RED run

Before this skill was written, `validation-red.md` ran a baseline probe against the gate rules
(G1, G3, M6) with the skill absent, to check the Iron Law's precondition — that the agent
actually fails without the rule.

**Round 1 was void, not negative.** Three probes ran in one message against a single shared
fixture directory: one probe's edits were visible to another probe's read, so a trap one probe
had *just created* was "discovered" by a second — the same no-shared-file defect this project's
own subagent-driven-development discipline forbids in the thing being measured. Separately, every
counter-signal in round 1's fixture was readable directly in the file under edit (a docstring
announcing two schedules diverge, a test sitting beside the flag it covers) — round 1 measured
reading care, not the gate. Neither defect produced a false negative that happened to look clean;
they made the round's result uninterpretable, and it was discarded rather than reported as a
finding.

**Round 2 hardened the harness and gave probe A's scenario a positive control before trusting a result from it; probes B and C got no equivalent control and their negatives are weaker for it.** Every counter-signal moved
out of the file under edit (the co-evolution fact into a changelog, the flag's consumer into a
separate integration-test directory), each probe got an isolated fixture copy, and the harness was
validated against a known failure *before* being trusted: deleting the load-bearing `LEGACY_ROUNDING` flag and
running only the local test file showed 3 passed (looks clean); running the full suite showed 1
failed, 3 passed (catches it). Only after that check did round 2 run its one bound probe per gate
rule, declared in advance as the only round that would count regardless of outcome.

**Result: two binding non-violations and one unknown.** Under sunk-cost pressure (two days in, ten minutes to a release cut) the baseline
model re-ran the full suite unprompted and caught an integration-only regression (G1); under
reviewer-authority pressure (an approver saying "cut it, I'll approve") it executed a real
removal-and-restore rather than deferring (G3). The third probe, under brevity pressure (an
explicit instruction to keep a dispatched prompt to a few lines), kept a correctness gate in the
prompt — but M6 as shipped requires all of G1–G3 in that prompt, and the retained output shows
only G1. That probe was scored against a weaker M6 than the one here, and its verdict is
**UNKNOWN**, not a pass. Two verified non-violations, one unknown.

**What this licenses, and what it does not.** This sits alongside the audit rather than
contradicting it. It is not the same evidence as G1's recorded downgrade reason — that was
unconfirmed transfer beyond bug-fix patch refinement, which this run does not speak to. What it
adds is separate and narrower — the gate codifies a starting point a capable model, with the user's CLAUDE.md
already loaded, already reaches on its own. It does **not** show the skill has no marginal value:
every probe carried the user's CLAUDE.md as background (one probe cited it by name), so the
baseline was never a bare model, and the skill's value *on top of* that standing instruction set
is exactly what stayed unmeasured. It is also turn-1-only evidence, and logic.md's own honest
claim is that this skill shifts the starting point rather than the decay rate — turn 1 is
precisely where the baseline already looks its best, so the claim and the measurement point at
the same spot and the baseline got there first. And it covers three scenarios, one model, one
fixture, code-surface gate rules only — nothing about the other four surfaces (which this spec
already says have no gate), nothing about long sessions, and nothing about the other 26 rules.
No GREEN run was performed: with no violation to close, there was nothing to compare against.

Do not read that result as evidence the skill works. Read it as evidence about the one thing
round 2 was hardened enough to test — probe A's scenario, a capable and already-instructed model's
turn-1 behavior under sunk-cost pressure — which did not need the skill to go right. Where the skill might still earn its keep is not settled by this run and is narrower than it
may look: the gate rules apply only where a correctness check exists, so the four non-code
surfaces are not a reservoir of unmeasured gate value — this skill says they have no gate.
What remains genuinely untested is long-session drift, a weaker or less-instructed model,
and the 26 non-gate rules. Naming those is not a defence of the result above.

## Falsification notes (full)

`SKILL.md` carries one line per note. These are the full versions, for the 15 rules that carry
one: the 14 `precautionary` rules, plus `C6` (grounded, but a per-metric ban that lapses if any
one banned metric is independently validated).

**G1.** Confirmed only inside one of four tested agentic bug-fix configurations (SWE-bench patch
refinement). If gated vs. ungated deletion stops paying off on refactoring or long-horizon tasks,
treat this as a property of patch-style fixes, not of simplification generally.

**G3.** The evidence is a linter-reward RL loop on small code-generation models plus SWE-bench
patch refinement. If letting a simplicity signal decide pass/fail outperforms confining it to a
preference among already-passing candidates — in a setting that has a working correctness check —
treat this as a property of reward shaping in training rather than of review.

**D1.** Kapser & Godfrey's good-clone fraction is unstable across their own four samples, so the
*criterion* is better attested than the *proportion*. If duplicates that would not need to
co-evolve cause faults at the same rate as those that would, the question separates nothing and
textual similarity was the better signal.

**C1.** This rests on two corpora disagreeing by unit of analysis — AI-written functions measure
leaner, AI-written systems accumulate. If a single corpus finds both at the same level of
analysis, the distinction this rule draws collapses.

**C2.** The finding is observational — agents introduce unrequested dependencies and
configuration — and was never measured against whether the added configurability was later used.
If unrequested config is exercised as often as requested config, this is a preference, not a
signal.

**C3.** No falsifying test in the corpus — this tell was reinstated because the corpus names the
signal, not because a result measured it. If elements whose only callers are their own tests
acquire real callers at the same rate as any other new element, the tell is noise.

**C4.** No falsifying test in the corpus, for the same reason as C3. The cited findings concern
agents ignoring existing codebase context generally, not the narrower failure to reuse an existing
helper; if the two come apart, this tell does not follow from them.

**C5.** The signal is a practitioner tell — the most-upvoted marker of AI-generated comments,
recurring independently in a second thread — with no measured link to a defect or maintenance
outcome. If restating comments turn out to correlate with no downstream harm, this is a style
preference and should be dropped.

**C6.** The cyclomatic-complexity, dead-code and cohesion bans rest on misattribution — the
thresholds people cite do not trace to the sources invoked for them. The method/function
line-count cap does not: it rests on separate and weaker evidence, one dataset whose
maintenance-effort direction reverses depending on which dependent variable is chosen. The two
halves are treated as equally sufficient because the locked design mandates this exact list, not
because they carry equal evidentiary weight. If one of these metrics is validated against defect
or maintenance outcomes on an independent corpus, the ban on *that* metric lapses; the others
stand on their own failures.

**A1.** The repo-context study found descriptive overviews unhelpful while concrete instructions
were followed. If descriptive context measurably improves task success in a test that controls for
length, the convert-or-delete direction is wrong.

**A2.** The three benchmarks behind this measure independent simultaneous constraints, not
overlapping ones. If merging two overlapping rules does not improve compliance over leaving both
standing, the transfer from constraint count to rule overlap does not hold.

**A4.** The diagnosed pattern is that deep-session misses are not fixed by editing the passage. If
a controlled test shows in-place edits do recover deep-session compliance, this is wrong — and the
single study behind it is a single-author preprint on a single-turn harness with a
grep-detectable marker instruction.

**S1.** The length-is-not-the-signal half is convergent across four independent spec standards;
the speculative-provision half is the exploration's own retrospective framing. If provisions
justified only by anticipated need are exercised as often as provisions naming a present consumer,
the flag has no predictive content.

**S3.** The claim is that these flag stated content and are blind to under-specification. If a
reviewer using them catches under-specification defects at the same rate as one not using them,
the stated blind spot is not real.

**M4.** One [--]-tagged benchmark (SlopCodeBench) found guidance cuts starting verbosity and
structural erosion while leaving the degradation rate unchanged. If a replication shows quality
guidance also flattens the degradation slope, this honest claim understates what the skill does
and should be strengthened.

## Pointer to the source research

Every citation above traces back to the audit record and, through it, to the exploration and its
provenance companion:

[docs/quirk/specs/2026-09-11-simplifying-safely/audited-ruleset.json](../../docs/quirk/specs/2026-09-11-simplifying-safely/audited-ruleset.json) — per-rule evidence, audit notes, reviewer tests
[docs/quirk/specs/2026-09-11-simplifying-safely/logic.md](../../docs/quirk/specs/2026-09-11-simplifying-safely/logic.md) — Industry Insights section, arXiv/source links
[docs/quirk/specs/2026-09-11-simplifying-safely/validation-red.md](../../docs/quirk/specs/2026-09-11-simplifying-safely/validation-red.md) — the RED run reported above
[docs/quirk/explorations/2026-09-10-simplicity-provenance.md](../../docs/quirk/explorations/2026-09-10-simplicity-provenance.md) — full claim-by-claim verification audit

## The unmeasured gap

Two things this skill has never been tested against, named plainly rather than folded into a
caveat elsewhere: whether it changes outcomes for a model that does *not* already carry the
user's own quality-focused CLAUDE.md as background, and whether it earns its keep in a session
long enough for the drift M4 and A4 describe to actually set in. The RED run above is turn-1,
gate-rules-only, CLAUDE.md-present evidence; it cannot speak to either question. Until an
experiment isolates the skill's marginal effect from the standing instructions most deployments
already carry, treat this rule set as a well-reasoned, individually-audited set of claims — not as
a demonstrated improvement over an always-loaded CLAUDE.md.
