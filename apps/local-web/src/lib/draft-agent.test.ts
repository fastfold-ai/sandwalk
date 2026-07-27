import { describe, expect, it } from 'vitest'

import {
  DRAFT_AGENT_SESSION_ID,
  isDraftAgentSessionId,
  isReservedAgentRouteId
} from '@/lib/draft-agent'

describe('draft-agent', () => {
  it('recognizes the draft sentinel', () => {
    expect(DRAFT_AGENT_SESSION_ID).toBe('new')
    expect(isDraftAgentSessionId('new')).toBe(true)
    expect(isDraftAgentSessionId('abc')).toBe(false)
    expect(isDraftAgentSessionId(null)).toBe(false)
  })

  it('treats draft and legacy reserved routes as reserved', () => {
    expect(isReservedAgentRouteId('new')).toBe(true)
    expect(isReservedAgentRouteId('home')).toBe(true)
    expect(isReservedAgentRouteId('skills')).toBe(true)
    expect(isReservedAgentRouteId('integrations')).toBe(true)
    expect(isReservedAgentRouteId('sess_123')).toBe(false)
  })
})
