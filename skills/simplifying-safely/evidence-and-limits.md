# Evidence and limits

This maintained companion records what each of the 32 rules in [SKILL.md](SKILL.md) rests on:
status, evidence or rationale, the audit's reviewer test and its limits, and — for the 15 rules
that carry one — the full falsification note. It also records the audit-to-shipped renumber and
the behavioral validation run performed before the skill was written.

Nothing here changes agent behavior. [SKILL.md](SKILL.md) is the complete operative artifact;
the reviewer tests below document how wording was assessed, not additional instructions. The
provenance source is the frozen
[audited ruleset](../../docs/quirk/specs/2026-09-11-simplifying-safely/audited-ruleset.json),
with the approved
[logic-spec amendments](../../docs/quirk/specs/2026-09-11-simplifying-safely/logic.md#status--amendments)
taking precedence where the frozen review record and the shipped wording differ. The audit's
`audit_note` narrowing is preserved rather than the stronger claim that first entered review.

## Proposal workflow revision — 2026-09-14

The user requested a more versatile, prescriptive skill after its Heimdall logic-spec review
reported no clear S1 finding but failed to propose most useful structural changes. The revised
workflow separates proposal generation from correctness claims. Its transformation prompts,
shared standing-document routing, expanded H2 and authorization-aware non-code M6 are **judgment**,
not newly audited research findings. Existing evidence tags and the code gate are unchanged.

The rationale is the exploration's direction 3 (“use LLM review only to propose”), its separation
of insight from invented machinery, and its warning that document cuts must preserve a maintained,
complete answer. See [the exploration](../../docs/quirk/explorations/2026-09-10-simplicity.md#idea-landscape).
The workflow does not claim that these sources validate its effectiveness.

Historical audit mappings and reviewer tests below retain their provenance. This revision supersedes
the former report-only non-code dispatch rule and the exact-wording fixture requirement: packaging
checks remain, but prose, heading-order and inventory pins were removed rather than updated to bless
new wording. Behavioral exercises, not source-text matches, assess proposal usefulness.

**Behavioral smoke exercise:** two fresh read-only scout agents loaded the revised skill. One
reviewed the Heimdall logic spec; one answered four contrasting miniature requests. The Heimdall
response proposed consolidating repeated normative sections, separating history/research and
resolving the lease-definition conflict, while retaining freshness, ledger and ownership safeguards.
The contrasting responses kept a coherent current importer spec unchanged, proposed removing
future-only plugin infrastructure, retained explicit offline recovery steps rather than an online
pointer, and left an unexecuted D2 rule-removal decision unadjudicated.

These outputs demonstrate proposal generation and restraint on those inputs, not correctness of
every recommendation. The cases were single exercises, the four miniature requests shared one
agent context, and no matched old/new comparison or authorized-edit scenario was run. The original
Heimdall conversation motivated the change but is not a controlled baseline. No general effectiveness
claim or document correctness certification follows. The six retained packaging checks passed with
`python3 -m pytest tests/test_simplifying_safely_skill.py -q`; they verify packaging, not these behaviors.

## Amendment boundary

Amendments 7–12 are part of the shipped provenance, not later commentary:

- **7:** `M6` is scoped to code fixes. Its non-code branch is a derivation from `G4` and `G3`,
  not an audited finding.
- **8:** `G3` limits what a simplicity signal may decide in the fix gate; it does not disarm the
  verdicts from `D1` and `D2`, and it does not outrank the user or standing correctness rules.
- **9:** `M1` permits naming a blocked claim only to refute it. Hedged repetition is still
  repetition; the frozen audit test's unconditional "any match" wording is therefore too broad.
- **10:** the behavioral baseline produced two binding non-violations and one unknown, not a RED
  failure and not three clean passes. The full limits are recorded below.
- **11:** the correctness gate exists only where a correctness check exists; the companion does
  not transfer it to any non-code surface.
- **12 (historical):** exact reviewed rule wording was pinned as a fixture. The proposal-workflow
  revision above removes that pin; the original audit remains a historical record.

## Audit → shipped ID mapping

The frozen audit preserved overloaded origins in both `section` and `id`; those two fields together
identify a record. The shipped skill uses one collision-free ID per rule. The mapping below copies
the audit fields verbatim rather than inventing aliases such as an unqualified `D1` or `S1`.

**Always-on core (7)**

| Audit section | Audit ID | Shipped | Status |
|---|---|---|---|
| `gate` | `G1` | G1 | precautionary |
| `gate` | `G2` | G2 | judgment |
| `gate` | `G3` | G3 | precautionary |
| `gate` | `G4` | G4 | grounded |
| `tests` | `D1-coevolution` | D1 | precautionary |
| `tests` | `D2-pruning-executed` | D2 | judgment |
| `tests` | `D3-retrospective-only` | D3 | grounded |

**Code (6)**

| Audit section | Audit ID | Shipped | Status |
|---|---|---|---|
| `surface-code` | `S1(code)` | C1 | precautionary |
| `surface-code` | `S5(code)` | C2 | precautionary |
| `surface-code` | `S2(code)` | C3 | precautionary |
| `surface-code` | `S6(code)` | C4 | precautionary |
| `surface-code` | `S7(code)` | C5 | precautionary |
| `tests` | `D4-blocklist-metrics` | C6 | grounded |

**Agent-facing docs (4)**

| Audit section | Audit ID | Shipped | Status |
|---|---|---|---|
| `surface-agentdocs` | `D1(agentdocs)` | A1 | precautionary |
| `surface-agentdocs` | `D2(agentdocs)` | A2 | precautionary |
| `surface-agentdocs` | `D4(agentdocs)` | A3 | judgment |
| `surface-agentdocs` | `D5(agentdocs)` | A4 | precautionary |

**Specs (3)**

| Audit section | Audit ID | Shipped | Status |
|---|---|---|---|
| `surface-specs` | `S1(specs)` | S1 | precautionary |
| `surface-specs` | `S2(specs)` | S2 | judgment |
| `surface-specs` | `S3(specs)` | S3 | precautionary |

**Human-facing docs (4)**

| Audit section | Audit ID | Shipped | Status |
|---|---|---|---|
| `surface-humandocs` | `HD1` | H1 | judgment |
| `surface-humandocs` | `HD2` | H2 | judgment |
| `surface-humandocs` | `HD3` | H3 | judgment |
| `surface-humandocs` | `HD4` | H4 | judgment |

**Conversational output (2)**

| Audit section | Audit ID | Shipped | Status |
|---|---|---|---|
| `surface-chat` | `P1B-1(chat)` | V1 | judgment |
| `surface-chat` | `P1B-2(chat)` | V2 | judgment |

**Meta (6)**

| Audit section | Audit ID | Shipped | Status |
|---|---|---|---|
| `meta` | `M1` | M1 | grounded |
| `meta` | `M2` | M2 | judgment |
| `meta` | `M3` | M3 | judgment |
| `meta` | `M4` | M4 | precautionary |
| `meta` | `M5` | M5 | judgment |
| `meta` | `M6` | M6 | judgment |

The tally is 4 `grounded`, 14 `precautionary`, and 14 `judgment`. Seven rules have
`reviewer_test_holds: false` and ship as diagnosis-only: **D3, C1, A4, S2, S3, V1, M4**.

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
| G3 | precautionary | A Ruff-linter-reward RL loop degraded pass@1 when simplicity dominated its training signal but improved over test-only when subordinated to a unit-test gate; RECAP's ungated minimal-patch modes cost resolved instances, and one practitioner report describes minimality pressure stripping working features. All three are patch-refinement, small-model-training, or anecdotal evidence. The audit's absolute "only the correctness re-check may decide" wording was narrowed by amendment 8: this evidence constrains a simplicity signal's authority in the fix gate; it does not silence `D1` or `D2`, and it establishes no precedence over the user's instructions or standing correctness rules. |
| G4 | grounded | "The correctness gate has no evidenced analogue outside code" is the exploration document's own stated absence, not an inference from a transferred result. It covers specs, agent-facing docs, human-facing docs, and conversational output, and is one of the four rules stating what the skill cannot do rather than what it can. |
| D1 | precautionary | Kapser & Godfrey's §4.2 co-evolution question is the literal deciding criterion for harmful clones, not a paraphrase — but their own "good clone" fraction is unstable across four case-study samples (71% / 42% / 33% / 57%), and the citation carries no adversarial-verification mark. The reviewer test checks that a co-evolution claim was *stated*, not that it's true. |
| D2 | judgment | "Cut a rule if the task still goes fine without it" is itself grounded — Claude Code's own docs state it as a real, cited pruning practice. What's invented, and what earns the `judgment` tag, is converting that from a *predicted* judgment ("would removing this cause a mistake?") into an *executed* one (remove it, run the task, observe). The method is judgment; the underlying keep/cut criterion is not. |
| D3 | grounded, diagnosis-only | "Over-engineering has no review-time definition — every review-time test in this document is a proxy for a fact that has not happened yet" is the exploration document's own headline synthesis, drawn from an independently cross-thread-confirmed practitioner consensus. No reviewer test is claimed; this rule names a limit, not a checkable property. |
| C1 | precautionary, diagnosis-only | A 500k-function study finds AI-generated functions shorter and structurally simpler than human ones; project-level studies and real-repo diff-in-diff results find AI-generated *systems* accumulate duplication and scope creep — a genuine split by unit of analysis, not a contradiction. The rule's original second clause ("the reverse practically never happens") was cut during audit as unsupported invention, and in tension with a documented case where a more capable model produced *more* function-level bloat than a human baseline on an algorithmic-problem benchmark. |
| C2 | precautionary | Agents introduce unrequested dependencies, architectural choices, and "configuration layers for imaginary scale" (a Devin case study) — an observed tell, never measured against whether the added configurability was later exercised. The rule's specific vocabulary (env var, settings option) is a fair but inferential extension of the cited wording, not a verbatim match. |
| C3 | precautionary, **rationale-only reinstatement** | The frozen record contains a `why`, `reinstated_because`, status, and a reviewer test written at reinstatement, but no audit-pass `evidence` or `audit_note`. See the dedicated section below. |
| C4 | precautionary, **rationale-only reinstatement** | The frozen record contains a `why`, `reinstated_because`, status, and a reviewer test written at reinstatement, but no audit-pass `evidence` or `audit_note`. See the dedicated section below. |
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
| H2 | judgment | Pointer replacement was originally imported by analogy from code co-evolution, not demonstrated by document-domain evidence. The proposal-workflow revision extends this to repeated sections and explicitly preserves unique qualifications and self-contained procedures. Resolving authority before consolidation and retaining necessary local instructions are editorial judgments, not a validated duplication test. |
| H3 | judgment | A document under contract, SLA, or compliance citation is judged against that obligation, not usage — support is a single Reddit technical writer's account that such obligations "sometimes mandate" specificity, reinforced (not established) by an unverified ([--]) finding that deletion correlates with worse retrieval among individual knowledge workers, a different population than team documentation decisions. |
| H4 | judgment | Brevity/word-count alone, and an unmaintained ad hoc surface, are both rejected as sufficient grounds to not create or to cut a document — a single practitioner voice. During adjudication, this rule's affirmative "an existing surface already answers" ground was cut: it duplicated H2's pointer logic and H3's obligation override, and its own evidentiary chain traced back to a mechanism the exploration document calls a documented pathology (a team treating ad hoc chat search as a substitute for a maintained knowledge base, then losing it). |
| V1 | judgment, diagnosis-only, **rationale-only reinstatement** | The frozen record contains a `why`, `reinstated_because`, status, and a diagnosis-only reviewer field written at reinstatement, but no audit-pass `evidence` or `audit_note`. See the dedicated section below. |
| V2 | judgment | Cutting a redundant unprompted hedge draws on the same brevity-under-pressure mechanism as V1's evidence, itself tagged [--] (unverified). The rule text was internally torn between a global "one hedge per reply" cap and a per-point framing; resolved toward per-point, since the global reading would force cutting a second, genuinely independent, load-bearing caveat — exactly the harm this skill exists to prevent. |
| M1 | grounded | The audit checked every claim in the inline `M1` blocklist against the research corpus and found each prohibition supported without overreach. This companion does not reproduce that list: [SKILL.md](SKILL.md) is its sole maintained location. Amendment 9 narrows the audit's unconditional "any match" reviewer wording only enough to let a claim be named for refutation; assertion, paraphrase, or hedged repetition remains outside that carve-out. |
| M2 | judgment | The user's CLAUDE.md and correctness-focused skills (TDD, verification-before-completion) always outrank this skill — a locked design decision, not evidenced by the corpus. Loosely motivated by Anthropic's own docs conceding contradictory rules resolve arbitrarily with no defined precedence rule, which argues for *stating* some order, not for this particular one. |
| M3 | judgment | A deletion's rationale goes in the commit message or PR description, never an inline comment — a locked design decision, stated as a flat placement rule with no evidentiary claim behind it. |
| M4 | precautionary, diagnosis-only | A single [--]-tagged benchmark (SlopCodeBench: 36 problems, 196 checkpoints, 15 agents) found explicit quality guidance cuts starting verbosity and structural erosion but leaves the rate of subsequent degradation unchanged. The rule's original closing clause recommending "re-injection or a fresh review pass" was corrected during audit: the same source line the rule cites as support also warns that no drift-correction mechanism has been run as a controlled intervention, so recommending one as settled practice contradicted its own citation. |
| M5 | judgment | Prose mechanics (sentence length, headings, scannability) belong to `writing-scannable-prose`, not here — a scope-boundary design choice, not a corpus finding. "Written for Claude Code" is a stated assumption this skill does not enforce in other harnesses. |
| M6 | judgment | Fresh subagent context and inline code-gate restatement are design choices, not corpus findings. Amendment 7 limited the pasted fence to code fixes. The proposal-workflow revision replaces its report-only non-code branch with the user's review/edit authorization and preservation obligations; unresolved policy remains a human choice, and no simplicity signal certifies correctness. The unchanged imperative code fence lives only in [SKILL.md](SKILL.md). |

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

## The three rationale-only reinstatements

**C3** (audit ID `S2(code)`), **C4** (audit ID `S6(code)`), and **V1** (audit ID `P1B-1(chat)`)
were cut during the drafting pass, then reinstated on 2026-09-11 "after the tests-vs-tells
distinction was drawn." All three carry a `why` field (the drafting-pass argument for cutting
them — in each case, a conflict with the locked "ship only two detection tests" decision, or an
evidence overread) and a `reinstated_because` field. Their later records also contain status and
reviewer-test text, but no audit-pass `evidence` or `audit_note`: **the frozen asset holds no
audited evidence or auditor's note for these three rules.** Their reviewer tests were written
during reinstatement, not produced or checked by the audit.

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
that carries an audit-checked evidence field, because none was re-audited after reinstatement.

## Reviewer tests and their limits

These are maintained summaries of the frozen `reviewer_test` fields, corrected where amendments
changed what the shipped rule means. They explain the review basis; they do not add a test or a
remedy absent from [SKILL.md](SKILL.md). A reviewer test can show that a draft states or records
the required fact. It generally cannot show that the fact is true, that the cited mechanism
transfers, or that the rule improves an outcome.

### Always-on core

- **G1 — audit test:** a shrinking change violates when it is presented as complete without a
  correctness check run against the post-change state; it satisfies when completion rests on that
  result. **Limit:** a record of a run can be inspected, but the audit test neither validates the
  chosen check's coverage nor establishes transfer beyond patch-style bug fixing.
- **G2 — audit test:** unequal justification, scrutiny, or re-check burdens for an addition and an
  equivalent deletion violate; the identical post-change re-check satisfies. **Limit:** "equivalent"
  still requires judgment, and the preference for symmetry is the locked design choice the corpus
  did not adjudicate.
- **G3 — amended reviewer test:** a simplicity signal used on this skill's authority to decide pass
  or fail violates; using it only to prefer among candidates that have cleared the correctness
  check satisfies. **Limit:** amendment 8 supersedes the audit's broader "correctness and nothing
  else" formulation. The test says nothing against `D1`/`D2` verdicts, a user instruction, or a
  standing correctness rule.
- **G4 — audit test:** a non-code rule that invents a mechanical substitute gate, or omits the
  absence while implying one, violates; naming the absence and leaving the disposition to human
  judgment satisfies. **Limit:** it tests the guidance's framing, not whether a human's eventual
  decision is correct.
- **D1 — audit test:** a duplication verdict based only on textual similarity violates; a verdict
  that states whether a shared requirement forces co-evolution satisfies. **Limit:** the audit
  checks that the co-evolution claim was stated, not that it is true; boilerplate can pass.
- **D2 — audit test:** a keep/cut decision resting only on a predicted counterfactual violates; a
  recorded removal-and-rerun with an observed outcome satisfies. **Limit:** the audit supplies no
  priced, validated harness or repeatability result. If no real run is available, the rule remains
  unadjudicated rather than gaining a verdict.
- **D3 — no verdict test:** the frozen field says diagnosis only. **Limit:** retrospective
  over-engineering cannot be established at review time; the rule records that boundary rather
  than pretending a reviewer can decide it.

### Code

- **C1 — no verdict test:** the frozen field treats change-level framing as diagnosis governing
  how the other code tells are read. **Limit:** the cited corpora differ as well as their units of
  analysis, so the framing does not prove any particular diff over-produced.
- **C2 — audit test:** a new configurable input or dependency set once, unrequested, and without a
  named need violates; a task, convention, or named caller that requires it satisfies.
  **Limit:** the test turns task interpretation and future-use claims into reviewer judgments; the
  observational evidence never measured eventual use.
- **C3 — reinstatement test:** a codebase-wide caller search finding only the new element's own
  tests violates; a non-test caller or named present caller satisfies. **Limit:** this test was
  written during rationale-only reinstatement, not audited, and current callers do not predict
  whether later callers will appear.
- **C4 — reinstatement test:** adding an equivalent helper, utility, or local pattern without
  reusing it violates; no equivalent, or a named reason the existing one does not fit, satisfies.
  **Limit:** this test was written during rationale-only reinstatement, not audited. Equivalence is
  judgment-laden, and a claimed search cannot be verified from the diff alone.
- **C5 — adjudication test:** a diff adding a comment whose content is fully recoverable from the
  next line violates; otherwise it satisfies. **Limit:** this identifies a tell only. It does not
  establish downstream harm or independently authorize removal; the evidence is practitioner
  observation, and the record was added during rule-set adjudication rather than the original
  drafting pass.
- **C6 — audit test:** a simplicity verdict resting on one of `C6`'s inline barred metrics violates;
  a verdict reasoned through `D1`, `D2`, or left explicitly unadjudicated satisfies. **Limit:** the
  four metric categories do not share equal evidence, and validation of one would affect only that
  category. The authoritative categories remain in [SKILL.md](SKILL.md), not this companion.

### Agent-facing docs

- **A1 — audit test:** trimming or rearranging an agent-facing document while leaving its
  descriptive overview intact violates; converting or removing that material in favor of concrete
  directives satisfies. **Limit:** a single repo-context study supports the direction and does not
  establish that every descriptive passage lacks task value.
- **A2 — audit test:** a completed diff leaving two live rules covering substantially the same
  ground violates; a result with no overlap, or with the overlap merged or cut, satisfies.
  **Limit:** "substantially the same" remains a reviewer judgment, and the backing benchmarks vary
  independent constraint counts rather than overlapping-rule pairs.
- **A3 — audit test:** a tool-description sentence that would change neither tool selection nor
  invocation violates; every sentence bearing on one of those decisions satisfies. **Limit:** the
  token-cost and catalog studies measure volume, not this content-category counterfactual.
- **A4 — no verdict test:** the frozen field labels the repeated deep-session-miss pattern
  diagnosis-not-enforcement. **Limit:** no static-file edit, hook, re-dispatch, or other correction
  mechanism has been validated here, so the record supports neither a verdict nor a preferred fix.

### Specs

- **S1 — audit test:** a provision justified only by anticipated future need, with no current
  consumer, ticket, or test, violates; no such provision satisfies. **Limit:** ordinary
  requirements without inline consumer citations are outside the trigger, and the evidence never
  measured whether anticipatory provisions are later exercised.
- **S2 — no shipped verdict test:** the audit drafted a binary test asking whether a second spec
  commits to a choice left open by the first, but set `reviewer_test_holds: false`; the shipped
  rule is diagnosis-only. **Limit:** template-required implementation detail already tends to meet
  the drafted criterion, and the rationale is this repository's rubric gap rather than a finding.
- **S3 — no verdict test:** the frozen field asks that the blind spot be stated beside `S1` and
  `S2`, not adjudicated. **Limit:** it names their inability to detect under-specification; it
  supplies no method for finding such gaps and cannot turn either tell into a code-style gate.

### Human-facing docs

- **H1 — audit test:** a new document that restates a current, indexed, one-place answer without
  saying why it cannot live there violates; naming the checked surface and the actual gap satisfies.
  **Limit:** whether a source is maintained, indexed, and already an answer rather than scattered
  facts remains a human judgment.
- **H2 — audit test:** keeping an unsynchronized full copy of content authoritative elsewhere,
  without considering a pointer, violates; a sole source or reduced pointer satisfies.
  **Limit:** pointer replacement is an analogy, not the mechanism shown effective by the cited
  document evidence, and outright deletion needs reasoning the test cannot validate.
- **H3 — audit test:** changing a document carrying an obligation citation on usage, staleness, or
  overlap alone violates; judging the obligated content against that obligation satisfies.
  **Limit:** the corpus support is a single practitioner report. The test protects the content,
  not the document's current location; consolidation can preserve the obligation.
- **H4 — audit test:** length preference alone, or reliance on an unmaintained or ad hoc surface
  without addressing its adequacy, violates; a different stated basis satisfies. **Limit:** the
  test only rejects two reasons. It does not prove that any remaining reason is sufficient or that
  an alternative surface is maintained.

### Conversational output

- **V1 — no verdict test:** the reinstatement field is explicitly diagnosis only; it routes a
  flagged passage but assigns no VIOLATES/SATISFIES result to the reply. **Limit:** this is a
  rationale-only reinstatement, and the corpus does not establish that excess length localizes
  uncertainty to a specific claim.
- **V2 — audit test:** repeating the same hedge on one point, or retaining a hedge removable
  without changing the reader's next action, violates; distinct load-bearing caveats satisfy.
  **Limit:** the action counterfactual is reviewer judgment, the evidence is unverified, and the
  audited correction rejects a global per-reply hedge cap.

### Meta

- **M1 — amended reviewer test:** asserting or repeating any claim in the inline `M1` blocklist,
  including by paraphrase or hedge, violates. Naming one solely in order to refute it is the only
  exception. **Limit:** amendment 9 supersedes the frozen "any match" wording because that wording
  would reject the refuting blocklist itself. Semantic paraphrase detection remains reviewer work;
  this companion deliberately does not carry a second copy of the claims.
- **M2 — audit test:** skipping a required test, verification step, or explicit user instruction
  because a simpler result would satisfy violates. **Limit:** the order is a design decision, not a
  corpus result, and identifying an applicable "similar" correctness rule still requires context.
- **M3 — audit test:** a new inline comment explaining why a deletion happened violates; the same
  explanation in the commit or PR record satisfies. **Limit:** the test imposes no requirement to
  write a rationale at all, and the user's standing instructions can resolve an overlapping
  comment requirement.
- **M4 — no verdict test:** the frozen field labels the starting-point/decay claim diagnosis only.
  **Limit:** it is one unverified benchmark, the baseline run did not measure long-session decay,
  and no correction mechanism is validated.
- **M5 — mixed audit test:** prose-mechanics rules in this skill rather than a pointer to
  `writing-scannable-prose` violate; the Claude Code harness assumption has no reviewer test.
  **Limit:** both halves are scope choices, not evidence that the rule set behaves the same in
  another harness.
- **M6 — revised review basis:** code dispatch still carries the literal `G1`–`G3` fence from
  [SKILL.md](SKILL.md). Non-code dispatch carries user authorization and obligations to preserve,
  permits authorized restructuring, and surfaces unresolved policy choices without claiming a
  correctness gate. **Limit:** this authorization distinction is a design judgment, not an audited
  result; the original audit covered inline restatement rather than this non-code workflow.

## Validation: the RED run

Before this skill was written,
[validation-red.md](../../docs/quirk/specs/2026-09-11-simplifying-safely/validation-red.md)
ran baseline probes against G1, G3, and M6 with the skill absent, testing the Iron Law's
precondition that an agent actually fails without the rule.

**Round 1 was void, not negative.** Three probes ran in one message against a single shared
fixture directory: one probe's edits were visible to another probe's read, so a trap one probe
had *just created* was "discovered" by a second — the same no-shared-file defect this project's
own subagent-driven-development discipline forbids in the thing being measured. Separately, every
counter-signal in round 1's fixture was readable directly in the file under edit (a docstring
announcing two schedules diverge, a test sitting beside the flag it covers) — round 1 measured
reading care, not the gate. Neither defect produced a false negative that happened to look clean;
they made the round's result uninterpretable, and it was discarded rather than reported as a
finding.

