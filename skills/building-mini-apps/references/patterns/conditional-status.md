# conditional-status

A split button whose primary half changes an item's state now and whose chevron opens a menu of deferred or conditional variants: resolve it in the next release, archive it until it recurs. The state is not final. A pure logic module takes the item's status record and incoming events (a new occurrence, a release, time passing) and returns the next status, so a resolved item regresses and an archived one escalates or comes back when its condition is met. The conditions are caller-supplied. It was studied in Sentry.

## When to use

Use it when the user parks an item with a condition attached, and the app should bring it back on its own when the condition is met:

- A task app's "snooze until Monday" or "until they reply": the task leaves the list and returns when the date passes or a reply arrives.
- A support inbox: "close until the customer writes back", "close for 3 days".
- A subscription or bill tracker: "mark paid until next month", "remind me after 2 more late notices".
- A bug or issue list: "fixed in the next release" that reopens if the bug shows up again, "archive until it happens 50 more times".
- A notification feed: "mute for a week", "mute until it affects 10 more people".

Do not use it when:

- The action is one click with no condition and no way back: use a plain `Button`, or `action-palette` when the user finds actions by typing.
- Snoozing is one queue item with preset times and a note, beside tiles that show live state: use `command-center`, which has its own snooze menu.
- Many rows are picked first and the work is mostly selecting: use `bulk-select` for the selection and header action bar. This pattern supplies the split buttons that bar holds.
- Status is just a label the user edits among fixed choices, with no conditions or automatic changes: use `inspector` or a select field.
- The rows are a table the user edits cell by cell: use `staged-table-edit`.

## Anatomy

```
┌──────────────────────────────────────────────────────────────────────┐
│ ☑ 2 selected · Clear            [ Resolve │ ⌄ ]  [ Archive │ ⌄ ]      │  ~44px
├──────────────────────────────────────────────────────────────────────┤
│ ☑ BUG-104  Crash when saving a recipe              ( ↺ Regressed )    │
│            Event in 2.4.2, newer than 2.4.1                            │  ~52px
│ ☐ BUG-107  Search ignores accented letters         ( ✓ Resolved )     │
│            Fixed in 2.4.1; reopens on an event from a newer release    │
│ ☐ BUG-110  Photo upload stalls on slow networks    ( ▣ Archived )     │
│            Returns after 100 more events (34 so far)                   │
│ ...                                                                    │
└──────────────────────────────────────────────────────────────────────┘

Resolve chevron open (about 15% of the block):   A "For…" row opened in place:
┌───────────────────────────────┐                ┌───────────────────────────────┐
│ Resolved in                   │                │ ‹ Back                        │
│ The next release              │                │ For…                          │
│   The next release after ...  │                │ Archive for  [ 2 ] [ hours ⌄ ]│
│ The current release           │                │ [ Apply ]                     │
│ Another existing release…   › │                └───────────────────────────────┘
│ A commit…                   › │
└───────────────────────────────┘
```

- **Workflow row:** a target label on the left and one split button per group on the right, in the model's order. The target is the checked rows, or the highlighted row when none are checked. With no target the label says to select an item and both buttons are disabled.
- **Split button:** the primary half takes about two thirds of the width and the chevron half the rest, joined with no gap. The primary label is the group's verb ("Resolve"). When every target already holds a condition from that group it reads the undo verb ("Unresolve"). A group with no menu entries draws the primary half alone.
- **List:** a scrolling listbox. Each row has a check box, an optional ID, the title, a state chip on the right, and a second muted line.
- **State chip:** an icon plus the state's label. Color only adds tone; the icon and word carry the meaning.
- **Second line:** the hold text when the item has a condition ("Returns after 100 more events (34 so far)"). Otherwise the reason for its last change ("Archive period ended"), then the caller's `meta`. Counters ("12 events · 4 users") follow when the model names them.
- **Condition menu:** a popover headed with the group's name, one row per condition: a label, an optional muted hint under it, and a right arrow on rows that need an input. The row matching the current condition is checked.
- **Input picker:** choosing a row with an arrow replaces the list in place with a back link, the row's name, a small input (a count, a length of time with a unit, a choice or a text field), and Apply. The studied app opens a second menu beside the first. In place keeps focus in one box.

## Interaction

Keys come from `useHotkeys`, act when focus is on the page body or inside the block, and never fire while focus is in an input, textarea, select or contenteditable. No source shows a key for resolve, archive or the menus (Unseen in the sentry study note), so every key except the row ones is our design. Row keys follow the blueprint's key map (j and k move, x toggles selection, Esc clears the selection).

