import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSkill,
  AgentSkillSource,
  McpCatalogEntry,
  McpServer
} from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { isFeaturedSkill } from '@/lib/skill-icons'

import {
  DEFAULT_SKILLS_REPO,
  FEATURED_SKILL_CATALOG
} from './onboarding-skills-shared'

export function useOnboardingSkills(client: LocalAgentClient) {
  const [skills, setSkills] = useState<AgentSkill[]>([])
  const [suggestions, setSuggestions] = useState<AgentSkillSource[]>([])
  const [mcpCatalog, setMcpCatalog] = useState<McpCatalogEntry[]>([])
  const [mcpServers, setMcpServers] = useState<McpServer[]>([])
  const [mcpLoading, setMcpLoading] = useState(true)
  const [loading, setLoading] = useState(true)
  const [installBusy, setInstallBusy] = useState(false)
  const [pendingEnabled, setPendingEnabled] = useState<Record<string, boolean>>(
    {}
  )
  const [selected, setSelected] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(FEATURED_SKILL_CATALOG.map(item => [item.name, true]))
  )
  const [suggestionSelected, setSuggestionSelected] = useState<
    Record<string, boolean>
  >({})
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [nextSkills, nextSources] = await Promise.all([
        client.listSkills(),
        client.listSkillSources().catch(() => [] as AgentSkillSource[])
      ])
      setSkills(nextSkills)
      setSuggestions(nextSources)
      setSuggestionSelected(prev => {
        const next = { ...prev }
        for (const item of nextSources) {
          if (next[item.source] === undefined) next[item.source] = false
        }
        return next
      })
    } catch {
      // Keep step usable.
    } finally {
      setLoading(false)
    }
  }, [client])

  const refreshMcp = useCallback(async () => {
    setMcpLoading(true)
    try {
      const [catalog, servers] = await Promise.all([
        client.listMcpCatalog(),
        client.listMcpServers().catch(() => [] as McpServer[])
      ])
      setMcpCatalog(catalog)
      setMcpServers(servers)
    } catch {
      // Keep step usable.
    } finally {
      setMcpLoading(false)
    }
  }, [client])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    void refreshMcp()
  }, [refreshMcp])

  const featuredInstalled = useMemo(
    () => skills.filter(skill => isFeaturedSkill(skill)),
    [skills]
  )

  const installedNames = useMemo(
    () => new Set(skills.map(skill => skill.name)),
    [skills]
  )

  const installedSuggestionSources = useMemo(() => {
    const sources = new Set<string>()
    for (const skill of skills) {
      const raw = String(skill.source || '')
        .trim()
        .toLowerCase()
      if (!raw) continue
      for (const item of suggestions) {
        const needle = String(item.source || '')
          .trim()
          .toLowerCase()
        if (!needle) continue
        if (raw === needle || raw.includes(needle) || needle.includes(raw)) {
          sources.add(item.source)
        }
      }
    }
    return sources
  }, [skills, suggestions])

  const hasFeaturedInstalled = featuredInstalled.length > 0

  const selectedFeatured = hasFeaturedInstalled
    ? []
    : FEATURED_SKILL_CATALOG.filter(
        item => selected[item.name] && !installedNames.has(item.name)
      )
  const selectedSuggestions = suggestions.filter(
    item =>
      suggestionSelected[item.source] &&
      !installedSuggestionSources.has(item.source)
  )
  const installCount = selectedFeatured.length + selectedSuggestions.length

  const installSelected = async () => {
    if (!installCount) {
      setError('Select at least one skill or suggestion, or skip this step.')
      return
    }
    setInstallBusy(true)
    setError(null)
    setNotice(null)
    try {
      const installedNamesAcc: string[] = []
      let installedPacks = 0
      if (
        !hasFeaturedInstalled &&
        selectedFeatured.length === FEATURED_SKILL_CATALOG.length &&
        FEATURED_SKILL_CATALOG.every(item => selected[item.name])
      ) {
        const installed = await client.installSkill(DEFAULT_SKILLS_REPO)
        installedNamesAcc.push(...(installed || []))
        installedPacks += 1
      } else {
        for (const item of selectedFeatured) {
          const installed = await client.installSkill(item.source)
          installedNamesAcc.push(...(installed || []))
          installedPacks += 1
        }
      }
      for (const item of selectedSuggestions) {
        const installed = await client.installSkill(item.source)
        installedNamesAcc.push(...(installed || []))
        installedPacks += 1
      }
      await refresh()
      const unique = Array.from(new Set(installedNamesAcc.filter(Boolean)))
      setNotice(
        unique.length > 0
          ? `Installed ${unique.length} skill${unique.length === 1 ? '' : 's'} from ${installedPacks} source${installedPacks === 1 ? '' : 's'}.`
          : `Installed ${installedPacks} source${installedPacks === 1 ? '' : 's'}.`
      )
      setSuggestionSelected(prev => {
        const next = { ...prev }
        for (const item of selectedSuggestions) {
          next[item.source] = false
        }
        return next
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not install skills.')
    } finally {
      setInstallBusy(false)
    }
  }

  const setEnabled = async (name: string, enabled: boolean) => {
    setPendingEnabled(prev => ({ ...prev, [name]: true }))
    setError(null)
    try {
      await client.setSkillEnabled(name, enabled)
      setSkills(prev =>
        prev.map(skill =>
          skill.name === name ? { ...skill, enabled } : skill
        )
      )
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not update skill.'
      )
    } finally {
      setPendingEnabled(prev => {
        const next = { ...prev }
        delete next[name]
        return next
      })
    }
  }

  return {
    skills,
    suggestions,
    mcpCatalog,
    mcpServers,
    mcpLoading,
    loading,
    installBusy,
    pendingEnabled,
    selected,
    setSelected,
    suggestionSelected,
    setSuggestionSelected,
    error,
    notice,
    refreshMcp,
    featuredInstalled,
    installedNames,
    installedSuggestionSources,
    hasFeaturedInstalled,
    selectedSuggestions,
    installCount,
    installSelected,
    setEnabled
  }
}
