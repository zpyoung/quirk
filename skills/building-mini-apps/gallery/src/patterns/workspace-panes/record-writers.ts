import type { WorkspaceItem } from "./types"

/** Serialises edits to one record so every write carries all earlier edits, whichever pane made them. */
export type RecordWriter<T extends WorkspaceItem> = {
  latest: () => T | undefined
  write: (next: T) => Promise<void>
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
 * pane's own copy, would drop edits made elsewhere.
 */
export function createRecordWriters<T extends WorkspaceItem>(): RecordWriters<T> {
  let save: ((next: T) => Promise<void>) | undefined
  const writers = new Map<string, ReturnType<typeof createWriter>>()

  function createWriter() {
    let published: T | undefined
    let unsettled: T | undefined
    let inflight = 0

    const latest = () => unsettled ?? published

    function write(next: T): Promise<void> {
      if (!save) return Promise.resolve()
      unsettled = next
      inflight += 1
      return save(next).then(
        () => {
          inflight -= 1
        },
        (cause: unknown) => {
          inflight -= 1
          if (inflight === 0) unsettled = undefined
          throw cause
        }
      )
    }

    return {
      latest,
      write,
      update(patch: Partial<T>): Promise<void> {
        const base = latest()
        return base ? write({ ...base, ...patch }) : Promise.resolve()
      },
      publish(item: T | undefined) {
        if (item === published) return
        published = item
        if (inflight === 0) unsettled = undefined
      },
      idle: () => inflight === 0,
      published: () => published,
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
