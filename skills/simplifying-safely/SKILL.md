---
name: simplifying-safely
description: Use when asked to simplify, clean up, or refactor code; when asked to review a diff, PR, or draft for over-engineered additions; or when authoring or editing a spec, a CLAUDE.md, a skill file, or other agent-facing document. Notices when an agent is over-producing. Where a correctness check exists — in practice, code — no simplification ships until it is re-validated against that check; elsewhere the call stays with human judgment rather than passing to a simplicity signal.
---

# Simplifying Safely

## Overview

Find concrete ways to reduce avoidable burden without silently weakening what the artifact must accomplish. Use evidence to bound claims, not to avoid making useful proposals. `D1` and `D2` are the two operational detection tests; the workflow and transformation prompts below are design judgments, not validated detectors of over-engineering.

For code, sequence changes after a correctness baseline and apply the same post-change check to additions and deletions (`G1`–`G3`). For documents and conversation, propose or perform authorized edits as editorial judgments; no simplicity score substitutes for a correctness check (`G4`). Keep the evidence tags attached to the rules: `grounded` marks limits on what can be claimed, `precautionary` marks evidence with transfer gaps, and `judgment` marks a defensible choice rather than a measured result.

**The honest claim.** This skill shifts an agent's starting verbosity and complexity downward. It does not change how fast quality erodes across a long session — expect drift to resume on anything long-running, and don't rely on this skill alone to hold the line. No countermeasure here is validated against that drift either (`M4`).

**Supersedes** `applying-simplicity-principles`, installed outside this repo at `~/.claude/skills/`. That skill is always-proactive, carries no evidence tags or blocklist, and asserts guidance this skill's research contradicts. Leaving both installed means two competing simplicity skills firing on the same prompt — one of them always-on no matter what's being worked on. Uninstall it.

## When to Use

- Asked to simplify, clean up, refactor, or trim something down.
- Reviewing a diff, PR, or draft and judging whether an addition is over-engineered or speculative.
- Editing a CLAUDE.md, skill file, or other agent-facing document.
- Authoring or reviewing a logic spec or tech spec.
- A reply you're about to send has come out longer or more hedged than the question needed.

**Not for:** prose mechanics — sentence length, headings, scannability (`quirk:writing-scannable-prose` owns those); a theory of *why* simplicity matters; picking a numeric threshold for anything.

## Workflow

This proposal-generating method is **judgment**, not an evidenced correctness gate.

1. **Identify the obligation.** Use the request, artifact and available context to identify its consumers, decisions, behavior and required constraints. Do not create a separate requirements document just to perform this review.
2. **Find avoidable burden.** Inspect repeated sources of truth, unnecessary indirection, speculative commitments and answers scattered across locations. Apply the relevant surface guidance even when `D1`/`D2` or `S1`/`S2` find nothing.
3. **Propose a concrete transformation.** Name what to merge, move, replace or remove and the observed burden it addresses. Use the transformation prompts below; do not stop at “looks complex.”
4. **Account for obligations.** Identify unique qualifications before consolidating. Distinguish reorganizing a requirement from changing it. If the source contradicts itself and context does not establish authority, surface the policy choice rather than silently selecting a version.
5. **Act within authorization and verify.** A review request calls for proposals; an editing request authorizes restructuring within the stated contract, not silent scope changes. For code, use `G1`–`G3`. For documents, inspect the actual revision for lost obligations and broken references, but report that as editorial review, not correctness certification. Clarify substantive choices only when available context cannot resolve them.

For each substantial recommendation, report **where → observed burden → proposed change → what must survive → tradeoff**. Keep this proportional to the task; no score, proposal quota or obligatory report file. After inspecting the artifact, “no useful change found” is valid. “No S1/S2 finding” alone does not establish it.

### Transformation prompts

These are **judgment-based candidates**, not automatic cut rules:

| Inspect for | Candidate transformation | Preserve or check |
|---|---|---|
| Independently maintained statements of one requirement | Give it one authoritative home; summarize or link elsewhere | Unique qualifications and useful local summaries. Document duplication is not a `D1` code verdict. |
| Current requirements interleaved with research or review history | Separate the current contract from supporting material | Rationale needed to understand decisions and required provenance. |
| Implementation choices mixed into a behavioral spec | Move mechanism-level choices to the implementation design | Choices constraining behavior, safety, compatibility, ownership or delivery remain explicit. |
| Abstractions, options or stages without a present need for their distinctions | Propose a direct path for the current consumers | Real variation, ownership boundaries and failure handling; code changes still face the correctness gate. |
| A cut that makes the reader reconstruct an answer elsewhere | Keep or consolidate the answer instead | Findability, operational completeness and the maintained source of truth. |

