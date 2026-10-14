import { SquareTerminal } from 'lucide-react'

import { useTerminalsStore } from '@/lib/terminals-store'
import { cn } from '@/lib/utils'

import { EXTERNAL_AGENT_LABELS, ExternalAgentIcon } from './ExternalAgentIcon'

/**
 * Terminal chip / sidebar icon. Plain shell: orange terminal glyph. While a
 * coding-agent CLI (Claude Code, Codex, OpenCode, fx) is in the foreground
 * of that PTY, the agent's own mark replaces it — the same cue Warp gives.
 */
export function TerminalTypeIcon({
  terminalId,
  className
}: {
  terminalId: string
  className?: string
}) {
  const agent = useTerminalsStore(
    state => state.terminals.find(t => t.id === terminalId)?.agent ?? null
  )
  if (agent) {
    return (
      <span title={EXTERNAL_AGENT_LABELS[agent]} className="contents">
        <ExternalAgentIcon
          kind={agent}
          className={cn('text-foreground/80', className)}
        />
      </span>
    )
  }
  return (
    <SquareTerminal
      className={cn('size-3.5 shrink-0 text-orange-500', className)}
      aria-hidden
    />
  )
}
