# Logic spec: `writing-html-artifacts`

**Status**: Approved, 2026-10-13

A quirk skill that has agents in Claude Code, pi and Oh My Pi build HTML files that open anywhere,
look deliberate, and come with proof that they work. The same machinery gives brainstorming and
exploring-ideas a live visual companion, which replaces quirk's Agent Isles integration. Users and
projects can add their own templates.

Derived from two research documents: *Cross-Agent Skills for Interactive Single-File HTML
Artifacts* (dual-path builder, bundle and QA contracts, host-neutral delivery) and *Deep research on
libraries like Astryx, TanStack* (library landscape, routing policy, two-tier architecture).

This spec covers three pieces of work that the user chose to keep in one spec: the single-file
builder (tier 1), the React builder (tier 2), and the companion.

## Conceptual model

Everything the skill produces comes from a **template**. Built-in pages, a project's branded
reports, the companion's screens and the React scaffold all go through the same pipeline, so a
custom template gets every guarantee a built-in one has.

The units:

- **Template.** A manifest plus fixed chrome plus one to three freeform slots. The manifest holds:
  - a name and a "use when" description the agent matches requests against
  - the tier (1 or 2)
  - the libraries it needs
  - token overrides for the house theme
  - a rules addendum layered on the design reference
  - a filled-in example, which is also its verify fixture

  Templates are built-in, user-level or project-level.
- **Library.** A vendored file set, pinned to a version, checksummed, and carrying its license.
  v1 ships Simple.css, Alpine.js, Web Awesome, one chart library and Mermaid. A template can bring
  more.
- **House theme.** One token set with light and dark pairs, plus the design reference that says how
  to use it. Project templates override its tokens.
- **Artifact.** A built `.html` file. It may have a sidecar data file and, for tier 2, a source
  folder. A header inside the file records the template, tier, mode and library versions.
- **Companion session.** A local server plus a directory of screens. Each screen is an artifact
  built from the `companion` template.
- **Verify report.** The result of running the checks on the final file, with screenshot paths.

Slots are deliberately coarse. The chrome is fixed (theme, toggle, license notices, header) and the
agent writes freely inside the slots. Consistency comes from the shared chrome and tokens, and
quality comes from verifying the output rather than from a rigid slot grammar.

## Data flow

A request comes in and the agent matches it against template descriptions, looking in the project
first, then the user's templates, then the built-ins. It states which template it picked and which
tier, and why.

The agent fills the slots by following the design reference and the template's rules addendum. It
also declares the artifact's interactions and its mode, so the later checks know what to expect.

The build turns template plus slot content into the deliverable. Tier 1 assembles chrome, slots
and tokens, inlines the libraries, and adds license notices and the header. Tier 2 copies the
React scaffold into a source folder, installs from the template's frozen lockfile, and bundles to
one file. Either way the output lands in `.quirk/html/`.

Static checks run on the built file, then browser verify runs on that same file if a browser is
reachable. Because the report must come from the final file, any edit after verify means verify
runs again.

The agent then delivers a note with the path, the facts about the build and the verify result. It
offers to open or publish the file and does neither on its own.

For the companion, brainstorming starts the local server, writes one screen per question into the
screen directory, and waits. The user's clicks travel back as an event stream. Proceed on the
current screen ends the wait and hands the agent the selection.

## Key decisions and rationale

- **One template engine for everything.** The user asked for custom templates that can be either
  tier and can add libraries. A token-overlay design can't express those, and research showed
  overlays break silently on upgrades: Shoelace's move to Web Awesome renamed every `--sl-*` token
  to `--wa-*` and inverted the color scale. Making the companion and the React scaffold templates
  too means project branding reaches them for free.
- **Coarse slots with freeform content.** A practitioner who shipped 21 rigid slot templates called
  the slot grammar "the bottleneck" and moved to one freeform body inside shared chrome.
- **Verification over instruction.** Of 101 "tests pass" claims one developer audited, 35 were
  false, and 34 of those were stale: the check ran before the last edit. Verify therefore runs on
  the final file and the note points at its output.
- **Pinned, vendored, checksummed libraries.** An unpinned dependency in Anthropic's own artifact
  builder resolved to a new major version. The build exited 0 and the page threw in the browser.
  Vendoring also lets tier 1 build with no network.
- **Simple.css instead of Pico CSS.** Pico is archived; its last release was v2.1.1 in March 2025.
  Simple.css is classless, MIT-licensed, maintained (last pushed July 2026), built on CSS variables
  and has automatic dark mode, so house tokens can override it. Open Props was rejected because it
  is a token library, not a classless stylesheet.
