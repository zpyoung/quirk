# Logic spec: `q-sequence`, an interactive sequence diagram element

**Status**: Approved

Agents draw sequence diagrams in Mermaid today. Mermaid gives a static picture: the reader can't open
a message to see what it carries, can't pick out one participant's part in a long exchange, and can't
step through the calls one at a time with the payload in view. Wide diagrams shrink to fit the page,
so on a phone the labels are too small to read.

`q-sequence` is a kit element for those pages. It draws participants as columns and messages as rows,
works out the activation bars itself, and lets the reader focus a participant, open a message, and
step through a trace with the payload at each message. Mermaid stays for diagrams inside Markdown.

It is the third of four specs. It follows the element contract in
[the q-flow logic spec](../2026-10-16-q-flow/logic.md) and reuses the trace format and trace panel
from [the q-flow traces logic spec](../2026-10-17-q-flow-traces/logic.md), with one step per message
instead of one per node. Everything those specs say about kinds, details, the trace panel and
reduced motion holds here unless this spec changes it.

## Conceptual model

A **sequence** has five kinds of thing, all written by the agent as data:

| Thing | What it is | What the agent gives it |
|---|---|---|
| participant | a person, service, worker, queue or store that sends and receives messages | an id and a label; optionally a kind and a detail |
| message | one call, reply or async message from one participant to another, or to itself | the two participants, a label and a type; optionally an id, a detail, and whether it creates its receiver |
| note | a short remark drawn over one or more participants | the text and the participants it sits over |
| fragment | a labeled box around a run of steps: `alt`, `opt`, `loop` or `par` | the fragment type, an optional label, and its steps or branches |
| kind | a category of participant with one chart color | a free-text name and one of the eight chart colors, as in q-flow |

The steps are one ordered list, top to bottom. A step is a message, a note, a fragment, or the end of
a participant. `alt` and `par` fragments hold two or more **branches**, each with a label and its own
steps; `opt` and `loop` hold one run of steps.

The agent never writes a position or an activation. Participants are columns in the order they are
listed, and every step is a row. The element works out the **activation bars** from the call and
reply pairs, and numbers the messages in the order they are drawn.

The reader explores the sequence through **focus**. Focusing a participant lights its lifeline and
every message that touches it, and dims the rest. Opening a message lights it and opens the
**drawer** with its detail. With traces, **trace mode** steps through the messages one at a time,
with spec 2's trace panel showing the payload and what changed.

Every sequence also renders as a **text list**: the participants, the numbered messages, the
fragments as nested lists, the notes, and the traces, in a "Diagram as a list" disclosure under the
diagram. It is the screen-reader and no-script view, so it carries everything the diagram does.

## Data flow

1. **Choosing.** The agent reaches for `q-sequence` for a sequence diagram on an HTML page: who calls
   whom, in what order, and what comes back. It reaches for `q-flow` for a graph of what connects to
   what, and for Mermaid for any diagram inside Markdown.
2. **Authoring.** The agent writes a `<q-sequence>` tag with a one-sentence `summary` and the
   sequence as JSON inside it: `kinds`, `participants`, `steps`, and optionally `traces`.
3. **Building.** The build runs the kit check over the sequence data (SC-2) and writes the no-script
   fallback list. The sequence renderer is part of the kit, so the build inlines no graph library for
   it; a page with only `q-sequence` carries no flow bundle (SC-20).
4. **Loading.** In the browser the element checks the data the same way, measures its labels, draws
   the columns and rows, and writes the text list from the same data. Nothing moves.
5. **Reading.** The reader scrolls the diagram with the page, scrolls it sideways when it is wider
   than the screen, focuses participants, opens messages, and steps through traces. The theme toggle
   recolors the diagram live.
6. **Verifying.** Verify waits until every sequence on the page has drawn, then takes its screenshots
   at 375px and 1280px in both themes.

## Key decisions and rationale

- **Its own element and its own SVG renderer, with no layout engine.** A sequence diagram is columns
  and rows: the column is fixed by the participant's place in the list, and the row by the step's
  place in the order. There is nothing for ELK to solve, and reusing `q-flow` would pull its 1.6 MB
  bundle onto every page with a sequence. A separate element also keeps the data honest: a sequence
  has order and replies, which a graph doesn't.
- **The type of a message is a field, not an arrow token.** Mermaid's arrow tokens mean different
  things across its dialects and versions, and nothing checks that a "reply" answers a call. Here a
  message says `call`, `reply` or `async`, the element draws each in the UML style (filled arrow,
  dashed return, open arrow), and the check can tell a call that never gets its reply.
- **Activation bars are worked out, never written.** In Mermaid and PlantUML the author activates
  and deactivates participants by hand, and a missed deactivation draws a bar to the bottom of the
  diagram. The pairing of a call with its reply already says when the receiver is busy, so the
  element draws the bar from it (SC-6).
