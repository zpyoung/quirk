---
name: adversarial-review
description: Use when a work product needs adversarial review - attacking a diff, spec, plan, or written claim to find what is wrong with it. Triggers on "adversarial review", "critique this", "red team it", "attack this", "find flaws", "tear this apart", "poke holes in", or when another skill composes a review step. Runs a deterministic pre-pass, a two-stage promote/refute protocol with a cross-family reviewer, and an evidence gate that drops findings whose evidence cannot be re-resolved.
---

# Adversarial Review

Attack a work product and return findings a human or a calling skill can act on. Point it at a
diff, a spec, a plan, or a claim.

**Core principle:** independence is structural, not rhetorical. A reviewer that shares the author's
context and model family will miss what it would catch in the same content framed as external, and
no amount of adversarial phrasing repairs that. This skill buys independence with asymmetric
context and a different model family, then spends the rest of its machinery keeping the findings
honest.

## When to Use

Use for: a branch diff before merge, a spec or design doc before implementation, a plan before
execution, a README or claim you suspect is stale, or as a review step inside another skill.

Do not use for: cooperative review — `quirk:requesting-code-review` is the skill that helps you
improve something you are still building. This one attacks a thing that claims to be finished. The
two postures are genuinely different.

Never applies patches, never edits files, never asks a blocking question.

## The three layers

Each layer has a different trust basis, and keeping them separate is what makes the output
readable.

**1. Ground truth — deterministic, no model.** The profile's pre-pass runs: tests for code,
reference resolution and section coverage for prose. Whatever it reports is true by construction. A
spec citing a function that does not exist needs no model to detect, and detecting it that way
costs nothing and cannot hallucinate.

**2. Adversarial — two dispatches with asymmetric context.** A **promote** stage maximizes recall
against a low bar. A **refute** stage runs in a fresh context under a kill mandate, receiving the
artifact, the ground truth, and promote's *claims only, never its reasoning*.

**3. Adjudication — deterministic again.** Evidence gate, tie resolution, suppression accounting,
verdict, manifest. The script computes all of it; no model decides the verdict.

### The load-bearing invariant

**The reviewer never sees the author's reasoning — only the artifact and the criteria.**

Not the commit messages, not the design rationale, not the implementer's account of why the
approach is right. Criteria — what the artifact was supposed to achieve — are staged verbatim. Every
other author-supplied context is withheld.

This is why the older prior-art instruction *"Do NOT validate — only critique"* is replaced rather
than inherited. That phrasing produces **inverse sycophancy**: a critic that manufactures findings
to appear useful, because it was told validation is not an acceptable output. Noise is the dominant
failure mode of AI review — 70–90% of findings get ignored as false positives, and teams switch
gates off over it. Every design choice below is downstream of that number.

## Data flow

```bash
SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/adversarial-review/scripts/adversarial-review"
WORK="$(mktemp -d)"
```

Each subcommand writes exactly one JSON object to stdout. Diagnostics go to stderr. Nothing writes
to the repository.

**1–2. Resolve the target and select the profile.**

```bash
"$SCRIPT" resolve --target "$TARGET" > "$WORK/resolve.json"
```

Target is a path, a git range (`a..b`), or `WORKTREE`/empty for uncommitted changes. The profile is
inferred from the target's shape; `--profile` overrides. `ResolveResult` carries `profile`,
`target_kind`, `artifact_hash`, `size_metric`, `depth_suggestion`, and `contract_surface`.

A target that cannot be read — a typo'd range, a non-repo root, a missing file — exits 2. It never
resolves to size 0, because a review of nothing must not be reportable as a review that found
nothing. `size_metric` is lines under `code-diff` and words under the prose profiles, on both the
path and the diff paths. `WORKTREE` covers **all** uncommitted work — unstaged, staged (it diffs
against `HEAD`), and untracked files that git would not diff at all. A brand-new module is
uncommitted work, and omitting it would review everything except the new code. `.gitignore` is
honoured.

**3. Pre-pass.**

```bash
"$SCRIPT" prepass --profile "$PROFILE" --target "$TARGET" > "$WORK/prepass.json"
```

