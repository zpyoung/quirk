# Logic spec — restructure the quirk flow into logic spec + tech spec

**Status:** Draft (awaiting user review)
**For humans.** This document explains *what* we're changing and *why*, in plain language. It deliberately avoids code and exact signatures — those live in the `tech.md` sibling, which is authored at execution time (see [Behavior & scenarios](#behavior--scenarios)). When this document names a skill file, it does so because *that file is the decision*, not as implementation detail.

---

## Problem & purpose

Quirk's development pipeline today produces **one combined document** at the front: brainstorming writes a `…-design.md` spec, the user approves it, and then the execution skills build the task plan in-context and start coding. That single document serves two masters at once:

- a **human** who needs to understand the shape of the work — the data flow, the reasoning behind each decision, the mental model — before committing to it, and
- an **AI agent** who needs precise, unambiguous, code-anchored instructions to build the thing correctly.

Those two audiences want almost opposite things. A human wants prose, rationale, and conceptual clarity, and is slowed down by file paths and function signatures. An agent wants exact paths, contracts, and "do not touch this" fences, and is misled by hand-wavy conceptual language. Serving both in one document means each reader wades through material written for the other, and the document is never fully optimized for either.

**The purpose of this change** is to split that single document along its natural seam:

- a **logic spec** (`logic.md`) — plain language, optimized so the *user* can fully understand the flow of data, why decisions were made, and how things work conceptually; and
- a **tech spec** (`tech.md`) — code-anchored and precise, optimized so an *AI agent* can build from it with zero ambiguity.

The goal is a pipeline where the human always gets a document written for humans, and the agent — when the work is substantial enough to warrant it — gets a document written for agents.

## Conceptual model

Think of the pipeline as three concerns that used to be tangled and are now separated by audience:

1. **The idea and its reasoning** — the "why we're doing this and how it hangs together." This is a human concern. It's produced by conversation and belongs in a document a person reads and approves. → **logic spec**
2. **The code-level map** — "here are the exact files, contracts, and boundaries to build against." This is an agent concern. It's produced by surveying the actual codebase, and it only pays for itself when the work is big enough that the survey is worth caching. → **tech spec** (optional)
3. **The moment-to-moment task list** — "do this, then this, red-green-commit." This is execution *state*: it churns constantly, gets reordered, absorbs review feedback. It has no business being a frozen document. → **in-context plan** (unchanged from today)

The key insight is that these three age at very different rates. The reasoning is stable. The code map ages slowly and silently (a renamed function quietly invalidates a pointer). The task list is stale by the end of the first work-wave. Separating them by how they age is what lets each live in the right home: a committed document, an optional committed document, and a live in-context list respectively.

A second insight shapes the whole design: **quirk specs are build-once artifacts, not living documentation.** A spec is written, used to build one feature, and then archived as a historical record. This is why the well-known "two documents drift apart over months" problem barely applies to us — the two documents only need to stay consistent for the length of a single build session, and one is authored directly from the other.

## Data flow

Here is how information moves through the new pipeline, end to end:

1. **Brainstorming** (a conversation) explores the idea. It still does a first-contact pass over the codebase so its conclusions are grounded in reality. Its output is the **logic spec** — the reasoning, the conceptual model, the data flow, the decisions and their rationale, written for a human.
2. **The user reads and approves the logic spec.** This is the one hard gate in the pipeline. Approving the logic spec means "yes, this is the right idea, I understand it, build it." Because the logic spec is written *for* the user, this is the moment human understanding is confirmed — which is exactly where the human gate belongs.
3. Control passes to an **execution skill**. Before it writes any code, it makes a judgment call: **is this work substantial enough to deserve a tech spec?**
   - **If yes** (multi-session work, a real subsystem boundary, many files touched, or the user asked): it runs the **tech-spec rubric**. This surveys the actual codebase in depth and writes the **tech spec** — the exact files, signatures, contracts, and do-not-touch fences an agent needs. An automated reviewer checks it; the user may optionally skim it. Crucially, if the codebase survey reveals that the approved idea won't work as written, execution **stops and escalates back to the user** rather than quietly changing the plan.
   - **If no** (a bug fix, a config tweak, a one- or two-file change): it skips the tech spec entirely. The logic spec plus the codebase are enough.
