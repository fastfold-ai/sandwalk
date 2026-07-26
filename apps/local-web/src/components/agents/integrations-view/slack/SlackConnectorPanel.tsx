import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSession,
  SlackSubscription,
  SlackWorkspace
} from '@sandwalk/agent-ui-core'
import { Loader2, Plus } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { Button } from '@/components/ui/button'

import { SlackAddWorkspaceModal } from './SlackAddWorkspaceModal'
import { SlackHowItWorks } from './SlackHowItWorks'
import { SlackParkedQueue } from './SlackParkedQueue'
import { SlackWorkspaceCard } from './SlackWorkspaceCard'
import { useSlackConnector } from './use-slack-connector'

export function SlackConnectorPanel({
  client,
  sessions
}: {
  client: LocalAgentClient
  sessions: AgentSession[]
}) {
  const slack = useSlackConnector(client)
  const [addOpen, setAddOpen] = useState(false)
  const [updating, setUpdating] = useState<SlackWorkspace | null>(null)
  const [subscriptions, setSubscriptions] = useState<SlackSubscription[]>([])

  const loadSubscriptions = useCallback(async () => {
    try {
      const result = await client.listSlackSubscriptions()
      setSubscriptions(result.data)
    } catch {
      setSubscriptions([])
    }
  }, [client])

  useEffect(() => {
    void loadSubscriptions()
  }, [loadSubscriptions, slack.status])

  const workspaces = slack.status?.workspaces ?? []
  const connected = workspaces.length > 0
  // One shared relay connection serves every relay-mode workspace, so this
  // only matters for those cards — shown there instead of as a global
  // summary, since a socket-mode workspace couldn't care less about it.
  const relayState = slack.status?.relayState ?? 'off'

  const run = async (operation: () => Promise<unknown>) => {
    const ok = await slack.act(operation)
    if (ok) await loadSubscriptions()
    return ok
  }

  if (slack.loading) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 py-10 text-[13px]">
        <Loader2 className="size-4 animate-spin" />
        Loading Slack…
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-3">
        <Button
          size="sm"
          className="h-8 gap-1.5"
          onClick={() => {
            setUpdating(null)
            setAddOpen(true)
          }}
        >
          <Plus className="size-3.5" />
          Add workspace
        </Button>
      </div>

      {slack.error ? (
        <p className="text-destructive text-[13px]">{slack.error}</p>
      ) : null}

      <SlackHowItWorks />

      <SlackParkedQueue
        parked={slack.parked}
        busy={slack.busy}
        onAllow={id => void run(() => client.allowSlackParked(id))}
        onDismiss={id => void run(() => client.dismissSlackParked(id))}
      />

      {connected ? (
        workspaces.map(workspace => (
          <SlackWorkspaceCard
            key={workspace.teamId}
            workspace={workspace}
            people={slack.people[workspace.teamId] ?? []}
            directory={slack.directories[workspace.teamId] ?? null}
            subscriptions={subscriptions}
            sessions={sessions}
            busy={slack.busy}
            onAllowPerson={(teamId, slackUserId, displayName) =>
              void run(() =>
                client.allowSlackPerson({ teamId, slackUserId, displayName })
              )
            }
            onDisallowPerson={(teamId, slackUserId) =>
              void run(() => client.disallowSlackPerson(teamId, slackUserId))
            }
            onAddSubscription={(sessionId, channel) =>
              void run(() =>
                client.addSlackSubscription({ sessionId, channel })
              )
            }
            onRemoveSubscription={(sessionId, channel) =>
              void run(() => client.removeSlackSubscription(sessionId, channel))
            }
            onUpdateTokens={target => {
              setUpdating(target)
              setAddOpen(true)
            }}
            onDisconnect={teamId =>
              void run(() => client.disconnectSlackWorkspace(teamId))
            }
            onSetEnabled={(teamId, enabled) =>
              void run(() => client.setSlackWorkspaceEnabled(teamId, enabled))
            }
            relayState={relayState}
          />
        ))
      ) : (
        <div className="border-border/70 text-muted-foreground flex flex-col items-center gap-3 rounded-xl border border-dashed py-12 text-center">
          <img
            src={INTEGRATION_ICONS.slack.src}
            alt=""
            className="size-8 object-contain opacity-60"
          />
          <div>
            <p className="text-foreground text-[14px] font-medium">
              No workspace connected
            </p>
            <p className="mt-1 max-w-sm text-[13px]">
              Connect a Slack workspace so mentions open a session here and the
              answer goes back as a thread reply.
            </p>
          </div>
        </div>
      )}

      <SlackAddWorkspaceModal
        open={addOpen}
        client={client}
        busy={slack.busy}
        updatingWorkspace={
          updating ? updating.teamName || updating.teamId : null
        }
        onOpenChange={next => {
          setAddOpen(next)
          if (!next) setUpdating(null)
        }}
        onImported={() => void run(async () => undefined)}
        onConnect={input =>
          run(() =>
            client.connectSlackManual({
              botToken: input.botToken.trim(),
              appToken: input.appToken.trim()
            })
          )
        }
      />
    </div>
  )
}
