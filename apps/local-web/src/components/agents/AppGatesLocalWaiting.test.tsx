import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppGatesLocalWaiting } from './AppGatesLocalWaiting'

afterEach(() => {
  cleanup()
})

const props = {
  connecting: false,
  connectError: null as unknown,
  connect: vi.fn(),
  backendUrl: 'http://127.0.0.1:8787',
  setBackendUrl: vi.fn(),
  backendApiKey: '',
  setBackendApiKey: vi.fn()
}

describe('AppGatesLocalWaiting', () => {
  it('shows a starting wait instead of the unreachable error while the server boots', () => {
    render(
      <AppGatesLocalWaiting
        {...props}
        backendDown
        starting
        connectError={new Error('Failed to fetch')}
      />
    )
    expect(screen.getByText('Server is starting. Please wait.')).toBeTruthy()
    expect(screen.queryByText('Backend unreachable')).toBeNull()
    expect(screen.queryByText('Local agent API error')).toBeNull()
  })

  it('shows the unreachable error after boot has failed', () => {
    render(
      <AppGatesLocalWaiting
        {...props}
        backendDown
        starting={false}
        connectError={new Error('TypeError: Failed to fetch')}
      />
    )
    expect(screen.getByText('Local agent API error')).toBeTruthy()
    expect(screen.getByText('Backend unreachable')).toBeTruthy()
  })
})
