import { ChevronDownIcon, ChevronRightIcon } from "lucide-react"

/**
 * Child-count pill that collapses or expands a subtree. Not a tab stop: the
 * tree's arrow keys do the same job, and a click keeps focus where it was.
 */
export function CollapsePill({
  count,
  expanded,
  onToggle,
  label,
}: {
  count: number
  expanded: boolean
  onToggle: () => void
  label: string
}) {
  const Chevron = expanded ? ChevronDownIcon : ChevronRightIcon
  return (
    <button
      type="button"
      tabIndex={-1}
      aria-label={label}
      data-mini="pill"
      onMouseDown={(event) => event.preventDefault()}
      onClick={(event) => {
        event.stopPropagation()
        onToggle()
      }}
      className="mr-1.5 inline-flex h-4 shrink-0 items-center gap-0.5 rounded-full border bg-background px-1.5 text-[10px] leading-none text-muted-foreground tabular-nums hover:bg-accent hover:text-accent-foreground"
    >
      {count}
      <Chevron className="size-3" aria-hidden />
    </button>
  )
}
