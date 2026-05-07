# pi-watch

SDK-based pi runner with split streaming output:

- **stdout** = assistant text only (caller can capture cleanly with `$(...)`)
- **stderr** = `⚙ tool args` progress lines + final `✔ done`

Bypasses pi's `DefaultResourceLoader` (extensions / skills / prompts / themes /
AGENTS.md discovery) so it starts instantly regardless of cwd. The pi binary
can hang for minutes on workspaces with deep nested trees (worktrees, plugin
caches, etc.); this script avoids that path entirely.

## Setup (one-time)

```bash
cd <this-dir>
pnpm install
```

Then either invoke by absolute path, or symlink onto your PATH:

```bash
ln -s "$(pwd)/pi-watch" ~/.local/bin/pi-watch    # or any dir on $PATH
```

## Usage

```bash
pi-watch --provider <p> --model <m> [--thinking <level>] [--tools t1,t2] "<prompt>"
```

Pair with the `resolve_pi_model` bash function from the pi-dev skill so
provider/model is auth-aware:

```bash
read PI_PROVIDER PI_MODEL PI_THINKING < <(resolve_pi_model high \
    openai-codex/gpt-5.5 openai/gpt-5.5 \
    openai-codex/gpt-5.4 openai/gpt-5.4 github-copilot/gpt-5.4)

# Watch live (no capture)
pi-watch --provider "$PI_PROVIDER" --model "$PI_MODEL" --thinking "$PI_THINKING" \
    --tools read \
    "Explain the auth flow in src/auth.ts"

# Capture for the calling agent (stderr still shows progress to user)
result="$(pi-watch --provider "$PI_PROVIDER" --model "$PI_MODEL" --thinking "$PI_THINKING" \
    --tools read \
    'Read src/utils.py and list top-level functions, one per line.')"
```

## Flags

| Flag | Purpose |
|---|---|
| `--provider <name>` | Required. e.g. `openai-codex`, `anthropic`, `google`, `github-copilot` |
| `--model <id>` | Required. Literal model ID per provider (dots vs dashes — see pi-dev skill) |
| `--thinking <level>` | `off` / `minimal` / `low` / `medium` / `high` (default) / `xhigh` |
| `--tools t1,t2` | Comma-separated allowlist. Default `read,bash` |
| `--no-tools` | Disable all tools (LLM only — review/analysis mode) |

## When to prefer pi-watch over `pi --mode json`

- Calling cwd has a large/deep tree (workspaces, monorepos, worktrees) where pi's startup scan is slow or hangs.
- You want clean stdout-only capture without `tee >(jq) | jq` shell plumbing.
- You want type-safe events and direct progress hooks rather than JSONL parsing.

For tiny scripts in shallow dirs the bash `pi_watch` from the skill works fine.