- **A stdlib Python server for the companion.** A page opened from `file://` can't send anything
  back, so the companion needs a process that outlives the agent's tool call. Python stdlib keeps
  Node out of the brainstorming path and matches quirk's existing `bin/` tooling.
- **The spec is the record.** Companion screens and events are transient. Decisions live in the
  spec that brainstorming writes, as they did with Isles.
- **Quirk builds; publishing is separate.** The skill writes a local file. Claude's own artifact
  skills and the Artifact tool apply only if the user later chooses to publish it.

## Behavior

### Triggering

- The skill runs when the user asks for HTML, a page, a report as a page, or an interactive tool.
- When an answer "has shape" (a comparison, a dashboard, a flow, a table someone will explore), the
  agent offers a page in one line and builds it only on a yes.

### Picking a template and a tier

1. The agent matches the request against template descriptions in lookup order: project
   `.quirk/html-templates/`, then user `~/.quirk/html-templates/`, then built-in. A name that
   exists at two levels resolves to the higher one. The user can name a template directly.
2. Tier 2 is chosen when any of these signals holds:
   - the artifact has multiple views or routes
   - it has an editable data grid
   - state is shared across views
   - the user asks for an app or a project

   The agent may also escalate on its own judgment, and must then say why. Otherwise the artifact
   is tier 1.
3. The agent states the template, its source level and the tier before building.

### Building

- **Tier 1** writes `.quirk/html/<slug>.html`. The file contains the chrome, slot content, tokens,
  inlined libraries, one license notice per library, and the header.
- **Tier 2** writes the source project to `.quirk/html/<slug>/` and the bundle to
  `.quirk/html/<slug>.html`. It installs from the template's lockfile with a frozen install. The
  first build needs network for that install; the output never does.
- **Tier 2 failure.** If Node is missing or the install or build fails, the agent builds a tier-1
  version instead. The delivery note lists every feature that was cut.
- **Editing an existing artifact** rebuilds it with the library versions recorded in its header,
  unless the user asks to upgrade.
- `.quirk/html/` is gitignored.

### Modes

- **Offline** (default): the file makes zero network requests. Fonts come from the system stack.
- **Connected**: chosen only when the artifact must call a real API, and labelled as connected in
  the delivery note. Libraries are still inlined; only the page's own data calls go to the network.
- There is no CDN mode.

### Static checks

These run on every build, companion screens included:

- in offline mode, no external references (scripts, stylesheets, fonts, images, fetches)
- size: a warning above 2 MB, a failure above 10 MB
- every inlined library matches its checksum, and its license notice is present
- the header is present and complete

When embedded data would push the file over budget, the data moves to a sidecar `.json` or `.csv`
next to the page. The page loads it through a file picker and says so on screen.

### Browser verify

When a browser is reachable, one quirk verify script runs these checks on the final file:

- no console errors
- screenshots at 375px wide and at desktop width
- light and dark themes both legible
- zero network requests (offline mode only; connected mode reports the requests it saw)

When no browser is reachable, the delivery note says "not browser-verified" and lists the static
checks that did run. Verify never installs a browser without asking.

### Delivery

The agent's note lists:

- the path and size, plus the sidecar and source folder if any
- the template and where it came from
- the tier and the signal (or judgment) that chose it
- the mode
- the libraries and their versions
- the verify result and screenshot paths

It ends with a one-line offer to open or publish the file. Neither happens automatically.

### Templates

- **Built-ins:**
  - `report`: Simple.css + Alpine, for reports, explainers, forms and small tools
  - `components`: Web Awesome + Alpine, for component-heavy pages (dialogs, tabs, comboboxes)
  - `companion`: the brainstorming screen shell
  - `app`: tier 2, React with Vite single-file bundling, Astryx and TanStack, with its own lockfile

  Any template can request the chart library or Mermaid.
- **Custom templates** can do everything a built-in does: either tier, token overrides, a rules
  addendum, extra libraries, and an example. A tier-2 custom template ships its own lockfile.
- **Project tokens apply to the companion.** A project template's token overrides reach the
  companion shell too, so brainstorming screens look like the project.
- **Creating a template** is a guided flow. The user starts from scratch or from an existing
  artifact. The flow writes the manifest, skeleton and example, then runs verify on the example.
  The template is usable only once its example passes.
