# query-tokens

A search box where `key:value` filters turn into removable chips, focus opens a list of keys grouped by type beside recent searches, and anything that is not `key:value` stays plain search text. The parsed query is plain data (chips plus free text) and can live in the URL. It was studied in Sentry.

## When to use

Use it when the user narrows one collection by several fields and wants to type the filter instead of opening a form:

- A recipe collection filtered by `cuisine:thai time:<30 -diet:vegan`, with free words matching the title.
- A photo library or file manager: `type:raw year:2024 -tag:blurry`.
- A personal finance ledger: `account:savings amount:>100 category:travel`.
- A mail or notes search: `from:ana before:2026-01-01 -label:newsletter`.
- A saved-filters feature, where a view stores the query string and restores it later.

Do not use it when:

- The filter is one field with a handful of fixed values: use `view-switcher` (tabs or chips for the views).
- The user filters one list by title only, with no other fields: use the filter input inside `list-peek`.
- The user is looking for an action, not a record: use `action-palette`.
- The user picks many records to act on, not to find them: use `bulk-select`, which can sit under this box.
- The user builds a metric from an aggregate and a group-by: use `aggregate-builder`.

## Anatomy

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Filter row                                                                 │
│ ┌──────────────────────────────────────────────┐                           │
│ │ ⌕ [cuisine is thai ×] [time <30 ×] soup    ✕ /│   7 of 20 recipes       │
│ └──────────────────────────────────────────────┘                           │
│ ┌──────────────────────────────────────────────┐                           │
│ │ RECENT SEARCHES                              │   box ~57% of the row     │
│ │   cuisine:thai time:<30                      │                           │
│ │ CHOICE                                       │                           │
│ │ ▸ cuisine                              thai  │   popover: same width     │
│ │   diet                               vegan   │   as the box              │
│ │ NUMBER                                       │                           │
│ │   time                                  <30  │                           │
│ │ TEXT                                         │                           │
│ │   ingredient                          basil  │                           │
│ └──────────────────────────────────────────────┘                           │
│ Results area (children, or Empty / Loading / Error)                        │
└────────────────────────────────────────────────────────────────────────────┘
```

- **Box:** one bordered row, about 36px tall, that grows to more lines when chips wrap. From left: a search icon, the chips, the text input, a clear-all button (shown when anything is typed or chipped) and a `/` key hint (shown while the box is empty and unfocused). Clicking anywhere in the box focuses the input.
- **Chip:** the key in muted text, an operator word (`is`, `is not`, `>`, `>=`, `<`, `<=`) and the value in the foreground weight, then a remove button. A chip that is selected for deletion gets a visible ring. A chip is a quiet pill, not a button colour.
- **Input:** holds the free text and the word being typed. It is the only tab stop besides the chip remove buttons and the clear button.
- **Suggestion popover:** appears under the box at the box's width while the input has focus. It never takes focus. Sections have a small uppercase heading. A key row shows the key at the left and a short example at the right.
- **Results area:** below the box, only when something goes there: the Loading and Error states, the empty-result state, or the host's results as children.
- **Narrow windows:** the box fills the row and the popover fills the box width.

## Interaction

| Key | Does | Notes |
|-----|------|-------|
| `/` | Focuses the box | Only while focus is on the page body or inside the block. The slash is not typed. |
| Typing a key | Filters the key list by what is typed | `-` in front of a key (our design) negates the chip: `-diet:vegan`. |
| `:` after a known key | Switches the popover to that key's values | `Type a value` hint for a key with no value list. An unknown key stays plain text. |
| Space after `key:value` | Turns the word into a chip | Also when a value is picked from the list. Free words stay in the input. |
| Enter, nothing highlighted | Commits the input: complete `key:value` words become chips, the rest becomes the free text, then `onSubmit` is called | Closes the popover. The free text is applied only now, not on each key (S13). |
| Enter, an option highlighted | Picks the option | A key fills `key:` in the input. A value makes a chip. A recent search replaces the whole query. |
| ArrowDown / ArrowUp | Opens the popover, then moves the highlight through the options | Nothing is highlighted when the popover first opens. |
| Backspace in an empty input | Selects the last chip; a second Backspace removes it (our design) | Any other key, a click elsewhere or Esc deselects. |
| ArrowLeft / ArrowRight at the start of the input | Moves the chip selection (our design) | ArrowRight past the last chip returns to the input. |
| Delete or Backspace with a chip selected | Removes it | Focus stays in the input. |
| Enter with a chip selected | Moves the chip back into the input as `key:value` text to edit (our design) | Clicking a chip does the same. |
| Click the chip's × | Removes the chip | |
| Click the clear button | Clears chips and text and focuses the input | |
| Esc | With a chip selected, deselects it; else closes the popover; else leaves the input | One step per press. |

Keys never fire while focus is in an input, textarea or contenteditable, except the box's own input keys in the table. The one block-level binding is `/`, scoped like `list-peek`'s filter key.

**Focus rules.**

- Focus stays in the input the whole time. The popover is a listbox the input owns (`aria-activedescendant`), so clicking an option never moves focus.
- The popover opens on focus and closes on Enter, on Esc and when focus leaves the box.
- The input commits on blur, so what is shown is what is applied. A suggestion click does not blur the input.
- When the host changes the value from outside (a saved view, the URL, Clear search), the input shows the new text and the chips follow.

**Free text.** A word that is not `key:value` with a known key stays text, so `cuisine:` with no value, `foo:bar` with an unknown key and `"cuisine:thai"` in quotes are all search text. A word in double quotes keeps its spaces: `ingredient:"coconut milk"`. Repeated spaces inside quotes are kept too, and a suggested value that holds quotes or backslashes is escaped when it is inserted.

| State | Shows |
|-------|-------|
| Empty query | The placeholder, the `/` hint, and on focus the recent searches above the key list. |
| No recent searches and no keys | No popover. |
| Loading | The box is shown but disabled, and `LoadingState` fills the results area. |
| Error | The box is disabled and `ErrorState` fills the results area with a Retry button when `onRetry` is given. |
| No results | With a query: `EmptyState` naming the query and a Clear search button. Without one: `EmptyState` with `emptyTitle`. The box stays in place. |
| Value list has no match | A choice key says "No matching value". A number or text key says what to type, since any value is allowed. |

## Borrow / Leave out

Borrow:

- Filters render as small removable chips inside the search box, with a clear-all × at the right edge.
- The box takes more than half of the filter row, beside the other controls.
- Focusing the box opens a popover with the keys; typing narrows it.
- Typed text that is not a filter is offered as a plain text search and does not change the results until Enter.
- A quiet popover with small group headings and a key's example at the right of its row.
- A placeholder that says what can be typed.
- An empty result keeps the box in place so the query can be edited.
- The chip text is a muted key beside a stronger value.
- The query is part of the page address.

Leave out:

- The "Ask AI to build your query" button and the feedback link in the popover footer.
- The tab strip inside the popover (All, Issues, Event Filters, Event Tags, Flags): one list grouped by type does the job.
- The project, environment and time-range buttons next to the box, the sort menu and the Save as button: other patterns own them (`view-switcher`).
- An illustration in the empty state and the tips list: base `EmptyState` is text only.
- The `or` between values (`S5-t0104.png`) and the query language's other operators (wildcards, `has:`): only negation and the comparison operators are built, and they are our design.

## Block API

Files in `gallery/src/patterns/query-tokens/`: `registry-item.json`, `index.ts`, `types.ts`, `query.ts`, `suggestions.ts`, `token-chip.tsx`, `suggestion-popover.tsx`, `use-query-state.ts`, `query-tokens.tsx`, `demo.tsx`.

`query.ts` and `suggestions.ts` are plain TypeScript with no React, so they can be tested alone. `parseQuery` and `serializeQuery` round-trip: `parseQuery(serializeQuery(q), { keys })` equals `q` for any query whose tokens use known keys, and `serializeQuery` of a parsed string is that string with the chips first and the spacing normalized.

```
CONTRACT: type TokenOp = "eq" | "gt" | "gte" | "lt" | "lte"
CONTRACT: type QueryToken = { key: string; op: TokenOp; value: string; negated: boolean }
CONTRACT: type Query = { tokens: QueryToken[]; text: string }       // text is the free words joined by single spaces
CONTRACT: type QueryKey = {
  key: string                         // the word before the colon; letters, digits, _ and .; matched case-insensitively
  type: "choice" | "number" | "text"  // groups the key list
  hint?: string                       // an example, shown at the right of the key row
  values?: string[]                   // suggested values; one may start with <, >, <= or >= to set the operator
}

