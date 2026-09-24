import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Banner } from '@astryxdesign/core/Banner'
import { EmptyState } from '@astryxdesign/core/EmptyState'
import { Heading } from '@astryxdesign/core/Heading'
import { HStack, Layout, LayoutContent, LayoutHeader, VStack } from '@astryxdesign/core/Layout'
import { StatusDot } from '@astryxdesign/core/StatusDot'
import { Tab, TabList } from '@astryxdesign/core/TabList'
import { Text } from '@astryxdesign/core/Text'
import { Theme } from '@astryxdesign/core/theme'
import { Token } from '@astryxdesign/core/Token'
import { Tooltip } from '@astryxdesign/core/Tooltip'
import { neutralTheme } from '@astryxdesign/theme-neutral/built'
import type { Export, ReviewState } from './spec-types'
import {
  EXPORT_KIND,
  activeBlindSpots,
  bootstrap,
  carryOver,
  changedItemIds,
  cloneState,
  decisionRecord,
  emptyState,
  gateList,
  isDecisionExport,
  nextTimestamp,
  readPayload,
  useViewerMode,
  type TabSpec,
  type Update,
  type ViewId,
} from './review-state'
import { BoardView } from './views/board-view'
import { ConstraintsView } from './views/constraints-view'
import { CoverageView } from './views/coverage-view'
import { ImpactCertaintyView } from './views/impact-certainty-view'
import { RisksView } from './views/risks-view'
import { ScenariosView } from './views/scenarios-view'
import { ScopeOutGuardProvider } from './views/scope-out-guard'
import { SignOffView } from './views/sign-off-view'
import { SpecView } from './views/spec-view'
import { StateMachineView } from './views/state-machine-view'
import { StoryMapView } from './views/story-map-view'
import type { ViewProps } from './views/view-props'
import './index.css'

type BadgePart = { id: string; one: string; many: string }

const BADGES: Partial<Record<ViewId, BadgePart[]>> = {
  board: [
    { id: 'move-reasons', one: 'change needs a reason', many: 'changes need a reason' },
    { id: 'scope-warnings', one: 'scope warning to resolve', many: 'scope warnings to resolve' },
  ],
  risks: [
    { id: 'assumptions', one: 'assumption to rule on', many: 'assumptions to rule on' },
    { id: 'blind-spots', one: 'blind spot to accept', many: 'blind spots to accept' },
  ],
  scenarios: [{ id: 'scenarios', one: 'scenario to approve', many: 'scenarios to approve' }],
  constraints: [{ id: 'constraints', one: 'constraint to rule on', many: 'constraints to rule on' }],
}

const STAGE_INDICATOR: Record<1 | 2, string> = {
  1: 'Stage 1 of 2 — what should happen',
  2: 'Stage 2 of 2 — what to build',
}

function Shell({ mode, children }: { mode: 'light' | 'dark' | 'system'; children: ReactNode }) {
  return <Theme theme={neutralTheme} mode={mode}>{children}</Theme>
}

