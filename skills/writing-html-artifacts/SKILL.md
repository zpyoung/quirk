---
name: writing-html-artifacts
description: Use when the user asks for HTML, a web page, an interactive tool, a dashboard or report as a page, or an offline single-file artifact, or when an answer would read better as a page and you want to offer one. Builds a styled self-contained page from a template, checks it, and hands it over with a delivery note. Also runs the brainstorming visual companion, the local page that asks one question at a time.
---

# Writing HTML artifacts

Build one self-contained HTML file from a template, check it, and hand it over with a short note. Never open or publish it unasked.

`SKILL_DIR` is the directory holding this `SKILL.md`, which the host shows when the skill loads. Every command below is run as `python3 "$SKILL_DIR/scripts/<script>.py" ...`. Do not build paths from a plugin-root environment variable: not every host sets one. Each command prints exactly one JSON object to stdout and sends diagnostics to stderr.

## When to use it, and when to offer

Build a page when the user asks for HTML, a web page, an interactive tool, a dashboard or report as a page, or a single file that works offline. Stay in Markdown when the answer is short, will be pasted into a ticket or chat, or the user asked for a file format such as `.md`, `.docx` or `.pdf`. The full rule is in [design reference](references/design-reference.md) section 1.

- **Offer, do not build, when an answer has shape.** A comparison, a dashboard, a flow, or a table someone will sort is better as a page. Finish the answer in text, add one line offering a page, and build only on a yes.
- **Not for these:** editing an existing app's components, publishing an existing artifact somewhere, slide decks, or diagrams that live inside a Markdown document.
- **Do not open or publish the result.** Deliver the path and the note. Opening it and publishing it are the user's calls.

## Workflow

Follow the steps in order. Each one leads with its rule.

1. **Pick a template.** Run `quirk_html.py templates list` and match the request against each `description` (all start "Use when"). The user can name a template directly. If `warnings` lists a skipped template, say so in the delivery note; see [templates](references/templates.md) for what to do.
2. **Pick the tier.** Tier 1 is the default: one source file assembled into one page. Choose tier 2 (a React project bundled to one file, the `app` template) when the request shows one of these signals, or when you state a judgment that it needs one:
   - multiple views or routes
   - an editable data grid
   - state shared across views
   - the user asks for an app

   Record the signal; it goes in the header and the delivery note. A page that only filters, sorts or toggles stays tier 1.
