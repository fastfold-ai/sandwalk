import { describe, expect, it } from 'vitest'

import { normalizeAppError } from './app-error'

describe('normalizeAppError extras', () => {
  it('handles empty input', () => {
    const info = normalizeAppError('')
    expect(info.title).toBe('Something went wrong')
    expect(info.raw).toBe('')
  })

  it('detects chunk load failures', () => {
    const info = normalizeAppError('Loading chunk 12 failed')
    expect(info.title).toBe('Failed to load UI')
  })
})
