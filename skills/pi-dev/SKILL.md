---
name: pi-dev
description: Use when invoking the pi coding agent (binary `pi`, package `@mariozechner/pi-coding-agent`) in headless mode — print, JSON-stream, RPC subprocess, or in-process SDK. Triggers on "use pi", "use pi dev", "pi agent", "pi subagent", "run pi", "pi headless", "pi codex", "pi gemini", "pi sonnet", "pi opus", "pi haiku", "pi grok", "pi deepseek", "pi --print", "pi --mode json", "pi --mode rpc", or any request to dispatch / embed / script the pi coding agent. Picks the right mode, resolves provider/model aliases, and supplies a working invocation recipe.
---

# pi-dev

## Overview

Pi has four run modes. One is interactive; the other three are headless and used for scripts, CI, embedded agents, and multi-agent orchestration. There is also a TypeScript SDK that runs Pi in-process.

Use this skill when the user asks you to run `pi` non-interactively, embed pi in a script or app, or build orchestration on top of pi.

## Mode selection

Pick a mode by asking: *what is calling pi, and what does it need from the response?*

| Caller | Needs | Mode |
|---|---|---|
| Bash script, CI step, one-off task | Final answer text only | **Print** (`pi -p`) |
| Tooling that watches tool calls / streaming deltas | Events as JSONL | **JSON stream** (`pi --mode json`) |
| Non-Node host (Python, Go, Rust) needing multi-turn control | Bidirectional command/event protocol | **RPC** (`pi --mode rpc`) |
| Node.js app with type safety, same-process | TS API, no subprocess | **SDK** (`@mariozechner/pi-coding-agent`) |

If the user is building a multi-agent system: orchestrator runs as SDK or interactive session; workers run as `pi --mode rpc --no-session` subprocesses, coordinated via JSONL.

## Provider & model selection

**Default**: `openai-codex / gpt-5-5` with thinking level `xhigh`. Pass as either split flags or shorthand:

```bash
pi --provider openai-codex --model gpt-5-5 --thinking-level xhigh "..."
# or shorthand:
pi --model openai-codex/gpt-5-5:xhigh "..."
```

When the user names a model in natural language, resolve via this alias table:

| User says | `--provider` | `--model` | Default thinking |
|---|---|---|---|
| (no model) / "use pi" / "pi codex" / "codex" | `openai-codex` | `gpt-5-5` | `xhigh` |
| "codex max" | `openai-codex` | `gpt-5-1-codex-max` | `xhigh` |
| "codex mini" / "pi mini" | `openai-codex` | `gpt-5-1-codex-mini` | `medium` |
| "pi sonnet" / "sonnet" / "claude" | `anthropic` | `claude-sonnet-4-6` | `high` |
| "pi opus" / "opus" | `anthropic` | `claude-opus-4-7` | `high` |
| "pi haiku" / "haiku" | `anthropic` | `claude-haiku-4-5` | `medium` |
| "pi gemini" / "gemini" / "gemini pro" | `google` | `gemini-3-1-pro-preview` | `high` |
| "pi flash" / "gemini flash" | `google` | `gemini-flash-latest` | `medium` |
| "pi deepseek" / "deepseek" | `deepseek` | `deepseek-v4-pro` | `high` |
| "pi grok" / "grok" | `xai` | `grok-code-fast-1` | `medium` |

Thinking levels: `off`, `low`, `medium`, `high`, `xhigh`. Providers that don't support a level silently clamp.

For the full catalog (all model IDs per provider, per-provider auth env vars, resolution algorithm, when to override the default): `reference/models.md`.

## Critical preflight (before any mode)

Run these checks before issuing a pi invocation:

