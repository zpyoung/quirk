#!/usr/bin/env node
/**
 * pi-watch — SDK-based pi runner with split streaming output.
 *
 *   stdout = assistant text only (caller can capture cleanly with $(...))
 *   stderr = "  ⚙ tool args" lines + final "  ✔ done"
 *
 * Bypasses pi's DefaultResourceLoader (extensions / skills / prompts / themes /
 * AGENTS.md discovery) so it starts instantly regardless of cwd. The pi binary
 * can hang for minutes on workspaces with deep nested trees; this script avoids
 * that path entirely.
 *
 * Caller passes resolved provider/model — the pi-dev skill's resolve_pi_model
 * bash function picks the (provider, model, thinking) triple before invoking.
 *
 * Usage:
 *   pi-watch --provider <p> --model <m> [--thinking <level>] [--tools t1,t2] "<prompt>"
 *
 * Setup (one-time):
 *   cd <this-dir> && pnpm install
 */

import { getModel } from "@mariozechner/pi-ai";
import {
    AuthStorage,
    createAgentSession,
    createExtensionRuntime,
    ModelRegistry,
    SessionManager,
    SettingsManager,
} from "@mariozechner/pi-coding-agent";

const args = process.argv.slice(2);
const opts = { provider: null, model: null, thinking: "high", tools: ["read", "bash"], prompt: null };
for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "--provider") opts.provider = args[++i];
    else if (a === "--model") opts.model = args[++i];
    else if (a === "--thinking" || a === "--thinking-level") opts.thinking = args[++i];
    else if (a === "--tools") opts.tools = args[++i].split(",").map((s) => s.trim()).filter(Boolean);
    else if (a === "--no-tools") opts.tools = [];
    else if (a.startsWith("--")) { console.error(`pi-watch: unknown flag ${a}`); process.exit(2); }
    else { opts.prompt = (opts.prompt ? opts.prompt + " " : "") + a; }
}
if (!opts.provider || !opts.model || !opts.prompt) {
    console.error('Usage: pi-watch --provider <p> --model <m> [--thinking <level>] [--tools t1,t2] "<prompt>"');
    process.exit(2);
}

const model = getModel(opts.provider, opts.model);
if (!model) {
    console.error(`pi-watch: model not found in pi-ai registry: ${opts.provider}/${opts.model}`);
    process.exit(3);
}

const resourceLoader = {
    getExtensions: () => ({ extensions: [], errors: [], runtime: createExtensionRuntime() }),
    getSkills: () => ({ skills: [], diagnostics: [] }),
    getPrompts: () => ({ prompts: [], diagnostics: [] }),
    getThemes: () => ({ themes: [], diagnostics: [] }),
    getAgentsFiles: () => ({ agentsFiles: [] }),
    getSystemPrompt: () => "You are a coding assistant. Be concise and direct.",
    getAppendSystemPrompt: () => [],
    extendResources: () => {},
    reload: async () => {},
};

const cwd = process.cwd();
const home = process.env.HOME ?? "";
const authStorage = AuthStorage.create(`${home}/.pi/agent/auth.json`);
const modelRegistry = ModelRegistry.inMemory(authStorage);
const settingsManager = SettingsManager.inMemory({
    compaction: { enabled: false },
    retry: { enabled: true, maxRetries: 2 },
});

const { session } = await createAgentSession({
    cwd,
    agentDir: `${home}/.pi/agent`,
    model,
    thinkingLevel: opts.thinking,
    authStorage,
    modelRegistry,
    resourceLoader,
    tools: opts.tools,
    sessionManager: SessionManager.inMemory(cwd),
    settingsManager,
});

session.subscribe((event) => {
    if (event.type === "message_update" && event.assistantMessageEvent?.type === "text_delta") {
        process.stdout.write(event.assistantMessageEvent.delta);
    } else if (event.type === "tool_execution_start") {
        const a = event.args ?? {};
        const summary = a.command ?? a.file_path ?? a.path ?? a.pattern ?? "";
        process.stderr.write(`  ⚙ ${event.toolName} ${summary}\n`);
    }
});

try {
    await session.prompt(opts.prompt);
    process.stdout.write("\n");
    process.stderr.write("  ✔ done\n");
    process.exit(0);
} catch (err) {
    process.stderr.write(`\n  ✖ error: ${err?.message ?? err}\n`);
    process.exit(1);
}
