import { useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Input } from "@/components/ui/input"
import type { ExpandField, ExpandItem } from "./types"

function readValue(item: ExpandItem, key: string): unknown {
  return (item as Record<string, unknown>)[key]
}

function patchOf<T extends ExpandItem>(key: string, value: string | undefined): Partial<T> {
  return { [key]: value } as unknown as Partial<T>
}

function hasText(value: unknown): value is string {
  return typeof value === "string" && value !== ""
}

function parseDay(value: string): Date {
  const [year, month, day] = value.split("-").map(Number)
  return new Date(year, month - 1, day)
}

function formatDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function ClearButton({ label, onClick }: { label: string; onClick(): void }) {
  return (
    <Button variant="ghost" size="sm" onClick={onClick}>
      Clear {label.toLowerCase()}
    </Button>
  )
}

function DateEditor<T extends ExpandItem>({
  field,
  item,
  onChange,
  onClose,
}: {
  field: Pick<ExpandField<T>, "key" | "label">
  item: T
  onChange(patch: Partial<T>): void
  onClose(): void
}) {
  const current = readValue(item, field.key)
  return (
    <div className="flex flex-col items-stretch">
      <Calendar
        mode="single"
        selected={hasText(current) ? parseDay(current) : undefined}
        defaultMonth={hasText(current) ? parseDay(current) : undefined}
        onSelect={(date) => {
          if (!date) return
          onChange(patchOf<T>(field.key, formatDay(date)))
          onClose()
        }}
      />
      {hasText(current) ? (
        <ClearButton
          label={field.label}
          onClick={() => {
            onChange(patchOf<T>(field.key, undefined))
            onClose()
          }}
        />
      ) : null}
    </div>
  )
}

function TextEditor<T extends ExpandItem>({
  field,
  item,
  onChange,
  onClose,
}: {
  field: Pick<ExpandField<T>, "key" | "label">
  item: T
  onChange(patch: Partial<T>): void
  onClose(): void
}) {
  const stored = readValue(item, field.key)
  const [draft, setDraft] = useState(hasText(stored) ? stored : "")
  return (
    <div className="flex w-64 flex-col gap-2">
      <Input
        aria-label={field.label}
        value={draft}
        placeholder={field.label}
        onChange={(event) => {
          setDraft(event.target.value)
          onChange(patchOf<T>(field.key, event.target.value))
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") onClose()
        }}
      />
      {draft !== "" ? (
        <ClearButton
          label={field.label}
          onClick={() => {
            onChange(patchOf<T>(field.key, undefined))
            onClose()
          }}
        />
      ) : null}
    </div>
  )
}

/** Date stored as a `YYYY-MM-DD` string under `key`, edited in a calendar popover. */
export function DateField<T extends ExpandItem>(
  key: keyof T & string,
  label: string,
  icon: ReactNode
): ExpandField<T> {
  return {
    key,
    label,
    icon,
    glyph: icon,
    isSet: (item) => hasText(readValue(item, key)),
    display: (item) => {
      const value = readValue(item, key)
      return hasText(value)
        ? parseDay(value).toLocaleDateString(undefined, {
            weekday: "short",
            day: "numeric",
            month: "short",
          })
        : null
    },
    clear: () => patchOf<T>(key, undefined),
    Editor: (props) => <DateEditor field={{ key, label }} {...props} />,
  }
}

/** Free text stored as a string under `key`, edited in an input popover. */
export function TextField<T extends ExpandItem>(
  key: keyof T & string,
  label: string,
  icon: ReactNode
): ExpandField<T> {
  return {
    key,
    label,
    icon,
    glyph: icon,
    isSet: (item) => hasText(readValue(item, key)),
    display: (item) => {
      const value = readValue(item, key)
      return hasText(value) ? value : null
    },
    clear: () => patchOf<T>(key, undefined),
    Editor: (props) => <TextEditor field={{ key, label }} {...props} />,
  }
}
