import { describe, expect, it } from 'vitest'

import { dragHasFiles } from './useComposerFileDrop'

describe('dragHasFiles', () => {
  it('detects Files in dataTransfer types', () => {
    const event = {
      dataTransfer: { types: ['Files', 'text/plain'] }
    } as unknown as DragEvent
    expect(dragHasFiles(event as never)).toBe(true)
  })

  it('returns false without Files', () => {
    const event = {
      dataTransfer: { types: ['text/plain'] }
    } as unknown as DragEvent
    expect(dragHasFiles(event as never)).toBe(false)
  })
})
