import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { MemoryEntry, Specialist } from '@sandwalk/agent-ui-core'
import {
  Check,
  Fingerprint,
  MessageSquare,
  MoreVertical,
  Pencil,
  Play,
  Plus,
  Search,
  Settings,
  SlidersHorizontal,
  Trash2,
  User,
  X
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { ListRowsSkeleton } from '@/components/agents/PageSkeletons'
import {
  PERSONA_CHARACTERS,
  SpecialistAvatar
} from '@/components/agents/specialists-view/specialist-ui'
import { SpecialistToggle } from '@/components/agents/specialists-view/specialists-view-shared'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { skillIconForName } from '@/lib/skill-icons'
import { cn } from '@/lib/utils'

const COOKBOOK_LABELS: Record<string, string> = {
  'biomed-research': '05 Biomed research',
  'pharma-intel': '02 Pharma intel',
  'industry-intel': '01 Industry intel',
  'context-graph': '03 Context graph',
  'vc-os': '04 VC OS',
  'second-brain': '06 Second brain'
}

type ProfileTab = 'info' | 'runtime' | 'skills' | 'memories'

export function SpecialistsListView({
  specialists,
  loading,
  client,
  userName,
  onOpenNew,
  onOpenEdit,
  onUpdate,
  onDelete,
  onRefresh,
  onStartChat,
  onExploreBrain,
  onOpenDefaults
}: {
  specialists: Specialist[]
  loading?: boolean
  client?: LocalAgentClient
  userName?: string | null
  onOpenNew: () => void
  onOpenEdit: (id: string) => void
  onUpdate: (
    id: string,
    input: {
      name?: string
      roleLabel?: string | null
      avatarUrl?: string | null
      icon?: string
      color?: string
      provider?: string | null
      model?: string | null
      clearLlm?: boolean
      cookbookId?: string | null
      priors?: string | null
      enabled?: boolean
    }
  ) => Promise<Specialist>
  onDelete?: (id: string) => Promise<void>
  onRefresh: () => Promise<void>
  onStartChat?: (specialist: Specialist) => void
  onExploreBrain?: (specialist: Specialist) => void
  onOpenDefaults?: () => void
}) {
  const [listQuery, setListQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<ProfileTab>('info')
  const [editingInline, setEditingInline] = useState(false)
  const [draftName, setDraftName] = useState('')
  const [draftRole, setDraftRole] = useState('')
  const [draftIcon, setDraftIcon] = useState('capybara')
  const [draftAvatarUrl, setDraftAvatarUrl] = useState('')
  const [draftPriors, setDraftPriors] = useState('')
  const [draftCookbook, setDraftCookbook] = useState('biomed-research')
  const [draftModel, setDraftModel] = useState('')
  const [savingProfile, setSavingProfile] = useState(false)

  const [personaMemories, setPersonaMemories] = useState<MemoryEntry[]>([])
  const [newMemoryText, setNewMemoryText] = useState('')
  const [loadingMemories, setLoadingMemories] = useState(false)

  const filteredSpecialists = useMemo(() => {
    const needle = listQuery.trim().toLowerCase()
    if (!needle) return specialists
    return specialists.filter(item => {
      const haystack = [
        item.name,
        item.slug,
        item.roleLabel || '',
        item.description || '',
        item.priors || '',
        item.skillNames.join(' ')
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(needle)
    })
  }, [listQuery, specialists])

  const selected = useMemo(
    () => specialists.find(s => s.id === selectedId) ?? null,
    [specialists, selectedId]
  )

  useEffect(() => {
    if (!selected) return
    setDraftName(selected.name)
    setDraftRole(selected.roleLabel || selected.description || 'Specialist')
    setDraftIcon(selected.icon || 'capybara')
    setDraftAvatarUrl(selected.avatarUrl || '')
    setDraftPriors(
      selected.priors ||
        selected.description ||
        'Prioritize reproducible evidence, clear provenance, and structured synthesis.'
    )
    setDraftCookbook(selected.cookbookId || 'biomed-research')
    setDraftModel(selected.model || '')
  }, [selected])

  useEffect(() => {
    if (!selected || !client) {
      setPersonaMemories([])
      return
    }
    let cancelled = false
    setLoadingMemories(true)
    client
      .listMemoryEntries(`specialist:${selected.id}`, false)
      .then(res => {
        if (!cancelled) setPersonaMemories(res.data)
      })
      .catch(() => {
        if (!cancelled) setPersonaMemories([])
      })
      .finally(() => {
        if (!cancelled) setLoadingMemories(false)
      })
    return () => {
      cancelled = true
    }
  }, [selected, client])

  const handleSaveProfile = async () => {
    if (!selected || !draftName.trim()) return
    setSavingProfile(true)
    try {
      await onUpdate(selected.id, {
        name: draftName.trim(),
        roleLabel: draftRole.trim() || null,
        icon: draftIcon,
        avatarUrl: draftAvatarUrl.trim() || null,
        priors: draftPriors.trim() || null,
        cookbookId: draftCookbook,
        model: draftModel.trim() || null,
        clearLlm: !draftModel.trim()
      })
      await onRefresh()
      setEditingInline(false)
      toast.success(`Saved ${draftName.trim()}`)
    } catch (cause) {
      toast.error(
        cause instanceof Error ? cause.message : 'Unable to save persona'
      )
    } finally {
      setSavingProfile(false)
    }
  }

  const handleAddPersonaMemory = async () => {
    if (!selected || !client || !newMemoryText.trim()) return
    try {
      const created = await client.createMemoryEntry({
        scope: `specialist:${selected.id}`,
        target: 'specialist',
        layer: 'L2',
        content: newMemoryText.trim(),
        tags: [selected.slug]
      })
      setPersonaMemories(prev => [created, ...prev])
      setNewMemoryText('')
      await onRefresh()
      toast.success(`Saved memory to ${selected.name}`)
    } catch (cause) {
      toast.error(
        cause instanceof Error ? cause.message : 'Could not add memory'
      )
    }
  }

  const handleDeletePersonaMemory = async (entryId: string) => {
    if (!client) return
    try {
      await client.deleteMemoryEntry(entryId)
      setPersonaMemories(prev => prev.filter(m => m.id !== entryId))
      await onRefresh()
    } catch (cause) {
      toast.error(
        cause instanceof Error ? cause.message : 'Could not delete memory'
      )
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-1 overflow-hidden">
      {/* Main Left Column: Agents & Personas Card Grid */}
      <div className="chat-scrollbar min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-5 pt-6 pb-10 md:px-8 md:pt-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">
                Specialists
              </h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Starter personas and domain specialists—create your own or
                customize any specialist’s priors, model, skills, MCPs, and
                brain.
              </p>
            </div>
            <div className="flex items-center gap-2">
              {onOpenDefaults ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="border-border/60 bg-muted/20 hover:bg-muted/35 h-9 gap-1.5 rounded-xl px-3.5 text-xs font-medium"
                  onClick={onOpenDefaults}
                >
                  <SlidersHorizontal className="size-3.5" />
                  Specialist defaults
                </Button>
              ) : null}
              <Button
                type="button"
                size="sm"
                className="h-9 gap-1.5 rounded-xl px-3.5 text-xs font-medium"
                onClick={onOpenNew}
              >
                <Plus className="size-3.5" />
                New specialist
              </Button>
            </div>
          </div>

          <div className="relative max-w-md">
            <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
            <Input
              value={listQuery}
              onChange={event => setListQuery(event.target.value)}
              placeholder="Search personas, roles, skills..."
              className="border-border/60 bg-muted/20 h-9 rounded-xl pl-9 text-sm"
            />
          </div>

          {loading ? (
            <ListRowsSkeleton />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filteredSpecialists.map(item => {
                const isSelected = item.id === selectedId
                const isEnabled = item.enabled !== false
                const roleText =
                  item.roleLabel || item.description || item.slug
                const modelText = item.model ? item.model : 'Default model'
                return (
                  <div
                    key={item.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => {
                      setSelectedId(item.id)
                      setEditingInline(false)
                    }}
                    onKeyDown={e => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setSelectedId(item.id)
                      }
                    }}
                    className={cn(
                      'group relative flex min-h-[250px] cursor-pointer flex-col justify-between rounded-2xl border p-5 text-left transition-all',
                      isSelected
                        ? 'border-foreground/30 bg-muted/45 ring-foreground/15 ring-2'
                        : 'border-border/50 bg-muted/20 hover:border-border hover:bg-muted/35',
                      !isEnabled && 'opacity-60'
                    )}
                  >
                    {/* Top-right 3-dots menu */}
                    <div className="flex items-center justify-between">
                      {item.roleLabel && item.roleLabel !== item.name ? (
                        <span className="border-border/50 bg-muted/40 text-muted-foreground rounded-full border px-2.5 py-0.5 text-[11px] font-medium">
                          {item.roleLabel}
                        </span>
                      ) : (
                        <span />
                      )}
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button
                            type="button"
                            onClick={e => e.stopPropagation()}
                            className="text-muted-foreground hover:text-foreground hover:bg-background/60 inline-flex size-7 items-center justify-center rounded-full transition-colors"
                            aria-label={`Actions for ${item.name}`}
                          >
                            <MoreVertical className="size-4" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={e => {
                              e.stopPropagation()
                              setSelectedId(item.id)
                              setEditingInline(true)
                            }}
                          >
                            Rename & Edit Persona
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={e => {
                              e.stopPropagation()
                              onOpenEdit(item.id)
                            }}
                          >
                            Configure Skills & Tools
                          </DropdownMenuItem>
                          {onExploreBrain ? (
                            <DropdownMenuItem
                              onClick={e => {
                                e.stopPropagation()
                                onExploreBrain(item)
                              }}
                            >
                              Explore Brain & Ontology
                            </DropdownMenuItem>
                          ) : null}
                          {onDelete ? (
                            <DropdownMenuItem
                              className="text-destructive focus:text-destructive"
                              onClick={e => {
                                e.stopPropagation()
                                void onDelete(item.id).then(() => {
                                  if (selectedId === item.id) {
                                    setSelectedId(null)
                                  }
                                  return onRefresh()
                                })
                              }}
                            >
                              Delete
                            </DropdownMenuItem>
                          ) : null}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>

                    {/* Center Character Portrait + Play Action Badge */}
                    <div className="my-4 flex items-center justify-center">
                      <div className="relative">
                        <SpecialistAvatar
                          color={item.color}
                          icon={item.icon}
                          avatarUrl={item.avatarUrl}
                          slug={item.slug}
                          size="xl"
                        />
                        <button
                          type="button"
                          title={`Start chat with ${item.name}`}
                          onClick={e => {
                            e.stopPropagation()
                            if (onStartChat) {
                              onStartChat(item)
                            } else {
                              setSelectedId(item.id)
                            }
                          }}
                          className="bg-foreground text-background hover:scale-105 absolute right-0 bottom-0 flex size-9 items-center justify-center rounded-full shadow-md transition-transform"
                        >
                          <Play className="size-4 fill-current pl-0.5" />
                        </button>
                      </div>
                    </div>

                    {/* Bottom Name + Model/Role Subtitle */}
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="truncate text-base font-semibold">
                          {item.name}
                        </span>
                        {(item.memoryCount ?? 0) > 0 ? (
                          <span className="bg-primary/10 text-primary rounded-full px-2 py-0.5 text-[10px] font-medium">
                            {item.memoryCount} mem
                          </span>
                        ) : null}
                      </div>
                      <p className="text-muted-foreground mt-0.5 truncate text-xs">
                        {modelText}
                        {roleText && roleText !== item.name
                          ? ` · ${roleText}`
                          : ''}
                      </p>
                    </div>
                  </div>
                )
              })}

              {/* Trailing '+' Create Card */}
              <button
                type="button"
                onClick={onOpenNew}
                className="border-border/60 hover:border-foreground/40 hover:bg-muted/20 flex min-h-[250px] flex-col items-center justify-center rounded-2xl border border-dashed p-5 transition-colors"
                aria-label="Create new agent persona"
              >
                <Plus className="text-muted-foreground size-7 stroke-[1.75]" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Right-Side Profile Inspector Drawer (Matches Screenshot 1) */}
      {selected ? (
        <aside className="border-border/60 bg-background flex h-full w-full max-w-[390px] shrink-0 flex-col border-l">
          {/* Drawer Header */}
          <div className="flex items-center justify-between px-5 pt-5 pb-3">
            <h3 className="text-base font-semibold">Profile</h3>
            <div className="flex items-center gap-1">
              <button
                type="button"
                title="Full Skills, Tools & MCP Editor"
                onClick={() => onOpenEdit(selected.id)}
                className="text-muted-foreground hover:text-foreground hover:bg-muted inline-flex size-8 items-center justify-center rounded-full transition-colors"
              >
                <Settings className="size-4" />
              </button>
              <button
                type="button"
                title="Close profile"
                onClick={() => setSelectedId(null)}
                className="text-muted-foreground hover:text-foreground hover:bg-muted inline-flex size-8 items-center justify-center rounded-full transition-colors"
              >
                <X className="size-4" />
              </button>
            </div>
          </div>

          <div className="chat-scrollbar flex-1 overflow-y-auto px-5 pb-6">
            {/* Avatar + Name Hero */}
            <div className="flex flex-col items-center pt-2 pb-4 text-center">
              <SpecialistAvatar
                color={selected.color}
                icon={editingInline ? draftIcon : selected.icon}
                avatarUrl={
                  editingInline ? draftAvatarUrl : selected.avatarUrl
                }
                slug={selected.slug}
                size="lg"
              />

              {editingInline ? (
                <div className="mt-3 w-full space-y-2 text-left">
                  <div>
                    <label className="text-muted-foreground text-[11px] font-medium">
                      Person / Agent Name
                    </label>
                    <Input
                      value={draftName}
                      onChange={e => setDraftName(e.target.value)}
                      placeholder="e.g. Atlas, Nova, Bumble..."
                      className="mt-1 h-8 text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-muted-foreground text-[11px] font-medium">
                      Role / Archetype
                    </label>
                    <Input
                      value={draftRole}
                      onChange={e => setDraftRole(e.target.value)}
                      placeholder="e.g. Ambitious Generalist, Dreamer, Project Manager"
                      className="mt-1 h-8 text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-muted-foreground text-[11px] font-medium">
                      Avatar Preset
                    </label>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {PERSONA_CHARACTERS.map(char => (
                        <button
                          key={char.id}
                          type="button"
                          onClick={() => {
                            setDraftIcon(char.id)
                            setDraftAvatarUrl('')
                          }}
                          className={cn(
                            'rounded-full p-0.5 transition-all',
                            draftIcon === char.id && !draftAvatarUrl
                              ? 'ring-foreground ring-2'
                              : 'opacity-75 hover:opacity-100'
                          )}
                          title={`${char.label} — ${char.archetype}`}
                        >
                          <SpecialistAvatar
                            color={selected.color}
                            icon={char.id}
                            size="sm"
                            className="size-9"
                          />
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-muted-foreground text-[11px] font-medium">
                      Custom Profile Photo URL (optional)
                    </label>
                    <Input
                      value={draftAvatarUrl}
                      onChange={e => setDraftAvatarUrl(e.target.value)}
                      placeholder="https://..."
                      className="mt-1 h-8 text-xs"
                    />
                  </div>
                  <div className="flex justify-end gap-1.5 pt-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => setEditingInline(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      className="h-7 gap-1 text-xs"
                      disabled={savingProfile}
                      onClick={() => void handleSaveProfile()}
                    >
                      <Check className="size-3" />
                      Save
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <h4 className="mt-3 text-lg font-semibold">
                    {selected.name}
                  </h4>
                  <p className="text-muted-foreground text-xs">
                    {selected.roleLabel || selected.description || selected.slug}
                  </p>
                </>
              )}

              {/* 3 Circular Action Buttons (Chat, Edit, Play/Brain) */}
              <div className="mt-4 flex items-center justify-center gap-3">
                <button
                  type="button"
                  title="Chat with this agent"
                  onClick={() => onStartChat?.(selected)}
                  className="border-border/70 bg-muted/30 hover:bg-muted flex size-10 items-center justify-center rounded-full border transition-colors"
                >
                  <MessageSquare className="size-4" />
                </button>
                <button
                  type="button"
                  title="Edit name, avatar & bias"
                  onClick={() => setEditingInline(v => !v)}
                  className={cn(
                    'border-border/70 flex size-10 items-center justify-center rounded-full border transition-colors',
                    editingInline
                      ? 'bg-foreground text-background'
                      : 'bg-muted/30 hover:bg-muted'
                  )}
                >
                  <Pencil className="size-4" />
                </button>
                <button
                  type="button"
                  title="Explore agent brain & knowledge graph"
                  onClick={() =>
                    onExploreBrain
                      ? onExploreBrain(selected)
                      : onOpenEdit(selected.id)
                  }
                  className="border-border/70 bg-muted/30 hover:bg-muted flex size-10 items-center justify-center rounded-full border transition-colors"
                >
                  <Play className="size-4 pl-0.5" />
                </button>
              </div>
            </div>

            {/* Pill Navigation Tabs (Info, Runtime, Skills, Memories N) */}
            <div className="mt-2 flex items-center gap-1 border-b border-border/50 pb-2.5">
              {(
                [
                  { id: 'info', label: 'Info' },
                  { id: 'runtime', label: 'Runtime •' },
                  {
                    id: 'skills',
                    label: `Skills ${selected.skillNames.length}`
                  },
                  {
                    id: 'memories',
                    label: `Memories ${personaMemories.length || selected.memoryCount || 0}`
                  }
                ] as const
              ).map(tab => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                    activeTab === tab.id
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab 1: Info */}
            {activeTab === 'info' && (
              <div className="mt-4 space-y-3">
                <div className="border-border/50 bg-muted/20 space-y-3 rounded-2xl border p-3.5">
                  <div className="flex items-start gap-3">
                    <Fingerprint className="text-muted-foreground mt-0.5 size-4 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="text-muted-foreground text-[11px]">
                        Persona ID & Ontology Lens
                      </div>
                      <div className="truncate font-mono text-xs">
                        {selected.slug} ·{' '}
                        {COOKBOOK_LABELS[
                          selected.cookbookId || 'biomed-research'
                        ] || '05 Biomed research'}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <User className="text-muted-foreground mt-0.5 size-4 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="text-muted-foreground text-[11px]">
                        Managed by
                      </div>
                      <div className="text-xs font-medium">
                        {userName ? `${userName} (you)` : 'You (Local)'}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="border-border/50 bg-muted/20 space-y-2 rounded-2xl border p-3.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold">
                      Cognitive Priors & Biases (PRIORS.md)
                    </span>
                  </div>
                  <textarea
                    value={draftPriors}
                    onChange={e => setDraftPriors(e.target.value)}
                    rows={4}
                    placeholder="Define how this persona thinks, what it is skeptical of, and its methodological biases..."
                    className="border-border/60 bg-background/70 w-full rounded-xl border p-2.5 text-xs leading-relaxed outline-none"
                  />
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      className="h-7 rounded-lg text-xs"
                      disabled={savingProfile}
                      onClick={() => void handleSaveProfile()}
                    >
                      Save Priors
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 2: Runtime */}
            {activeTab === 'runtime' && (
              <div className="mt-4 space-y-3">
                <div className="border-border/50 bg-muted/20 space-y-3 rounded-2xl border p-3.5">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-medium">Active in Picker</div>
                      <div className="text-muted-foreground text-[11px]">
                        Show this persona in the chat composer
                      </div>
                    </div>
                    <SpecialistToggle
                      enabled={selected.enabled !== false}
                      pending={savingProfile}
                      label={`Enable ${selected.name}`}
                      onToggle={() => {
                        void onUpdate(selected.id, {
                          enabled: selected.enabled === false
                        }).then(() => onRefresh())
                      }}
                    />
                  </div>

                  <div>
                    <label className="text-muted-foreground text-[11px] font-medium">
                      Preferred Model Override (leave blank for Default model)
                    </label>
                    <Input
                      value={draftModel}
                      onChange={e => setDraftModel(e.target.value)}
                      placeholder="Default model (or e.g. claude-sonnet-4-5, gpt-4o)"
                      className="mt-1 h-8 text-xs"
                    />
                  </div>

                  <div>
                    <label className="text-muted-foreground text-[11px] font-medium">
                      Default Knowledge Graph Cookbook Lens
                    </label>
                    <select
                      value={draftCookbook}
                      onChange={e => setDraftCookbook(e.target.value)}
                      className="border-border/60 bg-background mt-1 h-8 w-full rounded-lg border px-2 text-xs"
                    >
                      {Object.entries(COOKBOOK_LABELS).map(([id, label]) => (
                        <option key={id} value={id}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex justify-end">
                    <Button
                      type="button"
                      size="sm"
                      className="h-7 rounded-lg text-xs"
                      disabled={savingProfile}
                      onClick={() => void handleSaveProfile()}
                    >
                      Save Runtime
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 3: Skills & Tools */}
            {activeTab === 'skills' && (
              <div className="mt-4 space-y-3">
                <div className="border-border/50 bg-muted/20 space-y-2 rounded-2xl border p-3.5">
                  <div className="text-xs font-medium">
                    Equipped Skills ({selected.skillNames.length})
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {selected.skillNames.map(skill => {
                      const iconSrc = skillIconForName(skill)
                      return (
                        <span
                          key={skill}
                          className="bg-background border-border/60 inline-flex items-center gap-1.5 rounded-lg border px-2 py-0.5 font-mono text-[11px]"
                        >
                          {iconSrc ? (
                            <img
                              src={iconSrc}
                              alt=""
                              className="size-3.5 shrink-0 rounded-sm object-contain"
                            />
                          ) : null}
                          {skill}
                        </span>
                      )
                    })}
                  </div>
                  <div className="pt-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-8 w-full rounded-xl text-xs"
                      onClick={() => onOpenEdit(selected.id)}
                    >
                      Configure Skills, Tools & MCPs
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 4: Memories */}
            {activeTab === 'memories' && (
              <div className="mt-4 space-y-3">
                <div className="flex gap-1.5">
                  <Input
                    value={newMemoryText}
                    onChange={e => setNewMemoryText(e.target.value)}
                    placeholder={`Teach ${selected.name} a durable rule or memory...`}
                    className="h-8 text-xs"
                    onKeyDown={e => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        void handleAddPersonaMemory()
                      }
                    }}
                  />
                  <Button
                    type="button"
                    size="sm"
                    className="h-8 shrink-0 px-3 text-xs"
                    onClick={() => void handleAddPersonaMemory()}
                  >
                    Add
                  </Button>
                </div>

                {loadingMemories ? (
                  <p className="text-muted-foreground py-4 text-center text-xs">
                    Loading memories…
                  </p>
                ) : personaMemories.length === 0 ? (
                  <div className="border-border/50 bg-muted/15 rounded-2xl border p-4 text-center">
                    <p className="text-muted-foreground text-xs">
                      No learned memories yet for {selected.name}.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {personaMemories.map(mem => (
                      <div
                        key={mem.id}
                        className="border-border/50 bg-muted/20 flex items-start justify-between gap-2 rounded-xl border p-2.5 text-xs"
                      >
                        <p className="min-w-0 flex-1 leading-relaxed">
                          {mem.content}
                        </p>
                        <button
                          type="button"
                          onClick={() => void handleDeletePersonaMemory(mem.id)}
                          className="text-muted-foreground hover:text-destructive shrink-0 p-0.5"
                          title="Delete memory"
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {onExploreBrain ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 w-full rounded-xl text-xs"
                    onClick={() => onExploreBrain(selected)}
                  >
                    Open {selected.name}’s Brain & Ontology Graph
                  </Button>
                ) : null}
              </div>
            )}
          </div>
        </aside>
      ) : null}
    </div>
  )
}
