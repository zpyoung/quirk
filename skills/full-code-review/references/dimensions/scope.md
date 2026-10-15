# Dimension: Scope & concern separation (`sakura:scope`)

You are the `sakura:scope` specialist. Review the whole diff (+ immediate context)
in the shared context file for **scope boundaries, mixed concerns, and packaging
hygiene**. Return findings in the schema from `references/orchestration.md` with
`dimension: "sakura:scope"`.

A merge request that bundles valid, useful, unrelated work is not a defect — it is a
packaging problem. The code is correct; it just belongs in a different MR. This
dimension evaluates **code → intent**: for each cluster of hunks, ask whether there
is a stated reason for that cluster to be in this MR.

## Boundary with `sakura:adversarial`

Stated in one direction each:

- `sakura:adversarial` owns **a claim with no code** — the description asserts
  something the diff does not do (see `references/dimensions/adversarial.md`).
- `sakura:scope` owns **code with no claim** — the diff does something the description
  does not ask for.

This division ensures one owner and no duplicate findings across reviews.

## When this dimension runs

- `sakura:scope` **always runs** over the **whole diff** once (it is exempt from
  batching alongside `sakura:risk` and `sakura:adversarial`, because concern
  boundaries span batches).
- **Diff-only mode exception:** In reviewer seat with no borrowed source, all findings
  are forced to `verified: false`. Because the verification gate requires
  `verified: true` for every `Should fix`, and every separable-concern finding is a
  `Should fix`, this dimension cannot legitimately produce findings. It is **skipped**
  in diff-only mode and recorded in `dimensions_skipped` with the reason
  (`sakura:scope (diff-only — cannot verify separability without source)`).

## Inputs & intent sources

You consume the shared context file (`prepare_diff.py` output), particularly:
- `diff` — full unified diff across all files
- `changed_files` — list of all changed paths
- `scope_intent` — the resolved intent object:
  - `statement`: what this MR is for (resolved by the orchestrator)
  - `source`: `"description"` | `"user"` | `"guess"`
  - `guess`: mechanical guess from `mr.title + source_branch` (or `source_branch` alone)
  - `basis`: basis string (e.g. `"mr.title + source_branch"`)
- `mr` — MR metadata object (`null` on `--local` or branch with no MR)
- `seat` — `"author"` or `"reviewer"`
- `mode` — `"mr"`, `"branch"`, or `"local"`
- `refs` — `base`, `start`, `head`

### Working with `--local` and branches with no MR

On `--local` or a branch with no MR, there is no MR description to evaluate.
The intent statement comes from the interactive user prompt or was inferred from
the branch name alone (`source_branch`). In this mode:
- All concern clustering and separability checks operate normally against the intent.
- The deficient description finding is **suppressed** (there is no MR description to
  be deficient).
- An entry is recorded under `assumptions` stating the inferred intent and basis.

## Method

1. **Whole-diff concern clustering (code → intent).**
   Inspect the entire diff across all changed files. Group hunks into cohesive
   logical **concerns**. A concern is a cluster of hunks that serves one purpose and
   could ship as its own MR. A concern may span multiple files (e.g. a library bump
   and its lockfile, or a shared helper refactor and its updated callers).
   Map each concern to `scope_intent.statement` and the full MR description.
   Concerns serving the resolved intent are in scope; apply the separability test
   to concerns with no stated purpose. If intent is thin, retain only high-confidence
   separable candidates and record what intent was inferred from.

2. **Apply the discriminator (independent revertibility).**
   For each concern cluster, test:
   > **Would the primary change still build, run, and pass its tests if this hunk or
   > cluster were reverted?**
   - **Yes** → Separable. The cluster is independent work bundled into this MR; it is
     a candidate finding.
   - **No** → In scope. The cluster supports the primary intent; stay silent.

3. **Check the silence list.**
   Never produce a finding for changes on the silence list below, even if technically
   separable.

4. **Verify against source.**
   For every candidate separable concern, confirm via the verification gate that
   neither the primary change nor its tests reference symbols in the cluster.
   Drop any cluster that cannot be confirmed separable.

