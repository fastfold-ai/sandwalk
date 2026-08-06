import type { AgentCatalogSkill, AgentSkill } from '@sandwalk/agent-ui-core'

import { FEATURED_SKILL_CATALOG } from '@/components/agents/onboarding/onboarding-skills-shared'
import { isFeaturedSkill } from '@/lib/skill-icons'
import { compareSkillsBySearchRank, skillMatchesSearch } from '@/lib/skill-search'
import {
  catalogSkillInstallSource,
  categorizeSkill,
  normalizeSkillMatchKey,
  skillAuthorLabel,
  splitSkillSourceSpec
} from '@/lib/skills-catalog'

export type FeaturedPendingSkill = {
  name: string
  description: string
  source: string
}

export function buildInstalledSkillIndex(skills: AgentSkill[]) {
  const index = new Map<string, Set<string>>()
  for (const skill of skills) {
    const nameKey = normalizeSkillMatchKey(skill.name)
    if (!nameKey) continue
    const sourceSpec = splitSkillSourceSpec(skill.source)
    const ownerRepo = sourceSpec?.ownerRepo.toLowerCase() || ''
    const repos = index.get(nameKey) || new Set<string>()
    repos.add(ownerRepo)
    index.set(nameKey, repos)
  }
  return index
}

export function isCatalogSkillInstalled(
  skill: AgentCatalogSkill,
  installedSkillIndex: Map<string, Set<string>>
) {
  const candidateKeys = [
    normalizeSkillMatchKey(skill.slug),
    normalizeSkillMatchKey(skill.name)
  ].filter(Boolean)
  if (candidateKeys.length === 0) return false
  const catalogSpec = splitSkillSourceSpec(catalogSkillInstallSource(skill))
  const catalogOwnerRepo = catalogSpec?.ownerRepo.toLowerCase() || ''
  return candidateKeys.some(key => {
    const installedRepos = installedSkillIndex.get(key)
    if (!installedRepos || installedRepos.size === 0) return false
    if (!catalogOwnerRepo) return true
    return installedRepos.has(catalogOwnerRepo) || installedRepos.has('')
  })
}

export function formatCatalogInstallCount(installs: number) {
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1
  }).format(installs)
}

export type SkillsListFilters = {
  query: string
  categoryFilter: string
  authorFilter: string
  statusFilter: 'all' | 'enabled' | 'disabled'
}

export function computeSkillsListData(skills: AgentSkill[], filters: SkillsListFilters) {
  const categories = Array.from(
    new Set(skills.map(skill => categorizeSkill(skill)))
  ).sort()
  const authors = Array.from(
    new Set(skills.map(skill => skillAuthorLabel(skill)))
  ).sort((a, b) => {
    if (a === 'Unknown') return 1
    if (b === 'Unknown') return -1
    return a.localeCompare(b)
  })
  const categoryCounts = skills.reduce<Record<string, number>>((result, skill) => {
    const category = categorizeSkill(skill)
    result[category] = (result[category] || 0) + 1
    return result
  }, {})
  const authorCounts = skills.reduce<Record<string, number>>((result, skill) => {
    const author = skillAuthorLabel(skill)
    result[author] = (result[author] || 0) + 1
    return result
  }, {})
  const installedNames = new Set(skills.map(skill => skill.name))
  const featuredPendingInstall = FEATURED_SKILL_CATALOG.filter(item => {
    if (installedNames.has(item.name)) return false
    // Not installed yet — only surface when browsing all/featured, not status slices.
    if (filters.statusFilter !== 'all') return false
    if (filters.authorFilter !== 'all') return false
    if (
      filters.categoryFilter !== 'all' &&
      filters.categoryFilter !== 'featured'
    ) {
      return false
    }
    const queryText = filters.query.trim().toLowerCase()
    if (!queryText) return true
    return (
      item.name.toLowerCase().includes(queryText) ||
      item.description.toLowerCase().includes(queryText)
    )
  })
  const featuredCount =
    skills.filter(skill => isFeaturedSkill(skill)).length +
    featuredPendingInstall.length
  const enabledCount = skills.filter(skill => skill.enabled).length
  const disabledCount = skills.length - enabledCount
  const visible = skills.filter(skill => {
    const queryText = filters.query.trim().toLowerCase()
    const category = categorizeSkill(skill)
    const matchesQuery = skillMatchesSearch(skill, queryText)
    const matchesCategory =
      filters.categoryFilter === 'all' ||
      (filters.categoryFilter === 'featured' && isFeaturedSkill(skill)) ||
      category === filters.categoryFilter
    const author = skillAuthorLabel(skill)
    const matchesAuthor =
      filters.authorFilter === 'all' || author === filters.authorFilter
    const matchesStatus =
      filters.statusFilter === 'all' ||
      (filters.statusFilter === 'enabled' && skill.enabled) ||
      (filters.statusFilter === 'disabled' && !skill.enabled)
    return matchesQuery && matchesCategory && matchesAuthor && matchesStatus
  })
  const orderedVisible = [...visible].sort((a, b) => {
    const queryText = filters.query.trim().toLowerCase()
    if (queryText) {
      const rankDiff = compareSkillsBySearchRank(a, b, queryText)
      if (rankDiff !== 0) return rankDiff
    }
    if (filters.categoryFilter !== 'featured') {
      const featuredDiff =
        Number(isFeaturedSkill(b)) - Number(isFeaturedSkill(a))
      if (featuredDiff !== 0) return featuredDiff
    }
    return a.name.localeCompare(b.name)
  })
  const featuredVisible = orderedVisible.filter(skill => isFeaturedSkill(skill))
  const nonFeaturedVisible = orderedVisible.filter(skill => !isFeaturedSkill(skill))
  const filteredSkillNames = orderedVisible.map(skill => skill.name)
  const disableEligibleCount = orderedVisible.filter(skill => skill.enabled).length
  const enableEligibleCount = orderedVisible.filter(skill => !skill.enabled).length
  const removeEligibleCount = filteredSkillNames.length

  return {
    categories,
    authors,
    categoryCounts,
    authorCounts,
    featuredCount,
    enabledCount,
    disabledCount,
    visible,
    orderedVisible,
    featuredVisible,
    featuredPendingInstall,
    nonFeaturedVisible,
    filteredSkillNames,
    disableEligibleCount,
    enableEligibleCount,
    removeEligibleCount
  }
}
