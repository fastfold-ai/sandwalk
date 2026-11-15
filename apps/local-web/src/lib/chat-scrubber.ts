/** The scrollbar ticks stay hidden until a chat is long enough to need them. */
export const CHAT_SCRUBBER_MIN_MESSAGES = 21

const PREVIEW_LIMIT = 160

export type ChatScrubberTurn = {
  id: string
  /** Index in the full message list. */
  index: number
  /** The user's prompt, on one line. */
  label: string
  /** Start of the reply that closed this turn, if there is one yet. */
  reply: string | null
}

export function chatScrubberEnabled(messageCount: number): boolean {
  return messageCount >= CHAT_SCRUBBER_MIN_MESSAGES
}

function oneLine(content: string): string {
  const text = content
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/[*`#>]+/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (text.length <= PREVIEW_LIMIT) return text
  return `${text.slice(0, PREVIEW_LIMIT - 1)}…`
}

/** One line of the user prompt, for the hover card. */
export function chatScrubberLabel(content: string): string {
  return oneLine(content) || 'Message'
}

export function chatScrubberTurns(
  messages: { id: string; role: string; content: string }[]
): ChatScrubberTurn[] {
  if (!chatScrubberEnabled(messages.length)) return []
  const turns: ChatScrubberTurn[] = []
  messages.forEach((message, index) => {
    if (message.role === 'user') {
      turns.push({
        id: message.id,
        index,
        label: chatScrubberLabel(message.content),
        reply: null
      })
      return
    }
    // The last assistant message before the next prompt is the answer.
    const turn = turns.at(-1)
    if (turn && message.role === 'assistant') {
      turn.reply = oneLine(message.content) || turn.reply
    }
  })
  return turns
}
