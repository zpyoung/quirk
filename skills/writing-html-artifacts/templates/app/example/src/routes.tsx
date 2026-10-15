import type { ReactElement, ReactNode } from 'react'
import { EditorView } from './views/EditorView'
import { PreviewView } from './views/PreviewView'

export interface ViewDef {
  path: string
  label: string
  component: () => ReactElement
  summary?: ReactNode
  aside?: ReactNode
}

export const views: ViewDef[] = [
  {
    path: '/',
    label: 'Editor',
    component: EditorView,
    summary: <p>Edit each feature flag's state, rollout percent and owner. The Preview tab reads the same flags.</p>,
  },
  {
    path: '/preview',
    label: 'Preview',
    component: PreviewView,
    summary: <p>Which flags are on, at what rollout, and the config they generate.</p>,
  },
]
