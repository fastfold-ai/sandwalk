import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useStableHandlers } from './useStableHandlers'

describe('useStableHandlers', () => {
  it('keeps handler identity across renders and calls the latest one', () => {
    const first = vi.fn(() => 'first')
    const second = vi.fn(() => 'second')
    const { result, rerender } = renderHook(
      ({ onGo, label }: { onGo: () => string; label: string }) =>
        useStableHandlers({ onGo, label }),
      { initialProps: { onGo: first, label: 'a' } }
    )
    const initial = result.current
    expect(initial.label).toBe('a')
    expect(initial.onGo()).toBe('first')

    rerender({ onGo: second, label: 'b' })
    expect(result.current.onGo).toBe(initial.onGo)
    expect(result.current.onGo()).toBe('second')
    expect(result.current.label).toBe('b')
    expect(first).toHaveBeenCalledTimes(1)
    expect(second).toHaveBeenCalledTimes(1)
  })

  it('passes data fields through by identity and forwards arguments', () => {
    const session = { id: 's1' }
    const onPick = vi.fn((id: string, n: number) => `${id}:${n}`)
    const { result } = renderHook(() => useStableHandlers({ session, onPick }))
    expect(result.current.session).toBe(session)
    expect(result.current.onPick('x', 2)).toBe('x:2')
    expect(onPick).toHaveBeenCalledWith('x', 2)
  })

  it('reflects a handler becoming undefined (presence checks still work)', () => {
    const { result, rerender } = renderHook(
      ({ onDelete }: { onDelete?: () => void }) => useStableHandlers({ onDelete }),
      { initialProps: { onDelete: () => undefined } }
    )
    expect(typeof result.current.onDelete).toBe('function')
    rerender({ onDelete: undefined })
    expect(result.current.onDelete).toBeUndefined()
  })
})
