import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useLatestRef } from './useLatestRef'

describe('useLatestRef', () => {
  it('keeps a stable ref object whose .current tracks the latest value', () => {
    const first = [{ id: 'a' }]
    const second = [{ id: 'a' }, { id: 'b' }]
    const { result, rerender } = renderHook(
      ({ value }: { value: unknown[] }) => useLatestRef(value),
      { initialProps: { value: first } }
    )
    const ref = result.current
    expect(ref.current).toBe(first)

    rerender({ value: second })
    expect(result.current).toBe(ref)
    expect(ref.current).toBe(second)
  })
})
