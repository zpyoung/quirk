import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const harnessDir = fileURLToPath(new URL('../../harness/', import.meta.url))
const require = createRequire(import.meta.url)

const failures: string[] = []
const check = (ok: boolean, message: string) => {
  if (!ok) failures.push(message)
}
const same = (actual: unknown, expected: unknown, message: string) => {
  const a = JSON.stringify(actual)
  const e = JSON.stringify(expected)
  if (a !== e) failures.push(`${message}: expected ${e}, got ${a}`)
}

// the harness core is inlined into the page and also required from Node, so it must export itself
const core = require(`${harnessDir}harness-core.js`)

// pin block id round trip
{
  const pin = { version: 3, screen: 'saved-exports', state: 'empty', pin: 'btn.new-export', x: 42, y: 7 }
  const id = core.formatPinId(pin)
  same(id, 'mock:v3/saved-exports/empty/btn.new-export/x42-y7', 'formatPinId output')
  same(core.parsePinId(id), pin, 'parsePinId round trip')
  same(core.parsePinId(core.formatPinId({ ...pin, x: 0, y: 100 })), { ...pin, x: 0, y: 100 }, 'round trip at the 0 and 100 bounds')
  same(core.formatPinId({ ...pin, x: 41.6, y: -3 }), 'mock:v3/saved-exports/empty/btn.new-export/x42-y0', 'formatPinId rounds and clamps offsets')
}

// malformed ids are rejected, never half-parsed
{
  const malformed: unknown[] = [
    '',
    null,
    undefined,
    42,
    'section-1',
    'mock:v0/a/b/c/x1-y1',
    'mock:v01/a/b/c/x1-y1',
    'mock:v10000/a/b/c/x1-y1',
    'mock:v1/A/b/c/x1-y1',
    'mock:v1/a/b/c/x1',
    'mock:v1/a/b/c/x1-y1/extra',
    'mock:v1/a/b/.c/x1-y1',
    'mock:v1/a/b/c/x1000-y1',
    'mock:v1/a/b/c/x101-y1',
    'mock:v1/a/b/c/x1-y101',
    'mock:v1/a/b/c/x-1-y1',
    ' mock:v1/a/b/c/x1-y1',
    'mock:v1/a/b/c/x1-y1\n',
    'mock:v1/a/b//x1-y1',
    `mock:v1/${'a'.repeat(41)}/b/c/x1-y1`,
    `mock:v1/a/b/${'c'.repeat(81)}/x1-y1`,
  ]
  for (const id of malformed) check(core.parsePinId(id) === null, `parsePinId accepted ${JSON.stringify(id)}`)
  let threw = false
  try {
    core.formatPinId({ version: 1, screen: 'Bad Screen', state: 'a', pin: 'b', x: 1, y: 1 })
  } catch {
    threw = true
  }
  check(threw, 'formatPinId accepted an invalid screen id')
  threw = false
  try {
    core.formatPinId({ version: 0, screen: 'a', state: 'b', pin: 'c', x: 1, y: 1 })
  } catch {
    threw = true
  }
  check(threw, 'formatPinId accepted version 0')
}

// pin placement: every branch
{
  const keys = new Set(['btn.new-export'])
  const pin = (version: number, key = 'btn.new-export') => ({ version, screen: 's', state: 'default', pin: key, x: 5, y: 5 })
  same(core.placePin(pin(2), 2, 2, keys), 'draw', 'same version, key present')
  same(core.placePin(pin(2, 'gone'), 2, 2, keys), 'draw', 'same version draws even when the key is not in the set')
  same(core.placePin(pin(1), 2, 3, keys), 'reanchored', 'older version, key present')
  same(core.placePin(pin(1, 'gone'), 2, 3, keys), 'orphaned', 'older version, key missing')
  same(core.placePin(pin(1, 'gone'), 2, 3, new Set()), 'orphaned', 'older version, empty key set')
  same(core.placePin(pin(3), 2, 3, keys), 'hidden', 'newer version than the one viewed')
  same(core.placePin(pin(3, 'gone'), 2, 3, keys), 'hidden', 'newer version, key missing')
  same(core.placePin(pin(1), 1, 3, ['btn.new-export']), 'draw', 'viewing an old version draws its own pins; keys may be an array')
  same(core.placePin(pin(4), 4, 3, keys), 'hidden', 'a pin from beyond the latest version is hidden')
}

