# doc-collections

A page made of blocks, where some blocks are small tables of records; opening a record shows its properties above a free-text body. Studied in Craft 3 (collections inside documents).

## When to use

Use it when the records need prose around them or inside them:
- A reading journal: an intro essay, a books table, and a review in each book's body.
- Trip planning: itinerary notes, a places table (country, season, budget), and per-place notes.
- A project hub: a goals paragraph, a tasks table and a risks table, each task with its own notes.
- A content calendar where each row is a draft with fields on top and the draft text below.

Do not use it when:
- The data is only rows and columns with no prose: use `staged-table-edit` for cell editing, or `list-peek` for a list with a side preview.
- Rows need a quick look without leaving the list: use `list-peek` (here, opening replaces the page; no frame shows a peek).
- Several documents must stay open side by side: use `workspace-panes`.
- The same rows need table, board and filtered views: add `view-switcher`; this pattern ships one grid per collection.

## Anatomy

```
┌───────────────────────────────────────────────────────────┐
│ Reading List > Books              (breadcrumb, one line)  │ ~32px
├───────────────────────────────────────────────────────────┤
│              ┌─ document column, ~65% wide, centered ──┐  │
│              │ # Reading List            (page title)   │  │
│              │ Intro paragraph, free text (text block)  │  │
│              │ ┌─ collection block ───────────────────┐ │  │
│              │ │ Books              [search][+ Add]   │ │  │ ~30px
│              │ │ #  Title        Status   Rating  ... │ │  │ header
│              │ │ 1  Dune  (>)    Finished    4        │ │  │ rows ~30px,
│              │ │ 2  Deep Work    Reading     0        │ │  │ up to ~14
│              │ │ 3  ...                       ───scroll│ │  │ then scroll
│              │ └──────────────────────────────────────┘ │  │
│              │ More free text after the table           │  │
│              └──────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘

Opened record replaces the document column:
┌───────────────────────────────────────────────────────────┐
│ Reading List > Books > Dune                               │
│              ┌──────────────────────────────────────────┐ │
│              │ Dune                         (title)     │ │
│              │ Status   [Finished]   label | value ~50% │ │ rows ~26px
│              │ Rating    4                              │ │
│              │ Started   Empty                          │ │
│              │ ──────────────────────────────────────── │ │
│              │ Free body text, any length (textarea)    │ │
│              └──────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────┘
```

- **Breadcrumb**: page, collection, record; each earlier crumb goes back there.
- **Document column**: one scrolling column of blocks; the table width matches the text column.
- **Text block**: free text between collections; click to edit.
- **Collection block**: name, a small toolbar (search, add), a header row, numbered rows, an open button beside each title.
- **Record page**: title, a label/value property list, then the body, then a "Delete record" button below the column.
- **Page footer**: "Add text" and "Add collection" buttons below the last block. A new collection is named "Collection N" and starts with one text field, Notes.

## Interaction

| Key | Does | Notes |
|---|---|---|
| ↓ / ↑ or j / k | Move row selection within the focused collection | Act only while the collection grid itself has focus, so they are ignored in the search box and in property inputs; stops at first and last row |
| Enter | Open the selected record | Same as clicking the open button; needs a selected row and grid focus |
| Esc | Close the open record and return to the document | If focus is in a property input or the body, the first Esc blurs it and the second closes |
| n | Add a record to the focused collection and open it | Same focus rule as the arrows; our design |

