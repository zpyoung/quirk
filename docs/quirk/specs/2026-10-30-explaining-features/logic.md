# Logic spec: `explaining-features`, an evidence-first feature explainer skill

**Status**: Approved · Tech spec: authored (`tech.md`; tier gate fired: touches >3 source files across four skills)

On 2026-10-30 a session finished the Add project header button in the quirky repo, then made a
walkthrough at the user's request: a 58 s narrated video inside one offline HTML report, with
screenshots, behavior, how it's built, what was verified and what's still open. The user's verdict was
"This was great. Let's make a quirk skill for explainers like this."

That result took three skills and 621 lines of throwaway scripts, and it worked around gaps in all
three skills. This skill makes the same kind of result repeatable and closes those gaps.

## Conceptual model

**One explainer is one page about one feature, at one commit, for one reader, showing only what was
really run.** The skill runs in order and hands work to three existing skills. It doesn't render
video, drive apps or build pages itself.

| Thing | Where | What it holds |
|---|---|---|
| Evidence ledger | `~/Studio/explainers/<date>-<slug>/` | One row per behavior: the claim, the result, how it was checked, where the proof is |
| Film | `~/Studio/videos/<date>-<slug>/`, through `making-videos` | One narrated MP4, when the behavior moves |
| Page | `<project>/.quirk/html/`, through `writing-html-artifacts` | One self-contained HTML file with everything inline |
| Page source and scripts | the same explainer folder as the ledger | What rebuilds the page if the worktree goes, and how the footage was made |

The ledger is the new idea, and everything else comes from it. The film shows only behavior with a
result in the ledger. The page's results table is the ledger. "What's still open" is the unproven rows
plus anything cut.

## Data flow

1. **Plan.** The skill states the feature, reader, commit, and film or no film in one line, and doesn't
   wait for a reply. If the film needs an install, it asks now, because `making-videos` never installs
   unasked.
2. **Evidence.** It reads the spec, existing app runs and tests into the ledger. If the main behavior
   was never run for real, it verifies it with `using-apps-like-a-user`, or runs the real command or
   test for a feature with no UI.
3. **Stage.** It starts a private instance with seeded data, building that data if the repo has none,
   and builds the parent commit for "before".
4. **Capture.** It takes screenshots and footage, then reads the screenshots and sampled frames looking
   for real data.
5. **Film.** It runs `making-videos` with no stops, then sorts any `verify` failures.
6. **Page.** It builds the page with `writing-html-artifacts`, compressing the video so everything fits
   in one file.
7. **Hand over.** It gives the path, the `verify` result and what was cut, and warns that the page
   disappears with the worktree.

Only three things stop a run after the plan: the main behavior doesn't work, the feature can't be run
at all, or real data shows on screen.

## Key decisions and rationale

- **A new thin skill plus small fixes to the three it uses,** not a mode in `making-videos` and not a
  self-contained pipeline. Two facts in this repo decide it. No-UI features get a page with no film,
  which doesn't fit a skill whose job ends in an MP4. And "no stops" directly contradicts "Steps 4 and 7
  are stops" in `making-videos`, so that skill needs a supported setting; a parent skill can't simply
  overrule it.
- **The results table is the proof, and the film is a tour of it.** A recording shows one run. It can't
  show a measurement, keyboard reach or error handling. The example's strongest claims (the funnel's
  left edge at 261.8px in both states) came from measurements, not footage.
- **No stops by default.** The script comes from verified evidence, so a wrong direction is less likely
  than in a video made from a brief. The user skipped both stops on the example and liked the result.
  If the direction is wrong anyway, the whole render is wasted, and notes make a v2.
- **Verify first when nothing was run.** An explainer of code nobody ran can look finished and
  authoritative, so the minimum is that the main behavior was run for real.
- **Staging is always disclosed.** The example disclosed the drawn pointer and overlays but not the
  fixture or how "before" was built. A reader shouldn't have to guess which is which.
- **Frozen, not refreshable.** Refreshing would mean keeping capture scripts running as the app changes,
  which is a second test harness nobody owns. To update an explainer, run the skill again.
- **The page doesn't say "I".** It gets forwarded without its sender, and the example's "I didn't want a
  second instance interfering" would read as the user speaking.
- **Video length aims under 90 s partly because of file size.** At the example's bitrate, 90 s plus its
  screenshots comes to about 9.6 MB (a 6.2 MB video is 8.3 MB as base64, plus 1.3 MB of page and images),
  right at the page's 10 MB limit.

