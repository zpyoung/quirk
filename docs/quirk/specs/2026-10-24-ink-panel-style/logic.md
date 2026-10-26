# Logic spec: Ink Panel, an eighth `building-mini-apps` style with a retro comic look

## Status & amendments

**Status**: Approved

**Amendments:** none yet.

I like the Sentry app's look. Its buttons, filter groups and table card sit on a solid, unblurred
bottom edge, so they read like raised keys, and with the rounded bold type the whole thing has a
retro comic-book feel. I want that feel as a style the skill can build any mini app in, next to the
seven in the [styles spec](../2026-10-23-mini-app-styles/logic.md).

The look needs two things today's style system can't express: a press motion on buttons, and thick
outlines that survive high-contrast mode. So this spec also extends the style system, in a way any
later style can use.

## Conceptual model

**Ink Panel** (`ink-panel`) is a style in the same sense as the other seven: a named set of look
decisions with a source, generated CSS and a style reference
([styles spec, Conceptual model](../2026-10-23-mini-app-styles/logic.md#conceptual-model)). It adds
one row to the style table:

| Style | Character | Studied from |
|---|---|---|
| Ink Panel | Warm paper, 2px ink outlines and hard offset shadows on controls and panels, cobalt actions, marker-yellow selection, buttons that press in | Sentry |

Its look has four layers.

- **Paper and ink.** Light mode is a warm paper page (about #fbf6ea) with near-black ink (about
  #1b1722). Dark mode inverts the ink: a night page (about #1c1824) with cream outlines and offset
  shadows (about #ece4d2), like chalk on a dark panel. Every value is re-derived in oklch so each text
  pair clears WCAG AA.
- **Two accents.** Cobalt (about #2357d9 light, #7da2ff dark) is the primary: action buttons, the
  focus ring, and the highlight shadow under a selected item. Marker yellow (about #ffe682, chips
  about #ffd84d) is the selection fill in light mode. In dark mode the selected row uses a deep amber
  fill (about #4d3d0a) so its cream text stays readable, and chips stay yellow with dark text.
- **Outlines and offsets on controls and panels only.**
  - Buttons, inputs, chips and toggles get a 2px ink outline, 6px corners and a 3px offset shadow
    down and to the right.
  - Cards, list panels, menus, popovers and dialogs get a 2px ink outline, 8px corners and a 5px
    offset.
  - Rows inside a panel keep 1px dividers. The sidebar keeps a quiet 1px rule.
  - The selected row gets the selection fill, an inset ink edge and a 4px cobalt offset shadow.
- **Type.** Space Grotesk (OFL, from `@fontsource-variable/space-grotesk`) for interface text and
  titles. Data cells use the system monospace stack.

**Motion** applies to buttons and toggle chips only. Panels, rows and menus never move.

- **Lift.** On a device with a real pointer, hovering lifts the button 1px up and left, and its
  shadow grows to 4px.
- **Press.** Pressing pushes it 3px down and right and drops the shadow, so it sits where the shadow
  was. It snaps in at once and eases back over about 120ms.
- **Reduced motion.** With reduced motion on, nothing moves. The shadow still changes, so hover and
  press still read.

**The press marker** is a small script every app carries. While a button or toggle is pressed, by
pointer or by Space or Enter, it marks that element as pressed, and it holds the mark for at least
about 120ms. CSS alone can't show a press for a click shorter than one frame, which a trackpad tap can
be. The marker does nothing visible on its own. Only a style that targets it, Ink Panel today, draws
anything. It never delays, blocks or repeats a click.

**The style system extension** lets any style's extra rules use what Ink Panel needs:

- the `transform` and `transition` properties
- the `:active` state and the pressed marker as selector hooks
- the button, toggle, input, badge, card, menu, popover and dialog components as hooks, alongside
  today's `data-mini` roles

The build puts every motion rule behind a no-preference reduced-motion check, and every hover lift
behind a real-pointer check. A style can't forget either one. A style can also give a rule a
high-contrast fallback, which only applies in high-contrast mode. Ink Panel uses it so its outlines
become real borders there. The bans on `url()`, `!important` and raw CSS files stay.

## Data flow

A user asks for a mini app, either naming the look ("like Sentry", "comic-book style") or not. The
agent picks Ink Panel from the style index, says why in one line, and lists the other seven names
([styles spec SC-1, SC-2](../2026-10-23-mini-app-styles/logic.md#behavior--scenarios)). The scaffold
script writes the app's tokens file from Ink Panel's generated CSS and installs Space Grotesk. The
app's base already includes the press marker. In the browser, the generated CSS draws the outlines,
offsets and selection. When the user presses a button, the marker flags it and Ink Panel's rules move
it in and back out.

The style build reads Ink Panel's source with the others. It checks token contrast in both modes,
rejects any motion or selector the extended rules don't allow, and writes the CSS with the reduced-motion
and pointer guards in place, plus Ink Panel's high-contrast fallbacks. The other seven styles go through the same build and come out
byte-identical to today.

## Key decisions & rationale

- **Studied from Sentry, built from our own frames.** Sentry's own theme has no public spec, so every
  observation comes from the sandbox frames under `references/media/sentry/`. Ink Panel exaggerates
  the raised-key edge into a comic outline and offset, and keeps none of Sentry's colors or type
  (see Scope).
- **Outlines go on controls and panels, never on every cell.** Heavy outlines on each row turn a list
  into a grid of boxes and bury the selection. Rows keep thin dividers so the one selected row stands
  out.
- **Inverted ink in dark mode.** A black offset shadow disappears on a dark page. Cream outlines and
  shadows keep the same shape in both modes. The user chose this over accent-colored shadows, but
  wanted the accent-colored shadow kept as the highlight under a selected or active item.
- **A separate focus ring.** The focus ring is a 2px cobalt outline set 3px out. An outline that
  touched the ink edge would look like a thicker border, and an offset shadow doesn't count toward
  WCAG's focus-indicator area.
- **The press marker over CSS only.** The user asked that even a quick click show a press. CSS can't
  guarantee that for a sub-frame tap, so a shared script holds the press for a minimum time. Putting
  it in every app's base, rather than in Ink Panel, keeps styles data-only. Any later style can draw a
  press without shipping code.
- **Extend the validated rules rather than allow raw CSS.** A per-style CSS file would let a style use
  `url()` exfiltration tricks and break silently when a component changes. The build couldn't
  contrast-check it either. Adding a few properties and hooks to the validated list keeps every
  style checkable.
- **The guards are automatic.** The build wraps motion and hover itself, so a style author can't ship
  motion that ignores reduced motion or a hover that sticks after a tap.

## Behavior & scenarios

1. **SC-1: The user names Sentry**
   - **Given** the user asks for "a bug tracker that looks like Sentry"
   - **When** the agent chooses the style
   - **Then** it maps the request to Ink Panel, the style studied from Sentry, and says the style keeps
     the feel and not Sentry's exact look. The word "Sentry" never appears in the generated app.
   - **Walkthrough:**
     1. The agent finds Sentry in the Studied from column, next to Ink Panel.
     2. The agent writes: "I'll use Ink Panel, the style drawn from Sentry. It keeps the raised,
        comic feel, not Sentry's exact look."
   - **Data after:** **bugs-app***: ✓ Ink Panel tokens file; ✓ Space Grotesk installed; ✗ no
     occurrence of "Sentry" in the app's files

2. **SC-2: Building from the Sentry blueprint**
   - **Given** the user asks for a close clone of the error tracker in the Sentry blueprint
   - **When** the agent scaffolds it
   - **Then** it uses Ink Panel by default, since that's the style studied from the same app. The
     blueprint names Ink Panel where it names Neutral House today. The user can still ask for another
     style.

3. **SC-3: No look is named and the app fits Ink Panel**
   - **Given** the user asks for "a mini app to track my board game collection" and says nothing about
     looks
   - **When** the agent names its patterns, before building
   - **Then** it may pick Ink Panel, gives one line on why, and lists the other seven style names, as in
     the [styles spec SC-1](../2026-10-23-mini-app-styles/logic.md#behavior--scenarios). Ink Panel's
     reference says it fits personal and hobby trackers, playful or creative tools, and triage queues.
   - **Walkthrough:**
     1. The agent writes: "Style: Ink Panel, since a hobby collection suits a playful comic look.
        Others: Neutral House, Calm Paper, Airy White, Cool Tool, Dense Dark, Glass Launcher, Split
        Tone. Say the word to switch."
     2. The agent scaffolds **games-app*** with Ink Panel.

4. **SC-4: Switching an existing app to Ink Panel**
   - **Given** an app built with Calm Paper before the press marker existed, with its own edits in the
     demo files
   - **When** the user asks to switch it to Ink Panel
   - **Then** the style script writes the Ink Panel tokens file, installs Space Grotesk, and adds the
     press marker to the app once, the same way it rewires the font lines once. The user's own files
     are otherwise unchanged. It rebuilds and checks that the dev server starts.
   - **Data before:** **books-app***: Calm Paper tokens file; no press marker; edited book demo
   - **Data after:** **books-app**: ✓ Ink Panel tokens file; ✓ press marker present; ✓ book demo
     unchanged; ✓ builds clean

5. **SC-5: An unknown style name**
   - **Given** the user or the agent asks for a style called "comic"*
   - **When** the scaffold or style script runs
   - **Then** it exits with the bad-arguments code and lists the eight valid style names, Ink Panel
     last. No app is created or changed.

6. **SC-6: A quick trackpad tap still shows the press**
   - **Given** an Ink Panel app with a "New bug" button
   - **When** the user taps the trackpad, so the press and release land about 10ms* apart
   - **Then** the button shows the pressed look for at least about 120ms, then eases back over about
     120ms. The click fires once, at release, as it would in any other style.
   - **Timeline:**

     | Time | Input | Button |
     |---|---|---|
     | 0ms | press | ✓ pushed 3px in, shadow gone |
     | 10ms* | release; click fires once | ✓ still pushed in |
     | about 120ms | none | ✓ starts easing back |
     | about 240ms | none | ✓ at rest, 3px shadow back |

7. **SC-7: Keyboard press and focus**
   - **Given** the "New bug" button has keyboard focus in an Ink Panel app
   - **When** the user presses Space
   - **Then** the button shows the cobalt focus ring 3px outside its ink edge, presses in as in SC-6,
     and activates once. The focus ring stays visible throughout the press.

8. **SC-8: Reduced motion**
   - **Given** the system's reduced-motion setting is on
   - **When** the user hovers over and presses a button in an Ink Panel app
   - **Then** the button never moves and nothing transitions. Its shadow grows on hover and disappears
     while pressed, so both states still read.

9. **SC-9: Touch devices don't keep the lift**
   - **Given** an Ink Panel app on a phone
   - **When** the user taps a button and lifts their finger
   - **Then** the button presses as in SC-6 and returns to rest. It doesn't stay lifted afterwards.

10. **SC-10: High-contrast mode**
    - **Given** Windows high-contrast mode is on
    - **When** an Ink Panel app renders
    - **Then** buttons, inputs, chips, panels, menus and dialogs show real 2px borders in the system's
      colors, since the system removes shadows. The focus ring stays visible.

11. **SC-11: Dark mode selection**
    - **Given** an Ink Panel app in dark mode with one selected row in a list
    - **When** it renders
    - **Then** the page is the night color with cream outlines and offsets. The selected row has the
      deep amber fill, an inset cream edge and a 4px cobalt offset shadow. Its text clears 4.5:1 on the
      amber fill.

12. **SC-12: The other seven styles don't change**
    - **Given** the style system extension and the press marker are in place
    - **When** the style build runs, and when an app in any of the other seven styles is used
    - **Then** those seven styles' generated CSS is byte-identical to before. Their apps look and behave
      exactly as before, because nothing in their CSS targets the press marker.

13. **SC-13: A style's motion rule breaks the limits**
    - **Given** a style source adds a rule that transitions every property over two seconds*
    - **When** the style build runs
    - **Then** it fails, naming the style, the rule and the problem. Transitions must name what they
      move and stay short (at most 200ms). Transforms may only translate.

## Scope & non-goals

In scope:

- Ink Panel's source, generated CSS and style reference, with the style index row and the fits list.
- The style system extension: the new properties, the new hooks, the automatic reduced-motion and
  pointer guards, the opt-in high-contrast fallback, and the limits in SC-13.
- The press marker in the app base and the gallery, plus the style script adding it to older apps
  (SC-4).
- Changing "seven" to "eight" wherever the skill states the count: SKILL.md, script help, tests and the
  styles spec (its SC-3 and SC-6, by amendment).
- The Sentry blueprint naming Ink Panel as its default style (SC-2).

Not in scope:

- Sentry's own colors (its aubergine base, its blurple, its severity pinks and purples), its font,
  logo, icons, illustrations or copy. The reference's Leaves out section lists these.
- Halftone dots, a display-lettering title face, speech-bubble shapes or any other comic ornament
  beyond outlines and offsets.
- Motion anywhere but buttons and toggle chips.
- Changing how any of the other seven styles look.
- Letting styles ship JavaScript. The press marker is shared base code, not part of a style.

## Decisions Locked

**Intensity**
- Ink and offset: 2px near-black ink outlines, hard offset shadows down and right, flat fills on warm
  paper. No halftone, no display-lettering face.

**Edges**
- Rounded, medium offset: 6px corners on controls, 8px on panels; 3px offset on controls, 5px on
  panels.

**Dark mode**
- Inverted ink: night page with cream outlines and offsets.
- The cobalt offset shadow highlights the selected or active item, in both modes.

**Palette**
- Warm paper, near-black ink, cobalt primary, marker-yellow selection and chips.
- Cobalt was chosen over violet and magenta; marker yellow over tangerine and mustard.

**Typography**
- Space Grotesk for interface text and titles; system monospace for data.

**Scope of the look**
- Outlines and offsets on buttons, inputs, chips, toggles, cards, panels, menus, popovers and dialogs.
- Rows keep thin dividers; the sidebar keeps a quiet rule.
- The selected row: selection fill, inset ink edge, 4px cobalt offset shadow.

**Motion**
- Lift and press, on buttons and toggle chips only.
- Even a quick click shows a minimum press of about 120ms, through the press marker.
- Reduced motion: no movement, shadow changes kept.

**Name, mapping and fit**
- Named Ink Panel (`ink-panel`).
- Sentry is listed under Studied from, and requests to look like Sentry map to Ink Panel.
- Suggested for personal and hobby trackers, playful or creative tools, and triage and issue queues.

**Build**
- CSS plus the press marker script, through the validated style rules, with no raw CSS.

## Industry Insights

- **Box shadows vanish in high-contrast mode.** Forced-colors mode forces `box-shadow` to none, so
  outlines drawn with shadows need a real-border fallback inside `@media (forced-colors: active)`.
  ([MDN forced-colors](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/forced-colors),
  [Matuzović 2026](https://matuzo.at/blog/2026/box-shadow-no-alternative-to-outline))
- **Shadows don't count toward the focus indicator.** WCAG 2.4.13 measures a 2px perimeter with a 3:1
  change and excludes shadows. Offsetting the outline helps it read against a heavy border.
  ([W3C Understanding 2.4.13](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance.html))
- **Pressed feedback should appear within 100 to 150ms.** CSS can snap in on `:active` and ease the
  release, but it can't guarantee a frame for a sub-frame click. A held state needs script.
  ([NN/G button states](https://www.nngroup.com/articles/button-states-communicate-interaction/))
- **Hover sticks after a tap on touch screens.** Wrap hover styles in `@media (hover: hover)` and
  leave `:active` unguarded.
  ([CSS-Tricks](https://css-tricks.com/solving-sticky-hover-states-with-media-hover-hover/),
  [MDN hover](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/hover))
- **Reduced motion means remove or replace.** Drop the transform and transition, keep the non-motion
  state change.
  ([MDN prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion),
  [Open Props motionOK gating](https://op-reduced-animations.netlify.app/))
- **Raw theme CSS breaks and leaks.** Theme CSS escape hatches break on component updates, and
  attribute selectors with `url()` can exfiltrate page data without script. An allowlist that bans
  `url()` closes that path. Few public theme systems expose motion at all.
  ([PortSwigger blind CSS exfiltration](https://portswigger.net/research/blind-css-exfiltration),
  [BetterDiscord #1814](https://github.com/BetterDiscord/BetterDiscord/issues/1814),
  [daisyUI themes](https://daisyui.com/docs/themes/))
- **Neubrutalist practice, from the first research round.** Use heavy outlines on controls and
  panels, not every cell. Give focus its own color. Keep a zero-blur shadow scale. Use off-white
  rather than pure white on dark pages to avoid halation.

## Deferred Ideas

- `[tech-spec]` Which component hooks each Ink Panel rule targets, and the exact selector grammar for
  `:active` and the pressed marker.
- `[tech-spec]` Where the press marker lives in the app base and the gallery, and how the style script
  adds it to an older app.
- `[tech-spec]` How the build emits the reduced-motion, pointer and high-contrast wrappers, and the
  exact value grammar for `transform` and `transition`.
- `[tech-spec]` How rendered contrast is checked on real components (selected row, chips, primary
  button in both modes), beyond the token-pair gate.
- `[tech-spec]` Whether 2px outlines are drawn as inset shadows, as real borders, or as a mix per
  component, given that inputs already carry a 1px border.
- Halftone texture or a display title face as an opt-in "louder" variant of Ink Panel.
- Accent-colored offset shadows on more than the selected item, such as the open menu's trigger.

## Glossary

- **Ink**: the outline and offset-shadow color. Near-black in light mode, cream in dark mode.
- **Offset shadow**: a hard shadow with no blur, shifted down and right, so a control looks raised.
- **Highlight shadow**: the cobalt offset shadow under the selected or active item.
- **Lift**: the hover state, 1px up and left with a larger shadow.
- **Press**: the pressed state, 3px down and right with no shadow.
- **Press marker**: the shared script that flags a pressed button or toggle and holds the flag for a
  minimum time.
- **Hook**: a named attribute on a block or component that a style's extra rules may target.
