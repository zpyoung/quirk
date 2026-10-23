import { useEffect, type ReactNode } from "react"

import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"

/**
 * Applies the OS light/dark preference to <html> when nothing else has set a
 * theme class. Any later write to the class list by a ThemeProvider or a manual
 * toggle, even to the value already applied, hands ownership to that writer for good.
 */
function useSystemTheme() {
  useEffect(() => {
    const root = document.documentElement
    if (root.classList.contains("light") || root.classList.contains("dark")) return

    const query = window.matchMedia("(prefers-color-scheme: dark)")
    const observer = new MutationObserver(() => release())
    let owned = true

    function release() {
      owned = false
      observer.disconnect()
      query.removeEventListener("change", sync)
    }

    function sync() {
      if (observer.takeRecords().length > 0) return release()
      root.classList.remove("light", "dark")
      root.classList.add(query.matches ? "dark" : "light")
      observer.takeRecords()
    }

    sync()
    observer.observe(root, { attributes: true, attributeFilter: ["class"] })
    query.addEventListener("change", sync)

    return () => {
      if (owned && observer.takeRecords().length === 0) root.classList.remove("light", "dark")
      release()
    }
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
        <header data-mini="shell-header" className="flex h-10 shrink-0 items-center gap-3 border-b px-3">
          <h1 data-mini="title" className="text-sm font-semibold tracking-tight">{title}</h1>
          <div className="ml-auto flex items-center gap-1">{toolbar}</div>
        </header>
        <div className="flex min-h-0 flex-1">
          {sidebar ? (
            <aside data-mini="shell-sidebar" className="w-56 shrink-0 overflow-y-auto border-r bg-sidebar p-2 text-sidebar-foreground">
              {sidebar}
            </aside>
          ) : null}
          <main data-mini="shell-main" className="min-w-0 flex-1 overflow-auto">{children}</main>
        </div>
      </div>
      <Toaster />
    </TooltipProvider>
  )
}