Exit 1 means a check failed — that is a finding, not an error. Only exit 2 is a failure. `status:
"could-not-run"` means no check was executable at all, which is distinct from `"fail"` and feeds
the `NOT_REVIEWABLE` condition.

**Every failed check becomes a finding**, in every branch. The verdict is computed from findings
alone, so a failure that stops at `checks[]` is a failure that silently passes. Checks that file
their own, more specific findings (reference resolution) are covered by those; everything else gets
a generic `failing-check` finding. The default for a new check is *covered*, so forgetting to wire
one up fails safe.

**4. Select the adversary.**

```bash
"$SCRIPT" select-model --author-family "$AUTHOR_FAMILY" > "$WORK/model.json"
```

Defaults to a family different from the author's, gates each candidate on `pi-watch --check
<alias>`, and walks the ladder on failure. If the resolved rung lands on the author's own family,
`independence` is stamped `"reduced"`.

`author_family` resolves in order: the explicit input; else the family in the manifest of the run
that produced the artifact; else the family of this session. Exit 1 means no rung resolved —
continue anyway, with `resolved: false`. The gate turns that into `NOT_REVIEWABLE`; do not stop
here and do not treat it as a pass.

**5. Promote.** Stage `assets/promote-prompt.md` and dispatch. Collect its JSON array to
`$WORK/findings.json`. See Dispatch below.

**6. Refute.** Stage `assets/refute-prompt.md` with promote's six claim fields only — `id`,
`severity`, `confidence`, `category`, `claim`, `evidence[]` — and dispatch **in a fresh context**.
It returns judgments, not findings. Merge each judgment onto its finding: set `disposition` from
the judgment and `stage` to `"refute"`. Never let refute rewrite a `claim`.

Skip this step entirely at `quick` depth — promote already self-refuted.

**7. Evidence gate.**

```bash
"$SCRIPT" gate --findings "$WORK/findings.json" --model "$WORK/model.json" \
  --prepass "$WORK/prepass.json" --depth "$DEPTH" > "$WORK/gate.json"
```

`--model` and `--prepass` are required; without them the `NOT_REVIEWABLE` branch is unreachable and
an unreviewed artifact would emit `PASS`. The gate merges the pre-pass findings itself — do not
pre-merge them.

`--findings` takes either a bare array or `quick`'s `{"findings": [...], "suppressed": [...]}`
object. Pass the quick object through whole: its self-refuted entries are carried into
`suppressed_count`, and dropping them would report a kill rate of zero for the one depth that
refutes itself.

**Running several invocations and merging them?** Give each a distinct `--id-prefix`. Every gate
numbers from 1 independently, so three concurrent lenses all produce `F1` and a caller that keeps
the IDs — as the dismissal carry-forward requires — cannot tell them apart.

The evidence gate runs *before* the tie is routed, so a `contested` finding whose evidence is
demonstrably false is suppressed as `falsified` rather than sent to tiebreak. A falsehood is not a
disagreement, and adjudicating one costs a third dispatch to learn nothing.

**8. Tiebreak.** At `deep` depth only, and only if `gate.json` has a non-empty `contested[]`. Stage
`assets/tiebreak-prompt.md`, dispatch to a **third** family, merge its rulings onto those findings,
and re-run `gate`. Contested findings are withheld from `findings[]` and are not counted as
suppressed — ignoring `contested[]` silently drops them.

**9. Emit.**

```bash
"$SCRIPT" manifest --resolve "$WORK/resolve.json" --prepass "$WORK/prepass.json" \
  --model "$WORK/model.json" --gate "$WORK/gate.json" ${LENS:+--lens "$LENS"} > "$WORK/manifest.json"
