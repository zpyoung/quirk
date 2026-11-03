import { useCallback, useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { useCollection } from "@/lib/mini/store"

import type { ViewConfig } from "./types"
import { isDirty, mergeDraft, type ViewDraft } from "./view-draft"

export const DEFAULT_VIEWS: ViewConfig[] = [
  { id: "all", name: "All", layout: "table", filters: [] },
]

function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStored(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // storage can be blocked; the view then resets to the first tab on reload
  }
}

function reportFailure(cause: unknown) {
  toast.error("Couldn't save the view change", {
    description: cause instanceof Error ? cause.message : String(cause),
  })
}

export interface ViewsApi {
  views: ViewConfig[]
  loading: boolean
  /** Resolves true once the write is stored, false after a rejected write has been reported. */
  update(id: string, patch: Partial<Omit<ViewConfig, "id">>): Promise<boolean>
  add(view: ViewConfig): Promise<boolean>
  remove(id: string): Promise<boolean>
}

/**
 * Saved views in the store. Edits show at once and are dropped back to the
 * stored copy if the write rejects, so typing in a filter never waits on IndexedDB.
 */
export function useViews(
  storageKey: string,
  defaultViews: ViewConfig[] | undefined
): ViewsApi {
  const seed =
    defaultViews && defaultViews.length > 0 ? defaultViews : DEFAULT_VIEWS
  const collection = useCollection<ViewConfig>(`${storageKey}-views`, seed)
  const [pending, setPending] = useState<Record<string, Partial<ViewConfig>>>(
    {}
  )
  const inflight = useRef(new Map<string, number>())

  const { update: storeUpdate, add: storeAdd, remove: storeRemove } = collection
  const base =
    collection.status === "ready" && collection.items.length > 0
      ? collection.items
      : seed
  const views = useMemo(
    () => base.map((v) => (pending[v.id] ? { ...v, ...pending[v.id] } : v)),
    [base, pending]
  )

  function update(
    id: string,
    patch: Partial<Omit<ViewConfig, "id">>
  ): Promise<boolean> {
    setPending((p) => ({ ...p, [id]: { ...p[id], ...patch } }))
    inflight.current.set(id, (inflight.current.get(id) ?? 0) + 1)
    return storeUpdate(id, patch)
      .then(() => true)
      .catch((cause) => {
        reportFailure(cause)
        return false
      })
      .finally(() => {
        const left = (inflight.current.get(id) ?? 1) - 1
        if (left > 0) return inflight.current.set(id, left)
        inflight.current.delete(id)
        setPending((p) => {
          const next = { ...p }
          delete next[id]
          return next
        })
      })
  }

  async function run(write: Promise<void>): Promise<boolean> {
    try {
      await write
      return true
    } catch (cause) {
      reportFailure(cause)
      return false
    }
  }

  return {
    views,
    loading: collection.status === "loading",
    update,
    add: (view) => run(storeAdd(view)),
    remove: (id) => run(storeRemove(id)),
  }
}

/** Active view id: controlled when `controlled` is given, else remembered in localStorage. */
export function useActiveViewId(
  storageKey: string,
  views: ViewConfig[],
  controlled: string | undefined,
  onChange: ((id: string) => void) | undefined
) {
  const key = `${storageKey}-active`
  const [stored, setStored] = useState(() => readStored(key))
  const id = controlled ?? stored
  const active = views.find((v) => v.id === id) ?? views[0]

  function setActive(next: string) {
    if (controlled === undefined) {
      setStored(next)
      writeStored(key, next)
    }
    onChange?.(next)
  }

  return [active, setActive] as const
}

export interface DraftsApi {
  drafts: Record<string, ViewDraft>
  /** Ids of views whose draft differs from the stored copy. */
  dirtyIds: ReadonlySet<string>
  patch(id: string, patch: ViewDraft): void
  /** Drops a draft; with `only`, drops it only if it is still that exact draft. */
  clear(id: string, only?: ViewDraft): void
}

/**
 * Unsaved query, sort and filter edits per view id, kept in memory. A draft of
 * a view that no longer exists is ignored, so deleting a view needs no cleanup.
 */
export function useDrafts(views: ViewConfig[]): DraftsApi {
  const [drafts, setDrafts] = useState<Record<string, ViewDraft>>({})

  const patch = useCallback((id: string, next: ViewDraft) => {
    setDrafts((d) => ({ ...d, [id]: mergeDraft(d[id], next) }))
  }, [])

  const clear = useCallback((id: string, only?: ViewDraft) => {
    setDrafts((d) => {
      if (!(id in d) || (only && d[id] !== only)) return d
      const next = { ...d }
      delete next[id]
      return next
    })
  }, [])

  const dirtyIds = useMemo(
    () =>
      new Set(views.filter((v) => isDirty(v, drafts[v.id])).map((v) => v.id)),
    [views, drafts]
  )

  return { drafts, dirtyIds, patch, clear }
}
