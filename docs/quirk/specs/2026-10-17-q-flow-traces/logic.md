# Logic spec: stepping through a value in `q-flow`

**Status**: Approved

A `q-flow` graph shows what connects to what, but not what happens to the data on the way. A reader
can see that a renewal order goes from Pricing to Tax to Charge worker. They can't see that Pricing
adds a discount, Tax raises the total, and a declined card puts a retry time on the order that the
second attempt then clears. Pages that explain a flow end up pasting the order as JSON several
times in a row and leave the reader to spot the differences.

This spec adds **traces** to `q-flow`. A trace is a walk through the graph, one step per node, with
the full value as it leaves each node. The reader steps through it in a panel beside the canvas and
sees what was added, changed and removed at every step.

It is the second of four specs. It extends the element in
[the q-flow logic spec](../2026-10-16-q-flow/logic.md) and builds on
[the q-flow shapes logic spec](../2026-10-17-q-flow-shapes/logic.md), whose loop edges and decisions
a trace can walk through. Everything those specs say still holds unless this one changes it. The
interactive sequence element in spec 3 will reuse the trace format, with one step per message.

## Conceptual model

The graph gains one thing, the trace, and edges gain an optional id:

| Thing | What it is | What the agent gives it |
|---|---|---|
| trace | a named walk through the graph showing one value changing | an id, a label and at least two steps |
| step | one stop on a trace, at one node | the node, the value as it leaves that node, optionally a note and the edge it came in on |
| edge id | a name for an edge, so a step can pick it | optionally `id` on any edge |

- **Step.** A step points at a node. Its **value** is the whole value as it leaves that node, as any
  JSON value. Its **note** is one short sentence saying what happened there, such as "Pricing applies
  the loyalty discount".
- **Incoming edge.** Every step after the first arrives along one edge from the previous step's node
  to its own. When exactly one edge runs between them, the element uses it. When several do, the step
  names one with `via`, the edge's id. Edges run in the direction they are drawn, and a loop edge
  counts in its true direction, so a retry trace can go around a loop.
- **Changes.** The element works out each step's **changes** by comparing its value with the previous
  step's: fields added, fields changed and fields removed. Agents write whole values, never patches.
- **Trace mode.** The reader opens it with a "Step through" button. While it is open, the canvas
  shows the trace instead of a focused path, and the **trace panel** shows the current step.

A graph can carry several traces, for example "Card succeeds" and "Card declined, retried". The
reader picks one in the panel.

## Data flow

1. **Choosing.** The agent adds a trace when the reader needs to see what happens to a value as it
   moves through the flow: how an order is priced, how an event payload is enriched, what a retry
   changes. It leaves traces out when the page is only about structure.
2. **Authoring.** In the graph's JSON the agent writes a `traces` list, one entry per scenario worth
   walking, with the full value at each step. It gives an edge an id only when a step needs to pick it
   from several parallel edges.
3. **Building.** The kit check checks every trace against the graph (SC-2). The no-script fallback
   lists each trace's steps.
4. **Loading.** The element checks the traces the same way, adds "Step through" to the toolbar when
   the graph has a trace, and writes each trace into the text list. Nothing moves.
5. **Reading.** The reader opens trace mode, picks a trace, and steps with Back and Next, the step
   dots, the arrow keys, Play, or a click on a node. The canvas follows the current step and the panel
   shows its note and value with the changes marked.
6. **Verifying.** Verify screenshots an example page with two traces at 375px and 1280px in both
   themes.

## Key decisions and rationale

- **Steps point at nodes, and the value is what leaves the node.** A node is where data changes, so
  one step per node gives one before-and-after per change. Pointing steps at edges would double the
  steps and put the value in transit, where nothing happens to it.
- **The agent writes whole values; the element works out the changes.** Agents write patches badly,
  and a hand-written patch can disagree with the values around it. A whole value at each step is easy
  to write and to check, and the text list can show it as it is.
- **A trace must walk the graph as drawn.** Every consecutive pair of steps needs an edge, or the
  check fails. A trace that skips an edge would teach the reader a path the graph doesn't have.
  Inferring the edge when there's only one keeps `via` rare.
