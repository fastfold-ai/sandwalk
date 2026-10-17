import type { AgentSession } from '@sandwalk/agent-ui-core'
import { toast } from 'sonner'

import { useExternalAgentActions } from '@/lib/external-agent-actions'

/**
 * "Duplicate chat": clone the session on the server (settings + full message
 * history, fresh workspace), put it in the sidebar, and open it. Uses the
 * same bindings the Continue-in menu uses, so any menu can call it without
 * threading props through the tree.
 */
export async function duplicateChat(
  session: AgentSession
): Promise<AgentSession | null> {
  const bindings = useExternalAgentActions.getState().bindings
  if (!bindings) {
    toast.error('Not connected to the Sandwalk server yet.')
    return null
  }
  const key = `duplicate:${session.id}`
  const actions = useExternalAgentActions.getState()
  if (actions.busy[key]) return null
  actions.setBusy(key, true)
  try {
    const clone = await bindings.client.duplicateSession(session.id)
    bindings.upsertSession?.(clone)
    bindings.openItem(clone.id)
    void bindings.reloadSessions()
    toast.success(`Duplicated as “${clone.title}”.`)
    return clone
  } catch (error) {
    toast.error(
      error instanceof Error && error.message
        ? error.message
        : 'Could not duplicate the chat.'
    )
    return null
  } finally {
    useExternalAgentActions.getState().setBusy(key, false)
  }
}
