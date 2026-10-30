# The evidence ledger

Every claim the page or the film makes has one row in `$E/evidence.md`, and the page's results table is that ledger. Write the ledger before any footage, so the film is a tour of what is already proven.

## The columns

One Markdown table, one row per behavior:

```
| Behavior | Claim | Result | How checked | Proof |
|---|---|---|---|---|
| Hover grows the button | The button expands to its full label on hover | Pass | Real mouse move in the web build, then a pixel check | media/hover-after.png |
```

- **Behavior** is the name a reader would use, such as "Hover shows the full label".
- **Claim** is one sentence stating what should be true.
- **Result** is exactly one of the five values below.
- **How checked** says what was run: the driver and the kind of input (real mouse events, a command, a test name), and the engine or build. A row that can't say this isn't Pass.
- **Proof** is a path under `$E/media/`, a saved command output, or a test name with its run output. Keep paths relative to `$E`.

| Result | Meaning |
|---|---|
| Pass | The behavior was run for real and the proof shows the claimed result. |
| Partly | Part of the claim was shown. Say which part in Claim or How checked. |
| Unit test only | A test passed, and the behavior wasn't run in the app or command. |
| Not proven | Nothing was checked. |
| Failed | It was run and the claim was false. |

A behavior that's true but unchecked is Not proven until you check it. Then check it or leave it out of the page's claims; never round up to Pass.

## Filling it

1. **Read first.** Take behaviors from the spec's scenarios, then add what an earlier app run and the tests already show. Copy results from those runs only where their proof still exists; cite it in Proof.
2. **Measure what a recording can't show.** A film shows one run. A measurement (an element's left edge at 261.8px in both states), keyboard reach or error handling needs its own row and its own proof.
3. **Verify first when the main behavior was never run.** Invoke `quirk:using-apps-like-a-user` with `--unattended`, one goal per behavior, with a test account or seeded data only. Every row then comes from that run: `OBSERVED` with a screenshot showing the result is Pass; `NO_EFFECT` or `blocked` is not. Copy its screenshots into `$E/media/`. A behavior it couldn't check goes in as Not proven.
4. **A feature with no UI** gets the real command or test run, with its real output saved under `$E/media/` and cited in Proof. A diagram of how it works is fine on the page if it's labeled as a diagram, and it never stands in as proof.
5. **Stop on a broken or unreachable main behavior** before building anything. The stop wording is in the skill's step 2.

## Handing rows to the film

`making-videos` keeps its own `sources.md`. Each script line there cites a ledger row, such as `Row 2`, and doesn't restate the proof. Only rows marked Pass or Partly go into the script, and a Partly row's narration claims just the part that passed. A row marked Not proven, Unit test only or Failed never appears in the film.

## What the page does with the ledger

- The results table is the ledger, with Proof as links to the inlined screenshots or the saved output.
- "What's still open" is every row that isn't Pass, plus anything cut.
- The summary names the biggest gap among those rows.

Section wording and reader variants are in [page.md](page.md).
