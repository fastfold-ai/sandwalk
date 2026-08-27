import { describe, expect, it } from 'vitest'

import {
  languageForVoice,
  previewPhrase,
  shouldSpeakCapyReply
} from './capy-voice'

describe('shouldSpeakCapyReply', () => {
  it('stays silent for typed turns unless speak-all is on', () => {
    expect(shouldSpeakCapyReply(false, false)).toBe(false)
    expect(shouldSpeakCapyReply(true, false)).toBe(true)
    expect(shouldSpeakCapyReply(false, true)).toBe(true)
  })
})

describe('languageForVoice', () => {
  it('maps the selected Kokoro voice to a language name', () => {
    expect(
      languageForVoice('ef_dora', [
        { id: 'af_heart', language: 'English' },
        { id: 'ef_dora', language: 'Spanish' }
      ])
    ).toBe('Spanish')
    expect(languageForVoice('missing', [])).toBe('English')
  })
})

describe('previewPhrase', () => {
  it('returns a short line in the voice language', () => {
    expect(previewPhrase('en')).toMatch(/Capy/)
    expect(previewPhrase('es')).toMatch(/Capy/)
  })
})
