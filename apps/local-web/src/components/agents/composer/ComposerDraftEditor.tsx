import {
  type KeyboardEvent,
  type MutableRefObject,
  useMemo
} from 'react'

import {
  ComposerFileChip,
  ComposerMcpChip,
  ComposerSkillChip
} from '@/components/agents/composer/ComposerChip'
import type { ComposerAtMenuHandle } from '@/components/agents/composer/ComposerAtMenu'
import type { ComposerSlashMenuHandle } from '@/components/agents/composer/ComposerSlashMenu'
import {
  chipTokenLength,
  type ComposerPart,
  parseComposerParts,
  removeComposerChipAt,
  serializeComposerParts
} from '@/components/agents/composer-parts'
import { cn } from '@/lib/utils'

export function ComposerDraftEditor({
  draft,
  running,
  autoFocus,
  focusKey,
  composerParts,
  textInputRefs,
  pendingCaretRef,
  autoFocusedKeyRef,
  draftRef,
  focusedPartIndex,
  setFocusedPartIndex,
  setCaretPos,
  setLocalDraft,
  commitDraft,
  onSkillChipsChange,
  onFileChipsChange,
  onOpenFile,
  onSend,
  atOpen,
  slashOpen,
  atMenuRef,
  slashMenuRef
}: {
  draft: string
  running: boolean
  autoFocus?: boolean
  focusKey?: string | null
  composerParts: ComposerPart[]
  textInputRefs: MutableRefObject<Map<number, HTMLInputElement>>
  pendingCaretRef: MutableRefObject<number | null>
  autoFocusedKeyRef: MutableRefObject<string | null>
  draftRef: MutableRefObject<string>
  focusedPartIndex: number
  setFocusedPartIndex: (index: number) => void
  setCaretPos: (pos: number) => void
  setLocalDraft: (value: string) => void
  commitDraft: (value: string) => void
  onSkillChipsChange: (skills: string[]) => void
  onFileChipsChange?: (files: string[]) => void
  onOpenFile?: (path: string) => void
  onSend: () => void
  atOpen: boolean
  slashOpen: boolean
  atMenuRef: MutableRefObject<ComposerAtMenuHandle | null>
  slashMenuRef: MutableRefObject<ComposerSlashMenuHandle | null>
}) {
  const hasInlineChips = useMemo(
    () => composerParts.some(part => part.type !== 'text'),
    [composerParts]
  )

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
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onSend()
    }
  }

  let chipRenderIndex = -1

  return (
    <div
      className="min-h-12 max-h-32 overflow-y-auto px-2 py-1 text-[15px] leading-7"
      onClick={event => {
        if (event.target !== event.currentTarget) return
        const lastTextIndex = [...composerParts]
          .map((part, index) => (part.type === 'text' ? index : -1))
          .filter(index => index >= 0)
          .at(-1)
        if (lastTextIndex == null) return
        const node = textInputRefs.current.get(lastTextIndex)
        node?.focus()
        const len = node?.value.length ?? 0
        node?.setSelectionRange(len, len)
      }}
    >
      {composerParts.map((part, partIndex) => {
        if (part.type === 'file') {
          chipRenderIndex += 1
          const chipIndex = chipRenderIndex
          return (
            <ComposerFileChip
              key={`file-${partIndex}-${part.path}`}
              path={part.path}
              onOpenFile={onOpenFile}
              onRemove={() => {
                commitDraft(removeComposerChipAt(draft, chipIndex))
                onFileChipsChange?.([])
              }}
            />
          )
        }
        if (part.type === 'skill') {
          chipRenderIndex += 1
          const chipIndex = chipRenderIndex
          return (
            <ComposerSkillChip
              key={`skill-${partIndex}-${part.name}`}
              name={part.name}
              onRemove={() => {
                commitDraft(removeComposerChipAt(draft, chipIndex))
                onSkillChipsChange([])
              }}
            />
          )
        }
        if (part.type === 'mcp') {
          chipRenderIndex += 1
          const chipIndex = chipRenderIndex
          return (
            <ComposerMcpChip
              key={`mcp-${partIndex}-${part.id}`}
              id={part.id}
              name={part.name}
              onRemove={() => {
                commitDraft(removeComposerChipAt(draft, chipIndex))
              }}
            />
          )
        }

        const isLastText =
          partIndex ===
          composerParts.reduce(
            (last, item, index) => (item.type === 'text' ? index : last),
            0
          )
        if (!isLastText && part.text.length === 0) {
          return null
        }

        const syncCaret = (localCaret: number) => {
          let absolute = 0
          for (let index = 0; index < partIndex; index += 1) {
            const item = composerParts[index]
            if (item.type === 'text') absolute += item.text.length
            else absolute += chipTokenLength(item)
          }
          setCaretPos(absolute + localCaret)
        }

        const showPlaceholder =
          isLastText && !part.text && !hasInlineChips
            ? running
              ? 'Add a follow-up'
              : 'Ask Agent, @ for context, / for skills & MCPs'
            : undefined

        const emptyLastText = isLastText && !part.text
        return (
          <span
            key={`text-${partIndex}`}
            className={cn(
              'relative inline-grid max-w-full align-middle',
              emptyLastText &&
                (hasInlineChips
                  ? 'min-w-[0.5rem]'
                  : 'w-[min(100%,24rem)] min-w-[12rem]')
            )}
          >
            <span
              className="invisible col-start-1 row-start-1 whitespace-pre text-[15px] leading-7"
              aria-hidden
            >
              {part.text.length > 0 ? part.text : '\u00a0'}
            </span>
            <input
              ref={node => {
                if (!node) {
                  textInputRefs.current.delete(partIndex)
                  return
                }
                textInputRefs.current.set(partIndex, node)
                const pending = pendingCaretRef.current
                let absolute = 0
                for (let index = 0; index < partIndex; index += 1) {
                  const item = composerParts[index]
                  if (item.type === 'text') absolute += item.text.length
                  else absolute += chipTokenLength(item)
                }
                const tokenStart = absolute
                const tokenEnd = absolute + part.text.length
                const lastText =
                  partIndex ===
                  composerParts.reduce(
                    (last, item, index) =>
                      item.type === 'text' ? index : last,
                    0
                  )
                const key = focusKey ?? ''
                const shouldAutoFocus =
                  autoFocus &&
                  lastText &&
                  autoFocusedKeyRef.current !== key
                const shouldPendingFocus =
                  pending != null &&
                  ((pending >= tokenStart && pending <= tokenEnd) ||
                    (lastText && pending >= tokenStart))
                if (!shouldAutoFocus && !shouldPendingFocus) return
                const target =
                  pending != null ? pending : draftRef.current.length
                const local = Math.min(
                  Math.max(0, target - tokenStart),
                  node.value.length
                )
                node.focus({ preventScroll: true })
                try {
                  node.setSelectionRange(local, local)
                } catch {
                  // Ignore selection errors on detached nodes.
                }
                if (document.activeElement !== node) return
                pendingCaretRef.current = null
                autoFocusedKeyRef.current = key
                queueMicrotask(() => {
                  setCaretPos(tokenStart + local)
                  setFocusedPartIndex(partIndex)
                })
              }}
              value={part.text}
              size={1}
              autoFocus={Boolean(autoFocus && isLastText)}
              onChange={event => {
                const localCaret = event.target.selectionStart ?? 0
                updateTextPart(partIndex, event.target.value, localCaret)
              }}
              onFocus={() => setFocusedPartIndex(partIndex)}
              onClick={event => {
                setFocusedPartIndex(partIndex)
                syncCaret(event.currentTarget.selectionStart ?? 0)
              }}
              onKeyUp={event =>
                syncCaret(event.currentTarget.selectionStart ?? 0)
              }
              onSelect={event =>
                syncCaret(event.currentTarget.selectionStart ?? 0)
              }
              onKeyDown={handleKeyDown}
              placeholder={
                emptyLastText ? showPlaceholder || undefined : undefined
              }
              className="placeholder:text-muted-foreground/70 col-start-1 row-start-1 m-0 w-full min-w-0 border-0 bg-transparent p-0 text-[15px] leading-7 outline-none"
            />
          </span>
        )
      })}
    </div>
  )
}
