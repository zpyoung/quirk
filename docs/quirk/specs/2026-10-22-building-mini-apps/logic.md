# Logic spec: `building-mini-apps`, interaction-pattern templates for small local apps

## Status & amendments

**Status**: Approved

**Amendments:** none yet.

I build a lot of small apps for my own local use, and an agent asked to "make it nice" produces a
generic dashboard. This skill gives the agent proven interaction patterns to start from instead. The
patterns come from studying ten well-regarded interfaces: Linear, Things 3, Raycast, Craft, Obsidian,
TablePlus, Fantastical, Notion, Granola and Figma. Each pattern ships two ways: a written reference the
agent reads, and a working React block it installs.

The templates copy how each app behaves, not how it looks. Layout, density, keyboard flow and state
handling carry over. Brand colors, icons, fonts and illustrations don't, and every pattern shares one
neutral house style.

## Conceptual model

The skill has four parts. The first two are committed to quirk. The third is local only, and the
fourth sits beside the registry.

| Part | What it holds | Who reads it |
|---|---|---|
| References | One written reference per pattern and one study note per app, in text only | The agent before it builds, and me when I browse |
| Registry | A local shadcn registry: one `base` item plus one block per pattern | The shadcn CLI, when the skill scaffolds an app |
| Captured media | Video frames and screenshots of the ten apps, in a gitignored folder | Me, and the agent while it writes the references |
| Gallery | A Vite app that shows every pattern running, next to its reference | Me, to see what's on offer and catch broken blocks |

The skill lives at `skills/building-mini-apps/`. That location is itself a user-facing decision, so this
spec names it:

```
skills/building-mini-apps/
  SKILL.md                      the build flow and the pattern index
  references/patterns/<pattern>.md
  references/apps/<app>.md
  references/media/<app>/       gitignored, never committed
  registry/                     registry.json, block sources, built items in registry/r/
  gallery/                      Vite app over the registry source
```

**A pattern** is one interaction you can name and reuse, taken from one app. A mini app usually
combines two or three. The first round builds these ten:

| Pattern | What it does | Studied from |
|---|---|---|
| list-peek | A dense list. j and k move, Space previews the item without leaving the list | Linear |
| expand-in-place | A row opens into an editable card. Optional fields stay hidden until asked for | Things 3 |
| action-palette | Search, select, then ⌘K lists the actions for that one item | Raycast |
| doc-collections | A document with structured collections embedded in it, so records keep their context | Craft |
| workspace-panes | Tabs and split panes over data that lives in files you can see | Obsidian |
| staged-table-edit | Edit cells inline; changes show as pending until ⌘S commits or you discard them | TablePlus |
| mini-full | A small quick-add with natural-language parsing that expands to a full view | Fantastical |
| view-switcher | Table, board or calendar over the same records, with a record opening in a side panel | Notion |
| assisted-notes | My notes stay primary; AI additions are styled apart and link to their source | Granola |
| inspector | Navigation tree, main canvas, and a properties panel for whatever is selected | Figma |

**The base** is what every mini app gets before any pattern: the app shell, the design tokens for the
house style in light and dark, a keyboard-shortcut layer, a browser-storage hook with JSON export and
import, and building blocks for empty, loading and error states. Patterns build on the base, so two
patterns in one app share a keyboard layer and a store instead of each bringing its own.

## Data flow

Work moves through three stages, and each one feeds the next.

**Capture.** For each app I gather public material only: official videos, official docs screenshots,
third-party walkthroughs found with yt-dlp search, and public demo pages driven with Playwright. Frames
come out of videos through ffmpeg scene detection. Videos are deleted once their frames are extracted.
Frames land in `references/media/<app>/`, which git ignores, because quirk is a public repo and
publishing other companies' screens under my account isn't acceptable. If an app genuinely can't be
studied without logging in, the agent asks me rather than skipping it.

**Study.** Each app gets a study note in `references/apps/<app>.md`. It records what the frames show,
with the source URL and timestamp for each observation, and which pattern each observation feeds. The
notes are the committed record of the research. The frames are only local evidence for them.

**Build.** Each pattern reference is written from the study notes. It gives a layout diagram in text,
the keyboard and state rules, what to borrow, what to leave out, and where it came from. The block is
built to match the reference. The gallery imports block sources directly, so a broken block breaks the
gallery build and I see it.

When I later ask for a mini app, the skill reads the pattern index, picks the patterns that fit, makes a
fresh Vite app, installs the base and those patterns from the local registry with `shadcn add`, then
adapts them to what I asked for.

## Key decisions & rationale

- **Cut by pattern, not by app.** A "Linear-style app" mixes several patterns and invites a look-alike
  clone. Patterns compose: a reading tracker might use list-peek with action-palette.
