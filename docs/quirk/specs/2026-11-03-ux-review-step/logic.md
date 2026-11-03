# Logic spec: UX review step with clickable mocks

## Status & amendments

**Status**: Draft

**Amendments:** none.

When a brainstorm involves UI, `quirk:brainstorming` gains a **UX review** step. After the user picks an approach, the agent builds a full clickable mock of it, and the user clicks through, pins comments on elements and signs off before any design section is written. The signed-off mock is committed next to the logic spec, and the build is checked against it. Brainstorms with no UI are unchanged.

## Conceptual model

The UX review is a checklist step between *Propose approaches* and *Present design*. It runs only for UI work, so the design sections are written against screens the user has already clicked through.

It is made of five things:

- **Screen inventory.** The screens of the chosen approach, each with its purpose, its states (default, empty, loading, error, plus any the approach adds), and the repo component each main element would use. Elements with no matching component are **gaps**. The agent writes the inventory before the mock. The inventory is also the checklist behind "every screen reachable" and "the spec cites every screen".
- **Mock.** One HTML file per version (`v1`, `v2`, ...), covering every screen in the inventory in each of its states.
- **Harness.** A quirk-owned script the companion injects into whatever mock it serves. It owns all review UI: mode toggle, screen rail, state switcher, viewport toggle, version picker, change highlights, pins and the verdict bar. Mocks hold only product screens, so every mock gets the same review UI no matter who wrote it.
- **`mock-review` step.** A new companion step kind that shows one mock version inside the harness and collects the verdict.
- **Pins.** Comments anchored to a version, a screen, a state and an element. Each pin is an ordinary companion comment thread, so `reply` and resolve work as they do today.

The step ends when the user picks **Looks right** (signed off) or **Skip review** (logged as not done). **Needs changes** starts another round. There is no round cap.

## Data flow