## Behavior and scenarios

### The main paths

1. **SC-1 A finished web feature with evidence, and a behavior that moves**
   - **Given** a feature just finished and verified in the real app, and a request to "make a walkthrough"
   - **When** the skill runs
   - **Then** the user gets one offline page with a narrated film under 90 s at the top, with no stops
     along the way. The note gives the path, the `verify` result, what was cut, and a warning that the
     page disappears with the worktree.
   - **Data before:** **Spec**: 9 scenarios*; **Earlier QA run**: 6 results*; **Measurements**: funnel left edge at 261.8px*
   - **Walkthrough:**
     1. The skill states its plan: this feature, a technical teammate, this commit, a film because the
        button grows on hover. It doesn't wait.
     2. It reads the spec and the earlier run into the ledger.
     3. It stages a private instance with seeded data and builds the parent commit.
     4. It captures footage and screenshots, and reads the frames for real data.
     5. `making-videos` renders the film with no stops, and `verify` comes back clean.
     6. `writing-html-artifacts` builds the page.
   - **Data after:** **Ledger**: ✓ one row per behavior; **Film**: ✓ 58 s*; **Page**: ✓ one file under 10 MB; ✓ nothing shared

2. **SC-2 A shipped feature with no evidence**
   - **Given** a feature on the main branch that nobody verified in the app
   - **When** the user asks for an explainer
   - **Then** the skill verifies the behaviors with `using-apps-like-a-user` first, and every ledger row
     comes from that run. Behaviors it couldn't check are listed as not proven.

3. **SC-3 Verifying finds a bug**
   - **Given** a feature whose main behavior doesn't work as the spec says
   - **When** verification shows it
   - **Then** the skill stops before building anything and tells the user what it saw, with the
     screenshot. It doesn't render a film or write a page around it.

4. **SC-4 A change with nothing moving**
   - **Given** a feature that's visible but static, such as a new label or layout
   - **When** the skill plans
   - **Then** the plan line says "no film, because nothing moves", and the user can override it. The page
     has screenshots and text.

5. **SC-5 A different reader**
   - **Given** a request that says the explainer is for customers
   - **When** the page is written
   - **Then** "How it's built", scenario IDs, branch names and commits come out, and the rest is rewritten
     in the reader's terms. "What's still open" stays, in those terms too.
   - **Copy examples:**

     | For a teammate | For a customer |
     |---|---|
     | Native desktop window not driven. WebKit 27.2 stands in for the desktop engine. | Not yet tried in the desktop app. |
     | SC-2 hover: Pass, real mouse events | Hovering over the button shows its full label. |

6. **SC-6 The user asks for review**
   - **Given** a request that says "let me see the storyboard first"
   - **When** the skill runs
   - **Then** the film path keeps the `making-videos` stops the user asked for. Without that request there
     are none.

7. **SC-7 Notes after hand-over**
   - **Given** a delivered page and a note that one line of narration is wrong
   - **When** the user sends the note
   - **Then** a film change makes a new version under the `making-videos` rule that versions are never
     overwritten, and the page is rebuilt from its source. A text-only note rebuilds the page without
     rendering.

### When the evidence falls short

8. **SC-8 A feature with no UI**
   - **Given** a new CLI flag
   - **When** the skill runs
   - **Then** the user gets a page with real command output and test results and no film. Any diagram is
     labeled as a diagram.

9. **SC-9 A native app**
   - **Given** a feature in a native macOS app
   - **When** the skill plans
   - **Then** the app is driven with `using-apps-like-a-user` and the page uses its screenshots. There's no
     film because `making-videos` can't record native apps, and the page lists that as a cut.

10. **SC-10 No seeded data in the repo**
    - **Given** a repo with no fixture or seed data
    - **When** the skill reaches staging
    - **Then** it builds its own seeded data, and the video caption discloses it.

11. **SC-11 The parent commit won't build**
    - **Given** a parent commit that fails to build
    - **When** the skill reaches "before"
    - **Then** it describes "before" in words from the old code or spec and says no footage was captured.
      It never mocks up or rebuilds the old screen.

12. **SC-12 The feature can't be run at all**
    - **Given** a feature behind a login wall, hardware or a service the agent can't reach
    - **When** verification comes back blocked on the main behavior
    - **Then** the skill stops and says what blocked it. It doesn't produce a page from reading the code.

13. **SC-13 Too much for 90 seconds**
    - **Given** work whose behaviors won't fit in a 90 s film
    - **When** the skill plans
    - **Then** it makes a short clip per behavior, each beside its section, sharing the 10 MB budget. A
      single feature that fits still gets one film.

