# SDK Mode (`@earendil-works/pi-coding-agent`)

For TypeScript/Node.js, skip the subprocess entirely and embed pi directly. `AgentSession` is the same object the CLI uses internally — no protocol layer to translate, full type safety.

## Install

```bash
pnpm add @earendil-works/pi-coding-agent
```

## Minimal example

```typescript
import { createAgentSession, SessionManager } from "@earendil-works/pi-coding-agent";

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

## `createAgentSession(options)`

| Option | Purpose |
|---|---|
| `cwd` | Controls `DefaultResourceLoader` discovery (extensions, skills, context files, session naming). Defaults to `process.cwd()`. |
| `agentDir` | Global config root, default `~/.pi/agent`. |
| `model` / `thinkingLevel` | Starting model configuration. |
| `tools` / `customTools` | Tool allowlist. Use factory functions like `createReadTool(cwd)` when `cwd` differs from `process.cwd()`. |
| `resourceLoader` | Inject a `DefaultResourceLoader` with overrides (see below). |
| `sessionManager` | `SessionManager.inMemory()` / `.create(cwd)` / `.continueRecent(cwd)` / `.open(path)`. |
| `settingsManager` | Override compaction, retry, etc. |

## `DefaultResourceLoader` overrides

Inject Claude Code conventions or custom prompts programmatically:

```typescript
import { DefaultResourceLoader } from "@earendil-works/pi-coding-agent";

const loader = new DefaultResourceLoader({
    // Replace system prompt (CLAUDE.md / AGENTS.md still appended)
    systemPromptOverride: () => "You are a terse assistant.",

    // Inject extra context files (e.g., CLAUDE.md content from a virtual path)
    agentsFilesOverride: (current) => ({
        agentsFiles: [
            ...current.agentsFiles,
            { path: "/virtual/CLAUDE.md", content: claudeMdContent },
        ],
    }),

    // Register .claude/commands/ as prompt templates
    promptsOverride: (current) => ({
        prompts: [...current.prompts, ...myClaudeCommands],
        diagnostics: current.diagnostics,
    }),

    // Inline extension factory
    extensionFactories: [
        (pi) => { pi.on("agent_start", () => console.log("started")); }
    ],
});
await loader.reload();

const { session } = await createAgentSession({ resourceLoader: loader });
```

## `AgentSession` API

```typescript
await session.prompt("text", { streamingBehavior: "steer" | "followUp" });
await session.steer("redirect instruction");
await session.followUp("post-completion task");
await session.compact("focus on code changes");
await session.abort();
session.dispose();

// State
session.messages;         // AgentMessage[]
session.isStreaming;      // boolean
session.model;            // Model | undefined
session.thinkingLevel;    // ThinkingLevel
session.agent.state;      // full AgentState
```

## `SessionManager` tree API

Sessions are JSONL trees with branching:

```typescript
const sm = SessionManager.open("/path/to/session.jsonl");

sm.getEntries();                         // all entries
sm.getTree();                            // full tree
sm.branch(entryId);                      // move leaf to earlier point
sm.branchWithSummary(id, "summary");
sm.createBranchedSession(leafId);        // extract path to new file
```

## Embedding the CLI run modes

If you want the CLI's run-mode behaviors inside your own harness, the SDK exports them directly:

```typescript
import {
    runPrintMode,
    runRpcMode,
    InteractiveMode,
} from "@earendil-works/pi-coding-agent";

// Single-shot print
await runPrintMode(runtime, {
    mode: "text",
    initialMessage: "Hello",
    initialImages: [],
    messages: ["Follow up"],
});

// Headless RPC server (drives stdin/stdout JSONL like the CLI)
await runRpcMode(runtime);

// Full TUI in your process
const mode = new InteractiveMode(runtime, { initialMessage: "Hello" });
await mode.run();
```

## When to use SDK mode

- Node.js host that wants full type safety and zero subprocess overhead.
- Persistent agents with session branching / fork-and-replay.
- Custom multi-agent orchestrators where the orchestrator runs as `AgentSession` and dispatches RPC subprocesses for workers.

## When NOT to use SDK mode

- Non-Node host (Python, Go, Rust, etc.) → use **RPC**.
- Throwaway script / CI step → **print mode** is shorter to write.
- You only need passive event observation → **JSON mode** is sufficient.
