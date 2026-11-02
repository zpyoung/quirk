import { deliverExport } from '../src/deliver-export'

const failures: string[] = []
const check = (label: string, ok: boolean) => { if (!ok) failures.push(label) }

type Call = { url: string; init: RequestInit }
const g = globalThis as Record<string, unknown>

interface Env {
  fetchCalls: Call[]
  downloads: string[]
  blobs: Blob[]
}

function setup(pathname: string, search: string, fetchImpl: (call: Call) => Promise<{ status: number; ok: boolean }>): Env {
  const env: Env = { fetchCalls: [], downloads: [], blobs: [] }
  g.location = { pathname, search }
  g.fetch = (url: string, init: RequestInit) => {
    const call = { url, init }
    env.fetchCalls.push(call)
    return fetchImpl(call)
  }
  g.document = {
    createElement: () => {
      const anchor = { href: '', download: '', click() { env.downloads.push(anchor.download) } }
      return anchor
    },
  }
  g.URL = Object.assign(function URL() {}, {
    createObjectURL: (blob: Blob) => { env.blobs.push(blob); return 'blob:stub' },
    revokeObjectURL: () => {},
  })
  return env
}

const data = { kind: 'quirk-logic-spec-decisions', slug: 'demo', n: 1 }
const filename = 'demo-decisions-20260101T000000.json'
async function ok200() {
  return { status: 200, ok: true }
}

// on the companion route a 200 posts and does not download
{
  const env = setup('/_quirk/review', '?t=abc123', ok200)
  const result = await deliverExport(data, filename)
  check('200 resolves posted', result === 'posted')
  check('200 calls fetch once', env.fetchCalls.length === 1)
  const call = env.fetchCalls[0]
  check('posts to the export route', call?.url === '/_quirk/review/export')
  check('uses POST', call?.init.method === 'POST')
  const headers = (call?.init.headers ?? {}) as Record<string, string>
  check('sends the token header', headers['X-Quirk-Token'] === 'abc123')
  check('sends a JSON content type', headers['Content-Type'] === 'application/json')
  check('body is the export unmodified', call?.init.body === JSON.stringify(data))
  check('200 does not download', env.downloads.length === 0 && env.blobs.length === 0)
}

// a missing token is sent as an empty header
{
  const env = setup('/_quirk/review', '', ok200)
  await deliverExport(data, filename)
  const headers = (env.fetchCalls[0]?.init.headers ?? {}) as Record<string, string>
  check('missing token sends an empty header', headers['X-Quirk-Token'] === '')
}

// a non-200 or a thrown error falls back to the download
for (const [label, impl] of [
  ['403', async () => ({ status: 403, ok: false })],
  ['400', async () => ({ status: 400, ok: false })],
  ['413', async () => ({ status: 413, ok: false })],
  ['network error', async () => { throw new TypeError('network down') }],
] as const) {
  const env = setup('/_quirk/review', '?t=abc123', impl)
  const result = await deliverExport(data, filename)
  check(`${label} resolves downloaded`, result === 'downloaded')
  check(`${label} downloads with the same filename`, env.downloads.length === 1 && env.downloads[0] === filename)
  check(`${label} downloads the pretty-printed JSON`, env.blobs.length === 1 && (await env.blobs[0]!.text()) === JSON.stringify(data, null, 2))
}

// off the companion route fetch is never called
for (const pathname of ['/', '/review.html', '/Users/me/spec/review.html', '/_quirk/review/', '/_quirk/other']) {
  const env = setup(pathname, '?t=abc123', ok200)
  const result = await deliverExport(data, filename)
  check(`${pathname} resolves downloaded`, result === 'downloaded')
  check(`${pathname} never calls fetch`, env.fetchCalls.length === 0)
  check(`${pathname} downloads once`, env.downloads.length === 1 && env.downloads[0] === filename)
}

if (failures.length) {
  console.error(`deliver-check failed (${failures.length}):\n${failures.map((f) => `- ${f}`).join('\n')}`)
  process.exit(1)
}
console.log('deliver-check passed: companion post, fallback on failure, and off-companion download behave as specified.')
