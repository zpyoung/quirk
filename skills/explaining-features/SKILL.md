---
name: explaining-features
description: Use when the user asks for a walkthrough, to explain this feature, a feature explainer, or to show what this PR does. Makes one offline HTML page about one feature at one commit, with a results table of what was really run, screenshots, and a short narrated film when the behavior moves, and verifies the feature in the real app first when nobody has. Runs only when asked. For a video alone, such as an announcement or motion graphics, use making-videos; for a dashboard or any page not about one feature, use writing-html-artifacts; for trying a flow in an app, use using-apps-like-a-user.
---

# Explaining features

Make one offline page about one feature, at one commit, for one reader, showing only what was really run. The page's results table is the evidence ledger. The film, when there is one, is a tour of that table. This skill runs the steps in order and hands the work to three required sub-skills; it doesn't render video, drive apps or build pages itself.

`SKILL_DIR` is the directory holding this `SKILL.md`, which the host shows when the skill loads. Run its scripts as `python3 "$SKILL_DIR/scripts/<script>.py" ...`. Never build paths from a plugin-root environment variable. This skill's own scripts print one JSON object to stdout and diagnostics to stderr, and never prompt. `$E` is the explainer folder, `~/Studio/explainers/<date>-<slug>/`.

## Before anything else

- **macOS only.** On Linux or Windows say "This skill is macOS only, because making-videos and using-apps-like-a-user both are." and stop.
- **Only when asked.** Never offer an explainer when a branch finishes, a PR opens or a feature merges.
- **One feature per explainer.** Out of scope, and you say so if asked: publishing or attaching to a PR (unless the user asks in that run), refreshing an old explainer in place, roundups of a release or an epic, recording a native macOS app, and adding a fixture to the user's repo.
- **Frozen, not refreshable.** To update an explainer, run the skill again. Nothing checks whether the app has moved on since.
- **Never** write outside `~/Studio` and the repo's self-ignoring `.quirk/` (the page goes in `.quirk/html`, and `quirk:using-apps-like-a-user` keeps its run state in `.quirk/using-apps-like-a-user`) during a run, and never send anything to a cloud service the brief didn't name. Don't work around this with a working directory outside the repo or a test override. Ask the user before departing from any rule here.
- **Stop only what you started.** Record the PID of everything you start and stop only those PIDs. Never stop anything by name or pattern (`pkill`, `killall`), because the user's own instance of the same app may be running. After stopping, run `scripts/leftovers.py` to check that nothing is left under `$E`, including children that outlive their parent, and never stop what it lists as `check_by_hand`: see [capture.md](references/capture.md#stopping-what-you-started).

## Required sub-skills

Invoke each by name when its step starts, and follow it. They name their own scripts; this skill never builds their paths.

| Sub-skill | Invoked | How |
|---|---|---|
| `quirk:using-apps-like-a-user` | step 2, when the main behavior was never run for real | Always `--unattended`, because this skill is the caller. A `blocked` verdict on the main behavior is stop 2 below. |
| `quirk:making-videos` | step 5, when the plan says film | `stops: none` in the brief unless the user asked for review. Record web footage at `--scale 2`. Narration on, length under 90 s, `cloud_allow` empty. |
| `quirk:writing-html-artifacts` | step 6 | Report template, layout `explainer`. Media goes in with `data-inline`. |

## Folder layout

```
~/Studio/explainers/<date>-<slug>/
  evidence.md            the ledger
  <slug>.src.html        page source; media paths are relative to it
  media/                 screenshots, poster, and the fitted MP4 and captions the page inlines
  harness/               project-specific scripts, plus a README saying they aren't guaranteed to run
~/Studio/videos/<date>-<slug>/   the film project, owned by making-videos; absent when there's no film
<repo>/.quirk/html/<slug>.html   the built page
```

A clip-per-behavior run makes one `making-videos` project per clip, named `<date>-<slug>-<behavior>`, because its `verify` takes one MP4 per project.

## The run

Only three things stop a run after the plan: the main behavior doesn't work, the feature can't be run at all, or real data shows on screen. Everything else is handled and reported at the end.

### 1. Plan, and don't wait

State the plan in one line. It doesn't wait for a reply, so carry on. The line holds the feature, the reader, the commit, and film or no film with the reason. Any feature you can run qualifies: this session's work, a branch or PR, or something shipped. Example: "Explaining the Add project button for a technical teammate at commit 3f2a9c1, with a film because the button grows on hover." The user can override any part in a later message.

