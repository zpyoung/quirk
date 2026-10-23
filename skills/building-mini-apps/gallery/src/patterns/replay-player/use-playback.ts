import { useCallback, useEffect, useState } from "react"

import { advance, clamp, seekBy, stepSpeed } from "./playback"

type PlaybackState = { time: number; playing: boolean; speed: number }

/** Playhead state for one recording. The only code in the block that reads a clock. */
export function usePlayback(durationMs: number) {
  const [state, setState] = useState<PlaybackState>({
    time: 0,
    playing: false,
    speed: 1,
  })

  useEffect(() => {
    if (!state.playing) return
    let last = performance.now()
    let frame = requestAnimationFrame(function tick(now) {
      const elapsed = now - last
      last = now
      setState((current) => {
        if (!current.playing) return current
        const next = advance(current.time, elapsed, current.speed, durationMs)
        return { ...current, time: next.time, playing: !next.ended }
      })
      frame = requestAnimationFrame(tick)
    })
    return () => cancelAnimationFrame(frame)
  }, [state.playing, durationMs])

  const toggle = useCallback(() => {
    setState((current) => {
      if (current.playing) return { ...current, playing: false }
      const restart = current.time >= durationMs
      return { ...current, time: restart ? 0 : current.time, playing: true }
    })
  }, [durationMs])

  const seek = useCallback(
    (time: number) =>
      setState((current) => ({ ...current, time: clamp(time, 0, durationMs) })),
    [durationMs]
  )

  const skip = useCallback(
    (deltaMs: number) =>
      setState((current) => ({
        ...current,
        time: seekBy(current.time, deltaMs, durationMs),
      })),
    [durationMs]
  )

  const changeSpeed = useCallback(
    (direction: 1 | -1) =>
      setState((current) => ({
        ...current,
        speed: stepSpeed(current.speed, direction),
      })),
    []
  )

  return { ...state, ended: state.time >= durationMs, toggle, seek, skip, changeSpeed }
}
