import type {
  AgentSkill,
  McpServer,
  RuntimeSettings,
  ServerSystemInfo,
  SessionSandboxStatus,
  Specialist
} from '@sandwalk/agent-ui-core'
import {
  Check,
  ChevronRight,
  Container,
  GitBranch,
  Infinity as InfinityIcon,
  ListChecks,
  Paperclip,
  Plug,
  Plus,
  Sparkles
} from 'lucide-react'
import {
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react'

import {
  cleanSkillDescription,
  mcpIconForServer
} from '@/components/agents/composer/composer-mention-utils'
import { ComposerSandboxPicker } from '@/components/agents/composer/ComposerSandboxPicker'
import {
  type SandboxActionPhase,
  type SandboxComputeChange
} from '@/components/agents/composer/sandbox-utils'
import {
  PLUS_MENU_OPEN_EVENT,
  type PlusMenuFlyout,
  takeQueuedPlusMenu
} from '@/components/agents/empty-start'
import { SpecialistAvatar } from '@/components/agents/SpecialistsView'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import {
  composerSkillIcon,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import { cn } from '@/lib/utils'

type MainRowId =
  | 'agent'
  | 'plan'
  | 'files'
  | 'skills'
  | 'mcp'
  | 'specialist'
  | 'sandbox'

export function ComposerPlusMenu({
  runtimeSettings,
  skills,
  mcpServers,
  specialists,
  selectedSpecialistId,
  sandboxStatus,
  sandboxPhase,
  onUpload,
  onPlanModeChange,
  onPickSkill,
  onPickMcp,
  onSpecialistSelect,
  onCreateSpecialist,
  onManageSpecialists,
  onSandboxBackendSelect,
  onSandboxComputeChange,
  onSandboxStart,
  onSandboxStop,
  onSandboxRestart,
  onLoadLocalSystem,
  onRefreshSandbox
}: {
  runtimeSettings: RuntimeSettings | null
  skills: AgentSkill[]
  mcpServers: McpServer[]
  specialists: Specialist[]
  selectedSpecialistId: string | null
  sandboxStatus: SessionSandboxStatus | null
  sandboxPhase: SandboxActionPhase
  onUpload: (files: FileList) => void
  onPlanModeChange?: (planMode: boolean) => Promise<void>
  onPickSkill?: (skill: AgentSkill) => void
  onPickMcp?: (server: McpServer) => void
  onSpecialistSelect?: (specialistId: string | null) => void | Promise<void>
  onCreateSpecialist?: () => void
  onManageSpecialists?: () => void
  onSandboxBackendSelect?: (
    backend: 'builtin' | 'modal'
  ) => void | Promise<void>
  onSandboxComputeChange?: (
    changes: SandboxComputeChange
  ) => void | Promise<void>
  onSandboxStart?: () => void | Promise<void>
  onSandboxStop?: () => void | Promise<void>
  onSandboxRestart?: () => void | Promise<void>
  onLoadLocalSystem?: () => Promise<ServerSystemInfo | null>
  onRefreshSandbox?: () => void | Promise<void>
}) {
  const uploadRef = useRef<HTMLInputElement | null>(null)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const [open, setOpen] = useState(false)
  const [menuWidth, setMenuWidth] = useState<number | undefined>()
  const [sideOffset, setSideOffset] = useState(8)
  const [alignOffset, setAlignOffset] = useState(0)
  const [search, setSearch] = useState('')
  const [flyout, setFlyout] = useState<
    'skills' | 'mcp' | 'specialist' | 'sandbox' | null
  >(null)
  const [activeRow, setActiveRow] = useState<MainRowId | null>(null)
  const [searchHitIndex, setSearchHitIndex] = useState(0)
  const [inFlyout, setInFlyout] = useState(false)
  const [flyoutIndex, setFlyoutIndex] = useState(0)

  const planMode = Boolean(runtimeSettings?.planMode)
  const selectedSpecialist = useMemo(
    () => specialists.find(item => item.id === selectedSpecialistId) || null,
    [selectedSpecialistId, specialists]
  )
  const needle = search.trim().toLowerCase()
  const enabledSkills = useMemo(
    () => skills.filter(skill => skill.enabled),
    [skills]
  )
  const enabledSpecialists = useMemo(
    () => specialists.filter(item => item.enabled !== false),
    [specialists]
  )

  const skillHits = useMemo(() => {
    if (!needle || !onPickSkill) return []
    return enabledSkills
      .filter(skill => {
        const haystack = `${skill.name} ${skill.description}`.toLowerCase()
        return haystack.includes(needle)
      })
      .slice(0, 8)
  }, [enabledSkills, needle, onPickSkill])

  const mainRows = useMemo<MainRowId[]>(() => {
    const rows: MainRowId[] = []
    if (onPlanModeChange) {
      rows.push('agent', 'plan')
    }
    rows.push('files')
    if (onPickSkill) rows.push('skills')
    if (onPickMcp) rows.push('mcp')
    if (onSpecialistSelect) rows.push('specialist')
    if (onSandboxBackendSelect) rows.push('sandbox')
    return rows
  }, [
    onPickMcp,
    onPickSkill,
    onPlanModeChange,
    onSandboxBackendSelect,
    onSpecialistSelect
  ])

  const placeMenu = () => {
    const button = triggerRef.current
    const form = button?.closest('form')
    if (!button || !form) return
    const buttonBox = button.getBoundingClientRect()
    const formBox = form.getBoundingClientRect()
    const availableWidth =
      typeof window !== 'undefined'
        ? Math.max(280, window.innerWidth - formBox.left - 284)
        : formBox.width
    setMenuWidth(Math.min(formBox.width, 360, availableWidth))
    setAlignOffset(formBox.left - buttonBox.left)
    setSideOffset(Math.max(8, buttonBox.top - formBox.top + 8))
  }

  const syncRowState = (row: MainRowId | null) => {
    setActiveRow(row)
    setInFlyout(false)
    setFlyoutIndex(0)
    if (
      row === 'skills' ||
      row === 'mcp' ||
      row === 'specialist' ||
      row === 'sandbox'
    ) {
      setFlyout(row)
    } else {
      setFlyout(null)
    }
  }

  const reveal = (next: PlusMenuFlyout) => {
    placeMenu()
    setActiveRow(next)
    setFlyout(next)
    setInFlyout(false)
    setFlyoutIndex(0)
    setOpen(true)
  }

  useEffect(() => {
    const queued = takeQueuedPlusMenu()
    if (queued) reveal(queued)
    const onOpen = (event: Event) => {
      const targetFlyout = (event as CustomEvent<{ flyout?: PlusMenuFlyout }>)
        .detail?.flyout
      if (targetFlyout) {
        window.requestAnimationFrame(() => reveal(targetFlyout))
      }
    }
    window.addEventListener(PLUS_MENU_OPEN_EVENT, onOpen)
    return () => window.removeEventListener(PLUS_MENU_OPEN_EVENT, onOpen)
  }, [])

  const close = () => {
    setOpen(false)
    setSearch('')
    setFlyout(null)
    setActiveRow(null)
    setInFlyout(false)
    setFlyoutIndex(0)
  }

  const flyoutItemCount = useMemo(() => {
    if (flyout === 'skills') return enabledSkills.length
    if (flyout === 'mcp') return mcpServers.length
    if (flyout === 'specialist') {
      return 1 + enabledSpecialists.length + (onCreateSpecialist ? 1 : 0)
    }
    return 0
  }, [
    enabledSkills.length,
    enabledSpecialists.length,
    flyout,
    mcpServers.length,
    onCreateSpecialist
  ])

  const triggerMainRow = (row: MainRowId) => {
    if (row === 'agent' && onPlanModeChange) {
      void onPlanModeChange(false)
      close()
    } else if (row === 'plan' && onPlanModeChange) {
      void onPlanModeChange(true)
      close()
    } else if (row === 'files') {
      uploadRef.current?.click()
      close()
    } else if (
      row === 'skills' ||
      row === 'mcp' ||
      row === 'specialist' ||
      row === 'sandbox'
    ) {
      setFlyout(row)
      if (row !== 'sandbox') {
        setInFlyout(true)
        setFlyoutIndex(0)
      }
    }
  }

  const triggerFlyoutItem = (idx: number) => {
    if (flyout === 'skills' && onPickSkill) {
      const target = enabledSkills[idx]
      if (target) {
        onPickSkill(target)
        close()
      }
    } else if (flyout === 'mcp' && onPickMcp) {
      const target = mcpServers[idx]
      if (target) {
        onPickMcp(target)
        close()
      }
    } else if (flyout === 'specialist' && onSpecialistSelect) {
      if (idx === 0) {
        void onSpecialistSelect(null)
        close()
      } else if (idx <= enabledSpecialists.length) {
        const spec = enabledSpecialists[idx - 1]
        if (spec) {
          void onSpecialistSelect(spec.id)
          close()
        }
      } else if (onCreateSpecialist) {
        close()
        onCreateSpecialist()
      }
    }
  }

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      close()
      return
    }

    if (needle) {
      if (skillHits.length === 0) return
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setSearchHitIndex(prev => (prev + 1) % skillHits.length)
      } else if (event.key === 'ArrowUp') {
        event.preventDefault()
        setSearchHitIndex(
          prev => (prev - 1 + skillHits.length) % skillHits.length
        )
      } else if (event.key === 'Enter') {
        event.preventDefault()
        const hit = skillHits[searchHitIndex] || skillHits[0]
        if (hit && onPickSkill) {
          onPickSkill(hit)
          close()
        }
      }
      return
    }

    if (inFlyout && flyout && flyout !== 'sandbox' && flyoutItemCount > 0) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setFlyoutIndex(prev => (prev + 1) % flyoutItemCount)
      } else if (event.key === 'ArrowUp') {
        event.preventDefault()
        setFlyoutIndex(prev => (prev - 1 + flyoutItemCount) % flyoutItemCount)
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault()
        setInFlyout(false)
      } else if (event.key === 'Enter') {
        event.preventDefault()
        triggerFlyoutItem(flyoutIndex)
      }
      return
    }

    if (mainRows.length === 0) return
    const currentIdx = activeRow ? mainRows.indexOf(activeRow) : -1

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      const nextIdx = currentIdx < 0 ? 0 : (currentIdx + 1) % mainRows.length
      syncRowState(mainRows[nextIdx] ?? null)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      const nextIdx =
        currentIdx <= 0 ? mainRows.length - 1 : currentIdx - 1
      syncRowState(mainRows[nextIdx] ?? null)
    } else if (event.key === 'ArrowRight') {
      if (
        activeRow &&
        (activeRow === 'skills' ||
          activeRow === 'mcp' ||
          activeRow === 'specialist') &&
        flyoutItemCount > 0
      ) {
        event.preventDefault()
        setFlyout(activeRow)
        setInFlyout(true)
        setFlyoutIndex(0)
      }
    } else if (event.key === 'Enter' && activeRow) {
      event.preventDefault()
      triggerMainRow(activeRow)
    }
  }

  return (
    <>
      <input
        ref={uploadRef}
        type="file"
        multiple
        hidden
        onChange={event => {
          if (event.target.files) onUpload(event.target.files)
          event.target.value = ''
        }}
      />
      <Popover
        open={open}
        onOpenChange={next => {
          if (next) {
            placeMenu()
            window.requestAnimationFrame(() => {
              searchInputRef.current?.focus()
            })
          }
          setOpen(next)
          if (!next) {
            setSearch('')
            setFlyout(null)
            setActiveRow(null)
            setInFlyout(false)
            setFlyoutIndex(0)
          }
        }}
      >
        <PopoverTrigger asChild>
          <button
            ref={triggerRef}
            type="button"
            className="bg-foreground/10 text-foreground hover:bg-foreground/15 inline-flex size-7 shrink-0 items-center justify-center rounded-full"
            aria-label="Add"
          >
            <Plus className="size-3.5" />
          </button>
        </PopoverTrigger>
        <PopoverContent
          side="top"
          align="start"
          alignOffset={alignOffset}
          sideOffset={sideOffset}
          avoidCollisions={false}
          className="z-[90] w-auto max-w-none overflow-visible border-0 bg-transparent p-0 shadow-none"
          onOpenAutoFocus={event => {
            event.preventDefault()
            searchInputRef.current?.focus()
          }}
        >
          <div className="relative" onKeyDown={handleKeyDown}>
            <div
              style={menuWidth ? { width: menuWidth } : undefined}
              className="sandwalk-glass-menu border-border/60 bg-popover/90 rounded-2xl border p-1.5 shadow-lg backdrop-blur-xl"
            >
              <input
                ref={searchInputRef}
                value={search}
                onChange={event => {
                  setSearch(event.target.value)
                  setSearchHitIndex(0)
                  setFlyout(null)
                  setActiveRow(null)
                  setInFlyout(false)
                }}
                onMouseEnter={() => syncRowState(null)}
                placeholder="Search skills, context, chats..."
                className="placeholder:text-muted-foreground w-full bg-transparent px-2.5 py-1.5 text-sm outline-none"
              />
              {needle ? (
                <div className="py-1">
                  {skillHits.length === 0 ? (
                    <div className="text-muted-foreground px-2.5 py-2 text-sm">
                      No matches
                    </div>
                  ) : (
                    skillHits.map((skill, idx) => (
                      <MenuRow
                        key={skill.name}
                        icon={<SkillIcon skill={skill} />}
                        label={skill.name}
                        detail={cleanSkillDescription(skill.description)}
                        active={idx === searchHitIndex}
                        onMouseEnter={() => setSearchHitIndex(idx)}
                        onClick={() => {
                          onPickSkill?.(skill)
                          close()
                        }}
                      />
                    ))
                  )}
                </div>
              ) : (
                <div className="py-0.5">
                  {onPlanModeChange ? (
                    <>
                      <MenuRow
                        icon={<InfinityIcon className={cnIcon(!planMode)} />}
                        label="Agent"
                        detail="Work with tools in this project"
                        active={activeRow === 'agent'}
                        onMouseEnter={() => syncRowState('agent')}
                        onClick={() => {
                          void onPlanModeChange(false)
                          close()
                        }}
                      />
                      <MenuRow
                        icon={
                          <ListChecks className="size-4 shrink-0 text-amber-500" />
                        }
                        label="Plan"
                        detail="Generate an implementation plan"
                        active={activeRow === 'plan'}
                        onMouseEnter={() => syncRowState('plan')}
                        onClick={() => {
                          void onPlanModeChange(true)
                          close()
                        }}
                      />
                      <div className="bg-border/60 my-1 h-px" />
                    </>
                  ) : null}
                  <MenuRow
                    icon={
                      <Paperclip className="text-muted-foreground size-4 shrink-0" />
                    }
                    label="Files"
                    active={activeRow === 'files'}
                    onMouseEnter={() => syncRowState('files')}
                    onClick={() => {
                      uploadRef.current?.click()
                      close()
                    }}
                  />
                  {onPickSkill ? (
                    <MenuRow
                      icon={
                        <Sparkles className="text-muted-foreground size-4 shrink-0" />
                      }
                      label="Skills"
                      trailing={<FlyoutChevron />}
                      active={activeRow === 'skills' || flyout === 'skills'}
                      onMouseEnter={() => syncRowState('skills')}
                      onClick={() => syncRowState('skills')}
                    />
                  ) : null}
                  {onPickMcp ? (
                    <MenuRow
                      icon={
                        <Plug className="text-muted-foreground size-4 shrink-0" />
                      }
                      label="MCP"
                      trailing={<FlyoutChevron />}
                      active={activeRow === 'mcp' || flyout === 'mcp'}
                      onMouseEnter={() => syncRowState('mcp')}
                      onClick={() => syncRowState('mcp')}
                    />
                  ) : null}
                  {onSpecialistSelect ? (
                    <MenuRow
                      icon={
                        selectedSpecialist ? (
                          <SpecialistAvatar
                            color={selectedSpecialist.color}
                            icon={selectedSpecialist.icon}
                            avatarUrl={selectedSpecialist.avatarUrl}
                            slug={selectedSpecialist.slug}
                            className="size-5"
                          />
                        ) : (
                          <GitBranch className="text-muted-foreground size-4 shrink-0" />
                        )
                      }
                      label="Specialist"
                      detail={selectedSpecialist?.name}
                      trailing={<FlyoutChevron />}
                      active={
                        activeRow === 'specialist' || flyout === 'specialist'
                      }
                      onMouseEnter={() => syncRowState('specialist')}
                      onClick={() => syncRowState('specialist')}
                    />
                  ) : null}
                  {onSandboxBackendSelect ? (
                    <MenuRow
                      icon={
                        <Container className="text-muted-foreground size-4 shrink-0" />
                      }
                      label="Sandbox"
                      trailing={<FlyoutChevron />}
                      active={activeRow === 'sandbox' || flyout === 'sandbox'}
                      onMouseEnter={() => syncRowState('sandbox')}
                      onClick={() => syncRowState('sandbox')}
                    />
                  ) : null}
                </div>
              )}
            </div>
            {flyout ? (
              <div className="sandwalk-glass-menu border-border/60 bg-popover/90 absolute bottom-0 left-full z-10 ml-2 overflow-hidden rounded-2xl border p-1 shadow-lg backdrop-blur-xl">
                <div className="chat-scrollbar max-h-72 overflow-x-hidden overflow-y-auto p-0.5">
                  {flyout === 'skills' && onPickSkill ? (
                    <SkillFlyout
                      skills={enabledSkills}
                      activeIndex={inFlyout ? flyoutIndex : -1}
                      onHoverIndex={idx => {
                        setInFlyout(true)
                        setFlyoutIndex(idx)
                      }}
                      onPick={skill => {
                        onPickSkill(skill)
                        close()
                      }}
                    />
                  ) : null}
                  {flyout === 'mcp' && onPickMcp ? (
                    <McpFlyout
                      servers={mcpServers}
                      activeIndex={inFlyout ? flyoutIndex : -1}
                      onHoverIndex={idx => {
                        setInFlyout(true)
                        setFlyoutIndex(idx)
                      }}
                      onPick={server => {
                        onPickMcp(server)
                        close()
                      }}
                    />
                  ) : null}
                  {flyout === 'specialist' && onSpecialistSelect ? (
                    <SpecialistFlyout
                      specialists={enabledSpecialists}
                      selectedSpecialistId={selectedSpecialistId}
                      activeIndex={inFlyout ? flyoutIndex : -1}
                      onHoverIndex={idx => {
                        setInFlyout(true)
                        setFlyoutIndex(idx)
                      }}
                      onSelect={id => {
                        void onSpecialistSelect(id)
                        close()
                      }}
                      onCreate={
                        onCreateSpecialist
                          ? () => {
                              close()
                              onCreateSpecialist()
                            }
                          : undefined
                      }
                      onManage={
                        onManageSpecialists
                          ? () => {
                              close()
                              onManageSpecialists()
                            }
                          : undefined
                      }
                    />
                  ) : null}
                  {flyout === 'sandbox' && onSandboxBackendSelect ? (
                    <ComposerSandboxPicker
                      embedded
                      sandboxStatus={sandboxStatus}
                      sandboxPhase={sandboxPhase}
                      onRequestClose={close}
                      onSandboxBackendSelect={onSandboxBackendSelect}
                      onSandboxComputeChange={onSandboxComputeChange}
                      onSandboxStart={onSandboxStart}
                      onSandboxStop={onSandboxStop}
                      onSandboxRestart={onSandboxRestart}
                      onLoadLocalSystem={onLoadLocalSystem}
                      onRefreshSandbox={onRefreshSandbox}
                    />
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        </PopoverContent>
      </Popover>
    </>
  )
}

function cnIcon(active: boolean) {
  return active
    ? 'text-foreground size-4 shrink-0'
    : 'text-muted-foreground size-4 shrink-0'
}

function FlyoutChevron() {
  return <ChevronRight className="text-muted-foreground ml-auto size-4" />
}

function SkillIcon({ skill }: { skill: AgentSkill }) {
  const src = composerSkillIcon(skill)
  if (!src) {
    return (
      <span className="bg-primary/10 text-primary inline-flex size-[18px] shrink-0 items-center justify-center rounded">
        <Sparkles className="size-3" />
      </span>
    )
  }
  return (
    <img
      src={src}
      alt=""
      className={cn(
        'size-[18px] shrink-0 rounded object-contain',
        skillIconInvertInDark(skill) && 'dark:invert'
      )}
    />
  )
}

function McpIcon({ server }: { server: McpServer }) {
  const icon = mcpIconForServer(server)
  if (!icon) {
    return (
      <span className="bg-muted text-muted-foreground inline-flex size-[18px] shrink-0 items-center justify-center rounded">
        <Plug className="size-3" />
      </span>
    )
  }
  return (
    <img
      src={icon.src}
      alt=""
      className={cn(
        'size-[18px] shrink-0 rounded object-contain',
        icon.invertInDark && 'dark:invert'
      )}
    />
  )
}

function SkillFlyout({
  skills,
  activeIndex,
  onHoverIndex,
  onPick
}: {
  skills: AgentSkill[]
  activeIndex: number
  onHoverIndex: (index: number) => void
  onPick: (skill: AgentSkill) => void
}) {
  if (skills.length === 0) {
    return (
      <div className="text-muted-foreground w-56 px-2.5 py-2 text-sm">
        No skills
      </div>
    )
  }
  return (
    <div className="w-64">
      <div className="flex items-center justify-between px-2.5 py-1">
        <span className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
          Skills
        </span>
      </div>
      {skills.map((skill, idx) => (
        <button
          key={skill.name}
          type="button"
          onMouseEnter={() => onHoverIndex(idx)}
          className={cn(
            'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left transition-colors',
            idx === activeIndex && 'bg-foreground/[0.07] dark:bg-white/[0.1]'
          )}
          onClick={() => onPick(skill)}
        >
          <SkillIcon skill={skill} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">{skill.name}</span>
            <span className="text-muted-foreground block truncate text-xs">
              {cleanSkillDescription(skill.description) || skill.name}
            </span>
          </span>
        </button>
      ))}
    </div>
  )
}

function McpFlyout({
  servers,
  activeIndex,
  onHoverIndex,
  onPick
}: {
  servers: McpServer[]
  activeIndex: number
  onHoverIndex: (index: number) => void
  onPick: (server: McpServer) => void
}) {
  if (servers.length === 0) {
    return (
      <div className="text-muted-foreground w-56 px-2.5 py-2 text-sm">
        No MCP servers
      </div>
    )
  }
  return (
    <div className="w-64">
      <div className="flex items-center justify-between px-2.5 py-1">
        <span className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
          MCP Servers
        </span>
      </div>
      {servers.map((server, idx) => (
        <button
          key={server.id}
          type="button"
          onMouseEnter={() => onHoverIndex(idx)}
          className={cn(
            'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left transition-colors',
            idx === activeIndex && 'bg-foreground/[0.07] dark:bg-white/[0.1]'
          )}
          onClick={() => onPick(server)}
        >
          <McpIcon server={server} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">{server.name}</span>
            <span className="text-muted-foreground block truncate text-xs">
              {String(server.description || '').trim() || server.transport}
            </span>
          </span>
        </button>
      ))}
    </div>
  )
}

function SpecialistFlyout({
  specialists,
  selectedSpecialistId,
  activeIndex,
  onHoverIndex,
  onSelect,
  onCreate,
  onManage
}: {
  specialists: Specialist[]
  selectedSpecialistId: string | null
  activeIndex: number
  onHoverIndex: (index: number) => void
  onSelect: (id: string | null) => void
  onCreate?: () => void
  onManage?: () => void
}) {
  return (
    <div className="w-64">
      <div className="flex items-center justify-between px-2.5 py-1">
        <span className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
          Specialist
        </span>
        {onManage ? (
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground text-[11px] transition-colors"
            onClick={onManage}
          >
            Manage
          </button>
        ) : null}
      </div>
      <button
        type="button"
        onMouseEnter={() => onHoverIndex(0)}
        className={cn(
          'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors',
          activeIndex === 0
            ? 'bg-foreground/[0.07] dark:bg-white/[0.1]'
            : !selectedSpecialistId && 'bg-foreground/[0.04] dark:bg-white/[0.05]'
        )}
        onClick={() => onSelect(null)}
      >
        <span className="border-border/70 bg-muted/40 flex size-6 shrink-0 items-center justify-center rounded-full border">
          <span className="bg-muted-foreground/50 size-2 rounded-full" />
        </span>
        <span className="flex-1 truncate font-medium">None</span>
        {!selectedSpecialistId ? <Check className="size-3.5 shrink-0" /> : null}
      </button>
      {specialists.map((item, idx) => {
        const isSelected = item.id === selectedSpecialistId
        const rowIndex = idx + 1
        return (
          <button
            key={item.id}
            type="button"
            onMouseEnter={() => onHoverIndex(rowIndex)}
            className={cn(
              'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors',
              activeIndex === rowIndex
                ? 'bg-foreground/[0.07] dark:bg-white/[0.1]'
                : isSelected && 'bg-foreground/[0.04] dark:bg-white/[0.05]'
            )}
            onClick={() => onSelect(item.id)}
          >
            <SpecialistAvatar
              color={item.color}
              icon={item.icon}
              avatarUrl={item.avatarUrl}
              slug={item.slug}
              className="size-6"
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">
                {item.name}
              </span>
              {item.roleLabel && item.roleLabel !== item.name ? (
                <span className="text-muted-foreground block truncate text-[11px]">
                  {item.roleLabel}
                </span>
              ) : null}
            </span>
            {isSelected ? <Check className="size-3.5 shrink-0" /> : null}
          </button>
        )
      })}
      {onCreate ? (
        <button
          type="button"
          onMouseEnter={() => onHoverIndex(specialists.length + 1)}
          className={cn(
            'mt-0.5 flex w-full items-center gap-2.5 rounded-lg border-t border-border/50 px-2.5 pt-2 pb-1.5 text-left text-sm transition-colors',
            activeIndex === specialists.length + 1 &&
              'bg-foreground/[0.07] dark:bg-white/[0.1]'
          )}
          onClick={onCreate}
        >
          <Plus className="size-3.5" />
          Create new…
        </button>
      ) : null}
    </div>
  )
}

function MenuRow({
  icon,
  label,
  detail,
  trailing,
  active,
  onClick,
  onMouseEnter
}: {
  icon: ReactNode
  label: string
  detail?: string
  trailing?: ReactNode
  active?: boolean
  onClick?: () => void
  onMouseEnter?: () => void
}) {
  return (
    <button
      type="button"
      className={cn(
        'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left transition-colors',
        active && 'bg-foreground/[0.07] dark:bg-white/[0.1]'
      )}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
    >
      {icon}
      <span className="shrink-0 text-sm font-medium">{label}</span>
      {detail ? (
        <span className="text-muted-foreground min-w-0 truncate text-sm font-normal">
          {detail}
        </span>
      ) : null}
      {trailing}
    </button>
  )
}
