# Logic spec: `simplifying-safely`

**Status**: Draft — reviewed, corrections applied, awaiting user sign-off

A quirk skill that helps an agent notice when it is over-producing, and makes every fix for that
subordinate to a correctness check. Derived from
[2026-09-10-simplicity.md](../../explorations/2026-09-10-simplicity.md) and its
[provenance companion](../../explorations/2026-09-10-simplicity-provenance.md).

## Conceptual model

Over-production is real and worth spotting, but every fix for it is subordinate to a correctness
check — and outside code no such check exists, so the skill says less there and says so.

The skill makes three claims and nothing beyond them:

1. **Agents over-produce**, for reasons in the training signal rather than as a fault to be lectured
   out. Reward models correlate length with reward; models generate compressible padding correlated
   with their own uncertainty.
2. **Ungated pressure to simplify destroys function.** Prompting for minimal patches costs resolved
   instances; a linter used as the dominant training reward teaches deletion rather than improvement;
   a practitioner appending "minimum viable functionality" reported the agent stripping working
   features. Three evidence levels, one shape.
3. **Almost nothing about over-engineering is decidable at review time.** The only clean definition —
   complexity anticipating a requirement that never arrives — is retrospective. Two tests survived
   that constraint. The skill ships those and admits the rest.

It is deliberately not a theory of simplicity. The Hickey/Ousterhout canon explains why people care;
it gives a reviewer nothing to apply to a diff, and stays in the exploration document.

**The honest claim.** The skill shifts starting verbosity and complexity downward. It does not change
how fast quality erodes across a long session. Nothing here promises a better session, and a reader
who expects one has been misled.

## Data flow

The skill fires on narrow triggers — a simplification or cleanup request, a review, authoring an
agent-facing document, writing a spec — not on every code task.

Once loaded, an always-on core applies: the gate, the two surviving detection tests, and two framing
statements. The surface in play then activates its own small rule group, so a task touching one
surface faces seven to eleven simultaneous constraints rather than all thirty-two — counting the
five core checks that decide, plus that surface's group. Code is the worst case at eleven, and code
is the modal surface. The tiering does not cap stacking across surfaces, and the common tasks span
two: implementing a spec'd change touches code and the spec that authorized it. This tiering exists
because compliance falls measurably as simultaneous constraints accumulate — which is also why the
single-surface figure should not be read as covering the multi-surface case, where nothing caps it.

Work proceeds in two sequenced jobs. **Part 1** spots over-production: the two tests decide, and
per-surface tells prompt a closer look without deciding anything. **Part 2** gates the fix: any step
that shrinks, simplifies or deletes is sequenced after a correctness check and re-validated against
it. Part 2 is stated once and inherited by every surface — never restated per surface, which would
both inflate the constraint count and create the synchronized-co-evolution debt the skill's own
duplication test is designed to catch.

The surface in play also identifies the moment. Writing a spec is planning time; writing code is
code time; a document or a reply is whenever that artifact is authored. The core fires at every
moment, and no rule is gated by time independently of its surface — which is what gives planning
time and code time different rules without a second axis to carry.

Where the agent dispatches a subagent to apply a fix, it restates the gate in that subagent's prompt,
because a dispatched agent starts fresh and does not inherit the skill.

## Key decisions and rationale

**Two sequenced jobs rather than one.** Detection alone leaves the agent knowing it over-produced
with no safe way to act; gating alone never prevents the bloat. The cost is a larger constraint
count, paid for by the tiering above.

**The gate is symmetric.** Additions and deletions face the same re-check; neither carries a special
burden of justification. The asymmetric alternative — every deletion must be justified — was
considered and rejected: the evidence supports a gate, not a preservation prior, and a preservation
prior risks entrenching the bloat the skill exists to reduce. This is a locked default over an
irreducible tension, not a finding.