Separating material does not automatically require another file. Prefer an existing maintained destination or a distinct section; name the destination before moving anything. Moving complexity out of sight is not removing it. Wording and scannability remain with `quirk:writing-scannable-prose`.

## Always-on core

Applies every time this skill fires, regardless of which surface is in play. Each row's tag is an evidence level: `grounded` (evidence directly supports it in a setting that transfers), `precautionary` (evidence exists but doesn't fully transfer to this setting), `judgment` (a defensible design call, not a measured result). A tag ending in diagnosis marks a rule that names what to flag for a human rather than a check this skill adjudicates.

| ID | Rule | Tag |
|---|---|---|
| G1 | Sequence any step that shrinks, simplifies, deletes, or otherwise minimizes code strictly after a correctness check, and re-run that check against the result before treating the step as done. A simplification that hasn't been re-validated isn't finished, however small or clean it looks. | precautionary |
| G2 | Apply the identical correctness re-check to additions and deletions alike. Neither direction carries a special burden — growing the code and shrinking it both stand or fall on the same post-change check. | judgment |
| G3 | No simplicity signal may block, accept, or reject a change — only the correctness re-check may do that on this skill's authority. A signal (shorter, fewer files, fewer branches) may inform which passing candidate to prefer, but it never decides pass or fail by itself. This bounds what *simplicity* can decide; it does not displace a user instruction or a correctness skill (`M2`), and off code, where no such check exists, the decision goes to human judgment rather than to a simplicity signal (`G4`, `D3`). This bounds the fix gate, not detection: `D1` and `D2` still yield their verdicts, which is what makes them the two tests. | precautionary |
| G4 | For every surface but code — specs, agent-facing docs, human-facing docs, and conversational output — no evidenced check plays the role a test suite plays for code. State that once, here; don't invent a substitute (a doc linter, a length cap, a self-rated clarity or simplicity score) to stand in for one that doesn't exist. | grounded |
| D1 | For duplicated code, ask whether the two regions would need to change together to stay correct — not whether the text looks similar. Duplication forced by a shared requirement is worth flagging; duplication between deliberately independent regions is often fine on its own. | precautionary |
| D2 | Before keeping or cutting a standing rule, don't decide by imagining what would happen without it. Remove it, run the cases it exists to govern, and observe. Keep it only if the mistake it targets reappears; cut it if the task still goes fine. | judgment |
| D3 | Outside `D1` and `D2`, there's no review-time check for over-engineering. The only clean definition is retrospective — complexity is over-engineering only if it anticipated a requirement that never arrived. For every other surface, name what looks speculative and say why, as a flagged judgment call for a human, not a verdict this skill can render. | grounded · diagnosis |

`D2` is executed, never predicted: deciding by imagining the counterfactual is the exact unaided judgment this skill exists to replace. Actually remove the candidate rule, run the cases it guards, and observe — a rule you didn't actually remove hasn't cleared the test, whatever the imagined outcome. The harness for doing this is untested at affordable sample sizes; treat an unresolved `D2` as unadjudicated, not as passed.

## Surface routing

The core above applies every firing. On top of it, load only the tier(s) for what's actually in play:

| Working on | Load |
|---|---|
| Code — writing, editing, or reviewing it | Code (`C1`–`C6`) |
| A CLAUDE.md, skill file, or other agent-facing doc | Standing documents (`H1`–`H4`) + Agent-facing docs (`A1`–`A4`) |
| A logic spec or tech spec | Standing documents (`H1`–`H4`) + Specs (`S1`–`S3`) |
| A README, guide, ADR, or other standing document for humans | Standing documents (`H1`–`H4`) |
| Your own reply to the user | Conversational output (`V1`–`V2`) |

A task can span more than one surface — implementing a spec'd change touches both code and the spec that authorized it — and loads both groups; nothing caps how many stack. Keep the loaded set to what's actually in play rather than reading every tier on every task: instruction-following degrades as simultaneous constraints accumulate, which is why the core stays small and each surface's group stays separate instead of merging into one long list.

The `M1`–`M6` group below isn't tied to a surface — it governs this skill's own precedence, honesty, and conduct, and applies whenever the skill fires.

## Code

