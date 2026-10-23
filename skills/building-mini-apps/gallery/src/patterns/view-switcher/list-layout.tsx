import { cn } from "@/lib/utils"

import { displayValue, valueOf } from "./fields"
import { recordClasses, recordProps, type LayoutProps } from "./layout-shared"

export function ListLayout(props: LayoutProps) {
  const { items, fields } = props
  const others = fields.filter((f) => f.key !== "title")

  return (
    <div className="h-full overflow-auto">
      <div className="sticky top-0 z-10 flex h-8 items-center justify-between border-b bg-background px-3 text-xs font-medium text-muted-foreground">
        <span>Title</span>
        <span>Details</span>
      </div>
      <ul>
        {items.map((item) => {
          const details = others
            .map((f) => displayValue(f, valueOf(item, f.key)))
            .filter((text) => text !== "")
            .join(" · ")
          return (
            <li key={item.id}>
              <button
                type="button"
                {...recordProps(props, item.id)}
                className={cn(
                  "flex h-[26px] w-full cursor-pointer items-center gap-4 px-3 text-left text-xs hover:bg-muted/50",
                  recordClasses
                )}
              >
                <span
                  className="min-w-0 truncate font-medium"
                  title={item.title}
                >
                  {item.title}
                </span>
                <span className="ml-auto min-w-0 shrink-[20] truncate text-muted-foreground">
                  {details}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
