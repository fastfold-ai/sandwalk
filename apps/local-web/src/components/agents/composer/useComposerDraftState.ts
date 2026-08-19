import type { AgentSession, WorkspaceFile } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { createChipInserters } from '@/components/agents/composer/composer-chip-insert'
import { useComposerCaret } from '@/components/agents/composer/useComposerCaret'
import {
  computeAtFileQuery,
  computeHashChatQuery,
  computeSlashSkillQuery
} from '@/components/agents/skill-examples'

export function useComposerDraftState({
  value,
  onChange,
  onLiveDraftChange,
  autoFocus,
  focusKey,
  workspaceFiles = [],
  mentionChats,
  onEnsureWorkspaceFiles
}: {
  value: string
  onChange: (value: string) => void
  onLiveDraftChange?: (value: string) => void
  autoFocus?: boolean
  focusKey?: string | null
  workspaceFiles?: WorkspaceFile[]
  mentionChats?: AgentSession[]
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
  const [hashDismissed, setHashDismissed] = useState(false)

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
  const hashMention = useMemo(
    () => (mentionChats ? computeHashChatQuery(draft, caretPos) : null),
    [caretPos, draft, mentionChats]
  )
  const activeMention = useMemo(() => {
    const candidates: Array<{ kind: 'slash' | 'at' | 'hash'; start: number }> =
      []
    if (slash) candidates.push({ kind: 'slash', start: slash.start })
    if (atMention) candidates.push({ kind: 'at', start: atMention.start })
    if (hashMention) candidates.push({ kind: 'hash', start: hashMention.start })
    if (candidates.length === 0) return null
    return candidates.sort((a, b) => b.start - a.start)[0]?.kind ?? null
  }, [atMention, hashMention, slash])
  const slashOpen =
    activeMention === 'slash' && Boolean(slash) && !slashDismissed
  const atOpen = activeMention === 'at' && Boolean(atMention) && !atDismissed
  const hashOpen =
    activeMention === 'hash' && Boolean(hashMention) && !hashDismissed

  useEffect(() => {
    setSlashDismissed(false)
  }, [slash?.start])

  useEffect(() => {
    setAtDismissed(false)
  }, [atMention?.start])

  useEffect(() => {
    setHashDismissed(false)
  }, [hashMention?.start])

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
        hashMention,
        commitDraft,
        pendingCaretRef,
        applyComposerCaret
      }),
    [
      applyComposerCaret,
      atMention,
      commitDraft,
      draft,
      hashMention,
      pendingCaretRef,
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

  const hashResults = useMemo(() => {
    if (!hashMention || !mentionChats) return []
    const query = hashMention.query.toLowerCase()
    return mentionChats
      .filter(chat => chat.source !== 'capy' && chat.source !== 'bench')
      .filter(chat => {
        if (!query) return true
        const title = chat.title.toLowerCase()
        return title.includes(query) || chat.id.toLowerCase().includes(query)
      })
      .sort((a, b) => {
        if (!query) {
          return (b.updatedAt || '').localeCompare(a.updatedAt || '')
        }
        const aTitle = a.title.toLowerCase()
        const bTitle = b.title.toLowerCase()
        const aPrefix = aTitle.startsWith(query) ? 0 : 1
        const bPrefix = bTitle.startsWith(query) ? 0 : 1
        if (aPrefix !== bPrefix) return aPrefix - bPrefix
        return aTitle.localeCompare(bTitle)
      })
      .slice(0, 40)
  }, [hashMention, mentionChats])

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
    hashOpen,
    setSlashDismissed,
    setAtDismissed,
    setHashDismissed,
    pendingCaretRef,
    autoFocusedKeyRef,
    focusActiveComposerInput,
    chipInserters,
    atResults,
    hashResults
  }
}

export function useComposerMentionFocus(
  slashOpen: boolean,
  atOpen: boolean,
  focusActiveComposerInput: () => void,
  hashOpen = false
) {
  const mentionMenuWasOpenRef = useRef(false)
  useEffect(() => {
    const open = slashOpen || atOpen || hashOpen
    if (open && !mentionMenuWasOpenRef.current) {
      const frame = window.requestAnimationFrame(() => {
        focusActiveComposerInput()
      })
      mentionMenuWasOpenRef.current = true
      return () => window.cancelAnimationFrame(frame)
    }
    if (!open) mentionMenuWasOpenRef.current = false
  }, [atOpen, focusActiveComposerInput, hashOpen, slashOpen])
}