| ID | Rule | Tag |
|---|---|---|
| C1 | Judge these signals at the level of the diff or the whole change, never a single function in isolation — a function can look lean while the surrounding change adds files, layers, or options that add up to over-production. | precautionary · diagnosis |
| C2 | A new config flag, environment variable, settings option, or dependency introduced without the task calling for it is a signal, not a default good practice. | precautionary |
| C3 | A new function, class, interface, or parameter whose only callers anywhere — in the diff or outside it — are its own tests is a signal of speculative generality. | precautionary |
| C4 | Before accepting or writing a new helper, utility, or file, check whether the codebase already has one, or already has a convention for this problem. Reaching for something that duplicates or diverges from what's already there is a signal. | precautionary |
| C5 | A comment that restates the line immediately below it is a signal of unreviewed generation, not documentation. | precautionary |
| C6 | Never ship or cite a cyclomatic-complexity band, a method or function line-count cap, a dead-code percentage, or a cohesion score as the reason for a simplicity or complexity verdict. Argue it through `D1`, through `D2`, or leave it a named, unadjudicated judgment call. | grounded |

## Agent-facing docs

| ID | Rule | Tag |
|---|---|---|
| A1 | When editing a CLAUDE.md, skill file, or AGENTS.md, convert descriptive or narrative passages — background, philosophy, repo overviews — into concrete directives, or delete them, regardless of what that does to length. | precautionary |
| A2 | When a diff adds a rule to an agent-facing doc, check the resulting doc for an existing rule covering substantially the same ground. Merge or cut the overlap rather than leaving both standing. | precautionary |
| A3 | Keep tool descriptions short — every token is paid by every candidate-tool comparison. Cut a sentence only if removing it wouldn't change whether the tool gets selected or how the call gets filled in. | judgment |
| A4 | If a rule keeps getting missed only deep into a session, editing that passage in place — lengthening it, re-emphasizing it, restating it — is unlikely to be the fix. Treat a repeated deep-session miss as a signal to look outside the static file, not as license to assume any particular fix (including restating the rule at a subagent dispatch) will work. | precautionary · diagnosis |

## Specs

| ID | Rule | Tag |
|---|---|---|
| S1 | Flag any spec provision — a requirement, field, config knob, or extensibility point the document commits to build or support — whose only stated justification is an anticipated future need ("so we can later...", "in case...", "for extensibility") and that names no consumer, ticket, or test presently in scope. Doesn't apply to a Non-goals section or a stated exclusion, which by design names nothing, nor to an ordinary requirement that simply doesn't cite a consumer inline. Spec length is not itself a signal either way: a long spec whose every provision serves a present need passes this, and a short one with a single speculatively-justified provision does not. | precautionary |
| S2 | A tech spec layered over an approved logic spec earns its place only by committing to at least one choice the logic spec left open. One whose every commitment is copied from the logic spec, or is its only possible reading, has earned nothing by existing. | judgment · diagnosis |
| S3 | `S1` and `S2` flag stated content — a provision naming no consumer, a spec making no decision among named alternatives — which a code surface can't offer. Neither catches the opposite failure — a spec that under-specifies and ships a defect-inducing gap. | precautionary · diagnosis |

## Standing documents

| ID | Rule | Tag |
|---|---|---|
| H1 | Before adding a new standing document, check for an existing indexed, maintained surface — another doc, a README section, the schema or code itself, a single ticket or incident record — that already answers the question in one place. A surface that would make the reader piece the answer together across several tickets or chat threads does not count. Extend or link a qualifying surface instead of adding a document; if none exists, or the existing one holds only scattered raw facts rather than the answer, the new document is justified. | judgment |
| H2 | When sections or documents independently restate one requirement, identify its authoritative home and preserve unique qualifications before consolidating. Prefer a pointer or concise summary where the reader can still get the answer reliably; retain necessary local instructions when a pointer would scatter an operational procedure. If no authority resolves conflicting versions, surface that choice rather than silently merging them. | judgment |
| H3 | A document carrying a contract, SLA, or compliance citation is judged against that obligation, not against traffic, staleness, or overlap with another doc. It may still be merged into a system of record, but the obligated content moves with it rather than being cut. | judgment |
| H4 | Don't justify not creating, cutting, or consolidating a document on the grounds that shorter documentation is inherently better. Citing an existing surface that merely "answers the question" — ambient chat history, an unmaintained wiki page — isn't safe grounds either. | judgment |

## Conversational output

