import { md } from './markdown'

/** Where a section's block ids come from: `section:<section id>/p<n>`, n counting from `start`. */
export interface BlockNumbering {
  sectionId: string
  start: number
  changed: Set<string>
}

export interface Annotated {
  html: string
  /** How many blocks were numbered, so the next part of the section continues after them. */
  count: number
}

const MD_BLOCK_OPENERS = new Set(['paragraph_open', 'heading_open', 'bullet_list_open', 'ordered_list_open', 'blockquote_open', 'table_open'])
const MD_BLOCK_LEAVES = new Set(['fence', 'code_block'])

export function paragraphId(sectionId: string, n: number): string {
  return `section:${sectionId}/p${n}`
}

function idAttrs(id: string, changed: Set<string>): string {
  return changed.has(id) ? ` data-block-id="${id}" data-changed="true"` : ` data-block-id="${id}"`
}

/** Renders section markdown, giving each top-level block its paragraph id. */
export function renderSectionMarkdown(source: string | undefined, numbering: BlockNumbering): Annotated {
  if (!source) return { html: '', count: 0 }
  const tokens = md.parse(source, {})
  let count = 0
  for (const token of tokens) {
    if (token.level !== 0) continue
    if (!(token.nesting === 1 ? MD_BLOCK_OPENERS.has(token.type) : MD_BLOCK_LEAVES.has(token.type))) continue
    const id = paragraphId(numbering.sectionId, numbering.start + count)
    token.attrSet('data-block-id', id)
    if (numbering.changed.has(id)) token.attrSet('data-changed', 'true')
    count += 1
  }
  return { html: md.renderer.render(tokens, md.options, {}), count }
}

const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'])
const RAW_TEXT = new Set(['script', 'style', 'textarea', 'title'])
const NOT_CONTENT = new Set(['script', 'style', 'template', 'link', 'meta', 'title', 'br', 'hr', 'wbr'])
const BLOCK_TAGS = new Set([
  'p', 'ul', 'ol', 'dl', 'pre', 'table', 'blockquote', 'figure', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'section', 'article', 'aside',
  'header', 'footer', 'nav', 'main', 'form', 'fieldset', 'details', 'address', 'canvas', 'svg',
])
// an open <p> ends where one of these starts, as the browser parses it
const CLOSES_P = new Set(['address', 'article', 'aside', 'blockquote', 'dl', 'div', 'fieldset', 'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'main', 'nav', 'ol', 'p', 'pre', 'section', 'table', 'ul'])

const isBlockTag = (name: string) => !NOT_CONTENT.has(name) && (BLOCK_TAGS.has(name) || name.includes('-'))

/** End index (exclusive) of the tag that starts at `from`, skipping `>` inside quoted attribute values. */
function tagEnd(html: string, from: number): number {
  let quote = ''
  for (let i = from + 1; i < html.length; i += 1) {
    const ch = html[i]
    if (quote) {
      if (ch === quote) quote = ''
    } else if (ch === '"' || ch === "'") {
      quote = ch
    } else if (ch === '>') {
      return i + 1
    }
  }
  return html.length
}

/**
 * Gives each top-level block element of agent HTML its paragraph id, in document order. An element that already
 * carries its own `data-block-id` or `data-commentable` keeps it and still takes a number, so ids do not shift
 * when an agent adds or removes its own marker.
 */
export function annotateSectionHtml(html: string | undefined, numbering: BlockNumbering): Annotated {
  if (!html) return { html: '', count: 0 }
  let out = ''
  let copied = 0
  let depth = 0
  let openTop = ''
  let count = 0
  let i = 0
  while (i < html.length) {
    const lt = html.indexOf('<', i)
    if (lt === -1) break
    if (html.startsWith('<!--', lt)) {
      const close = html.indexOf('-->', lt + 4)
      i = close === -1 ? html.length : close + 3
      continue
    }
    const rest = html.slice(lt + 1, lt + 40)
    const closing = /^\/([A-Za-z][^\s/>]*)/.exec(rest)
    const opening = /^([A-Za-z][^\s/>]*)/.exec(rest)
    if (!closing && !opening) {
      i = tagEnd(html, lt)
      continue
    }
    const end = tagEnd(html, lt)
    if (closing) {
      if (depth > 0) {
        depth -= 1
        if (depth === 0) openTop = ''
      }
      i = end
      continue
    }
    const name = (opening as RegExpExecArray)[1].toLowerCase()
    if (depth === 1 && openTop === 'p' && CLOSES_P.has(name)) {
      depth = 0
      openTop = ''
    }
    const tag = html.slice(lt, end)
    const selfClosed = VOID.has(name) || tag.endsWith('/>')
    if (depth === 0 && isBlockTag(name)) {
      const id = paragraphId(numbering.sectionId, numbering.start + count)
      count += 1
      if (!/\sdata-(?:block-id|commentable)\s*=/.test(tag)) {
        const at = lt + 1 + (opening as RegExpExecArray)[1].length
        out += html.slice(copied, at) + idAttrs(id, numbering.changed)
        copied = at
      }
    }
    if (RAW_TEXT.has(name) && !selfClosed) {
      const close = html.toLowerCase().indexOf(`</${name}`, end)
      i = close === -1 ? html.length : tagEnd(html, close)
      continue
    }
    if (!selfClosed) {
      if (depth === 0) openTop = name
      depth += 1
    }
    i = end
  }
  return { html: out + html.slice(copied), count }
}
