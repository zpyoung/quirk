import { useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { EmptyState, ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { useCollection } from "@/lib/mini/store"
import { cn } from "@/lib/utils"

import { NoteView } from "./note-view"
import { isGenerated, isUser, newId } from "./segments"
import type { AssistedNoteItem, NoteSegment, NoteViewMode } from "./types"

type Run = { running: boolean; error?: Error }

const toError = (cause: unknown) =>
  cause instanceof Error ? cause : new Error(String(cause))

const cancelledError = () => new Error("Generation cancelled")

export type AssistedNotesProps<T extends AssistedNoteItem> = {
  /** `useCollection` name the notes are stored under. */
  collection: string
  seed?: T[]
  /** Returns generated lines only; the block forces their origin and replaces earlier generated lines. */
  onGenerate?: (note: T, signal: AbortSignal) => Promise<NoteSegment[]>
  /** Factory for the New note action. */
  newNote?: () => T
  className?: string
}

/**
 * A list of notes with a note view beside it: user lines stay primary,
 * generated lines sit beside them with a way back to their source. Stores
 * through `useCollection`; a failed write shows a toast and keeps what was typed.
 */
export function AssistedNotes<T extends AssistedNoteItem>({
  collection,
  seed,
  onGenerate,
  newNote,
  className,
}: AssistedNotesProps<T>) {
  const { items, status, error, add, update } = useCollection<T>(
    collection,
    seed
  )
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [views, setViews] = useState<Record<string, NoteViewMode>>({})
  const [drafts, setDrafts] = useState<Record<string, T>>({})
  const [runs, setRuns] = useState<Record<string, Run>>({})
  const controllers = useRef(new Map<string, AbortController>())

  const notes = useMemo(
    () => items.map((item) => drafts[item.id] ?? item),
    [items, drafts]
  )
  const notesRef = useRef(notes)
  useEffect(() => {
    notesRef.current = notes
  })

  useEffect(() => {
    const active = controllers.current
    return () => active.forEach((controller) => controller.abort())
  }, [])

  // the draft shows what was typed until the write lands, and stays if the write fails
  function commit(id: string, patch: Partial<T>) {
    const base = notesRef.current.find((note) => note.id === id)
    if (!base) return
    const next = { ...base, ...patch }
    notesRef.current = notesRef.current.map((note) =>
      note.id === id ? next : note
    )
    setDrafts((current) => ({ ...current, [id]: next }))
    update(id, patch).then(
      () =>
        setDrafts((current) => {
          if (current[id] !== next) return current
          return Object.fromEntries(
            Object.entries(current).filter(([key]) => key !== id)
          )
        }),
      (cause: unknown) =>
        toast.error("Could not save the note", {
          description: toError(cause).message,
        })
    )
  }

  async function createNote() {
    const note =
      newNote?.() ??
      ({
        id: newId(),
        title: "Untitled note",
        segments: [],
      } as AssistedNoteItem as T)
    try {
      await add(note)
      setViews((current) => ({ ...current, [note.id]: "mine" }))
      setSelectedId(note.id)
    } catch (cause) {
      toast.error("Could not create the note", {
        description: toError(cause).message,
      })
    }
  }

  async function generate(id: string) {
    const note = notesRef.current.find((n) => n.id === id)
    if (!onGenerate || !note || controllers.current.has(id)) return
    const controller = new AbortController()
    controllers.current.set(id, controller)
    setRuns((current) => ({ ...current, [id]: { running: true } }))
    try {
      const generated = await onGenerate(note, controller.signal)
      if (controller.signal.aborted) return
      const latest = notesRef.current.find((n) => n.id === id)
      if (latest) {
        const segments = [
          ...latest.segments.filter(isUser),
          ...generated.map((segment) => ({
            ...segment,
            origin: "generated" as const,
          })),
        ]
        commit(id, { segments } as Partial<T>)
      }
      setRuns((current) => ({ ...current, [id]: { running: false } }))
    } catch (cause) {
      if (controller.signal.aborted) return
      setRuns((current) => ({
        ...current,
        [id]: { running: false, error: toError(cause) },
      }))
    } finally {
      if (controllers.current.get(id) === controller)
        controllers.current.delete(id)
    }
  }

  function cancel(id: string) {
    controllers.current.get(id)?.abort()
    controllers.current.delete(id)
    setRuns((current) => ({
      ...current,
      [id]: { running: false, error: cancelledError() },
    }))
  }

  if (status === "loading") return <LoadingState label="Loading notes" />
  if (status === "error") {
    return (
      <ErrorState
        error={error ?? new Error("Could not load notes")}
        onRetry={() => window.location.reload()}
      />
    )
  }
  if (notes.length === 0) {
    return (
      <EmptyState
        title="No notes yet"
        description="Write your own lines, then generate more from them."
        action={<Button onClick={createNote}>New note</Button>}
      />
    )
  }

  const note = notes.find((n) => n.id === selectedId) ?? notes[0]
  const run = runs[note.id]
  const view =
    views[note.id] ?? (note.segments.some(isGenerated) ? "enhanced" : "mine")

  return (
    <div className={cn("flex h-full min-h-0", className)}>
      <nav
        aria-label="Notes"
        className="flex w-44 shrink-0 flex-col gap-0.5 overflow-y-auto border-r p-2"
      >
        {notes.map((item) => (
          <button
            key={item.id}
            type="button"
            aria-current={item.id === note.id ? "true" : undefined}
            title={item.title}
            onClick={() => setSelectedId(item.id)}
            className={cn(
              "truncate rounded-md px-2 py-1 text-left text-xs outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring/50",
              item.id === note.id && "bg-accent font-medium"
            )}
          >
            {item.title || "Untitled note"}
          </button>
        ))}
        <Button
          size="xs"
          variant="ghost"
          className="mt-1 justify-start"
          onClick={createNote}
        >
          New note
        </Button>
      </nav>
      <NoteView
        key={note.id}
        note={note}
        view={view}
        onViewChange={(next) =>
          setViews((current) => ({ ...current, [note.id]: next }))
        }
        onChange={(patch) => commit(note.id, patch)}
        onGenerate={onGenerate ? () => generate(note.id) : undefined}
        onCancel={() => cancel(note.id)}
        generating={run?.running}
        error={run?.error}
      />
    </div>
  )
}
