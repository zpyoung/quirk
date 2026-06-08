# ADHD-Powered Gray-Area Discovery — Design Spec

**Date**: 2026-06-08
**Status**: Approved for implementation
**Scope**: `skills/brainstorming/SKILL.md` only (brainstorming-side wiring change)
**Related**: `docs/specs/2026-06-02-adhd-skill-design.md` (the adhd skill this builds on)

---

## Executive Summary

Today the `adhd` skill is wired into brainstorming only as a **silent advisory bullet** in the "Exploring approaches" step (line 223): the agent privately decides whether to invoke divergent ideation, and the user never sees a choice.

This spec replaces that with an **explicit, user-facing offer at gray-area discovery (step 4)**. Before brainstorming asks "which areas should we clarify?", it offers to run adhd to surface *non-obvious decision areas* the static catalog would miss. Accepted adhd results are merged (and labeled) into the existing multiSelect; the user still picks what to drill into.

The advisory bullet at the approaches step is **removed** — adhd now lives at exactly one point in the flow.

---

## Why Gray-Area Discovery Is the Right Home

adhd exists to surface **non-obvious viable options at a decision point**. A gray area *is* a decision point. Discovery is the highest-leverage place to apply divergent ideation:

| Reason | Detail |
|--------|--------|
| **Patches the weakest part of the flow** | Gray areas currently come from a **static, domain-keyed catalog** — by definition the obvious, generic set. adhd's whole value is going past the obvious. |
| **Frames already fit** | adhd's thinking frames (failure pre-mortem, stakeholder rotation, expert blind spots) *are* blind-spot/ambiguity finders. The frame set maps onto "what decisions am I not seeing?" almost 1:1. |
| **Earliest = cheapest to fix** | A missed decision caught at discovery is cheap; the same one caught after the design is written is expensive. Highest value per dollar. |

### Why NOT the other candidate points

- **Approaches step (the old advisory location)**: targets non-obvious *solutions*. Valuable, but the agent's own 2–3 approaches plus the option-validation research swarm already cover this partially, and it fires later when blind spots cost more.
- **Drill-in refinement**: rejected. Drill-in is the fast, batched path with bounded, deliberately-obvious options (cards/list/grid). adhd is per-decision-point, so running it per drill-in question is N × 5–10× cost and injects minutes of latency into the phase designed to move fast.

---

## Locked Decisions

| # | Question | Answer |
|---|----------|--------|
| 1 | Placement | **Gray-area discovery only** (step 4), before the "which areas to clarify?" multiSelect |
| 2 | Mechanism | **`AskUserQuestion` offer** (not silent agent judgment, not prose) |
| 3 | Trigger | **Always offer when gray-area resolution runs**; suppress on truly-trivial work (same cases where the research swarm is skipped) |
| 4 | adhd prompt framing | **Discovery-framed** — the "decision point" handed to adhd is *"what ambiguous decisions are latent in this request?"*; returned "options" are candidate gray areas |
| 5 | Merge style | **Merged + labeled** — adhd areas appear in the same multiSelect as catalog areas but tagged so the user sees which are the non-obvious finds |
| 6 | Approaches-step bullet | **Deleted** — adhd no longer advertised at step 7 |
| 7 | Process graph / HARD-GATE / checklist structure | **Unchanged** — consistent with the adhd skill spec's locked decision to keep adhd advisory, not a gate |
| 8 | adhd skill / version / tests | **Untouched** — this is a brainstorming-side change only |

---

## Behavior

At the start of step 4, before surfacing gray areas:

1. Agent classifies the domain and assembles the catalog candidates (cheap baseline, as today).
2. **Unless the work is truly trivial**, the agent presents the offer:

   ```
   AskUserQuestion:
     question: "Before we pick what to clarify — want me to run adhd to surface
                non-obvious decision areas specific to this request?
                (~5–10× cost, parallel divergent ideation)"
     header: "Find gray areas"
     options:
       - label: "Use the standard set (Recommended)"
         description: "Surface gray areas from the domain catalog only. No extra cost."
       - label: "Run adhd first"
         description: "Spend 5–10× to surface non-obvious ambiguities the catalog
                       misses; they're merged into the areas you choose from."
   ```

   - **Recommended = the cheap path**, so the default is a one-keystroke "no."
3. If **"Run adhd first"**: the agent invokes the `adhd` skill with a **discovery-framed** delegation prompt — diverge on *latent ambiguous decisions in this request*, not on solutions. adhd returns candidate gray areas.
4. The catalog areas and the adhd-surfaced areas are presented in a **single multiSelect**, with adhd entries **labeled** (e.g. an `adhd:` prefix or a grouped section) so provenance is visible.
5. Drill-in proceeds unchanged on whatever the user selects.

If **"Use the standard set"** (or trivial work): proceed straight to the existing catalog-only multiSelect — identical to today.

---

## Files Changed

| File | Change |
|------|--------|
| `skills/brainstorming/SKILL.md` — Gray Areas section | **Edit** — add a "Step 0 — Offer adhd discovery" before "Step 1 — Surface gray areas," including the offer `AskUserQuestion`, the merge-and-label instruction, and the discovery-framing note for the adhd delegation |
| `skills/brainstorming/SKILL.md` — Checklist step 4 | **Edit** — reword to note the optional adhd pass: "Resolve gray areas — optionally surface non-obvious areas via adhd first, then present via `AskUserQuestion` (multiSelect)…" |
| `skills/brainstorming/SKILL.md` — Exploring approaches (line 223) | **Delete** — remove the advisory adhd bullet |
| Process graph, HARD-GATE, all other steps | **Unchanged** |

No changes to `skills/adhd/*`, no version bump, no new tests.

---

## Decisions Locked (gray-area drill-in)

- **Placement**: gray-area discovery only.
- **Mechanism**: `AskUserQuestion` offer.
- **Trigger**: always when gray-area resolution runs; suppressed on truly-trivial work.
- **adhd framing**: discovery-framed (find ambiguities, not solutions).
- **Merge style**: merged into one multiSelect, adhd entries labeled.
- **Old advisory bullet**: deleted.

## Industry Insights

(Offline mode — no external research swarm dispatched. This is quirk-internal skill wiring with no external best-practice to validate; the design rests on the adhd skill's existing spec and brainstorming's current structure.)

## Deferred Ideas

- **adhd at the approaches step** — surfacing non-obvious *solutions* (the original advisory location). Set aside in favor of the higher-leverage discovery point; could be revisited as a second, separate offer if discovery proves valuable.
- **adhd during drill-in** — per-area divergent ideation on the *answers* to a gray-area question. Rejected on cost/latency grounds; recorded here in case a cheaper variant becomes feasible.

---

## Success Criteria

1. Running brainstorming on non-trivial work presents the adhd discovery offer at step 4, before the gray-area multiSelect.
2. Declining (or trivial work) yields today's exact catalog-only behavior — no regression.
3. Accepting runs adhd with a discovery-framed prompt and merges labeled results into the multiSelect.
4. The approaches-step advisory bullet is gone.
5. Process graph, HARD-GATE, and checklist structure are unchanged.

---

**End of Spec (2026-06-08)**