// unvisited screens and gaps
{
  const doc = {
    ui_layer: true,
    screens: [
      { id: 'list', title: 'List', purpose: 'p', states: ['default'], elements: [{ pin: 'tbl', label: 'Table', component: 'DataTable' }, { pin: 'range', label: 'Date range', component: null }] },
      { id: 'detail', title: 'Detail', purpose: 'p', states: ['default'], elements: [{ pin: 'dl', label: 'Download', component: null }] },
      { id: 'dialog', title: 'Dialog', purpose: 'p', states: ['default'] },
    ],
  }
  same(core.unvisitedScreens(doc, ['detail']), ['list', 'dialog'], 'unvisited screens keep inventory order')
  same(core.unvisitedScreens(doc, new Set(['list', 'detail', 'dialog'])), [], 'nothing unvisited')
  same(core.unvisitedScreens(doc, []), ['list', 'detail', 'dialog'], 'everything unvisited')
  same(core.unvisitedScreens(doc, ['not-a-screen']), ['list', 'detail', 'dialog'], 'a visited id outside the inventory removes nothing')
  same(core.deriveGaps(doc), [{ screen: 'list', pin: 'range', label: 'Date range' }, { screen: 'detail', pin: 'dl', label: 'Download' }], 'gaps are elements with a null component')
  same(core.deriveGaps({ ...doc, ui_layer: false }), [], 'no gaps without a UI layer')
  same(core.deriveGaps({ ui_layer: true, screens: [{ id: 'a', title: 't', purpose: 'p', states: ['default'] }] }), [], 'screen without elements has no gaps')
}

// hash parsing
{
  const doc = { ui_layer: true, screens: [{ id: 'list' }, { id: 'detail' }] }
  same(core.currentScreenId('#/detail', doc), 'detail', 'hash names the screen')
  same(core.currentScreenId('', doc), 'list', 'empty hash is the first screen')
  same(core.currentScreenId('#', doc), 'list', 'bare # is the first screen')
  same(core.currentScreenId('#/', doc), 'list', '#/ is the first screen')
  same(core.currentScreenId('#/detail/extra?x=1', doc), 'detail', 'only the first path segment names the screen')
  same(core.currentScreenId('#/elsewhere', doc), 'elsewhere', 'an unknown screen id is returned so the harness can warn')
  same(core.currentScreenId('#/%E0%A4%A', doc), '%E0%A4%A', 'an undecodable hash does not throw')
  same(core.currentScreenId('', { screens: [] }), null, 'no screens, no current screen')
  check(core.isKnownScreen(doc, 'detail') === true && core.isKnownScreen(doc, 'nope') === false, 'isKnownScreen')
}

