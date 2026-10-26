import { MinusIcon, PlusIcon } from "lucide-react"

import { Button } from "@/components/ui/button"

import { formatSpeed, SPEEDS } from "./playback"

/** "- 1x +" control that steps through the playback speeds. */
export function SpeedStepper({
  speed,
  onStep,
}: {
  speed: number
  onStep: (direction: 1 | -1) => void
}) {
  return (
    <div role="group" aria-label="Playback speed" className="flex items-center gap-0.5">
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label="Slower"
        disabled={speed <= SPEEDS[0]}
        onClick={() => onStep(-1)}
      >
        <MinusIcon aria-hidden />
      </Button>
      <span
        aria-live="polite"
        className="w-8 text-center text-xs tabular-nums font-[family-name:var(--mini-font-data)]"
      >
        {formatSpeed(speed)}
      </span>
      <Button
        variant="ghost"
        size="icon-xs"
        aria-label="Faster"
        disabled={speed >= SPEEDS[SPEEDS.length - 1]}
        onClick={() => onStep(1)}
      >
        <PlusIcon aria-hidden />
      </Button>
    </div>
  )
}
