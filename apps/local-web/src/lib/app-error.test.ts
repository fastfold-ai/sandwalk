import { describe, expect, it } from 'vitest'

import {
  isAuthCredentialError,
  isBackendUnavailableError,
  normalizeAppError
} from './app-error'

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

  it('classifies network and 5xx as backend problems, not auth', () => {
    expect(isAuthCredentialError('Failed to fetch')).toBe(false)
    expect(isBackendUnavailableError('Failed to fetch')).toBe(true)
    // A connect probe that hits its AbortSignal.timeout deadline means the
    // server is not answering — must engage the retry loop, not stall it.
    const timedOut = new DOMException('signal timed out', 'TimeoutError')
    expect(isBackendUnavailableError(timedOut)).toBe(true)
    expect(
      isAuthCredentialError(
        'FastFold Agent API 500: {"detail":"boom"} [GET http://127.0.0.1:8787/v1/specialists]'
      )
    ).toBe(false)
    expect(
      isBackendUnavailableError(
        'FastFold Agent API 500: {"detail":"boom"} [GET http://127.0.0.1:8787/v1/specialists]'
      )
    ).toBe(true)
    expect(
      isAuthCredentialError(
        'FastFold Agent API 401: {"detail":"Missing or invalid backend API key."}'
      )
    ).toBe(true)
  })

  it('maps missing/invalid API key 401s to a clear Invalid API key title', () => {
    const info = normalizeAppError(
      'FastFold Agent API 401: {"detail":"Missing or invalid backend API key."}'
    )
    expect(info.title).toBe('Invalid API key')
    expect(info.detail).toMatch(/rejected by this server/i)
  })
})
