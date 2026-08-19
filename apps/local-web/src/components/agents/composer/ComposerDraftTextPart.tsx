import type { KeyboardEvent, MutableRefObject } from 'react'

import {
  absoluteCaretForPart,
  lastTextPartIndex,
  tokenBoundsForTextPart
} from '@/components/agents/composer/composer-draft-editor-handlers'
import { type ComposerPart } from '@/components/agents/composer-parts'
import { cn } from '@/lib/utils'

export function ComposerDraftTextPart({
  part,
  partIndex,
  composerParts,
  hasInlineChips,
  running,
  autoFocus,
  focusKey,
  textInputRefs,
  pendingCaretRef,
  autoFocusedKeyRef,
  draftRef,
  setFocusedPartIndex,
  setCaretPos,
  updateTextPart,
  handleKeyDown,
  placeholder
}: {
  part: Extract<ComposerPart, { type: 'text' }>
  partIndex: number
  composerParts: ComposerPart[]
  hasInlineChips: boolean
  running: boolean
  autoFocus?: boolean
  focusKey?: string | null
  textInputRefs: MutableRefObject<
    Map<number, HTMLInputElement | HTMLTextAreaElement>
  >
  pendingCaretRef: MutableRefObject<number | null>
  autoFocusedKeyRef: MutableRefObject<string | null>
  draftRef: MutableRefObject<string>
  setFocusedPartIndex: (index: number) => void
  setCaretPos: (pos: number) => void
  updateTextPart: (partIndex: number, text: string, localCaret: number) => void
  handleKeyDown: (
    event: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => void
  placeholder?: string
}) {
  const isLastText = partIndex === lastTextPartIndex(composerParts)
  if (!isLastText && part.text.length === 0) {
    return null
  }

  const syncCaret = (localCaret: number) => {
    setCaretPos(absoluteCaretForPart(composerParts, partIndex, localCaret))
  }

  const showPlaceholder =
    isLastText && !part.text && !hasInlineChips
      ? running
        ? 'Add a follow-up'
        : placeholder || 'Ask Agent, @ for context, / for skills & MCPs'
      : undefined

  const emptyLastText = isLastText && !part.text

  // With chips, keep trailing caret thin; without chips, leave room for placeholder.
  const growForPlaceholder = emptyLastText && !hasInlineChips

  return (
    <span
      className={cn(
        // Shrink-wrap to the mirror text. Avoid w-full — it fights chip layout.
        'relative inline-grid max-w-full align-middle',
        emptyLastText && hasInlineChips && 'min-w-[0.35rem]',
        growForPlaceholder && 'w-[min(100%,24rem)] min-w-[12rem]'
      )}
    >
      <span
        className="invisible col-start-1 row-start-1 whitespace-pre-wrap break-words text-[15px] leading-7"
        aria-hidden
      >
        {part.text.length > 0
          ? part.text
          : growForPlaceholder
            ? '\u00a0'
            : // Zero-width space: keep a caret target without inventing a wide gap.
              '\u200b'}
      </span>
      <textarea
        ref={node => {
          if (!node) {
            textInputRefs.current.delete(partIndex)
            return
          }
          textInputRefs.current.set(partIndex, node)
          const pending = pendingCaretRef.current
          const { tokenStart, tokenEnd } = tokenBoundsForTextPart(
            composerParts,
            partIndex
          )
          const lastText = partIndex === lastTextPartIndex(composerParts)
          const key = focusKey ?? ''
          const shouldAutoFocus =
            autoFocus && lastText && autoFocusedKeyRef.current !== key
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
        // Default HTML cols=20 makes every segment ~20ch wide around chips.
        cols={1}
        rows={1}
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
        placeholder={emptyLastText ? showPlaceholder || undefined : undefined}
        className={cn(
          'placeholder:text-muted-foreground/50 col-start-1 row-start-1 m-0 min-h-0 min-w-0 resize-none overflow-hidden border-0 bg-transparent p-0 text-[15px] leading-7 outline-none',
          // Match mirror width; only stretch when showing the empty placeholder.
          growForPlaceholder ? 'w-full' : 'w-full max-w-full'
        )}
      />
    </span>
  )
}
