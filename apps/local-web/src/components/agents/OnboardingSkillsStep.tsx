import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSkill,
  AgentSkillSource,
  McpCatalogEntry,
  McpServer
} from '@sandwalk/agent-ui-core'
import { Check, GitBranch, Loader2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { McpView } from '@/components/agents/McpView'
import {
  featuredSkillIcon,
  isFeaturedSkill,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import {
  suggestionSourceIcon,
  suggestionSourceLabel
} from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

const DEFAULT_SKILLS_REPO = 'fastfold-ai/skills'

/** Featured FastFold skills shown before install (matches catalog names). */
const FEATURED_SKILL_CATALOG: Array<{
  name: string
  description: string
  source: string
}> = [
  {
    name: 'fold',
    description: 'Protein structure prediction with FastFold Cloud jobs.',
    source: 'fastfold-ai/skills@skills/fold'
  },
  {
    name: 'boltz',
    description: 'Boltz structure prediction workflows.',
    source: 'fastfold-ai/skills@skills/boltz'
  },
  {
    name: 'protein_design_boltzgen',
    description: 'Protein design with BoltzGen.',
    source: 'fastfold-ai/skills@skills/protein_design_boltzgen'
  },
  {
    name: 'md_openmm_calvados',
    description: 'Molecular dynamics with OpenMM / CALVADOS.',
    source: 'fastfold-ai/skills@skills/md_openmm_calvados'
  },
  {
    name: 'md_openmmdl',
    description: 'MD analysis with OpenMMDL.',
    source: 'fastfold-ai/skills@skills/md_openmmdl'
  },
  {
    name: 'diagrams_mermaid',
    description: 'Diagrams and flowcharts with Mermaid.',
    source: 'fastfold-ai/skills@skills/diagrams_mermaid'
  },
  {
    name: 'slack_report',
    description: 'Share research updates to Slack.',
    source: 'fastfold-ai/skills@skills/slack_report'
  }
]

function SkillToggle({
  enabled,
  pending,
  label,
  onToggle
}: {
  enabled: boolean
  pending?: boolean
  label: string
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      disabled={pending}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        enabled
          ? 'bg-black/75 dark:bg-zinc-300/50'
          : 'bg-zinc-200 dark:bg-zinc-700',
        pending && 'cursor-not-allowed opacity-60'
      )}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        onToggle()
      }}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
          enabled ? 'translate-x-4' : 'translate-x-0.5'
        )}
      />
    </button>
  )
}

