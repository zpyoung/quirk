import { useEffect, useMemo, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react"
import { CheckIcon, CopyIcon, PinIcon, TriangleAlertIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"

import type { Palette, Span } from "./types"
import { formatDuration, opCategory, opShares, selfTime } from "./waterfall"

const colorOf = (palette: Palette, op: string) =>
  `var(--chart-${palette.get(opCategory(op)) ?? 1})`

function Swatch({ color }: { color: string }) {
  return (
    <span
      aria-hidden
      className="size-2.5 shrink-0 rounded-sm"
      style={{ backgroundColor: color }}
    />
  )
}

function CopyButton({ text, what }: { text: string; what: string }) {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopied(false), 1500)
    return () => window.clearTimeout(timer)
  }, [copied])
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-xs"
      aria-label={copied ? `Copied ${what}` : `Copy ${what}`}
      onClick={() => void copy()}
    >
      {copied ? <CheckIcon aria-hidden /> : <CopyIcon aria-hidden />}
    </Button>
  )
}

function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs tabular-nums">
      {children}
    </span>
  )
}

/**
 * Read-only detail for one span: ID, errors, op and timing, description, the
 * op mix of its descendants and a searchable attribute list whose pin buttons
 * add or remove waterfall columns. Esc, or Close, calls `onClose`.
 */
export function SpanPanel({
  span,
  spans,
  palette,
  origin,
  total,
  pinnedKeys,
  onTogglePin,
  onSelectParent,
  onClose,
}: {
  span: Span
  spans: Span[]
  palette: Palette
  origin: number
  total: number
  pinnedKeys: string[]
  onTogglePin: (key: string) => void
  onSelectParent: (id: string) => void
  onClose: () => void
}) {
  const [attributeQuery, setAttributeQuery] = useState("")
  const color = colorOf(palette, span.op)
  const errors = span.errors ?? []
  const parent = span.parentId === null ? undefined : spans.find((item) => item.id === span.parentId)
  const shares = useMemo(() => opShares(spans, span.id), [spans, span.id])
  const self = useMemo(() => selfTime(spans, span.id), [spans, span.id])
  const share = total > 0 ? Math.round((Math.max(0, span.duration) / total) * 100) : 0

  const attributes = useMemo(() => {
    const needle = attributeQuery.trim().toLowerCase()
    return Object.entries(span.attributes ?? {})
      .filter(([key, value]) => !needle || `${key} ${value}`.toLowerCase().includes(needle))
      .sort(([a], [b]) => a.localeCompare(b))
  }, [span.attributes, attributeQuery])
  const attributeCount = Object.keys(span.attributes ?? {}).length

  const onKeyDown = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key !== "Escape") return
    event.preventDefault()
    onClose()
  }

  return (
    <aside
      aria-label="Span details"
      data-mini="panel"
      onKeyDown={onKeyDown}
      className="flex h-full min-h-0 flex-col bg-background text-sm"
    >
      <div className="flex h-9 shrink-0 items-center gap-2 border-b px-2">
        <Button type="button" variant="ghost" size="xs" onClick={onClose}>
          <XIcon aria-hidden />
          Close
        </Button>
        <span className="flex min-w-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs">
          <Swatch color={color} />
          <span className="truncate">
            {span.op} - {span.description}
          </span>
        </span>
      </div>
      <ScrollArea className="min-h-0 flex-1 [&_[data-slot=scroll-area-viewport]>div]:block!">
        <div className="flex flex-col gap-4 p-4 break-words">
          <div>
            <h2 className="text-base font-semibold">Span</h2>
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <span>ID:</span>
              <code className="truncate font-[family-name:var(--mini-font-data)]">{span.id}</code>
              <CopyButton text={span.id} what="span ID" />
            </div>
          </div>

          {errors.length > 0 ? (
            <div
              role="group"
              aria-label="Errors"
              className="flex flex-col gap-1 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-destructive"
            >
              <div className="flex items-center gap-1.5 text-xs font-medium">
                <TriangleAlertIcon className="size-3.5" aria-hidden />
                {errors.length === 1 ? "1 error" : `${errors.length} errors`}
              </div>
              <ul className="flex flex-col gap-0.5 text-xs">
                {errors.map((message, index) => (
                  <li key={index}>{message}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 font-semibold">
              <Swatch color={color} />
              {span.op}
            </div>
            <div className="text-xl font-semibold tabular-nums">{formatDuration(span.duration)}</div>
            <div className="flex flex-wrap gap-1.5">
              <Chip>{share}% of trace</Chip>
              <Chip>Self time {formatDuration(self)}</Chip>
            </div>
          </div>

          <div className="flex items-start gap-1 rounded-md border bg-muted/40 p-2">
            <code className="min-w-0 flex-1 font-[family-name:var(--mini-font-data)] text-xs break-all whitespace-pre-wrap">
              {span.description}
            </code>
            <CopyButton text={span.description} what="description" />
          </div>

          {shares.length > 0 ? (
            <div className="flex flex-col gap-1.5">
              <h3 className="text-xs text-muted-foreground">Most frequent child span ops</h3>
              <div className="flex flex-wrap gap-1.5">
                {shares.map((item) => (
                  <Chip key={item.category}>
                    <Swatch
                      color={
                        palette.has(item.category)
                          ? `var(--chart-${palette.get(item.category)})`
                          : "var(--muted-foreground)"
                      }
                    />
                    {item.category} {Math.round(item.share * 100)}%
                  </Chip>
                ))}
              </div>
            </div>
          ) : null}

          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
            <dt className="text-muted-foreground">Start</dt>
            <dd className="tabular-nums">{formatDuration(span.start - origin)} into the trace</dd>
            <dt className="text-muted-foreground">Parent</dt>
            <dd className="min-w-0">
              {parent ? (
                <button
                  type="button"
                  className="max-w-full truncate text-left underline-offset-2 hover:underline focus-visible:underline"
                  onClick={() => onSelectParent(parent.id)}
                >
                  {parent.op} - {parent.description}
                </button>
              ) : (
                "None"
              )}
            </dd>
          </dl>

          <section aria-label="Attributes" className="flex flex-col gap-2">
            <h3 className="text-xs font-medium">Attributes</h3>
            {attributeCount === 0 ? (
              <p className="text-xs text-muted-foreground">This span has no attributes.</p>
            ) : (
              <>
                <Input
                  value={attributeQuery}
                  onChange={(event) => setAttributeQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape" && attributeQuery) {
                      event.preventDefault()
                      event.stopPropagation()
                      setAttributeQuery("")
                    }
                  }}
                  placeholder="Search attributes"
                  aria-label="Search attributes"
                  className="h-8"
                />
                {attributes.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No attributes match.</p>
                ) : (
                  <ul className="flex flex-col">
                    {attributes.map(([key, value]) => {
                      const pinned = pinnedKeys.includes(key)
                      return (
                        <li
                          key={key}
                          className="flex items-start gap-2 border-b border-border/60 py-1 text-xs last:border-b-0"
                        >
                          <span className="w-2/5 shrink-0 text-muted-foreground break-all">{key}</span>
                          <span className="min-w-0 flex-1 break-all">{value}</span>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            aria-pressed={pinned}
                            aria-label={`Pin ${key} as a column`}
                            onClick={() => onTogglePin(key)}
                          >
                            <PinIcon className={pinned ? "fill-current" : undefined} aria-hidden />
                          </Button>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </>
            )}
          </section>
        </div>
      </ScrollArea>
    </aside>
  )
}
