import type { ReactElement, ReactNode } from 'react'
import { RunbookView } from './views/RunbookView'

export interface ViewDef {
  path: string
  label: string
  component: () => ReactElement
  summary: ReactNode
}

export const views: ViewDef[] = [
  {
    path: '/',
    label: 'Runbook',
    component: RunbookView,
    summary: <p>How to deploy the checkout service, check it, and roll it back. Written for the on-call engineer.</p>,
  },
]
