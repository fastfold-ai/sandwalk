import { Icon } from '@iconify/react'
import type {
  AgentSkill,
  AgentSkillDetail,
  McpServer,
  RuntimeSettings,
  ServerSystemInfo,
  SessionSandboxStatus,
  Specialist,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import { ArrowUp, Plug, Plus, Sparkles, Square, X } from 'lucide-react'
import { type KeyboardEvent, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { flushSync } from 'react-dom'

import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import {
  chipTokenLength,
  fileChipToken,
  mcpChipToken,
  parseComposerParts,
  removeComposerChipAt,
  serializeComposerParts,
  skillChipToken,
  spaceAroundChips
} from '@/components/agents/composer-parts'
import {
  ComposerAtMenu,
  type ComposerAtMenuHandle
} from '@/components/agents/composer/ComposerAtMenu'
import { ComposerModelPicker } from '@/components/agents/composer/ComposerModelPicker'
import { ComposerSandboxPicker } from '@/components/agents/composer/ComposerSandboxPicker'
import {
  ComposerSlashMenu,
  type ComposerSlashMenuHandle
} from '@/components/agents/composer/ComposerSlashMenu'
import { ComposerSpecialistPicker } from '@/components/agents/composer/ComposerSpecialistPicker'
import { ComposerTokenUsage } from '@/components/agents/composer/ComposerTokenUsage'
import {
  type SandboxActionPhase,
  type SandboxComputeChange
} from '@/components/agents/composer/sandbox-utils'
import {
  computeAtFileQuery,
  computeSlashSkillQuery
} from '@/components/agents/skill-examples'
import { Button } from '@/components/ui/button'
import { type ComposerModelOption } from '@/lib/composer-models'
import { getFileIcon } from '@/lib/file-icons'
import { cn } from '@/lib/utils'

export type { SandboxActionPhase, SandboxComputeChange }

export function Composer({
  value,
  running,
  skills,
  mcpServers = [],
  skillChips: _skillChips,
  fileChips: _fileChips = [],
  workspaceFiles = [],
  modelOptions,
  specialists = [],
  selectedSpecialistId = null,
  sandboxStatus = null,
  sandboxPhase = 'idle',
  showAura = true,
  autoFocus = true,
  focusKey,
  onChange,
  onLiveDraftChange,
  onSkillChipsChange,
  onFileChipsChange,
  onSend,
  onStop,
  onUpload,
  onLoadSkill,
  onOpenFile,
  runtimeSettings,
  tokenUsage,
  onModelSelect,
  onReasoningSettingsChange,
  onSpecialistSelect,
  onCreateSpecialist,
  onManageSpecialists,
  onAddModels,
  onSandboxBackendSelect,
  onSandboxComputeChange,
  onSandboxStart,
  onSandboxStop,
  onSandboxRestart,
  onLoadLocalSystem,
  editingQueued = false,
  onCancelEditQueued
}: {
  value: string
  running: boolean
  skills: AgentSkill[]
  mcpServers?: McpServer[]
  skillChips: string[]
  fileChips?: string[]
  workspaceFiles?: WorkspaceFile[]
  modelOptions: ComposerModelOption[]
  specialists?: Specialist[]
  selectedSpecialistId?: string | null
  sandboxStatus?: SessionSandboxStatus | null
  sandboxPhase?: SandboxActionPhase
  showAura?: boolean
  /** Focus the chat input when mounted / when focusKey changes. */
  autoFocus?: boolean
  /** Re-run autofocus when this changes (e.g. session id). */
  focusKey?: string | null
  onChange: (value: string) => void
  /** Fires on every local keystroke without requiring a parent re-render. */
  onLiveDraftChange?: (value: string) => void
  onSkillChipsChange: (skills: string[]) => void
  onFileChipsChange?: (files: string[]) => void
  onSend: (value: string) => void
  onStop: () => void
  onUpload: (files: FileList) => Promise<void>
  onLoadSkill: (name: string) => Promise<AgentSkillDetail>
  onOpenFile?: (path: string) => void
  runtimeSettings: RuntimeSettings | null
  tokenUsage: { inputTokens: number; outputTokens: number }
  onModelSelect: (
    provider: string,
    model: string,
    profileId?: string | null
  ) => Promise<void>
  onReasoningSettingsChange?: (changes: {
    provider: string
    model: string
    reasoningEffort?: string
    reasoningFast?: boolean
  }) => Promise<void>
  onSpecialistSelect?: (specialistId: string | null) => void | Promise<void>
  onCreateSpecialist?: () => void
  onManageSpecialists?: () => void
  onAddModels?: () => void
  onSandboxBackendSelect?: (
    backend: 'builtin' | 'modal'
  ) => void | Promise<void>
  onSandboxComputeChange?: (
    changes: SandboxComputeChange
  ) => void | Promise<void>
  onSandboxStart?: () => void | Promise<void>
  onSandboxStop?: () => void | Promise<void>
  onSandboxRestart?: () => void | Promise<void>
  onLoadLocalSystem?: () => Promise<ServerSystemInfo | null>
  /** When true, composer is editing a queued follow-up. */
  editingQueued?: boolean
  onCancelEditQueued?: () => void
}) {
  const uploadRef = useRef<HTMLInputElement | null>(null)
  const textInputRefs = useRef<Map<number, HTMLInputElement>>(new Map())
  const [caretPos, setCaretPos] = useState(0)
  const [focusedPartIndex, setFocusedPartIndex] = useState(0)
  // Local draft owns keystrokes. Parent `value` is only for external writes
  // (session switch, workspace @-mention, send clear). Typing must NOT call
  // onChange — App re-renders remount this composer and steal focus.
  const [draft, setDraft] = useState(value)
  const draftRef = useRef(value)
  const emittedDraftRef = useRef(value)
  const [auraTick, setAuraTick] = useState(0)
  const [slashDismissed, setSlashDismissed] = useState(false)
  const [atDismissed, setAtDismissed] = useState(false)
  const atMenuRef = useRef<ComposerAtMenuHandle | null>(null)
  const slashMenuRef = useRef<ComposerSlashMenuHandle | null>(null)

  draftRef.current = draft

  useEffect(() => {
    // Ignore the echo of what we just emitted; accept real external writes.
    if (value === emittedDraftRef.current) return
    if (value === draftRef.current) {
      emittedDraftRef.current = value
      return
    }
    // Parent cleared after send — always accept (do not treat as stale).
    if (value === '') {
      emittedDraftRef.current = ''
      draftRef.current = ''
      setDraft('')
      onLiveDraftChange?.('')
      return
    }
    // Chip inserts stay local so the messages transcript doesn't re-render and
    // steal focus. Ignore a stale parent value that hasn't caught up yet.
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

  const pendingCaretRef = useRef<number | null>(null)

  const applyComposerCaret = useCallback((absoluteCaret: number) => {
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
  }, [])

  const commitDraft = useCallback(
    (nextValue: string) => {
      emittedDraftRef.current = nextValue
      setLocalDraft(nextValue)
      onChange(nextValue)
    },
    [onChange, setLocalDraft]
  )

  const focusActiveComposerInput = useCallback(() => {
    const preferred =
      textInputRefs.current.get(focusedPartIndex) ||
      [...textInputRefs.current.values()].at(-1)
    if (!preferred) return
    if (document.activeElement === preferred) return
    preferred.focus({ preventScroll: true })
  }, [focusedPartIndex])

  const autoFocusedKeyRef = useRef<string | null>(null)
  const isComposerInput = useCallback((node: Element | null) => {
    if (!(node instanceof HTMLInputElement)) return false
    return [...textInputRefs.current.values()].includes(node)
  }, [])

  // Focus chat input on page load / session switch (empty and non-empty).
  // Only treat focus as done when document.activeElement is actually our input —
  // browsers often ignore focus() on reload until a later tick.
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

    // If something else briefly steals focus (ScrollArea), reclaim it once.
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
  }, [applyComposerCaret, autoFocus, focusKey, isComposerInput])

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

  function caretAfterInsertedToken(nextValue: string, token: string): number {
    const index = nextValue.lastIndexOf(token)
    if (index < 0) return nextValue.length
    let caret = index + token.length
    if (nextValue[caret] === ' ') caret += 1
    return caret
  }

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

  const selectedSpecialist =
    specialists.find(item => item.id === selectedSpecialistId) || null

  const atResults = useMemo(() => {
    if (!atMention) return []
    const query = atMention.query.toLowerCase()
    return workspaceFiles
      .filter(file => file.type === 'file')
      .filter(file => {
        if (!query) return true
        return (
          file.name.toLowerCase().includes(query) ||
          file.path.toLowerCase().includes(query)
        )
      })
      .slice(0, 40)
  }, [atMention, workspaceFiles])

  useEffect(() => {
    setSlashDismissed(false)
  }, [slash?.start])

  useEffect(() => {
    setAtDismissed(false)
  }, [atMention?.start])

  const focusAfterChipInsert = (caret: number) => {
    applyComposerCaret(caret)
    // Messages view re-renders the transcript on parent updates and can blur
    // the follow-up input. Keep restoring for a couple frames.
    window.requestAnimationFrame(() => {
      applyComposerCaret(caret)
      window.requestAnimationFrame(() => {
        applyComposerCaret(caret)
        pendingCaretRef.current = null
      })
    })
  }

  const insertSkillChip = (skill: AgentSkill) => {
    if (!slash) return
    const before = draft.slice(0, slash.start)
    const after = draft.slice(slash.end).replace(/^\s+/u, '')
    const token = skillChipToken(skill.name)
    const nextValue = spaceAroundChips(
      after ? `${before}${token} ${after}` : `${before}${token}`
    )
    const caret = caretAfterInsertedToken(nextValue, token)
    pendingCaretRef.current = caret
    // Keep chip insert local — syncing App state re-renders the message list
    // and steals focus in sessions with history. Live draft ref covers send.
    flushSync(() => {
      emittedDraftRef.current = nextValue
      setLocalDraft(nextValue)
    })
    focusAfterChipInsert(caret)
  }

  const insertMcpChip = (server: McpServer) => {
    if (!slash) return
    const before = draft.slice(0, slash.start)
    const after = draft.slice(slash.end).replace(/^\s+/u, '')
    const token = mcpChipToken(server.id, server.name)
    const nextValue = spaceAroundChips(
      after ? `${before}${token} ${after}` : `${before}${token}`
    )
    const caret = caretAfterInsertedToken(nextValue, token)
    pendingCaretRef.current = caret
    flushSync(() => {
      emittedDraftRef.current = nextValue
      setLocalDraft(nextValue)
    })
    focusAfterChipInsert(caret)
  }

  const insertFileChip = (file: WorkspaceFile) => {
    if (!atMention) return
    const before = draft.slice(0, atMention.start)
    const after = draft.slice(atMention.end).replace(/^\s+/u, '')
    const token = fileChipToken(file.path)
    const nextValue = spaceAroundChips(
      after ? `${before}${token} ${after}` : `${before}${token}`
    )
    const caret = caretAfterInsertedToken(nextValue, token)
    pendingCaretRef.current = caret
    flushSync(() => {
      emittedDraftRef.current = nextValue
      setLocalDraft(nextValue)
    })
    focusAfterChipInsert(caret)
  }

  const insertExample = (skillName: string, prompt: string) => {
    if (!slash) return
    const before = draft.slice(0, slash.start)
    const after = draft.slice(slash.end).replace(/^\s+/u, '')
    const token = skillChipToken(skillName)
    const spacedPrompt = prompt.replace(/^\s+/u, '')
    const nextValue = spaceAroundChips(
      `${before}${token} ${spacedPrompt}${after}`
    )
    const caret =
      caretAfterInsertedToken(nextValue, token) + spacedPrompt.length
    pendingCaretRef.current = caret
    flushSync(() => {
      emittedDraftRef.current = nextValue
      setLocalDraft(nextValue)
    })
    focusAfterChipInsert(caret)
  }

  const focusComposerAt = (nextValue: string, absoluteCaret: number) => {
    draftRef.current = nextValue
    pendingCaretRef.current = absoluteCaret
    if (!applyComposerCaret(absoluteCaret)) {
      // useLayoutEffect / rAF retries will pick this up after mount.
    }
  }

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

  const handleSend = () => {
    const text = draftRef.current
    if (!text.trim()) return
    setAuraTick(tick => tick + 1)
    // Clear immediately — parent value may already be "" so the sync effect
    // would otherwise treat this as a no-op echo and leave the draft in place.
    // While a run is active, parent queues instead of sending.
    emittedDraftRef.current = ''
    setLocalDraft('')
    onSend(text)
  }

  const hasDraft = Boolean(draft.trim())
  const showStopButton = running && !hasDraft

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
      handleSend()
    }
  }

  const composerParts = useMemo(() => parseComposerParts(draft), [draft])

  const hasInlineChips = composerParts.some(part => part.type !== 'text')
  let chipRenderIndex = -1

  return (
    <div className="relative">
      {showAura ? (
        <div className="mb-3 flex justify-start pl-1">
          <AuraIconPulse
            className="text-muted-foreground/70 h-10 w-10"
            animateTick={auraTick}
          />
        </div>
      ) : null}

      <ComposerAtMenu
        ref={atMenuRef}
        open={atOpen}
        results={atResults}
        workspaceFileCount={workspaceFiles.length}
        onPick={insertFileChip}
        onDismiss={() => setAtDismissed(true)}
        focusInput={focusActiveComposerInput}
      />

      <ComposerSlashMenu
        ref={slashMenuRef}
        open={slashOpen}
        slash={slash}
        skills={skills}
        mcpServers={mcpServers}
        selectedSpecialist={selectedSpecialist}
        onLoadSkill={onLoadSkill}
        onPickSkill={insertSkillChip}
        onPickMcp={insertMcpChip}
        onPickExample={insertExample}
        onDismiss={() => setSlashDismissed(true)}
        focusInput={focusActiveComposerInput}
      />

      <div
        className={cn(
          editingQueued &&
            'overflow-hidden rounded-3xl border border-sky-500/40 bg-sky-500/5'
        )}
      >
        {editingQueued ? (
          <div className="flex items-center justify-between px-3 py-1.5 text-[12px]">
            <span className="text-sky-700 dark:text-sky-300">
              Editing queued message
            </span>
            <button
              type="button"
              onClick={() => onCancelEditQueued?.()}
              className="text-sky-700 hover:text-sky-900 dark:text-sky-300 dark:hover:text-sky-100 font-medium"
            >
              Cancel
            </button>
          </div>
        ) : null}
        <form
          onSubmit={event => {
            event.preventDefault()
            handleSend()
          }}
          className={cn(
            'bg-card focus-within:border-muted-foreground/40 border-border rounded-3xl border p-2 shadow-[0_4px_16px_-8px_rgba(0,0,0,0.12),0_1px_2px_rgba(0,0,0,0.05)] dark:shadow-[0_8px_24px_-12px_rgba(0,0,0,0.65)]',
            editingQueued &&
              'rounded-t-none border-x-0 border-b-0 border-t border-sky-500/25 shadow-none focus-within:border-sky-500/40'
          )}
        >
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
              const name = part.path.split('/').at(-1) || part.path
              return (
                <span
                  key={`file-${partIndex}-${part.path}`}
                  className="bg-muted/50 border-border/70 inline-flex max-w-full select-none items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs"
                >
                  <Icon
                    icon={getFileIcon(name)}
                    className="text-muted-foreground size-3.5 shrink-0"
                  />
                  <button
                    type="button"
                    className="text-foreground max-w-[180px] truncate hover:underline"
                    title={`Open @${part.path}`}
                    onClick={() => onOpenFile?.(part.path)}
                  >
                    @{name}
                  </button>
                  <button
                    type="button"
                    className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex size-4 items-center justify-center rounded-full"
                    onClick={() => {
                      commitDraft(removeComposerChipAt(draft, chipIndex))
                      onFileChipsChange?.([])
                    }}
                    aria-label={`Remove @${name}`}
                  >
                    <X className="size-3" />
                  </button>
                </span>
              )
            }
            if (part.type === 'skill') {
              chipRenderIndex += 1
              const chipIndex = chipRenderIndex
              return (
                <span
                  key={`skill-${partIndex}-${part.name}`}
                  className="border-primary/30 bg-primary/5 inline-flex max-w-full select-none items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs"
                >
                  <Sparkles className="text-primary/80 size-3.5 shrink-0" />
                  <button
                    type="button"
                    className="text-foreground max-w-[200px] truncate hover:underline"
                    onClick={() =>
                      window.open(
                        `/dashboard/skills/${encodeURIComponent(part.name)}`,
                        '_blank',
                        'noopener,noreferrer'
                      )
                    }
                  >
                    {part.name}
                  </button>
                  <button
                    type="button"
                    className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex size-4 items-center justify-center rounded-full"
                    onClick={() => {
                      commitDraft(removeComposerChipAt(draft, chipIndex))
                      onSkillChipsChange([])
                    }}
                    aria-label={`Remove skill ${part.name}`}
                  >
                    <X className="size-3" />
                  </button>
                </span>
              )
            }
            if (part.type === 'mcp') {
              chipRenderIndex += 1
              const chipIndex = chipRenderIndex
              const href = `/dashboard/mcp/server/${encodeURIComponent(part.id)}`
              return (
                <span
                  key={`mcp-${partIndex}-${part.id}`}
                  className="border-border/70 bg-muted/40 inline-flex max-w-full select-none items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs"
                >
                  <Plug className="text-muted-foreground size-3.5 shrink-0" />
                  <button
                    type="button"
                    className="text-foreground max-w-[200px] truncate hover:underline"
                    onClick={() =>
                      window.open(href, '_blank', 'noopener,noreferrer')
                    }
                  >
                    {part.name}
                  </button>
                  <button
                    type="button"
                    className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex size-4 items-center justify-center rounded-full"
                    onClick={() => {
                      commitDraft(removeComposerChipAt(draft, chipIndex))
                    }}
                    aria-label={`Remove MCP ${part.name}`}
                  >
                    <X className="size-3" />
                  </button>
                </span>
              )
            }

            const isLastText =
              partIndex ===
              composerParts.reduce(
                (last, item, index) => (item.type === 'text' ? index : last),
                0
              )
            // Skip truly empty gaps between chips.
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

            // Only the empty composer (no chips, no text) shows a placeholder.
            const showPlaceholder =
              isLastText && !part.text && !hasInlineChips
                ? running
                  ? 'Add a follow-up'
                  : 'Ask Agent, @ for context, / for skills & MCPs'
                : undefined

            // Always render the same wrapper/input structure so React
            // reconciles (keeps focus) instead of remounting when the empty
            // last-text input gains its first character.
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
                  // Native autofocus is allowed on load; JS focus() often is not.
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
        <div className="flex min-w-0 items-center justify-between gap-2 px-0.5">
          <div className="flex min-w-0 flex-1 items-center gap-1 overflow-hidden">
            <input
              ref={uploadRef}
              type="file"
              multiple
              hidden
              onChange={event => {
                if (event.target.files) void onUpload(event.target.files)
                event.target.value = ''
              }}
            />
            <Button
              variant="ghost"
              size="icon"
              className="size-7 shrink-0 rounded-full"
              type="button"
              onClick={() => uploadRef.current?.click()}
            >
              <Plus className="size-4" />
            </Button>
            <ComposerModelPicker
              modelOptions={modelOptions}
              runtimeSettings={runtimeSettings}
              onModelSelect={onModelSelect}
              onReasoningSettingsChange={onReasoningSettingsChange}
              onAddModels={onAddModels}
            />
            {onSpecialistSelect ? (
              <ComposerSpecialistPicker
                specialists={specialists}
                selectedSpecialistId={selectedSpecialistId}
                onSpecialistSelect={onSpecialistSelect}
                onCreateSpecialist={onCreateSpecialist}
                onManageSpecialists={onManageSpecialists}
              />
            ) : null}
            {onSandboxBackendSelect ? (
              <ComposerSandboxPicker
                sandboxStatus={sandboxStatus}
                sandboxPhase={sandboxPhase}
                onSandboxBackendSelect={onSandboxBackendSelect}
                onSandboxComputeChange={onSandboxComputeChange}
                onSandboxStart={onSandboxStart}
                onSandboxStop={onSandboxStop}
                onSandboxRestart={onSandboxRestart}
                onLoadLocalSystem={onLoadLocalSystem}
              />
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <ComposerTokenUsage tokenUsage={tokenUsage} />
            <Button
              type={showStopButton ? 'button' : 'submit'}
              size="icon"
              className="bg-foreground text-background hover:bg-foreground/90 size-7 rounded-full shadow-none [&_svg]:text-background"
              onClick={showStopButton ? onStop : undefined}
              aria-label={
                showStopButton ? 'Stop' : running ? 'Queue message' : 'Send'
              }
              title={
                showStopButton ? 'Stop' : running ? 'Queue' : 'Send'
              }
            >
              {showStopButton ? (
                <Square className="size-3 fill-current" />
              ) : (
                <ArrowUp className="size-4" strokeWidth={2.5} />
              )}
            </Button>
          </div>
        </div>
      </form>
      </div>
    </div>
  )
}
