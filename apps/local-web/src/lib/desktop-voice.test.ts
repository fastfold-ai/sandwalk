import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  appendTranscript,
  browserDictationStatus,
  downloadDictationModel,
  getDictationStatus,
  getVoiceInputOwner,
  isCapyOwnedVoiceInput,
  publishVoiceInputChanged,
  startDictation,
  usableVoiceTranscript,
  voiceReady
} from './desktop-voice'

describe('usableVoiceTranscript', () => {
  it('drops Whisper blank and special tokens', () => {
    expect(usableVoiceTranscript('')).toBeNull()
    expect(usableVoiceTranscript('   ')).toBeNull()
    expect(usableVoiceTranscript('[BLANK_AUDIO]')).toBeNull()
    expect(usableVoiceTranscript('[_EOT_]')).toBeNull()
    expect(usableVoiceTranscript('[_TT_100] [_EOT_]')).toBeNull()
    expect(usableVoiceTranscript('Hola [_EOT_]')).toBe('Hola')
    expect(usableVoiceTranscript('Hola, ¿cómo estás?')).toBe(
      'Hola, ¿cómo estás?'
    )
  })
})

describe('appendTranscript', () => {
  it('returns draft when transcript is empty', () => {
    expect(appendTranscript('hello', '  ')).toBe('hello')
    expect(appendTranscript('', '')).toBe('')
  })

  it('appends with a space when draft has content', () => {
    expect(appendTranscript('hello', 'world')).toBe('hello world')
    expect(appendTranscript('hello  ', '  world  ')).toBe('hello world')
  })

  it('uses transcript alone when draft is empty', () => {
    expect(appendTranscript('', 'hello')).toBe('hello')
    expect(appendTranscript('   ', 'hello')).toBe('hello')
  })
})

describe('voiceReady', () => {
  it('requires supported + verified + test passed', () => {
    expect(voiceReady(null)).toBe(false)
    expect(
      voiceReady({
        ...browserDictationStatus(),
        supported: true,
        model_verified: true,
        test_passed: false
      })
    ).toBe(false)
    expect(
      voiceReady({
        ...browserDictationStatus(),
        supported: true,
        model_verified: true,
        test_passed: true
      })
    ).toBe(true)
  })
})

describe('desktop-voice soft-fail outside Tauri', () => {
  afterEach(() => {
    Reflect.deleteProperty(globalThis as object, '__TAURI__')
    Reflect.deleteProperty(globalThis as object, '__TAURI_INTERNALS__')
  })

  it('returns unsupported browser status', () => {
    const status = browserDictationStatus()
    expect(status.supported).toBe(false)
    expect(status.active_model).toBe('multi')
    expect(status.compatibility_reason).toMatch(/desktop app/i)
  })

  it('getDictationStatus returns null without Tauri', async () => {
    await expect(getDictationStatus()).resolves.toBeNull()
  })

  it('startDictation throws a desktop-only error without Tauri', async () => {
    await expect(startDictation()).rejects.toThrow(/desktop app/i)
  })
})

describe('desktop-voice invoke wrappers', () => {
  afterEach(() => {
    Reflect.deleteProperty(globalThis as object, '__TAURI__')
  })

  it('getDictationStatus forwards Tauri invoke results', async () => {
    const status = {
      ...browserDictationStatus(),
      supported: true,
      model_verified: true,
      test_passed: true
    }
    const invoke = vi.fn().mockResolvedValue(status)
    ;(globalThis as { __TAURI__?: unknown }).__TAURI__ = {
      core: { invoke }
    }
    await expect(getDictationStatus()).resolves.toEqual(status)
    expect(invoke).toHaveBeenCalledWith('get_dictation_status', undefined)
  })

  it('downloadDictationModel invokes the Tauri command with no model id', async () => {
    const invoke = vi.fn().mockResolvedValue({
      ...browserDictationStatus(),
      supported: true
    })
    ;(globalThis as { __TAURI__?: unknown }).__TAURI__ = {
      core: { invoke }
    }
    await downloadDictationModel()
    expect(invoke).toHaveBeenCalledWith('download_dictation_model', undefined)
  })
})

describe('voice input owner', () => {
  afterEach(() => {
    publishVoiceInputChanged(browserDictationStatus(), 'composer')
  })

  it('marks Capy recordings so composers can ignore them', () => {
    const status = {
      ...browserDictationStatus(),
      recording: true
    }
    publishVoiceInputChanged(status, 'capy')
    expect(getVoiceInputOwner()).toBe('capy')
    expect(
      isCapyOwnedVoiceInput({ ...status, owner: 'capy' }, 'capy')
    ).toBe(true)
    expect(isCapyOwnedVoiceInput({ ...status, owner: 'composer' })).toBe(false)
  })
})
