import { useSyncExternalStore } from 'react'

export type ThemeMode = 'auto' | 'light' | 'dark'

const STORAGE_KEY = 'quirk-theme'
const ORDER: ThemeMode[] = ['auto', 'light', 'dark']

function readMode(): ThemeMode {
  const theme = document.documentElement.dataset.theme
  return theme === 'light' || theme === 'dark' ? theme : 'auto'
}

function subscribe(onChange: () => void): () => void {
  const observer = new MutationObserver(onChange)
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  return () => observer.disconnect()
}

/** Sets the theme on <html> and remembers it for the next visit; storage can be blocked, so a failure is ignored. */
export function setThemeMode(mode: ThemeMode): void {
  if (mode === 'auto') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.dataset.theme = mode
  try {
    if (mode === 'auto') window.localStorage.removeItem(STORAGE_KEY)
    else window.localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    // the toggle still works for this page view
  }
}

/** Restores the remembered theme before first paint; the key matches the tier-1 pages. */
export function applyStoredThemeMode(): void {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') document.documentElement.dataset.theme = stored
  } catch {
    // storage blocked: stay on the OS preference
  }
}

export function nextThemeMode(mode: ThemeMode): ThemeMode {
  return ORDER[(ORDER.indexOf(mode) + 1) % ORDER.length]
}

export function useThemeMode(): ThemeMode {
  return useSyncExternalStore(subscribe, readMode, () => 'auto')
}
