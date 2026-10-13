# writing-html-artifacts: tech spec

**Status**: Approved by the user, 2026-10-13; amended 2026-10-13 (see end) · Logic spec: [logic.md](logic.md)

This document says where to work and what must hold. Paths are relative to the repo root. `$SKILL`
means `skills/writing-html-artifacts/`. Line anchors are against `ac902bd`.

Every script is Python 3.9+ stdlib (`pyproject.toml:4`) except the Node pieces named in §1. Python
files open with `from __future__ import annotations`, like every in-skill script today.

## 1. Files and ownership

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

| Area | Files | Change |
|---|---|---|
| Skill entry | `$SKILL/SKILL.md` | new: workflow, delivery note, links to references |
| References | `$SKILL/references/design-reference.md`, `templates.md`, `companion.md` | new |
| Builder CLI | `$SKILL/scripts/quirk_html.py` | new: `build`, `build-app`, `check`, `verify`, `note`, `templates` subcommands |
| Builder library | `$SKILL/scripts/htmlkit/` (`__init__.py`, `manifest.py`, `resolve.py`, `tokens.py`, `assemble.py`, `checks.py`, `header.py`, `vendor.py`, `app.py`, `fsutil.py`) | new |
| Companion | `$SKILL/scripts/companion.py` | new: `start`, `show`, `wait`, `events`, `stop` |
| Pins | `$SKILL/scripts/pins.py` | new: `verify` (offline), `check` (network) |
| Verify (Node) | `$SKILL/scripts/verify/{package.json,pnpm-lock.yaml,verify.mjs}` | new |
| Vendor build (Node, maintainer only) | `$SKILL/scripts/vendor-build/{package.json,pnpm-lock.yaml,build-webawesome.mjs}` | new |
| Vendored libraries | `$SKILL/vendor/libraries.json`, `$SKILL/vendor/<lib>/<version>/…` | new |
| House theme | `$SKILL/theme/{house.tokens.json,base.css,chrome.js}` | new |
| Built-in templates | `$SKILL/templates/{report,components,companion,app}/` | new |
| Evals | `$SKILL/evals/trigger-evals.json` | new |
| Brainstorming | `skills/brainstorming/visual-companion.md` (rewrite; it must say terminal input outranks clicks), `skills/brainstorming/SKILL.md:357-374` (offer text) | modify |
| Exploring ideas | `skills/exploring-ideas/visual-companion.md` (rewrite; same terminal-priority rule), `skills/exploring-ideas/SKILL.md:178,188-196`, `skills/exploring-ideas/references/interaction-model.md:110` | modify |
| Isles removal | `bin/agent_isles.py`, `packs/quirk/`, `examples/agent-isles/`, `docs/agent-isles-artifacts.md`, `tests/test_agent_isles_{bridge,wait,pack}.py` | delete |
| Repo docs | `README.md:9` (count 25→26), `README.md:62-71` (Isles section), `.gitignore:10,15` | modify |
| Tests | `tests/test_writing_html_artifacts_skill.py`, `tests/test_html_builder.py`, `tests/test_html_companion.py`, `tests/test_html_vendor.py`, `tests/test_html_verify.py`, `tests/test_isles_removed.py` | new |

## 2. Architecture

