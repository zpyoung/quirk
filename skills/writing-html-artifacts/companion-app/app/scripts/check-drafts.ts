import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { postEvent } from '../src/transport'
import type { Actions, Draft, PostResult, Step } from '../src/types'
import { ApproachesView } from '../src/views/approaches'
import { createDraftGate, draftKey, pickDraft, restorePick, retryDelay } from '../src/views/draft'
import { HandOffView } from '../src/views/hand-off'

const failures: string[] = []
const check = (ok: boolean, message: string) => {
  if (!ok) failures.push(message)
}

// the same form rebuilt as a fresh object on every snapshot must not be posted again
{
  const gate = createDraftGate()
  const form = (): Draft => ({ answers: { q1: { selected: ['a'] } }, comment: 'wip' })
  check(!gate.wants('s1', form()), 'the first value of a step (the restored state) is wanted')
  check(!gate.wants('s1', form()), 'an equal rebuilt value is wanted before anything was posted')
  const typed: Draft = { answers: { q1: { selected: ['a'] } }, comment: 'wip!' }
  check(gate.wants('s1', typed), 'a changed value is not wanted')
  await gate.save('s1', typed, async () => 'ok')
  for (let snapshot = 0; snapshot < 5; snapshot += 1) {
    check(!gate.wants('s1', { answers: { q1: { selected: ['a'] } }, comment: 'wip!' }), `an unchanged form posts again after snapshot ${snapshot}`)
  }
  check(gate.wants('s1', form()), 'reverting to the restored content after a post is not wanted')
}

// a failed save stays pending and is retried; an ok or superseded save is settled
{
  const typed: Draft = { answers: {}, comment: 'typed' }
  const results: PostResult[] = ['error', 'error', 'ok']
  const posts: string[] = []
  const post = async (_id: string, value: Draft): Promise<PostResult> => {
    posts.push(draftKey(value))
    return results.shift() ?? 'ok'
  }
  const gate = createDraftGate()
  gate.wants('s1', { answers: {}, comment: '' })
  check(gate.wants('s1', typed), 'a typed change is not wanted')
  check((await gate.save('s1', typed, post)) === 'error', 'a failed save does not report error')
  check(gate.wants('s1', { answers: {}, comment: 'typed' }), 'a draft whose save failed is no longer pending')
  check((await gate.save('s1', typed, post)) === 'error', 'a second failed save does not report error')
  check(gate.wants('s1', typed), 'a draft that failed twice is no longer pending')
  check((await gate.save('s1', typed, post)) === 'ok', 'the retry does not report ok')
  check(!gate.wants('s1', { answers: {}, comment: 'typed' }), 'a saved draft is pending again')
  check(posts.length === 3, `expected three posts for one draft, got ${posts.length}`)
  check(!gate.wants('s1', typed) && posts.length === 3, 'an unchanged saved draft is posted again')
}
{
  const typed: Draft = { answers: {}, comment: 'typed' }
  const gate = createDraftGate()
  gate.wants('s1', { answers: {}, comment: '' })
  check(gate.wants('s1', typed), 'a typed change is not wanted')
  check((await gate.save('s1', typed, async () => 'superseded')) === 'superseded', 'a 409 save does not report superseded')
  check(!gate.wants('s1', typed), 'a superseded draft is retried')
}

// saves for a step are serialized, so an older request can never reach the server after a newer one
{
  const gate = createDraftGate()
  gate.wants('s1', { comment: '' })
  let stored = ''
  let inFlight = 0
  let maxInFlight = 0
  const arrivals: string[] = []
  const releases: ((r: PostResult) => void)[] = []
  const post = (_id: string, value: Draft) => {
    inFlight += 1
    maxInFlight = Math.max(maxInFlight, inFlight)
    arrivals.push(String(value.comment))
    return new Promise<PostResult>((resolve) =>
      releases.push((r) => {
        inFlight -= 1
        if (r === 'ok') stored = String(value.comment)
        resolve(r)
      }),
    )
  }
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0))
  const slow = gate.save('s1', { comment: 'a' }, post)
  const fast = gate.save('s1', { comment: 'b' }, post)
  await settle()
  check(arrivals.join() === 'a', `the newer save reached the server while the older one was in flight: ${arrivals.join()}`)
  check(gate.wants('s1', { comment: 'b' }), 'the newer draft is not pending while the older one is in flight')
  releases[0]('ok')
  await settle()
  check(arrivals.join() === 'a,b', `the newer draft was not posted after the older one settled: ${arrivals.join()}`)
  releases[1]('ok')
  await Promise.all([slow, fast])
  check(stored === 'b', `the server holds "${stored}" instead of the latest edit`)
  check(maxInFlight === 1, `${maxInFlight} draft posts were in flight at once`)
  check(!gate.wants('s1', { comment: 'b' }), 'the latest draft is still pending after it was stored')
}

