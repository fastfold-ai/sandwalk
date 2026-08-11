import type { AgentCatalogSkill, AgentSkill } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  buildInstalledSkillIndex,
  computeSkillsListData,
  isCatalogSkillInstalled
} from './skills-view-utils'

export function useSkillsViewFilters(skills: AgentSkill[]) {
  const [query, setQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [authorFilter, setAuthorFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'enabled' | 'disabled'>(
    'all'
  )

  const listData = useMemo(
    () =>
      computeSkillsListData(skills, {
        query,
        categoryFilter,
        authorFilter,
        statusFilter
      }),
    [skills, query, categoryFilter, authorFilter, statusFilter]
  )

  useEffect(() => {
    if (
      categoryFilter !== 'all' &&
      categoryFilter !== 'featured' &&
      !listData.categories.includes(categoryFilter)
    ) {
      setCategoryFilter('all')
    }
  }, [categoryFilter, listData.categories])

  useEffect(() => {
    if (authorFilter !== 'all' && !listData.authors.includes(authorFilter)) {
      setAuthorFilter('all')
    }
  }, [authorFilter, listData.authors])

  const installedSkillIndex = useMemo(
    () => buildInstalledSkillIndex(skills),
    [skills]
  )

  const checkCatalogSkillInstalled = useCallback(
    (skill: AgentCatalogSkill) =>
      isCatalogSkillInstalled(skill, installedSkillIndex),
    [installedSkillIndex]
  )

  return {
    query,
    setQuery,
    categoryFilter,
    setCategoryFilter,
    authorFilter,
    setAuthorFilter,
    statusFilter,
    setStatusFilter,
    listData,
    checkCatalogSkillInstalled
  }
}
