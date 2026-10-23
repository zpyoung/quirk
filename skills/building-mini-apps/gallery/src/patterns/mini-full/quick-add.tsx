import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from "react"
import { CornerDownLeftIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

import { formatDayShort, formatTime } from "./dates"
import type { ParsedEntry } from "./parse"

const TAG_TOKEN = /(?:^|\s)\/([\w-]*)$/

/**
 * The always-visible input row. Enter submits when the title is non-empty and
 * `disabled` is false; Esc clears the text, then blurs; typing `/` offers `tags`.
 */
export function QuickAdd({
  value,
  onChange,
  onSubmit,
  entry,
  disabled,
  tags = [],
  inputRef,
}: {
  value: string
  onChange(v: string): void
  onSubmit(): void
  entry: ParsedEntry
  disabled?: boolean
  tags?: string[]
  inputRef?: RefObject<HTMLInputElement | null>
}) {
  const [caret, setCaret] = useState(0)
  const [active, setActive] = useState(0)
  const [dismissedAt, setDismissedAt] = useState<string | null>(null)
  const pendingCaret = useRef<number | null>(null)
  const fallbackRef = useRef<HTMLInputElement | null>(null)
  const ref = inputRef ?? fallbackRef

  const before = value.slice(0, caret)
  const token = TAG_TOKEN.exec(before)
  const query = token?.[1].toLowerCase() ?? ""
  const options = token ? tags.filter((t) => t.toLowerCase().startsWith(query)) : []
  const exact = options.length === 1 && options[0].toLowerCase() === query
  const open = token !== null && options.length > 0 && !exact && dismissedAt !== value
  const activeIndex = Math.min(active, Math.max(options.length - 1, 0))

  useEffect(() => {
    if (pendingCaret.current === null) return
    ref.current?.setSelectionRange(pendingCaret.current, pendingCaret.current)
    pendingCaret.current = null
  }, [value, ref])

  function pick(tag: string) {
    if (!token) return
    const start = before.length - token[0].replace(/^\s/, "").length
    const next = `${value.slice(0, start)}/${tag} ${value.slice(caret)}`
    pendingCaret.current = start + tag.length + 2
    setCaret(pendingCaret.current)
    onChange(next)
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.nativeEvent.isComposing) return
    if (open) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault()
        const step = e.key === "ArrowDown" ? 1 : -1
        setActive((activeIndex + step + options.length) % options.length)
        return
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault()
        pick(options[activeIndex])
        return
      }
      if (e.key === "Escape") {
        e.preventDefault()
        setDismissedAt(value)
        return
      }
    }
    if (e.key === "Enter") {
      e.preventDefault()
      if (!disabled && entry.title.trim()) onSubmit()
    } else if (e.key === "Escape") {
      e.preventDefault()
      if (value) onChange("")
      else e.currentTarget.blur()
    }
  }

  return (
    <div className="relative">
      <Input
        ref={ref}
        value={value}
        placeholder="Add: dentist tomorrow 10-11"
        aria-label="Quick add"
        role="combobox"
        aria-expanded={open}
        aria-controls="mini-full-tags"
        aria-autocomplete="list"
        aria-activedescendant={open ? `mini-full-tag-${activeIndex}` : undefined}
        autoComplete="off"
        spellCheck={false}
        onChange={(e) => {
          setCaret(e.target.selectionStart ?? e.target.value.length)
          setActive(0)
          onChange(e.target.value)
        }}
        onSelect={(e) => setCaret(e.currentTarget.selectionStart ?? 0)}
        onKeyDown={onKeyDown}
      />
      {open ? (
        <ul
          id="mini-full-tags"
          role="listbox"
          aria-label="Tags"
          className="absolute inset-x-0 top-full z-20 mt-1 rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
        >
          {options.map((tag, i) => (
            <li
              key={tag}
              id={`mini-full-tag-${i}`}
              role="option"
              aria-selected={i === activeIndex}
              className={cn(
                "cursor-pointer rounded-sm px-2 py-1 text-xs",
                i === activeIndex && "bg-accent text-accent-foreground"
              )}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => pick(tag)}
            >
              /{tag}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

function whenText(entry: ParsedEntry): string {
  if (!entry.start) return "None"
  const day = formatDayShort(entry.start)
  if (entry.allDay) return day
  const end = entry.end ? `–${formatTime(entry.end)}` : ""
  return `${day}, ${formatTime(entry.start)}${end}`
}

/** Live card for the text being typed: title, when, all-day, tag and an Add button. */
export function ParsePreview({
  entry,
  onSubmit,
  disabled,
}: {
  entry: ParsedEntry
  onSubmit(): void
  disabled?: boolean
}) {
  const values = {
    when: whenText(entry),
    allDay: entry.start ? (entry.allDay ? "Yes" : "No") : "None",
    tag: entry.tag ?? "None",
  }
  const [shown, setShown] = useState(values)
  const [flash, setFlash] = useState<Partial<Record<keyof typeof values, boolean>>>({})

  if (shown.when !== values.when || shown.allDay !== values.allDay || shown.tag !== values.tag) {
    setShown(values)
    setFlash({
      when: shown.when !== values.when,
      allDay: shown.allDay !== values.allDay,
      tag: shown.tag !== values.tag,
    })
  }

  useEffect(() => {
    if (!Object.values(flash).some(Boolean)) return
    const timer = setTimeout(() => setFlash({}), 700)
    return () => clearTimeout(timer)
  }, [flash])

  const cell = (key: keyof typeof values) =>
    cn(
      "-mx-1 min-w-0 rounded px-1 transition-colors duration-500",
      flash[key] && "bg-[var(--mini-accent-soft)] motion-reduce:bg-transparent"
    )

  return (
    <Card size="sm" role="group" aria-label="Parsed entry" className="rounded-md">
      <CardContent className="flex flex-col gap-2">
        <dl className="grid grid-cols-[4.5rem_minmax(0,1fr)] items-baseline gap-x-2 gap-y-1 text-xs">
          <dt className="text-muted-foreground">Title</dt>
          <dd className="line-clamp-2 min-w-0 text-sm font-medium break-words">
            {entry.title || <span className="text-muted-foreground">None</span>}
          </dd>
          <dt className="text-muted-foreground">When</dt>
          <dd className={cell("when")}>{values.when}</dd>
          <dt className="text-muted-foreground">All-day</dt>
          <dd className={cell("allDay")}>{values.allDay}</dd>
          <dt className="text-muted-foreground">Tag</dt>
          <dd className={cell("tag")}>
            {entry.tag ? <Badge variant="outline">{entry.tag}</Badge> : values.tag}
          </dd>
        </dl>
        <Button
          size="sm"
          className="w-full"
          disabled={disabled || !entry.title.trim()}
          onClick={onSubmit}
        >
          Add
          <CornerDownLeftIcon aria-hidden />
        </Button>
      </CardContent>
    </Card>
  )
}