14. **SC-14 A film needs an install**
    - **Given** a behavior that moves, and Playwright or the voice tools missing
    - **When** the skill plans
    - **Then** it asks about the install in the plan step, before the user walks away. If the user declines,
      the page has no film and lists that as a cut.

15. **SC-15 Not on macOS**
    - **Given** a Linux or Windows machine
    - **When** the skill is invoked
    - **Then** it says the skill is macOS only and stops, because `making-videos` and
      `using-apps-like-a-user` both are.

### When checks fail

16. **SC-16 `verify` stops on a polish failure**
    - **Given** a film that hit 3 failed `verify` attempts on `sync`
    - **When** the skill reads the result
    - **Then** the film ships, and "What's still open" states the failure.
    - **Data before:** **verify**: `sync` failed; labels 35 to 87 ms from their words; all other checks clean
    - **Walkthrough:**
      1. The skill finds `sync` in the polish group.
      2. It keeps the film and adds a row to "What's still open".
    - **Data after:** **Page**: ✓ film included; ✓ "Three labels land 35 to 87 ms from their spoken words"

17. **SC-17 `verify` stops on anything else**
    - **Given** a film that hit 3 failed `verify` attempts
    - **When** the skill reads the result
    - **Then** the outcome depends on the check, as below.
    - **Outcome by check:**

      | Failing check | Group | What happens |
      |---|---|---|
      | `sync`, `loudness` | Polish | Film ships, failure listed as open |
      | `fonts`, `render_log`, `contrast`, `title_safe`, `captions`, `blender` | A viewer would notice | Film left out, and the page says why |
      | `outside_calls` | A cloud call nobody named | Run stops, and the skill tells the user |

18. **SC-18 Real data on screen**
    - **Given** seeded data, and a frame that shows a real home directory path
    - **When** the skill reads the frames
    - **Then** it stops and tells the user which frame. The note on any finished run says the frame check
      was the agent's, because small or fleeting text can get past it.

### Honesty on the page

19. **SC-19 The summary names the biggest gap**
    - **Given** a feature tested in the browser engines but not its desktop window
    - **When** the page is written
    - **Then** the summary under the title says so. The film doesn't, by the user's choice, so the MP4 alone
      looks fully proven. That's why the page's summary has to.

20. **SC-20 What the film can show**
    - **Given** a ledger row marked not proven
    - **When** the script is written
    - **Then** that behavior doesn't appear in the film. A behavior that's true but unchecked gets checked
      or left out.

21. **SC-21 Staging in the caption**
    - **Given** a film made with seeded data, a drawn pointer, added labels and a separately built "before"
    - **When** the page is written
    - **Then** the video's caption names all of them, plus any sped-up waits.

22. **SC-22 Reasoning in "How it's built"**
    - **Given** a design reason with no test behind it
    - **When** the page is written
    - **Then** it stays only if it names the code or spec it came from. Behavior claims need a ledger result.

23. **SC-23 A dated record**
    - **Given** an explainer opened a year after it was made
    - **When** someone reads it
    - **Then** near the top they see the date, branch and commit, and "this shows the app at this commit".
      Nothing checks whether the app has moved on.

### Triggering

24. **SC-24 Which skill fires**
    - **Given** the requests below
    - **When** the model picks a skill
    - **Then** it picks as below, and nothing offers an explainer when a branch finishes.
    - **Routing:**

      | Request | Skill |
      |---|---|
      | "Make a walkthrough of this feature" | `explaining-features` |
      | "Explain what this PR does, with screenshots" | `explaining-features` |
      | "Make a 30 second video announcing our release" | `making-videos` |
      | "Build a dashboard page for these numbers" | `writing-html-artifacts` |
      | "Try this flow in the app" | `using-apps-like-a-user` |

### Fixes to the existing skills

Each is useful without the new skill, and none changes what the skill does for someone who doesn't use
the new option.

25. **SC-25 `making-videos`: no-stops setting**
    - **Given** a brief with the no-stops setting on
    - **When** the pipeline runs
    - **Then** it goes through both stops without waiting and still writes the review page. A brief without
      the setting stops twice as it does today.

26. **SC-26 `making-videos`: richer recordings**
    - **Given** a web app flow with a hover, a key press and a drag, recorded at 2x
    - **When** the recording runs
    - **Then** those steps work without a custom script, and the frames are true 2560x1440, not a 1x page in
      the corner of a 2x canvas. A visible pointer follows the real mouse events.

