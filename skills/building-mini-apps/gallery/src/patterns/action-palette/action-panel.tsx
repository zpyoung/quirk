import { Fragment, useEffect, useRef, useState } from "react"
import { useHotkeys } from "react-hotkeys-hook"

import {
  Command,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

import { ShortcutKeys } from "./shortcut-keys"
import type { ActionPanelProps, PaletteAction, PaletteItem } from "./types"

type PanelRow<T extends PaletteItem> = {
  action: PaletteAction<T>
  hint?: string
  separated: boolean
}

function arrangeRows<T extends PaletteItem>(
  level: PaletteAction<T>[],
  filter: string,
  isRoot: boolean
): PanelRow<T>[] {
  const query = filter.trim().toLowerCase()
  const hintFor = (action: PaletteAction<T>) => {
    if (action.shortcut) return action.shortcut
    if (!isRoot) return undefined
    const index = level.indexOf(action)
    return index === 0 ? "enter" : index === 1 ? "mod+enter" : undefined
  }

  const ordered = [
    ...level.filter((action) => !action.destructive),
    ...level.filter((action) => action.destructive),
  ]

  if (query) {
    return ordered
      .filter((action) => action.title.toLowerCase().includes(query))
      .map((action) => ({ action, hint: hintFor(action), separated: false }))
  }

  return ordered.map((action, index) => {
    const previous = ordered[index - 1]
    const separated =
      previous !== undefined &&
      (Boolean(previous.destructive) !== Boolean(action.destructive) ||
        (!action.destructive && previous.section !== action.section))
    return { action, hint: hintFor(action), separated }
  })
}

const displayName = (title: string) => title.replace(/…$/, "")

/**
 * Card of filterable actions for one item. Leaf actions go to `onRun`;
 * actions with `children` replace the card's contents until Esc. Esc at the
 * top level and clicks outside call `onClose`. `initialPath` opens the card
 * already drilled into that chain of sub-menus.
 */
export function ActionPanel<T extends PaletteItem>({
  item,
  actions,
  initialPath,
  onClose,
  onRun,
}: ActionPanelProps<T>) {
  const [path, setPath] = useState<PaletteAction<T>[]>(initialPath ?? [])
  const [filter, setFilter] = useState("")
  const [highlight, setHighlight] = useState("")
  const panelRef = useRef<HTMLDivElement>(null)

  const parent = path.at(-1)
  const level = parent?.children ?? actions
  const rows = arrangeRows(level, filter, path.length === 0)
  const current = rows.some((row) => row.action.id === highlight)
    ? highlight
    : (rows[0]?.action.id ?? "")
  const heading = parent ? displayName(parent.title) : item.title

  function choose(action: PaletteAction<T>) {
    if (action.children) {
      setPath([...path, action])
      setFilter("")
      setHighlight("")
      return
    }
    onRun(action)
  }

  useHotkeys(
    "escape",
    () => {
      if (path.length > 0) {
        setPath(path.slice(0, -1))
        setFilter("")
        setHighlight("")
      } else {
        onClose()
      }
    },
    { enableOnFormTags: true, preventDefault: true }
  )

  useHotkeys(
    "mod+enter",
    () => {
      const secondary = actions[1]
      if (path.length === 0 && secondary && !secondary.children) onRun(secondary)
    },
    { enableOnFormTags: true, preventDefault: true }
  )

  useEffect(() => {
    function onPointerDown(event: PointerEvent) {
      const target = event.target
      if (!(target instanceof Element)) return
      if (panelRef.current?.contains(target)) return
      if (target.closest("[data-action-palette-toggle]")) return
      onClose()
    }
    document.addEventListener("pointerdown", onPointerDown)
    return () => document.removeEventListener("pointerdown", onPointerDown)
  }, [onClose])

  return (
    <div
      ref={panelRef}
      role="group"
      aria-label={`Actions for ${item.title}`}
      className="absolute right-3 bottom-12 z-20 w-[45%] max-w-sm min-w-64 overflow-hidden rounded-lg border bg-popover text-popover-foreground shadow-lg"
    >
      <Command
        shouldFilter={false}
        vimBindings={false}
        loop={false}
        label={heading}
        value={current}
        onValueChange={setHighlight}
        className="h-auto rounded-lg!"
        onKeyDown={(event) => {
          // cmdk would run the highlighted row on any Enter; ⌘↵ is handled above
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) event.preventDefault()
        }}
      >
        <div
          className="truncate px-2 pt-1.5 pb-1 text-xs font-medium text-muted-foreground"
          title={heading}
        >
          {heading}
        </div>
        <CommandList className="max-h-64">
          {rows.length === 0 ? (
            <div className="px-2 py-3 text-center text-xs text-muted-foreground">
              No actions match
            </div>
          ) : (
            rows.map(({ action, hint, separated }) => (
              <Fragment key={action.id}>
                {separated ? <Separator className="my-1" /> : null}
                <CommandItem
                  value={action.id}
                  onSelect={() => choose(action)}
                  className={cn(
                    action.destructive &&
                      "text-destructive data-selected:text-destructive"
                  )}
                >
                  <span className="min-w-0 flex-1 truncate" title={action.title}>
                    {action.title}
                  </span>
                  <CommandShortcut>
                    {hint ? <ShortcutKeys shortcut={hint} /> : null}
                  </CommandShortcut>
                </CommandItem>
              </Fragment>
            ))
          )}
        </CommandList>
        <div className="border-t">
          <CommandInput
            autoFocus
            value={filter}
            onValueChange={(value) => {
              setFilter(value)
              setHighlight("")
            }}
            placeholder={parent ? "Search…" : "Search actions…"}
            aria-label={parent ? `Filter ${displayName(parent.title)}` : "Filter actions"}
          />
        </div>
      </Command>
    </div>
  )
}
