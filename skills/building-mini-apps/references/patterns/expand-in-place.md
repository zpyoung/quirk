# expand-in-place

A one-line list row opens in place into an editable card, and optional fields stay out of sight until an icon strip asks for them; studied in Things 3 (Mac), with smaller hints from Fantastical, Craft and Notion.

## When to use

Fits apps where each item has a title plus a few optional details, and the list is the main screen:

- A to-do or chore list where most items need only a title, and a few get a date, tags or a checklist.
- A reading or watch list with optional rating, link and notes per entry.
- A habit or bug tracker where a quick scan matters more than seeing every field at once.
- A shopping or packing list with optional quantity and note per row.

Do not use it when:

- Items have many required fields or need side-by-side comparison. Use `staged-table-edit` (table rows) or `inspector` (a persistent detail panel).
- Opening an item should show a long document or a full page. Use `doc-collections` or `list-peek` (peek, then promote to a full page).
- The list is large and the user edits mostly from the keyboard in bulk. Use `staged-table-edit`.
- Creation is a separate quick-add that parses text. Use `mini-full` or `assisted-notes`.

## Anatomy

```
 ┌──────────────────────── list column, ~820px max, centered ────────────────────────┐
 │  Page title                                                                        │
 │                                                                                    │
 │   ○  Collapsed row, one line                                    ▤  (state glyphs)  │  ~27px pitch
 │   ○  Collapsed row, one line                                                       │
 │  ┌──────────────────────────────────────────────────────────────────────────┐ ←    │
 │  │ ○  Title being edited|                                                   │ ~14px│  open card,
 │  │    Notes                                                                 │ wider│  ~135-350px
 │  │    ▢ Due: Fri, 23 Aug                                              [x]   │ on   │  tall, grows
 │  │    ▢ Tags: home, errand                                            [x]   │ each │  with filled
 │  │                                               [cal] [tag] [list]         │ side │  rows
 │  └──────────────────────────────────────────────────────────────────────────┘      │
 │   ○  Collapsed row, one line                                                       │
 └────────────────────────────────────────────────────────────────────────────────────┘
                     [ footer bar: swaps its buttons while a card is open ]
```

- **Collapsed row**: checkbox or marker, one-line title, trailing glyphs (notes, checklist) for fields that have a value.
- **Open card**: raised panel, no border, soft shadow, slightly wider than the column. Holds the title field, a notes field, and one row for each field that has a value.
- **Field rows**: stacked below notes in a fixed order. A filled row shows its value; hovering it shows a remove (x) control.
- **Icon strip**: bottom right of the card, one icon per field that is still empty. Filling a field removes its icon.
- **Field editor**: a popover (date, picker) anchored to the icon or row that opened it.
- **Footer bar**: optional; its buttons change while a card is open.

## Interaction

| Key | Does | Notes |
|---|---|---|
| Enter | Opens the selected row | Our design; no source shows the trigger. Ignored while typing in an input |
| Click on a row | Opens that row; any open card collapses first | Our design (one card open at a time) |
| Esc | Closes an open field popover first, otherwise collapses the card | Our design. Works while typing in the card; never discards edits |
| ⌘Enter | Collapses the card | Our design. Works while typing in the card |
| N | Adds a new item and opens its card at the end of the list | Things uses ⌘N (hint text in S1-0003); `n` is our design because the browser reserves ⌘N. Ignored while typing in an input |
| ↑ / ↓ | Moves row selection | Our design. Ignored while typing in an input |
| Click an icon in the strip | Opens that field's editor and focuses it | The icon becomes a labeled field with a popover (S1-0107, S1-0040) |
| Click an x on a field row | Clears the field; its icon returns to the strip | Chip shows the x on hover only (S3-0020, S3-0021) |

Focus rules:

