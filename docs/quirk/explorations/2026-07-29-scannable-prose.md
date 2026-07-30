> 🧭 EXPLORATION — not a spec. No locked decisions; nothing here is build-ready.

# Exploring: scannable, information-dense prose

**Date**: 2026-07-29 · **Emphasis**: research-heavy blended · **Intensity**: 0.5 (Exploratory) · **Involvement**: medium

## Framing

How do you write prose that is scannable, easy to grok, and informative — cutting verbosity without losing information?

Scoped to **human-facing technical documents**: READMEs, guides, ADRs, PR descriptions, changelogs. Research depth was set to deep multi-round. The exploration feeds a **reusable style guide**, so every direction is judged on whether a reviewer could look at a draft and say *violates* or *satisfies* — not on whether it sounds wise.

One finding shapes everything below. **The evidence base for the standard advice is far thinner than the advice implies.** The clean experiment that would settle the central question — same causal content, bullets versus connected prose, comprehension as the outcome — has never been run. Several load-bearing numbers in wide circulation could not be sourced at all. What survives is a set of *structural* rules, because no numeric threshold in this area turned out to be defensible.

## What was explored

Eight parallel research facets produced 72 sourced findings; three gap-driven depth rounds followed.

| Facet | Question put to it |
|---|---|
| **Scanning behavior** | What eyetracking actually shows about reading on screens |
| **Plain language & readability** | Mandated rules, formula critiques, cognitive load theory |
| **Bullets, pro and con** | Usability evidence vs. the Tufte/McMaster critique |
| **Tables & matrices** | When a grid beats prose; design and accessibility failure modes |
| **Style systems & canon** | Google, Microsoft, Diátaxis, Williams, Gopen & Swan, Lanham |
| **Sentence-level compression** | Mechanical techniques, and where cutting starts destroying |
| **Visual hierarchy** | Headings, emphasis, callouts, chunking, progressive disclosure |
| **Failure modes** | Where 'make it scannable' goes wrong — adversarial by design |

**Depth rounds.** (1) Does bulleting causal reasoning measurably hurt comprehension? (2) Does heavy formatting now carry a credibility cost? (3) Is there a compression threshold past which comprehension degrades? A fourth agent returned placeholder junk and was re-run with two independent agents.

**Ideation.** Three technique lenses — first-principles, analogical transfer, assumption reversal — each pushed past its first pass, then quality-gated. A second round deepened three clusters and closed three coverage gaps with fresh research. Every survivor went through a challenge pass.

- _Steered:_ at the idea gate the user chose to deepen **logical structure**, **compression governance**, and **order & repetition**, leaving *channels & emphasis* as round-1 output; and to close the **figures/code**, **enforcement**, and **cross-document** gaps, explicitly deferring *readers beyond the default*.
- _Out of scope:_ voice, tone and register; typographic parameters (line length, font); localization and non-native-English readers; agent-facing docs.

## Findings: what the research actually supports

### Theme: the famous numbers do not hold up evenly

