import { useEffect, useId, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Button } from '@astryxdesign/core/Button'
import { Md } from './blocks'
import { useComments } from './comments'
import { isQueued, isThreadPointer } from './comments-model'
import type { Actions, ChatEntry } from './types'

const MAX_TEXT = 4000
const STICK_PX = 24

function Entry({ entry, onOpenThread }: { entry: ChatEntry; onOpenThread(threadId: string): void }) {
  if (isThreadPointer(entry)) {
    return (
      <li className="chat-entry" data-from="system">
        <button type="button" className="link-button chat-pointer" onClick={() => onOpenThread(entry.thread_id)}>
          Comment: {entry.text}
        </button>
      </li>
    )
  }
  if (entry.from === 'agent') {
    return (
      <li className="chat-entry" data-from="agent">
        <Md source={entry.text} className="chat-text" />
      </li>
    )
  }
  return (
    <li className="chat-entry" data-from={entry.from}>
      <p className="chat-text">{entry.text}</p>
      {isQueued(entry) ? <span className="chat-queued">Queued</span> : null}
    </li>
  )
}

/** The conversation with the agent: its messages as markdown, yours as text, and a composer that posts `chat` events. */
export function ChatPanel({ chat, actions }: { chat: ChatEntry[]; actions: Actions }) {
  const fieldId = useId()
  const { openThread } = useComments()
  const entries = useMemo(() => [...chat].sort((a, b) => a.seq - b.seq), [chat])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const log = useRef<HTMLDivElement>(null)
  const stuck = useRef(true)
  const last = entries.at(-1)?.seq

  useEffect(() => {
    const el = log.current
    if (el && stuck.current) el.scrollTop = el.scrollHeight
  }, [entries.length, last])

  const send = async () => {
    const message = text.trim()
    if (busy || !message) return
    setBusy(true)
    setError(null)
    const result = await actions.send('chat', { text: message })
    setBusy(false)
    if (result === 'error') {
      setError('Could not send your message. Check the connection and try again.')
      return
    }
    stuck.current = true
    setText('')
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    void send()
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      void send()
    }
  }

  return (
    <section className="panel chat" aria-label="Chat">
      <h2 className="panel-title">Chat</h2>
      <div
        ref={log}
        className="chat-log"
        role="log"
        aria-live="polite"
        aria-label="Conversation"
        onScroll={(event) => {
          const el = event.currentTarget
          stuck.current = el.scrollHeight - el.scrollTop - el.clientHeight < STICK_PX
        }}
      >
        {entries.length ? (
          <ul className="chat-list">
            {entries.map((entry) => (
              <Entry key={entry.seq} entry={entry} onOpenThread={openThread} />
            ))}
          </ul>
        ) : (
          <p className="muted">No messages yet.</p>
        )}
      </div>
      <form className="chat-form" onSubmit={onSubmit}>
        <label htmlFor={fieldId} className="visually-hidden">
          Message
        </label>
        <textarea
          id={fieldId}
          rows={2}
          maxLength={MAX_TEXT}
          value={text}
          placeholder="Message the agent"
          onChange={(event) => setText(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <p className="form-error" role="alert" hidden={!error}>
          {error}
        </p>
        <Button type="submit" variant="primary" size="sm" label="Send" isDisabled={busy || !text.trim()} />
      </form>
    </section>
  )
}
