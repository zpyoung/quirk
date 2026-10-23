import { useEffect, type ReactNode } from "react"

import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"

/**
 * Applies the OS light/dark preference to <html> until something else (a
 * ThemeProvider or a manual toggle) changes the class, then stops interfering.
 */
function useSystemTheme() {
  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)")
    const root = document.documentElement
    let applied: "dark" | "light" | null = null

    const sync = () => {
      if (applied !== null && !root.classList.contains(applied)) return
      applied = query.matches ? "dark" : "light"
      root.classList.remove("light", "dark")
      root.classList.add(applied)
    }

    sync()
    query.addEventListener("change", sync)
    return () => query.removeEventListener("change", sync)
  }, [])
}

/**
 * Page frame for a mini app: title bar with an optional toolbar, an optional
 * sidebar, and a scrolling main area. Provides the tooltip and toast hosts
 * that blocks rely on.
 */
export function AppShell({
  title,
  sidebar,
  toolbar,
  children,
}: {
  title: string
  sidebar?: ReactNode
  toolbar?: ReactNode
  children: ReactNode
}) {
  useSystemTheme()

  return (
    <TooltipProvider>
      <div className="flex h-svh flex-col bg-background text-foreground">
        <header className="flex h-10 shrink-0 items-center gap-3 border-b px-3">
          <h1 className="text-sm font-semibold tracking-tight">{title}</h1>
          <div className="ml-auto flex items-center gap-1">{toolbar}</div>
        </header>
        <div className="flex min-h-0 flex-1">
          {sidebar ? (
            <aside className="w-56 shrink-0 overflow-y-auto border-r bg-sidebar p-2 text-sidebar-foreground">
              {sidebar}
            </aside>
          ) : null}
          <main className="min-w-0 flex-1 overflow-auto">{children}</main>
        </div>
      </div>
      <Toaster />
    </TooltipProvider>
  )
}
