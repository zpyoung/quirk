import { useState } from "react"
import { toast } from "sonner"

import { ErrorState, LoadingState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { useCollection } from "@/lib/mini/store"

import { DocCollections } from "./doc-collections"
import type { CollectionDef, DocPage, DocRecord } from "./types"

type Preview = "live" | "empty" | "loading" | "error"
const PREVIEWS: Preview[] = ["live", "empty", "loading", "error"]

const PAGE_ID = "reading-list"

const books: CollectionDef = {
  id: "books",
  name: "Books",
  fields: [
    { key: "status", label: "Status", type: "select", options: ["Want to read", "Reading", "Finished"] },
    { key: "rating", label: "Rating", type: "number" },
    { key: "started", label: "Started", type: "date" },
    { key: "owned", label: "Owned", type: "checkbox" },
  ],
}

const quotes: CollectionDef = {
  id: "quotes",
  name: "Quotes",
  fields: [
    { key: "source", label: "Source", type: "text" },
    { key: "page", label: "Page", type: "number" },
  ],
}

const seedPage: DocPage = {
  id: PAGE_ID,
  title: "Reading List",
  collections: [books, quotes],
  blocks: [
    {
      id: "intro",
      kind: "text",
      text: "A running log of what I read this year. Each book keeps a short review in its notes.",
    },
    { id: "books-block", kind: "collection", collectionId: books.id },
    { id: "between", kind: "text", text: "Lines worth keeping, with where they came from." },
    { id: "quotes-block", kind: "collection", collectionId: quotes.id },
  ],
}

function book(
  n: number,
  title: string,
  status: string,
  rating: number | null,
  started: string | null,
  owned: boolean,
  body = ""
): DocRecord {
  return { id: `book-${n}`, title, collectionId: books.id, props: { status, rating, started, owned }, body }
}

function quote(n: number, title: string, source: string, page: number, body = ""): DocRecord {
  return { id: `quote-${n}`, title, collectionId: quotes.id, props: { source, page }, body }
}

const seedRecords: DocRecord[] = [
  book(1, "Dune", "Finished", 4, "2026-01-04", true, "Slow first hundred pages, then it does not let go."),
  book(2, "Deep Work", "Reading", null, "2026-03-10", true, "Good argument, repetitive examples."),
  book(3, "The Left Hand of Darkness", "Finished", 5, "2026-02-01", false, "The journey across the ice is the whole book."),
  book(4, "Braiding Sweetgrass", "Reading", null, "2026-04-02", true),
  book(5, "Piranesi", "Finished", 5, "2026-01-20", false, "Short and strange. Read it in one sitting."),
  book(6, "The Overstory", "Want to read", null, null, false),
  book(7, "A Pattern Language", "Reading", 3, "2026-03-28", true, "A book to dip into, not to read straight through."),
  book(8, "Flatland", "Finished", 3, "2026-02-18", false),
  book(
    9,
    "An Exceptionally Long Working Title for a Book About Everything That Happened Before, During and After the Great Reorganization of the Municipal Archive",
    "Want to read",
    null,
    null,
    false
  ),
  book(10, "Gödel, Escher, Bach", "Want to read", null, null, true),
  book(11, "The Dispossessed", "Finished", 4, "2026-05-06", true, "Both planets feel lived in."),
  book(12, "Seeing Like a State", "Reading", null, "2026-06-12", false),
]

const seedQuotes: DocRecord[] = [
  quote(1, "The mystery of life isn't a problem to solve", "Dune", 12),
  quote(2, "Attention is the rarest form of generosity", "Deep Work", 88, "Paraphrased from memory; check the exact wording."),
  quote(3, "It is good to have an end to journey toward", "The Left Hand of Darkness", 220),
  quote(4, "The house is all the world", "Piranesi", 41),
  quote(5, "Every pattern is a relationship between parts", "A Pattern Language", 9),
]

const initialRecords = [...seedRecords, ...seedQuotes]

type Journal = {
  page: DocPage
  onPageChange: (page: DocPage) => void
  records: DocRecord[]
  onAdd: (collectionId: string) => Promise<DocRecord>
  onUpdate: (id: string, patch: Partial<DocRecord>) => Promise<void>
  onRemove: (id: string) => Promise<void>
}

function newRecord(collectionId: string): DocRecord {
  return { id: crypto.randomUUID(), title: "Untitled", collectionId, props: {}, body: "" }
}

function useStoredJournal(): Journal & { status: "loading" | "ready" | "error"; error?: Error } {
  const pages = useCollection<DocPage>("doc-collections-demo-page", [seedPage])
  const records = useCollection<DocRecord>("doc-collections-demo", initialRecords)
  const page = pages.items.find((item) => item.id === PAGE_ID) ?? seedPage

  const status = pages.status === "error" || records.status === "error" ? "error" : pages.status === "loading" || records.status === "loading" ? "loading" : "ready"

  return {
    status,
    error: pages.error ?? records.error,
    page,
    onPageChange: (next) => {
      pages.update(PAGE_ID, next).catch((cause: unknown) => {
        toast.error(`Could not save: ${cause instanceof Error ? cause.message : String(cause)}`)
      })
    },
    records: records.items,
    onAdd: async (collectionId) => {
      const created = newRecord(collectionId)
      await records.add(created)
      return created
    },
    onUpdate: records.update,
    onRemove: records.remove,
  }
}

// the empty preview must not touch the stored journal, so it edits its own in-memory copy
function useScratchJournal(): Journal {
  const [page, setPage] = useState<DocPage>({ id: "scratch", title: "Reading List", blocks: [], collections: [] })
  const [records, setRecords] = useState<DocRecord[]>([])
  return {
    page,
    onPageChange: setPage,
    records,
    onAdd: async (collectionId) => {
      const created = newRecord(collectionId)
      setRecords((current) => [...current, created])
      return created
    },
    onUpdate: async (id, patch) => setRecords((current) => current.map((r) => (r.id === id ? { ...r, ...patch } : r))),
    onRemove: async (id) => setRecords((current) => current.filter((r) => r.id !== id)),
  }
}

function PreviewSwitch({ value, onChange }: { value: Preview; onChange: (value: Preview) => void }) {
  return (
    <div role="group" aria-label="Preview state" className="flex h-9 shrink-0 items-center justify-end gap-1 border-b px-3">
      <span className="mr-1 text-xs text-muted-foreground">Preview state</span>
      {PREVIEWS.map((state) => (
        <Button
          key={state}
          size="xs"
          variant={state === value ? "secondary" : "ghost"}
          aria-pressed={state === value}
          onClick={() => onChange(state)}
        >
          {state}
        </Button>
      ))}
    </div>
  )
}

export default function Demo() {
  const [preview, setPreview] = useState<Preview>("live")
  const stored = useStoredJournal()
  const scratch = useScratchJournal()

  const shown: Preview = preview !== "live" ? preview : stored.status === "ready" ? "live" : stored.status
  const journal = preview === "empty" ? scratch : stored

  let body
  if (shown === "loading" || shown === "error") {
    body = (
      <>
        <div className="flex h-8 items-center border-b px-3 text-xs font-medium">{stored.page.title}</div>
        {shown === "loading" ? (
          <LoadingState label="Loading document" />
        ) : (
          <ErrorState
            error={stored.error ?? new Error("Could not read the saved document.")}
            onRetry={() => (preview === "live" ? window.location.reload() : setPreview("live"))}
          />
        )}
      </>
    )
  } else {
    body = (
      <DocCollections
        key={shown}
        page={journal.page}
        onPageChange={journal.onPageChange}
        records={journal.records}
        onAdd={journal.onAdd}
        onUpdate={journal.onUpdate}
        onRemove={journal.onRemove}
      />
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PreviewSwitch value={preview} onChange={setPreview} />
      <div className="min-h-0 flex-1 overflow-auto">{body}</div>
    </div>
  )
}
