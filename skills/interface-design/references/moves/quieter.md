# Quieter

Lower the visual intensity of a screen that is too loud, without making it generic.

## When to use

- The user says it's too loud, busy, harsh or overstimulating.
- Many elements compete for attention: heavy weights, saturated color, borders, shadows, motion.

In a product UI, quieter means the tool disappears further into the task: less color, flatter surfaces, less motion, fewer decorations.

## Read first

- `.quirk/design/system.md`, if it exists. Quiet the screen toward the saved direction, depth strategy and single accent. Don't invent a new look.
- The target screen and its neighbors, so you know what is the signal and what is noise.

Work out what the screen is for, who uses it for how long, and what is working. If that isn't clear from the code, ask the user. Don't guess.

## Procedure

1. **Find the sources of intensity.** Saturated color, many colors, high-contrast pairings, too many heavy elements, large type everywhere, borders and shadows on everything, decorative effects, excess motion.
2. **Decide the cuts before making them.** Which one or two elements stay strong, which recede, what can go entirely, and where restraint signals quality.
3. **Cut across these dimensions.**
   - Color: one accent, used for action and state only. Let neutrals do the rest. Desaturate toward 70 to 85 percent where a color is simply too bright. Tint neutrals warm or cool. Where gray text sits on a colored surface, use a darker shade of that color or transparency.
   - Weight: drop heavy weights a step (900 to 600, 700 to 500) and reduce sizes where the hierarchy survives. Build hierarchy from weight, size and space, not from color.
   - Lines and surfaces: thinner or lighter borders, or none where spacing already groups. Remove gradients, glows, stacked shadows and textures that serve nothing. Soften extreme radii.
   - Motion: keep only motion that conveys state, at 150 to 250ms with ease-out. Shorten travel to 10 to 20px. Remove bounce, elastic and decorative loops.
   - Composition: smaller jumps between sizes, rogue elements back on the grid, even spacing.
4. **Check decoration flagged for intent.** Eyebrow labels (`intent-eyebrow-label`) and hero metrics (`intent-hero-metric`) are P3 check-intent items. Keep them if they group navigation or carry the headline number. Drop them if they only decorate.

Quiet is not gray. Gray text on white, one weight everywhere and an undifferentiated grid is generic, and it hides the hierarchy the user needs. Keep a point of view.

## Preserve

- The identity: its accent, typefaces and character. You are lowering intensity, not changing direction.
- Hierarchy, so a few anchors stay clearly strong.
- Affordances. Controls still look interactive, and focus rings and error states stay visible.
- Copy, behavior and everything outside the target.

## Verify

When the app can run, compare before and after at desktop and mobile widths.

- Tasks are still easy to find and complete.
- The screen still has character, not generic gray.
- Long reading is easier on the eyes.
- Contrast still passes for text and controls after desaturating.
- The strongest element is still obvious at a squint.

## Save to system.md

If you changed tokens such as the accent, neutrals, weights, borders or motion timing, offer once to update `.quirk/design/system.md`. Create `.quirk/design/` when saving.
