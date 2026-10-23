import { useCallback, useEffect, useRef, useState } from "react"
import { useHotkeys } from "react-hotkeys-hook"

import { Button } from "@/components/ui/button"
import { Kbd } from "@/components/ui/kbd"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

import { cn } from "@/lib/utils"

import { GeneratedRow, UserRow } from "./note-rows"
import { isGenerated, isUser, newId, orderSegments } from "./segments"
import type { AssistedNoteItem, NoteSegment, NoteViewMode } from "./types"

export type NoteViewProps<T extends AssistedNoteItem> = {
  note: T
  view: NoteViewMode
  onViewChange: (v: NoteViewMode) => void
  /** Title and user-segment edits. */
  onChange: (patch: Partial<T>) => void
  onGenerate?: () => Promise<void>
  onCancel?: () => void
  generating?: boolean
  error?: Error
}

const modLabel =
  typeof navigator !== "undefined" &&
  /Mac|iPhone|iPad/.test(navigator.userAgent)
    ? "⌘"
    : "Ctrl"

const hasText = (segment: NoteSegment) =>
  isUser(segment) && segment.text.trim() !== ""

function rowElements(container: HTMLElement | null): HTMLElement[] {
  return Array.from(
    container?.querySelectorAll<HTMLElement>("[data-row-id]") ?? []
  )
}

function placeCaret(element: HTMLElement, atEnd: boolean) {
  if (!(element instanceof HTMLTextAreaElement)) return
  const position = atEnd ? element.value.length : 0
  element.setSelectionRange(position, position)
}

function spansLines(textarea: HTMLTextAreaElement): boolean {
  const lineHeight = parseFloat(getComputedStyle(textarea).lineHeight)
  return Number.isNaN(lineHeight) || textarea.scrollHeight > lineHeight * 1.5
}

/**
 * One note: title, Mine/Enhanced toggle, the lines, and a pinned Generate
 * footer. Generated lines are read-only and each links back to its source.
 * Persistence and the generator belong to the caller (see `AssistedNotes`).
 */
