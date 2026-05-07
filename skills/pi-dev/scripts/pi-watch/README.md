# pi-watch

High-level pi runner. Pass an **alias** (`codex`, `opus`, `sonnet`, `gemini`, etc.) and a prompt. The script picks the first authed model from the alias's preference ladder and runs pi via the SDK with split streaming output:

- **stdout** = assistant text only — capture cleanly with `result="$(...)"`
- **stderr** = `▶ resolved <provider>/<model>:<thinking>` header, `⚙ tool args` progress, `✔ done`

Bypasses pi's `DefaultResourceLoader` (extensions / skills / prompts / themes / AGENTS.md discovery) so it starts instantly regardless of cwd. The `pi` binary can hang for minutes in workspaces with deep nested trees (worktrees, plugin caches, monorepos); this script avoids that path entirely.

## Setup (one-time)

```bash
cd <this-dir>
pnpm install
ln -sf "$(pwd)/pi-watch" ~/.local/bin/pi-watch    # or any dir on $PATH
```

## Usage

```bash
# Primary form — alias + prompt
pi-watch --alias codex "Explain the auth flow in src/auth.ts"

# Capture for the calling agent (stderr still shows progress to user)
result="$(pi-watch --alias sonnet --tools read \
    'Read src/utils.py and list top-level functions, one per line.')"

# Restrict tools / disable tools
pi-watch --alias opus --tools read,grep "Review src/auth.ts for issues"
pi-watch --alias haiku --no-tools "Summarize this diff: $(git diff HEAD~1)"

# Override the alias's default thinking level
pi-watch --alias codex --thinking medium "Quick summary of README.md"

# List all aliases and their preference ladders
pi-watch --list-aliases

# Explicit override (skip alias resolution)
pi-watch --provider openai-codex --model gpt-5.5 --thinking xhigh "..."
```

## Aliases

| Alias | Default thinking | Routes through (newest first) |
|---|---|---|
| `codex` | `xhigh` | gpt-5.5 → 5.4 → 5.3-codex (openai-codex / openai / copilot) |
| `codex-max` | `xhigh` | gpt-5.5-codex-max → 5.4-codex-max → 5.1-codex-max |
| `codex-mini` | `medium` | gpt-5.4-mini → 5.1-codex-mini |
| `codex-spark` | `high` | gpt-5.4-codex-spark → 5.3-codex-spark |
| `sonnet` | `high` | claude-sonnet-4-7 → 4-6 |
| `opus` | `high` | claude-opus-4-7 → 4-6 |
| `haiku` | `medium` | claude-haiku-4-6 → 4-5 |
| `gemini` | `high` | gemini-3.2-pro-preview → 3.1 → 3 |
| `flash` | `medium` | gemini-flash-latest → 3-flash-preview |
| `grok` | `medium` | github-copilot/grok-code-fast-1 |

Aliases auto-upgrade as new models ship. **OpenAI pro/deep-research tiers are excluded** (`gpt-5*-pro`, `o1-pro`, `o3-pro`, `o3-deep-research`, `o4-mini-deep-research`) — ~10–30× cost, multi-minute latency. Dispatch only on explicit user request via `--provider`/`--model`. (Google's `gemini-*-pro-preview` is the standard tier, not a pro tier — it's the routing target of the `gemini` alias.)

## Tools

Built-in tool names accepted by `--tools` (comma-separated):

| Tool | Capability |
|---|---|
| `read` | Read file contents (default in pi-watch) |
| `bash` | Execute bash commands (default in pi-watch) |
| `edit` | Edit files with find/replace |
| `write` | Write files (create/overwrite) |
| `grep` | Search file contents — read-only |
| `find` | Find files by glob — read-only |
| `ls` | List directory contents — read-only |

Common combinations:

```bash
--tools read,grep,find,ls                # read-only review / analysis
--no-tools                                # pure LLM judgment, no filesystem
--tools read,grep,find,edit,write         # code edits, no shell
--tools read,bash,edit,write              # full coding worker
```

Pi has no built-in sandbox — `bash`, `edit`, and `write` operate at the caller's user level. Use git worktrees or containers for isolation when running mutating workers in parallel.

## Flags

| Flag | Purpose |
|---|---|
| `--alias <name>` | Resolve provider/model/thinking from the alias table |
| `--provider <p>` | Explicit provider (skip alias) |
| `--model <m>` | Explicit model (must come with `--provider`) |
| `--thinking <level>` | `off` / `minimal` / `low` / `medium` / `high` / `xhigh`. Overrides alias default |
| `--tools t1,t2` | Comma-separated allowlist. Default `read,bash` |
| `--no-tools` | Disable all tools — LLM only (review/analysis mode) |
| `--list-aliases` | Print alias table and exit |
| `-h`, `--help` | Print usage and exit |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Runtime error during prompt execution |
| 2 | Bad CLI args / unknown alias |
| 3 | Model not in pi-ai registry (run `pnpm update` here) |
| 4 | Cannot run `pi --list-models` (pi binary missing?) |
| 5 | No combo in alias ladder is authed/shipping |

## When to prefer pi-watch over `pi --mode json`

- Calling cwd has a large/deep tree where pi's startup scan is slow or hangs.
- You want clean stdout-only capture without `tee >(jq) | jq` shell plumbing.
- You want type-safe events and direct progress hooks rather than JSONL parsing.
- You want alias-based model selection with auto-fallback.

For non-Node hosts, multi-turn control, or worker pools writing JSONL files, see the parent skill's escape-hatch table.
