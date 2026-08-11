import type { Site } from '@sandwalk/agent-ui-core'
import { describe, expect, it } from 'vitest'

import {
  filterSites,
  formatSiteBytes,
  isPublishedSite,
  siteChatPath,
  sitePublicUrl,
  siteSourceLabel
} from '@/lib/sites'

const site: Site = {
  id: 'site-1',
  name: 'Results dashboard',
  slug: 'results',
  status: 'published',
  sourceSessionId: 'session-1',
  sourceProjectId: null,
  sourcePath: 'dist',
  sizeBytes: 2048,
  deployment: {
    id: 'deployment-1',
    status: 'published',
    slug: 'results',
    publicUrl: 'https://results.example.test',
    sizeBytes: 2048,
    createdAt: '2026-07-28T12:00:00Z',
    updatedAt: '2026-07-28T12:00:00Z',
    publishedAt: '2026-07-28T12:00:00Z'
  },
  createdAt: '2026-07-28T12:00:00Z',
  updatedAt: '2026-07-28T12:00:00Z'
}

describe('site view helpers', () => {
  it('searches names, slugs, paths, and public URLs', () => {
    expect(filterSites([site], 'RESULTS')).toEqual([site])
    expect(filterSites([site], 'example.test')).toEqual([site])
    expect(filterSites([site], 'dist')).toEqual([site])
    expect(filterSites([site], 'missing')).toEqual([])
  })

  it('formats sizes for the list', () => {
    expect(formatSiteBytes(null)).toBe('—')
    expect(formatSiteBytes(512)).toBe('512 B')
    expect(formatSiteBytes(2048)).toBe('2.0 KB')
  })

  it('resolves source and hosted metadata', () => {
    expect(
      siteSourceLabel(
        site,
        [{ id: 'session-1', title: 'Build report' } as never],
        []
      )
    ).toBe('Build report')
    expect(sitePublicUrl(site)).toBe('https://results.example.test')
    expect(isPublishedSite(site)).toBe(true)
  })

  it('links a site back to its source chat and preview panel', () => {
    expect(siteChatPath(site)).toBe('/agents/session-1?site=site-1')
    expect(siteChatPath({ ...site, sourceSessionId: null })).toBeNull()
  })
})
