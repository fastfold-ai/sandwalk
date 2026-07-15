import type {
  AgentSkill,
  McpCatalogEntry,
  McpServer,
  Specialist,
  ToolCatalog
} from '@sandwalk/agent-ui-core'
import { useMemo } from 'react'

import { useSpecialistsEditorActions } from './use-specialists-editor-actions'
import {
  useSpecialistsEditorForm,
  useSpecialistsEditorSelection
} from './use-specialists-editor-form'
import { useSpecialistsEditorTools } from './use-specialists-editor-tools'

export type SpecialistsEditorInput = {
  mode: 'new' | 'edit'
  specialistId: string | null
  specialists: Specialist[]
  skills: AgentSkill[]
  mcpServers: McpServer[]
  mcpCatalog?: McpCatalogEntry[]
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
  onOpenEdit: (id: string) => void
  onBack: () => void
  onManageSkills?: () => void
  onEnableSkill?: (name: string) => Promise<void>
  onInstallSkill?: (source: string) => Promise<void>
  onListTools?: (signal?: AbortSignal) => Promise<ToolCatalog>
}

export function useSpecialistsEditor({
  mode,
  specialistId,
  specialists,
  skills,
  mcpServers,
  mcpCatalog = [],
  onRefresh,
  onCreate,
  onUpdate,
  onDelete,
  onOpenEdit,
  onBack,
  onManageSkills,
  onEnableSkill,
  onInstallSkill,
  onListTools
}: SpecialistsEditorInput) {
  const editing = useMemo(
    () =>
      mode === 'edit'
        ? specialists.find(item => item.id === specialistId) || null
        : null,
    [mode, specialistId, specialists]
  )

  const formState = useSpecialistsEditorForm({ mode, editing })

  const tools = useSpecialistsEditorTools({
    mode,
    editing,
    setForm: formState.setForm,
    onListTools
  })

  const selection = useSpecialistsEditorSelection({
    form: formState.form,
    setForm: formState.setForm,
    skills,
    mcpServers,
    mcpCatalog,
    skillAddQuery: formState.skillAddQuery,
    mcpAddQuery: formState.mcpAddQuery,
    setSkillAddQuery: formState.setSkillAddQuery,
    setMcpAddQuery: formState.setMcpAddQuery,
    setSkillAddOpen: formState.setSkillAddOpen,
    setMcpAddOpen: formState.setMcpAddOpen
  })

  const actions = useSpecialistsEditorActions({
    mode,
    specialistId,
    form: formState.form,
    onRefresh,
    onCreate,
    onUpdate,
    onDelete,
    onOpenEdit,
    onBack,
    onManageSkills,
    onEnableSkill,
    onInstallSkill
  })

  return {
    editing,
    ...formState,
    ...tools,
    ...selection,
    ...actions
  }
}

export type SpecialistsEditorState = ReturnType<typeof useSpecialistsEditor>
