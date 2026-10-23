import { useState } from "react"

/** Local edit buffer for a committed value; it resets whenever the committed value changes. */
export function useDraft(value: string) {
  const [draft, setDraft] = useState(value)
  const [seen, setSeen] = useState(value)
  if (seen !== value) {
    setSeen(value)
    setDraft(value)
  }
  return [draft, setDraft] as const
}
