# Motion, software-video technique, seek-safe GSAP, typography

Read this before writing any scene. The kit's motion roles (see [storyboard.md](storyboard.md)) come from
the principles here; the GSAP rules decide whether a scene renders correctly at all.

Contents:
- Motion principles
- Showing software
- Seek-safe GSAP rules
- Typography and layout

## Motion principles

Pick a few motion roles, use them everywhere, and sequence by importance. Durations and easings below
come from interactive-UI research (NN/g, Material, Carbon). A viewer of a video cannot skip ahead, so
the video-specific ranges marked "inference" are this skill's adjustment, not a sourced rule.

### Durations

| Move | Duration | Basis |
|---|---|---|
| Small UI feedback | 0.1-0.2 s | [NN/g](https://www.nngroup.com/articles/animation-duration/): most animations 100-500 ms, usually 100-400 ms |
| Element entrance that carries meaning | 0.3-0.5 s | inference, toward the top of the UI range |
| Element exit | 65-75% of the entrance (about 0.2-0.3 s) | NN/g: enter slightly longer than exit (300 ms in, 200-250 ms out); [Material 1](https://m1.material.io/motion/duration-easing.html) 225 in, 195 out |
| Text reveal | 0.3-0.8 s | practitioner guidance ([Demotion](https://trydemotion.com/blog/text-animation-secrets)) |
| Hero move or scene transition | 0.4-0.7 s | inference from Carbon slow tokens (400, 700 ms) and Material "long" (450-600 ms) |

Past about 500 ms a UI animation "starts to feel like a real drag" (NN/g), so long moves need a reason.
More frequent motion should be shorter and subtler.

### Easing

Entrances decelerate, exits accelerate, moves already on screen ease in and out. Use linear only for
constant-rate things such as a progress bar (NN/g, [Figma](https://help.figma.com/hc/en-us/articles/41238219562007-Motion-design-fundamentals-Easing), Material 1).

| Role | GSAP ease | Reference curve |
|---|---|---|
| Enter | `power3.out` or `expo.out` | Material decelerate `cubic-bezier(0, 0, 0.2, 1)`; easeOutExpo `(0.16, 1, 0.3, 1)` |
| Exit | `power2.in` | Material accelerate `cubic-bezier(0.4, 0, 1, 1)` |
| On-screen move | `power2.inOut` | Material standard `cubic-bezier(0.4, 0, 0.2, 1)` |

Use overshoot and springs rarely: Carbon reserves expressive motion for occasional, important moments.
Scale overshoot is a taste parameter (sources give 2-3% and 5-10%); keep it identical across the project.
Choose one personality per project and apply it everywhere: for example premium (0.35-0.6 s, no overshoot),
corporate (0.2-0.4 s, up to 3% overshoot), or energetic (0.1-0.25 s, strong ease-out). These ranges are from
the LottieFiles motion-design skill; match the brand, not the mood of the day.

### Stagger and hierarchy

- Primary elements enter first and fastest; supporting elements follow in a deliberate order. Start the next
  item before the previous one finishes.
- Video-scale stagger offsets from practitioners agree on about 30-100 ms: characters 20-40 ms, words
  40-70 ms, lines 60-100 ms, list items 50-100 ms. Material's 20 ms is a UI-list figure and too tight here.
- A staggered tween is one tween with a tail. If a later tween on the same element starts before the tail
  ends, `check` warns `gsap_tween_tail`; shorten the stagger or move the later tween.
- One focal point per transition. Material's rule: guide focus with the most important shared element.
- Keep most elements still while one moves. A common cap is about one third of the animated elements
  active at once.
- Do not wait for each item to finish before the next starts; overlap them.

### Continuity between scenes

Carry one element across a scene boundary as the focal point, and animate its transform instead of
cutting to a fresh layout. A scene timeline cannot reach elements outside its own file, so a persistent
object (card, cursor, highlight ring, logo) either lives in the root composition, or ends scene A and
starts scene B at the same position and size. If nothing is shared, the new content enters from a direction
that makes a new focal point.

### Scene transitions

Pick one transition role per project, so no scene invents its own, and never leave bare ground between scenes.

- Hard cut: the outgoing scene ends on its last frame and the incoming one starts on the next, with no exit tween. Use it when the beat changes sharply or the scenes share nothing.
- Overlap: the incoming scene's host starts 0.25 s before the outgoing host ends, so the outgoing exit (0.25 s, `power2.in`) and the incoming enter (0.3 to 0.4 s, `expo.out`) run together. Start the first incoming tween at the overlap start, not after the exit. Give an overlapping scene root no opaque background, because an opaque incoming layer hides the outgoing one at once and `check` reports `text_occluded`; the ground comes from `index.html`.
- An exit that ends before the next enter begins leaves the ground bare for the gap, even a 0.05 s one, which shows as a flash. Either overlap the two, or drop the exit and cut.

### Avoiding a slideshow

No source defines this; the list is a synthesis of the sources above.
- Do not fade everything in together with one identical effect; sequence by importance.
- Do not use linear easing or one default transition for every cut.
- Use one consistent motion language, not a different effect per element.
- Do not put the narration verbatim on screen.
- Do not use breathing, floating or pulsing loops as filler for motion on titles and UI.
- Land a title, then hold it dead still until it leaves.

### Kinetic typography

Use it for short, punchy lines (hooks, key claims), not for paragraphs. Match the tempo to the voice:
time word reveals to the measured word starts. Reveal in 0.3-0.8 s; stagger characters 20-40 ms or words
40-70 ms. A tested pattern in the trials: each word fades from muted to ink with a small blur-in, 0.13-0.15 s per word,
about 0.05-0.08 s apart, then the line holds still. Check legibility and clipping on the final frame.
Flashing text stays under three flashes per second ([WCAG 2.3.1](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html)).

## Showing software

Prefer a rebuilt, code-driven UI for hierarchy, vertical re-layout and sharp text; use a raw recording or
capture as proof ("this is the real product"). All numbers here are practitioner conventions.

- Record at native resolution and never upscale low-resolution footage. Capture a window of about 1280x800
  so the browser fills a 1080p frame.
- Virtual camera: animate `x`, `y` and `scale` on a wrapper `<div>` around the footage (never on the
  `<video>` itself). Zoom 1.3-2x: near 1.3x when context matters, toward 2x for small text; above 2x text
  softens. Zoom on each meaningful action rather than constantly.
- Pans glide, they do not snap: use the on-screen move ease (`power2.inOut`) with the hero-move duration. In the
  footage trial one continuous camera move over a captured page, with highlights drawn in the page's own
  coordinates, read as a real demo.
- Highlight overlays: draw a ring or box in page coordinates on the same wrapper so it moves with the page.
  Zoom beats a cursor halo for short async demos; use highlights when a constant zoom would disorient.
- Cursor: make it large enough to see (a default cursor is about 32 px, tiny on a retina capture), smooth its
  path, and hide it when idle.
- First meaningful action within about 2 s of a demo starting; a tight demo is about 40-45 s.
- Sensitive data: use a demo account with seeded data. If something must be hidden, cover it with a solid shape from the kit
  rather than a blur; blur or grade on footage goes through `python3 "$SKILL_DIR/scripts/hf.py" -- media-treatment`, never CSS filters.
- Terminal and editor text in the footage should be at least 18-20 px in a 1280x800 capture; otherwise zoom
  to it or replace it with a rebuilt callout.

## Seek-safe GSAP rules

HyperFrames renders by seeking a paused timeline one frame at a time (`time = floor(frame) / fps`), so
motion must be a pure function of time. Generic GSAP advice for web pages breaks this, so follow these
seven rules. Each scene and the root build one paused timeline and register it on `window.__timelines`.

1. Never call `play()`. The renderer owns the playhead; a running clock fights the seek.
2. Never nest scene timelines with `add()`. The runtime drives each scene, and nesting seeks it twice.
3. Use `fromTo`, never `from`. `from` records its start state once and drifts when the host re-seeks backwards.
4. Never use `repeat: -1`. An infinite loop is not a function of a finite timeline; use a finite count such as
   `repeat: Math.max(0, Math.floor(duration / cycle) - 1)`.
5. No ScrollTrigger. A render has no scrolling, so it sits at progress 0 or fights the seek.
6. When several `fromTo` tweens animate the same property of one element, set `immediateRender: false` on
   the later ones. Without it each later tween writes its start state at build time and overwrites the earlier tween.
7. Set initial state with `gsap.set(el, {...})` at build time, not `tl.set(el, {...}, 0)`. The starting
   state belongs to the page rather than to a position on the timeline, so it holds whichever frame is seeked first.
   Instant flips later in the timeline (`tl.set(el, {...}, t)` with t > 0) are fine.

```js
gsap.set("#s1-card", { opacity: 0, y: 24 });                           // rule 7
const tl = gsap.timeline({ paused: true });                            // rules 1, 2
tl.fromTo("#s1-card", { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }, 0.6);
tl.fromTo("#s1-card", { y: 0 }, { y: -12, duration: 0.3, ease: "power2.inOut", immediateRender: false }, 2.0);
window.__timelines["scene-one"] = tl;                                  // key equals data-composition-id
```

Related rules from the HyperFrames contract that scenes hit constantly:
- Place tweens at absolute seconds (`tl.to(el, {...}, 2.4)`), so each scene's timeline is self-contained.
- Register the timeline last, after any async work such as `document.fonts.ready`.
- No `Date.now()`, `requestAnimationFrame`, timers or unseeded `Math.random()`; seed a PRNG such as mulberry32.
- Animate transforms and opacity, not `left`, `top`, `width` or `height`. A `<span>` needs `display: inline-block` to transform.
- Never tween `display`, `visibility` or `autoAlpha` on a `.clip` element; animate a child.
- Tweening a colour needs a literal value, not `var(--x)`; read tokens with `getComputedStyle`.

Authoring structure, lint and check recipes are in [hyperframes.md](hyperframes.md).

## Typography and layout

Design for a phone-width viewer: if text under about 40 px at 1080p appears, zoom to it or enlarge it.

| Item | Rule | Basis |
|---|---|---|
| Body text, 1920x1080 | 40-60 px minimum | accessible-film standards via [legibility.info](https://legibility.info/rules-for-text-in-videos) |
| Titles | at least 50% larger than body | same |
| Subtitle line height | 7-8% of height for 16:9, 3.9-4.5% for 9:16 (about 75-86 px at 1080p) | [BBC](https://www.bbc.co.uk/accessibility/forproducts/guides/subtitles) |
| Burned-in vertical captions, 1080x1920 | start near 65 px, floor 55 px | vendor, low confidence |
| Phone check | a 44 px label at 1080p renders about 8 px tall on a 360 px-wide phone | trial t3 |
| Title-safe | keep text inside the central 90%: 96 px left and right, 54 px top and bottom at 1920x1080 | [EBU R95](https://tech.ebu.ch/docs/r/r095.pdf), [SMPTE ST 2046-1](https://www.nab.org/xert/scitech/pdfs/tv031510.pdf) |
| Corner furniture (logo, bug) | inside the central 93% | SMPTE action-safe |
| Contrast | at least 4.5:1; large text (18 pt, or 14 pt bold) at least 3:1 | [WCAG 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) |

- The 90% title-safe limit is also what verify checks, so keep every text box inside it in the final frame.
- Hold animated text to its final-state colours when you check contrast. Do not place text on busy
  backgrounds or gradients; avoid red-green and complementary pairs for text and background.
- Use at most three type sizes per aspect and take them from the kit. Prefer weight and colour for emphasis,
  and one accent colour for one meaning (in the trials, green only ever meant "checked").
- Declare brand fonts through the `:root` tokens inlined in each composition. A font declared only in a
  linked stylesheet renders as a system font in the MP4 while check, snapshots and preview look right.
- Vertical and square: stay inside the safe box from [storyboard.md](storyboard.md); captions use 90% of the frame width at most
  (two lines for 1:1, three for 9:16, per the BBC guide).