4. The execution skill builds its **in-context task list** (exactly as it does today), reading from the tech spec when one exists, or straight from the logic spec when one doesn't.
5. It **executes** the tasks through the existing per-task review chain, and finishes through the existing branch-completion flow. The documents' `Status` fields are set as the work completes; fuller lifecycle automation is deferred (see [Deferred Ideas](#deferred-ideas)).

The one-line version: **brainstorm → logic spec → (optional tech spec) → build**, with the only mandatory human checkpoint on the logic spec.

## Key decisions & rationale

**Why two documents instead of one document with two sections?**
Because the audiences are genuinely different and the clean separation is the entire point. The research warns that splitting *living* docs causes drift, but our specs are build-once, and we add explicit safeguards (ownership rule + traceability links + author-from-approved-source). Two files give the human a document with zero agent-noise and the agent a document with zero hand-waving. A single layered file would reintroduce exactly the "wading through the other audience's material" problem we're trying to kill.

**Why is the tech spec optional rather than always produced?**
Because mandating it would regress daily usability. Most changes — including most of quirk's own features — are edits to a handful of files that shipped fine under the single-document flow. Forcing a full codebase deep-dive, a second document, and a second review loop onto a two-line bug fix is pure ceremony. Brainstorming already scales its output down to "a few sentences" for trivial work; the tech spec gets the same treatment — it appears only when its cost is repaid by multi-session durability, subsystem complexity, or breadth.

**Why does the tech spec stop at technical design, leaving the task list in-context?**
Because the task list is execution *state*, not design. It splits, reorders, and absorbs reviewer feedback continuously; a task list written to a file is stale before the first wave finishes. Its correct home is the live in-context list that survives compaction — which is exactly where quirk's recent refactor already put it. The tech spec owns the stable material (architecture, contracts, boundaries); the volatile material stays live. This deliberately preserves the "plan lives in context" decision rather than reversing it.

**Why "precise pointers, no pasted code" in the tech spec?**
Because pasted code anchors the implementer to one approach, ages the instant the real code changes, and shifts reviewers from judging *decisions* to reviewing *syntax* — this is quirk's existing No-Code Rule, and it's correct. "Heavy code reference," in every modern agent-spec framework, means precise *pointers* (paths, signatures, symbols, do-not-touch fences), not reference implementations. Pointers give the agent crystal clarity about *where* and *what* while leaving *how* to the implementer who has the full live codebase. The tech spec is code-anchored without containing code.

**Why is the tech spec authored by an execution-owned rubric, not a new top-level skill?**
Because quirk's direction is consolidation — it recently folded plan-writing *into* execution rather than leaving it a separate stage. A brand-new user-facing stage cuts against that and adds a handoff seam. Making tech-spec authoring a rubric that the execution skills invoke (the same pattern plan-writing now follows) keeps the persistent, reviewable `tech.md` file and its optional-skim gate, but without a fourth stage in the user's mental model — and it gives the feasibility-escalation loop a natural home right where the code gets built.

**Why does only the logic spec get a mandatory user gate?**
Because the logic spec is the human artifact — it's where a person confirms the idea is right. The tech spec is agent-facing and is authored directly from the already-approved logic spec, so it gets an automated reviewer plus an optional user skim. The one exception, and it's important: if authoring the tech spec surfaces a *conflict* with an approved decision, that is escalated to the user as a change to the logic spec. The user never has to routinely review a dense code-referenced document, but they are never bypassed on a real decision either. And for work above the complexity tier, that optional skim arrives with a **risk summary** — the execution announcement surfaces the tech spec's most consequential calls (the subsystem it anchored in, its major do-not-touch fences, its riskiest contracts) so a person can veto a legal-but-poor technical bet — exactly the wrong-but-*consistent* choice the automated reviewer can't catch — without reading the whole document.

