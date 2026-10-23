# assisted-notes

A note page where the user's own lines stay primary and generated lines sit beside them in a quieter style, each with a way back to the excerpt it came from; studied in Granola (see the [granola study note](../apps/granola.md)).

## When to use

Use it when the user writes first and something else adds to it later, and the added text must be checkable.

- A meeting or call log: typed bullets, plus follow-ups drafted from a pasted transcript.
- A reading journal: the user's reactions, plus generated summaries that quote the passage they came from.
- A research scratchpad: the user's findings, plus suggested connections that cite the clipping behind each.
- A bug triage note: the user's observations, plus a generated "likely cause" list that points to log lines.

Do not use it when:
- There is no generator and no second voice. A plain editor needs no provenance; use `doc-collections` for notes in folders.
- The additions are edits to structured fields. Use `staged-table-edit` to review changes before they land.
- The user wants a read-only detail view of a row with no authored text. Use `inspector`.
- The two versions are alternate whole documents, not interleaved lines. Use `view-switcher`.

The block never calls an AI service. The app supplies a generator, which can be a canned function, a local script, a pasted result or a fetch to something the user runs.

## Anatomy

```
 ┌──────────────────────────── note column, 560 px max, centered ───────────────┐
 │ Title (single line, grows to 2)                          [Mine | Enhanced]   │ ~12%  header
 │ ─────────────────────────────────────────────────────────────────────────── │
 │ # Heading (user)                                                             │
 │  • user line, full foreground color                                          │
 │  • generated line, muted color, left rule   [Source]  <- on hover or focus   │ ~76%  body
 │      ┌─ source popover, ~60% of column ────────────┐                         │       (scrolls)
 │      │ SUMMARY / label                             │                         │
 │      │ short explanation                           │                         │
 │      │ ▌ quoted excerpt in a muted block           │                         │
 │      └─────────────────────────────────────────────┘                         │
 │  • user line                                                                 │
 │ ─────────────────────────────────────────────────────────────────────────── │
 │ [ Generate  ⌘↵ ]                              legend: ■ Yours ▒ Generated    │ ~12%  footer
 └──────────────────────────────────────────────────────────────────────────────┘
```

- Notes list: a narrow column of note titles at the left of the block, with a New note button. The selected note fills the rest.
- Header: title input and a two-segment toggle, `Mine` (user lines only) and `Enhanced` (both).
- Body: one row per segment. User rows are editable and full color. Generated rows are read-only, muted, with a left rule and a hidden `Generated` label for screen readers.
- Source button: appears on hover or keyboard focus of a generated row and opens the source popover.
- Source popover: label, short explanation, then the quoted excerpt in a muted block.
- Generating banner: a status line with Cancel that appears under the title while a generator runs (see States).
- Footer: the Generate button and a two-item legend.

## Interaction

| Key | Does | Notes |
|---|---|---|
| `Mod+Enter` | Generate, or regenerate | Also fires inside the note text areas; this is the one binding that does |
| `M` | Toggle Mine / Enhanced | Ignored while typing in an input or text area |
| `ArrowDown` / `ArrowUp` | Move focus to next / previous row | Rows are focusable; inside a text area it moves the caret instead until the first or last line |
| `Enter` on a user row | New empty user row below | Plain Enter in a text area; `Shift+Enter` is a line break. In the title, Enter moves focus to the first row |
| `Enter` on a generated row | Open its source popover | Same as clicking Source |
| `Backspace` on an empty user row | Delete the row, focus the previous row | |
| `Esc` | Close the popover; else cancel generation; else blur the row | One layer per press |

Focus rules:
- Opening a popover moves focus to its first control (Keep as mine, or the excerpt if the segment has no keep action). Esc and click-outside close it and return focus to the Source button of that row.
- Generate keeps focus on the button. When generation finishes, focus stays where it was and a polite live region reads `N lines added`.
- Switching view keeps the focused row if it exists in the new view; otherwise focus goes to the title.
- A new note focuses the first user row, showing the placeholder `Write notes...`.
- A note opens in Enhanced when it already has generated lines, otherwise in Mine; each note remembers its own view for the session.

