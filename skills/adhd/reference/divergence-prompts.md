# Divergence Prompts (Quirk-Specific)

This file contains prompt templates for the ADHD divergence phase. These prompts are Quirk-original additions (not from upstream) to provide consistent, effective Task agent prompts.

## General Structure

Each divergence Task agent receives:
1. The decision context (what problem/choice we're exploring)
2. The assigned thinking frame
3. Instructions to generate 3-5 raw ideas
4. Constraints (time limit, format, evaluation criteria)

## Base Template

```
You are a divergence agent in an ADHD ideation session. Your goal is to generate non-obvious options for the following decision:

**Decision context**: [problem statement]

**Your assigned thinking frame**: [frame name]

**Frame principle**: [frame description from frames.md]

**Your task**:
1. Apply this frame to the decision context
2. Generate 3-5 raw ideas that would NOT naturally occur without this frame
3. For each idea, provide:
   - One-sentence description
   - Why this is non-obvious
   - One key risk or challenge

**Output format**:
### Idea N: [name]
- **Description**: [one sentence]
- **Why non-obvious**: [one sentence]
- **Key challenge**: [one sentence]

**Constraints**:
- Ideas must be viable (not science fiction)
- Prioritize novelty over refinement
- Don't self-censor "weird" ideas
- 3-5 ideas total

Generate your ideas now.
```

## Frame-Specific Variants

### Constraint Inversion

```
Your thinking frame: **Constraint Inversion**

Identify one constraint that seems fixed in [decision context]. Generate 3-5 ideas that assume this constraint doesn't exist, or add a new constraint that forces a different solution.

For each idea:
- Which constraint did you invert/add?
- What new approach does this enable?
- What's the key challenge?
```

### Opposite Day

```
Your thinking frame: **Opposite Day**

For [decision context], what's the most counterintuitive or opposite approach? Generate 3-5 ideas that deliberately contradict the obvious solution.

For each idea:
- What's the opposite of the obvious approach?
- Why might this counterintuitive approach actually work?
- What's the key challenge?
```

### Time Travel

```
Your thinking frame: **Time Travel**

Solve [decision context] as if you're in 2036 (10 years forward) or 2016 (10 years back). Generate 3-5 ideas from that temporal vantage point.

For each idea:
- Which time period (2016 or 2036)?
- What would be obvious/available in that time period?
- What's the key challenge translating to 2026?
```

### Cross-Domain Analogy

```
Your thinking frame: **Cross-Domain Analogy**

How does a completely unrelated industry/field handle challenges similar to [decision context]? Generate 3-5 ideas by borrowing from other domains.

For each idea:
- Which domain did you borrow from?
- What's the analogous solution?
- What's the key challenge in translation?
```

### Stakeholder Rotation

```
Your thinking frame: **Stakeholder Rotation**

Solve [decision context] from the perspective of a different stakeholder (end user, admin, API consumer, support team, competitor). Generate 3-5 ideas, each from a different stakeholder perspective.

For each idea:
- Which stakeholder perspective?
- What would THEY prioritize?
- What's the key challenge?
```

### Failure Pre-Mortem

```
Your thinking frame: **Failure Pre-Mortem**

Assume we implemented a solution for [decision context] and it failed catastrophically 6 months later. Generate 3-5 failure scenarios, then work backward to identify what would prevent each failure.

For each idea:
- What failed?
- What would have prevented this failure?
- What's the key challenge?
```

### Sensory Shift

```
Your thinking frame: **Sensory Shift**

Solve [decision context] by changing the primary modality (visual → audio, click → gesture, text → spatial). Generate 3-5 ideas that use a different sense or interaction mode.

For each idea:
- Which sensory modality?
- How does this change the solution?
- What's the key challenge?
```

### Scale Extremes

```
Your thinking frame: **Scale Extremes**

Solve [decision context] assuming 10× scale (bigger) or 1/10× scale (smaller). Generate 3-5 ideas that optimize for extreme scale.

For each idea:
- Which scale (10× or 1/10×)?
- How does this scale change requirements?
- What's the key challenge?
```

### Role Reversal

```
Your thinking frame: **Role Reversal**

Swap the roles of actors in [decision context]. Generate 3-5 ideas where the typical roles are reversed.

For each idea:
- Which roles are reversed?
- What does this enable?
- What's the key challenge?
```

### Material Substitution

```
Your thinking frame: **Material Substitution**

Replace a core technology/material in [decision context] with something fundamentally different. Generate 3-5 ideas using alternative tech/materials.

For each idea:
- What's being replaced?
- What's the substitute?
- What's the key challenge?
```

### Process Reversal

```
Your thinking frame: **Process Reversal**

Reverse the order of steps in [decision context]. Generate 3-5 ideas where the process runs backward or in a different sequence.

For each idea:
- Which steps are reversed?
- Why might this work better?
- What's the key challenge?
```

### Success Post-Mortem

```
Your thinking frame: **Success Post-Mortem**

Assume we implemented a solution for [decision context] and it succeeded beyond expectations 6 months later. Generate 3-5 success scenarios, then work backward to identify what we did right.

For each idea:
- What succeeded spectacularly?
- What decisions led to this success?
- What's the key challenge?
```

### Beginner's Mind

```
Your thinking frame: **Beginner's Mind**

Approach [decision context] with zero domain knowledge. What obvious-to-a-beginner solutions would experts dismiss? Generate 3-5 "naive" ideas.

For each idea:
- What's the beginner's obvious solution?
- Why do experts dismiss this?
- What if the beginner is right?
```

### Expert Blind Spots

```
Your thinking frame: **Expert Blind Spots**

Identify what domain experts assume about [decision context] that might not be true. Generate 3-5 ideas that challenge expert assumptions.

For each idea:
- Which expert assumption are you challenging?
- What if this assumption is wrong?
- What's the key challenge?
```

### Adjacent Possible

```
Your thinking frame: **Adjacent Possible**

Solve [decision context] using technology or capabilities that will exist in 1-2 years but doesn't quite work today. Generate 3-5 ideas at the edge of current possibility.

For each idea:
- Which emerging tech/capability?
- How does this enable a new solution?
- What's the key challenge (maturity, adoption, cost)?
```

## Usage in ADHD Process

The main agent selects 5-7 frames based on decision context, then spawns parallel Task agents using the appropriate frame-specific prompts. All divergence Tasks MUST be dispatched in a single message.

After Task results return, the main agent summarizes findings in the next turn before proceeding to Score phase.
