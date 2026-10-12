import { Tooltip } from '@astryxdesign/core/Tooltip'
import type { ScoreStatus } from '../../compare-types'

export const STATUS_ORDER: readonly ScoreStatus[] = ['met', 'met with workaround', 'very hard', 'not met']

export const STATUS_META: Record<ScoreStatus, { glyph: string; label: string; color: 'green' | 'yellow' | 'orange' | 'red' }> = {
  met: { glyph: '✓', label: 'Met', color: 'green' },
  'met with workaround': { glyph: '◐', label: 'Met with workaround', color: 'yellow' },
  'very hard': { glyph: '▲', label: 'Very hard', color: 'orange' },
  'not met': { glyph: '✕', label: 'Not met', color: 'red' },
}

/** A score status as an icon on its status color; the icon and an accessible label carry the meaning, never the color alone. `sm` is icon-only with the label on hover; `md` prints the label. */
export function StatusChip({ status, qualifier, size = 'md' }: { status: ScoreStatus; qualifier?: string; size?: 'sm' | 'md' }) {
  const meta = STATUS_META[status]
  const text = qualifier ? `${meta.label} (${qualifier})` : meta.label
  const chip = (
    <span
      {...(size === 'sm' ? { role: 'img', 'aria-label': text } : {})}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        minWidth: 24,
        height: 24,
        padding: size === 'sm' ? '0 6px' : '0 10px',
        boxSizing: 'border-box',
        justifyContent: 'center',
        borderRadius: 12,
        border: `1px solid var(--color-border-${meta.color})`,
        background: `var(--color-background-${meta.color})`,
        color: `var(--color-text-${meta.color})`,
        fontSize: 13,
        fontWeight: 600,
        lineHeight: 1,
        whiteSpace: 'nowrap',
      }}
    >
      <span aria-hidden="true">{meta.glyph}</span>
      {size === 'md' ? <span>{text}</span> : null}
    </span>
  )
  return size === 'sm' ? <Tooltip content={text}>{chip}</Tooltip> : chip
}
