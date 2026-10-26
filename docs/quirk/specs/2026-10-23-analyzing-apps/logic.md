# Logic spec: analyzing an app for `building-mini-apps`, from study to clone blueprint

## Status & amendments

**Status**: Approved · Tech spec: authored (`tech.md`; tier gate fired: >3 files across guide, SKILL.md, two scripts and tests)

**Amendments:** none yet.

The first ten patterns came from a study process that only lives in the original spec
(`docs/quirk/specs/2026-10-22-building-mini-apps/`). An agent asked today to "analyze Sentry as a mini
app" has nothing in the skill to follow. This adds a guide to the skill for that ask. It studies a new
app the way the first ten were studied, extracts its reusable patterns and the components they need, and
writes a blueprint for how the patterns combine into a close clone. The library grows by one app and by
whatever new patterns the blueprint proposes and I approve.

A close clone matches the app's screens, layout, flows, keys and states. It keeps our neutral house
style, and its UI never names the studied app or uses its brand assets.

## Conceptual model

| Piece | What it is | Who reads it |
|---|---|---|
| Guide | `references/analyzing-apps.md`: the full procedure for "analyze <app> as a mini app" | The agent running an analysis |
| SKILL.md section | "Analyzing an app": the trigger, the two stops, and a link to the guide. The frontmatter description gains the "analyze <app> as a mini app" phrasing so the skill fires on it | The agent deciding what to do |
| Study note | `references/apps/<app>.md`, in today's format (Sources, Observations, Unseen, Patterns fed) | The agent writing the blueprint, and me |
| Blueprint | `references/blueprints/<app>.md`, a new doc type: the clone's build plan | Me at the second stop; the build flow when I later ask for the clone |
| Capture script | `scripts/capture.py`: search, download, frame extraction and video deletion as one command | The capture subagents |
| Blueprint check | `check_docs.py blueprint <app>`: required headings, one coverage row per confirmed job, every row citing an observation that exists | The agent before each stop, and the tests |

A blueprint has six parts:

- **Core jobs**: what users come to the app to do, as I confirmed them.
- **Screens**: one entry per distinct screen or state the jobs touch.
- **Coverage**: one row per job and per screen, marked matched, approximated (and how) or left out (and
  why), naming the pattern that serves it and the study-note observation it rests on.
- **Composition**: how the patterns share one shell, store and keyboard layer, and the app's real
  domain model (for an error tracker: issues, events, releases).
- **Proposed patterns**: every interaction no existing pattern covers, each with the components it
  needs and any new dependency and why.
- **Proposed revisions**: additive changes to existing patterns that the new app does better.

Patterns stay the installable unit. A component (a sparkline, a stack-trace frame) is built inside the
block of the pattern that needs it.

## Data flow

An analysis runs six steps in order, with two stops where I decide.

1. **Preflight.** The run needs the skill's own folder to be a writable quirk checkout, plus yt-dlp,
   ffmpeg and playwright-cli. If anything is missing it says which and stops.
2. **Jobs.** The coordinating agent reads the app's public site and docs, proposes the core jobs, and
   writes them into the blueprint. **Stop 1:** I confirm or edit the list. Nothing is captured before
   this.
3. **Survey.** It lists candidate sources in the study note's Sources table: official videos, docs
   pages, a public no-login demo or sandbox if one exists, and third-party walkthroughs.
4. **Capture.** One subagent per source. A video goes through `capture.py`. A public demo is driven
   with Playwright, triggering empty, error, loading, hover and keyboard states on purpose. Each
   subagent returns observation bullets that cite a frame and name the jobs they feed. The coordinator
   checks that every cited frame and source ID exists before appending a bullet to the study note. The
   step repeats until every confirmed job's flow and its empty, error and loading states have a cited
   frame or an Unseen entry.
5. **Blueprint.** The coordinator writes the screens, maps each to a pattern, fills the coverage table
   and composition, and lists the proposed patterns and revisions. `check_docs.py` must be clean on both
   the study note and the blueprint. **Stop 2:** I pick which proposals to build.
