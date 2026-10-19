import { VStack } from '@astryxdesign/core/Layout'

export function StatusView() {
  return (
    <VStack gap={4}>
      <q-grid>
        <q-panel span="2">
          <h3>Error rate</h3>
          <q-chart type="line" summary="The checkout error rate fell from 3.4% to 2.8% over the last six days.">
            <table>
              <thead>
                <tr><th>Day</th><th>Error rate %</th></tr>
              </thead>
              <tbody>
                <tr><td>Mon</td><td>3.4</td></tr>
                <tr><td>Tue</td><td>3.3</td></tr>
                <tr><td>Wed</td><td>3.3</td></tr>
                <tr><td>Thu</td><td>3.0</td></tr>
                <tr><td>Fri</td><td>2.9</td></tr>
                <tr><td>Sat</td><td>2.8</td></tr>
              </tbody>
            </table>
          </q-chart>
        </q-panel>
        <q-panel>
          <h3>Latency</h3>
          <q-stat direction="down-good" points="410,380,350,330,320,310">
            <span slot="label">p95 response time</span>
            <span slot="value">310 ms</span>
            <span slot="delta">-100 ms</span>
            <span slot="definition">95th percentile of checkout requests, last 7 days.</span>
          </q-stat>
        </q-panel>
        <q-panel>
          <h3>Open incidents</h3>
          <p>None. The last one closed 9 days ago.</p>
        </q-panel>
        <q-panel span="2">
          <h3>Queue depth</h3>
          <q-chart type="area" summary="The retry queue peaks at 1,900 tasks around midday and drains overnight.">
            <table>
              <thead>
                <tr><th>Hour</th><th>Tasks</th></tr>
              </thead>
              <tbody>
                <tr><td>00</td><td>120</td></tr>
                <tr><td>04</td><td>40</td></tr>
                <tr><td>08</td><td>980</td></tr>
                <tr><td>12</td><td>1900</td></tr>
                <tr><td>16</td><td>1300</td></tr>
                <tr><td>20</td><td>400</td></tr>
              </tbody>
            </table>
          </q-chart>
        </q-panel>
        <q-panel span="2">
          <h3>Recent deploys</h3>
          <q-table>
            <table>
              <thead>
                <tr><th>Service</th><th>Version</th><th>When</th><th>Result</th></tr>
              </thead>
              <tbody>
                <tr><td>checkout-web</td><td>2.41.0</td><td>Today 09:12</td><td>Healthy</td></tr>
                <tr><td>payments-gateway</td><td>5.8.3</td><td>Yesterday 16:40</td><td>Healthy</td></tr>
                <tr><td>fraud-score</td><td>1.19.1</td><td>Yesterday 11:05</td><td>Rolled back</td></tr>
              </tbody>
            </table>
          </q-table>
        </q-panel>
      </q-grid>
    </VStack>
  )
}