```

Then render the human summary, the findings block, and the manifest.

## Depth

| Depth | Protocol | Auto-selected when |
| --- | --- | --- |
| `quick` | One dispatch; the reviewer refutes its own list in the same reply | ≤50 changed lines, or <500 words of prose |
| `standard` | Independent refute dispatch in a fresh context | Default |
| `deep` | Adds a third-family tiebreak on contested findings | >150 changed lines, or a contract/schema surface |

`--depth` overrides. `resolve`'s `depth_suggestion` is advisory — a caller that knows the review is
branch-sized should pass `--depth` explicitly rather than letting size auto-selection decide.

`quick` is a **different pipeline shape**, not a cheaper `standard`: one dispatch instead of two,
self-refutation instead of independent refutation. It is therefore stamped `independence:
"reduced"` regardless of model family, so its `PASS` is never read as equivalent to a `standard`
one. The self-refute instructions live in `assets/promote-prompt.md`; there is no refute dispatch.

## Profiles

Auto-detected from the target, overridable with `--profile`. Each declares an attack surface,
evidence rules, and what the pre-pass already established, and is staged verbatim into the stage
prompts.

| Profile | Artifact | Detected by |
| --- | --- | --- |
| [`profiles/code-diff.md`](profiles/code-diff.md) | A diff, git range, or worktree | `..` in target, `WORKTREE`, or anything not matching below |
| [`profiles/spec-design.md`](profiles/spec-design.md) | Spec, design doc, ADR | `logic.md`, `tech.md`, `docs/adr/`, or `spec`/`design` in the name |
| [`profiles/plan.md`](profiles/plan.md) | Implementation plan | `docs/plans/` or a `plan*` basename |
| [`profiles/prose-claim.md`](profiles/prose-claim.md) | README, runbook, claim | Any other `.md` |

The script does not parse these files — its pre-pass tables are internal config. A profile's prose
can change without touching script behavior.

## Verdict contract

Computed mechanically from surviving **severity** only. Confidence never affects it.

| Verdict | Condition | Exit |
| --- | --- | --- |
| `CRITICAL_ISSUES` | Any surviving `CRITICAL` | 3 |
| `NEEDS_FIXES` | Any surviving `HIGH` or `MEDIUM`, no `CRITICAL` | 1 |
| `PASS` | Only `LOW` findings survive, or none | 0 |
| `NOT_REVIEWABLE` | No reviewer resolved at any rung, **or** the pre-pass could not run and the artifact's core claims are unfalsifiable | 4 |

**`NOT_REVIEWABLE` is never a synonym for `PASS`.** It means the review did not happen — nothing was
examined and nothing was cleared. Handle all four verdicts by name. A caller writing `if verdict !=
"CRITICAL_ISSUES": proceed` has a failure mode that is silent and looks exactly like success.

### Severity and confidence are independent axes

Severity is consequence; confidence is likelihood. The evidence gate moves only confidence, and
only where proof is required:

- **verified** — evidence re-resolves and includes a `command` or `prepass` item → unchanged.
- **unverified** — evidence re-resolves, no reproduction → severity unchanged, confidence capped at
  `LOW`, and only for `CRITICAL`/`HIGH`, which is exactly where reproduction is required. A
  high-consequence finding nobody can prove survives as `CRITICAL`/`LOW` rather than being
  downgraded into invisibility.
- **falsified** — *any* evidence item fails to re-resolve → dropped and counted. One true citation
  does not shield a fabricated one beside it; evidence that cannot be checked either way counts as
  holding, so this drops only demonstrable falsehoods.

What "re-resolve" checks, per evidence kind:

| Kind | Checked | Not checked |
| --- | --- | --- |
| `file-line`, `quote` | The file exists, and the quote appears **within the cited line range** | — |
| `absence` | The scope it names exists — a search over a missing file proves nothing | The search is never re-run |
| `command`, `prepass` | — | Never re-run |

Every evidence field must be a non-empty string. Presence is not content: an empty `command`/`output`
pair would otherwise satisfy the schema and buy reproduction credit, holding a finding at `HIGH`
confidence on evidence of nothing. A `#fragment` keeps a ref unfalsifiable only when what precedes it
names no file — `spec#3` is a section, `docs/gone.md#x` is a missing file and is falsified.

A cited range is a claim about location, so citing `src.py:400` for a quote that lives at line 12
is falsified even though the quote is real. A ref with no anchor makes no such claim and is matched
against the whole file. **Commands are never re-executed**: running model-supplied shell inside the
one deterministic stage would make it neither deterministic nor safe. That is a deliberate limit —
`command` evidence is trusted as written, which is why it grants reproduction credit but cannot be
falsified here.

