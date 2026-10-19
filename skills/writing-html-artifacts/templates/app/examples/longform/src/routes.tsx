import type { ReactElement, ReactNode } from 'react'
import { EssayView } from './views/EssayView'

export interface ViewDef {
  path: string
  label: string
  component: () => ReactElement
  summary: ReactNode
}

export const views: ViewDef[] = [
  {
    path: '/',
    label: 'Essay',
    component: EssayView,
    summary: (
      <p>
        Moving checkout to a single page raised completed orders by 4.1% and cut support contacts about address entry,
        but it took two quarters longer than planned because the old flow hid three separate payment code paths.
      </p>
    ),
  },
]
