import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { Site } from '@sandwalk/agent-ui-core'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SITE_PREVIEW_SANDBOX } from '@/lib/sites'

import { SitePreviewPanel } from './SitePreviewPanel'

afterEach(() => {
  cleanup()
})

const site = (updatedAt: string): Site => ({
  id: 'site-1',
  name: 'Research report',
  slug: null,
  status: 'ready',
  sourceSessionId: 'session-1',
  sourceProjectId: null,
  sourcePath: 'dist',
  sizeBytes: 42,
  deployment: null,
  createdAt: '2026-07-28T00:00:00Z',
  updatedAt
})

describe('SitePreviewPanel', () => {
  it('refreshes the iframe when the managed site changes', async () => {
    const listSites = vi
      .fn()
      .mockResolvedValueOnce([site('2026-07-28T00:00:00Z')])
      .mockResolvedValueOnce([site('2026-07-28T00:01:00Z')])
    const createSitePreviewTicket = vi
      .fn()
      .mockResolvedValueOnce({ url: 'http://local/preview/one/', expiresAt: null })
      .mockResolvedValueOnce({ url: 'http://local/preview/two/', expiresAt: null })
    const client = {
      listSites,
      createSitePreviewTicket
    } as unknown as LocalAgentClient
    const view = render(
      <SitePreviewPanel
        client={client}
        sessionId="session-1"
        workspaceVersion={0}
        runActive={false}
      />
    )

    await waitFor(() => {
      const frame = screen.getByTitle('Research report preview')
      expect(frame.getAttribute('src')).toBe('http://local/preview/one/')
      expect(frame.getAttribute('sandbox')).toBe(SITE_PREVIEW_SANDBOX)
    })

    view.rerender(
      <SitePreviewPanel
        client={client}
        sessionId="session-1"
        workspaceVersion={1}
        runActive={false}
      />
    )

    await waitFor(() => {
      expect(
        screen.getByTitle('Research report preview').getAttribute('src')
      ).toBe('http://local/preview/two/')
    })
    expect(createSitePreviewTicket).toHaveBeenCalledTimes(2)
  })

  it('opens the site requested by the Sites list', async () => {
    const requested = {
      ...site('2026-07-28T00:00:00Z'),
      id: 'site-2',
      name: 'Requested report'
    }
    const client = {
      listSites: vi
        .fn()
        .mockResolvedValue([site('2026-07-28T00:01:00Z'), requested]),
      createSitePreviewTicket: vi.fn().mockResolvedValue({
        url: 'http://local/preview/requested/',
        expiresAt: null
      }),
      publishSite: vi.fn().mockResolvedValue({
        ...requested,
        status: 'published',
        deployment: {
          id: 'deployment-1',
          status: 'published',
          slug: 'requested-report',
          publicUrl: 'https://requested-report.sandwalk.site',
          sizeBytes: 42,
          createdAt: '2026-07-28T00:00:00Z',
          updatedAt: '2026-07-28T00:00:00Z',
          publishedAt: '2026-07-28T00:00:00Z'
        }
      })
    } as unknown as LocalAgentClient
    const onClose = vi.fn()

    render(
      <SitePreviewPanel
        client={client}
        sessionId="session-1"
        siteId="site-2"
        workspaceVersion={0}
        runActive={false}
        onClose={onClose}
      />
    )

    await waitFor(() => {
      expect(screen.getByTitle('Requested report preview')).toBeTruthy()
    })
    expect(screen.getByLabelText('Preview site').parentElement?.className).toContain(
      'bg-muted'
    )
    screen.getByRole('button', { name: 'Publish' }).click()
    await waitFor(() => {
      expect(
        screen.getByRole('button', {
          name: 'Open published site https://requested-report.sandwalk.site'
        })
      ).toBeTruthy()
    })
    screen.getByRole('button', { name: 'Hide site preview' }).click()
    expect(onClose).toHaveBeenCalledOnce()
  })
})
