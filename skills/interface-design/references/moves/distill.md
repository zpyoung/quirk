# Move: distill

Strip a screen to its essence. Remove what doesn't earn its place, and keep the user's path to their goal clear.

## When to use

- "Too busy", "too many options", "simplify this", "clean this up", "it feels cluttered".
- Competing buttons, repeated information, decorative noise, too many colors, fonts or containers, or no clear primary action.

Ask when you can't tell the primary user goal or which features are required. Don't guess what can be cut.

## Read first

1. `.quirk/design/system.md` if it exists. Distill toward its palette, spacing and type scale, never away from them.
2. The target, plus how users reach it and what they do next.

## Procedure

1. **Find the complexity.** Sort it into too many elements, excess variation (colors, fonts, sizes, styles), information overload, visual noise (borders, shadows, backgrounds), unclear hierarchy and feature creep.
2. **Find the essence.** Name the one thing the screen exists to do. Decide what is necessary, what can be hidden until needed, and what can be combined. Expect to cut good ideas.
3. **Cut across these layers.**
   - **Structure:** drop secondary actions and repeated information. Keep one primary action, a few secondary, the rest tertiary or behind disclosure. Merge near-duplicate buttons and group related content.
   - **Visual:** fewer colors (neutrals plus one accent), one type family with few sizes and weights, one spacing scale. Remove borders, shadows and backgrounds that don't serve hierarchy. Flatten nesting and remove containers that only exist as wrappers. Nested cards almost always go.
   - **Layout:** a simpler flow beats a complex grid. Move secondary content inline or behind a control. Pick one alignment and keep it.
   - **Interaction:** fewer choices, smart defaults, inline editing instead of a modal, and a step removed where one can be. One obvious next action.
   - **Copy:** cut filler, not meaning. Active voice. Plain words. Say each thing once.
   - **Code:** delete dead CSS, unused components and orphaned files. Merge near-identical styles. Cut variants that cover few cases.
4. **Keep hierarchy.** Something should still stand out. Removing all emphasis is not simplicity.
5. **Log what you removed.** If you cut a feature or an option, say why and where it is still reachable.

Don't remove functions people need, accessibility (labels and ARIA stay), or information a user needs to decide. Don't make it so sparse it becomes cryptic. Match simplicity to the real complexity of the task: an expert tool can be dense.

## Preserve

- Required functionality and every path to it, even when it moves behind disclosure.
- Accessible names, labels, roles and keyboard behavior.
- Copy meaning, terminology and the incumbent identity.
- Everything outside the target.

## Verify

- A user can finish the main task faster and with less thought.
- Every necessary feature is still reachable. Walk the removed items and confirm each has a home or a recorded reason.
- Hierarchy is clearer: the primary action is obvious.
- Run the detector over the changed files and keep a11y findings at zero.
- Check desktop and mobile widths, and each state you touched.

## Update system.md

If you removed a token, pattern or component variant, or reduced the palette or type scale, offer once to update `.quirk/design/system.md` to match. Create the directory if it is missing.