**Why the "ownership + sync" content rule instead of strict zero-overlap?**
Because strict zero-overlap ("the logic spec may never name a file") is unachievable and actively harmful here. For a plugin whose product *is* files, the file-level structure often *is* the decision the user most needs to approve — quirk's own prior specs lock decisions like "keep this file under ~500 lines" in the user-facing document. Forbidding that would bury the decisions most likely to be wrong behind the optional gate. Instead: the logic spec **owns** the why and the behavior (and may name file-level structure when that structure is the user-facing decision); the tech spec **owns** the where and the contracts; each may summarize the other in a line and link across; and any change to a locked decision amends the logic spec first, in a dated entry, never as a silent edit to the tech spec.

**Why keep brainstorming's pre-approval codebase exploration?**
Because otherwise the only deep look at the codebase would happen *after* the user has already approved the logic spec, and a nasty surprise there would have nowhere to go but a silent reinterpretation. Grounding the logic spec in first-contact reality before approval, and reserving the deep survey for confirmatory depth, keeps the approved document honest.

## Behavior & scenarios

**Small change (bug fix, config tweak, 1–2 files).**
Brainstorm → short logic spec → user approves → execution sees the work is small, skips the tech spec, builds the in-context task list from the logic spec, and codes. Net experience: today's flow, with the front document renamed. No added ceremony.

