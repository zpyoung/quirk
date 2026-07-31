# Guardrails

Three gates stand between a session and an outward-facing artifact. Each is enforced by a script,
not by your discipline — but you have to run them, in order, and act on what they return.

| Gate | Script | Blocks |
|---|---|---|
| Non-waivable fields | `canonical_schema.py --for-emission` | rendering **and** filing |
| Secret scan | `secret_scan.py` | filing (and writing, until resolved) |
| Filing confirmation | `github_file.py` (dry run, then `--execute`) | filing |

Plus one derived value — `disclosure_required` — that you never hand-set.

---

## 1. The non-waivable gate

```
python3 skills/filing-requests/scripts/canonical_schema.py --input doc.json --for-emission
```

Exit `0` means every core field is resolved and nothing is halted. Exit `3` means it is not.

A core field is **resolved** when it holds a `value` with provenance `observed` or `reported`, or
carries provenance `missing` with a stated `reason`. Optional fields never gate anything.

**Which fields are non-waivable is fixed, not configurable:** `problem` and `acceptance_criteria`,
and only on `type: "feature"`. A `bug` or `code-change` document can resolve every core field via
`missing` + `reason`; the gate never halts those two types.

The gate is *stricter* than ordinary resolution. A non-waivable field needs `observed` or
`reported` with a real value. `inferred` fails. `missing` fails. So does a value still carrying
`needs_confirmation: true` — there is an open question against it.

When `halted` comes back populated, it names the field and why:

```json
{"valid": false, "errors": [], "halted": {"field": "acceptance_criteria",
 "reason": "no testable pass/fail condition established"}}
```

Say which field is unresolved and why that blocks. Then offer the two honest exits:

1. **Keep working on it now** — go back and establish the field.
2. **Save the partial canonical form** — write the JSON as-is so the session can resume later. No
   script is needed; the document is already valid JSON and the resume case doesn't call for
   markdown.

Nothing is filed. Nothing is fabricated to get past the gate. The absence of a `halted` key means
"not halted" — there is exactly one way to check, not two that could disagree.

**The gate is enforced in `canonical_schema.py` alone.** `markdown_render.py` and `github_file.py`
both re-run it rather than re-deriving the rule, so there is one implementation to be right.

---

## 2. The secret scan

```
python3 skills/filing-requests/scripts/secret_scan.py --input doc.json
```

Exit `0` = clean. Exit `1` = findings. Do not proceed until the user resolves **every** finding —
redact it or knowingly keep it.

**Scope is by output, not by field.** The scanner reads every string the artifact can render:

- every `fields[].value`
- every `fields[].reason`
- `title`
- `proposed_solution.value`
- every `verified_against[]` entry

Scanning only `fields[]` would leave the title and the reporter's proposed fix unscanned, and both
render into the emitted issue.

Findings are located by path so the user can see exactly what leaked and where:

```json
[{"path": "fields[2].value", "pattern": "aws_access_key_id", "match": "AKIA…CDEF", "span": [14, 34]}]
```

**The `match` is redacted** — first four characters, an ellipsis, last four. A scanner whose own
output re-prints the secret has defeated its purpose the moment that output is logged. Never echo a
full secret back to the user either; refer to it by its path and its redacted form.

### What v1 detects

| Pattern | Catches |
|---|---|
| `AKIA` + 16 uppercase alphanumerics | AWS access key ID |
| `ghp_` + 36 alphanumerics | GitHub personal access token |
| `gho_`/`ghp_`/`ghr_`/`ghs_`/`ghu_` + 36+ | GitHub OAuth / refresh / server / user tokens |
| `xoxb-`/`xoxa-`/`xoxp-`/`xoxr-`/`xoxs-` + 10+ | Slack tokens |
| `eyJ` + two dot-separated base64url segments | JWTs |
| `-----BEGIN [RSA\|EC\|OPENSSH] PRIVATE KEY-----` | private key blocks |
| `scheme://user:password@` | connection strings with an embedded credential |
| `api_key`/`secret`/`token`/`password` `=`/`:` + 16+ chars | generic credential assignments |

This is a **starter set, not a guarantee.** It catches the shapes that leak most often. It does not
catch a bare high-entropy string with no surrounding context, a credential the user paraphrased, or
a secret in a format nobody has published a pattern for. Say so if the user asks whether the scan
means the document is safe: it means none of the above shapes are present.

Expanding the list is a script change only, never a schema change.

---

## 3. The filing confirmation

The markdown artifact is written **unconditionally**. Filing to GitHub is not.

```
# 1. dry run -- show the user this output verbatim
python3 skills/filing-requests/scripts/github_file.py --input doc.json --repo owner/repo

# 2. only after explicit confirmation
python3 skills/filing-requests/scripts/github_file.py --input doc.json --repo owner/repo --execute
```

The dry run prints `{"repo", "title", "body_preview", "would_execute"}`, where `would_execute` is
the literal argv that would be executed. **Displaying it is the confirmation** — the user sees the
exact body and the exact destination before anything leaves the machine.

Filing is outward-facing and effectively irreversible: a deleted issue has already notified every
watcher. That asymmetry is why the file costs nothing and the filing costs a confirmation.

`github_file.py` re-checks everything before it acts, rather than trusting that you sequenced it
correctly:

| It refuses | Exit |
|---|---|
| `--repo` disagreeing with the document's `target.repo` | 2 |
| a document that fails `--for-emission` (including halted) | 3 |
| a document with secret findings | 1 |
| a `headless: true` document | 3 |
| `target.kind` that isn't `github` | 6 |

None of these invoke `gh`.

**Credentials are `gh`'s problem.** Never read, store, or pass a token. If `gh` is unauthenticated,
that is a message to relay, not a thing to work around.

---

## The disclosure footer

`disclosure_required` is **derived, never hand-set**:

```
disclosure_required = (visibility != "private") or (third_party != "no")
```

So `third_party: "unknown"` discloses exactly like `third_party: "yes"`, and an unknown visibility
discloses too. When ownership or visibility cannot be determined confidently, you disclose — the
uncertainty resolves toward disclosure, not away from it.

When it is `true`, the artifact ends with a fixed single-line footer naming AI assistance. When it
is `false`, **nothing** is rendered — no footer, no placeholder.

`canonical_schema.py` recomputes the value from `target` and rejects a document whose stored value
disagrees, so a public target carrying `"disclosure_required": false` cannot pass emission.

---

## Anti-slop

These are the reasons the artifact is short, and they are not stylistic preferences.

- **Padded prose and invented specificity are the signature markers of AI-authored issues**, and
  maintainers reject on sight. Length is the tell.
- **A field with no provenance cannot render.** That is the structural guard — you cannot pad a
  field into existence, because the renderer projects provenance, not prose.
- **`inferred` renders hedged**, with a fixed prefix. If you concluded something rather than
  verified it, say so in the data and let the renderer say it in the artifact.
- **`verified_against` is assembled from `observed` sources**, never written freehand. The
  validator rejects an entry that doesn't match some field's `source`.
- **Never fabricate to clear a gate.** An honest `missing` with a real reason is a better report
  than a plausible invention, and the reason is often diagnostic in itself.
