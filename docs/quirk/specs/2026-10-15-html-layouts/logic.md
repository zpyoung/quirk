# Logic spec: page shapes for `writing-html-artifacts`

**Status**: Approved by the user, 2026-10-15 · Tech spec: requested

Pages built by `writing-html-artifacts` get one of seven named shapes, chosen by a `layout` field
that works on every template. Today every tier-1 page is a single column with an optional right
aside, so dense content gets squeezed and runbooks, references and long write-ups have nowhere that
fits. Section 8 of the design reference describes recipes no skeleton builds, so agents either
ignore them or hand-write grid CSS that varies page to page and overflows on phones.

This spec builds on the uncommitted 1440px baseline in the worktree (both skeletons at 1440px, a
sticky report aside, section 8 widths raised). That work is committed on its own before this change
starts. The skill itself is specified in
[the writing-html-artifacts logic spec](../2026-10-13-writing-html-artifacts/logic.md), and the kit
this extends in [the component kit logic spec](../2026-10-14-html-component-kit/logic.md).

## Conceptual model

A **shape** is a named page arrangement, and every page has exactly one:

| Shape | For |
|---|---|
| `report` | findings and evidence; today's page |
| `explainer` | how-it-works pages and write-ups |
| `longform` | long prose with margin notes |
| `tool` | calculators, estimators, converters |
| `comparison` | picking between options |
| `dashboard` | status and metrics |
| `reference` | runbooks and references read by section |

Every shape is made of the same **regions**, and the build places them per shape:

| Region | Written by | Placement |
|---|---|---|
| `summary` (required) | the agent, in a `summary` slot | report, explainer, longform: the answer or findings under the h1. comparison: the recommendation line above the table. tool: the live result beside the inputs. dashboard: the headline metric, top-left. reference: a one-line purpose under the h1 |
| `main` (required) | the agent | the body |
| `nav` | the build, from the page's h2 and h3 headings | a sticky left rail. It appears at 5 or more h2 sections, and always on `reference`, where it is the left pane |
| `aside` (optional) | the agent | sticky on the right, report only, as today |

Inside `main` the agent arranges content with four new kit elements. They are light-DOM elements
styled by CSS attribute selectors, so their geometry never waits on a script:

- **`q-grid`** places children in columns with span attributes. It works in every shape and stacks
  on phones.
- **`q-panel`** is a titled box for one dashboard item. A panel without a title fails the build.
  Charts and tables inside it already carry their table view.
- **`q-sidenote`** is a margin note. On `longform` at wide widths it sits in the right margin.
  Narrower, it becomes a small numbered toggle in the text that opens the note in place. In print it
  is inline.
- **`q-compare`** is the comparison table: options as columns, criteria as rows. On phones it becomes
  one stacked block per option with the recommended one first, and it widens past 1440px when its
  options do not fit.

The existing kit elements (`q-chart`, `q-table`, `q-stat` and the rest) go inside these unchanged.

All shape geometry, breakpoints and print rules live in one shared layout stylesheet in the theme.
Every template inlines it, custom project and user templates included, so every shape works in every
template.

## Data flow

1. **Choosing.** The agent picks a template as today, then infers a shape from the direction brief.
   Before building, it names the template, its level, the tier and the layout, so the user can
   override any of them.
2. **Authoring.** The agent writes `"layout": "<shape>"` in the source header, a `summary` slot and a
   `main` slot (plus `aside` on a report). The companion's `screen.json` and the tier-2 app's
   `quirk-app.json` take the same field.
3. **Building.** The build checks the layout name and that `summary` is present. It generates the nav
   when the page qualifies, emits the regions in the shape's own DOM order (nav before main on
   `reference` and on pages with a nav rail, so tab order matches what the reader sees), tags the
   page with the shape, and inlines the layout stylesheet. It records the layout in the built page's
   header, as it does library versions.
4. **Rebuilding.** A rebuild uses the source's `layout` field, then the layout recorded in the built
   page's header. A page built before this change has neither and rebuilds as `report`, unchanged.
5. **Checking.** The kit check covers the four new elements. A new layout check fails the build when
   the page's own CSS sets layout by hand (grid templates, fixed widths) and names the kit element to
   use instead.
6. **Verifying.** Verify runs at 375px and 1280px as today.
7. **Tier 2.** The app scaffold gets a layout component that emits the same regions and uses the same
   stylesheet, so an app page and a tier-1 page of the same shape look alike.

## Key decisions and rationale

- **One `layout` field on every template, not a template per shape.** Seven shapes across four
  templates stays one switch instead of 28 templates, and branded custom templates get every shape
  for free.
- **The build emits the regions; one stylesheet places them.** Tab order and screen readers follow
  the DOM, not the visual grid, and some shapes need the nav before main while others need it after.
  Emitting regions per shape gets the order right by construction, and phones and print fall back to
  plain document order.
