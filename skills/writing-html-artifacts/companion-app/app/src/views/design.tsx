import { AgentHtml, Diagram, MdHtml, blockKey } from '../blocks'
import { annotateSectionHtml, paragraphId, renderSectionMarkdown } from '../section-blocks'
import type { Step } from '../types'
import { StepFrame, blockAttrs, type ViewProps } from './common'
import { VerdictBar } from './verdict'

type DesignStep = Extract<Step, { kind: 'design-section' }>

export function DesignView({ step, changed, draft, actions }: ViewProps<DesignStep>) {
  return (
    <StepFrame step={step} changed={changed}>
      <p className="design-count">
        Design {step.index} of {step.total}
      </p>
      {step.sections.map((section) => {
        const md = renderSectionMarkdown(section.body_md, { sectionId: section.id, start: 0, changed })
        const agent = annotateSectionHtml(section.body_html, { sectionId: section.id, start: md.count, changed })
        return (
          <section key={section.id} className="design-section" {...blockAttrs(`section:${section.id}`, changed)}>
            <h2 className="section-title">{section.title}</h2>
            <MdHtml html={md.html} />
            <AgentHtml key={blockKey(step.id, `body:${section.id}`)} html={agent.html} />
            {section.diagram ? (
              <Diagram
                key={blockKey(step.id, `diagram:${section.id}`)}
                source={section.diagram}
                blockAttrs={blockAttrs(paragraphId(section.id, md.count + agent.count), changed)}
              />
            ) : null}
          </section>
        )
      })}
      <VerdictBar
        stepId={step.id}
        draft={draft}
        actions={actions}
        verdicts={[
          { value: 'looks-right', label: 'Looks right', primary: true },
          { value: 'needs-changes', label: 'Needs changes', requiresComment: true },
        ]}
      />
    </StepFrame>
  )
}
