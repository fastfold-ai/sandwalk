import { findUrlRanges, rangeOverlapsUrl } from '@/lib/chat-urls'

export type ComposerPart =
  | { type: 'text'; text: string }
  | { type: 'file'; path: string }
  | { type: 'skill'; name: string }
  | { type: 'mcp'; id: string; name: string }

const TOKEN_RE = /⟦@:([^⟧]+)⟧|⟦\/:([^⟧]+)⟧|⟦mcp:([^⟧]+)⟧/g
/**
 * Sent-message mentions: @path/to/file, /skill-name, or mcp:Name.
 * Skill slash form requires a word boundary so URL paths like
 * `https://news.ycombinator.com/` are not treated as `/news`.
 */
const FILE_MENTION_RE =
  /(?:^|[\s(\["'])(@[^\s]+)(?=[\s.,;:!?)\]"'`]|$)/g
const SKILL_SLASH_RE =
  /(?:^|[\s(\["'])(\/[A-Za-z][\w-]*)(?=[\s.,;:!?)\]"'`]|$)/g
const MCP_MENTION_RE =
  /(?:^|[\s(\["'])(mcp:[^\s]+)(?=[\s.,;:!?)\]"'`]|$)/g

export function fileChipToken(path: string) {
  return `⟦@:${path}⟧`
}

export function skillChipToken(name: string) {
  return `⟦/:${name}⟧`
}

export function mcpChipToken(id: string, name: string) {
  return `⟦mcp:${encodeURIComponent(id)}:${encodeURIComponent(name)}⟧`
}

function parseMcpTokenPayload(raw: string): { id: string; name: string } {
  const trimmed = String(raw || '')
  const sep = trimmed.indexOf(':')
  if (sep <= 0) {
    const fallback = decodeURIComponent(trimmed)
    return { id: fallback, name: fallback }
  }
  const id = decodeURIComponent(trimmed.slice(0, sep))
  const name = decodeURIComponent(trimmed.slice(sep + 1)) || id
  return { id, name }
}

/** Ensure at most one space before/after chip tokens (no doubles). */
export function spaceAroundChips(value: string): string {
  return value
    .replace(/[ \t]+(?=⟦(?:[@/]|mcp:))/g, ' ')
    .replace(/(⟧)[ \t]+/g, '$1 ')
    .replace(/([^\s⟦])(⟦(?:[@/]|mcp:))/g, '$1 $2')
    .replace(/(⟧)([^\s⟧])/g, '$1 $2')
}

export function parseComposerParts(value: string): ComposerPart[] {
  const parts: ComposerPart[] = []
  let last = 0
  for (const match of value.matchAll(TOKEN_RE)) {
    const index = match.index ?? 0
    if (index > last) {
      parts.push({ type: 'text', text: value.slice(last, index) })
    }
    if (match[1] != null) {
      parts.push({ type: 'file', path: match[1] })
    } else if (match[2] != null) {
      parts.push({ type: 'skill', name: match[2] })
    } else if (match[3] != null) {
      parts.push({ type: 'mcp', ...parseMcpTokenPayload(match[3]) })
    }
    last = index + match[0].length
  }
  if (last < value.length) {
    parts.push({ type: 'text', text: value.slice(last) })
  }
  if (parts.length === 0) {
    parts.push({ type: 'text', text: '' })
  }
  if (parts[parts.length - 1]?.type !== 'text') {
    parts.push({ type: 'text', text: '' })
  }
  return parts
}

/** Parse sent user messages that use @path /skill / mcp:Name plain-text mentions. */
export function parseMessageParts(content: string): ComposerPart[] {
  type Hit = { start: number; end: number; part: ComposerPart }
  const hits: Hit[] = []
  const urls = findUrlRanges(content)

  for (const match of content.matchAll(FILE_MENTION_RE)) {
    const raw = match[1] || ''
    if (!raw) continue
    const full = match[0]
    const start = (match.index ?? 0) + full.indexOf(raw)
    const end = start + raw.length
    if (rangeOverlapsUrl(urls, start, end)) continue
    hits.push({
      start,
      end,
      part: { type: 'file', path: raw.slice(1) }
    })
  }

  for (const match of content.matchAll(SKILL_SLASH_RE)) {
    const raw = match[1] || ''
    const name = raw.replace(/^\//, '').trim()
    if (!name) continue
    const full = match[0]
    const start = (match.index ?? 0) + full.indexOf(raw)
    const end = start + raw.length
    if (rangeOverlapsUrl(urls, start, end)) continue
    if (hits.some(hit => start < hit.end && end > hit.start)) continue
    hits.push({ start, end, part: { type: 'skill', name } })
  }

  for (const match of content.matchAll(MCP_MENTION_RE)) {
    const raw = match[1] || ''
    if (!raw) continue
    const full = match[0]
    const start = (match.index ?? 0) + full.indexOf(raw)
    const end = start + raw.length
    if (rangeOverlapsUrl(urls, start, end)) continue
    if (hits.some(hit => start < hit.end && end > hit.start)) continue
    const name = decodeURIComponent(raw.slice('mcp:'.length))
    hits.push({ start, end, part: { type: 'mcp', id: name, name } })
  }

  hits.sort((a, b) => a.start - b.start)

  const parts: ComposerPart[] = []
  let last = 0
  for (const hit of hits) {
    if (hit.start < last) continue
    if (hit.start > last) {
      parts.push({ type: 'text', text: content.slice(last, hit.start) })
    }
    parts.push(hit.part)
    last = hit.end
  }
  if (last < content.length) {
    parts.push({ type: 'text', text: content.slice(last) })
  }
  if (parts.length === 0) {
    parts.push({ type: 'text', text: content })
  }
  return parts
}

export function serializeComposerParts(parts: ComposerPart[]): string {
  return parts
    .map(part => {
      if (part.type === 'text') return part.text
      if (part.type === 'file') return fileChipToken(part.path)
      if (part.type === 'mcp') return mcpChipToken(part.id, part.name)
      return skillChipToken(part.name)
    })
    .join('')
}

export function composerToMessage(value: string): string {
  const parts = parseComposerParts(value)
  let out = ''
  for (const part of parts) {
    const piece =
      part.type === 'text'
        ? part.text
        : part.type === 'file'
          ? `@${part.path}`
          : part.type === 'mcp'
            ? `mcp:${encodeURIComponent(part.name)}`
            : `/${part.name}`
    if (!piece) continue
    if (out && !/\s$/.test(out) && !/^\s/.test(piece)) {
      out += ' '
    }
    out += piece
  }
  return out
    .replace(/[ \t]+\n/g, '\n')
    .replace(/[ \t]{2,}/g, ' ')
    .trim()
}

export function removeComposerChipAt(value: string, chipIndex: number): string {
  const parts = parseComposerParts(value)
  let seen = -1
  const next = parts.filter(part => {
    if (part.type === 'text') return true
    seen += 1
    return seen !== chipIndex
  })
  // Merge adjacent text parts
  const merged: ComposerPart[] = []
  for (const part of next) {
    const lastPart = merged[merged.length - 1]
    if (part.type === 'text' && lastPart?.type === 'text') {
      lastPart.text += part.text
      continue
    }
    merged.push(part)
  }
  return serializeComposerParts(merged)
}

export function chipTokenLength(part: Exclude<ComposerPart, { type: 'text' }>): number {
  if (part.type === 'file') return fileChipToken(part.path).length
  if (part.type === 'mcp') return mcpChipToken(part.id, part.name).length
  return skillChipToken(part.name).length
}
