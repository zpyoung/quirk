# replay-player

A playback surface that steps through a recorded sequence of states, with transport controls (back 10s, play or pause, skip to the next event, speed), a marker lane over a seek slider, and a side panel of tabs whose lists follow the playhead and seek when an entry's time is clicked. It was studied in Sentry.

## When to use

Use it when the user reviews something that happened over time and needs to jump between the moments that matter:

- A recorded usability test or screen walkthrough: watch the screens, jump to each click or failure, read the notes beside it.
- A recorded meeting or call reviewed against its transcript, with markers for questions, decisions and action items.
- A training video or lecture where the user tags moments and returns to them.
- A game, workout or drive replay: a sequence of states with a log of events on the side.

Do not use it when:

- The record is a list of events with no playback to drive: use `event-timeline`, which has the same timed list without the transport.
- The time axis is a trace of nested, overlapping durations: use `span-waterfall`.
- The user browses many records and peeks at one: use `list-peek`.
- Details open under a row and nothing plays: use `expand-in-place`.
- The user edits the record while viewing it, or wants resizable panes: use `workspace-panes`.
- The page only reports numbers after the fact: use `command-center` for live status, or the `writing-html-artifacts` skill for a static report.

## Anatomy

```
┌───────────────────────────────────────────────────────────────────────┐
│ (P) participant-4                                  Clicks 9  Errors 2 │  header ~64px
│     Desktop browser · 4 minutes ago                                   │
├───────────────────────────────────┬───────────────────────────────────┤
│ [ ◎ https://app.example/recipes ] │ Activity  Console  Network  Errors│  tabs
│ ┌───────────────────────────────┐ │ [ Filter activity            ]    │  filter
│ │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│ │ ● Navigation             ▷ 00:08  │
│ │░░┌─────────────────────────┐░░│ │   /recipes                        │
│ │░░│  recorded page (inert)  │░░│ │ ● Click                  ▷ 00:18  │
│ │░░│        ↖ cursor         │░░│ │   button "Lemon orzo"             │
│ │░░└─────────────────────────┘░░│ │ ───────────── playhead ────────── │
│ │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│ │ ● Error                  ▷ 00:55  │
│ └───────────────────────────────┘ │   TypeError: ...                  │
│ ● ◆ ●   ● ◆ ■ ●     ◆   ■  ● ◆    │              [Jump to current ↓]  │
│ ──────────O───────────────────    │                                   │
│ 00:18                      01:30  │                                   │
│ [⟲10] [▶] [⏭]         − 1× +      │                                   │
└───────────────────────────────────┴───────────────────────────────────┘
          player ~42%                          tabs ~58%

narrow (block under about 48rem wide): header, URL bar, viewport, control bar, then the tabs, stacked.
```

- **Header:** the user's name with an initial, a one-line meta text and a "when" label, and on the right a Clicks and an Errors counter. The counts come from the events. Errors show in the destructive color when above zero.
- **URL bar:** one line showing the current snapshot's URL, truncated, with the full URL in the `title`. Read only.
- **Viewport:** the current snapshot, drawn by the caller, in a fixed 16:10 frame centered in the pane. Space outside the frame is hatched. The frame is inert: nothing inside it takes focus or clicks. A click event with a `point` moves a cursor to that spot and draws a ripple for 700ms after the click.
- **Control bar:** back 10s, a larger filled play or pause button, skip to the next event, and the current time. In the middle a marker lane sits above the seek slider, with the start and end times under it. On the right is the speed stepper. The play button becomes a restart icon at the end.
- **Marker lane:** one mark per click, navigation or error event at its time, with a vertical playhead line through it. Marks differ by shape as well as color: a dot for a click, a diamond for a navigation, a bar for an error. Marks stay in a single row and overlap when events are dense.
- **Seek slider:** a track filled up to the thumb. A floating time with milliseconds follows the pointer over the track and the thumb while dragging.
- **Tabs:** Activity, Console, Network and Errors in that order, then any the caller adds. Each tab holds a filter row and a timed list.
- **Timed list:** entries in time order with an icon, a bold label, an optional detail line and the entry's time at the right as a button. Entries after the playhead are muted. A rule marks the playhead between the last passed entry and the next one.

## Interaction

