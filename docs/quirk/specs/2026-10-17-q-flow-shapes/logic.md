# Logic spec: decisions, loops and subprocesses in `q-flow`

**Status**: Approved · Tech spec: authored (`tech.md`; tier gate fired: crosses subsystem boundaries and touches >3 source files)

`q-flow` draws every node as a rectangle and has no idea what a loop is. It accepts cycles, but the
layout engine silently picks which edge to run backwards, and that choice can bend the main path. A
node that loops to itself draws as a short stub. So agents still reach for static Mermaid whenever a
page needs a flowchart, and the reader loses focus, the drawer and the pulse.

This spec adds three things to `q-flow`: decision nodes, loops drawn as returns, and subprocess nodes
that can open another graph on the page. With them, `q-flow` becomes the tool for every flowchart on
an HTML page.

It is the first of four specs. The other three (value step-through, an interactive sequence diagram
and an interactive data model) each get their own brainstorm once this one ships; see
[Deferred Ideas](#deferred-ideas). It extends the element specified in
[the q-flow logic spec](../2026-10-16-q-flow/logic.md), and everything that spec says still holds
unless this one changes it.

## Conceptual model

The graph keeps its four kinds of thing (node, edge, group, kind). Nodes gain a **shape** and edges
gain a **loop** mark:

| Thing | What's new | What the agent gives it |
|---|---|---|
| node | a shape: box (the default), decision or subprocess | optionally `shape`; a subprocess may also name a `flow` |
| edge | a loop mark, for an edge that returns to an earlier step | optionally `loop: true` |

- **Decision.** A diamond holding a short question of up to two lines, such as "Paid?". Each edge
  leaving it is one **exit**, and the exit's label is the answer ("Yes", "No", "timeout"). A decision
  can still have a kind. Its kind color becomes the diamond's outline, because a diamond has no room
  for the stripe a box carries.
- **Subprocess.** The usual box with a second line down each side, meaning "this step is a process of
  its own". It may name another `q-flow` on the same page as its **linked flow**; its drawer then
  offers an "Open flow" button. Without a linked flow it is only a visual marker, and its detail
  explains the process in words.
- **Loop edge.** An edge the agent marks as returning to an earlier step, such as a retry. The layout
  treats it as running backwards, so the forward path stays straight, and it draws as a distinct
  return line with a return marker and its label. An edge from a node to itself is a **self-loop**,
  always a loop whether marked or not, and draws as a small arc on the node.

Shape and kind are independent. Kind still says what a thing is (a worker, a queue); shape says what
role the step plays in the flow.

**Forward edges** are every edge that isn't a loop. The focus walk and the pulse use forward edges
only, so a loop never drags a whole cycle into focus and pulses never circle forever.

## Data flow

1. **Choosing.** The agent reaches for `q-flow` for every flowchart on an HTML page, explorable or
   not. It keeps Mermaid for diagrams inside Markdown, for state charts, and for sequence and ER
   diagrams until their own elements ship.
2. **Authoring.** The agent writes nodes and edges as today, adds `shape` to the decision and
   subprocess nodes, labels every exit of a decision, marks each return edge with `loop: true`, and
   gives a subprocess `flow` when another graph on the page shows its inside.
3. **Building.** The kit check runs the new rules in SC-5 over each graph, and checks every `flow`
   against the ids of the page's other `q-flow` elements. The no-JS fallback list carries decisions,
   loops and links.
4. **Loading.** The element turns each loop edge around before it hands the graph to the layout
   engine, lays it out, then draws loop edges in their true direction as return lines. Decisions draw
   as diamonds and subprocesses as double-edged boxes. The text list is written from the same data.
5. **Reading.** Focus lights the forward path plus the loop edges inside it, pulses run along forward
   edges, and a subprocess drawer's "Open flow" button takes the reader to the linked graph.
6. **Verifying.** Verify screenshots the example flowchart at 375px and 1280px in both themes.

## Key decisions and rationale

- **The agent marks loops; the element doesn't guess.** The layout engine has to run some edge of a
  cycle backwards, and its default picks by edge count with random tie-breaks. A wrong pick bends the
  main path. The agent knows which edge is the retry, so it says so, and the check warns about any
  cycle left unmarked.
- **Turn loop edges around before layout, draw them the right way after.** In the research, writing
  the return edge the other way round removed the engine's detours and halved total edge length.
  Turning it back for drawing keeps the arrow honest.
- **Focus and pulse ignore loop edges.** Every node in a cycle is both upstream and downstream of
  every other, so a plain walk would light the whole cycle from any node in it. Walking forward edges
  only keeps the lit path meaningful. Pulses on loop edges would circle for as long as the node stays
  focused, which breaks the "motion only on focus, and readable" rule the q-flow spec set.
- **Shape is a node field, separate from kind.** A decision might belong to the "worker" kind, and a
  kind-level shape would force every decision to have a kind.
- **A diamond, not a box with a badge.** The diamond reads as a flowchart at a glance. Diamonds hold
  less text than their bounding box, so the question is capped at two lines and the check warns
  above about 24 characters.
- **Subprocess links stay on the page.** Opening another graph on the same page needs no URL scheme
  and lets the check prove the target exists. Expanding a subprocess in place is a bigger feature
  (the q-flow spec already ruled out collapsing groups), so it is deferred.

## Behavior and scenarios

The scenarios share one checkout graph unless they say otherwise. It has kinds "ui" (color 1),
"worker" (color 2) and "queue" (color 4); nodes Checkout (ui), Charge worker (worker), Paid?
(decision, worker), Ship (worker), Retry queue (queue) and Issue refund (subprocess, linked flow
"refund-flow"); and edges Checkout to Charge worker "order.created" async, Charge worker to Paid?,
Paid? to Ship "Yes", Paid? to Retry queue "No", Retry queue to Charge worker "retry up to 3x" marked
loop, and Ship to Issue refund "on return". A second graph on the page has the id "refund-flow".

### Drawing

1. **SC-1**
   - **Given** the checkout graph
   - **When** the page loads
   - **Then** Paid? draws as a diamond with its question inside and the worker color on its outline,
     its two exits carry "Yes" and "No", and the forward chain Checkout, Charge worker, Paid?, Ship
     runs left to right in that order without bending back
   - **Data before:** **Source**: Paid? with shape decision, kind worker; exits "Yes" to Ship and
     "No" to Retry queue
   - **Walkthrough:**
     1. The element measures "Paid?" and sizes the diamond to fit it on one line
     2. The layout places Checkout, Charge worker, Paid? and Ship in four successive columns
   - **Data after:** **Graph on screen**: ✓ Paid? is a diamond with a worker-color outline and no
     stripe; ✓ "Yes" on the edge to Ship; ✓ "No" on the edge to Retry queue; ✓ Checkout, Charge worker,
     Paid?, Ship left to right

2. **SC-2**
   - **Given** the checkout graph, with the Retry queue to Charge worker edge marked loop
   - **When** the page loads
   - **Then** that edge draws as a return line routed around the steps it passes, with a return
     marker and its label "retry up to 3x", its arrow pointing at Charge worker, and the forward chain
     stays in increasing column order
   - **Data before:** **Edge**: Retry queue to Charge worker, "retry up to 3x", loop
   - **Walkthrough:**
     1. The element hands the layout engine the edge turned around, Charge worker to Retry queue, so
        the engine sees no cycle
     2. The layout places Retry queue after Paid?, to the right of Charge worker
     3. The element draws the edge from Retry queue back to Charge worker, styled as a return
   - **Data after:** **Graph on screen**: ✓ Charge worker's column comes before Paid?'s, which comes
     before Retry queue's; ✓ the return line runs from Retry queue back to Charge worker with a return
     marker; ✓ label "retry up to 3x" beside it

3. **SC-3**
   - **Given** a graph with a node Status poller and an edge from Status poller to itself labelled
     "every 30s", not marked loop
   - **When** the page loads
   - **Then** the edge draws as a small return arc on Status poller with "every 30s" beside it, never
     a straight stub, and the check raises no unmarked-cycle warning for it

4. **SC-4**
   - **Given** the checkout graph
   - **When** the page loads
   - **Then** Issue refund draws as a box with a second line down each side, keeps its stripe and
     kind tag if it has a kind, and looks the same whether or not it names a linked flow

### Kit check

5. **SC-5**
   - **Given** a graph whose new fields break the contract
   - **When** the page is built
   - **Then** the kit check fails or warns, names the element and the problem, and the JS element
     reports the same failures when it parses the data, for each case in the table
   - **Kit check results:**

     | Graph data | Result |
     |---|---|
     | a node with shape "oval" | ✗ fails: unknown shape "oval"; use box, decision or subprocess |
     | a decision with one exit | ✗ fails: decision "paid" needs at least 2 exits |
     | a decision exit with no label | ✗ fails: every exit of decision "paid" needs a label |
     | `flow` on a box or decision node | ✗ fails: only a subprocess can name a flow |
     | a subprocess whose `flow` is "refunds" and no `q-flow` on the page has that id | ✗ fails: flow "refunds" names no q-flow on this page |
     | an edge with loop "yes" | ✗ fails: loop must be true or false |
     | a decision labelled "Has the customer confirmed their address?" (42 characters) | ✓ passes with a warning: decision labels over about 24 characters overflow the diamond |
     | a decision with two exits both labelled "Yes" | ✓ passes with a warning: decision "paid" has two exits labelled "Yes" |
     | a cycle Charge worker, Paid?, Retry queue with no edge marked loop | ✓ passes with a warning: cycle with no loop edge; mark the return edge with loop: true |

   - A loop edge leaving a decision is one of its exits, so it counts toward the two and needs a
     label like any other.
   - The JS element can't see the rest of the page at parse time, so it reports a missing `flow`
     target in the drawer (SC-11), not as a parse failure.

### Focus and pulse

6. **SC-6**
   - **Given** the checkout graph, nothing focused
   - **When** the reader clicks Ship
   - **Then** Ship's forward path lights (Checkout, Charge worker, Paid? upstream; Issue refund
     downstream) and Retry queue stays dim, even though a loop edge leads from it back into the path
   - **Data before:** **Graph**: nothing focused
   - **Walkthrough:**
     1. The reader clicks Ship
     2. The element walks forward edges only: upstream Paid?, Charge worker, Checkout; downstream
        Issue refund
     3. The walk never follows Retry queue to Charge worker, because that edge is a loop
   - **Data after:** **Graph**: ✓ Checkout, Charge worker, Paid?, Ship, Issue refund lit; ✓ Retry
     queue dimmed; ✓ the "No" edge and the "retry up to 3x" loop edge dimmed

