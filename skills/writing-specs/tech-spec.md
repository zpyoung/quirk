# Writing the Tech Spec

## Overview

> **How this rubric is used:** Authoring the tech spec is **not a user-facing stage.** The
> execution skills (`quirk:subagent-driven-development` and `quirk:executing-plans`) invoke
> `quirk:writing-specs` and read this file in-context as a **pre-planning sub-phase**, gated on
> the complexity-tier check below — before they hand off to `quirk:writing-plans` to build the
> task breakdown. It runs inside the execution skill's worktree, after the logic spec is
> approved. This rubric defines *what a good tech spec contains*; the calling skill owns *when*
> it runs.

A tech spec is a **code-anchored map of exact files, contracts, and boundaries that a fresh implementer can build against — not a rewrite of the logic spec, and not a substitute for the code itself.** It answers WHERE to work and WHAT MUST BE TRUE when the work is done, leaving HOW — the actual code — to the implementer, who has the live repository and will write better code than a pre-written body could capture. **The implementer still writes the code; this document only removes the ambiguity about where and against what.**

Write for an implementer who has **zero context for this conversation** and needs precise, resolvable anchors — not conceptual framing. The logic spec already carries the *why*; this document exists only because *where* and *what must hold* deserve their own, denser, agent-tuned home.

**Announce at start:** "I'm authoring the tech spec (writing-specs → tech-spec.md rubric)."

## Complexity-tier gate

Run this rubric — and produce a `tech.md` — **only if** at least one of these holds; otherwise skip straight to `quirk:writing-plans` from the logic spec:

- execution spans **more than one session**, OR
- the work **crosses a subsystem boundary**, OR
- it touches **≳3 source files**, OR
- the **user asks** for a tech spec (recorded — see below).

These inputs are judged **before** planning, so the calling skill's ruling here is *provisional* — real file count and "more than one session" aren't fully known until planning's File Structure pass runs:

- **Recorded ruling.** Log the tier decision as one line — which criterion fired, or "skipped — none met" — in the execution run, and in the logic spec's `Status` line when a `tech.md` is authored. No silent skips: a skip with no record is how this tier quietly decays into never firing.
- **Upgrade path.** After `quirk:writing-plans`' File Structure pass reveals the real scope, **re-check this gate**; if a skipped run now clears the tier, author `tech.md` then and re-plan the affected tasks. The calling execution skill owns this re-check.
- **User-ask capture.** If the user requests a tech spec at logic-spec approval, the logic-spec rubric ([logic-spec.md](logic-spec.md)) records it in the logic spec's `Status` line ("Tech spec: requested") so a later or headless run can read it without re-asking.

Below this line, the pipeline is `brainstorm → logic spec → build` — no tech spec, no extra document, no extra review loop.

## Deep-dive method

Before writing a single line of `tech.md`, gather precise anchors from the *live* codebase: exact file paths, function/class signatures, symbol names, existing tests that already cover the area, and regions that look stable and load-bearing. Dispatch **parallel `Explore` subagents** — one per subsystem or file cluster the logic spec touches — **when subagents are available**, and do this in parallel, not sequentially — the clusters are usually independent and the survey is the expensive part this rubric exists to pay for once. On a sequential, no-subagent path (e.g. `quirk:executing-plans`), the orchestrator performs this codebase survey directly, in-session — the anchors still must come from the live tree, never from memory.

This survey is what makes the spec "code-anchored" in the sense the industry means by **heavy code reference**: precise pointers — paths, signatures, symbols, do-not-touch fences — never reference implementations. A tech spec built from memory or from the logic spec's prose alone is not code-anchored; it is guessing with better formatting. If the survey can't resolve an anchor it was sent to find, that is signal the logic spec's assumption needs a closer look before you write it down as fact — see feasibility escalation below.

## The `tech.md` template

A `tech.md` is not free-form — it has required sections, because a fresh implementer scans for structure, not prose:

- **Header** — `Status`, and a back-link to the sibling logic spec.
- **Architecture** — the real files and how they relate (and the key technologies/libraries in play), not a diagram of intent.
- **Code references** — absolute paths, signatures, and symbols to create or modify, gathered by the deep-dive above.
- **Contracts & interfaces** — for every unit other work depends on: preconditions, postconditions, invariants, error behavior.
- **Data models / schemas** — exact field names and types, or request/response shapes, wherever the literal shape matters.
- **DO-NOT-CHANGE fences** — each names the exact region *and states why it's fenced*. A fence with no reason is not a fence, it's a suggestion; write the reason so a downstream re-check (at plan-build, and again at each task dispatch) can tell whether the fence still applies.
- **Always / Ask / Never** — the same three-bucket constraint list a plan uses, but scoped to technical constraints (hard invariants to preserve vs. choices delegated to the implementer).
- **Cross-cutting** — security, observability, data migration, and rollback concerns, where relevant.
- **Testing strategy** — which test files, what they must cover, the acceptance bar — never the test bodies themselves.
- **Non-goals** — what this tech spec deliberately does not cover, so a reader doesn't assume silence means "out of scope by omission" versus "considered and excluded."