Keys act while focus is on the page body or anywhere inside the block, and never while typing in the filter input, a textarea or a contenteditable (the base `useHotkeys` default). Keys never use ⌘N, ⌘T, ⌘W or ⌘L.

| Key or action | Does | Notes |
|---------------|------|-------|
| Space | Plays or pauses | Our design. At the end it restarts from 00:00. Ignored when focus is on a button, link or tab, which handle Space themselves. On the slider the slider forwards it, because the keyboard layer skips slider elements. A held key does not repeat. |
| Left / Right | Seeks back or forward 5s | Our design. A held key repeats. Clamped to the start and end. Ignored on a tab, where the arrows move between tabs. On the slider the slider's own handler does the same 5s step. |
| Home / End on the slider | Seeks to the start or the end | Our design, the standard slider keys. PageUp and PageDown step 30s. |
| Back 10s button | Seeks back 10s | Seen in S13-replay-player.png. |
| Play or pause button | Toggles playback | The label changes with the state. Seen in S13-replay-playing.png. |
| Skip button | Seeks to the next click, navigation or error after the playhead | Seen in S13-replay-player.png. With none left it seeks to the end. |
| Click or drag the slider | Seeks to that point | Seen in S13-replay-scrub-seek.png. Playback continues from there if it was playing. |
| Click a mark | Seeks to that event | Our design. Marks are not in the tab order, because the skip button and the list times reach the same moments. |
| Speed − / + | Steps the speed through 0.5×, 1×, 2×, 4× | The stepper is seen in S12-replay-details.png. The step list is our design. Changing speed does not move the playhead. |
| Click an entry's time | Seeks to that entry | Seen in S13-replay-activity-tab.png. Focus stays on the button. |
| Jump to current time | Scrolls the list to the entry at the playhead and resumes following | Seen in S13-replay-activity-tab.png. Appears only while the list is scrolled away from it. |
| Tab arrows | Move between tabs | Radix tabs behavior. |

**Focus rules.**

- Tab moves through the control bar buttons, the slider, the speed buttons, the tab triggers, the filter input and then the entry times. The viewport is never a tab stop.
- Playback never moves focus. Seeking from a list entry leaves focus on that entry's button.
- The slider has `role="slider"` with `aria-valuemin`, `aria-valuemax`, `aria-valuenow` and an `aria-valuetext` such as "00:18 of 01:30".
- The entry at the playhead has `aria-current="true"`. A visually hidden live region says "Playing" or "Paused" when the state changes. It does not announce the time.

**The list follows the playhead.** The entry at the playhead is the last one with a time at or before the playhead. While the list is following, it scrolls just enough to keep that entry in view as the playhead moves or after a seek. If the user scrolls the list so that entry is out of view, following stops and a "Jump to current time" button appears. Clicking an entry's time, or the button, resumes following.

| State | Shows |
|-------|-------|
| No recording, or one with no snapshots or no length | `EmptyState` filling the block. |
| Loading | `LoadingState` filling the block; keys do nothing. |
| Error | `ErrorState` with the message and a Retry button when `onRetry` is given. |
| Tab with no entries | `EmptyState` in the tab body, with the filter row and tab strip still shown. Each tab has its own wording; the Errors tab says there are no errors in this replay. |
| Filter matches nothing | `EmptyState` naming the filter text with a "Clear filter" button. |
| Paused, playing | The play button shows play or pause; the slider fill and the playhead line track the time. |
| Ended | Playback stops at the end, the play button shows a restart icon, and Space restarts. |
| Long lists | The list scrolls inside its own region, and the player pane stays in place. Not virtualized; fine to a few hundred entries. |
| Narrow block (under about 48rem) | The two panes stack, the player first and the tabs below, and the block scrolls. |

## Borrow / Leave out

Borrow:

- The stacked player: URL bar on top, the page letterboxed in the middle, the control bar pinned at the bottom of the pane.
- Control bar order: back 10s, a larger filled play button, skip to next event, current time, a marker lane over a seek slider with the end time, a "− 1× +" speed stepper.
- Markers at event times, one color per event type, with a playhead line through the lane.
- Header with the user and counters at the right.
- Tabs that stay beside the player while open, so the player and playhead stay live.
- Activity rows with an icon, a bold type, a secondary line and a play icon with the time at the right.
- A list that follows the playhead and scrolls it into view, with a rule at the current time and a "Jump to current time" button when scrolled away.
- Clicking an entry's time seeks the player; a floating time with milliseconds while scrubbing.
- A restart icon on the play button at the end.
- The empty tab that keeps its filter row and says there is nothing to show.
- Two-pane split on a wide window, stacked on a narrow one.

