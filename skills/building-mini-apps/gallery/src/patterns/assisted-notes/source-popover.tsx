import { useRef, useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover"

import type { NoteSegment } from "./types"

/**
 * Wraps `children` (the trigger, usually a Source button) with a popover that
 * quotes the excerpt a generated line came from. `onKeep` adds a Keep as mine
 * action. Without `segment.source` it renders `children` alone.
 */
export function SourcePopover({
  segment,
  onKeep,
  children,
}: {
  segment: NoteSegment
  onKeep?: (id: string) => void
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const keepRef = useRef<HTMLButtonElement>(null)
  const excerptRef = useRef<HTMLQuoteElement>(null)
  const kept = useRef(false)
  const { source } = segment

  if (!source) return <>{children}</>

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent
        side="bottom"
        align="end"
        aria-label="Source"
        className="w-[min(21rem,90vw)]"
        onOpenAutoFocus={(event) => {
          event.preventDefault()
          ;(keepRef.current ?? excerptRef.current)?.focus()
        }}
        onCloseAutoFocus={(event) => {
          // the row is replaced after Keep, so the caller places focus instead
          if (kept.current) event.preventDefault()
        }}
      >
        <PopoverHeader>
          <PopoverTitle className="text-[0.7rem] font-semibold tracking-wide text-muted-foreground uppercase">
            {source.label ?? "Source"}
          </PopoverTitle>
          {source.summary ? (
            <PopoverDescription className="text-xs">
              {source.summary}
            </PopoverDescription>
          ) : null}
        </PopoverHeader>
        <blockquote
          ref={excerptRef}
          tabIndex={0}
          aria-label="Source excerpt"
          className="max-h-32 overflow-y-auto rounded-md border-l-2 border-border bg-muted px-2 py-1.5 text-xs break-words whitespace-pre-wrap text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          {source.excerpt}
        </blockquote>
        {onKeep ? (
          <Button
            ref={keepRef}
            size="sm"
            variant="outline"
            className="self-start"
            onClick={() => {
              kept.current = true
              onKeep(segment.id)
              setOpen(false)
            }}
          >
            Keep as mine
          </Button>
        ) : null}
      </PopoverContent>
    </Popover>
  )
}
