import type { NoteSegment } from "./types"

export const isUser = (segment: NoteSegment) => segment.origin === "user"
export const isGenerated = (segment: NoteSegment) =>
  segment.origin === "generated"

export const newId = () => crypto.randomUUID()

/** Display order: each generated line follows its anchor user line; unanchored ones go last. */
export function orderSegments(segments: NoteSegment[]): NoteSegment[] {
  const userIds = new Set(segments.filter(isUser).map((s) => s.id))
  const anchored = new Map<string, NoteSegment[]>()
  const tail: NoteSegment[] = []
  for (const segment of segments) {
    if (!isGenerated(segment)) continue
    if (segment.after && userIds.has(segment.after)) {
      anchored.set(segment.after, [
        ...(anchored.get(segment.after) ?? []),
        segment,
      ])
    } else {
      tail.push(segment)
    }
  }
  const ordered: NoteSegment[] = []
  for (const segment of segments) {
    if (isUser(segment))
      ordered.push(segment, ...(anchored.get(segment.id) ?? []))
  }
  return [...ordered, ...tail]
}
