import type { AgentSession } from '@sandwalk/agent-ui-core'

import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'

import {
  EXTERNAL_AGENT_LABELS,
  ExternalAgentIcon,
  isExternalAgentKind
} from './ExternalAgentIcon'

/**
 * Badge marking where a session came from: a Slack mention, or an import
 * from another coding-agent CLI (Claude Code, Codex, OpenCode, fx).
 */
export function SessionSourceIcon({
  source,
  label
}: {
  source: AgentSession['source']
  label?: string | null
}) {
  if (source === 'slack') {
    return (
      <img
        src={INTEGRATION_ICONS.slack.src}
        alt=""
        title={label ? `From Slack · ${label}` : 'From Slack'}
        className="size-3 shrink-0 rounded-[2px] object-contain"
      />
    )
  }
  if (isExternalAgentKind(source)) {
    const name = EXTERNAL_AGENT_LABELS[source]
    return (
      <span
        title={label ? `Imported from ${label}` : `Imported from ${name}`}
        className="contents"
      >
        <ExternalAgentIcon kind={source} className="text-muted-foreground size-3" />
      </span>
    )
  }
  return null
}
