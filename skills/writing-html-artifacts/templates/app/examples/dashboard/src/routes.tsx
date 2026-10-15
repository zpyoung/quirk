import type { ReactElement, ReactNode } from 'react'
import { StatusView } from './views/StatusView'

export interface ViewDef {
  path: string
  label: string
  component: () => ReactElement
  summary: ReactNode
}

export const views: ViewDef[] = [
  {
    path: '/',
    label: 'Status',
    component: StatusView,
    summary: (
      <q-stat direction="up-good" points="96.4,96.6,96.9,96.8,97.0,97.2">
        <span slot="label">Checkout success rate</span>
        <span slot="value">97.2%</span>
        <span slot="delta">+0.4 pts</span>
        <span slot="definition">Completed checkouts divided by started checkouts, last 7 days.</span>
      </q-stat>
    ),
  },
]
