# Logic spec: companion-first brainstorming

## Status & amendments

**Status**: Draft

**Amendments:** none yet.

`quirk:brainstorming` becomes a browser-first skill. Today the visual companion is an optional tool
the agent offers for visual questions, and every other question, the approach pick, the design
review and the spec sign-off happen in the terminal. After this change, a brainstorm runs from
kickoff to hand-off inside one companion tab, and the terminal is only where you type the command,
where you can still override, and where the skill falls back when the companion can't run.

The request added three requirements partway through: use the writing-html-artifacts diagram kit,
add a chat with the agent, and let the user comment on individual elements.

## Conceptual model

A brainstorm is one **companion session**: a browser tab paired with the agent through the local
Python server. The server owns the session's state (stage, steps shown, answers, decisions, chat,
comment threads, current status) and keeps it on disk. The tab is a view of that state, so a
refresh, a closed tab or a restarted server loses nothing.

The tab has four fixed regions:

- **Step rail.** The brainstorm's stages in order: Context, Gray areas, Questions, Approaches,
  Design, Spec, Hand-off. The current stage is marked. A finished stage opens a recap of its answers,
  each with a Change control.
- **Main step area.** Whatever the agent is asking or showing now, or the live status while it
  works. Any meaningful block in it can take a pinned comment thread.
- **Chat.** The agent's whole voice: everything it would have said in the terminal appears here, and
  the user can message it at any time.
- **Decisions panel.** A collapsible list of every locked decision, on every step including the
  waiting one. Its content is what the spec's Decisions Locked section ends up holding.

The agent drives the main area one **step** at a time. Each step has a kind:

| Step kind | What the user sees | What the user does |
|---|---|---|
| Question batch | Up to about 4 related questions | Answers, skips, comments, submits once |
| Waiting | The rail plus one live status line | Waits, or cuts research short |
| Approaches | 2-3 approach cards side by side | Picks one, optionally with a comment |
| Design section | One section of the design | Looks right, or Needs changes with a comment |
| Spec review | The logic spec, markdown or interactive | Comments per section, signs off |
| Edit card | A proposed change to a locked decision and what it invalidates | Confirms or cancels |
| Hand-off | The execution skill choice | Picks one |
| Done | A closing message | Nothing; the tab can be closed |

Any step can carry text, mockups and the writing-html-artifacts diagram kit (`q-flow`, `q-schema`,
`q-sequence`, charts, and Mermaid for state charts), explorable in place. The agent uses a diagram
where a picture explains better, following the kit's own rules for which diagram fits.

Everything the user does flows back to the agent as an **event**: answers, rail edits, chat
messages, comments, and Continue without the rest.

Today's one-question companion screen keeps working unchanged, so `quirk:exploring-ideas` is
unaffected.

## Data flow

The core loop is: the agent sends a step, the user acts, the user's events wake the agent, the
agent posts status while it works, and then it sends the next step.

1. **A step arrives.** The agent hands the server a step. The server stores it, and the open tab
   switches to it in place with no reload. If the tab is in the background, its title changes to
   "(1) Your turn", the favicon gets a badge, and a short sound plays.
2. **The user acts.** They answer, comment on a block, chat, or edit an earlier answer from the
   rail. Half-typed answers are saved to the server as they go, so a refresh keeps them.
3. **The agent wakes.** Submitting a step, sending a chat message or posting a comment wakes the
   agent if it is waiting on the user, so it replies within seconds.
4. **The agent works.** It sets the status line, for example "Checking 3 approaches against
   real-world reports, 2 of 3 done, 1m 40s". Chat messages and comments sent now show as queued and
   are answered as soon as it is free. During research, Continue without the rest tells it to move
   on with whatever has returned.
5. **The next step.** The agent records what was decided in the Decisions panel, then sends the next
   step.

Changes to earlier answers go through one path. A rail Change, or a chat message such as "actually,
make skips required", becomes an edit card. The card lists what the change invalidates. Only after
the user confirms does the decision update and the affected work get redone.

The terminal stays an escape hatch. Anything typed there wins over the companion: it appears in the
chat as the user's message, and the current step updates to match.

## Key decisions and rationale

