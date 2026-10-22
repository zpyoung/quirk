# mini-full

A small quick-add panel (input, live parsed preview, month grid, upcoming list) that opens into a full view of the same data, with the same panel as the sidebar. Studied in Fantastical's Mini Window and Full Calendar Window, with smaller inputs from Raycast, Things and Granola.

## When to use

Use it when one text field is the fastest way in and the same data also deserves a larger view.

- Appointment or event tracker: type "dentist tomorrow at 10-11", see the date and time resolve, press Enter, and see the row land in time order.
- Task capture with due dates: "call landlord fri /home", with a list for planning and a month view for gaps.
- Habit or medication log: quick-add a dated entry, open the full view to review a month.
- Reading or watch queue with a "next up" date: the panel is the daily glance, the full view is the backlog.

Do not use it when:

- The entry is not parsed from text, or has no date or other resolvable field. Use `list-peek` for a short list with a peek, or `expand-in-place` if a plain card grows into more fields.
- The user needs several equal views (day, week, month, year) rather than one small panel plus one big one. Use `view-switcher`.
- The full view is a document or canvas, not a list or calendar. Use `doc-collections` or `workspace-panes`.
- Commands matter more than records. Use `action-palette`.
- The main work is free-form notes with generated structure. Use `assisted-notes`.

## Anatomy

Two sizes of one layout. The panel is the same component in both.

```
Mini (panel alone, ~320 px wide, ~560 px tall)
┌──────────────────────────────┐
│ [ Add: dentist tomorrow 10-11 ]│ input row            ~8%
├──────────────────────────────┤
│  October 2026        <  >    │ month grid           ~40%
│  M  T  W  T  F  S  S         │ dots under days with items
│  ...  (grid slides down      │ replaced by the parse card
│       while the card shows)  │ while the input has text
├──────────────────────────────┤
│ TODAY 10/22                  │ upcoming list        ~40%
│ • 10:00-11:00  Dentist       │ scrolls, grid stays pinned
│ TOMORROW 10/23               │
│ • 09:00  Standup             │
├──────────────────────────────┤
│ [Expand]   6 upcoming  [Today]│ footer row            ~8%
└──────────────────────────────┘

Full (window, 100% of the app area)
┌────────────┬─────────────────────────────────────────┐
│ the same   │ [<] [Today] [>]   [List | Month]  [Find] │ toolbar
│ panel,     ├─────────────────────────────────────────┤
│ ~22% wide  │                                         │
│ (min 280px)│ list grouped by date, or month grid     │ content ~78%
│            │ with one-line items per day cell        │
└────────────┴─────────────────────────────────────────┘
```

- **Input row:** one text field, always visible, Add happens on Enter.
- **Parse card:** appears on the first keystroke in the grid's position. Shows title, when, all-day, tag and an Add button.
- **Month grid:** small, pinned. Dots mark days with items, today is a filled circle, the selected date is outlined, adjacent-month days are dimmed.
- **Upcoming list:** date headers, then rows of dot, time, title. Past items are dimmed.
- **Footer:** expand/collapse toggle, count, Today button.
- **Full toolbar and content:** step back/forward, Today, a List | Month segmented control, a filter field. List and Month are the only two views.

## Interaction

Bare-letter keys are ignored while focus is in an input, textarea or contenteditable. They use `useHotkeys` from `react-hotkeys-hook`.

| Key | Does | Notes |
|-----|------|-------|
| `n` | Focus the quick-add input | Our design. Fantastical uses ⌘N (S5), which the browser reserves |
| Enter (in input) | Add the parsed entry, clear the input, keep focus in the input | Does nothing while the title is empty. The panel stays open (S1-0008) |
| Esc (in input) | Clear the text if there is any, otherwise blur the input | Our design |
| `/` (in input) | Open the tag picker; picking one inserts a `/tag` token | Fantastical's `/calendar` picker (S1-0007). Typing past `/` filters the picker |
| ↑ / ↓ | Move the selected row in the upcoming list | Our design. Source says keyboard navigation exists but shows none (S4) |
| Enter (on a row) | Expand to the full view on that item's date, row selected | Our design for the unseen expand moment. Fantastical's ⌥-double-click does this (S5) |
| `e` | Toggle mini / full | Our design. Fantastical uses ⌘0 (S1-0012), which the browser reserves |
| `t` | Go to today: grid month, selected date and list scroll | S5 ⌘T |
| ← / → | Full Month view only: previous / next month | S5 (arrows jump a month) |
| Backspace / Delete | Remove the selected row, with an Undo toast | S5 for delete; the Undo is our design (undo is unseen) |
| Double-click a grid day | Put that date in the input as text and focus it | Text-sourced (S6) |

