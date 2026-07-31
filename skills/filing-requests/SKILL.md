---
name: filing-requests
description: Use when the user wants to file, report, or write up a bug, a feature request, or a code-change request — triggers on "file a bug", "report an issue", "write up a bug report", "open an issue", "file a feature request", "raise a ticket". Runs a guided evidence-gathering session, resolves what it can by reading the repo, and emits a terse provenance-marked markdown artifact plus, on explicit confirmation, a GitHub issue. NOT for "build/implement/add X" — that is brainstorming.
---

# Filing Requests

An evidence-gathering interview that writes short.

A web form can only ask, so it asks for everything and reporters abandon it. You can *look*. Spend
inspection budget to buy back question budget, and spend the questions you save on what only the
human knows. Then write terse — length is the tell that gets AI-authored issues discarded.

**Completeness and length are separable.** Be thorough about fields and miserly about words. Every
field is either established or explicitly marked missing with a reason. Never quietly fill one with
something plausible.

## Not this skill

| The user says | Skill |
|---|---|
| "file a bug", "report this", "write up an issue", "open a ticket" | **this one** |
| "build X", "implement X", "add a feature that…" | `brainstorming` |

Both fire on the word *feature*. The difference is the verb: **file/report/write up** is this
skill; **build/implement/add** is `brainstorming`.

## The canonical form is the spine

Everything between Establish and Emit is one JSON document, and **every field carries its
provenance**. Hold it in the session, write it to a temp path, and pass it to the scripts with
`--input`.

| provenance | means | requires |
|---|---|---|
| `observed` | you verified it by inspection | `value` + `source` (what you read) |
| `reported` | the user told you | `value` |
| `inferred` | you concluded it, unverified | `value` — renders hedged |
| `missing` | not established | `reason` — never a `value` |

Provenance is what makes the guardrails structural rather than advisory: invented specificity has
nowhere to enter, because a field with no provenance cannot render. Schema details are in
`scripts/canonical_schema.py`; run it whenever you are unsure whether a document is well-formed.

**Absence is a first-class `observed` result.** "No PDF export path exists; `src/export/`
implements CSV and JSON only" with `source: "src/export/__init__.py, grep -r 'pdf' src/ (no
matches)"` and `polarity: "negative"` is a verified fact. For feature requests it is the *primary*
thing inspection produces, and it is the guard against proposing what a project already has.

---

## Stage 1 — Orient

Establish ground in **one turn**.

1. Resolve the target repo from the working directory (`git remote get-url origin`), and whether
   the user can write to it.
2. Discover templates:
   ```
   python3 skills/filing-requests/scripts/template_resolve.py discover --repo-root .
   ```
3. Infer the request type from the user's opening description.
4. Read the non-fileable table below against what you already know.

Then ask **one combined question**: confirm the type, and confirm the inspection depth
(`none` | `read` | `run`, default `read`). If your reading says this should not be filed at all,
that judgment and its evidence go in the same turn. The user may override; say so.

### Non-fileable conditions

Check these before spending the user's time. Each is type-shaped, and they run in both directions.

| Inferred type | Check |
|---|---|
| Bug | configuration error on the reporter's side; already fixed on `main`; not actually broken — the described behavior is intended, which makes it a feature request |
| Feature | the capability already exists; the project explicitly rejected it before (a `DECISIONS`/ADR entry, a documented non-goal); it is a support question about how to use what exists |
| Code-change | already done; the described state does not match the repo |

You inspect **the code, not the tracker**. "Already fixed on `main`" is a repo question and is in
scope. "Is this a duplicate of #410" is a tracker question and is out — do not attempt duplicate
detection of any kind.

### Resolving the template

`discover` returns `{"yaml_tier": ..., "candidates": [...]}`. Pipe it to `select`:

```
… discover --repo-root . | \
python3 skills/filing-requests/scripts/template_resolve.py select --candidates - --type bug
```

| resolution | what you do |
|---|---|
| `single` | use it |
| `ambiguous` | **ask the user to choose**, listing each candidate by name and path |
| `none` | fall back to the per-type core; record that no template applied |

Never pick silently among several. Which template is chosen determines the field set, so a silent
pick is a silent change to what gets asked and emitted. The fallback is not a failure — a repo
whose templates don't cover the confirmed type is better served by the per-type core.

Then fix the field set onto the document:

```
# with a template (feed it the `template` object from select's output)
python3 skills/filing-requests/scripts/template_resolve.py fields \
    --type bug --template - --repo-root .

# without one
python3 skills/filing-requests/scripts/template_resolve.py fields --type bug --no-template
```

Write that array to `template.fields`, with `template.applied` and `template.path`. **This is
required.** Every later consumer reads the required-field union from the document, so a document
without it cannot be validated against the right field set. See
`reference/template-resolution.md`.

---

## Stage 2 — Establish

Walk the field set. For each field, **inspect first, ask second**.

1. Attempt resolution by inspection at the permitted depth. What resolves becomes `observed` with
   its `source` recorded — including negative observations.
2. What inspection cannot settle becomes a question. The answer becomes `reported`.
3. Append every `observed` field's `source` to `verified_against`.

