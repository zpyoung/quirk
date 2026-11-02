import { useEffect, useMemo, useRef, useState } from 'react'
import { Theme } from '@astryxdesign/core/theme'
import { neutralTheme } from '@astryxdesign/theme-neutral/built'
import { readBoot } from './boot'
import { useReadySignal } from './notify'
import { Connecting, NotConnected, ShellView } from './shell'
import { nextThemeMode, setThemeMode, useThemeMode } from './theme'
import { postEvent, useSnapshotFeed } from './transport'
import type { Actions, PostResult, StageId } from './types'

function ThemeToggle() {
  const mode = useThemeMode()
  return (
    <button type="button" className="link-button theme-toggle" onClick={() => setThemeMode(nextThemeMode(mode))}>
      Theme: {mode}
    </button>
  )
}

export default function App() {
  const mode = useThemeMode()
  const boot = useMemo(readBoot, [])
  const feed = useSnapshotFeed(boot !== null)
  const [submittedStepId, setSubmittedStepId] = useState<string | null>(null)
  const [openStage, setOpenStage] = useState<StageId | null>(null)
  const step = feed.snapshot?.step ?? null
  const stepRef = useRef(step)
  stepRef.current = step
  const refresh = feed.refresh

  useReadySignal(step?.id ?? null)

  useEffect(() => {
    setSubmittedStepId(null)
    setOpenStage(null)
  }, [step?.id, step?.nonce])

  const actions = useMemo<Actions>(() => {
    const finish = (result: PostResult, optimisticStep: string | null): PostResult => {
      if (result === 'ok' && optimisticStep) setSubmittedStepId(optimisticStep)
      if (result === 'superseded') setSubmittedStepId(null)
      if (result !== 'error') refresh()
      return result
    }
    return {
      async submit(payload) {
        const current = stepRef.current
        if (!boot || !current) return 'error'
        return finish(await postEvent(boot, 'submit', payload, { nonce: current.nonce }), current.id)
      },
      async send(type, payload, withNonce) {
        if (!boot) return 'error'
        const current = stepRef.current
        const nonce = withNonce ? current?.nonce : undefined
        const result = await postEvent(boot, type, payload, { nonce })
        return finish(result, type === 'edit-decision' && current ? current.id : null)
      },
      saveDraft(stepId, payload) {
        return boot ? postEvent(boot, 'draft', payload, { step: stepId }) : Promise.resolve('error')
      },
    }
  }, [boot, refresh])

  const themeMode = mode === 'auto' ? 'system' : mode
  let body
  if (!boot) body = <NotConnected />
  else if (!feed.snapshot) body = <Connecting paused={feed.paused} />
  else {
    body = (
      <ShellView
        snapshot={feed.snapshot}
        token={boot.token}
        actions={actions}
        paused={feed.paused}
        submittedStepId={submittedStepId}
        openStage={openStage}
        onOpenStage={setOpenStage}
        headerExtras={<ThemeToggle />}
      />
    )
  }
  return <Theme theme={neutralTheme} mode={themeMode}>{body}</Theme>
}
