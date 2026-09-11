> 🧭 EXPLORATION COMPANION — provenance audit for [2026-09-10-simplicity.md](2026-09-10-simplicity.md).

# Simplicity exploration: provenance audit

**Date**: 2026-09-10

This is the citation-checker's document. The main exploration says what the research found; this one says which numbers survived being attacked, which were corrected, and which did not survive at all. If you are about to reuse a figure from the main document, look it up here first.

## Method

Every quantitative claim that was a candidate for the main document was sent to independent verifiers with one instruction: **refute it**. Verifiers were told to default to `unsourceable` when they could not confirm something, and explicitly told not to confirm on plausibility or recall.

Three lenses were used in the first round and the two most productive were retained for the second:

| Lens | Question | Catches |
|---|---|---|
| **traceability** | Does a primary source actually contain this number? | Citation chains that dead-end, figures quoted from a secondary that invented them |
| **construct** | Does the number measure what the claim says it measures? | A narrow lab result inflated into a general claim; raw counts read as rates |
| **currency** | Is it still true, and does it generalise? | Superseded findings; a model generation that no longer exists |

Round 1 ran all three lenses on 40 claims (120 checks) and scored CONFIRMED at 2-of-3. Round 2 ran traceability and construct on 59 headline claims (118 checks) and scored CONFIRMED only when **both** lenses confirmed. The `currency` lens was dropped for round 2 because it produced 4 of 48 non-confirming verdicts in round 1 against traceability's and construct's 40.

**Result: 99 claims tested, 235 adversarial checks, 56 confirmed, 43 corrected or failed.**

Two method notes worth carrying forward. A verifier reported that fetching a PLOS paper as HTML produced *hallucinated numbers* because the page renders every numeric result as inline MathML images — it had to download the PDF and run `pdftotext` to get ground truth, and noted that an earlier HTML fetch had produced "two different, mutually contradictory sets of numbers." Separately, the pipeline's cheap structural validator (URL well-formedness, claim length, quote presence) dropped 10 findings before any verifier ran; it was self-tested against seeded junk first, catching 2 of 2 planted entries while keeping a good one. Neither check would have caught the failures below — those needed a reader who opened the source.

## Round 2: failed both lenses


**Documentation drift measurements show that 7 out of 10 articles containing web references contained rotten links, with link failure rates of 34-80% for older publications.**  
`B2-spec-bloat` · verdicts: overstated / misattributed  

→ A 2014 PLOS ONE study (Klein et al., "Scholarly Context Not Found") found that 7 out of 10 STM articles containing web references suffered from "reference rot" — meaning a referenced URI was either dead (link rot) or had no representative archived snapshot (content drift), not simply "rotten [...]


**In software configuration documentation, stale code element references were found in 23.0% of analyzed repositories (95% CI 18.8–27.2%), with 64% being genuine referential rot.**  
`B2-spec-bloat` · verdicts: overstated / overstated  

