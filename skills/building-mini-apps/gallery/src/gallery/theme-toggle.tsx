import { MonitorIcon, MoonIcon, SunIcon } from "lucide-react"

import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"

const NEXT = { system: "light", light: "dark", dark: "system" } as const
const LABEL = { system: "System theme", light: "Light theme", dark: "Dark theme" } as const

/** Cycles system, light, dark; system follows the OS. */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const Icon = theme === "system" ? MonitorIcon : theme === "light" ? SunIcon : MoonIcon

  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label={`${LABEL[theme]}. Switch to ${LABEL[NEXT[theme]].toLowerCase()}`}
      title={LABEL[theme]}
      onClick={() => setTheme(NEXT[theme])}
    >
      <Icon />
    </Button>
  )
}
