import { CheckIcon, MinusIcon } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * Checkbox with a third "mixed" state, drawn as a dash. It is a button with
 * `role="checkbox"`, so it takes Space and Enter natively. `onToggle` receives
 * the Shift state of the click for range selection.
 */
export function IndeterminateCheckbox({
  checked,
  onToggle,
  label,
  tabIndex,
  disabled,
  className,
}: {
  checked: boolean | "mixed"
  onToggle: (event: { shiftKey: boolean }) => void
  label: string
  tabIndex?: number
  disabled?: boolean
  className?: string
}) {
  const mixed = checked === "mixed"
  const on = checked !== false
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={mixed ? "mixed" : checked}
      aria-label={label}
      tabIndex={tabIndex}
      disabled={disabled}
      data-state={mixed ? "mixed" : checked ? "checked" : "unchecked"}
      onMouseDown={(event) => {
        if (event.shiftKey) event.preventDefault()
      }}
      onClick={(event) => {
        event.stopPropagation()
        onToggle({ shiftKey: event.shiftKey })
      }}
      className={cn(
        "relative flex size-4 shrink-0 items-center justify-center rounded-[4px] border border-input bg-background transition-colors outline-none after:absolute after:-inset-2.5 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50",
        on && "border-primary bg-primary text-primary-foreground",
        className
      )}
    >
      {mixed ? (
        <MinusIcon className="size-3.5" aria-hidden />
      ) : checked ? (
        <CheckIcon className="size-3.5" aria-hidden />
      ) : null}
    </button>
  )
}