- **A new app shell instead of extending today's pages.** Batched answers, the rail, the Decisions
  panel, chat and pinned threads all need a tab that never reloads between steps. Reload-based pages
  lose focus, scroll and half-typed answers unless every screen kind carries its own save-and-restore
  code. Growing the interactive spec review app instead was rejected because it ties brainstorming to
  writing-specs and helps neither the markdown path nor exploring-ideas.
- **Batched question screens.** The skill already batches related questions so the user sees how
  they relate, so the companion carries the batch instead of splitting it.
- **Recommendations labeled, never preselected.** Every answer stays a deliberate pick, which guards
  against click-through on long sessions. The fast-track stays a free-text steer, now typed in the
  chat.
- **Chat is the agent's voice.** If narration stayed in the terminal, the user would have to watch
  two windows. Chat never changes a decision by itself, so the Decisions panel only ever reflects
  confirmed edits.
- **Comments pin to blocks, not text selections.** A block has an identity the agent can act on
  exactly, and it survives revision. A text selection's anchor breaks when the text changes.
- **The URL is printed, not opened.** The user chose to open it themselves.
- **On by default, with an opt-out.** `--terminal` keeps quick sessions quick. The fallback reuses
  the same terminal flow, so there is one non-companion path, not two.
- **A Node or pnpm build step is acceptable.** This relaxes the companion's python3-only rule for
  building the app shell.

## Behavior and scenarios

### Main path

1. **SC-1 Kickoff**
   - **Given** a project with python3 available
   - **When** the user types `/quirk:brainstorming add CSV export`
   - **Then** the agent starts the companion, prints its URL in the terminal and does not open a
     browser; ✓ the tab, once opened, shows the rail on Context and a status line naming what the
     agent is reading
   - **Screen states:**

     | Moment | Rail | Main area | Chat |
     |---|---|---|---|
     | Tab opened | Context (current) | "Reading the project and recent commits, 0m 12s" | "Starting on CSV export. I'll ask my first questions in a minute." |
     | Context done | Context ✓, Gray areas (current) | First question batch | One-paragraph summary of what the agent found |

2. **SC-2 Process choices on screen**
   - **Given** context exploration has finished and the work isn't trivial
   - **When** the agent is ready to pick gray areas
   - **Then** the adhd offer and the gray-area pick arrive together as one question batch; ✓ the
     standard areas question is unchanged when adhd runs, and adhd areas arrive as their own question
     in the next batch

3. **SC-3 Answering a question batch**
   - **Given** a batch of 3 questions, one of them text-only
   - **When** the user answers two, skips one, types in one Other box and adds a batch comment
   - **Then** one submit sends everything; ✓ the skipped question is logged as open in the spec and
     is re-asked only if a later step depends on it; ✓ the recommended option was listed first and
     labeled, and nothing was preselected
   - **Data before:** **Batch 2 (Layout)**: "Primary layout?" (Cards (Recommended), List); "Density?"
     (Compact (Recommended), Roomy); "What should the empty state say?" (text)
   - **Walkthrough:**
     1. The user picks List
     2. The user types "Roomy on desktop only" in Density's Other box
     3. The user skips the empty-state question
     4. The user writes "assume admins only" in the batch comment and submits
   - **Data after:** **Decisions panel**: ✓ Layout: List; ✓ Density: Roomy on desktop only;
     **Open items**: ✓ Empty-state copy (skipped); **Agent context**: "assume admins only"

4. **SC-4 Waiting on research**
   - **Given** the agent has started three option-validation researchers
   - **When** two have returned and the user clicks Continue without the rest
   - **Then** the agent moves on with the two results; ✓ the third option's research is marked
     pending in the spec's Industry Insights

5. **SC-5 Next step ready in the background**
   - **Given** the tab is in the background while the agent works
   - **When** the agent sends the next step
   - **Then** the tab title reads "(1) Your turn", the favicon shows a badge, and a short sound plays
     once; ✓ the title and favicon reset when the tab is focused

6. **SC-6 Picking an approach**
   - **Given** the agent proposes three approaches
   - **When** the step arrives
   - **Then** the approaches show as side-by-side cards, each with trade-offs and the research it
     cites, with the recommended card marked; ✓ the user picks one, optionally with a comment

