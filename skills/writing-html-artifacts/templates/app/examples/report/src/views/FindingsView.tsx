import { Heading } from '@astryxdesign/core/Heading'
import { VStack } from '@astryxdesign/core/Layout'

export function FindingsView() {
  return (
    <VStack gap={4}>
      <section>
        <Heading level={2}>Where the time goes</Heading>
        <q-chart type="bar" horizontal summary="Payment authorization takes 310 ms of the 640 ms p95, more than any other stage.">
          <table>
            <thead>
              <tr><th>Stage</th><th>p95 ms</th></tr>
            </thead>
            <tbody>
              <tr><td>Payment authorization</td><td>310</td></tr>
              <tr><td>Fraud check</td><td>180</td></tr>
              <tr><td>Tax and shipping</td><td>95</td></tr>
              <tr><td>Cart load</td><td>40</td></tr>
              <tr><td>Order write</td><td>35</td></tr>
            </tbody>
          </table>
        </q-chart>
      </section>
      <section>
        <Heading level={2}>The slowest services</Heading>
        <p>Three services account for almost all of the tail. Sort by p95 to see them first.</p>
        <q-table>
          <table>
            <thead>
              <tr><th>Service</th><th className="num">Requests</th><th className="num">p95 ms</th><th>Owner</th></tr>
            </thead>
            <tbody>
              <tr><td>payments-gateway</td><td>1,204,000</td><td>310</td><td>Payments</td></tr>
              <tr><td>fraud-score</td><td>1,198,400</td><td>180</td><td>Risk</td></tr>
              <tr><td>tax-engine</td><td>1,150,200</td><td>95</td><td>Billing</td></tr>
              <tr><td>cart</td><td>3,890,500</td><td>40</td><td>Storefront</td></tr>
              <tr><td>orders</td><td>1,201,900</td><td>35</td><td>Fulfilment</td></tr>
            </tbody>
          </table>
        </q-table>
      </section>
      <section>
        <Heading level={2}>What to change</Heading>
        <p>
          Run the fraud check after the order is written and hold shipment until it clears. Risk has confirmed that
          fewer than 0.3% of orders are reversed after the check, so the order stays safe to accept first.
        </p>
        <p>The payment provider call is already as fast as their contract allows, so it is not worth tuning.</p>
      </section>
    </VStack>
  )
}
