# Onboard

Get a new user to the first moment of real value as fast as the product allows.

## When to use

- First-run flows, setup, empty states, feature discovery, tours or in-product help are confusing, too long or missing.
- Users drop off before they reach the point that proves the product is worth their time.

Onboarding does not teach the whole product. It gets people to one result.

## Read first

- `.quirk/design/system.md`, if it exists. Onboarding surfaces use the same patterns, density and tone as the rest of the product.
- The current first-run path and what a new user sees on each screen.

Settle three things before designing. If the codebase doesn't answer them, ask the user:

- The "aha moment": the first result that makes the product useful.
- The users: beginners, power users or a mix, and whether they chose this product or were assigned it.
- How success is measured: completion, time to value, first key action.

## Procedure

1. **Cut to the shortest path.** List what a user must do and learn to reach the aha moment. Defer everything else to the moment they need it.
2. **Prefer the real product over a tutorial mode.** Use working examples, sample data and real controls. Teach one thing at a time.
3. **Make it skippable.** Experienced users get a visible "Skip" or "I'll explore" option, and the product is never blocked behind onboarding.
4. **Design the pieces that fit the situation.**
   - Setup: ask for the minimum, say why each item is needed, use smart defaults.
   - Core concepts: introduce one to three, in plain words, with step progress when there are several.
   - Empty states: say what will appear, why it matters and the one action to start, with a template or example if useful. Handle each kind differently: first use, user cleared it, no results (suggest clearing filters), no permission (say how to get access), load error (say what happened and offer retry).
   - Tooltips and hints: show at first encounter, point at the element, give a short explanation, allow dismissal.
   - Tours: only for complex or significantly changed products. Three to seven steps, focused on workflows ("Create a project", not "This is the project button"), skippable and replayable from help.
   - Help: contextual links, a shortcut reference, and shortcut hints where the control is.
5. **Remember state.** Store seen and dismissed flags so nothing repeats and returning users skip the first-run flow. Server-side or user-scoped storage if the product already has it, otherwise local storage.

Write in a direct, respectful voice. Don't over-explain standard patterns. Keep celebration to a short confirmation, and keep the visual treatment within the system's restrained palette and motion.

## Preserve

- The product's existing look, tone and terminology.
- Existing flows. Add guidance around them instead of rerouting them.
- Copy that isn't part of onboarding.

## Verify

- A new user reaches the aha moment without reading anything optional.
- Skip works at every step, nothing blocks the main UI, and dismissals stick.
- A returning user never sees first-run content again.
- Empty states cover every kind above that applies.
- Focus order, labels and keyboard paths work for every overlay or tour step.
- Watch the numbers you chose: completion, skip rate, time to value. A high skip rate means the flow is too long or not valuable.

## Save to system.md

If you created a reusable pattern (empty state, tooltip, tour step), offer once to record it in `.quirk/design/system.md`. Create `.quirk/design/` when saving.
