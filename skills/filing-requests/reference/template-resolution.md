# Template resolution

How a repo's issue templates become this session's field set. Three subcommands, split apart
deliberately so the "never pick silently" rule is structural rather than advisory: `fields` cannot
run until `select` has returned a single, settled outcome.

```
template_resolve.py discover --repo-root <path>
template_resolve.py select   --candidates <path|-> --type bug|feature|code-change
template_resolve.py fields   --type bug|feature|code-change [--template <path|-> | --no-template]
```

---

## Step 1 — `discover`

Globs `.github/ISSUE_TEMPLATE/*.yml`, `*.yaml`, `*.md` and `.gitlab/issue_templates/*.md`, then
applies two exclusions:

1. **`config.yml` is never a candidate.** It is GitHub's chooser configuration, not a template.
2. **A file with no body sections is never a candidate.** A YAML form qualifies iff at least one
   `body[]` element has `type != "markdown"` — static `markdown` blocks are instructions, not
   fields. A markdown template qualifies iff it carries at least one `##`-or-deeper heading.

Output:

```json
{"yaml_tier": "pyyaml",
 "candidates": [{"path": ".github/ISSUE_TEMPLATE/bug.yml", "kind": "github-yaml",
                 "name": "Bug Report", "labels": ["bug"], "filename_stem": "bug"}]}
```

A repo with no template directories at all is **not an error** — it is an empty candidate array,
exit `0`. A `--repo-root` that isn't a directory is exit `2`.

**A template that fails to parse is excluded with a warning on stderr naming the file and line.**
It does not abort discovery for the rest of the repo. Failing a whole session over one malformed
file would be a worse outcome than skipping it.

### Why `yaml_tier` is in the output

Parsing runs in two tiers: PyYAML when it happens to be importable, and a bounded built-in subset
otherwise. quirk ships to arbitrary machines, so nothing here may *require* a third-party library —
but PyYAML is frequently present, and using it when it exists beats a hand-rolled parser on every
input that matters.

The consequence is that a template can resolve on one machine and be skipped on another. Reporting
the active tier makes that visible instead of silent. If you see `"yaml_tier": "mini"` and a
template you expected is missing from the candidates, the stderr warning will say why.

The mini tier handles: block mappings, block sequences (including `- key: value` items),
plain/single/double-quoted scalars, booleans, `|`/`>` block scalars, `#` comments, and flow
sequences of scalars (`labels: ["bug", "needs-triage"]` — the form real GitHub issue forms
actually use). It rejects flow mappings, nested flow collections, anchors/aliases, multi-document
separators, tags, and merge keys.

---

## Step 2 — `select`

Matches the confirmed type against each candidate, in this order, stopping at the first stage that
yields exactly one template:

1. **Declared identity** — the template's `name` and `labels`.
2. **Filename stem** — only if identity didn't settle it. A stem-only match never outvotes a
   template that declares itself.

| Type | Keywords |
|---|---|
| `bug` | `bug`, `defect`, `regression` |
| `feature` | `feature`, `enhancement`, `proposal`, `idea` |
| `code-change` | `chore`, `task`, `refactor`, `maintenance` |

Output is one of three resolutions, and **all three are exit `0`** — "ambiguous" and "none" are
valid outcomes the caller must act on, not error states.

| resolution | meaning | what you do |
|---|---|---|
| `single` | exactly one candidate matched | use `template` |
| `ambiguous` | several matched | **ask the user**, listing each of `ambiguous_candidates` by name and path |
| `none` | nothing matched | fall back to the per-type core; record `template.applied: false` |

**Never pick silently among several.** Which template is chosen determines the field set, so a
silent pick is a silent change to what gets asked and what gets emitted.

**The fallback is not a failure mode to avoid.** A repo whose templates don't cover the confirmed
type is better served by the per-type core than by a template written for something else.

---

## Step 3 — `fields`

Returns the ordered field set as `[{"name", "required", "source"}, …]`, where `source` is
`"template"` or `"core"`. Three rules apply in order, identically to YAML forms and markdown
templates:

1. **The template supplies structure and ordering.** Its sections, in its own order, seed the list.
2. **Requiredness is the union of the template's markings and the per-type core.** A YAML form's
   `validations.required` is authoritative for its own sections. A markdown template has no such
   mechanism, so it contributes *no* markings — inventing them would let a template silently
   subtract from the core. Either way the core is additive: any core field the template omits is
   appended, in core order, after the template's sections, marked required.
3. **The non-waivable gate is global and overrides both.** On a `feature`, `problem` and
   `acceptance_criteria` are forced required regardless of what the template declared or omitted.

A template can add requirements. It can never subtract them.

### Canonical field names

Both kinds produce snake_case, so a template-derived name and a core name can be recognized as the
same field rather than added twice.

- **YAML form:** the element's `id` when present, else `slugify(attributes.label, sep="_")`.
- **Markdown template:** `slugify(<heading text>, sep="_")`, with markers and trailing punctuation
  stripped. The section's content runs to the next heading at any depth; heading *depth* is not
  modeled as nesting, since a field set is flat.

A small closed synonym table catches the near-misses — `Steps To Reproduce` →
`steps_to_reproduce`, `Expected behaviour` → `expected_behavior`, `Actual behavior` →
`current_behavior`. Without it, "Expected behaviour" slugs to `expected_behaviour` and becomes a
*second* field beside the core's `expected_behavior`, asking the user the same question twice and
rendering two near-identical sections. An unmatched heading becomes its own template-supplied
field, which is the right outcome for a genuinely novel section.

---

## Writing the result onto the document

`fields`' output goes onto the canonical document as `template.fields`, alongside `applied` and
`path`:

```json
{"template": {"applied": true, "path": ".github/ISSUE_TEMPLATE/bug.yml",
              "fields": [{"name": "what_happened", "required": true, "source": "template"}]}}
```

**This is required, including on the `--no-template` path** — there the entries are all
`source: "core"`.

The union is computed once, when resolution settles, and every later consumer reads it *from the
document*. That is what makes the union rule enforceable at all: `canonical_schema.py`'s interface
is `--input <doc>`, so without the union on the document, the gate meant to enforce "a template can
add requirements but never subtract them" can only see the fixed per-type table — and a
template-added required field left unresolved would pass emission silently.

A document whose `template.fields` is absent or empty fails `--for-emission` with a structural
error rather than falling back to the per-type table, because a silent fallback is the exact
failure this key exists to prevent.

**Type drift rewrites it.** `drift_apply.py` carries `template.fields` across the same mapping the
values take and re-applies the union rule to the destination type. Do not re-derive it by hand
after a drift, and do not leave the old one in place — it would describe the *source* type, so the
gate would check the wrong field list entirely.
