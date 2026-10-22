# Brand: studio layout, extraction, reuse

Reuse a product's saved brand when it is confirmed. Extract a draft on its first video, show it beside the
storyboard at stop 1, and confirm it only when the user approves that storyboard. Commands are
`python3 "$SKILL_DIR/scripts/studio.py" ...`.

Contents: [Studio layout](#studio-layout) · [brand.json](#brandjson) · [First video: extract and save](#first-video-extract-and-save) ·
[Later videos](#later-videos) · [Tokens in compositions](#tokens-in-compositions)

## Studio layout

Everything lives under `~/Studio`, outside the user's repo. `QUIRK_STUDIO` overrides the root.

```
~/Studio/
  brands/<product>/brand.json  fonts/  logo files
  videos/<YYYY-MM-DD>-<slug>/
    brief.json  storyboard.md  kit/  assets/  scenes/  calls.jsonl  review.html
    v1/  v2/ ...
```

| Command | Result |
|---|---|
| `studio.py init` | creates `~/Studio`, `videos/` and `brands/` |
| `studio.py project new --slug S --product P [--brief-json FILE]` | creates the dated project folder and `brief.json`; prints `{"project", "brief"}` |
| `studio.py version new --project DIR` | creates the next empty `vN/`; a number is never reused |
| `studio.py brand show --product P` | prints `{"brand": {...} \| null, "path"}` |
| `studio.py brand save --product P --file FILE [--confirm]` | validates and stores the brand; prints `{"path", "confirmed"}` |

- `--slug` is lowercase letters, digits and `-`. `--product` is the brand's id: letters, digits, `.`, `_`,
  `-`, starting with a letter or digit (`acme-cli`, not "Acme CLI"). Put the display name in the brief's
  `title`.
- `project new` fills defaults the brief file can override: `length_s` 30 (over 180 is refused, the 3-minute
  cap), `aspects` `["16:9"]`, `narration` true when `length_s` is over 20, `cloud_allow` `[]`
  ([cloud.md](cloud.md)), `music` `{"source": "none", "path": null}`.
- A version folder is never deleted, renamed or replaced. Notes become a new version.

## brand.json

```json
{
  "product": "acme-cli",
  "confirmed": false,
  "colors": {"ground": "#f2efe8", "ink": "#16171a", "accent": "#1e7a52"},
  "fonts": {
    "display": {"family": "Outfit", "files": ["fonts/Outfit.ttf"]},
    "mono": {"family": "IBM Plex Mono", "files": ["fonts/IBMPlexMono-Regular.ttf"]}
  },
  "logo": null,
  "voice": {"engine": "kokoro", "id": "af_heart"},
  "pronunciations": {"quirk": {"from": "kwˈɜːk", "to": "kwˈɜɹk"}}
}
```

| Field | Rule |
|---|---|
| `product` | required; must equal `--product` |
| `colors` | required; token name to `#rrggbb`. Name tokens as the product's CSS does, without the leading `--` |
| `fonts` | required; role to `{family, files}`. `files` are paths inside the brand folder (static TTF or OTF; Blender cannot load WOFF2 or pick a weight from a variable font, see [3d.md](3d.md#fonts)). Roles become `--font-<role>` |
| `voice` | required; `{engine, id}`. Engine is `kokoro`, `elevenlabs` or `openai`. One voice per brand, reused by every video |
| `logo` | path inside the brand folder, or `null` |
| `pronunciations` | optional; word to `{from, to}` phoneme patch for Kokoro ([audio.md](audio.md)) |
| `confirmed` | set by `brand save`, never by the file: false by default, true only with `--confirm` |

`brand save` refuses a file that is not valid JSON, misses `product`, `colors`, `fonts` or `voice`, or names
another product. Saving without `--confirm` always writes `"confirmed": false`, even over a confirmed
brand, so re-save a confirmed brand with `--confirm`.

## First video: extract and save

Do this when `studio.py brand show --product P` prints `"brand": null`, or a brand with `confirmed: false`
(a draft whose storyboard was never approved). If the brand is already confirmed, reuse it and skip steps 6 and 8: there
is no draft file to save, and studio folders are shared across runs, so another run may have confirmed it since you looked.

1. **Colors.** If the product has no site, CSS or design system, skip the search: propose a palette (ground, ink, accent) and a display and mono type pair that suit it, write them into the draft, and mark them as proposed in what you show. Ask at stop 1 whether to keep them. Otherwise find CSS custom properties first: grep `--[a-z-]+:` in `:root` blocks of `site.css`,
   `tokens.css`, `globals.css`, and theme or Tailwind config files. Keep the product's own token names and
   map them to roles: ground (background), ink (text), muted, rule, accent. Use a color from a screenshot
   only when no token exists.
2. **Fonts.** Read `font-family`, `@font-face` and font `<link>` tags. Copy any TTF or OTF files found in
   the repo into `~/Studio/brands/<product>/fonts/` (create the folder by hand; no `studio.py` command does
   it) and list them in `files`, because Blender needs a file. Blender needs a static file of the exact
   weight, not a variable font ([3d.md](3d.md#fonts)). If no file exists, record the family with an empty
   `files` list and say so at stop 1; HyperFrames loads common families by name
   ([hyperframes.md](hyperframes.md)). For a 3D shot, fetch the static file from the font's own upstream
   repo and add it to `files`.
3. **Logo.** Look for `logo*` and SVGs under `assets/`, `public/`, `docs/`. Copy it into the brand folder.
   If there is none, set `logo` to `null` and set the name in type. Do not draw a logo.
4. **Captured site.** Take tokens and fonts from a [URL capture](gather.md) only when the URL is the
   product's own site; a capture of any other page returns that site's design.
5. **Voice.** Default to Kokoro `af_heart`, or the voice the user names. Grades A and B in the Kokoro voice
   list are the safe picks for narration.
6. Write the draft to `$PROJECT/brand.draft.json`, then save it unconfirmed:
   `studio.py brand save --product P --file "$PROJECT/brand.draft.json"`.
7. Show the draft beside the storyboard at stop 1: swatches with names and hex values (labelled "proposed" where you chose them), font families and
   whether files were found, the logo or its absence, and the voice. Apply the user's edits to the
   draft and save it again (still unconfirmed).
8. When the user approves the storyboard, save with confirmation:
   `studio.py brand save --product P --file "$PROJECT/brand.draft.json" --confirm`. If the storyboard is not
   approved, the brand stays unconfirmed and the next video starts from the draft again.

## Later videos

- A confirmed brand is reused as is. Do not re-extract. Show one line at stop 1 naming the brand, voice and
  fonts in use.
- Change a confirmed brand only when the user asks, and save the change with `--confirm` once they agree.
- The brand voice stays the same unless the user asks to save a different one. A cloud voice named for one
  video is not saved to the brand ([cloud.md](cloud.md)).
- A new pronunciation patch for a brand word is a technical fix, not a design choice: add it to
  `pronunciations` and re-save with `--confirm` so the brand stays confirmed.

## Tokens in compositions

Inline the brand as a `:root` block in every composition file, never as a linked stylesheet. Generate it
from `brand.json`: `--<token>` for each color, `--font-<role>` for each font with a generic fallback.

```html
<style>
  :root {
    --ground: #f2efe8;
    --ink: #16171a;
    --accent: #1e7a52;
    --font-display: "Outfit", sans-serif;
    --font-mono: "IBM Plex Mono", monospace;
  }
</style>
```

Why: a `<link rel="stylesheet">` that holds the font families renders the MP4 in system fallback fonts,
while `check`, snapshots and preview all look right. The renderer injects `@font-face` rules only for
families it sees inline. Verify checks that every `var(--font-*)` resolves in an inline `<style>` and that
the render log's `Injected deterministic @font-face rules` line lists every brand family; decode a frame
from the MP4 to confirm. Details and the HyperFrames rules are in [hyperframes.md](hyperframes.md).

- Do not copy a token file into `assets/` and link it; the t1 trial did, and the fonts broke.
- Use `font-family: var(--font-display)`, never the `font:` shorthand with `var(--font-*)`: the compiler's font injection sees only the longhand, and the shorthand rendered fallback fonts in a real run. Verify fails it.
- Read colors in GSAP from the tokens at runtime so a hex value lives in one place.
