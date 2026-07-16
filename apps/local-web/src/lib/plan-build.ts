import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentPlanCard, RuntimeSettings } from '@sandwalk/agent-ui-core'

import { fileChipToken } from '@/components/agents/composer-parts'
import { titleFromPlanPath } from '@/components/agents/workspace-utils'
import type { SessionChatState } from '@/lib/sessions'

export function planCardFromPath(path: string): AgentPlanCard {
  return {
    path,
    title: titleFromPlanPath(path),
    summary: ''
  }
}

/** Switch to Agent mode and ask the agent to execute a plan file. */
export async function startPlanBuild({
  sessionId,
  plan,
  patchChat,
  client,
  setRuntimeSettings,
  handleComposerSend
}: {
  sessionId: string
  plan: AgentPlanCard
  patchChat: (
    sessionId: string,
    updater: (prev: SessionChatState) => SessionChatState
  ) => void
  client: LocalAgentClient
  setRuntimeSettings: (settings: RuntimeSettings) => void
  handleComposerSend: (text: string) => void
}): Promise<void> {
  patchChat(sessionId, prev => ({
    ...prev,
    activeBuildPlan: plan,
    builtPlanPaths: prev.builtPlanPaths.includes(plan.path)
      ? prev.builtPlanPaths
      : [...prev.builtPlanPaths, plan.path]
  }))
  try {
    const next = await client.updateRuntimeSettings({ planMode: false })
    setRuntimeSettings(next)
  } catch {
    // Best-effort mode switch; still ask the agent to build.
  }
  handleComposerSend(`Execute the plan at ${fileChipToken(plan.path)}`)
}
