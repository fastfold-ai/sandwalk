import type { WorkspaceFile } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { createChipInserters } from '@/components/agents/composer/composer-chip-insert'
import { useComposerCaret } from '@/components/agents/composer/useComposerCaret'
import {
  computeAtFileQuery,
  computeSlashSkillQuery
} from '@/components/agents/skill-examples'

export function useComposerDraftState({
  value,
  onChange,
  onLiveDraftChange,
  autoFocus,
  focusKey,
  workspaceFiles = [],
  onEnsureWorkspaceFiles
}: {
  value: string
  onChange: (value: string) => void
  onLiveDraftChange?: (value: string) => void
  autoFocus?: boolean
  focusKey?: string | null
  workspaceFiles?: WorkspaceFile[]
  onEnsureWorkspaceFiles?: () => void | Promise<void>
}) {
  const textInputRefs = useRef<
    Map<number, HTMLInputElement | HTMLTextAreaElement>
  >(new Map())
  const [caretPos, setCaretPos] = useState(0)
  const [focusedPartIndex, setFocusedPartIndex] = useState(0)
  const [draft, setDraft] = useState(value)
  const draftRef = useRef(value)
  const emittedDraftRef = useRef(value)
  const [slashDismissed, setSlashDismissed] = useState(false)
  const [atDismissed, setAtDismissed] = useState(false)

  draftRef.current = draft

  useEffect(() => {
    if (value === emittedDraftRef.current) return
    if (value === draftRef.current) {
      emittedDraftRef.current = value
      return
    }
    if (value === '') {
      emittedDraftRef.current = ''
      draftRef.current = ''
      setDraft('')
      onLiveDraftChange?.('')
      return
    }
    if (
      emittedDraftRef.current === draftRef.current &&
      draftRef.current.length > value.length
    ) {
      return
    }
    emittedDraftRef.current = value
    draftRef.current = value
    setDraft(value)
    onLiveDraftChange?.(value)
  }, [onLiveDraftChange, value])

  const setLocalDraft = useCallback(
    (nextValue: string) => {
      draftRef.current = nextValue
      setDraft(nextValue)
      onLiveDraftChange?.(nextValue)
    },
    [onLiveDraftChange]
  )

  const {
    pendingCaretRef,
    autoFocusedKeyRef,
    applyComposerCaret,
    focusActiveComposerInput
  } = useComposerCaret({
    draft,
    draftRef,
    autoFocus,
    focusKey,
    focusedPartIndex,
    setFocusedPartIndex,
    setCaretPos,
    textInputRefs
  })

  const commitDraft = useCallback(
    (nextValue: string) => {
      emittedDraftRef.current = nextValue
      setLocalDraft(nextValue)
      onChange(nextValue)
    },
    [onChange, setLocalDraft]
  )

  const slash = useMemo(
    () => computeSlashSkillQuery(draft, caretPos),
    [caretPos, draft]
  )
  const atMention = useMemo(
    () => computeAtFileQuery(draft, caretPos),
    [caretPos, draft]
  )
  const activeMention =
    slash && atMention
      ? slash.start >= atMention.start
        ? ('slash' as const)
        : ('at' as const)
      : slash
        ? ('slash' as const)
        : atMention
          ? ('at' as const)
          : null
  const slashOpen =
    activeMention === 'slash' && Boolean(slash) && !slashDismissed
  const atOpen = activeMention === 'at' && Boolean(atMention) && !atDismissed

  useEffect(() => {
    setSlashDismissed(false)
  }, [slash?.start])

  useEffect(() => {
    setAtDismissed(false)
  }, [atMention?.start])

  // Load @ file index when the menu opens — do not wait for the Files panel.
  const ensuredAtStartRef = useRef<number | null>(null)
  useEffect(() => {
    if (!atOpen || !atMention) return
    if (ensuredAtStartRef.current === atMention.start) return
    ensuredAtStartRef.current = atMention.start
    void onEnsureWorkspaceFiles?.()
  }, [atMention, atOpen, onEnsureWorkspaceFiles])

  const chipInserters = useMemo(
    () =>
      createChipInserters({
        draft,
        slash,
        atMention,
        setLocalDraft,
        commitDraft,
        emittedDraftRef,
        pendingCaretRef,
        applyComposerCaret
      }),
    [
      applyComposerCaret,
      atMention,
      commitDraft,
      draft,
      pendingCaretRef,
      setLocalDraft,
      slash
    ]
  )

  const atResults = useMemo(() => {
    if (!atMention) return []
    const query = atMention.query.toLowerCase()
    return workspaceFiles
      .filter(file => {
        if (!query) return true
        return (
          file.name.toLowerCase().includes(query) ||
          file.path.toLowerCase().includes(query)
        )
      })
      .sort((a, b) => {
        if (a.type !== b.type) {
          return a.type === 'directory' ? -1 : 1
        }
        return a.path.localeCompare(b.path)
      })
      .slice(0, 40)
  }, [atMention, workspaceFiles])

  const clearDraftAfterSend = useCallback(() => {
    emittedDraftRef.current = ''
    setLocalDraft('')
  }, [setLocalDraft])

  return {
    textInputRefs,
    draft,
    draftRef,
    focusedPartIndex,
    setFocusedPartIndex,
    setCaretPos,
    setLocalDraft,
    commitDraft,
    clearDraftAfterSend,
    slash,
    slashOpen,
    atOpen,
    setSlashDismissed,
    setAtDismissed,
    pendingCaretRef,
    autoFocusedKeyRef,
    focusActiveComposerInput,
    chipInserters,
    atResults
  }
}

export function useComposerMentionFocus(
  slashOpen: boolean,
  atOpen: boolean,
  focusActiveComposerInput: () => void
) {
  const mentionMenuWasOpenRef = useRef(false)
  useEffect(() => {
    const open = slashOpen || atOpen
    if (open && !mentionMenuWasOpenRef.current) {
      const frame = window.requestAnimationFrame(() => {
        focusActiveComposerInput()
      })
      mentionMenuWasOpenRef.current = true
      return () => window.cancelAnimationFrame(frame)
    }
    if (!open) mentionMenuWasOpenRef.current = false
  }, [atOpen, focusActiveComposerInput, slashOpen])
}
