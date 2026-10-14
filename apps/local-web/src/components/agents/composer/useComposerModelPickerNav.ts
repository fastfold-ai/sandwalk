import { type KeyboardEvent, useEffect, useMemo, useState } from 'react'

import {
  type ComposerModelOption,
  composerModelPrefKey,
  type RankedComposerModelSection
} from '@/lib/composer-models'

export function composerModelOptionKey(option: ComposerModelOption): string {
  return `${option.provider || option.source || 'cloud'}:${option.profileId || 'cloud'}:${option.model}`
}

export function useComposerModelPickerNav({
  open,
  search,
  sections,
  selected,
  effortMenuOpen
}: {
  open: boolean
  search: string
  sections: RankedComposerModelSection[]
  selected: ComposerModelOption
  effortMenuOpen: boolean
}) {
  const flatOptions = useMemo(
    () => sections.flatMap(section => section.options),
    [sections]
  )

  const [activeKey, setActiveKey] = useState<string | null>(null)

  const selectedKey = composerModelOptionKey(selected)

  useEffect(() => {
    if (!open) {
      setActiveKey(null)
      return
    }
    // Reset highlight when the open/search result set changes — not on every
    // parent re-render of ``selected`` (that would eat ArrowDown moves).
    // Do not scroll to the selected model on open — that fights the user
    // while they browse/search (especially on Bench).
    const match = flatOptions.some(
      option => composerModelOptionKey(option) === selectedKey
    )
    setActiveKey(
      match
        ? selectedKey
        : flatOptions[0]
          ? composerModelOptionKey(flatOptions[0])
          : null
    )
  }, [flatOptions, open, search, selectedKey])

  const scrollActiveIntoView = (key: string) => {
    const node = Array.from(
      document.querySelectorAll('[data-composer-model-option]')
    ).find(el => el.getAttribute('data-composer-model-option') === key)
    node?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }

  const activeOption =
    flatOptions.find(option => composerModelOptionKey(option) === activeKey) ||
    null

  const onSearchKeyDown = (
    event: KeyboardEvent<HTMLInputElement>,
    selectOption: (option: ComposerModelOption) => void
  ) => {
    if (effortMenuOpen) return
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      event.stopPropagation()
      if (flatOptions.length === 0) return
      const currentIndex = flatOptions.findIndex(
        option => composerModelOptionKey(option) === activeKey
      )
      const safeIndex = currentIndex < 0 ? 0 : currentIndex
      const nextIndex =
        event.key === 'ArrowDown'
          ? Math.min(safeIndex + 1, flatOptions.length - 1)
          : Math.max(safeIndex - 1, 0)
      const next = flatOptions[nextIndex]
      if (next) {
        const key = composerModelOptionKey(next)
        setActiveKey(key)
        // Keep keyboard highlight visible without snapping on open.
        requestAnimationFrame(() => scrollActiveIntoView(key))
      }
      return
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      event.stopPropagation()
      if (activeOption) selectOption(activeOption)
      return
    }
    if (event.key === 'Home' || event.key === 'End') {
      if (flatOptions.length === 0) return
      event.preventDefault()
      const next =
        event.key === 'Home'
          ? flatOptions[0]
          : flatOptions[flatOptions.length - 1]
      if (next) {
        const key = composerModelOptionKey(next)
        setActiveKey(key)
        requestAnimationFrame(() => scrollActiveIntoView(key))
      }
    }
  }

  return {
    flatOptions,
    activeKey,
    setActiveKey,
    activeOption,
    onSearchKeyDown,
    prefKey: composerModelPrefKey
  }
}
