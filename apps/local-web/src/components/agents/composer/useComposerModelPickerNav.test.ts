import { act, renderHook } from '@testing-library/react'
import { type KeyboardEvent } from 'react'
import { describe, expect, it } from 'vitest'

import type { ComposerModelOption } from '@/lib/composer-models'

import {
  composerModelOptionKey,
  useComposerModelPickerNav
} from './useComposerModelPickerNav'

function opt(
  provider: string,
  model: string,
  label = model
): ComposerModelOption {
  return { provider, model, label, speed: provider, contextWindow: null }
}

function keyEvent(
  key: string,
  extras: Partial<KeyboardEvent<HTMLInputElement>> = {}
) {
  return {
    key,
    shiftKey: false,
    preventDefault: () => undefined,
    stopPropagation: () => undefined,
    ...extras
  } as KeyboardEvent<HTMLInputElement>
}

describe('useComposerModelPickerNav', () => {
  it('moves highlight with ArrowDown / ArrowUp and selects on Enter', () => {
    const a = opt('openrouter', 'qwen/qwen3.7-flash', 'Flash')
    const b = opt('openrouter', 'qwen/qwen3.7-max', 'Max')
    const sections = [{ title: '', options: [a, b] }]
    const picks: ComposerModelOption[] = []

    const { result } = renderHook(() =>
      useComposerModelPickerNav({
        open: true,
        search: '',
        sections,
        selected: a,
        effortMenuOpen: false
      })
    )

    expect(result.current.activeKey).toBe(composerModelOptionKey(a))

    act(() => {
      result.current.onSearchKeyDown(keyEvent('ArrowDown'), option =>
        picks.push(option)
      )
    })
    expect(result.current.activeKey).toBe(composerModelOptionKey(b))

    act(() => {
      result.current.onSearchKeyDown(keyEvent('Enter'), option =>
        picks.push(option)
      )
    })
    expect(picks).toEqual([b])
  })
})
