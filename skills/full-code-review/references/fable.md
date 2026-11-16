# Three-Wave Deterministic Bookend Pipeline (Standard & `--deep`, Multi-Vendor)

Use this runbook for **Standard Mode** (default, when neither `--quick` nor `--deep` is passed; for `--deep`, see `$REFS/deep.md`). Both Standard Mode and `--deep` execute in **three exact LLM waves** bookended by deterministic Python setup and finalization (`$SCRIPTS/fable_pipeline.py`), supporting **Anthropic, OpenAI, Google, and xAI** models natively or via `pi-watch`:

| Vendor (`--vendor`) | Mode | Wave 1: Pre-Pass (`--prepass-model`) | Wave 2: 25-Focus Swarm (`--swarm-model`) | Wave 3: Verifier (`--verifier-model`) |
|---|---|---|---|---|
| **`anthropic`** *(default)* | **Standard** | `opus` (`claude-opus-5-5`) | `25 × haiku` (`claude-haiku-5-5`) | `4 × sonnet` shards (`claude-sonnet-5-5`) |
| **`anthropic`** | **`--deep`** | `fable` (`claude-fable-5-2`) | `25 × haiku` (`mutation probe: enabled`) | `1 × fable` (`copy-verifier.json` sandbox) |
| **`openai`** | **Standard** | `codex` (`gpt-6.1-sol`) | `25 × codex-mini` (`gpt-6-luna`) | `4 × codex` shards (`gpt-6.1-sol`) |
| **`openai`** | **`--deep`** | `codex-max` (`gpt-6.1-sol` max) | `25 × codex-mini` (`mutation probe: enabled`) | `1 × codex-max` (`copy-verifier.json` sandbox) |
| **`google`** | **Standard / `--deep`** | `gemini` (`gemini-3.1-pro`) | `25 × flash` (`gemini-3.8-flash`) | `4 × gemini` shards / `1 × gemini` |
| **`xai`** | **Standard / `--deep`** | `grok` (`grok-4.7`) | `25 × grok` (`grok-4.7`) | `4 × grok` shards / `1 × grok` |

Never skip a wave and never run a focus or verifier pass inline yourself. The shell may be zsh, so keep commands POSIX or use `bash <file>`.

---

## Step 1 — Deterministic Setup & Wave 1 Pre-Pass

If `$REVIEW_OUT_DIR/prepass-bundle.md` does not yet exist on disk, run `setup` in one Bash call:

```bash
SCRIPTS="${CLAUDE_PLUGIN_ROOT}/skills/full-code-review/scripts"
export REVIEW_OUT_DIR="${REVIEW_OUT_DIR:-$(mktemp -d -t quirk-review.XXXXXX)}"
python3 "$SCRIPTS/fable_pipeline.py" setup --run-dir "$REVIEW_OUT_DIR" \
  [--change <number> -R <owner/repo> | --branch <name> | --local] [--forge github|gitlab|none] [--since <ref>] [--seat author|reviewer] [--vendor anthropic|openai|google|xai|auto]
```

Next, perform the **Wave 1 Pre-Pass**:
- **Native harness (`Agent` tool or current model):** Read `$REVIEW_OUT_DIR/prepass-bundle.md` in one `Read` call, write `$REVIEW_OUT_DIR/prepass.json` using `Write` (`scope_intent`, `standfirst_md`, `risk`, `promise`, `structural_read`, `repo_facts`, `changed_symbols`, `hints`), and run:
  ```bash
  python3 "$SCRIPTS/fable_pipeline.py" prepare-focuses --run-dir "$REVIEW_OUT_DIR" [--vendor <vendor>]
  ```
- **Cross-vendor (`pi-watch`):** Or execute Wave 1 directly on any vendor (`openai`, `google`, `xai`, `anthropic`) via:
  ```bash
  python3 "$SCRIPTS/fable_pipeline.py" run-wave --run-dir "$REVIEW_OUT_DIR" --wave prepass --vendor <vendor>
  ```

---

## Step 2 — Wave 2: Fan Out All 25 Single-Focus Subagents in Parallel

- **Native harness (`Agent` tool):** Spawn every focus listed by `prepare-focuses` with `model: "<swarm-model>"` (`haiku` by default) and `run_in_background: true`:
  ```text
  Read and follow <REVIEW_OUT_DIR>/focus/prompts/<name>--<focus>.md in full. Work through every item in your focus, write your raw JSON and tables MD files, run the --check-focus command in the prompt, and return the one-line summary.
  ```
  Do **not** include `wait-and-prepare-fable` in the same message as the `Agent` calls (if the harness's 20-subagent concurrency limit rejects the last few focuses, spawn those remaining focuses in the next turn first).
- **Cross-vendor (`pi-watch`):** Or run all 25 focuses in parallel across any vendor (`codex-mini`, `flash`, `grok`, `haiku`) via:
  ```bash
  python3 "$SCRIPTS/fable_pipeline.py" run-wave --run-dir "$REVIEW_OUT_DIR" --wave swarm --vendor <vendor>
  ```

Then run the blocking barrier (`timeout: 600000`):

```bash
python3 "$SCRIPTS/fable_pipeline.py" wait-and-prepare-fable --run-dir "$REVIEW_OUT_DIR" --shards 4 --verifier-model <verifier-model>
```

---

## Step 3 — Wave 3: Verification, Validation, De-duplication & Finalize

- **Native harness (`Agent` tool, 4 parallel shards in Standard mode):**
  Spawn all 4 shards (`verifier-shard-1.md` .. `verifier-shard-4.md`) in parallel with `model: "<verifier-model>"` (`sonnet` by default) and `run_in_background: true`:
  ```text
  Read and follow <REVIEW_OUT_DIR>/verifier-shard-<k>.md in full. Verify, validate, and de-dupe every raw finding in your shard against the source windows in the prompt, write <REVIEW_OUT_DIR>/fable-ledger-shard-<k>.json directly using Write (keeping each group minimal: primary, duplicates, severity, production), and return a one-line summary.
  ```
  Then run:
  ```bash
  python3 "$SCRIPTS/fable_pipeline.py" finalize --run-dir "$REVIEW_OUT_DIR" --wait-shards 4 --prepass-model <prepass-model> --verifier-model <verifier-model>
  ```
- **Cross-vendor (`pi-watch`):** Or run Wave 3 + `finalize` across any vendor (`codex`, `codex-max`, `gemini`, `grok`, `fable`) via:
  ```bash
  python3 "$SCRIPTS/fable_pipeline.py" run-wave --run-dir "$REVIEW_OUT_DIR" --wave verifier --vendor <vendor>
  ```
