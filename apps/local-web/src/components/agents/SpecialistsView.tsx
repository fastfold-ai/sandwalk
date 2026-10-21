import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSkill,
  McpCatalogEntry,
  McpServer,
  Specialist,
  ToolCatalog
} from '@sandwalk/agent-ui-core'

import {
  SPECIALIST_COLORS,
  SPECIALIST_ICONS,
  SpecialistAvatar,
  specialistColorClass,
  SpecialistGlyph} from '@/components/agents/specialists-view/specialist-ui'
import { SpecialistsEditorView } from '@/components/agents/specialists-view/specialists-view-editor'
import { SpecialistsListView } from '@/components/agents/specialists-view/specialists-view-list'
import { resolveSkillInstallSource } from '@/components/agents/specialists-view/specialists-view-utils'

export {
  resolveSkillInstallSource,
  SPECIALIST_COLORS,
  SPECIALIST_ICONS,
  SpecialistAvatar,
  specialistColorClass,
  SpecialistGlyph}

export function SpecialistsView({
  mode,
  specialistId,
  specialists,
  skills,
  mcpServers,
  mcpCatalog = [],
  loading,
  onRefresh,
  onCreate,
  onUpdate,
  onDelete,
  onOpenNew,
  onOpenEdit,
  onBack,
  onManageSkills,
  onManageMcps,
  onOpenSkill,
  onOpenMcp,
  onEnableSkill,
  onInstallSkill,
  onListTools,
  client,
  userName,
  onStartChat,
  onExploreBrain,
  onOpenDefaults
}: {
  mode: 'list' | 'new' | 'edit'
  specialistId: string | null
  specialists: Specialist[]
  skills: AgentSkill[]
  mcpServers: McpServer[]
  mcpCatalog?: McpCatalogEntry[]
  loading?: boolean
  client?: LocalAgentClient
  userName?: string | null
  onRefresh: () => Promise<void>
  onCreate: (input: {
    name: string
    slug?: string | null
    description?: string | null
    instructions?: string | null
    color?: string
    icon?: string
    roleLabel?: string | null
    avatarUrl?: string | null
    provider?: string | null
    model?: string | null
    cookbookId?: string | null
    priors?: string | null
    skillNames?: string[]
    toolNames?: string[]
    mcpServerIds?: string[]
    mcpCatalogIds?: string[]
    enabled?: boolean
  }) => Promise<Specialist>
  onUpdate: (
    id: string,
    input: {
      name?: string
      slug?: string | null
      description?: string | null
      instructions?: string | null
      color?: string
      icon?: string
      roleLabel?: string | null
      avatarUrl?: string | null
      provider?: string | null
      model?: string | null
      clearLlm?: boolean
      cookbookId?: string | null
      priors?: string | null
      skillNames?: string[]
      toolNames?: string[]
      mcpServerIds?: string[]
      mcpCatalogIds?: string[]
      enabled?: boolean
    }
  ) => Promise<Specialist>
  onDelete: (id: string) => Promise<void>
  onOpenNew: () => void
  onOpenEdit: (id: string) => void
  onBack: () => void
  onManageSkills?: () => void
  onManageMcps?: () => void
  onOpenSkill?: (name: string) => void
  onOpenMcp?: (target: {
    kind: 'server' | 'catalog'
    id: string
  }) => void
  onEnableSkill?: (name: string) => Promise<void>
  onInstallSkill?: (source: string) => Promise<void>
  onListTools?: (signal?: AbortSignal) => Promise<ToolCatalog>
  onStartChat?: (specialist: Specialist) => void
  onExploreBrain?: (specialist: Specialist) => void
  onOpenDefaults?: () => void
}) {
  if (mode === 'list') {
    return (
      <SpecialistsListView
        specialists={specialists}
        loading={loading}
        client={client}
        userName={userName}
        onOpenNew={onOpenNew}
        onOpenEdit={onOpenEdit}
        onUpdate={onUpdate}
        onDelete={onDelete}
        onRefresh={onRefresh}
        onStartChat={onStartChat}
        onExploreBrain={onExploreBrain}
        onOpenDefaults={onOpenDefaults}
      />
    )
  }

  return (
    <SpecialistsEditorView
      mode={mode}
      specialistId={specialistId}
      specialists={specialists}
      skills={skills}
      mcpServers={mcpServers}
      mcpCatalog={mcpCatalog}
      loading={loading}
      onRefresh={onRefresh}
      onCreate={onCreate}
      onUpdate={onUpdate}
      onDelete={onDelete}
      onOpenEdit={onOpenEdit}
      onBack={onBack}
      onManageSkills={onManageSkills}
      onManageMcps={onManageMcps}
      onOpenSkill={onOpenSkill}
      onOpenMcp={onOpenMcp}
      onEnableSkill={onEnableSkill}
      onInstallSkill={onInstallSkill}
      onListTools={onListTools}
    />
  )
}
