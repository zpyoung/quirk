# Code walkthrough template (optional)

Use this template when a video walks through source code, such as a merge request or a module tour, and you'd rather describe the scenes than write them. It's optional. Hand-built scenes from the scene kit are still the default, and the template has no layout a hand-built scene can't match. It saves writing: a ~3 KB spec instead of a ~35 KB generator, and its cues are timed to the measured words for you.

`code_walkthrough.py` builds a 16:9 project from `<project>/kit/walkthrough.json` and the confirmed brand. It doesn't do 9:16 or 1:1 cuts, silent videos, music, or captures. It's fixed at 1920x1080 and 30 fps: its cues land one 30 fps frame early, so a render at another rate puts them off by more than a frame.

Contents: [Commands](#commands) · [Spec](#spec) · [Scene layouts](#scene-layouts) · [Cues and sync](#cues-and-sync) · [What it handles for you](#what-it-handles-for-you)

## Commands

Run them in this order, in the narration build step. `P` is the project folder.

```bash
python3 "$SKILL_DIR/scripts/voice.py" say --project "$P" --lines "$P/assets/lines.json"
python3 "$SKILL_DIR/scripts/code_walkthrough.py" timeline --project "$P"   # writes start_s and kit/timeline.json
python3 "$SKILL_DIR/scripts/voice.py" align --project "$P"
python3 "$SKILL_DIR/scripts/hf.py" --project "$P" -- init "$P/scenes" --non-interactive   # once; delete scenes/CLAUDE.md and AGENTS.md
python3 "$SKILL_DIR/scripts/code_walkthrough.py" build --project "$P"      # compositions, index.html, beats.json
```

- `timeline` places each line after the previous one, with `lead_s` (0.3) at each scene start, `gap_s` (0.4) between lines, `scene_gap_s` (0.6) after a scene and `end_hold_s` (3.0) after the last. Every line in `lines.json` must be placed in exactly one scene.
- Run `voice.py captions` after `timeline`, because captions read `start_s`.
- `build` copies the voice clips, brand font files and logo into `scenes/assets/`. Re-run it after any spec edit. Then lint, snapshot, render and verify as usual ([review.md](review.md)).
- Exit 1 names the missing input, or the spec value that doesn't resolve. A cue whose word wasn't heard lists the words Whisper did hear.

## Spec

```json
{
  "sources": {"pa": "assets/src/plan_availability.py"},
  "colors": {"ground": "bg-subtle", "focus": "primary"},
  "sync_shift": {"c:new": 0.037},
  "scenes": [
    {"id": "s1", "type": "cards", "lines": ["a", "b"], "eyebrow": "MR !123", "heading": "The module",
     "cards": [{"eye": "1 · this MR", "title": "Module", "ring": "a:base"},
               {"eye": "2 · !124", "title": "Writes", "enter": "a:stack"}],
     "sub": {"text": "One line under the cards", "at": "b:months"}},
    {"id": "s2", "type": "code", "lines": ["c"], "eyebrow": "services/plan_availability.py", "heading": "Validating",
     "source": "pa", "excerpt": [48, "...", [54, 70]],
     "bands": [{"at": "c:three", "lines": [54, 55]}, {"at": "c:sorted", "lines": [69, 70]}],
     "chips": [{"at": "c:three", "text": "exactly 3 keys"}]}
  ]
}
```

- `sources` maps a short key to a file in the project. Copy the files at the reviewed commit into `assets/src/` first, so the line numbers on screen match the commit.
- `colors` maps a template role to a brand token name, and is needed only when no brand token matches the role by name. The roles are `ground`, `ink`, `muted`, `rule`, `focus` (band edge, keywords), `ring` (card highlight), `good` and `bad`.
- Every scene has `id` (lowercase), `type`, `lines`, and optional `eyebrow`, `heading` and `chips` (`[{at, text}]`, swapped in place at the top right).

## Scene layouts

| Type | Fields | Use it for |
|---|---|---|
| `cards` | `cards` (1-3: `eye`, `title`, `enter`, `ring`), `arrows`, `top`, `sub`, `end_card` (`text`, `at`, `delay`; shows the brand logo), `card_title_px` | an MR stack, before and after, the closing card |
| `files` | `files` (1-6: `path`, `add`, `remove`, `tag`, `highlight`) | the changed-files list |
| `panels` | `panels` (1-2: `eye`, `title`, `rows`, `mono`, `enter`, `steps: [{at, row}]`), `height`, `sub`, `footer` | a data contract, an example value, a tests summary; a row is a string or a `[label, value]` pair |
| `code` | `source`, `excerpt`, `visible` (rows, default up to 17), `top`, `bands: [{at, lines: [a, b]}]`, `extra_html`, `extra_js` | the walkthrough itself |
| `custom` | `file` (a composition you write by hand) | anything else, such as an animated diagram |

- `excerpt` items are a line number, an inclusive `[a, b]` range, `"..."` for a gap row, or `{"line": n, "as": "str"}` to colour a docstring line as a string.
- A band covers source lines `a` to `b`. Both must be in the excerpt.
- `extra_html`, `extra_js` (a list of statements) and `custom` files can use `{{cue:line:word}}` for a scene-local time. A `custom` file can also use `{{kit_css}}` for the brand tokens and kit classes. A custom file still follows every authoring rule in [hyperframes.md](hyperframes.md).

## Cues and sync

A cue is `line:word`, or `line:word#n` for the nth word starting with `word` (counting from 0). It resolves to the word's start in `assets/voice/<line>.words.json`, minus one frame, so the picture changes on the word. Write the word as Whisper heard it: if "Writes" came back as "Rights", the cue is `n:rights`.

`build` writes `beats.json` for the changes it can measure cleanly: a card or panel entering, a card ring, a file row lighting up, and a code panel's first band. It skips a beat that lands within about the first second of its scene, while entrances are still moving. When verify reports a beat off by more than a frame, add its cue to `sync_shift`, with the reported offset in seconds and the opposite sign (picture -62 ms early becomes `+0.062`), then build and render again.

## What it handles for you

- Code rows soft-wrap at 80 columns. The continuation row has no line number, and a scrolled panel never opens on a wrapped tail.
- Rows outside the panel's visible window are hidden, so `check` sees only the text a viewer sees and the title-safe bands stay clean.
- Chips leave before the next one enters, so two never overlap.
- Brand tokens and `@font-face` rules are inlined in every composition, with the weight read from each font file's name (`Medium` is 500).
- Every animation follows the seek-safe GSAP rules in [motion.md](motion.md).
