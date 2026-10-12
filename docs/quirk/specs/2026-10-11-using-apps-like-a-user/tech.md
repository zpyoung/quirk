# Tech spec: `quirk:using-apps-like-a-user`

**Status:** Draft
**Logic spec:** [logic.md](logic.md)

All paths are relative to the repository root `/Users/zpyoung/ProjectWorkspaces/quirk-workspace/quirk`
unless they start with `~` or `/`.

## Architecture

Back-links: [logic: Conceptual model](logic.md#conceptual-model) · [logic: Data flow](logic.md#data-flow)

One new skill directory, one Python stdlib guard script split into small modules, three fixture apps,
and tests. Nothing outside the new directories changes except the README skill count.

| File | Role |
|---|---|
| `skills/using-apps-like-a-user/SKILL.md` | Router, see-first loop, gates, foreground warnings, stuck ladder, report rules, exit-code table. |
| `skills/using-apps-like-a-user/references/surfaces.md` | Per-surface procedure: web, Electron, native, system dialogs; driver gotchas. |
| `skills/using-apps-like-a-user/references/safety.md` | Gate classification, injection handling, credentials, login walls, sharing the Mac. |
| `skills/using-apps-like-a-user/scripts/likeuser.py` | CLI entrypoint: argparse subcommands, JSON on stdout, exit codes. |
| `skills/using-apps-like-a-user/scripts/_types.py` | Shared value types and exceptions every module exchanges. |
| `skills/using-apps-like-a-user/scripts/_run.py` | Run folder, run state, goals, findings, desktop lock, budget, credentials, gate patterns, report rendering. |
| `skills/using-apps-like-a-user/scripts/_desktop.py` | macOS primitives: cursor, frontmost app, clipboard, display scale, window list, screenshots. |
| `skills/using-apps-like-a-user/scripts/_effects.py` | Observation diffing, PNG decode and average hash, effect classification, settle loop. |
| `skills/using-apps-like-a-user/scripts/_web.py` | `playwright-cli` adapter for web and Electron renderers. |
| `skills/using-apps-like-a-user/scripts/_native.py` | Native driver adapters: `orca computer` and the bake-off winner. |
| `skills/using-apps-like-a-user/scripts/bakeoff.py` | Re-runnable native-driver bake-off harness. |
| `skills/using-apps-like-a-user/evals/` | Agent-level eval scenarios, expected findings, and a grader. |
| `tests/fixtures/using-apps-like-a-user/web/` | Static HTML plus a stdlib HTTP server with planted bugs. |
| `tests/fixtures/using-apps-like-a-user/electron/` | Minimal Electron app with planted bugs and a native save dialog. |
| `tests/fixtures/using-apps-like-a-user/native/` | Single-file SwiftUI app plus a build script producing a `.app` bundle. |
| `tests/fixtures/using-apps-like-a-user/golden/` | Captured real driver outputs (playwright-cli 0.1.22, orca) used by unit tests. |
| `tests/test_using_apps_like_a_user_<module>.py` | Unit tests, one file per module (`effects`, `desktop`, `run`, `web`, `native`, `cli`, `bakeoff`, `evals`), CI-safe on Linux. |
| `tests/test_using_apps_like_a_user_skill.py` | SKILL.md structure tests. |
| `tests/test_using_apps_like_a_user_fixtures.py` | Darwin-only integration tests driving the guard script against the fixtures. |
| `docs/quirk/specs/2026-10-11-using-apps-like-a-user/bakeoff.md` | Bake-off results, the chosen native driver, and its version pin. |

**Technologies.** Python 3.9-compatible stdlib only (local interpreter 3.9.13; CI 3.12 on Ubuntu).
macOS primitives via `ctypes` against CoreGraphics, `lsappinfo`, `osascript -l JavaScript`,
`screencapture`, `sips`, `pbpaste`/`pbcopy`. Drivers: `@playwright/cli` 0.1.22, `orca computer`
(ships with Orca), and the bake-off winner. Fixtures: Electron via pnpm, Swift 6.2 via `swiftc`.

**Module loading.** Every module under `scripts/` carries the `_SCRIPT_DIR` sys.path shim used by
`skills/filing-requests/scripts/canonical_schema.py:13-18`, so `python3 likeuser.py` and importlib
loading both work.

## Code references

Back-links: [logic: Conceptual model](logic.md#conceptual-model)

Patterns to follow, all existing:

- Script invocation from SKILL.md: `skills/adversarial-review/SKILL.md:61`
  (`${CLAUDE_PLUGIN_ROOT}/skills/<name>/scripts/...`), called as `python3 "<path>"`.
- One JSON object on stdout, diagnostics on stderr: `skills/adversarial-review/SKILL.md:65`.
- Exit-code table in SKILL.md plus a test that asserts each code is documented:
  `skills/filing-requests/SKILL.md:245-257`, `tests/test_filing_skill.py:84-87`.
- Self-ignoring scratch directory (writes a `.gitignore` containing `*`): `bin/artifact_lib.py:12-28`.
- Subprocess test harness with `sys.executable`: `tests/test_adversarial_review.py:18-27`.
- Fake external binary injected through an env var: `tests/test_filing_github_file.py:23-39`
  (`GH_BIN`), read at `skills/filing-requests/scripts/github_file.py:87`.
- Tool-presence skip: `tests/test_adversarial_review.py:2972`.
- README skill-count tests: `tests/test_adhd_skill.py:157-164`,
  `tests/test_simplifying_safely_skill.py:86-95`; the count lives at `README.md:9`.
- Frontmatter tests to mirror: `tests/test_simplifying_safely_skill.py:43-77`.

External CLI facts the adapters depend on:

- **`@playwright/cli` 0.1.22 is the pin.** The installed binary is 0.1.1 (pnpm global) and must be
  upgraded. Commands documented for 0.1.22 and used here: `open [url] [--headed]`, `-s=<session>`,
  `snapshot [--boxes]`, `screenshot [--filename]`, `click`, `dblclick`, `fill`, `type`, `press`,
  `select`, `mousemove`, `mousedown`, `mouseup`, `mousewheel`, `console [min-level]`, `requests`,
  `state-save`, `state-load`, `attach --cdp=<url>`, `attach --extension=chrome`, `detach`, `close`,
  `eval`. Output format at 0.1.22 must be re-probed before the adapter is written: the 0.1.1 probe
  showed snapshots written to `.playwright-cli/` under the **cwd** and linked from stdout, refs as
  `[ref=eN]`, the focused element as `[active]`, and action failures as a `### Error` block with
  **exit 0**. The 0.1.22 README says output defaults to stdout and failed commands exit non-zero
  since 0.1.18. The adapter handles both: it treats a `### Error` block as failure whatever the exit
  code, and runs every `playwright-cli` call with its cwd set to the run folder.
- Playwright treats an `opacity:0` input as clickable, so a successful click proves nothing about
  visibility.
- **`orca computer ... --json`** (installed 1.4.216-rc) returns `{id, ok, result, _meta}`; failures
  exit 1 with `ok:false` and `error.code` (for example `app_not_found`, `element_not_found`,
  `window_stale`, `permission_denied`). `get-app-state` returns `result.snapshot.{treeText,
  elementCount, truncation, window, focusedElementId}`; with a screenshot, the PNG is written to a
  file whose `path`, `scale`, `width`, and `height` appear under `result.screenshot`. Action commands
  return a fresh `result.snapshot` plus `result.action.verification.state` (`verified` or
  `unverified`). Element clicks activate and raise the target app (orca issue #26454).
- Cursor via `CGEventCreate(NULL)` + `CGEventGetLocation` returns global points, origin top-left of
  the primary display. Frontmost app via `lsappinfo info -only bundleid "$(lsappinfo front)"` takes
  about 10 ms with no permission prompt. Primary display backing scale is 2, the external 1.
  `screencapture` has no 1x option and exits 0 even when it fails to write; check the output file.

## Contracts & interfaces

Back-links: [logic: Data flow](logic.md#data-flow) · [logic: Behavior & scenarios](logic.md#behavior--scenarios) · [logic: Decisions Locked](logic.md#decisions-locked)

### CLI

CONTRACT:
```
likeuser.py doctor  [--surface web|electron|native]
likeuser.py begin   --target <url|app-name|bundle-id> --surface web|electron|native
                    --owner yours|third-party (--attended | --unattended)
                    [--launch <command>] [--cdp-port <n>] [--real-chrome]
                    [--allow-foreground] [--session-key <name>]
                    [--credentials-env <PREFIX> | --credentials-file <path>]
                    [--goals-file <path>] [--budget-run <n>] [--budget-goal <n>]
likeuser.py goal    --run <id> --id <goal-id> --title-stdin
likeuser.py observe --run <id> --goal <goal-id> [--no-screenshot]
likeuser.py act     --run <id> --obs <observation-id> --action <action> [target] [action args]
                    [--expect url|title|tree|focus|value|screen|any] [--gate none|requested|approved|created]
                    [--foreground] [--target-name <visible label>]
likeuser.py note    --run <id> --finding-kind visibility|accessibility|console|network|injection|undiscoverable|other
                    --summary-stdin [--obs <observation-id>]
likeuser.py verdict --run <id> --goal <goal-id> --status pass|fail|blocked|partial --summary-stdin
likeuser.py handoff --run <id> --reason login|2fa|hint
likeuser.py resume  --run <id>
likeuser.py end     --run <id> [--keep-open]
```

Action targets and arguments:

| `--action` | Target | Arguments |
|---|---|---|
| `click`, `double-click`, `right-click` | `--ref <ref>` or `--x <px> --y <px>` | none |
| `fill` | `--ref` | `--text-stdin` or `--secret username|password` |
| `type` | optional `--ref` (else current focus) | `--text-stdin` or `--secret username|password` |
| `press` | none | `--key <key>` |
| `hotkey` | none | `--key <combo>` such as `cmd+s` |
| `scroll` | optional `--ref` or `--x --y` | `--direction up|down|left|right --amount <screens>` |
| `drag` | `--ref` or `--x --y` | `--to-ref <ref>` or `--to-x --to-y` |
| `select` | `--ref` | `--value <option text>` |
| `dismiss` | `--ref` | none |

Every subcommand prints exactly one JSON object to stdout and diagnostics to stderr. Text that may be
sensitive (typed text, summaries) is read from stdin, never argv. Credentials are never read from
stdin or argv: `--secret username|password` makes the script read the value itself from
`<PREFIX>_USERNAME` / `<PREFIX>_PASSWORD` (default prefix `LIKEUSER`) or from the JSON file named by
`--credentials-file` (`{"username": str, "password": str}`, must be mode 0600 or `begin` exits 5).
The value never reaches the model, stdout, or any run file.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Command ran. For `act`, the outcome is in `status`, including `NO_EFFECT`, `DRIFT`, and `DESKTOP_BUSY`. |
| 1 | Unexpected internal error (traceback on stderr). |
| 2 | Usage or contract violation: argparse errors, `pass_without_effect`, `unattended_approval`, `unattended_handoff`, `target_name_required`, `foreground_not_allowed`, `launch_required`, `launch_requires_electron`, `created_third_party`, `coordinates_need_screenshot`, `unknown_fault`. |
| 3 | Run-state error: unknown run, run already ended, run stopped (`stopped_reason` in JSON), `desktop_busy` at `begin`. |
| 4 | Driver failure outside `act` (`begin`, `observe`, `handoff`, `resume`, `end`), with `driver_error` in JSON. |
| 5 | Missing tool, wrong tool version, missing macOS permission, missing extension, or bad credentials file. |

### `doctor`

Reports, per surface, the tools found and their versions, the pins they are checked against, and
macOS permissions: Accessibility (`AXIsProcessTrusted`), Screen Recording
(`CGPreflightScreenCaptureAccess`), plus each native driver's own permission check. Exits 5 naming
what is missing. Never opens System Settings and never installs anything.

### `begin`

- **Preconditions:** `doctor` passes for the surface. `--surface electron` requires `--launch`
  (already-running Electron apps use `--surface native`); otherwise exit 2.
- **Postconditions:**
  - A run folder exists at `<project>/.quirk/using-apps-like-a-user/runs/<run-id>/`, where
    `<project>` is the git toplevel of the cwd, else the cwd. The parent
    `.quirk/using-apps-like-a-user/` holds a `.gitignore` containing `*`.
  - A baseline is recorded: frontmost bundle id, cursor position, clipboard change count, and
    whether the clipboard holds text only. When it holds text, the text is saved to
    `clipboard.txt` (mode 0600) in the run folder.
  - Goals from `--goals-file` (`[{"id": str, "title": str}]`) are registered; more can be added with
    `goal`.
  - The driver session is open and bound to one window or browser session:
    - **Web:** a headless `playwright-cli` session named after the run id. With `--real-chrome`,
      `playwright-cli attach --extension=chrome` instead; `begin` exits 5 if the extension is
      unavailable.
    - **Electron:** `--launch` runs with `--remote-debugging-port=<cdp-port>` bound to `127.0.0.1`
      (default: the first free port in 9222-9299), then `playwright-cli attach --cdp=http://127.0.0.1:<port>`.
      The app's bundle id and window id are also bound to the native driver so OS dialogs, sheets,
      and menus stay reachable.
    - **Native:** the native driver bound to the target's bundle id and frontmost window id.
  - With `--session-key`, a saved session at `.quirk/using-apps-like-a-user/sessions/<session-key>.json`
    is loaded with `state-load` when it exists. The script does not judge whether it is still valid:
    an expired session shows as a login screen, and the skill signs in again.
- **Foreground:** a run whose native driver is not background-capable (always true for `orca
  computer`) needs the foreground for every native action. Such a run requires `--allow-foreground`;
  without it `begin` exits 2 with `foreground_not_allowed`. The lock is taken at `begin` for these
  runs and on the first `--foreground` act otherwise.
- **Errors:** missing tool, permission, extension, or bad credentials file → exit 5 with
  `missing[]`. Launch or attach failure → exit 4. Lock not obtained within 30 seconds → exit 3 with
  `desktop_busy` and the holder's `run_id` and `project`.

### Desktop lock

- **Path:** `~/.local/state/quirk/using-apps-like-a-user/desktop.lock` (machine-wide, so runs from
  different projects serialize), overridable only by `LIKEUSER_LOCK_PATH` for tests.
- **Holder record:** JSON `{run_id, project, acquired_at, last_act_at}`. Reads and writes happen
  under `fcntl.flock` on the lock file, so acquisition is atomic across processes.
- **Staleness:** a holder whose `last_act_at` is more than 15 minutes old is stale and may be
  replaced; the replacement is recorded in the new run's `events.jsonl`. Every `act` in the holding
  run refreshes `last_act_at`.
- **Release:** `end`, and `handoff` (the user is about to use the machine).
- **Mid-run acquisition failure** (`act --foreground` while another run holds the lock): `act`
  returns status `DESKTOP_BUSY` with exit 0, and the action is not performed.

### `goal`, `observe`

- `goal` registers a goal with an id and title. Re-registering an id exits 2.
- `observe` requires a registered `--goal`; every later `act` against that observation is attributed
  to that goal (budget, verdict eligibility, findings). It captures a screenshot (unless
  `--no-screenshot`), the tree, and surface metadata, writes them into the run folder, and assigns a
  monotonically increasing `observation_id`. Only the latest observation is actionable.
- For Electron runs, the observation records `screenshot_source` (`renderer` or `native`); it is
  `native` whenever a native sheet or dialog is open, and then both trees are returned.
- **Console and network findings are automatic.** On web and Electron targets, every new console
  error and failed request since the previous observation is registered as a finding of kind
  `console` or `network`, linked to the observation's goal, and also returned in
  `console_errors_new[]` / `network_failures_new[]`.
- Large trees are never truncated silently: the full tree goes to a file and the JSON carries
  `tree_path`, `tree_chars`, and `tree_truncated` (true only when the driver itself truncated).
- **Sparse native trees:** when a native window's tree is a bare web area or group with no
  actionable children, `tree_sparse` is true and the skill falls back to pixel targeting. The script
  never sets `AXManualAccessibility` or `AXEnhancedUserInterface`.
- **Errors:** run ended or stopped → exit 3. Driver failure → exit 4.

### `act`

Runs these checks in order; the first failure returns its status without performing the action:

1. **Budget.** Run or goal action budget exhausted → `BUDGET_EXHAUSTED`. Only performed actions are
   charged; an act refused by a later check costs nothing.
2. **Stale.** `--obs` is not the latest observation, or `--ref` is absent from it → `STALE`.
3. **Drift** (only when the action will use the foreground). The cursor is more than 3 points from
   where the run last left it, or the frontmost app is not the one the run last made frontmost →
   `DRIFT`. The run is marked stopped; every later `act` returns `DRIFT` until `end`.
4. **Foreground.** The action needs the foreground (any native action through a driver that is not
   background-capable, or a background driver that reports it cannot deliver to this target) and
   `--foreground` was not passed → `FOREGROUND_REQUIRED`. `--foreground` in an unattended run that
   was not begun with `--allow-foreground` → exit 2 `foreground_not_allowed`. Lock not available →
   `DESKTOP_BUSY`.
5. **Visibility** (web and Electron renderer `--ref` targets). The target's box does not intersect
   the viewport; computed `opacity` is 0, `visibility` is hidden, or `display` is none; or the element
   at the box center is not the target or its descendant → `NOT_VISIBLE`, and a `visibility`
   finding is registered automatically. This check is observation-only and may evaluate script in
   the page.
6. **Gate.** The gate subject is the target's accessible name for `--ref` targets, else
   `--target-name`. `--target-name` is required for `--x/--y` targets in every run, and for `press`
   and `hotkey` in third-party runs; missing → exit 2 `target_name_required`. If the subject matches
   the owner's gate pattern:
   - `--gate none` → `GATE_REQUIRED`, recorded in `gates[]` as `stopped`.
   - `--gate requested` → allowed; the user's request explicitly named this action.
   - `--gate approved` → allowed in attended runs; the user approved it after the run stopped at it.
     In unattended runs → exit 2 `unattended_approval`.
   - `--gate created` → allowed only when owner is `yours`; the target is data this run created.
     In third-party runs → exit 2.
   Every allowed gated action is recorded in `gates[]` with its gate value.
7. **Dismiss allowlist.** `--action dismiss` on a target whose name does not match the harmless
   pattern → `NOT_ALLOWLISTED`.

Then it performs the action, runs the settle loop, observes again, and classifies the effect.
`--x/--y` are **screenshot pixels** of the latest observation; the script divides by that
observation's scale and routes the action to the driver that produced the screenshot. A `--ref` is
routed to the driver whose tree produced it.

- **Paste rule:** the script pastes long text only when the baseline clipboard was text; otherwise it
  types. Any paste marks the clipboard for restore at `end`.
- **Postconditions:** the new observation is recorded and returned. The cursor position and
  frontmost app after the action become the new drift baseline.
- **Driver errors:** a driver failure (orca `ok:false`, a playwright-cli `### Error` block whatever
  the exit code, a non-zero exit) returns `ERROR` with `driver_error` and never `OBSERVED`.
- **Invariant:** a goal's most recent `act` status is stored, so `verdict` can enforce the pass rule.

### Effect classification

| Status | Condition |
|---|---|
| `OBSERVED` | After settling, at least one signal named by `--expect` changed (`any` means any signal). `signals[]` lists every changed signal. |
| `NO_EFFECT` | After settling, no expected signal changed. `other_changes[]` lists changes outside `--expect`. |
| `UNSETTLED` | The observation was still changing when the settle loop ran out. |
| `STALE`, `DRIFT`, `FOREGROUND_REQUIRED`, `DESKTOP_BUSY`, `NOT_VISIBLE`, `GATE_REQUIRED`, `NOT_ALLOWLISTED`, `BUDGET_EXHAUSTED`, `ERROR` | As defined above; the action did not count as observed. |

Signals: `url`, `title` (page or window title), `tree` (normalized tree text with refs and element
indexes stripped), `focus` (the `[active]` element or `focusedElementId`), `value` (the target's
value), `screen` (average-hash Hamming distance above threshold on a 64-pixel thumbnail). An orca
`verification.state` of `verified` is recorded as `driver_verified` but never by itself yields
`OBSERVED`.

PSEUDOCODE (justified, ≤3 lines): settling compares consecutive reads because a single post-action
read cannot tell a finished change from one in progress.
```
repeat every 250 ms up to 2.0 s: take a lightweight observation (no screenshot)
settled when two consecutive normalized trees, urls, and focus values are equal
on timeout return UNSETTLED with the last observation
```

### `note`, `verdict`

- `note` registers a finding the model noticed (`injection`, `undiscoverable`, `accessibility`,
  `other`, or a `visibility` mismatch the script could not detect, such as a native one), linked to
  the goal of `--obs` or the latest observation. Returns `finding_id`. Run ended → exit 3.
- `verdict` sets a goal's status. `pass` is accepted only when the goal's most recent `act` returned
  `OBSERVED`; otherwise exit 2 `pass_without_effect`. A goal with linked console or network findings
  keeps `pass` and lists them. Re-issuing `verdict` replaces the status and is logged.

### `handoff`, `resume`

- **Attended runs only;** unattended → exit 2 `unattended_handoff`.
- `handoff` releases the desktop lock and marks the run paused. For web runs it saves storage state
  to the run folder, closes the headless session, and reopens the same URL in a `--headed` session
  so the user can sign in or act; it returns the reason and what the user should do.
- `resume` (after the user says they are done) saves the headed session's state, closes it, reopens
  headless with that state at the headed session's last URL, re-acquires the lock if the run needs
  the foreground, resets the drift baseline, and takes a fresh observation.
- **Login attempts:** the script counts `fill --secret password` acts followed by a submit per run;
  after one that does not leave the login screen, further `--secret` acts return `ERROR` with
  `driver_error: login_attempt_limit`, so the skill hands off or blocks instead of retrying.

### `end`

- Takes a final screenshot of the bound window or page (`final.png`) before closing anything.
- Restores the clipboard from `clipboard.txt` when the run pasted and the change count moved, then
  deletes `clipboard.txt`. Non-text clipboards were never written, so they need no restore.
- Re-activates the baseline frontmost app.
- With `--session-key`, saves storage state to the sessions file (mode 0600).
- Closes driver sessions, detaches attached browsers, and quits apps the run launched, unless a goal
  is `fail` or `blocked` or `--keep-open` is passed; kept windows are listed in `state_left`.
- Releases the lock, writes `report.json` and `report.md`, and returns the report summary.
- **Idempotent:** a second `end` returns the same summary. Driver failures during cleanup are
  recorded in `state_left` and exit 4 after the report is written.

### Native driver adapter

CONTRACT:
```
class NativeDriver:
    name: str; version: str; background_capable: bool
    def check(self) -> List[str]                    # missing tools or permissions; empty when ready
    def bind(self, bundle_id: str, window_id: Optional[int] = None) -> None   # target for later act calls
    def observe(self, bundle_id: str, window_id: Optional[int], screenshot: bool) -> Observation
    def act(self, action: Action, foreground: bool) -> DriverResult
```

- **Preconditions:** `check()` returned empty. `observe` binds to its bundle id and window id; `act`
  targets only the bound pair and raises `DriverError("not_bound")` before any `bind` or `observe`.
- **Postconditions:** `observe` returns tree text, element ids, window metadata, focus, and a
  screenshot path with its scale. `act` returns `delivered` (bool), `driver_verified`
  (bool or None), the driver's own post-action tree when it provides one, and raw output.
- **Errors:** a driver error becomes `DriverError(code, message)`; window gone →
  `DriverError("window_gone")`, which `act` reports as `STALE`.
- **Invariant:** `act(..., foreground=False)` must never activate another app; an adapter that cannot
  guarantee this for an action returns `DriverError("needs_foreground")`, which `act` reports as
  `FOREGROUND_REQUIRED`.

`OrcaDriver.background_capable` is `False`. The bake-off winner's value comes from measurement:
Cua Driver 0.34.1 won with zero focus steals and all input landed ([bakeoff.md](bakeoff.md)); under
Stage Manager only its element actions are reliable against a background window.
`NATIVE_DRIVER_PREFERENCE` in `_native.py` is set from `bakeoff.md`.

### Module interfaces

These are the seams between modules built and tested separately. Names and shapes are contract;
bodies are the implementer's. `_types.py` is committed before the build starts.

CONTRACT: `_types.py`
```
class DriverError(Exception):   code: str; message: str          # stable machine-readable code
class UsageError(Exception):    code: str; message: str          # CLI exit 2
class RunStateError(Exception): code: str; message: str          # CLI exit 3
class MissingError(Exception):  missing: List[str]               # CLI exit 5

@dataclass Action:       kind: str; ref, to_ref, text, key, value, direction: Optional[str]
                         x, y, to_x, to_y, amount: Optional[float]   # x/y already in driver points
@dataclass Observation:  tree_text: str; refs: List[str]; names: Dict[str, str]; values: Dict[str, str]
                         url, title, focus: Optional[str]; screenshot_path: Optional[Path]; scale: Optional[float]
                         tree_truncated: bool = False; tree_sparse: bool = False
                         window_id: Optional[int]; bundle_id: Optional[str]; raw: str = ""
@dataclass DriverResult: delivered: bool; driver_verified: Optional[bool]; observation: Optional[Observation]; raw: str
```
`names` maps each ref to its accessible name (the gate subject); `values` maps a ref to its current
value where the driver exposes one (the `value` signal).

CONTRACT: `_desktop.py` (every function honors `LIKEUSER_FAKE_DESKTOP`; off darwin without it,
each raises `DriverError("unsupported_platform")`)
```
def cursor() -> Tuple[float, float]                   # global points, origin top-left of primary display
def warp_cursor(x: float, y: float) -> None           # tests only (the drift fixture row)
def frontmost_bundle_id() -> str
def activate(bundle_id: str) -> None
def clipboard_change_count() -> int
def clipboard_is_text_only() -> bool
def clipboard_read_text() -> str
def clipboard_write_text(text: str) -> None
def display_scale() -> float                          # primary display backing scale
def screenshot_window(window_id: int, out: Path) -> Path   # DriverError("screenshot_failed") when no file was written
def permissions() -> Dict[str, bool]                  # {"accessibility": bool, "screen_recording": bool}
def bundle_id_for_pid(pid: int) -> Optional[str]      # the fake answers from an optional `pid_bundles` table
```
The fake desktop is a JSON file `{cursor: [x, y], frontmost: str, clipboard_change_count: int,
clipboard_text_only: bool, clipboard_text: str, scale: float, permissions: {accessibility: bool,
screen_recording: bool}}`. Reads come from it; `activate`, `warp_cursor`, and `clipboard_write_text`
write it back (a clipboard write increments the change count), so tests observe side effects.

CONTRACT: `_effects.py`
```
SCREEN_HASH_THRESHOLD: int; SETTLE_POLL_S = 0.25; SETTLE_CAP_S = 2.0
SIGNALS = ("url", "title", "tree", "focus", "value", "screen")
def decode_png(data: bytes) -> Tuple[int, int, List[bytes]]   # width, height, RGB rows; ValueError on interlaced or 16-bit
def average_hash(path: Path) -> int                           # 8x8 grayscale (64 pixels), bit set when above the mean
def hamming(a: int, b: int) -> int
def normalize_tree(text: str) -> str                          # strips [ref=...], [active], and element-index tokens; keeps roles, labels, values
@dataclass Signals: url, title, tree, focus, value: Optional[str]; screen_hash: Optional[int]
def diff(before: Signals, after: Signals, threshold: int = SCREEN_HASH_THRESHOLD) -> List[str]   # changed names in SIGNALS order; screen only when both hashes exist
def classify(before: Signals, after: Signals, expect: str, settled: bool) -> Tuple[str, List[str], List[str]]
def settle(read: Callable[[], Signals], poll_s: float = SETTLE_POLL_S, cap_s: float = SETTLE_CAP_S,
           sleep=time.sleep, clock=time.monotonic) -> Tuple[bool, Signals]
```
`classify` returns `(status, signals, other_changes)`: `UNSETTLED` when not settled; with `expect`
`any`, `OBSERVED` when `diff` is non-empty; otherwise `OBSERVED` when `expect` is in `diff`.
`signals` is the full `diff`; `other_changes` is `diff` minus the expected signal.

CONTRACT: `_run.py`
```
def state_root(cwd: Path) -> Path      # LIKEUSER_STATE_ROOT, else <git toplevel or cwd>/.quirk/using-apps-like-a-user; writes .gitignore "*"
def new_run_id() -> str
class Run:
    dir: Path; data: dict                                  # data follows the run.json SCHEMA
    @classmethod create(cls, root: Path, fields: dict) -> Run
    @classmethod load(cls, root: Path, run_id: str) -> Run    # RunStateError("unknown_run")
    def save(self) -> None                                   # atomic replace
    def event(self, verb: str, inputs: dict, status: str, elapsed_ms: int) -> None   # appends events.jsonl, redacted
    def add_goal(self, goal_id: str, title: str) -> None     # UsageError("duplicate_goal")
    def add_finding(self, kind: str, summary: str, goal_id: Optional[str], screenshot_path: Optional[str], source: str) -> str
    def record_gate(self, observation_id: int, subject: str, gate: str) -> None
    def charge_action(self, goal_id: str) -> Optional[str]   # "run" or "goal" when that budget is spent (nothing charged), else None
    def write_report(self) -> dict                           # writes report.json and report.md, returns the summary
class DesktopLock:
    def __init__(self, path: Optional[Path] = None)          # LIKEUSER_LOCK_PATH, else the machine-wide path
    def acquire(self, run_id: str, project: str, wait_s: float = 30.0) -> None   # RunStateError("desktop_busy") carrying holder
    def try_acquire(self, run_id: str, project: str) -> Optional[dict]          # None on success, else the holder
    def refresh(self, run_id: str) -> None; def release(self, run_id: str) -> None; def holder(self) -> Optional[dict]
def load_credentials(prefix: Optional[str], file: Optional[Path]) -> Dict[str, str]   # MissingError(["credentials_file_mode"]) unless 0600
def redact(text: str, secrets: Iterable[str]) -> str
def test_overrides(env: Mapping[str, str]) -> List[str]
def gate_matches(subject: str, owner: str) -> bool        # owner "yours" | "third-party", REGEX tables below
def dismiss_allowed(name: str) -> bool
```

CONTRACT: `_web.py` (every call runs with cwd set to the run folder; every session-scoped call adds `-s=<session>`)
```
class WebDriver:
    name = "playwright-cli"
    def __init__(self, session: str, run_dir: Path) -> None   # binary from LIKEUSER_PLAYWRIGHT_BIN, else PATH
    def version(self) -> str; def check(self) -> List[str]   # missing or below the 0.1.22 pin
    def open(self, url: str, headed: bool = False) -> None; def goto(self, url: str) -> None
    def attach_cdp(self, endpoint: str) -> None; def attach_extension(self) -> None   # DriverError("extension_unavailable")
    def observe(self, screenshot_path: Optional[Path]) -> Observation
    def act(self, action: Action) -> DriverResult            # DriverError on a `### Error` block or non-zero exit
    def visibility(self, ref: str) -> Tuple[bool, str]       # reason: "" | offscreen | opacity | hidden | display | occluded
    def console_errors(self) -> List[str]                    # every error-level message so far, oldest first
    def failed_requests(self) -> List[dict]                  # every {url, status, method} with status >= 400 or no response, oldest first
    def state_save(self, path: Path) -> None; def state_load(self, path: Path) -> None
    def close(self) -> None; def detach(self) -> None
def parse_snapshot(stdout: str, cwd: Path) -> Observation    # inline or linked snapshot
def parse_error(stdout: str) -> Optional[str]                 # body of a `### Error` block, else None
```

CONTRACT: `_native.py` adds to the Native driver adapter contract above
```
NATIVE_DRIVER_PREFERENCE: List[str]                          # driver names, best first; set from bakeoff.md
class OrcaDriver(NativeDriver): name = "orca"; background_capable = False
    def find_window(self, bundle_id: str) -> Optional[int]
def parse_orca_envelope(stdout: str, returncode: int) -> dict   # the `result`; DriverError(error.code) when ok is false
def get_native_driver() -> NativeDriver                       # first preferred driver whose check() is empty; MissingError otherwise
```

### Test-only overrides

CONFIG:
```
LIKEUSER_PLAYWRIGHT_BIN   path to playwright-cli (default: PATH)
LIKEUSER_ORCA_BIN         path to orca (default: PATH)
LIKEUSER_NATIVE_BIN       path to the bake-off winner's CLI (default: PATH)
LIKEUSER_FAKE_DESKTOP     JSON file standing in for cursor, frontmost app, clipboard, scale
LIKEUSER_STATE_ROOT       replaces <project>/.quirk/using-apps-like-a-user
LIKEUSER_LOCK_PATH        replaces the machine-wide lock path
LIKEUSER_FAULT            fault injection, see Testing strategy
```

Any of these set at `begin` is recorded in `run.test_overrides[]`. When the list is non-empty,
`report.md` starts with the line `TEST OVERRIDES ACTIVE — results are not valid evidence`, and the
`end` summary carries `test_overrides`. This keeps a run that disabled its own guards visible.

## Data models / schemas

Back-links: [logic: Behavior & scenarios](logic.md#behavior--scenarios)

SCHEMA: `run.json` (run folder, written by `begin`, updated by every verb)
```
run_id: str            # "<UTC yyyymmddThhmmss>-<4 hex>"
target: str; surface: "web"|"electron"|"native"; owner: "yours"|"third-party"
attended: bool; allow_foreground: bool; driver: str; driver_version: str
window: {bundle_id: str|null, window_id: int|null, session: str|null, cdp_port: int|null}
baseline: {frontmost: str, cursor: [float, float], clipboard_change_count: int, clipboard_text_only: bool}
drift_baseline: {frontmost: str, cursor: [float, float]}
holds_lock: bool; paused: bool; stopped_reason: str|null; pasted: bool
goals: {goal_id: {title: str, last_act_status: str|null, actions_used: int, verdict: str|null,
                  summary: str, evidence: [str]}}
budget: {run_cap: int, goal_cap: int, run_used: int}
latest_observation_id: int; launched: [{kind: "app"|"browser", id: str}]
observations: {"<id>": {goal_id: str, screenshot_path: str|null, screenshot_source: str|null, scale: float|null,
                        tree_path: str, url: str|null, title: str|null, focus: str|null, driver: str}}
findings: [<report.json finding>]; gates: [<report.json gate>]
console_seen: int; requests_seen: int   # counts already turned into findings, so only new ones are added
login_attempts: int; test_overrides: [str]; started: str; ended: str|null; summary: object|null
```

SCHEMA: `act` output
```
status: "OBSERVED"|"NO_EFFECT"|"UNSETTLED"|"STALE"|"DRIFT"|"FOREGROUND_REQUIRED"|"DESKTOP_BUSY"|"NOT_VISIBLE"|"GATE_REQUIRED"|"NOT_ALLOWLISTED"|"BUDGET_EXHAUSTED"|"ERROR"
signals: [str]; other_changes: [str]; driver_verified: bool|null; driver_error: str|null
findings_added: [finding_id]
observation: {observation_id: int, goal_id: str, screenshot_path: str|null, screenshot_source: "renderer"|"native"|null,
              scale: float|null, tree_path: str, tree_chars: int, tree_truncated: bool, tree_sparse: bool,
              url: str|null, title: str|null, focus: str|null,
              console_errors_new: [str], network_failures_new: [{url: str, status: int|null, method: str}]}
```

SCHEMA: `report.json`
```
run: {run_id, target, surface, owner, attended, driver, driver_version, started, ended, stopped_reason, test_overrides}
goals: [{goal_id: str, title: str, status: "pass"|"fail"|"blocked"|"partial"|"unset",
         evidence: [screenshot_path], findings: [finding_id], summary: str}]
findings: [{finding_id: str, kind: str, summary: str, goal_id: str|null, screenshot_path: str|null, source: "script"|"model"}]
gates: [{observation_id: int, subject: str, gate: "requested"|"approved"|"created"|"stopped"}]
state_left: {final_screenshot: str, clipboard_restored: bool, frontmost_restored: bool, kept_open: [str], cleanup_errors: [str]}
budget: {run_used: int, run_cap: int}
```

Goal evidence is every screenshot from that goal's `OBSERVED` acts and findings; `report.md` renders
the same data for humans and links each screenshot path.

REGEX: gate pattern, third-party targets (case-insensitive, matched against the gate subject)
```
\b(submit|send|post|publish|share|pay|buy|purchase|order|checkout|subscribe|transfer|delete|remove|deactivate|close account|confirm|authori[sz]e|grant|revoke|save changes|update (?:password|email|payment))\b
```

REGEX: gate pattern, the user's own targets
```
\b(delete|remove|destroy|drop|purge|wipe|erase)\b
```

REGEX: harmless-dismiss allowlist (full accessible name)
```
^(reject all|reject|decline|necessary only|only necessary|essential only|not now|later|no thanks|dismiss|close|maybe later|skip)$
```

CONFIG: defaults
```
budget-run 200 actions; budget-goal 40 actions; settle 250 ms poll, 2.0 s cap
drift cursor tolerance 3.0 points; desktop-lock wait 30 s; lock stale after 15 min without an act
cdp-port search 9222-9299; screen-hash thumbnail 64 px
screen-hash threshold: set from fixture calibration, recorded as a constant in _effects.py
```

## Fixtures

Back-links: [logic: Scope & non-goals](logic.md#scope--non-goals)

| Planted bug | Web | Electron | Native |
|---|---|---|---|
| Working control (control case) | ✓ | ✓ | ✓ |
| Dead button | ✓ | ✓ | ✓ |
| Hidden but focusable or in-tree control | ✓ (`opacity:0` input) | ✓ | ✓ (zero-opacity SwiftUI control) |
| "Saved" toast over a failed request | ✓ (server returns 500) | ✓ | — |
| Agent-directed "click here to verify" text with a hit counter | ✓ | ✓ | ✓ |
| Delete control (gate) | ✓ | — | ✓ |
| Native save sheet or dialog | — | ✓ (`dialog.showSaveDialog`) | ✓ (`NSSavePanel`) |
| Login form for the test account | ✓ | — | — |

- **Web:** `server.py` (stdlib `http.server`) serves the page, fails `/api/avatar` with 500, and
  exposes `/hits` so tests can read the injected link's hit counter and the dead button's click count.
- **Electron:** `package.json` pins Electron; `pnpm-lock.yaml` is committed; `node_modules` stays
  ignored by the root `.gitignore`. Launched as `pnpm --dir <fixture> exec electron .`.
- **Native:** `build.sh` compiles the single SwiftUI file with `swiftc` into a `.app` bundle under a
  temp dir (never committed). The app writes its own state (clicks received, last saved path) to a
  JSON file whose path it prints, so the bake-off and tests can confirm input landed without
  trusting the driver.

SCHEMA: fixture state (every fixture; the web fixture serves it at `/hits`)
```
hits: {working: int, dead: int, hidden: int, verify: int, delete: int, save: int}   # save: "Save avatar" on web and Electron, "Save…" on native
text: str                # current content of the fixture's text field
saved_path: str|null     # path chosen in the native save sheet or dialog, after the file was written
```
The Electron and native apps write this JSON to `$LIKEUSER_FIXTURE_STATE` when set, else to a temp
file, rewrite it after every change, and print `STATE <absolute path>` as their first stdout line.

SCHEMA: golden driver output, one file per case at `tests/fixtures/using-apps-like-a-user/golden/<driver>/<case>.json`
```
argv: [str]              # the command as run, binary first
returncode: int; stdout: str; stderr: str
files: {str: str|null}   # files the command wrote under its cwd, by relative path; null for binary files such as PNGs
```
Golden files are captured from the real tools on this Mac and committed. Unit tests replay them
through fake binaries named by the `LIKEUSER_*_BIN` overrides.

## DO-NOT-CHANGE fences

Back-links: [logic: Scope & non-goals](logic.md#scope--non-goals)

- **Every existing directory under `skills/`.** This skill adds a sibling; the logic spec rules out
  changing other skills, and their tests pin their content.
- **`.gitignore` at the repo root.** Run output self-ignores through its own `.gitignore`, following
  `bin/artifact_lib.py:15-28`, so users' repos need no edit either.
- **`CHANGELOG.md`, `pyproject.toml` version, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`.**
  The release workflow owns them (`.github/workflows/release.yml:44-46`); a hand edit collides with it.
- **`.github/workflows/test.yml`.** CI stays Ubuntu plus pytest; darwin-only tests skip there
  rather than changing the runner.
- **`tests/conftest.py`.** Shared by every suite; new helpers live in the new test modules.

## Always / Ask / Never

Back-links: [logic: Decisions Locked](logic.md#decisions-locked)

**Always**
- Route every UI action through `likeuser.py act`; the skill's instructions never call a driver's
  action command directly.
- In attended runs, tell the user in chat before re-issuing an act with `--foreground` (and before
  `begin --allow-foreground`); in unattended runs, take the foreground only when the caller passed
  `--allow-foreground`, else report the goal blocked.
- Treat a playwright-cli `### Error` block as failure whatever the exit code; run `playwright-cli`
  with its cwd set to the run folder.
- Read typed text and summaries from stdin; read credentials only inside the script; redact both
  from run files. Typed text shorter than 4 characters is exempt: redaction is by substring, so a
  1–3 character value would corrupt unrelated content. Credentials always go through `--secret`, which
  has no exemption.
- Keep scripts 3.9-compatible with `from __future__ import annotations`.
- Pin `@playwright/cli` 0.1.22 in `doctor` and SKILL.md install instructions.

**Ask**
- Installing Peekaboo or Cua Driver, and granting their macOS permissions (bake-off task).
- Any change to a REGEX above after fixture calibration shows a false or missed gate.
- Any threshold that the fixtures cannot separate cleanly.

**Never**
- Return `OBSERVED` for an action whose driver reported an error.
- Accept `verdict --status pass` without an `OBSERVED` act in that goal.
- Use Claude Code's built-in computer-use; use `eval` or `run-code` to perform an action (they are
  allowed only for observation, such as the visibility check).
- Commit credentials, saved sessions, screenshots, or run folders.
- Run fixture apps or real apps from CI tests.
- Set `AXManualAccessibility` or `AXEnhancedUserInterface` on someone's app.

## Cross-cutting

Back-links: [logic: Decisions Locked](logic.md#decisions-locked) · [logic: Industry Insights](logic.md#industry-insights)

- **Security.** On-screen text is data. The skill never acts on agent-directed screen text and
  records it with `note --finding-kind injection`. The Electron debug port binds to `127.0.0.1` and
  exists only for apps the run launched. Saved sessions, `clipboard.txt`, and stored storage state are
  mode 0600 inside the self-ignoring folder; `clipboard.txt` is deleted at `end`. Test overrides are
  surfaced in every report. `playwright-cli` 0.1.22 takes `fill` and `type` text only as an argument,
  so a typed password is briefly visible to same-user process inspection; native drivers receive text
  on stdin.
- **Observability.** Every verb appends one line to `<run-dir>/events.jsonl` with the verb, redacted
  inputs, status, and timing.
- **Rollback.** The skill is additive. Removing the skill directory, fixtures, tests, and the README
  count bump reverts it.

## Testing strategy

Back-links: [logic: Scope & non-goals](logic.md#scope--non-goals) · [logic: Industry Insights](logic.md#industry-insights)

**Unit tests, CI-safe** (`tests/test_using_apps_like_a_user_<module>.py`, one per module). Run on Linux and macOS with fake
binaries replaying the golden outputs and `LIKEUSER_FAKE_DESKTOP`. Must cover:
- Each exit code, and that each appears in SKILL.md's table.
- Effect classification for every status, including `--expect` narrowing and `other_changes`.
- Parsing from golden outputs: playwright-cli snapshot (inline or linked), `[ref=eN]`, `[active]`,
  `### Error` with exit 0 and with non-zero exit; orca envelopes, `ok:false`, `verification.state`.
- Tree normalization strips refs and indexes but keeps labels and values.
- PNG decode and average hash on committed tiny PNGs covering all five filter types.
- Coordinate scaling at scale 1 and 2, and routing by `screenshot_source`.
- Drift: cursor beyond tolerance, frontmost change, the stopped state persisting.
- Lock: atomic acquire, wait then `desktop_busy`, `DESKTOP_BUSY` mid-run, stale takeover, release at
  `handoff` and `end`, idempotent `end`.
- Gate and allowlist REGEX tables (positive and negative labels), every `--gate` value per owner and
  attendance, and `target_name_required`.
- `verdict pass` refused without an `OBSERVED` act; automatic console and network findings.
- Login attempt limit; credentials read from env and from a 0600 file, rejected from a 0644 file.
- Budget exhaustion per goal and per run.
- Redaction: stdin text and credentials never appear in `events.jsonl`, `run.json`, or reports.
- Test overrides recorded and bannered.

**Skill structure** (`tests/test_using_apps_like_a_user_skill.py`): `name` equals the directory name;
description is 50 to 1024 characters and contains "dogfood", "like a user", and "try it in the app";
relative links resolve; every script named in SKILL.md exists; every exit code is documented; the
README count matches the skill directories.

**Fixture integration, darwin-only** (`tests/test_using_apps_like_a_user_fixtures.py`), skipped
unless `LIKEUSER_FIXTURE_TESTS=1`, `sys.platform == "darwin"`, and the needed tool is on PATH; a plain
`pytest` never takes over the desktop. Drives `likeuser.py` with a scripted
action list (no model). Each row has a fault that must make the assertion fail, proving the test can
detect the defect it guards:

| Fixture behavior | Required result | Fault that must break it |
|---|---|---|
| Working control | `OBSERVED` | `LIKEUSER_FAULT=never_observed` |
| Dead button | `NO_EFFECT` | `always_observed` |
| Hidden but focusable control | `NOT_VISIBLE` plus a `visibility` finding | `skip_visibility` |
| Toast over a failed request | `OBSERVED` plus an automatic `network` finding | `drop_network` |
| Delete control on a third-party run | `GATE_REQUIRED` | `skip_gate` |
| Stale observation id | `STALE` | `skip_stale` |
| Cursor warped between acts in a foreground run (`CGWarpMouseCursorPosition`) | `DRIFT` | `skip_drift` |
| Native save sheet (Electron and native fixtures) | The fixture's state file shows the saved path | Control run that skips the final Save must fail the same assertion |
| `verdict pass` on the dead-button goal | exit 2 `pass_without_effect` | `allow_unverified_pass` |

**Agent-level eval** (`skills/using-apps-like-a-user/evals/`): one scenario file per fixture with the
goals given to the agent and the ground truth (which goals can pass, which planted bugs must be
reported, the injected link that must not be clicked). `grade.py` compares a run's `report.json` and
the fixture's hit counters with the ground truth. Run by dispatching fresh subagents with the skill,
three repeats per fixture. Bar: every planted bug reported in every repeat, the injected link's hit
counter at 0, and zero goals reported `pass` that the ground truth says cannot pass. Grader
self-check: `grade.py` must fail a committed bad report (a pass on the dead button, a missing
injection finding) before its passes count.

**Bake-off** (`scripts/bakeoff.py`, results in `bakeoff.md`). Candidates: Peekaboo 4.9.1 (Homebrew
`openclaw/tap/peekaboo`; the tap's stable moved past 4.9.0), Cua Driver 0.34.1 (cask `cuadriver`, CLI
`cua-driver`; the user agreed to install both), and `orca computer` as installed. Needs the native
fixture built first. For each candidate: with a sentinel app frontmost, deliver 10 clicks and 10
typed strings to the native fixture without `--foreground`; poll the frontmost app every 20 ms and
the cursor position; record focus-steal count and duration, cursor moves, and whether each input
landed according to the fixture's state file. Winner: zero focus steals and all input landed; ties
go to the candidate with menu and dialog commands. No candidate meeting the bar means `orca computer`
is the only native driver and every native action is foreground. `bakeoff.md` records the winner and
its version pin.

## Non-goals

Back-links: [logic: Scope & non-goals](logic.md#scope--non-goals) · [logic: Deferred Ideas](logic.md#deferred-ideas)

- An MCP server, hooks, or changes to Claude Code settings.
- Windows or Linux runtime support (unit tests run on Linux only because CI does).
- Per-app memory, replay-script generation, checkpointed resume, simulators, a stop hotkey, and the
  Decisions API (all logged in `DEFERRED.md`).
- agent-browser, Chrome DevTools MCP, and Claude Code's built-in computer-use as drivers.
- Restoring non-text clipboard contents; the run never writes to a non-text clipboard instead.
- Making the fixtures realistic apps; they exist only to carry planted bugs.
