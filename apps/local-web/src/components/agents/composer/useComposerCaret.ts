import {
  type MutableRefObject,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef
} from 'react'

import {
  chipTokenLength,
  parseComposerParts
} from '@/components/agents/composer-parts'

export function useComposerCaret({
  draft,
  draftRef,
  autoFocus,
  focusKey,
  focusedPartIndex,
  setFocusedPartIndex,
  setCaretPos,
  textInputRefs
}: {
  draft: string
  draftRef: MutableRefObject<string>
  autoFocus?: boolean
  focusKey?: string | null
  focusedPartIndex: number
  setFocusedPartIndex: (index: number) => void
  setCaretPos: (pos: number) => void
  textInputRefs: MutableRefObject<Map<number, HTMLInputElement>>
}) {
  const pendingCaretRef = useRef<number | null>(null)
  const autoFocusedKeyRef = useRef<string | null>(null)

  const applyComposerCaret = useCallback(
    (absoluteCaret: number) => {
      const value = draftRef.current
      const parts = parseComposerParts(value)
      let offset = 0
      for (let index = 0; index < parts.length; index += 1) {
        const part = parts[index]
        if (part.type !== 'text') {
          offset += chipTokenLength(part)
          continue
        }
        const tokenStart = offset
        const tokenEnd = offset + part.text.length
        if (absoluteCaret >= tokenStart && absoluteCaret <= tokenEnd) {
          const input = textInputRefs.current.get(index)
          if (!input) return false
          const local = Math.min(
            Math.max(0, absoluteCaret - tokenStart),
            input.value.length
          )
          input.focus({ preventScroll: true })
          try {
            input.setSelectionRange(local, local)
          } catch {
            // Ignore selection errors on detached nodes.
          }
          if (document.activeElement !== input) return false
          setCaretPos(tokenStart + local)
          setFocusedPartIndex(index)
          return true
        }
        offset = tokenEnd
      }
      const lastTextIndex = [...parts]
        .map((part, index) => (part.type === 'text' ? index : -1))
        .filter(index => index >= 0)
        .at(-1)
      if (lastTextIndex == null) return false
      const last = textInputRefs.current.get(lastTextIndex)
      if (!last) return false
      const len = last.value.length
      last.focus({ preventScroll: true })
      try {
        last.setSelectionRange(len, len)
      } catch {
        // Ignore selection errors on detached nodes.
      }
      if (document.activeElement !== last) return false
      setCaretPos(value.length)
      setFocusedPartIndex(lastTextIndex)
      return true
    },
    [draftRef, setCaretPos, setFocusedPartIndex, textInputRefs]
  )

  const focusActiveComposerInput = useCallback(() => {
    const preferred =
      textInputRefs.current.get(focusedPartIndex) ||
      [...textInputRefs.current.values()].at(-1)
    if (!preferred) return
    if (document.activeElement === preferred) return
    preferred.focus({ preventScroll: true })
  }, [focusedPartIndex, textInputRefs])

  const isComposerInput = useCallback(
    (node: Element | null) => {
      if (!(node instanceof HTMLInputElement)) return false
      return [...textInputRefs.current.values()].includes(node)
    },
    [textInputRefs]
  )

  useEffect(() => {
    if (!autoFocus) return
    const key = focusKey ?? ''
    autoFocusedKeyRef.current = null
    pendingCaretRef.current = draftRef.current.length
    let cancelled = false

    const tryFocus = () => {
      if (cancelled) return true
      if (isComposerInput(document.activeElement)) {
        autoFocusedKeyRef.current = key
        pendingCaretRef.current = null
        return true
      }
      if (!applyComposerCaret(draftRef.current.length)) return false
      if (!isComposerInput(document.activeElement)) return false
      autoFocusedKeyRef.current = key
      pendingCaretRef.current = null
      return true
    }

    tryFocus()

    let frames = 0
    let frame = 0
    const tick = () => {
      if (cancelled || tryFocus()) return
      frames += 1
      if (frames < 60) frame = window.requestAnimationFrame(tick)
    }
    frame = window.requestAnimationFrame(tick)

    const timers = [0, 16, 50, 100, 200, 400, 800, 1600].map(ms =>
      window.setTimeout(() => {
        tryFocus()
      }, ms)
    )

    const onFocusIn = (event: FocusEvent) => {
      if (cancelled || autoFocusedKeyRef.current === key) return
      const target = event.target
      if (
        target instanceof Element &&
        target.closest('[data-radix-scroll-area-viewport]')
      ) {
        tryFocus()
      }
    }
    document.addEventListener('focusin', onFocusIn)

    return () => {
      cancelled = true
      window.cancelAnimationFrame(frame)
      for (const timer of timers) window.clearTimeout(timer)
      document.removeEventListener('focusin', onFocusIn)
    }
  }, [applyComposerCaret, autoFocus, draftRef, focusKey, isComposerInput])

  useLayoutEffect(() => {
    const caret = pendingCaretRef.current
    if (caret == null) return
    if (applyComposerCaret(caret)) {
      pendingCaretRef.current = null
      return
    }
    let attempts = 0
    let frame = 0
    const retry = () => {
      if (pendingCaretRef.current == null) return
      if (applyComposerCaret(pendingCaretRef.current)) {
        pendingCaretRef.current = null
        return
      }
      attempts += 1
      if (attempts < 16) frame = window.requestAnimationFrame(retry)
    }
    frame = window.requestAnimationFrame(retry)
    return () => window.cancelAnimationFrame(frame)
  }, [applyComposerCaret, draft])

  return {
    pendingCaretRef,
    autoFocusedKeyRef,
    applyComposerCaret,
    focusActiveComposerInput
  }
}
