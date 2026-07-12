import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentCatalogSkill,
  AgentCatalogSkillAudit,
  AgentCatalogSkillDetail,
  AgentEvent,
  AgentMessage,
  AgentProject,
  AgentSession,
  AgentSkill,
  AgentSkillBatchAction,
  AgentSkillBatchResult,
  AgentSkillDetail,
  AgentSkillSource,
  AgentTodo,
  BackendHealth,
  IntegrationSetupResult,
  IntegrationSummary,
  McpCatalogEntry,
  McpServer,
  RuntimeSettings,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import {
  Archive,
  ArrowLeft,
  Box,
  CalendarDays,
  Check,
  ChevronDown,
  ChevronRight,
  CircleCheck,
  Copy,
  Download,
  Folder,
  GitBranch,
  LayoutDashboard,
  Loader,
  Loader2,
  MoreHorizontal,
  PanelLeft,
  PanelRight,
  Pencil,
  Pin,
  Plus,
  Search,
  Send,
  SquareTerminal,
  Tag,
  Terminal,
  Trash2,
  Upload,
  UserRound,
  Webhook
} from 'lucide-react'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import { matchPath, useLocation, useNavigate } from 'react-router-dom'

import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import { Composer } from '@/components/agents/Composer'
import { LoginView } from '@/components/agents/LoginView'
import {
  composerToMessage,
  fileChipToken
} from '@/components/agents/composer-parts'
import {
  type DashboardSection,
  DashboardSidebar} from '@/components/agents/DashboardSidebar'
import { DataView } from '@/components/agents/DataView'
import { DoctorView } from '@/components/agents/DoctorView'
import { EnvironmentView } from '@/components/agents/EnvironmentView'
import { GeneralView } from '@/components/agents/GeneralView'
import { McpView } from '@/components/agents/McpView'
import { ModelsView } from '@/components/agents/ModelsView'
import { SandwalkMark } from '@/components/SandwalkMark'
import { ServerStatusView } from '@/components/agents/ServerStatusView'
import { StorageView } from '@/components/agents/StorageView'
import { ToolsView } from '@/components/agents/ToolsView'
import {
  GlobalSearchDialog,
  useGlobalSearchHotkey
} from '@/components/agents/GlobalSearchDialog'
import { MarkdownContent } from '@/components/agents/MarkdownContent'
import { NewProjectDialog } from '@/components/agents/NewProjectDialog'
import { ProjectPicker } from '@/components/agents/ProjectPicker'
import { ProjectSelector } from '@/components/agents/ProjectSelector'
import { ProjectSettingsDialog } from '@/components/agents/ProjectSettingsDialog'
import { ReasoningGhost } from '@/components/agents/ReasoningGhost'
import { SessionActivityHeatmap } from '@/components/agents/SessionActivityHeatmap'
import { SessionTabs } from '@/components/agents/SessionTabs'
import { SidebarUserMenu } from '@/components/agents/SidebarUserMenu'
import { TerminalPanel } from '@/components/agents/TerminalPanel'
import { TodoListInline } from '@/components/agents/TodoListInline'
import { ToolCard, type TranscriptTool } from '@/components/agents/ToolCard'
import { toast } from 'sonner'
import {
  CardGridSkeleton,
  ChatPageSkeleton,
  DetailPageSkeleton,
  ListRowsSkeleton
} from '@/components/agents/PageSkeletons'
import {
  buildConversationTimeline,
  thoughtDurationForTools,
  TOOL_RUN_VISIBLE_COUNT
} from '@/components/agents/transcript'
import { UserMessageContent } from '@/components/agents/UserMessageContent'
import { WorkspacePanel } from '@/components/agents/WorkspacePanel'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import {
  featuredSkillIcon,
  isFeaturedSkill,
  skillIcon
} from '@/lib/skill-icons'
import {
  compareSkillsBySearchRank,
  skillMatchesSearch
} from '@/lib/skill-search'

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8787'
/** Soft warn: live SSE streams start crowding the browser's ~6 conn/host limit. */
const CONCURRENT_RUN_SOFT_LIMIT = 3
/** Hard confirm: starting another run is likely to stall files/chat. */
const CONCURRENT_RUN_HARD_LIMIT = 5
const SIDEBAR_COLLAPSED_STORAGE_KEY =
  'agent-ide-v2-assistant-ui-base-sidebar-collapsed'
const FILES_PANEL_COLLAPSED_STORAGE_KEY =
  'agent-ide-v2-assistant-ui-base-files-panel-collapsed'
const SHELL_PANELS_AUTO_SAVE_ID = 'fastfold.shell-panels'
const SESSION_PANELS_AUTO_SAVE_ID = 'fastfold.session-panels'
const TERMINAL_OPEN_STORAGE_KEY = 'fastfold.terminal-open'
const OPEN_SESSION_TABS_STORAGE_KEY = 'fastfold.open-session-tabs-by-project'
const OPEN_SESSION_TABS_LEGACY_KEY = 'fastfold.open-session-tabs'
const ALL_PROJECTS_TABS_KEY = '__all__'
const PROJECT_SCOPE_STORAGE_KEY = 'fastfold.project-scope-id'
const LAST_SESSION_BY_SCOPE_KEY = 'fastfold.last-session-by-scope'
const RECENT_PROJECT_IDS_STORAGE_KEY = 'fastfold.recent-project-ids'
const SIDEBAR_SECTIONS_COLLAPSED_KEY = 'fastfold.sidebar-sections-collapsed'

/** Relative in-app path only (blocks open redirects). */
function sanitizeAuthReturnTo(path: string | null | undefined): string | null {
  if (!path) return null
  const trimmed = path.trim()
  if (!trimmed.startsWith('/') || trimmed.startsWith('//')) return null
  if (trimmed === '/' || trimmed === '/login' || trimmed.startsWith('/login?')) {
    return null
  }
  return trimmed
}

function loginPathWithNext(returnTo: string | null): string {
  const safe = sanitizeAuthReturnTo(returnTo)
  if (!safe) return '/'
  return `/?next=${encodeURIComponent(safe)}`
}

function nextFromSearch(search: string): string | null {
  const raw = new URLSearchParams(search).get('next')
  return sanitizeAuthReturnTo(raw)
}

function projectTabsKey(projectId: string | null | undefined) {
  return projectId || ALL_PROJECTS_TABS_KEY
}

function readOpenTabsByProject(): Record<string, string[]> {
  try {
    const raw = localStorage.getItem(OPEN_SESSION_TABS_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as unknown
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        const result: Record<string, string[]> = {}
        for (const [key, value] of Object.entries(
          parsed as Record<string, unknown>
        )) {
          if (!Array.isArray(value)) continue
          result[key] = value.filter(
            (id): id is string => typeof id === 'string' && id.length > 0
          )
        }
        return result
      }
    }
    const legacy = localStorage.getItem(OPEN_SESSION_TABS_LEGACY_KEY)
    if (!legacy) return {}
    const parsed = JSON.parse(legacy) as unknown
    if (!Array.isArray(parsed)) return {}
    const ids = parsed.filter(
      (id): id is string => typeof id === 'string' && id.length > 0
    )
    return ids.length > 0 ? { [ALL_PROJECTS_TABS_KEY]: ids } : {}
  } catch {
    return {}
  }
}

function writeOpenTabsByProject(map: Record<string, string[]>) {
  try {
    localStorage.setItem(OPEN_SESSION_TABS_STORAGE_KEY, JSON.stringify(map))
  } catch {
    // ignore storage failures
  }
}

function readProjectScopeId(): string | null {
  try {
    if (typeof window !== 'undefined') {
      const projectMatch = window.location.pathname.match(
        /^\/projects\/([^/]+)/
      )
      if (projectMatch?.[1]) return decodeURIComponent(projectMatch[1])
      if (
        window.location.pathname === '/' ||
        window.location.pathname === '/agents/home'
      ) {
        return null
      }
    }
    const raw = localStorage.getItem(PROJECT_SCOPE_STORAGE_KEY)
    if (!raw || raw === ALL_PROJECTS_TABS_KEY) return null
    return raw
  } catch {
    return null
  }
}

function writeProjectScopeId(projectId: string | null) {
  try {
    localStorage.setItem(
      PROJECT_SCOPE_STORAGE_KEY,
      projectId || ALL_PROJECTS_TABS_KEY
    )
  } catch {
    // ignore storage failures
  }
}

function readLastSessionByScope(): Record<string, string> {
  try {
    const raw = localStorage.getItem(LAST_SESSION_BY_SCOPE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {}
    }
    const result: Record<string, string> = {}
    for (const [key, value] of Object.entries(
      parsed as Record<string, unknown>
    )) {
      if (typeof value === 'string' && value.length > 0) result[key] = value
    }
    return result
  } catch {
    return {}
  }
}

function writeLastSessionByScope(map: Record<string, string>) {
  try {
    localStorage.setItem(LAST_SESSION_BY_SCOPE_KEY, JSON.stringify(map))
  } catch {
    // ignore storage failures
  }
}

function readRecentProjectIds(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_PROJECT_IDS_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (id): id is string => typeof id === 'string' && id.length > 0
    )
  } catch {
    return []
  }
}

function writeRecentProjectIds(ids: string[]) {
  try {
    localStorage.setItem(RECENT_PROJECT_IDS_STORAGE_KEY, JSON.stringify(ids))
  } catch {
    // ignore storage failures
  }
}

function readCollapsedSidebarSections(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(SIDEBAR_SECTIONS_COLLAPSED_KEY)
    if (!raw) return { archive: true }
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { archive: true }
    }
    const next: Record<string, boolean> = { archive: true }
    for (const [key, value] of Object.entries(
      parsed as Record<string, unknown>
    )) {
      if (typeof value === 'boolean') next[key] = value
    }
    return next
  } catch {
    return { archive: true }
  }
}

function writeCollapsedSidebarSections(value: Record<string, boolean>) {
  try {
    localStorage.setItem(SIDEBAR_SECTIONS_COLLAPSED_KEY, JSON.stringify(value))
  } catch {
    // ignore storage failures
  }
}

type SessionChatState = {
  messages: AgentMessage[]
  tools: TranscriptTool[]
  todosByRunId: Record<string, AgentTodo[]>
  runIdByMessageId: Record<string, string>
  usageByRunId: Record<string, { inputTokens: number; outputTokens: number }>
  tokenUsage: { inputTokens: number; outputTokens: number }
  activeRunId: string | null
  runActive: boolean
  liveDelta: string
  composer: string
  composerSkills: string[]
  composerFiles: string[]
  expandedToolRunKeys: Record<string, boolean>
  messagesLoaded: boolean
}

function emptySessionChatState(): SessionChatState {
  return {
    messages: [],
    tools: [],
    todosByRunId: {},
    runIdByMessageId: {},
    usageByRunId: {},
    tokenUsage: { inputTokens: 0, outputTokens: 0 },
    activeRunId: null,
    runActive: false,
    liveDelta: '',
    composer: '',
    composerSkills: [],
    composerFiles: [],
    expandedToolRunKeys: {},
    messagesLoaded: false
  }
}

type ComposerModelOption = {
  provider: string
  model: string
  label: string
  speed: string
  profileId?: string | null
  source?: 'cloud' | 'profile' | 'custom'
}

function modelOptionBadge(model: {
  source: string
  provider: string
}): string {
  if (model.source === 'profile' || model.provider === 'local') return 'Local'
  if (model.source === 'custom') return 'Custom'
  if (model.provider === 'anthropic') return 'Anthropic'
  if (model.provider === 'openai') return 'OpenAI'
  if (model.provider === 'google') return 'Gemini'
  if (model.provider === 'xai') return 'Grok'
  if (model.provider === 'nvidia') return 'NVIDIA'
  if (model.provider === 'opencode') return 'OpenCode Zen'
  return model.provider
}

function toComposerModelOptions(
  models: Array<{
    id: string
    label: string
    provider: string
    source: 'cloud' | 'profile' | 'custom'
    profileId: string | null
    enabled: boolean
  }>
): ComposerModelOption[] {
  return models
    .filter(model => model.enabled)
    .map(model => ({
      provider: model.provider,
      model: model.id,
      label: model.label,
      speed: modelOptionBadge(model),
      profileId: model.profileId,
      source: model.source
    }))
}

function relativeTime(value: string) {
  const elapsed = Math.max(0, Date.now() - new Date(value).getTime())
  const minutes = Math.floor(elapsed / 60_000)
  if (minutes < 1) return 'now'
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  return `${Math.floor(hours / 24)}d`
}

function formatMessagePopoverDate(value: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  }).format(date)
}

function downloadMarkdown(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(href)
}

const AUTO_TITLE_FIRST_RESPONSE_THRESHOLD = 2

function isLowSignalTitle(title: string): boolean {
  const normalized = String(title || '')
    .trim()
    .toLowerCase()
  if (!normalized) return true
  const defaults = new Set([
    'untitled',
    'untitled session',
    'untitled thread',
    'new chat',
    'new agent',
    'new agent session',
    'new research session'
  ])
  if (defaults.has(normalized)) return true
  return (
    normalized.includes('greeting chat') ||
    normalized.includes('casual greeting') ||
    normalized === 'general conversation' ||
    normalized === 'small talk'
  )
}

function SessionStatusIcon({ status }: { status: AgentSession['status'] }) {
  if (status === 'running') {
    return (
      <Loader
        className="text-muted-foreground/80 size-3.5 shrink-0 animate-spin"
        aria-hidden
      />
    )
  }
  if (status === 'error') {
    return (
      <span className="border-destructive size-3.5 shrink-0 rounded-full border" />
    )
  }
  if (status === 'interrupted') {
    return (
      <span className="size-3.5 shrink-0 rounded-full border border-amber-500" />
    )
  }
  return <CircleCheck className="text-muted-foreground/70 size-3.5 shrink-0" />
}

function groupSessions(sessions: AgentSession[]) {
  const now = new Date()
  const today = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate()
  ).getTime()
  const yesterday = today - 86_400_000
  const pinned = sessions.filter(item => item.organizeLabel === 'pinned')
  const archived = sessions.filter(item => item.organizeLabel === 'archive')
  const ordinary = sessions.filter(
    item => item.organizeLabel !== 'pinned' && item.organizeLabel !== 'archive'
  )
  return [
    { id: 'pinned', title: 'Pinned', items: pinned },
    {
      id: 'today',
      title: 'Today',
      items: ordinary.filter(
        item =>
          new Date(item.lastMessageAt || item.updatedAt).getTime() >= today
      )
    },
    {
      id: 'yesterday',
      title: 'Yesterday',
      items: ordinary.filter(item => {
        const timestamp = new Date(
          item.lastMessageAt || item.updatedAt
        ).getTime()
        return timestamp >= yesterday && timestamp < today
      })
    },
    {
      id: 'older',
      title: 'Older',
      items: ordinary.filter(
        item =>
          new Date(item.lastMessageAt || item.updatedAt).getTime() < yesterday
      )
    },
    { id: 'archive', title: 'Archived', items: archived }
  ].filter(section => section.items.length > 0)
}

function categorizeSkill(skill: AgentSkill) {
  const name = skill.name.toLowerCase()
  if (name === 'fold' || name === 'boltz-structure-and-binding')
    return 'Structure Prediction'
  if (
    name.includes('md_') ||
    name.includes('openmm') ||
    name.includes('calvados')
  ) {
    return 'Molecular Dynamics'
  }
  if (
    name === 'boltz' ||
    name.includes('design') ||
    name.includes('boltzgen') ||
    name.startsWith('boltz-protein-')
  ) {
    return 'Protein Design'
  }
  if (name.startsWith('boltz-small-molecule-')) return 'Small Molecules'
  if (
    name.includes('setup') ||
    name.includes('integration') ||
    name.includes('slack') ||
    name.includes('report')
  ) {
    return 'Integrations'
  }
  return skill.tags[0] || 'Utilities'
}

function isFeaturedIntegration(integration: IntegrationSummary) {
  const key = integration.key.toLowerCase()
  return (
    key === 'skills-sh' ||
    key === 'boltz' ||
    key === 'fastfold-cloud' ||
    key === 'openai'
  )
}

function stripFrontmatter(content: string) {
  return content.replace(/^---\s*\n[\s\S]*?\n---\s*\n?/, '')
}

