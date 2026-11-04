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

  /**
   * Placement of a pin from the viewed version's own screen inventory. A pin of an older version whose
   * screen or state the viewed version no longer lists is orphaned. When the screen and state exist,
   * `keysFor(screen, state)` returns the data-pin keys rendered there (array or Set), or null when that
   * screen is not rendered right now, which leaves the pin `unknown`: neither orphaned nor drawn.
   */
  function classifyPin(pin, viewed, latest, doc, keysFor) {
    if (pin.version > viewed || pin.version > latest) return 'hidden'
    if (pin.version === viewed) return 'draw'
    var screen = screenList(doc).filter(function (s) { return s.id === pin.screen })[0]
    if (!screen || !Array.isArray(screen.states) || screen.states.indexOf(pin.state) === -1) return 'orphaned'
    var keys = keysFor(pin.screen, pin.state)
    if (keys === null || keys === undefined) return 'unknown'
    return placePin(pin, viewed, latest, keys)
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

  var RAW_TEXT = { script: 1, style: 1, textarea: 1, title: 1, xmp: 1, iframe: 1, noembed: 1, noframes: 1, noscript: 1 }

  /**
   * Inserts <base href="about:srcdoc"> as the first child of the mock's real <head>. Comments, raw-text
   * elements (script, style, ...) and quoted attribute values are skipped, so `<head>` text inside them is
   * never mistaken for the head. With no head before the body, one is created right after <html>, else
   * after the doctype, else at the start.
   */
  function withBase(html) {
    var base = '<base href="about:srcdoc">'
    var len = html.length
    var i = 0
    var doctypeEnd = 0
    var htmlEnd = -1
    var sawTag = false
    while (i < len) {
      var lt = html.indexOf('<', i)
      if (lt === -1) break
      var next = html.charAt(lt + 1)
      if (html.substr(lt, 4) === '<!--') {
        var close = html.indexOf('-->', lt + 2)
        i = close === -1 ? len : close + 3
        continue
      }
      if (next === '!' || next === '?' || next === '/') {
        var gt = html.indexOf('>', lt + 2)
        if (next === '!' && !sawTag && gt !== -1 && /^<!doctype/i.test(html.substr(lt, 9))) doctypeEnd = gt + 1
        i = gt === -1 ? len : gt + 1
        continue
      }
      if (!/[a-zA-Z]/.test(next)) {
        i = lt + 1
        continue
      }
      var j = lt + 1
      while (j < len && !/[\s/>]/.test(html.charAt(j))) j += 1
      var name = html.slice(lt + 1, j).toLowerCase()
      while (j < len && html.charAt(j) !== '>') {
        if (html.charAt(j) === '=') {
          j += 1
          while (j < len && /\s/.test(html.charAt(j))) j += 1
          var q = html.charAt(j)
          if (q === '"' || q === "'") {
            var endQuote = html.indexOf(q, j + 1)
            j = endQuote === -1 ? len : endQuote + 1
          }
          continue
        }
        j += 1
      }
      var tagEnd = j < len ? j + 1 : len
      sawTag = true
      if (name === 'head') return html.slice(0, tagEnd) + base + html.slice(tagEnd)
      if (name === 'body' || name === 'frameset') break
      if (name === 'html' && htmlEnd === -1) htmlEnd = tagEnd
      i = tagEnd
      if (RAW_TEXT[name] === 1) {
        var closer = new RegExp('</' + name + '(?=[\\s/>])', 'ig')
        closer.lastIndex = tagEnd
        var found = closer.exec(html)
        i = found ? found.index : len
      }
    }
    var pos = htmlEnd !== -1 ? htmlEnd : doctypeEnd
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
    classifyPin: classifyPin,
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
