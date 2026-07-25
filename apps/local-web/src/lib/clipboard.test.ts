import { afterEach, describe, expect, it, vi } from 'vitest'

import { copyText } from './clipboard'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function stubClipboard(writeText: unknown) {
  vi.stubGlobal('navigator', { clipboard: { writeText } })
}

describe('copyText', () => {
  it('uses the async clipboard API when it works', async () => {
    const writeText = vi.fn(async () => undefined)
    stubClipboard(writeText)

    await expect(copyText('hello')).resolves.toBe(true)
    expect(writeText).toHaveBeenCalledWith('hello')
  })

  it('falls back when the clipboard API rejects', async () => {
    // A rejected write is the common desktop-webview failure, and the old code
    // reported success anyway.
    stubClipboard(
      vi.fn(async () => {
        throw new Error('NotAllowedError')
      })
    )
    const exec = vi.fn(() => true)
    document.execCommand = exec as unknown as typeof document.execCommand

    await expect(copyText('hello')).resolves.toBe(true)
    expect(exec).toHaveBeenCalledWith('copy')
  })

  it('falls back when the clipboard API is missing entirely', async () => {
    vi.stubGlobal('navigator', {})
    const exec = vi.fn(() => true)
    document.execCommand = exec as unknown as typeof document.execCommand

    await expect(copyText('hello')).resolves.toBe(true)
  })

  it('reports failure when both paths fail', async () => {
    stubClipboard(
      vi.fn(async () => {
        throw new Error('nope')
      })
    )
    document.execCommand = vi.fn(() => false) as unknown as typeof document.execCommand

    await expect(copyText('hello')).resolves.toBe(false)
  })

  it('treats empty text as nothing to copy', async () => {
    const writeText = vi.fn(async () => undefined)
    stubClipboard(writeText)

    await expect(copyText('')).resolves.toBe(false)
    expect(writeText).not.toHaveBeenCalled()
  })

  it('cleans up the fallback element', async () => {
    vi.stubGlobal('navigator', {})
    document.execCommand = vi.fn(() => true) as unknown as typeof document.execCommand

    await copyText('hello')
    expect(document.querySelectorAll('textarea')).toHaveLength(0)
  })
})
