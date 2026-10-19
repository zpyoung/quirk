import { useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

export interface Flag {
  id: string
  name: string
  description: string
  owner: string
  enabled: boolean
  rollout: number
}

export const SEED_FLAGS: Flag[] = [
  { id: 'new-checkout', name: 'new-checkout', description: 'Single-page checkout flow', owner: 'payments', enabled: true, rollout: 25 },
  { id: 'dark-mode', name: 'dark-mode', description: 'Dark theme in the admin', owner: 'design', enabled: true, rollout: 100 },
  { id: 'bulk-export', name: 'bulk-export', description: 'CSV export for large accounts', owner: 'data', enabled: false, rollout: 0 },
  { id: 'smart-retries', name: 'smart-retries', description: 'Retry failed charges on a schedule', owner: 'billing', enabled: true, rollout: 50 },
  { id: 'saved-views', name: 'saved-views', description: 'Per-user saved filters', owner: 'platform', enabled: false, rollout: 10 },
  { id: 'audit-log-v2', name: 'audit-log-v2', description: 'Searchable audit log', owner: 'security', enabled: false, rollout: 0 },
]

const FLAGS_KEY = ['flags']

/**
 * The flag list shared by every view. It lives in the query cache so an edit in one view shows
 * up in the others at once, and a connected app can later swap the seed for a real fetch.
 */
export function useFlags() {
  const client = useQueryClient()
  const { data } = useQuery({
    queryKey: FLAGS_KEY,
    queryFn: () => SEED_FLAGS,
    initialData: SEED_FLAGS,
    staleTime: Infinity,
  })
  const update = useCallback(
    (id: string, patch: Partial<Flag>) =>
      client.setQueryData<Flag[]>(FLAGS_KEY, (flags = SEED_FLAGS) =>
        flags.map((flag) => (flag.id === id ? { ...flag, ...patch } : flag)),
      ),
    [client],
  )
  const reset = useCallback(() => client.setQueryData<Flag[]>(FLAGS_KEY, SEED_FLAGS), [client])
  return { flags: data, update, reset }
}
