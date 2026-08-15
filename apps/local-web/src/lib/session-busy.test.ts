import { describe, expect, it } from 'vitest'

import { isSessionBusyError } from './session-busy'

describe('isSessionBusyError', () => {
  it('matches the FastFold Agent API 409 payload', () => {
    expect(
      isSessionBusyError(
        'FastFold Agent API 409: {"detail": "This session already has an active run."} [POST http://127.0.0.1:8787/v1/sessions/x/messages]'
      )
    ).toBe(true)
  })

  it('ignores unrelated failures', () => {
    expect(isSessionBusyError('Unable to send message')).toBe(false)
    expect(isSessionBusyError('FastFold Agent API 500: boom')).toBe(false)
  })
})