**Substantial feature (multi-file, or spanning a subsystem).**
Brainstorm → full logic spec → user approves → execution runs the tech-spec rubric: it surveys the codebase, writes `tech.md` with exact paths/contracts/fences, an agent reviewer checks it and confirms every logic-spec decision is faithfully carried through, the user optionally skims (the announcement surfaces the riskiest calls for a quick veto) → the in-context plan is built from `tech.md` (its header points at `tech.md`; each task's contract is excerpted from `tech.md` at dispatch so a fresh subagent still gets self-contained text) → execute.

**Feasibility conflict (the codebase contradicts the approved idea).**
While authoring the tech spec, the deep-dive reveals the approved approach is infeasible or naive. Execution **stops**. It presents the conflict to the user and records the resolution as a dated amendment to `logic.md`. Only then does it continue. The approved human document is never silently overridden in the agent document.

**Change request after execution has started.**
The change is written into the logic spec's amendment log first; any affected tech-spec sections are regenerated; the in-context task list is updated through the normal planning rubric. The logic spec remains the source of truth for *why*; the tech spec is a map that gets corrected when the territory moves.

**Multi-subsystem work.**
Brainstorming decomposes it into independent sub-projects, each getting its own dated `<topic>` folder with its own `logic.md` (and, at execution, its own optional `tech.md`). Each sub-project runs the full cycle independently.

## Scope & non-goals

**In scope:** re-purposing `brainstorming` to produce `logic.md`; a new tech-spec rubric invoked by the execution skills; amending `writing-plans` to consume `tech.md`; updating the execution skills, `using-quirk`, `using-git-worktrees`, `exploring-ideas`, `commands/explore.md`, and `README.md` for the new flow and paths; the two document templates; the per-topic folder convention; the new tech-spec reviewer and deletion of the orphaned spec reviewer.

**Non-goals:**
- Auto-*generating* the tech spec from the logic spec (spec-as-source). We author it; generation is a future idea.
- Continuous doc-sync tooling or automated traceability recovery. Out of scope for build-once specs.
- Migrating existing `*-design.md` specs. They stay as historical records under the old convention.
- Renaming the `brainstorming` skill. It keeps its name; only its output changes.
- The version bump. That happens at release time through the release flow.

## Glossary

- **Logic spec (`logic.md`)** — the human-facing document: why, behavior, conceptual model, data flow. The only artifact with a mandatory user-approval gate.
- **Tech spec (`tech.md`)** — the agent-facing document: exact files, signatures, contracts, do-not-touch fences. Optional; authored at execution time when the work warrants it; pointers not pasted code.
- **In-context plan** — the live task list (checkboxes, red-green-commit) the execution skills build in working context. Unchanged by this design.
- **Tech-spec rubric** — the ruleset (a skill) defining what a good `tech.md` contains and how to author it; invoked by the execution skills, not a user-facing stage.
- **Complexity tier** — the judgment that decides whether a given feature gets a `tech.md` at all.
- **Ownership rule** — logic spec owns *why + behavior*; tech spec owns *where + contracts*; cross-links allowed, duplication avoided.
- **Feasibility escalation** — the rule that a codebase conflict found while authoring the tech spec must stop and return to the user as a logic-spec amendment, never be resolved silently.
- **Do-not-touch fence** — a marked region of stable code the agent must not modify; each fence cites its reason and is re-verified when the task list is built.

## Decisions Locked

Grouped by area, these were confirmed during the brainstorm and hardened by an adversarial review.

**Structure**
- Two separate files: `logic.md` (human) + `tech.md` (agent). Not one layered doc; not in-context.
- The tech spec is an **optional depth tier**, not mandatory — built only for multi-session / multi-subsystem / many-file work, or on request.
- Files live in a per-topic subfolder: `docs/quirk/specs/YYYY-MM-DD-<topic>/{logic,tech}.md`. Multi-subsystem work = N sibling `<topic>` folders.

**Content boundary**
- Tech spec = technical design only; the task-by-task breakdown stays in-context via the planning rubric.
- Tech spec uses **precise pointers, no pasted code** (preserves the No-Code Rule).
- **Ownership + sync**, not strict zero-overlap: logic spec may name file-level structure when it's the user-facing decision; changes to a locked decision amend `logic.md` first (dated), never a silent `tech.md` edit; the reviewer verifies cross-links resolve.

**Topology**
- Tech-spec authoring is an **execution-owned rubric** invoked as a pre-planning sub-phase, mirroring how plan-writing became a rubric. Not a new top-level skill.
- `brainstorming` keeps its name and its pre-approval codebase exploration; produces `logic.md`.
- `writing-plans` is **amended to consume `tech.md`** (header = pointers; task contracts excerpted at dispatch). Its philosophy is otherwise untouched.

**Gates & safety**
- Logic spec = mandatory user approval. Tech spec = automated reviewer + optional user skim.
- **Feasibility escalation:** a codebase conflict found while authoring the tech spec stops execution and returns to the user as a `logic.md` amendment.
- The tech-spec reviewer verifies fidelity: every Decision Locked is implemented, none silently reinterpreted.
- Both documents carry a `Status` field; the logic spec carries an `Amendments` log.

**Housekeeping**
- The orphaned `skills/brainstorming/spec-document-reviewer-prompt.md` (referenced nowhere) is deleted; brainstorming keeps its inline self-review.
- Existing flat `*-design.md` specs are left as historical records.
- Do-not-touch fences cite a reason and are re-verified at plan-build time.

## Industry Insights

Distilled from two parallel research swarms (2026 sources).

- **The industry standard is three layers, not two.** Amazon Kiro uses `requirements.md → design.md → tasks.md`; GitHub Spec Kit uses Spec → Plan → Tasks → Implement. Our two-tier split (logic + tech, with the task list in-context) is a deliberate *compression* of that chain — the tech spec straddles their "design," and our in-context plan is their "tasks." Sources: [Kiro specs](https://kiro.dev/docs/specs/), [GitHub Spec Kit](https://github.github.com/spec-kit/).
- **"Heavy code reference" means pointers, not pasted code.** Every agent-facing framework (Kiro, Spec Kit, AGENTS.md, Addy Osmani's spec guidance) specifies absolute paths, function signatures, DO-NOT-CHANGE sections, and existing tests to match — not reference implementations. This is what makes our "code-anchored but No-Code" tech spec coherent. Sources: [How to write a good spec for AI agents](https://addyosmani.com/blog/good-spec/), [AGENTS.md standard](https://addyo.substack.com/p/how-to-write-a-good-spec-for-ai-agents).
- **Separate *living* documents drift and overlap (40–60%).** The academic literature is firm that splitting specs horizontally breaks traceability and creates orphaned artifacts, and that a single layered document is usually more maintainable. We escape this mainly because quirk specs are **build-once**, and secondarily via the ownership rule, cross-links, and authoring the tech spec from the just-approved logic spec. Sources: [The Spec Growth Engine](https://arxiv.org/pdf/2606.27045), [AI Agent Anti-Patterns pt.3](https://achan2013.medium.com/ai-agent-anti-patterns-part-3-knowledge-document-processing-0caf472856ff).
- **Splitting is justified when the layers have genuinely different audiences and change rates** — which is exactly our case (human vs. agent; stable reasoning vs. slowly-aging pointers vs. churning task list). Source: [Spec as source of truth](https://www.augmentcode.com/guides/spec-as-source-of-truth-rebuildable-codebase).
- **Vocabulary drift is a top agent-failure cause** — the same term meaning different things across documents produces wrong code. Hence the mandatory glossary in the logic spec. Source: [AI Agent Anti-Patterns pt.3](https://achan2013.medium.com/ai-agent-anti-patterns-part-3-knowledge-document-processing-0caf472856ff).

## Deferred Ideas

Captured so they aren't lost; explicitly out of scope for this change.

- **Generate the tech spec from the logic spec** (spec-as-source) instead of authoring it. Strongest anti-drift approach, but heavier machinery; revisit later.
- **Continuous doc-sync agents** (DocSync-style critic loops) and **automated traceability recovery** (R2Code / LiSSA). Overkill for build-once specs.
- **Rename `brainstorming` → `writing-logic-spec`** for naming symmetry with the tech-spec rubric. Rejected for now — the dialogue *is* the brainstorm, and the cross-reference cost is high.
- **Automate `Status` lifecycle transitions** in the branch-completion flow (Draft → Superseded/Archived). Noted for the implementation phase but not a design decision.

## Status & amendments

**Status:** Draft — awaiting user review. The `tech.md` sibling has been hand-authored (dogfooding), since the change spans 14 files across ~7 skills — above the complexity tier.

**Amendments:**
- **2026-07-10** — Data flow (step 5): softened "records the final status of the documents" to "`Status` fields are set as work completes; lifecycle automation deferred," aligning it with the Deferred Ideas entry and removing a promise no work unit implements. Surfaced by the tech-spec review; `finishing-a-development-branch` stays untouched (audited in `tech.md` CU-8).
- **2026-07-12** — F9 resolved (review-gate refinement): for work above the complexity tier, the optional tech-spec skim now comes with a **risk-surfacing announcement** (anchored subsystem, major fences, riskiest contracts), so a person can veto a legal-but-poor technical bet the automated reviewer can't catch — without a full mandatory gate. Reflected in `tech.md` C2.9.
- **2026-07-10** — Post-red-team hardening of `tech.md` (no logic-level decision changed): R4 feasibility escalation now fires at *any* point after approval (authoring / planning / execution), with an explicit tech-section regeneration owner and a headless-halt rule — closing the hole where a mid-execution conflict could silently edit the plan and override this document. Added the R2 provisional-tier upgrade path + recorded ruling, an R5 canonical-vocabulary / CU-ordering / bootstrap-exemption rule, and a C4.5 pointer-re-resolution step so "re-verified at plan-build" is an owned step rather than a phrase. Status file/skill count corrected to 14 / ~7.
