import type { AgentSkill, IntegrationUnlock } from '@sandwalk/agent-ui-core'
import { Box, CircleAlert, Loader, Puzzle } from 'lucide-react'
import type { ReactNode } from 'react'

import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { Button } from '@/components/ui/button'
import {
  featuredSkillIcon,
  isFeaturedSkill,
  skillIcon,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import { cn } from '@/lib/utils'

function capabilityIcon(unlock: IntegrationUnlock): ReactNode {
  if (unlock.id === 'slack-relay-agent' || unlock.id.startsWith('slack')) {
    return (
      <img
        src={INTEGRATION_ICONS.slack.src}
        alt=""
        className="size-5 shrink-0 object-contain"
      />
    )
  }
  if (
    unlock.id === 'npx-skills-cli' ||
    unlock.id === 'skills-sh-catalog' ||
    unlock.id.startsWith('skills-sh')
  ) {
    return (
      <img
        src={INTEGRATION_ICONS['skills-sh'].src}
        alt=""
        className={cn(
          'size-5 shrink-0 object-contain',
          INTEGRATION_ICONS['skills-sh'].invertInDark && 'dark:invert'
        )}
      />
    )
  }
  if (unlock.kind === 'notice') {
    return <CircleAlert className="text-muted-foreground size-5 shrink-0" />
  }
  return <Puzzle className="text-muted-foreground size-5 shrink-0" />
}

function requirementLabel(unlock: IntegrationUnlock) {
  if (unlock.requirement === 'connector') return 'Connected workspace'
  if (unlock.requirement === 'ambient') return 'Platform capability'
  if (unlock.requirement === 'not_wired') return 'Not wired'
  if (unlock.requirement === 'install') return 'Installation required'
  return 'Built in'
}

function DotStatus({
  label,
  tone = 'neutral',
  title
}: {
  label: string
  tone?: 'neutral' | 'ok' | 'warn'
  title?: string | null
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 text-xs font-medium',
        tone === 'neutral' && 'text-muted-foreground',
        tone === 'ok' && 'text-sky-700 dark:text-sky-300',
        tone === 'warn' && 'text-amber-700 dark:text-amber-300'
      )}
      title={title || undefined}
    >
      <span
        className={cn(
          'size-1.5 shrink-0 rounded-full',
          tone === 'neutral' && 'bg-muted-foreground/50',
          tone === 'ok' && 'bg-sky-500',
          tone === 'warn' && 'bg-amber-500'
        )}
        aria-hidden
      />
      {label}
    </span>
  )
}

export function SkillUnlockRow({
  unlock,
  skill,
  busy,
  onInstall,
  onEnable,
  onOpen
}: {
  unlock: IntegrationUnlock
  skill: AgentSkill | null
  busy: boolean
  onInstall: () => void
  onEnable: () => void
  onOpen: () => void
}) {
  const presentation = skill || {
    name: unlock.id,
    iconSrc: null,
    author: '',
    source: unlock.source || ''
  }
  const icon = isFeaturedSkill(presentation)
    ? featuredSkillIcon(presentation)
    : skillIcon(presentation)
  const action = !skill ? 'install' : skill.enabled ? null : 'enable'
  return (
    <div className="flex items-start justify-between gap-3 px-4 py-3">
      <button
        type="button"
        className="min-w-0 flex-1 text-left"
        onClick={onOpen}
      >
        <div className="flex flex-wrap items-center gap-2">
          {icon ? (
            <img
              src={icon}
              alt=""
              className={cn(
                'size-5 shrink-0 rounded object-contain',
                skillIconInvertInDark(presentation) && 'dark:invert'
              )}
            />
          ) : (
            <Box className="text-muted-foreground size-5 shrink-0" />
          )}
          <span className="font-mono text-sm font-medium">{unlock.id}</span>
          <span className="text-muted-foreground text-xs">Skill</span>
          <DotStatus
            tone={skill ? (skill.enabled ? 'ok' : 'neutral') : 'warn'}
            label={
              skill
                ? skill.enabled
                  ? 'Installed · Enabled'
                  : 'Installed · Disabled'
                : 'Not installed'
            }
          />
        </div>
        <p className="text-muted-foreground mt-1 pl-7 text-sm">
          {unlock.description}
        </p>
      </button>
      {action ? (
        <Button
          type="button"
          size="sm"
          disabled={busy || (action === 'install' && !unlock.source)}
          onClick={action === 'install' ? onInstall : onEnable}
        >
          {busy ? <Loader className="animate-spin" /> : null}
          {busy
            ? action === 'install'
              ? 'Installing…'
              : 'Enabling…'
            : action === 'install'
            ? 'Install'
            : 'Enable'}
        </Button>
      ) : null}
    </div>
  )
}

export function CapabilityUnlockRow({
  unlock,
  busy = false,
  onInstall,
  onOpen
}: {
  unlock: IntegrationUnlock
  busy?: boolean
  onInstall?: () => void
  onOpen?: () => void
}) {
  const status =
    unlock.installed === true
      ? { label: 'Installed', tone: 'ok' as const }
      : unlock.installed === false
      ? { label: 'Not installed', tone: 'warn' as const }
      : { label: requirementLabel(unlock), tone: 'neutral' as const }
  const body = (
    <>
      <div className="flex flex-wrap items-center gap-2">
        {capabilityIcon(unlock)}
        <span className="text-sm font-medium">{unlock.label}</span>
        <DotStatus
          label={status.label}
          tone={status.tone}
          title={unlock.statusDetail}
        />
      </div>
      <p className="text-muted-foreground mt-1 pl-7 text-sm">
        {unlock.description}
      </p>
    </>
  )
  return (
    <div className="flex items-start justify-between gap-3 px-4 py-3">
      {onOpen ? (
        <button
          type="button"
          className="min-w-0 flex-1 text-left"
          onClick={onOpen}
        >
          {body}
        </button>
      ) : (
        <div className="min-w-0 flex-1">{body}</div>
      )}
      {unlock.installable && unlock.installed !== true && onInstall ? (
        <Button type="button" size="sm" disabled={busy} onClick={onInstall}>
          {busy ? <Loader className="animate-spin" /> : null}
          {busy ? 'Installing…' : 'Install'}
        </Button>
      ) : null}
    </div>
  )
}
