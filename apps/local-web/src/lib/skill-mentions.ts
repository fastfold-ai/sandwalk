/**
 * Split plain text into skill mentions and residual text.
 *
 * Supports composer tokens `⟦/:name⟧` and slash mentions `/name` at word
 * boundaries (so filesystem paths like `/Users/...` are left alone).
 */
export type SkillMentionSegment =
  | { type: 'text'; text: string }
  | { type: 'skill'; name: string }

const SKILL_TOKEN_RE = /⟦\/:([^⟧]+)⟧/g
/** `/lab-notes` but not `/Users/foo` or mid-path segments. */
const SKILL_SLASH_RE =
  /(?:^|[\s(\["'])(\/[A-Za-z][\w-]*)(?=[\s.,;:!?)\]"'`]|$)/g

export function splitTextWithSkillMentions(text: string): SkillMentionSegment[] {
  type Hit = { start: number; end: number; name: string }
  const hits: Hit[] = []

  for (const match of text.matchAll(SKILL_TOKEN_RE)) {
    const name = (match[1] || '').trim()
    if (!name) continue
    const start = match.index ?? 0
    hits.push({ start, end: start + match[0].length, name })
  }

  for (const match of text.matchAll(SKILL_SLASH_RE)) {
    const raw = match[1] || ''
    const name = raw.replace(/^\//, '').trim()
    if (!name) continue
    const full = match[0]
    const start = (match.index ?? 0) + full.indexOf(raw)
    const end = start + raw.length
    // Skip if overlapping a token hit.
    if (hits.some(hit => start < hit.end && end > hit.start)) continue
    hits.push({ start, end, name })
  }

  hits.sort((a, b) => a.start - b.start)

  const parts: SkillMentionSegment[] = []
  let last = 0
  for (const hit of hits) {
    if (hit.start < last) continue
    if (hit.start > last) {
      parts.push({ type: 'text', text: text.slice(last, hit.start) })
    }
    parts.push({ type: 'skill', name: hit.name })
    last = hit.end
  }
  if (last < text.length) {
    parts.push({ type: 'text', text: text.slice(last) })
  }
  if (parts.length === 0) {
    parts.push({ type: 'text', text })
  }
  return parts
}
