import { describe, expect, it } from 'vitest'

import {
  CHAT_SCRUBBER_MIN_MESSAGES,
  chatScrubberEnabled,
  chatScrubberLabel,
  chatScrubberTurns
} from './chat-scrubber'

function messages(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    id: `m${index}`,
    role: index % 2 === 0 ? 'user' : 'assistant',
    content: index === 0 ? '  hello\nworld  ' : `turn ${index}`
  }))
}

describe('chat scrubber', () => {
  it('stays hidden until the chat has more than 20 messages', () => {
    expect(chatScrubberEnabled(20)).toBe(false)
    expect(chatScrubberEnabled(CHAT_SCRUBBER_MIN_MESSAGES)).toBe(true)
    expect(chatScrubberTurns(messages(20))).toEqual([])
  })

  it('makes one entry per user turn with its prompt and reply', () => {
    const turns = chatScrubberTurns(messages(21))
    expect(turns.map(turn => turn.id)).toEqual([
      'm0',
      'm2',
      'm4',
      'm6',
      'm8',
      'm10',
      'm12',
      'm14',
      'm16',
      'm18',
      'm20'
    ])
    expect(turns[0]?.label).toBe('hello world')
    expect(turns[0]?.reply).toBe('turn 1')
    // The newest prompt has no answer yet.
    expect(turns.at(-1)?.reply).toBeNull()
  })

  it('uses the last assistant message of a turn as the reply', () => {
    const list = messages(21)
    list.splice(2, 0, {
      id: 'extra',
      role: 'assistant',
      content: '**Final** `answer`\n```js\ncode()\n```'
    })
    expect(chatScrubberTurns(list)[0]?.reply).toBe('Final answer')
  })

  it('truncates a long prompt and names an empty one', () => {
    expect(chatScrubberLabel('')).toBe('Message')
    expect(chatScrubberLabel('x'.repeat(200)).endsWith('…')).toBe(true)
    expect(chatScrubberLabel('x'.repeat(200)).length).toBe(160)
  })
})
