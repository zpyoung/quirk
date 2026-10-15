import { Heading } from '@astryxdesign/core/Heading'
import { VStack } from '@astryxdesign/core/Layout'

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
        <Heading level={2}>What the customer sees</Heading>
        <p>
          One email after the first failure and one before the last retry, each with a link to update the card. A customer who
          fixes the card between attempts is charged right away instead of waiting for the next one.
        </p>
      </section>
    </VStack>
  )
}
