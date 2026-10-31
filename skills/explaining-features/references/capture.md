# Stage, capture and check the frames

Everything on screen is staged, seeded and checked before the page is built. `$E` is the explainer folder, `$REPO` the user's repo and `$FILM` the MP4 under check.

Contents: [Private instance](#private-instance-and-seeded-data) · [Stopping](#stopping-what-you-started) · [Resets](#resets-between-takes) · [Before](#the-parent-commit-for-before) · [Taking footage](#taking-footage-and-screenshots) · [Frame check](#the-frame-check) · [Label timing](#label-timing)

## Private instance and seeded data

Run your own copy of the app that nothing real can reach, and show only data you seeded.

- **A private instance** means a port the user's own dev server isn't on, a fresh data directory or database (never the user's real one), a fresh browser profile, and no real accounts or credentials. Start it from `$REPO` as it is and edit nothing in the repo. Stop it when the run ends, by the rules in [Stopping what you started](#stopping-what-you-started).
- **Run everything you start with `HOME` set to a folder under `$E/harness/`,** as well as the app's own data-dir variable if it has one, so the cleanup check can find survivors by their `HOME`. If the app can't run that way, the check can't find its survivors: rely on the recorded PIDs and say so in the delivery note.
- **Seed it under `$E/harness/`,** never in a system temp folder or the user's own project folders, because a write outside `~/Studio` and the repo's `.quirk/` breaks the write boundary. A fixture's repo path can appear on screen (a project path in a header or a recent-files list), and a path under `$E` carries the home directory, so the frame check looks for it.
- **Use the repo's seed data or fixtures if it has them,** after reading them for anything real: names, emails, paths, tokens.
- **If the repo has none, build your own** under `$E/harness/` and load it through the app's own import path or API. Invent the names (a made-up company, made-up people), fix the dates, and keep it small. Never add a fixture to the user's repo. The video caption discloses that the data is seeded ([page.md](page.md#the-staging-caption)).
- **Seeded data only.** If a screen can't be shown without real data, don't show that screen.

## Stopping what you started

Stop only the processes you started, by PID, because the user's own instance of the same app may be running.

- **Record the PID of everything you start,** at launch, in `$E/harness/pids`. Before stopping a process, also record its children (`pgrep -P <pid>` lists them by parent, not by name), because children can outlive their parent.
- **Stop only those PIDs.** Never stop anything by name or pattern: no `pkill`, no `killall`, no `kill $(pgrep -f ...)`. A pattern that matches your instance's path or binary also matches the user's.
- **After stopping, check what is left under `$E`:**

  ```bash
  python3 "$SKILL_DIR/scripts/leftovers.py" --explainer "$E"
  ```

  It prints `yours` (processes whose `HOME` is under `$E`) and `check_by_hand` (processes that only have their working directory there). It never stops anything.
  - Stop each PID in `yours` by its PID, then run it again until `yours` is empty. Stop an entry only if its command is one you started, and name anything else in the delivery note instead. The script reads each environment out of text, so a listing is not proof that the process is yours.
  - Never stop anything in `check_by_hand`, because it may be the user's own shell or editor. If an entry looks like your own, name it in the delivery note.
  - Exit 3 means the check didn't run (`ps` or `lsof` is missing or failed). Say so in the delivery note instead of reporting that nothing is left.

## Resets between takes

Reset all persisted state before every take, so "before" and "after" differ only by the feature:

- Seed data back to its initial state.
- Cookies, localStorage, sessionStorage and IndexedDB, or a new browser profile. A dismissed tip, a last-opened project or a remembered sidebar width changes what the next take shows.
- State the app persists itself, such as a panel width kept in its daemon, survives a new browser. Between takes that change it, restart the private instance on a fresh home and re-measure after.
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

The frame check is yours, so do it with your own eyes and say so in the hand-over note. Run it on the raw footage after capture. Run it again on the fitted MP4 only when `fit_video.py` reports `reencoded: true`, because then the fitted file differs from the raw one and is the one readers see.

1. **Sample one frame every 3 s plus every screenshot:**

   ```bash
   mkdir -p "$E/frames"
   ffmpeg -v error -i "$FILM" -vf fps=1/3 "$E/frames/film-%03d.png"
   ```

   The screenshots are the files in `$E/media/` that the page uses.
2. **Read every frame and every screenshot** with the Read tool and write one line for each saying what it shows. Look for a home directory path (`/Users/<name>`), a username, an email address, a token, a real customer or project name, a terminal prompt, a window or tab title, a notification, and the fixture's repo path.
3. **Search the text the frames can't show:** page source, alt text and captions, for the home directory and the username.

   ```bash
   grep -a -n -o -i -e "$HOME" -e "/Users/[A-Za-z0-9._-]*" -e "$(id -un)" \
     "$E/<slug>.src.html" "$E"/media/*.vtt "$E"/media/*.srt
   ffprobe -v error -show_entries format_tags -of default=nw=1 "$FILM"
   ```

   Run the same search on the built page. Judge each hit: a username that is also a common word needs a look at the line, not a reflex. The dated record near the top of the page carries the branch name ([page.md](page.md#the-dated-record)), and a branch name can contain the username, so a match on that one line is expected. Any other match is stop 3 in the skill. For an outside reader the record drops the branch ([page.md](page.md#readers)), so every match there is a stop.
4. **A hit (other than the dated-record line) or a frame with real data stops the run** (stop 3 in the skill). Name the file and the time.

Sampling every 3 s can miss text that is on screen for under 3 s, and a small font can be read past. That is why the note says the check was the agent's.

## Label timing

Labels are text you add over footage, and each one must land on the word that names it. Use the existing `making-videos` beat flow, with no new tool.

- Record each label as an entry in the film project's `beats.json` (the id, the word, the narration clip and where it starts, the expected time, the label's region in pixels, and the `changed` detector). `making-videos`' audio reference has the format. `verify` measures every beat on the rendered MP4 and prints each label's offset from its word.
- Real footage is recorded in real time and can't be frame-exact, so cut or trim the clip to the beat, then move the label's tween by the offset `verify` printed.
- If you write a script to correct label times, run it on a copy of the scenes folder first and render only after it works, because a bad render that fails `verify` costs one of its 3 attempts. The copy is for the script only. `verify` always runs on the film project's own version, and you never copy a project to reset the counter.
