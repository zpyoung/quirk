# Move: adapt

Rework an existing screen for a different context: screen size, input method, platform or use. Adapting is rethinking the experience for the new context, not scaling pixels.

## When to use

- "Make this work on mobile", "this breaks on tablet", "port this to iOS", "make it print-friendly".
- A desktop-first screen that gets used on a phone, or the reverse.
- Hover-only controls, tiny targets, horizontal scroll, or a stretched phone layout on a tablet.

Ask for the target devices and usage context if you can't infer them. Don't ask about anything the code already shows.

## Read first

1. `.quirk/design/system.md` if it exists. Its spacing base, type scale and component patterns carry over to every context.
2. The target screen's markup, styles and breakpoints.
3. Native target (SwiftUI, UIKit, Compose, Android views): also read `surfaces/ios.md` or `surfaces/android.md`, then follow the native section below instead of the web procedure.

## Procedure (web)

1. **Name the source and target context.** Device, input (touch, mouse, keyboard), screen size, connection, and whether the user is at a desk or on the move. List what won't fit, what won't work (hover on touch) and what is inappropriate (a desktop pattern on a phone).
2. **Decide the structure per context.** Don't hide core functions to make room; if it matters, make it work.
   - Phone: one column, full-width components, bottom or drawer navigation, bottom sheets instead of dropdowns, primary content first and the rest behind tabs or disclosure.
   - Tablet: two columns, master-detail, side panels, both touch and pointer.
   - Desktop: use the width with max-width limits, persistent side navigation, denser tables, hover for extra detail, keyboard shortcuts.
   - Print: page breaks at logical points, no navigation or controls, expanded links, limited color.
3. **Write mobile-first.** Base styles for the small screen, `min-width` queries to add layout. Break where the content breaks, not at device sizes. Three breakpoints usually do. Use `clamp()` for fluid sizes and container queries for components that live in different-width slots.
4. **Adapt to input, not just width.** A laptop can have a touchscreen. Use `(pointer: coarse)` and `(hover: none)` for touch behavior, and never put function behind hover.
5. **Meet touch minimums.** Targets 44x44px, with space between neighbors. Body text at 16px or larger on phones, so iOS doesn't zoom on input focus.
6. **Handle device chrome.** Add `viewport-fit=cover` and use `env(safe-area-inset-*)` for fixed bars. Set `max(1rem, env(safe-area-inset-bottom))` on bottom bars.
7. **Reshape data views.** Wide tables become stacked rows with `data-label` attributes, or keep the table in a scroll container with a pinned first column. Use `<details>` for sections that collapse on small screens.
8. **Serve the right assets.** `srcset` and `sizes` for resolution, `<picture>` for different crops, lazy loading below the fold. `display: none` still downloads the content.

## Native section

Native targets restructure instead of reflow, inside the platform's own conventions.

- **Phone to tablet:** don't stretch the phone UI. Switch structure with size classes (iOS) or window size classes (Android): tab bar to sidebar or rail, list to split view, popovers where phones used sheets. Split View and multi-window can give a tablet a phone-width window, so drive layout from size classes, never from device model.
- **Orientation and foldables:** landscape restructures into side-by-side panes and never clips. Lock orientation only when the task needs it. On foldables, react to posture and hinge through window size classes.
- **iOS to Android or back:** translate idioms, never transplant them. Tab bar to navigation bar or rail, edge-swipe back to predictive Back, action sheet to bottom sheet, SF Symbols and Dynamic Type to Material Symbols and sp scaling. Keep the product's palette intent and type accent through the target's theming system.
- **Web to native:** replace web navigation with the platform's model, HTML-shaped controls with platform controls, hover affordances with touch-first ones, and px type with Dynamic Type or sp.
- Respect safe areas and window insets in every new configuration, including the keyboard.

## Preserve

- The information architecture. The same task lives in the same place conceptually across contexts; don't invent a different IA per device.
- Copy, labels and terminology, brand color, type choices and every pattern in system.md.
- Behavior outside the target screen and the contexts you were asked to cover.
- Existing keyboard and screen-reader behavior on the contexts that already work.

## Verify

- Check 320px, a tablet width and a large desktop. Check portrait and landscape on phone and tablet.
- Check touch, mouse and keyboard paths. Tab through the new layout.
- Zoom text to 200% and confirm nothing clips or scrolls sideways.
- Custom controls (sliders, drag surfaces, scroll strips): tap, drag to completion, and swipe across them along the page scroll axis. The page should scroll without triggering the control, and a drag along the control's axis should move the control, not the page.
- Say what produced the evidence: resized viewport, synthesized touch, which engine, or a real device. A resized viewport proves layout, never a gesture. Name what stayed untested and report it as a gap.
- Run the detector over the changed files and confirm each hit before reporting it. Skip the detector for native code; say the native checks were prose-only.

## Update system.md

If you added breakpoints, a touch-target size, a navigation pattern or a responsive component, offer once to record it in `.quirk/design/system.md`. Create the directory if it is missing.
