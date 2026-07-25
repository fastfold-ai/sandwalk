import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSession,
  AgentSkill,
  McpServer,
  RuntimeSettings,
  Specialist,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import type { ComponentProps } from 'react'

import { AgentComposerSlot } from '@/components/agents/AgentComposerSlot'

type AgentComposerSlotProps = ComponentProps<typeof AgentComposerSlot>

type UseAgentComposerSlotPropsInput = {
  sessionId: string | null
  session: AgentSession | null
  client: LocalAgentClient
  navigate: AgentComposerSlotProps['navigate']
  pendingAttachmentsRef: AgentComposerSlotProps['pendingAttachmentsRef']
  composerLiveRef: AgentComposerSlotProps['composerLiveRef']
  queuedMessages: AgentComposerSlotProps['queuedMessages']
  editingQueuedId: AgentComposerSlotProps['editingQueuedId']
  editQueuedMessage: AgentComposerSlotProps['editQueuedMessage']
  sendQueuedMessageNow: AgentComposerSlotProps['sendQueuedMessageNow']
  removeQueuedMessage: AgentComposerSlotProps['removeQueuedMessage']
  cancelEditQueuedMessage: AgentComposerSlotProps['cancelEditQueuedMessage']
  composer: AgentComposerSlotProps['composer']
  runActive: boolean
  skills: AgentSkill[]
  mcpServers: McpServer[]
  composerSkills: AgentComposerSlotProps['composerSkills']
  composerFiles: AgentComposerSlotProps['composerFiles']
  workspaceFiles: WorkspaceFile[]
  modelOptions: AgentComposerSlotProps['modelOptions']
  specialists: Specialist[]
  sessionSandboxStatus: AgentComposerSlotProps['sessionSandboxStatus']
  sessionSandboxPhase: AgentComposerSlotProps['sessionSandboxPhase']
  setComposer: AgentComposerSlotProps['setComposer']
  setComposerSkills: AgentComposerSlotProps['setComposerSkills']
  setComposerFiles: AgentComposerSlotProps['setComposerFiles']
  setFilesPanelCollapsed: AgentComposerSlotProps['setFilesPanelCollapsed']
  setPendingOpenPath: AgentComposerSlotProps['setPendingOpenPath']
  handleComposerSend: AgentComposerSlotProps['handleComposerSend']
  handleStop: AgentComposerSlotProps['handleStop']
  setWorkspaceVersion: AgentComposerSlotProps['setWorkspaceVersion']
  runtimeSettings: RuntimeSettings | null
  tokenUsage: AgentComposerSlotProps['tokenUsage']
  selectSessionSpecialist: AgentComposerSlotProps['selectSessionSpecialist']
  selectSessionSandboxBackend: AgentComposerSlotProps['selectSessionSandboxBackend']
  updateSessionSandboxCompute: AgentComposerSlotProps['updateSessionSandboxCompute']
  startSessionSandbox: AgentComposerSlotProps['startSessionSandbox']
  stopSessionSandbox: AgentComposerSlotProps['stopSessionSandbox']
  restartSessionSandbox: AgentComposerSlotProps['restartSessionSandbox']
  setRuntimeSettings: AgentComposerSlotProps['setRuntimeSettings']
  loadModelOptions: AgentComposerSlotProps['loadModelOptions']
}

export function buildAgentComposerSlotProps(
  input: UseAgentComposerSlotPropsInput
): AgentComposerSlotProps {
  const loadSkillDetail = (name: string) => input.client.getSkill(name)

  return {
    sessionId: input.sessionId,
    session: input.session,
    client: input.client,
    navigate: input.navigate,
    pendingAttachmentsRef: input.pendingAttachmentsRef,
    composerLiveRef: input.composerLiveRef,
    queuedMessages: input.queuedMessages,
    editingQueuedId: input.editingQueuedId,
    editQueuedMessage: input.editQueuedMessage,
    sendQueuedMessageNow: input.sendQueuedMessageNow,
    removeQueuedMessage: input.removeQueuedMessage,
    cancelEditQueuedMessage: input.cancelEditQueuedMessage,
    composer: input.composer,
    runActive: input.runActive,
    skills: input.skills,
    mcpServers: input.mcpServers,
    composerSkills: input.composerSkills,
    composerFiles: input.composerFiles,
    workspaceFiles: input.workspaceFiles,
    modelOptions: input.modelOptions,
    specialists: input.specialists,
    sessionSandboxStatus: input.sessionSandboxStatus,
    sessionSandboxPhase: input.sessionSandboxPhase,
    setComposer: input.setComposer,
    setComposerSkills: input.setComposerSkills,
    setComposerFiles: input.setComposerFiles,
    setFilesPanelCollapsed: input.setFilesPanelCollapsed,
    setPendingOpenPath: input.setPendingOpenPath,
    handleComposerSend: input.handleComposerSend,
    handleStop: input.handleStop,
    loadSkillDetail,
    setWorkspaceVersion: input.setWorkspaceVersion,
    runtimeSettings: input.runtimeSettings,
    tokenUsage: input.tokenUsage,
    selectSessionSpecialist: input.selectSessionSpecialist,
    selectSessionSandboxBackend: input.selectSessionSandboxBackend,
    updateSessionSandboxCompute: input.updateSessionSandboxCompute,
    startSessionSandbox: input.startSessionSandbox,
    stopSessionSandbox: input.stopSessionSandbox,
    restartSessionSandbox: input.restartSessionSandbox,
    setRuntimeSettings: input.setRuntimeSettings,
    loadModelOptions: input.loadModelOptions
  }
}
