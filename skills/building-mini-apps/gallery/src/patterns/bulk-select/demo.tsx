import { useMemo, useState } from "react"
import {
  ArchiveIcon,
  CheckCheckIcon,
  LockIcon,
  LockOpenIcon,
  MailIcon,
  MergeIcon,
  PaperclipIcon,
  TrashIcon,
} from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useCollection } from "@/lib/mini/store"
import { cn } from "@/lib/utils"

import { AssigneeCell } from "./assignee-cell"
import { BulkSelect } from "./bulk-select"
import {
  ASSIGNEES,
  MAILBOXES,
  buildRecordings,
  buildThreads,
  formatAge,
  formatAgo,
  formatLength,
  type Mailbox,
  type Recording,
  type Thread,
} from "./demo-data"
import { TrendCell } from "./trend-cell"
import { formatCount } from "./trend"
import type { BulkSelectAction, BulkSelectColumn } from "./types"

type Preview = "live" | "empty" | "loading" | "error"
type Table = "inbox" | "recordings"

const PREVIEWS: Preview[] = ["live", "empty", "loading", "error"]
const TABLES: Array<{ id: Table; label: string }> = [
  { id: "inbox", label: "Inbox threads" },
  { id: "recordings", label: "Recordings" },
]
const NEW_WITHIN = 3 * 24 * 3_600_000

const HINTS = [
  "j/k or arrows move the highlight",
  "x selects the highlighted row",
  "Shift-click a checkbox for a range",
  "Enter or double-click opens",
  "Esc clears the selection, then the highlight",
]

function Segments({ filled, total = 10 }: { filled: number; total?: number }) {
  return (
    <div
      role="img"
      aria-label={`Activity ${filled} of ${total}`}
      className="flex gap-0.5"
    >
      {Array.from({ length: total }, (_, index) => (
        <span
          key={index}
          className={cn(
            "h-4 w-1.5 rounded-[2px]",
            index < filled ? "bg-(--chart-1)" : "bg-muted"
          )}
        />
      ))}
    </div>
  )
}

function reportWrite(write: Promise<unknown>) {
  write.catch((cause: unknown) => {
    toast.error("Couldn't save the change", {
      description: cause instanceof Error ? cause.message : String(cause),
    })
  })
}