- **An invalid template** (bad manifest, failed checksum, missing example) is skipped with a
  visible warning, and the next match in lookup order is used.

### Companion

- Brainstorming and exploring-ideas start the server. It prints its URL and directories as JSON,
  runs in the background, and exits after an idle timeout.
- For each question, the agent writes the question text, the options, and any mockup or diagram
  into the `companion` template. The server always serves the newest screen. Screens have 2 to 4
  options and never reuse a filename.
- The shell provides single- and multi-select choice sets, a Proceed button, the theme toggle, the
  project's tokens, and a "superseded" banner on stale tabs.
- Every click is recorded in a full event stream, tagged with the nonce of the screen it came from.
  Clicks from a screen that is no longer current are rejected.
- `wait` blocks until Proceed is clicked on the current screen, then returns the selection. If the
  host kills the wait, the agent re-runs it and no click is lost. With no server running, `wait`
  fails with a distinct exit code.
- The agent reads the stream and the Proceed payload. Anything the user types in the terminal takes
  priority over clicks.
- Screens and events live under `.quirk/brainstorm/`, which is gitignored.

### Isles removal

- Removed from quirk: `bin/agent_isles.py`, `packs/quirk/`, `examples/agent-isles/`,
  `docs/agent-isles-artifacts.md`, and the three Isles test files.
- Rewritten: both `visual-companion.md` guides and the companion offers in the brainstorming and
  exploring-ideas skills, which currently name Agent Isles and Node.
- The separately installed agent-isles plugin is left alone. Quirk just stops referencing it.
- The README skill count goes from 25 to 26.

### Hosts

- v1 supports Claude Code, pi and Oh My Pi.
- Scripts are found relative to the skill's own directory, so the skill works wherever it is
  installed or symlinked.
- Build, the server and static checks need only Python stdlib. Browser verify and tier 2 need Node.

### Scenarios

1. **A report from data.** The user asks for a page summarizing test-run timings. The agent picks
   `report` (built-in), tier 1, offline, and adds the chart library. It builds
   `.quirk/html/test-timings.html` at 410 KB, verify passes at both widths and both themes, and the
   note offers to open it.
2. **A branded project report.** The project has `.quirk/html-templates/report/`. The same request
   resolves to the project's `report`, the note says "project template", and the page uses the
   project's tokens and rules addendum.
3. **An app.** The user asks for a tool to edit a list of feature flags and preview them in two
   views. Two signals fire (editable grid, multiple views), so the agent picks `app`, tier 2. The
   source lands in `.quirk/html/flag-editor/` and the bundle in `.quirk/html/flag-editor.html`.
4. **Tier 2 without Node.** Same request on a machine without Node. The agent builds a tier-1
   version with one view and a read-only table, and the note lists both cuts.
5. **Too much data.** The data would make a 14 MB file. It moves to `flag-data.json` next to the
   page, the page shows a file picker, and the note names both files.
6. **No browser.** Verify can't find a browser. The note says "not browser-verified" and lists the
   static checks that passed.
7. **A broken custom template.** A user template's library checksum doesn't match. The agent warns,
   skips it, and uses the built-in of the same name, and the note says so.
8. **A companion session.** Brainstorming starts the server and shows a screen with three layout
   options in the project's colors. The user clicks two, changes their mind, clicks Proceed. The
   agent gets the full click stream and the final selection. A click on an older tab is rejected
   and that tab shows the "superseded" banner.
9. **A killed wait.** The host times out the agent's `wait` mid-question. The agent re-runs it, the
   user's earlier clicks are still in the stream, and Proceed returns normally.
10. **Editing an old artifact.** A file built against an older Web Awesome is edited. It rebuilds
    with the versions in its header, not the current pins.

## Scope and non-goals

**Success criteria:**

- every built-in template has a worked example that passes verify, and there is a tier-2 example
- trigger evals: about 10 prompts that should fire the skill and about 10 near-misses that should
  not
- a brainstorming session runs end to end on the new companion in Claude Code and in pi or OMP
- the server, builder and static checks are covered by pytest, which runs in CI

**Non-goals for v1:**

- Codex, Gemini CLI and Copilot CLI
- handoffs into other skills (code review, finishing a branch, the pm dashboard)
- changes to the writing-specs interactive app
- automatic opening or publishing
- a CDN mode
- webfonts
- browser verify in CI
- automated pin-bump PRs
- keyboard, axe and per-interaction smoke checks in verify
- archiving companion screens as an audit trail

## Decisions Locked

**Scope and shape**

