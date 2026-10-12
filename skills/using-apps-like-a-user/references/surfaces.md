# Surfaces

Per-surface procedure and driver gotchas for [SKILL.md](../SKILL.md). Each section opens with what
to do; the gotchas follow. Every action still goes through `likeuser.py act`.

## Web

Use `--surface web`. The run gets its own headless `playwright-cli` session named after the run id,
so two web runs proceed in parallel and the user's browser is untouched.

- **Errors are the script's job.** `playwright-cli` can print a `### Error` block and still exit 0.
  The script treats that as failure and returns `ERROR`; you never parse driver output.
- **A click that succeeds proves nothing about visibility.** Playwright clicks an `opacity:0` input.
  The script checks the target is on screen, not transparent, not hidden, and not covered before it
  acts. If it returns `NOT_VISIBLE`, the control is a finding, not a path forward.
- **A "Ref not found" after Back or Forward** can be a cache restore. `STALE` is the answer:
  `observe` again.
- **Console errors and failed requests arrive on their own.** Every `observe` and `act` returns
  `console_errors_new` and `network_failures_new` and registers them as findings on the goal. A
  success toast over an HTTP 500 is a `pass` plus a `network` finding. Do not demote the pass and do
  not hide the finding.
- **The real Chrome** (`--real-chrome`) only when the user asks for their signed-in browser. It
  needs the Playwright extension; `begin` exits 5 if it is missing. Your actions then run in the
  user's own tabs, so say so before `begin` and treat every click as touching their real account.
- **Reusing a session.** `--session-key <name>` loads saved storage state when it exists and saves
  it at `end`. The script does not check it is still valid. An expired session is a login screen.

## Electron

Use `--surface electron --launch "<command>"` for a dev build the run starts. The script appends
`--remote-debugging-port=<port>` to the command, bound to `127.0.0.1` (the first free port in
9222-9299, or `--cdp-port`), and attaches `playwright-cli` to it.

- **The launch command must pass the extra argument to Electron.** `pnpm exec electron .` does. A
  wrapper script that swallows its arguments does not, and `begin` exits 4 when the attach fails.
- **Already running or packaged apps are native.** Use `--surface native` for them. Do not quit and
  relaunch the user's running app to open a debug port.
- **Two trees in one run.** The renderer's refs look like `e12`. Refs from the native driver carry
  an `n:` prefix (`n:7`). Use a ref with the driver that produced it; the script routes by prefix.
- **Which screenshot you are looking at.** `observation.screenshot_source` is `renderer` or
  `native`. It is `native` whenever a native sheet or dialog is open, and then both trees are
  returned. `--x --y` are pixels of the latest screenshot and go to the driver that took it.
- **Native save sheet.** After the renderer click that opens it, `observe`. The sheet's name field
  and Save button appear in the native tree. Type the file name with `type`, click Save, then
  `observe` and confirm the app shows the file. Sheet buttons are disabled while the app is not
  frontmost, so expect `FOREGROUND_REQUIRED`: say so in chat and re-issue with `--foreground`.
- **Gates on a sheet.** Save is gated in a third-party run (`save changes`) and not in your own.
  A Save from a sheet that was not requested stops at `GATE_REQUIRED` like any other.

## Native

Use `--surface native` with the app's bundle id (`com.apple.TextEdit`) or name. The run binds to
that app's frontmost window.

- **Cua Driver is preferred.** Element actions (`click` with a `--ref`, `type`, `press`) are
  delivered in the background through the accessibility API, so the user's frontmost app and cursor
  do not move. The bake-off that picked it is in
  `docs/quirk/specs/2026-10-11-using-apps-like-a-user/bakeoff.md`.
- **Stage Manager changes what is reliable.** A window that is not frontmost shows up as a small
  thumbnail. Element actions still work in the background. Coordinate actions (`--x --y`), drags,
  and scrolls aimed at a target can post without error and not land, so they need the foreground:
  expect `FOREGROUND_REQUIRED`, announce it, and re-issue with `--foreground`.
- **Dialogs, sheets, and menus** go through the same native loop. Sheets and file pickers are
  foreground work: the buttons stay disabled until the owning app is frontmost. While a sheet is
  open, `press`, `hotkey`, and `type` without `--ref` go to the frontmost sheet instead of the main
  window, and need `--foreground` like any sheet action.
  - Check sheet actions with `--expect tree`; the `screen` signal is too coarse to see a sheet
    change. A `fill` into a sheet's field changes only its value, so use `--expect value` there.
  - A save sheet's name field takes a file name only. A path typed there saves into the sheet's
    current folder under a name with ":" where the "/" were.
  - To save into a chosen folder, `press --key cmd+shift+g --foreground --expect tree` opens Go to
    Folder (`hotkey` with the same chord works too). `fill` its path field (the
    `PathTextField` row of the native tree) with the folder path, then `press --key Return
    --foreground --expect tree`. Observe again: the sheet's "Where:" row in the native tree must
    name the folder (it shows the folder's name, not the path) before you click Save.
  - A save goal passes only when the destination folder was shown in the sheet before Save and the
    Save act was `OBSERVED`. Otherwise the goal is `partial`, and the summary says what is
    unverified.
- **macOS prompts are the user's call.** A privacy or consent prompt ("wants to access", "bypass the
  system private window picker") is not part of the app under test. Do not click Allow. Tell the
  user and leave it.
- **Sparse trees.** When `tree_sparse` is true (a web view or canvas with no actionable children),
  the tree cannot see the target. Pick the target from the screenshot and use `--x --y` with
  `--target-name`. Add a `note --finding-kind accessibility` when a real control a user can see has
  no tree entry.
- **Never set `AXManualAccessibility` or `AXEnhancedUserInterface`** on someone's app to get a fuller
  tree. The setting outlives the run and has caused keyboard side effects.
- **`orca computer` fallback.** Every action is a foreground action, so `begin` needs
  `--allow-foreground` and takes the lock up front. Its element click raises the target app, and its
  tree has no frame geometry, so click a text field by pixel to focus it before typing. In an
  unattended run without `--allow-foreground`, the native goals are `blocked`.

## Reading the observation

- `tree_path` holds the full tree. `tree_truncated` is true only when the driver itself cut it off.
  Truncation is not absence: a missing control in a truncated tree has not been shown to be missing.
- `tree_sparse` true means fall back to pixels, as above.
- `screenshot_path` is the evidence. Cite it in the goal summary.
- A 64-pixel thumbnail hash backs the `screen` signal. It catches changes the tree cannot name, such
  as a canvas redraw, and it can also move on an animation. That is why `--expect` should name the
  signal you mean. It misses small changes such as a label or a toast, so `NO_EFFECT` on `--expect
  screen` is weak evidence: compare the before and after screenshots yourself before reporting a
  dead control.