- **Layout elements are CSS-only.** Custom elements that lay themselves out with a script flash on
  load, and the usual fix (hide until defined) leaves the page blank when scripts fail. Attribute
  selectors avoid both.
- **Hand-written layout CSS fails the build.** Agents re-deriving grid CSS per page is the main
  source of inconsistent spacing and 375px overflow. Named elements with built-in stacking remove
  the reason to write it.
- **The summary is a required slot the skeleton places.** Section 8 already says where each shape's
  summary goes; making it a slot means the agent cannot misplace or skip it.
- **The nav is generated from headings.** It always matches the page, works with scripts off, and
  prints.
- **Inference with a recorded result.** The agent picks the shape so most pages get a fitting one
  without the user asking, and the recorded layout keeps rebuilds from reshaping a page after a small
  edit.

## Behavior and scenarios

### Each shape at desktop width, on a phone, and in print

| Shape | Desktop (1280px and up) | Phone (375px) | Print |
|---|---|---|---|
| `report` | 1440px column, prose at 70ch, sticky aside on the right from 900px | aside follows main | one column, aside inline |
| `explainer` | summary, then prose with full-width figures; nav rail on the left at 5+ h2s | an "On this page" menu under the summary | nav as a list under the summary |
| `longform` | as explainer, plus `q-sidenote`s in the right margin | notes become numbered toggles in the text | notes inline |
| `tool` | inputs on the left, the result (summary) beside them from 900px, inside 1440px | result directly below the inputs | one column |
| `comparison` | recommendation line, then `q-compare`; 1440px unless the options do not fit | one stacked block per option, recommended first | one column of blocks |
| `dashboard` | fluid width; headline metric top-left; `q-grid` of titled panels, 4 across up to about 1800px, then 5 or 6 | panels stack | one column |
| `reference` | section list as the left pane, always; content on the right | a collapsed "Sections" menu at the top | the section list, then the content |

Every shape uses the same spacing rhythm. Above its cap, every capped shape centers. All shapes print
light, whatever theme the reader has on, with the theme toggle and data picker hidden.

### The nav

- It lists h2 sections with their h3s nested, using the heading text as the label.
- It appears at 5 or more h2 sections. The agent can force it on or off in the source header.
- When the rail is taller than the screen, it scrolls on its own.
- It marks the section being read with weight and an indicator, not color alone, and screen readers
  hear which link is current.

### Edge cases

- **Unknown layout name:** the build exits 2 and lists the seven shapes.
- **No `summary` slot:** the build fails and says where the summary goes for that shape.
- **A `q-panel` without a title:** the kit check fails.
- **`grid-template-columns` or a fixed width in the page's own `<style>`:** the layout check fails and
  names `q-grid`.
- **An explainer with 4 h2 sections:** no nav unless the header forces it.
- **A comparison with more options than fit at 1440px:** the table widens past 1440px instead of
  scrolling sideways.
- **A dashboard on a 2560px screen:** 5 or 6 panels across.
- **A source with no `layout` field and no built page:** the agent was expected to name one; the build
  uses `report` and the delivery note says so.
- **A custom project template:** every shape works through the shared stylesheet with no change to the
  template.

## Scope and non-goals

In scope, shipped as one change:

- the seven shapes, the `layout` field, inference and the announcement
- the required summary slot and the generated nav
- the shared layout stylesheet and the four kit elements
- the layout check
- print basics: one column, chrome hidden, light theme, nav and notes inline
- all four templates: `report`, `components`, `companion` and the tier-2 `app`
- the design reference, template rules and components reference updated to match

Not in scope:

- slide decks or paged layouts
- choosing a width per section
- page-break design, and print rendering in verify
- adding widths to the token schema

## Success criteria

