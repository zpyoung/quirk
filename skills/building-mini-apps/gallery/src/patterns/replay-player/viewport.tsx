import type { ReactNode } from "react"
import { GlobeIcon, MousePointer2Icon } from "lucide-react"

import { RIPPLE_MS } from "./playback"

/** One-line read-only bar showing the URL of the page being replayed. */
export function UrlBar({ url }: { url: string }) {
  return (
    <div className="flex h-8 shrink-0 items-center gap-2 rounded-lg border bg-muted/40 px-2.5 text-xs">
      <GlobeIcon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
      <span
        title={url}
        className="min-w-0 truncate font-[family-name:var(--mini-font-data)]"
      >
        {url}
      </span>
    </div>
  )
}

/** The recorded page in a fixed-ratio frame on a hatched letterbox, with a cursor and ripple at the latest click. */
export function Viewport({
  time,
  url,
  cursor,
  children,
}: {
  time: string
  url: string
  cursor?: { x: number; y: number; ageMs: number }
  children: ReactNode
}) {
  const rippleProgress =
    cursor && cursor.ageMs >= 0 && cursor.ageMs < RIPPLE_MS ? cursor.ageMs / RIPPLE_MS : null
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded-lg border bg-[repeating-linear-gradient(135deg,transparent_0,transparent_6px,var(--border)_6px,var(--border)_7px)] p-3">
      <div
        role="group"
        aria-label={`Recorded page ${url} at ${time}`}
        className="relative aspect-[16/10] w-full max-w-[34rem] overflow-hidden rounded-md border bg-background shadow-sm"
      >
        <div inert className="size-full">
          {children}
        </div>
        {cursor ? (
          <div
            aria-hidden
            className="pointer-events-none absolute"
            style={{ left: `${cursor.x}%`, top: `${cursor.y}%` }}
          >
            {rippleProgress !== null ? (
              <span
                className="absolute rounded-full border-2 border-primary bg-primary/20"
                style={{
                  width: 12 + rippleProgress * 28,
                  height: 12 + rippleProgress * 28,
                  left: -(6 + rippleProgress * 14),
                  top: -(6 + rippleProgress * 14),
                  opacity: 1 - rippleProgress,
                }}
              />
            ) : null}
            <MousePointer2Icon className="relative size-4 fill-foreground text-background" />
          </div>
        ) : null}
      </div>
    </div>
  )
}