1. **Detection.** At the existing domain-detection step, the agent decides whether the work adds or changes UI (see [When it runs](#when-it-runs)). If it does, the agent says so once in the chat and adds a *UX review* stage to the rail.
2. **Inventory and v1.** After the approach is picked, the agent writes the screen inventory, then mock `v1`. While it builds, the status line names its progress, for example *Building mock: 3 of 5 screens*.
3. **Review.** The agent sends a `mock-review` step. The user clicks through in Interact mode and pins comments in Comment mode. Pins reach the agent the way comments do today, at any time while the step is open.
4. **Verdict.** On *Needs changes*, every open pin and an optional overall comment come back as one batch. The agent replies in each pin's thread with one of three outcomes: changed, declined with a reason, or carried as an open question. It then writes `v(N+1)`, records which elements it changed, and sends a new `mock-review` step. The loop repeats until *Looks right* or *Skip review*.
5. **Hand-on.** On *Looks right*, the final version, the inventory and the pin history are kept for the spec (see [What the signed-off mock feeds](#what-the-signed-off-mock-feeds)), and the brainstorm moves on to design sections, which cite screens by name.

## Key decisions and rationale

- **After the approach, before design.** UX problems surface before any text design is approved, and design sections can point at screens instead of describing them. A mock built at the end would reopen approved sections.
- **Automatic when UI is detected, skippable anytime.** A UI brainstorm shouldn't depend on someone remembering a flag. *Skip review* is the user's only hard constraint, so it is on screen at every point.
- **Neutral house style with real content.** Research shows polished, branded mocks pull review toward color and typography and away from flow. Grey-box wireframes under-sell hierarchy and density. House style reads as a mock while still showing real content.
- **Navigation plus key interactions, never a working app.** That is enough to judge flow and feel. A fake app with persistent data costs more and tempts reuse of mock code.
- **A state switcher on every screen.** Happy-path mocks are where builders fill gaps by guessing, so states are part of the mock. Any state a screen skips is listed on that screen.
- **Components mapped, gaps flagged.** Mocks that invent components the repo lacks are a known source of drift. Naming the component per element, and turning gaps into open questions, keeps that visible.
- **The harness is quirk's, not the mock's.** Written and tested once, it keeps the review UI consistent and keeps mocks small. Agent-stamped `data-pin` keys anchor pins far more reliably than CSS paths, according to the pin-anchoring research.
- **Pins never move silently.** When an element is gone in a newer version, its pin is marked orphaned instead of re-anchoring onto a neighbour, which is the failure the research found in shipping tools.
- **No round cap.** The user chose to revise until sign-off. Skip review is the way out.
- **The mock is the visual target, rebuilt and never lifted.** Execution treats it as the UX source of truth wherever the text is silent, and checks it through acceptance items. Mock code never ships, because prototype code tends to leak into production and the house-style mock isn't built from the repo's components.
- **The mock writing follows writing-html-artifacts' tier rule.** Tier 1 (kit plus Alpine, no build) by default, and tier 2 (React bundled to one file) only when a screen's interaction needs it. Node is not a hard constraint, but tier 1 avoids build failures on the common path.

## Behavior and scenarios

### Main path

1. **SC-1 A non-UI brainstorm is unchanged**
   - **Given** a brainstorm whose work adds an API endpoint and no screens
   - **When** domain detection runs
   - **Then** ✓ no UX review stage, question, chat line or mock appears; ✓ the checklist goes from approaches straight to design

2. **SC-2 UI is detected**
   - **Given** a brainstorm for "add a saved-exports page"
   - **When** domain detection runs
   - **Then** ✓ the rail gains a UX review stage between Approaches and Design; ✓ the chat says once that a clickable mock comes after the approach pick and can be skipped from the review screen; ✗ no opt-in question is asked

3. **SC-3 A generated page counts as UI**
   - **Given** a brainstorm for "add an HTML coverage report"
   - **When** domain detection runs
   - **Then** ✓ it counts as UI and runs the UX review; a brainstorm that only changes CLI output does not

4. **SC-4 The first mock arrives**
   - **Given** the user picked an approach for the saved-exports page
   - **When** the agent builds the mock
   - **Then** the agent writes the screen inventory, then `v1`, showing build progress in the status line; ✓ the `mock-review` step opens with the rail listing every inventory screen as not visited
   - **Screen inventory:**

     | Screen | States | Main elements and components |
     |---|---|---|
     | Exports list | default, empty, loading, error | table (DataTable), New export (Button) |
     | Saved exports | default, empty | list (List), New export (Button) |
     | New export dialog | default, error | date range (gap: no DateRangePicker), format (Select) |
     | Export detail | default, loading | summary (Card), Download (Button) |

5. **SC-5 Reviewing a screen**
   - **Given** `v1` is open on Saved exports
   - **When** the user flips the state switcher to empty, sets the viewport to mobile, turns on Comment mode and clicks the New export button
   - **Then** ✓ the frame shows the empty state at mobile width; ✓ hovering in Comment mode outlines the button and shows "Button"; ✓ the click opens a pin note anchored to that button in the empty state on `v1`
   - **Data before:** **Saved exports** in the rail: visited, 0 pins
   - **Walkthrough:**
     1. The user flips the state to empty: the frame shows "No exports yet"*
     2. The user pins "Put New export at the top on mobile"* on the button
   - **Data after:** **Pin 1**: `v1`, Saved exports, empty, the New export button, open; **Saved exports** in the rail: visited, 1 pin

6. **SC-6 Needs changes**
   - **Given** `v1` has 3 open pins
   - **When** the user picks Needs changes with the overall comment "Closer, mostly mobile issues"*
   - **Then** the agent replies in all 3 threads, writes `v2`, and sends a new `mock-review` step; ✓ in `v2` with Show changes on, changed elements are outlined and each addressed pin shows the reply that resolved it
   - **Data before:** **Pin 1** open; **Pin 2** open; **Pin 3** open
   - **Walkthrough:**
     1. The user submits Needs changes: all 3 pins and the comment reach the agent as one batch
     2. The agent replies: Pin 1 changed ("moved to the header on mobile")*; Pin 2 declined ("the list order is fixed by the API")*; Pin 3 open question ("retention period")*
     3. The agent writes `v2` with the New export button moved
   - **Data after:** **Pin 1** resolved, changed in `v2`; **Pin 2** resolved as not addressed, with its reason; **Pin 3** carried to design as an open question; **Mock** at `v2`

7. **SC-7 Looks right with unvisited screens**
   - **Given** `v2` is open and Export detail has not been visited
   - **When** the user picks Looks right
   - **Then** ✓ the harness lists Export detail as not visited and asks once to confirm; on confirm the review is signed off

8. **SC-8 Every pin needs an outcome before sign-off**
   - **Given** the user pinned a comment on `v2` and the agent has not replied yet
   - **When** the user picks Looks right
   - **Then** ✓ the agent replies to that pin first, carrying it into design as an open question, then closes the step; ✗ the step never closes with an unanswered pin

### Revisions and pins

9. **SC-9 A pin's element is removed**
   - **Given** Pin 4 sits on the "Filter by date"* chip in `v2`
   - **When** `v3` drops the chip
   - **Then** ✓ Pin 4 stays in its thread marked "element removed in v3"; ✗ it is not moved onto another element

10. **SC-10 A pin survives a layout change**
    - **Given** Pin 1 sits on the New export button in `v1`
    - **When** `v2` moves the button from the footer to the header
    - **Then** ✓ Pin 1 shows on the button in its new place, because the element's key is unchanged

11. **SC-11 Comparing versions**
    - **Given** the mock is at `v3`
    - **When** the user picks `v1` in the version picker
    - **Then** ✓ `v1` shows read-only with its own pins; ✗ a new pin on `v1` is refused; ✓ new pins go on `v3`

12. **SC-12 Skip review mid-round**
    - **Given** the mock is at `v2` with 2 open pins
    - **When** the user picks Skip review
    - **Then** ✓ the brainstorm moves to design; ✓ Decisions Locked records "UX review: skipped at v2"; ✓ the 2 open pins are listed as open questions in the first design section; ✗ nothing is copied to the spec folder

### What the signed-off mock feeds

13. **SC-13 Sign-off reaches the spec**
    - **Given** the user signed off `v3` of the saved-exports mock
    - **When** the logic spec is written
    - **Then** ✓ the mock folder sits next to `logic.md`; ✓ the spec has a Screens section linking each screen and state; ✓ acceptance has one item per screen and state; ✓ every gap is an open question
    - **Spec folder:**

      ```
      docs/quirk/specs/2026-11-03-saved-exports/
        logic.md
        mock/
          mock.html     final version, harness in offline mode, opens from disk
          screens.md    the screen inventory with components and gaps
          review.json   every pin, its reply and its outcome
      ```

14. **SC-14 Execution departs from the mock**
    - **Given** a logic spec with a signed-off mock, and the text says nothing about where New export sits
    - **When** the implementer places New export in an overflow menu instead of the header
    - **Then** ✓ that is a departure from the mock and needs a one-line note in the tech spec or the PR; ✓ the acceptance item for that screen fails until the note exists or the placement matches

### Edges and fallback

15. **SC-15 Terminal flow**
    - **Given** the brainstorm runs with `--terminal`
    - **When** the UX review step starts
    - **Then** the agent writes the mock with the harness inlined in offline mode to the session folder and prints its path; ✓ the state switcher, viewport toggle and screen list work; ✗ comment pins are not available; ✓ the verdict comes through `orca ask` (or `AskUserQuestion`): Looks right, Needs changes with free text, or Skip review

16. **SC-16 A repo with no UI layer**
    - **Given** the repo has no component library
    - **When** the inventory is written
    - **Then** ✓ the components column reads "none (no UI layer)" and no gaps are raised

## When it runs

Work counts as UI when it adds or changes either of these:

- a screen a person uses (web, app or desktop pages, components, dialogs, flows)
- a generated page (HTML reports, dashboards, companion or artifact pages)

Terminal UIs and CLI output don't count.

## What the signed-off mock feeds

- **Design sections.** Written after sign-off, they cite screens by name ("Saved exports, empty") instead of re-describing layouts. Pins carried as open questions are listed in the first design section that touches them.
- **Logic spec.** The rubric gains two requirements whenever a mock was signed off: a Screens section linking each screen and state in `mock/mock.html`, and one acceptance item per screen and state. Gaps become open questions. A skipped review is recorded in Decisions Locked instead.
- **Execution.** Both execution skills treat a signed-off mock as the UX source of truth wherever the text is silent. They rebuild in the project's stack and never lift mock code. A departure needs a one-line note. The existing verification checks the per-screen acceptance items; there is no new screen-diff step.

## What a mock must do

- Use neutral house style with real, specific content. No lorem ipsum and no brand palette.
- Make every inventory screen reachable through the mock's own navigation. A path the mock doesn't build shows a visible "Not in this mock" note instead of a dead end.
- Make key interactions work: dialogs open, tabs switch, and forms accept input and show a canned result.
- Put stable keys on everything a reviewer might comment on: one per screen, one per state variant, and a unique one per meaningful element.
- Reflow at mobile width, because the viewport toggle only changes the frame width.
- Use hash routes only, with no network calls and no real data.

## Scope and non-goals

**In scope:**

- the UX review checklist step and its trigger rule in `quirk:brainstorming`
- a mock-writing guide for the agent
- the `mock-review` step kind, the mock route and the harness in the companion
- the Screens section and per-screen acceptance rule in the logic-spec rubric
- the source-of-truth rule in `quirk:subagent-driven-development` and `quirk:executing-plans`

**Non-goals:**

- teammates reviewing the mock
- export to Figma or other design tools
- an accessibility audit of the mock
- real data or live API calls in a mock
- mocking terminal UIs or CLI output
- a screen-by-screen diff of the built UI against the mock
- publishing mocks as hosted artifacts

## Decisions Locked

**Trigger and placement**
- Placement: after the approach is picked, before design sections
- Trigger: runs automatically when UI is detected; skippable from the review screen
- What counts as UI: screens a person uses, plus generated pages and reports
- Terminal flow: build the mock as a local HTML file; review via chat or `orca ask`

**Mock fidelity**
- Look: neutral house style with real content
- Interaction depth: navigation plus key interactions; unbuilt paths say "Not in this mock"
- States: a state switcher on every screen; skipped states listed
- Components: map mocked elements to real repo components; gaps flagged as open questions

**Review and feedback**
- Comments: pinned to elements; each keeps screen, state and version; sent back as one batch
- Sign-off: one verdict for the whole mock, optional per-screen marks, unvisited screens listed
- Revision rounds: unlimited, until the user signs off
- Showing changes: changed elements highlighted, resolving reply on addressed pins, before/after via the version picker

**What the mocks become**
- Role: the visual target; the spec links each screen and state, and execution treats it as the UX source of truth when the text is silent
- Location: committed next to the logic spec, in `mock/`
- Checking the build: each screen and state is an acceptance item; deliberate departures need a note
- Mock code: never lifted; rebuilt in the project's stack

**Essentials**
- Success criteria: every screen reachable with no silent dead ends; every pin gets a reply or a change; the spec cites every signed-off screen and state; non-UI brainstorms unchanged
- Hard constraint: the user can skip the review at any point
- Out of scope: teammate review, design-tool export, accessibility audit, real data
- Viewports: desktop / mobile toggle on every mock

**Approach**
- One-file mock using the writing-html-artifacts tier rule, plus a review harness the companion injects; a new `mock-review` step; pins are companion comment threads

## Industry Insights

- **Fidelity changes which problems a review finds, not how many.** Lower fidelity keeps review on structure; polished color draws attention away from flow. ([MeasuringU](https://measuringu.com/prototype-fidelity/), [NN/g Mozilla case](https://www.nngroup.com/articles/mozilla-paper-prototype/), [NN/g fidelity](https://www.nngroup.com/articles/ux-prototype-hi-lo-fidelity/))
- **Element-pinned comments sent back as one batch is the pattern that works for AI prototypes.** ([Lovable comments](https://docs.lovable.dev/features/project-comments), [v0 changelog](https://v0.app/changelog), [Figma Make comments](https://help.figma.com/hc/en-us/articles/38701587731735-Add-comments-in-Figma-Make))
- **Pins break across versions, and the dangerous case is silent re-anchoring onto the wrong element.** Stable keys, percentage positions and an explicit orphaned state are the fixes. ([pin anchoring write-up](https://dev.to/imbillal/how-i-keep-feedback-pins-on-the-right-element-when-a-website-changes-3ae7), [self-hosted Marker.io alternative](https://dev.to/neosianexus/i-built-a-self-hosted-alternative-to-markerio-heres-how-it-works-under-the-hood-2i7k))
- **No vendor offers per-screen sign-off**, so it has to be built into the workflow. ([Lovable comments](https://docs.lovable.dev/features/project-comments), [Claude artifact sharing](https://support.claude.com/en/articles/9547008-publish-and-share-artifacts))
- **Happy-path mocks omit loading, empty and error states, and builders fill the gaps by guessing.** ([Miro handoff](https://miro.com/prototyping/design-hand-off/))
- **Mocks drift from the build when they use components the system doesn't have.** ([UXPin design drift](https://www.uxpin.com/studio/blog/design-drift/))
- **Prototype code tends to persist into production**; discard it deliberately. ([Coding Horror: the prototype pitfall](https://blog.codinghorror.com/the-prototype-pitfall/))
- **Screen-by-screen review hides dead ends and missing transitions** that a click-through exposes. ([MeasuringU](https://measuringu.com/prototype-fidelity/), [Overflow on flows](https://overflow.io/blog/storytelling-in-the-design-process/))
- **AI-built web apps often fail to start** (3-38% start failures in WebGen-Bench), which argues for a no-build default. ([WebGen-Bench](https://arxiv.org/html/2505.03733v1), [vite-plugin-singlefile](https://github.com/richardtallent/vite-plugin-singlefile))
- **Sandboxed iframes without same-origin get a "null" origin**, which complicates postMessage; a same-origin route avoids it. ([web.dev sandboxed iframes](https://web.dev/articles/sandboxed-iframes))

## Deferred Ideas

- `[tech-spec]` How the harness is injected (served-time insertion vs. a script tag the mock includes), and the mock route's shape next to `/_quirk/review`.
- `[tech-spec]` How pin positions are stored and re-anchored (key plus percentage offset), and the fallback when a mock lacks keys.
- `[tech-spec]` How the agent records which elements changed between versions, for the highlights.
- `[tech-spec]` How the offline harness mode is built and inlined into the committed `mock.html`.

## Glossary

- **Mock**: one HTML file per version showing every screen of the chosen approach in each of its states.
- **Screen inventory**: the screens, states, component mapping and gaps behind a mock.
- **Harness**: the quirk-owned review UI the companion injects around a mock.
- **Pin**: a comment anchored to a version, a screen, a state and an element.
- **Orphaned pin**: a pin whose element no longer exists in the newest version.
- **Gap**: a mocked element with no matching component in the repo.
- **Offline mode**: the harness without comment pins, used in the terminal flow and in the committed `mock.html`.