Every technical section earns its place by being something an agent can act on without asking a follow-up question. If a section reads like it belongs in the logic spec — rationale, alternatives, conceptual framing — cut it; that content already has a home, and duplicating it here is exactly the drift the two-document split exists to prevent.

## Pointers, not code

`tech.md` inherits `writing-plans`' No-Code convention in full: **no pasted implementations, no full test bodies.** Every code-shaped block must carry one of these six tags, or it's a defect:

- `CONTRACT:` — an interface/signature sketch other work depends on (names, parameter/return types, error enums/status codes) — a shape, never a body
- `SCHEMA:` — exact data-schema field names/types, or an API request/response shape
- `COMMAND:` — exact shell/git commands to run verbatim
- `REGEX:` — a literal pattern that *is* the specification
- `CONFIG:` — exact config keys, env vars, or values where the literal string matters
- `PSEUDOCODE (justified, ≤3 lines):` — only for a subtle algorithm where prose is genuinely ambiguous, with a one-line note on why prose failed

The reasoning is the same as in a plan: pasted code anchors the implementer to one approach, ages the instant the real code changes, and turns review into a syntax check instead of a decisions check. The deep-dive method above gathers *precise pointers* — that precision is what lets this rule hold without the spec going vague. A tech spec that pastes a function body to avoid ambiguity has solved the wrong problem; tighten the contract prose instead.

## Ownership, traceability & feasibility escalation

**Ownership.** The logic/tech ownership line and the amend-the-logic-spec-first rule live in [SKILL.md](SKILL.md#ownership). What this rubric adds: every technical section in `tech.md` **back-links** the logic-spec anchor that justifies it, and every one of those links must resolve to a real heading.

**Feasibility escalation.** A conflict with a locked decision (or its conceptual model) can surface at three moments: while **authoring** `tech.md`, during **planning**, or **mid-execution** when an implementer hits it. At any of them: **stop**, present the conflict to the user, and record the resolution as a dated entry in the logic spec's Amendments log **before** proceeding. Never resolve it unilaterally in `tech.md`, and never resolve it by silently editing the in-context plan — that is exactly how the logic spec's "the approved human document is never silently overridden" guarantee breaks.

- After the amendment lands, re-invoke this rubric **scoped to the affected sections** to regenerate them, then re-plan the affected tasks.
- On a **headless or non-interactive run**, this halts with a blocking note — it does **not** silently continue. This overrides any adjacent "no human approval gate" wording elsewhere in the pipeline, which governs plan review, not a conflict with a locked decision.

## Where `tech.md` lives

See [Where the specs live](SKILL.md#where-the-specs-live) — `tech.md` is always a sibling of the
actual `logic.md`, in whatever directory the logic spec was really saved to.

## After authoring: review, optional skim, handoff

Writing the document is not the last step. Three things happen next, in order:

1. **Dispatch the tech-spec reviewer, by default.** Use `tech-spec-reviewer-prompt.md` (this rubric's sibling file) — paste `tech.md` and the logic spec inline, since the reviewer reads no file. It checks pointer precision, fidelity to every Decisions-Locked entry, traceability (back-links resolve), the No-Code rule, contract completeness, and buildability. Apply its fixes inline. This is the standard gate, not optional, and it replaces any human approval step here.
2. **Offer an optional user skim — not a gate.** The user is never required to read `tech.md`; the mandatory checkpoint already happened at logic-spec approval. But *offer* it, and when you do, **surface the tech spec's most consequential calls** alongside the offer: which subsystem or files it anchored in, its major DO-NOT-CHANGE fences, and its riskiest contracts. This risk summary exists because the automated reviewer only checks fidelity and precision — it cannot catch a technical bet that is internally consistent but *wrong*. A short, pointed summary lets the user veto that kind of mistake without reading the whole document.
3. **Hand off to `quirk:writing-plans`.** Planning proceeds from `tech.md` (falling back to the logic spec for anything `tech.md` doesn't cover). There is no separate approval wait between review and handoff — the calling execution skill continues straight into planning once fixes are applied.
