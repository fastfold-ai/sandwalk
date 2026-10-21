import type { AgentSession } from '@sandwalk/agent-ui-core'
import {
  Box,
  Boxes,
  Cpu,
  Database,
  GitBranch,
  HardDrive,
  LayoutDashboard,
  LibraryBig,
  Mic,
  Paintbrush,
  Plug,
  ScrollText,
  Settings2,
  Sparkles,
  Stethoscope,
  Target,
  Terminal,
  Wrench
} from 'lucide-react'

import { McpMark } from '@/components/McpMark'

export type SearchScope = 'all' | 'artifacts' | 'sessions'

export type IndexedArtifact = {
  path: string
  name: string
  sessionId: string
  sessionTitle: string
  mtime: string | null
}

export const ARTIFACT_LIMIT = 40
export const SESSION_LIMIT = 30
export const INDEX_SESSION_LIMIT = 40

export function matchesQuery(haystack: string, query: string) {
  if (!query) return true
  return haystack.toLowerCase().includes(query.toLowerCase())
}

export function sessionRecency(session: AgentSession) {
  const stamp = session.lastMessageAt || session.updatedAt || session.createdAt
  const time = stamp ? new Date(stamp).getTime() : 0
  return Number.isFinite(time) ? time : 0
}

/** One row per title (case-insensitive); keep the most recently active session. */
export function uniqueSessionsByTitle(sessions: AgentSession[]) {
  const byId = new Map<string, AgentSession>()
  for (const session of sessions) {
    if (!byId.has(session.id)) byId.set(session.id, session)
  }
  const sorted = [...byId.values()].sort(
    (a, b) => sessionRecency(b) - sessionRecency(a)
  )
  const seenTitles = new Set<string>()
  const unique: AgentSession[] = []
  for (const session of sorted) {
    const key = session.title.trim().toLowerCase() || session.id
    if (seenTitles.has(key)) continue
    seenTitles.add(key)
    unique.push(session)
  }
  return unique
}

export function scopeLabel(scope: SearchScope) {
  if (scope === 'artifacts') return 'Artifacts'
  if (scope === 'sessions') return 'Sessions'
  return null
}

export function placeholderFor(scope: SearchScope) {
  if (scope === 'artifacts') return 'Search artifacts...'
  if (scope === 'sessions') return 'Search sessions...'
  return 'Search this project...'
}

export const DASHBOARD_COMMANDS = [
  {
    id: 'overview',
    label: 'Overview',
    path: '/dashboard',
    value: 'command overview dashboard',
    icon: LayoutDashboard
  },
  {
    id: 'library',
    label: 'Library',
    path: '/library',
    value: 'command library files documents images uploads',
    icon: LibraryBig
  },
  {
    id: 'general',
    label: 'General',
    path: '/dashboard/general',
    value: 'command general settings',
    icon: Settings2
  },
  {
    id: 'appearance',
    label: 'Appearance',
    path: '/dashboard/appearance',
    value: 'command appearance theme palette color font sidebar glass',
    icon: Paintbrush
  },
  {
    id: 'agent_runtime',
    label: 'Agent Runtime',
    path: '/dashboard/agent/runtime',
    value: 'command agent runtime recursion langgraph tool mode',
    icon: Cpu
  },
  {
    id: 'agent_sandbox',
    label: 'Agent Sandbox',
    path: '/dashboard/agent/sandbox',
    value: 'command agent sandbox modal builtin workspace',
    icon: Boxes
  },
  {
    id: 'context',
    label: 'Context',
    path: '/dashboard/context',
    value: 'command context prompts token budget specialist',
    icon: ScrollText
  },
  {
    id: 'voice',
    label: 'Voice',
    path: '/dashboard/voice',
    value: 'command voice input microphone dictation whisper speech',
    icon: Mic
  },
  {
    id: 'models',
    label: 'Models',
    path: '/dashboard/models',
    value: 'command models llm providers profiles',
    icon: Box
  },
  {
    id: 'datasets',
    label: 'Datasets',
    path: '/dashboard/datasets',
    value: 'command datasets data download install',
    icon: Database
  },
  {
    id: 'tools',
    label: 'Tools',
    path: '/dashboard/tools',
    value: 'command tools registry enable disable',
    icon: Wrench
  },
  {
    id: 'bench',
    label: 'Bench',
    path: '/dashboard/bench',
    value: 'command bench evaluate mmlu bixbench',
    icon: Target
  },
  {
    id: 'doctor',
    label: 'Doctor',
    path: '/dashboard/doctor',
    value: 'command doctor diagnostics health',
    icon: Stethoscope
  },
  {
    id: 'logs',
    label: 'Logs',
    path: '/dashboard/logs',
    value: 'command logs services daemon pid port memory',
    icon: Terminal
  },
  {
    id: 'storage',
    label: 'Storage',
    path: '/dashboard/storage',
    value: 'command storage disk usage datasets artifacts',
    icon: HardDrive
  },
  {
    id: 'environment',
    label: 'Environment',
    path: '/dashboard/environment',
    value: 'command environment python packages install torch rdkit',
    icon: Boxes
  },
  {
    id: 'skills',
    label: 'Skills',
    path: '/dashboard/skills',
    value: 'command skills',
    icon: Sparkles
  },
  {
    id: 'specialists',
    label: 'Specialists',
    path: '/dashboard/specialists',
    value: 'command specialists agent profiles',
    icon: GitBranch
  },
  {
    id: 'integrations',
    label: 'Integrations',
    path: '/dashboard/integrations',
    value: 'command integrations',
    icon: Plug
  },
  {
    id: 'mcp',
    label: 'MCPs',
    path: '/dashboard/mcp',
    value: 'command mcp servers',
    icon: McpMark
  }
] as const