- **A panel beside the canvas, not the drawer.** The value and its changes need room, and the reader
  has to see the canvas and the value together. The panel moves below the canvas at 700px and
  narrower, where there's no room beside it.
- **Only the current edge pulses.** Pulsing the whole trace would show every hop at once and lose the
  step. While a step is shown, its incoming edge pulses as a focused path's edges do, including a loop
  edge. Spec 1 keeps pulses off loop edges in focus mode because a pulse there would circle the cycle
  for as long as the node stays focused. In trace mode the reader chose that hop, so the pulse covers
  one edge only.
- **Marks use a symbol and a color.** Added, changed and removed fields carry `+`, `old → new` and a
  strike-through as well as a color, so the changes read without color vision and in print.
- **Play pauses and never starts itself.** Play is the one thing on the page that moves without a
  click, so it has a pause control (WCAG 2.2.2), stops at the last step, and never runs at load.

## Behavior and scenarios

The scenarios share one renewal graph unless they say otherwise. Nodes: Renewal scheduler, Pricing,
Tax, Charge worker, Paid? (a decision), Retry queue and Settlement. Edges: Renewal scheduler to
Pricing; two edges from Pricing to Tax, "domestic quote" with id "tax-domestic" and "cross-border
quote" with id "tax-intl"; Tax to Charge worker; Charge worker to Paid?; Paid? to Settlement "Yes";
Paid? to Retry queue "No"; and Retry queue to Charge worker "retry up to 3x" with id "retry", marked
loop.

It carries two traces:

- **"Card succeeds"**: Renewal scheduler, Pricing, Tax (via tax-domestic), Charge worker, Paid?,
  Settlement. 6 steps.
- **"Card declined, retried"**: Renewal scheduler, Pricing, Tax (via tax-domestic), Charge worker,
  Paid?, Retry queue, Charge worker, Paid?, Settlement. 9 steps. Its values are in SC-5.

### Authoring and building

1. **SC-1**
   - **Given** an agent writing an explainer page about how a renewal order is charged
   - **When** it writes the renewal graph with its two traces and builds the page
   - **Then** the kit check passes, the toolbar has a "Step through" button, and "Graph as a list"
     carries both traces; a graph with no traces has no "Step through" button
   - **Data before:** **Source**: the renewal graph; `traces` with "Card succeeds" (6 steps) and "Card
     declined, retried" (9 steps); the two Tax steps name via "tax-domestic"; every other step leaves
     its edge to be inferred
   - **Walkthrough:**
     1. The kit check finds an edge for every pair of consecutive steps: one edge each, except Pricing
        to Tax, where "tax-domestic" picks one of two
     2. In the browser the element repeats the check, adds "Step through" and writes both traces into
        the text list
   - **Data after:** **Built page**: ✓ kit check passed; **Graph on screen**: ✓ "Step through" in the
     toolbar; ✓ nothing moving; **Text list**: ✓ both traces, every step

2. **SC-2**
   - **Given** a graph whose traces break the contract
   - **When** the page is built
   - **Then** the kit check fails or warns, names the element, the trace and the step, and the JS
     element reports the same failures when it parses the data, for each case in the table
   - **Kit check results:**

     | Trace data | Result |
     |---|---|
     | a step at node "ledgr", which no node has | ✗ fails: trace "declined" step 3 points at unknown node "ledgr" |
     | a step with via "tax-eu", which no edge has | ✗ fails: trace "declined" step 3 names unknown edge "tax-eu" |
     | a Tax step with via naming the Retry queue to Charge worker edge | ✗ fails: edge "retry" doesn't run from Pricing to Tax |
     | a step at Settlement straight after Pricing | ✗ fails: no edge from Pricing to Settlement |
     | a step at Tax after Pricing with no via | ✗ fails: 2 edges run from Pricing to Tax; name one with via |
     | two traces with the id "declined" | ✗ fails: duplicate trace id "declined" |
     | two edges with the id "tax-domestic" | ✗ fails: duplicate edge id "tax-domestic" |
     | a trace with one step | ✗ fails: trace "declined" needs at least 2 steps |
     | a value that can't be written as JSON | ✗ fails: trace "declined" step 4 has a value that isn't JSON |
     | a value of 450 lines once pretty-printed | ✗ fails: trace "declined" step 4's value is over 400 lines |
     | a value of 60 lines once pretty-printed | ✓ passes with a warning: values over about 40 lines are hard to scan; trim fields the reader doesn't need |
     | a note of 150 characters | ✓ passes with a warning: notes over about 120 characters crowd the panel |
     | a trace with 35 steps | ✓ passes with a warning: traces over about 30 steps are hard to follow; split them |

   - A trace needs an id and a label, and a step needs a node and a value. The JS element can't
     receive a value that isn't JSON, because the graph data is JSON, so only the Python check can
     hit that case.

