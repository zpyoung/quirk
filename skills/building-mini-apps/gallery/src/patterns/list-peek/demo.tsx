import { useMemo, useState } from "react"

import { useCollection } from "@/lib/mini/store"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Kbd } from "@/components/ui/kbd"

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

export default function Demo() {
  const books = useCollection<Book>("list-peek-demo", SEED)
  const [preview, setPreview] = useState<Preview>("live")
  const [opened, setOpened] = useState<Book | null>(null)

  const ordered = useMemo(
    () => [...books.items].sort((a, b) => STATUSES.indexOf(a.status) - STATUSES.indexOf(b.status)),
    [books.items]
  )

  const restoreSamples = () => {
    setPreview("live")
    void books.replaceAll(SEED)
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
        <ListPeek
          aria-label="Reading list"
          items={items}
          status={status}
          error={new Error("Could not read the reading list (simulated).")}
          onRetry={() => setPreview("live")}
          groupBy={(book) => book.status}
          filterText={(book) => `${book.id} ${book.title} ${book.author}`}
          renderLead={(book) => book.id}
          renderMeta={(book) => book.author}
          onOpen={setOpened}
          emptyTitle="Your reading list is empty"
          emptyAction={{ label: "Restore sample books", onClick: restoreSamples }}
          renderPeek={(book) => (
            <article className="flex flex-col gap-3">
              <h2 className="line-clamp-3 text-base font-semibold">{book.title}</h2>
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
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    void books.update(book.id, {
                      status: STATUSES[(STATUSES.indexOf(book.status) + 1) % STATUSES.length],
                    })
                  }
                >
                  Move to {STATUSES[(STATUSES.indexOf(book.status) + 1) % STATUSES.length]}
                </Button>
                <Button size="sm" variant="outline" onClick={() => void books.remove(book.id)}>
                  Remove
                </Button>
              </div>
            </article>
          )}
        />
      </div>

      <p className="text-xs text-muted-foreground" aria-live="polite">
        {opened ? `Enter opened ${opened.id}: ${opened.title}` : "Press Enter on a highlighted row to open it."}
      </p>

      <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
        <li><Kbd>j</Kbd> <Kbd>k</Kbd> move</li>
        <li><Kbd>Space</Kbd> peek (hold to peek while pressed)</li>
        <li><Kbd>Enter</Kbd> open</li>
        <li><Kbd>/</Kbd> filter</li>
        <li><Kbd>Home</Kbd> <Kbd>End</Kbd> first / last</li>
        <li><Kbd>Esc</Kbd> close, then clear</li>
      </ul>
    </div>
  )
}
