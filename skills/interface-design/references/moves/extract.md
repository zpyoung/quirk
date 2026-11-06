# Extract

Turn repeated UI patterns and hard-coded values into shared components and tokens, then move the existing uses over.

## When to use

- The same pattern is hand-built in three or more places.
- Colors, spacing, type or timing values are scattered as literals.
- Two implementations of one concept have drifted apart.

Don't use it to invent a design system for a codebase that has none. That is a bigger decision than this move.

## Read first

- `.quirk/design/system.md`, if it exists. Its recorded patterns and tokens are the target names and values.
- The project's shared UI directory, token files and a few call sites. Learn the naming, prop and import conventions before writing anything.

If there is no shared UI directory, ask the user where extracted code should live before creating one.

## Procedure

1. **Find candidates.** Look for repeated components, literal values that act as tokens, repeated composition (form rows, toolbars, empty states), repeated type or timing combinations, and near-duplicates.
2. **Filter.** Keep only what has three or more uses with the same intent. Two things that look alike but serve different purposes stay separate. Duplication is cheaper than the wrong abstraction.
3. **Plan.** List the components, tokens, variants and names, matching existing conventions. Name tokens by role, not by value, and add a token only when a value carries meaning.
4. **Build the shared version.** Give each component a small props API with sensible defaults and the variants the real call sites need. Keep keyboard behavior, focus handling and ARIA inside the component. Type the props.
5. **Migrate.** Search for every instance, replace each with the shared version, then delete the old implementations. A half-migrated pattern is worse than none.
6. **Document.** Add the new pieces to the component catalog or Storybook if the project keeps one.

## Preserve

- How every migrated site looks and behaves. This move is a refactor, not a restyle.
- Copy, and anything outside the patterns you extracted.
- The incumbent conventions. Don't rename or restructure existing shared code to suit your taste.

## Verify

- Each migrated site matches its before state at desktop and mobile widths, including hover, focus, disabled and error states, when the app can run.
- Types check, tests pass and no dead copies remain.
- Props stay narrow. A component with a dozen boolean flags is too generic, so split it or leave it.

## Save to system.md

If you added tokens or components, offer once to record them in `.quirk/design/system.md` with measured values (for example `Button primary: 36px h · 12px 16px pad · 6px radius · 14px/500`). Create the `.quirk/design/` directory when saving.
