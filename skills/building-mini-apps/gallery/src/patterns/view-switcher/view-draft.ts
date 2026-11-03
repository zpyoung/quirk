import type { FilterRule, SortRule, ViewConfig } from "./types"

/** The parts of a view that are held back until the user saves. */
export interface ViewDraft {
  query?: string
  sort?: SortRule | undefined
  filters?: FilterRule[]
}

function same(a: unknown, b: unknown): boolean {
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null)
}

/** A view with its draft laid over it; keys the draft never touched keep the saved value. */
export function effectiveView(
  saved: ViewConfig,
  draft: ViewDraft | undefined
): ViewConfig {
  if (!draft) return saved
  const merged: ViewConfig = { ...saved }
  if ("query" in draft) merged.query = draft.query ?? ""
  if ("sort" in draft) merged.sort = draft.sort
  if ("filters" in draft && draft.filters) merged.filters = draft.filters
  return merged
}

/** True when any drafted part differs from the saved view, so undoing an edit by hand clears it. */
export function isDirty(saved: ViewConfig, draft: ViewDraft | undefined) {
  if (!draft) return false
  return (
    ("query" in draft && (draft.query ?? "") !== (saved.query ?? "")) ||
    ("sort" in draft && !same(draft.sort, saved.sort)) ||
    ("filters" in draft && !same(draft.filters, saved.filters))
  )
}

/** Adds `patch` to a draft without losing what it already holds. */
export function mergeDraft(
  draft: ViewDraft | undefined,
  patch: ViewDraft
): ViewDraft {
  return { ...draft, ...patch }
}

/** The fields Save writes to the stored view. An empty query is stored as absent. */
export function savePatch(merged: ViewConfig): Partial<Omit<ViewConfig, "id">> {
  return {
    filters: merged.filters,
    sort: merged.sort,
    query: merged.query ? merged.query : undefined,
  }
}
