# Logic spec: quirk:interface-design

## Status & amendments

**Status**: Approved · Tech spec: authored (`tech.md`; tier gate fired: crosses subsystems, >3 files)

**Amendments:**
- 2026-11-05: quirk has no README skill table and using-quirk has no skill catalog. The listing becomes README.md's skill-count bullet (30 → 31) plus one clause in its prose list; using-quirk is unchanged.
- 2026-11-05: brainstorming's UX review requires mocks in a neutral house style (`ux-review.md`, research-backed). The user chose: mocks keep the neutral palette and system fonts but adopt system.md's density, spacing base and type scale. SC-11 and the mock decision below are amended to match.

quirk gains a skill, **quirk:interface-design**, that helps an agent build, review and refine product UI in the user's own codebase so the result looks decided rather than defaulted. It merges three upstream sources into one skill written in quirk's voice:

- [Dammyjay93/interface-design](https://github.com/Dammyjay93/interface-design) (MIT), the craft spine
- [vercel-labs web-design-guidelines](https://github.com/vercel-labs/agent-skills/blob/main/skills/web-design-guidelines/SKILL.md) and its [rule list](https://github.com/vercel-labs/web-interface-guidelines) (MIT), the review checklist
- [pbakaus/impeccable](https://github.com/pbakaus/impeccable) (Apache-2.0), the named refine moves, product-UI depth and the detector rules

## Conceptual model

The skill covers **product UI** (dashboards, admin, tools, settings, data views) and **reading surfaces** (docs, help, changelogs), on the web and in native iOS and Android apps. Marketing, landing and portfolio pages are out.

It has three **jobs**. Each job reads one reference file named by SKILL.md:

- **Build** covers new screens and major redesigns, in this order:
  1. Set the intent: who uses it, what verb they're doing, what it should feel like.
  2. Explore the product domain.
  3. Write a direction block: domain concepts, a color world, a signature element, and the defaults it rejects.
  4. Write the code.
  5. Run the four craft tests (swap, squint, signature, token) and a visual check.
  6. Offer to save the system.
- **Review** returns `file:line` findings ranked P0 to P3. They come from the prose checklist, the detector script and the craft tests. Its scope is either named files or the current branch diff. The branch-diff scope replaces upstream's *deslop* command.
- **Refine** applies one named **move** to a target. The moves are every impeccable playbook that works as prose:
  - adapt, animate, bolder, clarify, colorize, delight, distill, extract
  - harden, layout, onboard, optimize, overdrive, polish, quieter, typeset
  - critique, audit (critique and audit run through Review's output format)

The project's design decisions persist in **`.quirk/design/system.md`**. It records:

- the direction and feel
- the depth strategy, spacing base and type scale
- component patterns, with their measurements

Every job reads system.md first when it exists, and holds to it.

The skill is a short **spine** (SKILL.md) plus small reference files one level deep. A **situation → file table** in SKILL.md tells the agent which file to read for each job, move and surface. A stdlib python **detector** catches the rules a regex can see. A **NOTICE.md** records each source's license and pinned commit.

## Data flow

1. **Trigger.** The skill fires on product or reading UI work in the user's codebase. Pages quirk itself generates stay with writing-html-artifacts, and scaffolded apps stay with building-mini-apps. A marketing-page request gets one line saying the skill isn't for that.
2. **Memory.** The agent reads `.quirk/design/system.md` if it exists. Upstream's `.interface-design/system.md` is not read.
3. **Routing.** The situation → file table names the reference for the job (`build.md`, `review.md` plus `checklist.md`, or `moves/<move>.md`). It adds a surface reference when the target is a reading surface or native.
4. **Work.** Build and Refine edit code. When the app can run, the agent checks the result visually at desktop and mobile widths.
5. **Review.** The agent runs the detector over the scope and confirms each hit in context. It then walks the prose checklist for what a regex can't see, applies the craft tests, and returns one ranked list.
6. **Save.** Build, and any Refine that changed tokens or patterns, offers once to save to system.md.

The agent doesn't announce modes or which file it loaded. That carries over upstream's "be invisible" rule.

## Key decisions and rationale

- **One skill with three jobs, no sub-commands.** Users steer with plain words ("make the table quieter", "review this branch"), and only the needed reference loads. A dozen new slash commands would be more to maintain and harder to discover.
- **Short spine, one file per job and move.** A small test found that files SKILL.md links get read 16 of 16 times and an unlinked file 0 of 4. Anthropic's guidance is under 500 lines and one level deep. A single move call reads about 100 lines, not impeccable's 5,300.
- **Rewritten, not vendored.** The three sources contradict each other in places, and impeccable's playbooks call a binary, a live browser and context files quirk doesn't ship. One rewritten skill resolves those once. It costs line-by-line diffability against upstream, which the drift script makes up for.
- **interface-design wins conflicts.** Its Linear and Stripe restraint is the target for product UI.
  - Color is restrained: one accent, for action and state.
  - Product motion is 150 to 250ms and conveys state only.
  - Some impeccable bans clash with conventional product patterns: eyebrow labels, hero metrics, side-stripe callouts, and the Inter and Geist fonts. These become **check-intent** flags at P3 instead of errors.
- **Ranked `file:line` findings.** This keeps Vercel's terse, actionable format and adds impeccable's P0 to P3 triage, so the reader knows what to fix first.
- **A prose checklist plus a detector for the regex-checkable rules.** About 25 of impeccable's rules can be caught with a regex. The roughly 20 that need computed layout or contrast stay prose. The script only proposes candidates; the agent confirms each one before reporting it, so false positives never reach the reader unchecked.
- **The checklist and the detector share rule ids, with no generated registry.** No established tool compiles one rule file into both a checklist and a linter, and a generated checklist reads worse than prose with reasons. A parity test keeps the two aligned instead.
- **Memory at `.quirk/design/system.md`, with no upstream migration.** It sits with quirk's other state. A returning upstream user starts a new system.
- **Vercel's list is bundled as a snapshot.** That keeps reviews offline and repeatable, and no remote text runs as instructions. The drift script shows when the list has moved.
- **The native references are included.** impeccable's iOS and Android files are short and load only for native targets.
- **Brainstorming's mocks borrow the project's structure, not its palette.** When a brainstorm targets the user's product UI and `.quirk/design/system.md` exists, the UX-review mock keeps the neutral house palette and system fonts but adopts system.md's density, spacing base and type scale. Branded mocks pull review toward style and away from flow, which is why the palette stays neutral.

## Behavior and scenarios

### Build

1. **SC-1 A new screen with no saved system**
   - **Given** a project with no `.quirk/design/system.md`
   - **When** the user asks for "a page where on-call engineers triage failed deploys"
   - **Then** ✓ before any code, the agent states the intent (who, verb, feel) and a direction block naming domain concepts, a color world, a signature and at least three rejected defaults; ✓ it asks for confirmation only if the direction is ambiguous or costly to change; ✓ after building it runs the four craft tests and a visual check, and fixes what fails before presenting; ✓ it offers once to save the system
   - **Screen states:**

     | Moment | What the user sees |
     |---|---|
     | Before code | Intent: "On-call engineer at 2am, find the broken deploy, feel like a calm terminal"*; Direction block with Domain, Color world, Signature, Rejecting, Direction |
     | After build | The page, then one line: "Want me to save these patterns to .quirk/design/system.md?" |

2. **SC-2 A screen in a project with a saved system**
   - **Given** a `.quirk/design/system.md` that sets an 8px spacing base, borders-only depth and one teal* accent
   - **When** the user asks for a new settings page
   - **Then** ✓ the agent skips domain exploration and applies the saved decisions; ✓ every spacing value lands on the 8px grid, no shadow is added, and teal is the only accent; ✓ it offers to save only if it created a reusable pattern not yet recorded

### Review

3. **SC-3 Reviewing named files**
   - **Given** `src/Modal.tsx`, `src/Table.tsx` and `src/Button.tsx` in a React and Tailwind project
   - **When** the user asks "review these for UI issues"
   - **Then** ✓ the detector runs over the three files; ✓ the agent confirms each hit in context and drops any that don't hold; ✓ the agent adds findings from the prose checklist and craft tests; ✓ one list comes back grouped P0 to P3, one line per finding as `path:line  rule-id  problem → fix`, followed by a note on what needs a running app to check
   - **Walkthrough:**
     1. The detector reports `src/Button.tsx:12 focus-outline-removed` and `src/Table.tsx:88 tailwind-arbitrary-tiny-text`*
     2. The agent opens Button.tsx:12, sees `outline-none` with no `focus-visible` replacement, and ✓ keeps it as P0
     3. The agent opens Table.tsx:88, sees `text-[10px]` on a table header, and ✓ keeps it as P2
     4. The agent's checklist pass finds Modal.tsx:42 lets focus escape the dialog, and ✓ adds it as P0
   - **Data after:** **Review**: P0 Button.tsx:12, Modal.tsx:42; P2 Table.tsx:88; note: "contrast and overflow need the running app"

4. **SC-4 Reviewing the branch diff**
   - **Given** a branch that changed four UI files
   - **When** the user asks to "clean up the UI slop on this branch"
   - **Then** ✓ Review scopes to the files and lines the branch changed; ✓ findings outside changed lines are left out; ✓ after the list, the agent offers to apply the fixes

5. **SC-5 A check-intent flag**
   - **Given** a settings sidebar with small uppercase group labels
   - **When** Review runs
   - **Then** ✓ the labels appear as P3 check-intent ("eyebrow labels: keep if they group navigation, drop if decorative"); ✗ they are never reported as P0 to P2

6. **SC-6 Drift from the saved system**
   - **Given** system.md records a 6px button radius
   - **When** Review finds a button with a 10px radius
   - **Then** ✓ it reports P1 drift naming both the saved and the found value

### Refine

7. **SC-7 A named move**
   - **Given** a dashboard the user calls "too loud"
   - **When** the user asks to "make it quieter"
   - **Then** ✓ the agent reads only `moves/quieter.md` (plus system.md if present); ✓ the edit keeps the incumbent identity, copy and everything outside the target; ✓ it offers to update system.md if tokens changed

8. **SC-8 A native target**
   - **Given** a SwiftUI project
   - **When** the user asks to polish a settings screen
   - **Then** ✓ the agent reads `moves/polish.md` and `surfaces/ios.md`; ✓ the detector is not run, because it covers CSS, JSX/TSX and Tailwind only; ✓ the review note says the native checks were prose-only

### Boundaries

9. **SC-9 Trigger boundaries**
   - **Given** each request below
   - **When** skills are matched
   - **Then** the outcomes are:
     - (a) "Build a settings page for our admin app" ✓ fires
     - (b) "Make an HTML report of these results" ✗ does not fire (writing-html-artifacts)
     - (c) "Scaffold a mini app for tracking reading" ✗ does not fire (building-mini-apps)
     - (d) "Design our product's landing page" ✗ does not fire, or answers once that it isn't for marketing pages
     - (e) "Improve our docs page layout" ✓ fires with the reading surface

10. **SC-10 Upstream's memory file exists**
    - **Given** a project with `.interface-design/system.md` and no `.quirk/design/system.md`
    - **When** any job runs
    - **Then** ✓ the agent treats the project as having no saved system; ✗ it neither reads nor moves the upstream file

11. **SC-11 Brainstorming mock for product UI**
    - **Given** a brainstorm that adds a screen to the user's app, with a saved system.md
    - **When** the UX-review mock is built
    - **Then** ✓ the mock uses system.md's density, spacing base and type scale; ✗ it keeps the neutral house palette and system fonts, never the saved palette or typefaces

### Maintenance

12. **SC-12 Checking upstream drift**
    - **Given** NOTICE.md pins interface-design at `2f9be3206855`, Vercel's guidelines at `434b7f913646`, Vercel's agent-skills at `1a2c79d4e6c4` and impeccable at `8c7b98c0ae13`
    - **When** a maintainer runs the drift script at release time
    - **Then** ✓ it lists each source's commits and changed files since its pin, using the network; ✗ it never edits the skill
    - **Walkthrough:**
      1. The maintainer runs the drift script
      2. The script reports "impeccable: 14 commits*, changed skill/reference/polish.md, craft-floor.md*" and "interface-design: no change"
    - **Data after:** **NOTICE.md** unchanged until the maintainer rewrites the affected files and bumps the pins by hand

## Scope and non-goals

In scope:
- the skill, its references, the detector, the drift script, NOTICE.md and trigger evals
- one rule added to the "Look and content" list in brainstorming's `ux-review.md`
- README.md's skill-count bullet and one clause in its prose list

Out of scope:
- marketing, landing and portfolio pages (impeccable's Persuade and Experience modes)
- impeccable's binary, its live-browser variant mode, hooks, doctor, PRODUCT.md and DESIGN.md, and image-generation component specs
- fetching Vercel's list live
- reading or migrating `.interface-design/`
- a full-code-review UI lens (deferred)
- detector coverage for Vue, Svelte and plain HTML, which fall back to the prose checklist
- changes to writing-html-artifacts' design reference or building-mini-apps' styles

**Done means:**
- the trigger evals pass, including SC-9's negative cases
- the detector's pytest fixtures pass, with zero findings on a clean sample
- the rule-id parity test passes
- one dogfood run (Build, then Review, on a real screen) yields a ranked review worth acting on

## Decisions Locked

**Structure**
- Shape: one skill with three jobs (Build, Review, Refine)
- Review output: `file:line` findings ranked P0 to P3
- Slop detector: a prose checklist, plus a python script for the regex-checkable rules
- Design memory: `.quirk/design/system.md`

**Upstream sync**
- Content: rewritten in quirk's voice, with attribution
- Conflicts: interface-design wins for product UI; impeccable's bans become P3 check-intent flags
- Vercel list: bundled as a snapshot
- Drift: pinned SHAs in NOTICE.md, plus a maintainer check script

**Triggering and overlap**
- Trigger: product UI in the user's codebase; quirk's own pages stay with writing-html-artifacts
- writing-html-artifacts' design-reference.md: left separate
- UX mocks: neutral palette and system fonts, with system.md's density, spacing base and type scale (amended)
- full-code-review lens: deferred

**Scope of surfaces**
- Surfaces: product UI plus docs and reading surfaces; marketing out
- Native: iOS and Android references included
- Refine moves: every prose-portable impeccable move
- Detector targets: CSS, JSX/TSX and Tailwind classes

**Success**
- Ship bar: trigger evals, detector fixtures, the parity test and one dogfood run
- Upstream `.interface-design/system.md`: ignored

**Approach**
- Short spine, one reference file per job and move; the checklist and the detector share rule ids

**UX review:** skipped, because the deliverable is an agent skill, not a screen.

## Industry Insights

- **Defaults win without concrete counter-moves.** Anthropic calls this "distributional convergence", and suppressing one default shifts the model to the next ([Anthropic](https://claude.com/blog/improving-frontend-design-through-skills)). A study of 120 generated interfaces found over 25% of stated design rationales went unimplemented ([Design Theater, arXiv:2607.22928](https://arxiv.org/abs/2607.22928)). This is why Build ends with checks against the built result, not just the stated intent.
- **Checklists fix consistency, not taste.** Commenters on impeccable said it helps with consistency and accessibility, but "the design itself is the same" ([HN](https://news.ycombinator.com/item?id=49058547)). Reviewers likewise call Vercel's list a checklist, not an art director. This is why interface-design's direction step leads and the checklists follow.
- **Linked references load; unlinked ones don't.** Files SKILL.md linked were read 16 of 16 times, and an unlinked one 0 of 4 ([dev.to test](https://dev.to/rulestack/13-of-16-claude-code-runs-loaded-the-skill-script-the-docs-call-executed-not-loaded-5cic)). Anthropic's guidance is SKILL.md under 500 lines, references one level deep, and a table of contents on any reference over 100 lines ([Anthropic best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)).
- **File structure showed no measurable effect on adherence.** A 1,650-session study found none; adherence dropped within a session instead ([arXiv:2605.10039](https://arxiv.org/abs/2605.10039)). Instruction density does cost adherence, since top models hit about 68% at 500 instructions ([IFScale](https://arxiv.org/pdf/2507.11538)). So the skill loads only what the job needs.
- **Rules-as-data has no established tool.** Mergify runs single-purpose AI linters as YAML plus prompt files, commenting only at high confidence ([Mergify](https://mergify.com/blog/goodbye-checklists-hello-ai-linters)). Semgrep warns that broad custom rules are noisy. This is why the detector only proposes and the agent confirms.
- **impeccable's own structure.** Its rule registry is data (`crates/foundation/src/registry.rs`), while the checks are about 20k lines of Rust. Some 18 of the 62 rules are marketing-page tells, which this skill skips.

## Deferred Ideas

- A full-code-review UI lens that runs Review on diffs touching UI files (to be logged in DEFERRED.md)
- Detector coverage for Vue, Svelte and plain HTML templates
- `[tech-spec]` How detect.py tells Tailwind class strings apart from other strings in JSX/TSX
- `[tech-spec]` The exact rule-id scheme, and which ~25 rules the detector owns

## Glossary

- **Job:** Build, Review or Refine, one of the skill's three kinds of work.
- **Move:** one named Refine playbook, such as polish, harden or quieter.
- **Surface:** product UI, reading, iOS or Android; it decides which extra reference loads.
- **system.md:** the project's saved design decisions at `.quirk/design/system.md`.
- **Direction block:** Build's five-line proposal (domain, color world, signature, rejecting, direction).
- **Craft tests:** swap, squint, signature and token, the checks Build runs before presenting.
- **Check-intent flag:** a P3 finding that asks for a reason, not a change.
- **Rule id:** the stable name a rule has in both `checklist.md` and the detector.
- **Detector:** the stdlib python script that flags regex-checkable rules for the agent to confirm.
- **Spine:** SKILL.md, the always-loaded part of the skill with the situation → file table.