→ In a preliminary study, an existing README/wiki documentation-consistency checker (DOCER) applied to AI-assistant configuration files (CLAUDE.md, AGENTS.md, .cursorrules) found stale code-element references in 23.0% of a statistically representative sample of 356 GitHub repositories (82 of 356 [...]


**Documentation duplication in localized environments creates measurable costs. A 100,000-word documentation suite at €0.10/word requires €10,000/language translation; 40% duplication wastes €4,000/lang**  
`B3-doc-systems` · verdicts: overstated / overstated  

→ This figure is a hypothetical illustrative calculation from a CCMS vendor's (Paligo) blog post promoting single-source-of-truth adoption, not an empirical measurement. Under the post's assumed inputs — a 100,000-word documentation suite translated at €0.10/word (€10,000/language), a "typical" [...]


**RLHF reward models exhibit strong positive correlation between response length and reward scores, with Pearson correlation coefficient of 0.451 in baseline models.**  
`C1-llm-verbosity` · verdicts: overstated / overstated  

→ In the ODIN paper's baseline reward model (trained on OpenAssistant-style preference data), the Pearson correlation between response length and reward score was 0.451 — a moderate, not "strong," positive correlation — versus near-zero (~-0.05) for the paper's disentangled (ODIN) reward model [...]


**AlpacaEval without length control shows extreme gameability: models can swing win rates from 22.9% to 64.3% just by adjusting verbosity (concise vs verbose prompts).**  
`C1-llm-verbosity` · verdicts: overstated / overstated  

→ AlpacaEval without length control is highly gameable by verbosity: in the paper's own test, the baseline model gpt4_1106_preview's win rate swung from 22.9% to 64.3% depending solely on whether it was prompted to answer concisely or with maximum detail (vs. 41.9%-64.3%... i.e. only 41.9% to [...]


**Length-controlled evaluation (AlpacaEval 2.0-LC) increases Spearman correlation with human preferences (Chatbot Arena) from 0.94 to 0.98, the highest human alignment of any automated benchmark.**  
`C1-llm-verbosity` · verdicts: overstated / overstated  

→ Length-controlled AlpacaEval 2.0 increases Spearman correlation with LMSYS Chatbot Arena from 0.94 to 0.98 (bootstrap p≈0.07). The authors describe this as the highest Chatbot Arena correlation among benchmarks they were aware of as of April 2024 — a comparison effectively limited to MT-Bench [...]


**Human annotators exhibit asymmetrical preference bias: when humans prefer longer answers, LLM judges align highly; when humans prefer brevity, LLM judges (GPT-3.5) still choose longer answers 72% of t**  
`C1-llm-verbosity` · verdicts: overstated / overstated  

→ Figure 5(b) of Saito et al., "Verbosity Bias in Preference Labeling by Large Language Models" (arXiv:2310.10076), shows GPT-3.5's agreement with HH-RLHF human labels was roughly 19–30% in the bins where humans preferred the shorter response (vs. 54–100% where they preferred the longer one) — [...]


**When human preferences are properly controlled for quality, users strongly prefer concise, source-backed responses: Otus Web (113 words) received 47% preference vs ChatGPT (466 words) at 4%, with cogn**  
`C1-llm-verbosity` · verdicts: overstated / overstated  

→ In a self-published, non-peer-reviewed arXiv preprint (2508.04713, July 2025) authored solely by Carlo Esposito — the founder of Eyed Softwares/Aploide Softwares, maker of Otus Web, the product being evaluated — an estimated ~10,000-participant study reported Otus Web (113 words, 4 sources) [...]


**Human preference datasets show modest but systematic length bias: chosen responses average only 7.5% longer than rejected ones by character count, but only 30.8% of prompts select the longest candidat**  
`C1-llm-verbosity` · verdicts: unsourceable / unsourceable  

→ In the Dahoas-rm-static split of Anthropic's HH-RLHF preference data, approximately 58% of preference pairs have the chosen response longer than the rejected one (Zhao et al., "Bias Fitting to Mitigate Length Bias of Reward Model in RLHF," 2025, Table 1 / §4.2). The paper reports no character- [...]


**A 2026 empirical study of AI-agent-generated pull requests, cited in a separate review-effort-prediction paper, found that 9.9% of AI agent-generated methods are eventually deleted during human code r**  
`C2-ai-code-complexity` · verdicts: unsourceable / overstated  

→ The 9.9%-methods-deleted figure is quoted accurately from a live preprint at arXiv:2605.06464 (correct title: "To What Extent Does Agent-generated Code Require Maintenance? An Empirical Study," Sawada/Shirai/Kashiwa/Yamaguchi et al. — not "Early-Stage Prediction of Review Effort in AI- [...]


**Test flakiness: agents show 0.41 flakiness rate vs 0.30 for humans, driven by file I/O mishandling (4.4% vs 3.5%) and non-deterministic logic (5.2% vs 3.1%).**  
`C3-agent-failure-modes` · verdicts: overstated / overstated  

→ Test flakiness (risk proxy, not confirmed flakiness): static pattern-analysis flagged 41% of agent-generated tests vs. 30% of human-written tests as "flakiness candidates" (containing patterns like non-determinism, hard-coded sleeps, or file/network I/O), driven mainly by file I/O mishandling [...]


**On CoDI-Eval's constraint taxonomy, length is the constraint category every tested model struggles with most: GPT-4 (0613) scores 73.8% on Length vs 86.2-93.6% on Keyword/Toxicity/Sentiment; ChatGPT s**  
`D1-constraint-prompting` · verdicts: overstated / overstated  

→ On CoDI-Eval's Table 3, the individual numbers check out — GPT-4 (0613) scores 73.8% on Length vs 86.2% (Keyword) and 93.6% (Toxicity Avoidance); GPT-3.5-turbo/"ChatGPT" scores 55% on Length, its lowest score; Vicuna-13B scores 41.4% on Length. But Length is not the category every model [...]


**A 2026 re-analysis using retrieval-augmented expert-role injection finds persona prompting produces only small aggregate accuracy differences but a consistent, measurable tradeoff: role prompting incr**  
`D1-constraint-prompting` · verdicts: overstated / overstated  

→ A 2026 study using retrieval-augmented expert-role injection (four conditions: no-role baseline, generic expert prompt, embedding-based role retrieval, and hybrid embedding+LLM retrieval) finds persona prompting produces only small aggregate score differences (all Cohen's d < 0.12) but a [...]


**GPT-4's self-preference bias as a judge appears to be driven by a preference for low-perplexity (familiar-to-the-model) text rather than literal self-identity -- it rates low-perplexity outputs higher**  
`D2-self-critique` · verdicts: misattributed / misattributed  

→ The paper demonstrates GPT-4 exhibits significant self-preference bias as an LLM judge (a separate experiment), and separately shows that six open-source LLM judges (Vicuna-7b/13b, oasst-pythia-12b, dolly-v2-12b, Koala-13b, stablelm-tuned-alpha-7b) rate low-perplexity outputs higher than human [...]


**Cursor best practices recommend: 'Keep rules concise: under 500 lines' and 'Write focused, composable .mdc rules'**  
`D3-harness-practice` · verdicts: unsourceable / misattributed  

→ No source found. The cited awesome-cursorrules README/contributing.md contains no "best practices" guidance about keeping .mdc rules under 500 lines, being composable, or reusing rule blocks. The only related text anywhere in the repo is one example project rule file (for a Hedera/TypeScript [...]


**Aider documentation warns on conventions file size: 'If rules are being forgotten, your CONVENTIONS.md may be too long—keep it under 150–200 lines'**  
`D3-harness-practice` · verdicts: unsourceable / unsourceable  

→ The cited Aider docs page (Specifying coding conventions) describes how to create and load a CONVENTIONS.md file but contains no guidance about file length, line-count limits, or rules being forgotten if the file is too long — no such statement exists on the page.


## Round 2: split verdicts (one lens confirmed, one did not)


**DORA documentation quality has quantified multiplicative effects on technical capability implementation—teams with above-average documentation achieved 1,525% performance**  
`B3-doc-systems` · construct = overstated  

→ DORA's 2022 research (Irvine & DeBellis deep-dive, cloud.google.com/blog) modeled a much larger "lift to organizational performance" from implementing trunk-based development among survey respondents whose self-reported documentation quality was ≥1 SD above the mean on an 8-item score [...]


**Instruction compliance for brevity constraints exhibits U-shaped failure pattern: 97.2% of experiments show worst compliance at medium prompt lengths (~27 words, score 6.**  
`C1-llm-verbosity` · construct = overstated  

→ In an unreviewed Dec. 2025 arXiv preprint introducing its own benchmark (CDCT, single independent researcher, not peer-reviewed), constraint-compliance scores — how closely responses hit a fixed 35-word target, rated by 3 LLM judges rather than by counting words — showed a U-shape across [...]


**Models exhibit verbosity compensation behavior (VC): generating responses that can be compressed without information loss when prompted for conciseness, correlating with **  
`C1-llm-verbosity` · traceability = overstated  

→ Models exhibit verbosity compensation behavior (VC): generating responses that can be compressed without information loss when prompted for conciseness. The paper (an unreviewed arXiv preprint, not confirmed peer-reviewed) finds verbose responses correlate with higher model uncertainty in [...]


**GitClear's 2026 report ('The Maintainability Gap'), covering 623 million analyzed changes from 2023-2026 across eight quality signals, found per-million-line block duplic**  
`C2-ai-code-complexity` · traceability = overstated  

→ GitClear's 2026 report ("The Maintainability Gap"), covering 623 million analyzed changes from 2023-2026 across seven (not eight) quality signals, found per-million-line block duplication climbed from 40.3 in 2023 to 73.0 year-to-date in 2026 (an 81% increase), and that moved/refactored code [...]


**NYU's 'Asleep at the Keyboard' study prompted GitHub Copilot across 89 scenarios tied to MITRE's Top-25 CWE list, generating 1,689 programs, of which approximately 40% we**  
`C2-ai-code-complexity` · construct = overstated  

→ NYU's "Asleep at the Keyboard" study prompted GitHub Copilot across 89 scenarios -- 71 tied to CWEs from MITRE's 2021 "CWE Top 25 Most Dangerous Software Weaknesses" list (54 varying the weakness, 17 varying the SQL-injection prompt) and 18 covering hardware-specific CWEs for which MITRE has [...]


**Refactoring architectural limitations: AI agents perform only 43% architectural refactoring vs 54.9% for humans; rarely address code duplication (1.1% vs 13.7%).**  
`C3-agent-failure-modes` · construct = overstated  

→ In a study of 15,451 AI-agent refactorings across 12,256 Java pull requests (Horikawa et al., "Agentic Refactoring: An Empirical Study of AI Coding Agents," arXiv:2511.04824), only 43.0% were "high-level" (signature-only) refactorings versus 54.9% reported for humans in a separate prior study [...]


**Maintenance burden: 83% of maintenance on AI-generated files done by humans; AI code lacks sufficient requirement coverage.**  
`C3-agent-failure-modes` · construct = overstated  

→ In a study of 100 popular GitHub repos (AIDev dataset), 83.21% of commits that later modified AI-agent-created files were authored by humans rather than AI agents — but this is not evidence of an AI-specific burden: human-authored files show an even higher human-maintenance share (92.98%), and [...]


**Assertion roulette in tests: AI-generated tests contain significantly more assertions (median 2.0 vs 1.0), making failure diagnosis difficult.**  
`C3-agent-failure-modes` · construct = overstated  

→ In a study of 9 TypeScript projects (hand-selected from the AIDev dataset for having the highest AI-authored test activity, using vitest), AI-generated test methods had a significantly higher median assertion count than human-written ones (2.00 vs 1.00, p<0.001). The authors note this pattern [...]


**Ambiguous assertions in tests: 11.58% of agent assertions are ambiguous/unclassified vs only 1.46% in human tests.**  
`C3-agent-failure-modes` · construct = overstated  

→ In this arXiv preprint (2607.12068v1, not shown to be peer-reviewed/published anywhere), restricted to Python test files from open-source GitHub PRs in the AIDev dataset: the paper's headline figures are 11.58% "unknown/unclassified" assertions in a size-matched random subsample of agent- [...]


**AI PR rejection rate: 67.3% of AI-generated PRs rejected vs 15.6% for manual code (LinearB data).**  
`C3-agent-failure-modes` · construct = unsourceable  

→ Unverifiable as stated. The blog mikemason.ca attributes "67.3% of AI-generated PRs rejected vs 15.6% for manual code" to "LinearB data," but the article's own citation link for that sentence points to devin.ai/agents101 (a Devin/Cognition marketing page), not to any LinearB publication — and [...]


**Across 9 tasks tested on OPT and GPT-3 (125M-175B), InstructGPT, few-shot-prompted models, and models fine-tuned specifically on negation, every model type performs worse**  
`D1-constraint-prompting` · construct = overstated  

→ Across 9 tasks, the paper demonstrates a genuine inverse scaling law (performance on negated prompts worsening as model size increases) specifically for pretrained zero-shot LMs (OPT & GPT-3, 125M-175B) and for instruction-tuned LMs (InstructGPT, T0) tested across their available sizes. It [...]


**Reflexion (verbal self-reflection stored in episodic memory across trial-and-error attempts) reached 91% pass@1 on HumanEval, beating the then-state-of-the-art GPT-4's 80**  
`D2-self-critique` · traceability = misattributed  

→ Reflexion reached 91% pass@1 on HumanEval. Its authors frame this as beating "the previous state-of-the-art GPT-4" at 80%, but that 80% figure is the Reflexion team's own uncited, single-sample zero-shot GPT-4 baseline (Table 2's "Base" column), not an externally published number. OpenAI's own [...]


**A 419-item adversarial benchmark (LLMBar) was built specifically because outputs can be constructed that violate instructions but have stylistically appealing/deceptive q**  
`D2-self-critique` · construct = overstated  

→ LLMBar is a 419-pair meta-evaluation benchmark, of which a 319-pair "Adversarial" subset (Neighbor, GPTInst, GPTOut, Manual) — not the full 419 — was built specifically because outputs can be constructed that violate instructions but have superficially appealing/deceptive qualities (e.g., a [...]


**OpenAI's CriticGPT, a model trained specifically to critique code, was preferred over human-written critiques in 63% of comparisons on code with naturally-occurring bugs,**  
`D2-self-critique` · construct = overstated  

→ OpenAI's CriticGPT (and prompted ChatGPT) critiques were preferred over human-written critiques in 63% of comparisons specifically on code with naturally-occurring bugs (real ChatGPT errors previously flagged by human raters). Separately, on a different evaluation set of bugs contractors [...]


**An analysis of 211 million changed lines of code from major tech-company repositories (Jan 2020-Dec 2024) found that refactoring-associated code changes fell from 25% of **  
`D2-self-critique` · construct = overstated  

→ GitClear (a code-analytics vendor) reported, in its 2025 "AI Copilot Code Quality" industry report, that among 211 million changed lines of code (Jan 2020–Dec 2024) drawn from its enterprise client base — including repos it attributes to Google, Microsoft, and Meta plus other unnamed [...]


## Round 1: failed 2-of-3 lenses


**Martin's refactoring of Ousterhout's prime-number code caused a 3-4x performance slowdown by separating a single loop into two methods. Martin later fixed this by recombining logic, reducing**  
`A1-canon` · {'overstated': 2, 'misattributed': 1}  

→ Martin's refactor of Ousterhout's prime-number code (a 5-method version, PrimeGenerator3) caused a measured 3-4x performance slowdown, traced to splitting a single loop into two methods (increaseEach... and candidateIsNot...). Martin fixed it by recombining those two methods into one [...]


**Munoz Baron, Wyrich & Wagner's 2020 meta-analysis (pooling 9 studies, 327 code snippets, ~24,000 human evaluations) found SonarSource's Cognitive Complexity has a pooled correlation of 0.54 **  
`A2-folk-wisdom` · {'overstated': 3}  

→ Muñoz Barón, Wyrich & Wagner (ESEM 2020) ran a random-effects meta-analysis specifically on comprehension-time correlations, pooling 9 of their 10 data sets (327 of 427 total code snippets), and found a pooled/weighted correlation of 0.54 [95% CI 0.24–0.75] between SonarSource's Cognitive [...]


**Indirection without abstraction can be detected by comparing method counts: if wrapper has same number of entry points as wrapped interface, no abstraction is gained**  
`A3-detection` · {'unsourceable': 3}  

→ A Medium opinion post ("Maybe You Don't Need That Function Wrapper?" by Philip Vrieni Arguelles) offers, as a personal design heuristic rather than an empirically validated method, the rule of thumb that a wrapper exposing the same number of functions as the interface it wraps has added [...]


**Cyclomatic complexity thresholds can flag over-engineered code: McCabe's original scale is 1-10 (simple), 11-20 (moderate), 21-50 (complex), >50 (untestable)**  
`A3-detection` · {'misattributed': 3}  

→ McCabe's original recommendation (1976 paper, reaffirmed in NIST SP 500-235, which he co-authored) was a single per-module cyclomatic-complexity limit of 10 — not a four-tier scale. The four-tier categorization "1–10 simple/little risk, 11–20 moderate, 21–50 complex/high risk, >50 [...]


**Dead code prevalence: nearly 20% of code, up to 66% in some applications, goes unused; static analysis + runtime profiling together yield most comprehensive detection**  
`A3-detection` · {'misattributed': 2, 'unsourceable': 1}  

→ The oft-cited "~20%, up to 66%, of code is unused" figure does not appear in the cited Oligo.security article at all — it is misattributed. Its actual origin is a first-person vendor claim on Azul Systems' own blog: "After monitoring many applications, the ballpark number is nearly 20% of [...]


**Empirical finding: close to 80% of code smells are never removed; smells that disappear do so via code removal, not refactoring; developers rarely perform targeted smell-specific refactoring**  
`A3-detection` · {'misattributed': 3}  

→ Citing Tufano et al., "When and Why Your Code Starts to Smell Bad (and Whether the Smells Go Away)," IEEE Transactions on Software Engineering 43(11), 2017 (not the SonarQube paper, which only cites this finding secondhand in its related work): across 200 open-source projects, 80% of code [...]


**Lack of Cohesion in Methods (LCOM) metric: high LCOM values indicate class methods are disparate and not related; such classes attempt many different objectives**  
`A3-detection` · {'misattributed': 3}  

→ Chidamber & Kemerer (1994, IEEE Transactions on Software Engineering, "A Metrics Suite for Object Oriented Design," DOI 10.1109/32.295895) state that a high LCOM value "indicates disparateness in the functionality provided by the class," and that this metric can identify classes "attempting to [...]


**Complexity formula: length × (fan-in × fan-out)² combines lines-of-code, incoming calls, and outgoing calls to measure method over-engineering**  
`A3-detection` · {'misattributed': 3}  

→ The formula length × (fan-in × fan-out)² is Henry & Kafura's 1981 information-flow complexity metric (IEEE TSE, SE-7(5):510–518) — not McCabe cyclomatic complexity, and it does not appear in the cited Scitools "Understanding McCabe Cyclomatic Complexity" article. Fan-in and fan-out there count [...]


**New Jersey's decades-old COBOL unemployment-claims system, chosen and maintained for its stability, could not absorb a roughly 16x (1,600%) surge in claim volume when COVID-19 hit, forcing t**  
`A4-simple-lost` · {'confirmed': 1, 'overstated': 2}  

→ New Jersey's decades-old COBOL unemployment-claims system could not keep pace with the COVID-19 surge in unemployment filings, prompting Governor Murphy to publicly ask for volunteer COBOL programmers in an April 4, 2020 briefing. The "1,600 percent increase" figure cited in that briefing was [...]


**Showing an LLM agent a shorter, better-targeted list of candidate tools instead of a large fixed list measurably improves tool-selection accuracy: with Claude Sonnet 4.6, an adaptive shortli**  
`B1-agent-docs` · {'confirmed': 1, 'overstated': 2}  

→ In a downstream validation on BFCL (370-tool registry, BM25 scorer) using Claude Sonnet 4.6 to pick a tool from a presented candidate set, the paper reports that WHEN the correct tool was included in the candidates shown, Claude picked it correctly 93.1% of the time with an adaptive (BoR- [...]


**Anthropic's official prompting guidance recommends a specific small example count (3 to 5) rather than an exhaustive rule list, with examples tagged to be structurally distinguishable from i**  
`B1-agent-docs` · {'overstated': 3}  

→ Anthropic's official prompting guidance (Claude Platform Docs, "Prompting best practices") recommends including 3–5 examples for best results, and wrapping them in `<example>`/`<examples>` XML tags so Claude can distinguish them from instructions.


**Adding more few-shot examples to a prompt does not help monotonically: on a real software-requirement classification task, LLaMA-3.2-3B's performance worsens significantly once past 80 examp**  
`B1-agent-docs` · {'overstated': 3}  

→ On software-requirement classification (PROMISE), few-shot gains are non-monotonic but model-dependent, not universal: in multi-class classification, LLaMA-3.2-3B's performance worsens significantly beyond 80 examples (it starts assigning multiple classes to a single requirement), and in [...]


## Confirmed by every lens applied

These carried their weight and can be cited as stated.

- An empirical study of 785K Java methods found that developers should keep methods under 24 lines in length, with data showing that [...]
- A peer-reviewed study validating Cognitive Complexity used 24,000 understandability evaluations across 427 code snippets and found [...]
- McCabe's own 1976 founding paper states the famous complexity threshold of 10 was a personal engineering judgment call, not a value [...]
- The only correlation evidence McCabe offers in the founding 1976 paper for complexity predicting reliability comes from a small, non- [...]
- Landman, Serebrenik, Bouwers & Vinju (2016), analyzing 17.6 million Java methods and 6.3 million C functions, found only a moderate [...]
- Landman et al. explicitly concluded the CC/SLOC correlation they measured is too weak to support the common claim that cyclomatic [...]
- Xia et al.'s large-scale 2018 field study found professional developers spend up to approximately 58% of their time on program [...]
- The 58% figure comes from a specific, non-representative sample: 79 professional developers across two Chinese outsourcing firms, [...]
- The competing '70% of time on comprehension' figure (Minelli et al. 2015), often cited alongside or interchangeably with Xia's 58%, is [...]
- Siegmund et al.'s 2014 fMRI study, widely cited as evidence about code comprehension in general, used only 17 undergraduate [...]
- Microsoft's own large-scale field study of refactoring (Kim, Zimmermann, Nagappan, TSE 2014) found that the most heavily refactored [...]
- Peer-reviewed empirical rebuttal to the pro-duplication position: in a large-scale study of 5 commercial/open-source systems, about [...]
- Go deliberately shipped without generics in 2009 despite the feature being one of the most requested by users for over a decade; it [...]
- The widely-cited Y2K cost figures that ARE traceable to a named source are far smaller and narrower than the commonly repeated global [...]
- Prime Video's own engineering blog frames its architecture change narrowly: moving one internal service (audio/video quality [...]
- In a peer-reviewed analysis of 198 real production failures across five widely-used distributed systems (HDFS, Hadoop MapReduce, [...]
- In the 2026 audit of the top one million website home pages, 95.9% had at least one detectable WCAG 2 accessibility failure, up from [...]
- GPT-3.5-Turbo's multi-document QA accuracy drops by more than 20 percentage points when the answer document sits in the middle of the [...]
- On the RULER benchmark, although all tested models claim 32K+ token context windows, only half actually maintain satisfactory [...]
- On IFEval's verifiable-instruction benchmark, GPT-4 reaches 76.89% prompt-level strict accuracy and 83.57% instruction-level strict [...]
- Across 20 frontier models tested on a 500-instruction keyword-inclusion task (IFScale), even the best-performing model achieves only [...]
- On FollowBench's multi-level constraint benchmark, GPT-4-Preview-1106's Hard Satisfaction Rate falls from 84.7% at 1 constraint to [...]
- GPT-4 scores 0.881 (DRFR) on simple single-level 'And' instruction compositions but only 0.694 on 3+-deep nested 'Selection' [...]
- On Multi-IF's multi-turn multilingual benchmark, o1-preview's average instruction-following accuracy across all languages drops from [...]
- OpenAI's instruction-hierarchy training (teaching models to rank system messages above user messages above third-party content) [...]
- Tool descriptions carry a measurable token tax: at roughly 200 tokens per tool description, a shortlist of just 100 candidate tools [...]
- Function-calling accuracy degrades sharply as tool catalogs or API-response context grow, even within a stated 128K-token window: [...]
- Anthropic's official prompting-best-practices docs state that for prompts with 20K+ tokens of document input, placing the query after [...]
- The ODIN method successfully reduces length-reward correlation from Pearson r=0.451 to r=-0.03 by disentangling quality and length [...]
- GitClear's original 2023/2024 report analyzed 153 million changed lines of code from Jan 2020-Dec 2023 and projected code churn (lines [...]
- GitClear's 2025 update (211M changed lines, Jan 2020-Dec 2024, from Google/Microsoft/Meta/enterprise repos) found copy/pasted code [...]
- In the Stanford user study (47 participants: 33 with AI-assistant access, 14 control) on the SQL-injection task, 36% of AI-assisted [...]
- METR's randomized controlled trial found that allowing 16 experienced open-source developers to use early-2025 AI tools (mainly Cursor [...]
- A large-scale real-world-repository study (19,816 AI-involved files across 12,749 commits, with 36,855 AI-generated and 65,391 human- [...]
- DORA's 2024 State of DevOps report found a 25% increase in AI adoption was associated with an estimated 1.5% decrease in software [...]
- Faros AI's July 2025 telemetry study of 10,000+ developers across 1,255 teams found teams with high AI adoption completed 21% more [...]
- CodeRabbit's analysis of 470 GitHub pull requests (320 AI co-authored, 150 human-authored) found AI-assisted PRs generated about 1.7x [...]
- Design smell persistence: agents show zero median change in design/implementation smell counts despite surface-level metric improvements.
- FollowBench's multi-level design shows GPT-4's Hard Satisfaction Rate falling from 84.7% at difficulty L1 to 61.9% at L5, and GPT-3.5 [...]
- ComplexBench (NeurIPS 2024) finds GPT-4-1106 still fails roughly 1 in 5 complex, multi-constraint instructions overall (DRFR-style [...]
- LIFEBench, evaluating 26 LLMs (9 proprietary, 8 open-source, 3 long-text-enhanced) on explicit length instructions, finds 23 of 26 [...]
- Testing 162 personas across 6 relationship types and 8 expertise domains, on 2,410 factual questions, across 4 popular LLM families, [...]
- s1's 'budget forcing' technique controls test-time reasoning length by appending 'Wait' to force continued thinking past a natural [...]
- Chain of Draft (CoD) claims to match or beat standard Chain-of-Thought accuracy using as little as 7.6% of the tokens, but its own [...]
- Self-Refine (LLM generates output, critiques it, then revises using its own critique) improved human- and metric-judged output quality [...]
- Self-consistency (sampling many reasoning paths and taking the majority answer, no critique step at all) boosted chain-of-thought [...]
- Position bias alone -- merely swapping which answer is shown first -- was large enough that a weaker model (Vicuna-13B) 'beat' ChatGPT [...]
- A paper specifically measuring verbosity bias in LLM-based preference labeling found GPT-4 prefers longer answers more than human [...]
- LLM evaluators (GPT-4, Llama 2) can recognize their own generations at above-chance accuracy, and the more accurately a model can [...]
- In a code-evaluation bias study, inserting extra 'dummy' functions that inflate a program's apparent complexity without changing its [...]
- Length-controlling AlpacaEval's automatic judge (statistically adjusting for the fact that longer answers get preferred) raised its [...]
- Replacing direct LLM-judge scoring with an LLM-generated, instruction-specific checklist of yes/no questions raised the rate of exact [...]
- A separate checklist-based evaluation framework (CheckEval), which decomposes evaluation into traceable binary questions, improved [...]
- Beyond assertion, one practitioner supplies an actual causal mechanism for why over-engineering recedes with experience: direct, [...]
- A concrete attempt to force documentation currency by tying it to ticket closure achieved only about 20% compliance.
- A reviewer reduced a 620-line AI-generated file to 68 lines and cut 9 of 13 imported libraries while preserving identical [...]

## Not verified

**188 quantitative claims in the corpus were never sent to a verifier.** The first pass capped verification at 40 of 228 and logged the cap; the second pass added the 59 that were headline candidates for the main document. Everything else remains unverified and is marked **(unverified)** wherever the main document uses it. Unverified numbers were not allowed to carry an argument — where one appears, it illustrates a point another verified finding establishes.

Twelve depth-round facets are treated as verified-by-provenance rather than re-verified: those agents read primary sources directly, and in one case re-ran the original authors' statistical analysis from their published replication package to reproduce ρ=0.935 against a claimed ρ=0.94, then showed the correlation collapses when the 20 non-independent data points are reduced to 5 scenario means.

## The one that is worth reading in full

The claim that **"Karpathy's 4 CLAUDE.md rules cut Claude's mistake rate from 41% to 11%"** circulates widely. The trace:

- Andrej Karpathy's actual post (26 January 2026) describes coding failure modes qualitatively and **contains no percentages at all**.
- The statistic originates with a different person entirely, in a long-form post published 9 May 2026, claiming to have tracked the same 50 tasks across 30 codebases for six weeks.
- That post discloses **no task list, no raw data, no blinding, and no adjudication criteria**. "Mistake" is self-counted across seven loosely specified categories.
- Its internal arithmetic is at least self-consistent — the 4-rule to 12-rule drop is described as 8 points, matching the quoted figures.
- At least one aggregator attributes the number to "Karpathy's original X thread."
- Reddit commenters have publicly challenged the figures as unmethodical.
- Both primary URLs returned **HTTP 402 Payment Required** to the verifier, and the Wayback Machine was rate-limited, so the earliest circulating version could not be independently pinned down.

Nothing here shows the underlying advice is bad. It shows that the number attached to it is not evidence, and that it acquired a famous name in transit.