### Opening trace mode

3. **SC-3**
   - **Given** the renewal graph on a 1280px page, with Pricing focused and its drawer open
   - **When** the reader presses "Step through"
   - **Then** focus clears and the drawer closes, the trace panel docks beside the canvas on the first
     trace, and the canvas shows step 1: Renewal scheduler lit, every node and edge off the trace's path
     dimmed, no edge lit or pulsing, and the value shown with no change marks
   - **Data before:** **Graph**: Pricing focused; drawer open
   - **Walkthrough:**
     1. The reader presses "Step through"
     2. The element clears focus, closes the drawer and opens the panel on "Card succeeds", the first
        trace listed
     3. It lights Renewal scheduler and dims Retry queue, the "No" edge, the loop edge and the
        "cross-border quote" edge, because "Card succeeds" never touches them
   - **Data after:** **Graph**: ✓ Renewal scheduler lit as the current node; ✓ the rest of the trace's
     path at full color; ✓ Retry queue and the three edges above dimmed; ✓ nothing pulsing;
     **Panel**: ✓ open beside the canvas; ✓ picker on "Card succeeds"; ✓ "Step 1 of 6"; ✓ value with no
     marks, because step 1 has nothing to compare against
   - **Panel contents:**

     | Part | Shown |
     |---|---|
     | trace picker | ✓ "Card succeeds", "Card declined, retried" |
     | step counter | ✓ "Step 1 of 6", in a live region |
     | Back, Next, Play | ✓ Back disabled on step 1 |
     | step dots | ✓ one per step, each clickable, the current one marked |
     | note | ✓ the step's note, or nothing if it has none |
     | "Changes only" toggle | ✓ off |
     | value | ✓ an indented tree |

   - The trace's path is every node and edge any of its steps lands on or arrives by.

### Stepping

4. **SC-4**
   - **Given** "Card succeeds" open at step 2, Pricing
   - **When** the reader presses Next
   - **Then** Tax becomes the current node, the "domestic quote" edge lights and pulses because the step
     names via "tax-domestic", the "cross-border quote" edge stays dimmed, and the value shows the tax
     added and the total changed
   - **Data before:** **Step 2, Pricing**: value { order "R-1042"*, status "queued", subtotal 36.00,
     discount { code "LOYALTY10", amount 3.60 }, total 32.40 }
   - **Walkthrough:**
     1. The reader presses Next
     2. Two edges run from Pricing to Tax, so the element uses the one the step names, "tax-domestic"
     3. It compares step 3's value with step 2's: tax is new, total changed
   - **Data after:** **Step 3, Tax**: ✓ value { order "R-1042", status "queued", subtotal 36.00,
     discount { code "LOYALTY10", amount 3.60 }, tax 2.67, total 35.07 }; ✓ tax marked `+`; ✓ total
     shown as 32.40 → 35.07; **Graph**: ✓ Tax current; ✓ "domestic quote" lit and pulsing; ✓ "cross-border
     quote" dimmed; ✓ Pricing no longer current but still on the path

