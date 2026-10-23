export type PropValue = string | number | boolean | null

export type FieldDef = {
  key: string
  label: string
  type: "text" | "number" | "checkbox" | "date" | "url" | "select"
  options?: string[]
}

export type DocRecord = {
  id: string
  title: string
  collectionId: string
  props: Record<string, PropValue>
  body: string
}

export type CollectionDef = { id: string; name: string; fields: FieldDef[] }

export type DocBlock =
  | { id: string; kind: "text"; text: string }
  | { id: string; kind: "collection"; collectionId: string }

export type DocPage = {
  id: string
  title: string
  blocks: DocBlock[]
  collections: CollectionDef[]
}
