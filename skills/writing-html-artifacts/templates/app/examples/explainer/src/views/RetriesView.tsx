import { Heading } from '@astryxdesign/core/Heading'
import { VStack } from '@astryxdesign/core/Layout'

const sub = { subscription: 'sub_812', charge: 'ch_5520' }

const retryGraph = {
  kinds: { ui: 1, worker: 2, database: 3, queue: 4 },
  nodes: [
    { id: 'charge', label: 'Renewal charge', kind: 'worker', detail: '<p>Runs on the billing date, and again for each retry.</p>' },
    { id: 'ok', label: 'Charge succeeded?', shape: 'decision' },
    { id: 'stolen', label: 'Lost or stolen?', shape: 'decision', detail: '<p>Read from the decline code.</p>' },
    { id: 'left', label: 'Retries left?', shape: 'decision', detail: '<p>Four retries in all.</p>' },
    { id: 'wait', label: 'Wait for the next retry', kind: 'queue', detail: '<p>1, 3, 7 and 7 days, moved later for insufficient funds.</p>' },
    { id: 'updated', label: 'Customer updates card', kind: 'ui', detail: '<p>From the link in either email.</p>' },
    { id: 'renewed', label: 'Subscription renewed', kind: 'database' },
    { id: 'pastdue', label: 'Past due', kind: 'database', detail: '<p>Nothing more is charged until the card is updated.</p>' },
  ],
  edges: [
    { from: 'charge', to: 'ok' },
    { from: 'ok', to: 'renewed', label: 'Yes' },
    { from: 'ok', to: 'stolen', label: 'No' },
    { from: 'stolen', to: 'pastdue', label: 'Yes' },
    { from: 'stolen', to: 'left', label: 'No' },
    { from: 'left', to: 'wait', label: 'Yes' },
    { from: 'left', to: 'pastdue', label: 'No' },
    { from: 'wait', to: 'charge', label: 'retry', loop: true },
    { from: 'updated', to: 'charge', label: 'charged at once' },
  ],
  traces: [
    {
      id: 'recovered',
      label: 'Recovered on the second retry',
      steps: [
        { node: 'charge', value: { ...sub, retry: 0, status: 'pending' }, note: 'The renewal charge on the billing date.' },
        { node: 'ok', value: { ...sub, retry: 0, status: 'declined', decline: 'issuer_unavailable' }, note: 'The bank did not answer in time.' },
        { node: 'stolen', value: { ...sub, retry: 0, status: 'declined', decline: 'issuer_unavailable' } },
        { node: 'left', value: { ...sub, retry: 0, status: 'declined', decline: 'issuer_unavailable', retries_left: 4 } },
        { node: 'wait', value: { ...sub, retry: 1, status: 'waiting', wait_days: 1 }, note: 'The first retry waits one day.' },
        { node: 'charge', value: { ...sub, retry: 1, status: 'pending' } },
        { node: 'ok', value: { ...sub, retry: 1, status: 'declined', decline: 'issuer_unavailable' } },
        { node: 'stolen', value: { ...sub, retry: 1, status: 'declined', decline: 'issuer_unavailable' } },
        { node: 'left', value: { ...sub, retry: 1, status: 'declined', decline: 'issuer_unavailable', retries_left: 3 } },
        { node: 'wait', value: { ...sub, retry: 2, status: 'waiting', wait_days: 3 }, note: 'The second retry waits three days.' },
        { node: 'charge', value: { ...sub, retry: 2, status: 'pending' } },
        { node: 'ok', value: { ...sub, retry: 2, status: 'succeeded' }, note: 'This time the bank answers.' },
        { node: 'renewed', value: { ...sub, retry: 2, status: 'active' } },
      ],
    },
    {
      id: 'stolen',
      label: 'Card reported stolen',
      steps: [
        { node: 'charge', value: { ...sub, retry: 0, status: 'pending' } },
        { node: 'ok', value: { ...sub, retry: 0, status: 'declined', decline: 'stolen_card' } },
        { node: 'stolen', value: { ...sub, retry: 0, status: 'declined', decline: 'stolen_card' }, note: 'A retry cannot help, so none is tried.' },
        { node: 'pastdue', value: { ...sub, retry: 0, status: 'past_due', decline: 'stolen_card' } },
      ],
    },
  ],
}

export function RetriesView() {
  return (
    <VStack gap={4}>
      <section>
        <Heading level={2}>What counts as a failure</Heading>
        <p>
          A charge fails when the card network declines it or the bank does not answer in time. A network outage on our side
          is not a failure: those charges are queued and sent again at once, without using up an attempt.
        </p>
      </section>
      <section>
        <Heading level={2}>The retry schedule</Heading>
        <p>The first retry waits one day, the second three days, and the last two seven days apart.</p>
        <q-chart type="bar" summary="The second attempt recovers 34% of failed charges, more than any other attempt.">
          <table>
            <thead>
              <tr><th>Attempt</th><th>Recovered %</th></tr>
            </thead>
            <tbody>
              <tr><td>First retry</td><td>21</td></tr>
              <tr><td>Second retry</td><td>34</td></tr>
              <tr><td>Third retry</td><td>18</td></tr>
              <tr><td>Fourth retry</td><td>9</td></tr>
            </tbody>
          </table>
        </q-chart>
      </section>
      <section>
        <Heading level={2}>Why the reason matters</Heading>
        <p>The decline code decides how long to wait. A card with insufficient funds is more likely to work after payday than after a day.</p>
        <q-table>
          <table>
            <thead>
              <tr><th>Decline reason</th><th>First retry after</th><th className="num">Recovered %</th></tr>
            </thead>
            <tbody>
              <tr><td>Insufficient funds</td><td>3 days</td><td>41</td></tr>
              <tr><td>Bank did not answer</td><td>1 day</td><td>67</td></tr>
              <tr><td>Card expired</td><td>never</td><td>12</td></tr>
              <tr><td>Do not honor</td><td>1 day</td><td>23</td></tr>
            </tbody>
          </table>
        </q-table>
      </section>
      <section>
        <Heading level={2}>When retries stop</Heading>
        <p>
          After the fourth retry fails, or at once for a card reported lost or stolen, the subscription moves to past due.
          Nothing more is charged until the customer updates their card.
        </p>
      </section>
      <section>
        <Heading level={2}>Follow one failed charge</Heading>
        <p>Choose Step through on the graph to watch a charge come back on its second retry, or stop at once for a stolen card.</p>
        <q-flow
          summary="A failed renewal charge stops at once for a lost or stolen card, otherwise waits and retries up to four times before the subscription moves to past due."
          direction="right"
        >
          <script type="application/json">{JSON.stringify(retryGraph)}</script>
        </q-flow>
      </section>
      <section>
        <Heading level={2}>What the customer sees</Heading>
        <p>
          One email after the first failure and one before the last retry, each with a link to update the card. A customer who
          fixes the card between attempts is charged right away instead of waiting for the next one.
        </p>
      </section>
    </VStack>
  )
}
