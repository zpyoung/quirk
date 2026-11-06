# Move: audit

Run a technical quality audit of a screen or component set and report what you find. Audit documents issues; it doesn't fix them.

This is a code-level check of what is measurable. For judgment about hierarchy, fit and feel, use the critique move.

## When to use

- "Audit this", "check accessibility", "is this ready to ship", "how bad is the responsive situation".
- Before a release, or before choosing which refine moves to run.

## Read first

1. `.quirk/design/system.md` if it exists. Values that differ from it are `drift-system-value` findings at P1.
2. The target files and their tokens and theme setup. If the target is the branch, scope to the files and lines it changed.

## Procedure

1. **Run the detector** over the scope and keep the raw hits: `python3 "$SKILL_DIR/scripts/detect.py" PATH...`. It reads CSS, SCSS, JSX and TSX only. Open each hit in context and drop the ones that don't hold. Never report a hit you haven't confirmed.
2. **Walk the five dimensions**, taking rule ids and severities from `checklist.md`. Score each 0-4.
   - **Accessibility:** contrast (4.5:1 text, 3:1 large text and controls), a reduced-motion path that keeps state changes, missing names, roles or states, keyboard traps and missing focus indicators, heading and landmark structure, divs used as buttons, alt text, unlabeled inputs.
   - **Performance:** layout thrash, animation of layout properties, unbounded blur, filter or shadow, unoptimized or non-lazy images, broad `will-change`, needless imports, avoidable re-renders.
   - **Theming:** hard-coded colors, missing or broken dark variants, wrong or mixed tokens, values that don't update on theme switch.
   - **Responsive:** fixed widths, touch targets under 44px (WCAG 2.5.8 sets a 24 CSS px floor, with spacing, equivalent-control, inline and essential-size exceptions), horizontal overflow, layouts that break at larger text, missing mobile or tablet layouts, and custom drag or slider surfaces that fail under touch (mouse-only handlers, no `touch-action`, drag state that nothing clears on cancel).
   - **Implementation integrity:** repeated shortcuts, drift from system.md, decorative or misleading content, and structure that would fit an unrelated product. Keep deterministic hits separate from judgment, and name the false positives you dropped.
3. **Rank every finding** P0 to P3. P0 blocks task completion. P1 is significant difficulty or a WCAG AA failure. P2 is an annoyance with a workaround. P3 is polish or a check-intent flag. Keep P3 short; a long tail buries what matters.
4. **Group repeats.** If hard-coded colors show up in fifteen files, report one systemic line with the count and one example `path:line`, not fifteen lines.
5. **Say what needs a running app.** Contrast of rendered pairs, overflow, gesture behavior and real performance need a browser or device. List them as unchecked and say what you couldn't produce.

## Output

Lead with one line: the verdict on implementation integrity (pass or fail, and why in a clause). Then findings, grouped under P0, P1, P2, P3 headings, one line each:

```
path:line  rule-id  problem → fix
```

Use the rule id from `checklist.md`. If no rule fits, name a short `<category>-<slug>` id in the same form. Check-intent flags (`intent-eyebrow-label`, `intent-hero-metric`, `intent-side-stripe`, `intent-overused-font`) are P3 and say "justify or change". They are a question, never a defect.

After the findings:

- **Scores:** one small table, five dimensions, each 0-4 with the single worst issue, and a total out of 20. Bands: 18-20 minor polish, 14-17 fix the weak dimensions, 10-13 significant work, 6-9 major overhaul, 0-5 fundamental problems.
- **Systemic patterns:** repeated problems that point to a gap in the system.
- **Working well:** a line or two on what to keep.
- **Not checked:** what needs a running app, and any native checks that were prose-only.
- **Next moves:** the refine moves that address the findings, P0 first, ending with `polish`. Offer to run them one at a time or together.

## Native section

For iOS, Android or adaptive targets, read `surfaces/ios.md` or `surfaces/android.md` first and score against its checks. Don't run the detector; its empty result reads as clean and means nothing on Swift or Kotlin.

Swap the dimensions that don't apply:

- **Accessibility** and **Performance** stay as they are.
- **Appearance and theming:** semantic system colors, dark mode, Dynamic Type or sp scaling.
- **Platform conformance** (replaces Responsive): system gestures kept (edge-swipe back, predictive Back), insets respected (notch, home indicator, keyboard), native navigation, native controls, one icon set (SF Symbols or Material Symbols).
- **Adaptivity** (replaces Implementation integrity): size classes, orientation, keyboard and IME handling, Split View and multi-window, foldable posture.

Findings keep the same line format and ranking. State in the output that the native checks were read from code only.

## Preserve

- The code. Audit edits nothing, adds no files and changes no config.
- The user's scope. Don't audit files outside it.

## Verify

- Every reported line points to a real `path:line` you opened.
- Every detector hit was confirmed or listed as a dropped false positive.
- Nothing is P0 unless it blocks the task.
- The score table matches the findings under it.

## Update system.md

Audit doesn't change tokens. If it surfaced a value the user wants to adopt as the standard, offer once to record it in `.quirk/design/system.md`, creating the directory if needed.