7. **SC-7 Reviewing a design section**
   - **Given** the design has five sections
   - **When** the user marks section 2 Needs changes with a comment
   - **Then** the next step is section 2 again, with the changed passages highlighted and a one-line
     "what changed" at the top; ✓ section 3 does not appear until section 2 is marked Looks right

8. **SC-8 Signing off a markdown spec**
   - **Given** the user chose markdown for the logic spec
   - **When** the spec is written
   - **Then** the tab renders `logic.md` with a comment control on each section and a Sign off
     button; ✓ comments get replies in their threads, revisions highlight what changed, and Sign off
     is the review gate's approval

9. **SC-9 Signing off an interactive spec**
   - **Given** the user chose interactive for the logic spec
   - **When** a review stage is ready
   - **Then** the interactive review page opens inside the companion tab; ✓ each stage's export goes
     straight to the agent with no downloaded file; ✓ a signed stage-2 export is the final approval,
     as it is today

10. **SC-10 Hand-off**
    - **Given** the spec is signed off
    - **When** the hand-off step arrives
    - **Then** the user picks subagent-driven development (recommended) or executing plans; ✓ a done
      screen says implementation continues in the terminal; ✓ the companion server stops

### Edits, chat and comments

11. **SC-11 Editing an earlier answer from the rail**
    - **Given** approaches are drafted and the user opens the Gray areas recap
    - **When** the user changes "Skips allowed" to "Skips not allowed"
    - **Then** an edit card lists what the change invalidates; ✓ (a) on Confirm, the decision
      updates, the Decisions panel shows it and only the invalidated work is redone; ✓ (b) on Cancel,
      nothing changes
    - **Edit card:**

      > Changing **Skipping** from "Skips allowed, logged as open" to "Every question required".
      > This invalidates: approach B's trade-offs and design section 3.
      > [Confirm and redo] [Cancel]

12. **SC-12 Asking the agent in chat**
    - **Given** the approaches step is on screen and the agent is waiting on the user
    - **When** the user asks "why do you recommend B?" in the chat
    - **Then** the agent replies in the chat within seconds; ✓ the approaches step stays on screen
      untouched
    - **Given** instead that the agent is running research
    - **Then** the message shows as queued and is answered when the agent is free

13. **SC-13 Changing a decision in chat**
    - **Given** "Skips allowed" is locked
    - **When** the user writes "make skips required" in the chat
    - **Then** the agent replies with an edit card as in SC-11; ✓ the decision does not change until
      the user confirms

14. **SC-14 Commenting on an element**
    - **Given** a step showing approach cards, a design paragraph, a flow diagram or a spec section
    - **When** the user comments on approach B's card
    - **Then** a thread pins to that card and the agent replies in the thread; ✓ the chat gets a
      one-line pointer that jumps to the thread; ✓ if the card is later revised, the thread stays
      attached and shows whether the revision addressed it

15. **SC-15 Fast-track from chat**
    - **Given** all six essentials are covered and questions remain
    - **When** the user writes "go with your recommendations" in the chat
    - **Then** every remaining open question resolves to its recommended option and is logged as
      "assumed — fast-tracked"; ✓ the design steps still follow and still need approval
    - **Given** instead that an essential is still open
    - **Then** the agent names the open essentials in the chat and asks them as the next batch

### Edges and fallback

16. **SC-16 Typing in the terminal**
    - **Given** the companion is showing a question batch
    - **When** the user types an answer in the terminal
    - **Then** the typed answer wins; ✓ it appears in the chat as the user's message and the step
      updates to match

17. **SC-17 Refresh or closed tab**
    - **Given** the user has half-answered a batch
    - **When** they close the tab and reopen the URL
    - **Then** the current step, the half-typed answers, the chat and the threads are restored

18. **SC-18 Server stopped**
    - **Given** the companion server stopped, from idle or a crash
    - **When** the tab is still open
    - **Then** the tab shows "Paused, reconnecting"; ✓ on its next step the agent restarts the
      server from the saved session, and the tab picks up where it was

19. **SC-19 Companion can't run**
    - **Given** python3 is missing, or the browser can't reach the server's port
    - **When** the user starts a brainstorm
    - **Then** the agent says why once in the terminal, then runs the same brainstorm in the terminal
      with today's question flow; ✓ remote setups can still use `--host` and `--allow-host` when the
      user asks

