/** Types for the run view model the companion folds from SDD reports and git facts. Times are epoch seconds. */

export type RunStatus =
  | 'queued'
  | 'running'
  | 'needs-you'
  | 'retrying'
  | 'passed'
  | 'failed'
  | 'skipped'
  | 'stopped'
  | 'missing'

export interface RunAttempt {
  n: number
  start: number
  end?: number
  outcome?: string
}

export interface RunTask {
  id: string
  title: string
  contract_md?: string
  level: number
  chain?: string
  status: RunStatus
  attempt: number
  reason?: string
  attempts: RunAttempt[]
  started_at?: number
  ended_at?: number
  files: number
  ready: boolean
  blocked_by: string[]
  downstream: string[]
  round?: string
  labels: string[]
  mismatch: { sdd: string; git: string; text: string } | null
  question?: string
  pending_action?: 'stop' | 'retry'
  held_by?: string
}

export interface RunEdge {
  from: string
  to: string
  kind: 'dep' | 'order'
}

export interface RunChain {
  id: string
  tasks: string[]
}

export interface RunFinding {
  id: string
  lens: string
  severity: string
  ruling: 'accepted' | 'dismissed'
  reason: string
  fix_task?: string
}

export interface RunRound {
  id: string
  kind: 'checkpoint' | 'final'
  title: string
  covers: string[]
  outcome?: 'clean' | 'fixes' | 'blocked'
  findings: RunFinding[]
}

export interface RunAnswer {
  question: string
  source: 'tab' | 'orca' | 'sdd'
  pick?: string
  label?: string
  text?: string
  at: number
}

export interface RunQuestionOption {
  value: string
  label: string
  description?: string
}

export interface RunQuestion {
  id: string
  task?: string
  header?: string
  prompt: string
  options: RunQuestionOption[]
  recommended?: string
  default?: string
  asked_at: number
  state: 'open' | 'answered'
  answer?: RunAnswer
}

export interface RunView {
  run_id: string
  branch: string
  status_text?: string
  started_at: number
  ended?: { at: number; outcome: 'clean' | 'blocked' | 'stopped'; next_step?: 'merge' | 'pr' | 'keep' }
  counts: Partial<Record<RunStatus, number>>
  last_update_at: number
  stale: null | { since: number }
  stale_after_s: number
  now: number
  tasks: RunTask[]
  edges: RunEdge[]
  chains: RunChain[]
  rounds: RunRound[]
  questions: RunQuestion[]
}

export interface DiffFile {
  path: string
  status: 'added' | 'modified' | 'deleted' | 'renamed'
  patch: string
  binary: boolean
}

export interface RunDiff {
  task: string
  base: string
  head: string | null
  source: 'commit' | 'worktree'
  files: DiffFile[]
  truncated: boolean
}
