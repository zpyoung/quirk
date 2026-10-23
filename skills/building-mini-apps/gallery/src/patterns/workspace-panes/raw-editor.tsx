import { useEffect, useRef, useState } from "react"

import { Textarea } from "@/components/ui/textarea"

const IDLE_COMMIT_MS = 600

/**
 * Plain-text view of a record's file. Calls `onCommit` with the draft on blur
 * and after 600 ms idle; `error` is the message to show when the parent
 * rejected the last commit, and the draft is kept as typed until it is fixed.
 */
export function RawEditor({
  value,
  onCommit,
  error,
}: {
  value: string
  onCommit: (raw: string) => void
  error?: string
}) {
  const [draft, setDraft] = useState(value)
  const [seen, setSeen] = useState(value)
  const [committed, setCommitted] = useState(value)
  const timer = useRef<number | undefined>(undefined)
  const latest = useRef({ draft, committed, onCommit })

  useEffect(() => {
    latest.current = { draft, committed, onCommit }
  })

  if (value !== seen) {
    setSeen(value)
    if (!error && (draft === seen || draft === committed)) setDraft(value)
  }

  function commit(raw: string) {
    window.clearTimeout(timer.current)
    timer.current = undefined
    if (!error && (raw === value || raw === committed)) return
    setCommitted(raw)
    onCommit(raw)
  }

  useEffect(
    () => () => {
      if (timer.current === undefined) return
      window.clearTimeout(timer.current)
      const { draft: pending, committed: sent, onCommit: flush } = latest.current
      if (pending !== sent) flush(pending)
    },
    []
  )

  return (
    <div className="flex h-full min-h-0 flex-col">
      <Textarea
        data-raw-editor
        aria-label="Raw file"
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? "raw-editor-error" : undefined}
        spellCheck={false}
        value={draft}
        onChange={(event) => {
          const next = event.target.value
          setDraft(next)
          window.clearTimeout(timer.current)
          timer.current = window.setTimeout(() => commit(next), IDLE_COMMIT_MS)
        }}
        onBlur={() => commit(draft)}
        onKeyDown={(event) => {
          if (event.key !== "Escape") return
          event.preventDefault()
          event.currentTarget.closest<HTMLElement>("[data-pane-body]")?.focus()
        }}
        className="min-h-0 flex-1 resize-none rounded-none border-0 p-4 font-mono text-xs leading-relaxed shadow-none focus-visible:ring-0"
      />
      {error ? (
        <p id="raw-editor-error" role="alert" className="border-t bg-destructive/10 px-4 py-2 text-xs text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  )
}
