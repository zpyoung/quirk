import type { FrameOrder, FrameView, SourceLine, StackFrame } from "./types"

export type TraceRow =
  | { kind: "frame"; frame: StackFrame; folded: boolean }
  | { kind: "fold"; id: string; count: number; open: boolean }

export const EXCERPT_SIZE = 11

/** Frames in display order: newest-first reverses the call order they arrive in. */
export function orderFrames<T>(frames: readonly T[], order: FrameOrder): T[] {
  return order === "newest" ? [...frames].reverse() : [...frames]
}

export const isExpandable = (frame: StackFrame) =>
  (frame.contextLines?.length ?? 0) > 0

/** Most relevant needs at least one in-app frame; without one every frame shows. */
export function effectiveView(
  frames: readonly StackFrame[],
  view: FrameView
): FrameView {
  return view === "relevant" && frames.some((frame) => frame.inApp)
    ? "relevant"
    : "full"
}

/** The id a fold row carries: the first frame of its run in call order, so it is stable under reordering. */
export const foldId = (firstFrameId: string) => `fold:${firstFrameId}`

type Segment =
  | { kind: "frame"; frame: StackFrame }
  | { kind: "run"; id: string; frames: StackFrame[] }

function segments(frames: readonly StackFrame[]): Segment[] {
  const out: Segment[] = []
  for (const frame of frames) {
    const last = out[out.length - 1]
    if (frame.inApp) {
      out.push({ kind: "frame", frame })
    } else if (last?.kind === "run") {
      last.frames.push(frame)
    } else {
      out.push({ kind: "run", id: foldId(frame.id), frames: [frame] })
    }
  }
  return out
}

/**
 * Rows to draw for one exception. In the relevant view every run of consecutive
 * library frames becomes one fold row, followed by those frames when its id is in
 * `openFolds`. The full view has no fold rows.
 */
export function foldFrames(
  frames: readonly StackFrame[],
  view: FrameView,
  order: FrameOrder,
  openFolds: ReadonlySet<string>
): TraceRow[] {
  if (effectiveView(frames, view) === "full") {
    return orderFrames(frames, order).map((frame) => ({
      kind: "frame",
      frame,
      folded: false,
    }))
  }
  return orderFrames(segments(frames), order).flatMap((segment): TraceRow[] => {
    if (segment.kind === "frame") {
      return [{ kind: "frame", frame: segment.frame, folded: false }]
    }
    const open = openFolds.has(segment.id)
    const row: TraceRow = {
      kind: "fold",
      id: segment.id,
      count: segment.frames.length,
      open,
    }
    if (!open) return [row]
    const shown = orderFrames(segment.frames, order).map((frame): TraceRow => ({
      kind: "frame",
      frame,
      folded: true,
    }))
    return [row, ...shown]
  })
}

/** The failing frame: the newest in-app frame that has source to show. */
export function defaultOpenFrameId(
  frames: readonly StackFrame[]
): string | undefined {
  for (let index = frames.length - 1; index >= 0; index -= 1) {
    const frame = frames[index]
    if (frame.inApp && isExpandable(frame)) return frame.id
  }
  return undefined
}

/**
 * About `size` lines centred on the failing line, shifted at the edges of the
 * supplied context so a window near a file's start or end still fills up.
 */
export function excerptWindow(
  lines: readonly SourceLine[],
  lineNo: number | undefined,
  size = EXCERPT_SIZE
): SourceLine[] {
  if (lines.length <= size) return [...lines]
  const at = lines.findIndex((line) => line.no === lineNo)
  const centre = at === -1 ? Math.floor(size / 2) : at
  const start = Math.min(
    Math.max(0, centre - Math.floor(size / 2)),
    lines.length - size
  )
  return lines.slice(start, start + size)
}