27. **SC-27 `using-apps-like-a-user`: hover**
    - **Given** a control that changes only on hover
    - **When** the agent hovers over it
    - **Then** the action goes through `act` and reports `OBSERVED` or `NO_EFFECT` like any other. A hover
      that changes nothing can't count as proof.

28. **SC-28 `writing-html-artifacts`: inline media**
    - **Given** a source that names a local MP4, a captions file, a poster and images
    - **When** the page builds
    - **Then** they end up inline in the one file, with captions on, and no hand-written base64. Figures in a
      `q-grid` don't collapse to a quarter-width column by surprise. The 10 MB limit still fails the build,
      and the 2 MB warning stays in the note.

## Scope and non-goals

In scope: one feature per explainer, from any repo the agent can run; web, Electron and native apps for
evidence; CLI and backend features as a page with no film; the fixes above.

Out of scope:

- Publishing, or attaching to a PR, unless the user asks in that run
- Refreshing an old explainer in place
- Whole-release or epic roundups
- Recording native macOS apps
- Adding a fixture to the user's repo
- Offering an explainer when a branch finishes
- Linux and Windows
- The broken Homebrew node on this Mac (`libllhttp.9.3.dylib` missing). That's a machine fix, and doesn't
  belong in a skill.

## Decisions Locked

No decision here was fast-tracked. Each was answered by the user during drill-in.

**What it explains**
- Any feature the agent can run: this session's work, a branch or PR, or something shipped.
- Nothing verified yet: verify first, then explain.
- One feature per explainer. Larger work gets a clip per behavior.
- Runs only when asked.

**Who reads it**
- Default reader: a teammate or reviewer who knows the code.
- Another named reader changes both sections and wording.
- "What's still open" stays for outside readers, in their terms.
- The page doesn't say "I". It states what was measured and how.

**The video**
- A film when the behavior moves. The plan says which and can be overridden.
- One narrated film at the top of the page.
- Aim under 90 s.
- The film doesn't state what wasn't proven; the page does. The user chose this against the recommended
  end-card line, knowing an MP4 shared alone looks fully proven.

**Review and failed checks**
- No stops by default. The page is the review, and notes make a v2.
- `verify` failures sort by severity, as in SC-17.
- A broken main behavior stops the run before anything is built.

**What the footage counts as**
- The film shows only behavior with a result on the page.
- All staging goes in the video caption.
- Reasoning stays if it names the code or spec it came from.

**Where it lives and how it ages**
- The page lands in the project's `.quirk/html`. The user chose this against the recommended `~/Studio`,
  knowing it disappears with the worktree. Its source and the MP4 stay in `~/Studio`.
- Always one file, with the video compressed to fit.
- The skill gives the path and shares only if asked.
- A dated record of one build.
- Scripts stay in the project folder as a starting point for the next explainer, labeled as not guaranteed
  to run.

**What can appear on screen**
- Seeded data only. The agent checks the frames, with no extra stop.

**When the evidence falls short**
- No seeded data: build it and disclose it.
- No UI: a page with real output and test results.
- No "before": words, disclosed, never a mock-up.
- Minimum: the main behavior was run for real.

**Approach and acceptance**
- A new thin skill plus fixes to the three it uses.
- Done means remaking the add-project explainer and comparing it, as described below.

## Done when

- Trigger evals exist for `explaining-features` and are re-run for `making-videos`, covering SC-24.
- Each fix in SC-25 to SC-28 has its own tests.
- The honesty rules (SC-19 to SC-22, and the three stops) have pressure scenarios, because those are what an
  agent is tempted to skip.
- A fresh agent remakes the add-project explainer **without access to the old `harness/` folder or the old
  report**, since copying would only prove it can copy. None of the scripts it writes redoes what the skills
  now cover: hover, 2x capture, the pointer or page embedding. The user compares the two and signs off.

The verify-first, no-UI, native-app and failure paths get no end-to-end run under this acceptance, by the
user's choice. They go into `TEST_BACKLOG.md` when the skill is built.

The `add-project-button` worktree has to stay until the comparison, because it holds the only copy of the
original report.

## Industry Insights

The evidence here is thin, and these are research-agent summaries I haven't re-read at the source. No source
measured what makes a walkthrough get watched, or how parent and child skill conflicts resolve.

