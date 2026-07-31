# Tech spec — `filing-requests`

**Status:** Draft (awaiting review)
**Logic spec:** [`logic.md`](./logic.md) — owns *why* and *behavior*. This document owns *where*
and *contracts*. Every technical section below back-links the `logic.md` section it implements.

**For agents.** This is the code-anchored implementation map for the skill described in
`logic.md`. It contains pointers, not pasted prose — exact files, contracts, and schemas. The
implementer authors the actual `SKILL.md` prose and script bodies; this document says *where*,
*what must be true after*, and *what not to guess at*.

**No-Code convention (inherited from `writing-plans`).** Every code-shaped block below is tagged
`CONTRACT:` (interface/signature shape), `SCHEMA:` (exact data shape), `COMMAND:` (verbatim shell),
`REGEX:` (a literal pattern that is the spec), `CONFIG:` (exact config keys/values), or
`PSEUDOCODE (justified, ≤3 lines):`. No block pastes a full implementation.

**Where this spec had to call it.** `logic.md` deliberately left implementation open (its own
words: "implementation open"). Wherever this document invents something `logic.md` doesn't state,
the call is marked inline with **Tech-spec call (logic.md silent):** and its reasoning. These are
additions, not reinterpretations — none of them narrows or contradicts a Decisions Locked entry.

---

## Purpose

Make the `filing-requests` skill buildable and testable without reopening any behavioral question
`logic.md` already settled.

Concretely, this document pins down four things the logic spec deliberately left open:

1. **The canonical JSON schema** — exact keys, types, and which sibling keys each `provenance`
   value requires, so the "invented specificity has nowhere to enter" guarantee is enforced by
   validation rather than by model discipline.
2. **CLI contracts for six stdlib-only scripts** — arguments, stdin/stdout shapes, exit codes, and
   failure modes, so every deterministic layer is provable by fixture with no model in the loop.
3. **The three algorithms** whose ambiguity the logic spec's adversarial review flagged as
   implementation-diverging: template resolution, drift carry-over, and the non-waivable gate.
4. **The test plan** — specifically which behaviors are fixture-provable and which are only
   exercisable through a live session, so the boundary is a stated design property rather than an
   accident of what was easy to test.

Out of its scope: `SKILL.md`'s interview prose and the script bodies. Those are the implementer's,
written against the contracts here.

## Architecture

