import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DesktopUpdateBanner } from './DesktopUpdateBanner'

const update = {
  available: true,
  currentVersion: '0.0.1',
  latestVersion: '0.1.0-beta.1',
  checking: false,
  installing: false,
  progress: null,
  error: null as string | null,
  hasChecked: true,
  upToDate: false as boolean | null,
  dismissed: false,
  checkForUpdate: vi.fn(),
  installUpdate: vi.fn(),
  dismiss: vi.fn()
}

vi.mock('@/hooks/useDesktopUpdate', () => ({
  useDesktopUpdate: () => update
}))

afterEach(() => {
  cleanup()
  update.available = true
  update.installing = false
  update.error = null
  update.dismissed = false
  update.progress = null
})

describe('DesktopUpdateBanner', () => {
  it('shows a compact sidebar offer with Later and Install Now', () => {
    render(<DesktopUpdateBanner />)
    expect(screen.getByText('New update available')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Later' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Install Now' })).toBeTruthy()
  })

  it('shows installing progress instead of actions', () => {
    update.installing = true
    update.progress = { phase: 'download', received: 50, total: 100 }
    render(<DesktopUpdateBanner />)
    expect(screen.getByText('Downloading… 50%')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Install Now' })).toBeNull()
  })
})
