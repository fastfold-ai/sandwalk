import { describe, expect, it } from 'vitest'

import { resolveDashboardSection } from '@/hooks/app-routing-helpers'

describe('resolveDashboardSection voice', () => {
  it('maps /dashboard/voice to voice', () => {
    expect(resolveDashboardSection('/dashboard/voice')).toBe('voice')
    expect(resolveDashboardSection('/dashboard/voice/extra')).toBe('voice')
  })
})
