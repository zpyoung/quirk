# Quick Review Mode (`--quick`)

Use this runbook when `--quick` is passed. Quick mode replaces the multi-wave review pipeline with a **single parallel wave of 7 pre-bundled specialist packs** (`4 deep + 3 fast`) bookended by deterministic Python preparation and consolidation (`$SCRIPTS/quick_review.py`):

| Vendor (`--vendor`) | 4 Deep Packs (`correctness`, `safety-db`, `cross-repo-and-callers`, `conventions-and-docs`) | 3 Fast Packs (`resilience-and-observability`, `adversarial-and-scope`, `tests-and-adequacy`) |
|---|---|---|
| **`anthropic`** *(default)* | `sonnet` (`claude-sonnet-5-5`) | `haiku` (`claude-haiku-5-5`) |
| **`openai`** | `codex` (`gpt-6.1-sol`) | `codex-mini` (`gpt-6-luna`) |
| **`google`** | `gemini` (`gemini-3.1-pro`) | `flash` (`gemini-3.8-flash`) |
| **`xai`** | `grok` (`grok-4.7`) | `grok` (`grok-4.7`) |

Never read the diff, source files, or sibling repositories in the coordinator session — `$SCRIPTS/quick_review.py prepare` pre-bundles the annotated diff, line-numbered source windows, cross-repo sibling grep hits, and discovered guidance into each pack's self-contained prompt file.

---

## Step 1 — Deterministic Preparation (1 Bash call)

Run setup and preparation in a single Bash call:

```bash
SCRIPTS="${CLAUDE_PLUGIN_ROOT}/skills/full-code-review/scripts"
export REVIEW_OUT_DIR="${REVIEW_OUT_DIR:-$(mktemp -d -t quirk-review.XXXXXX)}"
python3 "$SCRIPTS/quick_review.py" prepare --run-dir "$REVIEW_OUT_DIR" \
  [--change <number> -R <owner/repo> | --branch <name> | --local] [--forge github|gitlab|none] [--since <ref>] [--seat author|reviewer] [--vendor anthropic|openai|google|xai|auto]
```

If `prepare` prints `"hard_block": true`, stop and print the hard-block message from `SKILL.md`.

---

## Step 2 — Single-Wave Parallel Fan-Out (7 Packs)

In **one single assistant message**, spawn all 7 packs listed in `prepare`'s JSON output (`packs[]`) in parallel:
- **In Claude Code (`--vendor anthropic`):** use the `Agent` tool with `model: "<pack.model>"` (`sonnet` or `haiku`) and `run_in_background: false`.
- **Across other vendors (`openai`, `google`, `xai`) or `pi-watch`:** dispatch each pack via `pi-watch --alias <pack.model> --tools read,bash,edit,write` (see `quirk:pi-dev`).
- Prompt for each pack:
  ```text
  Read and follow <prompt_file> in full. Write your JSON array directly to <out_file> using Write, then return a one-line count summary.
  ```

---

## Step 3 — Deterministic Finalize & Report Delivery (1 Bash call)

Once the 7 packs complete, run `finalize` in a single Bash call:

```bash
python3 "$SCRIPTS/quick_review.py" finalize --run-dir "$REVIEW_OUT_DIR" [--format html|md|both] [--vendor anthropic|openai|google|xai|auto]
```

`finalize` normalizes and deduplicates findings across packs, validates line anchors against the source root, writes `$REVIEW_OUT_DIR/review-<slug>-report.json` and `$REVIEW_OUT_DIR/review-<slug>-findings.md` (and `.html` when requested), releases any borrowed worktree, and prints the JSON summary.
