import { describe, expect, it } from 'vitest'

import {
  modelSupportsMultimodalKind,
  multimodalKindForFile,
  resolveMultimodalCapabilityFlags,
  unsupportedMultimodalHint
} from './multimodal-attach'

describe('multimodalKindForFile', () => {
  it('maps Deep Agents extensions', () => {
    expect(multimodalKindForFile({ name: 'a.PNG' })).toBe('image')
    expect(multimodalKindForFile({ name: 'doc.pdf' })).toBe('file')
    expect(multimodalKindForFile({ name: 'x.wav' })).toBe('audio')
    expect(multimodalKindForFile({ name: 'x.mp4' })).toBe('video')
    expect(multimodalKindForFile({ name: 'data.csv' })).toBeNull()
  })
})

describe('modelSupportsMultimodalKind', () => {
  it('reads capability flags', () => {
    const flags = {
      supportsImageInputs: true,
      supportsPdfInputs: false,
      supportsAudioInputs: false,
      supportsVideoInputs: false
    }
    expect(modelSupportsMultimodalKind(flags, 'image')).toBe(true)
    expect(modelSupportsMultimodalKind(flags, 'file')).toBe(false)
  })
})

describe('unsupportedMultimodalHint', () => {
  it('returns a non-empty hint', () => {
    expect(unsupportedMultimodalHint('image')).toMatch(/vision/i)
  })
})

describe('resolveMultimodalCapabilityFlags', () => {
  it('infers image+video for local Qwen3.5 / 3.6 even when API flags are false', () => {
    const flags = resolveMultimodalCapabilityFlags({
      provider: 'local',
      id: 'Unsloth Qwen3.6 35B A3B UD',
      label: 'Unsloth Qwen3.6 35B A3B UD',
      supportsImageInputs: false,
      supportsVideoInputs: false
    })
    expect(flags.supportsImageInputs).toBe(true)
    expect(flags.supportsVideoInputs).toBe(true)
    expect(flags.supportsPdfInputs).toBe(false)
  })

  it('does not mark DeepSeek V4 Flash as vision', () => {
    const flags = resolveMultimodalCapabilityFlags({
      provider: 'local',
      id: 'DeepSeek-V4-Flash',
      label: 'Deepseek V4 Flash'
    })
    expect(flags.supportsImageInputs).toBe(false)
  })

  it('keeps Diffusion Gemma vision under openai runtime provider', () => {
    const flags = resolveMultimodalCapabilityFlags({
      provider: 'openai',
      id: 'diffusiongemma-26B-A4B-it-4bit',
      label: 'Diffusiongemma 26B A4B It 4bit oMLX',
      supportsImageInputs: false
    })
    expect(flags.supportsImageInputs).toBe(true)
  })

  it('marks Gemini 4 Argon and Meta Muse as supporting Image, PDF, Audio, and Video', () => {
    for (const model of [
      { provider: 'google', id: 'gemini-4-argon', label: 'Gemini 4 Argon' },
      { provider: 'meta', id: 'muse-wonder-1.0', label: 'Muse Wonder 1.0' },
      { provider: 'meta', id: 'muse-spark-1.3', label: 'Muse Spark 1.3' }
    ]) {
      expect(resolveMultimodalCapabilityFlags(model)).toEqual({
        supportsImageInputs: true,
        supportsPdfInputs: true,
        supportsAudioInputs: true,
        supportsVideoInputs: true
      })
    }
  })
})
