import { useCallback, useMemo, useRef, useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"

import { sharedValue } from "./shared-value"
import { TruncatedText } from "./truncated-text"
import type {
  FieldDef,
  InspectorItem,
  InspectorSchema,
  SectionDef,
} from "./types"

type Shared = { mixed: boolean; value: unknown }

type FieldProps = {
  field: FieldDef<InspectorItem>
  shared: Shared
  commit: (value: unknown) => void
}

const shellClass =
  "flex h-8 items-center gap-1.5 rounded-md bg-muted px-2 text-sm focus-within:ring-2 focus-within:ring-ring/50"
const bareInputClass =
  "h-full flex-1 rounded-none border-0 bg-transparent p-0 text-sm shadow-none focus-visible:ring-0 dark:bg-transparent md:text-sm"

function emptyVerb(label: string) {
  return `Add ${label.toLowerCase()}`
}

function FieldLabel({ children }: { children: ReactNode }) {
  return (
    <span className="max-w-[45%] shrink-0 truncate text-xs text-muted-foreground">
      {children}
    </span>
  )
}

/** Uncommitted text for a field: kept in a ref too so a blur right after Esc sees the revert. */
function useDraft() {
  const [draft, setDraft] = useState<string | null>(null)
  const ref = useRef<string | null>(null)
  const set = useCallback((next: string | null) => {
    ref.current = next
    setDraft(next)
  }, [])
  return { draft, ref, set }
}

function TextField({ field, shared, commit }: FieldProps) {
  const { draft, ref, set } = useDraft()
  const current =
    shared.mixed || shared.value == null ? "" : String(shared.value)

  const flush = () => {
    const next = ref.current
    set(null)
    if (next === null || next === current) return
    if (shared.mixed && next === "") return
    commit(next)
  }

  return (
    <label className={shellClass}>
      <FieldLabel>{field.label}</FieldLabel>
      <Input
        value={draft ?? current}
        placeholder={shared.mixed ? "Mixed" : emptyVerb(field.label)}
        className={bareInputClass}
        onChange={(event) => set(event.target.value)}
        onBlur={flush}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault()
            flush()
          } else if (event.key === "Escape") {
            set(null)
          }
        }}
      />
    </label>
  )
}

function NumberField({ field, shared, commit }: FieldProps) {
  const { draft, ref, set } = useDraft()
  const current = typeof shared.value === "number" ? shared.value : null
  const display = shared.mixed || current === null ? "" : String(current)
  const step = field.step ?? 1

  const clamp = (n: number) =>
    Math.min(
      field.max ?? Infinity,
      Math.max(field.min ?? -Infinity, Number(n.toFixed(10)))
    )

  const parse = (raw: string) => {
    const text = raw.trim()
    const n = Number(text)
    return text === "" || !Number.isFinite(n) ? null : clamp(n)
  }

  const flush = () => {
    const raw = ref.current
    set(null)
    if (raw === null) return
    const next = parse(raw)
    if (next === null || (!shared.mixed && next === current)) return
    commit(next)
  }

  const nudge = (delta: number) => {
    if (shared.mixed) return
    const base = (ref.current === null ? current : parse(ref.current)) ?? 0
    set(null)
    commit(clamp(base + delta))
  }

  return (
    <label className={shellClass}>
      <FieldLabel>{field.label}</FieldLabel>
      <Input
        type="text"
        inputMode="decimal"
        value={draft ?? display}
        placeholder={shared.mixed ? "Mixed" : emptyVerb(field.label)}
        className={bareInputClass}
        onChange={(event) => set(event.target.value)}
        onBlur={flush}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault()
            flush()
          } else if (event.key === "Escape") {
            set(null)
          } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
            event.preventDefault()
            const size = event.shiftKey ? step * 10 : step
            nudge(event.key === "ArrowUp" ? size : -size)
          }
        }}
      />
      {field.unit ? (
        <span aria-hidden className="shrink-0 text-xs text-muted-foreground">
          {field.unit}
        </span>
      ) : null}
    </label>
  )
}

function SelectField({ field, shared, commit }: FieldProps) {
  const value = shared.mixed || shared.value == null ? "" : String(shared.value)
  return (
    <div className={shellClass}>
      <FieldLabel>{field.label}</FieldLabel>
      <Select value={value} onValueChange={commit}>
        <SelectTrigger
          aria-label={field.label}
          className="h-full min-w-0 flex-1 justify-between rounded-none border-0 bg-transparent p-0 shadow-none focus-visible:ring-0 dark:bg-transparent dark:hover:bg-transparent"
        >
          <SelectValue
            placeholder={shared.mixed ? "Mixed" : emptyVerb(field.label)}
          />
        </SelectTrigger>
        <SelectContent>
          {(field.options ?? []).map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function ToggleField({ field, shared, commit }: FieldProps) {
  return (
    <label className={cn(shellClass, "cursor-pointer")}>
      <FieldLabel>{field.label}</FieldLabel>
      <Checkbox
        className="ml-auto"
        checked={shared.mixed ? "indeterminate" : shared.value === true}
        onCheckedChange={(checked) => commit(checked === true)}
      />
    </label>
  )
}

function PopoverField({ field, shared, commit }: FieldProps) {
  const { value } = shared
  const summary = shared.mixed
    ? "Mixed"
    : value == null || value === ""
      ? emptyVerb(field.label)
      : typeof value === "object"
        ? "Edit"
        : String(value)

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            shellClass,
            "w-full cursor-pointer text-left outline-none focus-visible:ring-2"
          )}
        >
          <FieldLabel>{field.label}</FieldLabel>
          <span
            className={cn(
              "min-w-0 flex-1 truncate",
              (shared.mixed || value == null || value === "") &&
                "text-muted-foreground"
            )}
          >
            {summary}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent side="left" align="start" aria-label={field.label}>
        {field.renderEditor?.(shared.mixed ? undefined : value, commit)}
      </PopoverContent>
    </Popover>
  )
}

