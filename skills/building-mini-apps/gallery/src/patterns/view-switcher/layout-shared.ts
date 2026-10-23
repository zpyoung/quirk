import type { Field, Rec } from "./fields"
import type { ViewConfig } from "./types"

export type CreateDefaults = Record<string, string | undefined>

export interface LayoutProps {
  items: Rec[]
  /** Every field including the title. */
  fields: Field[]
  view: ViewConfig
  noun: string
  activeId: string | null
  /** The one record that is a Tab stop; the rest are reached with the arrow keys. */
  tabStopId: string | null
  openId: string | null
  onOpen(id: string): void
  onActivate(id: string): void
  onCreate?: (defaults: CreateDefaults) => void
}

/** Attributes that make an element a record the keyboard layer can find, focus and open. */
export function recordProps(
  layout: LayoutProps,
  id: string,
  tabStopId = layout.tabStopId
) {
  return {
    "data-record-id": id,
    "data-active": layout.activeId === id ? "" : undefined,
    "aria-current": layout.openId === id ? ("true" as const) : undefined,
    tabIndex: tabStopId === id ? 0 : -1,
    onClick: () => layout.onOpen(id),
    onFocus: () => layout.onActivate(id),
  }
}

export const recordClasses =
  "outline-none focus-visible:ring-2 focus-visible:ring-ring/60 data-active:bg-accent aria-[current=true]:bg-(--mini-accent-soft)"
