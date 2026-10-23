import { ChevronRightIcon } from "lucide-react"

import { cn } from "@/lib/utils"

/** One-line trail; every crumb before the last calls `onNavigate`, the last is the current place. */
export function Breadcrumb({
  trail,
  onNavigate,
}: {
  trail: string[]
  onNavigate?: (index: number) => void
}) {
  return (
    <nav aria-label="Breadcrumb" className="flex h-8 items-center border-b px-3 text-xs">
      <ol className="flex min-w-0 items-center gap-1">
        {trail.map((crumb, index) => {
          const last = index === trail.length - 1
          return (
            <li key={index} className={cn("flex items-center gap-1", last ? "min-w-0" : "shrink-0")}>
              {last || !onNavigate ? (
                <span
                  aria-current={last ? "page" : undefined}
                  className={cn("truncate", last ? "font-medium" : "text-muted-foreground")}
                >
                  {crumb}
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => onNavigate(index)}
                  className="truncate rounded-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
                >
                  {crumb}
                </button>
              )}
              {last ? null : (
                <ChevronRightIcon className="size-3 shrink-0 text-muted-foreground" aria-hidden />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
