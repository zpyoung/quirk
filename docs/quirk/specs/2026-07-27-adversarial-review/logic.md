# Logic Spec — `adversarial-review` skill

**Date:** 2026-07-27
**Status:** Approved — tech spec authored (`tech.md`); complexity-tier gate met on ≳3 source files,
subsystem boundary crossed, and multi-session scope

## Purpose

A skill that attacks a work product and returns findings a human or a calling skill can act on.
Invocable directly as `/quirk:adversarial-review [target]`, or composed into another skill as a
review step.

Adversarial review already exists in this repo, but only as an implementation detail of
`subagent-driven-development`: per-task, code-only, gated on `>150 changed lines OR contract
surface`, adjudicated by the task captain. There is no way to point it at a spec, a plan, or a
design decision, and no contract another skill can compose against. This skill is that thing;
SDD's asset becomes a delegation to it.

## Conceptual model

Three layers, each with a different trust basis.

**1. Ground-truth layer** — deterministic, no model involved. The profile's pre-pass runs and its
output is fed forward as fact. Code profiles run build, tests, typecheck, and lint. Prose profiles
resolve every named file, symbol, command, flag, link, and ticket against the repo, and scan for
required sections. Anything this layer reports is true by construction, and a pre-pass failure is
already a finding — a spec citing a function that does not exist needs no model to detect.

**2. Adversarial layer** — two model dispatches with *asymmetric context*. A **promote** stage
maximizes recall against a low bar. A **refute** stage runs with a fresh context and an explicit
kill mandate, receiving the artifact, the ground truth, and promote's **claims only — never its
reasoning**.

**3. Adjudication layer** — evidence gate, tie resolution, suppression accounting, and emission of
the verdict and manifest.

### The load-bearing invariant

**The reviewer never sees the author's reasoning — only the artifact and the criteria.**

Independence is structural, not rhetorical. Models exhibit measurable self-recognition bias: they
favor their own output and fail to correct errors in self-review that they catch when the same
content is framed as external. Prompt wording cannot repair this. Context asymmetry and a
different model family can.

This is why the existing prior art's instruction — *"Do NOT validate — only critique"* — is
replaced rather than inherited. That phrasing produces **inverse sycophancy**: a critic that
manufactures findings to appear useful because it has been told validation is not an acceptable
output.

## Data flow

1. **Resolve target.** Positional argument (a path or a git range); else uncommitted changes plus
   the branch diff against main; else the artifact already in context.
2. **Select profile.** Inferred from target shape; `--profile` overrides.
3. **Pre-pass.** The script runs the profile's deterministic commands and emits ground-truth
   output. Failures become findings directly.
4. **Select adversary.** Determine the author's model family, choose a different one, and gate the
   dispatch on `pi-watch --check <alias>`. On failure, walk the ladder; if fallback lands on the
   author's own family, stamp the review `independence: reduced`.

   The author's family resolves in this order: the explicit `author_family` input; else the family
   recorded in the manifest of the run that produced the artifact, when one exists; else the family
   of the invoking session. A wrong guess degrades to `independence: reduced` rather than to a
   silent same-family review.

   The accepted values are a closed set — `anthropic`, `openai`, `google`, `other` — and anything
   else is a usage error, exit 2. It is not treated as an unknown that degrades safely: the
   independence guarantee turns on one string comparison, so a name nothing matches would leave the
   author's own family in the candidate pool while stamping the result `full`. `other` is the
   explicit escape hatch for an author outside the known families, and it excludes nothing.
5. **Promote.** Dispatch with artifact, criteria, ground truth, and lens. Read-only tools. Recall
   maximized, low bar for raising a candidate.
6. **Refute.** Fresh dispatch with artifact, ground truth, and promote's claims only. Kill
   mandate: assume each finding is false and attempt to refute it.
7. **Evidence gate.** The script validates findings against the schema. A CRITICAL or HIGH finding
   lacking a reproduction has its **confidence capped at `LOW`; its severity does not move** —
   severity tracks consequence and confidence tracks likelihood, and proof speaks only to the
   second. A finding whose evidence cannot be re-resolved against source is dropped and counted.
8. **Tiebreak.** At `deep` depth only, contested findings go to a third model family.
9. **Emit.** Human summary, structured findings block, manifest.

### Depth dial

| Depth | Protocol | Auto-selected when |
|---|---|---|
| `quick` | Single pass with self-refute in the same dispatch | Small or mechanical changes; short documents |
| `standard` | Independent refute dispatch | Default |
| `deep` | Adds a cross-model tiebreak on contested findings | `>150` changed lines, or a contract/schema surface |

