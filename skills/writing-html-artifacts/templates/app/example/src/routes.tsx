import type { ReactElement } from 'react'
import { EditorView } from './views/EditorView'
import { PreviewView } from './views/PreviewView'

export interface ViewDef {
  path: string
  label: string
  component: () => ReactElement
}

export const views: ViewDef[] = [
  { path: '/', label: 'Editor', component: EditorView },
  { path: '/preview', label: 'Preview', component: PreviewView },
]
