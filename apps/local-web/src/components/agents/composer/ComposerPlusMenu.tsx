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
import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react'

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
import {
  specialistColorClass,
  SpecialistGlyph
} from '@/components/agents/SpecialistsView'
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
  const [open, setOpen] = useState(false)
  const [menuWidth, setMenuWidth] = useState<number | undefined>()
  const [sideOffset, setSideOffset] = useState(8)
  const [alignOffset, setAlignOffset] = useState(0)
  const [search, setSearch] = useState('')
  const [flyout, setFlyout] = useState<
    'skills' | 'mcp' | 'specialist' | 'sandbox' | null
  >(null)
  const planMode = Boolean(runtimeSettings?.planMode)
  const needle = search.trim().toLowerCase()

  const skillHits = useMemo(() => {
    if (!needle || !onPickSkill) return []
    return skills
      .filter(skill => skill.enabled)
      .filter(skill => {
        const haystack = `${skill.name} ${skill.description}`.toLowerCase()
        return haystack.includes(needle)
      })
      .slice(0, 8)
  }, [needle, onPickSkill, skills])

  const placeMenu = () => {
    const button = triggerRef.current
    const form = button?.closest('form')
    if (!button || !form) return
    const buttonBox = button.getBoundingClientRect()
    const formBox = form.getBoundingClientRect()
    setMenuWidth(formBox.width)
    setAlignOffset(formBox.left - buttonBox.left)
    setSideOffset(Math.max(8, buttonBox.top - formBox.top + 8))
  }

  const reveal = (next: PlusMenuFlyout) => {
    placeMenu()
    setFlyout(next)
    setOpen(true)
  }

  useEffect(() => {
    const queued = takeQueuedPlusMenu()
    if (queued) reveal(queued)
    const onOpen = (event: Event) => {
      const flyout = (event as CustomEvent<{ flyout?: PlusMenuFlyout }>).detail
        ?.flyout
      if (flyout) reveal(flyout)
    }
    window.addEventListener(PLUS_MENU_OPEN_EVENT, onOpen)
    return () => window.removeEventListener(PLUS_MENU_OPEN_EVENT, onOpen)
  }, [])

  const close = () => {
    setOpen(false)
    setSearch('')
    setFlyout(null)
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
          if (next) placeMenu()
          setOpen(next)
          if (!next) {
            setSearch('')
            setFlyout(null)
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
          style={menuWidth ? { width: menuWidth } : undefined}
          className="z-[90] w-auto max-w-none overflow-visible rounded-xl p-1.5"
          onOpenAutoFocus={event => event.preventDefault()}
        >
          <div className="relative">
            <input
              value={search}
              onChange={event => {
                setSearch(event.target.value)
                setFlyout(null)
              }}
              placeholder="Search skills, context, chats..."
              className="placeholder:text-muted-foreground w-full bg-transparent px-2 py-1.5 text-sm outline-none"
            />
            {needle ? (
              <div className="py-1">
                {skillHits.length === 0 ? (
                  <div className="text-muted-foreground px-2 py-2 text-sm">
                    No matches
                  </div>
                ) : (
                  skillHits.map(skill => (
                    <MenuRow
                      key={skill.name}
                      icon={<SkillIcon skill={skill} />}
                      label={skill.name}
                      detail={cleanSkillDescription(skill.description)}
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
                      icon={
                        <InfinityIcon
                          className={cnIcon(!planMode)}
                        />
                      }
                      label="Agent"
                      detail="Work with tools in this project"
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
                      onClick={() => {
                        void onPlanModeChange(true)
                        close()
                      }}
                    />
                    <div className="bg-border my-1 h-px" />
                  </>
                ) : null}
                <MenuRow
                  icon={<Paperclip className="text-muted-foreground size-4 shrink-0" />}
                  label="Files"
                  onClick={() => {
                    uploadRef.current?.click()
                    close()
                  }}
                />
                {onPickSkill ? (
                  <MenuRow
                    icon={<Sparkles className="text-muted-foreground size-4 shrink-0" />}
                    label="Skills"
                    trailing={<FlyoutChevron />}
                    active={flyout === 'skills'}
                    onMouseEnter={() => setFlyout('skills')}
                  />
                ) : null}
                {onPickMcp ? (
                  <MenuRow
                    icon={<Plug className="text-muted-foreground size-4 shrink-0" />}
                    label="MCP"
                    trailing={<FlyoutChevron />}
                    active={flyout === 'mcp'}
                    onMouseEnter={() => setFlyout('mcp')}
                  />
                ) : null}
                {onSpecialistSelect ? (
                  <MenuRow
                    icon={<GitBranch className="text-muted-foreground size-4 shrink-0" />}
                    label="Specialist"
                    trailing={<FlyoutChevron />}
                    active={flyout === 'specialist'}
                    onMouseEnter={() => setFlyout('specialist')}
                  />
                ) : null}
                {onSandboxBackendSelect ? (
                  <MenuRow
                    icon={<Container className="text-muted-foreground size-4 shrink-0" />}
                    label="Sandbox"
                    trailing={<FlyoutChevron />}
                    active={flyout === 'sandbox'}
                    onMouseEnter={() => setFlyout('sandbox')}
                  />
                ) : null}
              </div>
            )}
            {flyout ? (
              <div className="bg-popover absolute top-8 left-full z-10 ml-2 max-h-72 overflow-y-auto rounded-xl border p-1 shadow-md">
                {flyout === 'skills' && onPickSkill ? (
                  <SkillFlyout
                    skills={skills.filter(skill => skill.enabled)}
                    onPick={skill => {
                      onPickSkill(skill)
                      close()
                    }}
                  />
                ) : null}
                {flyout === 'mcp' && onPickMcp ? (
                  <McpFlyout
                    servers={mcpServers}
                    onPick={server => {
                      onPickMcp(server)
                      close()
                    }}
                  />
                ) : null}
                {flyout === 'specialist' && onSpecialistSelect ? (
                  <SpecialistFlyout
                    specialists={specialists}
                    selectedSpecialistId={selectedSpecialistId}
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
  onPick
}: {
  skills: AgentSkill[]
  onPick: (skill: AgentSkill) => void
}) {
  if (skills.length === 0) {
    return (
      <div className="text-muted-foreground w-56 px-2 py-2 text-sm">No skills</div>
    )
  }
  return (
    <div className="w-64">
      {skills.map(skill => (
        <button
          key={skill.name}
          type="button"
          className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left"
          onClick={() => onPick(skill)}
        >
          <SkillIcon skill={skill} />
          <span className="min-w-0">
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
  onPick
}: {
  servers: McpServer[]
  onPick: (server: McpServer) => void
}) {
  if (servers.length === 0) {
    return (
      <div className="text-muted-foreground w-56 px-2 py-2 text-sm">
        No MCP servers
      </div>
    )
  }
  return (
    <div className="w-64">
      {servers.map(server => (
        <button
          key={server.id}
          type="button"
          className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left"
          onClick={() => onPick(server)}
        >
          <McpIcon server={server} />
          <span className="min-w-0">
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
  onSelect,
  onCreate,
  onManage
}: {
  specialists: Specialist[]
  selectedSpecialistId: string | null
  onSelect: (id: string | null) => void
  onCreate?: () => void
  onManage?: () => void
}) {
  return (
    <div className="w-64">
      <div className="flex items-center justify-between px-2 py-1">
        <span className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
          Specialist
        </span>
        {onManage ? (
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground text-[11px]"
            onClick={onManage}
          >
            Manage
          </button>
        ) : null}
      </div>
      <button
        type="button"
        className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
        onClick={() => onSelect(null)}
      >
        <span className="bg-muted-foreground/40 size-2.5 shrink-0 rounded-full" />
        <span className="flex-1 truncate">None</span>
        {!selectedSpecialistId ? <Check className="size-3.5" /> : null}
      </button>
      {specialists
        .filter(item => item.enabled !== false)
        .map(item => (
          <button
            key={item.id}
            type="button"
            className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
            onClick={() => onSelect(item.id)}
          >
            <span
              className={cn(
                'flex size-4 shrink-0 items-center justify-center rounded-full text-white [&_svg]:text-white',
                specialistColorClass(item.color)
              )}
            >
              <SpecialistGlyph icon={item.icon} className="size-2.5" />
            </span>
            <span className="min-w-0 flex-1 truncate">{item.name}</span>
            {item.id === selectedSpecialistId ? (
              <Check className="size-3.5" />
            ) : null}
          </button>
        ))}
      {onCreate ? (
        <button
          type="button"
          className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
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
        'hover:bg-muted flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left',
        active && 'bg-muted'
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
