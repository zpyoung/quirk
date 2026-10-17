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

**In the reviewer seat, the project pack and `REVIEW.md` are read at the merge base**
(`--policy-ref <merge-base SHA>`, taken from the context's `refs.base`: the commit the
change branched from), so a change cannot weaken its own review by editing them. Policy
that landed on the target branch after that point does not apply. The flag is required in the
reviewer seat: `resolve_policy.py` exits 2 for a reviewer context without it, unless
the run is diff-only. Files read from a ref are written under `policy-files/` next to
`policy.json` so lenses can read them from disk.

A reviewer run with no source checkout passes `--diff-only` instead of `--source-root`.
It skips the project pack and `REVIEW.md`, still applies the built-in roster and the user
pack, excludes generated files by `skip_globs` only (`.gitattributes` is unreadable), and
writes `diff_only: true` and a warning into `policy.json`. `--diff-only` cannot be combined
with `--policy-ref` or `--source-root`.

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
skip_globs: ["**/*.lock"]      # union across layers; excluded from review
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