Leave out:

- Real browser recordings and DOM inspection: the block plays back snapshots the caller draws. A recording player library is not a dependency.
- The AI summary tab, its failure state and its sparkle art: AI features are not part of the clone.
- Dead and rage click counters, Seen By, Share, Delete, Contact Us and the other header actions.
- The Trace, Memory, Tags and Playlist tabs: a caller can add tabs of its own through `extraTabs`.
- Copy-URL button, browser and OS icons, settings gear and fullscreen.
- The Type dropdown and the Network table's columns, sorting and "View HTML" links: each tab is one filtered list.
- The resizable split with a drag handle: `workspace-panes` owns resizing.
- The studied app's colors, icons, fonts and copy.

## Block API

Files in `gallery/src/patterns/replay-player/`: `registry-item.json`, `index.ts`, `types.ts`, `playback.ts`, `use-playback.ts`, `replay-player.tsx`, `viewport.tsx`, `control-bar.tsx`, `marker-lane.tsx`, `seek-slider.tsx`, `speed-stepper.tsx`, `timed-list.tsx`, `demo.tsx`.

```
CONTRACT: type ReplayEvent = {
  id: string
  at: number                       // ms from the start of the replay
  kind: string                     // "click" | "navigation" | "error" | "console" | "network" or any other string
  label: string
  detail?: string                  // second line, shown in the data font
  tone?: "error"                   // draws the entry in the destructive color
  point?: { x: number; y: number } // click position as percent of the frame; moves the cursor
}

CONTRACT: type ReplaySnapshot<S = unknown> = { id: string; at: number; url: string; state: S }

CONTRACT: type ReplayRecording<S = unknown> = {
  id: string
  user: string
  meta?: string                    // one line under the name
  whenLabel?: string               // e.g. "4 minutes ago"
  durationMs: number
  snapshots: ReplaySnapshot<S>[]   // data only, so a recording can live in a collection
  events: ReplayEvent[]
}

CONTRACT: type ReplayTab = {
  id: string
  label: string
  kinds: string[]                  // events of these kinds appear in the tab
  emptyTitle?: string
  emptyDescription?: string
}

CONTRACT: ReplayPlayer<S>(props: ReplayPlayerProps<S>): JSX.Element

CONTRACT: type ReplayPlayerProps<S> = {
  items: ReplayRecording<S>[]                  // the first plays unless activeId names another
  status?: "loading" | "ready" | "error"       // default "ready"; pass useCollection's status
  error?: Error
  onRetry?: () => void
  renderSnapshot: (snapshot: ReplaySnapshot<S>) => ReactNode   // drawn inside the inert frame
  activeId?: string
  extraTabs?: ReplayTab[]                      // added after Errors
  emptyTitle?: string
  "aria-label"?: string
}

CONTRACT: snapshotAt<S>(snapshots: ReplaySnapshot<S>[], time: number): ReplaySnapshot<S> | undefined
CONTRACT: nextEventTime(events: ReplayEvent[], time: number, durationMs: number): number
CONTRACT: markerPositions(events: ReplayEvent[], durationMs: number): Array<{ id: string; kind: string; at: number; percent: number }>
CONTRACT: advance(time: number, elapsedMs: number, speed: number, durationMs: number): { time: number; ended: boolean }
CONTRACT: seekBy(time: number, deltaMs: number, durationMs: number): number
CONTRACT: activeIndex(entries: ReplayEvent[], time: number): number
CONTRACT: cursorAt(events: ReplayEvent[], time: number): { x: number; y: number; ageMs: number } | undefined
CONTRACT: countByKind(events: ReplayEvent[], kind: string): number
CONTRACT: stepSpeed(speed: number, direction: 1 | -1): number
CONTRACT: formatClock(ms: number, withMillis?: boolean): string
```

`index.ts` exports `ReplayPlayer`, `MarkerLane`, `SeekSlider`, `SpeedStepper`, the pure functions above, `usePlayback` and the types. `demo.tsx` default-exports `Demo`.

