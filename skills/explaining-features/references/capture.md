# Stage, capture and check the frames

Everything on screen is staged, seeded and checked before the page is built. `$E` is the explainer folder, `$REPO` the user's repo and `$FILM` the MP4 under check.

Contents: [Private instance](#private-instance-and-seeded-data) · [Resets](#resets-between-takes) · [Before](#the-parent-commit-for-before) · [Taking footage](#taking-footage-and-screenshots) · [Frame check](#the-frame-check) · [Label timing](#label-timing)

## Private instance and seeded data

Run your own copy of the app that nothing real can reach, and show only data you seeded.

- **A private instance** means a port the user's own dev server isn't on, a fresh data directory or database (never the user's real one), a fresh browser profile, and no real accounts or credentials. Start it from `$REPO` as it is and edit nothing in the repo. Stop it when the run ends.
- **Use the repo's seed data or fixtures if it has them,** after reading them for anything real: names, emails, paths, tokens.
- **If the repo has none, build your own** under `$E/harness/` and load it through the app's own import path or API. Invent the names (a made-up company, made-up people), fix the dates, and keep it small. Never add a fixture to the user's repo. The video caption discloses that the data is seeded ([page.md](page.md#the-staging-caption)).
- **Seeded data only.** If a screen can't be shown without real data, don't show that screen.

## Resets between takes

Reset all persisted state before every take, so "before" and "after" differ only by the feature:

- Seed data back to its initial state.
- Cookies, localStorage, sessionStorage and IndexedDB, or a new browser profile. A dismissed tip, a last-opened project or a remembered sidebar width changes what the next take shows.
- Theme set explicitly (light or dark, never "system"), one viewport size, and one zoom level.
- The clock fixed where the app shows relative dates.

## The parent commit for "before"

Build the parent commit in a folder outside the repo, so nothing is written into it.

```bash
mkdir -p "$E/harness/before"
git -C "$REPO" archive <parent-sha> | tar -x -C "$E/harness/before"
```

`git archive` writes nothing into the repo's `.git`. Install and build there with the project's documented commands, run it on its own private instance with the same seed, and capture the same takes. Make one attempt with the documented build. If the parent commit won't build, don't edit the old code to coax it, because that changes what "before" was. Describe "before" in words from the old code or spec, say no footage was captured of it, and never mock up or rebuild the old screen.

## Taking footage and screenshots

- **Web footage** goes through `making-videos`' `record.py` at `--scale 2`. Its steps include `hover`, `move`, `press` and `drag` beside `goto`, `click`, `fill`, `wait` and `scroll`, and with `--scale` above 1 the result's `webm` is null, so use the `mp4`. It checks the frames are really size times scale, and fails if not.
- **Wait on UI state, not fixed sleeps.** Use a `wait` step on the selector or text that shows the state is ready.
- **Screenshots** come from the verification run or from a script in `$E/harness/`. Copy the ones the page uses into `$E/media/` and compress them before they count against the size budget ([page.md](page.md#the-size-budget)).
- **Keep every script you wrote** in `$E/harness/`, with a `README.md` saying they're a starting point for the next explainer and aren't guaranteed to run.

## The frame check

The frame check is yours, so do it with your own eyes and say so in the hand-over note. Run it on the raw footage after capture, and again on the fitted MP4 after `fit_video.py`, because the fitted file is the one readers see.

1. **Sample one frame every 3 s plus every screenshot:**

   ```bash
   mkdir -p "$E/frames"
   ffmpeg -v error -i "$FILM" -vf fps=1/3 "$E/frames/film-%03d.png"
   ```

   The screenshots are the files in `$E/media/` that the page uses.
2. **Read every frame and every screenshot** with the Read tool and write one line for each saying what it shows. Look for a home directory path (`/Users/<name>`), a username, an email address, a token, a real customer or project name, a terminal prompt, a window or tab title, and a notification.
3. **Search the text the frames can't show:** page source, alt text and captions, for the home directory and the username.

   ```bash
   grep -a -n -o -i -e "$HOME" -e "/Users/[A-Za-z0-9._-]*" -e "$(id -un)" \
     "$E/<slug>.src.html" "$E"/media/*.vtt "$E"/media/*.srt
   ffprobe -v error -show_entries format_tags -of default=nw=1 "$FILM"
   ```

   Run the same search on the built page. Judge each hit: a username that is also a common word needs a look at the line, not a reflex.
4. **A hit or a frame with real data stops the run** (stop 3 in the skill). Name the file and the time.

Sampling every 3 s can miss text that is on screen for under 3 s, and a small font can be read past. That is why the note says the check was the agent's.

## Label timing

Labels are text you add over footage, and each one must land on the word that names it. Use the existing `making-videos` beat flow, with no new tool.

- Record each label as an entry in the film project's `beats.json` (the id, the word, the narration clip and where it starts, the expected time, the label's region in pixels, and the `changed` detector). `making-videos`' audio reference has the format. `verify` measures every beat on the rendered MP4 and prints each label's offset from its word.
- Real footage is recorded in real time and can't be frame-exact, so cut or trim the clip to the beat, then move the label's tween by the offset `verify` printed.
- If you write a script to correct label times, run it on a copy of the scenes folder first and render only after it works, because a bad render that fails `verify` costs one of its 3 attempts. The copy is for the script only. `verify` always runs on the film project's own version, and you never copy a project to reset the counter.