- **Reader.** A teammate or reviewer who knows the code, unless the request names another reader. Another reader changes both the sections and the wording; see [page.md](references/page.md).
- **Film or not.** A film when the behavior moves. A visible but static change, such as a new label or layout: the plan line says "no film, because nothing moves", and the page has screenshots and text. A feature with no UI (a CLI flag, a backend change) gets a page with real command output and test results and no film, and any diagram on it is labeled as a diagram. A native macOS app is driven with `quirk:using-apps-like-a-user`, the page uses its screenshots, and the plan says no film because making-videos can't record native apps; the page lists that as a cut.
- **Too much for 90 seconds.** Make a short clip per behavior, each beside its section, sharing the 10 MiB budget. A single feature that fits still gets one film.
- **Installs.** If a film is planned and Playwright or the voice tools are missing, ask about the install now, in the plan step, before the user walks away: making-videos never installs unasked. If the user declines, the page has no film and lists that as a cut.
- **Review.** If the request says "let me see the storyboard first" or otherwise asks to review, leave `stops` at its default `both` and tell the user the film stops at the storyboard and after the first render. Without that request there are no stops.
- **Folder.** Create `$E` with `media/` and `harness/`.

### 2. Evidence

Build the ledger in `$E/evidence.md`, one row per behavior, as [evidence.md](references/evidence.md) describes. Read the spec, existing app runs and tests into it first.

- **Start the instance when verification needs one.** Start it by the rules in [capture.md](references/capture.md#private-instance-and-seeded-data), even though step 3 is where staging is described. To find how to start it, look for the repo's own fixture or test helpers first (an e2e setup, a seed script, a dev command), and build your own only when it has none.
- **Minimum: the main behavior was run for real.** If it wasn't, verify it with `quirk:using-apps-like-a-user` (web, Electron or native), or run the real command or test for a feature with no UI. Every ledger row then comes from that run, and a behavior it couldn't check is listed as not proven.
- **Nothing verified yet is normal.** A shipped feature that nobody checked in the app gets verified first, then explained.
- **Stop 1, the main behavior doesn't work as the spec says.** Stop before building anything and tell the user what you saw, with the screenshot. Say: "The main behavior doesn't work as the spec says: <what you saw>. Screenshot: <path>. I stopped before building anything, so there's no film and no page." Don't render a film or write a page around it, however far along the run is.
- **Stop 2, the feature can't be run at all** (a login wall, hardware, or a service you can't reach), shown by a `blocked` verdict on the main behavior. Stop and say what blocked it: "I couldn't run <feature>: <what blocked it>. I didn't write a page from reading the code." Don't produce a page from reading the code.

### 3. Stage

Start a private instance with seeded data, and build the parent commit for "before". The rules are in [capture.md](references/capture.md).

- **The film's project gets created before capture.** When the plan says film, run `studio.py project new` as `quirk:making-videos` describes, before any footage is recorded, because `record.py --project` needs it. Step 5 then uses that project and doesn't create another.

- **No seeded data in the repo.** Build your own seeded data in `$E/harness/` and disclose it in the video caption. Never add a fixture to the user's repo.
- **The parent commit won't build.** Describe "before" in words from the old code or spec, and say no footage was captured of it. Never mock up or rebuild the old screen.

### 4. Capture

Take screenshots and footage from the staged instance, then read the screenshots and sampled frames looking for real data ([capture.md](references/capture.md)). Keep every script you wrote in `$E/harness/`, with a `README.md` saying they're a starting point for the next explainer and aren't guaranteed to run.

- **Stop 3, real data shows on screen.** A frame that shows a real home directory path, a username, or other real data stops the run, even when the user said to just finish. Don't crop, blur or re-record to get past it. Say: "Frame <file> (<time>) shows <what, with the path masked>. I stopped; nothing was built from that footage."
- **The frame check is yours, and the note says so.** Small or fleeting text can get past it. Every finished run's hand-over note says the frame check was the agent's.

### 5. Film

Skip this step when the plan says no film. Otherwise invoke `quirk:making-videos` with the brief below, then sort the `verify` result.

