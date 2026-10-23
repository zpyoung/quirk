# command-center

Status tiles grouped in named sections, each with an icon that toggles and a body that opens details, beside a queue of items that need the user, who can acknowledge, snooze or resolve each one. Studied from Home Assistant's dashboard plus the attention queues of PagerDuty and incident.io.

## When to use

Use it when the user watches a set of things and acts on whichever ones need them:

- A smart-home or workshop overview: lights, locks, temperatures and a "door left open" queue.
- A personal ops board: backups, servers, build status and subscriptions, with "backup failed" and "cert expires" items.
- A household or small-business watchlist: bills due, battery levels, stock levels, with some items that no tile represents.
- A project or account monitor: one tile per project or account, each flagging when a number crosses a line.

Do not use it when:

- The items are records you browse and edit, with no live state to watch: use `list-peek`, where the detail opens beside a list.
- The same records need a table, a board and a calendar: use `view-switcher`.
- The main job is editing the properties of one selected thing: use `inspector`.
- Actions are the main thing and the user finds them by typing: use `action-palette`. A command center shows state first.
- The page only reports and nothing on it can be acted on (charts, KPIs, a status report): use the `writing-html-artifacts` skill. This pattern has no chart panels.

## Anatomy

```
┌───────────────────────────────────────────────────────────────────────┐
│ Sample data · loaded 07:05          ◉ Live · updated 07:05  [pause]   │
│ [Front door locked] [2 lights on] [Living room 20.5°]  [3 need you]   │
├───────────────────────────────────────────────────┬───────────────────┤
│ SECURITY                                          │ NEEDS YOU         │
│ ┌────────────────┐ ┌────────────────┐             │ Now  2            │
│ │ ⏻ Front door   │ │ ⏻ Garage door  │             │ ▸ NAS backup      │
│ │   Locked       │ │   Closed       │             │   failed          │
│ └────────────────┘ └────────────────┘             │   Open · 20 min   │
│ CLIMATE                                           │ ▾ Front door      │
│ ┌────────────────┐ ┌────────────────┐             │   unlocked        │
│ │ 🌡 Living room │ │ ∿ Basement hum │             │   [Acknowledge a] │
│ │   20.5° · 21°  │ │   58%  ╱╲╱     │             │   [Snooze s]      │
│ │   [-]  21  [+] │ │ ⚠ Needs you    │             │   [Resolve r]     │
│ └────────────────┘ └────────────────┘             │   Timeline        │
│ ...                                               │ Later  1          │
└───────────────────────────────────────────────────┴───────────────────┘

narrow (under about 768 px):
┌──────────────────────────┐
│ Sample data · Live 07:05 │
│ [3 need you]             │
│ ▸ 3 need you             │  ← collapsed strip, expands in place
│ SECURITY                 │
│ ┌──────────────────────┐ │
│ │ ⏻ Front door  Locked │ │
│ └──────────────────────┘ │
│ ...                      │
└──────────────────────────┘
```

- **Header**: the source label from the app, plus "loaded HH:mm" when given, and on the right the refresh state: Live with the last update time and a pause button, Paused with Resume, or Stale since a time. With no refresh function only the source label shows.
- **Refresh error banner**: appears under the header only while a refresh has failed. It says "Couldn't refresh:" plus the message, and has a Retry button. The last good tile values stay on screen.
- **Badge row**: pill badges the app computes ("2 lights on"), then one "N need you" badge that focuses the queue. A badge with a `tileId` opens that tile's details. The row is hidden when there are no summaries and nothing needs the user.
- **Tile sections**: a small uppercase heading per section, in order of first appearance in the data. Under it a grid of tiles in data order, at least 11rem wide each.
- **Tile**: an icon button on the left that toggles, then a body button with the name, the state in text, and optional lines: "Needs you" or "Acknowledged" when the tile has an active item, "Stale · Updated 3 h ago" when it is stale, and a sparkline for numeric tiles with history. Level tiles that are on show a slider under the body. Target tiles show a minus, the value and a plus. Sensor tiles have a plain icon and no toggle.
- **Queue column**: on the right, 20rem wide, headed "Needs you". Items are grouped Now then Later, each group with a count, newest first. A row shows the title, the status as text plus an icon, and "N min ago". An expanded row shows Acknowledge, Snooze and Resolve with key hints, an "Open <tile>" link when the item has a tile, and the timeline.
- **Details dialog**: a centered dialog for one tile: name and section, the state in large text with a toggle button, the exact last-update time, a "Stale" marker, a taller sparkline with a text summary, and the linked item's actions and timeline below.

