const MENTION = /⟦#:[^⟧]+⟧/g
const FENCE = /```[\s\S]*?```/g
const INLINE_CODE = /`([^`]+)`/g
const LINK = /\[([^\]]+)\]\([^)]+\)/g
const BULLET = /^\s*[-*•]\s+/gm

export function speakableBudget(languageCode = 'en'): {
  sentences: number
  chars: number
} {
  if (languageCode === 'zh' || languageCode === 'ja') {
    return { sentences: 6, chars: 600 }
  }
  return { sentences: 2, chars: 280 }
}

export function speakableText(
  raw: string,
  maxSentences?: number,
  maxChars?: number,
  languageCode = 'en'
): string {
  const budget = speakableBudget(languageCode)
  maxSentences ??= budget.sentences
  maxChars ??= budget.chars
  const cleaned = pronounceForSpeech(
    raw
      .replace(FENCE, ' ')
      .replace(INLINE_CODE, '$1')
      .replace(LINK, '$1')
      .replace(MENTION, ' ')
      .replace(BULLET, '')
      .replace(/\s+/g, ' ')
      .trim(),
    languageCode
  )
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
    .split(/(?<=[.!?。！？…])\s*/)
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
  const longer = /chinese|mandarin|japanese|中文|日本語/i.test(language)
  const length = longer
    ? '3-5 spoken sentences'
    : '1-2 short spoken sentences'
  return `(Voice: answer in ${language} in ${length}. No markdown, lists, or tool narration.)`
}

/** Spoken form so Kokoro says the name, not C-A-P-Y. */
export function spokenCapyName(languageCode = 'en'): string {
  switch (languageCode) {
    case 'ja':
      return 'キャピー'
    case 'zh':
      return '卡皮'
    case 'hi':
      return 'कैपी'
    default:
      // Lowercase so Kokoro G2P treats it as a word, not C-A-P-Y.
      return 'cappie'
  }
}

export function pronounceForSpeech(text: string, languageCode = 'en'): string {
  const spoken = spokenCapyName(languageCode)
  return text.replace(/\bCapp?y\b/gi, spoken)
}

export function applyVoiceHint(text: string, language: string): string {
  const hint = voiceReplyHint(language)
  if (text.includes(hint)) return text
  return `${text.trim()}\n\n${hint}`
}
