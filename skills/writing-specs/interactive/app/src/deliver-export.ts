export type DeliveryResult = 'posted' | 'downloaded'

const COMPANION_PATH = '/_quirk/review'

function download(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  globalThis.setTimeout(() => URL.revokeObjectURL(url), 0)
}

/**
 * Hands an export to the brainstorming companion when this page is served by it, else downloads it.
 * Resolves 'posted' only on an HTTP 200 from the companion; any failure falls back to the download
 * so the reviewer never loses an export.
 */
export async function deliverExport(data: unknown, filename: string): Promise<DeliveryResult> {
  if (location.pathname === COMPANION_PATH) {
    try {
      const token = new URLSearchParams(location.search).get('t') ?? ''
      const response = await fetch(`${COMPANION_PATH}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Quirk-Token': token },
        body: JSON.stringify(data),
      })
      if (response.status === 200) return 'posted'
    } catch {
      // fall through to the download
    }
  }
  download(data, filename)
  return 'downloaded'
}
