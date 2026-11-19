import type { Boot } from './types'

/** Reads the server-injected boot block; null when the page is opened as a file or there is no document. */
export function readBoot(): Boot | null {
  if (typeof document === 'undefined') return null
  const node = document.getElementById('quirk-companion-boot')
  if (!node?.textContent) return null
  try {
    const value: unknown = JSON.parse(node.textContent)
    if (value && typeof value === 'object') {
      const { token, session } = value as Record<string, unknown>
      if (typeof token === 'string' && token) return { token, session: typeof session === 'string' ? session : '' }
    }
  } catch {
    // a malformed block is treated like no block
  }
  return null
}