5. **SC-5**
   - **Given** "Card declined, retried" open at step 1
   - **When** the reader presses Next eight times
   - **Then** each step shows the changes in the table, step 7 arrives at Charge worker along the loop
     edge "retry up to 3x", and that edge lights and pulses as the current edge, drawn as a return line
   - **Data before:** **Step 1, Renewal scheduler**: value { order "R-1042"*, status "queued", lines
     [ { item "Coffee beans", qty 2, price 18.00 } ] }
   - **Walkthrough:**
     1. Step 2, Pricing: note "Pricing applies the loyalty discount"
     2. Step 3, Tax, via tax-domestic: note "Tax adds 8.25% sales tax"
     3. Step 4, Charge worker: note "The card is declined"
     4. Step 5, Paid?: note "Paid? answers No"
     5. Step 6, Retry queue: note "The retry is booked for tomorrow"
     6. Step 7, Charge worker, along the loop edge: note "The second attempt succeeds"
     7. Step 8, Paid?: note "Paid? answers Yes"
     8. Step 9, Settlement: note "The order settles"
   - **Data after:** **Step 9, Settlement**: ✓ value { order "R-1042", status "settled", lines [ … ],
     subtotal 36.00, discount { … }, tax 2.67, total 35.07, attempt 2, charge "ch_88"*, settled_at
     "2026-10-18T09:02Z"* }; **Graph**: ✓ Retry queue and the loop edge on the path, so not dimmed;
     ✓ "cross-border quote" dimmed
   - **Changes at each step:**

     | Step | Node | Changes shown |
     |---|---|---|
     | 1 | Renewal scheduler | none, the first step |
     | 2 | Pricing | `+` subtotal 36.00; `+` discount { code "LOYALTY10", amount 3.60 }; `+` total 32.40 |
     | 3 | Tax | `+` tax 2.67; total 32.40 → 35.07 |
     | 4 | Charge worker | status "queued" → "declined"; `+` attempt 1; `+` decline "insufficient_funds" |
     | 5 | Paid? | none; the value passes through unchanged |
     | 6 | Retry queue | status "declined" → "retry_scheduled"; `+` retry_at "2026-10-18T09:00Z"* |
     | 7 | Charge worker | status "retry_scheduled" → "paid"; attempt 1 → 2; `+` charge "ch_88"*; decline struck through; retry_at struck through |
     | 8 | Paid? | none |
     | 9 | Settlement | status "paid" → "settled"; `+` settled_at "2026-10-18T09:02Z"* |

   - Step 5's value is identical to step 4's. The panel shows it with no marks, which tells the reader
     the decision only routes the order.

6. **SC-6**
   - **Given** "Card declined, retried" at step 7, where decline and retry_at show struck through
   - **When** the reader presses Next
   - **Then** decline and retry_at are gone from step 8's value; a removed field shows struck through on
     the step that removed it only
   - **Value panel states:**

     | Mark | Symbol | Shown on |
     |---|---|---|
     | added | `+` before the field, in the success color | the step that adds it |
     | changed | `old → new`, the new value in the accent color | the step that changes it |
     | removed | the field and its old value struck through, in a muted color | the step that removes it, then gone |
     | unchanged | no mark | every step |

   - Fields are matched by name inside objects and by position inside lists. A value whose type changes,
     such as a string becoming an object, shows as changed.

7. **SC-7**
   - **Given** "Card declined, retried" at step 7
   - **When** the reader turns on "Changes only"
   - **Then** the value shows status, attempt, charge, decline and retry_at with their marks, and hides
     every unchanged field; the toggle stays on as the reader steps and
     when they switch traces
   - A changed field deep in the value keeps the objects that hold it, so it stays in place. On a step
     with no changes, such as step 8, "Changes only" shows "No changes at this step".

8. **SC-8**
   - **Given** a step whose value nests deeper than 3 levels, for example customer, address, geo,
     coordinates
   - **When** the step is shown
   - **Then** every branch below the third level starts collapsed with a count of the fields inside,
     and the reader can open it; a collapsed branch that holds a change at this step opens so the
     change is visible

9. **SC-9**
   - **Given** "Card declined, retried" at step 2
   - **When** the reader clicks Charge worker on the canvas, then clicks it again
   - **Then** the first click jumps to step 4 and the second to step 7: a click on a node on the trace
     jumps to that node's next visit after the current step, or its first visit if none follows
   - Clicking a step dot jumps to that step. Jumping shows the changes against the step before the one
     shown, not against the step the reader left.

