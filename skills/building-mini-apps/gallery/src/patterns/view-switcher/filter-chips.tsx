import { PlusIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"

import { describeRule, type Field } from "./fields"
import type { FilterRule } from "./types"

/** One chip per filter rule, shown only while the active view has filters. */
export function FilterChips({
  rules,
  fields,
  disabled,
  onEdit,
  onRemove,
  onAdd,
}: {
  rules: FilterRule[]
  fields: Field[]
  disabled: boolean
  onEdit(): void
  onRemove(index: number): void
  onAdd(): void
}) {
  return (
    <div
      role="group"
      aria-label="Active filters"
      className="flex shrink-0 flex-wrap items-center gap-1.5 border-b px-3 py-1.5"
    >
      {rules.map((rule, index) => {
        const label = describeRule(rule, fields)
        return (
          <span
            key={index}
            className="inline-flex h-6 items-center rounded-full border bg-(--mini-accent-soft) text-xs"
          >
            <button
              type="button"
              disabled={disabled}
              onClick={onEdit}
              className="h-full rounded-l-full pr-1 pl-2.5 outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
            >
              {label}
            </button>
            <button
              type="button"
              disabled={disabled}
              aria-label={`Remove filter: ${label}`}
              onClick={() => onRemove(index)}
              className="flex h-full items-center rounded-r-full pr-1.5 pl-0.5 text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60"
            >
              <XIcon className="size-3" />
            </button>
          </span>
        )
      })}
      <Button variant="ghost" size="xs" disabled={disabled} onClick={onAdd}>
        <PlusIcon />
        Add filter
      </Button>
    </div>
  )
}
