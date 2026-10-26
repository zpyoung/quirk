import { useState } from "react"

import { Kbd } from "@/components/ui/kbd"

type EmptyPaneProps = {
  hasItems: boolean
  recent: { id: string; title: string }[]
  onCreate?: () => void
  onGoTo: () => void
  onOpen: (id: string) => void
  onClose: () => void
}

const linkClass =
  "text-sm text-primary underline-offset-2 outline-none hover:underline focus-visible:underline focus-visible:ring-2 focus-visible:ring-ring rounded-sm"

function Link({ label, keys, ...rest }: { label: string; keys?: string } & React.ComponentProps<"button">) {
  return (
    <li className="flex items-center gap-2">
      <button type="button" data-empty-link className={linkClass} {...rest}>
        {label}
      </button>
      {keys ? <Kbd>{keys}</Kbd> : null}
    </li>
  )
}

/** What a tab with no record shows: plain text links with their shortcuts. */
export function EmptyPane({ hasItems, recent, onCreate, onGoTo, onOpen, onClose }: EmptyPaneProps) {
  const [showRecent, setShowRecent] = useState(false)
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6">
      <ul className="flex flex-col items-start gap-2">
        {onCreate ? <Link label="Create new item" keys="Alt+N" onClick={onCreate} /> : null}
        {hasItems ? (
          <>
            <Link label="Go to item" keys="Alt+O" onClick={onGoTo} />
            <Link
              label="See recent items"
              aria-expanded={showRecent}
              onClick={() => setShowRecent((open) => !open)}
            />
            <Link label="Close" onClick={onClose} />
          </>
        ) : null}
      </ul>
      {!onCreate && !hasItems ? (
        <p className="text-sm text-muted-foreground">Nothing to open yet.</p>
      ) : null}
      {showRecent ? (
        recent.length > 0 ? (
          <ul aria-label="Recent items" className="flex flex-col items-start gap-1">
            {recent.map((item) => (
              <li key={item.id}>
                <button type="button" className={linkClass} onClick={() => onOpen(item.id)}>
                  {item.title}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">No recent items.</p>
        )
      ) : null}
    </div>
  )
}