7. **SC-7**
   - **Given** the checkout graph, nothing focused
   - **When** the reader clicks Charge worker
   - **Then** the forward path lights (Checkout upstream; Paid?, Ship, Retry queue, Issue refund
     downstream), and the "retry up to 3x" loop edge lights with it because both its ends are lit
   - **Data after:** **Graph**: ✓ every node lit; ✓ "retry up to 3x" lit as a return line
   - A loop edge lights exactly when both its ends are on the lit path. A self-loop lights when its
     node is lit.

8. **SC-8**
   - **Given** Charge worker focused, as in SC-7
   - **When** pulses run
   - **Then** pulses travel the lit forward edges in flow order as before, and no pulse ever runs along
     the "retry up to 3x" loop edge or any self-loop
   - **Data before:** **Pulse schedule**: Checkout to Charge worker, then Charge worker to Paid?, then
     Paid? to Ship and Paid? to Retry queue, then Ship to Issue refund
   - **Walkthrough:**
     1. The element builds the schedule from forward edges only
     2. Each pulse finishes at Retry queue and at Issue refund; none continues back to Charge worker
   - **Data after:** **Pulse schedule**: ✓ the four forward hops above; ✗ Retry queue to Charge worker
     never scheduled

9. **SC-9**
   - **Given** the reader has reduced motion turned on
   - **When** they focus Charge worker
   - **Then** the lit path is the thicker static line with arrowheads, as in the q-flow spec, and the
     lit loop edge is drawn the same way in its return style