- **The diagram scrolls with the page, at full text size, with the headers pinned.** A pan and zoom
  canvas suits a graph the reader explores in two directions. A sequence is read top to bottom, so it
  scrolls like the rest of the page, sideways only when it is wider than the screen. The participant
  headers stay pinned to the top so the reader always knows which column is which.
- **Traces reuse spec 2's format and panel, pointing at messages.** A message is where the payload
  travels in a sequence, so a step names a message and its value is the payload. Sharing the panel
  and its value tree keeps the two elements reading the same way and gives one copy to maintain.
- **Steps are nested, so fragments can nest.** An `alt` inside a `loop` is common (retry until the
  card clears). Nesting the steps in the JSON mirrors the boxes on the page, and the check can prove
  every fragment is well formed.
- **Hard limits stop the diagram from becoming unreadable.** Sequence diagrams get hard to follow as
  participants are added, so the check warns past 8 and fails past 16, warns on long labels, and warns
  on a diagram past about 60 messages, nudging the agent to split it.

## Behavior and scenarios

The scenarios share one checkout sequence unless they say otherwise. Participants: Shopper (kind
"person", color 1), Checkout (kind "ui", color 2), Billing (kind "service", color 3), Stripe (kind
"external", color 4) and Ledger (kind "store", color 5). Its steps:

1. Shopper → Checkout "place order" (call)
2. Checkout → Billing "charge order" (call)
3. `loop` "up to 3 attempts", holding:
   - Billing → Stripe "create charge" (call, id "create-charge")
   - `alt` with two branches:
     - "card valid": Stripe → Billing "charge succeeded" (reply, id "charge-ok")
     - "card declined": Stripe → Billing "card declined" (reply, id "charge-declined"), then a note over
       Billing "waits 2 seconds before retrying"
4. `opt` "charge succeeded", holding Billing → Ledger "record payment" (async, id "record")
5. Billing → Checkout "order paid" (reply, id "paid")
6. Checkout → Shopper "show receipt" (reply)

Drawn and numbered, that is 8 messages: 1 place order, 2 charge order, 3 create charge, 4 charge
succeeded, 5 card declined, 6 record payment, 7 order paid, 8 show receipt.

It carries two traces, each a payload moving through the messages:

- **"Card succeeds"**: place order, charge order, create charge, charge succeeded, record payment,
  order paid. 6 steps.
- **"Declined, then retried"**: place order, charge order, create charge, card declined, create
  charge, charge succeeded, record payment, order paid. 8 steps. Its values are in SC-14.

### Authoring and building

1. **SC-1**
   - **Given** an agent writing an explainer page about how checkout charges a card
   - **When** it writes the checkout sequence with its two traces and builds the page
   - **Then** the kit check passes, the diagram shows five participant columns and eight numbered
     messages inside a loop, an alt and an opt box, the toolbar has a "Step through" button, and
     "Diagram as a list" carries every participant, message, fragment, note and trace
   - **Data before:** **Source**: `<q-sequence summary="Checkout charges the card through Billing and Stripe, retrying a declined card.">`
     with kinds person, ui, service, external and store; five participants; the steps above; two traces
   - **Walkthrough:**
     1. The kit check confirms every message names known participants, every fragment is well formed,
        and every trace step names a known message
     2. In the browser the element draws one column per participant in the order listed, one row per
        step, and numbers the messages 1 to 8 top to bottom
     3. It writes the text list from the same data
   - **Data after:** **Built page**: ✓ kit check passed; ✓ no flow bundle inlined; **Diagram**: ✓ five
     columns, Shopper on the left; ✓ messages numbered 1 to 8; ✓ "Step through" in the toolbar;
     ✓ nothing moving; **Text list**: ✓ everything above
   - A sequence with no traces has no "Step through" button.

