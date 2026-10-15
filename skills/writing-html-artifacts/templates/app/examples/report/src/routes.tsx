import type { ReactElement, ReactNode } from 'react'
import { Heading } from '@astryxdesign/core/Heading'
import { FindingsView } from './views/FindingsView'

export interface ViewDef {
  path: string
  label: string
  component: () => ReactElement
  summary: ReactNode
  aside?: ReactNode
}

export const views: ViewDef[] = [
  {
    path: '/',
    label: 'Findings',
    component: FindingsView,
    summary: (
      <p>
        Checkout p95 latency is 640 ms, and payment authorization is half of it. Moving the fraud check off the
        request path would cut about 180 ms without touching the payment provider.
      </p>
    ),
    aside: (
      <aside aria-label="How this was measured">
        <Heading level={2}>How this was measured</Heading>
        <p>Server-side spans for 1.2 million checkout requests between 8 and 14 September, excluding bots.</p>
        <p>Times are p95 per stage, so the stages do not add up to the request total.</p>
      </aside>
    ),
  },
]