**Focus rules**

- On mount the input is focused, so the panel is ready to type, as a popover would be. Our design.
- After Add, focus stays in the input with an empty field (S1-0008).
- Expanding from the input keeps focus in the input. Expanding from a row keeps that row selected and focused.
- Collapsing returns focus to the input.
- Esc never collapses the full view. Collapsing is explicit (`e` or the footer toggle), because the full view is not a transient surface. Our design.
- The panel and the full content share one selected item and one selected date. A date picked in the grid scrolls the list, and scrolling the list moves the grid's selected date to the topmost header (S1-0010).

**States**

| State | Shows |
|-------|-------|
| Empty (no items) | Input and grid stay. The list area shows `EmptyState` with a one-line hint of what to type. A today header with "No items today" in the accent color is the per-day version (S3-0062) |
| Empty input | Grid in its normal place and a disabled Add button when the card is open (S2-0013) |
| Typing | Parse card in place of the grid, updated on every keystroke with no debounce (typing-sheet cells 8-13). A changed field highlights briefly, and not at all under reduced motion. Our design |
| Nothing parsed | The whole text is the title and the other fields show "None". Add stays enabled. The partial-parse look is unseen, so this is our design |
| Loading | `LoadingState` in the list region (and the full content area). The input stays visible, Add is disabled until `status` is `ready`. Our design, no source shows loading |
| Error (load) | `ErrorState` with `onRetry` in place of the list. Grid and input stay, Add is disabled |
| Error (write) | `add` rejects: keep the text in the input and show a toast. Our design, matching the base contract |
| Long title | One line with an ellipsis in rows, grid cells and the footer (S1-0004, S2-0002). The parse card wraps the title to at most two lines |
| Many items | The list scrolls inside its region and the grid stays pinned (S1-0010). A grid cell shows at most 3 dots (S1-0004). A month cell truncates overflow with no "+N more" (S2-0002) |

## Borrow / Leave out

**Borrow**

- One input row at the top of the panel that does the add, with the card replacing the grid on the first keystroke and the grid sliding below (typing-sheet 8-13).
- Fields that resolve live as you type (all-day unchecks, date and times fill, default length 30 minutes), and the grid highlight follows the parsed date (typing-sheet 10-13, S2-0013, S1-0016).
- Enter adds, the field clears, the panel stays open, and the new row lands in time order (S1-0008).
- The same panel in the full view's sidebar, with the same quick-add and card behavior (S2-0002, S2-0013).
- Dots under days, filled today, dimmed adjacent months, pinned grid above a scrolling list (S1-0004, S1-0010).
- Selection that follows one item across list, grid and content (S2-0028, S2-0031).
- Dimmed past items, date headers, one-line rows with ellipsis (S1-0004).
- A compact surface that opens to a larger one (Raycast S3-0027), with an Add button and a named destination in a Quick Entry card (Things S1-0036).

**Leave out**

- Menu-bar popover, detach, keep-in-front, global shortcut: a browser tab has no menu bar.
- Calendar accounts, invitees, Zoom, "Propose Another Time", attachments: need remote services.
- Weather, moon phases, week numbers: decoration with no local data.
- Templates list and inline word highlighting with removable chips: belong to `assisted-notes`.
- Day, Week, Year and Quarter views, and time-zone columns: belong to `view-switcher`.
- Right-hand inspector column and search-results column: belong to `inspector` and `workspace-panes`.
- Gear menu and command list: belong to `action-palette`.
- Priority `!!!` and invitee `with` syntax: no use in a single-user local app.

## Block API

The block is controlled: the app owns the data through `useCollection` and passes it in.

```ts
CONTRACT: type ParsedEntry = { title: string; start?: Date; end?: Date; allDay: boolean; tag?: string; matches: { field: "when" | "tag"; from: number; to: number }[] }
CONTRACT: parseEntry(text: string, now?: Date, tags?: string[]): ParsedEntry
CONTRACT: MiniFull<T extends { id: string; title: string }>(props: MiniFullProps<T>): JSX.Element
CONTRACT: type MiniFullProps<T> = {
  items: T[]
  status: "loading" | "ready" | "error"
  error?: Error
  onRetry?: () => void
  getStart: (item: T) => Date | undefined
  getEnd?: (item: T) => Date | undefined
  getTag?: (item: T) => string | undefined
  fromEntry: (entry: ParsedEntry) => Omit<T, "id">
  onAdd: (item: Omit<T, "id">) => Promise<void>
  onRemove?: (id: string) => Promise<void>
  parse?: (text: string, now: Date) => ParsedEntry
  tags?: string[]
  renderRow?: (item: T, ctx: { selected: boolean; past: boolean }) => ReactNode
  mode?: "mini" | "full"
  onModeChange?: (mode: "mini" | "full") => void
  defaultDurationMinutes?: number
  emptyHint?: string
}
CONTRACT: QuickAdd(props: { value: string; onChange(v: string): void; onSubmit(): void; entry: ParsedEntry; disabled?: boolean; tags?: string[] }): JSX.Element
CONTRACT: ParsePreview(props: { entry: ParsedEntry; onSubmit(): void; disabled?: boolean }): JSX.Element
CONTRACT: UpcomingList<T>(props: { items: T[]; getStart: (item: T) => Date | undefined; selectedId?: string; onSelect(id: string): void; onOpen(id: string): void; renderRow?: MiniFullProps<T>["renderRow"] }): JSX.Element
CONTRACT: MonthGrid(props: { month: Date; selected: Date; marked: Map<string, number>; onSelectDate(d: Date): void; onDoubleClickDate?(d: Date): void }): JSX.Element
```

