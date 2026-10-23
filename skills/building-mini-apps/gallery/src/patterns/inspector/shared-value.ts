function normalize(value: unknown): unknown {
  return value === null || value === "" ? undefined : value
}

function same(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true
  if (typeof a === "object" && typeof b === "object")
    return JSON.stringify(a) === JSON.stringify(b)
  return false
}

/**
 * Reduces one field across a selection: `mixed` when the items disagree,
 * otherwise their common value. A field unset on every item is not mixed.
 */
export function sharedValue<T>(
  items: T[],
  key: keyof T
): { mixed: boolean; value: T[keyof T] | undefined } {
  if (items.length === 0) return { mixed: false, value: undefined }
  const first = normalize(items[0][key])
  const agree = items.every((item) => same(normalize(item[key]), first))
  if (!agree) return { mixed: true, value: undefined }
  return { mixed: false, value: first as T[keyof T] | undefined }
}
