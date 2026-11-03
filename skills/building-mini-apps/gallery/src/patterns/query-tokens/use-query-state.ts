import { useEffect, useEffectEvent, useMemo, useState } from "react"

import { EMPTY_QUERY, queryFromSearch, searchWithQuery } from "./query"
import type { Query, QueryKey } from "./types"

function readUrl(param: string | undefined, keys: string[]): Query | null {
  if (!param || typeof window === "undefined") return null
  return queryFromSearch(window.location.search, param, { keys })
}

/**
 * The query as state that follows `value` when the host passes one and is held locally otherwise.
 * With `urlParam` it reads that search param once on mount, reports it through `onChange` so the
 * host sees it, and rewrites the param on every change with `history.replaceState`, touching only
 * the search part so a hash route survives.
 */
export function useQueryState({
  value,
  defaultValue,
  onChange,
  urlParam,
  keys,
}: {
  value?: Query
  defaultValue?: Query
  onChange?: (query: Query) => void
  urlParam?: string
  keys: QueryKey[]
}): [Query, (next: Query) => void] {
  const names = useMemo(() => keys.map((k) => k.key), [keys])
  const controlled = value !== undefined
  const [inner, setInner] = useState<Query>(
    () => readUrl(urlParam, names) ?? defaultValue ?? EMPTY_QUERY
  )

  const reportUrl = useEffectEvent(() => {
    const fromUrl = readUrl(urlParam, names)
    if (fromUrl) onChange?.(fromUrl)
  })
  useEffect(() => reportUrl(), [])

  const set = (next: Query) => {
    if (!controlled) setInner(next)
    onChange?.(next)
    if (!urlParam) return
    try {
      window.history.replaceState(window.history.state, "", searchWithQuery(window.location.href, urlParam, next))
    } catch {
      // some sandboxed frames refuse replaceState; the query still works without the address
    }
  }
  return [controlled ? value : inner, set]
}
