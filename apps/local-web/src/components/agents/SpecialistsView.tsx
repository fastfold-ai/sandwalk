import type {
  AgentSkill,
  McpCatalogEntry,
  McpServer,
  Specialist,
  SpecialistColor,
  SpecialistIcon
} from '@sandwalk/agent-ui-core'
import {
  AlertTriangle,
  ArrowLeft,
  Atom,
  BarChart3,
  BookOpen,
  Bot,
  Briefcase,
  Check,
  ChevronDown,
  Code2,
  Database,
  Dna,
  FlaskConical,
  GitBranch,
  Globe,
  Heart,
  MessageSquare,
  Microscope,
  Plug,
  Plus,
  Search,
  Shield,
  Signpost,
  Sparkles,
  Star,
  Target,
  Trash2,
  X,
  Zap
} from 'lucide-react'
import type { ComponentType } from 'react'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { ListRowsSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import {
  composerSkillIcon,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import { cn } from '@/lib/utils'

const MCP_ICONS: Record<string, { src: string; invertInDark?: boolean }> = {
  tamarind: { src: '/integrations/tamarind.png' },
  latch: { src: '/integrations/latch.png' },
  neurosnap: { src: '/integrations/neurosnap.png' },
  linear: { src: '/integrations/linear.png' }
}

function skillMetaText(skill: AgentSkill): string | null {
  const parts: string[] = []
  const author = String(skill.author || '').trim()
  if (author) parts.push(author)
  if (skill.version) parts.push(`v${String(skill.version).replace(/^v/i, '')}`)
  return parts.length > 0 ? parts.join(' · ') : null
}

function mcpIconKey(server: McpServer): string {
  return String(server.catalogId || server.name || '')
    .trim()
    .toLowerCase()
}

function mcpMetaText(server: McpServer): string | null {
  const parts: string[] = []
  const transport =
    server.transport === 'streamable_http'
      ? 'Streamable HTTP'
      : server.transport === 'sse'
        ? 'SSE'
        : server.transport === 'stdio'
          ? 'stdio'
          : ''
  if (transport) parts.push(transport)
  if (server.catalogId) parts.push(server.catalogId)
  return parts.length > 0 ? parts.join(' · ') : null
}

function McpGlyph({
  server,
  className
}: {
  server: McpServer
  className?: string
}) {
  const icon = MCP_ICONS[mcpIconKey(server)]
  if (icon) {
    return (
      <img
        src={icon.src}
        alt=""
        className={cn(
          'size-7 shrink-0 rounded object-contain',
          icon.invertInDark && 'dark:invert',
          className
        )}
      />
    )
  }
  return (
    <span
      className={cn(
        'bg-muted flex size-7 shrink-0 items-center justify-center rounded-md',
        className
      )}
    >
      <Plug className="text-muted-foreground size-3.5" />
    </span>
  )
}

function SkillGlyph({
  skill,
  className
}: {
  skill: AgentSkill
  className?: string
}) {
  const iconSource = composerSkillIcon(skill)
  if (iconSource) {
    return (
      <img
        src={iconSource}
        alt=""
        className={cn(
          'size-7 shrink-0 rounded object-contain',
          skillIconInvertInDark(skill) && 'dark:invert',
          className
        )}
      />
    )
  }
  return (
    <span
      className={cn(
        'bg-muted flex size-7 shrink-0 items-center justify-center rounded-md',
        className
      )}
    >
      <Sparkles className="text-muted-foreground size-3.5" />
    </span>
  )
}

const FASTFOLD_SKILL_INSTALL_SOURCES: Record<string, string> = {
  fold: 'fastfold-ai/skills@skills/fold',
  boltz: 'fastfold-ai/skills@skills/boltz',
  protein_design_boltzgen: 'fastfold-ai/skills@skills/protein_design_boltzgen',
  md_openmm_calvados: 'fastfold-ai/skills@skills/md_openmm_calvados',
  md_openmmdl: 'fastfold-ai/skills@skills/md_openmmdl',
  diagrams_mermaid: 'fastfold-ai/skills@skills/diagrams_mermaid',
  slack_report: 'fastfold-ai/skills@skills/slack_report'
}

export function resolveSkillInstallSource(skillName: string): string | null {
  const name = skillName.trim()
  if (!name) return null
  if (FASTFOLD_SKILL_INSTALL_SOURCES[name]) {
    return FASTFOLD_SKILL_INSTALL_SOURCES[name]
  }
  // Common third-party catalog layouts used by installed science skills.
  if (name.includes('_') || name.includes('-')) {
    return `K-Dense-AI/scientific-agent-skills@${name}`
  }
  return null
}

function SpecialistToggle({
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

export const SPECIALIST_COLORS: Array<{
  id: SpecialistColor
  label: string
  swatch: string
  ink?: boolean
}> = [
  { id: 'ink', label: 'Ink', swatch: 'bg-zinc-900 dark:bg-zinc-100', ink: true },
  { id: 'gray', label: 'Gray', swatch: 'bg-zinc-500' },
  { id: 'red', label: 'Red', swatch: 'bg-red-500' },
  { id: 'orange', label: 'Orange', swatch: 'bg-orange-500' },
  { id: 'amber', label: 'Yellow', swatch: 'bg-amber-400' },
  { id: 'green', label: 'Green', swatch: 'bg-emerald-500' },
  { id: 'teal', label: 'Aqua', swatch: 'bg-teal-500' },
  { id: 'blue', label: 'Blue', swatch: 'bg-blue-500' },
  { id: 'indigo', label: 'Indigo', swatch: 'bg-indigo-500' },
  { id: 'violet', label: 'Violet', swatch: 'bg-violet-500' },
  { id: 'pink', label: 'Magenta', swatch: 'bg-pink-500' }
]

export const SPECIALIST_ICONS: Array<{
  id: SpecialistIcon
  label: string
  Icon: ComponentType<{ className?: string }>
}> = [
  { id: 'agent', label: 'Agent', Icon: Bot },
  { id: 'organization', label: 'Organization', Icon: BarChart3 },
  { id: 'chat', label: 'Chat', Icon: MessageSquare },
  { id: 'lightning', label: 'Lightning', Icon: Zap },
  { id: 'star', label: 'Star', Icon: Star },
  { id: 'signpost', label: 'Signpost', Icon: Signpost },
  { id: 'code', label: 'Command Line', Icon: Code2 },
  { id: 'database', label: 'Database', Icon: Database },
  { id: 'globe', label: 'Globe', Icon: Globe },
  { id: 'flask', label: 'Flask', Icon: FlaskConical },
  { id: 'dna', label: 'DNA', Icon: Dna },
  { id: 'microscope', label: 'Microscope', Icon: Microscope },
  { id: 'book', label: 'Book', Icon: BookOpen },
  { id: 'sparkles', label: 'Sparkles', Icon: Sparkles },
  { id: 'git-branch', label: 'Git Branch', Icon: GitBranch },
  { id: 'target', label: 'Target', Icon: Target },
  { id: 'shield', label: 'Shield', Icon: Shield },
  { id: 'heart', label: 'Heart', Icon: Heart },
  { id: 'briefcase', label: 'Briefcase', Icon: Briefcase },
  { id: 'atom', label: 'Atom', Icon: Atom }
]

export function specialistColorClass(color: string | undefined) {
  return (
    SPECIALIST_COLORS.find(item => item.id === color)?.swatch ??
    SPECIALIST_COLORS[0].swatch
  )
}

function specialistInkOnLight(color: string | undefined) {
  return Boolean(SPECIALIST_COLORS.find(item => item.id === color)?.ink)
}

export function SpecialistGlyph({
  icon,
  className
}: {
  icon: string | undefined
  className?: string
}) {
  const entry =
    SPECIALIST_ICONS.find(item => item.id === icon) ?? SPECIALIST_ICONS[0]
  const Icon = entry.Icon
  return <Icon className={className} />
}

function SpecialistAvatar({
  color,
  icon,
  className
}: {
  color: string | undefined
  icon: string | undefined
  className?: string
}) {
  const ink = specialistInkOnLight(color)
  return (
    <span
      className={cn(
        'flex size-9 shrink-0 items-center justify-center rounded-xl',
        specialistColorClass(color),
        ink ? 'text-white dark:text-zinc-900' : 'text-white',
        className
      )}
    >
      <SpecialistGlyph icon={icon} className="size-4" />
    </span>
  )
}

function slugify(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

type FormState = {
  name: string
  slug: string
  description: string
  instructions: string
  color: SpecialistColor
  icon: SpecialistIcon
  skillNames: string[]
  mcpServerIds: string[]
  mcpCatalogIds: string[]
  enabled: boolean
}

function emptyForm(): FormState {
  return {
    name: '',
    slug: '',
    description: '',
    instructions: '',
    color: 'ink',
    icon: 'git-branch',
    skillNames: [],
    mcpServerIds: [],
    mcpCatalogIds: [],
    enabled: true
  }
}

function formFromSpecialist(specialist: Specialist): FormState {
  return {
    name: specialist.name,
    slug: specialist.slug,
    description: specialist.description || '',
    instructions: specialist.instructions || '',
    color: (specialist.color as SpecialistColor) || 'ink',
    icon: (specialist.icon as SpecialistIcon) || 'git-branch',
    skillNames: [...(specialist.skillNames || [])],
    mcpServerIds: [...(specialist.mcpServerIds || [])],
    mcpCatalogIds: [...(specialist.mcpCatalogIds || [])],
    enabled: specialist.enabled !== false
  }
}

type CapabilityIssue = {
  kind: 'skill' | 'mcp'
  name: string
  detail: string
}

function fieldClassName() {
  return 'border-border/50 bg-muted/40 placeholder:text-muted-foreground focus-visible:ring-ring h-10 w-full rounded-xl border-0 px-3.5 text-sm outline-none focus-visible:ring-1'
}

export function SpecialistsView({
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
  onOpenNew,
  onOpenEdit,
  onBack,
  onManageSkills,
  onManageMcps,
  onOpenSkill,
  onOpenMcp,
  onEnableSkill,
  onInstallSkill
}: {
  mode: 'list' | 'new' | 'edit'
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
      mcpServerIds?: string[]
      mcpCatalogIds?: string[]
      enabled?: boolean
    }
  ) => Promise<Specialist>
  onDelete: (id: string) => Promise<void>
  onOpenNew: () => void
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
}) {
  const editing = useMemo(
    () =>
      mode === 'edit'
        ? specialists.find(item => item.id === specialistId) || null
        : null,
    [mode, specialistId, specialists]
  )
  const [form, setForm] = useState<FormState>(emptyForm)
  const [slugTouched, setSlugTouched] = useState(false)
  const [skillAddQuery, setSkillAddQuery] = useState('')
  const [mcpAddQuery, setMcpAddQuery] = useState('')
  const [skillAddOpen, setSkillAddOpen] = useState(false)
  const [mcpAddOpen, setMcpAddOpen] = useState(false)
  const [appearanceOpen, setAppearanceOpen] = useState(false)
  const [iconQuery, setIconQuery] = useState('')
  const [listQuery, setListQuery] = useState('')
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [skillActionPending, setSkillActionPending] = useState<string | null>(
    null
  )
  const [togglePendingId, setTogglePendingId] = useState<string | null>(null)

  useEffect(() => {
    if (mode === 'new') {
      setForm(emptyForm())
      setSlugTouched(false)
      setSkillAddQuery('')
      setMcpAddQuery('')
      setIconQuery('')
      return
    }
    if (mode === 'edit' && editing) {
      setForm(formFromSpecialist(editing))
      setSlugTouched(true)
      setSkillAddQuery('')
      setMcpAddQuery('')
      setIconQuery('')
    }
  }, [editing, mode])

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
    const issues: CapabilityIssue[] = []
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

  const filteredSpecialists = useMemo(() => {
    const needle = listQuery.trim().toLowerCase()
    if (!needle) return specialists
    return specialists.filter(item => {
      const haystack = [
        item.name,
        item.slug,
        item.description || '',
        item.skillNames.join(' '),
        item.mcpServerIds.join(' ')
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(needle)
    })
  }, [listQuery, specialists])

  if (mode === 'list') {
    return (
      <div className="chat-scrollbar flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 md:p-6">
          <div className="mb-0">
            <h2 className="text-2xl font-semibold">Specialists</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Run profiles that scope skills, MCPs, and extra instructions for
              focused research sessions.
            </p>
          </div>

          <div className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-20 flex flex-wrap items-center gap-2 pb-3 pt-2 backdrop-blur">
            <div className="relative min-w-[280px] max-w-3xl flex-1">
              <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
              <Input
                value={listQuery}
                onChange={event => setListQuery(event.target.value)}
                placeholder="Search specialists, descriptions..."
                className="border-border/70 bg-background/70 h-11 pl-10"
              />
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-10 shrink-0"
              onClick={onOpenNew}
            >
              <Plus className="size-3.5" />
              New specialist
            </Button>
          </div>

          {loading ? (
            <ListRowsSkeleton />
          ) : specialists.length === 0 ? (
            <p className="text-muted-foreground py-16 text-center text-sm">
              No specialists yet
            </p>
          ) : filteredSpecialists.length === 0 ? (
            <p className="text-muted-foreground py-8 text-center text-sm">
              No specialists match “{listQuery.trim()}”.
            </p>
          ) : (
            <div className="divide-border/60 divide-y">
              {filteredSpecialists.map(item => {
                const isEnabled = item.enabled !== false
                return (
                  <div
                    key={item.id}
                    className={cn(
                      'hover:bg-muted/40 -mx-2 flex w-[calc(100%+1rem)] items-start gap-3 rounded-lg px-2 py-3.5 transition-colors',
                      !isEnabled && 'opacity-60'
                    )}
                  >
                    <button
                      type="button"
                      className="flex min-w-0 flex-1 items-start gap-3 text-left"
                      onClick={() => onOpenEdit(item.id)}
                    >
                      <SpecialistAvatar color={item.color} icon={item.icon} />
                      <span className="min-w-0 flex-1">
                        <span className="flex items-baseline gap-2">
                          <span className="truncate text-sm font-medium">
                            {item.name}
                          </span>
                          <span className="text-muted-foreground shrink-0 text-xs">
                            {item.slug}
                          </span>
                          {!isEnabled ? (
                            <span className="text-muted-foreground shrink-0 text-[11px]">
                              Off
                            </span>
                          ) : null}
                        </span>
                        <span className="text-muted-foreground mt-0.5 block line-clamp-1 text-sm">
                          {item.description || 'No description'}
                        </span>
                        <span className="text-muted-foreground mt-1.5 block text-xs">
                          {item.skillNames.length} skill
                          {item.skillNames.length === 1 ? '' : 's'}
                          <span className="mx-1.5 opacity-40">·</span>
                          {(item.mcpServerIds?.length || 0) +
                            (item.mcpCatalogIds?.length || 0)}{' '}
                          MCP
                          {(item.mcpServerIds?.length || 0) +
                            (item.mcpCatalogIds?.length || 0) ===
                          1
                            ? ''
                            : 's'}
                        </span>
                      </span>
                    </button>
                    <div className="flex shrink-0 items-center pt-1">
                      <SpecialistToggle
                        enabled={isEnabled}
                        pending={togglePendingId === item.id}
                        label={`${isEnabled ? 'Disable' : 'Enable'} ${item.name}`}
                        onToggle={() =>
                          void toggleSpecialistEnabled(item.id, !isEnabled)
                        }
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    )
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
              className={fieldClassName()}
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
