import { useEffect, useMemo, useRef, useState } from "react"
import { useHotkeys } from "react-hotkeys-hook"
import { ArrowLeftIcon } from "lucide-react"

import { useCollection } from "@/lib/mini/store"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

import { ListPeek } from "./list-peek"

type BookStatus = "To read" | "Reading" | "Done"

type Book = {
  id: string
  title: string
  author: string
  status: BookStatus
  added: string
  notes: string
}

type Preview = "live" | "empty" | "loading" | "error"

const STATUSES: BookStatus[] = ["To read", "Reading", "Done"]
const PREVIEWS: Preview[] = ["live", "empty", "loading", "error"]

const SEED: Book[] = [
  { id: "BK-01", title: "The Lighthouse Keeper's Almanac", author: "M. Okafor", status: "To read", added: "2026-09-02", notes: "Recommended for the tide tables alone. Skim the appendix on fog signals first." },
  { id: "BK-02", title: "Small Gardens, Large Patience", author: "R. Lindqvist", status: "To read", added: "2026-09-05", notes: "Container planting for a north-facing balcony." },
  { id: "BK-03", title: "A Field Guide to Quiet Machines", author: "T. Nakamura", status: "To read", added: "2026-09-11", notes: "Short chapters on clocks, looms and pumps. Good for the train." },
  { id: "BK-04", title: "The Interesting Narrative of an Exhaustively Documented Voyage Across Three Oceans, Two Mutinies, and One Surprisingly Well-Preserved Wheel of Cheese", author: "Capt. E. Thorne-Whitcombe", status: "To read", added: "2026-09-14", notes: "Deliberately long title to check truncation in the row and wrapping in the panel. Reviews say the cheese chapters are the best part.\n\nThe edition on the shelf is the annotated two-volume set, so budget a few weekends." },
  { id: "BK-05", title: "Ledger of Small Mercies", author: "A. Duarte", status: "To read", added: "2026-09-18", notes: "Short stories. Start with the title story." },
  { id: "BK-06", title: "Maps Nobody Asked For", author: "J. Petrov", status: "To read", added: "2026-09-21", notes: "Essays on amateur cartography." },
  { id: "BK-07", title: "The Slow Compiler", author: "H. Abara", status: "Reading", added: "2026-08-19", notes: "Chapter 6 onward is the interesting part. Halfway through, taking notes on parsing." },
  { id: "BK-08", title: "Salt, Smoke and Time", author: "L. Moreau", status: "Done", added: "2026-06-03", notes: "Preservation techniques by region. The curing tables are worth photocopying." },
  { id: "BK-09", title: "Night Trains of the Interior", author: "S. Varga", status: "Done", added: "2026-06-17", notes: "Travel writing. Loved the dining car chapter." },
  { id: "BK-10", title: "On Keeping Bees Badly", author: "C. Ferreira", status: "Done", added: "2026-07-01", notes: "Funny, practical, and honest about the mistakes." },
  { id: "BK-11", title: "Arithmetic for the Curious", author: "P. Whitlock", status: "Done", added: "2026-07-09", notes: "Good puzzles. Skipped the final proofs." },
  { id: "BK-12", title: "The Cartographer's Apprentice", author: "N. Eze", status: "Done", added: "2026-07-22", notes: "A novel. Reread the ending twice." },
  { id: "BK-13", title: "Rivers of the Low Country", author: "D. Castellano", status: "Done", added: "2026-08-02", notes: "Dense but rewarding. Footnotes are the best bit." },
  { id: "BK-14", title: "Plain Text Forever", author: "K. Sorensen", status: "Done", added: "2026-08-11", notes: "A short polemic on keeping notes in files you can still open in thirty years." },
]

const dateFormat = new Intl.DateTimeFormat("en", { dateStyle: "medium", timeZone: "UTC" })

const formatDate = (iso: string) => dateFormat.format(new Date(`${iso}T00:00:00Z`))

const nextStatus = (status: BookStatus) => STATUSES[(STATUSES.indexOf(status) + 1) % STATUSES.length]

const HINTS = [
  "Click or Space toggle peek",
  "Hold Space peek while pressed",
  "Enter or double-click open full view",
  "j/k move",
  "/ filter",
  "Home/End first or last",
  "Esc clear filter, close peek, then clear highlight",
]

