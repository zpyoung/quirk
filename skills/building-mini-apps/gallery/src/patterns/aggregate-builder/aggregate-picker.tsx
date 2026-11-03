import type { Ref } from "react"

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import type { AggregateDef } from "./aggregate"
import { keepBlockKeys } from "./field-picker"
import type { AggregateFn } from "./types"

/** A select of aggregate functions, grouped as Count, Statistics and Percentiles. */
export function AggregatePicker({
  id,
  value,
  onChange,
  options,
  disabled,
  triggerRef,
}: {
  id?: string
  value: AggregateFn
  onChange: (fn: AggregateFn) => void
  options: AggregateDef[]
  disabled?: boolean
  triggerRef?: Ref<HTMLButtonElement>
}) {
  const groups = [...new Set(options.map((option) => option.group))]
  return (
    <Select
      value={value}
      onValueChange={(next) => onChange(next as AggregateFn)}
      disabled={disabled}
    >
      <SelectTrigger
        id={id}
        ref={triggerRef}
        size="sm"
        aria-label="Aggregate function"
        onKeyDown={keepBlockKeys}
        className="w-full min-w-0"
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {groups.map((group) => (
          <SelectGroup key={group}>
            <SelectLabel>{group}</SelectLabel>
            {options
              .filter((option) => option.group === group)
              .map((option) => (
                <SelectItem key={option.fn} value={option.fn}>
                  {option.label}
                </SelectItem>
              ))}
          </SelectGroup>
        ))}
      </SelectContent>
    </Select>
  )
}
