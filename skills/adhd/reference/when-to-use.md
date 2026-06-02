# When to Use the ADHD Skill

## Appropriate Use Cases

### High-Stakes Architectural Decisions

**Scenario**: You need to choose a core architecture pattern (monolith vs. microservices, REST vs. GraphQL, SQL vs. NoSQL).

**Why ADHD helps**: These decisions have long-term consequences. ADHD surfaces non-obvious alternatives (e.g., "hybrid approach", "defer the decision with abstraction layer") that might not emerge from standard pros/cons analysis.

**Example invocation**: `/adhd` → "We're building a real-time collaboration feature. Should we use WebSockets, Server-Sent Events, polling, or something else?"

### Decision Points with Multiple Gray Areas

**Scenario**: During brainstorming, you've identified 3+ gray areas (see `brainstorming` skill docs) with no clear resolution.

**Why ADHD helps**: Multiple gray areas indicate genuine uncertainty about the right approach. ADHD's frame-based divergence forces exploration of alternatives you might not naturally consider.

**Example**: Building a notification system with gray areas in: delivery guarantees, priority handling, user preferences, batching strategy. ADHD surfaces options like "inverted model where users pull vs. push" or "delegate to third-party service".

### User-Facing Features with High Impact

**Scenario**: You're designing a feature that will define user perception of your product (onboarding flow, primary navigation, search interface).

**Why ADHD helps**: User-facing decisions benefit from exploring unconventional approaches. ADHD frames like "opposite day" or "beginner's mind" surface ideas that resonate with users who don't share your expert assumptions.

**Example**: Designing file upload. ADHD surfaces alternatives like "paste-anywhere to upload", "email-to-upload", "sync from cloud storage" alongside standard file picker.

### Performance-Critical Optimizations

**Scenario**: You need to improve performance and standard approaches (caching, indexing) aren't sufficient.

**Why ADHD helps**: Frames like "constraint inversion" (remove assumed constraints), "scale extremes" (solve for 10× load), and "material substitution" (different tech stack) force consideration of radical approaches.

**Example**: Slow analytics dashboard. ADHD surfaces "pre-compute everything", "approximate results", "progressive rendering", "ditch real-time entirely".

## When NOT to Use ADHD

### Trivial Decisions

**Examples**:
- Variable naming
- Code formatting
- Obvious bug fixes
- Single-function utilities

**Why skip**: The 5-10× cost isn't justified. Make the obvious choice and move on.

### Decisions Already Constrained by Requirements

**Example**: "User requested a CSV export feature using library X"

**Why skip**: Requirements already specify the solution. No decision to make.

### Linear Problems with Clear Solutions

**Example**: "Implement OAuth 2.0 flow per spec"

**Why skip**: Specifications exist. Follow them. ADHD is for ambiguous decision spaces, not compliance work.

### Time-Sensitive Situations

**Example**: Production outage requires immediate fix

**Why skip**: Rapid execution matters more than thoroughness. Pick the fastest safe option and iterate later.

### Low-Stakes Decisions

**Example**: "Should we use margin or padding for this spacing?"

**Why skip**: If getting it "wrong" has minimal consequences, don't pay the ADHD cost. Make a choice, test with users, adjust if needed.

## Integration with Brainstorming

The `brainstorming` skill includes an **advisory** recommendation in step 6 ("Exploring approaches"):

> "For decisions with high uncertainty or 3+ gray areas, consider using `/adhd` to surface non-obvious options through structured divergent ideation."

This is opt-in guidance. The main agent can:
- Invoke ADHD explicitly: "This decision warrants ADHD. Invoking `/adhd` to explore alternatives..."
- Ask the user: "This is a high-stakes decision. Want me to use the ADHD skill to explore more options? (5-10× cost)"
- Skip it: "This decision is straightforward. Proposing [standard options] and moving forward."

## Standalone Invocation

Users can invoke ADHD directly via `/adhd` when they:
- Face a decision point outside the brainstorming context
- Want to explore alternatives for an existing design
- Need to debug why their current approach feels wrong

After rendering output, ADHD releases control to the normal agent loop. The user can ask follow-up questions, request elaboration on specific options, or choose an option and proceed.

## Cost-Benefit Heuristics

**Use ADHD when**:
- Decision stakes × uncertainty > 5-10× cost threshold
- You'd regret not exploring alternatives if the obvious choice fails
- The decision blocks multiple downstream choices

**Skip ADHD when**:
- The decision is reversible and low-cost to change later
- You have strong evidence for the obvious choice
- Stakeholders have already decided

## Examples

### ✅ Good Use Case

**Context**: Building a code review tool. Need to decide how to represent diff comments (inline vs. sidebar vs. overlay vs. separate view).

**Why ADHD**: User-facing, high-impact decision with multiple viable approaches. ADHD surfaces alternatives like "nested threads à la Google Docs" or "audio annotations" that might not emerge from standard analysis.

### ❌ Poor Use Case

**Context**: Fixing a bug where validation fails on empty input.

**Why skip**: Obvious solution (add empty check). No decision to explore.

### ✅ Good Use Case

**Context**: Refactoring a 5000-line controller file. Unclear how to decompose.

**Why ADHD**: Architectural decision with multiple strategies (service objects, event sourcing, CQRS, microservices, keep as-is with better organization). ADHD frames like "scale extremes" or "material substitution" force consideration of radical approaches.

### ❌ Poor Use Case

**Context**: Choosing between `let` and `const` for a loop variable.

**Why skip**: Trivial decision. Follow style guide or team convention.