6. **Build approved proposals.** Each approved pattern goes through the same reference-then-block flow
   the first ten used and joins the registry, the gallery and the pattern index. Each approved revision
   lands in its pattern's reference and block.

The blueprint and study note are the run's state. A run that resumes after a stop, or in a new session,
reads them rather than the chat history. Building the clone app is a separate, later request: the build
flow reads the blueprint first and scaffolds from the patterns it names.

## Key decisions & rationale

**Changes to the skill's rules**

- **"Cut by pattern, not by app" gets one exception.** Patterns stay app-agnostic. The blueprint is the
  one place an app is the unit, and it composes patterns without forking them.
- **"Copy behavior, not appearance" now covers layout too.** A clone matches screens, panel arrangement,
  navigation, keys and states. Colors, type, icons and copy stay in the house style, and the clone's UI
  never says the studied app's name. Trade dress protects a distinctive overall look, so structure and
  behavior keep the clone on the functional side.
- **"Never make one pattern import another" stands.** A component lives inside the block that needs it.
  When two patterns need the same component, each holds its own copy.
- **"Ask before adding dependencies" is met at Stop 2.** The blueprint names each proposed dependency
  and why, my approval there covers it, and it goes into that pattern's registry item only.

**Decisions for the guide**

- **Jobs first.** The order is jobs, then flows, then screens, then patterns. It gives the coverage
  table its rows and keeps the inventory to screens a job needs.
- **Every distinct gap becomes a proposed pattern.** It is named for the interaction, not the app
  (`stack-trace`, not `sentry-issue`), and like every pattern reference its When to use must fit an app
  other than the one studied.
- **Revisions are additive only.** New optional props and behaviors; existing keys and API stay. A change
  that would break the API is proposed as a new pattern instead.
- **No capture cap.** The first study capped each app at 3 videos and about 60 frames. Here coverage is
  the stopping rule. `capture.py` still deletes each video once its frames are out.
- **Public demos are fair game; accounts are not.** A no-login demo or sandbox may be driven freely.
  Signing up anywhere needs my yes, and the run carries on with other sources while it waits.
- **Evidence is checked mechanically.** Every observation's frame and source must exist, and every
  coverage row's observation must exist. Research agents hallucinate a share of their citations, so the
  coordinator checks rather than trusts.
- **Judgment stays in one agent; extraction fans out by source.** No two capture subagents share a
  decision, so their outputs don't conflict, and the heavy image reading stays out of the coordinator's
  context.
- **Frames stay local.** `references/media/<app>/` stays gitignored, and everything committed is text.

## Behavior & scenarios

1. **SC-1: Analyze Sentry**
   - **Given** a writable quirk checkout with yt-dlp, ffmpeg and playwright-cli installed
   - **When** I say "analyze Sentry as a mini app"
   - **Then** the run proposes core jobs and waits for me. After I confirm, it captures public sources
     one subagent per source, writes the study note and the blueprint, gets a clean `check_docs.py` on
     both, and stops with the proposed patterns, revisions and dependencies listed for me to pick from
   - **Walkthrough:**
     1. The coordinator reads Sentry's public site and docs and proposes five jobs: triage a new
        issue*, find the release that introduced it*, read a stack trace and breadcrumbs*, see whether
        error volume is rising*, assign or resolve an issue*.
     2. I confirm the list at Stop 1 ✓.
     3. The survey lists 2 official videos*, 4 docs pages*, a public demo* and 1 third-party
        walkthrough*.
     4. Eight capture subagents run, one per source, and return observation bullets; the coordinator
        appends the ones whose frames exist.
     5. Coverage reaches every job; "bulk-merge similar issues" is marked unseen because no public
        source shows it*.
     6. The coordinator writes the blueprint and runs `check_docs.py` on both files ✓ clean.
   - **Data after:** **references/apps/sentry.md**: ✓ written; **references/blueprints/sentry.md**: ✓
     written, five coverage rows for jobs; **Stop 2 list**: proposed patterns `stack-trace`* and
     `event-sparkline`*; one revision to action-palette* (an optional multi-item target*); proposed
     dependencies: none*

