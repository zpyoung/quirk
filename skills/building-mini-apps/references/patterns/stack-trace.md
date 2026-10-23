# stack-trace

A list of collapsible frames that shows where a failure came from: your own frames open to a numbered source excerpt with the failing line highlighted, runs of library frames fold into one "Show N more frames" row that opens in place, and two controls switch between the most relevant and the full list and between newest-first and oldest-first. It was studied in Sentry.

## When to use

Use it when the user reads a chain of calls to find the one that matters, and most of the chain is noise:

- A test runner: why a test failed, with the assertion in your spec and the runner's own frames folded away.
- A log viewer or crash reporter for a small app: the crash with its call path and the code around the failing line.
- A build or script tool: where a script threw, through the helper modules it imported.
- A personal automation or notebook runner: which step failed and which of your cells called it.

Do not use it when:

- The entries are events over time with no call hierarchy (a parcel history, an audit log): use `event-timeline`.
- The rows are timed steps drawn against a shared axis (a build pipeline's durations): use `span-waterfall`.
- The detail is a short body under a row that has nothing to fold: use `expand-in-place`.
- The user compares many records and wants a side preview of one: use `list-peek`.
- The page around the trace (the issue header, tags, the right rail) is what you are building: use `inspector`. This pattern is one section inside such a page.

## Anatomy

```
+----------------------------------------------------------------+
| [Most relevant | Full]                      [Newest first  ^v]  |  toolbar ~40px
| There are 2 chained exceptions                                  |  note ~24px
+----------------------------------------------------------------+
| v TypeError  Cannot read properties of undefined (reading 'x') |  exception ~36px
|   +------------------------------------------------------------+
|   | src/cart/totals.ts  in applyCoupon at line 72:14  [In app] ^|  frame header ~32px
|   |   67 | const base = items.reduce(sum, 0)                    |
|   |   68 |                                                      |  excerpt lines ~19px,
|   |  ...                                                        |  11 lines
|   |   72 | total -= coupon.amount        <- tinted, marked      |
|   |  ...                                                        |
|   |   77 | return round(total)                                  |
|   +------------------------------------------------------------+
|   | src/cart/index.ts   in checkout at line 31:9      [In app] v|  collapsed ~32px
|   +------------------------------------------------------------+
|   |   Show 17 more frames                                    v  |  fold row ~30px
|   +------------------------------------------------------------+
| v AssertionError  expected 42 to equal 40                       |
|   ...                                                           |
+----------------------------------------------------------------+
```

- **Toolbar:** a two-way toggle (Most relevant, Full) on the left and the order control on the right. The note under it reads "There are N chained exceptions" and shows only when there is more than one exception.
- **Exception block:** a heading with a chevron, the exception type in bold and its message beside it, optional mechanism and handled text. The heading collapses the whole block.
- **Frame header:** the file path (truncates with an ellipsis when it has to), "in function at line N:col" in muted text, an "In app" badge on relevant frames, and a chevron on the right. A frame with no source shows no chevron.
- **Code excerpt:** a monospace block of about 11 lines with a line-number gutter. The failing line has a full-width tint, a bar on its left edge and the hidden text "failing line", so it never relies on color alone. Long lines wrap with a hanging indent.
- **Fold row:** one dimmed row per run of consecutive library frames, reading "Show N more frames". Pressing it inserts those frames in place as single-line rows, darker and shorter than a relevant frame, and the label becomes "Hide N more frames".
- **Library frame row:** one line with the module or file and the function, no badge. It opens to an excerpt only when it carries source.

## Interaction

Everything here is our design. No source shows a key for a stack trace (study note, Unseen: "keyboard shortcuts for event navigation, none stated"), and S13 shows only mouse use. Keys act when focus is on the page body or inside the block, and never while focus is in an input, textarea, select or contenteditable.

| Key | Does | Notes |
|-----|------|-------|
| ArrowDown | Moves focus to the next row | Rows are exception headings, frame headers and fold rows, in the order shown. Stops at the last row. From the page body, focuses the first row. |
| ArrowUp | Moves focus to the previous row | Stops at the first row. |
| Home / End | Moves focus to the first / last row | |
| Enter or Space | Toggles the focused row | A frame header opens or closes its excerpt, an exception heading opens or closes its block, a fold row shows or hides its frames. Native button activation, so one press toggles once. |
| Click (header) | Toggles that row | Same as Enter. |
| Click (Most relevant / Full) | Switches the view | Keeps every open frame and fold open. |
| Click (order control) | Flips newest-first and oldest-first | Reverses frames inside each exception. Exceptions keep the order they were given. |
| Tab | Moves between the toolbar and the list | The list is one stop: the last focused row, or the first. |

Focus rules:

- Roving focus: only one row is in the tab order at a time, and arrow keys move it. Focus stays on a row when it toggles.
- If the focused row disappears (a fold closes while focus is on one of its frames, or the view changes), the tab stop falls back to the first row.
- Expansion state is kept by frame id. Switching view or order, or new data with the same ids, never closes what the user opened.
- Frame headers, fold rows and exception headings are buttons with `aria-expanded`; frame headers and exception headings add `aria-controls` while open. The failing line carries hidden text, and each exception's frames are an ordered list labelled by its heading.

Defaults when nothing has been toggled:

- The failing frame of each exception is open: the last in-app frame in call order that has source. Every other frame is closed, and every fold is closed.
- The view starts at Most relevant and the order at newest-first, matching "most recent call first" in S1-t0223.png. Both can be set with `defaultView` and `defaultOrder`.

Folding rules (the pure module in `frames.ts`):

- Frames arrive in call order, caller first and the failing frame last. Newest-first reverses them for display.
- In Most relevant, a run of one or more consecutive library frames becomes one fold row. A fold keeps its place and its id whichever way the order points.
- In Full there are no fold rows and every frame shows as a row.
- If an exception has no in-app frame, Most relevant shows every frame and a muted line says so, so the list is never one fold row.

| State | Shows |
|-------|-------|
| Empty (no exceptions) | `EmptyState` "No stack trace" with a line saying the event has no frames. No toolbar. |
| Exception with no frames | The heading and a muted line "No frames recorded". |
| Loading | `LoadingState` "Loading stack trace" in place of the toolbar and list. |
| Error | `ErrorState` with the message and a Retry button when `onRetry` is given. |
| Frame without source | The header has no chevron and does not toggle; arrow keys still reach it. |
| Excerpt near the top or bottom of a file | The window shifts so it still shows up to 11 lines. |
| Very long path or message | The path and the message truncate with an ellipsis and carry a `title` with the full text. |
| Narrow block | The toolbar and each frame header wrap, so the function text drops under the path. A single token too long for the excerpt scrolls it sideways. |
| Many frames | The list grows with the page; the host decides whether it scrolls. Not virtualized, fine to a few hundred frames. |

## Borrow / Leave out

Borrow:

- Each frame is a collapsible row with the file path, "in function at line N:col" and a collapse control at the right (S1-t0223.png, S6-t0088.png, S13-issue-detail-stacktrace.png).
- Collapsed frame rows are short, about 28 to 32px, with a chevron at the right edge (S6-t0088.png).
- The open frame shows about 11 source lines with line numbers, and the failing line stands out as a full-width band (S1-t0223.png, S13-issue-detail-stacktrace.png, S9-img-issue-details-breakdown-MAZU5VNB.png).
- The failing frame is open and the other frames are collapsed (S9-img-issue-details-breakdown-MAZU5VNB.png, S13-issue-detail-frames-collapsed.png).
- A relevance badge on in-app frames (S7-t0004.png, S13-issue-detail-stacktrace.png).
- A Most relevant / Full toggle and a Newest / Oldest order control above the frames (S3-t0883.png, S13-issue-detail-stacktrace.png).
- Library frames fold into "Show N more frames", which inserts the frames in place as single-line rows and flips to "Hide N more frames", with no modal and the page growing instead (S13-issue-detail-frames-collapsed.png, S13-issue-detail-frames-expanded.png).
- A chained exception is a second block under the first, each with its own heading, chevron and message, under a note that says how many there are (S13-issue-detail-stacktrace.png).
- Long source lines wrap with a hanging indent (S13-issue-detail-stacktrace.png).

Leave out:

- Registers, local variables and their "Show More" fade (S6-t0088.png, S13-issue-detail-frames-collapsed.png): they need real runtime data.
- The "Open this line in" source-host link, the copy and code icon buttons on a frame header, "Copy as" and the overflow menu (S1-t0223.png, S9-img-issue-details-breakdown-MAZU5VNB.png, S13-issue-detail-stacktrace.png): they need a repository or a backend.
- The Raw view, the Original / Minified toggle and the minified-source banner (S1-t0223.png): they need source maps.
- The thread selector and thread tags (S13-issue-detail-stacktrace.png): one list per exception is enough here.
- The "Called from" footer line (S1-t0223.png, S13-issue-detail-frames-collapsed.png): the next row in the list already is the caller.
- The Event Grouping Information tree (S9-img-issue-details-breakdown-MAZU5VNB.png): it explains a fingerprint, which is not part of reading a trace.
- Syntax colouring: colour comes only from theme tokens.
- Sentry's purple, its brand look and its copy.

## Block API

Files in `gallery/src/patterns/stack-trace/`: `registry-item.json`, `index.ts`, `types.ts`, `frames.ts`, `code-excerpt.tsx`, `stack-trace.tsx`, `demo.tsx`.

```
CONTRACT: type SourceLine = { no: number; text: string }

CONTRACT: type StackFrame = {
  id: string                       // unique within its exception
  filename: string                 // shown as the path; also the title
  function?: string
  module?: string                  // shown instead of the path for frames with no file
  lineNo?: number                  // the failing line; highlighted when it is in contextLines
  colNo?: number
  inApp: boolean                   // relevant: opens to source and survives Most relevant
  contextLines?: SourceLine[]      // source around lineNo; the block shows a window of about 11
}

CONTRACT: type StackException = {
  id: string
  type: string
  value?: string
  mechanism?: string               // shown as small text after the message
  handled?: boolean
  frames: StackFrame[]             // call order: caller first, failing frame last
}

CONTRACT: type FrameView = "relevant" | "full"
CONTRACT: type FrameOrder = "newest" | "oldest"

CONTRACT: StackTrace(props: StackTraceProps): JSX.Element

CONTRACT: type StackTraceProps = {
  exceptions: StackException[]
  status?: "loading" | "ready" | "error"          // default "ready"; pass useCollection's status
  error?: Error
  onRetry?: () => void
  defaultView?: FrameView                          // default "relevant"
  defaultOrder?: FrameOrder                        // default "newest"
  onViewChange?: (view: FrameView) => void
  onOrderChange?: (order: FrameOrder) => void
  emptyTitle?: string
  "aria-label"?: string
}
```

`frames.ts` is plain TypeScript with no React: `orderFrames`, `foldFrames` (returns the rows to draw for one exception from its frames, the view, the order and the set of open folds), `effectiveView` (the view after the no-in-app fallback), `excerptWindow` (the lines to show around the failing line, 11 by default), `defaultOpenFrameId` and `isExpandable`.

`index.ts` exports `StackTrace` and the types `StackTraceProps`, `StackException`, `StackFrame`, `SourceLine`, `FrameView` and `FrameOrder`. `demo.tsx` default-exports `Demo`.

Uses from the base:

- `useCollection` in the demo only; `StackTrace` takes `exceptions` and `status` as props and does not read the store.
- `EmptyState`, `LoadingState`, `ErrorState` from `src/components/mini/states.tsx`.
- `useHotkeys` from `react-hotkeys-hook` for the arrow, Home and End keys.
- shadcn components, all pre-installed: `button`, `badge` and `toggle-group`. No new dependencies.
- The code excerpt (line-number gutter and failing-line band) is built inside the block, in `code-excerpt.tsx`.

`demo.tsx` renders neither `AppShell` nor a toaster. It shows failed tests from a small shopping-cart project, stored with `useCollection("stack-trace-demo", seed)`: each record has an `id`, a test `name`, a `summary` and its `exceptions`. A button group above the trace picks one failure. The first has two chained exceptions: the first with a failing in-app frame, a library run of 17 frames, a run of 3 and an in-app frame with no source, the second with runs of 4 and 2; the second is a single exception whose failing frame is inside a library, with one in-app caller; the third has frames and no in-app frame, to show the fallback. Names, paths and code are invented. A plain-text footer lists the key hints. A "State preview (demo only)" button group (live, empty, loading, error) forces each state, and Retry in the error state returns to live.

## Sources

[sentry study note](../apps/sentry.md). The keyboard model, the roving focus, the fallback when no frame is in-app, the open and closed defaults beyond the failing frame, and everything else marked "our design" are not from a source.

- **Collapsible frame rows with path, function and line:column, and a collapse control:** `S1-t0223.png`, `S6-t0088.png`, `S13-issue-detail-stacktrace.png`.
- **Short collapsed rows with a chevron at the right:** `S6-t0088.png`, `S9-img-issue-details-breakdown-MAZU5VNB.png`.
- **About 11 numbered source lines, failing line as a full-width band:** `S1-t0223.png`, `S13-issue-detail-stacktrace.png`, `S9-img-issue-details-breakdown-MAZU5VNB.png`. The hidden "failing line" text and the left bar, so the mark never relies on color, are our design.
- **Failing frame open, the rest collapsed:** `S9-img-issue-details-breakdown-MAZU5VNB.png`, `S13-issue-detail-frames-collapsed.png`.
- **In-app badge:** `S7-t0004.png`, `S13-issue-detail-stacktrace.png`.
- **Most relevant / Full toggle and the order control:** `S3-t0883.png`, `S7-t0004.png`, `S13-issue-detail-stacktrace.png` (Newest / Oldest). "Most recent call first" as the default: `S1-t0223.png`.
- **Fold of library frames, in-place expansion, label flip:** `S13-issue-detail-frames-collapsed.png`, `S13-issue-detail-frames-expanded.png`.
- **Chained exceptions with a count note and a heading and chevron per exception:** `S13-issue-detail-stacktrace.png`. The order control reversing frames only, not exceptions, is our design.
- **Hanging indent on long source lines:** `S13-issue-detail-stacktrace.png`.
- **Unseen in the study note:** an empty or loading state for the section (Unseen under S13) and the frame-expanded state for an in-app frame's chevron (Unseen under S13). `S1-t0076.png` shows a blank page while loading, no skeleton; ours uses the base `LoadingState`.
- **Our design:** every key and the roving focus, folding a run of one frame, the no-in-app fallback, expansion kept by frame id, the exception heading collapsing its block, the window shift near file edges, and the demo's data and failure picker.
