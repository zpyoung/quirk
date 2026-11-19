# Overdrive

Push one part of a product UI past what users expect, so it feels extraordinary in use.

## When to use

- The user explicitly asks for something ambitious, "wow" or beyond the usual for a table, dialog, form, chart or transition.
- A part of the product has a hard technical edge: 100k rows, instant search, a transition between states.

This is about how the UI feels, not what the product does. Real-time collaboration, offline support or new backend features are product decisions, not overdrive.

## Read first

- `.quirk/design/system.md`, if it exists. Ambition must sit inside its direction, depth strategy, accent and motion rules.
- The surface and its users. A technique that impresses in one place is embarrassing in another. A settings page with instant optimistic saves and clear state transitions is extraordinary. The same page with a particle system is not.

## Procedure

1. **Propose before building.** This move misfires more than any other. Think through two or three directions that differ in technique and ambition, and describe what each looks and feels like. Ask the user to pick one, with each direction's description and trade-offs (browser support, performance cost, complexity) written inside the option so they can choose between things they can read. Write no code until they pick.
2. **Choose what "extraordinary" means for this surface.**
   - Functional UI (tables, forms, dialogs, navigation): how it feels. A dialog that morphs from its trigger, validation that feels instant, drag and drop with believable physics.
   - Performance-critical UI: it never hesitates. Filtering 50k items without a flicker, no main-thread block.
   - Data-heavy UI (charts, dashboards): fluid rendering of large sets, and transitions between data states instead of replacements.
3. **Pick from the toolkit by goal.**
   - State transitions: View Transitions API (same-document in all browsers, cross-document not in Firefox), `@starting-style` for entry from `display: none`, spring physics (motion, GSAP or a small solver).
   - Large data: virtual scrolling (TanStack Virtual for complex cases), Canvas or WebGL for datasets too big for SVG, Web Workers and OffscreenCanvas to keep the main thread free, WASM for heavy computation.
   - Animated values: `@property` for gradients and colors, the Web Animations API for composable, cancellable motion.
   - Scroll-linked effects (`animation-timeline: scroll()`) only when scroll position is the state being shown. Firefox lacks support, so provide a static fallback.
4. **Keep product discipline.** Motion conveys state and runs 150 to 250ms. Go outside that only where the user asked for it, and say so. One signature moment beats several competing ones. Skip decorative shaders, particles and sound.
5. **Enhance progressively.** Every technique needs a working fallback: `@supports` for CSS features, feature detection for WebGPU with a WebGL2 fallback, and a good experience without the enhancement. Respect `prefers-reduced-motion`.
6. **Hold the performance line.** Target 60fps and simplify below 50. Initialize heavy resources lazily, pause off-screen rendering, and test on mid-range devices. No jank, ever.
7. **Refine the last 20 percent.** Easing curves, stagger offsets and secondary motion decide whether it feels inevitable. Don't ship the first version that works.

Don't use technical ambition to cover weak fundamentals. Fix hierarchy, layout and states first with the other moves.

## Preserve

- What the product does, and its visual identity.
- Existing behavior and copy outside the chosen target.
- Accessibility: keyboard paths, focus, and reduced-motion behavior.

## Verify

When the app can run, watch the effect in it. Check timing, easing and smoothness. An effect that runs can still stutter or land on the wrong frame. Batch fixes between looks.

- Removal test: take it out. If nobody would notice, it wasn't worth it.
- Device test: a phone and a mid-range laptop stay smooth.
- Context test: it fits this product and its users.
- The fallback path still looks good with the enhancement disabled.

## Save to system.md

If you introduced a reusable motion or interaction pattern, offer once to record it in `.quirk/design/system.md`. Create `.quirk/design/` when saving.
