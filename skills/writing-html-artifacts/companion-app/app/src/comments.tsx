import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Button } from '@astryxdesign/core/Button'
import { Md } from './blocks'
import { isValidBlockId, nodeBlockId, resolutionLabel, threadsByBlock, threadsForBlock } from './comments-model'
import type { Actions, Thread } from './types'

const MAX_TEXT = 4000
const HIDE_DELAY_MS = 300
const BLOCK_SELECTOR = '[data-q-flow-node],[data-q-schema-entity],[data-commentable],[data-block-id]'
const FOCUSABLE = 'a[href],button,input,select,textarea,summary,[tabindex],[contenteditable="true"]'

/** Block id carried by `el` (agent `data-commentable` wins over the shell's `data-block-id`), or null when it has none the server would accept. */
export function blockIdOf(el: Element, stepId: string, diagrams: Element[]): string | null {
  const nodeId = el.getAttribute('data-q-flow-node') ?? el.getAttribute('data-q-schema-entity')
  if (nodeId !== null) {
    const host = el.closest('q-flow, q-schema')
    const index = host ? diagrams.indexOf(host) : -1
    const id = nodeBlockId(stepId, index, nodeId)
    return index >= 0 && isValidBlockId(id) ? id : null
  }
  const id = el.getAttribute('data-commentable') ?? el.getAttribute('data-block-id')
  return id !== null && isValidBlockId(id) ? id : null
}

/** Every commentable element under `root`, keyed by block id; the first element wins when an id repeats. */
function collectBlocks(root: Element, stepId: string): Map<string, Element> {
  const diagrams = [...root.querySelectorAll('q-flow, q-schema')]
  const out = new Map<string, Element>()
  for (const el of root.querySelectorAll(BLOCK_SELECTOR)) {
    const id = blockIdOf(el, stepId, diagrams)
    if (id && !out.has(id)) out.set(id, el)
  }
  return out
}

/** Gives a commentable block keyboard focus only when it has no focusable part of its own, so existing controls are untouched. */
function makeFocusable(root: Element): void {
  for (const el of root.querySelectorAll('[data-commentable],[data-block-id]')) {
    if (el.matches(FOCUSABLE) || el.querySelector(FOCUSABLE)) continue
    el.setAttribute('tabindex', '0')
  }
}

interface CommentsApi {
  /** Opens the thread popover for thread `threadId`, scrolling its block into view. */
  openThread(threadId: string): void
  /** Ref for the element whose subtree holds the commentable blocks of the current step. */
  rootRef(el: HTMLElement | null): void
}

const noop: CommentsApi = { openThread() {}, rootRef() {} }
const CommentsContext = createContext<CommentsApi>(noop)
export const useComments = (): CommentsApi => useContext(CommentsContext)

interface Open {
  blockId: string
  threadId?: string
}

export interface CommentsProviderProps {
  threads: Thread[]
  stepId: string | null
  actions: Actions
  children: ReactNode
}

/**
 * Owns comment pins, count badges and the thread popover. All of them render in an overlay portal on
 * `document.body`, positioned beside the block, so no control is ever nested inside an option card.
 */
