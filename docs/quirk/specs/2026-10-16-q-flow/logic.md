# Logic spec: `q-flow`, an explorable graph element for `writing-html-artifacts`

**Status**: Draft, awaiting the user's review

`q-flow` is a kit element that draws a read-only graph of things and the data moving between them,
which the reader can pan, zoom and click through. Agents today have Mermaid, which draws a static
picture: a reader can't follow one path through a 40-node system, open a node to see what it does,
or study one subsystem without the rest. `q-flow` is for those pages. Mermaid stays for static
pictures.

It extends the kit specified in [the component kit logic spec](../2026-10-14-html-component-kit/logic.md)
and fits the page shapes in [the page shapes logic spec](../2026-10-15-html-layouts/logic.md).

## Conceptual model

A **graph** has four kinds of thing, all written by the agent as data:

| Thing | What it is | What the agent gives it |
|---|---|---|
| node | a service, worker, queue, store, person, screen | an id and a label; optionally a kind, a group and a detail |
| edge | data or a call moving from one node to another | the two nodes; optionally a label and whether it is async |
| group | a named box around nodes, which can nest | an id and a label; optionally a parent group |
| kind | a category of node, shown as a small tag and an accent stripe | a free-text name and one of the eight chart colors |

The agent never writes a position. The element lays the graph out itself, left to right by default,
and draws groups as tinted panels with a header. When the agent asks for lanes, the top-level groups
become stages laid across the flow, one band per stage in the order the groups are listed.

The reader explores the graph through **focus**. Focusing a node lights its whole upstream and
downstream path, dims everything else, sends a **pulse** along the lit edges in flow order, and opens
the node's **drawer** with its detail. Focusing a group zooms to it and dims the rest. Nothing on the
graph moves until the reader focuses something.

Every graph also renders as a **text list**: the same groups, nodes, details and edges as a nested
list in a "Graph as a list" disclosure under the canvas. It is the screen-reader and no-script view,
so it always carries everything the canvas does.

## Data flow

1. **Choosing.** The agent reaches for `q-flow` when the reader will explore a graph: follow a path,
   open a node, study one group. It reaches for Mermaid for a static picture, for sequence diagrams
   and state charts, and inside Markdown.
2. **Authoring.** The agent writes a `<q-flow>` tag with a one-sentence `summary` and the graph as
   JSON inside it, then picks `direction` and `groups` if the defaults don't fit.
