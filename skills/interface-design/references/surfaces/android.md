# Android

Use this for native Android apps: Jetpack Compose, Android Views, React Native, Expo, or Flutter shipping to Android hardware. Read `.quirk/design/system.md` first if it exists.

Material Design 3 governs structure, navigation and interaction in every job. Brand expresses through Material's theming: color roles, type scale, shape and motion. A cross-platform app that also ships to iPhone still owes iOS its guarantees on that hardware: safe-area insets, Reduce Motion and edge-swipe back (see [ios.md](ios.md)).

The detector doesn't read Kotlin or XML. Checks here are prose only, and a review note says so.

## The slop test

Would a fluent Android user trust this app, or trip on an off-spec component? The common tell is an iOS app wearing Android's skin: a bottom-only navigation copied from iPhone, a back arrow that ignores the system Back gesture, Cupertino-shaped switches and dialogs. Material 3 is the rulebook. Follow its components and theme the brand through it.

## Layout and structure

- Match Material navigation to the size class. A navigation bar (bottom, three to five destinations) on compact width, and a navigation rail or drawer on expanded width. Don't ship a phone bottom bar untouched on a tablet.
- System Back always works. Honor the predictive Back gesture and the Back button, and never trap or hijack them.
- Go edge-to-edge and apply window insets for the status bar, navigation bar, display cutout and keyboard, so content never hides behind them.
- Use a top app bar for screen context, with a FAB when the screen has one primary action.

## Touch targets

48 by 48 dp minimum for every target, with at least 8 dp between them.

## Type

- Use the Material type scale: Display, Headline, Title, Body and Label, each in large, medium and small. Map text to roles and don't hand-pick sizes per screen.
- Roboto is the system face. Theme a brand face in through the type scale and keep body, labels and controls legible and consistent.
- Set type in sp, never fixed px, so it follows the system font-size setting.

## Color and theming

- Use Material color roles (primary, on-primary, surface, surface-variant, secondary-container, outline, error). Role tokens resolve light, dark and contrast variants. Raw hex breaks there.
- Use Dynamic Color (Material You) where it fits, taking the scheme from the wallpaper on Android 12 and up, with a static fallback.
- Dark theme is a first-class scheme. Design and test it. It is never a quick invert.
- Convey elevation through the standard surface tonal levels, with shadow where appropriate. No arbitrary drop shadows.

## Components and motion

- Use Material components: buttons (filled, tonal, outlined, text), FAB, switches, chips, snackbars, bottom sheets, dialogs, and the navigation bar, rail and drawer. Never port iOS controls or invent equivalents.
- One FAB, one primary action. Never stack FABs or spend one on a secondary task.
- Snackbars give transient feedback, with an action when useful, never a toast for that. Dialogs are for decisions that must interrupt.
- Use Material motion patterns (container transform, shared axis, fade through) with standard easing and durations, and keep motion to state changes. Honor the system Remove animations setting with a crossfade or an instant cut.

## Verify the build

- Take screenshots from the emulator or a connected device, never a browser. Build and install, then capture with `adb exec-out screencap -p > <path>`. With several devices attached, pick one with `adb -s <serial>`. Capture every device class the app ships to: at least one phone and, when tablets are a target, one tablet.
- Put dark theme and font scale in the pass. `adb shell cmd uimode night yes` flips the theme, and `adb shell settings put system font_scale 1.3` catches the clipped labels a fixed layout hides. Read both settings first (`adb shell cmd uimode night`, `adb shell settings get system font_scale`) and restore them afterward. With several targets attached, pass the same `-s <serial>` on these commands.
- Emulators give breadth. Gestures, refresh rates and performance need hardware. Say which one produced the evidence.
