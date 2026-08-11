import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { Site } from '@sandwalk/agent-ui-core'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SitesView } from './SitesView'

afterEach(() => {
  cleanup()
})

const site: Site = {
  id: 'site-1',
  name: 'Research brief',
  slug: null,
  status: 'ready',
  sourceSessionId: 'session-1',
  sourceProjectId: null,
  sourcePath: 'dist',
  sizeBytes: 2048,
  deployment: null,
  createdAt: '2026-07-28T00:00:00Z',
  updatedAt: '2026-07-28T00:00:00Z'
}

describe('SitesView layout', () => {
  it('switches between gallery and list views', async () => {
    const client = {
      listSites: vi.fn().mockResolvedValue([site]),
      createSitePreviewTicket: vi.fn().mockResolvedValue({
        url: 'http://local/preview/token/',
        expiresAt: null
      })
    } as unknown as LocalAgentClient

    render(
      <SitesView
        client={client}
        navigate={vi.fn()}
        siteId={null}
        sessions={[]}
        projects={[]}
        onAddSite={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Research brief')).toBeTruthy()
    })
    expect(screen.queryByText('Status')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'List view' }))

    expect(screen.getByText('Status')).toBeTruthy()
  })
})
