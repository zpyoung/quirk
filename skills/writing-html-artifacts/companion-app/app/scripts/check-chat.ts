import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { ChatPanel } from '../src/chat'
import { ThreadList } from '../src/comments'
import { isValidBlockId, nodeBlockId, threadsForBlock, threadsByBlock } from '../src/comments-model'
import { ShellView } from '../src/shell'
import type { Actions, ChatEntry, Snapshot, Thread } from '../src/types'

const failures: string[] = []
const check = (ok: boolean, message: string) => {
  if (!ok) failures.push(message)
}

const actions: Actions = { submit: async () => 'ok', send: async () => 'ok', saveDraft: async () => 'ok' }
const entry = (seq: number, from: string, text: string, extra: Partial<ChatEntry> = {}): ChatEntry => ({
  seq,
  from,
  text,
  timestamp: '2026-01-01T00:00:00Z',
  delivered: false,
  ...extra,
})
const chatHtml = (chat: ChatEntry[]) => renderToStaticMarkup(createElement(ChatPanel, { chat, actions }))

// user text is text, never markup
{
  const html = chatHtml([entry(1, 'user', '<b>x</b> and <img src=x onerror=alert(1)>')])
  check(!/<b>/.test(html) && !/<img/.test(html), 'user chat text produced an element')
  check(html.includes('&lt;b&gt;x&lt;/b&gt;'), 'user chat text is not shown literally')
}

// agent messages are markdown with raw html off
{
  const html = chatHtml([entry(1, 'agent', 'Because **B** keeps undo. <script>alert(1)</script>', { delivered: true })])
  check(html.includes('<strong>B</strong>'), 'agent chat text is not rendered as markdown')
  check(!html.includes('<script>'), 'agent chat text let raw html through')
}

// Queued marks undelivered user messages only
{
  const queued = chatHtml([entry(1, 'user', 'hello', { delivered: false })])
  const sent = chatHtml([entry(1, 'user', 'hello', { delivered: true })])
  const agent = chatHtml([entry(1, 'agent', 'hello', { delivered: false })])
  check(queued.includes('Queued'), 'an undelivered user message has no Queued marker')
  check(!sent.includes('Queued'), 'a delivered user message still shows Queued')
  check(!agent.includes('Queued'), 'an agent message shows Queued')
}

// entries keep seq order and the log is a polite live region
{
  const html = chatHtml([entry(3, 'user', 'third'), entry(1, 'user', 'first'), entry(2, 'agent', 'second', { delivered: true })])
  check(html.indexOf('first') < html.indexOf('second') && html.indexOf('second') < html.indexOf('third'), 'chat is not in seq order')
  check(/role="log"/.test(html) && /aria-live="polite"/.test(html), 'chat log is not role=log with aria-live=polite')
}

// a thread pointer is one line link to the thread, never plain text
{
  const html = chatHtml([entry(1, 'system', 'Why is this slow?', { kind: 'thread', thread_id: 't-1', delivered: true })])
  check(/<button[^>]*class="[^"]*chat-pointer[^"]*"[^>]*>Comment: Why is this slow\?<\/button>/.test(html), 'a thread pointer is not rendered as a Comment: link button')
}

// composer
{
  const html = chatHtml([])
  check(/<textarea/.test(html), 'no chat textarea')
  check(/<button[^>]*\sdisabled[^>]*>[\s\S]*?Send/.test(html), 'Send is enabled for an empty message')
}

// block id derivation and thread filtering
check(nodeBlockId('step-1', 0, 'svc-a') === 'node:step-1/0/svc-a', 'node block id for diagram 0')
check(nodeBlockId('step-1', 2, 'users') === 'node:step-1/2/users', 'node block id for diagram 2')
check(isValidBlockId('approach:b') && isValidBlockId('node:s/0/a.b-c_d') && isValidBlockId('option:q/o'), 'a valid block id is rejected')
check(!isValidBlockId('') && !isValidBlockId('has space') && !isValidBlockId('a'.repeat(201)) && !isValidBlockId('x<y'), 'an invalid block id is accepted')

const thread = (id: string, block_id: string, step: string): Thread => ({ id, block_id, step, messages: [{ from: 'user', text: `on ${block_id}`, timestamp: 't' }] })
const threads = [thread('t1', 'approach:b', 'step-1'), thread('t2', 'approach:a', 'step-1'), thread('t3', 'approach:b', 'step-2')]
check(threadsForBlock(threads, 'approach:b').map((t) => t.id).join() === 't1,t3', 'threads are not filtered by block id across steps')
check(threadsForBlock(threads, 'approach:c').length === 0, 'a block with no threads has threads')
check(threadsByBlock(threads).get('approach:b')?.length === 2, 'threadsByBlock miscounts')

// thread list: text for users, markdown for agents, resolution label
{
  const withReply: Thread = {
    id: 't9',
    block_id: 'approach:b',
    step: 's',
    messages: [
      { from: 'user', text: '<i>why</i>', timestamp: 't' },
      { from: 'agent', text: 'Fixed in the **revision**', timestamp: 't' },
    ],
    resolution: 'addressed',
  }
  const html = renderToStaticMarkup(createElement(ThreadList, { threads: [withReply, { ...withReply, id: 't10', resolution: 'not-addressed' }] }))
  check(!/<i>/.test(html) && html.includes('&lt;i&gt;why&lt;/i&gt;'), 'a user comment produced an element')
  check(html.includes('<strong>revision</strong>'), 'an agent reply is not markdown')
  check(html.includes('Addressed') && html.includes('Not addressed'), 'resolution labels are missing')
  const open = renderToStaticMarkup(createElement(ThreadList, { threads: [{ ...withReply, resolution: undefined }] }))
  check(!open.includes('Addressed'), 'an unresolved thread shows a resolution label')
}

// the shell shows the chat panel above the Decisions panel
{
  const snap: Snapshot = {
    rev: 1, mode: 'app', step: null, step_state: 'open', status: null, stages: [{ id: 'context', state: 'current' }],
    decisions: [], chat: [entry(1, 'user', 'hi')], threads: [], review_registered: false,
  }
  const html = renderToStaticMarkup(createElement(ShellView, { snapshot: snap, token: 't', actions, paused: false, submittedStepId: null, openStage: null, onOpenStage: () => {} }))
  const chat = html.indexOf('role="log"')
  const decisions = html.indexOf('class="panel decisions"')
  check(chat !== -1 && decisions !== -1 && chat < decisions, 'the chat panel is not above the Decisions panel')
}

if (failures.length) {
  console.error(`chat-check failed:\n${failures.map((f) => `  - ${f}`).join('\n')}`)
  process.exitCode = 1
} else {
  console.log('chat-check passed: chat rendering, Queued marker, thread pointer, block ids and thread filtering.')
}
