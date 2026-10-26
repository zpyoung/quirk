import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

import { displayValue, valueOf, type Field } from "./fields"
import { recordClasses, recordProps, type LayoutProps } from "./layout-shared"

function Cell({ field, raw }: { field: Field; raw: unknown }) {
  const text = displayValue(field, raw)
  if (text === "") return null
  if (field.type === "select") return <Badge variant="secondary">{text}</Badge>
  return (
    <span className={cn(field.type === "number" && "tabular-nums")}>
      {text}
    </span>
  )
}

export function TableLayout(props: LayoutProps) {
  const { items, fields } = props
  const columns = fields.filter((f) => f.key !== "title")

  return (
    <div className="h-full overflow-auto [&_[data-slot=table-container]]:overflow-visible">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="sticky top-0 z-10 h-8 bg-background">
              Title
            </TableHead>
            {columns.map((f) => (
              <TableHead
                key={f.key}
                className="sticky top-0 z-10 h-8 bg-background"
              >
                {f.label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow
              key={item.id}
              {...recordProps(props, item.id)}
              className={cn("group h-8 cursor-pointer", recordClasses)}
            >
              <TableCell data-mini="cell" className="py-0">
                <div className="flex items-center gap-2">
                  <span
                    className="max-w-[20rem] truncate font-medium"
                    title={item.title}
                  >
                    {item.title}
                  </span>
                  <span
                    aria-hidden
                    className="hidden shrink-0 rounded border bg-background px-1 text-[10px] leading-4 font-medium tracking-wide text-muted-foreground group-hover:inline group-data-active:inline"
                  >
                    OPEN
                  </span>
                </div>
              </TableCell>
              {columns.map((f) => (
                <TableCell key={f.key} data-mini="cell" className="py-0">
                  <Cell field={f} raw={valueOf(item, f.key)} />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