export function CommentsProvider({ threads, stepId, actions, children }: CommentsProviderProps) {
  const [root, setRoot] = useState<HTMLElement | null>(null)
  const [mounted, setMounted] = useState(false)
  const [target, setTarget] = useState<string | null>(null)
  const [open, setOpen] = useState<Open | null>(null)
  const [, setTick] = useState(0)
  const hideTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const threadsRef = useRef(threads)
  threadsRef.current = threads
  const step = stepId ?? ''

  useEffect(() => setMounted(true), [])

  const cancelHide = useCallback(() => clearTimeout(hideTimer.current), [])
  const scheduleHide = useCallback(() => {
    clearTimeout(hideTimer.current)
    hideTimer.current = setTimeout(() => setTarget(null), HIDE_DELAY_MS)
  }, [])
  useEffect(() => () => clearTimeout(hideTimer.current), [])

  useEffect(() => {
    if (!root) return undefined
    const track = (event: Event) => {
      const from = event.target instanceof Element ? event.target : null
      const el = from?.closest(BLOCK_SELECTOR) ?? null
      const id = el && root.contains(el) ? blockIdOf(el, step, [...root.querySelectorAll('q-flow, q-schema')]) : null
      if (event.type === 'keydown') {
        const key = event as globalThis.KeyboardEvent
        if (id && key.altKey && key.code === 'KeyC') {
          key.preventDefault()
          cancelHide()
          setTarget(null)
          setOpen({ blockId: id })
        }
        return
      }
      if (event.type === 'mouseout' || event.type === 'focusout') {
        const next = (event as MouseEvent | FocusEvent).relatedTarget
        if (!(next instanceof Node && root.contains(next))) scheduleHide()
        return
      }
      if (id) {
        cancelHide()
        setTarget(id)
      } else if (event.type === 'mouseover') {
        scheduleHide()
      }
    }
    const types = ['mouseover', 'mouseout', 'focusin', 'focusout', 'click', 'keydown']
    for (const type of types) root.addEventListener(type, track, true)
    return () => {
      for (const type of types) root.removeEventListener(type, track, true)
    }
  }, [root, step, cancelHide, scheduleHide])

  // pins follow their blocks through scrolling, resizing and agent HTML that builds its own DOM later
  useEffect(() => {
    if (!root) return undefined
    let frame = 0
    const bump = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => setTick((n) => n + 1))
    }
    makeFocusable(root)
    const observer = new MutationObserver(() => {
      makeFocusable(root)
      bump()
    })
    observer.observe(root, { childList: true, subtree: true })
    window.addEventListener('scroll', bump, true)
    window.addEventListener('resize', bump)
    bump()
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      window.removeEventListener('scroll', bump, true)
      window.removeEventListener('resize', bump)
    }
  }, [root, step])

  useEffect(() => {
    setTarget(null)
  }, [step])

  const blocks = root && mounted ? collectBlocks(root, step) : new Map<string, Element>()
  const rootNow = root
  const openThread = useCallback(
    (threadId: string) => {
      const thread = threadsRef.current.find((t) => t.id === threadId)
      if (!thread) return
      const el = rootNow ? collectBlocks(rootNow, step).get(thread.block_id) : undefined
      if (el) el.scrollIntoView({ block: 'center', behavior: 'auto' })
      setTarget(null)
      setOpen({ blockId: thread.block_id, threadId })
    },
    [rootNow, step],
  )
  const api = useMemo<CommentsApi>(() => ({ openThread, rootRef: setRoot }), [openThread])

  const byBlock = threadsByBlock(threads)
  const rectOf = (id: string): DOMRect | null => {
    const el = blocks.get(id)
    if (!el || !el.isConnected) return null
    const rect = el.getBoundingClientRect()
    return rect.width || rect.height ? rect : null
  }
  const visible = (rect: DOMRect) => rect.bottom > 24 && rect.top < window.innerHeight - 24

  let overlay: ReactNode = null
  if (mounted) {
    const badges = [...byBlock.entries()].flatMap(([id, list]) => {
      const rect = rectOf(id)
      if (!rect || !visible(rect)) return []
      const style: CSSProperties = { left: rect.left, top: Math.max(rect.top, 0) }
      return [
        <button
          key={id}
          type="button"
          className="comment-badge"
          data-for-block={id}
          style={style}
          aria-label={`${list.length} comment thread${list.length === 1 ? '' : 's'} on ${id}`}
          onClick={() => setOpen({ blockId: id })}
        >
          {list.length}
        </button>,
      ]
    })
    const pinRect = target && open?.blockId !== target ? rectOf(target) : null
    const pin =
      target && pinRect && visible(pinRect) ? (
        <button
          type="button"
          className="comment-pin"
          data-for-block={target}
          style={{ left: pinRect.right, top: Math.max(pinRect.top, 0) }}
          title="Comment on this block (Alt+C)"
          onMouseEnter={cancelHide}
          onMouseLeave={scheduleHide}
          onFocus={cancelHide}
          onClick={() => {
            setTarget(null)
            setOpen({ blockId: target })
          }}
        >
          Comment
        </button>
      ) : null
    const popover = open ? (
      <ThreadPopover
        key={`${open.blockId}:${open.threadId ?? ''}`}
        blockId={open.blockId}
        threads={threadsForBlock(threads, open.blockId)}
        initialThreadId={open.threadId}
        rect={rectOf(open.blockId)}
        onSend={(payload) => actions.send('comment', payload)}
        onClose={() => {
          const el = blocks.get(open.blockId)
          setOpen(null)
          if (el instanceof HTMLElement || el instanceof SVGElement) el.focus({ preventScroll: true })
        }}
      />
    ) : null
    overlay = createPortal(
      <div className="comment-overlay">
        {badges}
        {pin}
        {popover}
      </div>,
      document.body,
    )
  }

  return (
    <CommentsContext.Provider value={api}>
      {children}
      {overlay}
    </CommentsContext.Provider>
  )
}

