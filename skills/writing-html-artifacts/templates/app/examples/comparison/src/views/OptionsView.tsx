import { Heading } from '@astryxdesign/core/Heading'
import { VStack } from '@astryxdesign/core/Layout'

export function OptionsView() {
  return (
    <VStack gap={4}>
      <q-compare recommended="1">
        <table>
          <thead>
            <tr><th>Criterion</th><th>Cloud Tasks</th><th>Pub/Sub</th><th>Self-hosted Redis</th></tr>
          </thead>
          <tbody>
            <tr><th>Delayed delivery</th><td>Built in, up to 30 days</td><td>Not supported</td><td>Sorted set and a poller</td></tr>
            <tr><th>Delivery guarantee</th><td>At least once</td><td>At least once</td><td>At most once without extra work</td></tr>
            <tr><th>Monthly cost at 2M tasks</th><td>$0.80</td><td>$80</td><td>$310 for the cluster</td></tr>
            <tr><th>Per-task rate limits</th><td>Yes</td><td>No</td><td>Written by us</td></tr>
            <tr><th>On-call load</th><td>Low</td><td>Low</td><td>High</td></tr>
            <tr><th>Time to ship</th><td>1 week</td><td>2 weeks</td><td>4 weeks</td></tr>
          </tbody>
        </table>
      </q-compare>
      <section>
        <Heading level={2}>What would change the answer</Heading>
        <p>
          Pub/Sub wins if the worker also has to fan out to other consumers, because Cloud Tasks delivers each task to one
          handler. Redis wins only if tasks must run in under a second, which the retry schedule never needs.
        </p>
      </section>
    </VStack>
  )
}
