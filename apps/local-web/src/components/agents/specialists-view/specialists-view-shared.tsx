import type { AgentSkill, McpServer } from '@sandwalk/agent-ui-core'
import { Plug, Sparkles } from 'lucide-react'

import {
  composerSkillIcon,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import { cn } from '@/lib/utils'

const MCP_ICONS: Record<string, { src: string; invertInDark?: boolean }> = {
  tamarind: { src: '/integrations/tamarind.png' },
  latch: { src: '/integrations/latch.png' },
  neurosnap: { src: '/integrations/neurosnap.png' },
  paperclip: { src: '/integrations/paperclip.png' },
  huggingface: { src: '/integrations/huggingface.png' },
  linear: { src: '/integrations/linear.png' }
}

export function skillMetaText(skill: AgentSkill): string | null {
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

export function mcpMetaText(server: McpServer): string | null {
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

export function McpGlyph({
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

export function SkillGlyph({
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

export function SpecialistToggle({
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
