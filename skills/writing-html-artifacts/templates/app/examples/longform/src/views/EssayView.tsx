import { Heading } from '@astryxdesign/core/Heading'
import { VStack } from '@astryxdesign/core/Layout'

export function EssayView() {
  return (
    <VStack gap={4}>
      <section>
        <Heading level={2}>Why we started</Heading>
        <p>
          The four-step checkout had been <q-sidenote>stable for years<span slot="note">Median completion time was 3m 40s, measured on desktop and mobile web.</span></q-sidenote>,
          and that was the problem: nobody owned it. Every step was a separate page with its own validation, and a
          shopper who went back one step could lose what they had typed.
        </p>
        <p>
          Support tickets made the case. One in nine contacts about orders was an address that had been entered twice or
          corrected after payment, and each of those cost more to fix than the order was worth.
        </p>
      </section>
      <section>
        <Heading level={2}>What the old flow was hiding</Heading>
        <p>
          Splitting payment across steps meant three code paths for taking a card, <q-sidenote>one per payment method family<span slot="note">Cards, bank debits and wallets each had their own retry and error copy.</span></q-sidenote>.
          Merging the pages forced us to pick one behavior for each, and in two cases the winner was the version nobody had tested in a year.
        </p>
      </section>
      <section>
        <Heading level={2}>The design we shipped</Heading>
        <p>
          One page, five sections that stay open, and a running total that does not move while the shopper types. Address
          and payment validate as the fields lose focus, and a failed card keeps everything else as it was.
        </p>
      </section>
      <section>
        <Heading level={2}>What went wrong on the way</Heading>
        <p>
          The first rollout reached 10% of traffic and was pulled after two days: autofill filled the billing address
          into the shipping fields <q-sidenote>on one browser<span slot="note">Reported by 38 shoppers; reproduced only on a single mobile browser release.</span></q-sidenote>.
          The fix was small, but the lesson was that a single page puts every mistake in front of the shopper at once.
        </p>
      </section>
      <section>
        <Heading level={2}>What we would do again</Heading>
        <p>
          Ship behind a flag by region, keep the old flow for one release as a fallback, and write the support macro
          before the launch rather than after it. We would also name an owner for the whole flow on day one.
        </p>
      </section>
    </VStack>
  )
}