export function OnboardingSkillsStep({
  client
}: {
  client: LocalAgentClient
}) {
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

  // When featured skills are already installed, the selection toggles are hidden —
  // do not silently queue leftover default selections for install.
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

  if (loading && skills.length === 0 && suggestions.length === 0) {
    return (
      <p className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" />
        Loading skills…
      </p>
    )
  }

  return (
    <div className="space-y-5 pb-2">
      <section className="space-y-3">
        <p className="text-muted-foreground text-sm">Featured</p>

        {hasFeaturedInstalled ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {featuredInstalled.map(skill => {
              const iconSource = featuredSkillIcon(skill)
              return (
                <div
                  key={skill.name}
                  className={cn(
                    'bg-background/60 flex items-start justify-between gap-3 rounded-lg border p-3',
                    !skill.enabled && 'opacity-60'
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <img
                        src={iconSource}
                        alt=""
                        className={cn(
                          'size-7 rounded object-contain',
                          skillIconInvertInDark(skill) && 'dark:invert'
                        )}
                      />
                      <span className="truncate text-sm font-medium">
                        {skill.name}
                      </span>
                    </div>
                    {skill.description ? (
                      <p className="text-muted-foreground mt-1 line-clamp-2 text-xs">
                        {skill.description}
                      </p>
                    ) : null}
                  </div>
                  <SkillToggle
                    enabled={skill.enabled}
                    pending={pendingEnabled[skill.name]}
                    label={`${skill.enabled ? 'Disable' : 'Enable'} ${skill.name}`}
                    onToggle={() => void setEnabled(skill.name, !skill.enabled)}
                  />
                </div>
              )
            })}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {FEATURED_SKILL_CATALOG.map(item => {
              const on = Boolean(selected[item.name])
              const already = installedNames.has(item.name)
              const iconSource = featuredSkillIcon({
                name: item.name,
                iconSrc: null
              })
              return (
                <div
                  key={item.name}
                  className={cn(
                    'bg-background/60 flex items-start justify-between gap-3 rounded-lg border p-3',
                    !on && 'opacity-60'
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <img
                        src={iconSource}
                        alt=""
                        className={cn(
                          'size-7 rounded object-contain',
                          skillIconInvertInDark({
                            name: item.name,
                            iconSrc: null
                          }) && 'dark:invert'
                        )}
                      />
                      <span className="truncate text-sm font-medium">
                        {item.name}
                      </span>
                    </div>
                    <p className="text-muted-foreground mt-1 line-clamp-2 text-xs">
                      {item.description}
                    </p>
                    {already ? (
                      <p className="text-muted-foreground mt-1 text-[11px]">
                        Already installed
                      </p>
                    ) : null}
                  </div>
                  <SkillToggle
                    enabled={on}
                    label={`${on ? 'Exclude' : 'Include'} ${item.name}`}
                    onToggle={() =>
                      setSelected(prev => ({
                        ...prev,
                        [item.name]: !prev[item.name]
                      }))
                    }
                  />
                </div>
              )
            })}
          </div>
        )}
      </section>

      {suggestions.length > 0 ? (
        <section className="space-y-3">
          <div>
            <h3 className="text-sm font-semibold tracking-tight">
              Community Skills
            </h3>
            <p className="text-muted-foreground text-xs">
              Add any skills you love
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {suggestions.map(item => {
              const alreadyInstalled = installedSuggestionSources.has(
                item.source
              )
              const on =
                alreadyInstalled || Boolean(suggestionSelected[item.source])
              const icon = suggestionSourceIcon(item)
              const toggle = () => {
                if (alreadyInstalled || installBusy) return
                setSuggestionSelected(prev => ({
                  ...prev,
                  [item.source]: !prev[item.source]
                }))
              }
              return (
                <div
                  key={item.source}
                  className={cn(
                    'bg-background/60 flex items-start gap-3 rounded-lg border p-3',
                    on && !alreadyInstalled && 'border-foreground bg-muted/40',
                    alreadyInstalled && 'border-emerald-500/40 bg-emerald-500/5',
                    !on && 'opacity-60'
                  )}
                >
                  {icon ? (
                    <img
                      src={icon}
                      alt=""
                      className="mt-0.5 size-8 shrink-0 rounded object-contain"
                    />
                  ) : (
                    <span className="bg-muted/30 text-muted-foreground mt-0.5 grid size-8 shrink-0 place-items-center rounded">
                      <GitBranch className="size-4" />
                    </span>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">
                      {suggestionSourceLabel(item)}
                    </p>
                    <p className="text-muted-foreground mt-0.5 line-clamp-2 text-xs">
                      {item.description}
                    </p>
                    <span className="text-muted-foreground mt-1 block truncate font-mono text-[11px]">
                      {item.source}
                    </span>
                    {alreadyInstalled ? (
                      <p className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
                        <Check className="size-3" />
                        Installed
                      </p>
                    ) : null}
                  </div>
                  {alreadyInstalled ? (
                    <span
                      className="text-emerald-700 dark:text-emerald-300 mt-0.5 grid size-8 shrink-0 place-items-center"
                      title="Installed"
                    >
                      <Check className="size-4" />
                    </span>
                  ) : (
                    <SkillToggle
                      enabled={on}
                      pending={installBusy}
                      label={`${on ? 'Exclude' : 'Include'} ${suggestionSourceLabel(item)}`}
                      onToggle={toggle}
                    />
                  )}
                </div>
              )
            })}
          </div>
        </section>
      ) : null}

      {(!hasFeaturedInstalled || selectedSuggestions.length > 0) &&
      installCount > 0 ? (
        <div className="flex items-center justify-between gap-3">
          <p className="text-muted-foreground text-xs">
            {installCount} to install
          </p>
          <button
            type="button"
            disabled={installBusy}
            onClick={() => void installSelected()}
            className={cn(
              'bg-foreground text-background inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium transition-opacity',
              installBusy && 'opacity-60'
            )}
          >
            {installBusy ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Check className="size-4" />
            )}
            Install selected
          </button>
        </div>
      ) : null}

      {hasFeaturedInstalled && selectedSuggestions.length === 0 ? (
        <p className="text-muted-foreground text-xs">
          Later you can add more skills in your dashboard.
        </p>
      ) : null}

      {error ? <p className="text-destructive text-sm">{error}</p> : null}
      {notice ? <p className="text-muted-foreground text-sm">{notice}</p> : null}

      <McpView
        featuredOnly
        featuredLimit={null}
        featuredLabel="MCPs"
        mcpServers={mcpServers}
        catalog={mcpCatalog}
        catalogLoading={mcpLoading}
        onRefresh={refreshMcp}
        onConnectCatalog={async (catalogId, input) => {
          const result = await client.connectMcpCatalog(catalogId, input)
          await refreshMcp()
          return result
        }}
        onToggleCatalog={async (entry, enabled) => {
          await client.setMcpCatalogEnabled(entry.id, enabled)
          await refreshMcp()
        }}
        onCreateMcp={async () => {}}
        onDeleteMcp={async () => {}}
        onToggleCustom={async () => {}}
      />
    </div>
  )
}