10. **SC-10**
    - **Given** "Card declined, retried" open at step 4
    - **When** the reader picks "Card succeeds" in the picker
    - **Then** the panel shows "Card succeeds" at step 1, the canvas dims to that trace's path, and
      Retry queue and the loop edge dim

### Play

11. **SC-11**
    - **Given** "Card succeeds" at step 1, the reader not asking for reduced motion
    - **When** the reader presses Play
    - **Then** the trace advances about every 1.5 seconds, Play becomes Pause, and at step 6 it stops
      and Pause turns back into Play
    - **Data before:** **Panel**: "Step 1 of 6"; Play shown
    - **Walkthrough:**
      1. The reader presses Play; the button becomes Pause
      2. Steps 2 to 6 follow about 1.5 seconds apart, each lighting and pulsing its incoming edge
      3. At step 6 Play stops
    - **Data after:** **Panel**: ✓ "Step 6 of 6"; ✓ Play shown again; ✓ Next disabled
    - Pressing Pause, Back, Next, a dot, a node or the picker stops Play. Pressing Play on the last step
      starts again from step 1. Play never starts on its own.

### Keyboard, motion and screen readers

12. **SC-12**
    - **Given** trace mode open, keyboard focus in the panel
    - **When** the reader uses the keys in the table
    - **Then** each key does what the table says, and each new step is announced in the live region,
      for example "Step 4 of 9, Charge worker: The card is declined"
    - **Keyboard:**

      | Key | Result |
      |---|---|
      | Right arrow, Down arrow | ✓ next step |
      | Left arrow, Up arrow | ✓ previous step |
      | Tab | ✓ moves through the panel's controls |
      | Escape | ✓ leaves trace mode; keyboard focus returns to "Step through" |

    - The arrow keys step only while focus is in the panel. While focus is in the picker they work the
      picker as usual. On the canvas the arrow keys keep moving between nodes, as before.

13. **SC-13**
    - **Given** the reader has reduced motion turned on
    - **When** they step through "Card declined, retried", by hand or with Play
    - **Then** every step changes as usual, but nothing animates: the current edge is the thicker static
      line with arrowheads from the q-flow spec, with no pulse, and the canvas jumps instead of easing
      when it pans

14. **SC-14**
    - **Given** the canvas zoomed in on Renewal scheduler and Pricing
    - **When** the reader steps to Settlement, which is out of view
    - **Then** the canvas pans, keeping the zoom, until Settlement is in view; it doesn't move when the
      current node is already in view

### Leaving trace mode

15. **SC-15**
    - **Given** trace mode open at any step
    - **When** the reader presses Escape, presses "Step through" again, or clicks a node off the trace,
      such as Retry queue during "Card succeeds"
    - **Then** the panel closes, the graph returns to rest with everything at full color and nothing
      pulsing, and a click on a node off the trace also focuses that node as a click always does
    - Clicking empty canvas doesn't leave trace mode, so a reader who pans by dragging stays in it.

16. **SC-16**
    - **Given** a graph with traces, trace mode closed
    - **When** the reader clicks, tabs to and focuses nodes, or the page sits at rest
    - **Then** focus, the drawer and the pulse behave exactly as in the q-flow and shapes specs, and
      nothing moves at rest

### Phones and expand

17. **SC-17**
    - **Given** the renewal graph on a 375px phone
    - **When** the reader opens trace mode
    - **Then** the trace panel sits below the canvas, full width, instead of beside it; the canvas keeps
      its height and the canvas and panel scroll with the page
    - The panel moves below the canvas at 700px and narrower. In expand, the panel docks beside the
      canvas inside the full-screen view, or below it at 700px and narrower, and trace mode carries over
      between the page and expand.

### Text list and no-script fallback

