# Move: critique

Give a design critique of a screen as a design director would: what works, what fails, and what to fix first. It reports; it doesn't edit.

## Contents

- When to use
- Read first
- Procedure
- Output
- Heuristic scoring
- Cognitive load
- Personas
- Preserve
- Verify
- Update system.md

## When to use

- "Critique this", "what's wrong with this screen", "does this feel right", "give me design feedback".
- A judgment call on hierarchy, flow, fit and feel. For measurable code-level checks (contrast, targets, tokens), use the audit move.

## Read first

1. `.quirk/design/system.md` if it exists. Judge the screen against the direction it records, and report values that differ as `drift-system-value` at P1.
2. The target's source. Resolve "the settings modal" or "this page" to a real file first, and prefer the source path over a dev-server URL.
3. If the app can run, look at the screen at desktop and mobile widths. If it can't, say the critique was code-only.

## Procedure

1. **Judge before you scan.** Form your own view first. Is the composition grounded in this product, or could an unrelated product use it unchanged? Then check hierarchy, information architecture, fit, discoverability, typography, color, states, copy and edge cases.
2. **Score the ten heuristics** below, then run the cognitive load checklist. Mark a heuristic n/a with a one-line reason when it can't apply, such as help and documentation on a single reading page.
3. **Walk personas.** Pick two or three from the selection table and trace the main task as each. Name the exact element that fails each one.
4. **Then run the detector** over the target for the deterministic layer: `python3 "$SKILL_DIR/scripts/detect.py" PATH...`. It reads CSS, SCSS, JSX and TSX. Skip it for native code, because an empty result there means nothing. Confirm each hit in context, drop false positives, and note where it agrees with your judgment or caught something you missed.
5. **Rank and write.** Merge everything into one list. Keep the top three to five problems prominent. Be direct and specific: "the submit button", not "some elements". Give a concrete fix for each, never "consider exploring".
6. **Check intent flags last.** Eyebrow labels, hero metrics, side-stripe callouts, Inter or Geist type and card grids are conventional in product UI. Report them at P3 as `intent-*` flags that say "justify or change", and ask what the choice is for. They are never defects on their own.

## Output

Lead with the verdict on design specificity: authored for this product, or interchangeable, and why in two sentences. Then give the overall impression: what works, what doesn't, and the single biggest opportunity. Then findings grouped under P0, P1, P2 and P3 headings, one line each:

```
path:line  rule-id  problem → fix
```

Use the rule id from `checklist.md`. Heuristic and persona findings with no checklist rule take a `<category>-<slug>` id, such as `heuristic-error-recovery` or `persona-keyboard-path`. Put the why in the problem text. Severity: P0 blocks the task, P1 is significant difficulty, P2 is an annoyance with a workaround, P3 is polish or a check-intent flag. If you're unsure between two levels, ask whether a user would contact support. If yes, it is at least P1.

After the findings, add:

- **Heuristic table:** ten rows, score and key issue, with the total over the applicable maximum (4 per scored heuristic, so /32 with two n/a). Most real interfaces land between 20 and 32 of 40. A 4 means genuinely excellent.
- **Cognitive load:** failed checklist items and any decision point with more than four visible options.
- **Persona red flags:** one line per persona.
- **What's working:** two or three specifics worth keeping.
- **Not checked:** what needs a running app or a real device.
- **Questions:** two or three that could unlock a better design ("What would a confident version of this look like?").

Close with one multiple-choice question about where to start, built from the actual findings, and offer the refine moves that match them, ending with `polish`. Put nothing after the question.

## Heuristic scoring

Score 0-4 each: 0 none, 1 major gaps, 2 partial, 3 good with minor gaps, 4 excellent.

| # | Heuristic | Look for |
|---|---|---|
| 1 | Visibility of system status | loading, save and submit confirmation, progress, current location, inline validation |
| 2 | Match to the real world | the user's terms, natural order, recognizable icons |
| 3 | User control and freedom | undo, cancel, a way back, clearing filters, escape from long flows |
| 4 | Consistency and standards | one term per concept, platform conventions, matching components and spacing |
| 5 | Error prevention | confirmation before destruction, constrained inputs, good defaults, draft recovery |
| 6 | Recognition over recall | visible options, labeled icons, recent items, autocomplete |
| 7 | Flexibility and efficiency | shortcuts, bulk actions, customization that doesn't burden novices |
| 8 | Aesthetic and minimalist design | only needed information, clear hierarchy, no decorative competition |
| 9 | Error recovery | plain-language errors, the specific problem, a fix, work preserved |
| 10 | Help and documentation | findable, task-focused, contextual, concise |