| Key | Does | Notes |
|-----|------|-------|
| Click primary half | Applies the group's primary condition to the target now. If every target already holds one from this group, it undoes it | Seen: Resolve acts at once with no menu (S13-resolve-menu.png). The undo is our design. |
| Click chevron half | Opens that group's menu | Seen in S13-resolve-menu.png and S13-archive-menu.png. |
| Click a menu row | Applies that condition to the target and closes the menu | A row with an arrow opens its input picker instead. |
| r / a | Press the primary half of the Resolve or Archive split button | Our design. Each group's key comes from the model. |
| Shift+r / Shift+a | Open that group's menu | Our design. |
| j / ArrowDown, k / ArrowUp | Move the highlight to the next or previous row | Our design, from the blueprint key map. Stops at the ends. |
| Home / End | Highlight the first or last row | Our design. |
| x or Space | Check or uncheck the highlighted row | x is from the blueprint key map; Space is our design. |
| Esc | Clears the checks; with none, clears the highlight | Blueprint key map. |
| ArrowDown (on the chevron) | Opens the menu | Our design. |
| Menu: ArrowDown / ArrowUp / Home / End | Move between rows, wrapping at the ends | Our design. |
| Menu: Enter or Space | Apply the row, or open its picker | Native button behavior. |
| Menu: ArrowRight | Open the picker of a row with an arrow | Our design. |
| Picker: Enter | Apply the value | A form submit. A bad value shows its message and stays open. |
| Picker: Esc or Back | Return to the list; Esc again closes the menu | Our design. |
| Click row | Highlights it; clicking the check box checks it | Our design. |

Focus rules:

- The list is one tab stop with `aria-activedescendant`; the split buttons are two more. Opening a menu moves focus into it, and closing it returns focus to the chevron that opened it.
- A key pressed with focus in the toolbar acts on the target but never moves the highlight; the row keys work only when the list or the page body has focus.
- Changing a row's state never moves the highlight or the checks.
- Every state change, whether from a click, a key, a tick or a caller event, is announced in a polite live region as "<title>: <reason>".
- A condition's label ends in an ellipsis when it needs an input, the same cue the studied app uses.

| State | Shows |
|-------|-------|
| Loading | `LoadingState` in the list area; keys do nothing and the buttons are disabled. |
| Error | `ErrorState` with the message and Retry when `onRetry` is given. |
| Empty | `EmptyState` in the list area; the buttons are disabled. |
| No target | The label reads "Select an item to change its status" and both split buttons are disabled (S2-t0030.png shows them greyed with nothing selected). |
| Mixed targets | The primary applies to every target. The undo label shows only when all targets hold a condition from the group. The menu shows no checked row unless all targets share the same condition. |
| Waiting hold | A hold that has not started to matter says so: "Fix expected in the next release". |
| Bad input | The picker shows the message under the field and keeps focus on it. Nothing is applied. |
| Unknown condition | A stored hold whose condition id is not in the model shows the state chip and no hold text, and is never tripped. |
| Long title | The title truncates with an ellipsis; the full title is in the `title` attribute. |
| Many items | The list scrolls and the highlighted row stays in view. Not virtualized. |

Lifecycle. All of it is a pure function, so the caller can run it anywhere (a server, a test, a timer).

- **Record:** a status record holds the state (a string from the model), when it began, running totals of occurrences and users, the latest release seen, the active hold, and the last transition. It is plain JSON and is stored with the item.
- **Hold:** the condition in force. It stores the condition's id, when it began, the value the user entered, and a small data object the condition keeps for itself (a baseline count, an end time, the release that carries the fix).
- **Events:** `choose` (a condition picked, with its value), `clear` (undo), `occurrence` (with an optional count, new users and release), `release` (a version, with the commits it contains), `signal` (a named event the app defines, such as `reply`) and `time` (the clock moved).
- **Counting:** an occurrence adds to the totals in every state, so an archived item keeps counting. A release event raises the record's latest release only when it is newer.
- **Choosing:** a `choose` sets the condition's state and starts its hold, taking a snapshot of the totals. Choosing again replaces the hold.
- **Tripping:** after the totals update, each event is shown to the active condition's `watch`. If it trips, the item moves to the condition's `trips` state, which defaults to the model's open state, and its hold is cleared. A resolved item then reads Regressed, and an archived one reads Escalating or is simply open again.
- **Built-in conditions (issue model):**
  - Resolve now: any occurrence regresses it.
  - The next release: waits for the first release newer than the current one, which then carries the fix.
  - The current release: the fix is the release already seen.
  - Another release: the fix is the release picked.
  - A commit: waits for a release that lists the commit.
  - For each of these, once the fix release is known, an occurrence from a release newer than it regresses the item. An occurrence with no release does nothing.
  - Archive until escalating: trips on the app's `escalate` signal, because the forecast is the app's to compute.
  - Archive forever: never trips.
  - Archive for a length of time: trips when the clock passes the end, and the item is open again.
  - Until it occurs N more times, or affects N more users: trips when the totals grow by N since the hold began, and the item escalates.