## Output

Render at most **10 lines** of human summary above the findings block. Derive every line of it from
`GateResult` — verdict, reviewer alias and its `independence` flag, counts by severity, suppressed
count, the highest-severity claim. **Never author the summary independently**; a hand-written
summary and a machine-computed findings block drift, and the reader trusts the wrong one.

```
NEEDS_FIXES — 4 findings (1 HIGH, 2 MEDIUM, 1 LOW), 3 suppressed
reviewer: gpt-5.6-sol (openai) · independence: full · depth: standard · profile: spec-design
top: Step 7's "downgraded" names no axis, so two implementations diverge on which findings ship.
```

Then the findings array verbatim, then the manifest.

**Watch the kill rate.** `suppressed_count` against the number raised is an integrity signal. A
near-total kill rate means the promote stage was fabricating and the run itself should not be
trusted — a `PASS` reached by killing everything is not a `PASS` reached by finding nothing. Say so
in the summary when you see it.

## Dispatch

Both stage paths get `read`, `grep`, `find`, `ls`, and **read-only `bash`**. Tiebreak gets the first
four only. No stage ever gets `edit` or `write`.

**`pi-watch` path** — preferred for cross-family independence.

```bash
pi-watch --check "$ALIAS" || walk the ladder
pi-watch --provider "$PROVIDER" --model "$MODEL" --thinking "$THINKING" \
  --tools read,grep,find,ls,bash "$(cat "$PROMPT")" > "$OUT" 2> "$ERR"
```

`pi` has no sandbox. On this path the read-only constraint is enforced by prompt text alone — the
stage templates say so, and that is the entire mitigation. The risk is accepted deliberately and
recorded in `assets/composition-contract.md`; a caller that cannot accept it should use the `Task`
path, where permission mode bounds the reviewer.

**`Task` path** — when `pi` is unavailable or the risk is unacceptable. Dispatch a subagent with the
staged prompt as its whole instruction. Same-family review is still a real review; it is stamped
`independence: "reduced"` and read accordingly.

**Strip one fenced block before parsing.** Every stage prompt says to emit JSON and nothing else,
and reviewers still wrap it in ` ```json ` fences often enough to matter. A fenced payload is a
formatting deviation, not a crashed dispatch — unwrap a single leading fence, then parse. Treat it
as failed output only if what is inside does not parse.

**A dispatch that returns nothing crashed.** It did not find nothing. A reviewer that found nothing
emits `[]`; one that produced no output at all failed. Retry once, then walk the ladder, then block.
This holds no matter how many times that reviewer has come back empty — an established pattern of
empty output is evidence the reviewer is broken, not evidence the artifact is clean.

## Composing this skill

Read [`assets/composition-contract.md`](assets/composition-contract.md) — it is the caller-facing
interface: input and output schemas, `dismissed[]` carry-forward, finding-ID stability, the
clean-versus-crashed table, and the tool-grant trade stated plainly.

The caller keeps adjudication, patch application, round counts, and exit conditions. This skill
reviews once per invocation and returns findings; it does not decide what to do about them.

## Red Flags

| Thought | Reality |
| --- | --- |
| "The verdict isn't `CRITICAL_ISSUES`, so we're fine" | `NOT_REVIEWABLE` is not a pass. Handle all four by name. |
| "I'll paste the design rationale so the reviewer has context" | That is the author's reasoning. Staging it disables the only mechanism buying independence. |
| "The reviewer returned nothing — clean review" | It crashed. Retry, then walk the ladder, then block. |
| "It found nothing, so I'll look harder for something to report" | That is inverse sycophancy. A clean review is a valid outcome. |
| "Everything got suppressed, but the verdict is `PASS`" | A near-total kill rate means the run is untrustworthy. Say so. |
| "I'll summarize the findings in my own words" | Derive the summary from `GateResult` or it drifts from the block below it. |
| "`contested[]` is probably fine to skip" | At `deep` those are withheld findings, not dropped ones. Route them to tiebreak. |
| "It's a small change, `quick` is fine" | `quick` cannot deliver structural independence, and its `PASS` says so. Choose it knowingly. |