function App() {
  const [payloadResult] = useState(readPayload)
  const payload = payloadResult.payload
  const [initial] = useState(() => payload ? bootstrap(payload) : null)
  const [state, setState] = useState<ReviewState>(() => initial?.state ?? emptyState())
  const stateRef = useRef(state)
  stateRef.current = state
  const [seen, setSeen] = useState<Record<string, string>>(() => initial?.seen ?? {})
  const seenRef = useRef(seen)
  seenRef.current = seen
  const [lastExportUpdatedAt, setLastExportUpdatedAt] = useState<string | null>(() => initial?.lastExportUpdatedAt ?? null)
  const lastExportRef = useRef(lastExportUpdatedAt)
  lastExportRef.current = lastExportUpdatedAt
  const [storageOk, setStorageOk] = useState(initial?.storageOk ?? true)
  const defaultView: ViewId = payload && payload.spec.stage === 1 ? 'scenarios' : 'board'
  const [view, setView] = useState<ViewId>(defaultView)
  const [importStatus, setImportStatus] = useState<string | null>(null)
  const mode = useViewerMode()

  const persist = useCallback((next: ReviewState, currentSeen: Record<string, string>, exportedAt: string | null) => {
    if (!payload) return
    try {
      localStorage.setItem(`quirk-logic-spec:${payload.slug}`, JSON.stringify({ state: next, seen: currentSeen, lastExportUpdatedAt: exportedAt, renderId: payload.renderId }))
    } catch {
      setStorageOk(false)
    }
  }, [payload])

  const update = useCallback<Update>((recipe, reviewedItemId) => {
    const current = stateRef.current
    let next = recipe(current)
    if (current.signedAt && next !== current) next = { ...next, signedAt: undefined }
    next = { ...next, updatedAt: nextTimestamp(current.updatedAt) }
    let currentSeen = seenRef.current
    const reviewedHash = reviewedItemId && payload ? payload.itemHashes[reviewedItemId] : undefined
    if (reviewedItemId && reviewedHash !== undefined) {
      currentSeen = { ...currentSeen, [reviewedItemId]: reviewedHash }
      seenRef.current = currentSeen
      setSeen(currentSeen)
    }
    stateRef.current = next
    setState(next)
    persist(next, currentSeen, lastExportRef.current)
  }, [payload, persist])


  const changedIds = useMemo(() => new Set(payload ? changedItemIds(payload.spec, payload.itemHashes, seen) : []), [payload, seen])
  const gates = useMemo(() => payload ? gateList(state, payload.spec) : [], [payload, state])
  const tabs: TabSpec[] = useMemo(() => {
    if (!payload) return []
    const { spec } = payload
    if (spec.stage === 1) {
      return [
        { id: 'scenarios', label: 'Behaviors & scenarios' },
        { id: 'constraints', label: 'Constraints' },
        { id: 'risks', label: 'Risks' },
        { id: 'spec', label: 'Spec text' },
        { id: 'sign-off', label: 'Sign-off' },
      ]
    }
    const result: TabSpec[] = [
      { id: 'board', label: 'Scope board' },
      { id: 'coverage', label: 'Coverage' },
    ]
    if (spec.requirements.some((item) => item.certainty !== null)) result.push({ id: 'heatmap', label: 'Impact × certainty' })
    if (spec.views?.storyMap) result.push({ id: 'story-map', label: 'Story map' })
    if (spec.views?.stateMachine) result.push({ id: 'states', label: 'State machine' })
    result.push(
      { id: 'scenarios', label: 'Behaviors & scenarios' },
      { id: 'constraints', label: 'Constraints' },
      { id: 'risks', label: 'Risks' },
      { id: 'spec', label: 'Spec text' },
      { id: 'sign-off', label: 'Sign-off' },
    )
    return result
  }, [payload])

  useEffect(() => {
    if (payload && initial) persist(initial.state, initial.seen, initial.lastExportUpdatedAt)
  }, [initial, payload, persist])

  useEffect(() => {
    if (!tabs.some((tab) => tab.id === view)) setView(defaultView)
  }, [tabs, view, defaultView])

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!storageOk && (!lastExportUpdatedAt || lastExportUpdatedAt !== state.updatedAt)) {
        event.preventDefault()
        event.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', beforeUnload)
    return () => window.removeEventListener('beforeunload', beforeUnload)
  }, [lastExportUpdatedAt, state.updatedAt, storageOk])

  const createExport = useCallback((): Export => {
    if (!payload) throw new Error('No rendered review data is loaded.')
    return {
      kind: EXPORT_KIND,
      schemaVersion: 2,
      stage: payload.spec.stage,
      slug: payload.slug,
      renderId: payload.renderId,
      exportedAt: new Date().toISOString(),
      signed: Boolean(stateRef.current.signedAt),
      seen: { ...payload.itemHashes },
      state: cloneState(stateRef.current),
      record: decisionRecord(stateRef.current, payload.spec),
    }
  }, [payload])

  const onExport = useCallback((data: Export) => {
    const nextSeen = { ...data.seen }
    seenRef.current = nextSeen
    lastExportRef.current = data.state.updatedAt
    setSeen(nextSeen)
    setLastExportUpdatedAt(data.state.updatedAt)
    persist(stateRef.current, nextSeen, data.state.updatedAt)
  }, [persist])

  const importFile = useCallback((file: File) => {
    if (!payload) return
    void file.text().then((text) => {
      let parsed: unknown
      try { parsed = JSON.parse(text) } catch { setImportStatus('Import failed: file is not valid JSON.'); return }
      if (!isDecisionExport(parsed, payload.slug)) {
        setImportStatus('Import failed: expected a quirk logic spec decisions export for this spec slug.')
        return
      }
      const carried = carryOver(parsed.state, parsed.seen, payload.spec, payload.itemHashes, parsed.renderId, payload.renderId)
      stateRef.current = carried.state
      seenRef.current = carried.seen
      lastExportRef.current = parsed.state.updatedAt
      setState(carried.state)
      setSeen(carried.seen)
      setLastExportUpdatedAt(parsed.state.updatedAt)
      const signatureCleared = Boolean(parsed.state.signedAt && !carried.state.signedAt)
      setImportStatus(carried.changedIds.length
        ? `Imported. ${carried.changedIds.length} changed or new item${carried.changedIds.length === 1 ? '' : 's'} returned to review.`
        : signatureCleared ? 'Imported. The prior signature was cleared because the logic spec changed.' : 'Decision export imported.')
      persist(carried.state, carried.seen, parsed.state.updatedAt)
    }).catch(() => setImportStatus('Import failed: could not read the selected file.'))
  }, [payload, persist])

  const activeSpots = payload ? activeBlindSpots(state, payload.spec) : []
  const openGateCount = gates.filter((gate) => gate.done < gate.total).length

  const remaining = (id: string) => {
    const gate = gates.find((item) => item.id === id)
    return gate ? Math.max(0, gate.total - gate.done) : 0
  }
  const badge = (parts: BadgePart[] | undefined) => {
    if (!parts) return undefined
    const open = parts.map((part) => ({ ...part, n: remaining(part.id) })).filter((part) => part.n > 0)
    const total = open.reduce((sum, part) => sum + part.n, 0)
    if (total === 0) return undefined
    const hint = open.map((part) => `${part.n} ${part.n === 1 ? part.one : part.many}`).join(', ')
    return (
      <Tooltip content={hint}>
        <Token size="sm" color="orange" label={String(total)} description={hint} />
      </Tooltip>
    )
  }

  if (payloadResult.error) {
    return (
      <Shell mode={mode}>
        <VStack padding={6}>
          <Banner status="error" title="Review data error" description={payloadResult.error} />
        </VStack>
      </Shell>
    )
  }
  if (!payload) {
    return (
      <Shell mode={mode}>
        <VStack padding={6}>
          <EmptyState title="No spec loaded" description="Open a rendered review.html to review a spec. This page is the unfilled template." />
        </VStack>
      </Shell>
    )
  }

  const viewProps: ViewProps = { payload, spec: payload.spec, state, update, changedIds, onNavigate: setView }

  return (
    <Shell mode={mode}>
      <ScopeOutGuardProvider>
        <Layout
          height="auto"
          header={
            <LayoutHeader hasDivider label="Review header">
              <VStack gap={2} paddingBlock={3}>
                <HStack gap={2} justify="between" align="center" wrap="wrap">
                  <VStack gap={0.5}>
                    <Text type="label" color="secondary">Logic spec review · {payload.slug}</Text>
                    <Heading level={1}>{payload.spec.title}</Heading>
                    <Text type="label" color="secondary">{STAGE_INDICATOR[payload.spec.stage]}</Text>
                  </VStack>
                  <HStack gap={1} align="center">
                    <StatusDot variant={storageOk ? 'neutral' : 'error'} label={storageOk ? 'Saved in this browser only' : 'Browser storage unavailable'} />
                    <Text type="supporting">{storageOk ? 'Saved in this browser only' : 'Browser storage unavailable'}</Text>
                  </HStack>
                </HStack>
                <Text type="supporting">
                  {state.signedAt
                    ? `Signed ${new Date(state.signedAt).toLocaleString()}`
                    : openGateCount === 0
                      ? 'Every gate is met. Record your verdict on the Sign-off tab.'
                      : `${openGateCount} of ${gates.length} review gates still open`}
                </Text>
                <TabList value={view} onChange={(value) => setView(value as ViewId)} role="tablist" hasDivider>
                  {tabs.map((tab) => <Tab key={tab.id} value={tab.id} label={tab.label} panelId="panel" endContent={badge(BADGES[tab.id])} />)}
                </TabList>
              </VStack>
            </LayoutHeader>
          }
          content={
            <LayoutContent label="Review panel" padding={4} isScrollable={false}>
              <VStack gap={4} paddingBlockEnd={10}>
                {!storageOk ? (
                  <Banner
                    status="error"
                    title="Export before closing"
                    description="Browser storage is unavailable, so your progress may not survive this session. Download or copy your decisions on the Sign-off tab."
                  />
                ) : null}
                <VStack id="panel" role="tabpanel">
                  {view === 'board' ? <BoardView {...viewProps} /> : null}
                  {view === 'risks' ? <RisksView {...viewProps} /> : null}
                  {view === 'scenarios' ? <ScenariosView {...viewProps} /> : null}
                  {view === 'constraints' ? <ConstraintsView {...viewProps} /> : null}
                  {view === 'coverage' ? <CoverageView {...viewProps} /> : null}
                  {view === 'heatmap' ? <ImpactCertaintyView {...viewProps} /> : null}
                  {view === 'story-map' ? <StoryMapView {...viewProps} /> : null}
                  {view === 'states' ? <StateMachineView {...viewProps} /> : null}
                  {view === 'spec' ? <SpecView {...viewProps} /> : null}
                  {view === 'sign-off' ? (
                    <SignOffView {...viewProps} gates={gates} createExport={createExport} onExport={onExport} importStatus={importStatus} onImport={importFile} />
                  ) : null}
                </VStack>
                <Text type="supporting" color="secondary">
                  Local review only. No network connection is used. Render ID: {payload.renderId}
                  {activeSpots.length ? ` · ${activeSpots.length} active blind spot${activeSpots.length === 1 ? '' : 's'}` : ''}
                </Text>
              </VStack>
            </LayoutContent>
          }
        />
      </ScopeOutGuardProvider>
    </Shell>
  )
}

export default App