1. **`pi --version` ≥ 0.65.1.** Older versions have a JSON+piped-stdin regression where `--mode json` falls back to plain text when stdin is piped. Upgrade with `pnpm add -g @mariozechner/pi-coding-agent`.
2. **Auth.** Pi resolves credentials in this order: `--api-key` flag → `~/.pi/agent/auth.json` → provider env var (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`) → `models.json`. Never modify `~/.pi/agent/auth.json` — it is the user's. Subscription providers (Claude Pro/Max OAuth, ChatGPT Plus, Copilot) require a one-time interactive `pi /login` first.
3. **No `--cd` flag.** Pi has no working-directory flag. The caller MUST `cd` before invoking pi.
4. **No built-in sandbox.** Pi workers can write anywhere under the user's permissions. Filesystem isolation is the caller's responsibility (e.g., git worktrees, containers).
5. **No built-in timeout.** Wrap with `gtimeout` (macOS, from `brew install coreutils`) or `timeout` (Linux).
6. **Exit codes are undocumented.** Don't trust `$?` alone — also inspect stderr and the JSONL stream for completion markers and error patterns.

## Print mode — the one-liner

Fastest path to headless. Prints final assistant text and exits.

```bash
pi -p "Summarize this codebase"
cat README.md | pi -p "Summarize this text"
git diff HEAD~1 | pi -p "Write a conventional commit message for this diff"
pi -p @prompt.md @screenshot.png "Answer this"
```

**Critical flags for automation:**
- `--no-session` — ephemeral, nothing persisted to `~/.pi/agent/sessions/`
- `--offline` — suppress startup network/update check
- `--tools read,bash,edit,write` — allowlist built-in tools
- `--no-tools` — LLM only, no tool execution (good for analysis/review)
- `--model sonnet:high` — provider/model/thinking shorthand
- `--system-prompt "..."` / `--append-system-prompt "..."` — replace or append the system prompt
- `--no-context-files` — skip `AGENTS.md` / `CLAUDE.md` discovery (use only when conventions conflict)

**Piped stdin caveat (pre-0.65.1):** if `--mode json` + piped stdin misbehaves, use `@file` arguments instead.

Full deep-dive: `reference/print-mode.md`.

## JSON event stream — observable one-shots

Like print mode, but streams JSONL events on stdout (final text, tool calls, thinking deltas). Plain text goes to stderr.

```bash
pi --mode json "List files" 2>/dev/null | jq -c 'select(.type == "message_end")'

# Extract just the final assistant text:
pi --mode json "Explain the auth flow" \
  | jq -r 'select(.type=="agent_end") | .messages[] | select(.role=="assistant") | .content[] | select(.type=="text") | .text'
```

**Event sequence** (one JSON object per line):

```
session (header, first line)
agent_start
  turn_start
    message_start
    message_update      ← streaming text/thinking/tool deltas
    message_end
    tool_execution_start
    tool_execution_update
    tool_execution_end
  turn_end
agent_end               ← final messages
```

Full event reference: `reference/json-mode.md`.

## RPC mode — bidirectional control

Headless, fully programmatic. Drive pi from any language via JSONL on stdin/stdout.

```bash
pi --mode rpc --no-session [--provider anthropic --model sonnet:high]
```

**Protocol:** one JSON object per line, `\n` only. Commands → stdin. Responses (`type: "response"`) and events → stdout. Optional `id` field correlates request/response.

**Key commands:** `prompt`, `steer`, `follow_up`, `abort`, `bash`, `new_session`, `switch_session`, `get_state`, `get_messages`, `set_model`, `set_thinking_level`, `compact`, `get_commands`, `get_session_stats`, `fork`.

**Streaming behavior:** sending `prompt` while the agent is mid-stream requires `streamingBehavior: "steer" | "followUp"` or it errors.

**Node.js framing trap:** **do not use Node's `readline`** — it splits on Unicode line separators U+2028/U+2029 in addition to `\n`, which corrupts the protocol. Use a `StringDecoder`-based buffered reader splitting only on `\n`.

Minimal Python and Node examples + the full command reference: `reference/rpc-mode.md`.

## SDK mode — in-process Node.js

Same `AgentSession` object the CLI uses internally. Skip the subprocess.

```bash
pnpm add @mariozechner/pi-coding-agent
```

```typescript
import { createAgentSession, SessionManager } from "@mariozechner/pi-coding-agent";

const { session } = await createAgentSession({
    sessionManager: SessionManager.inMemory(),
});

session.subscribe((event) => {
    if (event.type === "message_update" &&
        event.assistantMessageEvent.type === "text_delta") {
        process.stdout.write(event.assistantMessageEvent.delta);
    }
});

await session.prompt("What files are in the current directory?");
```

**Key building blocks:**
- `createAgentSession({ cwd, agentDir, model, thinkingLevel, tools, customTools, resourceLoader, sessionManager, settingsManager })`
- `DefaultResourceLoader` — override system prompt, inject context files, register `.claude/commands/` as prompts, attach extension factories
- `SessionManager.inMemory() | .create(cwd) | .continueRecent(cwd) | .open(path)` — sessions are JSONL trees that can branch
- `AgentSession`: `prompt(text, { streamingBehavior })`, `steer`, `followUp`, `compact`, `abort`, `dispose`, plus state (`messages`, `isStreaming`, `model`, `thinkingLevel`, `agent.state`)
- `runPrintMode(runtime, opts)` / `runRpcMode(runtime)` / `new InteractiveMode(runtime, opts)` — embed any of the CLI run modes inside your harness

Full SDK API + ResourceLoader override patterns: `reference/sdk-mode.md`.

## Multi-agent orchestration

For teams of pi workers (decompose → dispatch → review → integrate → test):
- Workers: `pi --mode rpc --no-session` subprocesses, one per specialized role
- Orchestrator: SDK `AgentSession`, or another `pi --mode json` shell
- Coordination: orchestrator sends `prompt`, reads `agent_end` for results
- Parallel: `Promise.all` over RPC subprocesses, or tmux session matrix
- Three-tier (orchestrator → team leads → workers) is supported — pi has no opinion on topology

Patterns + pitfalls: `reference/orchestration.md`.

## Environment variables

| Variable | Effect |
|---|---|
| `PI_CODING_AGENT_DIR` | Override config dir (default `~/.pi/agent`) |
| `PI_CODING_AGENT_SESSION_DIR` | Override session storage location |
| `PI_OFFLINE` | Disable startup network operations (update checks, telemetry) |
| `PI_SKIP_VERSION_CHECK` | Skip pi.dev version probe |
| `PI_TELEMETRY` | Enable/disable install telemetry (`1`/`0`) |
| `PI_CACHE_RETENTION` | Set `long` for extended prompt cache |
| `ANTHROPIC_API_KEY` (etc.) | Picked up automatically; `--api-key` overrides |

## Canonical headless dispatch recipe

When invoking pi from a script, this is the safe form. It survives paths with spaces, works under zsh AND bash, captures pipeline exit codes correctly, and writes pure JSONL to the events file.

```bash
PI_WT="$REPO_ROOT"               # or per-worker worktree
PI_OUT="$SLICE_DIR/events.jsonl"
PI_ERR="$SLICE_DIR/stderr.log"
PI_PROMPT="$SLICE_DIR/prompt.txt"
PI_TIMEOUT=900                   # seconds; 1800 for complex
PI_PROVIDER=openai-codex         # default; resolve from alias table for user-named models
PI_MODEL=gpt-5-5                 # default; pair with --thinking-level xhigh
PI_THINKING=xhigh

bash -c '
  cat "$1" \
  | gtimeout --kill-after=30 --foreground "$2" \
      bash -c "
        cd \"\$1\" && pi \
          --mode json \
          --no-session \
          --offline \
          --provider \"\$2\" \
          --model \"\$3\" \
          --thinking-level \"\$4\"
      " _ "$3" "$4" "$5" "$6" \
    > "$7" 2> "$8"
  echo "${PIPESTATUS[1]}" > "$9"
' _ "$PI_PROMPT" "$PI_TIMEOUT" "$PI_WT" "$PI_PROVIDER" "$PI_MODEL" "$PI_THINKING" \
    "$PI_OUT" "$PI_ERR" "$SLICE_DIR/exit_code"
```

Why each piece:
- Outer `bash -c` so `PIPESTATUS` works regardless of caller shell (zsh's `pipestatus` is incompatible).
- Inner `bash -c "... cd \"\$1\" && pi ..." _ "$path"` because pi has no `--cd` flag; positional args avoid shell-quoting hell on paths with spaces.
- `gtimeout --kill-after=30 --foreground "$T"` enforces wall-clock cap, escalates SIGTERM → SIGKILL after 30s, keeps signals reaching pi (not just the wrapper).
- `--mode json --no-session --offline` is the parallel-safe ephemeral combo.
- For review passes: add `--no-tools` so the reviewer can't edit files (pi's closest substitute for a read-only sandbox).
- Linux: replace `gtimeout` with `timeout`.

## Failure detection (do NOT trust `$?` alone)

Apply rules in this order, first match wins:

1. **Auth failure** in stderr OR events → ABORT entire run.
   - OpenAI: `Incorrect API key`, `Invalid API key`, HTTP 401 + `invalid_request_error`
   - Anthropic: `invalid x-api-key`, `authentication_error`
   - Google/Gemini: `API key not valid`, `INVALID_ARGUMENT` (case-sensitive), HTTP 400
   - DeepSeek: `Authentication Fails`
   - Generic: `401 Unauthorized`, `unauthorized`
2. **Billing failure** (`insufficient_quota`, `quota.exceeded`) → ABORT.
3. **Rate limit** (HTTP 429, `rate_limit_error`, `rate_limit_exceeded`, `RESOURCE_EXHAUSTED`, `too many requests`) → RETRIABLE (single retry with 60s backoff).
4. `events.jsonl` missing/empty → FAIL (worker hung or never started).
5. Stream is only `error` events with no completion marker → FAIL.
6. Exit code 124 from `gtimeout` → TIMED_OUT, mark FAIL (no auto-retry beyond plan caps).
7. Worker ran but `git diff --cached --quiet` after `git add -A` → no edits made; FAIL on cycle 1, possibly DEMOTE on cycle 2 if cycle 1 already produced a good commit.

Auth/billing failures hit every worker the same way — short-circuit the whole run; do not consume retry budget.

## Token usage extraction (best-effort)

Pi's `--mode json` event schema for token usage is not officially stable. Scan events for any object exposing `usage` / `tokens` / `inputTokens` / `outputTokens` / `contextUsage`:

```bash
jq -s '
  map(select((.usage // .tokens // .contextUsage) != null))
  | map(.usage // .tokens // .contextUsage)
' events.jsonl 2>/dev/null
```

If nothing matches, mark token usage as `not captured` rather than fabricating numbers.

## Reviewer JSON parse fallback

When a reviewer worker is asked for JSON output, parse with this cascade:

1. `JSON.parse(content)` over the whole assistant message.
2. Search for the first ` ```json … ``` ` fenced block; parse its body.
3. Search for the first balanced `{ … }` block; parse.
4. On total failure: synthesize `{ verdict: "NEEDS_FIX", findings: [{ severity: "HIGH", issue: "reviewer output unparseable" }] }`. Never count an unparseable response as a PASS.

## Don't

- **Don't** modify `~/.pi/agent/auth.json` or `~/.pi/agent/AGENTS.md`.
- **Don't** use Node's `readline` to parse RPC stdout — see RPC framing trap.
- **Don't** rely on pi's session resume (`--continue` / `--session <id>`) for reproducibility — re-dispatch with prior context inlined into the prompt instead.
- **Don't** dispatch parallel `git worktree add` calls — they race on `.git/config.lock`. Serialize creation; only the workers run parallel.
- **Don't** run multiple workers in the same working directory — pi has no sandbox; they will overwrite each other.
- **Don't** default to `--no-context-files`. Workers should inherit `AGENTS.md` / `CLAUDE.md` unless conventions conflict.
- **Don't** use `pi --print` without `--no-session` and `--offline` in CI/scripts — you'll persist sessions and probe the network.