- **Time:** the block asks the logic about time every few seconds (`tickMs`, default 5000) and when `clock` changes, and reports a change through `onChange`. A condition that is due is also checked on any other event, so an occurrence after the end time never sees a stale hold.
- **No change, no write:** when nothing changed the function returns the record it was given, so a caller can compare references and skip the write.

## Borrow / Leave out

Borrow:

- A split button: a primary half that acts at once, and a chevron half that opens refinements (S13-resolve-menu.png, S13-archive-menu.png, S13-issue-detail.png, S3-t1221.png).
- The primary half acts with no menu, so the menu holds only refinements (S13-resolve-menu.png). Ours leaves the plain "resolve" out of its menu for the same reason.
- A menu headed with the group's name ("Resolved In", "Archive"), rows with a muted sub-line, and a right arrow on rows that open a second-level picker (S13-resolve-menu.png, S13-archive-menu.png).
- Resolve's choices: the next release, the current release, another existing release, a commit (S13-resolve-menu.png, S10 text).
- Archive's choices: until escalating, forever, for a length of time, until it occurs a number of times, until it affects a number of users (S13-archive-menu.png, S10 text).
- A default archive condition of "until escalating" and a plain resolve that treats any later event as a regression (S10 text).
- A lifecycle that reverses itself: resolved becomes regressed on a new event, archived becomes escalating, and any archived item can be unarchived (S10-issue-status-diagram.png, S10 text).
- A recurrence in a release newer than the resolving one flips to regressed (S10 text).
- An archived item keeps recording events; forever never escalates (S10 text).
- Buttons greyed out when nothing is selected, and the same two split buttons in a row of workflow actions and in a bulk bar (S2-t0030.png, S13-bulk-select.png, S13-issue-detail.png).
- A banner-style line saying the item is ignored until a time (S6-t0056.png). Ours is the hold text on the row.

Leave out:

- The studied app's brand look, copy and icons: the chip tones and icons are the skill's.
- Release and commit lookup against a real repository or release feed. Releases and commits are strings the caller supplies; there is no network.
- The escalation forecast. The pattern takes an `escalate` signal; computing "events exceed their weekly forecast" is the app's.
- Ignore and Mark Reviewed buttons, the For Review inbox, merge and delete (S2-t0030.png, S6-t0080.png, S10 text). Review state is not part of this pattern.
- Auto-resolve after X days without events and the automatic New to Ongoing move after 7 days (S10-issue-status-diagram.png). A caller can add them as a kind that watches `time`.
- The "Read the docs" link in the Archive menu (S13-archive-menu.png).
- Confirmation dialogs. Choosing acts at once; undo is one click on the same button.
- A side-by-side submenu. The picker replaces the list in place.
- Priority, assignee and the rest of the workflow row (S9 img-issue-details-breakdown, S13-issue-detail.png): `inspector` and `bulk-select` own those.

## Block API

Files in `gallery/src/patterns/conditional-status/`: `registry-item.json`, `index.ts`, `types.ts`, `status.ts` (pure logic), `models.ts` (two example models), `split-button.tsx`, `condition-menu.tsx`, `conditional-status.tsx`, `demo.tsx`.