### Subprocess links

10. **SC-10**
    - **Given** the checkout graph and the "refund-flow" graph further down the page
    - **When** the reader clicks Issue refund and presses "Open flow" in its drawer
    - **Then** the page scrolls to the "refund-flow" graph, that graph fits to view, and keyboard focus
      moves into it; the checkout graph keeps its own focus and drawer
    - **Data before:** **Checkout graph**: Issue refund focused, drawer open; **Refund graph**: zoomed
      in on one corner*
    - **Walkthrough:**
      1. The reader presses "Open flow"
      2. The page scrolls the refund graph into view and the refund graph fits itself
      3. Keyboard focus lands on the refund graph
    - **Data after:** **Checkout graph**: ✓ Issue refund still focused; **Refund graph**: ✓ in view;
      ✓ fitted; ✓ holds keyboard focus
    - If the checkout graph is expanded to full screen, it returns to the page first, then the page
      scrolls.

11. **SC-11**
    - **Given** a subprocess whose `flow` names "refunds" and no graph on the page has that id, for
      example on a page the kit check never saw
    - **When** the reader opens its drawer
    - **Then** the drawer shows no working "Open flow" button and says the linked flow "refunds"
      isn't on this page; the rest of the graph works

12. **SC-12**
    - **Given** a subprocess with no `flow`
    - **When** the reader opens its drawer
    - **Then** the drawer shows the node's detail and edges as for any node, with no "Open flow"
      button

