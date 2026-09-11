> 🧭 EXPLORATION — not a spec. No locked decisions; nothing here is build-ready.

# Exploring: simplicity in code, documents, and agent output

**Date**: 2026-09-10 · **Emphasis**: research-heavy blended · **Intensity**: 0.5 (Exploratory) · **Involvement**: medium

## Framing

What does simplicity actually mean in code, in documents, and in what an AI agent produces — and can an agent be *instructed* into it?

Scoped to feed a **reusable quirk skill**, so every finding is judged the same way the scannable-prose exploration judged its own: could a reviewer look at a real draft and say *violates* or *satisfies*? Advice that only sounds wise does not survive that test. Documents were scoped wide — human-facing docs, agent-facing docs (CLAUDE.md, skill files, tool descriptions), and specs. Reddit was treated as **first-class evidence** rather than colour, which raised its bar rather than lowering it: consensus had to be independently observed across threads, and the dissent had to be hunted as hard as the agreement.

Three findings shape everything below.

**The detection layer is the weakest part of the field, not the strongest.** Of twelve quantitative claims that failed adversarial verification in the first pass, five came from the single facet asking *how do you detect over-engineering* — the one question a simplicity skill most needs answered. Cyclomatic thresholds, dead-code rates, cohesion metrics and complexity formulas were misattributed to sources that do not contain them.

**Over-engineering has no review-time definition.** The one definition practitioners converge on — complexity that anticipates a requirement which never materialises — is only decidable in retrospect. The identical code is good engineering if the requirement arrives. Every review-time test in this document is a proxy for a fact that has not happened yet.

**Telling an agent to be simple works, briefly, and then stops.** Explicit quality guidance cuts *starting* verbosity by up to a third but leaves the *rate* of degradation unchanged. And in the only controlled test anyone has run on instruction files, none of the variables the field argues about — length, position, file architecture, even a directly contradictory rule — had a detectable effect on compliance, while how much code the agent had already written did. That study is a single-author preprint measuring a trivial marker in a single-turn harness, so read it as the best available evidence rather than a settled result; the caveats are in the Findings and they are severe.

**On this document's own length.** It runs long for a document about simplicity, and it names that rather than pretending otherwise. Its own directions supply the test: content earns its place by tracing to a decision a reader has to make. The provenance audit — which numbers survived being attacked — was split into a [companion](2026-09-10-simplicity-provenance.md) precisely because a reader of one would not open the other. What remains is the evidence, the option space, and the conflicts between the options — and a reader who wants only the options and their conflicts can read the Idea landscape and Tensions and skip the rest.

## What was explored

Sixteen parallel research facets produced 327 validated findings; twelve gap-driven depth questions across two rounds added 144 more, for **471 findings from 28 facets** — 116 peer-reviewed, 112 preprint, 60 official-doc, 41 industry-report, 79 practitioner-post, 28 forum-consensus, 25 anecdote, 10 book-or-talk.

| Facet | Question put to it |
|---|---|
| **Code canon** | Hickey, Ousterhout, Brooks, Parnas, Gabriel — actual claims, and where they conflict |
| **Folk wisdom** ⚔️ | Attempt to *falsify* KISS/YAGNI/DRY and the complexity metrics |
| **Detection** | What lets a reviewer say *violates* rather than *I don't like this* |
| **When simple lost** ⚔️ | The strongest available case against simplicity as a governing value |
| **Agent-facing docs** | Context rot, instruction-count decay, tool-description cost |
| **Spec bloat** | Over-specification, ADR minimalism, where a spec should stop |
| **Docs as a system** | Volume vs. usage, decay rates, deletion as practice |
| **LLM verbosity** | Length bias in reward models and in evaluation |
| **AI code complexity** | Measured comparisons of AI- vs human-written code |
| **Agent failure modes** | The specific shapes agent over-engineering takes |
| **Constraint prompting** | Does telling a model to be simple actually work? |
| **Self-critique** | Can an agent catch its own over-engineering? |
| **Harness practice** | Primary-source wording harness authors actually ship |
| **Reddit: devs** 🔴 | r/ExperiencedDevs, r/programming, r/softwarearchitecture |
| **Reddit: AI coding** 🔴 | r/ClaudeAI, r/cursor, r/ChatGPTCoding, r/LocalLLaMA |
| **Reddit: docs** 🔴 | r/technicalwriting and adjacent — doc bloat |

**Depth rounds.** Round 1 chased seven gaps, including the contradiction between "AI code is simpler" and "AI code decays", the provenance of the 24-line method threshold, whether simplicity constraints must be mechanically verifiable, and whether *Lost in the Middle* explains long-CLAUDE.md failures. Round 2 chased five more, including whether a mechanical in-loop gate beats prompt instructions, and whether a viral CLAUDE.md statistic was real.

**Verification.** 99 quantitative claims were put to independent adversarial verifiers instructed to refute them, under three lenses — *traceability* (does a primary source contain this number), *construct* (does it measure what the claim says), *currency* (is it still true and does it generalise). **235 checks; 56 confirmed, 43 corrected or failed.**

Read the markers precisely, because they do not cover everything. ✓ means a claim went through a verifier and survived it; ⚠️ means a verifier corrected it and the corrected form is what appears here; ✗ means it failed and is shown only as a cautionary example. A claim carrying **no marker** was not adversarially verified — it is cited to its source and its evidence type is stated, but nobody attacked it. Numbers explicitly marked **(unverified)** were additionally barred from carrying an argument. The 12 depth-round facets sit in a fourth category: those agents read primary sources directly, and in one case re-ran an author's published replication package, but that is provenance rather than adversarial verification — and the challenge pass later showed one such study carries severe limits. Full audit, including every correction: the [provenance companion](2026-09-10-simplicity-provenance.md).

**Ideation.** Six technique lenses — radical simplification, the avoided idea, first principles, assumption reversal, contrarian inversion, overlooked value — produced 30 directions; a quality gate rejected 5. A second round closed three coverage gaps the first missed (agent conversational output, specs and design docs, human-facing documentation) and deepened the two best-evidenced clusters, producing 25 more; a stricter gate rejected 11, and 2 more were lost when their gate agents exhausted a schema retry cap — those 2 were never judged, and are neither in the landscape nor counted as rejected. The survivors consolidated to **15 directions across seven clusters**.

