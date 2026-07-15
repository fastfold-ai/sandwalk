import type {
  AgentCatalogSkill,
  AgentCatalogSkillAudit,
  AgentCatalogSkillDetail,
  AgentSkillDetail
} from '@sandwalk/agent-ui-core'
import { useEffect, useState } from 'react'

import {
  catalogCoordsFromInstalledSkill,
  formatSkillInstallError,
  type SkillsViewMode
} from '@/lib/skills-catalog'

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
  const [catalogResults, setCatalogResults] = useState<AgentCatalogSkill[]>([])
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [catalogSearchMode, setCatalogSearchMode] = useState(
    openCatalogSearchInitially && catalogSearchEnabled
  )
  const [catalogInstallingId, setCatalogInstallingId] = useState<string | null>(null)
  const [catalogDetail, setCatalogDetail] = useState<AgentCatalogSkillDetail | null>(null)
  const [catalogAudit, setCatalogAudit] = useState<AgentCatalogSkillAudit | null>(null)
  const [catalogDetailLoading, setCatalogDetailLoading] = useState(false)
  const [catalogDetailError, setCatalogDetailError] = useState<string | null>(null)
  const [copiedCatalogInstall, setCopiedCatalogInstall] = useState(false)
  const [catalogInstallError, setCatalogInstallError] = useState<string | null>(null)
  const [localCatalogDetail, setLocalCatalogDetail] =
    useState<AgentCatalogSkillDetail | null>(null)
  const [localCatalogAudit, setLocalCatalogAudit] =
    useState<AgentCatalogSkillAudit | null>(null)
  const [localCatalogLoading, setLocalCatalogLoading] = useState(false)

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
    setCatalogDetail(null)
    setCatalogAudit(null)
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
      setLocalCatalogLoading(false)
      return
    }
    const coords = catalogCoordsFromInstalledSkill(detail)
    if (!coords) {
      setLocalCatalogDetail(null)
      setLocalCatalogAudit(null)
      setLocalCatalogLoading(false)
      return
    }
    const controller = new AbortController()
    setLocalCatalogLoading(true)
    setLocalCatalogDetail(null)
    setLocalCatalogAudit(null)
    const detailPromise = onGetCatalogDetail(
      coords.source,
      coords.skill,
      controller.signal
    )
      .then(result => {
        if (!controller.signal.aborted) setLocalCatalogDetail(result)
      })
      .catch(() => {
        if (!controller.signal.aborted) setLocalCatalogDetail(null)
      })
    const auditPromise = onGetCatalogAudit(
      coords.source,
      coords.skill,
      controller.signal
    )
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
    void Promise.allSettled([detailPromise, auditPromise]).then(() => {
      if (!controller.signal.aborted) setLocalCatalogLoading(false)
    })
    return () => controller.abort()
  }, [catalogSearchEnabled, detail, mode, onGetCatalogAudit, onGetCatalogDetail])

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

  const enableCatalogSearchMode = () => {
    if (!catalogSearchEnabled) {
      onOpenCatalogSetup()
      return
    }
    setCatalogError(null)
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
    !catalogLoading &&
    !catalogError &&
    query.trim().length >= 2 &&
    catalogResults.length === 0

  return {
    catalogResults,
    catalogLoading,
    catalogError,
    catalogSearchMode,
    setCatalogSearchMode,
    setCatalogResults,
    setCatalogError,
    catalogInstallingId,
    catalogDetail,
    catalogAudit,
    catalogDetailLoading,
    catalogDetailError,
    copiedCatalogInstall,
    setCopiedCatalogInstall,
    catalogInstallError,
    localCatalogDetail,
    localCatalogAudit,
    localCatalogLoading,
    enableCatalogSearchMode,
    submitCatalogInstallSource,
    showCatalogEmptyState
  }
}
