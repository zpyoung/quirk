/**
 * Press marker: sets `data-mini-pressed` on a shadcn button or toggle while it is pressed, and keeps
 * it for at least HOLD_MS so a quick tap still shows. A held key press also ends when the element
 * blurs, the window blurs, or the page is hidden, since keyup may never arrive. Styles key off the
 * attribute; the module only observes events and writes that one attribute. Import it once for its
 * side effect.
 */

const SELECTOR = '[data-slot="button"], [data-slot="toggle"], [data-slot="toggle-group-item"]'
const ATTRIBUTE = "data-mini-pressed"
const HOLD_MS = 120
const INSTALLED = "__miniPressMarker"

interface Press {
  element: HTMLElement
  at: number
  key: string | null
}

function enabled(element: HTMLElement | null): HTMLElement | null {
  if (!element) return null
  if (element.matches(":disabled") || element.getAttribute("aria-disabled") === "true") return null
  return element
}

function pressableAt(target: EventTarget | null): HTMLElement | null {
  return target instanceof Element ? enabled(target.closest<HTMLElement>(SELECTOR)) : null
}

function pressableFocus(active: Element | null): HTMLElement | null {
  return active instanceof HTMLElement && active.matches(SELECTOR) ? enabled(active) : null
}

function install() {
  let held: Press | null = null
  const removals = new Map<HTMLElement, number>()

  function press(element: HTMLElement, key: string | null) {
    const pending = removals.get(element)
    if (pending !== undefined) {
      window.clearTimeout(pending)
      removals.delete(element)
    }
    if (held && held.element !== element) release()
    element.setAttribute(ATTRIBUTE, "")
    held = { element, at: performance.now(), key }
  }

  function release() {
    if (!held) return
    const { element, at } = held
    held = null
    const wait = Math.max(0, HOLD_MS - (performance.now() - at))
    if (wait === 0) {
      element.removeAttribute(ATTRIBUTE)
      return
    }
    removals.set(
      element,
      window.setTimeout(() => {
        removals.delete(element)
        element.removeAttribute(ATTRIBUTE)
      }, wait)
    )
  }

  const options = { capture: true }

  document.addEventListener(
    "pointerdown",
    (event) => {
      if (event.button !== 0) return
      const element = pressableAt(event.target)
      if (element) press(element, null)
    },
    options
  )
  document.addEventListener("pointerup", release, options)
  document.addEventListener("pointercancel", release, options)
  document.addEventListener(
    "keydown",
    (event) => {
      if (event.repeat || (event.key !== " " && event.key !== "Enter")) return
      const element = pressableFocus(document.activeElement)
      if (element) press(element, event.key)
    },
    options
  )
  document.addEventListener(
    "keyup",
    (event) => {
      if (held && held.key === event.key) release()
    },
    options
  )
  document.addEventListener(
    "blur",
    (event) => {
      if (held && event.target === held.element) release()
    },
    options
  )
  window.addEventListener("blur", release)
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") release()
  })
}

const host = window as unknown as Record<string, unknown>
if (!host[INSTALLED]) {
  host[INSTALLED] = true
  install()
}
