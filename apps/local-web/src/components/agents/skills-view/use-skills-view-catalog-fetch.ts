import type {
  AgentCatalogSkillAudit,
  AgentCatalogSkillDetail,
  AgentSkillDetail
} from '@sandwalk/agent-ui-core'
import { useEffect, useRef, useState } from 'react'

import { catalogCoordsFromInstalledSkill, type SkillsViewMode } from '@/lib/skills-catalog'

const localCatalogCache = new Map<
  string,
  {
    detail: AgentCatalogSkillDetail | null
    audit: AgentCatalogSkillAudit | null
  }
>()

export function clearSkillsCatalogFetchCache() {
  localCatalogCache.clear()
}

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

  const getDetailRef = useRef(onGetCatalogDetail)
  getDetailRef.current = onGetCatalogDetail
  const getAuditRef = useRef(onGetCatalogAudit)
  getAuditRef.current = onGetCatalogAudit

  const routeId = catalogSkillRoute?.id || ''
  const routeSource = catalogSkillRoute?.source || ''
  const routeSkill = catalogSkillRoute?.skill || ''

  useEffect(() => {
    if (mode !== 'catalog_detail' || !routeSource || !routeSkill) {
      setCatalogDetail(null)
      setCatalogAudit(null)
      setCatalogDetailError(null)
      setCatalogDetailLoading(false)
      return
    }
    const cacheKey = `${routeSource}/${routeSkill}`
    const cached = localCatalogCache.get(cacheKey)
    if (cached?.detail) {
      setCatalogDetail(cached.detail)
      setCatalogAudit(cached.audit)
      setCatalogDetailError(null)
      setCatalogDetailLoading(false)
      return
    }

    const controller = new AbortController()
    setCatalogDetailLoading(true)
    setCatalogDetailError(null)
    setCatalogDetail(null)
    setCatalogAudit(null)

    let fetchedDetail: AgentCatalogSkillDetail | null = null
    let fetchedAudit: AgentCatalogSkillAudit | null = null

    const detailPromise = getDetailRef
      .current(routeSource, routeSkill, controller.signal)
      .then(result => {
        if (!controller.signal.aborted) {
          fetchedDetail = result
          setCatalogDetail(result)
        }
      })
      .catch(error => {
        if (!controller.signal.aborted) {
          setCatalogDetailError(
            error instanceof Error
              ? error.message
              : 'Unable to load catalog skill details.'
          )
        }
      })

    const auditPromise = getAuditRef
      .current(routeSource, routeSkill, controller.signal)
      .then(result => {
        if (!controller.signal.aborted) {
          fetchedAudit = result
          setCatalogAudit(result)
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          fetchedAudit = {
            id: routeId || cacheKey,
            source: routeSource,
            slug: routeSkill,
            audits: []
          }
          setCatalogAudit(fetchedAudit)
        }
      })

    void Promise.allSettled([detailPromise, auditPromise]).then(() => {
      if (!controller.signal.aborted) {
        if (fetchedDetail) {
          localCatalogCache.set(cacheKey, {
            detail: fetchedDetail,
            audit: fetchedAudit
          })
        }
        setCatalogDetailLoading(false)
      }
    })

    return () => controller.abort()
  }, [mode, routeId, routeSkill, routeSource])

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

  const getDetailRef = useRef(onGetCatalogDetail)
  getDetailRef.current = onGetCatalogDetail
  const getAuditRef = useRef(onGetCatalogAudit)
  getAuditRef.current = onGetCatalogAudit

  const coords = detail ? catalogCoordsFromInstalledSkill(detail) : null
  const coordsSource = coords?.source || ''
  const coordsSkill = coords?.skill || ''
  const detailName = detail?.name || ''

  useEffect(() => {
    if (mode !== 'detail' || !detailName || !catalogSearchEnabled) {
      setLocalCatalogDetail(null)
      setLocalCatalogAudit(null)
      setLocalCatalogLoading(false)
      return
    }
    if (!coordsSource || !coordsSkill) {
      setLocalCatalogDetail(null)
      setLocalCatalogAudit(null)
      setLocalCatalogLoading(false)
      return
    }

    const cacheKey = `${coordsSource}/${coordsSkill}`
    const cached = localCatalogCache.get(cacheKey)
    if (cached) {
      setLocalCatalogDetail(cached.detail)
      setLocalCatalogAudit(cached.audit)
      setLocalCatalogLoading(false)
      return
    }

    const controller = new AbortController()
    setLocalCatalogLoading(true)
    setLocalCatalogDetail(null)
    setLocalCatalogAudit(null)

    let fetchedDetail: AgentCatalogSkillDetail | null = null
    let fetchedAudit: AgentCatalogSkillAudit | null = null

    const detailPromise = getDetailRef
      .current(coordsSource, coordsSkill, controller.signal)
      .then(result => {
        if (!controller.signal.aborted) {
          fetchedDetail = result
          setLocalCatalogDetail(result)
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setLocalCatalogDetail(null)
      })

    const auditPromise = getAuditRef
      .current(coordsSource, coordsSkill, controller.signal)
      .then(result => {
        if (!controller.signal.aborted) {
          fetchedAudit = result
          setLocalCatalogAudit(result)
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          fetchedAudit = {
            id: cacheKey,
            source: coordsSource,
            slug: coordsSkill,
            audits: []
          }
          setLocalCatalogAudit(fetchedAudit)
        }
      })

    void Promise.allSettled([detailPromise, auditPromise]).then(() => {
      if (!controller.signal.aborted) {
        localCatalogCache.set(cacheKey, {
          detail: fetchedDetail,
          audit: fetchedAudit
        })
        setLocalCatalogLoading(false)
      }
    })
    return () => controller.abort()
  }, [catalogSearchEnabled, coordsSkill, coordsSource, detailName, mode])

  return {
    localCatalogDetail,
    localCatalogAudit,
    localCatalogLoading
  }
}