// while one save is in flight only the latest pending value is kept, and a value equal to the stored one is not posted
{
  const gate = createDraftGate()
  gate.wants('s1', { comment: '' })
  const arrivals: string[] = []
  const releases: ((r: PostResult) => void)[] = []
  const post = (_id: string, value: Draft) => {
    arrivals.push(String(value.comment))
    return new Promise<PostResult>((resolve) => releases.push(resolve))
  }
  const settle = () => new Promise((resolve) => setTimeout(resolve, 0))
  const first = gate.save('s1', { comment: 'a' }, post)
  const rest = [gate.save('s1', { comment: 'b' }, post), gate.save('s1', { comment: 'c' }, post)]
  releases[0]('ok')
  await settle()
  check(arrivals.join() === 'a,c', `expected only the latest pending value after "a", got ${arrivals.join()}`)
  releases[1]('ok')
  check((await Promise.all([first, ...rest])).every((r) => r === 'ok'), 'coalesced saves do not all report the final result')

  const again = gate.save('s1', { comment: 'd' }, post)
  const back = gate.save('s1', { comment: 'c' }, post)
  releases[2]('error')
  check((await Promise.all([again, back])).join() === 'ok,ok', 'a pending value equal to the stored one does not report ok')
  check(arrivals.join() === 'a,c,d', `a pending value equal to the stored one was posted: ${arrivals.join()}`)
}

// a failed in-flight save lets the newer value post; a failure with nothing newer stays an error; a 409 drops the pending value
{
  const gate = createDraftGate()
  gate.wants('s1', { comment: '' })
  const results: PostResult[] = ['error', 'ok']
  const arrivals: string[] = []
  const post = async (_id: string, value: Draft): Promise<PostResult> => {
    arrivals.push(String(value.comment))
    await new Promise((resolve) => setTimeout(resolve, 0))
    return results.shift() ?? 'ok'
  }
  const first = gate.save('s1', { comment: 'a' }, post)
  const second = gate.save('s1', { comment: 'b' }, post)
  check((await first) === 'ok' && (await second) === 'ok' && arrivals.join() === 'a,b', `a failed save blocked the newer value: ${arrivals.join()}`)

  const lone = createDraftGate()
  lone.wants('s1', { comment: '' })
  check((await lone.save('s1', { comment: 'x' }, async () => 'error')) === 'error', 'a lone failed save does not report error')
  check(lone.wants('s1', { comment: 'x' }), 'a lone failed save is no longer pending')

  const gone = createDraftGate()
  gone.wants('s1', { comment: '' })
  const sent: string[] = []
  const post409 = async (_id: string, value: Draft): Promise<PostResult> => {
    sent.push(String(value.comment))
    await new Promise((resolve) => setTimeout(resolve, 0))
    return 'superseded'
  }
  const one = gone.save('s1', { comment: 'a' }, post409)
  const two = gone.save('s1', { comment: 'b' }, post409)
  check((await one) === 'superseded' && (await two) === 'superseded' && sent.join() === 'a', `a 409 must settle without retrying the pending value: ${sent.join()}`)
}

// a save that finishes after the form moved to another step settles nothing there
{
  const gate = createDraftGate()
  gate.wants('s1', { comment: '' })
  let release: (r: PostResult) => void = () => {}
  const late = gate.save('s1', { comment: 'x' }, () => new Promise<PostResult>((resolve) => (release = resolve)))
  gate.wants('s2', { comment: 'x' })
  release('ok')
  await late
  check(gate.wants('s2', { comment: 'y' }), 'the new step lost its change to a save for the old step')
}

check(retryDelay(1) === 1000 && retryDelay(2) === 2000 && retryDelay(3) === 4000, 'the retry wait does not double')
check(retryDelay(5) === 16_000 && retryDelay(50) === 16_000, 'the retry wait is not capped')
check(retryDelay(0) === 1000, 'the retry wait for no failures is not the base')

// a change that is typed and reverted before the timer fires leaves nothing to post
{
  const gate = createDraftGate()
  gate.wants('s1', { answers: {}, comment: '' })
  check(gate.wants('s1', { answers: {}, comment: 'x' }), 'a typed change is not wanted')
  check(!gate.wants('s1', { answers: {}, comment: '' }), 'a reverted change is wanted')
}

// a new step starts from its own restored state
{
  const gate = createDraftGate()
  gate.wants('s1', { answers: {}, comment: 'a' })
  await gate.save('s1', { answers: {}, comment: 'b' }, async () => 'ok')
  check(!gate.wants('s2', { answers: {}, comment: 'b' }), 'the first value of a new step is wanted')
  check(gate.wants('s2', { answers: {}, comment: 'c' }), 'a change on the new step is not wanted')
}

