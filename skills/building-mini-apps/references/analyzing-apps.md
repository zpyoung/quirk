# Analyzing an app

The procedure for "analyze <app> as a mini app". It studies a public app, writes a study note and a clone blueprint, and ends with a list of new patterns and revisions for the user to pick from. One agent, the coordinator, makes every judgment. Capture subagents only turn one source each into cited observations.

Output goes into this skill's own library:

- `references/apps/<app>.md`: the study note, in the same format as the existing ones (Sources, Observations, Unseen, Patterns fed).
- `references/blueprints/<app>.md`: the clone's build plan.
- Frames and videos under `references/media/<app>/`, which is gitignored. Everything committed is text.

`<app>` is lowercase letters, digits and hyphens (`sentry`, `home-assistant`).

## When this runs

Run this guide when the user asks to analyze an app as a mini app, study an app for patterns, or plan a close clone of one. It does not build the clone. When the user later asks for "a Sentry-like error tracker", the normal build flow in `SKILL.md` reads the blueprint first.

A close clone matches the app's screens, layout, navigation, keys and states. It uses one of the skill's styles, Neutral House by default, carrying character only and never the studied app's exact look, and its UI never names the studied app or uses its brand assets.

The run has six steps and two stops where the user decides:

1. Preflight
2. Core jobs, then **Stop 1**
3. Survey
4. Capture
5. Blueprint, then **Stop 2**
6. Building approved proposals

## Preflight

The run needs this skill folder to be a writable quirk checkout, plus yt-dlp, ffmpeg and playwright-cli.

```
python3 "$SKILL_DIR/scripts/capture.py" preflight
```

It prints one line per check. If any fails, tell the user which one and stop. A skill folder that is an installed plugin copy fails the git check: the library can't be written from there, so the run must happen in a quirk checkout. Do not work around a failed check.

## Core jobs (Stop 1)

Read the app's public site and docs, then propose the core jobs: what users come to the app to do. Aim for the handful that define the app, not every feature. Work in this order: jobs, then flows, then screens, then patterns.

Write the jobs into a new `references/blueprints/<app>.md` as the `## Core jobs` table, every State set to `proposed`:

```
| ID | Job | State |
|---|---|---|
| J1 | Triage a new issue | proposed |
```

IDs are `J1`, `J2` and so on. States move `proposed`, then `confirmed`, then `covered`.

**Stop 1.** Ask the user to confirm or edit the list. Use `orca ask` when the host has it, otherwise ask plainly in chat. Show the jobs, and offer confirm as given or edit. End your turn. Nothing is captured before the user answers.

On confirmation, set every confirmed job's State to `confirmed`. Edits change the table first.

## Survey

List candidate sources in the study note's `## Sources` table, one row per source:

| ID | URL | Kind | Date | Shows |
|----|-----|------|------|-------|

Source IDs are `S1`, `S2` and so on. Kinds are `official` or `third-party`. Look for:

- Official videos. Find them with `python3 "$SKILL_DIR/scripts/capture.py" search <app>`; add `--query TEXT` or `--limit N` to narrow or widen.
- Docs pages and engineering or design blog posts.
- A public demo or sandbox that needs no login.
- Third-party walkthroughs.

Say in each row's Shows cell what the source can show, so gaps are visible before capture. Create the study note with its Sources table now; the other sections come as capture fills them.

## Capture

Dispatch one subagent per source, all in one message so they run in parallel. No two subagents share a decision. They only extract. Each writes staged bullets and returns; it does not touch the study note.

There is no cap on sources or frames. Coverage is the stopping rule: repeat Survey and Capture until every confirmed job's flow, and its empty, error and loading states, each have a cited frame or an Unseen entry.

### Capture subagent brief

Give each subagent this brief with the app, the source ID, the source URL, the confirmed jobs table and the study note's Sources row. It has one source and nothing else.