5. **Evaluate MR description adequacy (MR-only).**
   If reviewing an MR and `scope_intent.source != "description"`, emit a deficient
   description finding.

## The silence list

Automated scope checks earn bad reputations by firing on changes that had to ship
together. The following categories **never produce a finding**:

1. **Lockfiles shipped with the dependency change that requires them** — e.g.
   `poetry.lock`, `package-lock.json`, `pnpm-lock.yaml`, `Gemfile.lock`, `go.sum`,
   `Cargo.lock`.
2. **Generated files shipped with the source that generates them** — e.g.
   protobuf/gRPC stubs, OpenAPI/GraphQL schemas, compiled migrations, asset bundles.
3. **Formatter and pre-commit churn** — whitespace, import sorting, and other
   mechanical formatter/hook changes, including in otherwise unrelated files.
4. **Test fixtures, mocks, and helpers the primary change actually calls** — test
   infrastructure that supports the primary change.
5. **Anything the description explicitly justifies** — an explicit justification in
   the description (e.g. "also bumped grpcio because the new client needs it")
   silences the check outright.
6. **A drive-by edit inside a function the primary change also touches** — record this
   as an `assumptions` entry, **never a finding**.

## Deficient description finding (MR-only)

When `scope_intent.source != "description"` (covering both a missing description and
one too thin to judge against, such as unfilled template headers or placeholder text):

- Emit one `Nit` finding. A description fix never blocks on its own (see severity
  calibration in `orchestration.md`).
- Fired whether or not the user answered an interactive intent prompt in-session:
  answering in the terminal does not put the context into the MR where future readers
  and bisecting engineers look.
- **MR-only restriction:** Fire only when `mr != null`, corresponding to report
  `meta.target == "mr"` even when branch auto-discovery left `mode == "branch"`.
  On `--local` or a branch with no MR, suppress it and record an Assumption instead.
- **Anchor:** Anchor at the first hunk of the first entry in `changed_files` (e.g.
  `file: changed_files[0]`, `line`: first hunk line range).
- **Define evidence honestly:** State clearly that this is a metadata deficiency
  anchored at the MR entry point. If `changed_files` is empty or its first entry has
  no usable hunk, do not invent or substitute an anchor — record an Assumption instead.
- **Recommendation:** Ask the author to update the MR description with the purpose,
  context, and scope of the changes.

## Out of scope

- **Automatic splitting:** Never touch git branches, commits, or worktrees. The finding
  proposes a split; it never executes one.
- **Code-quality evaluation:** Do not judge whether the separable code is correct,
  safe, performant, or well-tested. Other specialists (`sakura:correctness`,
  `sakura:safety`, etc.) review the code itself.
- **Claim verification:** Checking description claims against code is owned by
  `sakura:adversarial`.

## Output

Return a list of findings in the standard schema from `references/orchestration.md`,
plus any `assumptions`.

### Finding rules
- **Severity:** Every separable-concern finding is a flat `Should fix`. The
  deficient-description finding is the one exception: always `Nit`.
- **No caps:** No artificial limit on the number of findings per review.
- **No dispositions:** Do not suggest triage dispositions (e.g. "Accept", "Ignore").
  `validate_triage.py` rejects inferred dispositions.
- **Concern granularity:** **One finding per separable concern**, anchored at that
  concern's first hunk and listing every file it spans. Never emit per-file findings
  for parts of the same concern.
- **Recommendation format:** A split is not a code change, so the "include corrected
  code" rule does not apply. Use this specific shape:
  ```
  Proposed MR: <concise proposed MR title>
  Files: <file:line-range, ...>
  Why separate: <one-line rationale: why it is independent, what reverting leaves working>
  ```
