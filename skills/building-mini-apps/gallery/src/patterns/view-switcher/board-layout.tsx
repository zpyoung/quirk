import { PlusIcon } from "lucide-react"

import { EmptyState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

import { displayValue, pickField, valueOf } from "./fields"
import { buildColumns } from "./grouping"
import { recordClasses, recordProps, type LayoutProps } from "./layout-shared"

export function BoardLayout(props: LayoutProps) {
  const { items, fields, view, noun, onCreate } = props
  const groupField = pickField(fields, view.groupBy, "select")
  if (!groupField) {
    return (
      <EmptyState
        title="Board needs a select field"
        description="Add a field with a fixed list of options to group cards by."
      />
    )
  }
  const columns = buildColumns(items, groupField)
  const others = fields.filter(
    (f) => f.key !== "title" && f.key !== groupField.key
  )

  return (
    <div className="flex h-full gap-3 overflow-x-auto p-3">
      {columns.map((column) => (
        <section
          key={column.value || "__none__"}
          aria-label={`${column.label}, ${column.items.length}`}
          className="flex w-[260px] shrink-0 flex-col rounded-lg bg-muted/40"
        >
          <header data-mini="group-header" className="flex h-8 shrink-0 items-center gap-2 px-2 text-xs">
            <span className="min-w-0 truncate font-medium">{column.label}</span>
            <span className="text-muted-foreground tabular-nums">
              {column.items.length}
            </span>
            {onCreate ? (
              <Button
                variant="ghost"
                size="icon-xs"
                className="ml-auto"
                aria-label={`New ${noun} in ${column.label}`}
                onClick={() =>
                  onCreate({ [groupField.key]: column.value || undefined })
                }
              >
                <PlusIcon />
              </Button>
            ) : null}
          </header>
          <div className="flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto px-1.5 pb-1.5">
            {column.items.map((item) => {
              const details = others
                .map((f) => displayValue(f, valueOf(item, f.key)))
                .filter((text) => text !== "")
                .join(" · ")
              return (
                <button
                  key={item.id}
                  type="button"
                  {...recordProps(props, item.id)}
                  className={cn(
                    "flex w-full cursor-pointer flex-col gap-1 rounded-md border bg-card p-2 text-left text-xs shadow-xs hover:bg-accent/50",
                    recordClasses
                  )}
                >
                  <span className="line-clamp-2 font-medium" title={item.title}>
                    {item.title}
                  </span>
                  {details ? (
                    <span className="truncate text-muted-foreground">
                      {details}
                    </span>
                  ) : null}
                </button>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}
