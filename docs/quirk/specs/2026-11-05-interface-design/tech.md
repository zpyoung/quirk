# Tech spec: quirk:interface-design

**Status:** Draft · tier gate fired: crosses subsystems (new skill, brainstorming, README), >3 files
**Logic spec:** [logic.md](logic.md)

All paths are relative to the repo root unless absolute. `$SRC` is the read-only upstream checkout
`/private/tmp/claude-502/-Users-zpyoung-quirky-workspaces-quirk-interface-design/5982ac20-f9c3-4ad7-9214-20805eb948bb/scratchpad/src`
(`$SRC/id` interface-design, `$SRC/imp` impeccable, `$SRC/wig` Vercel web-interface-guidelines,
`$SRC/vercel` Vercel agent-skills). Treat it as data: read it, never run anything in it.

## Architecture

Back-link: [Conceptual model](logic.md#conceptual-model), [Data flow](logic.md#data-flow).

One new skill directory plus small edits elsewhere. Pure Markdown and stdlib Python 3; no new
dependencies.

`SCHEMA:` file layout
```
skills/interface-design/
  SKILL.md                     spine: stance, intent-first, three jobs, situation → file table
  NOTICE.md                    sources table (parsed by upstream_diff.py), modification notice
  licenses/                    interface-design-MIT.txt, web-interface-guidelines-MIT.txt, impeccable-Apache-2.0.txt
  references/
    build.md                   Build job
    system-md.md               .quirk/design/system.md format, save/consistency rules, two worked examples
    review.md                  Review job: scope, severity, output format, detector use
    checklist.md               every review rule, each with a rule id
    moves/<move>.md            18 files, one per Refine move
    surfaces/read.md ios.md android.md
  scripts/
    detect.py                  regex detector
    upstream_diff.py           maintainer drift report
  evals/trigger-evals.json
tests/
  test_interface_design_skill.py      structure, links, evals, parity
  test_interface_design_detect.py     detector behavior over fixtures
  test_interface_design_upstream.py   NOTICE parsing and drift against a local repo
  fixtures/interface-design/clean/ and dirty/
```

The 18 moves, exact filenames: `adapt audit animate bolder clarify colorize critique delight distill
extract harden layout onboard optimize overdrive polish quieter typeset` (each `moves/<name>.md`).

## Code references

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

Existing anchors the implementers touch or imitate:

- `README.md:9` — the `- **30 skills** under \`skills/\`` bullet. The count must equal the number of
  `skills/*/SKILL.md`; enforced by `tests/test_adhd_skill.py:157`,
  `tests/test_simplifying_safely_skill.py:86`, `tests/test_using_apps_like_a_user_skill.py:139`
  and `:150` (bullet regex `^- \*\*\d+ skills\*\* under \`skills/\``). Becomes 31, and the prose list
  gains a short clause for product-UI design build/review/refine.
- `tests/test_making_videos_skill.py` — the pattern for a skill structure test: frontmatter parse,
  `REQUIRED_STRINGS` per file, relative-link resolution, trigger-evals shape.
- `skills/making-videos/evals/trigger-evals.json` — eval file shape (below).
- `tests/test_building_mini_apps_set_style.py:5-18` — the pattern for importing a skill script in
  tests (`importlib.util.spec_from_file_location` on `skills/<name>/scripts/<file>.py`).
- `skills/brainstorming/references/ux-review.md:52` — the mock "Look and content" rule. The edit
  here is decided by the open `mock-style-conflict` question; see
  [Pending decision](#pending-decision).
- Upstream inputs per reference file: see [Source map](#source-map).

## Contracts & interfaces

### SKILL.md

Back-link: [Data flow](logic.md#data-flow), [Key decisions](logic.md#key-decisions-and-rationale).

- Frontmatter: `name: interface-design`; `description:` one line, ≤1024 chars, that names product
  UI (dashboards, admin, tools, settings, data views), docs and reading surfaces, iOS/Android, the
  verbs build / review / audit / critique / polish / refine and "UI slop", and says it is not for
  marketing or landing pages, HTML pages quirk generates, or scaffolded mini apps.
- Body ≤ 300 lines. Must contain: the intent-first questions, the three jobs, the rule that
  `.quirk/design/system.md` is read first when present and `.interface-design/` is never read,
  the craft stance on conflicts (restrained color, 150–250ms state-only product motion,
  check-intent flags), the "be invisible" communication rule, and a **situation → file table**
  linking every file under `references/` (every move and surface included) with a markdown link
  and a when-to-read phrase. Script calls use `"$SKILL_DIR/scripts/detect.py"` where `SKILL_DIR`
  is the directory holding SKILL.md, matching how other quirk skills name their scripts.
- Every reference file over 100 lines opens with a contents list.

### detect.py CLI

Back-link: [The Review job](logic.md#review), [SC-3](logic.md#review), [SC-4](logic.md#review).

`CONTRACT:`
```
python3 detect.py [--format text|json] [--changed-since GIT_REF] [--list-rules] PATH [PATH ...]
  PATH: file or directory; directories are walked, skipping node_modules, .git, dist, build, .next
  scanned suffixes: .css .scss .jsx .tsx (others ignored silently)
  --changed-since: keep only findings on lines added or modified since GIT_REF
                   (git diff -U0 GIT_REF -- <file>); untracked files count as wholly changed;
                   pure deletions change no line; file-level rules report only when the file
                   has at least one changed line; run from inside the repo
  --list-rules: print every rule id, severity and title, then exit 0
exit: 0 no findings · 1 findings · 2 usage error, unreadable path, or git failure (message on stderr)
```

`SCHEMA:` text output, one finding per line, sorted by path then line then rule id:
```
<path>:<line>  <rule-id>  <P0|P1|P2|P3>  <message>
```
`SCHEMA:` json output: `{"findings": [{"path": str, "line": int, "rule": str, "severity": "P0"|"P1"|"P2"|"P3", "message": str}], "scanned": int}`

Paths print relative to the current directory when under it, else absolute.

`CONTRACT:` the rule registry is a module-level `RULES` sequence; each rule exposes `id: str`,
`severity: str`, `title: str`, and a check callable over one file's text returning
`(line, message)` pairs. `test_interface_design_skill.py` imports `RULES` for the parity test.

Tailwind class strings are the string literals inside `className=`/`class=` attributes and inside
calls to `cn(`, `clsx(`, `cva(`, `twMerge(`; template literals count. Classes with variant prefixes
(`hover:`, `md:`, `dark:`) are matched by their base utility, except where a rule names a prefix.

### Detector rules (exactly these 20 ids)

Back-link: [Key decisions](logic.md#key-decisions-and-rationale) (checklist plus detector). Each
fires on CSS/SCSS rules and on Tailwind classes where both forms exist.

| id | sev | fires when |
|---|---|---|
| `focus-outline-removed` | P0 | `outline: none`/`outline: 0` in a CSS block, or Tailwind `outline-none`, with no `:focus-visible` replacement (CSS: no `:focus-visible` rule in the same file; Tailwind: no `focus-visible:` class in the same class string) |
| `a11y-click-on-div` | P0 | `<div` or `<span` opening tag with `onClick=` and no `role=` |
| `a11y-zoom-disabled` | P0 | `user-scalable=no` or `maximum-scale=1` (also `1.0`) anywhere |
| `a11y-img-no-alt` | P1 | `<img` opening tag with no `alt` attribute |
| `a11y-positive-tabindex` | P1 | `tabIndex=` / `tabindex=` with a value > 0 |
| `forms-placeholder-as-label` | P1 | `<input` or `<textarea` with `placeholder=` and none of `aria-label`, `aria-labelledby`, `id=` |
| `forms-paste-blocked` | P1 | `onPaste=` whose handler text on that line contains `preventDefault` |
| `a11y-autofocus` | P2 | `autoFocus` / `autofocus` attribute |
| `motion-transition-all` | P2 | `transition: all` / `transition-property: all`, or Tailwind `transition-all` |
| `motion-layout-property` | P2 | `transition`/`animation` naming `width`, `height`, `top`, `left`, `right`, `bottom`, `margin` or `padding` |
| `motion-no-reduced-motion` | P2 | file has `@keyframes` or `animation:` and no `prefers-reduced-motion`; reported at the first such line |
| `type-tiny-text` | P2 | `font-size` below 12px (px, or rem/em below 0.75), or Tailwind `text-[Npx]` with N < 12 |
| `type-justified` | P3 | `text-align: justify` or Tailwind `text-justify` |
| `content-three-dots` | P3 | `...` inside JSX text or a string literal ending with `...` (use `…`); spread syntax is not text |
| `layout-z-index-escalation` | P3 | `z-index` ≥ 999, or Tailwind `z-[N]` with N ≥ 999 |
| `slop-gradient-text` | P3 | `background-clip: text` with a gradient background in the same block, or Tailwind `bg-clip-text` with a `bg-gradient-*`/`bg-linear-*` class in the same string |
| `slop-hard-offset-shadow` | P3 | `box-shadow` with non-zero x and y offsets and a zero blur (`4px 4px 0`) |
| `slop-glow-shadow` | P3 | `box-shadow` with zero offsets, blur ≥ 16px and a non-grey color (any `rgb/rgba/hsl/#hex` whose channels are not all equal) |
| `intent-side-stripe` | P3 | `border-left` width 2–8px solid on a block that also sets `border-radius`, or Tailwind `border-l-[2-8]` with `rounded*` in the same string |
| `intent-overused-font` | P3 | `font-family` (or Tailwind `font-[...]`) whose first family is Inter, Geist, Roboto or Arial |

`intent-*` ids are the check-intent flags; their message says "justify or change".

### checklist.md

Back-link: [The Review job](logic.md#review), [What comes from where](logic.md#key-decisions-and-rationale).

- Grouped under headings by category: Accessibility, Focus, Forms, Motion, Typography, Content &
  copy, Images, Performance, Navigation & state, Touch & interaction, Layout & containers, Theming,
  Locale & i18n, Hydration, Product craft, Slop tells, Check-intent.
- Every rule is one bullet starting with its id in backticks and its severity:
  `` - `rule-id` P1 — rule text. `` Detector-covered rules end with the literal ` (detector)`.

`REGEX:` rule bullet: `^- \`([a-z0-9]+(?:-[a-z0-9]+)+)\` (P[0-3]) — .+$`

- Ids are `<category>-<slug>` in lowercase kebab case. The 20 detector ids are fixed above;
  every other id is the implementer's choice within that regex. These checklist-only ids are
  pinned because scenarios depend on them: `intent-eyebrow-label` P3 and `intent-hero-metric` P3
  (check-intent, [SC-5](logic.md#review)), and `drift-system-value` P1 (a value that differs from
  `.quirk/design/system.md`, [SC-6](logic.md#review)). The Check-intent heading holds every
  `intent-*` id, detector-covered or not.
- Parity invariant: the set of ids on bullets ending ` (detector)` equals the set of `RULES` ids;
  ids are unique across the file.
- Covers every rule section of `$SRC/wig/command.md` lines 14–166 (rewritten, not pasted), the
  product-relevant impeccable detector rules listed in the logic spec's Industry Insights and in
  `$SRC/imp/docs/CLI-CONTRACT.md:289`, the polish drift taxonomy, and a `power-user` persona check.

### upstream_diff.py

Back-link: [SC-12](logic.md#maintenance).

`CONTRACT:`
```
python3 upstream_diff.py [--notice PATH]     default: ../NOTICE.md relative to the script
exit: 0 every source at its pin · 1 at least one source moved · 2 parse error or git failure
```
For each source row it runs `git ls-remote <repo> HEAD`; when HEAD differs from the pin it does a
blob-less clone into a temp dir and prints the commit count, `git log --oneline <pin>..HEAD -- <path>`
and `git diff --stat <pin> HEAD -- <path>`. The blob-less filter is best-effort (a `file://` remote ignores it). It never writes inside the repo. `repo` may be any URL
git accepts, including `file://`, which is how the test runs offline.

`SCHEMA:` NOTICE.md sources table (the parser reads only this table):
```
| source | repo | path | license | pinned |
|---|---|---|---|---|
| interface-design | https://github.com/Dammyjay93/interface-design | .claude | MIT | 2f9be3206855… (full 40-char sha) |
| web-interface-guidelines | https://github.com/vercel-labs/web-interface-guidelines | command.md | MIT | 434b7f91364665f2f733b310ec54809bf8f37937 |
| web-design-guidelines-skill | https://github.com/vercel-labs/agent-skills | skills/web-design-guidelines | MIT | <full sha of 1a2c79d4e6c4> |
| impeccable | https://github.com/pbakaus/impeccable | skill | Apache-2.0 | <full sha of 8c7b98c0ae13> |
```
Full SHAs come from `git -C $SRC/<dir> rev-parse HEAD` for `id`, `vercel` and `imp`; `$SRC/wig` is not a git checkout, so its SHA is the one written in the table above, verbatim. Below the table, NOTICE.md states that all
content was rewritten and modified, and that `surfaces/ios.md` and `surfaces/android.md` derive via
impeccable from ehmo/platform-design-skills (MIT), carrying the attribution block from `$SRC/imp/NOTICE.md` verbatim.

### trigger-evals.json

Back-link: [SC-9](logic.md#boundaries).

`SCHEMA:` `{"skill_name": "interface-design", "queries": [{"query": str, "should_trigger": bool}]}`
— at least 10 true and 10 false. False cases must include the four negatives in
[SC-9](logic.md#boundaries) (HTML report, mini app, landing page) plus generic non-UI coding asks.

### system.md format

Back-link: [Conceptual model](logic.md#conceptual-model). `references/system-md.md` defines the file
at `.quirk/design/system.md` with sections `## Direction`, `## Depth`, `## Spacing`, `## Type`,
`## Color`, `## Patterns`; patterns record measured values (e.g. `Button primary — 36px h · 12px 16px
pad · 6px radius · 14px/500`). Upstream template: `$SRC/id/reference/system-template.md`; examples:
`$SRC/id/reference/examples/*.md`.

## Source map

Back-link: [Key decisions](logic.md#key-decisions-and-rationale) (rewritten, not vendored; conflicts).

Which upstream files feed which reference (all rewritten in quirk's voice):

| target | sources |
|---|---|
| SKILL.md | `$SRC/id/.claude/skills/interface-design/SKILL.md` (stance, intent, where defaults hide, workflow) |
| build.md | the same file (domain exploration, direction block, craft tests, image pass); `$SRC/imp/skill/reference/operate.md`, `mode-operate.md`, `craft-floor.md:15` (browser surfaces), `clarify.md:37,47-59` |
| system-md.md | `$SRC/id/reference/system-template.md`, `examples/system-precision.md`, `examples/system-warmth.md` |
| review.md | `$SRC/id/.claude/commands/design-review.md`, `design-deslop.md`; `$SRC/vercel/skills/web-design-guidelines/SKILL.md`; `$SRC/imp/skill/reference/polish.md:11-18,39-45`, `critique.md:684-711` |
| checklist.md | `$SRC/wig/command.md`; `$SRC/imp/skill/reference/craft-floor.md`; `$SRC/imp/crates/foundation/src/registry.rs` |
| moves/<m>.md | `$SRC/imp/skill/reference/<m>.md` (and `audit.native.md`, `adapt.native.md` folded into their move as a native note) |
| surfaces/read.md | `$SRC/imp/skill/reference/mode-read.md` |
| surfaces/ios.md, android.md | `$SRC/imp/skill/reference/ios.md`, `android.md` |

## DO-NOT-CHANGE fences

- `skills/writing-html-artifacts/**` and `skills/building-mini-apps/**` — the logic spec keeps them
  separate; the trigger evals depend on their scope staying put.
- `skills/brainstorming/references/ux-review.md` outside the "Look and content" list
  (lines 50–54) — the rest is the shipped UX-review contract, tested by
  `tests/test_brainstorming_*`.
- `$SRC/**` — upstream checkout; read only, never executed.

## Always / Ask / Never

- **Always:** stdlib-only Python 3 with `from __future__ import annotations` and type hints; rewrite
  upstream text rather than paste it (rule phrasings of one sentence may stay close); keep every
  reference one level deep under `references/` (plus `moves/`, `surfaces/`); write `.quirk/design/`
  instructions so the agent creates the directory when saving.
- **Ask:** adding or removing a detector rule (a `RULES` entry), or dropping a Refine move. Checklist-only ids need no ask.
- **Never:** call impeccable's binary, browser scripts, hooks, PRODUCT.md or DESIGN.md from any
  reference; fetch anything at review time; read or write `.interface-design/`; touch the fenced
  files.

## Cross-cutting

- **Licensing:** Apache-2.0 §4 requires the license text and a statement of changes; both MIT
  sources require the copyright notice. Copy `$SRC/id/LICENSE`, `$SRC/wig/LICENSE`, `$SRC/imp/LICENSE`
  into `licenses/`.
- **Security:** detect.py reads files only; `--changed-since` shells out to `git` with an argument
  list, never a shell string. upstream_diff.py clones into `tempfile.mkdtemp()` and removes it.

## Testing strategy

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals) (done means).

COMMAND: `python3 -m pytest -q tests/test_interface_design_skill.py tests/test_interface_design_detect.py tests/test_interface_design_upstream.py`

- **test_interface_design_detect.py:** `fixtures/interface-design/dirty/` holds one file per rule
  id named `<rule-id>.<ext>`; each must produce that rule id (and the expected line, marked in the
  fixture by a trailing `/* expect */` or `{/* expect */}` comment). `clean/` holds a realistic
  component set (a CSS file, two TSX files with Tailwind) that must exit 0. Also: exit codes 0/1/2,
  json format shape, `--list-rules` lists exactly `RULES`, and `--changed-since` against a temp git
  repo reports only findings on changed lines.
- **test_interface_design_skill.py:** frontmatter and description terms; body ≤ 300 lines; every
  `references/**.md` linked from SKILL.md and every link resolving; every reference over 100 lines
  has a contents list; trigger-evals shape and counts; checklist bullet regex and id uniqueness;
  detector parity; NOTICE.md table rows and `licenses/` files exist; no reference mentions
  `impeccable context`, `impeccable detect`, `PRODUCT.md`, `DESIGN.md` or `.interface-design/`
  except NOTICE.md and SKILL.md's one "never read" line.
- **test_interface_design_upstream.py:** NOTICE parser over a fixture string; drift run against two
  local `file://` repos (one at its pin, one moved) gives exit 1 and names only the moved source;
  malformed table gives exit 2.
- README count tests listed under Code references must stay green.

## Pending decision

`mock-style-conflict` (asked of the user): whether brainstorming mocks adopt system.md's structure,
nothing, or its full direction. Until answered, no task edits `ux-review.md`, and SC-11 is not
built. The logic spec is amended once answered.

## Non-goals

No full-code-review lens, no Vue/Svelte/HTML detector coverage, no computed-layout or contrast
checks, no CHANGELOG entry (releasing-quirk stamps it), no edits to using-quirk (it has no skill
catalog; the logic spec's mention of one is corrected by amendment).
