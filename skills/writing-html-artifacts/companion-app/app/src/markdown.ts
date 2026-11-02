import MarkdownIt from 'markdown-it'

/** The shared renderer; `section-blocks` reuses it to number blocks as it renders. */
export const md = new MarkdownIt({ html: false, linkify: true, breaks: false })

const defaultLinkOpen =
  md.renderer.rules.link_open ?? ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noreferrer')
  return defaultLinkOpen(tokens, idx, options, env, self)
}

/** Renders agent markdown to HTML with raw HTML disabled; agent HTML only arrives through the *_html fields. */
export function renderMarkdown(source: string | undefined): string {
  return source ? md.render(source) : ''
}
