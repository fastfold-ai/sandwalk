import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useStableCallback } from './useStableCallback'

describe('useStableCallback', () => {
  it('keeps one identity across renders and calls the latest fn', () => {
    const first = vi.fn(() => 'first')
    const second = vi.fn(() => 'second')
    const { result, rerender } = renderHook(({ fn }) => useStableCallback(fn), {
      initialProps: { fn: first as () => string }
    })
    const identity = result.current
    expect(identity()).toBe('first')

    rerender({ fn: second })
    expect(result.current).toBe(identity)
    expect(result.current()).toBe('second')
    expect(first).toHaveBeenCalledTimes(1)
    expect(second).toHaveBeenCalledTimes(1)
  })

  it('forwards arguments', () => {
    const add = vi.fn((a: number, b: number) => a + b)
    const { result } = renderHook(() => useStableCallback(add))
    expect(result.current(2, 3)).toBe(5)
    expect(add).toHaveBeenCalledWith(2, 3)
  })

  it('returns undefined for an undefined handler', () => {
    const { result } = renderHook(() => useStableCallback(undefined))
    expect(result.current).toBeUndefined()
  })
})
