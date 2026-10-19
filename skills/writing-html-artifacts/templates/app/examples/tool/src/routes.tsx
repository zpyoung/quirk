import type { ReactElement, ReactNode } from 'react'
import { Heading } from '@astryxdesign/core/Heading'
import { Text } from '@astryxdesign/core/Text'
import { recovered, useEstimate } from './estimate'
import { EstimatorView } from './views/EstimatorView'

export interface ViewDef {
  path: string
  label: string
  component: () => ReactElement
  summary: ReactNode
}

function Result() {
  const { inputs } = useEstimate()
  const { failed, orders, revenue } = recovered(inputs)
  return (
    <div aria-live="polite">
      <Heading level={2}>Recovered each month</Heading>
      <p>{revenue.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })}</p>
      <Text type="supporting" color="secondary">
        {orders.toLocaleString('en-US')} of {failed.toLocaleString('en-US')} failed charges come back.
      </Text>
    </div>
  )
}

export const views: ViewDef[] = [{ path: '/', label: 'Estimator', component: EstimatorView, summary: <Result /> }]
