# Native-driver bake-off

Date: 2026-10-12  
Machine: macOS 26.6.2 (build 25G83) on MacBookPro18,2, Stage Manager on  
Versions: Peekaboo 4.9.1, Cua Driver 0.34.1 (`cua-driver`, app `/Applications/CuaDriver.app`), `orca computer` 1.4.216-rc.0.zy03

**Winner:** cua

background_capable: true  
Version pin: `cua-driver 0.34.1` (Homebrew cask `cuadriver`)  
`NATIVE_DRIVER_PREFERENCE` for `_native.py`: `["cua", "orca"]`  
Runs: 2 full passes, both winners cua, so no third pass. Rule applied: zero focus steals and every input landed; only Cua Driver met it.

Harness: `python3 skills/using-apps-like-a-user/scripts/bakeoff.py --runs 2`, 10 clicks on "Working button" and 10 distinct strings into "Notes", a sentinel app frontmost throughout, frontmost app and cursor polled about every 20 ms. Landing is read from the fixture's state file, never from the driver's own report.

## What decided it

- **Cua Driver** delivered 10/10 clicks and 10/10 strings with zero steals and zero cursor moves. Element clicks use `AXPress`, typing uses `type_text` against an element token. Every call exited 0.
- **Peekaboo** clicked 10/10 in the background with no steal and no cursor move, but 0/10 strings landed. Its background `type` refused every call with `INVALID_INPUT: The focused element frame is outside the exact target window bounds`. The cause is Stage Manager: with the sentinel in front, the fixture window is a 126x123 pt thumbnail in the strip while its AX frames stay at the real 900x450 geometry, so Peekaboo's frame check fails. With the fixture frontmost, the same `type` call landed the text but reported `INTERACTION_FAILED` (unverifiable). Peekaboo also marks a snapshot stale after any mutation (`SNAPSHOT_STALE`), so every action needs a fresh `see`.
- **orca** landed everything but its element click raises the target app, so it stole focus once and never gave it back (the duration is open-ended: it runs to the end of the measurement). Its element click on a text field only performs `AXConfirm`; focusing the field needed a coordinate click at the field center, taken from System Events because orca's tree has no frames.

**The winner depends on Stage Manager being on.** Peekaboo ships menu and dialog commands where Cua has only a menu command, so a re-run with Stage Manager off could let it qualify and win the tie-break. The harness is re-runnable for that: `python3 skills/using-apps-like-a-user/scripts/bakeoff.py --runs 2 --candidates peekaboo,cua --report <path>`. An earlier pass of this harness (orca focused the notes field with an element click) scored orca 0/10 strings; the harness was fixed and both recorded runs below use the final version.

## Environment findings that affect adapters

- **Stage Manager scales background windows.** `list_windows` and screenshots of a non-frontmost window report the thumbnail frame (126x123 pt, a 252x246 px capture) instead of 900x450. A Cua coordinate click against that capture posts without error and does not land; `scroll` with an element token or x,y is refused in the background (`lies outside window ... 126x123 pt frame`); `drag` maps into the thumbnail. Coordinate actions are reliable only while the target window is frontmost at its true size.
- **Cua Tahoe direct-capture consent.** The first screenshot call made macOS show "CuaDriver is requesting to bypass the system private window picker" while `cua-driver permissions status --json` still reported both permissions granted (`direct_capture_status: not_checked`). Screenshots succeeded anyway. The prompt was left unanswered for the user to decide.

## Cua Driver command forms that worked

Every call is `cua-driver call <tool> '<json>'` against the fixture's `$P` (pid) and `$W` (window id). Every call carries the same `"session":"<label>"`: each CLI invocation is its own transport session, so without a label an element token comes back `stale_element_token ... pid has no current snapshot`. Replies are JSON on stdout. A refusal exits 1 with a JSON body (`effect: refused`, `code`) or, for AX failures, a plain-text line such as `AX action failed: ...`. `effect` is `confirmed` or `unverifiable` on success, and `unverifiable` still exits 0, so the guard's own observation diff is the proof.

