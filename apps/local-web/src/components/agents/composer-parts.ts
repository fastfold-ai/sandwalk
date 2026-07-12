export type ComposerPart =
  | { type: 'text'; text: string }
  | { type: 'file'; path: string }
  | { type: 'skill'; name: string }

const TOKEN_RE = /⟦@:([^⟧]+)⟧|⟦\/:([^⟧]+)⟧/g
/** Sent-message mentions: @path/to/file or /skill-name */
const MESSAGE_MENTION_RE = /(@[^\s]+)|(\/[A-Za-z][\w-]*)/g

export function fileChipToken(path: string) {
  return `⟦@:${path}⟧`
}

export function skillChipToken(name: string) {
  return `⟦/:${name}⟧`
}

/** Ensure at most one space before/after chip tokens (no doubles). */
export function spaceAroundChips(value: string): string {
  return value
    .replace(/[ \t]+(?=⟦[@/]:)/g, ' ')
    .replace(/(⟧)[ \t]+/g, '$1 ')
    .replace(/([^\s⟦])(⟦[@/]:)/g, '$1 $2')
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

/** Parse sent user messages that use @path /skill plain-text mentions. */
export function parseMessageParts(content: string): ComposerPart[] {
  const parts: ComposerPart[] = []
  let last = 0
  for (const match of content.matchAll(MESSAGE_MENTION_RE)) {
    const index = match.index ?? 0
    if (index > last) {
      parts.push({ type: 'text', text: content.slice(last, index) })
    }
    if (match[1] != null) {
      parts.push({ type: 'file', path: match[1].slice(1) })
    } else if (match[2] != null) {
      parts.push({ type: 'skill', name: match[2].slice(1) })
    }
    last = index + match[0].length
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
    const last = merged[merged.length - 1]
    if (part.type === 'text' && last?.type === 'text') {
      last.text += part.text
    } else {
      merged.push(part.type === 'text' ? { ...part } : part)
    }
  }
  if (merged.length === 0) return ''
  if (merged[merged.length - 1]?.type !== 'text') {
    merged.push({ type: 'text', text: '' })
  }
  return serializeComposerParts(merged)
}
