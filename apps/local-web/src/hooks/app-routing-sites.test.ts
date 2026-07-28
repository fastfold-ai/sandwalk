import { describe, expect, it } from 'vitest'

import { matchAppRoutes } from '@/hooks/app-routing-helpers'

describe('site routes', () => {
  it('matches site detail routes', () => {
    expect(matchAppRoutes('/sites').siteRoute).toBeNull()
    expect(matchAppRoutes('/sites/site-123').siteRoute?.params.siteId).toBe(
      'site-123'
    )
  })

  it('does not treat a site id as an agent session', () => {
    expect(matchAppRoutes('/sites/site-123').sessionRoute).toBeNull()
  })
})
