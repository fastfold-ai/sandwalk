import { describe, expect, it } from 'vitest'

import { buildZipStore, crc32 } from './zip-store'

describe('zip-store', () => {
  it('checksums known bytes', () => {
    expect(crc32(new TextEncoder().encode('123456789'))).toBe(0xcbf43926)
  })

  it('builds a store zip with local and central headers', async () => {
    const blob = buildZipStore([
      { name: 'a.json', data: new TextEncoder().encode('{"ok":true}') }
    ])
    const bytes = new Uint8Array(await blob.arrayBuffer())
    expect(bytes[0]).toBe(0x50)
    expect(bytes[1]).toBe(0x4b)
    expect(new TextDecoder().decode(bytes)).toContain('a.json')
    expect(new TextDecoder().decode(bytes)).toContain('{"ok":true}')
  })
})
