import { Badge } from '@astryxdesign/core/Badge'
import { Banner } from '@astryxdesign/core/Banner'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { Text } from '@astryxdesign/core/Text'
import { useFlags } from '../flags'
import './preview.css'

export function PreviewView() {
  const { flags } = useFlags()
  const live = flags.filter((flag) => flag.enabled)
  const config = Object.fromEntries(live.map((flag) => [flag.name, { rollout: flag.rollout, owner: flag.owner }]))

  return (
    <VStack gap={3}>
      <Banner
        status={live.length ? 'info' : 'warning'}
        title={`${live.length} of ${flags.length} flags are on`}
        description="This is what the editor would hand to the service."
        collapsible={false}
      />
      <HStack gap={1} wrap="wrap">
        {flags.map((flag) => (
          <Badge key={flag.id} variant={flag.enabled ? 'success' : 'neutral'} label={`${flag.name}${flag.enabled ? ` ${flag.rollout}%` : ' off'}`} />
        ))}
      </HStack>
      <Heading level={2}>Config</Heading>
      <pre className="q-config" aria-label="Generated config">{JSON.stringify(config, null, 2)}</pre>
      <Text type="supporting" color="secondary">Edits stay in this page until you reload it.</Text>
    </VStack>
  )
}
