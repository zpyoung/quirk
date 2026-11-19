# Layout

Fix reading order, grouping, rhythm and usable space by changing structure, not decoration.

## When to use

- The screen has no clear primary element, or everything weighs the same.
- Spacing is uniform or arbitrary, and containers are doing the work proximity should do.
- It breaks at narrow widths, with long content or with localized text.

## Read first

- `.quirk/design/system.md`, if it exists. Use its spacing base, density and depth strategy. Don't introduce a second scale.
- Neighboring screens, so the structure stays consistent with them.
- For native targets, `surfaces/ios.md` or `surfaces/android.md` (navigation, insets, adaptation, touch targets).

## Procedure

1. **Diagnose before moving anything.** Look at the screen at several states and widths and answer from evidence:
   - Squint test: blurred, can you still tell the primary element, the secondary one and the major groups, in order?
   - Grouping: are related items close and distinct groups apart, or are boxes compensating for weak proximity?
   - Rhythm: do tight and generous gaps form a cadence, or is one value repeated everywhere?
   - Structure: does the topology fit the content and task? Are repeated columns or card grids truly equivalent, or a framework default? An identical card grid is a P3 check-intent flag: keep it when each item is a distinct object, change it when it is just a list.
   - Density: does information per region fit how often it's used and how hard the decision is?
   - Adaptation: at narrow, middle, wide and zoomed sizes, what reorders, collapses, wraps or scrolls? Does DOM and focus order still match the visual order?
   - Extremes: long content, empty states, overlays, sticky elements and safe areas.
2. **Scan the code.** For web targets, run `python3 "$SKILL_DIR/scripts/detect.py" <files>` and confirm each hit in context. It can't judge hierarchy or rhythm, and a clean run proves neither. Skip it for native code.
3. **State the spatial thesis** in a few lines: the reading path, what groups and what separates, what leads and what supports, the target density, and how structure changes across sizes and input modes.
4. **Apply the simplest structure that expresses it.**
   - Group by meaning with proximity before adding containers or borders.
   - Contrast tight and generous gaps on purpose.
   - Use the project's spacing scale. If none is documented, a 4-unit base gives useful middle steps.
   - Let hierarchy follow product priority, not defaults.
   - Make responsive behavior structural: reorder, collapse, reflow or reveal what matters.
   - Use `gap` for sibling rhythm and container-aware components where a component appears in several contexts.
   - Keep touch targets usable even when the visible mark is small.
   - Use depth only to clarify state or hierarchy. Make optical corrections only after seeing the render.

Repetition helps recognition. Break it only when content or priority changes.

## Preserve

- The visual identity: palette, type, radius and depth treatment. Layout changes structure inside the existing look.
- Copy, behavior and routes.
- Anything outside the target screen or region.

## Verify

When the app can run, check desktop and mobile widths, plus long text, empty and zoomed states.

- The squint test still shows primary, secondary and groups in order.
- Keyboard, touch and screen-reader order match the visual order.
- Spacing values land on the scale.
- Rerun the scan on web code and explain any remaining hit.
- Answer each point with evidence from the render or source, not a bare yes.

## Save to system.md

If spacing roles, container widths or density changed, offer once to update `.quirk/design/system.md`. Create `.quirk/design/` when saving.