check(draftKey({ answers: { a: { selected: ['x'] }, b: { text: 't' } }, comment: 'c' }) === draftKey({ comment: 'c', answers: { b: { text: 't' }, a: { selected: ['x'] } } }), 'key order changes the draft key')
check(draftKey({ comment: 'a' }) !== draftKey({ comment: 'b' }), 'different drafts share a key')

// restoring a pick
check(restorePick({ pick: 'two' }, ['one', 'two']) === 'two', 'a saved pick is not restored')
check(restorePick({ pick: 'gone' }, ['one', 'two']) === '', 'a pick naming no option is restored')
check(restorePick({ pick: 3 as unknown as string }, ['one']) === '', 'a non-string pick is restored')
check(restorePick(null, ['one']) === '' && restorePick(undefined, ['one']) === '' && restorePick({}, ['one']) === '', 'a missing pick is restored')
check(JSON.stringify(pickDraft('two', 'c')) === '{"answers":{},"comment":"c","pick":"two"}', 'a pick is not part of the draft payload')
check(!('pick' in pickDraft('', 'c')), 'an empty pick is part of the draft payload')

// the views start from the saved pick
const actions: Actions = { submit: async () => 'ok', send: async () => 'ok', saveDraft: async () => 'ok' }
const props = (step: Step, draft: Draft | null) => ({ step: step as never, changed: new Set<string>(), draft, actions, token: 't' })
const viewApproaches = (step: Step, draft: Draft | null) => renderToStaticMarkup(createElement(ApproachesView, props(step, draft)))
const viewHandOff = (step: Step, draft: Draft | null) => renderToStaticMarkup(createElement(HandOffView, props(step, draft)))
const base = { id: 's', nonce: 'n', v: 1, stage: 'approaches', title: 'T' }
const approaches = {
  ...base,
  kind: 'approaches',
  approaches: [
    { id: 'one', title: 'One', summary_md: 'a', recommended: true },
    { id: 'two', title: 'Two', summary_md: 'b', recommended: false },
  ],
} as unknown as Step
const handOff = {
  ...base,
  kind: 'hand-off',
  choices: [
    { id: 'plan', label: 'Plan', description: 'p', recommended: true },
    { id: 'stop', label: 'Stop', description: 's', recommended: false },
  ],
} as unknown as Step
const checkedIds = (html: string) => [...html.matchAll(/<input[^>]*type="radio"[^>]*>/g)].filter((m) => /\schecked/.test(m[0])).map((m) => /value="([^"]*)"/.exec(m[0])?.[1])
check(checkedIds(viewApproaches(approaches, null)).length === 0, 'an approach is selected without a draft')
check(checkedIds(viewApproaches(approaches, { pick: 'two' })).join() === 'two', 'the approaches view does not restore the saved pick')
check(checkedIds(viewApproaches(approaches, { pick: 'zzz' })).length === 0, 'the approaches view restores a pick that names no approach')
check(checkedIds(viewHandOff(handOff, { pick: 'stop' })).join() === 'stop', 'the hand-off view does not restore the saved pick')

// the draft request names its step and a 409 is a result, not an error
{
  const sent: { body: Record<string, unknown> }[] = []
  let status = 204
  const realFetch = globalThis.fetch
  globalThis.fetch = (async (_url: unknown, init?: { body?: string }) => {
    sent.push({ body: JSON.parse(init?.body ?? '{}') })
    return new Response(null, { status })
  }) as typeof fetch
  try {
    const boot = { token: 'tok', session: 's' }
    check((await postEvent(boot, 'draft', { comment: 'x' }, { step: 'step-9' })) === 'ok', 'a saved draft is not ok')
    check(sent[0]?.body.step === 'step-9' && !('nonce' in (sent[0]?.body ?? {})), 'the draft body does not carry the step id')
    status = 409
    check((await postEvent(boot, 'draft', { comment: 'x' }, { step: 'step-9' })) === 'superseded', 'a 409 draft is not reported as superseded')
    await postEvent(boot, 'submit', { pick: 'one' }, { nonce: 'n1' })
    check(sent[2]?.body.nonce === 'n1' && !('step' in (sent[2]?.body ?? {})), 'a submit body does not carry just the nonce')
  } finally {
    globalThis.fetch = realFetch
  }
}

if (failures.length) {
  console.error(`drafts-check failed:\n${failures.map((f) => `  - ${f}`).join('\n')}`)
  process.exitCode = 1
} else {
  console.log('drafts-check passed: draft dedupe, pick restore and step-scoped draft posts.')
}
