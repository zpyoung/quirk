import { useEffect, useState } from "react"

import styles from "@/gallery/style-list.json"

const STORAGE_KEY = "mini-style"
const DEFAULT_SLUG = "neutral-house"

const isKnown = (slug: string | null): slug is string =>
  slug !== null && styles.some((s) => s.slug === slug)

function readStored() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return isKnown(stored) ? stored : DEFAULT_SLUG
  } catch {
    return DEFAULT_SLUG
  }
}

function applyStyle(slug: string) {
  const root = document.documentElement
  if (slug === DEFAULT_SLUG) delete root.dataset.miniStyle
  else root.dataset.miniStyle = slug
}

/** Switches the gallery's visual style; the choice persists across reloads. */
export function StylePicker() {
  const [slug, setSlug] = useState(readStored)

  useEffect(() => {
    applyStyle(slug)
  }, [slug])

  const onChange = (next: string) => {
    setSlug(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // storage unavailable: the choice still applies for this session
    }
  }

  return (
    <select
      aria-label="Style"
      value={slug}
      onChange={(e) => onChange(e.target.value)}
      className="h-7 rounded-md border border-input bg-background px-2 text-xs text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {styles.map((s) => (
        <option key={s.slug} value={s.slug}>
          {s.name}
        </option>
      ))}
    </select>
  )
}