function FieldControl(props: FieldProps) {
  switch (props.field.kind) {
    case "number":
      return <NumberField {...props} />
    case "select":
      return <SelectField {...props} />
    case "toggle":
      return <ToggleField {...props} />
    case "popover":
      return <PopoverField {...props} />
    default:
      return <TextField {...props} />
  }
}

function Section<T extends InspectorItem>({
  section,
  selected,
  onChange,
}: {
  section: SectionDef<T>
  selected: T[]
  onChange: (patch: Partial<T>) => void
}) {
  const [userOpen, setUserOpen] = useState(false)
  const shared = section.fields.map((field) => sharedValue(selected, field.key))
  const isEmpty = shared.every((s) => !s.mixed && s.value === undefined)

  const fields = (
    <div className="grid grid-cols-2 gap-1.5">
      {section.fields.map((field, index) => (
        <div
          key={field.key}
          className={field.kind === "number" ? "col-span-1" : "col-span-2"}
        >
          <FieldControl
            field={field as unknown as FieldDef<InspectorItem>}
            shared={shared[index]}
            commit={(value) =>
              onChange({ [field.key]: value } as unknown as Partial<T>)
            }
          />
        </div>
      ))}
    </div>
  )

  if (!section.optional) {
    return (
      <section aria-label={section.title} className="flex flex-col gap-1.5">
        <h3 data-mini="group-header" className="text-xs font-semibold">{section.title}</h3>
        {fields}
      </section>
    )
  }

  const open = userOpen || !isEmpty
  return (
    <Collapsible
      open={open}
      onOpenChange={setUserOpen}
      className="flex flex-col gap-1.5"
    >
      <CollapsibleTrigger asChild disabled={!isEmpty}>
        <Button
          variant="ghost"
          size="xs"
          data-mini="group-header"
          className={cn(
            "justify-start px-1 disabled:opacity-100",
            open ? "font-semibold text-foreground" : "text-muted-foreground"
          )}
        >
          {open ? section.title : `+ ${section.title}`}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>{fields}</CollapsibleContent>
    </Collapsible>
  )
}

function commonSections<T extends InspectorItem>(
  selected: T[],
  schema: InspectorSchema<T>
): SectionDef<T>[] {
  const perItem = selected.map((item) => schema[item.type as T["type"]] ?? [])
  if (perItem.length === 0) return []
  if (perItem.length === 1) return perItem[0]

  const common = perItem
    .map(
      (sections) => new Set(sections.flatMap((s) => s.fields.map((f) => f.key)))
    )
    .reduce((a, b) => new Set([...a].filter((key) => b.has(key))))
  return perItem[0]
    .map((section) => ({
      ...section,
      fields: section.fields.filter((f) => common.has(f.key)),
    }))
    .filter((section) => section.fields.length > 0)
}

/**
 * Right-dock editor for the current selection: a pinned header, then the
 * schema's sections for the selected type (or the fields shared by all selected
 * types). Shows `pageView` when nothing is selected.
 */
export function PropertiesPanel<T extends InspectorItem>({
  selected,
  schema,
  onChange,
  pageView,
}: {
  selected: T[]
  schema: InspectorSchema<T>
  onChange: (patch: Partial<T>) => void
  pageView?: ReactNode
}) {
  const sections = useMemo(
    () => commonSections(selected, schema),
    [selected, schema]
  )
  const selectionKey = selected.map((item) => item.id).join("\u0000")

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="shrink-0 border-b px-3 py-2">
        {selected.length === 0 ? (
          <p className="text-sm font-semibold">Page</p>
        ) : selected.length === 1 ? (
          <>
            <p className="text-sm font-semibold capitalize">
              {selected[0].type}
            </p>
            <div className="flex min-w-0 text-xs text-muted-foreground">
              <TruncatedText text={selected[0].title} side="left" />
            </div>
          </>
        ) : (
          <>
            <p className="text-sm font-semibold">{selected.length} selected</p>
            <p className="text-xs text-muted-foreground">
              Type in a Mixed field to set it on all.
            </p>
          </>
        )}
      </header>
      <ScrollArea className="min-h-0 flex-1 [&_[data-slot=scroll-area-viewport]>div]:block!">
        <div data-panel-body className="flex flex-col gap-4 p-3">
          {selected.length === 0
            ? (pageView ?? (
                <p className="text-xs text-muted-foreground">
                  Nothing selected. Pick an item in the tree or on the canvas to
                  edit it.
                </p>
              ))
            : sections.map((section) => (
                <Section
                  key={`${selectionKey}:${section.id}`}
                  section={section}
                  selected={selected}
                  onChange={onChange}
                />
              ))}
        </div>
      </ScrollArea>
    </div>
  )
}