**Only two detection tests, plus tells that do not decide.** The co-evolution question for
duplication and the executed pruning test for rules are the only checks that survived adversarial
scrutiny. Per-surface tells were reinstated only where the corpus names a concrete signal — an
element whose sole callers are its own tests; code recreating what the codebase already has; a
comment restating the line below it; an abnormally long or hedge-dense passage. Tells that rested on
a failed claim, or that duplicated another surface's rule, stayed cut.

**The pruning test is executed, never predicted.** Deciding by imagining what would happen without a
rule is unaided model judgement — the exact move the skill forbids elsewhere. Actually remove the
candidate and observe. The harness behind this is untested and unpriced at affordable sample sizes,
and the skill says so.

**No magnitudes.** Of ninety-nine quantitative claims put to adversarial verifiers during the
research, forty-three needed correction or failed. Numbers are the part that decayed, and corrected
magnitudes are one model generation from being wrong again. The skill states direction only.

**Per-rule status tags, inline.** Each rule carries `grounded`, `precautionary` or `judgment`. Four
rules are grounded, and all four are statements about what the skill cannot do. Everything
prescriptive is weaker than that. This is an accurate picture of the field, and disclosing it makes
the four prohibitions more credible rather than less.

**The blocklist is inline, not in a reference file.** Its job is intercepting a citation reflex the
agent does not know it has — which only works before anyone opens a link.

**References carry justification, never behavior.** Anything that changes what the agent does is
inline. An agent that never follows a link is still correct, just less informed. Nothing measures
whether agents follow links, so the architecture is built to not depend on it.

## Behavior

Thirty-two rules, each with its status, tier, and reviewer test:
[audited-ruleset.json](audited-ruleset.json). Twenty-nine carry a full audit record — reviewer test,
evidence, and the auditor's note. The three reinstated on rationale alone — the test-only-callers
tell, the recreates-existing-code tell, and the verbosity-as-signal rule — carry that rationale in
place of evidence and an auditor's note. Their reviewer tests were written during review, not by the
audit.

**Always-on core (7)** — `G1` sequence simplification after a correctness check and re-validate ·
`G2` apply that check symmetrically to additions and deletions · `G3` only the correctness check may
block; a simplicity signal may prefer among passing candidates but never decide pass/fail ·
`G4` no evidenced analogue to that check exists outside code, and no substitute may be invented
*(grounded)* ·
`D1` the co-evolution question for duplication · `D2` the executed pruning test ·
`D3` outside those two tests there is no review-time check for over-engineering *(grounded,
diagnosis-only)*.

**Code (6)** — judge signals at the level of the change, never a single function in isolation, since
AI-written functions measure leaner than human ones while the decay shows at system level
*(diagnosis-only)* · unrequested configurability or dependencies · an element whose only callers are
its own tests · code recreating what the codebase already provides · a comment restating the line
below it · the banned-metrics rule *(grounded)*.

**Agent-facing docs (4)** — convert descriptive and overview passages into concrete directives or
delete them · merge or cut an overlapping rule rather than adding alongside it · keep tool
descriptions short · a rule missed only late in a session is not fixed by editing that passage
*(diagnosis-only)*.

**Specs (3)** — flag a provision whose only justification is an unstated future need · a tech spec
layered on a logic spec earns its place by committing to a choice the logic spec left open
*(diagnosis-only)* · these flag stated content, which a code surface cannot offer *(diagnosis-only)*.

**Human-facing docs (4)** — check for an existing indexed surface before adding a standing document ·
reduce a document restating an authoritative copy elsewhere to a pointer · a contract-, SLA- or
compliance-cited document is judged against that obligation, not traffic · never justify a cut on
the grounds that shorter is inherently better, and never on an unmaintained surface that merely
answers the question.

**Conversational output (2)** — excess length and hedge density are a signal about the model's own
confidence, so route flagged passages to verification or an explicit marker rather than trimming them
away *(diagnosis-only)* · cut a hedge that restates a point the reply already hedges, keeping the
instance whose removal would change what the reader does next; a caveat about a genuinely separate
risk is not a duplicate.

