import { useMemo, useSyncExternalStore } from "react"
import { createStore, entries, get, set, setMany, type UseStore } from "idb-keyval"

type Status = "loading" | "ready" | "error"

interface Snapshot<T> {
  items: T[]
  status: Status
  error?: Error
}

export interface Collection<T extends { id: string }> extends Snapshot<T> {
  add(item: T): Promise<void>
  update(id: string, patch: Partial<T>): Promise<void>
  remove(id: string): Promise<void>
  replaceAll(items: T[]): Promise<void>
}

interface Entry {
  snapshot: Snapshot<{ id: string }>
  listeners: Set<() => void>
  loaded: Promise<void>
  queue: Promise<unknown>
}

const entriesByName = new Map<string, Entry>()
let idbStore: UseStore | undefined

function db(): UseStore {
  idbStore ??= createStore("mini-app", "collections")
  return idbStore
}

function toError(cause: unknown): Error {
  return cause instanceof Error ? cause : new Error(String(cause))
}

function publish(entry: Entry, snapshot: Snapshot<{ id: string }>) {
  entry.snapshot = snapshot
  entry.listeners.forEach((listener) => listener())
}

function getEntry(name: string, seed?: { id: string }[]): Entry {
  const existing = entriesByName.get(name)
  if (existing) return existing

  const entry: Entry = {
    snapshot: { items: [], status: "loading" },
    listeners: new Set(),
    loaded: Promise.resolve(),
    queue: Promise.resolve(),
  }
  entriesByName.set(name, entry)

  entry.loaded = (async () => {
    try {
      const stored = await get<{ id: string }[]>(name, db())
      if (stored !== undefined) {
        publish(entry, { items: stored, status: "ready" })
        return
      }
      const initial = seed ?? []
      if (seed) await set(name, initial, db())
      publish(entry, { items: initial, status: "ready" })
    } catch (cause) {
      publish(entry, { items: [], status: "error", error: toError(cause) })
    }
  })()

  return entry
}

/** Serializes writes per collection so concurrent calls never drop each other's changes. */
function mutate<T extends { id: string }>(
  name: string,
  entry: Entry,
  change: (items: T[]) => T[] | null
): Promise<void> {
  const run = entry.queue.then(async () => {
    await entry.loaded
    const { items, status, error } = entry.snapshot
    if (status === "error") throw error
    const next = change(items as T[])
    if (next === null) return
    await set(name, next, db())
    publish(entry, { items: next, status: "ready" })
  })
  entry.queue = run.catch(() => undefined)
  return run
}

/**
 * Persistent list of records in IndexedDB, shared by every component that uses
 * the same `name`. `seed` is written only when nothing is stored under `name`.
 * Writes reject with the storage error and leave the last good items in place.
 */
export function useCollection<T extends { id: string }>(
  name: string,
  seed?: T[]
): Collection<T> {
  const entry = getEntry(name, seed)
  const snapshot = useSyncExternalStore(
    (listener) => {
      entry.listeners.add(listener)
      return () => entry.listeners.delete(listener)
    },
    () => entry.snapshot
  ) as Snapshot<T>

  const actions = useMemo(
    () => ({
      add: (item: T) => mutate<T>(name, entry, (items) => [...items, item]),
      update: (id: string, patch: Partial<T>) =>
        mutate<T>(name, entry, (items) =>
          items.some((item) => item.id === id)
            ? items.map((item) => (item.id === id ? { ...item, ...patch } : item))
            : null
        ),
      remove: (id: string) =>
        mutate<T>(name, entry, (items) =>
          items.some((item) => item.id === id)
            ? items.filter((item) => item.id !== id)
            : null
        ),
      replaceAll: (items: T[]) => mutate<T>(name, entry, () => items),
    }),
    [name, entry]
  )

  return { ...snapshot, ...actions }
}

/** Serializes every stored collection as `{"version":1,"collections":{...}}`. */
export async function exportAll(): Promise<string> {
  await Promise.all([...entriesByName.values()].map((entry) => entry.queue))
  await Promise.all([...entriesByName.values()].map((entry) => entry.loaded))
  const collections: Record<string, unknown> = {}
  for (const [key, value] of await entries(db())) collections[String(key)] = value
  return JSON.stringify({ version: 1, collections })
}

/**
 * Replaces the named collections with the imported ones and leaves others
 * untouched. Rejects without writing anything when the JSON is invalid, the
 * version is not 1, or any collection is not an array.
 */
export async function importAll(json: string): Promise<void> {
  const parsed: unknown = JSON.parse(json)
  if (typeof parsed !== "object" || parsed === null) {
    throw new Error("Import is not a JSON object")
  }
  const { version, collections } = parsed as Record<string, unknown>
  if (version !== 1) throw new Error(`Unsupported export version: ${String(version)}`)
  if (typeof collections !== "object" || collections === null || Array.isArray(collections)) {
    throw new Error("Import has no collections object")
  }
  const incoming = Object.entries(collections)
  for (const [name, items] of incoming) {
    if (!Array.isArray(items)) throw new Error(`Collection "${name}" is not an array`)
  }

  await Promise.all([...entriesByName.values()].map((entry) => entry.loaded))
  await setMany(incoming, db())
  for (const [name, items] of incoming) {
    const entry = entriesByName.get(name)
    if (entry) publish(entry, { items: items as { id: string }[], status: "ready" })
  }
}
