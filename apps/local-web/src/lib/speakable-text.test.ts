import { describe, expect, it } from 'vitest'

import {
  applyVoiceHint,
  completedSentences,
  pronounceForSpeech,
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
    expect(speakableText(dump).length).toBeLessThanOrEqual(280)
  })

  it('keeps longer Chinese sentences together', () => {
    const text = '你好，我是卡皮。我可以开新对话，并慢慢回答你提出的每一个问题。'
    expect(speakableText(text, undefined, undefined, 'zh')).toContain('每一个问题')
  })
})

describe('pronounceForSpeech', () => {
  it('says Capy as a name, not letter by letter', () => {
    expect(pronounceForSpeech("Hi, I'm Capy.")).toBe("Hi, I'm cappie.")
    expect(pronounceForSpeech('soy Capy.', 'es')).toBe('soy cappie.')
    expect(pronounceForSpeech('我是 Capy。', 'zh')).toBe('我是 卡皮。')
    expect(speakableText("I'm Capy. Ready.")).toBe("I'm cappie. Ready.")
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