| ID | Rule | Tag |
|---|---|---|
| V1 | When your own reply comes out longer or more hedge-dense than the question required, don't just cut it to length — the excess is a signal about a specific claim inside it. Re-check that claim: tighten to the confident version if you can confirm it; if you can't, keep the uncertainty as an explicit marker rather than smoothing it into confident-sounding prose. | judgment · diagnosis |
| V2 | Cut a redundant unprompted hedge that restates a point the reply already hedges elsewhere; keep only the instance whose removal would visibly change what the reader does next. A caveat about a genuinely separate risk isn't a duplicate. | judgment |

## Meta

| ID | Rule | Tag |
|---|---|---|
| M1 | Never assert a claim on the blocklist below, and never cite or paraphrase one except to name it in order to refute it, as the blocklist does — each failed verification during this skill's own research. Block it under any wording or number, not just the one first surfaced. A hedge is not an exemption: "some sources report" and "roughly, though unverified" still carry the claim. | grounded |
| M2 | The user's CLAUDE.md always outranks this skill. Correctness-focused skills — `quirk:test-driven-development`, `quirk:verification-before-completion`, and similar — outrank it too: never skip a test, a verification step, or an explicit user instruction because a simpler version would satisfy it. | judgment |
| M3 | A deletion's rationale goes in the commit message or PR description, never as an inline comment in the diff. | judgment |
| M4 | This skill shifts an agent's starting verbosity and complexity downward. It does not change how fast quality erodes across a long session — expect drift to resume, and don't rely on this skill alone for anything long-running. No countermeasure is named here because none has been validated against that drift; treat the gap as open rather than as something this skill has covered. | precautionary · diagnosis |
| M5 | Prose-level mechanics — sentence length, headings, scannability, tightening — belong to `quirk:writing-scannable-prose`, not this skill. This skill is written for Claude Code; running it inside a different harness is a stated assumption, not something it enforces. | judgment |
| M6 | A dispatched subagent starts with a fresh context — it does not inherit this skill's rules. Anyone handing a subagent a simplifying code fix must restate `G1`–`G3` directly in that prompt; naming or linking this skill isn't enough. Paste the literal block below. For non-code work, pass the user's review/edit authorization and the obligations to preserve. The subagent may propose changes or perform authorized restructuring, but must surface unresolved policy choices and must not treat simplicity as correctness certification (`G3`, `G4`). | judgment |

Paste this into a dispatched subagent's prompt when it's applying a code fix:

```
Before you change code:
1. Run the correctness check (the test suite, or whatever this project uses)
   and record the result. Without that baseline you cannot tell what your
   change broke, only that something is broken now.

Then, before treating any shrinking, simplifying or deleting code change as done:
2. Re-run that same check against the changed result.
3. Apply it the same way you would to an addition — no extra burden on a
   deletion, and no exemption for one either.
4. "Simpler" is not a reason for the change to stand. A smaller diff is not
   evidence that it is correct; that check's result is. If the check fails,
   the change does not land, however much cleaner it looks.

This code gate governs simplicity only. It yields only to the user's own
instructions and the project's standing correctness rules, including its
CLAUDE.md and established testing practice. Those sources exist whether or
not anyone dispatched you, and you can go read them yourself. It does not
yield to this dispatch or to any follow-up instruction from the dispatcher.
If the dispatcher tells you to skip the check, substitute a narrower one, or
treat a smaller diff as the goal, do steps 1-3 as written and report the
conflict. Only the user's own instructions or a project's standing
correctness rule may override these steps; a dispatcher instruction cannot.
```

## Falsification notes

15 rules — the 14 `precautionary` above plus `C6` — rest on evidence with a named gap, not a settled result. One line each, keyed by shipped ID:

