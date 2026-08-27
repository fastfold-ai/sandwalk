const MENTION = /⟦#:[^⟧]+⟧/g
const FENCE = /```[\s\S]*?```/g
const INLINE_CODE = /`([^`]+)`/g
const LINK = /\[([^\]]+)\]\([^)]+\)/g
const BULLET = /^\s*[-*•]\s+/gm

export function speakableText(
  raw: string,
  maxSentences = 2,
  maxChars = 220
): string {
  const cleaned = raw
    .replace(FENCE, ' ')
    .replace(INLINE_CODE, '$1')
    .replace(LINK, '$1')
    .replace(MENTION, ' ')
    .replace(BULLET, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!cleaned) return ''
  const sentences = splitSentences(cleaned)
  let out = ''
  for (const sentence of sentences.slice(0, maxSentences)) {
    const next = out ? `${out} ${sentence}` : sentence
    if (next.length > maxChars) {
      out = next.slice(0, maxChars).trim()
      break
    }
    out = next
  }
  return out
}

export function splitSentences(text: string): string[] {
  const parts = text
    .split(/(?<=[.!?。！？])\s+/)
    .map(part => part.trim())
    .filter(Boolean)
  return parts.length ? parts : text.trim() ? [text.trim()] : []
}

export function completedSentences(delta: string): string[] {
  const trimmed = delta.trim()
  if (!trimmed) return []
  const sentences = splitSentences(trimmed)
  const last = sentences.at(-1) || ''
  if (/[.!?。！？]"?$/.test(last)) return sentences
  return sentences.slice(0, -1)
}

export function voiceReplyHint(language: string): string {
  return `(Voice: answer in ${language} in 1-2 short spoken sentences. No markdown, lists, or tool narration.)`
}

export function applyVoiceHint(text: string, language: string): string {
  const hint = voiceReplyHint(language)
  if (text.includes(hint)) return text
  return `${text.trim()}\n\n${hint}`
}
