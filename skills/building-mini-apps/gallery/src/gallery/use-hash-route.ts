import { useSyncExternalStore } from "react"

function subscribe(listener: () => void) {
  window.addEventListener("hashchange", listener)
  return () => window.removeEventListener("hashchange", listener)
}

function decodeHash(hash: string): string {
  const raw = hash.replace(/^#\/?/, "")
  try {
    return decodeURIComponent(raw)
  } catch {
    return raw
  }
}

/**
 * The pattern slug in `#/<pattern>`, or "" when the hash is empty. A hash with
 * a malformed percent escape is returned undecoded, so it matches no pattern.
 */
export function useHashRoute(): string {
  return useSyncExternalStore(subscribe, () => decodeHash(window.location.hash))
}
