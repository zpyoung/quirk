# Writing the page

The page is one file that a reader can forward without you, so it says what was shown, how it was staged and what is still open. `$E` is the explainer folder. The page source is `$E/<slug>.src.html`, built by `quirk:writing-html-artifacts` into `<repo>/.quirk/html/<slug>.html`.

Contents: [Outline](#the-outline) · [Readers](#readers) · [No "I"](#no-i) · [Staging caption](#the-staging-caption) · [Reasoning](#reasoning-in-how-its-built) · [Dated record](#the-dated-record) · [Media markup](#media-markup) · [Size budget](#the-size-budget)

## The outline

For a teammate or reviewer, in this order:

1. **Title and summary.** The summary says what the feature does in a sentence, how many ledger rows passed, and the biggest gap in one sentence, for example "Tested in the browser engines but not in the desktop window." The film can't carry that gap, so the summary does. Directly under it, the [dated record](#the-dated-record).
2. **The film.** One narrated film at the top, with the staging caption under it. With a clip per behavior, each clip sits beside its own section instead. With no film, the page opens on its first screenshot, and the summary says "no film, because" plus the reason.
3. **What it does.** Screenshots and text for each behavior, before and after. Where "before" has no footage, describe it in words and say no footage was captured.
4. **How it's built.** The code path and the design reasons, with their sources ([below](#reasoning-in-how-its-built)).
5. **What was checked.** The results table: the ledger, with Behavior, Claim, Result, How checked and Proof.
6. **What's still open.** Every ledger row that isn't Pass, and everything cut: a skipped install, a native app with no film, a screenshot dropped for size, a film left out for a failed check, a polish failure such as "Three labels land 35 to 87 ms from their spoken words".

## Readers

Another named reader changes both the sections and the wording. For a customer:

- "How it's built", scenario IDs, branch names and commit hashes come out.
- Everything else is rewritten in the reader's terms, and "What's still open" stays, in those terms too.
- The dated record keeps the date and drops the branch and commit: "This shows the app as of 2026-10-30."

| For a teammate | For a customer |
|---|---|
| Native desktop window not driven. Only the Chromium build ran. | Not yet tried in the desktop app. |
| SC-2 hover: Pass, real mouse events | Hovering over the button shows its full label. |

Keep the ledger's own rows in `evidence.md` unchanged for any reader.

## No "I"

The page doesn't say "I", "we" or "my". It states what was measured and how, because it gets forwarded without its sender and "I" would read as the user speaking.

- Instead of "I didn't want a second instance interfering", write "Ran on a private instance, so no other session interfered."
- Instead of "I checked the hover", write "Hover checked with real mouse events in Chromium 131." Name only the engine that actually ran, never one that would stand in for another.

## The staging caption

The caption under the video names all the staging, every time, so a reader never has to guess which parts are staged. It covers seeded data, a drawn pointer, added labels, a separately built "before", and any sped-up waits. Leave out an item only when the film has none of it, and say "no sped-up waits" rather than saying nothing.

Worked example:

> Staged for the camera: the data is seeded (three invented projects, none from a real workspace); the pointer is drawn and follows the real mouse; the labels were added over the footage and timed to the narration; "before" is the parent commit (3f2a9c1) built separately and run with the same seed; the waits at 0:21 to 0:27 are sped up 4x.

If "before" has no footage, the caption says so: "No footage of 'before' was captured; the parent commit didn't build."

## Reasoning in "How it's built"

A design reason stays only if it names the code or spec it came from. A behavior claim needs a ledger result.

- Keeps: "The label hides below 640 px because the toolbar's width is fixed (`ProjectHeader.tsx`, the `compact` prop)."
- Fix or cut: "A pill reads as lighter than a bordered button." Name the spec or code that says so, or delete it.
- Needs a result: "The button never shifts the layout." That is a behavior claim. Add a ledger row with proof, or cut the sentence.

## The dated record

Near the top, directly under the summary, one line: the date, the branch, the commit, and what that means.

> Made 2026-10-30 on branch `zpyoung/add-project-button` at commit `3f2a9c1`. This shows the app at this commit.

Nothing checks whether the app has moved on, and the page doesn't claim it hasn't.

## Media markup

Put `data-inline` on each `<img>`, `<video>`, `<source>` or `<track>`, with `src` and `poster` as paths relative to the source. The build turns each into a data URI, converts `.srt` captions to WebVTT, and turns captions on. Never hand-write base64. Allowed types are `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.mp4`, `.vtt` and `.srt`.

```html
<figure>
  <video controls preload="metadata" data-inline src="media/film.mp4" poster="media/poster.jpg">
    <track data-inline kind="captions" src="media/film.srt" srclang="en" label="English">
  </video>
  <figcaption>Staged for the camera: ...</figcaption>
</figure>
<img data-inline src="media/hover-after.jpg" alt="The Add project button expanded to its full label">
```

- Alt text describes what the screenshot shows, in plain words, with no paths or usernames.
- A `figure` directly inside a `q-grid` needs a `data-span`. If the build warns about one, add the `data-span` it names, so it doesn't collapse to a quarter-width column.
- A missing file, a type that isn't allowed, or a path outside `$E` and the project fails the build with exit 2 and names the path.

## The size budget

The page is one file under 10 MiB (10,485,760 bytes), and base64 makes everything inlined 4/3 larger. The build fails over the limit and warns over 2 MB, and a film always crosses 2 MB, so keep the warning in the hand-over note. Never raise either limit.

1. **Compress the images first.** For each screenshot, for example `sips -Z 1600 --setProperty format jpeg --setProperty formatOptions 80 IN.png --out OUT.jpg`, and a JPEG poster the same way.
2. **Measure everything but the film.** Build the page with the poster and captions but no video, and read its size in bytes as `B`.
3. **Work out the film's budget.** The film's bytes are the space left, less 256 KiB of headroom, divided by 4/3:

   `budget = floor((10,485,760 - B - 262,144) * 3 / 4)`

   With a clip per behavior, share that budget between the clips in proportion to their seconds.
4. **Fit the film.**

   ```bash
   python3 "$SKILL_DIR/scripts/fit_video.py" --in "$E/media/film-raw.mp4" --budget-bytes <budget> --out "$E/media/film.mp4"
   ```

   It copies a film that already fits. Otherwise it re-encodes H.264 yuv420p with AAC at 96 kbps, and never lets video go under 300 kbps. Exit 1 means the film can't fit above that floor: compress the images harder, then drop a screenshot, then shorten the film. If a screenshot was dropped, "What's still open" says which one.
5. **Rebuild, then read frames from the fitted file when `fit_video.py` reported `reencoded: true`.** A re-encoded file is the one readers see and differs from the raw one, so run the frame check on it ([capture.md](capture.md#the-frame-check)). A copied film is the raw film, already checked.

Worked example: with `B` at 1,363,149 bytes (1.3 MB), the budget is 6,645,350 bytes. For a 90 s film that is about 570 kbps in total after the script's 4% margin and about 470 kbps for video, above the 300 kbps floor.
