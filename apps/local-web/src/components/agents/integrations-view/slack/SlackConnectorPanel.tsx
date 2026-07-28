import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSession,
  SlackSubscription,
  SlackWorkspace
} from '@sandwalk/agent-ui-core'
import { Loader2 } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { openInSystemBrowser } from '@/lib/desktop'

import { SLACK_ADD_HEADER_SLOT_ID } from '../integrations-view-detail-header'
import {
  SlackAddSplitButton,
  SlackOneClickDialog
} from './SlackAddSplitButton'
import { SlackAddWorkspaceModal } from './SlackAddWorkspaceModal'
import { SlackHowItWorks } from './SlackHowItWorks'
import { SlackParkedQueue } from './SlackParkedQueue'
import { SlackWorkspaceCard } from './SlackWorkspaceCard'
import { useSlackConnector } from './use-slack-connector'

const ONE_CLICK_TIMEOUT_MS = 5 * 60 * 1000
const ONE_CLICK_POLL_MS = 2000

export function SlackConnectorPanel({
  client,
  sessions
}: {
  client: LocalAgentClient
  sessions: AgentSession[]
}) {
  const slack = useSlackConnector(client)
  const [manualOpen, setManualOpen] = useState(false)
  const [updating, setUpdating] = useState<SlackWorkspace | null>(null)
  const [subscriptions, setSubscriptions] = useState<SlackSubscription[]>([])
  const [oneClickOpen, setOneClickOpen] = useState(false)
  const [oneClickWaiting, setOneClickWaiting] = useState(false)
  const [oneClickError, setOneClickError] = useState<string | null>(null)
  const [headerSlot, setHeaderSlot] = useState<Element | null>(null)
  const oneClickCancelledRef = useRef(false)

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

  useEffect(() => {
    oneClickCancelledRef.current = !oneClickOpen
    if (oneClickOpen) return
    setOneClickWaiting(false)
    setOneClickError(null)
  }, [oneClickOpen])

  useEffect(() => {
    setHeaderSlot(document.getElementById(SLACK_ADD_HEADER_SLOT_ID))
  }, [])

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

  const openManual = () => {
    setUpdating(null)
    setManualOpen(true)
  }

  const startOneClick = async () => {
    setOneClickError(null)
    setOneClickOpen(true)
    setOneClickWaiting(true)
    let authUrl: string
    try {
      authUrl = (await client.startSlackOneClick()).authUrl
    } catch (cause) {
      setOneClickWaiting(false)
      setOneClickError(
        cause instanceof Error
          ? cause.message
          : 'Could not start the Slack install.'
      )
      return
    }

    openInSystemBrowser(authUrl)
    const deadline = Date.now() + ONE_CLICK_TIMEOUT_MS
    while (Date.now() < deadline) {
      await new Promise(resolve => window.setTimeout(resolve, ONE_CLICK_POLL_MS))
      if (oneClickCancelledRef.current) return
      try {
        const result = await client.importSlackOneClick()
        if (result.data.length > 0) {
          setOneClickWaiting(false)
          await run(async () => undefined)
          setOneClickOpen(false)
          return
        }
      } catch {
        // Transient while the user is still in the browser; keep polling.
      }
    }
    setOneClickWaiting(false)
    setOneClickError(
      'No workspace arrived. Finish the approval in Slack and try again.'
    )
  }

  const addPortal =
    headerSlot != null
      ? createPortal(
          <SlackAddSplitButton
            busy={slack.busy}
            waiting={oneClickWaiting}
            onAddToSlack={() => void startOneClick()}
            onOpenManual={openManual}
          />,
          headerSlot
        )
      : null

  if (slack.loading) {
    return (
      <>
        {addPortal}
        <div className="text-muted-foreground flex items-center gap-2 py-10 text-[13px]">
          <Loader2 className="size-4 animate-spin" />
          Loading Slack…
        </div>
      </>
    )
  }

  return (
    <div className="space-y-4">
      {addPortal}
      <SlackHowItWorks />

      {slack.error ? (
        <p className="text-destructive text-[13px]">{slack.error}</p>
      ) : null}

      <SlackParkedQueue
        parked={slack.parked}
        busy={slack.busy}
        onAllow={id => void run(() => client.allowSlackParked(id))}
        onDismiss={id => void run(() => client.dismissSlackParked(id))}
      />

      <section className="space-y-2">
        <h3 className="text-sm font-medium">Connections</h3>
        {connected ? (
          <div className="space-y-4">
            {workspaces.map(workspace => (
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
                    client.allowSlackPerson({
                      teamId,
                      slackUserId,
                      displayName
                    })
                  )
                }
                onDisallowPerson={(teamId, slackUserId) =>
                  void run(() =>
                    client.disallowSlackPerson(teamId, slackUserId)
                  )
                }
                onAddSubscription={(sessionId, channel) =>
                  void run(() =>
                    client.addSlackSubscription({ sessionId, channel })
                  )
                }
                onRemoveSubscription={(sessionId, channel) =>
                  void run(() =>
                    client.removeSlackSubscription(sessionId, channel)
                  )
                }
                onUpdateTokens={target => {
                  setUpdating(target)
                  setManualOpen(true)
                }}
                onDisconnect={teamId =>
                  void run(() => client.disconnectSlackWorkspace(teamId))
                }
                onSetEnabled={(teamId, enabled) =>
                  void run(() =>
                    client.setSlackWorkspaceEnabled(teamId, enabled)
                  )
                }
                onRefreshChannels={teamId =>
                  void slack.refreshDirectory(teamId)
                }
                relayState={relayState}
              />
            ))}
          </div>
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
                Use your agents from a Slack workspace — complete Relay Agent
                and Socket Mode support.
              </p>
            </div>
          </div>
        )}
      </section>

      <SlackOneClickDialog
        open={oneClickOpen}
        busy={slack.busy}
        waiting={oneClickWaiting}
        error={oneClickError}
        onOpenChange={setOneClickOpen}
        onRetry={() => void startOneClick()}
        onOpenManual={openManual}
      />

      <SlackAddWorkspaceModal
        open={manualOpen}
        client={client}
        busy={slack.busy}
        updatingWorkspace={updating}
        onOpenChange={next => {
          setManualOpen(next)
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
