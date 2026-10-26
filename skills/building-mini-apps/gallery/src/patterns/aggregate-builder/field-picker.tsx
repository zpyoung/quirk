import type { KeyboardEvent, Ref } from "react"
import { ClockIcon, HashIcon, TypeIcon } from "lucide-react"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"

import type { FieldKind } from "./types"

export const NONE_VALUE = "__none"

/** Keys the block binds; a focused picker must not treat them as typeahead. */
export const BLOCK_KEYS = new Set(["v", "g", "s", "c", "1", "2"])

export function keepBlockKeys(event: KeyboardEvent<HTMLElement>) {
  if (event.ctrlKey || event.metaKey || event.altKey) return
  if (BLOCK_KEYS.has(event.key.toLowerCase())) event.preventDefault()
}

export type FieldOption = {
  value: string
  label: string
  kind?: FieldKind
}

const KIND_ICONS = { number: HashIcon, text: TypeIcon, time: ClockIcon }

function OptionLabel({ option }: { option: FieldOption }) {
  const Icon = option.kind ? KIND_ICONS[option.kind] : null
  return (
    <span className="flex min-w-0 items-center gap-1.5">
      {Icon ? <Icon className="size-3 shrink-0 text-muted-foreground" aria-hidden /> : null}
      <span className="truncate">{option.label}</span>
    </span>
  )
}

/**
 * A select over named fields (or any short list of options), with a kind icon per option, an
 * optional "None" choice that reports `null`, and a disabled state.
 */
export function FieldPicker({
  id,
  label,
  value,
  onChange,
  options,
  noneLabel,
  disabled,
  placeholder,
  triggerRef,
  className,
}: {
  id?: string
  /** Accessible name; the rail also pairs a visible heading with it. */
  label: string
  value: string | null
  onChange: (value: string | null) => void
  options: FieldOption[]
  /** Adds a first choice with this label that selects no field. */
  noneLabel?: string
  disabled?: boolean
  placeholder?: string
  triggerRef?: Ref<HTMLButtonElement>
  className?: string
}) {
  const current = value ?? (noneLabel ? NONE_VALUE : undefined)
  return (
    <Select
      value={current}
      onValueChange={(next) => onChange(next === NONE_VALUE ? null : next)}
      disabled={disabled}
    >
      <SelectTrigger
        id={id}
        ref={triggerRef}
        size="sm"
        aria-label={label}
        onKeyDown={keepBlockKeys}
        className={cn("w-full min-w-0", className)}
      >
        <SelectValue placeholder={placeholder ?? "Pick a field"} />
      </SelectTrigger>
      <SelectContent>
        {noneLabel ? <SelectItem value={NONE_VALUE}>{noneLabel}</SelectItem> : null}
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            <OptionLabel option={option} />
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
