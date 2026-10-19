import { Heading } from '@astryxdesign/core/Heading'
import { VStack } from '@astryxdesign/core/Layout'

const release = { service: 'checkout', version: '2.4.1', previous: '2.4.0' }

const deploySequence = {
  kinds: { person: 1, service: 3, ui: 2 },
  participants: [
    { id: 'engineer', label: 'Engineer', kind: 'person' },
    { id: 'deploy', label: 'Deploy CLI', kind: 'service' },
    { id: 'cluster', label: 'Cluster', kind: 'service', detail: '<p>Splits traffic between the old and new version.</p>' },
    { id: 'dashboard', label: 'Canary dashboard', kind: 'ui' },
    { id: 'channel', label: 'Release channel', kind: 'ui' },
  ],
  steps: [
    { from: 'engineer', to: 'deploy', label: 'deploy --canary', type: 'call', id: 'canary' },
    { from: 'deploy', to: 'cluster', label: 'send 5% to new version', type: 'call', id: 'shift-5' },
    { from: 'cluster', to: 'deploy', label: 'canary live', type: 'reply', id: 'canary-live' },
    { from: 'deploy', to: 'engineer', label: 'canary started', type: 'reply', id: 'canary-started' },
    { note: 'wait ten minutes', over: ['engineer'] },
    { from: 'engineer', to: 'dashboard', label: 'read error rates', type: 'call', id: 'read' },
    { from: 'dashboard', to: 'engineer', label: 'old and new error rate', type: 'reply', id: 'rates' },
    {
      fragment: 'alt',
      branches: [
        {
          label: 'within 0.2 points',
          steps: [
            { from: 'engineer', to: 'deploy', label: 'deploy --promote', type: 'call', id: 'promote' },
            { from: 'deploy', to: 'cluster', label: 'send 100% to new version', type: 'call', id: 'shift-100' },
            { from: 'cluster', to: 'deploy', label: 'promoted', type: 'reply', id: 'promoted' },
            { from: 'deploy', to: 'engineer', label: 'done', type: 'reply', id: 'promote-done' },
          ],
        },
        {
          label: 'worse by more than 0.2',
          steps: [
            { from: 'engineer', to: 'deploy', label: 'deploy --rollback', type: 'call', id: 'rollback' },
            { from: 'deploy', to: 'cluster', label: 'return to last healthy', type: 'call', id: 'restore' },
            { from: 'cluster', to: 'deploy', label: 'rolled back', type: 'reply', id: 'restored' },
            { from: 'deploy', to: 'engineer', label: 'done', type: 'reply', id: 'rollback-done' },
            { from: 'engineer', to: 'channel', label: 'post the version', type: 'async', id: 'post' },
          ],
        },
      ],
    },
  ],
  traces: [
    {
      id: 'promoted',
      label: 'Canary promoted',
      steps: [
        { message: 'canary', value: { ...release, new_traffic_pct: 0 } },
        { message: 'shift-5', value: { ...release, new_traffic_pct: 5 } },
        { message: 'canary-live', value: { ...release, new_traffic_pct: 5, pods_ready: 3 } },
        { message: 'canary-started', value: { ...release, new_traffic_pct: 5, pods_ready: 3 } },
        { message: 'read', value: { ...release, new_traffic_pct: 5 }, note: 'Ten minutes after the canary started.' },
        { message: 'rates', value: { ...release, new_traffic_pct: 5, error_rate_old: 0.41, error_rate_new: 0.48 }, note: '0.07 points apart, inside the 0.2 limit.' },
        { message: 'promote', value: { ...release, new_traffic_pct: 5 } },
        { message: 'shift-100', value: { ...release, new_traffic_pct: 100 } },
        { message: 'promoted', value: { ...release, new_traffic_pct: 100, pods_ready: 12 } },
        { message: 'promote-done', value: { ...release, new_traffic_pct: 100, pods_ready: 12 } },
      ],
    },
    {
      id: 'rolled-back',
      label: 'Canary rolled back',
      steps: [
        { message: 'canary', value: { ...release, new_traffic_pct: 0 } },
        { message: 'shift-5', value: { ...release, new_traffic_pct: 5 } },
        { message: 'canary-live', value: { ...release, new_traffic_pct: 5, pods_ready: 3 } },
        { message: 'canary-started', value: { ...release, new_traffic_pct: 5, pods_ready: 3 } },
        { message: 'read', value: { ...release, new_traffic_pct: 5 } },
        { message: 'rates', value: { ...release, new_traffic_pct: 5, error_rate_old: 0.41, error_rate_new: 1.12 }, note: '0.71 points worse, so the canary goes.' },
        { message: 'rollback', value: { ...release, new_traffic_pct: 5 } },
        { message: 'restore', value: { ...release, new_traffic_pct: 0 } },
        { message: 'restored', value: { ...release, new_traffic_pct: 0, running: '2.4.0' }, note: 'About two minutes.' },
        { message: 'rollback-done', value: { ...release, new_traffic_pct: 0, running: '2.4.0' } },
        { message: 'post', value: { ...release, new_traffic_pct: 0, running: '2.4.0' }, note: 'Name the version you rolled back from.' },
      ],
    },
  ],
}

export function RunbookView() {
  return (
    <VStack gap={4}>
      <section>
        <Heading level={2}>Before you start</Heading>
        <Heading level={3}>Check the freeze calendar</Heading>
        <p>Do not deploy during a freeze or in the hour before a peak sale. The calendar lives in the release channel topic.</p>
        <Heading level={3}>Confirm the build</Heading>
        <p>The pipeline for the commit must be green and the image tagged. A red end-to-end stage blocks the deploy.</p>
      </section>
      <section>
        <Heading level={2}>Deploy</Heading>
        <ol>
          <li>Run <code>deploy checkout --canary</code> to send 5% of traffic to the new version.</li>
          <li>Wait ten minutes and read the canary dashboard.</li>
          <li>Run <code>deploy checkout --promote</code> if the error rate is within 0.2 points of the old version.</li>
        </ol>
        <p>Choose Step through on the diagram to follow a release that is promoted, or one that is rolled back.</p>
        <q-sequence summary="The engineer starts a canary, reads the error rates after ten minutes, then either promotes the new version or rolls it back.">
          <script type="application/json">{JSON.stringify(deploySequence)}</script>
        </q-sequence>
      </section>
      <section>
        <Heading level={2}>Verify</Heading>
        <Heading level={3}>Health checks</Heading>
        <p>All pods report ready, and the synthetic checkout in the status page completes in under 5 seconds.</p>
        <Heading level={3}>Metrics to watch</Heading>
        <p>Error rate, p95 latency and the retry queue depth, for thirty minutes after the promote.</p>
      </section>
      <section>
        <Heading level={2}>Roll back</Heading>
        <ol>
          <li>Run <code>deploy checkout --rollback</code>. It returns to the last healthy version in about two minutes.</li>
          <li>Post in the release channel with the version you rolled back from.</li>
          <li>Open an incident if customers saw errors for more than five minutes.</li>
        </ol>
      </section>
      <section>
        <Heading level={2}>Who to call</Heading>
        <p>Payments on-call for gateway errors, Risk on-call for fraud-score errors, and the release manager for anything else.</p>
      </section>
    </VStack>
  )
}
