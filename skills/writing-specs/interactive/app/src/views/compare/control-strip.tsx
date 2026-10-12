import { Button } from '@astryxdesign/core/Button'
import { Card, HStack, VStack } from '@astryxdesign/core/Layout'
import { SegmentedControl, SegmentedControlItem } from '@astryxdesign/core/SegmentedControl'
import { Selector } from '@astryxdesign/core/Selector'
import { Text } from '@astryxdesign/core/Text'
import { Token } from '@astryxdesign/core/Token'
import type { Comparison, CompareState } from '../../compare-types'
import type { LogicSpec } from '../../spec-types'

interface ControlStripProps {
  comparison: Comparison
  spec: LogicSpec
  state: CompareState
  update: (recipe: (draft: CompareState) => void) => void
}

/** Focus options: every approach, then each pair in approach order, labelled "A vs B". */
function focusOptions(comparison: Comparison): { value: string; label: string }[] {
  const ids = comparison.approaches.map((approach) => approach.id)
  const options = [{ value: 'all', label: `All ${ids.length} approaches` }]
  for (let i = 0; i < ids.length; i += 1) {
    for (let j = i + 1; j < ids.length; j += 1) options.push({ value: `${ids[i]}${ids[j]}`, label: `${ids[i]} vs ${ids[j]}` })
  }
  return options
}

/** The cross-tab view controls: focus picker, conditional-requirements toggle and must-have count. None of them score anything. */
export function ControlStrip({ comparison, spec, state, update }: ControlStripProps) {
  const options = focusOptions(comparison)
  const focus = options.some((option) => option.value === state.focus) ? state.focus : 'all'
  const conditional = spec.requirements.filter((requirement) => requirement.scope !== 'out' && requirement.condition).map((requirement) => requirement.id)

  return (
    <Card padding={2}>
      <VStack gap={1}>
      <HStack gap={3} align="end" wrap="wrap">
        <div style={{ minWidth: 200 }}>
          <Selector
            label="Focus"
            value={focus}
            onChange={(value) => update((draft) => { draft.focus = value })}
            options={options}
          />
        </div>
        {conditional.length > 0 ? (
          <VStack gap={0.5}>
            <Text type="label" color="secondary">{`Conditional requirements (${conditional.join(', ')})`}</Text>
            <SegmentedControl
              label="Conditional requirements"
              size="sm"
              value={state.includeConditional ? 'included' : 'left-out'}
              onChange={(value) => update((draft) => { draft.includeConditional = value === 'included' })}
            >
              <SegmentedControlItem value="included" label="Included" />
              <SegmentedControlItem value="left-out" label="Left out" />
            </SegmentedControl>
          </VStack>
        ) : null}
        <HStack gap={1} align="center">
          <Token size="sm" color={state.stars.length ? 'yellow' : 'default'} label={`★ ${state.stars.length} must-have${state.stars.length === 1 ? '' : 's'}`} description="Stars are a view of what matters to you; they carry no weight and add no totals." />
        </HStack>
      </HStack>
      {state.droppedStars.length > 0 ? (
        <HStack gap={1} align="center" wrap="wrap">
          <Text type="supporting">{`Dropped ${state.droppedStars.length === 1 ? 'a star' : 'stars'} on ${state.droppedStars.join(', ')}: ${state.droppedStars.length === 1 ? 'that requirement is' : 'those requirements are'} no longer scored in this comparison.`}</Text>
          <Button variant="secondary" size="sm" label="Dismiss" onClick={() => update((draft) => { draft.droppedStars = [] })} />
        </HStack>
      ) : null}
      </VStack>
    </Card>
  )
}
