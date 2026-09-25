import { Card } from '@astryxdesign/core/Layout'
import { Markdown } from '@astryxdesign/core/Markdown'
import { OFFLINE_MARKDOWN_COMPONENTS } from './shared'
import type { ViewProps } from './view-props'

/** Renders the full logic spec markdown Claude generated, offline-safe. */
export function SpecView({ payload }: ViewProps) {
  return (
    <Card>
      <Markdown components={OFFLINE_MARKDOWN_COMPONENTS} headingLevelStart={2} contentWidth="100%">
        {payload.logicMarkdown}
      </Markdown>
    </Card>
  )
}
