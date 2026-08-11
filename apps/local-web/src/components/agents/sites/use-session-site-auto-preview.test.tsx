import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { Site } from '@sandwalk/agent-ui-core'
import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useSessionSiteAutoPreview } from './use-session-site-auto-preview'

const site = (updatedAt: string): Site => ({
  id: 'site-1',
  name: 'Report',
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

describe('useSessionSiteAutoPreview', () => {
  it('opens preview after a completed run changes the session site', async () => {
    const listSites = vi
      .fn()
      .mockResolvedValueOnce([site('2026-07-28T00:00:00Z')])
      .mockResolvedValueOnce([site('2026-07-28T00:01:00Z')])
    const client = { listSites } as unknown as LocalAgentClient
    const onSiteReady = vi.fn()

    const view = renderHook(
      ({ workspaceVersion }) =>
        useSessionSiteAutoPreview({
          client,
          sessionId: 'session-1',
          workspaceVersion,
          onSiteReady
        }),
      { initialProps: { workspaceVersion: 0 } }
    )

    await waitFor(() => expect(listSites).toHaveBeenCalledTimes(1))
    view.rerender({ workspaceVersion: 1 })

    await waitFor(() => expect(onSiteReady).toHaveBeenCalledTimes(1))
    expect(listSites).toHaveBeenCalledTimes(2)
  })
})
