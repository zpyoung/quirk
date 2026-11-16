---
name: explaining-code
description: Use when asked to explain a code change or a technical design to reviewers or teammates rather than review it, such as "explain this PR", "explainer page for MR !42", "help reviewers understand this branch", "walk me through this diff", "explain this design doc", or "make a walkthrough video of this change". Covers GitHub PRs, GitLab MRs, a branch, a commit range, local uncommitted changes, and a technical design or plan. Gathers cited facts once, then builds an explainer page and, when asked, an overview video and a walkthrough video. Not for explaining how existing code works when there is no change or design to explain, for finding bugs (use full-code-review), for a video with no code change or design behind it (use making-videos), or for general HTML pages (use writing-html-artifacts).
---

# Explaining code

Turn one code change or one technical design into an explainer page for a reader who hasn't read it, plus videos when asked. Everything comes from one cited `facts.md`, so the page and the videos can't disagree.

| Output | Made | Reader | What matters most |
|---|---|---|---|
| Explainer page | Always | Reviewers, teammates | A concrete example up top, a diagram, the one decision worth weighing, what to watch after it ships |
| Overview video (60-90 s) | When asked | Anyone, including people outside the team | Passes the outside-reader filter in [gather](references/gather.md#outside-reader-filter) |
| Walkthrough video (90-150 s) | When asked | Reviewers | What it does first, then what this change adds or the design proposes, then what to act on |

Explaining isn't reviewing. Don't hunt for bugs or grade the code; when you notice a real problem while gathering, tell the user in one line and keep going.

## Targets

| Target | How you recognise it | Where the facts come from |
|---|---|---|
| GitHub PR | A `github.com/.../pull/N` URL, or `#N` in a repo whose remote is GitHub | `gh pr view`, `gh pr diff` |
| GitLab MR | A `.../-/merge_requests/N` URL, or `!N` in a repo whose remote is GitLab | `glab mr view`, `glab mr diff` |
| Branch or range | A branch name, `base..head`, or a commit SHA | `git log`, `git diff base...head` |
| Local changes | "my changes", "this diff", or nothing named in a dirty worktree | `git diff HEAD` plus untracked files |
| Design or plan | A path or URL to a design doc, spec, ADR or plan | The document, then the code it names |

If the target is ambiguous (a dirty worktree on a branch that also has an open PR), ask which one in a single multiple-choice question.

## Rules that hold throughout

- **Every line of `facts.md` cites its source**: `file:line`, a PR or MR, an issue, or the description. A line with no source becomes `[ASK: ...]` for the user. Nothing reaches the page or a script without a line in `facts.md`.
- **The code wins.** When a description, design doc or comment disagrees with the code, say what the code does and tell the user about the disagreement at stop 1.
- **A design describes proposed behaviour.** Label it as proposed on the page. Claims about the code as it stands today still need `file:line`.
- **Write nothing into the user's repo** except what `writing-html-artifacts` writes to its git-ignored `.quirk/html/`. `facts.md` lives there too, as `<slug>.facts.md`.
- **Nothing leaves the machine unasked.** Don't publish the page, post a comment, or edit a PR or MR description without a yes.

## Steps

Steps 3 and 6 are stops: show the user, then wait.

1. **Inputs.** Resolve the target from the table above. Ask once, together, as multiple choice: whether to add videos (none by default; offer the overview and the walkthrough), and whether there's a running app URL to screenshot (only when the change has a UI). making-videos is macOS only, so on another OS say the videos are out of scope and offer the page alone.
2. **Gather.** Follow [gather](references/gather.md). It writes `<slug>.facts.md`: what it does in one concrete sentence, preconditions, what this change adds or the design proposes, related changes, one worked example, the decision worth weighing, monitoring, considerations and tests, each line cited.
3. **Outline (stop 1).** Draft the page outline from [page](references/page.md), with the section set for the target type. When videos are in scope, draft each script outline from [videos](references/videos.md). Show the outlines, every `[ASK: ...]` item, and any place the code disagrees with the description. Wait for approval.
4. **Build the page.** **REQUIRED SUB-SKILL:** Use quirk:writing-html-artifacts, with the `report` template and the `explainer` layout. [page](references/page.md) says what goes in each section and which components to use. Run that skill's build, check and verify steps, then the checklist at the end of [page](references/page.md).
5. **Videos (only when asked).** **REQUIRED SUB-SKILL:** Use quirk:making-videos, once per video. Hand it the brief from [videos](references/videos.md): audience, length, the `facts.md` path as its source list, and the script structure. It runs its own stops, so step 6 is where its review page and yours meet.
6. **Review (stop 2).** Give the user the page path and the delivery note. When there are videos, add their review pages and verify results. Wait for notes, and apply them through the same sub-skill that built the piece.
7. **Deliver.** Hand over the files. Offer in one line each, and act only on a yes:
   - publishing the page as a private claude.ai artifact, when you have the Artifact tool
   - adding the page link or the walkthrough video to the PR or MR description. GitLab: upload the MP4 with the project uploads API and edit the description with `glab mr update`. GitHub has no attachment upload API, so offer the file for the user to drag in, and add only a link with `gh pr edit`.

## Common mistakes

| Mistake | What to do instead |
|---|---|
| Opening with what the page will cover | Open with what someone can now do, with real values ("a retry that waits 2, 4, then 8 seconds before giving up"). |
| Crediting all the work to the change in front of you | Read each related PR or MR and credit what its own diff did. |
| Treating the feature flag check as the decision worth a look | Pick the decision a reviewer could most reasonably want done differently. It's rarely the flag. |
| Walking through the diff file by file | Code review covers the code. Show code only for the decision worth weighing. |
| Listing test counts | List the scenarios the tests cover, grouped by the question a reviewer would ask. |
| A "what it doesn't do" section | Say what's in. Keep a considerations line only when someone must act on it. |
| Writing a design's proposal as though it already ships | Label proposed behaviour as proposed, and cite today's code for anything described as existing. |
| Reviewing instead of explaining | Mention a real problem to the user once, then keep explaining. Suggest quirk:full-code-review if they want a review. |