```ts
CONTRACT: type Scalar = string | number | boolean
CONTRACT: type HoldData = Record<string, Scalar>
CONTRACT: type InputValue = string | number
CONTRACT: type DurationUnit = "minutes" | "hours" | "days"
CONTRACT: type ConditionInput =
  | { type: "count"; label: string; unit: string; min?: number; max?: number; default?: number }   // value is a whole number
  | { type: "duration"; label: string; default?: number; unit?: DurationUnit }                      // value is milliseconds
  | { type: "choice"; label: string; options: string[] }
  | { type: "text"; label: string; placeholder?: string }
CONTRACT: type Hold = { kind: string; at: number; value?: InputValue; data: HoldData }
CONTRACT: type Transition = { at: number; from: string; to: string; reason: string }
CONTRACT: type StatusRecord = {
  v: 1; state: string; since: number;
  occurrences: number; users: number; release?: string;
  hold?: Hold; last?: Transition
}
CONTRACT: type StatusEvent =
  | { type: "choose"; kind: string; value?: InputValue }
  | { type: "clear" }
  | { type: "occurrence"; count?: number; newUsers?: number; release?: string }
  | { type: "release"; version: string; commits?: string[] }
  | { type: "signal"; name: string }
  | { type: "time" }
CONTRACT: type ConditionContext = { now: number; record: StatusRecord }   // record already counts the event
CONTRACT: type ConditionKind = {
  id: string; group: string; label: string; hint?: string;
  enters: string;                       // state the item takes when this is chosen
  trips?: string;                       // state it takes when the condition is met; default is the model's open state
  inMenu?: boolean;                     // default true; false leaves it to the primary half only
  input?: ConditionInput;               // a label ends in "…" when set
  start?: (value: InputValue | undefined, ctx: ConditionContext) => HoldData;
  watch?: (hold: Hold, event: StatusEvent, ctx: ConditionContext) => { trip?: boolean; reason?: string; data?: HoldData } | void;
  describe?: (hold: Hold, ctx: ConditionContext) => string;   // hold text; default is the label
}
CONTRACT: type Tone = "neutral" | "good" | "warn" | "bad" | "muted"
CONTRACT: type StateDef = { label: string; tone: Tone; icon?: "open" | "done" | "regressed" | "archived" | "escalating" | "snoozed" }
CONTRACT: type StatusGroup = { id: string; label: string; undoLabel: string; menuLabel: string; primary: string; key?: string }
CONTRACT: type StatusModel = {
  open: string;
  states: Record<string, StateDef>;
  groups: StatusGroup[];
  kinds: ConditionKind[];
  counters?: { occurrences?: string; users?: string };      // nouns shown on rows, such as "events" and "users"
}
CONTRACT: type StatusItem = { id: string; title: string; meta?: string; status: StatusRecord }
CONTRACT: type ConditionalStatusProps<T extends StatusItem> = {
  items: T[]
  model: StatusModel                                  // pass a stable object; it holds functions
  onChange: (id: string, status: StatusRecord, transition: Transition | null) => void
  status?: "loading" | "ready" | "error"              // default "ready"; pass useCollection's status
  error?: Error
  onRetry?: () => void
  clock?: () => number                                // default Date.now; a new function runs a check at once
  tickMs?: number                                     // default 5000
  highlightedId?: string | null                       // controlled; omit for internal state
  onHighlightedIdChange?: (id: string | null) => void
  renderLead?: (item: T) => ReactNode                 // fixed-width leading column, such as an ID
  emptyTitle?: string
  "aria-label"?: string
}
CONTRACT: ConditionalStatus<T extends StatusItem>(props: ConditionalStatusProps<T>): JSX.Element
CONTRACT: SplitButton(props: { label: string; onPrimary(): void; disabled?: boolean; menuLabel?: string; open?: boolean; onOpenChange?(open: boolean): void; children?: ReactNode /* a ConditionMenu */ }): JSX.Element
CONTRACT: ConditionMenu(props: { heading: string; kinds: ConditionKind[]; current?: { kind: string; value?: InputValue }; onChoose(kind: string, value?: InputValue): void }): JSX.Element
CONTRACT: nextStatus(record: StatusRecord, event: StatusEvent, model: StatusModel, now: number): { record: StatusRecord; transition: Transition | null }
CONTRACT: initialStatus(model: StatusModel, now: number, release?: string): StatusRecord
CONTRACT: primaryEvent(records: StatusRecord[], group: StatusGroup, model: StatusModel): StatusEvent
CONTRACT: holdGroup(record: StatusRecord, model: StatusModel): StatusGroup | undefined
CONTRACT: holdText(record: StatusRecord, model: StatusModel, now: number): string | null
CONTRACT: validateInput(input: ConditionInput, value: InputValue | undefined): string | null
CONTRACT: compareReleases(a: string, b: string): number
CONTRACT: durationMs(amount: number, unit: DurationUnit): number
CONTRACT: bugStatusModel(releases: string[]): StatusModel
CONTRACT: taskStatusModel(): StatusModel
```

