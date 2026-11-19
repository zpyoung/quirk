# Typeset

Improve hierarchy, readability and voice in a screen's type, inside its established identity.

## When to use

- Headings, body, labels and data are hard to tell apart, or sizes and weights look arbitrary.
- Text is hard to read: bad measure, tight or loose leading, tiny sizes, awkward wraps.
- Fonts load badly, or too many families and weights ship.

## Read first

- `.quirk/design/system.md`, if it exists. Its type scale, families and weights are authoritative. Work within them.
- The existing type styles and the places they repeat.
- For native targets, `surfaces/ios.md` or `surfaces/android.md`, including platform text scaling.
- For reading surfaces such as docs and help, `surfaces/read.md`.

Product and reading surfaces want stability, scanability and measure first. One well-tuned family and a fixed role scale are often right.

## Procedure

1. **Assess with evidence** (file, selector or computed value):
   - Fit: which faces, weights and roles exist, and is each family needed? An overused default font (`intent-overused-font`, P3, such as Inter, Geist, Roboto or Arial) is a check-intent flag. Keep it with a reason or change it. Don't swap fonts reflexively.
   - Hierarchy: can heading, body, label, metadata and data roles be told apart at a glance? Are neighboring sizes or weights too close to do different jobs?
   - Scale: is there a role scale, or loose values? Do repeated roles match across screens and states?
   - Reading: is body copy 45 to 75 characters wide, with leading and tracking suited to the face, width and surface?
   - Stress: long headings, localized expansion, zoom, narrow containers, missing weights, fallback fonts.
   - Delivery: only used assets loaded, fallback metrics set, no invisible text or reflow.
2. **Scan web code.** Run `python3 "$SKILL_DIR/scripts/detect.py" <files>` and confirm each hit in context (`type-tiny-text`, `type-justified`). A clean run is a floor, not proof. Skip it for native code.
3. **State the roles** the interface needs, the contrast between them, the measure and density, which existing faces are authoritative, and any performance, locale or accessibility limits.
4. **Apply.**
   - Use the fewest families and roles that make the hierarchy obvious. Build contrast from size, weight, space and tone together. Name roles by purpose, not value.
   - Body text at 16px (1rem) on the web unless a dense role or platform convention justifies less. Prose at 45 to 75ch, with more leading as lines get longer.
   - On dark surfaces, add a little leading, a touch of tracking and, if the face needs it, one weight step.
   - Use tabular numerals for data, and code and label features where they help.
   - Load only the weights used, with metric-compatible fallbacks and non-blocking display.
   - Keep browser zoom, user font settings, Dynamic Type and platform scaling working.
   - Pick one paragraph rhythm, spacing or first-line indent, not both.
   - `text-wrap: balance` on headings and short centered blocks, `text-wrap: pretty` on body. Both are progressive enhancements.
   - Break a heading by hand only between phrases, and check it at every width. If a column is too narrow for wrapping to help, edit the copy or widen it. An uneven break can be deliberate, such as a one-word headline. Say which breaks are intended.

Don't add a second family without a role only it can fill.

## Preserve

- The confirmed families and the identity they express, unless the user asked for a new one. A replacement belongs to a redesign, not this move.
- Copy, behavior and everything outside the target.

## Verify

When the app can run, check desktop and mobile widths, zoom and a long-text case.

- Roles are recognizable without reading the words.
- Long text stays comfortable across widths and locales.
- Loading causes no invisible text or jarring reflow.
- Zoom and text scaling still work, and contrast holds.
- Rerun the scan on web code and explain any remaining hit.

## Save to system.md

If you changed the scale, families, weights or role styles, offer once to update the `## Type` section of `.quirk/design/system.md`. Create `.quirk/design/` when saving.