function Message({ from, text }: { from: string; text: string }) {
  return (
    <div className="thread-message" data-from={from}>
      <span className="thread-from">{from === 'agent' ? 'Agent' : 'You'}</span>
      {from === 'agent' ? <Md source={text} className="thread-text" /> : <p className="thread-text">{text}</p>}
    </div>
  )
}

/** Threads with their messages in order: user text as text, agent replies as markdown, and the resolution when set. */
export function ThreadList({ threads }: { threads: Thread[] }) {
  return (
    <ol className="thread-list">
      {threads.map((thread, i) => (
        <li key={thread.id} className="thread" data-thread-id={thread.id}>
          {threads.length > 1 ? <p className="thread-title">Thread {i + 1}</p> : null}
          {thread.messages.map((message, j) => (
            <Message key={j} from={message.from} text={message.text} />
          ))}
          {thread.resolution ? (
            <p className="thread-resolution" data-resolution={thread.resolution}>
              {resolutionLabel(thread.resolution)}
            </p>
          ) : null}
        </li>
      ))}
    </ol>
  )
}

interface ThreadPopoverProps {
  blockId: string
  threads: Thread[]
  initialThreadId?: string
  rect: DOMRect | null
  onSend(payload: Record<string, unknown>): Promise<'ok' | 'superseded' | 'error'>
  onClose(): void
}

const NEW_THREAD = 'new'

function ThreadPopover({ blockId, threads, initialThreadId, rect, onSend, onClose }: ThreadPopoverProps) {
  const fieldId = useId()
  const [text, setText] = useState('')
  const [choice, setChoice] = useState<string | null>(initialThreadId ?? null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const field = useRef<HTMLTextAreaElement>(null)
  useEffect(() => field.current?.focus({ preventScroll: true }), [])

  const valid = (id: string | null) => id === NEW_THREAD || threads.some((t) => t.id === id)
  const selected = choice && valid(choice) ? choice : (threads.at(-1)?.id ?? NEW_THREAD)

  const send = async () => {
    if (busy || !text.trim()) return
    setBusy(true)
    setError(null)
    const payload: Record<string, unknown> = { block_id: blockId, text: text.trim() }
    if (selected !== NEW_THREAD) payload.thread_id = selected
    const result = await onSend(payload)
    setBusy(false)
    if (result === 'error') {
      setError('Could not send your comment. Check the connection and try again.')
      return
    }
    setText('')
    setChoice(null)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation()
      onClose()
    }
  }

  const margin = 8
  const width = 340
  const style: CSSProperties = rect
    ? {
        left: Math.min(Math.max(margin, rect.left), Math.max(margin, window.innerWidth - width - margin)),
        top: Math.min(Math.max(margin, rect.bottom + margin), Math.max(margin, window.innerHeight - 220)),
      }
    : { right: 16, top: 80 }

  return (
    <div className="thread-popover" role="dialog" aria-label={`Comments on ${blockId}`} style={style} onKeyDown={onKeyDown}>
      <div className="thread-head">
        <span className="thread-block">{blockId}</span>
        <button type="button" className="link-button" onClick={onClose}>
          Close
        </button>
      </div>
      {!rect ? <p className="muted">This block is not on the current step.</p> : null}
      {threads.length ? <ThreadList threads={threads} /> : <p className="muted">No comments here yet.</p>}
      {threads.length ? (
        <div className="field">
          <label htmlFor={`${fieldId}-to`}>Post to</label>
          <select id={`${fieldId}-to`} value={selected} onChange={(event) => setChoice(event.target.value)}>
            {threads.map((thread, i) => (
              <option key={thread.id} value={thread.id}>
                Thread {i + 1}
              </option>
            ))}
            <option value={NEW_THREAD}>New thread</option>
          </select>
        </div>
      ) : null}
      <div className="field">
        <label htmlFor={fieldId}>Add a comment</label>
        <textarea
          id={fieldId}
          ref={field}
          rows={3}
          maxLength={MAX_TEXT}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
              event.preventDefault()
              void send()
            }
          }}
        />
      </div>
      <p className="form-error" role="alert" hidden={!error}>
        {error}
      </p>
      <div className="actions">
        <Button type="button" variant="primary" size="sm" label="Comment" isDisabled={busy || !text.trim()} onClick={() => void send()} />
      </div>
    </div>
  )
}
