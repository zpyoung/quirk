# event-timeline

A vertical, time-ordered list of typed entries, each with an icon, a category, a level, a message and a time, with a search box, a type filter and an order control. In playhead mode the list also follows a moving point in time: later entries dim, a divider marks the point, and clicking an entry's time seeks to it. It was studied in Sentry.

## When to use

Use it when the user reads what happened, in order, and sometimes needs to line it up with a moment:

- A parcel-tracking history: scans, depots, delays and the delivery, newest first, filtered to "delays".
- An audit log of a document's edits, with a playhead that replays the document "as of" a moment.
- A build or deploy log where each step is a typed entry and a failed step is marked.
- A habit, medication or symptom diary read back as a timeline, with a search for one word.
- A recorded meeting's moments (questions, decisions, action items) beside a player that seeks when a time is clicked.

Do not use it when:

- The entries are records you browse and act on, with no time order that matters: use `list-peek` (detail beside a list) or `expand-in-place` (detail inside the row).
- Each entry has a duration and the point is how long things took and how they overlap: use `span-waterfall`.
- The list is a stack of code frames, not events: use `stack-trace`.
- You also need the playback surface itself (transport controls, marker lane, seek slider): use `replay-player`, which holds a timeline like this one in its side panel.
- The user selects rows and applies one action to many: use `bulk-select`.
- The list is the app's main data and needs a table, a board and a calendar: use `view-switcher`.

## Anatomy

```
┌──────────────────────────────────────────────────────────────────┐
│ [🔍 Search entries (/)      ] [Any type ▾] [↓ Newest first] 9 of 14 │  toolbar ~44px
├──────────────────────────────────────────────────────────────────┤
│ ◉ Sync  error · Save failed                       ▷ 15:21:09      │
│ │  Autosave could not reach the server                            │  error row
│ ├───────────────────────────────────────── red rule ────────────  │
│ ○ Edit  info                                      ▷ 15:18:47      │  rows ~52px
│ │  Retyped the Day 3 route                                        │  (two lines)
│ │  Section: Day 3                                                 │
│ ━━━━━━━━━━━━━━━━━━━ ● Playhead 15:00:00 ━━━━━━━━━━━━━━━━━━━━━━━━━  │  divider ~28px
│ ○ Comment  info                                   ▷ 14:52:18      │
│ │  Mira: Moved. Day 2 now starts at 09:15.                        │  reached rows
│ ○ Edit  info                                      ▷ 14:47:05      │
│                                                                   │
│                       [↓ Jump to playhead]                        │  floating, only
└──────────────────────────────────────────────────────────────────┘  when scrolled away
 icon column ~28px · content fills the rest · time column ~100px
```

Rows above the divider in this picture are after the playhead, so they are dimmed. With the order flipped to oldest first, the same divider sits below the reached rows and the dimmed ones follow it.

- **Toolbar:** a search box, a type select, an order button and a live count ("9 of 14 entries" while filtered, "14 entries" otherwise). It wraps onto a second line in a narrow block. In the loading and error states and when there are no entries, its controls are disabled.
- **Entry row:** a round icon on the left, joined to its neighbours by a thin vertical line. First line: the category in bold, the level as a word (info, warning, error), and on the right the time. Second line: the message, wrapping in full. An optional third line holds a detail (a path or selector) in the data font. Each type has its own icon and a tint from the chart tokens.
- **Time:** plain text, or, when the host passes `onSeek`, a small button with a play triangle and the time. The button seeks to that entry's time.
- **Error row:** the entry the host marks `isError`. Its icon circle is outlined in the destructive color, its category and level read as errors, a label ("This event" unless the host renames it) sits beside the level, and a thin destructive rule separates it from the entries on its older side.
- **Playhead divider:** a full-width line in the primary color with a small label "Playhead" and the time. It exists only when `playhead` is a finite number, and sits between the entries the playhead has reached and those after it.
- **Dimmed rows:** entries whose time is after the playhead are drawn at reduced opacity. They stay readable, searchable and clickable.
- **Jump button:** a floating "Jump to playhead" button at the bottom center, shown only in playhead mode while the divider is scrolled out of view.
- **Scroll area:** the list scrolls by itself under the toolbar and is a focus stop, so a list with no seek buttons can still be scrolled from the keyboard.

