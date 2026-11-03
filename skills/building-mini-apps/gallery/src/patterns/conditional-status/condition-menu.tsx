import {
  useId,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react"
import { CheckIcon, ChevronLeftIcon, ChevronRightIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PopoverContent } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

import { durationMs, validateInput } from "./status"
import type {
  ConditionInput,
  ConditionKind,
  DurationUnit,
  InputValue,
} from "./types"

const FIELD =
  "h-8 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

function trimEllipsis(label: string): string {
  return label.replace(/…$/, "")
}

function PickerForm({
  kind,
  input,
  onBack,
  onApply,
}: {
  kind: ConditionKind
  input: ConditionInput
  onBack(): void
  onApply(value: InputValue): void
}) {
  const uid = useId()
  const [raw, setRaw] = useState(() => {
    if (input.type === "count" || input.type === "duration") {
      return String(input.default ?? 1)
    }
    if (input.type === "choice") return input.options[0] ?? ""
    return ""
  })
  const [unit, setUnit] = useState<DurationUnit>(
    input.type === "duration" ? (input.unit ?? "hours") : "hours"
  )
  const [error, setError] = useState<string | null>(null)
  const fieldRef = useRef<HTMLInputElement & HTMLSelectElement>(null)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    let value: InputValue
    if (input.type === "count") value = Number(raw)
    else if (input.type === "duration") value = durationMs(Number(raw), unit)
    else value = raw.trim()
    const problem = validateInput(input, value)
    if (problem) {
      setError(problem)
      fieldRef.current?.focus()
      return
    }
    onApply(value)
  }

  const fieldId = `${uid}-field`
  const errorId = `${uid}-error`
  const described = error ? errorId : undefined

  return (
    <form onSubmit={submit} className="flex flex-col gap-2 p-1" noValidate>
      <button
        type="button"
        onClick={onBack}
        className="flex w-fit items-center gap-1 rounded-md px-1 py-0.5 text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <ChevronLeftIcon className="size-3.5" aria-hidden />
        Back
      </button>
      <p className="px-1 text-sm font-medium">{trimEllipsis(kind.label)}</p>
      <label htmlFor={fieldId} className="px-1 text-xs text-muted-foreground">
        {input.label}
      </label>
      <div className="flex items-center gap-2 px-1">
        {input.type === "choice" ? (
          <select
            id={fieldId}
            ref={fieldRef}
            value={raw}
            onChange={(event) => setRaw(event.target.value)}
            aria-invalid={error ? true : undefined}
            aria-describedby={described}
            className={cn(FIELD, "min-w-0 flex-1")}
          >
            {input.options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        ) : (
          <Input
            id={fieldId}
            ref={fieldRef}
            autoFocus
            type={
              input.type === "count" || input.type === "duration"
                ? "number"
                : "text"
            }
            inputMode={
              input.type === "count" || input.type === "duration"
                ? "numeric"
                : undefined
            }
            min={input.type === "count" ? (input.min ?? 1) : undefined}
            value={raw}
            placeholder={input.type === "text" ? input.placeholder : undefined}
            onChange={(event) => {
              setRaw(event.target.value)
              setError(null)
            }}
            aria-invalid={error ? true : undefined}
            aria-describedby={described}
            className="h-8 min-w-0 flex-1"
          />
        )}
        {input.type === "count" ? (
          <span className="shrink-0 text-xs text-muted-foreground">
            {input.unit}
          </span>
        ) : null}
        {input.type === "duration" ? (
          <select
            aria-label="Unit"
            value={unit}
            onChange={(event) => setUnit(event.target.value as DurationUnit)}
            className={cn(FIELD, "shrink-0")}
          >
            <option value="minutes">minutes</option>
            <option value="hours">hours</option>
            <option value="days">days</option>
          </select>
        ) : null}
      </div>
      {error ? (
        <p id={errorId} role="alert" className="px-1 text-xs text-destructive">
          {error}
        </p>
      ) : null}
      <Button type="submit" size="sm" className="mx-1 mt-1">
        Apply
      </Button>
    </form>
  )
}

/**
 * The popover body for one split button: a headed list of conditions. A
 * condition with an `input` shows a right arrow and opens a small picker in place
 * of the list. Renders a `PopoverContent`, so it goes inside `SplitButton` or any
 * `Popover`; `onChoose` is the caller's cue to close it.
 */
export function ConditionMenu({
  heading,
  kinds,
  current,
  onChoose,
}: {
  heading: string
  kinds: ConditionKind[]
  /** The condition already in force, shown checked. */
  current?: { kind: string; value?: InputValue }
  onChoose(kind: string, value?: InputValue): void
}) {
  const uid = useId()
  const rows = kinds.filter((kind) => kind.inMenu !== false)
  const [picking, setPicking] = useState<ConditionKind | null>(null)
  const [returned, setReturned] = useState(false)
  const currentIndex = rows.findIndex((kind) => kind.id === current?.kind)
  const [active, setActive] = useState(Math.max(0, currentIndex))
  const listRef = useRef<HTMLDivElement>(null)

  const items = () =>
    Array.from(
      listRef.current?.querySelectorAll<HTMLElement>('[role^="menuitem"]') ?? []
    )

  const back = () => {
    setPicking(null)
    setReturned(true)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const all = items()
    const at = all.indexOf(document.activeElement as HTMLElement)
    let to: number | null = null
    if (event.key === "ArrowDown") to = (at + 1) % all.length
    else if (event.key === "ArrowUp") to = (at - 1 + all.length) % all.length
    else if (event.key === "Home") to = 0
    else if (event.key === "End") to = all.length - 1
    else if (event.key === "ArrowRight" && at >= 0 && rows[at]?.input) {
      event.preventDefault()
      setPicking(rows[at])
      return
    }
    if (to === null) return
    event.preventDefault()
    all[to]?.focus()
  }

  return (
    <PopoverContent
      align="start"
      className="w-72 gap-0 p-1"
      onEscapeKeyDown={(event) => {
        if (picking) {
          event.preventDefault()
          back()
        }
      }}
    >
      {picking?.input ? (
        <PickerForm
          kind={picking}
          input={picking.input}
          onBack={back}
          onApply={(value) => onChoose(picking.id, value)}
        />
      ) : (
        <>
          <div
            id={`${uid}-heading`}
            className="px-2 py-1.5 text-xs font-medium text-muted-foreground"
          >
            {heading}
          </div>
          <div
            ref={listRef}
            role="menu"
            aria-labelledby={`${uid}-heading`}
            onKeyDown={onKeyDown}
            className="flex flex-col"
          >
            {rows.map((kind, index) => {
              const isCurrent = kind.id === current?.kind
              return (
                <button
                  key={kind.id}
                  type="button"
                  role={current ? "menuitemradio" : "menuitem"}
                  aria-checked={current ? isCurrent : undefined}
                  tabIndex={index === active ? 0 : -1}
                  autoFocus={returned && index === active}
                  onFocus={() => setActive(index)}
                  onClick={() =>
                    kind.input ? setPicking(kind) : onChoose(kind.id)
                  }
                  className="flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none hover:bg-accent hover:text-accent-foreground focus-visible:bg-accent focus-visible:text-accent-foreground"
                >
                  <span className="flex size-4 shrink-0 items-center justify-center">
                    {isCurrent ? (
                      <CheckIcon className="size-3.5" aria-hidden />
                    ) : null}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{kind.label}</span>
                    {kind.hint ? (
                      <span className="block truncate text-xs text-muted-foreground">
                        {kind.hint}
                      </span>
                    ) : null}
                  </span>
                  {kind.input ? (
                    <ChevronRightIcon
                      className="size-4 shrink-0 text-muted-foreground"
                      aria-hidden
                    />
                  ) : null}
                </button>
              )
            })}
          </div>
        </>
      )}
    </PopoverContent>
  )
}
