# Review policy: packs and REVIEW.md

`scripts/resolve_policy.py` turns four layers into one `policy.json` that decides which
lenses run, on which models, at what posting floor, and against which critical paths.

## Layers

Each layer overrides the one before it:

1. **Built-in roster**: `references/lenses/*.md`, one file per lens with front matter
   (`id`, `run_when`, `model`, `escalate`, `batched`).
2. **User pack**: `${XDG_CONFIG_HOME:-~/.config}/quirk/review/`, or the directory given
   with `--pack` for one run. This is where an org standard lives.
3. **Project pack**: `<repo>/.quirk/review/`, committed with the repo. If the repo
   ignores `.quirk/` wholesale, add `!.quirk/review/` to its `.gitignore`.
4. **`REVIEW.md`**: the repo-root file plus any `REVIEW.md` in an ancestor directory of a
   changed file. A deeper file overrides a shallower one key by key.

**In the reviewer seat, the project pack and `REVIEW.md` are read from the target
branch** (`--policy-ref <target SHA>`), so a change cannot weaken its own review by
editing them. Files read from a ref are written under `policy-files/` next to
`policy.json` so lenses can read them from disk.

## Pack layout

| Path | Purpose |
|---|---|
| `pack.yaml` | Settings (keys below). |
| `lenses/<id>.md` | Same id as a built-in lens: replaces its checklist (front matter fields you set override too). New id: adds a lens; it must declare `run_when`, and defaults to `model: sonnet`, `escalate: false`, `batched: true`. |
| `guidance/*.md` | Review emphases passed to the `conventions` lens. |

`references/example-pack/` replaces the risk rubric for a payments domain, adds a
`license-headers` lens, and declares critical paths.

## Settings

`pack.yaml` and the front matter of `REVIEW.md` accept the same keys. **Use block
mappings**: the parser rejects flow mappings like `{db: haiku}`; flow lists of plain
values such as `[a, b]` are fine.

```yaml
severity_floor: Should fix     # Must fix | Should fix | Nit; findings below it never post
escalation: true               # escalate lenses one model tier on High risk / Critical
models:                        # per-lens model tier: sonnet | opus | haiku
  correctness: opus
skip: [observability]          # lenses to skip; a union across layers
critical_paths: ["src/payments/**"]   # union across layers; feeds the risk lens
skip_globs: ["**/*.lock"]      # union across layers; excluded from review and the size gate
cross_family:                  # opt-in second-family verification of Must/Should findings
  enabled: false
  alias: codex
cross_repo:
  search_agent: null           # a subagent type the cross-repo lens may dispatch
```

Scalars override; `skip`, `critical_paths`, and `skip_globs` accumulate; `models`
merges per lens. Unknown keys produce a warning. A malformed file stops the run with
exit 2 and names the file and line.

The body of `REVIEW.md` (everything after the front matter) is prose guidance for the
`conventions` lens, alongside each pack's `guidance/*.md`.

## Generated files

With `--apply`, files whose `linguist-generated` attribute is set (from `.gitattributes`)
or that match a `skip_globs` pattern are removed from the review context before the size
gate, and listed in `excluded_generated` and the report Summary. In the reviewer seat the
attributes come from the target ref (`git check-attr --source`, git 2.40 or newer); on
older git that half is skipped with a warning and `skip_globs` still apply.