2. **SC-2: Run from an installed plugin copy**
   - **Given** the skill folder is an installed plugin copy, not a quirk checkout
   - **When** I ask to analyze an app
   - **Then** preflight says the library can't be written from here and stops before capture

3. **SC-3: A job's core interaction is behind a login**
   - **Given** no public source shows how a confirmed job is done
   - **When** capture reaches that job
   - **Then** it is recorded as unseen with the reason, I am asked whether to sign up, and the run carries
     on with other sources. It never creates an account itself

4. **SC-4: A capture subagent cites a frame that doesn't exist**
   - **Given** a subagent returns a bullet citing a frame that is not on disk
   - **When** the coordinator checks the bullet
   - **Then** the bullet is rejected and never reaches the study note; the coordinator reruns that
     source's extraction or records the observation as unseen
   - **Data before:** **Subagent result for S3***: 12 bullets; one cites `S3-t0410.png`*, which is not
     in `references/media/sentry/`
   - **Data after:** **Study note**: ✓ 11 bullets appended; ✗ the `S3-t0410.png` bullet rejected

5. **SC-5: Building approved proposals in a new session**
   - **Given** a Sentry blueprint at Stop 2, and a new session
   - **When** I say "build stack-trace and event-sparkline from the Sentry blueprint"
   - **Then** the agent reads the blueprint, builds only those two patterns through the
     reference-then-block flow, and adds them to the registry, the gallery and the pattern index. The
     other proposals stay listed and unbuilt
   - **Data before:** **Pattern index**: 10 patterns; **Sentry blueprint**: 2 proposed patterns*, 1
     proposed revision*
   - **Data after:** **Pattern index**: ✓ 12 patterns; **Sentry blueprint**: the revision still
     proposed

6. **SC-6: Building the clone later**
   - **Given** a Sentry blueprint whose proposed patterns are built
   - **When** I ask for "a Sentry-like error tracker"
   - **Then** the build flow reads `blueprints/sentry.md` first, scaffolds from the patterns it names,
     and adapts them to the blueprint's domain model. The app's UI never says "Sentry"

## Scope & non-goals

In scope: the guide, its SKILL.md section and trigger, `capture.py`, the blueprint check in
`check_docs.py` (with its app list growing as the library does), tests for both scripts, and an
acceptance run on Sentry through Stop 2.

Not in scope:

- Building Sentry's proposed patterns. That follows Stop 2, when I approve them.
- Building the Sentry clone app.
- Writing blueprints for the existing ten apps.
- Per-app themes or any exception to the one house style.
- Visual comparison of a clone against reference frames.
- Committing frames or videos.
- Creating accounts without asking.

## Decisions Locked

**What an analysis produces**
- A study note, a clone blueprint, and new patterns for the gaps I approve.
- Patterns stay the unit; the blueprint also names the components each pattern needs, built inside
  that pattern's block.
- The blueprint is its own file, `references/blueprints/<app>.md`.
- Output goes into the skill's own library; the studied app becomes the next study note.
- When the new app does an existing pattern better, the pattern is revised.

**How close a clone gets**
- Screens, layout, flows and behavior match; the look stays the house style.
- The blueprint uses the app's real domain model and field names.
- Closeness is shown by a coverage table of core jobs and screens.

**Interactions no pattern covers**
- Every distinct gap becomes a proposed pattern.
- The run stops after the blueprint and I pick which proposals to build.
- Revisions are additive only.
- New dependencies are allowed per pattern, named in the blueprint for my approval.

**How deep an analysis goes**
- Jobs, then flows, then screens, then patterns.
- No capture cap; the run goes until coverage is complete.
- Public no-login demos may be driven; ask before any signup.
- I confirm the core jobs before capture starts.

**Guide form**
- `references/analyzing-apps.md`, routed from a short SKILL.md section.
- `check_docs.py` gains a `blueprint` kind, and a new `capture.py` wraps capture.
- Proven by running it on Sentry through Stop 2.

