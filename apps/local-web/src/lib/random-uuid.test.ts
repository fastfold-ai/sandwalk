import { afterEach, describe, expect, it, vi } from 'vitest'

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

describe('randomUUID on an HTTP LAN page', () => {
  const original = globalThis.crypto.randomUUID

  afterEach(() => {
    Object.defineProperty(globalThis.crypto, 'randomUUID', {
      configurable: true,
      writable: true,
      value: original
    })
    vi.resetModules()
  })

  it('builds an id when crypto.randomUUID is missing', async () => {
    Object.defineProperty(globalThis.crypto, 'randomUUID', {
      configurable: true,
      writable: true,
      value: undefined
    })
    vi.resetModules()
    const { randomUUID } = await import('./random-uuid')
    expect(randomUUID()).toMatch(UUID_RE)
    expect(globalThis.crypto.randomUUID()).toMatch(UUID_RE)
  })
})