## Interaction

Queue keys fire only while focus is inside the queue and not in an input, textarea or select, and they are off while the snooze choices are open. They come from `useHotkeys`. No source shows a keyboard shortcut for acknowledge, snooze or resolve (Unseen in both the pagerduty and incident-io notes), so every key is our design.

| Key | Does | Notes |
|-----|------|-------|
| `j` / `k` | Select the next / previous queue item and move focus to its row | Our design. Stops at the ends. If a row is expanded, the expansion follows the selection. |
| `a` | Acknowledge the selected item | Our design. Does nothing unless the item is open. The item stays in the queue and in place. |
| `s` | Expand the selected item and open its snooze choices | Our design. |
| `r` | Resolve the selected item | Our design. No confirmation. Selection and focus move to the neighbouring item. |
| Enter | Expand or collapse the selected item | Our design. Only when the queue container itself has focus; on a focused row, Enter activates the row's own button, which does the same. |
| Click row | Select it and toggle its detail | Our design. |
| Click tile icon | Toggle the tile; a `sensitive` tile asks first | Result seen in S1-icon-toggled and S4 text (home-assistant). The confirm is our design. |
| Click tile body | Open the details dialog | Seen in S1-light-moreinfo (home-assistant). |
| Click summary badge | Open that tile's details when the badge has a `tileId` | Seen in S1-badge-moreinfo (home-assistant). |
| Click "N need you" badge | Focus the queue; on a narrow window, open the strip first | Our design. |
| Level slider | Set the level on release or blur | Slider acting at once is seen in S1-overview (home-assistant). The commit moment is our design. |
| Target minus / plus | Change the target by 0.5 at once, with no confirm | Seen in S1-thermostat-plus (home-assistant). |
| Pause / Resume / Retry | Stop refreshing, restart it, or run the failed refresh again | Our design. |
| Tab | Plain tab order through each tile's buttons, section by section | Our design. No roving focus in the grid. |
| Esc | Close the dialog, confirm or snooze choices; focus returns to what opened it | Our design. Keyboard use of the dashboard is Unseen in the home-assistant note. |

Focus rules:

- Opening a tile's details from a tile button, the "Open <tile>" link or a badge returns focus to that element when the dialog closes. If the confirm dialog was opened from a button, focus returns to that button.
- Focusing a queue row selects it, so `j`/`k` and the action keys work after a Tab or a click.
- After resolving or snoozing, selection and focus go to the next item, or the previous one at the end of the list. After acknowledging, they stay.
- Status is always text plus an icon, never color alone. A snooze that ends while the page is open is announced in a polite live region as "<tile name> is back".