Back-link: [Data flow](logic.md#data-flow).

- `quirk_html.py` and `companion.py` are thin CLIs. They put `Path(__file__).resolve().parent` on
  `sys.path` (the filing-scripts pattern, `skills/filing-requests/scripts/template_resolve.py:18-23`)
  and import `htmlkit`. Every subcommand writes exactly one JSON object to stdout, the same shape
  convention as `skills/adversarial-review/SKILL.md:65-68`. Diagnostics go to stderr.
- `htmlkit` owns all logic so tests import it directly. Module responsibilities:
  - `manifest.py`: parse and validate `template.json` and `libraries.json`
  - `resolve.py`: template lookup across levels, invalid-template skipping
  - `tokens.py`: merge token layers, emit the `:root` CSS
  - `assemble.py`: tier-1 build (source file → HTML)
  - `checks.py`: static checks over a built file
  - `header.py`: write and read the artifact header and license block
  - `vendor.py`: locate a library version, verify checksums, produce inline blocks
  - `app.py`: tier-2 scaffold, install, build, post-process
  - `fsutil.py`: atomic writes and self-ignoring directories
- `companion.py` builds screens with `htmlkit.assemble` against the `companion` template, then runs
  an `http.server.ThreadingHTTPServer` in a detached process.
- Node runs only in `scripts/verify/` (Playwright), in tier-2 builds (`pnpm`), and in
  `scripts/vendor-build/` (maintainer-time esbuild). Python never imports from them; it shells out.
- Agents locate scripts relative to the skill directory. SKILL.md and both companion guides say:
  `SKILL_DIR` is the directory holding this skill's SKILL.md, which the host shows when the skill
  loads. The brainstorming and exploring-ideas guides reach the companion as
  `<their skill dir>/../writing-html-artifacts/scripts/companion.py`. No `$CLAUDE_PLUGIN_ROOT` in
  any new or rewritten text.

## 3. Data models

### 3.1 Template manifest: `template.json`

Back-link: [Templates](logic.md#templates).

SCHEMA:

```
{
  "schema": 1,                         // int; only 1 is valid
  "name": "report",                    // must equal the template directory name; [a-z0-9-]{1,40}
  "description": "Use when ...",       // 30..400 chars, starts with "Use when"
  "tier": 1,                           // 1 | 2
  "libraries": ["simple-css", "alpine"],        // tier 1: names in libraries.json, or in this template's vendor/
  "optional_libraries": ["chartjs", "mermaid"], // tier 1: a source file may request these
  "slots": { "main": {"required": true, "description": "..."} },  // tier 1: 1..3 entries
  "skeleton": "skeleton.html",         // tier 1, relative path
  "tokens": "tokens.json",             // optional, relative path (§3.3 shape)
  "rules": "rules.md",                 // optional design-rules addendum
  "example": "example.src.html",       // tier 1: a source file (§3.4); tier 2: a directory overlay
  "project": "project/"                // tier 2 only: Vite project with package.json + pnpm-lock.yaml
}
```

- A library name is resolved first in the template's own `vendor/libraries.json`, then in
  `$SKILL/vendor/libraries.json`. A template-level entry with the same name as a built-in shadows it
  for that template only.
- Custom templates (project or user level) also need `verified.json` (§3.6). Built-ins don't.

### 3.2 Vendored libraries: `vendor/libraries.json`

Back-link: [Conceptual model](logic.md#conceptual-model).

SCHEMA:

```
{
  "schema": 1,
  "libraries": {
    "<name>": {
      "current": "<version>",          // version new builds use
      "versions": {
        "<version>": {
          "package": "<npm name>",     // used by pins.py check
          "license": "MIT",            // SPDX id
          "license_file": "LICENSE",   // relative to vendor/<name>/<version>/
          "source": "<url>",           // where the files came from
          "files": [
            {"path": "cdn.min.js", "kind": "js" | "css",
             "sha256": "<hex of the raw file>",
             "inline_sha256": "<hex of the escaped form that is inlined>",
             "position": "head" | "body-end",
             "inline": true}           // false: served by the companion only, never inlined
          ]
        }
      }
    }
  }
}
```

v1 contents (exact versions; the implementer records sha256 values from the downloaded files):

| name | package@version | files | notes |
|---|---|---|---|
| `simple-css` | `simpledotcss@2.3.7` | `simple.min.css` | no manual dark toggle; `theme/base.css` adds one |
| `alpine` | `alpinejs@3.17.4` | `dist/cdn.min.js`, saved as `alpine.min.js`, position `body-end` | self-starts; must come after markup and after any Alpine plugin |
| `webawesome` | `@awesome.me/webawesome@3.14.0` | `webawesome.bundle.js` (IIFE), `webawesome.css` | produced by `scripts/vendor-build/build-webawesome.mjs`; free components only |
| `chartjs` | `chart.js@4.5.1` | `dist/chart.umd.js`, saved as `chart.umd.js` | already minified |
| `mermaid` | `mermaid@12.2.0` | `dist/mermaid.min.js` (about 5.2 MB IIFE) | never use the `.mjs` build; it loads chunks |

**Old versions are never deleted.** A pin bump adds a `versions` entry and moves `current`; the
previous directory stays so frozen artifacts rebuild. `pins.py verify` enforces that every listed
version's files exist and match.

### 3.3 Tokens: `house.tokens.json` and template `tokens.json`

Back-link: [Conceptual model](logic.md#conceptual-model), [Templates](logic.md#templates).

SCHEMA:

```
{
  "schema": 1,
  "color":  { "<role>": ["<light>", "<dark>"] },   // roles: bg, surface, text, text-muted, border,
                                                    // accent, accent-text, good, warn, critical, focus
  "font":   { "sans": "<stack>", "mono": "<stack>", "display": "<stack>" },
  "size":   { "<step>": "<css length>" },           // body, small, h1..h4
  "space":  { "<step>": "<css length>" },           // 1..8 on a 4px base
  "radius": { "sm": "4px", "md": "6px", "pill": "999px" }
}
```

- Every color is a light/dark pair. A single string is invalid.
- `tokens.py` merges layers in this order, later wins per key: house → user
  `~/.quirk/html-templates/tokens.json` → project `.quirk/html-templates/tokens.json` → the
  template's own `tokens` file. The two shared files are how project tokens reach built-in
  templates, the companion included.
- Emitted CSS uses `--q-<group>-<key>` names. It defines light values on `:root`, dark values under
  `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {…} }`, and dark values
  again under `:root[data-theme="dark"]`.
- `theme/base.css` maps `--q-*` onto Simple.css's variables (`--bg`, `--accent-bg`, `--text`,
  `--text-light`, `--border`, `--accent`, `--accent-hover`, `--accent-text`, `--code`,
  `--preformatted`, `--marked`, `--disabled`) and onto Web Awesome's brand and surface variables.
  It must override Simple.css's light values explicitly too, because Simple.css's own dark media
  block would otherwise win on a dark OS when the user picked light.
- System font stacks only. No `@font-face`, no `url()` fonts.

### 3.4 Tier-1 source file: `<slug>.src.html`

Back-link: [Picking a template and a tier](logic.md#picking-a-template-and-a-tier), [Building](logic.md#building).

The agent writes this file; the builder reads it. Format:

- Line 1 is a header comment containing one JSON object:
  `<!-- quirk-src {"template": "report", "title": "...", "mode": "offline", "libraries": ["chartjs"], "interactions": ["sort the table by column"], "data": "timings.json", "tier_reason": "..."} -->`
  - `template` (required), `title` (required), `mode` (`offline` default | `connected`),
    `libraries` (subset of the template's `optional_libraries`), `interactions` (list of strings,
    may be empty), `data` (optional path to a JSON or CSV file, relative to the source file),
    `tier_reason` (optional; set when the agent overrode the signal list).
- The rest is slot sections. Each starts with a line that is exactly `<!-- slot: <name> -->`.
  Content runs to the next such line or end of file. Text before the first slot line, other than
  the header, is an error.
- REGEX: `^<!-- slot: ([a-z][a-z0-9-]{0,30}) -->$` (one per line, matched with `re.M`)

### 3.5 Artifact header and license block

Back-link: [Building](logic.md#building), [Delivery](logic.md#delivery).

- The built file starts `<!doctype html>` and the next line is the header:
  `<!-- quirk-html-artifact {...} -->`.

SCHEMA:

```
{
  "schema": 1,
  "template": "report", "template_level": "builtin" | "user" | "project",
  "tier": 1 | 2, "tier_signal": "<signal or 'judgment: <reason>'>" | null,
  "mode": "offline" | "connected",
  "libraries": { "<name>": "<version>" },
  "sidecar": "<file name>" | null,
  "built_at": "<ISO 8601 UTC>",
  "quirk_version": "<from .claude-plugin/plugin.json when present, else 'unknown'>"
}
```

- `--` inside any JSON string is written as `--` so the comment can't close early.
- Directly after the header, one comment per inlined library:
  `<!-- license: <name> <version> <SPDX> | <first copyright line of the license file> -->`.
- Each inlined library is wrapped as `<style data-quirk-lib="<name>@<version>">` or
  `<script data-quirk-lib="<name>@<version>">`. Inside a script block every `</script` is written
  as `<\/script` before hashing into `inline_sha256`. Inside a style block every `</style` is
  written as `<\/style`.

### 3.6 `verified.json` (custom templates only)

Back-link: [Templates](logic.md#templates).

SCHEMA: `{"schema": 1, "verified_at": "<ISO>", "browser": true | false, "hashes": {"<relative path>": "<sha256>"}}`
covering `template.json`, the skeleton, tokens, rules, every file under `vendor/`, and the example.
For tier 2 it covers `template.json` and every file under `project/` and `example/` except
`node_modules` and `dist`; for tier 1 it also covers the example's data file. A
missing file or a hash mismatch makes the template invalid with reason `unverified`.

### 3.7 Companion screen spec: `screen.json`

Back-link: [Companion](logic.md#companion).

SCHEMA:

```
{
  "title": "Layout",                          // short; becomes the <title>
  "question": "Which layout fits the dashboard?",
  "select": "single" | "multi",
  "options": [ {"id": "two-col", "label": "Two column", "description": "...", "html": "<optional mockup>"} ],  // 2..4
  "content": "<optional freeform HTML: mockup, comparison, notes>",
  "diagram": "<optional Mermaid source>"
}
```

- Every screen has 2 to 4 options, as the logic spec requires, with unique `id`s matching `[a-z0-9-]{1,40}`. A screen that only shows something still offers choices about it.
- `diagram` makes the screen reference the server-served Mermaid build (§4.4).

### 3.8 Companion state directory

Back-link: [Companion](logic.md#companion).

`<session>/` is under `.quirk/brainstorm/`, for brainstorming and exploring-ideas alike.

| Path | Writer | Content |
|---|---|---|
| `screens/NNNN-<slug>.html` | `show` | the built screen; `NNNN` is a zero-padded counter, never reused |
| `state/current.json` | `show` | `{"screen": "NNNN-<slug>", "nonce": "<token>", "shown_at": <epoch float>}` |
| `state/server-info` | `start` | the `server-started` JSON |
| `state/server-stopped` | server on exit, or a client that finds the recorded pid dead | `{"reason": "idle" | "stop" | "signal" | "stale", "at": <epoch>}`; `stale` is written by a client only when the recorded pid is dead |
| `state/events` | server | JSONL, one record per accepted event |

Event record SCHEMA:
`{"type": "click" | "proceed", "screen": "NNNN-<slug>", "nonce": "<token>", "choice": "<id>" | null, "text": "<label>", "selected": ["<id>", ...], "note": "<string>" | null, "timestamp": <epoch float>}`

## 4. Contracts

### 4.1 `quirk_html.py` subcommands

Back-link: [Building](logic.md#building), [Static checks](logic.md#static-checks), [Delivery](logic.md#delivery).

CONTRACT:

```
quirk_html.py templates list   [--project-dir DIR] → {"templates": [{name, level, tier, description, path}], "warnings": [{name, level, path, reason}]}
quirk_html.py templates validate PATH              → {"valid": bool, "errors": [str]}
quirk_html.py templates new NAME --level project|user [--base TEMPLATE] [--from ARTIFACT.html] [--project-dir DIR]
                                                    → {"path": str, "next": [str]}
quirk_html.py templates verify NAME [--project-dir DIR] → {"passed": bool, "browser": bool, "report": {...}}   (writes verified.json on pass)
quirk_html.py build SRC.html [--out FILE] [--upgrade] [--project-dir DIR] → BuildResult
quirk_html.py build-app SLUG --title TITLE [--mode offline|connected] [--signal TEXT] [--template NAME] [--upgrade] [--project-dir DIR] → BuildResult
quirk_html.py check FILE                            → CheckResult
quirk_html.py verify FILE [--out-dir DIR]           → VerifyResult
quirk_html.py note FILE                             → {"markdown": "<delivery note>", "verify_stale": bool}
```

- `BuildResult`: `{path, size, sidecar|null, source_dir|null, template, template_level, tier, tier_signal, mode, libraries, warnings: [str], checks: CheckResult, cut: [str]}`.
- `CheckResult`: `{passed: bool, failures: [{check, detail}], warnings: [{check, detail}]}`.
- `VerifyResult`: `{status: "passed" | "failed" | "not-browser-verified", file_sha256, browser, checks: {...}, screenshots: [paths], requests: [urls]}`.
- Exit codes: `0` success; `1` the build finished but a static check or verify check failed;
  `2` usage error, unknown or invalid template, or malformed source; `3` tier-2 unavailable
  (`build-app` only: Node or pnpm missing, install failed, or build failed; `reason` in the JSON).
  `verify` returns `0` with `status: "not-browser-verified"` when no browser is found.
- `--project-dir` defaults to the git toplevel of the current directory, else the current
  directory. The user template root is `$QUIRK_HTML_USER_DIR` when set, else
  `~/.quirk/html-templates`. Tests set the variable; nothing else reads it.
- Output defaults: `build` writes `<project>/.quirk/html/<slug>.html` where `slug` is the source
  file's name minus `.src.html`. `build-app` uses `<project>/.quirk/html/<slug>/` for the source
  and `<project>/.quirk/html/<slug>.html` for the bundle.
- **Every write into `.quirk/html/` or `.quirk/brainstorm/` first ensures a `.gitignore` containing
  `*` in that directory**, the same self-ignoring pattern as `bin/artifact_lib.py:20`.
- Writes are atomic (temp file plus `os.replace`), as `render_spec.py:3229-3248` does.

### 4.2 Build behavior (`assemble.py`, `app.py`)

Back-link: [Building](logic.md#building), [Modes](logic.md#modes).

- **Template resolution** (`resolve.py`): levels in order project `.quirk/html-templates/<name>/`,
  user root `<name>/`, built-in `$SKILL/templates/<name>/`. The first *valid* match wins. Each
  invalid match adds a warning `{name, level, path, reason}` and the search continues to the next
  level. No valid match at any level is exit 2.
- **Skeleton placeholders** are literal strings replaced once each:
  `{{header}}`, `{{title}}`, `{{head}}` (library CSS, token CSS, `base.css`), `{{chrome}}` (the
  theme toggle and, with a sidecar, the file picker), `{{slot:<name>}}` per declared slot,
  `{{data}}` (embedded data or nothing), `{{body_end}}` (library JS, then `chrome.js`). A skeleton
  missing any of these except `{{data}}` fails validation. An unknown `{{…}}` left after
  substitution is exit 2.
- **Library order**: CSS in manifest order in `{{head}}`; JS in manifest order in `{{body_end}}`,
  Alpine last.
- **Frozen versions**: when the output file exists and has a readable header, the builder uses
  the header's library versions, not `current`. `--upgrade` uses `current` and lists the version
  changes in `warnings`. A recorded version missing from `libraries.json` is exit 2 with a message
  naming `--upgrade`.
- **Data**: `data` in the source is embedded as
  `<script type="application/json" id="quirk-data">…</script>` with every `<` written as `<`
  (as `render_spec.py:3288` does). When the build with data embedded would exceed the 10 MB
  fail limit, the builder instead copies the data to `<slug>.data.<ext>` beside the output, sets `sidecar` in the
  header, and `{{chrome}}` includes the file picker. `chrome.js` exposes
  `window.quirkData(): Promise<any>`, resolving from the embedded block or from the picked file;
  CSV is returned as an array of row objects. Page code reads data only through it.
- **Tier 2** (`app.py`), in order:
  1. If `.quirk/html/<slug>/` is absent, copy the template's `project/` there, then the example
     overlay. Never overwrite an existing source folder. `--title`, `--mode` and `--signal` are
     saved to `.quirk/html/<slug>/quirk-app.json` (`{"template", "title", "mode", "tier_signal"}`)
     on the first build; later builds read that file, and a flag given again overrides and updates
     it. The header takes its `title`, `mode` and `tier_signal` from there.
  2. Find `pnpm` on PATH, else `corepack pnpm`. Neither found is exit 3 with reason `no-pnpm`.
     `node` missing is exit 3 with reason `no-node`.
  3. `pnpm install --frozen-lockfile --ignore-scripts --ignore-pnpmfile` (so a cloned repo's template
     can't run install scripts or a pnpmfile), then `pnpm run build` (the merged token layers are first written to `src/quirk-tokens.css`),
     each with a 600 s timeout. A failure
     is exit 3 with reason `install-failed` or `build-failed` and the last 40 lines of output.
  4. Read `dist/index.html`, insert the header and one license comment per production dependency
     listed in the template's `package.json` (license read from
     `node_modules/<pkg>/package.json`), write `.quirk/html/<slug>.html`, and run the static checks.
- **Exit 3 is the fallback signal.** The skill tells the agent to write a tier-1 source instead and
  list the cuts. The CLI never falls back on its own.

### 4.3 Static checks (`checks.py`)

Back-link: [Static checks](logic.md#static-checks), [Modes](logic.md#modes).

Run on every `build`, `build-app`, `show` and `check`. Two kinds of block are excluded from the
reference scan and checked by hash instead:

- library blocks (`data-quirk-lib`), against `inline_sha256`
- shell blocks (`<script data-quirk-shell="<name>">`), which hold `theme/chrome.js` or
  `templates/companion/companion.js` with the same escaping; their content hash must equal the
  escaped hash of the shipped file. `companion.js` is where the companion's same-origin `fetch`
  calls live.

| Check | Failure when |
|---|---|
| `header` | the header is missing, unparseable, or lacks a schema field |
| `license` | an inlined library has no license comment |
| `checksum` | a library block's content hash differs from `inline_sha256` for that name and version, or a shell block differs from its shipped file |
| `external-refs` (offline) | outside library blocks: any `src`, `href`, `srcset`, `poster`, `action` or `data` attribute, CSS `url()`, or `@import` with an `http:`, `https:` or `//` target; or a `fetch(`, `XMLHttpRequest`, `WebSocket(` or `EventSource(` call |
| `external-refs` (connected) | as above, but only `<script src>`, `<link href>`, `@import`, and font `url()` fail; data calls are allowed |
| `external-refs` (companion) | as offline, except `src`/`href` starting `/_quirk/lib/` are allowed |
| `external-refs` (tier 2) | the bundle has no library wrappers, so only markup is scanned: `<script src>`, `<link href>`, `@import`, and CSS `url()` with an `http:`, `https:` or `//` target fail in offline mode. Runtime network behavior of the bundle is left to verify's `network` check |
| `size` | over 10 MB (fail); over 2 MB adds a warning |

- `<a href>` links to `http(s)` are navigation, not loads, and are allowed in every mode.
- Size is measured in bytes of the built file. Mermaid alone is about 5.2 MB, so a page that uses
  it always gets the 2 MB warning. That is expected and the note says so.

### 4.4 Companion (`companion.py`)

Back-link: [Companion](logic.md#companion).

CONTRACT:

```
companion.py start SESSION_DIR [--host 127.0.0.1] [--port 0] [--idle-minutes 30] [--foreground]
                          [--allow-host HOST[:PORT]]...
    → {"type": "server-started", "pid", "port", "host", "url", "screen_dir", "state_dir"}
companion.py show SESSION_DIR SCREEN.json [--project-dir DIR]
    → {"screen", "nonce", "url", "checks": CheckResult}
companion.py wait SESSION_DIR [--timeout 110]
    → {"proceed": <event record>, "clicks": [<event records for this screen, in order>]}
companion.py events SESSION_DIR [--screen ID]  → {"events": [...]}
companion.py stop SESSION_DIR                  → {"stopped": bool}
```

- `start` without `--foreground` re-executes itself detached (`subprocess.Popen` with
  `start_new_session=True`, stdio to `state/server.log`), waits until `state/server-info` appears,
  and prints it. `--allow-host` (repeatable) adds a `Host` value the server accepts, for remote or
  forwarded access. It is idempotent: a live server for the session is reused and its info printed.
- HTTP routes:
  - `GET /` → the current screen's HTML. Before any `show`, a waiting page.
  - `GET /_quirk/state` → `{"screen", "nonce"}`. Screens poll it every 2 s and show the
    "superseded" banner and disable controls when the nonce changes.
  - `GET /_quirk/lib/<name>/<version>/<file>` → that vendored file from `libraries.json`, and
    nothing else (no path traversal; unknown → 404).
  - `POST /_quirk/event` with JSON `{nonce, type, choice, text, selected, note}` → 204 when
    accepted. 409 `{"superseded": true}` when `nonce` isn't the current screen's. 403 when the
    `Origin` header is present and isn't the server's own origin, or `Host` isn't the bound
    host:port. 400 on malformed JSON or a body over 64 KB.
- The nonce is `secrets.token_urlsafe(16)`, minted by `show`, embedded only in that screen.
- `wait` reads `state/current.json` once at start and returns the first `proceed` event for that
  screen whose timestamp is at or after `shown_at`. The events file is append-only and never
  cleared, so re-running `wait` after a timeout loses nothing.
  - Exit `0` returns the payload. Exit `1` means a timeout; stderr says to re-run `wait`. Exit `2`
    means no live server (missing or unparseable `server-info`, `server-stopped` present, a
    dead pid, or a recorded port that does not answer as a companion), the same liveness rules as `bin/agent_isles.py:315-332`.
  - The default timeout of 110 s stays under a host's 120 s tool limit.
  - On exit 1 stdout is `{"status": "timeout", "screen"}`; on exit 2 it is
    `{"status": "no-server"}`.
- Other exit codes: `show` returns 0, 1 when a static check fails (the screen is still written but
  not made current), or 2 for a malformed `screen.json` or a missing session. `events` returns 0.
  `stop` returns 0 with `stopped: false` when no server was running. `start` returns 2 when the
  server didn't write `server-info` within 10 s.
- Idle shutdown: no HTTP request and no `show` for `--idle-minutes` → write `server-stopped` with
  reason `idle` and exit. `stop` sends SIGTERM and the server writes reason `stop`.
- Screens are built by `assemble.py` from the `companion` template with slots `question`,
  `options` and `content` generated from `screen.json`, mode `companion`. Mermaid is not inlined;
  the skeleton loads `/_quirk/lib/mermaid/<current>/mermaid.min.js` only when `diagram` is set.
- The companion shell's JS (`templates/companion/companion.js`, inlined) posts a `click` per option
  toggle and a `proceed` on the Proceed button, with the current selection and an optional note
  field.

### 4.5 Verify (`scripts/verify/verify.mjs`)

Back-link: [Browser verify](logic.md#browser-verify).

- Dependencies: `playwright-core@1.64.0` only, exact pin, with a committed `pnpm-lock.yaml`.
  Installed by `quirk_html.py verify` with `pnpm install --frozen-lockfile` and
  `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`. A failed install or no Node gives
  `status: "not-browser-verified"`. Verify never downloads a browser.
- Browser discovery, first that launches wins: `{channel: "chrome"}`, `{channel: "msedge"}`,
  `{executablePath: $CHROME_PATH}` when set, then Playwright's own Chromium only if
  `chromium.executablePath()` exists on disk.
- Checks, each on the `file://` URL of the given file:
  - `console`: no `console.error` and no `pageerror`, in any run.
  - `viewports`: a full-page screenshot at 375×800 and 1280×800 in each of light and dark (four
    images). At 375 the document's `scrollWidth` must not exceed its `clientWidth`.
  - `themes`: with `colorScheme` light and then dark, sample `body`, headings, `p`, `li`, `td`,
    `th`, `label`, `button` and `a`. Each sampled element with visible text must reach 4.5:1
    against its effective background, or 3:1 at 24px and up.
  - `network`: a context with `serviceWorkers: "block"`, a route on `/^https?:/` that records each
    request, and a `request` listener recording anything not `file:`, `data:`, `blob:` or `about:`.
    Offline mode aborts and fails on any recorded URL. Connected mode lets requests through
    (`route.continue()`) and reports them without failing, so the page's real behavior is verified.
- A verifier crash or timeout is `status: "failed"`.
- Output goes to `<file stem>.verify/` beside the file: `report.json` (the `VerifyResult`) and
  `375-light.png`, `375-dark.png`, `1280-light.png`, `1280-dark.png`.
- `report.json.file_sha256` is the hash of the file verify ran on. `note` compares it with the
  current file and reports `verify_stale: true` when they differ. This is what makes "verify ran on
  the final file" checkable.

### 4.6 Pins (`pins.py`)

Back-link: [Decisions Locked](logic.md#decisions-locked).

- `pins.py verify` is offline. It checks every version of every library in every built-in
  `libraries.json`: files exist, both hashes match, the license file exists. pytest runs this.
- `pins.py check` needs network and is run by a maintainer, never by CI. For each library it reads
  `https://registry.npmjs.org/<package>/latest` and queries `https://api.osv.dev/v1/query` with the
  `current` version. It reports `{name, current, latest, outdated, advisories: [ids]}` and exits 1
  when any pin is outdated or has an advisory.

### 4.7 Web Awesome vendor build

Back-link: [Templates](logic.md#templates).

- `scripts/vendor-build/build-webawesome.mjs` bundles a fixed component list from
  `@awesome.me/webawesome/dist/` with esbuild into one IIFE, and concatenates the theme CSS files
  (not the `@import` stub `styles/webawesome.css`) into `webawesome.css`.
- Component list: button, button-group, callout, card, checkbox, details, dialog, divider, drawer,
  icon, input, option, radio, radio-group, select, switch, tab, tab-group, tab-panel, tag,
  textarea, tooltip. Pro-only components are out of scope.
- It registers the `default` icon library with a resolver that returns `data:image/svg+xml,…`
  URIs from a fixed inline set, so no icon ever hits the Font Awesome CDN.
- It writes the new version directory and its `libraries.json` entry, including both hashes. It
  runs only when a maintainer bumps the pin. Its `node_modules` is never committed.
- The theme toggle sets `data-theme` on `<html>` and also Web Awesome's dark class. The implementer
  confirms the class name against 3.14.0, because its dark-mode docs page was unavailable during
  research.

### 4.8 Tier-2 `app` template

Back-link: [Templates](logic.md#templates), [Building](logic.md#building).

- `templates/app/project/package.json` pins exactly:
  - `react` and `react-dom` 19.2.8
  - `@astryxdesign/core` and `@astryxdesign/theme-neutral` 0.6.2
  - `@tanstack/react-table` 9.3.1, `@tanstack/react-query` 5.104.2, `@tanstack/react-router`
    1.170.44
  - dev: `vite` 8.3.0, `vite-plugin-singlefile` 2.3.3, `@vitejs/plugin-react` 6.1.1, `typescript`
    6.0.2

  These are the versions `skills/writing-specs/interactive/app/package.json:15-31` already runs,
  plus TanStack. A committed `pnpm-lock.yaml` is required.
- `vite.config.ts` follows the writing-specs app (`base: './'`, `viteSingleFile()`,
  `modulePreload.polyfill: false`, `assetsInlineLimit: 100_000_000`) with `outDir: 'dist'`.
- Routing uses TanStack Router's hash history, since History API routing doesn't work on `file://`.
  Route-level code splitting is off.
- The scaffold imports the house tokens as CSS and has a light/dark toggle, so tier-2 pages match
  tier-1 pages.

## 5. DO-NOT-CHANGE fences

Back-link: [Decisions Locked](logic.md#decisions-locked).

- `skills/writing-specs/interactive/**`: the user chose to leave the spec app as is
  ([Decisions Locked](logic.md#decisions-locked)). Read it as a precedent; never edit it.
- `docs/specs/2026-06-09-bidirectional-brainstorm-design.md` and
  `docs/specs/2026-06-16-exploring-ideas-design.md`: dated design records. Their Isles mentions
  are history, not live instructions.
- `CHANGELOG.md`: release automation owns it (`bin/release.py:90-95`). The PR body's
  `## Changelog` section feeds it.
- Version fields in `pyproject.toml`, `.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`: stamped by `bin/release.py:60-64`. Don't hand-bump.
- `skills/brainstorming/SKILL.md` outside the Visual Companion section (`:357-374`) and the
  companion-offer mentions at `:26,44,58,60,296`: other tests assert on this file
  (`tests/test_brainstorming_elicitation.py:208-216`, `tests/test_brainstorming_adhd_offer.py`).
  The file must stay under 400 lines.
- `bin/artifact_lib.py`: reuse its self-ignoring `.gitignore` idea; don't import or change it.
- `vendor/<lib>/<version>/` for any version already committed: frozen artifacts depend on it.

## 6. Always / Ask / Never

Back-link: [Modes](logic.md#modes), [Delivery](logic.md#delivery).

**Always**
- One JSON object on stdout per CLI call; diagnostics on stderr.
- Verify library checksums before inlining, and fail the build on a mismatch.
- Escape `</script` and `</style` in inlined blocks, and `<` in embedded JSON.
- Keep every new or rewritten instruction host-neutral: skill-relative paths, no
  `$CLAUDE_PLUGIN_ROOT`.

**Ask**
- Adding a library to v1, or any component beyond §4.7's list.
- Any change to a schema in §3 after the first task that consumes it has landed.

**Never**
- Network access from a tier-1 build, a static check, the companion, or a test.
- Downloading a browser.
- Opening or publishing an artifact.
- Deleting a vendored version directory.

## 7. Cross-cutting

Back-link: [Companion](logic.md#companion), [Hosts](logic.md#hosts).

- **Security.** The companion binds `127.0.0.1` by default. Events need the per-screen nonce. The
  `Origin` and `Host` checks block cross-site and DNS-rebinding posts. `/_quirk/lib/` serves only
  files named in `libraries.json`. Screen `content` and option `html` are agent-written and served
  as-is to the local user; the server doesn't sanitize them, which matches Isles. `--host 0.0.0.0`
  is opt-in for remote containers and the guides warn it exposes the session on the network.
- **Repo size.** Vendoring adds about 6 MB, mostly Mermaid. That's accepted for offline builds.
- **Hosts.** No new code depends on Claude-specific environment variables. Manual acceptance on pi
  and OMP is in §8.
- **Rollback.** The change is additive apart from the Isles removal. Reverting the PR restores
  Isles.

## 8. Testing strategy

Back-link: [Scope and non-goals](logic.md#scope-and-non-goals).

CI runs `pytest -q` on Python 3.12 with no Node (`.github/workflows/test.yml:22-28`), so every Node
path is skipped there, like `tests/test_compare_stage.py:469`.

| File | Must cover |
|---|---|
| `tests/test_writing_html_artifacts_skill.py` | frontmatter `name` equals dir; description 50..1024 chars and starts "Use when"; every relative link in SKILL.md and `references/` resolves; every script named in SKILL.md exists; `evals/trigger-evals.json` has 10 or more `should_trigger: true` and 10 or more `false` |
| `tests/test_html_builder.py` | manifest validation errors; resolution precedence across project, user and built-in (tmp dirs, `QUIRK_HTML_USER_DIR`); invalid-template skip warning and fall-through; every built-in tier-1 example builds and passes `check`; header round-trip with `--` in values; `</script>` escaping; frozen versions on rebuild versus `--upgrade` (with a fake two-version vendor dir); data over budget moves to a sidecar; size warn and fail thresholds; offline, connected, companion and tier-2 external-ref rules with positive and negative cases; a tampered shell block fails `checksum`; self-ignoring `.gitignore` creation |
| `tests/test_html_companion.py` | foreground server on port 0 in a subprocess; `show` then a click with the right nonce is recorded; a wrong nonce gets 409; a foreign `Origin` gets 403; `/_quirk/lib` traversal gets 404; `wait` returns proceed plus clicks; `wait` times out with exit 1 and a re-run still finds a proceed posted in between; no server gives exit 2; a new screen makes the old nonce stale; idle shutdown (fractional `--idle-minutes`) writes `server-stopped` |
| `tests/test_html_vendor.py` | `pins.py verify` passes over the built-in vendor dir; every built-in template's libraries resolve |
| `tests/test_html_verify.py` | skipped unless `scripts/verify/node_modules` exists and a browser launches: verify passes on the `report` example; it fails a fixture that fetches `https://example.com`; `note` flags a stale report after the file changes |
| `tests/test_isles_removed.py` | no file under `skills/`, `bin/`, `tests/`, `README.md` or `.gitignore` mentions `agent_isles`, `Agent Isles` or `agent-isles`, or matches the island-tag pattern `<agent-(option|choice|proceed)` (allowing this test file itself). `<agent-instructions>` in `skills/using-quirk/references/codex-tools.md:54` is unrelated and must not match |

Manual acceptance, recorded in the PR body:
- `quirk_html.py verify` passes on each built-in example, the tier-2 example included.
- A brainstorming session runs end to end on the companion in Claude Code and in pi or OMP.
- The trigger evals are run per `skills/writing-skills/activation-testing.md:22-32`.

## 9. Answers to the logic spec's open questions

Back-link: [Deferred Ideas](logic.md#deferred-ideas).

| Question | Answer |
|---|---|
| Which chart library ships | Chart.js 4.5.1 UMD (§3.2). It has the widest chart set and is MIT and maintained. Accessibility comes from `role="img"`, `aria-label` and a table view, which `rules.md` for `report` requires |
| Mermaid in the companion | served once by the companion at `/_quirk/lib/`, never inlined into screens (§4.4) |
| Manifest schema, version field, slot markers | §3.1, `schema: 1`; skeleton placeholders `{{slot:<name>}}` (§4.2); source slot lines (§3.4) |
| Header format and read-back | §3.5; frozen versions in §4.2 |
| Browser discovery, Playwright, screenshots | §4.5 |
| Pin check | §4.6 |
| Companion details from Isles | idle 30 min, `wait` 110 s, exit 2 for no server, event shape in §3.8 |
| Create from an existing artifact | `templates new --from`: a quirk-built artifact copies its source template and uses its `.src.html` as the example; any other HTML becomes a one-slot skeleton (`main` wraps the body) with house tokens, for the agent to refine before `templates verify` |
| Trigger evals | `evals/trigger-evals.json` as `{"skill_name", "queries": [{"query", "should_trigger"}]}`; shape checked by pytest, run manually |
| Design reference sections | the 14-section outline from the research, in `references/design-reference.md` |

## 10. Non-goals

- Everything in [Scope and non-goals](logic.md#scope-and-non-goals) stays out.
- No migration of existing Isles Markdown screens; they were transient.
- No sanitizing of agent-written companion HTML.
- No Windows-specific detach logic beyond what `subprocess` gives; Windows isn't a v1 host.

## 11. Amendments

- 2026-10-13, after the wave-1 review, decided by the user: tier-2 installs always use
  `--ignore-scripts` (§4.2), and connected-mode verify lets requests through while recording them (§4.5).
- 2026-10-13, from the final review: tier-2 install also passes `--ignore-pnpmfile` and tier-2 builds
  write the merged token layers to `src/quirk-tokens.css` (§4.2); `verified.json` covers every file
  under `project/` and `example/` for tier 2, plus the example's data file for tier 1 (§3.6);
  `server-stopped` may carry reason `stale`, written by a client only when the recorded pid is dead,
  and liveness also requires the recorded port to answer as a companion (§3.8, §4.4);
  `start --allow-host HOST[:PORT]` is repeatable, for remote or forwarded access (§4.4); a verifier
  crash or timeout is status `failed` (§4.5).
