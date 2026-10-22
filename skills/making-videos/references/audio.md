# Audio: narration, loudness, music, captions

Build the voice first and time every visual to its measured word starts. Run all commands as
`python3 "$SKILL_DIR/scripts/<x>.py"`; `$PROJECT` is the project folder.

Contents: [Build order](#build-order) · [Lines and voice](#lines-and-voice) · [Say and align](#say-and-align) ·
[Pronunciation](#pronunciation) · [Placing clips](#placing-clips-in-hyperframes) · [Loudness](#loudness) ·
[Music](#music) · [Captions](#captions) · [Beats and sync](#beats-and-sync)

## Build order

1. Confirm the brief has `narration: true`. Run `python3 "$SKILL_DIR/scripts/doctor.py" check --need narration`.
   If the TTS venv or models are missing, ask the user, then run
   `python3 "$SKILL_DIR/scripts/doctor.py" install --what tts --yes` (about 800 MB, shared cache).
   If they decline, set narration off and make the storyboard say the video is silent.
2. Write the lines, then `voice.py say`, then `voice.py align`.
3. Run `voice.py captions` straight away, before any visual work. A `cps_violations` failure means the
   narration must change, and changing it later moves every word start you timed the visuals to.
4. Write `beats.json` from the word starts, then build each scene so its beat lands on its word.
5. Place the clips, set levels, render, and let `verify.py` measure loudness and sync on the MP4.

Timing the voice to finished visuals has no anchor. Timing visuals to measured word starts held sync
within -27 to +7 ms in the t2 trial.

## Lines and voice

Write one JSON file, `$PROJECT/assets/lines.json`: `[{"id": "a", "text": "Your agent wants to ship.", "start_s": 0.3}]`.
`id` is letters, digits, `.`, `_`, `-`. `start_s` is where the clip begins on the video timeline.

- One sentence, or two short ones, per line. Kokoro is weak on utterances under about 10 to 20 tokens and
  rushes on more than about 400 ([model card](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)),
  so bundle fragments into a sentence and split long passages.
- Budget about 150 words per minute, less where the visuals need breathing room. The t2 trial's 170 wpm
  turned "plan, test, and review" into a blur 1 s long. For a rushed list, make three lines with gaps of
  about 0.3 s in `start_s`. Script word budgets live in [storyboard.md](storyboard.md).
- `voice.py say` has no speed option. Control pace with wording, commas and line splits.
- Spell out numbers and abbreviations, and respell a word in the script text before reaching for a
  phoneme patch.
- The voice comes from the brand's `voice.id` (Kokoro). Pass `--voice` only to override it for one run.
  `af_heart` (grade A) is the default pick; the A and B grades in the model card are the safe set for
  narration, and many male voices are graded D or F+. If the brand voice is a cloud engine, `say`
  refuses (exit 1); make that voice through `cloud.py` ([cloud.md](cloud.md)).

## Say and align

```bash
python3 "$SKILL_DIR/scripts/voice.py" say   --project "$PROJECT" --lines "$PROJECT/assets/lines.json"
python3 "$SKILL_DIR/scripts/voice.py" align --project "$PROJECT"
```

- `say` writes `assets/voice/<id>.wav` (24 kHz mono) and prints `{"clips": [{"id", "wav", "duration_s"}]}`.
  The render resamples to 48 kHz.
- `align` runs faster-whisper (`small.en`, CPU) on every wav in `assets/voice` and writes
  `assets/voice/<id>.words.json`: `[{"text", "start", "end"}]`, seconds from the start of that clip. The
  film time of a word is the clip's `start_s` plus its `start`.
- Exit 3 means the venv is missing; the JSON carries the doctor command.
- Read every `words.json` against the script. Whisper can mishear a clean TTS word (the t2 trial got
  "Claude Code" back as "cloud code"), invent a word over trailing silence, and mistime fricative onsets
  by about 40 ms. Captions use the `text` fields, so fix a wrong `text` in place and keep `start` and
  `end`. Edit only after the last `align`, which overwrites the file.

## Pronunciation

Brand names and jargon that Kokoro mispronounces get a phoneme patch saved in the brand's
`pronunciations` map ([brand.md](brand.md)). `say` applies every patch to the phoneme string with a plain
find-and-replace before synthesis.

```json
"pronunciations": {"quirk": {"from": "kwˈɜːk", "to": "kwˈɜɹk"}}
```

Worked example from the t2 trial: espeak's en-us lexicon gives "quirk" the non-rhotic `kwˈɜːk`, which
Whisper transcribed back as "quark". The patch to `kwˈɜɹk` fixed it. The vocabulary has no `ɝ`, and
phoneme symbols outside the vocabulary are silently dropped, so patch with symbols the model knows.

1. Print what espeak produces for the line:
   `~/.cache/quirk-video/venv/bin/python -c "from kokoro_onnx.tokenizer import Tokenizer; print(Tokenizer().phonemize('Quirk makes it plan.', 'en-us'))"`
   (use `$QUIRK_VIDEO_CACHE` instead of `~/.cache/quirk-video` when it is set).
2. Copy the word's phonemes as `from`, write the corrected `to`, and keep `from` long enough not to match
   inside other words.
3. Re-run `say` and `align`, and check that `words.json` now spells the word right. That is an ASR proxy,
   not a listener, so say in the delivery note that the voice was measured, not heard.

Patches apply to Kokoro only. For a cloud voice, respell the word in the line instead.

## Placing clips in HyperFrames

Give each clip its own `<audio>` element so one line can move without touching the others. The clips
must sit inside the HyperFrames project for `src` to resolve; copy `assets/voice/*.wav` into the scenes
project after each `say` (layout and cwd rules are in [hyperframes.md](hyperframes.md)).

```html
<audio id="vo-a" class="clip" src="assets/voice/a.wav" data-start="0.3" data-track-index="3"
  data-volume="1.88"
  data-fx-chain="{&quot;version&quot;:1,&quot;nodes&quot;:[{&quot;type&quot;:&quot;limiter&quot;,&quot;id&quot;:&quot;lim&quot;,&quot;params&quot;:{&quot;limit&quot;:-1.5}}]}"></audio>
```

- `data-volume` is linear gain (1 = 0 dB, at most 3.98 = +12 dB). Write the fx-chain JSON with `&quot;` for quotes.
- The `limiter` goes last in the chain and guards peaks. Do not also tween `volume` in GSAP on the same
  clip; lint flags it.
- Measure each clip with
  `python3 "$SKILL_DIR/scripts/hf.py" --project "$PROJECT" -- audio "$PROJECT/assets/voice/a.wav" --only loudness --json`
  (one file per call). Gain = 10^((target − measured) / 20), with a first target of -16 LUFS.
- `python3 "$SKILL_DIR/scripts/hf.py" -- normalize-audio . --target vo-a --lufs=-16 --write --json` (run
  from the scenes folder, and write `--lufs=-16` with the equals sign) does this, but it caps gain at the
  peak limit. In the t2 trial
  it left one line at -19.2 LUFS while the others reached about -16. Read the result and set equal-loudness
  gains by hand when a line is short.

## Loudness

Target about -16 LUFS integrated with true peak at or below -1 dBTP on the finished MP4. `verify.py`
passes narrated videos between -17 and -15 LUFS with true peak at or below -1.0 dBTP.

Why these numbers: web and social players normalize playback, and a master near -14 to -16 LUFS avoids
being turned down or clipped. [Spotify](https://support.spotify.com/us/artists/article/loudness-normalization/)
publishes -14 LUFS and a -1 dB true-peak ceiling, and
[EBU R 128](https://tech.ebu.ch/docs/r/r128.pdf) sets the -1 dBTP ceiling. YouTube, TikTok and Meta do not
publish a LUFS target, so treat -14 as a convention and -16 as the conservative end. Broadcast delivery
(-23 LUFS) is out of scope.

- Measure: `ffmpeg -hide_banner -nostats -i "$MP4" -af ebur128=peak=true:framelog=quiet -f null - 2>&1 | grep -E ' I:|Peak:'`.
- Per-clip gains of -16 LUFS do not make the mix -16: the t2 mix measured -14.5 LUFS integrated. Render,
  read the number, then shift every `data-volume` by the difference and render again.
- The renderer can still lower the track to hold -1 dBTP (the t2 log said "Audio lowered by 1.1 dB to stay
  under -1 dBTP"). That is harmless; the limiter alone does not catch every inter-sample peak.

## Music

Music comes only from a file the user supplied (`brief.music.source: "file"`, path in `music.path`) or
from the stock opt-in, a Freesound call through `cloud.py` when the brief names `freesound`
([cloud.md](cloud.md)). With neither, the video has no music. Never synthesize a bed or pull one from
another service.

- Keep the bed at least 20 dB below the narration while anyone speaks. [WCAG 1.4.7](https://www.w3.org/WAI/WCAG22/Understanding/low-or-no-background-audio.html)
  sets that floor for background sound under speech, and mix guides that use 18 to 20 dB agree.
- Check the gap with `audio --only loudness --json` on the music file and a voice clip, then set the
  music `data-volume` so its loudness is at least 20 dB under the voice's.
- Duck with a `volume` lane on the music element (times are seconds from the start of the clip):
  `data-automation='{"version":1,"lanes":[{"target":"volume","points":[{"t":0,"v":1},{"t":2.5,"v":0.35}]}]}'`.
  Add an explicit full-level point at `t: 0`, because a lane holds its first value back to the clip start.
  Drop within about 300 ms when a line begins, rise slowly after it ends, and let the bed rise only in
  pauses of 2 s or more. Take line times from `words.json`.
- Fade the bed out over the last 1 to 2 s with `data-fade-out`.
- Re-measure the render. The level under speech is what counts, not the setting.

## Captions

Burn captions into 9:16 and 1:1 renders and write a `.srt` sidecar for 16:9.

```bash
python3 "$SKILL_DIR/scripts/voice.py" captions --project "$PROJECT" --lines "$PROJECT/assets/lines.json" \
  --out "$PROJECT/v1/<slug>-16x9.srt"
python3 "$SKILL_DIR/scripts/voice.py" captions --project "$PROJECT" --lines "$PROJECT/assets/lines.json" \
  --out "$PROJECT/v1/<slug>-9x16.srt" --burn "$PROJECT/v1/raw/<slug>-9x16.mp4" --burned "$PROJECT/v1/<slug>-9x16.mp4"
```

`captions` is stdlib-only and needs `align` first (it reads each `words.json`). Cues follow
[Netflix's English style guide](https://partnerhelp.netflixstudios.com/hc/en-us/articles/217350977-English-USA-Timed-Text-Style-Guide):

| Rule | Value |
|---|---|
| Lines per cue | at most 2 |
| Characters per line | at most 42 (a longer word is hyphen-broken) |
| Reading speed | at most 20 characters per second |
| Cue length | at least 1.0 s; a cue can stretch into the silence before the next one, never past it |
| Cue breaks | sentence ends, pauses of 0.6 s or more, clip boundaries |

- `--burn` and `--burned` go together. Burning needs an ffmpeg with the `subtitles` filter, which the
  default Homebrew `ffmpeg` lacks. Without it `captions` exits 3 and names `brew install ffmpeg-full`;
  `doctor.py check` reports it as `ffmpeg_subtitles`.
- `--aspect 16:9|9:16|1:1` picks where the burned captions land. Leave it off and `captions` reads the
  video's size with ffprobe; if ffprobe cannot read it and no `--aspect` is given, it exits 2. A flag
  that contradicts the probed size also exits 2.
- Render the 9:16 or 1:1 MP4 into `v1/raw/`, burn into the version folder, and verify the burned file
  with `verify.py --mp4`.

| Aspect | Bottom margin | Side margins | Text |
|---|---|---|---|
| 9:16 | 35% of the height (672 px on 1080x1920) | 11% left, 18% right (120 and 192 px) | white, 48 px at 1080 wide, 4 px black outline |
| 1:1 | 10% of the height | 5% each side | white, 44 px at 1080 wide, 4 px black outline |
| 16:9 | 5% of the height (title-safe) | 5% each side | white, 5% of the height, 3 px black outline |

The 9:16 margins are the conservative envelope across TikTok, Reels and Shorts, which publish no
official pixel numbers and disagree with each other. The 1:1 and 16:9 values are chosen defaults, not
sourced zones. A cue can wrap to extra lines inside the narrower 9:16 box; it grows upward from the
bottom margin.

`captions` passes these as a libass `force_style` scaled to the frame, so they hold at 720x1280 or
1440x2560 as well. Nothing in the tests renders a frame: the machine that wrote this had no ffmpeg with
`subtitles`, so the placement is computed, not seen. After every burn, decode a frame where a cue is
showing (`ffmpeg -ss <cue start + 0.5> -i "$BURNED" -frames:v 1 frame.png`), look at it, and check the
text sits above the bottom zone and inside the side margins. If it does not, draw the captions as
composition text from `words.json` instead and still ship the `.srt`.

When `captions` exits 1 with `cps_violations` (`[{cue, start, end, cps}]`), the narration is faster than
20 characters per second at those cues. The `.srt` is written but nothing is burned until it is fixed.
Shorten the line, or split it into two lines and leave more room before the next `start_s`; then re-run
`say`, `align` and `captions`. Do not edit the `.srt` times by hand to pass.

## Beats and sync

`beats.json` lists the moments the picture must hit a spoken word. `verify.py` reads
`$PROJECT/beats.json` and measures each beat on the rendered MP4. Without the file, or without the venv,
the sync check is skipped.

| Field | Meaning |
|---|---|
| `id`, `word` | label and the spoken word |
| `clip` | the clip's wav path relative to the project, e.g. `assets/voice/b.wav` |
| `clip_start_s` | that clip's `start_s` on the film timeline |
| `expected_s` | film time of the word: `clip_start_s` plus the word's `start` in `words.json` |
| `region` | `[x, y, w, h]` in pixels of the render being verified, around what should change |
| `baseline_s` | film time of a frame before the change, with the region still unchanged |
| `detector` | `changed` (region differs from the baseline) or `color` |
| `color` | `#rrggbb`, required for `color` (a fill growing toward an accent) |

Verify passes when the first changed frame lands within one frame of the word's heard onset: a silence
end within 50 ms of `expected_s`, else a spectral onset within 80 ms, else `expected_s` itself, flagged
as unmeasured. Start each beat's tween on the frame before its word, because a tween shows nothing on
its start frame. Picture slightly ahead of sound reads fine; sound ahead of picture does not.
