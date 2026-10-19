import { useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

export interface Inputs {
  charges: number
  failureRate: number
  recoveryRate: number
  orderValue: number
}

export const DEFAULT_INPUTS: Inputs = { charges: 48000, failureRate: 7, recoveryRate: 55, orderValue: 62 }

const ESTIMATE_KEY = ['estimate']

/** The calculator inputs, shared by the form and the result so the result updates as the shopper types. */
export function useEstimate() {
  const client = useQueryClient()
  const { data } = useQuery({
    queryKey: ESTIMATE_KEY,
    queryFn: () => DEFAULT_INPUTS,
    initialData: DEFAULT_INPUTS,
    staleTime: Infinity,
  })
  const update = useCallback(
    (patch: Partial<Inputs>) => client.setQueryData<Inputs>(ESTIMATE_KEY, (inputs = DEFAULT_INPUTS) => ({ ...inputs, ...patch })),
    [client],
  )
  return { inputs: data, update }
}

export function recovered({ charges, failureRate, recoveryRate, orderValue }: Inputs) {
  const failed = Math.round((charges * failureRate) / 100)
  const orders = Math.round((failed * recoveryRate) / 100)
  return { failed, orders, revenue: orders * orderValue }
}
