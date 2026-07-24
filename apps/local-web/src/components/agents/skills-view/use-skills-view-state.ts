import type {
  AgentCatalogLeaderboardView,
  AgentCatalogSkill,
  AgentCatalogSkillAudit,
  AgentCatalogSkillDetail,
  AgentSkill,
  AgentSkillBatchAction,
  AgentSkillBatchResult,
  AgentSkillDetail,
  AgentSkillSource
} from '@sandwalk/agent-ui-core'
import { useState } from 'react'

import type { SkillsViewMode } from '@/lib/skills-catalog'

import { useSkillsViewCatalog } from './use-skills-view-catalog'
import { useSkillsViewFilters } from './use-skills-view-filters'
import { useSkillsViewImport } from './use-skills-view-import'
import { useSkillsViewListActions } from './use-skills-view-list-actions'

export type SkillsViewInput = {
  mode: SkillsViewMode
  skills: AgentSkill[]
  detail: AgentSkillDetail | null
  catalogSkillRoute: { id: string; source: string; skill: string } | null
  catalogSearchEnabled: boolean
  openCatalogSearchInitially?: boolean
  onOpen: (name: string) => void
  onBack: () => void
  onOpenCatalogSetup: () => void
  onInstall: (source: string) => Promise<string[] | void>
  onUpload: (file: File) => Promise<void>
  onLoadSuggestedSources: (signal?: AbortSignal) => Promise<AgentSkillSource[]>
  onSearchCatalog: (
    query: string,
    signal?: AbortSignal
  ) => Promise<AgentCatalogSkill[]>
  onListCatalogLeaderboard: (
    view: AgentCatalogLeaderboardView,
    options?: { page?: number; perPage?: number },
    signal?: AbortSignal
  ) => Promise<{
    data: AgentCatalogSkill[]
    total: number
    allTimeTotal: number
    hasMore: boolean
    page: number
  }>
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
  onUpgrade: () => Promise<string[]>
}

export function useSkillsViewState({
  mode,
  skills,
  detail,
  catalogSkillRoute,
  catalogSearchEnabled,
  openCatalogSearchInitially = false,
  onOpen,
  onBack,
  onOpenCatalogSetup,
  onInstall,
  onUpload,
  onLoadSuggestedSources,
  onSearchCatalog,
  onListCatalogLeaderboard,
  onGetCatalogDetail,
  onGetCatalogAudit,
  onBulkAction,
  onSetEnabled,
  onRemove,
  onUpgrade
}: SkillsViewInput) {
  const [installing, setInstalling] = useState(false)

  const filters = useSkillsViewFilters(skills)

  const importState = useSkillsViewImport({
    mode,
    installing,
    setInstalling,
    onBack,
    onInstall,
    onUpload,
    onLoadSuggestedSources
  })

  const listActions = useSkillsViewListActions({
    mode,
    detail,
    listData: filters.listData,
    onBack,
    onBulkAction,
    onSetEnabled,
    onRemove,
    onUpgrade
  })

  const catalog = useSkillsViewCatalog({
    mode,
    detail,
    catalogSkillRoute,
    catalogSearchEnabled,
    openCatalogSearchInitially,
    query: filters.query,
    installing,
    batchBusy: listActions.batchBusy,
    setInstalling,
    onOpen,
    onBack,
    onOpenCatalogSetup,
    onInstall,
    onSearchCatalog,
    onListCatalogLeaderboard,
    onGetCatalogDetail,
    onGetCatalogAudit
  })

  return {
    ...filters,
    ...importState,
    ...catalog,
    ...listActions,
    installing
  }
}