**Round 2 hardened the harness and gave probe A's scenario a positive control before trusting its
result; probes B and C got no equivalent control, so their negatives are weaker.** Every
counter-signal moved out of the file under edit, each probe got an isolated fixture copy, and the
harness was exercised against a known failure first: deleting the load-bearing
`LEGACY_ROUNDING` flag looked clean under the local tests but failed under the full suite. That
positive control establishes only probe A's G1 scenario, not probes B or C. Round 2 then ran one
prespecified probe per target and kept the declared stopping bound regardless of outcome.

**Result: two binding non-violations and one unknown.** Under sunk-cost pressure the baseline
model re-ran the full suite unprompted and caught an integration-only regression (G1); under
reviewer-authority pressure it executed a real removal-and-restore rather than deferring (G3).
The G1 result is independently established by its positive control. The G3 result binds the
shipped rule but is suggestive and uncontrolled. Under brevity pressure, the third probe kept a
correctness check in its dispatch prompt, but shipped M6 carries all of G1–G3 and the retained
excerpt establishes only G1. That probe was scored against a weaker M6 and cannot be re-scored
from the retained record, so its verdict is **UNKNOWN**, not a pass.

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

Do not read this as evidence that the skill works. Read it as a narrow result about a capable,
already-instructed model's turn-1 behavior: the controlled G1 scenario did not need the skill to
go right, the uncontrolled G3 scenario also produced a binding non-violation, and M6 stayed
unknown. The four non-code surfaces are not a reservoir of unmeasured gate value because this
skill claims no gate there. Long-session drift, a weaker or less-instructed model, and the 26
non-gate rules remain genuinely untested; naming those limits is not a defense of the result.

