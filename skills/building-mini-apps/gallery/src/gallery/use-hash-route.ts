import { useSyncExternalStore } from "react"

function subscribe(listener: () => void) {
  window.addEventListener("hashchange", listener)
  return () => window.removeEventListener("hashchange", listener)
}

/** The pattern slug in `#/<pattern>`, or "" when the hash is empty. */
export function useHashRoute(): string {
  return useSyncExternalStore(subscribe, () =>
    decodeURIComponent(window.location.hash.replace(/^#\/?/, ""))
  )
}
