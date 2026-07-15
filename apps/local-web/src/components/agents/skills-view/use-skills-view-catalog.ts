import type {
  AgentCatalogSkill,
  AgentCatalogSkillAudit,
  AgentCatalogSkillDetail,
  AgentSkillDetail
} from '@sandwalk/agent-ui-core'
import { useEffect, useState } from 'react'

import {
  formatSkillInstallError,
  type SkillsViewMode
} from '@/lib/skills-catalog'

import {
  useSkillsViewCatalogLocal,
  useSkillsViewCatalogRoute
} from './use-skills-view-catalog-fetch'
import { useSkillsViewCatalogSearch } from './use-skills-view-catalog-search'

type SkillsViewCatalogInput = {
  mode: SkillsViewMode
  detail: AgentSkillDetail | null
  catalogSkillRoute: { id: string; source: string; skill: string } | null
  catalogSearchEnabled: boolean
  openCatalogSearchInitially?: boolean
  query: string
  installing: boolean
  batchBusy: boolean
  setInstalling: (value: boolean) => void
  onOpen: (name: string) => void
  onBack: () => void
  onOpenCatalogSetup: () => void
  onInstall: (source: string) => Promise<string[] | void>
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
}

export function useSkillsViewCatalog({
  mode,
  detail,
  catalogSkillRoute,
  catalogSearchEnabled,
  openCatalogSearchInitially = false,
  query,
  installing,
  batchBusy,
  setInstalling,
  onOpen,
  onBack,
  onOpenCatalogSetup,
  onInstall,
  onSearchCatalog,
  onGetCatalogDetail,
  onGetCatalogAudit
}: SkillsViewCatalogInput) {
  const [catalogSearchMode, setCatalogSearchMode] = useState(
    openCatalogSearchInitially && catalogSearchEnabled
  )
  const [catalogInstallingId, setCatalogInstallingId] = useState<string | null>(null)
  const [copiedCatalogInstall, setCopiedCatalogInstall] = useState(false)
  const [catalogInstallError, setCatalogInstallError] = useState<string | null>(null)

  const route = useSkillsViewCatalogRoute({
    mode,
    catalogSkillRoute,
    onGetCatalogDetail,
    onGetCatalogAudit
  })

  const local = useSkillsViewCatalogLocal({
    mode,
    detail,
    catalogSearchEnabled,
    onGetCatalogDetail,
    onGetCatalogAudit
  })

  const search = useSkillsViewCatalogSearch({
    catalogSearchMode,
    query,
    onSearchCatalog
  })

  useEffect(() => {
    if (mode !== 'catalog_detail' || !catalogSkillRoute) return
    setCatalogInstallError(null)
  }, [catalogSkillRoute, mode])

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
    search.setCatalogError(null)
    setCatalogSearchMode(true)
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

  const showCatalogEmptyState =
    catalogSearchMode &&
    !search.catalogLoading &&
    !search.catalogError &&
    query.trim().length >= 2 &&
    search.catalogResults.length === 0

  return {
    catalogResults: search.catalogResults,
    catalogLoading: search.catalogLoading,
    catalogError: search.catalogError,
    catalogSearchMode,
    setCatalogSearchMode,
    setCatalogResults: search.setCatalogResults,
    setCatalogError: search.setCatalogError,
    catalogInstallingId,
    catalogDetail: route.catalogDetail,
    catalogAudit: route.catalogAudit,
    catalogDetailLoading: route.catalogDetailLoading,
    catalogDetailError: route.catalogDetailError,
    copiedCatalogInstall,
    setCopiedCatalogInstall,
    catalogInstallError,
    localCatalogDetail: local.localCatalogDetail,
    localCatalogAudit: local.localCatalogAudit,
    localCatalogLoading: local.localCatalogLoading,
    enableCatalogSearchMode,
    submitCatalogInstallSource,
    showCatalogEmptyState
  }
}
