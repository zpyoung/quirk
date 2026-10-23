import { useId } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

import { SourcePopover } from "./source-popover"
import type { NoteSegment } from "./types"

function Marker({ kind }: { kind: NoteSegment["kind"] }) {
  if (kind === "heading" || kind === "text") return null
  return (
    <span
      aria-hidden
      className="w-2.5 shrink-0 pt-px text-sm leading-6 text-muted-foreground"
    >
      •
    </span>
  )
}

const textClass = (kind: NoteSegment["kind"]) =>
  kind === "heading"
    ? "text-base leading-6 font-semibold md:text-base"
    : "text-sm leading-6 md:text-sm"

export function UserRow({
  segment,
  placeholder,
  onTextChange,
}: {
  segment: NoteSegment
  placeholder?: string
  onTextChange: (id: string, text: string) => void
}) {
  return (
    <div className="flex items-start gap-2 rounded-sm border-l-2 border-transparent py-0.5 pl-3 focus-within:bg-accent/40">
      <Marker kind={segment.kind} />
      <Textarea
        rows={1}
        value={segment.text}
        placeholder={placeholder}
        aria-label="Note line"
        data-row-id={segment.id}
        data-row-origin="user"
        onChange={(event) => onTextChange(segment.id, event.target.value)}
        className={cn(
          "min-h-0 flex-1 resize-none rounded-none border-0 bg-transparent p-0 shadow-none focus-visible:ring-0 dark:bg-transparent",
          textClass(segment.kind)
        )}
      />
    </div>
  )
}

export function GeneratedRow({
  segment,
  onKeep,
}: {
  segment: NoteSegment
  onKeep: (id: string) => void
}) {
  const labelId = useId()
  const textId = useId()

  return (
    <div
      role="group"
      tabIndex={0}
      data-row-id={segment.id}
      data-row-origin="generated"
      aria-labelledby={`${labelId} ${textId}`}
      className="group flex items-start gap-2 rounded-sm border-l-2 border-muted-foreground/40 py-0.5 pl-3 text-muted-foreground outline-none hover:bg-accent/50 focus-visible:bg-accent/50 focus-visible:ring-2 focus-visible:ring-ring/50"
    >
      <span id={labelId} className="sr-only">
        Generated
      </span>
      <Marker kind={segment.kind} />
      <p
        id={textId}
        className={cn(
          "min-w-0 flex-1 break-words whitespace-pre-wrap",
          textClass(segment.kind)
        )}
      >
        {segment.text}
      </p>
      {segment.source ? (
        <SourcePopover segment={segment} onKeep={onKeep}>
          <Button
            size="xs"
            variant="outline"
            data-source-trigger
            className="shrink-0 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100"
          >
            Source
          </Button>
        </SourcePopover>
      ) : (
        <Badge variant="secondary" className="shrink-0">
          No source
        </Badge>
      )}
    </div>
  )
}