18. **SC-18**
    - **Given** the renewal graph
    - **When** the reader opens "Graph as a list", or the page loads with scripts off
    - **Then** after the nodes and edges, the list has one section per trace: its label, then its steps
      in order, each with the node, the note and the value as a pretty-printed code block, and the
      no-script fallback the build writes carries the same steps
    - **List entries:**

      | Trace | Step | Entry |
      |---|---|---|
      | Card declined, retried | 3 | 3. Tax, via "domestic quote": Tax adds 8.25% sales tax, then the value as a code block |
      | Card declined, retried | 7 | 7. Charge worker, via "retry up to 3x": The second attempt succeeds, then the value |
      | Card succeeds | 5 | 5. Paid?: Paid? answers Yes, then the value |

    - A step names its incoming edge only when it came in by `via` or along a loop edge; other edges
      are plain from the steps before and after.

### Choosing

19. **SC-19**
    - **Given** an agent asked for "an HTML page that walks through how a renewal order changes as it's
      priced, taxed and charged, including a declined card"
    - **When** it writes the page
    - **Then** it writes a `q-flow` of the renewal flow with a trace for the happy path and one for the
      decline and retry, each value holding only the fields the reader needs; asked only for "a diagram
      of our renewal services", it writes no trace

## Scope and non-goals

In scope:

- the `traces` field, edge ids, `via`, and edge inference
- the kit check rules in SC-2, in both the Python check and the JS element
- the "Step through" button, trace mode and the trace panel: picker, counter, Back, Next, dots, Play,
  note, "Changes only" and the value tree with change marks
- canvas behavior in trace mode: the current node and edge, dimming off the path, the single-edge
  pulse, panning to the current node, clicks on nodes
- keyboard, the live region, reduced motion, the phone layout and expand
- the text list and the no-script fallback
- the skill's text on when to add a trace, in SKILL.md and the design reference; the generated
  components reference; "walk through how the order changes" prompts in the evals
- an example page with the renewal graph and its two traces

Not in scope:

- steps that point at an edge rather than a node
- values shown as tables
- values the reader can edit
- Play starting on its own at load
- traces in the sequence element, which spec 3 adds using this format

## Success criteria

- An eval of "walk through how X changes" prompts shows the agent adding a trace with the right
  values, and no trace for prompts that only ask for structure.
- Verify screenshots of the example at 375px and 1280px in both themes show the panel beside the
  canvas on desktop and below it on the phone, with added, changed and removed marks legible in both
  themes.

## Decisions Locked

Data:

- Traces live in an optional `traces` list in the existing q-flow JSON. Each trace has an id, a label
  and steps; each step has a node, a value, and optionally `via` and a note.
- Edges gain an optional `id`, used only by `via`.
- A step points at a node. Its value is the full data as it leaves that node, as any JSON value. Its
  note is a short sentence saying what happened.
- The element works out what was added, changed and removed against the previous step. Agents never
  write patches.
- A graph can carry several traces, and the reader picks one in a picker.

Edges between steps:

- When exactly one edge joins the previous step's node to this one, it is used automatically.
- When several do, the step must name one with `via`.
- When none does, the kit check fails, so a trace always walks the graph as drawn.
- A node may be visited again, for example around a loop edge.

Reading:

- A "Step through" toolbar button opens trace mode. It docks a trace panel beside the canvas, below it
  at 700px and narrower. The panel holds the trace picker, the step counter, Back and Next, clickable
  step dots, Play, the note and the value. Escape, or a click on a node off the trace, leaves trace
  mode.
- The canvas lights the current node and the edge it came in on, dims everything off the trace's path,
  and pulses only the current edge. Clicking a node on the trace jumps to its step. If the current node
  leaves the view, the canvas pans to it.
- The value is an indented tree. Added fields are marked `+`, changed fields show `old → new`, removed
  fields appear struck through for one step. Marks use a symbol and a color, never color alone. A
  "Changes only" toggle hides unchanged fields. Nesting deeper than 3 levels starts collapsed.
- Arrow keys step while the panel has focus. Play advances about every 1.5 seconds and stops at the
  last step. The step counter is announced in a live region.
- With reduced motion, Play still steps but nothing animates: no pulse, no animated pan.
- The graph stays calm at rest, and focus works exactly as before outside trace mode.