- **Reviewer seat tone:**
  In reviewer seat, phrase the issue and recommendation as a **question to the author**
  (e.g. *"Does this dependency bump belong in a separate MR? Reverting pyproject.toml:12-14
  and poetry.lock leaves the rate-locking feature green."*). The reviewer does not own the
  author's intent; which triage bucket it lands in stays the reviewer's call.

### Example findings

```json
[
  {
    "severity": "Should fix",
    "dimension": "sakura:scope",
    "file": "pyproject.toml",
    "line": "12-14",
    "issue": "Dependency bump for grpcio is bundled with unrelated credit rate locking logic.",
    "recommendation": "Proposed MR: `chore(grpc): pin grpcio to 1.62 for the new client`\nFiles: `pyproject.toml:12-14`, `poetry.lock`\nWhy separate: nothing in the credit-rate change imports the new client; reverting these two files leaves the feature green.",
    "verified": true,
    "assumptions": []
  }
]
```

Reviewer seat phrasing:
```json
{
  "severity": "Should fix",
  "dimension": "sakura:scope",
  "file": "pyproject.toml",
  "line": "12-14",
  "issue": "Does the grpcio dependency bump belong with credit rate locking, or in its own MR?",
  "recommendation": "Does the grpcio bump belong in a separate MR?\nProposed MR: `chore(grpc): pin grpcio to 1.62 for the new client`\nFiles: `pyproject.toml:12-14`, `poetry.lock`\nWhy separate: nothing in the credit-rate change imports the new client; reverting these two files leaves the rate-locking feature green.",
  "verified": true,
  "assumptions": []
}
```

Deficient description finding (MR-only):
```json
{
  "severity": "Nit",
  "dimension": "sakura:scope",
  "file": "src/billing/rates.py",
  "line": "1-25",
  "issue": "MR description is missing or too thin to establish change intent against the diff.",
  "recommendation": "Update the MR description to state the purpose, context, and intended scope of this change so reviewers and future readers can evaluate the diff against its goals.",
  "verified": true,
  "assumptions": []
}
```

### Assumptions reporting

Report assumptions even when returning no findings (`[]`):
- Drive-by edits inside a touched function:
  `"Assumed drive-by cleanup in `format_rate()` at `rates.py:45-52` is intentionally coupled with the primary change."`
- Inferred intent from guess / fallback:
  `"Scope intent was inferred from branch name 'feature-rates' and title 'Fix rate calculation' because the MR description was absent or thin."`
- Suppressed deficient description finding in non-MR mode:
  `"Deficient description check was suppressed because review was run in local working-tree mode with no MR."`
- Any uncertainty in call-graph reachability or separability.

## Verification gate

Every separable-concern finding is `Should fix` and must have `verified: true`.
No finding may rest on diff inspection alone.

Verification requires confirming that the flagged cluster is truly separable:
1. Search the reviewed repository at `refs.head` (the local working tree for `--local`)
   for all symbols and files in the flagged cluster, then inspect the references.
2. Confirm that neither the primary change nor its tests depends on or references
   anything in the flagged cluster.
3. Confirm that reverting the cluster's hunks leaves the primary change complete,
   compiling/building, and passing tests.
4. If source coverage or separability is uncertain, **drop the candidate**, do not
   guess or downgrade to a speculative Nit.
This is source/reference verification, not permission to revert code or run another
author's tests. Do not claim a build or test run succeeded unless it actually ran.

For the **MR-description finding**:
- Verify the description and intent-source mismatch (`scope_intent.source != "description"`)
  directly from the prepared MR context file.
- Confirm the first-hunk anchor against the reviewed source.
- Define evidence honestly for metadata deficiency (record that the MR description lacks
  a stated goal or is absent/unfilled, anchored at the first changed file as the MR
  entry point).
- **Never fabricate or invent an anchor** if `changed_files` is empty or diff hunks are
  unavailable.

Source access by seat and mode (per `orchestration.md`):
- **Author with `source == "gitlab"`:** `glab api --hostname <host> "projects/<enc-project>/repository/files/<enc-path>/raw?ref=<refs.head>"`
- **Author with `source == "git"`:** `git show <refs.head or origin/branch>:<path>`
- **`--local` mode:** Read the local working tree directly, consistent with orchestration
  (the working tree is the authoritative source for local changes).
- **Reviewer with borrowed source:** Read `REVIEW_SOURCE_ROOT/<path>` (verifying detached
  HEAD equals `refs.head`).
- **Reviewer diff-only:** As noted above, `sakura:scope` is skipped entirely in diff-only
  mode because verification without source is impossible.
