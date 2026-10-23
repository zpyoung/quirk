import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { PlusIcon, Trash2Icon } from "lucide-react"
import { toast } from "sonner"

import { EmptyState } from "@/components/mini/states"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

import { Breadcrumb } from "./breadcrumb"
import { CollectionBlock } from "./collection-block"
import { columnClass } from "./column"
import { RecordPage } from "./record-page"
import type { DocPage, DocRecord } from "./types"
import { useDraft } from "./use-draft"

function scrollParentOf(element: HTMLElement | null): HTMLElement | null {
  for (let node = element?.parentElement; node; node = node.parentElement) {
    const overflow = getComputedStyle(node).overflowY
    if ((overflow === "auto" || overflow === "scroll") && node.scrollHeight > node.clientHeight) return node
  }
  return null
}

function reportSaveError(cause: unknown) {
  toast.error(`Could not save: ${cause instanceof Error ? cause.message : String(cause)}`)
}

function TextBlock({ text, onCommit }: { text: string; onCommit: (text: string) => void }) {
  const [draft, setDraft] = useDraft(text)
  return (
    <Textarea
      aria-label="Text block"
      placeholder="Write something"
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={() => {
        if (draft !== text) onCommit(draft)
      }}
      className="my-1 min-h-8 resize-none border-transparent px-1.5 py-1 shadow-none hover:border-input focus-visible:border-ring dark:bg-transparent"
    />
  )
}

function PageTitle({ title, onCommit }: { title: string; onCommit: (title: string) => void }) {
  const [draft, setDraft] = useDraft(title)
  return (
    <Input
      aria-label="Page title"
      data-mini="title"
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={() => {
        const next = draft.trim()
        if (next === "" || next === title) setDraft(title)
        else onCommit(next)
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur()
      }}
      className="mb-2 h-auto border-transparent px-1.5 py-1 text-2xl font-semibold shadow-none hover:border-input focus-visible:border-ring md:text-2xl dark:bg-transparent"
    />
  )
}

/**
 * A page of text and collection blocks. Opening a record replaces the page with that record until it is closed;
 * closing restores the scroll position and puts focus back on the row that was opened.
 * The app owns storage: `page` and `records` are controlled, and rejected writes are shown as a toast.
 * Leave `openId` undefined to let the component track the open record itself.
 */
