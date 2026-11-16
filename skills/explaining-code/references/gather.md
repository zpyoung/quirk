# Gather: facts.md

Everything on the page and in the videos comes from `facts.md`. Gather once, write it to `<project>/.quirk/html/<slug>.facts.md`, and cite a source on every line. A line without a source either gets one or becomes `[ASK: ...]` for the user.

`facts.md` is written before any page build, and the build is what makes `.quirk/html/` ignore itself. So when that folder has no `.gitignore` yet, create one containing `*` before writing `facts.md`, or the file shows up in the user's `git status`.

## Contents

- [Read the target](#read-the-target)
- [Related changes](#related-changes)
- [Check claims against the code](#check-claims-against-the-code)
- [What facts.md holds](#what-factsmd-holds)
- [Screenshots](#screenshots)
- [Outside-reader filter](#outside-reader-filter)

## Read the target

Use `gh` for GitHub and `glab` for GitLab. Web fetches fail on private repos. Skim generated files and lockfiles; don't read them.

| Target | Metadata | Diff |
|---|---|---|
| GitHub PR | `gh pr view N -R owner/repo --json title,body,url,headRefName,headRefOid,baseRefName,files,closingIssuesReferences` | `gh pr diff N -R owner/repo` |
| GitLab MR | `glab mr view N -R group/project -F json` | `glab mr diff N -R group/project` |
| Branch or range | `git log --format='%h %s%n%b' base..head` | `git diff base...head` |
| Local changes | `git status --porcelain` | `git diff HEAD`, then read each untracked file |
| Design or plan | The document itself | None. Read the code it names instead (below) |

For a branch with no base given, use the repo's default branch (`git symbolic-ref refs/remotes/origin/HEAD`). Record the head SHA you read; the page footer cites it.

**The issue or ticket.** Look for a key or number in the title, branch name or description. Read it with `gh issue view`, `glab issue view`, or whatever tracker tool the session has. If none can reach it, ask the user for the acceptance criteria in one line.

**A design or plan.** Read the whole document. Then, for every component, file, endpoint or table it names, open the current code and note what exists today with `file:line`. That gives the page two kinds of line: what exists (cited to code) and what's proposed (cited to the document section).

## Related changes

Collect every PR or MR the description, the issue or the design links. Then search for others on the same issue key:

- GitHub: `gh pr list -R owner/repo --search "<KEY>" --state merged`
- GitLab: `glab mr list -R group/project --search "<KEY>" --merged`

Search each repo the description or design names, not just this one. For each related change, read its title and diff summary, and write one line on what that change actually merged. Don't credit all the work to whichever change the description happens to name.

## Check claims against the code

Check each behaviour claim in the description or design against the diff and the target branch. When they disagree, the code wins: write the code's behaviour in `facts.md`, add a `Disagreement:` line with both sources, and raise it at stop 1. Line numbers drift after merges, so cite them on the branch or SHA you read.

## What facts.md holds

Keep it short: a few lines per section, each ending with its source.

- **In one sentence:** What a user or caller can now do (or could, for a design), with real values. "A failed payment is retried after 2, 4 and 8 seconds before the order is marked failed", not "this change adds retry support".
- **Preconditions:** What must be true for it to apply: configuration, plan type, platform, data shape.
- **Flag:** The exact flag name and every place it's checked, plus who should and shouldn't get it. Leave the section out when there's no flag.
- **What this change adds** (or **What the design proposes**): The visible pieces first (new endpoints, controls, states, validation, CLI flags), then the code paths.
- **Related changes:** One concrete line on the whole picture, then each related PR or MR and what it did.
- **Worked example:** One input traced end to end through the new path, with the value at each step. Reviewers rely on this section more than any other.
- **Decision worth weighing:** The single choice a reviewer could most reasonably want done differently, what was chosen, what wasn't, and why, with `file:line` or the design section. For a design, also list the alternatives the document considered.
- **Monitoring:** What the code path emits. Search the touched files for metrics, logs and error reporting in the project's own idiom (for example `metrics.`, `statsd`, `logger.`, `log.`, `captureException`, `sentry`). List each with `file:line`, and say plainly which paths emit nothing. Anything you suggest watching is labelled as a suggestion. For a design, list what the document says it will emit, and label it proposed.
- **Considerations:** Only what a reviewer, an operator or the person flipping the flag must act on: rollout order, migrations, data that must not get the change, merge order with other PRs or MRs. No list of things it doesn't do.
- **Open questions** (design only): The questions the document leaves open, and any you found while reading the code.
- **Tests:** The scenarios covered, one line each, taken from the test names in the diff. No counts.
- **Spoken forms** (videos only): How to say each identifier that will be narrated. PR and MR numbers, issue keys, file names and function names are never narrated.

## Screenshots

Only for a change with a UI, and only with a running app URL at the change's head. Capture each new state in the order a user meets it (entry point, new control, error state, saved result) with Playwright if it's installed: phone width about 390 by 844 and desktop 1440 by 900, as JPEG. Don't install anything without a yes. Without Playwright or a URL, ask the user for screenshots or leave them out. Never mock a UI and present it as the product.

## Outside-reader filter

The overview video, and the page when the user wants to share it outside the team, must pass this filter: no code, no PR, MR or issue numbers, no internal service, repo or host names, no flag names unless the user says those readers know the flag, and no internal counts or customer names. Write that material only from the one-sentence summary, the preconditions, the worked example and the visible behaviour.
