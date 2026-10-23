import { useState, type ReactNode } from "react"
import { addDays, format, set, startOfDay } from "date-fns"
import { CalendarIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Textarea } from "@/components/ui/textarea"

import { snoozePresets } from "./attention"

function morningOf(day: Date): number {
  return set(day, {
    hours: 8,
    minutes: 0,
    seconds: 0,
    milliseconds: 0,
  }).getTime()
}

function SnoozeBody({
  now,
  onSnooze,
}: {
  now: number
  onSnooze(until: number, note?: string): void
}) {
  const [note, setNote] = useState("")
  const [picking, setPicking] = useState(false)
  const today = startOfDay(now)
  const firstDay = morningOf(today) > now ? today : addDays(today, 1)

  return (
    <div className="flex flex-col gap-2">
      <label className="flex flex-col gap-1 text-xs text-muted-foreground">
        Note (optional)
        <Textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          className="min-h-0 text-sm text-foreground"
          placeholder="Why snooze it?"
        />
      </label>
      <div role="group" aria-label="Snooze until" className="flex flex-col">
        {snoozePresets(now).map((preset) => (
          <Button
            key={preset.label}
            variant="ghost"
            size="sm"
            className="justify-between"
            onClick={() => onSnooze(preset.until, note)}
          >
            {preset.label}
            <span className="text-xs font-normal text-muted-foreground">
              {format(preset.until, "EEE HH:mm")}
            </span>
          </Button>
        ))}
        <Button
          variant="ghost"
          size="sm"
          className="justify-between"
          aria-expanded={picking}
          onClick={() => setPicking((open) => !open)}
        >
          Pick a date
          <CalendarIcon aria-hidden />
        </Button>
      </div>
      {picking ? (
        <Calendar
          mode="single"
          disabled={{ before: firstDay }}
          defaultMonth={firstDay}
          onSelect={(day) => day && onSnooze(morningOf(day), note)}
          className="p-0"
        />
      ) : null}
    </div>
  )
}

/** Popover of snooze choices around `children`, which is the trigger button. */
export function SnoozeMenu({
  now,
  open,
  onOpenChange,
  onSnooze,
  children,
}: {
  now: number
  open: boolean
  onOpenChange(open: boolean): void
  onSnooze(until: number, note?: string): void
  children: ReactNode
}) {
  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent align="start" className="w-64">
        <SnoozeBody
          now={now}
          onSnooze={(until, note) => {
            onOpenChange(false)
            onSnooze(until, note)
          }}
        />
      </PopoverContent>
    </Popover>
  )
}