- Two tiers: inlined single-file HTML, and a React project bundled to one file.
- Curated, inlined library stack rather than per-artifact choices.
- Replace Agent Isles as quirk's companion.
- Skill name `writing-html-artifacts`.
- All three pieces (tier 1, tier 2, companion) in one spec.

**Tier escalation**

- Named signal list plus agent judgment; the agent states the signal or the reason.
- Tier 2 leaves the source project and the bundle.
- Tier 2 installs from a shipped lockfile with a frozen install.
- Tier 2 failure falls back to tier 1 and lists what was cut.

**Offline semantics**

- Offline by default, opt-in connected mode, no CDN mode.
- System font stack only.
- Warn above 2 MB, fail above 10 MB.
- Over-budget data goes to a sidecar loaded through a file picker.

**Companion protocol**

- Quirk's own stdlib Python server.
- Content goes into a fixed shell with freeform regions.
- The agent reads the full click stream plus the Proceed payload.
- A killed wait is re-entered and loses no clicks.
- Stale clicks are rejected and old tabs show a "superseded" banner.
- Isles code is removed in the same change.
- The spec is the record; screens and events are transient.
- The external agent-isles plugin is left alone.

**Verification**

- Browser QA is required when a browser is reachable; otherwise the note says "not
  browser-verified".
- One quirk verify script for every host.
- Checks: console, 375px and desktop viewports, light and dark, network.
- Done means verify ran on the final file, with report and screenshot paths in the note.
- The companion shell is tested in pytest; screens get static checks only.

**Design quality**

- Quirk ships its own full design reference, informed by web and Reddit research.
- One house theme shared by artifacts and the companion.
- Light and dark both required, following the OS, with a toggle.

**Libraries and pins**

- v1 libraries: a classless stylesheet with Alpine, Web Awesome with Alpine, a chart library,
  Mermaid.
- Pico CSS is replaced by a maintained classless library; the design names Simple.css.
- Libraries are vendored with checksums.
- Pins are bumped by hand, and a check flags outdated pins or pins with advisories.
- Old artifacts keep their recorded versions unless the user asks to upgrade.
- Each inlined library carries a license notice.
- Python stdlib for build, server and static checks; Node for verify and tier 2.

**Hosts and delivery**

- Hosts: Claude Code, pi, Oh My Pi.
- Scripts resolve relative to the skill's directory.
- Output goes to `.quirk/html/<slug>.html`, gitignored.
- Report the path and the delivery note, then offer to open or publish; never automatic.
- Trigger when HTML, a page or a tool is asked for; offer in one line when an answer has shape.
- No handoffs beyond the companion in v1.
- The writing-specs app is left as is.
- Quirk builds the file; Claude's artifact skills apply only if the user publishes.

**Templates**

- Contents: skeleton with slots, token overrides, rules addendum, extra libraries, example.
- Lookup: project `.quirk/html-templates/` (committed), then user `~/.quirk/html-templates/`, then
  built-in.
- Custom templates can be either tier.
- Project tokens apply to the companion.
- The agent matches the request to descriptions and states its pick; the user can name one.
- Templates are created through a guided flow, from scratch or from an existing artifact.
- An invalid template is skipped with a warning and the next match is used.

**Approach**

- Approach A: one template engine with coarse slots, borrowing freeform regions and
  verify-over-rules from the agent-assembled approach.

## Industry Insights

Research ran in four phases: context research, adhd gray-area discovery, a deep dive on the design
reference, and validation of the three approaches. The Brave and reddit-research skills were
unavailable, so agents used WebSearch and WebFetch, and Reddit came from Arctic Shift.

**Templates and slots**