| State | Shows |
|---|---|
| Collection empty | `EmptyState` with a `New note` action; the notes list also has a New note button |
| Collection loading | `LoadingState` with the label `Loading notes` |
| Collection load error | `ErrorState` with Retry, which reloads the page |
| Note with no lines | One empty user row with the placeholder `Write notes...`; Generate is disabled |
| Mine view, no user lines | Placeholder only, the same as a new note |
| Enhanced view, nothing generated yet | Muted text `Nothing generated yet` and a Generate button in place of the body |
| Generating | A status banner under the title, `Analyzing...` with Cancel; user rows stay editable; the generated rows replace the old ones all at once when the generator resolves |
| Generation failed or cancelled | The banner turns into a one-line error message ("Generation cancelled" after Cancel) with Retry; user lines are untouched and any previous generated lines are kept |
| Generated line with no source | Row shows a `No source` badge instead of the Source button |
| Very long title | Wraps to two lines in the header, then truncates with the full title in a tooltip; the list in the demo truncates to one line |
| Very long line | Wraps within the column; rows never scroll sideways |
| Long excerpt | Popover clamps the excerpt to about 8 lines and scrolls inside |
| Many lines | Only the body scrolls; header and footer stay pinned |

## Borrow / Leave out

Borrow:
- User lines in the strongest text color, generated lines in a muted one, with a legend naming both. The study app's own vendor key does this.
- One row-level affordance (hover highlight plus a small Source button at the row's right end) that works for bullets and numbered items alike.
- A popover anchored under the row with a label, a short explanation and the quoted source, overlapping the note beneath it.
- A two-segment toggle between the user's own notes and the enhanced note.
- A generating banner under the title with Cancel, while the user's raw lines stay visible below it.
- Placeholder `Write notes...` on an empty note, with no toolbar.
- A pinned footer with the generate control; the page body scrolls above it.

Leave out:
- Live transcription, the floating transcript card and the audio indicator: needs microphone capture and a service the block does not own.
- Chat bar, recipes grid and model picker: a separate pattern (`action-palette`), and an AI service call.
- Template menu with numbered rows: needs a generator that varies by template; the app can add it through `view-switcher`.
- Calendar chips, attendee chips, share and folder controls: meeting-product features with no local data behind them.
- Color alone as the distinction: the source's grey is hard to read for some users, so we add a left rule and a screen-reader label.
- Serif title, green accents, logos and recording-pill styling: brand look, replaced by the house tokens.

## Block API

Public exports of `index.ts`: `AssistedNotes`, `AssistedNotesProps`, `NoteView`, `NoteViewProps`, `SourcePopover` and the types `NoteOrigin`, `SourceRef`, `NoteSegment`, `AssistedNoteItem` and `NoteViewMode`. Types:

```
CONTRACT: type NoteOrigin = "user" | "generated"
CONTRACT: type SourceRef = { excerpt: string; label?: string; summary?: string }
CONTRACT: type NoteSegment = {
  id: string; origin: NoteOrigin; text: string
  kind?: "heading" | "bullet" | "text"       // default "bullet"
  after?: string                             // generated only: id of the user segment it follows; unset = end of note
  source?: SourceRef                         // generated only
}
CONTRACT: type AssistedNoteItem = { id: string; title: string; segments: NoteSegment[] }
```

Components:

```
CONTRACT: type NoteViewMode = "mine" | "enhanced"

CONTRACT: type AssistedNotesProps<T extends AssistedNoteItem> = {
  collection: string                         // useCollection name
  seed?: T[]
  onGenerate?: (note: T, signal: AbortSignal) => Promise<NoteSegment[]>
  newNote?: () => T                          // factory for the New note actions
  className?: string
}
CONTRACT: AssistedNotes<T extends AssistedNoteItem>(props: AssistedNotesProps<T>): JSX.Element

CONTRACT: type NoteViewProps<T extends AssistedNoteItem> = {
  note: T
  view: NoteViewMode
  onViewChange: (v: NoteViewMode) => void
  onChange: (patch: Partial<T>) => void      // title and user-segment edits
  onGenerate?: () => Promise<void>
  onCancel?: () => void
  generating?: boolean
  error?: Error
}
CONTRACT: NoteView<T extends AssistedNoteItem>(props: NoteViewProps<T>): JSX.Element
CONTRACT: SourcePopover(props: { segment: NoteSegment; onKeep?: (id: string) => void; children: ReactNode })   // children is the trigger; without segment.source it renders children alone
```

Rules the block enforces:
- `onGenerate` returns generated segments only. The block forces their `origin` to `"generated"`, replaces all earlier generated segments of that note, and leaves user segments untouched.
- Generated lines are never editable. `Keep as mine` in the popover rewrites that segment to `origin: "user"` and drops its `source`.
- The block writes through `useCollection(collection, seed).update`; a rejected write surfaces as a `sonner` toast and the on-screen note stays as typed.

Base pieces: `useCollection` for items and `status`; `EmptyState`, `LoadingState`, `ErrorState` for the three collection states; `useHotkeys` from `react-hotkeys-hook` for the keys table (`enableOnFormTags` only on `mod+enter`). `AppShell`, with the `Toaster` and `TooltipProvider` it mounts, is the app's, not the block's or the demo's.

shadcn components used (all pre-installed): `button`, `textarea`, `toggle-group`, `popover`, `scroll-area`, `badge`, `kbd`, `tooltip`. `registry-item.json` declares the npm `dependencies` `react-hotkeys-hook` and `sonner`.

`demo.tsx` default-exports `Demo`: a volunteer garden-day planning log with 6 notes of up to 12 segments each, mixing user and generated lines, stored under collection `assisted-notes-demo`. Each note carries a `transcript` string; the demo's `onGenerate` is a local function that waits about 1.2 s (honoring `signal`), then builds generated lines from sentences of that transcript, each with the sentence as `source.excerpt`. One note starts empty, one has a generated line with no source, and one has a very long title, so the demo shows each state. A "Preview state" toggle group (live, empty, loading, error) swaps the block for the matching base state component.

## Sources

- [granola study note](../apps/granola.md)
- User text plain and primary, no toolbar, placeholder: S1-0021, S1-0005, S2-0030 (`S1-0021.png`, `S1-0005.png`, `S2-0030.png`).
- Dark user lines vs grey generated lines, lightly cleaned user text still dark, one dark line not typed by the user (so color is a hint, not proof, and we add a non-color cue): S1-0001, S1-0002, S2-0022, S5-enhanced-notes-1; vendor legend in S4 (`S4-blog-notes-vs-enhanced.png`).
- Row hover highlight and per-row Source button, works on numbered items: S1-0002, S3-0069.
- Source popover (label, explanation, quoted excerpt, about 60% width, overlaps note): S5-enhanced-notes-2.
- Mine / Enhanced toggle and regenerate-after-editing: S5-enhanced-notes-3 and the S5 page text; raw-note shortcuts and `#` headings in S7 page text.
- Generating banner with Cancel and raw lines visible beneath: S2-0018, S7-taking-notes-1, S1-0024.
- Pinned footer bar: S1-0002, S2-0022.
- Text-sourced: first output is not final, regenerate after edits (S4 and S5 page text).
- Our design: `Mod+Enter`, `M`, arrow and Backspace row keys, Esc layering, `after` anchoring, `Keep as mine`, `No source` badge, left rule and screen-reader label, error and cancelled states (the study note lists these as unseen), live-region announcement, demo content.