- **A reference plus a runnable block, for every pattern.** Research found that screenshots carry
  pixels but not behavior, and agents working from images miss states, keyboard flow and focus. The
  written reference carries those rules. The block proves they work.
- **A local shadcn registry does the installing.** `shadcn add ./registry/r/<pattern>.json` copies a
  block's files into the app, adds its npm dependencies, and pulls in the shadcn components it needs.
  That's exactly the "base plus add-ins" merge, without a copy script of our own. It also leaves plain
  code in the app for the agent to edit. A pnpm monorepo was rejected: it needs Tailwind workarounds,
  hits open shadcn CLI bugs, and a mini app couldn't stand alone.
- **React, Vite, Tailwind v4 and shadcn/ui.** My stack choice, and shadcn is the most familiar
  component set for agents.
- **One neutral house style.** All patterns share one set of tokens. This keeps combined patterns
  looking like one app and keeps clear of other apps' trade dress.
- **Data lives in the browser by default.** IndexedDB or localStorage, with JSON export and import.
  A pattern or app may add a small local server when it actually needs one, such as for reading real
  files.
- **Media stays local.** Frames go in a gitignored folder inside the skill. Only text and diagrams I
  draw get committed.
- **Done means it runs.** A block is done when an app using it starts with `pnpm dev` and `pnpm build`
  passes clean. My bar; no Playwright suite or visual comparison is required.

## Behavior & scenarios

1. **SC-1: Build a mini app from two patterns**
   - **Given** the registry holds all ten patterns and the base
   - **When** I ask for "a mini app to track books I'm reading"
   - **Then** the skill names the patterns it chose and why, scaffolds a new Vite app with the base and
     those patterns, adapts them to books, and reports that `pnpm dev` starts and `pnpm build` passes
   - **Walkthrough:**
     1. The agent reads the pattern index and picks list-peek and expand-in-place*.
     2. The agent creates **books-app*** with Vite and runs `shadcn init`.
     3. The agent installs `base`, `list-peek` and `expand-in-place` from the local registry.
     4. The agent renames the generic item to a book with title, author, status and notes*.
     5. The agent runs `pnpm build` ✓ clean, and reports the app's path and the patterns used.
   - **Data after:** **books-app**: ✓ base, list-peek and expand-in-place installed; ✓ builds clean; ✓
     books saved in the browser and exportable to JSON

2. **SC-2: No pattern fits the request**
   - **Given** the request matches none of the ten patterns well
   - **When** I ask for something like a waveform audio editor*
   - **Then** the skill says no pattern fits, offers the base alone, and lists the nearest patterns
     with why each falls short. It doesn't stretch a pattern into a shape it wasn't built for.

3. **SC-3: Adding a pattern to an app that already has one**
   - **Given** an existing mini app built with the base and list-peek
   - **When** I ask to add action-palette to it
   - **Then** the skill installs only the new block. Shared base files are left alone, because shadcn
     skips files that already exist, and the agent wires the new block into the existing keyboard layer
     and store.
   - **Data before:** **books-app**: base, list-peek
   - **Data after:** **books-app**: base unchanged; list-peek unchanged; ✓ action-palette added; ✓ ⌘K
     opens actions for the selected book

4. **SC-4: An app has no official video**
   - **Given** Things 3 has no official walkthrough video
   - **When** the capture stage studies Things 3
   - **Then** it uses official docs screenshots and blog images first, then third-party reviews found
     with yt-dlp search. The study note marks each observation official or third-party, and an
     interaction no public source shows is recorded as unseen rather than guessed.
   - **Details:**

     | Source | Example | Marked |
     |---|---|---|
     | Official blog images | Repeating to-dos post, Aug 2026 | official |
     | Third-party review video | A 2026 Things 3 review* at 03:12* | third-party |
     | Expanded to-do with checklist | Not shown in any source found* | unseen |

5. **SC-5: An app needs a login to study**
   - **Given** the public material for an app leaves a pattern's core interaction unseen
   - **When** the capture stage reaches that point
   - **Then** the agent asks me whether to log in. Until I answer, it carries on with the other apps
     and doesn't create accounts itself.

6. **SC-6: A block stops building**
   - **Given** a block's code breaks, say after a dependency update
   - **When** the gallery builds
   - **Then** the gallery build fails and names the broken block, because it imports block sources
     directly. A block that doesn't build isn't done.

7. **SC-7: Reading a pattern without building**
   - **Given** I want to see what list-peek offers before using it
   - **When** I open its reference or the gallery
   - **Then** the reference shows the layout, keys, states, and the parts deliberately left out, and
     the gallery shows the same block running with sample data

## Scope & non-goals

In scope: capturing and studying all ten apps, ten pattern references, ten study notes, the base item,
ten registry blocks, the gallery, and `SKILL.md`.

Not in scope:

