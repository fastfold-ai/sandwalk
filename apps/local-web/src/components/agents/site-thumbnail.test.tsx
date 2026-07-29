import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { Site } from '@sandwalk/agent-ui-core'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SiteThumbnail } from './site-thumbnail'

afterEach(cleanup)

describe('SiteThumbnail', () => {
  it('renders a scriptless sandbox preview', async () => {
    const client = {
      createSitePreviewTicket: vi.fn().mockResolvedValue({
        url: 'http://local/preview/token/',
        expiresAt: null
      })
    } as unknown as LocalAgentClient
    const site: Site = {
      id: 'site-1',
      name: 'Protein report',
      slug: null,
      status: 'ready',
      sourceSessionId: 'session-1',
      sourceProjectId: null,
      sourcePath: 'dist',
      sizeBytes: 42,
      deployment: null,
      createdAt: '2026-07-28T00:00:00Z',
      updatedAt: '2026-07-28T00:00:00Z'
    }

    render(<SiteThumbnail client={client} site={site} />)

    await waitFor(() => {
      const frame = screen.getByTitle('Protein report thumbnail')
      expect(frame.getAttribute('src')).toBe('http://local/preview/token/')
      expect(frame.getAttribute('sandbox')).toBe('')
    })
  })
})