- **The F-pattern is a symptom, not a target.** NN/g's own definition: it is "the default pattern when there are no strong cues to attract the eyes towards meaningful information." EyeQuant's 99-site study (157,498 scan-phase fixations) found no letter shape at all — a center-left "blob." Designing *for* the F-pattern optimizes for your own bad formatting. — [NN/g](https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/), [EyeQuant](https://www.eyequant.com/resources/eye-tracking-studies-does-the-famous-f-shape-pattern-really-exist)
- **The 25% screen-reading penalty is CRT-era.** Modern figures are 6.2% (iPad) and 10.7% (Kindle). — [NN/g](https://www.nngroup.com/articles/ipad-and-kindle-reading-speeds/)
- **Miller's 7±2 was revised to ~4.** Cowan (2001), controlling for rehearsal and long-term-memory support. Most style guides still cite 7. — [Journal of Cognition](https://journalofcognition.org/articles/10.5334/joc.387)
- **The 124% usability gain is not a credibility finding.** Morkes & Nielsen measured task time, task errors, recall, sitemap recall, and satisfaction. Credibility was never quantified. It cannot support a trust claim in either direction. — [NN/g](https://www.nngroup.com/articles/concise-scannable-and-objective-how-to-write-for-the-web/)
- **Could not be sourced at all:** the "30% bold maximum," "users read 25% faster with bullets," "bold enables 30% faster scanning," and the widely-quoted Mattis PowerPoint line.

### Theme: what does hold up

- **Readers consume ~20% of a page.** From 59,573 page views; users spend 4.4 additional seconds per extra 100 words. Pages under 111 words reach 50% reading depth. — [Weinreich et al. 2008 via NN/g](https://www.nngroup.com/articles/how-little-do-users-read/)
- **Causal connectives do specific cognitive work.** "Because" triggers inference generation; "and" and "after" do not. Visual adjacency between two bullets is not a demonstrated substitute. — [Millis, Golding & Barker 1995](https://www.tandfonline.com/doi)
- **The screen deficit is genre-specific.** Delgado et al. 2018 (54 studies, 170,000+ participants): g = −0.27 for expository text, g = 0.01 for narrative. Technical documentation sits squarely in the penalized genre. — [meta-analysis](https://www.researchgate.net/publication/330854760)
- **Compression drops qualifiers before it drops facts.** In LLM-compressed financial filings, every sentence stayed accurate while context share fell from 25% to 9%. The failure mode is not false statements but *orphaned* ones — readers who are confidently wrong rather than visibly confused. — [arXiv](https://arxiv.org/pdf/2606.29251)
- **Coherence, not length, is what breaks.** Mayer's coherence principle held in 23/23 tests (median d = 0.86); the redundancy principle at d = 0.87. Britton & Gülgöz showed that *restoring* connective material improves recall. — [Cambridge Handbook](https://www.cambridge.org/core/books/abs/cambridge-handbook-of-multimedia-learning/principles-for-reducing-extraneous-processing-in-multimedia-learning-coherence-signaling-redundancy-spatial-contiguit)
- **71.6% of screen-reader users navigate by headings.** The heading outline is a primary index, not decoration. — [WebAIM 2024 survey](https://medium.com/@colleengratzer/key-findings-from-the-webaim-2024-screen-reader-user-survey-bb15864d3bc8)
- **Tables can be verification devices.** Parnas-style tabular specification gives completeness (no missing cases) and consistency (no contradicting rules) — properties no scanning study measures. — [Tabular Expressions in Software Engineering](https://www.researchgate.net/publication/228939082_Tabular_Expressions_in_Software_Engineering)

### Theme: the three questions with no answer

- **No clean bullets-vs-prose RCT on causal content exists.** The closest, Garner & Alley 2013 (n=110, d=0.47–0.89 on causal misconceptions and 10-day retention), confounds bullet-removal with diagram-addition — so it may be the *diagram* doing the work. — [Penn State](https://writing.engr.psu.edu/ae_comprehension.pdf)
- **No compression dose-response curve exists.** Nobody has cut one document to 10/30/50/70/90% and measured comprehension at each level. What exists: procedural content tolerates aggressive cutting (Carroll's minimalism); explanatory content does not (2025 Google RCT, n=4,563 — legal text +3.5% vs PubMed +14.6%). — [arXiv](https://arxiv.org/abs/2505.01980)
- **The formatting → distrust chain has never been isolated.** Four research rounds found no experiment manipulating formatting density alone. What is real is a *labeling* effect (n=556, Cohen's h=0.28). Meanwhile processing-fluency research predicts the opposite: easier-to-process text is judged **more** true. — [Alter & Oppenheimer 2009](https://journals.sagepub.com/doi/10.1177/1088868309341564)

## Idea landscape

**16 directions across 7 clusters. No winner is declared and nothing is ranked.**

Challenge verdicts are inline. **Thirteen of sixteen came back *weakened*** — in nearly every case for the same reason: a genuine, well-sourced insight carrying unvalidated procedural machinery. That split is the most useful thing in this document. The insights are usable now; the machinery is untested invention and should be labelled as such by any guide that adopts it.

Full mechanisms, steelmen, and falsification tests: **[2026-07-29-scannable-prose-mechanisms.md](2026-07-29-scannable-prose-mechanisms.md)**.

### How hard you may cut, and what a cut is allowed to touch

#### Two compression budgets, tagged at the clause

*⚠️ weakened*

Decide how hard you may cut with one question — could a reader act correctly knowing only WHAT and in what ORDER, or do they need WHY — but tag the answer per clause, not per passage, and run a pinning pass before any cutting starts.

**Why this might actually work.** The 2025 Google RCT (n=4,563) applied the same simplification technique to two corpora and got 3.5% comprehension gain on legal text versus 14.6% on PubMed — content class, not prose quality, decided the payoff, and since no dose-response curve exists a guide can say 'cut hard here, conservatively there' but can never cite a percentage. Round 1 conceded two things: it presupposed a split-by-mode pass it did not supply, and it contradicted the deletability direction on the quick-start-carrying-a-safety-precondition case. Both concessions have the same cause — classification at passage grain, where mixing is the norm rather than an edge case. Dropping to the clause removes the precondition that content be 'clean'; running the pin as a pre-filter rather than a competing top-level rule turns the contradiction into an ordering question instead of an unadjudicated tie. The clause-grain tag and the Requires/If-skipped slot are design inferences (the latter structurally borrowed from design-by-contract preconditions), not measured effects.

**Worked example.** One sentence, two modes. Before: 'Run `foo migrate` before restarting the service — restarting first serves stale config for up to 5 minutes.' Passage-level tagging forces a single verdict, which either over-protects the imperative or exposes the consequence clause to bare-imperative cutting. Clause-level: 'Run `foo migrate` before restarting the service' → PROCEDURAL, compress hard; '— restarting first serves stale config for up to 5 minutes' → EXPLANATORY (consequence marker), pinned. Result: '`foo migrate`, then restart — restarting first serves up to 5 min of stale config.' Four filler words cut, zero facts cut. The precondition slot. Before (order only, dependency implicit): '1. Stop the application server. 2. Run migrate.sh --apply. 3. Restart the application server.' After: '2. Run `migrate.sh --apply`. Requires: step 1 complete — server fully stopped, not just draining. If skipped: migrate.sh applies schema changes against live traffic and can corrupt in-flight transactions. 3. Restart. Requires: step 2 exited 0. If skipped: the app starts against a partially-applied schema and crash-loops.' Explanatory budget, unchanged: 'because our access patterns are >80% ad-hoc joins across five tables, and DynamoDB's single-table design would require denormalizing all of them up front' stays intact; 'we chose Postgres for flexibility' deletes the decision-relevant evidence and replaces it with nothing.

**Replaces.** Global word-count or Flesch/Fog targets applied evenly across a document; the undifferentiated instruction 'tighten this up'; bare numbered lists used for procedures that carry a consequential dependency; and the vague inline 'Note: order matters here,' which says a dependency exists without ever naming what breaks.

**Held against it.** The direction's own failure-mode section is effectively a pre-written rebuttal: clause boundaries are "genuinely fuzzy," two reviewers will disagree, and "an author under deadline can tag everything EXPLANATORY to protect it" — i.e., the gaming surface the mechanism was built to close simply relocates to a finer grain.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#two-compression-budgets-tagged-at-the-clause)

#### What a cut is allowed to touch: operation class first, then dependency checks

*⚠️ weakened*

'Cut ruthlessly' collapses three operations with three different risk profiles — removing a word, removing a claim, removing a qualifier that scopes a surviving claim — so name which one you are performing, then run the dependency checks at the intensity that operation warrants.

**Why this might actually work.** The MD&A finding is specifically that accuracy held constant — no false claims introduced — while context share collapsed from 25% to 9%. That is a qualifier-level failure riding on a claim-level compression ratio, and it produces readers who are confidently wrong rather than visibly confused. Naming it as a third, distinct operation explains why 'the summary was factually accurate but decontextualized' keeps recurring across separate facets as if it were one diffuse phenomenon. Separately, checks (c) and (d) were left at the same level of vagueness despite having completely different enforceability: (d) is mechanizable today, (c) has no metric anywhere in the 72-finding corpus, and inventing a percentage for it would repeat exactly the error this research flags elsewhere. The honest alternative for (c) is the pattern this landscape already uses for unfalsifiable calls — forced pre-commitment plus an independent second reader.

**Worked example.** Before: 'Connection pooling substantially improves throughput in most configurations, particularly under high concurrency (PostgreSQL 12+; no measurable change observed on MySQL in our benchmarks, n=40 runs).' WORD-LEVEL, safe, no review: 'Connection pooling substantially improves throughput under high concurrency (PostgreSQL 12+; no measurable change on MySQL, n=40 runs).' The hedge-stack 'in most configurations, particularly' goes; claim and qualifiers intact. QUALIFIER-LEVEL, the dangerous one disguised as ordinary tightening: 'Connection pooling substantially improves throughput under high concurrency.' Fewer words, same claim — but the PostgreSQL-only scope and the MySQL null result are gone, converting a conditional claim into an unconditional and now-false-for-MySQL one. CLAIM-LEVEL: dropping the whole sentence because a Performance section is over budget — and if another section says 'see the pooling note above,' check (d) fails and the cut cannot ship without also handling the pointer. Check (d) in isolation: three paragraphs on retry semantics get cut for length, leaving 'For this reason, always set a timeout' pointing at nothing — a confident, unsupported assertion. Inline restatement: 'Because retries without a timeout can loop indefinitely against a hung dependency, always set a timeout.' Check (c) in isolation: a supported-platforms list ends '...Linux, macOS, and Windows (community-maintained, best-effort)'; under a length cut an editor drops to 'Linux, macOS.' The forced pre-commitment surfaces that a Windows user's next action — filing a bug expecting first-class support — is exactly what changes, so the qualifier survives compression: '...Linux, macOS, and Windows (best-effort).'

**Replaces.** 'Cut every unnecessary word' and 'strip the hedges, be direct,' both of which treat deletability as a property of a word's length or tone rather than of what depends on it; and the instinct that a shorter sentence is automatically a safer edit.

**Held against it.** The word/claim/qualifier split is less clean in practice than the taxonomy assumes: removing a hedge-stack like 'in most configurations, particularly' is simultaneously a word-level trim and a qualifier-level operation, and real edits routinely straddle categories rather than sitting cleanly in one.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#what-a-cut-is-allowed-to-touch-operation-class-first-then-dependency-checks)

#### The hunk test for changelogs and PR descriptions

*⚠️ weakened*

Write a changelog or PR line the way a unified diff shows a change — the delta plus the minimum FROM-state needed to interpret it — never a bare assertion with zero anchor, never a restatement of everything that didn't change.

**Why this might actually work.** Changelogs and PR descriptions are the one genre whose own convention — one terse line — actively rewards the decontextualization failure the rest of this research documents (MD&A context share 25%→9%), and unlike a doc paragraph there is no surrounding prose from which a reader can reconstruct what was dropped.

**Worked example.** Zero-context hunk: 'Added retry logic to the sync job.' Minimal-context hunk: 'Sync job now retries once on a 5xx before failing (previously failed immediately) — cuts false alerts from transient network blips.' One clause of prior state, one of consequence, nothing about the parts of the sync job that didn't change.

**Replaces.** 'Keep changelog entries to one short line' as an absolute, and its opposite failure, the entry that re-explains the whole feature.

**Held against it.** Its own grounding is an analogy, not evidence: the cited support is the MD&A decontextualization study (financial-summary compression, not changelogs) plus the diff-hunk metaphor itself, which is engineering intuition, not a reading-comprehension finding. No source in the provided research packet measures changelog or PR-description comprehension at all.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#the-hunk-test-for-changelogs-and-pr-descriptions)

### Devices that carry — or destroy — logical structure

#### The pairwise relation test: chained-in-time vs. crossed-in-state

*⚠️ weakened*

Test relation per PAIR of items, not per passage — a pair whose order can't be reversed without changing what's true is chained and belongs in prose with an explicit connective; a pair whose values combine independently is crossed and belongs in a grid; a passage containing both gets two artifacts, not one compromise.

**Why this might actually work.** The closest controlled test, Garner & Alley 2013 (n=110, d=0.47-0.89), found bulleted causal-process content produced more causal misconceptions and worse 10-day retention — but the manipulation also added a diagram and halved the text, so it isolates 'bullets+phrase-headlines vs. diagram+sentence-headlines,' not bullets vs. prose. The clean RCT does not exist, so this is a precautionary rule built on convergence (Millis/Golding/Barker: 'because' triggers inference, 'and'/'after' do not), and a style guide should say so rather than overclaim. What the second pass adds is not evidence but the removal of three places where judgment substituted for a rule: which pair gets tested, what happens when reviewers disagree, and — the one that dissolves the landscape's loudest internal conflict — the unit of classification. The swap test's trigger ('conditions are chained') and the completeness proof's trigger ('two or more independent conditions determine an outcome') are both correct, about different relations, and a real passage contains instances of both among its different pairs. No single pair is correctly both 'swap changes truth' and 'independent, cross freely.' The apparent incompatibility was manufactured by applying both triggers to whole passages. This is a logical resolution, not a measured one: nothing in the sweep tests whether pairwise decomposition improves reader outcomes.

**Worked example.** Chained, fails: '- Certificate expires / - Requests start failing / - Retry logic masks the errors / - On-call gets paged at 3am.' Swap items 2 and 3 and 'retry logic masks the errors' precedes 'requests start failing' — nothing to mask yet. Prose: 'Because the certificate expires silently, requests start failing; because retry logic masks those failures, the first visible symptom is on-call getting paged for what is actually a stale cert.' Disputed pair, resolved by tie-break: '- Enable read replicas / - Increase the connection pool size.' Reader A calls it parallel, reader B calls it chained. Read 'Increase the connection pool size' alone — meaning intact without the replicas bullet, nothing in it depends on replica state. Verdict crossed; stays bulleted; B's ordering was a style opinion, not a logical dependency. Mixed passage, two artifacts: 'During a deploy, the first 10 minutes route all requests to the canary build regardless of region or tier. Once that window closes, requests route by region and tier.' The pair (canary-window, region) is chained — region is irrelevant until the window resolves. The pair (region, tier) is crossed. Output: prose time-axis — 'For the first 10 minutes after deploy, route all requests to canary, regardless of region or tier. After the window closes, use the steady-state table below.' — plus a 2x2 region x tier table headed 'steady-state routing (post-canary),' not one flattened table encoding time as a third column. Labeling: 'Deployment requirements: - Kubernetes 1.28+ - 4 vCPU minimum - Outbound access to registry.example.com' leaves a reader unable to tell whether missing one item is a hard blocker. 'Deployment requirements — all of the following must hold:' fixes it. Same glyph, different relation: 'Authentication — choose one of the following: - API key - OAuth2 token - mTLS client cert.'

**Replaces.** 'Bulletize for scannability' as an undifferentiated default and its overcorrection 'never bullet technical content'; passage-level routing under either predecessor rule ('this passage failed the swap, the whole thing is prose' / 'this passage has 2+ conditions, the whole thing is a grid'), both of which assume a passage-level uniformity mixed content doesn't have; and the undifferentiated bullet used as a save-everything glyph.

**Held against it.** Every piece of cited evidence (Garner & Alley, Millis/Golding/Barker, Jansen, Tufte, McMaster) supports 'chained content loses something when bulleted' at the passage or connective level; none of it tests, or was designed to test, whether decomposing a passage into pairs and routing each pair separately produces better reader outcomes than picking one uniform treatment.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#the-pairwise-relation-test-chained-in-time-vs-crossed-in-state)

#### The table as a completeness proof, with escape hatches

*⚠️ weakened*

When a document states conditional behavior a table isn't a scannability choice, it's a verification device — and it only works if you band continuous conditions first, factor out mode switches before multiplying, and distinguish a cell that is impossible from a cell nobody has specified.

**Why this might actually work.** Parnas-style tabular specification gives tables a property no scanning study measures — enumerability — which converts 'did I cover every case?' from a close-reading problem into a counting problem, and resolves the Google-vs-Microsoft argument about one-row tables by changing the criterion entirely: a table earns its place by being falsifiable, not by having 3+ attributes per row. Round 1 applied that completeness property only to the easy case: small, discrete, already-fully-specified conditions. Banding, mode-gating and the impossible/unspecified split extend the same logic to the cases the source research did not spell out — they are reasoned from the Parnas base plus standard decision-table factoring practice, not additional empirical claims, and should be read that way.

**Worked example.** Prose that reads fine sentence by sentence: 'If the request is authenticated, allow it. If unauthenticated but from the internal network, log a warning and allow. Unauthenticated external requests are rejected, except during maintenance mode, where all requests are rejected regardless of authentication.' Grid it — Auth {yes,no} x Network {internal,external} x Maintenance {yes,no} = 8 rows — and the Auth=yes + Maintenance=yes row surfaces a direct contradiction between sentence one and the maintenance clause, invisible in prose because each sentence was individually correct. Cardinality: add Region {us,eu,apac} and the naive grid is 24 rows. Check for mode-gating — does Maintenance=yes make Region irrelevant? Yes. Factor it out: phase rule in prose ('During maintenance, all requests are rejected regardless of auth, network or region'), then Auth x Network x Region = 12 rows, with the mode split named rather than hidden. Unfillable: in that 12-row grid, Auth=no + Network=internal + Region=apac has no stated outcome. If §3.2 says internal traffic is always pre-authenticated, mark the row 'IMPOSSIBLE per §3.2.' If no such invariant exists anywhere in the document, mark it 'UNSPECIFIED — open question for spec owner' — a materially different and more honest flag than silently omitting the row.

**Replaces.** 'Use a table when a row has 3+ related attributes,' which optimizes for display and says nothing about whether the logic being documented is complete; and 'N/A' written into a cell, which hides the difference between a real invariant and an undocumented gap.

**Held against it.** The grounded core (Parnas/SCR tabular expressions guarantee completeness and consistency) comes from formal requirements engineering for safety-critical software specifications — a genre and effort budget nothing like a README, ADR, or PR description.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#the-table-as-a-completeness-proof-with-escape-hatches)

### Information order and budgeted repetition

#### Fractal old-new, with a cold start and a licensed exception

*⚠️ weakened*

'Lead with the important part' holds at three scales, not two — a document's or section's first sentence has no prior text to be 'old,' so it borrows its anchor from the title; sections open with the conclusion; sentences open with established information and land the new claim last, except where fronting new information deliberately corrects an assumption.

**Why this might actually work.** The passive-voice fight is a level confusion: BLUF is document architecture, Gopen & Swan's topic/stress is sentence grammar, and Strunk & White's blanket prohibition is what you get when the document-level instruction is pushed one level down and forces new information into every subject slot — which is also why Pullum can report that 84% of passives are not mystifying to readers. Round 1 admitted it had nothing to anchor to at a document's first sentence; the fix relocates the source of 'old' information from the discourse itself to the paratext the reader already holds — a title, a search query, a link they clicked — which is the same move BLUF makes at document level, pushed one level earlier. And the 'when may I break this' question was never absent from the linguistics, only from this landscape's use of it, which had borrowed only Halliday's unmarked case.

**Worked example.** Cold start, before: 'This library provides a flexible framework for state management in modern JavaScript applications.' Swap-test: equally true of Redux, Zustand, MobX, Recoil — pure category noise, fails. After: 'Nimbus stores UI state in plain objects and re-renders only the components whose subscribed keys changed — no selectors, no memoized hooks to write.' False for Redux, so it passes. Tail-chain: 'Connection pooling was added last quarter. It was intended to reduce database load. Load has not measurably decreased, however. The reason turned out to be a driver-level pooling layer already running underneath ours.' Tails: 'last quarter / database load / however / running underneath ours' — a date, a repeated concept, a hedge word, and only then an advancing fact. Fixed: '...running underneath ours, duplicating our pool and canceling out the intended reduction — so the fix is disabling one of the two layers, not tuning pool size.' Subject-swap: prior sentence 'We migrated the orders table to Postgres last sprint.' Bad next: 'A rollback plan was prepared by the SRE team in case of failure' — subject has no antecedent in the prior sentence; rewrite active. Passes: 'The migration was validated against production traffic for a week before cutover' — subject is a clear synonym for the event just named, so it stays passive. Marked exception, earned: after several sentences establishing that a slow query was assumed to be the database — 'Not the database — the connection pool itself was exhausted, three levels up from where everyone was looking.' Unearned: 'The cache was cold. A separate issue affected memory allocation. Networking had a brief blip too.' Three consecutive fronted new subjects, nothing overturned; reorder old-to-new like any other paragraph.

**Replaces.** 'Always lead with the point' as one flat rule with no distinction between document opening, section opening and sentence word order; the blanket 'avoid passive voice' it generates as a side effect; the blank spot the prior version admitted at a cold open; and the two positions that were otherwise the only ones available — 'always old-before-new' (too rigid to describe competent writing) or no rule at all.

**Held against it.** Every mechanism specific to this direction's actual contribution — the cold-start swap test, the anchor-from-title move, and the licensed marked-theme exception with its frequency and contrast gates — rests on zero technical-writing-specific evidence, and the direction says so itself: 'No experimental evidence in this sweep isolates the marked-theme device in technical documentation specifically...

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#fractal-old-new-with-a-cold-start-and-a-licensed-exception)

#### Redundancy debt, triggered by structural distance

*✅ survives*

Repeat yourself only where a reader could plausibly have lost the thread — measured by how many new concepts intervened and whether a heading came between — never on a fixed paragraph number, never in narrative sections, and most aggressively on the reference and how-to pages a search actually lands on.

**Why this might actually work.** Two independent measurements license bounded redundancy against Mayer's redundancy principle (d=0.87), and neither is a curve: Cowan supplies a capacity ceiling for the reading condition itself, Delgado supplies a genre-specific screen penalty. Mayer's principle targets modality-redundant duplication (text repeating a diagram); this targets intra-textual continuity repair, which is why both can be right. The previous version borrowed a curve shaped like the right idea — attention is not uniform — from a study that could not support the specific number it was asked to support. The arrival-mode scoping is a separate correction in the same direction: 'write every page as if it's someone's first page' pays a context-restating tax across the whole doc-set to serve a minority whose landing points are actually predictable.

**Worked example.** Entity distance: after introducing the shard map, the replica set, the write quorum, the failover controller and the health-check loop across several paragraphs — five entities deep — a sentence reads '...so the controller defers to it during a partition.' 'It' has no recoverable referent. Fixed: '...so the failover controller defers to the write quorum during a partition.' Heading crossing on a reference section: '## Rate Limits — This is enforced the same way as described above, but with a shorter window.' A reader who searched the exact error string and landed here has no 'above.' Fixed: '## Rate Limits — Requests are capped per API key using the token-bucket algorithm (see Retry Behavior for how clients should back off), but the window is 60 seconds instead of Retry Behavior's 5 minutes.' Arrival-mode scoping: the third page of an onboarding tutorial gets no such treatment — search rarely targets 'step 3 of the tutorial,' and the preceding pages already established the frame. Genre gate: an ADR paragraph opens 'Because each shard owns a disjoint key range (see Sharding above), replicas must be pinned to the same shard as their primary' — expository, gets the clause. A changelog line stays terse.

**Replaces.** The paragraph-position trigger ('paragraph 4' as a literal rule); 'never repeat yourself' applied uniformly across genre, medium and position; its lazy inverse 'add a summary box because people skim'; the blanket 'add a search bar and assume readers can search their way to anything'; and the opposite overcorrection, 'write every page as if it's someone's first page.'

**Held against it.** The central enforcement number is a construct-validity leap dressed as precision: Cowan's ~4 chunks was measured on short-term recall of discrete stimuli under controlled lab conditions, not on how many named entities a reader can track across paragraphs of continuous technical prose before losing an antecedent.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#redundancy-debt-triggered-by-structural-distance)

### Channels and budgets (carried forward from round 1)

#### One emphasis budget per section, allocated by blast radius

*⚠️ weakened*

Treat every loud device as a withdrawal from one finite per-section budget, and allocate that budget by what a reader's misreading would cost — not by how important the author feels the claim is.

**Why this might actually work.** Columbia and McMaster are usually read as evidence about causal shape, but both are failure-cost cases, and the Google RCT's legal-vs-medical gap makes the same point quantitatively: legal text isn't more causal in shape than medical text, it's costlier to misread. Stakes and shape are independent axes, so a guide organized purely around content shape still fails on an enumerable-but-lethal list — and separately, the em-dash/bold/bullet-triad cluster now reads as an AI signature to a growing share of readers, which is a documented phenomenon with an un-isolated trust penalty, so treat density as a risk to cap rather than a proven cost.

**Worked example.** Before: '**Note:** This endpoint is **rate-limited** to **100 requests/min**, and you **must** include an **API key** or the request will **fail**.' — seven bold spans; strip them and nothing stands out. After: 'This endpoint rate-limits to 100 requests/min. **Requests without an API key are rejected outright** — the one hard-failure mode; everything else degrades.' Allocation case: in an otherwise ordinary flag list ('--dry-run', '--verbose', '--force'), same shape, different blast radius — '`--force` — skip confirmation prompts; this can silently overwrite uncommitted local changes with no undo.'

**Replaces.** 'Use bold and callouts to highlight key information,' which has no ceiling on density and no test distinguishing decorative from signal-bearing emphasis.

**Held against it.** The direction refuses an unverified percentage threshold, then quietly substitutes an equally unverified count threshold: 'at most one loud device per section.' No source in the research measures how many bolded spans or callouts per section is optimal; the saturation effect is real directionally but unquantified at any granularity, count or percentage.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#one-emphasis-budget-per-section-allocated-by-blast-radius)

#### The serialization check

*✅ survives*

Every document is consumed twice — once as a two-dimensional visual surface, once as a linear stream where bold, position, whitespace, and layout do not exist — and only markup-level structure survives the second reading.

**Why this might actually work.** The Miller-versus-Cowan fight dissolves once you notice the two numbers were measured under different support conditions — Cowan's ~4 holds when rehearsal and external support are absent, which is exactly what the linear channel creates — so 'how many items may this list have' is not a fixed number but a consequence of a formatting decision the author already made; and the accessibility findings are not a compliance annex to a scannability guide, they are the only available test of whether your scannability was structural or merely cosmetic.

**Worked example.** A 'Key points' paragraph whose entire meaning lives in seven bolded fragments serializes into an undifferentiated run-on with nothing marked. A comparison table that reflows to stacked rows on mobile without generated-content labels announces a column of bare values with no header. A 26-item flag list gets skipped in one keystroke; the same content split into four labelled groups with a sentence of prose between them does not.

**Replaces.** Treating accessibility as a post-hoc checklist bolted onto a finished document, and treating list length as a universal number rather than a function of the channel.

**Held against it.** The unifying frame ("every document is consumed twice") quietly bundles three distinct populations and mechanisms — screen-reader users navigating by headings, sighted readers unable to visually re-consult a list, and general WCAG table semantics — as if they were one "linear channel" with one shared threshold, when the evidence for each is measured separately and for different reasons.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#the-serialization-check)

### When a figure or a code sample is the right device

#### The multimedia split

*⚠️ weakened*

An independent research line (Mayer's multimedia principle) shows text+diagram beats text-alone regardless of bullet formatting, so 'add a diagram for structural content' stands on its own evidence rather than waiting on the bullets-vs-prose argument — but the same literature shows a figure that encodes no real structure is a seductive detail that reliably hurts.

**Why this might actually work.** The landscape's central evidentiary problem is that Garner & Alley's RCT confounds bullet-removal with diagram-addition, so nobody knows which did the work. The multimedia-principle literature is a genuinely separate body of research that isolates diagram-addition while holding text format constant, and it converges on the diagram mattering on its own — which means a style guide does not need the deconfounded version of Garner & Alley to exist before recommending diagrams for structural content. The seductive-details finding is arguably the single most robustly replicated result surfaced anywhere in this pass: more consistently replicated than split-attention (which failed to replicate and was killed in round 1), more consistently replicated than the AI-formatting-trust chain (which was never isolated at all).

**Worked example.** A section explaining OAuth token refresh reads as five numbered prose steps describing a request/response cycle with a retry branch. Structural test passes (sequence plus branch): replace with a sequence diagram — client → auth server → resource server, retry branch as a labeled alternate path — plus one sentence stating the assertion it proves: 'A refresh failure triggers exactly one retry with backoff, then surfaces to the caller.' Contrast: a README's 'Why we built this' section carries a hero illustration of a rocket above the first paragraph. Nothing in the prose describes spatial or sequential structure, so the image fails the structural test and is a seductive detail; cutting it is likely to help comprehension of the paragraph beneath it, not merely save bytes. Signaling, applied at the honest effect size: the same sequence diagram renders the critical failure-path arrow at the same weight and color as four success-path arrows. Color or bold only the failure arrow and its label — cheap and evidence-backed. Do not reflexively split it into two panels; the newest pooled evidence for segmenting is no longer distinguishable from zero.

**Replaces.** 'Add a diagram to break up a wall of text' as an undifferentiated formatting move, and its overcorrection, 'diagrams are decoration, cut them to save space.'

**Held against it.** None of the specific evidence this direction leans on — Clark & Mayer's '11 studies, median 89% gain, median d>1,' the 'Guo et al. 2020... g=0.39' re-estimate, the Garner/Brown/Sanders/Menke 1989 seductive-details foundation, or the signaling/segmenting effect-size table (d=0.52, d=0.35-0.38, g=0.24, g=0.32-0.36, g=0.19) — appears anywhere in the provided 8-facet research sweep or the depth-repair round I was given to check against.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#the-multimedia-split)

#### Code answers how; prose answers why, which, and together

*⚠️ weakened*

Robillard's field study of 83 Microsoft developers found code examples become 'more of a hindrance than a resource' precisely when readers need composition, rationale, or best-practice information a snippet was never built to carry — so a snippet is load-bearing for mechanical 'how do I call this' questions and actively frustrating as a substitute for prose.

**Why this might actually work.** The trade-press claim 'developers don't read, they want code' inverts what the field data shows: Robillard found 78% of developers reported learning APIs primarily by reading documentation versus 55% who use code examples — reading was the more commonly reported strategy, not an afterthought. And the richest finding isn't that examples are unwanted, it's that they fail in a specific, diagnosable way: a mismatch between the tacit purpose of the example and the goal of the example user. A style guide can operationalize that mismatch instead of repeating an unsupported folk claim. The real-world cost of code copied without its surrounding context is quantified elsewhere: 69 vulnerable C++ snippets across 1,325 Stack Overflow posts propagated into 2,589 GitHub projects.

**Worked example.** A docs page for a retry-with-backoff client shows only a snippet wrapping a single call in try/catch. Compositional failure predicted: a developer issuing two sequential calls — Robillard's own example, 'you have to close the command before you can issue another command' — hits an exception the snippet gave no way to anticipate. Fix: keep the snippet for the mechanical case, and add one sentence of prose for the constraint the snippet cannot show: 'Only one command may be open on a connection at a time — close it before issuing the next, or the second call raises InvalidOperationException.' That sentence is compositional information no additional code sample would supply.

**Replaces.** 'Show, don't tell — lead with working code, cut the explanation' as an unconditional rule for API and technical documentation.

**Held against it.** None of the direction's supporting citations — Robillard 2009, the 78%/55% reading-vs-example statistic, the C++ Stack-Overflow-to-GitHub vulnerability-propagation study — appear anywhere in research.json or depth_repair.json, the two files constituting the research base for this pass.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#code-answers-how-prose-answers-why-which-and-together)

### Where content lives, and what moving it costs

#### Route it, don't delete it

*⚠️ weakened*

Most verbosity is misplacement, so before cutting a passage decide its destination — main flow, marked footnote/appendix, or a different document entirely — and delete only what has no destination.

**Why this might actually work.** A 10-K separates main-body content from footnote content by a decision test ('would a reasonable reader's decision change if this were omitted'), not a length target — nothing gets silently deleted, it gets addressed; Diataxis supplies the second axis, and together they explain why 'this doc is too long' so often survives a compression pass with the reader no happier: the words were never the problem, the address was.

**Worked example.** Main text: 'Run migrate before restarting — restarting first serves stale config for up to 5 minutes.' (Changes the next action: stays.) Footnote: 'Measured staleness window varies 2-8 min by cache size; see #142.' (True, relevant, doesn't change the action: deferred, not deleted.) Mode case: a 'Configuration reference' section opening with three paragraphs explaining what configuration is and why it matters — not verbose reference prose, it's explanation filed under reference; move it, don't trim it.

**Replaces.** Blanket 'cut qualifiers and background for brevity,' which treats deletion as the only available operation and makes every editing decision lossy by construction.

**Held against it.** The opening claim, 'most verbosity is misplacement,' is not supported by anything in the research and sits in tension with literature this same landscape draws on elsewhere: Zinsser's clutter-elimination, Williams' five concision principles, and Lanham's Paramedic Method are all about words that carry zero information and have no destination anywhere - 'currently' to 'now,' 'in order to' to 'to,' expletive constructions, redundant intensifiers.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#route-it-don-t-delete-it)

#### The context-fit tax: reuse is not free, it's a debt collected at every call site

*⚠️ weakened*

Before promoting a passage into a shared or transcluded unit, run a self-containment test — content that fails it doesn't save words on extraction, it moves the missing words to every call site instead.

**Why this might actually work.** DITA's answer to context-fit is a formal authoring constraint, not an escape hatch: topics must be self-contained because a topic can be assembled into any map or deliverable — so the documented reuse win (edit once, propagate everywhere, lower translation cost, higher consistency) only holds for content that was already context-independent before extraction. Forcing context-dependent content into a shared unit produces the CIDM-documented failure of reducing context in modular documents, trading reader comprehension for reuse-readiness. Heretto names the case directly: a product owner needs goals and trade-offs, a developer needs implementation constraints and edge cases, from the identical source artifact, and both are contextually correct compressions that one reused paragraph cannot be. This generalizes the deletability check from the operation of cutting to the different operation of extracting-to-share.

**Worked example.** Passes: 'Rate limits: 100 req/min' extracted into a shared Limits reference page linked from the SDK guide, the API reference and the admin console guide — a fixed number, identical for every reader; transclude freely. Fails: 'Why we chose eventual consistency here,' transcluded into both a Getting Started doc (first-time integrators need the plain consequence: 'writes may take up to 2s to appear elsewhere') and an Architecture doc (SREs need the trade-off: 'we accept read-after-write staleness to avoid a distributed lock on this path'). The 'why' each audience needs is a different correct compression of the same decision — write it twice; don't transclude it.

**Replaces.** 'Extract anything used twice into a shared doc or snippet' as an unconditional DRY instinct imported from code into prose, with no test for whether the extracted meaning survives arriving in an audience-unknown new home.

**Held against it.** I checked the entire research sweep provided for this pass (research.json, depth_repair.json, ideas.json — 72 findings plus contradictions/unverified/depth sections) for every term this direction cites as its evidentiary base: "DITA," "conref," "Heretto," "CIDM," "Henderson," "ASIST," "context-fit," "single-sourc[ing]" — zero matches anywhere.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#the-context-fit-tax-reuse-is-not-free-it-s-a-debt-collected-at-every-call-site)

#### The link is a leaky pipe: budget cross-references by actuarial class

*⚠️ weakened*

A cross-reference carrying load-bearing information is a bet that the target still exists and still means the same thing later — and that bet's size is measurable and differs enormously by reference class, so route load-bearing facts inline and reserve links for what age can't break.

**Why this might actually work.** Link decay is a documented actuarial curve, not a vague risk, and independent sources converge on its shape while disagreeing on magnitude. Zittrain, Albert & Lessig found over 70% of URLs cited in the Harvard Law Review and 50% in U.S. Supreme Court opinions no longer resolve to the originally cited content. A 20-year LIS citation study found accessibility falling from 87% (citations 0-5 years old) to 38% (10+ years), with permanent rot tripling from 5% to 15%. A CJR crawl of New York Times deep links found the same age shape at different absolute numbers: 6% of 2018-era links dead vs. 43% of 2008 vs. 72% of 1998. Every source agrees on the controlling variable — age, not intent — and none of these are edge cases: they are citation practices in law reviews, Supreme Court opinions and major newspapers, exactly the register a technical guide's 'just link to it' instinct assumes is safe.

**Worked example.** Before (external, load-bearing, unbudgeted): 'Rate limits are documented on our [pricing page](https://vendor.example.com/pricing).' If that page reorganizes in two years the number is gone and the reader has no fallback. After: 'Rate limits: 100 req/min on Free, 1,000 req/min on Pro (see [pricing page] for current tier names).' The number survives the link rotting; the link now carries only the volatile, non-load-bearing part. Internal case: a Configuration doc says 'see Retry Semantics for the timeout default' — safe only if a CI check asserts that the Retry Semantics doc's stated default still matches the code constant. Otherwise the pointer goes stale the moment someone changes the default without touching that doc: referent death with zero URL breakage.

**Replaces.** The unconditional 'avoid duplication, link to the single source of truth instead' applied uniformly regardless of who controls the target — treating an internal same-repo link and a link to a third party's changelog as equivalent-risk citations.

**Held against it.** Like the multimedia direction, none of this direction's core citations — the Zittrain/Albert/Lessig Harvard Law Review Perma figures, the Aslib/Emerald 20-year LIS study, the CJR NYT deep-link crawl — appear anywhere in the provided research sweep; this is evidence introduced outside the project's verified pipeline for a domain explicitly flagged as an open gap.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#the-link-is-a-leaky-pipe-budget-cross-references-by-actuarial-class)

### How any of this actually gets checked

#### Enforcement-tiered rule taxonomy: machine, second reader, real user

*⚠️ weakened*

Organize the guide by how each rule gets checked rather than by topic — tag every rule machine-checkable, review-checkable, or only-testable-with-users, give each tier its actual enforcement plumbing, and demote any rule that fits no tier to 'principle' instead of publishing it as a rule.

**Why this might actually work.** LintMe's comparison shows linters reliably catch structural issues (links, headings, formatting) but need domain models or LLM-semantic evaluation to touch substance at all, and even then a hybrid pipeline beat naive prompting only by combining deterministic operators with targeted semantic checks — no single mechanism covered everything. Bacchelli & Bird found reviewers spend attention on understandability and knowledge transfer rather than systematically hunting subtle judgment calls, so an unlabeled 'review should catch this' quietly becomes 'nobody catches this'; but a separate large-sample study of Java review comments found 42%+ already target understandability, so the lever isn't recruiting new reviewer attention, it's directing attention already being spent toward one specific named question. And Tier 3 exists because Martinez, Mollica & Gibson found 50 years of plain-language mandates produced no measurable decline in processing-difficulty features in US legislation — a mandate with stated compliance and no closed verification loop decays, which is the one failure a guide about enforceability cannot afford to leave unaddressed.

**Worked example.** Guide entry for the pairwise relation test: 'Tier 2 — reviewer question: did you run the swap on every adjacent pair in this list and confirm order-independence? (Y/N, second reader only; CODEOWNERS routes docs/** to the docs owner.)' Entry for table accessibility: 'Tier 1 — CI job `table-a11y-lint` fails the build if any table lacks scope attributes.' Entry for 'does this cut orphan a claim': 'Tier 1 for the referential half (anchor diff against the deletion range); Tier 3 for the informational half — sampled in the quarterly audit.' Q3 audit in practice: five people unfamiliar with the payments-service README are timed running the quickstart; five different people read the ADR justifying Postgres over DynamoDB and are asked to state the one condition under which the decision would reverse. If four of five cannot, the compression rule applied to that rationale section is flagged in the next guide revision — the finding routes to the rule, not just to a one-off doc fix.

**Replaces.** A flat style guide listing rules by topic (bullets, tables, passive voice) with no indication of how or whether any rule is checked; 'a second reader should catch it' with no assigned reader and no record the check ran; and 'Vale is clean' or 'the readability score improved' as evidence the guide is working.

**Held against it.** Two of its four supporting citations — the LintMe paper (arxiv 2603.00331) and 'Understanding Code Understandability Improvements in Code Reviews' (the 42% figure) — do not appear anywhere in the provided research packet and I cannot independently verify them.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#enforcement-tiered-rule-taxonomy-machine-second-reader-real-user)

#### Anchor perishable claims to something that fails the build

*✅ survives*

Co-locating docs with code fixes where documentation lives, not whether it stays true — so tag every factual claim stable or perishable, and write perishable ones so they either execute, get asserted against the source, or never state the volatile value at all.

**Why this might actually work.** The failure isn't that docs get old, it's that stale documentation reads exactly like current documentation — nothing marks which fact was the volatile one, so a reader has no signal to go verify. Practitioners converging from unrelated angles reach nearly the same phrase: pages that end up '80% accurate, which is often worse than 0% accurate,' and static docs feeding an automated system producing 'confidently wrong outputs instead of obvious failures.' That is the MD&A asymmetry at document scale. Executable checks are the only enforcement mechanism in this landscape that doesn't decay when nobody is watching — precisely the property the 2024 corpus study shows a plain-language mandate never had. Separately, the ACL 2021 GEM critique found readability-formula scores can move in the wrong direction relative to genuine simplification, which is new, narrower grounding than round 1's already-killed 'optimize to a Flesch target': gating a pipeline on that score is actively counterproductive, not merely useless.

**Worked example.** Before: 'The default connection timeout is 30 seconds.' A perishable fact, unanchored — six months later a tuning PR changes the default to 10s without touching docs and the sentence is confidently wrong. After (test-anchored): the same sentence plus a CI check comparing it against `DEFAULT_TIMEOUT` in `config.py`, failing the doc build on mismatch. Cheaper alternative (pointer): 'The default connection timeout is set by `DEFAULT_TIMEOUT` in `config.py` (30s at time of writing — check the constant for the current value)' — the number is demoted from an asserted fact to a convenience. Executable: a GitHub Action runs `pytest --doctest-glob='README.md'` so the literal `brew install foo && foo init` block executes on every PR; a renamed CLI flag turns the build red instead of silently misleading readers. Diagram: an ARCHITECTURE.md embeds a PNG showing three services; a fourth was added eight months ago and never redrawn because nothing in the PR process touches image files. Committed as a Mermaid block instead, the next PR adding a fifth service produces a visible diff on the diagram source. The boundary, deliberately not crossed: no Action computes a Flesch score and blocks the merge.

**Replaces.** 'Keep examples up to date' as an unenforced aspiration; the assumption that docs-as-code (same repo, PR-reviewed) is itself a solution to drift rather than a location decision; 'include an architecture diagram' as a one-time deliverable with no maintenance mechanism; and any CI step that fails a PR because a Flesch score crossed a threshold.

**Held against it.** The causal chain the mechanism depends on - things checked by CI stay accurate, things not checked silently rot - is asserted on industry blog posts (Sync-o, DataHub, Falconer, Ben Morris) the direction itself labels 'practitioner consensus only, no controlled study located,' and one supporting citation (Dasanayake et al. 2019) is explicitly excluded as unverifiable.

→ [Mechanism, steelman, and what would disprove it](2026-07-29-scannable-prose-mechanisms.md#anchor-perishable-claims-to-something-that-fails-the-build)

## Tensions & trade-offs

Nine conflicts between surviving directions. Where a genuine distinction exists it is named; where the conflict is irreducible that is said plainly. None is resolved by fiat.

**'One emphasis budget per section, allocated by blast radius' and 'Fractal old-new, with a cold start and a licensed exception'**

*The conflict.* Both claim the job of marking what matters, in incompatible systems. Syntactic stress position is one per sentence, uncapped across a paragraph, and free — every sentence has one whether the author uses it or not. Typographic emphasis is one per section and scarce by design. A bolded mid-sentence clause and that sentence's own stress position claim the same reader attention, and the licensed marked-theme sentence adds a third system competing inside the same section.

*Where it lands.* Partly, by scope. Stress position is the default carrier because it costs nothing; a bold span is reserved for the single claim whose misreading is unrecoverable. Under that split the two rarely collide. The residual is irreducible and it is a real authoring bind: when a section's highest-blast-radius claim arrives mid-sentence, the writer must either bold it (fighting the sentence's own stress position and spending the section's one loud device on a fragment) or restructure so the claim lands in stress position — which may itself violate old-new, since the claim is new information.

**'One emphasis budget per section' and 'The serialization check'**

*The conflict.* The budget is spent on bold spans, callouts and admonitions — precisely the devices that do not exist in the linear channel — so the emphasis it carefully concentrates reaches only part of the readership.

*Where it lands.* Mostly resolvable, and the resolution already sits inside the serialization check: visual emphasis must be redundant with words, never the sole carrier. If the bolded span is itself a lexically complete statement ('Requests without an API key are rejected outright'), nothing is lost when the bold disappears. It becomes irreducible for devices whose meaning lives in the container rather than the words — a warning callout whose only severity signal is the box type, an emoji standing in for urgency.

**'The multimedia split' and 'One emphasis budget per section' / 'The serialization check'**

*The conflict.* A diagram is a loud device and a visually-carried structure at once. Nothing says whether a section gets one loud device total across channels or one per channel, and a diagram rendered as image or SVG is exactly the structure the serialization check warns vanishes in the linear read.

*Where it lands.* Irreducible on the budget question. No evidence exists on cross-channel attention competition, and what a writer actually faces is a section containing both a sequence diagram and a bolded failure warning — two attention magnets, no principle for which wins, and a real possibility that the diagram makes the bold span redundant or vice versa.

**'Redundancy debt, triggered by structural distance' and 'The hunk test for changelogs and PR descriptions'**

*The conflict.* The genre gate classifies changelogs as narrative (Delgado g=0.01, no measured screen deficit) and therefore withholds backward-linking restatement from them; the hunk test requires a prior-state anchor on every line.

*Where it lands.* Resolvable, and the two are right about different objects. Delgado's g=0.01 concerns comprehension of continuous narrative text read on screen — a reading-mode finding about running prose. A changelog line is not read as running narrative; it is consumed as a standalone fragment by someone who does not hold the prior state and has no surrounding text to reconstruct it from. So the genre gate should govern cross-paragraph continuity repair inside running prose, and the hunk test should govern the interpretability of a standalone entry.

**'Two compression budgets, tagged at the clause' (pinning) and 'Route it, don't delete it'**

*The conflict.* Pinning requires a truth-changing clause to stay in the same visual unit as the step or claim it modifies; routing moves material that does not change the reader's next action out of the main flow into a footnote or appendix.

*Where it lands.* For clause-length material the two tests agree and the conflict is illusory: a truth-changing modifier changes the next action, so routing's own materiality test keeps it inline. The conflict is real and irreducible only in the long case — a paragraph of safety rationale hanging off one step, too long to inline without wrecking the procedure and too load-bearing to footnote without orphaning it. What a writer faces there is a choice between a bloated quick-start and a caveat in a place many readers will not open, and this landscape has no third option.

**'Route it, don't delete it', 'The link is a leaky pipe', and 'The context-fit tax'**

*The conflict.* All three govern where content lives and default in different directions. Routing sends non-decisive material to a footnote, appendix, or another document. The leaky pipe says any load-bearing fact placed behind a boundary a link checker doesn't cover decays at a measured, compounding rate. Context-fit says content whose correct compression is audience-dependent should be duplicated rather than extracted into one shared unit — the opposite instinct from both.

*Where it lands.* Largely resolvable by partitioning on what the material is. Routing is right about material that is true and relevant but does not change the reader's next action. The leaky pipe is right about material that does change it — that never goes behind an unchecked reference, whatever the length pressure. Context-fit is right about material whose correct form differs by audience, where a single shared version is wrong for everyone.

**'Redundancy debt, triggered by structural distance' and 'The context-fit tax'**

*The conflict.* The heading-crossing trigger makes sections survivable in isolation by restating; the context-fit tax prices duplication as debt that must be tracked and silently drifts when it isn't. Self-containment across sections is duplication under another name.

*Where it lands.* Partly. The entity-distance ceiling and the reference/how-to scoping are the throttle: restatement is licensed as one short orienting clause or a real link, never a re-explanation, and only where a reader plausibly lost the thread. Applied without that throttle, self-containment becomes an argument for restating the glossary at the top of every section.

**'The pairwise relation test' / 'The table as a completeness proof' and 'The serialization check'**

*The conflict.* The pairwise test routes crossed pairs into scoped grids, and a mixed passage into a prose gate plus a grid in two different places. Grids are the artifact most likely to lose header association on reflow or linear read-out, and nothing in this landscape specifies how to lay out an interleaved prose-gate-plus-scoped-grid without the layout itself becoming a new scannability problem.

*Where it lands.* Not resolvable with what is here, and this is the sharpest remaining structural conflict. The completeness proof's guarantee — you can count the rows and see a gap — exists only in the visual channel; serialized, a grid becomes a sequence of values whose header association must be restored by markup the completeness check itself does not require.

**'Enforcement-tiered rule taxonomy' and 'Anchor perishable claims to something that fails the build'**

*The conflict.* One is agnostic about where the machine/review line sits and cares only that every rule declares which side it is on; the other actively spends engineering effort moving checks into CI. Both then compete with the taxonomy's own Tier 3 audit for the same finite organizational attention.

*Where it lands.* The technical half is resolvable — anything phraseable as a runnable assertion belongs in CI, and the disagreement is about budget, not principle. The attention half is irreducible and it is the thing a team actually faces: review cycles spent answering Tier 2 checklist questions are cycles not spent on the functional defect-hunting code review already under-delivers on, and quarterly user testing is the first thing deadline pressure cuts because it is the only tier with no red X when skipped.

## Challenge notes

Every direction was steelmanned, attacked, and given a falsification test. **The falsification tests are the most portable thing here** — each names a concrete observation that would show the direction is wrong, which is what separates a style rule from a preference.

Full steelman and counter for each: [the companion file](2026-07-29-scannable-prose-mechanisms.md).

**Two compression budgets, tagged at the clause** — ⚠️ weakened  
*Would be disproven if:* Give the same passage to two independent reviewers and have them apply the clause-tagging test (finite clause, PROCEDURAL vs EXPLANATORY, marker-forced override) independently. If they disagree on tags for a nontrivial share of clauses in ordinary technical prose (not the cherry-picked worked example), the "reviewer test" doesn't converge and the rule is unenforceable as stated. Separately: if a study (or even a structured internal test) found that Requires/If-skipped annotations added to every dependent step caused readers to skip past them at the same or higher rate as the bare numbered list the direction replaces — the alarm-fatigue risk the direction itself names — the core claimed benefit would be falsified, not just weakened.

**What a cut is allowed to touch: operation class first, then dependency checks** — ⚠️ weakened  
*Would be disproven if:* Have two independent editors classify a batch of real diffs into word/claim/qualifier-level using only the definitions given, with no discussion; if agreement falls much below roughly 70%, the taxonomy isn't doing the classification work it claims to do, and 'classify the operation first' collapses into 'argue about the classification' before any check can even begin.

**The hunk test for changelogs and PR descriptions** — ⚠️ weakened  
*Would be disproven if:* Sample real CHANGELOG.md files from a set of popular OSS projects and classify entries as 'modifies existing behavior' vs 'pure addition with no prior state.' If pure-addition entries are a large fraction (say >40%), the hunk framing fails as a general mechanism and needs to be rescoped to modification-only entries. Separately, a reader test — hand engineers unfamiliar with a codebase changelog lines written with vs. without the prior-state clause and ask them to judge 'does this affect me' — that shows no accuracy difference would undercut the claimed payoff directly.

**The pairwise relation test: chained-in-time vs. crossed-in-state** — ⚠️ weakened  
*Would be disproven if:* Construct or find a real passage containing a pair that passes both tests at once: swapping it changes a concrete truth-or-action outcome (chained) AND the pair's values combine independently of discovery order (crossed). If such a pair exists, the dichotomy doesn't partition cleanly. Separately: give the 'disputed pair' worked example, or an equally ambiguous real one, to five independent reviewers applying only the tie-break test; if they don't converge, the tie-break relocates disagreement rather than resolving it.

**The table as a completeness proof, with escape hatches** — ⚠️ weakened  
*Would be disproven if:* Audit a sample of real READMEs, ADRs, guides, and PR descriptions for how often two or more independent orthogonal conditions actually determine a stated outcome (the trigger condition). If that pattern is rare in the target genres — as opposed to common in formal specs — this direction addresses a corner case dressed as a general prose-cutting principle. Separately: have writers under real deadline pressure apply the impossible/unspecified test and check whether they actually chase down a citable invariant before marking a cell IMPOSSIBLE, or default to marking it on intuition (as failure-mode predicts); a high rate of uncited IMPOSSIBLE markings would show the safeguard has no teeth without tooling.

**Fractal old-new, with a cold start and a licensed exception** — ⚠️ weakened  
*Would be disproven if:* Run a comprehension or takeaway-recall test where one arm opens documents with a title-noun-echoing, competitor-differentiating first sentence and the other opens with a generic capability statement; if readers extract the same core point at the same rate regardless of opening style, the swap-test recommendation loses the grounding it currently only asserts by analogy.

**Redundancy debt, triggered by structural distance** — ✅ survives  
*Would be disproven if:* A reading-comprehension or eye-tracking study on technical prose (not digit-span tasks) showing readers reliably track referents across meaningfully more than ~4 intervening named concepts without misreading would undercut the specific numeric trigger. Separately, server-log or analytics data from an actual technical-docs site showing search-referral share for reference/how-to pages is not meaningfully higher than for tutorial pages would undercut the differential arrival-mode scoping that is this version's main addition over the retired one.

**One emphasis budget per section, allocated by blast radius** — ⚠️ weakened  
*Would be disproven if:* Find or construct a real section containing two genuinely independent irreversible/security/binding facts (not two aspects of one fact) where bolding only one, per the cap, left readers measurably worse-informed about the other relative to a version bolding both.

**The serialization check** — ✅ survives  
*Would be disproven if:* Run the same document through both a sighted visual-scan test and a screen-reader/TTS linearized read. If documents that pass the serialization check (clean heading outline, no meaning carried only by bold/color, short unaided lists) show no measurable improvement for the sighted-scanning majority over documents that fail it — i.e., visual scanners do equally well regardless — that would show the check is a necessary accessibility requirement running in parallel, not, as claimed, the definitive test of whether scannability is "structural or cosmetic" for readers generally.

**The multimedia split** — ⚠️ weakened  
*Would be disproven if:* Pull the actual Clark & Mayer (2016) Cambridge Handbook chapter and the specific 'Guo et al. 2020' meta-analysis and confirm whether the '89% / d>1' and 'g=0.39' figures are accurately transcribed and attributed; if they can't be located or don't match, the numbers carry false precision even if the general effect they describe turns out to be real.

**Code answers how; prose answers why, which, and together** — ⚠️ weakened  
*Would be disproven if:* Locating and directly reading the actual Robillard 2009 text to confirm or correct the 78%/55% and 50-of-74 figures would resolve the immediate verifiability gap. A modern (post-2020) large-sample replication of the obstacle taxonomy — especially one accounting for LLM-assisted composition and inline-hover documentation, which didn't exist in 2009 — finding that 'compositional' and 'rationale' failures are now materially rarer would undercut using this specific taxonomy as a current-day baseline.

**Route it, don't delete it** — ⚠️ weakened  
*Would be disproven if:* Take a set of real edited drafts (before/after) and classify each cut as either relocatable content that changed address, or content with no possible destination that was simply excised. If the large majority of effective cuts fall into the latter, as the Zinsser/Williams/Lanham material implies, 'most verbosity is misplacement' is empirically false even though the routing test remains valid for the minority it targets.

**The context-fit tax: reuse is not free, it's a debt collected at every call site** — ⚠️ weakened  
*Would be disproven if:* Locate and verify the primary sources actually claimed (the DITA/conref authoring literature, the CIDM 2010 paper, Heretto's stated example, Henderson 2011 in ASIST) against their original text; if they say what's claimed, confidence should rise substantially and this concern dissolves. Absent that, a controlled comparison — shared/transcluded audience-spanning prose vs. duplicated-and-independently-maintained versions, measured on post-edit correctness or reader comprehension — showing reuse performs as well as duplication even for context-dependent content would directly undercut the core claim.

**The link is a leaky pipe: budget cross-references by actuarial class** — ⚠️ weakened  
*Would be disproven if:* Audit same-repo cross-references in a real docs-as-code corpus (e.g., sampling 'see X section' pointers against the git history of both endpoints) to see how often referent-death actually occurs uncaught; if it's rare because ordinary PR review already catches most of it, the alarm this direction raises about internal links specifically is undercut, leaving only the external-link half (which at least has real, if genre-mismatched, backing).

**Enforcement-tiered rule taxonomy: machine, second reader, real user** — ⚠️ weakened  
*Would be disproven if:* Track a team that adopts this three-tier structure for two or three quarterly cycles; if Tier 3 audits are skipped every time (no outside readers ever recruited) while Tier 1/Tier 2 checklist items proliferate, that would confirm the taxonomy doesn't prevent the decay it names as its reason for existing — it just relocates where the decay happens. Locating the actual LintMe paper and Bacchelli & Bird's original text and checking whether the 42%-understandability figure and the review-value framing are accurately represented would validate or undercut the Tier 1/Tier 2 boundary as currently drawn.

**Anchor perishable claims to something that fails the build** — ✅ survives  
*Would be disproven if:* Find teams or repositories that adopted pytest-doctest-glob, link-checking, or diagrams-as-code and measure whether their documentation's actual error/staleness rate over 6-12 months is lower than comparable teams without these mechanisms - versus finding the enforcement mechanisms themselves get disabled or narrowed at a rate that erases the advantage.

## Open questions & gaps

- Readers beyond the default — explicitly deferred by the user and still entirely unaddressed. Non-native English speakers, translation and localization, and readers with cognitive disabilities beyond list length. 'The serialization check' covers the screen-reader channel and nothing else.
- Voice, tone and register — second person, contractions, 'write like you speak,' humor, and the objective-language third of NN/g's 124% usability result. Deliberately out of scope for a verbosity guide, but it is one of the three manipulated variables in the study this landscape leans on most, which means the 124% figure cannot be attributed to scannability and concision alone by anything here.
- Typographic and layout parameters — line length 45-75 characters, paragraph length 40-70 words, whitespace, font. These appear in the research as high-confidence findings and no direction governs them. Partly deliberate (they are rendering-environment properties, not authoring decisions, in Markdown-based READMEs and PRs) but a style guide will be asked about them and currently has no answer.
- The clean bullets-vs-connected-prose RCT on causal content still does not exist, and nothing in round 2 changed that. The multimedia literature answers a related but distinct question (does adding a diagram help, holding text format constant), which is why 'The multimedia split' goes around Garner & Alley rather than through it. The pairwise relation test remains a precautionary rule built on convergence, and the guide should say so rather than imply a settled result.
- No compression dose-response curve exists, in either round. Every compression direction here is structural (what class, what operation, what pin) precisely because no numeric threshold is available; if a reader asks 'how much can I cut,' the honest answer is still 'no study answers that.'
- How to typeset the output of the pairwise relation test on mixed content — an interleaved prose gate plus a scoped grid — without the layout itself becoming a new scannability problem. Round 2 flagged this and did not solve it; it sits at the unaddressed boundary between the logical-structure directions, 'The serialization check,' and 'Route it, don't delete it.'
- Reader perception of AI-authored prose. The depth round confirms the causal chain (formatting density → inferred AI authorship → trust penalty) has never been isolated in any controlled experiment, while the AI-disclosure/label penalty is real (n=556, Cohen's h=0.28; 13-experiment and 16-study replications) and processing-fluency research predicts easier-to-process text is judged MORE credible.
- No evidence exists on internal, same-repo link or referent decay rates. Every actuarial figure in 'The link is a leaky pipe' comes from public-web, legal-citation or academic-citation studies; applying them inside a tooled doc-set is extrapolation, flagged but unresolved.
- No study measures README/ADR/PR entry-point distribution — browse vs. deep-link vs. search — for technical documentation specifically. The 14% search-first figure scoping 'Redundancy debt' is averaged across general commercial and retail sites, and developer docs plausibly sit well above it.
- How duplicated technical prose actually diverges over time. Henderson (2011, ASIST) states the question has not been studied. Both 'Redundancy debt' and 'The context-fit tax' deliberately license duplication, and neither can price its maintenance cost.
- Documents genuinely serving two audiences with conflicting natural sequences (end user vs. contributor). Surfaced when 'Decision-sequence ordering' was killed and never resolved: the honest fix is probably two documents, but nothing here supplies a method for detecting the fork, and 'Route it, don't delete it' assumes a mode label exists that in practice is contested.
- Whether the sentence is the right unit of compression. 'Two compression budgets' argues for the clause as the tagging unit and 'What a cut is allowed to touch' argues the claim/qualifier distinction cuts across sentence boundaries either way — neither resolves the underlying question, and clause boundaries themselves are conceded to be fuzzy under multiple subordination.
- What 'information preserved' means relative to a reader's prior knowledge. The informational check's forcing question ('what changes for the reader's next decision') is a proxy for reader-relative value, not an operational account of prior-knowledge-relative information — which would need grounding this research sweep does not supply, and which is what the materiality test's reader-relativity problem ultimately reduces to.
- Bateman et al.'s 'Useful Junk' finding (visual embellishment increased long-term memorability of some charts) sits in genuine tension with the seductive-details literature underlying 'The multimedia split.' The two test different things — one-off data-communication charts vs. instructional material — and a complete guide should eventually reconcile them rather than treating seductive-details as a universal veto on visual distinctiveness.
- Composition. No study anywhere in the corpus applies more than one of these rules together and measures the result, so every interaction effect in this landscape — and there are at least nine documented conflicts — is reasoned rather than observed. A team adopting the whole guide is running an untested combination, and the quarterly Tier 3 audit is the only mechanism here that would ever notice.
## Sources

Eighty-two sourced claims came out of the sweep. These are the ones the landscape actually leans on.

**Scanning and reading behavior**
- How users read on the web (79% scan / 16% word-by-word) — [nngroup.com](https://www.nngroup.com/articles/how-users-read-on-the-web/)
- How little users read (~20% of a page; Weinreich et al. 2008, 59,573 page views) — [nngroup.com](https://www.nngroup.com/articles/how-little-do-users-read/)
- F-pattern as a default under weak formatting cues — [nngroup.com](https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/)
- No consistent letter-shaped scan pattern across 99 sites — [eyequant.com](https://www.eyequant.com/resources/eye-tracking-studies-does-the-famous-f-shape-pattern-really-exist)
- Layer-cake scanning depends on strong subheads — [nngroup.com](https://www.nngroup.com/articles/layer-cake-pattern-scanning/)
- First two words carry link and heading scanning — [nngroup.com](https://www.nngroup.com/articles/first-2-words-a-signal-for-scanning/)
- Concise + scannable + objective: 124% usability (task time, errors, recall, satisfaction — not credibility) — [nngroup.com](https://www.nngroup.com/articles/concise-scannable-and-objective-how-to-write-for-the-web/)
- Screen reading-speed penalty now 6–10%, not 25% — [nngroup.com](https://www.nngroup.com/articles/ipad-and-kindle-reading-speeds/)
- Inverted pyramid for web writing — [nngroup.com](https://www.nngroup.com/articles/inverted-pyramid/)

**Comprehension, cognitive load, and compression**
- Delgado et al. 2018 meta-analysis: screen vs paper, g = −0.27 expository / g = 0.01 narrative (54 studies, 170k+ participants) — [researchgate.net](https://www.researchgate.net/publication/330854760)
- Mayer's coherence (23/23 tests, median d = 0.86) and redundancy (d = 0.87) principles — [cambridge.org](https://www.cambridge.org/core/books/abs/cambridge-handbook-of-multimedia-learning/principles-for-reducing-extraneous-processing-in-multimedia-learning-coherence-signaling-redundancy-spatial-contiguit)
- Split-attention effect fails to replicate under direct cognitive-load measurement (Schroeder & Cenkci 2019) — [springer.com](https://link.springer.com/article/10.1007/s10648-019-09465-5)
- Cowan's ~4-chunk revision to Miller's 7±2 — [journalofcognition.org](https://journalofcognition.org/articles/10.5334/joc.387)
- Cognitive load theory: intrinsic / extraneous / germane — [ncbi.nlm.nih.gov](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5696680/)
- LLM text simplification RCT, n=4,563: legal +3.5% vs PubMed +14.6% — [arxiv.org](https://arxiv.org/abs/2505.01980)
- Faithfulness in abstractive summarization: >70% hallucination at extreme compression (Maynez et al. 2020) — [aclanthology.org](https://aclanthology.org/2020.acl-main.173.pdf)
- Information fidelity in LLM-compressed financial analysis: context share 25% → 9% — [arxiv.org](https://arxiv.org/pdf/2606.29251)
- ERP evidence of weaker semantic encoding after digital reading — [ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC11111009/)

**Structure: bullets, tables, connectives**
- Garner & Alley 2013, assertion-evidence vs bulleted slides (n=110, d = 0.47–0.89) — [writing.engr.psu.edu](https://writing.engr.psu.edu/ae_comprehension.pdf)
- Millis, Golding & Barker 1995: causal connectives increase inference generation — [tandfonline.com](https://www.tandfonline.com/doi)
- Connectives reduce processing cost for causal and contrastive relations — [tandfonline.com](https://www.tandfonline.com/doi/full/10.1080/0163853X.2019.1605257)
- Jansen, five studies: bullets help item recall, hurt surrounding-prose recall — [jbe-platform.com](https://www.jbe-platform.com/content/journals/10.1075/idj.21.2.06jan)
- Kozak & Hartley 2011, bullet points in conclusions — [journals.sagepub.com](https://journals.sagepub.com/doi/abs/10.1177/0165551511399333)
- Tufte on the Columbia slide and the cognitive style of PowerPoint — [edwardtufte.com](https://www.edwardtufte.com/notebook/columbia-accident-investigation-board-the-boeing-powerpoint-slide/)
- Parnas-style tabular expressions: completeness and consistency — [researchgate.net](https://www.researchgate.net/publication/228939082_Tabular_Expressions_in_Software_Engineering)
- Google developer documentation style guide: tables — [developers.google.com](https://developers.google.com/style/tables)
- Microsoft Writing Style Guide: scannable content, tables — [learn.microsoft.com](https://learn.microsoft.com/en-us/style-guide/scannable-content/tables)
- NN/g on presenting bulleted lists — [nngroup.com](https://www.nngroup.com/articles/presenting-bulleted-lists/)

**Sentence-level craft**
- Gopen & Swan, The Science of Scientific Writing (topic/stress position) — [usenix.org](https://www.usenix.org/sites/default/files/gopen_and_swan_science_of_scientific_writing.pdf)
- Pullum on passive-voice loathing and misidentification — [lel.ed.ac.uk](https://www.lel.ed.ac.uk/~gpullum/passive_loathing.pdf)
- Pullum, "50 Years of Stupid Grammar Advice" — [chronicle.com](https://www.chronicle.com/article/50-years-of-stupid-grammar-advice/)
- Lanham's Paramedic Method — [owl.purdue.edu](https://owl.purdue.edu/owl/general_writing/academic_writing/paramedic_method.html)
- Function words: ~150 types, ~50% of text, 44% of readability variance — [tandfonline.com](https://www.tandfonline.com/doi/full/10.1080/10888438.2024.2422365)
- Garden-path sentences from over-deletion of relative pronouns — [effectiviology.com](https://effectiviology.com/avoid-garden-path-sentences-in-your-writing/)
- Diátaxis: why mixing documentation modes hurts — [diataxis.fr](https://diataxis.fr/)
- Google developer documentation style guide highlights — [developers.google.com](https://developers.google.com/style/highlights)

**Plain language and readability formulas**
- Federal Plain Writing Act of 2010 — [justice.gov](https://www.justice.gov/open/plain-writing-act)
- Why readability formulas fail — [academia.edu](https://www.academia.edu/47932647/Why_readability_formulas_fail)
- DuBay, The Principles of Readability — [researchgate.net](https://www.researchgate.net/publication/228965813_The_Principles_of_Readability)
- Plain-language rewrites: comprehension 23% → 70% on California court forms — [associatesmind.com](https://associatesmind.com/2013/02/12/judges-overwhelmingly-prefer-plain-language-with-some-caveats/)
- Martinez, Mollica & Gibson 2024: 50 years of mandates, no measurable decline in difficulty features — [tedlab.mit.edu](http://tedlab.mit.edu/tedlab_website/researchpapers/martinez_mollica_gibson_2024.pdf)

**Accessibility and the linear channel**
- WebAIM 2024: 71.6% of screen-reader users navigate by headings — [medium.com](https://medium.com/@colleengratzer/key-findings-from-the-webaim-2024-screen-reader-user-survey-bb15864d3bc8)
- Responsive tables lose semantics on CSS reflow (Roselli) — [adrianroselli.com](https://adrianroselli.com/2017/11/a-responsive-accessible-table.html)
- WCAG table requirements: th, scope, caption — [accessibility.psu.edu](https://accessibility.psu.edu/tableshtml/)
- Emoji as information carriers and screen readers — [boia.org](https://www.boia.org/blog/emojis-and-web-accessibility-best-practices)
- Long lists trigger skip behavior in screen readers — [boia.org](https://www.boia.org/blog/do-bullet-points-help-with-accessibility)

**Formatting, AI authorship, and trust**
- Alter & Oppenheimer 2009, "Uniting the Tribes of Fluency" — fluent text is judged *more* true — [journals.sagepub.com](https://journals.sagepub.com/doi/10.1177/1088868309341564)
- AI-disclosure penalty across 13 experiments (Schilke & Reimann) — [sciencedirect.com](https://www.sciencedirect.com/science/article/pii/S0749597825000172)
- Human-label preference: +13.7pp, Cohen's h = 0.28 (n=556) — [arxiv.org](https://arxiv.org/html/2510.08831v1)
- Disclosure penalty magnitude <0.15 on a 7-point scale (n=1,970) — [arxiv.org](https://arxiv.org/html/2507.01418v1)
- Vocabulary shift in 14M PubMed abstracts ("delve" +1,375%) — [science.org](https://www.science.org/doi/10.1126/sciadv.adt3813)
- Em-dash persistence under formatting suppression; human range 0.33–17.12 per 1,000 words — [arxiv.org](https://arxiv.org/html/2603.27006v1)
- Wikipedia, "Signs of AI writing" — the strongest institutional response found — [wikipedia.org](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
- AI-detector false positives, including 61% of non-native-English writing — [ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC12331776/)

### Marked unverified

Claims that circulate widely and could not be traced to a primary source. **None of them is load-bearing in this document**, and any style guide drawing on this material should treat them as folklore until sourced:

- The "30% bold maximum" threshold — appears in NN/g's formatting article without a cited study
- "Users read 25% faster with bullet points" — a 2022 source measures "21% higher skimmability," a different metric
- "Bold text allows 30% faster scanning"
- The James Mattis "PowerPoint makes us stupid" quote — attribution differs across sources; original not located
- Tufte's "relentless sequentiality" — appears in secondary discussion, not located in his published writing
- Helen Sword's zombie-noun studies — widely cited; sample sizes, controls, and effect sizes not accessible
- Shannon's 50–75% English redundancy estimate — no primary retrieved
- Lin 1999's 15–30% optimal compression band — paper is real, figure not confirmed in primary text
- Carroll's IBM minimalism task-time figures — consistently described in secondary literature, primary not retrieved
- Bullet points triggering dopamine via the Zeigarnik effect — no peer-reviewed source found
- "Incorrect documentation is worse than missing documentation" — Write the Docs community axiom, no empirical study found

---

*Exploration only. To build a direction: invoke `quirk:brainstorming` → an execution skill (which authors a tech spec when warranted, then plans in context).*
