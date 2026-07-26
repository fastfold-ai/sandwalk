import { describe, expect, it } from 'vitest'

/**
 * Index math for global back/forward (mirrors useGlobalHistoryNav).
 * Hook wiring is covered via UI; this pins the stack rules.
 */
function nextBounds(
  currentIdx: number,
  maxIdx: number,
  navType: 'POP' | 'PUSH' | 'REPLACE'
) {
  if (navType === 'POP') {
    return { idx: currentIdx, maxIdx }
  }
  return { idx: currentIdx, maxIdx: currentIdx }
}

describe('global history bounds', () => {
  it('keeps forward after back (POP)', () => {
    let max = 2
    let idx = 2
    idx = 1
    ;({ idx, maxIdx: max } = nextBounds(idx, max, 'POP'))
    expect(idx).toBe(1)
    expect(max).toBe(2)
    expect(idx < max).toBe(true)
  })

  it('truncates forward on PUSH', () => {
    let max = 2
    let idx = 0
    idx = 1
    ;({ idx, maxIdx: max } = nextBounds(idx, max, 'PUSH'))
    expect(idx).toBe(1)
    expect(max).toBe(1)
    expect(idx < max).toBe(false)
  })
})