- **Pure clock module.** `playback.ts` has no React and takes the time as a parameter, so every rule (which snapshot shows, where the next event is, where marks sit, how far to advance) can be checked without a browser. `use-playback.ts` is the only place that reads a clock: it advances the time from `requestAnimationFrame` while playing.
- **Components built in the block.** `MarkerLane`, `SeekSlider` and `SpeedStepper` take plain props and no provider. The timed list is the block's own `TimedList`; it does not import `event-timeline`.
- **Events and snapshots are sorted by the block** (stable, by `at`), so the caller may pass them in any order. Times past `durationMs` are clamped for the marks and the lists.
- **Snapshot state is data.** `renderSnapshot` receives the snapshot and draws it. Anything the user clicks inside the frame is ignored, because the frame is `inert`.
- The block reads no store. The block renders no `AppShell`, `Toaster` or `TooltipProvider`. States come from the base `EmptyState`, `LoadingState` and `ErrorState`.
- Uses from the base: `useCollection` in the demo only; `useHotkeys` from `react-hotkeys-hook` for Space, Left and Right.
- shadcn components: `button`, `input` and `tabs`. No new dependencies.

`demo.tsx` shows usability-test replays of an invented recipe app, stored through `useCollection("replay-player-demo", seed)`. Participant 4 runs 90 seconds with nine page snapshots (home, recipes, a recipe, a shopping list, the list with a save failure), 12 clicks, six navigations, two errors, console lines and network requests including failed ones, and an extra "Notes" tab fed by a `note` kind. Participant 7 runs 45 seconds with no errors or notes, so the Errors and Notes tabs show their empty states. A "State preview (demo only)" button group (live, empty, loading, error) forces each state, a "Replay (demo only)" group switches recordings through `activeId`, and "Restore sample replays" rewrites the collection. Retry in the error state returns to live. A plain-text footer lists the key hints.

## Sources

[sentry study note](../apps/sentry.md). The key bindings, the snapshot playback and everything marked "our design" are not from a source.

- **Two-pane player and tabs, resizable in the source:** S12-replay-details.png (player about 42%, tabs about 58%), S7-t0257.png. The resize handle is left out.
- **Stacked layout on a narrow window:** S13-replay-player.png.
- **Header with user and counters:** S12-replay-details.png, S13-replay-player.png. Only clicks and errors are kept.
- **URL bar above the page:** S7-t0257.png, S12-replay-details.png.
- **Page letterboxed in the player, a click shown as a cursor with a ripple:** S7-t0257.png.
- **Control bar order, larger play button, speed stepper:** S12-replay-details.png, S13-replay-player.png.
- **Marker lane over a slider, one color per type, playhead through the lane:** S12-replay-details.png, S12 text ("Timeline"), S13-replay-player.png. Shape per type is our design.
- **Play turns to pause, track fills, playhead advances:** S13-replay-playing.png.
- **Click the slider to seek, floating time with milliseconds, list scrolls to the nearest entry:** S13-replay-scrub-seek.png.
- **Tabs stay beside the live player:** S12-replay-details-tags.png.
- **Tab order Activity, Console, Network, Errors:** S13-replay-player.png, S12-replay-details.png.
- **Activity rows, a rule at the current time:** S12-replay-details.png, S7-t0242.png.
- **List synced with the player, auto-scrolls, Jump to current timestamp, restart at the end:** S13-replay-activity-tab.png, S12 text ("Activity").
- **Network entries seek from their timestamp, a visual indicator follows playback:** S13-replay-network-tab.png, S12 text ("Network").
- **Console tab holds messages that Activity does not:** S12 text ("Console").
- **Empty tab keeps its filter row and says there is nothing to show:** S13-replay-errors-tab-empty.png.
- **Errors both seek the player and link to an issue:** S12-replay-details.png. The issue link is left out.
- **Our design:** Space and Left/Right keys and their 5s step, the slider's Home, End, PageUp and PageDown, the 0.5× to 4× speed steps, clickable marks, mark shapes, the hatched letterbox and fixed frame ratio, the inert frame, following and the away state, muted future entries, the extra tabs prop, snapshot playback from data, the filter inputs, and the empty, loading and error states.
