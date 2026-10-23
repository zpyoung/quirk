import { useCallback, useMemo, useState } from "react"

import type { PendingChange } from "./types"

export type StagedRowState = "clean" | "changed" | "new" | "removed"

export type StagedRow<T> = {
  item: T
  state: StagedRowState
  changedKeys: Set<keyof T>
}

const changeKey = <T extends { id: string }>(change: PendingChange<T>) =>
  `${change.kind}:${change.kind === "add" ? change.item.id : change.id}`

/**
 * Holds edits to `items` in memory without writing them anywhere.
 * `rows` is `items` with the pending changes applied (new rows last) and
 * `changes` lists them in the order edited. Setting a cell back to its stored
 * value clears its pending mark.
 */
export function useStagedEdits<T extends { id: string }>(items: T[]) {
  const [changes, setChanges] = useState<PendingChange<T>[]>([])

  const setCell = useCallback(
    (id: string, key: keyof T, value: T[keyof T]) => {
      setChanges((prev) => {
        const addIndex = prev.findIndex((c) => c.kind === "add" && c.item.id === id)
        if (addIndex >= 0) {
          const target = prev[addIndex]
          if (target.kind !== "add") return prev
          const next = [...prev]
          next[addIndex] = { kind: "add", item: { ...target.item, [key]: value } }
          return next
        }

        const base = items.find((item) => item.id === id)
        if (!base || prev.some((c) => c.kind === "remove" && c.id === id)) return prev

        const updateIndex = prev.findIndex((c) => c.kind === "update" && c.id === id)
        const existing = prev[updateIndex]
        const patch: Partial<T> = existing?.kind === "update" ? { ...existing.patch } : {}
        if (Object.is(base[key], value)) delete patch[key]
        else patch[key] = value

        const empty = Object.keys(patch).length === 0
        if (updateIndex < 0) return empty ? prev : [...prev, { kind: "update", id, patch }]
        const next = [...prev]
        if (empty) next.splice(updateIndex, 1)
        else next[updateIndex] = { kind: "update", id, patch }
        return next
      })
    },
    [items]
  )

  const addRow = useCallback((item: T) => {
    setChanges((prev) => [...prev, { kind: "add", item }])
  }, [])

  const removeRow = useCallback((id: string) => {
    setChanges((prev) => {
      if (prev.some((c) => c.kind === "add" && c.item.id === id)) {
        return prev.filter((c) => !(c.kind === "add" && c.item.id === id))
      }
      if (prev.some((c) => c.kind === "remove" && c.id === id)) return prev
      return [...prev.filter((c) => !(c.kind === "update" && c.id === id)), { kind: "remove", id }]
    })
  }, [])

  const discard = useCallback(() => setChanges([]), [])

  const settle = useCallback((applied: PendingChange<T>[]) => {
    const done = new Set(applied.map(changeKey))
    setChanges((prev) => prev.filter((c) => !done.has(changeKey(c))))
  }, [])

  const rows = useMemo<StagedRow<T>[]>(() => {
    const removed = new Set<string>()
    const patches = new Map<string, Partial<T>>()
    const added: T[] = []
    for (const change of changes) {
      if (change.kind === "remove") removed.add(change.id)
      else if (change.kind === "update") patches.set(change.id, change.patch)
      else added.push(change.item)
    }

    const stored = new Set(items.map((item) => item.id))
    const out = items.map<StagedRow<T>>((item) => {
      const patch = patches.get(item.id)
      if (removed.has(item.id)) return { item, state: "removed", changedKeys: new Set() }
      if (!patch) return { item, state: "clean", changedKeys: new Set() }
      return {
        item: { ...item, ...patch },
        state: "changed",
        changedKeys: new Set(Object.keys(patch) as (keyof T)[]),
      }
    })
    // an add the store already holds is mid-settle; showing it twice would flicker
    for (const item of added) {
      if (!stored.has(item.id)) out.push({ item, state: "new", changedKeys: new Set() })
    }
    return out
  }, [items, changes])

  return { rows, changes, setCell, addRow, removeRow, discard, settle }
}
