import { describe, expect, it } from 'vitest'

import { normalizeAppError } from './app-error'
import {
  formatConnectError,
  loginPathWithNext,
  nextFromSearch,
  sanitizeAuthReturnTo
} from './auth-routing'

describe('sanitizeAuthReturnTo', () => {
  it('accepts in-app paths and rejects login loops', () => {
    expect(sanitizeAuthReturnTo('/dashboard/integrations/modal')).toBe(
      '/dashboard/integrations/modal'
    )
    expect(sanitizeAuthReturnTo('//evil')).toBeNull()
    expect(sanitizeAuthReturnTo('/login')).toBeNull()
    expect(sanitizeAuthReturnTo(null)).toBeNull()
  })
})

describe('loginPathWithNext / nextFromSearch', () => {
  it('round-trips next param', () => {
    expect(loginPathWithNext('/dashboard/agent/sandbox')).toBe(
      '/?next=%2Fdashboard%2Fagent%2Fsandbox'
    )
    expect(nextFromSearch('?next=%2Fdashboard%2Fagent%2Fsandbox')).toBe(
      '/dashboard/agent/sandbox'
    )
  })
})

describe('normalizeAppError', () => {
  it('maps 404 API failures with path', () => {
    const info = normalizeAppError(
      'FastFold Agent API 404: Not Found [GET http://127.0.0.1:8787/v1/settings/sandbox]'
    )
    expect(info.title).toBe('Not found')
    expect(info.status).toBe(404)
    expect(info.detail).toContain('/v1/settings/sandbox')
    expect(info.stack).toBeTruthy()
  })

  it('keeps Error stacks', () => {
    const err = new Error('boom')
    err.stack = 'Error: boom\n    at connect (App.tsx:1:1)'
    const info = normalizeAppError(err)
    expect(info.title).toBe('Something went wrong')
    expect(info.stack).toContain('App.tsx')
    expect(info.name).toBe('Error')
  })

  it('maps network failures', () => {
    const info = normalizeAppError('TypeError: Failed to fetch')
    expect(info.title).toBe('Backend unreachable')
  })

  it('maps auth failures', () => {
    const info = normalizeAppError('FastFold Agent API 401: Unauthorized')
    expect(info.title).toBe('Authentication failed')
    expect(info.status).toBe(401)
  })

  it('maps server errors from JSON detail', () => {
    const info = normalizeAppError('FastFold Agent API 500: {"detail":"boom"}')
    expect(info.title).toBe('Backend error')
    expect(info.detail).toBe('boom')
  })
})

describe('formatConnectError compat', () => {
  it('still works for connect form callers', () => {
    const info = formatConnectError('FastFold Agent API 404: Not Found')
    expect(info.title).toBe('Not found')
    expect(info.technical).toBeTruthy()
  })
})
