import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSkill,
  DatasetSummary,
  IntegrationUnlock,
  ToolSummary
} from '@sandwalk/agent-ui-core'
import { Loader, Wrench } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ToolsViewToolRow } from '@/components/agents/tools-view/tools-view-tool-row'
import {
  catalogSkillDetailPath,
  normalizeSkillMatchKey
} from '@/lib/skills-catalog'

import { CapabilityUnlockRow, SkillUnlockRow } from './integration-unlocks-rows'

function catalogPath(unlock: IntegrationUnlock) {
  const source = String(unlock.source || '').split('@')[0]
  return catalogSkillDetailPath({
    id: `${source}/${unlock.id}`,
    source,
    name: unlock.id
  })
}

export function IntegrationUnlocksSection({
  client,
  integrationKey,
  unlocks
}: {
  client: LocalAgentClient
  integrationKey: string
  unlocks: IntegrationUnlock[]
}) {
  const navigate = useNavigate()
  const [skills, setSkills] = useState<AgentSkill[]>([])
  const [tools, setTools] = useState<ToolSummary[]>([])
  const [datasets, setDatasets] = useState<DatasetSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pendingSkills, setPendingSkills] = useState<Record<string, boolean>>(
    {}
  )
  const [pendingTools, setPendingTools] = useState<Record<string, boolean>>({})
  const [pendingCapabilities, setPendingCapabilities] = useState<
    Record<string, boolean>
  >({})
  const [capabilities, setCapabilities] = useState<
    Record<string, IntegrationUnlock>
  >({})

  const hasSkills = unlocks.some(unlock => unlock.kind === 'skill')
  const hasTools = unlocks.some(unlock => unlock.kind === 'tool')

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const [nextSkills, nextTools, nextDatasets] = await Promise.all([
        hasSkills ? client.listSkills(signal) : Promise.resolve([]),
        hasTools
          ? client.listTools({ signal }).then(result => result.data)
          : Promise.resolve([]),
        hasTools
          ? client.listDatasets(signal).catch(() => [])
          : Promise.resolve([])
      ])
      if (signal?.aborted) return
      setSkills(nextSkills)
      setTools(nextTools)
      setDatasets(nextDatasets)
    },
    [client, hasSkills, hasTools]
  )

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    void load(controller.signal)
      .catch(cause => {
        if (!controller.signal.aborted)
          setError(cause instanceof Error ? cause.message : String(cause))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [load])

  useEffect(() => {
    setCapabilities({})
  }, [integrationKey])

  const skillsByName = useMemo(
    () =>
      new Map(
        skills.map(
          skill => [normalizeSkillMatchKey(skill.name), skill] as const
        )
      ),
    [skills]
  )
  const toolsById = useMemo(
    () => new Map(tools.map(tool => [tool.id, tool] as const)),
    [tools]
  )
  const datasetStatus = useMemo(
    () =>
      new Map(datasets.map(dataset => [dataset.id, dataset.status] as const)),
    [datasets]
  )
  const resolveRequirement = (token: string) => {
    const normalized = token.trim().toLowerCase()
    const prefix = normalized.split('_')[0]
    const datasetId = datasetStatus.has(normalized)
      ? normalized
      : datasetStatus.has(prefix)
      ? prefix
      : null
    if (!datasetId) return { datasetId: null, installed: null }
    const status = datasetStatus.get(datasetId)
    return {
      datasetId,
      installed: status === 'complete' || status === 'on-demand'
    }
  }

  const install = async (unlock: IntegrationUnlock) => {
    if (!unlock.source) return
    setPendingSkills(current => ({ ...current, [unlock.id]: true }))
    setError(null)
    try {
      const installed = await client.installSkill(unlock.source)
      const name = installed[0] || unlock.id
      await client.setSkillEnabled(name, true).catch(() => null)
      setSkills(await client.listSkills())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setPendingSkills(current => ({ ...current, [unlock.id]: false }))
    }
  }

  const enable = async (unlock: IntegrationUnlock, skill: AgentSkill) => {
    setPendingSkills(current => ({ ...current, [unlock.id]: true }))
    setError(null)
    try {
      const updated = await client.setSkillEnabled(skill.name, true)
      setSkills(current =>
        current.map(item =>
          item.name === updated.name ? { ...item, enabled: true } : item
        )
      )
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setPendingSkills(current => ({ ...current, [unlock.id]: false }))
    }
  }

  const toggleTool = async (tool: ToolSummary) => {
    setPendingTools(current => ({ ...current, [tool.id]: true }))
    setError(null)
    try {
      const updated = await client.updateToolEnabled(tool.id, !tool.enabled)
      setTools(current =>
        current.map(item => (item.id === updated.id ? updated : item))
      )
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setPendingTools(current => ({ ...current, [tool.id]: false }))
    }
  }

  const installCapability = async (unlock: IntegrationUnlock) => {
    setPendingCapabilities(current => ({ ...current, [unlock.id]: true }))
    setError(null)
    try {
      const provider = await client.installIntegrationCapability(
        integrationKey,
        unlock.id
      )
      const updated = provider.unlocks.find(item => item.id === unlock.id)
      if (updated)
        setCapabilities(current => ({ ...current, [unlock.id]: updated }))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setPendingCapabilities(current => ({ ...current, [unlock.id]: false }))
    }
  }

  if (unlocks.length === 0) return null

  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium">Unlocks</h3>
      {error ? (
        <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
          {error}
        </div>
      ) : null}
      <div className="bg-muted/20 border-border/60 divide-y overflow-hidden rounded-xl border">
        {loading && (hasSkills || hasTools) ? (
          <div className="text-muted-foreground flex items-center gap-2 px-4 py-4 text-sm">
            <Loader className="size-4 animate-spin" />
            Loading current status…
          </div>
        ) : (
          unlocks.map(unlock => {
            if (unlock.kind === 'skill') {
              const skill =
                skillsByName.get(normalizeSkillMatchKey(unlock.id)) || null
              return (
                <SkillUnlockRow
                  key={`${unlock.kind}:${unlock.id}`}
                  unlock={unlock}
                  skill={skill}
                  busy={Boolean(pendingSkills[unlock.id])}
                  onInstall={() => void install(unlock)}
                  onEnable={() => {
                    if (skill) void enable(unlock, skill)
                  }}
                  onOpen={() =>
                    navigate(
                      skill
                        ? `/dashboard/skills/${encodeURIComponent(skill.name)}`
                        : catalogPath(unlock)
                    )
                  }
                />
              )
            }
            if (unlock.kind === 'tool') {
              const tool = toolsById.get(unlock.id)
              if (tool) {
                return (
                  <ToolsViewToolRow
                    key={`${unlock.kind}:${unlock.id}`}
                    tool={tool}
                    pending={Boolean(pendingTools[tool.id])}
                    onOpenData={() => navigate('/dashboard/datasets')}
                    onToggle={() => void toggleTool(tool)}
                    resolveRequirement={resolveRequirement}
                  />
                )
              }
              return (
                <div
                  key={`${unlock.kind}:${unlock.id}`}
                  className="flex items-start gap-3 px-4 py-3"
                >
                  <Wrench className="text-muted-foreground mt-0.5 size-4" />
                  <div>
                    <span className="font-mono text-sm font-medium">
                      {unlock.id}
                    </span>
                    <p className="text-muted-foreground mt-1 text-sm">
                      {unlock.description}
                    </p>
                  </div>
                </div>
              )
            }
            const capability = capabilities[unlock.id] || unlock
            return (
              <CapabilityUnlockRow
                key={`${unlock.kind}:${unlock.id}`}
                unlock={capability}
                busy={Boolean(pendingCapabilities[unlock.id])}
                onInstall={() => void installCapability(capability)}
                onOpen={
                  capability.id === 'slack-relay-agent'
                    ? () => navigate('/dashboard/integrations/slack')
                    : undefined
                }
              />
            )
          })
        )}
      </div>
    </section>
  )
}