export default function Demo() {
  const [seed] = useState(() => {
    const at = Date.now()
    return { at, threads: buildThreads(at), recordings: buildRecordings(at) }
  })
  const threads = useCollection<Thread>("bulk-select-demo", seed.threads)
  const recordings = useCollection<Recording>(
    "bulk-select-demo-recordings",
    seed.recordings
  )
  const [now, setNow] = useState(seed.at)

  const [table, setTable] = useState<Table>("inbox")
  const [preview, setPreview] = useState<Preview>("live")
  const [query, setQuery] = useState("")
  const [mailbox, setMailbox] = useState<Mailbox | "All">("All")
  const [selected, setSelected] = useState<string[]>([])
  const [highlighted, setHighlighted] = useState<string | null>(null)

  const inbox = table === "inbox"
  const store = inbox ? threads : recordings
  const filtering =
    preview !== "empty" && (query.trim() !== "" || (inbox && mailbox !== "All"))

  const threadRows = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return threads.items.filter(
      (thread) =>
        thread.status === "open" &&
        (mailbox === "All" || thread.mailbox === mailbox) &&
        (!needle ||
          `${thread.id} ${thread.subject} ${thread.from} ${thread.preview}`
            .toLowerCase()
            .includes(needle))
    )
  }, [threads.items, query, mailbox])

  const recordingRows = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return recordings.items.filter(
      (recording) =>
        !needle ||
        `${recording.id} ${recording.name} ${recording.who}`
          .toLowerCase()
          .includes(needle)
    )
  }, [recordings.items, query])

  const status =
    preview === "loading" || preview === "error" ? preview : store.status
  const hidden = preview === "empty"

  const patchThreads = (ids: string[], patch: Partial<Thread>) =>
    reportWrite(Promise.all(ids.map((id) => threads.update(id, patch))))
  const patchRecordings = (ids: string[], patch: Partial<Recording>) =>
    reportWrite(Promise.all(ids.map((id) => recordings.update(id, patch))))

  const selectedThreads = threads.items.filter((thread) =>
    selected.includes(thread.id)
  )
  const mailboxes = new Set(selectedThreads.map((thread) => thread.mailbox))
  const mergeReason =
    selected.length < 2
      ? "Select at least two threads to merge."
      : mailboxes.size > 1
        ? "Threads from different mailboxes can't be merged."
        : undefined

  const threadActions: BulkSelectAction[] = [
    {
      id: "done",
      label: "Mark done",
      icon: <CheckCheckIcon aria-hidden />,
      onSelect: (ids) => {
        patchThreads(ids, { status: "done" })
        toast(
          `${ids.length} ${ids.length === 1 ? "thread" : "threads"} marked done`
        )
      },
    },
    {
      id: "archive",
      label: "Archive",
      icon: <ArchiveIcon aria-hidden />,
      onSelect: (ids) => {
        patchThreads(ids, { status: "archived" })
        toast(
          `${ids.length} ${ids.length === 1 ? "thread" : "threads"} archived`
        )
      },
    },
    {
      id: "merge",
      label: "Merge",
      icon: <MergeIcon aria-hidden />,
      disabledReason: mergeReason,
      onSelect: (ids) => {
        const [keep, ...rest] = ids
        patchThreads(rest, { status: "archived" })
        toast(`Merged ${ids.length} threads into ${keep}`)
      },
    },
    {
      id: "unread",
      label: "Mark unread",
      icon: <MailIcon aria-hidden />,
      overflow: true,
      onSelect: (ids) => patchThreads(ids, { unread: true }),
    },
    {
      id: "delete",
      label: "Delete",
      icon: <TrashIcon aria-hidden />,
      overflow: true,
      disabledReason: "You do not have permission to delete threads.",
      onSelect: () => undefined,
    },
  ]

  const lockedSelected = recordings.items.some(
    (recording) => selected.includes(recording.id) && recording.locked
  )
  const recordingActions: BulkSelectAction[] = [
    {
      id: "lock",
      label: "Lock",
      icon: <LockIcon aria-hidden />,
      onSelect: (ids) => patchRecordings(ids, { locked: true }),
    },
    {
      id: "unlock",
      label: "Unlock",
      icon: <LockOpenIcon aria-hidden />,
      onSelect: (ids) => patchRecordings(ids, { locked: false }),
    },
    {
      id: "delete",
      label: "Delete",
      icon: <TrashIcon aria-hidden />,
      overflow: true,
      disabledReason: lockedSelected
        ? "Locked recordings can't be deleted. Unlock them first."
        : undefined,
      onSelect: (ids) => {
        reportWrite(Promise.all(ids.map((id) => recordings.remove(id))))
        toast(
          `${ids.length} ${ids.length === 1 ? "recording" : "recordings"} deleted`
        )
      },
    },
  ]

  const threadColumns: BulkSelectColumn<Thread>[] = [
    {
      id: "thread",
      header: "Thread",
      width: "minmax(0, 2.6fr)",
      cell: (thread) => (
        <>
          <div className="flex min-w-0 items-center gap-1.5">
            {thread.unread ? (
              <>
                <span
                  aria-hidden
                  className="size-1.5 shrink-0 rounded-full bg-primary"
                />
                <span className="sr-only">Unread: </span>
              </>
            ) : null}
            <span className="truncate font-semibold" title={thread.subject}>
              {thread.subject}
            </span>
          </div>
          <p className="truncate text-muted-foreground">{thread.preview}</p>
          <div className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
            <Badge variant="secondary">{thread.mailbox}</Badge>
            <span className="tabular-nums">{thread.id}</span>
            {thread.attachment ? (
              <>
                <PaperclipIcon className="size-3 shrink-0" aria-hidden />
                <span className="sr-only">Has an attachment</span>
              </>
            ) : null}
            <span className="truncate">{thread.from}</span>
          </div>
        </>
      ),
    },
    {
      id: "last",
      header: "Last activity",
      width: "6.5rem",
      cell: (thread) => (
        <span className="text-sm">{formatAgo(now, thread.lastActivity)}</span>
      ),
    },
    {
      id: "age",
      header: "Age",
      width: "4rem",
      cell: (thread) => (
        <span className="text-sm">{formatAge(now, thread.created)}</span>
      ),
    },
    {
      id: "trend",
      header: "Trend (14 days)",
      width: "9.5rem",
      cell: (thread) => (
        <TrendCell
          values={thread.daily}
          label={`Messages per day for ${thread.id}`}
          caption={now - thread.created < NEW_WITHIN ? "New" : "Ongoing"}
        />
      ),
    },
    {
      id: "messages",
      header: "Messages",
      width: "5.5rem",
      align: "end",
      cell: (thread) => (
        <span className="text-sm">{formatCount(thread.messages)}</span>
      ),
    },
    {
      id: "people",
      header: "People",
      width: "5rem",
      align: "end",
      cell: (thread) => (
        <span className="text-sm">{formatCount(thread.people)}</span>
      ),
    },
    {
      id: "assignee",
      header: "Assignee",
      width: "5.5rem",
      cell: (thread) => (
        <AssigneeCell
          value={thread.assignee}
          groups={ASSIGNEES}
          onChange={(assignee) => patchThreads([thread.id], { assignee })}
          label="Assignee"
        />
      ),
    },
  ]

  const recordingColumns: BulkSelectColumn<Recording>[] = [
    {
      id: "recording",
      header: "Recording",
      width: "minmax(0, 2.2fr)",
      cell: (recording) => (
        <>
          <span className="truncate font-semibold" title={recording.name}>
            {recording.name}
          </span>
          <span className="flex min-w-0 items-center gap-1.5 truncate text-xs text-muted-foreground">
            {recording.locked ? (
              <LockIcon className="size-3 shrink-0" aria-label="Locked" />
            ) : null}
            <span className="truncate">
              {recording.who} · {formatAgo(now, recording.startedAt)}
            </span>
          </span>
        </>
      ),
    },
    {
      id: "device",
      header: "Device",
      width: "6rem",
      cell: (recording) => <span className="text-sm">{recording.device}</span>,
    },
    {
      id: "length",
      header: "Length",
      width: "5rem",
      cell: (recording) => (
        <span className="text-sm tabular-nums">
          {formatLength(recording.seconds)}
        </span>
      ),
    },
    {
      id: "bookmarks",
      header: "Bookmarks",
      width: "6rem",
      align: "end",
      cell: (recording) => (
        <span className="text-sm">{recording.bookmarks}</span>
      ),
    },
    {
      id: "activity",
      header: "Activity",
      width: "8rem",
      cell: (recording) => <Segments filled={recording.activity} />,
    },
  ]

  const switchTable = (next: Table) => {
    setTable(next)
    setSelected([])
    setHighlighted(null)
    setQuery("")
    setMailbox("All")
  }

  const clearFilters = () => {
    setQuery("")
    setMailbox("All")
  }

  const restore = () => {
    const at = Date.now()
    setNow(at)
    setPreview("live")
    clearFilters()
    if (inbox) reportWrite(threads.replaceAll(buildThreads(at)))
    else reportWrite(recordings.replaceAll(buildRecordings(at)))
  }

  const common = {
    status,
    error: new Error(
      `Could not read the ${inbox ? "inbox" : "recordings"} (simulated).`
    ),
    onRetry: () => setPreview("live"),
    selectedIds: selected,
    onSelectedIdsChange: setSelected,
    highlightedId: highlighted,
    onHighlightedIdChange: setHighlighted,
    emptyTitle: filtering
      ? `No ${inbox ? "threads" : "recordings"} match your filters`
      : inbox
        ? "Your inbox is empty"
        : "No recordings yet",
    emptyDescription: filtering
      ? "Check the search spelling and the mailbox filter, or clear the filters."
      : "Nothing is waiting here right now.",
    emptyAction: filtering
      ? { label: "Clear filters", onClick: clearFilters }
      : {
          label: inbox ? "Restore sample threads" : "Restore sample recordings",
          onClick: restore,
        },
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            State preview (demo only)
          </span>
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
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            Table (demo only)
          </span>
          <div role="group" aria-label="Table" className="flex gap-1">
            {TABLES.map((option) => (
              <Button
                key={option.id}
                size="xs"
                variant={table === option.id ? "default" : "outline"}
                aria-pressed={table === option.id}
                onClick={() => switchTable(option.id)}
              >
                {option.label}
              </Button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={inbox ? "Search threads" : "Search recordings"}
          aria-label={inbox ? "Search threads" : "Search recordings"}
          className="h-8 max-w-64"
        />
        {inbox ? (
          <div role="group" aria-label="Mailbox" className="flex gap-1">
            {(["All", ...MAILBOXES] as const).map((name) => (
              <Button
                key={name}
                size="xs"
                variant={mailbox === name ? "secondary" : "outline"}
                aria-pressed={mailbox === name}
                onClick={() => setMailbox(name)}
              >
                {name}
              </Button>
            ))}
          </div>
        ) : null}
        <p className="ml-auto text-xs text-muted-foreground">
          Selection handed to the host:{" "}
          {selected.length > 0 ? selected.join(", ") : "none"}
        </p>
      </div>

      <div className="min-h-[24rem] flex-1 overflow-hidden rounded-lg border">
        {inbox ? (
          <BulkSelect
            key="inbox"
            {...common}
            aria-label="Inbox threads"
            items={hidden ? [] : threadRows}
            columns={threadColumns}
            actions={threadActions}
            selectionNoun="thread"
            rowLabel={(thread) => thread.subject}
            onOpen={(thread) =>
              toast(`Open ${thread.id}: the host decides what opening means`)
            }
          />
        ) : (
          <BulkSelect
            key="recordings"
            {...common}
            aria-label="Recordings"
            items={hidden ? [] : recordingRows}
            columns={recordingColumns}
            actions={recordingActions}
            selectionNoun="recording"
            rowHeight={60}
            minWidth="38rem"
            rowLabel={(recording) => recording.name}
            onOpen={(recording) =>
              toast(`Open ${recording.id}: the host decides what opening means`)
            }
          />
        )}
      </div>

      <p className="text-xs text-muted-foreground">{HINTS.join(" · ")}</p>
    </div>
  )
}
