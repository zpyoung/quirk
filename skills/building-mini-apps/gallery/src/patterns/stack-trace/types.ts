export type SourceLine = { no: number; text: string }

export type StackFrame = {
  /** Unique within its exception; expansion state is kept by this id. */
  id: string
  filename: string
  function?: string
  /** Shown in place of the path for frames that have no file. */
  module?: string
  /** The failing line; highlighted when it is among `contextLines`. */
  lineNo?: number
  colNo?: number
  /** Relevant frames open to source and survive the Most relevant view. */
  inApp: boolean
  contextLines?: SourceLine[]
}

export type StackException = {
  id: string
  type: string
  value?: string
  mechanism?: string
  handled?: boolean
  /** Call order: caller first, failing frame last. */
  frames: StackFrame[]
}

export type FrameView = "relevant" | "full"
export type FrameOrder = "newest" | "oldest"
