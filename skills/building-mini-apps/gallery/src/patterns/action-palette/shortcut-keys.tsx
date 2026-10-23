import { Kbd, KbdGroup } from "@/components/ui/kbd"

import { formatShortcut } from "./format-shortcut"

/** One keycap per key of a shortcut, e.g. ⌘ ⇧ F. */
export function ShortcutKeys({ shortcut }: { shortcut: string }) {
  return (
    <KbdGroup>
      {formatShortcut(shortcut).map((key, index) => (
        <Kbd key={`${index}-${key}`}>{key}</Kbd>
      ))}
    </KbdGroup>
  )
}
