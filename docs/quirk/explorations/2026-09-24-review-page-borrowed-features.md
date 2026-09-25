> 🧭 EXPLORATION — not a spec. No locked decisions; nothing here is build-ready.

# Exploring: reviewer-experience features from archify, pr-lens, and goal-workflow for the interactive logic-spec review page

**Date**: 2026-09-24 · **Emphasis**: blended · **Intensity**: 0.5 (Exploratory)

## Framing
Would features the reviewer sees in [tt-a1i/archify](https://github.com/tt-a1i/archify), [coldteadotai/pr-lens](https://github.com/coldteadotai/pr-lens), and [smallnest/goal-workflow](https://github.com/smallnest/goal-workflow) improve `review.html` (`skills/writing-specs/interactive/app/`)? The backend verification side (hashing, integrity, diagnostics) was assessed earlier and is out of scope here. Scoping was delegated ("you decide"). The pains it targets:
- where to start across the views
- what changed between rounds
- following derivation chains, and what a dispute affects
- sharing with people who didn't review
- how dense the page is
- understanding the behavior itself

Constraints held fixed:
- The page stays a self-contained offline file.
- Motion is purposeful only and respects reduced-motion.
- v2's out-of-scope list stands: no hosting, no review server, no review-behavior signals, no per-requirement derivation tick (OOS-05), no per-behavior pipeline.

## What was explored
- archify's viewer: guided views, semantic lens, focus and reach panel, route probe, motion governor, export and share cards, and deep links.
- pr-lens's reviewer surface:
  - the walkthrough data format and authoring rules
  - change status (delta) on every element, with unchanged neighbours kept
  - "hero" emphasis
  - SMIL pulse pacing
  - the drill-down view tree
  - the sticky comment
  - stale-step pruning

  Its interactive canvas is closed source, so only the data format and the static renderer could be read.
- goal-workflow's presentation: the docs site (`docs/index_en.html`), the `design-it` template, `/prd` lettered multiple-choice questions, and `/to-issues` "Blocked by" / "Frontier" framing.
- Other review tools: Reviewable, GitHub "Viewed", Chromatic, Figma Dev Mode status, Example Mapping, guided-tour UX, and the SmartBear/Cisco review-size study.
- An inventory of the current page, with spot checks against the source.
- Out of scope: the backend mechanics already logged. Post-execution disposition (DEFER-11) and the falsifiability rubric (DEFER-12) are not reviewer-page features.
- _Steered:_ the user delegated all scoping choices ("you decide"), so the idea-landscape checkpoint ran without a pause. Every direction below is left open for the user to react to.

## Findings / Idea landscape

### Theme: what the page already has
- Stage-scoped tabs. Stage 1 has five tabs; stage 2 has up to ten, some shown only when the data exists. — `app/src/App.tsx:131-154`
- Gate progress ("X of Y review gates still open") and a badge per tab counting open actions. — `App.tsx:235-245`, `App.tsx:304-306`, `views/sign-off-view.tsx:75-86`
- "Changed since you reviewed" markers based on hashes. Flagged and withdrawn requirements also get this marker. — `review-state.ts:270-289`, `views/shared.tsx:58-61`
  - The marker says *that* something changed, not *why*. A flagged requirement shows the same generic marker as an edited one, and does not name the reopened scenario.
- Clickable item IDs in prose (`views/item-links.tsx:45-49`), dialogs for items, and state-machine transitions and blind-spot chips that open details (`views/state-machine-diagram.tsx:160,194`).
- **Missing:**
  - No deep links. There is no `location.hash` or URL handling anywhere in `app/src`.
  - No guided reading order.
  - No view of what a dispute would affect.
  - No animation that needs a reduced-motion guard.

### Theme: what the repos actually offer
- **archify guided views.** Up to five `{id, label, focus:[ids], note}` chapters. The chapter rail and the preview of what changes between chapters are derived automatically, and chapters can be deep-linked with `#view=`. — `archify/references/viewer-runtime.md`, `viewer/guided-views.js`, `archify/examples/web-app.architecture.json`
- **archify semantic lens.** It dims (CSS opacity) rather than removes, so the layout stays as context. Pick one or two kinds; the kinds are read off existing node data. — `viewer/semantic-lens.js`
- **archify focus panel.** Shows upstream and downstream reach counts one hop out, along directed edges only, with a copyable `#focus=&reach=` link. — `viewer/focus.js`
- **archify motion governor.** One Still/Live switch. Motion is paused if the reader toggles it off, if the OS asks for reduced motion, or while a higher-priority interaction is running. — `viewer/motion-governor.js`
- **archify export rule.** Exports strip all viewer state and are "communication assets, never the source of record." — `viewer/export.js`, `viewer-runtime.md`
- **pr-lens walkthroughs.**
  - 2–12 ordered steps, 3–7 recommended.
  - Each heading is at most 48 characters and must use change words: "a heading that could have been true before the PR is not a change heading."
  - Each body is at most 140 characters.
  - `stage` names the diagram to show; `focus` selects what stays lit while everything else dims.
  - — `packages/schema/src/walkthrough.ts`, `packages/agent-skill/SKILL.md`
- **pr-lens stale-step pruning.** A step whose focus loses its last item is dropped rather than widened to "everything." If fewer than two steps survive, the whole walkthrough is discarded. — `pruneWalkthrough` in `packages/schema/src/walkthrough.ts`
- **pr-lens context rules.**
  - Unaffected neighbours are marked `unchanged` rather than omitted, so the reader can see how far a change reaches. — "Include what did not change," `packages/agent-skill/SKILL.md`
  - Hero emphasis is capped at 1–2 because "more than a couple … stops meaning anything." — `packages/schema/src/graph.ts`
- **pr-lens pulse pacing.** Exactly one dot in flight, and the cycle is capped at 16 steps. — `packages/renderer/src/svg/pulse.ts`, `design.ts`
- **goal-workflow** has little here. Its docs are static; the pipeline SVG and hover glow are decorative. Two ideas carry over: "Frontier" (items with no open blockers, `skills/to-issues/SKILL.md:213-236`) and lettered multiple-choice clarifications (`skills/prd/SKILL.md:41-63`).
- **Other tools:**
  - GitHub's "Viewed" mark resets when the file changes.
  - Reviewable won't allow approval until every blocking discussion is resolved.
  - Figma status flips to "Changed" after an edit.
  - Example Mapping uses card colour to show which rules are under-specified.
  - SmartBear/Cisco found defect detection falls sharply as review size grows.
  
  The tour completion-rate and "40% comprehension" figures come from vendor and agency blogs and are **unverified**.

### Direction: round walkthrough — "what I did with your feedback"
On every re-render, Claude writes a short `walkthrough[]` of 3–7 steps. Each step names a view, the item IDs to keep lit, and a heading describing the change ("Split SC-4 into two scenarios", "REQ-07 now derives from C-2"). The page plays it as a dismissible strip that dims everything outside each step's focus.
*why this might actually work:* after round 1 the reviewer's question is "what did you do with my feedback?" `changedSinceReviewIds` already knows *which* items changed. pr-lens's rule that headings describe the change forces Claude to say *what* changed, and that is the missing half.
*surfaced by:* analogical transfer (pr-lens) · *sits at intensity:* Grounded

### Direction: first-read chapters for stage 1
On the first render only, Claude authors at most five archify-style chapters, such as "the risky behavior," "where the assumptions bite," and "the non-goals." Each is a `{label, focus, note}` over existing IDs, with no new content. The chapter rail doubles as a reading order across the tabs.
*why this might actually work:* the page has no entry point beyond gate counts, and gates say what is *unfinished*, not what is *important*. Capping chapters at five and building them from existing IDs keeps authoring cost near zero and prevents the tour from becoming a second spec.
*surfaced by:* analogical transfer (archify) · *sits at intensity:* Grounded

### Direction: preview what a dispute would affect
While the reviewer drafts a scenario dispute, the page previews what reopening the scenario would do. Requirements that would be withdrawn show solid, requirements that would be flagged show outlined, and everything else dims but stays in place. Flagged requirements get a reason chip ("SC-4 reopened").
*why this might actually work:* the consequence is already computed (`requirementStatus`, `review-state.ts:264-268`), but the reviewer only sees it after a round trip with Claude. Showing it before submission lets them choose between a derivation dispute and a scenario dispute knowingly. The reason chip fixes the generic marker on flagged requirements.
*surfaced by:* analogical transfer (archify lens + pr-lens unchanged-as-context) · *sits at intensity:* Grounded

### Direction: deep links as a bridge between chat and the page
Hash state such as `review.html#view=board&focus=REQ-07` works on a `file://` page. Claude's round summary in chat could link each item it mentions, and the reviewer could paste a link back ("this one is wrong") without retyping IDs.
*why this might actually work:* the review loop happens half in chat and half in the page, with nothing linking them today. archify shows hash links need no backend. The cost is small: parse the hash on load and update it when navigating.
*surfaced by:* analogical transfer (archify) · *sits at intensity:* Grounded

### Direction: play a scenario through the state machine
Selecting a scenario animates one token along its Given → When → Then path on the state-machine diagram, pr-lens-style with exactly one dot in flight, under a single Still/Live switch that obeys reduced-motion. A When with no matching transition stops the token visibly.
*why this might actually work:* Given/When/Then is a path, and the diagram already links transitions to requirement IDs (`views/state-machine-detail.tsx:24-40`). A token that can't move exposes a missing transition, making it a blind-spot detector, not decoration.
*surfaced by:* analogical transfer + assumption reversal ("the diagram is only for reading") · *sits at intensity:* Exploratory

### Direction: before/after for changed items
"Changed since you reviewed" becomes a word-level before/after of the Given/When/Then or requirement text, in the spirit of Chromatic's baseline comparison. The renderer would embed the previously seen text for each changed item. That text would come from a render history kept locally in the gitignored spec folder, since the export carries only hashes (`review-state.ts:175-189`).
*why this might actually work:* a marker without the change forces the reviewer to re-read the whole item from memory. The diff is exactly the part their earlier approval didn't cover.
*surfaced by:* analogical transfer (Chromatic, pr-lens `Payload.before`) · *sits at intensity:* Exploratory

### Direction: collapse the tabs into one review queue
Add a single "Next up" view. It flattens the open gates into one ordered list of decisions across all tabs, using goal-workflow's "Frontier" idea (only decisions with nothing blocking them). The existing views stay as reference.
*why this might actually work:* gates are already computed (`review-state.ts:553-599`), so the queue is those gates listed item by item. It attacks density directly: the reviewer works one list instead of choosing among ten tabs.
*surfaced by:* contrarian inversion ("more views help") · *sits at intensity:* Bold

### Direction: capped "look here" from Claude
Claude marks at most two items per render as the ones it is least sure of, using pr-lens-style hero emphasis. The cap is enforced by `validate`.
*why this might actually work:* the impact × certainty view spreads attention across every item. A hard cap keeps the signal meaningful ("stops meaning anything" past a couple), and it is honest provenance from the author, not a signal about how the reviewer behaves.
*surfaced by:* analogical transfer (pr-lens hero) · *sits at intensity:* Exploratory

_Rejected at the quality gate:_
- **A share card or PNG export of sign-off.** `logic.md` already serves readers who didn't review, so it had no insight left.
- **Per-item "viewed" marks.** They restate OOS-05 (no derivation tick) and edge into the review-behavior signals v1 excluded.
- **goal-workflow's pipeline SVG and hover glow.** Decorative.

## Tensions & trade-offs
- **Guidance vs. independent judgment.** The walkthrough, the chapters, and the "look here" marks all have Claude directing the reviewer's attention. That speeds review but can anchor it: the reviewer checks what Claude pointed at and skims the rest. The review queue and the dispute preview guide by *structure* (gates, dependencies), not by Claude's framing.
- **Authored vs. derived.** The walkthrough and chapters are extra JSON Claude must write and `validate` must check, so they are new ways to go stale. The dispute preview, deep links, before/after, and the queue derive from data that already exists. pr-lens's pruning rule reduces staleness but doesn't remove it.
- **Offline, deterministic render vs. history.** Before/after needs prior text, but `render` is deterministic for identical input. Embedding render history makes output depend on local history, and adds state the v2 design deliberately kept in the export.
- **Density vs. more features.** Every direction except the queue adds UI to a page whose density is one of the stated pains. The queue removes navigation but adds a view.
- **Motion vs. a quiet page.** Scenario playback is the only direction needing animation. It pulls in a motion governor for one feature.

## Challenge notes
- **Round walkthrough.**
  - Steelman: it is the only direction that answers "what did you do with my feedback" in Claude's words.
  - Strongest counter: Claude already says this in chat each round, so the page would duplicate it, and a heading describing the change can still misdescribe it.
  - Would be disproven if: reviewers read the chat summary and never open the strip, or headings drift from the actual hash changes. A `validate` check that each step focuses only changed IDs would catch the drift.
- **First-read chapters.**
  - Steelman: they give an entry point at almost no cost.
  - Strongest counter: tours get skipped, and five chapters over ten tabs may just reorder the tabs.
  - Would be disproven if: reviewers go straight to Sign-off gates anyway.
- **Dispute preview.**
  - Steelman: it uses existing logic to prevent a wasted round trip.
  - Strongest counter: disputes are rare (they are the exception path, per OOS-05's rationale), so it is polish on a cold path.
  - Would be disproven if: real specs seldom see scenario disputes.
- **Deep links.**
  - Steelman: the cheapest direction, and it touches the chat half of the loop.
  - Strongest counter: some browsers restrict hash handling or opening pages on `file://`, and Claude-printed links to a local file may not be clickable in every terminal.
  - Would be disproven if: `file://` links with a hash don't open from the terminals the reviewer uses.
- **Scenario playback.**
  - Steelman: it turns the diagram into a checker.
  - Strongest counter: scenarios are prose, not machine-linked to transitions, so the token needs a scenario → transition mapping that doesn't exist yet. Adding one means more authored data and more ways to go stale.
  - Would be disproven if: that mapping can't be derived reliably.
- **Before/after.**
  - Steelman: it answers "changed how?"
  - Strongest counter: it breaks deterministic render and pulls history into the renderer. The export would need to carry item text, which inflates it.
  - Would be disproven if: most changes are small enough that the marker suffices.
- **Review queue.**
  - Steelman: it attacks density at the root.
  - Strongest counter: some decisions (scope placement) need the board's spatial context, which a flat list loses.
  - Would be disproven if: the reviewer keeps leaving the queue for the board.
- **"Look here".**
  - Steelman: honest, capped, and cheap.
  - Strongest counter: it overlaps impact × certainty, and anchoring risk is highest here.
  - Would be disproven if: its picks match the top-right of impact × certainty every time.

## Open questions & gaps
- pr-lens's interactive player (step progression, marking steps seen) is closed source at prlens.dev. Only the data format was studied.
- Whether hash deep links and `window.open` behave consistently on `file://` in the browsers and terminals the reviewer uses. Not tested.
- How often scenario disputes actually happen in real v2 specs. This decides whether the dispute preview is worth it.
- Whether a scenario → transition mapping can be derived from existing `logic.json` data or would need new authored fields.
- How the round walkthrough relates to Claude's chat summary: replace, mirror, or supersede.
- DEFER-13 (agent-authored walkthrough) covers the first two directions. Any follow-up should update that entry rather than add a new one.

## Sources
- archify guided views, lens, focus, route probe, motion governor, export — `archify/references/viewer-runtime.md`, `viewer/{guided-views,semantic-lens,focus,route-probe,motion-governor,export}.js` in https://github.com/tt-a1i/archify
- pr-lens walkthrough format, pruning, hero cap, unchanged-as-context, pulse pacing — `packages/schema/src/{walkthrough,graph}.ts`, `packages/agent-skill/SKILL.md`, `packages/renderer/src/svg/pulse.ts` in https://github.com/coldteadotai/pr-lens (interactive canvas closed source — not verified)
- goal-workflow presentation — `docs/index_en.html:830-935`, `skills/design-it/SKILL.md:10-12`, `skills/prd/SKILL.md:41-63`, `skills/to-issues/SKILL.md:213-236` in https://github.com/smallnest/goal-workflow
- Current page behavior — `skills/writing-specs/interactive/app/src/` (`App.tsx`, `review-state.ts`, `views/*`), verified by grep in this session
- GitHub "Viewed" reset — https://codewithhugo.com/github-review-reset-viewed/
- Reviewable dispositions — https://docs.reviewable.io/files.html
- Figma Dev Mode status — https://help.figma.com/hc/en-us/articles/26781702258583-Dev-Mode-statuses-and-notifications
- Example Mapping — https://cucumber.io/blog/bdd/example-mapping-introduction/
- SmartBear/Cisco review-size study — https://mikeconley.ca/blog/2009/09/14/smart-bear-cisco-and-the-largest-study-on-code-review-ever/
- Guided-tour completion and comprehension percentages — https://userpilot.com/blog/product-tour-examples/, https://metabole.studio/en/blog/scrollytelling (vendor blogs — unverified)

---
*Exploration only. To build a direction: invoke `quirk:brainstorming` → an execution skill (which authors a tech spec when warranted, then plans in context).*