`reference/field-catalogs.md` holds the per-field inspection strategy and question wording.

**Ask nothing the repo can answer.** This is the skill's reason to exist.

### Two interrupts

**Contradiction** — inspection disagrees with something the user stated. Surface it immediately
with the citation. The user's resolution determines which value survives and with what provenance.

**Type drift** — the accumulating answers indicate a different type. Surface it with the evidence
that changed the picture. If the user switches:

```
python3 skills/filing-requests/scripts/drift_apply.py --input doc.json --to feature
```

Nothing the user supplied is ever discarded: mapped fields move per the carry-over table, unmapped
fields are retained under their original names, and colliding fields merge rather than overwrite.
The script also rewrites `template.fields` for the new type — do not re-derive it by hand. Do not
re-ask a question the drift already answered.

Drift is symmetric. Bug → feature is the more common direction: nothing is broken and the reporter
is asking for behavior the system never had.

### The gate

A core field is **resolved** when it holds a value with provenance `observed` or `reported`, or is
marked `missing` with a stated reason. Optional fields never gate anything.

Two core fields are **non-waivable**: a `feature`'s `problem` and `acceptance_criteria`. A bug
report with no reproduction steps is still a valid report — the reason is itself diagnostic. A
feature request with no stated problem or no testable criterion is not a feature request; it is a
wish.

Check with:
```
python3 skills/filing-requests/scripts/canonical_schema.py --input doc.json --for-emission
```

Exit `3` with a populated `halted` means you must not emit. Say which field is unresolved and why
that blocks, then offer the two honest exits: **keep working on it now**, or **save the partial
canonical form** so the session can resume later. Do not fabricate anything to get past the gate.

### The draft drives the rest

Once every core field is resolved, render and show the draft:

```
python3 skills/filing-requests/scripts/markdown_render.py --input doc.json
```

From there, the remaining questions are driven by what the draft makes visibly thin or wrong. The
visible draft is the stopping rule — questions run until the draft is complete, not until a
counter runs out.

---

## Stage 3 — Emit

Three steps, in this order. See `reference/guardrails.md`.

**1. Scan for secrets.** Blocking.
```
python3 skills/filing-requests/scripts/secret_scan.py --input doc.json
```
Exit `1` means findings. Show each one by the path that located it (`fields[2].value`, `title`) and
do not proceed until the user has decided about every one. The scanner redacts its own output;
never echo a full secret back.

Two resolutions, and they are not equivalent:

- **Redact** — edit the value so it no longer carries the secret. Re-scan. Both the artifact and
  filing are then unblocked.
- **Keep** — the user judges it a false positive or accepts it. The local artifact still writes,
  because it is theirs. **Filing stays blocked**: `github_file.py --execute` re-scans and refuses
  with exit `1`, and there is no override. If they want it filed, the text has to change.

Say which of the two you are doing. "Keep" is not a way past the filing gate.

**2. Write the markdown artifact.** Unconditional.
```
python3 skills/filing-requests/scripts/markdown_render.py --input doc.json --write .
```
Lands at `docs/quirk/requests/YYYY-MM-DD-<slug>.md`. The file costs nothing and preserves the
session's work even when filing is impossible or declined.

**3. File to GitHub.** Only on a separate, explicit confirmation.
```
# show the user exactly this, verbatim
python3 skills/filing-requests/scripts/github_file.py --input doc.json --repo owner/repo

# only after they confirm
python3 skills/filing-requests/scripts/github_file.py --input doc.json --repo owner/repo --execute
```

The dry run prints the exact body and the literal argv that would be executed. Display it verbatim
— that display *is* the confirmation. Filing is outward-facing and effectively irreversible: a
deleted issue has already notified every watcher.

`--repo` must match the document's own `target.repo`. Authentication is `gh`'s; never handle a
token yourself.

---

## Headless runs

No questions. Populate what inspection resolves; mark everything else `missing` with reason
`no human in session`. Set `"headless": true` — the artifact then opens with a prominent statement
that no human confirmed it. **It is never filed to a tracker automatically**, and `github_file.py`
refuses `--execute` on a headless document regardless of what you do here.

Headless is viable for `bug` and `code-change`, whose cores are substantially inspectable. It is
**not** viable for `feature`: the two non-waivable fields are irreducibly human, so a headless
feature request halts. That is the correct outcome — an unattended process cannot know who benefits
or what "done" means.

## Exit codes

Every script shares these.

| Code | Meaning |
|---|---|
| 0 | success / clean |
| 1 | secrets found |
| 2 | usage error — bad args, malformed JSON, unreadable file |
| 3 | validation failure, **including** the non-waivable halt |
| 5 | `gh` not found or exited non-zero |
| 6 | unsupported `target.kind` |
| 8 | `schema_version` is newer than this skill understands |

## Never

- Fabricate a value to satisfy a gate. Mark it `missing` with an honest reason.
- Pick among several matching templates without asking.
- Render or file a halted or core-incomplete document.
- Write the issue body by hand — `github_file.py` renders through `markdown_render.py`, so the
  filed issue and the written artifact are the same rendering, never two copies.
- Attempt duplicate detection against the tracker.
- Pad. Invented specificity and padded prose are what maintainers reject on sight.
