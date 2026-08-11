import type {
  AgentCatalogSkillAudit,
  AgentCatalogSkillDetail,
  AgentSkillDetail
} from '@sandwalk/agent-ui-core'
import { useEffect, useState } from 'react'

import { catalogCoordsFromInstalledSkill, type SkillsViewMode } from '@/lib/skills-catalog'

export function useSkillsViewCatalogRoute({
  mode,
  catalogSkillRoute,
  onGetCatalogDetail,
  onGetCatalogAudit
}: {
  mode: SkillsViewMode
  catalogSkillRoute: { id: string; source: string; skill: string } | null
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
}) {
  const [catalogDetail, setCatalogDetail] = useState<AgentCatalogSkillDetail | null>(null)
  const [catalogAudit, setCatalogAudit] = useState<AgentCatalogSkillAudit | null>(null)
  const [catalogDetailLoading, setCatalogDetailLoading] = useState(false)
  const [catalogDetailError, setCatalogDetailError] = useState<string | null>(null)

  useEffect(() => {
    if (mode !== 'catalog_detail' || !catalogSkillRoute) {
      setCatalogDetail(null)
      setCatalogAudit(null)
      setCatalogDetailError(null)
      setCatalogDetailLoading(false)
      return
    }
    const controller = new AbortController()
    setCatalogDetailLoading(true)
    setCatalogDetailError(null)
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

  return {
    catalogDetail,
    catalogAudit,
    catalogDetailLoading,
    catalogDetailError,
    setCatalogDetailError
  }
}

export function useSkillsViewCatalogLocal({
  mode,
  detail,
  catalogSearchEnabled,
  onGetCatalogDetail,
  onGetCatalogAudit
}: {
  mode: SkillsViewMode
  detail: AgentSkillDetail | null
  catalogSearchEnabled: boolean
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
}) {
  const [localCatalogDetail, setLocalCatalogDetail] =
    useState<AgentCatalogSkillDetail | null>(null)
  const [localCatalogAudit, setLocalCatalogAudit] =
    useState<AgentCatalogSkillAudit | null>(null)
  const [localCatalogLoading, setLocalCatalogLoading] = useState(false)

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

  return {
    localCatalogDetail,
    localCatalogAudit,
    localCatalogLoading
  }
}