## Falsification notes (full)

[SKILL.md](SKILL.md) carries one line per note. These are the full versions for the 15 rules that
carry one: the 14 `precautionary` rules plus `C6`, whose per-metric prohibition can lapse
independently. The other 17 rules — 14 `judgment` and the remaining three `grounded` rules — have
no falsification note in the approved record.

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

Literature-backed claims here trace to the frozen audit and, through it, to the exploration
provenance. The three rationale-only reinstatements and M6's non-code derivation are the explicit
exceptions described above:

[Frozen audited ruleset](../../docs/quirk/specs/2026-09-11-simplifying-safely/audited-ruleset.json) — per-rule fields and audit notes
[Approved logic spec and amendments](../../docs/quirk/specs/2026-09-11-simplifying-safely/logic.md) — rationale and amendment authority
[Behavioral validation record](../../docs/quirk/specs/2026-09-11-simplifying-safely/validation-red.md) — the bounded baseline run
[Exploration provenance](../../docs/quirk/explorations/2026-09-10-simplicity-provenance.md) — claim-by-claim source verification

## The unmeasured gap

Two material questions remain unmeasured: whether the skill changes outcomes for a model that does
not already carry the user's quality-focused CLAUDE.md, and whether it earns its keep in a session
long enough for the drift `M4` and `A4` describe to appear. The baseline is turn-1,
gate-rules-only, CLAUDE.md-present evidence and cannot answer either question. Until an experiment
isolates the skill's marginal effect from standing instructions, treat this as a maintained,
audited rule set with three explicitly rationale-only reinstatements — not as a demonstrated
improvement over an always-loaded CLAUDE.md.
