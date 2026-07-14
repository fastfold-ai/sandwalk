import { describe, expect, it } from 'vitest'

import {
  CPU_PRESETS,
  DEFAULT_CPU_PRESET,
  DEFAULT_GPU_PRESET,
  GPU_PRESETS,
  matchCpuPresetId,
  matchGpuPreset
} from './sandbox-presets'

describe('sandbox-presets', () => {
  it('exposes non-empty cpu and gpu catalogs with defaults', () => {
    expect(CPU_PRESETS.length).toBeGreaterThan(0)
    expect(GPU_PRESETS.length).toBeGreaterThan(0)
    expect(DEFAULT_CPU_PRESET).toEqual(CPU_PRESETS[0])
    expect(DEFAULT_GPU_PRESET).toEqual(GPU_PRESETS[0])
  })

  it('matchCpuPresetId finds exact core/ram pairs', () => {
    expect(matchCpuPresetId(2, 8)).toBe('2c8g')
    expect(matchCpuPresetId(16, 64)).toBe('16c64g')
    expect(matchCpuPresetId(3, 8)).toBeNull()
  })

  it('matchGpuPreset finds gpu class or returns null', () => {
    expect(matchGpuPreset('T4')?.vram).toBe(16)
    expect(matchGpuPreset('H200')?.shortLabel).toContain('H200')
    expect(matchGpuPreset('not-a-gpu')).toBeNull()
  })
})