**Approach**
- One coordinating agent for judgment; one capture subagent per source; state in the blueprint and
  study note.

## Industry Insights

- **Inventory one instance of each unique pattern, and settle names during the inventory.** Brad
  Frost's interface inventory captures one of each distinct pattern, not every occurrence, and agrees on
  names before moving the result into a library.
  ([Frost 2015](https://bradfrost.com/blog/post/conducting-an-interface-inventory/),
  [Atomic Design ch. 4](https://atomicdesign.bradfrost.com/chapter-4/))
- **Choose the entry point by the goal.** Component-first inventories suit a pattern library;
  scope-first (screens and flows) suits understanding how an app fits together.
  ([UX Collective](https://uxdesign.cc/entering-atomic-design-from-the-screen-bae744ecc288),
  [LogRocket](https://blog.logrocket.com/product-management/product-teardown-process-tools/))
- **A screenshot holds one state.** Hover, focus, empty, error and overflow states are invisible
  unless triggered before capture, and keyboard and focus behavior is the layer most often lost.
  ([Digital Applied](https://www.digitalapplied.com/blog/screenshot-driven-ui-development-vision-models-2026),
  [02ui](https://02ui.com/blog/how-to-reverse-engineer-an-app-with-ai/))
- **Trade dress protects the distinctive overall look, not function.** A claim needs non-functionality,
  distinctiveness and likely confusion; a near-copy can be enjoined fast.
  ([AIPLA](https://www.aipla.org/list/innovate-articles/does-this-web-dress-make-my-site-look-distinctive),
  [WHOOP v. Lexqi](https://hlth.com/insights/news/federal-court-grants-whoop-preliminary-injunction-against-lexqi-over-wearable-design-2026-02-05))
- **Fan-out costs tokens and duplicates work when briefs are vague.** Multi-agent research used about
  15x chat tokens, and early versions had subagents repeat each other's searches.
  ([Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system))
- **Subagents lose shared decisions.** Workers that can't see each other's choices produce parts that
  don't fit, so split only work that shares no decision.
  ([Cognition](https://cognition.com/blog/dont-build-multi-agents))
- **Check citations mechanically.** Research agents hallucinated 3-13% of citation URLs; a mechanical
  check cut unresolvable ones to under 1%. ([arXiv 2604.03173](https://arxiv.org/abs/2604.03173))
- **Long runs need state on disk.** Context quality falls as input grows, and after long pauses models
  invent steps that never happened; long-running harnesses resume from a progress file and git.
  ([Chroma](https://www.trychroma.com/research/context-rot),
  [Anthropic harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents),
  [Google ADK](https://developers.googleblog.com/build-long-running-ai-agents-that-pause-resume-and-never-lose-context-with-adk/))

## Deferred Ideas

- Promoting a component that several patterns copy into the base. Decide once two patterns actually
  hold the same component.
- Blueprints for the existing ten apps.
- A `new_pattern.py` that stubs a pattern's reference, block folder and registry entry. Offered and not
  chosen.
- `[tech-spec]` Where the run's progress lives inside the blueprint and study note (a status column on
  Core jobs, or a separate section), and how a resumed run detects stale entries.
- `[tech-spec]` The shape of a capture subagent's result, and how the coordinator matches cited frames
  and source IDs.

## Glossary

- **Core job**: something a user comes to the app to do. The unit the coverage table measures.
- **Blueprint**: an analyzed app's clone plan: core jobs, screens, coverage, composition and proposals.
- **Coverage table**: the blueprint's rows marking each job and screen matched, approximated or left
  out, with the pattern and the observation behind it.
- **Proposal**: a new pattern or an additive revision the blueprint asks to build.
- **Stop 1 / Stop 2**: the two points where the run waits for me: confirming the jobs, then picking
  proposals.
- **Coordinator**: the one agent that proposes jobs, checks and merges observations, and writes the
  blueprint.
- **Capture subagent**: an agent that turns one source into cited observation bullets.
- **Component**: a piece smaller than a pattern, built inside the block of the pattern that uses it.
