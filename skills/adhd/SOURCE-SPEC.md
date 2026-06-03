# ADHD Skill Source Specification

## Design Rationale

The ADHD (divergent-ideation) skill addresses a specific gap in the Quirk skills library: **structured exploration of non-obvious alternatives at decision points**.

### Problem Space

During brainstorming and implementation planning, developers often face decision points with multiple viable approaches. The default behavior is to:
1. Consider 2-3 obvious options
2. Pick one based on familiarity or perceived simplicity
3. Proceed to implementation

This works for routine decisions but fails when:
- The obvious approach has hidden costs
- A non-obvious approach offers significant advantages
- The decision has high stakes (architectural, user-facing, performance-critical)
- Multiple stakeholders have different optimization criteria

### Solution Design

ADHD provides a **parallel, mechanical, generator/critic-split** process:

1. **Generator phase (Diverge)**: Spawn N parallel agents, each using a different thinking frame to surface ideas. Frames deliberately push against natural thought patterns (opposite day, constraint inversion, time travel).

2. **Filter phase (Score)**: Main agent evaluates all raw ideas on novelty, viability, and impact. Discard low-scoring ideas.

3. **Clustering phase (Cluster)**: Main agent groups surviving ideas into strategic themes.

4. **Critic phase (Deepen)**: Spawn K parallel agents to develop each cluster's approach and surface risks/costs.

5. **Output phase (Render)**: Present structured options with adversarial critiques.

### Shape Comparison

| | `brainstorming` | `adhd` |
|---|---|---|
| **Goal** | Fuzzy idea → approved spec | Surface N non-obvious viable options |
| **Shape** | Sequential, conversational, gated | Parallel, mechanical, generator/critic-split |
| **When** | Every creative project (HARD-GATE) | Decision-point subroutine (5–10× cost) |
| **Integration** | Entry point for all creative work | Advisory opt-in from brainstorming step 6 |

### Key Design Decisions

#### Why peer skill, not integrated into brainstorming?

- **Cost**: ADHD is 5-10× more expensive (N+K parallel agents). Making it mandatory would bloat every brainstorming session.
- **Scope**: Brainstorming covers the full idea → spec lifecycle. ADHD is a point-in-time subroutine for specific decision moments.
- **Reusability**: ADHD can be invoked standalone (explicit `/adhd`) or from other contexts, not just brainstorming.

#### Why keep the name `adhd`?

The name captures the core mechanism: **deliberately scattered, rapid-fire exploration across multiple non-linear thinking frames**. Alternative names considered:
- `divergent-ideation`: Technically accurate but generic
- `option-explorer`: Doesn't convey the parallel, frame-based mechanism
- `decision-support`: Too broad

Decision: Keep `adhd` for brevity and conceptual clarity.

#### Why no mandatory integration with brainstorming?

Forcing ADHD into every brainstorming session would:
- Increase cost 5-10× for decisions that don't need it
- Slow down the brainstorming process
- Create decision fatigue

Instead, brainstorming includes an **advisory sub-bullet** in step 6 suggesting ADHD when:
- The decision has 3+ gray areas
- High uncertainty about the right approach
- Meaningful stakes (architectural, user-facing, performance-critical)

This preserves brainstorming's efficiency while surfacing ADHD when it adds value.

#### Why inline Score/Cluster instead of Task agents?

Upstream spec implied score/cluster might use sub-Tasks, but:
- No prompts provided for score/cluster agents
- Scoring is fast (simple heuristics on novelty/viability/impact)
- Clustering is pattern matching (group similar ideas)

Both are lightweight operations the main agent can do inline. Using Task agents would add overhead without benefit.

#### Why nesting fallback?

ADHD invoked from brainstorming (which may itself use Task agents for research) can hit Task nesting limits. The fallback (run deepen sequentially in-context) ensures ADHD works in nested scenarios.

## Upstream Source

This skill is adapted from the ADHD divergent-thinking framework originally developed as an open-source brainstorming methodology. The core mechanism (15 frames, parallel divergence, score/cluster/deepen phases) comes from that upstream work.

Quirk-specific additions:
1. Standalone exit + context handling
2. Nesting fallback
3. Score/Cluster inline clarification
4. Integration points with Quirk's brainstorming skill

See `UPSTREAM-LICENSE` for the MIT license covering the original framework.

## Future Enhancements (Deferred)

- **N tiering by stakes**: Use 3 frames for low-stakes decisions, 5 for medium, 7 for high
- **Wired gray-area trigger**: Automatically invoke ADHD when brainstorming detects ≥3 gray areas
- **Quirk-native voice rewrite**: Current version uses upstream voice; could be rewritten in Quirk's terser style
- **Runtime-isolation test scenarios**: Test ADHD invoked from different entry points (standalone, brainstorming, nested)
- **ADHD in skill index**: Add to `using-quirk` skill catalog and cross-ref in `dispatching-parallel-agents`

## Testing Strategy

The initial test suite (`tests/test_adhd_skill.py`) validates **content conformance**, not runtime behavior:
- YAML frontmatter structure
- Description length and routing guard (no generic "brainstorm" trigger)
- Upstream attribution + UPSTREAM-LICENSE file existence
- HARD-GATE presence
- Standalone exit + context handling documentation
- Score/Cluster inline clarification
- Nesting fallback documentation
- All 15 frames present in `frames.md`
- Output shape sections (Options A/B/C + Recommendation)
- Plugin keywords (`adhd`, `divergent-ideation`, `divergent-thinking`)

Runtime-isolation tests (does ADHD actually work when invoked?) are deferred per existing deferred test list.