2. **SC-2**
   - **Given** a sequence whose data breaks the contract
   - **When** the page is built
   - **Then** the kit check fails or warns, names the element and the step, and the JS element reports
     the same failures when it parses the data, for each case in the table
   - **Kit check results:**

     | Sequence data | Result |
     |---|---|
     | a message from Billing to "strip", which no participant has | ✗ fails: message 3 names unknown participant "strip" |
     | a note over "ledgr" | ✗ fails: note names unknown participant "ledgr" |
     | two participants with the id "billing" | ✗ fails: duplicate id "billing" |
     | a participant and a message both with the id "billing" | ✗ fails: duplicate id "billing" |
     | a fragment of type "critical" | ✗ fails: unknown fragment type "critical"; use alt, opt, loop or par |
     | an `alt` with one branch | ✗ fails: alt needs at least 2 branches |
     | a `par` with one branch | ✗ fails: par needs at least 2 branches |
     | a fragment or branch with no steps | ✗ fails: fragment "up to 3 attempts" has no steps |
     | a message of type "return" | ✗ fails: message 7 has unknown type "return"; use call, reply or async |
     | a trace step naming message "charge-retry", which no message has | ✗ fails: trace "declined" step 5 names unknown message "charge-retry" |
     | 17 participants | ✗ fails: at most 16 participants |
     | no `summary` | ✗ fails: summary is required |
     | 9 participants | ✓ passes with a warning: sequences over 8 participants are hard to follow; split them |
     | a call that no reply answers | ✓ passes with a warning: call 2 "charge order" has no matching reply |
     | a message label of 52 characters | ✓ passes with a warning: message labels over about 40 characters crowd the row; move the rest to the detail |
     | 64 messages | ✓ passes with a warning: sequences over about 60 messages are hard to follow; split them |

   - The q-flow rules for kinds and details hold unchanged: an undeclared kind fails, more than eight
     kinds fails, and a detail may hold only paragraphs, lists, code and links.
   - The spec 2 rules for traces hold unchanged: a duplicate trace id, a trace with fewer than 2 steps,
     and a value that isn't JSON or runs over 400 pretty-printed lines fail; a value over about 40
     lines, a note over about 120 characters and a trace over about 30 steps warn.
   - The create and destroy rules are in SC-8.

### Drawing

3. **SC-3**
   - **Given** the checkout sequence on a 1280px page
   - **When** it loads
   - **Then** each message is drawn in the style for its type, numbered, on its own row, in the order
     the steps list them, with fragment rows in drawn order too
   - **Message styles:**

     | Type | Line | Arrow head | Example |
     |---|---|---|---|
     | call | ✓ solid | ✓ filled | 3. create charge, Billing → Stripe |
     | reply | ✓ dashed, back toward the caller | ✓ open | 4. charge succeeded, Stripe → Billing |
     | async | ✓ solid | ✓ open | 6. record payment, Billing → Ledger |

   - The number sits before the label, as in "3. create charge". Notes, fragments and branch labels
     carry no number. A message drawn once inside a loop gets one number, however many times the loop
     would run.

4. **SC-4**
   - **Given** a sequence where Billing sends itself "validate cart" (call)
   - **When** it loads
   - **Then** the message is drawn as an arrow leaving Billing's lifeline and looping back to it, on a
     taller row so the label fits, and it opens no activation bar
   - A self-message never activates its participant, whatever its type, because the participant is
     already busy sending it.

5. **SC-5**
   - **Given** the checkout sequence
   - **When** it loads
   - **Then** each fragment is a labeled box around exactly its rows, wide enough to cover every
     participant its steps touch, and `alt` and `par` are split into sections by a dashed line
   - **Fragment boxes:**

     | Fragment | Tab | Rows it covers | Columns it spans |
     |---|---|---|---|
     | loop | ✓ "loop" with "up to 3 attempts" | ✓ messages 3 to 5 and the note | ✓ Billing to Stripe |
     | alt | ✓ "alt", sections "card valid" and "card declined" | ✓ messages 4 and 5 and the note | ✓ Billing to Stripe |
     | opt | ✓ "opt" with "charge succeeded" | ✓ message 6 | ✓ Billing to Ledger |

   - A nested fragment sits inside its parent with a small inset, so both edges stay visible.
   - A note sits over its participants: centered on one, or stretched from the leftmost to the
     rightmost when it names several.

6. **SC-6**
   - **Given** the checkout sequence
   - **When** it loads
   - **Then** an activation bar runs on each receiver from its call to the reply that answers it, and
     async messages and replies open none
   - **Data before:** **Steps**: 1 place order (call), 2 charge order (call), 3 create charge (call),
     alt with 4 charge succeeded (reply) or 5 card declined (reply), 6 record payment (async), 7 order
     paid (reply), 8 show receipt (reply)
   - **Walkthrough:**
     1. Message 1 opens a bar on Checkout; message 2 opens a bar on Billing; message 3 opens a bar on
        Stripe
     2. Each alt branch starts with the calls that were open when the alt began, so message 4 closes
        Stripe's bar in the first branch and message 5 closes it again in the second
     3. Message 6 is async, so Ledger gets no bar
     4. Message 7 closes Billing's bar; message 8 closes Checkout's
   - **Data after:** **Activation bars**: ✓ Checkout, from 1 to 8; ✓ Billing, from 2 to 7; ✓ Stripe,
     from 3 to 4, and again from the start of the "card declined" section to 5; ✓ Ledger, none
   - **Matching rules:**

     | Case | Result |
     |---|---|
     | a reply from B to A | ✓ closes the most recent open call from A to B |
     | a call made while the receiver already has a bar | ✓ a second bar, offset, stacked on the first |
     | after an `alt` | ✓ a call counts as answered only if every branch answers it |
     | after a `par` | ✓ a call counts as answered if any branch answers it |
     | after an `opt` or `loop` | ✓ a call counts as answered if its body answers it |
     | a call opened inside a branch and not answered there | ✓ the bar ends at the branch's end, with the no-reply warning |
     | a call never answered | ✓ the bar runs to the end of the diagram, or to the participant's end, with the no-reply warning |
     | a reply that answers no open call | ✓ drawn as a reply, no bar changes, with a warning: reply 5 answers no call |

