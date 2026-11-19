# Harden

Make a UI hold up against long text, odd input, other languages, errors, slow networks and heavy data.

## When to use

- It only works with tidy sample data.
- The user reports overflow, broken layouts in another language, missing error states or double submits.
- You're preparing a screen for real traffic.

## Read first

- `.quirk/design/system.md`, if it exists. New states (errors, empty, loading) use its patterns, spacing and tokens.
- The components and data sources behind the target, to see which inputs and failures can actually occur.

## Procedure

1. **List the stress cases that apply.**
   - Inputs: very long, very short and empty text, emoji, accents, RTL and CJK, huge numbers, 1000+ items, no data.
   - Failures: offline, slow or timed-out requests, 400, 401, 403, 404, 429 and 500 responses, validation and permission errors, concurrent operations.
   - Locale: translations 30 to 40 percent longer, RTL, date, number and currency formats, plural rules.
2. **Text and layout.**
   - Truncate with an ellipsis or line clamp where a single line is intended, and let other text wrap with `overflow-wrap`. Give flex and grid children `min-width: 0` so they can shrink.
   - Don't fix widths on text containers. Let them grow with content, and make sure they survive 200 percent zoom.
   - Keep body at 16px or more on mobile. iOS Safari zooms focused inputs below 16px.
3. **Internationalization.**
   - Use logical properties (`margin-inline-start`, `padding-inline`, `border-inline-end`) and flip directional icons under RTL.
   - Format with `Intl.DateTimeFormat` and `Intl.NumberFormat`, and use the i18n library's plural handling, not `count !== 1 ? 's' : ''`.
   - Arabic script: never strip the zero-width non-joiner (U+200C), preserve the original Yeh and Kaf variants in storage but match them as equivalent in search and validation, use locale-aware digits and calendars.
   - Use UTF-8 throughout and test emoji, which can span several code units.
4. **Errors.** Say what happened and what to do next, near where it happened. Offer retry on network failures. Handle each status code on purpose: validation errors inline, login redirect for 401, a permission message for 403, a not-found state for 404, a rate-limit message for 429, a generic error with a support route for 500. Keep the user's input after any error. One failing component must not block the whole screen.
5. **Edge states.** Give each of these its own state with a clear next action: empty list, no search results, loading (say what is loading), permission denied, read-only. Paginate or virtualize large sets. Disable submit while a request is in flight, handle races, and roll back optimistic updates on failure.
6. **Interrupted gestures** (sliders, drag surfaces, scrollable control strips). A second pointer mid-drag must not steal the first. On `pointercancel`, `lostpointercapture`, release outside the control or window blur, clear the dragging state and release capture. The next tap or drag must work without a reload.
7. **Validation.** Client checks for required fields, format and length, with hints tied by `aria-describedby`. Never rely on the client alone. Mention server-side validation to the user when you can't see it.
8. **Accessibility under stress.** Keyboard reach for everything, focus managed in modals, live regions for dynamic changes, and no meaning carried by color alone (check forced-colors and high-contrast modes).
9. **Resilience.** Clean up listeners, timers and in-flight requests on unmount, and debounce search input.

Only handle cases the screen can actually meet. Don't add defensive code for impossible states.

## Preserve

- Appearance in the normal, tidy-data case. Hardening should be invisible until something goes wrong.
- Copy for existing states. Write new messages in the product's voice, specific rather than "Error occurred".
- Everything outside the target.

## Verify

Exercise each case you handled, and add a regression test where the project's runner can drive it.

- Names of 100+ characters, emoji in every text field, an RTL and a CJK sample, a long translation.
- Offline, throttled and forced API errors, with a retry that works.
- 1000+ items, an empty dataset, ten rapid clicks on submit.
- For gestures, add a second finger mid-drag, scroll across the control, release outside it and switch windows, then drag again. State what produced the evidence (emulated viewport, synthesized touch, which engine, a physical device) and what stayed untested.

## Save to system.md

If you added reusable patterns (error, empty or loading states), offer once to record them in `.quirk/design/system.md` with measured values. Create `.quirk/design/` when saving.