> You turn one source into observation bullets for the `<app>` study note. Your source is `<source_id>`, `<url>`. Read the confirmed core jobs below; every bullet names the jobs it feeds.
>
> **Video.** Run `python3 "$SKILL_DIR/scripts/capture.py" video <app> <source_id> <url>`. It downloads the video, extracts frames into `references/media/<app>/`, prints each frame's path, and deletes the video. Read the frames it printed.
>
> **Docs page or article.** Read the text. If the page has screenshots worth citing, save them with `playwright-cli` into `references/media/<app>/` as `<source_id>-<slug>.png`.
>
> **Public demo or sandbox.** Drive it with `playwright-cli`. Trigger states on purpose rather than waiting for them: empty (a fresh view or a filter that matches nothing), error (bad input, a missing record), loading (throttle or reload), hover, focus, and keyboard (every key the UI advertises, plus Tab, Esc and the arrows). Screenshot each state as `references/media/<app>/<source_id>-<slug>.png`, where `<slug>` names the state, such as `empty-issue-list`.
>
> **Write bullets** to `references/media/<app>/_staging/<source_id>.md`, one per line, in this format:
>
> ```
> - <source_id>, `references/media/<app>/<frame>.png`: <observation> → feeds: <pattern slugs or proposed slugs>; jobs: <J ids>
> - <source_id>, text of <url or page section>: <observation> → feeds: <...>; jobs: <...>
> ```
>
> The second form is for text-only sources and cites no frame. Cite only frames that are on disk. Record measurable things: layout proportions, row heights, which key does what, what each state shows.
>
> **Say what the source can't show.** End the file with lines starting `Unseen:` for each job flow or state the source does not show, with the reason.
>
> **No logins.** Never create an account, sign in or enter credentials. If a job's step is behind a login wall, stop that flow, write `Unseen: <job id> <step>, behind a login` and carry on with what is public. Report the wall to the coordinator in your reply.

### Merge step

For each staged file, the coordinator runs:

```
python3 "$SKILL_DIR/scripts/check_docs.py" observations <app> references/media/<app>/_staging/<source_id>.md --frames
```

It checks that each bullet's source ID is a row in the Sources table and that every cited frame exists. It prints the failing lines and edits nothing. Then:

- Append only the clean bullet lines to the study note's `## Observations`.
- For a failing line, rerun that source's extraction, or record the observation under `## Unseen` with the reason. A rejected bullet never reaches the study note.
- Copy the `Unseen:` lines into the study note's `## Unseen`.

If a subagent reports a login wall for a job's core interaction, record it as Unseen and ask the user whether to sign up (plain question or `orca ask`). Do not sign up yourself. Carry on with the other sources while the question is open. If the user says yes, they sign up or give you what to use; you never create the account.

When coverage is complete, set each covered job's State to `covered` in the blueprint, and finish the study note with `## Patterns fed`. Check it:

```
python3 "$SKILL_DIR/scripts/check_docs.py" study <app>
```

## Blueprint (Stop 2)

Judgment stays with the coordinator. Write the rest of `references/blueprints/<app>.md` from the study note, with these `##` sections in this order:

- `## Core jobs`: the table from Stop 1.
- `## Screens`: one bullet per distinct screen or state the jobs touch: its name, what it shows, and the jobs it serves.
- `## Coverage`: a table, one row per job and one per screen.

  ```
  | Row | Mark | Pattern | Evidence |
  |---|---|---|---|
  | J1 Triage a new issue | matched | list-peek | S1-t0042.png |
  | Screen: issue detail | approximated | inspector (no activity feed) | S2-t0114.png |
  ```

  Row starts with the job ID, or `Screen:` for a screen. Mark is `matched`, `approximated` (say how in the Pattern cell) or `left out` (say why). Evidence cites a frame filename from the study note's Observations, or a source ID from its Sources table. `unseen` is allowed only on a `left out` row.
