import {
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
  type Ref,
} from "react"
import { Trash2Icon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import { ConfirmDialog } from "./confirm-dialog"
import { displayValue, textOf, valueOf, type Field, type Rec } from "./fields"

const EMPTY = "__empty__"

function PropertyRow({
  field,
  item,
  editable,
  onChange,
}: {
  field: Field
  item: Rec
  editable: boolean
  onChange(value: string | number | undefined): void
}) {
  const id = useId()
  const raw = valueOf(item, field.key)
  const text = textOf(raw)

  let control: ReactNode
  if (!editable) {
    const shown = displayValue(field, raw)
    control = shown ? (
      <span>{shown}</span>
    ) : (
      <span className="text-muted-foreground">Empty</span>
    )
  } else if (field.type === "select") {
    control = (
      <Select
        value={text || EMPTY}
        onValueChange={(v) => onChange(v === EMPTY ? undefined : v)}
      >
        <SelectTrigger id={id} size="sm" className="w-full">
          <SelectValue placeholder="Empty" />
        </SelectTrigger>
        <SelectContent position="popper">
          <SelectItem value={EMPTY}>Empty</SelectItem>
          {(field.options ?? []).map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  } else if (field.type === "date") {
    control = (
      <Input
        id={id}
        type="date"
        defaultValue={text}
        key={`${item.id}:${text}`}
        className="h-7 text-xs"
        onChange={(e) => onChange(e.target.value || undefined)}
      />
    )
  } else {
    const commit = (value: string) => {
      if (value === text) return
      if (field.type === "number")
        onChange(value === "" ? undefined : Number(value))
      else onChange(value === "" ? undefined : value)
    }
    control = (
      <Input
        id={id}
        type={field.type === "number" ? "number" : "text"}
        defaultValue={text}
        key={`${item.id}:${text}`}
        placeholder="Empty"
        className="h-7 text-xs"
        onBlur={(e) => {
          if (field.key === "title" && e.target.value.trim() === "")
            e.target.value = text
          else commit(e.target.value)
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur()
        }}
      />
    )
  }

  return (
    <>
      <dt className="pt-1.5 text-muted-foreground">
        <label htmlFor={editable ? id : undefined}>{field.label}</label>
      </dt>
      <dd className="min-w-0 break-words">{control}</dd>
    </>
  )
}

export interface RecordPanelProps {
  item: Rec
  /** Every field including the title. */
  fields: Field[]
  noun: string
  panelRef: Ref<HTMLElement>
  onClose(): void
  onUpdate?: (id: string, patch: Record<string, unknown>) => void
  onDelete?: (id: string) => void
  renderPanel?: (item: Rec, ctx: { close: () => void }) => ReactNode
}

/** Docked, non-modal detail for one record; focus lands on its title when the record changes. */
export function RecordPanel({
  item,
  fields,
  noun,
  panelRef,
  onClose,
  onUpdate,
  onDelete,
  renderPanel,
}: RecordPanelProps) {
  const titleRef = useRef<HTMLHeadingElement>(null)
  const [confirming, setConfirming] = useState(false)
  const deleteRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    titleRef.current?.focus()
  }, [item.id])

  return (
    <aside
      ref={panelRef}
      aria-label={`${noun} details`}
      className="absolute inset-0 z-20 flex min-w-0 flex-col border-l bg-card md:static md:inset-auto md:z-auto md:w-[35%] md:max-w-md md:min-w-64 md:shrink-0"
    >
      <div className="flex h-9 shrink-0 items-center justify-between px-3">
        <span className="text-xs text-muted-foreground capitalize">{noun}</span>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Close panel"
          onClick={onClose}
        >
          <XIcon />
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        <h2
          ref={titleRef}
          tabIndex={-1}
          data-panel-title=""
          className="mb-3 text-base font-semibold break-words outline-none"
        >
          {item.title}
        </h2>
        {renderPanel ? (
          renderPanel(item, { close: onClose })
        ) : (
          <dl className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-xs">
            {fields.map((field) => (
              <PropertyRow
                key={field.key}
                field={field}
                item={item}
                editable={Boolean(onUpdate)}
                onChange={(value) =>
                  onUpdate?.(item.id, { [field.key]: value })
                }
              />
            ))}
          </dl>
        )}
      </div>
      {onDelete ? (
        <div className="shrink-0 border-t p-2">
          <Button
            ref={deleteRef}
            variant="destructive"
            size="sm"
            onClick={() => setConfirming(true)}
          >
            <Trash2Icon />
            Delete
          </Button>
          <ConfirmDialog
            open={confirming}
            title={`Delete this ${noun}?`}
            description={`"${item.title}" will be removed. This can't be undone.`}
            confirmLabel="Delete"
            returnFocusRef={deleteRef}
            onOpenChange={setConfirming}
            onConfirm={() => onDelete(item.id)}
          />
        </div>
      ) : null}
    </aside>
  )
}
