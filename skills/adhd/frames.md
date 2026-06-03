# Divergent Thinking Frames

This document describes the 15 thinking frames used in the ADHD divergent-ideation process. Each frame provides a different lens for generating non-obvious options.

## Frame 1: Constraint Inversion

**Principle**: Remove a constraint you assumed was fixed, or add a constraint that doesn't currently exist.

**Prompt**: "What if [assumed constraint] wasn't actually a constraint? What if we added [new constraint] to force a different solution?"

**Example**: "We need a fast search feature" → Remove speed constraint → "What if search was deliberately slow but surfaced better results?" or Add constraint → "What if search had to work offline?"

## Frame 2: Opposite Day

**Principle**: Do the exact opposite of what seems natural or obvious.

**Prompt**: "What's the most counterintuitive or opposite approach to [problem]?"

**Example**: "Improve user retention" → Opposite → "Make it harder to use the product" → Insight: Add friction to high-value actions to increase perceived value

## Frame 3: Time Travel

**Principle**: Project the problem 10 years forward or backward and solve it from that vantage point.

**Prompt**: "How would we solve [problem] in 2036? How would we have solved it in 2016?"

**Example**: "Build a chat feature" → 2036 → "Assume AI handles most communication" → Design for AI-assisted/AI-mediated interaction

## Frame 4: Cross-Domain Analogy

**Principle**: Borrow solutions from a completely unrelated domain.

**Prompt**: "How does [unrelated industry/field] handle similar challenges?"

**Example**: "Improve code review process" → Hospital surgery protocols → Implement pre-review checklists and peer observation

## Frame 5: Stakeholder Rotation

**Principle**: Become a different stakeholder and solve from their perspective.

**Prompt**: "If I were [end user / admin / API consumer / support team / competitor], what would I want?"

**Example**: "Design an admin dashboard" → Become support team → "I need to see common failure patterns at a glance, not individual events"

## Frame 6: Failure Pre-Mortem

**Principle**: Assume the solution failed spectacularly. Work backward to identify what went wrong.

**Prompt**: "It's 6 months later and [solution] failed catastrophically. What happened?"

**Example**: "Launch new feature" → Pre-mortem → "Users hated it because we didn't consider mobile" → Design mobile-first from start

## Frame 7: Sensory Shift

**Principle**: Change the primary sense or modality through which the problem is experienced.

**Prompt**: "What if [problem] had to be solved through [audio / touch / movement / spatial arrangement] instead of [current modality]?"

**Example**: "Debug tool for API errors" → Audio → "What if errors made different sounds?" → Insight: Pattern recognition through audio cues

## Frame 8: Scale Extremes

**Principle**: Imagine the problem at 10× scale (bigger) or 1/10× scale (smaller).

**Prompt**: "What if we had 10× more [users/data/time/budget]? What if we had 1/10×?"

**Example**: "Design comment system" → 10× users → Need heavy moderation and threading → 1/10× → Direct replies work fine, skip complexity

## Frame 9: Role Reversal

**Principle**: Swap the roles of actors in the system.

**Prompt**: "What if [actor A] did what [actor B] normally does?"

**Example**: "Teacher-student platform" → Reverse → "Students teach teachers" → Peer learning platform, students curate content for faculty

## Frame 10: Material Substitution

**Principle**: Replace a core material/technology with something fundamentally different.

**Prompt**: "What if [current tech/material] was replaced with [different tech/material]?"

**Example**: "Build a REST API" → Replace with GraphQL → Different trade-offs around flexibility vs. caching

## Frame 11: Process Reversal

**Principle**: Reverse the order of steps in a process.

**Prompt**: "What if we did [final step] first and [first step] last?"

**Example**: "Write-test-deploy" → Reverse → "Deploy-test-write" → Feature flags + prod testing with real data

## Frame 12: Success Post-Mortem

**Principle**: Assume the solution succeeded beyond expectations. Work backward to identify what went right.

**Prompt**: "It's 6 months later and [solution] exceeded all goals. What did we do right?"

**Example**: "Launch product" → Post-mortem → "Users loved the onboarding" → Invest heavily in first-run experience

## Frame 13: Beginner's Mind

**Principle**: Approach the problem as if you know nothing about the domain.

**Prompt**: "If someone with zero experience in [domain] solved this, what obvious-to-them solution would they suggest?"

**Example**: "Optimize database queries" → Beginner → "Why not just cache everything?" → Insight: Aggressive caching layer might work

## Frame 14: Expert Blind Spots

**Principle**: Identify what experts assume but beginners question.

**Prompt**: "What do domain experts take for granted that might not be true?"

**Example**: "Web app architecture" → Expert assumption → "Must use a database" → Insight: Static site generation for read-heavy content

## Frame 15: Adjacent Possible

**Principle**: What's one step beyond current capabilities but not science fiction?

**Prompt**: "What could we do with tech/resources that will exist in 1-2 years but doesn't quite work today?"

**Example**: "Real-time collaboration" → Adjacent → "Browser-native P2P with WebRTC" → Insight: Skip server infrastructure for certain features

---

## Usage in ADHD Process

During the Diverge phase, select 5-7 frames most relevant to your decision context. Spawn parallel Task agents, each applying one frame to generate 3-5 raw ideas.

**Frame selection heuristics**:
- **Architectural decisions**: Frames 3, 8, 10, 14, 15
- **UX/product decisions**: Frames 2, 5, 7, 9, 13
- **Process improvements**: Frames 1, 4, 6, 11, 12
- **High uncertainty**: Frames 2, 6, 12, 14

Mix frames from different categories for maximum divergence.
