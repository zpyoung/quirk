# Optimize

Find the real performance bottleneck in a UI, fix it, and measure the difference.

## When to use

- The screen loads slowly, janks while scrolling or animating, or lags after input.
- A bundle, image set or font set is heavy.
- Core Web Vitals regressed.

Don't optimize what isn't slow. Without a measurement you are guessing.

## Read first

- `.quirk/design/system.md`, if it exists. Optimization must not change its look. Keep its tokens and motion rules.
- The project's build setup, bundler, image pipeline and any existing performance budget.

## Procedure

1. **Measure first.** Record the current state: LCP, INP and CLS, load and first-paint timing, bundle and image sizes, request count, and for runtime issues frame rate and long tasks. Measure on a throttled network and a mid-range device, not just a fast laptop. If the app can't run, say so and work from the code.
2. **Name the bottleneck.** What is slow (load, interaction, animation), why (large images, heavy JavaScript, layout thrash, re-renders), for whom (everyone, mobile, slow networks) and how badly. Fix the biggest one first.
3. **Apply the fix that matches the cause.**
   - Images: right size for the display, AVIF or WebP, `srcset`, lazy loading below the fold only, explicit dimensions or `aspect-ratio`.
   - JavaScript: split by route, lazy load heavy components, drop unused dependencies and third-party scripts, defer non-critical code.
   - CSS and fonts: remove unused CSS, subset and limit font weights, use `font-display: swap` or `optional`, preload only the critical font, and consider system fonts.
   - Rendering: batch DOM reads before writes, flatten deep DOM, use `content-visibility: auto` or `contain` on independent regions, virtualize very long lists.
   - Frameworks: stop needless re-renders, memoize expensive work, and don't create functions or objects in hot render paths without cause.
   - Animation: move with `transform` and `opacity`, and don't animate `width`, `height`, `top`, `left` or margins. Don't use `transition: all`. Use `will-change` only on known expensive cases. Keep product motion at 150 to 250ms and state-conveying.
   - Network: paginate, request only needed fields, compress, cache and put static assets on a CDN.
   - Slow connections: skeletons, optimistic updates and progressive enhancement.
   - Memory: remove listeners, cancel subscriptions, clear timers and abort requests on unmount.
4. **Target thresholds.** LCP under 2.5s, INP under 200ms, CLS under 0.1.

## Preserve

- Behavior and appearance. A faster screen that looks or acts different is a regression.
- Accessibility: alt text, focus order, reduced-motion handling. Don't trade them for speed.
- Above-the-fold content. Never lazy load it.
- Everything outside the bottleneck. Skip micro-optimizations while a major problem remains.

## Verify

- Compare before and after on the same metrics, network and device. Report the numbers.
- Test a low-end device and a throttled connection.
- Functionality and visuals are unchanged. Run the project's tests.
- Console is clean, with no new layout shift.
- For web code, run `python3 "$SKILL_DIR/scripts/detect.py" <files>`. It flags `motion-transition-all` and `motion-layout-property`. Confirm each hit in context.
- Check that it also feels faster, not only that the number moved.

## Save to system.md

Optimization rarely changes design decisions. If it changed a token or pattern, such as a font stack or motion timing, offer once to update `.quirk/design/system.md`. Create `.quirk/design/` when saving.