- Opening a row moves focus to its title field with the caret at the end (S1-0075). A new item opens with an empty title focused.
- Choosing an icon moves focus into that field's editor. When the editor closes, focus returns to the title field.
- Collapsing returns focus to the row that was open, still selected, so ↑ / ↓ continue from there. Our design.
- Edits save as you type through `useCollection.update`; there is no Save button. Our design, because the local app has no sync step.
- Collapsing a new item whose title is empty removes it. Our design.
- The list's context pre-fills fields: an item created in a filtered view opens with that field already set, shown as a filled row (S3-0017).

| State | Shows |
|---|---|
| Empty | `EmptyState` with the title, one line of hint ("Press N to add an item"), and an add button. S1-0002 shows a nearly blank list and S1-0003 a grey italic hint; the button is our design |
| Loading | `LoadingState` in place of the list; the footer bar and page title stay |
| Error | `ErrorState` with retry in place of the list. A failed save keeps the card open with the last good values and raises a toast. Both are our design; no source shows an error |
| Long title | Collapsed row truncates to one line with an ellipsis; the open card wraps the title over several lines. Our design |
| Long notes or checklist | The card grows with its content up to a max height of about 70% of the viewport, then scrolls inside. Our design; no source shows it |
| Many items | The list column scrolls; the open card scrolls into view when opened. Our design. Rows are not virtualized (under about 500 items) |
| Many filled fields | Rows stack in fixed order (S3-0022); the icon strip becomes empty and disappears |

## Borrow / Leave out

Borrow:

- A card that opens at the row's own position, wider than the list column, with the other rows staying where they are (S1-0014, S1-0013).
- Fields are rendered only when they have a value, so a blank card is title, notes and an icon strip (S1-0013, S1-0067).
- An icon strip for empty fields; each icon leaves the strip when its field is filled and returns when the value is cleared (S1-0075, S1-0076).
- Field rows in a fixed order, each with an x that shows on hover or pointer interaction (S3-0020, S3-0022).
- Pre-filled fields from the list's context (S3-0017).
- Trailing glyphs on collapsed rows for notes and checklist (S4 features stills).
- A floating footer bar whose buttons change while a card is open (S1-0013). Optional in our block.
- Popover editors anchored to the icon, with a Clear action when a value is set (S3-0021).

Leave out:

- Quick Entry floating window with Cancel and Save (S1-0041): belongs to `mini-full`.
- Natural-language date entry ("in 3 days", S4): belongs to `assisted-notes`.
- Today, Upcoming, Anytime and Someday lists, areas, projects: Things-specific data model.
- Calendar event panels, repeat rules, reminders, mail-to-do links: need services a local app lacks.
- Right-click menu with printed shortcuts (S2-0051): belongs to `action-palette`.
- The card's transition animation: not seen in any source. Our block uses a short height transition (about 150ms, our design) that respects reduced motion.
- Things' icon set, blue and yellow accents, dark popover styling: brand, and the house style replaces them.

## Block API

Files in `gallery/src/patterns/expand-in-place/`: `index.ts`, `demo.tsx`, `registry-item.json`, plus component files. `dependencies` is empty (uses `react-hotkeys-hook` from the base). `registryDependencies`: `button`, `input`, `textarea`, `popover`, `calendar`, `checkbox`, `badge`, `tooltip`, `kbd`, `scroll-area`.

