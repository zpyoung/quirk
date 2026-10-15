import type { ReactElement, ReactNode } from 'react'
import { RetriesView } from './views/RetriesView'

export interface ViewDef {
  path: string
  label: string
  component: () => ReactElement
  summary: ReactNode
}

export const views: ViewDef[] = [
  {
    path: '/',
    label: 'Retries',
    component: RetriesView,
    summary: (
      <p>
        A failed subscription charge is retried up to four times over eleven days, and each retry is timed to the reason
        the card failed. Most recoveries land on the second attempt.
      </p>
    ),
  },
]
