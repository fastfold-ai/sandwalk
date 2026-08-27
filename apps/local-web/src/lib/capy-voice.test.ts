import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  CAPY_VOICE_SPEED_KEY,
  DEFAULT_CAPY_VOICE_SPEED,
  defaultVoiceForLanguage,
  detectSpeechLanguage,
  languageCodeFromVoice,
  languageForVoice,
  previewPhrase,
  readCapyVoiceSpeed,
  shouldSpeakCapyReply,
  voiceForDetectedText
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

describe('detectSpeechLanguage', () => {
  it('picks a Kokoro language from script or cue words', () => {
    expect(detectSpeechLanguage('你好，我是 Capy。')).toBe('zh')
    expect(detectSpeechLanguage('こんにちは、キャピーです。')).toBe('ja')
    expect(detectSpeechLanguage('नमस्ते, मैं कैपी हूँ।')).toBe('hi')
    expect(detectSpeechLanguage('Hola, soy Capy.')).toBe('es')
    expect(detectSpeechLanguage("Hi, I'm Capy.")).toBe('en')
    expect(languageCodeFromVoice('cb_zh')).toBe('zh')
    expect(voiceForDetectedText('你好', 'af_heart')).toBe(
      defaultVoiceForLanguage('zh')
    )
    expect(
      voiceForDetectedText('你好', 'cb_en', [
        { id: 'cb_en', language_code: 'en' },
        { id: 'cb_zh', language_code: 'zh' }
      ])
    ).toBe('cb_zh')
    expect(voiceForDetectedText('你好', 'zm_yunjian')).toBe('zm_yunjian')
  })
})

describe('readCapyVoiceSpeed', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function installSpeedStore(value: string | null) {
    const store = new Map<string, string>()
    if (value != null) store.set(CAPY_VOICE_SPEED_KEY, value)
    const memory: Storage = {
      get length() {
        return store.size
      },
      clear() {
        store.clear()
      },
      getItem(key: string) {
        return store.has(key) ? store.get(key)! : null
      },
      key(index: number) {
        return [...store.keys()][index] ?? null
      },
      removeItem(key: string) {
        store.delete(key)
      },
      setItem(key: string, next: string) {
        store.set(key, String(next))
      }
    }
    vi.stubGlobal('localStorage', memory)
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: memory
    })
  }

  it('defaults to 1.0x when nothing is stored', () => {
    installSpeedStore(null)
    expect(readCapyVoiceSpeed()).toBe(DEFAULT_CAPY_VOICE_SPEED)
    expect(readCapyVoiceSpeed()).toBe(1)
  })

  it('keeps a saved speed in range', () => {
    installSpeedStore('1.4')
    expect(readCapyVoiceSpeed()).toBe(1.4)
  })
})

describe('previewPhrase', () => {
  it('returns a short line in the voice language', () => {
    expect(previewPhrase('en')).toMatch(/I'm Capy/)
    expect(previewPhrase('es')).toMatch(/soy Capy/)
  })
})