7. **SC-7**
   - **Given** the checkout sequence
   - **When** it loads
   - **Then** each participant has a header at the top of its column with its label, its kind as a
     small tag, and an accent stripe in its kind's chart color, and a dashed lifeline runs down from
     it; a participant with no kind has a plain header
   - The kinds and colors match q-flow's, so the same kind reads the same way on both elements.

8. **SC-8**
   - **Given** a sequence where Billing sends "start session" to Receipt worker, marked as creating
     it, and later Receipt worker ends
   - **When** it loads
   - **Then** Receipt worker's header is drawn at the row of "start session" rather than at the top,
     its lifeline starts there, and it ends in an X at the row where it ends
   - **Data before:** **Participant**: Receipt worker; **Steps**: Billing → Receipt worker "start
     session" (call, creates its receiver); Receipt worker → Billing "session ready" (reply); Billing
     → Receipt worker "send receipt" (async); end of Receipt worker
   - **Data after:** **Diagram**: ✓ Receipt worker's header at the "start session" row; ✓ empty column
     above it; ✓ lifeline ending in an X under "send receipt"
   - **Create and destroy checks:**

     | Data | Result |
     |---|---|
     | a message touching Receipt worker before the message that creates it | ✗ fails: message 2 touches Receipt worker before it is created |
     | a message touching Receipt worker after it ends | ✗ fails: message 6 touches Receipt worker after it ends |
     | two messages that create Receipt worker | ✗ fails: Receipt worker is created twice |
     | Receipt worker ended twice | ✗ fails: Receipt worker ends twice |
     | a self-message marked as creating | ✗ fails: a message can't create its own sender |

   - A message creates its receiver, never its sender. Any participant can end, whether it created
     itself or was there from the top. A participant ending while a call to it is open closes the
     bar there, with the no-reply warning.

### Narrow screens

9. **SC-9**
   - **Given** the checkout sequence on a 375px phone
   - **When** the reader scrolls down the page and then sideways across the diagram
   - **Then** the diagram keeps its full text size, scrolls sideways inside its own box, and scrolls
     down with the page; once the header row scrolls off the top, the participant headers stay pinned
     at the top of the screen, lined up with their columns as the reader scrolls sideways
   - **Screen states:**

     | Moment | Shown |
     |---|---|
     | page load | ✓ Shopper, Checkout and part of Billing visible; ✓ the rest reachable by scrolling sideways |
     | scrolled down past the headers | ✓ the headers pinned at the top; ✓ the page scrolls normally |
     | scrolled sideways to Stripe | ✓ the pinned headers move with the columns, so Stripe's header sits over Stripe's lifeline |
     | scrolled past the end of the diagram | ✓ the pinned headers leave with it |

   - The pinned headers name every participant, including one created further down, so the reader
     always knows which column is which. There is no pan, no zoom and no expand button; the page itself
     is the view.

### Exploring

10. **SC-10**
    - **Given** the checkout sequence with nothing focused
    - **When** the reader clicks Stripe's header
    - **Then** Stripe's lifeline and the messages that touch it (3, 4 and 5) light, every other
      message and lifeline dims, and the drawer opens with Stripe's label, kind, detail and the
      numbered messages it sends and receives
    - **Data before:** **Diagram**: nothing focused; drawer closed
    - **Walkthrough:**
      1. The reader clicks Stripe's header
      2. The element lights Stripe and messages 3, 4 and 5, and dims messages 1, 2, 6, 7 and 8, the
         note, and every other lifeline
      3. The drawer opens on Stripe
    - **Data after:** **Diagram**: ✓ Stripe and messages 3 to 5 at full color; ✓ the rest dimmed;
      ✓ fragment boxes still visible; **Drawer**: ✓ "Stripe", kind "external", its detail, "receives
      3. create charge", "sends 4. charge succeeded", "sends 5. card declined"
    - Clicking the same header again, clicking empty space, or pressing Escape clears focus and closes
      the drawer.

