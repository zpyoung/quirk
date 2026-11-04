/**
 * Pure logic for the mock review harness. Loaded two ways: inlined as a classic script in
 * mock-harness.html (exposes `QuirkMockCore`) and `require`d by app/scripts/check-harness.ts.
 * No DOM access, no network, so every rule here is testable from Node.
 */
(function (root) {
  'use strict'

  var PIN_ID = /^mock:v([1-9][0-9]{0,3})\/([a-z0-9-]{1,40})\/([a-z0-9-]{1,40})\/([a-z0-9][a-z0-9._-]{0,79})\/x([0-9]{1,3})-y([0-9]{1,3})$/

  function clampPct(n) {
    var v = Math.round(Number(n))
    if (!isFinite(v)) return 0
    return Math.max(0, Math.min(100, v))
  }

  /** Parses a pin block id into its parts, or returns null for anything that is not exactly a pin id. */
  function parsePinId(id) {
    if (typeof id !== 'string') return null
    var m = PIN_ID.exec(id)
    if (!m) return null
    var x = Number(m[5])
    var y = Number(m[6])
    if (x > 100 || y > 100) return null
    return { version: Number(m[1]), screen: m[2], state: m[3], pin: m[4], x: x, y: y }
  }

  /** Builds a pin block id; offsets are rounded and clamped to 0-100, anything else invalid throws. */
  function formatPinId(p) {
    var id = 'mock:v' + p.version + '/' + p.screen + '/' + p.state + '/' + p.pin + '/x' + clampPct(p.x) + '-y' + clampPct(p.y)
    if (!parsePinId(id)) throw new Error('invalid pin id parts: ' + id)
    return id
  }

  /**
   * Decides how a pin is shown while `viewed` is on screen.
   *   draw        its own version: drawn at the element plus offset
   *   reanchored  older version and the element key still exists: drawn there with a "from vN" badge
   *   orphaned    older version and the key is gone: listed, never drawn on another element
   *   hidden      newer than the version viewed (or than the latest)
   * `keys` is the set (or array) of data-pin keys present in the pin's screen and state in the viewed version.
   */
  function placePin(pin, viewed, latest, keys) {
    if (pin.version > viewed || pin.version > latest) return 'hidden'
    if (pin.version === viewed) return 'draw'
    var present = keys instanceof Set ? keys.has(pin.pin) : Array.isArray(keys) && keys.indexOf(pin.pin) !== -1
    return present ? 'reanchored' : 'orphaned'
  }

  function screenList(doc) {
    if (Array.isArray(doc)) return doc
    return doc && Array.isArray(doc.screens) ? doc.screens : []
  }

  function isKnownScreen(doc, id) {
    return screenList(doc).some(function (s) { return s.id === id })
  }

  /** Inventory screen ids not yet visited, in inventory order. */
  function unvisitedScreens(doc, visited) {
    var seen = visited instanceof Set ? visited : new Set(visited || [])
    return screenList(doc)
      .map(function (s) { return s.id })
      .filter(function (id) { return !seen.has(id) })
  }

  /** Elements with no repo component while the repo has a UI layer. */
  function deriveGaps(doc) {
    if (!doc || doc.ui_layer !== true) return []
    var gaps = []
    screenList(doc).forEach(function (s) {
      ;(s.elements || []).forEach(function (e) {
        if (e.component === null) gaps.push({ screen: s.id, pin: e.pin, label: e.label })
      })
    })
    return gaps
  }

  /** Screen id named by `#/<id>`; an empty hash is the first screen, an unknown id is returned as is. */
  function currentScreenId(hash, doc) {
    var h = String(hash || '').replace(/^#/, '').replace(/^\//, '')
    var id = h.split(/[/?]/)[0]
    try {
      id = decodeURIComponent(id)
    } catch (e) {
      // keep the raw text
    }
    if (id) return id
    var screens = screenList(doc)
    return screens.length ? screens[0].id : null
  }

  /** Inserts <base href="about:srcdoc"> as the first child of <head>, creating the head if the mock has none. */
  function withBase(html) {
    var base = '<base href="about:srcdoc">'
    var masked = html.replace(/<!--[\s\S]*?-->/g, function (c) { return new Array(c.length + 1).join(' ') })
    var head = /<head(?=[\s>/])[^>]*>/i.exec(masked)
    if (head) {
      var at = head.index + head[0].length
      return html.slice(0, at) + base + html.slice(at)
    }
    var open = /<html(?=[\s>/])[^>]*>/i.exec(masked)
    if (open) {
      var end = open.index + open[0].length
      return html.slice(0, end) + '<head>' + base + '</head>' + html.slice(end)
    }
    var doctype = /^\s*<!doctype[^>]*>/i.exec(masked)
    var pos = doctype ? doctype[0].length : 0
    return html.slice(0, pos) + '<head>' + base + '</head>' + html.slice(pos)
  }

  /** Whether comment mode and the verdict bar are allowed for this boot and snapshot. */
  function canReview(boot, snap) {
    if (!boot || boot.mode !== 'app' || !snap || !snap.step) return false
    if (snap.step_state !== 'open') return false
    if (snap.step.kind !== 'mock-review' || snap.step.version !== boot.version) return false
    return !!snap.mocks && snap.mocks.latest === boot.version
  }

  /** Integer percentage offset of a point inside a box, clamped to 0-100. */
  function offsetPct(rect, clientX, clientY) {
    if (!rect.width || !rect.height) return { x: 0, y: 0 }
    return {
      x: clampPct(((clientX - rect.left) / rect.width) * 100),
      y: clampPct(((clientY - rect.top) / rect.height) * 100),
    }
  }

  function lastAgentMessage(thread) {
    var msgs = (thread && thread.messages) || []
    for (var i = msgs.length - 1; i >= 0; i -= 1) if (msgs[i].from === 'agent') return msgs[i]
    return null
  }

  var api = {
    parsePinId: parsePinId,
    formatPinId: formatPinId,
    placePin: placePin,
    isKnownScreen: isKnownScreen,
    unvisitedScreens: unvisitedScreens,
    deriveGaps: deriveGaps,
    currentScreenId: currentScreenId,
    withBase: withBase,
    canReview: canReview,
    offsetPct: offsetPct,
    lastAgentMessage: lastAgentMessage,
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = api
  else root.QuirkMockCore = api
})(typeof globalThis !== 'undefined' ? globalThis : this)