## Interaction

Every key is our design: the blueprint's key map gives this pattern no binding, and no source shows a keyboard shortcut for a breadcrumb list (the study note lists keyboard use of the issue page as Unseen). Keys act only while focus is on the page body or inside the block, and never while typing in the search box, a textarea or a contenteditable. They also do nothing while focus is on the type select's trigger, which has its own type-ahead.

| Key / action | Does | Notes |
|--------------|------|-------|
| `/` | Focuses the search box | Our design. |
| `o` | Switches between newest first and oldest first | Our design. The order button does the same by click. The scroll position follows the playhead when there is one, and is otherwise left alone. |
| `p` | Jumps to the playhead and resumes following | Our design. Playhead mode only. |
| Esc (in the search box) | Clears the text; with the box already empty, moves focus to the list | Our design. The type filter is not touched. |
| Click or Enter on a time button | Calls `onSeek(time)` with the entry's time and resumes following | Result seen in S13-replay-activity-tab.png and S13-replay-network-tab.png (a play icon and a time that seeks). The follow-on is our design. |
| Click "Jump to playhead" | Scrolls the divider into view and resumes following | Seen in S13-replay-activity-tab.png ("Jump to current timestamp"). |
| Type select | Narrows the list to one type, or "Any type" for all | Seen in S7-t0257.png and S13-replay-activity-tab.png (Type: Any). |
| Order button | Flips the order | Seen in S3-t0627.png (a sort control set to "Newest"). Newest first is the default. |
| Tab | Search, type select, order button, then each time button in list order, then the list | Plain tab order. No roving focus. |

Focus rules:

- Focus never moves by itself. Scrolling to follow the playhead, filtering, and flipping the order leave focus where it was.
- After a seek, focus stays on the time button that was used. Rows are keyed by entry id, so the button survives the re-render.
- Following the playhead is automatic until the user scrolls the divider out of view by hand. Scrolling it back into view, seeking, `p` and the jump button all resume it. Scrolls the block makes itself never count as the user's.
- The current entry (the last one the playhead has reached) carries `aria-current="time"`. The divider is a separator with the label "Playhead at <time>". Level is always written as a word, and the error row says so in text, so nothing depends on color.
- The count is a polite live region, so filtering announces how many entries remain.

| State | Shows |
|-------|-------|
| Empty (no entries) | `EmptyState` filling the list area with a one-line hint and an optional `emptyAction` button. Toolbar controls are disabled. |
| Empty (filters match nothing) | `EmptyState` naming the search text and type, with a "Clear filters" action. The toolbar stays live and the divider is not drawn. Seen in S13-replay-errors-tab-empty.png: the toolbar stays and the body says why it is empty. |
| Loading | `LoadingState` in the list area. Toolbar controls are disabled. |
| Error | `ErrorState` with the message and a Retry button when `onRetry` is given. |
| No playhead | A plain list: nothing dimmed, no divider, no jump button, no `p` key. |
| Playhead before every entry or after every entry | The divider sits at the near or far end of the list and the rest is dimmed or reached as a whole. |
| Playhead moves while the user is scrolled away | The list does not scroll. The jump button stays until the divider is back in view. |
| Equal times | Entries with the same time keep their input order oldest first, and newest first is the exact mirror. An entry at exactly the playhead's time counts as reached. |
| Long message | The message wraps in full. A long detail line wraps too. |
| Many entries | The list scrolls inside its own area. It is not virtualized, which is fine to a few hundred entries. |
| Narrow window | The toolbar wraps. The time column stays on the first line of each row. |

## Borrow / Leave out

Borrow:

- A vertical timeline where each entry is an icon, a bold category, a level word, a message line and a right-aligned time (S13-issue-detail-breadcrumbs.png).
- Newest first as the default for a breadcrumb list, with an order control (S3-t0627.png, S13-issue-detail-breadcrumbs.png).
- A toolbar of type filter, search box and sort control above the list (S3-t0627.png, S7-t0257.png).
- The failing moment drawn in red, with a thin red rule between it and the earlier entry (S3-t0627.png, S6-t0096.png, S13-issue-detail-breadcrumbs.png).
- A round colored icon per event type, joined by a thin vertical line, with a second line in the data font for a path or selector (S7-t0257.png, S7-t0242.png, S12-replay-details.png).
- A play triangle beside the time that seeks the player when clicked (S12-replay-details.png, S13-replay-activity-tab.png, S13-replay-network-tab.png).
- A thin divider across the list at the current time, with the list scrolled so the entry nearest the playhead is visible (S12-replay-details.png, S13-replay-scrub-seek.png).
- A list that follows playback, and a floating jump button when the user has scrolled away from the playhead (S13-replay-activity-tab.png, S13-replay-network-tab.png, S12 text "Activity").
- A toolbar that stays when the filter leaves nothing to show (S13-replay-errors-tab-empty.png).

Leave out:

- The "View 7 more" cap that hides all but the first few entries (S13-issue-detail-breadcrumbs.png). The list scrolls instead.
- Collapsible structured data under an entry and "Copy as" (S13-issue-detail-breadcrumbs.png): `expand-in-place` covers expansion and the app owns exports.
- The time-format toggle and the absolute-versus-relative switch (S9-img-issue-details-breakdown-MAZU5VNB.png, S13-issue-detail-breadcrumbs.png). The host passes one `formatTime`.
- The "View HTML" link, linked issue ids and event ids on error rows (S12-replay-details.png). Those need a real backend; a host can put them in `message`.
- The tab strip over the list (Breadcrumbs, Console, Network, Errors, Trace, Memory, Tags in S7-t0257.png): that is `view-switcher`, or `replay-player` for the full panel.
- A table layout with a LEVEL pill column (S3-t0627.png). Level is a word beside the category.
- Brand look, copy and icon set: icons come from lucide-react and colors from the theme tokens.

## Block API

Files in `gallery/src/patterns/event-timeline/`: `registry-item.json`, `index.ts`, `types.ts`, `timeline.ts`, `entry-row.tsx`, `playhead-divider.tsx`, `event-timeline.tsx`, `demo.tsx`.

```
CONTRACT: type TimelineEntry = {
  id: string
  time: number                                      // milliseconds; entries and the playhead share one scale
  type: string                                      // key into `types`; the type filter lists the distinct values
  category: string                                  // bold first word, e.g. "Edit"
  level: "debug" | "info" | "warning" | "error"
  message: string
  detail?: string                                   // optional third line in the data font
  isError?: boolean                                 // the failing moment: error look and a rule on its older side
}

CONTRACT: type TimelineType = {
  label: string                                     // shown in the type select
  icon: LucideIcon                                  // from lucide-react
  tone?: 1 | 2 | 3 | 4 | 5                          // picks var(--chart-<tone>) for the icon circle; muted when omitted
}

CONTRACT: EventTimeline(props: EventTimelineProps): JSX.Element

CONTRACT: type EventTimelineProps = {
  entries: TimelineEntry[]
  status?: "loading" | "ready" | "error"            // default "ready"; pass useCollection's status
  error?: Error
  onRetry?: () => void
  types?: Record<string, TimelineType>              // an entry whose type is missing gets a plain icon and its type as the label
  defaultOrder?: "newest" | "oldest"                // default "newest"; the order button changes it from there
  playhead?: number                                 // playhead mode when a finite number; omit for a plain timeline
  onSeek?: (time: number) => void                   // turns each time into a button; the host moves the playhead
  formatTime?: (time: number) => string             // default formats the time as mm:ss or h:mm:ss from zero
  errorLabel?: string                               // default "This event"
  emptyTitle?: string
  emptyAction?: { label: string; onClick: () => void }
  "aria-label"?: string
}

CONTRACT: filterEntries(entries: TimelineEntry[], filter: { query: string; type: string | null }): TimelineEntry[]
CONTRACT: sortEntries(entries: TimelineEntry[], order: "newest" | "oldest"): TimelineEntry[]
CONTRACT: buildRows(entries: TimelineEntry[], options: { query: string; type: string | null; order: "newest" | "oldest"; playhead?: number }): TimelineRow[]
CONTRACT: type TimelineRow = { kind: "entry"; entry: TimelineEntry; after: boolean; current: boolean } | { kind: "playhead"; time: number }
```