| Verb | Command |
|---|---|
| check | `cua-driver permissions status --json` (read `accessibility`, `screen_recording`); `cua-driver --version`; `cua-driver status` (daemon) |
| find window | `cua-driver call list_windows '{"pid":P,"session":S}'` returns `windows[].window_id`, `bounds`, `title` |
| observe, tree | `cua-driver call get_window_state '{"pid":P,"window_id":W,"include_screenshot":false,"session":S}'` returns `elements[]` (`element_token`, `element_index`, `role`, `label`, `value`, `actions`, `frame`), `tree_markdown`, `snapshot_id`. The walk continues past the window into the app's full menu bar (about 100 more rows) |
| observe, tree plus screenshot | the same call with `"screenshot_out_file":"<absolute path>"`; relative paths fail (`Read-only file system`) because the daemon writes the file. Returns `screenshot_file_path`, `screenshot_width`, `screenshot_height`, `screenshot_scale`, `capture_id`, `window_bounds`. The PNG is downscaled (1568 px wide for the 900 pt window, so 1.742 px/pt); `"include_accessibility_tree":false` gives the screenshot alone |
| element click | `cua-driver call click '{"pid":P,"window_id":W,"element_token":"s00000011:1","session":S}'` (token `s<snapshot>:<index>`; the next snapshot of that window invalidates it) |
| coordinate click | `cua-driver call click '{"pid":P,"window_id":W,"x":505,"y":270,"capture_id":"<id>","session":S}'` with x,y in window-local screenshot pixels. A `capture_id` is consumed by its first use (`capture_not_found` after); omit it to reuse coordinates |
| type | `cua-driver call type_text '{"pid":P,"window_id":W,"element_token":"<Notes token>","text":"hello","session":S}'` needs no prior focus click (`AXPress` on a text field fails with -25206) |
| press | `cua-driver call press_key '{"pid":P,"window_id":W,"element_token":"<token>","key":"return","session":S}'`; optional `"modifiers":["cmd"]` |
| hotkey | `cua-driver call hotkey '{"pid":P,"window_id":W,"element_token":"<token>","keys":["cmd","a"],"session":S}'`; reports `effect: unverifiable` with `escalation.target: foreground` |
| scroll | `cua-driver call scroll '{"pid":P,"window_id":W,"direction":"down","amount":3,"session":S}'` (no target: keystroke path, works in the background). With `element_token` or x,y it needs the true-size window or `"delivery_mode":"foreground"` (global pointer wheel, moves the pointer) |
| drag | `cua-driver call drag '{"pid":P,"window_id":W,"from_x":200,"from_y":600,"to_x":400,"to_y":600,"delivery_mode":"foreground","session":S}'`; foreground only: background exits 1 with `background_unavailable`. It fronts the window, moves the physical pointer, then restores the prior frontmost app (verified) |
| menu | `cua-driver call invoke_menu '{"pid":P,"window_id":W,"path":["Edit","Select All"],"session":S}'` runs through AX; the frontmost app was unchanged afterwards |
| dialog | no dedicated tool. The `NSSavePanel` sheet shows up inside the owning window's tree (`AXSheet`, name `AXTextField`, `Cancel`, `Save` buttons) and as its own window id in `list_windows`. While the app is not frontmost, the sheet's buttons report `AXEnabled=false` and a click is refused (exit 1), even with `delivery_mode:"foreground"`. Working sequence: `cua-driver call bring_to_front '{"pid":P,"window_id":W,"session":S}'` (activates the app; returns `status: partial` and exits 1), a fresh `get_window_state`, then `click` the sheet's `Save` token; the fixture state file then showed `saved_path`. Dialogs are foreground |
| failing click | `click` with an unknown token exits 1 with `code: element_outside_target_window`, `effect: refused`; a superseded token exits 1 with `status: refused`, `code: stale_element_token` |

Golden captures of the observe (with screenshot), element click, coordinate click, type, press, hotkey, missing-element click, permissions, and window-list calls are in `tests/fixtures/using-apps-like-a-user/golden/cua/`. They were taken against the native fixture, with the menu bar subtree of `get_window_state` cut after the `AXMenuBar` row (it lists the user's recent apps and documents) and the capture directory rewritten to `/tmp/uala-golden`.

## Results

### Run 1

| candidate | steals | steal ms | cursor moves | clicks landed | strings landed | menu | dialog |
|---|---|---|---|---|---|---|---|
| peekaboo | 0 | 0 | 0 | 10/10 | 0/10 | yes | yes |
| cua | 0 | 0 | 0 | 10/10 | 10/10 | yes | no |
| orca | 1 | 10986 | 0 | 10/10 | 10/10 | no | no |

- peekaboo verdict: disqualified; failures: 11
- cua verdict: qualified; failures: 0
- orca verdict: disqualified; failures: 0

### Run 2

| candidate | steals | steal ms | cursor moves | clicks landed | strings landed | menu | dialog |
|---|---|---|---|---|---|---|---|
| peekaboo | 0 | 0 | 0 | 10/10 | 0/10 | yes | yes |
| cua | 0 | 0 | 0 | 10/10 | 10/10 | yes | no |
| orca | 1 | 10849 | 0 | 10/10 | 10/10 | no | no |

- peekaboo verdict: disqualified; failures: 11
- cua verdict: qualified; failures: 0
- orca verdict: disqualified; failures: 0

## Harness commands (as run)


### peekaboo Peekaboo 4.9.1 (release/4.9.1/e060b6ba2, built: 2026-10-10T12:36:50-07:00)

```
observe: peekaboo see --app dev.quirk.uala.fixture --json --path $TMP/peekaboo-see.png
click: peekaboo click --on elem_3 --snapshot ps1_fbf99c6a5460f222f2bd408eaf2e94de --app dev.quirk.uala.fixture --json
focus_text: peekaboo click --on elem_8 --snapshot ps1_b37aef2c8a8f9a5421a83280b6a0b7c9 --app dev.quirk.uala.fixture --json
type: peekaboo type uala01z --snapshot ps1_aeede390317ce195e5e0baf2d80b59fc --app dev.quirk.uala.fixture --clear --json
```

### cua cua-driver 0.34.1

```
list_windows: cua-driver call list_windows '{"pid":67320,"session":"bakeoff"}'
observe: cua-driver call get_window_state '{"pid":67320,"window_id":84816,"include_screenshot":false,"session":"bakeoff"}'
click: cua-driver call click '{"pid":67320,"window_id":84816,"element_token":"s0000000a:1","session":"bakeoff"}'
type: cua-driver call type_text '{"pid":67320,"window_id":84816,"element_token":"s0000000b:6","text":"uala01z","session":"bakeoff"}'
```

### orca 1.4.216-rc.0.zy03

```
observe: orca computer get-app-state --app dev.quirk.uala.fixture --json --no-screenshot
click: orca computer click --element-index 2 --app dev.quirk.uala.fixture --json --no-screenshot
focus_text: orca computer click --x 354 --y 263 --app dev.quirk.uala.fixture --json --no-screenshot
type: orca computer type-text --text uala01z --app dev.quirk.uala.fixture --json --no-screenshot
```
