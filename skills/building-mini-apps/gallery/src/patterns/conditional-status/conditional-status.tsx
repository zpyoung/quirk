import {
  useEffect,
  useEffectEvent,
  useId,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react"
import { useHotkeys } from "react-hotkeys-hook"
import {
  ArchiveIcon,
  CheckIcon,
  CircleCheckIcon,
  CircleIcon,
  ClockIcon,
  RotateCcwIcon,
  TrendingUpIcon,
  XIcon,
} from "lucide-react"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import { ConditionMenu } from "./condition-menu"
import { SplitButton } from "./split-button"
import { holdText, nextStatus, primaryEvent } from "./status"
import type {
  InputValue,
  StateIcon,
  StatusEvent,
  StatusGroup,
  StatusItem,
  StatusModel,
  StatusRecord,
  Tone,
  Transition,
} from "./types"

export type ConditionalStatusProps<T extends StatusItem> = {
  items: T[]
  /** Holds functions: pass a stable object. */
  model: StatusModel
  onChange: (
    id: string,
    status: StatusRecord,
    transition: Transition | null
  ) => void
  status?: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  /** Defaults to `Date.now`. A new function runs a time check at once. */
  clock?: () => number
  tickMs?: number
  highlightedId?: string | null
  onHighlightedIdChange?: (id: string | null) => void
  renderLead?: (item: T) => ReactNode
  emptyTitle?: string
  "aria-label"?: string
}

const TONE: Record<Tone, string> = {
  neutral: "bg-secondary text-secondary-foreground",
  good: "bg-primary/10 text-primary",
  warn: "bg-[var(--mini-accent-soft)] text-foreground ring-1 ring-inset ring-border",
  bad: "bg-destructive/10 text-destructive",
  muted: "bg-muted text-muted-foreground",
}

const ICON: Record<StateIcon, typeof CircleIcon> = {
  open: CircleIcon,
  done: CircleCheckIcon,
  regressed: RotateCcwIcon,
  archived: ArchiveIcon,
  escalating: TrendingUpIcon,
  snoozed: ClockIcon,
}

const INTERACTIVE =
  "a,button,input,select,textarea,summary,[role=button],[role=link],[contenteditable=true]"

function useControllable<V>(
  value: V | undefined,
  initial: V,
  onChange?: (next: V) => void
): [V, (next: V) => void] {
  const [inner, setInner] = useState(initial)
  const controlled = value !== undefined
  const set = (next: V) => {
    if (!controlled) setInner(next)
    onChange?.(next)
  }
  return [controlled ? value : inner, set]
}

function signature(record: StatusRecord): string {
  const { last } = record
  return last ? `${last.at}|${last.to}|${last.reason}` : ""
}

function StateChip({
  model,
  state,
}: {
  model: StatusModel
  state: string
}) {
  const def = model.states[state] ?? { label: state, tone: "neutral" as Tone }
  const Icon = ICON[def.icon ?? "open"]
  return (
    <span
      className={cn(
        "inline-flex h-5 shrink-0 items-center gap-1 rounded-4xl px-2 text-xs font-medium whitespace-nowrap",
        TONE[def.tone]
      )}
    >
      <Icon className="size-3" aria-hidden />
      {def.label}
    </span>
  )
}

/**
 * A list of items with Resolve-and-Archive style split buttons that act on the
 * checked rows, or the highlighted row when none are checked. The block applies
 * the user's choices and the passing of time through `nextStatus` and reports
 * every change to `onChange`; events from the app (occurrences, releases,
 * signals) go through `nextStatus` in the caller. Takes data as props and never
 * reads the store. Keys act when focus is on the page body or inside this block,
 * never while typing in an input.
 */
export function ConditionalStatus<T extends StatusItem>({
  items,
  model,
  onChange,
  status = "ready",
  error,
  onRetry,
  clock,
  tickMs = 5000,
  highlightedId: highlightedProp,
  onHighlightedIdChange,
  renderLead,
  emptyTitle = "Nothing here yet",
  "aria-label": ariaLabel = "Items",
}: ConditionalStatusProps<T>) {
  const uid = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const handled = useRef(new Map<string, { source: StatusRecord; at: number }>())
  const readClock = clock ?? Date.now

  const [highlightedId, setHighlightedId] = useControllable<string | null>(
    highlightedProp,
    null,
    onHighlightedIdChange
  )
  const [checked, setChecked] = useState<ReadonlySet<string>>(new Set())
  const [openGroup, setOpenGroup] = useState<string | null>(null)
  const [now, setNow] = useState(readClock)
  const [announcement, setAnnouncement] = useState("")

  const ready = status === "ready"
  const keysOn = ready && items.length > 0
  const activeIndex = items.findIndex((item) => item.id === highlightedId)
  const rowDomId = (id: string) => `${uid}-row-${encodeURIComponent(id)}`

  const targets = useMemo(() => {
    const picked = items.filter((item) => checked.has(item.id))
    return picked.length > 0
      ? picked
      : items.filter((item) => item.id === highlightedId)
  }, [items, checked, highlightedId])
  const checkedCount = items.filter((item) => checked.has(item.id)).length

  const signatures = useMemo(
    () => new Map(items.map((item) => [item.id, signature(item.status)])),
    [items]
  )
  const [seen, setSeen] = useState(signatures)
  if (signatures !== seen) {
    setSeen(signatures)
    for (const item of items) {
      const was = seen.get(item.id)
      const is = signatures.get(item.id)
      const last = item.status.last
      if (is && was !== undefined && was !== is && last) {
        const label = model.states[item.status.state]?.label ?? item.status.state
        setAnnouncement(`${item.title}: ${label}. ${last.reason}`)
        break
      }
    }
  }

  const checkTime = useEffectEvent(() => {
    const at = readClock()
    setNow(at)
    const wall = performance.now()
    for (const item of items) {
      if (!item.status.hold) continue
      const done = handled.current.get(item.id)
      if (done?.source === item.status && wall - done.at < tickMs * 2) continue
      const result = nextStatus(item.status, { type: "time" }, model, at)
      if (result.record === item.status) continue
      handled.current.set(item.id, { source: item.status, at: wall })
      onChange(item.id, result.record, result.transition)
    }
  })
  useEffect(() => {
    if (!ready) return
    const first = setTimeout(checkTime, 0)
    const timer = setInterval(checkTime, tickMs)
    return () => {
      clearTimeout(first)
      clearInterval(timer)
    }
  }, [ready, clock, tickMs])

  useEffect(() => {
    if (!highlightedId) return
    document
      .getElementById(rowDomId(highlightedId))
      ?.scrollIntoView?.({ block: "nearest" })
  })

  const focusList = () => listRef.current?.focus({ preventScroll: true })

  const apply = (make: () => StatusEvent) => {
    const at = readClock()
    const event = make()
    for (const item of targets) {
      const result = nextStatus(item.status, event, model, at)
      if (result.record !== item.status) {
        onChange(item.id, result.record, result.transition)
      }
    }
  }

  const press = (group: StatusGroup) =>
    apply(() =>
      primaryEvent(
        targets.map((item) => item.status),
        group,
        model
      )
    )

  const choose = (kind: string, value?: InputValue) => {
    setOpenGroup(null)
    apply(() => ({ type: "choose", kind, value }))
  }

  const move = (to: "next" | "previous" | "first" | "last") => {
    if (items.length === 0) return
    let index: number
    if (to === "first") index = 0
    else if (to === "last") index = items.length - 1
    else if (activeIndex === -1) index = to === "next" ? 0 : items.length - 1
    else {
      index = Math.min(
        items.length - 1,
        Math.max(0, activeIndex + (to === "next" ? 1 : -1))
      )
    }
    setHighlightedId(items[index].id)
    if (document.activeElement !== listRef.current) focusList()
  }

  const toggleChecked = (id: string) =>
    setChecked((current) => {
      const next = new Set(current)
      if (!next.delete(id)) next.add(id)
      return next
    })

  const inScope = (event: KeyboardEvent) => {
    const target = event.target
    if (target === document.body || target === document.documentElement) {
      return true
    }
    return target instanceof Node && rootRef.current?.contains(target) === true
  }
  const inList = (event: KeyboardEvent) => {
    const target = event.target
    if (target === document.body || target === document.documentElement) {
      return true
    }
    return target instanceof Node && listRef.current?.contains(target) === true
  }
  const navigate = (event: KeyboardEvent, to: Parameters<typeof move>[0]) => {
    if (!inList(event)) return
    event.preventDefault()
    move(to)
  }

  useHotkeys("j,down", (event) => navigate(event, "next"), { enabled: keysOn })
  useHotkeys("k,up", (event) => navigate(event, "previous"), { enabled: keysOn })
  useHotkeys("home", (event) => navigate(event, "first"), { enabled: keysOn })
  useHotkeys("end", (event) => navigate(event, "last"), { enabled: keysOn })
  useHotkeys(
    "x,space",
    (event) => {
      if (!inList(event) || !highlightedId) return
      event.preventDefault()
      toggleChecked(highlightedId)
    },
    { enabled: keysOn }
  )
  useHotkeys(
    "esc",
    (event) => {
      if (!inScope(event)) return
      if (checkedCount > 0) {
        event.preventDefault()
        setChecked(new Set())
      } else if (highlightedId) {
        event.preventDefault()
        setHighlightedId(null)
      }
    },
    { enabled: keysOn }
  )

  const groupKeys = model.groups.flatMap((group) =>
    group.key ? [group.key, `shift+${group.key}`] : []
  )
  useHotkeys(
    groupKeys,
    (event) => {
      if (!inScope(event) || targets.length === 0) return
      const group = model.groups.find(
        (candidate) => candidate.key === event.key.toLowerCase()
      )
      if (!group) return
      event.preventDefault()
      if (!event.shiftKey) return press(group)
      if (model.kinds.some((kind) => kind.group === group.id && kind.inMenu !== false)) {
        setOpenGroup(group.id)
      }
    },
    { enabled: keysOn }
  )

  const onRowClick = (event: ReactMouseEvent<HTMLElement>, id: string) => {
    const control = (event.target as Element).closest(INTERACTIVE)
    if (control && control !== event.currentTarget) return
    focusList()
    if ((event.target as Element).closest("[data-check]")) toggleChecked(id)
    else setHighlightedId(id)
  }

  let listArea: ReactNode
  if (status === "loading") {
    listArea = <LoadingState label="Loading items" />
  } else if (status === "error") {
    listArea = (
      <ErrorState
        error={error ?? new Error("Unknown error")}
        onRetry={onRetry}
      />
    )
  } else if (items.length === 0) {
    listArea = (
      <EmptyState
        title={emptyTitle}
        description="Items you add will show up here."
      />
    )
  } else {
    const active = activeIndex === -1 ? undefined : items[activeIndex]
    listArea = (
      <div
        ref={listRef}
        role="listbox"
        tabIndex={0}
        aria-label={ariaLabel}
        aria-multiselectable="true"
        aria-activedescendant={active ? rowDomId(active.id) : undefined}
        className="h-full overflow-y-auto outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/50"
      >
        {items.map((item) => {
          const highlighted = item.id === highlightedId
          const isChecked = checked.has(item.id)
          const hold = holdText(item.status, model, now)
          const counts = [
            model.counters?.occurrences
              ? `${item.status.occurrences} ${model.counters.occurrences}`
              : null,
            model.counters?.users
              ? `${item.status.users} ${model.counters.users}`
              : null,
          ].filter(Boolean)
          const line = [
            hold ?? item.status.last?.reason,
            counts.length > 0 ? counts.join(" · ") : null,
            item.meta,
          ]
            .filter(Boolean)
            .join(" · ")
          return (
            <div
              key={item.id}
              id={rowDomId(item.id)}
              role="option"
              aria-selected={isChecked}
              title={item.title}
              onClick={(event) => onRowClick(event, item.id)}
              className={cn(
                "flex min-h-[3.25rem] cursor-default items-center gap-3 border-b border-border/60 px-3 py-1.5 select-none",
                highlighted ? "bg-accent" : "hover:bg-accent/50"
              )}
            >
              <span
                data-check
                aria-hidden
                className={cn(
                  "flex size-4 shrink-0 items-center justify-center rounded-[4px] border",
                  isChecked
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-input bg-background"
                )}
              >
                {isChecked ? <CheckIcon className="size-3" aria-hidden /> : null}
              </span>
              {renderLead ? (
                <span className="w-16 shrink-0 truncate text-xs text-muted-foreground tabular-nums">
                  {renderLead(item)}
                </span>
              ) : null}
              <span className="min-w-0 flex-1">
                <span className="block truncate">{item.title}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  {line}
                </span>
              </span>
              <StateChip model={model} state={item.status.state} />
            </div>
          )
        })}
      </div>
    )
  }

  const statuses = targets.map((item) => item.status)
  const sharedHold =
    statuses.length > 0 &&
    statuses.every(
      (record) => record.hold && record.hold.kind === statuses[0].hold?.kind
    )
      ? statuses[0].hold
      : undefined

  const targetLabel = !ready ? null : checkedCount > 0 ? (
    <>
      <span className="font-medium">{checkedCount} selected</span>
      <Button
        variant="ghost"
        size="xs"
        onClick={() => {
          setChecked(new Set())
          focusList()
        }}
      >
        <XIcon aria-hidden />
        Clear
      </Button>
    </>
  ) : targets.length === 1 ? (
    <span className="truncate font-medium">{targets[0].title}</span>
  ) : (
    <span className="text-muted-foreground">
      Select an item to change its status
    </span>
  )

  return (
    <div
      ref={rootRef}
      className="@container flex h-full min-h-0 flex-col bg-background text-sm"
    >
      <div className="flex min-h-11 shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-b px-3 py-1.5">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {targetLabel}
        </div>
        <div className="flex items-center gap-2">
          {model.groups.map((group) => {
            const kinds = model.kinds.filter(
              (kind) => kind.group === group.id
            )
            const hasMenu = kinds.some((kind) => kind.inMenu !== false)
            const undo =
              statuses.length > 0 &&
              primaryEvent(statuses, group, model).type === "clear"
            const current =
              sharedHold &&
              kinds.some((kind) => kind.id === sharedHold.kind)
                ? { kind: sharedHold.kind, value: sharedHold.value }
                : undefined
            return (
              <SplitButton
                key={group.id}
                label={undo ? group.undoLabel : group.label}
                disabled={!ready || targets.length === 0}
                menuLabel={`${group.label} options`}
                onPrimary={() => press(group)}
                open={openGroup === group.id}
                onOpenChange={(open) => setOpenGroup(open ? group.id : null)}
              >
                {hasMenu ? (
                  <ConditionMenu
                    heading={group.menuLabel}
                    kinds={kinds}
                    current={current}
                    onChoose={choose}
                  />
                ) : undefined}
              </SplitButton>
            )
          })}
        </div>
      </div>
      <div className="min-h-0 flex-1">{listArea}</div>
      <div role="status" aria-live="polite" className="sr-only">
        {announcement}
      </div>
    </div>
  )
}
