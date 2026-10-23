import { useEffect, useRef, useState } from "react"
import { useHotkeys } from "react-hotkeys-hook"
import { XIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Textarea } from "@/components/ui/textarea"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import type { ExpandField, ExpandItem } from "./types"

const bareTextarea =
  "min-h-0 resize-none rounded-none border-0 bg-transparent p-0 text-sm shadow-none focus-visible:ring-0 dark:bg-transparent"

/**
 * The open editing card for one item: title, notes, a row per filled field and
 * an icon strip for the empty ones. Edits are reported through `onChange` as
 * they are typed. Esc and Cmd/Ctrl+Enter call `onClose`, including while
 * typing in the card; Esc leaves an open field popover to close first.
 */
export function ExpandCard<T extends ExpandItem>({
  item,
  fields,
  onChange,
  onClose,
}: {
  item: T
  fields: ExpandField<T>[]
  onChange(patch: Partial<T>): void
  onClose(): void
}) {
  // typing is mirrored locally because the store round-trips asynchronously and would drop keystrokes
  const [title, setTitle] = useState(item.title)
  const [notes, setNotes] = useState(item.notes ?? "")
  const [activeKey, setActiveKey] = useState<string | null>(null)
  const [entered, setEntered] = useState(false)
  const [settled, setSettled] = useState(false)
  const titleRef = useRef<HTMLTextAreaElement>(null)
  const notesRef = useRef<HTMLTextAreaElement>(null)
  const cardRef = useRef<HTMLDivElement>(null)
  const activeKeyRef = useRef<string | null>(null)
  // the field's icon turns into a row once it is filled, so the popover re-reads its anchor on every frame
  const anchorRef = useRef({
    getBoundingClientRect: () => {
      const card = cardRef.current
      const key = activeKeyRef.current
      const target =
        card?.querySelector(`[data-field-anchor="${CSS.escape(key ?? "")}"]`) ?? card
      return (target ?? document.body).getBoundingClientRect()
    },
  })

  const collapseKeys = { enableOnFormTags: true, enableOnContentEditable: true } as const
  useHotkeys("escape", (event) => {
    if (!event.defaultPrevented) onClose()
  }, collapseKeys)
  useHotkeys("mod+enter", onClose, { ...collapseKeys, preventDefault: true })

  useEffect(() => {
    const field = titleRef.current
    if (field) {
      field.focus()
      field.setSelectionRange(field.value.length, field.value.length)
    }
    const frame = requestAnimationFrame(() => setEntered(true))
    const timer = window.setTimeout(() => {
      setSettled(true)
      cardRef.current?.scrollIntoView({ block: "nearest" })
    }, 170)
    return () => {
      cancelAnimationFrame(frame)
      window.clearTimeout(timer)
    }
  }, [])

  function openEditor(key: string) {
    const next = activeKeyRef.current === key ? null : key
    activeKeyRef.current = next
    setActiveKey(next)
  }

  function closeEditor() {
    activeKeyRef.current = null
    setActiveKey(null)
  }

  const filled = fields.filter((field) => field.isSet(item))
  const empty = fields.filter((field) => !field.isSet(item))
  const activeField = fields.find((field) => field.key === activeKey)

  return (
    <div
      className={cn(
        "grid transition-[grid-template-rows] duration-150 ease-out motion-reduce:transition-none",
        entered ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
      )}
    >
      <div className={cn("min-h-0", !settled && "overflow-hidden")}>
        <div
          ref={cardRef}
          role="group"
          aria-label={`Edit ${item.title || "new item"}`}
          className="-mx-3.5 my-1.5 flex flex-col gap-2 rounded-xl bg-card p-3 text-card-foreground shadow-md"
        >
          <ScrollArea className="[&_[data-radix-scroll-area-viewport]]:max-h-[70svh] [&_[data-radix-scroll-area-viewport]>div]:block!">
            <div className="flex flex-col gap-1.5">
              <div className="flex items-start gap-2.5">
                <Checkbox
                  className="mt-0.5"
                  aria-label="Done"
                  checked={item.done === true}
                  onCheckedChange={(checked) =>
                    onChange({ done: checked === true } as Partial<T>)
                  }
                />
                <Textarea
                  ref={titleRef}
                  aria-label="Title"
                  placeholder="New item"
                  rows={1}
                  value={title}
                  className={cn(bareTextarea, "font-medium")}
                  onChange={(event) => {
                    setTitle(event.target.value)
                    onChange({ title: event.target.value } as Partial<T>)
                  }}
                  onKeyDown={(event) => {
                    if (event.key !== "Enter" || event.shiftKey || event.metaKey || event.ctrlKey) return
                    if (event.nativeEvent.isComposing) return
                    event.preventDefault()
                    notesRef.current?.focus()
                  }}
                />
              </div>
              <Textarea
                ref={notesRef}
                aria-label="Notes"
                placeholder="Notes"
                rows={1}
                value={notes}
                className={cn(bareTextarea, "ml-[26px] w-[calc(100%-26px)] text-muted-foreground")}
                onChange={(event) => {
                  setNotes(event.target.value)
                  onChange({ notes: event.target.value } as Partial<T>)
                }}
              />
              {filled.map((field) => (
                <div
                  key={field.key}
                  data-field-anchor={field.key}
                  className="group/field ml-[26px] flex items-center gap-1 rounded-md hover:bg-muted/60"
                >
                  <button
                    type="button"
                    aria-haspopup="dialog"
                    aria-expanded={activeKey === field.key}
                    onClick={() => openEditor(field.key)}
                    className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-1 py-0.5 text-left text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
                  >
                    <span aria-hidden className="text-muted-foreground [&_svg]:size-3.5">
                      {field.icon}
                    </span>
                    <span className="text-muted-foreground">{field.label}:</span>
                    <Badge variant="secondary" className="max-w-full truncate">
                      {field.display(item)}
                    </Badge>
                  </button>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label={`Clear ${field.label}`}
                    className="opacity-0 group-hover/field:opacity-100 focus-visible:opacity-100"
                    onClick={() => {
                      onChange(field.clear(item))
                      if (activeKey === field.key) closeEditor()
                      titleRef.current?.focus()
                    }}
                  >
                    <XIcon />
                  </Button>
                </div>
              ))}
            </div>
          </ScrollArea>
          {empty.length > 0 ? (
            <div className="flex justify-end gap-0.5">
              {empty.map((field) => (
                <Tooltip key={field.key}>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      data-field-anchor={field.key}
                      aria-label={`Add ${field.label}`}
                      aria-haspopup="dialog"
                      aria-expanded={activeKey === field.key}
                      onClick={() => openEditor(field.key)}
                    >
                      {field.icon}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{field.label}</TooltipContent>
                </Tooltip>
              ))}
            </div>
          ) : null}
        </div>
      </div>
      <Popover open={activeField !== undefined} onOpenChange={(open) => !open && closeEditor()}>
        <PopoverAnchor virtualRef={anchorRef} />
        <PopoverContent
          align="start"
          aria-label={activeField?.label}
          className="w-auto"
          updatePositionStrategy="always"
          onCloseAutoFocus={(event) => {
            event.preventDefault()
            if (titleRef.current?.isConnected) titleRef.current.focus()
          }}
          onInteractOutside={(event) => {
            // lets the field's own button toggle the editor instead of closing and instantly reopening it
            if ((event.target as Element).closest("[data-field-anchor]")) event.preventDefault()
          }}
        >
          {activeField ? (
            <activeField.Editor
              key={activeField.key}
              item={item}
              onChange={onChange}
              onClose={closeEditor}
            />
          ) : null}
        </PopoverContent>
      </Popover>
    </div>
  )
}
