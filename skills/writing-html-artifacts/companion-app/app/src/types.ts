export const STAGES = ['context', 'gray-areas', 'questions', 'approaches', 'design', 'spec', 'hand-off'] as const
export type StageId = (typeof STAGES)[number]

export const STAGE_LABELS: Record<StageId, string> = {
  context: 'Context',
  'gray-areas': 'Gray areas',
  questions: 'Questions',
  approaches: 'Approaches',
  design: 'Design',
  spec: 'Spec',
  'hand-off': 'Hand-off',
}

export interface Changed {
  summary: string
  blocks: string[]
}

export interface StepCommon {
  id: string
  nonce: string
  v: 1
  stage: StageId
  title: string
  intro_md?: string
  intro_html?: string
  changed?: Changed
}

export interface QuestionOption {
  id: string
  label: string
  description?: string
  preview_html?: string
}

export interface Question {
  id: string
  type: 'single' | 'multi' | 'text'
  prompt: string
  header?: string
  recommended?: string
  options?: QuestionOption[]
  content_html?: string
  diagram?: string
}

export interface Source {
  title: string
  url: string
}

export interface Approach {
  id: string
  title: string
  summary_md: string
  recommended: boolean
  pros?: string[]
  cons?: string[]
  sources?: Source[]
  content_html?: string
}

export interface DesignSectionItem {
  id: string
  title: string
  body_md?: string
  body_html?: string
  diagram?: string
}

export interface SpecSection {
  id: string
  title: string
  body_md: string
}

export interface Invalidation {
  label: string
  step_id?: string
}

export interface Choice {
  id: string
  label: string
  description: string
  recommended: boolean
}

export type Step = StepCommon &
  (
    | { kind: 'questions'; questions: Question[] }
    | { kind: 'approaches'; approaches: Approach[] }
    | { kind: 'design-section'; index: number; total: number; sections: DesignSectionItem[] }
    | { kind: 'spec-review'; format: 'markdown'; spec_path: string; sections: SpecSection[] }
    | { kind: 'spec-review'; format: 'interactive' }
    | { kind: 'edit-card'; decision_id: string; from: string; to: string; invalidates: Invalidation[]; origin: 'rail' | 'chat' }
    | { kind: 'hand-off'; choices: Choice[] }
    | { kind: 'done'; message_md: string }
  )

export type StepKind = Step['kind']

export interface Decision {
  id: string
  stage: string
  area: string
  label: string
  value: string
  status: 'confirmed' | 'assumed' | 'open'
  note?: string
}

export interface Status {
  text: string
  stage?: string
  progress?: unknown
  interruptible: boolean
  started_at?: unknown
}

export interface StageState {
  id: string
  state: 'done' | 'current' | 'todo'
}

export interface ChatEntry {
  seq: number
  from: string
  text: string
  timestamp: string
  delivered: boolean
}

export interface Thread {
  id: string
  block_id: string
  step: string
  messages: { from: string; text: string; timestamp: string }[]
  resolution?: string
}

export interface AnswerState {
  selected?: string[]
  other?: string
  text?: string
  skipped?: true
}

export interface Draft {
  answers?: Record<string, AnswerState>
  comment?: string
}

export interface Snapshot {
  rev: number | string
  mode: 'app'
  step: Step | null
  step_state: 'open' | 'submitted'
  status: Status | null
  stages: StageState[]
  decisions: Decision[]
  chat: ChatEntry[]
  threads: Thread[]
  draft?: Draft | null
  review_registered: boolean
}

export interface Boot {
  token: string
  session: string
}

export type SubmitPayload = Record<string, unknown>
export type PostResult = 'ok' | 'superseded' | 'error'

export interface Actions {
  /** Posts a `submit` for the open step; the shell switches to waiting at once and reconciles on the next snapshot. */
  submit(payload: SubmitPayload): Promise<PostResult>
  /** Posts a non-submit event such as `continue`, `edit-request`, `edit-decision` or `draft`. */
  send(type: 'continue' | 'edit-request' | 'edit-decision' | 'draft', payload: Record<string, unknown>, withNonce?: boolean): Promise<PostResult>
}