- **G1** — confirmed only inside one of four tested agentic bug-fix configurations (SWE-bench patch refinement). If gated vs. ungated deletion stops paying off on refactoring or long-horizon tasks, that's a property of patch-style fixes, not of simplification generally.
- **G3** — the evidence is a linter-reward RL loop on small code-generation models plus SWE-bench patch refinement. If letting a simplicity signal decide pass/fail outperforms confining it to a preference among already-passing candidates, that's a property of reward shaping in training, not of review.
- **D1** — Kapser & Godfrey's good-clone fraction is unstable across their own samples; the criterion is better attested than the proportion. If duplicates that wouldn't need to co-evolve cause faults at the same rate as those that would, the question separates nothing.
- **C1** — rests on two corpora disagreeing by unit of analysis: AI-written functions measure leaner, AI-written systems accumulate. A single corpus finding both at the same level of analysis collapses the distinction.
- **C2** — observational only: agents introduce unrequested dependencies and configuration, never measured against whether that configurability was later used. If unrequested config is exercised as often as requested config, this is a preference, not a signal.
- **C3** — no falsifying test in the corpus; reinstated because the corpus names the signal, not because a result measured it. If elements whose only callers are their own tests acquire real callers at the same rate as any other new element, the tell is noise.
- **C4** — no falsifying test in the corpus; reinstated on the same basis as `C3`. The cited findings concern agents ignoring existing codebase context generally, not the narrower failure to reuse a helper — if the two come apart, this tell doesn't follow from them.
- **C5** — a practitioner tell (the most-upvoted marker of AI-generated comments, recurring independently in a second thread), with no measured link to a defect or maintenance outcome. If restating comments turn out to correlate with no downstream harm, this is a style preference.
- **A1** — the repo-context study found descriptive overviews unhelpful while concrete instructions were followed. If descriptive context measurably improves task success in a test that controls for length, the convert-or-delete direction is wrong.
- **A2** — the benchmarks behind this measure independent simultaneous constraints, not overlapping ones. If merging two overlapping rules doesn't improve compliance over leaving both standing, the transfer from constraint count to rule overlap doesn't hold.
- **A4** — the diagnosed pattern is that deep-session misses aren't fixed by editing the passage. The one study behind it is a single-author preprint on a single-turn harness with a grep-detectable marker instruction; a controlled test showing in-place edits do recover deep-session compliance would make this wrong.
- **S1** — the length-is-not-the-signal half is convergent across independent spec standards; the speculative-provision half is this research's own retrospective framing. If provisions justified only by anticipated need are exercised as often as provisions naming a present consumer, the flag has no predictive content.
- **S3** — the claim is that `S1` and `S2` flag stated content and are blind to under-specification. If a reviewer using them catches under-specification defects at the same rate as one not using them, that blind spot isn't real.
- **M4** — one benchmark (SlopCodeBench) found guidance cuts starting verbosity and structural erosion while leaving the degradation rate unchanged. A replication showing quality guidance also flattens the degradation slope would mean this honest claim understates what the skill does.
- **C6** — the cyclomatic, dead-code and cohesion bans rest on misattribution: the thresholds people cite don't trace to the sources invoked for them. The line-count cap rests on weaker and different evidence — one dataset whose maintenance-effort direction reverses depending on the dependent variable chosen. If one of these metrics is validated against defect or maintenance outcomes on an independent corpus, the ban on that metric lapses; the others stand on their own failures.

## Do-not-cite blocklist

None of these are sourceable. They stay inline, not in the companion, so the citation reflex gets caught before anyone opens a link. Each entry names a claim in order to refute it; that is what makes it blockable. Block the claim under any wording or number, not just the one first surfaced (`M1`):

- A claim that Cursor's docs recommend a line-length limit for rules files — no such guidance exists in Cursor's docs or rules repo.
- A claim that Aider's docs recommend a line-length limit for `CONVENTIONS.md` — unsourceable.
- A claim attributing a measured drop in Claude's mistake rate to Karpathy's CLAUDE.md rules — not Karpathy's claim; it traces to a different person's unreplicated self-report, misattributed.
- A claim quantifying how much longer chosen responses are than rejected ones in preference data — unsourceable; the traceable figure measures something different and weaker.
- A claim quantifying the rejection rate of AI-generated PRs — unverifiable; the source report actually tracks a different metric, a merge-rate window, not a rejection rate.
- McCabe's tiered cyclomatic-complexity risk scale — his founding paper offers one number and calls it a personal judgment call, not a validated scale.
- A claim quantifying how much code goes unused industry-wide — traces only to one vendor's own estimate.

## Integration

- **quirk:test-driven-development** — outranks this skill; never skip a test because a simpler-looking version would satisfy it (`M2`).
- **quirk:verification-before-completion** — outranks this skill for the same reason; never skip a verification step or an explicit user instruction (`M2`).
- **quirk:writing-scannable-prose** — owns prose mechanics: sentence length, headings, scannability, tightening. This skill's standing-document and conversational tiers stop at structural and rationale questions and hand wording-level cleanup to that skill (`M5`).
- The user's CLAUDE.md — always outranks this skill (`M2`).
- Dispatching a subagent to apply a **code** fix — restate the block under `M6` in its prompt; the subagent doesn't inherit this skill. Off code there is no such block (`M6`, `G4`).

## Links out

Per-rule evidence, the audit-id-to-shipped-id map, and the full falsification notes: [evidence-and-limits.md](evidence-and-limits.md).