| State | Shows |
|-------|-------|
| Loading | `LoadingState` "Loading tiles" in the tile area. No badge row or queue is drawn until ready. The header stays. |
| Error | `ErrorState` with retry in the tile area (`onRetry`). No badge row or queue. |
| Refresh failed | Header reads "Stale since HH:mm"; an alert banner "Couldn't refresh: <message>" with Retry. When the refresh function itself failed, tiles keep their last good values; when a storage write failed while the readings were being saved, tiles whose write persisted show the new reading, a toast names the failed write, and nothing is rolled back. The next interval tries again and a success returns the header to Live. |
| Paused | Header reads "Paused" with a Resume button. No refresh runs, including the one in flight. Tiles keep their last values. |
| Empty | `EmptyState` "No tiles yet" in the tile area. The queue still shows its items. |
| Nothing needs you | The queue reads "Nothing needs you" and the "N need you" badge is hidden. A narrow strip reads "Nothing needs you" too. |
| Stale tile | The value is dimmed and a line reads "Stale · Updated N ago" with an icon. The tile keeps its place. It opens a queue item only if `staleOpensItem` is set. The dialog shows "Stale" and the exact time. |
| Tile with an item | The tile gets the attention style, plus the text "Needs you" or "Acknowledged" with an icon. |
| Narrow window | Under 768 px of block width the queue becomes a strip above the tiles, labeled "N need you" and closed until opened, and tiles flow in one column. |
| Many items | The queue scrolls in a `ScrollArea` and the tile area scrolls on its own. Section grids wrap. |
| Long title | Tile names truncate with an ellipsis; the dialog shows the full name. |

Item lifecycle. Everything below is derived from the item's timeline; status is never stored.

- **Statuses**: open, acknowledged, snoozed, resolved. The latest of these events decides: `opened`, `reopened`, `acknowledged`, `snoozed`, `snooze-ended`, `resolved`, `cleared`. `flagged-again` is recorded but changes nothing. Open and acknowledged items are the queue. `cleared` counts as resolved.
- **Flag edges**: a rule flags when its condition turns true, or when its `occurrence` key changes while it stays true. It does not flag on every evaluation. Rules run when tiles, rules or the clock change.
- **A flag finds the rule's latest item**: if it is unresolved, the item gets `flagged-again`. If it was resolved or cleared less than 24 hours ago, it gets `reopened` and is open again. Otherwise a new item opens with urgency from the rule and an `opened` event.
- **Auto-clear**: when a condition turns false and the item is unresolved (open, acknowledged or snoozed), it gets `cleared` with the text "Cleared: <tile name> <state>". An item resolved by hand is left alone.
- **Reload**: a fresh mount treats a rule as already true when its latest item is unresolved or was resolved by hand, so a reload does not re-flag something the user dismissed while the condition still holds.
- **Acknowledge**: allowed from open only. The item keeps its place.
- **Snooze**: allowed from open or acknowledged, with an optional note (trimmed, kept in the timeline when not empty) and an end time in the future. Presets are 1 hour, This evening (18:00, left out from 17:00), Tomorrow morning (08:00), Next week (next Monday 08:00) and a date picker (08:00 on that day; today only while 08:00 is still ahead). The item leaves the queue while snoozed.
- **Snooze ends**: a tick every 30 s, and when the tab becomes visible, appends `snooze-ended` stamped at the snooze's own end time. The item is open again from that instant, even before the event is written. Each item that returned is announced.
- **Resolve**: allowed from any unresolved status, immediately. A resolved item can come back only by the 24-hour reopen above.
- **Stale rule**: a tile with `staleOpensItem` gets a built-in rule "<name> has not reported", urgency Later, that is true while the tile is stale.

## Borrow / Leave out

Borrow:

