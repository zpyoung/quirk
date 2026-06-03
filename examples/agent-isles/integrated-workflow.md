# Integrated Quirk + Agent Isles workflow

Plain Markdown fallback: this example ties together the bridge helper, local pack, conventions, and disposable output policy.

1. Author canonical Markdown in this file or another Quirk artifact.
2. Use `python3 bin/agent_isles.py doctor` to see whether Agent Isles is available.
3. Use `python3 bin/agent_isles.py command examples/agent-isles/integrated-workflow.md` to print the exact render command.
4. Render only when desired; output defaults to `.quirk/isles/` and is disposable.
5. The helper adds `--pack packs/quirk --no-user-packs` by default when the Quirk pack exists.

<agent-timeline title="Workflow">
- Author Markdown source
- Review fallback text in GitHub or terminal
- Render with Agent Isles when present
- Delete/regenerate generated HTML as needed
</agent-timeline>

<quirk-artifact-summary title="Integration surfaces" bugs="0 integration blockers" deferred="future publishing workflow out of scope" test-backlog="optional Agent Isles smoke when available" proposals="paired artifact ecosystem direction captured" adrs="Markdown canonical policy" status="coherent">
Plain Markdown fallback: bin/agent_isles.py, packs/quirk, docs/agent-isles-artifacts.md, examples/agent-isles, and .quirk/isles form the integration story.
</quirk-artifact-summary>