`index.ts` exports `EventTimeline`, `EntryRow`, `PlayheadDivider`, the pure functions `buildRows`, `entryTypes`, `filterEntries`, `formatOffset` and `sortEntries`, and the types `EventTimelineProps`, `TimelineEntry`, `TimelineFilter`, `TimelineLevel`, `TimelineOrder`, `TimelineRow` and `TimelineType`. `demo.tsx` default-exports `Demo`.

`timeline.ts` is plain TypeScript with no React. It filters (text over category, message, detail and type, case-insensitive, plus an exact type), orders (stable on equal times), and places the playhead. The component only draws what `buildRows` returns, so the dimming, the divider and the current entry are decided in one tested place.

Uses from the base:

- `useCollection` in the demo only; `EventTimeline` takes `entries` and `status` as props and does not read the store.
- `EmptyState`, `LoadingState`, `ErrorState` from `src/components/mini/states.tsx` for every list-area state.
- `useHotkeys` from `react-hotkeys-hook` for `/`, `o` and `p`.
- shadcn components, all pre-installed: `button`, `input` and `select` in the block. No new dependencies.

`demo.tsx` renders neither `AppShell` nor a toaster; the app wraps everything in one `AppShell`. It shows the edit history of an invented document, "Autumn trip itinerary", stored with `useCollection("event-timeline-demo", seed)`: 15 entries over about 80 minutes in five types (edit, comment, share, restore, sync). One entry has a very long message, two share a time, one is a warning, and the autosave failure is marked `isError` with the label "Save failed". A "Replay (demo only)" strip turns playhead mode on or off, plays by stepping the playhead to the next entry every second, and has a slider across the whole span; `onSeek` moves the playhead to the clicked time. A plain-text footer lists the key hints. A "State preview (demo only)" button group (live, empty, loading, error) forces each state; the empty state offers "Restore sample history", and Retry in the error state returns to live.

## Sources

[sentry study note](../apps/sentry.md). The study note's observations come from video frames and docs text; the choices listed under "Our design" are not from a source.

- **Entry anatomy, newest first, "This event" label on the failing entry, capped list, time-format toggle:** `S13-issue-detail-breadcrumbs.png`.
- **Toolbar of type filter, search and sort set to "Newest"; failing entry on top with a thin red rule under it; row heights from about 30px to 45px:** `S3-t0627.png`.
- **Failing row outlined in red; time column with a sort toggle:** `S6-t0096.png`.
- **Section header with search, filter, sort order and time-format buttons; first row is the exception, in red:** `S9-img-issue-details-breakdown-MAZU5VNB.png`.
- **Replay breadcrumb rows: round colored icon, bold label, second line with a selector, time with a play triangle; Type dropdown defaulting to Any beside a full-width search:** `S7-t0257.png`.
- **Chronological event log with an icon and tint per event type:** `S7-t0242.png`.
- **Vertical connector joining the icons, mono second line, right-aligned play arrow and mm:ss, a thin rule across the list at the current time:** `S12-replay-details.png`.
- **Scrubbing scrolls the list so the entry nearest the playhead is visible, with a divider line:** `S13-replay-scrub-seek.png`.
- **Time link that seeks, Type: Any filter, search, and the floating "Jump to current timestamp" button when scrolled away:** `S13-replay-activity-tab.png`.
- **Play icon per timestamp that seeks, the same floating button over a table:** `S13-replay-network-tab.png`.
- **List synced with the player and auto-scrolling during playback; Network timestamps seek the player:** S12 text ("Activity" and "Network" sections).
- **Toolbar stays and the body explains an empty result:** `S13-replay-errors-tab-empty.png`.
- **Our design:** every key (`/`, `o`, `p`, Esc in the search box), dimming entries after the playhead, `aria-current` on the current entry, resuming follow on scroll-back, seek and `p`, the rule's side flipping with the order, the type filter and order control living in one toolbar with a live count, the "Any type" wording, the empty-by-filter state with "Clear filters", the oldest-first mirror, the tie rule, and the demo's replay strip.
