# Build

Use this for a new screen or a major redesign of product UI. The goal is an interface that looks decided: every choice has a reason you can state, and the hierarchy is clear at a glance. Defaults are shared by every generated interface, so the work is naming them and choosing something else on purpose.

## Contents

- [Start from what exists](#start-from-what-exists)
- [Set the intent](#set-the-intent)
- [Explore the product domain](#explore-the-product-domain)
- [Write the direction block](#write-the-direction-block)
- [When to confirm](#when-to-confirm)
- [Optional image reference pass](#optional-image-reference-pass)
- [Build](#build)
- [Product UI rules](#product-ui-rules)
- [Run the four craft tests](#run-the-four-craft-tests)
- [Check the render](#check-the-render)
- [Offer to save](#offer-to-save)

## Start from what exists

Read `.quirk/design/system.md` if it exists. If it does, the direction is already decided. Skip the exploration and the direction block and apply the saved spacing base, depth strategy, palette and patterns. Still state who the person is and what verb the screen serves, in a line or two, because those belong to this screen. The feel comes from system.md. Then go to [Build](#build). The format is in [system-md.md](system-md.md).

Then look at the project: its tokens, its component library, its styling convention. Reuse before you write.

## Set the intent

Answer three questions before any code. Keep the answers to a few lines.

- **Who is this person?** The actual human, not "users". Where are they when they open this, and what did they do five minutes ago?
- **What must they do?** One verb: triage the failed deploy, approve the payment, grade the submission. It decides what leads and what hides.
- **What should it feel like?** Words that mean something. "Clean and modern" is what every generated interface says. Try warm like a notebook, cold like a terminal, dense like a trading floor, calm like a reading app.

If the request is too vague to answer these, ask one short question. If a responsible assumption exists, state it in one line and go on.

Intent has to hold across every token. Saying "warm" and then using cold greys is not following through. If the intent is dense, spacing, type size and information layout all follow it. For each choice (layout, color temperature, typeface, spacing, hierarchy) you should be able to say why. "It's common" and "it works" mean you defaulted.

## Explore the product domain

Defaults hide in the parts that feel like plumbing. Type feels like a container, navigation like scaffolding, data like presentation, token names like an implementation detail. They are all design. A page with no navigation context is a component demo, not software.

Produce all four before you propose a direction:

- **Domain:** at least five concepts, metaphors or terms from this product's world. Territory, not features.
- **Color world:** at least five colors that exist naturally in this world. Picture the physical version of the product: what materials, light and objects would you see?
- **Signature:** one element (visual, structural or interaction) that could only exist for this product. If you can't name one, keep exploring.
- **Defaults:** three obvious choices for this kind of interface, visual and structural. You can't avoid a pattern you haven't named.

Test it: read the proposal with the product name removed. Could someone tell what it's for? If not, go deeper.

## Write the direction block

State five lines before you write code:

```
Domain:      [five or more concepts from the product's world]
Color world: [five or more colors that exist in this domain]
Signature:   [one element unique to this product]
Rejecting:   [default 1] → [alternative], [default 2] → [alternative], [default 3] → [alternative]
Direction:   [the approach that ties the four lines together]
```

Keep the color restrained. The color world shows up as the temperature of the neutrals, the type, the density and the signature. The interface still has one accent, used for primary action, current selection and state. A world lends type, palette, density and one signature move. It never supplies the layout, the navigation model or the controls, which stay standard for the platform. If the world is a tool people operate (a terminal, a scope, a cockpit), take only what transfers and skip the costume: no function-key bar, no bezel, no ledger paper standing in for a table.

Name the signature concretely so you can find it in the build: service health drawn as a transit map, a schedule set in a timetable's column rhythm. A world that only shows up as a color scheme has not found its move yet.

## When to confirm

Ask "Does that direction feel right?" only when the direction is ambiguous or costly to change: a new product with no precedent, a redesign that reshapes navigation, a choice that would touch many screens. Otherwise state the block and keep building. Do not ask permission for a direction the user's request already settled.

If the session has a tool that renders HTML or SVG inline, show a small specimen with the proposal: the palette as swatches, the type scale in the real face, the signature as a real component. Put the reasoning in your reply and only the visual in the specimen. When no such tool exists, use the written block.

## Optional image reference pass

Only when an image tool exists in the session, and only for a new screen, a major redesign or a vague direction. Skip it otherwise. It supports the build and is never the deliverable.

- **Direction board:** two or three abstract mood, material and color explorations before code. No real UI.
- **UI reference:** a medium-fidelity composition for the chosen direction.
- **Paintover:** a stronger version of an existing screenshot.
- **Raster asset:** empty-state art or texture. Never icons, logos or charts.

Reject generic SaaS output, illegible text and palettes that don't fit the domain. Pull out the palette, density, proportions and signature, then build it in real code and check the render.

## Build

State a short checkpoint before each component, even a small one, and keep it to one line per item:

```
Intent / Hierarchy / Palette / Depth / Surfaces / Type / Spacing
```

If you can't say why for one of them, stop and decide it.

**Use what exists.** Native HTML first: a `<button>` is a button, and `<dialog>` and `<details>` exist. For stateful controls that are hard to get right (select, combobox, dialog, popover, tooltip, menu, tabs, date picker), compose a trusted headless primitive and style it. Hand-roll only when nothing fits, and then deliver the full keyboard, focus and ARIA behavior. If the project has a design system, use its components and variants. Extract a component on the second real reuse. Bind to semantic tokens, not raw literals like `gray-200` or `#fff`.

**One focal point per view.** Name the thing the person came to do and make it win through size, contrast, position or space. Demote the rest on purpose. Name the spatial thesis too: the main path through the screen, what belongs together, what leads and what supports, the density, and how the structure changes at narrow widths.

**Hierarchy comes from three levers together:** size, weight and color. Weight and tone do more of the work than size. A single 14px size can hold three tiers (value 600 primary, label 500 secondary, meta 400 muted). Pick a scale ratio and step it: about 1.2 for dense or calm UI, up to 1.25 for most product UI. Use a fixed rem scale, not fluid headings.

**Density is a decision written in pixels.** Tie it to how often the screen is used and how heavy the decisions are. A table an operator scans all day runs tight. A settings page opened twice a year can breathe. Pick the numbers, then hold them. Vary the rhythm on purpose: tight within a group, real air between groups.

**Depth: choose one strategy and commit.** Borders only, subtle shadows, layered shadows, or surface-color shifts. Don't mix them. Surfaces step up a few percent of lightness at a time. Sidebars share the canvas background and are separated by a quiet border. Inputs sit slightly darker than their surroundings. Borders are low-opacity so they find the edge without announcing it.

**Spacing and radius.** Pick a base of 4 or 8px and use multiples only. Nested rounded elements follow `outer radius = inner radius + padding`. Radius is a scale: small for inputs and buttons, medium for cards, large for modals.

**Tokens belong to the product.** `--ink` and `--parchment` evoke a world. `--gray-700` and `--surface-2` evoke a template. Keep one hue across surfaces and shift only lightness.

**Motion.** Product motion is 150–250ms and conveys state only: a change, feedback, loading or a reveal. Use ease-out, never ease-in. Animate transform and opacity, name properties instead of `transition: all`, never start from `scale(0)`, and honor `prefers-reduced-motion`. Actions repeated all day (shortcuts, the command palette) get no animation. Don't choreograph page load.

## Product UI rules

These come from how people use tools, so they apply even when the direction is bold.

- **Familiarity is a feature.** Product UI fails by being strange for no reason: over-decorated buttons, mismatched controls, display fonts on labels, invented affordances for standard tasks. A fluent user should trust the screen immediately.
- **Typography.** One well-tuned family often carries headings, labels, body and data. Keep prose to 65–75ch. Dense tables can run wider. Use tabular numerals for data.
- **State vocabulary.** Standardize hover, focus, active, disabled, selected, loading, error, warning, success and info once, and reuse them. Every interactive component gets default, hover, focus, active, disabled, loading and error. Loading uses skeletons, not a spinner in the middle of content.
- **A second neutral.** Give sidebars, toolbars and panels a neutral slightly cooler or warmer than the content surface, so the shell and the work area read as different layers.
- **Accent discipline.** The accent marks primary action, selection and state. It is not decoration, and inactive states don't get a saturated version of it.
- **Modals are not the first thought.** Try inline, progressive and non-blocking options first. Use a modal only when the task needs the person's attention or protected focus. Overlays must escape their container: a dropdown inside an `overflow: hidden` ancestor gets clipped, so use `<dialog>`, the popover API, `position: fixed` or a portal.
- **Browser surfaces carry the design too.** Text selection, the caret, scrollbars, focus rings, underline offset and tabular numerals all ship with defaults that belong to no system. Theme them from the palette. Models skip this most reliably.
- **Copy is part of the interface.** Controls name their action. Destructive actions name the object and the consequence, and prefer undo to a confirmation when recovery is safe. When you must confirm, put the action name on both the message and the button, never `Yes`, `No`, `OK` or `Submit`. An error says what failed, why when that is known, and how to recover. Labels persist, and placeholders are examples. Loading text names the real operation.
- **Empty states teach.** There are five kinds, and each needs its own text and next action: first use, no results, filtered to nothing, no permission, and failure to load.
- **Responsive behavior is structural.** Collapse the sidebar, reflow the table, change columns at breakpoints. Don't rely on fluid type.

### Defaults to justify

Some patterns are common in generated UI and sometimes right in a real product. When you reach for one, be able to say why it fits this screen. In review each is a P3 check-intent flag, "justify or change", never an error.

- Eyebrow labels above headings: keep them when they group navigation, drop them when they decorate.
- The hero-metric block: a big number, a small label, supporting stats.
- A colored side stripe on cards, list items and callouts.
- Inter or Geist as the face with nothing chosen around them.
- Cards as the default container, and cards nested in cards.

## Run the four craft tests

Run them against the built result, not your intent. If one fails, fix the code and run it again before you present.

- **Swap test.** Swap your typeface for the usual one and your layout for a standard template. If nothing would feel different, you defaulted there.
- **Squint test.** Blur your eyes. The hierarchy should still read: what is above what, where sections divide. Nothing should jump out harshly. If you can't tell headline from body from label, the hierarchy is too weak.
- **Signature test.** Point to five specific elements where the signature appears. "The overall feel" doesn't count.
- **Token test.** Read the CSS variables aloud. Do they belong to this product's world, or to any project?

## Check the render

When the app can run, look at the result at a desktop width and at a mobile width of about 390px, using whatever local browser, screenshot or render tool the session has. Check for overlap, broken spacing, blank states, unreadable text, missing assets, overflow and a generic composition. Run the build, typecheck and tests the project already has. Fix what you find before presenting.

If the app can't run, say so in one line and describe what you could not check. For docs and long-form pages see [read.md](surfaces/read.md). For native apps see [ios.md](surfaces/ios.md) and [android.md](surfaces/android.md).

## Offer to save

After presenting, ask once: "Want me to save these patterns to `.quirk/design/system.md`?" Offer only if you made decisions or reusable patterns that are not already recorded. What to write, and how to hold to it afterward, is in [system-md.md](system-md.md).

Keep updates short. Don't announce modes or narrate the process, and don't paste your private design reasoning. Surface the recommendation and the decision.