export function DocCollections<T extends DocRecord>({
  page,
  onPageChange,
  records,
  onAdd,
  onUpdate,
  onRemove,
  openId,
  onOpenChange,
}: {
  page: DocPage
  onPageChange: (page: DocPage) => void
  records: T[]
  onAdd: (collectionId: string) => Promise<T>
  onUpdate: (id: string, patch: Partial<T>) => Promise<void>
  onRemove: (id: string) => Promise<void>
  openId?: string | null
  onOpenChange?: (id: string | null) => void
}) {
  const [ownOpenId, setOwnOpenId] = useState<string | null>(null)
  const [selection, setSelection] = useState<Record<string, string>>({})
  const currentId = openId === undefined ? ownOpenId : openId
  const open = currentId === null ? undefined : records.find((record) => record.id === currentId)

  const rootRef = useRef<HTMLDivElement>(null)
  const saved = useRef<{ element: HTMLElement; top: number } | null>(null)
  const lastOpened = useRef<{ collectionId: string; id: string } | null>(null)
  const focusTitleFor = useRef<string | null>(null)
  const wasOpen = useRef(false)

  const setOpen = (id: string | null) => {
    if (openId === undefined) setOwnOpenId(id)
    onOpenChange?.(id)
  }

  const openRecord = (collectionId: string, id: string) => {
    const element = scrollParentOf(rootRef.current)
    saved.current = element ? { element, top: element.scrollTop } : null
    setSelection((current) => ({ ...current, [collectionId]: id }))
    setOpen(id)
  }

  const addRecord = async (collectionId: string) => {
    try {
      const created = await onAdd(collectionId)
      focusTitleFor.current = created.id
      openRecord(collectionId, created.id)
    } catch (cause) {
      reportSaveError(cause)
    }
  }

  const updateOpen = async (patch: Partial<T>) => {
    if (!open) return
    try {
      await onUpdate(open.id, patch)
    } catch (cause) {
      reportSaveError(cause)
      throw cause
    }
  }

  const removeOpen = async () => {
    if (!open) return
    try {
      await onRemove(open.id)
      setOpen(null)
    } catch (cause) {
      reportSaveError(cause)
    }
  }

  const openDef = open ? page.collections.find((def) => def.id === open.collectionId) : undefined
  const isOpen = open !== undefined && openDef !== undefined
  useLayoutEffect(() => {
    if (isOpen && !wasOpen.current && saved.current) saved.current.element.scrollTop = 0
    if (!isOpen && wasOpen.current) {
      if (saved.current) saved.current.element.scrollTop = saved.current.top
      const last = lastOpened.current
      if (last) {
        rootRef.current
          ?.querySelector<HTMLElement>(`[data-collection-id="${CSS.escape(last.collectionId)}"]`)
          ?.focus({ preventScroll: true })
      }
    }
    wasOpen.current = isOpen
  }, [isOpen])

  useEffect(() => {
    if (!open) return
    lastOpened.current = { collectionId: open.collectionId, id: open.id }
    if (focusTitleFor.current === open.id) {
      focusTitleFor.current = null
      const title = rootRef.current?.querySelector<HTMLTextAreaElement>("[data-record-title]")
      title?.focus()
      title?.select()
    }
  }, [open])

  const patchBlocks = (blocks: DocPage["blocks"]) => onPageChange({ ...page, blocks })

  const addText = () => patchBlocks([...page.blocks, { id: crypto.randomUUID(), kind: "text", text: "" }])

  const addCollection = () => {
    const collectionId = crypto.randomUUID()
    onPageChange({
      ...page,
      collections: [
        ...page.collections,
        {
          id: collectionId,
          name: `Collection ${page.collections.length + 1}`,
          fields: [{ key: "notes", label: "Notes", type: "text" }],
        },
      ],
      blocks: [...page.blocks, { id: crypto.randomUUID(), kind: "collection", collectionId }],
    })
  }

  return (
    <div ref={rootRef}>
      {open && openDef ? (
        <>
          <RecordPage
            record={open}
            fields={openDef.fields}
            onUpdate={updateOpen}
            onClose={() => setOpen(null)}
            trail={[page.title, openDef.name, open.title]}
          />
          <div className={columnClass}>
            <Button variant="ghost" size="sm" onClick={removeOpen} className="text-muted-foreground">
              <Trash2Icon aria-hidden /> Delete record
            </Button>
          </div>
        </>
      ) : (
        <>
          <Breadcrumb trail={[page.title]} />
          <div className={`${columnClass} py-6`}>
            <PageTitle title={page.title} onCommit={(title) => onPageChange({ ...page, title })} />
            {page.blocks.length === 0 ? (
              <EmptyState
                title="Empty page"
                description="Add some text, or a collection of records."
                action={
                  <div className="flex gap-2">
                    <Button size="sm" onClick={addText}>
                      <PlusIcon aria-hidden /> Add text
                    </Button>
                    <Button size="sm" variant="outline" onClick={addCollection}>
                      <PlusIcon aria-hidden /> Add collection
                    </Button>
                  </div>
                }
              />
            ) : (
              <>
                {page.blocks.map((block) => {
                  if (block.kind === "text") {
                    return (
                      <TextBlock
                        key={block.id}
                        text={block.text}
                        onCommit={(text) =>
                          patchBlocks(page.blocks.map((b) => (b.id === block.id ? { ...block, text } : b)))
                        }
                      />
                    )
                  }
                  const def = page.collections.find((c) => c.id === block.collectionId)
                  if (!def) return null
                  return (
                    <CollectionBlock
                      key={block.id}
                      def={def}
                      records={records.filter((record) => record.collectionId === def.id)}
                      selectedId={selection[def.id]}
                      onSelect={(id) => setSelection((current) => ({ ...current, [def.id]: id }))}
                      onOpen={(id) => openRecord(def.id, id)}
                      onAdd={() => void addRecord(def.id)}
                    />
                  )
                })}
                <div className="mt-4 flex gap-2">
                  <Button variant="ghost" size="sm" onClick={addText}>
                    <PlusIcon aria-hidden /> Add text
                  </Button>
                  <Button variant="ghost" size="sm" onClick={addCollection}>
                    <PlusIcon aria-hidden /> Add collection
                  </Button>
                </div>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