- `## Composition`: how the patterns share one shell, store and keyboard layer: the shell layout, shared collections (`useCollection` names), the key map across patterns, and the app's real domain model with its entity and field names. Names only, no UI copy or brand strings from the app.
- `## Proposed patterns`: every interaction no existing pattern covers. Each proposal gives the slug, the interaction, a When to use, the components it needs, and any new dependency with the reason. Write `None` if there are no gaps.
- `## Proposed revisions`: additive changes to existing patterns that the studied app does better: the pattern, the change, the evidence. Write `None` if there are none.

Every distinct gap becomes its own proposed pattern. Name it for the interaction, not the app: `stack-trace`, not `sentry-issue`. Its When to use must fit an app other than the one studied, so give an example from a different app. A component smaller than a pattern, such as a sparkline, is built inside the block of the pattern that needs it. If two proposals need the same component, each lists it.

Revisions are additive only: new optional props and behaviors, with existing keys and the Block API unchanged. A change that would break the API is proposed as a new pattern instead.

Both documents must be clean before the stop:

```
python3 "$SKILL_DIR/scripts/check_docs.py" study <app>
python3 "$SKILL_DIR/scripts/check_docs.py" blueprint <app>
```

Fix every problem it prints. A confirmed or covered job needs at least one Coverage row, and every Evidence cell must cite something that exists.

**Stop 2.** Ask the user which proposed patterns and revisions to build, and approve the listed dependencies. Use `orca ask` when the host has it, otherwise ask plainly in chat. List each proposal with one line on what it is, and each dependency with why. Approval here covers the dependencies. End your turn. Do not build anything until the user answers.

## Building approved proposals

Build only what the user approved. The other proposals stay listed and unbuilt in the blueprint.

For each approved pattern, follow the same reference-then-block flow the first ten patterns used:

1. Write `references/patterns/<slug>.md` first, in the format of the existing pattern references, and check it with `python3 "$SKILL_DIR/scripts/check_docs.py" pattern <slug>`.
2. Build the block in `gallery/src/patterns/<slug>/` from that reference. Components live inside the block. Never import from another pattern, and copy a component that two patterns need into each block.
3. Add the pattern to the registry with `python3 "$SKILL_DIR/scripts/build_registry.py"`. An approved dependency goes into this pattern's registry item only.
4. Add a row to the pattern index in `SKILL.md`, studied from the new app.
5. Add the slug to the pattern lists in `tests/test_building_mini_apps_skill.py`, and add it to the gallery.

For each approved revision, update the pattern's reference and its block. Keep the Block API backward compatible: new props are optional, existing keys keep their meaning, and the pattern's existing demo still works unchanged.

After the build, update the blueprint: the revisions that landed leave the Proposed sections or are marked built, and the unbuilt ones stay. Run the skill's own tests before reporting.

## Resuming a run

A run can pause at a stop or end with the session. State lives on disk, so resume from the files and never from chat history.

1. Read `references/blueprints/<app>.md` and `references/apps/<app>.md`. If neither exists, start at Preflight.
2. Read the Core jobs State column:
   - `proposed`: the run is at Stop 1. Ask again.
   - `confirmed`: capture is under way. Read the Sources table, see which sources have observations and which don't, and continue the capture loop on the rest.
   - `covered` on every job: write or finish the blueprint and go to Stop 2.
3. If a blueprint has Proposed sections and the user names patterns to build, go to Building approved proposals with just those.
4. Staged files under `references/media/<app>/_staging/` that were never merged are run through the merge step again. Do not trust a staged bullet's frame until `check_docs.py observations ... --frames` passes.

## Rules

- A clone matches screens, layout, navigation, keys and states, and uses one of the skill's styles, Neutral House by default, carrying character only and never the studied app's exact look.
- No brand assets, and the clone's UI never names the studied app.
- A component needed by two patterns is copied into each block. No cross-pattern imports.
- Dependencies are proposed in the blueprint, approved at Stop 2, and land in that pattern's registry item only.
- Public no-login demos only. Ask before any signup, and never create an account yourself.
- No capture cap. Coverage is the stop.
- Frames and videos are never committed. `references/media/` is gitignored.
- A gap pattern is named for the interaction, and its When to use fits another app.