`--depth` overrides the auto-selection.

## Composition contract

```
in:   { target, profile?, lens?, depth?, model?, author_family?, criteria }
out:  { verdict, findings[], suppressed_count, manifest }
find: { id, severity, confidence, category, claim, evidence[], remediation, patch?, stage }
```

`verdict` is one of `PASS | NEEDS_FIXES | CRITICAL_ISSUES | NOT_REVIEWABLE`, determined
mechanically from the surviving findings:

| Verdict | Condition |
|---|---|
| `CRITICAL_ISSUES` | Any surviving CRITICAL finding, or a contested one awaiting tiebreak |
| `NEEDS_FIXES` | Any surviving HIGH or MEDIUM finding, or anything at all awaiting tiebreak, and no CRITICAL |
| `PASS` | Only LOW findings survive, or none, and nothing awaits tiebreak |
| `NOT_REVIEWABLE` | No adversary resolved at any ladder rung, **or** the pre-pass could not run and the artifact's core claims are unfalsifiable |

A contested finding awaiting tiebreak has no settled grade — the tiebreak may move it in either
direction — so it withholds `PASS` on presence rather than on severity. The gate that runs after the
tiebreak merge produces the final verdict.

`NOT_REVIEWABLE` is never a synonym for `PASS`. A calling skill that treats an unrecognized
verdict as passing is misusing the contract; the skill's own composition template says so
explicitly.

`manifest` carries the resolved model triple, thinking level, target SHA or artifact hash, depth,
lens, profile, pre-pass results, suppressed count, and the independence flag — enough to replay
the review and to distinguish a real regression from reviewer variance.

Composing skills invoke this skill and fill a template in `assets/`, matching the pattern SDD
already uses for its reviewer prompts.

## Behavior & scenarios

**A spec cites a function that does not exist.** The prose pre-pass fails reference resolution.
The finding is emitted with zero model involvement and zero false-positive risk.

**The promote stage invents a plausible bug.** Refute runs with a fresh context and a kill
mandate, cannot re-resolve the evidence against source, and kills it. The finding never reaches
the user; the suppressed count increments.

**Every finding gets suppressed.** The report shows a near-total kill rate, which signals that
the promote stage was fabricating and the run itself should not be trusted. Making the kill rate
visible is what turns suppression into an integrity signal rather than a silent filter.

**A high-consequence finding cannot be proven.** It survives as CRITICAL severity with LOW
confidence rather than being downgraded into invisibility, because severity tracks consequence and
confidence tracks likelihood on independent axes.

**`pi` is not authed.** Preflight fails, the ladder is walked, and Claude reviews Claude-authored
work. The review still returns, but stamped `independence: reduced`, so a `PASS` is not read as
stronger than it is.

**The artifact's core claim is unfalsifiable.** "This claim cannot be evaluated as written" is
emitted as a top finding, and review proceeds over whatever remains falsifiable.

## Scope & non-goals

- **Not** a cooperative reviewer. `requesting-code-review` stays as-is; the two postures are
  genuinely different and collapsing them would lose a real distinction.
- **Never** applies patches or edits files. Patches are proposed for mechanical findings only and
  applied by the caller, under the size and scope guards SDD already defines.
- **Never** interactive. Blocking questions would break unattended composition.
- No cross-session finding persistence.
- Does not replace human review.

## Decisions Locked

**Posture & mechanical verification**
- Refute-or-Promote two-stage protocol; the refute stage has an explicit kill mandate and a fresh context.
- Deterministic pre-pass first; the reviewer may then run its own read-only commands.
- Reproduction required for CRITICAL/HIGH; reasoned argument permitted below.
- Findings failing verification are dropped, with a suppressed count reported.

**Evidence across artifact types**
- Typed profiles over one shared engine; auto-detected, caller-overridable.
- Evidence is an anchored quote, or — for absence claims — a re-runnable search proving the absence.
- Prose pre-pass resolves every named reference against the repo *and* scans required-section coverage.
- Unfalsifiable core claims are reported as a top finding; review continues on what remains.

**Output format**
- Machine-parseable findings block plus a short human summary.
- Severity (consequence) and confidence (likelihood) are independent axes.
- Verdict vocabulary: `PASS | NEEDS_FIXES | CRITICAL_ISSUES | NOT_REVIEWABLE`.
- Bounded patches for mechanical findings; report-only for judgment calls.