- Pixel-faithful clones, or any brand assets: logos, icons, fonts, illustrations, copy.
- Committing any captured frame or video.
- Native desktop or mobile builds. Starters are web apps run locally.
- A hosted registry. Installs come from local files only.
- Automated UI tests or visual comparison, beyond "runs and builds".
- Logging into any app without asking me first.

## Decisions Locked

**Template shape**
- A template is a written reference plus a runnable starter block.
- Templates are cut by interaction pattern, not by app or app type.
- The behavior is copied and the style is our own neutral one.

**Location and media**
- New skill in the quirk repo at `skills/building-mini-apps/`.
- Captured frames go in a gitignored folder inside this worktree: `references/media/<app>/`.
- Downloaded videos are deleted after frame extraction.

**Stack**
- React with Vite, shadcn/ui with Tailwind.
- Local shadcn registry; the base app plus pattern add-ins are installed with `shadcn add`.
- Data in the browser by default; a server is allowed where it makes sense.
- A gallery app is built.

**Capture**
- yt-dlp installed (through uv, because Homebrew on this Intel Mac would build LLVM from source).
- Public pages and demos only; ask before logging in anywhere.
- All ten apps in the first round, with all ten patterns as listed.

**Quality bar**
- Done means it runs with `pnpm dev` and builds clean.

## Industry Insights

- **Text specs beat screenshots as the source of truth.** Google's DESIGN.md pairs YAML tokens with
  prose rules, and Interface Design keeps a `system.md` the agent reloads. Both carry decisions an image
  can't. ([design.md](https://github.com/google-labs-code/design.md),
  [interface-design](https://github.com/Dammyjay93/interface-design))
- **Screenshot-driven UI misses behavior.** Images are "strong evidence for visual symptoms and weak
  evidence for root cause". Agents miss states, focus and keyboard flow, and video is better for
  studying interactions. ([SandBase](https://blog.sandbase.ai/multimodal-coding-agents-screenshot-to-fix-2026/),
  [Columbia DAPLab](https://daplab.cs.columbia.edu/general/2026/01/08/9-critical-failure-patterns-of-coding-agents.html))
- **Copy mechanics, not looks.** Navbars, search bars and dropdowns are generally unprotectable
  conventions, but a specific combination of styling choices can be protected trade dress, and
  takedowns come faster than lawsuits. ([Turley Law](https://turleylaw.com/blog/trade-dress-protection-websites-digital-products))
- **shadcn installs from local files.** `shadcn add ./block.json` is documented. Blocks can depend on
  other local items, declare npm dependencies, and place files through `components.json` aliases, and
  existing files are skipped unless you pass `--overwrite`. It works with Vite and Tailwind v4.
  ([local file support](https://ui.shadcn.com/docs/changelog/2025-07-local-file-support),
  [registry-item schema](https://ui.shadcn.com/docs/registry/registry-item-json),
  [Vite install](https://ui.shadcn.com/docs/installation/vite))
- **Monorepos fight shadcn and Tailwind.** Shared packages need explicit Tailwind `@source` lines,
  and the shadcn CLI has open bugs placing files across workspaces.
  ([Tailwind source detection](https://tailwindcss.com/docs/detecting-classes-in-source-files),
  [docscn #40](https://github.com/ruiyuwg/docscn/issues/40))
- **Official video is scarce.** Of the ten apps, only Craft has a strong official video library, and
  most others have docs screenshots and third-party reviews. ([Craft Learn](https://www.craft.do/learn),
  [Linear board layout](https://linear.app/docs/board-layout),
  [Fantastical views](https://flexibits.com/fantastical/help/calendar-views))
- **Frame extraction.** Use scene detection (`select='gt(scene,0.3)'`, tuned per video), falling back to
  1–2 frames per second for fast UI demos.
  ([bogotobogo](https://www.bogotobogo.com/FFMpeg/ffmpeg_thumbnails_select_scene_iframe.php))

## Deferred Ideas

- Visual comparison of each block against its reference frames. It was offered and not chosen as a
  done bar.
- A Playwright test per pattern. Same as above.
- A DESIGN.md-style token file that other tools could lint. `[tech-spec]`: decide whether the base's
  tokens use that format.

## Glossary

- **Pattern**: one named, reusable interaction taken from one studied app, such as list-peek.
- **Reference**: the written description of a pattern: layout, keys, states, what to borrow, what to
  leave out, and where it came from.
- **Study note**: the per-app record of what the captured material shows, with sources.
- **Block**: a pattern's runnable React code, packaged as a shadcn registry item.
- **Base**: the registry item every mini app starts with: shell, tokens, keyboard layer, storage, and
  state building blocks.
- **Registry**: the local folder of shadcn items that `shadcn add` installs from.
- **Gallery**: the Vite app that runs every block next to its reference.
- **House style**: the one neutral set of design tokens all blocks share.