11. **SC-11**
    - **Given** the checkout sequence with nothing focused
    - **When** the reader clicks message 2, "charge order"
    - **Then** message 2 lights, its two participants' headers are marked, everything else dims, and
      the drawer opens on the message
    - **Drawer contents:**

      | Part | Shown |
      |---|---|
      | title | ✓ "2. charge order" |
      | from and to | ✓ Checkout → Billing |
      | type | ✓ call |
      | answered by | ✓ "7. order paid", a link that opens message 7 |
      | detail | ✓ the message's detail, or nothing if it has none |

    - A reply's drawer shows "answers 2. charge order" in the same place. A message inside fragments
      also lists them, for example "inside loop: up to 3 attempts, alt: card declined".
    - Clicking a message or participant named in the drawer moves focus to it.
    - At 700px and narrower the drawer opens as a bottom sheet, as in q-flow; wider, it docks beside
      the diagram and stays in view as the page scrolls.

12. **SC-12**
    - **Given** a keyboard user tabbing through the page
    - **When** they tab into the diagram
    - **Then** focus lands on the first participant's header, and the keys work as in the table, with
      each move announced in a live region
    - **Keyboard:**

      | Key | Result |
      |---|---|
      | Tab | ✓ enters the diagram on one header or message, and a second Tab leaves it |
      | Left and Right arrows | ✓ move between participant headers |
      | Down arrow on a header | ✓ moves to the first message touching that participant |
      | Up and Down arrows on a message | ✓ move to the previous or next message by number |
      | Up arrow on message 1 | ✓ moves back to its sender's header |
      | Enter | ✓ focuses the participant or opens the message, as a click does, and announces it, for example "Message 3 of 8, Billing to Stripe, create charge, call" |
      | Escape | ✓ clears focus and closes the drawer |

    - Moving keyboard focus scrolls the page and the diagram so the focused header or message is in
      view.

### Stepping through a trace

13. **SC-13**
    - **Given** the checkout sequence on a 1280px page, with Stripe focused
    - **When** the reader presses "Step through"
    - **Then** focus clears and the drawer closes, spec 2's trace panel opens beside the diagram on
      the first trace, and the diagram shows step 1: message 1 lit with its arrow pulsing, messages off
      the trace dimmed, and the value shown with no change marks
    - **Data before:** **Diagram**: Stripe focused; drawer open
    - **Walkthrough:**
      1. The reader presses "Step through"
      2. The element clears focus, closes the drawer and opens the panel on "Card succeeds"
      3. It lights message 1 and pulses its arrow from Shopper to Checkout, and dims messages 5 and 8
         and the note, because "Card succeeds" never reaches them
    - **Data after:** **Diagram**: ✓ message 1 current, its arrow pulsing; ✓ messages 2, 3, 4, 6 and 7 at
      full color; ✓ messages 5 and 8 and the note dimmed; **Panel**: ✓ beside the diagram, staying in
      view as the page scrolls; ✓ "Step 1 of 6"; ✓ the value with no marks
    - The panel's controls, change marks, "Changes only" toggle, collapsing, Play, keyboard and live
      region work exactly as spec 2 sets out. The live region names the message, for example "Step 3
      of 6, message 3, Billing to Stripe, create charge".
    - Only the current message's arrow pulses. Messages earlier in the trace stay at full color and
      still.

14. **SC-14**
    - **Given** "Declined, then retried" open at step 1
    - **When** the reader presses Next seven times
    - **Then** each step lights its message and shows the payload's changes in the table, step 5
      returns to message 3 because the loop runs again, and the page and diagram scroll so the current
      message stays in view
    - **Data before:** **Step 1, message 1 place order**: value { order "C-2207"*, items 2, total
      48.00 }
    - **Changes at each step:**

      | Step | Message | Changes shown |
      |---|---|---|
      | 1 | 1. place order | none, the first step |
      | 2 | 2. charge order | `+` amount 48.00; `+` currency "usd" |
      | 3 | 3. create charge | `+` attempt 1; `+` card "•••• 4242"* |
      | 4 | 5. card declined | `+` decline "insufficient_funds" |
      | 5 | 3. create charge | attempt 1 → 2; decline struck through |
      | 6 | 4. charge succeeded | `+` charge "ch_91"*; `+` status "succeeded" |
      | 7 | 6. record payment | none; the payload passes through unchanged |
      | 8 | 7. order paid | status "succeeded" → "paid" |

    - A trace's steps may name messages in any order, so it can go around a loop again or skip a
      message, as this one skips 8. The element doesn't check that a trace follows the drawn order.
    - A step that revisits a message lights the same row; the panel's counter tells the reader which
      visit it is.

15. **SC-15**
    - **Given** "Declined, then retried" at step 2
    - **When** the reader clicks message 3, then clicks it again, then clicks message 8
    - **Then** the first click jumps to step 3 and the second to step 5, its next visit, as in spec 2;
      the click on message 8, which is off the trace, leaves trace mode and opens message 8's drawer
    - Clicking empty space doesn't leave trace mode. Escape or "Step through" again leaves it, and the
      diagram returns to rest with nothing dimmed and nothing pulsing.

