# Review checklist

Every review rule has an id, and findings are reported by that id. A rule ending `(detector)` is also caught by `scripts/detect.py`: confirm the script's hits instead of searching again. The severity on each bullet is the default; [review.md](review.md) says when to move it.

## Contents

- [Accessibility](#accessibility)
- [Focus](#focus)
- [Forms](#forms)
- [Motion](#motion)
- [Typography](#typography)
- [Content & copy](#content--copy)
- [Images](#images)
- [Performance](#performance)
- [Navigation & state](#navigation--state)
- [Touch & interaction](#touch--interaction)
- [Layout & containers](#layout--containers)
- [Theming](#theming)
- [Locale & i18n](#locale--i18n)
- [Hydration](#hydration)
- [Product craft](#product-craft)
- [Slop tells](#slop-tells)
- [Check-intent](#check-intent)

## Accessibility

- `a11y-icon-button-label` P1 — Icon-only buttons need an accessible name: `aria-label` or visually hidden text.
- `a11y-control-label` P1 — Every form control needs a `<label>` or an `aria-label`.
- `a11y-keyboard-handlers` P1 — Anything clickable must also work from the keyboard: use a real `<button>`, or add `onKeyDown`/`onKeyUp`, a role and a tab stop.
- `a11y-click-on-div` P0 — A `<div>` or `<span>` with a click handler and no role is invisible to keyboards and screen readers; use `<button>` for actions and `<a>` for navigation. (detector)
- `a11y-img-no-alt` P1 — Images need `alt`, or `alt=""` when they are decorative. (detector)
- `a11y-decorative-icon-hidden` P2 — Decorative icons carry `aria-hidden="true"`.
- `a11y-live-region` P2 — Async updates such as toasts and validation messages need `aria-live="polite"`.
- `a11y-semantic-html` P2 — Reach for `<button>`, `<a>`, `<label>` and `<table>` before adding ARIA roles.
- `a11y-heading-order` P2 — Headings descend from `<h1>` to `<h6>` without skipping a level.
- `a11y-skip-link` P2 — Pages with repeated navigation offer a skip link to the main content.
- `a11y-heading-anchor-offset` P3 — Heading anchors set `scroll-margin-top` so a sticky bar does not cover them.
- `a11y-media-alternatives` P1 — Meaningful audio and video need captions, a transcript or a description.
- `a11y-media-controls` P2 — Media controls work from the keyboard, and decorative media is hidden from assistive tech.
- `a11y-zoom-disabled` P0 — `user-scalable=no` or `maximum-scale=1` blocks pinch zoom; remove it. (detector)
- `a11y-positive-tabindex` P1 — A `tabIndex` above 0 overrides the natural tab order; use 0 or -1. (detector)
- `a11y-contrast-text` P1 — Body and placeholder text reach 4.5:1 and large text 3:1 in every state and theme; this needs the running app.
- `a11y-gray-on-color` P2 — Secondary text on a colored surface is tinted from that surface's hue, never neutral grey.

## Focus

- `focus-outline-removed` P0 — `outline: none` or `outline-none` with no `:focus-visible` replacement leaves keyboard users with no position. (detector)
- `focus-visible-missing` P1 — Every interactive element shows a visible focus state, such as `focus-visible:ring-*`.
- `focus-visible-over-focus` P2 — Style `:focus-visible` instead of `:focus` so a mouse click does not draw a ring.
- `focus-within-compound` P3 — Compound controls group their focus style with `:focus-within`.
- `focus-obscured` P1 — Sticky headers, footers and overlays must not cover the focused element.
- `focus-dialog-trap` P0 — A dialog moves focus in when it opens, keeps it inside, closes on Esc and returns focus to its trigger.
- `focus-tab-order` P2 — Tab order follows the reading order, with no stops on hidden or inert elements.

## Forms

- `forms-autocomplete-name` P2 — Inputs carry a meaningful `name` and the right `autocomplete` token.
- `forms-input-type` P2 — Use the correct `type` (`email`, `tel`, `url`, `number`) and `inputmode`.
- `forms-paste-blocked` P1 — Never block paste with `onPaste` and `preventDefault`. (detector)
- `forms-label-clickable` P2 — Clicking a label focuses its control, through `htmlFor` or by wrapping it.
- `forms-spellcheck-off` P3 — Turn spellcheck off on emails, codes and usernames with `spellCheck={false}`.
- `forms-hit-target` P3 — A checkbox or radio and its label share one hit target, with no dead zone between them.
- `forms-submit-state` P2 — The submit button stays enabled until the request starts, then shows a spinner.
- `forms-inline-errors` P1 — Errors sit inline next to their field, and submit focuses the first error.
- `forms-placeholder-example` P3 — Placeholders show an example pattern and end with `…`.
- `forms-placeholder-as-label` P1 — A placeholder is not a label; give the input an `aria-label`, `aria-labelledby` or a labeled `id`. (detector)
- `forms-autocomplete-off` P3 — Non-auth fields that should not trigger a password manager set `autocomplete="off"`.
- `forms-unsaved-warning` P2 — Leaving a form with unsaved changes warns first, through `beforeunload` or a router guard.

## Motion

- `motion-no-reduced-motion` P2 — Files that animate honor `prefers-reduced-motion`, with a reduced variant or no animation. (detector)
- `motion-transition-all` P2 — Never `transition: all`; list the properties that change. (detector)
- `motion-layout-property` P2 — Animating `width`, `height`, `top`, `left`, `right`, `bottom`, `margin` or `padding` forces layout every frame; animate `transform` and `opacity`. (detector)
- `motion-product-duration` P2 — Product motion runs 150 to 250ms and conveys state only, such as a panel opening or a row saving; longer or decorative motion needs a reason.
- `motion-easing-curve` P3 — Ease out with a smooth decelerating curve; entrances never use `ease-in`.
- `motion-bounce-easing` P3 — Bounce and elastic easing read as dated; use a decelerating curve instead.
- `motion-transform-origin` P3 — Set the correct `transform-origin`, so a popover grows from its trigger.
- `motion-svg-transform-box` P3 — Animate SVG through a `<g>` wrapper with `transform-box: fill-box` and `transform-origin: center`.
- `motion-interruptible` P2 — Animations respond to user input mid-flight instead of finishing first.
- `motion-autoplay-controls` P2 — Autoplaying motion longer than 5 seconds beside other content needs pause, stop or hide controls.
- `motion-muted-loop-stops` P2 — Muted decorative loops stop under `prefers-reduced-motion`.
- `motion-pulsing-dot` P3 — Pulse only an indicator tied to live data; otherwise use a static, labeled dot.
- `motion-keyboard-repeat` P3 — Actions a keyboard repeats, such as arrow-key moves, do not animate.

## Typography

- `content-three-dots` P3 — Write `…`, not `...`, in visible text. (detector)
- `type-curly-quotes` P3 — Use curly quotes “ ” in copy, not straight `"`.
- `type-nbsp` P3 — Bind units, shortcuts and brand names with a non-breaking space: `10&nbsp;MB`, `⌘&nbsp;K`.
- `type-loading-ellipsis` P3 — Loading and saving labels end with `…`: "Loading…", "Saving…".
- `type-tabular-nums` P2 — Number columns and values that update use `font-variant-numeric: tabular-nums`.
- `type-heading-balance` P3 — Headings set `text-wrap: balance` or `text-pretty` so the last line is not a widow.
- `type-straggler` P3 — Body copy sets `text-wrap: pretty`, so a paragraph's last line is not one lonely word.
- `type-tiny-text` P2 — Text below 12px is hard to read; body text is 14px or larger. (detector)
- `type-justified` P3 — Justified text opens rivers of white space in narrow columns; align left. (detector)
- `type-line-length` P2 — Body text holds a 65 to 75ch measure, not full container width.
- `type-tight-leading` P2 — Body line height is at least 1.3 and usually 1.5 to 1.7.
- `type-flat-hierarchy` P2 — Adjacent type roles differ by at least 1.25x, so size, weight and color separate the tiers.
- `type-tracking-extremes` P3 — Letter-spacing stays between -0.04em and 0.05em; wide tracking belongs to short uppercase labels only.
- `type-all-caps-body` P3 — Uppercase is for short labels, never for a sentence or a paragraph.
- `type-heading-rhythm` P3 — A heading sits closer to the content it introduces than to the block above it.

## Content & copy

- `content-overflow-handling` P2 — Text containers handle long content with `truncate`, `line-clamp-*` or `break-words`.
- `content-flex-min-width` P2 — Flex children that truncate text need `min-w-0`.
- `content-empty-states` P1 — Empty strings and arrays render a designed empty state, not broken UI.
- `content-user-generated-lengths` P2 — User-generated content works at short, average and very long lengths.
- `content-active-voice` P3 — Write in the active voice: "Install the CLI", not "The CLI will be installed".
- `content-casing` P3 — Headings and buttons use one casing, the one the product already uses (Title Case when it has none).
- `content-numerals` P3 — Counts use numerals: "8 deployments", not "eight deployments".
- `content-specific-labels` P2 — Buttons name their action: "Save API Key", not "Continue".
- `content-error-next-step` P2 — An error message names the problem and the next step.
- `content-second-person` P3 — Address the user as "you"; avoid first person.
- `content-ampersand` P3 — Use `&` instead of "and" only where space is tight.
- `content-repeated-text` P3 — The same text three times inside one card or panel is noise; say it once where it matters most.
- `content-coherence` P2 — The title, body and numbers on a screen tell one story about one product.
- `content-illustrative-data` P2 — Sample or placeholder values are labeled as illustrative, never shown as real.

## Images

- `images-dimensions` P2 — `<img>` carries explicit `width` and `height` to prevent layout shift.
- `images-lazy-below-fold` P3 — Below-the-fold images set `loading="lazy"`.
- `images-priority-above-fold` P3 — Critical above-the-fold images use `priority` or `fetchpriority="high"`.
- `images-broken-placeholder` P1 — An `<img>` with an empty, missing or placeholder `src` ships as a broken box; use a real asset or remove it.

## Performance

- `perf-virtualize-lists` P2 — Lists over 50 items are virtualized or use `content-visibility: auto`.
- `perf-layout-reads` P2 — Render code does not read layout (`getBoundingClientRect`, `offsetHeight`, `scrollTop`).
- `perf-batch-dom` P3 — Batch DOM reads and writes instead of interleaving them.
- `perf-cheap-inputs` P3 — Prefer uncontrolled inputs; a controlled input must be cheap per keystroke.
- `perf-preconnect` P3 — CDN and asset domains get `<link rel="preconnect">`.
- `perf-font-preload` P3 — Critical fonts use `<link rel="preload" as="font">` with `font-display: swap`.
- `perf-video-over-gif` P3 — Use `<video autoplay muted loop playsinline>` instead of an animated GIF, with a still alternative.
- `perf-short-loops` P3 — A short non-essential loop offers a Safari H.264 MP4 `<picture>` source, a `prefers-reduced-motion` condition and a still fallback.
- `perf-console-errors` P2 — The console shows no errors or hydration warnings on the path under review; this needs the running app.

## Navigation & state

- `nav-url-state` P2 — The URL reflects filters, tabs, pagination and expanded panels in query params.
- `nav-real-links` P1 — Navigation uses `<a>` or `<Link>` so Cmd/Ctrl-click and middle-click work; no inline `onClick` navigation.
- `nav-deep-link-state` P3 — Stateful UI built on `useState` is deep-linkable, for example through nuqs.
- `nav-destructive-confirm` P1 — Destructive actions get a confirmation or an undo window, never an immediate effect.
- `nav-modal-by-reflex` P3 — A modal is for a task that needs interruption or protected focus; otherwise use inline or a panel.

## Touch & interaction

- `touch-action-manipulation` P3 — Set `touch-action: manipulation` to remove the double-tap zoom delay.
- `touch-tap-highlight` P3 — Set `-webkit-tap-highlight-color` on purpose.
- `touch-overscroll-contain` P2 — Modals, drawers and sheets set `overscroll-behavior: contain`.
- `touch-rubber-band` P3 — Suppress page rubber-banding only with `overscroll-behavior: none` on `<html>` inside `@media (pointer: fine)`; it also disables pull-to-refresh and swipe navigation.
- `touch-drag-selection` P3 — During a drag, disable text selection and mark dragged elements `inert`.
- `touch-gesture-alternatives` P1 — Drag, swipe, pinch and path gestures have a tap or click and a keyboard alternative unless the gesture is essential.
- `touch-target-size` P2 — Touch targets are at least 44x44px, 40px at the very least.
- `a11y-autofocus` P2 — Use `autoFocus` sparingly: desktop only, one primary input, never on mobile. (detector)

## Layout & containers

- `layout-safe-area` P2 — Full-bleed layouts use `env(safe-area-inset-*)` so notches do not clip content.
- `layout-unwanted-scrollbars` P2 — Fix the overflow that causes an unwanted scrollbar instead of hiding it with `overflow-x-hidden`.
- `layout-flex-over-js` P3 — Use flex and grid for layout, not JavaScript measurement.
- `layout-z-index-escalation` P3 — A `z-index` of 999 or more is an arms race; define a small layer scale. (detector)
- `layout-spacing-rhythm` P3 — Tight groups, generous separation between groups, one repeated gap everywhere is monotone.
- `layout-scroller-edge-inset` P3 — Cards in a horizontal scroller keep the same inset on both ends.
- `layout-text-occlusion` P2 — No text sits under an opaque element or another text run.
- `layout-cramped-padding` P2 — Bordered or colored containers keep at least 8px, ideally 12 to 16px, between text and edge.
- `layout-body-viewport-edge` P2 — Body text never touches the viewport edge; keep 16px of horizontal padding at least.
- `layout-clipped-popover` P2 — A clipping container (`overflow: hidden`) does not wrap a positioned tooltip, menu or popover.
- `layout-structural-hacks` P2 — Negative margins that undo parent padding, escape-hatch `calc()` and absolute positioning that dodges flow signal a layout that should be rebuilt.
- `layout-content-hidden-at-rest` P1 — Content is visible by default; script only enhances its entrance. Check that no large share of text sits at `opacity: 0`.

## Theming

- `theme-color-scheme` P2 — Dark themes set `color-scheme: dark` on `<html>` so scrollbars and inputs follow.
- `theme-meta-theme-color` P3 — `<meta name="theme-color">` matches the page background.
- `theme-native-select` P3 — A native `<select>` sets explicit `background-color` and `color` for Windows dark mode.
- `theme-hover-state` P2 — Buttons and links have a `hover:` state.
- `theme-state-contrast` P3 — Hover, active and focus are more prominent than the resting state.
- `theme-semantic-tokens` P2 — Colors come from semantic tokens, not literals such as `bg-white`, `border-gray-200` or `#fff`.
- `theme-browser-surfaces` P3 — Text selection, the caret, scrollbars and numerals in data are themed from the palette, not left at browser defaults.

## Locale & i18n

- `i18n-intl-dates` P2 — Dates and times use `Intl.DateTimeFormat`, not hardcoded formats.
- `i18n-intl-numbers` P2 — Numbers and currency use `Intl.NumberFormat`, not hardcoded formats.
- `i18n-language-detection` P3 — Detect language from `Accept-Language` or `navigator.languages`, never from IP.
- `i18n-translate-no` P3 — Brand names, code tokens and identifiers carry `translate="no"`.
- `i18n-text-expansion` P3 — Layouts survive translated text that runs 30 to 40 percent longer.

## Hydration

- `hydration-value-onchange` P1 — An input with `value` needs `onChange`; use `defaultValue` for an uncontrolled input.
- `hydration-datetime-mismatch` P2 — Date and time rendering guards against a server and client mismatch.
- `hydration-suppress-warning` P3 — `suppressHydrationWarning` appears only where the mismatch is unavoidable.

## Product craft

Run the four craft tests on the whole screen, once each. Then check the saved system, if there is one, and the power-user path.

- `craft-swap-test` P2 — Swap the typeface for the usual one and the layout for a standard template; where nothing would change, the screen defaulted.
- `craft-squint-test` P2 — Blur the screen: hierarchy still reads, and nothing jumps out harshly.
- `craft-signature-test` P3 — Point to five specific elements where the signature appears; "the overall feel" does not count.
- `craft-token-test` P2 — Read the CSS variable names aloud; they should belong to this product's world, not any project.
- `craft-focal-point` P2 — One element leads and the rest is demoted; a screen where everything competes equally has no focal point.
- `craft-hierarchy-tiers` P2 — Primary, secondary and metadata tiers separate through size, weight and color together, not size alone.
- `craft-color-restraint` P2 — One accent carries action and state, and the rest is neutral; competing accents or decorative tints dilute it.
- `craft-depth-strategy` P2 — One depth strategy, borders or shadows, with quiet steps; a harsh 1px grey border or dramatic elevation jump breaks it.
- `craft-concentric-radii` P3 — Nested radii are concentric: outer radius equals inner radius plus the padding between them.
- `craft-spacing-grid` P2 — Spacing values sit on the system's base grid; off-grid values like 17px or 23px are drift.
- `craft-borders-over-space` P3 — Structure comes from space and surface steps first; lines are for where separation needs one.
- `craft-handrolled-control` P1 — A hand-rolled dropdown, select, modal or tooltip without keyboard navigation, focus management or ARIA should be an accessible primitive or the project's own component.
- `craft-missing-states` P1 — Every control has default, hover, focus, active and disabled states, and data has loading, empty and error states.
- `craft-power-user-keyboard` P2 — A power-user reaches the primary actions from the keyboard, with shortcuts for common ones, and Esc dismisses overlays.
- `craft-power-user-batch` P2 — Repeated work offers bulk select or batch edit where one-item-at-a-time would be slow.
- `craft-power-user-onboarding` P2 — Onboarding and tutorials can be skipped; the core task completes in under a minute for someone who knows similar products.
- `craft-power-user-confirmations` P3 — Low-risk actions skip redundant confirmation steps, and animations never block the next action.
- `drift-system-value` P1 — A value that differs from `.quirk/design/system.md`: name both, for example "radius 10px, system.md says 6px".
- `drift-missing-token` P2 — The same value repeats and the system has no token for it; add the token, then use it.
- `drift-one-off-component` P2 — A one-off implementation duplicates a shared component or pattern; replace it with the shared one.
- `drift-conceptual-mismatch` P2 — The flow, information architecture or hierarchy differs from comparable areas of the product; align the screen with them.
- `drift-local-defect` P2 — The implementation is incomplete or inconsistent with itself and nothing wider is wrong; fix it in place.

## Slop tells

These are defaults, not bans. A finding means nobody chose it; drop the finding when the product's direction did.

- `slop-gradient-text` P3 — Gradient text is decoration; emphasis comes from weight or size. (detector)
- `slop-hard-offset-shadow` P3 — An unblurred offset shadow such as `4px 4px 0` is a costume unless the direction is neobrutalist. (detector)
- `slop-glow-shadow` P3 — A zero-offset colored halo shadow is decoration; depth shadows carry an offset and a soft grey blur. (detector)
- `slop-radial-halo` P3 — A chromatic radial-gradient glow behind a dark page is the same tell drawn as a gradient; ground the surface with a solid color.
- `slop-glassmorphism` P3 — Glass and backdrop blur are for a specific effect, not for decoration.
- `slop-glyph-icons` P3 — Unicode glyphs or emoji standing in for icons; draw icons from one library in one stroke weight.
- `slop-decorative-chrome` P3 — Sparklines, progress rings and soft rounded boxes that stand in for content are decoration.
- `slop-mono-costume` P3 — Monospace is for code, data and measurement, not a costume for "technical".
- `slop-icon-tile-stack` P3 — A small rounded icon tile above a heading is the template feature card; place the icon beside the heading or inline.
- `slop-ghost-card` P3 — A hairline border under a wide soft shadow on every card is a default nobody chose; commit to an edge or an elevation.
- `slop-decorative-backgrounds` P3 — Repeating stripes and grid-line backgrounds need a real canvas, map or measuring surface under them.
- `slop-theme-by-habit` P3 — Light or dark was picked by category; pick it from who uses the screen, where and under what light.

## Check-intent

These flags ask for a reason, not a change. Report each as P3 with "justify or change"; never above P3. Drop one when the code or `.quirk/design/system.md` already gives the reason.

- `intent-side-stripe` P3 — A colored `border-left` of 2 to 8px on a rounded card, list item, callout or alert: justify or change; a subtler accent or no stripe usually reads better. (detector)
- `intent-overused-font` P3 — The first font family is Inter, Geist, Roboto or Arial: justify or change; keep it when the system chose it, otherwise pick a face with character. (detector)
- `intent-eyebrow-label` P3 — A small uppercase label above a heading: keep if it groups navigation, drop if decorative.
- `intent-hero-metric` P3 — A big number over a small label with supporting stats and an accent: keep if that number is what users came for, otherwise lead with the content it summarizes.
- `intent-identical-card-grid` P3 — Same-size cards of icon, heading and text as the page structure: keep if the items are truly parallel, otherwise vary layout by content and role.
- `intent-nested-cards` P3 — A card inside a card adds noise and depth: flatten with space and type, or say why the inner one needs its own surface.