3. **Building.** The build sees the tag, inlines the graph library (the layout engine, the zoom
   library and the kit's renderer, with their licenses) and runs the kit check over the graph data.
   Pages without the tag carry none of it.
4. **Loading.** In the browser the element measures its labels, lays the graph out, fits it to the
   view and only then shows it. It writes the text list from the same data.
5. **Reading.** The reader pans, zooms, focuses nodes and groups, and opens drawers. The theme toggle
   recolors the graph live.
6. **Verifying.** Verify waits until every graph on the page has finished laying out, then takes its
   screenshots at 375px and 1280px in both themes.

## Key decisions and rationale

- **A plain custom element with its own SVG renderer, on ELK and d3-zoom.** React Flow and Cytoscape
  were the alternatives. Every behavior chosen here (the pulse, focus, the drawer, swimlanes, labels
  placed by the layout engine) is custom work in all three, and React Flow would add a React runtime,
  a second copy of React in tier-2 apps, and a conversion from ELK's nested output into its flat,
  parent-relative model. It also draws its own edge paths, which throws away ELK's routes and label
  positions, and overlapping edge labels are a known React Flow problem with no fix in the library.
  Cytoscape draws to canvas, which hides the graph from the static checks and leaves accessibility
  and theming to us. A plain element keeps `q-flow` behaving like every other `q-*` element in tier 1,
  tier 2 and the companion.
- **Data in, no coordinates.** Hand-placed positions are what agents get wrong. The element owns
  layout, so the agent only states what connects to what.
- **Kinds are free text, declared once per graph with a chart color.** The user wanted kinds free
  rather than a fixed list. Declaring each kind once, against the eight `--q-color-chart-*` colors,
  makes consistency inside a graph structural; consistency across artifacts comes from the skill's
  instructions to reuse kind names and colors.
- **The wheel scrolls the page.** A graph embedded in a long document must never trap the reader
  scrolling past it. Zooming takes Ctrl/Cmd+wheel, a pinch or the buttons.
- **Motion only on focus.** The design reference bans looping and ambient motion. The pulse is the one
  exception, and only while a path is focused and the reader has not asked for reduced motion.
- **The traveling pulse keeps the line's own pattern.** Async edges are dashed and sync edges solid;
  marching dashes would make every animated edge look dashed. The pulse swells the line as it passes
  without changing its pattern.
- **Size up to Mermaid's.** The library is about 1.5 MB, almost all of it the layout engine. The page
  budget for a graph page is anything up to Mermaid's 5.5 MB, with the usual warning above 2 MB.

## Behavior and scenarios

### Authoring and building

1. **SC-1**
   - **Given** an agent writing an explainer page about how orders are charged
   - **When** it writes a `q-flow` with four nodes, one group and three edges, and builds the page
   - **Then** the build inlines the graph library and its license comments, the kit check passes, and
     the page shows the graph laid out left to right with Billing as a tinted panel
   - **Data before:** **Source**: `<q-flow summary="Orders flow from checkout through billing to the ledger.">`
     with kinds "ui" (color 1), "worker" (color 2), "database" (color 3); nodes Checkout (ui), Charge
     worker (worker, in Billing), Ledger (database, in Billing), Retry queue (in Billing); edges
     Checkout to Charge worker "order.created" async, Charge worker to Ledger "charge.settled",
     Charge worker to Retry queue "charge.failed" async
   - **Walkthrough:**
     1. The build finds the `q-flow` tag and inlines the graph library with a license comment for
        each part
     2. The kit check reads the JSON: ids unique, every edge end exists, every kind declared
     3. In the browser, the element measures labels, lays out, fits to view, then shows the graph
   - **Data after:** **Built page**: ✓ graph library inlined once; ✓ license comments present;
     ✓ kit check passed; **Graph on screen**: ✓ Checkout on the left, Billing panel on the right
     holding the other three; ✓ dashed edges for "order.created" and "charge.failed"

2. **SC-2**
   - **Given** a page with no `q-flow` tag
   - **When** it is built
   - **Then** none of the graph library is inlined, and the page's size is unchanged by this feature

3. **SC-3**
   - **Given** a graph whose data breaks the contract
   - **When** the page is built
   - **Then** the build fails the kit check and names the element and the problem, for each case in
     the table
   - **Kit check results:**

     | Graph data | Result |
     |---|---|
     | two nodes with the id "charge" | ✗ fails: duplicate id "charge" |
     | an edge to "ledgr", which no node has | ✗ fails: edge points at unknown node "ledgr" |
     | a node of kind "cache" that `kinds` doesn't declare | ✗ fails: undeclared kind "cache" |
     | nine kinds declared | ✗ fails: at most eight kinds, one per chart color |
     | a group whose parent is itself or its own child | ✗ fails: group nesting loops |
     | `groups="lanes"` and a node outside every top-level group | ✗ fails: in lane mode every node belongs to a lane |
     | a detail containing a script, a form or an external image | ✗ fails: detail may hold only paragraphs, lists, code and links |
     | no `summary` | ✗ fails: summary is required |
     | 75 nodes | ✓ passes with a warning: large graphs read poorly, split into groups or several graphs |
     | 210 nodes | ✗ fails: more than 200 nodes |
     | an edge label of 45 characters | ✓ passes with a warning: edge labels over 30 characters crowd the layout |

4. **SC-4**
   - **Given** a page with two `q-flow` graphs
   - **When** the reader focuses a node in the first
   - **Then** only the first graph changes; each graph keeps its own focus, zoom and drawer

### Reading at rest

5. **SC-5**
   - **Given** a laid-out graph on a long explainer page
   - **When** the page loads
   - **Then** the graph appears already laid out and fitted, its height follows the graph's shape up to
     about two-thirds of the screen, nothing moves, and a corner cluster offers zoom in, zoom out, fit
     and expand

6. **SC-6**
   - **Given** the reader scrolling down the page with the graph in view
   - **When** they turn the mouse wheel over the graph, or swipe one finger over it on a phone
   - **Then** the page scrolls past the graph and the graph doesn't zoom
   - **Input results:**

     | Input over the graph | Result |
     |---|---|
     | mouse wheel | ✓ page scrolls |
     | Ctrl or Cmd plus wheel, trackpad pinch | ✓ graph zooms |
     | click and drag | ✓ graph pans |
     | one finger on a phone | ✓ page scrolls |
     | two fingers on a phone | ✓ graph pans and zooms |
     | zoom buttons, fit button | ✓ graph zooms, or fits to view |

7. **SC-7**
   - **Given** a large graph in the page column
   - **When** the reader presses expand
   - **Then** the graph fills the screen with the same focus and zoom, and Escape or the button returns
     it to the page

8. **SC-8**
   - **Given** the reader toggles the page theme from light to dark
   - **When** the theme changes
   - **Then** the graph recolors at once, kind colors included, with no re-layout and no flash

### Focusing

9. **SC-9**
   - **Given** the orders graph from SC-1 plus a Refund worker in Billing that sends "refund.issued"
     to Ledger, nothing focused
   - **When** the reader clicks Charge worker
   - **Then** Charge worker's whole upstream and downstream path stays lit and the rest dims, a pulse
     travels the lit edges hop by hop in flow order and loops, and the drawer opens with Charge
     worker's detail and its edges
   - **Data before:** **Graph**: nothing focused; drawer closed
   - **Walkthrough:**
     1. The reader clicks Charge worker
     2. The element finds the path: upstream Checkout; downstream Ledger and Retry queue
     3. The pulse runs Checkout to Charge worker, then Charge worker to Ledger and to Retry queue,
        then starts again
   - **Data after:** **Graph**: ✓ Checkout, Charge worker, Ledger, Retry queue lit; ✓ Refund worker
     and its "refund.issued" edge dimmed, because Refund worker is neither upstream nor downstream of
     Charge worker; **Drawer**: ✓ open on the right; ✓ shows "Charge worker", kind "worker", the
     detail, incoming "order.created" from Checkout, outgoing "charge.settled" to Ledger and
     "charge.failed" to Retry queue
   - **Screen states:**

     | Element | Shown |
     |---|---|
     | edges on the path | ✓ full color, pulsing hop by hop; async edges stay dashed, sync edges stay solid |
     | edges and nodes off the path | ✓ dimmed |
     | drawer | ✓ open, beside the graph, not covering Charge worker |

10. **SC-10**
    - **Given** a node focused with its drawer open
    - **When** the reader clicks an edge listed in the drawer, for example "charge.settled to Ledger"
    - **Then** focus moves to Ledger, its path lights, the pulse restarts on Ledger's path, and the
      drawer shows Ledger

11. **SC-11**
    - **Given** a node focused
    - **When** the reader presses Escape, clicks empty canvas, or closes the drawer
    - **Then** focus clears, everything returns to full color, the pulse stops and the drawer closes

12. **SC-12**
    - **Given** nothing focused
    - **When** the reader clicks the Billing group's header
    - **Then** the view zooms to fit Billing, everything outside it dims, nothing pulses, and no drawer
      opens

### Groups as lanes

13. **SC-13**
    - **Given** a left-to-right graph with `groups="lanes"`, top-level groups Intake, Billing and
      Settlement listed in that order, and a group Retries nested inside Billing
    - **When** the page loads
    - **Then** Intake, Billing and Settlement are drawn as bands across the flow, left to right in the
      order listed, each with its name at the top; every node sits in its band; Retries is a tinted
      panel inside the Billing band
    - **Screen states:**

      | Direction | Bands |
      |---|---|
      | `right` (default) | ✓ vertical bands side by side: Intake, then Billing, then Settlement |
      | `down` | ✓ horizontal bands stacked: Intake on top, then Billing, then Settlement |

### Keyboard, motion and phones

14. **SC-14**
    - **Given** a keyboard user tabbing through the page
    - **When** they tab into the graph
    - **Then** focus lands on one node, and the keys work as in the table
    - **Keyboard:**

      | Key | Result |
      |---|---|
      | Tab | ✓ enters the graph on one node, and a second Tab leaves it |
      | arrow keys | ✓ move to the nearest node in that direction |
      | Enter | ✓ focuses the node, as a click does, and announces it, for example "Charge worker, worker, 1 upstream, 2 downstream" |
      | Escape | ✓ clears focus and closes the drawer |
      | + and - | ✓ zoom in and out |
      | 0 | ✓ fits to view |

15. **SC-15**
    - **Given** the reader has reduced motion turned on
    - **When** they focus a node
    - **Then** nothing animates: the path is lit as a thicker static line with arrowheads, and zooms and
      fits jump instead of easing

16. **SC-16**
    - **Given** the orders graph on a 375px phone
    - **When** the reader taps Charge worker
    - **Then** the path lights and pulses as on desktop, and the drawer opens as a bottom sheet over the
      lower part of the graph

### Fallbacks

17. **SC-17**
    - **Given** a reader whose browser runs no scripts
    - **When** the page loads
    - **Then** the canvas shows a one-line notice and the "Graph as a list" disclosure is open, listing
      every group, node, detail and edge

18. **SC-18**
    - **Given** a graph the layout engine fails on
    - **When** the page loads
    - **Then** the canvas shows a one-line notice that the graph could not be drawn, the text list
      opens, and the rest of the page works

19. **SC-19**
    - **Given** a screen-reader user
    - **When** they reach the graph
    - **Then** they hear its summary, can open the text list, and find everything the canvas shows,
      details included

### Other surfaces

20. **SC-20**
    - **Given** a companion screen during brainstorming
    - **When** the agent puts a `q-flow` in the screen's `content`
    - **Then** the user can explore the graph on the screen; a `q-flow` in an option's `html` breaks the
      companion rule against interactive elements in option cards

21. **SC-21**
    - **Given** a tier-2 app
    - **When** a view renders a `q-flow` tag
    - **Then** it behaves as on a tier-1 page, and the built app inlines the graph library only because
      the tag is used

22. **SC-22**
    - **Given** verify running on a page with a graph
    - **When** it takes screenshots
    - **Then** it waits until every graph has finished laying out, so no screenshot shows a blank canvas
      or nodes piled in one corner

## Scope and non-goals

In scope:

- the `q-flow` element: authoring contract, layout, panels and swimlanes, kinds, sync and async edges,
  edge labels, focus, the pulse, the drawer, zoom and pan, expand, keyboard, the text list
- the kit check rules and warnings in SC-3
- the graph library vendored and inlined only on use, with license comments
- tier-1 pages, tier-2 apps and companion screen `content`
- verify waiting for layout
- the skill's text: the q-flow versus Mermaid rule in SKILL.md, the design reference and the companion
  rules; the section 10 motion exception; the generated `q-flow` entry in the components reference;
  the instruction to reuse kind names and colors across artifacts
- one example page per suitable shape

Not in scope:

- editing, dragging nodes, or saving a changed graph
- collapsing groups into a single node
- a minimap, search, or edge clicks
- deep links to a focused node in the URL
- a dedicated print view; printing shows the current view and the text list
- laying the graph out at build time
- reading graph data from the page's data file
- `q-flow` in companion option thumbnails
- replacing Mermaid anywhere it is used today

## Success criteria

- An eval of short prompts shows the agent choosing `q-flow` when the reader will explore a graph and
  Mermaid when a static picture does the job (for example "an interactive map of the billing services
  I can click through" versus "a diagram of the retry flow for this README").
- Verify screenshots of every `q-flow` example show a laid-out graph in light and dark themes, at
  1280px and 375px.

## Decisions Locked

Node, edge and group look:

- Nodes show a label plus a kind tag with an accent stripe (chosen on the companion).
- Groups are tinted panels with a header bar by default; swimlanes are supported, not the default
  (chosen on the companion, with the note "Swimlanes should be a supported option but not the
  default").
- In lane mode, groups nested inside a lane are drawn as tinted panels inside it.
- Lanes run across the flow, as stages: vertical bands in a left-to-right graph. Chosen after research
  showed ELK partitions only along the flow axis; lanes running with the flow would need custom
  routing with no precedent found.
- In lane mode every node belongs to a lane, and lanes appear in the order their groups are listed —
  assumed default, required for ELK to guarantee the band order.
- Kinds are free-form text; the agent is told to keep kinds and colors consistent.
- Each kind is declared once per graph with a color from the fixed chart palette.
- Layout runs left to right by default, with a `direction` attribute for top to bottom.
- Edge labels are always shown and kept short.
- Edges are solid for sync and dashed for async.

Interaction model:

- Node detail opens in a drawer inside the canvas, a bottom sheet on phones (chosen on the companion).
- Clicking a node focuses its path and opens the drawer in one action.
- Focus reaches everything upstream and downstream.
- The wheel scrolls the page; Ctrl/Cmd+wheel, pinch or buttons zoom.
- An expand button opens the graph full-screen.
- Clicking a group header zooms to the group and dims the rest.
- Node detail is short HTML: paragraphs, lists, code, links.

Data-flow animation:

- The animation is a traveling pulse that swells the line and keeps its solid or dashed pattern
  (chosen on the companion over a traveling dot, marching dashes, a highlight sweep and a dot riding a
  pulse; the pulse and the combined option were added at the user's request).
- Edges pulse only on the focused path.
- The pulse loops while the path stays focused.
- The pulse moves hop by hop in flow order.
- With reduced motion, the focused path is a thicker static line with arrowheads.

Scope and approach:

- Done means the routing eval and the verify screenshots in Success criteria.
- Page weight may go up to Mermaid's size.
- `q-flow` works on tier-1 pages, in tier-2 apps and in companion screen content.
- Above about 60 nodes the build warns; above about 200 it fails.
- Approach: a plain custom element with its own SVG renderer, ELK for layout and d3-zoom for zoom and
  pan.
- Reader behavior, keyboard model, group focus without a pulse, touch gestures and the fallbacks were
  approved as presented in the design.
- The design approved a warning on long edge labels; the 30-character threshold is an assumed default.

## Industry Insights

Phase A and B research, run 2026-10-16 with web search only (Brave search was unavailable in the
session). Sizes and licenses were measured locally with esbuild from the npm packages.

- **Measured sizes, minified as they would be inlined:** ELK 0.12.0 about 1.46 MB; React, ReactDOM
  and React Flow 12.12.0 about 376 KB plus 19 KB of CSS; Cytoscape 3.34.3 about 444 KB; d3-zoom and
  d3-selection about 48 KB. ELK dominates every option.
- **ELK is EPL-2.0 (or GPL-3.0-or-later).** The vendored Mermaid 12.2.0 bundle already contains ELK
  code, so the skill ships EPL code today.
- **ELK does not measure text.** Layout needs measured node and label sizes first, and a graph shown
  before layout settles puts every node at the origin
  ([Stately cookbook](https://stately.ai/docs/packages/graph/react-flow-elk-pipeline),
  [knowledge-transfer gist](https://gist.github.com/PCoelho/8496d811ef9c0c66526e2d9cc316c7a2)).
- **Edges belong to the lowest common ancestor of their ends** in ELK's model; a mis-contained edge
  renders badly and its label lands at the origin
  ([ELK graph data structure](https://eclipse.dev/elk/documentation/tooldevelopers/graphdatastructure.html),
  [elkjs #138](https://github.com/kieler/elkjs/issues/138)).
- **Cross-group edges need ELK's include-children hierarchy mode**, which has older reports of broken
  layering and routing; test cross-group edges early
  ([eclipse-elk #700](https://github.com/eclipse-elk/elk/issues/700),
  [elkjs #112](https://github.com/kieler/elkjs/issues/112)).
- **Overlapping edge labels have no fix in React Flow**; a maintainer suggested a custom label layer
  ([xyflow #819](https://github.com/wbkd/react-flow/issues/819)). ELK places labels itself when given
  their sizes ([ELK layered reference](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html)).
- **Dash-offset edge animation is a CPU bottleneck** at hundreds of edges; teams animate only
  highlighted edges with a custom animation
  ([Liam ERD](https://liambx.com/blog/tuning-edge-animations-reactflow-optimal-performance)).
- **Embedded diagrams should not capture the wheel**; React Flow's defaults do, and the advice is to
  turn that off and offer buttons ([React Flow API](https://reactflow.dev/api-reference/react-flow)).
  d3-zoom's default filter also zooms on a plain wheel, so it needs a custom filter
  ([d3-zoom](https://d3js.org/d3-zoom)).
- **Graph libraries give only partial screen-reader support**; the pattern that works is a short label
  plus a full text description beside the canvas
  ([Synergy Codes](https://www.synergycodes.com/webbook/building-usable-and-accessible-diagrams-with-react-flow),
  [W3C complex images](https://w3c.github.io/wai-tutorial-images/tutorials/images/complex/)).
  Keyboard focus across composite widgets favors a roving tabindex
  ([W3C APG](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/)).
- **Cytoscape is canvas-only for a11y and theming**: accessibility is app-level and dark mode is a
  JavaScript restyle ([discussion #3125](https://github.com/cytoscape/cytoscape.js/discussions/3125),
  [issue #3328](https://github.com/cytoscape/cytoscape.js/issues/3328)); cytoscape-elk depends on
  elkjs 0.3 ([cytoscape-elk](https://github.com/MarshallChen/cytoscape.js-elk)).
Phase C deep research on drawing ELK output to SVG, run 2026-10-16:

- **ELK partitions order along the flow axis**, so they give stages across the flow, not lanes
  running with it, and ELK draws no band geometry; band order is guaranteed only when every node has
  a partition ([partitioning.activate](https://eclipse.dev/elk/reference/options/org-eclipse-elk-partitioning-activate.html),
  [partitioning.partition](https://eclipse.dev/elk/reference/options/org-eclipse-elk-partitioning-partition.html)).
  Nested groups inside partitions have no documentation or reports (unverified).
- **Coordinates:** shapes are relative to their parent and edge points to the edge's container; the
  JSON options can return absolute coordinates instead
  ([coordinate system](https://eclipse.dev/elk/documentation/tooldevelopers/graphdatastructure/coordinatesystem.html),
  [edgeCoords](https://eclipse.dev/elk/reference/options/org-eclipse-elk-json-edgeCoords.html)).
- **An open ELK bug** throws on include-children layouts with fixed port constraints; free ports
  avoid it ([eclipse-elk #1192](https://github.com/eclipse-elk/elk/issues/1192)).
- **Layout time is small at this scale:** under about 120 ms below 150 nodes in one measured DAG,
  with no compound nodes or labels ([PostHog PR](https://github.com/PostHog/posthog/pull/73408)).
- **Measure after fonts load**, in an unscaled container, or sizes come out stale
  ([tldraw text measurement](https://tldraw.dev/sdk-features/text-measurement)).
- **Touch:** d3-zoom never sets `touch-action`; one-finger page scroll with two-finger pan needs CSS
  and a filter, and `touch-action: none` would block browser zoom for low-vision readers
  ([d3-zoom source](https://raw.githubusercontent.com/d3/d3-zoom/main/src/zoom.js),
  [MDN touch-action](https://developer.mozilla.org/en-US/docs/Web/CSS/touch-action),
  [OpenLayers two-finger example](https://openlayers.org/en/latest/examples/two-finger-pan-scroll.html)).
- **Keyboard:** a roving tabindex on node elements gives real focus, and the zoom must pan to the
  focused node because browser focus only scrolls the page; GoJS pairs arrow-key neighbors with a
  live region ([GoJS accessibility](https://gojs.net/latest/learn/accessibility)).
- **The pulse repaints each frame**, because only transform and opacity animate off the main thread;
  animating a mask rather than the edge keeps the cost to the focused path
  ([Motion SVG animation](https://motion.dev/docs/svg-animation)).

- **Read-only viewers to learn from:** Structurizr's viewer keyboard model (zoom keys, fit, step
  through) ([Structurizr viewer](https://docs.structurizr.com/server/diagrams/viewer)); Sprotty
  renders ELK output to SVG with zoom limits and keyboard guidance
  ([Sprotty best practices](https://sprotty.org/docs/concepts/best-practices/)).

## Deferred Ideas

Build-only questions for the tech spec:

- `[tech-spec]` How the graph library is vendored: an esbuild bundle in `scripts/vendor-build/`, its
  pin and checksum, and one license comment per part (ELK EPL-2.0, d3 ISC, kit code).
- `[tech-spec]` How the companion serves the library: from the companion server like Mermaid, or
  inlined in the screen.
- `[tech-spec]` How a tier-2 build detects the tag and inlines the library, alongside the existing
  Chart.js and highlight.js detection.
- `[tech-spec]` ELK settings: layered algorithm, hierarchy mode for cross-group edges, partitioning for
  lanes, edge-label placement and spacing, and whether layout runs on the main thread or a worker.
- `[tech-spec]` The measure-then-lay-out loop, including fonts that load late.
- `[tech-spec]` The readiness signal verify waits on.
- `[tech-spec]` The pulse implementation (mask, Web Animations or SMIL) and its cost with many
  focused edges.
- `[tech-spec]` The d3-zoom filter for wheel, modifier and touch behavior.
- `[tech-spec]` How the graph data sits in the tag (a JSON script child or another form) and how the
  kit check parses it.
- `[tech-spec]` Coordinate frames from ELK (absolute output or per-container conversion), port
  constraints that avoid ELK bug #1192, and the node-placement strategy by graph size.
- `[tech-spec]` Band geometry for lanes, derived from member extents, and whether nested groups lay
  out correctly inside partitions; prove it early with a test graph.
- `[tech-spec]` Touch handling: `touch-action` and the two-finger filter, tested on real devices.
- `[tech-spec]` Keeping the focused node in view as the keyboard moves focus.

Product ideas left out of this version: collapsing groups, a minimap, search, edge clicks, deep links
to a focused node, a print view, build-time layout, reading graph data from the page's data file, and
lanes that run along the flow (classic team swimlanes).

## Glossary

- **graph**: one `q-flow` element and its data.
- **node**: one thing in the graph, such as a service or a store.
- **edge**: an arrow from one node to another, for a call (sync) or a message (async).
- **group**: a named box around nodes; groups can nest.
- **lane**: a top-level group drawn as a band across the flow, a stage, in lane mode.
- **kind**: a free-text category of node with one chart color, declared once per graph.
- **focus**: the state where one node's path, or one group, is highlighted and the rest dimmed.
- **path**: everything upstream and downstream of a focused node.
- **pulse**: the swelling of a lit edge that travels in flow order while a path is focused.
- **drawer**: the panel inside the canvas that shows a focused node's detail and edges.
- **text list**: the "Graph as a list" disclosure that carries the whole graph as text.

## Status & amendments

**Status**: Draft, awaiting the user's review

**Amendments:** none yet.