3. **Write the direction brief.** Three lines in your reply, not in the page: subject and audience, one job, one specific detail only this subject has. The format and why are in [design reference](references/design-reference.md) section 2. Read that whole reference before filling a slot.
4. **Pick the layout, and name your choices.** Infer the page shape from the brief (see [Page shapes](#page-shapes)). Before building, tell the user the template, its level (`project`, `user` or `builtin`), the tier and the layout in one line, so they can override any of them.
5. **Write `<slug>.src.html`.** Line 1 is the header comment with the `layout` field, then one `<!-- slot: name -->` line per slot, `summary` and `main` among them. The exact format, header fields and slot rules are in [templates](references/templates.md). Use the `--q-*` tokens, and declare every interaction in `interactions`.
6. **Build it.**

   ```
   python3 "$SKILL_DIR/scripts/quirk_html.py" build SRC.src.html [--out FILE] [--upgrade] [--project-dir DIR]
   ```

   The page lands at `<project>/.quirk/html/<slug>.html` unless `--out` says otherwise. That directory ignores itself in git.
7. **Fix static-check failures.** `build` exits 1 when a check in `checks.failures` fails (`header`, `license`, `checksum`, `external-refs`, `size`, `kit`, `layout`). Fix the source and rebuild; do not edit the built file. `quirk_html.py check FILE` re-runs the checks alone. Exit 2 means a usage error, an unknown or invalid template, or a malformed source.
8. **Verify in a browser.**

   ```
   python3 "$SKILL_DIR/scripts/quirk_html.py" verify FILE [--out-dir DIR]
   ```

   It writes screenshots and `report.json` to `<file stem>.verify/`. Open the screenshots and judge them against the checklist in [design reference](references/design-reference.md) section 14, because verify proves the page loads and is legible, not that it is good. Never install or download a browser: when none is found, verify exits 0 with `status: "not-browser-verified"`, and you say so in the delivery note.
9. **Write the note.**

   ```
   python3 "$SKILL_DIR/scripts/quirk_html.py" note FILE [--verify-dir DIR]
   ```

   Pass `--verify-dir` when you gave verify an `--out-dir`. `verify_stale: true` means the file changed after verify; run verify again.
10. **Deliver.** Send the note's `markdown` with the direction brief's job restated in one sentence and any decision the user may want to change.

Any edit after verify means verify again.

### Tier 2

```
python3 "$SKILL_DIR/scripts/quirk_html.py" build-app SLUG --title TITLE [--layout SHAPE] [--mode offline|connected] [--signal TEXT] [--template NAME] [--upgrade] [--project-dir DIR]
```

- The first build copies the template's project to `<project>/.quirk/html/<slug>/`, installs, builds, and writes `<project>/.quirk/html/<slug>.html`. Title, layout, mode and signal are saved in `quirk-app.json` there, so later builds need only the slug. Edit the files under `<slug>/src/` and run `build-app SLUG` again; the source folder is never overwritten. The `app` template's `rules.md` lists the scaffold files.
- Pass `--signal` with the signal you chose in step 2, and `--layout` with the shape you named in step 4. The app takes each view's `summary` from `routes.tsx`; see the `app` template's `rules.md`.
- **Exit 3 means tier 2 is unavailable here:** Node or pnpm is missing, install failed, or the build failed. The JSON carries a `reason`. Do not retry in a loop. Fall back to a tier-1 build of the same idea and list every cut (a view merged, a grid made read-only) in the delivery note.
- Installs run `pnpm install --frozen-lockfile --ignore-scripts --ignore-pnpmfile`, so no package script or pnpmfile hook runs at install. Building still runs the template's own build code (`vite.config.ts`, the build script), so build only project or user tier-2 templates you trust.
- Never commit `node_modules/`.

### Editing an existing artifact

- Edit the source (`<slug>.src.html`, or the `<slug>/` folder for tier 2) and rebuild. Do not hand-edit the built file.
- **A rebuild keeps the library versions recorded in the page's header.** Pass `--upgrade` only when the user asks to move to current versions.
- Check the build's `warnings`: a template skipped as invalid means the rebuild used the next valid match.

### Data and modes

- **Sidecar data.** A `data` file named in the source header is embedded. When it is too large to embed, the build moves it to a sidecar file next to the page, and the page asks the reader to pick that file. The note names the sidecar; keep the two files together when delivering.
- **Offline is the default.** An offline page makes no network requests: the static check rejects external references and verify fails on any request.
- **Connected** (`"mode": "connected"` in the header, or `--mode connected`) is for pages that fetch live data. Requests go through instead of failing, and verify records every URL in the report's `requests`. Use it only when the user wants live data, and name the hosts the page calls in the note.

## Page shapes

Every page has exactly one shape, set by the `layout` header field and available on every template. Infer it from the direction brief, name it before building (step 4), and let the user override it.

| Shape | For | The `summary` slot holds |
|---|---|---|
| `explainer` | findings with their evidence, how-it-works pages and write-ups | the answer or findings under the h1 |
| `longform` | long prose with notes on its phrases | the answer or findings under the h1 |
| `tool` | calculators, estimators, converters | the live result beside the inputs |
| `comparison` | picking between options | the recommendation line above the table |
| `dashboard` | status and metrics | the headline metric, top left |
| `reference` | runbooks and references read by section | a one-line purpose under the h1 |

- **Every source needs a `layout` field and a `summary` slot.** A source with no `layout` builds as `explainer` and the note says "Layout: explainer (no layout named)", so always name one. A missing `summary` fails the build and says where it goes for that shape. Templates do not declare `summary`. Region-bearing templates (`report`, `components`, and custom ones with `{{regions}}` or the legacy `{{slot:main}}`) require it; the companion takes its question as the summary and rejects a `summary` slot.
- **A rebuild keeps the recorded shape.** The source's `layout` wins, then the one in the built page's header, then `explainer`.
- **The nav is generated.** It lists the h2 sections with their h3s, appears at 5 or more h2s, and is always on for `reference`. The header field `"nav": "on"` or `"off"` forces it; `off` fails on `reference`. Do not write a table of contents.
- **No shape has a side column for notes.** Put caveats and how the numbers were counted in a last section of `main`.
- **Arrange content with four layout elements:** `q-grid` (columns that stack on phones), `q-panel` (a titled box, the title is required), `q-sidenote` (a highlighted phrase with a note that opens on hover, `longform`) and `q-compare` (the comparison table, `comparison`). Their attributes are in [components](references/components.md). Hand-written grid or fixed-width CSS in a slot fails the layout check: a grid failure names `q-grid`, a width failure points at the `layout` field. Grid on and inside an element you build yourself passes; see [design reference](references/design-reference.md) section 10.
- **Examples, one per shape:** `templates/report/examples/<shape>.src.html`, `templates/components/examples/<shape>.src.html`, `templates/companion/examples/<shape>.screen.json` and `templates/app/examples/<shape>/`. Copy the closest one's structure.

Widths, breakpoints and print rules are in [design reference](references/design-reference.md) section 8.

## Exit codes

| Code | Meaning | Applies to |
|---|---|---|
| 0 | success; for `verify`, also `not-browser-verified` | every command |
| 1 | the build finished but a static check or verify check failed | `build`, `build-app`, `check`, `verify`, `templates verify` |
| 2 | usage error, unknown or invalid template, or malformed source | every command; `templates validate` returns it for an invalid template |
| 3 | tier 2 unavailable; `reason` in the JSON | `build-app` only |

## Delivery note

The note comes from `quirk_html.py note`; do not paraphrase away its facts. It must state:

- the file path, its size, and the sidecar path if there is one
- the template and its level, the layout (marked "no layout named" when the build defaulted it), the tier, and the signal that chose it
- the mode, and for connected mode the hosts the page calls (the note says only that data calls use the network, so add the hosts from the verify report)
- the libraries inlined, with versions
- the static-check result, and the verify result: `passed`, `failed`, or `not-browser-verified` with the reason
- screenshot paths, when verify ran
- a size warning when the file is over 2 MB
- a skipped invalid template (which, where, why) and the template used instead
- every cut, when a tier-2 build fell back to tier 1

It ends by asking whether the user wants the page opened or published. Wait for the answer.

## Custom templates

A project or user template gets every guarantee a built-in one has, and the user can ask for one ("make this a template", "use our branding for these"). Every shape works in a custom template with no change to it; a skeleton written before shapes existed keeps building (see [templates](references/templates.md)). Scaffold with `quirk_html.py templates new NAME --level project|user [--base TEMPLATE] [--from ARTIFACT.html]`, edit it, and finish with `quirk_html.py templates verify NAME`, which writes `verified.json` only when the example passes. It passes without a browser only for environment limits (no node, no browser, install failed) and records `browser: false`. The manifest fields, token layers, lookup order and the repair flow are in [templates](references/templates.md). Do not hand-write `verified.json`.

## Charts and the theme

The chrome fires a `quirk-theme` event on `document` when the theme changes. A page that draws a chart listens for it and rebuilds the chart; CSS variables switch everything else on their own. Bar, line and area charts use the `<q-chart>` element, which handles the rebuild itself; scatter and histogram charts are hand-written and rebuild on the event. `<q-flow>` is the tool for every flowchart on an HTML page: graphs of services, pipelines or data flows that the reader will pan, zoom and click through, and flowcharts with decisions (`shape: "decision"`), retries (`loop: true`) and steps that are their own process (`shape: "subprocess"`, with an optional `flow`). Add a trace (`traces` in the same data) when the reader needs to see what happens to a value as it moves through the flow: one trace per scenario worth walking, the whole value at every step trimmed to the fields the reader needs, and an edge `id` only when a step must pick between parallel edges with `via`. Reuse the same `kinds` names and `--q-color-chart-*` numbers across artifacts. Mermaid stays for diagrams inside Markdown, state charts, and sequence and ER diagrams. Details are in [design reference](references/design-reference.md) section 9 and [components](references/components.md).
## Companion

The companion is a local page that asks the user one question at a time and sends the click back. Brainstorming and exploring-ideas use it for visual questions, and you can run it when a choice is easier to make by seeing it. A screen may name a `layout` to get the room its content needs. Start it with `python3 "$SKILL_DIR/scripts/companion.py" start SESSION_DIR` (a session directory under `.quirk/brainstorm/`), drive it with `show` and `wait`, and end it with `stop`. A timeout on `wait` (exit 1) is normal, so re-run it. Typed input in the terminal outranks a click. The full protocol, `screen.json` format, exit codes and security notes are in [companion](references/companion.md); screen design is section 12 of the [design reference](references/design-reference.md).

## References

- [Design reference](references/design-reference.md): the house design standard, direction brief, banned tells, tokens, page shapes and widths, verify checklist
- [Templates](references/templates.md): template lookup, `template.json`, source file format, the `layout` and `nav` fields, region placeholders, tokens, custom and tier-2 templates
- [Companion](references/companion.md): the companion loop, commands, screen format and per-shape example screens
- [Components](references/components.md): the `q-*` elements (tabs, charts, tables, stats, timelines, code, diffs, boards, explorable `q-flow` graphs, and the layout elements grid, panel, sidenote, compare), their attributes and examples