`index.ts` exports the components `ConditionalStatus`, `SplitButton` and `ConditionMenu`, the functions `nextStatus`, `initialStatus`, `primaryEvent`, `holdGroup`, `holdText`, `validateInput`, `compareReleases`, `durationMs`, `bugStatusModel` and `taskStatusModel`, and every type above. The block never imports another pattern.

- `ConditionMenu` renders a `PopoverContent`, so it goes inside `SplitButton` or any `Popover`, and `onChoose` is the caller's cue to close it. A picker value is checked with `validateInput` before `onChoose` runs.
- `ConditionalStatus` is built from `SplitButton` and `ConditionMenu`; an app can use those two alone, for example in a table's header bar or an issue's workflow row, and call `nextStatus` itself. The block reads no store: it takes `items` and `status` as props and reports every change through `onChange`.
- Conditions are a prop, never stored. A `ConditionKind` holds functions, so it cannot go in a collection. Pass a stable model (a module constant or `useMemo`). The record stores only the condition's id and plain data, so a saved item outlives a model edit; a hold whose id is no longer in the model is left alone.
- To add a condition, add a kind to the model and put it in a group. "Until they reply" is `{ id: "snooze-reply", group: "snooze", label: "Until they reply", enters: "snoozed", watch: (_, event) => event.type === "signal" && event.name === "reply" ? { trip: true, reason: "They replied" } : undefined }`.
- The block owns user actions and the clock. Occurrence, release and signal events come from the app: call `nextStatus` with the item's current record and write the result. Both paths write through the same store, so read the latest items when you do.
- A transition is reported once, to `onChange`, by the writer that caused it. The live-region announcement is made by the block from any change to a row's `last` transition, whoever wrote it.
- Hotkeys use `useHotkeys` with form-tag filtering on. The block renders no `AppShell`, `Toaster` or `TooltipProvider`. States come from the base `LoadingState`, `ErrorState` and `EmptyState`.
- shadcn components used: `button`, `input` and `popover`. No new dependencies.

`demo.tsx` default-exports `Demo`: a "State preview (demo only)" group (live, empty, loading, error), a switch between a bug list for an invented recipe app (the issue model, 6 items covering resolve now, next release, a commit, archive forever, archive for a length of time, and archive until it occurs again) and a household task list (the task model: snooze until tomorrow, until Monday, until they reply or for a length of time, and Done). Items are stored through `useCollection("conditional-status-demo", seed)`. An event strip drives the logic from outside: New event, New event from a new user and Event spike (an occurrence plus the `escalate` signal) on the highlighted bug, Ship the next release (to every bug, carrying a sample commit), They reply on the highlighted task, and Skip ahead one day (which moves the demo's clock, so a duration ends at once). "Reset sample data" restores the seed. Each change also raises a `sonner` toast. A plain-text footer lists the key hints.

## Sources

[sentry study note](../apps/sentry.md). The logic module, its event set and the generic condition model are our design; the study note shows the menus and the status diagram only.

- **Split button with a primary half and a chevron half, in the workflow row and the bulk bar:** `S13-bulk-select.png`, `S13-issue-detail.png`, `S3-t1221.png`, and S9 text (`S9-img-issue-details-breakdown-MAZU5VNB.png`).
- **Primary acts at once; the menu holds refinements, headed "Resolved In":** `S13-resolve-menu.png`.
- **Archive menu, its sub-lines and the rows with right arrows that open a second-level picker:** `S13-archive-menu.png`. The second-level pickers were not opened (study note, Unseen): our design.
- **The set of Resolve and Archive conditions and what each one means:** S10 text (Archive and Resolve sections).
- **Status lifecycle: resolved regresses, archived escalates, archived can be unarchived:** `S10-issue-status-diagram.png` and S10 text.
- **Buttons greyed while nothing is selected:** `S2-t0030.png`.
- **An item ignored until a time shown as a line of text:** `S6-t0056.png`.
- **Our design:** the generic `ConditionKind` and `StatusModel`, the event set and every transition rule beyond S10's prose, the in-place picker, the undo label on the primary half, mixed-target rules, all keys other than the blueprint's row keys, the live-region announcements, the clock and tick, the choice and text inputs, the task model, and the demo's event strip.