### Text list and no-script fallback

13. **SC-13**
    - **Given** the checkout graph
    - **When** the reader opens "Graph as a list", or the page loads with scripts off
    - **Then** the list reads decisions, loops and links as in the table, and the no-script fallback
      the build writes says the same thing
    - **List entries:**

      | Node | Entry |
      |---|---|
      | Paid? | Paid? (decision, worker): Yes → Ship, No → Retry queue |
      | Retry queue | Retry queue (queue): ↩ returns to Charge worker: retry up to 3x |
      | Status poller from SC-3 | Status poller: ↩ returns to itself: every 30s |
      | Issue refund | Issue refund (subprocess): opens the "refund-flow" graph, as a link to it |
      | Ship | Ship (worker): → Issue refund (on return), as today |

### Choosing

14. **SC-14**
    - **Given** an agent asked for "an HTML page explaining our checkout flowchart, with the payment
      check and the retry loop"
    - **When** it picks a diagram
    - **Then** it writes a `q-flow` with a decision and a loop edge, not a Mermaid flowchart; asked for
      the same flowchart inside a README, it writes Mermaid

## Scope and non-goals

In scope:

- the `shape` field with box, decision and subprocess; the `flow` link; the `loop` mark and
  self-loops
- layout of loop edges, return-line and self-loop drawing, diamond and double-edged box drawing
- focus, pulse and reduced motion with loop edges
- the "Open flow" drawer button and its missing-target state
- the kit check rules in SC-5, in both the Python check and the JS element
- the text list and the no-script fallback
- the skill's text: `q-flow` for every flowchart on an HTML page, in SKILL.md, the design reference
  and the template rules; the generated components reference; flowchart prompts in the routing evals
- an example page with a checkout flow: a decision, a retry loop, a self-loop poll and a
  subprocess linked to a second graph

Not in scope:

- any other shape (see [Deferred Ideas](#deferred-ideas))
- expanding a subprocess in place, and links to graphs on other pages
- pulses or animation that go around a loop
- value step-through, sequence diagrams and data model diagrams (specs 2 to 4)
- replacing Mermaid inside Markdown, or for state, sequence or ER diagrams

## Success criteria

- An eval of flowchart prompts shows the agent choosing `q-flow` for a flowchart on an HTML page,
  including ones with a decision and a retry, and Mermaid for the same flowchart inside Markdown.
- Verify screenshots of the checkout example at 375px and 1280px in both themes show a diamond with
  labelled exits, a return line for the retry, an arc for the poll, and a double-edged subprocess.

## Decisions Locked

Shapes:

- Nodes get an optional `shape` field: "box" (the default), "decision" or "subprocess". Shape is
  independent of `kind`.
- A decision is a diamond sized to fit a short question of up to two lines. Its kind color is the
  diamond's outline accent. Each exit's label is the answer.
- A subprocess is the box with double vertical edges. It may name `flow`, the id of another `q-flow`
  on the same page; its drawer then gets an "Open flow" button that scrolls to that graph and fits
  it. With no `flow` it is only a visual marker.
- Only decision, loop and subprocess are in this spec, chosen from a longer list of shapes.

Loops:

- The agent marks the return edge with `loop: true`. The element doesn't detect cycles on its own.
- The layout treats a loop edge as running backwards, by turning it around before layout and drawing
  it in its true direction.
- A loop edge is a distinct return line routed around the steps it passes, with a return marker and
  its label.
- An edge from a node to itself is a loop automatically and draws as a small return arc with its label
  beside it.

Focus and pulse:

- The upstream and downstream walk ignores loop edges.
- Loop edges touching the lit path light with it. This spec reads "touching" as both ends lit (SC-7).
- Pulses travel forward edges only, never loop edges.
- Reduced motion is unchanged.

Text list and check:

- The text list and the no-script fallback read decisions as "Paid? (decision): Yes → Ship, No →
  Retry queue", loops as "↩ returns to Charge worker: retry up to 3x", and name a subprocess's linked
  flow.
- The JS parse and the Python check stay in step. They fail on an unknown shape, a decision with fewer
  than 2 exits, an unlabelled decision exit, `flow` on a node that isn't a subprocess, a `flow` naming
  no graph on the page (Python checks the page; JS reports it in the drawer), and a non-boolean
  `loop`. They warn on a decision label over about 24 characters, two exits of one decision sharing a
  label, and a cycle with no edge marked loop.

Choosing and scope:

- `q-flow` becomes the tool for every flowchart on an HTML page. Mermaid keeps diagrams inside
  Markdown, state charts, and sequence and ER diagrams until specs 3 and 4 ship.
- The work is four specs built one at a time: this one, then value step-through, then a sequence
  diagram element, then a data model element.
- Sequence and data model diagrams become new interactive kit elements in the `q-flow` mould, not
  modes of `q-flow` or a wrapper around Mermaid.
- Value step-through will work in `q-flow` and the sequence element, sharing one trace format.

## Industry Insights

Research run 2026-10-17 during the brainstorm, with web search and page fetches only (Brave search
was unavailable).

- **Cycle breaking decides what a loop looks like, and engines differ.** Dagre reverses the edge a
  depth-first search finds closing a cycle; ELK reverses a different one, so the same two-node cycle
  swapped layers between engines
  ([zombie-mermaid #1794](https://github.com/dfadler/zombie-mermaid/issues/1794)). Treat
  engine-difference claims as version-specific; that issue was revised after Mermaid 12.
- **ELK's cycle-breaking options choose which edge reverses, and none is right for every graph.**
  GREEDY, the default, minimises reversed edges with random tie-breaks; DEPTH_FIRST reverses edges
  that lead back to visited nodes; layer constraints and edge priorities also change direction
  ([Eclipse ELK, Layered, 2025](https://eclipse.dev/elk/blog/posts/2025/25-08-21-layered.html)).
- **Cycles through groups create detours.** ELK routed a reversed edge into a subgraph's input side,
  and changing presets only moved the detour. Writing the return edge reversed removed the cycle and
  cut total edge length from 1,217 px to 616 px in the reporter's test
  ([mermaid #8302](https://github.com/mermaid-js/mermaid/issues/8302)). This is the basis for turning
  loop edges around before layout.
- **Wide fan-outs need port-aware ordering** so a switch's branches keep their order and don't cross
  ([interlock #85](https://github.com/dgca/interlock/issues/85)).
- **Diamonds hold less text than their bounding box.** Keep the question short, put the answers on
  the exits, and label every exit
  ([GraphMake, flowchart best practices](https://graphmake.com/blog/flowchart-best-practices); search
  summary only, and the geometry point is the researcher's inference).
- **Shape sets in other tools.** Mermaid has the widest set: decision, cylinder, subroutine
  (subprocess), document, fork and join, terminal, delay and person, and draws loops as plain
  back-edges with no queue shape
  ([Mermaid flowchart docs](https://github.com/mermaid-js/mermaid/blob/develop/docs/syntax/flowchart.md)).
  D2 adds queue and stored data ([D2 shapes](https://d2lang.com/tour/shapes/)). BPMN marks a
  subprocess with a + and a call activity with a thick border
  ([Heflo](https://www.heflo.com/blog/bpmn-notation), [Creately](https://creately.com/guides/bpmn-symbols/)).
  draw.io's general library has only rectangle, rhombus and ellipse
  ([draw.io guide](https://drawio-app.com/blog/flowchart-symbols-all-you-need-to-know/)).
- **Which shapes get used.** No usage survey was found. The researcher's judgment is that rectangle,
  diamond, terminal, cylinder, document, subprocess and person cover most software diagrams.
- **SVG `<desc>` is read unreliably by screen readers, while `<title>` is read by all five tested**,
  which backs keeping the text list as the full account of the graph
  ([a11y.cafe](https://a11y.cafe/posts/svg-screen-readers)).

## Deferred Ideas

Shapes and edge types left out of this spec, all offered during the brainstorm:

- start and end (pill), with success and failure ends
- data store (cylinder)
- queue or topic
- person or external actor
- document or file
- parallel fork and join (bar)
- wait or timer
- error or failure edges drawn in a danger style

Later specs, each with its own brainstorm when this one ships:

- spec 2: value step-through for `q-flow`, with a trace format the sequence element will reuse
- spec 3: an interactive sequence diagram element
- spec 4: an interactive data model element

Separate work:

- expanding a subprocess in place inside its graph
- subprocess links to graphs on other pages
- the toolbar covers the top nodes of a graph at 375px

Build-only questions for the tech spec:

- `[tech-spec]` How the return line is routed around the steps it passes, and where its return marker
  sits.
- `[tech-spec]` How the diamond is sized from the measured question, and how ELK is told its size and
  where its exits leave.
- `[tech-spec]` How the self-loop arc is drawn, since ELK gives it no route.
- `[tech-spec]` How the kit check finds the page's `q-flow` ids, and whether that needs a new rule.
- `[tech-spec]` How the check finds cycles with no loop edge.

## Glossary

- **shape**: what role a node plays in the flow: box, decision or subprocess. Separate from kind.
- **decision**: a diamond node holding a short question, whose outgoing edges are its answers.
- **exit**: one outgoing edge of a decision; its label is the answer.
- **subprocess**: a double-edged box for a step that is a process of its own.
- **linked flow**: the other `q-flow` on the page a subprocess names with `flow`.
- **loop edge**: an edge marked as returning to an earlier step; drawn as a return line.
- **self-loop**: an edge from a node to itself; always a loop.
- **forward edge**: any edge that isn't a loop. Focus and pulses use forward edges only.
- **return line**: how a loop edge is drawn: routed around the steps it passes, with a return marker.

## Status & amendments

**Status**: Approved · Tech spec: authored (`tech.md`; tier gate fired: crosses subsystem boundaries and touches >3 source files)

**Amendments:**

- 2026-10-17: the example page's linked subprocess is "Pay another way", not a refund. The
  report explainer is about payment retries, so its subprocess opens the pay-another-way graph;
  "refund" in the scope line was illustrative. Raised in the final review.
