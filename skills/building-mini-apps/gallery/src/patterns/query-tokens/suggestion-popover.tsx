import { useEffect } from "react"

import { cn } from "@/lib/utils"

import type { Suggestion, SuggestionSection } from "./suggestions"

export const optionDomId = (listId: string, index: number) => `${listId}-option-${index}`

/**
 * Listbox under the box. It never takes focus: the input owns it through `aria-activedescendant`,
 * and a press on it is kept from blurring the input. With no options it shows only the hint.
 */
export function SuggestionPopover({
  listId,
  sections,
  hint,
  activeIndex,
  onActivate,
  onChoose,
}: {
  listId: string
  sections: SuggestionSection[]
  hint?: string
  activeIndex: number
  onActivate: (index: number) => void
  onChoose: (item: Suggestion) => void
}) {
  useEffect(() => {
    if (activeIndex < 0) return
    document.getElementById(optionDomId(listId, activeIndex))?.scrollIntoView({ block: "nearest" })
  }, [activeIndex, listId])

  let index = -1
  return (
    <div
      onMouseDown={(event) => event.preventDefault()}
      className="absolute inset-x-0 top-full z-30 mt-1 max-h-72 overflow-y-auto rounded-lg border bg-popover p-1 text-sm text-popover-foreground shadow-md"
    >
      {sections.length > 0 ? (
        <div role="listbox" id={listId} aria-label="Suggestions">
          {sections.map((section) => (
            <div key={section.id} role="group" aria-labelledby={`${listId}-${section.id}`}>
              <div
                id={`${listId}-${section.id}`}
                className="px-2 pt-2 pb-1 text-[0.7rem] font-medium tracking-wide text-muted-foreground uppercase"
              >
                {section.label}
              </div>
              {section.items.map((item) => {
                const own = ++index
                return (
                  <div
                    key={`${item.kind}:${item.label}`}
                    role="option"
                    id={optionDomId(listId, own)}
                    aria-selected={own === activeIndex}
                    onMouseMove={() => own !== activeIndex && onActivate(own)}
                    onClick={() => onChoose(item)}
                    className={cn(
                      "flex cursor-default items-center justify-between gap-3 rounded-md px-2 py-1.5",
                      "aria-selected:bg-accent aria-selected:text-accent-foreground"
                    )}
                  >
                    <span className="truncate font-[family-name:var(--mini-font-data)]">{item.label}</span>
                    {item.kind === "key" && item.hint ? (
                      <span className="shrink-0 text-xs text-muted-foreground">{item.hint}</span>
                    ) : null}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      ) : null}
      {hint ? (
        <p role="status" className="px-2 py-1.5 text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  )
}
