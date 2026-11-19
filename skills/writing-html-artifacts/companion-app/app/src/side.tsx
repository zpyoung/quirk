import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'
import type { ChatEntry } from './types'

const STORAGE_KEY = 'quirk-side'
export const SIDE_MIN = 260
export const SIDE_MAX = 720
export const SIDE_DEFAULT = 320
const KEY_STEP = 16

export interface SideLayout {
  width: number
  collapsed: boolean
}

export function clampWidth(width: number): number {
  const viewportCap = typeof window === 'undefined' ? SIDE_MAX : Math.floor(window.innerWidth * 0.5)
  return Math.round(Math.max(SIDE_MIN, Math.min(width, SIDE_MAX, Math.max(SIDE_MIN, viewportCap))))
}

function readLayout(): SideLayout {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : null
    if (parsed && typeof parsed.width === 'number') return { width: clampWidth(parsed.width), collapsed: Boolean(parsed.collapsed) }
  } catch {
    // storage blocked or malformed: fall back to the default layout
  }
  return { width: SIDE_DEFAULT, collapsed: false }
}

function writeLayout(layout: SideLayout): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(layout))
  } catch {
    // a viewer convenience only; the layout still works for this page load
  }
}

/** The side panel's width and collapsed state, remembered per browser. */
export function useSideLayout() {
  const [layout, setLayout] = useState<SideLayout>(readLayout)
  useEffect(() => writeLayout(layout), [layout])
  return {
    layout,
    setWidth: (width: number) => setLayout((l) => ({ ...l, width: clampWidth(width) })),
    toggle: () => setLayout((l) => ({ ...l, collapsed: !l.collapsed })),
  }
}

/** Agent messages that arrived while the panel was hidden, so a collapsed panel never hides the agent's voice. */
function useUnread(chat: ChatEntry[], collapsed: boolean): number {
  const lastSeq = chat.reduce((max, entry) => Math.max(max, entry.seq), 0)
  const seen = useRef(lastSeq)
  if (!collapsed) seen.current = lastSeq
  return collapsed ? chat.filter((entry) => entry.from === 'agent' && entry.seq > seen.current).length : 0
}

interface SidePanelProps {
  chat: ChatEntry[]
  layout: SideLayout
  setWidth(width: number): void
  toggle(): void
  children: ReactNode
}

/**
 * The right-hand sidebar holding Chat and Decisions: collapsible to a slim strip and resizable by dragging its
 * left edge (or with the arrow keys on that edge). Children stay mounted while collapsed so a half-typed
 * message survives.
 */
export function SidePanel({ chat, layout, setWidth, toggle, children }: SidePanelProps) {
  const unread = useUnread(chat, layout.collapsed)
  const drag = useRef<{ startX: number; startWidth: number } | null>(null)

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    event.preventDefault()
    drag.current = { startX: event.clientX, startWidth: layout.width }
    event.currentTarget.setPointerCapture(event.pointerId)
    document.body.dataset.resizing = 'side'
  }
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return
    setWidth(drag.current.startWidth + (drag.current.startX - event.clientX))
  }
  const endDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return
    drag.current = null
    event.currentTarget.releasePointerCapture(event.pointerId)
    delete document.body.dataset.resizing
  }
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, number> = {
      ArrowLeft: layout.width + KEY_STEP,
      ArrowRight: layout.width - KEY_STEP,
      Home: SIDE_MAX,
      End: SIDE_MIN,
    }
    if (!(event.key in moves)) return
    event.preventDefault()
    setWidth(moves[event.key])
  }

  if (layout.collapsed) {
    return (
      <aside className="side" aria-label="Session" data-collapsed="true">
        <button type="button" className="side-toggle side-expand" aria-expanded="false" onClick={toggle}>
          <span aria-hidden="true">&#x2039;</span>
          <span className="side-expand-label">Chat and decisions</span>
          {unread ? (
            <span className="side-unread" aria-label={`${unread} new message${unread === 1 ? '' : 's'}`}>
              {unread}
            </span>
          ) : null}
        </button>
        <div hidden>{children}</div>
      </aside>
    )
  }

  return (
    <aside className="side" aria-label="Session">
      <div
        className="side-resize"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize the chat and decisions panel"
        aria-valuemin={SIDE_MIN}
        aria-valuemax={SIDE_MAX}
        aria-valuenow={layout.width}
        tabIndex={0}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={onKeyDown}
        onDoubleClick={() => setWidth(SIDE_DEFAULT)}
      />
      <div className="side-head">
        <button type="button" className="link-button side-toggle" aria-expanded="true" onClick={toggle}>
          Hide panel <span aria-hidden="true">&#x203A;</span>
        </button>
      </div>
      {children}
    </aside>
  )
}
