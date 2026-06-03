# Agent Isles-aware Quirk artifacts

Quirk is the authoring and workflow discipline layer. Agent Isles is the optional rendering and presentation layer. This contract keeps normal Quirk skill use lightweight while making richer rendered reports available when Agent Isles is present.

## Core contract

- Markdown source is canonical. Review, edit, diff, and archive the `.md` files.
- generated HTML is disposable by default. The bridge writes to `.quirk/isles/`, which is ignored and can be deleted or regenerated at any time.
- Agent Isles is optional. Quirk must remain useful when Node, npm, npx, and Agent Isles are absent.
- Any built-in Agent Isles island may be used when it improves artifact structure, scanning, or readability.
- Quirk-specific component-pack tags represent Quirk-owned semantics such as typed artifacts, TDD cycles, plan readiness, and review findings.
- Prefer plain Markdown when a heading, list, or table communicates the artifact more clearly than a component.

## Bridge helper

Use the stdlib-only helper to inspect or run the optional renderer:

```bash
python3 bin/agent_isles.py doctor
python3 bin/agent_isles.py command examples/agent-isles/typed-artifacts-summary.md
python3 bin/agent_isles.py render examples/agent-isles/typed-artifacts-summary.md
```

The helper chooses command paths in this order:

1. repo-local `node_modules/.bin/isles`,
2. `isles` on `PATH`,
3. explicit `npx agent-isles@next ...` when `npx` exists and `--no-npx` is not set.

It never silently installs packages. The npx fallback is printed or executed only as an explicit command path and may download `agent-isles@next` according to npx behavior.

By default the helper adds `--pack packs/quirk --no-user-packs` when the local Quirk pack exists. Use `--with-user-packs`, `--no-quirk-pack`, and repeated `--pack <path>` only when a workflow intentionally changes that reproducibility boundary.

## Authoring rules

- Keep a useful Plain Markdown fallback near every island or custom element. A reader should understand the artifact in a terminal, code review, or raw GitHub view.
- Use no self-closing custom elements. Write `<quirk-tdd-cycle>...</quirk-tdd-cycle>`, not `<quirk-tdd-cycle />`.
- Keep raw HTML blocks continuous when nesting custom elements; many Markdown parsers stop raw HTML parsing after blank lines or indentation changes.
- Put durable data in Markdown text and safe attributes. Do not rely on generated DOM state as the source of truth.
- Use sanitized mode for untrusted Markdown renders. The Quirk pack manifest declares sanitized-mode attributes and intentionally omits unsafe attributes such as `style`, `srcdoc`, and event handlers.
- Treat component packs as trusted local code. Even in sanitized mode, local pack JavaScript executes in the rendered page; review pack changes like code.
- Avoid gratuitous components. Built-in `<agent-*>` islands and Quirk `<quirk-*>` tags are views, not a replacement for clear prose.

## When to use each surface

- Use built-in `<agent-*>` islands for generic presentation: status boards, decisions, risks, timelines, action lists, comparisons, and callouts.
- Use `<quirk-artifact-summary>` for Quirk typed artifact rollups across `BUGS.md`, `DEFERRED.md`, `TEST_BACKLOG.md`, `proposals.md`, and ADR files.
- Use `<quirk-tdd-cycle>` for red/green/refactor state, verification evidence, and deferred/skipped test debt.
- Use `<quirk-plan-review>` for plan readiness gates: scope, clarity, files, tests, risks, and handoff readiness.
- Use `<quirk-review-finding>` for review findings that need severity, path, recommendation, and status.

## Compatibility

This integration targets the current prerelease Agent Isles command surface exposed through `agent-isles@next` and local `isles` binaries. Default Quirk tests do not require Agent Isles or Node. Developers who have Agent Isles available can smoke-test with:

```bash
python3 bin/agent_isles.py doctor
python3 bin/agent_isles.py render examples/agent-isles/integrated-workflow.md --print-command
python3 bin/agent_isles.py render examples/agent-isles/integrated-workflow.md
```

Expected reproducibility flags for direct Agent Isles commands are:

```bash
isles packs resolve examples/agent-isles/integrated-workflow.md --pack packs/quirk --no-user-packs
isles render examples/agent-isles/integrated-workflow.md --pack packs/quirk --no-user-packs --output .quirk/isles/integrated-workflow.html
```

Generated files under `.quirk/isles/` are non-canonical views and should not be committed unless a future publishing issue deliberately changes that policy.