Text list and check:

- Each trace appears in "Graph as a list" as an ordered list of steps: node, note, and the value as a
  code block. The no-script fallback carries the same.
- The JS element and the Python check stay in step. They fail on an unknown node, an unknown `via`, a
  `via` naming an edge that doesn't join the two steps, no edge between consecutive steps, several
  edges with no `via`, a duplicate trace id, a trace with fewer than 2 steps, and a value that isn't
  JSON or runs over 400 pretty-printed lines. They warn on a value over about 40 lines, a note over
  about 120 characters, and a trace over about 30 steps.

Choices this spec makes within those decisions, for review:

- Opening trace mode clears focus and closes the drawer (SC-3).
- A loop edge pulses when it is the current edge (Key decisions).
- A click on a revisited node jumps to its next visit (SC-9); a click on a node off the trace also
  focuses it (SC-15); a click on empty canvas stays in trace mode (SC-15).
- "Changes only" persists across steps and traces (SC-7); a collapsed branch holding a change opens
  (SC-8).
- Play on the last step starts from step 1 (SC-11).
- Duplicate edge ids fail the check (SC-2), since `via` must name one edge.

## Industry Insights

From research during the brainstorm, with source pages checked 2026-10-17.

- **No diagram tool found shows a payload changing at each step.** The closest each do part of it:
  - The Transformer Explainer steps through a model and shows the data at each stage, moving between
    the overview and the detail
    ([Transformer Explainer](https://poloclub.github.io/transformer-explainer/),
    [AAAI 2025 paper](https://ojs.aaai.org/index.php/AAAI/article/view/35347)).
  - JointJS's animated process flow animates the flow from a clicked node through its descendants,
    with no data attached
    ([JointJS demo](https://www.jointjs.com/demos/animated-process-flow-diagram)).
  - PipelineViz came up in the brainstorm research as a pipeline viewer; no source page was found for
    it in this pass. Pipelex's execution graph is a close relative: clicking a node shows the data at
    that stage, without the changes
    ([Pipelex execution graph](https://docs.pipelex.com/latest/features/execution-graph/)).
- **A stepper that advances on its own needs a pause control.** Anything that moves for more than
  five seconds alongside other content needs a way to pause or stop it
  ([WCAG 2.2.2 Pause, Stop, Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html)).
- **Motion triggered by interaction must respect reduced motion**
  ([WCAG 2.3.3 Animation from Interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html)).

## Deferred Ideas

Left out of this spec during the brainstorm:

- steps that point at an edge, to show a value in transit
- values shown as tables
- values the reader can edit
- Play starting on its own at load
- traces in the sequence element, which spec 3 adds using this format

Build-only questions for the tech spec:

- `[tech-spec]` The diff: how objects, lists and type changes are compared, and how the tree marks
  them.
- `[tech-spec]` How trace mode reuses the focus and dim attributes, and how the pulse is limited to
  one edge.
- `[tech-spec]` The panel's layout beside and below the canvas, and inside expand.
- `[tech-spec]` How the canvas decides the current node has left the view, and how it pans.
- `[tech-spec]` How Play is timed so the browser tests can drive it on a fake clock.
- `[tech-spec]` How the Python check measures pretty-printed lines the same way the JS element does.

## Glossary

- **trace**: a named walk through a graph showing one value changing, one step per node.
- **step**: one stop on a trace, at one node, with the value as it leaves that node.
- **value**: the whole data at a step, as any JSON value.
- **note**: a short sentence on a step saying what happened there.
- **incoming edge**: the edge a step arrives along from the previous step's node.
- **via**: a step's choice of incoming edge, by edge id, when several edges could carry it.
- **changes**: what was added, changed and removed between a step's value and the previous step's.
- **trace mode**: the state where the canvas shows a trace and the trace panel is open.
- **trace panel**: the panel beside or below the canvas that shows the current step.
- **trace's path**: every node and edge a trace's steps land on or arrive by.

## Status & amendments

**Status**: Approved

**Amendments:** none yet.