- `index.ts` also exports `MiniFullProps` and `ParsedEntry`.
- `parseEntry` is a small built-in parser, our design. It handles `today`, `tomorrow`, weekday names, `M/D`, `at 3pm` or `10am`, ranges like `10-11`, `/tag`, and quoted text that the parser leaves alone (S6, typing-sheet). Without a time the entry is all-day. With a start and no end, the end is `defaultDurationMinutes` later (default 30).
- `MiniFull` holds its own state for input text, selected id, selected date and month. Mode is uncontrolled unless `mode` is passed.
- Full mode renders inside `AppShell` with the panel as `sidebar`, the segmented control as `toolbar`, and the list or month as `children`. Mini mode renders the panel alone at a fixed width.
- Base pieces: `useCollection` (in the demo, not the block), `EmptyState`, `LoadingState`, `ErrorState`, `AppShell`, and `useHotkeys` for the keys table.
- shadcn components: `input`, `button`, `card`, `checkbox`, `label`, `badge`, `scroll-area`, `calendar` (for the month grid, with a custom day cell for dots; if that is awkward, a plain button grid is fine), `toggle-group`, `popover`, `command` (tag picker), `kbd`, `tooltip`, `sonner`, `separator`.
- No other pattern is imported and no new dependency is needed.

**`demo.tsx`** default-exports `Demo`: a personal appointments and errands tracker with `useCollection<DemoEvent>("mini-full-demo", seed)`, `DemoEvent = { id; title; start: string; end?: string; allDay: boolean; tag?: "home" | "work" | "health" }`. About 12 seed items dated relative to the day of first load: one past item (dimmed), two on today, one all-day, two sharing a day, one with a very long title, and a few spread over the next month. It shows the mini panel on first render, an Expand button that switches to the full view, and ParsePreview filling as the user types. A small "simulate loading / error" toggle shows the other two states.

## Sources

- [fantastical study note](../apps/fantastical.md), the main source.
  - Panel layout, footer, pinned grid, dots, today circle: S1-0004. Popover closed leaves the window alone: S1-0003. Scroll indicator, grid follows list: S1-0010.
  - Live card, first-keystroke appearance, field-by-field resolve, grid highlight following the date, default 30-minute length: `S1-typing-sheet.png` cells 8-13, S1-0016. `/calendar` picker: S1-0007. Enter and clear: typing-sheet cells 18-19. New row in time order, panel stays open: S1-0008.
  - Gear menu items and shortcuts (⌘0, ⌘T): S1-0012. Full window with a 22% sidebar repeating the panel and its footer: S2-0002. Same card in the sidebar, disabled Add, typed date moves the grid: S2-0013. Selection continuity: S2-0028, S2-0031. Month cell truncation: S2-0002. Empty-day state and the longer "show more" card: S3-0062.
  - Text only: S5 (shortcuts, arrows, delete, ⌥-double-click to jump), S6 (quotes, double-click day starts an entry), S4 (keyboard navigation of the Mini Window).
- [raycast study note](../apps/raycast.md): compact search row that expands to the full list, S3-0027.
- [things study note](../apps/things.md): Quick Entry card with Cancel/Save and a destination, S1-0036 and S1-0041; empty Inbox, S1-0002.
- [granola study note](../apps/granola.md): the same note reflowing from a third-width pane to a full window, S1-0021 and S2-0016.
- Text-sourced from "Patterns fed" lines only: the Linear peek, side pane and full page, and the Obsidian embedded and full-tab base.
- Our design (no source shows it): all key letters other than those cited from S5, focus on mount, Esc behavior, the expand moment from a row, Undo toast, loading, error and write-failure behavior, the built-in `parseEntry`, the footer contents, the List | Month toggle, and the highlight on changed fields.