20. **SC-20 Choosing the terminal**
    - **Given** any project
    - **When** the user types `/quirk:brainstorming --terminal add CSV export`
    - **Then** no companion starts and the brainstorm runs in the terminal flow from the first
      question; ✓ in that flow, questions go through orca ask or AskUserQuestion as they do today

## Scope and non-goals

**In scope:**

- Rewriting `quirk:brainstorming` companion-first. The companion offer step goes away. The terminal
  flow stays as the `--terminal` opt-out and the fallback.
- A new companion app shell: one persistent tab with the rail, step area, chat and Decisions panel.
- Server-side session state that survives a refresh, a closed tab and a server restart.
- The step kinds above, including the diagram kit inside any step.
- Spec review in the tab for both formats; the interactive review page posts back instead of
  downloading.
- Chat and pinned comment threads. These are built in the last phase.
- Inside a companion brainstorm, the companion replaces orca ask for brainstorm questions.

**Not in scope:**

- `quirk:exploring-ideas` and `quirk:adhd` behavior. Both keep today's companion as it is.
- Running implementation in the companion. The session ends at the hand-off step.
- More than one person in a session, or any access model beyond today's localhost, Host-check and
  nonce rules.
- Desktop notifications. The ready signal is the tab title, favicon and sound.

## Decisions Locked

**Question shape**

- Clarifying questions arrive as a batched form: up to about 4 related questions with one submit.
- Every choice question has its own Other box, text-only questions are allowed, and the submit area
  has a comment for the whole batch.
- The recommended option is labeled and listed first, never preselected.
- Any question can be skipped. A skip is logged as open and re-asked only if something depends on
  it.
- Each question can carry its own mockup, diagram or per-option previews.

**Waiting and progress**

- A step rail plus one live status line, and the tab advances by itself when the next step is
  ready.
- The ready signal for a background tab is a title change, a favicon badge and a sound.
- A Continue without the rest button appears during research; skipped research is marked pending.
- The status is one plain line: activity, counts and elapsed time.

**Approaches, design and spec review**

- Approaches are side-by-side cards.
- The design is shown one section per screen, with Looks right or Needs changes plus a comment.
- A revision highlights the changed passages and adds a one-line "what changed".
- Both spec formats stay, and both are reviewed and signed off inside the companion.

**Going back and correcting**

- Finished stages on the rail open a recap with a Change control on each answer.
- An edit that invalidates later work shows what it invalidates and waits for confirmation.
- A collapsible Decisions panel appears on every step.

**Terminal boundary and fallback**

- The companion is on by default, with a `--terminal` opt-out.
- The agent prints the URL; it does not open the browser.
- If the companion can't run, the agent says why once and falls back to the terminal flow.
- Typed terminal input wins, and the companion catches up.
- The session ends on a hand-off step (pick the execution skill), then a done screen.

**Chat, comments and diagrams** (added mid-session)

- Chat is the agent's whole voice, and the user can message it at any time.
- A message sent while the agent is busy shows as queued and is answered when it is free.
- A chat message that changes a decision becomes an edit card the user confirms.
- Any meaningful block can be commented on: a question, an option, an approach card, a design
  paragraph, a diagram node or a spec section.
- A comment opens a thread pinned to its block, the agent replies in the thread, and the chat gets
  a one-line pointer.
- The diagram kit is available on every step, explorable, and used where a picture explains better.

**Scope and constraints**

- Brainstorming only; exploring-ideas keeps working as it is.
- Inside a companion brainstorm, the companion replaces orca ask for brainstorm questions.
- A Node or pnpm build step is acceptable.
- One logic spec for the whole experience. Execution builds it in phases, with chat and comments
  last.
- Done means a real brainstorm runs from the first screen to the execution pick with no terminal
  input, and the decisions it shows match the spec it writes.
- The new app shell (approach B) was chosen over extending today's pages (A) or growing the
  interactive spec review app (C).

## Industry Insights