```ts
CONTRACT: type ExpandItem = { id: string; title: string; notes?: string }

CONTRACT: type ExpandField<T extends ExpandItem> = {
  key: string                                        // unique, used for strip order
  label: string                                      // tooltip, editor label, row label
  icon: ReactNode                                    // supplied by the app; the block ships no icon set
  isSet(item: T): boolean                            // false means: icon in strip, no row
  display(item: T): ReactNode                        // value shown in the filled row and chip
  clear(item: T): Partial<T>                         // patch that empties the field
  Editor(props: {
    item: T
    onChange(patch: Partial<T>): void                // saves immediately
    onClose(): void                                  // closes the popover, focus back to title
  }): ReactNode
  glyph?: ReactNode                                  // trailing glyph on the collapsed row when set
}

CONTRACT: ExpandList<T extends ExpandItem>(props: {
  collection: string                                 // useCollection name
  seed?: T[]
  fields: ExpandField<T>[]                           // strip and row order follows this array
  newItem(): T                                       // defaults for N, including context pre-fill
  renderRow?(item: T): ReactNode                     // replaces the default one-line title
  emptyTitle?: string
  onError?(error: Error): void                       // called when a write rejects; default is a sonner toast
})

CONTRACT: ExpandCard<T extends ExpandItem>(props: {
  item: T
  fields: ExpandField<T>[]
  onChange(patch: Partial<T>): void
  onClose(): void
})

CONTRACT: DateField<T extends ExpandItem>(key: keyof T & string, label: string, icon: ReactNode): ExpandField<T>
CONTRACT: TextField<T extends ExpandItem>(key: keyof T & string, label: string, icon: ReactNode): ExpandField<T>
```

- `ExpandList` owns selection, which card is open, and the hotkeys (`useHotkeys` from `react-hotkeys-hook`, disabled while focus is in an input, textarea or contenteditable). It reads and writes through `useCollection<T>`.
- `ExpandCard` is exported separately so another block's app code can render the card without the list. It never imports another pattern.
- Status handling: `status === "loading"` renders `LoadingState`, `"error"` renders `ErrorState` with a reload callback, and an empty `items` array renders `EmptyState`.
- `DateField` uses `popover` plus `calendar`; `TextField` uses `popover` plus `input`. A checklist field is an app-supplied `ExpandField` and not shipped.
- Shadcn components used: button, input, textarea, popover, calendar, checkbox, badge, tooltip, kbd, scroll-area. `separator` and `card` are not required.

`demo.tsx` default-exports `Demo`, a task list of about 8 items inside `AppShell` titled "Errands". Items have `title`, `notes`, `due` and `tags`: three have a due date, two have tags, one has notes, and the rest are title-only so most rows collapse to a bare line. One item has a very long title to show truncation. Two fields are configured (`due` as `DateField`, `tags` as `TextField`). The seed is passed to `useCollection("expand-demo", seed)`, so the demo needs no setup.

## Sources

- [things study note](../apps/things.md), primary source for every behavior unless marked otherwise.
- Card shape and placement: S1-0013, S1-0014, S1-0016, S1-0017, S1-0075; dark theme variant S2-0010.
- Fields appear only when set, fixed order, strip shrinks: S1-0075, S1-0076, S1-0067, S3-0022, S4 features-checklists-mac.
- Pre-filled context field: S3-0017.
- Remove x on hover: S3-0020, S3-0021.
- Field editor popovers and the icon becoming a labeled field: S1-0107, S1-0040, S2-0028, S3-0021 (Clear when a value is set).
- Footer bar swap: S1-0013 compared with S1-0002.
- Empty state and new-item hint (⌘N in Things; `n` is our design because the browser reserves ⌘N): S1-0002, S1-0003.
- Trailing glyphs on collapsed rows: S4 features-checklists-mac, S4 features-today-mac.
- Intent quote ("tucked away in the corner until you need them"): S4 text.
- Smaller hints, not studied in depth: [fantastical study note](../apps/fantastical.md) (compact card with a "show more" chevron), [craft study note](../apps/craft.md) (child page as a row with excerpt, S2-0004), [notion study note](../apps/notion.md) (S1-0014 expand control).
- Text-sourced: the Things quote above.
- Our design, not seen in sources: row-open trigger and keys (Enter, Esc, ⌘Enter, ↑ / ↓), focus return on collapse, autosave, discarding an empty new item, error and long-content handling, the Empty-state button, the height transition, and the API in Block API.
- Unseen in sources (see the Things "Unseen" section): the open/close transition, what closes a card, loading and error states, long checklists.
