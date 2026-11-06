# system.md

The project's saved design decisions live in `.quirk/design/system.md`. Every job reads it first when it exists and holds to it. This file defines what goes in it, when to write it, and how to keep work consistent with it.

## Contents

- [Format](#format)
- [When to save](#when-to-save)
- [Writing the file](#writing-the-file)
- [Holding to it](#holding-to-it)
- [Example: precision and density](#example-precision-and-density)
- [Example: warmth and approachability](#example-warmth-and-approachability)

## Format

One Markdown file with six sections, in this order. Record values, not adjectives.

- `## Direction`: the feel in a sentence or two, the foundation (warm, cool, neutral or tinted), the signature element, and the defaults the project rejects. Add the reason where a future reader would ask.
- `## Depth`: the one strategy (borders only, subtle shadows, layered shadows, or surface-color shifts) with its values, such as the border color and opacity or the shadow definition.
- `## Spacing`: the base unit (4 or 8px), the scale, and the density values that follow from the feel (card padding, row height).
- `## Type`: the family, the size scale with its base, the weights, and the mono face if data uses one.
- `## Color`: the tokens. Foreground in four levels (primary, secondary, tertiary, muted), borders, surfaces and the second neutral, the one accent, and the state colors. Use values or token names, not "a calm blue".
- `## Patterns`: the reusable components with their measurements, one line each. The form is `Button primary — 36px h · 12px 16px pad · 6px radius · 14px/500`.

Keep the file short enough to read in one pass. If a section has nothing yet, leave it out of the file rather than filling it with guesses.

## When to save

Offer once, after Build finishes: "Want me to save these patterns to `.quirk/design/system.md`?" Offer after a Refine only if it changed tokens or patterns. Don't offer after a small edit that used the saved system unchanged, and don't offer twice in one task.

Record a pattern when it is used two or more times, is reusable, or has measurements worth remembering. Don't record one-offs or a prop variation of something already listed.

## Writing the file

Create `.quirk/design/` if it doesn't exist, then write `system.md` inside it. If the file already exists, edit the affected lines in place and don't append a second copy of anything.

The file is meant to be committed so the whole team and every agent session share it. Write it for a teammate who wasn't in this conversation: no first person, no references to what you tried, no task history. Don't read or write design memory anywhere else.

## Holding to it

When system.md defines a value, use it. This is what makes each save pay off later.

- Spacing lands on the saved grid.
- The declared depth strategy is used everywhere, with no second strategy added.
- Colors come from the saved palette, and the accent stays the only accent.
- A documented pattern is reused as written, not reinvented.

If a value in the file is wrong for the new screen, don't deviate quietly. Say so, change the file on purpose, and keep the screens consistent. In review, a value that differs from the file is a P1 drift finding that names both the saved and the found value.

## Example: precision and density

For a dashboard or admin tool used by power users all day.

```markdown
# Design system

## Direction
Precision and density. Cool slate foundation. Built for operators scanning many rows;
information density matters more than lift. Rejecting: card grids, drop shadows, display fonts.

## Depth
Borders only. `rgba(0,0,0,0.08)` standard, slate-200 for row dividers. No shadows.

## Spacing
Base 4px. Scale 4, 8, 12, 16, 24, 32. Cards 12px padding, table cells 8px 12px.

## Type
system-ui. Scale 11, 12, 13, 14 (base), 16, 18. Weights 400, 500, 600.
Mono (SF Mono, Consolas) for data; tabular numerals on every number.

## Color
Foreground slate-900, secondary slate-600, muted slate-400, faint slate-200.
Accent blue-600, for primary action, selection and state only.

## Patterns
- Button — 32px h · 8px 12px pad · 4px radius · 13px/500 · 1px border
- Card — 0.5px solid faint border · 12px pad · 6px radius · no shadow
- Table cell — 8px 12px pad · 13px tabular-nums · 1px faint bottom border
```

## Example: warmth and approachability

For a collaborative or consumer app used in short, focused tasks.

```markdown
# Design system

## Direction
Warmth and approachability. Warm stone foundation. Focused tasks, not cramming;
the screen should feel like a notebook. Rejecting: cold greys, hairline borders, dense tables.

## Depth
Subtle shadows. `0 1px 3px rgba(0,0,0,0.08)` on raised surfaces. Cards have no border.

## Spacing
Base 4px, generous scale 8, 12, 16, 24, 32, 48. Cards 20px padding, inputs 12px 16px.

## Type
Source Sans 3. Scale 13, 14, 15, 16 (base), 18, 20, 24. Weights 400, 500, 600.

## Color
Foreground stone-900, secondary stone-600, muted stone-400, faint stone-200.
Cards white on stone-50. Accent orange-500, for primary action and state only.

## Patterns
- Button — 40px h · 12px 20px pad · 8px radius · 15px/500 · subtle shadow
- Card — no border · 20px pad · 12px radius · white on stone-50 · subtle shadow
- Input — 44px h · 12px 16px pad · 8px radius · 1.5px solid faint border
```
