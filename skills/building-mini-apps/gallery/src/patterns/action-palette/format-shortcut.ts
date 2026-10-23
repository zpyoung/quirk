const GLYPHS: Record<string, readonly [mac: string, other: string]> = {
  mod: ["⌘", "Ctrl"],
  meta: ["⌘", "Win"],
  cmd: ["⌘", "Win"],
  ctrl: ["⌃", "Ctrl"],
  control: ["⌃", "Ctrl"],
  alt: ["⌥", "Alt"],
  option: ["⌥", "Alt"],
  shift: ["⇧", "Shift"],
  enter: ["↵", "Enter"],
  return: ["↵", "Enter"],
  backspace: ["⌫", "Backspace"],
  delete: ["⌦", "Del"],
  esc: ["Esc", "Esc"],
  escape: ["Esc", "Esc"],
  tab: ["⇥", "Tab"],
  space: ["Space", "Space"],
  up: ["↑", "↑"],
  down: ["↓", "↓"],
  left: ["←", "←"],
  right: ["→", "→"],
  slash: ["/", "/"],
}

function isApplePlatform(): boolean {
  return typeof navigator !== "undefined" && /mac|iphone|ipad/i.test(navigator.userAgent)
}

/** Splits a react-hotkeys-hook shortcut into one label per key, with glyphs chosen for the platform. */
export function formatShortcut(shortcut: string): string[] {
  const apple = isApplePlatform()
  return shortcut
    .split("+")
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean)
    .map((part) => {
      const glyph = GLYPHS[part]
      if (glyph) return apple ? glyph[0] : glyph[1]
      return part.charAt(0).toUpperCase() + part.slice(1)
    })
}
