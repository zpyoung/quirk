import { PauseIcon, PlayIcon, RewindIcon, RotateCcwIcon, SkipForwardIcon } from "lucide-react"

import { Button } from "@/components/ui/button"

import { formatClock } from "./playback"
import { MarkerLane } from "./marker-lane"
import { SeekSlider } from "./seek-slider"
import { SpeedStepper } from "./speed-stepper"
import type { ReplayMarker } from "./types"

/** Transport buttons, marker lane over the seek slider, times and the speed stepper. */
export function ControlBar({
  time,
  durationMs,
  playing,
  ended,
  speed,
  markers,
  onToggle,
  onBack,
  onSkip,
  onSeek,
  onStepSpeed,
}: {
  time: number
  durationMs: number
  playing: boolean
  ended: boolean
  speed: number
  markers: ReplayMarker[]
  onToggle: () => void
  onBack: () => void
  onSkip: () => void
  onSeek: (ms: number) => void
  onStepSpeed: (direction: 1 | -1) => void
}) {
  const playLabel = ended ? "Restart" : playing ? "Pause" : "Play"
  const PlayIconFor = ended ? RotateCcwIcon : playing ? PauseIcon : PlayIcon
  return (
    <div className="flex shrink-0 flex-col gap-1 pt-1">
      <div className="px-1">
        <MarkerLane
          markers={markers}
          durationMs={durationMs}
          time={time}
          onSeek={onSeek}
        />
        <SeekSlider
          value={time}
          max={durationMs}
          onChange={onSeek}
          onSpace={onToggle}
        />
        <div className="flex justify-between text-xs text-muted-foreground tabular-nums font-[family-name:var(--mini-font-data)]">
          <span>{formatClock(time)}</span>
          <span>{formatClock(durationMs)}</span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="icon-sm"
          aria-label="Back 10 seconds"
          title="Back 10 seconds"
          onClick={onBack}
        >
          <RewindIcon aria-hidden />
        </Button>
        <Button
          size="icon-lg"
          aria-label={playLabel}
          title={`${playLabel} (Space)`}
          onClick={onToggle}
        >
          <PlayIconFor aria-hidden />
        </Button>
        <Button
          variant="outline"
          size="icon-sm"
          aria-label="Skip to next event"
          title="Skip to next event"
          onClick={onSkip}
        >
          <SkipForwardIcon aria-hidden />
        </Button>
        <div className="ml-auto">
          <SpeedStepper speed={speed} onStep={onStepSpeed} />
        </div>
      </div>
    </div>
  )
}
