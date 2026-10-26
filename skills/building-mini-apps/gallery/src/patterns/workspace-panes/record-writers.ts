import type { WorkspaceItem } from "./types"

/**
 * Serialises edits to one record: saves run one at a time in call order, and
 * each edit is composed from the latest record at the moment it runs, so every
 * write carries all earlier edits, whichever pane made them.
 */
export type RecordWriter<T extends WorkspaceItem> = {
  latest: () => T | undefined
  write: (next: T) => Promise<void>
  /** Builds the next record from the latest one when the edit's turn comes; a throw rejects without saving. */
  edit: (build: (base: T) => T) => Promise<void>
  update: (patch: Partial<T>) => Promise<void>
}

export type RecordWriters<T extends WorkspaceItem> = {
  get: (id: string) => RecordWriter<T>
  saveWith: (onChange: (next: T) => Promise<void>) => void
  receive: (items: T[]) => void
}

/**
 * One writer per record id, shared by every pane showing that record. The
 * store publishes a record only after its write resolves, so the published
 * item lags behind edits already made; a write built from it alone, or from a
 * pane's own copy, would drop edits made elsewhere. Saves are queued per record
 * because onChange calls that overlap can complete out of order and let an older
 * record overwrite a newer one.
 */
export function createRecordWriters<T extends WorkspaceItem>(): RecordWriters<T> {
  let save: ((next: T) => Promise<void>) | undefined
  const writers = new Map<string, ReturnType<typeof createWriter>>()

  function createWriter() {
    let published: T | undefined
    let buffer: T | undefined
    let queued = 0
    let tail: Promise<void> = Promise.resolve()

    const latest = () => buffer ?? published

    function enqueue(build: (base: T | undefined) => T | undefined): Promise<void> {
      if (!save) return Promise.resolve()
      queued += 1
      const run = async () => {
        try {
          const next = build(latest())
          if (!next || !save) return
          buffer = next
          try {
            await save(next)
          } catch (cause) {
            buffer = undefined
            throw cause
          }
        } finally {
          queued -= 1
        }
      }
      const result = tail.then(run)
      tail = result.catch(() => undefined)
      return result
    }

    return {
      latest,
      edit: (build: (base: T) => T) =>
        enqueue((base) => (base ? build(base) : undefined)),
      write: (next: T) => enqueue(() => next),
      update: (patch: Partial<T>) =>
        enqueue((base) => (base ? { ...base, ...patch } : undefined)),
      publish(item: T | undefined) {
        if (item === published) return
        published = item
        if (queued === 0) buffer = undefined
      },
      idle: () => queued === 0,
    }
  }

  function writerOf(id: string) {
    let writer = writers.get(id)
    if (!writer) {
      writer = createWriter()
      writers.set(id, writer)
    }
    return writer
  }

  return {
    get: writerOf,
    saveWith(onChange) {
      save = onChange
    },
    receive(items) {
      const present = new Set<string>()
      for (const item of items) {
        present.add(item.id)
        writerOf(item.id).publish(item)
      }
      for (const [id, writer] of writers) {
        if (present.has(id)) continue
        writer.publish(undefined)
        if (writer.idle()) writers.delete(id)
      }
    },
  }
}
