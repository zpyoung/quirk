# Writing the page

The page is one file that a reader can forward without you, so it says what was shown, how it was staged and what is still open. `$E` is the explainer folder. The page source is `$E/<slug>.src.html`, built by `quirk:writing-html-artifacts` into `<repo>/.quirk/html/<slug>.html`.

Contents: [Outline](#the-outline) · [Readers](#readers) · [No "I"](#no-i) · [Poster](#the-poster) · [Staging caption](#the-staging-caption) · [Problem sentence](#the-problem-sentence) · [Reasoning](#reasoning-in-how-its-built) · [Code tour](#the-code-tour-on-the-page) · [Dated record](#the-dated-record) · [Media markup](#media-markup) · [Compressing images](#compressing-images) · [Cold read](#the-cold-read)

## The outline

For a teammate or reviewer, in this order:

1. **Title and summary.** The summary says what the feature does in a sentence, how many ledger rows passed, and the biggest gap in one sentence, for example "Tested in the browser engines but not in the desktop window." The film can't carry that gap, so the summary does. Directly under it, the [dated record](#the-dated-record).
2. **The behavior film.** One narrated film at the top, with [the poster](#the-poster) on it and the staging caption under it. With a clip per behavior, each clip sits beside its own section instead. With no film, the page opens on its first screenshot, and the summary says "no film, because" plus the reason.
3. **What it does.** [The problem sentence](#the-problem-sentence), then screenshots and text for each behavior, before and after. Where "before" has no footage, describe it in words and say no footage was captured.
4. **How it's built.** The [code tour](#the-code-tour-on-the-page) first, when there is one, then the written notes: the code path and the design reasons, with their sources ([below](#reasoning-in-how-its-built)). The notes stay with or without a tour.
5. **What was checked.** The results table: the ledger, with Behavior, Claim, Result, How checked and Proof.
6. **What's still open.** Every ledger row that isn't Pass, and everything cut: a skipped install, a native app with no film, a film or a code tour left out for a failed check, a polish failure such as "Three labels land 35 to 87 ms from their spoken words".

## Readers

Another named reader changes both the sections and the wording. For a customer:

- "How it's built" and its code tour, scenario IDs, branch names and commit hashes come out.
- Everything else is rewritten in the reader's terms, and "What's still open" stays, in those terms too.
- The problem sentence drops its source, which stays in `evidence.md`. If no source gives a reason, it comes out.
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

## The poster

The poster is what a reader sees before pressing play, so it shows the main behavior's result with its label on screen. This rule is for the behavior film only; [the tour's poster](#the-code-tour-on-the-page) is a plain frame.

```bash
ffmpeg -v error -ss <seconds> -i "$E/media/film.mp4" -frames:v 1 "$E/frames/poster.png"
```

- Pick a real frame from the rendered film, at a moment after the label has landed, then compress it to `$E/media/poster.jpg` as [compressing images](#compressing-images) says.
- Never composite, draw or mock up a poster. It's a frame of the film, so it shows nothing the film doesn't.
- Read it the way the [frame check](capture.md#the-frame-check) reads a screenshot before it goes in, because it comes from the rendered film, after step 4's check.
- With a clip per behavior, each clip's poster shows that clip's result. With no film there's no poster, and the page's first screenshot shows the main behavior's result instead.

## The staging caption

The caption under the video names all the staging, every time, so a reader never has to guess which parts are staged. It covers seeded data, a drawn pointer, added labels, a separately built "before", and any sped-up waits. Leave out an item only when the film has none of it, and say "no sped-up waits" rather than saying nothing.

Worked example:

> Staged for the camera: the data is seeded (three invented projects, none from a real workspace); the pointer is drawn and follows the real mouse; the labels were added over the footage and timed to the narration; "before" is the parent commit (3f2a9c1) built separately and run with the same seed; the waits at 0:21 to 0:27 are sped up 4x.

If "before" has no footage, the caption says so: "No footage of 'before' was captured; the parent commit didn't build."

## The problem sentence

"What it does" opens with one sentence saying what was wrong or missing before the change, and where that came from. Without it, a page can say where everything moved and leave the reader asking why.

> Once you have a project, Add project is hard to find: it sits inside the Worktrees funnel popover, and a funnel suggests filtering (`logic.md`, Why this exists).

- **Take it from a source,** meaning the spec, the commit message or the issue. Keep the sentence and its source in `evidence.md`.
- **If none gives a reason,** write "No spec, commit or issue says why this changed." Never infer a reason from the diff, however obvious it looks. The hand-over note's Cut line says the page gives no reason.
- **It stays out of the film,** because every script line cites a ledger row and this sentence has none.

## Reasoning in "How it's built"

A design reason stays only if it names the code or spec it came from. A behavior claim needs a ledger result.

- Keeps: "The label hides below 640 px because the toolbar's width is fixed (`ProjectHeader.tsx`, the `compact` prop)."
- Fix or cut: "A pill reads as lighter than a bordered button." Name the spec or code that says so, or delete it.
- Needs a result: "The button never shifts the layout." That is a behavior claim. Add a ledger row with proof, or cut the sentence.

## The code tour on the page

The tour sits at the top of "How it's built", above the written notes. The behavior film's rules stay with the behavior film.

- **The poster rule and the cold read use the behavior film only.** The behavior film stays at the top of the page. The cold read reads its poster and the first frame of `$E/media/film.mp4`, never `$E/media/tour.mp4`. With a tour and no behavior film, the cold read takes the first screenshot, as it does with no film.
- **The tour's poster is a plain frame of the tour,** such as the map scene a second in, taken the same way as the film's poster and compressed to `$E/media/tour-poster.jpg`. It needs no label on screen and shows no result.
- **The tour's caption names what's drawn and generated** ([contents and an example](code-tour.md#the-caption)), and it names each line that is a conclusion and not a tested result.
- **If the tour is left out,** "What's still open" says why, and the written notes stay.

```html
<figure>
  <video controls preload="metadata" data-inline src="media/tour.mp4" poster="media/tour-poster.jpg">
    <track data-inline kind="captions" src="media/tour.srt" srclang="en" label="English">
  </video>
  <figcaption>Generated from the code at commit 3f2a9c1: ...</figcaption>
</figure>
```

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

## Compressing images

An explainer has no size limit, so every film goes in as rendered and nothing is dropped for size. The page source's header comment sets `"size_limit": "none"` beside `layout`. Screenshots and posters are still compressed, because base64 makes everything inlined 4/3 larger.

- **Compress each screenshot,** for example `sips -Z 1600 --setProperty format jpeg --setProperty formatOptions 80 IN.png --out OUT.jpg`, and a JPEG poster the same way.
- **The build still warns over 2 MB,** and a film always crosses it. The hand-over note states the page's size and warns that it may open slowly.

## The cold read

Run this last, on the built page, because you know the feature and can't tell whether the top of the page explains it. It's not a stop: a miss gets fixed or reported, and the run carries on. It finds what's missing from the top of the page. It doesn't prove a person would understand it.

1. **Take the behavior film's first frame** from the file readers get:

   ```bash
   ffmpeg -v error -i "$E/media/film.mp4" -frames:v 1 "$E/frames/first.png"
   ```

2. **Start a fresh subagent with no conversation history,** never a fork of this one. Give it only the prompt below. With a clip per behavior, use the first clip. With no film, pass the page's first screenshot as image 1, if it has one, and drop image 2 and question 4.

   ```
   You have never seen this product or its code. Read only these two images, and open nothing else: no search, no other files, no web.
   Image 1 (a video's poster): <path>
   Image 2 (the same video's first frame): <path>
   The only other thing you know is this text from the top of the page:
   <the summary>
   <the problem sentence>
   Answer each question in one sentence, using only that material. Write "can't tell" instead of guessing, and don't infer a likely answer from general product knowledge.
   1. What does this feature do?
   2. Why was it made? What was wrong before?
   3. What is the biggest thing that wasn't proven?
   4. From image 2 alone, with no other text: what is this video about?
   ```

3. **Save its answers** to `$E/cold-read.md`, under the input they came from.
4. **Compare questions 1 to 3** with what the summary and the problem sentence say. A wrong answer or "can't tell" is a miss. When the page says no source gives a reason, repeating that is a correct answer to question 2. On a customer page with no problem sentence, "can't tell" is the expected answer to it.
5. **Fix a miss, then read once more with another fresh subagent.** Stop at two reads. A fix changes the wording or the poster, never the ledger, and adds no claim without a ledger result or a source. After a rebuild, read a new poster and run the frame check's text search on the built page again.
6. **Don't re-render for question 4.** A re-render spends a `verify` attempt and repeats the fit and the frame check, so a first frame that doesn't say what the film is about only goes in the hand-over note.
7. **Report the result in the hand-over note.** If the subagent can't be started, errors or comes back empty, write "not run, because" and the reason. Never report a read that didn't happen, and don't stand in for the subagent yourself.