**Challenge.** Every direction was steelmanned, attacked, and given a falsification test. **All fifteen came back weakened** — see [Challenge notes](#challenge-notes).

- _Steered:_ at the idea gate the user chose to close the agent-output, spec and human-doc gaps, to deepen the drift and judging clusters together, and to consolidate to roughly twelve directions with tensions preserved.
- _Out of scope:_ prose mechanics — emphasis budgets, tables, sentence-level compression — already covered by `writing-scannable-prose`, whose own out-of-scope list named agent-facing docs and which this exploration therefore takes up.

## Findings: what the research actually supports

### Theme: the measurement layer is hollow

Every complexity metric a simplicity rule might lean on turns out to rest on judgement, curve-fitting, or a sample too small to carry it.

- **McCabe's threshold of 10 was a personal judgement call.** His own 1976 paper says so. The only correlation evidence in it comes from 24 subroutines, non-randomly selected and subjectively ranked. — [McCabe 1976](http://literateprogramming.com/mccabe.pdf)
- **The Maintainability Index constants have "no logical justification."** Heitlager, Kuipers & Visser say it plainly: a curve-fit, not a derived model. — [Heitlager et al. 2007](https://www.ou.nl/documents/40554/349790/T66311_02.pdf)
- **Halstead's validations were "poorly designed"** and most of the theory's claims are not natural laws — NIST's own technical review, citing Hamer & Frewin. — [NIST TN 1990](https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.1990.pdf)
- **The popular "cyclomatic complexity is just SLOC" critique is itself overstated.** Landman et al., on 17.6M Java methods and 6.3M C functions, measured R² = 0.40 (Java) and 0.44 (C) — far below the 0.87–0.94 small studies had reported — and concluded the correlation is *too weak* to call CC redundant. The debunk needs debunking. — [Landman et al. 2016](https://aserebre.win.tue.nl/Landman2015-ccsloc-jsep2015-preprint.pdf)
- **More complexity did not mean more defects.** Basili & Perricone found error density per line *decreased* as cyclomatic complexity rose. — [via Shepperd 1988](https://www.cs.du.edu/~snarayan/sada/teaching/COMP3705/lecture/p1/cycl-1.pdf)
- **Refactoring's defect payoff did not show up at Microsoft.** The most heavily refactored Windows 7 modules reduced post-release defects 7% *less* than the rest of the codebase; the authors say reduction cannot be credited to refactoring alone. — [Kim, Zimmermann & Nagappan, TSE 2014](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/kim-tse-2014.pdf)
- **The "developers spend 58% of their time comprehending code" figure** comes from 79 developers at two Chinese outsourcing firms, Windows only, over two weeks — and "comprehension" was operationalised as time in certain applications, not understanding. The competing 70% figure draws over 85% of its data from three PhD students. — [Xia et al. 2018](https://baolingfeng.github.io/papers/tsecomprehension.pdf)
- **The famous code-comprehension fMRI study used 17 undergraduates** and snippets of at most 18 lines, tested no complexity metric, and its authors state it cannot be generalised to real programming. — [Siegmund et al. 2014](https://www.cs.cmu.edu/~ckaestne/pdf/icse14_fmri.pdf)

### Theme: detection is the weakest link, and that is the finding

The facet asking *how do you tell over-engineering when you see it* produced five of the twelve claims that failed adversarial verification — by far the worst rate in the study. Cyclomatic tiers, dead-code rates, cohesion thresholds and complexity formulas were all traced to sources that do not contain them.

- **Over-engineering's only clean definition is retrospective.** Practitioner consensus converges on: complexity counts as over-engineering only if it anticipates a requirement that never materialises. The identical code is good engineering if the requirement arrives. Nothing available at review time decides this.
- **Two operational tests survived scrutiny.** For duplication, Kapser & Godfrey's deciding question is whether the copies require *synchronised co-evolution* — clones tied to a shared underlying requirement are harmful, deliberately isolated ones frequently beneficial. For rules, Claude Code's documented pruning test: *would removing this cause Claude to make mistakes?* If no, delete it. — [Kapser & Godfrey](https://doi.org/10.1007/s10664-008-9076-6), [Claude Code best practices](https://code.claude.com/docs/en/best-practices)
- **Speculative generality has exactly one mechanical tell:** the only users of the code are its own tests. Everything else in the smell catalogue requires human judgement.
- **Even the duplication evidence does not settle.** Juergens et al. found ~52% of clone groups contained an inconsistency and developers confirmed faults in about half of the unintentional ones; Kapser & Godfrey found 33–71% of clones *beneficial* depending on sample and threshold. Kapser's own retrospective concedes the field still does not know which clones matter.

### Theme: whether AI over-engineers depends entirely on the unit of analysis

This is the study's central contradiction, and it dissolves rather than resolving.

- **AI-written functions are simpler than human ones.** In a 507k-function comparison, human Python functions averaged 12.72 NLOC and 3.97 cyclomatic complexity against 4.47–6.89 NLOC and 1.84–2.47 for three LLMs. But this measures isolated single-function generation from a docstring — not files, PRs, or projects.
- **AI-written systems decay.** God-class centralisation, false modularity, and rising duplication appear consistently in project-level studies. The headline ρ=0.94 "volume-quality inverse law", though, rests on N=20 non-independent points from one framework running one model — reproducible from its own data (ρ=0.935) but collapsing when the 20 points are reduced to 5 scenario means.
- **The real-world causal studies split the same way.** 806 Cursor-adopting repos: +30.3% static-analysis warnings, +41.6% complexity — falling to ~9% once codebase-size dynamics are controlled, with *no* significant duplication effect under three separate DiD estimators. 151 Java repos under agentic adoption: architectural smell counts flat (+1.1%, n.s.) while LOC grew 12.8%. A 19,816-file matched study found AI code had *lower* duplication than human code (14.29% vs 27.57%).
- **Counts versus density is doing most of the disagreement.** The 151-repo authors state the methodological lesson directly: when the treatment also changes system size, density-normalised metrics mislead — and raw counts and densities tell opposite stories.
- **GitClear's telemetry is the most-cited and least-controlled.** Block duplication rising 40.3 → 73.0 per million changed lines (2023 → 2026) is correlational, and its own appendix discloses that pre-2024 backfill sampled only the largest 1,000 commits per repo — which the report says biases *toward* finding more duplication.

### Theme: models over-produce because training and evaluation both pay for it

- **Reward models prefer length — moderately.** ⚠️ The claim entered this study as a *strong* correlation and was corrected: r = 0.451 between response length and reward score in the ODIN paper's baseline model is moderate, and the descriptor failed on both lenses. ✓ The paired result held — the method drives that correlation to −0.03 by splitting quality and length heads. — [ODIN](https://arxiv.org/abs/2402.07319)
- **Verbosity alone swings a leaderboard.** On AlpacaEval, `gpt4_1106_preview`'s win rate moved from 22.9% to 64.3% purely on whether it was told to answer concisely or in maximum detail — collapsing to 41.9–51.6% under length control. ⚠️ Demonstrated on *one* model instance, not across models. Length-controlled scoring raises Spearman correlation with Chatbot Arena from 0.94 to 0.98 — ⚠️ at bootstrap p≈0.07, and "highest of any benchmark" means the two the authors compared against in April 2024. — [Dubois et al.](https://arxiv.org/abs/2404.04475)
- **Judges prefer longer where humans prefer shorter.** In the bins of HH-RLHF where humans chose the shorter response, GPT-3.5's agreement with those human labels ran roughly 19–30%, against 54–100% where humans chose the longer one. ⚠️ The widely-quoted single "72%" pooled figure is not in the paper — it is a pooling of per-bin chart values that leans on bins as small as n=2. — [Saito et al.](https://arxiv.org/abs/2310.10076)
- **The bias looks amplified rather than inherited**, though the cleanest number for this failed. ✗ The "chosen responses average only 7.5% longer" claim is **unsourceable**; the traceable figure is that ~58% of preference pairs in the Dahoas-rm-static split of HH-RLHF have the chosen response longer. Preference models correlate with bias features at r = +0.36 where humans sit at −0.12 **(unverified)**.
- **Length is among the constraints models follow worst — but not the worst for everyone.** ⚠️ On CoDI-Eval, GPT-4 scores 73.8% on length against 86.2% keyword and 93.6% toxicity-avoidance — but the claim that length is the worst category *for every model* failed: GPT-4 and GPT-4-turbo score lower on multi-aspect constraints (70.2%/65.2%), and for most weaker open models toxicity avoidance is worse. ✓ Separately confirmed: on LIFEBench, 23 of 26 models score below 60/100 on exact length-matching. — [LIFEBench](https://arxiv.org/abs/2505.16234)

### Theme: what agent instructions actually buy

- **Repository context files do not generally improve task success.** Across SWE-bench tasks and real developer-committed AGENTS.md/CLAUDE.md files: no general success improvement, and over 20% higher inference cost. The useful distinction is *inside* the file — concrete instructions were well followed; descriptive repository overviews, "popular and recommended by model providers", were not. — [arXiv 2602.11988](https://arxiv.org/abs/2602.11988)
- **Compliance collapses as constraints accumulate.** FollowBench: GPT-4's Hard Satisfaction Rate falls 84.7% → 61.9% from one constraint to five. IFScale: the best of 20 frontier models manages 68% at 500 simultaneous instructions, and the *perfect-response* rate reaches exactly zero by 80 instructions for every model tested. Multi-IF: o1-preview drops 0.877 → 0.707 by the third turn.
- **Negation gets worse as models get bigger — for zero-shot and instruction-tuned models.** An inverse scaling law on negated prompts across pretrained zero-shot LMs (OPT, GPT-3, 125M–175B) and instruction-tuned ones (InstructGPT, T0). ⚠️ The claim does *not* extend to few-shot prompting or to negation-fine-tuned models as originally stated — those conditions were tested at only one or three sizes, so no scaling curve exists for them. Also 2022-era models on commonsense tasks, not code. The countervailing "phrase it positively" advice is offered by its own proponents as a heuristic, never as a study. — [arXiv 2209.12711](https://arxiv.org/abs/2209.12711)
- **Personas do nothing measurable.** 162 personas × 2,410 questions × 4 model families: no accuracy improvement over no-persona control, and automatically picking the "best" persona per question performs no better than random. — [arXiv 2311.10054](https://arxiv.org/abs/2311.10054)
- **But three abstract words moved output hard.** Adding "Follow YAGNI principles" to a coding prompt cut average output from 108 lines to 10.4; adding "and one-liner solutions" took it to 6.9 — beating a purpose-built prompting framework's 8.25. The author flags the benchmark as flawed. So: abstract wording shifted the *length* metric hard; whether it produced *better* code is unmeasured. This cuts directly against "only mechanically verifiable rules work."
- **The vendor line-limits mostly do not exist.** The research pass surfaced four — Anthropic under 200 lines, Aider 150–200, Cursor under 500, Cline none — and adversarial verification found that **two of them are unsourceable**: no such guidance appears on the cited Aider page or in the cited Cursor rules repository. What survives is Anthropic's under-200-line target (real, official, and citing no study) and Cline's unnumbered "rules consume context tokens; avoid lengthy explanations". A folk consensus about instruction length was, on inspection, one vendor's uncited number plus two inventions. ✗ *two claims failed verification* — [Claude Code memory docs](https://code.claude.com/docs/en/memory), [Cline rules](https://docs.cline.bot/customization/cline-rules)
- **Anthropic's own docs concede two things worth more than a line count.** Contradictory rules are resolved *arbitrarily*, with no precedence rule. And CLAUDE.md is injected as a **user message after the system prompt** — not as the system prompt, which is where most reasoning about its authority implicitly places it. *(Official documentation, quoted directly; non-quantitative, so never sent to a verifier.)*

### Theme: drift may beat structure — the study's most actionable result, and its most fragile

- **The one controlled factorial test of CLAUDE.md structure found every structural variable null.** File size (25–500 lines), instruction position (5 positions), single- versus multi-file architecture, and the presence of a directly conflicting instruction — none produced a detectable compliance effect. — [arXiv 2605.10039](https://arxiv.org/abs/2605.10039)
- **What did have an effect was how much code had already been written.** Each additional function the agent generated carried ~5.6% lower odds of complying with a standing instruction (OR = 0.944), dwarfing every file-structure variable.
- **The decay is front-loaded, not gradual.** Among runs with any non-compliance, the median first miss was at the **4th generated function**, and compliance after that first miss ran at 55% — intermittent, not collapsed.
- **"Lost in the middle" does not explain it.** A five-position sweep found no shape component at all (quadratic p=0.94, linear p=0.41). The authors offer a mechanism: QA retrieval has a query to anchor recency, a standing instruction has no such cue. The widely-shared "Claude skims the middle of the file" report changed length and content simultaneously and isolated neither.
- **The paper's own recommendation is in-session enforcement** — hooks that re-surface the rule mid-run — not better rule text. Goal-reminder injection at fixed turns measurably reduced drift in a separate agent study.

**Read the paragraph above with its limits attached, because they are severe.** This is a *single-author, non-peer-reviewed preprint*. It ran in single-turn `--print` mode — a harness that structurally excludes the compaction and re-injection dynamics real sessions have, which means it demonstrates drift in the *absence* of any mechanism rather than showing a mechanism is needed once one exists. Its target instruction was a trivially detectable marker comment, and its authors state that transfer of the absolute compliance rate to other instruction classes is an open question — a semantic rule like *do not add unnecessary abstraction* has no grep detector and may behave nothing like a marker. Claude Code's own documented reload-on-compact fires on **token volume, not generated-function count**, so it may not even reach the early window this finding identifies. And the corpus contains a direct counter-example: a simulated-agent study where strong upfront framing alone held near-perfect adherence past 100k tokens with no re-injection at all.

The honest statement is therefore narrower than "drift beats structure." It is: **in the one controlled test anyone has run, the file-shaped variables everyone argues about did nothing, and something about generation volume did something.** Whether that survives contact with real multi-turn sessions and non-trivial rules is unmeasured, and it is the single most consequential open question in this document.

### Theme: simplicity pressure without a correctness anchor destroys function

Three independent evidence levels — a preprint, an RL training study, and a Reddit report — converge on the same shape. This is the strongest constraint the research places on any simplicity instruction.

- **Pursuing concise patches costs solved problems.** Across four SWE-bench-Verified agents: a prompting-only "produce a minimal patch" instruction costs 30–39 resolved instances; purpose-trained minimal-patch generators cost 49–78; naive commit-untangling costs 160–217.
- **The one mode that won subordinated conciseness to a test-pass gate.** Oracle-Guided Refinement returns the refined patch only when the patched program still passes, else falls back: **on SWE-agent**, 375/500 resolved versus 357 for unconditional refinement and 333 for baseline. The load-bearing check was *correctness*, not size. — [arXiv 2608.13292](https://arxiv.org/html/2608.13292)
- **A linter as the dominant reward makes models delete rather than improve.** In RL training, a Ruff-based reward dropped pass@1 from 0.273 to 0.252; subordinated to a unit-test gate, the combined reward beat test-only on both correctness and quality.
- **Prompt guidance has a one-time effect, not a rate effect.** SlopCodeBench (36 problems, 196 checkpoints, 15 agents): explicit quality guidance cuts *starting* verbosity and structural erosion by up to a third but does not change the *rate* of degradation across subsequent checkpoints.
- **Practitioners hit the same wall.** On the most-shared anti-over-engineering prompt thread, a commenter reports that appending "minimum viable functionality" caused Claude to start stripping working features.

### Theme: the AI reviewer is biased toward the thing it is reviewing for

If a simplicity check is itself an LLM judgement, it runs against the grain of measured judge behaviour.

- **Inflating apparent complexity makes judges rate code better.** Inserting no-op dummy functions raised judge accuracy-ratings on correct code from 79.67% to 89.33% (n=8) and *dropped* them on incorrect code from 63.50% to 46.65%. A single insertion produced no directional effect — the bias needs length to become directional. — [arXiv 2505.16222](https://arxiv.org/html/2505.16222v2)
- **Adding LLM critique layers adds complexity and buys no correctness.** Six multi-agent architectures on HumanEval: more review/critique layers produced a 50–130% increase in SLOC, cyclomatic complexity and Halstead volume with no correctness gain. The best pass@1 architectures (84–92%) sit in the lean cluster — the one containing a mechanical test-execution debugger.
- **Intrinsic self-correction does not work.** LLMs largely cannot self-correct reasoning without external feedback and sometimes get worse; GPT-4 self-critiquing its own plans produces many false positives and drops solve rate. A simple *external* verifier that merely re-prompts captures nearly all achievable benefit. Several influential "self-correction works" papers leaked ground truth into the correction step.
- **Judges also carry position and self-preference bias.** Swapping answer order alone let Vicuna-13B "beat" ChatGPT in 66 of 80 queries with ChatGPT as judge. Models rate their own generations higher, an effect that tracks how well they recognise their own text. ✗ A further claim — that GPT-4's self-preference is *driven by* low perplexity rather than self-identity — failed verification on both lenses: the perplexity result was measured on six open-source judges, and GPT-4's self-preference was a separate experiment in the same paper.
- **Checklists help, modestly.** Replacing direct judge scoring with instruction-specific yes/no checklists raised exact judge-human agreement from 46.4% to 52.2%.

### Theme: the case against simplicity is stronger than its advocates admit

- **Simplicity has a body count.** The Therac-25 deliberately omitted the hardware interlocks its predecessor had, relying on software alone. Tesler's Law holds that complexity is conserved — it moves between user, application developer and platform, and is never removed.
- **The accessibility floor is real and mostly unmet:** 95.9% of the top million home pages carry a detectable WCAG 2 failure, up from 94.8% and reversing six years of improvement.
- **"Keep it simple" gets weaponised.** Practitioners explicitly warn it is deployed against directory structure, module boundaries and unit tests — not only against speculative abstraction. A separate practitioner in the same thread refuses to let "avoid over-engineering" collapse into tolerance for sloppy code, treating them as unrelated failure modes.
- **Technical writers push back on brevity as a value.** Cuts get framed as docs being treated as a cost centre; contracts and SLAs impose a completeness floor that compression cannot cross.
- **The famous monolith story is contested by its own community.** Adrian Cockcroft disputes the "microservices to monolith" framing of Prime Video's post: the change consolidated a chatty serverless design in one internal service, not an architecture-wide retreat.
- **Even the originators hedge.** Fowler concedes YAGNI sometimes backfires expensively; Dan McKinley concedes "choose boring technology" cannot be applied absolutely without becoming absurd.

### Theme: what survived verification, and what did not

**Ninety-nine headline quantitative claims were put to independent adversarial verifiers. Fifty-six survived intact. Forty-three needed correction or failed outright.** A 43% correction rate on the numbers a careful research pass chose to headline is the single most useful thing this document can tell anyone building on it — and the corrections were not nitpicks. The dominant failure was *construct*, not arithmetic: a real number measuring something narrower than the claim it was attached to.

### Theme: claims that could not be sourced

- **"Karpathy's 4 CLAUDE.md rules cut Claude's mistake rate from 41% to 11%" is not Karpathy's.** His actual January 2026 post is qualitative and contains no percentages. The statistic originates with a different individual's long-form post claiming 50 tasks across 30 codebases over six weeks — no task list, no raw data, no blinding, no adjudication criteria, with "mistake" self-counted. At least one aggregator attributes it to Karpathy's own thread.
- **DORA's 1,525% documentation multiplier does not measure brevity.** Its eight-metric construct covers reliability, findability, understandability and completeness — no metric names length or conciseness. The figure is a ±1 SD split on self-reported survey data from the 2022 instrument; DORA confirms it does not release raw data.
- **Could not be sourced at all, or traced only to vendor self-report:** the "~20%, up to 66% of code is unused" figure (absent from the article that supposedly carries it; traceable only to a vendor blog's own ballpark), the four-tier cyclomatic risk scale attributed to McCabe (his paper gives a single limit of 10), and the "67.3% of AI PRs fail first review" statistic (LinearB's actual metric is 30-day merge rate, 32.7% vs 84.4%).
- **KISS's attribution to Kelly Johnson is itself only loosely sourced** — Wikipedia hedges it as unverified.
- **Two of four vendor line-limits do not exist** (above). The pattern is worth naming on its own: a research agent asked for "what harness authors say about length" produced four confident, quotable, plausible rules, and half were invented. This document's own method is the reason you are reading the correction instead of the invention.
- **Several real numbers measured something narrower than claimed.** The "7 out of 10 documents have rotten links" figure is about *scholarly citation rot* in journal bibliographies, not software documentation. The 23.0% stale-reference rate in AI config files is described by its own authors as "a feasibility signal rather than a precise prevalence." A doc-duplication cost figure in euros is a CMS vendor's hypothetical worked example, not a measurement. A study showing users strongly prefer a 113-word answer to a 466-word one is self-published by the founder of the product being evaluated.

## Idea landscape

**Fifteen directions across seven clusters. No winner is declared and nothing is ranked.**

Two ideation rounds generated 55 directions; quality gates rejected 16 for cliché, restatement, machinery smuggling, or overreading a source. Round 2 was told to close three coverage gaps and to deepen the two best-evidenced clusters — and its most valuable output was **contesting round 1's own premises**, which is what a deepening pass is for. Where that happened it is recorded as a tension rather than smoothed over.

Every direction separates its **insight** (what the evidence supports) from its **machinery** (apparatus invented on top). Machinery is flagged untested wherever it is untested. The scannable-prose exploration in this series had 13 of 16 directions come back weakened for conflating exactly those two things; the split is enforced here from the start rather than discovered at the challenge pass.

### Drift and re-injection

**1 · Text is a one-time dial; drift needs an out-of-band mechanism — but which one is contested**
Prose buys a one-time shift in starting compliance, not a change in the decay rate. Every text-shaped lever measured null; within-session drift was the only variable that moved. The corpus's recommended countermeasure is out-of-band re-injection — but a design must name which drift hypothesis it is betting on rather than presenting re-injection as settled.
*Why it might work:* the factorial nulls plus the per-function odds ratio, and SlopCodeBench's intercept-not-slope finding. *Complicated by round 2:* Claude Code's real reload-on-compact fires on **token volume, not generated-function count**, so it plausibly misses the early window this targets; and a simulated-agent study found strong upfront framing alone held near-perfect adherence for 100k+ tokens with no re-injection at all.
*Machinery:* fixed-cadence re-delivery every ~3 generated functions — **untested**, never built.
*Reviewer test:* violates if a design relies on a one-time read with nothing operating after the first few generations, **or** if it presents periodic re-injection as *the* validated fix without naming the competing hypotheses.

**2 · Design for the post-violation state — and detect it structurally, never by self-report**
Compliance after a first miss is 55%, not a cliff to zero: a degraded-but-live state a static document has no way to represent.
*Why it might work:* the same paper supplies both the post-miss figure and the acknowledgment breakdown. *Contested by round 2:* the paper's own reanalysis attributes the apparent late-session recovery to **task-mix composition** rather than per-session self-healing — so the 55% may be population blending. The two readings cannot be separated without per-session tracking the corpus does not have.
*What both readings agree on, and it is the usable part:* the detector cannot be the model's own word. Only 9.7% of runs ever verbally acknowledge the rule; 28% of acknowledging functions violate it anyway; 63% of non-acknowledging functions comply.
*Reviewer test:* violates if the "a miss occurred" trigger is model self-report; satisfies if it is a structural check against the generated artifact.

### Distrust of LLM judgement

**3 · Anchor the simplicity verdict to a mechanical signal — and where none exists, log a falsifiable bet rather than invent one**
Never let an LLM's opinion arbitrate whether something is too complex; route accept/reject through a non-LLM signal and use LLM review only to propose. Where the question is genuinely retrospective, don't manufacture an in-the-moment heuristic — fall back to the orphan-caller proxy where it applies, else log a timestamped prediction to revisit.
*Why it might work:* three independent convergences — dummy-function judge bias, critique layers adding 50–130% complexity for no correctness gain, and self-correction failing without external ground truth. *Costed honestly:* the checklist mitigation buys 46.4% → 52.2% agreement at a token price that scales with checklist length.
*Machinery:* the falsifiable-bet log — **untested**.

**4 · Execute the removal test; don't ask an LLM to predict it**
The corpus's most-cited operational test — *would removing this cause Claude to make mistakes?* — is currently answered by asking a model to imagine the counterfactual: the exact unaided judgement the rest of this cluster forbids. Strip the rule, run a fixed task set with and without it, use the measured delta.
*Why it might work:* an external verifier that merely re-prompts captures nearly all the achievable benefit of self-correction — execution beats introspection in precisely this failure family.
*Machinery:* the ablation harness — **untested**, and unpriced at the frequency a skill would run it.
*Reviewer test:* violates if retention is justified only by a predicted counterfactual; satisfies if backed by an executed comparison, even two informal sessions run with and without.

**5 · Review duplication at the altitude where it shows — co-evolution, not per-function aesthetics**
Per-function AI output already measures leaner than human code; system-level decay is where the problem accumulates, and a single diff structurally cannot show it. Ask whether two regions require synchronised co-evolution.
*Why it might work:* the 507k-function comparison versus the real-world causal studies, resolved by unit of analysis; Kapser & Godfrey's test is the duplication heuristic that survived as operational rather than aesthetic.
*Machinery:* none — a reviewer question against real code.

### Correctness gating

**6 · Gate simplification and deletion behind a correctness check applied afterward — never freestanding, never blocking**
Any step that shrinks, simplifies or deletes must be sequenced after a correctness check and re-validated against it. Used alone or punitively it does not merely fail to help; it destroys function.
*Why it might work:* the best-evidenced finding in the study. RECAP's unconditional minimal-patch prompting cost 30–39 resolved instances and trained minimisers cost 49–78, while the test-gated mode beat baseline on SWE-agent (375/500 vs 357 vs 333); the linter-dominant reward dropped pass@1 0.273 → 0.252.
*Machinery:* none — uses the existing test suite.

**7 · Unwarranted simplification is itself a failure mode**
Treat deleting interlocks, collapsing branches and shrinking below requirement as a hazard to watch as hard as over-engineering. Every deletion is the move requiring justification.
*Why it might work:* the model's cheapest route to satisfying a simplicity signal is to delete rather than improve; Therac-25 is the case where simplification *was* the defect.
*Reviewer test:* violates if a branch, check or safety condition is removed with no note on why the path is now unreachable and no evidence the suite still covers what it covered.

### Agent-document discipline

**8 · Gate rules at both ends: an incident to add, a checkable removal test to keep, no invented taxonomy**
A rule may not be added prospectively — only after a specific observed failure it would have prevented — and every retained rule must survive being deleted and re-justified. Rules should be binary questions against a concrete instance, never taxonomy categories that read as tone.
*Why it might work:* descriptive taxonomy content measured unhelpful while concrete instructions were followed; the field is additive by default and does not self-correct — this repo's own library runs 46,547 words across 24 files, and the most-upvoted "minimalistic CLAUDE.md" post drew a top comment — which its author conceded — saying about half its content could be cut by applying its own principles to itself.

**9 · Never phrase a simplicity constraint to the generating agent — select among candidates instead**
Not positively, not negatively, not as YAGNI. Generate multiple candidates under a complexity-neutral prompt and let a separate mechanical selector choose.
*Why it might work:* negation degrades with scale, and instruction-following collapses with constraint count — one more instruction taxes the compliance of everything else rather than winning free. *Cuts against it:* the blog result where three abstract words cut output 108 → 10.4 lines.
*Machinery:* best-of-N plus a mechanical selector — **untested for this application**.

**10 · Cap the live constraint count — the lever is count, not polarity**
Actively merge, cut and rank as rules accumulate.
*Why it might work:* the count effect is large and reproduced across three benchmarks; "avoid negative phrasing" rests on 2022-era non-code commonsense evidence its own proponents call a heuristic. *Honest limit:* no threshold is licensed — the benchmarks show monotonic decay, never a safe number.

**11 · Concrete-instruction density, not length or position, is the real lever**
The reduction target is the ratio of checkable instructions to descriptive prose.
*Why it might work:* file size, position, architecture and even a conflicting instruction all measured null, while concrete instructions were followed and repository overviews were not — at +20% inference cost.
*Reviewer test:* violates if an edit mainly cuts length and reorders sections while leaving overview passages intact; satisfies if it converts or removes descriptive prose *regardless of resulting length*.

### Spec discipline

**12 · Content must trace to a named present consumer — and a second document must contain a real decision**
Audit for provisioning language attached to no current consumer, ticket or test. The same audit applies one level up: a tech spec atop a logic spec must contain at least one mechanism-level decision made among named alternatives, not a restatement with headers and a diagram. An unearned second document is itself the failure, not a symptom of it.
*Why it might work:* the retrospective-definition problem makes code-level review unusable at write time, so the check moves to the layer where "for the future" actually gets stated. This repo's own rubric already gates tech specs behind *only when warranted*.

**13 · Surface ambiguity as a question before building**
Practitioner testimony reframes "the model over-engineers" as "the request was ambiguous and the model invented scope to fill the gap."
*Why it might work:* piling anti-bloat constraints onto an ambiguous request adds to the very count that causes collapse; the one documented rule backfire is a downstream patch failing in a new way.

### Human-document lifecycle

**14 · Check lifecycle decisions against external reality, not writing quality or usage stats**
Before a new standing document exists, require evidence its question isn't already answerable from a searchable surface. In the other direction, carve out contract-, SLA- and compliance-referenced documents before any usage-based pruning runs: there, "nobody reads this" is not evidence it can be cut.
*Why it might work:* the practitioner thread on mandated incident reporting duplicating ServiceNow, Jira and Confluence; and the technical writer who pushes back on brevity-as-cost-cutting and names the contractual completeness floor.
*Machinery:* the tagged exemption list — **untested**.

### Conversational output

**15 · Excess length in a reply is diagnostic, not just noise**
Treat an abnormally long or hedge-dense passage as a signal about the model's own confidence — route it to verification or an explicit uncertainty marker rather than uniform shortening that erases the signal along with the padding. Cap unprompted stacked caveats at one, and only if it changes what the reader does next. Narration around a tool call earns its place only by adding something the visible output does not already show.
*Why it might work:* verbosity compensation — models still generate compressible padding under a brevity constraint, correlated with their own uncertainty; and a length-only reward model reproduces most of full RLHF's downstream gain, meaning a real share of what reads as "helpful" is explained by length alone.
*Machinery:* the outlier-length check and hedge budget — both **untested**. The narration clause is this landscape's own extrapolation; nothing in the 471-finding corpus tests preamble redundancy directly.

## Tensions & trade-offs

Eight conflicts between surviving directions. Seven are irreducible. Where a genuine distinction exists it is named; where the conflict cannot be resolved from this evidence, that is said plainly rather than papered over with a synthesis neither side's text licenses.

**The pruning test is the thing it forbids** — *4 (execute the ablation)* vs. *8 (removal test) and 3 (mechanical anchor)*
The corpus's most-cited pruning question — *would removing this cause a mistake?* — is, as directions 8 and 3 use it, answered by unaided LLM prediction. That is exactly the judgement shape direction 4 says must be replaced by an executed before/after comparison. The landscape's most-relied-upon operational test and its most-repeated prohibition are the same move seen from two sides. **Irreducible:** 8 and 3 as written permit the predictive form, 4 says that form is invalid, and nothing in the corpus supplies a threshold for when prediction is good enough.

**The landscape fails its own admission rule** — *8 (incident-required to add a rule)* vs. *the machinery of 1, 2, 3, 4, 9 and 15*
Direction 8 says a rule may only be added after a specific observed failure it would have prevented. Applied reflexively, that standard disqualifies nearly every piece of apparatus this landscape proposes — the hook, the state flag, the bet log, the ablation harness, the best-of-N selector, the hedge budget. None cites an observed failure in a specific deployed document; all are justified from general literature, which is the prospective shape direction 8 forbids. The obvious escape — *8 governs accretion inside a deployed document, these are pre-deployment design decisions* — does not hold, because 8's motivating insight is aimed precisely at authorship practice. **Irreducible, and self-implicating.**

**Say nothing about simplicity, versus everything else here** — *9 (never phrase a constraint)* vs. *1, 8, 10, 11, 12, 13*
Direction 9 categorically forbids phrasing a simplicity constraint to the generating agent — positively, negatively, or as a comment rule — while most of the landscape consists of writing, capping, densifying, or re-injecting exactly that content. This is not a preference clash but **a live evidentiary conflict inside the corpus**: 9 leans on constraint-count collapse and negation scaling, the content directions lean on concrete instructions being followed and on three abstract words moving output by an order of magnitude. **Irreducible** — 9's claim is unconditional, so it does not resolve by scope.

**Block the speculative abstraction, or log it** — *12 (trace to a named consumer)* vs. *3 (log a falsifiable bet)*
Same object, opposite verdicts. 12 treats forward-looking provisioning for an unnamed future consumer as the thing to catch and block now; 3 treats the same bet as legitimate provided it is logged and revisited. **Irreducible** — both are evidence-backed responses to the retrospective-definition problem, and the corpus contains no rule for when *defer and check* beats *block outright*.

**Deletion is the danger, or deletion is the lever** — *7* vs. *6, 8 and 4*
Direction 7 makes every deletion the move requiring justification. The correctness gate, the removal test and the ablation all treat deletion as the mechanism that actually works once checked. Both read the same RECAP and linter-reward evidence — one emphasising the destructive failure mode of unconditional deletion, the other the corrective success mode of the gated kind. **Irreducible:** the corpus does not adjudicate which framing should be a skill's default posture, and the choice of default is most of what a skill *is*.

**Two readings of the same 55%** — inside *direction 2*
Whether a within-session recovery phenomenon exists at all is contested by the same paper that reports it: the headline figure reads as partial self-healing, the authors' own reanalysis attributes it to task-mix composition. **Irreducible** without per-session tracking the corpus does not have. A mechanism designed around a phenomenon that may be an artifact of population blending is a real risk, and no direction here can retire it.

**Does text need help at all** — *1 (a mechanism is required)* vs. the simulated-agent counter-evidence
The factorial and SlopCodeBench results support *text only shifts the starting point, so a mechanism is required*. A simulated-agent study supports *sufficiently strong upfront framing needs no mechanism at all*, holding near-perfect adherence past 100k tokens. **Irreducible as stated** — different tasks, settings and models, neither validated on a coding agent, and the corpus does not license picking a winner. This is the tension most likely to decide whether anything built from this document is worth building.

**The one that resolves** — *3 (mechanical anchor as cross-cutting default)* vs. *15 (conversational output)*
Direction 3's prescription is built entirely from code and architecture evidence: SLOC, judge-accuracy on code, critique-layer bloat. Applying it by default to conversational output risks exactly the re-skinning direction 15 warns against, since whether code-complexity findings transfer to prose is one of the corpus's open questions. **Resolves by scope** — 3 governs code- and duplication-shaped judgements; 15 carves conversational output out and demands chat-native grounding rather than a relabelled code rubric.

## Challenge notes

Every direction was steelmanned, attacked, and given a falsification test by an independent challenger with access to the corpus and instructed to check whether each insight's cited evidence actually says what it claims.

**All fifteen came back weakened. None survived.** The scannable-prose exploration in this series had 13 of 16 weakened; this one went 15 for 15, and almost always for the same two reasons: **evidence drawn from a setting that does not transfer** (chat and QA benchmarks, 2022-era models, or single-framework studies applied to coding agents), and **a statement scoped wider than the finding under it**. Challengers were explicitly told not to downgrade a direction for honestly-labelled untested machinery — so none of these verdicts is about disclosed invention. They are about claims outrunning sources.

**The falsification tests are the most portable thing in this document.** Each names what to measure and which result kills the direction. Several are runnable in an afternoon.

- **1 · Text is a one-time dial** — *Counter:* the anchor study ran in single-turn `--print` mode, so it shows drift where no mechanism could fire, not that a mechanism is needed once one does. *Falsify:* run matched multi-turn sessions, arm A upfront-only framing, arm B the same rule restated with stated consequences of violation. If B holds compliance flat past the function count where A decays, drift is a framing-strength artifact fixable inside the document.
- **2 · Post-violation state** — *Counter:* one unreplicated single-author preprint measuring a trivially grep-detectable marker comment. *Falsify:* rerun with a semantic rule that has no detector — *do not introduce unnecessary abstraction* — in a real multi-turn harness with human ground truth. If self-report predicts compliance as well as a structural check there, the direction's usable half dies.
- **3 · Anchor the verdict mechanically** — *Counter:* every backing finding is about code being *scored* by an LLM, yet the statement covers code, docs and agent output uniformly. *Falsify:* label real code (not dummy-padded) as over-engineered or not, then run a bare LLM verdict against the prescribed pipeline. If the bare LLM matches human labels as well, the prohibition is unearned on realistic inputs.
- **4 · Execute the removal test** — *Counter:* the self-correction literature validates an external *ground-truth* verifier; an ablation harness re-running the same model is not obviously that. *Falsify:* run the harness twice at the N a skill could actually afford — 3–5 runs per arm. If the two runs disagree on keep-or-cut for the same rule, it is noise wearing the costume of measurement.
- **5 · Review at the co-evolution altitude** — *Counter:* diagnosis/prescription mismatch. The one causal AI-specific study finds decay in *complexity* and a **robust null on duplication** across three estimators, yet the prescription is a duplication heuristic — from a pre-LLM typology whose own originator later said the field still does not know which clones are harmful. *Falsify:* flag clone groups two ways in AI-authored repos, then track which flagging predicts inconsistent change downstream.
- **6 · Gate simplification behind correctness** — *Counter:* generalised from narrow automated patch-refinement pipelines; the winning result covers one of four tested configurations. *Falsify:* run gated versus ungated deletion outside SWE-bench bug-fixing — on agentic refactoring or long-horizon tasks. If the gate stops paying there, it is a property of patch refinement, not of simplification.
- **7 · Unwarranted simplification is a failure mode** — *Counter:* the evidence supports a *symmetric* gate on additions and deletions alike; the direction converts it into an asymmetric preservation prior that could entrench exactly the bloat the rest of the document is about. *Falsify:* sample merged diffs containing deletions, record whether a justification was present and whether a regression later traces to the deleted line. If justified and unjustified deletions regress at the same rate, the asymmetry buys nothing.
- **8 · Rules gated at both ends** — *Counter:* its one in-domain anchor is unverified, and an earlier draft of this document attached a "~600 lines" figure to the minimalistic-CLAUDE.md anecdote that appears nowhere in the source — the number was this document's own invention and has been cut. *Falsify:* classify an existing rule set into incident-gated-binary versus prospective-taxonomic, then run an agent on tasks designed to trigger each rule's target mistake.
- **9 · Never phrase the constraint** — *Counter:* the ban covers positive phrasing too, but the evidence reaches only the negative half and the constraint-count question — and the corpus's one relevant result has three abstract positive words cutting output by an order of magnitude. *Falsify:* one positive simplicity line versus the full best-of-N pipeline on the same benchmark. If the one line matches the pipeline on both size and correctness, the apparatus is unearned.
- **10 · Cap the constraint count** — *Counter:* the entire base is general instruction-following benchmarks — compositional English commands and a synthetic keyword task — while the corpus's own directly-relevant coding study found file size null. *Falsify:* hold file length constant and vary only the number of distinct live constraints across real multi-turn coding sessions.
- **11 · Concrete-instruction density** — *Counter:* the concrete-versus-descriptive split is real and directly quoted in the source — *"instructions in the context files are well followed by coding agents, repository overviews, although popular and recommended by model providers, are not helpful"* — but it is one workshop-track paper's observation about repository overviews, not a controlled manipulation of instruction density, and the direction treats it as though the lever had been isolated. *(The challenger initially recorded this as a misread of the source; that accusation was checked against the corpus and withdrawn — it had searched a truncated index that omitted the depth-round entry.)* *Falsify:* hold length and position constant and vary only the concrete-to-descriptive ratio. If density nulls out the way size and position did, the last surviving text-shaped lever goes with them.
- **12 · Trace content to a named consumer** — *Counter:* oversells the machinery by citing the clone co-evolution test as a validated model when the corpus's own reading of that test is far weaker. *Falsify:* strip every flagged unnamed-consumer abstraction from a batch of real specs, then count how many come back later as urgent unplanned retrofits.
- **13 · Surface ambiguity first** — *Counter:* the headline comparative — request-side clarification never hits the ceiling output-side patching hits — is **not evidenced anywhere in the corpus**; it chains two facts that do not meet. *Falsify:* run matched ambiguous coding requests, build-immediately versus clarify-first, and score output size and correctness.
- **14 · Check lifecycle against external reality** — *Counter:* **its strongest evidence cuts against its own prescription.** The knowledge-base-versus-Slack-search finding is reported in the corpus as a pathology, not as proof that ambient chat history is a satisfying surface that should block a new document. *Falsify:* take a document a team agrees was worth writing and check whether its raw facts were technically already scattered across old tickets and threads. If they were — the common case — the creation-side check would have blocked a document that deserved to exist.
- **15 · Length as a diagnostic** — *Counter:* the cited chat literature mostly establishes that length is *rewarded*, which is a different claim from length *signalling the model's own uncertainty*; the direction leans on the thinner story as though it were the better-attested one. *Falsify:* score real replies for relative length and hedge density against known ground truth about what turned out wrong. If flagged passages are no likelier to be incorrect, verbosity is noise here, not signal.

## Open questions & gaps

Nine questions the research could not answer. Several are load-bearing for anything built from this document — and the first one is the whole ballgame.

**No study has ever manipulated constraint *form* as the sole variable.** Nobody has A/B-tested "Follow YAGNI principles" against "no new files, diff under 200 lines" while holding everything else constant. The evidence points both ways and neither way is clean: concrete instructions beat descriptive overviews inside context files, but three abstract words cut output from 108 lines to 10.4. The single most practical question a simplicity skill must answer has no experiment behind it.

**No A/B of positive versus negative phrasing of the same constraint.** The inverse-scaling result on negation is real but comes from 2022-era models on commonsense tasks. Nobody has taken one style rule, written it as "always X" and "never not-X", and measured. The advice to phrase positively is offered by its own proponents as a heuristic.

**Hook-based mid-session re-injection is untested.** The drift study's own top recommendation — re-surface the rule mid-run via PreToolUse/PostToolUse hooks — has never been run as a controlled intervention on a coding agent. The three studies that do test reminder-style interventions with measured effects are in other domains.

**No mechanical bloat gate has been tested inside an agent loop.** The infrastructure exists and is documented. What has been measured is a *correctness* gate (which worked) and a *linter-dominant reward* (which backfired). A cyclomatic-threshold or diff-size cap subordinated to a test-pass gate — the configuration the evidence actually points toward — has never been run.

**Nobody has isolated CLAUDE.md line count while holding content constant.** The one factorial study varied 25–500 lines and found nothing, but its authors flag that the range sits below where long-context effects appear, that it used a single-turn harness with no compaction, and that its target instruction was a trivially detectable marker rather than a prohibition or a multi-step rule.

**No longitudinal study asks whether speculative abstractions were ever needed.** The retrospective definition of over-engineering could in principle be settled by following abstractions built "for the future" and checking whether the future used them. Nobody has. There is also no cost comparison between maintaining a wrong abstraction and re-introducing duplication — Metz's claim has no numerical backing in either direction.

**No experiment decomposes a large method and measures the same code before and after.** The 24-line threshold study's decomposition finding is an inference across different methods, not a before/after on any actual one. Worse, when the same dataset's change and bug counts are expressed as density rather than raw totals, the size-maintenance relationship *reverses* for most projects — the paper's own summary says the direction depends entirely on which dependent variable is chosen.

**No judge study isolates simplicity as its own bias axis.** The illusory-complexity-bias result concerns judges *scoring* code, not agents *generating* it under a simplicity instruction, and no controlled experiment asks a judge to reward simplicity and measures whether it can.

**Coverage the research could not reach.** No published system prompts from closed-source coding agents — only reverse-engineering and inference. No independent reproduction of the "context rot" industry report. Several primary sources were paywalled or rate-limited: Karpathy's and Mnimiy's original posts both returned HTTP 402, the Wayback Machine was rate-limited, and Veracode's full report, Hatton (1997), and Gatrell & Counsell (2015) could not be opened. Two research agents exhausted their WebSearch budget mid-run and finished on a different search backend, so coverage is uneven across facets in ways this document cannot fully characterise.

### What the idea landscape itself does not reach

The consolidation pass was asked what no surviving direction addresses. Its answers:

- **No drift mechanism is validated on a coding agent.** Fixed-cadence re-injection, upfront-framing strength, and attention-decay architecture are three competing hypotheses borrowed from adjacent settings. None has been run here.
- **The correctness gate — the single best-validated intervention in the corpus — has no evidenced analogue for documents, specs, or human-facing docs.** Three directions state this limit in their own text rather than papering over it. A skill covering all three surfaces would be extrapolating on two of them.
- **No threshold is licensed for the constraint-count cap.** The benchmarks show monotonic decay with count; none supplies a safe number for this setting.
- **The ablation harness is unpriced.** Nothing establishes its practical scale or statistical power at the frequency a skill would actually run it.
- **Human-facing documentation rests on two source directions**, both from the gap-filling round — thin next to the coverage available for code and agent-facing docs.
- **The narration clause in the conversational-output direction is this landscape's own extrapolation.** No claim in the 471-finding corpus tests preamble or recap redundancy directly.
- **Nothing resolves conflicts when several directions fire on the same draft.** The tensions above are stated, not arbitrated, and no direction supplies precedence.

## Sources

The research corpus holds **471 findings drawn from 312 distinct sources**. Listed here are the ones carrying weight in this document; the rest sit behind claims marked **(unverified)**, which were not allowed to carry an argument. Verification status for every headline number is in the [provenance companion](2026-09-10-simplicity-provenance.md).

**The canon**
- Hickey, *Simple Made Easy* — [transcript](https://github.com/matthiasn/talk-transcripts/blob/master/Hickey_Rich/SimpleMadeEasy.md)
- Ousterhout vs. Martin, the full recorded exchange — [aposd-vs-clean-code](https://github.com/johnousterhout/aposd-vs-clean-code)
- Gabriel, *The Rise of Worse is Better* — [jwz.org](https://www.jwz.org/doc/worse-is-better.html)
- Dijkstra, EWD447, *On the Role of Scientific Thought* — [UT Austin archive](https://www.cs.utexas.edu/~EWD/transcriptions/EWD04xx/EWD447.html)

**Metrics and their critiques**
- McCabe 1976, the founding paper (threshold of 10 as stated judgement) — [literateprogramming.com](http://literateprogramming.com/mccabe.pdf)
- Shepperd 1988, *A critique of cyclomatic complexity as a software metric* — [PDF](https://www.cs.du.edu/~snarayan/sada/teaching/COMP3705/lecture/p1/cycl-1.pdf)
- Landman, Serebrenik, Bouwers & Vinju 2016, 17.6M methods, R²=0.40 — [preprint](https://aserebre.win.tue.nl/Landman2015-ccsloc-jsep2015-preprint.pdf)
- Heitlager, Kuipers & Visser 2007, Maintainability Index constants — [PDF](https://www.ou.nl/documents/40554/349790/T66311_02.pdf)
- NIST TN 1990, Halstead review — [nvlpubs](https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.1990.pdf)
- Kim, Zimmermann & Nagappan, TSE 2014, Windows 7 refactoring field study — [Microsoft Research](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/kim-tse-2014.pdf)
- Xia et al. 2018, the 58% comprehension figure and its sample — [PDF](https://baolingfeng.github.io/papers/tsecomprehension.pdf)
- Siegmund et al. 2014, fMRI, n=17 — [CMU](https://www.cs.cmu.edu/~ckaestne/pdf/icse14_fmri.pdf)
- Kapser & Godfrey 2008, clone typology and the co-evolution test — [Waterloo](https://plg.uwaterloo.ca/~migod/papers/2008/emse08-ClonePatterns.pdf)

**Instruction-following and agent documents**
- McMillan 2026, the factorial CLAUDE.md study — drift, and every structural null — [arXiv 2605.10039](https://arxiv.org/abs/2605.10039)
- Repository context files across SWE-bench — [arXiv 2602.11988](https://arxiv.org/abs/2602.11988)
- FollowBench, multi-level constraints — [arXiv 2310.20410](https://arxiv.org/pdf/2310.20410)
- IFScale, 500 simultaneous instructions — [arXiv 2507.11538](https://arxiv.org/abs/2507.11538)
- ComplexBench — [arXiv 2407.03978](https://arxiv.org/html/2407.03978)
- Multi-IF, turn-wise decay — [arXiv 2410.15553](https://arxiv.org/pdf/2410.15553)
- Jang et al., inverse scaling on negated prompts — [arXiv 2209.12711](https://arxiv.org/abs/2209.12711)
- Zheng et al., persona prompting null — [arXiv 2311.10054](https://arxiv.org/abs/2311.10054)
- Liu et al., *Lost in the Middle* — [arXiv 2307.03172](https://arxiv.org/html/2307.03172)
- RULER, effective context length — [arXiv 2404.06654](https://arxiv.org/html/2404.06654)

**Verbosity, judging, and self-critique**
- ODIN, length-reward disentanglement (r=0.451 → −0.03) — [arXiv 2402.07319](https://arxiv.org/abs/2402.07319)
- Dubois et al., Length-Controlled AlpacaEval — [arXiv 2404.04475](https://arxiv.org/abs/2404.04475)
- Saito et al., verbosity bias in preference labeling — [arXiv 2310.10076](https://arxiv.org/abs/2310.10076)
- Illusory complexity bias in LLM code judges — [arXiv 2505.16222](https://arxiv.org/html/2505.16222v2)
- LIFEBench, explicit length instructions — [arXiv 2505.16234](https://arxiv.org/abs/2505.16234)

**Simplification under a correctness gate**
- RECAP, patch conciseness across four SWE-bench agents — [arXiv 2608.13292](https://arxiv.org/html/2608.13292)
- Linter-reward RL degradation — [arXiv 2605.30478](https://arxiv.org/html/2605.30478v1)
- SlopCodeBench, guidance shifts the intercept not the slope — [arXiv 2603.24755](https://arxiv.org/abs/2603.24755)
- Multi-agent architectures, critique layers and complexity — [arXiv 2606.00308](https://arxiv.org/html/2606.00308)

**AI code in the wild**
- 806 Cursor-adopting repositories, difference-in-differences — [arXiv 2511.04427](https://arxiv.org/html/2511.04427v3)
- 151 Java repositories under agentic adoption — [arXiv 2606.13298](https://arxiv.org/abs/2606.13298)
- 19,816 matched AI/human files — [arXiv 2603.27130](https://arxiv.org/abs/2603.27130)
- *AI-Generated Smells*, the ρ=0.94 study (N=20) — [arXiv 2605.02741](https://arxiv.org/html/2605.02741v1)

**Primary-source vendor guidance**
- Claude Code memory docs — the under-200-line target, arbitrary conflict resolution, CLAUDE.md as user message — [code.claude.com](https://code.claude.com/docs/en/memory)
- Claude Code best practices — the pruning test — [code.claude.com](https://code.claude.com/docs/en/best-practices)
- Anthropic, *Effective context engineering for AI agents* — [anthropic.com](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- AGENTS.md — [agents.md](https://agents.md/) · Cline rules — [docs.cline.bot](https://docs.cline.bot/customization/cline-rules)

**Practitioner evidence.** Reddit findings are cited by permalink in the corpus and treated as first-class per the scoping decision, with `forum-consensus` reserved for claims observed independently across threads and `anecdote` used for single reports. Threads drawn on most: r/ExperiencedDevs and r/programming on over-engineering; r/ClaudeAI, r/ClaudeCode, r/cursor and r/ChatGPTCoding on agent over-engineering and rules files; r/technicalwriting and r/sysadmin on documentation bloat.

**Local measurement.** The quirk skill-library word counts (46,547 across 24 `SKILL.md` files; 109,432 across all 90 markdown files; largest single skill 8,469 words) were measured directly in this repository on 2026-09-10, not sourced.


---
*Exploration only. To build a direction: invoke `quirk:brainstorming` → an execution skill (which authors a tech spec when warranted, then plans in context).*
