import { Icon } from '@iconify/react'
import type {
  AgentSkill,
  AgentSkillDetail,
  RuntimeSettings,
  SessionSandboxStatus,
  Specialist,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import {
  ArrowUp,
  Check,
  ChevronDown,
  CornerDownLeft,
  Loader,
  Plus,
  Sparkles,
  Square,
  X
} from 'lucide-react'
import { type KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import {
  fileChipToken,
  parseComposerParts,
  removeComposerChipAt,
  serializeComposerParts,
  skillChipToken,
  spaceAroundChips
} from '@/components/agents/composer-parts'
import {
  computeAtFileQuery,
  computeSlashSkillQuery,
  extractSkillOverviewFromMarkdown,
  getSkillPromptExamples
} from '@/components/agents/skill-examples'
import {
  specialistColorClass,
  SpecialistGlyph} from '@/components/agents/SpecialistsView'
import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { getFileIcon } from '@/lib/file-icons'
import { composerSkillIcon, skillIconInvertInDark } from '@/lib/skill-icons'
import {
  compareSkillsBySearchRank,
  skillMatchesSearch
} from '@/lib/skill-search'
import { cn } from '@/lib/utils'

function cleanSkillDescription(value: string | null | undefined) {
  const text = String(value || '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!text || text === '>' || text === '-') return ''
  return text
}

function formatTokenCount(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}k`
  return `${Math.max(0, Math.round(tokens))}`
}

function ModalGlyph({ className }: { className?: string }) {
  const icon = INTEGRATION_ICONS.modal
  return (
    <img
      src={icon.src}
      alt=""
      className={cn('size-3.5 shrink-0 rounded-sm object-contain', className)}
    />
  )
}

export type SandboxActionPhase =
  | 'idle'
  | 'starting'
  | 'stopping'
  | 'restarting'

function sandboxStatusLabel(
  status: SessionSandboxStatus | null | undefined,
  phase: SandboxActionPhase = 'idle'
) {
  if (phase === 'starting' || status?.status === 'starting') return 'Starting'
  if (phase === 'stopping' || status?.status === 'stopping') return 'Stopping'
  if (phase === 'restarting') return 'Restarting'
  if (!status) return 'Sandbox'
  if (status.backend !== 'modal') return 'Built-in'
  if (status.status === 'running') return 'Running'
  if (status.status === 'unavailable') return 'Unavailable'
  return 'Stopped'
}

function sandboxStatusDotClass(
  status: SessionSandboxStatus | null | undefined,
  phase: SandboxActionPhase = 'idle'
) {
  if (
    phase !== 'idle' ||
    status?.status === 'starting' ||
    status?.status === 'stopping'
  ) {
    return 'bg-muted-foreground/50'
  }
  if (!status || status.backend !== 'modal') return 'bg-muted-foreground/40'
  if (status.status === 'running') return 'bg-emerald-500'
  if (status.status === 'unavailable') return 'bg-amber-500'
  return 'bg-muted-foreground/50'
}

export function Composer({
  value,
  running,
  skills,
  skillChips: _skillChips,
  fileChips: _fileChips = [],
  workspaceFiles = [],
  modelOptions,
  specialists = [],
  selectedSpecialistId = null,
  sandboxStatus = null,
  sandboxPhase = 'idle',
  showAura = true,
  onChange,
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
  onSpecialistSelect,
  onCreateSpecialist,
  onSandboxBackendSelect,
  onSandboxStart,
  onSandboxStop,
  onSandboxRestart
}: {
  value: string
  running: boolean
  skills: AgentSkill[]
  skillChips: string[]
  fileChips?: string[]
  workspaceFiles?: WorkspaceFile[]
  modelOptions: Array<{
    provider: string
    model: string
    label: string
    speed?: string
    profileId?: string | null
    source?: string
  }>
  specialists?: Specialist[]
  selectedSpecialistId?: string | null
  sandboxStatus?: SessionSandboxStatus | null
  sandboxPhase?: SandboxActionPhase
  showAura?: boolean
  onChange: (value: string) => void
  onSkillChipsChange: (skills: string[]) => void
  onFileChipsChange?: (files: string[]) => void
  onSend: () => void
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
  onSpecialistSelect?: (specialistId: string | null) => void | Promise<void>
  onCreateSpecialist?: () => void
  onSandboxBackendSelect?: (
    backend: 'builtin' | 'modal'
  ) => void | Promise<void>
  onSandboxStart?: () => void | Promise<void>
  onSandboxStop?: () => void | Promise<void>
  onSandboxRestart?: () => void | Promise<void>
}) {
  const uploadRef = useRef<HTMLInputElement | null>(null)
  const textInputRefs = useRef<Map<number, HTMLInputElement>>(new Map())
  const [caretPos, setCaretPos] = useState(0)
  const [focusedPartIndex, setFocusedPartIndex] = useState(0)
  const [selectedSkillName, setSelectedSkillName] = useState<string | null>(
    null
  )
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewOverview, setPreviewOverview] = useState<string | null>(null)
  const [auraTick, setAuraTick] = useState(0)
  const [slashDismissed, setSlashDismissed] = useState(false)
  const [atDismissed, setAtDismissed] = useState(false)
  const [modelPickerOpen, setModelPickerOpen] = useState(false)
  const [modelSearch, setModelSearch] = useState('')
  const [specialistPickerOpen, setSpecialistPickerOpen] = useState(false)
  const [sandboxPickerOpen, setSandboxPickerOpen] = useState(false)
  const previewCacheRef = useRef<Map<string, string>>(new Map())
  const skillItemRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const fileItemRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const slashListRootRef = useRef<HTMLDivElement | null>(null)
  const atListRootRef = useRef<HTMLDivElement | null>(null)

  const focusActiveComposerInput = useCallback(() => {
    const preferred =
      textInputRefs.current.get(focusedPartIndex) ||
      [...textInputRefs.current.values()].at(-1)
    if (!preferred) return
    if (document.activeElement === preferred) return
    preferred.focus({ preventScroll: true })
  }, [focusedPartIndex])

  const scrollSkillIntoView = useCallback((skillName: string) => {
    const node = skillItemRefs.current.get(skillName)
    const viewport = slashListRootRef.current?.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLElement | null
    if (!node || !viewport) return
    const nodeRect = node.getBoundingClientRect()
    const viewRect = viewport.getBoundingClientRect()
    const pad = 6
    if (nodeRect.bottom > viewRect.bottom - pad) {
      viewport.scrollTop += nodeRect.bottom - viewRect.bottom + pad
    } else if (nodeRect.top < viewRect.top + pad) {
      viewport.scrollTop -= viewRect.top - nodeRect.top + pad
    }
  }, [])

  const scrollFileIntoView = useCallback((filePath: string) => {
    const node = fileItemRefs.current.get(filePath)
    const viewport = atListRootRef.current?.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLElement | null
    if (!node || !viewport) return
    const nodeRect = node.getBoundingClientRect()
    const viewRect = viewport.getBoundingClientRect()
    const pad = 6
    if (nodeRect.bottom > viewRect.bottom - pad) {
      viewport.scrollTop += nodeRect.bottom - viewRect.bottom + pad
    } else if (nodeRect.top < viewRect.top + pad) {
      viewport.scrollTop -= viewRect.top - nodeRect.top + pad
    }
  }, [])

  const slash = useMemo(
    () => computeSlashSkillQuery(value, caretPos),
    [caretPos, value]
  )
  const atMention = useMemo(
    () => computeAtFileQuery(value, caretPos),
    [caretPos, value]
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

  const slashResults = useMemo(() => {
    if (!slash) return []
    const query = slash.query.toLowerCase().trim()
    const specialistSkillSet = selectedSpecialist
      ? new Set(
          (selectedSpecialist.skillNames || [])
            .map(name => name.trim().toLowerCase())
            .filter(Boolean)
        )
      : null
    const seen = new Set<string>()
    return skills
      .filter(skill => skill.enabled)
      .filter(skill => {
        if (!specialistSkillSet) return true
        return specialistSkillSet.has(skill.name.trim().toLowerCase())
      })
      .filter(skill => {
        const key = skill.name.trim().toLowerCase()
        if (!key || seen.has(key)) return false
        seen.add(key)
        return skillMatchesSearch(skill, query)
      })
      .slice()
      .sort((a, b) => compareSkillsBySearchRank(a, b, query))
  }, [selectedSpecialist, skills, slash])

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
  }, [slash?.start, slash?.query])

  useEffect(() => {
    setAtDismissed(false)
  }, [atMention?.start, atMention?.query])

  const selectedSkill =
    slashResults.find(skill => skill.name === selectedSkillName) ||
    slashResults[0] ||
    null

  const selectedFile =
    atResults.find(file => file.path === selectedFilePath) ||
    atResults[0] ||
    null

  useEffect(() => {
    if (!slashOpen) {
      setSelectedSkillName(null)
      return
    }
    if (
      selectedSkillName &&
      slashResults.some(skill => skill.name === selectedSkillName)
    ) {
      return
    }
    setSelectedSkillName(slashResults[0]?.name || null)
  }, [selectedSkillName, slashOpen, slashResults])

  useEffect(() => {
    if (!atOpen) {
      setSelectedFilePath(null)
      return
    }
    if (
      selectedFilePath &&
      atResults.some(file => file.path === selectedFilePath)
    ) {
      return
    }
    setSelectedFilePath(atResults[0]?.path || null)
  }, [atOpen, atResults, selectedFilePath])

  useEffect(() => {
    if (!slashOpen || !selectedSkill) {
      setPreviewOverview(null)
      setPreviewLoading(false)
      return
    }
    const cached = previewCacheRef.current.get(selectedSkill.name)
    if (cached) {
      setPreviewOverview(cached)
      setPreviewLoading(false)
      return
    }
    let active = true
    setPreviewLoading(true)
    void onLoadSkill(selectedSkill.name)
      .then(detail => {
        if (!active) return
        const overview =
          extractSkillOverviewFromMarkdown(detail.content) ||
          cleanSkillDescription(detail.description) ||
          `Use /${detail.name} to run this skill.`
        previewCacheRef.current.set(selectedSkill.name, overview)
        setPreviewOverview(overview)
      })
      .catch(() => {
        if (!active) return
        const fallback =
          cleanSkillDescription(selectedSkill.description) ||
          `Use /${selectedSkill.name} to run this skill.`
        setPreviewOverview(fallback)
      })
      .finally(() => {
        if (active) setPreviewLoading(false)
      })
    return () => {
      active = false
    }
  }, [onLoadSkill, selectedSkill, slashOpen])

  const selectedModel =
    modelOptions.find(option => option.model === runtimeSettings?.model) ||
    (runtimeSettings
      ? {
          provider: runtimeSettings.provider,
          model: runtimeSettings.model,
          label: runtimeSettings.model,
          speed: ''
        }
      : modelOptions[0] || {
          provider: 'anthropic',
          model: '',
          label: 'Select model',
          speed: ''
        })

  const filteredModelOptions = useMemo(() => {
    const needle = modelSearch.trim().toLowerCase()
    if (!needle) return modelOptions
    return modelOptions.filter(option => {
      const haystack = [
        option.label,
        option.model,
        option.provider,
        option.speed || '',
        option.source || '',
        option.profileId || ''
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(needle)
    })
  }, [modelOptions, modelSearch])

  const usagePercent = Math.min(
    100,
    ((tokenUsage.inputTokens + tokenUsage.outputTokens) / 200_000) * 100
  )

  const selectedExamples = selectedSkill
    ? getSkillPromptExamples(selectedSkill.name)
    : []

  const insertSkillChip = (skill: AgentSkill) => {
    if (!slash) return
    const before = value.slice(0, slash.start)
    const after = value.slice(slash.end).replace(/^\s+/u, '')
    const token = skillChipToken(skill.name)
    const nextValue = spaceAroundChips(
      after ? `${before}${token} ${after}` : `${before}${token}`
    )
    onChange(nextValue)
    onSkillChipsChange([])
    setSelectedSkillName(null)
    window.requestAnimationFrame(() => {
      focusComposerAt(nextValue, before.length + token.length)
    })
  }

  const insertFileChip = (file: WorkspaceFile) => {
    if (!atMention) return
    const before = value.slice(0, atMention.start)
    const after = value.slice(atMention.end).replace(/^\s+/u, '')
    const token = fileChipToken(file.path)
    const nextValue = spaceAroundChips(
      after ? `${before}${token} ${after}` : `${before}${token}`
    )
    onChange(nextValue)
    onFileChipsChange?.([])
    setSelectedFilePath(null)
    window.requestAnimationFrame(() => {
      focusComposerAt(nextValue, before.length + token.length)
    })
  }

  const insertExample = (skillName: string, prompt: string) => {
    if (!slash) return
    const before = value.slice(0, slash.start)
    const after = value.slice(slash.end).replace(/^\s+/u, '')
    const token = skillChipToken(skillName)
    const spacedPrompt = prompt.replace(/^\s+/u, '')
    const nextValue = spaceAroundChips(
      `${before}${token} ${spacedPrompt}${after}`
    )
    onSkillChipsChange([])
    onChange(nextValue)
    setSelectedSkillName(null)
    window.requestAnimationFrame(() => {
      focusComposerAt(
        nextValue,
        before.length + token.length + 1 + spacedPrompt.length
      )
    })
  }

  const focusComposerAt = (nextValue: string, absoluteCaret: number) => {
    const tryFocus = (attempts = 0) => {
      const parts = parseComposerParts(nextValue)
      let offset = 0
      for (let index = 0; index < parts.length; index += 1) {
        const part = parts[index]
        if (part.type !== 'text') {
          offset +=
            part.type === 'file'
              ? fileChipToken(part.path).length
              : skillChipToken(part.name).length
          continue
        }
        const tokenStart = offset
        const tokenEnd = offset + part.text.length
        if (absoluteCaret >= tokenStart && absoluteCaret <= tokenEnd) {
          const input = textInputRefs.current.get(index)
          if (!input) {
            if (attempts < 8) {
              window.requestAnimationFrame(() => tryFocus(attempts + 1))
            }
            return
          }
          const local = Math.min(
            Math.max(0, absoluteCaret - tokenStart),
            input.value.length
          )
          input.focus({ preventScroll: true })
          input.setSelectionRange(local, local)
          setCaretPos(tokenStart + local)
          setFocusedPartIndex(index)
          return
        }
        offset = tokenEnd
      }
      const lastTextIndex = [...parts]
        .map((part, index) => (part.type === 'text' ? index : -1))
        .filter(index => index >= 0)
        .at(-1)
      if (lastTextIndex == null) return
      const last = textInputRefs.current.get(lastTextIndex)
      if (!last) {
        if (attempts < 8) {
          window.requestAnimationFrame(() => tryFocus(attempts + 1))
        }
        return
      }
      const len = last.value.length
      last.focus({ preventScroll: true })
      last.setSelectionRange(len, len)
      setCaretPos(nextValue.length)
      setFocusedPartIndex(lastTextIndex)
    }
    tryFocus()
  }

  const removeChipBeforeFocusedText = (partIndex: number) => {
    const parts = parseComposerParts(value)
    if (partIndex <= 0) return false
    const prev = parts[partIndex - 1]
    if (!prev || prev.type === 'text') return false
    let chipIndex = -1
    for (let i = 0; i < partIndex; i += 1) {
      if (parts[i].type !== 'text') chipIndex += 1
    }
    const nextValue = removeComposerChipAt(value, chipIndex)
    onChange(nextValue)
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
    const parts = parseComposerParts(value).map((part, index) =>
      index === partIndex && part.type === 'text' ? { ...part, text } : part
    )
    const nextValue = serializeComposerParts(parts)
    onChange(nextValue)
    let absolute = 0
    for (let index = 0; index < parts.length; index += 1) {
      const part = parts[index]
      if (part.type !== 'text') {
        absolute +=
          part.type === 'file'
            ? fileChipToken(part.path).length
            : skillChipToken(part.name).length
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
    if (running) return
    setAuraTick(tick => tick + 1)
    onSend()
  }

  useEffect(() => {
    if (!slashOpen && !atOpen) return
    const frame = window.requestAnimationFrame(() => {
      focusActiveComposerInput()
    })
    return () => window.cancelAnimationFrame(frame)
  }, [atOpen, focusActiveComposerInput, slashOpen])

  useEffect(() => {
    if (!slashOpen || !selectedSkill) return
    scrollSkillIntoView(selectedSkill.name)
  }, [scrollSkillIntoView, selectedSkill?.name, slashOpen])

  useEffect(() => {
    if (!atOpen || !selectedFile) return
    scrollFileIntoView(selectedFile.path)
  }, [atOpen, scrollFileIntoView, selectedFile?.path])

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    const input = event.currentTarget
    const localCaret = input.selectionStart ?? 0

    if (event.key === 'Backspace') {
      const parts = parseComposerParts(value)
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

    if (atOpen && event.key === 'Escape') {
      event.preventDefault()
      setAtDismissed(true)
      setSelectedFilePath(null)
      return
    }
    if (atOpen && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
      event.preventDefault()
      event.stopPropagation()
      if (atResults.length === 0) return
      const currentIndex = atResults.findIndex(
        file => file.path === selectedFile?.path
      )
      const safeIndex = currentIndex < 0 ? 0 : currentIndex
      const nextIndex =
        event.key === 'ArrowDown'
          ? Math.min(safeIndex + 1, atResults.length - 1)
          : Math.max(safeIndex - 1, 0)
      const nextPath = atResults[nextIndex]?.path
      if (!nextPath) return
      setSelectedFilePath(nextPath)
      window.requestAnimationFrame(() => {
        focusActiveComposerInput()
        scrollFileIntoView(nextPath)
      })
      return
    }
    if (atOpen && event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (selectedFile) insertFileChip(selectedFile)
      return
    }
    if (slashOpen && event.key === 'Escape') {
      event.preventDefault()
      setSlashDismissed(true)
      setSelectedSkillName(null)
      return
    }
    if (slashOpen && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
      event.preventDefault()
      event.stopPropagation()
      if (slashResults.length === 0) return
      const currentIndex = slashResults.findIndex(
        skill => skill.name === selectedSkill?.name
      )
      const safeIndex = currentIndex < 0 ? 0 : currentIndex
      const nextIndex =
        event.key === 'ArrowDown'
          ? Math.min(safeIndex + 1, slashResults.length - 1)
          : Math.max(safeIndex - 1, 0)
      const nextName = slashResults[nextIndex]?.name
      if (!nextName) return
      setSelectedSkillName(nextName)
      window.requestAnimationFrame(() => {
        focusActiveComposerInput()
        scrollSkillIntoView(nextName)
      })
      return
    }
    if (slashOpen && event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (selectedSkill) insertSkillChip(selectedSkill)
      return
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  const composerParts = useMemo(
    () => parseComposerParts(spaceAroundChips(value)),
    [value]
  )

  useEffect(() => {
    const next = spaceAroundChips(value)
    if (next !== value) onChange(next)
  }, [onChange, value])
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

      {atOpen ? (
        <div className="bg-popover border-border/70 absolute bottom-full left-0 right-0 z-40 mb-2 overflow-hidden rounded-lg border shadow-lg">
          <div ref={atListRootRef} className="min-h-0">
            <ScrollArea className="h-64">
              <div className="p-1" role="listbox" aria-label="Workspace files">
                {atResults.length > 0 ? (
                  atResults.map(file => {
                    const selected = selectedFile?.path === file.path
                    return (
                      <button
                        key={file.path}
                        type="button"
                        tabIndex={-1}
                        role="option"
                        aria-selected={selected}
                        ref={node => {
                          if (node) fileItemRefs.current.set(file.path, node)
                          else fileItemRefs.current.delete(file.path)
                        }}
                        onMouseDown={event => event.preventDefault()}
                        onMouseEnter={() => setSelectedFilePath(file.path)}
                        onClick={() => {
                          insertFileChip(file)
                          window.requestAnimationFrame(() => {
                            focusActiveComposerInput()
                          })
                        }}
                        className={cn(
                          'hover:bg-muted flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left',
                          selected && 'bg-muted'
                        )}
                      >
                        <Icon
                          icon={getFileIcon(file.name)}
                          className="mt-0.5 size-4 shrink-0"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium">
                            @{file.name}
                          </span>
                          <span className="text-muted-foreground block truncate text-[11px]">
                            workspace/{file.path}
                          </span>
                        </span>
                      </button>
                    )
                  })
                ) : (
                  <div className="text-muted-foreground px-2 py-1.5 text-xs">
                    {workspaceFiles.length === 0
                      ? 'No workspace files yet'
                      : 'No matching files'}
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>
        </div>
      ) : null}

      {slashOpen ? (
        <div className="bg-popover border-border/70 absolute bottom-full left-0 right-0 z-40 mb-2 overflow-hidden rounded-lg border shadow-lg">
          {selectedSpecialist ? (
            <div className="border-border/60 text-muted-foreground border-b px-3 py-1.5 text-[11px]">
              Showing skills for{' '}
              <span className="text-foreground font-medium">
                {selectedSpecialist.name}
              </span>
            </div>
          ) : null}
          <div className="grid h-72 grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div ref={slashListRootRef} className="min-h-0 min-w-0">
              <ScrollArea className="border-border/60 h-72 border-r">
                <div className="p-1" role="listbox" aria-label="Skills">
                  {slashResults.length > 0 ? (
                    slashResults.map(skill => {
                      const description =
                        cleanSkillDescription(skill.description) || skill.name
                      const iconSource = composerSkillIcon(skill)
                      const isSelected = selectedSkill?.name === skill.name
                      return (
                        <button
                          key={skill.name}
                          type="button"
                          tabIndex={-1}
                          role="option"
                          aria-selected={isSelected}
                          ref={node => {
                            if (node) skillItemRefs.current.set(skill.name, node)
                            else skillItemRefs.current.delete(skill.name)
                          }}
                          onMouseDown={event => event.preventDefault()}
                          onMouseEnter={() => setSelectedSkillName(skill.name)}
                          onClick={() => {
                            insertSkillChip(skill)
                            window.requestAnimationFrame(() => {
                              focusActiveComposerInput()
                            })
                          }}
                          className={cn(
                            'hover:bg-muted flex w-full flex-col rounded-md px-2 py-1.5 text-left',
                            isSelected && 'bg-muted'
                          )}
                        >
                          <span className="flex min-w-0 items-center gap-2">
                            {iconSource ? (
                              <img
                                src={iconSource}
                                alt=""
                                className={cn(
                                  'size-[18px] shrink-0 rounded object-contain',
                                  skillIconInvertInDark(skill) && 'dark:invert'
                                )}
                              />
                            ) : (
                              <span className="bg-primary/10 text-primary inline-flex size-[18px] shrink-0 items-center justify-center rounded">
                                <Sparkles className="size-3" />
                              </span>
                            )}
                            <span className="truncate text-sm font-medium">
                              /{skill.name}
                            </span>
                          </span>
                          <span className="text-muted-foreground truncate text-xs">
                            {description}
                          </span>
                          {(skill.author || skill.version) && (
                            <span className="text-muted-foreground/70 truncate text-[10px]">
                              {[skill.author, skill.version]
                                .filter(Boolean)
                                .join(' · ')}
                            </span>
                          )}
                        </button>
                      )
                    })
                  ) : (
                    <div className="text-muted-foreground px-2 py-1.5 text-xs">
                      {selectedSpecialist
                        ? `No matching skills for ${selectedSpecialist.name}`
                        : 'No skills found'}
                    </div>
                  )}
                </div>
              </ScrollArea>
            </div>
            <ScrollArea className="h-72">
              <div className="px-1 py-1">
                {selectedSkill ? (
                  <div className="space-y-3 px-2 py-1">
                    <div className="flex items-start justify-between gap-2">
                      <span className="truncate text-sm font-semibold">
                        /{selectedSkill.name}
                      </span>
                      <a
                        href={`/dashboard/skills/${encodeURIComponent(
                          selectedSkill.name
                        )}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary shrink-0 text-[11px] font-medium hover:underline"
                        onMouseDown={event => event.preventDefault()}
                      >
                        Read more
                      </a>
                    </div>
                    <p className="text-muted-foreground line-clamp-3 text-[11px] leading-relaxed">
                      {previewLoading
                        ? 'Loading preview…'
                        : previewOverview ||
                          cleanSkillDescription(selectedSkill.description) ||
                          `Use /${selectedSkill.name} to run this skill.`}
                    </p>
                    <div className="border-border/60 border-t pt-2">
                      <p className="text-muted-foreground mb-1 text-[10px] font-semibold uppercase tracking-wide">
                        Examples
                      </p>
                      <div className="space-y-1">
                        {selectedExamples.map(example => (
                          <button
                            key={`${selectedSkill.name}-${example.title}`}
                            type="button"
                            tabIndex={-1}
                            onMouseDown={event => event.preventDefault()}
                            onClick={() =>
                              insertExample(selectedSkill.name, example.prompt)
                            }
                            className="hover:bg-muted/50 border-border/60 bg-background w-full rounded-md border px-2 py-1.5 text-left"
                          >
                            <span className="flex items-center justify-between gap-2">
                              <span className="block truncate text-[11px] font-medium">
                                {example.title}
                              </span>
                              <span className="border-primary/30 text-primary inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium">
                                Try
                                <CornerDownLeft className="h-3 w-3" />
                              </span>
                            </span>
                            <span className="text-muted-foreground mt-0.5 line-clamp-2 block text-[10px]">
                              {example.prompt}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-muted-foreground p-3 text-xs">
                    Select a skill to preview its workflow.
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>
        </div>
      ) : null}

      <form
        onSubmit={event => {
          event.preventDefault()
          handleSend()
        }}
        className="bg-card focus-within:border-muted-foreground/40 border-border rounded-3xl border p-2 shadow-[0_4px_16px_-8px_rgba(0,0,0,0.12),0_1px_2px_rgba(0,0,0,0.05)] dark:shadow-[0_8px_24px_-12px_rgba(0,0,0,0.65)]"
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
                      onChange(removeComposerChipAt(value, chipIndex))
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
                    /{part.name}
                  </button>
                  <button
                    type="button"
                    className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex size-4 items-center justify-center rounded-full"
                    onClick={() => {
                      onChange(removeComposerChipAt(value, chipIndex))
                      onSkillChipsChange([])
                    }}
                    aria-label={`Remove /${part.name}`}
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
                else if (item.type === 'file') {
                  absolute += fileChipToken(item.path).length
                } else absolute += skillChipToken(item.name).length
              }
              setCaretPos(absolute + localCaret)
            }

            // Size to glyphs via mirror span. Inputs default to size=20 which
            // otherwise forces ~20ch of empty space before each chip.
            const showPlaceholder =
              isLastText &&
              !part.text &&
              (!hasInlineChips
                ? 'Ask Agent, @ for context, / for skills'
                : 'Add a follow-up…')

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
                      ? 'min-w-[11rem]'
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
                    if (node) textInputRefs.current.set(partIndex, node)
                    else textInputRefs.current.delete(partIndex)
                  }}
                  value={part.text}
                  size={1}
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
        <div className="flex items-center justify-between px-0.5">
          <div className="flex items-center gap-1">
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
              className="size-7 rounded-full"
              type="button"
              onClick={() => uploadRef.current?.click()}
            >
              <Plus className="size-4" />
            </Button>
            <Popover
              open={modelPickerOpen}
              onOpenChange={open => {
                setModelPickerOpen(open)
                if (!open) setModelSearch('')
              }}
            >
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs hover:bg-transparent"
                >
                  <span className="font-medium">{selectedModel.label}</span>
                  {selectedModel.speed ? (
                    <span className="text-muted-foreground text-[11px]">
                      {selectedModel.speed}
                    </span>
                  ) : null}
                  <ChevronDown className="text-muted-foreground size-3.5" />
                </button>
              </PopoverTrigger>
              <PopoverContent
                align="start"
                side="top"
                className="w-64 overflow-hidden p-0"
              >
                <div className="border-b px-3 py-2">
                  <Input
                    value={modelSearch}
                    onChange={event => setModelSearch(event.target.value)}
                    placeholder="Search models"
                    className="h-7 border-0 bg-transparent px-0 text-sm shadow-none focus-visible:ring-0"
                    autoFocus
                  />
                </div>
                <div className="max-h-72 overflow-y-auto overscroll-contain py-1">
                  {modelOptions.length === 0 ? (
                    <div className="text-muted-foreground px-3 py-3 text-sm">
                      No enabled models. Turn models on in Dashboard → Models.
                    </div>
                  ) : filteredModelOptions.length === 0 ? (
                    <div className="text-muted-foreground px-3 py-3 text-sm">
                      No models match “{modelSearch.trim()}”.
                    </div>
                  ) : (
                    filteredModelOptions.map(option => {
                      const isSelected =
                        option.model === runtimeSettings?.model
                      return (
                        <button
                          key={`${option.source || option.provider}:${option.profileId || 'cloud'}:${option.model}`}
                          type="button"
                          className="hover:bg-muted flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm"
                          onClick={() => {
                            void onModelSelect(
                              option.provider,
                              option.model,
                              option.profileId
                            )
                            setModelPickerOpen(false)
                            setModelSearch('')
                          }}
                        >
                          <span className="truncate">{option.label}</span>
                          {option.speed ? (
                            <span className="text-muted-foreground truncate text-xs">
                              {option.speed}
                            </span>
                          ) : null}
                          {isSelected ? (
                            <Check className="text-foreground ml-auto size-4 shrink-0" />
                          ) : null}
                        </button>
                      )
                    })
                  )}
                </div>
              </PopoverContent>
            </Popover>
            {onSpecialistSelect ? (
              <Popover
                open={specialistPickerOpen}
                onOpenChange={setSpecialistPickerOpen}
              >
                <PopoverTrigger asChild>
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 rounded-md px-1.5 py-1 text-xs hover:bg-transparent"
                  >
                    {selectedSpecialist ? (
                      <span
                        className={cn(
                          'flex size-3.5 items-center justify-center rounded-full text-white',
                          specialistColorClass(selectedSpecialist.color)
                        )}
                      >
                        <SpecialistGlyph
                          icon={selectedSpecialist.icon}
                          className="size-2"
                        />
                      </span>
                    ) : (
                      <span className="bg-muted-foreground/40 size-2 rounded-full" />
                    )}
                    <span className="font-medium">
                      {selectedSpecialist?.name || 'None'}
                    </span>
                    <ChevronDown className="text-muted-foreground size-3.5" />
                  </button>
                </PopoverTrigger>
                <PopoverContent
                  align="start"
                  side="top"
                  className="w-64 overflow-hidden p-0"
                >
                  <div className="text-muted-foreground border-b px-3 py-2 text-[11px] font-medium tracking-wide uppercase">
                    Specialist
                  </div>
                  <div className="max-h-72 overflow-y-auto overscroll-contain py-1">
                    <button
                      type="button"
                      className="hover:bg-muted flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm"
                      onClick={() => {
                        void onSpecialistSelect(null)
                        setSpecialistPickerOpen(false)
                      }}
                    >
                      <span className="bg-muted-foreground/40 size-2.5 rounded-full" />
                      <span className="truncate">None</span>
                      {!selectedSpecialistId ? (
                        <Check className="text-foreground ml-auto size-4 shrink-0" />
                      ) : null}
                    </button>
                    {specialists
                      .filter(item => item.enabled !== false)
                      .map(item => {
                      const isSelected = item.id === selectedSpecialistId
                      return (
                        <button
                          key={item.id}
                          type="button"
                          className="hover:bg-muted flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm"
                          onClick={() => {
                            void onSpecialistSelect(item.id)
                            setSpecialistPickerOpen(false)
                          }}
                        >
                          <span
                            className={cn(
                              'flex size-4 shrink-0 items-center justify-center rounded-full text-white',
                              specialistColorClass(item.color)
                            )}
                          >
                            <SpecialistGlyph
                              icon={item.icon}
                              className="size-2.5"
                            />
                          </span>
                          <span className="truncate">{item.name}</span>
                          {isSelected ? (
                            <Check className="text-foreground ml-auto size-4 shrink-0" />
                          ) : null}
                        </button>
                      )
                    })}
                  </div>
                  {onCreateSpecialist ? (
                    <div className="border-t p-1">
                      <button
                        type="button"
                        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
                        onClick={() => {
                          setSpecialistPickerOpen(false)
                          onCreateSpecialist()
                        }}
                      >
                        <Plus className="size-3.5" />
                        Create new…
                      </button>
                    </div>
                  ) : null}
                </PopoverContent>
              </Popover>
            ) : null}
            {onSandboxBackendSelect ? (
              <Popover
                open={sandboxPickerOpen}
                onOpenChange={setSandboxPickerOpen}
              >
                <PopoverTrigger asChild>
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 rounded-md px-1.5 py-1 text-xs hover:bg-transparent"
                    aria-label="Sandbox backend"
                  >
                    {sandboxPhase !== 'idle' ||
                    sandboxStatus?.status === 'starting' ||
                    sandboxStatus?.status === 'stopping' ? (
                      <Loader className="text-muted-foreground size-3.5 shrink-0 animate-spin" />
                    ) : sandboxStatus?.backend === 'modal' ? (
                      <>
                        <ModalGlyph />
                        <span
                          className={cn(
                            'size-1.5 rounded-full',
                            sandboxStatusDotClass(sandboxStatus, sandboxPhase)
                          )}
                        />
                      </>
                    ) : (
                      <span
                        className={cn(
                          'size-1.5 rounded-full',
                          sandboxStatusDotClass(sandboxStatus, sandboxPhase)
                        )}
                      />
                    )}
                    <span className="font-medium">
                      {sandboxStatusLabel(sandboxStatus, sandboxPhase)}
                    </span>
                    <ChevronDown className="text-muted-foreground size-3.5" />
                  </button>
                </PopoverTrigger>
                <PopoverContent
                  align="start"
                  side="top"
                  className="w-72 overflow-hidden p-0"
                >
                  <div className="text-muted-foreground border-b px-3 py-2 text-[11px] font-medium tracking-wide uppercase">
                    Sandbox
                  </div>
                  <div className="py-1">
                    <button
                      type="button"
                      className="hover:bg-muted flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm disabled:opacity-50"
                      disabled={sandboxPhase !== 'idle'}
                      onClick={() => {
                        setSandboxPickerOpen(false)
                        void onSandboxBackendSelect('builtin')
                      }}
                    >
                      <span className="bg-muted-foreground/40 size-2.5 rounded-full" />
                      <span className="truncate">Built-in</span>
                      {sandboxStatus?.backend !== 'modal' &&
                      sandboxPhase === 'idle' ? (
                        <Check className="text-foreground ml-auto size-4 shrink-0" />
                      ) : null}
                    </button>
                    <button
                      type="button"
                      className="hover:bg-muted flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm disabled:opacity-50"
                      disabled={sandboxPhase !== 'idle'}
                      onClick={() => {
                        setSandboxPickerOpen(false)
                        void onSandboxBackendSelect('modal')
                      }}
                    >
                      <ModalGlyph />
                      <div className="min-w-0 flex-1">
                        <div className="truncate">Modal</div>
                        {sandboxStatus?.modalConfigured === false ? (
                          <div className="text-muted-foreground truncate text-[11px]">
                            Configure tokens in Integrations
                          </div>
                        ) : null}
                      </div>
                      {sandboxStatus?.backend === 'modal' ||
                      sandboxPhase !== 'idle' ? (
                        <Check className="text-foreground ml-auto size-4 shrink-0" />
                      ) : null}
                    </button>
                  </div>
                  {sandboxStatus?.backend === 'modal' ||
                  sandboxPhase !== 'idle' ? (
                    <>
                      <div className="border-t py-1">
                        <button
                          type="button"
                          className="hover:bg-muted flex w-full items-center px-3 py-1.5 text-left text-sm disabled:opacity-50"
                          disabled={
                            sandboxPhase !== 'idle' ||
                            sandboxStatus?.status === 'running' ||
                            sandboxStatus?.status === 'unavailable'
                          }
                          onClick={() => {
                            setSandboxPickerOpen(false)
                            void onSandboxStart?.()
                          }}
                        >
                          {sandboxPhase === 'starting'
                            ? 'Starting…'
                            : 'Start sandbox'}
                        </button>
                        <button
                          type="button"
                          className="hover:bg-muted flex w-full items-center px-3 py-1.5 text-left text-sm disabled:opacity-50"
                          disabled={
                            sandboxPhase !== 'idle' ||
                            sandboxStatus?.status !== 'running'
                          }
                          onClick={() => {
                            setSandboxPickerOpen(false)
                            void onSandboxStop?.()
                          }}
                        >
                          {sandboxPhase === 'stopping'
                            ? 'Stopping…'
                            : 'Stop sandbox'}
                        </button>
                        <button
                          type="button"
                          className="hover:bg-muted flex w-full items-center px-3 py-1.5 text-left text-sm disabled:opacity-50"
                          disabled={
                            sandboxPhase !== 'idle' ||
                            sandboxStatus?.status === 'unavailable'
                          }
                          onClick={() => {
                            setSandboxPickerOpen(false)
                            void onSandboxRestart?.()
                          }}
                        >
                          {sandboxPhase === 'restarting'
                            ? 'Restarting…'
                            : 'Restart sandbox'}
                        </button>
                      </div>
                      {sandboxStatus ? (
                        <div className="text-muted-foreground space-y-1.5 border-t px-3 py-2.5 text-xs">
                          <div className="flex items-center justify-between gap-3">
                            <span>Mode</span>
                            <span className="text-foreground font-medium uppercase">
                              {sandboxStatus.computeType || 'cpu'}
                            </span>
                          </div>
                          <div className="flex items-center justify-between gap-3">
                            <span>Compute</span>
                            <span className="text-foreground font-medium">
                              {sandboxStatus.computeType === 'gpu'
                                ? sandboxStatus.gpuClass
                                : `${sandboxStatus.cpuCores} CPU · ${sandboxStatus.ramGb} GB RAM`}
                            </span>
                          </div>
                          <div className="space-y-0.5">
                            <div>Base image</div>
                            <div className="text-foreground font-mono text-[11px]">
                              {sandboxStatus.cpuImage || 'debian_slim'}
                            </div>
                          </div>
                          {sandboxPhase !== 'idle' ? (
                            <div className="text-[11px] leading-snug">
                              {sandboxPhase === 'starting'
                                ? 'Starting Modal sandbox…'
                                : sandboxPhase === 'stopping'
                                  ? 'Stopping Modal sandbox…'
                                  : 'Restarting Modal sandbox…'}
                            </div>
                          ) : sandboxStatus.detail ? (
                            <div className="text-[11px] leading-snug">
                              {sandboxStatus.detail}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </>
                  ) : null}
                </PopoverContent>
              </Popover>
            ) : null}
          </div>
          <div className="flex items-center gap-1.5">
            <TooltipProvider delayDuration={200}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="relative grid size-7 place-items-center rounded-full"
                    aria-label="Context usage"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      className="size-5 -rotate-90"
                      aria-hidden
                    >
                      <circle
                        cx="12"
                        cy="12"
                        r="9"
                        fill="none"
                        stroke="hsl(var(--muted))"
                        strokeWidth="2.5"
                      />
                      <circle
                        cx="12"
                        cy="12"
                        r="9"
                        fill="none"
                        stroke="hsl(var(--foreground) / 0.7)"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeDasharray={`${usagePercent * 0.565} 56.5`}
                      />
                    </svg>
                  </button>
                </TooltipTrigger>
                <TooltipContent
                  side="top"
                  sideOffset={10}
                  className="rounded-lg px-3 py-2"
                >
                  <div className="grid min-w-44 gap-1.5 text-xs">
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-muted-foreground">Usage</span>
                      <span className="font-mono tabular-nums">
                        {Math.round(usagePercent)}%
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-muted-foreground">↑ Input</span>
                      <span className="font-mono tabular-nums">
                        {formatTokenCount(tokenUsage.inputTokens)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-muted-foreground">↓ Output</span>
                      <span className="font-mono tabular-nums">
                        {formatTokenCount(tokenUsage.outputTokens)}
                      </span>
                    </div>
                    <div className="border-border/60 mt-0.5 border-t pt-1.5">
                      <div className="flex items-center justify-between gap-4">
                        <span className="text-muted-foreground">Total</span>
                        <span className="font-mono tabular-nums">
                          {formatTokenCount(
                            tokenUsage.inputTokens + tokenUsage.outputTokens
                          )}{' '}
                          / 200k
                        </span>
                      </div>
                    </div>
                  </div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <Button
              type={running ? 'button' : 'submit'}
              size="icon"
              className="size-7 rounded-full"
              onClick={running ? onStop : undefined}
            >
              {running ? (
                <Square className="size-3 fill-current" />
              ) : (
                <ArrowUp className="size-4" />
              )}
            </Button>
          </div>
        </div>
      </form>
    </div>
  )
}