**Meta (6)** — the do-not-cite blocklist *(grounded)* · precedence · deletion rationale goes in the
commit message or PR description · the honest claim *(diagnosis-only)* · scope boundary and harness
assumption · subagent restatement.

Rules that cannot yield a VIOLATES/SATISFIES verdict are labelled diagnosis-not-enforcement rather
than cut, because several — notably `G4` and `D3` — are load-bearing precisely by stopping the gate
being misapplied where no gate exists.

### Scenarios

**An agent is asked to clean up a file.** Core applies. It notices two blocks that look similar and
asks the co-evolution question rather than deduplicating on textual similarity; the blocks would not
need to change together, so they stay. It removes a genuinely dead branch, then re-runs the test
suite and only then treats the change as done. The rationale goes in the commit message.

**An agent is editing a CLAUDE.md.** The agent-doc group activates. It finds a new rule overlapping
an existing one and merges rather than appending. It converts a philosophy paragraph into a directive
or deletes it. It does not shorten the file for its own sake — file length measured null.

**An agent is about to cite a length limit for rules files.** The inline blocklist fires before the
claim is made: the Cursor and Aider limits are unsourceable, and only Anthropic's target is real —
and cites no study.

**An agent is asked whether a rule in a skill file is still earning its place.** `D2` applies, and
it is the test most easily faked: the agent cannot decide by imagining what would happen without the
rule, because unaided model judgement is the move the skill forbids elsewhere. It removes the rule,
runs the cases the rule exists to govern, and observes. If nothing changes, the rule goes; the
rationale goes in the commit message. If the harness to do this isn't available, the honest outcome
is that the rule is unadjudicated — not that it passed.

**An agent dispatches a subagent to apply a refactor.** It restates the gate in the subagent's
prompt, because the subagent does not inherit the skill.

**An agent proposes deleting a config flag it thinks is unused, and the reviewer pushes back asking
it to justify the deletion.** The rationale gets written — `M3` requires it, in the commit message.
What it is not is a gate: `G2` holds the deletion to the same correctness re-check an addition would
face, not to a higher bar, and `G3` says the verdict rests on that check's result rather than on
whether "this is simpler" persuaded the reviewer.

## Scope and non-goals

**In scope**: spotting over-production and gating the fix across five surfaces — code, agent-facing
docs, specs, human-facing docs, and the agent's own conversational output; the do-not-cite blocklist;
per-rule evidence status.

**Out of scope**: prose mechanics — sentence length, headings, scannability — which belong to
`writing-scannable-prose`; the simplicity canon as theory; any numeric threshold; hooks or mechanical
enforcement; a kill condition; the argument that no simplicity constraint should be phrased to a
generating agent at all, which remains in the exploration document.

**Supersedes** the `applying-simplicity-principles` skill in `~/.claude/skills/`, which is
always-proactive, carries no evidence tags or blocklist, and contains advice this research
contradicts. Leaving both installed would create two competing simplicity skills.

**Precedence**: the user's CLAUDE.md outranks this skill; correctness skills — `test-driven-development`,
`verification-before-completion` — outrank it too.

**Success is measured** by whether a human can say *violates* or *satisfies* about a real draft using
these rules. No kill condition ships.

## Decisions Locked

**Artifact shape** — Both jobs, sequenced: detect over-production, then gate the fix · Symmetric gate
on additions and deletions · Ship only the two surviving detection tests and state plainly that other
surfaces are not checkable at review time · Written for the agent during generation.

**Surface scope** — All five surfaces carry rules · No gate analogue offered outside code; the gap is
stated · Conversational output included · Ship standalone; absorb `writing-scannable-prose` later.

**Encoding under weakness** — Per-rule status tags inline, full notes in the companion · Do-not-cite
blocklist inline in SKILL.md · Falsification one-liners inline, full text in the companion ·
Direction only, never magnitudes.

