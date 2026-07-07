# Security & Trust for Skills

**Load this when:** authoring a skill others might run, or deciding whether to install a skill you didn't write.

Skills are trusted-by-proxy: once a skill loads, its instructions steer the agent, and the agent's actions look like legitimate user actions. That bypasses most traditional defenses. This applies both to skills you write (don't surprise your future self or teammates) and skills you install (you're granting instruction-level trust). Practices below are durable — verify current platform specifics separately, since mechanics change.

## Authoring: the principle of least surprise

- A skill's actual behavior should not surprise someone who read its description. No hidden side effects, no undocumented network calls, no capabilities the description doesn't imply.
- Don't treat frontmatter tool declarations as a security boundary. Declaring which tools a skill "uses" is documentation, not a sandbox — don't rely on it to contain a skill's blast radius; verify behavior instead.
- For side-effecting/dangerous skills (deploy, delete, publish), gate behind explicit invocation rather than silent auto-trigger — and confirm the gating actually works in your environment before trusting it.
- Keep bundled scripts and any test/fixture files honest: they can execute with full local permissions, so they are part of your skill's trust surface even if the SKILL.md looks clean.

## Consuming: vet before you trust

Before installing a third-party skill, treat it like running someone's script:

- **Read every file, not just SKILL.md** — including bundled scripts and test/fixture files. Executable content anywhere in the bundle runs with your permissions.
- **Scan for hidden/invisible content.** Instructions can be smuggled in invisible Unicode, HTML comments, or otherwise-unreadable markup that a human skim misses but the model reads. If a file looks shorter than its byte size suggests, be suspicious; use a tool that surfaces non-printing characters.
- **Check that stated purpose matches actual instructions.** A skill that claims to "format code" but instructs reading credentials or hitting an unfamiliar endpoint is a red flag.
- **Prefer sources you can inspect and that are maintained.** There is no official verified marketplace or signing; automated scanners help but miss things (notably code hidden in test files) — a clean scan is not proof of safety.
- **Default to team-private.** Commit skills you rely on to your own repo (`.claude/skills/`) rather than pulling from unvetted catalogs.
