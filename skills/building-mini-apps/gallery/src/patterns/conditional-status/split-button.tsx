import { useState, type ReactNode } from "react"
import { ChevronDownIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Popover, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

/**
 * A primary button joined to a chevron button. The primary half acts at once;
 * the chevron opens `children`, which must render a `PopoverContent` (a
 * `ConditionMenu` does). With no `children` only the primary half is drawn.
 */
export function SplitButton({
  label,
  onPrimary,
  disabled,
  menuLabel,
  open,
  onOpenChange,
  children,
}: {
  label: string
  onPrimary(): void
  disabled?: boolean
  /** Accessible name of the chevron half, such as "Resolve options". */
  menuLabel?: string
  open?: boolean
  onOpenChange?(open: boolean): void
  children?: ReactNode
}) {
  const [inner, setInner] = useState(false)
  const isOpen = open ?? inner
  const setOpen = (next: boolean) => {
    setInner(next)
    onOpenChange?.(next)
  }

  return (
    <Popover open={isOpen} onOpenChange={setOpen}>
      <div role="group" aria-label={label} className="inline-flex">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={onPrimary}
          className={cn("relative focus-visible:z-10", children && "rounded-r-none")}
        >
          {label}
        </Button>
        {children ? (
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              disabled={disabled}
              aria-label={menuLabel ?? `${label} options`}
              aria-haspopup="menu"
              onKeyDown={(event) => {
                if (event.key === "ArrowDown" && !isOpen) {
                  event.preventDefault()
                  setOpen(true)
                }
              }}
              className="relative -ml-px rounded-l-none focus-visible:z-10"
            >
              <ChevronDownIcon aria-hidden />
            </Button>
          </PopoverTrigger>
        ) : null}
      </div>
      {children}
    </Popover>
  )
}