CONTRACT: parseQuery(input: string, options?: { keys?: string[] }): Query
CONTRACT: serializeQuery(query: Query): string
CONTRACT: matchesToken(token: QueryToken, actual: string | number | readonly (string | number)[] | undefined): boolean
CONTRACT: matchesText(text: string, ...fields: string[]): boolean

CONTRACT: QueryTokens(props: QueryTokensProps): JSX.Element
CONTRACT: type QueryTokensProps = {
  keys: QueryKey[]
  value?: Query                          // controlled; omit for internal state
  defaultValue?: Query
  onChange?: (query: Query) => void      // chips added or removed, free text committed
  onSubmit?: (query: Query) => void      // Enter with a non-empty query; the host records recent searches here
  urlParam?: string                      // opt in: read this search param on mount and write it on every change
  recent?: string[]                      // serialized queries, newest first; the host stores them
  status?: "loading" | "ready" | "error" // default "ready"; pass useCollection's status
  error?: Error
  onRetry?: () => void
  resultCount?: number                   // 0 shows the no-results state under the box
  emptyTitle?: string                    // shown when the collection itself is empty
  emptyAction?: ReactNode                // e.g. a "Restore samples" button, under the empty title
  placeholder?: string
  autoFocus?: boolean
  boxClassName?: string                  // sizes the box inside the filter row, e.g. "lg:grow-0 lg:basis-[57%]"
  toolbar?: ReactNode                    // sits after the box in the same row: a count, a sort control
  "aria-label"?: string
  children?: ReactNode                   // results, shown when ready and not empty
}
```

`index.ts` exports `QueryTokens`, `TokenChip`, `SuggestionPopover`, `useQueryState`, `parseQuery`, `serializeQuery`, `matchesToken`, `matchesText` and the types `Query`, `QueryToken`, `QueryKey`, `TokenOp` and `QueryTokensProps`. `demo.tsx` default-exports `Demo`.

**URL.** With `urlParam="q"` the block reads `?q=` once on mount (and reports it through `onChange`, so a host that keeps its own copy sees it) and writes the serialized query on every change with `history.replaceState`, changing only the search part. The hash is left alone, so the gallery's `#/<slug>` route survives and no history entries pile up. An empty query removes the param. Without `urlParam` the block never touches the address.

