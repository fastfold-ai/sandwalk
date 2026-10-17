import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { DesktopUpdateProvider, useDesktopUpdate } from './useDesktopUpdate'

const updater = vi.hoisted(() => ({
  available: vi.fn(() => true),
  preview: vi.fn(() => null as string | null),
  check: vi.fn(),
  install: vi.fn()
}))

vi.mock('@/lib/desktop-updater', () => ({
  UPDATE_CHECK_INTERVAL_MS: 60_000,
  checkDesktopUpdate: () => updater.check(),
  desktopUpdaterAvailable: () => updater.available(),
  installDesktopUpdate: (options?: {
    onProgress?: (progress: { phase: string; received: number; total: number | null }) => void
  }) => updater.install(options),
  previewUpdateVersion: () => updater.preview()
}))

function renderUpdate() {
  return renderHook(() => useDesktopUpdate(), {
    wrapper: DesktopUpdateProvider
  })
}

beforeEach(() => {
  updater.available.mockReturnValue(true)
  updater.preview.mockReturnValue(null)
  updater.check.mockReset()
  updater.install.mockReset()
  sessionStorage.clear()
  vi.useFakeTimers()
})

describe('useDesktopUpdate', () => {
  it('returns an inert value outside the provider', () => {
    const { result } = renderHook(() => useDesktopUpdate())
    expect(result.current.available).toBe(false)
    expect(result.current.latestVersion).toBeNull()
  })

  it('surfaces an available update, dismisses it, and installs', async () => {
    vi.useRealTimers()
    updater.check.mockResolvedValue({
      kind: 'available',
      info: { version: '9.9.9' }
    })
    updater.install.mockImplementation(async (options?: {
      onProgress?: (progress: { phase: string; received: number; total: number | null }) => void
    }) => {
      options?.onProgress?.({ phase: 'download', received: 4, total: 10 })
      return { ok: false, message: 'disk full' }
    })
    const { result } = renderUpdate()
    await act(async () => {
      await result.current.checkForUpdate()
    })
    expect(result.current.available).toBe(true)
    expect(result.current.latestVersion).toBe('9.9.9')
    act(() => result.current.dismiss())
    expect(result.current.dismissed).toBe(true)
    expect(sessionStorage.getItem('sandwalk.update.dismissed:9.9.9')).toBe('1')
    await act(async () => {
      await result.current.installUpdate()
    })
    expect(result.current.error).toBe('disk full')
    expect(result.current.installing).toBe(false)
  })

  it('records the current build and a quiet error', async () => {
    vi.useRealTimers()
    updater.available.mockReturnValue(false)
    const { result } = renderUpdate()
    updater.available.mockReturnValue(true)
    updater.check.mockResolvedValue({ kind: 'current' })
    await act(async () => {
      await result.current.checkForUpdate()
    })
    expect(result.current.upToDate).toBe(true)
    updater.check.mockResolvedValue({ kind: 'error', message: 'offline' })
    await act(async () => {
      await result.current.checkForUpdate({ quiet: true })
    })
    expect(result.current.error).toBeNull()
    await act(async () => {
      await result.current.checkForUpdate()
    })
    expect(result.current.error).toBe('offline')
  })

  it('does nothing when the updater is unavailable', async () => {
    vi.useRealTimers()
    updater.available.mockReturnValue(false)
    const { result } = renderUpdate()
    await act(async () => {
      await result.current.checkForUpdate()
      await result.current.installUpdate()
    })
    expect(updater.check).not.toHaveBeenCalled()
    expect(result.current.hasChecked).toBe(false)
  })
})