**Invocation surface**
- Optional positional target with a smart default.
- Open mandate by default, narrowable with `--lens`.
- Composition via a documented input contract plus `assets/` prompt templates.
- Three depths auto-selected from risk, overridable.

**Reviewer supply & adjudication**
- Default to a model family different from the artifact's author; `--model` overrides.
- Ladder-fallback on unavailability, recording the actual reviewer and flagging same-family fallback.
- Record the resolved model triple and inputs so a review can be replayed.
- Refute wins ties; `deep` depth escalates to a cross-model tiebreak.

**Integration**
- This skill is the single source; **SDD's Step 8 review loop delegates to it, one invocation per
  lens** (amended 2026-07-27 — see Amendments 1).
- v1 ships all four profiles: `code-diff`, `spec-design`, `plan`, `prose-claim`.
- The contract carries `dismissed[]` in and stable finding IDs out, so SDD's cross-round
  carry-forward survives delegation (added 2026-07-27 — see Amendments 1).

## Industry Insights

- **Inverse sycophancy.** Critics instructed to only critique manufacture findings to appear
  useful; preference-model training rewards agreement over accuracy, and the inverse instruction
  inverts the pathology rather than curing it.
  [Sycophancy in AI](https://tokita.online/sycophancy-in-ai/) ·
  [Science: sycophantic AI decreases prosocial intentions](https://www.science.org/doi/10.1126/science.aec8352)
- **Refute-or-Promote.** Stage-gated multi-agent review chains a recall-maximizing promote stage to
  an independent refute stage with a kill mandate, validated against real CVEs and stdlib bugs.
  [arXiv 2604.19049](https://arxiv.org/pdf/2604.19049)
- **Self-recognition bias is structural.** Generator and verifier must be separate agents with
  asymmetric contexts; cross-family review outperforms same-family, and prompt engineering does not
  repair the bias. [Adversarial Code Review](https://www.augmentcode.com/guides/adversarial-code-review)
- **Noise is the dominant failure mode.** 70–90% of AI review findings are ignored as false
  positives; curl permanently closed its bug bounty and HackerOne paused the Internet Bug Bounty in
  March 2026 under AI-generated submission volume. Teams disable gates over cry-wolf.
  [AI code review overload](https://www.codeant.ai/blogs/prevent-ai-code-review-overload) ·
  [ICLR 2026 response](https://blog.iclr.cc/2025/11/19/iclr-2026-response-to-llm-generated-papers-and-reviews/)
- **Isolation without context is the top false-positive source.** Reviewing a diff without
  repository structure, type information, or conventions flags benign changes as risky — the
  motivation for the ground-truth pre-pass.
  [The false positive problem](https://www.cubic.dev/blog/the-false-positive-problem-why-most-ai-code-reviewers-fail-and-how-cubic-solved-it)
- **Evidence requirements are the calibration lever.** Rejecting findings whose claims cannot be
  re-resolved from source, and requiring reproduction steps, converts hallucinations into
  falsifiable claims — up to 96% reduction reported.
  [Reproduction steps in AI code review](https://www.codeant.ai/blogs/reproduction-steps-ai-code-review) ·
  [Reducing hallucination in production](https://www.blockchain-council.org/ai/reducing-ai-hallucination-in-production-rag-guardrails-evaluation-hitl/)
- **Model choice is a precision/recall dial.** Claude Opus 4.6 measured zero false positives while
  missing 80% of issues; GPT-5.3-codex-spark ran 75% false positives. Complementary layering beats
  picking a winner.
  [AI code review false positive rates](https://docs.bswen.com/blog/2026-03-05-ai-code-review-false-positives/)
- **Severity inflation.** 20–30% of CVSS 9+ findings sit on non-exposed, low-sensitivity assets.
  Aviation and medical safety review deliberately separate consequence from likelihood — the basis
  for the two-axis severity model.
  [Inflated CVE severity scores](https://jfrog.com/blog/where-cve-severity-scores-go-wrong/)
- **Negation insensitivity.** LLM critics are systematically weak at evaluating "MUST NOT"
  constraints, arguing for deterministic gates on negative rules rather than model judgment.
- **Review agents are socially engineerable.** Framing effects embedded in the reviewed material
  can bias evaluation — relevant because the artifact under review is untrusted input.
  [SEVRA-BENCH](https://arxiv.org/pdf/2606.13757)

## Deferred Ideas

- Finding lifecycle across sessions and branches, with expiry or ticket linkage.
- Multi-run consensus — run the promote stage N times and keep only recurring findings.
- Panel of N distinct lenses with membership and weighting policy.
- Right-of-reply: author rebuttal before findings are finalized.
- An explicit noise budget or skip threshold, and who sets it (skill, calling skill, or user).
- Absorbing `requesting-code-review` as a cooperative mode of this skill.
- A `quirk:code-reviewer` agent definition. The type is referenced throughout SDD and
  `requesting-code-review` but this plugin ships no `agents/` directory, so the reference is
  currently dangling. This skill deliberately does not depend on it.

## Glossary

- **Promote stage** — first adversarial pass; maximizes recall against a low bar.
- **Refute stage** — second pass with fresh context and a kill mandate; assumes each finding false.
- **Pre-pass** — deterministic, model-free verification run before any adversarial dispatch.
- **Absence claim** — a finding asserting something is missing, evidenced by a re-runnable search.
- **Independence flag** — marks a review whose reviewer shares the author's model family.
- **Suppressed count** — findings killed by the refute stage or evidence gate; a visible integrity signal.
- **Profile** — per-artifact-type bundle of attack surface, evidence rules, and pre-pass commands.
- **Manifest** — replay record: model triple, thinking, target hash, depth, lens, profile, results.
- **Criteria** — what the artifact is supposed to achieve, supplied by the caller and pasted
  verbatim rather than referenced by path. For a code diff this is the task contract and acceptance
  criteria; for a spec or plan, the goal it claims to serve; for a prose claim, the assertion under
  test. Criteria are the only author-supplied context the reviewer receives — the author's
  *reasoning* is withheld, per the load-bearing invariant.
- **Lens** — an optional narrowing of the open mandate to a named concern or hypothesis.

## Status & amendments

**Status:** Approved — 2026-07-27. Tech spec authored. Amended twice on 2026-07-27 after
`52f5865` rewrote SDD's control plane.

**Amendments:**

**1 — 2026-07-27 — Integration decision retargeted.** Upstream commit `52f5865`
("refactor(sdd)!: rewrite the control plane around branch-level adversarial review") deleted
`assets/codex-adversarial-prompt.md`, `assets/pi-codex-adversarial-prompt.md`, both captain
prompts, all four `scripts/sdd-*`, and the `>150 lines OR contract surface` gate. Every referent
of the original Integration decision ceased to exist, so it could not be implemented as written.

*Resolution (user, 2026-07-27):* SDD's **Step 8 review loop** delegates to this skill — one
invocation per lens (correctness/logic, spec compliance, security/failure modes), replacing the
direct `pi-watch` dispatch of `assets/reviewer-prompt.md`. SDD retains ownership of rounds,
adjudication, stable-ID assignment, fixer dispatch, and the five-round cap; this skill owns the
review itself and returns structured findings instead of a text block SDD must parse.

*Contract consequences:* delegation requires two additions not in the original design —
`dismissed[]` as an input (SDD carries dismissed findings forward so a re-report is matched to its
prior ruling) and stable, caller-supplied-or-preserved finding IDs as an output (SDD's IDs persist
across rounds). Both are recorded in Decisions Locked → Integration above.

*Risk accepted:* this option was flagged as the highest-risk of four, because it modifies a
control plane rewritten one commit earlier and not yet proven in use. The user selected it over
narrowing scope to non-code artifacts.

**2 — 2026-07-27 — Reviewer `bash` grant retained over a contrary security finding.** The same
commit added an explicit constraint to `skills/subagent-driven-development/SKILL.md`: *"Reviewers
get read-only tools. `pi` has no sandbox — a reviewer with `bash` or `write` has full filesystem
access."* That contradicts this spec's locked decision that the reviewer may run its own read-only
commands, on the `pi-watch` dispatch path specifically. A Claude `Task` reviewer is bounded by
permission mode; a `pi` reviewer is not.

*Resolution (user, 2026-07-27):* keep read-only `bash` on **both** dispatch paths. The locked
decision stands unchanged.

*Risk accepted, stated explicitly:* on the `pi` path this grants the reviewer unsandboxed
filesystem access for the duration of the review. The mitigation is prompt-level only — the stage
templates instruct read-only use — and prompt-level constraints are not enforcement. The reviewed
artifact is untrusted input (see Industry Insights → review agents are socially engineerable), so
a crafted artifact that induces a reviewer to run a destructive command is not blocked by any
mechanism in this design. This entry exists so the trade is traceable rather than implicit.