// srcdoc base insertion keeps hash links inside the mock
{
  const base = '<base href="about:srcdoc">'
  check(core.withBase('<!doctype html><html><head><title>x</title></head><body></body></html>').includes(`<head>${base}<title>`), 'base is not the first child of an existing head')
  check(core.withBase('<html><HEAD lang="en"><meta charset="utf-8"></HEAD></html>').includes(`<HEAD lang="en">${base}<meta`), 'base does not follow a head with attributes')
  const noHead = core.withBase('<!doctype html><html lang="en"><body>hi</body></html>')
  check(noHead.startsWith('<!doctype html>') && noHead.includes(`<html lang="en"><head>${base}</head><body>`), 'a missing head is not created inside html')
  const bare = core.withBase('<p>hi</p>')
  check(bare.startsWith(`<head>${base}</head>`), 'a fragment does not get a head')
  check(core.withBase('<!doctype html><p>hi</p>').startsWith(`<!doctype html><head>${base}</head>`), 'the doctype is not kept first')
  check(core.withBase('<!-- <head> --><html><head></head></html>').includes(`<!-- <head> --><html><head>${base}</head>`), 'base went into a comment instead of the real head')

  const count = (text: string, needle: string) => text.split(needle).length - 1
  for (const tag of ['script', 'style', 'textarea', 'title']) {
    const body = tag === 'script' ? 'var s = "<head>";' : '<head>'
    const doc = `<!doctype html><html><${tag}>${body}</${tag}><head><meta charset="utf-8"></head><body></body></html>`
    const out = core.withBase(doc)
    check(out.includes(`<head>${base}<meta charset="utf-8">`) && count(out, base) === 1, `base missed the real head after a ${tag} containing <head>: ${out}`)
    check(out.includes(`<${tag}>${body}</${tag}>`), `base corrupted the ${tag} contents`)
  }
  const inAttr = core.withBase('<html><body data-x="<head>"></body></html>')
  check(inAttr.includes(`<html><head>${base}</head><body data-x="<head>">`), `a <head> in an attribute value was taken for the head: ${inAttr}`)
  const scriptNoHead = core.withBase('<!doctype html><html lang="en"><script>document.write("<head><html>")</script><body>x</body></html>')
  check(scriptNoHead.includes(`<html lang="en"><head>${base}</head><script>document.write("<head><html>")</script>`) && count(scriptNoHead, base) === 1, `a headless document with <head> text in a script got the base in the wrong place: ${scriptNoHead}`)
  const scriptOnly = core.withBase('<!doctype html><script>var a = "<html><head>";</script><p>x</p>')
  check(scriptOnly.startsWith(`<!doctype html><head>${base}</head><script>var a = "<html><head>";</script>`), `a document with neither html nor head got the base inside a script: ${scriptOnly}`)
  const lateHead = core.withBase('<html><body><p>x</p></body></html>')
  check(lateHead.includes(`<html><head>${base}</head><body>`), 'a headless document did not get a head before the body')
}

// pin classification uses the viewed version's inventory
{
  const doc = {
    screens: [
      { id: 'list', states: ['default', 'empty'] },
      { id: 'detail', states: ['default'] },
    ],
  }
  const pin = (version: number, screen: string, state: string, key = 'btn') => ({ version, screen, state, pin: key, x: 1, y: 1 })
  const present = () => new Set(['btn'])
  const none = () => null
  same(core.classifyPin(pin(1, 'gone', 'default'), 2, 2, doc, none), 'orphaned', 'older pin on a screen removed from the inventory')
  same(core.classifyPin(pin(1, 'gone', 'default'), 2, 2, doc, present), 'orphaned', 'a removed screen is orphaned even if keys are offered')
  same(core.classifyPin(pin(1, 'list', 'loading'), 2, 2, doc, present), 'orphaned', 'older pin on a state removed from the screen')
  same(core.classifyPin(pin(1, 'list', 'empty'), 2, 2, doc, present), 'reanchored', 'older pin, screen, state and key all present')
  same(core.classifyPin(pin(1, 'list', 'empty', 'gone'), 2, 2, doc, present), 'orphaned', 'older pin whose key is gone from its rendered screen')
  same(core.classifyPin(pin(1, 'detail', 'default'), 2, 2, doc, none), 'unknown', 'older pin on a listed screen that is not rendered is neither orphaned nor drawn')
  same(core.classifyPin(pin(2, 'gone', 'default'), 2, 2, doc, none), 'draw', 'a pin of the viewed version always draws')
  same(core.classifyPin(pin(3, 'list', 'default'), 2, 3, doc, present), 'hidden', 'a newer pin is hidden')
}