function frontmatterValue(content: string, key: string): string | null {
  const match = content.match(new RegExp(`^${key}:\\s*(.+)$`, 'im'))
  if (!match?.[1]) return null
  return match[1].trim().replace(/^['"]|['"]$/g, '') || null
}

function auditStatusBadgeClass(status: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'pass') {
    return 'border-emerald-300/70 bg-emerald-500/10 text-emerald-700 dark:border-emerald-600/60 dark:bg-emerald-500/15 dark:text-emerald-300'
  }
  if (normalized === 'warn') {
    return 'border-amber-300/70 bg-amber-500/10 text-amber-700 dark:border-amber-600/60 dark:bg-amber-500/15 dark:text-amber-300'
  }
  if (normalized === 'fail') {
    return 'border-red-300/70 bg-red-500/10 text-red-700 dark:border-red-600/60 dark:bg-red-500/15 dark:text-red-300'
  }
  return 'border-border/70 bg-muted/40 text-muted-foreground'
}

function skillMetaText(skill: AgentSkill): string | null {
  const parts: string[] = []
  const author = skill.author.trim()
  if (author) parts.push(author)
  if (skill.version) parts.push(`v${skill.version.replace(/^v/i, '')}`)
  return parts.length > 0 ? parts.join(' · ') : null
}

function skillAuthorLabel(skill: AgentSkill): string {
  const author = String(skill.author || '').trim()
  return author || 'Unknown'
}

function suggestionSourceIcon(item: AgentSkillSource): string | null {
  const source = String(item.source || '').toLowerCase()
  const provider = String(item.provider || '').toLowerCase()
  if (source.includes('k-dense-ai') || provider.includes('k-dense')) {
    return '/suggestions/k-dense.png'
  }
  if (source.includes('google-deepmind') || provider.includes('deepmind')) {
    return '/suggestions/deepmind.png'
  }
  if (source.includes('anthropic') || provider.includes('anthropic')) {
    return '/suggestions/anthropic-claude.png'
  }
  return null
}

function suggestionSourceLabel(item: AgentSkillSource): string {
  const source = String(item.source || '').toLowerCase()
  const provider = String(item.provider || '').trim()
  if (source.includes('anthropic') || provider.toLowerCase().includes('anthropic')) {
    return 'Anthropic Claude'
  }
  return provider || item.source
}

function catalogSkillInstallSource(skill: AgentCatalogSkill): string {
  const installUrl = String(skill.installUrl || '').trim()
  if (installUrl) return installUrl
  const source = String(skill.source || '').trim()
  if (/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(source)) {
    return `https://github.com/${source}`
  }
  return source
}

function parseCatalogSkillId(raw: string | null | undefined): {
  id: string
  source: string
  skill: string
} | null {
  const decoded = String(raw || '')
    .trim()
    .replaceAll('~', '/')
  if (!decoded) return null
  const parts = decoded.split('/').filter(Boolean)
  if (parts.length < 2) return null
  const skill = parts.pop() || ''
  const source = parts.join('/')
  if (!source || !skill) return null
  return { id: `${source}/${skill}`, source, skill }
}

function catalogSkillInstallCommand(
  source: string,
  skill: string,
  files?: Array<{ path: string }> | null
): string {
  // Match `fastfold skills add <source>` — CLI has no --skill flag; use @subpath.
  const target = catalogSkillInstallTarget(source, skill, files)
  return target ? `fastfold skills add ${target}` : ''
}

function catalogSkillInstallTarget(
  source: string,
  skill: string,
  files?: Array<{ path: string }> | null
): string {
  const normalizedSource = String(source || '').trim()
  const normalizedSkill = String(skill || '').trim()
  if (!normalizedSource) return ''
  if (!OWNER_REPO_RE.test(normalizedSource)) {
    return normalizedSource
  }
  // Skills.sh file paths are often skill-relative (just "SKILL.md"), not repo-rooted.
  // Only use them when they include a real directory (e.g. skills/.curated/linear/SKILL.md).
  const skillMdPath = (files || [])
    .map(file => String(file.path || '').trim().replace(/^\/+/, ''))
    .find(path => /(^|\/)skill\.md$/i.test(path))
  if (skillMdPath && skillMdPath.includes('/')) {
    const dir = skillMdPath.replace(/\/[^/]+$/u, '').replace(/^\/+/, '')
    if (dir && !/^skill\.md$/i.test(dir)) {
      return `${normalizedSource}@${dir}`
    }
  }
  if (!normalizedSkill) return normalizedSource
  // CLI-compatible shorthand; nested layouts resolve by skill folder name.
  return `${normalizedSource}@skills/${normalizedSkill}`
}

function formatSkillInstallError(error: unknown): string {
  const raw =
    error instanceof Error
      ? error.message
      : typeof error === 'string'
        ? error
        : 'Unable to install this skill.'
  const detailMatch = raw.match(/\{.*"detail"\s*:\s*"((?:\\.|[^"\\])*)"/s)
  const detail = (detailMatch?.[1] || raw)
    .replace(/\\"/g, '"')
    .replace(/^FastFold Agent API \d+:\s*/i, '')
    .replace(/^"|"$/g, '')
    .trim()
  const lower = detail.toLowerCase()
  if (
    lower.includes('removed or moved') ||
    lower.includes('skills.sh listing') ||
    lower.includes('unavailable')
  ) {
    return detail
  }
  if (
    lower.includes('no skill.md') ||
    lower.includes('not found') ||
    lower.includes('could not find')
  ) {
    return (
      `${detail} ` +
      'Skills.sh may still list it, but the skill is unavailable or was removed/moved in the source repository.'
    )
  }
  return detail || 'Unable to install this skill from Skills.sh.'
}

function normalizeSkillMatchKey(raw: string | null | undefined): string {
  return String(raw || '')
    .trim()
    .toLowerCase()
    .replace(/[_\s]+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '')
}

const DEFAULT_SKILLS_REPO = 'fastfold-ai/skills'
const OWNER_REPO_RE = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/

function splitSkillSourceSpec(
  rawSource: string | null | undefined
): { ownerRepo: string; skillsPath: string } | null {
  const source = String(rawSource || '').trim()
  if (!source || source === 'bundled') {
    return { ownerRepo: DEFAULT_SKILLS_REPO, skillsPath: 'skills' }
  }
  if (source.startsWith('https://github.com/')) {
    try {
      const url = new URL(source)
      const parts = url.pathname.replace(/^\/+/, '').split('/').filter(Boolean)
      if (parts.length < 2) return null
      const ownerRepo = `${parts[0]}/${parts[1].replace(/\.git$/i, '')}`
      let skillsPath = 'skills'
      const treeIndex = parts.indexOf('tree')
      if (treeIndex >= 0 && parts.length > treeIndex + 3) {
        const pathFromTree = parts.slice(treeIndex + 3).join('/').trim()
        if (pathFromTree) skillsPath = pathFromTree
      }
      return { ownerRepo, skillsPath }
    } catch {
      return null
    }
  }
  const [ownerRepoRaw, pathRaw] = source.split('@', 2)
  const ownerRepo = ownerRepoRaw.trim()
  if (!OWNER_REPO_RE.test(ownerRepo)) return null
  const skillsPath =
    String(pathRaw || 'skills').trim().replace(/^\/+|\/+$/g, '') || 'skills'
  return { ownerRepo, skillsPath }
}

function pathPointsToSkill(skillsPath: string, skillName: string): boolean {
  const normalizedPath = String(skillsPath || '')
    .trim()
    .replace(/^\/+|\/+$/g, '')
    .toLowerCase()
  const normalizedName = String(skillName || '').trim().toLowerCase()
  if (!normalizedPath || !normalizedName) return false
  return (
    normalizedPath === normalizedName ||
    normalizedPath.endsWith(`/${normalizedName}`)
  )
}

function skillInstallSource(
  skillName: string,
  rawSource: string | null | undefined
): string {
  const source = String(rawSource || '').trim()
  const spec = splitSkillSourceSpec(source)
  if (spec) {
    if (pathPointsToSkill(spec.skillsPath, skillName)) {
      const parentPath = spec.skillsPath
        .split('/')
        .filter(Boolean)
        .slice(0, -1)
        .join('/')
      if (!parentPath || parentPath === 'skills') return spec.ownerRepo
      return `${spec.ownerRepo}@${parentPath}`
    }
    return spec.skillsPath === 'skills'
      ? spec.ownerRepo
      : `${spec.ownerRepo}@${spec.skillsPath}`
  }
  return source || DEFAULT_SKILLS_REPO
}

function skillGithubUrl(
  name: string,
  rawSource: string | null | undefined
): string | null {
  const spec = splitSkillSourceSpec(rawSource)
  if (!spec) return null
  const ownerRepo = spec.ownerRepo
  const skillPath = pathPointsToSkill(spec.skillsPath, name)
    ? spec.skillsPath
    : `${spec.skillsPath}/${encodeURIComponent(name)}`
  return `https://github.com/${ownerRepo}/tree/main/${skillPath}`
}

function catalogCoordsFromInstalledSkill(
  skill: Pick<AgentSkill, 'name' | 'source'>
): { source: string; skill: string } | null {
  const name = String(skill.name || '').trim()
  if (!name) return null
  const spec = splitSkillSourceSpec(skill.source)
  if (!spec?.ownerRepo) return null
  return { source: spec.ownerRepo, skill: name }
}

function skillsShSkillUrl(source: string, skill: string): string | null {
  const normalizedSource = String(source || '')
    .trim()
    .replace(/^\/+|\/+$/g, '')
  const normalizedSkill = String(skill || '')
    .trim()
    .replace(/^\/+|\/+$/g, '')
  if (!normalizedSource || !normalizedSkill) return null
  return `https://skills.sh/${normalizedSource}/${normalizedSkill}`
}

function skillAuthorUrl(rawSource: string | null | undefined): string | null {
  const spec = splitSkillSourceSpec(rawSource)
  if (!spec) return null
  return `https://github.com/${spec.ownerRepo}`
}

function displaySkillVersion(version: string | null | undefined): string {
  const value = String(version || '').trim()
  if (!value) return 'Unknown'
  return /^v/i.test(value) ? value : `v${value}`
}

function formatSkillUpdatedLabel(updatedAt: string | null | undefined): string {
  const raw = String(updatedAt || '').trim()
  if (!raw) return 'Unknown'
  const parsed = new Date(raw)
  if (Number.isNaN(parsed.getTime())) return raw
  const diffMs = Date.now() - parsed.getTime()
  if (diffMs < 0) return raw
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  if (diffMs < minute) return 'just now'
  if (diffMs < hour) return `${Math.floor(diffMs / minute)}m ago`
  if (diffMs < day) return `${Math.floor(diffMs / hour)}h ago`
  return `${Math.floor(diffMs / day)}d ago`
}

type SkillsViewMode =
  | 'list'
  | 'detail'
  | 'catalog_detail'
  | 'import_github'
  | 'import_file'
  | 'trusted_sources'

export default function App() {
  const location = useLocation()
  const navigate = useNavigate()
  const [backendUrl, setBackendUrl] = useState(
    () => localStorage.getItem('fastfold.backend.url') || DEFAULT_BACKEND_URL
  )
  const [backendApiKey, setBackendApiKey] = useState('')
  const client = useMemo(
    () =>
      new LocalAgentClient({
        baseUrl: backendUrl,
        apiKey: backendApiKey || undefined
      }),
    [backendApiKey, backendUrl]
  )
  const [health, setHealth] = useState<BackendHealth | null>(null)
  const [needsAuthLogin, setNeedsAuthLogin] = useState(false)
  const needsAuthLoginRef = useRef(false)
  const [authBootstrapped, setAuthBootstrapped] = useState(false)
  const [authLoggingIn, setAuthLoggingIn] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [connectionLimitDismissed, setConnectionLimitDismissed] =
    useState(false)
  const [sessions, setSessions] = useState<AgentSession[]>([])
  const [projects, setProjects] = useState<AgentProject[]>([])
  const [newProjectOpen, setNewProjectOpen] = useState(false)
  const [projectSettingsOpen, setProjectSettingsOpen] = useState(false)
  const [projectScopeId, setProjectScopeId] = useState<string | null>(() =>
    readProjectScopeId()
  )
  const [lastSessionByScope, setLastSessionByScope] = useState<
    Record<string, string>
  >(() => readLastSessionByScope())
  const [recentProjectIds, setRecentProjectIds] = useState<string[]>(() =>
    readRecentProjectIds()
  )
  const [sessionPreviews, setSessionPreviews] = useState<
    Record<string, string>
  >({})
  const [chatBySessionId, setChatBySessionId] = useState<
    Record<string, SessionChatState>
  >({})
  const [skills, setSkills] = useState<AgentSkill[]>([])
  const [skillDetail, setSkillDetail] = useState<AgentSkillDetail | null>(null)
  const [integrations, setIntegrations] = useState<IntegrationSummary[]>([])
  const catalogSearchEnabled = useMemo(
    () => integrations.find(item => item.key === 'skills-sh')?.configured ?? false,
    [integrations]
  )
  const [mcpServers, setMcpServers] = useState<McpServer[]>([])
  const [mcpCatalog, setMcpCatalog] = useState<McpCatalogEntry[]>([])
  const [mcpCatalogLoading, setMcpCatalogLoading] = useState(false)
  const [runtimeSettings, setRuntimeSettings] =
    useState<RuntimeSettings | null>(null)
  const [modelOptions, setModelOptions] = useState<ComposerModelOption[]>([])
  const [globalSearchOpen, setGlobalSearchOpen] = useState(false)
  const [pendingOpenPath, setPendingOpenPath] = useState<string | null>(null)
  const pendingMentionRef = useRef<string | null>(null)
  const sidebarPanelRef = useRef<ImperativePanelHandle>(null)
  const filesPanelRef = useRef<ImperativePanelHandle>(null)
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)
  const [copiedResumeCommand, setCopiedResumeCommand] = useState(false)
  const [cliMenuOpen, setCliMenuOpen] = useState(false)
  const [terminalOpen, setTerminalOpen] = useState(() => {
    try {
      return localStorage.getItem(TERMINAL_OPEN_STORAGE_KEY) === '1'
    } catch {
      return false
    }
  })
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === '1'
    } catch {
      return false
    }
  })
  const [filesPanelCollapsed, setFilesPanelCollapsed] = useState(() => {
    try {
      return localStorage.getItem(FILES_PANEL_COLLAPSED_STORAGE_KEY) === '1'
    } catch {
      return false
    }
  })
  const [threadMenuOpenId, setThreadMenuOpenId] = useState<string | null>(null)
  const [collapsedSidebarSections, setCollapsedSidebarSections] = useState<
    Record<string, boolean>
  >(() => readCollapsedSidebarSections())
  const [renameTarget, setRenameTarget] = useState<AgentSession | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<AgentSession | null>(null)
  const [openTabsByProject, setOpenTabsByProject] = useState<
    Record<string, string[]>
  >(() => readOpenTabsByProject())
  const [workspaceVersion, setWorkspaceVersion] = useState(0)
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFile[]>([])
  const [integrationValues, setIntegrationValues] = useState<
    Record<string, string>
  >({})
  const streamControllersRef = useRef<Map<string, AbortController>>(new Map())
  const sessionIdRef = useRef<string | null>(null)
  const loadSessionsRef = useRef<(() => Promise<void>) | null>(null)
  const createSessionInFlightRef = useRef(false)
  const autoTitlePassCountRef = useRef<Record<string, number>>({})
  const autoTitleInFlightRef = useRef<Record<string, boolean>>({})
  const prevRunActiveForTitleRef = useRef<Record<string, boolean>>({})

  const detailRoute = matchPath(
    '/dashboard/skills/:skillName',
    location.pathname
  )
  const importGithubRoute = matchPath(
    '/dashboard/skills/import/github',
    location.pathname
  )
  const importFileRoute = matchPath(
    '/dashboard/skills/import/file',
    location.pathname
  )
  const trustedSourcesRoute = matchPath(
    '/dashboard/skills/trusted/sources',
    location.pathname
  )
  const catalogDetailRoute = matchPath(
    { path: '/dashboard/skills/catalog/*', end: true },
    location.pathname
  )
  const legacySkillRoute = matchPath(
    '/agents/skills/:skillName',
    location.pathname
  )
  const integrationDetailRoute = matchPath(
    '/dashboard/integrations/:integrationKey',
    location.pathname
  )
  const legacyIntegrationRoute = matchPath(
    '/agents/integrations/:integrationKey',
    location.pathname
  )
  const isCatalogSearchPath = location.pathname === '/dashboard/skills/search'
  const isCatalogPath = location.pathname.startsWith('/dashboard/skills/catalog')
  const skillRouteName =
    isCatalogSearchPath || isCatalogPath
      ? null
      : (detailRoute?.params.skillName ?? legacySkillRoute?.params.skillName)
  const catalogSkillRoute = parseCatalogSkillId(
    catalogDetailRoute?.params['*']
      ? (() => {
          try {
            return decodeURIComponent(catalogDetailRoute.params['*'])
          } catch {
            return catalogDetailRoute.params['*']
          }
        })()
      : null
  )
  const integrationRouteName =
    integrationDetailRoute?.params.integrationKey ??
    legacyIntegrationRoute?.params.integrationKey ??
    null
  const decodedIntegrationRouteName = integrationRouteName
    ? (() => {
        try {
          return decodeURIComponent(integrationRouteName)
        } catch {
          return integrationRouteName
        }
      })()
    : null
  const normalizedIntegrationRouteName = decodedIntegrationRouteName
    ? decodedIntegrationRouteName.toLowerCase().replace(/[_\s]+/g, '-')
    : null
  const selectedIntegrationKey = decodedIntegrationRouteName
    ? integrations.find(item => {
        const normalizedKey = item.key.toLowerCase().replace(/[_\s]+/g, '-')
        const normalizedName = item.name.toLowerCase().replace(/[_\s]+/g, '-')
        return (
          item.key === decodedIntegrationRouteName ||
          normalizedKey === normalizedIntegrationRouteName ||
          normalizedName === normalizedIntegrationRouteName
        )
      })?.key ?? decodedIntegrationRouteName
    : null
  const sessionRoute = matchPath('/agents/:sessionId', location.pathname)
  const projectRoute = matchPath('/projects/:projectId', location.pathname)
  const routeProjectId = projectRoute?.params.projectId ?? null
  const activeProjectId = projectScopeId
  const tabsScopeKey = projectTabsKey(activeProjectId)
  const openTabIds = openTabsByProject[tabsScopeKey] || []
  const activeProject =
    projects.find(project => project.id === activeProjectId) || null
  const activeIntegration =
    integrations.find(item => item.key === selectedIntegrationKey) || null
  const isDashboard =
    location.pathname === '/dashboard' ||
    location.pathname.startsWith('/dashboard/')
  const dashboardSection: DashboardSection = location.pathname.startsWith(
    '/dashboard/status'
  ) || location.pathname.startsWith('/dashboard/server')
    ? 'status'
    : location.pathname.startsWith('/dashboard/general') ||
        location.pathname.startsWith('/dashboard/settings')
      ? 'general'
      : location.pathname.startsWith('/dashboard/models')
        ? 'models'
        : location.pathname.startsWith('/dashboard/datasets')
          ? 'datasets'
          : location.pathname.startsWith('/dashboard/tools')
            ? 'tools'
            : location.pathname.startsWith('/dashboard/doctor')
              ? 'doctor'
              : location.pathname.startsWith('/dashboard/storage')
                ? 'storage'
                : location.pathname.startsWith('/dashboard/environment')
                  ? 'environment'
                  : location.pathname.startsWith('/dashboard/skills')
                    ? 'skills'
                    : location.pathname.startsWith('/dashboard/integrations')
                      ? 'integrations'
                      : location.pathname.startsWith('/dashboard/mcp')
                        ? 'mcp'
                        : 'overview'
  const isSkills =
    dashboardSection === 'skills' ||
    location.pathname === '/agents/skills' ||
    Boolean(legacySkillRoute)
  const skillsViewMode: SkillsViewMode =
    catalogSkillRoute
    ? 'catalog_detail'
    : (detailRoute || legacySkillRoute) && !isCatalogSearchPath
    ? 'detail'
    : importGithubRoute
    ? 'import_github'
    : importFileRoute
    ? 'import_file'
    : trustedSourcesRoute
    ? 'trusted_sources'
    : 'list'
  const isIntegrations =
    dashboardSection === 'integrations' ||
    location.pathname === '/agents/integrations' ||
    Boolean(legacyIntegrationRoute)
  const isDashboardStatus = dashboardSection === 'status'
  const isDashboardGeneral = dashboardSection === 'general'
  const isDashboardModels = dashboardSection === 'models'
  const isDashboardData = dashboardSection === 'datasets'
  const isDashboardTools = dashboardSection === 'tools'
  const isDashboardDoctor = dashboardSection === 'doctor'
  const isDashboardStorage = dashboardSection === 'storage'
  const isDashboardEnvironment = dashboardSection === 'environment'
  const isDashboardMcp = dashboardSection === 'mcp'
  const isDashboardOverview = isDashboard && dashboardSection === 'overview'
  const isHome =
    location.pathname === '/' || location.pathname === '/agents/home'
  const isProjectHome = Boolean(routeProjectId)
  const isInspect = new URLSearchParams(location.search).get('inspect') === '1'
  const sessionId =
    !isDashboard &&
    !isSkills &&
    !isIntegrations &&
    !isHome &&
    !isProjectHome &&
    sessionRoute?.params.sessionId &&
    sessionRoute.params.sessionId !== 'home' &&
    sessionRoute.params.sessionId !== 'skills' &&
    sessionRoute.params.sessionId !== 'integrations'
      ? sessionRoute.params.sessionId
      : null
  const session = sessions.find(item => item.id === sessionId) || null

  const patchOpenTabs = useCallback(
    (scopeKey: string, updater: (current: string[]) => string[]) => {
      setOpenTabsByProject(current => {
        const prev = current[scopeKey] || []
        const next = updater(prev)
        if (
          next.length === prev.length &&
          next.every((id, index) => id === prev[index])
        ) {
          return current
        }
        const map = { ...current, [scopeKey]: next }
        writeOpenTabsByProject(map)
        return map
      })
    },
    []
  )

  const setOpenTabIds = useCallback(
    (value: string[] | ((current: string[]) => string[])) => {
      patchOpenTabs(tabsScopeKey, current =>
        typeof value === 'function' ? value(current) : value
      )
    },
    [patchOpenTabs, tabsScopeKey]
  )

  const openSessionTab = useCallback(
    (id: string, scopeKey: string = tabsScopeKey) => {
      patchOpenTabs(scopeKey, current =>
        current.includes(id) ? current : [...current, id]
      )
    },
    [patchOpenTabs, tabsScopeKey]
  )

  const runningSessionIdsKey = sessions
    .filter(item => item.status === 'running')
    .map(item => item.id)
    .sort()
    .join(',')
  const runningCount = runningSessionIdsKey
    ? runningSessionIdsKey.split(',').length
    : 0
  const showConnectionLimitWarning =
    runningCount >= CONCURRENT_RUN_SOFT_LIMIT && !connectionLimitDismissed
  const chat = sessionId
    ? chatBySessionId[sessionId] ?? emptySessionChatState()
    : emptySessionChatState()
  const {
    messages,
    tools,
    todosByRunId,
    runIdByMessageId,
    usageByRunId,
    tokenUsage,
    activeRunId,
    runActive,
    liveDelta,
    composer,
    composerSkills,
    composerFiles,
    expandedToolRunKeys,
    messagesLoaded
  } = chat

  sessionIdRef.current = sessionId

  const patchChat = useCallback(
    (
      id: string,
      patch:
        | Partial<SessionChatState>
        | ((prev: SessionChatState) => SessionChatState)
    ) => {
      setChatBySessionId(current => {
        const prev = current[id] ?? emptySessionChatState()
        const next =
          typeof patch === 'function' ? patch(prev) : { ...prev, ...patch }
        if (next === prev) return current
        return { ...current, [id]: next }
      })
    },
    []
  )

  const loadSessions = useCallback(async () => {
    const nextSessions = await client.listSessions()
    setSessions(nextSessions)
    setChatBySessionId(current => {
      let changed = false
      const next = { ...current }
      for (const item of nextSessions) {
        const prev = next[item.id]
        if (!prev) continue
        const shouldRun = item.status === 'running'
        if (prev.runActive === shouldRun) continue
        next[item.id] = { ...prev, runActive: shouldRun }
        changed = true
      }
      return changed ? next : current
    })
    void Promise.all(
      nextSessions.slice(0, 12).map(async item => {
        try {
          const history = await client.listMessages(item.id)
          return [
            item.id,
            history.at(-1)?.content || 'No messages yet.'
          ] as const
        } catch {
          return [item.id, 'No messages yet.'] as const
        }
      })
    ).then(entries => setSessionPreviews(Object.fromEntries(entries)))
  }, [client])

  loadSessionsRef.current = loadSessions

  const loadProjects = useCallback(async () => {
    setProjects(await client.listProjects())
  }, [client])

  const loadSkills = useCallback(async () => {
    const items = await client.listSkills()
    const seen = new Set<string>()
    const unique = items.filter(skill => {
      const key = skill.name.trim().toLowerCase()
      if (!key || seen.has(key)) return false
      seen.add(key)
      return true
    })
    setSkills(unique)
  }, [client])

  const loadIntegrations = useCallback(async () => {
    setIntegrations(await client.listIntegrations())
  }, [client])

  const loadMcpServers = useCallback(async () => {
    setMcpServers(await client.listMcpServers())
  }, [client])

  const loadMcpCatalog = useCallback(async () => {
    setMcpCatalogLoading(true)
    try {
      setMcpCatalog(await client.listMcpCatalog())
    } finally {
      setMcpCatalogLoading(false)
    }
  }, [client])

  const refreshMcp = useCallback(async () => {
    await Promise.all([loadMcpServers(), loadMcpCatalog()])
  }, [loadMcpCatalog, loadMcpServers])

  const loadModelOptions = useCallback(async () => {
    try {
      const models = await client.listModels({
        enabledOnly: true,
        discover: true
      })
      setModelOptions(toComposerModelOptions(models))
    } catch {
      // Keep the last known selector list if the catalog request fails.
    }
  }, [client])

  const loadAccount = useCallback(
    (options?: { checkUpdates?: boolean; signal?: AbortSignal }) =>
      client.getAccount(options),
    [client]
  )

  const logoutAccount = useCallback(
    (signal?: AbortSignal) => client.logoutAccount(signal),
    [client]
  )

  const loadStorage = useCallback(
    (signal?: AbortSignal) => client.getStorage(signal),
    [client]
  )
  const loadEnvironment = useCallback(
    (signal?: AbortSignal) => client.getEnvironment(signal),
    [client]
  )
  const loadServerStatus = useCallback(
    (signal?: AbortSignal) => client.getServerStatus(signal),
    [client]
  )

  const connect = useCallback(async () => {
    setConnecting(true)
    setError(null)
    const goToLogin = () => {
      const alreadyNext = nextFromSearch(location.search)
      const deepLink =
        location.pathname === '/'
          ? null
          : sanitizeAuthReturnTo(
              `${location.pathname}${location.search}${location.hash}`
            )
      needsAuthLoginRef.current = true
      setHealth(null)
      setNeedsAuthLogin(true)
      const target = loginPathWithNext(alreadyNext || deepLink)
      if (`${location.pathname}${location.search}` !== target) {
        navigate(target, { replace: true })
      }
    }
    const looksLikeAuthFailure = (message: string) =>
      message.includes('401') ||
      /failed to fetch|networkerror|load failed|network request failed/i.test(
        message
      )

    try {
      // If we already decided login is required (e.g. logout), do not remount
      // the shell from a stale reconnect.
      if (needsAuthLoginRef.current) {
        return
      }
      const nextHealth = await client.health()
      if (needsAuthLoginRef.current) return
      localStorage.setItem('fastfold.backend.url', backendUrl)

      let authEnabled = false
      try {
        const status = await client.authStatus()
        authEnabled = Boolean(status.authEnabled)
      } catch {
        authEnabled = false
      }
      if (needsAuthLoginRef.current) return

      if (authEnabled) {
        try {
          await client.getRuntimeSettings()
        } catch (cause) {
          const message = cause instanceof Error ? cause.message : ''
          if (looksLikeAuthFailure(message)) {
            goToLogin()
            return
          }
          throw cause
        }
      }
      if (needsAuthLoginRef.current) return

      // Only mount the app shell after auth is confirmed.
      needsAuthLoginRef.current = false
      setNeedsAuthLogin(false)
      setHealth(nextHealth)
      const [, , , , , , settings] = await Promise.all([
        loadSessions(),
        loadProjects(),
        loadSkills(),
        loadIntegrations(),
        loadMcpServers(),
        loadMcpCatalog(),
        client.getRuntimeSettings(),
        loadModelOptions()
      ])
      if (needsAuthLoginRef.current) return
      setRuntimeSettings(settings)
      const returnTo = nextFromSearch(location.search)
      if (returnTo) {
        navigate(returnTo, { replace: true })
      }
    } catch (cause) {
      if (needsAuthLoginRef.current) return
      const message =
        cause instanceof Error ? cause.message : 'Unable to connect'
      // Health succeeded path already handled; if auth is on and later
      // batch calls fail with opaque network/401 errors, prefer login UI.
      try {
        const status = await client.authStatus()
        if (status.authEnabled && looksLikeAuthFailure(message)) {
          goToLogin()
          return
        }
      } catch {
        // ignore — fall through to connect error UI
      }
      setHealth(null)
      setError(message)
    } finally {
      setConnecting(false)
      setAuthBootstrapped(true)
    }
  }, [
    backendUrl,
    client,
    loadIntegrations,
    loadMcpCatalog,
    loadMcpServers,
    loadModelOptions,
    loadProjects,
    loadSessions,
    loadSkills,
    location.hash,
    location.pathname,
    location.search,
    navigate
  ])

  const submitAuthLogin = useCallback(
    async (apiKey: string, remember: boolean) => {
      setAuthLoggingIn(true)
      try {
        await client.login(apiKey, { remember })
        setBackendApiKey('')
        needsAuthLoginRef.current = false
        // Keep login UI until connect() confirms the session.
        await connect()
      } catch (cause) {
        needsAuthLoginRef.current = true
        const raw = cause instanceof Error ? cause.message : 'Invalid API key'
        let message = 'Invalid API key'
        try {
          const jsonMatch = raw.match(/\{.*\}/s)
          if (jsonMatch) {
            const parsed = JSON.parse(jsonMatch[0]) as { detail?: string }
            if (parsed.detail) message = parsed.detail
          } else if (/invalid api key/i.test(raw)) {
            message = 'Invalid API key'
          } else if (raw && !raw.startsWith('FastFold Agent API')) {
            message = raw
          }
        } catch {
          // keep friendly default
        }
        toast.error(message)
      } finally {
        setAuthLoggingIn(false)
      }
    },
    [client, connect]
  )

  const logoutSession = useCallback(async () => {
    // Gate the UI immediately so a reconnect effect cannot remount the app
    // before the logout request finishes / cookie is cleared.
    needsAuthLoginRef.current = true
    setNeedsAuthLogin(true)
    setHealth(null)
    setAuthBootstrapped(true)
    setBackendApiKey('')
    setRuntimeSettings(null)
    if (location.pathname !== '/' || location.search) {
      navigate('/', { replace: true })
    }
    try {
      await client.logout()
    } catch {
      // Cookie clear may have failed; UI is already on login.
    }
  }, [client, location.pathname, location.search, navigate])

  useEffect(() => {
    // Legacy /login URL → root (login renders under / when unauthenticated).
    if (location.pathname === '/login') {
      navigate('/', { replace: true })
      return
    }
    if (location.pathname === '/agents/home') {
      navigate('/', { replace: true })
      return
    }
    if (location.pathname === '/dashboard/settings') {
      navigate('/dashboard/general', { replace: true })
      return
    }
    if (location.pathname === '/agents/skills') {
      navigate('/dashboard/skills', { replace: true })
      return
    }
    if (legacySkillRoute?.params.skillName) {
      navigate(
        `/dashboard/skills/${legacySkillRoute.params.skillName}`,
        { replace: true }
      )
      return
    }
    if (location.pathname === '/agents/integrations') {
      navigate('/dashboard/integrations', { replace: true })
      return
    }
    if (legacyIntegrationRoute?.params.integrationKey) {
      navigate(
        `/dashboard/integrations/${legacyIntegrationRoute.params.integrationKey}`,
        { replace: true }
      )
    }
  }, [
    legacyIntegrationRoute?.params.integrationKey,
    legacySkillRoute?.params.skillName,
    location.pathname,
    navigate
  ])

  useEffect(() => {
    const base = 'Sandwalk'
    if (session?.title) {
      document.title = `${session.title} · ${base}`
      return
    }
    if (isDashboardOverview) {
      document.title = `Dashboard · ${base}`
      return
    }
    if (isDashboardStatus) {
      document.title = `Status · ${base}`
      return
    }
    if (isDashboardGeneral) {
      document.title = `General · ${base}`
      return
    }
    if (isDashboardModels) {
      document.title = `Models · ${base}`
      return
    }
    if (isDashboardData) {
      document.title = `Datasets · ${base}`
      return
    }
    if (isDashboardTools) {
      document.title = `Tools · ${base}`
      return
    }
    if (isDashboardDoctor) {
      document.title = `Doctor · ${base}`
      return
    }
    if (isDashboardStorage) {
      document.title = `Storage · ${base}`
      return
    }
    if (isDashboardEnvironment) {
      document.title = `Environment · ${base}`
      return
    }
    if (isSkills) {
      document.title = `Skills · ${base}`
      return
    }
    if (isIntegrations) {
      if (activeIntegration) {
        document.title = `${activeIntegration.name} · Integrations · ${base}`
        return
      }
      document.title = `Integrations · ${base}`
      return
    }
    if (isDashboardMcp) {
      document.title = `MCP · ${base}`
      return
    }
    if (activeProject) {
      document.title = `${activeProject.name} · ${base}`
      return
    }
    document.title = base
  }, [
    activeIntegration,
    activeProject,
    isDashboardDoctor,
    isDashboardStorage,
    isDashboardEnvironment,
    isDashboardMcp,
    isDashboardOverview,
    isDashboardStatus,
    isDashboardGeneral,
    isDashboardModels,
    isDashboardData,
    isDashboardTools,
    isIntegrations,
    isSkills,
    session?.title
  ])

  useEffect(() => {
    if (needsAuthLogin) return
    void connect()
  }, [connect, needsAuthLogin])

  useEffect(() => {
    if (isDashboardModels || !health) return
    void loadModelOptions()
  }, [health, isDashboardModels, loadModelOptions])

  useEffect(() => {
    setIntegrationValues({})
  }, [selectedIntegrationKey])

  useEffect(() => {
    if (!isIntegrations || !selectedIntegrationKey) return
    if (integrations.length === 0) return
    if (!integrations.some(item => item.key === selectedIntegrationKey)) {
      navigate('/dashboard/integrations', { replace: true })
    }
  }, [integrations, isIntegrations, navigate, selectedIntegrationKey])

  useEffect(() => {
    if (!sessionId) return
    const item = sessions.find(session => session.id === sessionId)
    // Keep project tab strips clean: only pin sessions that belong to the scope.
    if (activeProjectId && item && item.projectId !== activeProjectId) return
    openSessionTab(sessionId)
  }, [activeProjectId, openSessionTab, sessionId, sessions])

  useEffect(() => {
    // Wait until sessions are loaded — otherwise every persisted tab looks
    // "unknown" and gets wiped on reload.
    if (!activeProjectId || sessions.length === 0) return
    setOpenTabsByProject(current => {
      const ids = current[activeProjectId]
      if (!ids || ids.length === 0) return current
      const filtered = ids.filter(id => {
        const item = sessions.find(session => session.id === id)
        return Boolean(item && item.projectId === activeProjectId)
      })
      if (filtered.length === ids.length) return current
      const next = { ...current }
      if (filtered.length > 0) next[activeProjectId] = filtered
      else delete next[activeProjectId]
      writeOpenTabsByProject(next)
      return next
    })
  }, [activeProjectId, sessions])

  useEffect(() => {
    if (!sessionId) return
    setLastSessionByScope(current => {
      if (current[tabsScopeKey] === sessionId) return current
      const next = { ...current, [tabsScopeKey]: sessionId }
      writeLastSessionByScope(next)
      return next
    })
  }, [sessionId, tabsScopeKey])

  useEffect(() => {
    writeProjectScopeId(projectScopeId)
  }, [projectScopeId])

  useEffect(() => {
    if (sessions.length === 0) return
    const existing = new Set(sessions.map(item => item.id))
    setOpenTabsByProject(current => {
      let changed = false
      const next: Record<string, string[]> = {}
      for (const [key, ids] of Object.entries(current)) {
        const filtered = ids.filter(id => existing.has(id))
        if (filtered.length !== ids.length) changed = true
        if (filtered.length > 0) next[key] = filtered
        else if (ids.length > 0) changed = true
      }
      if (!changed) return current
      writeOpenTabsByProject(next)
      return next
    })
    setLastSessionByScope(current => {
      let changed = false
      const next: Record<string, string> = {}
      for (const [key, id] of Object.entries(current)) {
        if (!existing.has(id)) {
          changed = true
          continue
        }
        next[key] = id
      }
      if (!changed) return current
      writeLastSessionByScope(next)
      return next
    })
  }, [sessions])

  useEffect(() => {
    if (!sessionId) {
      setWorkspaceFiles([])
      return
    }
    let cancelled = false
    void client
      .listFiles(sessionId)
      .then(files => {
        if (!cancelled) setWorkspaceFiles(files)
      })
      .catch(() => {
        if (!cancelled) setWorkspaceFiles([])
      })
    return () => {
      cancelled = true
    }
  }, [client, sessionId, workspaceVersion])

  useEffect(() => {
    try {
      localStorage.setItem(
        SIDEBAR_COLLAPSED_STORAGE_KEY,
        sidebarCollapsed ? '1' : '0'
      )
    } catch {
      // ignore storage failures
    }
  }, [sidebarCollapsed])

  useEffect(() => {
    try {
      localStorage.setItem(
        FILES_PANEL_COLLAPSED_STORAGE_KEY,
        filesPanelCollapsed ? '1' : '0'
      )
    } catch {
      // ignore storage failures
    }
  }, [filesPanelCollapsed])

  useEffect(() => {
    try {
      localStorage.setItem(TERMINAL_OPEN_STORAGE_KEY, terminalOpen ? '1' : '0')
    } catch {
      // ignore storage failures
    }
  }, [terminalOpen])

  useEffect(() => {
    const panel = sidebarPanelRef.current
    if (!panel) return
    if (sidebarCollapsed) {
      if (!panel.isCollapsed()) panel.collapse()
    } else if (panel.isCollapsed()) {
      panel.expand()
    }
  }, [sidebarCollapsed])

  useEffect(() => {
    const panel = filesPanelRef.current
    if (!panel) return
    if (filesPanelCollapsed) {
      if (!panel.isCollapsed()) panel.collapse()
    } else if (panel.isCollapsed()) {
      panel.expand()
    }
  }, [filesPanelCollapsed, sessionId])

  useEffect(() => {
    writeCollapsedSidebarSections(collapsedSidebarSections)
  }, [collapsedSidebarSections])

  useEffect(() => {
    if (runningCount < CONCURRENT_RUN_SOFT_LIMIT) {
      setConnectionLimitDismissed(false)
    }
  }, [runningCount])

  useEffect(() => {
    if (routeProjectId) {
      setProjectScopeId(routeProjectId)
      return
    }
    if (
      location.pathname === '/' ||
      location.pathname === '/agents/home'
    ) {
      setProjectScopeId(null)
    }
  }, [location.pathname, routeProjectId])

  useEffect(() => {
    if (!health || !sessionId) return
    const controller = new AbortController()
    void client
      .listMessages(sessionId, controller.signal)
      .then(history => {
        patchChat(sessionId, prev => ({
          ...prev,
          messages: history,
          messagesLoaded: true
        }))
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            cause instanceof Error ? cause.message : 'Unable to load messages'
          )
        }
      })
    return () => controller.abort()
  }, [client, health, patchChat, sessionId])

  useEffect(() => {
    if (!health) {
      for (const controller of streamControllersRef.current.values()) {
        controller.abort()
      }
      streamControllersRef.current.clear()
      return
    }

    // Only stream the active session + any currently running sessions.
    // An SSE per open tab exhausts the browser's ~6 HTTP/1.1 connections/host,
    // which leaves file content fetches stuck in (pending).
    const wanted = new Set<string>()
    if (sessionId) wanted.add(sessionId)
    for (const id of runningSessionIdsKey.split(',').filter(Boolean)) {
      wanted.add(id)
    }

    for (const [id, controller] of [...streamControllersRef.current]) {
      if (!wanted.has(id)) {
        controller.abort()
        streamControllersRef.current.delete(id)
      }
    }

    for (const id of wanted) {
      if (streamControllersRef.current.has(id)) continue
      const controller = new AbortController()
      streamControllersRef.current.set(id, controller)

      void client
        .streamEvents(id, {
          signal: controller.signal,
          onEvent: (event: AgentEvent) => {
            if (event.type === 'run.started') {
              patchChat(id, prev => ({
                ...prev,
                runActive: true,
                activeRunId: event.runId,
                liveDelta: ''
              }))
              setSessions(current =>
                current.map(item =>
                  item.id === id
                    ? { ...item, status: 'running' as const }
                    : item
                )
              )
              void client.listMessages(id).then(history => {
                patchChat(id, prev => ({
                  ...prev,
                  messages: history,
                  messagesLoaded: true
                }))
              })
            } else if (event.type === 'session.updated') {
              void loadSessionsRef.current?.()
            } else if (event.type === 'assistant.delta') {
              patchChat(id, prev => ({
                ...prev,
                liveDelta: prev.liveDelta + event.payload.delta
              }))
            } else if (event.type === 'tool.started') {
              const toolId = event.payload.toolCallId || event.id
              patchChat(id, prev => {
                if (prev.tools.some(tool => tool.id === toolId)) return prev
                return {
                  ...prev,
                  tools: [
                    ...prev.tools,
                    {
                      id: toolId,
                      runId: event.runId,
                      messageId: null,
                      name: event.payload.name,
                      status: 'pending' as const,
                      args: event.payload.arguments,
                      startedAt: event.timestamp
                    }
                  ]
                }
              })
            } else if (event.type === 'tool.completed') {
              patchChat(id, prev => ({
                ...prev,
                tools: prev.tools.map(tool =>
                  tool.id === event.payload.toolCallId
                    ? {
                        ...tool,
                        status: event.payload.isError
                          ? ('error' as const)
                          : ('completed' as const),
                        result: event.payload.output,
                        durationSeconds: event.payload.durationSeconds,
                        endedAt: event.timestamp
                      }
                    : tool
                )
              }))
            } else if (event.type === 'todos.updated') {
              if (!event.runId) return
              patchChat(id, prev => ({
                ...prev,
                todosByRunId: {
                  ...prev.todosByRunId,
                  [event.runId as string]: event.payload.todos
                }
              }))
            } else if (event.type === 'run.usage') {
              const payload = event.payload as Record<string, unknown>
              const nextUsage = {
                inputTokens: Number(
                  payload.inputTokens ?? payload.input_tokens ?? 0
                ),
                outputTokens: Number(
                  payload.outputTokens ?? payload.output_tokens ?? 0
                )
              }
              patchChat(id, prev => ({
                ...prev,
                tokenUsage: nextUsage,
                usageByRunId: event.runId
                  ? {
                      ...prev.usageByRunId,
                      [event.runId as string]: nextUsage
                    }
                  : prev.usageByRunId
              }))
            } else if (event.type === 'assistant.message') {
              patchChat(id, prev => {
                const message = event.payload.message
                const messages = prev.messages.some(
                  item => item.id === message.id
                )
                  ? prev.messages
                  : [...prev.messages, message]
                return {
                  ...prev,
                  liveDelta: '',
                  messages,
                  messagesLoaded: true,
                  runIdByMessageId: event.runId
                    ? {
                        ...prev.runIdByMessageId,
                        [message.id]: event.runId as string
                      }
                    : prev.runIdByMessageId,
                  tools: event.runId
                    ? prev.tools.map(tool =>
                        tool.runId === event.runId
                          ? { ...tool, messageId: message.id }
                          : tool
                      )
                    : prev.tools
                }
              })
            } else if (
              event.type === 'run.completed' ||
              event.type === 'run.failed' ||
              event.type === 'run.interrupted'
            ) {
              const nextStatus =
                event.type === 'run.failed'
                  ? ('error' as const)
                  : event.type === 'run.interrupted'
                  ? ('interrupted' as const)
                  : ('idle' as const)
              patchChat(id, prev => ({
                ...prev,
                runActive: false,
                activeRunId: null,
                liveDelta: '',
                todosByRunId:
                  event.runId && prev.todosByRunId[event.runId]
                    ? {
                        ...prev.todosByRunId,
                        [event.runId]: prev.todosByRunId[event.runId].map(
                          todo =>
                            todo.status === 'in_progress'
                              ? { ...todo, status: 'completed' as const }
                              : todo
                        )
                      }
                    : prev.todosByRunId
              }))
              setSessions(current =>
                current.map(item =>
                  item.id === id ? { ...item, status: nextStatus } : item
                )
              )
              if (event.type === 'run.completed') {
                setWorkspaceVersion(current => current + 1)
              }
              void client.listMessages(id).then(history => {
                patchChat(id, prev => ({
                  ...prev,
                  messages: history,
                  messagesLoaded: true
                }))
              })
              void loadSessionsRef.current?.()
            }
          }
        })
        .catch((cause: unknown) => {
          if (!controller.signal.aborted && sessionIdRef.current === id) {
            setError(
              cause instanceof Error
                ? cause.message
                : 'Event stream disconnected'
            )
          }
        })
        .finally(() => {
          if (streamControllersRef.current.get(id) === controller) {
            streamControllersRef.current.delete(id)
          }
        })
    }
  }, [client, health, patchChat, runningSessionIdsKey, sessionId])

  useEffect(() => {
    if (!sessionId) return
    const justFinished =
      Boolean(prevRunActiveForTitleRef.current[sessionId]) && !runActive
    prevRunActiveForTitleRef.current[sessionId] = runActive
    if (!justFinished || autoTitleInFlightRef.current[sessionId]) return
    if ((autoTitlePassCountRef.current[sessionId] || 0) > 0) return
    const conversationCount = messages.filter(
      message => message.role === 'user' || message.role === 'assistant'
    ).length
    if (conversationCount < AUTO_TITLE_FIRST_RESPONSE_THRESHOLD) return
    if (!isLowSignalTitle(session?.title || '')) return

    autoTitleInFlightRef.current[sessionId] = true
    const titledSessionId = sessionId
    void (async () => {
      try {
        const updated = await client.autoTitleSession(titledSessionId, {
          force: true
        })
        const title = String(updated.title || '').trim()
        if (!title) return
        setSessions(current =>
          current.map(item =>
            item.id === titledSessionId
              ? { ...item, title, updatedAt: updated.updatedAt }
              : item
          )
        )
        autoTitlePassCountRef.current[titledSessionId] = 1
      } catch {
        // Best effort; retry on a later completed run.
      } finally {
        autoTitleInFlightRef.current[titledSessionId] = false
      }
    })()
  }, [client, messages, runActive, session?.title, sessionId])

  useEffect(() => {
    const name = skillRouteName
    if (!name) {
      setSkillDetail(null)
      return
    }
    const controller = new AbortController()
    void client
      .getSkill(decodeURIComponent(name), controller.signal)
      .then(setSkillDetail)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            cause instanceof Error ? cause.message : 'Unable to load skill'
          )
        }
      })
    return () => controller.abort()
  }, [client, skillRouteName])

  useGlobalSearchHotkey(globalSearchOpen, setGlobalSearchOpen)

  const createSession = useCallback(
    async (projectId?: string | null) => {
      if (createSessionInFlightRef.current) return
      createSessionInFlightRef.current = true
      try {
        const id = projectId ?? activeProjectId ?? null
        const scopeKey = projectTabsKey(id)
        const created = await client.createSession({
          title: 'Untitled session',
          projectId: id || undefined
        })
        if (id) {
          setProjectScopeId(id)
          setRecentProjectIds(current => {
            const next = [id, ...current.filter(item => item !== id)].slice(
              0,
              10
            )
            writeRecentProjectIds(next)
            return next
          })
        }
        patchOpenTabs(scopeKey, current =>
          current.includes(created.id) ? current : [...current, created.id]
        )
        setLastSessionByScope(current => {
          const next = { ...current, [scopeKey]: created.id }
          writeLastSessionByScope(next)
          return next
        })
        await loadSessions()
        if (id) await loadProjects()
        navigate(`/agents/${created.id}`)
      } catch (cause) {
        setError(
          cause instanceof Error ? cause.message : 'Unable to create agent'
        )
      } finally {
        createSessionInFlightRef.current = false
      }
    },
    [
      activeProjectId,
      client,
      loadProjects,
      loadSessions,
      navigate,
      patchOpenTabs
    ]
  )

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return
      if (event.key.toLowerCase() !== 'n') return
      if (!(event.metaKey || event.ctrlKey)) return
      if (event.altKey || event.shiftKey) return
      event.preventDefault()
      void createSession(activeProjectId)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [activeProjectId, createSession])

  const closeSessionTab = (id: string) => {
    const scopeProjectId = activeProjectId
    const tabIsInScope = (tabId: string) => {
      const item = sessions.find(session => session.id === tabId)
      if (!item) return false
      if (!scopeProjectId) return true
      return item.projectId === scopeProjectId
    }

    let neighbor: string | null | undefined
    setOpenTabIds(current => {
      const index = current.indexOf(id)
      if (index === -1) return current
      const withoutClosed = current.filter(tabId => tabId !== id)
      // Drop tabs that don't belong in this project scope (e.g. leftover global tabs).
      const next = scopeProjectId
        ? withoutClosed.filter(tabIsInScope)
        : withoutClosed

      if (id === sessionId) {
        if (next.length === 0) {
          neighbor = null
        } else {
          const preferred = withoutClosed
            .slice(Math.min(index, withoutClosed.length))
            .concat(withoutClosed.slice(0, Math.min(index, withoutClosed.length)).reverse())
            .find(tabId => next.includes(tabId))
          neighbor = preferred || next[next.length - 1] || null
        }
      }
      return next
    })

    if (neighbor === undefined) return

    if (!neighbor) {
      setLastSessionByScope(current => {
        if (!(tabsScopeKey in current)) return current
        const next = { ...current }
        delete next[tabsScopeKey]
        writeLastSessionByScope(next)
        return next
      })
      navigate(scopeProjectId ? `/projects/${scopeProjectId}` : '/')
      return
    }

    navigate(`/agents/${neighbor}`)
  }

  const closeOtherSessionTabs = (keepId: string) => {
    setOpenTabIds(current => current.filter(id => id === keepId))
    if (sessionId !== keepId) navigate(`/agents/${keepId}`)
  }

  const sendMessage = async () => {
    const legacySkills = composerSkills
      .filter(name => !composer.includes(`⟦/:${name}⟧`))
      .map(name => `/${name}`)
    const legacyFiles = composerFiles
      .filter(path => !composer.includes(`⟦@:${path}⟧`))
      .map(path => `@${path}`)
    const content = [
      ...legacySkills,
      ...legacyFiles,
      composerToMessage(composer)
    ]
      .filter(Boolean)
      .join(' ')
      .trim()
    if (!sessionId || !content || runActive) return
    const othersRunning = sessions.filter(
      item => item.status === 'running' && item.id !== sessionId
    ).length
    if (othersRunning + 1 >= CONCURRENT_RUN_HARD_LIMIT) {
      const proceed = window.confirm(
        `You already have ${othersRunning} agent${
          othersRunning === 1 ? '' : 's'
        } running. Browsers allow about 6 live connections to the local API, so files and chat can freeze with this many concurrent runs.\n\nStart another run anyway?`
      )
      if (!proceed) return
    } else if (othersRunning + 1 >= CONCURRENT_RUN_SOFT_LIMIT) {
      setConnectionLimitDismissed(false)
    }
    const targetSessionId = sessionId
    const previousComposer = composer
    const previousSkills = composerSkills
    const previousFiles = composerFiles
    patchChat(targetSessionId, {
      composer: '',
      composerSkills: [],
      composerFiles: []
    })
    setError(null)
    try {
      await client.sendMessage(targetSessionId, content)
      patchChat(targetSessionId, prev => ({
        ...prev,
        runActive: true
      }))
      setSessions(current =>
        current.map(item =>
          item.id === targetSessionId
            ? { ...item, status: 'running' as const }
            : item
        )
      )
      const history = await client.listMessages(targetSessionId)
      patchChat(targetSessionId, prev => ({
        ...prev,
        messages: history,
        messagesLoaded: true
      }))
    } catch (cause) {
      patchChat(targetSessionId, {
        composer: previousComposer,
        composerSkills: previousSkills,
        composerFiles: previousFiles
      })
      setError(
        cause instanceof Error ? cause.message : 'Unable to send message'
      )
    }
  }

  const loadSkillDetail = useCallback(
    (name: string) => client.getSkill(name),
    [client]
  )

  const updateSession = async (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => {
    try {
      await client.updateSession(target.id, changes)
      await Promise.all([loadSessions(), loadProjects()])
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update agent'
      )
    }
  }

  const createProject = async (input: {
    name: string
    description: string
    agentContext: string
  }) => {
    try {
      const project = await client.createProject(input)
      await loadProjects()
      setProjectScopeId(project.id)
      setRecentProjectIds(current => {
        const next = [
          project.id,
          ...current.filter(item => item !== project.id)
        ].slice(0, 10)
        writeRecentProjectIds(next)
        return next
      })
      navigate(`/projects/${project.id}`)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to create project'
      )
      throw cause
    }
  }

  const saveProjectSettings = async (input: {
    name: string
    description: string
    agentContext: string
  }) => {
    if (!activeProject) return
    try {
      await client.updateProject(activeProject.id, {
        name: input.name,
        description: input.description || null,
        agentContext: input.agentContext || null
      })
      await loadProjects()
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update project'
      )
      throw cause
    }
  }

  const landingPathForScope = useCallback(
    (scopeId: string | null) => {
      const key = projectTabsKey(scopeId)
      const tabs = (openTabsByProject[key] || []).filter(id => {
        const item = sessions.find(session => session.id === id)
        if (!item) return false
        if (!scopeId) return true
        return item.projectId === scopeId
      })
      if (tabs.length === 0) {
        return scopeId ? `/projects/${scopeId}` : '/'
      }
      const last = lastSessionByScope[key]
      const target =
        last && tabs.includes(last) ? last : tabs[tabs.length - 1]
      return `/agents/${target}`
    },
    [lastSessionByScope, openTabsByProject, sessions]
  )

  const selectAllProjects = () => {
    setProjectScopeId(null)
    navigate(landingPathForScope(null))
  }

  const selectProjectScope = (projectId: string) => {
    setProjectScopeId(projectId)
    setRecentProjectIds(current => {
      const next = [
        projectId,
        ...current.filter(item => item !== projectId)
      ].slice(0, 10)
      writeRecentProjectIds(next)
      return next
    })
    navigate(landingPathForScope(projectId))
  }

  const togglePinProject = async (project: AgentProject) => {
    try {
      await client.updateProject(project.id, { pinned: !project.pinned })
      await loadProjects()
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update project'
      )
    }
  }

  const deleteProject = async (project: AgentProject) => {
    try {
      await client.deleteProject(project.id)
      setOpenTabsByProject(current => {
        if (!(project.id in current)) return current
        const next = { ...current }
        delete next[project.id]
        writeOpenTabsByProject(next)
        return next
      })
      setLastSessionByScope(current => {
        if (!(project.id in current)) return current
        const next = { ...current }
        delete next[project.id]
        writeLastSessionByScope(next)
        return next
      })
      if (activeProjectId === project.id) {
        setProjectScopeId(null)
        navigate('/')
      }
      await Promise.all([loadProjects(), loadSessions()])
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to delete project'
      )
    }
  }

  const deleteSession = async (target: AgentSession) => {
    await client.deleteSession(target.id)
    let neighbor: string | null = null
    let scopeEmpty = false
    const scopeProjectId = activeProjectId
    setOpenTabsByProject(current => {
      let changed = false
      const next: Record<string, string[]> = {}
      for (const [key, ids] of Object.entries(current)) {
        if (!ids.includes(target.id) && key !== tabsScopeKey) {
          next[key] = ids
          continue
        }
        const withoutTarget = ids.filter(id => id !== target.id)
        const filtered =
          key === tabsScopeKey && scopeProjectId
            ? withoutTarget.filter(id => {
                const item = sessions.find(session => session.id === id)
                return Boolean(item && item.projectId === scopeProjectId)
              })
            : withoutTarget
        if (filtered.length !== ids.length) changed = true
        if (key === tabsScopeKey) {
          neighbor = filtered[0] || null
          scopeEmpty = filtered.length === 0
        }
        if (filtered.length > 0) next[key] = filtered
        else if (ids.length > 0) changed = true
      }
      if (!changed) return current
      writeOpenTabsByProject(next)
      return next
    })
    if (scopeEmpty) {
      setLastSessionByScope(current => {
        if (!(tabsScopeKey in current)) return current
        const next = { ...current }
        delete next[tabsScopeKey]
        writeLastSessionByScope(next)
        return next
      })
    }
    setChatBySessionId(current => {
      if (!current[target.id]) return current
      const next = { ...current }
      delete next[target.id]
      return next
    })
    await loadSessions()
    if (target.id === sessionId) {
      navigate(
        neighbor
          ? `/agents/${neighbor}`
          : scopeProjectId
            ? `/projects/${scopeProjectId}`
            : '/'
      )
    }
  }

  const openRenameDialog = (target: AgentSession) => {
    setRenameTarget(target)
    setRenameValue(target.title || '')
  }

  const submitRename = async () => {
    const title = renameValue.trim()
    if (!renameTarget || !title) return
    await updateSession(renameTarget, { title })
    setRenameTarget(null)
    setRenameValue('')
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    const target = deleteTarget
    setDeleteTarget(null)
    await deleteSession(target)
  }

  const exportTranscript = async (target: AgentSession) => {
    const transcript = await client.listMessages(target.id)
    const markdown = transcript
      .map(
        message =>
          `## ${
            message.role === 'assistant' ? 'Sandwalk' : message.role
          }\n\n${message.content}`
      )
      .join('\n\n---\n\n')
    const url = URL.createObjectURL(
      new Blob([markdown], { type: 'text/markdown' })
    )
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${target.title
      .replace(/[^a-z0-9]+/gi, '-')
      .toLowerCase()}.md`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const setComposer = useCallback(
    (value: string | ((current: string) => string)) => {
      if (!sessionId) return
      patchChat(sessionId, prev => ({
        ...prev,
        composer: typeof value === 'function' ? value(prev.composer) : value
      }))
    },
    [patchChat, sessionId]
  )

  const setComposerSkills = useCallback(
    (value: string[] | ((current: string[]) => string[])) => {
      if (!sessionId) return
      patchChat(sessionId, prev => ({
        ...prev,
        composerSkills:
          typeof value === 'function' ? value(prev.composerSkills) : value
      }))
    },
    [patchChat, sessionId]
  )

  const setComposerFiles = useCallback(
    (value: string[] | ((current: string[]) => string[])) => {
      if (!sessionId) return
      patchChat(sessionId, prev => ({
        ...prev,
        composerFiles:
          typeof value === 'function' ? value(prev.composerFiles) : value
      }))
    },
    [patchChat, sessionId]
  )

  useEffect(() => {
    const path = pendingMentionRef.current
    if (!sessionId || !path) return
    pendingMentionRef.current = null
    setComposer(current => `${current}${fileChipToken(path)}`)
    setComposerFiles([])
  }, [sessionId, setComposer, setComposerFiles])

  const displayedSessions = activeProjectId
    ? sessions.filter(item => item.projectId === activeProjectId)
    : sessions
  const sections = groupSessions(displayedSessions)
  const openTabs = openTabIds
    .map(id => sessions.find(item => item.id === id))
    .filter((item): item is AgentSession => Boolean(item))
    .filter(
      item => !activeProjectId || item.projectId === activeProjectId
    )
  const showSessionTabs =
    !isDashboard &&
    !isHome &&
    !isProjectHome &&
    !isSkills &&
    !isIntegrations &&
    (Boolean(sessionId) || openTabs.length > 0)
  const activeTitle = isDashboardOverview
    ? 'Overview'
    : isDashboardStatus
    ? 'Status'
    : isDashboardGeneral
    ? 'General'
    : isDashboardModels
    ? 'Models'
    : isDashboardData
    ? 'Datasets'
    : isDashboardTools
    ? 'Tools'
    : isDashboardDoctor
    ? 'Doctor'
    : isDashboardStorage
    ? 'Storage'
    : isDashboardEnvironment
    ? 'Environment'
    : isSkills
    ? 'Skills'
    : isIntegrations
    ? 'Integrations'
    : isDashboardMcp
    ? 'MCPs'
    : isHome || isProjectHome
    ? 'Home'
    : session?.title || 'New Chat'
  const canShowFilesPanel = Boolean(sessionId)
  const conversationTimeline = useMemo(
    () =>
      buildConversationTimeline({
        messages,
        tools,
        todosByRunId,
        runIdByMessageId,
        activeRunId
      }),
    [activeRunId, messages, runIdByMessageId, todosByRunId, tools]
  )
  const activeRunTodos = activeRunId ? todosByRunId[activeRunId] || [] : []
  const activeRunTools = activeRunId
    ? tools.filter(tool => tool.runId === activeRunId && !tool.messageId)
    : []

  if (!authBootstrapped && !needsAuthLogin) {
    return (
      <main className="grid min-h-full place-items-center bg-[#f5f5f5] dark:bg-neutral-950">
        <AuraIconPulse className="text-muted-foreground/50 h-12 w-12" />
      </main>
    )
  }

  if (needsAuthLogin) {
    return (
      <LoginView
        submitting={authLoggingIn || connecting}
        onSubmit={submitAuthLogin}
      />
    )
  }

  if (!health) {
    return (
      <main className="bg-background grid h-full place-items-center p-6">
        <form
          className="bg-card w-full max-w-lg rounded-xl border p-6"
          onSubmit={event => {
            event.preventDefault()
            void connect()
          }}
        >
          <div className="mb-6 flex items-center gap-3">
            <div className="bg-primary text-primary-foreground grid size-10 place-items-center rounded-lg">
              <SandwalkMark className="h-6 w-6" />
            </div>
            <div>
              <h1 className="font-semibold">Sandwalk</h1>
              <p className="text-muted-foreground text-sm">
                Connect to an agent backend
              </p>
            </div>
          </div>
          <Input
            value={backendUrl}
            onChange={event => setBackendUrl(event.target.value)}
          />
          <Input
            className="mt-2"
            type="password"
            value={backendApiKey}
            onChange={event => setBackendApiKey(event.target.value)}
            placeholder="Backend API key (remote servers only)"
          />
          {error ? (
            <p className="text-destructive mt-3 text-sm">{error}</p>
          ) : null}
          <Button className="mt-4 w-full" disabled={connecting}>
            {connecting ? <Loader2 className="animate-spin" /> : null}
            Connect
          </Button>
        </form>
      </main>
    )
  }

  return (
    <>
      <ResizablePanelGroup
        direction="horizontal"
        autoSaveId={SHELL_PANELS_AUTO_SAVE_ID}
        className="bg-background h-full w-full overflow-hidden"
      >
        <ResizablePanel
          id="sidebar"
          order={1}
          ref={sidebarPanelRef}
          collapsible
          collapsedSize={0}
          defaultSize={18}
          minSize={12}
          maxSize={30}
          onCollapse={() => setSidebarCollapsed(true)}
          onExpand={() => setSidebarCollapsed(false)}
          className="min-w-0"
        >
        <aside className="bg-sidebar flex h-full flex-col overflow-hidden">
          {isDashboard ? (
            <DashboardSidebar
              active={dashboardSection}
              userName={health?.userName ?? null}
              onCollapse={() => setSidebarCollapsed(true)}
            />
          ) : (
            <>
          <div className="shrink-0 p-3">
            <div className="mb-2 flex items-center gap-1">
              <button
                type="button"
                className="hover:bg-sidebar-accent/70 inline-flex size-8 shrink-0 items-center justify-center rounded-md"
                onClick={() => {
                  setProjectScopeId(null)
                  navigate('/')
                }}
                aria-label="Home"
                title="Home"
              >
                <SandwalkMark className="h-5 w-5" />
              </button>
              <ProjectSelector
                projects={projects}
                value={activeProjectId}
                onSelectAll={selectAllProjects}
                onSelectProject={selectProjectScope}
                onOpenSettings={() => setProjectSettingsOpen(true)}
                onNewProject={() => setNewProjectOpen(true)}
              />
              <div className="min-w-0 flex-1" />
              <TooltipProvider delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 shrink-0"
                      onClick={() => setGlobalSearchOpen(true)}
                      aria-label="Search"
                    >
                      <Search className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">Search ⌘K</TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 shrink-0"
                onClick={() => setSidebarCollapsed(true)}
                aria-label="Hide sidebar"
              >
                <PanelLeft className="size-4" />
              </Button>
            </div>
            <button
              type="button"
              className="text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground flex w-full items-center justify-between rounded-md px-2 py-1.5 text-[13px]"
              onClick={() => void createSession(activeProjectId)}
            >
              <span className="inline-flex items-center gap-2">
                <Send className="size-3.5" />
                New Agent
              </span>
              <span className="text-muted-foreground/70 text-[11px]">⌘N</span>
            </button>
            {canShowFilesPanel ? (
              <button
                type="button"
                className={cn(
                  'mt-1 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[13px]',
                  !filesPanelCollapsed
                    ? 'bg-sidebar-accent text-foreground'
                    : 'text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground'
                )}
                onClick={() => setFilesPanelCollapsed(current => !current)}
              >
                <Folder className="size-3.5" />
                Files
              </button>
            ) : null}
            <button
              type="button"
              className="text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground mt-1 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[13px]"
              onClick={() => navigate('/dashboard')}
            >
              <LayoutDashboard className="size-3.5" />
              Dashboard
            </button>
          </div>
          <ScrollArea className="flex-1">
            <div className="space-y-3 p-3">
              {sections.length === 0 ? (
                <p className="text-muted-foreground px-1.5 py-2 text-[13px]">
                  No Agents Yet
                </p>
              ) : (
              sections.map(section => {
                const collapsed = Boolean(collapsedSidebarSections[section.id])
                return (
                  <div key={section.id} className="space-y-1">
                    <button
                      type="button"
                      className="text-muted-foreground/80 hover:text-foreground flex w-full items-center gap-1 rounded-md px-1.5 py-0.5 text-left text-[13px]"
                      aria-expanded={!collapsed}
                      onClick={() =>
                        setCollapsedSidebarSections(current => ({
                          ...current,
                          [section.id]: !current[section.id]
                        }))
                      }
                    >
                      <ChevronDown
                        className={cn(
                          'size-3.5 shrink-0 transition-transform',
                          collapsed && '-rotate-90'
                        )}
                      />
                      <span className="min-w-0 flex-1 truncate">
                        {section.title}
                      </span>
                      <span className="text-muted-foreground/60 shrink-0 text-[11px] tabular-nums">
                        {section.items.length}
                      </span>
                    </button>
                    {!collapsed ? (
                      <ul className="space-y-0.5">
                        {section.items.map(item => (
                          <li key={item.id}>
                            <div
                              className={cn(
                                'hover:bg-sidebar-accent/70 group grid grid-cols-[minmax(0,1fr)_2.75rem] items-center rounded px-1.5 py-1.5',
                                item.id === sessionId && 'bg-sidebar-accent'
                              )}
                            >
                              <button
                                type="button"
                                className="flex min-w-0 items-center gap-1.5 text-left"
                                onClick={() => navigate(`/agents/${item.id}`)}
                              >
                                <SessionStatusIcon
                                  status={
                                    chatBySessionId[item.id]?.runActive
                                      ? 'running'
                                      : item.status
                                  }
                                />
                                {item.organizeLabel === 'pinned' ? (
                                  <Pin className="text-muted-foreground/70 size-3 shrink-0" />
                                ) : null}
                                <span className="text-foreground/90 group-hover:text-foreground truncate text-[13px]">
                                  {item.title || 'Untitled'}
                                </span>
                              </button>
                              <div className="relative h-7 w-11 justify-self-end">
                                <span
                                  className={cn(
                                    'text-muted-foreground/70 pointer-events-none absolute inset-0 flex items-center justify-end pr-0.5 text-[11px] transition-opacity',
                                    threadMenuOpenId === item.id
                                      ? 'opacity-0'
                                      : 'opacity-100 group-hover:opacity-0'
                                  )}
                                >
                                  {relativeTime(
                                    item.lastMessageAt || item.updatedAt
                                  )}
                                </span>
                                <Popover
                                  open={threadMenuOpenId === item.id}
                                  onOpenChange={open => {
                                    setThreadMenuOpenId(open ? item.id : null)
                                  }}
                                >
                                  <PopoverTrigger asChild>
                                    <button
                                      type="button"
                                      className={cn(
                                        'text-muted-foreground hover:bg-muted absolute right-0 top-0 inline-flex h-7 w-7 items-center justify-center rounded-md',
                                        threadMenuOpenId === item.id
                                          ? 'opacity-100'
                                          : 'opacity-0 group-hover:opacity-100'
                                      )}
                                      aria-label="Thread options"
                                    >
                                      <MoreHorizontal className="h-4 w-4" />
                                    </button>
                                  </PopoverTrigger>
                                  <PopoverContent
                                    align="start"
                                    className="w-44 p-1.5"
                                  >
                                    <SessionActionsMenu
                                      session={item}
                                      projects={projects}
                                      onRename={() => {
                                        setThreadMenuOpenId(null)
                                        openRenameDialog(item)
                                      }}
                                      onTogglePin={() => {
                                        setThreadMenuOpenId(null)
                                        void updateSession(item, {
                                          organizeLabel:
                                            item.organizeLabel === 'pinned'
                                              ? null
                                              : 'pinned'
                                        })
                                      }}
                                      onMoveToProject={projectId => {
                                        setThreadMenuOpenId(null)
                                        void updateSession(item, { projectId })
                                      }}
                                      onExport={() => {
                                        setThreadMenuOpenId(null)
                                        void exportTranscript(item)
                                      }}
                                      onInspect={() => {
                                        setThreadMenuOpenId(null)
                                        navigate(
                                          `/agents/${item.id}?inspect=1`
                                        )
                                      }}
                                      onArchive={() => {
                                        setThreadMenuOpenId(null)
                                        const nextLabel =
                                          item.organizeLabel === 'archive'
                                            ? null
                                            : 'archive'
                                        void updateSession(item, {
                                          organizeLabel: nextLabel
                                        })
                                        if (nextLabel === 'archive') {
                                          setCollapsedSidebarSections(
                                            current => ({
                                              ...current,
                                              archive: false
                                            })
                                          )
                                        }
                                      }}
                                      onDelete={() => {
                                        setThreadMenuOpenId(null)
                                        setDeleteTarget(item)
                                      }}
                                    />
                                  </PopoverContent>
                                </Popover>
                              </div>
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                )
              })
              )}
            </div>
          </ScrollArea>
          <div className="shrink-0 p-2">
            <SidebarUserMenu
              userName={health?.userName ?? null}
              onLogout={logoutSession}
            />
          </div>
            </>
          )}
        </aside>
        </ResizablePanel>

        <ResizableHandle
          className={cn(
            'w-px',
            sidebarCollapsed && 'pointer-events-none opacity-0'
          )}
        />

        <ResizablePanel
          id="main"
          order={2}
          defaultSize={82}
          minSize={40}
          className="min-w-0"
        >
        <div className="relative flex h-full min-w-0 flex-col">
          {showConnectionLimitWarning ? (
            <div className="border-border bg-amber-500/10 text-amber-950 dark:text-amber-100 flex shrink-0 items-start gap-3 border-b px-3 py-2 text-xs">
              <div className="min-w-0 flex-1">
                <p className="font-medium">
                  {runningCount} agents running at once
                </p>
                <p className="text-muted-foreground mt-0.5">
                  Browsers allow about 6 live connections to the local API. With
                  this many concurrent runs, opening files or switching chats
                  can stall. Prefer finishing some runs before starting more.
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 shrink-0 px-2 text-xs"
                onClick={() => setConnectionLimitDismissed(true)}
              >
                Dismiss
              </Button>
            </div>
          ) : null}
          {!showSessionTabs &&
          !(isHome || isProjectHome || isDashboard) ? (
            <div className="flex h-10 shrink-0 items-center gap-1 border-b px-1.5 md:px-2">
              {sidebarCollapsed ? (
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8 shrink-0"
                  onClick={() => setSidebarCollapsed(false)}
                  aria-label="Show sidebar"
                >
                  <PanelLeft className="size-4" />
                </Button>
              ) : null}
              <span className="min-w-0 flex-1 truncate px-2 text-sm font-medium">
                {activeTitle}
              </span>
            </div>
          ) : null}
          {(isHome || isProjectHome || isDashboard) && sidebarCollapsed ? (
            <div className="absolute left-2 top-2 z-20">
              <Button
                variant="ghost"
                size="icon"
                className="size-8 shrink-0"
                onClick={() => setSidebarCollapsed(false)}
                aria-label="Show sidebar"
              >
                <PanelLeft className="size-4" />
              </Button>
            </div>
          ) : null}

          {isDashboardOverview ? (
            <DashboardOverviewView sessions={sessions} />
          ) : isDashboardStatus ? (
            <ServerStatusView
              onLoad={loadServerStatus}
              onClearCache={signal => client.clearRuntimeCache(signal)}
            />
          ) : isDashboardGeneral ? (
            <GeneralView
              backendUrl={backendUrl}
              backendVersion={health?.version ?? null}
              connected={Boolean(health)}
              onCheckBackend={async () => {
                try {
                  const nextHealth = await client.health()
                  setHealth(nextHealth)
                  return true
                } catch {
                  setHealth(null)
                  return false
                }
              }}
              onUpdateBackendUrl={async url => {
                setBackendUrl(url)
                localStorage.setItem('fastfold.backend.url', url)
                const nextClient = new LocalAgentClient({
                  baseUrl: url,
                  apiKey: backendApiKey || undefined
                })
                try {
                  const nextHealth = await nextClient.health()
                  setHealth(nextHealth)
                  const [
                    nextSessions,
                    nextProjects,
                    nextSkills,
                    nextIntegrations,
                    nextMcpServers,
                    nextMcpCatalog,
                    settings,
                    nextModels
                  ] = await Promise.all([
                    nextClient.listSessions(),
                    nextClient.listProjects(),
                    nextClient.listSkills(),
                    nextClient.listIntegrations(),
                    nextClient.listMcpServers(),
                    nextClient.listMcpCatalog(),
                    nextClient.getRuntimeSettings(),
                    nextClient.listModels({
                      enabledOnly: true,
                      discover: true
                    })
                  ])
                  setSessions(nextSessions)
                  setProjects(nextProjects)
                  setSkills(nextSkills)
                  setIntegrations(nextIntegrations)
                  setMcpServers(nextMcpServers)
                  setMcpCatalog(nextMcpCatalog)
                  setRuntimeSettings(settings)
                  setModelOptions(toComposerModelOptions(nextModels))
                  return true
                } catch {
                  setHealth(null)
                  return false
                }
              }}
              onLoadAccount={loadAccount}
              onLogoutAccount={logoutAccount}
            />
          ) : isDashboardModels ? (
            <ModelsView
              integrations={integrations}
              onListModels={options => client.listModels(options)}
              onUpdateModelEnabled={async (modelId, enabled, signal) => {
                const updated = await client.updateModelEnabled(
                  modelId,
                  enabled,
                  signal
                )
                void loadModelOptions()
                return updated
              }}
              onCreateCustomModel={async (input, signal) => {
                const created = await client.createCustomModel(input, signal)
                void loadModelOptions()
                return created
              }}
              onDeleteCustomModel={async (modelId, signal) => {
                await client.deleteCustomModel(modelId, signal)
                void loadModelOptions()
              }}
              onListProfiles={signal => client.listModelProfiles({ signal })}
              onCreateProfile={async (input, signal) => {
                const created = await client.createModelProfile(input, signal)
                void loadModelOptions()
                return created
              }}
              onUpdateProfile={async (profileId, input, signal) => {
                const updated = await client.updateModelProfile(
                  profileId,
                  input,
                  signal
                )
                void loadModelOptions()
                return updated
              }}
              onDeleteProfile={async (profileId, signal) => {
                await client.deleteModelProfile(profileId, signal)
                void loadModelOptions()
              }}
              onProbeProfile={(profileId, signal) =>
                client.probeModelProfile(profileId, signal)
              }
              onSaveProviderKey={async (key, envVar, value) => {
                await client.updateIntegration(key, { [envVar]: value })
                await loadIntegrations()
                await loadModelOptions()
              }}
              onClearProviderKey={async key => {
                await client.removeIntegration(key)
                await loadIntegrations()
                await loadModelOptions()
              }}
            />
          ) : isDashboardData ? (
            <DataView
              onListDatasets={signal => client.listDatasets(signal)}
              onInstallDataset={(datasetId, signal) =>
                client.installDataset(datasetId, signal)
              }
            />
          ) : isDashboardTools ? (
            <ToolsView
              onListTools={signal => client.listTools({ signal })}
              onUpdateToolEnabled={(toolId, enabled, signal) =>
                client.updateToolEnabled(toolId, enabled, signal)
              }
              onBatchUpdateTools={(action, ids, signal) =>
                client.batchUpdateTools(action, ids, signal)
              }
              onListDatasets={signal => client.listDatasets(signal)}
              onOpenData={() => navigate('/dashboard/datasets')}
            />
          ) : isDashboardDoctor ? (
            <DoctorView
              onRun={signal => client.runDoctor(signal)}
              onDownloadDiagnostics={(uiDiagnostics, signal) =>
                client.downloadDiagnostics(uiDiagnostics, signal)
              }
            />
          ) : isDashboardStorage ? (
            <StorageView onLoad={loadStorage} />
          ) : isDashboardEnvironment ? (
            <EnvironmentView
              onLoad={loadEnvironment}
              onInstall={(name, options) =>
                client.installEnvironmentPackage(name, options)
              }
              onUninstall={(name, signal) =>
                client.uninstallEnvironmentPackage(name, signal)
              }
            />
          ) : isSkills ? (
            <SkillsView
              mode={skillsViewMode}
              skills={skills}
              loading={connecting && skills.length === 0}
              detail={skillDetail}
              catalogSkillRoute={catalogSkillRoute}
              catalogSearchEnabled={catalogSearchEnabled}
              openCatalogSearchInitially={isCatalogSearchPath}
              onOpen={name =>
                navigate(`/dashboard/skills/${encodeURIComponent(name)}`)
              }
              onOpenCatalogDetail={skill =>
                navigate(`/dashboard/skills/catalog/${skill.id}`)
              }
              onBack={() => navigate('/dashboard/skills')}
              onOpenImportGithub={() => navigate('/dashboard/skills/import/github')}
              onOpenImportFile={() => navigate('/dashboard/skills/import/file')}
              onOpenTrustedSources={() => navigate('/dashboard/skills/trusted/sources')}
              onOpenCatalogSetup={() => navigate('/dashboard/integrations/vercel')}
              onInstall={async source => {
                const installed = await client.installSkill(source)
                await loadSkills()
                return installed
              }}
              onUpload={async file => {
                await client.installSkillFile(file)
                await loadSkills()
              }}
              onLoadSuggestedSources={signal => client.listSkillSources(signal)}
              onSearchCatalog={(query, signal) =>
                client.searchSkillCatalog(query, 12, signal)
              }
              onGetCatalogDetail={(source, skill, signal) =>
                client.getCatalogSkillDetail(source, skill, signal)
              }
              onGetCatalogAudit={(source, skill, signal) =>
                client.getCatalogSkillAudit(source, skill, signal)
              }
              onBulkAction={async (action, names) => {
                const result = await client.bulkSkillAction(action, names)
                if (action === 'remove') {
                  setSkillDetail(current =>
                    current && result.succeeded.includes(current.name) ? null : current
                  )
                } else if (skillDetail && result.succeeded.includes(skillDetail.name)) {
                  const refreshed = await client.getSkill(skillDetail.name)
                  setSkillDetail(refreshed)
                }
                await loadSkills()
                return result
              }}
              onSetEnabled={async (name, enabled) => {
                const updated = await client.setSkillEnabled(name, enabled)
                setSkillDetail(current =>
                  current && current.name === name ? updated : current
                )
                await loadSkills()
              }}
              onRemove={async name => {
                await client.removeSkill(name)
                setSkillDetail(current =>
                  current && current.name === name ? null : current
                )
                await loadSkills()
              }}
            />
          ) : isIntegrations ? (
            <IntegrationsView
              terminalClient={client}
              integrations={integrations}
              loading={connecting && integrations.length === 0}
              selectedKey={selectedIntegrationKey}
              values={integrationValues}
              onValueChange={(envName, value) =>
                setIntegrationValues(current => ({
                  ...current,
                  [envName]: value
                }))
              }
              onSelect={key => {
                if (!key) {
                  navigate('/dashboard/integrations')
                  return
                }
                const target = integrations.find(item => item.key === key)
                const segment = (target?.name || key)
                  .trim()
                  .toLowerCase()
                  .replace(/[^a-z0-9]+/g, '-')
                  .replace(/^-+|-+$/g, '')
                navigate(
                  `/dashboard/integrations/${encodeURIComponent(segment || key)}`
                )
              }}
              onSave={async () => {
                if (!selectedIntegrationKey) return
                await client.updateIntegration(
                  selectedIntegrationKey,
                  integrationValues
                )
                setIntegrationValues({})
                await loadIntegrations()
              }}
              onValidate={async key => client.validateIntegration(key)}
              onAutofill={async key => {
                await client.autofillIntegration(key)
                await loadIntegrations()
              }}
              onSetup={async key => {
                const result = await client.setupIntegration(key)
                await loadIntegrations()
                return result
              }}
              onOpenVercelTerminal={async () => {
                const existing = sessions.find(item =>
                  String(item.workspacePath || '')
                    .trim()
                    .endsWith('/.fastfold-cli/vercel-integration')
                )
                if (existing) return existing.id
                const created = await client.createSession({
                  title: 'Vercel integration setup',
                  workspacePath: '~/.fastfold-cli/vercel-integration',
                  projectId: activeProjectId || undefined
                })
                await loadSessions()
                return created.id
              }}
              onRemove={async key => {
                await client.removeIntegration(key)
                if (selectedIntegrationKey === key) {
                  navigate('/dashboard/integrations', { replace: true })
                }
                await loadIntegrations()
              }}
            />
          ) : isDashboardMcp ? (
            <McpView
              mcpServers={mcpServers}
              catalog={mcpCatalog}
              catalogLoading={mcpCatalogLoading}
              onRefresh={refreshMcp}
              onConnectCatalog={async (catalogId, input) => {
                const result = await client.connectMcpCatalog(catalogId, input)
                await refreshMcp()
                await loadIntegrations()
                return result
              }}
              onToggleCatalog={async (entry, enabled) => {
                await client.setMcpCatalogEnabled(entry.id, enabled)
                await refreshMcp()
              }}
              onCreateMcp={async input => {
                await client.createMcpServer(input)
                await loadMcpServers()
              }}
              onDeleteMcp={async id => {
                await client.deleteMcpServer(id)
                await loadMcpServers()
              }}
              onToggleCustom={async (id, enabled) => {
                await client.updateMcpServer(id, { enabled })
                await loadMcpServers()
              }}
            />
          ) : isHome || isProjectHome ? (
            <HomeView
              projects={projects}
              sessions={sessions}
              previews={sessionPreviews}
              userName={health.userName}
              activeProjectId={activeProjectId}
              onCreateProject={() => setNewProjectOpen(true)}
              onCreateSession={projectId => void createSession(projectId)}
              onOpenProject={id => {
                setProjectScopeId(id)
                navigate(`/projects/${id}`)
              }}
              onOpenSession={id => navigate(`/agents/${id}`)}
              onTogglePinProject={project => void togglePinProject(project)}
              onDeleteProject={project => void deleteProject(project)}
            />
          ) : (
            <ResizablePanelGroup
              direction="horizontal"
              autoSaveId={SESSION_PANELS_AUTO_SAVE_ID}
              className="min-h-0 flex-1"
            >
              <ResizablePanel
                id="chat"
                order={1}
                defaultSize={65}
                minSize={30}
                className="min-w-0"
              >
              <main className="relative flex h-full min-w-0 flex-col">
                <div className="flex h-10 shrink-0 items-center gap-1 px-1.5 md:px-2">
                  {sidebarCollapsed ? (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 shrink-0"
                      onClick={() => setSidebarCollapsed(false)}
                      aria-label="Show sidebar"
                    >
                      <PanelLeft className="size-4" />
                    </Button>
                  ) : null}
                  <SessionTabs
                    tabs={openTabs}
                    activeId={sessionId}
                    onSelect={id => navigate(`/agents/${id}`)}
                    onClose={closeSessionTab}
                    onCloseOthers={closeOtherSessionTabs}
                    onRename={openRenameDialog}
                    onTogglePin={item =>
                      void updateSession(item, {
                        organizeLabel:
                          item.organizeLabel === 'pinned' ? null : 'pinned'
                      })
                    }
                    onExport={item => void exportTranscript(item)}
                    onInspect={item => navigate(`/agents/${item.id}?inspect=1`)}
                    onArchive={item =>
                      void updateSession(item, {
                        organizeLabel:
                          item.organizeLabel === 'archive' ? null : 'archive'
                      })
                    }
                    onDelete={item => setDeleteTarget(item)}
                  />
                  <div className="ml-auto flex shrink-0 items-center gap-0.5">
                    {session?.projectId
                      ? (() => {
                          const projectName =
                            projects.find(p => p.id === session.projectId)
                              ?.name || null
                          if (!projectName) return null
                          return (
                            <button
                              type="button"
                              className="text-muted-foreground hover:text-foreground mr-1 inline-flex max-w-[12rem] items-center gap-1.5 rounded-md px-1.5 py-1 text-xs"
                              title={projectName}
                              onClick={() =>
                                selectProjectScope(session.projectId!)
                              }
                            >
                              <Folder className="size-3.5 shrink-0" />
                              <span className="truncate">{projectName}</span>
                            </button>
                          )
                        })()
                      : null}
                    <Popover
                      open={cliMenuOpen}
                      onOpenChange={open => {
                        setCliMenuOpen(open)
                        if (!open) setCopiedResumeCommand(false)
                      }}
                    >
                      <PopoverTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="size-8"
                          aria-label="Resume in Agent CLI"
                          title="Resume in Agent CLI"
                          disabled={!sessionId}
                        >
                          <Terminal className="size-4" />
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent
                        align="end"
                        className="w-[22rem] overflow-hidden p-0"
                      >
                        <div className="px-4 pt-3">
                          <p className="text-foreground text-sm font-semibold">
                            Resume in Agent CLI
                          </p>
                        </div>
                        <div className="px-4 pb-3 pt-2">
                          <div className="border-border/80 bg-muted/35 flex items-center gap-2 rounded-lg border p-2.5">
                            <Terminal className="text-muted-foreground size-4 shrink-0" />
                            <code className="min-w-0 flex-1 truncate font-mono text-[13px]">
                              {sessionId
                                ? `fastfold --resume ${sessionId}`
                                : 'fastfold --resume <chat_id>'}
                            </code>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="size-7 shrink-0 rounded-md"
                              disabled={!sessionId}
                              onClick={() => {
                                if (!sessionId) return
                                void navigator.clipboard.writeText(
                                  `fastfold --resume ${sessionId}`
                                )
                                setCopiedResumeCommand(true)
                                window.setTimeout(
                                  () => setCopiedResumeCommand(false),
                                  2000
                                )
                              }}
                              aria-label="Copy resume command"
                              title="Copy resume command"
                            >
                              {copiedResumeCommand ? (
                                <Check className="size-3.5" />
                              ) : (
                                <Copy className="size-3.5" />
                              )}
                            </Button>
                          </div>
                          <p className="text-muted-foreground mt-2 text-xs">
                            Continue this session in your local{' '}
                            <a
                              href="https://docs.fastfold.ai/agents/cli"
                              target="_blank"
                              rel="noreferrer"
                              className="underline underline-offset-2 hover:text-foreground"
                            >
                              Fastfold Agent CLI
                            </a>
                            .
                          </p>
                        </div>
                        <div className="border-border/70 border-t px-4 py-3">
                          <Button
                            type="button"
                            variant="ghost"
                            className="h-10 w-full justify-start gap-2 rounded-lg px-3 text-sm"
                            disabled={!session}
                            onClick={() => {
                              if (!session) return
                              void exportTranscript(session)
                              setCliMenuOpen(false)
                            }}
                          >
                            <Download className="size-4" />
                            Export transcript
                          </Button>
                        </div>
                      </PopoverContent>
                    </Popover>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      disabled={!sessionId}
                      onClick={() => {
                        if (terminalOpen) {
                          setTerminalOpen(false)
                          return
                        }
                        setFilesPanelCollapsed(false)
                        setTerminalOpen(true)
                      }}
                      aria-label={
                        terminalOpen ? 'Hide terminal' : 'Show terminal'
                      }
                      title={terminalOpen ? 'Hide terminal' : 'Show terminal'}
                    >
                      <SquareTerminal
                        className={cn(
                          'size-4',
                          terminalOpen && 'text-foreground'
                        )}
                      />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      onClick={() =>
                        setFilesPanelCollapsed(current => !current)
                      }
                      aria-label={
                        filesPanelCollapsed
                          ? 'Show files panel'
                          : 'Hide files panel'
                      }
                      title={
                        filesPanelCollapsed
                          ? 'Show files panel'
                          : 'Hide files panel'
                      }
                    >
                      <PanelRight
                        className={cn(
                          'size-4',
                          !filesPanelCollapsed && 'text-foreground'
                        )}
                      />
                    </Button>
                  </div>
                </div>
                {isInspect ? (
                  <InspectView
                    messages={messages}
                    tools={tools}
                    onClose={() => navigate(`/agents/${sessionId}`)}
                  />
                ) : null}
                <div
                  className={cn(
                    'flex min-h-0 flex-1 flex-col',
                    isInspect && 'hidden'
                  )}
                >
                  {!messagesLoaded && !runActive ? (
                    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                      <ChatPageSkeleton />
                    </div>
                  ) : messages.length === 0 && !runActive ? (
                    <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-5 pb-20">
                      <AuraIconPulse className="text-muted-foreground/70 mb-6 h-12 w-12" />
                      <div className="bg-background w-full max-w-[44rem]">
                        <div className="mb-2 flex items-center px-1">
                          <ProjectPicker
                            projects={projects}
                            value={session?.projectId ?? activeProjectId}
                            recentIds={recentProjectIds}
                            noneLabel="All"
                            onNewProject={() => setNewProjectOpen(true)}
                            onChange={projectId => {
                              if (session) {
                                void updateSession(session, { projectId })
                              }
                              if (projectId) selectProjectScope(projectId)
                              else selectAllProjects()
                            }}
                          />
                        </div>
                        <Composer
                          value={composer}
                          running={runActive}
                          skills={skills}
                          skillChips={composerSkills}
                          fileChips={composerFiles}
                          workspaceFiles={workspaceFiles}
                          modelOptions={modelOptions}
                          showAura={false}
                          onChange={setComposer}
                          onSkillChipsChange={setComposerSkills}
                          onFileChipsChange={setComposerFiles}
                          onOpenFile={path => {
                            setFilesPanelCollapsed(false)
                            setPendingOpenPath(path)
                          }}
                          onSend={() => void sendMessage()}
                          onStop={() =>
                            sessionId && void client.interrupt(sessionId)
                          }
                          onLoadSkill={loadSkillDetail}
                          onUpload={async files => {
                            if (!sessionId) return
                            await Promise.all(
                              Array.from(files).map(file =>
                                client.uploadFile(sessionId, file)
                              )
                            )
                            setWorkspaceVersion(current => current + 1)
                          }}
                          runtimeSettings={runtimeSettings}
                          tokenUsage={tokenUsage}
                          onModelSelect={async (provider, model, profileId) => {
                            if (profileId) {
                              try {
                                await client.updateModelProfile(profileId, {
                                  setActive: true
                                })
                              } catch {
                                // Profile activation is best-effort for local models.
                              }
                            }
                            // Local profile models are labeled provider=local in the
                            // catalog, but the runtime still speaks OpenAI-compatible.
                            const runtimeProvider =
                              provider === 'local' || profileId ? 'openai' : provider
                            setRuntimeSettings(
                              await client.updateRuntimeSettings({
                                provider: runtimeProvider,
                                model
                              })
                            )
                          }}
                        />
                      </div>
                    </div>
                  ) : (
                    <>
                      <ScrollArea className="chat-scrollbar min-h-0 flex-1">
                        <div className="mx-auto flex w-full max-w-[44rem] flex-col px-5 py-6">
                          <div className="mb-4 flex min-w-0 flex-1 flex-col gap-y-2 empty:hidden">
                            {(() => {
                              const items: Array<
                                | {
                                    kind: 'entry'
                                    key: string
                                    entry: (typeof conversationTimeline)[number]
                                  }
                                | {
                                    kind: 'tool_run'
                                    key: string
                                    tools: TranscriptTool[]
                                  }
                              > = []
                              let cursor = 0
                              while (cursor < conversationTimeline.length) {
                                const entry = conversationTimeline[cursor]
                                if (entry.kind !== 'tool') {
                                  items.push({
                                    kind: 'entry',
                                    key: `${entry.kind}-${cursor}`,
                                    entry
                                  })
                                  cursor += 1
                                  continue
                                }
                                const runTools: TranscriptTool[] = []
                                while (
                                  cursor < conversationTimeline.length &&
                                  conversationTimeline[cursor].kind === 'tool'
                                ) {
                                  const toolEntry = conversationTimeline[cursor]
                                  if (toolEntry.kind === 'tool') {
                                    runTools.push(toolEntry.tool)
                                  }
                                  cursor += 1
                                }
                                if (runTools.length > TOOL_RUN_VISIBLE_COUNT) {
                                  items.push({
                                    kind: 'tool_run',
                                    key: `tool-run-${
                                      runTools[0]?.id || cursor
                                    }`,
                                    tools: runTools
                                  })
                                } else {
                                  runTools.forEach((tool, index) => {
                                    items.push({
                                      kind: 'entry',
                                      key: `tool-${tool.id}-${index}`,
                                      entry: { kind: 'tool', tool }
                                    })
                                  })
                                }
                              }

                              return items.map(timelineItem => {
                                if (timelineItem.kind === 'tool_run') {
                                  const isExpanded =
                                    expandedToolRunKeys[timelineItem.key] ===
                                    true
                                  const visibleTools = isExpanded
                                    ? timelineItem.tools
                                    : timelineItem.tools.slice(
                                        -TOOL_RUN_VISIBLE_COUNT
                                      )
                                  const hiddenCount = Math.max(
                                    0,
                                    timelineItem.tools.length -
                                      TOOL_RUN_VISIBLE_COUNT
                                  )
                                  return (
                                    <div
                                      key={timelineItem.key}
                                      className="space-y-1"
                                    >
                                      {hiddenCount > 0 ? (
                                        <div className="mx-auto w-full max-w-[44rem] px-2">
                                          <button
                                            type="button"
                                            className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex h-7 items-center gap-1 rounded-md px-1.5 text-xs"
                                            onClick={() => {
                                              if (!sessionId) return
                                              patchChat(sessionId, prev => ({
                                                ...prev,
                                                expandedToolRunKeys: {
                                                  ...prev.expandedToolRunKeys,
                                                  [timelineItem.key]:
                                                    !isExpanded
                                                }
                                              }))
                                            }}
                                          >
                                            {isExpanded ? (
                                              <ChevronDown className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
                                            ) : (
                                              <ChevronRight className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
                                            )}
                                            <span>
                                              {isExpanded
                                                ? 'Show less'
                                                : `Show more (${hiddenCount})`}
                                            </span>
                                          </button>
                                        </div>
                                      ) : null}
                                      {visibleTools.map(tool => (
                                        <div
                                          key={tool.id}
                                          className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
                                        >
                                          <ToolCard
                                            tool={tool}
                                            isRunning={runActive}
                                            onStop={
                                              sessionId
                                                ? () =>
                                                    void client.interrupt(
                                                      sessionId
                                                    )
                                                : undefined
                                            }
                                          />
                                        </div>
                                      ))}
                                    </div>
                                  )
                                }

                                const entry = timelineItem.entry
                                if (entry.kind === 'thought') {
                                  const turnTools = tools.filter(
                                    tool =>
                                      tool.messageId === entry.message.id ||
                                      (runIdByMessageId[entry.message.id] &&
                                        tool.runId ===
                                          runIdByMessageId[entry.message.id])
                                  )
                                  const duration =
                                    thoughtDurationForTools(turnTools)
                                  return (
                                    <div
                                      key={timelineItem.key}
                                      className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
                                    >
                                      <ReasoningGhost
                                        id={entry.message.id}
                                        label={
                                          duration
                                            ? `Thought for ${duration}`
                                            : 'Thought'
                                        }
                                        thought={entry.thought}
                                      />
                                    </div>
                                  )
                                }

                                if (entry.kind === 'tool') {
                                  return (
                                    <div
                                      key={timelineItem.key}
                                      className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
                                    >
                                      <ToolCard
                                        tool={entry.tool}
                                        isRunning={runActive}
                                        onStop={
                                          sessionId
                                            ? () =>
                                                void client.interrupt(sessionId)
                                            : undefined
                                        }
                                      />
                                    </div>
                                  )
                                }

                                if (entry.kind === 'todos') {
                                  return (
                                    <div
                                      key={timelineItem.key}
                                      className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
                                    >
                                      <TodoListInline
                                        todos={entry.todos}
                                        className="mt-1"
                                      />
                                    </div>
                                  )
                                }

                                const message = entry.message
                                const isUser = message.role === 'user'
                                const isAssistant = message.role === 'assistant'
                                const messagePopoverDate =
                                  formatMessagePopoverDate(message.createdAt)
                                const messageRunId =
                                  runIdByMessageId[message.id] || null
                                const messageUsage =
                                  (messageRunId &&
                                    usageByRunId[messageRunId]) ||
                                  null
                                const hideActionsWhileStreaming =
                                  runActive &&
                                  isAssistant &&
                                  message.id === messages.at(-1)?.id

                                return (
                                  <div
                                    key={timelineItem.key}
                                    className={cn(
                                      'fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] duration-150',
                                      isUser ? 'flex justify-end px-2' : ''
                                    )}
                                  >
                                    {isUser ? (
                                      <div className="relative min-w-0 max-w-[85%]">
                                        <div className="bg-muted text-foreground peer inline-block w-auto max-w-full break-words rounded-xl px-4 py-2">
                                          <UserMessageContent
                                            content={entry.content}
                                            onOpenFile={path => {
                                              setFilesPanelCollapsed(false)
                                              setPendingOpenPath(path)
                                            }}
                                          />
                                        </div>
                                      </div>
                                    ) : (
                                      <div
                                        className={cn(
                                          'text-foreground min-w-0 break-words px-2 leading-relaxed',
                                          message.role === 'system' &&
                                            'border-border/70 text-muted-foreground rounded-xl border'
                                        )}
                                      >
                                        {entry.content.trim() ? (
                                          <MarkdownContent
                                            content={entry.content}
                                            className="max-w-full [&_*]:max-w-full [&_pre]:w-full [&_pre]:max-w-full [&_pre_code]:whitespace-pre-wrap [&_table]:w-full [&_table]:table-auto"
                                          />
                                        ) : null}
                                        {isAssistant &&
                                        entry.content &&
                                        !hideActionsWhileStreaming ? (
                                          <div className="text-muted-foreground -mb-7.5 min-h-7.5 -ml-1 flex items-center gap-1 pt-1.5">
                                            <button
                                              type="button"
                                              className="hover:bg-muted inline-flex h-7 w-7 items-center justify-center rounded-md"
                                              onClick={async () => {
                                                await navigator.clipboard.writeText(
                                                  message.content
                                                )
                                                setCopiedMessageId(message.id)
                                                window.setTimeout(() => {
                                                  setCopiedMessageId(current =>
                                                    current === message.id
                                                      ? null
                                                      : current
                                                  )
                                                }, 1200)
                                              }}
                                              aria-label="Copy message"
                                            >
                                              {copiedMessageId ===
                                              message.id ? (
                                                <Check className="size-4" />
                                              ) : (
                                                <Copy className="size-4" />
                                              )}
                                            </button>
                                            <Popover>
                                              <PopoverTrigger asChild>
                                                <button
                                                  type="button"
                                                  className="hover:bg-muted inline-flex h-7 w-7 items-center justify-center rounded-md"
                                                  aria-label="More actions"
                                                >
                                                  <MoreHorizontal className="size-4" />
                                                </button>
                                              </PopoverTrigger>
                                              <PopoverContent
                                                align="start"
                                                className="w-48 p-1.5"
                                              >
                                                {messagePopoverDate ? (
                                                  <div className="text-muted-foreground border-border/50 mb-1 border-b px-2 pb-1.5 pt-1 text-xs">
                                                    {messagePopoverDate}
                                                  </div>
                                                ) : null}
                                                <div className="text-muted-foreground border-border/50 mb-1 border-b px-2 pb-1.5 pt-1 text-xs tabular-nums">
                                                  <div className="flex items-center justify-between gap-3">
                                                    <span>↑ Input</span>
                                                    <span className="text-foreground">
                                                      {(
                                                        messageUsage?.inputTokens ??
                                                        0
                                                      ).toLocaleString()}
                                                    </span>
                                                  </div>
                                                  <div className="mt-0.5 flex items-center justify-between gap-3">
                                                    <span>↓ Output</span>
                                                    <span className="text-foreground">
                                                      {(
                                                        messageUsage?.outputTokens ??
                                                        0
                                                      ).toLocaleString()}
                                                    </span>
                                                  </div>
                                                </div>
                                                <button
                                                  type="button"
                                                  className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                                                  onClick={() =>
                                                    downloadMarkdown(
                                                      `${
                                                        session?.title ||
                                                        'assistant-reply'
                                                      }-${message.id.slice(
                                                        0,
                                                        8
                                                      )}.md`,
                                                      message.content
                                                    )
                                                  }
                                                >
                                                  <Download className="size-4" />
                                                  Export Markdown
                                                </button>
                                              </PopoverContent>
                                            </Popover>
                                          </div>
                                        ) : null}
                                      </div>
                                    )}
                                  </div>
                                )
                              })
                            })()}
                            {activeRunTools.length > 0 ? (
                              <div className="space-y-1">
                                {activeRunTools.map(tool => (
                                  <div
                                    key={`active-${tool.id}`}
                                    className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
                                  >
                                    <ToolCard
                                      tool={tool}
                                      isRunning={runActive}
                                      onStop={
                                        sessionId
                                          ? () =>
                                              void client.interrupt(sessionId)
                                          : undefined
                                      }
                                    />
                                  </div>
                                ))}
                              </div>
                            ) : null}
                            {activeRunTodos.length > 0 ? (
                              <div className="mx-auto w-full max-w-[44rem] px-2">
                                <TodoListInline todos={activeRunTodos} />
                              </div>
                            ) : null}
                            {liveDelta ? (
                              <div className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150">
                                <MarkdownContent
                                  content={liveDelta}
                                  className="max-w-full [&_*]:max-w-full"
                                />
                              </div>
                            ) : null}
                            {runActive && !liveDelta ? (
                              <div className="text-muted-foreground mx-auto flex w-full max-w-[44rem] items-center gap-1 px-2 py-2 text-sm">
                                <div className="bg-foreground/80 animate-breathe h-2.5 w-2.5 rounded-full" />
                                <span className="sr-only">Generating</span>
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </ScrollArea>
                      <div className="bg-background mx-auto w-full max-w-[44rem] shrink-0 px-5 pb-6 pt-2">
                        <Composer
                          value={composer}
                          running={runActive}
                          skills={skills}
                          skillChips={composerSkills}
                          fileChips={composerFiles}
                          workspaceFiles={workspaceFiles}
                          modelOptions={modelOptions}
                          showAura={false}
                          onChange={setComposer}
                          onSkillChipsChange={setComposerSkills}
                          onFileChipsChange={setComposerFiles}
                          onOpenFile={path => {
                            setFilesPanelCollapsed(false)
                            setPendingOpenPath(path)
                          }}
                          onSend={() => void sendMessage()}
                          onStop={() =>
                            sessionId && void client.interrupt(sessionId)
                          }
                          onLoadSkill={loadSkillDetail}
                          onUpload={async files => {
                            if (!sessionId) return
                            await Promise.all(
                              Array.from(files).map(file =>
                                client.uploadFile(sessionId, file)
                              )
                            )
                            setWorkspaceVersion(current => current + 1)
                          }}
                          runtimeSettings={runtimeSettings}
                          tokenUsage={tokenUsage}
                          onModelSelect={async (provider, model, profileId) => {
                            if (profileId) {
                              try {
                                await client.updateModelProfile(profileId, {
                                  setActive: true
                                })
                              } catch {
                                // Profile activation is best-effort for local models.
                              }
                            }
                            const runtimeProvider =
                              provider === 'local' || profileId ? 'openai' : provider
                            setRuntimeSettings(
                              await client.updateRuntimeSettings({
                                provider: runtimeProvider,
                                model
                              })
                            )
                          }}
                        />
                      </div>
                    </>
                  )}
                </div>
                {error ? (
                  <div className="bg-destructive text-destructive-foreground absolute bottom-2 left-1/2 -translate-x-1/2 rounded-md px-3 py-1.5 text-xs">
                    {error}
                  </div>
                ) : null}
              </main>
              </ResizablePanel>
              {canShowFilesPanel ? (
                <>
                  <ResizableHandle
                    className={cn(
                      'w-px',
                      filesPanelCollapsed && 'pointer-events-none opacity-0'
                    )}
                  />
                  <ResizablePanel
                    id="files"
                    order={2}
                    ref={filesPanelRef}
                    collapsible
                    collapsedSize={0}
                    defaultSize={35}
                    minSize={20}
                    maxSize={55}
                    onCollapse={() => setFilesPanelCollapsed(true)}
                    onExpand={() => setFilesPanelCollapsed(false)}
                    className="min-w-0"
                  >
                    {sessionId ? (
                      <WorkspacePanel
                        key={sessionId}
                        client={client}
                        sessionId={sessionId}
                        workspaceVersion={workspaceVersion}
                        openPathRequest={pendingOpenPath}
                        onOpenPathRequestHandled={() => setPendingOpenPath(null)}
                        onAddToChat={path => {
                          setComposer(current => `${current}${fileChipToken(path)}`)
                          setComposerFiles([])
                        }}
                        onTogglePanel={() => setFilesPanelCollapsed(true)}
                        terminalOpen={terminalOpen}
                        onCloseTerminal={() => setTerminalOpen(false)}
                        onOpenTerminal={() => setTerminalOpen(true)}
                      />
                    ) : null}
                  </ResizablePanel>
                </>
              ) : null}
            </ResizablePanelGroup>
          )}
        </div>
        </ResizablePanel>
      </ResizablePanelGroup>

      <GlobalSearchDialog
        open={globalSearchOpen}
        onOpenChange={setGlobalSearchOpen}
        client={client}
        sessions={sessions}
        currentSessionId={sessionId}
        currentSessionTitle={session?.title || activeProject?.name}
        workspaceFiles={workspaceFiles}
        onOpenSession={id => {
          openSessionTab(id)
          navigate(`/agents/${id}`)
        }}
        onOpenArtifact={(targetSessionId, path) => {
          openSessionTab(targetSessionId)
          setFilesPanelCollapsed(false)
          setPendingOpenPath(path)
          navigate(`/agents/${targetSessionId}`)
        }}
        onMentionArtifact={(targetSessionId, path) => {
          pendingMentionRef.current = path
          openSessionTab(targetSessionId)
          if (targetSessionId === sessionId) {
            setComposer(current => `${current}${fileChipToken(path)}`)
            setComposerFiles([])
            pendingMentionRef.current = null
          } else {
            navigate(`/agents/${targetSessionId}`)
          }
        }}
        onCreateSession={() => void createSession(activeProjectId)}
        onNavigate={path => navigate(path)}
      />

      <NewProjectDialog
        open={newProjectOpen}
        onOpenChange={setNewProjectOpen}
        onCreate={createProject}
      />

      <ProjectSettingsDialog
        project={activeProject}
        open={projectSettingsOpen}
        onOpenChange={setProjectSettingsOpen}
        onSave={saveProjectSettings}
      />

      <Dialog
        open={Boolean(renameTarget)}
        onOpenChange={open => {
          if (!open) {
            setRenameTarget(null)
            setRenameValue('')
          }
        }}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Rename chat</DialogTitle>
            <DialogDescription>
              Choose a clearer name for this agent session.
            </DialogDescription>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={event => setRenameValue(event.target.value)}
            placeholder="Chat name"
            autoFocus
            maxLength={140}
            onKeyDown={event => {
              if (event.key === 'Enter') {
                event.preventDefault()
                void submitRename()
              }
            }}
          />
          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setRenameTarget(null)
                setRenameValue('')
              }}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => void submitRename()}
              disabled={!renameValue.trim()}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={Boolean(deleteTarget)}
        onOpenChange={open => {
          if (!open) setDeleteTarget(null)
        }}
      >
        <AlertDialogContent className="max-w-sm">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete chat?</AlertDialogTitle>
            <AlertDialogDescription>
              Delete “{deleteTarget?.title || 'Untitled session'}”? This cannot
              be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => void confirmDelete()}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

function SessionActionsMenu({
  session,
  projects,
  onRename,
  onTogglePin,
  onMoveToProject,
  onExport,
  onInspect,
  onArchive,
  onDelete
}: {
  session: AgentSession
  projects: AgentProject[]
  onRename: () => void
  onTogglePin: () => void
  onMoveToProject: (projectId: string | null) => void
  onExport: () => void
  onInspect: () => void
  onArchive: () => void
  onDelete: () => void
}) {
  return (
    <>
      <button
        type="button"
        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
        onClick={onRename}
      >
        <Pencil className="h-3.5 w-3.5" />
        Rename
      </button>
      <ProjectPicker
        projects={projects}
        value={session.projectId}
        noneLabel="No project"
        trigger={
          <button
            type="button"
            className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
          >
            <Folder className="h-3.5 w-3.5" />
            Move to project…
          </button>
        }
        onChange={onMoveToProject}
      />
      <button
        type="button"
        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
        onClick={onTogglePin}
      >
        <Pin className="h-3.5 w-3.5" />
        {session.organizeLabel === 'pinned' ? 'Unpin' : 'Pin'}
      </button>
      <button
        type="button"
        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
        onClick={onExport}
      >
        <Download className="h-3.5 w-3.5" />
        Export transcript
      </button>
      <button
        type="button"
        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
        onClick={onInspect}
      >
        <Search className="h-3.5 w-3.5" />
        Inspect chat
      </button>
      <button
        type="button"
        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
        onClick={onArchive}
      >
        <Archive className="h-3.5 w-3.5" />
        {session.organizeLabel === 'archive' ? 'Unarchive' : 'Archive'}
      </button>
      <button
        type="button"
        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-950/20"
        onClick={onDelete}
      >
        <Trash2 className="h-3.5 w-3.5" />
        Delete
      </button>
    </>
  )
}

function HomeView({
  projects,
  sessions,
  previews,
  userName,
  activeProjectId,
  onCreateProject,
  onCreateSession,
  onOpenProject,
  onOpenSession,
  onTogglePinProject,
  onDeleteProject
}: {
  projects: AgentProject[]
  sessions: AgentSession[]
  previews: Record<string, string>
  userName: string | null
  activeProjectId: string | null
  onCreateProject: () => void
  onCreateSession: (projectId: string | null) => void
  onOpenProject: (id: string) => void
  onOpenSession: (id: string) => void
  onTogglePinProject: (project: AgentProject) => void
  onDeleteProject: (project: AgentProject) => void
}) {
  const hour = new Date().getHours()
  const greeting =
    hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  const activeProject =
    projects.find(project => project.id === activeProjectId) || null
  const recent = sessions
    .filter(
      item =>
        item.organizeLabel !== 'archive' &&
        (!activeProjectId || item.projectId === activeProjectId)
    )
    .slice(0, activeProjectId ? 20 : 8)
  const projectNames = new Map(
    projects.map(project => [project.id, project.name])
  )
  const orderedProjects = [...projects].sort(
    (a, b) =>
      Number(b.pinned) - Number(a.pinned) ||
      new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  )

  if (activeProject) {
    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto w-full max-w-5xl px-6 py-8 md:px-10">
          <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <h2 className="truncate text-xl font-semibold">
                {activeProject.name}
              </h2>
              <p className="text-muted-foreground mt-1 text-sm">
                {activeProject.description ||
                  'Pick up where you left off or start something new.'}
              </p>
            </div>
            {recent.length > 0 ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onCreateSession(activeProject.id)}
              >
                <Plus className="size-3.5" />
                New Agent
              </Button>
            ) : null}
          </div>
          <section>
            <h3 className="mb-3 text-sm font-medium">Recent sessions</h3>
            {recent.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {recent.map(item => (
                  <button
                    key={item.id}
                    type="button"
                    className="bg-card hover:bg-muted/40 flex min-h-[8.5rem] flex-col rounded-xl border p-4 text-left transition-colors"
                    onClick={() => onOpenSession(item.id)}
                    title={previews[item.id] || undefined}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <span className="line-clamp-2 text-sm font-medium">
                        {item.title || 'Untitled'}
                      </span>
                      <span className="text-muted-foreground shrink-0 text-xs">
                        {relativeTime(item.lastMessageAt || item.updatedAt)}
                      </span>
                    </div>
                    <p className="text-muted-foreground mt-2 line-clamp-3 flex-1 text-xs leading-relaxed">
                      {previews[item.id] || 'No messages yet'}
                    </p>
                  </button>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center px-4 py-14 text-center">
                <AuraIconPulse className="text-muted-foreground/40 mb-4 h-10 w-10" />
                <p className="text-muted-foreground text-sm">No sessions here</p>
                <Button
                  variant="ghost"
                  className="mt-2"
                  onClick={() => onCreateSession(activeProject.id)}
                >
                  <Plus className="size-3.5" />
                  New Agent
                </Button>
              </div>
            )}
          </section>
        </div>
      </ScrollArea>
    )
  }

  if (recent.length === 0 && orderedProjects.length === 0) {
    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto w-full max-w-3xl px-6 py-8 md:px-10">
          <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <h2 className="text-xl font-semibold">
                {greeting}
                {userName ? `, ${userName}` : ''}
              </h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Pick up where you left off or start something new.
              </p>
            </div>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={onCreateProject}>
                <Plus className="size-3.5" />
                New project
              </Button>
            </div>
          </div>
          <section>
            <h3 className="mb-3 text-sm font-medium">Recent sessions</h3>
            <div className="flex flex-col items-center px-4 py-14 text-center">
              <AuraIconPulse className="text-muted-foreground/40 mb-4 h-10 w-10" />
              <p className="text-muted-foreground text-sm">No sessions here</p>
              <Button
                variant="ghost"
                className="mt-2"
                onClick={() => onCreateSession(null)}
              >
                <Plus className="size-3.5" />
                New Agent
              </Button>
            </div>
          </section>
        </div>
      </ScrollArea>
    )
  }

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-6xl px-6 py-8 md:px-10">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">
              {greeting}
              {userName ? `, ${userName}` : ''}
            </h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Pick up where you left off or start something new.
            </p>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" onClick={onCreateProject}>
              <Plus className="size-3.5" />
              New project
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onCreateSession(null)}
            >
              <Plus className="size-3.5" />
              New Agent
            </Button>
          </div>
        </div>
        <div className="grid gap-8 lg:grid-cols-2">
          <section>
            <h3 className="mb-3 text-sm font-medium">Projects</h3>
            <div className="bg-card divide-y rounded-xl border">
              {orderedProjects.length > 0 ? (
                orderedProjects.map(project => (
                  <div
                    key={project.id}
                    className="hover:bg-muted/50 flex items-center gap-3 px-4 py-3"
                  >
                    <button
                      type="button"
                      className="min-w-0 flex-1 text-left"
                      onClick={() => onOpenProject(project.id)}
                    >
                      <div className="flex items-center gap-1.5">
                        <span className="truncate text-sm font-medium">
                          {project.name}
                        </span>
                        {project.pinned ? (
                          <Pin className="size-3 shrink-0" />
                        ) : null}
                      </div>
                      <p className="text-muted-foreground mt-0.5 text-xs">
                        {project.sessionCount} sessions ·{' '}
                        {relativeTime(project.updatedAt)}
                      </p>
                    </button>
                    <Popover>
                      <PopoverTrigger asChild>
                        <button
                          type="button"
                          className="text-muted-foreground hover:bg-muted inline-flex size-7 items-center justify-center rounded-md"
                          aria-label={`Actions for ${project.name}`}
                        >
                          <MoreHorizontal className="size-4" />
                        </button>
                      </PopoverTrigger>
                      <PopoverContent align="end" className="w-36 p-1">
                        <button
                          type="button"
                          className="hover:bg-muted flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm"
                          onClick={() => onTogglePinProject(project)}
                        >
                          <Pin className="size-3.5" />
                          {project.pinned ? 'Unpin' : 'Pin'}
                        </button>
                        <button
                          type="button"
                          className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-red-600 hover:bg-red-50"
                          onClick={() => onDeleteProject(project)}
                        >
                          <Trash2 className="size-3.5" />
                          Delete
                        </button>
                      </PopoverContent>
                    </Popover>
                  </div>
                ))
              ) : (
                <div className="text-muted-foreground px-4 py-8 text-center text-sm">
                  No projects yet. Create one to organize your work.
                </div>
              )}
            </div>
          </section>
          <section>
            <h3 className="mb-3 text-sm font-medium">Recent sessions</h3>
            {recent.length > 0 ? (
              <div className="bg-card divide-y rounded-xl border">
                {recent.map(item => (
                  <button
                    key={item.id}
                    type="button"
                    className="hover:bg-muted/50 flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
                    onClick={() => onOpenSession(item.id)}
                    title={previews[item.id] || undefined}
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">
                        {item.title || 'Untitled'}
                      </span>
                      <span className="text-muted-foreground block truncate text-xs">
                        {item.projectId
                          ? projectNames.get(item.projectId) || 'Project'
                          : 'No project'}
                      </span>
                    </span>
                    <span className="text-muted-foreground shrink-0 text-xs">
                      {relativeTime(item.lastMessageAt || item.updatedAt)}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center px-4 py-10 text-center">
                <p className="text-muted-foreground text-sm">No sessions here</p>
                <Button
                  variant="ghost"
                  className="mt-2"
                  onClick={() => onCreateSession(null)}
                >
                  <Plus className="size-3.5" />
                  New Agent
                </Button>
              </div>
            )}
          </section>
        </div>
      </div>
    </ScrollArea>
  )
}

function InspectView({
  messages,
  tools,
  onClose
}: {
  messages: AgentMessage[]
  tools: TranscriptTool[]
  onClose: () => void
}) {
  const userTurns = messages.filter(message => message.role === 'user').length
  const assistantTurns = messages.filter(
    message => message.role === 'assistant'
  ).length
  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto max-w-4xl px-8 py-10">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-muted-foreground text-xs uppercase tracking-wide">
              Inspect chat
            </p>
            <h2 className="mt-2 text-3xl font-semibold">
              Session execution overview
            </h2>
          </div>
          <Button variant="outline" onClick={onClose}>
            Back to chat
          </Button>
        </div>
        <div className="mt-8 grid grid-cols-3 gap-3">
          {[
            ['User turns', userTurns],
            ['Assistant turns', assistantTurns],
            ['Tool calls', tools.length]
          ].map(([label, value]) => (
            <div key={label} className="bg-card rounded-xl border p-4">
              <span className="text-muted-foreground text-xs">{label}</span>
              <strong className="mt-2 block text-2xl">{value}</strong>
            </div>
          ))}
        </div>
        <div className="mt-8 space-y-2">
          {tools.map(tool => (
            <div key={tool.id} className="bg-card rounded-lg border p-3">
              <div className="flex items-center justify-between">
                <strong className="text-sm">{tool.name}</strong>
                <span className="text-muted-foreground text-xs capitalize">
                  {tool.status}
                </span>
              </div>
              {tool.result != null ? (
                <pre className="bg-muted/20 mt-3 max-h-52 overflow-auto whitespace-pre-wrap p-3 text-[11px]">
                  {typeof tool.result === 'string'
                    ? tool.result
                    : JSON.stringify(tool.result, null, 2)}
                </pre>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </ScrollArea>
  )
}

function SkillsView({
  mode,
  skills,
  loading = false,
  detail,
  catalogSkillRoute,
  catalogSearchEnabled,
  openCatalogSearchInitially = false,
  onOpen,
  onOpenCatalogDetail,
  onBack,
  onOpenImportGithub,
  onOpenImportFile,
  onOpenTrustedSources,
  onOpenCatalogSetup,
  onInstall,
  onUpload,
  onLoadSuggestedSources,
  onSearchCatalog,
  onGetCatalogDetail,
  onGetCatalogAudit,
  onBulkAction,
  onSetEnabled,
  onRemove
}: {
  mode: SkillsViewMode
  skills: AgentSkill[]
  loading?: boolean
  detail: AgentSkillDetail | null
  catalogSkillRoute: { id: string; source: string; skill: string } | null
  catalogSearchEnabled: boolean
  openCatalogSearchInitially?: boolean
  onOpen: (name: string) => void
  onOpenCatalogDetail: (skill: AgentCatalogSkill) => void
  onBack: () => void
  onOpenImportGithub: () => void
  onOpenImportFile: () => void
  onOpenTrustedSources: () => void
  onOpenCatalogSetup: () => void
  onInstall: (source: string) => Promise<string[] | void>
  onUpload: (file: File) => Promise<void>
  onLoadSuggestedSources: (signal?: AbortSignal) => Promise<AgentSkillSource[]>
  onSearchCatalog: (
    query: string,
    signal?: AbortSignal
  ) => Promise<AgentCatalogSkill[]>
  onGetCatalogDetail: (
    source: string,
    skill: string,
    signal?: AbortSignal
  ) => Promise<AgentCatalogSkillDetail>
  onGetCatalogAudit: (
    source: string,
    skill: string,
    signal?: AbortSignal
  ) => Promise<AgentCatalogSkillAudit>
  onBulkAction: (
    action: AgentSkillBatchAction,
    names: string[]
  ) => Promise<AgentSkillBatchResult>
  onSetEnabled: (name: string, enabled: boolean) => Promise<void>
  onRemove: (name: string) => Promise<void>
}) {
  const [query, setQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [authorFilter, setAuthorFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'enabled' | 'disabled'>('all')
  const [pendingEnabled, setPendingEnabled] = useState<Record<string, boolean>>(
    {}
  )
  const [pendingRemove, setPendingRemove] = useState<Record<string, boolean>>({})
  const [removeTarget, setRemoveTarget] = useState<
    | { type: 'single'; name: string }
    | { type: 'filtered'; count: number }
    | null
  >(null)
  const [batchBusy, setBatchBusy] = useState(false)
  const [batchToast, setBatchToast] = useState<{
    message: string
    tone: 'success' | 'warning'
  } | null>(null)
  const [githubSource, setGithubSource] = useState('fastfold-ai/skills@skills/fold')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const uploadInputRef = useRef<HTMLInputElement | null>(null)
  const [installing, setInstalling] = useState(false)
  const [trustedSources, setTrustedSources] = useState<AgentSkillSource[]>([])
  const [trustedSelected, setTrustedSelected] = useState<Record<string, boolean>>({})
  const [trustedLoading, setTrustedLoading] = useState(false)
  const [catalogResults, setCatalogResults] = useState<AgentCatalogSkill[]>([])
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [catalogSearchMode, setCatalogSearchMode] = useState(
    openCatalogSearchInitially && catalogSearchEnabled
  )
  const [catalogInstallingId, setCatalogInstallingId] = useState<string | null>(
    null
  )
  const [catalogDetail, setCatalogDetail] = useState<AgentCatalogSkillDetail | null>(
    null
  )
  const [catalogAudit, setCatalogAudit] = useState<AgentCatalogSkillAudit | null>(
    null
  )
  const [catalogDetailLoading, setCatalogDetailLoading] = useState(false)
  const [catalogDetailError, setCatalogDetailError] = useState<string | null>(null)
  const [copiedCatalogInstall, setCopiedCatalogInstall] = useState(false)
  const [catalogInstallError, setCatalogInstallError] = useState<string | null>(
    null
  )
  const [localCatalogDetail, setLocalCatalogDetail] =
    useState<AgentCatalogSkillDetail | null>(null)
  const [localCatalogAudit, setLocalCatalogAudit] =
    useState<AgentCatalogSkillAudit | null>(null)
  useEffect(() => {
    if (mode !== 'catalog_detail' || !catalogSkillRoute) {
      setCatalogDetail(null)
      setCatalogAudit(null)
      setCatalogDetailError(null)
      setCatalogInstallError(null)
      setCatalogDetailLoading(false)
      return
    }
    const controller = new AbortController()
    setCatalogDetailLoading(true)
    setCatalogDetailError(null)
    setCatalogInstallError(null)
    void onGetCatalogDetail(
      catalogSkillRoute.source,
      catalogSkillRoute.skill,
      controller.signal
    )
      .then(setCatalogDetail)
      .catch(error => {
        if (!controller.signal.aborted) {
          setCatalogDetailError(
            error instanceof Error
              ? error.message
              : 'Unable to load catalog skill details.'
          )
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setCatalogDetailLoading(false)
      })
    void onGetCatalogAudit(
      catalogSkillRoute.source,
      catalogSkillRoute.skill,
      controller.signal
    )
      .then(setCatalogAudit)
      .catch(() => {
        if (!controller.signal.aborted) {
          setCatalogAudit({
            id: catalogSkillRoute.id,
            source: catalogSkillRoute.source,
            slug: catalogSkillRoute.skill,
            audits: []
          })
        }
      })
    return () => controller.abort()
  }, [catalogSkillRoute, mode, onGetCatalogAudit, onGetCatalogDetail])
  useEffect(() => {
    if (mode !== 'detail' || !detail || !catalogSearchEnabled) {
      setLocalCatalogDetail(null)
      setLocalCatalogAudit(null)
      return
    }
    const coords = catalogCoordsFromInstalledSkill(detail)
    if (!coords) {
      setLocalCatalogDetail(null)
      setLocalCatalogAudit(null)
      return
    }
    const controller = new AbortController()
    void onGetCatalogDetail(coords.source, coords.skill, controller.signal)
      .then(result => {
        if (!controller.signal.aborted) setLocalCatalogDetail(result)
      })
      .catch(() => {
        if (!controller.signal.aborted) setLocalCatalogDetail(null)
      })
    void onGetCatalogAudit(coords.source, coords.skill, controller.signal)
      .then(result => {
        if (!controller.signal.aborted) setLocalCatalogAudit(result)
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setLocalCatalogAudit({
            id: `${coords.source}/${coords.skill}`,
            source: coords.source,
            slug: coords.skill,
            audits: []
          })
        }
      })
    return () => controller.abort()
  }, [
    catalogSearchEnabled,
    detail,
    mode,
    onGetCatalogAudit,
    onGetCatalogDetail
  ])
  useEffect(() => {
    if (!copiedCatalogInstall) return
    const timer = window.setTimeout(() => setCopiedCatalogInstall(false), 2000)
    return () => window.clearTimeout(timer)
  }, [copiedCatalogInstall])
  useEffect(() => {
    if (!openCatalogSearchInitially) return
    if (!catalogSearchEnabled) {
      onBack()
      return
    }
    setCatalogSearchMode(true)
    onBack()
  }, [catalogSearchEnabled, onBack, openCatalogSearchInitially])
  useEffect(() => {
    if (catalogSearchEnabled) return
    setCatalogSearchMode(false)
  }, [catalogSearchEnabled])
  const enableCatalogSearchMode = () => {
    if (!catalogSearchEnabled) {
      onOpenCatalogSetup()
      return
    }
    setCatalogError(null)
    setCatalogSearchMode(true)
  }
  const submitGithubInstall = async () => {
    if (installing) return
    setInstalling(true)
    try {
      const source = githubSource.trim()
      if (!source) return
      await onInstall(source)
      onBack()
    } finally {
      setInstalling(false)
    }
  }
  const submitFileInstall = async () => {
    if (installing || !uploadFile) return
    setInstalling(true)
    try {
      await onUpload(uploadFile)
      onBack()
    } finally {
      setInstalling(false)
    }
  }
  useEffect(() => {
    if (mode !== 'import_file') return
    const timer = window.setTimeout(() => {
      if (uploadInputRef.current) {
        uploadInputRef.current.value = ''
        uploadInputRef.current.click()
      }
    }, 0)
    return () => window.clearTimeout(timer)
  }, [mode])
  useEffect(() => {
    if (mode !== 'trusted_sources') return
    const controller = new AbortController()
    setTrustedLoading(true)
    void onLoadSuggestedSources(controller.signal)
      .then(items => {
        setTrustedSources(items)
        setTrustedSelected(current => {
          const next = { ...current }
          for (const item of items) {
            if (next[item.source] === undefined) next[item.source] = false
          }
          return next
        })
      })
      .finally(() => {
        if (!controller.signal.aborted) setTrustedLoading(false)
      })
    return () => controller.abort()
  }, [mode, onLoadSuggestedSources])
  useEffect(() => {
    if (!catalogSearchMode) {
      setCatalogResults([])
      setCatalogError(null)
      setCatalogLoading(false)
      return
    }
    const text = query.trim()
    if (text.length < 2) {
      setCatalogResults([])
      setCatalogError(null)
      setCatalogLoading(false)
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setCatalogLoading(true)
      setCatalogError(null)
      void onSearchCatalog(text, controller.signal)
        .then(items => {
          if (!controller.signal.aborted) setCatalogResults(items)
        })
        .catch(error => {
          if (controller.signal.aborted) return
          setCatalogResults([])
          setCatalogError(
            error instanceof Error ? error.message : 'Unable to search skills.sh.'
          )
        })
        .finally(() => {
          if (!controller.signal.aborted) setCatalogLoading(false)
        })
    }, 220)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [catalogSearchMode, onSearchCatalog, query])
  const selectedTrustedSources = trustedSources
    .map(item => item.source)
    .filter(source => Boolean(trustedSelected[source]))
  const submitTrustedInstall = async () => {
    if (installing || selectedTrustedSources.length === 0) return
    setInstalling(true)
    try {
      for (const source of selectedTrustedSources) {
        await onInstall(source)
      }
      onBack()
    } finally {
      setInstalling(false)
    }
  }
  const openCatalogDetailFromResult = (skill: AgentCatalogSkill) => {
    onOpenCatalogDetail(skill)
  }
  const submitCatalogInstallSource = async (
    source: string,
    installingId = 'catalog-detail',
    preferredSkillName?: string
  ) => {
    if (installing || batchBusy) return
    const installSource = String(source || '').trim()
    if (!installSource) {
      setCatalogInstallError('No install source available for this catalog skill.')
      return
    }
    setCatalogInstallingId(installingId)
    setInstalling(true)
    setCatalogInstallError(null)
    try {
      const installed = (await onInstall(installSource)) || []
      const preferred = String(preferredSkillName || '').trim()
      const preferredKey = preferred.toLowerCase().replace(/_/g, '-')
      const match =
        installed.find(
          name => name.toLowerCase().replace(/_/g, '-') === preferredKey
        ) ||
        installed[0] ||
        preferred
      if (match) onOpen(match)
    } catch (error) {
      setCatalogInstallError(formatSkillInstallError(error))
    } finally {
      setInstalling(false)
      setCatalogInstallingId(null)
    }
  }
  const categories = Array.from(
    new Set(skills.map(skill => categorizeSkill(skill)))
  ).sort()
  const authors = Array.from(
    new Set(skills.map(skill => skillAuthorLabel(skill)))
  ).sort((a, b) => {
    if (a === 'Unknown') return 1
    if (b === 'Unknown') return -1
    return a.localeCompare(b)
  })
  useEffect(() => {
    if (
      categoryFilter !== 'all' &&
      categoryFilter !== 'featured' &&
      !categories.includes(categoryFilter)
    ) {
      setCategoryFilter('all')
    }
  }, [categories, categoryFilter])
  useEffect(() => {
    if (authorFilter !== 'all' && !authors.includes(authorFilter)) {
      setAuthorFilter('all')
    }
  }, [authors, authorFilter])
  const categoryCounts = skills.reduce<Record<string, number>>((result, skill) => {
    const category = categorizeSkill(skill)
    result[category] = (result[category] || 0) + 1
    return result
  }, {})
  const authorCounts = skills.reduce<Record<string, number>>((result, skill) => {
    const author = skillAuthorLabel(skill)
    result[author] = (result[author] || 0) + 1
    return result
  }, {})
  const featuredCount = skills.filter(skill => isFeaturedSkill(skill)).length
  const enabledCount = skills.filter(skill => skill.enabled).length
  const disabledCount = skills.length - enabledCount
  const visible = skills.filter(skill => {
    const queryText = query.trim().toLowerCase()
    const category = categorizeSkill(skill)
    const matchesQuery = skillMatchesSearch(skill, queryText)
    const matchesCategory =
      categoryFilter === 'all' ||
      (categoryFilter === 'featured' && isFeaturedSkill(skill)) ||
      category === categoryFilter
    const author = skillAuthorLabel(skill)
    const matchesAuthor = authorFilter === 'all' || author === authorFilter
    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'enabled' && skill.enabled) ||
      (statusFilter === 'disabled' && !skill.enabled)
    return matchesQuery && matchesCategory && matchesAuthor && matchesStatus
  })
  const orderedVisible = [...visible].sort((a, b) => {
    const queryText = query.trim().toLowerCase()
    if (queryText) {
      const rankDiff = compareSkillsBySearchRank(a, b, queryText)
      if (rankDiff !== 0) return rankDiff
    }
    if (categoryFilter !== 'featured') {
      const featuredDiff =
        Number(isFeaturedSkill(b)) - Number(isFeaturedSkill(a))
      if (featuredDiff !== 0) return featuredDiff
    }
    return a.name.localeCompare(b.name)
  })
  const featuredVisible = orderedVisible.filter(skill => isFeaturedSkill(skill))
  const nonFeaturedVisible = orderedVisible.filter(skill => !isFeaturedSkill(skill))
  const filteredSkillNames = orderedVisible.map(skill => skill.name)
  const disableEligibleCount = orderedVisible.filter(skill => skill.enabled).length
  const enableEligibleCount = orderedVisible.filter(skill => !skill.enabled).length
  const removeEligibleCount = filteredSkillNames.length
  const [copiedInstall, setCopiedInstall] = useState(false)
  const detailInstallCommand = detail
    ? `fastfold skills add ${skillInstallSource(detail.name, detail.source)} --skill ${detail.name}`
    : ''
  const detailGithubUrl = detail
    ? skillGithubUrl(detail.name, detail.source)
    : null
  const detailAuthorUrl = detail
    ? skillAuthorUrl(detail.source)
    : null
  const detailIconSource = detail
    ? isFeaturedSkill(detail)
      ? featuredSkillIcon(detail)
      : skillIcon(detail)
    : null
  const detailVersionLabel = displaySkillVersion(detail?.version)
  const detailUpdatedLabel = formatSkillUpdatedLabel(detail?.updatedAt)
  useEffect(() => {
    setCopiedInstall(false)
  }, [detail?.name])
  const handleCopyInstall = useCallback(() => {
    if (!detailInstallCommand) return
    void navigator.clipboard.writeText(detailInstallCommand).then(() => {
      setCopiedInstall(true)
      window.setTimeout(() => setCopiedInstall(false), 2000)
    })
  }, [detailInstallCommand])

  const renderSkillsShMetrics = (
    source: string,
    installs: number,
    audits: AgentCatalogSkillAudit['audits']
  ) => {
    const installLabel = new Intl.NumberFormat('en-US', {
      notation: 'compact',
      maximumFractionDigits: 1
    }).format(installs)
    return (
      <aside className="space-y-4 lg:sticky lg:top-4">
        <div className="rounded-lg p-3">
          <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
            Installs
          </p>
          <p className="mt-1 text-3xl font-semibold">{installLabel}</p>
        </div>
        <div className="rounded-lg p-3">
          <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
            Repository
          </p>
          <p className="mt-1 break-all text-sm">{source || 'Unknown'}</p>
        </div>
        <div className="rounded-lg p-3">
          <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
            Security Audits
          </p>
          <div className="mt-2 space-y-2">
            {audits.length === 0 ? (
              <p className="text-muted-foreground text-xs">No audits available.</p>
            ) : (
              audits.map(audit => (
                <div
                  key={`${audit.provider}-${audit.slug}`}
                  className="flex items-center justify-between gap-2"
                >
                  <span className="truncate text-xs">{audit.provider}</span>
                  <span
                    className={cn(
                      'rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase',
                      auditStatusBadgeClass(audit.status)
                    )}
                  >
                    {audit.status || 'unknown'}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </aside>
    )
  }

  const setSkillEnabled = async (name: string, enabled: boolean) => {
    setPendingEnabled(current => ({ ...current, [name]: true }))
    try {
      await onSetEnabled(name, enabled)
    } finally {
      setPendingEnabled(current => ({ ...current, [name]: false }))
    }
  }
  const removeSkill = (name: string) => {
    if (batchBusy || pendingRemove[name]) return
    setRemoveTarget({ type: 'single', name })
  }
  const removeFiltered = () => {
    if (filteredSkillNames.length === 0 || batchBusy) return
    setRemoveTarget({ type: 'filtered', count: filteredSkillNames.length })
  }
  const confirmRemoveSkill = async () => {
    const target = removeTarget
    if (!target) return
    setRemoveTarget(null)
    if (target.type === 'single') {
      const name = target.name
      setPendingRemove(current => ({ ...current, [name]: true }))
      try {
        await onRemove(name)
        if (mode === 'detail' && detail?.name === name) {
          onBack()
        }
      } finally {
        setPendingRemove(current => ({ ...current, [name]: false }))
      }
      return
    }
    if (filteredSkillNames.length === 0 || batchBusy) return
    setBatchBusy(true)
    try {
      const result = await onBulkAction('remove', filteredSkillNames)
      setBatchToast({
        message:
          result.failed.length > 0
            ? `Removed ${result.succeeded.length}/${result.requested} skills (${result.failed.length} failed).`
            : `Removed ${result.succeeded.length}/${result.requested} skills.`,
        tone: result.failed.length > 0 ? 'warning' : 'success'
      })
      if (mode === 'detail' && detail && result.succeeded.includes(detail.name)) {
        onBack()
      }
    } finally {
      setBatchBusy(false)
    }
  }
  const setFilteredEnabled = async (enabled: boolean) => {
    if (filteredSkillNames.length === 0 || batchBusy) return
    setBatchBusy(true)
    try {
      const result = await onBulkAction(
        enabled ? 'enable' : 'disable',
        filteredSkillNames
      )
      const actionLabel = enabled ? 'Enabled' : 'Disabled'
      setBatchToast({
        message:
          result.failed.length > 0
            ? `${actionLabel} ${result.succeeded.length}/${result.requested} skills (${result.failed.length} failed).`
            : `${actionLabel} ${result.succeeded.length}/${result.requested} skills.`,
        tone: result.failed.length > 0 ? 'warning' : 'success'
      })
    } finally {
      setBatchBusy(false)
    }
  }
  useEffect(() => {
    if (!batchToast) return
    const timer = window.setTimeout(() => setBatchToast(null), 2800)
    return () => window.clearTimeout(timer)
  }, [batchToast])
  const showCatalogEmptyState =
    catalogSearchMode &&
    !catalogLoading &&
    !catalogError &&
    query.trim().length >= 2 &&
    catalogResults.length === 0
  const catalogInstallLabelFor = (installs: number) =>
    new Intl.NumberFormat('en-US', {
      notation: 'compact',
      maximumFractionDigits: 1
    }).format(installs)
  const installedSkillIndex = useMemo(() => {
    const index = new Map<string, Set<string>>()
    for (const skill of skills) {
      const nameKey = normalizeSkillMatchKey(skill.name)
      if (!nameKey) continue
      const sourceSpec = splitSkillSourceSpec(skill.source)
      const ownerRepo = sourceSpec?.ownerRepo.toLowerCase() || ''
      const repos = index.get(nameKey) || new Set<string>()
      repos.add(ownerRepo)
      index.set(nameKey, repos)
    }
    return index
  }, [skills])
  const isCatalogSkillInstalled = useCallback(
    (skill: AgentCatalogSkill) => {
      const candidateKeys = [
        normalizeSkillMatchKey(skill.slug),
        normalizeSkillMatchKey(skill.name)
      ].filter(Boolean)
      if (candidateKeys.length === 0) return false
      const catalogSpec = splitSkillSourceSpec(catalogSkillInstallSource(skill))
      const catalogOwnerRepo = catalogSpec?.ownerRepo.toLowerCase() || ''
      return candidateKeys.some(key => {
        const installedRepos = installedSkillIndex.get(key)
        if (!installedRepos || installedRepos.size === 0) return false
        if (!catalogOwnerRepo) return true
        return (
          installedRepos.has(catalogOwnerRepo) ||
          installedRepos.has('')
        )
      })
    },
    [installedSkillIndex]
  )

  const renderEnabledToggle = (skill: AgentSkill) => {
    const pending = Boolean(pendingEnabled[skill.name])
    return (
      <button
        type="button"
        role="switch"
        aria-checked={skill.enabled}
        aria-label={`${skill.enabled ? 'Disable' : 'Enable'} ${skill.name}`}
        disabled={pending}
        className={cn(
          'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
          skill.enabled
            ? 'bg-black/75 dark:bg-zinc-300/50'
            : 'bg-zinc-200 dark:bg-zinc-700',
          pending && 'cursor-not-allowed opacity-60'
        )}
        onClick={event => {
          event.preventDefault()
          event.stopPropagation()
          void setSkillEnabled(skill.name, !skill.enabled)
        }}
      >
        <span
          className={cn(
            'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
            skill.enabled ? 'translate-x-4' : 'translate-x-0.5'
          )}
        />
      </button>
    )
  }
  const renderRemoveButton = (skill: AgentSkill) => {
    const pending = Boolean(pendingRemove[skill.name]) || batchBusy
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-muted-foreground/70 hover:text-muted-foreground h-6 w-6 p-0"
            disabled={pending}
            onClick={event => {
              event.preventDefault()
              event.stopPropagation()
            }}
          >
            <MoreHorizontal className="size-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            className="text-red-600 focus:text-red-700"
            onClick={event => {
              event.preventDefault()
              event.stopPropagation()
              void removeSkill(skill.name)
            }}
          >
            <Trash2 className="size-3.5" />
            Remove
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    )
  }
  const renderSkillsBreadcrumb = () => (
    <div className="flex items-center gap-2 text-sm">
      <button
        type="button"
        onClick={onBack}
        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back
      </button>
      <span className="text-muted-foreground/40">/</span>
      <button
        type="button"
        onClick={onBack}
        className="text-muted-foreground hover:text-foreground transition-colors"
      >
        Skills
      </button>
    </div>
  )

  const renderRemoveDialog = () => (
    <AlertDialog
      open={Boolean(removeTarget)}
      onOpenChange={open => {
        if (!open) setRemoveTarget(null)
      }}
    >
      <AlertDialogContent className="max-w-sm">
        <AlertDialogHeader>
          <AlertDialogTitle>
            {removeTarget?.type === 'filtered'
              ? 'Remove skills?'
              : 'Remove skill?'}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {removeTarget?.type === 'filtered'
              ? `Remove ${removeTarget.count} skills in the current filter? This cannot be undone.`
              : `Remove “${removeTarget?.name || 'this skill'}”? This uninstalls it from this machine and cannot be undone.`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={() => void confirmRemoveSkill()}
          >
            Remove
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )

  if (mode === 'import_github') {
    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto w-full max-w-3xl px-6 py-8 md:px-10">
          {renderSkillsBreadcrumb()}
          <section className="bg-card mt-4 space-y-4 rounded-xl border p-6">
            <div>
              <h2 className="text-lg font-semibold">Import from GitHub</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Use owner/repo, owner/repo@path, or a GitHub URL. This matches how
                `fastfold skills add` parses sources.
              </p>
            </div>
            <Input
              value={githubSource}
              onChange={event => setGithubSource(event.target.value)}
              placeholder="fastfold-ai/skills@skills/fold"
              autoFocus
              onKeyDown={event => {
                if (event.key === 'Enter' && githubSource.trim() && !installing) {
                  event.preventDefault()
                  void submitGithubInstall()
                }
              }}
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={onBack}>
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={!githubSource.trim() || installing}
                onClick={() => void submitGithubInstall()}
              >
                {installing ? 'Importing…' : 'Import'}
              </Button>
            </div>
          </section>
        </div>
      </ScrollArea>
    )
  }

  if (mode === 'import_file') {
    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto w-full max-w-3xl px-6 py-8 md:px-10">
          {renderSkillsBreadcrumb()}
          <section className="bg-card mt-4 space-y-4 rounded-xl border p-6">
            <div>
              <h2 className="text-lg font-semibold">Import from file</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Choose a local .zip, .skill, or SKILL.md file.
              </p>
            </div>
            <Input
              ref={uploadInputRef}
              type="file"
              accept=".zip,.skill,.md"
              onChange={event => {
                const file = event.target.files?.[0] ?? null
                setUploadFile(file)
              }}
            />
            <p className="text-muted-foreground text-xs">
              {uploadFile
                ? `Selected: ${uploadFile.name}`
                : 'Pick a file to upload using your file browser.'}
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={onBack}>
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={!uploadFile || installing}
                onClick={() => void submitFileInstall()}
              >
                {installing ? 'Uploading…' : 'Upload'}
              </Button>
            </div>
          </section>
        </div>
      </ScrollArea>
    )
  }

  if (mode === 'trusted_sources') {
    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto w-full max-w-4xl px-6 py-8 md:px-10">
          {renderSkillsBreadcrumb()}
          <section className="bg-card mt-4 space-y-4 rounded-xl border p-6">
            <div>
              <h2 className="text-lg font-semibold">Suggestions</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Suggested community skill collections from FastFold setup.
                Select one or more sources to install.
              </p>
            </div>
            {trustedLoading ? (
              <CardGridSkeleton cards={6} columns={3} />
            ) : trustedSources.length === 0 ? (
              <p className="text-muted-foreground text-sm">
                No suggestions are currently available.
              </p>
            ) : (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {trustedSources.map(item => (
                  <button
                    key={item.source}
                    type="button"
                    className={cn(
                      'bg-background/60 hover:bg-muted/40 flex items-start gap-3 rounded-lg border p-3 text-left transition-colors',
                      trustedSelected[item.source] &&
                        'ring-primary bg-muted/40 ring-1'
                    )}
                    onClick={() =>
                      setTrustedSelected(current => ({
                        ...current,
                        [item.source]: !current[item.source]
                      }))
                    }
                  >
                    {suggestionSourceIcon(item) ? (
                      <img
                        src={suggestionSourceIcon(item) || ''}
                        alt=""
                        className="mt-0.5 size-8 rounded object-contain"
                      />
                    ) : (
                      <span className="bg-muted/30 text-muted-foreground mt-0.5 grid size-8 shrink-0 place-items-center rounded">
                        <GitBranch className="size-4" />
                      </span>
                    )}
                    <div className="min-w-0">
                      <p className="text-sm font-medium">
                        {suggestionSourceLabel(item)}
                      </p>
                      <p className="text-muted-foreground mt-0.5 text-xs">
                        {item.description}
                      </p>
                      <span className="text-muted-foreground mt-1 block truncate text-xs">
                        {item.source}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={onBack}>
                Cancel
              </Button>
              <Button
                size="sm"
                disabled={selectedTrustedSources.length === 0 || installing}
                onClick={() => void submitTrustedInstall()}
              >
                {installing
                  ? `Installing ${selectedTrustedSources.length}…`
                  : `Install selected (${selectedTrustedSources.length})`}
              </Button>
            </div>
          </section>
        </div>
      </ScrollArea>
    )
  }

  if (mode === 'catalog_detail') {
    const catalogSource = String(
      catalogDetail?.source || catalogSkillRoute?.source || ''
    ).trim()
    const catalogSlug = String(catalogDetail?.slug || catalogSkillRoute?.skill || '').trim()
    const catalogId = String(catalogDetail?.id || catalogSkillRoute?.id || '').trim()
    const catalogFiles = catalogDetail?.files || []
    const catalogSkillMd = (
      catalogFiles.find(file => file.path.toLowerCase() === 'skill.md') ||
      catalogFiles.find(file => file.path.toLowerCase().endsWith('/skill.md'))
    )?.contents
    const catalogSummary =
      (catalogSkillMd
        ? frontmatterValue(catalogSkillMd, 'description')
        : null) ||
      (catalogSkillMd
        ? stripFrontmatter(catalogSkillMd)
            .split('\n')
            .map(line => line.trim())
            .find(line => line && !line.startsWith('#') && !line.startsWith('-'))
        : null) ||
      'No summary available.'
    const catalogInstallCommand =
      catalogSource && catalogSlug
        ? catalogSkillInstallCommand(catalogSource, catalogSlug, catalogFiles)
        : ''
    const catalogInstallTarget =
      catalogSource && catalogSlug
        ? catalogSkillInstallTarget(catalogSource, catalogSlug, catalogFiles)
        : ''
    const catalogInstalls = Number(catalogDetail?.installs || 0)
    const catalogAudits = catalogAudit?.audits || []
    const catalogSkillsShUrl =
      catalogSource && catalogSlug
        ? skillsShSkillUrl(catalogSource, catalogSlug)
        : null
    const handleCatalogInstall = async () => {
      if (!catalogInstallTarget) return
      await submitCatalogInstallSource(
        catalogInstallTarget,
        catalogId || 'catalog-detail',
        catalogSlug
      )
    }
    const handleCatalogCopyInstall = () => {
      if (!catalogInstallCommand) return
      void navigator.clipboard.writeText(catalogInstallCommand).then(() => {
        setCopiedCatalogInstall(true)
      })
    }

    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 p-4 md:p-6">
          <div className="flex items-center justify-between gap-3">
            {renderSkillsBreadcrumb()}
            {catalogSkillsShUrl ? (
              <a
                href={catalogSkillsShUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border/70 px-3 py-1.5 text-xs hover:bg-muted"
              >
                <img
                  src="/suggestions/skills-sh.png"
                  alt=""
                  className="size-3.5 rounded object-contain"
                />
                View in Skills.sh
              </a>
            ) : null}
          </div>
          {catalogDetailLoading ? (
            <DetailPageSkeleton />
          ) : catalogDetailError ? (
            <p className="text-destructive text-sm">{catalogDetailError}</p>
          ) : (
            <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_250px]">
              <section className="space-y-4">
                <div>
                  <p className="text-muted-foreground text-xs">
                    skills / {catalogSource || 'unknown'} / {catalogSlug || 'unknown'}
                  </p>
                  <h1 className="mt-2 text-3xl font-semibold">
                    {catalogSlug || 'Catalog skill'}
                  </h1>
                </div>

                <div className="space-y-2">
                  <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                    Installation
                  </p>
                  <div className="bg-muted/50 overflow-hidden rounded-lg border">
                    <div className="bg-muted/80 flex items-center justify-between border-b px-3 py-1.5">
                      <span className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                        bash
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 gap-1.5 px-2 text-xs"
                        onClick={handleCatalogCopyInstall}
                      >
                        {copiedCatalogInstall ? (
                          <>
                            <Check className="h-3.5 w-3.5" />
                            Copied!
                          </>
                        ) : (
                          <>
                            <Copy className="h-3.5 w-3.5" />
                            Copy
                          </>
                        )}
                      </Button>
                    </div>
                    <pre className="text-muted-foreground overflow-x-auto p-3 font-mono text-sm">
                      <code>{catalogInstallCommand || 'No install command available.'}</code>
                    </pre>
                  </div>
                  <div className="flex justify-end">
                    <Button
                      size="sm"
                      disabled={!catalogInstallTarget || installing}
                      onClick={() => void handleCatalogInstall()}
                    >
                      {installing && catalogInstallingId === (catalogId || 'catalog-detail')
                        ? 'Installing…'
                        : isCatalogSkillInstalled({
                            id: catalogId,
                            slug: catalogSlug,
                            name: catalogSlug,
                            source: catalogSource,
                            installs: catalogInstalls,
                            sourceType: 'github',
                            installUrl: null,
                            url: null
                          })
                        ? 'Update'
                        : 'Install'}
                    </Button>
                  </div>
                  {catalogInstallError ? (
                    <div
                      role="alert"
                      className="border-destructive/30 bg-destructive/5 text-destructive rounded-lg border px-3 py-2 text-sm leading-relaxed"
                    >
                      {catalogInstallError}
                    </div>
                  ) : null}
                </div>

                <div className="space-y-2">
                  <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                    Summary
                  </p>
                  <div className="bg-card rounded-lg border p-3 text-sm leading-relaxed">
                    {catalogSummary}
                  </div>
                </div>

                {catalogSkillMd ? (
                  <section className="space-y-2">
                    <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                      SKILL.md
                    </p>
                    <MarkdownContent
                      content={stripFrontmatter(catalogSkillMd)}
                      className="max-w-none text-sm [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_code]:break-words [&_table]:block [&_table]:max-w-full [&_table]:overflow-x-auto"
                    />
                  </section>
                ) : null}
              </section>

              {renderSkillsShMetrics(
                catalogSource,
                catalogInstalls,
                catalogAudits
              )}
            </div>
          )}
        </div>
      </ScrollArea>
    )
  }

  if (mode === 'detail' && detail) {
    const localCatalogSource = String(
      localCatalogDetail?.source ||
        catalogCoordsFromInstalledSkill(detail)?.source ||
        ''
    ).trim()
    const localCatalogInstalls = Number(localCatalogDetail?.installs || 0)
    const localCatalogAudits = localCatalogAudit?.audits || []
    const showLocalCatalogMetrics =
      catalogSearchEnabled && localCatalogDetail != null
    const localSkillsShUrl =
      showLocalCatalogMetrics && localCatalogSource
        ? skillsShSkillUrl(
            localCatalogSource,
            String(localCatalogDetail?.slug || detail.name)
          )
        : null

    return (
      <>
        <ScrollArea className="flex-1">
          <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 p-4 md:p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <button
                  type="button"
                  onClick={onBack}
                  className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back
                </button>
                <span className="text-muted-foreground/40">/</span>
                <button
                  type="button"
                  onClick={onBack}
                  className="text-muted-foreground hover:text-foreground transition-colors"
                >
                  Skills
                </button>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs text-red-600 hover:text-red-700"
                  disabled={Boolean(detail && pendingRemove[detail.name]) || batchBusy}
                  onClick={() => removeSkill(detail.name)}
                >
                  <Trash2 className="mr-1 size-3.5" />
                  Remove
                </Button>
              {localSkillsShUrl ? (
                <a
                  href={localSkillsShUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-md border border-border/70 px-3 py-1.5 text-xs hover:bg-muted"
                >
                  <img
                    src="/suggestions/skills-sh.png"
                    alt=""
                    className="size-3.5 rounded object-contain"
                  />
                  View in Skills.sh
                </a>
              ) : null}
              {detailGithubUrl ? (
                <a
                  href={detailGithubUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-md border border-border/70 px-3 py-1.5 text-xs hover:bg-muted"
                >
                  <GitBranch className="h-3.5 w-3.5" />
                  View in GitHub
                </a>
              ) : (
                <span className="text-muted-foreground inline-flex items-center gap-1.5 rounded-md border border-border/60 px-3 py-1.5 text-xs">
                  <GitBranch className="h-3.5 w-3.5" />
                  Source not on GitHub
                </span>
              )}
            </div>
          </div>

          <div
            className={cn(
              'grid items-start gap-4',
              showLocalCatalogMetrics
                ? 'lg:grid-cols-[240px_minmax(0,1fr)_220px]'
                : 'lg:grid-cols-[240px_minmax(0,1fr)]'
            )}
          >
            <aside className="space-y-3 lg:sticky lg:top-4 lg:border-r lg:border-border/60 lg:pr-4">
              <div className="space-y-2">
                {detailIconSource ? (
                  <img
                    src={detailIconSource}
                    alt=""
                    className="size-9 rounded object-contain"
                  />
                ) : (
                  <span className="bg-muted/30 text-muted-foreground grid size-9 shrink-0 place-items-center rounded">
                    <Box className="size-5" />
                  </span>
                )}
                <div className="min-w-0 space-y-0.5">
                  <div className="flex items-start justify-between gap-2">
                    <h1 className="break-all text-lg font-semibold">
                      /{detail.name}
                    </h1>
                    <div className="shrink-0 pt-0.5">
                      {renderEnabledToggle(detail)}
                    </div>
                  </div>
                  <p className="text-muted-foreground mb-6 pb-3 text-sm">
                    {detail.description || 'Runtime skill'}
                  </p>
                  <div className="mt-6 space-y-1 border-t border-border/60 pt-5 text-xs">
                    <div className="text-muted-foreground flex items-center gap-1.5">
                      <Tag className="h-3.5 w-3.5 shrink-0" />
                      <span className="text-foreground/90 font-medium">
                        Version:
                      </span>
                      <span className="truncate">{detailVersionLabel}</span>
                    </div>
                    <div className="text-muted-foreground flex items-center gap-1.5">
                      <CalendarDays className="h-3.5 w-3.5 shrink-0" />
                      <span className="text-foreground/90 font-medium">
                        Last updated:
                      </span>
                      <span className="truncate" title={detailUpdatedLabel}>
                        {detailUpdatedLabel}
                      </span>
                    </div>
                    <div className="text-muted-foreground flex items-center gap-1.5">
                      <UserRound className="h-3.5 w-3.5 shrink-0" />
                      <span className="text-foreground/90 font-medium">
                        Author:
                      </span>
                      {detailAuthorUrl ? (
                        <a
                          href={detailAuthorUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="truncate underline-offset-2 hover:underline"
                        >
                          {detail.author || 'fastfold-ai'}
                        </a>
                      ) : (
                        <span className="truncate">{detail.author || 'unknown'}</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </aside>

            <section className="min-w-0 overflow-x-hidden p-1">
              <div className="mb-4 space-y-1.5">
                <p className="text-muted-foreground text-sm font-medium">
                  Install this skill
                </p>
                <div className="bg-muted/50 overflow-hidden rounded-lg border">
                  <div className="bg-muted/80 flex items-center justify-between border-b px-3 py-1.5">
                    <span className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                      bash
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 gap-1.5 px-2 text-xs"
                      onClick={handleCopyInstall}
                    >
                      {copiedInstall ? (
                        <>
                          <Check className="h-3.5 w-3.5" />
                          Copied!
                        </>
                      ) : (
                        <>
                          <Copy className="h-3.5 w-3.5" />
                          Copy
                        </>
                      )}
                    </Button>
                  </div>
                  <pre className="text-muted-foreground overflow-x-auto p-3 font-mono text-sm">
                    <code>{detailInstallCommand}</code>
                  </pre>
                </div>
              </div>

              <MarkdownContent
                content={stripFrontmatter(detail.content)}
                className="max-w-none text-sm [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_code]:break-words [&_table]:block [&_table]:max-w-full [&_table]:overflow-x-auto"
              />
            </section>

            {showLocalCatalogMetrics
              ? renderSkillsShMetrics(
                  localCatalogSource,
                  localCatalogInstalls,
                  localCatalogAudits
                )
              : null}
          </div>
        </div>
      </ScrollArea>
      {renderRemoveDialog()}
      </>
    )
  }
  if (mode === 'detail') {
    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto w-full max-w-3xl px-6 py-8 md:px-10">
          {renderSkillsBreadcrumb()}
          <DetailPageSkeleton />
        </div>
      </ScrollArea>
    )
  }
  return (
    <>
      <ScrollArea className="flex-1">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 md:p-6 xl:flex-row">
          <div className="min-w-0 flex-1">
            <div className="mb-4">
              <h2 className="text-2xl font-semibold">Skills</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Packaged instructions and scripts the agent can load on demand.
                Install from the catalog or GitHub, and toggle which are active.
              </p>
            </div>
            <div className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-20 mb-4 flex flex-wrap items-center gap-2 pb-3 pt-2 backdrop-blur">
              <div className="relative min-w-[280px] flex-1 max-w-3xl">
                <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
                <Input
                  value={query}
                  onChange={event => setQuery(event.target.value)}
                  placeholder={
                    catalogSearchMode
                      ? 'Search skills.sh...'
                      : 'Search skills, descriptions...'
                  }
                  className="border-border/70 bg-background/70 h-11 pl-10 pr-[9.5rem]"
                />
                <button
                  type="button"
                  className={cn(
                    'absolute right-1.5 top-1/2 flex h-8 -translate-y-1/2 items-center gap-1.5 rounded-md px-2 text-xs transition-colors',
                    catalogSearchMode
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:text-foreground',
                    !catalogSearchEnabled && 'opacity-70'
                  )}
                  onClick={() => {
                    if (catalogSearchMode) {
                      setCatalogSearchMode(false)
                      setCatalogResults([])
                      setCatalogError(null)
                      return
                    }
                    enableCatalogSearchMode()
                  }}
                  title={
                    catalogSearchEnabled
                      ? 'Toggle Skills.sh search'
                      : 'Skills.sh needs setup'
                  }
                >
                  <img
                    src="/suggestions/skills-sh.png"
                    alt=""
                    className="size-3.5 rounded object-contain"
                  />
                  <span>Skills.sh</span>
                  <span
                    className={cn(
                      'ml-0.5 inline-flex h-4 w-7 items-center rounded-full px-0.5 transition-colors',
                      catalogSearchMode ? 'bg-foreground/80' : 'bg-muted-foreground/30'
                    )}
                    aria-hidden
                  >
                    <span
                      className={cn(
                        'bg-background size-3 rounded-full transition-transform',
                        catalogSearchMode ? 'translate-x-3' : 'translate-x-0'
                      )}
                    />
                  </span>
                </button>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-10">
                    <Plus className="mr-1 size-3.5" />
                    Add skill
                    <ChevronDown className="ml-1 size-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={onOpenImportGithub}>
                    <GitBranch className="size-4" />
                    Import from GitHub
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={onOpenImportFile}>
                    <Upload className="size-4" />
                    Upload from file
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className={cn(
                      !catalogSearchEnabled &&
                        'text-muted-foreground/80 data-[highlighted]:text-muted-foreground/80'
                    )}
                    onClick={enableCatalogSearchMode}
                  >
                    <img
                      src="/suggestions/skills-sh.png"
                      alt=""
                      className={cn(
                        'size-4 rounded object-contain',
                        !catalogSearchEnabled && 'opacity-60'
                      )}
                    />
                    <span>Search in Skills.sh</span>
                    {!catalogSearchEnabled ? (
                      <span className="text-muted-foreground/80 text-[11px]">
                        (Needs setup)
                      </span>
                    ) : null}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={onOpenTrustedSources}>
                    <Check className="size-4" />
                    Suggestions
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
            {catalogSearchMode ? (
              <div className="space-y-4 pb-4">
                <section className="space-y-2">
                  <p className="text-muted-foreground text-xs font-medium">
                    Skills.sh
                    {query.trim().length >= 2
                      ? ` · ${catalogResults.length} result${catalogResults.length === 1 ? '' : 's'}`
                      : ''}
                  </p>
                  {catalogLoading ? (
                    <ListRowsSkeleton rows={5} withToggle={false} />
                  ) : null}
                  {catalogError ? (
                    <p className="text-destructive text-sm">{catalogError}</p>
                  ) : null}
                  {!catalogLoading && !catalogError && query.trim().length < 2 ? (
                    <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
                      Type at least 2 characters to search skills.sh.
                    </div>
                  ) : null}
                  {showCatalogEmptyState ? (
                    <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
                      No skills.sh results match “{query.trim()}”.
                    </div>
                  ) : null}
                  {!catalogLoading && !catalogError && catalogResults.length > 0 ? (
                    <div className="space-y-2">
                      {catalogResults.map(skill => {
                        const isInstalled = isCatalogSkillInstalled(skill)
                        const title = skill.name || skill.slug
                        return (
                          <div
                            key={skill.id}
                            className="bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg p-3 transition-colors"
                          >
                            <button
                              type="button"
                              className="min-w-0 flex-1 text-left"
                              onClick={() => openCatalogDetailFromResult(skill)}
                            >
                              <div className="flex items-center gap-2">
                                <img
                                  src="/suggestions/skills-sh.png"
                                  alt=""
                                  className="size-6 rounded object-contain"
                                />
                                <span className="truncate text-sm font-medium">
                                  {title}
                                </span>
                                <span className="text-muted-foreground truncate text-xs">
                                  {skill.source}
                                </span>
                                {skill.installs > 0 ? (
                                  <span className="text-muted-foreground shrink-0 text-xs">
                                    {catalogInstallLabelFor(skill.installs)} installs
                                  </span>
                                ) : null}
                              </div>
                              <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
                                {skill.source}
                                {skill.sourceType ? ` · ${skill.sourceType}` : ''}
                              </p>
                            </button>
                            <div className="flex items-center gap-1 pt-0.5">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 text-xs"
                                onClick={() => openCatalogDetailFromResult(skill)}
                              >
                                {isInstalled ? 'Update' : 'View'}
                              </Button>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  ) : null}
                </section>
              </div>
            ) : loading ? (
              <div className="space-y-4 pb-4">
                <section className="space-y-2">
                  <Skeleton className="h-3 w-24" />
                  <CardGridSkeleton cards={6} columns={3} />
                </section>
                <section className="space-y-2">
                  <Skeleton className="h-3 w-16" />
                  <ListRowsSkeleton rows={5} />
                </section>
              </div>
            ) : visible.length === 0 ? (
              <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
                No skills match the current search/filter.
              </div>
            ) : (
              <div className="space-y-4 pb-4">
                {featuredVisible.length > 0 ? (
                  <section className="space-y-2">
                    <p className="text-muted-foreground text-xs font-medium">
                      Featured ({featuredVisible.length})
                    </p>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                      {featuredVisible.map(skill => {
                        const iconSource = featuredSkillIcon(skill)
                        const metaText = skillMetaText(skill)
                        return (
                          <div
                            key={skill.name}
                            className={cn(
                              'bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg p-3 transition-colors',
                              !skill.enabled && 'opacity-60'
                            )}
                          >
                            <button
                              type="button"
                              className="min-w-0 flex-1 text-left"
                              onClick={() => onOpen(skill.name)}
                            >
                              <div className="flex items-center gap-2">
                                <img
                                  src={iconSource}
                                  alt=""
                                  className="size-7 rounded object-contain"
                                />
                                <span className="truncate text-sm font-medium">
                                  {skill.name}
                                </span>
                              </div>
                              {metaText ? (
                                <p className="text-muted-foreground mt-0.5 text-xs">
                                  {metaText}
                                </p>
                              ) : null}
                              <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
                                {skill.description}
                              </p>
                            </button>
                            <div className="flex items-center gap-1 pt-0.5">
                              {renderEnabledToggle(skill)}
                              {renderRemoveButton(skill)}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </section>
                ) : null}
                {categoryFilter !== 'featured' ? (
                  <section className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-muted-foreground text-xs font-medium">
                        All ({nonFeaturedVisible.length})
                      </p>
                      <div className="flex flex-wrap items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground h-7 text-xs"
                          disabled={disableEligibleCount === 0 || batchBusy}
                          onClick={() => void setFilteredEnabled(false)}
                        >
                          Disable ({disableEligibleCount})
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground h-7 text-xs"
                          disabled={enableEligibleCount === 0 || batchBusy}
                          onClick={() => void setFilteredEnabled(true)}
                        >
                          Enable ({enableEligibleCount})
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground h-7 text-xs"
                          disabled={removeEligibleCount === 0 || batchBusy}
                          onClick={() => void removeFiltered()}
                        >
                          Remove ({removeEligibleCount})
                        </Button>
                      </div>
                    </div>
                    <div className="space-y-2">
                      {nonFeaturedVisible.map(skill => {
                        const iconSource = skillIcon(skill)
                        const metaText = skillMetaText(skill)
                        return (
                          <div
                            key={skill.name}
                            className={cn(
                              'bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg p-3 transition-colors',
                              !skill.enabled && 'opacity-60'
                            )}
                          >
                            <button
                              type="button"
                              className="min-w-0 flex-1 text-left"
                              onClick={() => onOpen(skill.name)}
                            >
                              <div className="flex items-center gap-2">
                                {iconSource ? (
                                  <img
                                    src={iconSource}
                                    alt=""
                                    className="size-6 rounded object-contain"
                                  />
                                ) : (
                                  <span className="bg-muted/30 text-muted-foreground grid size-6 shrink-0 place-items-center rounded">
                                    <Box className="size-4" />
                                  </span>
                                )}
                                <span className="truncate text-sm font-medium">
                                  {skill.name}
                                </span>
                                <span className="text-muted-foreground text-xs">
                                  {categorizeSkill(skill)}
                                </span>
                                {metaText ? (
                                  <span className="text-muted-foreground text-xs">
                                    {metaText}
                                  </span>
                                ) : null}
                              </div>
                              <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
                                {skill.description}
                              </p>
                            </button>
                            <div className="flex items-center gap-1 pt-0.5">
                              {renderEnabledToggle(skill)}
                              {renderRemoveButton(skill)}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </section>
                ) : null}
              </div>
            )}
          </div>
          {!catalogSearchMode ? (
          <aside className="flex w-full shrink-0 flex-col gap-4 xl:sticky xl:top-4 xl:self-start xl:w-[320px]">
            <section className="bg-background/70 rounded-lg p-2">
              <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
                Status
              </div>
              <button
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  statusFilter === 'all'
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setStatusFilter('all')}
              >
                All ({skills.length})
              </button>
              <button
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  statusFilter === 'enabled'
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setStatusFilter('enabled')}
              >
                Enabled ({enabledCount})
              </button>
              <button
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  statusFilter === 'disabled'
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setStatusFilter('disabled')}
              >
                Disabled ({disabledCount})
              </button>
            </section>
            <section className="bg-background/70 rounded-lg p-2">
              <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
                Categories
              </div>
              <button
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  categoryFilter === 'all'
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setCategoryFilter('all')}
              >
                All ({skills.length})
              </button>
              <button
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  categoryFilter === 'featured'
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setCategoryFilter('featured')}
              >
                Featured ({featuredCount})
              </button>
              {categories.map(category => (
                <button
                  key={category}
                  type="button"
                  className={cn(
                    'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                    categoryFilter === category
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                  onClick={() => setCategoryFilter(category)}
                >
                  {category} ({categoryCounts[category] || 0})
                </button>
              ))}
            </section>
            <section className="bg-background/70 rounded-lg p-2">
              <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
                Authors
              </div>
              <button
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  authorFilter === 'all'
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setAuthorFilter('all')}
              >
                All ({skills.length})
              </button>
              {authors.map(author => (
                <button
                  key={author}
                  type="button"
                  className={cn(
                    'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                    authorFilter === author
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                  onClick={() => setAuthorFilter(author)}
                >
                  {author} ({authorCounts[author] || 0})
                </button>
              ))}
            </section>
          </aside>
          ) : null}
        </div>
      </ScrollArea>
      {batchToast ? (
        <div
          className={cn(
            'fixed bottom-4 right-4 z-50 max-w-xs rounded-md border px-3 py-2 text-xs shadow-md',
            batchToast.tone === 'warning'
              ? 'border-amber-300/70 bg-amber-50 text-amber-900 dark:border-amber-500/40 dark:bg-amber-950/40 dark:text-amber-100'
              : 'border-border/70 bg-background/95 text-foreground'
          )}
          role="status"
          aria-live="polite"
        >
          {batchToast.message}
        </div>
      ) : null}
      {renderRemoveDialog()}
    </>
  )
}

function IntegrationsView({
  terminalClient,
  integrations,
  loading = false,
  selectedKey,
  values,
  onSelect,
  onValueChange,
  onSave,
  onValidate,
  onAutofill,
  onSetup,
  onOpenVercelTerminal,
  onRemove
}: {
  terminalClient: LocalAgentClient
  integrations: IntegrationSummary[]
  loading?: boolean
  selectedKey: string | null
  values: Record<string, string>
  onSelect: (key: string | null) => void
  onValueChange: (envName: string, value: string) => void
  onSave: () => Promise<void>
  onValidate: (key: string) => Promise<{ ok: boolean; message: string }>
  onAutofill: (key: string) => Promise<void>
  onSetup: (key: string) => Promise<IntegrationSetupResult>
  onOpenVercelTerminal: () => Promise<string>
  onRemove: (key: string) => Promise<void>
}) {
  const selected = integrations.find(item => item.key === selectedKey)
  const [integrationSearch, setIntegrationSearch] = useState('')
  const [integrationCategory, setIntegrationCategory] = useState('all')
  const [integrationStatus, setIntegrationStatus] = useState<
    'all' | 'configured' | 'not_configured'
  >('all')
  const [validationMessage, setValidationMessage] = useState<string | null>(
    null
  )
  const [setupResult, setSetupResult] = useState<IntegrationSetupResult | null>(
    null
  )
  const [setupRunning, setSetupRunning] = useState(false)
  const [autoFetchPending, setAutoFetchPending] = useState(false)
  const autoFetchAttemptsRef = useRef(0)
  const [terminalSessionId, setTerminalSessionId] = useState<string | null>(null)
  const [terminalOpen, setTerminalOpen] = useState(false)
  const [openingTerminal, setOpeningTerminal] = useState(false)
  const [terminalStartupNonce, setTerminalStartupNonce] = useState(0)
  const vercelSetupRunCommand =
    'vercel login && vercel link && vercel env pull .env.local --environment=development'
  useEffect(() => {
    setSetupResult(null)
    setAutoFetchPending(false)
    autoFetchAttemptsRef.current = 0
  }, [selectedKey])
  useEffect(() => {
    if (!autoFetchPending || selected?.key !== 'skills-sh') return
    let cancelled = false
    let timer: number | null = null
    const attemptImport = async () => {
      if (cancelled) return
      try {
        await onAutofill(selected.key)
        if (cancelled) return
        setAutoFetchPending(false)
        setValidationMessage(
          'Imported Vercel OIDC token into /keys config. Skills.sh search is now enabled.'
        )
      } catch {
        if (cancelled) return
        autoFetchAttemptsRef.current += 1
        if (autoFetchAttemptsRef.current >= 40) {
          setAutoFetchPending(false)
          setValidationMessage(
            'Still waiting for Vercel token. Finish terminal prompts, then click Re-link Project again.'
          )
          return
        }
        timer = window.setTimeout(() => {
          void attemptImport()
        }, 3000)
      }
    }
    timer = window.setTimeout(() => {
      void attemptImport()
    }, 2500)
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [autoFetchPending, onAutofill, selected?.key])
  const categories = Array.from(
    new Set(integrations.map(item => item.category))
  ).sort()
  const configuredCount = integrations.filter(item => item.configured).length
  const notConfiguredCount = integrations.length - configuredCount
  const featuredCount = integrations.filter(item =>
    isFeaturedIntegration(item)
  ).length
  const categoryCounts = integrations.reduce<Record<string, number>>(
    (counts, item) => {
      counts[item.category] = (counts[item.category] || 0) + 1
      return counts
    },
    {}
  )
  const visibleIntegrations = integrations.filter(item => {
    const query = integrationSearch.trim().toLowerCase()
    const matchesQuery =
      !query ||
      item.name.toLowerCase().includes(query) ||
      item.description.toLowerCase().includes(query) ||
      item.key.toLowerCase().includes(query)
    const matchesStatus =
      integrationStatus === 'all' ||
      (integrationStatus === 'configured' ? item.configured : !item.configured)
    const matchesCategory =
      integrationCategory === 'all'
        ? true
        : integrationCategory === 'featured'
        ? isFeaturedIntegration(item)
        : item.category === integrationCategory
    return (
      matchesStatus &&
      matchesQuery &&
      matchesCategory
    )
  })
  const orderedVisibleIntegrations = [...visibleIntegrations].sort((a, b) => {
    const featuredDelta =
      Number(isFeaturedIntegration(b)) - Number(isFeaturedIntegration(a))
    if (featuredDelta !== 0) return featuredDelta
    return a.name.localeCompare(b.name)
  })
  const featuredVisible = orderedVisibleIntegrations.filter(item =>
    isFeaturedIntegration(item)
  )
  const nonFeaturedVisible = orderedVisibleIntegrations.filter(
    item => !isFeaturedIntegration(item)
  )
  const vercelIntegrationDir = '~/.fastfold-cli/vercel-integration'
  const vercelSetupCommands = [
    `cd "${vercelIntegrationDir}"`,
    'vercel login',
    'vercel link',
    'vercel env pull .env.local --environment=development'
  ]
  const renderConfiguredToggle = (configured: boolean, name: string) => (
    <span
      role="switch"
      aria-checked={configured}
      aria-label={`${name} ${configured ? 'configured' : 'not configured'}`}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        configured ? 'bg-black/75 dark:bg-zinc-300/50' : 'bg-zinc-200 dark:bg-zinc-700'
      )}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
          configured ? 'translate-x-4' : 'translate-x-0.5'
        )}
      />
    </span>
  )
  const renderIntegrationCard = (item: IntegrationSummary) => (
    <div
      key={item.key}
      className="bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg p-3 transition-colors"
    >
      <button
        type="button"
        className="min-w-0 flex-1 text-left"
        onClick={() => onSelect(item.key)}
      >
        <div className="flex items-center gap-2">
          <IntegrationIcon integration={item} />
          <span className="truncate text-sm font-medium">{item.name}</span>
          <span className="text-muted-foreground text-xs">{item.category}</span>
        </div>
        <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
          {item.description}
        </p>
      </button>
      <div className="flex items-center pt-0.5">
        {renderConfiguredToggle(item.configured, item.name)}
      </div>
    </div>
  )
  const goBackToIntegrations = () => {
    onSelect(null)
    setValidationMessage(null)
    setSetupResult(null)
    setTerminalOpen(false)
  }

  if (selected) {
    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-6xl px-8 py-8">
          <div className="mb-8 flex items-center gap-2 text-sm">
            <button
              type="button"
              onClick={goBackToIntegrations}
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </button>
            <span className="text-muted-foreground/40">/</span>
            <button
              type="button"
              onClick={goBackToIntegrations}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              Integrations
            </button>
          </div>
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-3">
              <IntegrationIcon integration={selected} size="lg" />
              <div>
                <h2 className="text-xl font-semibold">{selected.name}</h2>
                {selected.key === 'skills-sh' ? (
                  <div className="text-muted-foreground mt-1 space-y-1 text-sm">
                    <p>Use this for Skills.sh catalog search authentication.</p>
                    <ol className="list-inside list-decimal space-y-0.5 text-xs">
                      <li>
                        In{' '}
                        {selected.setupUrl ? (
                          <a
                            href={selected.setupUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="underline"
                          >
                            Vercel Dashboard
                          </a>
                        ) : (
                          'Vercel Dashboard'
                        )}
                        , open the target project, then go to `Settings {'->'}{' '}
                        Security {'->'} OIDC Federation` and enable it.
                      </li>
                      <li>
                        Click{' '}
                        <strong>
                          {selected.configured
                            ? 'Re-link Project'
                            : 'Link Project'}
                        </strong>{' '}
                        - it opens the setup terminal and runs these commands for
                        you.
                      </li>
                      <li>Follow the terminal prompts, then click Test API Key.</li>
                    </ol>
                    <pre className="bg-muted/40 mt-2 rounded border p-2 font-mono text-[11px]">
                      <code>{vercelSetupCommands.join('\n')}</code>
                    </pre>
                  </div>
                ) : (
                  <p className="text-muted-foreground mt-1 text-sm">
                    Preset provider env keys. Fill values and save.
                  </p>
                )}
                {selected.setupUrl && selected.key !== 'skills-sh' ? (
                  <p className="text-muted-foreground mt-1 text-xs">
                    Get API keys at{' '}
                    <a
                      href={selected.setupUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="underline"
                    >
                      {selected.setupUrl}
                    </a>
                  </p>
                ) : null}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {selected.key === 'skills-sh' ? (
                <>
                  <Button
                    variant="secondary"
                    disabled={setupRunning || openingTerminal}
                    onClick={() => {
                      setOpeningTerminal(true)
                      setAutoFetchPending(false)
                      autoFetchAttemptsRef.current = 0
                      void onOpenVercelTerminal()
                        .then(id => {
                          setTerminalSessionId(id)
                          setTerminalOpen(true)
                          setTerminalStartupNonce(current => current + 1)
                          setSetupRunning(true)
                          return onSetup(selected.key)
                        })
                        .then(result => {
                          setSetupResult(result)
                          setValidationMessage(
                            `${result.summary} Use the terminal below to run the listed commands.`
                          )
                          setAutoFetchPending(true)
                        })
                        .catch(error => {
                          setSetupResult(null)
                          setAutoFetchPending(false)
                          setValidationMessage(
                            error instanceof Error
                              ? error.message
                              : 'Unable to open Vercel setup.'
                          )
                        })
                        .finally(() => {
                          setSetupRunning(false)
                          setOpeningTerminal(false)
                        })
                    }}
                  >
                    {setupRunning || openingTerminal ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <img
                        src="/integrations/vercel.png"
                        alt=""
                        className="size-4 rounded object-contain"
                      />
                    )}
                    {selected.configured ? 'Re-link Project' : 'Link Project'}
                  </Button>
                </>
              ) : null}
            </div>
          </div>
          {selected.key === 'skills-sh' && setupResult ? (
            <div className="bg-muted/20 mt-4 rounded-md border p-3">
              <p className="text-sm font-medium">{setupResult.summary}</p>
              <ul className="mt-2 space-y-1">
                {setupResult.steps.map(step => (
                  <li
                    key={step.id}
                    className="text-muted-foreground flex items-start gap-2 text-xs"
                  >
                    <span
                      className={cn(
                        'mt-0.5 inline-block h-2 w-2 rounded-full',
                        step.ok ? 'bg-emerald-500' : 'bg-amber-500'
                      )}
                    />
                    <span>
                      <strong className="text-foreground mr-1">{step.label}:</strong>
                      {step.detail}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {selected.key === 'skills-sh' && terminalOpen && terminalSessionId ? (
            <div className="bg-background mt-4 overflow-hidden rounded-md border">
              <div className="text-muted-foreground border-b px-3 py-2 text-xs">
                Setup terminal in `~/.fastfold-cli/vercel-integration`. Run:
                `vercel login`, `vercel link`, then `vercel env pull`.
              </div>
              <div className="h-[320px]">
                <TerminalPanel
                  client={terminalClient}
                  sessionId={terminalSessionId}
                  visible={terminalOpen}
                  autoCreateOnEmpty
                  startupCommand={vercelSetupRunCommand}
                  startupNonce={terminalStartupNonce}
                  onClose={() => setTerminalOpen(false)}
                />
              </div>
            </div>
          ) : null}
          <div className="mt-5 overflow-hidden rounded-md border">
            <div className="bg-muted/20 text-muted-foreground grid grid-cols-[1.15fr_2fr_1.1fr_auto] border-b px-3 py-2 text-xs">
              <span>Key</span>
              <span>Value</span>
              <span>Status</span>
              <span>Action</span>
            </div>
            {selected.fields.map(field => (
              <div
                key={field.envVar}
                className="grid grid-cols-[1.15fr_2fr_1.1fr_auto] items-center gap-3 border-b px-3 py-3 last:border-b-0"
              >
                <div>
                  <strong className="text-sm">{field.envVar}</strong>
                  <span className="text-muted-foreground block text-xs">
                    {field.label}
                  </span>
                </div>
                <Input
                  type={field.isSecret ? 'password' : 'text'}
                  value={values[field.envVar] || ''}
                  onChange={event =>
                    onValueChange(field.envVar, event.target.value)
                  }
                  placeholder={`Enter ${field.envVar}`}
                />
                <span className="text-muted-foreground text-xs">
                  {field.configured
                    ? `Configured · ${field.maskedPreview || field.source}`
                    : 'Not configured'}
                </span>
                {field.configured ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive"
                    onClick={() => void onRemove(selected.key)}
                  >
                    Remove
                  </Button>
                ) : (
                  <span className="text-muted-foreground px-3">-</span>
                )}
              </div>
            ))}
          </div>
          {validationMessage ? (
            <p className="text-muted-foreground mt-3 text-sm">
              {validationMessage}
            </p>
          ) : null}
          <div className="mt-4 flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() =>
                void onValidate(selected.key).then(result =>
                  setValidationMessage(result.message)
                )
              }
            >
              <CircleCheck className="size-4" />
              Test API Key
            </Button>
            <Button
              disabled={!Object.values(values).some(value => value.trim())}
              onClick={() => void onSave()}
            >
              Save Overrides
            </Button>
          </div>
        </div>
      </ScrollArea>
    )
  }

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 md:p-6 xl:flex-row">
        <div className="min-w-0 flex-1">
          <div className="mb-4">
            <h2 className="text-2xl font-semibold">Integrations</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Connect API keys and services the agent uses for models, search,
              compute, and cloud workflows.
            </p>
          </div>
          <div className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-20 mb-4 flex flex-wrap items-center gap-2 pb-3 pt-2 backdrop-blur">
            <div className="relative min-w-[280px] max-w-3xl flex-1">
              <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
              <Input
                value={integrationSearch}
                onChange={event => setIntegrationSearch(event.target.value)}
                placeholder="Search integrations, descriptions..."
                className="border-border/70 bg-background/70 h-11 pl-10"
              />
            </div>
          </div>
          {loading ? (
            <div className="space-y-4 pb-4">
              <section className="space-y-2">
                <Skeleton className="h-3 w-24" />
                <CardGridSkeleton cards={4} columns={2} />
              </section>
              <section className="space-y-2">
                <Skeleton className="h-3 w-16" />
                <div className="space-y-2">
                  <ListRowsSkeleton rows={5} />
                </div>
              </section>
            </div>
          ) : visibleIntegrations.length === 0 ? (
            <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              No integrations match the current search/filter.
            </div>
          ) : (
            <div className="space-y-4 pb-4">
              {featuredVisible.length > 0 ? (
                <section className="space-y-2">
                  <p className="text-muted-foreground text-xs font-medium">
                    Featured ({featuredVisible.length})
                  </p>
                  <div className="grid gap-3 md:grid-cols-2">
                    {featuredVisible.map(item => renderIntegrationCard(item))}
                  </div>
                </section>
              ) : null}
              {integrationCategory !== 'featured' ? (
                <section className="space-y-2">
                  <p className="text-muted-foreground text-xs font-medium">
                    All ({nonFeaturedVisible.length})
                  </p>
                  <div className="space-y-2">
                    {nonFeaturedVisible.map(item => renderIntegrationCard(item))}
                  </div>
                </section>
              ) : null}
            </div>
          )}
        </div>
        <aside className="flex w-full shrink-0 flex-col gap-4 xl:sticky xl:top-4 xl:self-start xl:w-[320px]">
          <section className="bg-background/70 rounded-lg p-2">
            <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
              Status
            </div>
            <button
              type="button"
              className={cn(
                'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                integrationStatus === 'all'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              onClick={() => setIntegrationStatus('all')}
            >
              All ({integrations.length})
            </button>
            <button
              type="button"
              className={cn(
                'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                integrationStatus === 'configured'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              onClick={() => setIntegrationStatus('configured')}
            >
              Configured ({configuredCount})
            </button>
            <button
              type="button"
              className={cn(
                'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                integrationStatus === 'not_configured'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              onClick={() => setIntegrationStatus('not_configured')}
            >
              Not configured ({notConfiguredCount})
            </button>
          </section>
          <section className="bg-background/70 rounded-lg p-2">
            <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
              Categories
            </div>
            <button
              type="button"
              className={cn(
                'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                integrationCategory === 'all'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              onClick={() => setIntegrationCategory('all')}
            >
              All ({integrations.length})
            </button>
            <button
              type="button"
              className={cn(
                'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                integrationCategory === 'featured'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              onClick={() => setIntegrationCategory('featured')}
            >
              Featured ({featuredCount})
            </button>
            {categories.map(category => (
              <button
                key={category}
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  integrationCategory === category
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setIntegrationCategory(category)}
              >
                {category} ({categoryCounts[category] || 0})
              </button>
            ))}
          </section>
        </aside>
      </div>
    </ScrollArea>
  )
}

function DashboardOverviewView({ sessions }: { sessions: AgentSession[] }) {
  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto max-w-5xl px-6 py-8 sm:px-8 sm:py-10">
        <SessionActivityHeatmap sessions={sessions} />
      </div>
    </ScrollArea>
  )
}

const INTEGRATION_ICONS: Record<
  string,
  { src: string; invertInDark?: boolean }
> = {
  'fastfold-cloud': { src: '/ff_simbol_color.svg' },
  boltz: { src: '/pipelines/boltzgen.svg', invertInDark: true },
  modal: { src: '/modal-logo-icon.png' },
  langsmith: { src: '/langsmith-color.png' },
  nvidia: { src: '/nvidia.svg' },
  opencode: { src: '/opencode.png' },
  openai: { src: '/openai.svg', invertInDark: true },
  'openai-compatible': { src: '/openai.svg', invertInDark: true },
  anthropic: { src: '/anthropic.png', invertInDark: true },
  xai: { src: '/xai.png' },
  google: { src: '/gemini.png' },
  'ibm-rxn': { src: '/ibm.png' },
  lens: { src: '/lens.png' },
  sendgrid: { src: '/sendgrid.png' },
  'lambda-labs': { src: '/lambda.png', invertInDark: true },
  runpod: { src: '/runpod.png' },
  tavily: { src: '/tavily-color.png' },
  slack: { src: '/integrations/slack.png' },
  'skills-sh': { src: '/integrations/vercel.png', invertInDark: true },
  tamarind: { src: '/integrations/tamarind.png' },
  latch: { src: '/integrations/latch.png' },
  neurosnap: { src: '/integrations/neurosnap.png' },
  linear: { src: '/integrations/linear.png' },
}

function IntegrationIcon({
  integration,
  size = 'sm'
}: {
  integration: IntegrationSummary
  size?: 'sm' | 'lg'
}) {
  const icon =
    INTEGRATION_ICONS[integration.key] ??
    (integration.key.startsWith('openai') ? INTEGRATION_ICONS.openai : null)
  const imageClass = size === 'lg' ? 'size-9' : 'size-6'
  const fallbackClass = size === 'lg' ? 'size-9' : 'size-6'
  const fallbackIconClass = size === 'lg' ? 'size-5' : 'size-4'
  if (icon) {
    return (
      <img
        src={icon.src}
        alt=""
        className={cn(
          imageClass,
          'shrink-0 rounded object-contain',
          icon.invertInDark && 'dark:invert'
        )}
      />
    )
  }
  if (integration.key === 'custom-webhook') {
    return (
      <span
        className={cn(
          'bg-muted/30 text-foreground grid shrink-0 place-items-center rounded',
          fallbackClass
        )}
      >
        <Webhook className={fallbackIconClass} />
      </span>
    )
  }
  return (
    <span
      className={cn(
        'bg-muted grid shrink-0 place-items-center rounded text-xs font-semibold',
        fallbackClass
      )}
    >
      {integration.name.slice(0, 2).toUpperCase()}
    </span>
  )
}