- Every shape has an example that passes verify at 375px and 1280px in every template.
- A trigger eval of short prompts (for example "a status dashboard for the checkout service", "compare
  these three queues") shows the agent infers the expected shape for each.

## Decisions Locked

**Page shapes**
- Build explainer, tool, comparison and dashboard for real, alongside report.
- Add two new shapes: a two-pane reference and long-form with margin notes.
- Every template gets the shapes: report, components, companion and the tier-2 app.
- Each shape has a required summary slot that the skeleton places.

**Width and density**
- 1440px for every shape except the dashboard, which is fluid.
- The dashboard shows at most 4 panels across up to about 1800px, then 5 or 6.
- The comparison widens past 1440px only when its options do not fit.
- One spacing rhythm for every shape.

**Responsive behavior**
- Comparison on a phone: one stacked block per option.
- Reference on a phone: a collapsed "Sections" menu at the top.
- Margin notes when narrow: numbered toggles in the text.
- Tool on a phone: the result directly below the inputs.

**Packaging**
- A `layout` field on every template, not a template per shape.
- With no field, the agent infers the shape from the direction brief, and names it before building.
- Every shape works in every template, custom ones included.
- The built page records the layout, and rebuilds keep it.

**Building blocks**
- A few named layout elements in the kit, usable in every shape.
- Hand-written layout CSS fails the static check, naming the element to use.
- Dashboard panels require a title; the table view comes from the chart and table elements.

**Long-page navigation**
- A sticky rail on the left at desktop widths.
- Generated by the build from the headings.
- Shown automatically at 5 or more h2 sections, h2 with h3 nested.
- Marks the current section.

**Print**
- The basics only: one readable column, chrome hidden.
- Always light.
- The nav prints as a list under the summary; asides and notes print inline.
- Verify stays screen-only.

**Approach**
- A shared layout layer: the build emits regions per shape, and one stylesheet places them.

## Industry Insights

- Generative-UI tooling in 2026 has mostly settled on allow-listed component catalogs, trading
  coverage for verifiability
  ([awesome-generative-ui](https://github.com/narrowin/awesome-generative-ui),
  [Macaron-V1](https://arxiv.org/pdf/2608.09819)).
- Identical card grids, KPI walls and decorative sparklines are the most-cited tells of AI-built
  dashboards ([Impeccable anti-patterns](https://mintlify.wiki/pbakaus/impeccable/concepts/anti-patterns)).
  Mobile overflow is common: one audit found 75 of 140 dashboard views failing before fixes
  ([llm-systems-manager #1128](https://github.com/llmsyscore/llm-systems-manager/pull/1128)).
- A `1fr` grid track grows with long content unless written as `minmax(0, 1fr)`
  ([CSS-Tricks](https://css-tricks.com/preventing-a-grid-blowout/)). Sticky positioning fails inside
  any ancestor with `overflow` other than visible or clip, and in stretched grid items
  ([Polypane](https://polypane.app/blog/getting-stuck-all-the-ways-position-sticky-can-fail/)).
- Tab order and screen readers follow the DOM, not grid placement
  ([Matuzović](https://www.matuzo.at/blog/the-dark-side-of-the-grid-part-2/)). Unplaced grid items
  fall back to source order, which makes document order a safe reflow and print fallback
  ([W3C C32](https://www.w3.org/WAI/WCAG21/Techniques/css/C32)). An invalid `grid-template-areas`
  value is dropped silently ([Smashing](https://www.smashingmagazine.com/understanding-css-grid-template-areas/)).
- Hiding undefined custom elements to avoid a flash breaks pages when scripts fail, and the spec issue
  is unresolved ([whatwg/html#6231](https://github.com/whatwg/html/issues/6231)). Attribute-only CSS
  on light-DOM elements avoids the upgrade lifecycle
  ([Every Layout](https://every-layout.dev/blog/css-components/)).
- Layout x template composition through copied partials drifts: copied theme files stop receiving
  upstream fixes ([zwbetz](https://zwbetz.com/override-a-hugo-theme/)), and mixing two composition
  mechanisms on one page caused recursive renders in Eleventy
  ([11ty #853](https://github.com/11ty/eleventy/issues/853)).
- Printing a dark theme drops backgrounds and leaves light text on white, measured at 2.3:1 for
  headings ([philipp.fyi #528](https://github.com/philippstorl/philipp.fyi/issues/528)). A print
  reset must cover every theme selector and win on specificity
  ([yomihon #784](https://github.com/Koopa0/yomihon/issues/784)).
- Dashboard grids conventionally use 12 columns; Grafana uses 24
  ([Grafana JSON model](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/view-dashboard-json-model/)).
  Tufte CSS puts sidenotes in the margin on wide screens and behind a toggle on narrow ones
  ([Tufte CSS](https://edwardtufte.github.io/tufte-css/)).

## Deferred Ideas

- Page-break rules per shape, keeping panels, tables and figures whole.
- Swapping charts for their table view in print.
- A print render in verify, with its own screenshot and contrast check.
- A filter bar that drives several panels at once (also deferred in the kit spec).

Open for the tech spec:

- `[tech-spec]` How skeletons expose the regions, and how custom skeletons written before this change
  get them.
- `[tech-spec]` Which CSS properties the layout check treats as hand-written layout, and how it avoids
  false positives on legitimate page CSS.
- `[tech-spec]` Anchor and slug rules for the generated nav, and the header field that forces it on or
  off.
- `[tech-spec]` How the app's layout component shares the stylesheet with tier 1.
- `[tech-spec]` How the companion maps its question onto the summary region.
- `[tech-spec]` The eval's prompt set and how it is scored.

## Glossary

- **Shape**: one of the seven named page arrangements. Set by the `layout` field.
- **Region**: a named part of a page (summary, main, nav, aside) that a shape places.
- **Summary**: the required region holding the one thing the reader needs first; where it sits
  depends on the shape.
- **Nav**: the section list the build generates from headings; a sticky rail, or the left pane on
  `reference`.
- **Layout stylesheet**: the single shared stylesheet in the theme that holds every shape's
  geometry, breakpoints and print rules.
- **Layout check**: the static check that fails a page whose own CSS sets layout by hand.

## Status & amendments

**Amendments:** none.
