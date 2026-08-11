export function schemaPropertyEntries(schema: Record<string, unknown> | null) {
  if (!schema || typeof schema !== 'object') return []
  const properties = schema.properties
  if (!properties || typeof properties !== 'object' || Array.isArray(properties)) {
    return []
  }
  const required = Array.isArray(schema.required)
    ? schema.required.map(String)
    : []
  return Object.entries(properties as Record<string, unknown>).map(
    ([key, value]) => {
      const prop =
        value && typeof value === 'object' && !Array.isArray(value)
          ? (value as Record<string, unknown>)
          : {}
      const typeValue = prop.type
      const typeLabel = Array.isArray(typeValue)
        ? typeValue.map(String).join(' | ')
        : typeof typeValue === 'string'
          ? typeValue
          : 'any'
      return {
        key,
        required: required.includes(key),
        type: typeLabel,
        description:
          typeof prop.description === 'string' ? prop.description : null
      }
    }
  )
}

export function firstParagraph(text: string, maxChars = 220): string {
  const cleaned = text.replace(/\s+/g, ' ').trim()
  if (!cleaned) return ''
  const cut = cleaned.split(/(?<=\.)\s+/)[0] || cleaned
  if (cut.length <= maxChars) return cut
  return `${cut.slice(0, maxChars - 1).trimEnd()}…`
}
