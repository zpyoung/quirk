export type NoteOrigin = "user" | "generated"

export type SourceRef = { excerpt: string; label?: string; summary?: string }

export type NoteSegment = {
  id: string
  origin: NoteOrigin
  text: string
  kind?: "heading" | "bullet" | "text"
  /** Generated only: id of the user segment it follows; unset places it at the end of the note. */
  after?: string
  /** Generated only. */
  source?: SourceRef
}

export type AssistedNoteItem = {
  id: string
  title: string
  segments: NoteSegment[]
}

export type NoteViewMode = "mine" | "enhanced"
