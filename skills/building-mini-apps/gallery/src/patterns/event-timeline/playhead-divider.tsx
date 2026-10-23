import { cn } from "@/lib/utils"

/** Full-width line marking the playhead between the entries it has reached and those after it. */
export function PlayheadDivider({ time, className }: { time: string; className?: string }) {
  return (
    <li role="presentation" data-mini="playhead" className={cn("list-none", className)}>
      <div
        role="separator"
        aria-label={`Playhead at ${time}`}
        className="flex items-center gap-2 px-3 py-1.5"
      >
        <span aria-hidden className="h-px flex-1 bg-primary" />
        <span className="flex items-center gap-1.5 rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground tabular-nums">
          <span aria-hidden className="size-1.5 rounded-full bg-primary-foreground" />
          Playhead {time}
        </span>
        <span aria-hidden className="h-px flex-1 bg-primary" />
      </div>
    </li>
  )
}
