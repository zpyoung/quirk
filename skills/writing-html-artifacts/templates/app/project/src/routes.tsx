import type { ReactElement, ReactNode } from 'react'
import { Heading } from '@astryxdesign/core/Heading'
import { VStack } from '@astryxdesign/core/Layout'
import { Text } from '@astryxdesign/core/Text'

export interface ViewDef {
  path: string
  label: string
  component: () => ReactElement
  /** The page's opening answer, shown in the summary region for every shape. */
  summary?: ReactNode
}

function Home() {
  return (
    <VStack gap={2}>
      <Heading level={2}>Start here</Heading>
      <Text>Replace this view in src/routes.tsx. Each entry in views becomes a tab and a hash route.</Text>
    </VStack>
  )
}

/** One entry per view; the first is the landing view and its path must be "/". */
export const views: ViewDef[] = [
  {
    path: '/',
    label: 'Home',
    component: Home,
    summary: <p>Replace this summary with the page's answer in a sentence or two.</p>,
  },
]
