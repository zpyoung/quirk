# iOS

Use this for native iOS and iPadOS apps: SwiftUI, UIKit, React Native, Expo, or Flutter shipping to Apple hardware. Read `.quirk/design/system.md` first if it exists.

The Human Interface Guidelines govern structure, navigation and interaction in every job. Brand expresses through the layer the platform leaves open: tint, type, motion and content.

The detector doesn't read Swift or Kotlin. Checks here are prose only, and a review note says so.

## The slop test

Would a fluent iPhone user trust this app, or pause at an off-spec control? The tell is a port from a website: reinvented navigation bars, custom back gestures, web-shaped buttons, hover-dependent affordances. Use the platform's components and depart only for a reason the user would thank you for.

## Layout and structure

- Lay out inside the safe-area insets. Nothing under the notch, Dynamic Island, home indicator or rounded corners.
- Use system navigation. A tab bar for two to five top-level sections (sections, never actions), a navigation stack for hierarchy, a sheet for a self-contained task. No custom global nav and no mixed metaphors.
- Keep the left-edge swipe back alive. Never disable or overlay it.
- Large titles on top-level screens, collapsing to inline on scroll. Deep detail screens stay inline.
- Settings-shaped content uses grouped or inset lists, not bespoke card stacks.

## Touch targets

44 by 44 pt minimum for every tappable control, with room between neighbors.

## Type

- Use the system text styles (Large Title through Caption) so text follows Dynamic Type. No hard-coded point sizes.
- San Francisco carries the UI: body, labels and controls. A brand face may appear in display moments.
- Body is 17 pt and nothing goes below 11 pt.

## Color and materials

- Use semantic system colors (label, secondaryLabel, systemBackground, separator, tint). They adapt to Dark Mode and increased contrast. Raw hex breaks there.
- Dark Mode is a first-class appearance. Design and test both.
- One tint color drives interactive elements. It does not decorate.
- Use system materials for blur and translucency behind bars and sheets. No hand-rolled glass.

## Components and motion

- Use the platform controls: switch, segmented control, stepper, system pickers, action sheets, alerts, context menus, swipe actions. Reinventing these for flavor is the most common native slop.
- Use SF Symbols for icons, baseline-aligned and Dynamic Type aware. Don't mix in a web icon set.
- Modality is deliberate. A sheet is for a focused, dismissible sub-task and a full-screen cover is for immersion. Give a clear Cancel or Done, and honor swipe-to-dismiss unless data loss needs a guard.
- Use system transitions: push slides, sheets rise, dismiss reverses the entrance. Custom transitions that fight the navigation model disorient.
- Honor Reduce Motion with a crossfade in place of parallax and large slides. Motion still conveys state only.

## Verify the build

- Take screenshots from the Simulator, never a browser. Build and run, then capture with `xcrun simctl io booted screenshot <path>`. When several simulators run, replace `booted` with the UDID from `xcrun simctl list devices booted`, because display names can collide. Capture every device class the app ships to: at least one iPhone and, when iPad is a target, one iPad.
- Put Dark Mode and Dynamic Type in the pass. `xcrun simctl ui booted appearance dark` flips appearance. A check at a large Dynamic Type size catches the truncation a fixed layout hides.
- Simulators give breadth. Posture, gestures and performance need hardware. Say which one produced the evidence.
