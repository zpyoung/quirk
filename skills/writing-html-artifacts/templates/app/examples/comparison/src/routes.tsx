import type { ReactElement, ReactNode } from 'react'
import { OptionsView } from './views/OptionsView'

export interface ViewDef {
  path: string
  label: string
  component: () => ReactElement
  summary: ReactNode
}

export const views: ViewDef[] = [
  {
    path: '/',
    label: 'Options',
    component: OptionsView,
    summary: (
      <p>
        Use Cloud Tasks for the retry worker. It is the only option with per-task scheduling built in, which the
        retry schedule needs, and it costs the least to run.
      </p>
    ),
  },
]
