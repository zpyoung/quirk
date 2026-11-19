import type { ChatEntry, Thread } from './types'

/** The server's block id rule; a pin is never offered for an id it would reject. */
const BLOCK_ID = /^[A-Za-z0-9:/_.-]{1,200}$/

export function isValidBlockId(id: string): boolean {
  return BLOCK_ID.test(id)
}

/** Block id of node `nodeId` in the `diagramIndex`th q-flow or q-schema of step `stepId` (0-based, document order). */
export function nodeBlockId(stepId: string, diagramIndex: number, nodeId: string): string {
  return `node:${stepId}/${diagramIndex}/${nodeId}`
}

/** Threads on one block, in server order. Threads follow the block id, not the step, so a revised block keeps them. */
export function threadsForBlock(threads: Thread[], blockId: string): Thread[] {
  return threads.filter((thread) => thread.block_id === blockId)
}

export function threadsByBlock(threads: Thread[]): Map<string, Thread[]> {
  const out = new Map<string, Thread[]>()
  for (const thread of threads) {
    const list = out.get(thread.block_id)
    if (list) list.push(thread)
    else out.set(thread.block_id, [thread])
  }
  return out
}

/** A user message the agent has not yet read through `next`. */
export function isQueued(entry: ChatEntry): boolean {
  return entry.from === 'user' && !entry.delivered
}

export function isThreadPointer(entry: ChatEntry): entry is ChatEntry & { kind: 'thread'; thread_id: string } {
  return entry.from === 'system' && entry.kind === 'thread' && typeof entry.thread_id === 'string'
}

export function resolutionLabel(resolution: string): string {
  if (resolution === 'addressed') return 'Addressed'
  if (resolution === 'not-addressed') return 'Not addressed'
  return resolution
}
