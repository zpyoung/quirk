import { useCallback, useMemo, useRef, useState } from 'react'
import { Banner } from '@astryxdesign/core/Banner'
import { VStack } from '@astryxdesign/core/Layout'
import { focusApproaches, loadCompareState, saveCompareState } from '../../compare-state'
import type { Comparison, CompareState, CompareViewProps, TabKey } from '../../compare-types'
import type { ViewId } from '../../review-state'
import type { LogicSpecPayload } from '../../spec-types'
import { ApproachesView } from './approaches-view'
import { BlastView } from './blast-view'
import { ChallengeTray } from './challenge-tray'
import { ControlStrip } from './control-strip'
import { EffortView } from './effort-view'
import { GuidanceView } from './guidance-view'
import { OverviewView } from './overview-view'
import { ScoreDrawer } from './score-drawer'
import { TradeoffsView } from './tradeoffs-view'

interface CompareShellProps {
  payload: LogicSpecPayload
  comparison: Comparison
  view: ViewId
  onView: (view: ViewId) => void
}

/** Stage 3: owns the reviewer's compare state (stored under its own key), the active stage-3 view, the score drawer, the control strip and the challenge tray. Renders nothing on any other view, but stays mounted so state survives tab changes. */
export function CompareShell({ payload, comparison, view, onView }: CompareShellProps) {
  const comparisonId = payload.comparisonId ?? ''
  const [loaded] = useState(() => loadCompareState(payload.slug, comparison, comparisonId))
  const [state, setState] = useState<CompareState>(loaded.state)
  const stateRef = useRef(state)
  const [storageOk, setStorageOk] = useState(loaded.storageOk)
  const [openRequirementId, setOpenRequirementId] = useState<string | null>(null)

  const update = useCallback((recipe: (draft: CompareState) => void) => {
    const next = structuredClone(stateRef.current)
    recipe(next)
    stateRef.current = next
    setState(next)
    if (!saveCompareState(payload.slug, next)) setStorageOk(false)
  }, [payload.slug])

  const goToTab = useCallback((tab: TabKey) => onView(`s3-${tab}`), [onView])
  const approaches = useMemo(() => focusApproaches(comparison, state), [comparison, state])

  if (!view.startsWith('s3-')) return null

  const viewProps: CompareViewProps = {
    comparison,
    comparisonId,
    spec: payload.spec,
    itemHashes: payload.itemHashes,
    state,
    update,
    approaches,
    openRequirement: setOpenRequirementId,
    goToTab,
  }

  return (
    <VStack gap={3}>
      {!storageOk ? (
        <Banner status="error" title="Challenges are not being saved" description="Browser storage is unavailable, so drafts and must-haves are lost when this page closes. Export your challenges before leaving." />
      ) : null}
      <ControlStrip comparison={comparison} spec={payload.spec} state={state} update={update} />
      {view === 's3-guidance' ? <GuidanceView {...viewProps} /> : null}
      {view === 's3-overview' ? <OverviewView {...viewProps} /> : null}
      {view === 's3-approaches' ? <ApproachesView {...viewProps} /> : null}
      {view === 's3-effort' ? <EffortView {...viewProps} /> : null}
      {view === 's3-blast' ? <BlastView {...viewProps} /> : null}
      {view === 's3-tradeoffs' ? <TradeoffsView {...viewProps} /> : null}
      <ChallengeTray slug={payload.slug} renderId={payload.renderId} comparisonId={comparisonId} comparison={comparison} state={state} update={update} />
      <ScoreDrawer {...viewProps} requirementId={openRequirementId} onClose={() => setOpenRequirementId(null)} />
    </VStack>
  )
}