- An explicit plan beat flat skill selection in one benchmark of 30 tasks, run by the authors of the system
  tested. That system hands off by file path plus a short status.
  ([arXiv 2603.02176](https://arxiv.org/html/2603.02176v1))
- Similar skill descriptions start triggering interchangeably, so descriptions should work as routing logic.
  ([O'Reilly Radar](https://www.oreilly.com/radar/agent-skills-work-but-the-research-shows-most-teams-are-building-them-wrong/))
- Negative clauses in a description are a fix for an observed false trigger, not a default.
  ([SmartScope](https://smartscope.blog/en/blog/agent-skills-description-guide/))
- One job per skill, and split when the output changes. Practitioner opinion, not measured.
  ([Steve Kinney](https://stevekinney.com/writing/agent-skills))
- Script the repeatable steps and keep judgment in prose, and never let a script prompt interactively.
  ([arXiv 2607.00911](https://arxiv.org/html/2607.00911v1), an unreviewed preprint;
  [freeCodeCamp](https://www.freecodecamp.org/news/learn-the-ai-sdlc-the-complete-guide-to-building-agent-skills/))
- PR demo recipes favor short, behavior-focused clips and one callout per beat, and the scope beat is the one
  teams cut first. ([openscreen PR #1121](https://github.com/getopenscreen/openscreen/pull/1121);
  [Scrimba](https://scrimba.com/articles/how-to-explain-a-pull-request-to-your-team-2026/), vendor content)
- Setting `recordVideo.size` to viewport × scale puts the frame in a corner of a grey canvas while header-only
  tests stay green, which matches the friction on the example.
  ([DemoFlow #47](https://github.com/AndreyBegma/DemoFlow/issues/47))
- Demo environments should be seeded and reset like test fixtures, with fixed dates and one zoom level, and
  footage should wait on UI state, not fixed sleeps.
  ([DemoVexa](https://dev.to/demovexa/treat-your-demo-environment-like-a-test-fixture-45dj), vendor post;
  [Justin Abrahms](https://justin.abrah.ms/blog/2026-02-12-generating-demo-videos-with-playwright.html))

## Deferred Ideas

- A paste-ready PR summary written from the page.
- A contact sheet for the user to approve before embedding, for a run that asks for it.
- An end-card line in the film stating what wasn't proven, if MP4s start travelling alone.
- Whole-release explainers, and native app recording (already deferred in the `making-videos` spec).
- Offering a fixture to the repo when the skill had to build one.
- `[tech-spec]` Where the ledger lives and its format, including how it relates to the `sources.md` that
  `making-videos` already keeps.
- `[tech-spec]` The folder layout for a run with no film.
- `[tech-spec]` The compression floor, and what gives first when video and screenshots won't fit in 10 MB.
- `[tech-spec]` How often to sample frames for the real-data check, and how to include alt text and metadata.
- `[tech-spec]` How clips per behavior go through `verify`, which refuses several MP4s unless each is named.
- `[tech-spec]` Labeling sync when real footage is timed to narration, and whether a crash in the agent's own
  correction script should be easier to recover from before it costs a `verify` attempt.
- `[tech-spec]` Running the acceptance against this branch's skills, because the loaded plugin resolves from
  the installed path and not the worktree (see TEST-2 in `TEST_BACKLOG.md`).

## Glossary

- **Explainer**: the page this skill makes, with or without a film.
- **Film**: the narrated MP4 on the page.
- **Evidence ledger**: one row per behavior, holding its claim, result, how it was checked and where the proof
  is.
- **Staging**: anything arranged for the camera: seeded data, a drawn pointer, added labels and rings, sped-up
  waits, a separately built "before".
- **Polish failure**: a `verify` failure a viewer is unlikely to notice (`sync`, `loudness`).
- **Stop**: a point where the skill waits for the user.
- **Reader**: who the page is written for, which is separate from whoever asked for it.

## Status & amendments

**Amendments:**

- 2026-10-30: The ledger, page source and scripts live in `~/Studio/explainers/<date>-<slug>/`, not the video project folder. `studio.py project new` refuses a folder that already exists, and a run with no film has no video project. The film project stays in `~/Studio/videos/`. This settles the folder-layout item deferred to the tech spec.
- 2026-10-31: The acceptance standard for scripts changes from "the only script is the project-specific fixture" to "no script redoes what the skills now cover". The blind remake wrote seven scripts (393 lines, against the original's 621), all specific to one feature or app, and the user chose this standard over building more shared tooling. The user compared the remake with the original and signed off the same day. The remake's film and page predate the last doc and `leftovers.py` fixes and weren't rebuilt.