function BookDetail({
  book,
  full = false,
  onMove,
  onRemove,
}: {
  book: Book
  full?: boolean
  onMove: () => void
  onRemove: () => void
}) {
  const Heading = full ? "h1" : "h2"
  return (
    <article className="flex flex-col gap-3">
      <Heading className={full ? "text-xl font-semibold" : "line-clamp-3 text-base font-semibold"}>
        {book.title}
      </Heading>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="secondary">{book.status}</Badge>
        <span>{book.author}</span>
        <span aria-hidden>·</span>
        <span>Added {formatDate(book.added)}</span>
        <span aria-hidden>·</span>
        <span>{book.id}</span>
      </div>
      <p className="text-sm leading-relaxed whitespace-pre-line">{book.notes}</p>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" onClick={onMove}>
          Move to {nextStatus(book.status)}
        </Button>
        <Button size="sm" variant="outline" onClick={onRemove}>
          Remove
        </Button>
      </div>
    </article>
  )
}

export default function Demo() {
  const books = useCollection<Book>("list-peek-demo", SEED)
  const [preview, setPreview] = useState<Preview>("live")
  const [openedId, setOpenedId] = useState<string | null>(null)
  const [highlightedId, setHighlightedId] = useState<string | null>(null)
  const [peekOpen, setPeekOpen] = useState(false)
  const fullViewRef = useRef<HTMLElement>(null)

  const ordered = useMemo(
    () => [...books.items].sort((a, b) => STATUSES.indexOf(a.status) - STATUSES.indexOf(b.status)),
    [books.items]
  )

  const restoreSamples = () => {
    setPreview("live")
    void books.replaceAll(SEED)
  }

  const opened = preview === "live" ? ordered.find((book) => book.id === openedId) : undefined

  const backToList = () => setOpenedId(null)
  const fullViewOpen = opened !== undefined
  useHotkeys("esc", backToList, { enabled: fullViewOpen })
  useEffect(() => {
    if (fullViewOpen) fullViewRef.current?.focus()
  }, [fullViewOpen])

  const removeFromFullView = (book: Book) => {
    const at = ordered.findIndex((item) => item.id === book.id)
    setHighlightedId((ordered[at + 1] ?? ordered[at - 1])?.id ?? null)
    setPeekOpen(false)
    setOpenedId(null)
    void books.remove(book.id)
  }

  const status = preview === "live" ? books.status : preview === "empty" ? "ready" : preview
  const items = preview === "empty" ? [] : ordered

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">State preview (demo only)</span>
        <div role="group" aria-label="State preview" className="flex gap-1">
          {PREVIEWS.map((name) => (
            <Button
              key={name}
              size="xs"
              variant={preview === name ? "default" : "outline"}
              aria-pressed={preview === name}
              onClick={() => setPreview(name)}
              className="capitalize"
            >
              {name}
            </Button>
          ))}
        </div>
      </div>

      <div className="min-h-[24rem] flex-1 overflow-hidden rounded-lg border">
        {opened ? (
          <section
            ref={fullViewRef}
            tabIndex={-1}
            aria-label={`Full view: ${opened.title}`}
            className="flex h-full flex-col outline-none"
          >
            <div className="flex h-11 shrink-0 items-center gap-3 border-b px-3">
              <Button size="sm" variant="ghost" onClick={backToList}>
                <ArrowLeftIcon aria-hidden />
                Back to list
              </Button>
              <span className="text-xs text-muted-foreground">or press Esc</span>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-6">
              <div className="max-w-2xl">
                <BookDetail
                  full
                  book={opened}
                  onMove={() => void books.update(opened.id, { status: nextStatus(opened.status) })}
                  onRemove={() => removeFromFullView(opened)}
                />
              </div>
            </div>
          </section>
        ) : (
          <ListPeek
            autoFocus={highlightedId !== null}
            aria-label="Reading list"
            items={items}
            status={status}
            error={new Error("Could not read the reading list (simulated).")}
            onRetry={() => setPreview("live")}
            groupBy={(book) => book.status}
            filterText={(book) => `${book.id} ${book.title} ${book.author}`}
            renderLead={(book) => book.id}
            renderMeta={(book) => book.author}
            highlightedId={highlightedId}
            onHighlightedIdChange={setHighlightedId}
            peekOpen={peekOpen}
            onPeekOpenChange={setPeekOpen}
            onOpen={(book) => setOpenedId(book.id)}
            emptyTitle="Your reading list is empty"
            emptyAction={{ label: "Restore sample books", onClick: restoreSamples }}
            renderPeek={(book) => (
              <BookDetail
                book={book}
                onMove={() => void books.update(book.id, { status: nextStatus(book.status) })}
                onRemove={() => void books.remove(book.id)}
              />
            )}
          />
        )}
      </div>

      <p className="text-xs text-muted-foreground">{HINTS.join(" · ")}</p>
    </div>
  )
}
