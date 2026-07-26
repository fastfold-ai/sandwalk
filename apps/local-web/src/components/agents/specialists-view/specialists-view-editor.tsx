import type {
  AgentSkill,
  McpCatalogEntry,
  McpServer,
  Specialist,
  ToolCatalog
} from '@sandwalk/agent-ui-core'

import { SpecialistsEditorMcpsSection } from '@/components/agents/specialists-view/specialists-editor-mcps-section'
import { SpecialistsEditorSkillsSection } from '@/components/agents/specialists-view/specialists-editor-skills-section'
import { SpecialistsEditorToolsSection } from '@/components/agents/specialists-view/specialists-editor-tools-section'
import { Button } from '@/components/ui/button'

import {
  SpecialistsEditorAppearanceFields,
  SpecialistsEditorCapabilityBanner,
  SpecialistsEditorHeader
} from './specialists-editor-form-fields'
import { useSpecialistsEditor } from './use-specialists-editor'

export function SpecialistsEditorView({
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
  mode: 'new' | 'edit'
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
  const state = useSpecialistsEditor({
    mode,
    specialistId,
    specialists,
    skills,
    mcpServers,
    mcpCatalog,
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
  })

  if (mode === 'edit' && !state.editing && !loading) {
    return (
      <div className="chat-scrollbar flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 pt-2 pb-4 md:px-6 md:pt-3 md:pb-6">
          <p className="text-sm">Specialist not found.</p>
          <div>
            <Button type="button" variant="ghost" size="sm" onClick={onBack}>
              Back to specialists
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <SpecialistsEditorHeader
        mode={mode}
        specialistId={specialistId}
        state={state}
        onBack={onBack}
      />
      <div className="chat-scrollbar min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 pt-2 pb-8 md:gap-8 md:px-6 md:pt-3 md:pb-10">
          <SpecialistsEditorCapabilityBanner state={state} />
          <SpecialistsEditorAppearanceFields state={state} />

          <SpecialistsEditorSkillsSection
            skillCount={state.form.skillNames.length}
            onManageSkills={onManageSkills}
            skillAddOpen={state.skillAddOpen}
            onSkillAddOpenChange={state.setSkillAddOpen}
            skillAddQuery={state.skillAddQuery}
            onSkillAddQueryChange={state.setSkillAddQuery}
            availableSkills={state.availableSkills}
            onAddSkill={state.addSkill}
            selectedSkillRows={state.selectedSkillRows}
            onOpenSkill={onOpenSkill}
            skillActionPending={state.skillActionPending}
            onEnableSkill={onEnableSkill}
            onEnableSkillClick={name => void state.handleEnableSkill(name)}
            onInstallSkillClick={name => void state.handleInstallSkill(name)}
            onRemoveSkill={state.removeSkill}
          />

          <SpecialistsEditorToolsSection
            toolCount={state.form.toolNames.length}
            toolNames={state.form.toolNames}
            toolQuery={state.toolQuery}
            onToolQueryChange={state.setToolQuery}
            toolsLoading={state.toolsLoading}
            catalogToolCount={state.catalogTools.length}
            coreTools={state.coreTools}
            extraTools={state.extraTools}
            onSetTierTools={state.setTierTools}
            onToggleTool={state.toggleTool}
          />

          <SpecialistsEditorMcpsSection
            mcpCount={state.selectedMcpRows.length}
            onManageMcps={onManageMcps}
            mcpAddOpen={state.mcpAddOpen}
            onMcpAddOpenChange={state.setMcpAddOpen}
            mcpAddQuery={state.mcpAddQuery}
            onMcpAddQueryChange={state.setMcpAddQuery}
            availableMcps={state.availableMcps}
            onAddMcp={state.addMcp}
            selectedMcpRows={state.selectedMcpRows}
            onOpenMcp={onOpenMcp}
            onRemoveMcp={state.removeMcp}
            onRemoveMcpCatalog={state.removeMcpCatalog}
          />
        </div>
      </div>

      <div className="border-border/60 bg-background flex shrink-0 items-center justify-end gap-1 border-t">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-end gap-1 px-4 py-3 md:px-6">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onBack}
            disabled={state.saving}
          >
            Cancel
          </Button>
          <Button
            type="button"
            size="sm"
            className="rounded-full px-4"
            disabled={state.saving}
            onClick={() => void state.save()}
          >
            {state.saving
              ? 'Saving…'
              : mode === 'new'
                ? 'Create specialist'
                : 'Save'}
          </Button>
        </div>
      </div>
    </div>
  )
}
