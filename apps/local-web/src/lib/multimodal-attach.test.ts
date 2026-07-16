import { describe, expect, it } from 'vitest'

import {
  modelSupportsMultimodalKind,
  multimodalKindForFile,
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
