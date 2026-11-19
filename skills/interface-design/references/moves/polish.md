# Polish

Bring a finished feature to a consistent, complete standard across its whole path.

## When to use

- A feature works and needs the final pass before shipping.
- It drifts from neighboring screens in tokens, components, terminology or states.

Polish is refinement, not a hidden redesign. If the concept itself is wrong, say so and suggest a redesign or the bolder move. Don't slip a replacement in.

## Read first

- `.quirk/design/system.md`, if it exists. It defines what "consistent" means here. If it doesn't, read representative tokens, shared components and neighboring flows and follow the project's conventions.
- For native targets, `surfaces/ios.md` or `surfaces/android.md`.
- The quality bar and constraints. If they aren't clear, ask: what ships, when, and what is deliberately unfinished.

## Procedure

1. **Classify each drift before fixing it.**
   - Missing token: the system needs a reusable value.
   - One-off implementation: a shared component or pattern should replace it.
   - Conceptual mismatch: flow, information architecture or hierarchy differs from comparable areas.
   - Local defect: the work is simply unfinished or inconsistent.

   Fix the cause at the narrowest correct level. A value that differs from system.md is drift, so fix it toward the saved value. Ask when a binding principle can't be inferred.
2. **Use the feature.** Walk the real path at desktop and mobile on the web, or on a simulator, emulator or device for native, if the app can run. Note whether the path is functionally complete, and which states, content lengths, roles and input methods users will meet.
3. **Triage in this order.**
   1. Broken or blocked tasks, data loss, misleading state, inaccessible paths.
   2. Missing loading, empty, error, success, disabled and permission states.
   3. Flow, hierarchy, responsive behavior and system drift.
   4. Visual and motion inconsistencies.
   5. Code and asset cleanup.

   Don't perfect one corner while the rest sits below the same bar.
4. **Fix the whole path.**
   - Flow and hierarchy: match neighboring terminology, disclosure, routing and save behavior. Make the primary task and current state obvious. Connect arrival, transition, empty and recovery paths.
   - Layout and type: align to the grid and spacing scale, including optically. Group tightly, separate groups generously. Keep same-role type identical. Test wrapping, localized length, zoom and font loading.
   - Color, imagery and icons: semantic tokens, stable color meanings across themes, contrast in every state, one icon family at a consistent weight and size, no image layout shift, useful alt text.
   - Interaction: every control gets default, hover, focus, active, disabled, loading, error and success behavior as it needs. Keep visible focus, logical tab order, labels and sensible touch targets. Motion is 150 to 250ms, conveys state only and can be interrupted.
   - Content and code: consistent terminology, capitalization and punctuation (ask before changing claims). Remove debug output, dead code, unused imports and obsolete styles. Prefer shared components where the system owns the pattern. Promote a value to a token only when it is reusable.

## Preserve

- The incumbent visual world, content, behavior and everything outside the scope you were given.
- Claims and factual copy.
- Deliberate exceptions. Document the narrow ones instead of normalizing them.

## Verify

For web code, run `python3 "$SKILL_DIR/scripts/detect.py" <files>` and confirm each hit in context. It is defect evidence, not proof of quality. Don't run it on native code. For native work, state in your summary that the native checks were prose-only.

Walk the full path again with mouse, keyboard and touch where they apply.

- Mobile, middle and wide layouts on the web, or phone and tablet in both orientations on native.
- Loading, empty, error, success, disabled, long and missing-content states.
- Zoom, contrast, focus, semantics and screen-reader names.
- Console errors, layout shift, interaction latency and image loading. On native, runtime warnings and dropped frames.
- Agreement with system.md, neighboring features and the scope you were given.

Finish by reading your diff. Remove accidental churn, orphaned code, duplicated values and temporary files. Ship only when the feature is complete and consistent along the whole path.

## Save to system.md

If polish added or changed tokens or patterns, offer once to record them in `.quirk/design/system.md`. Create `.quirk/design/` when saving.
