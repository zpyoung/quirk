# Pi Models, Providers & Aliases

When the user says "use pi codex" or "with a pi gemini agent" they are picking a **provider + model**. This file maps natural-language references to the exact `--provider` and `--model` flag values, lists the canonical model IDs from [pi.dev/models](https://pi.dev/models), and defines short aliases so future invocations stay consistent.

## Default

If no provider/model is specified by the user, dispatch with:

```bash
pi --provider openai-codex --model gpt-5-5 --thinking-level xhigh
# canonical shorthand: openai-codex/gpt-5-5:xhigh
```

This is the project default — `openai-codex` is OpenAI's coding-tuned variant family, `gpt-5-5` is the strongest current model in that family, and `:xhigh` is the deepest reasoning level. Override only when the user explicitly names a different model.

## Trigger phrase → provider/model mapping

When the user's request includes any of these phrases (case-insensitive), resolve to the listed provider/model. Phrases that include "pi" are explicit pi invocations; bare model names ("sonnet", "opus") in a pi-context conversation should also resolve through this table.

| User phrase | `--provider` | `--model` | Default `--thinking-level` |
|---|---|---|---|
| (no model specified) | `openai-codex` | `gpt-5-5` | `xhigh` |
| `use pi`, `pi agent`, `pi subagent`, `pi worker` | `openai-codex` | `gpt-5-5` | `xhigh` |
| `pi codex`, `codex`, `with codex`, `codex agent` | `openai-codex` | `gpt-5-5` | `xhigh` |
| `pi codex max`, `codex max` | `openai-codex` | `gpt-5-1-codex-max` | `xhigh` |
| `pi codex mini`, `codex mini`, `pi mini` | `openai-codex` | `gpt-5-1-codex-mini` | `medium` |
| `pi codex spark`, `codex spark` | `openai-codex` | `gpt-5-3-codex-spark` | `high` |
| `pi gpt`, `gpt`, `gpt-5` | `openai-codex` | `gpt-5-5` | `xhigh` |
| `pi sonnet`, `sonnet`, `claude sonnet`, `pi claude` | `anthropic` | `claude-sonnet-4-6` | `high` |
| `pi opus`, `opus`, `claude opus` | `anthropic` | `claude-opus-4-7` | `high` |
| `pi haiku`, `haiku`, `claude haiku` | `anthropic` | `claude-haiku-4-5` | `medium` |
| `pi gemini`, `gemini`, `gemini pro`, `pi gemini agent` | `google` | `gemini-3-1-pro-preview` | `high` |
| `pi gemini flash`, `gemini flash`, `pi flash` | `google` | `gemini-flash-latest` | `medium` |
| `pi deepseek`, `deepseek` | `deepseek` | `deepseek-v4-pro` | `high` |
| `pi grok`, `grok`, `xai grok` | `xai` | `grok-code-fast-1` | `medium` |

If the user names a model NOT in this table, fall through to the full catalog below and use the literal model ID. If the model ID is ambiguous (e.g., "claude-4"), ask one multiple-choice clarifying question before dispatching.

## Canonical shorthand syntax

Pi accepts a single `provider/model:thinking` shorthand string with `--model` (the provider and thinking level are parsed out). Both forms below are equivalent:

```bash
pi --provider openai-codex --model gpt-5-5 --thinking-level xhigh "..."
pi --model openai-codex/gpt-5-5:xhigh "..."
```

Use whichever is clearer in context. The split form is slightly more robust in shell scripts (no quoting traps with `:`).

## Thinking levels

Recognized values: `off`, `low`, `medium`, `high`, `xhigh`.

- **`off`** — disable extended reasoning entirely (cheapest, fastest).
- **`low`** / **`medium`** — incremental reasoning budget. Default for fast models (Haiku, Flash, Codex Mini).
- **`high`** — strong reasoning. Default for balanced/strong models (Sonnet, Gemini Pro, DeepSeek Pro).
- **`xhigh`** — maximum reasoning. Default for the project default (`openai-codex/gpt-5-5`) and any review pass.

Not all models accept all levels — providers that don't support a given level silently clamp. Surface the resolved level in dispatch logs.

## Full catalog (from pi.dev/models)

These are the literal model IDs accepted by `--model` for each provider. List captured 2026-05-04; check [pi.dev/models](https://pi.dev/models) for newer entries.

### `--provider openai-codex`

```
gpt-5-1
gpt-5-1-codex-max
gpt-5-1-codex-mini
gpt-5-2
gpt-5-2-codex
gpt-5-3-codex
gpt-5-3-codex-spark
gpt-5-4
gpt-5-4-mini
gpt-5-5            ← project default
```

### `--provider anthropic`

```
claude-3-haiku-20240307
claude-3-5-haiku-20241022
claude-3-5-haiku-latest
claude-haiku-4-5-20251001
claude-haiku-4-5
claude-3-opus-20240229
claude-opus-4-20250514
claude-opus-4-0
claude-opus-4-1-20250805
claude-opus-4-1
claude-opus-4-5-20251101
claude-opus-4-5
claude-opus-4-6
claude-opus-4-7
claude-3-sonnet-20240229
claude-3-5-sonnet-20240620
claude-3-5-sonnet-20241022
claude-3-7-sonnet-20250219
claude-sonnet-4-20250514
claude-sonnet-4-0
claude-sonnet-4-5-20250929
claude-sonnet-4-5
claude-sonnet-4-6
```

### `--provider google`

```
gemini-1-5-flash
gemini-1-5-flash-8b
gemini-1-5-pro
gemini-2-0-flash
gemini-2-0-flash-lite
gemini-2-5-flash
gemini-2-5-flash-lite
gemini-2-5-flash-lite-preview-06-17
gemini-2-5-flash-lite-preview-09-2025
gemini-2-5-flash-preview-04-17
gemini-2-5-flash-preview-05-20
gemini-2-5-flash-preview-09-2025
gemini-2-5-pro
gemini-2-5-pro-preview-05-06
gemini-2-5-pro-preview-06-05
gemini-3-flash-preview
gemini-3-pro-preview
gemini-3-1-flash-lite-preview
gemini-3-1-pro-preview
gemini-3-1-pro-preview-customtools
gemini-flash-latest
gemini-flash-lite-latest
gemini-live-2-5-flash
gemini-live-2-5-flash-preview-native-audio
gemma-3-27b-it
gemma-4-26b-a4b-it
gemma-4-31b-it
```

### `--provider deepseek`

```
deepseek-v4-flash
deepseek-v4-pro
```

### `--provider xai`

```
grok-code-fast-1
```

### Other providers

The pi.dev catalog also exposes: `openai` (non-Codex line), `openrouter` (273+ models, multi-provider routing including additional Grok variants), `amazon-bedrock`, `azure-openai-responses`, `mistral`, `groq`, `cerebras`, `fireworks`, `huggingface`, `cloudflare-workers-ai`, `cloudflare-ai-gateway`, `vercel-ai-gateway`, `moonshotai` / `moonshotai-cn` (Kimi), `minimax` / `minimax-cn`, `github-copilot`. See pi.dev/models for full enumeration. Use the literal model ID from the catalog as `--model`.

## Auth requirements per provider

Each provider has its own credential. Pi resolves auth in order: `--api-key` flag → `~/.pi/agent/auth.json` → provider env var → `models.json`.

| Provider | Env var |
|---|---|
| `openai`, `openai-codex` | `OPENAI_API_KEY` |
| `anthropic` | `ANTHROPIC_API_KEY` |
| `google` (Gemini) | `GEMINI_API_KEY` |
| `deepseek` | `DEEPSEEK_API_KEY` |
| `xai` | `XAI_API_KEY` |
| `openrouter` | `OPENROUTER_API_KEY` |
| `groq` | `GROQ_API_KEY` |
| `mistral` | `MISTRAL_API_KEY` |

Subscription providers — `github-copilot`, plus Claude Pro/Max OAuth and ChatGPT Plus when used through pi — require a one-time interactive `pi /login` before headless use. They will not work in fresh `--no-session` invocations until the user has logged in once.

Verify credentials before dispatch. Fail loudly on missing env var; never modify `~/.pi/agent/auth.json`.

## Resolution algorithm (for dispatch)

```
1. If user explicitly named provider+model, use literal values from this file's tables.
2. Else if user named only a model alias (e.g., "use sonnet"), look up the alias.
3. Else if user said "use pi" with no qualifier, use default openai-codex/gpt-5-5:xhigh.
4. Always validate the provider's auth env var is set before dispatch.
5. If the user requests a model not in the alias table or catalog, treat the literal
   string as the model ID and pick the provider from context. If both are unclear,
   ask ONE multiple-choice question before dispatching.
6. Surface the resolved (provider, model, thinking-level) in any plan/dispatch log
   so the user can correct it before workers actually run.
```

## When to override the default

The `openai-codex/gpt-5-5:xhigh` default optimizes for code-quality on edits. Override when:

- **Cost-sensitive bulk work** (test generation, docs scaffolding) → `claude-haiku-4-5` or `gpt-5-1-codex-mini`.
- **Adversarial review pass** → use a *different provider* than the worker. If worker is `openai-codex`, reviewer should be `anthropic` (`claude-sonnet-4-6`) or `google` (`gemini-3-1-pro-preview`). Cross-provider review surfaces issues that same-provider review tends to miss.
- **Long-context refactors** → `gemini-3-1-pro-preview` (1M context) or `claude-opus-4-7` (1M context).
- **Speed over depth** → `gemini-flash-latest`, `gpt-5-1-codex-mini`, or `claude-haiku-4-5` with `:medium`.