16. **SC-16**
    - **Given** the reader has reduced motion turned on
    - **When** they step through a trace, by hand or with Play
    - **Then** every step changes as usual, but nothing animates: the current message is a thicker
      static line with its arrowhead, with no pulse, and the page jumps instead of easing when it
      scrolls to the current message

17. **SC-17**
    - **Given** the checkout sequence on a 375px phone
    - **When** the reader opens trace mode
    - **Then** the trace panel is pinned to the bottom of the screen, at most about half its height,
      and the page scrolls so the current message sits in view above the panel
    - The panel's header row, with the counter, Back and Next, stays visible; the reader can collapse
      the rest of the panel to see more of the diagram. It docks beside the diagram above 700px.

### Text list and fallbacks

18. **SC-18**
    - **Given** the checkout sequence
    - **When** the reader opens "Diagram as a list", or the page loads with scripts off
    - **Then** the list carries the participants, then the steps as a numbered list with fragments
      as nested lists and notes inline, then each trace as an ordered list of steps, and the no-script
      fallback the build writes carries the same
    - **List entries:**

      | Part | Entry |
      |---|---|
      | participant | Stripe (external): its detail |
      | message | 3. Billing → Stripe: create charge (call) |
      | async message | 6. Billing → Ledger: record payment (async) |
      | fragment | loop: up to 3 attempts, with its steps nested under it |
      | alt fragment | alt: card valid / card declined, each branch a nested list under its label |
      | note | Note over Billing: waits 2 seconds before retrying |
      | created participant | 1. Billing → Receipt worker: start session (call, creates Receipt worker) |
      | end | Receipt worker ends |
      | trace step | 4. message 5, Stripe → Billing, card declined, then the value as a code block |

    - With scripts off the diagram area shows a one-line notice and the list starts open, as in
      q-flow.

19. **SC-19**
    - **Given** a screen-reader user
    - **When** they reach the diagram
    - **Then** they hear its summary, can open the text list, and find everything the diagram shows,
      details and traces included

### Other surfaces

20. **SC-20**
    - **Given** a page whose only diagram is a `q-sequence`
    - **When** it is built
    - **Then** the built page carries the kit and no flow bundle; a page with both a `q-sequence` and a
      `q-flow` carries the flow bundle once, for the `q-flow`

21. **SC-21**
    - **Given** a tier-2 app view, or a companion screen during brainstorming
    - **When** it renders a `q-sequence`
    - **Then** it behaves as on a tier-1 page; in the companion it may sit in a screen's `content`, and
      one in an option's `html` breaks the rule against interactive elements in option cards, as for
      `q-flow`

22. **SC-22**
    - **Given** verify running on a page with a sequence
    - **When** it takes screenshots
    - **Then** it waits until every sequence has drawn, so no screenshot shows an empty diagram, and
      the theme toggle recolors the headers, arrows, bars and fragment boxes without a reload

### Choosing

23. **SC-23**
    - **Given** an agent asked for "an HTML page explaining how checkout talks to Billing and Stripe
      when a card is declined"
    - **When** it writes the page
    - **Then** it writes a `q-sequence` with an `alt` for the declined card, keeps labels short and
      payloads in details or traces, and doesn't use Mermaid; asked for the same diagram inside a
      Markdown README, it writes Mermaid
    - **Choosing:**

      | Request | Element |
      |---|---|
      | a sequence diagram on an HTML page | ✓ `q-sequence` |
      | a graph of services the reader will explore | ✓ `q-flow` |
      | any diagram inside Markdown | ✓ Mermaid |
      | a state chart on an HTML page | ✓ Mermaid, as today |

## Scope and non-goals

In scope:

- the `q-sequence` element: participants, kinds, messages and their three types, self-messages,
  notes, the four fragment types and nesting, create and end, numbering, activation bars
- pinned headers and sideways scrolling, participant focus, the message drawer, keyboard and the live
  region
- traces pointing at messages, trace mode with spec 2's trace panel, the pulse and reduced motion
- the text list and the no-script fallback
- the kit check rules in SC-2 and SC-8, in both the Python check and the JS element
- factoring spec 2's trace panel and value tree so both elements share them
- the skill's text on choosing `q-sequence`, `q-flow` and Mermaid in SKILL.md, the design reference,
  the template rules and the evals; the generated components reference; the tier-2 typings
- an example page with the checkout sequence and its two traces

Not in scope:

- collapsing fragments
- pan and zoom, and an expand button
- editing a sequence on the page
- links from a message to a node in a `q-flow`
- `break` and `critical` fragments

## Success criteria

- An eval of "sequence diagram on an HTML page" prompts shows the agent writing `q-sequence`, and
  Mermaid for the same diagram in Markdown.
- Verify screenshots of the example at 375px and 1280px in both themes show legible full-size labels,
  pinned headers, activation bars and fragment boxes, and the trace panel beside the diagram on
  desktop and pinned to the bottom on the phone.
- A page with only `q-sequence` carries no flow bundle.

