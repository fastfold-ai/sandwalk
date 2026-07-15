import type {
  AgentSkill,
  McpCatalogEntry,
  McpServer,
  Specialist,
  ToolCatalog,
  ToolSummary
} from '@sandwalk/agent-ui-core'
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  ChevronDown,
  Plug,
  Search,
  Sparkles,
  Trash2,
  X
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import {
  SPECIALIST_COLORS,
  SPECIALIST_ICONS,
  SpecialistAvatar
} from '@/components/agents/specialists-view/specialist-ui'
import {
  McpGlyph,
  SkillGlyph,
  SpecialistToggle,
  mcpMetaText,
  skillMetaText
} from '@/components/agents/specialists-view/specialists-view-shared'
import {
  emptySpecialistForm,
  resolveSkillInstallSource,
  slugify,
  specialistFieldClassName,
  specialistFormFromRecord,
  type SpecialistCapabilityIssue,
  type SpecialistFormState
} from '@/components/agents/specialists-view/specialists-view-utils'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

export function SpecialistsEditorView({
  mode,
  specialistId,
  specialists,
  skills,
  mcpServers,
  mcpCatalog = [],
  loading,
  onRefresh,
  onCreate,
  onUpdate,
  onDelete,
  onOpenEdit,
  onBack,
  onManageSkills,
  onManageMcps,
  onOpenSkill,
  onOpenMcp,
  onEnableSkill,
  onInstallSkill,
  onListTools
}: {
  mode: 'new' | 'edit'
  specialistId: string | null
  specialists: Specialist[]
  skills: AgentSkill[]
  mcpServers: McpServer[]
  mcpCatalog?: McpCatalogEntry[]
  loading?: boolean
  onRefresh: () => Promise<void>
  onCreate: (input: {
    name: string
    slug?: string | null
    description?: string | null
    instructions?: string | null
    color?: string
    icon?: string
    skillNames?: string[]
    toolNames?: string[]
    mcpServerIds?: string[]
    mcpCatalogIds?: string[]
    enabled?: boolean
  }) => Promise<Specialist>
  onUpdate: (
    id: string,
    input: {
      name?: string
      slug?: string | null
      description?: string | null
      instructions?: string | null
      color?: string
      icon?: string
      skillNames?: string[]
      toolNames?: string[]
      mcpServerIds?: string[]
      mcpCatalogIds?: string[]
      enabled?: boolean
    }
  ) => Promise<Specialist>
  onDelete: (id: string) => Promise<void>
  onOpenEdit: (id: string) => void
  onBack: () => void
  onManageSkills?: () => void
  onManageMcps?: () => void
  onOpenSkill?: (name: string) => void
  onOpenMcp?: (target: {
    kind: 'server' | 'catalog'
    id: string
  }) => void
  onEnableSkill?: (name: string) => Promise<void>
  onInstallSkill?: (source: string) => Promise<void>
  onListTools?: (signal?: AbortSignal) => Promise<ToolCatalog>
}) {
  const editing = useMemo(
    () =>
      mode === 'edit'
        ? specialists.find(item => item.id === specialistId) || null
        : null,
    [mode, specialistId, specialists]
  )
  const [form, setForm] = useState<SpecialistFormState>(emptySpecialistForm)
  const [slugTouched, setSlugTouched] = useState(false)
  const [skillAddQuery, setSkillAddQuery] = useState('')
  const [mcpAddQuery, setMcpAddQuery] = useState('')
  const [skillAddOpen, setSkillAddOpen] = useState(false)
  const [mcpAddOpen, setMcpAddOpen] = useState(false)
  const [appearanceOpen, setAppearanceOpen] = useState(false)
  const [iconQuery, setIconQuery] = useState('')
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [skillActionPending, setSkillActionPending] = useState<string | null>(
    null
  )
  const [togglePendingId, setTogglePendingId] = useState<string | null>(null)
  const [catalogTools, setCatalogTools] = useState<ToolSummary[]>([])
  const [toolsLoading, setToolsLoading] = useState(false)
  const [toolQuery, setToolQuery] = useState('')

  useEffect(() => {
    if (!onListTools) return
    const controller = new AbortController()
    setToolsLoading(true)
    void onListTools(controller.signal)
      .then(catalog => {
        if (!controller.signal.aborted) setCatalogTools(catalog.data || [])
      })
      .catch(() => {
        if (!controller.signal.aborted) setCatalogTools([])
      })
      .finally(() => {
        if (!controller.signal.aborted) setToolsLoading(false)
      })
    return () => controller.abort()
  }, [onListTools])

  useEffect(() => {
    if (mode === 'new') {
      setForm(emptySpecialistForm())
      setSlugTouched(false)
      setSkillAddQuery('')
      setMcpAddQuery('')
      setIconQuery('')
      setToolQuery('')
      return
    }
    if (mode === 'edit' && editing) {
      setForm(specialistFormFromRecord(editing))
      setSlugTouched(true)
      setSkillAddQuery('')
      setMcpAddQuery('')
      setIconQuery('')
      setToolQuery('')
    }
  }, [editing, mode])

  useEffect(() => {
    if (mode !== 'new' || catalogTools.length === 0) return
    setForm(current => {
      if (current.toolNames.length > 0) return current
      return {
        ...current,
        toolNames: catalogTools
          .filter(tool => tool.tier === 'core')
          .map(tool => tool.id)
          .sort()
      }
    })
  }, [mode, catalogTools])

  const availableSkills = useMemo(() => {
    const selected = new Set(form.skillNames)
    const needle = skillAddQuery.trim().toLowerCase()
    return skills.filter(skill => {
      if (selected.has(skill.name)) return false
      if (!needle) return true
      return `${skill.name} ${skill.description || ''}`
        .toLowerCase()
        .includes(needle)
    })
  }, [form.skillNames, skillAddQuery, skills])

  const filteredIcons = useMemo(() => {
    const needle = iconQuery.trim().toLowerCase()
    if (!needle) return SPECIALIST_ICONS
    return SPECIALIST_ICONS.filter(entry =>
      `${entry.label} ${entry.id}`.toLowerCase().includes(needle)
    )
  }, [iconQuery])

  const availableMcps = useMemo(() => {
    const selected = new Set(form.mcpServerIds)
    const needle = mcpAddQuery.trim().toLowerCase()
    return mcpServers.filter(server => {
      if (selected.has(server.id)) return false
      if (!needle) return true
      return `${server.name} ${server.id}`.toLowerCase().includes(needle)
    })
  }, [form.mcpServerIds, mcpAddQuery, mcpServers])

  const selectedSkillRows = useMemo(() => {
    return form.skillNames.map(name => {
      const skill = skills.find(item => item.name === name) || null
      let status: 'ok' | 'missing' | 'disabled' = 'ok'
      let statusLabel: string | null = null
      if (!skill) {
        status = 'missing'
        statusLabel = 'Not installed'
      } else if (!skill.enabled) {
        status = 'disabled'
        statusLabel = 'Disabled'
      }
      return { name, skill, status, statusLabel }
    })
  }, [form.skillNames, skills])

  const selectedMcpRows = useMemo(() => {
    const rows: Array<{
      key: string
      kind: 'server' | 'catalog'
      name: string
      server: McpServer | null
      catalog: McpCatalogEntry | null
      status: 'ok' | 'missing' | 'disabled' | 'disconnected'
      statusLabel: string | null
    }> = []

    for (const id of form.mcpServerIds) {
      const server = mcpServers.find(item => item.id === id) || null
      let status: 'ok' | 'missing' | 'disabled' | 'disconnected' = 'ok'
      let statusLabel: string | null = null
      if (!server) {
        status = 'missing'
        statusLabel = 'Missing server'
      } else if (!server.enabled) {
        status = 'disabled'
        statusLabel = 'Disabled'
      }
      rows.push({
        key: `server:${id}`,
        kind: 'server',
        name: server?.name || id,
        server,
        catalog: null,
        status,
        statusLabel
      })
    }

    for (const catalogId of form.mcpCatalogIds) {
      const catalog =
        mcpCatalog.find(item => item.id === catalogId) || null
      const server =
        mcpServers.find(item => item.catalogId === catalogId) || null
      let status: 'ok' | 'missing' | 'disabled' | 'disconnected' = 'ok'
      let statusLabel: string | null = null
      if (!server) {
        status = 'disconnected'
        statusLabel = 'Not connected'
      } else if (!server.enabled) {
        status = 'disabled'
        statusLabel = 'Disabled'
      }
      rows.push({
        key: `catalog:${catalogId}`,
        kind: 'catalog',
        name: catalog?.name || server?.name || catalogId,
        server,
        catalog,
        status,
        statusLabel
      })
    }

    return rows
  }, [form.mcpCatalogIds, form.mcpServerIds, mcpCatalog, mcpServers])

  const capabilityIssues = useMemo(() => {
    const issues: SpecialistCapabilityIssue[] = []
    for (const row of selectedSkillRows) {
      if (row.status === 'ok' || !row.statusLabel) continue
      issues.push({ kind: 'skill', name: row.name, detail: row.statusLabel })
    }
    for (const row of selectedMcpRows) {
      if (row.status === 'ok' || !row.statusLabel) continue
      issues.push({ kind: 'mcp', name: row.name, detail: row.statusLabel })
    }
    return issues
  }, [selectedMcpRows, selectedSkillRows])

  const filteredCatalogTools = useMemo(() => {
    const needle = toolQuery.trim().toLowerCase()
    if (!needle) return catalogTools
    return catalogTools.filter(tool =>
      `${tool.id} ${tool.name} ${tool.description} ${tool.category}`
        .toLowerCase()
        .includes(needle)
    )
  }, [catalogTools, toolQuery])

  const coreTools = useMemo(
    () => filteredCatalogTools.filter(tool => tool.tier === 'core'),
    [filteredCatalogTools]
  )
  const extraTools = useMemo(
    () => filteredCatalogTools.filter(tool => tool.tier !== 'core'),
    [filteredCatalogTools]
  )

  const toggleTool = (toolId: string) => {
    setForm(current => {
      const selected = new Set(current.toolNames)
      if (selected.has(toolId)) selected.delete(toolId)
      else selected.add(toolId)
      return {
        ...current,
        toolNames: Array.from(selected).sort()
      }
    })
  }

  const setTierTools = (tools: ToolSummary[], enabled: boolean) => {
    setForm(current => {
      const selected = new Set(current.toolNames)
      for (const tool of tools) {
        if (enabled) selected.add(tool.id)
        else selected.delete(tool.id)
      }
      return {
        ...current,
        toolNames: Array.from(selected).sort()
      }
    })
  }

  const addSkill = (name: string) => {
    setForm(current => ({
      ...current,
      skillNames: Array.from(new Set([...current.skillNames, name])).sort()
    }))
    setSkillAddQuery('')
    setSkillAddOpen(false)
  }

  const removeSkill = (name: string) => {
    setForm(current => ({
      ...current,
      skillNames: current.skillNames.filter(item => item !== name)
    }))
  }

  const addMcp = (id: string) => {
    setForm(current => ({
      ...current,
      mcpServerIds: Array.from(new Set([...current.mcpServerIds, id])).sort()
    }))
    setMcpAddQuery('')
    setMcpAddOpen(false)
  }

  const removeMcp = (id: string) => {
    setForm(current => ({
      ...current,
      mcpServerIds: current.mcpServerIds.filter(item => item !== id)
    }))
  }

  const removeMcpCatalog = (catalogId: string) => {
    setForm(current => ({
      ...current,
      mcpCatalogIds: current.mcpCatalogIds.filter(item => item !== catalogId)
    }))
  }

  const save = async () => {
    const name = form.name.trim()
    if (!name) {
      toast.error('Name is required')
      return
    }
    setSaving(true)
    try {
      const payload = {
        name,
        slug: form.slug.trim() || undefined,
        description: form.description.trim() || null,
        instructions: form.instructions.trim() || null,
        color: form.color,
        icon: form.icon,
        skillNames: form.skillNames,
        toolNames: form.toolNames,
        mcpServerIds: form.mcpServerIds,
        mcpCatalogIds: form.mcpCatalogIds,
        enabled: form.enabled
      }
      if (mode === 'edit' && specialistId) {
        await onUpdate(specialistId, payload)
        await onRefresh()
        toast.success('Specialist saved')
      } else {
        const created = await onCreate(payload)
        await onRefresh()
        toast.success('Specialist created')
        onOpenEdit(created.id)
      }
    } catch (cause) {
      toast.error(
        cause instanceof Error ? cause.message : 'Unable to save specialist'
      )
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!specialistId) return
    if (
      !window.confirm(
        'Delete this specialist? Sessions using it will clear the selection.'
      )
    ) {
      return
    }
    setDeleting(true)
    try {
      await onDelete(specialistId)
      toast.success('Specialist deleted')
      await onRefresh()
      onBack()
    } catch (cause) {
      toast.error(
        cause instanceof Error ? cause.message : 'Unable to delete specialist'
      )
    } finally {
      setDeleting(false)
    }
  }

  const toggleSpecialistEnabled = async (
    id: string,
    nextEnabled: boolean
  ) => {
    setTogglePendingId(id)
    try {
      await onUpdate(id, { enabled: nextEnabled })
      await onRefresh()
    } catch (cause) {
      toast.error(
        cause instanceof Error
          ? cause.message
          : 'Unable to update specialist'
      )
    } finally {
      setTogglePendingId(null)
    }
  }

  const handleEnableSkill = async (name: string) => {
    if (!onEnableSkill) return
    setSkillActionPending(name)
    try {
      await onEnableSkill(name)
      toast.success(`Enabled ${name}`)
    } catch (cause) {
      toast.error(
        cause instanceof Error ? cause.message : `Unable to enable ${name}`
      )
    } finally {
      setSkillActionPending(null)
    }
  }

  const handleInstallSkill = async (name: string) => {
    const source = resolveSkillInstallSource(name)
    if (!source || !onInstallSkill) {
      onManageSkills?.()
      toast.message(`Open Skills to install “${name}”.`)
      return
    }
    setSkillActionPending(name)
    try {
      await onInstallSkill(source)
      toast.success(`Installed ${name}`)
    } catch (cause) {
      toast.error(
        cause instanceof Error
          ? cause.message
          : `Unable to install ${name}. Try Skills → Find.`
      )
    } finally {
      setSkillActionPending(null)
    }
  }

  if (mode === 'edit' && !editing && !loading) {
    return (
      <div className="chat-scrollbar flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-8 py-10">
          <p className="text-sm">Specialist not found.</p>
          <div>
            <Button type="button" variant="ghost" size="sm" onClick={onBack}>
              Back to specialists
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="chat-scrollbar min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-6 py-8 md:px-10">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm">
              <button
                type="button"
                onClick={onBack}
                className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </button>
              <span className="text-muted-foreground/40">/</span>
              <button
                type="button"
                onClick={onBack}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                Specialists
              </button>
            </div>
            {mode === 'edit' || mode === 'new' ? (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground text-xs">
                    {form.enabled ? 'On' : 'Off'}
                  </span>
                  <SpecialistToggle
                    enabled={form.enabled}
                    pending={
                      mode === 'edit' &&
                      Boolean(specialistId) &&
                      togglePendingId === specialistId
                    }
                    label={
                      form.enabled
                        ? 'Disable specialist'
                        : 'Enable specialist'
                    }
                    onToggle={() => {
                      if (mode !== 'edit' || !specialistId) {
                        setForm(current => ({
                          ...current,
                          enabled: !current.enabled
                        }))
                        return
                      }
                      const next = !form.enabled
                      setForm(current => ({ ...current, enabled: next }))
                      void toggleSpecialistEnabled(specialistId, next)
                    }}
                  />
                </div>
                {mode === 'edit' ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs text-red-600 hover:text-red-700"
                    disabled={deleting || saving}
                    onClick={() => void remove()}
                  >
                    <Trash2 className="mr-1 size-3.5" />
                    Delete
                  </Button>
                ) : null}
              </div>
            ) : null}
          </div>

          {capabilityIssues.length > 0 ? (
            <div className="border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200 flex gap-3 rounded-xl border px-3.5 py-3 text-sm">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              <div className="min-w-0 space-y-1">
                <p className="font-medium text-amber-900 dark:text-amber-100">
                  Some required capabilities aren’t ready
                </p>
                <p className="text-amber-800/80 dark:text-amber-200/80 text-xs">
                  You can still use this specialist. Missing or disabled skills
                  and MCPs won’t be available until you install, connect, or
                  enable them.
                </p>
                <ul className="text-amber-800/90 dark:text-amber-200/90 mt-1 space-y-0.5 text-xs">
                  {capabilityIssues.map(issue => (
                    <li key={`${issue.kind}:${issue.name}`}>
                      {issue.kind === 'skill' ? 'Skill' : 'MCP'}{' '}
                      <span className="font-medium">{issue.name}</span> —{' '}
                      {issue.detail}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}

          <section className="space-y-3">
            <div className="bg-muted/30 flex items-center gap-3 rounded-2xl px-4 py-3.5">
              <DropdownMenu
                open={appearanceOpen}
                onOpenChange={open => {
                  setAppearanceOpen(open)
                  if (!open) setIconQuery('')
                }}
              >
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    className="group relative shrink-0 rounded-xl outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    aria-label="Choose color and icon"
                  >
                    <SpecialistAvatar color={form.color} icon={form.icon} />
                    <span className="bg-background/90 text-muted-foreground absolute -bottom-1 -right-1 flex size-4 items-center justify-center rounded-full border shadow-sm">
                      <ChevronDown className="size-2.5" />
                    </span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="start"
                  className="w-64 p-0"
                  onCloseAutoFocus={event => event.preventDefault()}
                >
                  <div className="space-y-2 p-2">
                    <p className="text-muted-foreground px-1 text-[11px] font-medium uppercase tracking-wide">
                      Color
                    </p>
                    <div className="flex flex-wrap gap-1.5 px-1">
                      {SPECIALIST_COLORS.map(color => (
                        <button
                          key={color.id}
                          type="button"
                          title={color.label}
                          className={cn(
                            'size-6 rounded-full transition-transform hover:scale-110',
                            color.swatch,
                            form.color === color.id &&
                              'ring-foreground/80 ring-2 ring-offset-2 ring-offset-popover'
                          )}
                          onClick={() =>
                            setForm(current => ({
                              ...current,
                              color: color.id
                            }))
                          }
                        />
                      ))}
                    </div>
                  </div>
                  <div className="border-t px-2 pt-2">
                    <p className="text-muted-foreground px-1 pb-1.5 text-[11px] font-medium uppercase tracking-wide">
                      Icon
                    </p>
                    <div className="relative mb-1.5">
                      <Search className="text-muted-foreground/70 pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2" />
                      <Input
                        value={iconQuery}
                        onChange={event => setIconQuery(event.target.value)}
                        placeholder="Search icons"
                        className="h-8 border-0 bg-transparent pl-7 shadow-none focus-visible:ring-0"
                        autoFocus
                      />
                    </div>
                  </div>
                  <div className="chat-scrollbar max-h-56 overflow-y-auto py-1">
                    {filteredIcons.length === 0 ? (
                      <p className="text-muted-foreground px-3 py-3 text-xs">
                        No icons match.
                      </p>
                    ) : (
                      filteredIcons.map(entry => {
                        const Icon = entry.Icon
                        return (
                          <DropdownMenuItem
                            key={entry.id}
                            className="gap-2"
                            onClick={() =>
                              setForm(current => ({
                                ...current,
                                icon: entry.id
                              }))
                            }
                          >
                            <Icon className="size-3.5 shrink-0" />
                            <span className="flex-1">{entry.label}</span>
                            {form.icon === entry.id ? (
                              <Check className="text-blue-500 size-3.5" />
                            ) : null}
                          </DropdownMenuItem>
                        )
                      })
                    )}
                  </div>
                </DropdownMenuContent>
              </DropdownMenu>

              <div className="min-w-0 flex-1 space-y-0.5">
                <Input
                  value={form.name}
                  onChange={event => {
                    const name = event.target.value
                    setForm(current => ({
                      ...current,
                      name,
                      slug: slugTouched ? current.slug : slugify(name)
                    }))
                  }}
                  placeholder="Untitled specialist"
                  className="placeholder:text-muted-foreground h-7 border-0 bg-transparent px-0 text-sm font-medium shadow-none focus-visible:ring-0"
                  autoFocus
                />
                <Input
                  value={form.slug}
                  onChange={event => {
                    setSlugTouched(true)
                    setForm(current => ({
                      ...current,
                      slug: slugify(event.target.value)
                    }))
                  }}
                  placeholder="slug"
                  className="text-muted-foreground placeholder:text-muted-foreground/60 h-5 border-0 bg-transparent px-0 font-mono text-xs shadow-none focus-visible:ring-0"
                />
              </div>
            </div>

            <Input
              value={form.description}
              onChange={event =>
                setForm(current => ({
                  ...current,
                  description: event.target.value
                }))
              }
              placeholder="Short description for pickers. Not used by the agent."
              className={specialistFieldClassName()}
            />
            <textarea
              value={form.instructions}
              onChange={event =>
                setForm(current => ({
                  ...current,
                  instructions: event.target.value
                }))
              }
              rows={5}
              placeholder="Instructions — appended to the base system prompt. Optional."
              className="border-border/50 bg-muted/40 placeholder:text-muted-foreground focus-visible:ring-ring flex min-h-[8rem] w-full rounded-2xl border-0 px-3.5 py-3 text-sm outline-none focus-visible:ring-1"
            />
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-baseline gap-2">
                <h2 className="text-sm font-medium">
                  Skills ({form.skillNames.length})
                </h2>
                {onManageSkills ? (
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground text-xs transition-colors"
                    onClick={onManageSkills}
                  >
                    Manage all skills
                  </button>
                ) : null}
              </div>
              <DropdownMenu
                open={skillAddOpen}
                onOpenChange={open => {
                  setSkillAddOpen(open)
                  if (!open) setSkillAddQuery('')
                }}
              >
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    className="bg-muted/40 hover:bg-muted/60 text-muted-foreground inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-xs transition-colors"
                  >
                    Add a skill…
                    <ChevronDown className="size-3.5" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="end"
                  className="w-80 p-0"
                  onCloseAutoFocus={event => event.preventDefault()}
                >
                  <div className="border-b px-2 py-2">
                    <div className="relative">
                      <Search className="text-muted-foreground/70 pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2" />
                      <Input
                        value={skillAddQuery}
                        onChange={event => setSkillAddQuery(event.target.value)}
                        placeholder="Search"
                        className="h-8 border-0 bg-transparent pl-7 shadow-none focus-visible:ring-0"
                        autoFocus
                      />
                    </div>
                  </div>
                  <div className="chat-scrollbar max-h-56 overflow-y-auto py-1">
                    {availableSkills.length === 0 ? (
                      <p className="text-muted-foreground px-3 py-3 text-xs">
                        Nothing to add.
                      </p>
                    ) : (
                      availableSkills.map(skill => {
                        const meta = skillMetaText(skill)
                        return (
                          <DropdownMenuItem
                            key={skill.name}
                            className="gap-2 py-2"
                            onClick={() => addSkill(skill.name)}
                          >
                            <SkillGlyph
                              skill={skill}
                              className="size-[18px]"
                            />
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-sm">
                                {skill.name}
                              </span>
                              {skill.description ? (
                                <span className="text-muted-foreground block truncate text-xs">
                                  {skill.description}
                                </span>
                              ) : null}
                              {meta ? (
                                <span className="text-muted-foreground/70 block truncate text-[10px]">
                                  {meta}
                                </span>
                              ) : null}
                            </span>
                          </DropdownMenuItem>
                        )
                      })
                    )}
                  </div>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
            {selectedSkillRows.length === 0 ? (
              <p className="text-muted-foreground py-2 text-sm">
                No skills selected.
              </p>
            ) : (
              <div className="divide-border/40 divide-y">
                {selectedSkillRows.map(row => {
                  const meta = row.skill ? skillMetaText(row.skill) : null
                  return (
                    <div
                      key={row.name}
                      className="flex items-center gap-3 py-2.5"
                    >
                      <button
                        type="button"
                        className={cn(
                          'flex min-w-0 flex-1 items-center gap-3 text-left',
                          onOpenSkill &&
                            'hover:opacity-90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring rounded-md'
                        )}
                        disabled={!onOpenSkill}
                        onClick={() => onOpenSkill?.(row.name)}
                      >
                        {row.skill ? (
                          <SkillGlyph skill={row.skill} />
                        ) : (
                          <span className="bg-muted flex size-7 shrink-0 items-center justify-center rounded-md">
                            <Sparkles className="text-muted-foreground size-3.5" />
                          </span>
                        )}
                        <span className="min-w-0 flex-1">
                          <span
                            className={cn(
                              'block truncate text-sm',
                              onOpenSkill && 'hover:underline'
                            )}
                          >
                            {row.name}
                          </span>
                          {meta || row.statusLabel ? (
                            <span className="text-muted-foreground block truncate text-xs">
                              {[meta, row.statusLabel]
                                .filter(Boolean)
                                .join(' · ')}
                            </span>
                          ) : null}
                        </span>
                      </button>
                      {row.status !== 'ok' ? (
                        <div className="flex shrink-0 items-center gap-1.5">
                          <span className="text-amber-500/90 text-[11px] font-medium">
                            {row.statusLabel}
                          </span>
                          {row.status === 'disabled' && onEnableSkill ? (
                            <button
                              type="button"
                              className="bg-muted/50 hover:bg-muted text-foreground rounded-full px-2 py-0.5 text-[11px] transition-colors"
                              disabled={skillActionPending === row.name}
                              onClick={() => void handleEnableSkill(row.name)}
                            >
                              {skillActionPending === row.name
                                ? '…'
                                : 'Enable'}
                            </button>
                          ) : null}
                          {row.status === 'missing' ? (
                            <button
                              type="button"
                              className="bg-muted/50 hover:bg-muted text-foreground rounded-full px-2 py-0.5 text-[11px] transition-colors"
                              disabled={skillActionPending === row.name}
                              onClick={() => void handleInstallSkill(row.name)}
                            >
                              {skillActionPending === row.name
                                ? '…'
                                : resolveSkillInstallSource(row.name)
                                  ? 'Install'
                                  : 'Find'}
                            </button>
                          ) : null}
                        </div>
                      ) : null}
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-foreground rounded-md p-1 transition-colors"
                        aria-label={`Remove ${row.name}`}
                        onClick={() => removeSkill(row.name)}
                      >
                        <X className="size-3.5" />
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <h2 className="text-sm font-medium">
                  Tools ({form.toolNames.length})
                </h2>
                <p className="text-muted-foreground mt-0.5 text-xs">
                  Allowlist for this specialist. Core tools are the usual
                  defaults; Extra tools are opt-in.
                </p>
              </div>
            </div>
            <div className="relative">
              <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2" />
              <Input
                value={toolQuery}
                onChange={event => setToolQuery(event.target.value)}
                placeholder="Search tools"
                className="border-border/50 bg-muted/40 h-9 pl-9"
              />
            </div>
            {toolsLoading && catalogTools.length === 0 ? (
              <p className="text-muted-foreground py-2 text-sm">Loading tools…</p>
            ) : catalogTools.length === 0 ? (
              <p className="text-muted-foreground py-2 text-sm">
                No tools available.
              </p>
            ) : (
              <div className="space-y-4">
                {(
                  [
                    { label: 'Core', tools: coreTools },
                    { label: 'Extra', tools: extraTools }
                  ] as const
                ).map(group => (
                  <div key={group.label} className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                        {group.label} ({group.tools.length})
                      </p>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          className="text-muted-foreground hover:text-foreground text-[11px] transition-colors"
                          onClick={() => setTierTools(group.tools, true)}
                        >
                          All
                        </button>
                        <span className="text-muted-foreground/40 text-[11px]">
                          /
                        </span>
                        <button
                          type="button"
                          className="text-muted-foreground hover:text-foreground text-[11px] transition-colors"
                          onClick={() => setTierTools(group.tools, false)}
                        >
                          None
                        </button>
                      </div>
                    </div>
                    {group.tools.length === 0 ? (
                      <p className="text-muted-foreground text-xs">
                        No {group.label.toLowerCase()} tools match.
                      </p>
                    ) : (
                      <div className="divide-border/40 max-h-56 divide-y overflow-y-auto rounded-xl border border-border/40">
                        {group.tools.map(tool => {
                          const checked = form.toolNames.includes(tool.id)
                          return (
                            <div
                              key={tool.id}
                              className="flex items-start justify-between gap-3 px-3 py-2"
                            >
                              <div className="min-w-0 flex-1">
                                <p className="truncate font-mono text-xs font-medium">
                                  {tool.id}
                                </p>
                                <p className="text-muted-foreground mt-0.5 line-clamp-1 text-xs">
                                  {tool.description}
                                </p>
                              </div>
                              <SpecialistToggle
                                enabled={checked}
                                label={`${checked ? 'Remove' : 'Allow'} ${tool.id}`}
                                onToggle={() => toggleTool(tool.id)}
                              />
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-baseline gap-2">
                <h2 className="text-sm font-medium">
                  MCPs ({selectedMcpRows.length})
                </h2>
                {onManageMcps ? (
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground text-xs transition-colors"
                    onClick={onManageMcps}
                  >
                    Manage all MCPs
                  </button>
                ) : null}
              </div>
              <DropdownMenu
                open={mcpAddOpen}
                onOpenChange={open => {
                  setMcpAddOpen(open)
                  if (!open) setMcpAddQuery('')
                }}
              >
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    className="bg-muted/40 hover:bg-muted/60 text-muted-foreground inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-xs transition-colors"
                  >
                    Add an MCP…
                    <ChevronDown className="size-3.5" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="end"
                  className="w-80 p-0"
                  onCloseAutoFocus={event => event.preventDefault()}
                >
                  <div className="border-b px-2 py-2">
                    <div className="relative">
                      <Search className="text-muted-foreground/70 pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2" />
                      <Input
                        value={mcpAddQuery}
                        onChange={event => setMcpAddQuery(event.target.value)}
                        placeholder="Search"
                        className="h-8 border-0 bg-transparent pl-7 shadow-none focus-visible:ring-0"
                        autoFocus
                      />
                    </div>
                  </div>
                  <div className="chat-scrollbar max-h-56 overflow-y-auto py-1">
                    {availableMcps.length === 0 ? (
                      <p className="text-muted-foreground px-3 py-3 text-xs">
                        Nothing to add.
                      </p>
                    ) : (
                      availableMcps.map(server => {
                        const meta = mcpMetaText(server)
                        return (
                          <DropdownMenuItem
                            key={server.id}
                            className="gap-2 py-2"
                            onClick={() => addMcp(server.id)}
                          >
                            <McpGlyph
                              server={server}
                              className="size-[18px]"
                            />
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-sm">
                                {server.name}
                              </span>
                              {server.description ? (
                                <span className="text-muted-foreground block truncate text-xs">
                                  {server.description}
                                </span>
                              ) : null}
                              {meta ? (
                                <span className="text-muted-foreground/70 block truncate text-[10px]">
                                  {meta}
                                </span>
                              ) : null}
                            </span>
                          </DropdownMenuItem>
                        )
                      })
                    )}
                  </div>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
            {selectedMcpRows.length === 0 ? (
              <p className="text-muted-foreground py-2 text-sm">
                No MCPs selected.
              </p>
            ) : (
              <div className="divide-border/40 divide-y">
                {selectedMcpRows.map(row => {
                  const meta = row.server ? mcpMetaText(row.server) : null
                  const catalogMeta =
                    row.kind === 'catalog'
                      ? row.catalog?.id || row.key.replace(/^catalog:/, '')
                      : null
                  const openTarget =
                    row.kind === 'catalog'
                      ? {
                          kind: 'catalog' as const,
                          id: row.key.replace(/^catalog:/, '')
                        }
                      : {
                          kind: 'server' as const,
                          id: row.server?.id || row.key.replace(/^server:/, '')
                        }
                  return (
                    <div
                      key={row.key}
                      className="flex items-center gap-3 py-2.5"
                    >
                      <button
                        type="button"
                        className={cn(
                          'flex min-w-0 flex-1 items-center gap-3 text-left',
                          onOpenMcp &&
                            'hover:opacity-90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring rounded-md'
                        )}
                        disabled={!onOpenMcp || !openTarget.id}
                        onClick={() => {
                          if (!openTarget.id) return
                          onOpenMcp?.(openTarget)
                        }}
                      >
                        {row.server ? (
                          <McpGlyph server={row.server} />
                        ) : (
                          <span className="bg-muted flex size-7 shrink-0 items-center justify-center rounded-md">
                            <Plug className="text-muted-foreground size-3.5" />
                          </span>
                        )}
                        <span className="min-w-0 flex-1">
                          <span
                            className={cn(
                              'block truncate text-sm',
                              onOpenMcp && 'hover:underline'
                            )}
                          >
                            {row.name}
                          </span>
                          <span className="text-muted-foreground block truncate text-xs">
                            {[meta || catalogMeta, row.statusLabel]
                              .filter(Boolean)
                              .join(' · ')}
                          </span>
                        </span>
                      </button>
                      {row.status !== 'ok' ? (
                        <span className="text-amber-500/90 shrink-0 text-[11px] font-medium">
                          {row.statusLabel}
                        </span>
                      ) : null}
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-foreground rounded-md p-1 transition-colors"
                        aria-label={`Remove ${row.name}`}
                        onClick={() => {
                          if (row.kind === 'catalog') {
                            removeMcpCatalog(
                              row.key.replace(/^catalog:/, '')
                            )
                          } else if (row.server) {
                            removeMcp(row.server.id)
                          } else {
                            removeMcp(row.key.replace(/^server:/, ''))
                          }
                        }}
                      >
                        <X className="size-3.5" />
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </section>
        </div>
      </div>

      <div className="border-border/60 flex shrink-0 items-center justify-end gap-1 border-t px-6 py-3">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onBack}
          disabled={saving}
        >
          Cancel
        </Button>
        <Button
          type="button"
          size="sm"
          className="rounded-full px-4"
          disabled={saving}
          onClick={() => void save()}
        >
          {saving
            ? 'Saving…'
            : mode === 'new'
              ? 'Create specialist'
              : 'Save'}
        </Button>
      </div>
    </div>
  )
}