- **Batching versus one question at a time is unsettled in shipped tools.** Claude Code and Gemini CLI
  batch 1 to 4 questions per call. Superpowers brainstorming and spec-kit's clarify step ask one at a
  time. Users have asked for tabbed questionnaires and for a comment that covers the whole set.
  [Claude Agent SDK user input](https://code.claude.com/docs/en/agent-sdk/user-input),
  [Gemini CLI ask_user](https://geminicli.com/docs/tools/ask-user/),
  [spec-kit clarify](https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/clarify.md),
  [claude-code #80781](https://github.com/anthropics/claude-code/issues/80781)
- **Waits over about 10 seconds need specific status and a way out.** "Thinking…" says little, so
  name the operation. "Waiting on you" should look different from "working".
  [NN/G response times](https://www.nngroup.com/articles/response-times-3-important-limits/),
  [Setproduct agent UI patterns](https://www.setproduct.com/blog/ai-agent-ui-design-patterns)
- **Too many prompts train click-through.** Ask fewer, larger questions and show exactly what an
  approval covers. [Setproduct agent UI patterns](https://www.setproduct.com/blog/ai-agent-ui-design-patterns)
- **Users who can't correct an earlier answer feel trapped.** Save each answer as it is given,
  allow returning to any earlier answer, and re-ask only what an edit invalidates.
  [NN/G user control and freedom](https://www.nngroup.com/articles/user-control-and-freedom/),
  [NN/G wizards](https://www.nngroup.com/articles/wizards/)
- **A pending question must be tied to its exact request and survive reconnects.** Approvals
  replayed against a stale session got lost in a shipped agent.
  [Hermes Agent #137640](https://github.com/NousResearch/hermes-agent/issues/137640),
  [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- **Background tabs and stale connections drop updates.** Resync the full state when a tab becomes
  visible again instead of trusting the stream.
  [SSE connection status UI](https://www.server-sent-events.com/frontend-consumption-client-patterns/error-handling-and-reconnection-ux/showing-connection-status-in-the-ui/),
  [SSE background tabs](https://www.server-sent-events.com/frontend-consumption-client-patterns/mobile-background-tab-handling/)
- **Reload-based pages break on form controls.** Pages that poll and refresh lose focus, scroll and
  in-progress input unless the server owns all state. These are known htmx failure modes.
  [htmx morphing](https://four.htmx.org/docs/morphing-swaps-guide),
  [htmx #4030](https://github.com/bigskysoftware/htmx/issues/4030),
  [Unpoly polling](https://unpoly.com/learn/polling)
- **Typed components beat generic JSON-schema forms for rich steps.** Version the step contract and
  reject unknown kinds. [A2UI and MCP Apps](https://developers.googleblog.com/a2ui-and-mcp-apps/),
  [A2UI v0.9](https://developers.googleblog.com/a2ui-v0-9-generative-ui/),
  [MCP elicitation](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation)
- **Mode flags multiply, which counts against growing one app into two workflows.**
  [Fowler, feature toggles](https://martinfowler.com/articles/feature-toggles.html)
- **The closest prior art is Superpowers' visual companion.** It uses a file-based channel, a
  "continuing in terminal" waiting screen, and a paused overlay with auto-reconnect.
  [Superpowers visual companion](https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/visual-companion.md)

## Deferred Ideas

- `quirk:exploring-ideas` adopts the new app shell.
- Execution progress shown in the companion after hand-off.
- `[tech-spec]` How chat messages and comments wake an agent that is blocked on `wait`.
- `[tech-spec]` Push versus polling between the server and the tab.
- `[tech-spec]` How the prebuilt app shell is built and shipped in the plugin.
- `[tech-spec]` Versioning the step contract between agent and tab.
- `[tech-spec]` Reusing interactive-spec components and the design system in the shell.
- `[tech-spec]` Server threading under concurrent polling, posting and chat.
- `[tech-spec]` Keeping `SKILL.md` within its 400-line budget, and updating the brainstorming and
  adhd tests that pin the current offer and `AskUserQuestion` wording.

## Glossary

- **Companion session**: one brainstorm's tab, server and saved state.
- **Step**: what the agent is currently asking or showing in the main area.
- **Step kind**: the type of a step, such as question batch, waiting or edit card.
- **Stage**: one entry on the rail. A stage spans one or more steps.
- **Edit card**: a step that proposes a change to a locked decision and lists what it invalidates.
- **Thread**: a comment conversation pinned to one block.
- **Terminal flow**: today's question flow in the terminal, used by the opt-out and the fallback.
- **Fast-track**: the user choosing, in the chat, to accept recommended defaults for everything
  still open once the six essentials are covered.
