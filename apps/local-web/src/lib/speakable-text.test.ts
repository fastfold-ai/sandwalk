import { describe, expect, it } from 'vitest'

import {
  applyVoiceHint,
  completedSentences,
  speakableText,
  voiceReplyHint
} from './speakable-text'

describe('speakableText', () => {
  it('strips markdown, chips, and bullets then caps sentences', () => {
    expect(
      speakableText(
        'Hello **world**. ```code``` more. [link](https://x) and ⟦#:abc⟧\n- item'
      )
    ).toMatch(/Hello/)
    expect(speakableText('One. Two. Three.')).toBe('One. Two.')
  })

  it('does not speak empty or code-only dumps', () => {
    expect(speakableText('```\nfn main() {}\n```')).toBe('')
  })

  it('caps long doctor-style dumps', () => {
    const dump = `${'Error: something failed. '.repeat(20)}Fix: restart.`
    expect(speakableText(dump).length).toBeLessThanOrEqual(220)
  })
})

describe('completedSentences', () => {
  it('waits for the unfinished trailing sentence', () => {
    expect(completedSentences('Hello there. I am still')).toEqual([
      'Hello there.'
    ])
    expect(completedSentences('Done.')).toEqual(['Done.'])
  })
})

describe('voiceReplyHint', () => {
  it('asks Capy to speak in the selected language', () => {
    expect(voiceReplyHint('Spanish')).toMatch(/Spanish/)
    expect(applyVoiceHint('Hi', 'English')).toContain(voiceReplyHint('English'))
  })
})
