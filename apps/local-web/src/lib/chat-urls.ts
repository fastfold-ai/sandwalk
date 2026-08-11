/**
 * Detect http(s) URLs in plain text for linkification and mention exclusion.
 */

export type UrlTextSegment =
  | { type: 'text'; text: string }
  | { type: 'url'; href: string; text: string }

const URL_RE = /https?:\/\/[^\s<>"'`]+/gi

/** Trim trailing sentence punctuation that is usually not part of the URL. */
export function trimUrlMatch(raw: string): string {
  return raw.replace(/[.,;:!?]+$/g, '')
}

export function findUrlRanges(
  text: string
): Array<{ start: number; end: number }> {
  const ranges: Array<{ start: number; end: number }> = []
  for (const match of text.matchAll(URL_RE)) {
    const start = match.index ?? 0
    const trimmed = trimUrlMatch(match[0] || '')
    if (!trimmed) continue
    ranges.push({ start, end: start + trimmed.length })
  }
  return ranges
}

export function rangeOverlapsUrl(
  ranges: Array<{ start: number; end: number }>,
  start: number,
  end: number
): boolean {
  return ranges.some(range => start < range.end && end > range.start)
}

/** Split plain text into URL and residual text segments. */
export function splitTextWithUrls(text: string): UrlTextSegment[] {
  const ranges = findUrlRanges(text)
  if (ranges.length === 0) {
    return [{ type: 'text', text }]
  }
  const parts: UrlTextSegment[] = []
  let last = 0
  for (const range of ranges) {
    if (range.start < last) continue
    if (range.start > last) {
      parts.push({ type: 'text', text: text.slice(last, range.start) })
    }
    const href = text.slice(range.start, range.end)
    parts.push({ type: 'url', href, text: href })
    last = range.end
  }
  if (last < text.length) {
    parts.push({ type: 'text', text: text.slice(last) })
  }
  return parts
}
