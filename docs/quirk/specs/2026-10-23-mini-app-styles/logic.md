# Logic spec: `building-mini-apps` styles, looks drawn from the ten studied apps

## Status & amendments

**Status**: Approved · Tech spec: authored (`tech.md`; tier gate fired: scripts, gallery, all ten blocks and SKILL.md)

**Amendments:**
- 2026-10-23: SC-4 now says the user's own files stay unchanged, rather than every other file. A
  switch may add a style's font packages (package.json, lockfile) and rewires `index.css`'s font lines
  once. Found while writing the tech spec. Approved by the user.
- 2026-10-23: SC-7 holds focus rings to 3:1 and treats borders and input outlines as decorative.
  Neutral House's locked values (border 1.27:1, input 1.37:1 in light) could not meet 3:1 without
  moving the default look. Approved by the user.
- 2026-10-24: An eighth style, Ink Panel, studied from Sentry, is added by
  [its own spec](../2026-10-24-ink-panel-style/logic.md), which also extends the extra rules with
  motion, component hooks and a high-contrast fallback. SC-3 no longer forbids an eighth style; it
  forbids inventing one. SC-6 lists eight names. Counts of seven elsewhere describe what this spec
  added. Approved by the user with the Ink Panel design.

Every mini app the skill builds today looks the same, because the skill ships one neutral house style
and its spec bans copying the studied apps' looks
([building-mini-apps](../2026-10-22-building-mini-apps/logic.md), "One neutral house style" and the
brand-assets non-goal). I want the apps to be able to look like the kind of app they came from: a
reading journal that feels like a calm paper notebook, a data tool that feels dense and dark.

This spec adds seven named styles drawn from the ten studied apps. A style captures an app's
character, not its brand: no logos, icons, copy, exact brand colors or proprietary fonts. It
supersedes the house-style decision and narrows the brand-assets non-goal of the building-mini-apps
spec. Behavior, keys and layout are unchanged.

## Conceptual model

**A style is a named set of look decisions and nothing else.** It sets:

