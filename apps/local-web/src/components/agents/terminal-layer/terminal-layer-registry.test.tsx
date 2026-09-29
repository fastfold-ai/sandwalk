import { renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import {
  type PlaceholderEntry,
  TerminalLayerProvider,
  useTerminalLayer
} from './terminal-layer-registry'

function wrapper({ children }: { children: ReactNode }) {
  return <TerminalLayerProvider>{children}</TerminalLayerProvider>
}

function entry(): PlaceholderEntry {
  return { node: document.createElement('div'), onFocus: vi.fn() }
}

describe('TerminalLayerRegistry', () => {
  it('throws outside the provider', () => {
    expect(() => renderHook(() => useTerminalLayer())).toThrow(
      /inside <TerminalLayerProvider>/
    )
  })

  it('registers a placeholder and notifies only that terminal', () => {
    const { result } = renderHook(() => useTerminalLayer(), { wrapper })
    const registry = result.current
    const onA = vi.fn()
    const onB = vi.fn()
    registry.subscribe('term_a', onA)
    registry.subscribe('term_b', onB)

    const a = entry()
    registry.registerPlaceholder('term_a', a)

    expect(registry.getPlaceholder('term_a')).toBe(a)
    expect(registry.getPlaceholder('term_b')).toBeNull()
    expect(onA).toHaveBeenCalledTimes(1)
    expect(onB).not.toHaveBeenCalled()
  })

  it('only unregisters when the entry is still the current one', () => {
    const { result } = renderHook(() => useTerminalLayer(), { wrapper })
    const registry = result.current
    const listener = vi.fn()
    registry.subscribe('term_a', listener)

    const stale = entry()
    const fresh = entry()
    const unregisterStale = registry.registerPlaceholder('term_a', stale)
    registry.registerPlaceholder('term_a', fresh)
    listener.mockClear()

    // React remount race: the old placeholder's cleanup runs after the new
    // one registered. It must not wipe the fresh entry.
    unregisterStale()
    expect(registry.getPlaceholder('term_a')).toBe(fresh)
    expect(listener).not.toHaveBeenCalled()
  })

  it('removes the entry and notifies on a matching unregister', () => {
    const { result } = renderHook(() => useTerminalLayer(), { wrapper })
    const registry = result.current
    const listener = vi.fn()
    registry.subscribe('term_a', listener)
    const unregister = registry.registerPlaceholder('term_a', entry())
    listener.mockClear()

    unregister()
    expect(registry.getPlaceholder('term_a')).toBeNull()
    expect(listener).toHaveBeenCalledTimes(1)
  })

  it('stops notifying after unsubscribe', () => {
    const { result } = renderHook(() => useTerminalLayer(), { wrapper })
    const registry = result.current
    const listener = vi.fn()
    const unsubscribe = registry.subscribe('term_a', listener)
    unsubscribe()
    registry.registerPlaceholder('term_a', entry())
    expect(listener).not.toHaveBeenCalled()
  })

  it('exposes the layer root and re-renders consumers when it changes', () => {
    const { result } = renderHook(() => useTerminalLayer(), { wrapper })
    const root = document.createElement('div')
    expect(result.current.getLayerRoot()).toBeNull()
    result.current.setLayerRoot(root)
    expect(result.current.getLayerRoot()).toBe(root)
    // Same node: no-op.
    result.current.setLayerRoot(root)
    expect(result.current.getLayerRoot()).toBe(root)
  })
})