**Tension posture** — State a default and name the tension as its exception · The pruning test is
executed, not predicted · The argument against the skill's own existence is not restated in the skill ·
Rule admission is left ungoverned.

**Activation** — Narrow triggers, not always-on · Fires at planning time and code time with different
rules at each, satisfied by the surface tiering rather than a separate time axis: the surface in play
identifies the moment · Supersedes `applying-simplicity-principles`.

**Disclosure cost** — Degrade gracefully: behavior inline, justification in references · Dispatchers
restate the gate in subagent prompts · Written for Claude Code, stated explicitly · Tiered constraint
budget with a small always-on core.

**Precedence collisions** — The user's CLAUDE.md wins · Deletion rationale goes in the commit message
or PR body, never an inline comment · No special carve-out for doc comments; the general precedence
rule covers it · Correctness skills outrank this one.

**Kill condition** — The honest claim is a shifted starting point, not a better session · No kill
condition ships · Measured by reviewer judgment on real drafts.

**Rule-set adjudication** (added after the audit) — Tells are permitted alongside the two tests only
where the corpus names a concrete signal · Rules that cannot yield a verdict are labelled
diagnosis-not-enforcement rather than cut.

## Industry Insights

Drawn from this session's research pass — 471 findings across 28 facets, 99 quantitative claims
adversarially verified. Full audit in the
[provenance companion](../../explorations/2026-09-10-simplicity-provenance.md).

