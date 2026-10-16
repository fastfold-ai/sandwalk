/** Same split Llama's menu uses: org, short name, parameter chip, quant chip. */

const PARAMS = /^[Ee]?\d+(\.\d+)?[BbMmKkTt]$/
const ACTIVATED = /^[Aa]\d+(\.\d+)?[BbMmKkTt]$/
const IGNORED = new Set(['GGUF', 'GGML'])

export type ParsedModelId = {
  org: string | null
  name: string
  params: string | null
  quant: string | null
}

export function parseModelId(id: string): ParsedModelId {
  let rest = id
  let org: string | null = null
  let quant: string | null = null
  const colon = rest.lastIndexOf(':')
  if (colon >= 0) {
    const tag = rest.slice(colon + 1)
    if (tag.toLowerCase() !== 'unknown') quant = tag
    rest = rest.slice(0, colon)
  }
  const slash = rest.indexOf('/')
  if (slash >= 0) {
    org = rest.slice(0, slash)
    rest = rest.slice(slash + 1)
  }
  const segments = rest.split('-').filter(part => !IGNORED.has(part.toUpperCase()))
  let paramsIndex: number | null = null
  let activatedIndex: number | null = null
  let params: string | null = null
  segments.forEach((segment, index) => {
    if (paramsIndex === null && PARAMS.test(segment)) {
      paramsIndex = index
      params = segment.toUpperCase()
    } else if (
      paramsIndex !== null &&
      activatedIndex === null &&
      ACTIVATED.test(segment)
    ) {
      activatedIndex = index
      params = `${params}-${segment.toUpperCase()}`
    }
  })
  const pivot = paramsIndex ?? segments.length
  const name = segments.slice(0, pivot).join('-') || rest
  return {
    org: org === 'ggml-org' ? null : org,
    name,
    params,
    quant
  }
}

export function formatContext(tokens: number | null): string | null {
  if (!tokens) return null
  if (tokens >= 1024) {
    const k = tokens / 1024
    return `${Number.isInteger(k) ? k : k.toFixed(1)}k context`
  }
  return `${tokens} context`
}