Focus rules:
- Opening a new record puts focus in its title with the text selected; opening an existing record focuses the record page container so Esc works.
- Closing returns focus to the row that was opened, and the document scroll position is restored (our design; Craft's scroll behavior was not shown).
- Clicking a property value opens a small popover and the choice applies on click, with no save button. Text, number and date properties commit on Enter or blur.
- Rows are not focusable one by one; the collection block has one tab stop and arrows move the selection inside it.

| State | Shows |
|---|---|
| Empty collection | Block name, header row, then an inline `EmptyState` ("No records", Add button). Craft shows only an empty numbered grid; we add the message |
| No search matches | Inline `EmptyState` "No matches" naming the search text; the header row stays |
| Empty document | `EmptyState` "Empty page" with an "Add text" and "Add collection" action |
| Empty property | Grey "Empty" in the value slot |
| Empty record body | Placeholder "Write something" in the textarea; properties still show |
| Loading | The block takes no `status`; the app renders `LoadingState` in place of `DocCollections`, as the demo does |
| Error (load) | Same: the app renders `ErrorState` with retry in place of `DocCollections` |
| Error (save) | A rejected write shows a `sonner` toast ("Could not save: …"), and an edited title, body or property snaps back to its last good value |
| Long title | One line with ellipsis in the table; wraps in full in the record title |
| Many rows | The block grows to about 14 rows, then scrolls inside itself; wide field sets scroll sideways inside the block |
| Many collections | The page grows; the document column scrolls as one |
| Long body | The record page scrolls; properties are not pinned |

## Borrow / Leave out

Borrow:
- The page is a stack of blocks; a collection is one block among text blocks.
- Every row is a full record: properties on top, free body below.
- A small open button beside the title opens the record; it replaces the page.
- Title is always text and cannot be removed; other fields are typed (text, number, checkbox, date, URL, select).
- Property editing happens in place: popover pick for select, no save button.
- The record keeps its trail (page, collection, record) in the breadcrumb.
- Empty values read "Empty"; row numbers sit in the first column; the block shrinks to fit its rows.
- A new collection starts with Title plus one field.

Leave out:
- Cover images, page styles, backdrops: decoration, not behavior.
- Sharing, publishing, comments: a local app has one user.
- Page/card display toggle and card tiles: a second layout that belongs to `view-switcher`.
- Saved views, filters, grouping, sort: owned by `view-switcher`.
- Relation and link-to-block fields: need cross-collection joins that a single-store demo does not carry.
- Field configuration dialogs: fields are declared in code.
- Tab strip, sidebar outline of records, back/forward history: owned by `workspace-panes`.
- Slash-command insertion of blocks: owned by `action-palette`; here two buttons add blocks.
- Multi-row selection and drag reorder: not shown in any source.

## Block API

`index.ts` exports `DocCollections`, `RecordPage`, `CollectionBlock`, `PropertyValue` and the types `PropValue`, `FieldDef`, `DocRecord`, `CollectionDef`, `DocBlock` and `DocPage`. It does not read the store: `page` and `records` come in as props, and the demo wires them to `useCollection`. It uses `EmptyState` from the base, `useHotkeys` from `react-hotkeys-hook`, and shadcn `button`, `input`, `textarea`, `popover`, `command`, `checkbox`, `badge`, `separator`, plus `sonner` for save errors (the app's single `AppShell` mounts the `Toaster`). No new dependencies.

```ts
CONTRACT: type PropValue = string | number | boolean | null
CONTRACT: type FieldDef = { key: string; label: string; type: "text" | "number" | "checkbox" | "date" | "url" | "select"; options?: string[] }
CONTRACT: type DocRecord = { id: string; title: string; collectionId: string; props: Record<string, PropValue>; body: string }
CONTRACT: type CollectionDef = { id: string; name: string; fields: FieldDef[] }
CONTRACT: type DocBlock = { id: string; kind: "text"; text: string } | { id: string; kind: "collection"; collectionId: string }
CONTRACT: type DocPage = { id: string; title: string; blocks: DocBlock[]; collections: CollectionDef[] }

CONTRACT: DocCollections<T extends DocRecord>(props: {
  page: DocPage; onPageChange(page: DocPage): void;
  records: T[]; onAdd(collectionId: string): Promise<T>;
  onUpdate(id: string, patch: Partial<T>): Promise<void>; onRemove(id: string): Promise<void>;
  openId?: string | null; onOpenChange?(id: string | null): void;
})
CONTRACT: RecordPage<T extends DocRecord>(props: { record: T; fields: FieldDef[]; onUpdate(patch: Partial<T>): Promise<void>; onClose(): void; trail: string[] })
CONTRACT: CollectionBlock<T extends DocRecord>(props: { def: CollectionDef; records: T[]; selectedId?: string; onSelect(id: string): void; onOpen(id: string): void; onAdd(): void })
CONTRACT: PropertyValue(props: { field: FieldDef; value: PropValue; onChange(value: PropValue): void })
```

- `DocCollections` is controlled for the page and records, so the app owns storage. `openId` is optional; without it the component keeps the open record in its own state. Callers back `page` with a `useCollection<DocPage>` record and `records` with a `useCollection<DocRecord>`, as the demo does.
- Open state is not persisted, and a stale `openId` (record removed) closes to the document.
- `onAdd` creates the record in the store and resolves with it so the block can open it.
- `status` from `useCollection` maps to `LoadingState` and `ErrorState` in the caller; `DocCollections` renders `EmptyState` when `page.blocks` is empty.
- The open record page offers "Delete record", which calls `onRemove` and returns to the document.

`demo.tsx`: default-exports `Demo`, a reading journal with one page: an intro text block, a "Books" collection (Status select, Rating number, Started date, Owned checkbox) of about 12 records, a text block, and a second small "Quotes" collection of about 5 records. About half the books have a short body, one has a very long title, and one has no body. The demo renders no `AppShell`; the app provides it. It seeds two collections, `doc-collections-demo-page` (the page) and `doc-collections-demo` (the records), through `useCollection`. A "Preview state" group (live, empty, loading, error) forces each state; the empty preview edits an in-memory copy so it never touches the stored journal.

## Sources

- [craft study note](../apps/craft.md), frames in `references/media/craft/`.
- Page as blocks, collection inserted as a block, table width matches text column: S1-0017, S1-0003, S1-0007, S5 page text.
- Empty collection is an empty numbered grid; toolbar icons visible without hover: S1-0019, S3-0025.
- Default fields Title plus one; Title type locked: S1-0020, S3-0025.
- Field types and the typed-field set: S1-0026 (the "Link to Block", Phone, Email and Relation types are left out).
- Row density (~30 px), numbered gutter, open button beside the title, horizontal scroll inside the block, right-aligned numbers: S1-0004, S1-0007.
- Opening a record replaces the page; properties above body; "Empty" values; breadcrumb keeps parent chain: S1-0005, S1-0006, S1-0038.
- Property edit by popover pick with no save button: S1-0009.
- Block shrinks to fit its rows: S1-0015.
- New record opens with the title focused: text-sourced from Notion's new-page peek, [notion study note](../apps/notion.md) S3-0003.
- Our design: keys table (j/k, Enter, Esc, n), focus return to the opened row, scroll restore, two-step Esc, inline `EmptyState` message, row cap of about 14 before inner scroll, save-error toast, "Add text / Add collection" buttons, controlled props API. Craft's keyboard use, loading and error states are listed under Unseen in the study note.