- Brief: `{"stops": "none", "narration": true, "length_s": <under 90>, "cloud_allow": []}`, plus the product and slug. Add the review setting from step 1 when it applies.
- **The script comes from the ledger.** Every script line in the film's `sources.md` cites a ledger row and doesn't restate the proof. The film shows only behavior with a ledger result of Pass or Partly, and narrates only the part that passed. A row marked Not proven, Unit test only or Failed never appears in the film: check the behavior first, or leave it out. A behavior that's true but unchecked gets checked or left out.
- **The film doesn't state what wasn't proven.** The page does. By the user's choice, don't add an end card or caption line about gaps to the MP4.
- **Label timing and sync.** Follow [capture.md](references/capture.md#label-timing).
- **Sort the `verify` result with the script:**

  ```bash
  python3 "$SKILL_DIR/scripts/verify_outcome.py" --verify "$P/v1/verify.json" [--mp4 NAME]
  ```

  `$P` is the film project. Pass `--mp4` when the version holds several MP4s.

| `outcome` | Failing checks | What you do |
|---|---|---|
| `ship` | none | The film goes in. |
| `ship_disclosed` | `sync`, `loudness` (polish) | The film ships, and "What's still open" states the failure with its numbers, for example "Three labels land 35 to 87 ms from their spoken words". |
| `omit` | `fonts`, `render_log`, `contrast`, `title_safe`, `captions`, `blender`, an unknown check, or none named (a viewer would notice) | Leave the film out, and the page says why, in its own row. A film whose text is hard to read doesn't ship because it looks fine otherwise. |
| `halt` | `outside_calls` (a cloud call nobody named) | The run stops. Tell the user which call, because it has already happened. |
| `retry` | any, while the stop flag is false | Fix the cause and verify again under making-videos' 3-attempt rule. Never copy a project to reset the counter. |

After `ship` or `ship_disclosed`, fit the film to the page budget with `fit_video.py` (the arithmetic for `N` is in [page.md](references/page.md#the-size-budget)), then read frames again from the fitted file when `fit_video.py` reports `reencoded: true`, because that's the file readers see. When it reports `reencoded: false` the file is the raw film, and the raw frame check already covers it.

```bash
python3 "$SKILL_DIR/scripts/fit_video.py" --in "$E/media/film-raw.mp4" --budget-bytes N --out "$E/media/film.mp4"
```

Exit 1 means the film can't fit above the 300 kbps video floor: compress images harder, then drop a screenshot and say so on the page, then shorten the film.

### 6. Page

Invoke `quirk:writing-html-artifacts` and build the page from `$E/<slug>.src.html`, using the outline and rules in [page.md](references/page.md). The page is one file with the film at the top and the video compressed to fit. The page is the review, and the honesty rules below are part of the build, not a polish pass.

- **The summary under the title names the biggest gap**, for example "Tested in the browser engines but not in the desktop window." The film doesn't carry it, so an MP4 shared alone looks fully proven. That is why the summary must.
- **The video's caption names all the staging:** seeded data, a drawn pointer, added labels, a separately built "before", and any sped-up waits.
- **"How it's built"** keeps a design reason only if it names the code or spec it came from. A behavior claim needs a ledger result.
- **A dated record** sits near the top: the date, branch and commit, and "this shows the app at this commit".
- **"What's still open"** is every ledger row that isn't Pass, plus anything cut (a skipped install, a native app with no film, a dropped screenshot, an omitted film).
- **The page doesn't say "I".** It states what was measured and how.

### 7. Hand over

Give the path, the `verify` result, what was cut, and a warning that the page disappears with the worktree. Don't open it, publish it or attach it to a PR unless the user asks. Template:

```
Done: <repo>/.quirk/html/<slug>.html (<size>), written for <reader>.
Film: <58 s, verify passed | no film, because <reason> | left out, because <check> failed>.
Cut: <what was left out and why, or "nothing">.
The frame check was mine: one frame every 3 s plus every screenshot. Small or fleeting text can get past it.
The page lives in this worktree's .quirk/html and disappears with the worktree. The source, media and film
are in ~/Studio/explainers/<date>-<slug>/, so it can be rebuilt.
```

## After hand-over: notes

Tell the user that notes make a v2. A note that changes the film (say, one line of narration is wrong) makes a new version under the making-videos rule that versions are never overwritten, fits the new film, re-reads its frames when the fit re-encoded it, and rebuilds the page from its source. A text-only note rebuilds the page from its source without rendering.

## When you're tempted to skip a rule

| Thought | Do this instead |
|---|---|
| "The film looks great without the gap." | Leave the behavior out of the film, and put it in the summary and "What's still open". |
| "The summary reads better without the biggest gap." | Name it anyway, in one sentence. Say "The page says <gap>; the film doesn't." |
| "The user said to just finish." | The three stops still stop. Report the frame or the broken behavior, and offer to continue once it's resolved. |
| "The text is fine to my eye after 3 failed `verify` attempts." | Run `verify_outcome.py` and do what `outcome` says. |
| "The old screen is easy to mock up." | Write "before" in words from the old code or spec, and say no footage was captured. |
| "Nobody will read the caption." | The caption names all the staging. A reader shouldn't have to guess which parts are staged. |
| "It's obviously true, so the ledger row can say Pass." | Pass needs a real run you can point to. Check it, or mark it Not proven. |
| "I'll offer an explainer now that the branch is done." | Don't. It runs only when asked. |

Pressure scenarios for the rules a script can't enforce: [test-pressure-1.md](test-pressure-1.md), [test-pressure-2.md](test-pressure-2.md), [test-pressure-3.md](test-pressure-3.md), [test-pressure-4.md](test-pressure-4.md).

## References

Read a reference when its step starts, not before.

- [evidence.md](references/evidence.md): the ledger columns and results, how each row is filled, verifying first, and features with no UI.
- [capture.md](references/capture.md): the private instance and seeded data, stopping what you started, resets between takes, the parent-commit build, the frame check, the real-data search, and label timing.
- [page.md](references/page.md): the section outline, reader variants, the staging caption, reasoning and the dated record, and the size budget.
