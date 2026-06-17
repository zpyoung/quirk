# SCAMPER

## When to Use
Reach for SCAMPER when you already have a working solution and want a structured sweep for variants rather than a blank-page brainstorm. It is strongest mid-exploration, after the problem is well understood, when ad-hoc ideation has stalled and you suspect there are adjacent options you keep walking past. Use it to force coverage of transformation directions you would not naturally consider.

## The Method
1. Name the existing thing precisely — a feature, flow, data model, or product — and write down its current shape so each lens has a fixed target.
2. Walk it through all seven lenses in order, generating at least one concrete variant per lens: Substitute (swap a component), Combine (merge with another part or product), Adapt (borrow a mechanism from elsewhere), Modify/Magnify (change scale, frequency, or a key attribute), Put to another use (serve a different user or job), Eliminate (remove a step or assumption), Reverse (invert order, control, or direction).
3. Capture every variant without judging it; the goal is breadth, so resist editing during the pass.
4. Mark the two or three variants that are surprising yet plausible, and note for each what assumption it breaks.
5. Spin the strongest candidates into a short test or sketch before deciding which to pursue.

## Example
Starting point: a SaaS app emails each user a weekly digest of their account activity.
- Substitute: replace email with an in-app inbox feed (lower deliverability risk, higher engagement).
- Reverse: instead of the system pushing a digest, let users pull a live "what changed since I last looked" view on login.
- Eliminate: drop the fixed weekly cadence; send only when a threshold of meaningful changes accrues.
The Reverse + Eliminate combination yields the surprising-but-sound result: a change-since-last-seen panel that replaces a batch job entirely, cuts notification fatigue, and removes a whole scheduling subsystem.

## Why It Works
SCAMPER counters functional fixedness — the tendency to see an artifact only in its current role — by forcing attention onto specific dimensions of change one at a time. The seven lenses act as a divergence checklist (rooted in Osborn's brainstorming questions and Eberle's mnemonic), so coverage comes from the structure rather than from inspiration. Treating an existing solution as raw material to transform tends to surface options that open-ended ideation skips.
