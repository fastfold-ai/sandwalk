import { describe, expect, it, vi } from 'vitest'

import { navigateBack } from './navigate-back'

describe('navigateBack', () => {
  it('uses history back when router stack has a prior entry', () => {
    const navigate = vi.fn()
    const previous = window.history.state
    window.history.replaceState({ idx: 2 }, '')
    navigateBack(navigate, '/dashboard/skills')
    expect(navigate).toHaveBeenCalledWith(-1)
    window.history.replaceState(previous, '')
  })

  it('falls back when this is the first router entry', () => {
    const navigate = vi.fn()
    const previous = window.history.state
    window.history.replaceState({ idx: 0 }, '')
    navigateBack(navigate, '/dashboard/skills')
    expect(navigate).toHaveBeenCalledWith('/dashboard/skills')
    window.history.replaceState(previous, '')
  })
})
