import { Heading } from '@astryxdesign/core/Heading'
import { VStack } from '@astryxdesign/core/Layout'

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