// the review UI is gated on the open mock-review step for the viewed latest version
{
  const boot = { mode: 'app', version: 2, latest: 2, token: 't' }
  const snap = (patch: Record<string, unknown> = {}) => ({
    step: { id: 's', nonce: 'n', kind: 'mock-review', version: 2 },
    step_state: 'open',
    mocks: { latest: 2, versions: [1, 2] },
    ...patch,
  })
  check(core.canReview(boot, snap()) === true, 'canReview rejected the open step for the latest version')
  check(core.canReview({ ...boot, mode: 'offline' }, snap()) === false, 'canReview allowed offline mode')
  check(core.canReview(boot, null) === false, 'canReview allowed no snapshot')
  check(core.canReview(boot, snap({ step_state: 'submitted' })) === false, 'canReview allowed a submitted step')
  check(core.canReview(boot, snap({ mocks: { latest: 3, versions: [1, 2, 3] } })) === false, 'canReview allowed a non-latest version')
  check(core.canReview(boot, snap({ step: { id: 's', nonce: 'n', kind: 'questions' } })) === false, 'canReview allowed another step kind')
  check(core.canReview(boot, snap({ step: { id: 's', nonce: 'n', kind: 'mock-review', version: 1 } })) === false, 'canReview allowed a step for another version')
  check(core.canReview(boot, snap({ step: null })) === false, 'canReview allowed no step')
}

// offsets within an element box are integer percentages inside 0-100
{
  const rect = { left: 100, top: 50, width: 200, height: 40 }
  same(core.offsetPct(rect, 150, 70), { x: 25, y: 50 }, 'offsetPct midpoint')
  same(core.offsetPct(rect, 0, 1000), { x: 0, y: 100 }, 'offsetPct clamps')
  same(core.offsetPct({ left: 0, top: 0, width: 0, height: 0 }, 5, 5), { x: 0, y: 0 }, 'offsetPct on an empty box')
}

// the last agent message of a thread is the one a resolved pin shows
{
  const thread = { messages: [{ from: 'user', text: 'a' }, { from: 'agent', text: 'moved it' }, { from: 'user', text: 'thanks' }] }
  same(core.lastAgentMessage(thread)?.text, 'moved it', 'lastAgentMessage')
  same(core.lastAgentMessage({ messages: [{ from: 'user', text: 'a' }] }), null, 'lastAgentMessage with no agent reply')
}

// page template: exactly one of each placeholder, and nothing fetched beyond same-origin /_quirk/app
{
  const html = readFileSync(`${harnessDir}mock-harness.html`, 'utf8')
  const count = (needle: string) => html.split(needle).length - 1
  const boot = '<script id="quirk-mock-boot" type="application/json">null</script>'
  check(count(boot) === 1, `boot placeholder appears ${count(boot)} times, expected 1`)
  check(count('quirk-mock-boot') === 1, 'boot id is mentioned outside its placeholder')
  check(count('<!--quirk-harness-core-->') === 1, `core placeholder appears ${count('<!--quirk-harness-core-->')} times, expected 1`)
  check(!/\binnerHTML\b/.test(html), 'the page uses innerHTML')
  check(!/<(script|link)[^>]+\b(src|href)=["']https?:/i.test(html), 'the page loads an external script or stylesheet')
  const coreSrc = readFileSync(`${harnessDir}harness-core.js`, 'utf8')
  check(!coreSrc.includes('quirk-mock-boot') && !coreSrc.includes('quirk-harness-core') && !coreSrc.includes('</script'), 'harness-core.js would break when inlined into the page')
  check(!/\bXMLHttpRequest\b|\bWebSocket\b|\bEventSource\b/.test(html), 'the page opens a connection other than fetch')
  for (const target of html.match(/fetch\(([^,)]*)/g) ?? []) check(/_quirk\/app\//.test(target), `fetch target is not same-origin /_quirk/app: ${target}`)
}

if (failures.length) {
  console.error(`harness-check failed:\n${failures.map((f) => `  - ${f}`).join('\n')}`)
  process.exitCode = 1
} else {
  console.log('harness-check passed: pin ids, placement, unvisited screens, gaps, hash parsing, srcdoc base, pin classification and page placeholders.')
}
