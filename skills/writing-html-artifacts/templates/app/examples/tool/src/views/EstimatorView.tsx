import { Button } from '@astryxdesign/core/Button'
import { Heading } from '@astryxdesign/core/Heading'
import { VStack } from '@astryxdesign/core/Layout'
import { NumberInput } from '@astryxdesign/core/NumberInput'
import { Text } from '@astryxdesign/core/Text'
import { DEFAULT_INPUTS, useEstimate } from '../estimate'

export function EstimatorView() {
  const { inputs, update } = useEstimate()
  return (
    <VStack gap={3}>
      <Heading level={2}>Your numbers</Heading>
      <Text color="secondary">Start from last month&rsquo;s billing report. The result updates as you type.</Text>
      <NumberInput label="Subscription charges per month" value={inputs.charges} min={0} isIntegerOnly onChange={(charges) => update({ charges })} />
      <NumberInput label="Share of charges that fail (%)" value={inputs.failureRate} min={0} max={100} onChange={(failureRate) => update({ failureRate })} />
      <NumberInput label="Share of failures that retries recover (%)" value={inputs.recoveryRate} min={0} max={100} onChange={(recoveryRate) => update({ recoveryRate })} />
      <NumberInput label="Average order value (USD)" value={inputs.orderValue} min={0} onChange={(orderValue) => update({ orderValue })} />
      <Button label="Reset to the example numbers" variant="secondary" size="sm" onClick={() => update(DEFAULT_INPUTS)} />
    </VStack>
  )
}
