import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import { layout } from './quirk-page'

const NAV_MIN_H2 = 5
const NAV_EXCLUDED = 'q-panel, q-compare, q-tabs, q-board'

interface NavHeading {
  id: string
  label: string
}

interface NavItem {
  heading: NavHeading
  children: NavHeading[]
}

function slug(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'section'
}

function uniqueId(base: string, taken: Set<string>): string {
  let candidate = base
  let n = 1
  while (taken.has(candidate)) {
    n += 1
    candidate = `${base}-${n}`
  }
  taken.add(candidate)
  return candidate
}

/**
 * The section nav for the rendered main content, or null when the page does not qualify.
 *
 * Follows the build's rules for tier-1 pages: h2 and h3 headings outside q-panel, q-compare, q-tabs
 * and q-board are listed, headings without an id gain one from their text, and the nav exists on
 * `reference` or at five or more h2 sections.
 */
function readNav(main: HTMLElement): NavItem[] | null {
  const headings = Array.from(main.querySelectorAll<HTMLElement>('h2, h3')).filter((h) => !h.closest(NAV_EXCLUDED))
  const h2Count = headings.filter((h) => h.tagName === 'H2').length
  const qualifies = layout === 'reference' ? headings.length > 0 : h2Count >= NAV_MIN_H2
  if (!qualifies) return null

  const taken = new Set(Array.from(document.querySelectorAll('[id]'), (el) => el.id))
  const items: NavItem[] = []
  for (const h of headings) {
    const text = (h.textContent ?? '').split(/\s+/).filter(Boolean).join(' ')
    if (!h.id) h.id = uniqueId(slug(text), taken)
    const entry = { id: h.id, label: text }
    if (h.tagName === 'H2' || items.length === 0) items.push({ heading: entry, children: [] })
    else items[items.length - 1].children.push(entry)
  }
  return items
}

/**
 * The id of the last nav heading whose top has passed 30% of the viewport height, or the last
 * heading once the page is scrolled to the bottom; null before the first heading is reached.
 */
function readCurrentId(items: NavItem[]): string | null {
  const ids = items.flatMap(({ heading, children }) => [heading.id, ...children.map((child) => child.id)])
  const headings = ids.map((id) => ({ id, el: document.getElementById(id) })).filter((h) => h.el)
  if (headings.length === 0) return null
  const scrollable = document.documentElement.scrollHeight - window.innerHeight
  if (scrollable > 0 && window.scrollY >= scrollable - 2) return headings[headings.length - 1].id
  const line = window.innerHeight * 0.3
  let current: string | null = null
  for (const { id, el } of headings) {
    if (el!.getBoundingClientRect().top <= line) current = id
  }
  return current
}

function NavLinks({ items, className, currentId }: { items: NavItem[]; className?: string; currentId?: string | null }) {
  // hash history owns location.hash, so a plain #id link would navigate the router instead of scrolling
  const jump = (event: MouseEvent<HTMLAnchorElement>, id: string) => {
    event.preventDefault()
    event.currentTarget.closest('details')?.removeAttribute('open')
    document.getElementById(id)?.scrollIntoView()
  }
  const link = ({ id, label }: NavHeading) => (
    <a href={`#${id}`} onClick={(event) => jump(event, id)} aria-current={id === currentId ? 'location' : undefined}>
      {label}
    </a>
  )
  return (
    <ol className={className}>
      {items.map(({ heading, children }) => (
        <li key={heading.id}>
          {link(heading)}
          {children.length ? (
            <ol>
              {children.map((child) => (
                <li key={child.id}>{link(child)}</li>
              ))}
            </ol>
          ) : null}
        </li>
      ))}
    </ol>
  )
}

function PageNav({ items, currentId }: { items: NavItem[]; currentId: string | null }) {
  const label = layout === 'reference' ? 'Sections' : 'On this page'
  return (
    <nav className="q-nav" aria-label={label}>
      <details className="q-nav-menu">
        <summary>{label}</summary>
        <NavLinks items={items} />
      </details>
      <NavLinks items={items} className="q-nav-rail" currentId={currentId} />
    </nav>
  )
}

/**
 * The page-shape wrapper every view renders inside: the same regions, class names and DOM order that
 * the build emits for a tier-1 page of this shape, placed by `quirk-layout.css`.
 *
 * `summary` is the page's answer or headline (where it sits depends on the shape), `children` is the
 * main content, and `aside` is an `<aside>` element that only the report shape places. The shape comes
 * from `quirk-page.ts`, which every build rewrites from the app's `layout` setting.
 */
export function PageLayout({ summary, children, aside }: { summary: ReactNode; children: ReactNode; aside?: ReactNode }) {
  const mainRef = useRef<HTMLElement>(null)
  const [items, setItems] = useState<NavItem[] | null>(null)
  const [currentId, setCurrentId] = useState<string | null>(null)
  const hasAside = aside !== undefined && aside !== null && aside !== false

  useEffect(() => {
    if (hasAside && layout !== 'report') console.warn(`PageLayout: the ${layout} shape has no aside region, so the aside is not rendered`)
  }, [hasAside])

  useLayoutEffect(() => {
    const main = mainRef.current
    if (!main) return
    const update = () => {
      const next = readNav(main)
      setItems((prev) => (JSON.stringify(prev) === JSON.stringify(next) ? prev : next))
    }
    update()
    const observer = new MutationObserver(update)
    observer.observe(main, { childList: true, subtree: true, characterData: true })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!items) {
      setCurrentId(null)
      return
    }
    let frame = 0
    const mark = () => {
      frame = 0
      setCurrentId(readCurrentId(items))
    }
    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(mark)
    }
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    mark()
    return () => {
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [items])

  const summaryRegion = summary ? (
    <section className="q-summary" aria-label="Summary">
      {summary}
    </section>
  ) : null
  const nav = items ? <PageNav items={items} currentId={currentId} /> : null
  const main = (
    <main id="main" ref={mainRef}>
      {children}
    </main>
  )

  return (
    <div className="q-page" data-layout={layout}>
      {layout === 'tool' ? (
        <>
          {nav}
          {main}
          {summaryRegion}
        </>
      ) : (
        <>
          {summaryRegion}
          {nav}
          {main}
          {layout === 'report' && hasAside ? aside : null}
        </>
      )}
    </div>
  )
}
