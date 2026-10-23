import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react"
import { useHotkeys } from "react-hotkeys-hook"
import { ArrowUpRightIcon, CheckIcon, PlusIcon } from "lucide-react"

import { EmptyState } from "@/components/mini/states"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

import type { CollectionDef, DocRecord, FieldDef, PropValue } from "./types"

function Cell({ field, value }: { field: FieldDef; value: PropValue }): ReactNode {
  if (value === null || value === "" || value === false) return null
  if (field.type === "checkbox") {
    return (
      <>
        <CheckIcon className="size-3.5" aria-hidden />
        <span className="sr-only">Yes</span>
      </>
    )
  }
  if (field.type === "select") return <Badge variant="secondary">{String(value)}</Badge>
  return String(value)
}

function matches(record: DocRecord, query: string) {
  const needle = query.trim().toLowerCase()
  if (!needle) return true
  return (
    record.title.toLowerCase().includes(needle) ||
    Object.values(record.props).some((value) => value !== null && String(value).toLowerCase().includes(needle))
  )
}

/**
 * One collection as a numbered grid with a search box and an Add button. The grid is a single tab stop:
 * while it has focus, arrows or j/k move the selection, Enter opens the selected row and n adds a record.
 */
export function CollectionBlock<T extends DocRecord>({
  def,
  records,
  selectedId,
  onSelect,
  onOpen,
  onAdd,
}: {
  def: CollectionDef
  records: T[]
  selectedId?: string
  onSelect: (id: string) => void
  onOpen: (id: string) => void
  onAdd: () => void
}) {
  const uid = useId()
  const [query, setQuery] = useState("")
  const rows = useMemo(() => records.filter((record) => matches(record, query)), [records, query])
  const selectedIndex = rows.findIndex((row) => row.id === selectedId)
  const rowDomId = (id: string) => `${uid}-${id}`

  const move = (delta: 1 | -1) => {
    if (rows.length === 0) return
    const next = selectedIndex < 0 ? (delta > 0 ? 0 : rows.length - 1) : Math.min(rows.length - 1, Math.max(0, selectedIndex + delta))
    onSelect(rows[next].id)
  }

  const gridRef = useHotkeys<HTMLTableElement>(
    ["down", "up", "j", "k", "enter", "n"],
    (event) => {
      switch (event.key) {
        case "ArrowDown":
        case "j":
          return move(1)
        case "ArrowUp":
        case "k":
          return move(-1)
        case "Enter":
          if (selectedIndex >= 0) onOpen(rows[selectedIndex].id)
          return
        case "n":
          return onAdd()
      }
    },
    { preventDefault: true, ignoreEventWhen: (event) => event.target !== event.currentTarget }
  )

  const previous = useRef(selectedId)
  useEffect(() => {
    if (selectedId && previous.current !== selectedId) {
      document.getElementById(`${uid}-${selectedId}`)?.scrollIntoView({ block: "nearest" })
    }
    previous.current = selectedId
  }, [selectedId, uid])

  return (
    <section aria-label={def.name} className="my-4">
      <div className="flex h-[30px] items-center gap-2">
        <h2 className="min-w-0 flex-1 truncate text-sm font-semibold">{def.name}</h2>
        <Input
          type="search"
          aria-label={`Search ${def.name}`}
          placeholder="Search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="h-7 w-36 text-xs md:text-xs"
        />
        <Button variant="outline" size="sm" onClick={onAdd} aria-label={`Add record to ${def.name}`}>
          <PlusIcon aria-hidden /> Add
        </Button>
      </div>

      <div className="mt-1 max-h-[450px] overflow-auto rounded-md border has-[table:focus-visible]:ring-3 has-[table:focus-visible]:ring-ring/50">
        <table
          ref={gridRef}
          role="grid"
          tabIndex={0}
          aria-label={def.name}
          aria-activedescendant={selectedIndex >= 0 ? rowDomId(selectedId!) : undefined}
          data-collection-id={def.id}
          className="w-max min-w-full border-collapse text-sm outline-none"
        >
          <thead className="sticky top-0 z-10 bg-background text-xs text-muted-foreground">
            <tr role="row" className="h-[30px] border-b">
              <th role="columnheader" scope="col" className="w-10 px-2 text-right font-normal">
                #
              </th>
              <th role="columnheader" scope="col" className="min-w-40 px-2 text-left font-normal">
                Title
              </th>
              {def.fields.map((field) => (
                <th
                  key={field.key}
                  role="columnheader"
                  scope="col"
                  className={cn("min-w-28 px-2 font-normal", field.type === "number" ? "text-right" : "text-left")}
                >
                  {field.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr
                key={row.id}
                id={rowDomId(row.id)}
                role="row"
                aria-selected={row.id === selectedId}
                onClick={() => onSelect(row.id)}
                className="h-[30px] border-b last:border-b-0 hover:bg-muted/50 aria-selected:bg-accent"
              >
                <td role="gridcell" className="px-2 text-right text-xs text-muted-foreground tabular-nums">
                  {index + 1}
                </td>
                <td role="gridcell" className="max-w-56 px-2">
                  <div className="flex items-center gap-1">
                    <span className="min-w-0 flex-1 truncate" title={row.title}>
                      {row.title}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      tabIndex={-1}
                      aria-label={`Open ${row.title}`}
                      onClick={(event) => {
                        event.stopPropagation()
                        onSelect(row.id)
                        onOpen(row.id)
                      }}
                    >
                      <ArrowUpRightIcon aria-hidden />
                    </Button>
                  </div>
                </td>
                {def.fields.map((field) => (
                  <td
                    key={field.key}
                    role="gridcell"
                    className={cn("px-2 whitespace-nowrap", field.type === "number" && "text-right tabular-nums")}
                  >
                    <Cell field={field} value={row.props[field.key] ?? null} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {records.length === 0 ? (
        <EmptyState
          title="No records"
          action={
            <Button size="sm" onClick={onAdd}>
              <PlusIcon aria-hidden /> Add record
            </Button>
          }
        />
      ) : rows.length === 0 ? (
        <EmptyState title="No matches" description={`Nothing in ${def.name} matches "${query.trim()}".`} />
      ) : null}
    </section>
  )
}
