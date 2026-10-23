import { useCallback, useEffect, useRef, useState } from "react"
import { useHotkeys } from "react-hotkeys-hook"

import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"

import { Breadcrumb } from "./breadcrumb"
import { columnClass } from "./column"
import { PropertyValue } from "./property-value"
import type { DocRecord, FieldDef, PropValue } from "./types"
import { useDraft } from "./use-draft"

const EDITABLE = "input, textarea, select, [contenteditable]"

/**
 * A record opened as a page: title, one editable row per field, then the free-text body.
 * Esc blurs the field being edited first, and closes the record when nothing is being edited.
 * A rejected `onUpdate` puts the edited field back to the stored value.
 */
export function RecordPage<T extends DocRecord>({
  record,
  fields,
  onUpdate,
  onClose,
  trail,
}: {
  record: T
  fields: FieldDef[]
  onUpdate: (patch: Partial<T>) => Promise<void>
  onClose: () => void
  trail: string[]
}) {
  const [revision, setRevision] = useState(0)
  const [title, setTitle] = useDraft(record.title)
  const [body, setBody] = useDraft(record.body)

  // props lag behind edits until each store write resolves, so writes compose from this buffer
  const latestProps = useRef<{ id: string; props: Record<string, PropValue>; pending: number } | null>(null)

  const save = (patch: Partial<T>) => {
    onUpdate(patch).catch(() => {
      setRevision((n) => n + 1)
      setTitle(record.title)
      setBody(record.body)
    })
  }

  const containerRef = useRef<HTMLDivElement | null>(null)
  const hotkeysRef = useHotkeys<HTMLDivElement>(
    "esc",
    () => {
      const active = document.activeElement
      if (active instanceof HTMLElement && active !== containerRef.current && active.matches(EDITABLE)) {
        active.blur()
        containerRef.current?.focus({ preventScroll: true })
        return
      }
      onClose()
    },
    { enableOnFormTags: true, enableOnContentEditable: true }
  )
  const setContainer = useCallback(
    (element: HTMLDivElement | null) => {
      containerRef.current = element
      hotkeysRef(element)
    },
    [hotkeysRef]
  )

  useEffect(() => {
    const container = containerRef.current
    if (container && !container.contains(document.activeElement)) container.focus({ preventScroll: true })
  }, [record.id])

  const commitTitle = () => {
    const next = title.trim()
    if (next === "" || next === record.title) setTitle(record.title)
    else save({ title: next } as Partial<T>)
  }

  const setProp = (key: string, value: PropValue) => {
    const current = latestProps.current?.id === record.id ? latestProps.current : null
    const inFlight = current !== null && current.pending > 0
    const base = inFlight ? current.props : record.props
    const previous = base[key] ?? null
    const entry = { id: record.id, props: { ...base, [key]: value }, pending: (inFlight ? current.pending : 0) + 1 }
    latestProps.current = entry
    onUpdate({ props: entry.props } as Partial<T>)
      .catch(() => {
        setRevision((n) => n + 1)
        const latest = latestProps.current
        if (latest && latest.id === entry.id && latest.props[key] === value) {
          latest.props = { ...latest.props, [key]: previous }
        }
      })
      .finally(() => {
        const latest = latestProps.current
        if (latest && latest.id === entry.id) latest.pending -= 1
      })
  }

  return (
    <div ref={setContainer} tabIndex={-1} role="region" aria-label={`Record: ${record.title}`} className="outline-none">
      <Breadcrumb trail={trail} onNavigate={onClose} />
      <div key={revision} className={`${columnClass} py-6`}>
        <Textarea
          data-record-title
          data-mini="title"
          rows={1}
          aria-label="Title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          onBlur={commitTitle}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault()
              event.currentTarget.blur()
            }
          }}
          className="min-h-0 resize-none border-transparent px-1.5 text-2xl font-semibold shadow-none md:text-2xl dark:bg-transparent"
        />
        <div className="mt-3 flex flex-col">
          {fields.map((field) => (
            <div key={field.key} className="grid min-h-[26px] grid-cols-2 items-center gap-2 text-sm">
              <span className="truncate px-1.5 text-muted-foreground">{field.label}</span>
              <PropertyValue field={field} value={record.props[field.key] ?? null} onChange={(value) => setProp(field.key, value)} />
            </div>
          ))}
        </div>
        <Separator className="my-4" />
        <Textarea
          aria-label="Body"
          placeholder="Write something"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          onBlur={() => {
            if (body === record.body) return
            save({ body } as Partial<T>)
          }}
          className="min-h-48 border-transparent px-1.5 shadow-none dark:bg-transparent"
        />
      </div>
    </div>
  )
}
