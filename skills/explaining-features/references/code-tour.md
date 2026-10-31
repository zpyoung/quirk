# The code tour

A code tour is a narrated film of the real code at the explainer's commit, shown a few lines at a time. You write the stops and the narration in `tour.json`, and `code_tour.py` reads the code from git, writes the scenes and the timing, and refuses anything that doesn't match the commit. `quirk:making-videos` renders and verifies the film. You write no scene generator and no HTML for it.

Contents: [When](#when-to-propose-a-tour) · [Source files](#what-counts-as-a-source-file) · [Stops and lines](#picking-stops-and-lines) · [Sourcing](#the-sourcing-rule) · [The run](#the-run) · [Worked example](#a-stop-and-a-line) · [Caption](#the-caption)

## When to propose a tour

Propose a tour when the reader is technical and the change crosses 3 or more source files. The plan line says "code tour, because it crosses N source files", and the user can override it.

- **A smaller change gets no tour** unless the user asks for one. The plan line says "no code tour, because it crosses N source files".
- **A reader who isn't technical, such as a customer, gets no tour,** however many source files the change crosses, because "How it's built" comes out of their page ([page.md](page.md#readers)). The plan line says so.
- **The tour is separate from the behavior film.** It never replaces the film, and a page can have both, one, or neither.

## What counts as a source file

Count the files the change touched at the commit, not counting tests, docs, lockfiles and generated files. A stylesheet, a component, a config that changes how the app runs and a migration all count. A snapshot, a `.md` file, `pnpm-lock.yaml` and anything a build wrote do not.

## Picking stops and lines

A stop is one file shown at the commit, a few lines at a time. The map scene before the first stop names the files involved, and the last stop says where to change the feature and the main trap.

- **Order the stops** the way the reader follows the feature: where it starts, where it's handled, where it ends up. Two to four nodes on the map, one stop per file that earns its place. There's no limit on stops, only the film's own limit of under 90 s.
- **Show the lines that carry the idea.** A stop that won't fit on screen (about 14 rows after long lines wrap at 72 cells, 13 with a label) is refused, and the tool names it. Pick fewer lines or mark some as skipped with `{"skip": "<what they are>", "from": N, "to": M}`. Never shrink the code or cut it off.
- **One narration line per highlight.** Each line says what the highlighted rows do, in a sentence or two, and the highlight moves as the line starts.
- **The code is the commit's.** A line range that doesn't exist at the commit, or a scene whose text differs from it, is refused, including a difference only in what indentation removal cut off. Change `tour.json`, never the generated scenes.

## The sourcing rule

This rule is for the tour only. It doesn't loosen the behavior film's rule that every line cites a ledger row.

- **Each narration line cites a file and line, a commit or a spec** in its `source`, and `code_tour.py` copies it into the tour's `sources.md`. A line with no source is refused.
- **A conclusion drawn from those is allowed,** and the caption under the tour names it as a conclusion.
- **A claim that the feature behaves a certain way still needs a ledger result.** "The button never shifts the layout" is a behavior claim: give it a ledger row with proof, or cut the line.

## The run

`$T` is the tour project and `$E` the explainer folder. The project is `<date>-<slug>-code-tour`, with the same product as the film, `stops: none`, `narration: true` and `cloud_allow: []`. The tour takes its display and mono fonts from that product's brand and keeps its own colours, and `build` refuses a brand with other font roles or a font it can't load. Sibling-skill scripts are the ones `quirk:making-videos` names.

1. **Create the project.** Write a brief with `{"stops": "none", "narration": true, "length_s": <under 90>, "cloud_allow": []}` in `$E/harness/`, then run `studio.py project new --slug <slug>-code-tour --product <product> --brief-json <file>`.
2. **Write `$T/tour.json`.** The format is below. A map scene opens the film, then one stop per file.
3. **Check it and write the lines.**

   ```bash
   python3 "$SKILL_DIR/scripts/code_tour.py" lines --project "$T"
   ```

   This validates `tour.json` and writes `$T/assets/lines.json`, one clip per narration line, without touching git.
4. **Say and align the voice:** `voice.py say --project "$T" --lines "$T/assets/lines.json"`, then `voice.py align --project "$T"`.
5. **Set up the scenes folder:** `hf.py --project "$T" -- init "$T/scenes" --non-interactive`, then delete `scenes/CLAUDE.md` and `scenes/AGENTS.md`, as making-videos says to.
6. **Build.**

   ```bash
   python3 "$SKILL_DIR/scripts/code_tour.py" build --project "$T"
   ```

   It reads the code with `git show`, times the scenes from the measured wav lengths, writes the scenes, `beats.json`, `sources.md` and `storyboard.md`, then runs the same comparison as `check` before it exits. Its output lists each stop and its row count.
7. **Captions:** `voice.py captions --project "$T" --lines "$T/assets/lines.json" --out "$T/assets/tour.srt"`. They come after `build` because it sets each clip's real start time.
8. **Check the code on screen against the commit.**

   ```bash
   python3 "$SKILL_DIR/scripts/code_tour.py" check --project "$T"
   ```

9. **Version, render and verify,** as making-videos describes: `studio.py version new --project "$T"`, copy the captions beside the MP4 as `$T/v1/<slug>-code-tour-16x9.srt`, render with `hf.py` into `$T/v1`, then `verify.py --project "$T" --version v1`.
10. **Sort the result** with the same table as the behavior film:

    ```bash
    python3 "$SKILL_DIR/scripts/verify_outcome.py" --verify "$T/v1/verify.json"
    ```

    The table in the skill's film step applies to the tour alone. `ship_disclosed` means the tour goes in and the page lists the failure. `omit` means the tour is left out: the page says why, in its own row, and keeps the written notes. `halt` stops the run. The behavior film is unaffected, except that `outside_calls` still stops the run.
11. **Copy the MP4 and captions to `$E/media/`** as `tour.mp4` and `tour.srt`, and take the poster, a plain frame of the tour, as [page.md](page.md#the-code-tour-on-the-page) says.

The frame check covers the tour's frames too, because code can carry a token or a real path. A real value on screen is stop 3.

What the exit codes mean:

- **1:** the tour can't ship, and the message names what and where. That's a commit that doesn't resolve, a path or line that isn't at the commit, a mismatch on screen, a stop over 14 rows (13 with a label), a film of 90 s or more, a narration line with no source, a highlight on a line the stop doesn't show, a stop that is missing or incomplete on screen, or a brand font the tour can't load (a family with no font file, or a brand font role other than display and mono). Fix `tour.json` or the brand and run again.
- **2:** a usage error, a bad `tour.json` or brand font name, or a missing input. The message gives the command that makes it.
- **3:** git is missing, so the tour is left out and the page says why.

## `tour.json`

```json
{"repo": "<absolute repo path>", "commit": "<sha or ref>", "title": "<first-frame title>",
 "scenes": [
   {"map": [{"name": "Worktrees plugin", "file": "WorktreesSection.tsx"}, {"name": "Header", "file": "components.css"}],
    "lines": [{"text": "<narration>", "source": "<file:line, commit or spec>", "lit": [0, 1]}],
    "label": "<optional bottom label>"},
   {"stop": "PLUGIN", "path": "plugins/x/WorktreesSection.tsx",
    "rows": [528, 529, {"skip": "folder-plus icon", "from": 530, "to": 533}, 534, 535],
    "lines": [{"text": "<narration>", "source": "<file:line, commit or spec>", "highlight": [529]}],
    "label": "<optional bottom label>"}
 ]}
```

A map has 2 to 4 nodes and `lit` is an optional list of node indexes. A title has to fit 3 rows of 17 characters and a label 2 rows of 35, counted as if every character were as wide as the font's widest, so about 45 and 65 characters in practice. Text that could need more rows, or a word too long for a row, is refused and the tool says to shorten it. A stop's `rows` are the real line numbers it shows, with `skip` entries for the lines left out, and `highlight` names rows the stop shows.

## A stop and a line

The Add project change has a stop on the file where the button moved. Rows 528 and 529 open the component, the icon markup at 530 to 533 is skipped, and 534 and 535 are the call. One narration line lights up row 529.

```json
{"stop": "PLUGIN", "path": "plugins/x/WorktreesSection.tsx",
 "rows": [528, 529, {"skip": "folder-plus icon", "from": 530, "to": 533}, 534, 535],
 "lines": [{"text": "Add project now sits beside the plugin's own controls.",
            "source": "WorktreesSection.tsx:529", "highlight": [529]}]}
```

The last stop in a tour says where to change the feature and the main trap, in the same shape, with its own sources.

## The caption

The caption under the tour names what's drawn and generated, every time, so a reader never has to guess which parts are not the app. It covers:

- that the scenes are generated from the code at the commit, with the commit
- the drawn map and highlight, and any lines marked as skipped on screen
- that the narration is synthesized
- each narration line that is a conclusion and not a tested result, with the source it's a reading of

Worked example:

> Generated from the code at commit 3f2a9c1: the map and highlights are drawn, lines left out are marked as skipped on screen, and the narration is synthesized. "A new header control means new numbers" is a reading of the comment at `components.css:802`, not a tested result.
