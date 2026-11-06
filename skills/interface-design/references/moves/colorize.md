# Move: colorize

Add color as hierarchy and meaning without replacing the product's identity. In product UI, color mostly encodes action, selection, status and wayfinding.

## When to use

- "This looks gray and lifeless", "status is hard to see", "add some color", "dark mode looks off".
- Hierarchy or state that grayscale obscures.
- A request for more color, not for a new identity. A new identity is a Build job.

Ask only when a binding brand decision can't be inferred.

## Read first

1. `.quirk/design/system.md` if it exists. Its Color section holds the accent, neutrals and semantic roles; extend them, don't replace them.
2. The tokens, themes and assets in the code, and the target in its representative states: default, hover, selected, error, empty, disabled.

## Procedure

1. **Audit what exists.** Identify the confirmed brand colors, the current roles (surface, text, action, semantic), the places where gray hides hierarchy or state, contrast failures, color-only communication, and light and dark requirements.
2. **Set the strategy before editing.** Name the temperature, the contrast range and the dosage. For product UI the default is restrained: neutrals do most of the work, and one accent carries action and state. More color needs a reason tied to meaning.
3. **Build roles, not swatches.**
   - canvas and raised surfaces
   - primary and secondary text
   - action, focus and selection (the single accent)
   - borders and separators
   - success, warning, error and info
   - data categories, when a chart needs them

   Use the project's color space. For a new web palette, prefer OKLCH: vary lightness along a ramp and reduce chroma near white and black. Choose hue from product meaning, not category habit.
4. **Apply at system scale.** Let the accent own the primary action and active state, not scattered decoration. Tint neutrals only if the product hue gives real cohesion; plain gray is valid. On colored surfaces, derive secondary text from the surface or foreground hue, not generic gray. Keep semantic colors consistent across the product.
5. **Don't rely on color alone.** Pair status with text, an icon or position. For data, vary lightness, shape or label as well as hue.
6. **Compose dark mode.** Set surface elevation and contrast on purpose. Don't invert the light theme.
7. **Use tokens.** Add primitives and semantic tokens if the project has a token system, so a theme change remaps roles. Prefer explicit colors over stacked translucent overlays when alpha makes contrast depend on context.

Decoration with no link to hierarchy, state or content is not a color strategy.

## Preserve

- Brand colors and established semantic meanings (red for destructive, for example).
- Layout, copy, type and behavior. This move changes color values and the tokens that hold them.
- The accent's job. Don't spend it on decoration or add a second accent.
- Anything outside the target.

## Verify

- Check computed contrast: body text 4.5:1, large text 3:1, controls, icons and focus indicators 3:1. Cover hover, disabled, overlays, text on images and both themes. Don't judge by eye.
- Simulate common color-vision deficiencies and confirm state still reads.
- Attention lands on the intended action or state. Squint to check.
- The palette holds across quiet, dense, error and empty states.
- Each color has a stable role. A color with no role comes out.
- Hard-coded values are gone from the changed files, replaced by tokens.

## Update system.md

If you added a token, a semantic color or changed the accent, offer once to update the Color section of `.quirk/design/system.md` with the measured values. Create the directory if it is missing.
