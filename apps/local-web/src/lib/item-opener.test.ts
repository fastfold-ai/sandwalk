import { describe, expect, it, vi } from 'vitest'

import { openItem, setItemOpener } from './item-opener'

describe('openItem', () => {
  it('does nothing until an opener is installed, then forwards the id', () => {
    setItemOpener(null)
    expect(() => openItem('chat-1')).not.toThrow()
    const opener = vi.fn()
    setItemOpener(opener)
    openItem('chat-1')
    expect(opener).toHaveBeenCalledWith('chat-1')
    setItemOpener(null)
  })
})
