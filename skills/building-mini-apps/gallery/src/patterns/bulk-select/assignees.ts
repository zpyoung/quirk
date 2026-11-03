export type AssigneeOption = { id: string; name: string; hint?: string }
export type AssigneeGroup = {
  id: string
  label: string
  options: AssigneeOption[]
}

/** Groups keeping only options whose name or hint contains `query`; groups left empty are dropped. */
export function filterAssigneeGroups(
  groups: AssigneeGroup[],
  query: string
): AssigneeGroup[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return groups
  return groups
    .map((group) => ({
      ...group,
      options: group.options.filter((option) =>
        `${option.name} ${option.hint ?? ""}`.toLowerCase().includes(needle)
      ),
    }))
    .filter((group) => group.options.length > 0)
}

export function findAssignee(
  groups: AssigneeGroup[],
  id: string | null
): AssigneeOption | undefined {
  if (id === null) return undefined
  for (const group of groups) {
    const found = group.options.find((option) => option.id === id)
    if (found) return found
  }
  return undefined
}

/** Up to two capital letters from the first and last words of a name. */
export function initials(name: string): string {
  const words = name
    .replace(/[^\p{L}\p{N}\s]/gu, "")
    .split(/\s+/)
    .filter(Boolean)
  if (words.length === 0) return "?"
  const first = words[0][0]
  const last = words.length > 1 ? words[words.length - 1][0] : ""
  return `${first}${last}`.toUpperCase()
}
