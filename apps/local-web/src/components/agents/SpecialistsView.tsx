import type {
  AgentSkill,
  McpCatalogEntry,
  McpServer,
  Specialist,
  ToolCatalog
} from '@sandwalk/agent-ui-core'

import { SpecialistsEditorView } from '@/components/agents/specialists-view/specialists-view-editor'
import { SpecialistsListView } from '@/components/agents/specialists-view/specialists-view-list'
import {
  SPECIALIST_COLORS,
  SPECIALIST_ICONS,
  SpecialistAvatar,
  SpecialistGlyph,
  specialistColorClass
} from '@/components/agents/specialists-view/specialist-ui'
import { resolveSkillInstallSource } from '@/components/agents/specialists-view/specialists-view-utils'

export {
  SPECIALIST_COLORS,
  SPECIALIST_ICONS,
  SpecialistAvatar,
  SpecialistGlyph,
  specialistColorClass,
  resolveSkillInstallSource
}

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
  onListTools
}: {
  mode: 'list' | 'new' | 'edit'
  specialistId: string | null
  specialists: Specialist[]
  skills: AgentSkill[]
  mcpServers: McpServer[]
  mcpCatalog?: McpCatalogEntry[]
  loading?: boolean
  onRefresh: () => Promise<void>
  onCreate: (input: {
    name: string
    slug?: string | null
    description?: string | null
    instructions?: string | null
    color?: string
    icon?: string
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
}) {
  if (mode === 'list') {
    return (
      <SpecialistsListView
        specialists={specialists}
        loading={loading}
        onOpenNew={onOpenNew}
        onOpenEdit={onOpenEdit}
        onUpdate={onUpdate}
        onRefresh={onRefresh}
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