- Two click targets per tile: the icon toggles, the body opens details (S4 (home-assistant), S1-icon-toggled, S1-light-moreinfo).
- Tiles grouped under small section headings with no section borders (S1-overview (home-assistant)).
- Tile features inside the card that act at once: a level slider, a target minus and plus, 0.5 steps (S1-overview, S1-thermostat-plus (home-assistant)).
- A badge row above the sections that gives a count or value without opening anything, and opens the same details as a tile (S1-overview, S1-badge-moreinfo, S5 (home-assistant)).
- A number tile with a sparkline and no axes, and a taller history view in its details (S1-overview, S1-sensor-moreinfo (home-assistant)).
- A tile that cannot be trusted keeps its name, place and size and changes only icon, badge and subtitle (S2-t0010 (home-assistant)). Our stale tile does the same with dimmed text.
- Confirmation is opt-in per action, for a lock or garage door and not for every toggle (S7 and S8 (home-assistant)).
- A summary that counts what needs attention (S1-next-demo, S2-t0010 (home-assistant)). Ours is the "N need you" badge.
- Acknowledge means "I have seen it and own it" and the item stays listed (S1 (pagerduty), S4-t0271 (pagerduty)). Status is a word, not a pill.
- Snooze is a timed pause that comes back (S2 (pagerduty), S4 (incident-io)), and an acknowledged item can be snoozed (S4 (incident-io)). Presets that include "until tomorrow" (S2-docs-snooze (pagerduty)).
- A reason asked on snooze, recorded in the timeline (S4 (incident-io)). Ours is optional.
- Urgency-first ordering that holds after acknowledgement (S3-docs-incidents-page (pagerduty)), with two levels, Now and Later.
- Three equal-weight outlined actions on an item: Acknowledge, Snooze and the rest (S4-docs-snoozing (incident-io)).
- A condition that stops being true closes its item (S5 (incident-io), the route's auto-cancel when its alert resolves), and a repeat alert joins the open item (S6 (incident-io)).
- A timeline of time and label rows, with system events and hand-written notes in one list (S1 (pagerduty), S2-s0540, S3-s0240 (incident-io)).
- A stated refresh rhythm in the page ("Refreshes every 15s", S1-t0815 (incident-io)).
- An empty list says so in one line (S4-t0149 (pagerduty)).

Our design (no source shows it):

- All queue keys, the 24-hour reopen window, flag edges with an occurrence key, standalone items with no tile, the stale rule, the pause control, the Retry banner, the narrow strip, and the Live, Paused and Stale header states. Reopen is mentioned in the pagerduty and incident-io docs but never shown (both notes list it as Unseen). A stale tile is not shown in any Home Assistant source (Unseen in that note).

Leave out:

- Notifications of any kind: push, email, sound or OS alerts. Attention shows only in the page.
- Escalation, on-call, schedules, responders and assigning an item to someone (S1 and S4 (pagerduty), S1 and S5 (incident-io)). This is single-user.
- An editor for flag rules or thresholds, and the tile card editor with Config, Visibility and Layout tabs (S2-t0124 (home-assistant)). Rules live in the app's code or data.
- Drag-to-rearrange, an edit mode, section backgrounds, header titles and footer cards (S3 and S6 (home-assistant)). Order comes from the data.
- Chart panels as tiles or sections, and a history chart with axes and gridlines (S1-sensor-moreinfo (home-assistant)).
- Built-in integrations with any service. `onRefresh` is the app's to write.
- A bottom-sheet dialog on phones (S1-narrow-light-moreinfo (home-assistant)), two tile columns on a narrow screen (S1-narrow-top), vertical tiles and the "Favorites" and "Summaries" layouts (S1-next-demo): the app chooses its sections.
- Home Assistant's inline second-press "Really open?" button (S1-open-door-click), hold and double-tap actions (S7), and entity search (S1-search-door): use `action-palette` for search.
- PagerDuty's filled Resolve and its resolve confirmation modal (S4-t0271), the Triggered label and acknowledgement timeout, priority and urgency as separate fields, merge, status updates, Run Actions and Run Play modals (S1, S2, S5 (pagerduty)).
- The Incidents page frame: status tabs, "Assigned to me / All", row checkboxes and bulk actions, counters (S3 and S4 (pagerduty)). `view-switcher` covers tabs.
- incident.io's other escalation statuses (Pending, Delayed, Expired, Cancelled, Pending repeat), "I'm unavailable", the paging countdown sheet, alert grouping windows with Ungroup, routes, and Triage accept, merge or decline (S1 to S7 (incident-io)).

## Block API

`index.ts` exports the components `CommandCenter`, `BadgeRow`, `TileBoard`, `TileDialog`, `AttentionQueue` and `Sparkline`, the hook `useCommandCenter`, the functions `itemStatus`, `isStale`, `stateText`, `evaluateRules`, `applyItemAction`, `endExpiredSnoozes`, `initialRuleMemory` and `snoozePresets`, and the types `CommandCenterProps`, `Tile`, `FlagRule`, `Urgency`, `AttentionItem`, `TimelineEvent`, `ItemStatus`, `ItemAction`, `RefreshState` and `RuleMemory`. The block never imports another pattern. The `Summary` type lives in `types.ts` and is not exported; reach it as `NonNullable<CommandCenterProps["summaries"]>[number]`.

```ts
CONTRACT: type Tile = {
  id: string; section: string; name: string;
  kind: "toggle" | "level" | "target" | "sensor";
  on?: boolean; value?: number; unit?: string; target?: number; text?: string;
  onLabel?: string; offLabel?: string;
  onVerb?: string; offVerb?: string;       // toggle verbs: "Lock" in `Lock Front door?`; default "Turn on" / "Turn off"
  sensitive?: boolean;                      // toggling asks first
  updatedAt: number;                        // epoch ms
  staleAfterMs?: number; staleOpensItem?: boolean;
  history?: number[];                       // numeric kinds only; 2 or more points draw a sparkline
}
CONTRACT: type Urgency = "now" | "later"
CONTRACT: type FlagRule = {
  id: string; tileId: string; title: string; urgency: Urgency;
  test: (tile: Tile) => boolean;
  occurrence?: (tile: Tile) => string;      // a change while `test` stays true flags again
}
CONTRACT: type TimelineEvent = {
  at: number;
  type: "opened" | "flagged-again" | "acknowledged" | "snoozed" | "snooze-ended" | "cleared" | "resolved" | "reopened";
  until?: number; note?: string; text?: string;
}
CONTRACT: type AttentionItem = {
  v: 1; id: string; title: string; urgency: Urgency;
  tileId?: string; ruleId?: string; timeline: TimelineEvent[];
}
CONTRACT: type ItemStatus = "open" | "acknowledged" | "snoozed" | "resolved"
CONTRACT: type ItemAction = { type: "acknowledge" } | { type: "snooze"; until: number; note?: string } | { type: "resolve" }
CONTRACT: type RefreshState =
  | { state: "none" } | { state: "live"; at: number }
  | { state: "paused"; at?: number } | { state: "stale"; since?: number; error: Error }
CONTRACT: type RuleMemory = Record<string, { on: boolean; occurrence?: string }>
CONTRACT: type Summary = { id: string; label: string; tileId?: string }   // not exported
CONTRACT: type CommandCenterProps = Parameters<typeof useCommandCenter>[0] & {
  sourceLabel: string; loadedAt?: number; summaries?: Summary[];
  status?: "loading" | "ready" | "error"; error?: Error; onRetry?: () => void;
}
CONTRACT: CommandCenter(props: CommandCenterProps): JSX.Element
CONTRACT: useCommandCenter(opts: {
  tiles: Tile[]; items: AttentionItem[]; rules: FlagRule[];
  onTileUpdate: (id: string, patch: Partial<Tile>) => Promise<void>;
  onItemAdd: (item: AttentionItem) => Promise<void>;
  onItemUpdate: (id: string, patch: Pick<AttentionItem, "timeline">) => Promise<void>;
  onRefresh?: (signal: AbortSignal) => Promise<Array<Pick<Tile, "id"> & Partial<Tile>>>;
  refreshMs?: number;                       // default 30000
}): { now: number; announcement: string; refresh: RefreshState;
      pause(): void; resume(): void; retry(): void; act(itemId: string, action: ItemAction): void }
CONTRACT: BadgeRow(props: { summaries: Summary[]; needYouCount: number; onFocusQueue(): void; onOpenTile(id: string): void }): JSX.Element | null
CONTRACT: TileBoard(props: { tiles: Tile[]; items: AttentionItem[]; now: number; onToggle(tile: Tile): void; onOpen(tile: Tile, trigger: HTMLElement): void; onLevel(tile: Tile, value: number): void; onTarget(tile: Tile, target: number): void }): JSX.Element
CONTRACT: TileDialog(props: { tile: Tile | null; item: AttentionItem | null; now: number; returnFocusRef: RefObject<HTMLElement | null>; onOpenChange(open: boolean): void; onToggle(tile: Tile): void; onAct(action: ItemAction): void }): JSX.Element
CONTRACT: AttentionQueue(props: { items: AttentionItem[]; tiles: Tile[]; now: number; onAct(itemId: string, action: ItemAction): void; onOpenTile(id: string): void }): JSX.Element
CONTRACT: Sparkline(props: { values: number[]; className?: string; label?: string }): JSX.Element | null
CONTRACT: itemStatus(item: AttentionItem, now: number): ItemStatus
CONTRACT: isStale(tile: Tile, now: number): boolean
CONTRACT: stateText(tile: Tile): string
CONTRACT: evaluateRules(input: { tiles: Tile[]; items: AttentionItem[]; rules: FlagRule[]; previous: RuleMemory; now: number; newId: () => string }): { add: AttentionItem[]; append: Array<{ id: string; events: TimelineEvent[] }>; memory: RuleMemory }
CONTRACT: applyItemAction(item: AttentionItem, action: ItemAction, now: number): TimelineEvent[]
CONTRACT: endExpiredSnoozes(items: AttentionItem[], now: number): Array<{ id: string; events: TimelineEvent[] }>
CONTRACT: initialRuleMemory(items: AttentionItem[], rules: FlagRule[], tiles: Tile[]): RuleMemory
CONTRACT: snoozePresets(now: number): Array<{ label: string; until: number }>
```

- `CommandCenter` is built from the exported parts. An app can use `BadgeRow`, `TileBoard`, `TileDialog` and `AttentionQueue` alone or rearrange them; they take plain props with no shared wrapper and no hidden provider. `useCommandCenter` wires the pure functions to the store, the refresh loop and the tick.
- Rules are a prop, never stored. `FlagRule` holds functions, so it cannot go in a collection or JSON. Pass a stable array (a module constant or `useMemo`), because a new array re-runs the rules.
- Pass `tiles` and `items` to `useCommandCenter` together. Rule memory is seeded from the first non-empty `tiles`, so `items` must already be loaded by then. While `status` is `"loading"`, pass empty arrays for both, as the demo does.
- Timeline-append contract: the block only ever sends a timeline that is the last confirmed one plus new events. `onItemUpdate(id, { timeline })` must store the whole array as given and never reorder or drop earlier events. Writes to one item go one at a time; a failed write drops only its own events and shows a `sonner` toast. An app that adds a standalone item calls `onItemAdd` with `v: 1` and an `opened` first event.
- `updatedAt` stamping: every tile write the block makes (toggle, level, target) sets `updatedAt` to now. Refresh patches get `updatedAt` now unless the patch carries its own. Writes the app makes itself must stamp `updatedAt`, or the tile will read stale.
- `AttentionItem.v` is the timeline format version. Readers treat a missing `v` as 1. Saved items outlive the code that wrote them, so bump it when an event's shape changes.
- `onRefresh` returns the tiles that changed, as patches with an `id`. One refresh runs at a time, the first right after mount, then every `refreshMs`. Pausing aborts the one in flight through its `AbortSignal`. Without `onRefresh` the refresh state is `none`.
- The block renders no `AppShell`, `Toaster` or `TooltipProvider`; the app's single `AppShell` provides them. States come from the base `LoadingState`, `ErrorState` and `EmptyState`.
- Hotkeys use `useHotkeys` from `react-hotkeys-hook` with form-tag filtering on. shadcn components used: `badge`, `button`, `calendar`, `collapsible`, `dialog`, `kbd`, `popover`, `scroll-area`, `textarea`, `tooltip`, and `dropdown-menu` for the demo. `registry-item.json` declares the npm `dependencies` `date-fns`, `lucide-react`, `react-hotkeys-hook` and `sonner`.

`demo.tsx` default-exports `Demo`: a sample home with 10 tiles in the sections Security, Climate, Lights and Home network, and 5 items (a failed backup, high humidity, an acknowledged smoke-alarm item, a snoozed registration item with 90 s left, and a freezer item cleared earlier), stored through `useCollection("command-center-tiles", ...)` and `useCollection("command-center-items", ...)`. It passes four flag rules (front door unlocked, humidity above 55% with an occurrence key, backup failed, freezer door open), the source label "Sample data", and summary badges. Nothing changes unless the user acts or picks an event. A "Simulate event" menu changes the sample home: the front door unlocks or locks, humidity rises or falls, the backup fails, succeeds or stops reporting, the freezer door opens or closes, and "Electric bill due Friday" is added as a standalone item; a "Refresh fails" checkbox makes the 30 s refresh throw. The menu exists only in the demo. A "Preview state" button group (live, empty, loading, error) forces each screen state, and "Reset sample data" replaces both collections with a fresh seed, hiding the tiles while it runs and putting the old data back if one write fails. It renders no `AppShell`; the app provides it.

## Sources

- [home-assistant study note](../apps/home-assistant.md): S1 (public demo), S2 and S3 (videos), S4 to S7 (tile, badges, sections and actions docs), S8 (confirmation design discussion).
- [pagerduty study note](../apps/pagerduty.md): S1 and S2 (incident and edit docs), S3 (Incidents page docs), S4 and S5 (product videos).
- [incident-io study note](../apps/incident-io.md): S1 to S3 (product videos), S4 to S7 (snoozing, escalation statuses, grouping and auto-create docs).
- Two click targets and the toggle fallback: S4 text, S1-icon-toggled, S1-light-moreinfo, S1-overview2-lock-icon-click (home-assistant).
- Section layout, tile anatomy, features and 0.5 steps: S1-overview, S1-thermostat-plus (home-assistant). Narrow layout seen as two columns: S1-narrow-top, S1-narrow-scrolled.
- Badge row and its details dialog: S1-overview, S1-badge-moreinfo, S5 text (home-assistant). Entity-filter badges are text only.
- Sensor sparkline and dialog chart: S1-overview, S1-sensor-moreinfo (home-assistant).
- Unavailable tile that keeps its place: S2-t0010, S2-t0135 (home-assistant).
- Confirmation: S7 text and S8 text, S1-open-door-click (home-assistant); the resolve modal S4-t0271 (pagerduty).
- Acknowledge, statuses, resolve: S1 text, S4-t0271, S5-t0322 (pagerduty); S5 text, S4-docs-snoozing, S3-s0120 (incident-io).
- Snooze presets, expiry and return: S2-docs-snooze, S2 text (pagerduty); S4 text (incident-io). Snooze from acknowledged: S4 FAQ (incident-io).
- Urgency order kept after acknowledgement: S3-docs-incidents-page (pagerduty). Empty list line: S4-t0149 (pagerduty).
- Timeline rows: S1 text (pagerduty); S2-s0540, S3-s0240 (incident-io). Refresh note: S1-t0815 (incident-io).
- Auto-clear and grouping into one item: S5 and S6 text (incident-io); S1 text (pagerduty).
- Our design: every queue key, the 24-hour reopen, flag edges and occurrence keys, standalone items, the stale rule and opt-in, the Live, Paused and Stale header and its banner, the narrow strip, the optional snooze note, immediate resolve, the snooze preset list and the Now and Later wording.