## Decisions Locked

Element and data:

- `<q-sequence summary="…">` with a JSON `<script type="application/json">` child, the same pattern as
  q-flow. Its own element and its own SVG renderer, laid out in columns and rows with no ELK, so a
  page with only `q-sequence` doesn't inline the flow bundle.
- `kinds` as in q-flow: a name mapped to a chart color from 1 to 8.
- `participants`: each has an id and a label, and optionally a kind and a detail, with q-flow's
  sanitized HTML whitelist.
- `steps`: an ordered, nested list of messages, notes and fragments. A message has an optional id,
  from, to, label, type (`call`, `reply` or `async`) and an optional detail; from equal to to is a
  self-message. A note has text and the participants it sits over. A fragment is `alt`, `loop`,
  `opt` or `par` with an optional label and its steps; `alt` and `par` have branches, each with a
  label and steps.
- A participant can start partway down when a message creates it, and can end with an X.
- `traces` use spec 2's format, except that a step points at a message, and its value is the
  message's payload.

Drawing:

- A call is a solid line with a filled arrow, a reply is dashed back to the caller, and async is a
  solid line with an open arrow. Messages are numbered automatically.
- Activation bars are worked out: a call activates the receiver until its matching reply; async
  messages never activate.
- Fragments are labeled boxes, with `alt` and `par` split into sections.
- Each participant header carries its kind's color accent.

Narrow screens:

- The diagram scrolls sideways at full text size, with the participant headers pinned to the top
  while the reader scrolls down. No pan or zoom canvas; the diagram scrolls with the page.

Exploring:

- Clicking a participant highlights its lifeline and the messages touching it and dims the rest.
- Clicking a message opens a drawer with its label, number, from and to, and detail.
- The keyboard model follows q-flow's, with Escape to clear.
- With traces, "Step through" opens spec 2's trace panel; the current message lights up and its arrow
  pulses, under spec 2's reduced-motion rules.

Text list and fallback:

- Messages are a numbered list, as in "3. Billing → Stripe: create charge (call)"; fragments are
  nested lists, as in "alt: card valid / else"; notes are inline; each trace is an ordered list of
  steps.

Kit check, with the JS element and the Python check kept in step:

- Fails: an unknown participant, a duplicate id, an unknown fragment type, an `alt` or `par` with
  fewer than 2 branches, a trace step naming an unknown message, more than 16 participants, no
  `summary`.
- Warns: more than 8 participants, a call with no matching reply, a message label over about 40
  characters, more than about 60 messages.

Choosing:

- Sequence diagrams on HTML pages use `q-sequence`; Mermaid keeps diagrams inside Markdown. The
  SKILL.md, design reference, template rules and evals change to say so, and the skill test that
  allows only `q-flow` and `mermaid` as expected values widens.

Choices this spec makes within those decisions, for review:

- Create is a flag on the message that creates its receiver; ending is its own step naming the
  participant, alongside messages, notes and fragments (Conceptual model, SC-8).
- The create and end checks in SC-8 fail; a fragment or branch with no steps fails; a message type
  other than call, reply or async fails (SC-2).
- How a reply matches its call, including across fragment branches, and the warning for a reply that
  answers no call (SC-6).
- A self-message never activates (SC-4).
- Clicking a participant also opens the drawer with its detail and messages (SC-10); clicking a
  message lights it and dims the rest, and its drawer links the call and its reply (SC-11).
- The keyboard model: Left and Right across headers, Up and Down through messages by number
  (SC-12). There are no zoom keys, since there is no zoom.
- No expand button (SC-9).
- On phones the trace panel is pinned to the bottom of the screen and collapsible, rather than placed
  below the diagram as in spec 2, because a long diagram would push the panel out of sight of the
  current message (SC-17).
- A trace's steps aren't checked against the drawn order (SC-14).

## Industry Insights

From research during the brainstorm and while writing this spec, with source pages checked
2026-10-17.

