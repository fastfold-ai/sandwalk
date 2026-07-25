import type { AgentSession } from '@sandwalk/agent-ui-core'

import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'

/** Badge marking a session that a connector started, e.g. a Slack mention. */
export function SessionSourceIcon({
  source,
  label
}: {
  source: AgentSession['source']
  label?: string | null
}) {
  if (source !== 'slack') return null
  return (
    <img
      src={INTEGRATION_ICONS.slack.src}
      alt=""
      title={label ? `From Slack · ${label}` : 'From Slack'}
      className="size-3 shrink-0 rounded-[2px] object-contain"
    />
  )
}
