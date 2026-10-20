import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentModel,
  AgentProject,
  AgentSession,
  CookbookSummary,
  GraphNode,
  GraphSnapshot,
  MemoryEntry,
  MemoryOverview,
  MemorySettings,
  PendingMemoryWrite,
  Specialist,
  WikiPageDetail,
  WikiPageSummary
} from '@sandwalk/agent-ui-core'
import {
  AlertTriangle,
  BookOpen,
  Brain,
  Check,
  Database,
  Download,
  GitBranch,
  GitMerge,
  Layers,
  Network,
  Plus,
  RefreshCw,
  Settings2,
  Sparkles,
  Trash2,
  X
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { SpecialistAvatar } from '@/components/agents/specialists-view/specialist-ui'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

type MemoryTab = 'graph' | 'cookbooks' | 'wiki' | 'memories' | 'settings'
type GraphVisualMode = 'blueprint' | 'instances'

const NODE_COLOR_MAP: Record<string, string> = {
  blue: '#2563eb',
  teal: '#0d9488',
  indigo: '#4f46e5',
  amber: '#d97706',
  violet: '#7c3aed',
  green: '#16a34a',
  pink: '#db2777',
  orange: '#ea580c',
  red: '#dc2626',
  gray: '#52525b'
}

export function MemoryView({
  client,
  projects,
  specialists,
  sessions,
  activeProjectId
}: {
  client: LocalAgentClient
  projects: AgentProject[]
  specialists: Specialist[]
  sessions: AgentSession[]
  activeProjectId: string | null
}) {
  const location = useLocation()
  const navigate = useNavigate()
  const searchParams = useMemo(
    () => new URLSearchParams(location.search),
    [location.search]
  )

  const initialScope =
    searchParams.get('scope') ||
    (activeProjectId ? `project:${activeProjectId}` : 'global')
  const initialTab = (searchParams.get('tab') as MemoryTab) || 'graph'

  const [scope, setScope] = useState<string>(initialScope)
  const [activeTab, setActiveTab] = useState<MemoryTab>(initialTab)
  const [visualMode, setVisualMode] = useState<GraphVisualMode>('blueprint')
  const [branch, setBranch] = useState<string>('main')
  const [activeQueryName, setActiveQueryName] = useState<string | null>(null)
  const [selectedNodeTypeFilter, setSelectedNodeTypeFilter] = useState<
    string | null
  >(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

  const [overview, setOverview] = useState<MemoryOverview | null>(null)
  const [graph, setGraph] = useState<GraphSnapshot | null>(null)
  const [cookbooks, setCookbooks] = useState<CookbookSummary[]>([])
  const [inspectCookbook, setInspectCookbook] =
    useState<CookbookSummary | null>(null)

  const [memories, setMemories] = useState<MemoryEntry[]>([])
  const [pendingWrites, setPendingWrites] = useState<PendingMemoryWrite[]>([])
  const [wikiPages, setWikiPages] = useState<WikiPageSummary[]>([])
  const [activeWikiPage, setActiveWikiPage] = useState<WikiPageDetail | null>(
    null
  )
  const [models, setModels] = useState<AgentModel[]>([])
  const [settingsDraft, setSettingsDraft] = useState<MemorySettings | null>(
    null
  )
  const [busy, setBusy] = useState(false)

  // Form states
  const [newMemoryContent, setNewMemoryContent] = useState('')
  const [newMemoryTarget, setNewMemoryTarget] = useState<'memory' | 'user'>(
    'memory'
  )
  const [wikiTitle, setWikiTitle] = useState('')
  const [wikiSlug, setWikiSlug] = useState('')
  const [wikiContent, setWikiContent] = useState('')
  const [newBranchName, setNewBranchName] = useState('')
  const [newNodeType, setNewNodeType] = useState('Entity')
  const [newNodeName, setNewNodeName] = useState('')
  const [newNodeSummary, setNewNodeSummary] = useState('')
  const [distillSessionId, setDistillSessionId] = useState('')

  useEffect(() => {
    const qScope = searchParams.get('scope')
    if (qScope) setScope(qScope)
    const qTab = searchParams.get('tab') as MemoryTab | null
    if (qTab) setActiveTab(qTab)
  }, [searchParams])

  const loadAll = useCallback(async () => {
    try {
      const [ov, gr, cb, mems, pend, wiki] = await Promise.all([
        client.getMemoryOverview(scope),
        client.getMemoryGraph({
          scope,
          branch,
          queryName: activeQueryName
        }),
        client.listCookbooks(scope),
        client.listMemoryEntries(scope, true),
        client.listPendingMemoryWrites(scope),
        client.listWikiPages(scope)
      ])
      setOverview(ov)
      setSettingsDraft(ov.settings)
      setGraph(gr)
      setCookbooks(cb.data)
      setMemories(mems.data)
      setPendingWrites(pend)
      setWikiPages(wiki)
      if (gr.activeCookbook.nodeTypes.length > 0) {
        setNewNodeType(gr.activeCookbook.nodeTypes[0].name)
      }
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Failed to load memory workspace'
      )
    }
  }, [client, scope, branch, activeQueryName])

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  useEffect(() => {
    client
      .listModels({ discover: false })
      .then(items => setModels(items.filter(m => m.enabled)))
      .catch(() => setModels([]))
  }, [client])

  const activeSpecialist = useMemo(() => {
    if (!scope.startsWith('specialist:')) return null
    const idOrSlug = scope.split(':', 2)[1]
    return (
      specialists.find(s => s.id === idOrSlug || s.slug === idOrSlug) ?? null
    )
  }, [scope, specialists])

  const filteredGraphNodes = useMemo(() => {
    if (!graph) return []
    let list = graph.nodes
    if (selectedNodeTypeFilter) {
      list = list.filter(n => n.nodeType === selectedNodeTypeFilter)
    }
    if (activeQueryName && graph.matchedNodeIds.length > 0) {
      const set = new Set(graph.matchedNodeIds)
      list = list.filter(n => set.has(n.id))
    }
    return list
  }, [graph, selectedNodeTypeFilter, activeQueryName])

  const positionedGraph = useMemo(() => {
    const nodes = filteredGraphNodes
    const edges = graph?.edges ?? []
    if (!graph || nodes.length === 0) {
      return { nodes: [], edges: [], width: 860, height: 420 }
    }
    const layers = graph.activeCookbook.layers
    const layerIndexByType: Record<string, number> = {}
    layers.forEach((l, idx) => {
      l.nodeTypes.forEach(nt => {
        layerIndexByType[nt] = idx
      })
    })
    const buckets: Record<number, GraphNode[]> = { 0: [], 1: [], 2: [] }
    nodes.forEach(n => {
      const idx = layerIndexByType[n.nodeType] ?? 1
      buckets[idx] = buckets[idx] || []
      buckets[idx].push(n)
    })

    const width = 900
    const height = Math.max(
      420,
      Math.max(buckets[0].length, buckets[1].length, buckets[2].length) * 86 +
        80
    )
    const coords: Record<
      string,
      { x: number; y: number; node: GraphNode; color: string }
    > = {}
    const colorByType = Object.fromEntries(
      graph.activeCookbook.nodeTypes.map(nt => [
        nt.name,
        NODE_COLOR_MAP[nt.color] || '#2563eb'
      ])
    )

    ;[0, 1, 2].forEach(colIdx => {
      const colNodes = buckets[colIdx] || []
      const x = 150 + colIdx * 300
      colNodes.forEach((n, rowIdx) => {
        const y =
          (height / (colNodes.length + 1)) * (rowIdx + 1)
        coords[n.id] = {
          x,
          y,
          node: n,
          color: colorByType[n.nodeType] || '#2563eb'
        }
      })
    })

    const visibleEdges = edges.filter(
      e => coords[e.sourceId] && coords[e.targetId]
    )
    return {
      nodes: Object.values(coords),
      edges: visibleEdges.map(e => ({
        edge: e,
        source: coords[e.sourceId],
        target: coords[e.targetId]
      })),
      width,
      height
    }
  }, [graph, filteredGraphNodes])

  const handleSelectCookbook = async (
    cookbookId: string,
    loadDemoSeed: boolean
  ) => {
    setBusy(true)
    try {
      const snap = await client.selectCookbook({
        scope,
        cookbookId,
        loadDemoSeed
      })
      setGraph(snap)
      setSelectedNodeTypeFilter(null)
      setActiveQueryName(null)
      if (loadDemoSeed) {
        setVisualMode('instances')
      }
      await loadAll()
      toast.success(
        loadDemoSeed
          ? `Loaded ${snap.activeCookbook.name} with starter graph seed`
          : `Switched ontology to ${snap.activeCookbook.name}`
      )
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Could not switch cookbook'
      )
    } finally {
      setBusy(false)
    }
  }

  const handleAddMemory = async () => {
    if (!newMemoryContent.trim()) return
    try {
      await client.createMemoryEntry({
        scope: newMemoryTarget === 'user' ? 'user' : scope,
        target: newMemoryTarget,
        layer: 'L1',
        content: newMemoryContent.trim()
      })
      setNewMemoryContent('')
      await loadAll()
      toast.success('Memory saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save memory')
    }
  }

  const handleOpenWikiPage = async (slug: string) => {
    try {
      const detail = await client.getWikiPage(slug, scope)
      setActiveWikiPage(detail)
      setWikiSlug(detail.slug)
      setWikiTitle(detail.title)
      setWikiContent(detail.content)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not open page')
    }
  }

  const handleSaveWikiPage = async () => {
    const slug = (wikiSlug || wikiTitle).trim()
    if (!slug || !wikiTitle.trim()) return
    try {
      const saved = await client.writeWikiPage(slug, {
        scope,
        title: wikiTitle.trim(),
        content: wikiContent
      })
      setActiveWikiPage(saved)
      await loadAll()
      toast.success(`Saved wiki page [[${saved.slug}]]`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save wiki')
    }
  }

  const handleAddGraphNode = async () => {
    if (!newNodeName.trim()) return
    try {
      await client.upsertGraphNode({
        scope,
        branch,
        nodeType: newNodeType,
        name: newNodeName.trim(),
        summary: newNodeSummary.trim()
      })
      setNewNodeName('')
      setNewNodeSummary('')
      await loadAll()
      toast.success(`Added ${newNodeType} node`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add node')
    }
  }

  const handleBranchAction = async (
    action: 'create' | 'merge' | 'delete',
    targetName: string
  ) => {
    if (!targetName.trim()) return
    try {
      await client.manageGraphBranch({
        scope,
        action,
        name: targetName.trim(),
        targetBranch: 'main'
      })
      if (action === 'create') {
        setBranch(targetName.trim())
        setNewBranchName('')
      } else {
        setBranch('main')
      }
      await loadAll()
      toast.success(`Branch ${action}: ${targetName}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Branch action failed')
    }
  }

  const handleDistillSession = async () => {
    if (!distillSessionId) return
    setBusy(true)
    try {
      const res = await client.distillSession(distillSessionId, {
        scope,
        includeWiki: true,
        includeGraph: true
      })
      await loadAll()
      toast.success(res.summary)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Distillation failed')
    } finally {
      setBusy(false)
    }
  }

  const handleSaveSettings = async () => {
    if (!settingsDraft) return
    setBusy(true)
    try {
      const next = await client.updateMemorySettings(settingsDraft)
      setSettingsDraft(next)
      await loadAll()
      toast.success('Memory & Omnigraph settings saved')
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Could not save settings'
      )
    } finally {
      setBusy(false)
    }
  }

  const handleInstallOmnigraph = async () => {
    setBusy(true)
    try {
      const status = await client.installOmnigraph()
      await loadAll()
      if (status.installed) {
        toast.success('Omnigraph installed and MCP enabled')
      } else {
        toast.error(status.detail || 'Omnigraph install failed')
      }
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Omnigraph install failed'
      )
    } finally {
      setBusy(false)
    }
  }

  const cb = graph?.activeCookbook

  return (
    <div className="chat-scrollbar flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-5 pt-6 pb-10 md:px-8 md:pt-8">
        {/* Top Header + Scope Selector + Distill Session Bar */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            {activeSpecialist ? (
              <SpecialistAvatar
                color={activeSpecialist.color}
                icon={activeSpecialist.icon}
                avatarUrl={activeSpecialist.avatarUrl}
                slug={activeSpecialist.slug}
                size="md"
              />
            ) : (
              <span className="bg-primary/10 text-primary flex size-11 items-center justify-center rounded-2xl">
                <Brain className="size-5" />
              </span>
            )}
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-2xl font-semibold tracking-tight">
                  {activeSpecialist
                    ? `${activeSpecialist.name}’s Brain`
                    : 'Memory & Knowledge'}
                </h2>
                {cb ? (
                  <span className="bg-muted text-muted-foreground rounded-full px-2.5 py-0.5 text-xs font-medium">
                    {cb.number} {cb.name}
                  </span>
                ) : null}
              </div>
              <p className="text-muted-foreground mt-0.5 text-sm">
                {activeSpecialist
                  ? activeSpecialist.priors ||
                    activeSpecialist.description ||
                    'Persona priors, learned memories, and ontology lens.'
                  : 'Curated session-start snapshots, Living Markdown Wiki, and Omnigraph Cookbook ontologies.'}
              </p>
            </div>
          </div>

          {/* Scope Picker + Session Distiller */}
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={scope}
              onChange={e => {
                setScope(e.target.value)
                setBranch('main')
                setSelectedNode(null)
              }}
              aria-label="Knowledge scope"
              className="border-border/60 bg-muted/25 h-9 rounded-xl border px-3 text-xs font-medium"
            >
              <option value="global">Global Brain (Personal & Lab)</option>
              {projects.length > 0 && (
                <optgroup label="Projects">
                  {projects.map(p => (
                    <option key={p.id} value={`project:${p.id}`}>
                      Project: {p.name}
                    </option>
                  ))}
                </optgroup>
              )}
              {specialists.length > 0 && (
                <optgroup label="Agent Personas / Specialists">
                  {specialists.map(s => (
                    <option key={s.id} value={`specialist:${s.id}`}>
                      Persona: {s.name} ({s.roleLabel || s.slug})
                    </option>
                  ))}
                </optgroup>
              )}
            </select>

            <div className="flex items-center gap-1">
              <select
                value={distillSessionId}
                onChange={e => setDistillSessionId(e.target.value)}
                className="border-border/60 bg-muted/25 h-9 max-w-[210px] rounded-xl border px-2.5 text-xs"
              >
                <option value="">Distill a chat session…</option>
                {sessions.slice(0, 25).map(s => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={!distillSessionId || busy}
                onClick={() => void handleDistillSession()}
                className="h-9 gap-1.5 rounded-xl text-xs"
              >
                <Sparkles className="size-3.5" />
                Distill
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={async () => {
                  setBusy(true)
                  try {
                    await client.seedMemoryDemo(true)
                    await loadAll()
                  } finally {
                    setBusy(false)
                  }
                }}
                className="h-9 gap-1.5 rounded-xl text-xs"
                title="Populate realistic Memories, Living Wiki pages, Omnigraph branches/claims, and multi-turn Otium & Soren example chats"
              >
                <RefreshCw className="size-3.5" />
                Load Demo
              </Button>
            </div>
          </div>
        </div>

        {/* Summary Strip */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <div className="border-border/50 bg-muted/20 rounded-2xl border p-3.5">
            <div className="text-muted-foreground text-[11px]">
              MEMORY.md Snapshot
            </div>
            <div className="mt-1 text-base font-semibold">
              {overview?.charUsed ?? 0}{' '}
              <span className="text-muted-foreground text-xs font-normal">
                / {overview?.charLimit ?? 2200} chars
              </span>
            </div>
          </div>
          <div className="border-border/50 bg-muted/20 rounded-2xl border p-3.5">
            <div className="text-muted-foreground text-[11px]">
              USER.md Profile
            </div>
            <div className="mt-1 text-base font-semibold">
              {overview?.userCharUsed ?? 0}{' '}
              <span className="text-muted-foreground text-xs font-normal">
                / {overview?.userCharLimit ?? 1375} chars
              </span>
            </div>
          </div>
          <div className="border-border/50 bg-muted/20 rounded-2xl border p-3.5">
            <div className="text-muted-foreground text-[11px]">
              Living Wiki Pages
            </div>
            <div className="mt-1 text-base font-semibold">
              {wikiPages.length}
            </div>
          </div>
          <div className="border-border/50 bg-muted/20 rounded-2xl border p-3.5">
            <div className="text-muted-foreground text-[11px]">
              Graph Nodes & Edges
            </div>
            <div className="mt-1 text-base font-semibold">
              {graph?.nodes.length ?? 0} nodes · {graph?.edges.length ?? 0}{' '}
              edges
            </div>
          </div>
          <div className="border-border/50 bg-muted/20 rounded-2xl border p-3.5">
            <div className="text-muted-foreground text-[11px]">
              Contested Claims
            </div>
            <div className="mt-1 flex items-center gap-1.5 text-base font-semibold">
              {(graph?.contradictionCount ?? 0) > 0 ? (
                <AlertTriangle className="size-4 text-amber-500" />
              ) : null}
              {graph?.contradictionCount ?? 0}
            </div>
          </div>
        </div>

        {/* Navigation Pills */}
        <div className="border-border/60 flex flex-wrap items-center justify-between gap-2 border-b pb-3">
          <div className="flex flex-wrap items-center gap-1.5">
            {(
              [
                {
                  id: 'graph',
                  label: 'Ontology & Graph Explorer',
                  icon: Network
                },
                {
                  id: 'cookbooks',
                  label: 'Cookbook Modes (01–06)',
                  icon: Layers
                },
                {
                  id: 'wiki',
                  label: `Living Wiki (${wikiPages.length})`,
                  icon: BookOpen
                },
                {
                  id: 'memories',
                  label: `Memories & Approvals (${memories.length}${pendingWrites.length ? ` · ${pendingWrites.length} pending` : ''})`,
                  icon: Database
                },
                {
                  id: 'settings',
                  label: 'Models, Control & Omnigraph',
                  icon: Settings2
                }
              ] as const
            ).map(tab => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors',
                    activeTab === tab.id
                      ? 'bg-foreground text-background'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  <Icon className="size-3.5" />
                  {tab.label}
                </button>
              )
            })}
          </div>

          {activeSpecialist ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 text-xs"
              onClick={() => navigate('/dashboard/specialists')}
            >
              Back to Agents
            </Button>
          ) : null}
        </div>

        {/* TAB 1: ONTOLOGY & GRAPH EXPLORER */}
        {activeTab === 'graph' && cb && (
          <div className="space-y-4">
            {/* Toolbar: Visual Mode Toggle + Stored Queries + Branch Bar */}
            <div className="border-border/60 bg-muted/20 flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-3">
              <div className="flex flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setVisualMode('blueprint')}
                  className={cn(
                    'rounded-xl px-3 py-1.5 text-xs font-medium transition-colors',
                    visualMode === 'blueprint'
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  Level 1 · Ontology Blueprint
                </button>
                <button
                  type="button"
                  onClick={() => setVisualMode('instances')}
                  className={cn(
                    'rounded-xl px-3 py-1.5 text-xs font-medium transition-colors',
                    visualMode === 'instances'
                      ? 'bg-background text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  Level 2 · Instance Graph ({graph?.nodes.length ?? 0})
                </button>

                <span className="text-muted-foreground mx-1 text-xs">|</span>
                <span className="text-muted-foreground text-xs font-medium">
                  Stored Queries:
                </span>
                {cb.storedQueries.map(sq => {
                  const active = activeQueryName === sq.name
                  return (
                    <button
                      key={sq.name}
                      type="button"
                      title={sq.description}
                      onClick={() => {
                        setActiveQueryName(active ? null : sq.name)
                        setVisualMode('instances')
                      }}
                      className={cn(
                        'rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors',
                        active
                          ? 'border-primary bg-primary/15 text-primary'
                          : 'border-border/60 bg-background/60 text-muted-foreground hover:text-foreground'
                      )}
                    >
                      {sq.label}
                    </button>
                  )
                })}
                {(selectedNodeTypeFilter || activeQueryName) && (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedNodeTypeFilter(null)
                      setActiveQueryName(null)
                    }}
                    className="text-muted-foreground hover:text-foreground text-[11px] underline"
                  >
                    Clear filter
                  </button>
                )}
              </div>

              {/* Branch Switcher + Seed Quick Button */}
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-1">
                  <GitBranch className="text-muted-foreground size-3.5" />
                  <select
                    value={branch}
                    onChange={e => setBranch(e.target.value)}
                    className="border-border/60 bg-background h-8 rounded-lg border px-2 text-xs"
                  >
                    {(graph?.branches ?? []).map(b => (
                      <option key={b.name} value={b.name}>
                        {b.name} ({b.nodeCount})
                      </option>
                    ))}
                  </select>
                </div>
                {branch !== 'main' && (
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    className="h-8 gap-1 rounded-lg text-xs"
                    onClick={() => void handleBranchAction('merge', branch)}
                  >
                    <GitMerge className="size-3.5" />
                    Merge into main
                  </Button>
                )}
                {graph && graph.nodes.length === 0 && (
                  <Button
                    type="button"
                    size="sm"
                    className="h-8 rounded-lg text-xs"
                    disabled={busy}
                    onClick={() => void handleSelectCookbook(cb.id, true)}
                  >
                    Load {cb.name} Demo Seed
                  </Button>
                )}
              </div>
            </div>

            {/* LEVEL 1: ONTOLOGY BLUEPRINT VIEW (Layered Swimlanes) */}
            {visualMode === 'blueprint' && (
              <div className="space-y-4">
                {cb.layers.map(layer => {
                  const layerTypes = cb.nodeTypes.filter(
                    nt => nt.layer === layer.id
                  )
                  return (
                    <div
                      key={layer.id}
                      className="border-border/60 bg-muted/15 rounded-2xl border p-4"
                    >
                      <div className="mb-3 flex items-baseline justify-between">
                        <div>
                          <h3 className="text-sm font-semibold">
                            {layer.label}
                          </h3>
                          <p className="text-muted-foreground text-xs">
                            {layer.description}
                          </p>
                        </div>
                      </div>
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        {layerTypes.map(nt => {
                          const outgoing = cb.edgeTypes.filter(
                            et => et.sourceType === nt.name
                          )
                          return (
                            <button
                              key={nt.name}
                              type="button"
                              onClick={() => {
                                setSelectedNodeTypeFilter(nt.name)
                                setVisualMode('instances')
                              }}
                              className="border-border/60 bg-background/80 hover:border-foreground/40 flex flex-col justify-between rounded-xl border p-3.5 text-left transition-all"
                            >
                              <div>
                                <div className="flex items-center justify-between gap-2">
                                  <span className="flex items-center gap-2 text-sm font-semibold">
                                    <span
                                      className="size-2.5 rounded-full"
                                      style={{
                                        backgroundColor:
                                          NODE_COLOR_MAP[nt.color] || '#2563eb'
                                      }}
                                    />
                                    {nt.name}
                                  </span>
                                  <span className="bg-muted text-muted-foreground rounded-full px-2 py-0.5 font-mono text-[11px]">
                                    {nt.count}
                                  </span>
                                </div>
                                <p className="text-muted-foreground mt-1 line-clamp-2 text-xs">
                                  {nt.description}
                                </p>
                                <div className="mt-2.5 flex flex-wrap gap-1">
                                  {nt.properties.map(p => (
                                    <span
                                      key={p.name}
                                      className="bg-muted/60 text-muted-foreground rounded px-1.5 py-0.5 font-mono text-[10px]"
                                    >
                                      {p.name}
                                      {p.isKey
                                        ? ' @key'
                                        : p.isIndexed
                                          ? ' @index'
                                          : ''}
                                    </span>
                                  ))}
                                </div>
                              </div>

                              {outgoing.length > 0 && (
                                <div className="border-border/50 mt-3 border-t pt-2">
                                  {outgoing.map(edge => (
                                    <div
                                      key={`${edge.predicate}-${edge.targetType}`}
                                      className="flex items-center justify-between text-[11px]"
                                    >
                                      <span
                                        className={cn(
                                          'font-mono',
                                          edge.polarity === 'contradict'
                                            ? 'text-red-500'
                                            : edge.polarity === 'support'
                                              ? 'text-emerald-500'
                                              : 'text-muted-foreground'
                                        )}
                                      >
                                        → {edge.predicate}
                                      </span>
                                      <span className="text-muted-foreground">
                                        {edge.targetType} ({edge.count})
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {/* LEVEL 2: INSTANCE KNOWLEDGE WEB (Interactive SVG + Inspector) */}
            {visualMode === 'instances' && (
              <div className="flex flex-col gap-4 lg:flex-row">
                <div className="border-border/60 bg-muted/10 min-w-0 flex-1 overflow-x-auto rounded-2xl border p-3">
                  {positionedGraph.nodes.length === 0 ? (
                    <div className="flex min-h-[340px] flex-col items-center justify-center gap-3 text-center">
                      <p className="text-muted-foreground text-sm">
                        No graph nodes in this view yet.
                      </p>
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => void handleSelectCookbook(cb.id, true)}
                      >
                        Load {cb.name} Starter Graph Seed
                      </Button>
                    </div>
                  ) : (
                    <svg
                      width={positionedGraph.width}
                      height={positionedGraph.height}
                      viewBox={`0 0 ${positionedGraph.width} ${positionedGraph.height}`}
                      className="mx-auto block select-none"
                    >
                      {positionedGraph.edges.map(({ edge, source, target }) => {
                        const isContradict = edge.polarity === 'contradict'
                        const isSupport = edge.polarity === 'support'
                        const stroke = isContradict
                          ? '#ef4444'
                          : isSupport
                            ? '#10b981'
                            : '#71717a'
                        const midX = (source.x + target.x) / 2
                        const midY = (source.y + target.y) / 2
                        return (
                          <g key={edge.id}>
                            <path
                              d={`M ${source.x} ${source.y} C ${midX} ${source.y}, ${midX} ${target.y}, ${target.x} ${target.y}`}
                              fill="none"
                              stroke={stroke}
                              strokeWidth={2}
                              strokeDasharray={isContradict ? '6 4' : undefined}
                              opacity={0.85}
                            />
                            <text
                              x={midX}
                              y={midY - 6}
                              textAnchor="middle"
                              fill={stroke}
                              fontSize={10}
                              fontWeight={600}
                            >
                              {edge.predicate}
                            </text>
                          </g>
                        )
                      })}

                      {positionedGraph.nodes.map(({ x, y, node, color }) => {
                        const isSelected = selectedNode?.id === node.id
                        return (
                          <g
                            key={node.id}
                            transform={`translate(${x - 105}, ${y - 26})`}
                            onClick={() => setSelectedNode(node)}
                            className="cursor-pointer"
                          >
                            <rect
                              width={210}
                              height={52}
                              rx={12}
                              fill="#18181b"
                              stroke={isSelected ? '#ffffff' : color}
                              strokeWidth={isSelected ? 2.5 : 1.5}
                            />
                            <circle cx={16} cy={18} r={4.5} fill={color} />
                            <text
                              x={26}
                              y={21}
                              fill="#a1a1aa"
                              fontSize={10}
                              fontWeight={600}
                            >
                              {node.nodeType}
                            </text>
                            <text
                              x={14}
                              y={38}
                              fill="#f4f4f5"
                              fontSize={11}
                              fontWeight={500}
                            >
                              {node.name.length > 26
                                ? `${node.name.slice(0, 26)}…`
                                : node.name}
                            </text>
                          </g>
                        )
                      })}
                    </svg>
                  )}
                </div>

                {/* Right-side Node Inspector / Quick Add */}
                <div className="border-border/60 bg-muted/15 w-full shrink-0 space-y-4 rounded-2xl border p-4 lg:w-80">
                  {selectedNode ? (
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <span className="text-muted-foreground font-mono text-[11px]">
                            {selectedNode.id}
                          </span>
                          <h4 className="text-sm font-semibold">
                            {selectedNode.name}
                          </h4>
                        </div>
                        <button
                          type="button"
                          onClick={() => setSelectedNode(null)}
                          className="text-muted-foreground hover:text-foreground"
                        >
                          <X className="size-4" />
                        </button>
                      </div>
                      <p className="text-muted-foreground text-xs leading-relaxed">
                        {selectedNode.summary || 'No summary recorded.'}
                      </p>
                      {selectedNode.sourceRef && (
                        <div className="text-muted-foreground font-mono text-[11px]">
                          Source: {selectedNode.sourceRef}
                        </div>
                      )}
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        className="h-7 w-full text-xs"
                        onClick={() => {
                          void client
                            .deleteGraphNode(selectedNode.id, scope, branch)
                            .then(() => {
                              setSelectedNode(null)
                              return loadAll()
                            })
                        }}
                      >
                        Delete Node
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      <h4 className="text-xs font-semibold">
                        Add Node to {cb.name}
                      </h4>
                      <select
                        value={newNodeType}
                        onChange={e => setNewNodeType(e.target.value)}
                        className="border-border/60 bg-background h-8 w-full rounded-lg border px-2 text-xs"
                      >
                        {cb.nodeTypes.map(nt => (
                          <option key={nt.name} value={nt.name}>
                            {nt.name}
                          </option>
                        ))}
                      </select>
                      <Input
                        value={newNodeName}
                        onChange={e => setNewNodeName(e.target.value)}
                        placeholder="Node name or statement..."
                        className="h-8 text-xs"
                      />
                      <Input
                        value={newNodeSummary}
                        onChange={e => setNewNodeSummary(e.target.value)}
                        placeholder="Summary / evidence note..."
                        className="h-8 text-xs"
                      />
                      <Button
                        type="button"
                        size="sm"
                        className="h-8 w-full rounded-lg text-xs"
                        onClick={() => void handleAddGraphNode()}
                      >
                        <Plus className="mr-1 size-3.5" />
                        Add to {branch}
                      </Button>

                      <div className="border-border/50 border-t pt-3">
                        <div className="text-muted-foreground mb-1.5 text-[11px] font-medium">
                          Create Hypothesis Branch
                        </div>
                        <div className="flex gap-1.5">
                          <Input
                            value={newBranchName}
                            onChange={e => setNewBranchName(e.target.value)}
                            placeholder="review/hypothesis-1"
                            className="h-8 text-xs"
                          />
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="h-8 shrink-0 text-xs"
                            onClick={() =>
                              void handleBranchAction('create', newBranchName)
                            }
                          >
                            Branch
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: COOKBOOK MODES STUDIO (Matches omnigraph.dev screenshot) */}
        {activeTab === 'cookbooks' && (
          <div className="space-y-5">
            <div>
              <div className="text-muted-foreground font-mono text-[11px] uppercase tracking-wider">
                [COOKBOOKS]
              </div>
              <h3 className="mt-1 text-xl font-semibold">
                Start from a working graph
              </h3>
              <p className="text-muted-foreground mt-1 max-w-2xl text-sm">
                Cookbooks are runnable Omnigraph projects: schema, stored
                queries, seed data, and agent skills in one bundle. Apply one to
                this scope or load its starter seed to explore immediately.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {cookbooks.map(item => {
                const isActive = cb?.id === item.id
                return (
                  <div
                    key={item.id}
                    className={cn(
                      'flex flex-col justify-between rounded-2xl border p-5 transition-all',
                      isActive
                        ? 'border-foreground/40 bg-muted/35 ring-foreground/15 ring-1'
                        : 'border-border/60 bg-muted/15 hover:bg-muted/25'
                    )}
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground font-mono text-xs">
                          {item.number}
                        </span>
                        {isActive && (
                          <span className="bg-foreground text-background rounded-full px-2.5 py-0.5 text-[10px] font-medium">
                            Active Mode
                          </span>
                        )}
                      </div>
                      <h4 className="mt-2 text-base font-semibold">
                        {item.name}
                      </h4>
                      <p className="text-muted-foreground mt-1.5 text-xs leading-relaxed">
                        {item.tagline}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-1">
                        {item.nodeTypes.map(nt => (
                          <span
                            key={nt.name}
                            className="border-border/50 bg-muted/35 rounded-md border px-1.5 py-0.5 font-mono text-[10px]"
                          >
                            {nt.name}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="mt-5 flex flex-wrap items-center gap-2 pt-2">
                      <Button
                        type="button"
                        size="sm"
                        variant={isActive ? 'secondary' : 'default'}
                        className="h-8 rounded-lg text-xs"
                        disabled={busy}
                        onClick={() => void handleSelectCookbook(item.id, false)}
                      >
                        {isActive ? 'Active' : 'Use Mode'}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="h-8 rounded-lg text-xs"
                        disabled={busy}
                        onClick={() => {
                          void handleSelectCookbook(item.id, true).then(() =>
                            setActiveTab('graph')
                          )
                        }}
                      >
                        Load Demo Seed
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-8 rounded-lg text-xs"
                        onClick={() => setInspectCookbook(item)}
                      >
                        Schema (.pg)
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>

            {inspectCookbook && (
              <div className="border-border/60 bg-muted/20 space-y-3 rounded-2xl border p-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold">
                    {inspectCookbook.number} {inspectCookbook.name} — Schema
                    (.pg) & Stored Queries (.gq)
                  </h4>
                  <button
                    type="button"
                    onClick={() => setInspectCookbook(null)}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <X className="size-4" />
                  </button>
                </div>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <pre className="border-border/50 bg-background max-h-72 overflow-auto rounded-xl border p-3 font-mono text-[11px]">
                    {inspectCookbook.pgSchema}
                  </pre>
                  <pre className="border-border/50 bg-background max-h-72 overflow-auto rounded-xl border p-3 font-mono text-[11px]">
                    {inspectCookbook.storedQueries
                      .map(q => `// ${q.description}\n${q.gqSource}`)
                      .join('\n\n')}
                  </pre>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: LIVING MARKDOWN WIKI */}
        {activeTab === 'wiki' && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="border-border/60 bg-muted/15 space-y-2 rounded-2xl border p-3.5">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold">
                  Wiki Pages ({wikiPages.length})
                </h4>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={() => {
                    setActiveWikiPage(null)
                    setWikiSlug('')
                    setWikiTitle('')
                    setWikiContent('')
                  }}
                >
                  <Plus className="mr-1 size-3" />
                  New Page
                </Button>
              </div>
              {wikiPages.length === 0 ? (
                <p className="text-muted-foreground py-8 text-center text-xs">
                  No Wiki pages in {scope} yet.
                </p>
              ) : (
                <div className="space-y-1">
                  {wikiPages.map(page => (
                    <button
                      key={page.slug}
                      type="button"
                      onClick={() => void handleOpenWikiPage(page.slug)}
                      className={cn(
                        'w-full rounded-xl p-2.5 text-left transition-colors',
                        activeWikiPage?.slug === page.slug
                          ? 'bg-background shadow-sm'
                          : 'hover:bg-background/60'
                      )}
                    >
                      <div className="text-xs font-semibold">{page.title}</div>
                      <div className="text-muted-foreground font-mono text-[10px]">
                        [[{page.slug}]]
                      </div>
                      <p className="text-muted-foreground mt-1 line-clamp-2 text-[11px]">
                        {page.summary}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="border-border/60 bg-muted/15 space-y-3 rounded-2xl border p-4 md:col-span-2">
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  value={wikiTitle}
                  onChange={e => setWikiTitle(e.target.value)}
                  placeholder="Page Title (e.g. KRAS G12D Target Dossier)"
                  className="h-9 flex-1 text-sm"
                />
                <Input
                  value={wikiSlug}
                  onChange={e => setWikiSlug(e.target.value)}
                  placeholder="slug-optional"
                  className="h-9 w-44 font-mono text-xs"
                />
                <Button
                  type="button"
                  size="sm"
                  className="h-9 rounded-xl px-4 text-xs"
                  onClick={() => void handleSaveWikiPage()}
                >
                  Save Page
                </Button>
              </div>
              <textarea
                value={wikiContent}
                onChange={e => setWikiContent(e.target.value)}
                rows={14}
                placeholder="Write Markdown notes here. Link to other pages with [[page-slug]]..."
                className="border-border/60 bg-background w-full rounded-xl border p-3 font-mono text-xs leading-relaxed outline-none"
              />
              {activeWikiPage && activeWikiPage.backlinks.length > 0 && (
                <div className="flex items-center gap-1.5 text-xs">
                  <span className="text-muted-foreground">Backlinks:</span>
                  {activeWikiPage.backlinks.map(bl => (
                    <button
                      key={bl}
                      type="button"
                      onClick={() => void handleOpenWikiPage(bl)}
                      className="bg-muted rounded px-2 py-0.5 font-mono text-[11px]"
                    >
                      [[{bl}]]
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: MEMORIES & PENDING APPROVALS */}
        {activeTab === 'memories' && (
          <div className="space-y-4">
            {pendingWrites.length > 0 && (
              <div className="border-amber-500/40 bg-amber-500/10 space-y-2 rounded-2xl border p-4">
                <div className="text-xs font-semibold">
                  Pending Write Approvals ({pendingWrites.length})
                </div>
                {pendingWrites.map(pw => (
                  <div
                    key={pw.id}
                    className="bg-background/80 flex items-center justify-between gap-3 rounded-xl p-2.5 text-xs"
                  >
                    <span>{pw.summary}</span>
                    <div className="flex items-center gap-1.5">
                      <Button
                        type="button"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => {
                          void client
                            .approvePendingMemoryWrite(pw.id)
                            .then(() => loadAll())
                        }}
                      >
                        <Check className="mr-1 size-3" />
                        Approve
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => {
                          void client
                            .rejectPendingMemoryWrite(pw.id)
                            .then(() => loadAll())
                        }}
                      >
                        Reject
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="border-border/60 bg-muted/15 flex flex-wrap items-center gap-2 rounded-2xl border p-3">
              <select
                value={newMemoryTarget}
                onChange={e =>
                  setNewMemoryTarget(e.target.value as 'memory' | 'user')
                }
                className="border-border/60 bg-background h-9 rounded-xl border px-2.5 text-xs"
              >
                <option value="memory">MEMORY.md ({scope})</option>
                <option value="user">USER.md (User Profile)</option>
              </select>
              <Input
                value={newMemoryContent}
                onChange={e => setNewMemoryContent(e.target.value)}
                placeholder="Add a compact, high-signal memory entry or rule..."
                className="h-9 flex-1 text-xs"
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    void handleAddMemory()
                  }
                }}
              />
              <Button
                type="button"
                size="sm"
                className="h-9 rounded-xl px-4 text-xs"
                onClick={() => void handleAddMemory()}
              >
                Add Entry
              </Button>
            </div>

            <div className="space-y-2">
              {memories.map(entry => (
                <div
                  key={entry.id}
                  className="border-border/60 bg-muted/15 flex items-start justify-between gap-3 rounded-2xl border p-3.5"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="bg-background border-border/60 rounded-full border px-2 py-0.5 font-mono text-[10px]">
                        {entry.scope === 'user' ? 'USER.md' : entry.scope}
                      </span>
                      <span className="text-muted-foreground text-[11px]">
                        {entry.content.length} chars
                      </span>
                    </div>
                    <p className="mt-1.5 text-sm leading-relaxed">
                      {entry.content}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      void client
                        .deleteMemoryEntry(entry.id)
                        .then(() => loadAll())
                    }}
                    className="text-muted-foreground hover:text-destructive p-1"
                    title="Delete entry"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 5: MODELS, CONTROL & 1-CLICK OMNIGRAPH ENGINE */}
        {activeTab === 'settings' && settingsDraft && overview && (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {/* 1-Click Local Omnigraph Engine Card */}
            <div className="border-border/60 bg-muted/20 flex flex-col justify-between rounded-2xl border p-5">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-semibold">
                      Local Omnigraph Engine
                    </h3>
                    <p className="text-muted-foreground text-xs">
                      Self-hosted Rust + Lance graph engine & auto-enabled MCP
                    </p>
                  </div>
                  <span
                    className={cn(
                      'rounded-full px-2.5 py-0.5 text-xs font-medium',
                      overview.omnigraph.installed
                        ? 'bg-emerald-500/15 text-emerald-500'
                        : 'bg-muted text-muted-foreground'
                    )}
                  >
                    {overview.omnigraph.installed
                      ? overview.omnigraph.version || 'Installed'
                      : 'Built-in SQLite Fallback Active'}
                  </span>
                </div>

                <div className="border-border/50 bg-muted/30 space-y-1.5 rounded-xl border p-3 font-mono text-[11px]">
                  <div>
                    Binary:{' '}
                    {overview.omnigraph.binaryPath ||
                      '~/.sandwalk/bin/omnigraph (1-click install)'}
                  </div>
                  <div>Store: {overview.omnigraph.storePath}</div>
                  <div>
                    MCP Auto-Enabled:{' '}
                    {overview.omnigraph.mcpEnabled ? 'Yes' : 'Ready on install'}
                  </div>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  disabled={busy}
                  onClick={() => void handleInstallOmnigraph()}
                  className="h-9 gap-1.5 rounded-xl text-xs"
                >
                  <Download className="size-3.5" />
                  {overview.omnigraph.installed
                    ? 'Update Omnigraph Binary'
                    : '1-Click Install Omnigraph'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={busy}
                  onClick={() => {
                    void client
                      .syncOmnigraph(scope, branch)
                      .then(() =>
                        toast.success('Synced schema.pg, queries.gq & data')
                      )
                  }}
                  className="h-9 gap-1.5 rounded-xl text-xs"
                >
                  <RefreshCw className="size-3.5" />
                  Sync .omni Bundle
                </Button>
              </div>
            </div>

            {/* Unified Pre-Configured Models & Governance */}
            <div className="border-border/60 bg-muted/20 space-y-4 rounded-2xl border p-5">
              <div>
                <h3 className="text-base font-semibold">
                  Models & User Control
                </h3>
                <p className="text-muted-foreground text-xs">
                  Uses your pre-configured Cloud, OpenRouter, and Local
                  llama.cpp models from Dashboard → Models.
                </p>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-muted-foreground text-xs font-medium">
                    Knowledge Distillation & Curation Model
                  </label>
                  <select
                    value={
                      settingsDraft.distillerModel === 'auto'
                        ? 'auto'
                        : `${settingsDraft.distillerProvider}::${settingsDraft.distillerModel}`
                    }
                    onChange={e => {
                      const val = e.target.value
                      if (val === 'auto') {
                        setSettingsDraft({
                          ...settingsDraft,
                          distillerProvider: 'auto',
                          distillerModel: 'auto'
                        })
                      } else {
                        const [prov, mod] = val.split('::', 2)
                        setSettingsDraft({
                          ...settingsDraft,
                          distillerProvider: prov,
                          distillerModel: mod
                        })
                      }
                    }}
                    className="border-border/60 bg-background mt-1 h-9 w-full rounded-xl border px-3 text-xs"
                  >
                    <option value="auto">
                      Auto (Reuse active chat model — warm prompt cache)
                    </option>
                    {models.map(m => (
                      <option
                        key={`${m.provider}-${m.id}-${m.profileId || ''}`}
                        value={`${m.provider}::${m.id}`}
                      >
                        [{m.provider}] {m.label || m.id}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-muted-foreground text-xs font-medium">
                    Omnigraph Vector Embedding Provider
                  </label>
                  <select
                    value={settingsDraft.embeddingsProvider}
                    onChange={e =>
                      setSettingsDraft({
                        ...settingsDraft,
                        embeddingsProvider: e.target
                          .value as MemorySettings['embeddingsProvider']
                      })
                    }
                    className="border-border/60 bg-background mt-1 h-9 w-full rounded-xl border px-3 text-xs"
                  >
                    <option value="none">
                      BM25 + Graph Traversal Only (Zero embedding cost)
                    </option>
                    <option value="openrouter">
                      OpenRouter (uses configured OpenRouter API key)
                    </option>
                    <option value="openai">
                      OpenAI (uses configured OpenAI API key)
                    </option>
                    <option value="gemini">
                      Google Gemini (uses configured Gemini API key)
                    </option>
                    <option value="local_llama">
                      Local llama.cpp (:9931 on-device embeddings)
                    </option>
                  </select>
                </div>

                <label className="flex items-center justify-between gap-2 text-xs">
                  <span>
                    Require my approval before agents write to Memory
                    (write_approval)
                  </span>
                  <input
                    type="checkbox"
                    checked={settingsDraft.writeApproval}
                    onChange={e =>
                      setSettingsDraft({
                        ...settingsDraft,
                        writeApproval: e.target.checked
                      })
                    }
                  />
                </label>

                <label className="flex items-center justify-between gap-2 text-xs">
                  <span>
                    Isolate agent graph writes on a review/* branch first
                  </span>
                  <input
                    type="checkbox"
                    checked={settingsDraft.graphBranchOnWrite}
                    onChange={e =>
                      setSettingsDraft({
                        ...settingsDraft,
                        graphBranchOnWrite: e.target.checked
                      })
                    }
                  />
                </label>

                <label className="flex items-center justify-between gap-2 text-xs">
                  <span>
                    Defer background distillation while local llama.cpp GPU is
                    busy
                  </span>
                  <input
                    type="checkbox"
                    checked={settingsDraft.distillerDeferOnLocalGpu}
                    onChange={e =>
                      setSettingsDraft({
                        ...settingsDraft,
                        distillerDeferOnLocalGpu: e.target.checked
                      })
                    }
                  />
                </label>

                <div className="flex justify-end pt-2">
                  <Button
                    type="button"
                    size="sm"
                    disabled={busy}
                    onClick={() => void handleSaveSettings()}
                    className="h-9 rounded-xl px-4 text-xs"
                  >
                    Save Control Settings
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