Bands for the full /40: 36-40 excellent, 28-35 good, 20-27 acceptable, 12-19 poor, 0-11 critical. With n/a rows, read the band off the percentage: 90% and up excellent, 70% good, 50% acceptable, 30% poor, below that critical.

## Cognitive load

Three kinds: the task's own complexity (structure it), extraneous load from bad design (remove it all), and the effort of learning a pattern (support it with consistency and feedback).

Count the failures on these eight. Zero or one is low load. Two or three needs attention soon. Four or more is a critical fix.

- Single focus: no competing elements around the primary task.
- Chunking: information in groups of about four or fewer.
- Grouping: related items sit together by proximity, border or shared background.
- Visual hierarchy: what matters most is obvious.
- One thing at a time: a single decision before the next.
- Minimal choices: four or fewer visible options at a decision point.
- Working memory: nothing from a previous screen is needed to act on this one.
- Progressive disclosure: complexity appears when the user needs it.

Working memory holds about four items. Four or fewer is fine, five to seven is pushing it, eight or more makes users skip, misclick or leave. In practice: one primary action, one or two secondary, the rest in a menu; no more than about five top-level navigation items; four or fewer sibling choices per sidebar level.

Common failures: a wall of options with no hierarchy, a memory bridge between steps, hidden navigation with no current-location cue, jargon, uniform visual weight, the same action behaving differently in different places, several simultaneous inputs, and information scattered across screens or modals.

## Personas

Trace the main task as two or three of these. Report specific broken elements, not generic descriptions.

- **Alex, power user.** Skips onboarding, wants shortcuts and bulk actions, leaves if anything is slow or patronizing. Red flags: forced tutorials, no keyboard path for primary actions, unskippable animation, one-at-a-time flows where batch is natural, confirmation on low-risk actions. Test: can Alex finish the core task in under a minute, and dismiss every modal with Esc?
- **Jordan, first-timer.** Reads everything, hesitates, takes labels literally. Red flags: icon-only navigation, unexplained jargon, no visible help, unclear next step after an action, no sign an action succeeded. Test: is the first action clear in five seconds?
- **Sam, accessibility-dependent.** Keyboard and screen reader, possibly low vision, zooms to 200%. Red flags: click-only interactions, missing or invisible focus, meaning carried by color alone, unlabeled fields, time limits without extension, custom components that break screen-reader flow. Test: can the whole primary flow run keyboard-only with announced state changes?
- **Riley, stress tester.** Pushes the edges: empty, one, a thousand items, very long strings, emoji, right-to-left text, refresh mid-flow, two tabs. Red flags: features that silently fail, errors that expose internals or break the UI, empty states with no guidance, lost data on refresh.
- **Casey, distracted mobile user.** One thumb, interrupted often, slow connection. Red flags: key actions at the top of the screen, no state persistence across interruptions, big text inputs where a selection would work, heavy assets, tiny or crowded targets.

| Surface | Start with |
|---|---|
| Dashboard, admin, data-heavy | Alex, Sam |
| Form-heavy or wizard | Jordan, Sam, Casey |
| Onboarding | Jordan, Casey |
| Checkout or transactional | Casey, Riley, Jordan |
| Docs and reading | Sam, Jordan, Casey |

If `.quirk/design/system.md` names a specific audience, add one persona for it. Don't invent audience details when it doesn't.

## Preserve

- The code and the design. Critique edits nothing and writes no files.
- The user's scope and their stated intent. If a flagged choice is intentional, record it as intentional and move on.

## Verify

- The verdict, the scores and the ranked findings agree with each other.
- Every line points to a `path:line` you opened. Every detector hit was confirmed or dropped.
- Each top issue has a concrete fix and a reason users would care.
- The report names what stayed unchecked, and the question comes last.

## Update system.md

Critique changes no tokens. If the critique settled a design decision the user wants to keep, offer once to record it in `.quirk/design/system.md`, creating the directory if needed.