- **Conciseness without a correctness anchor costs solved problems.** Across four SWE-bench-Verified
  agents, prompting for minimal patches and purpose-trained minimisers both lost resolved instances;
  the one mode that beat baseline subordinated conciseness to a test-pass gate —
  [arXiv 2608.13292](https://arxiv.org/html/2608.13292)
- **A linter as dominant training reward teaches deletion, not improvement**; subordinating it to a
  unit-test gate beat a test-only reward on both axes —
  [arXiv 2605.30478](https://arxiv.org/html/2605.30478v1)
- **Prompt guidance shifts the intercept, not the slope.** Explicit quality guidance reduced starting
  verbosity and structural erosion but left the degradation rate unchanged —
  [arXiv 2603.24755](https://arxiv.org/abs/2603.24755)
- **Repository context files did not generally improve task success** while raising inference cost;
  concrete instructions were followed, descriptive repository overviews were not —
  [arXiv 2602.11988](https://arxiv.org/abs/2602.11988)
- **Instruction compliance falls as simultaneous constraints accumulate**, across three independent
  benchmarks — [FollowBench](https://arxiv.org/pdf/2310.20410),
  [IFScale](https://arxiv.org/abs/2507.11538), [Multi-IF](https://arxiv.org/pdf/2410.15553)
- **File length, instruction position, file architecture and even a directly conflicting instruction
  all measured null** for compliance in the only controlled factorial test; what moved was how much
  code the agent had already generated. Single-author preprint, single-turn harness, trivial marker
  instruction — read as best-available, not settled —
  [arXiv 2605.10039](https://arxiv.org/abs/2605.10039)
- **LLM judges rate padded code more favourably**, and adding critique layers to multi-agent
  architectures raised complexity with no correctness gain —
  [arXiv 2505.16222](https://arxiv.org/html/2505.16222v2),
  [arXiv 2606.00308](https://arxiv.org/html/2606.00308)
- **Duplication harm turns on synchronized co-evolution**, not textual similarity —
  [Kapser & Godfrey](https://plg.uwaterloo.ca/~migod/papers/2008/emse08-ClonePatterns.pdf)
- **The complexity metrics do not carry the weight placed on them.** McCabe's threshold was a stated
  personal judgement; the Maintainability Index constants have no logical justification; the most
  heavily refactored Windows 7 modules showed no attributable defect reduction —
  [McCabe 1976](http://literateprogramming.com/mccabe.pdf),
  [Heitlager et al.](https://www.ou.nl/documents/40554/349790/T66311_02.pdf),
  [Kim et al. TSE 2014](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/kim-tse-2014.pdf)
- **Anthropic's own guidance** targets minimal information that fully specifies behaviour, warns that
  bloated CLAUDE.md files cause instructions to be ignored, supplies the pruning test, and states that
  contradictory rules are resolved arbitrarily —
  [memory docs](https://code.claude.com/docs/en/memory),
  [best practices](https://code.claude.com/docs/en/best-practices)

## Deferred Ideas

- **Absorb `writing-scannable-prose`** into this skill, or merge the two, in a later pass. Until then
  the library holds a known-duplicate state on human-facing documentation.
- **A PostToolUse hook enforcing the gate.** The exploration's own top recommendation, and the only
  mechanism that reaches within-session drift and subagents. Untested as an intervention; deferred
  with its falsification test rather than built.
- **An executable ablation helper** for the pruning test, making "executed, not predicted" runnable
  rather than aspirational. The repo already ships stdlib-only Python in `bin/`.
- **Rule-admission governance** — the incident-required gate was considered and dropped, leaving
  nothing that limits the skill's own growth.

## Glossary

- **Gate** — a correctness check (typically the test suite) applied *after* a simplifying change and
  re-validated against it. The only thing permitted to block.
- **Test** — a check that yields a verdict. Two ship: the co-evolution question and the executed
  pruning test.
- **Tell** — a signal that prompts a closer look without deciding anything. Tells never block.
- **Co-evolution question** — do these two regions need to change together to stay correct? The
  duplication check that survived scrutiny; textual similarity is not the criterion.
- **Executed pruning test** — actually remove a candidate rule and observe, rather than imagining the
  counterfactual.
- **Status tags** — `grounded` (evidence directly supports it in a setting that transfers),
  `precautionary` (convergent evidence or reasoned inference, no direct result), `judgment` (a
  defensible design call, not evidenced).
- **Diagnosis-not-enforcement** — a rule that cannot yield a VIOLATES/SATISFIES verdict, labelled as
  such rather than cut.
- **Surface** — one of the five objects the skill governs: code, agent-facing docs, specs,
  human-facing docs, conversational output.
- **Do-not-cite blocklist** — claims that failed verification during the research and must never be
  repeated, kept inline to intercept the citation reflex.

## Status & amendments

**Status**: Draft — reviewed, corrections applied, awaiting user sign-off.

**Amendments**

1. **Plan-time and code-time activation now has behavior behind it.** The locked decision promised
   different rules at each moment and the design carried no time axis. Resolved by stating that the
   surface identifies the moment, rather than by adding one.
2. **The three duplication failures the audit found in the rule set itself are merged out, not just
   disclosed.** `HD4` no longer restates `HD2`'s system-of-record ground or `HD3`'s obligation
   override; `D4`'s evidence points at `M1`'s blocklist instead of repeating the McCabe and
   dead-code facts; `G3`'s reviewer test no longer restates `G1`'s re-run requirement inside the
   core. The skill's own co-evolution test, applied to the skill.
3. **`G4` is no longer labelled diagnosis-only.** Its test holds on authored guidance. It is stated
   once rather than per surface, which is a statement about cost per firing, not about whether it
   can yield a verdict.
4. **Every precautionary rule now carries a falsification line**, drawn from its own evidence. The
   two reinstated tells carry the honest version: no falsifying test exists in the corpus, and they
   were reinstated because the corpus names the signal, not because a result measured it.
5. **`S7`'s trailing precedence clause is gone.** `M2` states precedence once; a surface rule
   restating it is the shape this spec bars for the gate.
6. **`D4`'s rule text was the auditor's editing memo**, never a rule. Written out from the memo's
   instructions and the surviving reviewer test.
