import { useEffect, useRef } from 'react'

const READY_TITLE = '(1) Your turn'

function drawBadge(): string | null {
  const canvas = document.createElement('canvas')
  canvas.width = 32
  canvas.height = 32
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  ctx.fillStyle = '#0a6464'
  ctx.beginPath()
  ctx.arc(16, 16, 14, 0, Math.PI * 2)
  ctx.fill()
  ctx.fillStyle = '#d93025'
  ctx.beginPath()
  ctx.arc(24, 8, 8, 0, Math.PI * 2)
  ctx.fill()
  ctx.strokeStyle = '#ffffff'
  ctx.lineWidth = 2
  ctx.stroke()
  return canvas.toDataURL('image/png')
}

function playTone(audio: AudioContext | null): void {
  if (!audio || audio.state !== 'running') return
  const osc = audio.createOscillator()
  const gain = audio.createGain()
  osc.type = 'sine'
  osc.frequency.value = 880
  gain.gain.setValueAtTime(0.0001, audio.currentTime)
  gain.gain.exponentialRampToValueAtTime(0.15, audio.currentTime + 0.02)
  gain.gain.exponentialRampToValueAtTime(0.0001, audio.currentTime + 0.35)
  osc.connect(gain)
  gain.connect(audio.destination)
  osc.start()
  osc.stop(audio.currentTime + 0.4)
}

function faviconLink(): HTMLLinkElement {
  let link = document.querySelector<HTMLLinkElement>('link[rel~="icon"]')
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  return link
}

/**
 * Ready signal for a background tab: when a new step id arrives while the tab is hidden, sets the title,
 * swaps the favicon for a badge and plays one tone; all three reset on focus.
 */
export function useReadySignal(stepId: string | null): void {
  const lastStep = useRef<string | null | undefined>(undefined)
  const original = useRef<{ title: string; href: string | null } | null>(null)
  const audio = useRef<AudioContext | null>(null)

  useEffect(() => {
    const unlock = () => {
      try {
        audio.current ??= new AudioContext()
        void audio.current.resume()
      } catch {
        // audio unavailable: the tone is skipped
      }
    }
    const reset = () => {
      if (!original.current) return
      document.title = original.current.title
      const link = faviconLink()
      if (original.current.href === null) link.removeAttribute('href')
      else link.href = original.current.href
      original.current = null
    }
    window.addEventListener('pointerdown', unlock)
    window.addEventListener('keydown', unlock)
    window.addEventListener('focus', reset)
    return () => {
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('keydown', unlock)
      window.removeEventListener('focus', reset)
    }
  }, [])

  useEffect(() => {
    const previous = lastStep.current
    lastStep.current = stepId
    if (previous === undefined || !stepId || stepId === previous || !document.hidden) return
    const link = faviconLink()
    original.current ??= { title: document.title, href: link.getAttribute('href') }
    document.title = READY_TITLE
    const badge = drawBadge()
    if (badge) link.href = badge
    try {
      playTone(audio.current)
    } catch {
      // a blocked or closed audio context is not worth surfacing
    }
  }, [stepId])
}
