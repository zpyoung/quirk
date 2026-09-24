import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { Link } from '@astryxdesign/core/Link'
import type { MarkdownInlinePlugin } from '@astryxdesign/core/Markdown'
import type { LogicSpec } from '../spec-types'

type ItemLinks = { ids: Set<string>; open: (id: string) => void; plugins: MarkdownInlinePlugin[] }

const ItemLinksContext = createContext<ItemLinks | null>(null)

/** Every spec item a reference in prose can open: scenarios, constraints, assumptions, blind spots, requirements, and behaviors. */
export function linkableItemIds(spec: LogicSpec): string[] {
  return [spec.behaviors, spec.scenarios, spec.constraints, spec.assumptions, spec.blindSpots, spec.requirements].flatMap((items) =>
    items.map((item) => item.id),
  )
}

const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Makes item IDs clickable for everything below it; `open` receives the clicked ID. */
export function ItemLinksProvider({ spec, open, children }: { spec: LogicSpec; open: (id: string) => void; children: ReactNode }) {
  const value = useMemo<ItemLinks>(() => {
    const ids = new Set(linkableItemIds(spec))
    const plugins: MarkdownInlinePlugin[] = ids.size
      ? [{
          pattern: new RegExp(`\\b(${[...ids].map(escapeRegExp).join('|')})\\b`, 'g'),
          render: (match, key) => <ItemRef key={key} id={match[1]} />,
        }]
      : []
    return { ids, open, plugins }
  }, [spec, open])
  return <ItemLinksContext.Provider value={value}>{children}</ItemLinksContext.Provider>
}

/** Markdown inline plugins that turn item IDs in prose into links; empty outside a provider. */
export function useItemLinkPlugins(): MarkdownInlinePlugin[] | undefined {
  return useContext(ItemLinksContext)?.plugins
}

/** Opens an item's details by ID; undefined outside a provider. */
export function useOpenItem(): ((id: string) => void) | undefined {
  return useContext(ItemLinksContext)?.open
}

/** An item ID that opens the item's details; plain text when the ID is unknown or no provider is mounted. */
export function ItemRef({ id }: { id: string }) {
  const links = useContext(ItemLinksContext)
  if (!links?.ids.has(id)) return <>{id}</>
  return <Link onClick={() => links.open(id)}>{id}</Link>
}
