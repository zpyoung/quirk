/** Props shared by the component kit's custom elements; each element's own attributes are checked by the build's kit check. */
type KitElementProps = {
  children?: import('react').ReactNode
  className?: string
  [attribute: string]: unknown
}

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      'q-tabs': KitElementProps
      'q-chart': KitElementProps
      'q-stat': KitElementProps
      'q-table': KitElementProps
      'q-timeline': KitElementProps
      'q-code': KitElementProps
      'q-diff': KitElementProps
      'q-diff-note': KitElementProps
      'q-board': KitElementProps
      'q-grid': KitElementProps
      'q-panel': KitElementProps
      'q-sidenote': KitElementProps
      'q-compare': KitElementProps
      'q-flow': KitElementProps
      'q-schema': KitElementProps
    }
  }
}

export {}
