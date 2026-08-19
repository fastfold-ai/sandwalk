import type { KeyboardEvent, MutableRefObject } from 'react'

import type { ComposerAtMenuHandle } from '@/components/agents/composer/ComposerAtMenu'
import type { ComposerHashMenuHandle } from '@/components/agents/composer/ComposerHashMenu'
import type { ComposerSlashMenuHandle } from '@/components/agents/composer/ComposerSlashMenu'
import {
  chipTokenLength,
  type ComposerPart,
  parseComposerParts,
  removeComposerChipAt,
  serializeComposerParts
} from '@/components/agents/composer-parts'

type DraftEditorHandlersInput = {
  draft: string
  focusedPartIndex: number
  atOpen: boolean
  slashOpen: boolean
  hashOpen?: boolean
  textInputRefs: MutableRefObject<
    Map<number, HTMLInputElement | HTMLTextAreaElement>
  >
  atMenuRef: MutableRefObject<ComposerAtMenuHandle | null>
  slashMenuRef: MutableRefObject<ComposerSlashMenuHandle | null>
  hashMenuRef?: MutableRefObject<ComposerHashMenuHandle | null>
  setFocusedPartIndex: (index: number) => void
  setCaretPos: (pos: number) => void
  setLocalDraft: (value: string) => void
  commitDraft: (value: string) => void
  onSkillChipsChange: (skills: string[]) => void
  onFileChipsChange?: (files: string[]) => void
  onSend: () => void
}

export function createDraftEditorHandlers({
  draft,
  focusedPartIndex,
  atOpen,
  slashOpen,
  hashOpen = false,
  textInputRefs,
  atMenuRef,
  slashMenuRef,
  hashMenuRef,
  setFocusedPartIndex,
  setCaretPos,
  setLocalDraft,
  commitDraft,
  onSkillChipsChange,
  onFileChipsChange,
  onSend
}: DraftEditorHandlersInput) {
  const removeChipBeforeFocusedText = (partIndex: number) => {
    const parts = parseComposerParts(draft)
    if (partIndex <= 0) return false
    const prev = parts[partIndex - 1]
    if (!prev || prev.type === 'text') return false
    let chipIndex = -1
    for (let i = 0; i < partIndex; i += 1) {
      if (parts[i].type !== 'text') chipIndex += 1
    }
    const nextValue = removeComposerChipAt(draft, chipIndex)
    commitDraft(nextValue)
    onSkillChipsChange([])
    onFileChipsChange?.([])
    window.requestAnimationFrame(() => {
      const nextParts = parseComposerParts(nextValue)
      let target = partIndex - 2
      while (target >= 0 && nextParts[target]?.type !== 'text') target -= 1
      if (target < 0) {
        target = nextParts.findIndex(part => part.type === 'text')
      }
      if (target < 0) return
      const node = textInputRefs.current.get(target)
      const len = node?.value.length ?? 0
      node?.focus({ preventScroll: true })
      node?.setSelectionRange(len, len)
      setFocusedPartIndex(target)
      setCaretPos(len)
    })
    return true
  }

  const updateTextPart = (
    partIndex: number,
    text: string,
    localCaret: number
  ) => {
    const parts = parseComposerParts(draft).map((part, index) =>
      index === partIndex && part.type === 'text' ? { ...part, text } : part
    )
    const nextValue = serializeComposerParts(parts)
    setLocalDraft(nextValue)
    let absolute = 0
    for (let index = 0; index < parts.length; index += 1) {
      const part = parts[index]
      if (part.type !== 'text') {
        absolute += chipTokenLength(part)
        continue
      }
      if (index === partIndex) {
        setCaretPos(absolute + localCaret)
        return
      }
      absolute += part.text.length
    }
  }

  const handleKeyDown = (
    event: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const input = event.currentTarget
    const localCaret = input.selectionStart ?? 0

    if (event.key === 'Backspace') {
      const parts = parseComposerParts(draft)
      const textPart = parts[focusedPartIndex]
      if (textPart?.type === 'text') {
        const textBeforeCaret = textPart.text.slice(0, localCaret)
        const textAfterCaret = textPart.text.slice(localCaret)
        const atStartOfText = localCaret === 0
        const onlyWhitespaceSegment = /^\s*$/.test(textPart.text)
        const deletingTrailingWhitespace =
          onlyWhitespaceSegment ||
          (/^\s+$/.test(textBeforeCaret) && textAfterCaret === '')
        if (
          (atStartOfText || deletingTrailingWhitespace) &&
          removeChipBeforeFocusedText(focusedPartIndex)
        ) {
          event.preventDefault()
          return
        }
      }
    }

    if (atOpen && atMenuRef.current?.handleKeyDown(event)) return
    if (slashOpen && slashMenuRef.current?.handleKeyDown(event)) return
    if (hashOpen && hashMenuRef?.current?.handleKeyDown(event)) return
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onSend()
    }
  }

  return { updateTextPart, handleKeyDown }
}

export function lastTextPartIndex(parts: ComposerPart[]) {
  return parts.reduce(
    (last, item, index) => (item.type === 'text' ? index : last),
    0
  )
}

export function absoluteCaretForPart(
  parts: ComposerPart[],
  partIndex: number,
  localCaret: number
) {
  let absolute = 0
  for (let index = 0; index < partIndex; index += 1) {
    const item = parts[index]
    if (item.type === 'text') absolute += item.text.length
    else absolute += chipTokenLength(item)
  }
  return absolute + localCaret
}

export function tokenBoundsForTextPart(parts: ComposerPart[], partIndex: number) {
  let absolute = 0
  for (let index = 0; index < partIndex; index += 1) {
    const item = parts[index]
    if (item.type === 'text') absolute += item.text.length
    else absolute += chipTokenLength(item)
  }
  const part = parts[partIndex]
  const textLen = part?.type === 'text' ? part.text.length : 0
  return { tokenStart: absolute, tokenEnd: absolute + textLen }
}
