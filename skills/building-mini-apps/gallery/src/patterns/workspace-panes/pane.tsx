import { useEffect, useState, type ReactNode } from "react"
import { ChevronLeftIcon, ChevronRightIcon, EllipsisVerticalIcon } from "lucide-react"

import { EmptyState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

import { RawEditor } from "./raw-editor"
import type { PaneMode, WorkspaceItem } from "./types"

type PaneHeaderProps = {
  title: string
  mode: PaneMode
  hasItem: boolean
  canBack: boolean
  canForward: boolean
  canReopen: boolean
  onBack: () => void
  onForward: () => void
  onMode: (mode: PaneMode) => void
  onSplit?: () => void
  onClose: () => void
  onReopen: () => void
}

function PaneHeader({
  title,
  mode,
  hasItem,
  canBack,
  canForward,
  canReopen,
  onBack,
  onForward,
  onMode,
  onSplit,
  onClose,
  onReopen,
}: PaneHeaderProps) {
  return (
    <div className="grid h-9 shrink-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 border-b px-2">
      <div className="flex items-center">
        <Button variant="ghost" size="icon-sm" aria-label="Back" disabled={!canBack} onClick={onBack}>
          <ChevronLeftIcon />
        </Button>
        <Button variant="ghost" size="icon-sm" aria-label="Forward" disabled={!canForward} onClick={onForward}>
          <ChevronRightIcon />
        </Button>
      </div>
      <h2 className="truncate text-center text-xs font-medium" title={title}>
        {title}
      </h2>
      <div className="flex items-center gap-1">
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          spacing={0}
          aria-label="View"
          value={mode}
          disabled={!hasItem}
          onValueChange={(value) => {
            if (value === "structured" || value === "raw") onMode(value)
          }}
        >
          <ToggleGroupItem value="structured" aria-label="Structured view" className="h-6 px-2 text-xs">
            Structured
          </ToggleGroupItem>
          <ToggleGroupItem value="raw" aria-label="Raw view" className="h-6 px-2 text-xs">
            Raw
          </ToggleGroupItem>
        </ToggleGroup>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label="Pane menu">
              <EllipsisVerticalIcon />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-44">
            {onSplit ? <DropdownMenuItem onSelect={onSplit}>Split right</DropdownMenuItem> : null}
            <DropdownMenuItem onSelect={onClose}>Close tab</DropdownMenuItem>
            <DropdownMenuItem disabled={!canReopen} onSelect={onReopen}>
              Reopen closed tab
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}

type PaneProps<T extends WorkspaceItem> = Omit<PaneHeaderProps, "title" | "hasItem"> & {
  item: T | undefined
  deleted: boolean
  empty: ReactNode
  maxContentWidth: number
  renderStructured: (item: T, api: { update: (patch: Partial<T>) => Promise<void> }) => ReactNode
  toRaw: (item: T) => string
  parseRaw: (raw: string, item: T) => T
  onChange: (next: T) => Promise<void>
}

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

/**
 * Composes every write from the newest local record. The store publishes a
 * record only after its write resolves, so the `item` prop lags behind edits
 * already made; building a write from it alone would drop those edits.
 */
function createWriter<T extends WorkspaceItem>() {
  let prop: T | undefined
  let save: ((next: T) => Promise<void>) | undefined
  let unsettled: T | undefined
  let inflight = 0

  const latest = () => unsettled ?? prop

  function write(next: T): Promise<void> {
    if (!save) return Promise.resolve()
    unsettled = next
    inflight += 1
    return save(next).then(
      () => {
        inflight -= 1
      },
      (cause: unknown) => {
        inflight -= 1
        if (inflight === 0) unsettled = undefined
        throw cause
      }
    )
  }

  return {
    latest,
    write,
    update(patch: Partial<T>): Promise<void> {
      const base = latest()
      return base ? write({ ...base, ...patch }) : Promise.resolve()
    },
    saveWith(onChange: (next: T) => Promise<void>) {
      save = onChange
    },
    receive(item: T | undefined) {
      prop = item
      if (inflight === 0) unsettled = undefined
    },
  }
}

/** Header plus body for one tab: structured form, raw file, the empty pane, or the deleted notice. */
export function Pane<T extends WorkspaceItem>({
  item,
  deleted,
  empty,
  maxContentWidth,
  renderStructured,
  toRaw,
  parseRaw,
  onChange,
  ...header
}: PaneProps<T>) {
  const [rawError, setRawError] = useState<string>()
  const [writer] = useState(createWriter<T>)

  useEffect(() => {
    writer.saveWith(onChange)
  }, [writer, onChange])

  useEffect(() => {
    writer.receive(item)
  }, [writer, item])

  function commitRaw(raw: string) {
    const base = writer.latest()
    if (!base) return
    try {
      const next = parseRaw(raw, base)
      setRawError(undefined)
      writer.write(next).catch((cause: unknown) => setRawError(messageOf(cause)))
    } catch (cause) {
      setRawError(messageOf(cause))
    }
  }

  let body: ReactNode
  if (deleted) {
    body = (
      <EmptyState
        title="This item was deleted"
        action={
          <Button size="sm" variant="outline" onClick={header.onClose}>
            Close tab
          </Button>
        }
      />
    )
  } else if (!item) {
    body = empty
  } else if (header.mode === "raw") {
    body = <RawEditor value={toRaw(item)} error={rawError} onCommit={commitRaw} />
  } else {
    body = (
      <div className="mx-auto w-full p-4" style={{ maxWidth: maxContentWidth }}>
        {renderStructured(item, { update: (patch) => writer.update(patch) })}
      </div>
    )
  }

  return (
    <>
      <PaneHeader
        {...header}
        title={deleted ? "Deleted" : (item?.title ?? "New tab")}
        hasItem={!!item}
      />
      <div
        data-pane-body
        tabIndex={-1}
        className="min-h-0 flex-1 overflow-auto outline-none"
      >
        {body}
      </div>
    </>
  )
}