**Recent searches.** The block stores nothing. The host passes `recent` and records new entries from `onSubmit` (the demo keeps them in a second `useCollection`). Choosing one replaces the whole query.

Uses from the base:

- `EmptyState`, `LoadingState`, `ErrorState` from `src/components/mini/states.tsx` for the results area.
- `useHotkeys` from `react-hotkeys-hook` for `/`.
- shadcn components, all pre-installed: `badge` (demo), `button`, `kbd`. No new dependencies.

`demo.tsx` shows a recipe collection of 20 invented recipes stored with `useCollection("query-tokens-demo", seed)`, and the recent searches in `useCollection("query-tokens-demo-recent", [])`. Keys: `cuisine`, `course` and `diet` (choice), `time` and `rating` (number), `ingredient` (text). The box takes about 57% of the filter row on wide screens, with the match count beside it (the `toolbar` prop). Rows show the name, badges, time and rating. A "State preview (demo only)" control (live, empty, loading, error) forces each state, and a plain-text footer lists the keys.

## Sources

[sentry study note](../apps/sentry.md).

- **Chips in the search box with a clear-all ×:** `S13-issue-stream.png` (`is unresolved` chip, × at the right edge) and `S8-save-button.png`.
- **Box takes about 57% of the filter row:** `S13-issue-stream.png`; `S3-t1220.png` (about 60%).
- **Chip text, a muted key beside a stronger value:** `S5-t0040.png` (`span.op is db`).
- **Focus opens a key list under the box, placeholder says what can be typed:** `S5-t0032.png`, `S13-search-suggestions.png` (a scrolling list of keys with a short label at the right; ours shows an example value there instead of the type).
- **Free text offered as plain search, applied on Enter:** `S13-search-typing.png`.
- **Empty box returns to the placeholder:** `S5-t0080.png`.
- **Recent searches:** `S5-t0032.png` shows a Recent tab beside All; the study note records the tab, not its contents.
- **Query in the URL:** the address bar in `S5-t0040.png` carries `query=span.op:db`.
- **Empty result keeps the box in place:** `S13-issue-stream-empty-filter.png`.
- **Our design:** `/` focusing the box, negation with `-`, comparison operators, quoted values, Backspace selecting then removing the last chip, chip selection with the arrow keys, Enter or click on a chip to edit it, grouping keys by type instead of tabs, the value step after choosing a key, Esc steps, commit on blur, recent searches above the keys, the `urlParam` prop and `replaceState` rule, the host-owned recent list, `onSubmit`, and the demo.
