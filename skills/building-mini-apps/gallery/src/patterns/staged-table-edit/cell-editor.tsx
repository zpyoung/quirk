import { useEffect, useRef, useState } from "react"
import { useHotkeys } from "react-hotkeys-hook"

import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

type EditorProps = {
  type: "text" | "number" | "select"
  options: string[]
  label: string
  value: string
  onDraft(text: string): void
  onAccept(text: string): void
  onNext(text: string): void
  onCancel(): void
}

const typing = { enableOnFormTags: true, preventDefault: true } as const

function TextLikeEditor({
  type,
  label,
  value,
  onDraft,
  onAccept,
  onNext,
  onCancel,
}: EditorProps) {
  const [text, setText] = useState(value)
  const field = useRef<HTMLInputElement & HTMLTextAreaElement>(null)
  const done = useRef(false)

  // blur fires after a keyboard accept removes the field; only the first exit counts
  const once = (exit: (text: string) => void) => () => {
    if (done.current) return
    done.current = true
    exit(text)
  }

  useEffect(() => {
    field.current?.focus()
    field.current?.select()
  }, [])

  useHotkeys("enter", once(onAccept), typing)
  useHotkeys("tab", once(onNext), typing)
  useHotkeys("esc", once(() => onCancel()), typing)

  const shared = {
    ref: field,
    value: text,
    "aria-label": label,
    onChange: (event: { target: { value: string } }) => {
      setText(event.target.value)
      onDraft(event.target.value)
    },
    onBlur: once(onAccept),
  }

  return type === "number" ? (
    <Input type="number" className="h-7 rounded-sm px-1.5" {...shared} />
  ) : (
    <textarea
      rows={1}
      className="field-sizing-content block min-h-7 w-full resize-none rounded-sm border border-input bg-background px-1.5 py-1 text-sm leading-5 outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50"
      {...shared}
    />
  )
}

function SelectEditor({ options, label, value, onAccept, onCancel }: EditorProps) {
  const picked = useRef(false)
  return (
    <Select
      defaultOpen
      value={value}
      onValueChange={(next) => {
        picked.current = true
        onAccept(next)
      }}
      onOpenChange={(open) => {
        if (!open && !picked.current) onCancel()
      }}
    >
      <SelectTrigger size="sm" aria-label={label} className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option} value={option}>
            {option}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

/**
 * Inline editor for one cell. Return accepts, Tab accepts and asks for the
 * next cell, Esc cancels, and blur accepts. Text and number fields work from
 * the keyboard directly; a select opens its list and takes the picked option.
 */
export function CellEditor(props: EditorProps) {
  return props.type === "select" ? <SelectEditor {...props} /> : <TextLikeEditor {...props} />
}