- Rigid slot grammars became "the bottleneck" for a 21-template HTML skill; one freeform body over
  shared chrome kept pages consistent.
  [Muninn](https://muninn.austegard.com/blog/the-unreasonable-effectiveness-of-html-and-the-skill-that-tries-not-to-ruin-it.html)
- dogum/html-artifacts v2.0.0 dropped HTML teaching in favor of judgment, headless-render checks
  and evals against a no-skill baseline. [dogum/html-artifacts](https://github.com/dogum/html-artifacts)
- Template precedence needs one explicit rule, and collisions need qualified names.
  [Hugo lookup order](https://gohugo.io/templates/lookup-order/),
  [shadcn namespaces](https://ui.shadcn.com/docs/registry/namespace)
- Templates sprawl and rot unless versioned and tested; Backstage's official templates are
  unversioned and Copier updates pass drift through unmarked.
  [backstage/software-templates](https://github.com/backstage/software-templates),
  [Red Hat](https://developers.redhat.com/articles/2025/03/17/10-tips-better-backstage-software-templates),
  [fastmcp-server-template #653](https://github.com/pvliesdonk/fastmcp-server-template/issues/653)
- Manifests with descriptions and typed kinds keep growing template sets findable.
  [shadcn registry-item.json](https://ui.shadcn.com/docs/registry/registry-item-json)

**Theming**

- Token overrides stop at component internals; Web Awesome needs component properties or
  `::part()` for shadow DOM. [Web Awesome theming](https://webawesome.com/docs/theming-overview/)
- Upgrades break silently through renames: Shoelace to Web Awesome renamed `--sl-*` to `--wa-*` and
  inverted the color scale.
  [migration guide](https://webawesome.com/docs/resources/migrating-from-shoelace/)
- Light and dark pairs are usually hand-duplicated; Pico requires dark variables twice. The DTCG
  2025.10 resolver models themes as contexts.
  [Pico CSS variables](https://picocss.com/docs/css-variables),
  [DTCG resolver](https://www.designtokens.org/tr/2025.10/resolver/)
- Dark themes fail contrast near the threshold (4.43:1 against 4.5:1), so each theme is checked
  separately. [gh-aw-cao #9249](https://github.com/githubnext/gh-aw-cao/issues/9249)

**Building and dependencies**

- An unpinned `react-resizable-panels` resolved to v4 in Anthropic's artifact builder; the build
  exited 0 and the browser threw React #130.
  [anthropics/skills #1893](https://github.com/anthropics/skills/issues/1893)
- vite-plugin-singlefile is the simplest single-file route; it doesn't inline `public/` files or
  SVG. [vite-plugin-singlefile](https://github.com/richardtallent/vite-plugin-singlefile)
- Hidden CDN and font dependencies break offline pages.
  [livepage #161](https://github.com/glennfaison/livepage/issues/161)
- Inlined widgets add up fast: ten self-contained widgets totaled 4.1 MB.
  [bundle plan](https://glama.ai/mcp/servers/@mikechao/brave-search-mcp/blob/9db552a665dc2c1e7b81f16dd87301daddd1c88f/docs/reduce-bundle-plan.md)
- Anthropic's web-artifacts-builder is a heavy React/shadcn stack "not for simple single-file
  artifacts", and defers testing.
  [web-artifacts-builder](https://github.com/anthropics/skills/blob/main/skills/web-artifacts-builder/SKILL.md)

**Verification**

- In an audit of 101 "tests pass" claims, 35 were false and 34 of those were stale.
  [dev.to audit](https://dev.to/vinzenz_eiberger/i-checked-101-tests-pass-claims-from-my-ai-coding-agents-35-werent-true-h6n)
- dogum verifies at 1280x800 in light and dark and at 400x800, checks the console, and doesn't
  install a browser without asking.
  [verify-before-delivering.md](https://raw.githubusercontent.com/dogum/html-artifacts/main/skills/html-artifacts/references/verify-before-delivering.md)
- Agent-written browser tests can pass by accident when they only confirm page load.
  [Currents](https://currents.dev/posts/state-of-playwright-ai-ecosystem-in-2026)

**Design reference**

- Models converge on a default look ("distributional convergence": Inter, purple gradients);
  Anthropic names Space Grotesk as the next default to avoid.
  [Anthropic cookbook](https://platform.claude.com/cookbook/coding-prompting-for-frontend-aesthetics),
  [Anthropic blog](https://claude.com/blog/improving-frontend-design-through-skills)
- dogum's banned list (gray card grids, gradient heroes, emoji headers, glassmorphism, centered
  everything) with "rebuild at three or more" is the most usable artifact-specific list.
  [matching-your-style.md](https://raw.githubusercontent.com/dogum/html-artifacts/main/skills/html-artifacts/references/matching-your-style.md)
- frontend-design gives the most concrete rules: a 4 to 6 color plan, one or two families, measure
  under 80 characters, named device bans.
  [frontend-design](https://raw.githubusercontent.com/anthropics/skills/main/skills/frontend-design/SKILL.md)
- Recurring defaults: body 16 to 18px, line-height 1.5 to 1.6, measure 60 to 75ch, one type ratio
  (1.25 or 1.333), 4px spacing base, 4.5:1 text and 3:1 UI contrast, 2px focus outline with 2px
  offset, a named radius scale, 5 to 8 categorical chart series (Okabe-Ito).
  [accessibility-and-print.md](https://raw.githubusercontent.com/dogum/html-artifacts/main/skills/html-artifacts/references/accessibility-and-print.md),
  [noqta](https://noqta.tn/en/blog/ai-design-slop-overused-ui-patterns-fix-2026)
- DESIGN.md (Google Labs, alpha) pairs YAML tokens with prose and lints contrast, but doesn't model
  light and dark. [design.md](https://github.com/google-labs-code/design.md)
- The superpowers brainstorming companion has a ready vocabulary (options, cards, mockup, split,
  pros-cons) and the rule of 2 to 4 options per screen.
  [visual-companion.md](https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/visual-companion.md)
- Reddit: people spot "AI purple" and "Claude sad beige", but clarity and usability matter more
  than avoiding the look. [r/webdev](https://www.reddit.com/r/webdev/comments/1trfxp1/),
  [r/ClaudeAI](https://www.reddit.com/r/ClaudeAI/comments/1x22sap/),
  [r/UI_Design](https://www.reddit.com/r/UI_Design/comments/1wnh9z5/)
- No source measures concrete rules against vague taste guidance; the reference ships numbers and
  checkable rules, and evals test them.
  [arXiv 2505.17037](https://arxiv.org/html/2505.17037v1)

**Skill packaging**

- Only `name` and `description` frontmatter is portable across hosts.
  [Agent Skills spec](https://agentskills.io/specification)
- Descriptions are the only trigger signal; test about 20 queries, half should-fire and half
  near-miss. [agentskills.io](https://agentskills.io/skill-creation/optimizing-descriptions)

## Deferred Ideas

Out of scope for v1:

- handoffs from code review, finishing a branch and the pm dashboard into a page
- browser verify in CI
- Codex, Gemini CLI and Copilot CLI support
- automated pin-bump PRs
- keyboard, axe and per-interaction smoke checks in verify
- a pinned-CDN mode and inlined webfonts
- Preact + HTM and Bulma as libraries
- archiving companion screens alongside the spec

Open for the tech spec:

- `[tech-spec]` Which chart library ships.
- `[tech-spec]` How the companion keeps Mermaid (over 1 MB inlined) from bloating every screen.
- `[tech-spec]` The manifest schema, its version field, and how slots are marked in a skeleton.
- `[tech-spec]` The header's format and how an edit reads versions back from it.
- `[tech-spec]` How verify finds a browser, how it runs Playwright, and where screenshots go.
- `[tech-spec]` How the pin check finds outdated pins and advisories.
- `[tech-spec]` Companion details carried from Isles: idle timeout, `wait` chunk length, the
  no-server exit code, and the event record shape.
- `[tech-spec]` How "create from an existing artifact" extracts a skeleton and tokens.
- `[tech-spec]` How trigger evals are run and scored.
- `[tech-spec]` The design reference's section list (the research proposed 14 sections).

## Glossary

- **Artifact**: a built `.html` file the skill delivers, with its header, plus any sidecar or
  source folder.
- **Chrome**: the fixed part of a template (theme, toggle, notices, header) that the agent doesn't
  write.
- **Companion**: the live page brainstorming and exploring-ideas show in a browser to ask visual
  questions.
- **Connected mode**: an artifact allowed to call a real API at runtime. Libraries are still
  inlined.
- **Header**: a comment block inside the artifact recording template, tier, mode and library
  versions.
- **House theme**: quirk's default token set, with light and dark pairs.
- **Library**: a vendored, pinned, checksummed file set with its license, such as Alpine or
  Simple.css.
- **Nonce**: a per-screen token that ties each click to the screen it came from.
- **Offline mode**: the default; the artifact makes zero network requests.
- **Proceed payload**: what `wait` returns when the user clicks Proceed: the current selection.
- **Sidecar**: a data file shipped next to an artifact and loaded through a file picker.
- **Slot**: a freeform region of a template the agent fills.
- **Template**: a manifest, chrome, slots, tokens, rules addendum, libraries and example. Built-in,
  user or project.
- **Tier 1**: a single file assembled from a template with inlined libraries; no build tool.
- **Tier 2**: a React project bundled to one file, with the source kept.
- **Tokens**: CSS custom properties for color, type, spacing and radius.
- **Verify**: the browser checks run on the final file.

## Status & amendments

**Status**: Approved by the user, 2026-10-13. Handed to subagent-driven-development.

**Amendments**

None yet.