*Back-link: [logic.md → Skill-level](./logic.md#decisions-locked)*

New skill, additive only — no existing file is modified. Repo constraints verified directly
against `pyproject.toml:1-8` and `tests/`: `requires-python = ">=3.9"`, no `[project.dependencies]`
table exists, and no `bin/*.py` script imports anything beyond the standard library. This tech spec
holds that line: **no third-party dependency may be required.**

The distinction matters for YAML specifically. PyYAML is frequently present in a developer's
environment — but quirk ships to arbitrary machines, so nothing here may *depend* on it. That makes
PyYAML usable when it happens to exist and forbidden as a requirement, which is why parsing takes
the two-tier shape described under [The YAML tier](#the-yaml-tier-pyyaml-then-_yaml_mini): prefer
the real parser, fall back to a bounded subset. Being unable to require a library is not the same
as the library being unavailable, and the fallback exists for the former.

`CONFIG:` file layout —
```
skills/filing-requests/
  SKILL.md                          # interview flow: Orient / Establish / Emit (prose, implementer-authored)
  reference/
    field-catalogs.md               # per-type question wording + inspection strategy (logic.md#per-type-field-cores)
    guardrails.md                   # non-waivable gate, secret-scan gate, disclosure rule — operational checklist
    template-resolution.md          # human-readable walkthrough of the ordered resolution algorithm
  scripts/
    _common.py                      # shared: stdin/file JSON I/O, schema_version guard, CORE_FIELDS, slugify — no CLI surface
    _yaml_mini.py                   # minimal YAML-subset parser (see Template resolution) — no CLI surface
    canonical_schema.py             # canonical JSON constants + validate() — invoked by its own filename, no separate entry point
    template_resolve.py             # discover / select / fields subcommands
    secret_scan.py                  # scan a canonical doc for leaked secrets
    markdown_render.py              # canonical JSON -> markdown artifact text
    drift_apply.py                  # apply the bug<->feature carry-over tables
    github_file.py                  # dry-run / --execute wrapper around `gh issue create`

tests/
  test_filing_skill.py              # frontmatter + activation (mirrors test_skill.py)
  test_filing_canonical_schema.py
  test_filing_template_resolve.py
  test_filing_secret_scan.py
  test_filing_markdown_render.py
  test_filing_drift_apply.py
  test_filing_github_file.py
  fixtures/filing-requests/
    canonical/*.json                # sample canonical docs (valid bug, valid feature, halted feature, ...)
    repos/*/.github/ISSUE_TEMPLATE/  # sample template trees for discovery + selection fixtures
```

**Technologies in play:** Python 3.9+ stdlib only (`argparse`, `json`, `re`, `pathlib`, `subprocess`,
`dataclasses`, `enum`), `git`/`gh` CLIs (delegated auth, per
[logic.md → emission-and-auth](./logic.md#decisions-locked)), pytest (repo's existing test stack,
`tests/`, `pyproject.toml:6-8`).

**Tech-spec call (logic.md silent):** `logic.md`'s Data flow names two glob patterns for GitHub
templates: `.github/ISSUE_TEMPLATE/*.yml` and `*.md`. GitHub also recognizes `.yaml`. `discover`
(below) globs both extensions for the YAML form path — this is an addition, not a narrowing, and
is called out rather than silently assumed.

---

## Canonical JSON schema

*Back-link: [logic.md → The canonical form is the spine](./logic.md#the-canonical-form-is-the-spine),
[logic.md → Negative observation](./logic.md#negative-observation)*

`SCHEMA:` root object:

| Key | Type | First appears | Required for emission |
|---|---|---|---|
| `schema_version` | int | doc creation | yes — see Versioning below |
| `type` | enum `bug` \| `feature` \| `code-change` | Orient | yes |
| `headless` | bool | Orient | yes |
| `depth` | enum `none` \| `read` \| `run` | Orient | yes |
| `title` | string | Establish (drafted once core fields resolve) | yes |
| `target` | object, see below | Orient | yes |
| `template` | object `{applied: bool, path: string \| null, fields: [{name: string, required: bool, source: "template" \| "core"}]}` | Establish (after template resolution) | yes |
| `fields` | array of field objects, see below | Establish (may be `[]` at doc creation) | yes |
| `proposed_solution` | object `{value: string, attributed_to: "reporter"}` | Establish, only if the reporter proposes a fix | no |
| `verified_against` | array of strings | Establish (grows as `observed` sources accrue) | yes (may be `[]`) |
| `disclosure_required` | bool | derived, not hand-authored | yes |
| `halted` | object `{field: string, reason: string}` | only when the non-waivable gate blocks (see below) | absence = not halted |

**The core field set is read from `template.fields`, not recomputed.** `template_resolve.py fields`
computes the union once when template resolution settles, and its output is written onto the
document. Every later consumer — `canonical_schema.py --for-emission` above all — reads the union
from the document it is already holding.

This is what makes the union rule enforceable at all. `canonical_schema.py`'s interface is
`--input <doc>`; without the union on the document, the gate meant to enforce
"a template can add requirements but never subtract them"
([logic.md → Required sections in a template](./logic.md#required-sections-in-a-template)) can only
see the fixed per-type table, and a template-added required field left unresolved passes
emission silently. Passing the union as a separate CLI argument was considered and rejected: an
omitted flag degrades to the weaker check with no signal, which is a failure that hides precisely
when it matters. A document that carries its own field set cannot be validated against the wrong
one.

`template.fields` is therefore **required and non-empty on any document reaching `--for-emission`**,
including the `--no-template` fallback path — there the entries are all `source: "core"`. A document
whose `template.fields` is absent or empty fails `--for-emission` with a structural error (exit `3`)
rather than falling back to the per-type table, because a silent fallback is the exact failure this
key exists to prevent.

**Tech-spec call (logic.md silent):** `template` and `halted` are inventions of this tech spec.
`logic.md` requires that template resolution "record that no template applied"
([§Choosing among templates](./logic.md#choosing-among-templates)) and that a blocked emission
"say[s] which field is unresolved and why"
([§Data flow](./logic.md#data-flow)) — both need a machine-readable home, since the caller
(`SKILL.md`) has to branch on them without re-parsing prose. These two keys are that home.

`SCHEMA:` `target` object:

| Key | Type | Required |
|---|---|---|
| `kind` | enum `"github"` (`"gitlab"`, `"jira"` reserved, unimplemented — [§Deferred to later versions](./logic.md#deferred-to-later-versions)) | yes |
| `repo` | string `"owner/repo"` | yes when `kind == "github"` |
| `writable` | bool | yes |
| `third_party` | enum `"yes"` \| `"no"` \| `"unknown"` | yes |
| `visibility` | enum `"public"` \| `"private"` \| `"unknown"` | yes |

**Tech-spec call (logic.md silent):** neither `visibility` nor a tri-state `third_party` appears in
`logic.md`'s worked examples (its example JSON shows `third_party` as a plain bool), but the
disclosure rule — "appears when the target is public or third-party; when visibility **or
ownership** cannot be determined confidently, the skill discloses"
([§Decisions Locked → provenance-and-safety](./logic.md#decisions-locked)) — names two independent
axes of uncertainty, visibility and ownership, and a plain bool can only represent a confident
"yes" or "no" for the second. `third_party` is widened to the same three-state shape as
`visibility` so "ownership undeterminable" is representable at all. `disclosure_required` is
**derived, never hand-set**: any script that finalizes a canonical doc recomputes it from `target`
before validation succeeds — `disclosure_required = (visibility != "private") or (third_party !=
"no")`, so `third_party: "unknown"` discloses exactly like `third_party: "yes"` — and overwrites
whatever was there. This keeps the stored value from drifting out of sync with its inputs.

`SCHEMA:` `fields[]` entry:

| Key | Type | Required when |
|---|---|---|
| `name` | string | always |
| `provenance` | enum `observed` \| `reported` \| `inferred` \| `missing` | always |
| `value` | string | required if `provenance` in `{observed, reported, inferred}`; **forbidden** if `provenance == missing` |
| `source` | string | required **iff** `provenance == observed` |
| `reason` | string | required **iff** `provenance == missing` |
| `polarity` | enum `"negative"` | optional; legal **only if** `provenance == observed` — its absence means an ordinary (non-negative) observation, per `logic.md`'s own examples (the `environment` field carries no `polarity` key at all) |
| `needs_confirmation` | bool | optional; set only by `drift_apply.py` — on the one mapping `logic.md` calls out as re-opening a question ([§Data flow](./logic.md#data-flow): `expected_behavior → acceptance_criteria`), and on a merge that appends weaker-provenance content onto a stronger field (see [Drift carry-over](#drift-carry-over)); cleared once the user edits or confirms the value |

**Tech-spec call (logic.md silent):** `needs_confirmation` is this tech spec's representation of
"a `reported` draft the user must confirm" ([§Data flow](./logic.md#data-flow)). Without it, a
carried-over `acceptance_criteria` is indistinguishable from one the user actually typed — exactly
the ambiguity `logic.md` is careful to avoid everywhere else provenance is concerned.

### Versioning

`CONFIG:` `CURRENT_SCHEMA_VERSION = 1`, defined once in `_common.py`, imported by every script that
consumes a canonical document — `canonical_schema.py`, `secret_scan.py`, `markdown_render.py`,
`drift_apply.py`, `github_file.py` (five of the six). Each of those five calls a shared
`check_schema_version(doc)` before doing anything else: `schema_version` is required (no default —
this is a format the skill controls end-to-end, unlike a markdown file a user might hand-edit, so
there is no legacy-file case to be lenient about); a document whose `schema_version` exceeds
`CURRENT_SCHEMA_VERSION` fails with exit `8` (below) rather than being guessed at.
**`template_resolve.py` is the one exception** — its three subcommands take a repo path, a
candidate list, and a resolved template respectively, never a canonical document, so there is
nothing for it to version-check. A future breaking change to this shape bumps
`CURRENT_SCHEMA_VERSION` and every consuming script gains an explicit branch for the new version; an
additive-only change (a new optional key) does not bump it. There is no migration path yet — v1 is
the first version, and the guard exists so a second version can be introduced later without a
redesign.

The per-type core/optional field lists are likewise defined exactly once, in `_common.py`, as the
single source of truth both `template_resolve.py fields` (the union rule) and `canonical_schema.py`
(the non-waivable check, and "every core field resolved" for `--for-emission`) import rather than
each hard-coding their own copy — verbatim from
[§Per-type field cores](./logic.md#per-type-field-cores):

`SCHEMA:`
```yaml
core_fields:
  bug: [current_behavior, expected_behavior, steps_to_reproduce, environment]
  feature: [problem, who_benefits, current_behavior, acceptance_criteria]
  code-change: [scope, why_now, blast_radius]
optional_fields:
  bug: [stack_trace, frequency, regression_range, workaround]
  feature: [value_or_impact, constraints, out_of_scope, prior_art]
  code-change: [migration, rollback, test_plan, perf_impact]
non_waivable:
  feature: [problem, acceptance_criteria]
```

---

## Contracts & interfaces — the six scripts

*Back-link: [logic.md → Deterministic work goes in Python](./logic.md#key-decisions--rationale)*

### Shared conventions

`CONTRACT:` every script accepts `--input <path> | -` (stdin) where it consumes a canonical
document, and reads/writes UTF-8 JSON with `ensure_ascii=False`. `_common.py` provides
`read_json_arg(path_or_dash) -> dict` and `slugify(text: str, sep: str = "-") -> str` (lowercase,
non-alnum runs collapsed to `sep`, trimmed, capped at 60 chars) — shared so the two things that
need slugs (artifact filenames in kebab-case, template-derived field names in snake_case) don't
diverge into two ad hoc implementations.

`SCHEMA:` shared exit-code convention (uniform across all six scripts; a script that doesn't use a
given code simply never returns it):

| Code | Meaning |
|---|---|
| 0 | success / clean |
| 1 | findings/secrets present — returned by `secret_scan.py` directly, and by `github_file.py --execute` when its own defense-in-depth secret re-scan (see its contract below) is not clean |
| 2 | usage error — bad args, malformed JSON, unreadable file |
| 3 | validation failure against the canonical schema, **including** the non-waivable halt — returned by `canonical_schema.py`, and by `markdown_render.py` / `github_file.py --execute` when their own precondition re-check is not clean |
| 5 | external tool failure — `gh` not found or exited non-zero (`github_file.py` only) |
| 6 | unsupported `target.kind` (`github_file.py` only — it is the one script that actually acts on `kind`) |
| 8 | `schema_version` exceeds `CURRENT_SCHEMA_VERSION` — checked by every script that consumes a canonical document (see the scoping note under Versioning) |

### `canonical_schema.py`

Invoked directly by filename — there is no separate `canonical_validate` entry point, and none is
added to `pyproject.toml` (DO-NOT-CHANGE, below).

`CONTRACT:`
```
python3 skills/filing-requests/scripts/canonical_schema.py --input <path|-> [--for-emission]
```

- Preconditions: input parses as JSON and passes `check_schema_version`.
- Postconditions: stdout is always a JSON object
  `{"valid": bool, "errors": [{"path": str, "message": str}], "halted": null | {"field": str, "reason": str}}`.
  Exit `0` iff `valid == true` (and, with `--for-emission`, also `halted == null`).
- Checks performed: every `fields[]` entry obeys the provenance/sibling-key table above; every
  `verified_against[]` entry equals (or is contained in) some field's `source` value — see
  [§The "verified against" line](./logic.md#the-canonical-form-is-the-spine); `target` is well-formed.
- With `--for-emission`: additionally requires every **core** field to be *resolved* —
  `observed`/`reported` with a value, or `missing` with a `reason` — **except** the two
  non-waivable fields on a `feature` request
  (`problem`, `acceptance_criteria`), which must carry a real value; if either does not, `halted` is
  populated and the overall result is `valid: false` (exit `3`). See
  [The non-waivable gate](#the-non-waivable-gate) below for the full contract.
- Error behavior: malformed JSON or an unreadable `--input` path is exit `2`, never `3` (a `3`
  means "the JSON is well-formed but the *document* is invalid").

### `template_resolve.py`

`CONTRACT:` three subcommands, each independently invocable — split apart deliberately so the
"never pick silently" rule ([§Choosing among templates](./logic.md#choosing-among-templates)) is
structural: `fields` cannot run until `select` has returned a single, settled outcome.

```
template_resolve.py discover --repo-root <path>
template_resolve.py select --candidates <path|-> --type bug|feature|code-change
template_resolve.py fields --type bug|feature|code-change [--template <path|-> | --no-template]
```

- `discover` — globs `.github/ISSUE_TEMPLATE/*.yml`, `*.yaml`, `*.md` and
  `.gitlab/issue_templates/*.md`; excludes `config.yml` outright ([§Choosing among
  templates](./logic.md#choosing-among-templates), step 1); parses each remaining file and excludes
  any with no body sections (see Template resolution, below, for what "body sections" means per
  format); outputs
  `{"yaml_tier": "pyyaml"|"mini", "candidates": [{"path": str, "kind":
  "github-yaml"|"github-markdown"|"gitlab-markdown", "name": str|null, "labels": [str],
  "filename_stem": str}, ...]}`. **Tech-spec call (logic.md silent):** the candidate list is
  wrapped in an object rather than emitted as a bare array, because
  [The YAML tier](#the-yaml-tier-pyyaml-then-_yaml_mini) below requires `discover` to report the
  active tier "in its JSON output" and a bare array has nowhere to carry it. `select --candidates`
  accepts either shape, so the two still compose directly. A `--repo-root` that doesn't exist or isn't a directory
  is exit `2` (usage error), same as any other bad-argument case; a repo with no template
  directories at all is not an error — it's an empty candidate array, exit `0`.
  **Tech-spec call (logic.md silent):** a template file that fails to parse (violates the
  supported YAML/frontmatter subset) is excluded with a stderr warning naming the file and line —
  it does not abort discovery for the rest of the repo. `logic.md` doesn't address malformed
  templates; failing the whole session over one bad file would be a worse outcome than skipping it.
- `select` — takes `discover`'s output (already has-body-filtered) and applies step 2/3 of the
  ordered rule against the per-type keyword lists
  ([§Choosing among templates](./logic.md#choosing-among-templates)): first `name`/`labels`, and
  if that does not yield exactly one, `filename_stem`. **The stem narrows the identity matches
  rather than widening them** — it is the tie-break the ordered rule names, so two
  self-declaring templates are settled by whichever the filename also names, while a candidate
  that declared nothing never outvotes ones that did. Output
  `{"resolution": "single"|"ambiguous"|"none", "template": {...}|null, "ambiguous_candidates": [...]}`.
  All three resolutions are exit `0` — "ambiguous" and "none" are valid outcomes the caller must
  act on (ask the user; fall back to the per-type core), not error states.
- `fields` — given the final settled template (or `--no-template` for the fallback path), returns
  the ordered field set implementing the union rule (see [Template resolution](#template-resolution)
  below): `[{"name": str, "required": bool, "source": "template"|"core"}, ...]`.

### `secret_scan.py`

`CONTRACT:`
```
secret_scan.py --input <path|->
```

- Scans exactly the strings `logic.md` names as scope: every `fields[].value`, `title`,
  `proposed_solution.value`, every `verified_against[]` entry, and every `fields[].reason`
  ([§Data flow](./logic.md#data-flow): "the rule is scope-by-output: if it can appear in the
  artifact, it is scanned").
- stdout: JSON array of findings, each
  `{"path": str, "pattern": str, "match": str, "span": [int, int]}`, where `path` is the exact
  locator `logic.md` requires (`fields[2].value`, `title`) and `match` is **redacted** (first 4 +
  last 4 characters, `…` between) — never the full secret.
  **Tech-spec call (logic.md silent):** the redaction itself isn't in `logic.md`; it follows
  directly from "never fabricate/never leak" spirit of the spec — a scanner whose own stdout
  re-prints the secret it found has defeated its purpose the moment that stdout is logged.
- Exit `0` = no findings; exit `1` = findings present; exit `2` = usage/JSON error.
- `REGEX:` v1 pattern set (documented in full in `reference/guardrails.md` for the model to
  paraphrase to the user; this is the literal set `secret_scan.py` implements):
  ```
  AKIA[0-9A-Z]{16}                                    # AWS access key id
  ghp_[A-Za-z0-9]{36}                                 # GitHub PAT
  gh[oprsu]_[A-Za-z0-9]{36,}                          # GitHub OAuth/refresh/server/user token
  xox[baprs]-[A-Za-z0-9-]{10,}                        # Slack token
  eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+   # JWT
  -----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----     # private key block
  [a-zA-Z][a-zA-Z0-9+.-]{0,31}://[^/\s:]{1,256}:[^/\s@]{1,256}@   # connection string with credential
  (?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['"]?[A-Za-z0-9_\-]{16,}  # generic assignment
  ```
  Expanding this list is a script change only, never a schema change.
  **Tech-spec call (logic.md silent):** the connection-string pattern's repetitions are
  *bounded*. Unbounded `*`/`+` runs make each of the N positions `finditer` tries scan to the
  end of the input before failing, so a long alphabetic run carrying no `://` costs O(N²) and
  stalls the scan — and with it, filing. The bounds are far past any real scheme (RFC 3986
  schemes are a handful of characters) or userinfo pair, so nothing legitimate stops matching.

### `markdown_render.py`

`CONTRACT:`
```
markdown_render.py --input <path|-> [--output <path>] [--write <project-root>] [--slug <text>]
```

- Precondition: `canonical_schema.py --for-emission` on the input document reports `valid: true`.
  Refuses (exit `3`, same body shape as `canonical_schema.py`) otherwise — a halted or
  core-incomplete document is never rendered, including for the on-screen draft preview
  ([§Data flow](./logic.md#data-flow): the draft only appears "once every core field is resolved").
- `--output <path>` writes there instead of stdout. `--write <project-root>` computes the full
  artifact path per [§emission-and-auth](./logic.md#decisions-locked)
  (`docs/quirk/requests/YYYY-MM-DD-<slug>.md`, today's date, `<slug>` from `--slug` if given else
  `slugify(doc["title"])`) under `<project-root>`, writes it, and prints the resulting relative
  path to stdout, the same "compute a path, write it, print a confirmation" shape `bin/adr_create.py`
  uses (though that script confirms with an ID line, not the path itself).
  **Tech-spec call (logic.md silent):** `--slug` goes through the same `slugify` the title does,
  and an override that slugifies to nothing is exit `2`. The slug is interpolated into a path, so
  taking it verbatim lets separators and `..` segments walk out of `docs/quirk/requests/` and
  overwrite an arbitrary file — `--write` promises one new file in one directory, and a slug is
  a filename fragment, never a path. A *title* that slugifies to nothing falls back to
  `untitled` instead of erroring, since the user never chose that filename.
- Rendering rules (pure function of the document, no model in the loop, per
  [§Projection](./logic.md#the-canonical-form-is-the-spine)): `observed`/`reported` fields render plainly;
  `inferred` fields render with a fixed hedge prefix; `missing` fields render their `reason`; the
  "Verified against" section lists `verified_against[]` verbatim; empty optional sections are
  pruned entirely, never rendered as an empty heading.
- **Every top-level key has a rendering rule.** A key defined in the schema with no stated
  projection is a contract hole — the renderer is a pure function of the document, so anything the
  document carries and the renderer ignores is silently dropped from the artifact. In document
  order:

  | Key | Rendered as |
  |---|---|
  | `title` | the artifact's `#` heading, and the issue title on the GitHub path |
  | `fields[]` | body sections, per the provenance rules above, in field-set order |
  | `proposed_solution` | a `## Proposed approach` section placed **after** the problem and evidence sections, never before, prefixed with a fixed attribution line naming `attributed_to` and framing it as open rather than directed ([§Decisions Locked → tone-and-length](./logic.md#decisions-locked): the problem stays primary and the proposal is a marked suggestion). Omitted entirely when the key is absent |
  | `verified_against[]` | the "Verified against" section, verbatim |
  | `disclosure_required` | when `true`, a fixed single-line footer naming AI assistance, rendered last. When `false`, **nothing** — no footer, no placeholder ([§Decisions Locked → provenance-and-safety](./logic.md#decisions-locked): disclosure is conditional on public-or-third-party) |
  | `halted` | never rendered — a halted document fails the `--for-emission` precondition and is refused before any rendering occurs |
  | `headless` | not rendered as content; selects the banner below |
  | `template`, `target`, `schema_version`, `type`, `depth` | never rendered; they are provenance about the document, not content of the artifact |

  **Tech-spec call (logic.md silent):** the exact wording of the hedge prefix, the attribution line,
  the headless banner, and the disclosure footer is fixed in `_common.py` as four module-level
  string constants rather than being composed per call. They are asserted verbatim in tests, so a
  wording change is a deliberate edit with a failing test behind it, not drift.
- **`headless: true` renders a banner.** The artifact opens — above the title, first thing a reader
  sees — with the fixed statement that no human confirmed it ([§Data flow](./logic.md#data-flow):
  "The artifact carries a prominent statement that no human confirmed it"). The root `headless` key
  already carries this fact, so the renderer reads it rather than inferring from a heuristic like
  "every unresolved field says *no human in session*" — that inference breaks the moment a headless
  run resolves everything by inspection, which is the case it most needs to catch. `headless` is
  the one root key that is neither rendered as content nor ignored: it selects the banner.
  **Tech-spec call (logic.md silent):** the per-type terseness ceiling
  ([§Decisions Locked → tone-and-length](./logic.md#decisions-locked)) is **not** enforced by this
  script. It's a constraint on what the model writes into a field's `value` during Establish, not
  something a length-counting renderer can safely re-derive — a script can't tell "this is the
  payload, exempt from the ceiling" from "this is padding" for `steps_to_reproduce` vs. an
  optional. This is deliberately named a non-goal below so a reviewer doesn't look for a test that
  can't exist.
- **Composition contract (not itself checked by this script):** this script does **not** call
  `secret_scan.py`. `logic.md`'s own ordering has a draft rendered during Establish, before the
  scan, which runs "at emission" ([§Data flow](./logic.md#data-flow)). The caller (`SKILL.md`) is
  responsible for sequencing: render for preview any time core-complete; only call `--write` after
  `secret_scan.py` reports clean.

### `drift_apply.py`

`CONTRACT:`
```
drift_apply.py --input <path|-> --to bug|feature [--output <path>]
```

- Preconditions: input passes `canonical_schema.py` **without** `--for-emission` (structural
  validity only — drift can fire mid-session before core fields are resolved); `--to` differs from
  the document's current `type` (exit `2`, "already this type", otherwise).
  **Tech-spec call (logic.md silent):** `--to code-change` is not implemented. `logic.md`'s drift
  tables and every drift scenario name only `bug ↔ feature`
  ([§Data flow](./logic.md#data-flow)); `code-change` never appears as a drift source or
  destination anywhere in the spec. Rather than inventing a symmetric table nothing calls for,
  `--to code-change` exits `2` with "drift to code-change is not defined; start a fresh session."
- Applies the two mapping tables below (see [Drift carry-over](#drift-carry-over)) in table order,
  identity mappings first, so a later append lands on top of the identity-mapped value rather than
  racing it.
- Postcondition: every field from the source type is accounted for — mapped per the table, or
  retained as an optional field under its original name if the table has no row for it
  ([§Data flow](./logic.md#data-flow): "nothing the user supplied is ever discarded on drift").
  **This holds when two of them collide.** Two source entries can land on one destination — an
  `environment → constraints` rename onto a document that already carries `constraints`, or two
  entries that simply share a name — and the second must merge, never overwrite. Overwriting is
  how a field gets discarded, and "nothing is ever discarded" admits no exception for collisions
  the tables didn't anticipate. A merge with no `lead_in` of its own uses
  `Also supplied for <name>:`.
- Postcondition: a `halted` key on the input is **dropped**, not carried. The halt was computed
  against the source type's field set and may name a field the destination type does not have;
  carried over, it would block the drifted document permanently, and since `--for-emission` now
  honors a stored halt (see [The non-waivable gate](#the-non-waivable-gate)) there would be no
  way past it. Drift is itself the "keep working on it" exit from a halt — re-deriving is the
  point.
- Postcondition: `template.fields` is carried across the same mapping the values took, whenever
  the document already has one. Left behind, the union the emission gate reads still describes
  the *source* type: `--for-emission` reports the source type's fields missing and never enforces
  the destination type's own required set — on a `feature`, the non-waivable gate would check the
  bug's field list and pass a request with no `acceptance_criteria`. The rebuild applies
  [The union-of-requiredness rule](#the-union-of-requiredness-rule) to the new type: mapped
  entries keep their `source` and the template's ordering, requiredness unions when two entries
  collapse onto one name (`demote_optional` contributes `required: false`), the destination
  core is additive, and the non-waivable pair is forced `required: true`. An **absent or empty**
  `template.fields` is left alone — template resolution has not settled, and synthesizing a union
  here would manufacture the exact silent fallback the key exists to prevent.
  **Tech-spec call (logic.md silent):** an `append_or_become` row appends **only when the merge
  keeps both provenance claims true** — that is, when the incoming field has content and its
  provenance *equals* the destination's (`observed` > `reported` > `inferred` > `missing`).
  Otherwise the incoming field is retained under its *own* name instead, exactly as an unmapped
  field would be. When two `observed` fields do merge, their `source` values are unioned, since
  `verified_against` entries are matched against field sources and keeping only one would strand
  the other's citation.

  Equality, not "at least as strong", is the condition — a stronger incoming understates its own
  claim harmlessly, but the merged field has one `source` slot, so the incoming's citation would
  be dropped and every `verified_against` entry naming it would fail validation.

  Two locked rules collide here. The carry-over tables say `problem` appends onto
  `current_behavior`; [§Data flow](./logic.md#data-flow) says "every carried field keeps the
  provenance it already had". A field has one provenance slot, so appending `reported` content
  into an `observed` field asserts the appended claim was verified, and appending a `missing`
  field discards its `reason` outright — and that reason is the diagnostic content
  [§Data flow](./logic.md#data-flow) specifically defends ("maintainers prefer an honest
  'intermittent, no reliable trigger'"). Provenance wins the collision: it is the invariant the
  renderer enforces, whereas the destination name is a mapping the caller can still see. Nothing
  is discarded either way — the content simply keeps its own section.

  Downgrading the merged field's provenance instead was considered and rejected: dropping
  `source` from a demoted `observed` field strands every `verified_against` entry that cited it,
  so the drift would produce a structurally invalid document.

### `github_file.py`

`CONTRACT:`
```
github_file.py --input <path|-> --repo <owner/repo> [--execute]
```

- Reads `GH_BIN` env var for the `gh` executable path, default `"gh"`.
  **Tech-spec call (logic.md silent):** this override exists purely for testability — it lets
  `test_filing_github_file.py` point `GH_BIN` at a repo-local stub that just echoes its argv, so
  `--execute` is exercised with no real network or `gh` install required in CI.
- **`--repo` must equal `doc["target"]["repo"]`** (exit `2` otherwise). The body's disclosure
  footer is derived from *this document's* `target`, so filing it at some other repository can
  send a disclosure-free body to a public or third-party tracker. The document names its own
  destination; `--repo` restates it, and a disagreement is the caller pointing at something the
  document was not prepared for, not a destination to honor.
- **Defense in depth:** this script itself re-runs
  `canonical_schema.validate(doc, for_emission=True)` and, under `--execute`, `secret_scan.scan(doc)`
  — it does not trust that the caller already gated on both. Exit `3` (validation) or `1` (secrets
  found) if either fails, and `gh` is never invoked. **The validation runs before rendering, and
  it gates the dry run too**: `markdown_render.render()` assumes a validated document and indexes
  keys directly, so rendering first turns a structural error into a `KeyError` traceback instead
  of the exit `3` this table promises — and `markdown_render.py`'s own contract refuses a halted
  or core-incomplete document "including for the on-screen draft preview", which is exactly what
  the dry run is. The same re-check also refuses `--execute` (exit `3`)
  when `doc["headless"] == true`: [§session-economics](./logic.md#decisions-locked) says headless
  output "is never filed to a tracker automatically," and that guarantee should not rest solely on
  `SKILL.md` never reaching the confirmation step in a headless run — the script that performs the
  irreversible action enforces it too.
  **Tech-spec call (logic.md silent):** `logic.md` calls filing "outward-facing and effectively
  irreversible" ([§Key decisions → the file is unconditional](./logic.md#key-decisions--rationale));
  that's the reasoning for making the last script before an irreversible action defensive rather
  than trusting upstream sequencing, for both the validation/secret gates and the headless gate.
- Without `--execute`: dry run. stdout is
  `{"repo": str, "title": str, "body_preview": str, "would_execute": [str, ...]}` — the literal
  argv `github_file.py` would exec, so the caller can display it verbatim for the "separate
  confirmation that displays the exact body and destination"
  ([§Data flow](./logic.md#data-flow)). Exit `0`.
- With `--execute`:
  ```
  COMMAND:
  gh issue create --repo <repo> --title <title> --body <body>
  ```
  On `gh` exit `0`: stdout is `gh`'s own stdout (the issue URL), exit `0`. On `gh` exiting non-zero
  or `GH_BIN` not found: stderr carries the captured message, exit `5`.
- `target.kind != "github"` is exit `6` before anything else runs — [§Multi-target
  emission](./logic.md#scope--non-goals) is out of scope, and this is the one script that would
  otherwise silently no-op against an unsupported target.

---

## Template resolution

*Back-link: [logic.md → Choosing among templates](./logic.md#choosing-among-templates),
[logic.md → Required sections in a template](./logic.md#required-sections-in-a-template)*

### The YAML tier (PyYAML, then `_yaml_mini`)

**Tech-spec call (logic.md silent):** GitHub's YAML issue-form schema and a markdown template's
frontmatter block both need YAML parsing, and quirk may not *require* a third-party library
(Architecture, above). Parsing therefore runs in two tiers, resolved once at import time in
`_yaml_mini.py` and exposed as a single `parse_yaml(text, path)` entry point so no caller knows
which tier served it:

1. **PyYAML when importable.** `try: import yaml` / `except ImportError`. When present it parses,
   because a maintained implementation beats a hand-rolled subset on every input that matters.
   `yaml.safe_load` only — never `yaml.load`, which can construct arbitrary objects from a file the
   skill did not write.
2. **`_yaml_mini` otherwise.** The bounded subset below, sufficient for the documented Issue Forms
   schema and simple frontmatter.

Both tiers raise `TemplateParseError` on input they cannot handle, so callers see one failure mode.
`template_resolve.py discover` reports which tier is active in its JSON output (`"yaml_tier":
"pyyaml" | "mini"`), because a template that resolves on a machine with PyYAML and is skipped on one
without is otherwise a silent, environment-dependent difference in what the skill asks the user —
and that is exactly the kind of divergence this document exists to prevent. The degradation is
bounded and already specified: a template that fails to parse is excluded per-file, and if no
candidate survives, resolution falls back to the per-type core with `template.applied: false`
([logic.md → Choosing among templates](./logic.md#choosing-among-templates)).

**Testing consequence:** the `_yaml_mini` tier must be exercised directly rather than through
`parse_yaml`, or it goes untested on any machine that happens to have PyYAML installed — including
CI. See [Testing strategy](#testing-strategy).

`_yaml_mini` implements exactly this subset — enough for the documented GitHub Issue Forms schema
and simple frontmatter, no more:

`PSEUDOCODE (justified, ≤3 lines):` supported: block mappings (`key: value`, nested via
indentation), block sequences (`- item`, including `- key: value` list items), plain/single/double-
quoted scalars, booleans, `|`/`>` block scalars, `#` comments, **and flow sequences whose items are
all scalars** (`[a, "b", c]`, including the empty `[]`). **Not** supported: flow mappings (`{...}`),
flow sequences containing a nested collection, anchors/aliases, multi-document `---`/`...`
separators, tags, merge keys — a file using any of these raises `TemplateParseError` naming the file
and line, which `discover` (above) catches per-file rather than propagating.

**Tech-spec call (logic.md silent):** two bounds keep that per-file guarantee honest, because
`discover` can only catch what arrives as a `TemplateParseError`.

- **Nesting is bounded** (64 levels, far past anything a real issue form uses) and both tiers
  additionally catch `RecursionError`. Otherwise a deeply nested file raises `RecursionError` out
  of `parse` and aborts discovery for the whole repo — the exact all-or-nothing failure the
  per-file exclusion rule exists to prevent.
- **Double-quoted escapes are decoded in full, and an unknown escape is rejected** rather than
  having its backslash silently dropped. The two tiers must never disagree about the *content* of
  a template ID or field name: PyYAML decodes `"_"` to `_`, and a tier that yields `u005f`
  produces a different field set on a machine without PyYAML, which is precisely the
  environment-dependent divergence `yaml_tier` reporting exists to make visible.

**Why scalar flow sequences are in the subset.** GitHub's documented Issue Forms schema declares
labels as `labels: ["bug", "needs-triage"]`, and that flow form is what real templates use — a
sample of issue-form templates on a working machine found the flow form in every one, with the
block form in none. Excluding it would mean the fallback tier rejects essentially every real GitHub
Issue Form, so `discover` drops them all, `select` returns `"none"`, and template conformance
silently degrades to the per-type core on exactly the machines the fallback exists to serve. Since
`select` also matches on `labels`, losing them degrades selection even for a template that
otherwise survived. The subset is widened by the narrowest thing that fixes this — scalar items
only — rather than by general flow-collection support, which would reintroduce the unbounded
parser this tier is deliberately not.

`SCHEMA:` a parsed YAML form: `{"name": str, "description": str, "labels": [str],
"body": [{"type": str, "id": str|null, "attributes": {...}, "validations": {"required": bool}}]}`.
`type: "markdown"` elements are static instructions, never candidate fields — `fields`
(`template_resolve.py`) skips them, and they don't count toward "has body sections" (below).
Checkboxes' per-option `required` is not modeled; a checkboxes block is one field gated by its own
block-level `validations.required` only.
**Tech-spec call (logic.md silent):** `logic.md` doesn't go to per-option granularity; modeling it
would add a schema dimension nothing in the spec asks for.

### "Has body sections" (the step-1 exclusion filter)

`logic.md` excludes `config.yml` and "any file whose parsed form has no body sections"
([§Choosing among templates](./logic.md#choosing-among-templates)). Operationalized: a YAML form
has body sections iff at least one `body[]` element has `type != "markdown"`; a markdown template
has body sections iff it contains at least one `##`-or-deeper heading.
**Tech-spec call (logic.md silent):** heading *depth* (`##` vs `###`) is not modeled as nesting — a
field set is a flat list, so every heading at `##` or deeper becomes one flat section boundary. A
markdown template's own leading frontmatter (`name:`/`labels:`/`about:`) is parsed via the same
mapping-parsing routine in `_yaml_mini.py` and supplies the `name`/`labels` step-2 classifies
against, exactly as a YAML form's top-level `name`/`labels` do.

### Field-name mapping (template → canonical `fields[].name`)

Both template kinds produce canonical field names, and the union-of-requiredness rule below cannot
run without them — it has to compare a template's field set against the per-type core, which means
both sides must be in the same namespace. The rule is stated per kind rather than left to be
composed from the section-boundary rule and the slug convention:

**YAML form.** A body element's canonical field name is its `id` when present, else
`slugify(attributes.label, sep="_")`.

**Markdown template.** Each `##`-or-deeper heading is one section boundary (above), and its
canonical field name is `slugify(<heading text>, sep="_")` — the heading text with any leading
markdown markers and trailing punctuation stripped. The section's content is everything up to the
next heading at any depth. A heading inside a fenced code block (` ``` ` or `~~~`) is **not** a
section boundary: a template showing example output or a traceback is displaying text, and
treating it as a declaration injects a field the maintainer never asked for into the interview.

**Two template sections whose names slug alike are still two sections**, in either kind. The
second and subsequent get a `_2`, `_3` suffix rather than collapsing onto the first — a template
asking for a client version and a server version under separate parents is asking twice, and
merging them by name drops the maintainer's second question. This applies only to
*template-internal* duplicates; a template name that collides with a **core** name is the same
field, which is exactly what the snake_case convention exists to make recognizable.

Both produce snake_case, matching the per-type core naming convention — `current_behavior`, not
`current-behavior` — which is what lets a template-derived name collide with a core name and be
recognized as the same field rather than added twice.

**Tech-spec call (logic.md silent):** heading text is matched against core names after slugging,
case-insensitively, with a small fixed synonym table in `_common.py` (`steps to reproduce` →
`steps_to_reproduce`, `expected behaviour`/`expected behavior` → `expected_behavior`, `actual
behaviour`/`actual behavior` → `current_behavior`). Without it, a template heading of "Steps To
Reproduce" produces `steps_to_reproduce` and matches, but "Expected behaviour" produces
`expected_behaviour` and silently becomes a *second* field alongside the core's
`expected_behavior` — asking the user the same question twice and rendering two near-identical
sections. The table is deliberately small and closed; an unmatched heading becomes its own
template-supplied field, which is the correct outcome for a genuinely novel section.

### The union-of-requiredness rule

`template_resolve.py fields` implements [§Required sections in a
template](./logic.md#required-sections-in-a-template)'s three ordered rules, identically for YAML
and markdown:

1. The template's sections, in its own order, seed the field list.
2. `required: true` comes from a YAML form's `validations.required`, read **strictly** — the key
   must be the YAML boolean `true`. Anything else (a quoted `"false"`, a number, a missing
   `validations` block) is not a requiredness marking, because truthiness-coercing a
   schema-invalid value would have the template add a requirement it explicitly declined to add,
   inverting rule 2's own direction. A markdown template contributes **no** requiredness markings
   (it has no mechanism to). In both cases the per-type core is additive: any core field the
   template's section list omits is appended, in core order, after the template's own sections,
   marked `required: true`.
3. The non-waivable gate is global and cannot be unset by a template of either kind: on a `feature`
   request, `problem` and `acceptance_criteria` are forced `required: true` in the output
   regardless of what the template declared or omitted.

---

## Drift carry-over

*Back-link: [logic.md → Data flow](./logic.md#data-flow) (the two mapping tables)*

`SCHEMA:` bug → feature (applied in this order — identity mappings first, so an append lands on an
already-settled value, not a race):

```yaml
- from: current_behavior
  to: current_behavior
  mode: identity
- from: steps_to_reproduce
  to: current_behavior
  mode: append_or_become        # append if current_behavior already has content, else becomes it
  lead_in: "Steps to reproduce (from the original bug report):"
- from: expected_behavior
  to: acceptance_criteria
  mode: rename_reopen           # provenance carries over; needs_confirmation: true is set
- from: environment
  to: constraints
  mode: identity_rename
```

`SCHEMA:` feature → bug (same ordering rule):

```yaml
- from: current_behavior
  to: current_behavior
  mode: identity
- from: problem
  to: current_behavior
  mode: append_or_become
  lead_in: "Problem statement (from the original feature request):"
- from: acceptance_criteria
  to: expected_behavior
  mode: identity_rename
- from: who_benefits
  to: affected_users
  mode: demote_optional          # dropped from the core; retained as an optional field
```

Any field with no row in the applicable table is retained as an optional field under its original
name, rendered after the new type's sections
([§Data flow](./logic.md#data-flow)). `lead_in` text is embedded directly in the appended `value`
string by `drift_apply.py` — it is not a separate schema key, since it only ever exists inline in
the rendered content the append produces.

---

## The non-waivable gate

*Back-link: [logic.md → Data flow](./logic.md#data-flow) (non-waivable fields),
[logic.md → Decisions Locked → artifact-structure](./logic.md#decisions-locked)*

- **Enforced in:** `canonical_schema.py`'s `--for-emission` check, exclusively. No other script
  re-derives this rule; `markdown_render.py` and `github_file.py` both depend on
  `canonical_schema.py --for-emission` having already passed (see their contracts above).
- **Represented in the canonical form as:** the top-level `halted` key
  (`{"field": "acceptance_criteria", "reason": "no testable pass/fail condition established"}`).
  Its absence means "not halted" — there is no separate boolean, so there is exactly one way to
  check, not two that could disagree.
- **Surfaced to the caller as:** `canonical_schema.py --for-emission`'s stdout `halted` object plus
  exit `3`. `SKILL.md` reads this and offers the two honest exits `logic.md` names — keep working
  now, or save the partial canonical form (a raw JSON write; no script is needed for this, since
  the document is already valid JSON and the resume case doesn't call for markdown rendering).
- Which fields are non-waivable is fixed, not configurable: `problem` and `acceptance_criteria`,
  and only on `type == "feature"`. A `bug`/`code-change` document can resolve every core field via
  `missing` + `reason`; `--for-emission` never sets `halted` for those two types *on field
  grounds* — see the headless rule below, which halts a `feature` regardless of field state.
- **A `halted` key already on the document is honored, not recomputed away.** The gate's own
  output is what `SKILL.md` saves when the user takes the "save the partial canonical form" exit,
  so a resumed document arrives carrying it. Recomputing from scratch and reporting
  `halted: null` would let that document walk straight past the block it was saved under —
  "absence means not halted" only holds if a present one still means halted.
- **A headless `feature` request halts, whatever its fields say.**
  [§Data flow](./logic.md#data-flow) states this outright: "A headless feature request halts with
  the same non-waivable message rather than emitting a hollow artifact." The gate cannot reach
  that outcome field-by-field, because a document can arrive with `problem` and
  `acceptance_criteria` populated and `headless: true` — resolved by something other than a human
  in session, which is exactly the hollow artifact the rule exists to refuse. The check is
  therefore on the type, not the fields.
- **An `observed` field obliges a non-empty `verified_against`.**
  [§The canonical form is the spine](./logic.md#the-canonical-form-is-the-spine) locks the
  "verified against" line as "assembled from `observed` sources, not written freehand", and
  [§Decisions Locked](./logic.md#decisions-locked) requires it to name "what was actually
  checked". The existing per-entry check runs one way only — every entry must cite some field's
  `source` — so a document with observed claims and an empty list passed, shipping verified
  assertions with nothing naming the verification. The reverse check is deliberately coarse
  (non-empty, not per-source matching): a `source` is free text that may name several artifacts in
  one string, and a stricter comparison would fail on formatting rather than on substance.

---

## DO-NOT-CHANGE fences

*Back-link: [logic.md → The skill inspects the code, not the tracker](./logic.md#key-decisions--rationale)*

| Region | Why fenced |
|---|---|
| `tests/conftest.py`'s existing fixtures (`project_dir`, `initialized_project`, `run_script`, `BIN_DIR`) | Load-bearing for the typed-artifacts suite; this work adds a parallel helper (see Testing strategy) rather than repurposing these |
| `pyproject.toml`'s `pythonpath = ["bin"]` | Adding `skills/filing-requests/scripts` here would make its modules importable bare repo-wide, risking a name collision with any future skill's same-named script; the testing strategy below uses `importlib` file-path loading instead, precisely so this line never needs to change |
| `.claude-plugin/plugin.json` | Verified directly — it carries no skill enumeration, only package metadata; a new skill under `skills/` needs no entry here |
| Every other existing skill under `skills/` | This is purely additive work; nothing here reads or writes another skill's files |
| `docs/quirk/requests/` | New directory this skill owns exclusively; no existing content lives there to protect, but nothing outside this skill should write to it |

## Always / Ask / Never

*Back-link: [logic.md → Provenance is structural, not stylistic](./logic.md#key-decisions--rationale)*

**Always**

- Check `schema_version` first, in every script that consumes a canonical document, via the shared
  `_common.check_schema_version` (`template_resolve.py`'s three subcommands operate on template
  files and candidate lists, never a canonical document, so this doesn't apply to them — see the
  scoping note under Versioning).
- Gate `markdown_render.py` and `github_file.py` on `canonical_schema.py --for-emission` passing —
  never render or file an unresolved or halted document.
- Redact a matched secret before it appears in `secret_scan.py`'s own stdout.
- Derive `disclosure_required` from `target` at finalize time; never trust a stored value.

**Ask** (escalate to the human via `SKILL.md`, not resolved unilaterally by a script)

- An ambiguous template resolution (`select` returns `"ambiguous"`).
- Any conflict between this tech spec and a `logic.md` Decisions Locked entry discovered during
  implementation — amend `logic.md`'s Amendments log first, per the `writing-tech-spec` rubric's
  own feasibility-escalation rule, before changing this document.

**Never**

- Add a *required* third-party dependency. PyYAML is used opportunistically when importable and
  must never become a hard requirement; `_yaml_mini` is the guarantee that the skill works without
  it, not a placeholder to be deleted once PyYAML is "available."
- Call `yaml.load`. The PyYAML tier is `safe_load` only — issue templates are files the skill did
  not author.
- Let `github_file.py`'s issue body diverge from what `markdown_render.py` would produce for the
  same document — the filed issue and the written artifact are the same rendering, never two
  independently-formatted copies.
- Widen `drift_apply.py` to a type it isn't defined for (`code-change`) without first amending
  `logic.md`.

---

## Cross-cutting

*Back-link: [logic.md → Credential custody](./logic.md#scope--non-goals),
[logic.md → provenance-and-safety](./logic.md#decisions-locked)*

**Security.** No script prompts for, stores, or transmits a credential — `gh` auth is entirely
delegated to an already-authenticated CLI, matching
[§emission-and-auth](./logic.md#decisions-locked). `secret_scan.py`'s pattern list (above) is a v1
starter set; growing it is a script change, never a schema change. `github_file.py`'s
defense-in-depth re-check (Contracts, above) is the load-bearing security property of the whole
script set: it is the one script that performs an irreversible outward action, so it is the one
that does not trust its caller.

**Observability.** The "verified against" line is assembled from `observed` sources and validated
by `canonical_schema.py`, not written freehand — this is the entire observability story for v1.
Optional local persistence of the session trail is explicitly deferred
([§Deferred to later versions](./logic.md#deferred-to-later-versions)) and out of scope for these
scripts.

**Data migration.** Covered under Versioning, above — `schema_version` plus a forward-compat guard,
no migration path yet since there is only one version.

**Rollback.** The markdown artifact write is additive (a new file under `docs/quirk/requests/`);
nothing here mutates an existing file. `gh issue create` has no scripted rollback — this is exactly
why filing requires a separate explicit confirmation on top of the unconditional markdown write
([§The file is unconditional; the filing is not](./logic.md#key-decisions--rationale)).

---

## Testing strategy

*Back-link: [logic.md → Deterministic work goes in Python](./logic.md#key-decisions--rationale),
[logic.md → In scope for v1](./logic.md#in-scope-for-v1) (pytest coverage of the deterministic layers)*

### Test infrastructure

**Tech-spec call (logic.md silent):** rather than expanding `pyproject.toml`'s `pythonpath` (fenced
above), `tests/conftest.py` gains one addition:

`CONTRACT:`
```
FILING_SCRIPTS_DIR = REPO_ROOT / "skills" / "filing-requests" / "scripts"

def load_filing_module(name: str) -> ModuleType:
    """Load a skills/filing-requests/scripts/<name>.py module by path, without touching sys.path."""

def run_filing_script(script_name: str, *args: str, cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess:
    """Invoke a skills/filing-requests/scripts/<name>.py in a child process."""
```

`load_filing_module` uses `importlib.util.spec_from_file_location` — function-level tests (pure
logic: rendering rules, drift table application, provenance validation) import and call directly;
`run_filing_script` mirrors the existing `run_script` helper (`tests/conftest.py:34-41`) for
CLI-contract tests (argv parsing, exit codes, stdin/stdout shape).

### Per-script coverage (fixture JSON in, expected output asserted — no model in any of these)

- **`test_filing_canonical_schema.py`** — every provenance/sibling-key rule in the table above (a
  fixture per violation: `observed` missing `source`, `missing` carrying a `value`, `polarity` on a
  non-`observed` field); the `verified_against`-must-cite-a-`source` cross-check; the
  `schema_version`-too-new guard (exit `8`); the non-waivable halt on a `feature` fixture missing
  `acceptance_criteria`, and its **absence** on an equivalent `bug` fixture missing
  `steps_to_reproduce` (that one resolves via `missing` + `reason`, no halt).
- **`test_filing_template_resolve.py`** — `discover` excludes `config.yml` and a bodiless fixture
  file; classification by `name`/`labels`/`filename_stem` for all three types; `select` returns each
  of `single`/`ambiguous`/`none` for constructed candidate sets; `fields` proves the union rule
  (template adds a field the core doesn't have; core adds a field the template omits; non-waivable
  override fires even when a YAML form's `validations.required: false` says otherwise); a handful
  of representative `_yaml_mini` fixtures (nested mapping, block sequence, `|` block scalar,
  quoted scalar) plus one fixture per unsupported construct proving `TemplateParseError` fires and
  `discover` excludes that file rather than aborting.

  **The `_yaml_mini` cases must call `_yaml_mini.parse()` directly, never `parse_yaml()`.** Going
  through the tier-resolving entry point means those assertions silently exercise PyYAML on any
  machine that has it — including CI — and the fallback tier ships untested precisely where it is
  the only tier. One further test asserts tier selection itself: with `yaml` forced unimportable
  (`monkeypatch.setitem(sys.modules, "yaml", None)` and a module reload), `parse_yaml` resolves to
  the mini tier and `discover` reports `"yaml_tier": "mini"`. Parity is checked on the shared
  subset: the representative fixtures above are asserted to produce the same parsed structure under
  both tiers when PyYAML is importable, and skipped when it is not.
- **`test_filing_secret_scan.py`** — one positive fixture per `REGEX:` pattern above, one
  similar-but-benign negative fixture per pattern (false-positive guard), path-labeling correctness
  (`fields[2].value` vs. `title` vs. `verified_against[0]`), and that the redacted `match` in
  output never contains the full secret.
- **`test_filing_markdown_render.py`** — one fixture per provenance rendering rule (plain, hedged,
  missing-with-reason); empty optional sections pruned from output; refusal (exit `3`) on a
  core-incomplete or halted input; `--write` computing the exact
  `docs/quirk/requests/YYYY-MM-DD-<slug>.md` path.
- **`test_filing_drift_apply.py`** — both directions end-to-end on worked fixtures; the
  collision/append ordering fixture (two source fields landing on one destination, later row
  appends rather than overwrites); `needs_confirmation` set only on the
  `expected_behavior → acceptance_criteria` mapping; an unmapped field retained as an optional
  under its original name; `--to code-change` exiting `2`.
- **`test_filing_github_file.py`** — dry-run mode asserts the exact `would_execute` argv against a
  fixture, no network or `gh` needed; `--execute` against a `GH_BIN`-stubbed fake `gh` (a fixture
  script that echoes its argv) proving the command shape and exit-code passthrough; the
  defense-in-depth re-check refusing `--execute` on a fixture with an unresolved secret finding and
  on a `headless: true` fixture, in both cases without ever invoking the stub.
- **`test_filing_skill.py`** — frontmatter validity (mirrors `tests/test_skill.py`): `name:
  filing-requests`; the description contains trigger phrases disambiguating from `brainstorming`
  ("file", "report", "bug", "feature request" — *not* "build"/"implement", which are
  `brainstorming`'s triggers, per [§It is a sibling of
  brainstorming](./logic.md#key-decisions--rationale)).

### Session-only behaviors (not script-provable — exercisable only through a live session, or an
eval-style scripted transcript, never a pytest fixture)

- Orient's type inference and the combined type+depth confirmation question's wording.
- Every non-fileable judgment call (config error / already fixed / already exists / previously
  rejected / support question) — each requires live repo inspection plus model judgment about what
  it means, not just a pattern match.
- Establish's per-field inspect-then-ask sequencing, and the *decision* to surface a contradiction
  or offer a type-drift switch (the mechanical *application* of an already-decided drift mapping is
  `drift_apply.py`'s job and is script-provable; deciding *whether* to offer the switch is not).
- The headless narrative ("no human confirmed it") and the two-honest-exits prompt on a halt — the
  halt *detection* is script-provable (above); the surrounding prose is not.
- User confirmation gates themselves (secret-finding acknowledgment, the final filing confirmation)
  — the scripts enforce the preconditions; the asking is `SKILL.md` prose.

The acceptance bar: every script-provable behavior above has a passing fixture test, and every
session-only behavior is named here rather than silently assumed covered.

---

## Non-goals

*Back-link: [logic.md → Scope & non-goals](./logic.md#scope--non-goals)*

- Not specifying `SKILL.md`'s prose, section order, or exact interview question wording — that's
  the implementer's call against `logic.md`'s three-stage protocol. `reference/field-catalogs.md`'s
  question wording is likewise implementer-authored.
- Not enforcing the per-type terseness ceiling mechanically — see the call-out under
  `markdown_render.py`, above.
- Not implementing GitLab or Jira projection, or `--to code-change` drift — both deferred/out of
  scope per `logic.md`, and not stubbed here.
- Not touching `pyproject.toml`, `.claude-plugin/plugin.json`, or any existing skill — see
  DO-NOT-CHANGE fences.
- Not specifying a duplicate-detection mechanism of any kind — `logic.md` rules this out entirely
  ([§Explicit non-goals](./logic.md#scope--non-goals)).

## Traceability

| Section | logic.md anchor |
|---|---|
| Canonical JSON schema | The canonical form is the spine; Negative observation |
| Contracts & interfaces | Deterministic work goes in Python |
| Template resolution | Choosing among templates; Required sections in a template |
| Drift carry-over | Data flow (mapping tables) |
| The non-waivable gate | Data flow (non-waivable fields); Decisions Locked → artifact-structure |
| Cross-cutting | Credential custody; provenance-and-safety |
| Testing strategy | In scope for v1 (pytest coverage of the deterministic layers) |
| Non-goals | Scope & non-goals |
