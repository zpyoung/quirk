# Review

Review returns ranked `file:line` findings on UI code. It judges and reports. It edits only when the user asks.

## Contents

- [Intent and scope](#intent-and-scope)
- [Severity](#severity)
- [Run the detector](#run-the-detector)
- [Confirm every hit](#confirm-every-hit)
- [Walk the checklist](#walk-the-checklist)
- [Craft tests and drift](#craft-tests-and-drift)
- [What not to report](#what-not-to-report)
- [Output format](#output-format)
- [Triage order](#triage-order)
- [Offer to apply fixes](#offer-to-apply-fixes)

## Intent and scope

Read `.quirk/design/system.md` if it exists. You review against what the design is trying to be, so a deliberately dense trading screen is not wrong for being dense. If no system is saved, infer the user, the task and the feel from the code. If you cannot, review against general craft and say so in the closing note.

The scope is one of two things:

- **Named files or folders.** Review exactly those.
- **The branch diff.** Use this for "clean up the UI slop on this branch" and similar asks. It replaces upstream's separate deslop pass. Find the base, then scope everything to lines changed since it:

```bash
default=$(git symbolic-ref --short refs/remotes/origin/HEAD | sed 's|^origin/||')
base=$(git merge-base HEAD "origin/${default:-main}")
git diff --name-only "$base"; git ls-files --others --exclude-standard
```

Run git from inside the repo. Only findings on lines the branch added or changed count. Pre-existing problems in untouched lines stay out.

Use only [checklist.md](checklist.md). Never fetch rules from the network.

## Severity

Each checklist rule carries a default severity. Move it one level when context clearly justifies it, for example tiny text in a legal footer. Never move a check-intent flag.

- **P0:** a user is blocked or an accessibility floor fails. No keyboard path, focus lost, zoom disabled. Fix before merge.
- **P1:** a task works wrongly or the user is misled. Unlabeled controls, missing error or empty states, a broken link, drift from the saved system.
- **P2:** a real defect with a clear fix. Tiny text, `transition: all`, missing reduced-motion handling, a one-off that should be a shared component.
- **P3:** polish, and every check-intent flag. A check-intent flag asks the owner to justify the choice or change it. It is never P0 to P2.

## Run the detector

For CSS, SCSS, JSX and TSX, run the script over the scope. `SKILL_DIR` is the directory holding SKILL.md.

```bash
python3 "$SKILL_DIR/scripts/detect.py" --format json src/Modal.tsx src/Table.tsx src/Button.tsx
python3 "$SKILL_DIR/scripts/detect.py" --format json --changed-since "$base" .
```

Exit 0 means no findings, 1 means findings, 2 means a usage or git error on stderr. JSON is `{"findings": [{path, line, rule, severity, message}], "scanned": N}`.

The script reads only CSS, SCSS, JSX and TSX. For Vue, Svelte, plain HTML and native code, skip it and rely on the checklist. Say so in the closing note.

## Confirm every hit

A hit is a candidate. Open the file at that line and read the code around it before you report it.

- Keep it when the code really does what the rule describes.
- Drop it when something nearby answers it: a `focus-visible` style applied through another class, a role passed through spread props, a label elsewhere for a placeholder, a visually hidden element, generated or vendored code.
- Drop a check-intent hit when the code or system.md gives its reason.

Report only what you kept. A dropped hit never appears in the output.

## Walk the checklist

The detector catches only what a regex can see. The rest of [checklist.md](checklist.md) needs reading. Walk its categories against the files in scope and skip a category the code cannot touch, such as Hydration in a plain stylesheet. Do not repeat a rule the detector already confirmed.

## Craft tests and drift

Run the four craft tests from the Product craft section on the screen as a whole: swap, squint, signature and token. Report a failure as one finding with the rule id, at the line where the screen's structure starts. For a persona check, walk the primary action as a power-user and report the `craft-power-user-*` rules that fail. Do it for tools people use repeatedly, not for a one-time settings screen.

If system.md exists, compare the values you read against it. Report `drift-system-value` and name both values: "radius 10px, system.md says 6px". For drift without a saved value behind it, classify the cause first, because each has a different fix:

- **Missing token:** the value repeats and the system has no name for it.
- **One-off implementation:** a shared component or pattern should replace it.
- **Conceptual mismatch:** the flow or hierarchy differs from comparable product areas.
- **Local defect:** the code is simply incomplete or inconsistent.

Fix at the narrowest level that removes the cause.

## What not to report

- **Taste.** "I would have chosen another font" is not a finding when the choice is coherent and well executed.
- **A bold choice that works as intended.** A saturated palette that matches the stated feel is a success.
- **Anything outside the scope**, or on lines a branch review did not touch.
- **Anything system.md already decided.**
- **Lint, format and compile concerns.** Others own them.

If you cannot say what a finding costs the user or why it reads as generated, cut it. A few high-conviction findings beat a long cosmetic list.

## Output format

Return one list, grouped by severity with a heading line per level (`P0`, `P1`, `P2`, `P3`). Leave out empty levels. Inside a level, sort by path then line. One line per finding, with two spaces between fields:

```
path:line  rule-id  problem → fix
```

Example:

```
P0
src/Button.tsx:12  focus-outline-removed  outline-none with no focus-visible style → add focus-visible:ring-2
src/Modal.tsx:42  focus-dialog-trap  focus can leave the open dialog → trap focus, return it on close
P2
src/Table.tsx:88  type-tiny-text  text-[10px] on the column headers → use 12px or larger
P3
src/Nav.tsx:20  intent-eyebrow-label  small uppercase group labels → keep if they group navigation, drop if decorative
```

Every finding needs a line number; for a whole-file concern, use the first line. Keep the problem and the fix to what is not obvious from the rule id. No preamble, and do not announce which files you loaded.

End with one note on what needs a running app to check: contrast, overflow, focus order, layout shift, motion feel, and the squint test on a real render. If you did render the app, say which sizes you checked. If the target was native or the detector did not apply, say the checks were prose only.

## Triage order

When findings compete for attention, within a severity order them like this, and fix in the same order:

1. Broken or blocked tasks, data loss, misleading state, inaccessible paths.
2. Missing loading, empty, error, success, disabled and permission states.
3. Flow, hierarchy, responsive and design-system drift.
4. Visual and motion inconsistencies.
5. Code and asset cleanup.

Do not perfect one corner and leave the rest below the same bar.

## Offer to apply fixes

After a branch-diff review, offer once to apply the fixes. If the user agrees, work in triage order, edit only lines the branch changed, match the surrounding conventions, and leave behavior alone. A fix that turns into a rebuild gets named as a follow-up instead of half done. Offer to update system.md if you introduced or changed a token.