- light and dark color tokens (the shadcn variables plus the skill's own `--mini-*` ones)
- the radius
- three font stacks: interface text, titles, and data (numbers, code, table cells)
- border and shadow weight
- optionally, a few extra rules that may only target named hooks the blocks expose, such as the
  sidebar surface or a list row

A style never changes layout, key bindings, density or behavior. Each app has exactly one style.

The seven styles, and the apps each was studied from:

| Style | Character | Studied from |
|---|---|---|
| Neutral House | Calm, neutral greys, one restrained slate-teal accent (today's default) | none |
| Calm Paper | Warm paper surface, serif titles, almost no chrome, ink-black primary, pill chips | Granola, Craft |
| Airy White | White canvas, big bold titles, whitespace, one soft blue call to action | Notion, Things 3 |
| Cool Tool | Cool grey utility UI, hairline rows, tinted group bands, one muted blue-violet | Linear, Figma |
| Dense Dark | Charcoal, flat, solid selection color, monospace data cells | TablePlus, Obsidian |
| Glass Launcher | Translucent blurred panel, large radius, near-achromatic with a warm accent | Raycast |
| Split Tone | Dark sidebar on a light canvas, one saturated rose accent, edge-striped items | Fantastical |

Every style ships in light and dark, including the dark-first ones.

**A style reference** (`references/styles/<slug>.md`, one per style) is the written half, the same way
each pattern has a reference. It gives the style's character, which kinds of apps it suits, the apps it
was studied from with the frames behind each observation, and the brand traits it deliberately leaves
out, such as Linear's indigo or Raycast's red-lit gradient. App names appear only here and in the style
table above, never in a generated app.

## Data flow

Each style has one source file, a JSON description of its tokens, fonts, radius and extra rules. A
build script turns every source into CSS twice: once for an app, and once scoped so the gallery can hold
all seven at the same time. The same script checks contrast from the source values and fails if any
style misses WCAG AA in light or dark. A freshness check fails when the generated CSS no longer matches
its source, the same way the registry's check works today.

When a mini app is scaffolded with a style, the chosen style's CSS is written into the app as its tokens
file, so the base, the blocks and the stylesheet wiring are unchanged. If the style uses a bundled open
font, that font's npm package is installed too, so the app still works offline. Changing an app's style
later overwrites that one tokens file, then rebuilds.

The gallery loads every style and switches between them from a picker in its top bar, beside the
existing light/dark toggle.

## Key decisions & rationale

- **Character, not copy.** A style keeps an app's mood (light or dark lean, radius, type feel, how loud
  the accent is) and re-derives its colors. A specific combination of styling choices can be protected
  trade dress, so a pixel match is the exposed part.
- **Descriptive names.** "Cool Tool", never "Linear". Naming a preset after a product implies
  affiliation, the thing marketplace brand rules forbid.
- **Shifted accents.** A style keeps its source's color family but not the exact brand value: Cool Tool
  uses a blue-violet, not Linear's indigo.
- **System fonts first, a few bundled open fonts.** Most styles use `system-ui`, which renders as the
  user's own OS font without the app distributing it. A style that needs a serif or editorial face
  bundles an openly licensed font from npm. SF Pro can't be distributed in web content, so no style
  ships it.
- **Picked at scaffold time, one style per app.** Apps stay light and keep one look. No runtime style
  switcher ships in an app.
- **The agent picks when the user doesn't.** It chooses the style that fits the domain and says which
  and why before building, along with the other names.
- **A script swaps an existing app's style.** It matches how patterns are added to an app later.
- **A style may carry a small stylesheet**, aimed only at named hooks. This is what makes the glass
  blur, the dark split sidebar and the mono data cells possible. It means every style must be checked on
  every block.
- **JSON source compiled to CSS.** One source per style lets the contrast check read real values, and
  the app copy and gallery copy can't drift apart. Hand-written CSS would need two copies and a CSS
  parser. shadcn registry theme items were rejected: their fonts are Google-hosted only, and re-running
  them to swap a theme is undocumented and was reported to corrupt Tailwind v4 stylesheets.
- **Done means it passes AA and survives every block.** Each style passes the automated contrast check
  in light and dark, and has been viewed on all ten blocks in the gallery with a screenshot kept as
  evidence.

## Behavior & scenarios

1. **SC-1: No look is named, so the agent picks one**
   - **Given** the user asks for "a mini app to keep a reading journal" and says nothing about looks
   - **When** the agent names its patterns, before building
   - **Then** it also names one style, gives one line on why it fits, lists the other style names, and
     says the user can ask to switch. It scaffolds with that style. The final report names the style.
   - **Walkthrough:**
     1. The agent picks doc-collections and list-peek* for the journal.
     2. The agent writes: "Style: Calm Paper, since it suits a reading journal. Others: Neutral House,
        Airy White, Cool Tool, Dense Dark, Glass Launcher, Split Tone. Say the word to switch."
     3. The agent scaffolds **journal-app*** with that style.
   - **Data after:** **journal-app**: ✓ Calm Paper tokens in its tokens file; ✓ the serif title font
     installed; ✓ builds clean

2. **SC-2: The user names a studied app**
   - **Given** the user asks for a task tracker that "looks like Linear"
   - **When** the agent chooses the style
   - **Then** it maps the request to the style studied from that app and says so, including that the
     style keeps the feel and not the app's exact look. The app's name never appears in the generated
     app.
   - **Walkthrough:**
     1. The agent finds Linear in the Studied from column, next to Cool Tool.
     2. The agent writes: "I'll use Cool Tool, the style drawn from Linear and Figma. It keeps the feel,
        not Linear's exact look."
   - **Data after:** **tracker-app***: ✓ Cool Tool tokens; ✗ no occurrence of "Linear" in the app's
     files

3. **SC-3: The user names a look the styles don't cover**
   - **Given** the user asks for an app that "looks like Things 3 but green"
   - **When** the agent chooses the style
   - **Then** it maps "Things 3" to Airy White as in SC-2 and says so. It doesn't invent a new style.
     For the "but green" part, it tunes the accent in the app's tokens file itself and says so, including
     that the app no longer matches a shipped style, so a later style switch needs force (SC-5).
   - **Walkthrough:**
     1. The agent finds Things 3 next to Airy White and writes the SC-2 line.
     2. The agent scaffolds **tasks-app*** with Airy White.
     3. The agent changes the accent tokens, light and dark, to a green* and reruns the contrast check on
        the app's tokens file.
     4. The agent writes: "Airy White with a green accent. That's now a hand edit, so switching styles
        later will ask you to confirm."
   - **Data after:** **tasks-app**: ✓ Airy White tokens with a green accent; ✓ passes AA in light and
     dark; ✗ matches no shipped style

4. **SC-4: Switching an existing app's style**
   - **Given** an existing mini app built with Neutral House, with its own domain edits in the demo
     files
   - **When** the user asks to switch it to Dense Dark
   - **Then** the style script overwrites the app's tokens file, installs any font package the new style
     needs, rewires the stylesheet's font lines if they aren't already, rebuilds, and checks that the dev
     server starts. Files the user edited, such as the book demo, are unchanged.
   - **Data before:** **books-app***: Neutral House tokens file; edited book demo
   - **Data after:** **books-app**: ✓ Dense Dark tokens file; ✓ book demo unchanged; ✓ builds clean

5. **SC-5: Switching when the tokens file was hand-edited**
   - **Given** the user changed the accent by hand in the app's tokens file, so it matches no shipped
     style
   - **When** the style script runs without the force option
   - **Then** it refuses, names the tokens file, and says that rerunning with force discards the hand
     edits. Nothing changes. With force, it switches as in SC-4.

6. **SC-6: An unknown style name**
   - **Given** the user or the agent asks for a style called "neon"*
   - **When** the scaffold or style script runs
   - **Then** it exits with the bad-arguments code and lists the eight valid style names. No app is
     created or changed.

7. **SC-7: A style fails contrast**
   - **Given** a style's dark muted text is edited to a value below 4.5:1 against its background
   - **When** the style build runs
   - **Then** it fails, naming the style, the mode, the two tokens and the measured ratio. Semi-
     transparent tokens are measured as blended over the background they sit on. Focus rings are held
     to 3:1; borders and input outlines are decorative and not checked.
   - **Details:**

     | Style | Mode | Pair | Ratio | Needed |
     |---|---|---|---|---|
     | Dense Dark | dark | muted text on background | 3.9:1* | ✗ 4.5:1 |

8. **SC-8: Browsing styles in the gallery**
   - **Given** the gallery is running
   - **When** the user picks Glass Launcher in the top bar and toggles dark
   - **Then** every pattern page renders in Glass Launcher's dark tokens and extra rules, and switching
     back to Neutral House restores the default look with nothing left behind

## Scope & non-goals

In scope:

- The seven styles: their sources, generated CSS and style references.
- The style build with its contrast and freshness checks.
- Choosing a style when scaffolding, and a script to switch an existing app's style.
- The gallery's style picker.
- Named style hooks added to the blocks, with no behavior change.
- SKILL.md updates: the style index, how the agent picks and announces a style, and the replacement for
  the "one neutral house style" rule.
- Amending the building-mini-apps spec to point at this one.

Not in scope:

- Logos, icons, illustrations, copy, exact brand colors or proprietary fonts from any studied app.
- Loading fonts from the network.
- Density as a style property or as its own option. It needs every block moved onto size tokens first
  (see Deferred Ideas).
- A style switcher inside a generated app.
- One style per studied app, or user-authored styles.
- APCA as a pass/fail gate. It may be reported for information.

## Decisions Locked

**How close to each app**
- Each style captures the app's character; colors are re-derived, not sampled.
- Styles have descriptive names; the source app is named only in the style reference.
- Accents keep the source's color family with a shifted hue.
- Fonts are system stacks plus a few bundled open fonts.

**Where the style is picked**
- At scaffold time, one style per app.
- With no look named, the agent picks a style to fit the domain and says why.
- A script swaps an existing app's style.
- The gallery has a style picker in its top bar.

**What a style covers**
- Colors, radius, fonts, and border and shadow weight.
- Density is deferred.
- Every style ships in light and dark.
- A style may carry a small stylesheet aimed at named hooks.

**Which styles and how many**
- All seven: Neutral House plus the six looks the ten apps group into.

**Remaining**
- Done means the automated AA check passes and every style has a gallery pass on all ten blocks.
- A request naming a studied app maps to the style studied from it, and the agent says so.
- When the agent picks, the user sees the style, one line on why, and the other names, before building.
- Approach: JSON source compiled to CSS.

## Industry Insights

- **Name the attribute, not the brand.** Courts dismiss vague look-and-feel claims but protect a
  specific pleaded combination of visual features, so copying a product's exact combination is the
  exposed part. ([Lathrop GPM](https://www.lathropgpm.com/insights/trade-dress-litigation-in-the-dupe-era-what-works-what-fails-and-early-court-signals/))
- **Marketplace naming norm.** VS Code allows only "[Name] for Visual Studio Code" and bans names that
  imply endorsement. ([VS Code brand guidelines](https://code.visualstudio.com/brand))
- **SF Pro can't ship.** Its license allows interface mockups for Apple platforms only and prohibits
  embedding the font or using it in website content. Inter is under the SIL Open Font License.
  ([Apple Fonts](https://developer.apple.com/fonts/), [Inter license](https://raw.githubusercontent.com/rsms/inter/v4.0/LICENSE.txt))
- **Contrast thresholds.** 4.5:1 for normal text, 3:1 for large text and for UI components such as focus
  rings. Dark modes commonly fail by checking against the light surface, by muted greys near 3:1, and by
  focus rings that vanish. ([W3C 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html),
  [WebYes](https://www.webyes.com/blogs/dark-mode-accessibility/))
- **A preset is a value swap.** shadcn components read semantic tokens defined under `:root` and
  `.dark`, so a preset is a different set of values, and density lives in component variants, not tokens.
  ([shadcn theming](https://ui.shadcn.com/docs/theming), [eastondev](https://eastondev.com/blog/en/posts/dev/20260326-shadcn-ui-theme-customization/))
- **Attribute-scoped themes work for plain values.** `[data-theme]` overrides work in Tailwind v4, but
  shadcn says to keep `:root` and `.dark` outside `@layer base`.
  ([tailwindcss #16292](https://github.com/tailwindlabs/tailwindcss/discussions/16292),
  [shadcn Tailwind v4](https://ui.shadcn.com/docs/tailwind-v4))
- **Contrast from oklch needs care.** Blend translucent colors over their real background before
  measuring, map out-of-gamut colors into sRGB, and gate on WCAG 2 rather than APCA.
  ([Smashing](https://www.smashingmagazine.com/2026/05/building-self-correcting-color-systems-contrast-color/),
  [CSS Color 4](https://www.w3.org/TR/css-color-4/))
- **shadcn theme items are a poor fit here.** `registry:font` supports only Google-hosted fonts, and a
  Tailwind v4 user reported re-running `add --overwrite` duplicated blocks and misplaced variables.
  ([registry examples](https://ui.shadcn.com/docs/registry/examples),
  [nebari-design #151](https://github.com/nebari-dev/nebari-design/issues/151))

## Deferred Ideas

- **Density as its own option** (compact or comfortable, independent of style). Every block hard-codes
  its sizes today, so this needs a refactor across all ten blocks first. Logged as DEFER-26.
- `[tech-spec]` Which named hooks the blocks expose for style stylesheets, and how the gallery-scoped
  CSS is selected.
- `[tech-spec]` How the style script recognises a hand-edited tokens file (SC-5).
- `[tech-spec]` Which open fonts the serif and mono styles bundle, and confirming each license.

## Glossary

- **Style**: one named set of look decisions (tokens, fonts, radius, border and shadow weight, optional
  hook rules) applied to a whole mini app.
- **Style reference**: the written description of a style: character, fit, sources, what it leaves out.
- **Style source**: the one JSON file a style's CSS and contrast check are generated from.
- **Tokens file**: the CSS file in a mini app that holds its style. Swapping a style overwrites it.
- **Named hook**: a stable attribute a block exposes so a style's extra rules can target it without
  touching the block's code.
- **Character**: an app's mood (light or dark lean, radius, type feel, accent loudness, depth) as
  opposed to its brand assets.
- **Neutral House**: today's house style, kept as one of the seven and the fallback.
