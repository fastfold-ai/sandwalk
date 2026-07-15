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
import {
  ArrowUp,
  Check,
  ChevronDown,
  CornerDownLeft,
  Loader,
  Plug,
  Plus,
  RefreshCw,
  Sparkles,
  Square,
  X
} from 'lucide-react'
import { type KeyboardEvent, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { Link } from 'react-router-dom'

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
import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import {
  computeAtFileQuery,
  computeSlashSkillQuery,
  extractSkillOverviewFromMarkdown,
  getSkillPromptExamples
} from '@/components/agents/skill-examples'
import {
  specialistColorClass,
  SpecialistGlyph
} from '@/components/agents/SpecialistsView'
import { Button } from '@/components/ui/button'
import {
  formatModelEffortBadge,
  formatReasoningEffortLabel,
  isComposerModelSelected,
  resolveComposerModelOption,
  type ComposerModelOption
} from '@/lib/composer-models'
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
import {
  CPU_PRESETS,
  DEFAULT_CPU_PRESET,
  DEFAULT_GPU_PRESET,
  GPU_PRESETS,
  matchCpuPresetId,
  matchGpuPreset
} from '@/lib/sandbox-presets'
import { composerSkillIcon, skillIconInvertInDark } from '@/lib/skill-icons'
import {
  compareSkillsBySearchRank,
  skillMatchesSearch
} from '@/lib/skill-search'
import { cn } from '@/lib/utils'

const selectClassName =
  'border-input bg-background h-7 w-full rounded-md border px-2 text-xs disabled:cursor-not-allowed disabled:opacity-60'

export type SandboxComputeChange = {
  computeType: 'cpu' | 'gpu'
  gpuClass: string
  cpuCores: number
  ramGb: number
}

type SandboxDraft = {
  backend: 'builtin' | 'modal'
  computeType: 'cpu' | 'gpu'
  gpuClass: string
  cpuCores: number
  ramGb: number
}

function formatSandboxBytes(bytes: number): string {
  const value = Math.max(0, bytes)
  if (value < 1024) return `${value} B`
  const units = ['KB', 'MB', 'GB', 'TB'] as const
  let n = value / 1024
  for (let i = 0; i < units.length; i += 1) {
    if (n < 1024 || i === units.length - 1) {
      return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`
    }
    n /= 1024
  }
  return `${value} B`
}

function draftFromSandboxStatus(
  status: SessionSandboxStatus | null | undefined
): SandboxDraft {
  const computeType = status?.computeType === 'gpu' ? 'gpu' : 'cpu'
  const gpuPreset =
    matchGpuPreset(String(status?.gpuClass || '')) ?? DEFAULT_GPU_PRESET
  const cpuPreset =
    CPU_PRESETS.find(
      item =>
        item.id ===
        matchCpuPresetId(Number(status?.cpuCores), Number(status?.ramGb))
    ) ?? DEFAULT_CPU_PRESET
  return {
    backend: status?.backend === 'modal' ? 'modal' : 'builtin',
    computeType,
    gpuClass: gpuPreset.gpu,
    cpuCores: computeType === 'gpu' ? gpuPreset.cpu : cpuPreset.cpu,
    ramGb: computeType === 'gpu' ? gpuPreset.ram : cpuPreset.ram
  }
}

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
  if (status.backend !== 'modal') return 'Local Sandbox'
  if (status.status === 'running') return 'Modal Sandbox'
  if (status.status === 'unavailable') return 'Unavailable'
  return 'Modal Sandbox'
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

type SlashItem =
  | { kind: 'skill'; key: string; skill: AgentSkill }
  | { kind: 'mcp'; key: string; server: McpServer }

function mcpSlashKey(server: McpServer): string {
  return `mcp:${server.id}`
}

function mcpIconForServer(server: McpServer) {
  const key = String(server.catalogId || server.name || '')
    .trim()
    .toLowerCase()
  return INTEGRATION_ICONS[key] || null
}

function mcpMatchesSearch(server: McpServer, query: string): boolean {
  const needle = query.trim().toLowerCase()
  if (!needle) return true
  const haystack = [
    server.name,
    server.description || '',
    server.catalogId || '',
    server.id,
    server.transport,
    server.url || ''
  ]
    .join(' ')
    .toLowerCase()
  return haystack.includes(needle)
}

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
  const [selectedSlashKey, setSelectedSlashKey] = useState<string | null>(null)
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewOverview, setPreviewOverview] = useState<string | null>(null)
  const [auraTick, setAuraTick] = useState(0)
  const [slashDismissed, setSlashDismissed] = useState(false)
  const [atDismissed, setAtDismissed] = useState(false)
  const [modelPickerOpen, setModelPickerOpen] = useState(false)
  const [modelSearch, setModelSearch] = useState('')
  const [effortMenuOpen, setEffortMenuOpen] = useState(false)
  const [specialistPickerOpen, setSpecialistPickerOpen] = useState(false)
  const [sandboxPickerOpen, setSandboxPickerOpen] = useState(false)
  const [sandboxDraft, setSandboxDraft] = useState<SandboxDraft>(() =>
    draftFromSandboxStatus(sandboxStatus)
  )
  const [sandboxConfirming, setSandboxConfirming] = useState(false)
  const [localSystem, setLocalSystem] = useState<ServerSystemInfo | null>(null)
  const [localSystemLoading, setLocalSystemLoading] = useState(false)
  const previewCacheRef = useRef<Map<string, string>>(new Map())
  const skillItemRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const slashItemRefs = skillItemRefs
  const fileItemRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const slashListRootRef = useRef<HTMLDivElement | null>(null)
  const atListRootRef = useRef<HTMLDivElement | null>(null)

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

  useEffect(() => {
    if (!sandboxPickerOpen) return
    setSandboxDraft(draftFromSandboxStatus(sandboxStatus))
    if (!onLoadLocalSystem) {
      setLocalSystem(null)
      return
    }
    let cancelled = false
    setLocalSystemLoading(true)
    void onLoadLocalSystem()
      .then(info => {
        if (!cancelled) setLocalSystem(info)
      })
      .catch(() => {
        if (!cancelled) setLocalSystem(null)
      })
      .finally(() => {
        if (!cancelled) setLocalSystemLoading(false)
      })
    return () => {
      cancelled = true
    }
    // Snapshot draft only when the picker opens.
  }, [sandboxPickerOpen])

  const appliedSandboxBackend =
    sandboxStatus?.backend === 'modal' ? 'modal' : 'builtin'
  const sandboxDraftDirty = useMemo(() => {
    if (sandboxDraft.backend !== appliedSandboxBackend) return true
    if (sandboxDraft.backend !== 'modal') return false
    return (
      sandboxDraft.computeType !==
        (sandboxStatus?.computeType === 'gpu' ? 'gpu' : 'cpu') ||
      sandboxDraft.gpuClass !==
        (matchGpuPreset(String(sandboxStatus?.gpuClass || ''))?.gpu ??
          DEFAULT_GPU_PRESET.gpu) ||
      Number(sandboxDraft.cpuCores) !== Number(sandboxStatus?.cpuCores) ||
      Number(sandboxDraft.ramGb) !== Number(sandboxStatus?.ramGb)
    )
  }, [appliedSandboxBackend, sandboxDraft, sandboxStatus])

  async function confirmSandboxDraft() {
    if (!onSandboxBackendSelect || sandboxPhase !== 'idle' || sandboxConfirming) {
      return
    }
    setSandboxConfirming(true)
    try {
      if (sandboxDraft.backend === 'modal' && onSandboxComputeChange) {
        const computeDirty =
          sandboxDraft.computeType !==
            (sandboxStatus?.computeType === 'gpu' ? 'gpu' : 'cpu') ||
          sandboxDraft.gpuClass !==
            (matchGpuPreset(String(sandboxStatus?.gpuClass || ''))?.gpu ??
              DEFAULT_GPU_PRESET.gpu) ||
          Number(sandboxDraft.cpuCores) !== Number(sandboxStatus?.cpuCores) ||
          Number(sandboxDraft.ramGb) !== Number(sandboxStatus?.ramGb)
        if (computeDirty || sandboxDraft.backend !== appliedSandboxBackend) {
          await onSandboxComputeChange({
            computeType: sandboxDraft.computeType,
            gpuClass: sandboxDraft.gpuClass,
            cpuCores: sandboxDraft.cpuCores,
            ramGb: sandboxDraft.ramGb
          })
        }
      }
      if (sandboxDraft.backend !== appliedSandboxBackend) {
        await onSandboxBackendSelect(sandboxDraft.backend)
      }
      setSandboxPickerOpen(false)
    } finally {
      setSandboxConfirming(false)
    }
  }

  const scrollSlashItemIntoView = useCallback((key: string) => {
    const node = slashItemRefs.current.get(key)
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

  const slashResults = useMemo((): SlashItem[] => {
    if (!slash) return []
    const query = slash.query.toLowerCase().trim()
    const specialistSkillSet = selectedSpecialist
      ? new Set(
          (selectedSpecialist.skillNames || [])
            .map(name => name.trim().toLowerCase())
            .filter(Boolean)
        )
      : null
    const specialistMcpIds = selectedSpecialist
      ? new Set(
          [
            ...(selectedSpecialist.mcpServerIds || []),
            ...(selectedSpecialist.mcpCatalogIds || [])
          ]
            .map(id => id.trim())
            .filter(Boolean)
        )
      : null

    const skillItems: SlashItem[] = []
    const seenSkills = new Set<string>()
    for (const skill of skills) {
      if (!skill.enabled) continue
      if (
        specialistSkillSet &&
        !specialistSkillSet.has(skill.name.trim().toLowerCase())
      ) {
        continue
      }
      const nameKey = skill.name.trim().toLowerCase()
      if (!nameKey || seenSkills.has(nameKey)) continue
      if (!skillMatchesSearch(skill, query)) continue
      seenSkills.add(nameKey)
      skillItems.push({
        kind: 'skill',
        key: `skill:${nameKey}`,
        skill
      })
    }
    skillItems.sort((a, b) =>
      a.kind === 'skill' && b.kind === 'skill'
        ? compareSkillsBySearchRank(a.skill, b.skill, query)
        : 0
    )

    const mcpItems: SlashItem[] = []
    const seenMcps = new Set<string>()
    for (const server of mcpServers) {
      if (!server.enabled) continue
      if (specialistMcpIds && specialistMcpIds.size > 0) {
        const catalogId = String(server.catalogId || '').trim()
        if (
          !specialistMcpIds.has(server.id) &&
          !(catalogId && specialistMcpIds.has(catalogId))
        ) {
          continue
        }
      }
      if (!mcpMatchesSearch(server, query)) continue
      const key = mcpSlashKey(server)
      if (seenMcps.has(key)) continue
      seenMcps.add(key)
      mcpItems.push({ kind: 'mcp', key, server })
    }
    mcpItems.sort((a, b) => {
      if (a.kind !== 'mcp' || b.kind !== 'mcp') return 0
      return a.server.name.localeCompare(b.server.name)
    })

    // Skills first (existing muscle memory), then MCPs.
    return [...skillItems, ...mcpItems]
  }, [mcpServers, selectedSpecialist, skills, slash])

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

  const selectedSlashItem =
    slashResults.find(item => item.key === selectedSlashKey) ||
    slashResults[0] ||
    null
  const selectedSkill =
    selectedSlashItem?.kind === 'skill' ? selectedSlashItem.skill : null
  const selectedMcp =
    selectedSlashItem?.kind === 'mcp' ? selectedSlashItem.server : null
  const selectedSkillName = selectedSkill?.name ?? null
  const selectedMcpId = selectedMcp?.id ?? null

  const selectedFile =
    atResults.find(file => file.path === selectedFilePath) ||
    atResults[0] ||
    null

  useEffect(() => {
    if (!slashOpen) {
      setSelectedSlashKey(null)
      return
    }
    if (
      selectedSlashKey &&
      slashResults.some(item => item.key === selectedSlashKey)
    ) {
      return
    }
    const nextKey = slashResults[0]?.key || null
    setSelectedSlashKey(current => (current === nextKey ? current : nextKey))
  }, [selectedSlashKey, slashOpen, slashResults])

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
    const nextPath = atResults[0]?.path || null
    setSelectedFilePath(current => (current === nextPath ? current : nextPath))
  }, [atOpen, atResults, selectedFilePath])

  useEffect(() => {
    if (!slashOpen || !selectedSkillName) {
      if (!selectedMcpId) {
        setPreviewOverview(null)
        setPreviewLoading(false)
      }
      return
    }
    const fallbackDescription = selectedSkill?.description
    const cached = previewCacheRef.current.get(selectedSkillName)
    if (cached) {
      setPreviewOverview(current => (current === cached ? current : cached))
      setPreviewLoading(false)
      return
    }
    let active = true
    setPreviewLoading(true)
    void onLoadSkill(selectedSkillName)
      .then(detail => {
        if (!active) return
        const overview =
          extractSkillOverviewFromMarkdown(detail.content) ||
          cleanSkillDescription(detail.description) ||
          `Use /${detail.name} to run this skill.`
        previewCacheRef.current.set(selectedSkillName, overview)
        setPreviewOverview(overview)
      })
      .catch(() => {
        if (!active) return
        const fallback =
          cleanSkillDescription(fallbackDescription || '') ||
          `Use /${selectedSkillName} to run this skill.`
        setPreviewOverview(fallback)
      })
      .finally(() => {
        if (active) setPreviewLoading(false)
      })
    return () => {
      active = false
    }
    // selectedSkill identity changes every slashResults rebuild; key off name only.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- selectedSkillName gates the load
  }, [onLoadSkill, selectedMcpId, selectedSkillName, slashOpen])

  useEffect(() => {
    if (!slashOpen || !selectedMcpId || !selectedMcp) return
    const overview =
      String(selectedMcp.description || '').trim() ||
      `Mention mcp:${selectedMcp.name} so the agent prefers tools from this MCP server.`
    setPreviewLoading(false)
    setPreviewOverview(current => (current === overview ? current : overview))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- selectedMcpId gates the preview
  }, [selectedMcpId, slashOpen])

  const selectedModel =
    resolveComposerModelOption(modelOptions, runtimeSettings) ||
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

  const supportsReasoningEffort = Boolean(
    selectedModel.supportsReasoningEffort ||
      (selectedModel.reasoningEffortOptions &&
        selectedModel.reasoningEffortOptions.length > 0)
  )
  const selectedEffort = String(selectedModel.reasoningEffort || 'medium')
    .trim()
    .toLowerCase()
  const selectedFast = Boolean(selectedModel.reasoningFast)
  const reasoningBadge = supportsReasoningEffort
    ? formatModelEffortBadge({
        reasoningEffort: selectedEffort,
        reasoningFast: selectedFast
      })
    : null

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
    setSelectedSlashKey(null)
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
    setSelectedSlashKey(null)
  }

  const insertSlashItem = (item: SlashItem) => {
    if (item.kind === 'skill') insertSkillChip(item.skill)
    else insertMcpChip(item.server)
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
    setSelectedFilePath(null)
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
    setSelectedSlashKey(null)
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

  useEffect(() => {
    if (!slashOpen || !selectedSlashItem) return
    scrollSlashItemIntoView(selectedSlashItem.key)
  }, [scrollSlashItemIntoView, selectedSlashItem?.key, slashOpen])

  useEffect(() => {
    if (!atOpen || !selectedFile) return
    scrollFileIntoView(selectedFile.path)
  }, [atOpen, scrollFileIntoView, selectedFile?.path])

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
      setSelectedSlashKey(null)
      return
    }
    if (slashOpen && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
      event.preventDefault()
      event.stopPropagation()
      if (slashResults.length === 0) return
      const currentIndex = slashResults.findIndex(
        item => item.key === selectedSlashItem?.key
      )
      const safeIndex = currentIndex < 0 ? 0 : currentIndex
      const nextIndex =
        event.key === 'ArrowDown'
          ? Math.min(safeIndex + 1, slashResults.length - 1)
          : Math.max(safeIndex - 1, 0)
      const nextKey = slashResults[nextIndex]?.key
      if (!nextKey) return
      setSelectedSlashKey(nextKey)
      window.requestAnimationFrame(() => {
        focusActiveComposerInput()
        scrollSlashItemIntoView(nextKey)
      })
      return
    }
    if (slashOpen && event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (selectedSlashItem) insertSlashItem(selectedSlashItem)
      return
    }
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
              Showing skills & MCPs for{' '}
              <span className="text-foreground font-medium">
                {selectedSpecialist.name}
              </span>
            </div>
          ) : null}
          <div className="grid h-72 grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div ref={slashListRootRef} className="min-h-0 min-w-0">
              <ScrollArea className="border-border/60 h-72 border-r">
                <div className="p-1" role="listbox" aria-label="Skills and MCPs">
                  {slashResults.length > 0 ? (
                    slashResults.map(item => {
                      const isSelected = selectedSlashItem?.key === item.key
                      if (item.kind === 'mcp') {
                        const { server } = item
                        const description =
                          String(server.description || '').trim() ||
                          server.transport
                        const icon = mcpIconForServer(server)
                        return (
                          <button
                            key={item.key}
                            type="button"
                            tabIndex={-1}
                            role="option"
                            aria-selected={isSelected}
                            ref={node => {
                              if (node) slashItemRefs.current.set(item.key, node)
                              else slashItemRefs.current.delete(item.key)
                            }}
                            onMouseDown={event => event.preventDefault()}
                            onMouseEnter={() => setSelectedSlashKey(item.key)}
                            onClick={() => {
                              insertMcpChip(server)
                            }}
                            className={cn(
                              'hover:bg-muted flex w-full flex-col rounded-md px-2 py-1.5 text-left',
                              isSelected && 'bg-muted'
                            )}
                          >
                            <span className="flex min-w-0 items-center gap-2">
                              {icon ? (
                                <img
                                  src={icon.src}
                                  alt=""
                                  className={cn(
                                    'size-[18px] shrink-0 rounded object-contain',
                                    icon.invertInDark && 'dark:invert'
                                  )}
                                />
                              ) : (
                                <span className="bg-muted text-muted-foreground inline-flex size-[18px] shrink-0 items-center justify-center rounded">
                                  <Plug className="size-3" />
                                </span>
                              )}
                              <span className="truncate text-sm font-medium">
                                {server.name}
                              </span>
                            </span>
                            <span className="text-muted-foreground truncate text-xs">
                              {description}
                            </span>
                            <span className="text-muted-foreground/70 truncate text-[10px]">
                              {[server.transport, server.catalogId || 'custom']
                                .filter(Boolean)
                                .join(' · ')}
                            </span>
                          </button>
                        )
                      }

                      const { skill } = item
                      const description =
                        cleanSkillDescription(skill.description) || skill.name
                      const iconSource = composerSkillIcon(skill)
                      return (
                        <button
                          key={item.key}
                          type="button"
                          tabIndex={-1}
                          role="option"
                          aria-selected={isSelected}
                          ref={node => {
                            if (node) slashItemRefs.current.set(item.key, node)
                            else slashItemRefs.current.delete(item.key)
                          }}
                          onMouseDown={event => event.preventDefault()}
                          onMouseEnter={() => setSelectedSlashKey(item.key)}
                          onClick={() => {
                            insertSkillChip(skill)
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
                              {skill.name}
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
                        ? `No matching skills or MCPs for ${selectedSpecialist.name}`
                        : 'No skills or MCPs found'}
                    </div>
                  )}
                </div>
              </ScrollArea>
            </div>
            <ScrollArea className="h-72">
              <div className="px-1 py-1">
                {selectedMcp ? (
                  <div className="space-y-3 px-2 py-1">
                    <div className="flex items-start justify-between gap-2">
                      <span className="truncate text-sm font-semibold">
                        {selectedMcp.name}
                      </span>
                      <a
                        href={
                          selectedMcp.catalogId
                            ? `/dashboard/mcp/catalog/${encodeURIComponent(
                                selectedMcp.catalogId
                              )}`
                            : `/dashboard/mcp/server/${encodeURIComponent(
                                selectedMcp.id
                              )}`
                        }
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary shrink-0 text-[11px] font-medium hover:underline"
                        onMouseDown={event => event.preventDefault()}
                      >
                        Read more
                      </a>
                    </div>
                    <p className="text-muted-foreground line-clamp-5 text-[11px] leading-relaxed">
                      {previewOverview ||
                        `Mention mcp:${selectedMcp.name} so the agent prefers tools from this MCP server.`}
                    </p>
                    <div className="border-border/60 border-t pt-2">
                      <p className="text-muted-foreground mb-1 text-[10px] font-semibold uppercase tracking-wide">
                        Insert
                      </p>
                      <button
                        type="button"
                        tabIndex={-1}
                        onMouseDown={event => event.preventDefault()}
                        onClick={() => insertMcpChip(selectedMcp)}
                        className="hover:bg-muted/50 border-border/60 bg-background w-full rounded-md border px-2 py-1.5 text-left"
                      >
                        <span className="flex items-center justify-between gap-2">
                          <span className="block truncate text-[11px] font-medium">
                            Mention this MCP
                          </span>
                          <span className="border-primary/30 text-primary inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium">
                            Insert
                            <CornerDownLeft className="h-3 w-3" />
                          </span>
                        </span>
                        <span className="text-muted-foreground mt-0.5 line-clamp-2 block text-[10px]">
                          Adds mcp:{selectedMcp.name} so the agent can prioritize
                          its tools.
                        </span>
                      </button>
                    </div>
                  </div>
                ) : selectedSkill ? (
                  <div className="space-y-3 px-2 py-1">
                    <div className="flex items-start justify-between gap-2">
                      <span className="truncate text-sm font-semibold">
                        {selectedSkill.name}
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
                    Select a skill or MCP to preview.
                  </div>
                )}
              </div>
            </ScrollArea>
          </div>
        </div>
      ) : null}

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
            <Popover
              open={modelPickerOpen}
              onOpenChange={open => {
                setModelPickerOpen(open)
                if (!open) {
                  setModelSearch('')
                  setEffortMenuOpen(false)
                }
              }}
            >
              <PopoverTrigger asChild>
                <button
                  type="button"
                  title={`${selectedModel.label}${selectedModel.speed ? ` · ${selectedModel.speed}` : ''}${reasoningBadge ? ` · ${reasoningBadge}` : ''}`}
                  className="text-muted-foreground hover:text-foreground inline-flex min-w-0 max-w-[min(100%,20rem)] items-center gap-1 rounded-md px-1.5 py-1 text-xs hover:bg-transparent"
                >
                  <span className="min-w-0 truncate font-medium">
                    {selectedModel.label}
                  </span>
                  {reasoningBadge ? (
                    <span className="text-muted-foreground shrink-0 text-[11px]">
                      {reasoningBadge}
                    </span>
                  ) : selectedModel.speed ? (
                    <span className="text-muted-foreground shrink-0 text-[11px]">
                      {selectedModel.speed}
                    </span>
                  ) : null}
                  <ChevronDown className="text-muted-foreground size-3.5 shrink-0" />
                </button>
              </PopoverTrigger>
              <PopoverContent
                align="start"
                side="top"
                className="w-[min(28rem,calc(100vw-2rem))] overflow-visible p-0"
                onCloseAutoFocus={event => event.preventDefault()}
                onInteractOutside={event => {
                  // Nested Edit panel is portaled; don't dismiss the model list.
                  if (effortMenuOpen) event.preventDefault()
                }}
                onFocusOutside={event => {
                  if (effortMenuOpen) event.preventDefault()
                }}
                onPointerDownOutside={event => {
                  if (effortMenuOpen) event.preventDefault()
                }}
              >
                <div className="bg-popover overflow-hidden rounded-md border-0">
                  <div className="bg-popover border-b px-3 py-2">
                    <Input
                      value={modelSearch}
                      onChange={event => setModelSearch(event.target.value)}
                      placeholder="Search models"
                      className="h-7 border-0 bg-transparent px-0 text-sm shadow-none focus-visible:ring-0"
                      autoFocus
                    />
                  </div>
                  <ScrollArea className="h-72 w-full">
                    <div className="w-full py-1">
                      {modelOptions.length === 0 ? (
                        <div className="text-muted-foreground px-3 py-3 text-sm">
                          No enabled models. Turn models on in Dashboard →
                          Models.
                        </div>
                      ) : filteredModelOptions.length === 0 ? (
                        <div className="text-muted-foreground px-3 py-3 text-sm">
                          No models match “{modelSearch.trim()}”.
                        </div>
                      ) : (
                        filteredModelOptions.map(option => {
                          const isSelected = isComposerModelSelected(
                            option,
                            runtimeSettings,
                            modelOptions
                          )
                          const optionSupportsEffort = Boolean(
                            option.supportsReasoningEffort ||
                              (option.reasoningEffortOptions &&
                                option.reasoningEffortOptions.length > 0)
                          )
                          const optionEffortOptions =
                            option.reasoningEffortOptions &&
                            option.reasoningEffortOptions.length > 0
                              ? option.reasoningEffortOptions
                              : ['low', 'medium', 'high']
                          const optionEffort = String(
                            option.reasoningEffort || 'medium'
                          )
                            .trim()
                            .toLowerCase()
                          const optionFast = Boolean(option.reasoningFast)
                          const optionEffortLabel = formatModelEffortBadge({
                            reasoningEffort: optionEffort,
                            reasoningFast: optionFast
                          })
                          const selectModel = () => {
                            void onModelSelect(
                              option.provider,
                              option.model,
                              option.profileId
                            )
                            setModelSearch('')
                            if (!optionSupportsEffort) {
                              setEffortMenuOpen(false)
                            }
                          }
                          return (
                            <div
                              key={`${option.source || option.provider}:${option.profileId || 'cloud'}:${option.model}`}
                              className={cn(
                                'hover:bg-muted group relative flex w-full items-center gap-2 px-3 py-1.5 text-sm',
                                isSelected && 'bg-muted'
                              )}
                            >
                              <button
                                type="button"
                                title={`${option.label}${
                                  optionSupportsEffort
                                    ? ` ${optionEffortLabel}`
                                    : option.speed
                                      ? ` · ${option.speed}`
                                      : ''
                                }`}
                                className="absolute inset-0 z-0"
                                aria-label={`Select ${option.label}`}
                                onClick={selectModel}
                              />
                              <span className="pointer-events-none flex min-w-0 flex-1 items-baseline gap-1.5 truncate text-left">
                                <span className="text-foreground truncate">
                                  {option.label}
                                </span>
                                {optionSupportsEffort ? (
                                  <span className="text-muted-foreground shrink-0 text-[11px]">
                                    {optionEffortLabel}
                                  </span>
                                ) : null}
                              </span>
                              <div className="relative z-10 flex shrink-0 items-center gap-2">
                                {optionSupportsEffort &&
                                onReasoningSettingsChange ? (
                                  isSelected ? (
                                    <Popover
                                      modal={false}
                                      open={effortMenuOpen}
                                      onOpenChange={setEffortMenuOpen}
                                    >
                                      <PopoverTrigger asChild>
                                        <button
                                          type="button"
                                          className="text-muted-foreground hover:text-foreground text-xs font-medium opacity-100"
                                          onClick={event => {
                                            event.stopPropagation()
                                          }}
                                        >
                                          Edit
                                        </button>
                                      </PopoverTrigger>
                                      <PopoverContent
                                        side="right"
                                        align="start"
                                        sideOffset={10}
                                        className="w-44 overflow-hidden p-0"
                                        onOpenAutoFocus={event =>
                                          event.preventDefault()
                                        }
                                        onCloseAutoFocus={event =>
                                          event.preventDefault()
                                        }
                                      >
                                        <div className="text-muted-foreground border-b px-3 py-2 text-[11px] font-medium tracking-wide uppercase">
                                          Effort
                                        </div>
                                        <div className="py-1">
                                          {optionEffortOptions.map(level => {
                                            const active = optionEffort === level
                                            return (
                                              <button
                                                key={level}
                                                type="button"
                                                className="hover:bg-muted flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm"
                                                onClick={event => {
                                                  event.preventDefault()
                                                  event.stopPropagation()
                                                  void onReasoningSettingsChange(
                                                    {
                                                      provider: option.provider,
                                                      model: option.model,
                                                      reasoningEffort: level
                                                    }
                                                  )
                                                }}
                                              >
                                                <span className="truncate">
                                                  {formatReasoningEffortLabel(
                                                    level
                                                  )}
                                                </span>
                                                {active ? (
                                                  <Check className="text-foreground ml-auto size-4 shrink-0" />
                                                ) : null}
                                              </button>
                                            )
                                          })}
                                        </div>
                                        <div className="text-muted-foreground border-t px-3 py-2 text-[11px] font-medium tracking-wide uppercase">
                                          Options
                                        </div>
                                        <div className="flex items-center justify-between gap-3 px-3 py-2.5">
                                          <span className="text-sm font-medium">
                                            Fast
                                          </span>
                                          <button
                                            type="button"
                                            role="switch"
                                            aria-checked={optionFast}
                                            aria-label="Fast mode"
                                            className={cn(
                                              'relative h-5 w-9 shrink-0 rounded-full transition-colors',
                                              optionFast
                                                ? 'bg-primary'
                                                : 'bg-muted-foreground/30'
                                            )}
                                            onClick={event => {
                                              event.preventDefault()
                                              event.stopPropagation()
                                              void onReasoningSettingsChange({
                                                provider: option.provider,
                                                model: option.model,
                                                reasoningFast: !optionFast
                                              })
                                            }}
                                          >
                                            <span
                                              className={cn(
                                                'bg-background pointer-events-none absolute top-0.5 left-0.5 size-4 rounded-full border border-black/5 shadow-sm transition-transform',
                                                optionFast && 'translate-x-4'
                                              )}
                                            />
                                          </button>
                                        </div>
                                      </PopoverContent>
                                    </Popover>
                                  ) : (
                                    <button
                                      type="button"
                                      className="text-muted-foreground hover:text-foreground text-xs font-medium opacity-0 transition-opacity group-hover:opacity-100"
                                      onClick={event => {
                                        event.preventDefault()
                                        event.stopPropagation()
                                        void (async () => {
                                          await onModelSelect(
                                            option.provider,
                                            option.model,
                                            option.profileId
                                          )
                                          setModelSearch('')
                                          setEffortMenuOpen(true)
                                        })()
                                      }}
                                    >
                                      Edit
                                    </button>
                                  )
                                ) : null}
                                {option.speed &&
                                !isSelected &&
                                !optionSupportsEffort ? (
                                  <span className="text-muted-foreground pointer-events-none text-xs whitespace-nowrap">
                                    {option.speed}
                                  </span>
                                ) : null}
                                {isSelected ? (
                                  <Check className="text-foreground pointer-events-none size-4 shrink-0" />
                                ) : null}
                              </div>
                            </div>
                          )
                        })
                      )}
                    </div>
                  </ScrollArea>
                  {onAddModels ? (
                    <div className="border-t p-1">
                      <button
                        type="button"
                        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
                        onClick={() => {
                          setModelPickerOpen(false)
                          setModelSearch('')
                          setEffortMenuOpen(false)
                          onAddModels()
                        }}
                      >
                        <Plus className="size-3.5 shrink-0" />
                        Add Models
                      </button>
                    </div>
                  ) : null}
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
                    className="text-muted-foreground hover:text-foreground inline-flex shrink-0 items-center gap-1.5 rounded-md px-1.5 py-1 text-xs hover:bg-transparent"
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
                    <span className="max-w-[7rem] truncate font-medium">
                      {selectedSpecialist?.name || 'None'}
                    </span>
                    <ChevronDown className="text-muted-foreground size-3.5 shrink-0" />
                  </button>
                </PopoverTrigger>
                <PopoverContent
                  align="start"
                  side="top"
                  className="w-64 overflow-hidden p-0"
                  onCloseAutoFocus={event => event.preventDefault()}
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
                    className="text-muted-foreground hover:text-foreground inline-flex shrink-0 items-center gap-1.5 rounded-md px-1.5 py-1 text-xs hover:bg-transparent"
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
                  sideOffset={6}
                  className="w-[16.5rem] overflow-hidden p-0"
                  onOpenAutoFocus={event => event.preventDefault()}
                  onCloseAutoFocus={event => event.preventDefault()}
                >
                  <div className="flex items-center justify-between gap-2 border-b px-2.5 py-1.5">
                    <span className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
                      Sandbox
                    </span>
                    <Link
                      to="/dashboard/agent/sandbox"
                      className="text-muted-foreground hover:text-foreground text-[10px] font-medium underline-offset-2 hover:underline"
                      onClick={() => setSandboxPickerOpen(false)}
                    >
                      Settings
                    </Link>
                  </div>
                  <div className="space-y-1.5 p-2">
                    <div className="inline-flex w-full rounded-md border p-0.5">
                      <button
                        type="button"
                        disabled={sandboxPhase !== 'idle' || sandboxConfirming}
                        onClick={() =>
                          setSandboxDraft(current => ({
                            ...current,
                            backend: 'builtin'
                          }))
                        }
                        className={cn(
                          'flex flex-1 items-center justify-center gap-1 rounded px-1.5 py-1 text-[11px] font-medium transition-colors',
                          sandboxDraft.backend === 'builtin'
                            ? 'bg-background text-foreground shadow-sm'
                            : 'text-muted-foreground hover:text-foreground',
                          (sandboxPhase !== 'idle' || sandboxConfirming) &&
                            'cursor-not-allowed opacity-60'
                        )}
                      >
                        <span className="bg-muted-foreground/40 size-1.5 rounded-full" />
                        Local
                      </button>
                      {sandboxStatus?.modalConfigured !== true ? (
                        <div className="text-muted-foreground flex flex-1 items-center justify-center gap-1 rounded px-1.5 py-1 text-[11px] opacity-60">
                          <ModalGlyph className="size-3 opacity-70" />
                          Modal
                        </div>
                      ) : (
                        <button
                          type="button"
                          disabled={
                            sandboxPhase !== 'idle' || sandboxConfirming
                          }
                          onClick={() =>
                            setSandboxDraft(current => ({
                              ...current,
                              backend: 'modal'
                            }))
                          }
                          className={cn(
                            'flex flex-1 items-center justify-center gap-1 rounded px-1.5 py-1 text-[11px] font-medium transition-colors',
                            sandboxDraft.backend === 'modal'
                              ? 'bg-background text-foreground shadow-sm'
                              : 'text-muted-foreground hover:text-foreground',
                            (sandboxPhase !== 'idle' || sandboxConfirming) &&
                              'cursor-not-allowed opacity-60'
                          )}
                        >
                          <ModalGlyph className="size-3" />
                          Modal
                        </button>
                      )}
                    </div>

                      {sandboxStatus?.modalConfigured !== true ? (
                        <p className="text-muted-foreground px-0.5 text-[10px] leading-snug">
                          Modal not set up.{' '}
                          <Link
                            to="/dashboard/integrations/modal"
                            className="text-foreground font-medium underline underline-offset-2"
                            onClick={() => setSandboxPickerOpen(false)}
                          >
                            Set up
                          </Link>
                        </p>
                      ) : null}

                      {sandboxDraft.backend === 'builtin' ? (
                        <div className="bg-muted/30 space-y-1 rounded-md border border-border/60 px-2 py-1.5 text-[10px]">
                          <p className="text-muted-foreground font-medium tracking-wide uppercase">
                            This machine
                          </p>
                          {localSystemLoading && !localSystem ? (
                            <p className="text-muted-foreground">
                              Loading system info…
                            </p>
                          ) : localSystem ? (
                            <div className="text-foreground space-y-0.5">
                              <div className="flex items-start justify-between gap-2">
                                <span className="text-muted-foreground">
                                  Chip
                                </span>
                                <span className="min-w-0 text-right leading-snug">
                                  {localSystem.chipName?.trim() ||
                                    localSystem.label ||
                                    `${localSystem.platform} · ${localSystem.arch}`}
                                </span>
                              </div>
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-muted-foreground">
                                  RAM
                                </span>
                                <span className="tabular-nums">
                                  {formatSandboxBytes(localSystem.ramUsedBytes)}{' '}
                                  /{' '}
                                  {formatSandboxBytes(localSystem.ramTotalBytes)}
                                </span>
                              </div>
                              {localSystem.gpuCores != null ? (
                                <div className="flex items-center justify-between gap-2">
                                  <span className="text-muted-foreground">
                                    GPU cores
                                  </span>
                                  <span className="tabular-nums">
                                    {localSystem.gpuCores}
                                  </span>
                                </div>
                              ) : null}
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-muted-foreground">
                                  Arch
                                </span>
                                <span className="truncate">
                                  {localSystem.arch}
                                  {localSystem.osVersion
                                    ? ` · ${localSystem.osVersion}`
                                    : ''}
                                </span>
                              </div>
                            </div>
                          ) : (
                            <p className="text-muted-foreground">
                              Local Python environment on this computer.
                            </p>
                          )}
                        </div>
                      ) : null}

                      {sandboxDraft.backend === 'modal' &&
                      sandboxStatus?.modalConfigured === true ? (
                        <>
                          <div className="text-muted-foreground flex items-center justify-between gap-2 px-0.5 text-[10px]">
                            <span>Mode</span>
                            <div className="inline-flex rounded border p-0.5">
                              <button
                                type="button"
                                disabled={
                                  sandboxPhase !== 'idle' || sandboxConfirming
                                }
                                onClick={() => {
                                  const preset =
                                    CPU_PRESETS.find(
                                      item =>
                                        item.id ===
                                        matchCpuPresetId(
                                          sandboxDraft.cpuCores,
                                          sandboxDraft.ramGb
                                        )
                                    ) ?? DEFAULT_CPU_PRESET
                                  setSandboxDraft(current => ({
                                    ...current,
                                    computeType: 'cpu',
                                    cpuCores: preset.cpu,
                                    ramGb: preset.ram
                                  }))
                                }}
                                className={cn(
                                  'rounded px-1.5 py-0.5 text-[10px] font-medium',
                                  sandboxDraft.computeType !== 'gpu'
                                    ? 'bg-background text-foreground shadow-sm'
                                    : 'text-muted-foreground hover:text-foreground',
                                  (sandboxPhase !== 'idle' ||
                                    sandboxConfirming) &&
                                    'cursor-not-allowed opacity-60'
                                )}
                              >
                                CPU
                              </button>
                              <button
                                type="button"
                                disabled={
                                  sandboxPhase !== 'idle' || sandboxConfirming
                                }
                                onClick={() => {
                                  const preset =
                                    matchGpuPreset(sandboxDraft.gpuClass) ??
                                    DEFAULT_GPU_PRESET
                                  setSandboxDraft(current => ({
                                    ...current,
                                    computeType: 'gpu',
                                    gpuClass: preset.gpu,
                                    cpuCores: preset.cpu,
                                    ramGb: preset.ram
                                  }))
                                }}
                                className={cn(
                                  'rounded px-1.5 py-0.5 text-[10px] font-medium',
                                  sandboxDraft.computeType === 'gpu'
                                    ? 'bg-background text-foreground shadow-sm'
                                    : 'text-muted-foreground hover:text-foreground',
                                  (sandboxPhase !== 'idle' ||
                                    sandboxConfirming) &&
                                    'cursor-not-allowed opacity-60'
                                )}
                              >
                                GPU
                              </button>
                            </div>
                          </div>

                          <div className="text-muted-foreground space-y-1 px-0.5 text-[10px]">
                            <div className="flex items-center justify-between gap-2">
                              <span>Compute</span>
                            </div>
                            {sandboxDraft.computeType === 'gpu' ? (
                              <select
                                className={selectClassName}
                                disabled={
                                  sandboxPhase !== 'idle' || sandboxConfirming
                                }
                                value={
                                  matchGpuPreset(sandboxDraft.gpuClass)?.gpu ??
                                  DEFAULT_GPU_PRESET.gpu
                                }
                                onChange={event => {
                                  const preset =
                                    matchGpuPreset(event.target.value) ??
                                    DEFAULT_GPU_PRESET
                                  setSandboxDraft(current => ({
                                    ...current,
                                    computeType: 'gpu',
                                    gpuClass: preset.gpu,
                                    cpuCores: preset.cpu,
                                    ramGb: preset.ram
                                  }))
                                }}
                              >
                                {GPU_PRESETS.map(preset => (
                                  <option key={preset.gpu} value={preset.gpu}>
                                    {preset.shortLabel}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <select
                                className={selectClassName}
                                disabled={
                                  sandboxPhase !== 'idle' || sandboxConfirming
                                }
                                value={
                                  matchCpuPresetId(
                                    sandboxDraft.cpuCores,
                                    sandboxDraft.ramGb
                                  ) ?? 'custom'
                                }
                                onChange={event => {
                                  if (event.target.value === 'custom') return
                                  const preset =
                                    CPU_PRESETS.find(
                                      item => item.id === event.target.value
                                    ) ?? DEFAULT_CPU_PRESET
                                  setSandboxDraft(current => ({
                                    ...current,
                                    computeType: 'cpu',
                                    cpuCores: preset.cpu,
                                    ramGb: preset.ram
                                  }))
                                }}
                              >
                                {CPU_PRESETS.map(preset => (
                                  <option key={preset.id} value={preset.id}>
                                    {preset.shortLabel}
                                  </option>
                                ))}
                                {matchCpuPresetId(
                                  sandboxDraft.cpuCores,
                                  sandboxDraft.ramGb
                                ) === null ? (
                                  <option value="custom">
                                    {sandboxDraft.cpuCores} CPU ·{' '}
                                    {sandboxDraft.ramGb} GB
                                  </option>
                                ) : null}
                              </select>
                            )}
                          </div>

                          <div className="text-muted-foreground space-y-0.5 px-0.5 text-[10px]">
                            <span>Base image</span>
                            <div className="text-foreground truncate font-mono text-[10px]">
                              {sandboxStatus?.cpuImage || 'python:3.12-slim'}
                            </div>
                          </div>
                        </>
                      ) : null}

                      <div className="flex items-center gap-1 pt-0.5">
                        <Button
                          type="button"
                          size="sm"
                          className="h-7 flex-1 px-2 text-[11px]"
                          disabled={
                            sandboxPhase !== 'idle' ||
                            sandboxConfirming ||
                            !sandboxDraftDirty ||
                            (sandboxDraft.backend === 'modal' &&
                              sandboxStatus?.modalConfigured !== true)
                          }
                          onClick={() => void confirmSandboxDraft()}
                        >
                          {sandboxConfirming ? (
                            <>
                              <Loader className="size-3 animate-spin" />
                              Applying…
                            </>
                          ) : (
                            'Confirm'
                          )}
                        </Button>

                        {sandboxDraft.backend === 'modal' &&
                        sandboxStatus?.modalConfigured === true &&
                        appliedSandboxBackend === 'modal' ? (
                          sandboxPhase !== 'idle' ||
                          sandboxStatus.status === 'starting' ||
                          sandboxStatus.status === 'stopping' ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="secondary"
                              className="h-7 px-2 text-[11px]"
                              disabled
                            >
                              <Loader className="size-3 animate-spin" />
                            </Button>
                          ) : sandboxStatus.status === 'running' ? (
                            <>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="text-destructive hover:text-destructive h-7 px-2 text-[11px]"
                                onClick={() => void onSandboxStop?.()}
                              >
                                Stop
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="secondary"
                                className="h-7 px-2"
                                aria-label="Restart sandbox"
                                onClick={() => void onSandboxRestart?.()}
                              >
                                <RefreshCw className="size-3" />
                              </Button>
                            </>
                          ) : (
                            <Button
                              type="button"
                              size="sm"
                              variant="secondary"
                              className="h-7 px-2 text-[11px]"
                              disabled={
                                sandboxStatus.status === 'unavailable' ||
                                !onSandboxStart ||
                                sandboxConfirming
                              }
                              onClick={() => void onSandboxStart?.()}
                            >
                              Start
                            </Button>
                          )
                        ) : null}
                      </div>

                      {sandboxStatus?.detail &&
                      sandboxStatus.status !== 'running' &&
                      appliedSandboxBackend === 'modal' ? (
                        <p className="text-muted-foreground px-0.5 text-[10px] leading-snug">
                          {sandboxStatus.detail}
                        </p>
                      ) : null}
                    </div>
                  </PopoverContent>
              </Popover>
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
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