export function NoteView<T extends AssistedNoteItem>({
  note,
  view,
  onViewChange,
  onChange,
  onGenerate,
  onCancel,
  generating = false,
  error,
}: NoteViewProps<T>) {
  const [placeholderId] = useState(newId)
  const bodyElement = useRef<HTMLDivElement | null>(null)
  const titleElement = useRef<HTMLTextAreaElement>(null)
  const [titleClipped, setTitleClipped] = useState(false)

  const ordered = orderSegments(note.segments)
  const users = ordered.filter(isUser)
  const generatedCount = ordered.length - users.length
  const canGenerate = Boolean(onGenerate) && note.segments.some(hasText)

  const pendingFocus = useRef<string | null>(
    note.segments.some(hasText) ? null : (users[0]?.id ?? placeholderId)
  )
  useEffect(() => {
    const id = pendingFocus.current
    if (!id) return
    pendingFocus.current = null
    const target =
      id === "title"
        ? titleElement.current
        : rowElements(bodyElement.current).find((el) => el.dataset.rowId === id)
    target?.focus()
  })

  const [wasGenerating, setWasGenerating] = useState(generating)
  const [announcement, setAnnouncement] = useState("")
  if (wasGenerating !== generating) {
    setWasGenerating(generating)
    if (generating || error) setAnnouncement("")
    else
      setAnnouncement(
        `${generatedCount} ${generatedCount === 1 ? "line" : "lines"} added`
      )
  }

  function patchSegments(segments: NoteSegment[]) {
    onChange({ segments } as Partial<T>)
  }

  function requestGenerate() {
    if (canGenerate && !generating) void onGenerate?.()
  }

  function switchView(next: NoteViewMode) {
    const active = document.activeElement
    const row =
      active instanceof HTMLElement
        ? active.closest<HTMLElement>("[data-row-id]")
        : null
    if (row && bodyElement.current?.contains(row)) {
      const survives =
        next === "mine" ? row.dataset.rowOrigin === "user" : generatedCount > 0
      pendingFocus.current = survives ? (row.dataset.rowId ?? null) : "title"
    }
    onViewChange(next)
  }

  function setText(id: string, text: string) {
    if (note.segments.some((s) => s.id === id)) {
      patchSegments(
        note.segments.map((s) => (s.id === id ? { ...s, text } : s))
      )
    } else {
      patchSegments([
        ...note.segments,
        { id, origin: "user", text, kind: "bullet" },
      ])
    }
  }

  function addRowBelow(id: string) {
    const base = note.segments.some((s) => s.id === id)
      ? note.segments
      : [
          ...note.segments,
          { id, origin: "user" as const, text: "", kind: "bullet" as const },
        ]
    const created: NoteSegment = {
      id: newId(),
      origin: "user",
      text: "",
      kind: "bullet",
    }
    const index = base.findIndex((s) => s.id === id)
    pendingFocus.current = created.id
    patchSegments([
      ...base.slice(0, index + 1),
      created,
      ...base.slice(index + 1),
    ])
  }

  function deleteRow(row: HTMLElement) {
    const id = row.dataset.rowId
    const userSegments = note.segments.filter(isUser)
    if (!id || userSegments.length <= 1) return
    const rows = rowElements(bodyElement.current)
    const neighbour = rows[rows.indexOf(row) - 1] ?? rows[rows.indexOf(row) + 1]
    const previousUser =
      userSegments[userSegments.findIndex((s) => s.id === id) - 1]
    pendingFocus.current = neighbour?.dataset.rowId ?? null
    patchSegments(
      note.segments
        .filter((s) => s.id !== id)
        .map((s) => (s.after === id ? { ...s, after: previousUser?.id } : s))
    )
  }

  function keepAsMine(id: string) {
    pendingFocus.current = id
    patchSegments(
      ordered.map((s) =>
        s.id === id ? { id, origin: "user", text: s.text, kind: s.kind } : s
      )
    )
  }

  function moveFocus(from: HTMLElement, direction: 1 | -1) {
    const rows = rowElements(bodyElement.current)
    const target = rows[rows.indexOf(from) + direction]
    if (!target) return
    target.focus()
    placeCaret(target, direction === -1)
  }

  const bodyHotkeys = useHotkeys<HTMLDivElement>(
    "arrowdown,arrowup,enter,backspace",
    (event) => {
      const active = document.activeElement
      if (!(active instanceof HTMLElement) || !active.dataset.rowId) return
      const isUserRow = active.dataset.rowOrigin === "user"

      if (event.key === "Enter") {
        event.preventDefault()
        if (isUserRow) addRowBelow(active.dataset.rowId)
        else active.querySelector<HTMLElement>("[data-source-trigger]")?.click()
      } else if (event.key === "Backspace") {
        if (
          active instanceof HTMLTextAreaElement &&
          isUserRow &&
          active.value === ""
        ) {
          event.preventDefault()
          deleteRow(active)
        }
      } else {
        const direction = event.key === "ArrowDown" ? 1 : -1
        if (active instanceof HTMLTextAreaElement && spansLines(active)) {
          // let the caret move first; only a press that cannot move it leaves the row
          const { selectionStart, selectionEnd } = active
          setTimeout(() => {
            if (
              document.activeElement === active &&
              active.selectionStart === selectionStart &&
              active.selectionEnd === selectionEnd
            ) {
              moveFocus(active, direction)
            }
          }, 0)
        } else {
          event.preventDefault()
          moveFocus(active, direction)
        }
      }
    },
    { enableOnFormTags: true }
  )
  const setBody = useCallback(
    (element: HTMLDivElement | null) => {
      bodyElement.current = element
      return bodyHotkeys(element)
    },
    [bodyHotkeys]
  )

  useHotkeys(
    "mod+enter",
    (event) => {
      event.preventDefault()
      requestGenerate()
    },
    { enableOnFormTags: true, enableOnContentEditable: true }
  )

  useHotkeys("m", (event) => {
    event.preventDefault()
    if (
      event.target instanceof Element &&
      event.target.closest("[data-slot=popover-content]")
    )
      return
    switchView(view === "mine" ? "enhanced" : "mine")
  })

  useHotkeys(
    "escape",
    (event) => {
      if (event.defaultPrevented) return
      if (generating) return onCancel?.()
      const active = document.activeElement
      if (
        active instanceof HTMLElement &&
        bodyElement.current?.contains(active)
      )
        active.blur()
    },
    { enableOnFormTags: true }
  )

  const placeholderRow: NoteSegment = {
    id: placeholderId,
    origin: "user",
    text: "",
    kind: "bullet",
  }
  const visible = view === "mine" ? users : ordered
  const rows = users.length === 0 ? [placeholderRow, ...visible] : visible
  const onlyEmptyRow = users.length <= 1 && !note.segments.some(hasText)

  const generateButton = (label: string, className?: string) => (
    <Button
      size="sm"
      disabled={!canGenerate}
      aria-disabled={generating || !canGenerate}
      className={cn("aria-disabled:opacity-50", className)}
      onClick={requestGenerate}
    >
      {label}
      <Kbd aria-hidden>{modLabel}↵</Kbd>
    </Button>
  )

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      <header className="shrink-0 border-b">
        <div className="mx-auto flex w-full max-w-[560px] flex-col gap-1.5 px-4 py-3">
          <div className="flex items-start gap-3">
            <Tooltip>
              <TooltipTrigger asChild>
                <Textarea
                  ref={titleElement}
                  rows={1}
                  value={note.title}
                  aria-label="Note title"
                  placeholder="Untitled note"
                  data-mini="title"
                  onChange={(event) =>
                    onChange({
                      title: event.target.value.replace(/\n/g, " "),
                    } as Partial<T>)
                  }
                  onKeyDown={(event) => {
                    if (
                      event.key !== "Enter" ||
                      event.shiftKey ||
                      event.metaKey ||
                      event.ctrlKey
                    )
                      return
                    event.preventDefault()
                    rowElements(bodyElement.current)[0]?.focus()
                  }}
                  onPointerEnter={(event) =>
                    setTitleClipped(
                      event.currentTarget.scrollHeight >
                        event.currentTarget.clientHeight + 1
                    )
                  }
                  onFocus={(event) =>
                    setTitleClipped(
                      event.currentTarget.scrollHeight >
                        event.currentTarget.clientHeight + 1
                    )
                  }
                  className="max-h-[3.2rem] min-h-0 flex-1 resize-none overflow-hidden rounded-none border-0 bg-transparent p-0 text-lg leading-[1.6rem] font-semibold shadow-none focus-visible:ring-0 md:text-lg dark:bg-transparent"
                />
              </TooltipTrigger>
              {titleClipped ? (
                <TooltipContent className="max-w-xs">
                  {note.title}
                </TooltipContent>
              ) : null}
            </Tooltip>
            <ToggleGroup
              type="single"
              variant="outline"
              size="sm"
              spacing={0}
              value={view}
              aria-label="View"
              onValueChange={(value) => {
                if (value === "mine" || value === "enhanced") switchView(value)
              }}
            >
              <ToggleGroupItem value="mine">Mine</ToggleGroupItem>
              <ToggleGroupItem value="enhanced">Enhanced</ToggleGroupItem>
            </ToggleGroup>
          </div>
          {generating ? (
            <div
              role="status"
              className="flex items-center gap-2 text-xs text-muted-foreground"
            >
              <span>Analyzing...</span>
              <Button size="xs" variant="ghost" onClick={onCancel}>
                Cancel
              </Button>
            </div>
          ) : error ? (
            <div
              role="alert"
              className="flex items-center gap-2 text-xs text-destructive"
            >
              <span>{error.message}</span>
              {onGenerate ? (
                <Button
                  size="xs"
                  variant="ghost"
                  disabled={!canGenerate}
                  onClick={requestGenerate}
                >
                  Retry
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      </header>

      <div ref={setBody} className="min-h-0 flex-1">
        <ScrollArea className="h-full [&_[data-slot=scroll-area-viewport]>div]:block!">
          <div className="mx-auto flex w-full max-w-[560px] flex-col gap-0.5 px-4 py-3">
            {view === "enhanced" && generatedCount === 0 && !generating ? (
              <div className="flex flex-col items-start gap-2 py-6">
                <p className="text-sm text-muted-foreground">
                  Nothing generated yet
                </p>
                {generateButton("Generate notes")}
              </div>
            ) : (
              rows.map((segment) =>
                isGenerated(segment) ? (
                  <GeneratedRow
                    key={segment.id}
                    segment={segment}
                    onKeep={keepAsMine}
                  />
                ) : (
                  <UserRow
                    key={segment.id}
                    segment={segment}
                    placeholder={onlyEmptyRow ? "Write notes..." : undefined}
                    onTextChange={setText}
                  />
                )
              )
            )}
          </div>
        </ScrollArea>
      </div>

      <footer className="shrink-0 border-t">
        <div className="mx-auto flex w-full max-w-[560px] items-center justify-between gap-3 px-4 py-2">
          {generateButton(generatedCount > 0 ? "Regenerate" : "Generate")}
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span aria-hidden className="size-2.5 rounded-sm bg-foreground" />
              Yours
            </span>
            <span className="flex items-center gap-1.5">
              <span
                aria-hidden
                className="h-3 w-2.5 border-l-2 border-muted-foreground/60 bg-muted"
              />
              Generated
            </span>
          </div>
        </div>
      </footer>

      <div role="status" aria-live="polite" className="sr-only">
        {announcement}
      </div>
    </div>
  )
}
