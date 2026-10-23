import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

import type { FieldDef, PropValue } from "./types"
import { useDraft } from "./use-draft"

const slot = "h-7 w-full justify-start rounded-md border-transparent bg-transparent px-1.5 text-sm shadow-none hover:bg-muted dark:bg-transparent"

function toText(value: PropValue) {
  return value === null ? "" : String(value)
}

function fromText(field: FieldDef, text: string): PropValue {
  if (text.trim() === "") return null
  if (field.type !== "number") return text
  const n = Number(text)
  return Number.isFinite(n) ? n : null
}

function SelectValue({ field, value, onChange }: { field: FieldDef; value: PropValue; onChange: (value: PropValue) => void }) {
  const [open, setOpen] = useState(false)
  const pick = (next: PropValue) => {
    setOpen(false)
    if (next !== value) onChange(next)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={field.label}
          className={cn(slot, "inline-flex items-center rounded-md outline-none focus-visible:ring-3 focus-visible:ring-ring/50")}
        >
          {value === null ? (
            <span className="text-muted-foreground">Empty</span>
          ) : (
            <Badge variant="secondary">{String(value)}</Badge>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-56 p-0">
        <Command>
          <CommandInput placeholder={`Find ${field.label.toLowerCase()}`} aria-label={`Find ${field.label}`} />
          <CommandList>
            <CommandEmpty>No options</CommandEmpty>
            {(field.options ?? []).map((option) => (
              <CommandItem key={option} value={option} data-checked={option === value} onSelect={() => pick(option)}>
                {option}
              </CommandItem>
            ))}
            {value === null ? null : (
              <CommandItem value="clear selection" onSelect={() => pick(null)}>
                <span className="text-muted-foreground">Clear</span>
              </CommandItem>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

function TypedValue({ field, value, onChange }: { field: FieldDef; value: PropValue; onChange: (value: PropValue) => void }) {
  const [draft, setDraft] = useDraft(toText(value))
  const [focused, setFocused] = useState(false)

  const commit = () => {
    const next = fromText(field, draft)
    if (next !== value) onChange(next)
    else setDraft(toText(value))
  }

  // an empty date shows the grey "Empty" placeholder until it is focused
  const type = field.type === "date" ? (draft !== "" || focused ? "date" : "text") : field.type === "url" ? "url" : field.type

  return (
    <Input
      type={type}
      aria-label={field.label}
      placeholder="Empty"
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onFocus={() => setFocused(true)}
      onBlur={() => {
        setFocused(false)
        commit()
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur()
      }}
      className={cn(slot, "md:text-sm", field.type === "number" && "text-left")}
    />
  )
}

/** Editor for one property value; select applies on pick, text-like types apply on Enter or blur. */
export function PropertyValue({
  field,
  value,
  onChange,
}: {
  field: FieldDef
  value: PropValue
  onChange: (value: PropValue) => void
}) {
  if (field.type === "checkbox") {
    return (
      <div className="flex h-7 items-center px-1.5">
        <Checkbox aria-label={field.label} checked={value === true} onCheckedChange={(checked) => onChange(checked === true)} />
      </div>
    )
  }
  if (field.type === "select") return <SelectValue field={field} value={value} onChange={onChange} />
  return <TypedValue field={field} value={value} onChange={onChange} />
}