- **Sequence diagrams get hard to read as participants are added, and the advice is to split them.**
  Tool guides describe too many lifelines as "a dense web of crossing lines" and recommend smaller,
  focused diagrams ([Visual Paradigm](https://skills.visual-paradigm.com/?p=2926)); Microsoft's
  engineering playbook splits a scenario into sub-scenario diagrams for the same reason
  ([Microsoft playbook](https://microsoft.github.io/code-with-engineering-playbook/design/diagram-types/sequence-diagrams/)),
  and a PlantUML user asks for folding because "many participants and levels of indentation" stop
  being readable ([PlantUML forum](https://forum.plantuml.net/19361/suggestion-sequence-diagram-simplified)).
  The brainstorm's figure of about 5 to 6 participants isn't a published rule; no source in this pass
  gives a number, so the 8 and 16 limits are this spec's own.
- **Mermaid's guidance favors short ids, short labels and failure branches.** Mermaid gives each
  participant an id and a descriptive alias ([Mermaid sequence diagrams](https://mermaid.js.org/syntax/sequenceDiagram.html));
  a widely shared Mermaid skill guide recommends short ids with aliases, short message labels with the
  payload moved to notes, `alt` for failure paths, and refactoring large diagrams into focused
  sub-diagrams ([Mermaid sequence diagram skill](https://sharedcontext.ai/skills/external/msewell/mermaid-sequence-diagrams)).
  The brainstorm's "separate happy-path and failure-path diagrams" wasn't found as stated in this
  pass; the guide argues for failure branches inside the diagram instead, which is what `alt` and
  traces give here.
- **Mermaid's arrow semantics are ambiguous.** Mermaid draws arrows without saying which are calls,
  replies or async messages: it offers solid and dotted lines with and without heads, crosses and open
  heads ([Mermaid sequence diagrams](https://mermaid.js.org/syntax/sequenceDiagram.html)); its 7.0
  docs labeled the cross as async ([Mermaid 7.0 docs](https://unpkg.com/mermaid@7.0.0/build/www/sequenceDiagram.html)),
  and the UML convention is a filled head for a call, an open head for async and a dashed line for a
  reply, noting that "the arrowhead, not the dashed stroke, distinguishes an asynchronous message"
  ([Schematex on UML arrows](https://schematex.js.org/research/uml-synchronous-vs-asynchronous-message-arrows)).
- **PlantUML and Mermaid model the same fragments.** Both have `alt`, `opt`, `loop`, `par`, `break`
  and `critical`; PlantUML adds a free `group` and Mermaid a colored `rect`
  ([PlantUML sequence diagrams](https://plantuml.com/sequence-diagram),
  [Mermaid sequence diagrams](https://mermaid.js.org/syntax/sequenceDiagram.html)).
- **Both make the author write activations and lifetimes by hand.** Mermaid uses `activate` and
  `deactivate` or `+` and `-` on an arrow, and stacks activations; PlantUML has the same plus
  `autoactivate on` with `return`. Both mark create and destroy just before the message involved, and
  Mermaid allows only the receiver to be created
  ([Mermaid sequence diagrams](https://mermaid.js.org/syntax/sequenceDiagram.html),
  [PlantUML sequence diagrams](https://plantuml.com/sequence-diagram)).

## Deferred Ideas

Left out of this spec during the brainstorm:

- collapsing fragments
- pan and zoom
- editing a sequence on the page
- links from a message to a node in a `q-flow`
- `break` and `critical` fragments

Build-only questions for the tech spec:

- `[tech-spec]` Field names for create and end, kept flat and checkable in both the Python check and
  the JS element.
- `[tech-spec]` Pinned headers inside a box that scrolls sideways: a sideways-scrolling box becomes
  the sticky container, so the headers need a separate strip kept in step with the box's scroll.
- `[tech-spec]` Row heights: measuring labels, wrapping long labels, and the extra height for
  self-messages, notes and fragment tabs.
- `[tech-spec]` Fragment insets for nesting, and how far a fragment box extends past its outermost
  columns.
- `[tech-spec]` Where spec 2's trace panel and value tree move so both elements import them without
  the flow bundle, and how the panel docks beside a diagram that scrolls with the page.
- `[tech-spec]` The pulse along a message arrow, reusing spec 2's single-edge pulse.
- `[tech-spec]` The readiness signal verify waits on, shared with `q-flow`.
- `[tech-spec]` How the Python check numbers messages the same way the JS element does, so the two
  name the same message in their errors.

## Glossary

- **sequence**: one `q-sequence` element and its data.
- **participant**: one column in the sequence, such as a service or a person.
- **lifeline**: the dashed line running down from a participant's header.
- **message**: one arrow from a participant to another, or to itself, of type call, reply or async.
- **call**: a message whose sender waits for a reply.
- **reply**: a message answering an earlier call, drawn dashed back to the caller.
- **async**: a message whose sender doesn't wait.
- **self-message**: a message whose sender and receiver are the same participant.
- **activation bar**: the narrow bar on a lifeline showing the participant is busy with a call.
- **note**: a short remark drawn over one or more participants.
- **fragment**: a labeled box around a run of steps: alt, opt, loop or par.
- **branch**: one section of an alt or par fragment, with its own label and steps.
- **step**: one entry in the sequence's steps (a message, note, fragment or end), or one stop on a
  trace, at one message.
- **focus**: the state where one participant or message is lit and the rest dimmed.
- **drawer**: the panel that shows a focused participant's or message's detail.
- **trace mode**: the state where the diagram shows a trace and the trace panel is open.
- **pinned headers**: the participant headers held at the top of the screen while the diagram
  scrolls under them.

## Status & amendments

**Status**: Approved

**Amendments:** none yet.
